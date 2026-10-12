"""Phase 1 of the EDA plan (docs/eda/eda_plan.md): the base tables every later phase reads.

    python -m src.eda.base_tables codes --fy 2025     # the code values the splits rely on, before any build
    python -m src.eda.base_tables vendor_cells       # one Parquet file per year in data/eda/vendor_cells/ (restartable)
    python -m src.eda.base_tables labels             # data/eda/labels_agency.parquet and labels_psc.parquet
    python -m src.eda.base_tables cells              # data/eda/cells.parquet, one row per cell and variant
    python -m src.eda.base_tables checks             # reports/eda/base_checks.csv: the tables add back to Stage 1
    python -m src.eda.base_tables                    # vendor_cells, labels, cells and checks, in order

Each rule is written in RULES below before the build runs. The cell, the vendor, the reversal pairs, the US Mint rows
and MISCELLANEOUS FOREIGN AWARDEES follow src/analyses_v2.py exactly (imported, not copied). Nothing in Stages 0 to 2
changes. The row-level tables stay in data/eda/, and only the checks are committed, in reports/eda/.
"""

from __future__ import annotations

import csv
import os
import sys
from decimal import Decimal

from .. import config
from ..analyses_v2 import AMT, MFA, MINT_KEYS, PAIRS, VENDOR, d, files
from ..analyses_v2 import con as _con

DATA = config.DATA_DIR / "eda"
VC_DIR = DATA / "vendor_cells"
CELLS = DATA / "cells.parquet"
OUT = config.REPORTS_DIR / "eda"

# Code groups for the dollar splits. Any value outside these lists goes to "other", so every split adds back to the net.
COMPETED = ("A", "D", "F", "CDO")              # full and open, after exclusion of sources, simplified, competitive order
SOLE_SOURCE = ("B", "C", "G", "NDO")           # not available, not competed, not competed simplified, non-competitive order
FOLLOW_ON = ("E",)                             # follow-on to a competed action
FIXED_PRICE = ("A", "B", "J", "K", "L", "M")
COST = ("R", "S", "T", "U", "V")
TIME_AND_MATERIALS = ("Y", "Z")
NO_SET_ASIDE = ("NONE",)
FAIR_OPPORTUNITY_GIVEN = ("FAIR", "CSA")       # fair opportunity given, competitive set-aside
ORDER_FOLLOW_ON = ("FOO",)                     # follow-on action following a competitive initial action
SMALL_ACTION = 10000                           # decision 3 as proposed: counts use actions of $10,000 or more

RULES = {
    "cell": "As in src/analyses_v2.py. Awarding agency code as recorded x product or service code x fiscal year.",
    "vendor": "As in src/analyses_v2.py. recipient_parent_uei, or recipient_uei when the parent is blank. Rows with both "
              "blank form one vendor, '(no ID)'.",
    "vendor_cell": "One row per fiscal year, cell and vendor. Sums over its rows: rows, rows with an amount of $10,000 or "
                   "more, net, gross (sum of absolute amounts), positive amounts and negative amounts, as recorded (V0).",
    "v1": "Variant V1, the decisions as proposed in integrity report version 3. Each reversal pair is replaced by its net, "
          "placed on the pair's first row (the Emerson entry in FY2008) with the other row set to zero. The two US Mint "
          "rows, rows named MISCELLANEOUS FOREIGN AWARDEES and the vendor '(no ID)' are left out. Shares over vendors "
          "with a positive net.",
    "v8b": "Variant V8b. V1, with rows flagged J03 (a deobligation larger than the award's obligations that year) also "
           "left out.",
    "v8c": "Variant V8c. V1, with the product code cut to its first 2 characters.",
    "v8a_equivalence": "Setting negative vendor totals to zero (option 2 of decision 8) gives the same shares, HHI and "
                       "top-4 share as V1, because V1 already takes shares over vendors with a positive net only. The two "
                       "differ only in the cell's net, which cells.parquet reports both ways.",
    "splits": "Net dollars under V1 by group. Umbrella competition (extent_competed_code): competed "
              f"{', '.join(COMPETED)}; sole source {', '.join(SOLE_SOURCE)}; follow-on {', '.join(FOLLOW_ON)}; blank; other. "
              f"Order competition (fair_opportunity_limited_sources_code): fair opportunity given {', '.join(FAIR_OPPORTUNITY_GIVEN)}; "
              f"follow-on {', '.join(ORDER_FOLLOW_ON)}; blank; any other value counts as limited sources. Single offer: competed rows whose number_of_offers_received "
              f"is 1. Pricing (type_of_contract_pricing_code): fixed price {', '.join(FIXED_PRICE)}; cost {', '.join(COST)}; "
              f"time and materials or labor hours {', '.join(TIME_AND_MATERIALS)}; blank; other. Set-aside "
              f"(type_of_set_aside_code): none {', '.join(NO_SET_ASIDE)}; blank; any other value counts as a set-aside. "
              "Vehicle: rows with a parent_award_id_piid are orders under a contract vehicle.",
    "hhi": "As hhi() in src/analyses_v2.py, computed in DuckDB as a double. 10,000 x the sum of squared shares, a share "
           "being a vendor's net over the summed net of vendors with a positive net. A cell with no vendor of positive "
           "net has no HHI. Top-4 share: the four largest shares summed, in percent. A vendor counts in a variant when at "
           "least one of its rows is kept by that variant.",
}

