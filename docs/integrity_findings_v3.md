# Integrity and completeness findings, FY2008 to FY2025 (version 3)

All 88,753,968 federal contract transactions in USAspending's Award Data Archive, release of 2026-09-06, checked without changing any value.

## Summary

This report checks whether the federal contract data behind our project is complete and clean enough to measure how concentrated federal contracting is. It covers every transaction from FY2008 to FY2025 in USAspending's Award Data Archive. No value was changed. Every finding describes the data as published.

The data is complete and was copied without loss. Every fiscal year's copy is verified against its published zip file. Our yearly totals match GAO's figures within 0.2% in the four years GAO publishes exact figures, FY2022 to FY2025. They also clear GAO's lower bounds for FY2018 to FY2020. We found no published total for FY2008 to FY2017, so those years rest on our internal checks.

Complete data can still mislead a concentration measure. Five issues would distort it if the data were used as it stands.

- A $13.9 billion entry and its reversal fall in different fiscal years and break two cells.
- Two US Mint rows record $10 billion each on contract vehicles whose orders carry their own obligations.
- About 7.5% of vendor totals within a cell are negative.
- One vendor name, MISCELLANEOUS FOREIGN AWARDEES, stands for many foreign companies.
- The early years carry a placeholder funding agency and fields whose coverage changes over time.

Each issue comes with a proposed decision for the team, and the nine decisions come first, in one table. None is decided yet.

## Decisions for the team

| # | Decision | Options | Proposed by Andy |
|---|---|---|---|
| 1 | Reversal pairs | Keep both rows. Move both rows to the exclusions ledger. Move both to the ledger and carry their net forward. | Move both rows to the ledger and keep their net as one documented adjustment. |
| 2 | The two $10 billion US Mint rows | Keep them. Exclude them as ceilings recorded as obligations. Hold them out until a source confirms them. | Keep them out of HHI until a source confirms they are real obligations. |
| 3 | The FY2015 step in row counts | Count every row. Report small orders separately. Start count trends at FY2015. Count only actions above a fixed size. | Keep every row for dollar measures. For count measures, count only actions of $10,000 or more in every year. |
| 4 | Funding agency code 999 | Label it "unknown funding agency". Leave FY2008 to FY2010 out of funding-agency work. Use the awarding agency. | Use the awarding agency for the main analysis. Limit funding-agency checks to FY2011 onward. |
| 5 | Competition measure | The extent-competed code, the number of offers, or both, with or without year limits. | The extent-competed code as the main measure. The number of offers only within FY2011 to FY2017. |
| 6 | Parent roll-up | The parent recorded at the time of the action. Today's parent for every action. | The parent recorded at the time of the action, for the eras the parent test supports. |
| 7 | Primary benchmark | GAO, GSA, or the worse of the two. | GAO primary, GSA as context. |
| 8 | Negative vendor totals | Shares over vendors with a positive net only. Set negative totals to zero. Move the deobligation rows behind them to the ledger. Use a coarser product code. | Decide after seeing the counts. |
| 9 | MISCELLANEOUS FOREIGN AWARDEES | Score it as one vendor. Report it separately and leave it out of HHI. Spread it across foreign vendors by some rule. | Report it separately, leave it out of HHI, and state the share of dollars left out. |

## How the data was checked

The work had three parts, and each can be repeated from the code.

**The copy.** The 18 yearly zip files hold 97 CSV files. For each one, two independent readers agree on the record count, the exact dollar total and a checksum over every field of every row. All 18 years pass. The checksum is extremely strong. It still does not compare rows one by one, so this report says the copy is verified.

**The rules.** 62 checks ran on every row of every year, each with a fixed rule and threshold. The rules were committed before the first run. Any rule changed after seeing results is disclosed in the appendix with its date and reason.

**The totals.** Each year's net total was compared with published figures from GAO and GSA.

A few terms recur throughout.

- **Cell.** One awarding agency, one product or service code and one fiscal year. Concentration is measured within each cell.
- **Vendor.** The parent UEI recorded on the row, or the recipient UEI where the parent is blank.
- **Net dollars.** The sum of obligations, with deobligations counted as negative amounts.
- **Gross dollars.** The sum of the absolute amounts, so a +$5 entry and a -$5 reversal count as $10.
- **HHI.** 10,000 times the sum of each vendor's squared share of the cell. HHI values in this report are for illustration and use vendors with a positive net only.

## Is the data complete?

The 18 years hold 88,753,968 rows and $10.51 trillion in net obligations. The picture by year is steady, apart from three years that carry known issues.

<!-- figure: rows_and_dollars_v2 -->

Two bodies publish yearly totals that can serve as a check. GAO and GSA both start from the Federal Procurement Data System (FPDS), the same system USAspending draws from. A match therefore shows that we extracted and summed the data correctly. It cannot catch an error inside FPDS itself.

The benchmarks are uneven. Four of the 18 years, FY2022 to FY2025, have a well-defined GAO figure. Four more, FY2018 to FY2021, have a loosely defined one, made of a GSA figure and a GAO statement that is a lower bound or an approximation. The other 10 years, FY2008 to FY2017, have none that we found. With GAO as the primary benchmark and GSA as context, all eight benchmarked years pass. Under the version 1 rule, which took the worse of GAO and GSA, six pass and two warn.

