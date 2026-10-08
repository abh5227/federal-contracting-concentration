"""Fill the topic-ordered findings appendix and the source list in a version of the research note.

    python tools/build_gaps_appendix.py docs/research/government_documented_gaps_v3.md
    python tools/build_gaps_appendix.py docs/research/government_documented_gaps_v3.md --check

The note keeps two regions between HTML comment markers, and only those regions are rewritten:
  <!-- begin generated: findings-by-topic -->   every finding in config/gov_findings.csv, grouped by TOPICS below
  <!-- begin generated: sources-cited -->       every source behind those findings, from config/gov_sources.csv
Each region ends with <!-- end generated: NAME -->. The script stops if any finding is missing from TOPICS,
listed twice, or unknown, so the appendix always holds each finding exactly once.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ids(spec: str) -> list[str]:
    """'E01-E06, E33' -> ['E01', ..., 'E06', 'E33']"""
    out = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            out += [f"{a[0]}{k:02d}" for k in range(int(a[1:]), int(b[1:]) + 1)]
        elif part:
            out.append(part)
    return out


# (topic, lead sentence, [(subtopic, lead sentence, finding IDs)]). Order follows the body of the note.
TOPICS = [
    ("Product and industry codes",
     "How the product or service code and the NAICS code were defined, revised and checked.",
     [("Product code revisions", "GSA renumbered the codes in FY2012 and FY2021 and made smaller changes in between.",
       "E01-E06, E33, E34"),
      ("Accuracy of codes", "How often the codes match contract files, and what FPDS can and cannot fix.",
       "D01-D03, D46"),
      ("NAICS revisions", "Industry codes change every five years at the start of a fiscal year.",
       "E35-E37")]),
    ("Vendor identity",
     "Who answers for vendor and parent data, how often it is wrong, and which records name the wrong company.",
     [("Who answers for parent data", "Parent fields come from the recipient's registration, and agencies do not certify them.",
       "D04, D05, D13"),
      ("Parent ID and parent name errors", "What inspectors general and GAO found when they tested parent fields.",
       "D06-D12, D35, D53"),
      ("Vendor ID changes", "The move from DUNS to UEI in 2022 and related changes in how recipients are grouped.",
       "E09-E12, E38, G28"),
      ("Consortium managers and other middlemen", "Records that name a pass-through manager instead of the firms doing the work.",
       "D18-D22, F34"),
      ("Generic IDs and consolidated reports", "Placeholder vendor IDs and single rows that stand for many actions.",
       "D14-D17, A29, F30")]),
    ("Spending outside the data",
     "Spending that never enters FPDS by rule, and buyers that do not report to it.",
     [("Other transaction agreements", "OTAs sit outside FAR contract data, and their own reporting is incomplete.",
       "A01-A05, A31, B06, D68-D70, D79, D89, E17, E18, E32"),
      ("Classified and national security actions", "Actions kept out of FPDS to protect classified information.",
       "A06-A08, F13"),
      ("Small purchases and purchase cards", "What must be reported above the micro-purchase threshold, and what may be left out below it.",
       "A09, A11, A12, A23-A28, A30, F16"),
      ("Other channels excluded by rule", "Stock, store, resale, interagency and non-appropriated fund purchases, and other exclusions.",
       "A10, A13-A15, A18-A22, A32, A33"),
      ("Buyers outside the FAR or FPDS, and agencies that do not report", "Agencies and branches absent from FPDS, and agencies that submit empty or no files.",
       "A16, A17, B03-B05, B07-B15")]),
    ("Which agency gets the dollars",
     "How buying for other agencies and reorganizations move dollars between agency cells.",
     [("Buying for other agencies", "Assisted acquisitions, shared service providers and the 2025 shift to GSA.",
       "B01, B02, D23, D86, E16, G01-G03, G15"),
      ("Reorganizations and agency code changes", "Moves of work between agencies and changes in how agency codes are used.",
       "E13-E15, E42, F37")]),
    ("Data quality over time and who checks it",
     "How quality was tested, what the tests found, and how oversight changed.",
     [("GAO tests of whole records", "GAO's samples that trace award records back to agency records.",
       "D25-D29, D34"),
      ("Inspector general audits", "The DATA Act audits of FY2017 to FY2021 and GAO's summaries of them.",
       "D36-D44, D47-D52, F09, F10"),
      ("Agencies' own checks and certification", "The annual verification and certification of FPDS data, and how well agencies follow it.",
       "D30-D33, F05-F08, F14, F15, F25-F29"),
      ("Systems and validation", "What Treasury and FPDS validate, and the state of the systems behind the data.",
       "E30, F01-F04, F24, F33, F35, F36, F38-F40, G17"),
      ("Warnings about using the data", "What GAO, CRS and USAspending tell users about the data's limits.",
       "D24, E07, E08, F23, F31, F32")]),
    ("Rule changes that move row counts",
     "Changes to what must be reported, which create steps in row counts with little effect on dollars.",
     [("Reporting rules, 2008 to 2012", "The 2008 rewrite of FAR subpart 4.6 and the changes that followed.",
       "E19-E27"),
      ("How DoD records agreements and accounts", "DoD reporting practices that change what a row stands for.",
       "E43, E44"),
      ("The FAR overhaul of 2025", "The rewrite of the FAR, which moves the reporting rules to a new section.",
       "G24-G27")]),
    ("Timeliness, revisions and the move to SAM.gov",
     "The timing of reports, corrections made afterwards, and recent changes to the systems that publish the data.",
     [("DoD's 90-day hold", "DoD and Army Corps of Engineers data are released 90 days after signing.",
       "C03, C04, C06-C17"),
      ("Reporting deadlines and late entry", "The FAR deadline for reports and how often agencies miss it.",
       "C18-C26"),
      ("Changes after the fact and published totals", "Corrections with no cut-off, and the dates behind GAO's totals.",
       "C01, C05, D88, E31, G20"),
      ("The move to SAM.gov and the 2025 funding lapse", "The replacement of FPDS by SAM.gov in 2026 and the fall 2025 lapse.",
       "G05-G10, G18, G19, G29")]),
    ("Deobligations and terminations",
     "How returned money and ended contracts appear in the data, including the FY2025 terminations.",
     [("How deobligations are recorded", "The sign convention and deobligations that never reach File D1.",
       "C02, D59, G30-G32"),
      ("Terminations in FY2025", "Contract terminations across agencies in 2025 and how fully FPDS records them.",
       "G04, G11-G14, G21-G23")]),
    ("Links between awards and agency accounts",
     "How contract records in FPDS link to agencies' own account data, and where the links fail.",
     [("Linkage statistics", "The counts USAspending publishes of awards that do not link.",
       "E45, F11, F12, F17-F22, G16")]),
    ("Other fields",
     "Fields our measure does not use directly, which matter for side analyses.",
     [("Dollar and contract value fields", "Obligation amounts and the value fields that FPDS calculates.",
       "D45, D54-D58, D74, D83"),
      ("Competition and offers", "Competition codes and the number of offers received.",
       "D60-D67, E28, E29"),
      ("COVID-19 and disaster codes", "The national interest action code and the disaster emergency fund code.",
       "D71-D73"),
      ("Small business and socioeconomic fields", "Small business, minority-owned and waiver fields.",
       "D75, D77, D78"),
      ("Dates, places, types and descriptions", "Other fields with documented problems.",
       "D76, D80-D82, D84, D85, D87, E39-E41")]),
]


def read(name: str) -> list[dict]:
    return list(csv.DictReader(open(ROOT / "config" / name, encoding="utf-8")))


def cite(f: dict, src: dict) -> str:
    rn = src.get("report_number", "")
    label = rn if rn and " " not in rn.strip() else f["source_id"]
    return f"{label}, {f['pinpoint']}" if f["pinpoint"] else label


def findings_md(findings: dict, sources: dict) -> str:
    placed = [i for _, _, subs in TOPICS for _, _, spec in subs for i in ids(spec)]
    dupes = sorted({i for i in placed if placed.count(i) > 1})
    unknown = sorted(set(placed) - set(findings))
    missing = sorted(set(findings) - set(placed))
    if dupes or unknown or missing:
        sys.exit(f"TOPICS is out of step with the findings: duplicates {dupes}, unknown {unknown}, missing {missing}")
    out = []
    for n, (topic, lead, subs) in enumerate(TOPICS, 1):
        count = sum(len(ids(spec)) for _, _, spec in subs)
        out += [f"### Topic {n}. {topic}", "", f"{lead} This topic holds {count} findings.", ""]
        for sub, sublead, spec in subs:
            fs = sorted(ids(spec))
            out += [f"**{sub}.** {sublead}", ""]
            for i in fs:
                f = findings[i]
                period = f["period_covered"].strip().rstrip(".")
                meta = f"Source {cite(f, sources.get(f['source_id'], {}))}."
                if period:
                    meta += f" Period covered is {period}."
                meta += f" Effect on the measure is {f['effect_on_measure']}."
                out.append(f"- **{i}.** {f['claim']} *{meta}*")
            out.append("")
    return "\n".join(out).rstrip()


def sources_md(used: set[str], sources: dict) -> str:
    out = [f"These are the {len(used)} sources behind the findings in this note, listed by source ID. "
           "The list is generated from `config/gov_sources.csv`.", ""]
    for sid in sorted(used, key=str.lower):
        s = sources[sid]
        bits = [f"**{sid}.** {s['publisher']}."]
        if s["title"]:
            bits.append(f"\"{s['title'].rstrip('.')}.\"")
        if s["report_number"] and s["report_number"] != sid:
            bits.append(f"{s['report_number']}.")
        if s["published_date"]:
            bits.append(f"Published {s['published_date']}.")
        if s["url"]:
            bits.append(f"[{s['url']}]({s['url']})")
        if s["retrieved_utc"]:
            bits.append(f"Accessed {s['retrieved_utc'][:10]}.")
        bits.append(f"Read status is {s['read_status']}.")
        out.append("- " + " ".join(bits))
    return "\n".join(out)


def region(text: str, name: str, body: str) -> str:
    pat = re.compile(rf"(<!-- begin generated: {name} -->\n)(?:.*?\n)?(<!-- end generated: {name} -->)", re.S)
    if not pat.search(text):
        sys.exit(f"region {name!r} not found")
    return pat.sub(lambda m: m[1] + body + "\n" + m[2], text)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    paths = [a for a in args if not a.startswith("--")]
    if len(paths) != 1:
        sys.exit(__doc__)
    note = ROOT / paths[0]
    findings = {f["finding_id"]: f for f in read("gov_findings.csv")}
    sources = {s["source_id"]: s for s in read("gov_sources.csv")}
    text = note.read_text(encoding="utf-8")
    hand = re.sub(r"<!-- begin generated: (\S+) -->.*?<!-- end generated: \1 -->", " ", text, flags=re.S)
    used = {f["source_id"] for f in findings.values()}
    used |= {sid for sid in sources if re.search(rf"(?<![\w-]){re.escape(sid)}(?![\w-])", hand)}
    used |= {sid for sid, s in sources.items() if s["report_number"].strip() and " " not in s["report_number"].strip()
             and re.search(rf"(?<![\w-]){re.escape(s['report_number'].strip())}(?![\w-])", hand)}
    new = region(text, "findings-by-topic", findings_md(findings, sources))
    new = region(new, "sources-cited", sources_md(used, sources))
    if "--check" in args:
        print("up to date" if new == text else "OUT OF DATE")
        return 0 if new == text else 1
    note.write_text(new, encoding="utf-8")
    print(f"{note}: {len(findings)} findings in {len(TOPICS)} topics, {len(used)} sources listed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
