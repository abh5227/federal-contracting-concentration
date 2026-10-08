"""Summaries of Stage 2 for people: reports/integrity/ (committed) and data/integrity/summary/ (for the dashboard).

    python -m src.integrity_report

Reads only Stage 1 proofs, Stage 2 outputs, config/flag_catalog.csv and config/benchmarks.csv. Writes:
  reports/integrity/integrity_summary.md      plain-language verdict, then the biggest findings first
  reports/integrity/completeness_check.md/.csv our totals vs published figures (thresholds fixed in the catalog)
  reports/integrity/column_quality.csv        column x year: blank, zero, placeholder shares and more
  reports/integrity/flag_counts.csv           flag x year: rows (or items) and dollars
  reports/integrity/outliers.csv              J01 and J02 rows with context and award net (full J01-J04 list:
                                              data/integrity/summary/outliers_all.parquet, not committed)
  data/integrity/summary/cube_flags.parquet   flag x year x global-filter dimensions (dashboard)
Nothing in Stage 0 or Stage 1 is read for writing, and no value is changed.
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import duckdb

from . import config, stage1, stage2
from .convert import parquet_list_sql, q

REP = config.INTEGRITY_REPORTS_DIR
SUMMARY = config.INTEGRITY_DIR / "summary"
BENCHMARKS = config.REPO_ROOT / "config" / "benchmarks.csv"
PASS_GAP, WARN_GAP = Decimal("0.02"), Decimal("0.10")      # flag catalog I01/I02 (= the pilot's GAO thresholds)
SEV_ORDER = {"serious": 0, "review": 1, "info": 2}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def money(x) -> str:
    if x is None or x == "":
        return ""
    x = Decimal(x)
    return f"-${-x:,.2f}" if x < 0 else f"${x:,.2f}"


def dec(x) -> str:
    """Exact decimal as text, shown to the cent when that loses nothing (sums are DECIMAL(38,6))."""
    if x is None or x == "":
        return ""
    x = Decimal(x)
    c = x.quantize(Decimal("0.01"))
    return str(c if c == x else x)


def pct(x) -> str:
    return "" if x is None else f"{Decimal(x) * 100:.2f}%"


def years() -> list[int]:
    return stage2.present_years()


def con() -> duckdb.DuckDBPyConnection:
    c = duckdb.connect()
    c.execute("SET TimeZone = 'UTC'")
    c.execute(f"SET temp_directory = '{config.SCRATCH_DIR / 'duckdb_report'}'")
    c.execute("SET memory_limit = '6GB'")
    return c


def all_of(name: str) -> str:
    return parquet_list_sql([stage2.year_dir(fy) / f"{name}.parquet" for fy in years()])


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


# ------------------------------------------------------------------------------------------- year totals


def year_table(c) -> list[dict]:
    """One row per in-scope fiscal year; FY2015 shows as pending, never as a gap."""
    tot = {r[0]: r for r in c.execute(f"SELECT * FROM read_parquet({all_of('year_totals')})").fetchall()}
    cols = [d[0] for d in c.execute(f"SELECT * FROM read_parquet({all_of('year_totals')}) LIMIT 0").description]
    out = []
    for fy in config.years_in_scope():
        prog = stage1.load_progress(fy)
        if fy in config.years_pending():
            out.append({"fiscal_year": fy, "status": "pending - not yet downloaded"})
            continue
        if fy not in tot:
            out.append({"fiscal_year": fy, "status": "not yet profiled (Stage 2 has not run for this year)"})
            continue
        r = dict(zip(cols, tot[fy]))
        members = list(prog.get("members", {}).values())
        out.append({"fiscal_year": fy, "status": "present", "zip": prog.get("zip"), "zip_sha256": prog.get("zip_sha256"),
                    "release": config.RELEASE_DATE, "stage1_proof": prog.get("status"),
                    "proof_rows": sum(m["raw_records"] for m in members),
                    "proof_dollars": dec(sum(Decimal(m["raw_dollars"]) for m in members)),
                    **{k: (dec(v) if k in ("net", "idv_net", "positive_only") else v) for k, v in r.items()}})
    return out


# ------------------------------------------------------------------------------------------- flags


def flag_counts(c, cat: list[dict]) -> list[dict]:
    """Row-level flags: rows and dollars (each flagged transaction row counted once per flag).
    Other levels: items (codes, entities, agency-years, months) from the cross-year tables."""
    SUMMARY.mkdir(parents=True, exist_ok=True)
    parts = []
    for fy in years():
        rf = config.INTEGRITY_DIR / "row_flags" / f"fy{fy}.parquet"
        kd = stage2.year_dir(fy) / "keys_dims.parquet"
        parts.append(f"""SELECT f.flag_id, k.* FROM (SELECT DISTINCT contract_transaction_unique_key AS key, flag_id
                         FROM read_parquet('{rf}')) f JOIN read_parquet('{kd}') k ON k.contract_transaction_unique_key = f.key""")
    c.execute(f"""COPY (SELECT flag_id, fiscal_year, agency, subagency, award_type, psc_cat, COUNT(*) AS rows,
                  SUM(amt) AS net, SUM(abs(amt)) AS gross FROM ({' UNION ALL '.join(parts)}) GROUP BY ALL)
                  TO '{SUMMARY / "cube_flags.parquet"}' (FORMAT parquet)""")
    row_level = {(f, fy): (n, net, gross) for f, fy, n, net, gross in c.execute(
        f"SELECT flag_id, fiscal_year, SUM(rows), SUM(net), SUM(gross) FROM read_parquet('{SUMMARY / 'cube_flags.parquet'}') GROUP BY ALL").fetchall()}
    cross = stage2.CROSS
    items: dict[tuple[str, int], int] = {}

    def add_items(sql: str) -> None:
        for fid, fy, n in c.execute(sql).fetchall():
            items[(fid, fy)] = items.get((fid, fy), 0) + n

    add_items(f"SELECT flag_id, fiscal_year, COUNT(*) FROM read_parquet('{cross / 'agency_year_flags.parquet'}') GROUP BY ALL")
    add_items(f"SELECT flag_id, fiscal_year, COUNT(*) FROM read_parquet('{cross / 'subagency_year_flags.parquet'}') GROUP BY ALL")
    add_items(f"SELECT 'H01', fiscal_year, COUNT(*) FILTER (WHERE h01_thin_rows) FROM read_parquet('{cross / 'months.parquet'}') GROUP BY 2")
    add_items(f"SELECT 'H02', fiscal_year, COUNT(*) FILTER (WHERE h02_thin_dollars) FROM read_parquet('{cross / 'months.parquet'}') GROUP BY 2")
    add_items(f"SELECT 'F07', fiscal_year, COUNT(*) FROM read_parquet('{cross / 'multi_label_codes.parquet'}') GROUP BY 2")
    add_items(f"""SELECT 'G04', fiscal_year, COUNT(*) FILTER (WHERE id_column = 'recipient_uei') FROM read_parquet({all_of('many_names')}) GROUP BY 2""")
    add_items(f"""SELECT 'G05', fiscal_year, COUNT(*) FILTER (WHERE id_column = 'recipient_parent_uei') FROM read_parquet({all_of('many_names')}) GROUP BY 2""")
    add_items(f"""SELECT 'B05', fiscal_year, awards_also_in_other_years FROM read_parquet('{cross / 'awards_multi_year_by_year.parquet'}')""")
    f08 = c.execute(f"SELECT COUNT(*) FROM read_parquet('{cross / 'label_changes.parquet'}')").fetchone()[0]
    dual = cross / "dual_code_agencies.parquet"
    f10 = c.execute(f"SELECT COUNT(DISTINCT (code_column, name)) FROM read_parquet('{dual}')").fetchone()[0] if dual.exists() else 0
    proofs = {fy: stage1.load_progress(fy) for fy in years()}
    out = []
    for f in cat:
        for fy in config.years_in_scope():
            row = {**{k: f[k] for k in ("flag_id", "name", "severity", "level", "section")}, "fiscal_year": fy}
            if fy in config.years_pending():
                row.update({"count": "", "count_unit": "", "note": "pending - FY2015 not yet downloaded"})
                out.append(row)
                continue
            if fy not in proofs:
                row.update({"count": "", "count_unit": "", "note": "not yet profiled"})
                out.append(row)
                continue
            fid = f["flag_id"]
            if f["level"] == "row":
                n, net, gross = row_level.get((fid, fy), (0, Decimal(0), Decimal(0)))
                row.update({"count": n, "count_unit": "rows", "net_dollars": dec(net or 0), "gross_dollars": dec(gross or 0)})
            elif fid in ("A01", "A02", "A03", "A04", "A05"):
                ms = list(proofs[fy]["members"].values())
                val = {"A01": int(proofs[fy]["zip"].split("_")[-1][:8] != config.RELEASE_DATE),
                       "A02": 0, "A03": 0,
                       "A04": sum(m.get("wrong_field_count", 0) + m.get("csv_errors", 0) for m in ms),
                       "A05": sum(m.get("blank_lines", 0) for m in ms)}[fid]
                row.update({"count": val, "count_unit": {"A04": "records", "A05": "blank lines"}.get(fid, "files")})
            elif fid == "F08":
                row.update({"count": f08 if fy == years()[-1] else "", "count_unit": "codes (all years)",
                            "note": "cross-year: counted once, on the latest year" if fy == years()[-1] else ""})
            elif fid == "F10":
                row.update({"count": f10 if fy == years()[-1] else "", "count_unit": "agencies (all years)",
                            "note": "cross-year: counted once, on the latest year" if fy == years()[-1] else ""})
            elif fid.startswith("I"):
                row.update({"count": "", "count_unit": "see completeness_check.csv"})
            elif fid in ("E03", "E04", "E05", "H09"):
                row.update({"count": "", "count_unit": "profile (see column_quality.csv)"})
            else:
                row.update({"count": items.get((fid, fy), 0), "count_unit": {"agency_year": "agency-years",
                            "subagency_year": "sub-agency-years", "year_month": "months", "code": "codes",
                            "entity": "IDs", "award": "awards"}.get(f["level"], "items")})
            if f.get("fy2015_handling") and config.years_pending():
                row["note"] = (row.get("note", "") + " " + f["fy2015_handling"]).strip()
            out.append(row)
    write_csv(REP / "flag_counts.csv", out, ["flag_id", "name", "severity", "level", "section", "fiscal_year", "count",
                                             "count_unit", "net_dollars", "gross_dollars", "note"])
    return out


# ------------------------------------------------------------------------------------------- columns


def column_quality(c) -> list[dict]:
    guide = {}
    gpath = config.REPO_ROOT / "tools" / "column_guide" / "colguide.json"
    if gpath.exists():
        for grp in json.loads(gpath.read_text(encoding="utf-8")):
            for col in grp["cols"]:
                guide[col["col"]] = {"group": grp["name"], "verdict": col["verdict"]}
    rows = c.execute(f"""SELECT fiscal_year, position, column_name, rows, blank, zero, placeholder, distinct_nonblank,
                         lead_trail_space, case_variant_values, min_value, max_value, max_length
                         FROM read_parquet({all_of('column_profile')}) ORDER BY position, fiscal_year""").fetchall()
    out = []
    for fy, pos, col, n, b, z, p, d, ws, cv, mn, mx, ml in rows:
        g = guide.get(col, {})
        out.append({"column": col, "position": pos, "fiscal_year": fy, "rows": n,
                    "pct_blank": f"{100 * b / n:.4f}" if n else "", "pct_zero": f"{100 * z / n:.4f}" if n else "",
                    "pct_placeholder": f"{100 * p / n:.4f}" if n else "", "distinct_nonblank": d,
                    "values_with_lead_trail_space": ws, "case_variant_values": cv, "max_length": ml,
                    "min_value": (mn or "")[:60], "max_value": (mx or "")[:60],
                    "guide_verdict": g.get("verdict", ""), "guide_group": g.get("group", "")})
    write_csv(REP / "column_quality.csv", out, list(out[0]))
    return out


OUTLIER_CONTEXT = ["action_date", "awarding_agency_name", "awarding_sub_agency_name", "recipient_name",
                   "product_or_service_code", "contract_award_unique_key", "modification_number"]


def outliers(c) -> list[dict]:
    """Every J01-J04 row (millions: J03 alone is millions) goes to data/integrity/summary/outliers_all.parquet, which is
    rebuildable and never committed. reports/integrity/outliers.csv holds the review lists J01 and J02 in full, with
    context from Stage 1 and what each row's award nets to across all present years: a huge amount reversed by
    another row nets to almost nothing there. No outlier is removed from the data."""
    SUMMARY.mkdir(parents=True, exist_ok=True)
    amt = "TRY_CAST(federal_action_obligation AS DECIMAL(38,6))"
    c.execute(f"""COPY (SELECT fiscal_year, flag_id, contract_transaction_unique_key, federal_action_obligation
                  FROM read_parquet({all_of('outliers')}) ORDER BY fiscal_year, flag_id, abs({amt}) DESC,
                  contract_transaction_unique_key)
                  TO '{SUMMARY / "outliers_all.parquet"}' (FORMAT parquet, COMPRESSION zstd)""")
    c.execute(f"""CREATE OR REPLACE TEMP TABLE o AS SELECT fiscal_year, string_agg(flag_id, ';' ORDER BY flag_id) AS flags,
                  contract_transaction_unique_key, any_value(federal_action_obligation) AS federal_action_obligation
                  FROM read_parquet({all_of('outliers')}) WHERE flag_id IN ('J01', 'J02') GROUP BY ALL""")
    ctx_cols = ", ".join(q(x) for x in OUTLIER_CONTEXT)
    c.execute(f"CREATE OR REPLACE TEMP TABLE ctx (fiscal_year INTEGER, contract_transaction_unique_key VARCHAR, "
              + ", ".join(f"{q(x)} VARCHAR" for x in OUTLIER_CONTEXT) + ")")
    files_all = []
    for fy in years():
        files = stage1.layer_a_files(fy)
        files_all += files
        c.execute(f"""INSERT INTO ctx SELECT {fy}, contract_transaction_unique_key, {ctx_cols}
                      FROM read_parquet({parquet_list_sql(files)})
                      WHERE contract_transaction_unique_key IN (SELECT contract_transaction_unique_key FROM o WHERE fiscal_year = {fy})""")
    c.execute(f"""CREATE OR REPLACE TEMP TABLE aw AS SELECT contract_award_unique_key, COUNT(*) AS award_rows,
                  SUM({amt}) AS award_net, string_agg(DISTINCT CAST(fy AS VARCHAR), ';' ORDER BY CAST(fy AS VARCHAR)) AS award_fiscal_years
                  FROM (SELECT contract_award_unique_key, federal_action_obligation, action_date_fiscal_year AS fy
                        FROM read_parquet({parquet_list_sql(files_all)})
                        WHERE contract_award_unique_key IN (SELECT DISTINCT contract_award_unique_key FROM ctx))
                  GROUP BY 1""")
    cols = (["fiscal_year", "flags", "contract_transaction_unique_key", "federal_action_obligation"] + OUTLIER_CONTEXT
            + ["award_rows_present_years", "award_net_present_years", "award_fiscal_years"])
    res = c.execute(f"""SELECT o.fiscal_year, o.flags, o.contract_transaction_unique_key, o.federal_action_obligation,
                        {', '.join('ctx.' + q(x) for x in OUTLIER_CONTEXT)}, aw.award_rows, aw.award_net, aw.award_fiscal_years
                        FROM o LEFT JOIN ctx USING (fiscal_year, contract_transaction_unique_key)
                        LEFT JOIN aw USING (contract_award_unique_key)
                        ORDER BY o.fiscal_year, abs(TRY_CAST(o.federal_action_obligation AS DECIMAL(38,6))) DESC,
                        o.contract_transaction_unique_key""").fetchall()
    out = [dict(zip(cols, r)) for r in res]
    for r in out:
        r["award_net_present_years"] = dec(r["award_net_present_years"])
    write_csv(REP / "outliers.csv", out, cols)
    return out


# ------------------------------------------------------------------------------------------- completeness


def load_benchmarks() -> list[dict]:
    if not BENCHMARKS.exists():
        return []
    return list(csv.DictReader(open(BENCHMARKS, encoding="utf-8")))


def completeness(yt: list[dict]) -> dict:
    bms = load_benchmarks()
    by_fy = {y["fiscal_year"]: y for y in yt}
    rows = []
    for b in bms:
        fy = int(b["fiscal_year"])
        y = by_fy.get(fy, {})
        base = {k: b.get(k, "") for k in ("benchmark_id", "fiscal_year", "agency", "figure", "dollars_basis", "independence",
                                           "publisher", "title", "url", "published_date", "source_data_as_of", "scope",
                                           "quote_or_location", "includes_excludes", "benchmark_type", "role")}
        base["benchmark_type"] = base["benchmark_type"] or "figure"
        if y.get("status") != "present":
            rows.append({**base, "status": "PENDING", "note": "our data for this year is not yet downloaded"})
            continue
        if not b["dollars_basis"].strip().lower().startswith("nominal"):
            rows.append({**base, "status": "NOT COMPARED", "note": "constant-dollar figure: recorded, not compared"})
            continue
        ours = Decimal(y["net"]) if not b["agency"] else agency_total(fy, b["agency"])
        if ours is None:
            rows.append({**base, "status": "NOT COMPARED", "note": f"agency {b['agency']!r} not found by name in our data"})
            continue
        fig = Decimal(b["figure"])
        gap = ours - fig
        rel = abs(gap) / fig
        if base["benchmark_type"] == "bound":      # "more than $X": one-sided, our total should be at least X
            rows.append({**base, "ours": dec(ours), "gap_dollars": dec(gap), "gap_pct": f"{gap * 100 / fig:.2f}",
                         "status": "MEETS BOUND" if ours >= fig else "BELOW BOUND", "diagnostics": "",
                         "note": "lower bound: checked one-sided (our total should be at least the figure)"})
            continue
        status = "PASS" if rel <= PASS_GAP else "WARN" if rel <= WARN_GAP else "FAIL"
        diag = {}
        if status != "PASS" and not b["agency"]:
            diag = {"ours_without_idv_rows": dec(Decimal(y["net"]) - Decimal(y.get("idv_net") or 0)),
                    "ours_positive_amounts_only": dec(y.get("positive_only"))}
            diag = {k: v for k, v in diag.items()} | {
                f"gap_pct_{k}": f"{(Decimal(v) - fig) * 100 / fig:.2f}%" for k, v in list(diag.items())}
        rows.append({**base, "ours": dec(ours), "gap_dollars": dec(gap), "gap_pct": f"{gap * 100 / fig:.2f}",
                     "status": status, "diagnostics": json.dumps(diag) if diag else "",
                     "note": "our data as of 2026-09-06; the source's data date differs (see source_data_as_of)"})
    write_csv(REP / "completeness_check.csv", rows, ["benchmark_id", "fiscal_year", "agency", "status", "ours", "figure",
                                                     "gap_dollars", "gap_pct", "benchmark_type", "role", "dollars_basis",
                                                     "independence", "diagnostics",
                                                     "note", "publisher", "title", "url", "published_date",
                                                     "source_data_as_of", "scope", "quote_or_location", "includes_excludes"])
    return {"rows": rows, "years": year_status(rows)}


ORDER = {"FAIL": 0, "WARN": 1, "PASS": 2}


def year_status(rows: list[dict]) -> dict[int, dict]:
    """Each year's benchmark status under both rules, side by side.

    Version 2 rule (2026-10-05, changed after seeing version 1's results; see config/benchmarks.csv changelog):
    GAO is primary. A year's status comes from GAO wherever GAO has a figure (exact or approximate); GSA is
    context and sets the status only where GAO has none. GAO lower bounds are checked one-sided and reported.
    Version 1 rule: the worst status among the government-wide exact figures (GAO and GSA)."""
    out: dict[int, dict] = {}
    for r in rows:
        if r["agency"] or r["status"] in ("PENDING", "NOT COMPARED"):
            continue
        y = out.setdefault(int(r["fiscal_year"]), {"gao": None, "gsa": None, "bound": None, "v1": None})
        gao = r.get("role") == "primary"
        if r["benchmark_type"] == "bound":
            y["bound"] = r["status"]
        elif gao:
            y["gao"] = r["status"]
            y["gao_type"] = r["benchmark_type"]
        else:
            y["gsa"] = r["status"]
        if r["benchmark_type"] == "figure" and (y["v1"] is None or ORDER[r["status"]] < ORDER[y["v1"]]):
            y["v1"] = r["status"]
    for fy, y in out.items():
        y["v2"] = y["gao"] or y["gsa"]
        y["class"] = ("well-defined" if y["gao"] and y.get("gao_type") == "figure" else
                      "loosely defined" if (y["gao"] or y["gsa"] or y["bound"]) else "none")
    return out


_agency_cache: dict = {}


def agency_total(fy: int, name: str) -> Decimal | None:
    c = con()
    r = c.execute(f"""SELECT SUM(net) FROM read_parquet('{stage2.year_dir(fy) / "agencies.parquet"}')
                      WHERE lower(name) = lower(?)""", [name]).fetchone()[0]
    return Decimal(r) if r is not None else None


def completeness_markdown(c, comp: dict, yt: list[dict]) -> str:
    rows = comp["rows"]
    ys = comp["years"]
    def label(fy):
        return f"FY{fy} (pending - not yet downloaded)" if fy in config.years_pending() else f"FY{fy}"
    well = sorted(fy for fy, y in ys.items() if y["class"] == "well-defined")
    loose = sorted(fy for fy, y in ys.items() if y["class"] == "loosely defined")
    none = [fy for fy in config.years_in_scope() if fy not in well and fy not in loose]
    v2 = {s_: sum(1 for y in ys.values() if y["v2"] == s_) for s_ in ("PASS", "WARN", "FAIL")}
    v1 = {s_: sum(1 for y in ys.values() if y["v1"] == s_) for s_ in ("PASS", "WARN", "FAIL")}
    bounds = [y["bound"] for y in ys.values() if y["bound"]]
    L = [f"GAO and GSA both start from FPDS, the system USAspending draws from, so a match checks our extraction and "
         f"sums, not FPDS itself. {len(well)} of {len(config.years_in_scope())} years have a well-defined benchmark "
         f"(a GAO figure: {year_ranges(well) or 'none'}), {len(loose)} have a loosely defined one "
         f"({year_ranges(loose) or 'none'}: GSA figures, and GAO statements that are lower bounds or approximate), and "
         f"{len(none)} have none ({', '.join(label(fy) for fy in none) if len(none) < 4 else year_ranges(none)}). "
         f"Status with GAO primary and GSA as context: {v2['PASS']} PASS, {v2['WARN']} WARN, {v2['FAIL']} FAIL. "
         f"GAO lower bounds met: {sum(1 for b_ in bounds if b_ == 'MEETS BOUND')} of {len(bounds)}. "
         f"Version 1 rule (the worse of GAO and GSA): {v1['PASS']} PASS, {v1['WARN']} WARN, {v1['FAIL']} FAIL.", "",
         "| FY | Class | Status (version 2: GAO primary) | Status (version 1: worst of GAO and GSA) | GAO | GSA | GAO lower bound |",
         "|---|---|---|---|---|---|---|"]
    for fy in sorted(ys):
        y = ys[fy]
        L.append(f"| {fy} | {y['class']} | **{y['v2'] or ''}** | {y['v1'] or ''} | {y['gao'] or ''} | {y['gsa'] or ''} | {y['bound'] or ''} |")
    L += ["",
         "# Completeness check against published totals", "",
         f"Generated {now()} by `python -m src.integrity_report`. Thresholds are fixed in `config/flag_catalog.csv` (I01, I02) "
         "and were written down before any comparison: PASS within 2%, WARN within 10%, FAIL beyond 10%. They apply to "
         "figures stated in nominal dollars. GAO lower bounds (\"more than $X\") are checked one-sided. Constant-dollar "
         "figures are recorded, not compared.", "",
         "**Expected differences.** Each published figure reflects its source's data as of its own date. Ours reflect "
         "USAspending's release of 2026-09-06. Data keeps changing after publication, so small gaps are expected, "
         "especially for recent years. The gaps are reported as they are, with no adjustment.", "",
         "| FY | Benchmark | Agency | Status | Our net total | Published figure | Gap | Gap % | Data as of (source) |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: (int(r["fiscal_year"]), r["agency"], r["benchmark_id"])):
        L.append(f"| {r['fiscal_year']} | [{r['benchmark_id']}]({r['url']}) | {r['agency'] or 'government-wide'} | "
                 f"**{r['status']}** | {money(r.get('ours'))} | {money(r['figure'])} | {money(r.get('gap_dollars'))} | "
                 f"{(r.get('gap_pct') or '') and r['gap_pct'] + '%'} | {r['source_data_as_of']} |")
    L += ["", "## Every WARN or FAIL: likely reasons and the ones our data can test", ""]
    for r in rows:
        if r["status"] in ("WARN", "FAIL"):
            L += [f"**{r['benchmark_id']} (FY{r['fiscal_year']}, {r['agency'] or 'government-wide'}): {r['status']}, gap "
                  f"{r['gap_pct']}%.**", "",
                  "- **Possible reasons:**",
                  "  - definitions: IDV rows, other transaction agreements, classified actions;",
                  "  - whether deobligations are netted;",
                  "  - the source's data date versus ours (2026-09-06);",
                  "  - constant versus nominal dollars.",
                  f"- **What the source says it includes and excludes:** {r['includes_excludes'] or '(nothing stated)'}"]
            if r.get("diagnostics"):
                d = json.loads(r["diagnostics"])
                L.append("- **Diagnostics.** These are shown next to the main number and never replace it:")
                L.append(f"  - without IDV rows: {money(d['ours_without_idv_rows'])} ({d['gap_pct_ours_without_idv_rows']} gap);")
                L.append(f"  - positive amounts only: {money(d['ours_positive_amounts_only'])} "
                         f"({d['gap_pct_ours_positive_amounts_only']} gap).")
            L.append("")
    L += ["## Inside our own data (no outside source needed)", ""] + own_data_lines(c) + ["", "## Sources", ""]
    for r in sorted(rows, key=lambda r: (int(r["fiscal_year"]), r["benchmark_id"])):
        published = f", published {r['published_date']}" if r["published_date"] else ""
        L.append(f"- **{r['benchmark_id']}**: {r['publisher']}, \"{r['title']}\"{published}. <{r['url']}>.")
        L.append(f"  - Figure: {money(r['figure'])} ({r['dollars_basis']}).")
        L.append(f"  - Scope: {r['scope'].rstrip('.')}.")
        L.append(f"  - Quote or location: {r['quote_or_location'].rstrip('.')}.")
        L.append(f"  - Data as of: {r['source_data_as_of'] or 'not stated'}.")
    return "\n".join(L) + "\n"


def year_ranges(fys) -> str:
    """[2010, 2011, 2012, 2016] -> 'FY2010-FY2012, FY2016'."""
    out, run = [], []
    for fy in sorted(fys):
        if run and fy != run[-1] + 1:
            out.append(run)
            run = []
        run.append(fy)
    if run:
        out.append(run)
    return ", ".join(f"FY{r[0]}" if len(r) == 1 else f"FY{r[0]}-FY{r[-1]}" for r in out)


def own_data_lines(c) -> list[str]:
    """H01-H08 in words: the months, agencies and sub-agencies that the catalog's rules picked out, with names."""
    cross = stage2.CROSS
    ag = {code: name for code, name in c.execute(
        f"SELECT code, arg_max(name, fiscal_year) FROM read_parquet({all_of('agencies')}) GROUP BY 1").fetchall()}
    sub = {code: f"{name} ({agency})" for code, name, agency in c.execute(
        f"""SELECT code, arg_max(name, fiscal_year), arg_max(agency_name, fiscal_year)
            FROM read_parquet({all_of('subagencies')}) GROUP BY 1""").fetchall()}
    L = []
    months = c.execute(f"""SELECT month, rows, med_rows, net, med_net, h01_thin_rows, h02_thin_dollars
                           FROM read_parquet('{cross / 'months.parquet'}') WHERE h01_thin_rows OR h02_thin_dollars
                           ORDER BY month""").fetchall()
    L.append("- **Thin months (H01 rows, H02 dollars; under half the year's median month):** "
             + ("; ".join(f"{m}: " + ", ".join(
                 ([f"{r:,} rows vs a median of {int(mr):,}"] if h1 else []) + ([f"net {money(n)} vs a median of {money(mn)}"] if h2 else []))
                 for m, r, mr, n, mn, h1, h2 in months) if months else "none") + ".")
    for table, names, what in (("agency_year_flags", ag, "Agencies"), ("subagency_year_flags", sub, "Sub-agencies")):
        gaps = c.execute(f"""SELECT code, list(fiscal_year ORDER BY fiscal_year) FROM read_parquet('{cross / (table + '.parquet')}')
                             WHERE flag_id IN ('H03', 'H06') GROUP BY 1 ORDER BY 1""").fetchall()
        fid = "H03" if what == "Agencies" else "H06"
        L.append(f"- **{what} missing in a middle year ({fid}):** "
                 + ("; ".join(f"{code} {names.get(code, '(name unknown)')}: no rows in {year_ranges(fys)}" for code, fys in gaps)
                    if gaps else "none") + ".")
        drops = c.execute(f"""SELECT flag_id, code, fiscal_year, before, during FROM read_parquet('{cross / (table + '.parquet')}')
                              WHERE flag_id NOT IN ('H03', 'H06') ORDER BY fiscal_year, code""").fetchall()
        L.append(f"- **{what}: drops below 20% of the year before that recover (H04/H05/H07/H08):** "
                 + ("; ".join(f"{fid_} {code} {names.get(code, '(name unknown)')}, FY{fy}: {money(during)} after "
                              f"{money(before)} the year before" for fid_, code, fy, before, during in drops) if drops else "none") + ".")
    skipped = cross / "_skipped.json"
    sk = json.loads(skipped.read_text()) if skipped.exists() else {}
    if sk.get("pending_years"):
        L.append(f"- **Skipped because of pending years ({', '.join('FY' + str(y) for y in sk['pending_years'])}):** "
                 + "; ".join(sk["skipped"]) + ".")
    return L


# ------------------------------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    c = con()
    REP.mkdir(parents=True, exist_ok=True)
    cat = stage2.catalog()
    yt = year_table(c)
    write_csv(REP / "years.csv", yt, ["fiscal_year", "status", "zip", "zip_sha256", "release", "stage1_proof", "proof_rows",
                                      "proof_dollars", "rows", "net", "distinct_keys", "awards", "agencies", "subagencies",
                                      "idv_rows", "idv_net", "positive_only"])
    fc = flag_counts(c, cat)
    column_quality(c)
    outl = outliers(c)
    comp = completeness(yt)
    (REP / "completeness_check.md").write_text(completeness_markdown(c, comp, yt), encoding="utf-8")
    from . import integrity_summary
    integrity_summary.write(c, cat, yt, fc, comp, outl)
    print(f"reports -> {REP}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
