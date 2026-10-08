"""Independent raw-CSV audit: the "other side" of checks 1-3.

This module deliberately shares no parsing code with the conversion:
  conversion: zip -> extract to scratch -> pyarrow CSV reader -> Parquet
  audit:      zip -> streamed straight from the zip -> Python csv module -> Decimal
It counts records, sums federal_action_obligation with Python's Decimal, and
draws the spot-check sample (reservoir sampling with a fixed seed, so the same
file and seed always give the same 20 rows).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import random
import re
import sys
import time
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

from . import config

# Large free-text fields must not trip the csv module's default 128 KB limit.
csv.field_size_limit(sys.maxsize)

CANONICAL_MONEY = re.compile(r"-?[0-9]+(\.[0-9]+)?")
FIELD_SEP = "\x1f"       # unit separator: joins the fields of one record for its fingerprint


def row_fingerprint(row: list[str]) -> int:
    """First 16 hex digits of MD5 over the record's fields joined by U+001F, as an integer (review S1).

    Summed per member (SUM, not XOR, so duplicated rows cannot cancel out). The same recipe in DuckDB:
    CAST(('0x' || substr(md5(concat_ws(chr(31), <all columns in header order>)), 1, 16)) AS UBIGINT).
    """
    return int(hashlib.md5(FIELD_SEP.join(row).encode("utf-8")).hexdigest()[:16], 16)


def audit_zip(zip_path: Path, csv_members: list, header: list[str],
              seed: int = config.SPOT_CHECK_SEED, sample_size: int = config.SPOT_CHECK_ROWS,
              log=print) -> dict:
    ncols = len(header)
    money_idx = header.index(config.OBLIGATION_COL)
    rng = random.Random(seed)
    sample: list[dict] = []
    seen = 0                     # records seen so far across all members (for reservoir sampling)
    members_out = []

    with zipfile.ZipFile(zip_path) as zf:
        for m in csv_members:
            t0 = time.time()
            res = {
                "member": m.name, "member_idx": m.index, "records": 0, "wrong_field_count": 0,
                "wrong_field_count_examples": [], "csv_errors": [], "records_with_embedded_newlines": 0,
                "physical_lines": 0, "obligation_sum": Decimal(0), "obligation_blank": 0,
                "obligation_noncanonical": 0, "obligation_noncanonical_examples": [],
                "obligation_unparseable": 0, "obligation_unparseable_examples": [],
                "obligation_max_decimal_places": 0, "header_matches": None,
                "blank_lines": 0, "blank_line_examples": [], "all_empty_records": 0, "fingerprint": 0,
            }
            with zf.open(m.name) as raw:
                text = io.TextIOWrapper(raw, encoding=config.CSV_ENCODING, errors="strict", newline="")
                reader = csv.reader(text, strict=True)
                res["header_matches"] = next(reader) == header
                prev_line = reader.line_num
                while True:
                    try:
                        row = next(reader)
                    except StopIteration:
                        break
                    except csv.Error as e:  # malformed quoting: record it and keep reading
                        res["csv_errors"].append({"after_record": res["records"], "line": reader.line_num, "error": str(e)})
                        continue
                    if not row:          # an empty line is not a record (review S3): count it, never use it
                        res["blank_lines"] += 1
                        if len(res["blank_line_examples"]) < config.EXAMPLES_PER_CHECK:
                            res["blank_line_examples"].append({"line": reader.line_num, "after_record": res["records"]})
                        prev_line = reader.line_num
                        continue
                    res["records"] += 1
                    res["fingerprint"] += row_fingerprint(row)
                    if not any(row):
                        res["all_empty_records"] += 1
                    rownum = res["records"]
                    if reader.line_num - prev_line > 1:
                        res["records_with_embedded_newlines"] += 1
                    prev_line = reader.line_num

                    if len(row) != ncols:
                        res["wrong_field_count"] += 1
                        if len(res["wrong_field_count_examples"]) < config.EXAMPLES_PER_CHECK:
                            res["wrong_field_count_examples"].append({"row": rownum, "fields": len(row)})
                    else:
                        v = row[money_idx]
                        if v == "":
                            res["obligation_blank"] += 1
                        else:
                            if not CANONICAL_MONEY.fullmatch(v):
                                res["obligation_noncanonical"] += 1
                                if len(res["obligation_noncanonical_examples"]) < config.EXAMPLES_PER_CHECK:
                                    res["obligation_noncanonical_examples"].append({"row": rownum, "value": v})
                            try:
                                d = Decimal(v)
                                res["obligation_sum"] += d
                                exp = d.as_tuple().exponent
                                if isinstance(exp, int) and -exp > res["obligation_max_decimal_places"]:
                                    res["obligation_max_decimal_places"] = -exp
                            except InvalidOperation:
                                res["obligation_unparseable"] += 1
                                if len(res["obligation_unparseable_examples"]) < config.EXAMPLES_PER_CHECK:
                                    res["obligation_unparseable_examples"].append({"row": rownum, "value": v})

                    # Reservoir sampling (Algorithm R) over every record in the year.
                    seen += 1
                    item = {"member": m.name, "member_idx": m.index, "row": rownum, "values": row}
                    if len(sample) < sample_size:
                        sample.append(item)
                    else:
                        j = rng.randrange(seen)
                        if j < sample_size:
                            sample[j] = item
                res["physical_lines"] = reader.line_num
            res["seconds"] = round(time.time() - t0, 1)
            log(f"  audited {m.name}: {res['records']:,} records, obligations {res['obligation_sum']:,} "
                f"({res['seconds']}s)")
            members_out.append(res)

    total = {
        "records": sum(r["records"] for r in members_out),
        "obligation_sum": sum((r["obligation_sum"] for r in members_out), Decimal(0)),
        "obligation_blank": sum(r["obligation_blank"] for r in members_out),
        "obligation_noncanonical": sum(r["obligation_noncanonical"] for r in members_out),
        "obligation_unparseable": sum(r["obligation_unparseable"] for r in members_out),
        "obligation_max_decimal_places": max(r["obligation_max_decimal_places"] for r in members_out),
        "wrong_field_count": sum(r["wrong_field_count"] for r in members_out),
        "csv_errors": sum(len(r["csv_errors"]) for r in members_out),
        "records_with_embedded_newlines": sum(r["records_with_embedded_newlines"] for r in members_out),
        "blank_lines": sum(r["blank_lines"] for r in members_out),
        "all_empty_records": sum(r["all_empty_records"] for r in members_out),
    }
    sample.sort(key=lambda s: (s["member_idx"], s["row"]))
    return {"method": "Python csv module streamed from the zip; Decimal sum", "seed": seed,
            "sample_size": sample_size, "members": members_out, "total": total, "sample": sample}


def save_audit(audit: dict, fiscal_year: int) -> Path:
    """Save to data/audit (gitignored: the sample holds raw rows)."""
    config.AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    out = config.AUDIT_DIR / f"fy{fiscal_year}_raw_audit.json"
    out.write_text(json.dumps(audit, default=str, indent=1), encoding="utf-8")
    return out
