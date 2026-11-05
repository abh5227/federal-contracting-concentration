"""Is the rise in concentration real? Trend tests against chance, for the civilian agencies (Phase 5 of docs/eda/eda_plan.md).

    python -m src.eda.trends            # every table
    python -m src.eda.trends yearly     # only the named ones

Looks at concentration alone, as the plan's ground rule 2 allows: no feature is compared with rising lines here. Reads
the Phase 1 base tables and the civilian tables of src/eda/concentration.py. Each rule is written in RULES below before
the tables are built. Outputs are small summaries in reports/eda/ (committed).
"""

from __future__ import annotations

import csv
import math
import random
import sys
from collections import defaultdict

from .. import config
from .base_tables import CELLS, OUT, con
from .concentration import CE, DOD, write

SEED = 20261105
YEAR_SHUFFLES = 20000
LINE_SHUFFLES = 500
MIN_YEARS, MIN_DOLLARS = 6, 1e7          # the thin-line point of the rising counts in src/eda/lines.py
CUTOFFS = (250, 500, 1000, 1500, 2000, 3000)
FDR_Q = 0.10

RULES = {
    "variant": "Every table uses variant V1 and the civilian agencies: every awarding agency except Defense (097).",
    "yearly": "The yearly series is each year's share of civilian dollars in segments with HHI above 2,500 "
              "(civilian_by_year.csv). Tests: Kendall's tau between year and share; the least-squares slope in points per "
              "year; and the mean of the last 6 years minus the mean of the first 6. Each p-value is one-sided (a rise) "
              f"and comes from {YEAR_SHUFFLES:,} shuffles of the 18 yearly values, seed {SEED}. Shuffling assumes years are "
              "exchangeable, which neighbouring years with shared multi-year awards are not, so the p-values are too "
              "small if anything. The same tests run on the series with Veterans Affairs left out, and on the share of "
              "segments (unweighted) above 2,500.",
    "lines": "A line is one civilian agency and one product code over FY2008 to FY2025, kept when it has at least "
             f"{MIN_YEARS} scored years and at least ${MIN_DOLLARS:,.0f} in net over them (product codes carry across the "
             "code changes for 88.5% of dollars, psc_era_patterns.csv). Gain: the mean HHI of its last 3 scored years "
             "minus the mean of its first 3.",
    "chance_share": "For each cutoff, the share of lines whose gain is at least the cutoff, observed and after shuffling "
                    f"each line's own years ({LINE_SHUFFLES} times). The ratio shuffled over observed estimates the share "
                    "of flagged lines that chance alone would flag.",
    "line_test": f"Each line's own permutation p-value: the share of its {LINE_SHUFFLES} shuffles with a gain at least the "
                 "observed one. A line is a tested riser when its gain is at least 500 points and its p-value passes the "
                 f"Benjamini-Hochberg rule at q = {FDR_Q} across all kept lines.",
}


def kendall_tau(xs: list[float], ys: list[float]) -> float:
    n, s = len(xs), 0
    for i in range(n):
        for j in range(i + 1, n):
            s += (1 if (xs[j] - xs[i]) * (ys[j] - ys[i]) > 0 else -1 if (xs[j] - xs[i]) * (ys[j] - ys[i]) < 0 else 0)
    return s / (n * (n - 1) / 2)


def slope(xs: list[float], ys: list[float]) -> float:
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)


def late_minus_early(ys: list[float], k: int = 6) -> float:
    return sum(ys[-k:]) / k - sum(ys[:k]) / k


def series() -> dict[str, tuple[list[int], list[float]]]:
    c = con()
    out = {}
    rows = c.execute(f"""SELECT fiscal_year,
                            100 * SUM(net) FILTER (WHERE hhi > 2500) / SUM(net),
                            100 * SUM(net) FILTER (WHERE hhi > 2500 AND ag <> '036') / SUM(net) FILTER (WHERE ag <> '036'),
                            100.0 * COUNT(*) FILTER (WHERE hhi > 2500) / COUNT(hhi)
                         FROM {CE} WHERE variant = 'V1' AND ag <> '{DOD}' GROUP BY 1 ORDER BY 1""").fetchall()
    yrs = [r[0] for r in rows]
    out["civilian, share of dollars"] = (yrs, [float(r[1]) for r in rows])
    out["civilian without Veterans Affairs, share of dollars"] = (yrs, [float(r[2]) for r in rows])
    out["civilian, share of scored segments (unweighted)"] = (yrs, [float(r[3]) for r in rows])
    return out


