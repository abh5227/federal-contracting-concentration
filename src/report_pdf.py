"""reports/integrity/integrity_report.pdf: the integrity and completeness findings as a PDF, with charts.

    python -m src.report_pdf                                     # version 1 (the default, unchanged)
    python -m src.report_pdf --in docs/integrity_findings_v2.md --out reports/integrity/integrity_report_v2.pdf
    python -m src.report_pdf --plain --in docs/proposal/proposal_v1.md --out reports/proposal/proposal_v1.pdf

--plain is for submission documents such as the proposal: no "Generated" subtitle under the title, a footer
that holds only the page number, and a compact page (0.6 inch margins, 10 pt body text at 1.35 line spacing,
smaller headings, and entries under a "References" heading at 9 pt) so a page-limited document fits. Without it,
every document builds exactly as before.

By default the narrative is docs/integrity_findings.md, so the PDF and the doc never disagree. Each
`<!-- figure: NAME -->` line in it is replaced by a chart drawn from the committed reports
(reports/integrity/*.csv) and Stage 2 outputs (data/integrity/). The charts are plain SVG written
here (no plotting library), and headless Chrome prints the page to PDF. Nothing in Stage 0, 1 or 2
is written; the only outputs are the PDF and its HTML source in data/scratch/report_pdf/.
"""

from __future__ import annotations

import csv
import html
import math
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from . import config, stage1, stage2

SRC_MD = config.DOCS_DIR / "integrity_findings.md"
REP = config.INTEGRITY_REPORTS_DIR
OUT_PDF = REP / "integrity_report.pdf"
WORK = config.SCRATCH_DIR / "report_pdf"
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

BLUE, ORANGE, GREEN, PURPLE, RED, GREY, TEAL = "#2b6cb0", "#dd6b20", "#2f855a", "#6b46c1", "#c53030", "#a0aec0", "#319795"
INK, MUTED, GRID = "#1a202c", "#4a5568", "#e2e8f0"


# ============================================================================================ data


def read_csv(name: str) -> list[dict]:
    return list(csv.DictReader(open(REP / name, encoding="utf-8")))


def fiscal_years() -> list[int]:
    return list(range(config.FIRST_FY, config.LAST_FY + 1))


def years_table() -> dict[int, dict]:
    return {int(r["fiscal_year"]): r for r in read_csv("years.csv")}


def present(yt: dict[int, dict]) -> list[int]:
    return [fy for fy in fiscal_years() if yt.get(fy, {}).get("status") == "present"]


# ============================================================================================ SVG helpers


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def nice_ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    if hi <= lo:
        hi = lo + 1
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    first, last = math.floor(lo / step + 1e-9), math.ceil(hi / step - 1e-9)
    return [round(k * step, 10) for k in range(first, last + 1)]


def svg(w: int, h: int, body: str) -> str:
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" xmlns="http://www.w3.org/2000/svg" '
            f'font-family="Helvetica, Arial, sans-serif" font-size="10" fill="{INK}">{body}</svg>')


def text(x, y, s, size=10, anchor="start", color=INK, weight="normal", rotate=None) -> str:
    rot = f' transform="rotate({rotate} {x:.1f} {y:.1f})"' if rotate else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" fill="{color}" '
            f'font-weight="{weight}"{rot}>{esc(s)}</text>')


def line(x1, y1, x2, y2, color=GRID, width=1, dash=None) -> str:
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{width}"{d}/>'


def rect(x, y, w, h, fill, title=None, stroke=None, opacity=None) -> str:
    st = f' stroke="{stroke}" stroke-width="1.5"' if stroke else ""
    op = f' fill-opacity="{opacity}"' if opacity is not None else ""
    t = f"<title>{esc(title)}</title>" if title else ""
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w, 0):.1f}" height="{max(h, 0):.1f}" fill="{fill}"{st}{op}>{t}</rect>'


def legend(x, y, items: list[tuple[str, str]], gap=16) -> str:
    out, cx = [], x
    for label, color in items:
        out.append(rect(cx, y - 8, 10, 10, color))
        out.append(text(cx + 14, y, label, 9.5, color=MUTED))
        cx += 14 + 5.6 * len(label) + gap
    return "".join(out)


def y_axis(x0, x1, y_of, ticks, fmt) -> str:
    out = []
    for t in ticks:
        y = y_of(t)
        out.append(line(x0, y, x1, y, GRID if t else "#a0aec0"))
        out.append(text(x0 - 4, y + 3, fmt(t), 9, "end", MUTED))
    return "".join(out)


