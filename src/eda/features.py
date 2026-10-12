"""Phase 7a of the EDA plan (docs/eda/eda_plan.md): coverage and distributions of the candidate features for question 3.

    python -m src.eda.features            # every table
    python -m src.eda.features coverage   # only the named ones

Phase 7a only. No feature is compared with rising lines here: that is phase 7b, which waits for the gate in the plan's
ground rule 2. Reads the Phase 1 base tables. Each rule is written in RULES below before the tables are built.
"""

from __future__ import annotations

import math
import sys

from .base_tables import CELLS, con
from .concentration import KIND, VC, query, write
from .lines import KEEP_DOLLARS, KEEP_YEARS

WINDOW = (2012, 2020)
FEATURES = ("sole_source_share", "follow_on_share", "order_limited_share", "single_offer_share", "fixed_price_share",
            "cost_share", "set_aside_share", "vehicle_share", "start_positive_vendors", "log_size")

RULES = {
    "coverage": "By fiscal year under V1: the share of net dollars in each group of each split (src/eda/base_tables.py), "
                "blank groups included, so a reader sees where a feature is missing.",
    "line_features": f"For lines inside FY{WINDOW[0]} to FY{WINDOW[1]} kept by the thin-line point used for the rising "
                     f"counts ({KEEP_YEARS} scored years, ${KEEP_DOLLARS:,.0f}), each feature is measured over the line's "
                     "first 3 scored years: a split's net divided by the line's net over those years. Single offer: "
                     "competed dollars with one offer over competed dollars with offers reported, FY2012 to FY2017 only. "
                     "Starting positive vendors: the first scored year. Size: log10 of the net over the first 3 years.",
    "out_of_range": "A share below 0 or above 1 comes from deobligations. Counted, never capped here (methods notes, item 4).",
    "correlation": "Pearson correlation between each pair of features, over lines where both are defined and in range.",
}


def coverage() -> None:
    groups = {"umbrella competition": ("v1_competed", "v1_sole_source", "v1_follow_on", "v1_competition_blank", "v1_competition_other"),
              "order competition": ("v1_order_fair", "v1_order_follow_on", "v1_order_limited", "v1_order_blank"),
              "pricing": ("v1_fixed_price", "v1_cost", "v1_time_and_materials", "v1_pricing_blank", "v1_pricing_other"),
              "set-aside": ("v1_set_aside", "v1_no_set_aside", "v1_set_aside_blank"),
              "vehicle": ("v1_vehicle",)}
    cols = ", ".join(f"ROUND(100 * SUM({c}) / SUM(net_v1), 2) AS \"{g}: {c[3:]} pct\"" for g, cs in groups.items() for c in cs)
    query("feature_coverage", f"""
        SELECT fiscal_year, ROUND(SUM(net_v1), 2) AS net_v1, {cols},
               ROUND(100 * SUM(v1_competed_offers_reported) / NULLIF(SUM(v1_competed), 0), 2) AS "offers reported, pct of competed",
               ROUND(100 * SUM(v1_single_offer) / NULLIF(SUM(v1_competed_offers_reported), 0), 2) AS "single offer, pct of competed with offers"
        FROM {VC} GROUP BY 1 ORDER BY 1""")


