"""Get USAspending archive files and record them in data/manifest.csv.

Two modes, one manifest code path:

    # download a new file (not run during the FY2025 pilot)
    python -m src.download fetch --url https://files.usaspending.gov/award_data_archive/FY2024_All_Contracts_Full_20260906.zip

    # record a file that is already on disk (what the pipeline's step 1 calls)
    python -m src.download register --path /path/to/FY2025_All_Contracts_Full_20260906.zip

`register` never moves, copies, or modifies the file; it only reads it.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from datetime import date
from pathlib import Path

from . import config, inventory, manifest

# UNVERIFIED: files.usaspending.gov is reported to reject some default client
# User-Agent strings (e.g. python-requests). A browser-style UA is sent as a
# precaution. This was not tested during the pilot (no network calls were made).
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
CHUNK_BYTES = 8 * 1024 * 1024


def register(path: Path, source_url: str = "", registered_via: str = "register",
             manifest_path: Path = config.MANIFEST_PATH) -> dict:
    """Read an archive on disk and upsert its manifest row. Returns the row and the zip inventory."""
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    name = inventory.parse_archive_name(path.name)
    inv = inventory.inspect_zip(path)
    member_dates = inv["member_name_dates"]
    notes = []
    if not name["matched"]:
        notes.append("file name does not match FY####_<scope>_<Contracts|Assistance>_<Full|Delta>_YYYYMMDD.zip")
    if member_dates and name.get("data_as_of_date") and member_dates != [name["data_as_of_date"]]:
        notes.append(f"member names carry date(s) {','.join(member_dates)}, zip name carries {name['data_as_of_date']}")
    row = {
        "file_name": path.name,
        "local_path": str(path),
        "source_url": source_url,
        "size_bytes": str(path.stat().st_size),
        "sha256": inventory.sha256_of(path),
        "fiscal_year": str(name.get("fiscal_year", "")),
        "archive_scope": name.get("scope", ""),
        "archive_type": name.get("type", ""),
        "data_as_of_date": name.get("data_as_of_date", ""),
        "member_file_date": ",".join(d for d in member_dates if d),
        "date_registered": date.today().isoformat(),
        "registered_via": registered_via,
        "member_count": str(len(inv["csv_members"])),
        "column_count": str(len(inv["columns"])),
        "notes": "; ".join(notes),
    }
    saved = manifest.upsert_row(row, manifest_path)
    return {"row": saved, "inventory": inv}


def fetch(url: str, dest_dir: Path = config.DATA_DIR / "raw", expected_sha256: str | None = None,
          overwrite: bool = False, manifest_path: Path = config.MANIFEST_PATH) -> dict:
    """Stream `url` to `dest_dir/<file name>` and register it.

    Skips the download when the file is already there and its SHA-256 matches
    the expected value (given with --sha256, or recorded in the manifest).
    """
    import requests  # imported here so `register` works without network libraries

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / url.rstrip("/").rsplit("/", 1)[-1]

    if dest.exists() and not overwrite:
        if expected_sha256 is None:
            known = [r for r in manifest.read_manifest(manifest_path) if r["file_name"] == dest.name]
            expected_sha256 = known[-1]["sha256"] if known else None
        if expected_sha256 is None:
            raise FileExistsError(
                f"{dest} already exists and there is no checksum to compare it with. "
                "Pass --sha256, use `register`, or pass --overwrite to download again."
            )
        actual = inventory.sha256_of(dest)
        if actual == expected_sha256:
            print(f"{dest.name}: already present with matching SHA-256, skipping download.")
            return register(dest, source_url=url, registered_via="download", manifest_path=manifest_path)
        raise ValueError(
            f"{dest} exists but its SHA-256 {actual} does not match the expected {expected_sha256}. "
            "Not overwriting it; pass --overwrite to replace it."
        )

    part = dest.with_suffix(dest.suffix + ".part")
    h = hashlib.sha256()
    written = 0
    with requests.get(url, stream=True, timeout=(30, 300),
                      headers={"User-Agent": BROWSER_USER_AGENT}) as resp:
        resp.raise_for_status()
        expected_len = int(resp.headers.get("Content-Length", 0)) or None
        with open(part, "wb") as f:
            for chunk in resp.iter_content(chunk_size=CHUNK_BYTES):
                f.write(chunk)
                h.update(chunk)
                written += len(chunk)
    if expected_len is not None and written != expected_len:
        raise IOError(f"Download incomplete: got {written} bytes, server said {expected_len}. Left {part} in place.")
    if expected_sha256 and h.hexdigest() != expected_sha256:
        raise ValueError(f"Downloaded file SHA-256 {h.hexdigest()} != expected {expected_sha256}. Left {part} in place.")
    os.replace(part, dest)
    return register(dest, source_url=url, registered_via="download", manifest_path=manifest_path)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="mode", required=True)
    f = sub.add_parser("fetch", help="download an archive URL and register it")
    f.add_argument("--url", required=True)
    f.add_argument("--dest-dir", type=Path, default=config.DATA_DIR / "raw")
    f.add_argument("--sha256", default=None, help="expected SHA-256, if known")
    f.add_argument("--overwrite", action="store_true")
    r = sub.add_parser("register", help="record an already-downloaded archive")
    r.add_argument("--path", type=Path, required=True)
    r.add_argument("--source-url", default="")
    args = p.parse_args(argv)
    if args.mode == "fetch":
        out = fetch(args.url, args.dest_dir, args.sha256, args.overwrite)
    else:
        out = register(args.path, source_url=args.source_url)
    print(out["row"])


if __name__ == "__main__":
    main()
