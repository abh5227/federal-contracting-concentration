"""Stage 0: verify the raw archive zips, then move them into the release folder.

    python -m src.stage0 verify   --source ~/Downloads            # read-only: checks only, prints a table
    python -m src.stage0 organize --source ~/Downloads --source "<Project/DATA>"
    python -m src.stage0 organize --source ~/Downloads --only-fy 2015   # add one year later
    python -m src.stage0 report                                    # rewrite reports/integrity/stage0_inventory.*

Every zip is checked BEFORE it is moved:
  SHA-256 of the zip; every member read in full (zipfile checks CRC-32 on a full
  read) with its byte count compared to the directory; strict UTF-8 decoding of
  every byte; BOM; the CSV header compared with FY2025's 297 columns
  (reports/columns_fy2025.txt); header-only members; member names' dates.

Moving: same-volume rename only (os.rename never copies, so nothing is ever
deleted). The moved file is re-hashed (by `download.register`, which also writes
its manifest row) and must have the same SHA-256. Then the zip is made read-only
(chmod a-w); after all moves, the release folder is too. Undo with `chmod u+w`.

In-scope years without a zip (pending years) get a manifest placeholder row with
no SHA-256, marked "pending - not yet downloaded". FY2026 (and any other year
outside FIRST_FY..LAST_FY) goes to RELEASE_DIR/_out_of_scope and is recorded as
"out of scope - not a pipeline input". Restartable: a zip already in place with
the same SHA-256 is skipped.
"""

from __future__ import annotations

import argparse
import codecs
import csv
import json
import os
import re
import stat
import sys
import zipfile
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from . import config, download, inventory, manifest

VERIFY_DIR = config.INTEGRITY_DIR / "stage0"
CHUNK = 8 * 1024 * 1024
BOM = codecs.BOM_UTF8
PENDING_NOTE = "PENDING - not yet downloaded"
OUT_OF_SCOPE_NOTE = "out of scope - not a pipeline input"
ZIP_RE = re.compile(r"^FY(\d{4})_All_Contracts_Full_(\d{8})\.zip$")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def reference_columns() -> list[str]:
    lines = config.REFERENCE_COLUMNS_FILE.read_text(encoding="utf-8").splitlines()
    return [ln.split("\t", 1)[1] for ln in lines if ln and not ln.startswith("#")]


def header_diff(header: list[str], ref: list[str]) -> dict:
    return {"identical": header == ref, "columns": len(header),
            "missing": [c for c in ref if c not in header], "extra": [c for c in header if c not in ref],
            "same_set_different_order": header != ref and sorted(header) == sorted(ref)}


def verify_member(zf: zipfile.ZipFile, info: zipfile.ZipInfo, ref: list[str]) -> dict:
    """Read one member in full: CRC (by zipfile), byte count, strict UTF-8, BOM, header, data after header."""
    out = {"member": info.filename, "compressed_bytes": info.compress_size, "uncompressed_bytes": info.file_size,
           "crc32": f"{info.CRC:08x}", "zip_entry_modified": "%04d-%02d-%02d %02d:%02d:%02d" % info.date_time}
    m = inventory.MEMBER_NAME_RE.match(info.filename)
    out["name_fy"], out["name_date"] = (m["fy"], m["date"]) if m else (None, None)
    dec = codecs.getincrementaldecoder("utf-8")("strict")
    read, newlines, first_nl, first = 0, 0, None, b""
    try:
        with zf.open(info) as f:                 # a full read makes zipfile verify the CRC-32
            while block := f.read(CHUNK):
                if not first:
                    first = block[:1024 * 1024]      # the header line (297 names, ~9 KB) and BOM
                if first_nl is None and (i := block.find(b"\n")) >= 0:
                    first_nl = read + i
                newlines += block.count(b"\n")
                dec.decode(block)
                read += len(block)
            dec.decode(b"", final=True)
        out["crc_ok"], out["utf8_ok"], out["error"] = True, True, None
    except zipfile.BadZipFile as e:
        out["crc_ok"], out["utf8_ok"], out["error"] = False, None, f"BadZipFile: {e}"
    except UnicodeDecodeError as e:
        out["crc_ok"], out["utf8_ok"], out["error"] = None, False, f"UnicodeDecodeError at byte {read + e.start}: {e.reason}"
    out["bytes_read"] = read
    out["size_ok"] = read == info.file_size
    out["bom"] = first.startswith(BOM)
    out["newlines"] = newlines
    if info.filename.lower().endswith(".csv"):
        line = first[: first_nl if first_nl is not None else len(first)].rstrip(b"\r")
        header = next(csv.reader([line.decode("utf-8", "replace")]), [])
        out["header"] = header_diff(header, ref)
        out["header_only"] = first_nl is None or read - (first_nl + 1) == 0
    return out


