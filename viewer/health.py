"""Data-health dashboard: read-only queries over the Stage 2 summaries, plus the decision log.

Everything here reads data/integrity/ (rebuildable from Stage 1), reports/integrity/ and config/. The only
file it ever writes is config/decisions.csv (decisions, never data). Same safety rules as the row viewer:
every value from the browser is validated against a known list and passed to DuckDB as a bound parameter;
column names are checked against the real header before they reach SQL; money stays an exact decimal string.
"""

from __future__ import annotations

import csv
import json
import os
import re
import tempfile
import threading
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import duckdb

from src import config, stage1, stage2

DECISIONS = config.OUTPUT_ROOT / "config" / "decisions.csv"   # = repo config/ normally; a temp folder in tests
DECISION_FIELDS = ["decision_id", "target_type", "target", "scope", "status", "rationale", "decided_by", "decided_date",
                   "created_utc", "updated_utc"]
STATUSES = ["proposed", "keep as is", "clean (rule)", "exclude from analysis (with ledger)", "investigate"]
TARGET_TYPES = ["flag", "column", "value pattern"]
GLOBAL_DIMS = ["agency", "subagency", "award_type", "psc_cat"]
METRICS = {"blank": "blank", "zero": "zero", "placeholder": "placeholder"}
MAX_TEXT = 2000


class BadRequest(ValueError):
    pass


class NoData(FileNotFoundError):
    """Stages 1 and 2 have not been built on this machine. The message is meant to be printed as it is."""


