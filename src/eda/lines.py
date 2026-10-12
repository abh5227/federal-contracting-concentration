"""Phases 4 and 5 of the EDA plan (docs/eda/eda_plan.md): product code eras, trend lines and the rising rule.

    python -m src.eda.lines            # every table
    python -m src.eda.lines eras       # only the named ones

Reads the Phase 1 base tables (src/eda/base_tables.py). Looks at concentration alone, as the plan's ground rule 2
allows: no feature is compared with rising lines here. Each rule is written in RULES below before the tables are
built. Outputs are small summaries in reports/eda/ (committed), one CSV per table.
"""

from __future__ import annotations

import random
import sys
from collections import defaultdict

from .base_tables import CELLS, con
from .concentration import CE, PSC_LABELS, VC, query, write

ERAS = (("FY2008 to FY2011", 2008, 2011), ("FY2012 to FY2020", 2012, 2020), ("FY2021 to FY2025", 2021, 2025))
ERA_CASE = "CASE " + " ".join(f"WHEN fiscal_year BETWEEN {a} AND {b} THEN '{n}'" for n, a, b in ERAS) + " END"
BREAKS = (2012, 2021)                         # first fiscal year of each new product code manual
MIN_YEARS = (6, 8, 9)                         # 9 is every year of the longest era
MIN_DOLLARS = (1e6, 1e7, 1e8)
KEEP_YEARS, KEEP_DOLLARS = 6, 1e7             # the thin-line point used for the rising counts, until the team picks one
CUTOFFS = (250, 500, 1000)
SHUFFLES = 20
SEED = 20261012
POOLED = ((2012, 2014), (2015, 2017), (2018, 2020))

RULES = {
    "variant": "Every table uses variant V1 (src/eda/base_tables.py).",
    "eras": "Product code eras by fiscal year: " + "; ".join(f"{n}" for n, _, _ in ERAS) + ". The new manuals took "
            "effect on 2011-10-01 (FY2012) and 2020-10-01 (FY2021).",
    "breaks": "At each change, a code stops when it has dollars in the last year before the change and none in the first "
              "year after it, and starts in the mirror case. Dollars are V1 net in the adjacent year.",
    "line": "A trend line is one awarding agency code and one product code, scored in the years where its cell has an HHI. "
            "Inside an era, only that era's years count.",
    "thin_lines": "A line is kept when it has at least the minimum number of scored years and at least the minimum total "
                  "net over those years, inside FY2012 to FY2020. Grid: years " + ", ".join(map(str, MIN_YEARS)) +
                  "; dollars $1 million, $10 million, $100 million.",
    "noise": "The change in HHI between two consecutive years of one line, for lines scored in both years, by the size "
             "of the cell (the mean of the two years' net) in deciles. Pooled: HHI over the summed vendor nets of three "
             "3-year windows inside FY2012 to FY2020, and the change between adjacent windows.",
    "rising": "Inside FY2012 to FY2020, for lines kept at 6 years and $10 million: rising when the mean HHI of its last 3 "
              "scored years is at least the cutoff above the mean of its first 3, falling in the mirror case. Cutoffs "
              + ", ".join(map(str, CUTOFFS)) + ".",
    "shuffle": f"The same counts after shuffling each line's yearly values, {SHUFFLES} times with seed {SEED}, so a line "
               "keeps its values and loses their order. The mean share over the shuffles is what noise alone would give.",
    "traps": "Rising and falling shares by the mean HHI of the first 3 years and by the positive vendors of the first year.",
}


# ============================================================================================ Phase 4