def bar_panel(x0, y0, w, h, labels, values, title, fmt_tick, fmt_val=None, color=BLUE, pending=(), highlight=None,
              ymax=None) -> str:
    """One bar chart inside (x0, y0, w, h): title on top, y axis on the left, one bar per label."""
    left, top, bottom = 38, 18, 18
    pw, ph = w - left - 4, h - top - bottom
    vmax = ymax if ymax is not None else max([v for v in values if v is not None] + [0])
    vmin = min([v for v in values if v is not None] + [0])
    ticks = nice_ticks(vmin, vmax, 4)
    lo, hi = min(ticks), max(ticks)
    y_of = lambda v: y0 + top + ph - (v - lo) / (hi - lo) * ph  # noqa: E731
    out = [text(x0, y0 + 10, title, 10.5, weight="bold"), y_axis(x0 + left, x0 + w, y_of, ticks, fmt_tick)]
    bw = pw / len(labels)
    for i, (lab, v) in enumerate(zip(labels, values)):
        bx = x0 + left + i * bw
        if lab in pending or v is None:
            out.append(rect(bx + bw * 0.15, y0 + top, bw * 0.7, ph, "url(#hatch)", "pending - not yet downloaded"))
        else:
            c = (highlight or {}).get(lab, color)
            y_top, y_base = y_of(max(v, 0)), y_of(min(v, 0))
            out.append(rect(bx + bw * 0.15, y_top, bw * 0.7, y_base - y_top, c, f"{lab}: {fmt_val(v) if fmt_val else v}"))
            if fmt_val:
                out.append(text(bx + bw / 2, y_top - 2, fmt_val(v), 7, "middle", MUTED))
        out.append(text(bx + bw / 2, y0 + h - 5, str(lab)[-2:], 8.5, "middle", MUTED))
    return "".join(out)


HATCH = ('<defs><pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
         f'<rect width="6" height="6" fill="#f7fafc"/><line x1="0" y1="0" x2="0" y2="6" stroke="{GREY}" stroke-width="2"/>'
         '</pattern></defs>')


# ============================================================================================ figures


def fig_rows_and_dollars() -> tuple[str, str]:
    yt = years_table()
    fys = fiscal_years()
    pend = [fy for fy in fys if yt.get(fy, {}).get("status") != "present"]
    rows = [int(yt[fy]["rows"]) / 1e6 if fy not in pend else None for fy in fys]
    net = [float(yt[fy]["net"]) / 1e9 if fy not in pend else None for fy in fys]
    body = HATCH + bar_panel(0, 0, 340, 210, fys, rows, "Transaction rows (millions)", lambda t: f"{t:g}",
                             lambda v: f"{v:.1f}", BLUE, pend)
    body += bar_panel(350, 0, 340, 210, fys, net, "Net obligations ($ billions, nominal)", lambda t: f"{t:g}",
                      lambda v: f"{v:.0f}", TEAL, pend)
    cap = ("Rows and net obligations by fiscal year (FY2008-FY2025), from the Stage 1 proof. "
           + ("Hatched: pending, not yet downloaded. " if pend else "")
           + ("Row counts jump 73% in FY2015 (small Defense Logistics Agency orders) while dollars barely move."
              if not pend else "Row counts nearly double between FY2014 and FY2016 while dollars change far less."))
    return svg(690, 214, body), cap


def fig_benchmarks() -> tuple[str, str]:
    rows = [r for r in read_csv("completeness_check.csv")
            if not r["agency"] and r["independence"].startswith("independent") and r.get("benchmark_type", "figure") == "figure"
            and r["status"] in ("PASS", "WARN", "FAIL")]
    fys = sorted({int(r["fiscal_year"]) for r in rows})
    src = {"GAO": BLUE, "GSA": ORANGE}
    gaps = {(int(r["fiscal_year"]), r["benchmark_id"].split("-")[0]): float(r["gap_pct"]) for r in rows}
    w, h, left, top, bottom = 690, 230, 44, 26, 22
    pw, ph = w - left - 10, h - top - bottom
    lim = max(3.0, math.ceil(max(abs(v) for v in gaps.values()) + 0.5))
    y_of = lambda v: top + ph / 2 - v / lim * (ph / 2)  # noqa: E731
    out = [rect(left, y_of(2), pw, y_of(-2) - y_of(2), "#c6f6d5", opacity=0.6),
           text(left + pw - 4, y_of(2) + 11, "PASS zone: within ±2%", 9, "end", GREEN),
           y_axis(left, left + pw, y_of, nice_ticks(-lim, lim, 6), lambda t: f"{t:+g}%" if t else "0%"),
           legend(left, 12, [("GAO (government-wide obligations)", BLUE), ("GSA Small Business Act report", ORANGE)])]
    gw = pw / len(fys)
    for i, fy in enumerate(fys):
        gx = left + i * gw
        for j, s in enumerate(("GAO", "GSA")):
            if (fy, s) not in gaps:
                continue
            v = gaps[(fy, s)]
            bx = gx + gw * 0.18 + j * gw * 0.32
            yv, y0 = y_of(v), y_of(0)
            out.append(rect(bx, min(yv, y0), gw * 0.3, abs(y0 - yv), src[s], f"FY{fy} {s}: {v:+.2f}%"))
            out.append(text(bx + gw * 0.15, yv - 3 if v >= 0 else yv + 10, f"{v:+.2f}", 7.5, "middle", MUTED))
        out.append(text(gx + gw / 2, h - 6, f"FY{fy}", 9, "middle", MUTED))
    cap = ("Gap between our net total and each published figure, as a percentage of the published figure "
           "(positive: ours is higher). Thresholds were fixed before comparing: PASS within 2%, WARN within 10%, "
           "FAIL beyond. GAO's figures are matched within 0.2%; GSA's run increasingly above ours from FY2022.")
    return svg(w, h, "".join(out)), cap


