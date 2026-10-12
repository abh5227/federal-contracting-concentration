# Exploratory data analysis plan, FY2008 to FY2025

*Author.* Shivram Nekkanti. *Branch.* `shivram-eda`. *Status.* Draft for team review, 2026-10-12.

## Why this plan

The integrity review answered whether the data is complete and copied without loss. The proposal's milestones then move straight to the working set, the parent roll-up, product code handling and the concentration table (weeks 4 to 8). Several choices on that path are still open, and each one needs numbers the team has not yet seen over all 18 years. This plan produces those numbers.

The exploratory work has three jobs.

1. **Describe the data in the shape the analysis uses.** Segments, vendor totals within segments and trend lines, over all 18 years. The preliminary results cover only FY2024 and FY2025.
2. **Give evidence for the open decisions.** The nine main decisions (D0024 to D0032), the two added after the first review (D0033, D0034) and the ten open items in the methods notes, such as the 500-point cutoff and the thin-line rule.
3. **Check that the candidate features for question 3 are usable.** Coverage by year, distributions and overlap between features.

It does not cluster trend lines, fit the question 3 models or claim causes. Those stay with the milestones in the proposal.

## Ground rules

1. **Read only.** Stages 0, 1 and 2 never change. The exploratory code reads Layer A through each year's `_files.json`, never with a glob, and reads Stage 2 flags from `data/integrity/`.
2. **Thresholds are fixed before results.** The proposal fixes its thresholds before any result is seen. Looking at concentration alone, its levels, its noise and the number of lines, is allowed now, and the cutoff and thin-line rule depend on it. Comparing features with rising lines waits until the team has frozen the rules in `config/decisions.csv`, with a date. Phase 7 has this gate.
3. **Every number that depends on an open decision is computed under each option.** The base tables carry a marker column for each disputed group of rows, so an option is a filter and needs no rebuild.
4. **Committed outputs are summaries.** Tables and figures go in `reports/eda/`. Row-level tables stay in `data/eda/`, which git ignores with the rest of `data/`.
5. **Codes, never labels.** Agencies and products are grouped by code. Labels drift within and across years.
6. **Counts use actions of $10,000 or more**, as decision 3 proposes, with the all-rows count beside it. Dollar measures keep every row.
7. **Shares and HHI use recorded dollars.** Constant FY2025 dollars appear only on charts of totals, once the team picks the price index (methods notes, item 8).

## Setup on this machine

The project now runs on Windows. The data is on drive D: and nothing goes on C:.

