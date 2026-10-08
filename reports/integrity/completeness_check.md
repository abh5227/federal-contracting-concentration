GAO and GSA both start from FPDS, the system USAspending draws from, so a match checks our extraction and sums, not FPDS itself. 4 of 18 years have a well-defined benchmark (a GAO figure: FY2022-FY2025), 4 have a loosely defined one (FY2018-FY2021: GSA figures, and GAO statements that are lower bounds or approximate), and 10 have none (FY2008-FY2017). Status with GAO primary and GSA as context: 8 PASS, 0 WARN, 0 FAIL. GAO lower bounds met: 3 of 3. Version 1 rule (the worse of GAO and GSA): 6 PASS, 2 WARN, 0 FAIL.

| FY | Class | Status (version 2: GAO primary) | Status (version 1: worst of GAO and GSA) | GAO | GSA | GAO lower bound |
|---|---|---|---|---|---|---|
| 2018 | loosely defined | **PASS** | PASS |  | PASS | MEETS BOUND |
| 2019 | loosely defined | **PASS** | PASS |  | PASS | MEETS BOUND |
| 2020 | loosely defined | **PASS** | PASS |  | PASS | MEETS BOUND |
| 2021 | loosely defined | **PASS** | PASS | PASS | PASS |  |
| 2022 | well-defined | **PASS** | PASS | PASS | PASS |  |
| 2023 | well-defined | **PASS** | PASS | PASS | PASS |  |
| 2024 | well-defined | **PASS** | WARN | PASS | WARN |  |
| 2025 | well-defined | **PASS** | WARN | PASS | WARN |  |

# Completeness check against published totals

Generated 2026-10-05T23:40:55+00:00 by `python -m src.integrity_report`. Thresholds are fixed in `config/flag_catalog.csv` (I01, I02) and were written down before any comparison: PASS within 2%, WARN within 10%, FAIL beyond 10%. They apply to figures stated in nominal dollars. GAO lower bounds ("more than $X") are checked one-sided. Constant-dollar figures are recorded, not compared.

**Expected differences.** Each published figure reflects its source's data as of its own date. Ours reflect USAspending's release of 2026-09-06. Data keeps changing after publication, so small gaps are expected, especially for recent years. The gaps are reported as they are, with no adjustment.