def fig_monthly_net() -> tuple[str, str]:
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
        i0 = k * 12
        if k:
            out.append(line(x_of(i0) - pw / len(m) / 2, top, x_of(i0) - pw / len(m) / 2, top + ph, "#a0aec0", 1, "3,3"))
        out.append(text(x_of(i0 + 5.5), top - 6, f"FY{fy}", 10, "middle", MUTED, "bold"))
    pts = " ".join(f"{x_of(i):.1f},{y_of(v):.1f}" for i, (_, v) in enumerate(m))
    out.append(f'<polyline points="{pts}" fill="none" stroke="{BLUE}" stroke-width="1.8"/>')
    for i, (mo, v) in enumerate(m):
        hot = mo in ("2008-09", "2009-01")
        out.append(f'<circle cx="{x_of(i):.1f}" cy="{y_of(v):.1f}" r="{3.5 if hot else 2}" fill="{RED if hot else BLUE}">'
                   f"<title>{esc(mo)}: ${v:.1f}B</title></circle>")
        if i % 3 == 0:
            out.append(text(x_of(i), h - 14, mo, 8, "middle", MUTED))
        if mo == "2008-09":
            out.append(text(x_of(i) + 7, y_of(v) + 3, f"Sep 2008: ${v:.0f}B, incl. a +$13.9B entry", 8.5, "start", RED))
        if mo == "2009-01":
            out.append(text(x_of(i) + 6, y_of(v) + 12, f"Jan 2009: ${v:.0f}B, incl. its -$13.9B reversal", 8.5, "start", RED))
    cap = ("Net obligations by month, FY2008-FY2010. One Army construction award records +$13.9 billion in "
           "September 2008 (FY2008) and reverses it in January 2009 (FY2009), so each year's net total is off by "
           "about $13.9 billion in opposite directions. January 2009 is the only month in 18 years flagged as thin (H02).")
    return svg(w, h, "".join(out)), cap


def fig_coverage() -> tuple[str, str]:
    cq = read_csv("column_quality.csv")
    yt = years_table()
    fys = present(yt)
    cols = [("number_of_offers_received", "Offers received: blank", ORANGE),
            ("recipient_duns", "Recipient DUNS: blank", PURPLE),
            ("naics_code", "NAICS code: blank", TEAL),
            ("extent_competed_code", "Extent competed: blank", GREEN)]
    series = {col: {} for col, _, _ in cols}
    for r in cq:
        if r["column"] in series:
            series[r["column"]][int(r["fiscal_year"])] = float(r["pct_blank"])
    # funding agency recorded as the placeholder code 999 (with no name): counted exactly from Stage 1
    con = duckdb.connect()
    f999 = {}
    for fy in fys:
        files = stage1.layer_a_files(fy)
        n, k = con.execute(f"SELECT COUNT(*), COUNT(*) FILTER (WHERE funding_agency_code = '999') "
                           f"FROM read_parquet({[str(p) for p in files]!r})").fetchone()
        f999[fy] = 100 * k / n if n else 0
    allfy = fiscal_years()
    w, h, left, top, bottom = 690, 240, 40, 36, 22
    pw, ph = w - left - 10, h - top - bottom
    x_of = lambda fy: left + (allfy.index(fy) + 0.5) * pw / len(allfy)  # noqa: E731
    y_of = lambda v: top + ph - v / 100 * ph  # noqa: E731
    out = [y_axis(left, left + pw, y_of, [0, 25, 50, 75, 100], lambda t: f"{t:g}%")]
    items = [(lab, colr) for _, lab, colr in cols] + [("Funding agency = code 999", RED)]
    out.append(legend(left, 12, items[:3]))
    out.append(legend(left, 26, items[3:]))
    for data, colr in [(series[c], colr) for c, _, colr in cols] + [(f999, RED)]:
        segs, cur = [], []
        for fy in allfy:
            if fy in data:
                cur.append(f"{x_of(fy):.1f},{y_of(data[fy]):.1f}")
            elif cur:
                segs.append(cur)
                cur = []
        if cur:
            segs.append(cur)
        for sgm in segs:
            out.append(f'<polyline points="{" ".join(sgm)}" fill="none" stroke="{colr}" stroke-width="2"/>')
        for fy, v in data.items():
            out.append(f'<circle cx="{x_of(fy):.1f}" cy="{y_of(v):.1f}" r="2.2" fill="{colr}"><title>FY{fy}: {v:.1f}%</title></circle>')
    for fy in allfy:
        out.append(text(x_of(fy), h - 6, f"{fy % 100:02d}", 8.5, "middle", MUTED if fy in fys else GREY))
    cap = ("Share of rows with a blank value (or, for the funding agency, the placeholder code 999) by fiscal year. "
           "Offers received becomes mostly blank from FY2018; DUNS disappears as UEI replaces it in FY2022-FY2023; "
           "the early years carry placeholder funding agencies and missing NAICS and competition codes.")
    return svg(w, h, "".join(out)), cap