def no_data_message(missing: list[Path]) -> str:
    shown = ", ".join(os.path.relpath(p, config.OUTPUT_ROOT) for p in missing[:3])
    more = f" and {len(missing) - 3} more" if len(missing) > 3 else ""
    return ("The dashboard needs Stages 1 and 2 built on this machine, and their outputs are missing "
            f"({shown}{more}). Build them with python -m src.stages refresh after placing the yearly zips "
            "with python -m src.stage0 organize (README, Getting the data).")


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def lit_list(paths: list[Path]) -> str:
    return "[" + ", ".join("'" + str(p).replace("'", "''") + "'" for p in paths) + "]"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class HealthDB:
    def __init__(self):
        self.years = stage2.present_years()
        self.pending = config.years_pending()
        self.all_years = config.years_in_scope()
        self.con = duckdb.connect(":memory:")
        self.con.execute(f"SET temp_directory = '{Path(tempfile.gettempdir()) / 'fy_dashboard_duckdb'}'")
        self.con.execute("SET autoinstall_known_extensions = false")
        self.con.execute("SET autoload_known_extensions = false")
        self.con.execute("SET enable_progress_bar = false")
        self.lock = threading.Lock()
        yd = [stage2.year_dir(fy) for fy in self.years]
        views = {
            "cube_months": [d / "cube_months.parquet" for d in yd],
            "cube_columns": [d / "cube_columns.parquet" for d in yd],
            "column_profile": [d / "column_profile.parquet" for d in yd],
            "top_values": [d / "top_values.parquet" for d in yd],
            "placeholder_values": [d / "placeholder_values.parquet" for d in yd],
            "agencies": [d / "agencies.parquet" for d in yd],
            "subagencies": [d / "subagencies.parquet" for d in yd],
            "year_totals": [d / "year_totals.parquet" for d in yd],
            "coverage": [d / "coverage.parquet" for d in yd],
            "reporting_lag": [d / "reporting_lag.parquet" for d in yd],
            "cube_flags": [config.INTEGRITY_DIR / "summary" / "cube_flags.parquet"],
            "agency_year_flags": [stage2.CROSS / "agency_year_flags.parquet"],
            "subagency_year_flags": [stage2.CROSS / "subagency_year_flags.parquet"],
            "months_flags": [stage2.CROSS / "months.parquet"],
            "parent_test": [stage2.CROSS / "parent_test_raytheon.parquet"],
        }
        optional = {"parent_test"}                      # only exists once FY2018-FY2022 are profiled
        views = {k: v for k, v in views.items() if k not in optional or all(p.exists() for p in v)}
        missing = [p for ps in views.values() for p in ps if not p.exists()]
        if not self.years:
            missing.insert(0, stage2.year_dir(config.LAST_FY) / "_done.json")
        if missing:
            raise NoData(no_data_message(missing))
        for name, paths in views.items():
            self.con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet({lit_list(paths)})")
        self.catalog = stage2.catalog()
        self.flag_ids = {f["flag_id"] for f in self.catalog}
        self.header = json.loads((config.layer_a_dir(self.years[0]) / "_files.json").read_text())["columns"]
        self.guide = self._guide()
        self.dim_values = {d: {r[0] for r in self.con.execute(f"SELECT DISTINCT {d} FROM cube_months").fetchall()}
                           for d in GLOBAL_DIMS}
        self.reports = config.INTEGRITY_REPORTS_DIR

    # ------------------------------------------------------------------ helpers

    def _guide(self) -> dict:
        p = config.REPO_ROOT / "tools" / "column_guide" / "colguide.json"
        out = {}
        if p.exists():
            for grp in json.loads(p.read_text(encoding="utf-8")):
                for c in grp["cols"]:
                    out[c["col"]] = {"group": grp["name"], "meaning": c.get("meaning", ""), "verdict": c.get("verdict", ""),
                                     "why": c.get("why", "")}
        return out

    def _run(self, sql: str, params: list | None = None) -> list[tuple]:
        with self.lock:
            return self.con.execute(sql, params or []).fetchall()

    def parse_global(self, raw: str | None) -> dict:
        """g = {"fy": [lo, hi], "agency": [...], "subagency": [...], "award_type": [...], "psc_cat": [...]}"""
        try:
            g = json.loads(raw) if raw else {}
        except json.JSONDecodeError as e:
            raise BadRequest(f"g is not valid JSON: {e}") from None
        if not isinstance(g, dict) or set(g) - {"fy", *GLOBAL_DIMS}:
            raise BadRequest("g has unknown keys")
        lo, hi = g.get("fy") or [config.FIRST_FY, config.LAST_FY]
        if not (isinstance(lo, int) and isinstance(hi, int) and config.FIRST_FY <= lo <= hi <= config.LAST_FY):
            raise BadRequest("fy must be [lo, hi] within the years in scope")
        out = {"fy": [lo, hi]}
        for d in GLOBAL_DIMS:
            vals = g.get(d) or []
            if not isinstance(vals, list) or len(vals) > 200 or not all(isinstance(v, str) for v in vals):
                raise BadRequest(f"{d} must be a list of strings")
            unknown = [v for v in vals if v not in self.dim_values[d]]
            if unknown:
                raise BadRequest(f"unknown {d} value(s): {unknown[:5]}")
            out[d] = vals
        return out

    def where(self, g: dict, alias: str = "") -> tuple[str, list]:
        p = alias + "." if alias else ""
        clauses, params = [f"{p}fiscal_year BETWEEN ? AND ?"], [g["fy"][0], g["fy"][1]]
        for d in GLOBAL_DIMS:
            if g.get(d):
                clauses.append(f"{p}{d} IN (SELECT unnest(?))")
                params.append(g[d])
        return " AND ".join(clauses), params

    @staticmethod
    def filtered(g: dict) -> bool:
        return any(g.get(d) for d in GLOBAL_DIMS)

    def _years_in(self, g: dict) -> list[int]:
        return [fy for fy in self.all_years if g["fy"][0] <= fy <= g["fy"][1]]

    # ------------------------------------------------------------------ meta

    def meta(self) -> dict:
        ag = self._run("SELECT code, arg_max(name, fiscal_year) FROM agencies GROUP BY code ORDER BY 2")
        sub = self._run("""SELECT code, arg_max(name, fiscal_year), arg_max(agency_code, fiscal_year) FROM subagencies
                           GROUP BY code ORDER BY 2""")
        at = self._run("SELECT award_type, SUM(rows) FROM cube_months GROUP BY 1 ORDER BY 2 DESC")
        pc = self._run("SELECT psc_cat, SUM(rows) FROM cube_months GROUP BY 1 ORDER BY 1")
        return {"years_in_scope": self.all_years, "years_present": self.years, "years_pending": self.pending,
                "release": config.RELEASE_DATE, "first_fy": config.FIRST_FY, "last_fy": config.LAST_FY,
                "agencies": [{"value": c, "label": n} for c, n in ag],
                "subagencies": [{"value": c, "label": n, "agency": a} for c, n, a in sub],
                "award_types": [{"value": v, "rows": n} for v, n in at],
                "psc_cats": [{"value": v, "rows": n} for v, n in pc],
                "catalog": self.catalog, "statuses": STATUSES, "target_types": TARGET_TYPES,
                "columns": [{"name": c, "position": i + 1, **self.guide.get(c, {})} for i, c in enumerate(self.header)]}

    # ------------------------------------------------------------------ overview

    def overview(self, g: dict) -> dict:
        w, p = self.where(g)
        tot = {fy: (n, net) for fy, n, net in self._run(
            f"SELECT fiscal_year, SUM(rows), SUM(net) FROM cube_months WHERE {w} GROUP BY 1", p)}
        sev = {f["flag_id"]: f["severity"] for f in self.catalog}
        fl: dict[int, dict] = {}
        for fid, fy, n in self._run(f"SELECT flag_id, fiscal_year, SUM(rows) FROM cube_flags WHERE {w} GROUP BY 1, 2", p):
            fl.setdefault(fy, {"serious": 0, "review": 0, "info": 0})[sev[fid]] += int(n)
        comp = self._completeness_rows()
        cards = []
        for fy in self._years_in(g):
            prog = stage1.load_progress(fy) if fy in self.years else {}
            bm = [r for r in comp if int(r["fiscal_year"]) == fy and not r["agency"]]
            if fy in self.pending:
                cards.append({"fiscal_year": fy, "status": "pending", "note": "not yet downloaded",
                              "benchmarks": [{"id": r["benchmark_id"], "status": r["status"], "url": r["url"]} for r in bm]})
                continue
            if fy not in self.years:
                cards.append({"fiscal_year": fy, "status": "not profiled", "note": "in Stage 0 but not yet profiled (run python -m src.stages refresh)",
                              "benchmarks": [{"id": r["benchmark_id"], "status": r["status"], "url": r["url"]} for r in bm]})
                continue
            n, net = tot.get(fy, (0, Decimal(0)))
            cards.append({"fiscal_year": fy, "status": "present", "rows": n, "net": self.dec(net),
                          "release": prog.get("zip", "").split("_")[-1][:8], "proof": prog.get("status"),
                          "benchmarks": [{"id": r["benchmark_id"], "status": r["status"], "gap_pct": r.get("gap_pct"),
                                          "url": r["url"]} for r in bm],
                          "flags": fl.get(fy, {"serious": 0, "review": 0, "info": 0})})
        top = self._run(f"""SELECT flag_id, SUM(rows) AS n, SUM(gross) AS gross, COUNT(DISTINCT fiscal_year) AS yrs
                            FROM cube_flags WHERE {w} GROUP BY 1""", p)
        cat = {f["flag_id"]: f for f in self.catalog}
        rank = {"serious": 0, "review": 1, "info": 2}
        findings = sorted(({"flag_id": fid, "name": cat[fid]["name"], "severity": cat[fid]["severity"], "rows": int(n),
                            "gross": self.dec(gross), "years": yrs, "why": cat[fid]["why_it_matters"]}
                           for fid, n, gross, yrs in top if n),
                          key=lambda f: (rank[f["severity"]], -Decimal(f["gross"] or 0), -f["rows"]))
        return {"cards": cards, "findings": findings[:15], "filtered": self.filtered(g),
                "summary_md": self._read_report("integrity_summary.md")}

    @staticmethod
    def dec(x) -> str | None:
        if x is None:
            return None
        x = Decimal(x)
        c = x.quantize(Decimal("0.01"))
        return str(c if c == x else x)

    def _read_report(self, name: str) -> str:
        p = self.reports / name
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def _completeness_rows(self) -> list[dict]:
        p = self.reports / "completeness_check.csv"
        return list(csv.DictReader(open(p, encoding="utf-8"))) if p.exists() else []

    # ------------------------------------------------------------------ completeness

    def completeness(self, g: dict) -> dict:
        w, p = self.where(g)
        months = self._run(f"""SELECT fiscal_year, month, SUM(rows), SUM(net) FROM cube_months WHERE {w}
                               GROUP BY 1, 2 ORDER BY 1, 2""", p)
        thin = {(fy, m): (r, d) for fy, m, r, d in self._run(
            "SELECT fiscal_year, month, h01_thin_rows, h02_thin_dollars FROM months_flags")}
        ag = self._run(f"""SELECT agency, fiscal_year, SUM(rows), SUM(net) FROM cube_months WHERE {w}
                           GROUP BY 1, 2 ORDER BY 1, 2""", p)
        names = dict(self._run("SELECT code, arg_max(name, fiscal_year) FROM agencies GROUP BY code"))
        aflags = self._run("SELECT code, fiscal_year, flag_id, detail FROM agency_year_flags")
        yrs = self._years_in(g)
        return {"benchmarks": [r for r in self._completeness_rows() if int(r["fiscal_year"]) in yrs],
                "benchmark_md": self._read_report("completeness_check.md"),
                "months": [{"fiscal_year": fy, "month": m, "rows": int(n), "net": self.dec(net),
                            "thin_rows": bool(thin.get((fy, m), (False, False))[0]) and not self.filtered(g),
                            "thin_dollars": bool(thin.get((fy, m), (False, False))[1]) and not self.filtered(g)}
                           for fy, m, n, net in months],
                "agency_matrix": [{"agency": a, "name": names.get(a, ""), "fiscal_year": fy, "rows": int(n),
                                   "net": self.dec(net)} for a, fy, n, net in ag],
                "agency_flags": [{"agency": a, "fiscal_year": fy, "flag_id": f, "detail": d} for a, fy, f, d in aflags],
                "years": yrs, "pending": [fy for fy in self.pending if fy in yrs], "filtered": self.filtered(g)}

    # ------------------------------------------------------------------ column quality

    def columns(self, g: dict, metric: str) -> dict:
        if metric not in METRICS:
            raise BadRequest("metric must be blank, zero or placeholder")
        w, p = self.where(g)
        res = self._run(f"""SELECT column_name, fiscal_year, SUM(rows), SUM({METRICS[metric]}) FROM cube_columns WHERE {w}
                            GROUP BY 1, 2""", p)
        cells = {}
        for col, fy, n, m in res:
            cells.setdefault(col, {})[fy] = {"rows": int(n), "count": int(m)}
        return {"metric": metric, "years": self._years_in(g), "pending": self.pending,
                "columns": [{"name": c, "position": i + 1, "verdict": self.guide.get(c, {}).get("verdict", ""),
                             "group": self.guide.get(c, {}).get("group", ""), "cells": cells.get(c, {})}
                            for i, c in enumerate(self.header)]}

    def column_detail(self, name: str, fy: int | None) -> dict:
        if name not in self.header:
            raise BadRequest(f"unknown column {name!r}")
        prof = self._run("""SELECT fiscal_year, rows, blank, zero, placeholder, distinct_nonblank, min_value, max_value,
                            lead_trail_space, case_variant_values, max_length FROM column_profile WHERE column_name = ?
                            ORDER BY fiscal_year""", [name])
        tops = self._run("""SELECT fiscal_year, rank, value, n FROM top_values WHERE column_name = ? AND (? IS NULL OR fiscal_year = ?)
                            ORDER BY fiscal_year, rank""", [name, fy, fy])
        phs = self._run("""SELECT fiscal_year, value, n FROM placeholder_values WHERE column_name = ? AND (? IS NULL OR fiscal_year = ?)
                           ORDER BY fiscal_year, n DESC""", [name, fy, fy])
        keys = ["fiscal_year", "rows", "blank", "zero", "placeholder", "distinct_nonblank", "min_value", "max_value",
                "lead_trail_space", "case_variant_values", "max_length"]
        return {"column": name, "guide": self.guide.get(name, {}), "profile": [dict(zip(keys, r)) for r in prof],
                "top_values": [{"fiscal_year": a, "rank": b, "value": v, "n": n} for a, b, v, n in tops],
                "placeholders": [{"fiscal_year": a, "value": v, "n": n} for a, v, n in phs]}

    # ------------------------------------------------------------------ flags

    def flags(self, g: dict) -> dict:
        w, p = self.where(g)
        row = self._run(f"""SELECT flag_id, fiscal_year, SUM(rows), SUM(net), SUM(gross) FROM cube_flags WHERE {w}
                            GROUP BY 1, 2""", p)
        counts = {}
        for fid, fy, n, net, gross in row:
            counts.setdefault(fid, {})[fy] = {"count": int(n), "net": self.dec(net), "gross": self.dec(gross)}
        fc = self.reports / "flag_counts.csv"
        other = {}
        if fc.exists():
            for r in csv.DictReader(open(fc, encoding="utf-8")):
                if r["level"] != "row" and r["count"] not in ("", None):
                    other.setdefault(r["flag_id"], {})[int(r["fiscal_year"])] = {"count": int(r["count"]),
                                                                                  "unit": r["count_unit"]}
        out = []
        for f in self.catalog:
            by = counts.get(f["flag_id"], {}) if f["level"] == "row" else other.get(f["flag_id"], {})
            out.append({**f, "by_year": {str(k): v for k, v in by.items()},
                        "total": sum(v["count"] for k, v in by.items() if g["fy"][0] <= int(k) <= g["fy"][1]),
                        "filter_applies": f["level"] == "row"})
        return {"flags": out, "years": self._years_in(g), "pending": self.pending, "filtered": self.filtered(g)}

    # ------------------------------------------------------------------ glossary (read-only)

    def glossary(self, q: str = "", category: str = "") -> dict:
        """Terms from config/glossary.csv. q searches term, also_called and plain_summary (case-insensitive)."""
        if category and category not in config.GLOSSARY_CATEGORIES:
            raise BadRequest(f"unknown category: {category[:60]!r}")
        if len(q) > 200:
            raise BadRequest("search text too long")
        terms = list(csv.DictReader(open(config.GLOSSARY_CSV, encoding="utf-8"))) if config.GLOSSARY_CSV.exists() else []
        sources = ({r["source_id"]: r for r in csv.DictReader(open(config.GOV_SOURCES_CSV, encoding="utf-8"))}
                   if config.GOV_SOURCES_CSV.exists() else {})
        needle = q.strip().lower()
        out = []
        for t in terms:
            if category and t["category"] != category:
                continue
            if needle and needle not in " ".join((t["term"], t["also_called"], t["plain_summary"])).lower():
                continue
            src = sources.get(t["source_id"], {})
            out.append({**t, "source_title": src.get("title", ""), "source_publisher": src.get("publisher", ""),
                        "source_url": src.get("url", "")})
        out.sort(key=lambda t: t["term"].lower())
        return {"terms": out, "total": len(terms), "categories": config.GLOSSARY_CATEGORIES,
                "counts": {c: sum(t["category"] == c for t in terms) for c in config.GLOSSARY_CATEGORIES}}

    # ------------------------------------------------------------------ decisions (the only write)

    def decisions(self) -> list[dict]:
        if not DECISIONS.exists():
            return []
        return list(csv.DictReader(open(DECISIONS, encoding="utf-8")))

    def save_decision(self, body: dict) -> dict:
        if not isinstance(body, dict):
            raise BadRequest("body must be a JSON object")
        d = {k: body.get(k, "") for k in DECISION_FIELDS}
        for k, v in d.items():
            if not isinstance(v, str) or len(v) > MAX_TEXT:
                raise BadRequest(f"{k} must be text up to {MAX_TEXT} characters")
            if any(ch in v for ch in "\r\x00"):
                raise BadRequest(f"{k} contains a control character")
        if d["status"] not in STATUSES:
            raise BadRequest(f"status must be one of {STATUSES}")
        if d["target_type"] not in TARGET_TYPES:
            raise BadRequest(f"target_type must be one of {TARGET_TYPES}")
        if d["target_type"] == "flag" and d["target"] not in self.flag_ids:
            raise BadRequest("unknown flag")
        if d["target_type"] == "column" and d["target"] not in self.header:
            raise BadRequest("unknown column")
        if not d["target"].strip():
            raise BadRequest("target is required")
        if not d["decided_by"].strip():
            raise BadRequest("decided by is required")
        if d["decided_date"] and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d["decided_date"]):
            raise BadRequest("decided date must be YYYY-MM-DD")
        d["decided_date"] = d["decided_date"] or date.today().isoformat()
        with self.lock:
            rows = self.decisions()
            existing = next((r for r in rows if d["decision_id"] and r["decision_id"] == d["decision_id"]), None)
            if existing:
                d["created_utc"] = existing["created_utc"]
                d["updated_utc"] = now()
                rows = [d if r is existing else r for r in rows]
            else:
                nums = [int(m[1]) for r in rows if (m := re.fullmatch(r"D(\d+)", r["decision_id"]))]
                d["decision_id"] = f"D{(max(nums) + 1) if nums else 1:04d}"
                d["created_utc"] = d["updated_utc"] = now()
                rows.append(d)
            write_decisions(rows)
        return d


