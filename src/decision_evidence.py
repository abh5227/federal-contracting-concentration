"""Evidence for the open data decisions in config/decisions.csv.

    python -m src.decision_evidence part1      # one part: part1 to part9
    python -m src.decision_evidence extract    # only build the working extract
    python -m src.decision_evidence rules      # only write rules.json from RULES

Analysis only. Nothing here cleans, drops or changes data, nothing under data/ is written, and no decision is
applied. Each rule is written in RULES below before the code that uses it. The segment, the vendor and HHI follow
src/analyses_v2.py (its VENDOR expression, hhi(), PAIRS, MINT_KEYS and MFA are imported, not copied).

The working extract is a typed copy of the columns used here, one Parquet file per fiscal year, in
.tmp/decision_evidence/ (gitignored, outside data/). It is rebuilt from the Stage 1 mirror whenever it is missing.
Outputs are small tables in reports/decision_evidence/, one CSV per table.
"""

from __future__ import annotations

import csv
import json
import re
import sys
import time
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import duckdb

from . import config
from .analyses_v2 import AMT, MFA, MINT_KEYS, PAIRS, VENDOR, d, files, hhi, years
from .concentration_prelim import BANDS as HHI_BANDS
from .stage2 import COMPETED

OUT = config.REPORTS_DIR / "decision_evidence"
WORK = config.REPO_ROOT / ".tmp" / "decision_evidence"

# Every Layer A column the extract keeps, checked against reports/columns_fy2025.txt before it is read.
COLUMNS = ["contract_transaction_unique_key", "contract_award_unique_key", "award_id_piid", "modification_number",
           "parent_award_agency_id", "parent_award_id_piid", "federal_action_obligation", "total_dollars_obligated",
           "action_date", "awarding_agency_code", "awarding_agency_name", "awarding_sub_agency_code",
           "awarding_sub_agency_name", "funding_agency_code", "funding_agency_name", "recipient_uei", "recipient_duns",
           "recipient_name", "recipient_parent_uei", "recipient_parent_duns", "recipient_parent_name",
           "recipient_parent_name_raw", "primary_place_of_performance_country_code", "primary_place_of_performance_country_name",
           "award_or_idv_flag", "award_type_code", "idv_type_code", "type_of_contract_pricing_code", "action_type_code",
           "action_type", "product_or_service_code", "extent_competed_code", "number_of_offers_received",
           "parent_award_single_or_multiple_code"]
# Read straight from Layer A for the few example rows that need them.
TEXT_COLUMNS = ["transaction_description", "prime_award_base_transaction_description"]

RULES = {
    "extract": "A typed copy of the columns in COLUMNS for every present fiscal year: federal_action_obligation as "
               "DECIMAL(38,6) (the AMT expression of src/analyses_v2.py), action_date as a date, the vendor as the "
               "VENDOR expression and the placeholder flag as the MFA expression. Text is kept as published.",
    "segment": "As in src/analyses_v2.py. The awarding agency code as recorded x product or service code x fiscal year. "
               "A blank product code is its own value.",
    "vendor": "As in src/analyses_v2.py. recipient_parent_uei, or recipient_uei when the parent is blank. Rows with "
              "both blank form one vendor, '(no ID)'.",
    "proposed_handling": "Variant V1 of src/eda/base_tables.py on the shivram-eda branch. Each reversal pair in PAIRS "
                         "keeps the pair's net on its first listed row and its second row is set to zero. The two rows "
                         "in MINT_KEYS, rows matching MFA and the vendor '(no ID)' are left out.",
    "hhi": "As hhi() in src/analyses_v2.py. 10,000 x the sum of squared shares, where a share is a vendor's dollars "
           "divided by the summed dollars of vendors with positive dollars in the segment. A segment with no such "
           "vendor is unscored.",
    "bands": "HHI bands as in src/concentration_prelim.py: " + "; ".join(b for b, _, _ in HHI_BANDS) + ", plus "
             "'unscored'. Each band includes its upper bound. A segment changes band when its band differs between "
             "two runs, a segment missing from one run counting as unscored there.",
    "share_above_2500": "The summed net (under the proposed handling) of segments whose HHI is strictly above 2,500, "
                        "divided by the summed net of all rows under the proposed handling that year, in percent. "
                        "Civilian: the same over every awarding agency except 097.",
}


# ============================================================================================ helpers


def con() -> duckdb.DuckDBPyConnection:
    c = duckdb.connect()
    c.execute("SET TimeZone = 'UTC'")
    (WORK / "spill").mkdir(parents=True, exist_ok=True)
    c.execute(f"SET temp_directory = '{WORK / 'spill'}'")
    c.execute("SET memory_limit = '8GB'")
    c.execute("SET preserve_insertion_order = false")
    c.execute("SET enable_progress_bar = false")
    return c


BUCKETS = 8                                     # award-level work runs in this many hash buckets of the award key


def bucketed(c: duckdb.DuckDBPyConnection, name: str, select: str) -> None:
    """CREATE TABLE name from select, run once per bucket; select must contain {bucket}, a WHERE condition on the
    award key, so that every award's rows fall in one run."""
    for i in range(BUCKETS):
        cond = f"hash(contract_award_unique_key) % {BUCKETS} = {i}"
        sql = select.format(bucket=cond)
        c.execute(f"CREATE OR REPLACE TEMP TABLE {name} AS {sql}" if i == 0 else f"INSERT INTO {name} {sql}")


def check_columns(cols: list[str]) -> None:
    known = {ln.split("\t", 1)[1] for ln in config.REFERENCE_COLUMNS_FILE.read_text(encoding="utf-8").splitlines()
             if ln and not ln.startswith("#")}
    missing = [x for x in cols if x not in known]
    if missing:
        raise SystemExit(f"columns not in {config.REFERENCE_COLUMNS_FILE.name}: {missing}")


def extract_path(fy: int) -> Path:
    return WORK / f"fy{fy}.parquet"


def build_extract(force: bool = False) -> None:
    check_columns(COLUMNS)
    c = con()
    for fy in years():
        p = extract_path(fy)
        if p.exists() and not force:
            continue
        sel = ", ".join(x for x in COLUMNS if x not in ("federal_action_obligation", "action_date"))
        c.execute(f"""COPY (SELECT {fy} AS fy, {sel}, {AMT} AS amt, TRY_CAST(action_date AS DATE) AS action_date,
                                   {VENDOR} AS v, {MFA} AS mfa FROM read_parquet({files(fy)!r}))
                      TO '{p}.part' (FORMAT parquet, COMPRESSION zstd)""")
        Path(f"{p}.part").rename(p)
        print(f"extract: FY{fy} done", flush=True)


def all_rows() -> str:
    """SQL for every row of every present year in the extract."""
    build_extract()
    return f"read_parquet({[str(extract_path(fy)) for fy in years()]!r})"


def pair_net_sql(c: duckdb.DuckDBPyConnection, pairs: list | None = None, other: str = "amt") -> str:
    """A CASE expression for the proposed handling's amount: the pair's net on its first row, zero on its second.
    pairs defaults to PAIRS. Rows outside the pairs keep the column named by other."""
    pairs = list(PAIRS.values()) if pairs is None else pairs
    keys = [k for ks in pairs for k in ks]
    c.execute("CREATE OR REPLACE TEMP TABLE pnk (k VARCHAR)")
    c.executemany("INSERT INTO pnk VALUES (?)", [[k] for k in keys])
    amt = dict(c.execute(f"SELECT contract_transaction_unique_key, amt FROM {all_rows()} "
                         "SEMI JOIN pnk ON contract_transaction_unique_key = pnk.k").fetchall())
    if len(amt) != len(set(keys)):
        raise SystemExit(f"reversal pair rows missing from the data: {sorted(set(keys) - set(amt))}")
    whens = []
    for first, second in pairs:
        whens.append(f"WHEN '{first}' THEN CAST({amt[first] + amt[second]} AS DECIMAL(38,6))")
        whens.append(f"WHEN '{second}' THEN CAST(0 AS DECIMAL(38,6))")
    return f"CASE contract_transaction_unique_key {' '.join(whens)} ELSE {other} END"


def handled(c: duckdb.DuckDBPyConnection, name: str = "h") -> None:
    """A view of every row kept under the proposed handling, with its amount in amt_h."""
    c.execute(f"""CREATE OR REPLACE TEMP VIEW {name} AS SELECT *, {pair_net_sql(c)} AS amt_h FROM {all_rows()}
                  WHERE NOT list_contains({MINT_KEYS!r}, contract_transaction_unique_key) AND NOT mfa AND v <> '(no ID)'""")


def show_codes(c: duckdb.DuckDBPyConnection, col: str, fys: tuple[int, int] = (2008, 2025), limit: int = 40) -> None:
    """Print the distinct values of a code column, with row counts, for one early and one late year."""
    for fy in fys:
        res = c.execute(f"""SELECT {col} AS x, COUNT(*) FROM read_parquet('{extract_path(fy)}') GROUP BY 1
                            ORDER BY 2 DESC""").fetchall()
        shown = ", ".join(f"{x!r}: {n:,}" for x, n in res[:limit])
        print(f"  {col} FY{fy}: {len(res)} distinct. {shown}{' ...' if len(res) > limit else ''}", flush=True)


