"""Figures for version 2 of the integrity report (docs/integrity_findings_v2.md).

Loaded by src.report_pdf only when a version 2 figure marker appears, so version 1's figures are untouched.
Data: reports/integrity/years.csv, completeness_check.csv, column_quality.csv, flag_counts.csv, the v2
analysis tables in reports/integrity/v2/ (src/analyses_v2.py) and Stage 2 cross-year outputs.
Captions follow the version 2 writing rules (no semicolons, ranges written with "to", no flag codes).
"""

from __future__ import annotations

import csv
from collections import defaultdict

import duckdb

from . import config, stage1, stage2
from .report_pdf import (BLUE, GREEN, GREY, HATCH, INK, MUTED, ORANGE, PURPLE, RED, TEAL, bar_panel, esc, fiscal_years,
                         legend, line, nice_ticks, present, read_csv, rect, svg, text, y_axis, years_table)

V2 = config.INTEGRITY_REPORTS_DIR / "v2"


def v2csv(name: str) -> list[dict]:
    return list(csv.DictReader(open(V2 / f"{name}.csv", encoding="utf-8")))


# -------------------------------------------------------------------------------------------- Figure 1


def fig_rows_and_dollars_v2() -> tuple[str, str]:
    yt = years_table()
    fys = fiscal_years()
    rows = [int(yt[fy]["rows"]) / 1e6 for fy in fys]
    diag = {int(r["fiscal_year"]): float(r["diagnostic_net"]) / 1e9 for r in v2csv("figure1_diagnostic")}
    net = [float(yt[fy]["net"]) / 1e9 for fy in fys]
    body = bar_panel(0, 0, 690, 170, fys, rows, "Transaction rows (millions)", lambda t: f"{t:g}", lambda v: f"{v:.1f}", BLUE)
    # net obligations with lettered markers on the three affected years, a key, and the diagnostic line
    x0, y0, w, h, left, top, bottom = 0, 185, 690, 300, 38, 52, 18
    pw, ph = w - left - 4, h - top - bottom
    ticks = nice_ticks(0, max(net + list(diag.values())), 4)
    hi = max(ticks)
    y_of = lambda v: y0 + top + ph - v / hi * ph  # noqa: E731
    bw = pw / len(fys)
    notes = {2008: ("a", "FY2008 includes a +$13.9B entry"), 2009: ("b", "FY2009 includes its -$13.9B reversal"),
             2010: ("c", "FY2010 includes two $10B Mint rows")}
    out = [text(x0, y0 + 10, "Net obligations ($ billions, nominal)", 10.5, weight="bold"),
           legend(x0 + 250, y0 + 10, [("recorded", TEAL), ("affected year", ORANGE)]),
           f'<line x1="{x0 + 440:.1f}" y1="{y0 + 6:.1f}" x2="{x0 + 462:.1f}" y2="{y0 + 6:.1f}" stroke="{INK}" stroke-width="1.6" stroke-dasharray="3,3"/>',
           text(x0 + 466, y0 + 10, "diagnostic, known issues adjusted, not the data", 9, color=MUTED),
           y_axis(x0 + left, x0 + w, y_of, ticks, lambda t: f"{t:g}")]
    kx = x0 + left
    for fy, (letter, note) in notes.items():
        out.append(f'<circle cx="{kx + 6:.1f}" cy="{y0 + 27:.1f}" r="6" fill="{RED}"/>')
        out.append(text(kx + 6, y0 + 30, letter, 8.5, "middle", "#ffffff", "bold"))
        out.append(text(kx + 16, y0 + 30, note, 9, color=INK))
        kx += 22 + 5.2 * len(note)
    pts = []
    for i, (fy, v) in enumerate(zip(fys, net)):
        bx = x0 + left + i * bw
        colr = ORANGE if fy in notes else TEAL
        out.append(rect(bx + bw * 0.15, y_of(v), bw * 0.7, y_of(0) - y_of(v), colr, f"FY{fy}: ${v:.1f}B recorded"))
        out.append(text(bx + bw / 2, y_of(v) - 3, f"{v:.0f}", 7, "middle", MUTED))
        out.append(text(bx + bw / 2, y0 + h - 5, str(fy)[-2:], 8.5, "middle", MUTED))
        pts.append((bx + bw / 2, y_of(diag[fy])))
        if fy in notes:
            cy = y_of(max(v, diag[fy])) - 22
            out.append(f'<circle cx="{bx + bw / 2:.1f}" cy="{cy:.1f}" r="6" fill="{RED}"/>')
            out.append(text(bx + bw / 2, cy + 3, notes[fy][0], 8.5, "middle", "#ffffff", "bold"))
    out.append('<polyline points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts) +
               f'" fill="none" stroke="{INK}" stroke-width="1.6" stroke-dasharray="3,3"/>')
    for (x, y), fy in zip(pts, fys):
        if fy in notes:
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="{INK}"><title>FY{fy} diagnostic: ${diag[fy]:.1f}B</title></circle>')
    cap = ("Rows and net obligations by fiscal year. Three bars carry known issues. FY2008 includes a $13.9 billion entry "
           "that was reversed in FY2009, and the reversal lowers FY2009 by the same amount. FY2010 includes two $10 billion "
           f"US Mint rows recorded on contract vehicles. The dotted line adjusts those three years. It shows FY2008 at "
           f"${diag[2008]:.1f} billion, FY2009 at ${diag[2009]:.1f} billion and FY2010 at ${diag[2010]:.1f} billion. It is a "
           "diagnostic and is not the data. Row counts rise 73% in FY2015 while dollars barely move.")
    return svg(690, 490, body + "".join(out)), cap