| FY | Class | GAO | GAO gap | GSA gap, context | Status, versions 2 and 3 | Status, version 1 |
|---|---|---|---|---|---|---|
| 2018 | loosely defined | more than $550B | ours is 1.10% above | +0.18% | PASS | PASS |
| 2019 | loosely defined | more than $586B | ours is 0.64% above | +0.47% | PASS | PASS |
| 2020 | loosely defined | more than $665B | ours is 0.97% above | +0.97% | PASS | PASS |
| 2021 | loosely defined | about $637B | +1.32% | -0.40% | PASS | PASS |
| 2022 | well-defined | $694B | +0.10% | -1.46% | PASS | PASS |
| 2023 | well-defined | $759B | +0.19% | -1.88% | PASS | PASS |
| 2024 | well-defined | $755B | +0.18% | -2.28% | PASS | WARN |
| 2025 | well-defined | $793B | +0.02% | -2.32% | PASS | WARN |

A year passes within 2% of its benchmark, warns within 10% and fails beyond 10%. These thresholds were fixed before any comparison. Three details matter for reading the table.

- **GAO's lower bounds.** GAO's posts for FY2018 to FY2020 say the government "spent more than" $550 billion, $586 billion and $665 billion on contracts. Our totals are above all three. The infographics in those posts show $554.1 billion, $586.2 billion and $665.1 billion. These one-decimal figures were read from the images and are not machine-checked.
- **GAO in FY2021.** GAO's post says the government "spent about $637 billion on contracts". The figure is approximate, and our total is 1.32% above it.
- **GSA's figures.** They run $10.3 billion to $18.8 billion above ours in FY2022 to FY2025. GSA calls its figure "expenditures" and does not say how it treats contract vehicles, deobligations or classified actions. The gap needs an explanation from GSA before it counts against our data.

<!-- figure: benchmarks_v2 -->

For FY2008 to FY2017 the internal checks are the only evidence. Every month of every year has data. Only one month is thin, January 2009, which holds a $13.9 billion reversal. The agencies missing in a middle year are all small. These checks catch gaps. They cannot detect a shortfall spread evenly across a year.

<!-- figure: months_heatmap_v2 -->

## What would distort the concentration measure

The measure turns each vendor's net dollars within a cell into shares. Anything that inflates one vendor's dollars, makes a total negative, or merges many companies into one vendor moves HHI and the top-4 share with no change in the market itself. Five findings do that. They run from the most severe single records to the broadest patterns.

### Large entries that were reversed later

Five entries of $7.0 billion to $344.7 billion were recorded and then reversed. Four of the reversals came within a week, inside the same fiscal year. The fifth crossed into the next fiscal year, and that one does real damage.

| FY | Contract | Entry | Reversal | Left over |
|---|---|---|---|---|
| 2013 | Army `W912GB09C0090` (MISCELLANEOUS FOREIGN AWARDEES) | +$344,733,911,303.88 (P00006, 2013-09-26) | -$344,733,702,433.01 (P00007, 2013-09-27) | +$208,870.87 |
| 2009 | Army `W912ER04D0004` order 0021 (Fluor Intercontinental) | +$116,091,716,928.00 (mod 13, 2009-08-24) | -$116,092,075,155.00 (mod 14, 2009-08-27) | -$358,227.00 |
| 2015 | Army `W912DR12C0019` (Hensel Phelps Construction) | +$92,490,715,466.13 (P00008, 2015-05-12) | -$92,490,158,844.13 (P00009, 2015-05-13) | +$556,622.00 |
| 2020 | Navy `N0001914C0002` (Lockheed Martin) | -$7,017,900,026.25 (P00081, 2019-12-04) | +$7,017,900,026.25 (P00082, 2019-12-10) | $0.00 |

Inside one fiscal year a pair barely touches HHI. Both rows sit with the same vendor in the same cell, so they cancel. The largest change across the four cells is 2.5 points.

| Pair | Cell | Vendors in cell | HHI with pair | HHI without pair |
|---|---|---|---|---|
| FY2013 Army `W912GB09C0090` | Defense, Y112 construction of conference space, FY2013 | 9 | 4,601.3 | 4,601.3 |
| FY2009 Army `W912ER04D0004` order 0021 | Defense, AD25 defense research, FY2009 | 133 | 1,601.9 | 1,599.4 |
| FY2015 Army `W912DR12C0019` | Defense, Y1AZ construction of administrative buildings, FY2015 | 440 | 747.3 | 746.2 |
| FY2020 Navy `N0001914C0002` | Defense, 1510 fixed-wing aircraft, FY2020 | 63 | 6,467.3 | 6,467.3 |

The FY2013 cell has a negative net either way, -$1.71 million with the pair and -$1.91 million without it. Its one large vendor is MISCELLANEOUS FOREIGN AWARDEES.

The pairs do distort any measure built on gross dollars, positive amounts or the largest transactions. The FY2013 pair alone is 5.4% of all gross dollars in the 18 years, which total $12.82 trillion.

#### The Emerson pair crosses a fiscal year

Army contract `W912QR08C0053`, awarded to Emerson Construction, records +$13,917,176,427.00 on 2008-09-29, in FY2008. It records -$13,901,924,427.00 on 2009-01-07, in FY2009. The award's recorded total dollars obligated is $16,293,527.48. Both rows sit in the cell for the Department of Defense and product code Y199, construction of miscellaneous buildings, and they break that cell in both years.

- **FY2008.** Emerson's net is $13.93 billion with the entry and $11.2 million without it. The cell's HHI is 4,281.8 with the entry and 167.2 without it. One vendor appears to hold most of a market that has 1,039 vendors.
- **FY2009.** Emerson's net is -$13.90 billion. The whole cell nets to -$4.52 billion, against $9.38 billion without the reversal. Shares of a negative total have no meaning, so HHI and the top-4 share cannot be computed for this cell as it stands.

