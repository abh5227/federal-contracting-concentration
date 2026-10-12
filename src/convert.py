"""Step 3: CSV -> Parquet, in two layers.

Layer A (lossless): every CSV column as text, one Parquet file per CSV member,
plus three lineage columns (_source_file, _source_member_idx, _source_row).
Written with pyarrow's streaming CSV reader so memory stays bounded and row
order is exactly file order.

Layer B (working table): the columns in config.LAYER_B_COLUMNS, cast to real
types by explicit rules, built from Layer A with DuckDB. A value that does not
match its type's pattern becomes NULL and is counted as a cast failure.
"""

from __future__ import annotations

import json
import shutil
import time
import zipfile
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from . import config

# ---------------------------------------------------------------------------
# Layer A
# ---------------------------------------------------------------------------


def extract_member(zip_path: Path, member: str, scratch_dir: Path) -> Path:
    """Copy one member out of the zip into scratch. zipfile checks the CRC-32 when the read finishes."""
    scratch_dir.mkdir(parents=True, exist_ok=True)
    out = scratch_dir / Path(member).name
    with zipfile.ZipFile(zip_path) as zf, zf.open(member) as src, open(out, "wb") as dst:
        shutil.copyfileobj(src, dst, length=16 * 1024 * 1024)
    return out


def layer_a_schema(columns: list[str]) -> pa.Schema:
    fields = [pa.field(c, pa.string(), nullable=False) for c in columns]
    fields += [
        pa.field("_source_file", pa.string(), nullable=False),
        pa.field("_source_member_idx", pa.int16(), nullable=False),
        pa.field("_source_row", pa.int64(), nullable=False),
    ]
    return pa.schema(fields)


def csv_to_layer_a(csv_path: Path, member_name: str, member_idx: int, columns: list[str],
                   out_path: Path, rejects_path: Path) -> dict:
    """Stream one CSV into one Parquet file, all columns as text.

    `_source_row` is the 1-based record number in the CSV, header excluded.

    Rows pyarrow cannot parse (wrong field count) are written to
    `rejects_path` and the conversion of this member stops with an error:
    once a row is skipped, later `_source_row` numbers can no longer be
    guaranteed to line up with the CSV, and a Layer A file with a silent gap
    must not be published.
    """
    rejects: list[dict] = []

    def on_invalid(row: pacsv.InvalidRow) -> str:
        rejects.append({"expected_columns": row.expected_columns, "actual_columns": row.actual_columns,
                        "csv_line_number": row.number, "text": row.text})
        return "skip"

    read_opts = pacsv.ReadOptions(block_size=config.ARROW_BLOCK_SIZE, encoding="utf8", use_threads=True)
    parse_opts = pacsv.ParseOptions(
        delimiter=",", quote_char='"', double_quote=True, escape_char=False,
        newlines_in_values=True,       # FPDS text fields can contain line breaks inside quotes
        # A blank line is not a record (review S3). With ignore_empty_lines=False pyarrow turned it into a
        # fake all-empty row; now it is skipped here and COUNTED by the independent audit (audit.py,
        # `blank_lines`), which the Stage 1 proof reports. A real record whose fields are all empty
        # (",,,") is still kept by both sides, and the full-row fingerprint must still match.
        ignore_empty_lines=True,
        invalid_row_handler=on_invalid,
    )
    conv_opts = pacsv.ConvertOptions(
        column_types={c: pa.string() for c in columns},
        strings_can_be_null=False,          # empty field -> "" (never NULL) in Layer A
        quoted_strings_can_be_null=False,
        check_utf8=True,
    )

    schema = layer_a_schema(columns)
    tmp_out = out_path.with_suffix(".parquet.tmp")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows_written = 0
    t0 = time.time()
    def stop_on_rejects() -> None:
        if rejects:
            rejects_path.parent.mkdir(parents=True, exist_ok=True)
            rejects_path.write_text("\n".join(json.dumps(r) for r in rejects) + "\n", encoding="utf-8")
            raise RuntimeError(f"{member_name}: {len(rejects)} row(s) pyarrow could not parse; "
                               f"Layer A not published for this member. Rows saved to {rejects_path}.")

    # The file is opened here and closed on the way out, even when a reject stops the member: the reader alone
    # keeps its handle while the exception is live, and Windows cannot delete the scratch CSV until it is closed.
    with pa.OSFile(str(csv_path), "r") as source:
        reader = pacsv.open_csv(source, read_options=read_opts, parse_options=parse_opts, convert_options=conv_opts)
        if reader.schema.names != columns:
            raise ValueError(f"{member_name}: header read by pyarrow differs from the inventory header")
        with pq.ParquetWriter(tmp_out, schema, compression=config.PARQUET_COMPRESSION) as writer:
            for batch in reader:
                stop_on_rejects()
                n = batch.num_rows
                first = rows_written + 1
                arrays = list(batch.columns) + [
                    pa.array([member_name] * n, pa.string()),
                    pa.array([member_idx] * n, pa.int16()),
                    pa.array(range(first, first + n), pa.int64()),
                ]
                writer.write_table(pa.Table.from_arrays(arrays, schema=schema))
                rows_written += n
    stop_on_rejects()
    tmp_out.replace(out_path)
    return {"member": member_name, "rows_written": rows_written, "rejected_rows": len(rejects),
            "parquet": str(out_path), "parquet_bytes": out_path.stat().st_size,
            "seconds": round(time.time() - t0, 1)}