def fig_monthly_net_v2() -> tuple[str, str]:
    c = duckdb.connect()
    m = c.execute(f"""SELECT month, CAST(net AS DOUBLE) / 1e9 FROM read_parquet('{stage2.CROSS / "months.parquet"}')
                      WHERE month BETWEEN '2007-10' AND '2010-09' ORDER BY month""").fetchall()
    w, h, left, top, bottom = 690, 220, 44, 22, 30
    pw, ph = w - left - 10, h - top - bottom
    vals = [v for _, v in m]
    ticks = nice_ticks(min(0, min(vals)), max(vals), 5)
    lo, hi = min(ticks), max(ticks)
    x_of = lambda i: left + (i + 0.5) * pw / len(m)  # noqa: E731
    y_of = lambda v: top + ph - (v - lo) / (hi - lo) * ph  # noqa: E731
    out = [y_axis(left, left + pw, y_of, ticks, lambda t: f"${t:g}B")]
    for k, fy in enumerate((2008, 2009, 2010)):
        if k:
            xx = x_of(k * 12) - pw / len(m) / 2
            out.append(line(xx, top, xx, top + ph, "#a0aec0", 1, "3,3"))
        out.append(text(x_of(k * 12 + 5.5), top - 6, f"FY{fy}", 10, "middle", MUTED, "bold"))
    out.append('<polyline points="' + " ".join(f"{x_of(i):.1f},{y_of(v):.1f}" for i, (_, v) in enumerate(m)) +
               f'" fill="none" stroke="{BLUE}" stroke-width="1.8"/>')
    for i, (mo, v) in enumerate(m):
        hot = mo in ("2008-09", "2009-01")
        out.append(f'<circle cx="{x_of(i):.1f}" cy="{y_of(v):.1f}" r="{3.5 if hot else 2}" fill="{RED if hot else BLUE}"/>')
        if i % 3 == 0:
            out.append(text(x_of(i), h - 14, mo, 8, "middle", MUTED))
        if mo == "2008-09":
            out.append(text(x_of(i) + 7, y_of(v) + 3, f"September 2008, ${v:.0f}B with a +$13.9B entry", 8.5, "start", RED))
        if mo == "2009-01":
            out.append(text(x_of(i) + 6, y_of(v) + 12, f"January 2009, ${v:.0f}B with its -$13.9B reversal", 8.5, "start", RED))
    cap = ("Net obligations by month, FY2008 to FY2010. One Army construction award records a $13.9 billion entry in "
           "September 2008 and reverses it in January 2009. Each of the two years is off by about $13.9 billion in opposite "
           "directions. January 2009 is the only month in 18 years below half of its year's median month in dollars.")
    return svg(w, h, "".join(out)), cap