The pair also shifts the year totals. FY2008 is recorded at $541.90 billion and FY2009 at $540.84 billion, a change of -0.20%. With the pair's net of $15.25 million moved to FY2008, the two years are $528.00 billion and $554.74 billion, a rise of 5.06%. The reversal is also the only reason January 2009 falls below half of its year's median month. No other month in 18 years does.

<!-- figure: monthly_net_v2 -->

**Proposed decision.** Move both rows of each pair to the exclusions ledger and carry their net forward as one documented adjustment. Keeping both rows keeps net totals right but leaves gross dollars and largest-transaction lists wrong. Excluding both rows outright removes real money, because each pair leaves something behind. The Emerson pair nets to +$15,252,000.00. The whole award nets to $16,293,527.48 across all years, which equals its recorded total dollars obligated. The other pairs leave +$208,870.87, -$358,227.00, +$556,622.00 and $0.00.

### Two $10 billion US Mint rows

Two rows in FY2010 record $10 billion each. Both are gold bullion contract vehicles awarded by the US Mint in May 2010. A contract vehicle is an umbrella agreement, and orders are placed under it. Here the orders carry their own obligations in our data, separate from the $10 billion rows. One reading is that each $10 billion is a ceiling recorded as an obligation. USAspending's award records show the following, and they stop short of saying what the $10 billion represents.

| | A-Mark Precious Metals, `TMHQ10C0040` | Coins 'N Things, `TMHQ10C0044` |
|---|---|---|
| Description | Mint MAC gold bullion, provide raw gold material | Basic ordering agreement to purchase newly mined US gold bullion bars |
| Total obligation on the vehicle record | $10,000,000,000 | $10,000,000,000 |
| Base and all options value | $10,000,000,000 | $15,000,000,000 |
| Later modifications | 6, all $0 | 7, all $0 |
| Orders placed under it (USAspending) | 1,438 delivery orders, $5,983,985,991.33 | 1,773 delivery orders, $11,876,614,896.49 |
| Orders in our data, FY2010 to FY2025 | 1,646 rows, $5,977,575,309.34 | 2,354 rows, $11,876,614,896.49 |
| Period of performance ends | 2030-12-30 | 2030-05-30 |

The Coins 'N Things vehicle's modification of 2022-07-18 reads "THE PURPOSE OF THIS MODIFICATION IS TO INCREASE THE CONTRACT CEILING DUE TO THE PRIOR CEILING BEING EXCEEDED."

The two rows add $20.00 billion to FY2010. Without them FY2010 is $541.22 billion, level with FY2009 as recorded.

**Proposed decision.** Keep both rows out of HHI until the USAspending lookup or another source confirms they are real obligations. The lookup shows a $10 billion obligation on each vehicle record and separate obligations on the orders placed under them. It does not confirm the $10 billion as spending.

### Negative vendor totals

A vendor's net in a cell turns negative when its deobligations outweigh its new obligations that year. That is normal accounting, since money obligated in one year is often returned in a later one. It still breaks the measure. A vendor with a negative total has no meaningful share.

The pattern is common. 588,645 of 7,847,575 vendor-cells (7.5%) have a negative net. They sit in 127,992 of 365,402 cells (35.0%) and net to -$124.05 billion, against $10.63 trillion in positive vendor-cell dollars. The share of negative vendor-cells rises from 3.7% in FY2008 to 9.9% in FY2025.

| FY | Cells | Vendor-cells | Negative vendor-cells | Their net | Cells with a negative vendor |
|---|---|---|---|---|---|
| 2008 | 20,040 | 570,767 | 21,281 (3.7%) | -$3.10B | 4,870 (24.3%) |
| 2009 | 20,792 | 515,425 | 24,269 (4.7%) | -$17.16B | 5,342 (25.7%) |
| 2010 | 21,136 | 520,209 | 29,737 (5.7%) | -$4.54B | 6,160 (29.1%) |
| 2011 | 21,115 | 511,475 | 34,102 (6.7%) | -$4.70B | 6,735 (31.9%) |
| 2012 | 23,206 | 490,775 | 38,528 (7.9%) | -$5.90B | 7,530 (32.4%) |
| 2013 | 22,377 | 455,640 | 38,494 (8.4%) | -$5.51B | 7,820 (34.9%) |
| 2014 | 22,008 | 452,234 | 35,415 (7.8%) | -$4.99B | 7,661 (34.8%) |
| 2015 | 21,756 | 463,952 | 34,385 (7.4%) | -$4.54B | 7,766 (35.7%) |
| 2016 | 21,117 | 456,489 | 34,577 (7.6%) | -$5.75B | 7,562 (35.8%) |
| 2017 | 21,524 | 466,231 | 35,866 (7.7%) | -$4.64B | 7,932 (36.9%) |
| 2018 | 20,227 | 418,656 | 33,562 (8.0%) | -$4.76B | 7,665 (37.9%) |
| 2019 | 19,043 | 378,746 | 32,387 (8.6%) | -$5.96B | 7,245 (38.0%) |
| 2020 | 18,432 | 368,725 | 33,642 (9.1%) | -$5.39B | 7,134 (38.7%) |
| 2021 | 19,483 | 365,600 | 33,561 (9.2%) | -$6.60B | 7,280 (37.4%) |
| 2022 | 19,041 | 357,808 | 30,487 (8.5%) | -$8.28B | 7,138 (37.5%) |
| 2023 | 18,659 | 351,470 | 31,204 (8.9%) | -$8.22B | 7,167 (38.4%) |
| 2024 | 18,243 | 370,791 | 34,225 (9.2%) | -$10.18B | 7,571 (41.5%) |
| 2025 | 17,203 | 332,582 | 32,923 (9.9%) | -$13.83B | 7,414 (43.1%) |

