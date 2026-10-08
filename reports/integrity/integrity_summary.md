# Integrity and completeness: summary

Generated 2026-10-05T23:40:55+00:00 by `python -m src.integrity_report`, from Stage 1 (the proven mirror) and Stage 2 (flags and profiles). No row was changed, dropped or fixed. Every finding below is a fact about the data, waiting for a team decision (`config/decisions.csv`).

## Verdict

We hold 18 of 18 fiscal years (none pending): 88,753,968 transaction rows and $10,507,674,358,151.57 in net obligations, all from the 2026-09-06 release. Every year's Parquet mirror is verified against its zip: row counts, exact dollars and a full-row checksum match (Stage 1 PASS). Against published totals from GAO and GSA (both drawn from FPDS, so they check our extraction, not FPDS), 8 of 8 benchmarked years are within 2% with GAO as the primary benchmark (6 of 8 under the version 1 rule, the worse of GAO and GSA; see `completeness_check.md`). No serious flag fired. The review flags below need a person's judgment; they are ordered by dollars within each severity. After them come the largest single transactions and what their awards net to.

## Biggest findings first

Ordered by severity, then by gross dollars affected (|amount| summed over flagged rows), then by count.

| Flag | Severity | What | Count | Gross $ affected | Share of gross $ | Years affected |
|---|---|---|---|---|---|---|
| J04 | review | Amount far from its peers | 309,520 rows | $3,159,536,803,809.64 | 24.64% | 18 (2008-2025) |
| C08 | review | Reported before the action date | 5,265,535 rows | $3,014,313,732,001.61 | 23.51% | 18 (2008-2025) |
| J02 | review | Transaction of $1 billion or more | 403 rows | $1,958,203,342,697.07 | 15.27% | 18 (2008-2025) |
| E01 | review | Placeholder vendor | 974,834 rows | $742,591,701,534.23 | 5.79% | 18 (2008-2025) |
| G03 | review | Code and label disagree on presence | 3,904,790 rows | $341,888,568,909.92 | 2.67% | 17 (2008-2025) |
| J03 | review | Deobligation larger than the award's obligations that year | 2,407,492 rows | $270,649,387,811.91 | 2.11% | 18 (2008-2025) |
| C06 | review | Performance period starts after it ends | 2,229,493 rows | $166,424,295,907.64 | 1.30% | 18 (2008-2025) |
| X02 | review | Zero offers on a competed action | 930,254 rows | $48,328,399,140.15 | 0.38% | 18 (2008-2025) |
| C10 | review | Last modified before the action date | 48,481 rows | $7,056,377,526.42 | 0.06% | 18 (2008-2025) |
| C05 | review | Implausible date | 2,745 rows | $618,588,061.08 | 0.00% | 18 (2008-2025) |
| F04 | review | DUNS not 9 digits | 1,501 rows | $41,958,536.74 | 0.00% | 11 (2008-2021) |
| F02 | review | NAICS not 6 digits | 43 rows | $19,543,517.47 | 0.00% | 8 (2008-2018) |
| G01 | review | Order without a parent award | 3 rows | $89,463.97 | 0.00% | 2 (2008-2010) |
| F01 | review | PSC not 4 characters | 5 rows | $13,356.07 | 0.00% | 2 (2008-2012) |
| G02 | review | Definitive contract or purchase order with a parent award | 3 rows | $1,112.74 | 0.00% | 1 (2010-2010) |
| F07 | review | Code with more than one label in a year | 5,069 codes |  |  | 18 (2008-2025) |
| H06 | review | Sub-agency missing in a middle year | 32 sub-agency-years |  |  | 12 (2010-2024) |
| H03 | review | Agency missing in a middle year | 16 agency-years |  |  | 10 (2010-2021) |
| H07 | review | Sub-agency drop that recovers (dollars) | 2 sub-agency-years |  |  | 2 (2012-2024) |
| E02 | review | Placeholder ID | 1 rows |  |  | 1 (2017-2017) |
| H02 | review | Thin month (dollars) | 1 months |  |  | 1 (2009-2009) |
| H04 | review | Agency drop that recovers (dollars) | 1 agency-years |  |  | 1 (2012-2012) |
| J01 | info | Top 100 by absolute amount | 1,800 rows | $2,756,633,146,619.32 | 21.50% | 18 (2008-2025) |
| C07 | info | Reported more than 90 days after the action | 4,004,540 rows | $297,072,425,528.70 | 2.32% | 18 (2008-2025) |
| D04 | info | IDV row carries dollars | 183,497 rows | $216,208,604,122.51 | 1.69% | 18 (2008-2025) |
| F05 | info | Agency code not 3 characters | 286,312 rows | $62,461,228,892.69 | 0.49% | 18 (2008-2025) |
| B05 | info | Award spans several fiscal years | 4,314,940 distinct awards |  |  | 18 (2008-2025) |
| F08 | info | Code whose label changes across years | 2,530 codes (all years) |  |  | all present years (cross-year) |