def fig_flags_by_year() -> tuple[str, str]:
    fc = read_csv("flag_counts.csv")
    yt = years_table()
    fys = fiscal_years()
    pend = [fy for fy in fys if yt.get(fy, {}).get("status") != "present"]
    panels = [("C08", "C08 Reported before the action date"), ("C06", "C06 Performance period starts after it ends"),
              ("G03", "G03 Code and label disagree on presence"), ("X02", "X02 Zero offers on a competed action"),
              ("J03", "J03 Deobligation larger than that year's obligations"), ("E01", "E01 Placeholder vendor")]
    by = defaultdict(dict)
    for r in fc:
        if r["count"] not in ("", None):
            by[r["flag_id"]][int(r["fiscal_year"])] = int(r["count"])
    out = [HATCH]
    for k, (fid, title) in enumerate(panels):
        x0, y0 = (k % 2) * 350, (k // 2) * 150
        vals = [by[fid].get(fy, 0) / 1000 if fy not in pend else None for fy in fys]
        out.append(bar_panel(x0, y0, 340, 140, fys, vals, title, lambda t: f"{t:g}k", None, PURPLE, pend))
    cap = ("Rows flagged per fiscal year (thousands) for six review flags. Several fall away after a reporting change: "
           "G03 and X02 are concentrated in FY2008-FY2010, C06 ends around FY2020; C08 grows with row counts.")
    return svg(690, 450, "".join(out)), cap


def fig_parent_switch() -> tuple[str, str]:
    p = stage2.CROSS / "parent_test_raytheon_by_month.parquet"
    c = duckdb.connect()
    rows = c.execute(f"""SELECT month,
            SUM(rows) FILTER (WHERE recipient_parent_uei = 'KLW3ZYL15493'),
            SUM(rows) FILTER (WHERE recipient_parent_uei = 'PPLZG8J3N9D4'),
            SUM(rows) FILTER (WHERE recipient_parent_uei NOT IN ('KLW3ZYL15493', 'PPLZG8J3N9D4'))
            FROM read_parquet('{p}') WHERE month BETWEEN '2019-10' AND '2021-09' GROUP BY 1 ORDER BY 1""").fetchall()
    rows = [(m, a or 0, b or 0, o or 0) for m, a, b, o in rows]
    w, h, left, top, bottom = 690, 230, 44, 40, 30
    pw, ph = w - left - 10, h - top - bottom
    ticks = nice_ticks(0, max(a + b + o for _, a, b, o in rows), 4)
    hi = max(ticks)
    y_of = lambda v: top + ph - v / hi * ph  # noqa: E731
    bw = pw / len(rows)
    out = [y_axis(left, left + pw, y_of, ticks, lambda t: f"{t:,.0f}"),
           legend(left, 12, [("Old parent: Raytheon Company (UEI KLW3ZYL15493)", ORANGE),
                             ("New parent: RTX (UEI PPLZG8J3N9D4)", BLUE), ("Other or blank", GREY)])]
    for i, (m, a, b, o) in enumerate(rows):
        x = left + i * bw + bw * 0.15
        y = y_of(0)
        for v, colr in ((a, ORANGE), (b, BLUE), (o, GREY)):
            if v:
                out.append(rect(x, y_of(0) - (y_of(0) - y_of(v)) - (y_of(0) - y), bw * 0.7, y_of(0) - y_of(v), colr, f"{m}: {v:,} rows"))
                y -= y_of(0) - y_of(v)
        if i % 3 == 0:
            out.append(text(left + i * bw + bw / 2, h - 14, m, 8, "middle", MUTED))
        if m == "2020-04":
            xm = left + i * bw
            out.append(line(xm, top - 8, xm, top + ph, RED, 1.2, "4,3"))
            out.append(text(xm - 4, top - 1, "Merger closed 2020-04-03", 9, "end", RED))
    cap = ("Raytheon rows by month and the parent ID recorded on them. The parent switches to RTX within two months "
           "of the merger and stays switched, so the parent ID reflects the time of the action, not today.")
    return svg(w, h, "".join(out)), cap


def fig_months_heatmap() -> tuple[str, str]:
    c = duckdb.connect()
    m = c.execute(f"""SELECT fiscal_year, month, rows, h01_thin_rows OR h02_thin_dollars
                      FROM read_parquet('{stage2.CROSS / "months.parquet"}')""").fetchall()
    yt = years_table()
    fys = fiscal_years()
    cells = {(fy, mo[-2:]): (n, thin) for fy, mo, n, thin in m}
    order = ["10", "11", "12", "01", "02", "03", "04", "05", "06", "07", "08", "09"]
    names = ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep"]
    left, top, cw, ch = 50, 16, 52, 12.5
    out = [HATCH]
    for j, nm in enumerate(names):
        out.append(text(left + j * cw + cw / 2, top - 4, nm, 9, "middle", MUTED))
    for i, fy in enumerate(fys):
        y = top + i * ch
        out.append(text(left - 6, y + ch - 3, f"FY{fy}", 9, "end", MUTED))
        if yt.get(fy, {}).get("status") != "present":
            out.append(rect(left, y + 0.5, cw * 12, ch - 1, "url(#hatch)", "pending - not yet downloaded"))
            continue
        ymax = max((cells.get((fy, mo), (0, False))[0] for mo in order), default=1) or 1
        for j, mo in enumerate(order):
            n, thin = cells.get((fy, mo), (0, False))
            t = n / ymax
            colr = f"rgb({int(235 - 200 * t)},{int(244 - 140 * t)},{int(255 - 90 * t)})"
            out.append(rect(left + j * cw + 0.5, y + 0.5, cw - 1, ch - 1, colr, f"FY{fy} {names[j]}: {n:,} rows",
                            RED if thin else None))
            out.append(text(left + j * cw + cw / 2, y + ch - 3.2, f"{n / 1000:.0f}k", 7.5, "middle",
                            "#ffffff" if t > 0.6 else INK))
    h = top + len(fys) * ch + 4
    cap = ("Rows per month (thousands), shaded relative to each year's busiest month. Every month of every present year "
           "has data; September is the usual year-end peak. Red outline: a thin month (below half the year's median, "
           "by rows or dollars).")
    return svg(left + 12 * cw + 4, int(h), "".join(out)), cap


FIGURES = {"rows_and_dollars": fig_rows_and_dollars, "benchmarks": fig_benchmarks, "monthly_net": fig_monthly_net,
           "coverage": fig_coverage, "flags_by_year": fig_flags_by_year, "parent_switch": fig_parent_switch,
           "months_heatmap": fig_months_heatmap}


# ============================================================================================ markdown -> HTML


LIST_RE = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.*)$")
FIG_RE = re.compile(r"^\s*<!--\s*figure:\s*(\w+)\s*-->\s*$")
NUMERIC = re.compile(r"^[-+]?\$?[-+]?[0-9][0-9,]*(\.[0-9]+)?\s*(%|B|GB|M|k)?$|^-?\$[0-9]")