<!-- figure: negative_vendors_v2 -->

Nearly all of it traces to one kind of row. 582,703 of the negative vendor-cells (99.0%) contain at least one deobligation larger than the award's obligations that year. Removing those rows leaves 581,709 of them (98.8%) at zero or above. There are 2,407,492 such rows in all.

Two variants show how stable the count is. With the product code cut to its first 2 characters, the counts fall to 69,384 cells, 449,217 negative vendor-cells netting to -$99.93 billion, and 33,920 cells with a negative vendor. With the five reversal pairs removed as a diagnostic, one negative vendor-cell disappears, the Emerson reversal in FY2009, and the negative total shrinks by $13.90 billion to -$110.15 billion. The four pairs inside one year never create a negative vendor total.

**Proposed decision.** The options are to compute shares over vendors with a positive net only, to set negative vendor totals to zero, to move the deobligation rows behind them to the exclusions ledger, or to use a coarser product code. Andy proposes deciding after the team has seen these counts.

### MISCELLANEOUS FOREIGN AWARDEES

Agencies record many foreign companies under one placeholder name, MISCELLANEOUS FOREIGN AWARDEES. One vendor ID carries 974,811 of its 974,817 rows and $41.21 billion from FY2008 to FY2025, almost all from the Department of Defense. Scored as one company, it looks like a dominant vendor in thousands of markets. It holds more than 10% of the net dollars in 18,995 cells, with $28.48 billion of its net in those cells.

Its weight has fallen over time. It holds 0.39% of all net dollars, falling from 1.84% of net in FY2008 to 0.05% in FY2025. These are the 20 cells with the most of its dollars.

| FY | Agency | Product or service | Cell net | Its net | Share of cell |
|---|---|---|---|---|---|
| 2008 | Defense | 9999 miscellaneous items | $7,956.2M | $7,467.2M | 93.9% |
| 2009 | Defense | 9999 miscellaneous items | $1,712.6M | $1,198.2M | 70.0% |
| 2010 | Defense | 9999 miscellaneous items | $808.1M | $443.3M | 54.9% |
| 2013 | Defense | 9140 fuel oils | $1,963.6M | $420.8M | 21.4% |
| 2009 | Defense | Y222 construction of highways and bridges | $967.2M | $344.2M | 35.6% |
| 2010 | Defense | AD25 defense research, operational systems | $652.3M | $309.5M | 47.4% |
| 2019 | Defense | Y141 construction of hospitals | $253.6M | $248.2M | 97.9% |
| 2010 | Defense | V112 motor freight | $573.5M | $237.8M | 41.5% |
| 2011 | Defense | V112 motor freight | $531.6M | $231.0M | 43.4% |
| 2015 | Defense | Y141 construction of hospitals | $246.1M | $224.0M | 91.0% |
| 2011 | Defense | 9999 miscellaneous items | $364.6M | $200.8M | 55.1% |
| 2016 | Defense | Y1CA construction of schools | $488.5M | $196.1M | 40.1% |
| 2010 | Defense | Y222 construction of highways and bridges | $768.5M | $191.9M | 25.0% |
| 2021 | Defense | Y141 construction of hospitals | $182.9M | $182.9M | 100.0% |
| 2011 | Defense | AD25 defense research, operational systems | $509.1M | $182.0M | 35.7% |
| 2023 | Defense | Y141 construction of hospitals | $175.7M | $175.7M | 100.0% |
| 2010 | Peace Corps | 9999 miscellaneous items | $158.2M | $152.1M | 96.1% |
| 2012 | State | V003 packing and crating | $152.0M | $149.3M | 98.2% |
| 2009 | Defense | 8710 forage and feed | $137.1M | $129.0M | 94.1% |
| 2009 | Defense | AD25 defense research, operational systems | $444.4M | $127.2M | 28.6% |

**Proposed decision.** Report it separately, leave it out of HHI, and state the share of dollars left out. The other options are to score it as one vendor or to spread it across foreign vendors by some rule.

### Which company a row belongs to

The measure groups each row under its parent company, so the parent ID has to be right for the date of the action. That is harder than it sounds for the early years. UEIs replaced DUNS numbers only in 2022, and every UEI and parent UEI before then was filled in afterwards. The question is whether that backfill kept the parent recorded at the time of each action or carried today's parent back in time.

Corporate deals make a natural test. We took four deals, each with its closing date confirmed in an SEC filing, and the business units that changed hands in each. Then we counted those units' rows each month by the parent ID on the row. A correct backfill shows the old parent before the closing and the new one after it.

| Deal | Closed | Parent ID takes over | Lag | Rows with the new ID dated before the closing | Old ID after the switch | Confidence |
|---|---|---|---|---|---|---|
| SAIC splits into Leidos and a new SAIC | 2013-09-27 | March 2014 | 6 months | 5, all on 2013-09-26 | 2,385 of 89,559 rows (2.7%) | moderate |
| Lockheed Martin buys Sikorsky | 2015-11-06 | February 2016 | 3 months | 0 | 651 of 24,173 rows (2.7%) | high |
| L3 and Harris merge into L3Harris | 2019-06-29 | August 2019 | 2 months | 25, of which 20 are more than 30 days early | 102 of 5,544 rows (1.8%) | high |
| Raytheon Company into Raytheon Technologies | 2020-04-03 | June 2020 | 2 months | 2, the first on 2020-03-16 | 32 of 15,323 rows (0.2%) | high |

