"""data/manifest.csv: one row per source file.

All writes go through `upsert_row`, so a file registered twice (for example on
a pipeline rerun) keeps one row. The key is the file name plus its SHA-256: a
different file with the same name gets its own row rather than overwriting
the old one.
"""

from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path

from . import config

MANIFEST_FIELDS = [
    "file_name",
    "local_path",
    "source_url",
    "size_bytes",
    "sha256",
    "fiscal_year",
    "archive_scope",        # "All" = all agencies, or an agency code
    "archive_type",         # "Full" or "Delta"
    "data_as_of_date",      # date in the zip file name (YYYY-MM-DD)
    "member_file_date",     # date in the CSV member names, if different
    "date_registered",      # first time this file entered the manifest
    "registered_via",       # "download" or "register"
    "member_count",
    "column_count",
    "row_count",            # filled after conversion (independent raw-CSV count)
    "obligation_total",     # filled after conversion (independent raw-CSV Decimal sum)
    "notes",
]


def read_manifest(path: Path = config.MANIFEST_PATH) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != MANIFEST_FIELDS:
            raise ValueError(
                f"{path} has columns {reader.fieldnames}, expected {MANIFEST_FIELDS}. "
                "Refusing to rewrite a manifest with an unexpected layout."
            )
        return list(reader)


def _write_manifest(rows: list[dict], path: Path) -> None:
    """Write atomically: a crash mid-write never leaves a half-written manifest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".manifest.", suffix=".csv")
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in MANIFEST_FIELDS})
    os.replace(tmp, path)


def find_row(file_name: str, sha256: str, path: Path = config.MANIFEST_PATH) -> dict | None:
    for row in read_manifest(path):
        if row["file_name"] == file_name and row["sha256"] == sha256:
            return row
    return None


def upsert_row(new: dict, path: Path = config.MANIFEST_PATH) -> dict:
    """Insert `new`, or update the existing row with the same file name + SHA-256.

    On update, `date_registered` keeps its original value and empty values in
    `new` never overwrite filled ones.
    """
    unknown = set(new) - set(MANIFEST_FIELDS)
    if unknown:
        raise KeyError(f"Unknown manifest fields: {sorted(unknown)}")
    rows = read_manifest(path)
    for row in rows:
        if row["file_name"] == new["file_name"] and row["sha256"] == new["sha256"]:
            for k, v in new.items():
                if k == "date_registered" and row.get(k):
                    continue
                if v not in (None, ""):
                    row[k] = v
            _write_manifest(rows, path)
            return row
    rows.append({k: new.get(k, "") for k in MANIFEST_FIELDS})
    _write_manifest(rows, path)
    return rows[-1]