| FY | Benchmark | Agency | Status | Our net total | Published figure | Gap | Gap % | Data as of (source) |
|---|---|---|---|---|---|---|---|---|
| 2018 | [GAO-FY2018-bound](https://www.gao.gov/blog/2019/05/28/federal-government-contracting-for-fiscal-year-2018-infographic) | government-wide | **MEETS BOUND** | $556,022,709,344.49 | $550,000,000,000.00 | $6,022,709,344.49 | 1.10% | not stated ("Analysis of FY2018 FPDS-NG data") |
| 2018 | [GSA-15H-FY2018](https://www.gsa.gov/system/files/FY18%20Sm%20Bus%20Act%20Section%2015%28h%29%283%29%28A%29%28ii%29%20FPDS%20GSA%20Report%20%20-%20Executive%20Summary.pdf) | government-wide | **PASS** | $556,022,709,344.49 | $555,000,000,000.00 | $1,022,709,344.49 | 0.18% |  |
| 2019 | [GAO-FY2019-bound](https://www.gao.gov/blog/snapshot-government-wide-contracting-fy-2019-infographic) | government-wide | **MEETS BOUND** | $589,730,494,134.75 | $586,000,000,000.00 | $3,730,494,134.75 | 0.64% | not stated ("Analysis of FY2019 FPDS-NG data") |
| 2019 | [GSA-15H-FY2019](https://www.gsa.gov/system/files/Executive%20Summary_FY19%20GSA%20Report%20documents_0.pdf) | government-wide | **PASS** | $589,730,494,134.75 | $587,000,000,000.00 | $2,730,494,134.75 | 0.47% | FPDS data derived February 24, 2020 |
| 2020 | [GAO-FY2020-bound](https://www.gao.gov/blog/snapshot-government-wide-contracting-fy-2020-infographic) | government-wide | **MEETS BOUND** | $671,424,501,194.64 | $665,000,000,000.00 | $6,424,501,194.64 | 0.97% | not stated ("Analysis of FY2020 FPDS-NG data") |
| 2020 | [GSA-15H-FY2020](https://www.gsa.gov/system/files/Executive%20Summary_FY20%20GSA%20Report%20documents_0.pdf) | government-wide | **PASS** | $671,424,501,194.64 | $665,000,000,000.00 | $6,424,501,194.64 | 0.97% | FPDS data derived February 24, 2021 |
| 2021 | [GAO-FY2021](https://www.gao.gov/blog/snapshot-government-wide-contracting-fy-2021-interactive-dashboard) | government-wide | **PASS** | $645,398,980,544.39 | $637,000,000,000.00 | $8,398,980,544.39 | 1.32% | not stated ("Analysis of FY2021 FPDS-NG data") |
| 2021 | [GSA-15H-FY2021](https://www.gsa.gov/system/files/ExecutiveSummaryFY21GSAReportDocuments_0.pdf) | government-wide | **PASS** | $645,398,980,544.39 | $648,000,000,000.00 | -$2,601,019,455.61 | -0.40% | FPDS data derived February 22, 2022 |
| 2022 | [GAO-FY2022](https://files.gao.gov/multimedia/Federal_Government_Contracting-FY2022/static/data/data.json) | government-wide | **PASS** | $694,685,943,373.84 | $694,000,000,000.00 | $685,943,373.84 | 0.10% | FPDS data as of May 2023 |
| 2022 | [GSA-15H-FY2022](https://www.gsa.gov/system/files/ExecutiveSummaryFY%2722GSAReportDocuments%20%282%29%20%281%29.pdf) | government-wide | **PASS** | $694,685,943,373.84 | $705,000,000,000.00 | -$10,314,056,626.16 | -1.46% | FPDS data derived February 22, 2023 |
| 2023 | [GAO-FY2023](https://files.gao.gov/multimedia/Federal_Government_Contracting/static/data/data.json) | government-wide | **PASS** | $760,429,406,567.32 | $759,000,000,000.00 | $1,429,406,567.32 | 0.19% | FPDS data as of May 2024 |
| 2023 | [GSA-15H-FY2023](https://www.gsa.gov/system/files/ExecutiveSummaryFY%2723GSAReportDocuments_508.docx) | government-wide | **PASS** | $760,429,406,567.32 | $775,000,000,000.00 | -$14,570,593,432.68 | -1.88% | FPDS data derived February 22, 2024 |
| 2024 | [GAO-FY2024](https://files.gao.gov/multimedia/Federal_Government_Contracting-FY2024/static/data/data.json) | government-wide | **PASS** | $756,390,254,511.19 | $755,000,000,000.00 | $1,390,254,511.19 | 0.18% | FPDS data as of June 2025 |
| 2024 | [GSA-15H-FY2024](https://www.gsa.gov/system/files/Executive%20Summary_%20FY%202024%20FPDS%20GSA%20Report.pdf) | government-wide | **WARN** | $756,390,254,511.19 | $774,000,000,000.00 | -$17,609,745,488.81 | -2.28% | FPDS data derived February 20, 2025 |
| 2025 | [GAO-FY2025](https://files.gao.gov/multimedia/Federal_Government_Contracting-FY2025/static/data/data.json) | government-wide | **PASS** | $793,189,920,124.27 | $793,000,000,000.00 | $189,920,124.27 | 0.02% | FPDS data as of April 2026 |
| 2025 | [GSA-15H-FY2025](https://www.gsa.gov/system/files/Executive%20Summary.pdf) | government-wide | **WARN** | $793,189,920,124.27 | $812,000,000,000.00 | -$18,810,079,875.73 | -2.32% | FPDS data derived February 20, 2026 |

## Every WARN or FAIL: likely reasons and the ones our data can test

**GSA-15H-FY2024 (FY2024, government-wide): WARN, gap -2.28%.**

- **Possible reasons:**
  - definitions: IDV rows, other transaction agreements, classified actions;
  - whether deobligations are netted;
  - the source's data date versus ours (2026-09-06);
  - constant versus nominal dollars.
- **What the source says it includes and excludes:** Includes (stated): "all prime contract procurements made during each fiscal year (FY), not excluding any contract awarded"; "includes procurements made for the Federal Government, including each of the 24 Chief Financial Officers (CFO) Act agencies"; the figure is followed by other-than-small-business and small-business expenditure totals; the Final Data Report's other-than-small line reads "In the aggregate, without exclusions". Uses the word "expenditures" but the source is FPDS dollar amounts (obligations) - basis not stated. Dollars: not stated (current-year FPDS dollars, i.e. nominal). Other transaction agreements, deobligation netting, IDV treatment, classified actions: not stated.
- **Diagnostics.** These are shown next to the main number and never replace it:
  - without IDV rows: $740,952,078,179.60 (-4.27% gap);
  - positive amounts only: $795,433,621,870.68 (2.77% gap).

**GSA-15H-FY2025 (FY2025, government-wide): WARN, gap -2.32%.**

- **Possible reasons:**
  - definitions: IDV rows, other transaction agreements, classified actions;
  - whether deobligations are netted;
  - the source's data date versus ours (2026-09-06);
  - constant versus nominal dollars.
- **What the source says it includes and excludes:** Includes (stated): "all prime contract procurements made during each fiscal year (FY), not excluding any contract awarded"; "includes procurements made for the Federal Government, including each of the 24 Chief Financial Officers (CFO) Act agencies"; the figure is followed by other-than-small-business and small-business expenditure totals; the Final Data Report's other-than-small line reads "In the aggregate, without exclusions". Uses the word "expenditures" but the source is FPDS dollar amounts (obligations) - basis not stated. Dollars: not stated (current-year FPDS dollars, i.e. nominal). Other transaction agreements, deobligation netting, IDV treatment, classified actions: not stated.
- **Diagnostics.** These are shown next to the main number and never replace it:
  - without IDV rows: $778,489,275,685.34 (-4.13% gap);
  - positive amounts only: $846,547,964,967.59 (4.25% gap).

## Inside our own data (no outside source needed)

- **Thin months (H01 rows, H02 dollars; under half the year's median month):** 2009-01: net $19,117,420,775.83 vs a median of $42,719,639,132.76.
- **Agencies missing in a middle year (H03):** 090 Selective Service System: no rows in FY2014; 3301 John F. Kennedy Center for the Performing Arts: no rows in FY2017; 394 National Capital Planning Commission: no rows in FY2018; 432 Occupational Safety and Health Review Commission: no rows in FY2010-FY2015; 510 United States Chemical Safety Board: no rows in FY2021; 525 Election Assistance Commission: no rows in FY2012-FY2016; 9566 Federal Housing Finance Agency: no rows in FY2011.
- **Agencies: drops below 20% of the year before that recover (H04/H05/H07/H08):** H04 1133 United States Trade and Development Agency, FY2012: $1,744,806.60 after $11,999,001.85 the year before.
- **Sub-agencies missing in a middle year (H06):** 12D3 Foreign Agricultural Service (Department of Agriculture): no rows in FY2010; 1635 Employment Standards Administration (Department of Labor): no rows in FY2011, FY2013; 3352 John F. Kennedy Center for the Performing Arts (John F. Kennedy Center for the Performing Arts): no rows in FY2017; 4700 General Services Administration (General Services Administration): no rows in FY2011-FY2015; 4775 Technology Transformation Service (General Services Administration): no rows in FY2021, FY2023-FY2024; 7555 Program Support Center (Department of Health and Human Services): no rows in FY2013-FY2014; 9000 Selective Service System (Selective Service System): no rows in FY2014; 9502 National Capital Planning Commission (National Capital Planning Commission): no rows in FY2018; 9514 Occupational Safety and Health Review Commission (Occupational Safety and Health Review Commission): no rows in FY2010-FY2015; 9523 Election Assistance Commission (Election Assistance Commission): no rows in FY2012-FY2016; 9542 Federal Housing Finance Agency (Federal Housing Finance Agency): no rows in FY2011; 9565 United States Chemical Safety Board (United States Chemical Safety Board): no rows in FY2021; 97EX Office of the Inspector General (Department of Defense): no rows in FY2023; 97HW Uniformed Services University of the Health Sciences (Department of Defense): no rows in FY2012-FY2013.
- **Sub-agencies: drops below 20% of the year before that recover (H04/H05/H07/H08):** H07 1153 United States Trade and Development Agency (United States Trade and Development Agency), FY2012: $1,744,806.60 after $11,999,001.85 the year before; H07 97AD Immediate Office of the Secretary of Defense (Department of Defense), FY2024: $4,273,371.00 after $130,428,574.42 the year before.

## Sources

- **GAO-FY2018-bound**: U.S. Government Accountability Office (GAO), "Federal Government Contracting for Fiscal Year 2018 (infographic)", published 2019-05-28. <https://www.gao.gov/blog/2019/05/28/federal-government-contracting-for-fiscal-year-2018-infographic>.
  - Figure: $550,000,000,000.00 (nominal (GAO's charts say constant fiscal year 2018 dollars, which equals nominal for FY2018)).
  - Scope: Federal contract spending, government-wide (GAO analysis of FPDS data; the post says 'spent').
  - Quote or location: WatchBlog post: "In fiscal year 2018, the federal government spent more than $550 billion on these contracts, an increase of more $100 billion from 2015." (verbatim in saved copy). The infographic image reads "Fiscal year 2018 Obligations $554.1" (read from the image, not machine-checked).
  - Data as of: not stated ("Analysis of FY2018 FPDS-NG data").
- **GSA-15H-FY2018**: U.S. General Services Administration (GSA), Office of Small Business, "Executive Summary: FY 2018 Federal Procurement Data System GSA Report (GSA Reports Required by Section 15(h)(3)(A)(ii) of the Small Business Act)". <https://www.gsa.gov/system/files/FY18%20Sm%20Bus%20Act%20Section%2015%28h%29%283%29%28A%29%28ii%29%20FPDS%20GSA%20Report%20%20-%20Executive%20Summary.pdf>.
  - Figure: $555,000,000,000.00 (nominal).
  - Scope: Federal Government contract expenditures: all prime contract procurements made during the fiscal year, not excluding any contract awarded, for the Federal Government including the 24 CFO Act agencies (derived from FPDS).
  - Quote or location: Executive Summary, page 1, first paragraph: "Based on this report, Federal Government contract expenditures totaled $555 Billion during FY 2018." Same paragraph: "The information in this report was derived from the Federal Procurement Data System (FPDS)" - no data date is stated. Verbatim in extracted text. Text extracted with pdftotext. The GSA landing page (saved) labels this file as the FY 2018 executive summary.
  - Data as of: not stated.
- **GAO-FY2019-bound**: U.S. Government Accountability Office (GAO), "A Snapshot of Government-wide Contracting for FY 2019 (infographic)", published 2020-05-26. <https://www.gao.gov/blog/snapshot-government-wide-contracting-fy-2019-infographic>.
  - Figure: $586,000,000,000.00 (nominal (GAO's charts say constant fiscal year 2019 dollars, which equals nominal for FY2019)).
  - Scope: Federal contract spending, government-wide (GAO analysis of FPDS data; the post says 'spent').
  - Quote or location: WatchBlog post: "In FY 2019, the federal government spent more than $586 billion on these contracts, an increase of over $20 billion from FY 2018." (verbatim in saved copy). The infographic image reads "Fiscal year 2019 Obligations $586.2" (read from the image, not machine-checked).
  - Data as of: not stated ("Analysis of FY2019 FPDS-NG data").
- **GSA-15H-FY2019**: U.S. General Services Administration (GSA), Office of Small Business, "Executive Summary: FY 2019 Federal Procurement Data System GSA Report (GSA Reports Required by Section 15(h)(3)(A)(ii) of the Small Business Act)". <https://www.gsa.gov/system/files/Executive%20Summary_FY19%20GSA%20Report%20documents_0.pdf>.
  - Figure: $587,000,000,000.00 (nominal).
  - Scope: Federal Government contract expenditures: all prime contract procurements made during the fiscal year, not excluding any contract awarded, for the Federal Government including the 24 CFO Act agencies (derived from FPDS).
  - Quote or location: Executive Summary, page 1, first paragraph: "Based on this report, Federal Government contract expenditures totaled $587 billion during FY 2019." Same paragraph: "The information in this report for FY 2019 was derived from the Federal Procurement Data System (FPDS) on February 24, 2020". Verbatim in extracted text. Text extracted with pdftotext. The GSA landing page (saved) labels this file as the FY 2019 executive summary.
  - Data as of: FPDS data derived February 24, 2020.
- **GAO-FY2020-bound**: U.S. Government Accountability Office (GAO), "A Snapshot of Government-Wide Contracting For FY 2020 (infographic)", published 2021-06-22. <https://www.gao.gov/blog/snapshot-government-wide-contracting-fy-2020-infographic>.
  - Figure: $665,000,000,000.00 (nominal (GAO's charts say constant fiscal year 2020 dollars, which equals nominal for FY2020)).
  - Scope: Federal contract spending, government-wide (GAO analysis of FPDS data; the post says 'spent').
  - Quote or location: WatchBlog post: "In fiscal year 2020, the federal government spent more than $665 billion on contracts, an increase of over $70 billion from fiscal year 2019." (verbatim in saved copy). The infographic image reads "Fiscal year 2020 Obligations $665.1" (read from the image, not machine-checked).
  - Data as of: not stated ("Analysis of FY2020 FPDS-NG data").
- **GSA-15H-FY2020**: U.S. General Services Administration (GSA), Office of Small Business, "Executive Summary: FY 2020 Federal Procurement Data System GSA Report (GSA Reports Required by Section 15(h)(3)(A)(ii) of the Small Business Act)". <https://www.gsa.gov/system/files/Executive%20Summary_FY20%20GSA%20Report%20documents_0.pdf>.
  - Figure: $665,000,000,000.00 (nominal).
  - Scope: Federal Government contract expenditures: all prime contract procurements made during the fiscal year, not excluding any contract awarded, for the Federal Government including the 24 CFO Act agencies (derived from FPDS).
  - Quote or location: Executive Summary, page 1, first paragraph: "Based on this report, Federal Government contract expenditures totaled $665 billion during FY 2020." Same paragraph: "The information in this report for FY 2020 was derived from the Federal Procurement Data System (FPDS) on February 24, 2021". Verbatim in extracted text. Text extracted with pdftotext. The GSA landing page (saved) labels this file as the FY 2020 executive summary.
  - Data as of: FPDS data derived February 24, 2021.
- **GAO-FY2021**: U.S. Government Accountability Office (GAO), "A Snapshot of Government-wide Contracting for FY 2021 (Interactive Dashboard)", published 2022-08-25. <https://www.gao.gov/blog/snapshot-government-wide-contracting-fy-2021-interactive-dashboard>.
  - Figure: $637,000,000,000.00 (nominal (GAO's charts say constant fiscal year 2021 dollars, which equals nominal for FY2021)).
  - Scope: Federal contract spending, government-wide (GAO analysis of FPDS data; the post says 'spent').
  - Quote or location: WatchBlog post: "In Fiscal Year 2021, the federal government spent about $637 billion on contracts, a decrease of $54 billion from FY 2020 after adjusting for inflation." (verbatim in saved copy). An approximate figure, not a lower bound.
  - Data as of: not stated ("Analysis of FY2021 FPDS-NG data").
- **GSA-15H-FY2021**: U.S. General Services Administration (GSA), Office of Small Business, "Executive Summary: FY 2021 Federal Procurement Data System GSA Report (GSA Reports Required by Section 15(h)(3)(A)(ii) of the Small Business Act)". <https://www.gsa.gov/system/files/ExecutiveSummaryFY21GSAReportDocuments_0.pdf>.
  - Figure: $648,000,000,000.00 (nominal).
  - Scope: Federal Government contract expenditures: all prime contract procurements made during the fiscal year, not excluding any contract awarded, for the Federal Government including the 24 CFO Act agencies (derived from FPDS).
  - Quote or location: Executive Summary, page 1, first paragraph: "Based on this report, Federal Government contract expenditures totaled $648 billion during FY 2021." Same paragraph: "The information in this report for FY 2021 was derived from the Federal Procurement Data System (FPDS) on February 22, 2022". Verbatim in extracted text. Text extracted with pdftotext. The GSA landing page (saved) labels this file as the FY 2021 executive summary.
  - Data as of: FPDS data derived February 22, 2022.
- **GAO-FY2022**: U.S. Government Accountability Office (GAO), "A Snapshot of Government-Wide Contracting for FY 2022 (WatchBlog post); dashboard "A Snapshot: Government-Wide Contracting - A 2022 Update"", published 2023-08-15. <https://files.gao.gov/multimedia/Federal_Government_Contracting-FY2022/static/data/data.json>.
  - Figure: $694,000,000,000.00 (nominal).
  - Scope: Federal government obligations through contracts, government-wide (GAO analysis of Federal Procurement Data System data).
  - Quote or location: Dashboard data file (loaded by the dashboard page), variable textData, field "intro": "The federal government obligated $694 billion through contracts in fiscal year 2022, including about $40 billion related to the COVID-19 pandemic." (verbatim in saved copy). textData.sourceDate = "May 2023"; textData.fy = 2022. The WatchBlog post (https://www.gao.gov/blog/snapshot-government-wide-contracting-fy-2022) could not be saved: www.gao.gov returns HTTP 403 to curl.
  - Data as of: FPDS data as of May 2023.
- **GSA-15H-FY2022**: U.S. General Services Administration (GSA), Office of Small Business, "Executive Summary: FY 2022 Federal Procurement Data System GSA Report (GSA Reports Required by Section 15(h)(3)(A)(ii) of the Small Business Act)". <https://www.gsa.gov/system/files/ExecutiveSummaryFY%2722GSAReportDocuments%20%282%29%20%281%29.pdf>.
  - Figure: $705,000,000,000.00 (nominal).
  - Scope: Federal Government contract expenditures: all prime contract procurements made during the fiscal year, not excluding any contract awarded, for the Federal Government including the 24 CFO Act agencies (derived from FPDS).
  - Quote or location: Executive Summary, page 1, first paragraph: "Based on this report, Federal Government contract expenditures totaled $705 billion during FY 2022." Same paragraph: "The information in this report for FY 2022 was derived from the Federal Procurement Data System (FPDS) on February 22, 2023". Verbatim in extracted text. Text extracted with pdftotext. The GSA landing page (saved) labels this file as the FY 2022 executive summary.
  - Data as of: FPDS data derived February 22, 2023.
- **GAO-FY2023**: U.S. Government Accountability Office (GAO), "A Snapshot of Government-Wide Contracting for FY 2023 (WatchBlog post); dashboard "A Snapshot: Government-Wide Contracting - A 2023 Update"", published 2024-06-25. <https://files.gao.gov/multimedia/Federal_Government_Contracting/static/data/data.json>.
  - Figure: $759,000,000,000.00 (nominal).
  - Scope: Federal government obligations through contracts, government-wide (GAO analysis of Federal Procurement Data System data).
  - Quote or location: Dashboard data file (loaded by the dashboard page), variable textData, field "intro": "The federal government obligated $759 billion through contracts in fiscal year 2023, a $33 billion increase from fiscal year 2022 after adjusting for inflation." (verbatim in saved copy). textData.sourceDate = "May 2024"; textData.fy = 2023. The WatchBlog post (https://www.gao.gov/blog/snapshot-government-wide-contracting-fy-2023-interactive-dashboard) could not be saved: www.gao.gov returns HTTP 403 to curl. Note the FY2023 dashboard folder has no FY suffix.
  - Data as of: FPDS data as of May 2024.
- **GSA-15H-FY2023**: U.S. General Services Administration (GSA), Office of Small Business, "Executive Summary: FY 2023 Federal Procurement Data System GSA Report (GSA Reports Required by Section 15(h)(3)(A)(ii) of the Small Business Act)". <https://www.gsa.gov/system/files/ExecutiveSummaryFY%2723GSAReportDocuments_508.docx>.
  - Figure: $775,000,000,000.00 (nominal).
  - Scope: Federal Government contract expenditures: all prime contract procurements made during the fiscal year, not excluding any contract awarded, for the Federal Government including the 24 CFO Act agencies (derived from FPDS).
  - Quote or location: Executive Summary, page 1, first paragraph: "Based on this report, Federal Government contract expenditures totaled $775 billion during FY 2023." Same paragraph: "The information in this report for FY 2023 was derived from the Federal Procurement Data System (FPDS) on February 22, 2024". Verbatim in extracted text. Saved as .docx; text extracted with textutil. The GSA landing page (saved) labels this file as the FY 2023 executive summary.
  - Data as of: FPDS data derived February 22, 2024.
- **GAO-FY2024**: U.S. Government Accountability Office (GAO), "A Snapshot of Government-Wide Contracting for FY 2024 (WatchBlog post); dashboard "A Snapshot: Government-Wide Contracting - A 2024 Update"", published 2025-06-24. <https://files.gao.gov/multimedia/Federal_Government_Contracting-FY2024/static/data/data.json>.
  - Figure: $755,000,000,000.00 (nominal).
  - Scope: Federal government obligations through contracts, government-wide (GAO analysis of Federal Procurement Data System data).
  - Quote or location: Dashboard data file (loaded by the dashboard page), variable textData, field "intro": "The federal government obligated $755 billion through contracts in fiscal year 2024, a $22.5 billion decrease from fiscal year 2023 after adjusting for inflation." (verbatim in saved copy). textData.sourceDate = "June 2025"; textData.fy = 2024. The WatchBlog post (https://www.gao.gov/blog/snapshot-government-wide-contracting-fy-2024-interactive-dashboard) could not be saved: www.gao.gov returns HTTP 403 to curl. Data file also has a field "NaN" saying "All obligation amounts are presented in constant FY 2024 dollars" (consistent here).
  - Data as of: FPDS data as of June 2025.
- **GSA-15H-FY2024**: U.S. General Services Administration (GSA), Office of Small Business, "Executive Summary: FY 2024 Federal Procurement Data System GSA Report (GSA Reports Required by Section 15(h)(3)(A)(ii) of the Small Business Act)". <https://www.gsa.gov/system/files/Executive%20Summary_%20FY%202024%20FPDS%20GSA%20Report.pdf>.
  - Figure: $774,000,000,000.00 (nominal).
  - Scope: Federal Government contract expenditures: all prime contract procurements made during the fiscal year, not excluding any contract awarded, for the Federal Government including the 24 CFO Act agencies (derived from FPDS).
  - Quote or location: Executive Summary, page 1, first paragraph: "Based on this report, Federal Government contract expenditures totaled $774 billion during FY 2024." Same paragraph: "The information in this report for FY 2024 was derived from the Federal Procurement Data System (FPDS) on February 20, 2025". Verbatim in extracted text. Text extracted with pdftotext. The GSA landing page (saved) labels this file as the FY 2024 executive summary.
  - Data as of: FPDS data derived February 20, 2025.
- **GAO-FY2025**: U.S. Government Accountability Office (GAO), "A Snapshot of Government-Wide Contracting for FY 2025 (WatchBlog post); dashboard "A Snapshot: Government-Wide Contracting - A 2025 Update"", published 2026-05-05. <https://files.gao.gov/multimedia/Federal_Government_Contracting-FY2025/static/data/data.json>.
  - Figure: $793,000,000,000.00 (nominal).
  - Scope: Federal government obligations through contracts, government-wide (GAO analysis of Federal Procurement Data System data).
  - Quote or location: Dashboard data file (loaded by the dashboard page), variable textData, field "intro": "The federal government obligated $793 billion through contracts in fiscal year 2025, a $17.8 billion increase from fiscal year 2024 after adjusting for inflation." (verbatim in saved copy). textData.sourceDate = "April 2026"; textData.fy = 2025. The WatchBlog post (https://www.gao.gov/blog/snapshot-government-wide-contracting-fy-2025-interactive-dashboard) could not be saved: www.gao.gov returns HTTP 403 to curl. Data file also has a leftover field "NaN" saying "All obligation amounts are presented in constant FY 2024 dollars", which contradicts the page footer (constant FY 2025) and looks stale. The FY2025 GAO_REFERENCE row in src/config.py is carried over unchanged; its quote matches this field verbatim.
  - Data as of: FPDS data as of April 2026.
- **GSA-15H-FY2025**: U.S. General Services Administration (GSA), Office of Small Business, "Executive Summary: FY 2025 Federal Procurement Data System GSA Report (GSA Reports Required by Section 15(h)(3)(A)(ii) of the Small Business Act)". <https://www.gsa.gov/system/files/Executive%20Summary.pdf>.
  - Figure: $812,000,000,000.00 (nominal).
  - Scope: Federal Government contract expenditures: all prime contract procurements made during the fiscal year, not excluding any contract awarded, for the Federal Government including the 24 CFO Act agencies (derived from FPDS).
  - Quote or location: Executive Summary, page 1, first paragraph: "Based on this report, Federal Government contract expenditures totaled $812 billion during FY 2025." Same paragraph: "The information in this report for FY 2025 was derived from the Federal Procurement Data System (FPDS) on February 20, 2026". Verbatim after removing zero-width spaces (U+200B) that the PDF puts between words. Text extracted with pdftotext. The GSA landing page (saved) labels this file as the FY 2025 executive summary.
  - Data as of: FPDS data derived February 20, 2026.
