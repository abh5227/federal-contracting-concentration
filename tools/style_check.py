"""Check a markdown report against Andy's writing rules and print every hit with its line number.

    python tools/style_check.py docs/integrity_findings_v2.md
    python tools/style_check.py docs/integrity_findings.md --summary      # counts only

Checks (outside fenced code blocks, inline code spans, HTML comments, file paths and verbatim quotes):
  em-dash        an em dash (U+2014)
  range          a number range written with a hyphen or en dash (FY2008-FY2025, 63-70%, $5B-$15B);
                 ISO dates (2013-09-26) and year-months (2020-04) are not ranges
  semicolon      a semicolon
  conjunction    a sentence that starts with where, when, while, if, because, although, though, since,
                 once, unless, after, before or as
  not-x          the ", not " construction
  pointer        a "see ..." pointer, or "explained/shown/described/listed/mentioned above/below"
  contraction    a contraction (don't, it's, they're, ...); possessives such as GAO's are fine
Report and document numbers are not ranges (added 2026-10-06): GAO-18-138, M-17-04, DODIG-2022-027, E8-8447,
FAC 2005-62, Pub. L. 114-328, FIPS 180-4, FAR 13.303-1, FAR Case 2004-038, 20-04237-09 and similar identifiers are ignored. A fiscal-year range such as FY2008-2025 is still a hit.
Verbatim quotes from sources are exempt (added 2026-10-06 for the research note and glossary): blockquote lines
(starting with ">") are skipped, and text inside quotation marks ("..." or “...”) on a line is ignored.
Exit code: 0 when there are no hits, 1 otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CONJ = ("where", "when", "while", "if", "because", "although", "though", "since", "once", "unless", "after", "before", "as")
PATH = re.compile(r"(?<![\w$])(?:\.{0,2}/)?(?:[\w.-]+/)+[\w.*{}-]*|\b[\w-]+\.(?:md|csv|py|json|parquet|pdf|txt|html)\b")
IDENT = re.compile(r"\b(?!FY\d)[A-Za-z][A-Za-z0-9]*-\d+(?:-\d+)*[A-Za-z]?\b"
                   r"|\b(?:FAC|L\.|Doc|No\.|Letter|Circular|FIPS|FR|OIG)\s+\d+-\d+\b"
                   r"|\b\d+\.\d+(?:-\d+)+\b"                        # FAR and DFARS sections such as 13.303-1
                   r"|\b\d+-\d+-\d+\b"                                # report numbers with two hyphens, such as 20-04237-09
                   r"|\bCase\s+\d+-\d+\b")                            # FAR case numbers
DATE = re.compile(r"\b\d{4}-\d{2}(?:-\d{2})?\b")
RANGE = re.compile(r"(?:\bFY\d{4}\s*[-–]\s*(?:FY)?\d{2,4}\b)"
                   r"|(?:\d(?:[\d,.]*\d)?\s*(?:%|B|M|K|k|billion|million)?\s*[-–]\s*[-+]?\$?\d)")
CONTRACTION = re.compile(r"\b\w+n[’']t\b|\b\w+[’'](?:re|ve|ll|d|m)\b"
                         r"|\b(?:it|that|there|what|here|let|who|he|she|where|how)[’']s\b", re.I)
POINTER = re.compile(r"\bsee\b|\b(?:explained|shown|described|listed|mentioned)\s+(?:above|below)\b", re.I)
SENT_START = re.compile(r"(?:^|[.!?]\s+|^\s*(?:[-*+]|\d+\.)\s+|\*\*[^*]+[.:]\*\*\s+|\|\s*)"
                        r"(?:\*\*)?(" + "|".join(CONJ) + r")\b", re.I)


def clean(line: str) -> str:
    line = re.sub(r"`[^`]*`", " ", line)                  # inline code spans
    line = re.sub(r"<!--.*?-->", " ", line)                # HTML comments (figure markers)
    line = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", line)   # keep link text, drop the target
    line = re.sub(r"https?://\S+", " ", line)
    line = re.sub(r"\u201c[^\u201d]*\u201d|\"[^\"]*\"", " ", line)   # verbatim quotes in quotation marks
    line = IDENT.sub(" ", line)                                       # report and document numbers
    return PATH.sub(" ", line)


def check(path: Path) -> list[tuple[int, str, str]]:
    hits, fenced, in_comment = [], False, False
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if raw.strip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        if in_comment:
            if "-->" in raw:
                in_comment = False
            continue
        if raw.strip().startswith("<!--") and "-->" not in raw:
            in_comment = True
            continue
        if raw.lstrip().startswith(">"):                     # blockquotes hold verbatim quotes
            continue
        line = clean(raw)
        found = []
        if "—" in line:
            found.append(("em-dash", "—"))
        for m in RANGE.finditer(DATE.sub(" ", line)):       # dates are never ranges
            found.append(("range", m.group(0)))
        if ";" in line:
            found.append(("semicolon", ";"))
        for m in SENT_START.finditer(line):
            found.append(("conjunction", m.group(1)))
        if ", not " in line:
            found.append(("not-x", ", not "))
        for m in POINTER.finditer(line):
            found.append(("pointer", m.group(0)))
        for m in CONTRACTION.finditer(line):
            found.append(("contraction", m.group(0)))
        for rule, what in found:
            hits.append((n, rule, what))
    return hits


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    summary = "--summary" in args
    files = [Path(a) for a in args if not a.startswith("--")]
    total = 0
    for f in files:
        hits = check(f)
        total += len(hits)
        counts: dict[str, int] = {}
        for _, rule, _ in hits:
            counts[rule] = counts.get(rule, 0) + 1
        if not summary:
            lines = f.read_text(encoding="utf-8").splitlines()
            for n, rule, what in hits:
                print(f"{f}:{n}: {rule}: {what!r}  |  {lines[n - 1].strip()[:110]}")
        print(f"{f}: {len(hits)} hits " + (str(dict(sorted(counts.items()))) if counts else ""))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