def verify_zip(path: Path) -> dict:
    path = Path(path)
    ref = reference_columns()
    m = ZIP_RE.match(path.name)
    res = {"file_name": path.name, "path": str(path), "verified_utc": now(), "size_bytes": path.stat().st_size,
           "fiscal_year": int(m[1]) if m else None, "name_date": m[2] if m else None,
           "sha256": inventory.sha256_of(path)}
    try:
        with zipfile.ZipFile(path) as zf:
            infos = zf.infolist()
            res["members"] = [verify_member(zf, i, ref) for i in infos]
    except zipfile.BadZipFile as e:
        res["members"], res["open_error"] = [], str(e)
    csvs = [x for x in res["members"] if x["member"].lower().endswith(".csv")]
    res["member_count"] = len(res["members"])
    res["csv_member_count"] = len(csvs)
    res["non_csv_members"] = [x["member"] for x in res["members"] if not x["member"].lower().endswith(".csv")]
    res["member_name_dates"] = sorted({x["name_date"] for x in csvs if x["name_date"]})
    res["member_name_fys"] = sorted({x["name_fy"] for x in csvs if x["name_fy"]})
    res["all_crc_ok"] = bool(csvs) and all(x["crc_ok"] and x["size_ok"] for x in res["members"])
    res["all_utf8_ok"] = bool(csvs) and all(x["utf8_ok"] for x in csvs)
    res["any_bom"] = any(x["bom"] for x in csvs)
    res["headers_match_fy2025"] = bool(csvs) and all(x["header"]["identical"] for x in csvs)
    res["header_only_members"] = [x["member"] for x in csvs if x["header_only"]]
    problems = []
    if "open_error" in res:
        problems.append(f"zip does not open: {res['open_error']}")
    if not m:
        problems.append("file name is not FY####_All_Contracts_Full_YYYYMMDD.zip")
    elif m[2] != config.RELEASE_DATE:
        problems.append(f"release date {m[2]} is not {config.RELEASE_DATE}")
    if m and res["member_name_fys"] != [m[1]]:
        problems.append(f"member names carry fiscal year(s) {res['member_name_fys']}")
    if not res["all_crc_ok"]:
        problems.append("a member failed its CRC or size check")
    if not res["all_utf8_ok"]:
        problems.append("a member is not valid UTF-8")
    if res["non_csv_members"]:
        problems.append(f"non-CSV members: {res['non_csv_members']}")
    res["problems"] = problems
    res["column_differences"] = [] if res["headers_match_fy2025"] else [
        {"member": x["member"], **x["header"]} for x in csvs if not x["header"]["identical"]]
    return res


def save_verification(res: dict) -> Path:
    VERIFY_DIR.mkdir(parents=True, exist_ok=True)
    out = VERIFY_DIR / f"{Path(res['file_name']).stem}.json"
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    return out


def find_zips(sources: list[Path], only_fy: set[int] | None = None) -> list[Path]:
    found = []
    for src in sources:
        for p in sorted(Path(src).expanduser().glob("FY*_All_Contracts_Full_*.zip")):
            m = ZIP_RE.match(p.name)
            if p.is_file() and m and (only_fy is None or int(m[1]) in only_fy):
                found.append(p)
    return found