def build_layer_a(zip_path: Path, csv_members: list, columns: list[str], fiscal_year: int,
                  log=print) -> list[dict]:
    """Extract, convert, and delete one member at a time."""
    out_dir = config.layer_a_dir(fiscal_year)
    results = []
    for m in csv_members:
        out_path = out_dir / (Path(m.name).stem + ".parquet")
        rejects_path = config.REJECTS_DIR / f"fy{fiscal_year}" / (Path(m.name).stem + ".jsonl")
        log(f"  [{m.index}/{len(csv_members)}] extracting {m.name} ({m.uncompressed_bytes/1e9:.2f} GB)")
        t0 = time.time()
        scratch_csv = extract_member(zip_path, m.name, config.SCRATCH_DIR)
        try:
            if scratch_csv.stat().st_size != m.uncompressed_bytes:
                raise IOError(f"{m.name}: extracted {scratch_csv.stat().st_size} bytes, zip says {m.uncompressed_bytes}")
            extract_s = round(time.time() - t0, 1)
            res = csv_to_layer_a(scratch_csv, m.name, m.index, columns, out_path, rejects_path)
            res["extract_seconds"] = extract_s
            log(f"      -> {res['rows_written']:,} rows, {res['rejected_rows']} rejected, "
                f"{res['parquet_bytes']/1e6:.0f} MB parquet ({extract_s}s extract, {res['seconds']}s convert)")
            results.append(res)
        finally:
            scratch_csv.unlink(missing_ok=True)
    leftovers = [p.name for p in config.SCRATCH_DIR.iterdir()] if config.SCRATCH_DIR.exists() else []
    if leftovers:
        log(f"  note: scratch still holds {leftovers}")
    return results


# ---------------------------------------------------------------------------
# Layer B
# ---------------------------------------------------------------------------

DECIMAL_TYPE = "DECIMAL(18,2)"
PATTERNS = {
    "decimal": r"-?[0-9]+(\.[0-9]{1,2})?",
    "date": r"[0-9]{4}-[0-9]{2}-[0-9]{2}",
    "int": r"-?[0-9]+",
}
TARGET_TYPES = {"text": "VARCHAR", "decimal": DECIMAL_TYPE, "date": "DATE", "int": "INTEGER"}


def q(name: str) -> str:
    """Quote a column name for DuckDB (some names start with digits or contain '-')."""
    return '"' + name.replace('"', '""') + '"'


def cast_expr(col: str, kind: str) -> str:
    """SQL that turns a Layer A text value into its Layer B value.

    The pattern test comes first, so DuckDB's own lenient parsing (e.g. it
    would round '1.239' to 1.24 for DECIMAL(18,2), or trim spaces) never
    decides anything on its own. Values that fail the pattern become NULL and
    are counted by `cast_failure_sql`.
    """
    c = q(col)
    if kind == "text":
        return f"NULLIF({c}, '')"
    pattern = PATTERNS[kind]
    target = TARGET_TYPES[kind]
    return f"CASE WHEN regexp_full_match({c}, '{pattern}') THEN TRY_CAST({c} AS {target}) END"


