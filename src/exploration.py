"""Follow-up exploration of the open questions from the first report.

    python -m src.exploration part1      # one part: part1 to part12, or part20
    python -m src.exploration rules      # only write rules.json from RULES

Analysis only. Nothing here cleans, drops or changes data, nothing under data/ is written, and nothing is a decision.
Each rule is written in RULES below before the code that uses it. The segment, AMT, VENDOR and hhi() come from
src/analyses_v2.py, and the proposed handling, the working extract and the name normalization from
src/decision_evidence.py. They are imported, not copied.

Outputs are small tables in reports/exploration/, one CSV per table.
"""

from __future__ import annotations

import csv
import json
import random
import re
import shutil
import statistics
import sys
import time
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import duckdb

from . import config
from .analyses_v2 import AMT, MFA, MINT_KEYS, PAIRS, VENDOR, d, files, hhi, years
from .decision_evidence import (all_rows, check_columns, con, extract_path, handled, merged_scores, norm_name, pair_net_sql, pct, q, score,
                                share_above, show_codes, vendor_segments)

OUT = config.REPORTS_DIR / "exploration"
ROW_FLAGS = config.INTEGRITY_DIR / "row_flags"
FLAG_CATALOG = config.REPO_ROOT / "config" / "flag_catalog.csv"

RULES = {
    "segment": "As in src/analyses_v2.py. The awarding agency code as recorded x product or service code x fiscal year.",
    "amount": "AMT in src/analyses_v2.py, federal_action_obligation as a decimal.",
    "vendor": "VENDOR in src/analyses_v2.py. recipient_parent_uei, or recipient_uei when the parent is blank, or "
              "'(no ID)' when both are blank.",
    "hhi": "hhi() in src/analyses_v2.py, over the vendors with a positive net in the segment.",
    "proposed_handling": "As built by handled() in src/decision_evidence.py (variant V1 of src/eda/base_tables.py). "
                         "Each reversal pair keeps its net on its first row and its second row is set to zero. The two "
                         "US Mint rows, rows to MISCELLANEOUS FOREIGN AWARDEES and the vendor '(no ID)' are left out.",
    "civilian": "Every awarding agency code other than 097. A blank code counts as civilian.",
}


# ============================================================================================ helpers