def no_zips_message(sources: list[Path], only_fy: set[int] | None = None) -> str:
    missing = [str(s) for s in sources if not Path(s).expanduser().is_dir()]
    years = f" for FY{', FY'.join(str(fy) for fy in sorted(only_fy))}" if only_fy else ""
    return (f"Stop: no zip named like FY2025_All_Contracts_Full_20260906.zip{years} in "
            f"{', '.join(str(s) for s in sources)}"
            + (f" (not a folder: {', '.join(missing)})" if missing else "") + ".")


def verify_many(paths: list[Path], workers: int = 4) -> list[dict]:
    with ProcessPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(verify_zip, paths))
    for r in results:
        save_verification(r)
    return results


def make_read_only(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def make_writable_by_owner(path: Path) -> None:
    path.chmod(path.stat().st_mode | stat.S_IWUSR)


def destination(fy: int) -> tuple[Path, bool]:
    in_scope = config.FIRST_FY <= fy <= config.LAST_FY
    folder = config.RELEASE_DIR if in_scope else config.OUT_OF_SCOPE_DIR
    return folder / config.archive_name(fy), in_scope


def fill_placeholder(file_name: str) -> None:
    """Drop the 'pending' placeholder for a year once its real file is registered (metadata only)."""
    rows = manifest.read_manifest()
    kept = [r for r in rows if not (r["file_name"] == file_name and r["sha256"] == "" and r["registered_via"] == "pending")]
    if len(kept) != len(rows):
        manifest._write_manifest(kept, config.MANIFEST_PATH)


def ensure_placeholders() -> None:
    present = {r["file_name"] for r in manifest.read_manifest() if r["sha256"]}
    for fy in config.years_pending():
        name = config.archive_name(fy)
        if name not in present:
            manifest.upsert_row({"file_name": name, "sha256": "", "fiscal_year": str(fy), "archive_scope": "All",
                                 "archive_type": "Full", "data_as_of_date": "2026-09-06",
                                 "source_url": config.ARCHIVE_URL_BASE + name, "registered_via": "pending",
                                 "date_registered": datetime.now().date().isoformat(), "notes": PENDING_NOTE})


def organize(sources: list[Path], only_fy: set[int] | None = None, log=print) -> list[dict]:
    """Verify, then move into Stage 0, re-hash, register, make read-only. Stops on any verification problem."""
    paths = find_zips(sources, only_fy)
    if not paths:                                   # a mistyped --source must not rewrite the inventory or the manifest
        raise SystemExit(no_zips_message(sources, only_fy) + " Nothing was moved or written.")
    by_fy: dict[int, list[Path]] = {}
    for p in paths:
        by_fy.setdefault(int(ZIP_RE.match(p.name)[1]), []).append(p)
    dupes = {fy: [str(p) for p in ps] for fy, ps in by_fy.items() if len(ps) > 1}
    if dupes:
        raise SystemExit(f"Stop: more than one zip for a year: {dupes}")
    log(f"Verifying {len(paths)} zip(s) before moving anything ...")
    results = verify_many(paths)
    bad = {r["file_name"]: r["problems"] for r in results if r["problems"]}
    if bad:
        raise SystemExit(f"Stop: verification problems, nothing moved: {json.dumps(bad, indent=1)}")
    for folder in (config.RELEASE_DIR, config.OUT_OF_SCOPE_DIR):
        if folder.exists():
            make_writable_by_owner(folder)
    config.OUT_OF_SCOPE_DIR.mkdir(parents=True, exist_ok=True)
    moved = []
    try:
        for r in sorted(results, key=lambda r: r["fiscal_year"]):
            src = Path(r["path"])
            dest, in_scope = destination(r["fiscal_year"])
            if dest.exists():
                if inventory.sha256_of(dest) != r["sha256"]:
                    raise SystemExit(f"Stop: {dest} already exists with a different SHA-256; not touching either file")
                if src.resolve() != dest.resolve():
                    raise SystemExit(f"Stop: {dest} is already in place and {src} is a second identical copy; "
                                     "leaving both for you to decide")
            else:
                if src.stat().st_dev != dest.parent.stat().st_dev:
                    raise SystemExit(f"Stop: {src} is on a different volume; a move would need copy + delete")
                os.rename(src, dest)                  # same volume: a rename, never a copy
            reg = download.register(dest, source_url=config.ARCHIVE_URL_BASE + dest.name)
            if reg["row"]["sha256"] != r["sha256"]:
                raise SystemExit(f"Stop: SHA-256 of {dest} changed after the move "
                                 f"({r['sha256']} -> {reg['row']['sha256']})")
            if not in_scope:
                manifest.upsert_row({"file_name": dest.name, "sha256": r["sha256"], "registered_via": "out_of_scope",
                                     "notes": OUT_OF_SCOPE_NOTE})
            fill_placeholder(dest.name)
            make_read_only(dest)
            r.update({"moved_from": str(src), "stage0_path": str(dest), "sha256_after_move": reg["row"]["sha256"],
                      "in_scope": in_scope})
            save_verification(r)
            moved.append(r)
            log(f"  FY{r['fiscal_year']}: {'Stage 0' if in_scope else 'out of scope'} <- {src}  (SHA-256 unchanged)")
    finally:
        ensure_placeholders()
        for folder in (config.OUT_OF_SCOPE_DIR, config.RELEASE_DIR):
            if folder.exists():
                make_read_only(folder)
    still_writable = [str(p) for p in [config.RELEASE_DIR, config.OUT_OF_SCOPE_DIR, *config.RELEASE_DIR.glob("*.zip"),
                                       *config.OUT_OF_SCOPE_DIR.glob("*.zip")] if p.stat().st_mode & 0o222]
    if still_writable:     # seen once: a background run left the folders writable; never pass that silently
        raise SystemExit(f"Stop: still writable after chmod a-w: {still_writable}. Run: chmod a-w <each path>")
    write_report(log=log)
    return moved


def write_report(log=print) -> None:
    """reports/integrity/stage0_inventory.md and .csv: one row per fiscal year, in scope or not."""
    verified = {}
    if VERIFY_DIR.exists():
        for p in VERIFY_DIR.glob("*.json"):
            r = json.loads(p.read_text(encoding="utf-8"))
            if r.get("stage0_path"):
                verified[r["fiscal_year"]] = r
    years = sorted(set(config.years_in_scope()) | set(verified))
    rows = []
    for fy in years:
        r = verified.get(fy)
        in_scope = config.FIRST_FY <= fy <= config.LAST_FY
        if r is None:
            rows.append({"fiscal_year": fy, "status": "pending - not yet downloaded" if in_scope else "", "file_name":
                         config.archive_name(fy)})
            continue
        rows.append({
            "fiscal_year": fy, "status": "stage 0" if in_scope else OUT_OF_SCOPE_NOTE,
            "file_name": r["file_name"], "size_bytes": r["size_bytes"], "sha256": r["sha256"],
            "sha256_unchanged_after_move": r["sha256_after_move"] == r["sha256"],
            "csv_members": r["csv_member_count"], "non_csv_members": len(r["non_csv_members"]),
            "uncompressed_bytes": sum(m["uncompressed_bytes"] for m in r["members"]),
            "all_crc_ok": r["all_crc_ok"], "all_utf8_ok": r["all_utf8_ok"], "any_bom": r["any_bom"],
            "headers_match_fy2025": r["headers_match_fy2025"],
            "header_only_members": len(r["header_only_members"]),
            "member_name_dates": ";".join(r["member_name_dates"]),
            "verified_utc": r["verified_utc"],
        })
    out_dir = config.INTEGRITY_REPORTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    fields = ["fiscal_year", "status", "file_name", "size_bytes", "sha256", "sha256_unchanged_after_move",
              "csv_members", "non_csv_members", "uncompressed_bytes", "all_crc_ok", "all_utf8_ok", "any_bom",
              "headers_match_fy2025", "header_only_members", "member_name_dates", "verified_utc"]
    with open(out_dir / "stage0_inventory.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    in_scope_rows = [r for r in rows if r["status"] == "stage 0"]
    lines = [
        "# Stage 0 inventory: release 2026-09-06", "",
        f"Generated {now()} by `python -m src.stage0 report`. Folder: `{config.RELEASE_DIR.name}/` under "
        "`Project/DATA/raw/award_data_archive/` (read-only). Every check below ran before the file was moved; "
        "the SHA-256 was recomputed after the move.", "",
        f"- In Stage 0: {len(in_scope_rows)} of {len(config.years_in_scope())} fiscal years "
        f"({config.FIRST_FY}-{config.LAST_FY}).",
        f"- Pending (not yet downloaded): {', '.join(f'FY{r['fiscal_year']}' for r in rows if r['status'].startswith('pending')) or 'none'}.",
        f"- Out of scope (kept, not processed): {', '.join(f'FY{r['fiscal_year']}' for r in rows if r['status'] == OUT_OF_SCOPE_NOTE) or 'none'}.",
        f"- All in-scope files: CRC ok {all(r['all_crc_ok'] for r in in_scope_rows)}, UTF-8 ok "
        f"{all(r['all_utf8_ok'] for r in in_scope_rows)}, BOM {any(r['any_bom'] for r in in_scope_rows)}, "
        f"headers identical to FY2025 {all(r['headers_match_fy2025'] for r in in_scope_rows)}, header-only members "
        f"{sum(r['header_only_members'] for r in in_scope_rows)}, SHA-256 unchanged by the move "
        f"{all(r['sha256_unchanged_after_move'] for r in in_scope_rows)}.", "",
        "| FY | Status | File | Size (bytes) | SHA-256 (first 16) | CSV members | Uncompressed GB | CRC | UTF-8 | BOM | "
        "Header = FY2025 | Header-only | Member-name dates |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if "sha256" not in r:
            lines.append(f"| {r['fiscal_year']} | {r['status']} | {r['file_name']} | | | | | | | | | | |")
            continue
        lines.append(f"| {r['fiscal_year']} | {r['status']} | {r['file_name']} | {r['size_bytes']:,} | "
                     f"`{r['sha256'][:16]}` | {r['csv_members']} | {r['uncompressed_bytes'] / 1e9:.2f} | "
                     f"{'ok' if r['all_crc_ok'] else 'FAIL'} | {'ok' if r['all_utf8_ok'] else 'FAIL'} | "
                     f"{'yes' if r['any_bom'] else 'no'} | {'yes' if r['headers_match_fy2025'] else '**no**'} | "
                     f"{r['header_only_members']} | {r['member_name_dates']} |")
    lines += ["", "Full SHA-256 values are in `stage0_inventory.csv` and `data/manifest.csv`. Member names carry "
              "20260906 or 20260907 while every zip name carries 20260906; FY2025, checked in the pilot, does the same."]
    (out_dir / "stage0_inventory.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"  report -> {out_dir / 'stage0_inventory.md'}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="mode", required=True)
    for name in ("verify", "organize"):
        s = sub.add_parser(name)
        s.add_argument("--source", type=Path, action="append", required=True)
        s.add_argument("--only-fy", type=int, action="append")
    sub.add_parser("report")
    a = p.parse_args(argv)
    if a.mode == "report":
        write_report()
        return 0
    only = set(a.only_fy) if a.only_fy else None
    if a.mode == "verify":
        paths = find_zips(a.source, only)
        if not paths:
            print(no_zips_message(a.source, only) + " Nothing was checked.", file=sys.stderr)
            return 1
        res = verify_many(paths)
        for r in sorted(res, key=lambda r: r["fiscal_year"] or 0):
            print(f"FY{r['fiscal_year']} {r['file_name']}: crc={r['all_crc_ok']} utf8={r['all_utf8_ok']} "
                  f"bom={r['any_bom']} header=FY2025:{r['headers_match_fy2025']} header_only={r['header_only_members']} "
                  f"problems={r['problems']}")
        return 1 if any(r["problems"] for r in res) else 0
    organize(a.source, only)
    return 0


if __name__ == "__main__":
    sys.exit(main())
