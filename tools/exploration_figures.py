"""Figures for the follow-up findings, built only from the CSVs in reports/exploration/.

    .venv/bin/python tools/exploration_figures.py              # the core, backup and other sets, and the redrawn figure 14
    .venv/bin/python tools/exploration_figures.py --dropped    # also redraws the other dropped figures

Writes each figure as PDF and PNG to a set folder under reports/exploration/figures/, then core_figures.pdf, backup_figures.pdf
and reports/exploration/figures_gallery_v2.md. The colors, font and sizes come from report_figures.py, the script behind the
first report's figures. Nothing here reads the raw data, changes a table or is a decision. findings_figures.pdf and
figures_gallery.md, from the first round of figures, are no longer written.
"""

from __future__ import annotations

import csv
import re
import statistics
import sys
import textwrap
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TABLES = ROOT / "reports" / "exploration"
OUT = TABLES / "figures"

# Colors: categorical slots 1 to 3 of the reference palette, as in report_figures.py.
# Slot 3 (aqua) is below 3:1 contrast on white, so every aqua series also carries a direct label and its own dash.
BLUE = "#2a78d6"      # main series
ORANGE = "#eb6834"    # comparison
AQUA = "#1baf7a"      # third series, only with a direct label
GRAY = "#9a9893"      # chance or a reference
DARK = "#33322f"      # a third series that is neither chance nor a reference
MOCK_GRAY = "#8a8984"  # the gray dashes of figure 1a
BAND = "#eef3fa"      # the shaded FY2012 to FY2020 of figure 1a
LINE_GRAY = "#d9d8d4"  # the light gray line of figure 1b
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
DASH = (0, (3, 1.5))
DOT = (0, (1, 1.2))
# Bars have no marker or line style, so a comparison series also carries a hatch.
STRIPES = {"hatch": "/////", "edgecolor": "white", "linewidth": 0}
DOTS = {"hatch": "....", "edgecolor": "white", "linewidth": 0}
HALF = (3.3, 2.2)
FULL_W = 6.9
FONTS = (Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
         Path("/System/Library/Fonts/Supplemental/Arial.ttf"))     # Helvetica-metric fonts, in order of preference
BOLD_FONTS = (Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
              Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"))

AS_RECORDED, ONE_FIRM, SPREAD, PLANNED, EVERY, PAY_AHEAD, POOLED, CHANCE = (
    "As recorded", "One firm per contract", "Spread evenly", "Spread over the planned length", "Spread every contract",
    "Spread pay-ahead contracts only", "Three years scored together", "Chance (years shuffled)")
ALL_MARKETS, STABLE = "All markets, FY2012 to FY2020", "Codes that never changed, FY2008 to FY2025"
ROW_DATES, WHOLE_CONTRACT = "By each row's dates", "By the whole contract"
RULE_LABELS = {"baseline": ONE_FIRM, "S1": SPREAD, "S2": PLANNED, "S3": EVERY, "S4": PAY_AHEAD}
ERAS = ((2008, 2011), (2012, 2020), (2021, 2025))
AGENCY_SHORT = {"089": "Energy", "036": "VA", "020": "Treasury", "080": "NASA", "070": "Homeland Security", "019": "State",
                "075": "HHS", "086": "HUD", "047": "GSA", "015": "Justice", "1602": "Pension Benefit Guaranty",
                "069": "Transportation", "012": "Agriculture", "014": "Interior"}
# An opaque legend box, so a code-change line or gridline does not run through the legend text.
MASK = {"frameon": True, "facecolor": "white", "edgecolor": "none", "framealpha": 1, "borderpad": 0.2}
SERVICE_LETTERS = {"Q": "Medical services", "D": "IT and telecom", "M": "Operating government facilities", "R": "Professional support",
                   "G": "Social services", "Y": "Construction"}


def setup() -> None:
    for regular, bold in zip(FONTS, BOLD_FONTS):
        if regular.exists():
            font_manager.fontManager.addfont(str(regular))
            if bold.exists():
                font_manager.fontManager.addfont(str(bold))
            plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(regular)).get_name()
            break
    plt.rcParams.update({
        "font.size": 7.5, "axes.titlesize": 7.5, "axes.labelsize": 7.5, "xtick.labelsize": 7, "ytick.labelsize": 7,
        "axes.edgecolor": INK_2, "axes.labelcolor": INK, "xtick.color": INK_2, "ytick.color": INK_2,
        "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.6,
        "xtick.major.width": 0.6, "ytick.major.width": 0.6, "pdf.fonttype": 42, "text.parse_math": False, "hatch.linewidth": 0.5,
    })


def read(name: str) -> list[dict]:
    with open(TABLES / f"{name}.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def finish(fig, name: str, title: str, subtitle: str, bottom: float = 0.0) -> None:
    """Title and one-line subtitle above the plot, then save both formats. bottom reserves inches below the plot for a figure legend."""
    w, h = fig.get_size_inches()
    head = textwrap.wrap(title, int(w * 17.2))
    sub = textwrap.wrap(subtitle, int(w * 21.5))
    if len(sub) != 1:
        raise SystemExit(f"{name}: the subtitle runs to {len(sub)} lines: {subtitle}")
    top = 0.03 + 0.125 * len(head) + 0.125
    fig.tight_layout(pad=0.3, rect=(0, bottom / h, 1, 1 - top / h))
    y = 1 - 0.03 / h
    for line in head:
        fig.text(0.008, y, line, fontsize=8, fontweight="bold", color=INK, va="top", ha="left")
        y -= 0.125 / h
    fig.text(0.008, y - 0.005 / h, sub[0], fontsize=6.5, color=INK_2, va="top", ha="left")
    (OUT / name).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.pdf")
    fig.savefig(OUT / f"{name}.png", dpi=220)
    plt.close(fig)


def grid_y(ax) -> None:
    ax.yaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def grid_x(ax) -> None:
    ax.xaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def year_axis(ax, first: int = 2008, last: int = 2025, step: int = 4) -> None:
    """Fiscal-year ticks, and the two code changes wherever they fall on this axis."""
    ticks = [y for y in range(2008, 2026, step) if first <= y <= last]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"FY{y}" for y in ticks])
    ax.set_xlim(first - 0.6, last + 0.6)
    ax.set_xlabel("Fiscal year")
    for year in (2012, 2021):
        if first < year <= last:
            ax.axvline(year - 0.5, color=INK_2, linewidth=0.6, linestyle=(0, (1, 2)), zorder=1)
            ax.text(year - 0.5, 1.005, f"FY{year} code change", transform=ax.get_xaxis_transform(), fontsize=6.3, color=INK_2, ha="center", va="bottom")


def pct_axis(ax, ticks, axis: str = "y") -> None:
    labels = [f"{t:g}%" for t in ticks]
    if axis == "y":
        ax.set_yticks(ticks)
        ax.set_yticklabels(labels)
    else:
        ax.set_xticks(ticks)
        ax.set_xticklabels(labels)


def f(value) -> float:
    return float(value)


