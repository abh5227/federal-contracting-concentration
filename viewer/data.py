"""Read-only DuckDB access to the FY2025 pilot Parquet files, for the viewer.

Two tables, both opened read-only from the pipeline's outputs:
  b = Layer B (typed working columns), one row per transaction
  a = Layer A (all 297 source columns as text), joined to b on the lineage
      columns only when a query needs a column that exists only in Layer A

Safety rules followed everywhere in this module:
  - every column name and sort key is checked against the real column list
    (the Parquet schemas) before it is put into SQL, and is always quoted;
  - every filter value is passed to DuckDB as a bound parameter, never
    pasted into the SQL text;
  - money is summed as DECIMAL and returned as an exact string.
"""

from __future__ import annotations

import json
import re
import tempfile
import time
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import duckdb
import pyarrow.parquet as pq

from src import config

FISCAL_YEAR = 2025
LINEAGE = ("_source_file", "_source_member_idx", "_source_row")
KEY = "contract_transaction_unique_key"
AWARD_KEY = "contract_award_unique_key"
MONEY = "federal_action_obligation"

DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 1000
EXPORT_CAP = 100_000
DROPDOWN_MAX_DISTINCT = 200       # text columns with at most this many distinct values get a dropdown
GROUPBY_TOP = 50
MAX_FILTERS = 50
MAX_VALUE_LEN = 500

# Operators allowed per column kind.
TEXT_OPS = {"eq", "contains", "is", "blank"}
TYPED_OPS = {"min", "max", "is", "blank"}

VALUE_PATTERNS = {
    "decimal": re.compile(r"-?[0-9]+(\.[0-9]+)?"),
    "int": re.compile(r"-?[0-9]+"),
    "date": re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}"),
}
DUCKDB_KIND = {"VARCHAR": "text", "DATE": "date", "INTEGER": "int"}