def write(name: str, rows: list[dict]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        if not rows:
            return
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows([{k: (str(v) if isinstance(v, Decimal) else v) for k, v in r.items()} for r in rows])


def fiscal_year(x: date) -> int:
    return x.year + 1 if x.month >= 10 else x.year


PARTS: dict = {}


def part(fn):
    PARTS[fn.__name__] = fn
    return fn


# ============================================================================================ Part 1. One contract traced

MAIN_AGENCY, MAIN_PSC, MAIN_FY = "036", "Q201", 2025
MAIN_MIN_YEARS = 4
EMERSON = "CONT_AWD_W912QR08C0053_9700_-NONE-_-NONE-"
DATE_RANGE = (1990, 2040)                       # a date outside these years counts as impossible

# Layer A columns read for the traced awards, checked against reports/columns_fy2025.txt.
TRACE_COLUMNS = ["contract_transaction_unique_key", "contract_award_unique_key", "award_id_piid", "action_date",
                 "modification_number", "action_type", "transaction_description", "federal_action_obligation",
                 "total_dollars_obligated", "current_total_value_of_award", "potential_total_value_of_award",
                 "period_of_performance_start_date", "period_of_performance_current_end_date",
                 "period_of_performance_potential_end_date", "product_or_service_code",
                 "product_or_service_code_description", "awarding_agency_code", "awarding_agency_name",
                 "awarding_sub_agency_code", "awarding_sub_agency_name", "recipient_name", "recipient_uei",
                 "recipient_parent_name", "recipient_parent_uei", "extent_competed", "number_of_offers_received",
                 "type_of_contract_pricing", "award_type", "parent_award_id_piid", "parent_award_agency_id",
                 "idv_type_code", "extent_competed_code"]

RULES |= {
    "main_example": f"Among awards (contract_award_unique_key) with at least one row in awarding agency {MAIN_AGENCY}, "
                    f"product code {MAIN_PSC}, FY{MAIN_FY}, the one with the largest net over all fiscal years "
                    f"(AMT over every row of the award, as recorded) among those with rows in at least {MAIN_MIN_YEARS} "
                    "fiscal years.",
    "second_example": f"The Emerson award {EMERSON}.",
    "trace_rows": "Every row of the award in every present fiscal year of Layer A, sorted by action_date, then "
                  "modification_number, then the transaction key. The running net is the cumulative AMT in that "
                  "order. Integrity flags are every flag_id in data/integrity/row_flags/ for the row's transaction key, "
                  "with its name from config/flag_catalog.csv, joined by semicolons.",
    "handling_change": "For each row, how the proposed handling treats it: the first row of a reversal pair carries "
                       "the pair's net, the second is set to zero, the US Mint rows, placeholder rows and '(no ID)' "
                       "rows are left out, and every other row is unchanged.",
    "trace_by_year": "One row per fiscal year with rows. Net as recorded and under the proposed handling. Each "
                     "segment the award's rows land in, with the award's net there under the proposed handling, the "
                     "award's share of the segment's net under the proposed handling and the segment's HHI under the "
                     "proposed handling. A product code or vendor ID differs from the year before when the set of "
                     "values differs from the previous fiscal year with rows.",
    "spread": "Each row's AMT spread evenly by day over its period of performance, from "
              "period_of_performance_start_date to period_of_performance_current_end_date, both days included, then "
              "summed by fiscal year (October to September). A row whose start or end date is blank or unreadable is "
              f"missing. A row whose start is after its end, or with a year before {DATE_RANGE[0]} or after "
              f"{DATE_RANGE[1]}, is impossible. Missing and impossible rows are counted and left unspread.",
    "umbrella": "When the main example has parent_award_id_piid filled: every award in the extract with the same "
                "parent_award_id_piid and parent_award_agency_id, in all fiscal years, with its first and last fiscal "
                "year, vendor IDs, net, product codes and extent_competed_code values. The umbrella's own rows are the "
                "rows whose award_id_piid is the umbrella PIID with idv_type_code filled.",
}


def flag_names() -> dict[str, str]:
    with open(FLAG_CATALOG, newline="", encoding="utf-8") as f:
        return {r["flag_id"]: r["name"] for r in csv.DictReader(f)}


def award_years(c: duckdb.DuckDBPyConnection, award: str) -> list[int]:
    return [r[0] for r in c.execute(f"SELECT DISTINCT fy FROM {all_rows()} WHERE contract_award_unique_key = ? ORDER BY 1",
                                    [award]).fetchall()]


def handling_change(key: str, recipient: str | None, vendor: str) -> str:
    for label, (first, second) in PAIRS.items():
        if key == first:
            return f"reversal pair ({label}), first row: carries the pair's net"
        if key == second:
            return f"reversal pair ({label}), second row: set to zero"
    if key in MINT_KEYS:
        return "left out: US Mint row"
    if (recipient or "").strip().upper() == "MISCELLANEOUS FOREIGN AWARDEES":
        return "left out: placeholder vendor"
    if vendor == "(no ID)":
        return "left out: no vendor ID"
    return "unchanged"


def trace_rows(c: duckdb.DuckDBPyConnection, award: str) -> list[dict]:
    fys = award_years(c, award)
    names = flag_names()
    sel = ", ".join(x for x in TRACE_COLUMNS if x != "federal_action_obligation")
    rows = []
    for fy in fys:
        res = c.execute(f"""SELECT {fy} AS fy, {sel}, {AMT} AS amt, {VENDOR} AS v, {MFA} AS mfa
                            FROM read_parquet({files(fy)!r}) WHERE contract_award_unique_key = ?""", [award])
        cols = [x[0] for x in res.description]
        got = [dict(zip(cols, r)) for r in res.fetchall()]
        flags = defaultdict(set)
        for k, f in c.execute(f"""SELECT contract_transaction_unique_key, flag_id FROM read_parquet('{ROW_FLAGS / f"fy{fy}.parquet"}')
                                  WHERE list_contains(?, contract_transaction_unique_key)""",
                              [[r["contract_transaction_unique_key"] for r in got]]).fetchall():
            flags[k].add(f"{f} {names.get(f, '')}".strip())
        for r in got:
            r["flags"] = "; ".join(sorted(flags.get(r["contract_transaction_unique_key"], ())))
            rows.append(r)
    rows.sort(key=lambda r: (r["action_date"] or "", r["modification_number"] or "", r["contract_transaction_unique_key"]))
    run = Decimal(0)
    out = []
    for r in rows:
        run += d(r["amt"])
        out.append({"fiscal_year": r["fy"], "action_date": r["action_date"], "modification_number": r["modification_number"],
                    "action_type": r["action_type"], "transaction_description": r["transaction_description"],
                    "amount": q(r["amt"]), "running_net": q(run), "total_dollars_obligated": r["total_dollars_obligated"],
                    "current_total_value_of_award": r["current_total_value_of_award"],
                    "potential_total_value_of_award": r["potential_total_value_of_award"],
                    "period_of_performance_start_date": r["period_of_performance_start_date"],
                    "period_of_performance_current_end_date": r["period_of_performance_current_end_date"],
                    "period_of_performance_potential_end_date": r["period_of_performance_potential_end_date"],
                    "product_or_service_code": r["product_or_service_code"],
                    "product_or_service_code_description": r["product_or_service_code_description"],
                    "awarding_agency_code": r["awarding_agency_code"], "awarding_agency_name": r["awarding_agency_name"],
                    "awarding_sub_agency_code": r["awarding_sub_agency_code"],
                    "awarding_sub_agency_name": r["awarding_sub_agency_name"], "recipient_name": r["recipient_name"],
                    "recipient_uei": r["recipient_uei"], "recipient_parent_name": r["recipient_parent_name"],
                    "recipient_parent_uei": r["recipient_parent_uei"], "vendor_id": r["v"],
                    "extent_competed": r["extent_competed"], "number_of_offers_received": r["number_of_offers_received"],
                    "type_of_contract_pricing": r["type_of_contract_pricing"], "award_type": r["award_type"],
                    "parent_award_id_piid": r["parent_award_id_piid"], "integrity_flags": r["flags"],
                    "proposed_handling": handling_change(r["contract_transaction_unique_key"], r["recipient_name"], r["v"]),
                    "transaction_key": r["contract_transaction_unique_key"]})
    return out


def trace_by_year(c: duckdb.DuckDBPyConnection, award: str, rows: list[dict]) -> list[dict]:
    hs = c.execute("""SELECT fy, awarding_agency_code, product_or_service_code, v, SUM(amt_h) FROM h
                      WHERE contract_award_unique_key = ? GROUP BY ALL""", [award]).fetchall()
    segs = {(fy, ag, psc) for fy, ag, psc, _, _ in hs}
    c.execute("CREATE OR REPLACE TEMP TABLE tsegs (fy INTEGER, ag VARCHAR, psc VARCHAR)")
    if segs:
        c.executemany("INSERT INTO tsegs VALUES (?, ?, ?)", [list(s) for s in segs])
    vrows = c.execute("""SELECT fy, awarding_agency_code, product_or_service_code, v, SUM(amt_h) AS net FROM h
                         SEMI JOIN tsegs ON h.fy = tsegs.fy AND h.awarding_agency_code IS NOT DISTINCT FROM tsegs.ag
                                    AND h.product_or_service_code IS NOT DISTINCT FROM tsegs.psc GROUP BY ALL""").fetchall()
    scores = score((fy, ag, psc, v, n, n) for fy, ag, psc, v, n in vrows)
    out, prev = [], None
    for fy in sorted({r["fiscal_year"] for r in rows}):
        yr = [r for r in rows if r["fiscal_year"] == fy]
        mine = [x for x in hs if x[0] == fy]
        psc = sorted({r["product_or_service_code"] or "" for r in yr})
        ven = sorted({r["vendor_id"] for r in yr})
        seg_txt = []
        for _, ag, p, _, n in sorted(mine, key=lambda x: (x[1] or "", x[2] or "")):
            h_, _, segnet = scores[(fy, ag, p)]
            seg_txt.append(f"{ag} x {p}: award net {q(d(n))}, share {pct(n, segnet)}%, HHI {q(h_, '0.1') if h_ is not None else 'unscored'}")
        out.append({"fiscal_year": fy, "rows": len(yr), "net": q(sum((d(r["amount"]) for r in yr), Decimal(0))),
                    "net_proposed_handling": q(sum((d(x[4]) for x in mine), Decimal(0))),
                    "segments": "; ".join(seg_txt), "vendor_id": "; ".join(ven), "product_codes": "; ".join(psc),
                    "product_code_differs": "" if prev is None else ("yes" if psc != prev[0] else "no"),
                    "vendor_id_differs": "" if prev is None else ("yes" if ven != prev[1] else "no")})
        prev = (psc, ven)
    return out


def parse_date(s: str | None) -> date | None:
    try:
        return date.fromisoformat((s or "").strip()[:10])
    except ValueError:
        return None


def spread(rows: list[dict]) -> tuple[list[dict], dict]:
    recorded: dict[int, Decimal] = defaultdict(Decimal)
    spread_to: dict[int, Decimal] = defaultdict(Decimal)
    counts = {"rows": len(rows), "spread": 0, "missing": 0, "impossible": 0, "missing_net": Decimal(0), "impossible_net": Decimal(0)}
    for r in rows:
        amt = d(r["amount"])
        recorded[r["fiscal_year"]] += amt
        a, b = parse_date(r["period_of_performance_start_date"]), parse_date(r["period_of_performance_current_end_date"])
        if a is None or b is None:
            counts["missing"] += 1
            counts["missing_net"] += amt
            continue
        if a > b or not all(DATE_RANGE[0] <= x.year <= DATE_RANGE[1] for x in (a, b)):
            counts["impossible"] += 1
            counts["impossible_net"] += amt
            continue
        counts["spread"] += 1
        days = (b - a).days + 1
        x = a
        while x <= b:                                # whole fiscal years at a time
            fy = fiscal_year(x)
            end = min(b, date(fy, 9, 30))
            spread_to[fy] += amt * ((end - x).days + 1) / days
            x = end + timedelta(days=1)
    fys = sorted(set(recorded) | set(spread_to))
    return [{"fiscal_year": fy, "recorded": q(recorded.get(fy, Decimal(0))), "spread": q(spread_to.get(fy, Decimal(0)))}
            for fy in fys], counts


def umbrella(c: duckdb.DuckDBPyConnection, piid: str, agency: str) -> list[dict]:
    res = c.execute(f"""SELECT contract_award_unique_key, MIN(fy), MAX(fy), string_agg(DISTINCT v, '; ' ORDER BY v), SUM(amt),
                               string_agg(DISTINCT product_or_service_code, '; ' ORDER BY product_or_service_code),
                               string_agg(DISTINCT extent_competed_code, '; ' ORDER BY extent_competed_code), COUNT(*)
                        FROM {all_rows()} WHERE parent_award_id_piid = ? AND parent_award_agency_id = ?
                        GROUP BY 1 ORDER BY 5 DESC""", [piid, agency]).fetchall()
    return [{"award": k, "first_fy": a, "last_fy": b, "vendor_id": v, "net": q(n), "product_codes": p,
             "extent_competed_codes": e, "rows": r} for k, a, b, v, n, p, e, r in res]


@part
def part1() -> None:
    check_columns(TRACE_COLUMNS)
    c = con()
    show_codes(c, "awarding_agency_code", limit=10)
    show_codes(c, "product_or_service_code", limit=10)
    handled(c)
    best = c.execute(f"""WITH k AS (SELECT DISTINCT contract_award_unique_key FROM {all_rows()}
                                    WHERE fy = ? AND awarding_agency_code = ? AND product_or_service_code = ?)
                         SELECT contract_award_unique_key, SUM(amt), COUNT(DISTINCT fy) FROM {all_rows()} SEMI JOIN k USING (contract_award_unique_key)
                         GROUP BY 1 HAVING COUNT(DISTINCT fy) >= ? ORDER BY 2 DESC, 1 LIMIT 1""",
                     [MAIN_FY, MAIN_AGENCY, MAIN_PSC, MAIN_MIN_YEARS]).fetchone()
    if best is None:
        raise SystemExit("CHECK FAILED: no award meets the main example rule")
    main = best[0]
    for label, award in (("main", main), ("emerson", EMERSON)):
        rows = trace_rows(c, award)
        if not rows:
            raise SystemExit(f"CHECK FAILED: no rows for {award}")
        write(f"p1_trace_{label}_rows", rows)
        write(f"p1_trace_{label}_by_year", trace_by_year(c, award, rows))
        sp, counts = spread(rows)
        write(f"p1_trace_{label}_spread", sp)
        total_r = sum((d(x["recorded"]) for x in sp), Decimal(0))
        total_s = sum((d(x["spread"]) for x in sp), Decimal(0))
        left = counts["missing_net"] + counts["impossible_net"]
        if abs(total_r - total_s - left) > Decimal("0.05"):
            raise SystemExit(f"CHECK FAILED: {label} spread total {total_s} plus unspread {left} is not the recorded {total_r}")
        print(f"{label}: {award}, PIID {sorted({r['transaction_key'].split('_')[2] for r in rows})}, "
              f"parent PIID {sorted({r['parent_award_id_piid'] or '' for r in rows})}, {len(rows)} rows, "
              f"net {q(sum((d(r['amount']) for r in rows), Decimal(0)))}. Spread: {counts['spread']} rows spread, "
              f"{counts['missing']} missing ({q(counts['missing_net'])}), {counts['impossible']} impossible "
              f"({q(counts['impossible_net'])})", flush=True)
        write(f"p1_trace_{label}_spread_counts", [{k: q(v) for k, v in counts.items()}])
        if label == "main":
            parents = {(r["parent_award_id_piid"] or "").strip() for r in rows} - {""}
            if parents:
                agency = c.execute(f"SELECT DISTINCT parent_award_agency_id FROM {all_rows()} WHERE contract_award_unique_key = ?",
                                   [main]).fetchall()
                for p in sorted(parents):
                    for (ag,) in agency:
                        write("p1_umbrella_orders", umbrella(c, p, ag))
                        own = c.execute(f"""SELECT fy, extent_competed_code, number_of_offers_received FROM {all_rows()}
                                            WHERE award_id_piid = ? AND NULLIF(trim(idv_type_code), '') IS NOT NULL""", [p]).fetchall()
                        print(f"umbrella {p}: own rows {own if own else 'not in the data'}", flush=True)
            else:
                print("main: parent_award_id_piid is blank on every row, so it is no order under an umbrella", flush=True)
    print("part1: checks passed", flush=True)


# ============================================================================================ Part 2. Joint ventures

JV_FLAGS = ["sba_certified_8a_joint_venture", "joint_venture_women_owned_small_business",
            "joint_venture_economic_disadvantaged_women_owned_small_bus"]
JV_PATTERN = r"(^|[^A-Z])(JOINT VENTURE|J\.? ?V\.?)($|[^A-Z])"
JV_VENDOR_SHARE = Decimal("0.5")                # a vendor ID is a joint venture when its venture rows hold half its net
NAME_REVIEW_TOP = 50
LARGEST_TOP = 30
PARENT_TOP = 30
MEMBER_MIN = Decimal(1_000_000)                 # non-venture vendor IDs a member can be matched to, by net in the year
SPLIT_ON = r"\s+AND\s+|[-/&,]"
MIN_LETTERS = 3
MERGE_TOP = 20
MERGE_YEARS = (2024, 2025)
NAME_SQL = ("CASE WHEN NULLIF(trim(recipient_parent_uei), '') IS NOT NULL AND NULLIF(trim(recipient_parent_name), '') IS NOT NULL "
            "THEN recipient_parent_name ELSE recipient_name END")

RULES |= {
    "jv_flag_test": "A row passes the flag test when any of " + ", ".join(JV_FLAGS) + " is 't' in Layer A, joined on "
                    "contract_transaction_unique_key.",
    "jv_name_test": f"A row passes the name test when the upper-cased recipient_name or recipient_parent_name matches "
                    f"{JV_PATTERN}.",
    "jv_rows": "Joint venture rows are the rows kept under the proposed handling that pass either test. Their net is "
               "the money held by joint ventures. Shares are of the year's net under the proposed handling, all "
               "agencies or civilian.",
    "jv_vendor": f"A vendor ID is a joint venture in a fiscal year when its net under the proposed handling is positive "
                 f"and the rows passing a test hold at least {JV_VENDOR_SHARE:.0%} of that net. This is applied to the "
                 "flag test, the name test and either test separately, and 'both' means the flag and name tests both "
                 "hold.",
    "display_name_jv": "A vendor ID's display name in a year follows the display_name rule of src/decision_evidence.py "
                       "(recipient_parent_name when the parent ID and name are both filled, else recipient_name, taking "
                       "the name with the largest net), applied here to every vendor ID with a positive net.",
    "name_review": f"The {NAME_REVIEW_TOP} vendor IDs with the most net on rows that pass the name test, over all years, "
                   "among vendor IDs with no row passing the flag test.",
    "segment_top": "A segment's top vendor is the vendor ID with the largest net in it under the proposed handling (ties "
                   "broken by the ID). Reported: segments whose top vendor is a joint venture (either test) that year, "
                   "and the share of the dollars in segments with HHI above 2,500 that sits in those segments.",
    "jv_largest": f"The {LARGEST_TOP} vendor IDs with the most net over the years in which they are a joint venture "
                  "(either test), with their agencies, top product codes and years.",
    "jv_parent_ids": "Joint venture rows whose recipient_parent_uei is filled and differs from recipient_uei, after "
                     f"trimming. Their parent names are listed, the {PARENT_TOP} with the most such dollars.",
    "jv_member_names": "For each joint venture vendor ID and year, its display name is upper-cased, the venture words "
                       "(the name test pattern) are replaced by a space, and a lone A left before them is dropped. The "
                       f"rest is split on '-', '/', '&', ',' and ' AND '. Each part is normalized with norm_name() of "
                       f"src/decision_evidence.py and kept when it has at least {MIN_LETTERS} letters. A part matches a "
                       f"non-venture vendor ID with ${MEMBER_MIN:,.0f} or more of net in the same year when the first two "
                       "words of the part equal the first two words of that ID's normalized display name. A part of one "
                       "word matches only an ID whose whole normalized display name is that word, since matching it to "
                       "every name that starts with it (AMERICAN, GLOBAL) gave tens of thousands of false matches in a "
                       "first run. Marked for a check by hand: a part of one word, or a part that matches more "
                       "than one ID.",
    "jv_same_segment": "A joint venture and a matched member that both have a positive net in the same segment.",
    "jv_merge": "Each joint venture is merged into its matched member with the largest net that year, its net added to "
                "the member's within each segment, and HHI recomputed under the proposed handling. The share of "
                f"dollars above 2,500 is reported for FY{MERGE_YEARS[0]} and FY{MERGE_YEARS[1]}, all agencies and "
                "civilian, with every match merged and with only the matches not marked for a check by hand.",
}


def jv_strip(name: str) -> list[str]:
    s = (name or "").upper()
    while re.search(JV_PATTERN, s):
        s = re.sub(JV_PATTERN, lambda m: f"{m.group(1)} {m.group(3)}", s)
    s = re.sub(r"\bA\s*$|\bA\s+(?=[,\-/&]|$)", " ", s.strip())
    parts = [norm_name(p) for p in re.split(SPLIT_ON, s)]
    return [p for p in parts if len(re.sub(r"[^A-Z]", "", p)) >= MIN_LETTERS]


def jv_rows_table(c: duckdb.DuckDBPyConnection) -> None:
    """jvf: transaction keys passing the flag test. jr: every kept row's vendor-segment net, split by test result."""
    check_columns(JV_FLAGS + ["recipient_name", "recipient_parent_name", "recipient_uei", "recipient_parent_uei"])
    c.execute("CREATE OR REPLACE TEMP TABLE jvf (k VARCHAR)")
    for fy in years():
        c.execute(f"""INSERT INTO jvf SELECT contract_transaction_unique_key FROM read_parquet({files(fy)!r})
                      WHERE {' OR '.join(f"{x} = 't'" for x in JV_FLAGS)}""")
    c.execute(f"""CREATE OR REPLACE TEMP TABLE jr AS
                  SELECT fy, awarding_agency_code AS ag, product_or_service_code AS psc, v,
                         contract_transaction_unique_key IN (SELECT k FROM jvf) AS f,
                         regexp_matches(upper(COALESCE(recipient_name, '')), '{JV_PATTERN}')
                           OR regexp_matches(upper(COALESCE(recipient_parent_name, '')), '{JV_PATTERN}') AS nm,
                         COUNT(*) AS n, SUM(amt_h) AS net FROM h GROUP BY ALL""")
    c.execute(f"""CREATE OR REPLACE TEMP TABLE jn AS SELECT DISTINCT v, n FROM (
                    SELECT v, upper(recipient_name) AS n FROM h UNION ALL SELECT v, upper(recipient_parent_name) FROM h)
                  WHERE regexp_matches(n, '{JV_PATTERN}')""")


def display_names(c: duckdb.DuckDBPyConnection) -> dict[tuple[int, str], str]:
    return {(fy, v): name for fy, v, name in c.execute(f"""
        WITH r AS (SELECT fy, v, {NAME_SQL} AS name, SUM(amt_h) AS s FROM h GROUP BY ALL),
             t AS (SELECT fy, v FROM r GROUP BY ALL HAVING SUM(s) > 0)
        SELECT fy, v, arg_max(name, (s, -hash(name))) FROM r SEMI JOIN t USING (fy, v) GROUP BY ALL""").fetchall()}


@part
def part2() -> None:
    c = con()
    show_codes(c, "awarding_agency_code", limit=10)
    for fy in (2008, 2025):
        for col in JV_FLAGS:
            print(f"  {col} FY{fy}: {c.execute(f'SELECT {col}, COUNT(*) FROM read_parquet({files(fy)!r}) GROUP BY 1 ORDER BY 2 DESC').fetchall()}",
                  flush=True)
    handled(c)
    jv_rows_table(c)
    nets = {fy: (d(a), d(b)) for fy, a, b in c.execute(
        "SELECT fy, SUM(net), SUM(net) FILTER (WHERE ag IS DISTINCT FROM '097') FROM jr GROUP BY 1").fetchall()}
    names = display_names(c)
    print("part2: tables built", flush=True)

    # vendor classification by year
    vt = defaultdict(lambda: {"net": Decimal(0), "f": Decimal(0), "nm": Decimal(0), "either": Decimal(0), "both": Decimal(0)})
    for fy, v, f, nm, net in c.execute("SELECT fy, v, f, nm, SUM(net) FROM jr GROUP BY ALL").fetchall():
        x, net = vt[(fy, v)], d(net)
        x["net"] += net
        x["f"] += net if f else 0
        x["nm"] += net if nm else 0
        x["either"] += net if (f or nm) else 0
    jv = {}                                          # (fy, v) -> set of tests that hold
    for k, x in vt.items():
        if x["net"] > 0:
            tests = {t for t in ("f", "nm", "either") if x[t] >= JV_VENDOR_SHARE * x["net"]}
            if tests:
                jv[k] = tests
    either = {k for k, t in jv.items() if "either" in t}

    # 1. name-only review
    flagged_ids = {v for (v,) in c.execute("SELECT DISTINCT v FROM jr WHERE f").fetchall()}
    rev = c.execute("""SELECT v, SUM(net), SUM(n), MIN(fy), MAX(fy) FROM jr WHERE nm GROUP BY 1 ORDER BY 2 DESC""").fetchall()
    rev = [r for r in rev if r[0] not in flagged_ids][:NAME_REVIEW_TOP]
    jn = defaultdict(list)
    for v, n in c.execute("SELECT v, n FROM jn ORDER BY v, n").fetchall():
        jn[v].append(n)
    write("p2_jv_name_review", [{"vendor_id": v, "display_name_latest": names.get((b, v), ""),
                                 "matched_names": "; ".join(jn[v][:5]),
                                 "net_on_name_matched_rows": q(d(n)), "rows": rows, "first_fy": a, "last_fy": b, "false_match": ""}
                                for v, n, rows, a, b in rev])
    print("part2: name review written", flush=True)

    # 2. by year
    seg = defaultdict(list)
    for fy, ag, psc, v, net in c.execute("SELECT fy, ag, psc, v, SUM(net) FROM jr GROUP BY ALL").fetchall():
        seg[(fy, ag, psc)].append((v, d(net)))
    scores = score((fy, ag, psc, v, n, n) for (fy, ag, psc), vs_ in seg.items() for v, n in vs_)
    top = {k: max(vs_, key=lambda x: (x[1], x[0]))[0] for k, vs_ in seg.items() if any(n > 0 for _, n in vs_)}
    rowsum = defaultdict(lambda: defaultdict(Decimal))
    for fy, ag, f, nm, n, net in c.execute("""SELECT fy, ag IS DISTINCT FROM '097', f, nm, SUM(n), SUM(net) FROM jr
                                               WHERE f OR nm GROUP BY ALL""").fetchall():
        r = rowsum[fy]
        for t, ok in (("either", True), ("f", f), ("nm", nm), ("both", f and nm)):
            if ok:
                r[f"{t}_rows"] += n
                r[f"{t}_net"] += d(net)
                if ag:
                    r[f"{t}_civ"] += d(net)
    by_year = []
    for fy in years():
        r = rowsum[fy]
        topped = [k for k in scores if k[0] == fy and (fy, top.get(k)) in either]
        above = [k for k in scores if k[0] == fy and scores[k][0] is not None and scores[k][0] > 2500]
        above_net = sum((scores[k][2] for k in above), Decimal(0))
        above_top = sum((scores[k][2] for k in above if (fy, top.get(k)) in either), Decimal(0))
        ids = {t: sum(1 for (y, _), ts in jv.items() if y == fy and t in ts) for t in ("f", "nm", "either")}
        by_year.append({"fiscal_year": fy, "jv_vendor_ids": ids["either"], "jv_vendor_ids_flag_test": ids["f"],
                        "jv_vendor_ids_name_test": ids["nm"],
                        "jv_vendor_ids_both_tests": sum(1 for (y, _), ts in jv.items() if y == fy and {"f", "nm"} <= ts),
                        "jv_vendor_net": q(sum((vt[k]["net"] for k in either if k[0] == fy), Decimal(0))),
                        "jv_rows": int(r["either_rows"]), "jv_rows_flag_test": int(r["f_rows"]), "jv_rows_name_test": int(r["nm_rows"]),
                        "jv_rows_both_tests": int(r["both_rows"]), "jv_net": q(r["either_net"]), "jv_net_flag_test": q(r["f_net"]),
                        "jv_net_name_test": q(r["nm_net"]), "jv_net_both_tests": q(r["both_net"]),
                        "jv_share_of_all_net_pct": pct(r["either_net"], nets[fy][0]),
                        "jv_share_of_civilian_net_pct": pct(r["either_civ"], nets[fy][1]),
                        "segments": sum(1 for k in scores if k[0] == fy), "segments_jv_top": len(topped),
                        "segments_jv_top_above_2500": sum(1 for k in topped if k in set(above)),
                        "share_of_above_2500_dollars_in_jv_topped_pct": pct(above_top, above_net)})
    write("p2_jv_by_year", by_year)

    # largest
    tot = defaultdict(Decimal)
    for k in either:
        tot[k[1]] += vt[k]["net"]
    biggest = sorted(tot, key=lambda v: (-tot[v], v))[:LARGEST_TOP]
    c.execute("CREATE OR REPLACE TEMP TABLE jy (fy INTEGER, v VARCHAR)")
    c.executemany("INSERT INTO jy VALUES (?, ?)", [list(k) for k in either if k[1] in set(biggest)])
    det = defaultdict(lambda: {"ag": defaultdict(Decimal), "psc": defaultdict(Decimal), "fy": set()})
    for fy, v, ag, psc, net in c.execute("SELECT fy, v, ag, psc, SUM(net) FROM jr SEMI JOIN jy USING (fy, v) GROUP BY ALL").fetchall():
        det[v]["ag"][ag] += d(net)
        det[v]["psc"][psc] += d(net)
        det[v]["fy"].add(fy)
    agn = dict(c.execute(f"SELECT awarding_agency_code, arg_max(awarding_agency_name, fy) FROM {all_rows()} GROUP BY 1").fetchall())
    write("p2_jv_largest", [{"rank": i + 1, "vendor_id": v, "display_name": names.get((max(det[v]["fy"]), v), ""),
                             "net_in_jv_years": q(tot[v]),
                             "agencies": "; ".join(f"{agn.get(a, a)} ({pct(n, tot[v], '0.1')}%)" for a, n in
                                                   sorted(det[v]["ag"].items(), key=lambda x: -x[1])[:3]),
                             "top_product_codes": "; ".join(f"{p} ({pct(n, tot[v], '0.1')}%)" for p, n in
                                                            sorted(det[v]["psc"].items(), key=lambda x: -x[1])[:3]),
                             "years": f"{min(det[v]['fy'])} to {max(det[v]['fy'])} ({len(det[v]['fy'])} years)"}
                            for i, v in enumerate(biggest)])
    print("part2: by year and largest written", flush=True)

    # 3. members by parent ID
    par = c.execute(f"""SELECT recipient_parent_uei, arg_max(recipient_parent_name, amt_h), COUNT(*), SUM(amt_h),
                               MIN(fy), MAX(fy), COUNT(DISTINCT recipient_uei)
                        FROM h WHERE (contract_transaction_unique_key IN (SELECT k FROM jvf)
                                      OR regexp_matches(upper(COALESCE(recipient_name, '')), '{JV_PATTERN}')
                                      OR regexp_matches(upper(COALESCE(recipient_parent_name, '')), '{JV_PATTERN}'))
                              AND NULLIF(trim(recipient_parent_uei), '') IS NOT NULL
                              AND trim(recipient_parent_uei) IS DISTINCT FROM trim(recipient_uei)
                        GROUP BY 1 ORDER BY 4 DESC""").fetchall()
    all_jv = sum((r["either_net"] for r in rowsum.values()), Decimal(0))
    all_jv_rows = sum((r["either_rows"] for r in rowsum.values()), Decimal(0))
    par_rows, par_net = sum(r[2] for r in par), sum((d(r[3]) for r in par), Decimal(0))
    write("p2_jv_parent_ids", [{"rank": i + 1, "parent_uei": u, "parent_name": nm, "rows": n, "net": q(d(net)),
                                "venture_ids_rolled_up": k, "years": f"{a} to {b}"} for i, (u, nm, n, net, a, b, k) in enumerate(par[:PARENT_TOP])])
    parent_summary = {"jv_rows": int(all_jv_rows), "jv_net": q(all_jv), "rows_with_other_parent": par_rows,
                      "net_with_other_parent": q(par_net), "share_of_jv_rows_pct": pct(par_rows, all_jv_rows),
                      "share_of_jv_net_pct": pct(par_net, all_jv), "parent_ids": len(par)}
    write("p2_jv_parent_ids_summary", [parent_summary])
    print(f"part2: parent IDs {parent_summary}", flush=True)

    # 3. members by name
    cand = defaultdict(lambda: defaultdict(list))   # fy -> first two words -> [vendor ids]
    for (fy, v), x in vt.items():
        nm = names.get((fy, v), "")
        if (fy, v) in jv or x["net"] < MEMBER_MIN or re.search(JV_PATTERN, nm.upper()):
            continue
        w = norm_name(nm).split()
        if w:
            cand[fy][" ".join(w[:2])].append(v)
    matches = []
    for fy, v in sorted(either):
        nm = names.get((fy, v), "")
        for p in jv_strip(nm):
            w = p.split()
            key = " ".join(w[:2])
            hits = [m for m in cand[fy].get(key, []) if m != v]
            for m in hits:
                matches.append({"fiscal_year": fy, "jv_vendor_id": v, "jv_name": nm, "jv_net": q(vt[(fy, v)]["net"]),
                                "part": p, "match_words": key, "member_vendor_id": m, "member_name": names.get((fy, m), ""),
                                "member_net": q(vt[(fy, m)]["net"]),
                                "check_by_hand": "yes" if len(w) < 2 or len(hits) > 1 else ""})
    write("p2_jv_member_matches", matches)
    print(f"part2: {len(matches)} name matches, {len({(m['fiscal_year'], m['jv_vendor_id']) for m in matches})} venture-years", flush=True)

    # 4. same segment and the merge effect
    segv = {k: dict(vs_) for k, vs_ in seg.items()}
    pos = defaultdict(set)                           # (fy, vendor) -> segments where the vendor's net is positive
    for k, vs_ in segv.items():
        for v, n in vs_.items():
            if n > 0:
                pos[(k[0], v)].add(k)
    same = []
    for m in matches:
        for k in sorted(pos[(m["fiscal_year"], m["jv_vendor_id"])] & pos[(m["fiscal_year"], m["member_vendor_id"])],
                        key=lambda k: (k[1] or "", k[2] or "")):
            vs_ = segv[k]
            same.append({**{x: m[x] for x in ("fiscal_year", "jv_vendor_id", "jv_name", "member_vendor_id", "member_name", "check_by_hand")},
                         "agency_code": k[1], "psc": k[2], "jv_segment_net": q(vs_[m["jv_vendor_id"]]),
                         "member_segment_net": q(vs_[m["member_vendor_id"]]), "segment_net": q(scores[k][2]),
                         "hhi": q(scores[k][0], "0.1")})
    write("p2_jv_same_segment", same)

    def mapping(fy: int, keep) -> dict[str, str]:
        best: dict[str, str] = {}
        for m in matches:
            if m["fiscal_year"] == fy and keep(m):
                cur = best.get(m["jv_vendor_id"])
                if cur is None or (vt[(fy, m["member_vendor_id"])]["net"], m["member_vendor_id"]) > (vt[(fy, cur)]["net"], cur):
                    best[m["jv_vendor_id"]] = m["member_vendor_id"]
        return best

    rows_by_fy = defaultdict(list)
    for (fy, ag, psc), vs_ in seg.items():
        rows_by_fy[fy] += [(fy, ag, psc, v, n) for v, n in vs_]
    effect, shares = [], []
    for fy in years():
        base = {k: s for k, s in scores.items() if k[0] == fy}
        for label, keep in (("every match", lambda m: True), ("matches not marked for a check", lambda m: not m["check_by_hand"])):
            mp = mapping(fy, keep)
            s = merged_scores(rows_by_fy[fy], base, mp)
            if label == "every match":
                for k in {(x["fiscal_year"], x["agency_code"], x["psc"]) for x in same if x["fiscal_year"] == fy}:
                    effect.append({"fiscal_year": fy, "agency_code": k[1], "psc": k[2], "segment_net": q(base[k][2]),
                                   "hhi_as_is": q(base[k][0], "0.1"), "hhi_merged": q(s[k][0], "0.1"),
                                   "hhi_change": q(s[k][0] - base[k][0], "0.1"),
                                   "ventures_merged": "; ".join(sorted(f"{j} into {mp[j]}" for j, _ in segv[k].items() if j in mp))})
            if fy in MERGE_YEARS:
                b0, s0 = share_above(base, nets[fy]), share_above(s, nets[fy])
                shares.append({"fiscal_year": fy, "merges": label, "ventures_merged": len(mp),
                               "share_above_2500_all_pct": b0[0], "share_above_2500_all_merged_pct": s0[0],
                               "change_all_points": s0[0] - b0[0], "share_above_2500_civilian_pct": b0[1],
                               "share_above_2500_civilian_merged_pct": s0[1], "change_civilian_points": s0[1] - b0[1]})
    effect.sort(key=lambda r: (-abs(d(r["hhi_change"])), r["fiscal_year"], r["agency_code"] or "", r["psc"] or ""))
    write("p2_jv_merge_effect", effect[:MERGE_TOP])
    write("p2_jv_merge_share_above_2500", shares)
    for s in shares:
        print(f"  {s}", flush=True)
    check = {fy: share_above({k: v for k, v in scores.items() if k[0] == fy}, nets[fy])[0] for fy in MERGE_YEARS}
    expect = {2024: Decimal("35.52"), 2025: Decimal("50.33")}
    if check != expect:
        raise SystemExit(f"CHECK FAILED: share above 2,500 before merges {check}, expected {expect}")
    print("part2: checks passed", flush=True)


# ============================================================================================ shared by Parts 3 to 6

CIV = "ag IS DISTINCT FROM '097'"


def year_scores(c: duckdb.DuckDBPyConnection, fy: int, where: str = "TRUE") -> tuple[list[tuple], dict[tuple, tuple]]:
    """The vendor-segment nets of one year from vs, and their scores."""
    rows = c.execute(f"SELECT fy, ag, psc, v, net FROM vs WHERE fy = ? AND {where}", [fy]).fetchall()
    return rows, score((*r, r[-1]) for r in rows)


def descriptions(c: duckdb.DuckDBPyConnection, fy: int) -> dict[str, str]:
    """Product code -> the product_or_service_code_description with the most rows that year (ties by the text)."""
    return dict(c.execute(f"""SELECT product_or_service_code, arg_max(d, (n, d))
                              FROM (SELECT product_or_service_code, product_or_service_code_description AS d, COUNT(*) AS n
                                    FROM read_parquet({files(fy)!r}) GROUP BY ALL) GROUP BY 1""").fetchall())


def agency_names(c: duckdb.DuckDBPyConnection) -> dict[str, str]:
    return dict(c.execute(f"SELECT awarding_agency_code, arg_max(awarding_agency_name, fy) FROM {all_rows()} GROUP BY 1").fetchall())


def top_vendor(vendors: dict[str, Decimal]) -> tuple[str, Decimal]:
    return max(vendors.items(), key=lambda x: (x[1], x[0]))


def setup(c: duckdb.DuckDBPyConnection) -> None:
    handled(c)
    vendor_segments(c)
    print("vendor-segment nets built", flush=True)


# ============================================================================================ Part 3. Civilian services growth

SERVICES = "regexp_matches(psc, '^[B-Z]')"
SERVICE_YEARS = (2008, 2025)
REPORT_SERVICES = {2008: Decimal("96.9e9"), 2025: Decimal("229.1e9")}
SERVICES_TOLERANCE = Decimal("0.001")
TOP_CODES = 20

RULES |= {
    "services": "Civilian rows whose product code starts with an upper-case letter other than A. Codes starting with A "
                "are research and development and codes starting with a digit are products.",
    "services_check": "Civilian services net under the proposed handling must be within 0.1% of the report's "
                      "$96.9 billion in FY2008 and $229.1 billion in FY2025.",
    "services_growth": f"Growth is the FY{SERVICE_YEARS[1]} net minus the FY{SERVICE_YEARS[0]} net. A group's share of "
                       "the growth is its growth divided by the growth of all civilian services.",
    "services_top_codes": f"The {TOP_CODES} four-character codes with the most growth in civilian services. Label: the "
                          "description with the most rows in FY2025 (FY2008 when absent). Main agency: the civilian agency "
                          "with the largest FY2025 net in the code. HHI: the FY2025 HHI of the main agency's segment.",
    "services_above_2500": "The share of the growth in agency x code pairs whose FY2025 segment has HHI above 2,500: "
                           "those pairs' FY2025 net minus their FY2008 net, divided by the growth of all civilian services.",
}


@part
def part3() -> None:
    c = con()
    show_codes(c, "awarding_agency_code", limit=10)
    for fy in SERVICE_YEARS:
        print(f"  first character of product_or_service_code FY{fy}: " + str(c.execute(
            f"SELECT left(product_or_service_code, 1), COUNT(*) FROM read_parquet('{extract_path(fy)}') GROUP BY 1 ORDER BY 1").fetchall()),
            flush=True)
    setup(c)
    a, b = SERVICE_YEARS
    tot = dict(c.execute(f"SELECT fy, SUM(net) FROM vs WHERE {CIV} AND fy IN ({a}, {b}) GROUP BY 1").fetchall())
    svc = dict(c.execute(f"SELECT fy, SUM(net) FROM vs WHERE {CIV} AND {SERVICES} AND fy IN ({a}, {b}) GROUP BY 1").fetchall())
    for fy, rep in REPORT_SERVICES.items():
        off = abs(d(svc[fy]) - rep) / rep
        print(f"  civilian services FY{fy}: {q(d(svc[fy]))} against the report's {rep:,.0f} ({off * 100:.3f}% off)", flush=True)
        if off > SERVICES_TOLERANCE:
            raise SystemExit(f"CHECK FAILED: civilian services FY{fy} is {off * 100:.3f}% off the report")
    growth = d(svc[b]) - d(svc[a])
    print(f"  services share of civilian growth: {pct(growth, d(tot[b]) - d(tot[a]))}% (report: 84%)", flush=True)

    def breakdown(key: str) -> list[tuple]:
        return c.execute(f"""SELECT {key} AS k, SUM(net) FILTER (WHERE fy = {a}), SUM(net) FILTER (WHERE fy = {b})
                             FROM vs WHERE {CIV} AND {SERVICES} AND fy IN ({a}, {b}) GROUP BY 1""").fetchall()

    def table(rows: list[tuple], label: str, names: dict | None = None) -> list[dict]:
        out = []
        for k, x, y in rows:
            x, y = d(x or 0), d(y or 0)
            out.append({label: k, **({"name": names.get(k, "")} if names is not None else {}), f"net_fy{a}": q(x),
                        f"net_fy{b}": q(y), "growth": q(y - x), "share_of_services_growth_pct": pct(y - x, growth)})
        return sorted(out, key=lambda r: -d(r["growth"]))

    write("p3_services_by_letter", table(breakdown("left(psc, 1)"), "first_letter"))
    write("p3_services_by_agency", table(breakdown("ag"), "agency_code", agency_names(c)))

    codes = table(breakdown("psc"), "psc")[:TOP_CODES]
    desc = descriptions(c, b)
    old = descriptions(c, a)
    _, s25 = year_scores(c, b, CIV)
    by_ag = defaultdict(dict)
    for (fy, ag, psc), (_, _, net) in s25.items():
        by_ag[psc][ag] = net
    names = agency_names(c)
    out = []
    for r in codes:
        main, _ = top_vendor(by_ag[r["psc"]]) if by_ag.get(r["psc"]) else ("", 0)
        h_ = s25.get((b, main, r["psc"]), (None,))[0]
        out.append({**r, "label": desc.get(r["psc"]) or old.get(r["psc"], ""), "main_agency": names.get(main, main),
                    "main_agency_share_of_fy2025_pct": pct(by_ag[r["psc"]].get(main, 0), d(r[f"net_fy{b}"])),
                    "fy2025_hhi_main_agency_segment": q(h_, "0.1") if h_ is not None else "unscored"})
    write("p3_services_top_codes", out)

    hi = {(ag, psc) for (_, ag, psc), (h_, _, _) in s25.items() if h_ is not None and h_ > 2500}
    pairs = c.execute(f"""SELECT ag, psc, SUM(net) FILTER (WHERE fy = {a}), SUM(net) FILTER (WHERE fy = {b})
                          FROM vs WHERE {CIV} AND {SERVICES} AND fy IN ({a}, {b}) GROUP BY 1, 2""").fetchall()
    g_hi = sum((d(y or 0) - d(x or 0) for ag, psc, x, y in pairs if (ag, psc) in hi), Decimal(0))
    write("p3_services_growth_above_2500", [{"services_growth": q(growth), "growth_in_pairs_above_2500_fy2025": q(g_hi),
                                             "share_pct": pct(g_hi, growth),
                                             "fy2025_services_net_above_2500": q(sum((d(y or 0) for ag, psc, x, y in pairs if (ag, psc) in hi), Decimal(0))),
                                             "fy2025_services_net": q(d(svc[b]))}])
    print(f"  share of services growth in FY2025 segments above 2,500: {pct(g_hi, growth)}%", flush=True)
    print("part3: checks passed", flush=True)


# ============================================================================================ Part 4. The FY2021 IT code split

IT_SERVICES = "^(D3|D[A-K])"
IT_PRODUCTS = "^(70|7[A-K])"
IT_YEARS = range(2018, 2026)
IT_CHECK_YEARS = (2020, 2021)
IT_WORDS = ("IT AND TELECOM", "INFORMATION TECHNOLOGY")
IT_MARKET = (f"CASE WHEN {CIV} AND regexp_matches(psc, '{IT_SERVICES}') THEN 'IT services' "
             f"WHEN {CIV} AND regexp_matches(psc, '{IT_PRODUCTS}') THEN 'IT products' ELSE psc END")

RULES |= {
    "it_markets": "For civilian agencies, codes matching " + IT_SERVICES + " form one market per agency and year, IT "
                  "services, and codes matching " + IT_PRODUCTS + " form another, IT products. Every other code, and "
                  "every Defense code, stays as recorded.",
    "it_check": "Every two-character group the rule catches in FY2020 and FY2021 must be an IT group: the description "
                "with the most rows in the group starts with " + " or ".join(IT_WORDS) + ".",
    "it_effect": "The civilian share of dollars above 2,500 for FY2018 to FY2025, as recorded and with the IT markets "
                 "merged, HHI recomputed over the merged vendor nets. The part of the FY2020 to FY2021 step the merge "
                 "removes is 1 minus the merged step divided by the step as recorded.",
}


@part
def part4() -> None:
    c = con()
    for fy in IT_CHECK_YEARS:
        groups = c.execute(f"""SELECT left(product_or_service_code, 2) AS g, arg_max(product_or_service_code_description, n), SUM(n), COUNT(*)
                               FROM (SELECT product_or_service_code, product_or_service_code_description, COUNT(*) AS n
                                     FROM read_parquet({files(fy)!r}) WHERE awarding_agency_code IS DISTINCT FROM '097'
                                       AND (regexp_matches(product_or_service_code, '{IT_SERVICES}') OR regexp_matches(product_or_service_code, '{IT_PRODUCTS}'))
                                     GROUP BY ALL) GROUP BY 1 ORDER BY 1""").fetchall()
        for g, top_desc, n, k in groups:
            print(f"  FY{fy} group {g}: {k} code-description pairs, {n:,} rows, most rows: {top_desc}", flush=True)
            if not (top_desc or "").upper().startswith(IT_WORDS):
                raise SystemExit(f"CHECK FAILED: group {g} in FY{fy} is not an IT group ({top_desc})")
    show_codes(c, "awarding_agency_code", limit=10)
    setup(c)
    c.execute(f"""CREATE OR REPLACE TEMP TABLE vm AS SELECT fy, ag, {IT_MARKET} AS psc, v, SUM(net) AS net FROM vs
                  WHERE fy BETWEEN {IT_YEARS[0]} AND {IT_YEARS[-1]} GROUP BY ALL""")
    nets = dict(c.execute(f"SELECT fy, SUM(net) FROM vs WHERE {CIV} GROUP BY 1").fetchall())
    out = []
    for fy in IT_YEARS:
        res = {}
        for label, table in (("as_recorded", "vs"), ("it_merged", "vm")):
            rows = c.execute(f"SELECT fy, ag, psc, v, net FROM {table} WHERE fy = ? AND {CIV}", [fy]).fetchall()
            s = score((*r, r[-1]) for r in rows)
            res[label] = sum((n for (_, _, _), (h_, _, n) in s.items() if h_ is not None and h_ > 2500), Decimal(0))
            if label == "as_recorded":
                it = [(k, v_) for k, v_ in s.items() if re.match(IT_SERVICES, k[2] or "") or re.match(IT_PRODUCTS, k[2] or "")]
                it_net = sum((v_[2] for _, v_ in it), Decimal(0))
                it_above = sum((v_[2] for _, v_ in it if v_[0] is not None and v_[0] > 2500), Decimal(0))
                it_segs = len(it)
            else:
                m = [(k, v_) for k, v_ in s.items() if k[2] in ("IT services", "IT products")]
                m_above = sum((v_[2] for _, v_ in m if v_[0] is not None and v_[0] > 2500), Decimal(0))
        out.append({"fiscal_year": fy, "civilian_net": q(d(nets[fy])),
                    "share_above_2500_as_recorded_pct": pct(res["as_recorded"], nets[fy]),
                    "share_above_2500_it_merged_pct": pct(res["it_merged"], nets[fy]),
                    "it_net": q(it_net), "it_segments_as_recorded": it_segs,
                    "it_net_above_2500_as_recorded": q(it_above), "it_net_above_2500_merged": q(m_above)})
        print(f"  {out[-1]}", flush=True)
    by = {r["fiscal_year"]: r for r in out}
    step = by[2021]["share_above_2500_as_recorded_pct"] - by[2020]["share_above_2500_as_recorded_pct"]
    step_m = by[2021]["share_above_2500_it_merged_pct"] - by[2020]["share_above_2500_it_merged_pct"]
    write("p4_it_split_effect", out)
    write("p4_it_step", [{"step_as_recorded_points": step, "step_it_merged_points": step_m,
                          "removed_points": step - step_m, "removed_pct_of_step": pct(step - step_m, step, "0.1")}])
    print(f"  FY2020 to FY2021 civilian step: {step} points as recorded, {step_m} merged, "
          f"{pct(step - step_m, step, '0.1')}% removed", flush=True)
    print("part4: checks passed", flush=True)


# ============================================================================================ Part 5. Stable codes

STABLE_YEARS = range(2008, 2026)
STABLE_PAIRS = ((2011, 2012), (2020, 2021))
STABLE_KEEP = Decimal("0.5")
STABLE_REPORT_YEARS = (2012, 2021, 2025)
LINE_YEARS, LINE_DOLLARS = 6, Decimal(10_000_000)
CUTOFFS = (250, 500, 1000)
SHUFFLES = 20
SEED = 20261012
REPORT_LINES = {250: (Decimal("44.75"), Decimal("36.08"), Decimal("36.11"), Decimal("36.1")),
                500: (Decimal("37.92"), Decimal("28.2"), Decimal("29.89"), Decimal("28.22")),
                1000: (Decimal("28.38"), Decimal("17.97"), Decimal("21.55"), Decimal("18.02"))}   # rising_counts.csv
REPORT_LINE_COUNT = 5772
REPORT_WINDOW = (2012, 2020)

RULES |= {
    "stable_code": "A four-character code with rows in every fiscal year FY2008 to FY2025, whose description (the one "
                   "with the most rows that year, upper-cased, every character other than a letter, digit or space "
                   "removed and runs of spaces collapsed) is the same in FY2011 and FY2012 and the same in FY2020 and "
                   f"FY2021, and whose government-wide net under the proposed handling in FY2012 and FY2021 is at least "
                   f"{STABLE_KEEP:.0%} of its net the year before.",
    "stable_lines": f"Trend lines as in src/eda/lines.py on the shivram-eda branch, over all 18 years and stable codes "
                    f"only: one awarding agency x product code, scored in the years its segment has an HHI. Kept with "
                    f"{LINE_YEARS} scored years and ${LINE_DOLLARS:,.0f} of net over them. Rising when the mean HHI of "
                    "the last 3 scored years is at least the cutoff above the mean of the first 3, falling in the "
                    f"mirror case. Shuffled {SHUFFLES} times with seed {SEED}, one generator for all cutoffs, lines in "
                    "agency and code order, as in that file. All agencies, as in the report. The same code run on all "
                    f"codes in FY{REPORT_WINDOW[0]} to FY{REPORT_WINDOW[1]} must give the report's {REPORT_LINE_COUNT:,} "
                    "lines and its rising and falling shares.",
    "stable_line_dollars": "A line set's share of dollars: the net of its kept lines over their scored years, divided "
                           "by the net of every scored segment in the same years.",
    "stable_share": "The civilian share of dollars above 2,500 on stable codes: the civilian net in stable-code segments "
                    "with HHI above 2,500, divided by the civilian net on stable codes, each year.",
}


def norm_desc(s: str | None) -> str:
    return " ".join(re.sub(r"[^A-Z0-9 ]", " ", (s or "").upper()).split())


def classify(vals: list[Decimal], cutoff: int) -> str:
    first, last = sum(vals[:3]) / 3, sum(vals[-3:]) / 3
    return "rising" if last - first >= cutoff else "falling" if first - last >= cutoff else "neither"


def rising_counts(lines: list[list[tuple]]) -> list[dict]:
    import random
    rng = random.Random(SEED)
    out = []
    for cut in CUTOFFS:
        obs, shuf = defaultdict(int), defaultdict(float)
        for v in lines:
            obs[classify([x[1] for x in v], cut)] += 1
        for _ in range(SHUFFLES):
            for v in lines:
                vals = [x[1] for x in v]
                rng.shuffle(vals)
                shuf[classify(vals, cut)] += 1 / SHUFFLES
        n = len(lines)
        out.append({"cutoff": cut, "lines": n, "rising_pct": round(100 * obs["rising"] / n, 2),
                    "rising_pct_after_shuffle": round(100 * shuf["rising"] / n, 2),
                    "falling_pct": round(100 * obs["falling"] / n, 2),
                    "falling_pct_after_shuffle": round(100 * shuf["falling"] / n, 2)})
    return out


def line_set(scores: dict[tuple, tuple], codes: set | None, first: int, last: int) -> tuple[list[list[tuple]], Decimal, Decimal]:
    s = defaultdict(list)
    for (fy, ag, psc), (h_, _, net) in scores.items():
        if h_ is not None and first <= fy <= last and (codes is None or psc in codes):
            s[(ag, psc)].append((fy, float(h_), net))
    kept = []
    for k in sorted(s, key=lambda k: tuple((x is None, x or "") for x in k)):
        v = sorted(s[k])
        if len(v) >= LINE_YEARS and sum((x[2] for x in v), Decimal(0)) >= LINE_DOLLARS:
            kept.append(v)
    all_net = sum((net for (fy, _, _), (h_, _, net) in scores.items() if h_ is not None and first <= fy <= last), Decimal(0))
    return kept, sum((x[2] for v in kept for x in v), Decimal(0)), all_net


@part
def part5() -> None:
    c = con()
    show_codes(c, "awarding_agency_code", limit=10)
    show_codes(c, "product_or_service_code", limit=10)
    present = defaultdict(set)
    for fy, psc in c.execute(f"SELECT DISTINCT fy, product_or_service_code FROM {all_rows()}").fetchall():
        present[psc].add(fy)
    every = {p for p, f in present.items() if p and len(p) == 4 and set(STABLE_YEARS) <= f}
    desc = {fy: {k: norm_desc(v) for k, v in descriptions(c, fy).items()} for pair in STABLE_PAIRS for fy in pair}
    setup(c)
    gnet = defaultdict(Decimal)
    for fy, psc, net in c.execute("SELECT fy, psc, SUM(net) FROM vs GROUP BY ALL").fetchall():
        gnet[(fy, psc)] += d(net)
    stable = sorted(p for p in every
                    if all(desc[a].get(p) and desc[a].get(p) == desc[b].get(p) for a, b in STABLE_PAIRS)
                    and all(gnet[(b, p)] >= STABLE_KEEP * gnet[(a, p)] for a, b in STABLE_PAIRS))
    print(f"  codes with rows every year: {len(every)}, stable: {len(stable)}", flush=True)
    tot25 = sum((n for (fy, _), n in gnet.items() if fy == 2025), Decimal(0))
    write("p5_stable_codes", [{"psc": p, "description_fy2021": desc[2021].get(p, ""),
                               "net_fy2011": q(gnet[(2011, p)]), "net_fy2012": q(gnet[(2012, p)]),
                               "net_fy2020": q(gnet[(2020, p)]), "net_fy2021": q(gnet[(2021, p)]),
                               "net_fy2025": q(gnet[(2025, p)]), "share_of_fy2025_dollars_pct": pct(gnet[(2025, p)], tot25, "0.001")}
                              for p in stable])
    st = set(stable)
    scores, civ_share, by_year = {}, [], []
    for fy in years():
        rows, s = year_scores(c, fy)
        scores |= s
        civ = [(k, v_) for k, v_ in s.items() if k[1] != "097"]
        civ_all = sum((v_[2] for _, v_ in civ), Decimal(0))
        civ_st = [(k, v_) for k, v_ in civ if k[2] in st]
        civ_st_net = sum((v_[2] for _, v_ in civ_st), Decimal(0))
        civ_st_above = sum((v_[2] for _, v_ in civ_st if v_[0] is not None and v_[0] > 2500), Decimal(0))
        civ_above = sum((v_[2] for _, v_ in civ if v_[0] is not None and v_[0] > 2500), Decimal(0))
        by_year.append({"fiscal_year": fy, "civilian_net": q(civ_all), "civilian_net_stable_codes": q(civ_st_net),
                        "stable_codes_share_of_civilian_pct": pct(civ_st_net, civ_all),
                        "share_above_2500_stable_codes_pct": pct(civ_st_above, civ_st_net),
                        "share_above_2500_all_codes_pct": pct(civ_above, civ_all)})
    write("p5_stable_share_by_year", by_year)
    for r in by_year:
        if r["fiscal_year"] in STABLE_REPORT_YEARS:
            print(f"  FY{r['fiscal_year']}: stable codes hold {r['stable_codes_share_of_civilian_pct']}% of civilian dollars", flush=True)

    rep, rep_net, rep_all = line_set(scores, None, *REPORT_WINDOW)
    mine = rising_counts(rep)
    lines, l_net, l_all = line_set(scores, st, STABLE_YEARS[0], STABLE_YEARS[-1])
    stab = rising_counts(lines)
    out = []
    for r_rep, r_st in zip(mine, stab):
        cut = r_st["cutoff"]
        rp = REPORT_LINES[cut]
        out.append({"cutoff": cut, "stable_lines": r_st["lines"], "stable_lines_share_of_dollars_pct": pct(l_net, l_all),
                    "stable_rising_pct": r_st["rising_pct"], "stable_rising_pct_after_shuffle": r_st["rising_pct_after_shuffle"],
                    "stable_falling_pct": r_st["falling_pct"], "stable_falling_pct_after_shuffle": r_st["falling_pct_after_shuffle"],
                    "report_lines_fy2012_fy2020": REPORT_LINE_COUNT, "report_rising_pct": rp[0],
                    "report_rising_pct_after_shuffle": rp[1], "report_falling_pct": rp[2],
                    "report_falling_pct_after_shuffle": rp[3], "recomputed_report_lines": r_rep["lines"],
                    "recomputed_report_rising_pct": r_rep["rising_pct"],
                    "recomputed_report_rising_pct_after_shuffle": r_rep["rising_pct_after_shuffle"],
                    "recomputed_report_lines_share_of_dollars_pct": pct(rep_net, rep_all)})
        print(f"  {out[-1]}", flush=True)
    write("p5_stable_lines_rising", out)
    bad = [r["cutoff"] for r in out if r["recomputed_report_lines"] != REPORT_LINE_COUNT
           or Decimal(str(r["recomputed_report_rising_pct"])) != r["report_rising_pct"]]
    if bad:
        raise SystemExit(f"CHECK FAILED: the line rules do not reproduce rising_counts.csv at cutoffs {bad}")
    print("part5: checks passed", flush=True)


# ============================================================================================ Part 6. Agency markets against government-wide markets

LEADER_YEAR = 2025
LEADER_SHARE = Decimal(50)

RULES |= {
    "code_hhi": "For each product code and year, HHI over vendor nets summed across every agency (government-wide) and "
                "across civilian agencies only (civilian-wide), under the proposed handling.",
    "levels": "Each year: the civilian share of dollars in agency segments with HHI above 2,500, against the share of "
              "civilian dollars in codes whose civilian-wide HHI is above 2,500.",
    "leaders": f"FY{LEADER_YEAR} civilian agency segments with HHI above 2,500 whose top vendor (largest net) holds "
               f"{LEADER_SHARE}% or more of the segment's net. Each is checked against the civilian-wide market for "
               "its code: whether the same vendor is the top vendor there, its civilian-wide share of net, and the "
               "civilian-wide HHI.",
}


@part
def part6() -> None:
    c = con()
    show_codes(c, "awarding_agency_code", limit=10)
    show_codes(c, "product_or_service_code", limit=10)
    setup(c)
    code_rows, levels, leaders = [], [], []
    for fy in years():
        rows, s = year_scores(c, fy)
        gov, civ = defaultdict(lambda: defaultdict(Decimal)), defaultdict(lambda: defaultdict(Decimal))
        segv = defaultdict(dict)
        for _, ag, psc, v, net in rows:
            gov[psc][v] += d(net)
            if ag != "097":
                civ[psc][v] += d(net)
                segv[(ag, psc)][v] = d(net)
        gs = score((fy, "", p, v, n, n) for p, vs_ in gov.items() for v, n in vs_.items())
        cs = score((fy, "", p, v, n, n) for p, vs_ in civ.items() for v, n in vs_.items())
        for p in sorted(gov, key=lambda x: x or ""):
            g, cc = gs[(fy, "", p)], cs.get((fy, "", p))
            code_rows.append({"fiscal_year": fy, "psc": p, "net_all": q(g[2]), "hhi_all": q(g[0], "0.1") if g[0] is not None else "",
                              "net_civilian": q(cc[2]) if cc else "", "hhi_civilian": q(cc[0], "0.1") if cc and cc[0] is not None else ""})
        civ_net = sum((v_[2] for k, v_ in s.items() if k[1] != "097"), Decimal(0))
        agency_above = sum((v_[2] for k, v_ in s.items() if k[1] != "097" and v_[0] is not None and v_[0] > 2500), Decimal(0))
        code_above = sum((v_[2] for v_ in cs.values() if v_[0] is not None and v_[0] > 2500), Decimal(0))
        levels.append({"fiscal_year": fy, "civilian_net": q(civ_net), "share_above_2500_agency_level_pct": pct(agency_above, civ_net),
                       "share_above_2500_civilian_wide_code_pct": pct(code_above, civ_net),
                       "difference_points": pct(agency_above, civ_net) - pct(code_above, civ_net)})
        if fy == LEADER_YEAR:
            for (ag, psc), vs_ in segv.items():
                h_, _, net = s[(fy, ag, psc)]
                if h_ is None or h_ <= 2500 or net <= 0:
                    continue
                v, vn = top_vendor(vs_)
                if vn * 100 / net < LEADER_SHARE:
                    continue
                cv, _ = top_vendor(civ[psc])
                ch, _, cn = cs[(fy, "", psc)]
                leaders.append({"agency_code": ag, "psc": psc, "segment_net": q(net), "segment_hhi": q(h_, "0.1"),
                                "top_vendor": v, "top_vendor_share_pct": pct(vn, net),
                                "leads_civilian_wide": "yes" if cv == v else "no", "civilian_wide_top_vendor": cv,
                                "vendor_civilian_wide_share_pct": pct(civ[psc][v], cn), "civilian_wide_net": q(cn),
                                "civilian_wide_hhi": q(ch, "0.1") if ch is not None else "unscored",
                                "agencies_buying_code": sum(1 for (a2, p2) in segv if p2 == psc)})
        print(f"  FY{fy}: {levels[-1]['share_above_2500_agency_level_pct']}% agency level, "
              f"{levels[-1]['share_above_2500_civilian_wide_code_pct']}% civilian-wide", flush=True)
    write("p6_code_hhi_government_wide", code_rows)
    write("p6_levels_by_year", levels)
    leaders.sort(key=lambda r: -d(r["segment_net"]))
    write("p6_leader_check_fy2025", leaders)
    yes = sum(1 for r in leaders if r["leads_civilian_wide"] == "yes")
    yes_net = sum((d(r["segment_net"]) for r in leaders if r["leads_civilian_wide"] == "yes"), Decimal(0))
    all_net = sum((d(r["segment_net"]) for r in leaders), Decimal(0))
    write("p6_leader_summary", [{"segments": len(leaders), "leaders_also_lead_civilian_wide": yes,
                                 "share_of_segments_pct": pct(yes, len(leaders)), "segment_net": q(all_net),
                                 "share_of_segment_dollars_pct": pct(yes_net, all_net),
                                 "single_agency_codes": sum(1 for r in leaders if r["agencies_buying_code"] == 1)}])
    print(f"  FY{LEADER_YEAR}: {yes} of {len(leaders)} leaders also lead the civilian-wide market "
          f"({pct(yes_net, all_net)}% of their dollars)", flush=True)
    print("part6: checks passed", flush=True)


# ============================================================================================ Part 7. Subcontracts, feasibility only

SUBAWARD_DIR = config.REPO_ROOT / ".tmp" / "subawards"
API = "https://api.usaspending.gov/api/v2"
SUBAWARD_FY = 2025
SUBAWARD_MAX_BYTES = 2 * 10**9
SUBAWARD_TOP = 20
SUBAWARD_REQUEST = {"filters": {"sub_award_types": ["procurement"], "date_type": "action_date",
                                "date_range": {"start_date": f"{SUBAWARD_FY - 1}-10-01", "end_date": f"{SUBAWARD_FY}-09-30"},
                                "agencies": [{"type": "awarding", "tier": "toptier", "name": "All"}]},
                    "file_format": "csv"}
DISCLOSURES = ("https://raw.githubusercontent.com/fedspendingtransparency/usaspending-website/"
               "86af01ba9ab403f2ed75f1d62a0dbcd35dbc4076/src/content/about-the-data/{}.mdx")

RULES |= {
    "subaward_source": f"The Award Data Archive listing (POST {API}/bulk_download/list_monthly_files/) for FY{SUBAWARD_FY} "
                       f"contracts, and the bulk download (POST {API}/bulk_download/awards/) with sub_award_types "
                       f"procurement and subaward action dates in FY{SUBAWARD_FY}, the request behind the Custom Award "
                       "Data Download page. The zip is saved in .tmp/subawards/, outside data/, and reused when present.",
    "subaward_limit": f"The run stops when the zip is larger than {SUBAWARD_MAX_BYTES:,} bytes.",
    "subaward_main": "The main example's subawards are the rows whose prime_award_unique_key is its award key. "
                     f"Reported: their count and summed subaward_amount, and the {SUBAWARD_TOP} largest subrecipients "
                     "(subawardee_uei, else the name) with their share of the subaward total and of the prime award's "
                     f"FY{SUBAWARD_FY} net.",
    "subaward_coverage": "For context: subaward rows, prime awards and summed subaward_amount by the prime award's "
                         "awarding agency.",
}


def http_json(url: str, body: dict | None = None) -> dict:
    import urllib.request
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def subaward_zip() -> tuple:
    """The FY2025 contract subaward zip in SUBAWARD_DIR, requested and downloaded when absent."""
    import urllib.request
    SUBAWARD_DIR.mkdir(parents=True, exist_ok=True)
    have = sorted(SUBAWARD_DIR.glob("All_Subawards_*.zip"))
    status_path = SUBAWARD_DIR / "status.json"
    if have and status_path.exists():
        return have[-1], json.loads(status_path.read_text(encoding="utf-8"))
    job = http_json(f"{API}/bulk_download/awards/", SUBAWARD_REQUEST)
    (SUBAWARD_DIR / "job.json").write_text(json.dumps(job, indent=1), encoding="utf-8")
    while True:
        st = http_json(job["status_url"])
        if st.get("status") in ("finished", "failed"):
            break
        time.sleep(30)
    status_path.write_text(json.dumps(st, indent=1), encoding="utf-8")
    if st["status"] != "finished":
        raise SystemExit(f"CHECK FAILED: the subaward download failed: {st}")
    if st.get("total_size") and st["total_size"] * 1000 > SUBAWARD_MAX_BYTES:
        raise SystemExit(f"STOP: the FY{SUBAWARD_FY} contract subaward file is {st['total_size'] * 1000:,.0f} bytes, over the limit")
    path = SUBAWARD_DIR / job["file_name"]
    req = urllib.request.Request(job["file_url"], headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=600) as r, open(f"{path}.part", "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    Path(f"{path}.part").rename(path)
    return path, st


def main_award(c: duckdb.DuckDBPyConnection) -> str | None:
    best = c.execute(f"""WITH k AS (SELECT DISTINCT contract_award_unique_key FROM {all_rows()}
                                    WHERE fy = ? AND awarding_agency_code = ? AND product_or_service_code = ?)
                         SELECT contract_award_unique_key FROM {all_rows()} SEMI JOIN k USING (contract_award_unique_key)
                         GROUP BY 1 HAVING COUNT(DISTINCT fy) >= ? ORDER BY SUM(amt) DESC, 1 LIMIT 1""",
                     [MAIN_FY, MAIN_AGENCY, MAIN_PSC, MAIN_MIN_YEARS]).fetchone()
    return best[0] if best else None


@part
def part7() -> None:
    import hashlib
    import zipfile
    archive = http_json(f"{API}/bulk_download/list_monthly_files/", {"agency": "all", "fiscal_year": SUBAWARD_FY, "type": "contracts"})
    print(f"  Award Data Archive, FY{SUBAWARD_FY} contracts: {[f['file_name'] for f in archive['monthly_files']]}", flush=True)
    path, st = subaward_zip()
    size = path.stat().st_size
    if size > SUBAWARD_MAX_BYTES:
        raise SystemExit(f"STOP: the FY{SUBAWARD_FY} contract subaward file is {size:,} bytes, over the limit")
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    with zipfile.ZipFile(path) as z:
        members = [(i.filename, i.file_size) for i in z.infolist()]
        out_dir = SUBAWARD_DIR / "unzipped"
        z.extractall(out_dir)
    print(f"  {path.name}: {size:,} bytes, SHA-256 {h.hexdigest()}, members {members}", flush=True)
    csvs = [str(out_dir / m) for m, _ in members if m.endswith(".csv")]
    c = con()
    c.execute(f"CREATE TEMP VIEW sub AS SELECT * FROM read_csv({csvs!r}, all_varchar = true, header = true)")
    cols = [r[0] for r in c.execute("DESCRIBE sub").fetchall()]
    need = ["prime_award_unique_key", "prime_award_awarding_agency_name", "subaward_amount", "subaward_action_date",
            "subawardee_uei", "subawardee_name", "subawardee_parent_name", "subaward_number"]
    missing = [x for x in need if x not in cols]
    if missing:
        raise SystemExit(f"CHECK FAILED: columns missing from the subaward file: {missing}")
    n, primes, total, d0, d1 = c.execute("""SELECT COUNT(*), COUNT(DISTINCT prime_award_unique_key), SUM(TRY_CAST(subaward_amount AS DECIMAL(38,2))),
                                                   MIN(subaward_action_date), MAX(subaward_action_date) FROM sub""").fetchone()
    main = main_award(c)
    prime_net = d(c.execute(f"SELECT SUM(amt) FROM {all_rows()} WHERE fy = ? AND contract_award_unique_key = ?",
                            [SUBAWARD_FY, main]).fetchone()[0])
    count_api = http_json(f"{API}/awards/count/subaward/{main}/").get("subawards")
    mine = c.execute("""SELECT COALESCE(NULLIF(trim(subawardee_uei), ''), subawardee_name) AS who, any_value(subawardee_name),
                               COUNT(*), SUM(TRY_CAST(subaward_amount AS DECIMAL(38,2))) FROM sub
                        WHERE prime_award_unique_key = ? GROUP BY 1 ORDER BY 4 DESC, 1""", [main]).fetchall()
    mine_total = sum((d(x[3]) for x in mine), Decimal(0))
    rows = [{"rank": i + 1, "subawardee": who, "subawardee_name": nm, "subawards": k, "amount": q(d(a)),
             "share_of_subaward_total_pct": pct(a, mine_total), f"share_of_prime_fy{SUBAWARD_FY}_net_pct": pct(a, prime_net)}
            for i, (who, nm, k, a) in enumerate(mine[:SUBAWARD_TOP])]
    fields = ["rank", "subawardee", "subawardee_name", "subawards", "amount", "share_of_subaward_total_pct",
              f"share_of_prime_fy{SUBAWARD_FY}_net_pct"]
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "p7_subawards_main_contract.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    write("p7_subaward_file", [{"source": "USAspending bulk download, sub_award_types procurement", "file": path.name,
                                "zip_bytes": size, "sha256": h.hexdigest(), "members": "; ".join(f"{m} ({b:,} bytes)" for m, b in members),
                                "columns": len(cols), "rows": n, "rows_reported_by_api": st.get("total_rows"),
                                "prime_awards": primes, "subaward_total": q(d(total)),
                                "first_action_date": d0, "last_action_date": d1, "data_dictionary_in_zip": "no",
                                "archive_fy2025_contract_files": "; ".join(f["file_name"] for f in archive["monthly_files"]),
                                "main_award": main, "main_award_subawards": sum(x[2] for x in mine),
                                "main_award_subaward_total": q(mine_total), "main_award_subawards_by_api_count": count_api,
                                f"main_award_fy{SUBAWARD_FY}_net": q(prime_net)}])
    write("p7_subawards_by_agency", [{"prime_awarding_agency": a, "subaward_rows": k, "prime_awards": p, "subaward_total": q(d(t)),
                                      "share_of_subaward_total_pct": pct(t, total)} for a, k, p, t in c.execute(
        """SELECT prime_award_awarding_agency_name, COUNT(*), COUNT(DISTINCT prime_award_unique_key), SUM(TRY_CAST(subaward_amount AS DECIMAL(38,2)))
           FROM sub GROUP BY 1 ORDER BY 4 DESC NULLS LAST""").fetchall()])
    print(f"  {n:,} subaward rows under {primes:,} prime awards, ${d(total):,.2f}, {d0} to {d1}", flush=True)
    print(f"  main award {main}: {sum(x[2] for x in mine)} subawards in the file, {count_api} by the API count", flush=True)
    if st.get("total_rows") is not None and int(st["total_rows"]) != n:
        raise SystemExit(f"CHECK FAILED: the file has {n} rows, the download status says {st['total_rows']}")
    for slug in ("reporting-threshold-for-subawards", "subaward-data-quality"):
        import urllib.request
        with urllib.request.urlopen(urllib.request.Request(DISCLOSURES.format(slug), headers={"User-Agent": "Mozilla/5.0"}), timeout=60) as r:
            (SUBAWARD_DIR / f"{slug}.mdx").write_bytes(r.read())
    print("part7: checks passed", flush=True)