def con():
    """The connection of src/analyses_v2.py with lower limits: 8 GB and every thread froze a 16 GB Windows laptop
    on 2026-10-12. PILOT_DUCKDB_MEMORY and PILOT_DUCKDB_THREADS change them."""
    c = _con()
    c.execute(f"SET memory_limit = '{os.environ.get('PILOT_DUCKDB_MEMORY', '4GB')}'")
    c.execute(f"SET threads = {int(os.environ.get('PILOT_DUCKDB_THREADS', '8'))}")
    return c


def years() -> list[int]:
    """Years proven in Stage 1 (their _files.json exists). Stage 2 is needed only for the J03 flags of V8b."""
    return [fy for fy in config.years_present() if (config.layer_a_dir(fy) / "_files.json").exists()]


def j03_years() -> list[int]:
    return [fy for fy in years() if (config.INTEGRITY_DIR / "row_flags" / f"fy{fy}.parquet").exists()
            and (config.INTEGRITY_DIR / f"fy{fy}" / "_done.json").exists()]


CODE_COLUMNS = ("extent_competed_code", "fair_opportunity_limited_sources_code", "type_of_contract_pricing_code",
                "type_of_set_aside_code", "number_of_offers_received")


def sql_list(xs) -> str:
    return "(" + ", ".join("'" + str(x).replace("'", "''") + "'" for x in xs) + ")"


def pair_targets() -> dict[str, Decimal]:
    """Each reversal-pair row's amount under V1: the pair's net on its first row, zero on the second."""
    c, amounts = con(), {}
    keys = [k for ks in PAIRS.values() for k in ks]
    for fy in years():
        for k, a in c.execute(f"SELECT contract_transaction_unique_key, {AMT} FROM read_parquet({files(fy)!r}) "
                              f"WHERE contract_transaction_unique_key IN {sql_list(keys)}").fetchall():
            amounts[k] = d(a)
    missing = [k for k in keys if k not in amounts]
    if missing:
        raise SystemExit(f"Stop: reversal-pair rows not found in Stage 1: {missing}")
    out = {}
    for first, second in PAIRS.values():
        out[first], out[second] = amounts[first] + amounts[second], Decimal(0)
    return out


def codes(fy: int) -> None:
    """Print each code column's values with rows and net, to check the lists above before any build."""
    c = con()
    for col in CODE_COLUMNS:
        print(f"--- {col}, FY{fy}")
        for v, n, net in c.execute(f"SELECT {col}, COUNT(*), SUM({AMT}) FROM read_parquet({files(fy)!r}) "
                                   "GROUP BY 1 ORDER BY 2 DESC LIMIT 25").fetchall():
            print(f"  {v!r:12} {n:>12,} {d(net):>22,.2f}")