Flags with no hits in any present year: A01, A02, A03, A04, A05, B01, B02, B03, B04, B06, C01, C02, C03, C04, C09, D01, D02, D03, F03, F06, F09, F10, G04, G05, H01, H05, H08, X01.

## Largest single transactions, and what their awards net to

The 10 largest rows by |amount| across all present years. "Award net" sums every row of the same `contract_award_unique_key` in every present year. When it is far smaller than the row, another row offsets it. Nothing here is changed or excluded; the full list is `outliers.csv`.

| FY | Amount | Action date | Agency / sub-agency | Recipient | PSC | Award (mod) | Award rows | Award net | Award years |
|---|---|---|---|---|---|---|---|---|---|
| 2013 | $344,733,911,303.88 | 2013-09-26 | Department of Defense / Department of the Army | MISCELLANEOUS FOREIGN AWARDEES | Y112 | `CONT_AWD_W912GB09C0090_9700_-NONE-_-NONE-` (P00006) | 15 | $3,077,395.65 | 2009, 2010, 2012, 2013, 2014, 2015 |
| 2013 | -$344,733,702,433.01 | 2013-09-27 | Department of Defense / Department of the Army | MISCELLANEOUS FOREIGN AWARDEES | Y112 | `CONT_AWD_W912GB09C0090_9700_-NONE-_-NONE-` (P00007) | 15 | $3,077,395.65 | 2009, 2010, 2012, 2013, 2014, 2015 |
| 2009 | -$116,092,075,155.00 | 2009-08-27 | Department of Defense / Department of the Army | FLUOR INTERCONTINENTAL, INC. | AD25 | `CONT_AWD_0021_9700_W912ER04D0004_9700` (14) | 22 | $6,651,609.60 | 2008, 2009, 2010, 2012, 2015, 2017 |
| 2009 | $116,091,716,928.00 | 2009-08-24 | Department of Defense / Department of the Army | FLUOR INTERCONTINENTAL, INC. | AD25 | `CONT_AWD_0021_9700_W912ER04D0004_9700` (13) | 22 | $6,651,609.60 | 2008, 2009, 2010, 2012, 2015, 2017 |
| 2015 | $92,490,715,466.13 | 2015-05-12 | Department of Defense / Department of the Army | HENSEL PHELPS CONSTRUCTION CO | Y1AZ | `CONT_AWD_W912DR12C0019_9700_-NONE-_-NONE-` (P00008) | 139 | $132,762,030.00 | 2012, 2013, 2014, 2015, 2016, 2017, 2019 |
| 2015 | -$92,490,158,844.13 | 2015-05-13 | Department of Defense / Department of the Army | HENSEL PHELPS CONSTRUCTION CO | Y1AZ | `CONT_AWD_W912DR12C0019_9700_-NONE-_-NONE-` (P00009) | 139 | $132,762,030.00 | 2012, 2013, 2014, 2015, 2016, 2017, 2019 |
| 2020 | $16,597,954,142.00 | 2019-11-26 | Department of Defense / Department of the Navy | LOCKHEED MARTIN CORPORATION | 1510 | `CONT_AWD_N0001917C0001_9700_-NONE-_-NONE-` (P00024) | 211 | $35,135,514,910.20 | 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025 |
| 2025 | $14,145,203,547.00 | 2025-09-29 | Department of Defense / Department of the Navy | LOCKHEED MARTIN CORPORATION | 1510 | `CONT_AWD_N0001923C0003_9700_-NONE-_-NONE-` (P00015) | 16 | $24,499,534,829.00 | 2023, 2024, 2025 |
| 2008 | $13,917,176,427.00 | 2008-09-29 | Department of Defense / Department of the Army | EMERSON CONSTRUCTION COMPANY, INC. | Y199 | `CONT_AWD_W912QR08C0053_9700_-NONE-_-NONE-` (0) | 27 | $16,293,527.48 | 2008, 2009, 2010, 2011, 2012 |
| 2009 | -$13,901,924,427.00 | 2009-01-07 | Department of Defense / Department of the Army | EMERSON CONSTRUCTION COMPANY, INC. | Y199 | `CONT_AWD_W912QR08C0053_9700_-NONE-_-NONE-` (P00001) | 27 | $16,293,527.48 | 2008, 2009, 2010, 2011, 2012 |