# ============================================================================================ Part 8. Dates and money across modifications

TIMING = config.REPO_ROOT / ".tmp" / "timing"
SPAN_FILE = config.REPO_ROOT / ".tmp" / "p8_award_span.parquet"
TIMING_VERSION = "2"                            # bump to rebuild the row and award tables in .tmp/timing
TIMING_BUCKETS = 32
TIMING_COLUMNS = ["contract_transaction_unique_key", "contract_award_unique_key", "award_id_piid", "action_date",
                  "modification_number", "action_type_code", "action_type", "period_of_performance_start_date",
                  "period_of_performance_current_end_date", "period_of_performance_potential_end_date",
                  "awarding_agency_code", "product_or_service_code", "federal_action_obligation", "recipient_name",
                  "recipient_uei", "recipient_parent_uei"]
BASE_MOD = "0"
DATE_PROBE_YEARS = (2010, 2025)
OPTION_TYPES = ("EXERCISE AN OPTION",)
FUNDING_TYPES = ("FUNDING ONLY ACTION",)
SAMPLE_MAIN_PIID, SAMPLE_MAIN_AGENCY = "36C24220C0072", "036"
SAMPLE_MIN_YEARS, SAMPLE_MIN_ROWS = 3, 5
SAMPLE_TOP, SAMPLE_RANDOM = 10, 12
SAMPLE_MIN_NET = Decimal(1_000_000)
DATA_START = date(2007, 10, 1)
SPAN_BANDS = [("up to 366 days", 0, 366), ("367 to 731 days", 367, 731), ("732 to 1,826 days", 732, 1826),
              ("more than 1,826 days", 1827, None)]
