"""Descriptive analyses behind version 2 of the integrity report (docs/integrity_findings_v2.md).

    python -m src.analyses_v2                 # every analysis
    python -m src.analyses_v2 negative_vendors parent_tests   # only the named ones

Each rule and threshold is written in RULES below before the analysis runs, and the report's appendix
quotes them. Nothing here cleans, drops or changes data: every number is a count or a sum over the
Stage 1 mirror (Layer A, text as published) and Stage 2 row flags. Outputs are small summaries in
reports/integrity/v2/ (committed), one CSV per table plus headline.json.
"""

from __future__ import annotations

import csv
import json
import sys
from decimal import Decimal
from pathlib import Path

import duckdb

from . import config, stage1, stage2

OUT = config.INTEGRITY_REPORTS_DIR / "v2"
AMT = "TRY_CAST(NULLIF(federal_action_obligation, '') AS DECIMAL(38,6))"
VENDOR = ("COALESCE(NULLIF(trim(recipient_parent_uei), ''), NULLIF(trim(recipient_uei), ''), '(no ID)')")
MFA = "upper(trim(recipient_name)) = 'MISCELLANEOUS FOREIGN AWARDEES'"

# The five reversal pairs named in the report: four inside one fiscal year, and the Emerson pair across FY2008/FY2009.
PAIRS = {
    "FY2013 Army W912GB09C0090": ["9700_-NONE-_W912GB09C0090_P00006_-NONE-_0", "9700_-NONE-_W912GB09C0090_P00007_-NONE-_0"],
    "FY2009 Army W912ER04D0004 order 0021": ["9700_9700_0021_13_W912ER04D0004_0", "9700_9700_0021_14_W912ER04D0004_0"],
    "FY2015 Army W912DR12C0019": ["9700_-NONE-_W912DR12C0019_P00008_-NONE-_0", "9700_-NONE-_W912DR12C0019_P00009_-NONE-_0"],
    "FY2020 Navy N0001914C0002": ["9700_-NONE-_N0001914C0002_P00081_-NONE-_16", "9700_-NONE-_N0001914C0002_P00082_-NONE-_16"],
    "Emerson, Army W912QR08C0053 (FY2008 entry, FY2009 reversal)": ["9700_-NONE-_W912QR08C0053_0_-NONE-_0",
                                                                    "9700_-NONE-_W912QR08C0053_P00001_-NONE-_0"],
}
PAIR_KEYS = [k for ks in PAIRS.values() for k in ks]
MINT_KEYS = ["2044_-NONE-_TMHQ10C0040_0_-NONE-_-NONE-", "2044_-NONE-_TMHQ10C0044_0_-NONE-_-NONE-"]

# Amount bands for row-count breakdowns (federal_action_obligation of the row). Fixed before running.
BANDS = [("negative", "amt < 0"), ("zero", "amt = 0"), ("under $3,000", "amt > 0 AND amt < 3000"),
         ("$3,000 to under $3,500", "amt >= 3000 AND amt < 3500"), ("$3,500 to under $10,000", "amt >= 3500 AND amt < 10000"),
         ("$10,000 to under $250,000", "amt >= 10000 AND amt < 250000"), ("$250,000 and over", "amt >= 250000"),
         ("unparseable", "amt IS NULL")]