# -------------------------------------------------------------------------------------------- findings


def fig_negative_vendors_v2() -> tuple[str, str]:
    rows = [r for r in v2csv("negative_vendor_totals") if r["variant"] == "full PSC"]
    fys = [int(r["fiscal_year"]) for r in rows]
    n = [int(r["negative_vendor_cells"]) / 1000 for r in rows]
    d = [float(r["negative_dollars"]) / 1e9 for r in rows]
    body = bar_panel(0, 0, 340, 210, fys, n, "Vendor-cells with a negative net (thousands)", lambda t: f"{t:g}",
                     lambda v: f"{v:.0f}", PURPLE)
    body += bar_panel(350, 0, 340, 210, fys, d, "Their summed net ($ billions)", lambda t: f"{t:g}", None, RED)
    cap = ("Vendor-cells with a negative net total, by fiscal year. A cell is one awarding agency, product or service code "
           "and fiscal year. A vendor is the parent UEI, or the recipient UEI where the parent is blank. FY2009 includes the "
           "$13.9 billion Emerson reversal. Nearly every negative vendor-cell holds a deobligation larger than the "
           "award's obligations that year.")
    return svg(690, 214, body), cap


def fig_small_rows_v2() -> tuple[str, str]:
    b = v2csv("amount_bands")
    fys = fiscal_years()
    small = {int(r["fiscal_year"]): int(r["rows"]) / 1e6 for r in b if r["band"] == "under $3,000"}
    big = defaultdict(float)
    for r in b:
        if r["band"] in ("$10,000 to under $250,000", "$250,000 and over"):
            big[int(r["fiscal_year"])] += int(r["rows"]) / 1e6
    share = {int(r["fiscal_year"]): float(r["share_of_net_pct"]) for r in b if r["band"] == "under $3,000"}
    w, h, left, top, bottom = 690, 230, 40, 34, 34
    pw, ph = w - left - 10, h - top - bottom
    ticks = nice_ticks(0, max(small.values()), 4)
    hi = max(ticks)
    x_of = lambda fy: left + (fys.index(fy) + 0.5) * pw / len(fys)  # noqa: E731
    y_of = lambda v: top + ph - v / hi * ph  # noqa: E731
    out = [y_axis(left, left + pw, y_of, ticks, lambda t: f"{t:g}M"),
           legend(left, 12, [("rows under $3,000", ORANGE), ("rows of $10,000 or more", BLUE)])]
    for series, colr in ((small, ORANGE), (big, BLUE)):
        out.append('<polyline points="' + " ".join(f"{x_of(fy):.1f},{y_of(series[fy]):.1f}" for fy in fys) +
                   f'" fill="none" stroke="{colr}" stroke-width="2"/>')
        for fy in fys:
            out.append(f'<circle cx="{x_of(fy):.1f}" cy="{y_of(series[fy]):.1f}" r="2.3" fill="{colr}"/>')
    for fy in fys:
        out.append(text(x_of(fy), h - 20, f"{fy % 100:02d}", 8.5, "middle", MUTED))
        out.append(text(x_of(fy), h - 6, f"{share[fy]:.2f}%", 7, "middle", ORANGE))
    out.append(text(left, h - 6, "share of net", 7, "end", ORANGE))
    cap = ("Rows under $3,000 and rows of $10,000 or more, by fiscal year, in millions. The small figures along the "
           "bottom give the share of net dollars in rows under $3,000. Rows under $3,000 jump in FY2008, FY2015 and "
           f"FY2019 and never hold more than {max(share.values()):.2f}% of net dollars. Rows of $10,000 or more stay between "
           f"{min(big.values()):.2f} million and {max(big.values()):.2f} million in every year.")
    return svg(w, h, "".join(out)), cap