WORK_BANDS = [("up to 1 year", 0, 366), ("1 to 2 years", 367, 731), ("2 to 5 years", 732, 1826), ("over 5 years", 1827, None)]
PEAK_BANDS = [("under 67%", None, 67), ("67% to 80%", 67, 80), ("80% and over", 80, None)]
BASE_BANDS = [("under 20%", None, 20), ("20% to 50%", 20, 50), ("50% to 80%", 50, 80), ("80% and over", 80, None)]
FUNDING_TOP_AGENCIES = 5
NO_SPAN_LIMIT = Decimal(10)

RULES |= {
    "timing_dates": f"A valid date is a text whose first 10 characters parse as YYYY-MM-DD with a year from {DATE_RANGE[0]} to "
                    f"{DATE_RANGE[1]} (DATE_RANGE from Part 1). Two dates are compared on those 10 characters, because "
                    "period_of_performance_potential_end_date is published in some rows with a time of 00:00:00 added.",
    "timing_base_row": f"The base row is a row with modification_number '{BASE_MOD}'. Every other row is a modification, "
                       "whatever its action type. Rows are read as recorded in Part 8 unless a column says proposed "
                       "handling, and the award tables take in every row of the award, 097 rows included.",
    "timing_order": "An award's rows are sorted as in trace_rows() of Part 1: action_date, then modification_number, then "
                    "the transaction key, all as text. The previous row and the earliest row come from this order. An "
                    "award's first row has no previous row and is never counted as differing from one.",
    "timing_covered_span": "A row's covered span runs from the later of its action date and its start date to its current "
                           "end date, both days included. It is invalid when the action date, the start date or the "
                           "current end date is invalid, or when the span would end before it starts.",
    "timing_sample": f"The main example (PIID {SAMPLE_MAIN_PIID}, agency {SAMPLE_MAIN_AGENCY}), the Emerson award, then the "
                     f"{SAMPLE_TOP} awards with a civilian row and the largest net as recorded, then {SAMPLE_RANDOM} drawn "
                     f"with random.Random({SEED}).sample from the remaining awards with a civilian row and net of at "
                     f"least ${SAMPLE_MIN_NET:,.0f}, sorted by award key before the draw. All must have rows in at least "
                     f"{SAMPLE_MIN_YEARS} fiscal years and at least {SAMPLE_MIN_ROWS} rows.",
    "timing_date_checks": "Six cases over every civilian row, by fiscal year. A case needing two dates counts only rows "
                          "where both are valid, other than the first case, which is the count of rows with either "
                          "date blank or invalid. Each case gets its rows, its net as recorded and its share of the "
                          "year's civilian rows and net.",
    "timing_action_groups": f"Funding groups by action_type name. Option exercises: {', '.join(OPTION_TYPES)}. Funding-only "
                            f"actions: {', '.join(FUNDING_TYPES)}. Every other modification is 'other', a blank "
                            "action type included. The names were read from the distinct values printed in step 1 over "
                            "all years, and no other spelling of either name appears.",
    "timing_funding": "For each award with a civilian row and a positive net as recorded over all years, the net of its "
                      "base rows, option exercises, funding-only actions and other modifications, each over the award's "
                      "net, and the count of its rows with a positive amount. An award with no base row has a base "
                      "share of zero and is also counted in its own column. An award belongs to the civilian agency with "
                      "the largest civilian net in it, ties to the lower code. The top agencies are the "
                      f"{FUNDING_TOP_AGENCIES} civilian agencies with the most civilian net as recorded over all years. "
                      "Per-award detail is too large to keep with the tables and stays in .tmp/timing/awards/.",
    "timing_award_span": "One row per award. Work starts on the earliest valid start date and ends on the latest valid "
                         "current end date among all its rows. The work length is the days between them, both days "
                         "included. There is no span when either is missing or the start falls after the end. Net by "
                         "fiscal year, peak year (largest net, ties to the earlier year) and peak share (peak year net "
                         "over net in all years) use the proposed handling, and the positive net test uses the same net. "
                         f"starts_before_data marks work starting before {DATA_START.isoformat()}. "
                         f"{SPAN_FILE.name} in .tmp/ holds awards with a civilian row and a positive net. "
                         ".tmp/timing/awards/ holds every award, because the report's lines include agency 097 and Part 9 "
                         "needs the same span for those awards.",
    "timing_bands": "Span and work length bands share the edges 366, 731 and 1,826 days, so 'up to 1 year' is up to 366 "
                    "days, '1 to 2 years' is 367 to 731, '2 to 5 years' is 732 to 1,826 and 'over 5 years' is more. A "
                    "percent band includes its lower edge and excludes its upper edge. Peak share and base share bands "
                    "are tested exactly, on the dollars.",
    "timing_no_span": "The share of civilian net over all years in awards with no usable span. 'no_row_with_both' is the "
                      "stated test: no row of the award has both a valid start date and a valid current end date. "
                      "'no_award_span' is the test the span itself applies: the award has no valid start date, no valid "
                      f"end date, or an earliest start after its latest end. The run stops above "
                      f"{NO_SPAN_LIMIT}% on any of the four figures (each test, as recorded and under the proposed handling).",
}


def valid_date(col: str) -> str:
    parsed = f"CAST(try_strptime(substr(trim({col}), 1, 10), '%Y-%m-%d') AS DATE)"
    return f"CASE WHEN year({parsed}) BETWEEN {DATE_RANGE[0]} AND {DATE_RANGE[1]} THEN {parsed} END"


def band_sql(col: str, bands: list[tuple]) -> str:
    whens = " ".join(f"WHEN {col} <= {hi} THEN '{name}'" for name, _, hi in bands[:-1])
    return f"CASE {whens} ELSE '{bands[-1][0]}' END"


def pct_band_sql(num: str, den: str, bands: list[tuple]) -> str:
    whens = " ".join(f"WHEN {num} * 100 < {den} * {hi} THEN '{name}'" for name, _, hi in bands[:-1])
    return f"CASE {whens} ELSE '{bands[-1][0]}' END"


def timing_build(c: duckdb.DuckDBPyConnection) -> None:
    """Build the row table and award table once: .tmp/timing/rows/b*.parquet and .tmp/timing/awards/b*.parquet."""
    done = TIMING / f"built_v{TIMING_VERSION}"
    if done.exists():
        print(f"row and award tables already built in {TIMING}", flush=True)
        return
    check_columns(TIMING_COLUMNS)
    pair = pair_net_sql(c)
    stage = TIMING / "stage"
    for sub in ("stage", "rows", "awards"):
        shutil.rmtree(TIMING / sub, ignore_errors=True)
        (TIMING / sub).mkdir(parents=True)
    for fy in years():
        t0 = time.time()
        c.execute(f"""COPY (SELECT *, {pair} AS amt_p, hash(contract_award_unique_key) % {TIMING_BUCKETS} AS b FROM (
                        SELECT {fy} AS fy, contract_transaction_unique_key, contract_award_unique_key,
                               awarding_agency_code AS ag, product_or_service_code AS psc, {VENDOR} AS v, {AMT} AS amt,
                               NOT list_contains({MINT_KEYS!r}, contract_transaction_unique_key) AND NOT COALESCE({MFA}, FALSE)
                                   AND {VENDOR} <> '(no ID)' AS kept,
                               action_date AS ad_raw, modification_number, trim(modification_number) = '{BASE_MOD}' AS base,
                               action_type_code, action_type,
                               substr(trim(period_of_performance_start_date), 1, 10) AS s_txt,
                               substr(trim(period_of_performance_current_end_date), 1, 10) AS e_txt,
                               substr(trim(period_of_performance_potential_end_date), 1, 10) AS p_txt,
                               {valid_date('action_date')} AS ad,
                               {valid_date('period_of_performance_start_date')} AS s,
                               {valid_date('period_of_performance_current_end_date')} AS e,
                               {valid_date('period_of_performance_potential_end_date')} AS p
                        FROM read_parquet({files(fy)!r})))
                      TO '{stage}/fy{fy}' (FORMAT parquet, PARTITION_BY (b), COMPRESSION zstd)""")
        print(f"  rows: FY{fy} read, {time.time() - t0:.0f} s", flush=True)
    fy_nets = ", ".join(f"SUM(amt_h) FILTER (WHERE fy = {fy}) AS net_fy{fy}" for fy in years())
    for i in range(TIMING_BUCKETS):
        t0 = time.time()
        order = "PARTITION BY contract_award_unique_key ORDER BY COALESCE(ad_raw, ''), COALESCE(modification_number, ''), contract_transaction_unique_key"
        c.execute(f"""CREATE OR REPLACE TEMP TABLE t AS
                      SELECT * EXCLUDE (amt_p), CASE WHEN kept THEN amt_p END AS amt_h,
                             ag IS DISTINCT FROM '097' AS civ,
                             row_number() OVER w AS rn,
                             s_txt IS DISTINCT FROM lag(s_txt) OVER w AND row_number() OVER w > 1 AS chg_s,
                             e_txt IS DISTINCT FROM lag(e_txt) OVER w AND row_number() OVER w > 1 AS chg_e,
                             p_txt IS DISTINCT FROM lag(p_txt) OVER w AND row_number() OVER w > 1 AS chg_p,
                             first_value(s) OVER w AS first_s,
                             CASE WHEN e >= ad AND e >= s THEN date_diff('day', greatest(ad, s), e) + 1 END AS covered_days
                      FROM read_parquet('{stage}/fy*/b={i}/*.parquet')
                      WINDOW w AS ({order})""")
        c.execute(f"COPY t TO '{TIMING}/rows/b{i}.parquet' (FORMAT parquet, COMPRESSION zstd)")
        kinds = (f"CASE WHEN base THEN 'base' WHEN action_type IN {OPTION_TYPES!r} THEN 'option' ".replace(",)", ")")
                 + f"WHEN action_type IN {FUNDING_TYPES!r} THEN 'funding' ELSE 'other' END".replace(",)", ")"))
        c.execute(f"""COPY (
            WITH a AS (SELECT contract_award_unique_key AS award, bool_or(civ) AS civilian, COUNT(*) AS n_rows, COUNT(DISTINCT fy) AS n_fy,
                              MIN(fy) AS first_fy, MAX(fy) AS last_fy, SUM(amt) AS net, COALESCE(SUM(amt_h), 0) AS net_h,
                              COALESCE(SUM(amt) FILTER (WHERE civ), 0) AS civ_net, COALESCE(SUM(amt_h) FILTER (WHERE civ), 0) AS civ_net_h,
                              bool_or(base) AS has_base, COALESCE(SUM(amt) FILTER (WHERE {kinds} = 'base'), 0) AS net_base,
                              COALESCE(SUM(amt) FILTER (WHERE {kinds} = 'option'), 0) AS net_option,
                              COALESCE(SUM(amt) FILTER (WHERE {kinds} = 'funding'), 0) AS net_funding,
                              COALESCE(SUM(amt) FILTER (WHERE {kinds} = 'other'), 0) AS net_other,
                              COUNT(*) FILTER (WHERE amt > 0) AS rows_adding_money,
                              MIN(s) AS work_start, MAX(e) AS work_end, bool_or(s IS NOT NULL AND e IS NOT NULL) AS row_with_both,
                              {fy_nets}
                       FROM t GROUP BY 1),
                 y AS (SELECT contract_award_unique_key AS award, fy, SUM(amt_h) AS n FROM t WHERE kept GROUP BY 1, 2),
                 pk AS (SELECT award, fy AS peak_fy, n AS peak_net FROM y QUALIFY row_number() OVER (PARTITION BY award ORDER BY n DESC, fy) = 1),
                 g AS (SELECT contract_award_unique_key AS award, ag, SUM(amt) AS n FROM t WHERE civ GROUP BY 1, 2),
                 m AS (SELECT award, ag AS main_agency FROM g QUALIFY row_number() OVER (PARTITION BY award ORDER BY n DESC NULLS LAST, ag NULLS LAST) = 1)
            SELECT a.*, peak_fy, peak_net, main_agency,
                   CASE WHEN work_start <= work_end THEN date_diff('day', work_start, work_end) + 1 END AS work_days,
                   work_start < DATE '{DATA_START.isoformat()}' AS starts_before_data
            FROM a LEFT JOIN pk USING (award) LEFT JOIN m USING (award))
            TO '{TIMING}/awards/b{i}.parquet' (FORMAT parquet, COMPRESSION zstd)""")
        print(f"  awards: bucket {i + 1} of {TIMING_BUCKETS}, {time.time() - t0:.0f} s", flush=True)
    c.execute("DROP TABLE t")
    shutil.rmtree(stage)
    done.write_text("built\n", encoding="utf-8")


