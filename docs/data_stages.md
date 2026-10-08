# Data stages: what we keep, where it lives, and how it was proven

**Location.** The repo and a folder named `DATA` sit side by side. The raw zips are in `../DATA/`, relative to the repo, and everything the pipeline builds is in the repo's own `data/` folder, which git ignores. Our copy was moved out of iCloud Drive on 2026-10-05. The section "Where the project lives, and why" explains the move.

**The rule above all others: nothing is ever thrown away.** Every piece of data is kept, in stages. Each stage has a defined job, a defined place, and a record of how it was built or proven. Later, when anything is excluded, changed or cleaned, the record will say why and who decided.

| Stage | What it is | Folder | Changes allowed | Status (release 2026-09-06) |
|---|---|---|---|---|
| **0. Raw** | The zips exactly as USAspending published them | `../DATA/raw/award_data_archive/release_2026-09-06/` | None, ever. Files and folder are read-only. | 18 of 18 fiscal years |
| **1. Mirror** | A lossless text Parquet copy of every row and all 297 columns ("Layer A") | `data/parquet/layer_a/fy{YYYY}/20260906/` | None. Proven identical to Stage 0, row by row. | 18 of 18 years PASS (`reports/integrity/stage1_mirror_proof.md`) |
| **2. Flags** | Facts about the data: one row per (transaction key, flag), plus profiles and summaries | `data/integrity/` | Rebuildable from Stage 1 at any time | 18 years profiled, 61 flags run (`reports/integrity/`) |
| **3. Working set** *(later)* | Typed and cleaned for analysis | (later) | Only through documented rules in `config/decisions.csv` | not built |

---

## Stage 0: raw

**In plain language.** These are the files we downloaded from USAspending's Award Data Archive, unchanged. Everything else is built from them. They are locked, so neither a person nor a script can change them by accident.

- **Folder:** `../DATA/raw/award_data_archive/release_2026-09-06/`, next to the repo. Never in git.
  - **In scope:** 18 zips, `FY2008_…` through `FY2025_All_Contracts_Full_20260906.zip`.
  - **`_out_of_scope/`:** `FY2026_All_Contracts_Full_20260906.zip`. It is recorded in `data/manifest.csv` as "out of scope - not a pipeline input" and is never processed. FY2026 stays incomplete until about January because of DoD's 90-day reporting lag.
- **Release:** every in-scope zip is from the 2026-09-06 release, the date in its name.
  - Their CSV members carry 20260906 or 20260907. The FY2025 zip, checked in the pilot, does the same.
  - One release for all years matters. Every file is a snapshot, and mixing monthly releases would leave small differences nobody could trace.
- **How each zip got here** (`python -m src.stage0 organize`):
  1. **Checked before anything moved.** For each zip:
     - SHA-256 of the zip
     - every member read in full, which makes Python check its CRC-32, with the byte count compared to the zip's directory
     - strict UTF-8 decoding of every byte
     - BOM check
     - CSV header compared with FY2025's 297 columns (`reports/columns_fy2025.txt`)
     - header-only members
     - dates in the member names.
  2. **Moved by renaming** within the same disk, which never copies or deletes. Then re-hashed: the SHA-256 must be unchanged. The zips must therefore start on the same disk as `../DATA`.
  3. **Registered** in `data/manifest.csv` through `src/download.py register` (with its source URL), and made read-only (`chmod a-w`).
  4. **Result:** all 18 passed every check. All headers are identical to FY2025's, with no BOM and no header-only members. Every SHA-256 was unchanged by the move. Details: `reports/integrity/stage0_inventory.md`.
- **FY2015 came last.**
  - **History:** its first download (2026-10-05) failed with a 0-byte file, so the other 17 years were built first, with FY2015 shown as *pending*.
  - **Adding it:** with the download in hand, `python -m src.stages add-year --fy 2015 --source ~/Downloads` ran the same steps: verify, move, Stage 1, Stage 2, then every cross-year check again.
  - **Result:** it passed everything, and its manifest row replaced the placeholder.
- **Kept out of iCloud Drive.** The section "Where the project lives, and why" explains this.
- **Undoing the read-only setting** (it is reversible), from the repo folder:

  ```bash
  cd ../DATA/raw/award_data_archive
  chmod u+w release_2026-09-06 release_2026-09-06/_out_of_scope      # folders writable again (to add a file)
  chmod u+w release_2026-09-06/FY2008_All_Contracts_Full_20260906.zip # one zip writable again (rarely needed)
  chmod a-w release_2026-09-06 release_2026-09-06/_out_of_scope release_2026-09-06/*.zip  # lock again
  ```

  `src.stage0 organize` unlocks the folders itself while it moves a file in, then locks them again and checks they are locked.

