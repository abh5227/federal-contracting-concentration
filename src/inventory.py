"""Step 1: look inside an archive zip without extracting it.

Reads the zip's directory and the first line (header) of each CSV member by
streaming it, so nothing is written to disk here.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import config

# USAspending archive names look like FY2025_All_Contracts_Full_20260906.zip.
# "All" can also be an agency code (per-agency files); type is Full or Delta.
ARCHIVE_NAME_RE = re.compile(
    r"^FY(?P<fy>\d{4})_(?P<scope>[A-Za-z0-9]+)_(?P<kind>Contracts|Assistance)_(?P<type>Full|Delta)_(?P<date>\d{8})\.zip$"
)
MEMBER_NAME_RE = re.compile(
    r"^FY(?P<fy>\d{4})_(?P<scope>[A-Za-z0-9]+)_(?P<kind>Contracts|Assistance)_(?P<type>Full|Delta)_(?P<date>\d{8})_(?P<part>\d+)\.csv$"
)


def _yyyymmdd(s: str) -> str:
    return date(int(s[:4]), int(s[4:6]), int(s[6:])).isoformat()


def parse_archive_name(name: str) -> dict:
    """Split an archive file name into its parts. Returns {'matched': False, ...} if it doesn't fit."""
    m = ARCHIVE_NAME_RE.match(name)
    if not m:
        return {"matched": False, "file_name": name}
    return {
        "matched": True,
        "file_name": name,
        "fiscal_year": int(m["fy"]),
        "scope": m["scope"],
        "kind": m["kind"],
        "type": m["type"],
        "data_as_of_date": _yyyymmdd(m["date"]),
    }


def sha256_of(path: Path, chunk: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


@dataclass
class MemberInfo:
    index: int                  # 1-based position in the zip
    name: str
    compressed_bytes: int
    uncompressed_bytes: int
    crc32: str
    modified: str               # timestamp stored in the zip entry
    is_csv: bool
    name_parts: dict = field(default_factory=dict)
    header: list[str] | None = None


def read_csv_header(zf: zipfile.ZipFile, member: str) -> list[str]:
    """Parse only the header record of a member, streaming from the zip."""
    with zf.open(member) as raw:
        text = io.TextIOWrapper(raw, encoding=config.CSV_ENCODING, newline="")
        return next(csv.reader(text))


def inspect_zip(zip_path: Path) -> dict:
    """List members, parse names, read every CSV header, compare headers."""
    members: list[MemberInfo] = []
    with zipfile.ZipFile(zip_path) as zf:
        for i, info in enumerate(zf.infolist(), start=1):
            is_csv = info.filename.lower().endswith(".csv") and not info.is_dir()
            m = MEMBER_NAME_RE.match(info.filename)
            mi = MemberInfo(
                index=i,
                name=info.filename,
                compressed_bytes=info.compress_size,
                uncompressed_bytes=info.file_size,
                crc32=f"{info.CRC:08x}",
                modified="%04d-%02d-%02d %02d:%02d:%02d" % info.date_time,
                is_csv=is_csv,
                name_parts=({**m.groupdict(), "date": _yyyymmdd(m["date"])} if m else {}),
            )
            if is_csv:
                mi.header = read_csv_header(zf, info.filename)
            members.append(mi)

    csv_members = [m for m in members if m.is_csv]
    reference = csv_members[0].header if csv_members else []
    header_mismatches = [
        {"member": m.name, "columns": len(m.header),
         "first_difference_at": next((j for j, (a, b) in enumerate(zip(m.header, reference)) if a != b), None)}
        for m in csv_members[1:] if m.header != reference
    ]
    duplicates = sorted({c for c in reference if reference.count(c) > 1})
    member_dates = sorted({m.name_parts.get("date") for m in csv_members if m.name_parts})
    return {
        "zip_path": str(zip_path),
        "name": parse_archive_name(zip_path.name),
        "members": members,
        "csv_members": csv_members,
        "non_csv_members": [m.name for m in members if not m.is_csv],
        "columns": reference,
        "headers_identical": not header_mismatches,
        "header_mismatches": header_mismatches,
        "duplicate_column_names": duplicates,
        "member_name_dates": member_dates,
        "total_compressed_bytes": sum(m.compressed_bytes for m in members),
        "total_uncompressed_bytes": sum(m.uncompressed_bytes for m in members),
    }


def check_expected_columns(columns: list[str]) -> dict:
    """Which Layer B / brief columns are present in the real header."""
    present = set(columns)
    brief_missing = [c for c in config.BRIEF_EXPECTED_COLUMNS if c not in present]
    layer_b_missing = [c["name"] for c in config.LAYER_B_COLUMNS if c["name"] not in present]
    # Report near-matches for anything missing, to catch renames.
    near = {}
    for c in brief_missing + layer_b_missing:
        stem = c.replace("_code", "").replace("_name", "")
        near[c] = [x for x in columns if stem in x][:10]
    return {
        "brief_expected": len(config.BRIEF_EXPECTED_COLUMNS),
        "brief_missing": brief_missing,
        "layer_b_missing": layer_b_missing,
        "near_matches_for_missing": near,
        "lineage_name_collisions": [c for c in config.LINEAGE_COLS if c in present],
    }