def timing_views(c: duckdb.DuckDBPyConnection) -> None:
    timing_build(c)
    c.execute(f"CREATE OR REPLACE TEMP VIEW r AS SELECT * FROM read_parquet('{TIMING}/rows/b*.parquet')")
    c.execute(f"CREATE OR REPLACE TEMP VIEW aw AS SELECT * FROM read_parquet('{TIMING}/awards/b*.parquet')")


def part8_action_types(c: duckdb.DuckDBPyConnection) -> None:
    """Step 1: the printed values and the base row check."""
    for fy in DATE_PROBE_YEARS:
        print(f"  FY{fy} action_type_code, action_type, rows, net", flush=True)
        for code, name, n, net in c.execute(f"""SELECT action_type_code, action_type, COUNT(*), SUM(amt) FROM r WHERE fy = {fy}
                                                GROUP BY 1, 2 ORDER BY 3 DESC, 1, 2""").fetchall():
            print(f"    {code!r} {name!r}: {n:,} rows, net {q(net)}", flush=True)
        top = c.execute(f"SELECT modification_number, COUNT(*) FROM r WHERE fy = {fy} GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 20").fetchall()
        print(f"  FY{fy} top 20 modification_number: {top}", flush=True)
    names = [x for (x,) in c.execute("SELECT DISTINCT action_type FROM r ORDER BY 1").fetchall()]
    print(f"  action_type over all years: {names}", flush=True)
    close = [x for x in names if x and ("OPTION" in x or "FUNDING" in x) and x not in OPTION_TYPES + FUNDING_TYPES]
    if close:
        raise SystemExit(f"CHECK FAILED: other spellings of the funding groups: {close}")
    n, with_base, first_is_base = c.execute("""SELECT COUNT(*), COUNT(*) FILTER (WHERE has_base), NULL FROM aw""").fetchone()
    in_data = c.execute("SELECT COUNT(*), COUNT(*) FILTER (WHERE base) FROM r WHERE rn = 1").fetchone()
    many = c.execute("""SELECT COUNT(*) FROM (SELECT contract_award_unique_key FROM r WHERE base GROUP BY 1 HAVING COUNT(*) > 1)""").fetchone()[0]
    typed, blank_mod = c.execute("""SELECT COUNT(*) FILTER (WHERE base AND COALESCE(action_type, '') <> ''),
                                           COUNT(*) FILTER (WHERE NOT base AND COALESCE(action_type, '') = '') FROM r""").fetchone()
    print(f"  base rows: {with_base:,} of {n:,} awards ({pct(with_base, n)}%) have a row marked {BASE_MOD!r}. The earliest row is "
          f"marked {BASE_MOD!r} in {in_data[1]:,} of {in_data[0]:,}. {many:,} awards have more than one. Base rows with an action "
          f"type: {typed:,}. Modifications with a blank action type: {blank_mod:,}", flush=True)
    if with_base * 2 <= n:
        raise SystemExit(f"CHECK FAILED: the base row is marked {BASE_MOD!r} in only {pct(with_base, n)}% of awards")


def part8_sample(c: duckdb.DuckDBPyConnection) -> None:
    """Steps 2 and 3: the sample awards and their rows."""
    import random
    main = c.execute(f"SELECT DISTINCT contract_award_unique_key FROM {all_rows()} WHERE award_id_piid = ? AND awarding_agency_code = ?",
                     [SAMPLE_MAIN_PIID, SAMPLE_MAIN_AGENCY]).fetchall()
    if len(main) != 1:
        raise SystemExit(f"CHECK FAILED: PIID {SAMPLE_MAIN_PIID} is {len(main)} awards")
    fit = f"n_fy >= {SAMPLE_MIN_YEARS} AND n_rows >= {SAMPLE_MIN_ROWS}"
    picks = {main[0][0]: "main example traced in Part 1", EMERSON: "Emerson award traced in Part 1"}
    for k in picks:
        if not c.execute(f"SELECT COUNT(*) FROM aw WHERE award = ? AND {fit}", [k]).fetchone()[0]:
            raise SystemExit(f"CHECK FAILED: {k} does not meet the sample's minimum rows and years")
    for (k,) in c.execute(f"""SELECT award FROM aw WHERE civilian AND {fit} AND NOT list_contains(?, award)
                              ORDER BY net DESC, award LIMIT {SAMPLE_TOP}""", [list(picks)]).fetchall():
        picks[k] = f"top {SAMPLE_TOP} civilian net"
    pool = [k for (k,) in c.execute(f"""SELECT award FROM aw WHERE civilian AND {fit} AND net >= {SAMPLE_MIN_NET}
                                        AND NOT list_contains(?, award) ORDER BY award""", [list(picks)]).fetchall()]
    for k in random.Random(SEED).sample(pool, SAMPLE_RANDOM):
        picks[k] = f"random draw, net of at least ${SAMPLE_MIN_NET:,.0f}"
    print(f"  sample: {len(picks)} awards, {len(pool):,} in the random pool", flush=True)
    c.execute("CREATE OR REPLACE TEMP TABLE samp (award VARCHAR)")
    c.executemany("INSERT INTO samp VALUES (?)", [[k] for k in picks])
    names = defaultdict(set)
    for fy in years():
        for k, name in c.execute(f"""SELECT DISTINCT contract_award_unique_key, recipient_name FROM read_parquet({files(fy)!r})
                                     SEMI JOIN samp ON contract_award_unique_key = samp.award""").fetchall():
            names[k].add(name or "")
    info = c.execute("""SELECT contract_award_unique_key, string_agg(DISTINCT ag, '; ' ORDER BY ag), string_agg(DISTINCT psc, '; ' ORDER BY psc),
                               SUM(amt), MIN(fy), MAX(fy), COUNT(*) FROM r SEMI JOIN samp ON contract_award_unique_key = samp.award GROUP BY 1""").fetchall()
    by_key = {x[0]: x for x in info}
    write("p8_date_sample_awards", [{"award": k, "agency": by_key[k][1], "product_codes": by_key[k][2],
                                     "vendor_names": "; ".join(sorted(names[k])), "net": q(by_key[k][3]), "first_fy": by_key[k][4],
                                     "last_fy": by_key[k][5], "rows": by_key[k][6], "reason": why} for k, why in picks.items()])
    res = c.execute("""SELECT contract_award_unique_key, fy, ad_raw, modification_number, action_type, amt, s_txt, e_txt, p_txt,
                              chg_s, chg_e, chg_p, covered_days, contract_transaction_unique_key, rn
                       FROM r SEMI JOIN samp ON contract_award_unique_key = samp.award""").fetchall()
    rows = []
    groups = defaultdict(list)
    for x in res:
        groups[x[0]].append(x)
    for k in picks:
        g = sorted(groups[k], key=lambda x: (x[2] or "", x[3] or "", x[13]))
        total, run = sum((d(x[5]) for x in g), Decimal(0)), Decimal(0)
        yn = lambda flag, i: "" if i == 0 else ("yes" if flag else "no")
        for i, x in enumerate(g):
            if x[14] != i + 1:
                raise SystemExit(f"CHECK FAILED: row order in SQL and in Python differ for {k}")
            run += d(x[5])
            rows.append({"award": k, "fiscal_year": x[1], "action_date": x[2], "modification_number": x[3], "action_type": x[4],
                         "amount": q(x[5]), "running_net": q(run), "share_of_award_net_pct": pct(x[5], total), "start_date": x[6],
                         "current_end_date": x[7], "potential_end_date": x[8], "start_differs": yn(x[9], i), "current_end_differs": yn(x[10], i),
                         "potential_end_differs": yn(x[11], i), "covered_days": "" if x[12] is None else x[12]})
    write("p8_date_sample_rows", rows)
    for label, k in (("main", main[0][0]), ("emerson", EMERSON)):
        with open(OUT / f"p1_trace_{label}_rows.csv", newline="", encoding="utf-8") as f:
            traced = [(r["action_date"], r["modification_number"], r["running_net"]) for r in csv.DictReader(f)]
        mine = [(r["action_date"], r["modification_number"], str(r["running_net"])) for r in rows if r["award"] == k]
        if traced != mine:
            raise SystemExit(f"CHECK FAILED: the {label} sample rows differ from the Part 1 trace")
    print("  sample rows match the Part 1 traces, row by row", flush=True)


def part8_tables(c: duckdb.DuckDBPyConnection) -> None:
    """Steps 4 to 6."""
    cases = {"row_is_a_modification (context)": "NOT base",
             "start_or_current_end_blank_or_invalid": "s IS NULL OR e IS NULL",
             "start_after_current_end": "s > e",
             "modification_start_equals_earliest_row_start": "NOT base AND s = first_s",
             "start_over_366_days_before_action": "date_diff('day', s, ad) > 366",
             "current_end_before_action": "e < ad",
             "current_end_differs_from_previous_row": "chg_e"}
    sel = ", ".join(f"COUNT(*) FILTER (WHERE {w}), SUM(amt) FILTER (WHERE {w})" for w in cases.values())
    res = c.execute(f"SELECT fy, COUNT(*), SUM(amt), {sel} FROM r WHERE civ GROUP BY 1 ORDER BY 1").fetchall()
    rows, totals = [], defaultdict(lambda: [0, Decimal(0)])
    for x in res:
        for j, name in enumerate(cases):
            n, net = x[3 + 2 * j], d(x[4 + 2 * j] or 0)
            rows.append({"fiscal_year": x[0], "case": name, "rows": n, "net": q(net), "civilian_rows": x[1], "civilian_net": q(d(x[2])),
                         "rows_pct": pct(n, x[1]), "net_pct": pct(net, x[2])})
            totals[name][0] += n
            totals[name][1] += net
    all_rows_n, all_net = sum(x[1] for x in res), sum((d(x[2]) for x in res), Decimal(0))
    for name, (n, net) in totals.items():
        rows.append({"fiscal_year": "all", "case": name, "rows": n, "net": q(net), "civilian_rows": all_rows_n, "civilian_net": q(all_net),
                     "rows_pct": pct(n, all_rows_n), "net_pct": pct(net, all_net)})
        print(f"  {name}: {pct(n, all_rows_n)}% of rows, {pct(net, all_net)}% of net", flush=True)
    write("p8_date_checks_by_year", rows)
    kind = "CASE WHEN base THEN 'base row' ELSE 'modification' END"
    write("p8_money_by_action_type", [
        {"fiscal_year": a, "row_kind": b, "action_type": t, "rows": n, "positive": q(d(p or 0)), "negative": q(d(m or 0)), "net": q(d(x or 0)),
         "net_proposed_handling": q(d(h or 0))} for a, b, t, n, p, m, x, h in c.execute(
            f"""SELECT fy, {kind}, action_type, COUNT(*), SUM(amt) FILTER (WHERE amt > 0), SUM(amt) FILTER (WHERE amt < 0), SUM(amt), SUM(amt_h)
                FROM r WHERE civ GROUP BY 1, 2, 3 ORDER BY 1, 2, 7 DESC, 3""").fetchall()])
    span = f"CASE WHEN covered_days IS NULL THEN 'invalid' ELSE {band_sql('covered_days', SPAN_BANDS)} END"
    write("p8_row_spans", [
        {"fiscal_year": a, "row_kind": b, "action_type": t, "span_band": s_, "rows": n, "money": q(d(x))} for a, b, t, s_, n, x in c.execute(
            f"""SELECT fy, {kind}, action_type, {span}, COUNT(*), SUM(amt) FROM r WHERE civ AND amt > 0 GROUP BY 1, 2, 3, 4 ORDER BY 1, 2, 3, 4""").fetchall()])
    print("  date checks, money by action type and row spans written", flush=True)


def part8_awards(c: duckdb.DuckDBPyConnection) -> None:
    """Steps 7 to 9."""
    top = [x for (x,) in c.execute(f"""SELECT ag FROM r WHERE civ GROUP BY 1 ORDER BY SUM(amt) DESC LIMIT {FUNDING_TOP_AGENCIES}""").fetchall()]
    print(f"  top civilian agencies: {top}", flush=True)
    base_band = pct_band_sql("net_base", "net", BASE_BANDS)
    rows = []
    groups = [("all civilian agencies", "TRUE")] + [(ag, f"main_agency = '{ag}'") for ag in top]
    for label, where in groups:
        res = c.execute(f"""SELECT {base_band} AS band, COUNT(*), SUM(net), SUM(net_base), SUM(net_option), SUM(net_funding), SUM(net_other),
                                   AVG(rows_adding_money), MEDIAN(rows_adding_money), COUNT(*) FILTER (WHERE NOT has_base)
                            FROM aw WHERE civilian AND net > 0 AND {where} GROUP BY 1""").fetchall()
        by = {x[0]: x for x in res}
        n_all, net_all = sum(x[1] for x in res), sum((d(x[2]) for x in res), Decimal(0))
        for name, _, _ in BASE_BANDS:
            x = by.get(name, (name, 0, 0, 0, 0, 0, 0, None, None, 0))
            rows.append({"agency_group": label, "base_share_band": name, "awards": x[1], "awards_pct": pct(x[1], n_all), "net": q(d(x[2])),
                         "net_pct": pct(x[2], net_all), "base_share_of_net_pct": pct(x[3], x[2]), "option_share_of_net_pct": pct(x[4], x[2]),
                         "funding_only_share_of_net_pct": pct(x[5], x[2]), "other_mod_share_of_net_pct": pct(x[6], x[2]),
                         "mean_rows_adding_money": "" if x[7] is None else round(x[7], 2), "median_rows_adding_money": "" if x[8] is None else x[8],
                         "awards_with_no_base_row": x[9]})
    write("p8_award_funding_pattern", rows)
    for r in rows[:len(BASE_BANDS)]:
        print(f"  funding {r['base_share_band']}: {r['awards_pct']}% of awards, {r['net_pct']}% of net", flush=True)

    fy_cols = ", ".join(f"net_fy{fy}" for fy in years())
    c.execute(f"""COPY (SELECT award, net_h AS net, {fy_cols}, peak_fy, peak_net, peak_net / net_h AS peak_share, work_start, work_end, work_days,
                               starts_before_data, main_agency FROM aw WHERE civilian AND net_h > 0)
                  TO '{SPAN_FILE}' (FORMAT parquet, COMPRESSION zstd)""")
    work = f"CASE WHEN work_days IS NULL THEN 'no span' ELSE {band_sql('work_days', WORK_BANDS)} END"
    peak = pct_band_sql("peak_net", "net_h", PEAK_BANDS)
    res = c.execute(f"""SELECT {work}, {peak}, COUNT(*), SUM(net_h), COUNT(*) FILTER (WHERE starts_before_data),
                               SUM(net_h) FILTER (WHERE starts_before_data)
                        FROM aw WHERE civilian AND net_h > 0 GROUP BY 1, 2""").fetchall()
    by = {(x[0], x[1]): x for x in res}
    n_all, net_all = sum(x[2] for x in res), sum((d(x[3]) for x in res), Decimal(0))
    rows = []
    for w_ in [b[0] for b in WORK_BANDS] + ["no span"]:
        for p_ in [b[0] for b in PEAK_BANDS]:
            x = by.get((w_, p_), (w_, p_, 0, 0, 0, 0))
            rows.append({"work_length_band": w_, "peak_share_band": p_, "awards": x[2], "awards_pct": pct(x[2], n_all), "net": q(d(x[3])),
                         "net_pct": pct(x[3], net_all), "awards_starts_before_data": x[4], "net_starts_before_data": q(d(x[5] or 0))})
    write("p8_award_span_summary", rows)

    tot, tot_h = c.execute("SELECT SUM(civ_net), SUM(civ_net_h) FROM aw").fetchone()
    tests = {"no_row_with_both": "NOT row_with_both", "no_award_span": "work_days IS NULL"}
    rows = []
    for name, w_ in tests.items():
        n, a, b = c.execute(f"SELECT COUNT(*), SUM(civ_net), SUM(civ_net_h) FROM aw WHERE civilian AND ({w_})").fetchone()
        rows.append({"test": name, "awards": n, "civilian_net": q(d(a or 0)), "civilian_net_pct": pct(a or 0, tot),
                     "civilian_net_proposed_handling": q(d(b or 0)), "civilian_net_proposed_handling_pct": pct(b or 0, tot_h),
                     "civilian_net_all": q(d(tot)), "civilian_net_all_proposed_handling": q(d(tot_h))})
        print(f"  {name}: {n:,} awards, {rows[-1]['civilian_net_pct']}% of civilian net as recorded, "
              f"{rows[-1]['civilian_net_proposed_handling_pct']}% under the proposed handling", flush=True)
    write("p8_no_span_check", rows)
    high = [r for r in rows if max(r["civilian_net_pct"], r["civilian_net_proposed_handling_pct"]) > NO_SPAN_LIMIT]
    if high:
        raise SystemExit(f"CHECK FAILED: more than {NO_SPAN_LIMIT}% of civilian net has no usable span: {high}")


@part
def part8() -> None:
    check_columns(TIMING_COLUMNS)
    c = con()
    show_codes(c, "awarding_agency_code", limit=10)
    show_codes(c, "product_or_service_code", limit=10)
    show_codes(c, "action_type_code", limit=30)
    show_codes(c, "action_type", limit=30)
    timing_views(c)
    part8_action_types(c)
    part8_sample(c)
    part8_tables(c)
    part8_awards(c)
    print("part8: checks passed", flush=True)


# ============================================================================================ Part 9. Big jumps against money paid ahead

ROW_RULES = {"row_548": 548, "row_731": 731}
AWARD_RULES = {"award_548_80": (548, 80), "award_731_80": (731, 80), "award_548_67": (548, 67)}
ALL_RULES = tuple(ROW_RULES) + tuple(AWARD_RULES)
MAIN_ROW, MAIN_AWARD = "row_548", "award_548_80"
PROVISIONAL_FROM = 2023
JUMP_SIZES = (500, 1000, 2000)
JUMP_MAIN = 1000
CALM_BELOW = 250
STABLE_LINE_COUNT = 979
STABLE_CODES_CSV = OUT / "p5_stable_codes.csv"
LINE_SCOPES = {"all agencies": lambda ag: True, "civilian": lambda ag: ag != "097", "097": lambda ag: ag == "097"}

RULES |= {
    "paid_ahead_rows": "Part 9 reads rows under the proposed handling, with amt_h as their amount, and leaves out the rows that "
                       "handling leaves out.",
    "paid_ahead_row_rule": "A row with a positive amount pays ahead when its covered span is more than 548 days. Check: more "
                           "than 731 days. Rows with an invalid span count as unknown, whatever their sign.",
    "paid_ahead_award_rule": "An award is front-loaded when its net under the proposed handling is positive, its work length "
                             "is more than 548 days and its peak share is at least 80%. Every row of its peak year pays ahead, "
                             "whatever its sign. Checks: more than 731 days with at least 80%, and more than 548 days with at "
                             "least 67%. Rows of an award with no span count as unknown. Rows of an award with a span and a "
                             "net of zero or below have no peak share, are never front-loaded, and are counted as not judged.",
    "paid_ahead_all_agencies": "The report's lines and the stable lines include agency 097, as in the report, so both rules "
                               "are applied to all agencies with the same row and award tables. Part 8's span tables report "
                               "awards with a civilian row only. Tables by year are civilian, and the jump summary gives all "
                               "agencies and also civilian and 097 lines on their own.",
    "paid_ahead_provisional": f"Money paid ahead in FY{PROVISIONAL_FROM} or later is provisional. p9_paid_ahead_by_year marks those "
                              "years, p9_jumps marks jumps whose higher year is in them, and p9_jump_summary counts those "
                              "pairs and gives the shares without them.",
    "jump_pairs": f"For each line, every pair of back-to-back fiscal years with both years scored. A jump is a change in HHI of "
                  f"at least {JUMP_MAIN:,} points either way, with {JUMP_SIZES[0]} and {JUMP_SIZES[2]:,} as checks. A calm pair is a "
                  f"change of under {CALM_BELOW}.",
    "jump_mover": "The vendor whose share changed most between the two years, either way. A share is the vendor's net over the "
                  "summed net of the segment's vendors with a positive net, as hhi() computes it, and a vendor with no positive "
                  "net has no share. Only a vendor with a share in at least one of the two years can be the mover, so its net in "
                  "the higher year is always positive. Shares are compared exactly, in whole millionths of a dollar, and ties go to the lower vendor ID. The higher year is the year with the "
                  "mover's larger share, and an exact tie, which happens only when the shares do not change, goes to the later year.",
    "jump_timing_linked": "A pair is timing-linked under a rule when the mover's rows in that segment and higher year that the "
                          "rule flags sum to at least half of the mover's net there. The largest award is the one with the "
                          "largest net among those flagged rows, ties to the lower key.",
    "jump_weighted": "The weighted share is the segment net of the higher year in timing-linked pairs over the segment net of "
                     "the higher year in all the pairs of that group, with the segment net as score() gives it.",
}