def layer_b_select_sql(columns_present: list[dict]) -> str:
    parts = [f"{cast_expr(c['name'], c['kind'])} AS {q(c['name'])}" for c in columns_present]
    parts += [q(c) for c in config.LINEAGE_COLS]
    return ",\n       ".join(parts)


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    spill = config.SCRATCH_DIR / "duckdb_tmp"
    spill.mkdir(parents=True, exist_ok=True)
    con.execute(f"SET temp_directory = '{spill}'")
    con.execute("SET memory_limit = '8GB'")
    con.execute("SET preserve_insertion_order = true")
    con.execute("SET TimeZone = 'UTC'")
    return con


def parquet_list_sql(paths: list[Path]) -> str:
    """An explicit file list (never a glob), so stray files can't sneak into a count."""
    return "[" + ", ".join("'" + str(p).replace("'", "''") + "'" for p in paths) + "]"


def build_layer_b(layer_a_files: list[Path], header: list[str], fiscal_year: int, log=print) -> dict:
    present = [c for c in config.LAYER_B_COLUMNS if c["name"] in header]
    missing = [c["name"] for c in config.LAYER_B_COLUMNS if c["name"] not in header]
    out = config.layer_b_path(fiscal_year)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".parquet.tmp")
    con = connect()
    src = f"read_parquet({parquet_list_sql(layer_a_files)})"
    t0 = time.time()
    con.execute(f"""
        COPY (
            SELECT {layer_b_select_sql(present)}
            FROM {src}
            ORDER BY _source_member_idx, _source_row
        ) TO '{tmp}' (FORMAT parquet, COMPRESSION zstd)
    """)
    tmp.replace(out)
    log(f"  Layer B written: {out} ({out.stat().st_size/1e6:.0f} MB, {time.time()-t0:.0f}s)")

    # Per-column cast report, computed from Layer A with the same expressions.
    stats_sql = []
    for c in present:
        col, expr = q(c["name"]), cast_expr(c["name"], c["kind"])
        stats_sql.append(f"""
            SELECT '{c["name"]}' AS column_name,
                   COUNT(*) AS rows,
                   COUNT(*) FILTER (WHERE {col} = '') AS blank_in_source,
                   COUNT(*) FILTER (WHERE {col} <> '' AND ({expr}) IS NULL) AS cast_failures,
                   COUNT(*) FILTER (WHERE {col} <> '' AND trim({col}) = '') AS whitespace_only,
                   COUNT(*) FILTER (WHERE {col} <> trim({col})) AS leading_or_trailing_space
            FROM {src}""")
    stats = con.execute(" UNION ALL ".join(stats_sql)).fetchall()
    by_name = {r[0]: r for r in stats}
    column_report = []
    for c in config.LAYER_B_COLUMNS:
        r = by_name.get(c["name"])
        rule = "'' -> NULL" if c["kind"] == "text" else f"regex ^{PATTERNS[c['kind']]}$ then cast"
        column_report.append({
            "column": c["name"], "group": c["group"], "found": r is not None,
            "requested_in_brief": c["requested"], "why_added": c.get("why", ""),
            "source_type": "text (Layer A)", "cast_to": TARGET_TYPES[c["kind"]] if r else None,
            "rule": rule if r else None,
            "blank_in_source": r[2] if r else None,
            "cast_failures": r[3] if r else None,
            "whitespace_only_values": r[4] if r else None,
            "values_with_leading_or_trailing_space": r[5] if r else None,
        })
    # Examples of failed casts, so a reviewer can see what they look like.
    failure_examples = {}
    for c in present:
        if c["kind"] == "text" or not by_name[c["name"]][3]:
            continue
        col, expr = q(c["name"]), cast_expr(c["name"], c["kind"])
        failure_examples[c["name"]] = con.execute(f"""
            SELECT {col} AS value, COUNT(*) AS n FROM {src}
            WHERE {col} <> '' AND ({expr}) IS NULL GROUP BY 1 ORDER BY n DESC LIMIT 10
        """).fetchall()
    con.close()
    return {"path": str(out), "columns_present": [c["name"] for c in present], "columns_missing": missing,
            "column_report": column_report, "cast_failure_examples": failure_examples}