def yearly() -> None:
    rng = random.Random(SEED)
    rows = []
    for name, (yrs, ys) in series().items():
        x = [float(y) for y in yrs]
        obs = (kendall_tau(x, ys), slope(x, ys), late_minus_early(ys))
        ge = [0, 0, 0]
        perm = ys[:]
        for _ in range(YEAR_SHUFFLES):
            rng.shuffle(perm)
            stats = (kendall_tau(x, perm), slope(x, perm), late_minus_early(perm))
            for i in range(3):
                ge[i] += stats[i] >= obs[i]
        p = [(g + 1) / (YEAR_SHUFFLES + 1) for g in ge]
        rows.append((name, yrs[0], yrs[-1], round(ys[0], 2), round(ys[-1], 2), round(obs[0], 3), round(p[0], 4),
                     round(obs[1], 3), round(p[1], 4), round(obs[2], 2), round(p[2], 4)))
    write("trend_yearly_tests", ["series", "first_year", "last_year", "first_value_pct", "last_value_pct", "kendall_tau",
                                 "tau_p_one_sided", "slope_points_per_year", "slope_p_one_sided",
                                 "last6_minus_first6_points", "last6_minus_first6_p_one_sided"], rows)


def civilian_lines() -> dict[tuple, list[tuple]]:
    out = defaultdict(list)
    for ag, psc, fy, h, net in con().execute(f"""
            SELECT ag, psc, fiscal_year, hhi, CAST(net AS DOUBLE) FROM read_parquet('{CELLS}')
            WHERE variant = 'V1' AND ag <> '{DOD}' AND hhi IS NOT NULL ORDER BY 1, 2, 3""").fetchall():
        out[(ag, psc)].append((fy, h, net))
    return {k: v for k, v in out.items() if len(v) >= MIN_YEARS and sum(x[2] for x in v) >= MIN_DOLLARS}


def gain(vals: list[float]) -> float:
    return sum(vals[-3:]) / 3 - sum(vals[:3]) / 3


def lines() -> None:
    kept = civilian_lines()
    rng = random.Random(SEED)
    obs = {k: gain([x[1] for x in v]) for k, v in kept.items()}
    shuffled = {}
    pvals = {}
    for k, v in kept.items():
        vals = [x[1] for x in v]
        g = []
        for _ in range(LINE_SHUFFLES):
            rng.shuffle(vals)
            g.append(gain(vals))
        shuffled[k] = g
        pvals[k] = (sum(1 for x in g if x >= obs[k]) + 1) / (LINE_SHUFFLES + 1)
    n = len(kept)
    rows = []
    for cut in CUTOFFS:
        o = sum(1 for k in kept if obs[k] >= cut)
        s = sum(sum(1 for x in shuffled[k] if x >= cut) for k in kept) / LINE_SHUFFLES
        of = sum(1 for k in kept if obs[k] <= -cut)
        sf = sum(sum(1 for x in shuffled[k] if x <= -cut) for k in kept) / LINE_SHUFFLES
        rows.append((cut, n, o, round(100 * o / n, 2), round(100 * s / n, 2), round(100 * s / o, 1) if o else "",
                     of, round(100 * of / n, 2), round(100 * sf / n, 2)))
    write("trend_lines_chance", ["cutoff", "lines", "rising", "rising_pct", "rising_pct_shuffled", "chance_share_of_rising_pct",
                                 "falling", "falling_pct", "falling_pct_shuffled"], rows)
    # Benjamini-Hochberg across all kept lines, on the one-sided rising p-values
    order = sorted(kept, key=lambda k: pvals[k])
    passed, cutoff_rank = set(), 0
    for rank, k in enumerate(order, start=1):
        if pvals[k] <= FDR_Q * rank / n:
            cutoff_rank = rank
    passed = {k for k in order[:cutoff_rank]}
    risers = [k for k in passed if obs[k] >= 500]
    dollars = lambda ks: sum(sum(x[2] for x in kept[k]) for k in ks)
    write("trend_lines_tested", ["lines", "lines_with_gain_500_or_more", "tested_risers_bh_q10",
                                 "tested_risers_pct_of_lines", "net_in_tested_risers", "net_in_all_kept_lines"],
          [(n, sum(1 for k in kept if obs[k] >= 500), len(risers), round(100 * len(risers) / n, 2),
            round(dollars(risers), 2), round(dollars(kept), 2))])
    write("trend_tested_risers", ["agency_code", "psc", "scored_years", "first_year", "last_year", "hhi_first3_mean",
                                  "hhi_last3_mean", "gain", "p_value", "net_all_years"],
          sorted(((k[0], k[1], len(kept[k]), kept[k][0][0], kept[k][-1][0], round(sum(x[1] for x in kept[k][:3]) / 3, 1),
                   round(sum(x[1] for x in kept[k][-3:]) / 3, 1), round(obs[k], 1), round(pvals[k], 4),
                   round(sum(x[2] for x in kept[k]), 2)) for k in risers), key=lambda r: -r[9]))


EARLY, LATE = (2012, 2014), (2023, 2025)