def fig_coverage_v2() -> tuple[str, str]:
    cq = read_csv("column_quality.csv")
    fys = fiscal_years()
    cols = [("number_of_offers_received", "Offers received: blank", ORANGE), ("recipient_duns", "Recipient DUNS: blank", PURPLE),
            ("naics_code", "NAICS code: blank", TEAL), ("extent_competed_code", "Extent competed: blank", GREEN)]
    series = {col: {} for col, _, _ in cols}
    for r in cq:
        if r["column"] in series:
            series[r["column"]][int(r["fiscal_year"])] = float(r["pct_blank"])
    f999 = {int(r["fiscal_year"]): float(r["share_of_rows_pct"]) for r in v2csv("funding_agency_999")}
    w, h, left, top, bottom = 690, 240, 40, 36, 22
    pw, ph = w - left - 10, h - top - bottom
    x_of = lambda fy: left + (fys.index(fy) + 0.5) * pw / len(fys)  # noqa: E731
    y_of = lambda v: top + ph - v / 100 * ph  # noqa: E731
    items = [(lab, colr) for _, lab, colr in cols] + [("Funding agency code 999", RED)]
    out = [y_axis(left, left + pw, y_of, [0, 25, 50, 75, 100], lambda t: f"{t:g}%"), legend(left, 12, items[:3]),
           legend(left, 26, items[3:])]
    for data, colr in [(series[c], colr) for c, _, colr in cols] + [(f999, RED)]:
        out.append('<polyline points="' + " ".join(f"{x_of(fy):.1f},{y_of(data[fy]):.1f}" for fy in fys if fy in data) +
                   f'" fill="none" stroke="{colr}" stroke-width="2"/>')
        for fy, v in data.items():
            out.append(f'<circle cx="{x_of(fy):.1f}" cy="{y_of(v):.1f}" r="2.2" fill="{colr}"/>')
    for fy in fys:
        out.append(text(x_of(fy), h - 6, f"{fy % 100:02d}", 8.5, "middle", MUTED))
    cap = ("Share of rows with a blank value by fiscal year, and the share of rows whose funding agency is the placeholder "
           "code 999. Offers received becomes mostly blank from FY2018. DUNS disappears in FY2022 and FY2023 as the UEI "
           "replaces it. The early years carry placeholder funding agencies and missing NAICS and competition codes.")
    return svg(w, h, "".join(out)), cap