# Parent-ID tests: involved parent IDs (found by name in the data, before the month-by-month counts were run).
PARENT_TESTS = {
    "raytheon_2020": {"title": "Raytheon Company into Raytheon Technologies (RTX)", "window": ("2019-10", "2021-09"),
                      "before": "KLW3ZYL15493", "after": "PPLZG8J3N9D4", "event_month": "2020-04", "closing": "2020-04-03",
                      "units": "upper(trim(recipient_name)) = 'RAYTHEON COMPANY'"},
    "saic_2013": {"title": "SAIC splits into Leidos and a new SAIC", "window": ("2012-10", "2015-09"),
                  "before": "ZL41ERXMPAR3", "after": "RE7WMNV9L719", "event_month": "2013-09", "closing": "2013-09-27",
                  "units": "recipient_parent_uei = 'RE7WMNV9L719'"},
    "sikorsky_2015": {"title": "Lockheed Martin buys Sikorsky from United Technologies", "window": ("2014-10", "2017-09"),
                      "before": "PPLZG8J3N9D4", "after": "ZFN2JJXBLZT3", "event_month": "2015-11", "closing": "2015-11-06",
                      "units": "upper(recipient_name) LIKE '%SIKORSKY%'"},
    "l3harris_2019": {"title": "L3 Technologies and Harris merge into L3Harris", "window": ("2018-10", "2021-09"),
                      "before": "XXP4PLFFFGK9", "after": "SJULQDJ8NZU7", "event_month": "2019-06", "closing": "2019-06-29",
                      "units": "(upper(trim(recipient_name)) LIKE 'L3 %' OR upper(trim(recipient_name)) LIKE 'L-3 %')"},
}

RULES = {
    "cell": "A cell is the awarding agency code as recorded (3 characters, or 4 for agencies identified by a FREC code) "
            "x product or service code (PSC) x fiscal year. A blank PSC is its own value.",
    "vendor": "A vendor is recipient_parent_uei, or recipient_uei when the parent is blank. Rows with both blank form "
              "one vendor, '(no ID)'.",
    "negative_vendors": "A vendor-cell is negative when the sum of federal_action_obligation over its rows is below zero. "
                        "Counted by fiscal year: cells, vendor-cells, negative vendor-cells, the summed net of negative "
                        "vendor-cells, and cells holding at least one negative vendor-cell. Variants: full PSC, PSC cut to "
                        "its first 2 characters, and full PSC with the ten rows of the five reversal pairs removed "
                        "(diagnostic only). Deobligation-flag attribution: for each negative vendor-cell, the net of its rows "
                        "flagged 'deobligation larger than the award's obligations that year'; the vendor-cell counts as "
                        "explained by those rows when removing them leaves a net of zero or more.",
    "hhi": "For illustration only: HHI = 10,000 x the sum of squared shares, where a share is a vendor's net divided by "
           "the summed net of vendors with a positive net in the cell. Vendors with a net of zero or less get no share.",
    "figure1_diagnostic": "Diagnostic line, not the data: FY2008 net minus the Emerson entry plus the Emerson pair's net; "
                          "FY2009 net minus the Emerson reversal; FY2010 net minus the two $10,000,000,000 US Mint rows. "
                          "Every other year as recorded.",
    "bands": "Amount bands by federal_action_obligation: " + "; ".join(b for b, _ in BANDS) + ".",
    "row_jumps": "Row-count differences between two fiscal years, broken down by awarding agency and sub-agency, by "
                 "order type (award type code, or 'IDV ' + IDV type for contract vehicles), and by amount band. Late "
                 "reporting means initial_report_date (as a UTC date) more than 90 days after action_date.",
    "mfa_cells": "Rows whose recipient_name (trimmed, upper case) is MISCELLANEOUS FOREIGN AWARDEES. For each cell with a "
                 "positive net, the share is their net divided by the cell's net. Reported: cells where the share is "
                 "above 10%, as a count and the top 20 by their dollars.",
    "dual_codes": "An agency name (trimmed, upper case) that appears with at least one 3-character code and at least one "
                  "4-character code in the same column pair (awarding_agency_code with awarding_agency_name, or "
                  "funding_agency_code with funding_agency_name) across FY2008 to FY2025. Reported with rows and net "
                  "dollars for each code.",
    "parent_tests": "Population: the units that changed hands, as every row in the window of each recipient_uei that "
                    "matches the unit rule at least once in that window. Raytheon, Sikorsky and L3 units are found by "
                    "recipient name (RAYTHEON COMPANY, as in version 1; any name containing SIKORSKY; names starting L3 or "
                    "L-3). Spun-off SAIC units are found by the new SAIC parent ID, because old and new SAIC share one "
                    "name. Corrected after a first run, whose population (any unit carrying either parent ID) mixed in "
                    "units of United Technologies and Harris that never changed hands, because those parents' IDs carried "
                    "over to RTX and L3Harris. Counted: rows per month by the parent ID recorded on the row "
                    "(before, after, other or blank). Switch month: the first month in which rows carrying the after ID "
                    "outnumber rows carrying the before ID. Anachronistic rows: rows carrying the after ID more than one "
                    "month before the event month.",
    "early_rows": "Rows carrying the new parent ID dated before the closing date in the SEC filing, and more than 30 days "
                  "before it.",
    "display_names": "Display name of a parent ID in a year: the most common recipient_parent_name_raw on rows carrying "
                     "that ID in that year.",
    "funding_999": "Rows whose funding_agency_code is 999, counted with their net dollars by fiscal year.",
    "mint_children": "Rows whose parent_award_id_piid is TMHQ10C0040 or TMHQ10C0044 (orders placed under the two US Mint "
                     "contract vehicles), counted with their net dollars by fiscal year and vehicle.",
}