def line_features() -> list[dict]:
    c = con()
    res = c.execute(f"""
        WITH lc AS (SELECT ag, psc, fiscal_year, net AS cell_net, positive_vendors FROM read_parquet('{CELLS}')
                    WHERE variant = 'V1' AND hhi IS NOT NULL AND fiscal_year BETWEEN {WINDOW[0]} AND {WINDOW[1]}),
        kept AS (SELECT ag, psc FROM lc GROUP BY 1, 2 HAVING COUNT(*) >= {KEEP_YEARS} AND SUM(cell_net) >= {KEEP_DOLLARS}),
        first3 AS (SELECT * FROM (SELECT lc.*, row_number() OVER (PARTITION BY ag, psc ORDER BY fiscal_year) AS k
                                  FROM lc JOIN kept USING (ag, psc)) WHERE k <= 3),
        f AS (SELECT v.ag, v.psc, SUM(net_v1) AS net, SUM(v1_sole_source) AS sole, SUM(v1_follow_on) AS follow,
                     SUM(v1_order_limited) AS lim, SUM(v1_fixed_price) AS fp, SUM(v1_cost) AS cost, SUM(v1_set_aside) AS sa,
                     SUM(v1_vehicle) AS veh,
                     SUM(v1_single_offer) FILTER (WHERE v.fiscal_year <= 2017) AS one,
                     SUM(v1_competed_offers_reported) FILTER (WHERE v.fiscal_year <= 2017) AS rep
              FROM {VC} v JOIN first3 USING (ag, psc, fiscal_year) WHERE rows_v1 > 0 GROUP BY 1, 2)
        SELECT f.ag, f.psc, {KIND.replace('psc', 'f.psc')} AS kind, CAST(net AS DOUBLE), CAST(sole AS DOUBLE), CAST(follow AS DOUBLE),
               CAST(lim AS DOUBLE), CAST(one AS DOUBLE), CAST(rep AS DOUBLE), CAST(fp AS DOUBLE), CAST(cost AS DOUBLE),
               CAST(sa AS DOUBLE), CAST(veh AS DOUBLE),
               (SELECT positive_vendors FROM first3 x WHERE (x.ag, x.psc) = (f.ag, f.psc) AND k = 1) AS pv
        FROM f""").fetchall()
    out = []
    for ag, psc, kind, net, sole, follow, lim, one, rep, fp, cost, sa, veh, pv in res:
        div = lambda a: a / net if net else None
        out.append({"ag": ag, "psc": psc, "kind": kind, "sole_source_share": div(sole), "follow_on_share": div(follow),
                    "order_limited_share": div(lim), "single_offer_share": one / rep if rep else None,
                    "fixed_price_share": div(fp), "cost_share": div(cost), "set_aside_share": div(sa),
                    "vehicle_share": div(veh), "start_positive_vendors": pv,
                    "log_size": math.log10(net) if net and net > 0 else None})
    return out


def quantile(xs: list[float], q: float) -> float:
    s = sorted(xs)
    pos = q * (len(s) - 1)
    lo = int(pos)
    return s[lo] + (s[min(lo + 1, len(s) - 1)] - s[lo]) * (pos - lo)


def distributions() -> None:
    lines = line_features()
    rows = []
    for f in FEATURES:
        xs = [r[f] for r in lines if r[f] is not None]
        share = f.endswith("_share")
        bad = sum(1 for x in xs if share and (x < 0 or x > 1))
        ok = [x for x in xs if not share or 0 <= x <= 1]
        rows.append((f, len(lines), len(xs), bad, *(round(quantile(ok, q), 4) if ok else None for q in (0.1, 0.25, 0.5, 0.75, 0.9))))
    write("feature_distributions", ["feature", "lines", "defined", "outside_0_to_1", "p10", "p25", "median", "p75", "p90"], rows)
    kinds = {}
    for r in lines:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    write("feature_kind_counts", ["kind", "lines"], sorted(kinds.items()))
    corr = []
    for i, a in enumerate(FEATURES):
        for b in FEATURES[i + 1:]:
            pairs = [(r[a], r[b]) for r in lines if r[a] is not None and r[b] is not None
                     and all(not k.endswith("_share") or 0 <= r[k] <= 1 for k in (a, b))]
            if len(pairs) < 3:
                continue
            n = len(pairs)
            ma, mb = sum(p[0] for p in pairs) / n, sum(p[1] for p in pairs) / n
            sa = math.sqrt(sum((p[0] - ma) ** 2 for p in pairs))
            sb = math.sqrt(sum((p[1] - mb) ** 2 for p in pairs))
            r = sum((p[0] - ma) * (p[1] - mb) for p in pairs) / (sa * sb) if sa and sb else None
            corr.append((a, b, n, round(r, 3) if r is not None else None))
    corr.sort(key=lambda x: -abs(x[3] or 0))
    write("feature_correlations", ["feature_a", "feature_b", "lines", "pearson_r"], corr)


STEPS = {"coverage": coverage, "distributions": distributions}


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