def inline(s: str) -> str:
    codes: list[str] = []

    def keep(m):                       # code spans become placeholders, so bold around them still works
        codes.append(f"<code>{esc(m[1])}</code>")
        return f"\x00{len(codes) - 1}\x00"

    p = esc(re.sub(r"`([^`]+)`", keep, s))
    # link text may hold one level of brackets, so a citation written [[1]](https://...) links as "[1]"
    p = re.sub(r"\[((?:[^\[\]]|\[[^\[\]]*\])+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', p)
    p = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", p)                         # repo-relative links: text only
    p = re.sub(r"&lt;(https?://[^&\s]+)&gt;", r'<a href="\1">\1</a>', p)
    p = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", p)
    p = re.sub(r"(?<![\w*])\*(?![\s*])(.+?)(?<![\s*])\*(?![\w*])", r"<em>\1</em>", p)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m[1])], p)


class Doc:
    def __init__(self):
        self.fig_no = 0
        self.title = ""

    def figure(self, name: str) -> str:
        figs = FIGURES
        if name not in figs:                    # version 2 figures live in their own module, loaded only when used
            from .report_figures_v2 import V2_FIGURES
            figs = {**FIGURES, **V2_FIGURES}
        if name not in figs:
            raise SystemExit(f"Unknown figure marker: {name}")
        self.fig_no += 1
        body, cap = figs[name]()
        return f'<figure>{body}<figcaption><strong>Figure {self.fig_no}.</strong> {esc(cap)}</figcaption></figure>'

    @staticmethod
    def table(lines: list[str]) -> str:
        rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in lines]
        head, body = rows[0], [r for r in rows[2:]] if len(rows) > 1 and re.match(r"^[\s|:-]+$", lines[1]) else rows[1:]
        th = "".join(f"<th>{inline(c)}</th>" for c in head)
        trs = "".join("<tr>" + "".join(f'<td{" class=num" if NUMERIC.match(re.sub(r"[*`]", "", c)) else ""}>{inline(c)}</td>'
                                       for c in r) + "</tr>" for r in body)
        return f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>"

    def blocks(self, lines: list[str]) -> str:
        out, i, n = [], 0, len(lines)
        while i < n:
            ln = lines[i]
            if not ln.strip():
                i += 1
                continue
            if (m := FIG_RE.match(ln)):
                out.append(self.figure(m[1]))
                i += 1
                continue
            if ln.lstrip().startswith("```"):          # fenced code block (commands in an appendix)
                j = i + 1
                while j < n and not lines[j].lstrip().startswith("```"):
                    j += 1
                out.append(f"<pre><code>{esc(chr(10).join(lines[i + 1:j]))}</code></pre>")
                i = j + 1
                continue
            if ln.lstrip().startswith("<!--"):
                while i < n and "-->" not in lines[i]:
                    i += 1
                i += 1
                continue
            if (m := re.match(r"^(#{1,4})\s+(.*)$", ln)):
                lvl = len(m[1])
                if lvl == 1 and not self.title:
                    self.title = m[2]
                out.append(f"<h{lvl}>{inline(m[2])}</h{lvl}>")
                i += 1
                continue
            if ln.strip() == "---":
                out.append("<hr>")
                i += 1
                continue
            if ln.lstrip().startswith("|"):
                j = i
                while j < n and lines[j].lstrip().startswith("|"):
                    j += 1
                out.append(self.table(lines[i:j]))
                i = j
                continue
            if ln.startswith(">"):
                j = i
                while j < n and lines[j].startswith(">"):
                    j += 1
                out.append(f"<blockquote>{self.blocks([x[1:].lstrip() for x in lines[i:j]])}</blockquote>")
                i = j
                continue
            if (m := LIST_RE.match(ln)):
                indent, ordered = len(m[1]), m[2][0].isdigit()
                start = int(m[2][:-1]) if ordered else 1
                items = []
                while i < n and (m2 := LIST_RE.match(lines[i])) and len(m2[1]) == indent and m2[2][0].isdigit() == ordered:
                    content = indent + len(m2[2]) + 1
                    item = [m2[3]]
                    i += 1
                    while i < n:
                        nxt = lines[i]
                        if not nxt.strip():
                            j = i
                            while j < n and not lines[j].strip():
                                j += 1
                            if j < n and len(lines[j]) - len(lines[j].lstrip()) > indent:
                                item.append("")
                                i += 1
                                continue
                            break
                        lead = len(nxt) - len(nxt.lstrip())
                        if lead <= indent:
                            break
                        item.append(nxt[min(lead, content):])
                        i += 1
                    items.append(item)
                tag = "ol" if ordered else "ul"
                st = f' start="{start}"' if ordered and start != 1 else ""
                lis = "".join(f"<li>{self.blocks(it)}</li>" for it in items)
                out.append(f"<{tag}{st}>{lis}</{tag}>")
                continue
            j = i
            para = []
            while j < n and lines[j].strip() and not (FIG_RE.match(lines[j]) or LIST_RE.match(lines[j])
                                                      or lines[j].lstrip().startswith("```")
                                                      or re.match(r"^#{1,4}\s", lines[j]) or lines[j].lstrip().startswith("|")
                                                      or lines[j].startswith(">") or lines[j].strip() == "---"):
                para.append(lines[j].strip())
                j += 1
            out.append(f"<p>{inline(' '.join(para))}</p>")
            i = j
        return "".join(out)