def one(value: float) -> Decimal:
    """One decimal, rounding halves up, so 17.95 prints as 18.0 and not, through binary rounding, as 17.9."""
    return Decimal(str(round(value, 6))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def method_rows(line_set: str, field: str) -> list[tuple]:
    """(label, observed, chance) for each method at 500 points. field is rising_pct, falling_pct, or either with _by_dollars."""
    shuffled = field.replace("_pct", "_pct_after_shuffle")
    ten = {r["method"]: r for r in read("p10_pooled_rising") if r["line_set"] == line_set and r["cutoff"] == "500"}
    twelve = {r["rule"]: r for r in read("p12_rising") if r["line_set"] == line_set and r["cutoff"] == "500"}
    rows = [(AS_RECORDED, ten["averaged"]), (POOLED, ten["pooled"]), (ONE_FIRM, twelve["baseline"]), (SPREAD, twelve["S1"]),
            (PLANNED, twelve["S2"]), (EVERY, twelve["S3"]), (PAY_AHEAD, twelve["S4"])]
    return [(label, f(r[field]), f(r[shuffled])) for label, r in rows]


def dot_pairs(ax, rows: list[tuple], xmax: float, xlabel: str, gaps: bool = True, legend: bool = True, ylabel: str = "Method") -> None:
    ys = list(range(len(rows)))[::-1]
    for y, (_, obs, chance) in zip(ys, rows):
        ax.plot([chance, obs], [y, y], color=GRAY, linewidth=1.2, zorder=2)
        ax.scatter([chance], [y], s=18, color=GRAY, marker="D", zorder=3, linewidths=0, label=CHANCE if y == ys[0] else None)
        ax.scatter([obs], [y], s=22, color=BLUE, zorder=4, linewidths=0, label="Observed" if y == ys[0] else None)
        if gaps:
            ax.text(xmax, y, f"{one(obs - chance):+} points".replace("-", "−"), va="center", ha="right", fontsize=6.5, color=INK)
    ax.set_yticks(ys)
    ax.set_yticklabels([r[0] for r in rows])
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.set_xlim(0, xmax)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    grid_x(ax)
    if legend:
        ax.legend(loc="upper left", frameon=False, fontsize=6.5, handletextpad=0.2, borderaxespad=0.1)


# ============================================================================================ Is concentration rising?


def f01() -> None:
    twelve = {r["period"]: r for r in read("p12_share_by_year")}
    years = list(range(2008, 2026))
    fig, ax = plt.subplots(figsize=(FULL_W, 2.9))
    for key, label, color, dash, width in (("report", AS_RECORDED, BLUE, "solid", 1.7), ("baseline", ONE_FIRM, ORANGE, DASH, 1.5), ("S1", SPREAD, AQUA, DOT, 1.5)):
        ax.plot(years, [f(twelve[f"FY{y}"][key]) for y in years], color=color, linestyle=dash, linewidth=width, label=label, zorder=3)
    pooled = {int(r["fiscal_year"]): r["pooled_share_above_2500_pct"] for r in read("p10_pooled_share_by_year")}
    for i, (a, b) in enumerate(ERAS):
        xs = [y for y in range(a, b + 1) if pooled[y]]
        ax.plot(xs, [f(pooled[y]) for y in xs], color=GRAY, linewidth=1.5, marker="o", markersize=2.4, label=POOLED if i == 0 else None, zorder=2)
    ax.annotate(SPREAD, xy=(2013, f(twelve["FY2013"]["S1"])), xytext=(2012.2, 46.5), fontsize=6.5, color=INK, ha="left",
                arrowprops={"arrowstyle": "-", "color": INK_2, "linewidth": 0.5})
    year_axis(ax)
    ax.set_ylim(30, 60)
    pct_axis(ax, [30, 40, 50, 60])
    ax.set_ylabel("Share of civilian dollars above HHI 2,500")
    grid_y(ax)
    ax.legend(loc="lower left", ncol=4, fontsize=6.5, handlelength=2.2, borderaxespad=0.1, **MASK)
    finish(fig, "dropped/f01_civilian_share_by_year", "The civilian share rose from FY2012 to FY2020 under every version of the measure",
           "Civilian share of dollars above HHI 2,500. Spreading covers contracts that start and end inside the data. Three-year scores carry their last year.")


def f02() -> None:
    rows = read("p6_levels_by_year")
    years = [int(r["fiscal_year"]) for r in rows]
    fig, ax = plt.subplots(figsize=(FULL_W, 2.5))
    ax.plot(years, [f(r["share_above_2500_agency_level_pct"]) for r in rows], color=BLUE, linewidth=1.7, label="Each agency's market on its own")
    ax.plot(years, [f(r["share_above_2500_civilian_wide_code_pct"]) for r in rows], color=ORANGE, linestyle=DASH, linewidth=1.5, label="Each product across all civilian agencies")
    year_axis(ax)
    ax.set_ylim(0, 60)
    pct_axis(ax, [0, 20, 40, 60])
    ax.set_ylabel("Share of civilian dollars above HHI 2,500")
    grid_y(ax)
    ax.legend(loc="lower left", ncol=2, fontsize=6.5, handlelength=2.2, borderaxespad=0.1, **MASK)
    finish(fig, "dropped/f02_markets_drawn_wider", "With markets drawn across all civilian agencies, levels are lower and the rise holds",
           "Civilian share of dollars above HHI 2,500, as recorded, with markets drawn per agency and across all civilian agencies.")


def f03() -> None:
    fig, ax = plt.subplots(figsize=(FULL_W, 2.5))
    dot_pairs(ax, method_rows("report's lines", "rising_pct"), 50, "Share of 5,772 markets rising by 500 points or more")
    pct_axis(ax, [0, 10, 20, 30, 40], "x")
    finish(fig, "dropped/f03_rising_by_count", "The rise beats chance under every method, by about 10 markets in 100",
           f"{ALL_MARKETS}, including Defense. Each market counts once. The right column gives observed less chance.")


def f04() -> None:
    fig, ax = plt.subplots(figsize=(FULL_W, 2.5))
    dot_pairs(ax, method_rows("report's lines", "rising_pct_by_dollars"), 40, "Share of the markets' dollars in markets rising by 500 points or more")
    pct_axis(ax, [0, 10, 20, 30], "x")
    finish(fig, "backup/f01_rising_by_dollars", "By dollars, the rise also beats chance under every method",
           f"{ALL_MARKETS}, including Defense. Each market counts by its dollars. The right column gives observed less chance.")


def f05() -> None:
    fig, axes = plt.subplots(2, 2, figsize=(FULL_W, 3.9))
    keep = (AS_RECORDED, POOLED, ONE_FIRM, SPREAD)
    panels = (("rising_pct", "Rising, by count of markets"), ("falling_pct", "Falling, by count of markets"),
              ("rising_pct_by_dollars", "Rising, by dollars"), ("falling_pct_by_dollars", "Falling, by dollars"))
    for i, (ax, (field, label)) in enumerate(zip(axes.flat, panels)):
        rows = [r for r in method_rows("stable lines", field) if r[0] in keep]
        dot_pairs(ax, rows, 80, "Share of the 979 markets' dollars" if i >= 2 else "Share of the 979 markets", legend=False, ylabel="" if i % 2 else "Method")
        ax.set_title(label, color=INK, pad=3, loc="left")
        pct_axis(ax, [0, 20, 40, 60], "x")
        if i % 2:
            ax.set_yticklabels([])
    fig.legend(*axes[0][0].get_legend_handles_labels(), loc="lower center", ncol=2, frameon=False, fontsize=6.5, handletextpad=0.2)
    finish(fig, "backup/f02_codes_never_changed", "On codes that never changed, more markets rise than chance, but more dollars sit in falling markets",
           f"{STABLE}, including Defense, at 500 points. The right columns give observed less chance.", bottom=0.17)


def f06() -> None:
    rows = read("p12_line_agreement")
    classes = ("rising", "falling", "neither")
    fig, axes = plt.subplots(1, 2, figsize=(FULL_W, 2.6))
    for ax, line_set, label in ((axes[0], "report's lines", ALL_MARKETS), (axes[1], "stable lines", STABLE)):
        cell = {(r["baseline_class"], r["s1_class"]): int(r["lines"]) for r in rows if r["line_set"] == line_set}
        total = sum(cell.values())
        grid = [[cell[(a, b)] for b in classes] for a in classes]
        ax.imshow([[1 if a == b else 0 for b in classes] for a in classes], cmap=LinearSegmentedColormap.from_list("kept", ["#f1f0ec", BLUE]), vmin=0, vmax=1, aspect="auto")
        for i, a in enumerate(classes):
            for j, b in enumerate(classes):
                ax.text(j, i, f"{grid[i][j]:,}", ha="center", va="center", fontsize=7.5, color="white" if a == b else INK, fontweight="bold" if a == b else "normal")
        same = sum(cell[(c, c)] for c in classes)
        ax.set_title(f"{label}\n{same:,} of {total:,} keep their label ({100 * same / total:.1f}%)", color=INK, pad=3, loc="left")
        ax.set_xticks(range(3))
        ax.set_xticklabels([c.capitalize() for c in classes])
        ax.set_yticks(range(3))
        ax.set_yticklabels([c.capitalize() for c in classes])
        ax.set_xlabel(f"Label when {SPREAD.lower()} (count of markets)")
        ax.set_ylabel(ONE_FIRM)
        ax.tick_params(length=0)
        for s in ax.spines.values():
            s.set_visible(False)
    finish(fig, "backup/f03_labels_kept", "About three in four markets keep their label when contracts are spread",
           "Rising, falling or neither at 500 points, with each contract under one firm, then after spreading. Blue cells keep their label.")


def f07() -> None:
    rows = read("p5_stable_share_by_year")
    years = [int(r["fiscal_year"]) for r in rows]
    vals = [f(r["stable_codes_share_of_civilian_pct"]) for r in rows]
    fig, ax = plt.subplots(figsize=HALF)
    ax.plot(years, vals, color=BLUE, linewidth=1.7)
    for y, v in ((years[0], vals[0]), (years[-1], vals[-1])):
        ax.text(y, v - 1.6, f"{v:.0f}%", ha="center", va="top", fontsize=6.5, color=INK)
    year_axis(ax)
    ax.set_ylim(0, 35)
    pct_axis(ax, [0, 10, 20, 30])
    ax.set_ylabel("Share of civilian dollars")
    grid_y(ax)
    finish(fig, "dropped/f07_stable_share", "Codes that never changed hold a shrinking share of civilian dollars",
           "Civilian net on codes that never changed, over all civilian net.")


# ============================================================================================ Does contract timing drive the swings?


def f08() -> None:
    rows = {r["rule"]: r for r in read("p12_swings") if r["line_set"] == "report's lines" and r["agencies"] == "civilian"}
    order = ("baseline", "S4", "S2", "S1", "S3")
    labels = [RULE_LABELS[k] for k in order]
    colors = [GRAY if k == "baseline" else BLUE for k in order]
    fig, axes = plt.subplots(1, 2, figsize=(FULL_W, 2.3), sharey=True)
    for ax, field, xlabel, fmt, lim in ((axes[0], "median_change", "Median yearly change in HHI (points)", "{:.0f}", 800),
                                        (axes[1], "jump_share_pct", "Share of yearly changes of 1,000 points or more", "{:.1f}%", 50)):
        vals = [f(rows[k][field]) for k in order]
        ys = list(range(len(order)))[::-1]
        ax.barh(ys, vals, color=colors, height=0.62, zorder=3)
        for y, k, v in zip(ys, order, vals):
            if k in ("baseline", "S1"):
                ax.text(v + lim * 0.012, y, fmt.format(v), va="center", fontsize=6.5, color=INK)
        ax.set_yticks(ys)
        ax.set_yticklabels(labels)
        ax.set_xlim(0, lim)
        ax.set_xlabel(xlabel)
        grid_x(ax)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
    pct_axis(axes[1], [0, 10, 20, 30, 40, 50], "x")
    axes[0].set_ylabel("Method")
    finish(fig, "core/f03_swings", "Spreading contracts evenly cuts the typical yearly change by about a quarter",
           "Civilian markets, FY2012 to FY2020. Every bar counts each contract under one firm.")


def f09() -> None:
    rows = {r["rule"]: r for r in read("p9_jump_summary") if r["line_set"] == "report's lines" and r["agencies"] == "civilian" and r["jump_size"] == "1000"}
    fig, axes = plt.subplots(1, 2, figsize=(FULL_W, 2.3), sharey=True)
    width = 0.36
    for ax, suffix, label in ((axes[0], "", "By count of pairs"), (axes[1], "_by_dollars", "By dollars")):
        for x, rule in enumerate(("row_548", "award_548_80")):
            jump, calm = f(rows[rule][f"jumps_timing_linked_pct{suffix}"]), f(rows[rule][f"calm_timing_linked_pct{suffix}"])
            ax.bar(x - width / 2 - 0.02, jump, width, color=BLUE, zorder=3, label="Big jumps" if x == 0 else None)
            ax.bar(x + width / 2 + 0.02, calm, width, color=GRAY, zorder=3, label="Quiet years" if x == 0 else None, **STRIPES)
            ax.text(x - width / 2 - 0.02, jump + 0.6, f"{one(jump)}%", ha="center", va="bottom", fontsize=6.5, color=INK)
            ax.text(x + width / 2 + 0.02, calm + 0.6, f"{one(calm)}%", ha="center", va="bottom", fontsize=6.5, color=INK_2)
        ax.set_xticks([0, 1])
        ax.set_xticklabels([ROW_DATES, WHOLE_CONTRACT])
        ax.set_xlabel("How money paid ahead is judged")
        ax.set_title(label, color=INK, pad=3, loc="left")
        grid_y(ax)
    axes[0].set_ylim(0, 40)
    pct_axis(axes[0], [0, 10, 20, 30, 40])
    axes[0].set_ylabel("Share tied to pay-ahead money")
    axes[0].legend(loc="upper right", frameon=False, fontsize=6.5, handlelength=1.0)
    finish(fig, "core/f04_jumps_and_pay_ahead", "Big jumps are tied to pay-ahead money a few points more often by count, and up to 12 points more by dollars",
           "Civilian markets, FY2012 to FY2020, as recorded. A big jump is a yearly change of 1,000 points or more, and a quiet year is under 250.")


def f10() -> None:
    rows = [r for r in read("p9_jumps") if r["line_set"] == "report's lines" and r["agency"] != "097"]
    bands = ((1e6, "Under $1M"), (1e7, "$1M to $10M"), (1e8, "$10M to $100M"), (1e9, "$100M to $1B"), (float("inf"), "$1B and over"))
    counts = [[0, 0, 0] for _ in bands]
    for r in rows:
        i = next(k for k, (hi, _) in enumerate(bands) if f(r["segment_net_higher_year"]) < hi)
        a, b = f(r["mover_share_first"]), f(r["mover_share_second"])
        counts[i][1 if a == 0 else 2 if b == 0 else 0] += 1
    fig, ax = plt.subplots(figsize=(FULL_W, 2.5))
    keys = ("Firm in the market both years", "Firm enters", "Firm leaves")
    bottoms = [0.0] * len(bands)
    for j, (label, color, look) in enumerate(zip(keys, (BLUE, ORANGE, DARK), ({"edgecolor": "white", "linewidth": 0.6}, STRIPES, DOTS))):
        vals = [100 * c[j] / sum(c) for c in counts]
        ax.bar(range(len(bands)), vals, 0.62, bottom=bottoms, color=color, label=label, zorder=3, **look)
        if j == 0:
            for x, v in enumerate(vals):
                ax.text(x, v / 2, f"{v:.0f}%", ha="center", va="center", fontsize=6.5, color="white")
        bottoms = [p + v for p, v in zip(bottoms, vals)]
    ax.set_xticks(range(len(bands)))
    ax.set_xticklabels([f"{b[1]}\n{sum(c):,} jumps" for b, c in zip(bands, counts)])
    ax.set_xlabel("Size of the market in the higher year (net dollars)")
    ax.set_ylim(0, 100)
    pct_axis(ax, [0, 25, 50, 75, 100])
    ax.set_ylabel("Share of big jumps")
    grid_y(ax)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.13), ncol=3, frameon=False, fontsize=6.5, handlelength=1.0)
    finish(fig, "backup/f04_jumps_by_size", "Most big jumps come from firms already in the market, and more so in large markets",
           "Civilian markets, FY2012 to FY2020, as recorded: 1,000-point jumps, by what the firm whose share moved most did.")