## By year

| FY | Status | Rows | Net obligations | Stage 1 proof | IDV rows | IDV net | Agencies | Sub-agencies |
|---|---|---|---|---|---|---|---|---|
| 2008 | present | 4,505,730 | $541,901,088,924.47 | PASS | 117,978 | $5,017,787,105.20 | 64 | 166 |
| 2009 | present | 3,497,692 | $540,837,049,440.12 | PASS | 155,253 | $5,634,276,266.92 | 65 | 173 |
| 2010 | present | 3,543,905 | $561,215,227,985.37 | PASS | 177,342 | $26,608,953,093.85 | 67 | 179 |
| 2011 | present | 3,408,506 | $539,905,845,139.79 | PASS | 186,592 | $6,655,022,335.51 | 66 | 171 |
| 2012 | present | 3,129,630 | $520,841,173,582.02 | PASS | 186,580 | $6,274,503,003.85 | 66 | 170 |
| 2013 | present | 2,515,087 | $463,606,712,799.66 | PASS | 204,967 | $5,492,973,577.28 | 66 | 168 |
| 2014 | present | 2,528,542 | $446,304,627,405.15 | PASS | 204,159 | $6,209,758,460.98 | 64 | 168 |
| 2015 | present | 4,375,319 | $439,983,581,411.26 | PASS | 204,704 | $9,185,334,914.33 | 65 | 166 |
| 2016 | present | 4,821,964 | $475,372,633,098.04 | PASS | 207,319 | $11,848,571,382.62 | 68 | 169 |
| 2017 | present | 4,913,345 | $510,434,208,570.80 | PASS | 207,107 | $9,327,998,483.57 | 69 | 170 |
| 2018 | present | 5,619,630 | $556,022,709,344.49 | PASS | 222,099 | $10,273,895,515.98 | 70 | 171 |
| 2019 | present | 6,488,828 | $589,730,494,134.75 | PASS | 201,776 | $11,069,339,909.19 | 70 | 172 |
| 2020 | present | 6,306,607 | $671,424,501,194.64 | PASS | 266,972 | $13,745,772,674.92 | 70 | 174 |
| 2021 | present | 6,405,488 | $645,398,980,544.39 | PASS | 228,754 | $12,206,399,539.98 | 70 | 169 |
| 2022 | present | 6,668,009 | $694,685,943,373.84 | PASS | 252,731 | $14,115,417,661.30 | 70 | 170 |
| 2023 | present | 6,693,769 | $760,429,406,567.32 | PASS | 244,607 | $13,934,108,709.01 | 70 | 167 |
| 2024 | present | 6,692,741 | $756,390,254,511.19 | PASS | 260,982 | $15,438,176,331.59 | 70 | 168 |
| 2025 | present | 6,639,176 | $793,189,920,124.27 | PASS | 311,910 | $14,700,644,438.93 | 70 | 168 |

**The FY2015 row-count jump.** FY2014 to FY2015: +1,846,777 rows (+73.0%), net obligations -1.4%. FY2015 to FY2016: +446,645 rows (+10.2%), net obligations +8.0%. See `docs/integrity_findings.md` for what the new rows are.

## Where to look next

- `completeness_check.md`: our totals against published figures, with citations.
- `flag_counts.csv`: every flag by year (rows or items, and dollars).
- `column_quality.csv`: blank, zero and placeholder shares for all 297 columns by year.
- `outliers.csv`: every J01 (top 100 per year) and J02 ($1 billion or more) row, with what its award nets to. The full J01-J04 lists (millions of rows) are in `data/integrity/summary/outliers_all.parquet` and on the dashboard. Every outlier stays in the data.
- `stage1_mirror_proof.md`: the row-by-row proof.