def vendor_cells(force: bool = False) -> None:
    VC_DIR.mkdir(parents=True, exist_ok=True)
    targets = pair_targets()
    pair_case = " ".join(f"WHEN '{k}' THEN {v}" for k, v in targets.items())
    c = con()
    for fy in years():
        out = VC_DIR / f"fy{fy}.parquet"
        if out.exists() and not force:
            print(f"vendor_cells: FY{fy} already built, skipping", flush=True)
            continue
        j03 = config.INTEGRITY_DIR / "row_flags" / f"fy{fy}.parquet"
        if fy in j03_years():
            c.execute(f"""CREATE OR REPLACE TEMP TABLE j AS SELECT DISTINCT contract_transaction_unique_key AS k
                          FROM read_parquet('{j03}') WHERE flag_id = 'J03'""")
        else:                                   # Stage 2 not built for this year yet: V8b is left out until it is
            c.execute("CREATE OR REPLACE TEMP TABLE j AS SELECT ''::VARCHAR AS k WHERE false")
            print(f"vendor_cells: FY{fy} has no Stage 2 flags yet, so its J03 columns are empty and V8b waits", flush=True)
        ec, fo = "trim(extent_competed_code)", "trim(fair_opportunity_limited_sources_code)"
        pr, sa = "trim(type_of_contract_pricing_code)", "trim(type_of_set_aside_code)"
        tmp = out.with_suffix(".parquet.tmp")
        c.execute(f"""
            COPY (
            WITH r AS (
                SELECT contract_transaction_unique_key AS k, awarding_agency_code AS ag, product_or_service_code AS psc,
                       {VENDOR} AS v, {AMT} AS amt,
                       ({MFA}) AS mfa, contract_transaction_unique_key IN {sql_list(MINT_KEYS)} AS mint,
                       {ec} AS ec, {fo} AS fo, {pr} AS pr, {sa} AS sa,
                       trim(number_of_offers_received) AS offers, NULLIF(trim(parent_award_id_piid), '') IS NOT NULL AS veh
                FROM read_parquet({files(fy)!r})),
            r1 AS (
                SELECT r.*, j.k IS NOT NULL AS j03,
                       CASE WHEN mint OR mfa OR v = '(no ID)' THEN NULL
                            ELSE CASE k {pair_case} ELSE amt END END AS a1
                FROM r LEFT JOIN j USING (k))
            SELECT {fy} AS fiscal_year, {str(fy in j03_years()).upper()} AS j03_available, ag, psc, v AS vendor,
                   COUNT(*) AS rows, COUNT(*) FILTER (WHERE amt >= {SMALL_ACTION}) AS rows_10k,
                   SUM(amt) AS net, SUM(abs(amt)) AS gross,
                   COALESCE(SUM(amt) FILTER (WHERE amt > 0), 0) AS positive, COALESCE(SUM(amt) FILTER (WHERE amt < 0), 0) AS negative,
                   COUNT(*) FILTER (WHERE mfa) AS rows_mfa, COALESCE(SUM(amt) FILTER (WHERE mfa), 0) AS net_mfa,
                   COUNT(*) FILTER (WHERE mint) AS rows_mint, COALESCE(SUM(amt) FILTER (WHERE mint), 0) AS net_mint,
                   COUNT(*) FILTER (WHERE j03) AS rows_j03, COALESCE(SUM(amt) FILTER (WHERE j03), 0) AS net_j03,
                   COUNT(a1) AS rows_v1, COALESCE(SUM(a1), 0) AS net_v1,
                   COUNT(a1) FILTER (WHERE NOT j03) AS rows_v8b, COALESCE(SUM(a1) FILTER (WHERE NOT j03), 0) AS net_v8b,
                   COUNT(a1) FILTER (WHERE amt >= {SMALL_ACTION}) AS rows_10k_v1,
                   COALESCE(SUM(a1) FILTER (WHERE ec IN {sql_list(COMPETED)}), 0) AS v1_competed,
                   COALESCE(SUM(a1) FILTER (WHERE ec IN {sql_list(SOLE_SOURCE)}), 0) AS v1_sole_source,
                   COALESCE(SUM(a1) FILTER (WHERE ec IN {sql_list(FOLLOW_ON)}), 0) AS v1_follow_on,
                   COALESCE(SUM(a1) FILTER (WHERE ec = '' OR ec IS NULL), 0) AS v1_competition_blank,
                   COALESCE(SUM(a1) FILTER (WHERE ec <> '' AND ec NOT IN {sql_list(COMPETED + SOLE_SOURCE + FOLLOW_ON)}), 0) AS v1_competition_other,
                   COALESCE(SUM(a1) FILTER (WHERE fo IN {sql_list(FAIR_OPPORTUNITY_GIVEN)}), 0) AS v1_order_fair,
                   COALESCE(SUM(a1) FILTER (WHERE fo IN {sql_list(ORDER_FOLLOW_ON)}), 0) AS v1_order_follow_on,
                   COALESCE(SUM(a1) FILTER (WHERE fo <> '' AND fo NOT IN {sql_list(FAIR_OPPORTUNITY_GIVEN + ORDER_FOLLOW_ON)}), 0) AS v1_order_limited,
                   COALESCE(SUM(a1) FILTER (WHERE fo = '' OR fo IS NULL), 0) AS v1_order_blank,
                   COALESCE(SUM(a1) FILTER (WHERE ec IN {sql_list(COMPETED)} AND offers = '1'), 0) AS v1_single_offer,
                   COALESCE(SUM(a1) FILTER (WHERE ec IN {sql_list(COMPETED)} AND offers <> '' AND offers IS NOT NULL), 0) AS v1_competed_offers_reported,
                   COALESCE(SUM(a1) FILTER (WHERE pr IN {sql_list(FIXED_PRICE)}), 0) AS v1_fixed_price,
                   COALESCE(SUM(a1) FILTER (WHERE pr IN {sql_list(COST)}), 0) AS v1_cost,
                   COALESCE(SUM(a1) FILTER (WHERE pr IN {sql_list(TIME_AND_MATERIALS)}), 0) AS v1_time_and_materials,
                   COALESCE(SUM(a1) FILTER (WHERE pr = '' OR pr IS NULL), 0) AS v1_pricing_blank,
                   COALESCE(SUM(a1) FILTER (WHERE pr <> '' AND pr NOT IN {sql_list(FIXED_PRICE + COST + TIME_AND_MATERIALS)}), 0) AS v1_pricing_other,
                   COALESCE(SUM(a1) FILTER (WHERE sa <> '' AND sa NOT IN {sql_list(NO_SET_ASIDE)}), 0) AS v1_set_aside,
                   COALESCE(SUM(a1) FILTER (WHERE sa IN {sql_list(NO_SET_ASIDE)}), 0) AS v1_no_set_aside,
                   COALESCE(SUM(a1) FILTER (WHERE sa = '' OR sa IS NULL), 0) AS v1_set_aside_blank,
                   COALESCE(SUM(a1) FILTER (WHERE veh), 0) AS v1_vehicle
            FROM r1 GROUP BY ag, psc, v
            ) TO '{tmp}' (FORMAT parquet, COMPRESSION zstd)""")
        tmp.replace(out)
        print(f"vendor_cells: FY{fy} done", flush=True)