def write(name: str, rows: list[dict]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        if not rows:
            return
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows([{k: (str(v) if isinstance(v, Decimal) else v) for k, v in r.items()} for r in rows])


def q(x, e: str = "0.01"):
    return x.quantize(Decimal(e)) if isinstance(x, Decimal) else ("" if x is None else x)


def pct(a, b, e: str = "0.01"):
    return (d(a) * 100 / d(b)).quantize(Decimal(e)) if b else ""


def band(h: Decimal | None, npos: int) -> str:
    if h is None:
        return "unscored"
    if npos == 1:
        return HHI_BANDS[-1][0]
    return next(name for name, lo, hi in HHI_BANDS[:-1] if (lo is None or h > lo) and (hi is None or h <= hi))


def score(vendor_rows) -> dict[tuple, tuple]:
    """(fy, ag, psc, vendor, dollars, net) rows -> {(fy, ag, psc): (hhi or None, positive vendors, segment net)}.
    HHI is taken over the vendor dollars, the segment net is the sum of the vendor nets."""
    seg: dict[tuple, list] = defaultdict(lambda: [[], Decimal(0)])
    for fy, ag, psc, _, dollars, net in vendor_rows:
        s = seg[(fy, ag, psc)]
        s[0].append(d(dollars))
        s[1] += d(net)
    out = {}
    for k, (dollars, net) in seg.items():
        npos = sum(1 for x in dollars if x > 0)
        out[k] = (hhi(dollars) if npos else None, npos, net)
    return out


PARTS: dict = {}


def part(fn):
    PARTS[fn.__name__] = fn
    return fn


# ============================================================================================ Part 1. Vendor ID splits

SPLIT_MIN = Decimal(100_000_000)
SUFFIXES = ("INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LLC", "LP", "LTD", "THE")
# Listed by hand, from the top-100 vendor list on the shivram-eda branch (FY2023 to FY2025): firm -> (first ID, second ID).
HAND_PAIRS = {"Lockheed Martin": ("ZFN2JJXBLZT3", "JSQTW5L2SSM1"), "Optum (UnitedHealth)": ("GVW2YMAK1AC1", "XP3YPU1JDX68"),
              "McKesson": ("S1RUKWWRYFL6", "JTAPCFM4NSL4"), "General Dynamics": ("VF58HFRNGEL8", "FAZSFFE6CST9"),
              "RTX": ("PPLZG8J3N9D4", "EGAVSJTA2D81")}
UNCERTAIN = "RTX"                      # the older ID later carries the name Kidde Technologies
VA_SEGMENT = (2024, "036", "Q201")     # VA managed care, the Part 1 check
VA_HHI_BEFORE = Decimal("6991.2")      # shivram-eda, before the merges
VA_HHI_MERGED_MIN = Decimal(9000)      # estimate close to 9,600 with the two Optum IDs merged
SCENARIOS = {"before the merges": lambda line: False,
             "all merges": lambda line: True,
             "name-matched merges only": lambda line: line["source"] != "listed by hand",
             "all merges, RTX left out": lambda line: line["hand_pair"] != UNCERTAIN}

RULES |= {
    "display_name": "For each fiscal year, every vendor ID whose net under the proposed handling is $100 million or "
                    "more. A row's name is recipient_parent_name when recipient_parent_uei and recipient_parent_name "
                    "are both filled, and recipient_name otherwise. The display name is the name with the largest "
                    "summed net on the ID's rows that year (ties broken by the name in alphabetical order).",
    "normalized_name": "Upper case, every character other than a letter, a digit or a space removed, runs of spaces "
                       "collapsed to one, and the trailing words " + ", ".join(SUFFIXES) + " removed one at a time "
                       "until the name no longer ends in one.",
    "name_matched_split": "Two or more vendor IDs with $100 million or more of net and the same normalized display "
                          "name in the same year. The group's first ID is the one with the largest net. The second "
                          "ID's share is the net of every ID other than the first, divided by the group's net.",
    "first_two_words": "Two vendor IDs with $100 million or more of net in the same year whose normalized names both "
                       "have two or more words, share their first two words and are not equal. For review by hand, "
                       "never merged.",
    "merge_list": "For each year: every name-matched split, and each of the five pairs listed by hand in every year "
                  "in which both of its IDs have rows under the proposed handling, whatever their dollars. A line is "
                  "marked name-matched, listed by hand, or both. Each pair listed by hand is its own line. Within a "
                  "year, IDs joined by any chain of merges become one vendor, whose ID is the one with the largest "
                  "net that year.",
    "merge_effect": "For each year and each set of merges (" + "; ".join(SCENARIOS) + "), every segment's HHI under the "
                    "proposed handling with the merged IDs counted as one vendor, their nets summed within the "
                    "segment. Reported: segments whose band differs from the band before the merges, and the share "
                    "of dollars in segments with HHI above 2,500, for all agencies and for civilian agencies. The "
                    "denominators are the year's net under the proposed handling, all agencies or civilian, and do not "
                    "change with merges.",
    "civilian": "Every awarding agency code other than 097, the Department of Defense. A blank code counts as civilian.",
    "va_check": f"Segment {VA_SEGMENT[1]} x {VA_SEGMENT[2]} in FY{VA_SEGMENT[0]}. Its HHI before the merges, rounded to "
                f"one decimal, must equal {VA_HHI_BEFORE}. With only the two Optum IDs merged it must be "
                f"{VA_HHI_MERGED_MIN} or more.",
}


def norm_name(s: str | None) -> str:
    words = re.sub(r"[^A-Z0-9 ]", "", (s or "").upper()).split()
    while words and words[-1] in SUFFIXES:
        words.pop()
    return " ".join(words)


def roots(edges: list[tuple[str, str]], net: dict[str, Decimal]) -> dict[str, str]:
    """Union the IDs joined by edges, and map every joined ID onto the member with the largest net."""
    parent: dict[str, str] = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            x = parent[x]
        return x

    for a, b in edges:
        parent[find(a)] = find(b)
    groups = defaultdict(list)
    for x in list(parent):
        groups[find(x)].append(x)
    out = {}
    for members in groups.values():
        top = max(members, key=lambda x: (net.get(x, Decimal(0)), x))
        out |= {x: top for x in members if x != top}
    return out


def vendor_segments(c: duckdb.DuckDBPyConnection) -> None:
    c.execute("""CREATE OR REPLACE TEMP TABLE vs AS SELECT fy, awarding_agency_code AS ag, product_or_service_code AS psc, v,
                 SUM(amt_h) AS net FROM h GROUP BY ALL""")


def year_nets(c: duckdb.DuckDBPyConnection) -> dict[int, tuple[Decimal, Decimal]]:
    return {fy: (d(a), d(b)) for fy, a, b in c.execute(
        "SELECT fy, SUM(amt_h), SUM(amt_h) FILTER (WHERE awarding_agency_code IS DISTINCT FROM '097') FROM h GROUP BY 1").fetchall()}


def share_above(scores: dict[tuple, tuple], nets: tuple[Decimal, Decimal], t: int = 2500) -> tuple:
    above = [(k, net) for k, (h_, _, net) in scores.items() if h_ is not None and h_ > t]
    return (pct(sum((n for _, n in above), Decimal(0)), nets[0]),
            pct(sum((n for k, n in above if k[1] != "097"), Decimal(0)), nets[1]))


def merged_scores(rows: list[tuple], base: dict[tuple, tuple], m: dict[str, str]) -> dict[tuple, tuple]:
    """Scores with the IDs in m merged: only segments holding a merged ID are recomputed."""
    if not m:
        return base
    touched = {(fy, ag, psc) for fy, ag, psc, v, _ in rows if v in m}
    agg: dict[tuple, Decimal] = defaultdict(Decimal)
    for fy, ag, psc, v, net in rows:
        if (fy, ag, psc) in touched:
            agg[(fy, ag, psc, m.get(v, v))] += d(net)
    out = dict(base)
    out |= score((*k, n, n) for k, n in agg.items())
    return out


@part
def part1() -> None:
    c = con()
    handled(c)
    show_codes(c, "awarding_agency_code")
    show_codes(c, "product_or_service_code", limit=15)
    vendor_segments(c)
    nets = year_nets(c)
    vnet = {(fy, v): d(n) for fy, v, n in c.execute("SELECT fy, v, SUM(net) FROM vs GROUP BY ALL").fetchall()}

    # 1. display names of the IDs with $100 million or more
    named = c.execute(f"""
        WITH r AS (SELECT fy, v, amt_h, recipient_parent_name_raw AS raw,
                          CASE WHEN NULLIF(trim(recipient_parent_uei), '') IS NOT NULL AND NULLIF(trim(recipient_parent_name), '') IS NOT NULL
                               THEN recipient_parent_name ELSE recipient_name END AS name FROM h),
             big AS (SELECT fy, v, SUM(amt_h) AS net, COUNT(*) AS n FROM r GROUP BY ALL HAVING SUM(amt_h) >= {SPLIT_MIN}),
             rb AS (SELECT r.* FROM r SEMI JOIN big USING (fy, v)),
             nm AS (SELECT *, row_number() OVER (PARTITION BY fy, v ORDER BY s DESC, name) AS i
                    FROM (SELECT fy, v, name, SUM(amt_h) AS s FROM rb GROUP BY fy, v, name)),
             rw AS (SELECT *, row_number() OVER (PARTITION BY fy, v ORDER BY s DESC, raw) AS i
                    FROM (SELECT fy, v, raw, SUM(amt_h) AS s FROM rb GROUP BY fy, v, raw))
        SELECT big.fy, big.v, big.net, big.n, nm.name, rw.raw FROM big JOIN nm ON nm.fy = big.fy AND nm.v = big.v AND nm.i = 1
        JOIN rw ON rw.fy = big.fy AND rw.v = big.v AND rw.i = 1 ORDER BY big.fy, big.net DESC""").fetchall()
    ids = [{"fiscal_year": fy, "vendor_id": v, "net": q(d(net)), "rows": n, "display_name": name,
            "normalized_name": norm_name(name), "raw_parent_name_with_most_dollars": raw} for fy, v, net, n, name, raw in named]
    write("p1_vendor_display_names", ids)

    # 2. name-matched splits, and 3. first-two-word pairs for review
    by_name = defaultdict(list)
    for r in ids:
        by_name[(r["fiscal_year"], r["normalized_name"])].append(r)
    splits, lines = [], []
    for (fy, name), grp in sorted(by_name.items()):
        if len(grp) < 2 or not name:
            continue
        grp = sorted(grp, key=lambda r: (-r["net"], r["vendor_id"]))
        tot = sum((r["net"] for r in grp), Decimal(0))
        for i, r in enumerate(grp):
            splits.append({"fiscal_year": fy, "normalized_name": name, "ids_in_group": len(grp), "rank": i + 1,
                           "vendor_id": r["vendor_id"], "display_name": r["display_name"], "net": r["net"],
                           "share_of_group_pct": pct(r["net"], tot), "group_net": tot,
                           "second_id_share_pct": pct(tot - grp[0]["net"], tot)})
        lines.append({"fiscal_year": fy, "firm": name, "ids": [r["vendor_id"] for r in grp]})
    write("p1_name_matched_splits", splits)
    review = []
    for fy in years():
        yr = [r for r in ids if r["fiscal_year"] == fy and len(r["normalized_name"].split()) >= 2]
        for i, a in enumerate(yr):
            for b in yr[i + 1:]:
                if a["normalized_name"].split()[:2] == b["normalized_name"].split()[:2] and a["normalized_name"] != b["normalized_name"]:
                    review.append({"fiscal_year": fy, "first_two_words": " ".join(a["normalized_name"].split()[:2]),
                                   "vendor_id_a": a["vendor_id"], "name_a": a["display_name"], "net_a": a["net"],
                                   "vendor_id_b": b["vendor_id"], "name_b": b["display_name"], "net_b": b["net"]})
    write("p1_first_two_words_for_review", review)

    # 4. the merge list
    merge = []
    hand_ids = {frozenset(p): firm for firm, p in HAND_PAIRS.items()}
    for ln in lines:
        firm = next((f for ids_, f in hand_ids.items() if ids_ <= set(ln["ids"])), "")
        merge.append({"fiscal_year": ln["fiscal_year"], "line": ln["firm"], "hand_pair": firm, "ids": ln["ids"],
                      "source": "name-matched and listed by hand" if firm else "name-matched"})
    for firm, (a, b) in HAND_PAIRS.items():
        for fy in years():
            if (fy, a) in vnet and (fy, b) in vnet and not any(m["fiscal_year"] == fy and m["hand_pair"] == firm for m in merge):
                merge.append({"fiscal_year": fy, "line": f"{firm} (listed by hand)", "hand_pair": firm, "ids": [a, b],
                              "source": "listed by hand"})
    merge.sort(key=lambda m: (m["fiscal_year"], m["line"]))
    write("p1_merge_list", [{"fiscal_year": m["fiscal_year"], "line": m["line"], "hand_pair": m["hand_pair"], "source": m["source"],
                             "uncertain": "yes" if m["hand_pair"] == UNCERTAIN else "",
                             "ids": " + ".join(m["ids"]), "nets": " + ".join(str(q(vnet.get((m["fiscal_year"], x), Decimal(0))))
                                                                            for x in m["ids"])} for m in merge])

    # 5. HHI with the merges, and 6. the VA check
    effect, changes, va = [], [], {}
    for fy in years():
        rows = c.execute("SELECT fy, ag, psc, v, net FROM vs WHERE fy = ?", [fy]).fetchall()
        base = score((*r, r[-1]) for r in rows)
        yn = {v: n for (y, v), n in vnet.items() if y == fy}
        for sc, keep in SCENARIOS.items():
            edges = [(x, m["ids"][0]) for m in merge if m["fiscal_year"] == fy and keep(m) for x in m["ids"][1:]]
            s = merged_scores(rows, base, roots(edges, yn))
            moved = [k for k in s if band(s[k][0], s[k][1]) != band(base[k][0], base[k][1])]
            above = share_above(s, nets[fy])
            effect.append({"fiscal_year": fy, "merges": sc, "merge_lines": sum(1 for m in merge if m["fiscal_year"] == fy and keep(m)),
                           "segments": len(s), "segments_changing_band": len(moved),
                           "share_above_2500_all_pct": above[0], "share_above_2500_civilian_pct": above[1]})
            for k in moved:
                changes.append({"fiscal_year": fy, "merges": sc, "agency_code": k[1], "psc": k[2], "segment_net": q(s[k][2]),
                                "hhi_before": q(base[k][0], "0.1"), "hhi_after": q(s[k][0], "0.1"),
                                "band_before": band(base[k][0], base[k][1]), "band_after": band(s[k][0], s[k][1])})
            if fy == VA_SEGMENT[0] and sc == "before the merges":
                va["hhi_before"] = base[VA_SEGMENT][0]
        if fy == VA_SEGMENT[0]:
            optum = HAND_PAIRS["Optum (UnitedHealth)"]
            va["hhi_optum_merged"] = merged_scores(rows, base, roots([optum], yn))[VA_SEGMENT][0]
            va["second_optum_id_dollars"] = sum((d(r[4]) for r in rows if r[:3] == VA_SEGMENT and r[3] == optum[1]), Decimal(0))
            va["first_optum_id_dollars"] = sum((d(r[4]) for r in rows if r[:3] == VA_SEGMENT and r[3] == optum[0]), Decimal(0))
            va["segment_net"] = base[VA_SEGMENT][2]
        print(f"part1: FY{fy} done", flush=True)
    write("p1_merge_effect_by_year", effect)
    write("p1_segments_changing_band", changes)
    va_row = {"segment": " x ".join(map(str, VA_SEGMENT)), "hhi_before": q(va["hhi_before"], "0.1"),
              "expected_before": VA_HHI_BEFORE, "hhi_optum_merged": q(va["hhi_optum_merged"], "0.1"),
              "optum_merged_minimum": VA_HHI_MERGED_MIN, "first_optum_id_dollars": q(va["first_optum_id_dollars"]),
              "second_optum_id_dollars": q(va["second_optum_id_dollars"]), "segment_net": q(va["segment_net"])}
    write("p1_va_check", [va_row])
    print(json.dumps(va_row, default=str), flush=True)
    if q(va["hhi_before"], "0.1") != VA_HHI_BEFORE:
        raise SystemExit(f"CHECK FAILED: VA segment HHI before the merges is {q(va['hhi_before'], '0.1')}, expected {VA_HHI_BEFORE}")
    if va["hhi_optum_merged"] < VA_HHI_MERGED_MIN:
        raise SystemExit(f"CHECK FAILED: VA segment HHI with Optum merged is {q(va['hhi_optum_merged'], '0.1')}, below {VA_HHI_MERGED_MIN}")
    print("part1: VA check passed", flush=True)

    # 7. headliners for the report appendix
    eff = {(r["fiscal_year"], r["merges"]): r for r in effect}
    firms = {r["normalized_name"] for r in splits}
    top_fy = max(years(), key=lambda fy: sum(1 for r in splits if r["fiscal_year"] == fy and r["rank"] == 1))
    groups_top = sum(1 for r in splits if r["fiscal_year"] == top_fy and r["rank"] == 1)
    other_top = sum((r["net"] for r in splits if r["fiscal_year"] == top_fy and r["rank"] > 1), Decimal(0))
    move = eff[(2024, "all merges")]["share_above_2500_all_pct"] - eff[(2024, "before the merges")]["share_above_2500_all_pct"]
    text = ("# Vendor ID splits: headliners\n\nFor the report appendix, under improvements for the next round.\n\n"
            f"- Across FY{years()[0]} to FY{years()[-1]}, {len(firms)} large firms appear under two or more vendor IDs "
            "that carry the same name in the same year.\n"
            f"- The splits cluster in the last few years, and FY{top_fy} alone holds {groups_top} of these firms.\n"
            f"- In FY{top_fy} the IDs other than each firm's largest carry ${other_top / Decimal(10**9):.1f} billion.\n"
            "- Counting each split firm as one vendor raises the FY2024 share of dollars in segments with HHI above "
            f"2,500 by {move:.1f} percentage points.\n"
            "- In the VA managed care segment, counting the two Optum IDs as one vendor raises the FY2024 HHI to "
            f"{va['hhi_optum_merged']:,.0f}.\n")
    (OUT / "vendor_id_headliners.md").write_text(text, encoding="utf-8")


# ============================================================================================ Part 2. Reversal pairs

PAIR_MIN = Decimal(100_000_000)
PAIR_TOLERANCE = Decimal("0.01")              # absolute values within 1% of the larger
COUNT_THRESHOLDS = (Decimal(10_000_000), Decimal(100_000_000), Decimal(1_000_000_000))
ERROR_RATIO = 10                              # larger amount at least 10 x the award's net over all years
ERROR_CLOSE, ERROR_DAYS = Decimal("0.001"), 30
# Pairs the scan must find besides the five in PAIRS: label -> (award key part, fiscal years of the two rows).
MUST_FIND = {"KEPA-TCI JV, FY2015": ("W912QR13C0016", {2015}), "Lawrence Livermore, FY2012": ("DEAC5207NA27344", {2012}),
             "CBY Design Builders, FY2011 and FY2012": ("CBY", {2011, 2012})}
TOP_RANKED = 30                               # the largest rows across all years, ranked for the Part 2 explanation

RULES |= {
    "candidate_pair": f"Two rows of the same contract_award_unique_key, as recorded (no row left out), with opposite "
                      f"signs, each with an absolute amount of ${PAIR_MIN:,.0f} or more, whose absolute amounts differ "
                      f"by at most {PAIR_TOLERANCE * 100:.0f}% of the larger. Each row is used in at most one pair. Pairs "
                      "are taken in order of the smallest relative difference, then the fewest days between the rows, "
                      "then the transaction keys. A pair's first row is the earlier by action date (then by key).",
    "award_net": "The sum of federal_action_obligation over every row of the award in every year in the data. "
                 "total_dollars_obligated is the value on the award's row with the latest action date.",
    "entry_error": f"Test A: the larger absolute amount is at least {ERROR_RATIO} times the absolute value of the "
                   f"award's net. Test B: the absolute amounts differ by at most {ERROR_CLOSE * 100}% of the larger and "
                   f"the rows are {ERROR_DAYS} days apart or less. A pair is a likely entry error when either test marks "
                   "it, and likely normal accounting otherwise. Pairs marked by only one test are listed for review.",
    "cross_year_hhi": "For each cross-year pair, the segment of each of its rows in that row's year, HHI with every row "
                      "as recorded, and HHI with the pair's net on its first row and its second row set to zero.",
    "pair_counts": "The scan repeated with the minimum absolute amount set to " +
                   ", ".join(f"${t:,.0f}" for t in COUNT_THRESHOLDS) + ", each run matched on its own.",
    "largest_rows": f"The {TOP_RANKED} rows with the largest absolute amount across all years (ties by key), with the "
                    "pair each belongs to, for the explanation of the five pairs in integrity report version 3.",
}


def scan_pairs(c: duckdb.DuckDBPyConnection, floor: Decimal) -> list[dict]:
    cand = c.execute(f"""
        WITH r AS (SELECT contract_transaction_unique_key AS k, contract_award_unique_key AS aw, amt, action_date AS dt
                   FROM {all_rows()} WHERE abs(amt) >= {floor})
        SELECT a.k, b.k, abs(abs(a.amt) - abs(b.amt)) / greatest(abs(a.amt), abs(b.amt)) AS rel, abs(a.dt - b.dt) AS days
        FROM r a JOIN r b ON a.aw = b.aw AND a.amt > 0 AND b.amt < 0
        WHERE abs(abs(a.amt) - abs(b.amt)) <= {PAIR_TOLERANCE} * greatest(abs(a.amt), abs(b.amt))""").fetchall()
    used, out = set(), []
    for ka, kb, rel, days in sorted(cand, key=lambda x: (x[2], x[3] if x[3] is not None else 10**9, x[0], x[1])):
        if ka not in used and kb not in used:
            used |= {ka, kb}
            out.append({"pos": ka, "neg": kb, "rel": rel, "days": days})
    return out


def pair_details(c: duckdb.DuckDBPyConnection, pairs: list[dict]) -> list[dict]:
    keys = [k for p in pairs for k in (p["pos"], p["neg"])]
    c.execute("CREATE OR REPLACE TEMP TABLE pk (k VARCHAR)")
    c.executemany("INSERT INTO pk VALUES (?)", [[k] for k in keys])
    cols = ["fy", "contract_award_unique_key", "action_date", "amt", "modification_number", "action_type_code",
            "recipient_name", "awarding_agency_code", "awarding_agency_name", "product_or_service_code", "v"]
    rows = {r[0]: dict(zip(cols, r[1:])) for r in c.execute(
        f"SELECT contract_transaction_unique_key, {', '.join(cols)} FROM {all_rows()} SEMI JOIN pk ON contract_transaction_unique_key = pk.k").fetchall()}
    awards = sorted({r["contract_award_unique_key"] for r in rows.values()})
    c.execute("CREATE OR REPLACE TEMP TABLE pa (aw VARCHAR)")
    c.executemany("INSERT INTO pa VALUES (?)", [[a] for a in awards])
    aw = {a: (d(n), t, cnt) for a, n, t, cnt in c.execute(
        f"""SELECT contract_award_unique_key, SUM(amt), arg_max(total_dollars_obligated, action_date), COUNT(*) FROM {all_rows()}
            SEMI JOIN pa ON contract_award_unique_key = pa.aw GROUP BY 1""").fetchall()}
    out = []
    for p in pairs:
        a, b = sorted((p["pos"], p["neg"]), key=lambda k: (rows[k]["action_date"], k))
        ra, rb = rows[a], rows[b]
        net, tdo, n = aw[ra["contract_award_unique_key"]]
        big = max(abs(ra["amt"]), abs(rb["amt"]))
        test_a = big >= ERROR_RATIO * abs(net)
        test_b = p["rel"] <= ERROR_CLOSE and p["days"] is not None and p["days"] <= ERROR_DAYS
        out.append({"award": ra["contract_award_unique_key"], "first_key": a, "second_key": b,
                    "first_date": ra["action_date"], "second_date": rb["action_date"], "first_fy": ra["fy"], "second_fy": rb["fy"],
                    "first_amount": q(ra["amt"]), "second_amount": q(rb["amt"]), "pair_net": q(ra["amt"] + rb["amt"]),
                    "relative_difference_pct": q(p["rel"] * 100, "0.0001"), "days_between": p["days"],
                    "first_mod": ra["modification_number"], "second_mod": rb["modification_number"],
                    "first_action_type_code": ra["action_type_code"], "second_action_type_code": rb["action_type_code"],
                    "recipient": ra["recipient_name"], "vendor": ra["v"], "agency_code": ra["awarding_agency_code"],
                    "agency": ra["awarding_agency_name"], "psc": ra["product_or_service_code"],
                    "second_agency_code": rb["awarding_agency_code"], "second_psc": rb["product_or_service_code"],
                    "second_vendor": rb["v"], "award_rows_all_years": n, "award_net_all_years": q(net),
                    "award_total_dollars_obligated": tdo, "test_a_ten_times_award_net": test_a,
                    "test_b_close_and_within_30_days": test_b,
                    "group": "likely entry error" if test_a or test_b else "likely normal accounting",
                    "timing": "same year" if ra["fy"] == rb["fy"] else "cross-year", "one_test_only": test_a != test_b})
    out.sort(key=lambda r: (-max(abs(r["first_amount"]), abs(r["second_amount"])), r["first_key"]))
    return out


def segment_vendor_nets(c: duckdb.DuckDBPyConnection, segs: set[tuple], amount: str = "amt", source: str | None = None) -> dict:
    """{(fy, ag, psc): {vendor: net}} for the named segments, by default with every row as recorded."""
    c.execute("CREATE OR REPLACE TEMP TABLE sg (fy INTEGER, ag VARCHAR, psc VARCHAR)")
    c.executemany("INSERT INTO sg VALUES (?, ?, ?)", [list(s) for s in segs])
    out: dict = defaultdict(dict)
    for fy, ag, psc, v, net in c.execute(
            f"""SELECT r.fy, r.awarding_agency_code, r.product_or_service_code, r.v, SUM({amount}) FROM {source or all_rows()} r
                JOIN sg ON r.fy = sg.fy AND r.awarding_agency_code IS NOT DISTINCT FROM sg.ag
                       AND r.product_or_service_code IS NOT DISTINCT FROM sg.psc GROUP BY ALL""").fetchall():
        out[(fy, ag, psc)][v] = d(net)
    return out


@part
def part2() -> None:
    c = con()
    show_codes(c, "action_type_code")
    pairs = pair_details(c, scan_pairs(c, PAIR_MIN))
    write("p2_candidate_pairs", pairs)
    write("p2_review_one_test_only", [p for p in pairs if p["one_test_only"]])

    # 4. cross-year pairs: HHI of each affected segment as recorded and with the pair netted onto its first row
    cross = [p for p in pairs if p["timing"] == "cross-year"]
    segs = {(p["first_fy"], p["agency_code"], p["psc"]) for p in cross} | {(p["second_fy"], p["second_agency_code"], p["second_psc"]) for p in cross}
    nets = segment_vendor_nets(c, segs)
    seg_rows = []
    for p in cross:
        for which, fy, ag, psc, v, delta in (("first row", p["first_fy"], p["agency_code"], p["psc"], p["vendor"], p["second_amount"]),
                                             ("second row", p["second_fy"], p["second_agency_code"], p["second_psc"], p["second_vendor"], -p["second_amount"])):
            rec = nets[(fy, ag, psc)]
            adj = dict(rec)
            adj[v] = adj.get(v, Decimal(0)) + delta
            h_rec = hhi(list(rec.values())) if any(x > 0 for x in rec.values()) else None
            h_adj = hhi(list(adj.values())) if any(x > 0 for x in adj.values()) else None
            seg_rows.append({"award": p["award"], "group": p["group"], "row": which, "fiscal_year": fy, "agency_code": ag, "psc": psc,
                             "vendors_in_segment": len(rec), "vendor_net_as_recorded": q(rec.get(v, Decimal(0))),
                             "vendor_net_with_pair_netted": q(adj[v]), "segment_net_as_recorded": q(sum(rec.values(), Decimal(0))),
                             "segment_net_with_pair_netted": q(sum(adj.values(), Decimal(0))), "hhi_as_recorded": q(h_rec, "0.1"),
                             "hhi_with_pair_netted": q(h_adj, "0.1"), "band_as_recorded": band(h_rec, sum(1 for x in rec.values() if x > 0)),
                             "band_with_pair_netted": band(h_adj, sum(1 for x in adj.values() if x > 0))})
    write("p2_cross_year_segment_hhi", seg_rows)

    # 5. counts at three floors
    counts = []
    for t in COUNT_THRESHOLDS:
        ps = pairs if t == PAIR_MIN else pair_details(c, scan_pairs(c, t))
        for g in ("likely entry error", "likely normal accounting"):
            for tm in ("same year", "cross-year"):
                sel = [p for p in ps if p["group"] == g and p["timing"] == tm]
                counts.append({"minimum_absolute_amount": t, "group": g, "timing": tm, "pairs": len(sel),
                               "one_test_only": sum(1 for p in sel if p["one_test_only"]),
                               "gross_dollars_both_rows": q(sum((abs(p["first_amount"]) + abs(p["second_amount"]) for p in sel), Decimal(0)))})
        print(f"part2: floor {t:,.0f}: {len(ps)} pairs", flush=True)
    write("p2_counts_by_threshold", counts)

    # 6. the largest rows across all years, and which pair holds each
    in_pair = {k: p for p in pairs for k in (p["first_key"], p["second_key"])}
    listed = {k: name for name, ks in PAIRS.items() for k in ks}
    top = c.execute(f"""SELECT contract_transaction_unique_key, fy, contract_award_unique_key, modification_number, action_date, amt,
                               recipient_name FROM {all_rows()} ORDER BY abs(amt) DESC, contract_transaction_unique_key LIMIT {TOP_RANKED}""").fetchall()
    write("p2_largest_rows_all_years", [
        {"rank": i + 1, "transaction_key": k, "fiscal_year": fy, "award": a, "mod": m, "action_date": dt, "amount": q(x),
         "recipient": rn, "in_scan_pair": k in in_pair, "pair_group": in_pair[k]["group"] if k in in_pair else "",
         "listed_in_integrity_report_v3": listed.get(k, "")} for i, (k, fy, a, m, dt, x, rn) in enumerate(top)])

    # 7. the check
    found = []
    for name, (k1, k2) in PAIRS.items():
        p = in_pair.get(k1)
        found.append({"pair": name, "found": bool(p and {p["first_key"], p["second_key"]} == {k1, k2}),
                      "award": p["award"] if p else "", "group": p["group"] if p else ""})
    for name, (part_of_key, fys) in MUST_FIND.items():
        p = next((p for p in pairs if part_of_key in p["award"] + p["recipient"].upper() and {p["first_fy"], p["second_fy"]} == fys), None)
        found.append({"pair": name, "found": p is not None, "award": p["award"] if p else "", "group": p["group"] if p else ""})
    write("p2_check", found)
    for f in found:
        print(f"  check: {f['pair']}: {'found' if f['found'] else 'MISSING'} {f['award']} {f['group']}", flush=True)
    if not all(f["found"] for f in found):
        raise SystemExit("CHECK FAILED: the scan misses " + ", ".join(f["pair"] for f in found if not f["found"]))
    print(f"part2: {len(pairs)} pairs at ${PAIR_MIN:,.0f}, check passed", flush=True)


# ============================================================================================ Part 3. Net and positive only

NET_CHECK = {"share_above_2500_all_pct": {2008: Decimal("43.04"), 2024: Decimal("35.52"), 2025: Decimal("50.33")},
             "unscored": {2008: 974, 2024: 2275, 2025: 2816}}     # shivram-eda, net under the proposed handling
MEASURES = {"net": ("amt_h", "net"), "net, Part 2 pairs netted": ("amt_p", "net"),
            "positive only, proposed handling": ("amt_h", "positive"),
            "positive only, Part 2 pairs netted": ("amt_p", "positive")}
READ_POSITIVE = "positive only, Part 2 pairs netted"    # the positive-only run to read
EXAMPLES, EXAMPLE_ROWS = 5, 25

RULES |= {
    "net_measure": "A vendor's dollars in a segment are its net: the sum of its amounts under the proposed handling.",
    "positive_only": "A vendor's dollars in a segment are the sum of its positive amounts that year, returns ignored. "
                     "Run 1 uses the proposed handling alone. Run 2 also nets onto its first row every same-year pair "
                     "from Part 2 and every cross-year pair Part 2 marks as a likely entry error (the pair's net on its "
                     "first row, its second row set to zero). Run 2 is the one to read. 'net, Part 2 pairs netted' is "
                     "the net measure with the same netting, so a band change can be traced to the measure or to the "
                     "netting.",
    "unscored": "A segment is unscored when no vendor has positive dollars under the measure. Split two ways: some "
                "rows with a positive amount but no vendor with positive dollars, and no row with a positive amount at "
                "all. Under positive only, the first kind cannot occur. The segments counted are those with at least "
                "one row kept under the proposed handling.",
    "share_by_measure": "The share of dollars in segments with HHI above 2,500, weighted by the measure's own dollars: "
                        "the summed segment net over the year's net for net, and the summed positive dollars over the "
                        "year's positive dollars for positive only. A second column weights every measure by net dollars "
                        "under the proposed handling.",
    "band_change": "A segment changes band between two measures when its band (unscored included) differs.",
    "examples": f"{EXAMPLES} segments unscored under net but scored under '{READ_POSITIVE}', the largest by positive "
                f"dollars, and {EXAMPLES} unscored under both, the largest by negative net. Each with its "
                f"{EXAMPLE_ROWS} rows of largest absolute amount and its row count.",
}


def netted_pairs(c: duckdb.DuckDBPyConnection) -> list[dict]:
    """The Part 2 pairs that positive only nets: every same-year pair and every cross-year likely entry error."""
    return [p for p in pair_details(c, scan_pairs(c, PAIR_MIN))
            if p["timing"] == "same year" or p["group"] == "likely entry error"]


def score_measures(c: duckdb.DuckDBPyConnection, fy: int) -> dict[str, dict]:
    """{measure: {(ag, psc): (hhi or None, positive vendors, dollars, net, positive dollars, has a positive row)}}."""
    rows = c.execute("""SELECT awarding_agency_code, product_or_service_code, v,
                               SUM(amt_h), SUM(amt_h) FILTER (WHERE amt_h > 0), COUNT(*) FILTER (WHERE amt_h > 0),
                               SUM(amt_p), SUM(amt_p) FILTER (WHERE amt_p > 0), COUNT(*) FILTER (WHERE amt_p > 0)
                        FROM h2 WHERE fy = ? GROUP BY ALL""", [fy]).fetchall()
    out = {}
    for m, (col, kind) in MEASURES.items():
        seg: dict = defaultdict(lambda: [[], Decimal(0), Decimal(0), False])
        for ag, psc, _, nh, ph, ch, np_, pp, cp in rows:
            net, pos, cnt = (nh, ph, ch) if col == "amt_h" else (np_, pp, cp)
            s = seg[(ag, psc)]
            s[0].append(d(net) if kind == "net" else d(pos))
            s[1] += d(net)
            s[2] += d(pos)
            s[3] = s[3] or cnt > 0
        res = {}
        for k, (dollars, net, pos, has_pos) in seg.items():
            npos = sum(1 for x in dollars if x > 0)
            res[k] = (hhi(dollars) if npos else None, npos, net if kind == "net" else pos, net, pos, has_pos)
        out[m] = res
    return out


@part
def part3() -> None:
    c = con()
    handled(c)
    pairs = netted_pairs(c)
    c.execute(f"CREATE OR REPLACE TEMP VIEW h2 AS SELECT *, "
              f"{pair_net_sql(c, [(p['first_key'], p['second_key']) for p in pairs], 'amt_h')} AS amt_p FROM h")
    nets = year_nets(c)
    # weighting is by the measure's dollars; the net-weighted column uses the proposed handling's net for every measure
    out, changes, unscored_net_scored_pos, unscored_both = [], [], [], []
    for fy in years():
        s = score_measures(c, fy)
        tot = {m: (sum((v[2] for v in s[m].values()), Decimal(0)),
                   sum((v[2] for k, v in s[m].items() if k[0] != "097"), Decimal(0))) for m in MEASURES}
        for m in MEASURES:
            sm = s[m]
            above = [(k, v) for k, v in sm.items() if v[0] is not None and v[0] > 2500]
            share = lambda sel, i, t: pct(sum((v[i] for _, v in sel), Decimal(0)), t)
            civ = [(k, v) for k, v in above if k[0] != "097"]
            moved = sum(1 for k in sm if band(sm[k][0], sm[k][1]) != band(s["net"][k][0], s["net"][k][1]))
            unsc = [v for v in sm.values() if v[0] is None]
            out.append({"fiscal_year": fy, "measure": m, "segments": len(sm), "scored": len(sm) - len(unsc), "unscored": len(unsc),
                        "unscored_with_positive_rows": sum(1 for v in unsc if v[5]),
                        "unscored_no_positive_rows": sum(1 for v in unsc if not v[5]),
                        "share_above_2500_all_pct": share(above, 2, tot[m][0]), "share_above_2500_civilian_pct": share(civ, 2, tot[m][1]),
                        "share_above_2500_all_net_weighted_pct": share(above, 3, nets[fy][0]),
                        "share_above_2500_civilian_net_weighted_pct": share(civ, 3, nets[fy][1]),
                        "segments_changing_band_from_net": moved})
            if m != "net":
                for k in sm:
                    b0, b1 = band(s["net"][k][0], s["net"][k][1]), band(sm[k][0], sm[k][1])
                    if b0 != b1:
                        changes.append({"fiscal_year": fy, "measure": m, "agency_code": k[0], "psc": k[1], "band_net": b0,
                                        "band_measure": b1, "hhi_net": q(s["net"][k][0], "0.1"), "hhi_measure": q(sm[k][0], "0.1"),
                                        "segment_net": q(sm[k][3]), "segment_positive_dollars": q(sm[k][4])})
        for k, v in s["net"].items():
            if v[0] is None:
                p = s[READ_POSITIVE][k]
                (unscored_net_scored_pos if p[0] is not None else unscored_both).append((fy, *k, v[3], v[4]))
        print(f"part3: FY{fy} done", flush=True)

    by = {(r["fiscal_year"], r["measure"]): r for r in out}
    failed = [f"FY{fy} {key} is {by[(fy, 'net')][key]}, expected {want}"
              for key, exp in NET_CHECK.items() for fy, want in exp.items() if by[(fy, "net")][key] != want]
    if failed:
        raise SystemExit("CHECK FAILED: " + "; ".join(failed))
    print("part3: net check passed", flush=True)
    write("p3_measures_by_year", out)
    write("p3_segments_changing_band", changes)
    write("p3_netted_pairs", [{k: p[k] for k in ("award", "first_key", "second_key", "first_fy", "second_fy", "pair_net", "group", "timing")}
                              for p in pairs])

    # 4. example segments, each with its rows
    ex = [("unscored under net, scored under positive only", sorted(unscored_net_scored_pos, key=lambda r: -r[4])[:EXAMPLES]),
          ("unscored under both", sorted(unscored_both, key=lambda r: r[3])[:EXAMPLES])]
    seg_rows, seg_list = [], []
    for label, segs in ex:
        for fy, ag, psc, net, pos in segs:
            n = c.execute("SELECT COUNT(*) FROM h2 WHERE fy = ? AND awarding_agency_code IS NOT DISTINCT FROM ? AND product_or_service_code IS NOT DISTINCT FROM ?",
                          [fy, ag, psc]).fetchone()[0]
            seg_list.append({"example": label, "fiscal_year": fy, "agency_code": ag, "psc": psc, "segment_net": q(net),
                             "segment_positive_dollars": q(pos), "rows": n})
            for r in c.execute(f"""SELECT contract_transaction_unique_key, contract_award_unique_key, modification_number, action_date, v,
                                          recipient_name, action_type_code, amt, amt_h, amt_p FROM h2
                                   WHERE fy = ? AND awarding_agency_code IS NOT DISTINCT FROM ? AND product_or_service_code IS NOT DISTINCT FROM ?
                                   ORDER BY abs(amt) DESC, contract_transaction_unique_key LIMIT {EXAMPLE_ROWS}""", [fy, ag, psc]).fetchall():
                seg_rows.append({"example": label, "fiscal_year": fy, "agency_code": ag, "psc": psc,
                                 **dict(zip(["transaction_key", "award", "mod", "action_date", "vendor", "recipient", "action_type_code",
                                             "amount_as_recorded", "amount_proposed_handling", "amount_part2_pairs_netted"], r))})
    write("p3_example_segments", seg_list)
    write("p3_example_segment_rows", [{k: q(v) if isinstance(v, Decimal) else v for k, v in r.items()} for r in seg_rows])


# ============================================================================================ Part 4. Negative vendor totals

TERMINATION_CODES = ("E", "F", "X")           # terminate for default, for convenience, for cause
TERMINATION_BASE = range(2018, 2025)          # FY2018 to FY2024, against FY2025
AGE_BUCKETS = [("0 years", 0, 0), ("1 year", 1, 1), ("2 years", 2, 2), ("3 to 5 years", 3, 5), ("6 to 10 years", 6, 10),
               ("11 years or more", 11, None)]
PATTERN_MIN = Decimal(1_000_000)              # positive obligations of an award in the return-pattern step
LARGE_RETURN = Decimal("0.5")                 # return ratio of 50% or more
VENDOR_MIN_AWARDS, TOP_VENDORS = 10, 25
EXAMPLE_AWARD_MAX_ROWS, AWARD_ROWS_SHOWN = 40, 40
TRACE_SHOWN = 1000                            # the largest negative rows written with their trace; all rows go to WORK

RULES |= {
    "negative_vendor_total": "A vendor's total in a segment and year under the proposed handling that is below zero. "
                             "Its negative rows are its rows with a negative amount under the proposed handling.",
    "trace": "For each negative row, the award's other rows under the proposed handling with an earlier action date "
             "(strictly earlier). Earlier positive obligations are those rows with a positive amount. Reported: their "
             "dollars, the first and the most recent fiscal year with them, the fiscal years from the first of them to "
             "the row, the days from the first of them to the row, and their dollars in the row's own segment (the "
             "same awarding agency and product code, in any year).",
    "negative_source": "Each negative row falls in the first that applies: in a reversal pair from Part 2 (the scan at "
                       "$100,000,000, any group); on an award with earlier positive obligations in the data; on an award "
                       "with no earlier row in the data (likely older than FY2008); on an award with earlier rows but "
                       "none positive.",
    "action_type": "action_type_code as recorded, labelled with the most common action_type text for the code. A "
                   "blank code is labelled '(blank)'.",
    "return_age": "Fiscal years from the award's first earlier positive obligation to the negative row, in the buckets " +
                  ", ".join(b for b, _, _ in AGE_BUCKETS) + ", and 'no earlier positive obligation'.",
    "terminations": f"The share of a year's negative dollars on rows with action_type_code {', '.join(TERMINATION_CODES)} "
                    f"(terminate for default, for convenience, for cause). FY2025 against the mean of the yearly shares "
                    f"for FY{TERMINATION_BASE[0]} to FY{TERMINATION_BASE[-1]}.",
    "return_awards": f"Awards with ${PATTERN_MIN:,.0f} or more of positive obligations under the proposed handling, "
                     "leaving out the rows of the Part 2 pairs, whose earliest row in the data is the base record "
                     "(modification number 0 or blank), so the first positive obligation falls in FY2008 or later. The "
                     "stated rule (first positive obligation in FY2008 or later) holds for every award in the "
                     "data, so the count under it is reported too. An award's agency, vendor and pricing type are those "
                     "of its earliest row (its earliest positive row for the vendor), ties by key.",
    "return_ratio": f"Returned dollars (the negative amounts, as a positive number) over positive dollars. A large return "
                    f"is a ratio of {LARGE_RETURN * 100:.0f}% or more. The largest return is the most negative row. "
                    "Timing splits returned dollars by days from the first positive obligation: before it, 365 days or "
                    "fewer, and later.",
    "expected_share": f"For vendors with {VENDOR_MIN_AWARDS} or more such awards. The share of all such awards with a "
                      "large return is taken for each awarding agency x pricing type. A vendor's expected share is the "
                      "mean of those shares over its awards, and the difference is its own share minus the expected "
                      "share, in percentage points. The vendor's name is the most common display name (as in Part 1) on "
                      "its awards' earliest positive rows.",
    "worked_examples": f"The largest negative row (by absolute amount) of each kind on an award with "
                       f"{EXAMPLE_AWARD_MAX_ROWS} rows or fewer: action_type_code K (close out), F (terminate for "
                       "convenience), C (funding only), and a row on an award with no earlier row in the data, rows of Part 2 "
                       "pairs left out; plus "
                       f"the largest negative vendor total in FY2025, with its rows in the segment. Award examples "
                       f"show up to {AWARD_ROWS_SHOWN} rows."
}


def age_bucket(years_between) -> str:
    if years_between is None:
        return "no earlier positive obligation"
    return next(b for b, lo, hi in AGE_BUCKETS if years_between >= lo and (hi is None or years_between <= hi))


def award_rows(c: duckdb.DuckDBPyConnection, award: str, label: str, limit: int = AWARD_ROWS_SHOWN) -> list[dict]:
    cols = ["fy", "contract_transaction_unique_key", "modification_number", "action_date", "action_type_code", "amt",
            "awarding_agency_code", "product_or_service_code", "v", "recipient_name", "type_of_contract_pricing_code"]
    return [{"example": label, **dict(zip(cols, [q(x) if isinstance(x, Decimal) else x for x in r]))} for r in c.execute(
        f"SELECT {', '.join(cols)} FROM {all_rows()} WHERE contract_award_unique_key = ? "
        f"ORDER BY action_date, contract_transaction_unique_key LIMIT {limit}", [award]).fetchall()]


@part
def part4() -> None:
    c = con()
    handled(c)
    for col in ("action_type_code", "type_of_contract_pricing_code"):
        show_codes(c, col)
    labels = {code: lab for code, lab in c.execute("SELECT action_type_code, mode(action_type) FROM h GROUP BY 1").fetchall()}
    label = lambda code: "(blank)" if not code else (labels.get(code) or "")
    pair_keys = [k for p in pair_details(c, scan_pairs(c, PAIR_MIN)) for k in (p["first_key"], p["second_key"])]
    c.execute("CREATE OR REPLACE TEMP TABLE pair2 (k VARCHAR)")
    c.executemany("INSERT INTO pair2 VALUES (?)", [[k] for k in pair_keys])

    # 1. negative vendor totals and their negative rows
    c.execute("""CREATE OR REPLACE TEMP TABLE vt AS SELECT fy, awarding_agency_code AS ag, product_or_service_code AS psc, v,
                 SUM(amt_h) AS net, COUNT(*) AS n FROM h GROUP BY ALL HAVING SUM(amt_h) < 0""")
    c.execute("""CREATE OR REPLACE TEMP TABLE nr AS SELECT h.contract_transaction_unique_key AS k, h.contract_award_unique_key AS aw,
                 h.fy, h.action_date AS dt, vt.ag, vt.psc, h.v, h.amt_h AS amt, h.action_type_code AS atc
                 FROM h JOIN vt ON h.fy = vt.fy AND h.awarding_agency_code IS NOT DISTINCT FROM vt.ag
                 AND h.product_or_service_code IS NOT DISTINCT FROM vt.psc AND h.v = vt.v WHERE h.amt_h < 0""")
    c.execute("CREATE OR REPLACE TEMP TABLE nra AS SELECT DISTINCT aw AS contract_award_unique_key FROM nr")

    # 2. trace each negative row to its award's earlier rows
    w = "ORDER BY action_date RANGE BETWEEN UNBOUNDED PRECEDING AND INTERVAL 1 DAY PRECEDING"
    bucketed(c, "tr", f"""
        SELECT k, first_pos_fy, last_pos_fy, first_pos_dt, pos_before, rows_before, pos_before_same_segment FROM (
          SELECT contract_transaction_unique_key AS k,
                 MIN(fy) FILTER (WHERE amt_h > 0) OVER (PARTITION BY contract_award_unique_key {w}) AS first_pos_fy,
                 MAX(fy) FILTER (WHERE amt_h > 0) OVER (PARTITION BY contract_award_unique_key {w}) AS last_pos_fy,
                 MIN(action_date) FILTER (WHERE amt_h > 0) OVER (PARTITION BY contract_award_unique_key {w}) AS first_pos_dt,
                 SUM(amt_h) FILTER (WHERE amt_h > 0) OVER (PARTITION BY contract_award_unique_key {w}) AS pos_before,
                 COUNT(*) OVER (PARTITION BY contract_award_unique_key {w}) AS rows_before,
                 SUM(amt_h) FILTER (WHERE amt_h > 0) OVER (PARTITION BY contract_award_unique_key, awarding_agency_code,
                                                           product_or_service_code {w}) AS pos_before_same_segment
          FROM h SEMI JOIN nra USING (contract_award_unique_key) WHERE {{bucket}}) SEMI JOIN nr USING (k)""")
    c.execute(f"""CREATE OR REPLACE TEMP TABLE trace AS SELECT nr.*, tr.first_pos_fy, tr.last_pos_fy, tr.first_pos_dt,
                  COALESCE(tr.pos_before, 0) AS pos_before, COALESCE(tr.rows_before, 0) AS rows_before,
                  COALESCE(tr.pos_before_same_segment, 0) AS pos_before_same_segment,
                  nr.fy - tr.first_pos_fy AS years_since_first, nr.dt - tr.first_pos_dt AS days_since_first,
                  CASE WHEN nr.k IN (SELECT k FROM pair2) THEN 'in a Part 2 reversal pair'
                       WHEN COALESCE(tr.pos_before, 0) > 0 THEN 'award with earlier positive obligations'
                       WHEN COALESCE(tr.rows_before, 0) = 0 THEN 'award with no earlier row in the data'
                       ELSE 'award with earlier rows, none positive' END AS source
                  FROM nr LEFT JOIN tr USING (k)""")
    c.execute(f"COPY trace TO '{WORK / 'p4_negative_row_trace.parquet'}' (FORMAT parquet, COMPRESSION zstd)")
    n_nr, n_tr = c.execute("SELECT (SELECT COUNT(*) FROM nr), (SELECT COUNT(*) FROM trace)").fetchone()
    if n_nr != n_tr:
        raise SystemExit(f"trace lost rows: {n_nr} negative rows, {n_tr} traced")
    cols = [x[0] for x in c.execute("SELECT * FROM trace LIMIT 0").description]
    write("p4_negative_row_trace_largest", [dict(zip(cols, [q(x) if isinstance(x, Decimal) else x for x in r])) for r in c.execute(
        f"SELECT * FROM trace ORDER BY amt, k LIMIT {TRACE_SHOWN}").fetchall()])
    print(f"part4: {n_nr:,} negative rows traced", flush=True)

    # 1 and 3. by year: totals, and the three-way (four-way) split of negative dollars
    write("p4_negative_totals_by_year", [
        {"fiscal_year": fy, "negative_vendor_totals": n, "negative_vendor_total_net": q(d(net)), "rows_in_them": rows,
         "negative_rows": nn, "negative_row_dollars": q(d(nd)),
         "negative_rows_earlier_money_same_segment": same, "negative_rows_earlier_money_other_segment_only": other}
        for fy, n, net, rows, nn, nd, same, other in c.execute("""
            SELECT fy, n, net, rows, nn, nd, same, other FROM
              (SELECT fy, COUNT(*) AS n, SUM(net) AS net, SUM(n) AS rows FROM vt GROUP BY 1)
            JOIN (SELECT fy, COUNT(*) AS nn, SUM(amt) AS nd, COUNT(*) FILTER (WHERE pos_before_same_segment > 0) AS same,
                         COUNT(*) FILTER (WHERE pos_before > 0 AND pos_before_same_segment = 0) AS other FROM trace GROUP BY 1) USING (fy)
            ORDER BY fy""").fetchall()])
    by_src = c.execute("SELECT fy, source, COUNT(*), SUM(amt) FROM trace GROUP BY ALL ORDER BY 1, 2").fetchall()
    tot = defaultdict(Decimal)
    for fy, _, _, s in by_src:
        tot[fy] += d(s)
    write("p4_negative_dollars_by_source", [{"fiscal_year": fy, "source": src, "rows": n, "dollars": q(d(s)),
                                             "share_of_negative_dollars_pct": pct(s, tot[fy])} for fy, src, n, s in by_src])

    # 4. by action type
    by_at = c.execute("SELECT fy, atc, COUNT(*), SUM(amt) FROM trace GROUP BY ALL ORDER BY 1, 4").fetchall()
    rows_fy = dict(c.execute("SELECT fy, COUNT(*) FROM trace GROUP BY 1").fetchall())
    write("p4_negative_by_action_type", [{"fiscal_year": fy, "action_type_code": code, "label": label(code), "rows": n,
                                          "dollars": q(d(s)), "share_of_rows_pct": pct(n, rows_fy[fy]),
                                          "share_of_dollars_pct": pct(s, tot[fy])} for fy, code, n, s in by_at])

    # 5. the age of returns, and terminations in FY2025
    ages = defaultdict(lambda: [0, Decimal(0)])
    for fy, yrs, n, s in c.execute("SELECT fy, years_since_first, COUNT(*), SUM(amt) FROM trace GROUP BY ALL").fetchall():
        a = ages[(fy, age_bucket(yrs))]
        a[0] += n
        a[1] += d(s)
    order = [b for b, _, _ in AGE_BUCKETS] + ["no earlier positive obligation"]
    write("p4_return_age_by_year", [{"fiscal_year": fy, "years_since_first_positive_obligation": b, "rows": ages[(fy, b)][0],
                                     "dollars": q(ages[(fy, b)][1]), "share_of_negative_dollars_pct": pct(ages[(fy, b)][1], tot[fy])}
                                    for fy in years() for b in order])
    term = {fy: d(s) for fy, s in c.execute(
        f"SELECT fy, SUM(amt) FILTER (WHERE list_contains({list(TERMINATION_CODES)!r}, atc)) FROM trace GROUP BY 1").fetchall()}
    term_rows = [{"fiscal_year": fy, "termination_dollars": q(term[fy]), "negative_dollars": q(tot[fy]),
                  "termination_share_pct": pct(term[fy], tot[fy])} for fy in years()]
    base = [r["termination_share_pct"] for r in term_rows if r["fiscal_year"] in TERMINATION_BASE]
    term_rows.append({"fiscal_year": f"mean of FY{TERMINATION_BASE[0]} to FY{TERMINATION_BASE[-1]}", "termination_dollars": "",
                      "negative_dollars": "", "termination_share_pct": q(sum(base, Decimal(0)) / len(base))})
    write("p4_terminations_by_year", term_rows)

    # 6. return patterns by award and vendor
    names = """CASE WHEN NULLIF(trim(recipient_parent_uei), '') IS NOT NULL AND NULLIF(trim(recipient_parent_name), '') IS NOT NULL
                    THEN recipient_parent_name ELSE recipient_name END"""
    bucketed(c, "aw", f"""
        WITH r AS (SELECT *, MIN(fy) FILTER (WHERE amt_h > 0) OVER (PARTITION BY contract_award_unique_key) AS fpf,
                          MIN(action_date) FILTER (WHERE amt_h > 0) OVER (PARTITION BY contract_award_unique_key) AS fpd
                   FROM h WHERE {{bucket}} AND contract_transaction_unique_key NOT IN (SELECT k FROM pair2))
        SELECT contract_award_unique_key AS award, SUM(amt_h) FILTER (WHERE amt_h > 0) AS pos,
               -COALESCE(SUM(amt_h) FILTER (WHERE amt_h < 0), 0) AS ret, MIN(fpf) AS first_fy, MIN(fpd) AS first_dt,
               SUM(amt_h) FILTER (WHERE amt_h > 0 AND fy = fpf) AS pos_first_fy,
               arg_min(modification_number, (action_date, contract_transaction_unique_key)) AS first_mod,
               arg_min(awarding_agency_code, (action_date, contract_transaction_unique_key)) AS agency,
               arg_min(type_of_contract_pricing_code, (action_date, contract_transaction_unique_key)) AS pricing,
               arg_min(v, (action_date, contract_transaction_unique_key)) FILTER (WHERE amt_h > 0) AS vendor,
               arg_min({names}, (action_date, contract_transaction_unique_key)) FILTER (WHERE amt_h > 0) AS vendor_name,
               arg_min(action_date, (amt_h, contract_transaction_unique_key)) FILTER (WHERE amt_h < 0) AS big_ret_dt,
               arg_min(action_type_code, (amt_h, contract_transaction_unique_key)) FILTER (WHERE amt_h < 0) AS big_ret_atc,
               -COALESCE(SUM(amt_h) FILTER (WHERE amt_h < 0 AND action_date < fpd), 0) AS ret_before,
               -COALESCE(SUM(amt_h) FILTER (WHERE amt_h < 0 AND action_date - fpd BETWEEN 0 AND 365), 0) AS ret_1y,
               -COALESCE(SUM(amt_h) FILTER (WHERE amt_h < 0 AND action_date - fpd > 365), 0) AS ret_later,
               COUNT(*) AS rows
        FROM r GROUP BY 1 HAVING SUM(amt_h) FILTER (WHERE amt_h > 0) >= {PATTERN_MIN}""")
    literal = c.execute("SELECT COUNT(*) FROM aw").fetchone()[0]
    cols = [x[0] for x in c.execute("SELECT * FROM aw LIMIT 0").description]
    awards = [dict(zip(cols, r)) for r in c.execute("SELECT * FROM aw WHERE first_mod IN ('0', '') ORDER BY award").fetchall()]
    for a in awards:
        a["ratio"] = d(a["ret"]) / d(a["pos"])
        a["large"] = a["ratio"] >= LARGE_RETURN
    print(f"part4: {literal:,} awards with ${PATTERN_MIN:,.0f} or more, {len(awards):,} begun in the data", flush=True)
    write("p4_return_awards_largest", [
        {"award": a["award"], "vendor": a["vendor"], "vendor_name": a["vendor_name"], "agency_code": a["agency"],
         "pricing_code": a["pricing"], "first_fy": a["first_fy"], "positive_dollars": q(d(a["pos"])), "returned_dollars": q(d(a["ret"])),
         "return_ratio_pct": q(a["ratio"] * 100), "share_of_positive_in_first_fy_pct": pct(a["pos_first_fy"], a["pos"]),
         "days_first_obligation_to_largest_return": (a["big_ret_dt"] - a["first_dt"]).days if a["big_ret_dt"] and a["first_dt"] else "",
         "largest_return_action_type_code": a["big_ret_atc"], "rows": a["rows"]}
        for a in sorted(awards, key=lambda a: -d(a["ret"]))[:TRACE_SHOWN]])
    cell = defaultdict(lambda: [0, 0])
    for a in awards:
        cell[(a["agency"], a["pricing"])][0] += 1
        cell[(a["agency"], a["pricing"])][1] += a["large"]
    rate = {k: Decimal(v[1]) / v[0] for k, v in cell.items()}
    for dim, key in (("agency", "agency"), ("pricing", "pricing")):
        g = defaultdict(lambda: [0, 0, Decimal(0), Decimal(0)])
        for a in awards:
            x = g[a[key]]
            x[0] += 1
            x[1] += a["large"]
            x[2] += d(a["pos"])
            x[3] += d(a["ret"])
        write(f"p4_large_returns_by_{dim}", [{dim: k, "awards": n, "awards_with_large_return": lg, "share_large_pct": pct(lg, n),
                                              "positive_dollars": q(p), "returned_dollars": q(r), "returned_over_positive_pct": pct(r, p)}
                                             for k, (n, lg, p, r) in sorted(g.items(), key=lambda kv: -kv[1][0])])
    vend = defaultdict(list)
    for a in awards:
        vend[a["vendor"]].append(a)
    vrows = []
    for v, aws in vend.items():
        if len(aws) < VENDOR_MIN_AWARDS:
            continue
        share = Decimal(sum(a["large"] for a in aws)) * 100 / len(aws)
        expected = sum((rate[(a["agency"], a["pricing"])] for a in aws), Decimal(0)) * 100 / len(aws)
        ratios = sorted(a["ratio"] for a in aws)
        med = ratios[len(ratios) // 2] if len(ratios) % 2 else (ratios[len(ratios) // 2 - 1] + ratios[len(ratios) // 2]) / 2
        nm = defaultdict(int)
        for a in aws:
            nm[a["vendor_name"]] += 1
        vrows.append({"vendor": v, "vendor_name": max(nm, key=lambda x: (nm[x], x or "")), "awards": len(aws),
                      "awards_with_large_return": sum(a["large"] for a in aws), "share_large_pct": q(share),
                      "expected_share_pct": q(expected), "difference_points": q(share - expected),
                      "positive_dollars": q(sum((d(a["pos"]) for a in aws), Decimal(0))),
                      "returned_dollars": q(sum((d(a["ret"]) for a in aws), Decimal(0))), "median_return_ratio_pct": q(med * 100)})
    vrows.sort(key=lambda r: (-r["returned_dollars"], r["vendor"]))
    write("p4_vendor_return_patterns", vrows)
    top_ret = vrows[:TOP_VENDORS]
    top_diff = sorted(vrows, key=lambda r: (-r["difference_points"], r["vendor"]))[:TOP_VENDORS]
    write("p4_top_vendors_by_returned_dollars", top_ret)
    write("p4_top_vendors_by_difference", top_diff)
    timing = [("before the first positive obligation", "ret_before"), ("365 days or fewer", "ret_1y"), ("later", "ret_later")]
    ret_all = sum((d(a["ret"]) for a in awards), Decimal(0))
    write("p4_return_timing", [{"timing": t, "returned_dollars": q(s), "share_pct": pct(s, ret_all)}
                               for t, col in timing for s in [sum((d(a[col]) for a in awards), Decimal(0))]])
    write("p4_return_award_counts", [
        {"awards": "positive obligations of the minimum or more (the literal rule)", "count": literal},
        {"awards": "of those, begun in the data (earliest row is the base record)", "count": len(awards)},
        {"awards": "of those, with a large return", "count": sum(a["large"] for a in awards)},
        {"awards": f"vendors with {VENDOR_MIN_AWARDS} or more such awards", "count": len(vrows)}])
    ex_awards, seen = [], set()
    for v in [r["vendor"] for r in top_ret[:3]] + [r["vendor"] for r in top_diff if r["vendor"] not in {x["vendor"] for x in top_ret[:3]}][:2]:
        a = max((a for a in vend[v] if a["large"]), key=lambda a: (d(a["ret"]), a["award"]), default=None)
        if a and a["award"] not in seen:
            seen.add(a["award"])
            ex_awards += award_rows(c, a["award"], f"vendor {v}: award {a['award']}, return ratio {a['ratio'] * 100:.1f}%")
    write("p4_return_pattern_examples", ex_awards)

    # 7. worked examples
    examples = []
    for lab, cond in (("close out (K)", "atc = 'K'"), ("termination for convenience (F)", "atc = 'F'"),
                      ("funding only (C)", "atc = 'C'"), ("award older than the data", "source = 'award with no earlier row in the data'")):
        k, aw = c.execute(f"""SELECT k, aw FROM trace WHERE {cond} AND source <> 'in a Part 2 reversal pair' AND aw IN (SELECT contract_award_unique_key FROM {all_rows()}
                              GROUP BY 1 HAVING COUNT(*) <= {EXAMPLE_AWARD_MAX_ROWS}) ORDER BY amt, k LIMIT 1""").fetchone()
        examples += award_rows(c, aw, f"{lab}: row {k}")
    fy, ag, psc, v, net = c.execute("SELECT fy, ag, psc, v, net FROM vt WHERE fy = 2025 ORDER BY net, v LIMIT 1").fetchone()
    cols = ["fy", "contract_transaction_unique_key", "modification_number", "action_date", "action_type_code", "amt",
            "awarding_agency_code", "product_or_service_code", "v", "recipient_name", "type_of_contract_pricing_code"]
    examples += [{"example": f"largest negative vendor total in FY2025: {ag} x {psc}, vendor {v}, net {q(d(net))}",
                  **dict(zip(cols, [q(x) if isinstance(x, Decimal) else x for x in r]))} for r in c.execute(
        f"""SELECT {', '.join(cols[:5])}, amt_h, {', '.join(cols[6:])} FROM h WHERE fy = ? AND awarding_agency_code IS NOT DISTINCT FROM ?
            AND product_or_service_code IS NOT DISTINCT FROM ? AND v = ? ORDER BY abs(amt_h) DESC LIMIT {AWARD_ROWS_SHOWN}""",
        [fy, ag, psc, v]).fetchall()]
    write("p4_worked_examples", examples)


# ============================================================================================ Part 5. Small actions

SMALL = 10_000
SMALL_BANDS = [("below $3,000", "amt > 0 AND amt < 3000"), ("$3,000 to under $3,500", "amt >= 3000 AND amt < 3500"),
               ("$3,500 to under $10,000", "amt >= 3500 AND amt < 10000"), ("$10,000 and over", "amt >= 10000"),
               ("zero", "amt = 0"), ("negative", "amt < 0"), ("unparseable", "amt IS NULL")]
BUNCH_LIMITS, BIN, BINS_BELOW, BINS_ABOVE = (3000, 3500, 10000), 100, 10, 5
# The micro-purchase thresholds in the table of integrity report version 3, by action date.
LIMIT_SQL = ("CASE WHEN fy <= 2015 THEN 3000 WHEN fy <= 2019 THEN 3500 "
             "WHEN fy = 2020 AND action_date < DATE '2020-08-31' THEN 3500 ELSE 10000 END")
SPLIT_EXAMPLE_YEARS, SPLIT_EXAMPLE_MAX = (2010, 2014, 2018, 2022, 2025), 5
TOP_SMALL = 10

RULES |= {
    "small_rows": "Every row as recorded (no row left out, no pair netted). A small action is a row with an amount "
                  f"above zero and under ${SMALL:,}. Bands: " + "; ".join(b for b, _ in SMALL_BANDS) + ".",
    "bunching": f"For each limit ({', '.join(f'${x:,}' for x in BUNCH_LIMITS)}), rows counted in ${BIN} bins that "
                f"include their upper end, (limit - {BIN}, limit] and so on, {BINS_BELOW} bins below the limit and "
                f"{BINS_ABOVE} above. The ratio is the bin just below, (limit - {BIN}, limit], over the bin just above, "
                f"(limit, limit + {BIN}]. Bins include their upper end because the threshold is a ceiling not to be "
                "exceeded. Rows exactly at the limit are also counted on their own, and a second ratio leaves them out "
                "of the bin just below, since round amounts gather there whatever the limit.",
    "split_purchases": "Groups of two or more rows with the same vendor, the same awarding sub-agency code and the "
                       "same action date, each with an amount above zero and at or below the limit in force on its "
                       "date, whose amounts sum to more than that limit. The limits follow the table in integrity "
                       "report version 3: $3,000 for FY2008 to FY2015, $3,500 for FY2016 to FY2019 and for FY2020 "
                       "actions before 2020-08-31, and $10,000 from 2020-08-31 and for FY2021 to FY2025. The Defense "
                       "thresholds noted below that table are not applied. The vendor '(no ID)' and MISCELLANEOUS "
                       "FOREIGN AWARDEES rows are left out, since neither is one vendor. 'At or below' reads the "
                       "stated 'under' as within the limit, the same ceiling as for bunching. Examples: in each of "
                       f"{', '.join(f'FY{y}' for y in SPLIT_EXAMPLE_YEARS)}, the group of {SPLIT_EXAMPLE_MAX} rows or "
                       "fewer with the largest sum.",
    "small_vendors": f"By year, the {TOP_SMALL} vendors (the VENDOR expression) with the most dollars in small "
                     "actions, with their share of all small-action dollars that year. Names as in Part 1.",
}


def small_figure(rows: list[dict]) -> str:
    from .report_pdf import BLUE, HATCH, svg
    from .report_pdf import bar_panel
    fys = [r["fiscal_year"] for r in rows]
    a = bar_panel(0, 0, 690, 190, fys, [float(r["share_of_rows_pct"]) for r in rows],
                  "Share of rows in actions under $10,000 (%)", lambda t: f"{t:g}", lambda v: f"{v:.1f}", BLUE)
    b = bar_panel(0, 210, 690, 190, fys, [float(r["share_of_dollars_pct"]) for r in rows],
                  "Share of net dollars in actions under $10,000 (%)", lambda t: f"{t:g}", lambda v: f"{v:.2f}", BLUE)
    return svg(690, 400, HATCH + a + b)


@part
def part5() -> None:
    c = con()
    for col in ("awarding_sub_agency_code", "award_type_code", "idv_type_code"):
        show_codes(c, col, limit=20)
    c.execute(f"CREATE OR REPLACE TEMP VIEW r AS SELECT * FROM {all_rows()}")
    tot = {fy: (n, d(s)) for fy, n, s in c.execute("SELECT fy, COUNT(*), SUM(amt) FROM r GROUP BY 1").fetchall()}

    # 1. bands
    band_sql = "CASE " + " ".join(f"WHEN {cond} THEN '{b}'" for b, cond in SMALL_BANDS) + " END"
    res = {(fy, b): (n, d(s)) for fy, b, n, s in c.execute(f"SELECT fy, {band_sql}, COUNT(*), SUM(amt) FROM r GROUP BY ALL").fetchall()}
    write("p5_bands_by_year", [{"fiscal_year": fy, "band": b, "rows": res.get((fy, b), (0, 0))[0],
                                "net": q(res.get((fy, b), (0, Decimal(0)))[1]),
                                "share_of_rows_pct": pct(res.get((fy, b), (0, 0))[0], tot[fy][0]),
                                "share_of_net_pct": pct(res.get((fy, b), (0, Decimal(0)))[1], tot[fy][1], "0.001")}
                               for fy in years() for b, _ in SMALL_BANDS])
    small = f"amt > 0 AND amt < {SMALL}"

    # 2. sub-agencies, and award and vehicle types
    write("p5_top_subagencies_by_year", [
        {"fiscal_year": fy, "rank": i, "awarding_sub_agency_code": code, "awarding_sub_agency_name": name, "small_rows": n,
         "small_dollars": q(d(s)), "share_of_year_small_rows_pct": pct(n, ny)}
        for fy, i, code, name, n, s, ny in c.execute(f"""
            SELECT fy, i, code, name, n, s, ny FROM (
              SELECT fy, awarding_sub_agency_code AS code, mode(awarding_sub_agency_name) AS name, COUNT(*) AS n, SUM(amt) AS s,
                     SUM(COUNT(*)) OVER (PARTITION BY fy) AS ny, row_number() OVER (PARTITION BY fy ORDER BY COUNT(*) DESC, awarding_sub_agency_code) AS i
              FROM r WHERE {small} GROUP BY fy, awarding_sub_agency_code) WHERE i <= {TOP_SMALL} ORDER BY fy, i""").fetchall()])
    write("p5_small_rows_by_type", [
        {"fiscal_year": fy, "award_type_code": at, "idv_type_code": it, "small_rows": n, "small_dollars": q(d(s)),
         "share_of_year_small_rows_pct": pct(n, ny)}
        for fy, at, it, n, s, ny in c.execute(f"""
            SELECT fy, award_type_code, idv_type_code, COUNT(*), SUM(amt), SUM(COUNT(*)) OVER (PARTITION BY fy) FROM r WHERE {small}
            GROUP BY fy, award_type_code, idv_type_code ORDER BY 1, 4 DESC""").fetchall()])

    # 3. bunching below each limit
    bunch = []
    for lim in BUNCH_LIMITS:
        lo = lim - BINS_BELOW * BIN
        hi = lim + BINS_ABOVE * BIN
        counts = defaultdict(int)
        for fy, b, n in c.execute(f"""SELECT fy, CAST(ceil((amt - {lo}) / {BIN}) AS INTEGER), COUNT(*) FROM r
                                      WHERE amt > {lo} AND amt <= {hi} GROUP BY ALL""").fetchall():
            counts[(fy, b)] = n
        at = dict(c.execute(f"SELECT fy, COUNT(*) FROM r WHERE amt = {lim} GROUP BY 1").fetchall())
        for fy in years():
            below, above = counts[(fy, BINS_BELOW)], counts[(fy, BINS_BELOW + 1)]
            row = {"limit": lim, "fiscal_year": fy, "rows_exactly_at_limit": at.get(fy, 0), "bin_just_below": below,
                   "bin_just_above": above, "ratio_below_over_above": q(Decimal(below) / above, "0.01") if above else "",
                   "ratio_without_rows_exactly_at_limit": q(Decimal(below - at.get(fy, 0)) / above, "0.01") if above else ""}
            for i in range(1, BINS_BELOW + BINS_ABOVE + 1):
                row[f"bin_limit{(i - 1 - BINS_BELOW) * BIN:+d}_to_limit{(i - BINS_BELOW) * BIN:+d}"] = counts[(fy, i)]
            bunch.append(row)
    write("p5_bunching_by_year", bunch)

    # 4. possible split purchases
    c.execute(f"""CREATE OR REPLACE TEMP TABLE sp AS
                  SELECT fy, v, awarding_sub_agency_code AS sub, action_date, lim, COUNT(*) AS n, SUM(amt) AS s, list(contract_transaction_unique_key) AS keys
                  FROM (SELECT *, {LIMIT_SQL} AS lim FROM r WHERE amt > 0 AND v <> '(no ID)' AND NOT mfa)
                  WHERE amt <= lim GROUP BY fy, v, awarding_sub_agency_code, action_date, lim HAVING COUNT(*) >= 2""")
    write("p5_split_purchase_groups_by_year", [
        {"fiscal_year": fy, "limit": lims, "same_day_groups_of_two_or_more": g_all, "groups_summing_above_limit": g, "rows_in_them": n,
         "dollars_in_them": q(d(s)), "share_of_groups_pct": pct(g, g_all)}
        for fy, lims, g_all, g, n, s in c.execute("""
            SELECT fy, string_agg(DISTINCT CAST(lim AS VARCHAR), ' then '), COUNT(*), COUNT(*) FILTER (WHERE s > lim),
                   SUM(n) FILTER (WHERE s > lim), SUM(s) FILTER (WHERE s > lim) FROM sp GROUP BY 1 ORDER BY 1""").fetchall()])
    ex = []
    for fy in SPLIT_EXAMPLE_YEARS:
        g = c.execute(f"""SELECT v, sub, action_date, lim, n, s, keys FROM sp WHERE fy = ? AND s > lim AND n <= {SPLIT_EXAMPLE_MAX}
                          ORDER BY s DESC, v LIMIT 1""", [fy]).fetchone()
        if not g:
            continue
        label = f"FY{fy}: vendor {g[0]}, sub-agency {g[1]}, {g[2]}, {g[4]} rows summing to {q(d(g[5]))} against a limit of {g[3]:,}"
        for r in c.execute("""SELECT contract_transaction_unique_key, contract_award_unique_key, modification_number, action_date, amt,
                                     recipient_name, awarding_sub_agency_name, product_or_service_code, award_type_code, idv_type_code
                              FROM r WHERE fy = ? AND list_contains(?, contract_transaction_unique_key) ORDER BY contract_transaction_unique_key""",
                           [fy, g[6]]).fetchall():
            ex.append({"example": label, **dict(zip(["transaction_key", "award", "mod", "action_date", "amount", "recipient",
                                                      "sub_agency", "psc", "award_type_code", "idv_type_code"], [q(x) for x in r]))})
    write("p5_split_purchase_examples", ex)

    # 5. vendors with the most small-action dollars
    names = """CASE WHEN NULLIF(trim(recipient_parent_uei), '') IS NOT NULL AND NULLIF(trim(recipient_parent_name), '') IS NOT NULL
                    THEN recipient_parent_name ELSE recipient_name END"""
    write("p5_top_vendors_small_dollars", [
        {"fiscal_year": fy, "rank": i, "vendor": v, "name": nm, "small_rows": n, "small_dollars": q(d(s)), "share_of_small_dollars_pct": pct(s, sy)}
        for fy, i, v, nm, n, s, sy in c.execute(f"""
            SELECT fy, i, v, nm, n, s, sy FROM (
              SELECT fy, v, mode({names}) AS nm, COUNT(*) AS n, SUM(amt) AS s, SUM(SUM(amt)) OVER (PARTITION BY fy) AS sy,
                     row_number() OVER (PARTITION BY fy ORDER BY SUM(amt) DESC, v) AS i
              FROM r WHERE {small} GROUP BY fy, v) WHERE i <= {TOP_SMALL} ORDER BY fy, i""").fetchall()])

    # 6. the figure
    share = [{"fiscal_year": fy, "small_rows": n, "small_dollars": q(d(s)), "share_of_rows_pct": pct(n, tot[fy][0]),
              "share_of_dollars_pct": pct(s, tot[fy][1], "0.001")}
             for fy, n, s in c.execute(f"SELECT fy, COUNT(*), SUM(amt) FROM r WHERE {small} GROUP BY 1 ORDER BY 1").fetchall()]
    write("p5_small_share_by_year", share)
    (OUT / "p5_small_share_by_year.svg").write_text(small_figure(share), encoding="utf-8")


# ============================================================================================ Part 6. MISCELLANEOUS FOREIGN AWARDEES

MFA_BY_YEAR = config.INTEGRITY_REPORTS_DIR / "v2" / "mfa_by_year.csv"
MFA_SHARES = (Decimal("0.10"), Decimal("0.50"))
MFA_TOP_AGENCIES, MFA_TOP_COUNTRIES, MFA_TOP_COUNTRIES_YEAR, MFA_HIGH_YEARS = 5, 10, 3, 3
MFA_EXAMPLE_YEARS = (2008, 2012, 2016, 2020, 2025)

RULES |= {
    "mfa": "Rows matching the MFA expression of src/analyses_v2.py (recipient_name trimmed and upper case equal to "
           "MISCELLANEOUS FOREIGN AWARDEES), every row as recorded. The check compares rows, net and share of net by "
           f"year with {MFA_BY_YEAR.name} of integrity report version 2, at that file's rounding.",
    "mfa_shares": "Shares of the year's rows, distinct awards (contract_award_unique_key) and net, and of the net of "
                  "awarding agency 097. Segments with the placeholder hold at least one of its rows. Its share of a "
                  "segment is its net over the segment's net, for segments with a positive net, counted at "
                  + " and ".join(f"{x * 100:.0f}% or more" for x in MFA_SHARES) + ".",
    "mfa_countries": "primary_place_of_performance_country_code, named by the most common "
                     "primary_place_of_performance_country_name for the code. A blank code is '(blank)'.",
    "mfa_high_years": f"The {MFA_HIGH_YEARS} years with the highest share of net are marked.",
    "mfa_examples": "In each of " + ", ".join(f"FY{y}" for y in MFA_EXAMPLE_YEARS) + ", the placeholder row with the "
                    "largest positive amount, with its two description fields read from the Stage 1 mirror.",
}


@part
def part6() -> None:
    c = con()
    for col in ("awarding_agency_code", "awarding_sub_agency_code", "primary_place_of_performance_country_code",
                "award_type_code", "idv_type_code"):
        show_codes(c, col, limit=15)
    c.execute(f"CREATE OR REPLACE TEMP VIEW r AS SELECT * FROM {all_rows()}")

    # 1. the check against integrity report version 2
    ref = {int(x["fiscal_year"]): x for x in csv.DictReader(open(MFA_BY_YEAR, encoding="utf-8"))}
    got = c.execute("SELECT fy, COUNT(*) FILTER (WHERE mfa), SUM(amt) FILTER (WHERE mfa), SUM(amt) FROM r GROUP BY 1 ORDER BY 1").fetchall()
    bad = []
    for fy, n, net, tot in got:
        mine = (str(n), str(q(d(net))), str(pct(net, tot, "0.001")))
        theirs = (ref[fy]["rows"], ref[fy]["net"], ref[fy]["share_of_year_net_pct"])
        if mine != theirs:
            bad.append(f"FY{fy}: {mine} against {theirs}")
    if bad or set(ref) != {g[0] for g in got}:
        raise SystemExit("CHECK FAILED: placeholder by year differs from integrity report version 2: " + "; ".join(bad))
    print("part6: check against mfa_by_year.csv passed", flush=True)

    # 2. by year
    rows = c.execute("""
        WITH seg AS (SELECT fy, awarding_agency_code, product_or_service_code, SUM(amt) AS net, SUM(amt) FILTER (WHERE mfa) AS m,
                            COUNT(*) FILTER (WHERE mfa) AS mr FROM r GROUP BY ALL)
        SELECT y.*, s.segs, s.s10, s.s50 FROM (
          SELECT fy, COUNT(*) FILTER (WHERE mfa) AS rows, COUNT(DISTINCT contract_award_unique_key) FILTER (WHERE mfa) AS awards,
                 SUM(amt) FILTER (WHERE mfa) AS net, COUNT(*) AS all_rows, COUNT(DISTINCT contract_award_unique_key) AS all_awards,
                 SUM(amt) AS all_net, SUM(amt) FILTER (WHERE mfa AND awarding_agency_code = '097') AS dod_m,
                 SUM(amt) FILTER (WHERE awarding_agency_code = '097') AS dod FROM r GROUP BY 1) y
        JOIN (SELECT fy, COUNT(*) FILTER (WHERE mr > 0) AS segs,
                     COUNT(*) FILTER (WHERE mr > 0 AND net > 0 AND m >= ? * net) AS s10,
                     COUNT(*) FILTER (WHERE mr > 0 AND net > 0 AND m >= ? * net) AS s50 FROM seg GROUP BY 1) s USING (fy)
        ORDER BY fy""", [float(MFA_SHARES[0]), float(MFA_SHARES[1])]).fetchall()
    by_year = [{"fiscal_year": fy, "rows": n, "awards": a, "net": q(d(net)), "share_of_rows_pct": pct(n, an, "0.001"),
                "share_of_awards_pct": pct(a, aa, "0.001"), "share_of_net_pct": pct(net, anet, "0.001"),
                "share_of_defense_net_pct": pct(dm, dod, "0.001"), "segments_with_placeholder": segs,
                "segments_10pct_or_more": s10, "segments_50pct_or_more": s50}
               for fy, n, a, net, an, aa, anet, dm, dod, segs, s10, s50 in rows]
    high = sorted(by_year, key=lambda r: -r["share_of_net_pct"])[:MFA_HIGH_YEARS]
    for r in by_year:
        r["among_highest_shares"] = "yes" if r in high else ""
    write("p6_mfa_by_year", by_year)

    # 3. agencies and sub-agencies, 4. countries, 5. types
    for name, col, label in (("agencies", "awarding_agency_code", "awarding_agency_name"),
                             ("subagencies", "awarding_sub_agency_code", "awarding_sub_agency_name")):
        write(f"p6_mfa_top_{name}_by_year", [
            {"fiscal_year": fy, "rank": i, "code": code, "name": nm, "rows": n, "net": q(d(s)), "share_of_placeholder_net_pct": pct(s, t)}
            for fy, i, code, nm, n, s, t in c.execute(f"""
                SELECT * FROM (SELECT fy, row_number() OVER (PARTITION BY fy ORDER BY SUM(amt) DESC, {col}) AS i, {col}, mode({label}),
                                      COUNT(*), SUM(amt), SUM(SUM(amt)) OVER (PARTITION BY fy)
                               FROM r WHERE mfa GROUP BY fy, {col}) WHERE i <= {MFA_TOP_AGENCIES} ORDER BY 1, 2""").fetchall()])
    cc = "COALESCE(NULLIF(trim(primary_place_of_performance_country_code), ''), '(blank)')"
    cname = dict(c.execute(f"SELECT {cc}, mode(primary_place_of_performance_country_name) FROM r WHERE mfa GROUP BY 1").fetchall())
    all_net = d(c.execute("SELECT SUM(amt) FROM r WHERE mfa").fetchone()[0])
    write("p6_mfa_top_countries_all_years", [
        {"rank": i + 1, "country_code": k, "country_name": cname.get(k), "rows": n, "net": q(d(s)), "share_of_placeholder_net_pct": pct(s, all_net)}
        for i, (k, n, s) in enumerate(c.execute(f"""SELECT {cc}, COUNT(*), SUM(amt) FROM r WHERE mfa GROUP BY 1
                                                     ORDER BY 3 DESC, 1 LIMIT {MFA_TOP_COUNTRIES}""").fetchall())])
    write("p6_mfa_top_countries_by_year", [
        {"fiscal_year": fy, "rank": i, "country_code": k, "country_name": cname.get(k), "rows": n, "net": q(d(s)),
         "share_of_placeholder_net_pct": pct(s, t)}
        for fy, i, k, n, s, t in c.execute(f"""
            SELECT * FROM (SELECT fy, row_number() OVER (PARTITION BY fy ORDER BY SUM(amt) DESC, {cc}) AS i, {cc} AS k, COUNT(*), SUM(amt),
                                  SUM(SUM(amt)) OVER (PARTITION BY fy) FROM r WHERE mfa GROUP BY fy, k)
            WHERE i <= {MFA_TOP_COUNTRIES_YEAR} ORDER BY 1, 2""").fetchall()])
    write("p6_mfa_by_type", [
        {"fiscal_year": fy, "award_type_code": at, "idv_type_code": it, "rows": n, "net": q(d(s)), "share_of_placeholder_net_pct": pct(s, t)}
        for fy, at, it, n, s, t in c.execute("""
            SELECT fy, award_type_code, idv_type_code, COUNT(*), SUM(amt), SUM(SUM(amt)) OVER (PARTITION BY fy) FROM r WHERE mfa
            GROUP BY fy, award_type_code, idv_type_code ORDER BY 1, 5 DESC""").fetchall()])

    # 7. example rows with their descriptions
    check_columns(TEXT_COLUMNS)
    ex = []
    for fy in MFA_EXAMPLE_YEARS:
        k = c.execute("SELECT contract_transaction_unique_key FROM r WHERE fy = ? AND mfa ORDER BY amt DESC, 1 LIMIT 1", [fy]).fetchone()[0]
        cols = ["contract_transaction_unique_key", "contract_award_unique_key", "action_date", "federal_action_obligation",
                "awarding_agency_name", "awarding_sub_agency_name", "product_or_service_code",
                "primary_place_of_performance_country_name"] + TEXT_COLUMNS
        r = c.execute(f"SELECT {', '.join(cols)} FROM read_parquet({files(fy)!r}) WHERE contract_transaction_unique_key = ?", [k]).fetchone()
        ex.append({"fiscal_year": fy, **dict(zip(cols, r))})
    write("p6_mfa_example_rows", ex)


# ============================================================================================ Part 7. Funding agency

FUND_YEARS = range(2011, 2026)                # FY2008 to FY2010 carry the placeholder funding code 999
FUND_TOP_PAIRS, FUND_SEGMENTS, FUND_SEGMENT_FY, GSA = 15, 50, 2025, "047"

RULES |= {
    "funding_compare": f"FY{FUND_YEARS[0]} to FY{FUND_YEARS[-1]}, every row as recorded. funding_agency_code differs "
                       "when it is filled and not equal to awarding_agency_code, both as recorded. It is blank when "
                       "empty after trimming. A difference in code alone can come from an agency recorded with a "
                       "3-character code in one column and a 4-character code in the other, so the rows whose codes "
                       "differ but whose agency names (trimmed, upper case) match are counted too.",
    "funding_pairs": f"The {FUND_TOP_PAIRS} awarding and funding code pairs with the largest net where the codes "
                     f"differ, over FY{FUND_YEARS[0]} to FY{FUND_YEARS[-1]}, named by the most common names.",
    "funding_segments": f"The {FUND_SEGMENTS} FY{FUND_SEGMENT_FY} segments with the largest net under the proposed "
                        "handling. Each one's HHI as usual, and the HHI of the segment built from the same code and "
                        "product code with funding_agency_code in place of awarding_agency_code (a blank funding code "
                        "is its own value). Dollars that move out: the net of the segment's rows whose funding code is "
                        "not the awarding code. Dollars that move in: the net of rows funded by that code and awarded "
                        "by another agency, for the same product code.",
    "gsa_funded": f"The share of awarding agency {GSA} (General Services Administration) net, by year, on rows whose "
                  f"funding code is filled and not {GSA}, and on rows whose funding code is blank.",
}


@part
def part7() -> None:
    c = con()
    for col in ("awarding_agency_code", "funding_agency_code"):
        show_codes(c, col, fys=(FUND_YEARS[0], FUND_YEARS[-1]), limit=20)
    c.execute(f"""CREATE OR REPLACE TEMP VIEW f AS SELECT *, NULLIF(trim(funding_agency_code), '') IS NULL AS fblank,
                  NULLIF(trim(funding_agency_code), '') IS NOT NULL AND funding_agency_code <> awarding_agency_code AS fdiff,
                  upper(trim(funding_agency_name)) = upper(trim(awarding_agency_name)) AS same_name
                  FROM {all_rows()} WHERE fy BETWEEN {FUND_YEARS[0]} AND {FUND_YEARS[-1]}""")
    write("p7_funding_differs_by_year", [
        {"fiscal_year": fy, "rows": n, "net": q(d(s)), "rows_differ": nd, "net_differ": q(d(sd)), "share_rows_differ_pct": pct(nd, n),
         "share_net_differ_pct": pct(sd, s), "rows_differ_same_name": nds, "net_differ_same_name": q(d(sds)),
         "rows_blank": nb, "net_blank": q(d(sb)), "share_rows_blank_pct": pct(nb, n), "share_net_blank_pct": pct(sb, s)}
        for fy, n, s, nd, sd, nds, sds, nb, sb in c.execute("""
            SELECT fy, COUNT(*), SUM(amt), COUNT(*) FILTER (WHERE fdiff), SUM(amt) FILTER (WHERE fdiff),
                   COUNT(*) FILTER (WHERE fdiff AND same_name), SUM(amt) FILTER (WHERE fdiff AND same_name),
                   COUNT(*) FILTER (WHERE fblank), SUM(amt) FILTER (WHERE fblank) FROM f GROUP BY 1 ORDER BY 1""").fetchall()])
    write("p7_top_awarding_funding_pairs", [
        {"rank": i + 1, "awarding_agency_code": a, "awarding_agency_name": an, "funding_agency_code": fc, "funding_agency_name": fn,
         "rows": n, "net": q(d(s))}
        for i, (a, an, fc, fn, n, s) in enumerate(c.execute(f"""
            SELECT awarding_agency_code, mode(awarding_agency_name), funding_agency_code, mode(funding_agency_name), COUNT(*), SUM(amt)
            FROM f WHERE fdiff GROUP BY awarding_agency_code, funding_agency_code ORDER BY 6 DESC, 1, 3 LIMIT {FUND_TOP_PAIRS}""").fetchall())])

    # 3. the largest FY2025 segments, built by funding agency
    handled(c)
    top = c.execute(f"""SELECT awarding_agency_code, product_or_service_code, SUM(amt_h) FROM h WHERE fy = {FUND_SEGMENT_FY}
                        GROUP BY ALL ORDER BY 3 DESC, 1, 2 LIMIT {FUND_SEGMENTS}""").fetchall()
    c.execute("CREATE OR REPLACE TEMP TABLE fs (ag VARCHAR, psc VARCHAR)")
    c.executemany("INSERT INTO fs VALUES (?, ?)", [[ag, psc] for ag, psc, _ in top])
    fund = "COALESCE(NULLIF(trim(funding_agency_code), ''), '(blank)')"
    by_award, by_fund = defaultdict(dict), defaultdict(dict)
    moved_out, moved_in = defaultdict(Decimal), defaultdict(Decimal)
    for ag, fc, psc, v, net in c.execute(f"""
            SELECT awarding_agency_code, {fund}, product_or_service_code, v, SUM(amt_h) FROM h
            WHERE fy = {FUND_SEGMENT_FY} AND product_or_service_code IN (SELECT psc FROM fs) GROUP BY ALL""").fetchall():
        by_award[(ag, psc)][v] = by_award[(ag, psc)].get(v, Decimal(0)) + d(net)
        by_fund[(fc, psc)][v] = by_fund[(fc, psc)].get(v, Decimal(0)) + d(net)
        if fc != ag:
            moved_out[(ag, psc)] += d(net)
            moved_in[(fc, psc)] += d(net)
    label = dict(c.execute(f"SELECT product_or_service_code, mode(product_or_service_code_description) FROM read_parquet({files(FUND_SEGMENT_FY)!r}) GROUP BY 1").fetchall())
    h_or_none = lambda nets: hhi(list(nets.values())) if any(x > 0 for x in nets.values()) else None
    write("p7_largest_segments_by_funding_agency", [
        {"rank": i + 1, "agency_code": ag, "psc": psc, "psc_description": label.get(psc), "segment_net": q(d(net)),
         "hhi_awarding_agency": q(h_or_none(by_award[(ag, psc)]), "0.1"), "segment_net_by_funding_agency": q(sum(by_fund[(ag, psc)].values(), Decimal(0))),
         "hhi_funding_agency": q(h_or_none(by_fund[(ag, psc)]), "0.1") if by_fund.get((ag, psc)) else "",
         "net_moving_out_to_another_funding_agency": q(moved_out[(ag, psc)]), "share_moving_out_pct": pct(moved_out[(ag, psc)], net),
         "net_moving_in_from_another_awarding_agency": q(moved_in[(ag, psc)])}
        for i, (ag, psc, net) in enumerate(top)])

    # 4. GSA
    write("p7_gsa_funded_by_another_agency", [
        {"fiscal_year": fy, "gsa_awarding_net": q(d(s)), "net_funded_by_another_agency": q(d(so)), "share_funded_by_another_pct": pct(so, s),
         "net_funding_blank": q(d(sb)), "share_funding_blank_pct": pct(sb, s)}
        for fy, s, so, sb in c.execute(f"""SELECT fy, SUM(amt), SUM(amt) FILTER (WHERE fdiff), SUM(amt) FILTER (WHERE fblank) FROM f
                                           WHERE awarding_agency_code = '{GSA}' GROUP BY 1 ORDER BY 1""").fetchall()])


# ============================================================================================ Part 8. Offers received

ZERO_UNTIL = 2012                             # a zero on a competed row before FY2012 counts as blank
MINT_CHECK = {"TMHQ10C0040": (1646, Decimal("5977575309.34")), "TMHQ10C0044": (2354, Decimal("11876614896.49"))}
MINT_CHECK_YEARS = (2010, 2025)
OFFER_EXAMPLE_YEARS = (2018, 2020, 2022, 2024, 2025)
RECORD_TYPE = """CASE WHEN NULLIF(trim(idv_type_code), '') IS NOT NULL THEN 'vehicle record'
                      WHEN NULLIF(trim(parent_award_id_piid), '') IS NOT NULL THEN 'order under a vehicle'
                      WHEN award_type_code = 'D' THEN 'definitive contract' ELSE 'other' END"""

RULES |= {
    "competed": "extent_competed_code in COMPETED of src/stage2.py (" + ", ".join(COMPETED) + "), as flag X02 uses it. "
                "Every row as recorded. Dollars are net.",
    "record_type": "The first that applies: vehicle record (idv_type_code filled), order under a vehicle "
                   "(parent_award_id_piid filled), definitive contract (award_type_code D), other.",
    "offers_filled": "number_of_offers_received filled means not blank after trimming. Zero means it reads as the "
                     "number 0.",
    "vehicle_join": "An order joins its vehicle when the order's parent_award_id_piid equals the vehicle's "
                    "award_id_piid and the order's parent_award_agency_id equals the vehicle's agency ID. No column "
                    "of the vehicle record holds that ID (a sample of FY2022 orders matched awarding_sub_agency_code "
                    "on 33% of rows and awarding_agency_code on almost none). It is the last part of the vehicle's "
                    "contract_award_unique_key (CONT_IDV_<PIID>_<agency ID>), which always equals the first part "
                    "of its contract_transaction_unique_key. A vehicle is one contract_award_unique_key, from any "
                    "year in the data. The run stops if one PIID and agency ID pair belongs to more than one vehicle.",
    "vehicle_offers": f"The vehicle's offers are those on its base record (modification number 0). When that is blank "
                      "they come from its first row (by action date, then key) with offers filled. The zero rule "
                      "applies to vehicle rows as well.",
    "fill": f"A competed row's offers count as blank when blank, and when they are zero on a row before FY{ZERO_UNTIL}. "
            "An order's blank offers are then filled from its vehicle. Coverage is the share of competed rows and of "
            "competed dollars with offers known.",
    "single_offer": "The share of competed dollars on rows with exactly one offer, over competed dollars with offers "
                    "known and over all competed dollars, for orders under single-award (S) and multiple-award (M) "
                    "vehicles by parent_award_single_or_multiple_code. Before the fill uses offers as recorded, after "
                    "the fill applies the zero rule and the fill.",
    "mint_check": "Orders joined to the vehicles TMHQ10C0040 and TMHQ10C0044, "
                  f"FY{MINT_CHECK_YEARS[0]} to FY{MINT_CHECK_YEARS[1]}, must match the rows and net that integrity "
                  "report version 3 counts.",
    "offer_examples": "In each of " + ", ".join(f"FY{y}" for y in OFFER_EXAMPLE_YEARS) + ", the competed order row with "
                      "blank offers and the largest amount whose vehicle has offers, shown with the vehicle row the "
                      "count came from.",
}


@part
def part8() -> None:
    c = con()
    for col in ("extent_competed_code", "parent_award_single_or_multiple_code", "award_type_code", "idv_type_code"):
        show_codes(c, col, limit=15)
    comp = f"list_contains({COMPETED!r}, extent_competed_code)"
    off = f"""CASE WHEN NULLIF(trim(number_of_offers_received), '') IS NULL THEN NULL
                   WHEN fy < {ZERO_UNTIL} AND {comp} AND TRY_CAST(number_of_offers_received AS DOUBLE) = 0 THEN NULL
                   ELSE TRY_CAST(number_of_offers_received AS DOUBLE) END"""
    raw = "TRY_CAST(NULLIF(trim(number_of_offers_received), '') AS DOUBLE)"

    # 1. coverage as recorded
    write("p8_offers_coverage_by_record_type", [
        {"fiscal_year": fy, "record_type": rt, "competed_rows": n, "competed_dollars": q(d(s)),
         "share_rows_filled_pct": pct(nf, n), "share_dollars_filled_pct": pct(sf, s),
         "share_rows_zero_pct": pct(nz, n), "share_dollars_zero_pct": pct(sz, s)}
        for fy, rt, n, s, nf, sf, nz, sz in c.execute(f"""
            SELECT fy, {RECORD_TYPE}, COUNT(*), SUM(amt), COUNT({raw}), SUM(amt) FILTER (WHERE {raw} IS NOT NULL),
                   COUNT(*) FILTER (WHERE {raw} = 0), SUM(amt) FILTER (WHERE {raw} = 0)
            FROM {all_rows()} WHERE {comp} GROUP BY ALL ORDER BY 1, 2""").fetchall()])

    # 2. vehicles and the join
    c.execute(f"""CREATE OR REPLACE TEMP TABLE vo AS
        WITH v AS (SELECT *, {off} AS off FROM {all_rows()} WHERE NULLIF(trim(idv_type_code), '') IS NOT NULL)
        SELECT contract_award_unique_key AS vk, any_value(award_id_piid) AS piid, split_part(contract_award_unique_key, '_', -1) AS ag_id,
               bool_and(split_part(contract_award_unique_key, '_', -1) = split_part(contract_transaction_unique_key, '_', 1)) AS ids_agree,
               arg_min(off, (action_date, contract_transaction_unique_key)) FILTER (WHERE modification_number = '0' AND off IS NOT NULL) AS base_off,
               arg_min(off, (action_date, contract_transaction_unique_key)) FILTER (WHERE off IS NOT NULL) AS first_off,
               arg_min(contract_transaction_unique_key, (action_date, contract_transaction_unique_key)) FILTER (WHERE modification_number = '0' AND off IS NOT NULL) AS base_key,
               arg_min(contract_transaction_unique_key, (action_date, contract_transaction_unique_key)) FILTER (WHERE off IS NOT NULL) AS first_key
        FROM v GROUP BY 1""")
    c.execute("""CREATE OR REPLACE TEMP TABLE vo2 AS SELECT *, COALESCE(base_off, first_off) AS veh_off,
                 COALESCE(base_key, first_key) AS source_key,
                 CASE WHEN base_off IS NOT NULL THEN 'base record' WHEN first_off IS NOT NULL THEN 'first row with offers' ELSE 'none' END AS source
                 FROM vo""")
    dup, disagree = c.execute("""SELECT (SELECT COUNT(*) FROM (SELECT piid, ag_id FROM vo2 GROUP BY 1, 2 HAVING COUNT(*) > 1)),
                                        (SELECT COUNT(*) FROM vo2 WHERE NOT ids_agree)""").fetchone()
    if dup:
        raise SystemExit(f"CHECK FAILED: {dup} PIID and agency ID pairs belong to more than one vehicle")
    write("p8_vehicle_offer_sources", [{"source": s, "vehicles": n} for s, n in
                                       c.execute("SELECT source, COUNT(*) FROM vo2 GROUP BY 1 ORDER BY 2 DESC").fetchall()]
          + [{"source": "vehicles whose key and transaction key agency IDs differ", "vehicles": disagree}])
    p8 = WORK / "p8_rows.parquet"
    c.execute(f"""COPY (SELECT r.fy, r.contract_transaction_unique_key AS k, r.amt, {RECORD_TYPE} AS rt, {comp} AS competed,
                              {raw} AS off_raw, {off} AS off, COALESCE(NULLIF(trim(r.parent_award_single_or_multiple_code), ''), '(blank)') AS sm,
                              CASE WHEN {RECORD_TYPE} = 'order under a vehicle' THEN vo2.vk END AS vk,
                              CASE WHEN {RECORD_TYPE} = 'order under a vehicle' THEN vo2.veh_off END AS veh_off,
                              CASE WHEN {RECORD_TYPE} = 'order under a vehicle' THEN vo2.source_key END AS source_key
                       FROM {all_rows()} r LEFT JOIN vo2 ON vo2.piid = r.parent_award_id_piid AND vo2.ag_id = r.parent_award_agency_id)
                  TO '{p8}' (FORMAT parquet, COMPRESSION zstd)""")
    c.execute(f"CREATE OR REPLACE TEMP VIEW o AS SELECT *, CASE WHEN rt = 'order under a vehicle' THEN COALESCE(off, veh_off) ELSE off END AS off_f FROM read_parquet('{p8}')")
    write("p8_vehicle_match_by_year", [
        {"fiscal_year": fy, "order_rows": n, "matched_rows": m, "match_rate_rows_pct": pct(m, n), "order_dollars": q(d(s)),
         "matched_dollars": q(d(sm_)), "match_rate_dollars_pct": pct(sm_, s)}
        for fy, n, m, s, sm_ in c.execute("""SELECT fy, COUNT(*), COUNT(vk), SUM(amt), SUM(amt) FILTER (WHERE vk IS NOT NULL) FROM o
                                             WHERE rt = 'order under a vehicle' GROUP BY 1 ORDER BY 1""").fetchall()])
    mint = {piid: (n, d(s)) for piid, n, s in c.execute(f"""
        SELECT vo2.piid, COUNT(*), SUM(amt) FROM o JOIN vo2 USING (vk) WHERE vo2.piid IN ('TMHQ10C0040', 'TMHQ10C0044')
        AND fy BETWEEN {MINT_CHECK_YEARS[0]} AND {MINT_CHECK_YEARS[1]} GROUP BY 1""").fetchall()}
    write("p8_mint_check", [{"vehicle": v, "rows_found": mint.get(v, (0, 0))[0], "rows_expected": n, "net_found": q(mint.get(v, (0, Decimal(0)))[1]),
                             "net_expected": s} for v, (n, s) in MINT_CHECK.items()])
    if any((mint.get(v, (0, Decimal(0)))[0], q(mint.get(v, (0, Decimal(0)))[1])) != exp for v, exp in MINT_CHECK.items()):
        raise SystemExit(f"CHECK FAILED: US Mint orders found {mint}, expected {MINT_CHECK}")
    print("part8: no order matches two vehicles, US Mint check passed", flush=True)

    # 3. coverage after the fill, by single or multiple award
    write("p8_coverage_after_fill_by_year", [
        {"fiscal_year": fy, "parent_award_single_or_multiple_code": sm, "competed_rows": n, "competed_dollars": q(d(s)),
         "rows_filled_as_recorded_pct": pct(n0, n), "rows_known_after_zero_rule_pct": pct(n1, n), "rows_known_after_fill_pct": pct(n2, n),
         "dollars_filled_as_recorded_pct": pct(s0, s), "dollars_known_after_zero_rule_pct": pct(s1, s), "dollars_known_after_fill_pct": pct(s2, s)}
        for fy, sm, n, s, n0, n1, n2, s0, s1, s2 in c.execute("""
            SELECT fy, sm, COUNT(*), SUM(amt), COUNT(off_raw), COUNT(off), COUNT(off_f),
                   SUM(amt) FILTER (WHERE off_raw IS NOT NULL), SUM(amt) FILTER (WHERE off IS NOT NULL), SUM(amt) FILTER (WHERE off_f IS NOT NULL)
            FROM o WHERE competed GROUP BY ALL ORDER BY 1, 2""").fetchall()])

    # 4. single-offer share of competed dollars, orders under single- and multiple-award vehicles
    write("p8_single_offer_share_by_year", [
        {"fiscal_year": fy, "parent_award_single_or_multiple_code": sm, "competed_dollars": q(d(s)),
         "single_offer_share_of_known_before_pct": pct(b1, bk), "single_offer_share_of_known_after_pct": pct(a1, ak),
         "single_offer_share_of_all_before_pct": pct(b1, s), "single_offer_share_of_all_after_pct": pct(a1, s)}
        for fy, sm, s, b1, bk, a1, ak in c.execute("""
            SELECT fy, sm, SUM(amt), SUM(amt) FILTER (WHERE off_raw = 1), SUM(amt) FILTER (WHERE off_raw IS NOT NULL),
                   SUM(amt) FILTER (WHERE off_f = 1), SUM(amt) FILTER (WHERE off_f IS NOT NULL)
            FROM o WHERE competed AND rt = 'order under a vehicle' AND sm IN ('S', 'M') GROUP BY ALL ORDER BY 1, 2""").fetchall()])

    # 5. worked examples
    cols = ["fy", "contract_transaction_unique_key", "contract_award_unique_key", "action_date", "amt", "extent_competed_code",
            "number_of_offers_received", "parent_award_id_piid", "parent_award_agency_id", "parent_award_single_or_multiple_code",
            "idv_type_code", "modification_number", "recipient_name"]
    ex = []
    for fy in OFFER_EXAMPLE_YEARS:
        hit = c.execute("""SELECT k, source_key FROM o WHERE fy = ? AND competed AND rt = 'order under a vehicle' AND off IS NULL
                           AND veh_off IS NOT NULL ORDER BY amt DESC, k LIMIT 1""", [fy]).fetchone()
        if not hit:
            continue
        for role, key in (("order", hit[0]), ("vehicle row with the count", hit[1])):
            r = c.execute(f"SELECT {', '.join(cols)} FROM {all_rows()} WHERE contract_transaction_unique_key = ?", [key]).fetchone()
            ex.append({"example": f"FY{fy}", "record": role, **dict(zip(cols, [q(x) if isinstance(x, Decimal) else x for x in r]))})
    write("p8_examples", ex)


# ============================================================================================ Part 9. Rows with no vendor ID

NO_ID_CHECK = {2008: 371, 2009: 106, 2010: 56}   # shivram-eda vendor counts table

RULES |= {
    "no_vendor_id": "Rows whose vendor is '(no ID)' under the VENDOR expression: recipient_parent_uei and "
                    "recipient_uei both blank after trimming. Every row as recorded. The agencies of a year are listed "
                    "with their rows, largest first.",
}


@part
def part9() -> None:
    c = con()
    show_codes(c, "awarding_agency_code", limit=10)
    rows = c.execute(f"""SELECT fy, action_date, awarding_agency_code, awarding_agency_name, awarding_sub_agency_code, awarding_sub_agency_name,
                                product_or_service_code, amt, recipient_name, recipient_duns, recipient_parent_duns,
                                contract_transaction_unique_key FROM {all_rows()} WHERE v = '(no ID)'
                         ORDER BY fy, action_date, contract_transaction_unique_key""").fetchall()
    cols = ["fiscal_year", "action_date", "awarding_agency_code", "awarding_agency_name", "awarding_sub_agency_code",
            "awarding_sub_agency_name", "product_or_service_code", "amount", "recipient_name", "recipient_duns",
            "recipient_parent_duns", "transaction_key"]
    write("p9_rows_with_no_vendor_id", [dict(zip(cols, [q(x) if isinstance(x, Decimal) else x for x in r])) for r in rows])
    summary = []
    for fy in years():
        yr = [r for r in rows if r[0] == fy]
        ag = defaultdict(int)
        for r in yr:
            ag[r[3]] += 1
        summary.append({"fiscal_year": fy, "rows": len(yr), "net": q(sum((d(r[7]) for r in yr), Decimal(0))),
                        "agencies": "; ".join(f"{a} ({n})" for a, n in sorted(ag.items(), key=lambda kv: (-kv[1], kv[0] or "")))})
    write("p9_no_vendor_id_by_year", summary)
    got = {r["fiscal_year"]: r["rows"] for r in summary}
    bad = [f"FY{fy}: {got.get(fy)} against {n}" for fy, n in NO_ID_CHECK.items() if got.get(fy) != n]
    if bad:
        raise SystemExit("CHECK FAILED: rows with no vendor ID differ from Shivram's table: " + "; ".join(bad))
    print("part9: check passed", flush=True)


@part
def rules() -> None:
    """Run no analysis. main() then writes rules.json from RULES, as it does after every part."""


def main(argv: list[str] | None = None) -> int:
    names = argv if argv is not None else sys.argv[1:]
    if not names or any(n not in PARTS and n != "extract" for n in names):
        print(__doc__)
        return 2
    if not years():                                 # never replace committed tables with empty ones
        print("No yearly data found: no fiscal year has its Stage 0 zip and finished Stage 1 and Stage 2 outputs. "
              f"Nothing was written to {OUT}. Build the stages first: python -m src.stages refresh")
        return 1
    for n in names:
        t0 = time.time()
        if n == "extract":
            build_extract()
        else:
            PARTS[n]()
            (OUT / "rules.json").write_text(json.dumps(RULES, indent=1), encoding="utf-8")
        print(f"{n}: {time.time() - t0:.0f} s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
