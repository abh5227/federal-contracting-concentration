# What the first look suggests for the project's story

*Author.* Shivram Nekkanti. *For.* Suchitra Hole and Andy Hannah. *Date.* 2026-10-12. *Branch.* `shivram-eda`.

The exploratory tables for all 18 years are built and checked (116 of 116 checks pass, `reports/eda/base_checks.csv`). Three results change how the project could tell its story. This note proposes a revised framing and asks the team for four decisions. Nothing in the proposal changes until the team agrees.

## The story in one line

Civilian agencies increasingly place their contract money with a few companies, and they mostly get there through open competition. The question then becomes how much the government consolidates its buying, where, and whether competition stays real after the award.

## The evidence

**1. Concentration in civilian contracting has grown.** Segments with HHI above 2,500 held 44.1% of civilian contract dollars in FY2008 and 50.5% in FY2025, while civilian contract spending doubled from $143B to $301B. The share moved between 38% and 44% until FY2014 and peaked at 53.3% in FY2022. The FY2024 dip to 42.8% comes mostly from one Department of Energy segment, contractors operating its buildings and sites, which fell below 2,500 that year. It accounts for $15.2B of the $19.4B drop. Source: `civilian_by_year.csv`, `civilian_drivers_fy2024.csv`.

**2. Veterans Affairs health care stands out.** Veterans Affairs is the largest civilian buyer ($78.3B in FY2025), and 75.6% of its dollars sat in highly concentrated segments, against 33.4% in FY2008. Its three largest concentrated segments put $44.0B with one company each. Source: `civilian_by_agency.csv`, `civilian_top_segments.csv`.

| VA segment, FY2025 | Dollars | Largest company and its share |
|---|---|---|
| Managed healthcare (Q201) | $22.8B | UnitedHealth Group, 98% |
| Drugs and biologicals (6505) | $11.7B | McKesson, 98% |
| Government health insurance programs (G007) | $9.5B | TriWest Healthcare Alliance, 100% |

Managed healthcare shows how fast a market can change. In FY2019 it held $389M across 167 companies, and the largest had 19%. In FY2025 it held $22.8B, and one company had 98%. Source: `example_segment.csv`.

**3. Concentrated civilian money was competed as often as the rest.** Across the 18 years, 84.5% of the dollars in concentrated segments were competed, against 85.2% in the other segments. The sole-source share of concentrated dollars fell from 18.6% in FY2008 to 9.8% in FY2025. Source: `civilian_competition_by_year.csv`, `civilian_competition_all_years.csv`.

| Civilian dollars | Concentrated segments | Other segments |
|---|---|---|
| Competed, FY2008 | 65.5% | 67.8% |
| Competed, FY2025 | 90.2% | 89.5% |
| Sole source, FY2025 | 9.8% | 10.3% |
| Competed, all 18 years | 84.5% | 85.2% |

The three VA segments were competed on 99.6% to 100% of their dollars, placed almost entirely through contract vehicles (99.6% to 100%) and at fixed prices (100%). NASA is the exception among large buyers: 36.8% of its concentrated FY2025 dollars were sole source, led by basic space research (54.5%). Source: `civilian_competition_top_segments.csv`, `civilian_competition_by_agency.csv`.

## The revised story

1. No public measure of contract concentration exists for the civilian agencies. Published studies cover Defense, which buys from a handful of prime contractors and studies its own market. We built a verified measure for every civilian agency, product and year.
2. Concentration grew, from 44% to 50% of civilian contract dollars, while spending doubled.
3. It sits in a few places, led by Veterans Affairs health care.
4. It mostly comes from competed awards. The common pattern looks like a deliberate choice: one competition, then one or two winners for the whole market. Economists call this competition for the market, as against competition in the market. HHI measures the result after the award and misses the competition before it.
5. The project's contribution is then the trade-off. Consolidation can bring scale, simpler administration and lower prices. It can also bring dependence on one supplier, fewer credible bidders when the contract is competed again, and savings that fade at renewal.

## What happens to the research questions

| Question in proposal version 10 | Status | Proposed |
|---|---|---|
| 1. Can USAspending records support a trustworthy score? | Answered. The copy is exact, totals match GAO within 0.2%, product codes carry across the 18 years, and the proposed decisions move under 1% of segments between bands. | Report as evidence, no longer a question |
| 2. What paths does concentration follow over time? | Open. Yearly noise is large: at a 500-point cutoff, 38% of trend lines rise and 28% still rise with their years shuffled (`rising_counts.csv`). | Keep, with a rising rule tested against shuffled lines |
| 3. What do markets that came to rely on a few vendors have in common, such as sole-source awards? | Sole-source share differs little between concentrated and other civilian dollars. | What sets markets that consolidated apart from the rest? |
| (new) 4 | | Does competition stay real when a consolidated market's contract is awarded again? |

Candidate features for questions 3 and 4, each to be checked against the 297 columns before use:

- Single-award against multiple-award vehicles (`multiple_or_single_award_idv_code`, `parent_award_single_or_multiple_code`).
- Offers received at award (`number_of_offers_received`), coded consistently only for FY2012 to FY2017.
- Incumbent persistence: whether the same company keeps the largest share year after year (`vendor_turnover.csv` gives a first version).
- Contract size and length.
- Sole-source share, kept as one path among several. NASA research is where it matters most.

## Caveats the story has to carry

1. **Prime contractors only.** For VA managed healthcare, the one company administers a network, and the money flows on to hospitals and doctors the data does not show.
2. **What "competed" means on an order.** The column guide says the competition field on an order describes its umbrella contract, and marks this as unconfirmed. The FPDS data dictionary should settle it before the story relies on it. Competition may also have happened years before the order.
3. **Description, no causes.** Consolidation by design is the most likely reading of the competed share. The data does not prove it.
4. **The comparison in point 3 uses concentration levels.** It compares no feature with rising lines, so the gate for phase 7b in the EDA plan still holds.

## Decisions for the team

1. **Scope.** Make the civilian agencies the focus, with Defense as the comparison, or keep every agency in the main analysis.
2. **Questions 3 and 4.** Adopt the revised wording, or keep version 10's.
3. **Features.** Agree the candidate list, and record it with the rising rule in `config/decisions.csv` before phase 7b runs.
4. **The competition field.** Who checks the FPDS data dictionary, and by when.

The deck for the class (`reports/eda/eda_presentation.pptx`) already follows points 1 to 3 of the revised story. Its slides on the competed share wait for decision 1.
