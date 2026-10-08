"""Build a new version of the glossary from config/glossary.csv (the source of truth).

    python tools/build_glossary.py --out docs/glossary_vN.md      # N is the next unused version number
    python -m src.report_pdf --in docs/glossary_vN.md --out reports/glossary_vN.pdf

--out is required, and the script stops if that file already exists, because every earlier version is frozen
(docs/glossary.md is version 1). An output named *_vN.md gets "(version N)" after the title, so its PDF footer
names the version.

Layout: a one-line note on how to use it, an index by category, the entries A to Z, then an appendix listing every
flag code with its one-line meaning, generated from config/flag_catalog.csv so it never drifts. Source titles and
URLs come from config/gov_sources.csv. The script stops on a row with an unknown category or a missing column.
"""

from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config  # noqa: E402

COLUMNS = ["term", "also_called", "category", "plain_summary", "why_it_matters_here", "where_it_shows_up",
           "official_definition", "source_id", "pinpoint", "learn_more_url", "related_terms", "definition_type",
           "verified", "added_utc"]
CODE_LIKE = re.compile(r"^[\w.*-]*(?:_|/|\.(?:md|csv|py|json|parquet|pdf)\b)[\w./*{}-]*$")


def code_items(text: str) -> str:
    """Comma-separated places: column names and file paths in code spans, the rest as written."""
    out = []
    for x in (x.strip() for x in text.split(",") if x.strip()):
        head, _, tail = x.partition(" ")
        out.append(f"`{head}`" + (" " + tail if tail else "") if CODE_LIKE.match(head) else x)
    return ", ".join(out)


def letter(term: str) -> str:
    c = term.strip()[0].upper()
    return c if c.isalpha() else "Numbers and symbols"


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True, help="markdown to write, a new file such as docs/glossary_v4.md")
    out = ap.parse_args(argv).out
    out = out if out.is_absolute() else config.REPO_ROOT / out
    if out.exists():
        sys.exit(f"{out} already exists. Glossary versions are frozen, so build a new version under a new name.")
    version = re.search(r"_v(\d+)$", out.stem)
    rows = list(csv.DictReader(open(config.GLOSSARY_CSV, encoding="utf-8")))
    missing = [c for c in COLUMNS if rows and c not in rows[0]]
    bad = [r["term"] for r in rows if r["category"] not in config.GLOSSARY_CATEGORIES]
    if missing or bad:
        sys.exit(f"glossary.csv: missing columns {missing}, unknown category in {bad[:5]}")
    sources = {r["source_id"]: r for r in csv.DictReader(open(config.GOV_SOURCES_CSV, encoding="utf-8"))}
    flags = list(csv.DictReader(open(config.REPO_ROOT / "config" / "flag_catalog.csv", encoding="utf-8")))
    rows.sort(key=lambda r: r["term"].lower())

    md = ["# Glossary of terms for the contract concentration project" + (f" (version {version[1]})" if version else ""), "",
          "Find a term in the index by category or in the entries A to Z. Each entry gives a plain summary, why the "
          "term matters to our measure, where it shows up, an official definition where one exists, and a source to "
          "read more.", "", "## Index by category", ""]
    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r["term"])
    for c in config.GLOSSARY_CATEGORIES:
        if by_cat[c]:
            md += [f"**{c} ({len(by_cat[c])}).** " + " · ".join(by_cat[c]), ""]

    md += ["## Entries A to Z", ""]
    current = None
    for r in sorted(rows, key=lambda r: (letter(r["term"]) != "Numbers and symbols", r["term"].lower())):
        if letter(r["term"]) != current:
            current = letter(r["term"])
            md += [f"### {current}", ""]
        md += [f"#### {r['term']}", ""]
        head = f"*{r['category']}.*" + (f" Also called {r['also_called']}." if r["also_called"] else "")
        md += [head + " " + r["plain_summary"], ""]
        if r["why_it_matters_here"]:
            md += [f"**Why it matters here.** {r['why_it_matters_here']}", ""]
        if r["where_it_shows_up"]:
            md += [f"**Shows up in.** {code_items(r['where_it_shows_up'])}", ""]
        if r["official_definition"]:
            md += ["> " + r["official_definition"], ""]
        src = sources.get(r["source_id"], {})
        bits = []
        if r["source_id"]:
            name = src.get("title") or r["source_id"]
            label = f"\"{name}\"" if src.get("title") else name           # titles are verbatim, so they go in quotation marks
            bits.append(f"{src.get('publisher', '')}, {label}".strip(", ") + (f", {r['pinpoint']}" if r["pinpoint"] else ""))
        kind = {"official": "This is an official definition.", "official paraphrased": "The summary paraphrases an official source.",
                "project-internal": "This is a project definition."}.get(r["definition_type"], r["definition_type"])
        line = f"**Source.** {'. '.join(bits) + '. ' if bits else ''}{kind}"
        if r["learn_more_url"]:
            line += f" Read more at [{r['learn_more_url']}]({r['learn_more_url']})."
        md += [line, ""]
        if r["related_terms"]:
            md += ["**Related.** " + " · ".join(x.strip() for x in r["related_terms"].split(",") if x.strip()) + ".", ""]

    md += ["## Appendix. Flag codes", "",
           "Every check in the flag catalog, with its one-line meaning. This list is generated from the catalog.", "",
           "| Code | Meaning | Severity | Level |", "|---|---|---|---|"]
    md += [f"| {f['flag_id']} | {f['name']} | {f['severity']} | {f['level']} |" for f in flags]
    out.write_text("\n".join(md).rstrip() + "\n", encoding="utf-8")
    print(f"{out}: {len(rows)} terms in {sum(1 for c in by_cat if by_cat[c])} categories, {len(flags)} flag codes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
