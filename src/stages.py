"""One command per routine job across the stages (docs/data_stages.md).

    # add a year that was pending (FY2015), once its zip is downloaded, e.g. into ~/Downloads:
    caffeinate -i .venv/bin/python -m src.stages add-year --fy 2015 --source ~/Downloads

    # rebuild everything that is missing (restartable; finished work is skipped):
    caffeinate -i .venv/bin/python -m src.stages refresh

add-year runs, in order, stopping at the first failure (non-zero exit):
  1. Stage 0: verify the zip (SHA-256, CRC of every member, UTF-8, header = FY2025's 297 columns, release
     date 20260906), move it into the read-only release folder, re-hash, register it in data/manifest.csv
     (replacing the year's "pending" placeholder) and make it read-only again;
  2. Stage 1: convert it to the Layer A mirror and prove it row by row (reports/integrity/stage1_mirror_proof.*);
  3. Stage 2: that year's flags and profiles;
  4. cross-year results (keys across years, agency and sub-agency matrices, label changes, parent test),
     then the reports in reports/integrity/ and new "proposed" decisions for newly fired flags;
  5. no report PDF. Every report PDF is a frozen version, so the run ends by logging the command that builds
     the latest integrity report to a path you choose.
Restart the dashboard (python -m viewer.server) to see the new year.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config, integrity_report, stage0, stage1, stage2


def refresh(log=print) -> int:
    if not config.years_present():
        log(stage1.no_zips_message())
        return 1
    disk = stage1.disk_check(log)
    if not disk["ok"]:
        log("Stop: disk space is tight.")
        return 1
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    for fy in sorted(config.years_present(), reverse=True):
        prog = stage1.build_year(fy, log)
        stage1.write_report(log)
        if prog["status"] != "PASS":
            log(f"STOP: FY{fy} failed its Stage 1 proof; nothing after it was run. See {stage1.progress_path(fy)}")
            return 1
    for fy in sorted(config.years_present(), reverse=True):
        stage2.build_year(fy, log)
    stage2.build_cross(log)
    integrity_report.main([])
    from viewer.health import prefill_decisions
    prefill_decisions(log)
    stage0.write_report(log)
    # Every report PDF in reports/ is a frozen version, so refresh rewrites none of them (none of the data steps
    # above needs one). It only says how to build the latest integrity report somewhere new.
    log("Report PDFs are frozen and were not rebuilt. To build the latest integrity report, run: "
        ".venv/bin/python -m src.report_pdf --in docs/integrity_findings_v3.md --out <path of your choice>.pdf")
    return 0


def add_year(fy: int, source: Path, log=print) -> int:
    if not config.FIRST_FY <= fy <= config.LAST_FY:
        log(f"FY{fy} is outside {config.FIRST_FY}-{config.LAST_FY}; nothing to do")
        return 1
    if config.stage0_zip(fy).is_file():
        log(f"FY{fy} is already in Stage 0; continuing with the later steps")
    else:
        stage0.organize([source], {fy}, log=log)
    return refresh(log)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="mode", required=True)
    a = sub.add_parser("add-year")
    a.add_argument("--fy", type=int, required=True)
    a.add_argument("--source", type=Path, required=True, help="folder holding FY####_All_Contracts_Full_20260906.zip")
    sub.add_parser("refresh")
    args = p.parse_args(argv)
    log = lambda s: print(s, flush=True)  # noqa: E731
    if args.mode == "add-year":
        return add_year(args.fy, args.source.expanduser(), log)
    return refresh(log)


if __name__ == "__main__":
    sys.exit(main())