def f11() -> None:
    rows = read("p11_spread_examples")
    panels = (("36C24220C0072", "VA, 36C24220C0072"), ("HSHQDC11C00083", "Homeland Security, HSHQDC11C00083"),
              ("HSCG2311C2DB043", "Homeland Security, HSCG2311C2DB043:\nfront-loaded, then spread"))
    fig, axes = plt.subplots(1, 3, figsize=(FULL_W, 2.85))
    width = 0.42
    for ax, (piid, label) in zip(axes, panels):
        got = [r for r in rows if piid in r["award"]]
        years = [int(r["fiscal_year"]) for r in got]
        ax.bar([y - width / 2 for y in years], [f(r["baseline"]) / 1e6 for r in got], width, color=BLUE, zorder=3, label=AS_RECORDED)
        ax.bar([y + width / 2 for y in years], [f(r["S1"]) / 1e6 for r in got], width, color=ORANGE, zorder=3, label=SPREAD, **STRIPES)
        ax.axhline(0, color=INK_2, linewidth=0.6, zorder=4)
        year_axis(ax, step=6)
        ax.set_title(label, color=INK, pad=11, loc="left", fontsize=6.5)
        ax.set_ylabel("$ millions")
        grid_y(ax)
    fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=2, frameon=False, fontsize=6.5, handlelength=1.0)
    finish(fig, "core/f05_example_contracts", "Spreading flattens lumpy contracts that start and end inside the data",
           "Each contract's net by fiscal year, recorded in the year of each action against spread evenly over its span. Each panel has its own scale.", bottom=0.17)