def decompose() -> None:
    """Which segments moved the civilian share between two 3-year windows. The contributions add up exactly to the change."""
    from .concentration import AGENCY_LABELS, PSC_LABELS, vendor_names
    c = con()
    win = lambda w: f"fiscal_year BETWEEN {w[0]} AND {w[1]}"
    res = c.execute(f"""
        WITH x AS (SELECT ag, psc, fiscal_year, CAST(net AS DOUBLE) AS net, CASE WHEN hhi > 2500 THEN CAST(net AS DOUBLE) ELSE 0 END AS hi
                   FROM read_parquet('{CELLS}') WHERE variant = 'V1' AND ag <> '{DOD}'),
        t AS (SELECT SUM(net) FILTER (WHERE {win(EARLY)}) AS te, SUM(net) FILTER (WHERE {win(LATE)}) AS tl FROM x),
        s AS (SELECT ag, psc, COALESCE(SUM(hi) FILTER (WHERE {win(EARLY)}), 0) AS he, COALESCE(SUM(hi) FILTER (WHERE {win(LATE)}), 0) AS hl,
                     COALESCE(SUM(net) FILTER (WHERE {win(EARLY)}), 0) AS ne, COALESCE(SUM(net) FILTER (WHERE {win(LATE)}), 0) AS nl
              FROM x GROUP BY 1, 2)
        SELECT s.ag, s.psc, a.label_latest, p.label_latest, s.he, s.hl, s.ne, s.nl, 100 * (s.hl / t.tl - s.he / t.te) AS contrib, t.te, t.tl
        FROM s CROSS JOIN t LEFT JOIN {AGENCY_LABELS} a ON a.code = s.ag LEFT JOIN {PSC_LABELS} p ON p.code = s.psc""").fetchall()
    te, tl = res[0][9], res[0][10]
    he_all, hl_all = sum(r[4] for r in res), sum(r[5] for r in res)
    change = 100 * (hl_all / tl - he_all / te)
    kind = lambda r: ("newly concentrated" if r[4] <= 0 < r[5] else "no longer concentrated" if r[5] <= 0 < r[4]
                      else "concentrated in both" if r[4] > 0 and r[5] > 0 else "never concentrated")
    groups = defaultdict(lambda: [0, 0.0])
    for r in res:
        g = groups[kind(r)]
        g[0] += 1
        g[1] += r[8]
    write("trend_decomposition_summary", ["early_window", "late_window", "share_early_pct", "share_late_pct", "change_points",
                                          "segment_group", "segments", "contribution_points"],
          [(f"FY{EARLY[0]} to FY{EARLY[1]}", f"FY{LATE[0]} to FY{LATE[1]}", round(100 * he_all / te, 2), round(100 * hl_all / tl, 2),
            round(change, 2), g, n, round(v, 2)) for g, (n, v) in sorted(groups.items(), key=lambda kv: -kv[1][1])])
    by_agency = defaultdict(float)
    for r in res:
        by_agency[r[2] or r[0]] += r[8]
    write("trend_decomposition_by_agency", ["agency", "contribution_points"],
          sorted(((a, round(v, 2)) for a, v in by_agency.items()), key=lambda x: -abs(x[1]))[:15])
    top = sorted(res, key=lambda r: -abs(r[8]))[:20]
    leaders = {(ag, psc): v for ag, psc, v in c.execute(f"""
        SELECT ag, psc, arg_max(largest_vendor, net) FROM read_parquet('{CELLS}')
        WHERE variant = 'V1' AND fiscal_year BETWEEN {LATE[0]} AND {LATE[1]} AND hhi > 2500 GROUP BY 1, 2""").fetchall()}
    names = vendor_names(sorted({v for v in leaders.values() if v}), LATE[1])
    pos = sorted((r[8] for r in res if r[8] > 0), reverse=True)
    run, k50 = 0.0, 0
    for k, v in enumerate(pos, start=1):
        run += v
        if run >= sum(pos) / 2:
            k50 = k
            break
    write("trend_decomposition_top", ["rank", "agency", "psc", "psc_label", "segment_group", "net_early", "net_late",
                                      "contribution_points", "largest_vendor_late_window"],
          [(i + 1, r[2], r[1], r[3], kind(r), round(r[6], 2), round(r[7], 2), round(r[8], 2), names.get(leaders.get((r[0], r[1])), ""))
           for i, r in enumerate(top)])
    write("trend_decomposition_breadth", ["segments_with_positive_contribution", "positive_contribution_points",
                                          "segments_for_half_of_positive_contribution"], [(len(pos), round(sum(pos), 2), k50)])


STEPS = {"yearly": yearly, "lines": lines, "decompose": decompose}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not CELLS.exists():
        print("No base tables yet. Run python -m src.eda.base_tables first.")
        return 1
    for name in argv or STEPS:
        STEPS[name]()
    with open(OUT / "trends_rules.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rule", "text"])
        w.writerows(RULES.items())
    return 0


if __name__ == "__main__":
    sys.exit(main())
