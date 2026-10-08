"""Tests for Stage 0 and Stage 1 and the code-review fixes they carry (S1, S3, S4, S5, N9).

    .venv/bin/python -m tests.test_stages          # standard library only (pytest is not installed)
    .venv/bin/pytest tests/                        # the same tests, if pytest is installed

Each test builds small archive zips with the real 297-column header in a temporary folder and runs the
real CLIs in a subprocess with PILOT_OUTPUT_ROOT / PILOT_RAW_ROOT pointed at that folder, so nothing in
the repo's data/ or reports/ and nothing in Project/DATA is touched.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import traceback
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HEADER = [ln.split("\t", 1)[1] for ln in (REPO / "reports" / "columns_fy2025.txt").read_text().splitlines()
          if ln and not ln.startswith("#")]
ZIP_NAME = "FY2025_All_Contracts_Full_20260906.zip"


def record(i: int, amount: str = "100.00", **over) -> list[str]:
    r = dict.fromkeys(HEADER, "")
    r.update({"contract_transaction_unique_key": f"KEY_{i}", "contract_award_unique_key": f"CONT_AWD_{i}",
              "federal_action_obligation": amount, "action_date": "2025-01-15", "action_date_fiscal_year": "2025",
              "recipient_name": f"VENDOR {i}, INC.", "transaction_description": "line one\nline two" if i % 3 == 0 else "x"})
    r.update(over)
    return [r[c] for c in HEADER]


def csv_bytes(rows: list[list[str]], blank_after: tuple[int, ...] = (), raw_lines: list[bytes] | None = None) -> bytes:
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(HEADER)
    out = buf.getvalue().encode()
    for k, row in enumerate(rows, start=1):
        b = io.StringIO(newline="")
        csv.writer(b, lineterminator="\r\n").writerow(row)
        out += b.getvalue().encode()
        if k in blank_after:
            out += b"\r\n"                      # a blank line: not a record
    for line in raw_lines or []:
        out += line
    return out


def make_zip(folder: Path, members: list[bytes], name: str = ZIP_NAME) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for k, data in enumerate(members, start=1):
            z.writestr(f"FY2025_All_Contracts_Full_20260907_{k}.csv", data)
    return path


def run(tmp: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PILOT_OUTPUT_ROOT": str(tmp / "out"), "PILOT_RAW_ROOT": str(tmp / "raw")}
    return subprocess.run([sys.executable, "-m", *args], cwd=REPO, env=env, capture_output=True, text=True)


def organize(tmp: Path, src: Path) -> subprocess.CompletedProcess:
    return run(tmp, "src.stage0", "organize", "--source", str(src), "--only-fy", "2025")


def proof(tmp: Path) -> dict:
    return json.loads((tmp / "out" / "data" / "integrity" / "stage1" / "fy2025_proof.json").read_text())


def layer_a(tmp: Path) -> Path:
    return tmp / "out" / "data" / "parquet" / "layer_a" / "fy2025" / "20260906"


# ----------------------------------------------------------------------------------------- tests


def test_fingerprint_recipe_matches_duckdb(tmp_path: Path) -> None:
    """S1: the Python and DuckDB fingerprints agree on empty fields, separators, newlines and Unicode."""
    import duckdb
    sys.path.insert(0, str(REPO))
    from src.audit import row_fingerprint
    rows = [["a", "", "b"], ["", "", ""], ["x,y", "line\r\nbreak", "é漢 "], ["\x1f", "", "z"]]
    con = duckdb.connect()
    con.execute("CREATE TABLE t (a VARCHAR, b VARCHAR, c VARCHAR)")
    con.executemany("INSERT INTO t VALUES (?, ?, ?)", rows)
    db = con.execute("SELECT SUM(CAST(('0x' || substr(md5(concat_ws(chr(31), a, b, c)), 1, 16)) AS UBIGINT)) FROM t").fetchone()[0]
    assert int(db) == sum(row_fingerprint(r) for r in rows)


def test_stage0_moves_verified_zip_and_makes_it_read_only(tmp_path: Path) -> None:
    src = make_zip(tmp_path / "downloads", [csv_bytes([record(i) for i in range(1, 6)])])
    sha = hashlib.sha256(src.read_bytes()).hexdigest()
    r = organize(tmp_path, src.parent)
    assert r.returncode == 0, r.stderr
    dest = tmp_path / "raw" / "release_2026-09-06" / ZIP_NAME
    assert dest.is_file() and not src.exists()
    assert hashlib.sha256(dest.read_bytes()).hexdigest() == sha
    assert not dest.stat().st_mode & 0o222 and not dest.parent.stat().st_mode & 0o222
    rows = list(csv.DictReader(open(tmp_path / "out" / "data" / "manifest.csv")))
    mine = [x for x in rows if x["file_name"] == ZIP_NAME]
    assert mine[0]["sha256"] == sha and mine[0]["local_path"] == str(dest.resolve())
    pending = [x for x in rows if x["registered_via"] == "pending"]
    assert {x["fiscal_year"] for x in pending} == {str(y) for y in range(2008, 2025)}   # every other year is pending here
    os.chmod(dest.parent, 0o755)


def test_stage0_bad_crc_stops_before_moving(tmp_path: Path) -> None:
    src = make_zip(tmp_path / "downloads", [csv_bytes([record(i) for i in range(1, 200)])])
    data = bytearray(src.read_bytes())
    data[200] ^= 0xFF                              # flip a byte inside the compressed data
    src.write_bytes(bytes(data))
    r = organize(tmp_path, src.parent)
    assert r.returncode != 0
    assert src.exists() and not (tmp_path / "raw" / "release_2026-09-06" / ZIP_NAME).exists()


def test_stage1_blank_lines_counted_header_only_member_passes(tmp_path: Path) -> None:
    """S3 + N9 + S5: blank lines are counted, never rows; an all-empty record is kept; header-only member passes."""
    empty_record = [""] * len(HEADER)
    m1 = csv_bytes([record(1), record(2), empty_record, record(3, "-5.25")], blank_after=(1, 4))
    m2 = csv_bytes([])                             # header only
    organize(tmp_path, make_zip(tmp_path / "downloads", [m1, m2]).parent)
    r = run(tmp_path, "src.stage1", "build", "--fy", "2025")
    assert r.returncode == 0, r.stdout + r.stderr
    p = proof(tmp_path)
    m = {k.rsplit("_", 1)[-1]: v for k, v in p["members"].items()}
    assert p["status"] == "PASS"
    assert m["1.csv"]["raw_records"] == m["1.csv"]["parquet_rows"] == 4
    assert m["1.csv"]["blank_lines"] == 2 and m["1.csv"]["parquet_all_empty_rows"] == 1
    assert m["2.csv"]["raw_records"] == 0 and m["2.csv"]["status"] == "PASS" and m["2.csv"]["header_only_member"]
    listing = json.loads((layer_a(tmp_path) / "_files.json").read_text())
    assert [x["rows"] for x in listing["members"]] == [4, 0]
    assert (tmp_path / "out" / "reports" / "integrity" / "stage1_mirror_proof.md").exists()
    os.chmod(tmp_path / "raw" / "release_2026-09-06", 0o755)


def test_stage1_recheck_passes_then_catches_a_changed_cell(tmp_path: Path) -> None:
    """recheck (used after moving the project) re-proves a year from the recorded raw side, without the CSVs."""
    import pyarrow.parquet as pq
    import pyarrow as pa
    organize(tmp_path, make_zip(tmp_path / "downloads", [csv_bytes([record(i) for i in range(1, 40)])]).parent)
    assert run(tmp_path, "src.stage1", "build", "--fy", "2025").returncode == 0
    r = run(tmp_path, "src.stage1", "recheck", "--fy", "2025")
    assert r.returncode == 0 and "FY2025: PASS" in r.stdout, r.stdout + r.stderr
    built = next(layer_a(tmp_path).glob("*.parquet"))
    t = pq.read_table(built)
    col = t.column("recipient_name").to_pylist()
    col[5] = col[5] + " "                          # one invisible change; rows and dollars unchanged
    pq.write_table(t.set_column(t.schema.get_field_index("recipient_name"), "recipient_name", pa.array(col, pa.string())), built)
    r = run(tmp_path, "src.stage1", "recheck", "--fy", "2025")
    assert r.returncode == 1 and "fingerprint" in r.stdout and "FY2025: FAIL" in r.stdout, r.stdout + r.stderr
    os.chmod(tmp_path / "raw" / "release_2026-09-06", 0o755)


def test_stage1_tampered_pilot_file_is_caught_and_rebuilt(tmp_path: Path) -> None:
    """S1: a Layer A file with one changed cell (row count and dollars unchanged) fails its fingerprint."""
    import pyarrow.parquet as pq
    import pyarrow as pa
    rows = [record(i) for i in range(1, 50)]
    organize(tmp_path, make_zip(tmp_path / "downloads", [csv_bytes(rows)]).parent)
    assert run(tmp_path, "src.stage1", "build", "--fy", "2025").returncode == 0
    built = next(layer_a(tmp_path).glob("*.parquet"))
    t = pq.read_table(built)
    col = t.column("recipient_name").to_pylist()
    col[17] = col[17] + " "                        # one invisible change in one non-money column
    t = t.set_column(t.schema.get_field_index("recipient_name"), "recipient_name", pa.array(col, pa.string()))
    legacy = tmp_path / "out" / "data" / "parquet" / "layer_a" / "fy2025"
    pq.write_table(t, legacy / built.name)          # pretend it is the pilot's old flat-layout file
    built.unlink()
    (layer_a(tmp_path) / "_files.json").unlink()
    (tmp_path / "out" / "data" / "integrity" / "stage1" / "fy2025_proof.json").unlink()
    r = run(tmp_path, "src.stage1", "build", "--fy", "2025")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "failed its proof (fingerprint)" in r.stdout
    assert (legacy / "_old" / built.name).exists() and proof(tmp_path)["status"] == "PASS"
    os.chmod(tmp_path / "raw" / "release_2026-09-06", 0o755)


def test_stage1_adopts_matching_pilot_file(tmp_path: Path) -> None:
    rows = [record(i) for i in range(1, 30)]
    organize(tmp_path, make_zip(tmp_path / "downloads", [csv_bytes(rows)]).parent)
    assert run(tmp_path, "src.stage1", "build", "--fy", "2025").returncode == 0
    built = next(layer_a(tmp_path).glob("*.parquet"))
    legacy = tmp_path / "out" / "data" / "parquet" / "layer_a" / "fy2025"
    os.rename(built, legacy / built.name)
    (layer_a(tmp_path) / "_files.json").unlink()
    (tmp_path / "out" / "data" / "integrity" / "stage1" / "fy2025_proof.json").unlink()
    r = run(tmp_path, "src.stage1", "build", "--fy", "2025")
    assert r.returncode == 0 and built.exists() and not (legacy / built.name).exists()
    assert next(iter(proof(tmp_path)["members"].values()))["adopted_from_pilot"] is True
    os.chmod(tmp_path / "raw" / "release_2026-09-06", 0o755)


def test_stage1_exits_nonzero_on_malformed_record(tmp_path: Path) -> None:
    """S4: a record with an extra field stops the member; exit code 1; no _files.json is published."""
    bad = b"KEY_X" + b"," * len(HEADER) + b"\r\n"   # one field too many
    organize(tmp_path, make_zip(tmp_path / "downloads", [csv_bytes([record(1)], raw_lines=[bad])]).parent)
    r = run(tmp_path, "src.stage1", "build", "--fy", "2025")
    assert r.returncode == 1, r.stdout + r.stderr
    assert proof(tmp_path)["status"] == "FAIL" and not (layer_a(tmp_path) / "_files.json").exists()
    os.chmod(tmp_path / "raw" / "release_2026-09-06", 0o755)


def test_stage2_flags_fire_on_planted_problems(tmp_path: Path) -> None:
    """Stage 2 on planted problems: each lands in row_flags with the right flag_id; clean rows get none of these."""
    import duckdb
    rows = [record(i) for i in range(1, 40)]
    rows.append(record(1))                                                      # B02 duplicate key (and B04 exact copy)
    rows.append(record(50, action_date="2023-05-01"))                           # C01 outside FY2025
    rows.append(record(51, product_or_service_code="12"))                       # F01 bad PSC
    rows.append(record(52, recipient_name="MULTIPLE RECIPIENTS"))               # E01 placeholder vendor
    rows.append(record(53, amount="1500000000.00"))                             # J02 >= $1B
    rows.append(record(54, number_of_offers_received="0", extent_competed_code="A"))   # X02
    rows.append(record(55, amount="12.345"))                                    # D03 3 decimals
    organize(tmp_path, make_zip(tmp_path / "downloads", [csv_bytes(rows)]).parent)
    assert run(tmp_path, "src.stage1", "build", "--fy", "2025").returncode == 0
    r = run(tmp_path, "src.stage2", "years")
    assert r.returncode == 0, r.stdout + r.stderr
    r = run(tmp_path, "src.stage2", "cross")
    assert r.returncode == 0, r.stdout + r.stderr
    f = tmp_path / "out" / "data" / "integrity" / "row_flags" / "fy2025.parquet"
    got = set(duckdb.sql(f"SELECT contract_transaction_unique_key || ':' || flag_id FROM '{f}'").fetchall())
    got = {x[0] for x in got}
    for expect in ("KEY_1:B02", "KEY_1:B04", "KEY_50:C01", "KEY_51:F01", "KEY_52:E01", "KEY_53:J02", "KEY_54:X02", "KEY_55:D03"):
        assert expect in got, (expect, sorted(got)[:40])
    for clean in ("KEY_7:B02", "KEY_7:C01", "KEY_7:F01", "KEY_7:J02"):
        assert clean not in got
    prof = tmp_path / "out" / "data" / "integrity" / "fy2025" / "column_profile.parquet"
    n = duckdb.sql(f"SELECT rows FROM '{prof}' WHERE column_name = 'recipient_name'").fetchone()[0]
    assert n == len(rows)
    os.chmod(tmp_path / "raw" / "release_2026-09-06", 0o755)


def test_add_year_refreshes_cross_year_results(tmp_path: Path) -> None:
    """The one-command add (src.stages add-year): a later year is verified, moved, proven, profiled, and the
    cross-year key check (B03) sees a key that sits in both years. Reports and proposed decisions are rebuilt."""
    import duckdb
    y25 = [record(i) for i in range(1, 30)] + [record(900)]
    y24 = [record(i + 100, action_date="2024-03-01", action_date_fiscal_year="2024") for i in range(1, 30)]
    y24.append(record(900, action_date="2024-03-02", action_date_fiscal_year="2024"))   # same key as FY2025's KEY_900
    src = tmp_path / "downloads"
    make_zip(src, [csv_bytes(y25)])
    zp = make_zip(src, [csv_bytes(y24)], name="FY2024_All_Contracts_Full_20260906.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:      # member names must carry FY2024
        z.writestr("FY2024_All_Contracts_Full_20260906_1.csv", csv_bytes(y24))
    assert organize(tmp_path, src).returncode == 0
    r = run(tmp_path, "src.stages", "refresh")
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    r = run(tmp_path, "src.stages", "add-year", "--fy", "2024", "--source", str(src))
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    out = tmp_path / "out"
    b03 = duckdb.sql(f"SELECT DISTINCT contract_transaction_unique_key, fiscal_year FROM '{out}/data/integrity/row_flags/fy2024.parquet' "
                     "WHERE flag_id = 'B03'").fetchall()
    assert b03 == [("KEY_900", 2024)], b03
    rows = list(csv.DictReader(open(out / "data" / "manifest.csv")))
    assert not [x for x in rows if x["fiscal_year"] == "2024" and x["registered_via"] == "pending"]
    head = (out / "reports" / "integrity" / "completeness_check.md").read_text().split("\n")[0]
    assert head.startswith("GAO and GSA both start from FPDS") and "Status with GAO primary and GSA as context: 0 PASS, 0 WARN, 2 FAIL" in head, head
    dec = list(csv.DictReader(open(out / "config" / "decisions.csv")))
    assert any(d["target"] == "B03" and d["status"] == "proposed" for d in dec)
    for p in (tmp_path / "raw" / "release_2026-09-06",):
        os.chmod(p, 0o755)


# ----------------------------------------------------------------------------------------- runner


def main() -> int:
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        with tempfile.TemporaryDirectory() as d:
            try:
                fn(Path(d))
                print(f"PASS  {name}")
            except Exception:  # noqa: BLE001
                failed += 1
                print(f"FAIL  {name}\n{traceback.format_exc()}")
            finally:
                for p in Path(d).rglob("*"):         # read-only Stage 0 folders must be writable to clean up
                    try:
                        os.chmod(p, p.stat().st_mode | stat.S_IWUSR)
                    except OSError:
                        pass
    print(f"{len(tests) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
