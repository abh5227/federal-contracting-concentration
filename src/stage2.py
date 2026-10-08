"""Stage 2: integrity and completeness profile of Stage 1 (facts about the data; the data is untouched).

    python -m src.stage2 year --fy 2024        # one year's flags and profiles (restartable: skips a finished year)
    python -m src.stage2 years                 # every proven year in Stage 1
    python -m src.stage2 cross                 # cross-year checks (keys across years, agency matrix, labels, parent test)
    python -m src.stage2 all                   # years + cross + reports

Every rule and threshold comes from config/flag_catalog.csv (committed before this ran). Nothing here
changes, drops or fixes a row: findings are written as facts to data/integrity/ (rebuildable at any time
from Stage 1) and summarised in reports/integrity/ by src/integrity_report.py.

Outputs (data/integrity/):
  row_flags/fy{YYYY}.parquet          one row per (transaction key, flag): contract_transaction_unique_key,
                                      fiscal_year, flag_id (year-local flags + cross-year B03)
  fy{YYYY}/*.parquet                  per-year profiles (column profile, top values, months, agencies, ...)
  cross/*.parquet                     cross-year results
FY2015 is pending (not yet downloaded): cross-year comparisons that would need it are skipped and say so.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from . import config, stage1
from .convert import parquet_list_sql, q

OUT = config.INTEGRITY_DIR
ROW_FLAGS = OUT / "row_flags"
CROSS = OUT / "cross"
CATALOG = config.REPO_ROOT / "config" / "flag_catalog.csv"
KEY, AWARD, MONEY = "contract_transaction_unique_key", "contract_award_unique_key", "federal_action_obligation"
RELEASE_DAY = "2026-09-06"
PENDING_NOTE = "FY2015 is pending (not yet downloaded); skipped, not flagged."

# ---- fixed values from config/flag_catalog.csv (written before this ran) -----------------------
PLACEHOLDER_WORDS = ["UNKNOWN", "UNK", "N/A", "NA", "N\\A", "NONE", "NULL", "NIL", "NAN", "-", "--", ".", "?", "TBD",
                     "NOT APPLICABLE", "NOT AVAILABLE", "MISSING", "MULTIPLE RECIPIENTS",
                     "MISCELLANEOUS FOREIGN AWARDEES", "MISCELLANEOUS FOREIGN CONTRACTORS"]
PLACEHOLDER_VENDORS = ["MULTIPLE RECIPIENTS", "MISCELLANEOUS FOREIGN AWARDEES", "MISCELLANEOUS FOREIGN CONTRACTORS",
                       "UNKNOWN", "UNKNOWN VENDOR", "N/A", "NA", "NONE", "NULL"]
DATE_COLS = ["period_of_performance_start_date", "period_of_performance_current_end_date",
             "period_of_performance_potential_end_date", "ordering_period_end_date", "solicitation_date"]
TS_COLS = ["initial_report_date", "last_modified_date"]
ID_COLS = ["recipient_uei", "recipient_parent_uei", "recipient_duns", "recipient_parent_duns"]
LAG_DAYS = 90
MANY_NAMES = 5
THIN_MONTH = 0.5
DROP_TO, RECOVER_TO = 0.2, 0.5
DROP_MIN_DOLLARS, DROP_MIN_ROWS = 10_000_000, 1_000
BIG = 1_000_000_000
TOP_N = 100
Z_LIMIT, Z_MIN_GROUP = 5, 20
COMPETED = ["A", "D", "F", "CDO"]
COVERAGE_COLS = ["recipient_uei", "recipient_duns", "recipient_parent_uei", "recipient_parent_duns",
                 "product_or_service_code", "extent_competed_code", "number_of_offers_received",
                 "type_of_set_aside_code", "parent_award_id_piid"]
WORK_COLS = ["award_or_idv_flag", "action_date_fiscal_year", "recipient_name", "recipient_uei", "recipient_parent_uei",
             "recipient_duns", "recipient_parent_duns", "recipient_parent_name", "recipient_parent_name_raw",
             "product_or_service_code", "product_or_service_code_description", "naics_code", "naics_description",
             "awarding_agency_code", "awarding_agency_name", "awarding_sub_agency_code", "awarding_sub_agency_name",
             "awarding_office_code", "awarding_office_name", "funding_agency_code", "funding_agency_name",
             "funding_sub_agency_code", "funding_sub_agency_name", "funding_office_code", "funding_office_name",
             "number_of_offers_received", "award_type_code", "award_type", "idv_type_code", "idv_type",
             "extent_competed_code", "extent_competed", "type_of_set_aside_code", "type_of_set_aside",
             "type_of_contract_pricing_code", "type_of_contract_pricing", "parent_award_id_piid", "award_id_piid",
             "total_dollars_obligated", "action_date", *DATE_COLS, *TS_COLS]
MAIN_PAIRS = [("awarding_agency_code", "awarding_agency_name"), ("awarding_sub_agency_code", "awarding_sub_agency_name"),
              ("awarding_office_code", "awarding_office_name"), ("funding_agency_code", "funding_agency_name"),
              ("funding_sub_agency_code", "funding_sub_agency_name"), ("funding_office_code", "funding_office_name"),
              ("product_or_service_code", "product_or_service_code_description"), ("naics_code", "naics_description"),
              ("award_type_code", "award_type"), ("idv_type_code", "idv_type"),
              ("extent_competed_code", "extent_competed"), ("type_of_set_aside_code", "type_of_set_aside"),
              ("type_of_contract_pricing_code", "type_of_contract_pricing")]


# Dimensions every dashboard summary can be filtered by (the global filters).
DIMS_SQL = ("awarding_agency_code AS agency, awarding_sub_agency_code AS subagency, "
            "CASE WHEN award_or_idv_flag = 'IDV' THEN 'IDV_' || idv_type_code ELSE award_type_code END AS award_type, "
            "left(product_or_service_code, 1) AS psc_cat")
DIMS = ["agency", "subagency", "award_type", "psc_cat"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def catalog_sha() -> str:
    import hashlib
    return hashlib.sha256(CATALOG.read_bytes()).hexdigest()


def catalog() -> list[dict]:
    return list(csv.DictReader(open(CATALOG, encoding="utf-8")))


def sql_list(values: list[str]) -> str:
    return "(" + ", ".join("'" + v.replace("'", "''") + "'" for v in values) + ")"


def blank(c: str) -> str:
    return f"regexp_full_match({q(c)}, '\\s*')"


def placeholder_expr(value_sql: str, column_name: str) -> str:
    """E03: placeholder-looking value. The all-zero rule applies only to *_code, *_uei, *_duns columns."""
    words = f"upper(trim({value_sql})) IN {sql_list(PLACEHOLDER_WORDS)} OR upper(trim({value_sql})) LIKE 'REDACTED%'"
    if column_name.endswith(("_code", "_uei", "_duns")):
        words += f" OR regexp_full_match({value_sql}, '0{{2,}}')"
    return f"({words})"


# Fast row-level versions of blank / zero / placeholder for the cube (cheap first-character tests guard the
# exact regex, which then runs only on candidates). build_year asserts they give the same totals as the
# regex versions used in the column profile, so the two can never silently disagree.
WS_ASCII = "(9, 10, 11, 12, 13, 32)"


def blank_fast(v: str) -> str:
    return f"({v} = '' OR (ascii({v}) IN {WS_ASCII} AND regexp_full_match({v}, '\\s*')))"


def zero_fast(v: str) -> str:
    return f"(CASE WHEN ascii({v}) IN (45, 48) AND ltrim({v}, '-0.') = '' THEN regexp_full_match({v}, '-?0+(\\.0+)?') ELSE false END)"


def placeholder_fast(v: str, column_name: str) -> str:
    longest = max(len(w) for w in PLACEHOLDER_WORDS) + 8
    words = (f"(CASE WHEN length({v}) <= {longest} THEN upper(trim({v})) IN {sql_list(PLACEHOLDER_WORDS)} ELSE false END"
             f" OR (CASE WHEN ascii({v}) IN (82, 114) OR ascii({v}) IN {WS_ASCII} THEN upper(left(trim({v}), 8)) = 'REDACTED' ELSE false END)")
    if column_name.endswith(("_code", "_uei", "_duns")):
        words += f" OR (CASE WHEN ascii({v}) = 48 AND length({v}) >= 2 THEN ltrim({v}, '0') = '' ELSE false END)"
    return words + ")"


def code_label_pairs(header: list[str]) -> list[tuple[str, str]]:
    pairs = []
    for c in header:
        if not c.endswith("_code"):
            continue
        base = c[:-5]
        for lab in (f"{base}_name", base, f"{base}_description", f"{c}_description"):
            if lab in header and lab != c:
                pairs.append((c, lab))
                break
    return pairs


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    spill = config.SCRATCH_DIR / "duckdb_stage2"
    spill.mkdir(parents=True, exist_ok=True)
    con.execute(f"SET temp_directory = '{spill}'")
    con.execute("SET TimeZone = 'UTC'")
    con.execute("SET preserve_insertion_order = false")
    con.execute("SET memory_limit = '6GB'")
    return con


def write(con, sql: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".parquet.tmp")
    con.execute(f"COPY ({sql}) TO '{tmp}' (FORMAT parquet, COMPRESSION zstd)")
    tmp.replace(path)


# ================================================================================ per year


def year_dir(fy: int) -> Path:
    return OUT / f"fy{fy}"


def year_done(fy: int) -> bool:
    d = year_dir(fy) / "_done.json"
    if not d.exists():
        return False
    done = json.loads(d.read_text())
    listing = json.loads((config.layer_a_dir(fy) / "_files.json").read_text())
    return done.get("zip_sha256") == listing["zip_sha256"] and done.get("catalog_sha256") == catalog_sha()


def build_year(fy: int, log=print, force: bool = False) -> None:
    if year_done(fy) and not force:
        log(f"FY{fy}: Stage 2 already built, skipping")
        return
    t0 = time.time()
    files = stage1.layer_a_files(fy)
    listing = json.loads((config.layer_a_dir(fy) / "_files.json").read_text())
    header = listing["columns"]
    con = connect()
    con.execute(f"CREATE VIEW a AS SELECT * FROM read_parquet({parquet_list_sql(files)})")
    d = year_dir(fy)
    d.mkdir(parents=True, exist_ok=True)
    fy_start, fy_end = f"{fy - 1}-10-01", f"{fy}-09-30"
    allcols = ", ".join(q(c) for c in header)

    # A narrow working table: only what the rules need, typed by explicit, counted rules (nothing is changed in Stage 1).
    log(f"FY{fy}: working table")
    # action_date: strictly YYYY-MM-DD (C03). Other date columns: YYYY-MM-DD with an optional time of day, because
    # period_of_performance_potential_end_date is stored as 'YYYY-MM-DD 00:00:00' (C04 revision, see the catalog).
    date_sel = ", ".join(
        [f"CASE WHEN regexp_full_match(action_date, '\\d{{4}}-\\d{{2}}-\\d{{2}}') THEN TRY_CAST(action_date AS DATE) END AS d_action_date"]
        + [f"CASE WHEN regexp_full_match({q(c)}, '\\d{{4}}-\\d{{2}}-\\d{{2}}( \\d{{2}}:\\d{{2}}:\\d{{2}})?') "
           f"THEN CAST(TRY_CAST({q(c)} AS TIMESTAMP) AS DATE) END AS {q('d_' + c)}" for c in DATE_COLS])
    ts_sel = ", ".join(f"CAST(TRY_CAST(NULLIF({q(c)}, '') AS TIMESTAMPTZ) AS DATE) AS {q('d_' + c)}" for c in TS_COLS)
    con.execute(f"""CREATE TEMP TABLE t AS SELECT
        {KEY} AS k, {AWARD} AS aw, {q(MONEY)} AS m_txt, TRY_CAST(NULLIF({q(MONEY)}, '') AS DECIMAL(38,6)) AS amt,
        md5(concat_ws(chr(31), {allcols})) AS rowhash,
        {date_sel}, {ts_sel},
        {", ".join(q(c) for c in WORK_COLS if c in header)}
        FROM a""")
    n_rows = con.execute("SELECT COUNT(*) FROM t").fetchone()[0]

    # ---------------------------------------------------------------- row flags (year-local)
    log(f"FY{fy}: row flags ({n_rows:,} rows)")
    S = []
    def flag(fid: str, where: str, frm: str = "t") -> None:
        S.append(f"SELECT k, '{fid}' AS flag_id FROM {frm} WHERE {where}")
    flag("B01", "regexp_full_match(k, '\\s*')")
    flag("B02", "k IN (SELECT k FROM t GROUP BY k HAVING COUNT(*) > 1)")
    flag("B04", "rowhash IN (SELECT rowhash FROM t GROUP BY rowhash HAVING COUNT(*) > 1)")
    flag("B06", "NOT ((aw LIKE 'CONT_AWD_%' AND award_or_idv_flag = 'AWARD') OR (aw LIKE 'CONT_IDV_%' AND award_or_idv_flag = 'IDV'))")
    flag("C01", f"d_action_date IS NOT NULL AND (d_action_date < DATE '{fy_start}' OR d_action_date > DATE '{fy_end}')")
    flag("C02", f"action_date_fiscal_year IS DISTINCT FROM '{fy}'")
    flag("C03", "d_action_date IS NULL")
    bad_dates = " OR ".join([f"(NOT {blank(c)} AND {q('d_' + c)} IS NULL)" for c in DATE_COLS + TS_COLS])
    flag("C04", bad_dates)
    all_d = ["d_action_date"] + [f"d_{c}" for c in DATE_COLS + TS_COLS]
    flag("C05", " OR ".join(f"({q(c)} < DATE '1900-01-01' OR {q(c)} > DATE '2100-12-31')" for c in all_d))
    flag("C06", "d_period_of_performance_start_date > d_period_of_performance_current_end_date")
    flag("C07", f"d_initial_report_date - d_action_date > {LAG_DAYS}")
    flag("C08", "d_initial_report_date < d_action_date")
    flag("C09", f"d_action_date > DATE '{RELEASE_DAY}'")
    flag("C10", "d_last_modified_date < d_action_date")
    flag("D01", "m_txt = ''")
    flag("D02", "m_txt <> '' AND amt IS NULL")
    flag("D03", "regexp_full_match(m_txt, '-?[0-9]*\\.[0-9]{3,}')")
    flag("D04", "award_or_idv_flag = 'IDV' AND amt <> 0")
    flag("E01", f"upper(trim(recipient_name)) IN {sql_list(PLACEHOLDER_VENDORS)} OR upper(trim(recipient_name)) LIKE 'REDACTED%'")
    flag("E02", " OR ".join(f"(regexp_full_match({q(c)}, '0{{2,}}|9{{2,}}') OR upper(trim({q(c)})) IN {sql_list(PLACEHOLDER_WORDS)})"
                            for c in ID_COLS))
    flag("F01", "NOT " + blank("product_or_service_code") + " AND NOT regexp_full_match(product_or_service_code, '[A-Z0-9]{4}')")
    flag("F02", "NOT " + blank("naics_code") + " AND NOT regexp_full_match(naics_code, '[0-9]{6}')")
    flag("F03", " OR ".join(f"(NOT {blank(c)} AND NOT regexp_full_match({q(c)}, '[A-Z0-9]{{12}}'))" for c in ("recipient_uei", "recipient_parent_uei")))
    flag("F04", " OR ".join(f"(NOT {blank(c)} AND NOT regexp_full_match({q(c)}, '[0-9]{{9}}'))" for c in ("recipient_duns", "recipient_parent_duns")))
    flag("F05", " OR ".join(f"(NOT {blank(c)} AND NOT regexp_full_match({q(c)}, '[0-9A-Z]{{3}}'))" for c in ("awarding_agency_code", "funding_agency_code")))
    flag("F06", " OR ".join(f"(NOT {blank(c)} AND NOT regexp_full_match({q(c)}, '[0-9A-Z]{{4}}'))" for c in ("awarding_sub_agency_code", "funding_sub_agency_code")))
    flag("F09", "NOT " + blank("number_of_offers_received") + " AND NOT regexp_full_match(number_of_offers_received, '[0-9]+')")
    flag("G01", "award_type_code IN ('A', 'C') AND " + blank("parent_award_id_piid"))
    flag("G02", "award_type_code IN ('B', 'D') AND NOT " + blank("parent_award_id_piid"))
    pairs = [(c, l) for c, l in MAIN_PAIRS if c in header and l in header]
    flag("G03", " OR ".join(f"({blank(c)} <> {blank(l)})" for c, l in pairs))
    flag("J02", f"abs(amt) >= {BIG}")
    S.append(f"""SELECT k, 'J01' AS flag_id FROM (SELECT k, ROW_NUMBER() OVER (ORDER BY abs(amt) DESC NULLS LAST, k) AS r FROM t) WHERE r <= {TOP_N}""")
    S.append("""SELECT k, 'J03' AS flag_id FROM (SELECT k, amt, SUM(amt) FILTER (WHERE amt > 0) OVER (PARTITION BY aw) AS pos FROM t)
                WHERE amt < 0 AND -amt > COALESCE(pos, 0)""")
    S.append(f"""SELECT k, 'J04' AS flag_id FROM (
        WITH s AS (SELECT k, log10(abs(CAST(amt AS DOUBLE))) AS x, awarding_agency_code AS ag,
                          left(product_or_service_code, 1) AS p FROM t WHERE amt <> 0),
             md AS (SELECT ag, p, median(x) AS med, COUNT(*) AS n FROM s GROUP BY ag, p),
             ad AS (SELECT s.ag, s.p, median(abs(s.x - md.med)) AS mad FROM s JOIN md USING (ag, p) GROUP BY s.ag, s.p)
        SELECT s.k FROM s JOIN md USING (ag, p) JOIN ad USING (ag, p)
        WHERE n >= {Z_MIN_GROUP} AND mad > 0 AND abs(x - med) / (1.4826 * mad) > {Z_LIMIT})""")
    key_like = [KEY, AWARD, "award_id_piid", "parent_award_id_piid", "product_or_service_code", "naics_code",
                "awarding_agency_code", "funding_agency_code", "awarding_sub_agency_code", "funding_sub_agency_code", *ID_COLS]
    col_sql = {KEY: "k", AWARD: "aw"}
    ws = " OR ".join(f"regexp_matches({col_sql.get(c, q(c))}, '^\\s|\\s$')" for c in key_like)
    flag("X01", ws)
    flag("X02", f"number_of_offers_received = '0' AND extent_competed_code IN {sql_list(COMPETED)}")
    write(con, f"SELECT k AS {KEY}, {fy} AS fiscal_year, flag_id FROM ({' UNION ALL '.join(S)})", d / "row_flags_local.parquet")

    # ---------------------------------------------------------------- column profile (every column)
    log(f"FY{fy}: column profile ({len(header)} columns)")
    prof, tops, phs = [], [], []
    for i, c in enumerate(header, start=1):
        con.execute(f"CREATE OR REPLACE TEMP TABLE g AS SELECT {q(c)} AS v, COUNT(*) AS n FROM a GROUP BY 1")
        r = con.execute(f"""SELECT SUM(n), COALESCE(SUM(n) FILTER (WHERE regexp_full_match(v, '\\s*')), 0),
            COALESCE(SUM(n) FILTER (WHERE regexp_full_match(v, '-?0+(\\.0+)?')), 0),
            COUNT(*) FILTER (WHERE NOT regexp_full_match(v, '\\s*')),
            MIN(v) FILTER (WHERE NOT regexp_full_match(v, '\\s*')), MAX(v) FILTER (WHERE NOT regexp_full_match(v, '\\s*')),
            COALESCE(SUM(n) FILTER (WHERE {placeholder_expr('v', c)}), 0),
            COALESCE(SUM(n) FILTER (WHERE regexp_matches(v, '^\\s|\\s$')), 0),
            COUNT(DISTINCT trim(v)) FILTER (WHERE NOT regexp_full_match(v, '\\s*'))
              - COUNT(DISTINCT upper(trim(v))) FILTER (WHERE NOT regexp_full_match(v, '\\s*')),
            MAX(length(v))
            FROM g""").fetchone()
        prof.append((fy, i, c, *r))
        tops += [(fy, c, rank, v, n) for rank, (v, n) in enumerate(con.execute(
            "SELECT v, n FROM g ORDER BY n DESC, v LIMIT 10").fetchall(), start=1)]
        phs += [(fy, c, v, n) for v, n in con.execute(
            f"SELECT v, n FROM g WHERE {placeholder_expr('v', c)} ORDER BY n DESC, v LIMIT 10").fetchall()]
    con.execute("""CREATE OR REPLACE TEMP TABLE prof (fiscal_year INT, position INT, column_name VARCHAR, rows BIGINT, blank BIGINT,
                   zero BIGINT, distinct_nonblank BIGINT, min_value VARCHAR, max_value VARCHAR, placeholder BIGINT,
                   lead_trail_space BIGINT, case_variant_values BIGINT, max_length BIGINT)""")
    con.executemany("INSERT INTO prof VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", prof)
    write(con, "SELECT * FROM prof", d / "column_profile.parquet")
    con.execute("CREATE OR REPLACE TEMP TABLE tops (fiscal_year INT, column_name VARCHAR, rank INT, value VARCHAR, n BIGINT)")
    con.executemany("INSERT INTO tops VALUES (?, ?, ?, ?, ?)", tops)
    write(con, "SELECT * FROM tops", d / "top_values.parquet")
    con.execute("CREATE OR REPLACE TEMP TABLE phs (fiscal_year INT, column_name VARCHAR, value VARCHAR, n BIGINT)")
    if phs:
        con.executemany("INSERT INTO phs VALUES (?, ?, ?, ?)", phs)
    write(con, "SELECT * FROM phs", d / "placeholder_values.parquet")

    # ---------------------------------------------------------------- year-level profiles
    log(f"FY{fy}: profiles")
    write(con, f"""SELECT {fy} AS fiscal_year, COALESCE(strftime(d_action_date, '%Y-%m'), '(invalid date)') AS month,
                   COUNT(*) AS rows, SUM(amt) AS net, SUM(amt) FILTER (WHERE amt > 0) AS positive,
                   SUM(amt) FILTER (WHERE amt < 0) AS negative FROM t GROUP BY 2 ORDER BY 2""", d / "months.parquet")
    write(con, f"""SELECT {fy} AS fiscal_year, awarding_agency_code AS code, mode(awarding_agency_name) AS name,
                   COUNT(DISTINCT awarding_agency_name) AS names, COUNT(*) AS rows, SUM(amt) AS net
                   FROM t GROUP BY 2""", d / "agencies.parquet")
    write(con, f"""SELECT {fy} AS fiscal_year, awarding_sub_agency_code AS code, mode(awarding_sub_agency_name) AS name,
                   mode(awarding_agency_code) AS agency_code, mode(awarding_agency_name) AS agency_name,
                   COUNT(*) AS rows, SUM(amt) AS net FROM t GROUP BY 2""", d / "subagencies.parquet")
    cov = " UNION ALL ".join(
        f"""SELECT {fy} AS fiscal_year, '{c}' AS column_name, COUNT(*) AS rows, COUNT(*) FILTER (WHERE {blank(c)}) AS blank_rows,
            SUM(abs(amt)) AS gross_dollars, COALESCE(SUM(abs(amt)) FILTER (WHERE {blank(c)}), 0) AS blank_gross_dollars FROM t"""
        for c in COVERAGE_COLS)
    write(con, cov, d / "coverage.parquet")
    write(con, f"""SELECT {fy} AS fiscal_year, CASE WHEN m_txt = '' THEN 'blank' WHEN amt IS NULL THEN 'unparseable'
                     WHEN amt = 0 THEN 'zero' WHEN amt < 0 THEN 'negative' ELSE 'positive' END AS category,
                   COUNT(*) AS rows, SUM(amt) AS dollars,
                   COUNT(*) FILTER (WHERE regexp_full_match(m_txt, '-?[0-9]*\\.[0-9]{{3,}}')) AS more_than_2_decimals
                   FROM t GROUP BY 2""", d / "money.parquet")
    write(con, f"""SELECT {fy} AS fiscal_year, awarding_agency_code AS agency_code, mode(awarding_agency_name) AS agency_name,
                   COUNT(*) AS rows_with_both_dates, quantile_cont(lag, 0.5) AS p50, quantile_cont(lag, 0.9) AS p90,
                   quantile_cont(lag, 0.99) AS p99, COUNT(*) FILTER (WHERE lag > {LAG_DAYS}) AS over_90,
                   COUNT(*) FILTER (WHERE lag < 0) AS negative FROM (
                     SELECT awarding_agency_code, awarding_agency_name, d_initial_report_date - d_action_date AS lag FROM t
                     WHERE d_initial_report_date IS NOT NULL AND d_action_date IS NOT NULL)
                   GROUP BY GROUPING SETS ((awarding_agency_code), ())""", d / "reporting_lag.parquet")
    write(con, f"""SELECT {fy} AS fiscal_year, COALESCE(strftime(d_last_modified_date, '%Y-%m'), '(invalid)') AS last_modified_month,
                   COUNT(*) AS rows, SUM(amt) AS net FROM t GROUP BY 2""", d / "last_modified.parquet")
    labs = []
    for c, l in code_label_pairs(header):
        labs.append(f"""SELECT {fy} AS fiscal_year, '{c}' AS code_column, '{l}' AS label_column, {q(c)} AS code,
                        {q(l)} AS label, COUNT(*) AS rows FROM a WHERE NOT {blank(c)} GROUP BY {q(c)}, {q(l)}""")
    write(con, " UNION ALL ".join(labs), d / "code_labels.parquet")
    write(con, f"""SELECT {fy} AS fiscal_year, 'recipient_uei' AS id_column, recipient_uei AS id, COUNT(DISTINCT upper(trim(recipient_name))) AS names,
                   COUNT(*) AS rows, SUM(amt) AS net, list(DISTINCT upper(trim(recipient_name)) ORDER BY upper(trim(recipient_name)))[1:10] AS example_names
                   FROM t WHERE NOT {blank('recipient_uei')} GROUP BY recipient_uei HAVING COUNT(DISTINCT upper(trim(recipient_name))) >= {MANY_NAMES}
                   UNION ALL
                   SELECT {fy}, 'recipient_parent_uei', recipient_parent_uei, COUNT(DISTINCT upper(trim(recipient_parent_name))),
                   COUNT(*), SUM(amt), list(DISTINCT upper(trim(recipient_parent_name)) ORDER BY upper(trim(recipient_parent_name)))[1:10]
                   FROM t WHERE NOT {blank('recipient_parent_uei')} GROUP BY recipient_parent_uei
                   HAVING COUNT(DISTINCT upper(trim(recipient_parent_name))) >= {MANY_NAMES}""", d / "many_names.parquet")
    write(con, f"""SELECT {fy} AS fiscal_year, COUNT(DISTINCT recipient_parent_uei) FILTER (WHERE NOT {blank('recipient_parent_uei')}) AS parent_ueis,
                   COUNT(DISTINCT recipient_parent_uei) FILTER (WHERE NOT {blank('recipient_parent_uei')} AND NOT {blank('recipient_parent_name_raw')}) AS with_raw_name,
                   (SELECT COUNT(*) FROM (SELECT recipient_parent_uei FROM t WHERE NOT {blank('recipient_parent_uei')} GROUP BY 1
                     HAVING COUNT(DISTINCT upper(trim(recipient_parent_name_raw))) >= {MANY_NAMES})) AS raw_name_many
                   FROM t""", d / "parent_names_raw.parquet")
    write(con, f"""SELECT {fy} AS fiscal_year, COUNT(DISTINCT aw) AS awards, SUM(amt) AS transaction_net,
                   (SELECT SUM(x) FROM (SELECT max(TRY_CAST(NULLIF(total_dollars_obligated, '') AS DECIMAL(38,6))) AS x FROM t GROUP BY aw)) AS sum_award_total_dollars_obligated,
                   (SELECT COUNT(*) FROM (SELECT aw, SUM(amt) AS s, max(TRY_CAST(NULLIF(total_dollars_obligated, '') AS DECIMAL(38,6))) AS tdo
                      FROM t GROUP BY aw) WHERE s = tdo) AS awards_whose_year_sum_equals_award_total
                   FROM t""", d / "award_context.parquet")
    write(con, f"""SELECT f.{KEY}, f.fiscal_year, f.flag_id, t.m_txt AS {MONEY}
                   FROM read_parquet('{d / "row_flags_local.parquet"}') f JOIN t ON t.k = f.{KEY}
                   WHERE f.flag_id IN ('J01', 'J02', 'J03', 'J04')""", d / "outliers.parquet")
    # ---------------------------------------------------------------- cubes for the dashboard's global filters
    log(f"FY{fy}: cubes")
    write(con, f"SELECT k AS {KEY}, {fy} AS fiscal_year, amt, {DIMS_SQL} FROM t", d / "keys_dims.parquet")
    write(con, f"""SELECT {fy} AS fiscal_year, COALESCE(strftime(d_action_date, '%Y-%m'), '(invalid date)') AS month,
                   {DIMS_SQL}, COUNT(*) AS rows, SUM(amt) AS net FROM t GROUP BY ALL""", d / "cube_months.parquet")
    aggs = []
    for i, c in enumerate(header):
        aggs.append(f"COUNT(*) FILTER (WHERE {blank_fast(q(c))}) AS b{i}")
        aggs.append(f"COUNT(*) FILTER (WHERE {zero_fast(q(c))}) AS z{i}")
        aggs.append(f"COUNT(*) FILTER (WHERE {placeholder_fast(q(c), c)}) AS p{i}")
    con.execute(f"CREATE TEMP TABLE cq AS SELECT {DIMS_SQL}, COUNT(*) AS rows, {', '.join(aggs)} FROM a GROUP BY ALL")
    unpivot = " UNION ALL ".join(f"SELECT {fy} AS fiscal_year, agency, subagency, award_type, psc_cat, '{c}' AS column_name, "
                                 f"rows, b{i} AS blank, z{i} AS zero, p{i} AS placeholder FROM cq" for i, c in enumerate(header))
    write(con, unpivot, d / "cube_columns.parquet")
    con.execute("DROP TABLE cq")
    mism = con.execute(f"""SELECT p.column_name, p.blank, c.b, p.zero, c.z, p.placeholder, c.p
        FROM read_parquet('{d / "column_profile.parquet"}') p JOIN (SELECT column_name, SUM(blank) AS b, SUM(zero) AS z,
          SUM(placeholder) AS p, SUM(rows) AS n FROM read_parquet('{d / "cube_columns.parquet"}') GROUP BY 1) c USING (column_name)
        WHERE p.blank <> c.b OR p.zero <> c.z OR p.placeholder <> c.p OR p.rows <> c.n""").fetchall()
    if mism:
        raise SystemExit(f"FY{fy}: cube and column profile disagree (fast vs exact rules): {mism[:5]}")
    write(con, f"""SELECT {fy} AS fiscal_year, COUNT(*) AS rows, SUM(amt) AS net, COUNT(DISTINCT k) AS distinct_keys,
                   COUNT(DISTINCT aw) AS awards, COUNT(DISTINCT awarding_agency_code) AS agencies,
                   COUNT(DISTINCT awarding_sub_agency_code) AS subagencies,
                   COUNT(*) FILTER (WHERE award_or_idv_flag = 'IDV') AS idv_rows,
                   SUM(amt) FILTER (WHERE award_or_idv_flag = 'IDV') AS idv_net,
                   SUM(amt) FILTER (WHERE amt > 0) AS positive_only FROM t""", d / "year_totals.parquet")
    con.close()
    listing = json.loads((config.layer_a_dir(fy) / "_files.json").read_text())
    (d / "_done.json").write_text(json.dumps({"fiscal_year": fy, "zip_sha256": listing["zip_sha256"],
                                              "catalog_rows": len(catalog()), "catalog_sha256": catalog_sha(),
                                              "rows": n_rows, "finished_utc": now(),
                                              "seconds": round(time.time() - t0, 1)}, indent=1))
    log(f"FY{fy}: done in {time.time() - t0:.0f}s")


# ================================================================================ cross-year


def present_years() -> list[int]:
    return [fy for fy in config.years_present() if (year_dir(fy) / "_done.json").exists()]


def read_all(name: str) -> str:
    return parquet_list_sql([year_dir(fy) / f"{name}.parquet" for fy in present_years()])


def build_cross(log=print) -> None:
    years = present_years()
    pending = config.years_pending()
    CROSS.mkdir(parents=True, exist_ok=True)
    con = connect()
    log(f"Cross-year: {len(years)} years; pending {pending}")

    # B03 / B05: keys and awards across years (key + year only, from every Stage 1 file)
    files = {fy: stage1.layer_a_files(fy) for fy in years}
    con.execute("CREATE TEMP TABLE keys AS " + " UNION ALL ".join(
        f"SELECT {KEY} AS k, {AWARD} AS aw, {fy} AS fy FROM read_parquet({parquet_list_sql(f)})" for fy, f in files.items()))
    write(con, f"""SELECT k AS {KEY}, fy AS fiscal_year, 'B03' AS flag_id FROM keys
                   WHERE k IN (SELECT k FROM keys GROUP BY k HAVING COUNT(DISTINCT fy) > 1)""", CROSS / "row_flags_b03.parquet")
    write(con, """SELECT years_spanned, COUNT(*) AS awards FROM (SELECT aw, COUNT(DISTINCT fy) AS years_spanned FROM keys GROUP BY aw)
                  GROUP BY 1 ORDER BY 1""", CROSS / "awards_years_spanned.parquet")
    write(con, """SELECT fy AS fiscal_year, COUNT(DISTINCT aw) AS awards, COUNT(DISTINCT aw) FILTER (WHERE multi) AS awards_also_in_other_years
                  FROM keys JOIN (SELECT aw, COUNT(DISTINCT fy) > 1 AS multi FROM keys GROUP BY aw) USING (aw) GROUP BY 1""",
          CROSS / "awards_multi_year_by_year.parquet")
    con.execute("DROP TABLE keys")

    # row_flags/fy{YYYY}.parquet = year-local flags + B03
    ROW_FLAGS.mkdir(parents=True, exist_ok=True)
    for fy in years:
        write(con, f"""SELECT * FROM read_parquet('{year_dir(fy) / "row_flags_local.parquet"}')
                       UNION ALL SELECT * FROM read_parquet('{CROSS / "row_flags_b03.parquet"}') WHERE fiscal_year = {fy}""",
              ROW_FLAGS / f"fy{fy}.parquet")

    # F08: code labels across years (modal label per code per year; a tie goes to the first label alphabetically, so reruns agree)
    write(con, f"""WITH m AS (SELECT fiscal_year, code_column, label_column, code, first(label ORDER BY rows DESC, label) AS label, SUM(rows) AS rows
                     FROM read_parquet({read_all('code_labels')}) WHERE NOT regexp_full_match(label, '\\s*') GROUP BY ALL)
                   SELECT code_column, label_column, code, COUNT(DISTINCT label) AS labels,
                          list(struct_pack(fiscal_year := fiscal_year, label := label, rows := rows) ORDER BY fiscal_year) AS by_year
                   FROM m GROUP BY ALL HAVING COUNT(DISTINCT label) > 1""", CROSS / "label_changes.parquet")
    # F10: an agency name under both a 3- and a 4-character code across years (one agency split in two)
    write(con, f"""WITH m AS (SELECT code_column, upper(trim(label)) AS name, code, SUM(rows) AS rows,
                                     MIN(fiscal_year) AS first_fy, MAX(fiscal_year) AS last_fy
                              FROM read_parquet({read_all('code_labels')})
                              WHERE code_column IN ('awarding_agency_code', 'funding_agency_code')
                                AND NOT regexp_full_match(label, '\\s*') AND NOT regexp_full_match(code, '\\s*') GROUP BY ALL),
                        dual AS (SELECT code_column, name FROM m GROUP BY ALL
                                 HAVING COUNT(*) FILTER (WHERE length(code) = 3) > 0 AND COUNT(*) FILTER (WHERE length(code) = 4) > 0)
                   SELECT m.* FROM m SEMI JOIN dual USING (code_column, name) ORDER BY code_column, name, code""",
          CROSS / "dual_code_agencies.parquet")
    write(con, f"""SELECT fiscal_year, code_column, label_column, code, COUNT(*) AS labels, SUM(rows) AS rows,
                   list(struct_pack(label := label, rows := rows) ORDER BY rows DESC, label) AS label_list
                   FROM read_parquet({read_all('code_labels')}) WHERE NOT regexp_full_match(label, '\\s*')
                   GROUP BY ALL HAVING COUNT(*) > 1""", CROSS / "multi_label_codes.parquet")

    # H03-H08: agency and sub-agency x year, with FY2015 skipped (never flagged)
    for level, src, fids in (("agency", "agencies", ("H03", "H04", "H05")), ("subagency", "subagencies", ("H06", "H07", "H08"))):
        con.execute(f"CREATE OR REPLACE TEMP TABLE ay AS SELECT fiscal_year, code, rows, net FROM read_parquet({read_all(src)})")
        rows = con.execute("SELECT code, fiscal_year, rows, net FROM ay").fetchall()
        by_code: dict[str, dict[int, tuple[int, float]]] = {}
        for code, fy, n, net in rows:
            by_code.setdefault(code, {})[fy] = (n, net)
        out = []
        for code, ys in by_code.items():
            first, last = min(ys), max(ys)
            for fy in range(first + 1, last):
                if fy in years and fy not in ys:
                    out.append((code, fy, fids[0], "missing in a middle year", None, None))
            for fy in years:
                prev, nxt = fy - 1, fy + 1
                if any(x in pending for x in (prev, fy, nxt)) or prev not in years or nxt not in years:
                    continue
                p, c, n = ys.get(prev), ys.get(fy), ys.get(nxt)
                if not p or not n:
                    continue
                cn, cd = (c or (0, 0))
                if p[1] is not None and p[1] >= DROP_MIN_DOLLARS and (cd or 0) < DROP_TO * float(p[1]) and (n[1] or 0) >= RECOVER_TO * float(p[1]):
                    out.append((code, fy, fids[1], f"net {cd} vs {p[1]} before and {n[1]} after", str(p[1]), str(cd)))
                if p[0] >= DROP_MIN_ROWS and cn < DROP_TO * p[0] and n[0] >= RECOVER_TO * p[0]:
                    out.append((code, fy, fids[2], f"rows {cn} vs {p[0]} before and {n[0]} after", str(p[0]), str(cn)))
        con.execute("CREATE OR REPLACE TEMP TABLE hf (code VARCHAR, fiscal_year INT, flag_id VARCHAR, detail VARCHAR, before VARCHAR, during VARCHAR)")
        if out:
            con.executemany("INSERT INTO hf VALUES (?, ?, ?, ?, ?, ?)", out)
        write(con, "SELECT * FROM hf ORDER BY flag_id, code, fiscal_year", CROSS / f"{level}_year_flags.parquet")
        write(con, "SELECT * FROM ay", CROSS / f"{level}_year_matrix.parquet")
    (CROSS / "_skipped.json").write_text(json.dumps({"pending_years": pending, "note": PENDING_NOTE if pending else "",
        "skipped": ["B03/B05 keys and awards across years cannot include FY2015",
                    "H03/H06 a gap at FY2015 alone is not flagged",
                    "H04/H05/H07/H08 drops whose before, during or after year is FY2015 are not evaluated",
                    "F08 label changes cannot see FY2015",
                    "The FY2015 row-count jump cannot be measured until FY2015 is added"] if pending else []},
        indent=1))

    # H01/H02: thin months (per year, vs that year's median month)
    write(con, f"""WITH m AS (SELECT * FROM read_parquet({read_all('months')}) WHERE month <> '(invalid date)'),
                   med AS (SELECT fiscal_year, median(rows) AS med_rows, median(net) AS med_net FROM m GROUP BY 1)
                   SELECT m.*, med_rows, med_net, rows < {THIN_MONTH} * med_rows AS h01_thin_rows,
                          net < {THIN_MONTH} * med_net AS h02_thin_dollars FROM m JOIN med USING (fiscal_year) ORDER BY fiscal_year, month""",
          CROSS / "months.parquet")

    # K: parent at the time of the action, or today? Raytheon Company's own IDs, FY2018-FY2022.
    k_years = [fy for fy in range(2018, 2023) if fy in years]
    if not k_years:
        con.close()
        log("Cross-year: done (parent test skipped: no FY2018-FY2022 data)")
        return
    k_src = " UNION ALL ".join(f"""SELECT {fy} AS fiscal_year, recipient_name, recipient_uei, recipient_duns, recipient_parent_uei,
        recipient_parent_duns, recipient_parent_name_raw, recipient_parent_name, {q(MONEY)} AS m, action_date
        FROM read_parquet({parquet_list_sql(files[fy])}) WHERE upper(trim(recipient_name)) = 'RAYTHEON COMPANY'""" for fy in k_years)
    write(con, f"""SELECT fiscal_year, recipient_uei, recipient_duns, recipient_parent_uei, recipient_parent_duns,
                   recipient_parent_name_raw, recipient_parent_name, COUNT(*) AS rows,
                   SUM(TRY_CAST(NULLIF(m, '') AS DECIMAL(38,2))) AS net, MIN(action_date) AS first_action, MAX(action_date) AS last_action
                   FROM ({k_src}) GROUP BY ALL ORDER BY fiscal_year, rows DESC""", CROSS / "parent_test_raytheon.parquet")
    write(con, f"""SELECT strftime(TRY_CAST(action_date AS DATE), '%Y-%m') AS month, recipient_parent_duns, recipient_parent_uei,
                   recipient_parent_name_raw, COUNT(*) AS rows FROM ({k_src}) WHERE fiscal_year IN (2019, 2020, 2021)
                   GROUP BY ALL ORDER BY 1, rows DESC""", CROSS / "parent_test_raytheon_by_month.parquet")
    con.close()
    log("Cross-year: done")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="mode", required=True)
    y = sub.add_parser("year")
    y.add_argument("--fy", type=int, action="append", required=True)
    y.add_argument("--force", action="store_true", help="rebuild (overwrite) even if already built")
    sub.add_parser("years")
    sub.add_parser("cross")
    sub.add_parser("all")
    a = p.parse_args(argv)
    log = lambda s: print(s, flush=True)  # noqa: E731
    proven = [fy for fy in config.years_present() if stage1.load_progress(fy).get("status") == "PASS"]
    if a.mode == "year":
        for fy in a.fy:
            if fy not in proven:
                print(f"FY{fy} is not proven in Stage 1; Stage 2 runs only on proven years")
                return 1
            build_year(fy, log, force=a.force)
        return 0
    if a.mode in ("years", "all"):
        for fy in sorted(proven, reverse=True):
            build_year(fy, log)
    if a.mode in ("cross", "all"):
        build_cross(log)
    if a.mode == "all":
        from . import integrity_report
        integrity_report.main([])
    return 0


if __name__ == "__main__":
    sys.exit(main())