def eras() -> None:
    query("psc_era_patterns", f"""
        WITH p AS (SELECT psc, {ERA_CASE} AS era, SUM(net) AS net FROM {CE} WHERE variant = 'V1' GROUP BY 1, 2),
        q AS (SELECT psc, string_agg(era, ' + ' ORDER BY era) AS eras_present, SUM(net) AS net FROM p GROUP BY psc)
        SELECT eras_present, COUNT(*) AS codes, ROUND(SUM(net), 2) AS net,
               ROUND(100 * SUM(net) / (SELECT SUM(net) FROM q), 2) AS pct_of_net
        FROM q GROUP BY 1 ORDER BY 3 DESC""")
    for brk in BREAKS:
        query(f"psc_break_fy{brk}", f"""
            WITH y AS (SELECT psc, SUM(net) FILTER (WHERE fiscal_year = {brk - 1}) AS before,
                              SUM(net) FILTER (WHERE fiscal_year = {brk}) AS after
                       FROM {CE} WHERE variant = 'V1' AND fiscal_year IN ({brk - 1}, {brk}) GROUP BY psc),
            tot AS (SELECT SUM(before) AS b, SUM(after) AS a FROM y)
            SELECT CASE WHEN after IS NULL THEN 'stops' WHEN before IS NULL THEN 'starts' ELSE 'continues' END AS status,
                   COUNT(*) AS codes, ROUND(SUM(before), 2) AS net_fy{brk - 1}, ROUND(SUM(after), 2) AS net_fy{brk},
                   ROUND(100 * SUM(before) / any_value(tot.b), 2) AS pct_of_fy{brk - 1},
                   ROUND(100 * SUM(after) / any_value(tot.a), 2) AS pct_of_fy{brk}
            FROM y, tot GROUP BY 1 ORDER BY 1""")
        query(f"crosswalk_worklist_fy{brk}", f"""
            WITH y AS (SELECT psc, SUM(net) FILTER (WHERE fiscal_year = {brk - 1}) AS before,
                              SUM(net) FILTER (WHERE fiscal_year = {brk}) AS after
                       FROM {CE} WHERE variant = 'V1' AND fiscal_year IN ({brk - 1}, {brk}) GROUP BY psc)
            SELECT CASE WHEN after IS NULL THEN 'stops' ELSE 'starts' END AS status, y.psc, l.label_latest AS label,
                   ROUND(COALESCE(before, after), 2) AS net_in_adjacent_year
            FROM y LEFT JOIN {PSC_LABELS} l ON l.code = y.psc
            WHERE before IS NULL OR after IS NULL ORDER BY abs(COALESCE(before, after)) DESC LIMIT 100""")
        query(f"psc_group_shift_fy{brk}", f"""
            WITH g AS (SELECT left(psc, 2) AS grp, SUM(net) FILTER (WHERE fiscal_year = {brk - 1}) AS before,
                              SUM(net) FILTER (WHERE fiscal_year = {brk}) AS after
                       FROM {CE} WHERE variant = 'V1' AND fiscal_year IN ({brk - 1}, {brk}) GROUP BY 1),
            t AS (SELECT SUM(before) AS b, SUM(after) AS a FROM g)
            SELECT grp, ROUND(before, 2) AS net_fy{brk - 1}, ROUND(after, 2) AS net_fy{brk},
                   ROUND(100 * before / t.b, 3) AS share_fy{brk - 1}_pct, ROUND(100 * after / t.a, 3) AS share_fy{brk}_pct,
                   ROUND(100 * after / t.a - 100 * before / t.b, 3) AS share_change_points
            FROM g, t ORDER BY abs(COALESCE(100 * after / t.a, 0) - COALESCE(100 * before / t.b, 0)) DESC""")


# ============================================================================================ Phase 5


def series(first: int = 2012, last: int = 2020) -> dict[tuple, list[tuple]]:
    """(agency, product code) -> [(fiscal year, HHI, net, positive vendors)] for scored years inside the window."""
    c = con()
    out = defaultdict(list)
    for ag, psc, fy, h, net, pv in c.execute(f"""
            SELECT ag, psc, fiscal_year, hhi, CAST(net AS DOUBLE), positive_vendors FROM {CE}
            WHERE variant = 'V1' AND hhi IS NOT NULL AND fiscal_year BETWEEN {first} AND {last} ORDER BY 1, 2, 3""").fetchall():
        out[(ag, psc)].append((fy, h, net, pv))
    return out


def thin_lines() -> None:
    s = series()
    total = sum(sum(x[2] for x in v) for v in s.values())
    rows = []
    for my in MIN_YEARS:
        for md in MIN_DOLLARS:
            kept = [v for v in s.values() if len(v) >= my and sum(x[2] for x in v) >= md]
            dollars = sum(sum(x[2] for x in v) for v in kept)
            rows.append((my, int(md), len(s), len(kept), round(dollars, 2), round(100 * dollars / total, 2)))
    write("thin_line_grid", ["min_years", "min_total_net", "lines_in_window", "lines_kept", "net_kept", "pct_of_net_kept"], rows)
    query("line_lengths", f"""
        WITH l AS (SELECT ag, psc, {ERA_CASE} AS era, COUNT(*) AS scored_years FROM {CE}
                   WHERE variant = 'V1' AND hhi IS NOT NULL GROUP BY 1, 2, 3)
        SELECT era, scored_years, COUNT(*) AS lines FROM l GROUP BY 1, 2 ORDER BY 1, 2""")


