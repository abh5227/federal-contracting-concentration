"""reports/integrity/integrity_summary.md: the plain-language verdict, then the biggest findings first.

Called by src.integrity_report. Every number comes from the Stage 1 proofs and Stage 2 outputs; the
wording around them is fixed here, so a rerun on new data rewrites the summary consistently.
"""

from __future__ import annotations

from decimal import Decimal

from . import config, stage2
from .integrity_report import REP, SEV_ORDER, money, now


def _share(part, whole) -> str:
    return f"{100 * Decimal(part) / Decimal(whole):.2f}%" if whole else ""


TOP_SHOWN = 10


def largest_transactions(outl: list[dict]) -> list[str]:
    """The largest single rows across all present years (from the J01 lists), and what each one's award nets to across
    all present years. Facts only: an amount followed by its reversal shows up as an award net far below the row."""
    if not outl:
        return []
    top = sorted(outl, key=lambda r: (-abs(Decimal(r["federal_action_obligation"])), r["contract_transaction_unique_key"]))[:TOP_SHOWN]
    L = ["## Largest single transactions, and what their awards net to", "",
         f"The {TOP_SHOWN} largest rows by |amount| across all present years. \"Award net\" sums every row of the same "
         "`contract_award_unique_key` in every present year. When it is far smaller than the row, another row offsets "
         "it. Nothing here is changed or excluded; the full list is `outliers.csv`.", "",
         "| FY | Amount | Action date | Agency / sub-agency | Recipient | PSC | Award (mod) | Award rows | Award net | Award years |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for r in top:
        L.append(f"| {r['fiscal_year']} | {money(r['federal_action_obligation'])} | {r['action_date']} | "
                 f"{r['awarding_agency_name']} / {r['awarding_sub_agency_name']} | {r['recipient_name']} | "
                 f"{r['product_or_service_code']} | `{r['contract_award_unique_key']}` ({r['modification_number']}) | "
                 f"{r['award_rows_present_years']} | {money(r['award_net_present_years'])} | "
                 f"{(r['award_fiscal_years'] or '').replace(';', ', ')} |")
    return L


def write(c, cat: list[dict], yt: list[dict], fc: list[dict], comp: dict, outl: list[dict]) -> None:
    present = [y for y in yt if y["status"] == "present"]
    pending = [y["fiscal_year"] for y in yt if y["status"] != "present"]
    rows = sum(int(y["rows"]) for y in present)
    net = sum(Decimal(y["net"]) for y in present)
    proof_ok = all(y["stage1_proof"] == "PASS" for y in present)
    by_flag: dict[str, dict] = {}
    for r in fc:
        if r.get("count") in ("", None) or r["fiscal_year"] in pending:
            continue
        f = by_flag.setdefault(r["flag_id"], {**{k: r[k] for k in ("flag_id", "name", "severity", "level")},
                                              "count": 0, "unit": r["count_unit"], "gross": Decimal(0), "net": Decimal(0),
                                              "years": []})
        n = int(r["count"])
        f["count"] += n
        f["gross"] += Decimal(r.get("gross_dollars") or 0)
        f["net"] += Decimal(r.get("net_dollars") or 0)
        if n:
            f["years"].append(r["fiscal_year"])
    # B05 is counted per year (an award in three years counts three times); the summary shows distinct awards.
    spanned = stage2.CROSS / "awards_years_spanned.parquet"
    if "B05" in by_flag and spanned.exists():
        by_flag["B05"]["count"] = c.execute(
            f"SELECT COALESCE(SUM(awards), 0) FROM read_parquet('{spanned}') WHERE years_spanned >= 2").fetchone()[0]
        by_flag["B05"]["unit"] = "distinct awards"
    fired = [f for f in by_flag.values() if f["count"]]
    fired.sort(key=lambda f: (SEV_ORDER[f["severity"]], -f["gross"], -f["count"]))
    serious = [f for f in fired if f["severity"] == "serious"]
    gross_all = sum(abs(Decimal(y["positive_only"] or 0)) + abs(Decimal(y["net"]) - Decimal(y["positive_only"] or 0))
                    for y in present)
    ys = comp.get("years", {})
    v2_pass = sum(1 for y in ys.values() if y["v2"] == "PASS")
    v1_pass = sum(1 for y in ys.values() if y["v1"] == "PASS")
    benchmarked = sum(1 for y in ys.values() if y["v2"])

    L = ["# Integrity and completeness: summary", "",
         f"Generated {now()} by `python -m src.integrity_report`, from Stage 1 (the proven mirror) and Stage 2 (flags and "
         "profiles). No row was changed, dropped or fixed. Every finding below is a fact about the data, waiting for a "
         "team decision (`config/decisions.csv`).", "",
         "## Verdict", "",
         (f"We hold {len(present)} of {len(yt)} fiscal years "
          f"({', '.join('FY' + str(fy) for fy in pending) + ' pending, not yet downloaded' if pending else 'none pending'}): "
          f"{rows:,} transaction rows and {money(net)} in net obligations, all from the 2026-09-06 release. "
          + ("Every year's Parquet mirror is verified against its zip: row counts, exact dollars and a full-row checksum match (Stage 1 PASS). " if proof_ok else
             "**Not every year passed the Stage 1 proof.** ")
          + f"Against published totals from GAO and GSA (both drawn from FPDS, so they check our extraction, not FPDS), "
          f"{v2_pass} of {benchmarked} benchmarked years are within 2% with GAO as the primary benchmark "
          f"({v1_pass} of {benchmarked} under the version 1 rule, the worse of GAO and GSA; see `completeness_check.md`). "
          + (f"{len(serious)} serious flag types fired: " + "; ".join(f"{f['name']} ({f['count']:,} {f['unit']})" for f in serious[:6])
             + ". " if serious else "No serious flag fired. ")
          + "The review flags below need a person's judgment; they are ordered by dollars within each severity. "
          "After them come the largest single transactions and what their awards net to."), "",
         "## Biggest findings first", "",
         "Ordered by severity, then by gross dollars affected (|amount| summed over flagged rows), then by count.", "",
         "| Flag | Severity | What | Count | Gross $ affected | Share of gross $ | Years affected |",
         "|---|---|---|---|---|---|---|"]
    for f in fired:
        yrs = f["years"]
        span = ("all present years (cross-year)" if "(all years)" in f["unit"]
                else f"{len(yrs)} ({min(yrs)}-{max(yrs)})" if yrs else "")
        L.append(f"| {f['flag_id']} | {f['severity']} | {f['name']} | {f['count']:,} {f['unit']} | "
                 f"{money(f['gross']) if f['gross'] else ''} | {_share(f['gross'], gross_all) if f['gross'] else ''} | {span} |")
    quiet = sorted(f["flag_id"] for f in by_flag.values() if not f["count"])
    L += ["", f"Flags with no hits in any present year: {', '.join(quiet) or 'none'}.", ""]
    L += largest_transactions(outl)
    L += ["",
          "## By year", "",
          "| FY | Status | Rows | Net obligations | Stage 1 proof | IDV rows | IDV net | Agencies | Sub-agencies |",
          "|---|---|---|---|---|---|---|---|---|"]
    for y in yt:
        if y["status"] != "present":
            L.append(f"| {y['fiscal_year']} | pending - not yet downloaded | | | | | | | |")
            continue
        L.append(f"| {y['fiscal_year']} | present | {int(y['rows']):,} | {money(y['net'])} | {y['stage1_proof']} | "
                 f"{int(y['idv_rows']):,} | {money(y['idv_net'])} | {y['agencies']} | {y['subagencies']} |")
    if 2015 in pending:
        L += ["", "**The FY2015 row-count jump.** FY2015 is when small purchases first appear in large numbers. It can't be "
              "measured until FY2015 is added: FY2014 and FY2016 are both present, but the year in between is not."]
    else:
        by_fy = {int(y["fiscal_year"]): y for y in present}
        if all(fy in by_fy for fy in (2014, 2015, 2016)):
            def change(a, b):
                ra, rb = int(by_fy[a]["rows"]), int(by_fy[b]["rows"])
                na, nb = Decimal(by_fy[a]["net"]), Decimal(by_fy[b]["net"])
                return f"{rb - ra:+,} rows ({100 * (rb - ra) / ra:+.1f}%), net obligations {100 * (nb - na) / na:+.1f}%"
            L += ["", f"**The FY2015 row-count jump.** FY2014 to FY2015: {change(2014, 2015)}. FY2015 to FY2016: "
                  f"{change(2015, 2016)}. See `docs/integrity_findings.md` for what the new rows are."]
    L += ["", "## Where to look next", "",
          "- `completeness_check.md`: our totals against published figures, with citations.",
          "- `flag_counts.csv`: every flag by year (rows or items, and dollars).",
          "- `column_quality.csv`: blank, zero and placeholder shares for all 297 columns by year.",
          "- `outliers.csv`: every J01 (top 100 per year) and J02 ($1 billion or more) row, with what its award nets to. "
          "The full J01-J04 lists (millions of rows) are in `data/integrity/summary/outliers_all.parquet` and on the "
          "dashboard. Every outlier stays in the data.",
          "- `stage1_mirror_proof.md`: the row-by-row proof.",
          ] + ([f"- {stage2.PENDING_NOTE}"] if pending else [])
    (REP / "integrity_summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")