def flag_select(i: int) -> str:
    """Bucket i's kept rows joined to their award, with the flags of every rule."""
    rows = [f"COALESCE(amt_h > 0 AND covered_days > {n}, FALSE) AS {name}" for name, n in ROW_RULES.items()]
    awards = [f"COALESCE(a.net_h > 0 AND a.work_days > {n} AND a.peak_net * 100 >= a.net_h * {p} AND r.fy = a.peak_fy, FALSE) AS {name}"
              for name, (n, p) in AWARD_RULES.items()]
    return f"""SELECT r.fy, r.ag, r.psc, r.v, r.civ, r.contract_award_unique_key AS award, r.amt_h, {', '.join(rows + awards)},
                      r.covered_days IS NULL AS unknown_row, a.work_days IS NULL AS unknown_award,
                      a.work_days IS NOT NULL AND a.net_h <= 0 AS not_judged, COALESCE(a.starts_before_data, FALSE) AS before_data
               FROM read_parquet('{TIMING}/rows/b{i}.parquet') r
               JOIN read_parquet('{TIMING}/awards/b{i}.parquet') a ON r.contract_award_unique_key = a.award WHERE r.kept"""


def build_cells(c: duckdb.DuckDBPyConnection) -> None:
    """The net each rule flags in each vendor x segment x year, one file per bucket (a cell can span buckets)."""
    cells = TIMING / "cells"
    shutil.rmtree(cells, ignore_errors=True)
    cells.mkdir(parents=True)
    sums = ", ".join(f"COALESCE(SUM(amt_h) FILTER (WHERE {x}), 0) AS {x}" for x in ALL_RULES)
    for i in range(TIMING_BUCKETS):
        c.execute(f"""COPY (SELECT fy, ag, psc, v, civ, SUM(amt_h) AS net, {sums},
                                   COALESCE(SUM(amt_h) FILTER (WHERE {MAIN_ROW} AND {MAIN_AWARD}), 0) AS both_main,
                                   COALESCE(SUM(amt_h) FILTER (WHERE {MAIN_ROW} AND NOT {MAIN_AWARD}), 0) AS only_row,
                                   COALESCE(SUM(amt_h) FILTER (WHERE {MAIN_AWARD} AND NOT {MAIN_ROW}), 0) AS only_award,
                                   COALESCE(SUM(amt_h) FILTER (WHERE unknown_row), 0) AS unknown_row,
                                   COALESCE(SUM(amt_h) FILTER (WHERE unknown_award), 0) AS unknown_award,
                                   COALESCE(SUM(amt_h) FILTER (WHERE not_judged), 0) AS not_judged,
                                   COALESCE(SUM(amt_h) FILTER (WHERE {MAIN_AWARD} AND before_data), 0) AS award_main_before_data
                            FROM ({flag_select(i)}) GROUP BY ALL) TO '{cells}/b{i}.parquet' (FORMAT parquet, COMPRESSION zstd)""")
        print(f"  flags: bucket {i + 1} of {TIMING_BUCKETS}", flush=True)
    c.execute(f"CREATE OR REPLACE TEMP VIEW cells AS SELECT * FROM read_parquet('{cells}/b*.parquet')")


def paid_ahead_by_year(c: duckdb.DuckDBPyConnection) -> None:
    cols = list(ALL_RULES) + ["both_main", "only_row", "only_award", "unknown_row", "unknown_award", "not_judged", "award_main_before_data"]
    res = c.execute(f"SELECT fy, SUM(net), {', '.join(f'SUM({x})' for x in cols)} FROM cells WHERE civ GROUP BY 1 ORDER BY 1").fetchall()
    vs_net = dict(c.execute(f"SELECT fy, SUM(net) FROM vs WHERE {CIV} GROUP BY 1").fetchall())
    rows = []
    for x in res:
        fy, net = x[0], d(x[1])
        if net != d(vs_net[fy]):
            raise SystemExit(f"CHECK FAILED: FY{fy} civilian net {net} in the flag table differs from {vs_net[fy]} in the vendor-segment table")
        v_ = dict(zip(cols, map(d, x[2:])))
        if v_["both_main"] + v_["only_row"] != v_[MAIN_ROW] or v_["both_main"] + v_["only_award"] != v_[MAIN_AWARD]:
            raise SystemExit(f"CHECK FAILED: FY{fy} both and only do not add up to the two main rules")
        for rule in ALL_RULES:
            main = rule in (MAIN_ROW, MAIN_AWARD)
            unk = v_["unknown_row"] if rule in ROW_RULES else v_["unknown_award"]
            rows.append({"fiscal_year": fy, "rule": rule, "main_rule": "yes" if main else "no", "provisional": "yes" if fy >= PROVISIONAL_FROM else "no",
                         "civilian_net": q(net), "net_paid_ahead": q(v_[rule]), "paid_ahead_pct": pct(v_[rule], net),
                         "net_unknown": q(unk), "unknown_pct": pct(unk, net),
                         "net_not_judged": q(v_["not_judged"]) if rule in AWARD_RULES else "",
                         "net_both_main_rules": q(v_["both_main"]) if main else "", "net_only_row_rule": q(v_["only_row"]) if main else "",
                         "net_only_award_rule": q(v_["only_award"]) if main else "",
                         "award_rule_net_in_awards_starting_before_data": q(v_["award_main_before_data"]) if rule == MAIN_AWARD else ""})
    write("p9_paid_ahead_by_year", rows)
    print(f"  paid ahead by year written: {len(res)} years", flush=True)


def line_cells(c: duckdb.DuckDBPyConnection, lines: list[list[tuple]], line_keys: list[tuple]):
    """Yield (line index, {fy: {vendor: net}}) for each line, over its scored years, in line order."""
    c.execute("CREATE OR REPLACE TEMP TABLE lk (i INTEGER, ag VARCHAR, psc VARCHAR, fy INTEGER)")
    c.executemany("INSERT INTO lk VALUES (?, ?, ?, ?)", [[i, *line_keys[i], x[0]] for i, v in enumerate(lines) for x in v])
    res = c.execute("""SELECT lk.i, vs.fy, vs.v, vs.net FROM vs JOIN lk ON vs.fy = lk.fy AND vs.ag IS NOT DISTINCT FROM lk.ag
                       AND vs.psc IS NOT DISTINCT FROM lk.psc ORDER BY lk.i""")
    cur, nets = None, defaultdict(dict)
    while True:
        batch = res.fetchmany(200_000)
        if not batch:
            break
        for i, fy, v_, net in batch:
            if i != cur:
                if cur is not None:
                    yield cur, nets
                cur, nets = i, defaultdict(dict)
            nets[fy][v_] = d(net)
    if cur is not None:
        yield cur, nets


def line_keys_of(scores: dict[tuple, tuple], lines: list[list[tuple]], codes: set | None, first: int, last: int) -> list[tuple]:
    """Each line's (agency, code), since line_set() returns the lines without them. Walks the same keys in the same order."""
    s = defaultdict(list)
    for (fy, ag, psc), (h_, _, net) in scores.items():
        if h_ is not None and first <= fy <= last and (codes is None or psc in codes):
            s[(ag, psc)].append((fy, float(h_), net))
    order = iter(sorted(s, key=lambda k: tuple((x is None, x or "") for x in k)))
    keys = []
    for v in lines:
        for k in order:
            if sorted(s[k]) == v:
                keys.append(k)
                break
        else:
            raise SystemExit("CHECK FAILED: a line could not be matched to its agency and code")
    return keys


def find_pairs(c: duckdb.DuckDBPyConnection, lines: list[list[tuple]], keys: list[tuple]) -> list[dict]:
    """Every calm pair and every jump of the smallest size, each with its mover."""
    pairs = []
    for i, nets in line_cells(c, lines, keys):
        scored = {x[0]: x for x in lines[i]}
        for fy in sorted(scored):
            if fy + 1 not in scored:
                continue
            h1, h2 = scored[fy][1], scored[fy + 1][1]
            change = abs(h2 - h1)
            if not (change < CALM_BELOW or change >= JUMP_SIZES[0]):
                continue
            a, b = nets[fy], nets[fy + 1]
            # Whole millionths, so that shares and exact ties are compared with no rounding. A two-vendor segment ties often.
            ia = {k: int(x.scaleb(6)) for k, x in a.items() if x > 0}
            ib = {k: int(x.scaleb(6)) for k, x in b.items() if x > 0}
            ta, tb = sum(ia.values()), sum(ib.values())
            best, best_gap = None, -1
            for k in sorted(set(ia) | set(ib)):
                gap = abs(ib.get(k, 0) * ta - ia.get(k, 0) * tb)      # the share change x ta x tb
                if gap > best_gap:
                    best, best_gap = k, gap
            s1, s2 = Decimal(ia.get(best, 0)) / ta, Decimal(ib.get(best, 0)) / tb
            high = fy if ia.get(best, 0) * tb > ib.get(best, 0) * ta else fy + 1
            pairs.append({"ag": keys[i][0], "psc": keys[i][1], "fy1": fy, "fy2": fy + 1, "h1": h1, "h2": h2, "change": change, "mover": best,
                          "s1": s1, "s2": s2, "high": high, "mover_net": (a if high == fy else b)[best], "seg_net": scored[high][2]})
    return pairs


def attach_flags(c: duckdb.DuckDBPyConnection, pairs: list[dict]) -> None:
    """Add to each pair the part of the mover's net that each rule flags, and whether that makes it timing-linked."""
    c.execute("CREATE OR REPLACE TEMP TABLE mv (fy INTEGER, ag VARCHAR, psc VARCHAR, v VARCHAR)")
    c.executemany("INSERT INTO mv VALUES (?, ?, ?, ?)", [list(x) for x in {(p["high"], p["ag"], p["psc"], p["mover"]) for p in pairs}])
    sums = ", ".join(f"SUM(c.{x})" for x in ALL_RULES)
    found = {tuple(x[:4]): x[4:] for x in c.execute(f"""SELECT c.fy, c.ag, c.psc, c.v, SUM(c.net), {sums} FROM cells c
        JOIN mv ON c.fy = mv.fy AND c.v = mv.v AND c.ag IS NOT DISTINCT FROM mv.ag AND c.psc IS NOT DISTINCT FROM mv.psc GROUP BY 1, 2, 3, 4""").fetchall()}
    for p in pairs:
        x = found[(p["high"], p["ag"], p["psc"], p["mover"])]
        if d(x[0]) != p["mover_net"]:
            raise SystemExit(f"CHECK FAILED: mover net differs between tables for {p}")
        for rule, part_ in zip(ALL_RULES, x[1:]):
            p[rule] = d(part_)
            p[f"{rule}_linked"] = 2 * d(part_) >= p["mover_net"]


def largest_awards(c: duckdb.DuckDBPyConnection, jumps: list[dict]) -> dict:
    """{(fy, ag, psc, mover, rule): (award, net)} for the mover's largest award behind the paid-ahead part."""
    c.execute("CREATE OR REPLACE TEMP TABLE mv (fy INTEGER, ag VARCHAR, psc VARCHAR, v VARCHAR)")
    c.executemany("INSERT INTO mv VALUES (?, ?, ?, ?)", [list(x) for x in {(p["high"], p["ag"], p["psc"], p["mover"]) for p in jumps}])
    best: dict = {}
    for i in range(TIMING_BUCKETS):
        for rule in (MAIN_ROW, MAIN_AWARD):
            for fy, ag, psc, v_, award, net in c.execute(f"""SELECT f.fy, f.ag, f.psc, f.v, f.award, SUM(f.amt_h) FROM ({flag_select(i)}) f
                    JOIN mv ON f.fy = mv.fy AND f.v = mv.v AND f.ag IS NOT DISTINCT FROM mv.ag AND f.psc IS NOT DISTINCT FROM mv.psc
                    WHERE f.{rule} GROUP BY 1, 2, 3, 4, 5""").fetchall():
                k, net = (fy, ag, psc, v_, rule), d(net)
                if k not in best or net > best[k][1] or (net == best[k][1] and award < best[k][0]):
                    best[k] = (award, net)
    return best


def share_linked(group: list[dict], rule: str) -> tuple:
    n = sum(1 for p in group if p[f"{rule}_linked"])
    w_all = sum((p["seg_net"] for p in group), Decimal(0))
    w = sum((p["seg_net"] for p in group if p[f"{rule}_linked"]), Decimal(0))
    return pct(n, len(group)), pct(w, w_all)


def jump_tables(c: duckdb.DuckDBPyConnection, label: str, lines: list[list[tuple]], keys: list[tuple]) -> tuple[list[dict], list[dict]]:
    pairs = find_pairs(c, lines, keys)
    attach_flags(c, pairs)
    print(f"  {label}: {len(pairs):,} calm or jump pairs. Negative segment nets among them: "
          f"{sum(1 for p in pairs if p['seg_net'] < 0):,}", flush=True)
    with open(TIMING / f"p9_pairs_{label.replace(' ', '_').replace(chr(39), '')}.csv", "w", newline="", encoding="utf-8") as f:
        fields = ["ag", "psc", "fy1", "fy2", "h1", "h2", "change", "mover", "s1", "s2", "high", "mover_net", "seg_net", *ALL_RULES]
        w_ = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w_.writeheader()
        w_.writerows(pairs)
    jumps = [p for p in pairs if p["change"] >= JUMP_MAIN]
    big = largest_awards(c, jumps)
    jump_rows = []
    for p in jumps:
        row = {"line_set": label, "agency": p["ag"], "product_code": p["psc"], "fy_first": p["fy1"], "fy_second": p["fy2"],
               "hhi_first": round(p["h1"], 1), "hhi_second": round(p["h2"], 1), "mover": p["mover"], "mover_share_first": q(p["s1"], "0.0001"),
               "mover_share_second": q(p["s2"], "0.0001"), "higher_year": p["high"], "mover_net_higher_year": q(p["mover_net"]),
               "segment_net_higher_year": q(p["seg_net"]), "provisional": "yes" if p["high"] >= PROVISIONAL_FROM else "no"}
        for rule in (MAIN_ROW, MAIN_AWARD):
            award, net = big.get((p["high"], p["ag"], p["psc"], p["mover"], rule), ("", ""))
            row |= {f"{rule}_paid_ahead": q(p[rule]), f"{rule}_timing_linked": "yes" if p[f"{rule}_linked"] else "no",
                    f"{rule}_largest_award": award, f"{rule}_largest_award_net": q(net)}
        jump_rows.append(row)
    summary = []
    for scope, keep in LINE_SCOPES.items():
        mine = [p for p in pairs if keep(p["ag"])]
        calm = [p for p in mine if p["change"] < CALM_BELOW]
        for size in JUMP_SIZES:
            group = [p for p in mine if p["change"] >= size]
            for rule in ALL_RULES:
                a, aw_ = share_linked(group, rule)
                b, bw = share_linked(calm, rule)
                g2 = [p for p in group if p["high"] < PROVISIONAL_FROM]
                c2 = [p for p in calm if p["high"] < PROVISIONAL_FROM]
                summary.append({"line_set": label, "agencies": scope, "jump_size": size, "rule": rule, "main_rule": "yes" if rule in (MAIN_ROW, MAIN_AWARD) else "no",
                                "jumps": len(group), "jumps_timing_linked_pct": a, "calm_pairs": len(calm), "calm_timing_linked_pct": b,
                                "jumps_timing_linked_pct_by_dollars": aw_, "calm_timing_linked_pct_by_dollars": bw,
                                "jumps_provisional": len(group) - len(g2), "calm_pairs_provisional": len(calm) - len(c2),
                                "jumps_timing_linked_pct_without_provisional": share_linked(g2, rule)[0],
                                "calm_timing_linked_pct_without_provisional": share_linked(c2, rule)[0]})
    return jump_rows, summary


def report_and_stable_lines(c: duckdb.DuckDBPyConnection) -> tuple[dict, tuple, tuple]:
    """The scores of every year, then each line set as (lines, keys), with the line counts checked."""
    scores = {}
    for fy in years():
        scores |= year_scores(c, fy)[1]
        print(f"  scored FY{fy}", flush=True)
    with open(STABLE_CODES_CSV, newline="", encoding="utf-8") as f:
        stable = {r["psc"] for r in csv.DictReader(f)}
    rep = line_set(scores, None, *REPORT_WINDOW)[0]
    st = line_set(scores, stable, STABLE_YEARS[0], STABLE_YEARS[-1])[0]
    print(f"  report's lines: {len(rep):,}, stable lines: {len(st):,}", flush=True)
    if len(rep) != REPORT_LINE_COUNT or len(st) != STABLE_LINE_COUNT:
        raise SystemExit(f"CHECK FAILED: line counts {len(rep)} and {len(st)}, expected {REPORT_LINE_COUNT} and {STABLE_LINE_COUNT}")
    return (scores, (rep, line_keys_of(scores, rep, None, *REPORT_WINDOW)),
            (st, line_keys_of(scores, st, stable, STABLE_YEARS[0], STABLE_YEARS[-1])))


@part
def part9() -> None:
    c = con()
    show_codes(c, "awarding_agency_code", limit=10)
    show_codes(c, "product_or_service_code", limit=10)
    setup(c)
    timing_views(c)
    build_cells(c)
    paid_ahead_by_year(c)
    _, rep, st = report_and_stable_lines(c)
    jumps, summary = [], []
    for label, (lines, keys) in (("report's lines", rep), ("stable lines", st)):
        a, b = jump_tables(c, label, lines, keys)
        jumps += a
        summary += b
    write("p9_jumps", jumps)
    write("p9_jump_summary", summary)
    for r in summary:
        if r["jump_size"] == JUMP_MAIN and r["main_rule"] == "yes":
            print(f"  {r['line_set']}, {r['agencies']}, {r['rule']}: {r['jumps']:,} jumps, {r['jumps_timing_linked_pct']}% linked, "
                  f"calm {r['calm_timing_linked_pct']}%, by dollars {r['jumps_timing_linked_pct_by_dollars']}% against "
                  f"{r['calm_timing_linked_pct_by_dollars']}%", flush=True)
    print("part9: checks passed", flush=True)


# ============================================================================================ Part 10. Pooled three-year scores

POOL_YEARS = 3
POOL_ERAS = ((2008, 2011), (2012, 2020), (2021, 2025))
POOL_REPORT_CUTOFF = 500
YEARLY_SHARE_CSV = OUT / "p5_stable_share_by_year.csv"
POOL_THRESHOLD = 2500

RULES |= {
    "pooled_endpoints": f"For each line, each vendor's net over the line's first {POOL_YEARS} scored years is summed and the total "
                        f"is scored once with hhi(), and the same for its last {POOL_YEARS} scored years. A line is rising when the "
                        "last pool scores at least the cutoff above the first, and falling in the mirror case. A pool in which no "
                        "vendor has a positive total has no score, and its line is neither rising nor falling. The count of "
                        "those lines is in the table.",
    "pooled_shuffle": f"One random.Random({SEED}) for each line set, used in the order rising_counts() uses it: for each cutoff, "
                      f"{SHUFFLES} rounds, and in each round every line in the order line_set() returns them. Each line's scored "
                      "years are shuffled, then the first and last three shuffled years are pooled. The averaged method "
                      "uses the same shuffled years through classify(), and its counts must equal rising_counts().",
    "pooled_dollars": "A line's dollars are its segment nets over its scored years. The dollar share of a result is the "
                      "dollars of the lines with that result over the dollars of all lines in the set. Shuffled shares are "
                      "the average over the rounds.",
    "pooled_share": f"Inside each code era ({', '.join(f'FY{a} to FY{b}' for a, b in POOL_ERAS)}), each civilian agency x code is pooled "
                    f"over {POOL_YEARS} back-to-back fiscal years and labeled by the last. The share is the net of pools with a score above "
                    f"{POOL_THRESHOLD:,} over the net of all pools with that label. The first two years of each era have no pool and "
                    "stay blank. The yearly share is share_above_2500_all_codes_pct in p5_stable_share_by_year.csv.",
}


def pooled_score(nets: dict, fys, cache: dict) -> Decimal | None:
    key = tuple(sorted(fys))
    if key not in cache:
        total: dict = defaultdict(Decimal)
        for fy in key:
            for v_, n in nets[fy].items():
                total[v_] += n
        cache[key] = hhi(list(total.values())) if any(x > 0 for x in total.values()) else None
    return cache[key]


def pooled_class(first: Decimal | None, last: Decimal | None, cutoff: int) -> str:
    if first is None or last is None:
        return "neither"
    return "rising" if last - first >= cutoff else "falling" if first - last >= cutoff else "neither"


def pooled_lines(c: duckdb.DuckDBPyConnection, label: str, lines: list[list[tuple]], keys: list[tuple]) -> list[dict]:
    rng = random.Random(SEED)
    orders: list[list[tuple]] = [[] for _ in lines]
    for cut in CUTOFFS:                                # the same draws, in the same order, as rising_counts()
        for _ in range(SHUFFLES):
            for i, v in enumerate(lines):
                fys = [x[0] for x in v]
                rng.shuffle(fys)
                orders[i].append((cut, fys))
    dollars = [sum((x[2] for x in v), Decimal(0)) for v in lines]
    all_dollars = sum(dollars, Decimal(0))
    seen = {(m, kind, cut): defaultdict(int) for m in ("averaged", "pooled") for kind in ("observed", "shuffled") for cut in CUTOFFS}
    money = {(m, kind, cut): defaultdict(Decimal) for m in ("averaged", "pooled") for kind in ("observed", "shuffled") for cut in CUTOFFS}
    unscored = 0
    done = 0
    for i, nets in line_cells(c, lines, keys):
        v = lines[i]
        h_by_year = {x[0]: x[1] for x in v}
        fys = [x[0] for x in v]
        cache: dict = {}
        first, last = pooled_score(nets, fys[:POOL_YEARS], cache), pooled_score(nets, fys[-POOL_YEARS:], cache)
        unscored += first is None or last is None
        for cut in CUTOFFS:
            for m, res in (("averaged", classify([x[1] for x in v], cut)), ("pooled", pooled_class(first, last, cut))):
                seen[(m, "observed", cut)][res] += 1
                money[(m, "observed", cut)][res] += dollars[i]
        for cut, order in orders[i]:
            res_a = classify([h_by_year[fy] for fy in order], cut)
            res_p = pooled_class(pooled_score(nets, order[:POOL_YEARS], cache), pooled_score(nets, order[-POOL_YEARS:], cache), cut)
            for m, res in (("averaged", res_a), ("pooled", res_p)):
                seen[(m, "shuffled", cut)][res] += 1
                money[(m, "shuffled", cut)][res] += dollars[i]
        done += 1
        if done % 1000 == 0:
            print(f"  {label}: {done:,} of {len(lines):,} lines", flush=True)
    n = len(lines)
    rows = []
    for cut in CUTOFFS:
        for m in ("averaged", "pooled"):
            row = {"line_set": label, "cutoff": cut, "method": m, "lines": n, "lines_with_an_unscored_pool": unscored if m == "pooled" else 0}
            for res in ("rising", "falling"):
                row[f"{res}_pct"] = round(100 * seen[(m, "observed", cut)][res] / n, 2)
                row[f"{res}_pct_after_shuffle"] = round(100 * seen[(m, "shuffled", cut)][res] / (n * SHUFFLES), 2)
            for res in ("rising", "falling"):
                row[f"{res}_pct_by_dollars"] = pct(money[(m, "observed", cut)][res], all_dollars)
                row[f"{res}_pct_after_shuffle_by_dollars"] = pct(money[(m, "shuffled", cut)][res] / SHUFFLES, all_dollars)
            rows.append(row)
    want = {r["cutoff"]: r for r in rising_counts(lines)}
    for row in rows:
        if row["method"] == "averaged":
            r = want[row["cutoff"]]
            got = (row["rising_pct"], row["rising_pct_after_shuffle"], row["falling_pct"], row["falling_pct_after_shuffle"])
            if got != (r["rising_pct"], r["rising_pct_after_shuffle"], r["falling_pct"], r["falling_pct_after_shuffle"]):
                raise SystemExit(f"CHECK FAILED: {label} averaged results at {row['cutoff']} differ from rising_counts(): {got}, {r}")
    print(f"  {label}: {unscored} lines with an unscored pool, averaged counts equal rising_counts()", flush=True)
    return rows