CSS = """
@page { size: Letter; margin: 0.65in 0.7in 0.75in;
  @bottom-left { content: "Contract transactions FY2008-FY2025 · integrity and completeness · release 2026-09-06"; font: 8pt Helvetica, Arial, sans-serif; color: #718096; }
  @bottom-right { content: "Page " counter(page) " of " counter(pages); font: 8pt Helvetica, Arial, sans-serif; color: #718096; } }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font: 10pt/1.45 Helvetica, Arial, sans-serif; color: #1a202c; margin: 0; }
h1 { font-size: 19pt; margin: 0 0 2pt; line-height: 1.2; }
.sub { color: #4a5568; font-size: 9.5pt; margin: 0 0 12pt; padding-bottom: 8pt; border-bottom: 2px solid #2b6cb0; }
h2 { font-size: 13.5pt; margin: 16pt 0 5pt; padding-bottom: 2pt; border-bottom: 1px solid #cbd5e0; break-after: avoid; }
h3 { font-size: 11pt; margin: 12pt 0 4pt; break-after: avoid; }
p { margin: 4pt 0 6pt; orphans: 3; widows: 3; }
ul, ol { margin: 3pt 0 6pt; padding-left: 18pt; }
li { margin: 2pt 0; } li > p { margin: 2pt 0; }
table { border-collapse: collapse; width: 100%; font-size: 8pt; margin: 5pt 0 8pt; }
th, td { border: 1px solid #cbd5e0; padding: 2pt 4pt; vertical-align: top; text-align: left; }
th { background: #edf2f7; }
td.num { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
tr { break-inside: avoid; }
td code { word-break: break-all; }
code { font-family: Menlo, Consolas, monospace; font-size: 8.3pt; background: #f1f5f9; padding: 0 2px; border-radius: 2px; }
blockquote { margin: 6pt 0; padding: 5pt 10pt; border-left: 3px solid #2b6cb0; background: #ebf8ff; }
blockquote p { margin: 0; }
figure { margin: 8pt 0 12pt; break-inside: avoid; }
figcaption { font-size: 8.5pt; color: #4a5568; margin-top: 3pt; line-height: 1.35; }
hr { border: 0; border-top: 1px solid #cbd5e0; margin: 10pt 0; }
pre { background: #f1f5f9; padding: 6pt 8pt; border-radius: 3px; font-size: 7.8pt; line-height: 1.4; white-space: pre-wrap; break-inside: avoid; }
pre code { background: none; padding: 0; font-size: 7.8pt; }
a { color: #2b6cb0; text-decoration: none; }
"""