def labels() -> None:
    """Display labels and year spans by code. Groups always use codes, and labels are for reading only."""
    c = con()
    for name, code, label in (("agency", "awarding_agency_code", "awarding_agency_name"),
                              ("psc", "product_or_service_code", "product_or_service_code_description")):
        parts = " UNION ALL ".join(f"SELECT {fy} AS fy, {code} AS code, {label} AS label, COUNT(*) AS n, SUM({AMT}) AS net "
                                   f"FROM read_parquet({files(fy)!r}) GROUP BY ALL" for fy in years())
        out = DATA / f"labels_{name}.parquet"
        c.execute(f"""COPY (
            WITH t AS ({parts}),
            lab AS (SELECT code, arg_max(label, (fy, n)) AS label_latest FROM t GROUP BY code)
            SELECT code, label_latest, MIN(fy) AS first_year, MAX(fy) AS last_year, COUNT(DISTINCT fy) AS years_present,
                   SUM(n) AS rows, SUM(net) AS net
            FROM t JOIN lab USING (code) GROUP BY code, label_latest ORDER BY code
            ) TO '{out}' (FORMAT parquet)""")
        print(f"labels -> {out}", flush=True)


VARIANTS = {   # name -> (net column, row-count column, product code expression)
    "V0": ("net", "rows", "psc"),
    "V1": ("net_v1", "rows_v1", "psc"),
    "V8b": ("net_v8b", "rows_v8b", "psc"),
    "V8c": ("net_v1", "rows_v1", "left(psc, 2)"),
}