def pooled_share(c: duckdb.DuckDBPyConnection) -> None:
    with open(YEARLY_SHARE_CSV, newline="", encoding="utf-8") as f:
        yearly = {int(r["fiscal_year"]): r["share_above_2500_all_codes_pct"] for r in csv.DictReader(f)}
    rows = []
    for first, last in POOL_ERAS:
        for y in range(first, last + 1):
            row = {"fiscal_year": y, "code_era": f"FY{first} to FY{last}", "yearly_share_above_2500_pct": yearly[y], "pooled_first_year": "",
                   "pooled_net": "", "pooled_share_above_2500_pct": ""}
            if y >= first + POOL_YEARS - 1:
                got = c.execute(f"SELECT ag, psc, v, SUM(net) FROM vs WHERE {CIV} AND fy BETWEEN ? AND ? GROUP BY ALL", [y - POOL_YEARS + 1, y]).fetchall()
                s = score((y, ag, psc, v_, n, n) for ag, psc, v_, n in got)
                net = sum((x[2] for x in s.values()), Decimal(0))
                above = sum((x[2] for x in s.values() if x[0] is not None and x[0] > POOL_THRESHOLD), Decimal(0))
                row |= {"pooled_first_year": y - POOL_YEARS + 1, "pooled_net": q(net), "pooled_share_above_2500_pct": pct(above, net)}
            rows.append(row)
            print(f"  FY{y}: yearly {row['yearly_share_above_2500_pct']}, pooled {row['pooled_share_above_2500_pct']}", flush=True)
    write("p10_pooled_share_by_year", rows)


@part
def part10() -> None:
    c = con()
    show_codes(c, "awarding_agency_code", limit=10)
    show_codes(c, "product_or_service_code", limit=10)
    setup(c)
    _, rep, st = report_and_stable_lines(c)
    want = REPORT_LINES[POOL_REPORT_CUTOFF]
    got = next(r for r in rising_counts(rep[0]) if r["cutoff"] == POOL_REPORT_CUTOFF)
    print(f"  report at {POOL_REPORT_CUTOFF}: {got}", flush=True)
    if Decimal(str(got["rising_pct"])) != want[0] or Decimal(str(got["rising_pct_after_shuffle"])) != want[1]:
        raise SystemExit(f"CHECK FAILED: rising_counts() gives {got}, the report has {want}")
    rows = []
    for label, (lines, keys) in (("report's lines", rep), ("stable lines", st)):
        rows += pooled_lines(c, label, lines, keys)
    write("p10_pooled_rising", rows)
    for r in rows:
        print(f"  {r}", flush=True)
    pooled_share(c)
    print("part10: checks passed", flush=True)


# ============================================================================================ Part 11. Spread each contract evenly

SPREAD = config.REPO_ROOT / ".tmp" / "spread"
SPREAD_RULES = ("S1", "S2", "S3", "S4")
SPREAD_ALL = ("baseline",) + SPREAD_RULES
SPREAD_YEARS = (2008, 2025)
DATA_END = date(2025, 9, 30)
TOTAL_TOLERANCE = Decimal(1)
SHARE_TOLERANCE = 1e-9
SPREAD_TOP = 5
SPREAD_EXAMPLES = (("36C24220C0072", "036"), ("HSHQDC11C00083", "070"))
ABSTRACT_AVERAGES = ((2012, 2014), (2018, 2020), (2021, 2025))
R_NO_SPAN, R_BEFORE, R_AFTER, R_BOTH, R_NOT_FRONT = ("no span", "started before the data", "still running after FY2025",
                                                     "started before the data and still running", "not front-loaded")
SPREAD_REASONS = (R_NO_SPAN, R_BEFORE, R_AFTER, R_BOTH, R_NOT_FRONT)

RULES |= {
    "award_part": "An award part is an award's rows in one awarding agency and one product code, under the proposed handling. "
                  "Its net is the sum of those amounts over all years.",
    "main_vendor": "The vendor with the largest net on the award over all years under the proposed handling, ties to the lower "
                   "vendor ID. Every award part counts under its award's main vendor, in the baseline and in every spread.",
    "spread_baseline": "Each award part's net stays in the fiscal years its rows fall in and counts under the main vendor.",
    "spread_awards": "Spans come from .tmp/timing/awards/, the Part 8 span of every award. SPAN_FILE holds the same span for awards "
                     "with a civilian row and a positive net only, and the run stops if the two disagree. Every award is spread, "
                     "because the report's lines include agency 097 and an award with a net of zero or below still has a span.",
    "spread_method": "A spread award part gives each fiscal year its net x the span's days in that year / the span's days, both "
                     "days included, computed by fiscal-year overlap and kept to 6 decimals.",
    "spread_s1": f"S1. Each award part is spread over its award's span when the span starts on or after {DATA_START.isoformat()} and "
                 f"ends on or before {DATA_END.isoformat()}. Every other award part stays as recorded.",
    "spread_s2": "S2. As S1, but the span ends on the award's latest valid potential end date over all its rows, or on its latest "
                 "valid current end date when no row has a valid potential end. The later window test uses this end. An end before "
                 "the start means no span.",
    "spread_s3": "S3. Every award with a span is spread over its full span, whatever its dates. Money landing outside FY2008 to "
                 "FY2025 drops out and is reported.",
    "spread_s4": f"S4. As S1, but only awards that {MAIN_AWARD} calls front-loaded are spread. A front-loaded award outside the S1 "
                 "window stays as recorded, under its S1 reason.",
    "spread_reasons": "A part left as recorded has one reason, tested in this order: "
                      f"{', '.join(SPREAD_REASONS)}. The fourth reason exists so the columns add up, since an award can be both of the two before it.",
    "spread_moved": "For each spread award part and fiscal year, the spread amount minus the baseline amount. The money moved out of "
                    "a year sums the falls, and the money moved into a year sums the rises. All money landing outside FY2008 to FY2025, "
                    "positive and negative, is the money dropping out.",
    "spread_multi_vendor": "An award has more than one vendor ID when its rows under the proposed handling carry more than one VENDOR value.",
    "spread_examples": "The VA award with PIID 36C24220C0072, the Homeland Security award with PIID HSHQDC11C00083, the civilian "
                       f"award with the largest net that {MAIN_AWARD} calls front-loaded, and, among the awards S1 spreads, the "
                       f"front-loaded award with the largest civilian net under the proposed handling. Ties go to the lower award key.",
    "spread_averages": "The abstract's averages are the mean of the yearly shares, as in docs/reviews/2026-10-24_report_v1/recomputed.csv.",
}


def spread_rule_sql(rule: str) -> str:
    end = "COALESCE(a.pot_end, a.work_end)" if rule == "S2" else "a.work_end"
    before, after = f"a.work_start < DATE '{DATA_START.isoformat()}'", f"{end} > DATE '{DATA_END.isoformat()}'"
    window = "" if rule == "S3" else (f"WHEN {before} AND {after} THEN '{R_BOTH}' WHEN {before} THEN '{R_BEFORE}' "
                                      f"WHEN {after} THEN '{R_AFTER}'")
    front = f"WHEN NOT a.front_loaded THEN '{R_NOT_FRONT}'" if rule == "S4" else ""
    return f"""SELECT p.pid, p.net, a.work_start AS sp_start, {end} AS sp_end,
                      CASE WHEN a.work_start IS NULL OR {end} IS NULL OR a.work_start > {end} THEN '{R_NO_SPAN}' {window} {front} END AS reason
               FROM parts p JOIN award_info a ON p.award = a.award"""


def spread_setup(c: duckdb.DuckDBPyConnection, i: int) -> None:
    """Bucket i's award parts, their amounts by year and each award's span, main vendor and front-loaded flag."""
    days, share = AWARD_RULES[MAIN_AWARD]
    c.execute(f"""CREATE OR REPLACE TEMP TABLE kept_rows AS SELECT fy, contract_award_unique_key AS award, ag, psc, v, civ, amt_h
                  FROM read_parquet('{TIMING}/rows/b{i}.parquet') WHERE kept""")
    c.execute("""CREATE OR REPLACE TEMP TABLE main_v AS SELECT award, v AS mv FROM (SELECT award, v, SUM(amt_h) AS n FROM kept_rows GROUP BY 1, 2)
                 QUALIFY row_number() OVER (PARTITION BY award ORDER BY n DESC, v) = 1""")
    c.execute("""CREATE OR REPLACE TEMP TABLE parts AS
                 SELECT row_number() OVER () AS pid, x.*, m.mv FROM (SELECT award, ag, psc, bool_or(civ) AS civ, SUM(amt_h) AS net FROM kept_rows GROUP BY 1, 2, 3) x
                 JOIN main_v m USING (award)""")
    c.execute("""CREATE OR REPLACE TEMP TABLE by_year AS
                 SELECT p.pid, k.fy, SUM(k.amt_h) AS n FROM kept_rows k JOIN parts p ON k.award = p.award AND k.ag IS NOT DISTINCT FROM p.ag
                 AND k.psc IS NOT DISTINCT FROM p.psc GROUP BY 1, 2""")
    c.execute(f"""CREATE OR REPLACE TEMP TABLE award_info AS
                  SELECT a.award, a.work_start, a.work_end, a.civilian, a.net_h, x.pot_end,
                         COALESCE(a.net_h > 0 AND a.work_days > {days} AND a.peak_net * 100 >= a.net_h * {share}, FALSE) AS front_loaded
                  FROM read_parquet('{TIMING}/awards/b{i}.parquet') a
                  LEFT JOIN (SELECT contract_award_unique_key AS award, MAX(p) AS pot_end FROM read_parquet('{TIMING}/rows/b{i}.parquet') GROUP BY 1) x USING (award)""")


def spread_one_rule(c: duckdb.DuckDBPyConnection, rule: str, i: int) -> None:
    """The rule's amounts by award part and year in rule_year, and the differences from the baseline in moved."""
    c.execute(f"CREATE OR REPLACE TEMP TABLE part_rule AS {spread_rule_sql(rule)}")
    c.execute("""CREATE OR REPLACE TEMP TABLE spread_year AS
                 SELECT pid, fy, o, days, CAST(CAST(net AS DOUBLE) * o / days AS DECIMAL(38,6)) AS n FROM (
                     SELECT pid, net, fy, date_diff('day', sp_start, sp_end) + 1 AS days,
                            date_diff('day', greatest(sp_start, make_date(fy - 1, 10, 1)), least(sp_end, make_date(fy, 9, 30))) + 1 AS o
                     FROM (SELECT *, UNNEST(generate_series(year(sp_start) + (month(sp_start) >= 10)::INT, year(sp_end) + (month(sp_end) >= 10)::INT)) AS fy
                           FROM part_rule WHERE reason IS NULL))""")
    bad = c.execute(f"""SELECT COUNT(*) FROM (SELECT pid, SUM(o) AS so, ANY_VALUE(days) AS dd, SUM(o::DOUBLE / days) AS ss FROM spread_year GROUP BY 1)
                        WHERE so <> dd OR abs(ss - 1) > {SHARE_TOLERANCE}""").fetchone()[0]
    if bad:
        raise SystemExit(f"STOP: {rule}, bucket {i}: {bad} award parts have year shares that do not sum to 1")
    lo, hi = SPREAD_YEARS
    c.execute(f"""CREATE OR REPLACE TEMP TABLE rule_year AS
                  SELECT pid, fy, n FROM spread_year WHERE fy BETWEEN {lo} AND {hi}
                  UNION ALL SELECT b.pid, b.fy, b.n FROM by_year b JOIN part_rule r USING (pid) WHERE r.reason IS NOT NULL""")
    c.execute("""CREATE OR REPLACE TEMP TABLE moved AS
                 SELECT COALESCE(s.pid, b.pid) AS pid, COALESCE(s.fy, b.fy) AS fy, COALESCE(s.n, 0) - COALESCE(b.n, 0) AS diff FROM spread_year s
                 FULL JOIN (SELECT b.* FROM by_year b JOIN part_rule r USING (pid) WHERE r.reason IS NULL) b ON s.pid = b.pid AND s.fy = b.fy""")


def spread_build(c: duckdb.DuckDBPyConnection, examples: list[str]) -> tuple[list[tuple], dict, list[tuple], list[tuple]]:
    """Every rule's cells to .tmp/spread/cells/, and the money tables, one bucket at a time."""
    for rule in SPREAD_ALL:
        (SPREAD / "cells" / rule).mkdir(parents=True, exist_ok=True)
    c.execute("CREATE OR REPLACE TEMP TABLE examples (award VARCHAR)")
    c.executemany("INSERT INTO examples VALUES (?)", [[k] for k in examples])
    money: list[tuple] = []
    recorded: dict = defaultdict(Decimal)
    multi: list[tuple] = []
    ex: list[tuple] = []
    top: list[tuple] = []
    for i in range(TIMING_BUCKETS):
        t0 = time.time()
        spread_setup(c, i)
        c.execute(f"""COPY (SELECT b.fy, p.ag, p.psc, p.mv AS v, SUM(b.n) AS net FROM by_year b JOIN parts p USING (pid) GROUP BY ALL)
                      TO '{SPREAD}/cells/baseline/b{i}.parquet' (FORMAT parquet, COMPRESSION zstd)""")
        money += [("baseline", *x, Decimal(0), Decimal(0)) for x in c.execute(
            "SELECT b.fy, p.civ, SUM(b.n) FROM by_year b JOIN parts p USING (pid) GROUP BY 1, 2").fetchall()]
        ex += [("baseline", *x) for x in c.execute("""SELECT p.award, b.fy, SUM(b.n) FROM by_year b JOIN parts p USING (pid)
                                                      SEMI JOIN examples e ON p.award = e.award GROUP BY 1, 2""").fetchall()]
        multi += c.execute("""SELECT fy, SUM(amt_h) FROM kept_rows WHERE civ AND award IN
                              (SELECT award FROM kept_rows GROUP BY 1 HAVING COUNT(DISTINCT v) > 1) GROUP BY 1""").fetchall()
        for rule in SPREAD_RULES:
            spread_one_rule(c, rule, i)
            c.execute(f"""COPY (SELECT y.fy, p.ag, p.psc, p.mv AS v, SUM(y.n) AS net FROM rule_year y JOIN parts p USING (pid) GROUP BY ALL)
                          TO '{SPREAD}/cells/{rule}/b{i}.parquet' (FORMAT parquet, COMPRESSION zstd)""")
            got = dict(((fy, civ), net) for fy, civ, net in c.execute(
                "SELECT y.fy, p.civ, SUM(y.n) FROM rule_year y JOIN parts p USING (pid) GROUP BY 1, 2").fetchall())
            out = {(fy, civ): (a, b) for fy, civ, a, b in c.execute(
                """SELECT m.fy, p.civ, COALESCE(SUM(-m.diff) FILTER (WHERE m.diff < 0), 0), COALESCE(SUM(m.diff) FILTER (WHERE m.diff > 0), 0)
                   FROM moved m JOIN parts p USING (pid) GROUP BY 1, 2""").fetchall()}
            for k in set(got) | set(out):
                a, b = out.get(k, (0, 0))
                money.append((rule, k[0], k[1], got.get(k, Decimal(0)), d(a), d(b)))
            for fy, civ, why, net in c.execute("""SELECT b.fy, p.civ, r.reason, SUM(b.n) FROM by_year b JOIN part_rule r USING (pid) JOIN parts p USING (pid)
                                                  WHERE r.reason IS NOT NULL GROUP BY 1, 2, 3""").fetchall():
                recorded[(rule, fy, civ, why)] += d(net)
            ex += [(rule, *x) for x in c.execute("""SELECT p.award, y.fy, SUM(y.n) FROM rule_year y JOIN parts p USING (pid)
                                                    SEMI JOIN examples e ON p.award = e.award GROUP BY 1, 2""").fetchall()]
            if rule == "S1":
                top += c.execute(f"""SELECT SUM(m.diff), p.award, p.ag, p.psc, p.mv, p.net, ANY_VALUE(r.sp_start), ANY_VALUE(r.sp_end)
                                     FROM moved m JOIN parts p USING (pid) JOIN part_rule r USING (pid) WHERE m.diff > 0
                                     GROUP BY p.pid, 2, 3, 4, 5, 6 ORDER BY 1 DESC LIMIT {SPREAD_TOP}""").fetchall()
        print(f"  spread: bucket {i + 1} of {TIMING_BUCKETS}, {time.time() - t0:.0f} s", flush=True)
    return money, recorded, multi, ex, top


def rule_vs(c: duckdb.DuckDBPyConnection, rule: str) -> None:
    """Load a rule's cells as vs, the table year_scores() reads. A cell can span buckets."""
    c.execute(f"""CREATE OR REPLACE TEMP TABLE vs AS SELECT fy, ag, psc, v, SUM(net) AS net
                  FROM read_parquet('{SPREAD}/cells/{rule}/b*.parquet') GROUP BY ALL""")


def civilian_share_by_year(scores: dict[int, dict]) -> dict[int, Decimal]:
    out = {}
    for fy, s in scores.items():
        civ = [v_ for k, v_ in s.items() if k[1] != "097"]
        total = sum((v_[2] for v_ in civ), Decimal(0))
        above = sum((v_[2] for v_ in civ if v_[0] is not None and v_[0] > POOL_THRESHOLD), Decimal(0))
        out[fy] = pct(above, total)
    return out


def yearly_report_share() -> dict[int, Decimal]:
    with open(YEARLY_SHARE_CSV, newline="", encoding="utf-8") as f:
        return {int(r["fiscal_year"]): Decimal(r["share_above_2500_all_codes_pct"]) for r in csv.DictReader(f)}


def average_label(a: int, b: int) -> str:
    return f"FY{a} to FY{b} average"


def mean_share(values: dict, a: int, b: int) -> Decimal:
    return q(sum((Decimal(values[y]) for y in range(a, b + 1)), Decimal(0)) / (b - a + 1))


def main_vendor_effect(c: duckdb.DuckDBPyConnection, multi: list[tuple]) -> None:
    report = yearly_report_share()
    proposed = {fy: year_scores(c, fy)[1] for fy in years()}
    share_p = civilian_share_by_year(proposed)
    bad = [fy for fy in years() if share_p[fy] != report[fy]]
    if bad:
        raise SystemExit(f"CHECK FAILED: the civilian share under the proposed handling differs from p5_stable_share_by_year.csv in {bad}")
    civ_net = {fy: sum((v_[2] for k, v_ in s.items() if k[1] != "097"), Decimal(0)) for fy, s in proposed.items()}
    del proposed
    vs_total = dict(c.execute("SELECT fy, SUM(net) FROM vs GROUP BY 1").fetchall())
    rule_vs(c, "baseline")
    base_total = dict(c.execute("SELECT fy, SUM(net) FROM vs GROUP BY 1").fetchall())
    drift = [fy for fy in years() if d(vs_total[fy]) != d(base_total[fy])]
    if drift:
        raise SystemExit(f"CHECK FAILED: the baseline's net differs from the proposed handling's net in {drift}")
    share_b = civilian_share_by_year({fy: year_scores(c, fy)[1] for fy in years()})
    multi_net = defaultdict(Decimal)
    for fy, net in multi:
        multi_net[fy] += d(net)
    rows = [{"period": f"FY{fy}", "report_share_above_2500_pct": report[fy], "proposed_handling_share_above_2500_pct": share_p[fy],
             "baseline_share_above_2500_pct": share_b[fy], "change_points": share_b[fy] - share_p[fy],
             "civilian_net": q(civ_net[fy]), "net_on_awards_with_more_than_one_vendor_id": q(multi_net[fy]),
             "share_on_awards_with_more_than_one_vendor_id_pct": pct(multi_net[fy], civ_net[fy])} for fy in years()]
    for a, b in ABSTRACT_AVERAGES:
        p_, b_ = mean_share(share_p, a, b), mean_share(share_b, a, b)
        rows.append({"period": average_label(a, b), "report_share_above_2500_pct": mean_share(report, a, b),
                     "proposed_handling_share_above_2500_pct": p_, "baseline_share_above_2500_pct": b_, "change_points": b_ - p_,
                     "civilian_net": "", "net_on_awards_with_more_than_one_vendor_id": "", "share_on_awards_with_more_than_one_vendor_id_pct": ""})
    total, tm = sum(civ_net.values(), Decimal(0)), sum(multi_net.values(), Decimal(0))
    rows.append({"period": "all years", "report_share_above_2500_pct": "", "proposed_handling_share_above_2500_pct": "", "baseline_share_above_2500_pct": "",
                 "change_points": "", "civilian_net": q(total), "net_on_awards_with_more_than_one_vendor_id": q(tm),
                 "share_on_awards_with_more_than_one_vendor_id_pct": pct(tm, total)})
    write("p11_main_vendor_effect", rows)
    for r in rows[-4:]:
        print(f"  {r}", flush=True)


