# Vendor Concentration in Federal Contracting by Agency, Product and Year, FY2008 to FY2025

*Authors.* Suchitra Hole, Shivram Nekkanti, Andy Hannah

*Sponsor.* [SPONSOR NAME AND ROLE, AND CONFIRMATION THAT THEY AGREED TO SERVE]

*GitHub.* [https://github.com/abh5227/federal-contracting-concentration](https://github.com/abh5227/federal-contracting-concentration)

## Summary

The federal government obligated $793 billion through contracts in FY2025 [[1]](https://files.gao.gov/multimedia/Federal_Government_Contracting-FY2025/static/data/data.json). In defense, a few firms now lead most major weapon programs. US aerospace and defense prime contractors fell from 51 in 1993 to 5 in 2000 [[2]](https://media.defense.gov/2022/Feb/15/2002939087/-1/-1/1/STATE-OF-COMPETITION-WITHIN-THE-DEFENSE-INDUSTRIAL-BASE.PDF), and at least one of those five is a prime contractor on 58 of the 78 major weapon systems in DoD's FY2024 budget [[3]](https://www.congress.gov/crs_external_products/R/PDF/R47751/R47751.1.pdf). Studies that measure concentration directly also stay within defense [[4]](https://doi.org/10.1016/j.jpubeco.2020.104141), [[5]](https://www.dair.nps.edu/bitstream/123456789/2733/1/CSIS-AM-18-230.pdf), [[6]](https://csis-website-prod.s3.amazonaws.com/s3fs-public/2023-12/231207_Sanders_Defense_Acquisition_Trends_2023.pdf). The closest one compares DoD with all other agencies combined but measures concentration for only five product categories, over FY2010 to FY2019 [[7]](https://dair.nps.edu/bitstream/123456789/4827/1/SYM-AM-23-058.pdf). We found no measure for the rest of the government, so we build one for every agency, product and year from FY2008 to FY2025. The measure, its pipeline and the review of the data's gaps are our own work. A high score is not evidence of wrongdoing. One shipyard building aircraft carriers can be the sensible arrangement, so we describe where concentration sits and how it changes without claiming causes. The measure also has limits. It counts prime contractors only, and parent company IDs can lag a merger by 2 to 6 months [[8]](https://github.com/abh5227/federal-contracting-concentration/blob/main/reports/integrity/integrity_report_v3.pdf). It also looks at one buyer at a time, so a vendor can win most of one agency's purchases and still face many rivals elsewhere, and the antitrust cutoffs for a concentrated market serve only as a rough guide.

We use every federal contract transaction in USAspending's Award Data Archive from FY2008 to FY2025, 88,753,968 rows in all [[9]](https://www.usaspending.gov/download_center/award_data_archive). Each transaction carries a product or service code, a four-character label for what was bought, such as 1510 for fixed-wing aircraft. We group transactions into segments, one for each awarding agency, product code and fiscal year. Within each segment we compute the Herfindahl-Hirschman Index (HHI), the sum of each vendor's squared percentage share of the segment's dollars, which runs from near 0 to 10,000 [[10]](https://www.justice.gov/atr/herfindahl-hirschman-index). Take two agencies that each spend $100M on one product across five vendors. Paying $20M to each scores 20² × 5 = 2,000. Paying $80M to one and $5M to each of the others scores 80² + 5² × 4 = 6,500. We score every segment, sort each agency and product's yearly trend into one of a few common shapes and compare the rising ones with the rest. The project asks three questions.

1. Can USAspending records support a trustworthy concentration score?
2. What common paths does concentration follow over time, such as a steady rise, a steady fall or a one-time jump?
3. What do agencies and products that came to rely on a few vendors have in common, such as sole-source awards?

## Proposed plan

*Data and processing.* Our pipeline keeps every row in stages, so nothing is thrown away. The published zip files, a verified Parquet copy and flags from 62 rule checks already exist [[8]](https://github.com/abh5227/federal-contracting-concentration/blob/main/reports/integrity/integrity_report_v3.pdf), and the working set will log every row it leaves out or changes, with the reason. A vendor is the parent company ID on the row, or the company's own ID where no parent is given, and deobligations count as negative dollars. The team will first settle the nine main data decisions from our integrity review. Product codes changed meaning twice, in FY2012 [[11]](https://www.acquisition.gov/sites/default/files/page_file_uploads/PSC%20Manual%20-%20Final%20-%2011%20August%202011.pdf) and FY2021 [[12]](https://www.acquisition.gov/sites/default/files/manual/PSC_Manual_October_2020.pdf), [[13]](https://github.com/abh5227/federal-contracting-concentration/blob/main/reports/research/government_documented_gaps_v3.pdf), so each trend line stays within one code era, and we also compare trends at a coarser level that stayed stable. We work in Python and use DuckDB, a database engine inside Python that lets one laptop query all 88.8 million rows without a database server. HHI needs no inflation adjustment, because inflation scales every vendor equally, and only charts of dollar totals will use constant FY2025 dollars.

*Analysis.* We compute HHI and the top-4 share, the percentage held by the four largest vendors, for about 365,000 segments [[8]](https://github.com/abh5227/federal-contracting-concentration/blob/main/reports/integrity/integrity_report_v3.pdf). The yearly values for one agency and product code form a trend line. For question 2 we sort these thousands of lines into a few shapes with k-means clustering. Lines are centered and scaled first, so they group by shape regardless of size. We try 2 to 10 groups and keep the number with the best average silhouette width. Lines with too few years or dollars are set aside by a rule fixed in advance. For question 3, a line is rising if its average HHI over its last 3 years is at least 500 points above its average over its first 3 years, and we repeat the analysis at 250 and 1,000 points. To learn what sets rising lines apart, we fit a logistic regression with an L1 penalty, which keeps only the features that help, and a shallow decision tree, which states the result as a few readable rules. Candidate features start with the sole-source share, the share of dollars awarded without competition, measured for umbrella contracts and for the orders placed under them. The others are the contract type mix, whether the segment covers products, services or research, the shares placed through contract vehicles and set aside for small business, the number of vendors and the segment's size. Features come from each line's first 3 years, before any rise, and the vendor count is the starting count, since a falling count raises HHI by itself. Competed awards that drew a single offer enter for FY2012 to FY2017 for now, the years offers received is coded consistently. Both models describe what goes together, so a link with sole-source awards could run in either direction.

*Evaluation.* A pattern counts as a result only if it passes every check below, with proposed thresholds fixed before we look at results. Our fallback, should the full scope prove too large, is one department over all 18 years with the same method.

| Check | Criterion |
|---|---|
| Totals | Our total is within 2% of GAO's in every year GAO reports one. FY2022 to FY2025 already match within 0.2%. |
| Data decisions | The pattern holds under each alternative decision, and we report how many segments change concentration band. |
| Robustness | The pattern holds with top-4 share, two-character product codes, fewer years and 3-year pooled windows. |
| Clusters | Average silhouette width is at least 0.25, and the mean adjusted Rand index over 100 bootstrap samples is at least 0.6. |
| Descriptive models | Five-fold cross-validated AUC beats an agency-and-size baseline by at least 0.05, with a 95% interval above zero. |
| Face validity | The sponsor confirms segments with a known answer, such as aircraft carrier shipbuilding. |

## Preliminary results

*Completeness.* All 97 CSV files in the 18 yearly zips were copied without loss, confirmed by record counts, dollar totals and checksums over every field. Our yearly totals match GAO within 0.2% for FY2022 to FY2025 [[1]](https://files.gao.gov/multimedia/Federal_Government_Contracting-FY2025/static/data/data.json), [[14]](https://files.gao.gov/multimedia/Federal_Government_Contracting-FY2022/static/data/data.json), [[15]](https://files.gao.gov/multimedia/Federal_Government_Contracting/static/data/data.json), [[16]](https://files.gao.gov/multimedia/Federal_Government_Contracting-FY2024/static/data/data.json). The integrity review found five issues that would distort the measure [[8]](https://github.com/abh5227/federal-contracting-concentration/blob/main/reports/integrity/integrity_report_v3.pdf). A $13.9 billion entry and its reversal fall in different fiscal years, and two US Mint rows record $10 billion each on contract vehicles. About 7.5% of vendor totals in a segment are negative. One placeholder name covers many foreign vendors, and early years carry a placeholder funding agency.

*A first look at concentration.* We computed the measure for FY2024 and FY2025, the two years free of those large-record issues. About 30% of segments have a single vendor, but together they hold under 2% of dollars. Most of the increase from FY2024 to FY2025 comes from a few very large defense segments. DoD's fixed-wing aircraft, combat ships and managed health care segments account for about $71 billion of the $130 billion rise in dollars held in segments with HHI above 2,500, and in fixed-wing aircraft alone dollars nearly doubled to $42.0 billion as the largest vendor's share went from 39% to 76%. Multi-year awards that land in one year can cause swings like these, so trends will be judged over pooled windows and the full 18 years. The figures come before the team's decisions, except that only vendors with a positive net count, decision 8's first option. That leaves 2,282 segments in FY2024 and 2,868 in FY2025 unscored, with 9.2% and 9.9% of vendor totals negative.

| Measure | FY2024 | FY2025 |
|---|---|---|
| Segments | 18,243 | 17,203 |
| Median vendors per segment | 4 | 4 |
| Median vendors per segment with a positive net | 3 | 2 |
| Net dollars in segments with HHI above 1,800, the 2023 guideline [[17]](https://www.ftc.gov/system/files/ftc_gov/pdf/2023_merger_guidelines_final_12.18.2023.pdf) | 46.9% | 59.1% |
| Net dollars in segments with HHI above 2,500, the 2010 guideline [[18]](https://www.justice.gov/sites/default/files/atr/legacy/2010/08/19/hmg-2010.pdf) | 35.5% | 50.3% |
| Dollar-weighted median HHI | 1,576 | 2,548 |

## Project milestones

Weeks follow the 13-week plan from our pitch. Calendar dates will be filled in once the course schedule is confirmed.

| Milestone | Target | Deliverable | Done when |
|---|---|---|---|
| Download, verify and review 18 years | Weeks 1 to 3, done | Parquet copy, integrity report | Totals within 0.2% of GAO, 62 checks run |
| Settle the nine data decisions | Week 4 | Decision log | All nine decided with the sponsor |
| Stage 3 and exclusions ledger | Week 5 | Working set, ledger | Working set plus ledger equals Stage 1 |
| Parent roll-up | Week 6 | Vendor key by era | Top 100 vendors checked by hand |
| Product code handling | Week 7 | Era rule, roll-up table | Every code mapped |
| Concentration table | Week 8 | HHI and top-4 per segment | Every segment scored, totals reconciled |
| Clustering of trend shapes | Weeks 9 to 10 | Named shapes | Quality thresholds met |
| Descriptive model | Week 11 | Model, features | Beats the baseline AUC |
| Robustness runs | Week 12 | Robustness table | All robustness checks run |
| Dashboard, write-up, code | Week 13 | Final report | Submitted by [FINAL REPORT DUE DATE] |

## References

[1] U.S. Government Accountability Office, "A Snapshot: Government-Wide Contracting, A 2025 Update," dashboard data file, May 2026. [Online]. Available: [https://files.gao.gov/multimedia/Federal_Government_Contracting-FY2025/static/data/data.json](https://files.gao.gov/multimedia/Federal_Government_Contracting-FY2025/static/data/data.json) (accessed Oct. 5, 2026).

[2] Office of the Under Secretary of Defense for Acquisition and Sustainment, "State of Competition within the Defense Industrial Base," U.S. Dept. of Defense, Washington, DC, USA, Feb. 2022, pp. 1, 23. [Online]. Available: [https://media.defense.gov/2022/Feb/15/2002939087/-1/-1/1/STATE-OF-COMPETITION-WITHIN-THE-DEFENSE-INDUSTRIAL-BASE.PDF](https://media.defense.gov/2022/Feb/15/2002939087/-1/-1/1/STATE-OF-COMPETITION-WITHIN-THE-DEFENSE-INDUSTRIAL-BASE.PDF) (accessed Oct. 6, 2026).

[3] L. A. Nicastro, "The U.S. Defense Industrial Base: Background and Issues for Congress," Congressional Research Service, Washington, DC, USA, Rep. R47751, Oct. 12, 2023, p. 9. [Online]. Available: [https://www.congress.gov/crs_external_products/R/PDF/R47751/R47751.1.pdf](https://www.congress.gov/crs_external_products/R/PDF/R47751/R47751.1.pdf) (accessed Oct. 6, 2026).

[4] R. Carril and M. Duggan, "The impact of industry consolidation on government procurement: Evidence from Department of Defense contracting," *J. Public Econ.*, vol. 184, Art. no. 104141, 2020, doi: 10.1016/j.jpubeco.2020.104141.

[5] A. P. Hunter, G. Sanders, and Z. Huitink, "Evaluating Consolidation and the Threat of Monopolies within Industrial Sectors," Center for Strategic and International Studies, Washington, DC, USA, Rep. CSIS-AM-18-230, Aug. 2018. [Online]. Available: [https://www.dair.nps.edu/bitstream/123456789/2733/1/CSIS-AM-18-230.pdf](https://www.dair.nps.edu/bitstream/123456789/2733/1/CSIS-AM-18-230.pdf) (accessed Oct. 6, 2026).

[6] G. Sanders, N. Velazquez, E. Hardesty, and A. Aldisert, "Defense Acquisition Trends 2023: A Preliminary Look," CSIS Brief, Center for Strategic and International Studies, Washington, DC, USA, Dec. 2023. [Online]. Available: [https://csis-website-prod.s3.amazonaws.com/s3fs-public/2023-12/231207_Sanders_Defense_Acquisition_Trends_2023.pdf](https://csis-website-prod.s3.amazonaws.com/s3fs-public/2023-12/231207_Sanders_Defense_Acquisition_Trends_2023.pdf) (accessed Oct. 6, 2026).

[7] E. Hyatt, "Effective competition and market concentration in the defense industrial base and the U.S. federal government," in *Proc. 20th Annu. Acquisition Research Symp.*, Naval Postgraduate School, Monterey, CA, USA, May 2023, pp. 167 to 185, Rep. SYM-AM-23-058. [Online]. Available: [https://dair.nps.edu/bitstream/123456789/4827/1/SYM-AM-23-058.pdf](https://dair.nps.edu/bitstream/123456789/4827/1/SYM-AM-23-058.pdf) (accessed Oct. 6, 2026).

[8] Federal contracting concentration project team, "Integrity and completeness findings, FY2008 to FY2025 (version 3)," project repository, Oct. 2026. [Online]. Available: [https://github.com/abh5227/federal-contracting-concentration/blob/main/reports/integrity/integrity_report_v3.pdf](https://github.com/abh5227/federal-contracting-concentration/blob/main/reports/integrity/integrity_report_v3.pdf) (accessed Oct. 7, 2026).

[9] U.S. Department of the Treasury, Bureau of the Fiscal Service, "Award Data Archive," USAspending.gov, contracts, all agencies, full files for FY2008 to FY2025, release of Sep. 6, 2026. [Online]. Available: [https://www.usaspending.gov/download_center/award_data_archive](https://www.usaspending.gov/download_center/award_data_archive) (accessed Oct. 6, 2026).

[10] U.S. Department of Justice, Antitrust Division, "Herfindahl-Hirschman Index." [Online]. Available: [https://www.justice.gov/atr/herfindahl-hirschman-index](https://www.justice.gov/atr/herfindahl-hirschman-index) (accessed Oct. 6, 2026).

[11] U.S. General Services Administration, "Federal Procurement Data System Product and Service Codes Manual," Aug. 2011 ed., V1.1, effective Oct. 1, 2011. [Online]. Available: [https://www.acquisition.gov/sites/default/files/page_file_uploads/PSC%20Manual%20-%20Final%20-%2011%20August%202011.pdf](https://www.acquisition.gov/sites/default/files/page_file_uploads/PSC%20Manual%20-%20Final%20-%2011%20August%202011.pdf) (accessed Oct. 6, 2026).

[12] U.S. General Services Administration, "Product and Service Codes (PSC) Manual," Oct. 2020 ed., V1.5. [Online]. Available: [https://www.acquisition.gov/sites/default/files/manual/PSC_Manual_October_2020.pdf](https://www.acquisition.gov/sites/default/files/manual/PSC_Manual_October_2020.pdf) (accessed Oct. 6, 2026).

[13] Federal contracting concentration project team, "Government-documented gaps in federal contract data (version 3)," project repository, Oct. 2026. [Online]. Available: [https://github.com/abh5227/federal-contracting-concentration/blob/main/reports/research/government_documented_gaps_v3.pdf](https://github.com/abh5227/federal-contracting-concentration/blob/main/reports/research/government_documented_gaps_v3.pdf) (accessed Oct. 7, 2026).

[14] U.S. Government Accountability Office, "A Snapshot: Government-Wide Contracting, A 2022 Update," dashboard data file, Aug. 2023. [Online]. Available: [https://files.gao.gov/multimedia/Federal_Government_Contracting-FY2022/static/data/data.json](https://files.gao.gov/multimedia/Federal_Government_Contracting-FY2022/static/data/data.json) (accessed Oct. 5, 2026).

[15] U.S. Government Accountability Office, "A Snapshot: Government-Wide Contracting, A 2023 Update," dashboard data file, Jun. 2024. [Online]. Available: [https://files.gao.gov/multimedia/Federal_Government_Contracting/static/data/data.json](https://files.gao.gov/multimedia/Federal_Government_Contracting/static/data/data.json) (accessed Oct. 5, 2026).

[16] U.S. Government Accountability Office, "A Snapshot: Government-Wide Contracting, A 2024 Update," dashboard data file, Jun. 2025. [Online]. Available: [https://files.gao.gov/multimedia/Federal_Government_Contracting-FY2024/static/data/data.json](https://files.gao.gov/multimedia/Federal_Government_Contracting-FY2024/static/data/data.json) (accessed Oct. 5, 2026).

[17] U.S. Department of Justice and Federal Trade Commission, "Merger Guidelines," Dec. 18, 2023, Guideline 1, p. 5. [Online]. Available: [https://www.ftc.gov/system/files/ftc_gov/pdf/2023_merger_guidelines_final_12.18.2023.pdf](https://www.ftc.gov/system/files/ftc_gov/pdf/2023_merger_guidelines_final_12.18.2023.pdf) (accessed Oct. 6, 2026).

[18] U.S. Department of Justice and Federal Trade Commission, "Horizontal Merger Guidelines," Aug. 19, 2010, Sec. 5.3, p. 19. [Online]. Available: [https://www.justice.gov/sites/default/files/atr/legacy/2010/08/19/hmg-2010.pdf](https://www.justice.gov/sites/default/files/atr/legacy/2010/08/19/hmg-2010.pdf) (accessed Oct. 6, 2026).
