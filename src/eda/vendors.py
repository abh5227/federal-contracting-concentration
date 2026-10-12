"""Phase 8 of the EDA plan (docs/eda/eda_plan.md): vendors.

    python -m src.eda.vendors            # every table
    python -m src.eda.vendors top100     # only the named ones

Reads the Phase 1 base tables, and Layer A only for display names of the largest parents. Each rule is written in
RULES below before the tables are built. Outputs are small summaries in reports/eda/ (committed). Vendor IDs appear
in the top-100 list, which is the hand-check list for the week 6 milestone.
"""

from __future__ import annotations

import sys

from ..analyses_v2 import files
from .base_tables import CELLS, con, years
from .concentration import CE, VC, query, write

TOP = 100

RULES = {
    "vendor": "The vendor key of src/analyses_v2.py, under V1.",
    "top100": "The 100 vendors with the largest V1 net over FY2008 to FY2025, with their net in each year.",
    "names": "Display name of a vendor in a year: the recipient_parent_name_raw carrying the most gross dollars on its rows "
             "that year, or the recipient_name where the row has no parent. name_most_dollars is the same over all 18 years. Weighted by dollars, because a parent's many "
             "small rows can carry a subsidiary's name (the most common name by rows showed Lockheed Martin's ID as "
             "Sikorsky). Ties go to the first name alphabetically.",
    "counts": "Vendors with at least one kept action of $10,000 or more in the year (decision 3 as proposed), and every "
              "vendor with a kept row, for comparison.",
    "turnover": "Inside one line, a vendor enters in a year when it has an action of $10,000 or more that year and none "
                "the year before, and leaves in the mirror case. Lines scored in both years only.",
    "leads": "Cells per year in which a top-20 vendor has the largest positive net, under V1.",
}


def top_ids(n: int = TOP) -> list[str]:
    return [r[0] for r in con().execute(f"""SELECT vendor FROM {VC} WHERE rows_v1 > 0 GROUP BY 1
                                            ORDER BY SUM(net_v1) DESC LIMIT {n}""").fetchall()]


def top100() -> None:
    ids = top_ids()
    c = con()
    names, weight = {}, {}
    idl = "[" + ", ".join(f"'{i}'" for i in ids) + "]"
    for fy in years():
        for v, name, n, rank in c.execute(f"""
                WITH r AS (SELECT COALESCE(NULLIF(trim(recipient_parent_uei), ''), NULLIF(trim(recipient_uei), '')) AS v,
                                  CASE WHEN NULLIF(trim(recipient_parent_uei), '') IS NOT NULL THEN recipient_parent_name_raw
                                       ELSE recipient_name END AS name
                                  , abs(TRY_CAST(NULLIF(federal_action_obligation, '') AS DOUBLE)) AS g
                           FROM read_parquet({files(fy)!r}))
                SELECT v, name, SUM(g) AS n, dense_rank() OVER (PARTITION BY v ORDER BY name) AS rank
                FROM r WHERE list_contains({idl}, v) GROUP BY 1, 2""").fetchall():
            weight[(v, name)] = weight.get((v, name), 0) + (n or 0)
            best = names.get((v, fy))
            if best is None or ((n or 0), -rank) > best[1]:
                names[(v, fy)] = (name, ((n or 0), -rank))
    names = {k: x[0] for k, x in names.items()}
    overall = {}
    for (v, name), w in weight.items():
        if v not in overall or (w, name) > (overall[v][1], overall[v][0]):
            overall[v] = (name, w)
    yrs = years()
    res = c.execute(f"""SELECT vendor, fiscal_year, SUM(net_v1) FROM {VC} WHERE rows_v1 > 0 AND list_contains({idl}, vendor)
                        GROUP BY 1, 2""").fetchall()
    net = {(v, fy): x for v, fy, x in res}
    rows = []
    for rank, v in enumerate(ids, start=1):
        latest = next((names[(v, fy)] for fy in reversed(yrs) if (v, fy) in names), "")
        changes = len({names[(v, fy)] for fy in yrs if (v, fy) in names})
        rows.append((rank, v, latest, overall.get(v, ("", 0))[0], changes, round(sum(net.get((v, fy), 0) for fy in yrs), 2),
                     *(round(net[(v, fy)], 2) if (v, fy) in net else "" for fy in yrs)))
    write("top100_vendors", ["rank", "vendor_id", "name_latest_year", "name_most_dollars", "distinct_yearly_names", "net_all_years",
                             *(f"net_fy{fy}" for fy in yrs)], rows)
    write("top100_vendor_names", ["vendor_id", "fiscal_year", "display_name"],
          sorted((v, fy, n) for (v, fy), n in names.items()))