| Step | Command or check | Done when |
|---|---|---|
| Raw zips in place | `.venv\Scripts\python -m src.stage0 organize --source D:\DATA\downloads\recovered` | All 18 zips pass and sit in `D:\DATA\raw\award_data_archive\release_2026-09-06\`. 13 are verified already, and FY2021 to FY2025 are downloading. |
| Stage 1 | `.venv\Scripts\python -m src.stage1 build` | 18 of 18 years PASS. About 1 hour 45 minutes. |
| Stage 2 | `.venv\Scripts\python -m src.stage2 all` | 18 years profiled. About 1 hour. |
| Same data as the team | Compare the new `reports/integrity/stage1_mirror_proof.csv` with the committed one | Records, exact dollars and fingerprints are identical for all 97 members. Any difference stops the work. |
| Committed files untouched | `git diff reports/ config/` | Only run times and paths differ. None of those changes is committed. |

Temporary files go to `D:\Temp`, and DuckDB writes anything over its 8 GB memory limit to `data/scratch/` on D:. The machine has 15.4 GB of memory, so browsers and other heavy programs should be closed during the long runs.

The code lives in `src/eda/`, one module per phase, run as `python -m src.eda.<module>` in the same style as `src/`. Each module states its rules in its docstring before it runs, as `src/analyses_v2.py` does.

## Phase 1. Base tables

Everything later reads three tables built once from Layer A. Building them once keeps each later question to seconds.

| Table | One row per | About | Columns |
|---|---|---|---|
| `data/eda/vendor_cells.parquet` | Fiscal year, awarding agency code, product code, vendor | 7.85 million rows | Net, gross, positive obligations, deobligations, rows, rows of $10,000 or more, and the dollar splits below |
| `data/eda/cells.parquet` | Fiscal year, awarding agency code, product code | 365,000 rows | Net, vendors, vendors with a positive net, HHI and top-4 share under each variant, largest vendor and its share |
| `data/eda/lines.parquet` | Awarding agency code, product code | To be counted | First and last year, years present, gaps, total net, era of each year |

The vendor key follows the proposal: the parent UEI on the row, or the recipient UEI where the parent is blank.

**Dollar splits in `vendor_cells`.** Each split is the net dollars on the rows in that group, so every feature in phase 7 is a sum over this table.

- Competition on the umbrella, from `extent_competed_code`, in four groups: competed (A, D, F, CDO), sole source (B, C, G, NDO), follow-on (E) and blank.
- Competition on the order, from `fair_opportunity_limited_sources_code`, in three groups: limited sources, open to every holder, and blank.
- Offers, from `number_of_offers_received`: competed with one offer, for FY2012 to FY2017.
- Pricing, from `type_of_contract_pricing_code`: fixed price, cost, time and materials or labor hours, other or blank.
- Set aside, from `type_of_set_aside_code`: any set-aside, none, blank.
- Through a vehicle: rows with a `parent_award_id_piid`, and rows without one.

**Marker splits**, one per disputed group of rows, from the Stage 2 flags and the integrity findings: the five reversal pairs, the two US Mint rows, deobligations larger than the award's obligations that year (J03), MISCELLANEOUS FOREIGN AWARDEES and rows with no vendor ID.

**Variants.** Each variant is a filter on the marker columns.

| Variant | Rule |
|---|---|
| V0, as recorded | Every row. Shares over vendors with a positive net, the rule of the preliminary results. |
| V1, as proposed | Reversal pairs replaced by their net, US Mint rows out, MISCELLANEOUS FOREIGN AWARDEES out, no-ID rows out, shares over vendors with a positive net. |
| V8a | V1, with negative vendor totals set to zero. |
| V8b | V1, without the J03 deobligation rows. |
| V8c | V1, with two-character product codes. |

**Checks.** The tables must add back exactly to Stage 1 for every year, in rows and in net dollars. They must also reproduce the integrity report's counts: 365,402 cells, 7,847,575 vendor-cells and 588,645 negative vendor-cells. FY2024 and FY2025 under V0 must reproduce `reports/proposal/concentration_prelim_by_year.csv`.

## Phase 2. The spending picture

1. Net dollars by year, by awarding agency (the 15 largest and the rest), for DoD against civilian agencies, and for products, services and research. Research codes start with A, product codes start with a digit and service codes start with any other letter.
2. How the money is spread over cells. The number of cells that hold 50%, 80% and 95% of each year's dollars, and the distribution of cell size on a log scale.
3. The share of dollars placed through contract vehicles, by year and by agency.
4. Charts mark the known issues in FY2008, FY2009 and FY2010, so a reader can tell a data issue from a change in spending.

## Phase 3. Concentration in all 18 years

This phase extends the preliminary table from 2 years to 18.

1. **By year.** Cells, scored cells and unscored cells (D0033) with their dollars. Median vendors, with and without a positive net. Single-vendor cells and their dollars. HHI and top-4 share quantiles, unweighted and weighted by dollars. Dollars in each band: below 1,500, 1,500 to 2,500, above 2,500, and above 1,800.
2. **By variant.** For V1, V8a, V8b and V8c against V0: cells whose band changes, and the dollars in them. This is the evidence for decision 8 and the proposal's data decisions check.
3. **By agency and by kind of purchase.** The location of concentration, for the 15 largest agencies and for products, services and research.
4. **What drives a change.** The cells that account for most of each year's change in dollars above 2,500, as the preliminary results did for FY2024 to FY2025.
5. **The floor set by few vendors.** HHI can be no lower than 10,000 divided by the number of vendors. Plot HHI against vendor count, so a high score from a cell with two vendors reads differently from a high score in a cell with 200.
6. **Face validity.** Score each year of a short list of known cases, such as Navy combat ships (1905) and DoD fixed-wing aircraft (1510), for the sponsor to check.

## Phase 4. Product code eras

Product codes changed meaning in FY2012 and FY2021, and the proposal keeps each trend line inside one era.

1. For each code, its first and last year. The codes that appear or disappear at each change, with their dollars.
2. The trend lines each change breaks, and their dollars.
3. Two-character groups across the changes. Whether group dollars stay level across each change, which tests the proposal's fallback.
4. The codes that need a crosswalk, ranked by dollars. This is the work list for the week 7 milestone.

**A problem to raise now.** The eras are FY2008 to FY2011 (4 years), FY2012 to FY2020 (9 years) and FY2021 to FY2025 (5 years). The rising rule needs at least 6 years, so its first 3 and last 3 years do not overlap. Inside one era, only FY2012 to FY2020 is long enough. Without a crosswalk, question 3 would rest on 9 of the 18 years. Phase 4 measures how much a crosswalk or the two-character groups recover, and the team should choose among these options before week 7.

- A crosswalk across both changes, for the codes that carry most of the dollars.
- Two-character groups for lines that cross a change.
- The rising rule within FY2012 to FY2020 only, with the other years descriptive.

## Phase 5. Trend lines and the rising rule

1. **The lines.** Their number in each era, years present, gaps inside a line and dollars.
2. **The thin-line rule** (methods notes, item 5). Lines and dollars kept on a grid of minimum years (6, 8, every year of the era) and minimum total dollars ($1 million, $10 million, $100 million). The team picks one point on the grid before any clustering run.
3. **Year-to-year noise.** The distribution of the change in HHI between consecutive years, by cell size, for single years and for 3-year pooled windows. The methods notes say this spread is the best guide for the 500-point cutoff.
4. **Rising and falling counts.** The share of kept lines that rise, and the share that fall, at 250, 500 and 1,000 points. A comparison with lines whose years are shuffled shows how many would pass by noise alone.
5. **Two traps to measure.** Lines that start very high or very low drift toward the middle by chance, so the counts are shown by starting level. Cells with few vendors swing more, so they are also shown by starting vendor count.

## Phase 6. A first look at shapes, with no clustering

1. Small multiples of the 50 largest kept lines, and of a random 50.
2. **Scaling** (methods notes, item 6). Examples of nearly flat lines that centering and scaling stretch into large swings, and a count of kept lines with a small spread. The same lines are shown as the change from their first year.
3. **Line length.** k-means compares lines of equal length. Count the kept lines by length, and list the ways to handle unequal lengths for the team.

## Phase 7. Candidate features for question 3

**7a. Coverage and distributions, allowed now.** For each candidate feature, by year: blank share, distribution over segments and dollars covered.

- Sole-source share, both ways: on the umbrella and on the order (methods notes, item 3). Confirm what `extent_competed_code` and `fair_opportunity_limited_sources_code` record for orders in the FPDS data dictionary before relying on either.
- The share coded E, follow-on to a competed action, counted both ways (item 2).
- Lines with a sole-source share below 0% or above 100% (item 4).
- Competed with a single offer, FY2012 to FY2017 only (D0028).
- Pricing mix, set-aside share, vehicle share, kind of purchase, starting vendor count and size.
- Correlations between features. The L1 regression can keep one of two overlapping features and drop the other somewhat arbitrarily, so the team should know which pairs overlap.

**7b. Features against rising, after the gate.** This part starts only after the cutoff, the thin-line rule, the era handling and the scaling choice are recorded in `config/decisions.csv` with a date. It then shows each feature's rising rate by quartile, from each line's first 3 years. It fits no model.

## Phase 8. Vendors

1. The 100 largest parents by dollars over 18 years, with the most common raw name for each parent ID in each year. This is the hand-check list for the week 6 milestone, and the integrity report shows why names must be chosen per ID per year.
2. Parents per year, and vendors entering and leaving each line, counting actions of $10,000 or more.
3. The cells each large parent leads, by year.
4. One table by year for MISCELLANEOUS FOREIGN AWARDEES and for rows with no vendor ID: rows, dollars and share of dollars (D0032, D0034).

## Outputs

| Output | What it holds |
|---|---|
| `src/eda/` | One module per phase |
| `reports/eda/*.csv` | Summary tables, with no row-level data |
| `reports/eda/figures/` | Figures, with the code that draws each one |
| `docs/eda/eda_findings.md` | The write-up: what each phase found and what it means for each decision |

## Which phase informs which decision

| Decision | Phase |
|---|---|
| D0024 reversal pairs, D0025 US Mint rows | 3 (band changes between V0 and V1) |
| D0026 the FY2015 step in counts | 2, 8 (counts with and without the $10,000 rule) |
| D0028 competition measure | 7a |
| D0029 parent roll-up | 8 |
| D0031 negative vendor totals | 3 (V8a, V8b and V8c) |
| D0032 MISCELLANEOUS FOREIGN AWARDEES, D0034 no-ID rows | 3, 8 |
| D0033 unscored segments | 3 |
| Product code eras, week 7 | 4 |
| Cutoff for rising (item 1) | 5 |
| Code E, umbrella and order fields, shares outside 0% to 100% (items 2, 3 and 4) | 7a |
| Thin-line rule (item 5) | 5 |
| Scaling (item 6) | 6 |

## Order and effort

Phases 1 to 6, 7a and 8 can run as soon as Stages 1 and 2 are built. Phase 7b waits for the gate.

| Order | Work | Effort |
|---|---|---|
| 1 | Setup: Stage 0 to 2 and the match with the team's proof | Half a day, mostly waiting |
| 2 | Phase 1, base tables and their checks | 1 to 2 days |
| 3 | Phases 2 and 3 | 2 days |
| 4 | Phase 4, with the era problem taken to the team | 1 day |
| 5 | Phases 5 and 6 | 2 days |
| 6 | Phases 7a and 8 | 2 days |
| 7 | Findings write-up and team review | 1 day |
| 8 | Phase 7b, after the gate | 1 day |

## Questions for the team

1. **The era problem in phase 4.** Should it go to the team before the rest of the work, since it changes the shape of question 3?
2. **Variant V1.** Is it the right reading of the proposed decisions, in particular replacing each reversal pair by its net?
3. **The face-validity list in phase 3.** Which cases should go to the sponsor?
4. **Who does what.** Phases 2 and 3, 4 to 6, and 7 and 8 split cleanly across three people, and all three read the same base tables.