def f12() -> None:
    rows = [r for r in read("p11_spread_money_by_year") if r["rule"] == "S1"]
    years = [int(r["fiscal_year"]) for r in rows]
    moved = [f(r["moved_out_pct_of_baseline"]) for r in rows]
    fig, axes = plt.subplots(1, 2, figsize=(FULL_W, 2.75))
    ax = axes[0]
    ax.bar(years, moved, 0.7, color=BLUE, zorder=3)
    mean = statistics.mean(moved[years.index(2012):years.index(2020) + 1])
    ax.plot([2011.6, 2020.4], [mean, mean], color=INK, linewidth=0.9, zorder=4)
    ax.text(2016, 30.6, f"Mean {mean:.2f}%, FY2012 to FY2020", ha="center", va="bottom", fontsize=6.5, color=INK)
    ax.annotate(f"{moved[-1]:.2f}%", xy=(2025, moved[-1]), xytext=(2025, moved[-2] + 1.5), ha="center", va="bottom", fontsize=6.5, color=INK, arrowprops={"arrowstyle": "-", "color": INK_2, "linewidth": 0.5, "shrinkA": 1, "shrinkB": 0})
    year_axis(ax)
    ax.set_ylim(0, 45)
    pct_axis(ax, [0, 10, 20, 30, 40])
    ax.set_ylabel("Share of the year's civilian net moved out")
    grid_y(ax)
    ax = axes[1]
    parts = ((("recorded: still running after FY2025", "recorded: started before the data and still running"), "Still running after FY2025", BLUE, {"edgecolor": "white", "linewidth": 0.3}),
             (("recorded: started before the data",), "Started before the data", ORANGE, STRIPES), (("recorded: no span",), "No usable dates", DARK, DOTS))
    up, down = [0.0] * len(rows), [0.0] * len(rows)
    for cols, label, color, look in parts:
        vals = [100 * sum(f(r[c]) for c in cols) / f(r["baseline_civilian_net"]) for r in rows]
        base = [u if v >= 0 else d_ for v, u, d_ in zip(vals, up, down)]
        ax.bar(years, vals, 0.7, bottom=base, color=color, label=label, zorder=3, **look)
        up = [u + max(v, 0) for u, v in zip(up, vals)]
        down = [d_ + min(v, 0) for d_, v in zip(down, vals)]
        if color == BLUE:
            ax.text(2025.4, 81, f"{vals[-1]:.0f}% still running", ha="right", va="bottom", fontsize=6.5, color=INK, zorder=5)
    ax.axhline(0, color=INK_2, linewidth=0.6, zorder=4)
    year_axis(ax)
    ax.set_ylim(-2, 90)
    pct_axis(ax, [0, 20, 40, 60, 80])
    ax.set_ylabel("Share of the year's civilian net left as recorded")
    grid_y(ax)
    ax.legend(loc="upper left", fontsize=6.5, handlelength=1.0, **MASK)
    finish(fig, "backup/f05_money_moved", "Spreading moves about a quarter of each year's money over FY2012 to FY2020, and almost nothing in FY2025",
           "Spreading evenly. Left, money moved to other years. Right, money the rule cannot spread, by reason.")


def f13() -> None:
    rows = read("p9_paid_ahead_by_year")
    fig, ax = plt.subplots(figsize=(FULL_W, 2.6))
    series = ((ROW_DATES, BLUE, "solid", "o", [(int(r["fiscal_year"]), f(r["paid_ahead_pct"]), r["provisional"]) for r in rows if r["rule"] == "row_548"]),
              (WHOLE_CONTRACT, ORANGE, DASH, "s", [(int(r["fiscal_year"]), f(r["paid_ahead_pct"]), r["provisional"]) for r in rows if r["rule"] == "award_548_80"]),
              ("Flagged by both tests", DARK, DOT, "^", [(int(r["fiscal_year"]), 100 * f(r["net_both_main_rules"]) / f(r["civilian_net"]), r["provisional"]) for r in rows if r["rule"] == "row_548"]))
    for label, color, dash, marker, pts in series:
        firm = [p for p in pts if p[2] == "no"]
        ax.plot([p[0] for p in firm], [p[1] for p in firm], color=color, linestyle=dash, linewidth=1.6, marker=marker, markersize=3.2, label=label, zorder=3)
        late = [firm[-1]] + [p for p in pts if p[2] == "yes"]
        ax.plot([p[0] for p in late], [p[1] for p in late], color=color, linestyle=dash, linewidth=1.6, marker=marker, markersize=3.2, alpha=0.38, zorder=3)
    ax.text(2024, 37.5, "Lighter: provisional", ha="center", va="center", fontsize=6.5, color=INK_2)
    year_axis(ax)
    ax.set_ylim(0, 40)
    pct_axis(ax, [0, 10, 20, 30, 40])
    ax.set_ylabel("Share of civilian net paid ahead")
    grid_y(ax)
    ax.legend(loc="center left", bbox_to_anchor=(0.0, 0.62), ncol=3, fontsize=6.5, handlelength=2.2, borderaxespad=0.1, **MASK)
    finish(fig, "backup/f06_paid_ahead_by_year", "Row dates flag far more money as paid ahead than the whole-contract test",
           "Civilian net flagged. Row test: its own dates span over 18 months. Contract test: over 18 months with 80% of its money in one year.")


# ============================================================================================ How contracts are paid


def f14() -> None:
    rows = read("p8_money_by_action_type")
    groups = (("Original award", BLUE), ("Funding-only actions", ORANGE), ("Option exercises", AQUA), ("All other changes", GRAY))
    shares = {}
    for a, b in ERAS:
        yearly = {g[0]: [] for g in groups}
        for y in range(a, b + 1):
            mine = [r for r in rows if int(r["fiscal_year"]) == y]
            total = sum(f(r["net_proposed_handling"]) for r in mine)
            base = sum(f(r["net_proposed_handling"]) for r in mine if r["row_kind"] == "base row")
            fund = sum(f(r["net_proposed_handling"]) for r in mine if r["row_kind"] == "modification" and r["action_type"] == "FUNDING ONLY ACTION")
            opt = sum(f(r["net_proposed_handling"]) for r in mine if r["row_kind"] == "modification" and r["action_type"] == "EXERCISE AN OPTION")
            for key, v in zip(yearly, (base, fund, opt, total - base - fund - opt)):
                yearly[key].append(100 * v / total)
        shares[(a, b)] = {k: statistics.mean(v) for k, v in yearly.items()}
    fig, ax = plt.subplots(figsize=(FULL_W, 2.4))
    eras = list(shares)
    ys = list(range(len(eras)))[::-1]
    left = [0.0] * len(eras)
    for label, color in groups:
        vals = [shares[e][label] for e in eras]
        ax.barh(ys, vals, 0.62, left=left, color=color, label=label, zorder=3, edgecolor="white", linewidth=0.6)
        for y, l, v in zip(ys, left, vals):
            ax.text(l + v / 2, y, f"{v:.0f}%", ha="center", va="center", fontsize=6.5, color="white" if color == BLUE else INK, zorder=4)
        if color == AQUA:
            ax.text(left[0] + vals[0] / 2, ys[0] + 0.34, label, ha="center", va="bottom", fontsize=6.5, color=INK)
        left = [p + v for p, v in zip(left, vals)]
    ax.set_yticks(ys)
    ax.set_yticklabels([f"FY{a} to FY{b}" for a, b in eras])
    ax.set_ylim(-0.45, 2.72)
    ax.set_xlim(0, 100)
    pct_axis(ax, [0, 25, 50, 75, 100], "x")
    ax.set_xlabel("Share of civilian net, mean of the yearly shares")
    ax.set_ylabel("Code era")
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.17), ncol=4, frameon=False, fontsize=6.5, handlelength=1.0)
    finish(fig, "dropped/f14_money_by_kind", "Later changes carry more money than the original award in every code era",
           "Civilian net as recorded, by kind of contract action.")


def f15() -> None:
    rows = [r for r in read("p8_award_funding_pattern") if r["agency_group"] == "all civilian agencies"]
    fig, ax = plt.subplots(figsize=HALF)
    width = 0.36
    for x, r in enumerate(rows):
        a, n = f(r["awards_pct"]), f(r["net_pct"])
        ax.bar(x - width / 2 - 0.02, a, width, color=ORANGE, zorder=3, label="Share of contracts" if x == 0 else None, **STRIPES)
        ax.bar(x + width / 2 + 0.02, n, width, color=BLUE, zorder=3, label="Share of dollars" if x == 0 else None)
        ax.text(x - width / 2 - 0.02, a + 1.5, f"{a:.0f}%", ha="center", va="bottom", fontsize=6.3, color=INK)
        ax.text(x + width / 2 + 0.02, n + 1.5, f"{n:.0f}%", ha="center", va="bottom", fontsize=6.3, color=INK)
    ax.set_xticks(range(len(rows)))
    ax.set_xticklabels(["Under 20%", "20% to 50%", "50% to 80%", "80% and over"], fontsize=6.5)
    ax.set_xlabel("Share of the contract's net in its original award")
    ax.set_ylim(0, 115)
    pct_axis(ax, [0, 25, 50, 75, 100])
    ax.set_ylabel("Share of the civilian total")
    grid_y(ax)
    ax.legend(loc="upper left", frameon=False, fontsize=6.3, handlelength=1.0)
    finish(fig, "backup/f07_up_front", "Most contracts get their money up front, but most dollars sit on contracts funded later",
           "Civilian contracts with a positive net over all years.")


