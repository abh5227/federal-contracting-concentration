"""Phases 2 and 3 of the EDA plan (docs/eda/eda_plan.md): the spending picture, and concentration in all 18 years.

    python -m src.eda.concentration            # every table
    python -m src.eda.concentration spending   # only the named ones

Reads the Phase 1 base tables (src/eda/base_tables.py) and nothing else. Each rule is written in RULES below before
the tables are built. Outputs are small summaries in reports/eda/ (committed), one CSV per table.
"""

from __future__ import annotations

import csv
import sys

from .. import config
from .base_tables import CELLS, DATA, OUT, VC_DIR, con

VC = f"read_parquet('{VC_DIR / 'fy*.parquet'}')"
CE = f"read_parquet('{CELLS}')"
AGENCY_LABELS = f"read_parquet('{DATA / 'labels_agency.parquet'}')"
PSC_LABELS = f"read_parquet('{DATA / 'labels_psc.parquet'}')"
DOD = "097"
KIND = ("CASE WHEN psc IS NULL OR trim(psc) = '' THEN 'blank' WHEN left(psc, 1) BETWEEN '0' AND '9' THEN 'product' "
        "WHEN left(psc, 1) = 'A' THEN 'research' ELSE 'service' END")
BANDS = (("1,500 or less", "hhi <= 1500"), ("above 1,500 to 1,800", "hhi > 1500 AND hhi <= 1800"),
         ("above 1,800 to 2,500", "hhi > 1800 AND hhi <= 2500"), ("above 2,500", "hhi > 2500"), ("no HHI", "hhi IS NULL"))
BAND_CASE = "CASE " + " ".join(f"WHEN {cond} THEN '{name}'" for name, cond in BANDS) + " END"
VENDOR_BUCKETS = ((1, 1), (2, 2), (3, 3), (4, 5), (6, 10), (11, 25), (26, 100), (101, None))
# Known cases for face validity, for the sponsor to confirm or extend: DoD buying systems with very few makers.
FACE_VALIDITY = ((DOD, "1905"), (DOD, "1510"), (DOD, "1520"), (DOD, "1410"), (DOD, "2350"))
TOP_AGENCIES = 15

RULES = {
    "source": "Every table reads data/eda/cells.parquet and data/eda/vendor_cells/, as built by src/eda/base_tables.py.",
    "kind": "Kind of purchase from the product code's first character: a digit is a product, A is research, any other "
            "letter is a service, and a blank code is its own group.",
    "dod": f"The Department of Defense is awarding agency code {DOD}. Every other code counts as civilian.",
    "year_net": "A variant's year net is the sum of its cells' nets, so the shares of V1 use V1's own total.",
    "bands": "HHI bands: " + "; ".join(n for n, _ in BANDS) + ". 1,800 is the 2023 Merger Guidelines' line and 2,500 "
             "the 2010 Horizontal Merger Guidelines' line for a highly concentrated market.",
    "weighted": "Dollar-weighted quantiles take cells with an HHI and a net above zero, weighted by the cell's net.",
    "spread": "Cells holding a share of the year's dollars: cells with a net above zero, sorted by net from largest, "
              "counted until their running net reaches the share of the summed positive cell nets.",
    "band_changes": "A cell changes band when its band under a variant differs from its band under V0, for cells present "
                    "in both. V8c groups product codes differently, so it has no cell-by-cell comparison.",
    "drivers": "For each pair of consecutive years under V1, each cell's change in net dollars counted above 2,500 (its "
               "net when its HHI is above 2,500, zero otherwise). The 10 cells with the largest change either way.",
    "face_validity": "Each year's V1 score for the cells in FACE_VALIDITY.",
    "example_row": "The largest FY2025 row by amount in DoD's fixed-wing aircraft segment (1510), as published.",
}