# Later versions only (version 1's rendering stays as built): IDs and paths in table cells wrap only at a word boundary.
LATER_CSS = """
td code { word-break: normal; overflow-wrap: break-word; }
.nw { white-space: nowrap; }
"""

# Documents without figures (research notes, the glossary): long URLs in source lists wrap instead of running off the page.
DOC_CSS = """
a { overflow-wrap: anywhere; }
td { overflow-wrap: anywhere; }
td code { overflow-wrap: anywhere; font-size: 7.4pt; }
h4 { font-size: 10.5pt; margin: 10pt 0 2pt; break-after: avoid; }
h4 + p { break-before: avoid; }
"""

# Submission documents (--plain): the footer holds only the page number, and the page is compact.
PLAIN_FOOTER = '@bottom-center { content: counter(page); font: 9pt Helvetica, Arial, sans-serif; color: #1a202c; } }'
PLAIN_CSS = """
@page { margin: 0.6in; }
body { font: 10pt/1.35 Helvetica, Arial, sans-serif; }
h1 { font-size: 15pt; margin: 0 0 6pt; padding-bottom: 5pt; border-bottom: 2px solid #2b6cb0; }
h2 { font-size: 11.5pt; margin: 9pt 0 3pt; }
p { margin: 2pt 0 4pt; }
h1 + p, h1 + p + p, h1 + p + p + p { margin: 0 0 1pt; }
table { font-size: 8.5pt; margin: 3pt 0 4pt; }
th, td { padding: 1.5pt 4pt; }
p.ref { font-size: 9pt; line-height: 1.3; margin: 0 0 2.5pt; }
"""

# Paper style (--paper, which implies --plain): a conventional academic look for submissions. Serif type, a
# centered title block, headings without rules, and tables ruled only above, below and under the header.
PAPER_FOOTER = '@bottom-center { content: counter(page); font: 10pt "Times New Roman", Times, serif; color: #000; } }'
PAPER_CSS = """
body { font: 10.5pt/1.25 "Times New Roman", Times, "Liberation Serif", serif; color: #000; }
h1 { font-size: 15.5pt; text-align: center; border-bottom: none; padding-bottom: 0; margin: 0 0 6pt; }
h1 + p, h1 + p + p, h1 + p + p + p { text-align: center; }
h2 { font-size: 12pt; border-bottom: none; margin: 9pt 0 3pt; }
p { text-align: justify; hyphens: auto; }
a { color: #1f3f7a; }
ol { margin: 2pt 0 4pt; }
table { font-size: 9pt; border-top: 1.2px solid #000; border-bottom: 1.2px solid #000; }
th, td { border: none; padding: 1.5pt 5pt; }
th { background: none; border-bottom: 0.8px solid #000; }
p.ref { font-size: 9pt; text-align: left; hyphens: manual; }
"""