# ============================================================================================ Codes, firms and markets


def f16() -> None:
    rows = {int(r["fiscal_year"]): r for r in read("p4_it_split_effect")}
    vals = [f(rows[2021][k]) - f(rows[2020][k]) for k in ("share_above_2500_as_recorded_pct", "share_above_2500_it_merged_pct")]
    fig, ax = plt.subplots(figsize=HALF)
    ax.bar([0, 1], vals, 0.5, color=[BLUE, ORANGE], zorder=3)
    for x, v in enumerate(vals):
        ax.text(x, v + 0.1, f"{v:.2f} points", ha="center", va="bottom", fontsize=6.5, color=INK)
    ax.set_xticks([0, 1])
    ax.set_xticklabels([AS_RECORDED, "IT codes grouped back together"], fontsize=6.5)
    ax.set_xlim(-0.6, 1.6)
    ax.set_ylim(0, 5.5)
    ax.set_xlabel("How the IT codes are treated")
    ax.set_ylabel("FY2021 step (points)")
    grid_y(ax)
    finish(fig, "dropped/f16_it_split", "About half of the FY2021 step goes away with the IT codes grouped back together",
           "Rise in the civilian share above HHI 2,500, FY2020 to FY2021.")


def f17() -> None:
    rows = [r for r in read("p11_main_vendor_effect") if re.fullmatch(r"FY\d{4}", r["period"])]
    years = [int(r["period"][2:]) for r in rows]
    vals = [f(r["change_points"]) for r in rows]
    fig, ax = plt.subplots(figsize=(FULL_W, 2.3))
    ax.bar(years, vals, 0.7, color=[BLUE if v >= 3 else GRAY for v in vals], zorder=3)
    ax.axhline(0, color=INK_2, linewidth=0.6, zorder=4)
    for y, v in zip(years, vals):
        if y >= 2024:
            ax.text(y, v + 0.12, f"{v:+.2f}", ha="center", va="bottom", fontsize=6.5, color=INK)
    year_axis(ax)
    ax.set_ylim(-1.5, 7)
    ax.set_ylabel("Change in the share (points)")
    grid_y(ax)
    finish(fig, "dropped/f17_one_firm_by_year", "One firm per contract changes little through FY2023, then adds 5 to 6 points",
           "Civilian share of dollars above HHI 2,500 with each contract under one firm, less the share as recorded.")


def agency_label(code: str) -> str:
    names = {r["agency_code"]: r["name"] for r in read("p3_services_by_agency")}
    return AGENCY_SHORT.get(code, names.get(code, code))


def f18() -> None:
    rows = read("p13_fy2024_one_firm")
    vals = [f(r["change_in_dollars_above_2500"]) / 1e9 for r in rows]
    fig, ax = plt.subplots(figsize=(FULL_W, 2.9))
    ys = list(range(len(rows)))[::-1]
    ax.barh(ys, vals, 0.62, color=[BLUE if r["product_code"] == "M1JZ" else GRAY for r in rows], zorder=3)
    ax.axvline(0, color=INK_2, linewidth=0.6, zorder=4)
    for y, v, r in zip(ys, vals, rows):
        ax.text(v + (0.15 if v >= 0 else -0.15), y, f"{v:+.2f}".replace("-", "−"), va="center", ha="left" if v >= 0 else "right", fontsize=6.5, color=INK)
    ax.set_yticks(ys)
    ax.set_yticklabels([f"{agency_label(r['agency'])} {r['product_code']}" for r in rows], fontsize=6.5)
    ax.set_xlim(-2.5, 19)
    ax.set_xlabel("Change in dollars above HHI 2,500, one firm per contract less as recorded ($ billions)")
    ax.set_ylabel("Market (agency and product code)")
    grid_x(ax)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    finish(fig, "dropped/f18_fy2024_segments", "One Energy market gives almost all of the FY2024 change",
           "The ten civilian markets whose FY2024 dollars above HHI 2,500 change most. Energy M1JZ gives 5.41 of the 5.82 points.")


def f19() -> None:
    rows = read("p2_jv_by_year")
    years = [int(r["fiscal_year"]) for r in rows]
    fig, ax = plt.subplots(figsize=HALF)
    ax.plot(years, [f(r["jv_share_of_civilian_net_pct"]) for r in rows], color=BLUE, linewidth=1.7, label="Civilian")
    ax.plot(years, [f(r["jv_share_of_all_net_pct"]) for r in rows], color=ORANGE, linestyle=DASH, linewidth=1.5, label="All agencies")
    year_axis(ax)
    ax.set_ylim(0, 4)
    pct_axis(ax, [0, 1, 2, 3, 4])
    ax.set_ylabel("Joint ventures' share of net")
    grid_y(ax)
    ax.legend(loc="upper left", bbox_to_anchor=(0.03, 0.98), fontsize=6.5, handlelength=2.2, **MASK)
    finish(fig, "dropped/f19_joint_ventures", "Joint ventures hold a small share of dollars, about 3% by FY2025",
           "Net on rows flagged or named as joint ventures, over each group's net.")


def f20() -> None:
    r = read("p6_leader_summary")[0]
    vals = [f(r["share_of_segments_pct"]), f(r["share_of_segment_dollars_pct"])]
    fig, ax = plt.subplots(figsize=HALF)
    ax.bar([0, 1], vals, 0.5, color=[GRAY, BLUE], zorder=3)
    for x, v in enumerate(vals):
        ax.text(x, v + 1.5, f"{v:.1f}%", ha="center", va="bottom", fontsize=6.5, color=INK)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Count of markets", "Dollars"])
    ax.set_xlim(-0.6, 1.6)
    ax.set_ylim(0, 100)
    pct_axis(ax, [0, 25, 50, 75, 100])
    ax.set_xlabel("Counted by")
    ax.set_ylabel("Share with the same leader")
    grid_y(ax)
    finish(fig, "dropped/f20_leaders", "About one in five one-agency leaders also lead across civilian agencies, and they hold most of the dollars",
           f"FY2025: {int(r['segments']):,} civilian markets above 2,500 led by one firm at 50%+.")


def f21() -> None:
    letters = read("p3_services_by_letter")
    agencies = read("p3_services_by_agency")
    fig, axes = plt.subplots(1, 2, figsize=(FULL_W, 2.75))
    for ax, rows, key, label, namer, ylabel in ((axes[0], letters, "first_letter", "By kind of service", lambda k: SERVICE_LETTERS[k], "Kind of service"),
                                                (axes[1], agencies, "agency_code", "By agency", agency_label, "Agency")):
        top = rows[:6]
        rest = sum(f(r["share_of_services_growth_pct"]) for r in rows[6:])
        labels = [namer(r[key]) for r in top] + ["All others"]
        vals = [f(r["share_of_services_growth_pct"]) for r in top] + [rest]
        ys = list(range(len(vals)))[::-1]
        ax.barh(ys, vals, 0.62, color=[BLUE] * 6 + [DARK], zorder=3)
        for y, v in zip(ys, vals):
            ax.text(v + 0.6, y, f"{v:.0f}%", va="center", fontsize=6.5, color=INK)
        ax.set_yticks(ys)
        ax.set_yticklabels(labels, fontsize=6.5)
        ax.set_xlim(0, 50)
        pct_axis(ax, [0, 10, 20, 30, 40, 50], "x")
        ax.set_xlabel("Share of the growth in civilian services")
        ax.set_ylabel(ylabel)
        ax.set_title(label, color=INK, pad=3, loc="left")
        grid_x(ax)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
    finish(fig, "other/f01_services_growth", "Medical services lead services growth by kind, and Veterans Affairs by agency",
           "Growth in civilian services net from FY2008 to FY2025, as recorded, in current dollars.")


# ============================================================================================ Added figures


