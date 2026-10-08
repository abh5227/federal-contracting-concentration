# Stage 1 proof: the Layer A mirror equals the raw zips, row by row

Generated 2026-10-05T23:39:13+00:00 by `python -m src.stage1 report`. One row per member is in `stage1_mirror_proof.csv`.

**How it is proven.** For every CSV member, two independent readers compute the same three numbers:
- **raw side:** Python's `csv` module, streamed straight from the zip;
- **Parquet side:** DuckDB over the member's Parquet file.

The three numbers:
1. the number of records;
2. the exact Decimal sum of `federal_action_obligation`;
3. a fingerprint of every row: the sum, over all records, of the first 16 hex digits of the MD5 of the record's 297 fields joined by U+001F.

A member passes only if all three are identical, with no malformed records and no rejects, and with `_source_row` running 1..n. Blank lines are not records: they are counted here and never become rows.

- Years proven: 18 PASS, 0 not PASS, pending: none.
- Layer A on disk: 19.84 GB (19,842,415,854 bytes).

| FY | Status | Members | Raw records | Parquet rows | Raw dollars | Parquet dollars | Fingerprints equal | Blank lines | Rejects | Pilot files adopted | Layer A GB |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2008 | **PASS** | 5 | 4,505,730 | 4,505,730 | $541,901,088,924.47 | $541,901,088,924.47 | yes | 0 | 0 | 0 | 0.91 |
| 2009 | **PASS** | 4 | 3,497,692 | 3,497,692 | $540,837,049,440.12 | $540,837,049,440.12 | yes | 0 | 0 | 0 | 0.78 |
| 2010 | **PASS** | 4 | 3,543,905 | 3,543,905 | $561,215,227,985.37 | $561,215,227,985.37 | yes | 0 | 0 | 0 | 0.86 |
| 2011 | **PASS** | 4 | 3,408,506 | 3,408,506 | $539,905,845,139.79 | $539,905,845,139.79 | yes | 0 | 0 | 0 | 0.84 |
| 2012 | **PASS** | 4 | 3,129,630 | 3,129,630 | $520,841,173,582.02 | $520,841,173,582.02 | yes | 0 | 0 | 0 | 0.78 |
| 2013 | **PASS** | 3 | 2,515,087 | 2,515,087 | $463,606,712,799.66 | $463,606,712,799.66 | yes | 0 | 0 | 0 | 0.63 |
| 2014 | **PASS** | 3 | 2,528,542 | 2,528,542 | $446,304,627,405.15 | $446,304,627,405.15 | yes | 0 | 0 | 0 | 0.63 |
| 2015 | **PASS** | 5 | 4,375,319 | 4,375,319 | $439,983,581,411.26 | $439,983,581,411.26 | yes | 0 | 0 | 0 | 0.96 |
| 2016 | **PASS** | 5 | 4,821,964 | 4,821,964 | $475,372,633,098.04 | $475,372,633,098.04 | yes | 0 | 0 | 0 | 1.05 |
| 2017 | **PASS** | 5 | 4,913,345 | 4,913,345 | $510,434,208,570.80 | $510,434,208,570.80 | yes | 0 | 0 | 0 | 1.09 |
| 2018 | **PASS** | 6 | 5,619,630 | 5,619,630 | $556,022,709,344.49 | $556,022,709,344.49 | yes | 0 | 0 | 0 | 1.24 |
| 2019 | **PASS** | 7 | 6,488,828 | 6,488,828 | $589,730,494,134.75 | $589,730,494,134.75 | yes | 0 | 0 | 0 | 1.41 |
| 2020 | **PASS** | 7 | 6,306,607 | 6,306,607 | $671,424,501,194.64 | $671,424,501,194.64 | yes | 0 | 0 | 0 | 1.42 |
| 2021 | **PASS** | 7 | 6,405,488 | 6,405,488 | $645,398,980,544.39 | $645,398,980,544.39 | yes | 0 | 0 | 0 | 1.42 |
| 2022 | **PASS** | 7 | 6,668,009 | 6,668,009 | $694,685,943,373.84 | $694,685,943,373.84 | yes | 0 | 0 | 0 | 1.48 |
| 2023 | **PASS** | 7 | 6,693,769 | 6,693,769 | $760,429,406,567.32 | $760,429,406,567.32 | yes | 0 | 0 | 0 | 1.47 |
| 2024 | **PASS** | 7 | 6,692,741 | 6,692,741 | $756,390,254,511.19 | $756,390,254,511.19 | yes | 0 | 0 | 0 | 1.46 |
| 2025 | **PASS** | 7 | 6,639,176 | 6,639,176 | $793,189,920,124.27 | $793,189,920,124.27 | yes | 0 | 0 | 7 | 1.43 |