In all four deals the parent ID changes after the deal closes. Only 32 rows across the four tests carry the new ID before the closing date, and 25 of them are L3 rows. The backfill kept the parent recorded at the time of each action. It did not carry today's parent back in time.

The switch comes 2 to 6 months after each closing, and a small share of rows keeps the old ID for months after that. Confidence is high for 2015 to 2020, where the switch comes within 3 months and the old ID fades quickly. It is moderate for 2013, where the switch takes 6 months and 50 to 300 rows a month keep the old ID into 2015. FY2008 to FY2012 are untested. One detail links two of the tests. The Sikorsky units' parent before the deal is United Technologies, and that ID later became RTX's, so the Raytheon test reuses it as the new parent.

<!-- figure: parent_saic_v2 -->

<!-- figure: parent_sikorsky_v2 -->

<!-- figure: parent_l3harris_v2 -->

<!-- figure: parent_raytheon_v2 -->

The parent ID holds up better than the parent name. Neither name column is reliable. The derived name is today's name for the recorded ID, and the raw name lags behind mergers. Even the most common raw name per ID per year still lags, as these cases show.

- The Leidos ID shows "SAIC INC." as its most common raw name in FY2016 to FY2020, years after the 2013 rename.
- The RTX ID shows "RAYTHEON COMPANY" in FY2022.
- The L3Harris ID shows "L3 TECHNOLOGIES INC." in FY2020 and FY2022.

Display names should therefore be chosen per parent ID per year, ideally from a dated list of corporate names for the largest parents. This corrects earlier advice to display the raw name.

**Proposed decision.** Use the parent recorded at the time of the action, for the eras where the parent test supports it. The other option is to map every action to today's parent.

## What changes over time

The remaining findings do not distort a single cell. They change what the data can say across years, which matters for trends and for any measure built on counts.

### Row counts jump in FY2008, FY2015 and FY2019

Row counts are a poor measure of activity in this data. In three years they jump or drop by about a million rows with little change in dollars, and each step comes from small orders at one agency.

Small orders are tied to the micro-purchase threshold, the size below which simple purchases are allowed. The threshold changed during these years.

| Fiscal years | Threshold in the FAR | Notes |
|---|---|---|
| FY2008 to FY2015 | $3,000 | Effective 2006-09-28 |
| FY2016 to FY2019 | $3,500 | Effective 2015-10-01. The statute moved to $10,000 on 2017-12-12, and agencies could adopt it early by class deviation from 2018-02-16 |
| FY2020 | $3,500, then $10,000 | The FAR changed on 2020-08-31 |
| FY2021 to FY2025 | $10,000 | Raised to $15,000 on 2025-10-01, in FY2026 |

The Department of Defense had its own statutory threshold of $5,000 from 2016-12-23 and $10,000 from 2018-08-13. The appendix gives every citation.

**FY2015.** Rows rise by 1,846,777 (+73.0%) over FY2014 while net obligations fall 1.4%. Orders under $3,000, the threshold that year, rise from 168,688 to 1,961,639. Defense Logistics Agency rows rise from 600,140 to 2,486,703, and delivery orders from 1.23 million to 2.87 million. The agency reported 900,982 of its FY2015 rows more than 90 days after the action.

**FY2019.** Rows rise by 869,198 over FY2018. GSA's Federal Acquisition Service grows from 172,486 rows to 1,372,543, and the Defense Logistics Agency falls by 130,360. Orders under $3,000 rise by 1,073,616, and calls against blanket purchase agreements rise from 192,376 to 796,679. The Federal Acquisition Service reported 884,941 of its FY2019 rows more than 90 days late. The late rows in FY2019 (1,201,438) come from a different agency than the late rows in FY2015 (925,614).

**FY2008.** FY2008 has 1,008,038 more rows than FY2009. Department of Veterans Affairs rows fall from 1,295,822 in FY2008 to 232,062 in FY2009. Orders under $3,000 fall from 2,015,916 to 967,658, and purchase orders from 1,600,094 to 858,147.

The steps barely touch dollar shares. Rows under $3,000 rise from 6.7% of all rows in FY2014 to 44.8% in FY2015, while their share of net dollars moves from 0.04% to 0.26%. Vendor shares within a cell barely move, and HHI follows dollar shares. Counts of awards, actions or vendors do change, so any count-based measure shows a step with no change in spending behind it.

<!-- figure: small_rows_v2 -->

**Proposed decision.** Keep every row for dollar-based measures. For count-based measures, count only actions of $10,000 or more in every year, so changes to the small-purchase threshold cannot create steps. Actions of that size number 995,315 in FY2014, 997,217 in FY2015 and 1,026,773 in FY2016. Across all 18 years they stay between 956,532 and 1,219,805.

### The funding agency is a placeholder in the early years

Each row names an awarding agency, which signed the contract, and a funding agency, which paid for it. In FY2008 to FY2010 the funding agency is often the placeholder code 999, which carries a blank name on every row.

| FY | Rows | Share of rows | Net | Share of net |
|---|---|---|---|---|
| 2008 | 2,111,342 | 46.86% | $84.88B | 15.66% |
| 2009 | 1,128,360 | 32.26% | $90.89B | 16.81% |
| 2010 | 394,803 | 11.14% | $27.88B | 4.97% |
| 2011 | 4,828 | 0.14% | $0.47B | 0.09% |