def cells() -> None:
    c = con()
    src = f"read_parquet('{VC_DIR / 'fy*.parquet'}')"
    parts = []
    with_j03 = set(j03_years()) == set(years())
    for name, (net, rows, psc) in VARIANTS.items():
        if name == "V8b" and not with_j03:
            print("cells: V8b left out until Stage 2 has built every year", flush=True)
            continue
        parts.append(f"""
            SELECT '{name}' AS variant, fiscal_year, ag, {psc} AS psc, vendor, SUM({net}) AS net
            FROM {src} WHERE {rows} > 0 GROUP BY ALL""")
    tmp = CELLS.with_suffix(".parquet.tmp")
    c.execute(f"""
        COPY (
        WITH v AS ({" UNION ALL ".join(parts)}),
        k AS (SELECT *, row_number() OVER (PARTITION BY variant, fiscal_year, ag, psc ORDER BY net DESC, vendor) AS rk FROM v)
        SELECT variant, fiscal_year, ag, psc,
               SUM(net) AS net, COALESCE(SUM(net) FILTER (WHERE net > 0), 0) AS positive_net,
               COUNT(*) AS vendors, COUNT(*) FILTER (WHERE net > 0) AS positive_vendors,
               CASE WHEN COUNT(*) FILTER (WHERE net > 0) > 0 THEN
                    10000 * SUM(CAST(net AS DOUBLE) ^ 2) FILTER (WHERE net > 0) / CAST(SUM(net) FILTER (WHERE net > 0) AS DOUBLE) ^ 2 END AS hhi,
               CASE WHEN COUNT(*) FILTER (WHERE net > 0) > 0 THEN
                    100 * CAST(SUM(net) FILTER (WHERE net > 0 AND rk <= 4) AS DOUBLE) / CAST(SUM(net) FILTER (WHERE net > 0) AS DOUBLE) END AS top4_pct,
               CASE WHEN COUNT(*) FILTER (WHERE net > 0) > 0 THEN
                    100 * CAST(MAX(net) AS DOUBLE) / CAST(SUM(net) FILTER (WHERE net > 0) AS DOUBLE) END AS top1_pct,
               arg_max(vendor, net) AS largest_vendor
        FROM k GROUP BY ALL
        ) TO '{tmp}' (FORMAT parquet, COMPRESSION zstd)""")
    tmp.replace(CELLS)
    print(f"cells -> {CELLS}", flush=True)