def noise() -> None:
    query("noise_by_size", f"""
        WITH c AS (SELECT ag, psc, fiscal_year, hhi, net FROM {CE} WHERE variant = 'V1' AND hhi IS NOT NULL),
        d AS (SELECT abs(n.hhi - p.hhi) AS change, (n.net + p.net) / 2 AS size
              FROM c n JOIN c p ON (p.ag, p.psc, p.fiscal_year + 1) = (n.ag, n.psc, n.fiscal_year)
              WHERE n.fiscal_year NOT IN (2012, 2021)),
        q AS (SELECT *, ntile(10) OVER (ORDER BY size) AS decile FROM d)
        SELECT decile, COUNT(*) AS year_pairs, ROUND(MIN(size), 2) AS size_from, ROUND(MAX(size), 2) AS size_to,
               ROUND(quantile_cont(change, 0.5), 1) AS change_median, ROUND(quantile_cont(change, 0.75), 1) AS change_p75,
               ROUND(quantile_cont(change, 0.9), 1) AS change_p90,
               ROUND(100.0 * COUNT(*) FILTER (WHERE change >= 500) / COUNT(*), 2) AS pct_changing_500_or_more
        FROM q GROUP BY 1 ORDER BY 1""")
    windows = " ".join(f"WHEN fiscal_year BETWEEN {a} AND {b} THEN {i}" for i, (a, b) in enumerate(POOLED))
    query("noise_pooled", f"""
        WITH v AS (SELECT ag, psc, CASE {windows} END AS w, vendor, SUM(net_v1) AS net FROM {VC}
                   WHERE rows_v1 > 0 AND fiscal_year BETWEEN {POOLED[0][0]} AND {POOLED[-1][1]} GROUP BY ALL),
        c AS (SELECT ag, psc, w, SUM(net) AS net,
                     10000 * SUM(CAST(net AS DOUBLE) ^ 2) FILTER (WHERE net > 0) / CAST(SUM(net) FILTER (WHERE net > 0) AS DOUBLE) ^ 2 AS hhi
              FROM v GROUP BY ALL HAVING COUNT(*) FILTER (WHERE net > 0) > 0),
        d AS (SELECT abs(n.hhi - p.hhi) AS change FROM c n JOIN c p ON (p.ag, p.psc, p.w + 1) = (n.ag, n.psc, n.w))
        SELECT COUNT(*) AS window_pairs, ROUND(quantile_cont(change, 0.5), 1) AS change_median,
               ROUND(quantile_cont(change, 0.75), 1) AS change_p75, ROUND(quantile_cont(change, 0.9), 1) AS change_p90,
               ROUND(100.0 * COUNT(*) FILTER (WHERE change >= 500) / COUNT(*), 2) AS pct_changing_500_or_more
        FROM d""")


def classify(vals: list[float], cutoff: float) -> str:
    first, last = sum(vals[:3]) / 3, sum(vals[-3:]) / 3
    return "rising" if last - first >= cutoff else "falling" if first - last >= cutoff else "neither"


def rising() -> None:
    kept = [v for v in series().values() if len(v) >= KEEP_YEARS and sum(x[2] for x in v) >= KEEP_DOLLARS]
    if not kept:
        print("rising: no line passes the thin-line rule; nothing written", flush=True)
        return
    rng = random.Random(SEED)
    rows = []
    for cut in CUTOFFS:
        obs = defaultdict(int)
        for v in kept:
            obs[classify([x[1] for x in v], cut)] += 1
        shuf = defaultdict(float)
        for _ in range(SHUFFLES):
            for v in kept:
                vals = [x[1] for x in v]
                rng.shuffle(vals)
                shuf[classify(vals, cut)] += 1 / SHUFFLES
        n = len(kept)
        rows.append((cut, n, obs["rising"], round(100 * obs["rising"] / n, 2), round(100 * shuf["rising"] / n, 2),
                     obs["falling"], round(100 * obs["falling"] / n, 2), round(100 * shuf["falling"] / n, 2)))
    write("rising_counts", ["cutoff", "lines", "rising", "rising_pct", "rising_pct_after_shuffle", "falling", "falling_pct",
                            "falling_pct_after_shuffle"], rows)
    level = lambda h: "below 1,500" if h < 1500 else "1,500 to 2,500" if h <= 2500 else "2,500 to 5,000" if h <= 5000 else "above 5,000"
    vendors = lambda n: "1" if n == 1 else "2 to 3" if n <= 3 else "4 to 10" if n <= 10 else "11 or more"
    out = []
    for label, key in (("starting HHI", lambda v: level(sum(x[1] for x in v[:3]) / 3)),
                       ("starting positive vendors", lambda v: vendors(v[0][3]))):
        groups = defaultdict(lambda: defaultdict(int))
        for v in kept:
            groups[key(v)][classify([x[1] for x in v], 500)] += 1
        for g, cnt in sorted(groups.items()):
            n = sum(cnt.values())
            out.append((label, g, n, round(100 * cnt["rising"] / n, 2), round(100 * cnt["falling"] / n, 2)))
    write("rising_by_start", ["grouped_by", "group", "lines", "rising_pct_at_500", "falling_pct_at_500"], out)


STEPS = {"eras": eras, "thin_lines": thin_lines, "noise": noise, "rising": rising}


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