def write(name: str, cols: list[str], rows: list[tuple]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    print(f"{name}: {len(rows)} rows", flush=True)


def query(name: str, sql: str) -> None:
    c = con()
    res = c.execute(sql)
    write(name, [x[0] for x in res.description], res.fetchall())


# ============================================================================================ Phase 2


def spending() -> None:
    query("spending_by_year", f"""
        SELECT fiscal_year, SUM(rows) AS rows, SUM(rows_10k) AS rows_10k, ROUND(SUM(net), 2) AS net, ROUND(SUM(gross), 2) AS gross,
               ROUND(SUM(net_v1), 2) AS net_v1, ROUND(SUM(net_v1) FILTER (WHERE ag = '{DOD}'), 2) AS net_v1_dod,
               ROUND(SUM(net_v1) FILTER (WHERE ag <> '{DOD}'), 2) AS net_v1_civilian,
               ROUND(SUM(net_v1) FILTER (WHERE {KIND} = 'product'), 2) AS net_v1_product,
               ROUND(SUM(net_v1) FILTER (WHERE {KIND} = 'service'), 2) AS net_v1_service,
               ROUND(SUM(net_v1) FILTER (WHERE {KIND} = 'research'), 2) AS net_v1_research,
               ROUND(SUM(v1_vehicle), 2) AS net_v1_orders_under_vehicles,
               ROUND(100 * SUM(v1_vehicle) / SUM(net_v1), 2) AS orders_under_vehicles_pct,
               ROUND(SUM(net_mfa), 2) AS net_mfa, ROUND(SUM(net) FILTER (WHERE vendor = '(no ID)'), 2) AS net_no_id,
               ROUND(SUM(net_mint), 2) AS net_mint
        FROM {VC} GROUP BY 1 ORDER BY 1""")
    query("spending_by_agency", f"""
        WITH a AS (SELECT fiscal_year, ag, SUM(net_v1) AS net_v1, SUM(rows_10k_v1) AS rows_10k_v1, SUM(v1_vehicle) AS vehicle
                   FROM {VC} GROUP BY 1, 2),
        top AS (SELECT ag FROM a GROUP BY ag ORDER BY SUM(net_v1) DESC LIMIT {TOP_AGENCIES})
        SELECT fiscal_year, CASE WHEN ag IN (SELECT ag FROM top) THEN ag ELSE 'other' END AS agency_code,
               COALESCE(any_value(l.label_latest) FILTER (WHERE ag IN (SELECT ag FROM top)), 'Every other agency') AS agency,
               ROUND(SUM(net_v1), 2) AS net_v1, SUM(rows_10k_v1) AS rows_10k_v1,
               ROUND(100 * SUM(vehicle) / NULLIF(SUM(net_v1), 0), 2) AS orders_under_vehicles_pct
        FROM a LEFT JOIN {AGENCY_LABELS} l ON l.code = a.ag GROUP BY 1, 2 ORDER BY 1, 4 DESC""")
    query("cell_spread", f"""
        WITH c AS (SELECT fiscal_year, net, SUM(net) OVER (PARTITION BY fiscal_year ORDER BY net DESC ROWS UNBOUNDED PRECEDING) AS run,
                          SUM(net) OVER (PARTITION BY fiscal_year) AS tot
                   FROM {CE} WHERE variant = 'V1' AND net > 0)
        SELECT fiscal_year, COUNT(*) AS cells_with_positive_net,
               COUNT(*) FILTER (WHERE run - net < 0.5 * tot) AS cells_for_50pct,
               COUNT(*) FILTER (WHERE run - net < 0.8 * tot) AS cells_for_80pct,
               COUNT(*) FILTER (WHERE run - net < 0.95 * tot) AS cells_for_95pct,
               ROUND(quantile_cont(net, 0.25), 2) AS cell_net_p25, ROUND(quantile_cont(net, 0.5), 2) AS cell_net_median,
               ROUND(quantile_cont(net, 0.75), 2) AS cell_net_p75, ROUND(quantile_cont(net, 0.99), 2) AS cell_net_p99,
               ROUND(MAX(net), 2) AS cell_net_max
        FROM c GROUP BY 1 ORDER BY 1""")


# ============================================================================================ Phase 3


def by_year() -> None:
    bands = ", ".join(f"ROUND(100 * COALESCE(SUM(net) FILTER (WHERE {cond}), 0) / SUM(net), 2) AS \"{name} pct of net\"" for name, cond in BANDS)
    query("concentration_by_year", f"""
        SELECT variant, fiscal_year, COUNT(*) AS cells, COUNT(hhi) AS scored_cells, COUNT(*) - COUNT(hhi) AS unscored_cells,
               ROUND(COALESCE(SUM(net) FILTER (WHERE hhi IS NULL), 0), 2) AS unscored_net,
               quantile_cont(vendors, 0.5) FILTER (WHERE hhi IS NOT NULL) AS median_vendors,
               quantile_cont(positive_vendors, 0.5) FILTER (WHERE hhi IS NOT NULL) AS median_positive_vendors,
               COUNT(*) FILTER (WHERE positive_vendors = 1) AS one_positive_vendor_cells,
               ROUND(100 * COALESCE(SUM(net) FILTER (WHERE positive_vendors = 1), 0) / SUM(net), 2) AS one_positive_vendor_pct_of_net,
               ROUND(quantile_cont(hhi, 0.25), 1) AS hhi_p25, ROUND(quantile_cont(hhi, 0.5), 1) AS hhi_median,
               ROUND(quantile_cont(hhi, 0.75), 1) AS hhi_p75,
               ROUND(weighted_hhi_median, 1) AS dollar_weighted_median_hhi, ROUND(weighted_top4_median, 1) AS dollar_weighted_median_top4_pct,
               ROUND(100 * COALESCE(SUM(net) FILTER (WHERE hhi > 1800), 0) / SUM(net), 2) AS above_1800_pct_of_net, {bands}
        FROM {CE} JOIN (
            SELECT variant, fiscal_year,
                   arg_min(hhi, CASE WHEN run_h >= tot / 2 THEN run_h END) AS weighted_hhi_median,
                   arg_min(top4_pct, CASE WHEN run_t >= tot / 2 THEN run_t END) AS weighted_top4_median
            FROM (SELECT variant, fiscal_year, hhi, top4_pct,
                         SUM(net) OVER (PARTITION BY variant, fiscal_year ORDER BY hhi ROWS UNBOUNDED PRECEDING) AS run_h,
                         SUM(net) OVER (PARTITION BY variant, fiscal_year ORDER BY top4_pct ROWS UNBOUNDED PRECEDING) AS run_t,
                         SUM(net) OVER (PARTITION BY variant, fiscal_year) AS tot
                  FROM {CE} WHERE hhi IS NOT NULL AND net > 0)
            GROUP BY ALL) USING (variant, fiscal_year)
        GROUP BY variant, fiscal_year, weighted_hhi_median, weighted_top4_median ORDER BY variant, fiscal_year""")


def band_changes() -> None:
    query("band_changes", f"""
        WITH b AS (SELECT variant, fiscal_year, ag, psc, net, {BAND_CASE} AS band FROM {CE} WHERE variant IN ('V0', 'V1', 'V8b'))
        SELECT x.variant, x.fiscal_year, COUNT(*) AS cells_in_both, COUNT(*) FILTER (WHERE x.band <> o.band) AS cells_changing_band,
               ROUND(100.0 * COUNT(*) FILTER (WHERE x.band <> o.band) / COUNT(*), 2) AS cells_changing_band_pct,
               ROUND(SUM(o.net) FILTER (WHERE x.band <> o.band), 2) AS v0_net_in_changing_cells,
               COUNT(*) FILTER (WHERE o.band = 'no HHI' AND x.band <> 'no HHI') AS newly_scored,
               COUNT(*) FILTER (WHERE o.band <> 'no HHI' AND x.band = 'no HHI') AS newly_unscored,
               COUNT(*) FILTER (WHERE o.band <> 'above 2,500' AND x.band = 'above 2,500') AS into_above_2500,
               COUNT(*) FILTER (WHERE o.band = 'above 2,500' AND x.band <> 'above 2,500') AS out_of_above_2500
        FROM b x JOIN b o ON o.variant = 'V0' AND (o.fiscal_year, o.ag, o.psc) = (x.fiscal_year, x.ag, x.psc)
        WHERE x.variant <> 'V0' GROUP BY 1, 2 ORDER BY 1, 2""")


def by_group() -> None:
    def weighted(group: str, name: str) -> None:
        query(name, f"""
            WITH c AS (SELECT fiscal_year, {group} AS grp, hhi, net FROM {CE} WHERE variant = 'V1'),
            w AS (SELECT fiscal_year, grp, hhi, net,
                         SUM(net) OVER (PARTITION BY fiscal_year, grp ORDER BY hhi ROWS UNBOUNDED PRECEDING) AS run,
                         SUM(net) OVER (PARTITION BY fiscal_year, grp) AS tot
                  FROM c WHERE hhi IS NOT NULL AND net > 0)
            SELECT c.fiscal_year, c.grp AS "group", COUNT(*) AS cells, ROUND(SUM(c.net), 2) AS net,
                   ROUND(100 * COALESCE(SUM(c.net) FILTER (WHERE c.hhi > 2500), 0) / SUM(c.net), 2) AS above_2500_pct_of_net,
                   ROUND(any_value(m.wm), 1) AS dollar_weighted_median_hhi
            FROM c LEFT JOIN (SELECT fiscal_year, grp, arg_min(hhi, CASE WHEN run >= tot / 2 THEN run END) AS wm FROM w GROUP BY ALL) m
                 USING (fiscal_year, grp)
            GROUP BY 1, 2 ORDER BY 1, 4 DESC""")
    top = (f"(SELECT ag FROM {CE} WHERE variant = 'V1' GROUP BY ag ORDER BY SUM(net) DESC LIMIT {TOP_AGENCIES})")
    weighted(f"CASE WHEN ag IN {top} THEN ag ELSE 'other' END", "concentration_by_agency")
    weighted(KIND, "concentration_by_kind")
    weighted(f"CASE WHEN ag = '{DOD}' THEN 'DoD' ELSE 'civilian' END", "concentration_dod_civilian")


def vendor_floor() -> None:
    bucket = "CASE " + " ".join(
        f"WHEN positive_vendors BETWEEN {lo} AND {hi} THEN '{lo} to {hi}'" if hi and lo != hi else
        (f"WHEN positive_vendors = {lo} THEN '{lo}'" if hi else f"WHEN positive_vendors >= {lo} THEN '{lo} or more'")
        for lo, hi in VENDOR_BUCKETS) + " END"
    query("hhi_by_vendor_count", f"""
        SELECT {bucket} AS positive_vendors, MIN(positive_vendors) AS bucket_start, COUNT(*) AS cell_years,
               ROUND(10000.0 / MIN(positive_vendors), 1) AS hhi_floor_at_bucket_start,
               ROUND(quantile_cont(hhi, 0.1), 1) AS hhi_p10, ROUND(quantile_cont(hhi, 0.5), 1) AS hhi_median,
               ROUND(quantile_cont(hhi, 0.9), 1) AS hhi_p90, ROUND(SUM(net), 2) AS net,
               ROUND(100 * SUM(net) / (SELECT SUM(net) FROM {CE} WHERE variant = 'V1' AND hhi IS NOT NULL), 2) AS pct_of_scored_net
        FROM {CE} WHERE variant = 'V1' AND hhi IS NOT NULL GROUP BY 1 ORDER BY 2""")


def drivers() -> None:
    query("drivers_above_2500", f"""
        WITH c AS (SELECT fiscal_year, ag, psc, CASE WHEN hhi > 2500 THEN net ELSE 0 END AS hi, net, hhi, top1_pct
                   FROM {CE} WHERE variant = 'V1'),
        d AS (SELECT COALESCE(n.fiscal_year, p.fiscal_year + 1) AS fiscal_year, COALESCE(n.ag, p.ag) AS ag,
                     COALESCE(n.psc, p.psc) AS psc, COALESCE(n.hi, 0) - COALESCE(p.hi, 0) AS change, p.net AS net_before,
                     n.net AS net_after, p.hhi AS hhi_before, n.hhi AS hhi_after, p.top1_pct AS top1_before, n.top1_pct AS top1_after
              FROM c n FULL JOIN c p ON (p.fiscal_year + 1, p.ag, p.psc) = (n.fiscal_year, n.ag, n.psc)
              WHERE COALESCE(n.fiscal_year, p.fiscal_year + 1) BETWEEN {config.FIRST_FY + 1} AND {config.LAST_FY}),
        r AS (SELECT *, row_number() OVER (PARTITION BY fiscal_year ORDER BY abs(change) DESC) AS rk FROM d WHERE fiscal_year IS NOT NULL)
        SELECT r.fiscal_year, rk AS "rank", r.ag AS agency_code, a.label_latest AS agency, r.psc, p.label_latest AS psc_label,
               ROUND(change, 2) AS change_in_net_above_2500, ROUND(net_before, 2) AS net_before, ROUND(net_after, 2) AS net_after,
               ROUND(hhi_before, 1) AS hhi_before, ROUND(hhi_after, 1) AS hhi_after,
               ROUND(top1_before, 1) AS largest_share_before, ROUND(top1_after, 1) AS largest_share_after
        FROM r LEFT JOIN {AGENCY_LABELS} a ON a.code = r.ag LEFT JOIN {PSC_LABELS} p ON p.code = r.psc
        WHERE rk <= 10 ORDER BY 1, 2""")


def face_validity() -> None:
    cells = ", ".join(f"('{a}', '{p}')" for a, p in FACE_VALIDITY)
    query("face_validity", f"""
        SELECT c.ag AS agency_code, c.psc, p.label_latest AS psc_label, c.fiscal_year, ROUND(c.net, 2) AS net, c.positive_vendors,
               ROUND(hhi, 1) AS hhi, ROUND(top4_pct, 1) AS top4_pct, ROUND(top1_pct, 1) AS largest_share
        FROM {CE} c LEFT JOIN {PSC_LABELS} p ON p.code = c.psc
        WHERE variant = 'V1' AND (c.ag, c.psc) IN ({cells}) ORDER BY 1, 2, 4""")


def example_row() -> None:
    """The largest FY2025 row in DoD's fixed-wing aircraft segment, shown in the deck as what one row of the data is."""
    from ..analyses_v2 import files
    query("example_row", f"""
        SELECT action_date, awarding_agency_name, awarding_sub_agency_name, product_or_service_code,
               product_or_service_code_description, recipient_parent_name, recipient_name, federal_action_obligation,
               extent_competed, type_of_contract_pricing, award_id_piid
        FROM read_parquet({files(2025)!r}) WHERE awarding_agency_code = '{DOD}' AND product_or_service_code = '1510'
        ORDER BY TRY_CAST(federal_action_obligation AS DOUBLE) DESC LIMIT 1""")


STEPS = {"spending": spending, "by_year": by_year, "band_changes": band_changes, "by_group": by_group,
         "vendor_floor": vendor_floor, "drivers": drivers, "face_validity": face_validity,
         "example_row": example_row}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not CELLS.exists():
        print("No base tables yet. Run python -m src.eda.base_tables first.")
        return 1
    for name in argv or STEPS:
        STEPS[name]()
    (OUT / "concentration_rules.csv").write_text("rule,text\n" + "".join(f'{k},"{v}"\n' for k, v in RULES.items()),
                                                  encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