def counts() -> None:
    query("vendor_counts", f"""
        SELECT fiscal_year, COUNT(DISTINCT vendor) FILTER (WHERE rows_10k_v1 > 0) AS vendors_with_action_10k,
               COUNT(DISTINCT vendor) FILTER (WHERE rows_v1 > 0) AS vendors_any_kept_row,
               ROUND(100 * SUM(net_mfa) / SUM(net), 3) AS mfa_pct_of_net,
               ROUND(100 * SUM(net) FILTER (WHERE vendor = '(no ID)') / SUM(net), 3) AS no_id_pct_of_net,
               SUM(rows_mfa) AS mfa_rows, SUM(rows) FILTER (WHERE vendor = '(no ID)') AS no_id_rows
        FROM {VC} GROUP BY 1 ORDER BY 1""")


def turnover() -> None:
    query("vendor_turnover", f"""
        WITH v AS (SELECT DISTINCT fiscal_year, ag, psc, vendor FROM {VC} WHERE rows_10k_v1 > 0),
        scored AS (SELECT n.ag, n.psc, n.fiscal_year FROM {CE} n JOIN {CE} p
                 ON p.variant = 'V1' AND (p.ag, p.psc, p.fiscal_year + 1) = (n.ag, n.psc, n.fiscal_year)
                 WHERE n.variant = 'V1' AND n.hhi IS NOT NULL AND p.hhi IS NOT NULL),
        e AS (SELECT x.ag, x.psc, x.fiscal_year, COUNT(*) AS n FROM v x
              LEFT JOIN v y ON (y.ag, y.psc, y.vendor, y.fiscal_year) = (x.ag, x.psc, x.vendor, x.fiscal_year - 1)
              WHERE y.vendor IS NULL GROUP BY ALL),
        l AS (SELECT x.ag, x.psc, x.fiscal_year + 1 AS fiscal_year, COUNT(*) AS n FROM v x
              LEFT JOIN v y ON (y.ag, y.psc, y.vendor, y.fiscal_year) = (x.ag, x.psc, x.vendor, x.fiscal_year + 1)
              WHERE y.vendor IS NULL GROUP BY ALL),
        ent AS (SELECT b.fiscal_year, COALESCE(e.n, 0) AS entering, COALESCE(l.n, 0) AS leaving
                FROM scored b LEFT JOIN e USING (ag, psc, fiscal_year) LEFT JOIN l USING (ag, psc, fiscal_year))
        SELECT fiscal_year, COUNT(*) AS lines, ROUND(AVG(entering), 2) AS mean_entering, ROUND(AVG(leaving), 2) AS mean_leaving,
               quantile_cont(entering, 0.5) AS median_entering, quantile_cont(leaving, 0.5) AS median_leaving
        FROM ent GROUP BY 1 ORDER BY 1""")


def leads() -> None:
    ids = "[" + ", ".join(f"'{i}'" for i in top_ids(20)) + "]"
    query("top20_cells_led", f"""
        SELECT largest_vendor AS vendor_id, fiscal_year, COUNT(*) AS cells_led, ROUND(SUM(net), 2) AS net_in_cells_led
        FROM {CE} WHERE variant = 'V1' AND hhi IS NOT NULL AND list_contains({ids}, largest_vendor)
        GROUP BY 1, 2 ORDER BY 1, 2""")


STEPS = {"top100": top100, "counts": counts, "turnover": turnover, "leads": leads}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not CELLS.exists():
        print("No base tables yet. Run python -m src.eda.base_tables first.")
        return 1
    for name in argv or STEPS:
        STEPS[name]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