def write_decisions(rows: list[dict]) -> None:
    DECISIONS.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=DECISIONS.parent, prefix=".decisions.", suffix=".csv")
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=DECISION_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in DECISION_FIELDS})
    os.replace(tmp, DECISIONS)


def prefill_decisions(log=print) -> int:
    """One 'proposed' decision per serious or review flag that fired (nothing gets forgotten). Never overwrites."""
    rows = list(csv.DictReader(open(DECISIONS, encoding="utf-8"))) if DECISIONS.exists() else []
    have = {(r["target_type"], r["target"]) for r in rows}
    fc = config.INTEGRITY_REPORTS_DIR / "flag_counts.csv"
    totals: dict[str, int] = {}
    for r in csv.DictReader(open(fc, encoding="utf-8")):
        if r["count"] not in ("", None):
            totals[r["flag_id"]] = totals.get(r["flag_id"], 0) + int(r["count"])
    added = 0
    nums = [int(m[1]) for r in rows if (m := re.fullmatch(r"D(\d+)", r["decision_id"]))]
    nxt = (max(nums) + 1) if nums else 1
    for f in stage2.catalog():
        if f["severity"] not in ("serious", "review") or not totals.get(f["flag_id"]) or ("flag", f["flag_id"]) in have:
            continue
        rows.append({"decision_id": f"D{nxt:04d}", "target_type": "flag", "target": f["flag_id"],
                     "scope": f"FY{config.FIRST_FY}-FY{config.LAST_FY} (present years)", "status": "proposed",
                     "rationale": f"Auto-filled so nothing is forgotten: {f['name']} fired on {totals[f['flag_id']]:,} "
                                  f"{'rows' if f['level'] == 'row' else 'items'}. Team to decide.",
                     "decided_by": "(not yet decided)", "decided_date": "", "created_utc": now(), "updated_utc": now()})
        nxt += 1
        added += 1
    write_decisions(rows)
    log(f"decisions: {added} proposed entries added ({len(rows)} total) -> {DECISIONS}")
    return added