Fewer than 200 rows a year carry the code from FY2012 on. It also drives most of the mismatches between codes and labels, 3,904,790 rows with 96% of them in FY2008 to FY2010.

**Proposed decision.** Use the awarding agency for the main analysis, and limit funding-agency checks to FY2011 onward. The other options are to label the code "unknown funding agency" or to leave FY2008 to FY2010 out of funding-agency analyses.

### Some fields fill in or empty out over time

Several fields change coverage across the 18 years. That matters most for variables used alongside concentration, such as competition.

- **Offers received.** It is 5% blank or less through FY2017 and 63% to 70% blank from FY2018, with 83% blank on orders under contract vehicles in FY2018.
- **Zero offers on a competed action.** It appears 265,297 to 279,578 times a year in FY2008 to FY2010, 64,905 times in FY2011 and 14,557 or fewer from FY2012. In the early years a zero seems to mean "not reported".
- **Recipient DUNS.** It is 21% blank in FY2020, 82% in FY2022 and 100% in FY2023 to FY2025, as the UEI replaced it.
- **Recipient UEI.** It is never blank, back to FY2008, though UEIs replaced DUNS only in 2022. The earlier UEIs were filled in afterwards. The same holds for the parent UEI.
- **NAICS and extent competed.** NAICS is 19.7% blank and extent competed 16.7% blank in FY2008. Both are under 2% blank from FY2011.

<!-- figure: coverage_v2 -->

**Proposed decision.** Use the extent-competed code as the main competition measure. It is under 2% blank from FY2011. Use the number of offers only within FY2011 to FY2017, where its coding is consistent. FY2011 still has 64,905 competed actions with zero offers, against 14,557 or fewer in each year from FY2012, so FY2012 to FY2017 is the cleaner window.

### Codes hold steady while labels drift

Agency and product codes are more reliable than their text labels. In FY2008 to FY2016, 278 to 910 codes a year carried more than one label within the year, against 8 to 83 a year from FY2017. Across years, 2,530 codes changed their label, against 2,537 in version 1. In 102 code-years two labels tie for most common, and ties now go to the first label alphabetically.

Agency codes are consistent even where they look odd. USAspending's API documentation says a top-tier agency code could be a CGAC or a FREC code, which have 3 and 4 characters. Eleven agencies use a 4-character code. Each uses the same code in every year and in both the awarding and the funding column. No agency appears under both a 3-character and a 4-character code, so no agency is split in two.

| Code | Agency | Rows as awarding agency | Net as awarding agency |
|---|---|---|---|
| `1601` | Department of Labor | 139,535 | $37.05B |
| `3300` | Smithsonian Institution | 63,863 | $6.53B |
| `1602` | Pension Benefit Guaranty Corporation | 20,754 | $5.57B |
| `1100` | Executive Office of the President | 14,450 | $1.16B |
| `1125` | Peace Corps | 11,525 | $2.03B |
| `3302` | National Gallery of Art | 10,057 | $0.78B |
| `9553` | Court Services and Offender Supervision Agency | 9,611 | $0.71B |
| `1133` | United States Trade and Development Agency | 3,961 | $0.31B |
| `3301` | John F. Kennedy Center for the Performing Arts | 1,712 | $0.18B |
| `3303` | Woodrow Wilson International Center for Scholars | 317 | $3.9M |
| `9566` | Federal Housing Finance Agency | 305 | $35.1M |

## Smaller findings

Three more patterns are worth knowing. None needs a decision beyond confirming a routine rule.

**Performance periods that start after they end.** 2,229,493 rows show a start date later than the current end date. They run at 140,000 to 274,000 rows a year through FY2019 and under 1,300 a year from FY2021. In FY2010 and FY2017, more than 99.98% of them are modifications, and 66% to 84% carry the modification's own date as the start. USAspending's release notes explain the drop. For actions dated on or after 2019-10-25, the start date now carries over from the base award to every modification.

**Reports filed before the action date.** 5,265,535 rows (5.9%) were first reported before their action date, with $3.01 trillion in gross dollars. The gaps are short, with a median of 3 to 4 days, a 90th percentile of 16 to 23 days and a 99th percentile of 96 to 118 days in FY2010 and FY2024. That pattern fits actions entered a few days before their effective date.

**Awards that span fiscal years.** 4,314,940 of 68,429,519 distinct awards have transactions in more than one fiscal year. Each transaction counts in the cell for its own fiscal year.

<!-- figure: flags_by_year_v2 -->

**Routine choices.** A documented rule settles each of these, and the team only needs to confirm it.

- Group by codes. Labels change within a year and across years.
- Keep rows on contract vehicles that carry dollars in every total, because the GAO match includes them. Reports also show them as a separate line. There are 183,497 such rows with $197.7 billion net.
- Treat reporting dates as information. Reports filed before the action date, or more than 90 days after it, are timing facts.
- Treat deobligations larger than an award's obligations in the same year as normal. Many return money obligated in an earlier year.

## Verify rather than trust

Anyone using this data should check these points before relying on a number.