def f22() -> None:
    r = read("p13_fy2024_one_firm")[0]
    if r["product_code"] != "M1JZ":
        raise SystemExit("f22: the first row of p13_fy2024_one_firm.csv is not M1JZ")
    pairs = [re.fullmatch(r"\S+ (.+) to YBVGQEYENNM6 HONEYWELL INTERNATIONAL INC: ([\d.]+)", part).groups() for part in r["vendor_ids_row_to_main"].split("; ")]
    vals = [f(v) / 1e9 for _, v in pairs]
    if abs(sum(vals) - f(r["net_moved_between_ids"]) / 1e9) > 0.005:
        raise SystemExit("f22: the IDs do not add up to the money moved")
    names = {"RESIDEO TECHNOLOGIES, INC.": "Resideo Technologies", "HONEYWELL SAFETY PRODUCTS USA, INC.": "Honeywell Safety Products",
             "HONEYWELL FEDERAL MANUFACTURING & TECHNOLOGIES, LLC": "Honeywell Federal Manufacturing",
             "NATIONAL TECHNOLOGY & ENGINEERING SOLUTIONS OF SANDIA, LLC": "Sandia's operator, its own ID"}
    fig, ax = plt.subplots(figsize=(FULL_W, 2.0))
    ys = list(range(len(vals)))[::-1]
    ax.barh(ys, vals, 0.62, color=BLUE, zorder=3)
    for y, v in zip(ys, vals):
        ax.text(v + 0.06, y, f"${v:.2f}B", va="center", fontsize=6.5, color=INK)
    ax.set_yticks(ys)
    ax.set_yticklabels([names[n] for n, _ in pairs], fontsize=6.5)
    ax.set_xlim(0, 7)
    ax.set_xlabel("FY2024 money that moves back under Honeywell International ($ billions)")
    ax.set_ylabel("Name on the rows")
    grid_x(ax)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    finish(fig, "core/f07_honeywell_ids", "One firm's $11.47 billion was scored under four other IDs in FY2024",
           "The Sandia and Kansas City contracts in Energy code M1JZ, by the parent name on the FY2024 rows.")


def f23() -> None:
    fig, ax = plt.subplots(figsize=(FULL_W, 2.5))
    dot_pairs(ax, method_rows("report's lines", "falling_pct"), 50, "Share of 5,772 markets falling by 500 points or more")
    pct_axis(ax, [0, 10, 20, 30, 40], "x")
    finish(fig, "dropped/f23_falling_by_count", "Falling barely beats chance as recorded, and beats it by more once contracts are spread",
           f"{ALL_MARKETS}, including Defense. Each market counts once. The right column gives observed less chance.")


def f24() -> None:
    ten = {r["cutoff"]: r for r in read("p10_pooled_rising") if r["line_set"] == "report's lines" and r["method"] == "averaged"}
    twelve = {r["cutoff"]: r for r in read("p12_rising") if r["line_set"] == "report's lines" and r["rule"] == "S1"}
    fig, axes = plt.subplots(1, 2, figsize=(FULL_W, 1.95), sharey=True)
    for i, (ax, rows, label) in enumerate(((axes[0], ten, AS_RECORDED), (axes[1], twelve, SPREAD))):
        pts = [(f"{int(c):,} points", f(rows[c]["rising_pct"]), f(rows[c]["rising_pct_after_shuffle"])) for c in ("250", "500", "1000")]
        dot_pairs(ax, pts, 60, "Share of 5,772 markets rising by the cutoff", legend=i == 0, ylabel="" if i else "Cutoff (HHI points)")
        pct_axis(ax, [0, 10, 20, 30, 40], "x")
        ax.set_title(label, color=INK, pad=3, loc="left")
    finish(fig, "backup/f08_cutoffs", "The rise beats chance at all three cutoffs, as recorded and spread evenly",
           f"{ALL_MARKETS}, including Defense. The right columns give observed less chance.")


def f25() -> None:
    rows = read("p8_date_checks_by_year")
    fig, ax = plt.subplots(figsize=(FULL_W, 2.4))
    for case, label, color, dash, marker in (("start_or_current_end_blank_or_invalid", "Start or end date blank or invalid", BLUE, "solid", "o"),
                                             ("start_after_current_end", "Start after the end", ORANGE, DASH, "s")):
        pts = [(int(r["fiscal_year"]), f(r["rows_pct"])) for r in rows if r["case"] == case and r["fiscal_year"] != "all"]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=color, linestyle=dash, linewidth=1.6, marker=marker, markersize=3.2, label=label)
    year_axis(ax)
    ax.set_ylim(0, 16)
    pct_axis(ax, [0, 5, 10, 15])
    ax.set_ylabel("Share of civilian rows")
    grid_y(ax)
    ax.legend(loc="upper right", fontsize=6.5, handlelength=2.2, **MASK)
    finish(fig, "backup/f09_date_problems", "About 8% of rows lack a usable start or end date, and rows that start after they end nearly vanish from FY2020",
           "Civilian rows, as recorded. Over all years, 8.03% have a blank or invalid start or end date, and 3.20% start after they end.")


def f26() -> None:
    rows = {r["period"]: r for r in read("p12_share_by_year")}
    years = list(range(2018, 2026))
    fig, ax = plt.subplots(figsize=HALF)
    for key, label, color, dash, marker in (("report", AS_RECORDED, BLUE, "solid", "o"), ("baseline", ONE_FIRM, ORANGE, DASH, "s")):
        ax.plot(years, [f(rows[f"FY{y}"][key]) for y in years], color=color, linestyle=dash, linewidth=1.6, marker=marker, markersize=3.2, label=label)
    year_axis(ax, 2018, 2025, 2)
    ax.set_ylim(35, 60)
    pct_axis(ax, [40, 50, 60])
    ax.set_ylabel("Share above HHI 2,500")
    grid_y(ax)
    ax.legend(loc="lower right", frameon=False, fontsize=6.3, handlelength=2.2, borderaxespad=0.1)
    finish(fig, "core/f06_fy2024_dip", "With each contract under one firm, the FY2024 drop mostly closes",
           "Civilian share. The FY2023 to FY2024 drop: 7.37 points becomes 1.37.")


def f27() -> None:
    rows = [r for r in read("p2_jv_merge_share_above_2500") if r["merges"] == "every match"]
    fig, ax = plt.subplots(figsize=HALF)
    width = 0.36
    labels, x = [], 0
    for r in rows:
        for scope, a, b in (("All agencies", "share_above_2500_all_pct", "share_above_2500_all_merged_pct"), ("Civilian", "share_above_2500_civilian_pct", "share_above_2500_civilian_merged_pct")):
            ax.bar(x - width / 2 - 0.02, f(r[a]), width, color=BLUE, zorder=3, label=AS_RECORDED if x == 0 else None)
            ax.bar(x + width / 2 + 0.02, f(r[b]), width, color=ORANGE, zorder=3, label="Ventures merged" if x == 0 else None)
            labels.append(f"{scope}\nFY{r['fiscal_year']}")
            x += 1
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=6.3)
    ax.set_xlabel("Group and fiscal year")
    ax.set_ylim(0, 70)
    pct_axis(ax, [0, 20, 40, 60])
    ax.set_ylabel("Share above HHI 2,500")
    grid_y(ax)
    ax.legend(loc="upper left", ncol=2, frameon=False, fontsize=6.3, handlelength=1.0, borderaxespad=0.1)
    finish(fig, "dropped/f27_joint_venture_merge", "Merging joint ventures with their member firms barely moves the share",
           "Share of dollars above HHI 2,500. The largest change is 0.10 points.")


# ============================================================================================ Figures 1a and 1b and the merged rising and falling figure

THIRDS = ((2012, 2014), (2015, 2017), (2018, 2020))
ACROSS_AGENCIES = "Each product across all civilian agencies"


def yearly(rows: list[dict], key: str, column: str) -> dict[int, float]:
    """{fiscal year: value} for the rows that are single fiscal years with a value in this column."""
    out = {}
    for r in rows:
        match = re.fullmatch(r"(?:FY)?(\d{4})", r[key])
        if match and r[column]:
            out[int(match.group(1))] = f(r[column])
    return out


def third_means(data: dict[int, float]) -> tuple[float, ...]:
    """The averages of FY2012 to FY2014, FY2015 to FY2017 and FY2018 to FY2020."""
    return tuple(statistics.mean(data[y] for y in range(a, b + 1)) for a, b in THIRDS)


def versions() -> list[tuple]:
    """(name, {year: share}, (three averages)) for each version of the measure in figure 1a. Every number comes from a CSV."""
    twelve, eleven, ten = read("p12_share_by_year"), read("p11_main_vendor_effect"), read("p10_pooled_share_by_year")
    recorded, one_firm = yearly(twelve, "period", "report"), yearly(eleven, "period", "baseline_share_above_2500_pct")
    if one_firm != yearly(twelve, "period", "baseline") or recorded != yearly(ten, "fiscal_year", "yearly_share_above_2500_pct"):
        raise SystemExit("figure 1: the share tables disagree with each other")
    spread = yearly(twelve, "period", "S1")
    pooled = yearly(ten, "fiscal_year", "pooled_share_above_2500_pct")
    return [(AS_RECORDED, recorded, third_means(recorded)), (ONE_FIRM, one_firm, third_means(one_firm)), (SPREAD, spread, third_means(spread)),
            (POOLED, pooled, tuple(pooled[b] for _, b in THIRDS))]   # a pooled score already covers three years, so each bar is the one ending in that period