def build_html(src_md: Path | None = None, plain: bool = False, paper: bool = False) -> str:
    plain = plain or paper
    src_md = src_md or SRC_MD
    md = src_md.read_text(encoding="utf-8").splitlines()
    doc = Doc()
    body = doc.blocks(md)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yt = years_table()
    pend = [fy for fy in fiscal_years() if yt.get(fy, {}).get("status") != "present"]
    if src_md.resolve() == SRC_MD.resolve():
        sub = (f"Generated {stamp} by <code>python -m src.report_pdf</code> from <code>docs/integrity_findings.md</code>, "
               f"<code>reports/integrity/</code> and Stage 2 outputs. USAspending Award Data Archive, release 2026-09-06; "
               f"{len(present(yt))} of {len(fiscal_years())} fiscal years present"
               + (f" ({', '.join('FY' + str(f) for f in pend)} pending)" if pend else "") + ". No data was changed.")
        css = CSS
    elif src_md.stem.startswith("integrity_findings") and re.search(r"_v(\d+)$", src_md.stem):
        # later integrity versions keep commands and file paths in their appendix, not in the subtitle.
        # Other documents with a version suffix (research notes) fall through to the generic branch below.
        sub = (f"Generated {stamp}. USAspending Award Data Archive, release 2026-09-06. {len(present(yt))} of "
               f"{len(fiscal_years())} fiscal years present. No data was changed.")
        m = re.search(r"_v(\d+)$", src_md.stem)
        css = CSS.replace("release 2026-09-06\"", f"release 2026-09-06 · version {m[1]}\"" if m else "release 2026-09-06\"", 1)
        css = css.replace("Contract transactions FY2008-FY2025", "Contract transactions FY2008 to FY2025", 1) + LATER_CSS
    elif plain:             # submission documents: no subtitle, and only the page number in the footer
        sub = ""
        css = re.sub(r"@bottom-left \{.*?\} *\n *@bottom-right \{.*?\} \}", PLAIN_FOOTER, CSS, count=1, flags=re.S)
        css += LATER_CSS + DOC_CSS + PLAIN_CSS
        if paper:
            css = css.replace(PLAIN_FOOTER, PAPER_FOOTER, 1) + PAPER_CSS
    else:                   # any other document (research notes, the glossary): the footer names the document itself
        sub = f"Generated {stamp}."
        footer = doc.title.replace('"', "'") + f" · generated {stamp}"
        css = CSS.replace("Contract transactions FY2008-FY2025 · integrity and completeness · release 2026-09-06", footer, 1)
        css += LATER_CSS + DOC_CSS
    if src_md.resolve() != SRC_MD.resolve():   # keep ISO dates on one line (outside the inline SVG charts)
        body = "".join(part if part.startswith("<") else re.sub(r"\b(\d{4}-\d{2}-\d{2})\b", r'<span class="nw">\1</span>', part)
                       for part in re.split(r"(<svg.*?</svg>|<[^>]+>)", body, flags=re.S))
    if sub:
        body = body.replace("</h1>", f'</h1><p class="sub">{sub}</p>', 1)
    if plain and "<h2>References</h2>" in body:   # reference entries in a smaller size (page limits exclude them)
        head, refs = body.split("<h2>References</h2>", 1)
        body = head + "<h2>References</h2>" + refs.replace("<p>", '<p class="ref">')
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{esc(doc.title)}</title>'
            f"<style>{css}</style></head><body>{body}</body></html>")


def print_pdf(html_path: Path, pdf_path: Path) -> None:
    if not CHROME.exists():
        raise SystemExit(f"Chrome not found at {CHROME}; the HTML is at {html_path}")
    profile = Path(tempfile.mkdtemp(prefix="report_pdf_chrome_"))
    tmp = pdf_path.with_suffix(".pdf.tmp")
    try:
        subprocess.run([str(CHROME), "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                        "--disable-background-networking", "--disable-component-update", "--disable-sync",
                        "--disable-extensions", "--disable-default-apps", f"--user-data-dir={profile}",
                        "--no-pdf-header-footer", f"--print-to-pdf={tmp}", html_path.as_uri()],
                       capture_output=True, timeout=300, check=False)
        if not tmp.exists() or tmp.stat().st_size < 10_000:
            raise SystemExit("Chrome did not produce the PDF")
        tmp.replace(pdf_path)
    finally:
        shutil.rmtree(profile, ignore_errors=True)
        tmp.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--in", dest="src", type=Path, default=SRC_MD, help="markdown source (default: docs/integrity_findings.md)")
    p.add_argument("--out", type=Path, default=OUT_PDF, help="PDF to write (default: reports/integrity/integrity_report.pdf)")
    p.add_argument("--plain", action="store_true",
                   help="submission document: no 'Generated' subtitle, and only the page number in the footer")
    p.add_argument("--paper", action="store_true",
                   help="submission document in a conventional academic style (serif type, centered title); implies --plain")
    a = p.parse_args(argv)
    src = a.src if a.src.is_absolute() else config.REPO_ROOT / a.src
    out = a.out if a.out.is_absolute() else config.REPO_ROOT / a.out
    WORK.mkdir(parents=True, exist_ok=True)
    html_path = WORK / ("integrity_report.html" if out.resolve() == OUT_PDF.resolve() else f"{out.stem}.html")
    html_path.write_text(build_html(src, plain=a.plain, paper=a.paper), encoding="utf-8")
    print_pdf(html_path, out)
    pages = out.read_bytes().count(b"/Type /Page") - out.read_bytes().count(b"/Type /Pages")
    print(f"PDF -> {out} ({out.stat().st_size // 1024} KB, {pages} pages); HTML -> {html_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