1. **The largest amounts.** Check the reversal pairs against FPDS before using gross, positive-only or largest-transaction measures.
2. **The FY2008 and FY2009 totals.** Each is off by about $13.9 billion in opposite directions.
3. **The two US Mint rows.** The vehicle records carry $10 billion each, and the orders under them carry separate obligations.
4. **Row counts from FY2008, FY2015 and FY2019.** Small orders from one agency drive each step.
5. **Funding agency in FY2008 to FY2010.** The placeholder code covers up to 47% of rows and 17% of net dollars.
6. **Offers received.** Its coverage breaks in FY2018, and zero seems to mean "not reported" in FY2008 to FY2011.
7. **Recipient IDs.** UEIs before 2022 were filled in afterwards, and DUNS is empty from FY2023.
8. **Parent names.** Choose display names per parent ID per year from a dated reference.
9. **Performance start dates on modifications before FY2020.** They often carry the modification's own date.
10. **Labels.** Group by codes.
11. **GSA's figures.** Find out what GSA includes before treating its gap as a problem.
12. **Years with no published total.** FY2008 to FY2017 rest on internal checks alone.

## Appendix

### How it was checked, in detail

- **The copy.** For each of 97 CSV members, two independent readers agree on the record count, the exact dollar total and a checksum over every field of every row. The checksum adds up an MD5-based fingerprint of each row. All 18 years pass. The Parquet side was recomputed for every member on 2026-10-05, once the project had moved, and it still matches.
- **The rules.** 62 checks, each with a fixed rule and threshold, run on every row of every year. The catalog was committed before the first run. Each change made after seeing results is disclosed with its date and reason.
- **The analyses added in version 2.** Each rule was written into the code before the analysis ran, and this wording is quoted from it.
  - **Cell.** Awarding agency code as recorded (3 characters, or 4 for agencies identified by a FREC code), product or service code, and fiscal year. A blank product code is its own value.
  - **Vendor.** The parent UEI, or the recipient UEI where the parent is blank. Rows with both blank form one vendor.
  - **Negative vendor totals.** A vendor-cell is negative when its net is below zero. A negative vendor-cell counts as explained by deobligation rows when removing them leaves a net of zero or more.
  - **HHI for illustration.** 10,000 times the sum of squared shares, with shares taken over vendors with a positive net.
  - **Figure 1 diagnostic.** FY2008 without the Emerson entry and with the pair's net, FY2009 without the reversal, FY2010 without the two US Mint rows.
  - **Amount bands.** Negative, zero, under $3,000, $3,000 to under $3,500, $3,500 to under $10,000, $10,000 to under $250,000, $250,000 and over.
  - **Late reporting.** First report more than 90 days after the action date.
  - **MISCELLANEOUS FOREIGN AWARDEES cells.** Cells with a positive net where the name's share is above 10%.
  - **Dual agency codes.** An agency name that appears with a 3-character and a 4-character code in the same column pair across all years.
  - **Parent test.** The units that changed hands, by recipient name for Raytheon, Sikorsky and L3, and by the new SAIC parent ID for the spun-off SAIC units. The switch month is the first month in which rows with the new ID outnumber rows with the old ID.

### Flag codes

| Code | Plain name in this report |
|---|---|
| B05 | Awards that span fiscal years |
| C04 | Implausible potential end date |
| C06 | Performance periods that start after they end |
| C07 | Reported more than 90 days after the action |
| C08 | Reports filed before the action date |
| D04 | Rows on contract vehicles that carry dollars |
| E01 | Placeholder vendor, mainly MISCELLANEOUS FOREIGN AWARDEES |
| F05 | Agency codes with 4 characters |
| F07 | Codes with more than one label within a year |
| F08 | Codes whose label changes across years |
| F10 | Agency under both a 3- and a 4-character code |
| G03 | Code and label mismatches |
| H02 | Thin month by dollars |
| H03, H06 | Agency or sub-agency missing in a middle year |
| J01, J02 | Largest transactions, and transactions of $1 billion or more |
| J03 | Deobligation larger than the award's obligations that year |
| J04 | Amount far from its peers |
| X02 | Zero offers on a competed action |

### Files and commands

| What | Location |
|---|---|
| This report, and its PDF | `docs/integrity_findings_v3.md`, `reports/integrity/integrity_report_v3.pdf` |
| What changed from version 2 | `docs/integrity_findings_v3_changes.md` |
| Version 2, frozen | `docs/integrity_findings_v2.md`, `reports/integrity/integrity_report_v2.pdf` |
| Version 1, frozen | `docs/integrity_findings.md`, `reports/integrity/integrity_report.pdf` |
| The version 2 analyses and their rules | `src/analyses_v2.py`, tables in `reports/integrity/v2/` |
| Figures | `src/report_figures_v2.py` |
| Flag rules, thresholds and their changelog | `config/flag_catalog.csv` |
| Published totals, their changelog and saved copies | `config/benchmarks.csv`, `data/external/benchmarks/` |
| Completeness detail | `reports/integrity/completeness_check.md` and `.csv` |
| Every flag by year | `reports/integrity/flag_counts.csv` |
| Decision log | `config/decisions.csv` |
| SEC, FAR and USAspending lookups | `data/external/sec/`, `data/external/far/`, `data/external/usaspending_api/` |
| Writing-rule check | `tools/style_check.py` |

```bash
# the version 3 PDF
.venv/bin/python -m src.report_pdf --in docs/integrity_findings_v3.md \
    --out reports/integrity/integrity_report_v3.pdf
# the version 2 analyses that version 3 draws on (about 15 minutes)
caffeinate -i .venv/bin/python -m src.analyses_v2
# writing-rule check
.venv/bin/python tools/style_check.py docs/integrity_findings_v3.md
# dashboard at http://127.0.0.1:8765/
.venv/bin/python -m viewer.server
```

