"""Stage 1: the lossless mirror (Layer A) of every Stage 0 zip, with a full-row proof.

    python -m src.stage1 disk                  # projected size vs free space; changes nothing
    python -m src.stage1 build                 # every year present in Stage 0 (restartable)
    python -m src.stage1 build --fy 2015       # one year
    python -m src.stage1 report                # rewrite reports/integrity/stage1_mirror_proof.*
    python -m src.stage1 recheck               # after a move or restore: re-prove every proven year (see recheck_year)

For each CSV member, one at a time:
  1. convert: extract to data/scratch, pyarrow -> text Parquet in layer_a/fy{YYYY}/{release}/ (review S5),
     scratch file deleted;
  2. raw side: Python csv module streamed from the zip (src/audit.py) -> records, Decimal sum of
     federal_action_obligation, blank lines, and the summed MD5 fingerprint of all 297 fields (review S1);
  3. Parquet side: DuckDB over the member's Parquet -> the same three numbers, computed independently;
  4. proof row: PASS only if records, dollars and fingerprints are identical, there are no malformed
     records, no rejects, and _source_row runs 1..n. A header-only member passes with 0 = 0 (review N9).
Blank lines are not records: they are counted and reported, never turned into rows (review S3).

`_files.json` (the list of members that make up Layer A) is written only when every member of the
year passes. Any FAIL stops the run with exit code 1 (review S4). Progress is saved after every
member, so a stopped run resumes where it left off. FY2025's pilot files (old flat layout) are moved
into the new layout if, and only if, their fingerprint proof passes; otherwise they are rebuilt and
the old files are moved to layer_a/fy2025/_old/ (never deleted).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import duckdb

from . import audit, config, convert, inventory, manifest, stage0

PROOF_DIR = config.INTEGRITY_DIR / "stage1"
MONEY = config.OBLIGATION_COL
HEADROOM_BYTES = 20 * 1024**3
# Bytes of Layer A per byte of zip, for the disk check before any year is built. Measured on the 18 years of
# the 2026-09-06 release: 19.84 GB of Parquet for 27.11 GB of zips (0.732), 0.705 (FY2013) to 0.751 (FY2024)
# by year. 0.76 sits above every year, so the check never asks for less room than a real build used.
FIRST_RUN_RATIO = 0.76


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def progress_path(fy: int) -> Path:
    return PROOF_DIR / f"fy{fy}_proof.json"


def load_progress(fy: int) -> dict:
    p = progress_path(fy)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save_progress(fy: int, prog: dict) -> None:
    PROOF_DIR.mkdir(parents=True, exist_ok=True)
    tmp = progress_path(fy).with_suffix(".tmp")
    tmp.write_text(json.dumps(prog, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, progress_path(fy))


def parquet_stats(path: Path, header: list[str]) -> dict:
    """The Parquet side of the proof, computed by DuckDB with no code shared with the raw side."""
    cols = ", ".join(convert.q(c) for c in header)
    con = duckdb.connect()
    n, fp, total, bad, empty, lo, hi, distinct = con.execute(f"""
        SELECT COUNT(*),
               COALESCE(SUM(CAST(('0x' || substr(md5(concat_ws(chr(31), {cols})), 1, 16)) AS UBIGINT)), 0),
               COALESCE(SUM(TRY_CAST(NULLIF({convert.q(MONEY)}, '') AS DECIMAL(38,6))), 0),
               COUNT(*) FILTER (WHERE {convert.q(MONEY)} <> '' AND TRY_CAST({convert.q(MONEY)} AS DECIMAL(38,6)) IS NULL),
               COUNT(*) FILTER (WHERE concat_ws('', {cols}) = ''),
               MIN(_source_row), MAX(_source_row), COUNT(DISTINCT _source_row)
        FROM read_parquet({convert.parquet_list_sql([path])})""").fetchone()
    con.close()
    return {"rows": n, "fingerprint": int(fp), "obligation_sum": Decimal(total), "obligation_unparseable": bad,
            "all_empty_rows": empty, "source_row_contiguous": n == 0 or (lo == 1 and hi == n and distinct == n)}


def proof_row(fy: int, zip_sha: str, m, raw: dict, pq_: dict, conv: dict) -> dict:
    row = {
        "fiscal_year": fy, "member": m.name, "member_idx": m.index, "zip_sha256": zip_sha,
        "raw_records": raw["records"], "parquet_rows": pq_["rows"],
        "raw_dollars": str(raw["obligation_sum"]), "parquet_dollars": str(pq_["obligation_sum"]),
        "raw_fingerprint": f"{raw['fingerprint']:x}", "parquet_fingerprint": f"{pq_['fingerprint']:x}",
        "blank_lines": raw["blank_lines"], "raw_all_empty_records": raw["all_empty_records"],
        "parquet_all_empty_rows": pq_["all_empty_rows"], "wrong_field_count": raw["wrong_field_count"],
        "csv_errors": len(raw["csv_errors"]), "raw_unparseable_dollars": raw["obligation_unparseable"],
        "parquet_unparseable_dollars": pq_["obligation_unparseable"], "rejects": conv.get("rejected_rows", 0),
        "source_row_contiguous": pq_["source_row_contiguous"], "header_only_member": raw["records"] == 0,
        "parquet_file": conv["parquet"], "parquet_bytes": conv["parquet_bytes"],
        "adopted_from_pilot": conv.get("adopted", False), "checked_utc": now(),
    }
    failures = []
    if row["raw_records"] != row["parquet_rows"]:
        failures.append("row count")
    if Decimal(row["raw_dollars"]) != Decimal(row["parquet_dollars"]):
        failures.append("dollars")
    if row["raw_fingerprint"] != row["parquet_fingerprint"]:
        failures.append("fingerprint")
    if row["raw_all_empty_records"] != row["parquet_all_empty_rows"]:
        failures.append("all-empty records")
    for k in ("wrong_field_count", "csv_errors", "raw_unparseable_dollars", "parquet_unparseable_dollars", "rejects"):
        if row[k]:
            failures.append(k)
    if not row["source_row_contiguous"]:
        failures.append("_source_row not 1..n")
    row["failures"] = ";".join(failures)
    row["status"] = "FAIL" if failures else "PASS"
    return row


def check_header(inv: dict) -> None:
    ref = stage0.reference_columns()
    if not inv["headers_identical"] or inv["columns"] != ref:
        raise SystemExit(f"Stop: {inv['zip_path']} header differs from FY2025's {len(ref)} columns")


def convert_member(zip_path: Path, m, header: list[str], fy: int, out_dir: Path, log) -> dict:
    out = out_dir / (Path(m.name).stem + ".parquet")
    rejects = config.REJECTS_DIR / f"fy{fy}" / config.RELEASE_DATE / (Path(m.name).stem + ".jsonl")
    scratch = convert.extract_member(zip_path, m.name, config.SCRATCH_DIR)
    try:
        if scratch.stat().st_size != m.uncompressed_bytes:
            raise IOError(f"{m.name}: extracted {scratch.stat().st_size} bytes, zip says {m.uncompressed_bytes}")
        return convert.csv_to_layer_a(scratch, m.name, m.index, header, out, rejects)
    finally:
        scratch.unlink(missing_ok=True)


def build_year(fy: int, log=print) -> dict:
    zip_path = config.stage0_zip(fy)
    if not zip_path.is_file():
        raise SystemExit(f"FY{fy}: no Stage 0 zip at {zip_path} (pending); nothing to build")
    known = [r for r in manifest.read_manifest() if r["file_name"] == zip_path.name and r["sha256"]]
    zip_sha = known[-1]["sha256"] if known else inventory.sha256_of(zip_path)
    out_dir = config.layer_a_dir(fy)
    files_json = out_dir / "_files.json"
    prog = load_progress(fy)
    if prog.get("zip_sha256") not in (None, zip_sha):
        raise SystemExit(f"FY{fy}: saved progress is for a different zip ({prog['zip_sha256'][:12]}); "
                         f"move {progress_path(fy)} aside to rebuild")
    if files_json.exists() and prog.get("status") == "PASS":
        log(f"FY{fy}: already proven ({len(prog['members'])} members), skipping")
        return prog
    inv = inventory.inspect_zip(zip_path)
    check_header(inv)
    header = inv["columns"]
    prog.update({"fiscal_year": fy, "zip": zip_path.name, "zip_sha256": zip_sha, "release": config.RELEASE_DATE,
                 "columns": len(header), "status": "IN PROGRESS"})
    prog.setdefault("members", {})
    prog.setdefault("started_utc", now())
    out_dir.mkdir(parents=True, exist_ok=True)
    legacy = config.layer_a_legacy_dir(fy)
    t_year = time.time()
    for m in inv["csv_members"]:
        done = prog["members"].get(m.name)
        target = out_dir / (Path(m.name).stem + ".parquet")
        if done and done["status"] == "PASS" and target.exists():
            log(f"  FY{fy} [{m.index}/{len(inv['csv_members'])}] {m.name}: already PASS")
            continue
        t0 = time.time()
        old = legacy / target.name
        conv = None
        if old.is_file() and not target.exists():
            log(f"  FY{fy} [{m.index}] {m.name}: checking the pilot's existing Layer A file before adopting it")
            conv = {"parquet": str(old), "parquet_bytes": old.stat().st_size, "adopted": True}
        else:
            log(f"  FY{fy} [{m.index}/{len(inv['csv_members'])}] converting {m.name} ({m.uncompressed_bytes / 1e9:.2f} GB)")
            try:
                conv = convert_member(zip_path, m, header, fy, out_dir, log)
            except RuntimeError as e:          # pyarrow rejected rows: the member is not published
                row = {"fiscal_year": fy, "member": m.name, "member_idx": m.index, "zip_sha256": zip_sha,
                       "status": "FAIL", "failures": f"conversion stopped: {e}", "checked_utc": now(),
                       "raw_records": 0, "parquet_rows": 0, "raw_dollars": "0", "parquet_dollars": "0",
                       "raw_fingerprint": "", "parquet_fingerprint": "", "blank_lines": 0, "rejects": 1}
                prog["members"][m.name], prog["status"] = row, "FAIL"
                save_progress(fy, prog)
                log(f"    FAIL: {e}")
                return prog
        raw = audit.audit_zip(zip_path, [m], header, sample_size=0, log=lambda *_: None)["members"][0]
        stats = parquet_stats(Path(conv["parquet"]), header)
        row = proof_row(fy, zip_sha, m, raw, stats, conv)
        if conv.get("adopted"):
            if row["status"] == "PASS":
                os.rename(old, target)                      # same folder tree: a rename, never a copy
                row["parquet_file"] = str(target)
            else:
                log(f"    pilot file failed its proof ({row['failures']}); moving it to _old/ and rebuilding")
                (legacy / "_old").mkdir(exist_ok=True)
                os.rename(old, legacy / "_old" / old.name)
                conv = convert_member(zip_path, m, header, fy, out_dir, log)
                row = proof_row(fy, zip_sha, m, raw, parquet_stats(Path(conv["parquet"]), header), conv)
        row["seconds"] = round(time.time() - t0, 1)
        prog["members"][m.name] = row
        save_progress(fy, prog)
        log(f"    {row['status']}: {row['raw_records']:,} records, fingerprint {'=' if row['raw_fingerprint'] == row['parquet_fingerprint'] else '!='}, "
            f"blank lines {row['blank_lines']} ({row['seconds']}s)" + (f"  FAILURES: {row['failures']}" if row["failures"] else ""))
        if row["status"] != "PASS":
            prog["status"] = "FAIL"
            save_progress(fy, prog)
            return prog
    members = [prog["members"][m.name] for m in inv["csv_members"]]
    prog["status"] = "PASS" if all(r["status"] == "PASS" for r in members) else "FAIL"
    prog["finished_utc"] = now()
    prog["seconds_this_run"] = round(time.time() - t_year, 1)
    if prog["status"] == "PASS":
        listing = {"fiscal_year": fy, "release": config.RELEASE_DATE, "zip": zip_path.name, "zip_sha256": zip_sha,
                   "columns": header, "written_utc": now(),
                   "members": [{"member": r["member"], "member_idx": r["member_idx"],
                                "parquet": Path(r["parquet_file"]).name, "rows": r["parquet_rows"],
                                "bytes": (out_dir / Path(r["parquet_file"]).name).stat().st_size,  # the folder, not a
                                "proof": r["status"]} for r in members]}                            # recorded absolute path
        tmp = files_json.with_suffix(".tmp")
        tmp.write_text(json.dumps(listing, indent=1), encoding="utf-8")
        os.replace(tmp, files_json)
        manifest.upsert_row({"file_name": zip_path.name, "sha256": zip_sha,
                             "row_count": str(sum(r["raw_records"] for r in members)),
                             "obligation_total": str(sum(Decimal(r["raw_dollars"]) for r in members))})
    save_progress(fy, prog)
    if legacy.exists() and not any(legacy.glob("*.parquet")) and prog["status"] == "PASS":
        log(f"  FY{fy}: the pilot's flat folder no longer holds Parquet files (all moved into {out_dir.name}/)")
    return prog


def layer_a_files(fy: int) -> list[Path]:
    """The Parquet files that make up a proven year (from _files.json, never a glob)."""
    listing = json.loads((config.layer_a_dir(fy) / "_files.json").read_text(encoding="utf-8"))
    return [config.layer_a_dir(fy) / x["parquet"] for x in listing["members"]]


def no_zips_message() -> str:
    return (f"No Stage 0 zips found in {config.RELEASE_DIR}. Put the yearly zips in place first: "
            "python -m src.stage0 organize --source <folder holding the zips>. Nothing was built.")


def nearest_existing(path: Path) -> Path:
    while not path.exists():
        path = path.parent
    return path


def disk_check(log=print) -> dict:
    present = config.years_present()
    if not present:
        raise SystemExit(no_zips_message())
    built = [fy for fy in present if (config.layer_a_dir(fy) / "_files.json").exists()]
    layer_a = {fy: sum(p.stat().st_size for p in config.layer_a_dir(fy).glob("*.parquet")) for fy in built}
    if built:                                       # scale by what this machine has already built
        ref_bytes, ref_zip = sum(layer_a.values()), sum(config.stage0_zip(fy).stat().st_size for fy in built)
        ratio = ref_bytes / ref_zip
        basis = (f"{len(built)} built year(s): {ref_bytes:,} bytes of Layer A for {ref_zip:,} bytes of zips "
                 f"({ratio:.3f}), scaled by each zip's size")
    else:                                           # a first run: the ratio measured on the 18 years we built
        ratio = FIRST_RUN_RATIO
        basis = (f"no year built yet: {FIRST_RUN_RATIO} bytes of Layer A per zip byte (measured 0.705 to 0.751 by "
                 "year, 0.732 overall), scaled by each zip's size")
    projected, rows = 0, []
    for fy in present:
        done = fy in built
        size = layer_a[fy] if done else int(ratio * config.stage0_zip(fy).stat().st_size)
        rows.append({"fiscal_year": fy, "built": done, "layer_a_bytes": size})
        projected += 0 if done else size
    largest_member = max(i.file_size for fy in present
                         for i in __import__("zipfile").ZipFile(config.stage0_zip(fy)).infolist())
    free = shutil.disk_usage(nearest_existing(config.DATA_DIR)).free     # data/ may not exist yet on a fresh clone
    need = projected + largest_member + HEADROOM_BYTES
    res = {"free_bytes": free, "projected_new_layer_a_bytes": projected, "largest_member_bytes": largest_member,
           "headroom_bytes": HEADROOM_BYTES, "need_bytes": need, "ok": free > need, "per_year": rows, "basis": basis}
    log(f"Disk: {free / 1e9:.0f} GB free; projected new Layer A {projected / 1e9:.1f} GB + largest extracted member "
        f"{largest_member / 1e9:.1f} GB + 20 GB headroom = {need / 1e9:.1f} GB -> {'OK' if res['ok'] else 'TOO TIGHT'}")
    return res


def write_report(log=print) -> None:
    rows, years = [], []
    for fy in config.years_in_scope():
        prog = load_progress(fy)
        if not prog:
            years.append({"fiscal_year": fy, "status": "pending - not yet downloaded" if fy in config.years_pending()
                          else "not built"})
            continue
        ms = list(prog["members"].values())
        rows += ms
        lay = config.layer_a_dir(fy)
        years.append({"fiscal_year": fy, "status": prog["status"], "members": len(ms),
                      "raw_records": sum(r["raw_records"] for r in ms), "parquet_rows": sum(r["parquet_rows"] for r in ms),
                      "raw_dollars": str(sum(Decimal(r["raw_dollars"]) for r in ms)),
                      "parquet_dollars": str(sum(Decimal(r["parquet_dollars"]) for r in ms)),
                      "fingerprints_equal": all(r["raw_fingerprint"] == r["parquet_fingerprint"] for r in ms),
                      "blank_lines": sum(r["blank_lines"] for r in ms), "rejects": sum(r["rejects"] for r in ms),
                      "adopted_from_pilot": sum(1 for r in ms if r.get("adopted_from_pilot")),
                      "layer_a_bytes": sum(p.stat().st_size for p in lay.glob("*.parquet")) if lay.exists() else 0})
    out = config.INTEGRITY_REPORTS_DIR
    out.mkdir(parents=True, exist_ok=True)
    fields = ["fiscal_year", "member", "status", "failures", "raw_records", "parquet_rows", "raw_dollars", "parquet_dollars",
              "raw_fingerprint", "parquet_fingerprint", "blank_lines", "raw_all_empty_records", "parquet_all_empty_rows",
              "wrong_field_count", "csv_errors", "rejects", "source_row_contiguous", "header_only_member",
              "adopted_from_pilot", "parquet_bytes", "zip_sha256", "checked_utc"]
    with open(out / "stage1_mirror_proof.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["fiscal_year"], r["member_idx"])))
    built = [y for y in years if "members" in y]
    total_bytes = sum(y["layer_a_bytes"] for y in built)
    lines = ["# Stage 1 proof: the Layer A mirror equals the raw zips, row by row", "",
             f"Generated {now()} by `python -m src.stage1 report`. One row per member is in `stage1_mirror_proof.csv`.", "",
             "**How it is proven.** For every CSV member, two independent readers compute the same three numbers:",
             "- **raw side:** Python's `csv` module, streamed straight from the zip;",
             "- **Parquet side:** DuckDB over the member's Parquet file.", "",
             "The three numbers:",
             "1. the number of records;",
             "2. the exact Decimal sum of `federal_action_obligation`;",
             "3. a fingerprint of every row: the sum, over all records, of the first 16 hex digits of the MD5 of the "
             "record's 297 fields joined by U+001F.", "",
             "A member passes only if all three are identical, with no malformed records and no rejects, and with `_source_row` running 1..n. "
             "Blank lines are not records: they are counted here and never become rows.", "",
             f"- Years proven: {sum(1 for y in built if y['status'] == 'PASS')} PASS, "
             f"{sum(1 for y in built if y['status'] != 'PASS')} not PASS, "
             f"pending: {', '.join('FY' + str(y['fiscal_year']) for y in years if y['status'].startswith('pending')) or 'none'}.",
             f"- Layer A on disk: {total_bytes / 1e9:.2f} GB ({total_bytes:,} bytes).", "",
             "| FY | Status | Members | Raw records | Parquet rows | Raw dollars | Parquet dollars | Fingerprints equal | "
             "Blank lines | Rejects | Pilot files adopted | Layer A GB |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for y in years:
        if "members" not in y:
            lines.append(f"| {y['fiscal_year']} | {y['status']} | | | | | | | | | | |")
            continue
        lines.append(f"| {y['fiscal_year']} | **{y['status']}** | {y['members']} | {y['raw_records']:,} | {y['parquet_rows']:,} | "
                     f"${Decimal(y['raw_dollars']):,.2f} | ${Decimal(y['parquet_dollars']):,.2f} | "
                     f"{'yes' if y['fingerprints_equal'] else '**no**'} | {y['blank_lines']} | {y['rejects']} | "
                     f"{y['adopted_from_pilot']} | {y['layer_a_bytes'] / 1e9:.2f} |")
    (out / "stage1_mirror_proof.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"  report -> {out / 'stage1_mirror_proof.md'}")


def recheck_year(fy: int, log=print) -> dict:
    """Re-prove a proven year without re-reading its CSVs, e.g. after the project folder moved.

    The zip's SHA-256 must still equal the one in the proof, so the raw side recorded there still describes
    the zip byte for byte. The Parquet side is then recomputed for every member (rows, exact dollars, full-row
    fingerprint, _source_row 1..n, file size) and compared with the recorded raw side. Nothing is written."""
    prog = load_progress(fy)
    listing = json.loads((config.layer_a_dir(fy) / "_files.json").read_text(encoding="utf-8"))
    problems = []
    if prog.get("status") != "PASS":
        problems.append("proof status is not PASS")
    zip_sha = inventory.sha256_of(config.stage0_zip(fy))
    if not zip_sha == prog.get("zip_sha256") == listing["zip_sha256"]:
        problems.append("zip SHA-256 differs from the proof")
    rows = 0
    for m in listing["members"]:
        rec, path = prog["members"][m["member"]], config.layer_a_dir(fy) / m["parquet"]
        if not path.exists():
            problems.append(f"{m['parquet']}: missing")
            continue
        st = parquet_stats(path, listing["columns"])
        rows += st["rows"]
        diffs = [name for name, ok in (
            ("rows", st["rows"] == rec["raw_records"]), ("dollars", st["obligation_sum"] == Decimal(rec["raw_dollars"])),
            ("fingerprint", f"{st['fingerprint']:x}" == rec["raw_fingerprint"]),
            ("_source_row", st["source_row_contiguous"]), ("file size", path.stat().st_size == m["bytes"])) if not ok]
        if diffs:
            problems.append(f"{m['parquet']}: {', '.join(diffs)} differ")
    out = {"fiscal_year": fy, "members": len(listing["members"]), "rows": rows,
           "status": "PASS" if not problems else "FAIL", "problems": problems, "checked_utc": now()}
    log(f"FY{fy}: {out['status']} ({out['members']} members, {rows:,} rows){'; ' + '; '.join(problems) if problems else ''}")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="mode", required=True)
    b = sub.add_parser("build")
    b.add_argument("--fy", type=int, action="append", help="fiscal year(s); default: every year in Stage 0")
    sub.add_parser("report")
    sub.add_parser("disk")
    r = sub.add_parser("recheck")
    r.add_argument("--fy", type=int, action="append", help="fiscal year(s); default: every proven year")
    a = p.parse_args(argv)
    if a.mode in ("report", "recheck") and not any(progress_path(fy).exists() for fy in config.years_in_scope()):
        print(f"No Stage 1 year has been built on this machine ({PROOF_DIR} holds no proof), so there is nothing to "
              "report or recheck, and the committed report was left as it is. Build first: python -m src.stage1 build")
        return 1
    if a.mode == "report":
        write_report()
        return 0
    if a.mode == "recheck":
        years = a.fy or [fy for fy in config.years_present() if (config.layer_a_dir(fy) / "_files.json").exists()]
        if not years:
            print("No proven Stage 1 year has its zip in Stage 0, so there is nothing to recheck.")
            return 1
        res = [recheck_year(fy, log=lambda s: print(s, flush=True)) for fy in sorted(years)]
        (PROOF_DIR / "recheck.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
        bad = [r["fiscal_year"] for r in res if r["status"] != "PASS"]
        print(f"Recheck: {len(res) - len(bad)} of {len(res)} years PASS" + (f"; FAIL: {bad}" if bad else ""))
        return 1 if bad else 0
    disk = disk_check()
    if a.mode == "disk":
        return 0 if disk["ok"] else 1
    if not disk["ok"]:
        print("Stop: disk space is tight; nothing built.")
        return 1
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    years = a.fy or config.years_present()
    status = {}
    for fy in sorted(years, reverse=True):
        prog = build_year(fy, log=lambda s: print(s, flush=True))
        status[fy] = prog["status"]
        write_report()
        if prog["status"] != "PASS":
            print(f"STOP: FY{fy} did not pass; later years not started. See {progress_path(fy)}")
            return 1
    print("Stage 1:", ", ".join(f"FY{fy} {s}" for fy, s in sorted(status.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