# ============================================================================================ helpers


def con() -> duckdb.DuckDBPyConnection:
    c = duckdb.connect()
    c.execute("SET TimeZone = 'UTC'")
    c.execute(f"SET temp_directory = '{config.SCRATCH_DIR / 'duckdb_v2'}'")
    c.execute("SET memory_limit = '8GB'")
    return c


def files(fy: int) -> list[str]:
    return [str(p) for p in stage1.layer_a_files(fy)]


def years() -> list[int]:
    return stage2.present_years()


def write(name: str, rows: list[dict]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if not rows:
        (OUT / f"{name}.csv").write_text("", encoding="utf-8")
        return
    with open(OUT / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows([{k: (str(v) if isinstance(v, Decimal) else v) for k, v in r.items()} for r in rows])


def d(x) -> Decimal:
    return Decimal(x) if x is not None else Decimal(0)


HEADLINE: dict = {}


# ============================================================================================ analyses


def negative_vendors() -> None:
    c = con()
    out = []
    pairs = "[" + ", ".join(f"'{k}'" for k in PAIR_KEYS) + "]"
    for fy in years():
        c.execute(f"""CREATE OR REPLACE TEMP TABLE r AS SELECT contract_transaction_unique_key AS k, awarding_agency_code AS ag,
                      product_or_service_code AS psc, {VENDOR} AS v, {AMT} AS amt FROM read_parquet({files(fy)!r})""")
        c.execute(f"""CREATE OR REPLACE TEMP TABLE j AS SELECT DISTINCT contract_transaction_unique_key AS k
                      FROM read_parquet('{config.INTEGRITY_DIR / "row_flags" / f"fy{fy}.parquet"}') WHERE flag_id = 'J03'""")
        for variant, psc, where in (("full PSC", "psc", "TRUE"), ("PSC first 2 characters", "left(psc, 2)", "TRUE"),
                                    ("full PSC, five reversal pairs removed", "psc", f"NOT list_contains({pairs}, k)")):
            res = c.execute(f"""
                WITH vc AS (SELECT ag, {psc} AS p, v, SUM(amt) AS net, SUM(amt) FILTER (WHERE j.k IS NOT NULL) AS jnet,
                                   COUNT(j.k) AS jrows
                            FROM r LEFT JOIN j USING (k) WHERE {where} GROUP BY ALL)
                SELECT COUNT(DISTINCT (ag, p)), COUNT(*), COUNT(*) FILTER (WHERE net < 0), SUM(net) FILTER (WHERE net < 0),
                       COUNT(DISTINCT (ag, p)) FILTER (WHERE net < 0),
                       COUNT(*) FILTER (WHERE net < 0 AND jrows > 0), SUM(jnet) FILTER (WHERE net < 0),
                       COUNT(*) FILTER (WHERE net < 0 AND net - COALESCE(jnet, 0) >= 0),
                       SUM(net) FILTER (WHERE net > 0) FROM vc""").fetchone()
            out.append({"fiscal_year": fy, "variant": variant, "cells": res[0], "vendor_cells": res[1],
                        "negative_vendor_cells": res[2], "negative_dollars": d(res[3]).quantize(Decimal("0.01")),
                        "cells_with_a_negative_vendor": res[4], "negative_vendor_cells_with_deobligation_flag_rows": res[5],
                        "deobligation_flag_net_in_negative_vendor_cells": d(res[6]).quantize(Decimal("0.01")),
                        "negative_vendor_cells_explained_by_those_rows": res[7],
                        "positive_vendor_cell_dollars": d(res[8]).quantize(Decimal("0.01"))})
        print(f"negative_vendors: FY{fy} done", flush=True)
    write("negative_vendor_totals", out)


def figure1_diagnostic() -> None:
    c = con()
    yt = {int(r["fiscal_year"]): r for r in csv.DictReader(open(config.INTEGRITY_REPORTS_DIR / "years.csv", encoding="utf-8"))}
    amounts = {}
    for fy in (2008, 2009, 2010):
        for k, a in c.execute(f"SELECT contract_transaction_unique_key, {AMT} FROM read_parquet({files(fy)!r}) "
                              f"WHERE list_contains({PAIR_KEYS + MINT_KEYS!r}, contract_transaction_unique_key)").fetchall():
            amounts[k] = Decimal(a)
    e_in, e_out = amounts[PAIRS[list(PAIRS)[-1]][0]], amounts[PAIRS[list(PAIRS)[-1]][1]]
    mint = sum(amounts[k] for k in MINT_KEYS)
    out = []
    for fy in sorted(yt):
        net = Decimal(yt[fy]["net"])
        adj, note = net, ""
        if fy == 2008:
            adj, note = net - e_in + (e_in + e_out), f"Emerson entry {e_in} replaced by the pair's net {e_in + e_out}"
        elif fy == 2009:
            adj, note = net - e_out, f"Emerson reversal {e_out} removed"
        elif fy == 2010:
            adj, note = net - mint, f"two US Mint rows totaling {mint} removed"
        out.append({"fiscal_year": fy, "net": net, "diagnostic_net": adj, "note": note})
    write("figure1_diagnostic", out)
    g = {r["fiscal_year"]: r for r in out}
    HEADLINE["figure1"] = {"fy2008_net": str(g[2008]["net"]), "fy2009_net": str(g[2009]["net"]), "fy2010_net": str(g[2010]["net"]),
                           "fy2008_diag": str(g[2008]["diagnostic_net"]), "fy2009_diag": str(g[2009]["diagnostic_net"]),
                           "fy2010_diag": str(g[2010]["diagnostic_net"]), "emerson_entry": str(e_in), "emerson_reversal": str(e_out),
                           "emerson_pair_net": str(e_in + e_out), "mint_total": str(mint),
                           "fy2009_vs_2008_recorded_pct": str(((g[2009]["net"] / g[2008]["net"]) - 1) * 100),
                           "fy2009_vs_2008_diag_pct": str(((g[2009]["diagnostic_net"] / g[2008]["diagnostic_net"]) - 1) * 100)}


def hhi(nets: list[Decimal]) -> Decimal:
    pos = [n for n in nets if n > 0]
    tot = sum(pos)
    return sum((n / tot) ** 2 for n in pos) * 10000 if tot else Decimal(0)


def pair_cells() -> None:
    """The cells holding each reversal pair: the vendor's net, the cell's net and HHI, with and without the pair."""
    c = con()
    out = []
    for name, keys in PAIRS.items():
        rows = []
        for fy in years():
            rows += [(fy, *r) for r in c.execute(
                f"""SELECT contract_transaction_unique_key, awarding_agency_code, awarding_agency_name, product_or_service_code,
                           {VENDOR}, recipient_name, {AMT}, total_dollars_obligated FROM read_parquet({files(fy)!r})
                    WHERE list_contains({keys!r}, contract_transaction_unique_key)""").fetchall()]
        for fy, k, ag, agn, psc, v, rn, a, tdo in rows:
            cell = c.execute(f"""SELECT {VENDOR} AS v, SUM({AMT}) AS net, SUM({AMT}) FILTER (WHERE NOT list_contains({keys!r}, contract_transaction_unique_key)) AS net_wo
                                 FROM read_parquet({files(fy)!r}) WHERE awarding_agency_code = ? AND product_or_service_code = ? GROUP BY 1""",
                             [ag, psc]).fetchall()
            nets = [d(n) for _, n, _ in cell]
            nets_wo = [d(n) for _, _, n in cell]
            vn = next((d(n) for vv, n, _ in cell if vv == v), Decimal(0))
            vn_wo = next((d(n) for vv, _, n in cell if vv == v), Decimal(0))
            out.append({"pair": name, "fiscal_year": fy, "transaction_key": k, "amount": d(a), "agency_code": ag, "agency": agn,
                        "psc": psc, "vendor": v, "recipient_name": rn, "award_total_dollars_obligated": tdo,
                        "vendors_in_cell": len(cell), "cell_net": sum(nets), "cell_net_without_pair": sum(nets_wo),
                        "vendor_net": vn, "vendor_net_without_pair": vn_wo,
                        "cell_hhi": hhi(nets).quantize(Decimal("0.1")), "cell_hhi_without_pair": hhi(nets_wo).quantize(Decimal("0.1"))})
    write("reversal_pair_cells", out)


def pairs_leftover() -> None:
    c = con()
    out = []
    for name, keys in PAIRS.items():
        amts, award = [], None
        for fy in years():
            for k, a, aw in c.execute(f"""SELECT contract_transaction_unique_key, {AMT}, contract_award_unique_key FROM read_parquet({files(fy)!r})
                                         WHERE list_contains({keys!r}, contract_transaction_unique_key)""").fetchall():
                amts.append(d(a))
                award = aw
        tdo, net, n = None, Decimal(0), 0
        for fy in years():
            r = c.execute(f"""SELECT COUNT(*), SUM({AMT}), arg_max(total_dollars_obligated, action_date) FROM read_parquet({files(fy)!r})
                             WHERE contract_award_unique_key = ?""", [award]).fetchone()
            if r[0]:
                n += r[0]
                net += d(r[1])
                tdo = r[2] or tdo
        out.append({"pair": name, "award": award, "entry": max(amts), "reversal": min(amts), "pair_net": sum(amts),
                    "award_rows_all_years": n, "award_net_all_years": net, "award_total_dollars_obligated_latest": tdo})
    write("reversal_pair_leftovers", out)


def amount_bands() -> None:
    c = con()
    out = []
    for fy in years():
        c.execute(f"CREATE OR REPLACE TEMP TABLE r AS SELECT {AMT} AS amt FROM read_parquet({files(fy)!r})")
        tot_n, tot_net = c.execute("SELECT COUNT(*), SUM(amt) FROM r").fetchone()
        for band, cond in BANDS:
            n, net = c.execute(f"SELECT COUNT(*), SUM(amt) FROM r WHERE {cond}").fetchone()
            out.append({"fiscal_year": fy, "band": band, "rows": n, "net": d(net).quantize(Decimal("0.01")),
                        "share_of_rows_pct": (Decimal(n) * 100 / tot_n).quantize(Decimal("0.01")),
                        "share_of_net_pct": (d(net) * 100 / d(tot_net)).quantize(Decimal("0.001"))})
    write("amount_bands", out)


def row_jumps() -> None:
    c = con()
    typ = "CASE WHEN award_or_idv_flag = 'IDV' THEN 'IDV ' || idv_type_code ELSE award_type_code END"
    band = "CASE " + " ".join(f"WHEN {cond} THEN '{b}'" for b, cond in BANDS) + " END"
    late = "(CAST(TRY_CAST(NULLIF(initial_report_date, '') AS TIMESTAMPTZ) AS DATE) - TRY_CAST(action_date AS DATE)) > 90"
    for a, b in ((2014, 2015), (2018, 2019), (2009, 2008)):
        tables = {}
        for fy in (a, b):
            c.execute(f"""CREATE OR REPLACE TEMP TABLE y{fy} AS SELECT awarding_agency_name AS agency, awarding_sub_agency_name AS sub,
                          {typ} AS typ, amt, {band} AS band, {late} AS late
                          FROM (SELECT *, {AMT} AS amt FROM read_parquet({files(fy)!r}))""")
        for dim, expr in (("subagency", "agency || ' / ' || sub"), ("type", "typ"), ("band", "band"),
                          ("subagency_band", "agency || ' / ' || sub || ' | ' || band")):
            res = c.execute(f"""WITH x AS (SELECT {expr} AS g, COUNT(*) AS n, COUNT(*) FILTER (WHERE late) AS late_n FROM y{a} GROUP BY 1),
                                     y AS (SELECT {expr} AS g, COUNT(*) AS n, COUNT(*) FILTER (WHERE late) AS late_n FROM y{b} GROUP BY 1)
                                SELECT COALESCE(x.g, y.g), COALESCE(x.n, 0), COALESCE(y.n, 0), COALESCE(y.n, 0) - COALESCE(x.n, 0),
                                       COALESCE(x.late_n, 0), COALESCE(y.late_n, 0)
                                FROM x FULL JOIN y ON x.g = y.g ORDER BY abs(COALESCE(y.n, 0) - COALESCE(x.n, 0)) DESC""").fetchall()
            tables[dim] = [{"group": g or "(blank)", f"rows_fy{a}": na, f"rows_fy{b}": nb, "difference": diff,
                            f"late_fy{a}": la, f"late_fy{b}": lb} for g, na, nb, diff, la, lb in res]
            write(f"row_jump_fy{a}_to_fy{b}_by_{dim}", tables[dim][:200])
        print(f"row_jumps: FY{a} to FY{b} done", flush=True)


def mfa_cells() -> None:
    c = con()
    out, by_year, vendors = [], [], set()
    for fy in years():
        res = c.execute(f"""WITH r AS (SELECT awarding_agency_code AS ag, awarding_agency_name AS agn, product_or_service_code AS psc,
                                              {AMT} AS amt, {MFA} AS m, {VENDOR} AS v FROM read_parquet({files(fy)!r})),
                             cell AS (SELECT ag, any_value(agn) AS agn, psc, SUM(amt) AS net, SUM(amt) FILTER (WHERE m) AS mnet,
                                             COUNT(*) FILTER (WHERE m) AS mrows FROM r GROUP BY ag, psc)
                        SELECT ag, agn, psc, net, mnet, mrows FROM cell WHERE mrows > 0""").fetchall()
        vendors |= {v for (v,) in c.execute(f"SELECT DISTINCT {VENDOR} FROM read_parquet({files(fy)!r}) WHERE {MFA}").fetchall()}
        tot = c.execute(f"SELECT SUM({AMT}), SUM({AMT}) FILTER (WHERE {MFA}), COUNT(*) FILTER (WHERE {MFA}) FROM read_parquet({files(fy)!r})").fetchone()
        by_year.append({"fiscal_year": fy, "rows": tot[2], "net": d(tot[1]).quantize(Decimal("0.01")),
                        "share_of_year_net_pct": (d(tot[1]) * 100 / d(tot[0])).quantize(Decimal("0.001")),
                        "cells_with_mfa": len(res),
                        "cells_over_10pct": sum(1 for _, _, _, net, mnet, _ in res if d(net) > 0 and d(mnet) / d(net) > Decimal("0.10"))})
        for ag, agn, psc, net, mnet, mrows in res:
            if d(net) > 0 and d(mnet) / d(net) > Decimal("0.10"):
                out.append({"fiscal_year": fy, "agency_code": ag, "agency": agn, "psc": psc, "cell_net": d(net).quantize(Decimal("0.01")),
                            "mfa_net": d(mnet).quantize(Decimal("0.01")), "mfa_rows": mrows,
                            "mfa_share_pct": (d(mnet) * 100 / d(net)).quantize(Decimal("0.1"))})
    out.sort(key=lambda r: -r["mfa_net"])
    write("mfa_cells_over_10pct", out)
    write("mfa_by_year", by_year)
    HEADLINE["mfa"] = {"cells_over_10pct": len(out), "vendor_ids": sorted(vendors)[:20], "vendor_id_count": len(vendors),
                       "dollars_in_those_cells": str(sum(r["mfa_net"] for r in out))}


def dual_codes() -> None:
    c = con()
    out = []
    for col in ("awarding", "funding"):
        parts = " UNION ALL ".join(
            f"SELECT {fy} AS fy, upper(trim({col}_agency_name)) AS name, {col}_agency_code AS code, {AMT} AS amt FROM read_parquet({files(fy)!r})"
            for fy in years())
        res = c.execute(f"""WITH r AS ({parts}), g AS (SELECT name, code, COUNT(*) AS n, SUM(amt) AS net, MIN(fy) AS fy0, MAX(fy) AS fy1
                                                     FROM r WHERE name <> '' AND code <> '' GROUP BY 1, 2),
                               dual AS (SELECT name FROM g GROUP BY 1 HAVING COUNT(*) FILTER (WHERE length(code) = 3) > 0
                                                                         AND COUNT(*) FILTER (WHERE length(code) = 4) > 0)
                            SELECT g.* FROM g JOIN dual USING (name) ORDER BY name, code""").fetchall()
        out += [{"column": col, "agency_name": name, "code": code, "rows": n, "net": d(net).quantize(Decimal("0.01")),
                 "first_fy": fy0, "last_fy": fy1} for name, code, n, net, fy0, fy1 in res]
        four = c.execute(f"""WITH r AS ({parts}) SELECT code, mode(name), COUNT(*), SUM(amt), MIN(fy), MAX(fy) FROM r
                             WHERE length(code) = 4 GROUP BY 1 ORDER BY 3 DESC""").fetchall()
        write(f"four_character_codes_{col}", [{"code": cd, "agency_name": nm, "rows": n, "net": d(net).quantize(Decimal("0.01")),
                                               "first_fy": a, "last_fy": b} for cd, nm, n, net, a, b in four])
    write("dual_code_agencies", out)


def funding_999() -> None:
    c = con()
    out = []
    for fy in years():
        n, net, blank_name = c.execute(f"""SELECT COUNT(*), SUM({AMT}), COUNT(*) FILTER (WHERE trim(funding_agency_name) = '')
                                          FROM read_parquet({files(fy)!r}) WHERE funding_agency_code = '999'""").fetchone()
        tot = c.execute(f"SELECT COUNT(*), SUM({AMT}) FROM read_parquet({files(fy)!r})").fetchone()
        out.append({"fiscal_year": fy, "rows": n, "rows_with_blank_name": blank_name, "net": d(net).quantize(Decimal("0.01")),
                    "share_of_rows_pct": (Decimal(n) * 100 / tot[0]).quantize(Decimal("0.01")),
                    "share_of_net_pct": (d(net) * 100 / d(tot[1])).quantize(Decimal("0.01"))})
    write("funding_agency_999", out)


def mint_children() -> None:
    c = con()
    out = []
    for fy in years():
        for piid, n, net in c.execute(f"""SELECT parent_award_id_piid, COUNT(*), SUM({AMT}) FROM read_parquet({files(fy)!r})
                                         WHERE parent_award_id_piid IN ('TMHQ10C0040', 'TMHQ10C0044') GROUP BY 1 ORDER BY 1""").fetchall():
            out.append({"fiscal_year": fy, "vehicle": piid, "orders_rows": n, "net": d(net).quantize(Decimal("0.01"))})
    write("mint_vehicle_orders", out)


def parent_tests() -> None:
    c = con()
    for name, t in PARENT_TESTS.items():
        lo, hi = t["window"]
        fys = [fy for fy in years() if f"{fy - 1}-10" <= hi and f"{fy}-09" >= lo]
        parts = " UNION ALL ".join(
            f"""SELECT {fy} AS fy, left(action_date, 7) AS month, recipient_uei AS ru, recipient_parent_uei AS pu,
                       upper(trim(recipient_parent_name_raw)) AS raw, recipient_parent_name AS derived, recipient_name,
                       recipient_parent_uei, action_date FROM read_parquet({files(fy)!r})"""
            for fy in fys)
        c.execute(f"CREATE OR REPLACE TEMP TABLE w AS SELECT * FROM ({parts}) WHERE month BETWEEN '{lo}' AND '{hi}'")
        c.execute(f"CREATE OR REPLACE TEMP TABLE pop AS SELECT * FROM w WHERE ru IN (SELECT DISTINCT ru FROM w WHERE {t['units']})")
        months = c.execute(f"""SELECT month, COUNT(*) FILTER (WHERE pu = '{t["before"]}'), COUNT(*) FILTER (WHERE pu = '{t["after"]}'),
                                      COUNT(*) FILTER (WHERE pu NOT IN ('{t["before"]}', '{t["after"]}') OR pu IS NULL OR pu = '')
                               FROM pop GROUP BY 1 ORDER BY 1""").fetchall()
        write(f"parent_test_{name}_by_month", [{"month": m, "before_id_rows": b, "after_id_rows": a, "other_or_blank_rows": o}
                                              for m, b, a, o in months])
        names = c.execute("""SELECT fy, pu, mode(raw) AS display_name, mode(derived) AS derived_name, COUNT(*) AS rows
                             FROM pop WHERE pu <> '' GROUP BY 1, 2 HAVING COUNT(*) >= 20 ORDER BY 1, rows DESC""").fetchall()
        write(f"parent_test_{name}_names", [{"fiscal_year": fy, "parent_uei": pu, "most_common_raw_name": dn, "derived_name": dv,
                                             "rows": n} for fy, pu, dn, dv, n in names])
        switch = next((m for m, b, a, _ in months if a > b), None)
        early_after = sum(a for m, _, a, _ in months if m < t["event_month"] and _months_between(m, t["event_month"]) > 1)
        recipients = c.execute("SELECT COUNT(DISTINCT ru) FROM pop").fetchone()[0]
        early = c.execute(f"""SELECT COUNT(*) FILTER (WHERE action_date < '{t["closing"]}'),
                                     COUNT(*) FILTER (WHERE action_date < CAST(DATE '{t["closing"]}' - INTERVAL 30 DAY AS VARCHAR)),
                                     MIN(action_date) FROM pop WHERE pu = '{t["after"]}'""").fetchone()
        HEADLINE.setdefault("parent_tests", {})[name] = {
            "title": t["title"], "before": t["before"], "after": t["after"], "event_month": t["event_month"], "switch_month": switch,
            "months_from_event_to_switch": _months_between(t["event_month"], switch) if switch else None,
            "after_id_rows_more_than_1_month_before_event": early_after, "recipients": recipients,
            "closing_date_sec": t["closing"], "after_id_rows_before_closing": early[0],
            "after_id_rows_more_than_30_days_before_closing": early[1], "first_after_id_row": early[2],
            "rows": sum(b + a + o for _, b, a, o in months),
            "before_rows_after_switch": sum(b for m, b, _, _ in months if switch and m >= switch),
            "after_rows_after_switch": sum(a for m, _, a, _ in months if switch and m >= switch)}
        print(f"parent_tests: {name} switch {switch}", flush=True)


def _months_between(a: str, b: str) -> int:
    ya, ma = map(int, a.split("-"))
    yb, mb = map(int, b.split("-"))
    return (yb - ya) * 12 + (mb - ma)


ANALYSES = {"figure1_diagnostic": figure1_diagnostic, "pairs_leftover": pairs_leftover, "pair_cells": pair_cells,
            "amount_bands": amount_bands, "funding_999": funding_999, "dual_codes": dual_codes, "mfa_cells": mfa_cells,
            "row_jumps": row_jumps, "mint_children": mint_children, "parent_tests": parent_tests, "negative_vendors": negative_vendors}


def main(argv: list[str] | None = None) -> int:
    names = (argv if argv is not None else sys.argv[1:]) or list(ANALYSES)
    OUT.mkdir(parents=True, exist_ok=True)
    head = OUT / "headline.json"
    if head.exists():
        HEADLINE.update(json.loads(head.read_text(encoding="utf-8")))
    HEADLINE["rules"] = RULES
    for n in names:
        ANALYSES[n]()
        head.write_text(json.dumps(HEADLINE, indent=1, default=str), encoding="utf-8")
    print(f"analyses -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