### Sources for dates and thresholds

- **SAIC.** Leidos Holdings, Form 8-K filed 2013-10-01, Item 2.01, accession `0001193125-13-387297`. "On September 27, 2013, the Company completed the previously announced separation from New SAIC."
- **Sikorsky.** Lockheed Martin, Form 8-K filed 2015-11-06, Item 2.01, accession `0001193125-15-369311`. "On November 6, 2015 ... Lockheed Martin completed the acquisition from Sellers ... of all of the issued and outstanding equity of Sikorsky Aircraft Corporation".
- **L3Harris.** L3Harris Technologies, Form 8-K filed 2019-07-01, Item 2.01, accession `0001140361-19-012139`. "on June 29, 2019, Harris and L3 completed their previously announced Merger."
- **Raytheon.** The closing date of 2020-04-03 comes from version 1 and was not checked against an SEC filing.
- **Micro-purchase threshold.**
  - FAC 2005-13, 71 FR 57363, 2006-09-28, effective 2006-09-28, $2,500 to $3,000.
  - FAC 2005-45, 75 FR 53129, 2010-08-30. "The micro-purchase base threshold of $3,000 (FAR 2.101) is not changed."
  - FAC 2005-83, 80 FR 38293, 2015-07-02, effective 2015-10-01. "The micro-purchase base threshold of $3,000 (FAR 2.101) is increased to $3,500."
  - `Pub. L. 114-328`, section 821, 2016-12-23, a $5,000 threshold for the Department of Defense.
  - `Pub. L. 115-91`, section 806, 2017-12-12, the statute to $10,000.
  - CAAC Letter 2018-02, 2018-02-16, class deviations allowed.
  - `Pub. L. 115-232`, section 821, 2018-08-13, $10,000 for the Department of Defense.
  - FAC 2020-07, 85 FR 40064, 2020-07-02, effective 2020-08-31, $3,500 to $10,000 in the FAR.
  - FAC 2025-06, 90 FR 41872, 2025-08-27, effective 2025-10-01, $10,000 to $15,000.
- **Agency codes.** USAspending API documentation, `usaspending_api/api_contracts/contracts/v2/agency/toptier_code.md` in the usaspending-api GitHub repository. The text is quoted from the review and was not fetched, because GitHub was outside the network rule for version 2.
- **Performance start dates.** USAspending release notes, November 04, 2019, Data and Download Notes, "Prime Contract Data", in the usaspending-website GitHub wiki (<https://github.com/fedspendingtransparency/usaspending-website/wiki>). "For awards with action_date on or after October 25, 2019, the period_of_performance_start_date will now propagate from the base award (modification_number = 0) instead of allowing each mod to have its own period_of_performance_start_date". Recorded as finding E39 in `config/gov_findings.csv`, with a saved copy in `data/external/gov_sources/`.

### Disclosures and rule changes

- **Version 3.** Version 3 reorganizes version 2 for readability. It adds no analysis and changes no number. The one new piece of content is the explanation for performance start dates, taken from USAspending's release notes. Versions 1 and 2 are frozen.
- **F05 severity.** Changed from review to info on 2026-10-05, after seeing the data. Version 1 rated it review, with 286,312 rows flagged. Version 2 rates it info, and the new dual-code check finds no agency under two codes.
- **F10 added.** The dual-code check was written after seeing the F05 results, so it is not part of the catalog committed before the first run.
- **C08 explanation.** Version 1's text read `A report cannot precede the action; points to a date entry error.` Version 2's text says most gaps are short and fit actions entered a few days before their effective date. The rule, threshold and severity are unchanged.
- **Benchmark status rule.** Version 1 took the worse of GAO and GSA for each year. Version 2 takes GAO wherever GAO has a figure and shows GSA as context. FY2024 and FY2025 change from WARN to PASS. Both statuses appear in the completeness table.
- **GAO statements for FY2018 to FY2021.** Version 1 left them out. Version 2 records them, with lower bounds checked one-sided and FY2021 compared as an approximate figure. The posts say "spent", and none gives an FPDS data date.
- **Benchmark wording.** "Independent" is now "independent extraction from the same source (FPDS)".
- **Parent test population.** The first run of the new tests counted any unit carrying either parent ID. That mixed in United Technologies and Harris units that never changed hands, because those parents' IDs carried over to RTX and L3Harris. The rule was changed to the units that changed hands, found by recipient name for Raytheon, Sikorsky and L3 and by the new SAIC parent ID for SAIC.
- **Label changes across years (F08).** The most common label per code per year was picked with no rule for ties, and 102 code-years have a tie. Version 1 counted 2,537 codes. A rebuild on 2026-10-05 counted 2,539 from the same data. Version 2 gives a tie to the first label alphabetically and counts 2,530 on every run. The definition is otherwise unchanged. This change is in the code and is recorded here, outside the catalog changelog.
- **Reversal pairs removed in the diagnostic.** The review asked for four pairs. The diagnostic removes five, the four inside one year and the Emerson pair, because the Emerson pair is the one that creates a negative vendor total.
- **Network lookups.** sec.gov refused direct downloads with HTTP 403. The 8-K text was read through a fetch service and confirmed with exact-phrase searches on EDGAR's full-text search. GAO's pages refused plain requests, and the posts were saved using a browser-style request. The US Mint lookup used api.usaspending.gov.
- **Earlier disclosures carried forward.** C04 was corrected before the first full run, and its threshold did not change. The full lists of the largest transactions and outliers are kept outside the committed reports.