## Stage 1: the mirror (Layer A)

**In plain language.** A copy of every row and every column in a format that is fast to read: Parquet, with every value kept as text exactly as in the CSV. Two independent readers compare it with the zip, row by row, and only then do we trust it.

- **Files:**
  - one Parquet file per CSV member, in `data/parquet/layer_a/fy{YYYY}/20260906/` (one folder per year and release, review fix S5)
  - `_files.json` in each folder, listing the members that make up the year's mirror. Read the files from that list, never with a glob.
  - Each row also carries `_source_file`, `_source_member_idx` and `_source_row`, its exact position in the zip.
- **How it is proven** (`python -m src.stage1 build`, with results in `reports/integrity/stage1_mirror_proof.md` and `.csv`). For every member:
  1. **Raw side:** Python's `csv` module reads the member straight from the zip.
  2. **Parquet side:** DuckDB reads the Parquet file. The two share no code.
  3. **Both compute:**
     - the number of records
     - the exact Decimal sum of `federal_action_obligation`
     - a full-row fingerprint: the sum over all records of the first 16 hex digits of the MD5 of the record's 297 fields joined by U+001F (review fix S1).
  4. **PASS** only if all three are identical, with no malformed records, no rejected rows, and `_source_row` running 1..n.
  5. **Blank lines** are not records. They are counted, and never become fake rows (S3).
  6. **Header-only members** pass with 0 = 0 (N9).
  7. **Any mismatch** stops the run with a non-zero exit (S4). `_files.json` is written only for a year whose members all pass.
- **FY2025's pilot files** sat in the old flat folder `layer_a/fy2025/`. Each one's fingerprint was checked against the zip before it was moved into `fy2025/20260906/`. All passed, so none was rebuilt.
- **Not built in this stage:** Layer B (the typed table) and the pilot's reconciliation checks. They come with the working set.

## Stage 2: flags and profiles

**In plain language.** Facts about the data, kept beside it rather than inside it. For example: "this row's PSC code has 3 characters", or "this agency has no rows in FY2012". Nothing in Stage 0 or Stage 1 is changed.

- **Rules:** `config/flag_catalog.csv`.
  - 61 flags, each with an exact rule, a threshold and a severity (serious, review or info).
  - The catalog was committed **before** it was run on the data (commit `3fd729a`), and its thresholds were not tuned afterwards.
- **Files:**
  - `data/integrity/row_flags/fy{YYYY}.parquet`: one row per (`contract_transaction_unique_key`, `fiscal_year`, `flag_id`).
  - `data/integrity/fy{YYYY}/`: the year's profiles. These cover every column's blanks, zeros, placeholders, whitespace, case variants and top values, plus months, agencies, sub-agencies, money, reporting lag, last-modified dates and code/label pairs. They also hold the cubes the dashboard filters on.
  - `data/integrity/cross/`: cross-year results. These cover keys across years, awards spanning years, agency and sub-agency matrices, label changes, thin months and the parent test.
  - `data/integrity/summary/`: the flag cube for the dashboard, and `outliers_all.parquet`, the full J01-J04 lists (2.6 million rows, too many to commit). `reports/integrity/outliers.csv` keeps the J01 and J02 rows with context.
  - `reports/integrity/`: committed summaries, with no row-level data.
  - `config/benchmarks.csv`: published totals for the completeness check, each quote re-checked against a saved copy in `data/external/benchmarks/`.
- **Fast versus exact rules:** the dashboard cube uses fast versions of the blank, zero and placeholder rules. Each year's build checks that they give exactly the same totals as the exact rules, and stops if not.
- **Rebuild:** `python -m src.stage2 all`. It skips years already built for the same zip. `python -m src.stage2 year --fy 2024 --force` rebuilds one year.

## Stage 3: the working set (later), and the ledger rule

**The ledger rule.**
- Every row in Stage 1 must end up either in the working set or in an **exclusions ledger** that records its reason code.
- Rows and dollars must add back exactly: working set + ledger = Stage 1, for every fiscal year.
- A row can be changed or excluded only by a rule recorded in `config/decisions.csv`, which states the status, the rationale, who decided and when.
- The dashboard's Decision log page writes that file and nothing else.

## Where the project lives, and why

This section is background from our Mac. It matters only on a Mac that syncs `~/Documents` with iCloud Drive.

**In plain language.** The project used to sit inside `~/Documents`, which iCloud Drive syncs. iCloud kept undoing the read-only lock on the raw zips' folders, and it can quietly swap a local file for an online-only placeholder. A raw stage that must stay exactly as published cannot live there, so on 2026-10-05 the whole project moved to a folder that iCloud does not sync.