def runs_of_years(years: list[int]) -> list[list[int]]:
    """Split years into unbroken runs, so a line never joins across a gap in the table."""
    out: list[list[int]] = []
    for y in years:
        if out and y == out[-1][-1] + 1:
            out[-1].append(y)
        else:
            out.append([y])
    return out


def fig1a() -> None:
    fig, axes = plt.subplots(2, 2, figsize=(FULL_W, 4.6), sharey=True)
    all_years = list(range(2008, 2026))
    for ax, (name, data, avgs) in zip(axes.flat, versions()):
        ax.axvspan(2011.5, 2020.5, color=BAND, zorder=0)
        years = sorted(data)
        for part in ([y for y in years if y <= 2012], [y for y in years if y >= 2020]):
            for run in runs_of_years(part):
                if len(run) > 1:
                    ax.plot(run, [data[y] for y in run], color=MOCK_GRAY, linewidth=1.1, linestyle=(0, (3, 2)), zorder=2)
        inside = [y for y in years if 2012 <= y <= 2020]
        ax.plot(inside, [data[y] for y in inside], color=BLUE, linewidth=1.8, marker="o", markersize=2.6, zorder=3)
        for value, (a, b) in zip(avgs, THIRDS):
            ax.hlines(value, a - 0.3, b + 0.3, color=ORANGE, linewidth=2.6, zorder=4)
            ax.text((a + b) / 2, 31.1, f"{value:.0f}%", ha="center", fontsize=8, color=ORANGE, fontweight="bold")
        for start, end in ((2013, 2016), (2016, 2019)):
            ax.annotate("", xy=(end, 31.9), xytext=(start, 31.9), arrowprops={"arrowstyle": "-|>", "color": ORANGE, "linewidth": 0.9, "mutation_scale": 7, "shrinkA": 13, "shrinkB": 13})
        ax.set_title(f"{name}  ({avgs[-1] - avgs[0]:+.1f} points)", loc="left", fontsize=8, fontweight="bold", color=INK, pad=3)
        ax.set_ylim(30, 60)
        ax.set_xlim(2007.5, 2025.5)
        pct_axis(ax, [30, 40, 50, 60])
        ax.set_xticks(all_years)
        ax.set_xticklabels([f"{y % 100:02d}" for y in all_years], fontsize=6.5)
        ax.yaxis.grid(True, color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
    for ax in axes[1]:
        ax.set_xlabel("Fiscal year (FY2008 to FY2025)")
    for ax in axes[:, 0]:
        ax.set_ylabel("Civilian dollars above 2,500")
    finish(fig, "core/f01a_share_by_version_panels", "The civilian share in concentrated markets rose from FY2012 to FY2020 under every version",
           "Blue: FY2012 to FY2020, between the code changes. Gray dashes: other years. Orange bars: each three years' average (last panel: their joint score).")


def fig1b() -> None:
    rows = [(name, avgs) for name, _, avgs in versions()]
    wide = yearly(read("p6_levels_by_year"), "fiscal_year", "share_above_2500_civilian_wide_code_pct")
    rows.append((ACROSS_AGENCIES, third_means(wide)))
    fig, ax = plt.subplots(figsize=(FULL_W, 3.2))
    for i, (_, (first, middle, last)) in enumerate(rows):
        y = len(rows) - 1 - i
        low, high = min(first, middle, last), max(first, middle, last)
        ax.plot([low, high], [y, y], color=LINE_GRAY, linewidth=2.2, zorder=1, solid_capstyle="round")
        ax.plot([first], [y], "o", color=ORANGE, markersize=8, zorder=3, markeredgecolor="white", markeredgewidth=0.7)
        ax.plot([middle], [y], "D", color=INK, markersize=5.5, zorder=4, markeredgecolor="white", markeredgewidth=0.6)
        ax.plot([last], [y], "o", color=BLUE, markersize=8, zorder=3, markeredgecolor="white", markeredgewidth=0.7)
        ax.text(high + 0.7, y, f"{last - first:+.1f} points overall", va="center", fontsize=7.5, color=INK)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(["\n".join(textwrap.wrap(r[0], 28)) for r in rows][::-1])
    ax.set_xlim(20, 54)
    pct_axis(ax, [20, 30, 40, 50], "x")
    ax.xaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("Share of civilian contract dollars above 2,500")
    handles = [Line2D([], [], linestyle="none", marker="o", color=ORANGE, markersize=8, label="FY2012 to FY2014"),
               Line2D([], [], linestyle="none", marker="D", color=INK, markersize=5.5, label="FY2015 to FY2017"),
               Line2D([], [], linestyle="none", marker="o", color=BLUE, markersize=8, label="FY2018 to FY2020")]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.0, 1.0), ncol=3, frameon=False, fontsize=7, handletextpad=0.3, borderaxespad=0.2)
    finish(fig, "core/f01b_rise_by_version", "The rise holds under every version of the measure",
           "Three-year averages, or the joint score for three years scored together: orange first, black middle, blue last.")


def merged_3_23() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(FULL_W, 2.7))
    for i, (ax, field, word) in enumerate(((axes[0], "rising_pct", "Rising"), (axes[1], "falling_pct", "Falling"))):
        dot_pairs(ax, method_rows("report's lines", field), 52, f"Share of 5,772 markets {word.lower()} by 500 points or more", legend=i == 0, ylabel="" if i else "Method")
        pct_axis(ax, [0, 10, 20, 30, 40], "x")
        ax.set_title(f"{word}, by count of markets", color=INK, pad=3, loc="left")
        if i:
            ax.set_yticklabels([])
    finish(fig, "core/f02_rising_and_falling", "Rising beats chance by about 10 markets in 100 under every method, falling by about 2, or 3 to 6 when spread",
           f"{ALL_MARKETS}, including Defense. Each market counts once. The right columns give observed less chance.")


