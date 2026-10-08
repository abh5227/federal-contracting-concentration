"""Preliminary concentration figures for FY2024 and FY2025, for the project proposal (docs/proposal/proposal_v1.md).

    python -m src.concentration_prelim

Each rule is written in RULES below before the analysis runs, and the proposal's checklist quotes them. The cell,
the vendor and HHI follow src/analyses_v2.py exactly (its VENDOR expression and hhi() are imported, not copied).
Nothing here cleans, drops or changes data, and none of the team decisions in config/decisions.csv is applied:
every number is a sum over the Stage 1 mirror (Layer A, text as published). The figures are preliminary.
Outputs are small summaries in reports/proposal/ (committed), one CSV per table plus prelim_headline.json.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from decimal import Decimal

from . import config
from .analyses_v2 import AMT, VENDOR, con, d, files, hhi

OUT = config.REPORTS_DIR / "proposal"
YEARS = (2024, 2025)          # the two years with none of the known large-record issues
THRESHOLDS = (1800, 2500)     # 2023 Merger Guidelines (above 1,800 is highly concentrated) and 2010 Horizontal Merger Guidelines (above 2,500)
BANDS = [("1,500 or less", None, 1500), ("above 1,500 to 1,800", 1500, 1800), ("above 1,800 to 2,500", 1800, 2500),
         ("above 2,500, two or more vendors", 2500, None), ("10,000, one vendor", None, None)]

RULES = {
    "cell": "As in src/analyses_v2.py. The awarding agency code as recorded x product or service code x fiscal year. "
            "A blank product code is its own value.",
    "vendor": "As in src/analyses_v2.py. recipient_parent_uei, or recipient_uei when the parent is blank. Rows with both "
              "blank form one vendor, '(no ID)'.",
    "vendor_net": "The sum of federal_action_obligation over a vendor's rows in the cell.",
    "hhi": "As hhi() in src/analyses_v2.py. 10,000 x the sum of squared shares, where a share is a vendor's net divided by "
           "the summed net of vendors with a positive net in the cell. Vendors with a net of zero or less get no share. "
           "A cell with no vendor of positive net has no HHI and is counted separately.",
    "top4": "The sum of the four largest shares under the same rule, in percent. A cell with fewer than four vendors of "
            "positive net sums the shares it has, so it scores 100%.",
    "vendors_per_cell": "Reported two ways for cells with an HHI. Vendors with a positive net (the vendors HHI counts), "
                        "and every vendor with at least one row in the cell. The median is the middle value over cells "
                        "(the mean of the two middle values for an even count).",
    "year_net": "The sum of federal_action_obligation over every row of the fiscal year.",
    "share_above_threshold": "The summed net of cells whose HHI is strictly above the threshold, divided by the year's net, "
                             "in percent. Thresholds are 1,800 (2023 Merger Guidelines, highly concentrated) and 2,500 "
                             "(2010 Horizontal Merger Guidelines, highly concentrated).",
    "weighted_median": "Dollar-weighted median of HHI (and of top-4 share). Cells with an HHI and a cell net above zero, "
                       "weighted by the cell net, sorted by the measure. The value at the first cell where the running "
                       "weight reaches half the total weight.",
    "single_vendor": "Reported two ways. Cells where every row carries the same vendor, and cells where exactly one vendor "
                     "has a positive net, so HHI is 10,000.",
    "bands": "Cells and their summed net by HHI band: " + "; ".join(b for b, _, _ in BANDS) + ". Each band includes its "
             "upper bound. The last band holds the cells with exactly one vendor of positive net, and only those.",
    "largest_cells": "The 20 cells with the largest net in either year, with each year's net, HHI, top-4 share, vendors "
                     "with a positive net and the largest vendor's share. Labels are the most common agency name and "
                     "product code description on the cell's rows across both years. Vendors are not named.",
    "not_applied": "None of the team decisions in config/decisions.csv is applied. MISCELLANEOUS FOREIGN AWARDEES counts "
                   "as one vendor, negative vendors stay in the cell's net, parent IDs are as recorded, and product codes "
                   "are used as recorded.",
}


def write(name: str, rows: list[dict]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows([{k: (str(v) if isinstance(v, Decimal) else v) for k, v in r.items()} for r in rows])


def median(xs: list) -> Decimal:
    s = sorted(xs)
    n = len(s)
    return Decimal(s[n // 2]) if n % 2 else (Decimal(s[n // 2 - 1]) + Decimal(s[n // 2])) / 2


def weighted_median(pairs: list[tuple[Decimal, Decimal]]) -> Decimal:
    """pairs of (value, weight > 0): the value at the first point where the running weight reaches half the total."""
    pairs = sorted(pairs, key=lambda p: p[0])
    half, run = sum(w for _, w in pairs) / 2, Decimal(0)
    for v, w in pairs:
        run += w
        if run >= half:
            return v
    raise ValueError("no weight")


def year_summary(fy: int) -> tuple[dict, list[dict], dict]:
    c = con()
    year_net = d(c.execute(f"SELECT SUM({AMT}) FROM read_parquet({files(fy)!r})").fetchone()[0])
    rows = c.execute(f"""SELECT awarding_agency_code AS ag, product_or_service_code AS psc, {VENDOR} AS v, SUM({AMT}) AS net
                         FROM read_parquet({files(fy)!r}) GROUP BY ALL""").fetchall()
    cells: dict[tuple, list[Decimal]] = defaultdict(list)
    for ag, psc, _, net in rows:
        cells[(ag, psc)].append(d(net))
    per_cell = {}                                   # cell -> (net, hhi, top4, positive vendors, largest share), for largest_cells
    for k, nets in cells.items():
        pos = sorted((n for n in nets if n > 0), reverse=True)
        per_cell[k] = (sum(nets), hhi(nets) if pos else None, sum(pos[:4]) * 100 / sum(pos) if pos else None, len(pos),
                       pos[0] * 100 / sum(pos) if pos else None)
    out = {"fiscal_year": fy, "year_net": year_net.quantize(Decimal("0.01")), "cells": len(cells), "vendor_cells": len(rows)}
    scored = []                                     # (hhi, top4, cell net, positive vendors, all vendors)
    for nets in cells.values():
        pos = sorted((n for n in nets if n > 0), reverse=True)
        if not pos:
            continue
        tot = sum(pos)
        scored.append((hhi(nets), sum(pos[:4]) * 100 / tot, sum(nets), len(pos), len(nets)))
    out["cells_with_hhi"] = len(scored)
    out["cells_without_positive_vendor"] = len(cells) - len(scored)
    out["median_positive_vendors_per_cell"] = median([s[3] for s in scored])
    out["median_all_vendors_per_cell"] = median([s[4] for s in scored])
    for t in THRESHOLDS:
        sel = [s for s in scored if s[0] > t]
        out[f"cells_hhi_above_{t}"] = len(sel)
        out[f"share_of_year_net_in_cells_above_{t}_pct"] = (sum(s[2] for s in sel) * 100 / year_net).quantize(Decimal("0.01"))
    w = [s for s in scored if s[2] > 0]
    out["cells_in_weighted_median"] = len(w)
    out["dollar_weighted_median_hhi"] = weighted_median([(s[0], s[2]) for s in w]).quantize(Decimal("0.1"))
    out["dollar_weighted_median_top4_pct"] = weighted_median([(s[1], s[2]) for s in w]).quantize(Decimal("0.1"))
    out["cells_one_vendor_on_all_rows"] = sum(1 for nets in cells.values() if len(nets) == 1)
    out["cells_one_positive_vendor_hhi_10000"] = sum(1 for s in scored if s[3] == 1)
    out["net_in_cells_one_positive_vendor_pct"] = (sum(s[2] for s in scored if s[3] == 1) * 100 / year_net).quantize(Decimal("0.01"))
    bands = []
    for name, lo, hi in BANDS:
        if lo is None and hi is None:
            sel = [s for s in scored if s[3] == 1]
        else:
            sel = [s for s in scored if s[3] > 1 and (lo is None or s[0] > lo) and (hi is None or s[0] <= hi)]
        bands.append({"fiscal_year": fy, "hhi_band": name, "cells": len(sel), "net": sum(s[2] for s in sel).quantize(Decimal("0.01")),
                      "share_of_year_net_pct": (sum(s[2] for s in sel) * 100 / year_net).quantize(Decimal("0.01"))})
    return out, bands, per_cell


def labels() -> dict[tuple, tuple[str, str]]:
    c = con()
    parts = " UNION ALL ".join(f"SELECT awarding_agency_code AS ag, product_or_service_code AS psc, awarding_agency_name AS agn, "
                               f"product_or_service_code_description AS pscd FROM read_parquet({files(fy)!r})" for fy in YEARS)
    return {(ag, psc): (agn, pscd) for ag, psc, agn, pscd in
            c.execute(f"SELECT ag, psc, mode(agn), mode(pscd) FROM ({parts}) GROUP BY ag, psc").fetchall()}


def largest_cells(per_year: dict[int, dict]) -> list[dict]:
    keys = set().union(*per_year.values())
    top = sorted(keys, key=lambda k: -max(per_year[fy].get(k, (Decimal(0),))[0] for fy in YEARS))[:20]
    lab, out = labels(), []
    q = lambda x, e: x.quantize(Decimal(e)) if x is not None else ""
    for k in top:
        r = {"agency_code": k[0], "agency": lab[k][0], "psc": k[1], "psc_description": lab[k][1]}
        for fy in YEARS:
            net, h, t4, npos, big = per_year[fy].get(k, (Decimal(0), None, None, 0, None))
            r |= {f"net_fy{fy}": q(net, "0.01"), f"hhi_fy{fy}": q(h, "0.1"), f"top4_pct_fy{fy}": q(t4, "0.1"),
                  f"positive_vendors_fy{fy}": npos, f"largest_vendor_share_pct_fy{fy}": q(big, "0.1")}
        out.append(r)
    return out


def main(argv: list[str] | None = None) -> int:
    summary, bands, per_year = [], [], {}
    for fy in YEARS:
        s, b, per_year[fy] = year_summary(fy)
        summary.append(s)
        bands += b
        print(f"concentration_prelim: FY{fy} done", flush=True)
    write("concentration_prelim_by_year", summary)
    write("concentration_prelim_hhi_bands", bands)
    write("concentration_prelim_largest_cells", largest_cells(per_year))
    (OUT / "prelim_headline.json").write_text(json.dumps({"rules": RULES, "by_year": summary}, indent=1, default=str),
                                              encoding="utf-8")
    print(f"concentration_prelim -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
