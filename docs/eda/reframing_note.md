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

## Why Veterans Affairs health care concentrated: the policy record

Added 2026-11-05, after the presentation. The trend test (`trend_yearly_tests.csv`) found that the civilian rise in concentration comes almost entirely from Veterans Affairs: without it, the civilian share is flat, 45.4% in FY2008 against 41.7% in FY2025. The record shows that the VA markets concentrated by policy design, through competed contracts. Each fact below was read on the source page. Two are confirmed a second time, as noted.

**Managed healthcare (Q201) followed the MISSION Act and the Community Care Network.**

- The VA MISSION Act was signed on 2018-06-06 (Pub. L. 115-182) "to establish a permanent community care program for veterans". The Veterans Community Care Program replaced the Veterans Choice Program on 2019-06-06. Sources: [govinfo.gov, Pub. L. 115-182](https://www.govinfo.gov/content/pkg/PLAW-115publ182/html/PLAW-115publ182.htm), [VA News, 2019-06-05](https://news.va.gov/press-room/va-announces-final-community-care-regulations-under-mission-act/).
- VA awarded Community Care Network contracts for Regions 1, 2 and 3 to Optum Public Sector Solutions, part of UnitedHealth Group, on December 28 (2018), Region 4 to TriWest on 2019-08-06, and Region 5 to TriWest on 2020-10-01. Sources: [VA News, Regions 1 to 3](https://news.va.gov/press-room/va-awards-community-care-network-contracts-to-increase-health-care-access/), [Region 4](https://news.va.gov/press-room/va-awards-contract-for-region-4-of-community-care-network/), [Region 5](https://news.va.gov/press-room/va-awards-contract-for-region-5-of-community-care-network-to-increase-veteran-access-to-health-care-in-alaska/).
- The award was competed. GAO's decision on TriWest's protest reads "The agency received proposals from three offerors, including TriWest and OPSS", describes "three fixed-price indefinite-delivery, indefinite-quantity (IDIQ) contracts", gives Regions 2 and 3 "a maximum ordering value of over $18 billion and $21.5 billion, respectively", and denies the protest. Confirmed a second time. Source: [GAO B-415222.3 et al., 2019-05-02](https://www.gao.gov/products/b-415222.3,b-415222.4,b-415222.6,b-415222.7).
- The regions were fully running between December 2019 (Region 1) and June 2021 (Region 5). Source: [GAO-23-105290](https://www.gao.gov/assets/gao-23-105290.pdf). Our data shows the same timing: VA managed healthcare held $0.39B in FY2019, $2.2B in FY2020 and $9.3B in FY2021 (`example_segment.csv`).
- GAO reports community care spending "from about $2.3 billion in fiscal year 2018 to $23.9 billion in fiscal year 2023", and finds gaps that "increase contract oversight risks". Source: [GAO-24-106390](https://www.gao.gov/assets/gao-24-106390.pdf).
- The money passes through the administrators to community providers. VA's inspector general describes how "the TPA seeks reimbursement from VHA for the same amount the TPA paid the community provider", and found that VHA "paid Optum approximately $783.4 million more and TriWest about $127.3 million more than the TPAs paid community dental providers". This confirms the second-layer caveat for this market. Source: [VA OIG 23-00748-28, 2025-02-20](https://www.vaoig.gov/sites/default/files/reports/2025-02/vaoig-23-00748-28.pdf).

**Two administrators ran the earlier programs.** VA awarded Patient-Centered Community Care contracts to Health Net Federal Services and TriWest in September 2013, and modified them in October 2014 to run the Veterans Choice Program under the Choice Act of 2014. Health Net's contract ended on 2018-09-30. Sources: [GAO-17-52](https://www.gao.gov/assets/gao-17-52.pdf), [GAO-18-671](https://www.gao.gov/assets/gao-18-671.pdf), [govinfo.gov, Pub. L. 113-146](https://www.govinfo.gov/content/pkg/PLAW-113publ146/html/PLAW-113publ146.htm).

**Drugs and biologicals (6505) is a single distributor by design.** The Pharmaceutical Prime Vendor program has one commercial distributor, and its use is mandatory for VA ordering activities. VA started the program in 1994 "to reduce the costs for storing and distributing pharmaceutical supplies". McKesson has held it since 2004, and the current contract runs from 2020-08-10 to 2028-08-09, awarded on the lowest-priced technically acceptable proposal. The contract is "for distribution services only": VA sets drug prices separately, through the Federal Supply Schedule. The 98% share in this segment therefore describes the distributor, while the drugs themselves come from many makers. VA's inspector general found that about 3% of $11.7B in VA drug purchases from April 2024 to March 2025 went outside the prime vendor contract. Sources: [VA National Contract Service](https://department.va.gov/procurement-acquisition-and-logistics/national-contract-service/?target=PharmPrimeVendor), [McKesson release, 2019-12-12](https://www.sec.gov/Archives/edgar/data/927653/000119312519312338/d837526dex991.htm), [VA OIG statement, 2012-06-06](https://www.vaoig.gov/sites/default/files/document/2023-08/VAOIG-statement-20120606-PPV.pdf), [VA OIG 25-02487-143](https://vaoig.gov/sites/default/files/reports/2026-06/vaoig-25-02487-143_-_final.pdf).

**Not confirmed.** The total Community Care Network ceilings appear only in trade press ($55.1B for Optum's three regions, a potential $26B for Region 4). The program behind government health insurance programs (G007, TriWest 100%) is unconfirmed, as are the value of the 2020 prime vendor award and the number of firms that bid for it.

**What this means for the story.** The two largest concentrated civilian markets are concentrated by design: a competed network administrator and a competed single distributor. Both are consolidations the project should describe as such, with their trade-offs: the oversight risks GAO and the inspector general report, and what happens when the contracts are competed again from 2026.

## The revised story

1. No public measure of contract concentration exists for the civilian agencies. Published studies cover Defense, which buys from a handful of prime contractors and studies its own market. We built a verified measure for every civilian agency, product and year.
2. Concentration grew, from 44% to 50% of civilian contract dollars, while spending doubled. The rise passes a test against chance (`trend_yearly_tests.csv`).
3. The rise comes from a few markets, led by Veterans Affairs health care. Without Veterans Affairs the civilian share is flat, and twelve segments make up half of all upward movement (`trend_decomposition_*.csv`). The two largest VA markets concentrated by policy design, through competed contracts.
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

## For discussion after the presentation: the second layer of money

The HHI describes the prime contracts, the contracts the government signs directly, and every one of them is in the data. For some markets the prime passes much of the money on. In VA managed healthcare, the prime companies administer networks, and community hospitals and doctors deliver the care. In construction, a general contractor wins the prime award and subcontracts much of the work. The score is right for the question "whom does the government contract with", and silent on "who does the work and gets the money in the end".

**Sources for the second layer.**

| Source | What it gives | Limits |
|---|---|---|
| Subaward data: USAspending custom download (Subawards), the API (`/api/v2/subawards/`), and the Sub-Awards tab on each award's page | First-tier subcontracts reported by the prime under FFATA | Generally $30,000 and over, self-reported by the prime, found incomplete by GAO more than once. Payments to providers in a health care network are probably claims payments and absent from subaward data. The current home of FFATA reporting (FSRS or SAM.gov) needs confirming. |
| FPDS (fpds.gov, ezSearch) | The official record of each contract action, including offers received and competition codes | The same records USAspending publishes, one action at a time |
| SAM.gov Contract Opportunities | Solicitations, award notices, and the justification for each sole-source award | Coverage varies by agency and year |
| GAO bid protest decisions | How many firms competed for a protested award, and why the winner was chosen | Only protested awards |
| Agency pages, inspector general reports, FOIA reading rooms | Program design, such as the VA Community Care Network contracts | Case by case |

**Proposal.** Keep the prime-contract HHI as the main measure, as proposal version 10 defines it. Add a subaward check for a few flagged markets, such as VA health care and the largest construction segments: recompute concentration one level down and report how complete the subaward data is. Read a handful of cases in FPDS and SAM.gov, such as how many offers the VA network contracts drew. The USAspending API refused connections from one team member's network on 2026-10-12, so a pull needs a single test request first.

## Decisions for the team

1. **Scope.** Make the civilian agencies the focus, with Defense as the comparison, or keep every agency in the main analysis.
2. **Questions 3 and 4.** Adopt the revised wording, or keep version 10's.
3. **Features.** Agree the candidate list, and record it with the rising rule in `config/decisions.csv` before phase 7b runs.
4. **The competition field.** Who checks the FPDS data dictionary, and by when.
5. **The second layer.** Whether to add the subaward check for flagged markets, which markets, and who pulls the data.

The deck for the class (`reports/eda/eda_presentation.pptx`) already follows points 1 to 3 of the revised story. Its slides on the competed share wait for decision 1.