# Set, label, first-round number, file name, drawing function, question, takeaway, source.
FIGURES = [
    ("core", "1a", "1 (redrawn)", "core/f01a_share_by_version_panels", fig1a, "Is the civilian share of concentrated dollars rising?",
     "Between the first and last three-year periods, the share rises by 3.7 points as recorded, 3.7 with one firm per contract, 5.7 spread evenly and 3.3 with three years scored together, whose middle period dips first.",
     "p12_share_by_year.csv, p11_main_vendor_effect.csv, p10_pooled_share_by_year.csv"),
    ("core", "1b", "1 and 2 (redrawn)", "core/f01b_rise_by_version", fig1b, "Does the rise hold under every version, including markets drawn across all civilian agencies?",
     "Every version shown ends higher than it starts, by 3.3 to 5.7 points, though three years scored together falls 0.3 points first, and scoring each product across all civilian agencies lowers the level but still gives a rise of 5.2 points.",
     "p12_share_by_year.csv, p11_main_vendor_effect.csv, p10_pooled_share_by_year.csv, p6_levels_by_year.csv"),
    ("core", "2", "3 and 23", "core/f02_rising_and_falling", merged_3_23, "Do more markets rise, or fall, than chance would explain, counting each market once?",
     "With contracts as recorded, 37.92% of markets rise against 28.2% by chance, and every method keeps a gap of about 9 to 11 points, while falling beats chance by 1.6 to 5.8 points, most once contracts are spread.",
     "p10_pooled_rising.csv, p12_rising.csv"),
    ("core", "3", "8", "core/f03_swings", f08, "Does contract timing drive the swings?",
     "It drives part of them: with each contract under one firm, spreading cuts the median yearly change on civilian markets from 658.2 to 490.2 points and jumps from 39.47% to 32.1% of yearly changes, and spreading only pay-ahead contracts gives about a third of that calming.",
     "p12_swings.csv"),
    ("core", "4", "9", "core/f04_jumps_and_pay_ahead", f09, "Are big jumps tied to money paid ahead?",
     "By count, only a few points more often than quiet years (14.97% against 10.66% by the whole contract), while by dollars the whole-contract gap is wider (17.95% against 6.33%).",
     "p9_jump_summary.csv"),
    ("core", "5", "11", "core/f05_example_contracts", f11, "What does spreading do to one contract?",
     "It evens out a contract's yearly money over the years it ran, most plainly on a contract with a lump of money up front, but the even spread leaves contracts still running after FY2025 where they were recorded.",
     "p11_spread_examples.csv, p11_spread_money_by_year.csv"),
    ("core", "6", "26", "core/f06_fy2024_dip", f26, "Does one firm per contract close the FY2024 dip?",
     "It closes most of the drop from FY2023, which goes from 7.37 points to 1.37, but FY2025 still sits 7 to 8 points above FY2024 either way.",
     "p12_share_by_year.csv"),
    ("core", "7", "22", "core/f07_honeywell_ids", f22, "Which IDs held Honeywell's FY2024 money?",
     "The $11.47 billion sat under four other IDs, $5.62 billion of it under the Resideo-named ID, and the rest under Honeywell-named IDs or the Sandia operator's own ID, and that Energy market alone gives 5.41 of the 5.82 points FY2024 regains.",
     "p13_fy2024_one_firm.csv, p11_main_vendor_effect.csv"),
    ("backup", "1", "4", "backup/f01_rising_by_dollars", f04, "Do more dollars sit in rising markets than chance would explain?",
     "With contracts as recorded, 28.57% of dollars sit in rising markets against 17.41% by chance, and every method keeps a gap of about 10 to 13 points.",
     "p10_pooled_rising.csv, p12_rising.csv"),
    ("backup", "2", "5", "backup/f02_codes_never_changed", f05, "Do markets on codes that never changed rise too?",
     "By count they rise well beyond chance, 51.69% against 30.12% as recorded, but by dollars more sits in falling markets under every method, and as recorded rising does not beat chance (23.84% against 23.20%).",
     "p10_pooled_rising.csv, p12_rising.csv"),
    ("backup", "3", "6", "backup/f03_labels_kept", f06, "Do the same markets rise when contracts are spread?",
     "Mostly yes: 4,277 of the 5,772 markets keep their label, and a quarter change.",
     "p12_line_agreement.csv"),
    ("backup", "4", "10", "backup/f04_jumps_by_size", f10, "In which markets do big jumps happen, and does the moving firm enter or leave?",
     "Of 12,986 civilian jumps, 54% come from a firm in the market both years, 26% from a firm entering and 19% from a firm leaving, and the share from firms staying rises with market size, though the top band holds only 27 jumps.",
     "p9_jumps.csv"),
    ("backup", "5", "12", "backup/f05_money_moved", f12, "How much money does spreading move, and why does the rest stay?",
     "Spreading moves a mean of 27.42% of each year's civilian net over FY2012 to FY2020 and 0.99% in FY2025, where contracts still running hold 70% of the money.",
     "p11_spread_money_by_year.csv"),
    ("backup", "6", "13", "backup/f06_paid_ahead_by_year", f13, "How much money is paid ahead, judged two ways?",
     "Row dates flag about 25% to 33% of civilian net by era, the whole-contract test about 8% to 13%, and both tests flag about 4% to 7%.",
     "p9_paid_ahead_by_year.csv"),
    ("backup", "7", "15", "backup/f07_up_front", f15, "Do contracts get their money up front?",
     "Most do, with 96.21% of contracts getting 80% or more in the original award, but those hold only 31.85% of dollars, and contracts under 50% hold 63.55%.",
     "p8_award_funding_pattern.csv"),
    ("backup", "8", "24", "backup/f08_cutoffs", f24, "Does the rise depend on the 500-point cutoff?",
     "The gap over chance holds at 250, 500 and 1,000 points, as recorded and spread evenly.",
     "p10_pooled_rising.csv, p12_rising.csv"),
    ("backup", "9", "25", "backup/f09_date_problems", f25, "How clean are the contract dates that spreading rests on?",
     "Over all years 8.03% of civilian rows have a blank or invalid start or end date and 3.20% start after they end, which peaks at 13.47% in FY2017 and is near zero from FY2020.",
     "p8_date_checks_by_year.csv"),
    ("other", "1", "21", "other/f01_services_growth", f21, "What drove the growth in civilian services?",
     "Medical services give 26% of the growth and IT and telecom 19%, and Veterans Affairs alone gives 41%.",
     "p3_services_by_letter.csv, p3_services_by_agency.csv"),
]

# First-round number, file name, drawing function, reason.
DROPPED = [
    ("1", "dropped/f01_civilian_share_by_year", f01, "Replaced by the new figures 1a and 1b."),
    ("2", "dropped/f02_markets_drawn_wider", f02, "Replaced by the new figure 1b, which adds a row for each product across all civilian agencies."),
    ("3", "dropped/f03_rising_by_count", f03, "Merged with figure 23 into core figure 2."),
    ("7", "dropped/f07_stable_share", f07, "Background on how much money the stable codes cover, which a sentence can carry."),
    ("14", "dropped/f14_money_by_kind", f14, "Background on how contracts are paid, which the rising question does not need. Redrawn on the same net as the other figures before it was dropped: later changes carry 57.49%, 60.48% and 57.20% of civilian net by era, led by funding-only actions."),
    ("16", "dropped/f16_it_split", f16, "A single pair of numbers, 4.34 and 2.31 points, which a sentence can carry."),
    ("17", "dropped/f17_one_firm_by_year", f17, "Core figures 1a and 6 already show the one-firm effect by year."),
    ("18", "dropped/f18_fy2024_segments", f18, "Core figure 7 and its takeaway carry the Energy market's part in FY2024."),
    ("19", "dropped/f19_joint_ventures", f19, "Joint ventures hold a small share of dollars and do not change the answer."),
    ("20", "dropped/f20_leaders", f20, "A side question about market leaders, which the rising question does not need."),
    ("23", "dropped/f23_falling_by_count", f23, "Merged with figure 3 into core figure 2."),
    ("27", "dropped/f27_joint_venture_merge", f27, "The merge barely moves the share, which a sentence can carry."),
]


def build_pdf(figure_set: str, heading: str) -> None:
    """One page per figure, in order, with the question above and the takeaway below. Each figure carries its own title."""
    with PdfPages(OUT / f"{figure_set}_figures.pdf") as pdf:
        for fig_set, label, _, name, _, question, takeaway, _ in FIGURES:
            if fig_set != figure_set:
                continue
            page = plt.figure(figsize=(8.5, 11))
            page.text(0.09, 0.94, f"{heading} {label}", fontsize=9, color=INK_2, va="top")
            y = 0.915
            for line in textwrap.wrap(question, 80):
                page.text(0.09, y, line, fontsize=11, color=INK, va="top")
                y -= 0.021
            image = mpimg.imread(OUT / f"{name}.png")
            h_in, w_in = image.shape[0] / 220, image.shape[1] / 220
            top = y - 0.012
            ax = page.add_axes((0.09, top - h_in / 11, w_in / 8.5, h_in / 11))
            ax.imshow(image, interpolation="none")
            ax.axis("off")
            y = top - h_in / 11 - 0.02
            for line in textwrap.wrap(takeaway, 92):
                page.text(0.09, y, line, fontsize=9.5, color=INK, va="top")
                y -= 0.019
            pdf.savefig(page)
            plt.close(page)


def build_gallery(titles: dict[str, str]) -> None:
    lines = ["# Figures for the follow-up findings, trimmed set", "",
             "This gallery lists the trimmed set, chosen from the 27 first-round figures. All numbers come from the CSVs in this folder, "
             "and nothing here is a decision. The core set is in `figures/core_figures.pdf` and the backup set in `figures/backup_figures.pdf`.", "",
             "`figures_gallery.md` and `figures/findings_figures.pdf` from the first round are left as they were. The PDF still shows the first set, but the PNG links in that gallery "
             "point at the old paths, because the files have moved to the folders named here.", "",
             "## Figures", "",
             "| Set | New number | First-round number | Question | Takeaway | Source | Figure |", "|---|---|---|---|---|---|---|"]
    for fig_set, label, old, name, _, question, takeaway, source in FIGURES:
        sources = ", ".join(f"`{s}`" for s in source.split(", "))
        lines.append(f"| {fig_set.capitalize()} | {label} | {old} | {question} | {takeaway} | {sources} | [{titles[name]}](figures/{name}.png) |")
    lines += ["", "## Dropped figures", "", "| First-round number | Figure | Reason |", "|---|---|---|"]
    for old, name, _, reason in DROPPED:
        lines.append(f"| {old} | [{titles[name]}](figures/{name}.png) | {reason} |")
    (TABLES / "figures_gallery_v2.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def collect_titles() -> dict[str, str]:
    """Each figure's title, read back from this file so the gallery cannot drift from the figures."""
    source = Path(__file__).read_text(encoding="utf-8")
    return dict(re.findall(r'finish\(fig, "([\w/]+)", "([^"]+)"', source))


def main() -> int:
    setup()
    for entry in FIGURES:
        entry[4]()
    f14()   # redrawn on the same net as the other figures, and kept with the dropped set
    if "--dropped" in sys.argv:
        for _, _, draw, _ in DROPPED:
            draw()
    build_pdf("core", "Figure")
    build_pdf("backup", "Backup figure")
    build_gallery(collect_titles())
    print(f"{len(FIGURES)} figures and the redrawn figure 14 written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