- **What iCloud was doing.**
  - `~/Documents` is synced by iCloud Drive (Desktop & Documents), with Optimize Mac Storage on.
  - Its file provider made the two Stage 0 folders writable again (`drwx------`) shortly after each lock. This was seen three times on 2026-10-05.
  - It was uploading all of the data (about 50 GB) to iCloud.
  - With Optimize Mac Storage, macOS may replace local files with download-on-demand placeholders, which would make Stage 0 and Stage 1 depend on the network.
- **How the move was done and checked.**
  1. **First:** no file in the project folder was an online-only placeholder (`find . -flags +dataless`: 0). Every file's path and size was listed: 943 files and 51.674 GB, leaving out `.venv`.
  2. **The move:** one rename of the whole folder on the same disk (`os.rename`). Nothing was copied or deleted. The list afterwards was identical: same files, same sizes.
  3. **`.venv`:** rebuilt from `requirements.txt` with the same Python 3.13.1, giving the same 7 packages and versions. The old one is in `data/scratch/venv_before_move/`.
  4. **`data/manifest.csv`:** `local_path` was updated on all 22 rows, and no other field changed. Every path exists with its recorded size. A copy from before is in `data/scratch/pre_move/`. The finished comparison's load record (`data/comparison/custom_q1fy2025_load.json`) got the same path change.
  5. **Checks:**
     - all 19 zips match their manifest SHA-256
     - `python -m src.stage1 recheck`: 18 of 18 years PASS (97 members, rows, exact dollars and full-row fingerprints against the recorded raw side)
     - Stage 0 is read-only again
     - `tests.test_stages`: 10 of 10
     - `viewer.test_viewer`: 24 of 24 checks and 6 screenshots.
- **What was left as it was.** Files that record history keep the old path, because they describe what happened at the time: the pilot's run log, the Stage 0 verification and Stage 1 proof records, and the run logs in `data/integrity/`. No code reads a path back from them.
- **The old location.** iCloud later recreated three empty folders at the old location, rebuilt from its cloud copy. They hold no data.
- **Keep it this way.**
  - On a Mac with iCloud Drive, keep the repo and `DATA` out of `~/Documents` and `~/Desktop`.
  - Two checks should both print nothing ahead of any data work. Run them from the repo folder. The second works only with the macOS version of `find`.

    ```bash
    find ../DATA/raw/award_data_archive/release_2026-09-06 -perm -u+w   # anything writable in Stage 0
    find .. -flags +dataless                                             # any online-only placeholder (macOS)
    ```
  - Run `python -m src.stage1 recheck` after any move or restore.

## Commands

```bash
# Stage 0: verify and organize zips found in a folder on the same disk as ../DATA (read-only checks first; stops on any problem)
.venv/bin/python -m src.stage0 organize --source ~/Downloads --only-fy 2015
# Stage 1: build and prove every year in Stage 0 (restartable; proven years are skipped)
caffeinate -i .venv/bin/python -m src.stage1 build
# Stage 2: flags, profiles, cross-year results, reports
caffeinate -i .venv/bin/python -m src.stage2 all
# Everything missing, in order (restartable), then refresh the proposed decisions
caffeinate -i .venv/bin/python -m src.stages refresh
# After moving or restoring the project: re-prove every year from its recorded raw side (about 3 minutes)
caffeinate -i .venv/bin/python -m src.stage1 recheck

# Add a year that was pending (done for FY2015 on 2026-10-05): verify/move, Stage 1, Stage 2, cross-year refresh and reports:
caffeinate -i .venv/bin/python -m src.stages add-year --fy 2015 --source ~/Downloads
# then restart the dashboard to see it:
.venv/bin/python -m viewer.server     # http://127.0.0.1:8765/
```

`caffeinate -i` keeps a Mac awake during long runs. Leave it out on other systems.

## Disk

Measured 2026-10-05 after all 18 years were built (sizes in GB = 10^9 bytes).

| What | Folder | Size |
|---|---|---|
| Stage 0, 18 in-scope zips | `../DATA/raw/award_data_archive/release_2026-09-06/` | 27.11 GB |
| Stage 0, FY2026 (out of scope and never processed) | `release_2026-09-06/_out_of_scope/` | 1.38 GB |
| Stage 1, Layer A (97 Parquet files, 18 years) | `data/parquet/layer_a/` | 19.84 GB |
| Stage 2, flags, profiles, cubes, cross-year results | `data/integrity/` | 2.05 GB |
| Saved benchmark sources | `data/external/benchmarks/` | 0.001 GB |
| Pilot's FY2025 Layer B (not rebuilt in this work) | `data/parquet/layer_b/` | 0.32 GB |
| **Total** | | **50.7 GB** |

The disk had 472 GiB free afterwards.