def checks() -> int:
    """The base tables against Stage 1 and the committed integrity and proposal tables. Exact unless noted."""
    c = con()
    vc, ce = f"read_parquet('{VC_DIR / 'fy*.parquet'}')", f"read_parquet('{CELLS}')"
    yt = {int(r["fiscal_year"]): r for r in csv.DictReader(open(config.INTEGRITY_REPORTS_DIR / "years.csv", encoding="utf-8"))}
    neg = {int(r["fiscal_year"]): r for r in csv.DictReader(open(config.INTEGRITY_REPORTS_DIR / "v2" / "negative_vendor_totals.csv",
                                                                 encoding="utf-8")) if r["variant"] == "full PSC"}
    pre = {int(r["fiscal_year"]): r for r in csv.DictReader(open(config.REPORTS_DIR / "proposal" / "concentration_prelim_by_year.csv",
                                                                 encoding="utf-8"))}
    out = []

    def check(fy, what, ours, expected, tol=None):
        ok = (abs(float(ours) - float(expected)) <= tol) if tol is not None else (str(ours) == str(expected))
        out.append({"fiscal_year": fy, "check": what, "ours": ours, "expected": expected, "status": "PASS" if ok else "FAIL"})

    for fy, rows, net, vcs, ncells, nneg, splits in c.execute(f"""
            SELECT fiscal_year, SUM(rows), SUM(net), COUNT(*), COUNT(DISTINCT (ag, psc)), COUNT(*) FILTER (WHERE net < 0),
                   SUM(net_v1) = SUM(v1_competed + v1_sole_source + v1_follow_on + v1_competition_blank + v1_competition_other)
                   AND SUM(net_v1) = SUM(v1_order_fair + v1_order_follow_on + v1_order_limited + v1_order_blank)
                   AND SUM(net_v1) = SUM(v1_fixed_price + v1_cost + v1_time_and_materials + v1_pricing_blank + v1_pricing_other)
                   AND SUM(net_v1) = SUM(v1_set_aside + v1_no_set_aside + v1_set_aside_blank)
            FROM {vc} GROUP BY 1 ORDER BY 1""").fetchall():
        check(fy, "rows equal Stage 1", rows, yt[fy]["rows"])
        check(fy, "net equals Stage 1", d(net).quantize(Decimal("0.01")), yt[fy]["net"])
        check(fy, "vendor-cells equal integrity report", vcs, neg[fy]["vendor_cells"])
        check(fy, "cells equal integrity report", ncells, neg[fy]["cells"])
        check(fy, "negative vendor-cells equal integrity report", nneg, neg[fy]["negative_vendor_cells"])
        check(fy, "every V1 split adds back to the V1 net", bool(splits), True)
    for fy in pre:
        r = c.execute(f"""SELECT COUNT(*), COUNT(hhi), COUNT(*) FILTER (WHERE hhi > 2500),
                                 quantile_disc(positive_vendors, 0.5) FILTER (WHERE hhi IS NOT NULL)
                          FROM {ce} WHERE variant = 'V0' AND fiscal_year = {fy}""").fetchone()
        check(fy, "V0 cells equal preliminary results", r[0], pre[fy]["cells"])
        check(fy, "V0 scored cells equal preliminary results", r[1], pre[fy]["cells_with_hhi"])
        check(fy, "V0 cells above 2,500 equal preliminary results", r[2], pre[fy]["cells_hhi_above_2500"])
        check(fy, "V0 median positive vendors equals preliminary results (lower median)", r[3],
              pre[fy]["median_positive_vendors_per_cell"], tol=0.5)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "base_checks.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    fails = [r for r in out if r["status"] != "PASS"]
    print(f"checks: {len(out) - len(fails)} PASS, {len(fails)} FAIL -> {OUT / 'base_checks.csv'}")
    for r in fails:
        print(f"  FAIL FY{r['fiscal_year']} {r['check']}: ours {r['ours']}, expected {r['expected']}")
    return 1 if fails else 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["codes"]:
        codes(int(argv[argv.index("--fy") + 1]) if "--fy" in argv else max(years()))
        return 0
    steps = argv or ["vendor_cells", "labels", "cells", "checks"]
    for s in steps:
        if s == "vendor_cells":
            vendor_cells(force="--force" in argv)
        elif s == "labels":
            labels()
        elif s == "cells":
            cells()
        elif s == "checks":
            if checks():
                return 1
        elif not s.startswith("--"):
            raise SystemExit(f"unknown step {s!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