def spread_money_tables(money: list[tuple], recorded: dict) -> None:
    """p11_spread_money_by_year and p11_spread_totals, with the stop checks on the totals."""
    base, net, out, into = defaultdict(Decimal), defaultdict(Decimal), defaultdict(Decimal), defaultdict(Decimal)
    for rule, fy, civ, n, a, b in money:
        if rule == "baseline":
            base[(fy, civ)] += d(n)
        else:
            net[(rule, fy, civ)] += d(n)
            out[(rule, fy, civ)] += a
            into[(rule, fy, civ)] += b
    lo, hi = SPREAD_YEARS
    rows, totals = [], []
    for rule in SPREAD_RULES:
        for fy in years():
            bn, sn = base[(fy, True)], net[(rule, fy, True)]
            a, b = out[(rule, fy, True)], into[(rule, fy, True)]
            if abs(bn + b - a - sn) > Decimal("0.01"):
                raise SystemExit(f"CHECK FAILED: {rule} FY{fy}: baseline + in - out is not the spread net")
            row = {"fiscal_year": fy, "rule": rule, "baseline_civilian_net": q(bn), "spread_civilian_net": q(sn), "moved_out": q(a), "moved_in": q(b),
                   "moved_out_pct_of_baseline": pct(a, bn), "money_dropping_out": ""}
            for why in SPREAD_REASONS:
                row[f"recorded: {why}"] = q(recorded[(rule, fy, True, why)])
            rows.append(row)
        outside = {"before FY2008": lambda y: y < lo, "after FY2025": lambda y: y > hi}
        for label, test in outside.items():
            drop = sum((into[k] - out[k] for k in set(into) | set(out) if k[0] == rule and k[2] and test(k[1])), Decimal(0))
            if rule == "S3":
                row = {"fiscal_year": label, "rule": rule, "baseline_civilian_net": "", "spread_civilian_net": "", "moved_out": "", "moved_in": "",
                       "moved_out_pct_of_baseline": "", "money_dropping_out": q(drop)}
                for why in SPREAD_REASONS:
                    row[f"recorded: {why}"] = ""
                rows.append(row)
        for scope, keep in (("all agencies", lambda c_: True), ("civilian", lambda c_: c_)):
            b_total = sum((v_ for (y, c_), v_ in base.items() if keep(c_)), Decimal(0))
            s_total = sum((v_ for (r_, y, c_), v_ in net.items() if r_ == rule and keep(c_)), Decimal(0))
            drop = sum((into[k] - out[k] for k in set(into) | set(out) if k[0] == rule and keep(k[2]) and not lo <= k[1] <= hi), Decimal(0))
            gap = b_total - s_total
            totals.append({"rule": rule, "agencies": scope, "baseline_total": q(b_total), "spread_total": q(s_total), "difference": q(gap, "0.000001"),
                           "money_dropping_out": q(drop, "0.000001"), "difference_less_money_dropping_out": q(gap - drop, "0.000001")})
            print(f"  totals {totals[-1]}", flush=True)
            if rule == "S3" and abs(gap - drop) > TOTAL_TOLERANCE:
                raise SystemExit(f"STOP: S3 {scope}: the difference {gap} is not the money dropping out, {drop}")
            if rule != "S3" and abs(gap) > TOTAL_TOLERANCE:
                raise SystemExit(f"STOP: {rule} {scope}: the total differs from the baseline by {gap}")
    write("p11_spread_money_by_year", rows)
    write("p11_spread_totals", totals)


@part
def part11() -> None:
    check_columns(TIMING_COLUMNS + ["award_id_piid", "recipient_name"])
    c = con()
    SPREAD.mkdir(parents=True, exist_ok=True)
    show_codes(c, "awarding_agency_code", limit=10)
    show_codes(c, "product_or_service_code", limit=10)
    setup(c)
    if not SPAN_FILE.exists():
        print("  SPAN_FILE is missing, rebuilding it with the Part 8 code", flush=True)
        timing_views(c)
        part8_awards(c)
    timing_views(c)
    differ = c.execute(f"""SELECT COUNT(*) FROM read_parquet('{SPAN_FILE}') s LEFT JOIN aw ON s.award = aw.award
                           WHERE aw.award IS NULL OR s.work_start IS DISTINCT FROM aw.work_start OR s.work_end IS DISTINCT FROM aw.work_end""").fetchone()[0]
    print(f"  span file against the award table: {differ} awards differ", flush=True)
    if differ:
        raise SystemExit(f"CHECK FAILED: SPAN_FILE and .tmp/timing/awards differ on {differ} awards")
    examples = []
    for piid, agency in SPREAD_EXAMPLES:
        got = c.execute(f"SELECT DISTINCT contract_award_unique_key FROM {all_rows()} WHERE award_id_piid = ? AND awarding_agency_code = ?", [piid, agency]).fetchall()
        if len(got) != 1:
            raise SystemExit(f"CHECK FAILED: PIID {piid} in agency {agency} is {len(got)} awards")
        examples.append(got[0][0])
    days, share = AWARD_RULES[MAIN_AWARD]
    examples.append(c.execute(f"""SELECT award FROM aw WHERE civilian AND net_h > 0 AND work_days > {days} AND peak_net * 100 >= net_h * {share}
                                  ORDER BY net_h DESC, award LIMIT 1""").fetchone()[0])
    examples.append(c.execute(f"""SELECT award FROM aw WHERE civilian AND net_h > 0 AND work_days > {days} AND peak_net * 100 >= net_h * {share}
                                  AND work_start >= DATE '{DATA_START.isoformat()}' AND work_end <= DATE '{DATA_END.isoformat()}'
                                  ORDER BY civ_net_h DESC, award LIMIT 1""").fetchone()[0])
    print(f"  examples: {examples}", flush=True)
    money, recorded, multi, ex, top = spread_build(c, examples)
    spread_money_tables(money, recorded)
    by = {(r, k, fy): d(n) for r, k, fy, n in ex}
    write("p11_spread_examples", [{"award": k, "fiscal_year": fy, **{r: q(by.get((r, k, fy), Decimal(0))) for r in SPREAD_ALL}}
                                  for k in examples for fy in years()])
    c.execute("CREATE OR REPLACE TEMP TABLE tv (award VARCHAR, v VARCHAR)")
    top = sorted(top, key=lambda x: x[0], reverse=True)[:SPREAD_TOP]
    c.executemany("INSERT INTO tv VALUES (?, ?)", [[x[1], x[4]] for x in top])
    names = {(a, v_): n for a, v_, n in c.execute(f"""SELECT contract_award_unique_key, r.v, arg_max(recipient_name, action_date) FROM {all_rows()} r
                                                      JOIN tv ON contract_award_unique_key = tv.award AND r.v = tv.v GROUP BY 1, 2""").fetchall()}
    for moved_, award, ag, psc, v_, net, a, b in top:
        print(f"  moved {q(d(moved_))}: {award}, agency {ag}, code {psc}, vendor {names.get((award, v_))} ({v_}), span {a} to {b}, net {q(d(net))}", flush=True)
    setup(c)                                         # back to the proposed handling for the vendor change alone
    main_vendor_effect(c, multi)
    print("part11: checks passed", flush=True)


# ============================================================================================ Part 12. Do the results change?

SWING_JUMP = 1000
AGREEMENT_CUTOFF = 500
LARGEST_YEARS = (2016, 2019)
LARGEST_TOP = 10
LINE_CLASSES = ("rising", "falling", "neither")

RULES |= {
    "spread_lines": "The report's lines and the stable lines keep the agency, code and years they have under the proposed handling, "
                    "and are rescored under each rule. A year the rule leaves unscored drops out of that line for that rule, and the count "
                    "of such line-years is in p12_swings. A line left with fewer than 3 years is neither rising nor falling, as classify() gives.",
    "spread_swings": "The change is the absolute change in HHI between back-to-back fiscal years with both years scored under the rule. "
                     f"A jump is a change of {SWING_JUMP:,} points or more.",
    "spread_rising": f"classify() on each rule's scores, shuffled {SHUFFLES} times with random.Random({SEED}), one generator for each line "
                     "set and rule, in the order rising_counts() uses it, whose counts must be matched. A line's dollars are its segment nets "
                     "under the rule over its scored years. The check rows rebuild the lines from S1's scores with line_set().",
    "spread_share": "The civilian share of dollars above 2,500 is the net of civilian segments scoring above 2,500 over the net of all "
                    "civilian segments, each under the rule. Under S3 the money dropping out is in neither.",
    "spread_largest": f"The {LARGEST_TOP} civilian segments with the most baseline net in each of FY{LARGEST_YEARS[0]} and FY{LARGEST_YEARS[1]}, ties "
                      "to the lower agency and code. A segment a rule leaves unscored has a blank HHI.",
}


def rescore_lines(lines: list[list[tuple]], keys: list[tuple], scores: dict[tuple, tuple]) -> tuple[list[list[tuple]], int]:
    out, lost = [], 0
    for v, (ag, psc) in zip(lines, keys):
        kept = []
        for x in v:
            h_, _, net = scores.get((x[0], ag, psc), (None, 0, None))
            if h_ is None:
                lost += 1
            else:
                kept.append((x[0], float(h_), net))
        out.append(kept)
    return out, lost


def swing_rows(label: str, rule: str, lines: list[list[tuple]], keys: list[tuple], lost: int) -> list[dict]:
    rows = []
    for scope, keep in LINE_SCOPES.items():
        changes = []
        for v, (ag, _) in zip(lines, keys):
            if keep(ag):
                by_year = {x[0]: x[1] for x in v}
                changes += [abs(by_year[y + 1] - h_) for y, h_ in by_year.items() if y + 1 in by_year]
        jumps = sum(1 for x in changes if x >= SWING_JUMP)
        rows.append({"line_set": label, "agencies": scope, "rule": rule, "lines": sum(1 for k in keys if keep(k[0])), "pairs": len(changes),
                     "median_change": round(statistics.median(changes), 1) if changes else "", "jumps": jumps,
                     "jump_share_pct": round(100 * jumps / len(changes), 2) if changes else "", "line_years_unscored_all_agencies": lost})
    return rows


def rising_rows(label: str, rule: str, lines: list[list[tuple]]) -> list[dict]:
    rng = random.Random(SEED)
    n = len(lines)
    dollars = [sum((x[2] for x in v), Decimal(0)) for v in lines]
    all_dollars = sum(dollars, Decimal(0))
    rows = []
    want = {r["cutoff"]: r for r in rising_counts(lines)}
    for cut in CUTOFFS:
        seen, shuf, money, shuf_money = defaultdict(int), defaultdict(int), defaultdict(Decimal), defaultdict(Decimal)
        for v, dol in zip(lines, dollars):
            res = classify([x[1] for x in v], cut)
            seen[res] += 1
            money[res] += dol
        for _ in range(SHUFFLES):
            for v, dol in zip(lines, dollars):
                vals = [x[1] for x in v]
                rng.shuffle(vals)
                res = classify(vals, cut)
                shuf[res] += 1
                shuf_money[res] += dol
        row = {"line_set": label, "rule": rule, "cutoff": cut, "lines": n}
        for res in ("rising", "falling"):
            row[f"{res}_pct"] = round(100 * seen[res] / n, 2)
            row[f"{res}_pct_after_shuffle"] = round(100 * shuf[res] / (n * SHUFFLES), 2)
        for res in ("rising", "falling"):
            row[f"{res}_pct_by_dollars"] = pct(money[res], all_dollars)
            row[f"{res}_pct_after_shuffle_by_dollars"] = pct(shuf_money[res] / SHUFFLES, all_dollars)
        r = want[cut]
        if (row["rising_pct"], row["rising_pct_after_shuffle"], row["falling_pct"], row["falling_pct_after_shuffle"]) != (
                r["rising_pct"], r["rising_pct_after_shuffle"], r["falling_pct"], r["falling_pct_after_shuffle"]):
            raise SystemExit(f"CHECK FAILED: {label}, {rule}, cutoff {cut}: counts differ from rising_counts(): {row}, {r}")
        rows.append(row)
    return rows


@part
def part12() -> None:
    c = con()
    show_codes(c, "awarding_agency_code", limit=10)
    show_codes(c, "product_or_service_code", limit=10)
    setup(c)
    _, rep, st = report_and_stable_lines(c)
    got = next(r for r in rising_counts(rep[0]) if r["cutoff"] == POOL_REPORT_CUTOFF)
    want = REPORT_LINES[POOL_REPORT_CUTOFF]
    if Decimal(str(got["rising_pct"])) != want[0] or Decimal(str(got["rising_pct_after_shuffle"])) != want[1]:
        raise SystemExit(f"CHECK FAILED: rising_counts() gives {got}, the report has {want}")
    with open(STABLE_CODES_CSV, newline="", encoding="utf-8") as f:
        stable = {r["psc"] for r in csv.DictReader(f)}
    report = yearly_report_share()
    sets = (("report's lines", rep), ("stable lines", st))
    swings, rising, shares, classes, largest, chosen = [], [], {}, {}, {}, None
    for rule in SPREAD_ALL:
        t0 = time.time()
        rule_vs(c, rule)
        by_year = {fy: year_scores(c, fy)[1] for fy in years()}
        scores = {k: v_ for s in by_year.values() for k, v_ in s.items()}
        shares[rule] = civilian_share_by_year(by_year)
        if rule == "baseline":
            chosen = {}
            for fy in LARGEST_YEARS:
                civ = sorted(((k, v_[2]) for k, v_ in by_year[fy].items() if k[1] != "097"), key=lambda x: (-x[1], x[0][1] or "", x[0][2] or ""))
                chosen[fy] = civ[:LARGEST_TOP]
        largest[rule] = {k: scores.get(k, (None,))[0] for top in chosen.values() for k, _ in top}
        for label, (lines, keys) in sets:
            mine, lost = rescore_lines(lines, keys, scores)
            print(f"  {rule}, {label}: {lost} line-years unscored", flush=True)
            swings += swing_rows(label, rule, mine, keys, lost)
            rising += rising_rows(label, rule, mine)
            classes[(label, rule)] = [classify([x[1] for x in v], AGREEMENT_CUTOFF) for v in mine]
        if rule == "S1":
            for label, codes, first, last in (("report's lines, rebuilt on S1", None, *REPORT_WINDOW),
                                              ("stable lines, rebuilt on S1", stable, STABLE_YEARS[0], STABLE_YEARS[-1])):
                rebuilt = line_set(scores, codes, first, last)[0]
                print(f"  {label}: {len(rebuilt):,} lines", flush=True)
                rising += rising_rows(label, rule, rebuilt)
        print(f"  {rule} scored, {time.time() - t0:.0f} s", flush=True)
    write("p12_swings", swings)
    write("p12_rising", rising)
    agreement = []
    for label, _ in sets:
        pairs = list(zip(classes[(label, "baseline")], classes[(label, "S1")]))
        for a in LINE_CLASSES:
            for b in LINE_CLASSES:
                agreement.append({"line_set": label, "cutoff": AGREEMENT_CUTOFF, "baseline_class": a, "s1_class": b, "lines": sum(1 for x in pairs if x == (a, b))})
    write("p12_line_agreement", agreement)
    rows = []
    for fy in years():
        rows.append({"period": f"FY{fy}", "report": report[fy], **{r: shares[r][fy] for r in SPREAD_ALL}})
    for a, b in ABSTRACT_AVERAGES:
        rows.append({"period": average_label(a, b), "report": mean_share(report, a, b), **{r: mean_share(shares[r], a, b) for r in SPREAD_ALL}})
    write("p12_share_by_year", rows)
    with open(OUT / "p11_main_vendor_effect.csv", newline="", encoding="utf-8") as f:
        p11 = {r["period"]: r["baseline_share_above_2500_pct"] for r in csv.DictReader(f)}
    off = [r["period"] for r in rows if str(r["baseline"]) != p11[r["period"]]]
    if off:
        raise SystemExit(f"CHECK FAILED: the baseline share differs from p11_main_vendor_effect.csv in {off}")
    write("p12_largest_segments", [
        {"selected_on": f"FY{fy}", "rank": i + 1, "agency": k[1], "product_code": k[2], "baseline_net": q(net),
         **{f"hhi_{r}": ("" if largest[r][k] is None else q(largest[r][k], "0.1")) for r in SPREAD_ALL}}
        for fy, top in chosen.items() for i, (k, net) in enumerate(top)])
    print("part12: checks passed", flush=True)


# ============================================================================================ Part 20. Civilian trend lines

CIVILIAN_GROUPS = {"all": LINE_SCOPES["all agencies"], "civilian": LINE_SCOPES["civilian"], "defense": LINE_SCOPES["097"]}
CIVILIAN_KEPT_CUTOFFS = {"all": (POOL_REPORT_CUTOFF,), "civilian": CUTOFFS, "defense": (POOL_REPORT_CUTOFF,)}
CIVILIAN_SAVED = {"averaged": ("p10_pooled_rising", "method"), "pooled": ("p10_pooled_rising", "method"),
                  "baseline": ("p12_rising", "rule"), "S1": ("p12_rising", "rule")}
CIVILIAN_RESULTS = ("rising_pct", "rising_pct_after_shuffle", "falling_pct", "falling_pct_after_shuffle", "rising_pct_by_dollars",
                    "rising_pct_after_shuffle_by_dollars", "falling_pct_by_dollars", "falling_pct_after_shuffle_by_dollars")
CIVILIAN_LINE_SET = "report's lines"

RULES |= {
    "civilian_lines": f"The report's {REPORT_LINE_COUNT:,} lines from line_set(), with the same settings and order. The groups are taken after "
                      "the lines are chosen: all is every line, civilian leaves out the lines on awarding agency 097 with a blank code "
                      "counting as civilian, and defense keeps only the 097 lines. Civilian and defense add back to all.",
    "civilian_ways": "Four ways of counting, each through the code of its saved table. averaged and pooled come from pooled_lines() on the "
                      "proposed handling. baseline and S1 come from rescore_lines() and rising_rows() on each rule's scores, so each line keeps "
                      "its agency, code and years.",
    "civilian_shuffle": f"One random.Random({SEED}) for each group and way, {SHUFFLES} rounds, in the order rising_counts() uses it. All "
                        f"cutoffs are drawn in order even where the table keeps one, as the results at a cutoff depend on the draws before it. "
                        "A group's shuffled shares come from its own draws, so they are not a slice of the all-agency draws, and only the "
                        "observed counts add back exactly.",
    "civilian_reproduce": f"The all group must equal {', '.join(sorted({v[0] for v in CIVILIAN_SAVED.values()}))} on every result at "
                          f"{POOL_REPORT_CUTOFF} points, to two decimals. Any difference stops the run before anything is written.",
}


def civilian_row(group: str, way: str, row: dict) -> dict:
    return {"group": group, "line_set": CIVILIAN_LINE_SET, "rule": way, "cutoff": row["cutoff"], "lines": row["lines"], **{k: row[k] for k in CIVILIAN_RESULTS}}


def civilian_reproduce(way: str, row: dict) -> None:
    """Stop unless a rebuilt all-agency row equals its saved row."""
    table, column = CIVILIAN_SAVED[way]
    with open(OUT / f"{table}.csv", newline="", encoding="utf-8") as f:
        saved = next(r for r in csv.DictReader(f) if r["line_set"] == CIVILIAN_LINE_SET and r["cutoff"] == str(POOL_REPORT_CUTOFF) and r[column] == way)
    for k in ("lines",) + CIVILIAN_RESULTS:
        same = Decimal(str(row[k])) == Decimal(saved[k])
        print(f"  reproduce {way}, {k}: rebuilt {row[k]}, saved {saved[k]}, {'same' if same else 'DIFFERENT'}", flush=True)
        if not same:
            raise SystemExit(f"CHECK FAILED: {way}, {k}: rebuilt {row[k]}, {table}.csv has {saved[k]}")


def civilian_keep(group: str, way: str, rows: list[dict]) -> list[dict]:
    """The group's kept cutoffs as table rows, with the all group checked against its saved table."""
    out = [civilian_row(group, way, r) for r in rows if r["cutoff"] in CIVILIAN_KEPT_CUTOFFS[group]]
    if group == "all":
        for r in out:
            civilian_reproduce(way, r)
    return out


def civilian_add_back(rows: list[dict]) -> None:
    """Civilian and defense lines, and their observed counts at the shared cutoff, must add back to all."""
    at = {(r["group"], r["rule"]): r for r in rows if r["cutoff"] == POOL_REPORT_CUTOFF}
    for way in CIVILIAN_SAVED:
        for k in (None, "rising_pct", "falling_pct"):
            got = {g: at[(g, way)]["lines"] if k is None else round(at[(g, way)][k] * at[(g, way)]["lines"] / 100) for g in CIVILIAN_GROUPS}
            if got["civilian"] + got["defense"] != got["all"]:
                raise SystemExit(f"CHECK FAILED: {way}, {k or 'lines'}: civilian and defense do not add back to all: {got}")


@part
def part20() -> None:
    c = con()
    show_codes(c, "awarding_agency_code", limit=10)
    show_codes(c, "product_or_service_code", limit=10)
    setup(c)
    _, (lines, keys), _ = report_and_stable_lines(c)
    members = {g: [i for i, k in enumerate(keys) if keep(k[0])] for g, keep in CIVILIAN_GROUPS.items()}
    print("  lines: " + ", ".join(f"{g} {len(m):,}" for g, m in members.items()), flush=True)
    rows = []
    for group, m in members.items():
        got = pooled_lines(c, f"{CIVILIAN_LINE_SET}, {group}", [lines[i] for i in m], [keys[i] for i in m])
        for way in ("averaged", "pooled"):
            rows += civilian_keep(group, way, [r for r in got if r["method"] == way])
    for rule in ("baseline", "S1"):
        t0 = time.time()
        rule_vs(c, rule)
        scores = {k: v_ for fy in years() for k, v_ in year_scores(c, fy)[1].items()}
        mine, lost = rescore_lines(lines, keys, scores)
        print(f"  {rule}: {lost} line-years unscored", flush=True)
        for group, m in members.items():
            rows += civilian_keep(group, rule, rising_rows(f"{CIVILIAN_LINE_SET}, {group}", rule, [mine[i] for i in m]))
        print(f"  {rule} scored, {time.time() - t0:.0f} s", flush=True)
    civilian_add_back(rows)
    order = {g: i for i, g in enumerate(CIVILIAN_GROUPS)}
    ways = {w: i for i, w in enumerate(CIVILIAN_SAVED)}
    rows.sort(key=lambda r: (order[r["group"]], ways[r["rule"]], r["cutoff"]))
    write("p20_civilian_rising", rows)
    for r in rows:
        print(f"  {r}", flush=True)
    print("part20: checks passed", flush=True)


@part
def rules() -> None:
    """Run no analysis. main() then writes rules.json from RULES, as it does after every part."""


def main(argv: list[str] | None = None) -> int:
    names = argv if argv is not None else sys.argv[1:]
    if not names or any(n not in PARTS for n in names):
        print(__doc__)
        return 2
    if not years():                                 # never replace committed tables with empty ones
        print("No yearly data found: no fiscal year has its Stage 0 zip and finished Stage 1 and Stage 2 outputs. "
              f"Nothing was written to {OUT}. Build the stages first: python -m src.stages refresh")
        return 1
    for n in names:
        t0 = time.time()
        PARTS[n]()
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "rules.json").write_text(json.dumps(RULES, indent=1), encoding="utf-8")
        print(f"{n}: {time.time() - t0:.0f} s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