class BadRequest(ValueError):
    """Raised for any invalid user input; the server turns it into HTTP 400."""


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def sql_string(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


# ---------------------------------------------------------------------------
# Request state
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Filter:
    col: str
    op: str
    value: str | None


@dataclass(frozen=True)
class State:
    filters: tuple[Filter, ...] = ()
    sort: str = "action_date"
    desc: bool = True
    cols: tuple[str, ...] = ()
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
    gb: str | None = None
    gb_order: str = "rows"


@dataclass
class Column:
    name: str
    position: int          # 1-based position in the source CSV header
    in_b: bool             # True if Layer B has it (typed); else read from Layer A as text
    kind: str              # text | decimal | date | int
    b_type: str | None = None


@dataclass
class Catalog:
    header: list[str]
    columns: dict[str, Column]
    layer_b_cols: list[str]
    default_cols: list[str]
    descriptions: dict[str, str] = field(default_factory=dict)  # code column -> description column


# ---------------------------------------------------------------------------
# The database
# ---------------------------------------------------------------------------

class ViewerDB:
    def __init__(self, fiscal_year: int = FISCAL_YEAR):
        self.fy = fiscal_year
        self.layer_b_path = config.layer_b_path(fiscal_year)
        self.report_path = config.REPORTS_DIR / f"reconciliation_fy{fiscal_year}.json"
        self.reference = self._load_reference()
        self.layer_a_files = self._layer_a_files()
        self.catalog = self._build_catalog()
        self.con = duckdb.connect(":memory:")
        spill = Path(tempfile.gettempdir()) / "fy2025_viewer_duckdb"   # never spill into the repo
        self.con.execute(f"SET temp_directory = {sql_string(str(spill))}")
        # No network: never auto-install or auto-load extensions.
        self.con.execute("SET autoinstall_known_extensions = false")
        self.con.execute("SET autoload_known_extensions = false")
        self.con.execute("SET enable_progress_bar = false")
        self.view_sql = {
            "b": f"CREATE VIEW b AS SELECT * FROM read_parquet({sql_string(str(self.layer_b_path))});",
            "a": "CREATE VIEW a AS SELECT * FROM read_parquet(["
                 + ", ".join(sql_string(str(p)) for p in self.layer_a_files) + "]);",
        }
        for v in self.view_sql.values():
            self.con.execute(v)
        self.startup_check = self._startup_check()

    # -- setup ---------------------------------------------------------------

    def _load_reference(self) -> dict:
        r = json.loads(self.report_path.read_text(encoding="utf-8"))
        agencies = r["checks"][7]["details"]["agencies"]       # check 8: totals by awarding agency
        return {"rows": int(r["row_count"]), "net": Decimal(r["grand_total_obligations"]),
                "agencies": agencies, "report": str(self.report_path.relative_to(config.REPO_ROOT))}

    def _layer_a_files(self) -> list[Path]:
        """The explicit member list from the reconciliation report (never a glob; see review S5)."""
        r = json.loads(self.report_path.read_text(encoding="utf-8"))
        names = [Path(x["parquet"]).name for x in r["supplementary"]["layer_a_files"]]
        paths = [config.layer_a_dir(self.fy) / n for n in names]
        missing = [str(p) for p in paths if not p.exists()]
        if missing:
            raise FileNotFoundError(f"Layer A files listed in the report are missing: {missing}")
        return paths

    def _build_catalog(self) -> Catalog:
        a_schema = pq.read_schema(self.layer_a_files[0])
        header = [n for n in a_schema.names if n not in LINEAGE]
        b_schema = duckdb.sql(f"DESCRIBE SELECT * FROM read_parquet({sql_string(str(self.layer_b_path))})").fetchall()
        b_types = {name: typ for name, typ, *_ in b_schema if name not in LINEAGE}
        columns = {}
        for i, name in enumerate(header, start=1):
            if name in b_types:
                t = b_types[name]
                kind = "decimal" if t.startswith("DECIMAL") else DUCKDB_KIND.get(t, "text")
                columns[name] = Column(name, i, True, kind, t)
            else:
                columns[name] = Column(name, i, False, "text")
        unknown_b = set(b_types) - set(header)
        if unknown_b:
            raise ValueError(f"Layer B has columns not in the source header: {sorted(unknown_b)}")
        layer_b_cols = [n for n in header if n in b_types]
        descriptions = {}
        for name in header:
            base = name[:-5] if name.endswith("_code") else None
            for cand in ([base, f"{base}_description", f"{base}_name"] if base else []) + [f"{name}_description"]:
                if cand and cand in columns and cand != name:
                    descriptions[name] = cand
                    break
        return Catalog(header, columns, layer_b_cols, layer_b_cols, descriptions)

    def _startup_check(self) -> dict:
        """Row counts of both layers against the reconciliation report (cheap: Parquet metadata)."""
        rows_a = sum(pq.ParquetFile(p).metadata.num_rows for p in self.layer_a_files)
        rows_b = pq.ParquetFile(self.layer_b_path).metadata.num_rows
        stray = sorted({p.name for p in config.layer_a_dir(self.fy).glob("*.parquet")}
                       - {p.name for p in self.layer_a_files})
        return {"layer_a_rows": rows_a, "layer_b_rows": rows_b, "reference_rows": self.reference["rows"],
                "consistent": rows_a == rows_b == self.reference["rows"], "ignored_layer_a_files": stray}

    # -- state parsing -----------------------------------------------------

    def parse_state(self, params: dict[str, str]) -> State:
        cat = self.catalog.columns
        filters = []
        raw_f = params.get("f") or "[]"
        try:
            items = json.loads(raw_f)
        except json.JSONDecodeError as e:
            raise BadRequest(f"filters are not valid JSON: {e}") from None
        if not isinstance(items, list) or len(items) > MAX_FILTERS:
            raise BadRequest("filters must be a list of at most %d [column, op, value] items" % MAX_FILTERS)
        for it in items:
            if not (isinstance(it, list) and len(it) in (2, 3) and all(isinstance(x, str) for x in it)):
                raise BadRequest(f"bad filter item: {it!r}")
            col, op = it[0], it[1]
            value = it[2] if len(it) == 3 else None
            c = self._column(col)
            allowed = TEXT_OPS if c.kind == "text" else TYPED_OPS
            if op not in allowed:
                raise BadRequest(f"operator {op!r} not allowed for {c.kind} column {col!r}")
            if op != "blank":
                if value is None or (value == "" and op != "is"):
                    raise BadRequest(f"filter on {col!r} needs a value")
                if len(value) > MAX_VALUE_LEN:
                    raise BadRequest("filter value too long")
                if c.kind != "text":
                    self._typed_value(c, value)   # validate now, raise 400 if bad
            filters.append(Filter(col, op, value))

        cols_raw = params.get("cols")
        cols = tuple(cols_raw.split(",")) if cols_raw else tuple(self.catalog.default_cols)
        for col in cols:
            self._column(col)
        if len(set(cols)) != len(cols) or not cols:
            raise BadRequest("cols must be a non-empty list without duplicates")

        sort = params.get("sort") or "action_date"
        self._column(sort)
        direction = params.get("dir") or "desc"
        if direction not in ("asc", "desc"):
            raise BadRequest("dir must be asc or desc")
        page = self._int(params.get("page"), 1, 1, 10_000_000, "page")
        page_size = self._int(params.get("ps"), DEFAULT_PAGE_SIZE, 1, MAX_PAGE_SIZE, "ps")
        gb = params.get("gb") or None
        if gb is not None:
            self._column(gb)
        gb_order = params.get("gbo") or "rows"
        if gb_order not in ("rows", "net"):
            raise BadRequest("gbo must be rows or net")
        return State(tuple(filters), sort, direction == "desc", cols, page, page_size, gb, gb_order)

    def _column(self, name: str) -> Column:
        c = self.catalog.columns.get(name)
        if c is None:
            raise BadRequest(f"unknown column: {name!r}")
        return c

    @staticmethod
    def _int(raw, default, lo, hi, label) -> int:
        if raw in (None, ""):
            return default
        if not re.fullmatch(r"[0-9]+", raw):
            raise BadRequest(f"{label} must be a whole number")
        v = int(raw)
        if not lo <= v <= hi:
            raise BadRequest(f"{label} must be between {lo} and {hi}")
        return v

    @staticmethod
    def _typed_value(c: Column, value: str):
        if not VALUE_PATTERNS[c.kind].fullmatch(value):
            raise BadRequest(f"{value!r} is not a valid {c.kind} for {c.name!r}")
        if c.kind == "decimal":
            return Decimal(value)
        if c.kind == "int":
            return int(value)
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise BadRequest(f"{value!r} is not a real date") from None

    # -- SQL building ---------------------------------------------------------

    def ref(self, name: str) -> str:
        c = self._column(name)
        return f"{'b' if c.in_b else 'a'}.{q(name)}"

    def _needs_a(self, names) -> bool:
        return any(not self._column(n).in_b for n in names)

    def _from(self, names) -> str:
        if self._needs_a(names):
            return ("b JOIN a ON a._source_member_idx = b._source_member_idx "
                    "AND a._source_row = b._source_row")
        return "b"

    def _where(self, filters) -> tuple[str, list]:
        clauses, params = [], []
        for f in filters:
            c = self._column(f.col)
            r = self.ref(f.col)
            if f.op == "blank":
                clauses.append(f"({r} IS NULL OR {r} = '')" if c.kind == "text" else f"{r} IS NULL")
            elif c.kind == "text":
                if f.op == "eq":
                    clauses.append(f"lower({r}) = lower(?)")
                elif f.op == "contains":
                    clauses.append(f"contains(lower({r}), lower(?))")
                else:  # is: exact match (dropdowns, group-by clicks, award button)
                    clauses.append(f"{r} = ?")
                params.append(f.value)
            else:
                opsym = {"min": ">=", "max": "<=", "is": "="}[f.op]
                clauses.append(f"{r} {opsym} ?")
                params.append(self._typed_value(c, f.value))
        return (" AND ".join(clauses) if clauses else "TRUE"), params

    def _referenced(self, state: State, *extra) -> list[str]:
        return [f.col for f in state.filters] + list(extra)

    def rows_sql(self, state: State, limit: int, offset: int) -> tuple[str, list]:
        """One page of rows, in two steps inside one statement ("late materialization").

        Step 1 (the CTE) finds which rows are on the page using only the filter
        and sort columns. Step 2 fetches the visible columns for just those rows
        by joining back on the lineage columns. Without this, showing many
        Layer A columns made DuckDB decode all 6.6M rows of every visible
        column before keeping 100 (90 s for a deep page with all 297 columns).
        The outer ORDER BY repeats the page order exactly: sort value, then the
        unique transaction key.
        """
        where, params = self._where(state.filters)
        direction = "DESC" if state.desc else "ASC"
        inner_from = self._from(self._referenced(state, state.sort))
        visible_from = "page JOIN b ON b._source_member_idx = page._m AND b._source_row = page._r"
        if self._needs_a(state.cols):
            visible_from += "\n     JOIN a ON a._source_member_idx = page._m AND a._source_row = page._r"
        select = ", ".join(f"{self.ref(c)} AS {q(c)}" for c in state.cols)
        sql = (f"WITH page AS (\n"
               f"  SELECT b._source_member_idx AS _m, b._source_row AS _r, b.{q(KEY)} AS _key,\n"
               f"         {self.ref(state.sort)} AS _sort\n"
               f"  FROM {inner_from}\n  WHERE {where}\n"
               f"  ORDER BY _sort {direction} NULLS LAST, _key ASC   -- transaction key breaks ties: stable paging\n"
               f"  LIMIT ? OFFSET ?\n)\n"
               f"SELECT page._key, page._m, page._r,\n       {select}\n"
               f"FROM {visible_from}\n"
               f"ORDER BY page._sort {direction} NULLS LAST, page._key ASC")
        return sql, params + [limit, offset]

    def totals_sql(self, state: State) -> tuple[str, list]:
        names = self._referenced(state)
        where, params = self._where(state.filters)
        sql = (f"SELECT COUNT(*) AS rows, SUM(b.{q(MONEY)}) AS net_obligations\n"
               f"FROM {self._from(names)}\nWHERE {where}")
        return sql, params

    def groupby_sql(self, state: State) -> tuple[str, list]:
        names = self._referenced(state, state.gb)
        where, params = self._where(state.filters)
        g = self.ref(state.gb)
        order = "n DESC, net DESC" if state.gb_order == "rows" else "net DESC NULLS LAST, n DESC"
        sql = (f"WITH g AS (\n"
               f"  SELECT {g} AS value, COUNT(*) AS n, SUM(b.{q(MONEY)}) AS net,\n"
               f"         COUNT(*) FILTER (WHERE b.{q(MONEY)} < 0) AS negative_rows\n"
               f"  FROM {self._from(names)}\n  WHERE {where}\n  GROUP BY 1\n"
               f"), r AS (\n"
               f"  SELECT *, row_number() OVER (ORDER BY {order}, value ASC NULLS LAST) AS rank FROM g\n"
               f")\n"
               f"SELECT FALSE AS is_other, value, n, net, negative_rows, rank, 1 AS groups FROM r WHERE rank <= ?\n"
               f"UNION ALL\n"
               f"SELECT TRUE, NULL, SUM(n), SUM(net), SUM(negative_rows), NULL, COUNT(*) FROM r WHERE rank > ?\n"
               f"ORDER BY is_other, rank")
        return sql, params + [GROUPBY_TOP, GROUPBY_TOP]

    def display_sql(self, sql: str, params: list) -> str:
        """The SQL with parameter values written in, for people to read and rerun (never executed)."""
        parts = sql.split("?")
        if len(parts) - 1 != len(params):
            raise AssertionError("placeholder count mismatch")
        out = [parts[0]]
        for p, rest in zip(params, parts[1:]):
            if isinstance(p, str):
                lit = sql_string(p)
            elif isinstance(p, date):
                lit = f"DATE '{p.isoformat()}'"
            else:
                lit = str(p)
            out.append(lit + rest)
        return "".join(out)

    # -- queries ----------------------------------------------------------------

    def _run(self, sql: str, params: list, with_names: bool = False):
        cur = self.con.cursor()
        try:
            t0 = time.perf_counter()
            res = cur.execute(sql, params)
            names = [d[0] for d in res.description]
            out = res.fetchall()
            ms = round((time.perf_counter() - t0) * 1000, 1)
            return (out, ms, names) if with_names else (out, ms)
        finally:
            cur.close()

    def rows(self, state: State) -> dict:
        offset = (state.page - 1) * state.page_size
        sql, params = self.rows_sql(state, state.page_size, offset)
        res, ms = self._run(sql, params)
        return {"columns": list(state.cols),
                "kinds": {c: self._column(c).kind for c in state.cols},
                "keys": [[r[0], r[1], r[2]] for r in res],
                "rows": [list(r[3:]) for r in res],
                "page": state.page, "page_size": state.page_size, "offset": offset,
                "sql": self.display_sql(sql, params), "ms": ms}

    def totals(self, state: State) -> dict:
        return dict(self._totals_cached(json.dumps([[f.col, f.op, f.value] for f in state.filters])))

    @lru_cache(maxsize=256)
    def _totals_cached(self, filters_json: str) -> dict:
        state = State(filters=tuple(Filter(*f) for f in json.loads(filters_json)))
        sql, params = self.totals_sql(state)
        res, ms = self._run(sql, params)
        n, net = res[0]
        net = net if net is not None else Decimal("0.00")
        unfiltered = not state.filters
        return {"rows": n, "net": net, "filtered": not unfiltered,
                "reference": {"rows": self.reference["rows"], "net": self.reference["net"],
                              "report": self.reference["report"]},
                "matches_reference": (n == self.reference["rows"] and net == self.reference["net"])
                if unfiltered else None,
                "sql": self.display_sql(sql, params), "ms": ms}

    def groupby(self, state: State) -> dict:
        if not state.gb:
            raise BadRequest("gb (group-by column) is required")
        key = json.dumps([[[f.col, f.op, f.value] for f in state.filters], state.gb, state.gb_order])
        return self._groupby_cached(key)

    @lru_cache(maxsize=128)
    def _groupby_cached(self, key: str) -> dict:
        filters, gb, gbo = json.loads(key)
        state = State(filters=tuple(Filter(*f) for f in filters), gb=gb, gb_order=gbo)
        totals = self._totals_cached(json.dumps(filters))
        sql, params = self.groupby_sql(state)
        res, ms = self._run(sql, params)
        total_n, total_net = totals["rows"], totals["net"]

        def pct(x, total):
            if x is None or not total:
                return None
            return str((Decimal(x) * 100 / Decimal(total)).quantize(Decimal("0.01")))

        values, other = [], None
        for is_other, value, n, net, neg, rank, groups in res:
            entry = {"rows": n or 0, "net": net if net is not None else Decimal("0.00"),
                     "negative_rows": neg or 0, "pct_net": pct(net, total_net), "pct_rows": pct(n, total_n)}
            if is_other:
                other = {**entry, "distinct_values": groups}
            else:
                entry.update({"value": value, "blank": value is None or value == "", "rank": rank})
                values.append(entry)
        return {"column": gb, "kind": self._column(gb).kind, "order": gbo, "top": GROUPBY_TOP,
                "values": values, "other": other,
                "distinct_values": len(values) + (other["distinct_values"] if other else 0),
                "filtered_rows": total_n, "filtered_net": total_net,
                "sql": self.display_sql(sql, params), "ms": ms}

    @lru_cache(maxsize=512)
    def values(self, column: str) -> dict:
        """Dropdown options for a text column with few distinct values (counts over all FY2025 rows)."""
        c = self._column(column)
        if c.kind != "text":
            return {"column": column, "dropdown": False, "kind": c.kind}
        # Layer A stores blanks as '', so COUNT(DISTINCT) counts "blank" as one value.
        res, ms1 = self._run(f"SELECT COUNT(DISTINCT {q(column)}), COUNT(*) FILTER (WHERE {q(column)} = '') FROM a", [])
        total_distinct, blank_rows = res[0]
        if total_distinct > DROPDOWN_MAX_DISTINCT:
            return {"column": column, "dropdown": False, "kind": "text", "distinct": total_distinct,
                    "cutoff": DROPDOWN_MAX_DISTINCT}
        desc = self.catalog.descriptions.get(column)
        if desc:
            sql = (f"WITH g AS (SELECT {q(column)} AS v, {q(desc)} AS d, COUNT(*) AS n FROM a GROUP BY 1, 2)\n"
                   f"SELECT v, arg_max(d, n), SUM(n) FROM g GROUP BY v ORDER BY SUM(n) DESC, v")
        else:
            sql = f"SELECT {q(column)}, NULL, COUNT(*) FROM a GROUP BY 1 ORDER BY 3 DESC, 1"
        res, ms2 = self._run(sql, [])
        return {"column": column, "dropdown": True, "kind": "text", "distinct": total_distinct,
                "cutoff": DROPDOWN_MAX_DISTINCT, "description_column": desc,
                "blank_rows": blank_rows,
                "options": [{"value": v, "label": d, "rows": int(n), "blank": v == ""} for v, d, n in res],
                "ms": round(ms1 + ms2, 1)}

    def row_detail(self, member_idx: str, row: str) -> dict:
        m = self._int(member_idx, None, 1, 32767, "m")
        r = self._int(row, None, 1, 10_000_000_000, "r")
        sql = "SELECT * FROM a WHERE _source_member_idx = ? AND _source_row = ?"
        res, ms, cols = self._run(sql, [m, r], with_names=True)
        if len(res) != 1:
            raise BadRequest(f"expected one Layer A row for member {m} row {r}, found {len(res)}")
        names = self.catalog.header + list(LINEAGE)
        record = dict(zip(cols, res[0]))
        return {"fields": [[n, record[n]] for n in names], "award_key": record[AWARD_KEY],
                "key": record[KEY], "sql": self.display_sql(sql, [m, r]), "ms": ms}

    def export_rows(self, state: State):
        """Yield the header, then rows of the filtered view in the current sort, up to EXPORT_CAP."""
        sql, params = self.rows_sql(state, EXPORT_CAP, 0)
        cur = self.con.cursor()
        try:
            res = cur.execute(sql, params)
            yield list(state.cols)
            while True:
                chunk = res.fetchmany(10_000)
                if not chunk:
                    break
                for r in chunk:
                    yield list(r[3:])
        finally:
            cur.close()

    def meta(self) -> dict:
        cat = self.catalog
        return {
            "fiscal_year": self.fy,
            "columns": [{"name": c.name, "position": c.position, "layer": "B" if c.in_b else "A",
                         "kind": c.kind, "type": c.b_type or "VARCHAR (Layer A text)"}
                        for c in (cat.columns[n] for n in cat.header)],
            "default_cols": cat.default_cols,
            "default_sort": "action_date", "default_dir": "desc",
            "page_size": DEFAULT_PAGE_SIZE, "export_cap": EXPORT_CAP,
            "dropdown_max_distinct": DROPDOWN_MAX_DISTINCT, "groupby_top": GROUPBY_TOP,
            "reference": {"rows": self.reference["rows"], "net": self.reference["net"],
                          "report": self.reference["report"]},
            "startup_check": self.startup_check,
            "files": {"layer_b": str(self.layer_b_path), "layer_a": [str(p) for p in self.layer_a_files]},
            "view_sql": self.view_sql,
        }