def fig_flags_by_year_v2() -> tuple[str, str]:
    fc = read_csv("flag_counts.csv")
    fys = fiscal_years()
    panels = [("C08", "Reported before the action date"), ("C06", "Performance period starts after it ends"),
              ("G03", "Code and label disagree on presence"), ("X02", "Zero offers on a competed action"),
              ("J03", "Deobligation larger than that year's obligations"), ("E01", "Placeholder vendor")]
    by = defaultdict(dict)
    for r in fc:
        if r["count"] not in ("", None):
            by[r["flag_id"]][int(r["fiscal_year"])] = int(r["count"])
    out = []
    for k, (fid, title) in enumerate(panels):
        x0, y0 = (k % 2) * 350, (k // 2) * 150
        out.append(bar_panel(x0, y0, 340, 140, fys, [by[fid].get(fy, 0) / 1000 for fy in fys], title,
                             lambda t: f"{t:g}k", None, PURPLE))
    cap = ("Rows flagged per fiscal year, in thousands, for six checks. Code and label mismatches and zero offers on "
           "competed actions are concentrated in FY2008 to FY2010. Performance periods that start after they end stop "
           "around FY2020. Reports filed before the action date grow with row counts.")
    return svg(690, 450, "".join(out)), cap


# -------------------------------------------------------------------------------------------- completeness


def fig_benchmarks_v2() -> tuple[str, str]:
    rows = [r for r in read_csv("completeness_check.csv") if not r["agency"] and r["status"] not in ("PENDING", "NOT COMPARED")]
    fys = sorted({int(r["fiscal_year"]) for r in rows})
    gao = {int(r["fiscal_year"]): float(r["gap_pct"]) for r in rows if r["role"] == "primary" and r["benchmark_type"] != "bound"}
    gsa = {int(r["fiscal_year"]): float(r["gap_pct"]) for r in rows if r["role"] == "context"}
    bnd = {int(r["fiscal_year"]): float(r["gap_pct"]) for r in rows if r["benchmark_type"] == "bound"}
    w, h, left, top, bottom = 690, 240, 44, 30, 22
    pw, ph = w - left - 10, h - top - bottom
    lim = 3.0
    y_of = lambda v: top + ph / 2 - v / lim * (ph / 2)  # noqa: E731
    out = [rect(left, y_of(2), pw, y_of(-2) - y_of(2), "#c6f6d5", opacity=0.6),
           text(left + pw - 4, y_of(2) + 11, "PASS zone, within 2%", 9, "end", GREEN),
           y_axis(left, left + pw, y_of, nice_ticks(-lim, lim, 6), lambda t: f"{t:+g}%" if t else "0%"),
           legend(left, 12, [("GAO, primary", BLUE), ("GSA, context only", "#f6c99b")]),
           f'<path d="M {left + 290} 12 l 5 -9 l 5 9 z" fill="{GREEN}"/>', text(left + 304, 12, "GAO lower bound (ours above it)", 9.5, color=MUTED)]
    gw = pw / len(fys)
    for i, fy in enumerate(fys):
        gx = left + i * gw
        for j, (data, colr) in enumerate(((gao, BLUE), (gsa, "#f6c99b"))):
            if fy not in data:
                continue
            v = data[fy]
            bx = gx + gw * 0.18 + j * gw * 0.32
            out.append(rect(bx, min(y_of(v), y_of(0)), gw * 0.3, abs(y_of(0) - y_of(v)), colr, f"FY{fy}: {v:+.2f}%"))
            out.append(text(bx + gw * 0.15, y_of(v) - 3 if v >= 0 else y_of(v) + 10, f"{v:+.2f}", 7.5, "middle", MUTED))
        if fy in bnd:
            cx, cy = gx + gw * 0.33, y_of(min(bnd[fy], lim - 0.2))
            out.append(f'<path d="M {cx - 6:.1f} {cy + 5:.1f} l 6 -11 l 6 11 z" fill="{GREEN}"><title>FY{fy}: ours is {bnd[fy]:.2f}% above GAO\'s lower bound</title></path>')
            out.append(text(cx, cy - 9, f"+{bnd[fy]:.2f}", 7.5, "middle", GREEN))
        out.append(text(gx + gw / 2, h - 6, f"FY{fy}", 9, "middle", MUTED))
    cap = ("Gap between our net total and each published figure, as a percentage of that figure. Positive means ours is "
           "higher. GAO is the primary benchmark and GSA is context only. FY2018 to FY2020 have GAO lower bounds, shown as "
           "triangles, and our total sits above each one. FY2021 uses GAO's approximate figure of about $637 billion. The "
           "four exact GAO figures, FY2022 to FY2025, match within 0.2%.")
    return svg(w, h, "".join(out)), cap


def fig_months_heatmap_v2() -> tuple[str, str]:
    from .report_pdf import fig_months_heatmap
    body, _ = fig_months_heatmap()
    cap = ("Rows per month, in thousands, shaded relative to each year's busiest month. Every month of every year has "
           "data. September is the usual year-end peak. A red outline marks a month below half of its year's median, by "
           "rows or dollars.")
    return body, cap


# -------------------------------------------------------------------------------------------- parent tests


PARENT_CAPTIONS = {
    "raytheon_2020": ("Raytheon Company units by month and the parent ID on their rows. The merger closed on April 3, "
                      "2020. The new parent ID takes over in June 2020, two months later. Two rows carry it before the "
                      "closing, the first on March 16, 2020."),
    "saic_2013": ("Spun-off SAIC units by month and the parent ID on their rows. The split closed on September 27, 2013. "
                  "The new SAIC parent ID takes over in March 2014, six months later. Between 50 and 300 rows a month keep "
                  "the old ID into 2015. Five rows carry the new ID before the split, all on September 26, 2013."),
    "sikorsky_2015": ("Sikorsky units by month and the parent ID on their rows. Lockheed Martin closed the purchase on "
                      "November 6, 2015. The Lockheed Martin parent ID takes over in February 2016, three months later. No "
                      "row carries it before the purchase."),
    "l3harris_2019": ("L3 units by month and the parent ID on their rows. The merger closed on June 29, 2019. The L3Harris "
                      "parent ID takes over in August 2019, two months later. 25 rows carry it before the merger, 20 of "
                      "them more than 30 days early."),
}
PARENT_LABELS = {
    "raytheon_2020": ("Raytheon Company (KLW3ZYL15493)", "RTX (PPLZG8J3N9D4)", "Closed April 3, 2020"),
    "saic_2013": ("old SAIC, now Leidos (ZL41ERXMPAR3)", "new SAIC (RE7WMNV9L719)", "Closed September 27, 2013"),
    "sikorsky_2015": ("United Technologies (PPLZG8J3N9D4)", "Lockheed Martin (ZFN2JJXBLZT3)", "Closed November 6, 2015"),
    "l3harris_2019": ("L3 Technologies (XXP4PLFFFGK9)", "Harris, now L3Harris (SJULQDJ8NZU7)", "Closed June 29, 2019"),
}


def parent_figure(name: str):
    def fig() -> tuple[str, str]:
        from .analyses_v2 import PARENT_TESTS
        t = PARENT_TESTS[name]
        rows = [(r["month"], int(r["before_id_rows"]), int(r["after_id_rows"]), int(r["other_or_blank_rows"]))
                for r in v2csv(f"parent_test_{name}_by_month")]
        before, after, closed = PARENT_LABELS[name]
        w, h, left, top, bottom = 690, 230, 50, 42, 30
        pw, ph = w - left - 10, h - top - bottom
        ticks = nice_ticks(0, max(a + b + o for _, a, b, o in rows), 4)
        hi = max(ticks)
        y_of = lambda v: top + ph - v / hi * ph  # noqa: E731
        bw = pw / len(rows)
        out = [y_axis(left, left + pw, y_of, ticks, lambda t: f"{t:,.0f}"),
               legend(left, 12, [(f"Old parent, {before}", ORANGE), (f"New parent, {after}", BLUE)]),
               legend(left, 26, [("Other or blank", GREY)])]
        for i, (m, b, a, o) in enumerate(rows):
            x, base = left + i * bw + bw * 0.12, y_of(0)
            for v, colr in ((b, ORANGE), (a, BLUE), (o, GREY)):
                if v:
                    hgt = y_of(0) - y_of(v)
                    out.append(rect(x, base - hgt, bw * 0.76, hgt, colr, f"{m}: {v:,} rows"))
                    base -= hgt
            if i % 3 == 0:
                out.append(text(left + i * bw + bw / 2, h - 14, m, 8, "middle", MUTED))
            if m == t["event_month"]:
                xm = left + i * bw
                out.append(line(xm, top - 6, xm, top + ph, RED, 1.2, "4,3"))
                out.append(text(xm + 4, top + 4, closed, 9, "start", RED))
        return svg(w, h, "".join(out)), PARENT_CAPTIONS[name]
    return fig


V2_FIGURES = {"rows_and_dollars_v2": fig_rows_and_dollars_v2, "monthly_net_v2": fig_monthly_net_v2,
              "negative_vendors_v2": fig_negative_vendors_v2, "small_rows_v2": fig_small_rows_v2,
              "coverage_v2": fig_coverage_v2, "flags_by_year_v2": fig_flags_by_year_v2, "benchmarks_v2": fig_benchmarks_v2,
              "months_heatmap_v2": fig_months_heatmap_v2,
              **{f"parent_{n.split('_')[0]}_v2": parent_figure(n) for n in PARENT_CAPTIONS}}
