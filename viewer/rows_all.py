"""Row browser across every present fiscal year, read-only, over Stage 1 (Layer A text).

Same rules as the FY2025 viewer (viewer/data.py): column names are checked against the real header and
quoted; filter values are bound parameters; money is summed as DECIMAL and returned as an exact string;
pages use late materialization (find the page's row ids first, then fetch the visible columns).

Layer A is all text. Three columns get typed operators: fiscal_year (int, added from the file it came
from), action_date (date) and federal_action_obligation (decimal). Their typed value is computed in SQL
with TRY_CAST; nothing is stored or changed.

Totals without row-level filters are summed from Stage 2's keys_dims (one narrow row per transaction: key, year,
typed amount, the four global-filter dimensions), which is much faster than casting 84 million text amounts.
The flag filter is a semi-join on (fiscal_year, key) against Stage 2's row flags.
"""

from __future__ import annotations

import json
import re
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import duckdb

from src import config, stage1, stage2

KEY = "contract_transaction_unique_key"
AWARD_KEY = "contract_award_unique_key"
MONEY = "federal_action_obligation"
ROWID = ("fiscal_year", "_source_member_idx", "_source_row")
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 1000
EXPORT_CAP = 100_000
DROPDOWN_MAX_DISTINCT = 200
GROUPBY_TOP = 50
MAX_FILTERS = 50
MAX_VALUE_LEN = 500
TEXT_OPS = {"eq", "contains", "is", "blank"}
TYPED_OPS = {"min", "max", "is", "blank"}
TYPED = {"fiscal_year": "int", "action_date": "date", MONEY: "decimal"}
VALUE_PATTERNS = {"decimal": re.compile(r"-?[0-9]+(\.[0-9]+)?"), "int": re.compile(r"-?[0-9]+"),
                  "date": re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")}
DEFAULT_COLS = ["fiscal_year", KEY, AWARD_KEY, "award_id_piid", "modification_number", MONEY, "action_date",
                "awarding_agency_name", "awarding_sub_agency_name", "recipient_name", "recipient_uei",
                "recipient_parent_name", "product_or_service_code", "naics_code", "extent_competed_code",
                "type_of_set_aside_code", "award_type_code"]
DIM_SQL = {"agency": "a.awarding_agency_code", "subagency": "a.awarding_sub_agency_code",
           "award_type": "(CASE WHEN a.award_or_idv_flag = 'IDV' THEN 'IDV_' || a.idv_type_code ELSE a.award_type_code END)",
           "psc_cat": "left(a.product_or_service_code, 1)"}
KD_DIM = {d: f"kd.{d}" for d in DIM_SQL}      # the same dimensions, precomputed in Stage 2's keys_dims (stage2.DIMS_SQL)


class BadRequest(ValueError):
    pass


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def sql_string(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


@dataclass(frozen=True)
class Filter:
    col: str
    op: str
    value: str | None


@dataclass(frozen=True)
class State:
    g: str = "{}"                       # global filters, already validated JSON (canonical)
    filters: tuple[Filter, ...] = ()
    flag: str | None = None
    sort: str = "action_date"
    desc: bool = True
    cols: tuple[str, ...] = ()
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
    gb: str | None = None
    gb_order: str = "rows"


class RowsDB:
    def __init__(self, flag_ids: set[str]):
        # Years proven in Stage 1 AND profiled in Stage 2 (the flag filter needs Stage 2's row flags).
        self.years = [fy for fy in stage2.present_years() if stage1.load_progress(fy).get("status") == "PASS"]
        self.flag_ids = flag_ids
        self.files = {fy: stage1.layer_a_files(fy) for fy in self.years}
        self.header = json.loads((config.layer_a_dir(self.years[0]) / "_files.json").read_text())["columns"]
        self.columns = ["fiscal_year"] + self.header
        self.kinds = {c: TYPED.get(c, "text") for c in self.columns}
        self.proof = {fy: (sum(m["raw_records"] for m in stage1.load_progress(fy)["members"].values()),
                           sum(Decimal(m["raw_dollars"]) for m in stage1.load_progress(fy)["members"].values()))
                      for fy in self.years}
        self.con = duckdb.connect(":memory:")
        self.con.execute(f"SET temp_directory = '{Path(tempfile.gettempdir()) / 'fy_rows_duckdb'}'")
        self.con.execute("SET autoinstall_known_extensions = false")
        self.con.execute("SET autoload_known_extensions = false")
        self.con.execute("SET enable_progress_bar = false")
        union = " UNION ALL ".join(
            f"SELECT CAST({fy} AS SMALLINT) AS fiscal_year, * FROM read_parquet([{', '.join(sql_string(str(p)) for p in fs)}])"
            for fy, fs in self.files.items())
        flags = [config.INTEGRITY_DIR / "row_flags" / f"fy{fy}.parquet" for fy in self.years]
        kd = [stage2.year_dir(fy) / "keys_dims.parquet" for fy in self.years]
        self.view_sql = {
            "kd": f"CREATE VIEW kd AS SELECT CAST(fiscal_year AS SMALLINT) AS fiscal_year, {KEY}, amt, agency, subagency, "
                  f"award_type, psc_cat FROM read_parquet([{', '.join(sql_string(str(p)) for p in kd)}]);",
            "a": f"CREATE VIEW a AS {union};",
            "flags": "CREATE VIEW flags AS SELECT contract_transaction_unique_key AS k, CAST(fiscal_year AS SMALLINT) AS fy, flag_id "
                     f"FROM read_parquet([{', '.join(sql_string(str(p)) for p in flags)}]);",
        }
        for v in self.view_sql.values():
            self.con.execute(v)
        self.lock = threading.Lock()

    # ---------------------------------------------------------------- parsing

    def column(self, name: str) -> str:
        if name not in self.kinds:
            raise BadRequest(f"unknown column: {name!r}")
        return name

    @staticmethod
    def _int(raw, default, lo, hi, label) -> int:
        if raw in (None, ""):
            return default
        if not re.fullmatch(r"[0-9]+", str(raw)):
            raise BadRequest(f"{label} must be a whole number")
        v = int(raw)
        if not lo <= v <= hi:
            raise BadRequest(f"{label} must be between {lo} and {hi}")
        return v

    def typed_value(self, col: str, value: str):
        kind = self.kinds[col]
        if not VALUE_PATTERNS[kind].fullmatch(value):
            raise BadRequest(f"{value!r} is not a valid {kind} for {col!r}")
        if kind == "decimal":
            return Decimal(value)
        if kind == "int":
            return int(value)
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise BadRequest(f"{value!r} is not a real date") from None

    def parse_state(self, params: dict, g: dict) -> State:
        try:
            items = json.loads(params.get("f") or "[]")
        except json.JSONDecodeError as e:
            raise BadRequest(f"filters are not valid JSON: {e}") from None
        if not isinstance(items, list) or len(items) > MAX_FILTERS:
            raise BadRequest(f"filters must be a list of at most {MAX_FILTERS} items")
        filters = []
        for it in items:
            if not (isinstance(it, list) and len(it) in (2, 3) and all(isinstance(x, str) for x in it)):
                raise BadRequest(f"bad filter item: {it!r}")
            col, op, value = it[0], it[1], (it[2] if len(it) == 3 else None)
            self.column(col)
            allowed = TEXT_OPS if self.kinds[col] == "text" else TYPED_OPS
            if op not in allowed:
                raise BadRequest(f"operator {op!r} not allowed for {self.kinds[col]} column {col!r}")
            if op != "blank":
                if value is None or (value == "" and op != "is"):
                    raise BadRequest(f"filter on {col!r} needs a value")
                if len(value) > MAX_VALUE_LEN:
                    raise BadRequest("filter value too long")
                if self.kinds[col] != "text":
                    self.typed_value(col, value)
            filters.append(Filter(col, op, value))
        flag = params.get("flag") or None
        if flag is not None and flag not in self.flag_ids:
            raise BadRequest("unknown flag")
        cols = tuple(params["cols"].split(",")) if params.get("cols") else tuple(DEFAULT_COLS)
        for c in cols:
            self.column(c)
        if not cols or len(set(cols)) != len(cols):
            raise BadRequest("cols must be a non-empty list without duplicates")
        sort = self.column(params.get("sort") or "action_date")
        direction = params.get("dir") or "desc"
        if direction not in ("asc", "desc"):
            raise BadRequest("dir must be asc or desc")
        gb = params.get("gb") or None
        if gb is not None:
            self.column(gb)
        gbo = params.get("gbo") or "rows"
        if gbo not in ("rows", "net"):
            raise BadRequest("gbo must be rows or net")
        return State(json.dumps(g, sort_keys=True), tuple(filters), flag, sort, direction == "desc", cols,
                     self._int(params.get("page"), 1, 1, 10_000_000, "page"),
                     self._int(params.get("ps"), DEFAULT_PAGE_SIZE, 1, MAX_PAGE_SIZE, "ps"), gb, gbo)

    # ---------------------------------------------------------------- SQL

    def ref(self, col: str) -> str:
        kind = self.kinds[col]
        if col == "fiscal_year":
            return "a.fiscal_year"
        if kind == "decimal":
            return f"TRY_CAST(NULLIF(a.{q(col)}, '') AS DECIMAL(38,6))"
        if kind == "date":
            return f"TRY_CAST(NULLIF(a.{q(col)}, '') AS DATE)"
        return f"a.{q(col)}"

    def sort_ref(self, col: str) -> str:
        # action_date sorts as its YYYY-MM-DD text (same order as the date; avoids a cast per row)
        return "a.action_date" if col == "action_date" else self.ref(col)

    def where(self, st: State, alias: str = "a") -> tuple[str, list]:
        """WHERE clause over Layer A (alias 'a') or, for totals without row-level filters, Stage 2's keys_dims ('kd')."""
        if alias == "kd" and st.filters:
            raise ValueError("row-level filters need Layer A")
        g = json.loads(st.g)
        clauses, params = [f"{alias}.fiscal_year BETWEEN ? AND ?"], list(g.get("fy") or [config.FIRST_FY, config.LAST_FY])
        for d, expr in (DIM_SQL if alias == "a" else KD_DIM).items():
            if g.get(d):
                clauses.append(f"{expr} IN (SELECT unnest(?))")
                params.append(g[d])
        if st.flag:
            # a semi-join on (year, key); a correlated EXISTS here took 30+ seconds over all years
            clauses.append(f"{{'y': {alias}.fiscal_year, 'k': {alias}.{KEY}}} IN "
                           "(SELECT {'y': fy, 'k': k} FROM flags WHERE flag_id = ?)")
            params.append(st.flag)
        for f in st.filters:
            r, kind = self.ref(f.col), self.kinds[f.col]
            if f.op == "blank":
                clauses.append(f"({r} IS NULL OR {r} = '')" if kind == "text" else f"{r} IS NULL")
            elif kind == "text":
                clauses.append({"eq": f"lower({r}) = lower(?)", "contains": f"contains(lower({r}), lower(?))",
                                "is": f"{r} = ?"}[f.op])
                params.append(f.value)
            else:
                clauses.append(f"{r} {dict(min='>=', max='<=', is_='=').get(f.op, '=')} ?")
                params.append(self.typed_value(f.col, f.value))
        return " AND ".join(clauses), params

    def rows_sql(self, st: State, limit: int, offset: int) -> tuple[str, list]:
        where, params = self.where(st)
        d = "DESC" if st.desc else "ASC"
        select = ", ".join(f"{self.ref(c)} AS {q(c)}" for c in st.cols)
        sql = (f"WITH page AS (\n  SELECT a.fiscal_year AS _y, a._source_member_idx AS _m, a._source_row AS _r,\n"
               f"         a.{q(KEY)} AS _key, {self.sort_ref(st.sort)} AS _sort\n  FROM a\n  WHERE {where}\n"
               f"  ORDER BY _sort {d} NULLS LAST, _key ASC, _y ASC\n  LIMIT ? OFFSET ?\n)\n"
               f"SELECT page._key, page._y, page._m, page._r,\n       {select}\n"
               f"FROM page JOIN a ON a.fiscal_year = page._y AND a._source_member_idx = page._m AND a._source_row = page._r\n"
               f"ORDER BY page._sort {d} NULLS LAST, page._key ASC, page._y ASC")
        return sql, params + [limit, offset]

    def display_sql(self, sql: str, params: list) -> str:
        parts = sql.split("?")
        out = [parts[0]]
        for p, rest in zip(params, parts[1:]):
            if isinstance(p, str):
                lit = sql_string(p)
            elif isinstance(p, list):
                lit = "[" + ", ".join(sql_string(x) for x in p) + "]"
            elif isinstance(p, date):
                lit = f"DATE '{p.isoformat()}'"
            else:
                lit = str(p)
            out.append(lit + rest)
        return "".join(out)

    def _run(self, sql: str, params: list):
        cur = self.con.cursor()
        try:
            t0 = time.perf_counter()
            res = cur.execute(sql, params)
            names = [x[0] for x in res.description]
            return res.fetchall(), round((time.perf_counter() - t0) * 1000, 1), names
        finally:
            cur.close()

    @staticmethod
    def dec(x) -> str:
        x = Decimal(x if x is not None else 0)
        c = x.quantize(Decimal("0.01"))
        return str(c if c == x else x)

    # ---------------------------------------------------------------- endpoints

    def rows(self, st: State) -> dict:
        offset = (st.page - 1) * st.page_size
        sql, params = self.rows_sql(st, st.page_size, offset)
        res, ms, _ = self._run(sql, params)
        conv = [(lambda v: self.dec(v) if v is not None else None) if self.kinds[c] == "decimal" else (lambda v: v)
                for c in st.cols]
        return {"columns": list(st.cols), "kinds": {c: self.kinds[c] for c in st.cols},
                "keys": [[r[0], r[1], r[2], r[3]] for r in res],
                "rows": [[f(v) for f, v in zip(conv, r[4:])] for r in res],
                "page": st.page, "page_size": st.page_size, "offset": offset,
                "sql": self.display_sql(sql, params), "ms": ms}

    def totals(self, st: State) -> dict:
        return dict(self._totals(st.g, json.dumps([[f.col, f.op, f.value] for f in st.filters]), st.flag))

    @lru_cache(maxsize=256)
    def _totals(self, g: str, filters: str, flag: str | None) -> dict:
        st = State(g=g, filters=tuple(Filter(*f) for f in json.loads(filters)), flag=flag)
        if st.filters:
            where, params = self.where(st)
            sql = f"SELECT COUNT(*), SUM({self.ref(MONEY)}) FROM a WHERE {where}"
        else:
            where, params = self.where(st, "kd")
            sql = f"SELECT COUNT(*), SUM(kd.amt) FROM kd WHERE {where}"
        res, ms, _ = self._run(sql, params)
        n, net = res[0]
        gd = json.loads(g)
        lo, hi = gd.get("fy") or [config.FIRST_FY, config.LAST_FY]
        unfiltered = not st.filters and not flag and not any(gd.get(d) for d in DIM_SQL)
        ref_rows = sum(self.proof[fy][0] for fy in self.years if lo <= fy <= hi)
        ref_net = sum((self.proof[fy][1] for fy in self.years if lo <= fy <= hi), Decimal(0))
        return {"rows": n, "net": self.dec(net), "filtered": not unfiltered,
                "reference": {"rows": ref_rows, "net": self.dec(ref_net), "source": "reports/integrity/stage1_mirror_proof.csv",
                              "years": [fy for fy in self.years if lo <= fy <= hi]},
                "matches_reference": (n == ref_rows and Decimal(net or 0) == ref_net) if unfiltered else None,
                "sql": self.display_sql(sql, params), "ms": ms}

    def groupby(self, st: State) -> dict:
        if not st.gb:
            raise BadRequest("gb (group-by column) is required")
        where, params = self.where(st)
        order = "n DESC, net DESC" if st.gb_order == "rows" else "net DESC NULLS LAST, n DESC"
        sql = (f"WITH g AS (SELECT {self.ref(st.gb)} AS value, COUNT(*) AS n, SUM({self.ref(MONEY)}) AS net,\n"
               f"  COUNT(*) FILTER (WHERE {self.ref(MONEY)} < 0) AS negative_rows FROM a WHERE {where} GROUP BY 1),\n"
               f"r AS (SELECT *, row_number() OVER (ORDER BY {order}, value ASC NULLS LAST) AS rank FROM g)\n"
               f"SELECT FALSE, value, n, net, negative_rows, rank, 1 FROM r WHERE rank <= ?\nUNION ALL\n"
               f"SELECT TRUE, NULL, SUM(n), SUM(net), SUM(negative_rows), NULL, COUNT(*) FROM r WHERE rank > ?\n"
               f"ORDER BY 1, rank")
        res, ms, _ = self._run(sql, params + [GROUPBY_TOP, GROUPBY_TOP])
        tot = self.totals(st)
        tn, tnet = tot["rows"], Decimal(tot["net"])

        def pct(x, total):
            return None if x is None or not total else str((Decimal(x) * 100 / Decimal(total)).quantize(Decimal("0.01")))

        values, other = [], None
        for is_other, value, n, net, neg, rank, groups in res:
            e = {"rows": n or 0, "net": self.dec(net), "negative_rows": neg or 0, "pct_net": pct(net, tnet), "pct_rows": pct(n, tn)}
            if is_other:
                other = {**e, "distinct_values": groups}
            else:
                values.append({**e, "value": value if not isinstance(value, Decimal) else self.dec(value),
                               "blank": value is None or value == "", "rank": rank})
        return {"column": st.gb, "kind": self.kinds[st.gb], "order": st.gb_order, "top": GROUPBY_TOP, "values": values,
                "other": other, "distinct_values": len(values) + (other["distinct_values"] if other else 0),
                "filtered_rows": tn, "filtered_net": tot["net"], "sql": self.display_sql(sql, params + [GROUPBY_TOP, GROUPBY_TOP]),
                "ms": ms}

    @lru_cache(maxsize=512)
    def values(self, column: str) -> dict:
        self.column(column)
        if self.kinds[column] != "text":
            return {"column": column, "dropdown": False, "kind": self.kinds[column]}
        res, ms, _ = self._run(f"SELECT COUNT(DISTINCT a.{q(column)}) FROM a", [])
        if res[0][0] > DROPDOWN_MAX_DISTINCT:
            return {"column": column, "dropdown": False, "kind": "text", "distinct": res[0][0], "cutoff": DROPDOWN_MAX_DISTINCT}
        res, ms2, _ = self._run(f"SELECT a.{q(column)}, COUNT(*) FROM a GROUP BY 1 ORDER BY 2 DESC, 1", [])
        return {"column": column, "dropdown": True, "kind": "text", "distinct": len(res), "cutoff": DROPDOWN_MAX_DISTINCT,
                "options": [{"value": v, "rows": int(n), "blank": v == ""} for v, n in res], "ms": round(ms + ms2, 1)}

    def row_detail(self, fy: str, m: str, r: str) -> dict:
        fy_ = self._int(fy, None, config.FIRST_FY, config.LAST_FY, "y")
        m_ = self._int(m, None, 1, 32767, "m")
        r_ = self._int(r, None, 1, 10_000_000_000, "r")
        sql = "SELECT * FROM a WHERE fiscal_year = ? AND _source_member_idx = ? AND _source_row = ?"
        res, ms, cols = self._run(sql, [fy_, m_, r_])
        if len(res) != 1:
            raise BadRequest(f"expected one row for FY{fy_} member {m_} row {r_}, found {len(res)}")
        rec = dict(zip(cols, res[0]))
        flags, _, _ = self._run("SELECT flag_id FROM flags WHERE k = ? AND fy = ? ORDER BY 1", [rec[KEY], fy_])
        return {"fields": [[c, rec[c]] for c in self.columns + ["_source_file", "_source_member_idx", "_source_row"]],
                "key": rec[KEY], "award_key": rec[AWARD_KEY], "flags": [f[0] for f in flags],
                "sql": self.display_sql(sql, [fy_, m_, r_]), "ms": ms}

    def export_rows(self, st: State):
        sql, params = self.rows_sql(st, EXPORT_CAP, 0)
        cur = self.con.cursor()
        try:
            res = cur.execute(sql, params)
            yield list(st.cols)
            while chunk := res.fetchmany(10_000):
                for r in chunk:
                    yield [self.dec(v) if self.kinds[c] == "decimal" and v is not None else v for c, v in zip(st.cols, r[4:])]
        finally:
            cur.close()

    def meta(self) -> dict:
        return {"columns": [{"name": c, "position": i, "kind": self.kinds[c]} for i, c in enumerate(self.columns)],
                "default_cols": DEFAULT_COLS, "default_sort": "action_date", "default_dir": "desc",
                "page_size": DEFAULT_PAGE_SIZE, "export_cap": EXPORT_CAP, "groupby_top": GROUPBY_TOP,
                "years": self.years, "view_sql": self.view_sql}
