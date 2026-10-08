# Glossary of terms for the contract concentration project (version 3)

Find a term in the index by category or in the entries A to Z. Each entry gives a plain summary, why the term matters to our measure, where it shows up, an official definition where one exists, and a source to read more.

## Index by category

**Data systems and files (33).** Award Data Archive · CFO Act agencies · contract action report · custom award download · DAIMS · DATA Act · DATA Act Broker · data quality certification · Delta file · DoD 90-day delay · express report · federal account · FFATA · File A · File B · File C · File D1 · File D2 · File E · File F · fiscal year · FPDS · Full file · GTAS · Integrated Award Environment · object class · program activity · SAM.gov · Senior Accountable Official · Treasury Account Symbol · unlinked award · USAspending.gov · verification and validation

**Award structure (39).** action date · assisted acquisition · award · award type · BOA · BPA · BPA call · consortium management organization · contract action · contracting officer · definitive contract · delivery order · fair opportunity · Federal Supply Schedule · financial assistance · government purchase card · GWAC · IDIQ · IDV · interagency acquisition · management and operating contract · micro-purchase · micro-purchase threshold · modification · multi-agency contract · multiple award · option · other transaction agreement · period of performance · PIID · purchase order · referenced IDV · simplified acquisition threshold · sub-award · task order · termination for convenience · transaction · transaction key · unique award key

**Money (16).** appropriation · base and all options value · base and exercised options value · constant dollars · current total value of award · deobligation · Disaster Emergency Fund Code · federal action obligation · gross dollars · imprest fund · net dollars · nominal dollars · obligation · outlay · potential total value of award · total dollars obligated

**Identifiers (8).** CAGE code · DUNS · generic entity identifier · parent DUNS · parent UEI · recipient hash · UEI · ultimate parent

**Codes (9).** awarding agency · CGAC · contracting office · Federal Supply Class · FREC · funding agency · NAICS · PSC · subtier agency

**Competition and socioeconomic (17).** 8(a) · AbilityOne Program · commercial product or service · extent competed · full and open after exclusion of sources · full and open competition · HUBZone · national interest action code · not competed · number of offers received · other than full and open competition · SDVOSB · set-aside · small business concern · small business size standard · unusual and compelling urgency · WOSB

**Concentration (6).** effective number of firms · HHI · HHI thresholds (2010 guidelines) · HHI thresholds (2023 guidelines) · market definition · top-4 share

**Oversight and law (18).** CIGIE · classified contract · deviation · DFARS · eCFR · FAR · FAR Council · FAR subpart 4.6 · Federal Acquisition Circular · Federal Register · GAO · GSA · inspector general · lapse in appropriations · OMB · PGI · Revolutionary FAR Overhaul · SBA

**Our pipeline (38).** benchmark · benchmark bound · benchmark figure · cell · decision log · DuckDB · Emerson pair · exclusions ledger · flag · flag catalog · funding agency 999 · label drift · late-reported row · Layer A · Layer B · lineage columns · manifest · MD5 · MISCELLANEOUS FOREIGN AWARDEES · negative vendor total · parent test · Parquet · PASS/WARN/FAIL · placeholder vendor · release date · reversal pair · row fingerprint · row-count jump · SHA-256 · Stage 0 · Stage 1 · Stage 2 · Stage 3 · thin month · US Mint rows · vendor · vendor share · vendor-cell

## Entries A to Z

### Numbers and symbols

#### 8(a)

*Competition and socioeconomic.* Also called 8(a) Business Development Program, 8(a) program, c8a_program_participant. An SBA business development program for eligible small firms. Agencies can award contracts to these firms through SBA, sometimes without competition.

**Why it matters here.** 8(a) awards can be sole source, which can raise concentration in small cells.

**Shows up in.** `c8a_program_participant`, `type_of_set_aside_code`

> established a program that authorizes the Small Business Administration (SBA) to enter into all types of contracts with other agencies and award subcontracts for performing those contracts to firms eligible for program participation.

**Source.** FAR Council, acquisition.gov, "FAR Subpart 19.8 Contracting with the Small Business Administration (The 8(a) Program)", FAR 19.800(a). This is an official definition. Read more at [https://www.acquisition.gov/far/subpart-19.8](https://www.acquisition.gov/far/subpart-19.8).

**Related.** set-aside · SBA · small business concern · not competed.

### A

#### AbilityOne Program

*Competition and socioeconomic.* Also called AbilityOne. A federal program that buys certain supplies and services from nonprofit agencies that employ people who are blind or have severe disabilities. Purchases at its stores are not reported to FPDS.

**Why it matters here.** GSA already reports the stocked items, so the buying agencies' cells look smaller than their real demand.

**Shows up in.** `docs/research/government_documented_gaps_v3.md`

**Source.** FAR Council, acquisition.gov, "FAR 8.701 Definitions (AbilityOne Program)", FAR 8.701, definitions of central nonprofit agency and ordering office. The summary paraphrases an official source. Read more at [https://www.acquisition.gov/far/8.701](https://www.acquisition.gov/far/8.701).

**Related.** GSA · FAR subpart 4.6.

#### action date

*Award structure.* Also called action_date. The date the government signed the action. USAspending ties each obligation to this date.

**Why it matters here.** action_date sets each row's fiscal year, and flags C01 to C03 and C07 to C09 test it.

**Shows up in.** `action_date`, `action_date_fiscal_year`, `config/flag_catalog.csv`

> The date the action being reported (for prime award transactions or sub-awards) was issued or signed by the Government, or a binding agreement was reached.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, term 'Action Date'. This is an official definition. Read more at [https://www.usaspending.gov/?glossary=action-date](https://www.usaspending.gov/?glossary=action-date).

**Related.** fiscal year · late-reported row · transaction.

#### appropriation

*Money.* Also called appropriations. A law in which Congress approves money for a purpose. Agencies can obligate only money that has been appropriated.

**Why it matters here.** Contract actions use appropriated money, which is why non-appropriated fund buys can be left out of FPDS.

**Shows up in.** FAR 4.601, FAR 4.606

> The process by which Congress designates and approves spending for a specific purpose (e.g., a project or program).

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, term 'Appropriation'. This is an official definition. Read more at [https://www.usaspending.gov/?glossary=appropriation](https://www.usaspending.gov/?glossary=appropriation).

**Related.** obligation · lapse in appropriations · Treasury Account Symbol · contract action.

#### assisted acquisition

*Award structure.* Also called assisted buying. One agency awards and runs a contract for another agency that needs the work. The agency that does the buying is the awarding agency on the record.

**Why it matters here.** Dollars land in the cells of the agency that did the buying, so the agency that paid for the work looks smaller.

**Shows up in.** `awarding_agency_code`, `funding_agency_code`, `docs/research/government_documented_gaps_v3.md`

> Assisted acquisition means a type of interagency acquisition where a servicing agency performs acquisition activities on a requesting agency's behalf, such as awarding and administering a contract, task order, or delivery order.

**Source.** FAR Council (GSA, DoD, NASA), acquisition.gov, "FAR 2.101 Definitions", FAR 2.101(b), Assisted acquisition. This is an official definition. Read more at [https://www.acquisition.gov/far/2.101](https://www.acquisition.gov/far/2.101).

**Related.** interagency acquisition · awarding agency · funding agency.

#### award

*Award structure.* Also called prime award. A contract, order or agreement under which the government commits money to a recipient. One award usually has many rows, the original action plus its modifications.

**Why it matters here.** We group rows into awards with contract_award_unique_key. 4,314,940 of 68,429,519 distinct awards have rows in more than one fiscal year.

**Shows up in.** `contract_award_unique_key`, `docs/integrity_findings_v3.md`

> Money the federal government has promised to pay a recipient.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, term 'Award'. This is an official definition. Read more at [https://www.usaspending.gov/?glossary=award](https://www.usaspending.gov/?glossary=award).

**Related.** transaction · modification · unique award key · IDV.

#### Award Data Archive

*Data systems and files.* Also called archive, award data archive files. A USAspending download page with ready-made zip files of award transactions, one per fiscal year. New files come out each month. We use the All Agencies, Contracts, Full files from the 2026-09-06 release.

**Why it matters here.** It is our only data source. We hold 18 of its zips, FY2008 to FY2025, about 88.7 million rows.

**Shows up in.** `data/manifest.csv`, `docs/data_stages.md` (Stage 0), `docs/source_choice.md`, `README.md`

> Download major agencies’ award transaction data for full fiscal years.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "Award Data Archive download page", Award Data Archive page, introduction. This is an official definition. Read more at [https://www.usaspending.gov/download_center/award_data_archive](https://www.usaspending.gov/download_center/award_data_archive).

**Related.** Full file · Delta file · release date · USAspending.gov · custom award download.

#### award type

*Award structure.* Also called award_type_code. The kind of award on a row. Code A is a BPA call, B a purchase order, C a delivery order and D a definitive contract. IDV rows use idv_type_code instead.

**Why it matters here.** Award type explains the FY2008, FY2015 and FY2019 row-count jumps, which came from purchase orders, delivery orders and BPA calls.

**Shows up in.** `award_type_code`, `idv_type_code`, `docs/research/government_documented_gaps_v3.md`

> The type of award being entered by this transaction.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending data dictionary, API /api/v2/references/data_dictionary/", USAspending data dictionary, element ContractAwardType. This is an official definition. Read more at [https://www.usaspending.gov/data-dictionary](https://www.usaspending.gov/data-dictionary).

**Related.** BPA call · purchase order · delivery order · definitive contract · IDV.

#### awarding agency

*Codes.* Also called awarding_agency_code, awarding_agency_name. The agency that issued and manages the award.

**Why it matters here.** It is the agency part of our cell. We use it over the funding agency, which carries placeholder code 999 in FY2008 to FY2010.

**Shows up in.** `awarding_agency_code`, `awarding_agency_name`, `docs/integrity_findings_v3.md`

> The Awarding Agency is the agency that issues and administers the award.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, term 'Awarding Agency'. This is an official definition. Read more at [https://www.usaspending.gov/?glossary=awarding-agency](https://www.usaspending.gov/?glossary=awarding-agency).

**Related.** funding agency · subtier agency · CGAC · cell · funding agency 999.

### B

#### base and all options value

*Money.* Also called base_and_all_options_value, ceiling. The full agreed value of a contract if every option were used. For an IDV it also includes the estimated value of all orders.

**Why it matters here.** The Coins 'N Things vehicle records $15 billion here against the $10 billion obligated on its vehicle record.

**Shows up in.** `base_and_all_options_value`, `docs/integrity_findings_v3.md`

> For the Award it is the mutually agreed upon total contract value including all options (if any). For IDVs the value is the mutually agreed upon total contract value including all options (if any) AND the estimated value of all potential orders.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending data dictionary, API /api/v2/references/data_dictionary/", USAspending data dictionary, element BaseAndAllOptionsValue. This is an official definition. Read more at [https://www.usaspending.gov/data-dictionary](https://www.usaspending.gov/data-dictionary).

**Related.** option · potential total value of award · IDV · US Mint rows.

#### base and exercised options value

*Money.* Also called base_and_exercised_options_value. The value of a contract counting the base period and any options already exercised. On a modification it records the change in that value.

**Why it matters here.** It describes contract size. Our measure uses obligations instead.

**Shows up in.** `base_and_exercised_options_value`

> The contract value for the base contract and any options that have been exercised.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending data dictionary, API /api/v2/references/data_dictionary/", USAspending data dictionary, element BaseAndExercisedOptionsValue. This is an official definition. Read more at [https://www.usaspending.gov/data-dictionary](https://www.usaspending.gov/data-dictionary).

**Related.** option · base and all options value · current total value of award.

#### benchmark

*Our pipeline.* Also called published total, config/benchmarks.csv. A published government total, from GAO or GSA, that we compare with our own yearly total. Each one has a saved copy and a verified quote.

**Why it matters here.** A match shows we extracted and summed the data correctly. It cannot catch an error inside FPDS itself.

**Shows up in.** `config/benchmarks.csv`, `data/external/benchmarks/`, `docs/integrity_findings_v3.md`

**Source.** This is a project definition.

**Related.** benchmark figure · benchmark bound · PASS/WARN/FAIL · GAO · GSA.

#### benchmark bound

*Our pipeline.* Also called bound, lower bound. A benchmark stated as a floor, such as GAO's "more than $550 billion" for FY2018. It is checked one way only, so our total passes if it is above the floor. GAO's FY2021 figure is approximate and is treated separately.

**Why it matters here.** FY2018 to FY2020 rest on bounds, which say less than exact figures.

**Shows up in.** `config/benchmarks.csv` (benchmark_type bound and approximate), `docs/integrity_findings_v3.md`

**Source.** This is a project definition.

**Related.** benchmark · benchmark figure.

#### benchmark figure

*Our pipeline.* Also called figure, well-defined benchmark. A benchmark stated as an exact total, such as GAO's $793 billion for FY2025. GAO gives these for FY2022 to FY2025.

**Why it matters here.** Our totals are within 0.2% of GAO's figure in all four of those years.

**Shows up in.** `config/benchmarks.csv` (benchmark_type figure), `docs/integrity_findings_v3.md`

**Source.** This is a project definition.

**Related.** benchmark · benchmark bound.

#### BOA

*Award structure.* Also called basic ordering agreement. A written understanding with a vendor on terms and prices for future orders. A BOA is not itself a contract, and the orders under it are.

**Why it matters here.** One of the two $10 billion US Mint rows is a basic ordering agreement for gold bullion.

**Shows up in.** `idv_type_code` D, `docs/integrity_findings_v3.md`

> A Basic Ordering Agreement (BOA) is a type of Indefinite Delivery Vehicle (IDV). It is not a contract; it is a written understanding between government and contractor.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, term 'Basic Ordering Agreement (BOA)'. This is an official definition. Read more at [https://www.acquisition.gov/far/16.703](https://www.acquisition.gov/far/16.703).

**Related.** IDV · US Mint rows · delivery order.

#### BPA

*Award structure.* Also called blanket purchase agreement. A standing agreement with a vendor for repeat purchases, set up like a charge account. Each purchase under it is a BPA call.

**Why it matters here.** BPA calls drove much of the FY2019 row-count jump.

**Shows up in.** `idv_type_code` E, `award_type_code` A

> A blanket purchase agreement (BPA) is a simplified method of filling anticipated repetitive needs for supplies or services by establishing "charge accounts" with qualified sources of supply

**Source.** FAR Council, acquisition.gov, "FAR 13.303-1 Blanket purchase agreements, General", FAR 13.303-1(a). This is an official definition. Read more at [https://www.acquisition.gov/far/13.303-1](https://www.acquisition.gov/far/13.303-1).

**Related.** BPA call · IDV · Federal Supply Schedule.

#### BPA call

*Award structure.* Also called call, call order. A single order placed under a BPA. It is award type A in our data.

**Why it matters here.** BPA calls rose from 192,376 in FY2018 to 796,679 in FY2019, part of the FY2019 row-count jump.

**Shows up in.** `award_type_code` A, `docs/integrity_findings_v3.md`

> Enter this code for an award that is a call against a BPA.

**Source.** GSA (FPDS), "FPDS Data Dictionary V1.5 (J1 Data Element Dictionary)", FPDS Data Dictionary V1.5, element Award Type, value A, p. 146 (PDF p. 148). This is an official definition. Read more at [https://www.acquisition.gov/far/13.303-1](https://www.acquisition.gov/far/13.303-1).

**Related.** BPA · award type · row-count jump.

### C

#### CAGE code

*Identifiers.* Also called Commercial and Government Entity code, cage_code, NCAGE. A code that the Defense Logistics Agency assigns to a company location. One company can have many CAGE codes.

**Why it matters here.** cage_code marks a vendor location, so we do not use it to define vendors.

**Shows up in.** `cage_code`

> An identifier assigned to entities located in the United States or its outlying areas by the Defense Logistics Agency (DLA) Commercial and Government Entity (CAGE) Branch to identify a commercial or government entity by unique location

**Source.** FAR Council (GSA, DoD, NASA), acquisition.gov, "FAR 2.101 Definitions", FAR 2.101(b), definition of CAGE code, paragraph (1). This is an official definition. Read more at [https://www.acquisition.gov/far/subpart-4.18](https://www.acquisition.gov/far/subpart-4.18).

**Related.** UEI · SAM.gov.

#### cell

*Our pipeline.* Also called market cell, agency x PSC x fiscal year. One market in our measure, meaning one awarding agency code, one PSC and one fiscal year. A blank PSC counts as its own value.

**Why it matters here.** HHI and CR4 are computed once per cell. There are 365,402 cells across FY2008 to FY2025.

**Shows up in.** `docs/integrity_findings_v3.md`

**Source.** This is a project definition.

**Related.** vendor-cell · market definition · awarding agency · PSC · fiscal year.

#### CFO Act agencies

*Data systems and files.* Also called 24 CFO Act agencies, Chief Financial Officers Act agencies. The 24 large agencies listed in the Chief Financial Officers Act of 1990, such as Defense, Veterans Affairs and GSA. Many audits and OMB rules cover only these 24.

**Why it matters here.** Many government data-quality reviews test only these 24 agencies, so their findings say little about the smaller agencies in our data.

**Shows up in.** `config/benchmarks.csv` (GSA scope), `docs/research/government_documented_gaps_v3.md`

> The CFO Act, among other things, established Chief Financial Officer positions at major federal entities. The current list of 24 included entities is commonly referred to as the CFO Act agencies.

**Source.** GAO, "DATA Act: Quality of Data Submissions Has Improved but Further Action Is Needed to Disclose Known Data Limitations", p. 4 (PDF p. 10). This is an official definition. Read more at [https://www.govinfo.gov/content/pkg/USCODE-2023-title31/html/USCODE-2023-title31-subtitleI-chap9-sec901.htm](https://www.govinfo.gov/content/pkg/USCODE-2023-title31/html/USCODE-2023-title31-subtitleI-chap9-sec901.htm).

**Related.** Senior Accountable Official · data quality certification · GAO · inspector general.

#### CGAC

*Codes.* Also called CGAC agency code, toptier agency code. The 3-character agency code Treasury uses in account codes, such as 097 for Defense. Most awarding agency codes in our data are CGAC codes.

**Why it matters here.** It is the agency part of our cell. We keep it as text because most codes have a leading zero.

**Shows up in.** `awarding_agency_code`, `funding_agency_code`, `docs/integrity_findings_v3.md`

**Source.** Treasury (fedspendingtransparency/usaspending-api on GitHub), "API contract: Agency Overview /api/v2/agency/{toptier_code}/", API contract /api/v2/agency/{toptier_code}/, parameter toptier_code. The summary paraphrases an official source. Read more at [https://github.com/fedspendingtransparency/usaspending-api/blob/master/usaspending_api/api_contracts/contracts/v2/agency/toptier_code.md](https://github.com/fedspendingtransparency/usaspending-api/blob/master/usaspending_api/api_contracts/contracts/v2/agency/toptier_code.md).

**Related.** FREC · awarding agency · funding agency · Treasury Account Symbol.

#### CIGIE

*Oversight and law.* Also called Council of the Inspectors General on Integrity and Efficiency. The council of all federal inspectors general. It coordinates their work across agencies.

**Why it matters here.** CIGIE set the common guide and timing for the IG DATA Act audits, so their results follow one method (GAO-20-540).

**Shows up in.** `docs/research/government_documented_gaps_v3.md`

> The Council of the Inspectors General on Integrity and Efficiency (CIGIE) is an independent entity established within the executive branch to address integrity, economy and effectiveness issues that transcend individual Government agencies

**Source.** CIGIE (ignet.gov), "IGnet home page", IGnet home page, What is CIGIE. This is an official definition. Read more at [https://www.ignet.gov](https://www.ignet.gov).

**Related.** inspector general · GAO.

#### classified contract

*Oversight and law.* Also called classified acquisition. A contract whose work requires access to classified information. Contract actions whose reported data would be classified are kept out of FPDS.

**Why it matters here.** Classified buying is missing from every year of our data, with no marker in the rows.

**Shows up in.** `docs/research/government_documented_gaps_v3.md`

> Classified contract means any contract in which the contractor or its employees must have access to classified information during contract performance.

**Source.** FAR Council (GSA, DoD, NASA), acquisition.gov, "FAR 2.101 Definitions", FAR 2.101(b), Classified contract. This is an official definition. Read more at [https://www.acquisition.gov/far/2.101](https://www.acquisition.gov/far/2.101).

**Related.** FAR subpart 4.6 · contract action.

#### commercial product or service

*Competition and socioeconomic.* Also called commercial item, commercial_item_acquisition_procedures_code. Goods or services of a kind sold to the public, bought under the simpler rules in FAR Part 12.

**Why it matters here.** Cells of commercial buys may call for a different reading of concentration than cells of custom defense work.

**Shows up in.** `commercial_item_acquisition_procedures_code`

> A product, other than real property, that is of a type customarily used by the general public or by nongovernmental entities for purposes other than governmental purposes

**Source.** FAR Council (GSA, DoD, NASA), acquisition.gov, "FAR 2.101 Definitions", FAR 2.101(b), definition of commercial product, paragraph (1). This is an official definition. Read more at [https://www.acquisition.gov/far/2.101](https://www.acquisition.gov/far/2.101).

**Related.** FAR · PSC.

#### consortium management organization

*Award structure.* Also called CMO. A firm that manages a group of companies that win other transaction agreements together. FPDS often names the manager as the vendor, even though member firms do the work.

**Why it matters here.** A manager counted as the vendor makes a cell look more concentrated than it is.

**Shows up in.** `recipient_name`, `docs/research/government_documented_gaps_v3.md`

> The CMO is a single point of contact for the government, managing hundreds of consortium members and providing administrative services to both the government and vendors.

**Source.** GAO, "Other Transaction Agreements: DOD Can Improve Planning for Consortia Awards", PDF p. 17. This is an official definition. Read more at [https://www.gao.gov/assets/gao-22-105357.pdf](https://www.gao.gov/assets/gao-22-105357.pdf).

**Related.** other transaction agreement · vendor · top-4 share.

#### constant dollars

*Money.* Also called real dollars, inflation-adjusted dollars. Dollar amounts adjusted for inflation to the prices of one base year, so years compare fairly.

**Why it matters here.** HHI and CR4 use shares within one cell and year, so inflation cancels out. Dollar trends across FY2008 to FY2025 need constant dollars.

**Shows up in.** `config/benchmarks.csv` (dollars_basis)

> A dollar value adjusted to remove the effects of inflation by dividing the nominal value (also called the current dollar value) by the appropriate price index.

**Source.** GAO, "A Glossary of Terms Used in the Federal Budget Process", Budget Glossary, 'Real Dollar', p. 81 (PDF p. 85). This is an official definition. Read more at [https://www.gao.gov/assets/gao-05-734sp.pdf](https://www.gao.gov/assets/gao-05-734sp.pdf).

**Related.** nominal dollars · benchmark.

#### contract action

*Award structure.* Any action that buys, rents or leases goods, services or construction with appropriated money above the micro-purchase threshold, plus any change to such an action. Grants and other transaction agreements are not contract actions.

**Why it matters here.** FPDS must hold every contract action, so this definition marks the edge of our data.

**Shows up in.** `docs/research/government_documented_gaps_v3.md`

> Contract action means any oral or written action that results in the purchase, rent, or lease of supplies or equipment, services, or construction using appropriated dollars over the micro-purchase threshold

**Source.** FAR Council, acquisition.gov, "FAR Subpart 4.6 Contract Reporting", FAR 4.601, definition of contract action. This is an official definition. Read more at [https://www.acquisition.gov/far/subpart-4.6](https://www.acquisition.gov/far/subpart-4.6).

**Related.** contract action report · micro-purchase threshold · other transaction agreement · FPDS · appropriation.

#### contract action report

*Data systems and files.* Also called CAR. The FPDS record for one contract action. Each transaction row in our data comes from one CAR.

**Why it matters here.** Contracting officers must complete a CAR within three business days of award, so most rows are timely. DoD rows publish later.

**Shows up in.** `contract_transaction_unique_key`, `initial_report_date`

> contract action data required to be entered into the Federal Procurement Data System (FPDS).

**Source.** FAR Council, acquisition.gov, "FAR Subpart 4.6 Contract Reporting", FAR 4.601, definition of contract action report. This is an official definition. Read more at [https://www.acquisition.gov/far/subpart-4.6](https://www.acquisition.gov/far/subpart-4.6).

**Related.** contract action · FPDS · transaction · DoD 90-day delay.

#### contracting office

*Codes.* Also called awarding office, awarding_office_code. The specific office that awards and manages a contract.

**Why it matters here.** awarding_office_code is the finest level of buyer in our data. The cell stops at the agency level.

**Shows up in.** `awarding_office_code`, `awarding_office_name`

> Contracting office means an office that awards or executes a contract for supplies or services and performs postaward functions not assigned to a contract administration office

**Source.** FAR Council (GSA, DoD, NASA), acquisition.gov, "FAR 2.101 Definitions", FAR 2.101(b), definition of contracting office. This is an official definition. Read more at [https://www.acquisition.gov/far/2.101](https://www.acquisition.gov/far/2.101).

**Related.** subtier agency · awarding agency · contracting officer.

#### contracting officer

*Award structure.* Also called CO, KO. The government official with legal authority to sign, manage and end contracts. The contracting officer enters each contract action in FPDS.

**Why it matters here.** Field accuracy in our data rests on what contracting officers enter.

**Shows up in.** `docs/research/government_documented_gaps_v3.md`

> Contracting officer means a person with the authority to enter into, administer, and/or terminate contracts and make related determinations and findings.

**Source.** FAR Council (GSA, DoD, NASA), acquisition.gov, "FAR 2.101 Definitions", FAR 2.101(b), definition of contracting officer. This is an official definition. Read more at [https://www.acquisition.gov/far/2.101](https://www.acquisition.gov/far/2.101).

**Related.** contract action report · FPDS · contracting office.

#### current total value of award

*Money.* Also called current_total_value_of_award, current award amount. For a contract, the total obligated so far, including the base and exercised options.

**Why it matters here.** It is an award-level running total. Summing it across rows would double count.

**Shows up in.** `current_total_value_of_award`

> For procurement, the total amount obligated to date on a contract, including the base and exercised options.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending data dictionary, API /api/v2/references/data_dictionary/", USAspending data dictionary, element CurrentTotalValueOfAward. This is an official definition. Read more at [https://www.usaspending.gov/?glossary=current-award-amount](https://www.usaspending.gov/?glossary=current-award-amount).

**Related.** base and exercised options value · total dollars obligated.

#### custom award download

*Data systems and files.* Also called custom download, Contracts_PrimeTransactions. A USAspending download built on request for the dates and filters you choose. It holds the same 297 columns as the archive.

**Why it matters here.** Our one-quarter test found the archive complete against a custom download. 89% of matched rows were identical in every column.

**Shows up in.** `docs/source_choice.md`

> The Assistance_PrimeTransactions and Contracts_PrimeTransactions files are generated on demand based on selected specifications.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "Analyst's Guide to Federal Spending Data (PDF)", Analyst's Guide, How to access the data, p. 9 (PDF p. 9). This is an official definition. Read more at [https://www.usaspending.gov/download_center/custom_award_data](https://www.usaspending.gov/download_center/custom_award_data).

**Related.** Award Data Archive · release date.

### D

#### DAIMS

*Data systems and files.* Also called DATA Act Information Model Schema, GSDM, Governmentwide Spending Data Model. The rulebook for federal spending data. It lists each data element with its definition and format, plus the validation rules. Treasury renamed it GSDM.

**Why it matters here.** Many column definitions in our files follow this model, so it is the place to check what a field was meant to hold.

**Shows up in.** USAspending data dictionary

> The Governmentwide Spending Data Model (GSDM) is the authoritative source for the terms, definitions, formats, and structures for hundreds of distinct data elements that tell the story of how federal dollars are spent.

**Source.** Treasury, Bureau of the Fiscal Service, "Governmentwide Spending Data Model (GSDM), formerly DAIMS", GSDM page, opening paragraph. This is an official definition. Read more at [https://tfx.treasury.gov/data-transparency/gsdm](https://tfx.treasury.gov/data-transparency/gsdm).

**Related.** DATA Act · DATA Act Broker · USAspending.gov.

#### DATA Act

*Data systems and files.* Also called Digital Accountability and Transparency Act of 2014, Pub. L. 113-101. A 2014 law that expanded FFATA. It made OMB and Treasury set common data standards for spending data. It also made agencies link their accounting data to their awards.

**Why it matters here.** It created the quarterly reporting, SAO sign-offs and audits behind most government reviews of the data we use.

**Shows up in.** `docs/research/government_documented_gaps_v3.md`

> Expands FFATA by requiring the Office of Management and Budget (OMB) and the Department of the Treasury to develop government-wide data standards and data elements for agencies to use when reporting federal spending and requires agencies to link financial information (e.g., obligations) to the related federal awards.

**Source.** GAO, "Federal Spending Transparency: Opportunities Exist to Further Improve the Information Available on USAspending.gov", Table 1, Laws and Regulations with Relevant USAspending.gov Reporting Requirements (PDF p. 2, no printed page number). This is an official definition. Read more at [https://www.gao.gov/assets/gao-24-106214.pdf](https://www.gao.gov/assets/gao-24-106214.pdf).

**Related.** FFATA · DAIMS · DATA Act Broker · Senior Accountable Official · File C · USAspending.gov · OMB.

#### DATA Act Broker

*Data systems and files.* Also called Data Broker, Broker. Treasury's system that takes in agency submissions, runs validation checks and assembles the data shown on USAspending. It also pulls award data from government-wide systems such as FPDS.

**Why it matters here.** The Broker builds File D1 from FPDS, the data behind our archive files.

**Shows up in.** `docs/research/government_documented_gaps_v3.md`

> DATA Act Broker—a system that collects and validates agency data—which operationalizes the reporting framework laid out in the schema.

**Source.** GAO, "DATA Act: OMB, Treasury, and Agencies Need to Improve Completeness and Accuracy of Spending Data and Disclose Limitations", p. 7 (PDF p. 12). This is an official definition. Read more at [https://github.com/fedspendingtransparency/data-act-broker-backend](https://github.com/fedspendingtransparency/data-act-broker-backend).

**Related.** DATA Act · DAIMS · File D1 · Senior Accountable Official · USAspending.gov.

#### data quality certification

*Data systems and files.* Also called annual FPDS certification, SAO assurance. A formal sign-off that an agency's data is complete and accurate. For FPDS, each agency certifies its prior fiscal year's contract data to GSA within 120 days of year end. For the DATA Act, the SAO gives a quarterly assurance.

**Why it matters here.** A certification says the agency checked its data. It does not prove any single row in our files is right.

**Shows up in.** `docs/research/government_documented_gaps_v3.md`

> an annual certification of whether, and to what degree, agency CAR data for the preceding fiscal year is complete and accurate.

**Source.** FAR Council, acquisition.gov, "FAR Subpart 4.6 Contract Reporting", FAR 4.604(c). This is an official definition. Read more at [https://www.acquisition.gov/far/4.604](https://www.acquisition.gov/far/4.604).

**Related.** verification and validation · Senior Accountable Official · contract action report · FPDS · GSA.

#### decision log

*Our pipeline.* Also called config/decisions.csv. The file that records each team decision about a flag, column or value, with its status, rationale, who decided and when. The dashboard's Decision log page is the only thing that writes it.

**Why it matters here.** Stage 3 may change or leave out a row only by a rule in this log.

**Shows up in.** `config/decisions.csv`, `docs/data_stages.md` (Stage 3), `README.md`

**Source.** This is a project definition.

**Related.** Stage 3 · exclusions ledger · flag.

#### definitive contract

*Award structure.* In FPDS terms, any reported contract that is not an IDV. It is award type D in our data.

**Why it matters here.** Definitive contracts and purchase orders stand alone, so they should have no parent IDV (flag G02).

**Shows up in.** `award_type_code` D, `config/flag_catalog.csv` (G02)

> any contract that must be reported to FPDS other than an indefinite delivery vehicle

**Source.** FAR Council, acquisition.gov, "FAR Subpart 4.6 Contract Reporting", FAR 4.601, definition of definitive contract. This is an official definition. Read more at [https://www.acquisition.gov/far/subpart-4.6](https://www.acquisition.gov/far/subpart-4.6).

**Related.** IDV · purchase order · award type.

#### delivery order

*Award structure.* Also called DO. An order for goods placed under an existing contract. FPDS uses award type C for both delivery orders and task orders under an IDV.

**Why it matters here.** Delivery orders rose from 1.23 million in FY2014 to 2.87 million in FY2015, the core of the FY2015 row-count jump.

**Shows up in.** `award_type_code` C, `docs/integrity_findings_v3.md`

> Delivery order means an order for supplies placed against an established contract or with Government sources.

**Source.** FAR Council (GSA, DoD, NASA), acquisition.gov, "FAR 2.101 Definitions", FAR 2.101(b), definition of delivery order. This is an official definition. Read more at [https://www.acquisition.gov/far/2.101](https://www.acquisition.gov/far/2.101).

**Related.** task order · IDIQ · IDV · award type · row-count jump.

#### Delta file

*Data systems and files.* Also called Contracts_Delta, Delta archive file. An Award Data Archive file that holds only the rows added, changed or deleted since the previous month's files. A column marks each row as changed (C), deleted (D) or added (blank).

**Why it matters here.** We do not use Delta files, so nothing in our data is patched on top of a Full file.

> only new, modified, and deleted data since the date the last month's files were generated.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "Award Data Archive download page", Award Data Archive page, archive file types. This is an official definition. Read more at [https://www.usaspending.gov/download_center/award_data_archive](https://www.usaspending.gov/download_center/award_data_archive).

**Related.** Full file · Award Data Archive · release date.

#### deobligation

*Money.* Also called de-obligation, negative obligation. Money taken back from an award, recorded as a negative amount. Early terminations, unused funds and corrections all show up this way.

**Why it matters here.** Deobligations larger than an award's obligations that year sit in 99.0% of negative vendor-cells (582,703 of 588,645), so they are the main source of negative vendor totals.

**Shows up in.** `federal_action_obligation` < 0, `config/flag_catalog.csv` (J03), `docs/integrity_findings_v3.md`

> An agency’s cancellation or downward adjustment of previously incurred obligations.

**Source.** GAO, "A Glossary of Terms Used in the Federal Budget Process", Budget Glossary, 'Deobligation', p. 44 (PDF p. 48). This is an official definition. Read more at [https://www.usaspending.gov/?glossary=deobligation](https://www.usaspending.gov/?glossary=deobligation).

**Related.** obligation · negative vendor total · vendor-cell · reversal pair.

#### deviation

*Oversight and law.* Also called class deviation. Permission for an agency to depart from the FAR. A class deviation covers a whole group of contract actions, and agencies use them to adopt new rules early.

**Why it matters here.** Agencies adopted the $10,000 micro-purchase threshold and the 2025 FAR rewrite by class deviation on different dates, so a rule change reaches agencies at different times.

**Shows up in.** `docs/integrity_findings_v3.md`, `docs/research/government_documented_gaps_v3.md`

> Deviation means any one or combination of the following: (a) The issuance or use of a policy, procedure, solicitation provision (see definition in 2.101), contract clause (see definition in 2.101), method, or practice of conducting acquisition actions of any kind at any stage of the acquisition process that is inconsistent with the FAR.

**Source.** FAR Council, acquisition.gov, "FAR 1.401 Definition (deviation)", FAR 1.401(a). This is an official definition. Read more at [https://www.acquisition.gov/far/1.401](https://www.acquisition.gov/far/1.401).

**Related.** FAR · micro-purchase threshold · Revolutionary FAR Overhaul.

#### DFARS

*Oversight and law.* Also called Defense Federal Acquisition Regulation Supplement. The Defense Department's own additions to the FAR.

**Why it matters here.** DFARS rules shape how Defense, the largest buyer in our data, reports to FPDS.

**Shows up in.** `docs/research/government_documented_gaps_v3.md`

> DoD implementation and supplementation of the FAR is issued in the Defense Federal Acquisition Regulation Supplement (DFARS) under authorization and subject to the authority, direction, and control of the Secretary of Defense.

**Source.** DoD (Defense Acquisition Regulations System), acquisition.gov, "DFARS Part 201 Federal Acquisition Regulations System", DFARS 201.301(a)(1). This is an official definition. Read more at [https://www.acquisition.gov/dfars/part-201-federal-acquisition-regulations-system](https://www.acquisition.gov/dfars/part-201-federal-acquisition-regulations-system).

**Related.** FAR · DoD 90-day delay.

#### Disaster Emergency Fund Code

*Money.* Also called DEFC, disaster_emergency_fund_codes_for_overall_award. A code that tracks spending from disaster or emergency funding laws, such as COVID-19 relief or the infrastructure law.

**Why it matters here.** It flags awards paid partly with emergency money, which can explain a one-year spike in a cell.

**Shows up in.** `disaster_emergency_fund_codes_for_overall_award`

> Disaster Emergency Fund Code (DEFC) is used to track the spending of funding for disasters and emergencies such as COVID-19.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, term 'Disaster Emergency Fund Code (DEFC)'. This is an official definition. Read more at [https://www.usaspending.gov/?glossary=disaster-emergency-fund-code-defc](https://www.usaspending.gov/?glossary=disaster-emergency-fund-code-defc).

**Related.** national interest action code · appropriation · outlay.

#### DoD 90-day delay

*Data systems and files.* Also called 90-day reporting lag, DoD reporting delay. Contract data for the Department of Defense and the Army Corps of Engineers is published 90 days after the action. Other agencies' data reaches USAspending about two days after it enters FPDS.

**Why it matters here.** Recent months fill in late, so FY2026 stays incomplete until about January. That is one reason FY2026 is out of scope.

**Shows up in.** `docs/data_stages.md` (Stage 0), `config/flag_catalog.csv` (C07)

> Procurement data (such as for contracts and indefinite delivery vehicles (IDV)) for the Department of Defense (DOD) and U.S. Army Corps of Engineers (USACE) are published on a 90-day delay

**Source.** Treasury (USAspending.gov About the Data, usaspending-website on GitHub), "About the Data: Delay in DOD Procurement Data", USAspending About the Data, 'Delay in DOD Procurement Data'. This is an official definition. Read more at [https://www.usaspending.gov/data-sources](https://www.usaspending.gov/data-sources).

**Related.** late-reported row · FPDS · File D1.

#### DuckDB

*Our pipeline.* A database program that runs inside Python and reads Parquet files directly, using SQL, the standard language for database queries.

**Why it matters here.** It runs the Parquet side of the Stage 1 proof and all Stage 2 checks.

**Shows up in.** `docs/data_stages.md` (Stage 1), `src/stage1.py`, `src/stage2.py`

> DuckDB is a relational (table-oriented) DBMS that supports the Structured Query Language (SQL)

**Source.** DuckDB Foundation (duckdb.org), "Why DuckDB", DuckDB, Why DuckDB. This is an official definition. Read more at [https://duckdb.org/why_duckdb](https://duckdb.org/why_duckdb).

**Related.** Parquet · Stage 1 · Stage 2.

#### DUNS

*Identifiers.* Also called DUNS number, Data Universal Numbering System, recipient_duns. The 9-digit company ID from Dun & Bradstreet that the government used for vendors until April 2022.

**Why it matters here.** recipient_duns is 21% blank in FY2020, 82% in FY2022 and 100% in FY2023 to FY2025, so we group vendors by UEI.

**Shows up in.** `recipient_duns`, `recipient_parent_duns`, `config/flag_catalog.csv` (F04), `docs/integrity_findings_v3.md`

> It is a unique 9-digit identification number assigned to a company or organization by Dun & Bradstreet, Inc.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, term 'DUNS'. This is an official definition. Read more at [https://www.usaspending.gov/?glossary=duns](https://www.usaspending.gov/?glossary=duns).

**Related.** UEI · parent DUNS · SAM.gov.

### E

#### eCFR

*Oversight and law.* Also called Electronic Code of Federal Regulations. The online copy of all federal regulations, including the FAR, updated daily. Legal research should be checked against the official edition.

**Why it matters here.** It is the quickest way to read the FAR as of a past date when checking a threshold.

> The Electronic Code of Federal Regulations (eCFR) is a web version of the Code of Federal Regulations (CFR) that we update daily to better reflect its current status.

**Source.** National Archives, Office of the Federal Register (ecfr.gov), "eCFR Reader Aids: What is the eCFR", eCFR Reader Aids, What is the eCFR. This is an official definition. Read more at [https://www.ecfr.gov](https://www.ecfr.gov).

**Related.** Federal Register · FAR.

#### effective number of firms

*Concentration.* Also called numbers-equivalent, 1 divided by HHI. The number of equal-sized firms that would give the same HHI. With shares as fractions it is 1 divided by HHI, or 10,000 divided by HHI on the 0 to 10,000 scale. An HHI of 2,000 means about 5 equal firms.

**Why it matters here.** It turns HHI into a count that is easier to explain for each cell.

**Source.** DOJ and FTC, "Merger Guidelines", Merger Guidelines (2023), Guideline 1, footnote 13 (five equal firms give an HHI of 2,000). The summary paraphrases an official source. Read more at [https://www.justice.gov/atr/2023-merger-guidelines](https://www.justice.gov/atr/2023-merger-guidelines).

**Related.** HHI · top-4 share.

#### Emerson pair

*Our pipeline.* Also called W912QR08C0053. The one reversal pair that crosses fiscal years. Army contract W912QR08C0053 records +$13.92 billion on 2008-09-29 and -$13.90 billion on 2009-01-07.

**Why it matters here.** It makes Emerson hold most of a 1,039-vendor FY2008 cell (HHI 4,281.8 against 167.2 without it) and drives the FY2009 cell negative.

**Shows up in.** `docs/integrity_findings_v3.md`

**Source.** This is a project definition.

**Related.** reversal pair · total dollars obligated · negative vendor total · cell.

#### exclusions ledger

*Our pipeline.* Also called ledger, ledger rule. The planned record of every row left out of the working set, each with a reason code. Working set plus ledger must equal Stage 1, in rows and dollars, for every fiscal year.

**Why it matters here.** Nothing can quietly drop out of the concentration measure.

**Shows up in.** `docs/data_stages.md` (Stage 3 and the ledger rule)

**Source.** This is a project definition.

**Related.** Stage 3 · decision log · reversal pair.

#### express report

*Data systems and files.* Also called express reporting, consolidated report. One FPDS record that sums many contract actions, filed at least monthly. Its number of actions field holds the count.

**Why it matters here.** Row counts understate the real number of actions wherever express reports are used.

**Shows up in.** `number_of_actions`, `docs/research/government_documented_gaps_v3.md`

> Express reporting (consolidated reporting of multiple contract actions, to be submitted at least monthly).

**Source.** DoD (DFARS PGI, acquisition.gov), "DFARS Procedures, Guidance, and Information 204.6, Contract Reporting", DFARS PGI 204.606, express reporting. This is an official definition. Read more at [https://www.acquisition.gov/dfarspgi/pgi-204.6-contract-reporting](https://www.acquisition.gov/dfarspgi/pgi-204.6-contract-reporting).

**Related.** contract action report · FPDS · generic entity identifier.

#### extent competed

*Competition and socioeconomic.* Also called extent_competed_code. A code for how much competition an award had. A is full and open, B not available for competition, C not competed, D full and open after exclusion of sources, E follow-on to a competed action, F competed under simplified acquisition, G not competed under simplified acquisition.

**Why it matters here.** It is the proposed main competition measure. It is 16.7% blank in FY2008 and under 2% blank from FY2011.

**Shows up in.** `extent_competed_code`, `extent_competed`, `docs/integrity_findings_v3.md`

> A code that represents the competitive nature of the contract.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, term 'Extent Competed', official text. This is an official definition. Read more at [https://www.usaspending.gov/?glossary=extent-competed](https://www.usaspending.gov/?glossary=extent-competed).

**Related.** full and open competition · full and open after exclusion of sources · not competed · number of offers received · simplified acquisition threshold.

### F

#### fair opportunity

*Award structure.* Also called fair opportunity to be considered. The rule that each holder of a multiple-award contract gets a fair chance at each order above the micro-purchase threshold, unless a legal exception applies.

**Why it matters here.** fair_opportunity_limited_sources_code records which exception, if any, was used on an order.

**Shows up in.** `fair_opportunity_limited_sources_code`

> The contracting officer must provide each awardee a fair opportunity to be considered for each order exceeding the micro-purchase threshold issued under multiple delivery-order contracts or multiple task-order contracts

**Source.** FAR Council, acquisition.gov, "FAR Subpart 16.5 Indefinite-Delivery Contracts", FAR 16.505(b)(1)(i). This is an official definition. Read more at [https://www.acquisition.gov/far/subpart-16.5](https://www.acquisition.gov/far/subpart-16.5).

**Related.** multiple award · extent competed · micro-purchase threshold · contracting officer.

#### FAR

*Oversight and law.* Also called Federal Acquisition Regulation. The main rulebook for how federal agencies buy goods and services. Agencies add their own supplements, such as the DFARS for Defense.

**Why it matters here.** FAR rules set what must be reported to FPDS and the dollar thresholds behind our row-count steps.

**Shows up in.** `docs/integrity_findings_v3.md`

> The Federal Acquisition Regulations System consists of the Federal Acquisition Regulation (FAR), which is the primary document, and agency acquisition regulations that implement or supplement the FAR.

**Source.** FAR Council, acquisition.gov, "FAR 1.101 Purpose", FAR 1.101. This is an official definition. Read more at [https://www.acquisition.gov/far/1.101](https://www.acquisition.gov/far/1.101).

**Related.** DFARS · FAR subpart 4.6 · Federal Acquisition Circular · eCFR.

#### FAR Council

*Oversight and law.* Also called Federal Acquisition Regulatory Council, DAR Council, CAA Council. The group that writes and revises the FAR. It works through two councils, one for defense agencies and one for civilian agencies.

**Why it matters here.** Its rule changes, published in the Federal Register, set what agencies must report to FPDS in each year of our data.

**Shows up in.** `docs/research/government_documented_gaps_v3.md`

> Subject to the authorities discussed in 1.103, revisions to the FAR will be prepared and issued through the coordinated action of two councils, the Defense Acquisition Regulations Council (DAR Council) and the Civilian Agency Acquisition Council (CAA Council).

**Source.** FAR Council, acquisition.gov, "FAR 1.201-1 The two councils", FAR 1.201-1(a). This is an official definition. Read more at [https://www.acquisition.gov/far/1.201-1](https://www.acquisition.gov/far/1.201-1).

**Related.** FAR · Federal Acquisition Circular · Federal Register.

#### FAR subpart 4.6

*Oversight and law.* Also called FAR 4.6, Contract Reporting. The FAR rules on what agencies must, may and must not report to FPDS, and how fast. Section 4.606 lists what is left out, such as classified actions and most purchases at or below the micro-purchase threshold.

**Why it matters here.** It defines which federal buying can never appear in our data.

**Shows up in.** `docs/research/government_documented_gaps_v3.md`

> This subpart prescribes uniform reporting requirements for the Federal Procurement Data System (FPDS).

**Source.** FAR Council, acquisition.gov, "FAR Subpart 4.6 Contract Reporting", FAR 4.600. This is an official definition. Read more at [https://www.acquisition.gov/far/subpart-4.6](https://www.acquisition.gov/far/subpart-4.6).

**Related.** FPDS · FAR · contract action · micro-purchase threshold · government purchase card.

#### federal account

*Data systems and files.* Also called Federal Account Symbol. A group of Treasury accounts that share an agency code and an account number. USAspending uses it to group related accounts.

**Why it matters here.** federal_accounts_funding_this_award lists the federal accounts that paid for an award. We do not use it in the measure.

**Shows up in.** `federal_accounts_funding_this_award`

> On this website we group them by their agency identifier (3-digit code) and Main Account code (4-digit code).

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, term 'Federal Account'. This is an official definition. Read more at [https://www.usaspending.gov/?glossary=federal-account](https://www.usaspending.gov/?glossary=federal-account).

**Related.** Treasury Account Symbol · CGAC.

#### Federal Acquisition Circular

*Oversight and law.* Also called FAC. A numbered release of FAR changes, such as FAC 2020-07, which raised the micro-purchase threshold to $10,000.

**Why it matters here.** Our micro-purchase threshold dates cite FACs, such as FAC 2005-83 for the $3,500 threshold.

**Shows up in.** `docs/integrity_findings_v3.md`

> Federal Acquisition Circular (FAC) 2005-62, which amends the Federal Acquisition Regulation (FAR).

**Source.** FAR Council, acquisition.gov, "Federal Acquisition Circular 2005-62 notice", FAC 2005-62 notice, summary. This is an official definition. Read more at [https://www.acquisition.gov/reg-change-notice/fac2005-62](https://www.acquisition.gov/reg-change-notice/fac2005-62).

**Related.** FAR · Federal Register · micro-purchase threshold.

#### federal action obligation

*Money.* Also called federal_action_obligation, action obligation. The dollar amount on one transaction row. It is positive for new money and negative for money taken back.

**Why it matters here.** It is the only amount we sum. All 88.7 million rows net to $10.51 trillion.

**Shows up in.** `federal_action_obligation`, `docs/research/government_documented_gaps_v3.md`

> Amount of Federal Government’s obligation, de-obligation, or liability, in dollars, for an award transaction.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, term 'Federal Action Obligation', official text. This is an official definition. Read more at [https://www.usaspending.gov/?glossary=federal-action-obligation](https://www.usaspending.gov/?glossary=federal-action-obligation).

**Related.** obligation · deobligation · net dollars · gross dollars.

#### Federal Register

*Oversight and law.* Also called FR. The government's daily publication of new rules, proposed rules and notices. FAR changes are published there and cited by volume and page, such as 80 FR 38293.

**Why it matters here.** Our threshold dates come from Federal Register notices.

**Shows up in.** `docs/integrity_findings_v3.md`

> The Federal Register (the daily journal of the Federal government) is published every business day by the National Archives and Records Administration (NARA)'s Office of the Federal Register (OFR).

**Source.** National Archives, Office of the Federal Register, "About the Federal Register", NARA, About the Federal Register. This is an official definition. Read more at [https://www.federalregister.gov](https://www.federalregister.gov).

**Related.** eCFR · Federal Acquisition Circular · FAR.

#### Federal Supply Class

*Codes.* Also called FSC, Federal Supply Group, FSG. The 4-digit product classes, such as 1510 for fixed-wing aircraft, kept by the Defense Logistics Agency. Product PSCs are these classes, and the first two digits give the product group.

**Why it matters here.** Cutting the PSC to 2 characters groups products by these groups. That cuts negative vendor-cells from 588,645 to 449,217.

**Shows up in.** `product_or_service_code` (products)

**Source.** GSA, Federal Acquisition Service, "Product and Service Codes (PSC) Manual, Fiscal Year 2025 Edition", PSC Manual, revision chart (product codes follow the DLA class list) and Section D, Product Codes. The summary paraphrases an official source. Read more at [https://www.acquisition.gov/psc-manual](https://www.acquisition.gov/psc-manual).

**Related.** PSC · market definition.

#### Federal Supply Schedule

*Award structure.* Also called FSS, Multiple Award Schedule, MAS, GSA Schedule. GSA's program of long-term contracts with set prices that any agency can order from.

**Why it matters here.** Orders under schedules appear as delivery orders or BPA calls whose parent IDV has type C.

**Shows up in.** `idv_type_code` C, `parent_award_type_code`

> The Federal Supply Schedule program is also known as the GSA Schedules Program or the Multiple Award Schedule Program.

**Source.** FAR Council, acquisition.gov, "FAR 8.402 Federal Supply Schedules, General", FAR 8.402(a). This is an official definition. Read more at [https://www.acquisition.gov/far/8.402](https://www.acquisition.gov/far/8.402).

**Related.** IDV · GSA · BPA · multiple award.

#### FFATA

*Data systems and files.* Also called Federal Funding Accountability and Transparency Act of 2006, Pub. L. 109-282. A 2006 law that created USAspending.gov and requires agencies to publish data on federal awards. The DATA Act later expanded it.

**Why it matters here.** It is the legal basis for the public contract data we download.

**Shows up in.** `docs/research/government_documented_gaps_v3.md`

> Establishes USAspending.gov and requires agencies to publish data on federal awards equal to or greater than $25,000.

**Source.** GAO, "Federal Spending Transparency: Opportunities Exist to Further Improve the Information Available on USAspending.gov", Table 1, Laws and Regulations with Relevant USAspending.gov Reporting Requirements (PDF p. 2, no printed page number). This is an official definition. Read more at [https://www.gao.gov/assets/gao-24-106214.pdf](https://www.gao.gov/assets/gao-24-106214.pdf).

**Related.** DATA Act · USAspending.gov · File F.

#### File A

*Data systems and files.* Also called Appropriations Account file. The agency file of account balances for the fiscal year to date, by Treasury account. It comes from the agency's accounting system.

**Why it matters here.** Our contract rows come from File D1, so File A is context only.

> File A contains the FY cumulative appropriations account summary data.

**Source.** DoD Office of Inspector General, "Audit of DoD Compliance With the Digital Accountability and Transparency Act of 2014", Results in Brief, p. i (PDF p. 3). This is an official definition. Read more at [https://www.usaspending.gov/data-sources](https://www.usaspending.gov/data-sources).

**Related.** File B · File C · GTAS · Treasury Account Symbol · appropriation.

#### File B

*Data systems and files.* Also called Object Class and Program Activity file. The agency file that splits File A's account balances by object class and program activity.

**Why it matters here.** Our contract rows come from File D1, so File B is context only.

**Shows up in.** `object_classes_funding_this_award`, `program_activities_funding_this_award`

> File B contains the appropriation account data listed in File A but is further defined by object class code and program activity name.

**Source.** DoD Office of Inspector General, "Audit of DoD Compliance With the Digital Accountability and Transparency Act of 2014", Results in Brief, p. i (PDF p. 3). This is an official definition. Read more at [https://www.usaspending.gov/data-sources](https://www.usaspending.gov/data-sources).

**Related.** File A · File C · object class · program activity.

#### File C

*Data systems and files.* Also called Award Financial file, Account Breakdown by Award. The agency file that lists award-level spending from the agency's accounting system. It is the link between accounts and awards.

**Why it matters here.** The account columns in our files, such as treasury_accounts_funding_this_award, depend on this link. Awards with no link have those columns blank.

**Shows up in.** `treasury_accounts_funding_this_award`, `federal_accounts_funding_this_award`

> File C contains transaction-level financial data for all procurements and grants processed during the quarter.

**Source.** DoD Office of Inspector General, "Audit of DoD Compliance With the Digital Accountability and Transparency Act of 2014", Results in Brief, p. i (PDF p. 3). This is an official definition. Read more at [https://www.usaspending.gov/data-sources](https://www.usaspending.gov/data-sources).

**Related.** File A · File B · File D1 · unlinked award · Treasury Account Symbol.

#### File D1

*Data systems and files.* Also called Procurement file, Award and Awardee Attributes (Procurement). The DATA Act file of contract award data that the Broker builds from FPDS. It holds the transaction amount, dates, agency, vendor, PSC, NAICS and similar fields.

**Why it matters here.** Our contract files are built from File D1 data, so its coverage limits are our coverage limits.

**Shows up in.** all 297 columns of our files, `docs/research/government_documented_gaps_v3.md`

> File D1 contains procurement award and awardee data extracted from the Federal Procurement Data System-Next Generation.

**Source.** DoD Office of Inspector General, "Audit of DoD Compliance With the Digital Accountability and Transparency Act of 2014", Results in Brief, p. ii (PDF p. 4). This is an official definition. Read more at [https://www.usaspending.gov/data-sources](https://www.usaspending.gov/data-sources).

**Related.** FPDS · File C · File D2 · DATA Act Broker · DoD 90-day delay.

#### File D2

*Data systems and files.* Also called Financial assistance file. The DATA Act file of grants, loans and other financial assistance. It is the assistance counterpart of File D1.

**Why it matters here.** Out of scope. We use contracts only.

**Shows up in.** `docs/research/government_documented_gaps_v3.md`

> File D2 contains grant award and awardee data extracted from the Financial Assistance Broker Submission system on grant and other financial assistance awards.

**Source.** DoD Office of Inspector General, "Audit of DoD Compliance With the Digital Accountability and Transparency Act of 2014", Results in Brief, p. ii (PDF p. 4). This is an official definition. Read more at [https://www.usaspending.gov/data-sources](https://www.usaspending.gov/data-sources).

**Related.** File D1 · DATA Act Broker.

#### File E

*Data systems and files.* Also called Additional Awardee Data file, executive compensation file. The DATA Act file of extra recipient data taken from SAM.gov, such as the pay of a recipient's top five executives.

**Why it matters here.** Our files carry these executive pay columns, but we do not use them.

**Shows up in.** `highly_compensated_officer_1_name` to highly_compensated_officer_5_amount

> File E includes information extracted from System for Award Management on the award recipients.

**Source.** DoD Office of Inspector General, "Audit of DoD Compliance With the Digital Accountability and Transparency Act of 2014", Results in Brief, p. ii (PDF p. 4). This is an official definition. Read more at [https://www.usaspending.gov/data-sources](https://www.usaspending.gov/data-sources).

**Related.** SAM.gov · File F · DATA Act Broker.

#### File F

*Data systems and files.* Also called Sub-award Data file. The DATA Act file of subawards, the contracts or grants that a main award holder passes on to other firms. The main award holders report them.

**Why it matters here.** Out of scope. Our measure counts prime contract dollars only, so money passed to subcontractors stays with the prime vendor.

> File F contains information extracted from the FFATA Sub-award Reporting System on awards made to sub-recipients under a prime contract or grant award.

**Source.** DoD Office of Inspector General, "Audit of DoD Compliance With the Digital Accountability and Transparency Act of 2014", Results in Brief, p. ii (PDF p. 4). This is an official definition. Read more at [https://www.usaspending.gov/data-sources](https://www.usaspending.gov/data-sources).

**Related.** File E · FFATA · DATA Act Broker.

#### financial assistance

*Award structure.* Also called assistance award. Federal money given to support a public purpose, such as grants, loans and direct payments. It is reported apart from contracts and is outside our data.

**Why it matters here.** Several audits mix assistance awards with contracts, so their error rates do not describe contract rows alone.

**Shows up in.** File D2, `docs/research/government_documented_gaps_v3.md`

> A federal program, service, or activity that directly aids organizations, individuals, or state/local/tribal governments.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, Financial Assistance, plain text. This is an official definition. Read more at [https://www.usaspending.gov/](https://www.usaspending.gov/).

**Related.** File D2 · award · contract action.

#### fiscal year

*Data systems and files.* Also called FY. The federal budget year. It runs from October 1 to September 30 and is named for the year it ends, so FY2025 began on 2024-10-01.

**Why it matters here.** Every cell is one fiscal year, assigned from action_date.

**Shows up in.** `action_date_fiscal_year`, file names FY2008 to FY2025

> For the federal government, it runs from October 1 to September 30.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, term 'Fiscal Year (FY)'. This is an official definition. Read more at [https://www.usaspending.gov/?glossary=fiscal-year-fy](https://www.usaspending.gov/?glossary=fiscal-year-fy).

**Related.** action date · cell.

#### flag

*Our pipeline.* Also called row flag, integrity rule. A fact recorded about a row, year or code, such as a PSC that is not 4 characters. Each flag has a fixed rule and a severity of serious, review or info.

**Why it matters here.** Flags mark rows for team decisions without changing them.

**Shows up in.** `data/integrity/row_flags/fy{YYYY}.parquet`, `config/flag_catalog.csv`, `reports/integrity/flag_counts.csv`

**Source.** This is a project definition.

**Related.** flag catalog · Stage 2 · decision log.

#### flag catalog

*Our pipeline.* Also called config/flag_catalog.csv. The list of every integrity rule with its threshold and severity. It holds 62 flags, 61 committed before the first run plus F10, which was added later and disclosed.

**Why it matters here.** Fixing the rules before seeing the data keeps the checks from being tuned to the results.

**Shows up in.** `config/flag_catalog.csv`, `docs/data_stages.md` (Stage 2), `docs/integrity_findings_v3.md`

**Source.** This is a project definition.

**Related.** flag · Stage 2 · decision log.

#### FPDS

*Data systems and files.* Also called FPDS-NG, Federal Procurement Data System, Federal Procurement Data System-Next Generation. The government-wide database where contracting officers report each contract action. GSA manages it. USAspending copies its contract data from FPDS.

**Why it matters here.** Every row in our data began as an FPDS record, so any gap or error in FPDS is also in our data.

**Shows up in.** File D1, `data/manifest.csv`, `docs/integrity_findings_v3.md`, `docs/source_choice.md`

> The FPDS provides a comprehensive web-based tool for agencies to report contract actions

**Source.** FAR Council, acquisition.gov, "FAR Subpart 4.6 Contract Reporting", FAR 4.602(a). This is an official definition. Read more at [https://www.acquisition.gov/far/subpart-4.6](https://www.acquisition.gov/far/subpart-4.6).

**Related.** File D1 · contract action · contract action report · FAR subpart 4.6 · USAspending.gov · GSA · contracting officer.

#### FREC

*Codes.* Also called FREC agency code, 4-character agency code. A 4-character agency code that USAspending uses for some agencies in place of a 3-character CGAC code. Eleven agencies in our data use one, such as 1601 for Labor and 3300 for the Smithsonian.

**Why it matters here.** No agency appears under both a 3- and a 4-character code (flag F10), so no market is split in two.

**Shows up in.** `awarding_agency_code`, `funding_agency_code`, `config/flag_catalog.csv` (F05, F10), `docs/integrity_findings_v3.md`

> The toptier code of an agency (could be a CGAC or FREC) so only numeric character strings of length 3-4 are accepted.

**Source.** Treasury (fedspendingtransparency/usaspending-api on GitHub), "API contract: Agency Overview /api/v2/agency/{toptier_code}/", API contract /api/v2/agency/{toptier_code}/, parameter toptier_code. This is an official definition. Read more at [https://github.com/fedspendingtransparency/usaspending-api/blob/master/usaspending_api/api_contracts/contracts/v2/agency/toptier_code.md](https://github.com/fedspendingtransparency/usaspending-api/blob/master/usaspending_api/api_contracts/contracts/v2/agency/toptier_code.md).

**Related.** CGAC · awarding agency.

#### full and open after exclusion of sources

*Competition and socioeconomic.* Also called extent_competed_code D, full and open competition after exclusion of sources. Competition open to everyone in a defined group, with other sources left out on purpose. Small business set-asides are the usual case.

**Why it matters here.** Code D actions are competed, but only among a subset of firms, which caps how many vendors a cell can have.

**Shows up in.** `extent_competed_code` D, `type_of_set_aside_code`

> This subpart prescribes policies and procedures for providing for full and open competition after excluding one or more sources.

**Source.** FAR Council, acquisition.gov, "FAR Subpart 6.2 Full and Open Competition After Exclusion of Sources", FAR 6.200. This is an official definition. Read more at [https://www.acquisition.gov/far/subpart-6.2](https://www.acquisition.gov/far/subpart-6.2).

**Related.** set-aside · extent competed · full and open competition.

#### full and open competition

*Competition and socioeconomic.* Also called extent_competed_code A. Competition in which every capable, eligible firm may bid.

**Why it matters here.** Code A is the baseline for competitive markets in our data.

**Shows up in.** `extent_competed_code` A

> when used with respect to a contract action, means that all responsible sources are permitted to compete.

**Source.** FAR Council (GSA, DoD, NASA), acquisition.gov, "FAR 2.101 Definitions", FAR 2.101(b), definition of full and open competition. This is an official definition. Read more at [https://www.acquisition.gov/far/2.101](https://www.acquisition.gov/far/2.101).

**Related.** extent competed · full and open after exclusion of sources · other than full and open competition.

#### Full file

*Data systems and files.* Also called Contracts_Full, Full archive file. An Award Data Archive file that holds every transaction for one fiscal year as of the day the file was built.

**Why it matters here.** We load Full files only, so each fiscal year in our data is one complete snapshot.

**Shows up in.** `FY2008_All_Contracts_Full_20260906.zip` to FY2025_All_Contracts_Full_20260906.zip, `data/manifest.csv` (archive_type)

> data for the fiscal year up until the date the file was prepared

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "Award Data Archive download page", Award Data Archive page, archive file types. This is an official definition. Read more at [https://www.usaspending.gov/download_center/award_data_archive](https://www.usaspending.gov/download_center/award_data_archive).

**Related.** Delta file · Award Data Archive · release date.

#### funding agency

*Codes.* Also called funding_agency_code, program or funding agency. The agency that paid most of the money for an award. It is often the same as the awarding agency.

**Why it matters here.** Funding agency code 999 covers 46.86% of FY2008 rows, so funding-agency analysis is reliable only from FY2011.

**Shows up in.** `funding_agency_code`, `funding_agency_name`, `docs/integrity_findings_v3.md`

> Name and 3-digit CGAC agency code of the department or establishment of the Government that provided the preponderance of the funds for an award and/or individual transactions related to an award.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, term 'Funding Agency', official text. This is an official definition. Read more at [https://www.usaspending.gov/?glossary=funding-agency](https://www.usaspending.gov/?glossary=funding-agency).

**Related.** awarding agency · funding agency 999 · CGAC.

#### funding agency 999

*Our pipeline.* Also called funding_agency_code 999. A placeholder funding agency code with a blank name. It covers 46.86% of FY2008 rows, 32.26% in FY2009, 11.14% in FY2010 and fewer than 200 rows a year from FY2012.

**Why it matters here.** It makes funding-agency analysis unreliable before FY2011, so the main measure uses the awarding agency.

**Shows up in.** `funding_agency_code`, `docs/integrity_findings_v3.md`, `config/decisions.csv` (D0027)

**Source.** This is a project definition.

**Related.** funding agency · awarding agency.

### G

#### GAO

*Oversight and law.* Also called Government Accountability Office. The independent, nonpartisan audit agency that works for Congress.

**Why it matters here.** GAO's yearly contract totals are our primary benchmark for FY2018 to FY2025, and its audits are the main record of known data problems.

**Shows up in.** `config/benchmarks.csv`, `docs/integrity_findings_v3.md`

> GAO, often called the "congressional watchdog,” is an independent, non-partisan agency that works for Congress.

**Source.** GAO, "About GAO", GAO, About page. This is an official definition. Read more at [https://www.gao.gov/about](https://www.gao.gov/about).

**Related.** benchmark · inspector general · CIGIE.

#### generic entity identifier

*Identifiers.* Also called generic vendor ID. One ID that stands for a whole category of vendors instead of one firm. The FAR allows it for some small awards and for some vendors outside the United States.

**Why it matters here.** Placeholder vendors such as MISCELLANEOUS FOREIGN AWARDEES work like this, so one vendor ID can cover many firms.

**Shows up in.** `recipient_uei`, `recipient_name`, `config/flag_catalog.csv` (E01, E02)

> Generic entity identifier means a number or other identifier assigned to a category of vendors and not specific to any individual or entity.

**Source.** FAR Council, acquisition.gov, "FAR Subpart 4.6 Contract Reporting", FAR 4.601, definition, uses listed in FAR 4.605(c)(2). This is an official definition. Read more at [https://www.acquisition.gov/far/subpart-4.6](https://www.acquisition.gov/far/subpart-4.6).

**Related.** MISCELLANEOUS FOREIGN AWARDEES · placeholder vendor · UEI.

#### government purchase card

*Award structure.* Also called purchase card, Governmentwide commercial purchase card, GPC. A government credit card that staff use to buy and pay for small purchases.

**Why it matters here.** Card buys below the micro-purchase threshold are generally not reported to FPDS (FAR 4.606(c)(1)), so most card spending is outside our data.

**Shows up in.** FAR 4.606

> Governmentwide commercial purchase card means a purchase card, similar in nature to a commercial credit card, issued to authorized agency personnel to use to acquire and to pay for supplies and services.

**Source.** FAR Council, acquisition.gov, "FAR 13.001 Definitions (Governmentwide commercial purchase card)", FAR 13.001. This is an official definition. Read more at [https://www.acquisition.gov/far/13.001](https://www.acquisition.gov/far/13.001).

**Related.** micro-purchase · micro-purchase threshold · FAR subpart 4.6.

#### gross dollars

*Money.* Also called gross, absolute dollars. The sum of the absolute values of the amounts, so a +$5 entry and a -$5 reversal count as $10.

**Why it matters here.** Reversal pairs distort gross totals badly. The FY2013 pair alone is 5.4% of the $12.82 trillion gross over 18 years.

**Shows up in.** `docs/integrity_findings_v3.md`

**Source.** This is a project definition.

**Related.** net dollars · reversal pair.

#### GSA

*Oversight and law.* Also called General Services Administration. The agency that runs government-wide buying programs such as the Federal Supply Schedules. Its Integrated Award Environment office manages FPDS.

**Why it matters here.** GSA runs the system our data comes from, and its yearly FPDS totals are our context benchmark.

**Shows up in.** `config/benchmarks.csv` (GSA rows)

**Source.** GAO, "Federal Contracting: procurement data quality reports (GAO-25-107469)", GAO-25-107469, p. 26 (PDF p. 31), on GSA's Integrated Award Environment program office managing FPDS. The summary paraphrases an official source. Read more at [https://www.gsa.gov](https://www.gsa.gov).

**Related.** FPDS · SAM.gov · Federal Supply Schedule · benchmark.

#### GTAS

*Data systems and files.* Also called Governmentwide Treasury Account Symbol Adjusted Trial Balance System. Treasury's system where agencies report their account balances and their spending against their budgets. Agency File A is checked against it.

**Why it matters here.** It ties agency books to spending reports. It does not hold our contract rows.

> Entities, including agencies, use GTAS to provide proprietary financial reporting information and information about budget execution to the Department of the Treasury.

**Source.** Treasury, Bureau of the Fiscal Service, "Governmentwide Treasury Account Symbol Adjusted Trial Balance System (GTAS)", GTAS page, opening paragraph. This is an official definition. Read more at [https://fiscal.treasury.gov/gtas/](https://fiscal.treasury.gov/gtas/).

**Related.** File A · Treasury Account Symbol · DATA Act.

#### GWAC

*Award structure.* Also called governmentwide acquisition contract, government-wide acquisition contract. An IDV for information technology that one agency sets up for every agency to use.

**Why it matters here.** Each order under a GWAC carries its own awarding agency, so GWAC spending spreads across many agencies' cells.

**Shows up in.** `idv_type_code` A, `parent_award_type_code`

> a task-order or delivery-order contract for information technology established by one agency for Governmentwide use

**Source.** FAR Council (GSA, DoD, NASA), acquisition.gov, "FAR 2.101 Definitions", FAR 2.101(b), definition of Governmentwide acquisition contract. This is an official definition. Read more at [https://www.acquisition.gov/far/2.101](https://www.acquisition.gov/far/2.101).

**Related.** IDV · multi-agency contract · task order · delivery order.

### H

#### HHI

*Concentration.* Also called Herfindahl-Hirschman Index. A score from near 0 to 10,000 for how concentrated a market is. Square each firm's percentage share and add the squares. One firm with everything scores 10,000.

**Why it matters here.** It is the project's main measure, computed per cell from vendors' net dollars.

**Shows up in.** `docs/integrity_findings_v3.md`

> The HHI is calculated by squaring the market share of each firm competing in the market and then summing the resulting numbers.

**Source.** DOJ Antitrust Division, "Herfindahl-Hirschman Index", DOJ Antitrust Division, Herfindahl-Hirschman Index page. This is an official definition. Read more at [https://www.justice.gov/atr/herfindahl-hirschman-index](https://www.justice.gov/atr/herfindahl-hirschman-index).

**Related.** top-4 share · effective number of firms · HHI thresholds (2023 guidelines) · HHI thresholds (2010 guidelines) · market definition · vendor-cell.

#### HHI thresholds (2010 guidelines)

*Concentration.* Also called 2010 Horizontal Merger Guidelines thresholds. Under the 2010 guidelines, HHI below 1,500 was unconcentrated, 1,500 to 2,500 moderately concentrated and above 2,500 highly concentrated. A rise of more than 200 points in a highly concentrated market was presumed harmful.

**Why it matters here.** Results for FY2008 to FY2023 may be read against these older bands, which are looser than the 2023 ones.

**Shows up in.** `docs/proposal/proposal_v9.md`

> Mergers resulting in highly concentrated markets that involve an increase in the HHI of more than 200 points will be presumed to be likely to enhance market power.

**Source.** DOJ and FTC, "Horizontal Merger Guidelines", Horizontal Merger Guidelines (2010), Section 5.3, p. 19 (PDF p. 22). This is an official definition. Read more at [https://www.justice.gov/atr/horizontal-merger-guidelines-08192010](https://www.justice.gov/atr/horizontal-merger-guidelines-08192010).

**Related.** HHI · HHI thresholds (2023 guidelines).

#### HHI thresholds (2023 guidelines)

*Concentration.* Also called 2023 Merger Guidelines thresholds. Under the 2023 Merger Guidelines of the Department of Justice and the Federal Trade Commission, a market with HHI above 1,800 is highly concentrated, and a rise of more than 100 points is significant.

**Why it matters here.** Comparing cell HHIs with 1,800 gives a familiar yardstick, though the guidelines were written for mergers.

**Shows up in.** `docs/proposal/proposal_v9.md`

> Markets with an HHI greater than 1,800 are highly concentrated, and a change of more than 100 points is a significant increase.

**Source.** DOJ and FTC, "Merger Guidelines", Merger Guidelines (2023), Guideline 1, p. 5 (PDF p. 6). This is an official definition. Read more at [https://www.justice.gov/atr/2023-merger-guidelines](https://www.justice.gov/atr/2023-merger-guidelines).

**Related.** HHI · HHI thresholds (2010 guidelines).

#### HUBZone

*Competition and socioeconomic.* Also called historically underutilized business zone. An SBA program for small firms based in economically distressed areas, called HUBZones. SBA certifies these firms.

**Why it matters here.** HUBZone set-asides limit who can bid, which can shape concentration in a cell.

**Shows up in.** `type_of_set_aside_code`

> HUBZone means a historically underutilized business zone that is an area located within one or more qualified census tracts, qualified nonmetropolitan counties, lands within the external boundaries of an Indian reservation, qualified base closure areas, redesignated areas, governor-designated covered areas, or qualified disaster areas

**Source.** FAR Council (GSA, DoD, NASA), acquisition.gov, "FAR 2.101 Definitions", FAR 2.101(b), definition of HUBZone. This is an official definition. Read more at [https://www.acquisition.gov/far/2.101](https://www.acquisition.gov/far/2.101).

**Related.** set-aside · SBA · small business concern.

### I

#### IDIQ

*Award structure.* Also called indefinite-delivery, indefinite-quantity contract, indefinite-quantity contract, IDC. A contract that sets a minimum and maximum amount over a period. The agency buys the actual work through orders.

**Why it matters here.** Order rows in our data link to their IDIQ contract or other IDV through parent_award_id_piid.

**Shows up in.** `idv_type_code` B, `parent_award_type_code`

> An indefinite-quantity contract provides for an indefinite quantity, within stated limits, of supplies or services during a fixed period. The Government places orders for individual requirements.

**Source.** FAR Council, acquisition.gov, "FAR Subpart 16.5 Indefinite-Delivery Contracts", FAR 16.504(a). This is an official definition. Read more at [https://www.acquisition.gov/far/subpart-16.5](https://www.acquisition.gov/far/subpart-16.5).

**Related.** IDV · delivery order · task order · multiple award.

#### IDV

*Award structure.* Also called indefinite delivery vehicle, contract vehicle, umbrella agreement. An umbrella contract or agreement under which agencies later place orders. Types include GWACs, IDIQ contracts, Federal Supply Schedules, BOAs and BPAs. IDV rows usually carry no dollars, and the orders under them do.

**Why it matters here.** IDV rows that carry dollars (flag D04) number 183,497 with $197.7 billion net. We keep them in totals because the GAO match includes them.

**Shows up in.** `award_or_idv_flag`, `idv_type_code`, `contract_award_unique_key` (CONT_IDV_), `docs/integrity_findings_v3.md`

> Indefinite Delivery Vehicles (IDVs) are vehicles that facilitate the delivery of supply and service orders.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "Analyst's Guide to Federal Spending Data (PDF)", Analyst's Guide, p. 7 (PDF p. 7). This is an official definition. Read more at [https://www.acquisition.gov/far/subpart-4.6](https://www.acquisition.gov/far/subpart-4.6).

**Related.** IDIQ · GWAC · Federal Supply Schedule · BPA · BOA · referenced IDV · US Mint rows.

#### imprest fund

*Money.* A small cash fund an agency keeps for minor purchases paid in cash. Purchases from it below the micro-purchase threshold are not reported to FPDS.

**Why it matters here.** This spending is outside our data by rule.

**Shows up in.** `docs/research/government_documented_gaps_v3.md`

> Imprest fund means a cash fund of a fixed amount established by an advance of funds, without charge to an appropriation, from an agency finance or disbursing officer to a duly appointed cashier, for disbursement as needed from time to time in making payment in cash for relatively small amounts.

**Source.** FAR Council, acquisition.gov, "FAR 13.001 Definitions (Governmentwide commercial purchase card)", FAR 13.001, Imprest fund. This is an official definition. Read more at [https://www.acquisition.gov/far/13.001](https://www.acquisition.gov/far/13.001).

**Related.** micro-purchase · government purchase card · FAR subpart 4.6.

#### inspector general

*Oversight and law.* Also called IG, OIG, Office of Inspector General. An independent office inside an agency that audits and investigates that agency. IGs have audited their agencies' DATA Act data.

**Why it matters here.** IG audits give error rates for agency contract data, the closest thing to a field-by-field accuracy check.

**Shows up in.** `docs/research/government_documented_gaps_v3.md`

> established agency inspectors general to provide policy direction for and to conduct, supervise, and coordinate audits and investigations relating to agency programs and operations.

**Source.** GAO, "A Glossary of Terms Used in the Federal Budget Process", Budget Glossary, Appendix I, p. 113 (PDF p. 117). This is an official definition. Read more at [https://www.ignet.gov](https://www.ignet.gov).

**Related.** CIGIE · GAO · DATA Act.

#### Integrated Award Environment

*Data systems and files.* Also called IAE. The family of GSA systems for federal award data, including SAM.gov and FPDS. GSA paused its modernization in September 2023 for lack of funds.

**Why it matters here.** Fixes to FPDS fields such as the product code are unlikely while the systems are frozen.

**Shows up in.** `docs/research/government_documented_gaps_v3.md`

> FPDS is part of the Integrated Award Environment (IAE), a suite of systems administered by the General Services Administration (GSA) that tracks federal award data.

**Source.** GAO, "Federal Contracting: procurement data quality reports (GAO-25-107469)", PDF p. 2. This is an official definition. Read more at [https://www.gao.gov/assets/gao-25-107469.pdf](https://www.gao.gov/assets/gao-25-107469.pdf).

**Related.** FPDS · SAM.gov · GSA.

#### interagency acquisition

*Award structure.* Any purchase where one agency gets goods or services through another agency, either by having it award the contract or by ordering from its contract.

**Why it matters here.** These purchases can put one agency's demand in another agency's cells.

**Shows up in.** `awarding_agency_code`, `funding_agency_code`

> Interagency acquisition means a procedure by which an agency needing supplies or services (the requesting agency) obtains them from another agency (the servicing agency), by an assisted acquisition or a direct acquisition.

**Source.** FAR Council (GSA, DoD, NASA), acquisition.gov, "FAR 2.101 Definitions", FAR 2.101(b), Interagency acquisition. This is an official definition. Read more at [https://www.acquisition.gov/far/2.101](https://www.acquisition.gov/far/2.101).

**Related.** assisted acquisition · multi-agency contract · GWAC.

### L

#### label drift

*Our pipeline.* Also called code and label drift, flags F07 and F08. A code whose text label changes within a year or across years, such as an agency renamed.

**Why it matters here.** Grouping by codes avoids splitting one agency or PSC into several groups.

**Shows up in.** `config/flag_catalog.csv` (F07, F08), `docs/integrity_findings_v3.md`

**Source.** This is a project definition.

**Related.** awarding agency · PSC · cell.

#### lapse in appropriations

*Oversight and law.* Also called government shutdown, funding gap. A period when Congress has not passed funding for an agency, often called a shutdown. Agencies can then make only the obligations the law still allows.

**Why it matters here.** The fall 2025 lapse began in FY2026, after our years end. A 2019 lapse pushed back a DATA Act deadline (GAO-20-540), so lapses can slow data updates.

**Shows up in.** `docs/research/government_documented_gaps_v3.md`

> under a lapse in appropriations, agencies could not incur any obligation that was not legally funded from prior appropriations or otherwise authorized by law.

**Source.** GSA, "GSA plan for a lapse in appropriations", GSA Order ADM 4220.1S, Operations in the absence of appropriations, p. 6 (PDF p. 6). This is an official definition. Read more at [https://www.gsa.gov/directives/files?file=2025-09%2FFINAL_GSA_Lapse_Plan_September_2025_CV.pdf](https://www.gsa.gov/directives/files?file=2025-09%2FFINAL_GSA_Lapse_Plan_September_2025_CV.pdf).

**Related.** appropriation · obligation · fiscal year.

#### late-reported row

*Our pipeline.* Also called flag C07, reported more than 90 days after the action. A row first reported more than 90 days after its action date.

**Why it matters here.** Late rows cluster by agency and year, such as 884,941 GSA Federal Acquisition Service rows in FY2019, so recent months can still be filling in.

**Shows up in.** `initial_report_date`, `action_date`, `config/flag_catalog.csv` (C07), `docs/integrity_findings_v3.md`

**Source.** This is a project definition.

**Related.** DoD 90-day delay · action date · release date.

#### Layer A

*Our pipeline.* Also called mirror, lossless copy. The Parquet files that make up Stage 1, one per comma-separated data file inside each zip. Every column is text, and three extra columns record each row's exact place in the zip.

**Why it matters here.** Reading Layer A gives the published values with nothing changed. Read it through _files.json, never with a wildcard, to avoid double counting.

**Shows up in.** `data/parquet/layer_a/`, `_files.json`, `docs/data_stages.md` (Stage 1), `docs/data_stages.md`

**Source.** This is a project definition.

**Related.** Stage 1 · Layer B · lineage columns · Parquet.

#### Layer B

*Our pipeline.* Also called working table (pilot). The FY2025 pilot's typed table of 32 chosen columns, with money as exact decimals and dates as dates. It is not rebuilt in the all-years work.

**Why it matters here.** It shows how the later working set will type columns. Codes stay text so leading zeros survive.

**Shows up in.** `data/parquet/layer_b/`, `docs/data_stages.md`

**Source.** This is a project definition.

**Related.** Layer A · Stage 3.

#### lineage columns

*Our pipeline.* Also called _source_file, _source_member_idx, _source_row. Three columns added to each Layer A row that record which file inside the zip it came from and its row number there.

**Why it matters here.** Any row can be traced back to its exact place in the published zip.

**Shows up in.** Layer A, `docs/data_stages.md` (Stage 1)

**Source.** This is a project definition.

**Related.** Layer A · Stage 1 · Stage 0.

### M

#### management and operating contract

*Award structure.* Also called M&O contract. A contract under which a firm runs a government-owned laboratory or plant for an agency, mostly at the Department of Energy. The operator buys from many subcontractors who do not appear in FPDS.

**Why it matters here.** Each operator shows up as one very large vendor, so Department of Energy cells look highly concentrated.

**Shows up in.** `docs/research/government_documented_gaps_v3.md`

> Management and operating contract means an agreement under which the Government contracts for the operation, maintenance, or support, on its behalf, of a Government-owned or -controlled research, development, special production, or testing establishment wholly or principally devoted to one or more major programs of the contracting Federal agency.

**Source.** FAR Council, acquisition.gov, "FAR 17.601 Definitions (management and operating contracts)", FAR 17.601. This is an official definition. Read more at [https://www.acquisition.gov/far/17.601](https://www.acquisition.gov/far/17.601).

**Related.** vendor · sub-award · HHI.

#### manifest

*Our pipeline.* Also called data/manifest.csv. The file with one row per source zip, holding its SHA-256, path, web address, row count and dollar total.

**Why it matters here.** It proves which exact files every number came from.

**Shows up in.** `data/manifest.csv`, `docs/data_stages.md`

**Source.** This is a project definition.

**Related.** SHA-256 · Stage 0 · release date.

#### market definition

*Concentration.* Also called relevant market. Deciding which sellers and products count as one market before measuring shares. Our market is one cell, meaning one awarding agency, one PSC and one fiscal year.

**Why it matters here.** Concentration scores change with the market definition. Cutting PSC to 2 characters or using NAICS gives different answers.

> First, market definition helps specify the line of commerce and section of the country in which the competitive concern arises.

**Source.** DOJ and FTC, "Horizontal Merger Guidelines", Horizontal Merger Guidelines (2010), Section 4, p. 7 (PDF p. 10). This is an official definition. Read more at [https://www.justice.gov/atr/horizontal-merger-guidelines-08192010](https://www.justice.gov/atr/horizontal-merger-guidelines-08192010).

**Related.** cell · PSC · NAICS · HHI.

#### MD5

*Our pipeline.* Also called MD5 message digest. An older fingerprint method that turns any input into a 128-bit code.

**Why it matters here.** The row fingerprint uses MD5 to compare all 297 fields of every row.

**Shows up in.** `docs/data_stages.md` (Stage 1), `config/flag_catalog.csv` (B04)

> algorithm takes as input a message of arbitrary length and produces as output a 128-bit "fingerprint" or "message digest" of the input.

**Source.** IETF (rfc-editor.org), "The MD5 Message-Digest Algorithm", RFC 1321, Executive Summary. This is an official definition. Read more at [https://www.rfc-editor.org/rfc/rfc1321](https://www.rfc-editor.org/rfc/rfc1321).

**Related.** row fingerprint · SHA-256.

#### micro-purchase

*Award structure.* A small purchase at or below the micro-purchase threshold, often paid with a government purchase card. Agencies need not report most of them to FPDS.

**Why it matters here.** Reporting below the threshold is optional, so changes in what agencies report can create row-count steps with almost no dollars behind them.

**Shows up in.** `docs/integrity_findings_v3.md`, FAR 4.606

> an acquisition of supplies or services using simplified acquisition procedures

**Source.** FAR Council (GSA, DoD, NASA), acquisition.gov, "FAR 2.101 Definitions", FAR 2.101(b), definition of micro-purchase. This is an official definition. Read more at [https://www.acquisition.gov/far/2.101](https://www.acquisition.gov/far/2.101).

**Related.** micro-purchase threshold · government purchase card · FAR subpart 4.6 · row-count jump.

#### micro-purchase threshold

*Award structure.* Also called MPT. The dollar limit for a micro-purchase. It was $3,000 for FY2008 to FY2015 and $3,500 from FY2016. It rose to $10,000 in the FAR on 2020-08-31 and to $15,000 on 2025-10-01.

**Why it matters here.** FPDS must hold actions above the threshold, so each change can shift how many small rows appear.

**Shows up in.** `docs/integrity_findings_v3.md`

> Micro-purchase threshold means $15,000

**Source.** FAR Council (GSA, DoD, NASA), acquisition.gov, "FAR 2.101 Definitions", FAR 2.101(b), definition of micro-purchase threshold (text as retrieved 2026-10-06). This is an official definition. Read more at [https://www.acquisition.gov/far/2.101](https://www.acquisition.gov/far/2.101).

**Related.** micro-purchase · simplified acquisition threshold · Federal Acquisition Circular · row-count jump.

#### MISCELLANEOUS FOREIGN AWARDEES

*Our pipeline.* Also called placeholder foreign vendor. A placeholder vendor name that stands for many foreign companies, almost all on Defense contracts. One vendor ID carries 974,811 of its 974,817 rows and $41.21 billion.

**Why it matters here.** Scored as one company it would hold more than 10% of net dollars in 18,995 cells. The proposal is to report it separately and leave it out of HHI.

**Shows up in.** `recipient_name`, `docs/integrity_findings_v3.md`, `config/flag_catalog.csv` (E01)

**Source.** This is a project definition.

**Related.** placeholder vendor · generic entity identifier · vendor.

#### modification

*Award structure.* Also called mod, modification number, amendment. A change to an existing contract, such as adding money, exercising an option or ending the contract early. Each modification is its own row with its own amount, which can be negative.

**Why it matters here.** Modifications carry deobligations and reversal pairs. In FY2025, modification 0 is 80.8% of rows but only 41.3% of dollars.

**Shows up in.** `modification_number`, `action_type_code`, `docs/source_choice.md`

> The identifier of an action being reported that indicates the specific subsequent change to the initial award.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, term 'Modification Number'. This is an official definition. Read more at [https://www.usaspending.gov/?glossary=modification-number](https://www.usaspending.gov/?glossary=modification-number).

**Related.** transaction · deobligation · option · reversal pair.

#### multi-agency contract

*Award structure.* Also called MAC. An order contract that one agency sets up for other agencies to use.

**Why it matters here.** Each order under a MAC carries its own awarding agency, so MAC spending spreads across many agencies' cells.

**Shows up in.** `idv_type_code`, `parent_award_type_code`

> A Multi-Agency Contract (MAC) is a task-order or delivery-order contract established by one agency for use by government agencies to obtain supplies and services.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, term 'Multi-Agency Contract (MAC)'. This is an official definition. Read more at [https://www.usaspending.gov/?glossary=multi-agency-contract-mac](https://www.usaspending.gov/?glossary=multi-agency-contract-mac).

**Related.** GWAC · IDV · awarding agency.

#### multiple award

*Award structure.* Also called multiple-award contract, multiple_or_single_award_idv_code M. An IDV awarded to several vendors from one competition. The vendors then compete for each order.

**Why it matters here.** Orders under multiple-award IDVs are competed through fair opportunity, so their competition codes differ from those of standalone contracts.

**Shows up in.** `multiple_or_single_award_idv_code`, `parent_award_single_or_multiple_code`

> Indicates whether the contract is one of many that resulted from a single solicitation, all of the contracts are for the same or similar items, and contracting officers are required to compare their requirements with the offerings under more than one contract or are required to acquire the requirement competitively among the awardees.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending data dictionary, API /api/v2/references/data_dictionary/", USAspending data dictionary, element MultipleOrSingleAwardIDV. This is an official definition. Read more at [https://www.acquisition.gov/far/subpart-16.5](https://www.acquisition.gov/far/subpart-16.5).

**Related.** fair opportunity · IDIQ · IDV · extent competed.

### N

#### NAICS

*Codes.* Also called North American Industry Classification System, naics_code. A 6-digit industry code. The contracting officer picks one for each contract, and it sets which small business size standard applies.

**Why it matters here.** NAICS is an alternative market definition. It is 19.7% blank in FY2008 and under 2% blank from FY2011, and its codes are revised every 5 years.

**Shows up in.** `naics_code`, `naics_description`, `config/flag_catalog.csv` (F02), `docs/integrity_findings_v3.md`

> The North American Industry Classification System (NAICS) is the standard used by Federal statistical agencies in classifying business establishments for the purpose of collecting, analyzing, and publishing statistical data related to the U.S. business economy.

**Source.** U.S. Census Bureau, "North American Industry Classification System (NAICS)", Census NAICS page, Introduction to NAICS. This is an official definition. Read more at [https://www.census.gov/naics/](https://www.census.gov/naics/).

**Related.** PSC · small business size standard · market definition · contracting officer.

#### national interest action code

*Competition and socioeconomic.* Also called NIA, national_interest_action_code. A code that tags contracts tied to a declared emergency or national event, such as a named hurricane or COVID-19.

**Why it matters here.** It can explain a one-year spike in a cell, such as COVID-19 buying in FY2020. FPDS end-dated the field as of 2024-01-27.

**Shows up in.** `national_interest_action_code`, `national_interest_action`

> The National Interest Action values are used to categorize procurement actions related to emergency contingency responses or other nationally significant events.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, term 'National Interest Action (NIA)', official text. This is an official definition. Read more at [https://www.usaspending.gov/?glossary=national-interest-action-nia](https://www.usaspending.gov/?glossary=national-interest-action-nia).

**Related.** Disaster Emergency Fund Code.

#### negative vendor total

*Our pipeline.* Also called negative vendor-cell. A vendor-cell whose net is below zero, usually because money obligated in an earlier year was taken back.

**Why it matters here.** A negative total has no meaningful share. 588,645 vendor-cells (7.5%) are negative, in 35.0% of cells, netting to -$124.05 billion.

**Shows up in.** `docs/integrity_findings_v3.md`, `config/decisions.csv` (D0031)

**Source.** This is a project definition.

**Related.** vendor-cell · deobligation · cell · HHI.

#### net dollars

*Money.* Also called net, net obligations. The sum of all amounts with their signs, so a +$5 entry and a -$5 reversal net to $0.

**Why it matters here.** Vendor shares, HHI and CR4 use net dollars per vendor-cell. All years net to $10.51 trillion.

**Shows up in.** `docs/integrity_findings_v3.md`, `config/benchmarks.csv`

**Source.** This is a project definition.

**Related.** gross dollars · federal action obligation · vendor-cell · HHI.

#### nominal dollars

*Money.* Also called current dollars. Dollar amounts as recorded at the time, with no adjustment for inflation.

**Why it matters here.** All our totals are nominal. GAO's charts state constant-dollar figures, which equal nominal only in the chart's base year.

**Shows up in.** `config/benchmarks.csv` (dollars_basis)

> The current dollar value of a good or service is its value in terms of prices current at the time the good or service is acquired or sold.

**Source.** GAO, "A Glossary of Terms Used in the Federal Budget Process", Budget Glossary, 'Current Dollar', p. 37 (PDF p. 41). This is an official definition. Read more at [https://www.gao.gov/assets/gao-05-734sp.pdf](https://www.gao.gov/assets/gao-05-734sp.pdf).

**Related.** constant dollars · benchmark.

#### not competed

*Competition and socioeconomic.* Also called extent_competed_code B, C and G, sole source. An award made without competition. Codes B (not available for competition), C (not competed) and G (not competed under simplified acquisition) mark it.

**Why it matters here.** Cells with many uncompeted awards can show high concentration for legal reasons, such as only one capable source.

**Shows up in.** `extent_competed_code` B, C, G

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, term 'Extent Competed', plain text (code list). The summary paraphrases an official source. Read more at [https://www.usaspending.gov/?glossary=extent-competed](https://www.usaspending.gov/?glossary=extent-competed).

**Related.** extent competed · other than full and open competition.

#### number of offers received

*Competition and socioeconomic.* Also called number_of_offers_received, offers. How many bids or proposals came in for the award.

**Why it matters here.** It is 5% blank or less through FY2017 and 63% to 70% blank from FY2018. Zero offers on a competed action (flag X02) seems to mean not reported in FY2008 to FY2011.

**Shows up in.** `number_of_offers_received`, `config/flag_catalog.csv` (F09, X02), `docs/integrity_findings_v3.md`

> The number of actual offers/bids received in response to the solicitation.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending data dictionary, API /api/v2/references/data_dictionary/", USAspending data dictionary, element NumberOfOffersReceived. This is an official definition. Read more at [https://www.usaspending.gov/data-dictionary](https://www.usaspending.gov/data-dictionary).

**Related.** extent competed · full and open competition.

### O

#### object class

*Data systems and files.* Also called object classification. A budget category for what money was spent on, such as personnel pay or equipment, whatever the agency or program.

**Why it matters here.** object_classes_funding_this_award shows the budget categories behind an award. We do not use it in the measure.

**Shows up in.** `object_classes_funding_this_award`

> Categories in a classification system that presents obligations by the items or services purchased by the Federal Government.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, term 'Object Class', official text. This is an official definition. Read more at [https://www.usaspending.gov/?glossary=object-class](https://www.usaspending.gov/?glossary=object-class).

**Related.** program activity · File B · obligation.

#### obligation

*Money.* Also called obligated amount. A binding promise to pay, made when an agency signs a contract or places an order. Payment can come right away or years later.

**Why it matters here.** Our measure counts obligations. Payments made later are outlays, a separate figure.

**Shows up in.** `federal_action_obligation`, `docs/integrity_findings_v3.md`

> Obligation means a legally binding agreement that will result in outlays, immediately or in the future.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, term 'Obligation', official text. This is an official definition. Read more at [https://www.usaspending.gov/?glossary=obligation](https://www.usaspending.gov/?glossary=obligation).

**Related.** federal action obligation · deobligation · outlay · appropriation.

#### OMB

*Oversight and law.* Also called Office of Management and Budget. The White House office that prepares the budget and oversees how agencies are managed. It sets rules for procurement data quality and DATA Act reporting.

**Why it matters here.** OMB guidance set the verification and validation and SAO rules behind the data we use.

**Shows up in.** `docs/research/government_documented_gaps_v3.md`

> Specifically, OMB’s mission is to assist the President in meeting his policy, budget, management and regulatory objectives and to fulfill the agency’s statutory responsibilities.

**Source.** OMB (whitehouse.gov), "Office of Management and Budget home page", OMB home page, mission. This is an official definition. Read more at [https://www.whitehouse.gov/omb/](https://www.whitehouse.gov/omb/).

**Related.** verification and validation · Senior Accountable Official · DATA Act.

#### option

*Award structure.* Also called contract option. A right written into a contract that lets the government buy more or extend the contract later.

**Why it matters here.** Exercising an option is a modification that can add an obligation row.

**Shows up in.** `base_and_exercised_options_value`, `base_and_all_options_value`, `action_type_code`

> Option means a unilateral right in a contract by which, for a specified time, the Government may elect to purchase additional supplies or services called for by the contract, or may elect to extend the term of the contract.

**Source.** FAR Council (GSA, DoD, NASA), acquisition.gov, "FAR 2.101 Definitions", FAR 2.101(b), definition of option. This is an official definition. Read more at [https://www.acquisition.gov/far/2.101](https://www.acquisition.gov/far/2.101).

**Related.** modification · base and exercised options value · base and all options value.

#### other than full and open competition

*Competition and socioeconomic.* Also called FAR 6.3, other_than_full_and_open_competition_code. The legal exceptions that let an agency skip full and open competition, such as only one responsible source or unusual urgency.

**Why it matters here.** other_than_full_and_open_competition_code gives the reason for an uncompeted award.

**Shows up in.** `other_than_full_and_open_competition_code`

> The designator for solicitation procedures other than full and open competition pursuant to FAR 6.3.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending data dictionary, API /api/v2/references/data_dictionary/", USAspending data dictionary, element OtherThanFullAndOpenCompetition. This is an official definition. Read more at [https://www.acquisition.gov/far/subpart-6.3](https://www.acquisition.gov/far/subpart-6.3).

**Related.** not competed · full and open competition · extent competed.

#### other transaction agreement

*Award structure.* Also called OTA, other transaction, OT. A legally binding agreement that is neither a standard contract nor a grant. Agencies use OTAs for flexible deals such as research and prototypes.

**Why it matters here.** FAR 4.601 leaves other transactions out of contract actions, so OTA dollars may be missing from our cells. GAO found agencies reported OTA spending inconsistently.

**Shows up in.** `docs/research/government_documented_gaps_v3.md`

> other transaction agreements (OTA)—legally binding agreements other than standard federal contracts and grants, allowing for more flexible arrangements.

**Source.** GAO, "Federal Spending Transparency: Opportunities Exist to Further Improve the Information Available on USAspending.gov", Highlights page (PDF p. 1). This is an official definition. Read more at [https://www.gao.gov/assets/gao-24-106214.pdf](https://www.gao.gov/assets/gao-24-106214.pdf).

**Related.** contract action · FPDS · GAO.

#### outlay

*Money.* Also called payment, disbursement. Money actually paid out to settle an obligation. It can come years after the obligation.

**Why it matters here.** Our files carry an award-level outlay column, but outlays were required only from FY2022 except for COVID-19 awards, so we do not use it.

**Shows up in.** `total_outlayed_amount_for_overall_award`

> The issuance of checks, disbursement of cash, or electronic transfer of funds made to liquidate a federal obligation.

**Source.** GAO, "A Glossary of Terms Used in the Federal Budget Process", Budget Glossary, 'Outlay', p. 73 (PDF p. 77). This is an official definition. Read more at [https://www.usaspending.gov/?glossary=outlay](https://www.usaspending.gov/?glossary=outlay).

**Related.** obligation · Disaster Emergency Fund Code.

### P

#### parent DUNS

*Identifiers.* Also called recipient_parent_duns, global parent DUNS. The DUNS number of a vendor's ultimate parent, used before April 2022.

**Why it matters here.** It is empty in recent years, so the parent UEI is the only parent ID that spans FY2008 to FY2025.

**Shows up in.** `recipient_parent_duns`

> The unique identification number for the ultimate parent of an awardee or recipient.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, term 'Parent DUNS'. This is an official definition. Read more at [https://www.usaspending.gov/?glossary=parent-duns](https://www.usaspending.gov/?glossary=parent-duns).

**Related.** DUNS · parent UEI · ultimate parent.

#### parent test

*Our pipeline.* Also called parent-ID test, test K. Our check of whether the parent ID on a row changes when a deal closes or carries today's parent back in time. Four deals from 2013 to 2020 were tested against closing dates in company filings with the Securities and Exchange Commission.

**Why it matters here.** In all four the parent ID switched 2 to 6 months after closing, which supports using the parent recorded at the time of each action.

**Shows up in.** `docs/integrity_findings_v3.md`, `config/decisions.csv` (D0029)

**Source.** This is a project definition.

**Related.** parent UEI · ultimate parent · vendor.

#### parent UEI

*Identifiers.* Also called recipient_parent_uei, ultimate parent UEI. The UEI of a vendor's ultimate parent company.

**Why it matters here.** Our vendor is the parent UEI, or the recipient UEI where the parent is blank. The parent test found the parent ID switches 2 to 6 months after a deal closes.

**Shows up in.** `recipient_parent_uei`, `recipient_parent_name`, `docs/integrity_findings_v3.md`

> The Unique Entity Identifier (UEI) for the ultimate parent of an awardee or recipient.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending data dictionary, API /api/v2/references/data_dictionary/", USAspending data dictionary, element UltimateParentUEI. This is an official definition. Read more at [https://www.usaspending.gov/data-dictionary](https://www.usaspending.gov/data-dictionary).

**Related.** UEI · ultimate parent · vendor · parent test.

#### Parquet

*Our pipeline.* Also called Apache Parquet. An open file format that stores data by column, which makes large tables fast to read.

**Why it matters here.** Stage 1 holds all 18 years as 97 Parquet files, 19.84 GB in total.

**Shows up in.** `data/parquet/layer_a/`, `docs/data_stages.md` (Disk)

> Apache Parquet is an open source, column-oriented data file format designed for efficient data storage and retrieval.

**Source.** Apache Software Foundation (parquet.apache.org), "Apache Parquet documentation, Overview", Apache Parquet documentation, Overview. This is an official definition. Read more at [https://parquet.apache.org/docs/overview/](https://parquet.apache.org/docs/overview/).

**Related.** Layer A · DuckDB · Stage 1.

#### PASS/WARN/FAIL

*Our pipeline.* Also called benchmark status. The status of a benchmark check. PASS means within 2% of the published total, WARN within 10% and FAIL beyond 10%. The bands were fixed before any comparison.

**Why it matters here.** All 8 benchmarked years PASS under the version 2 rule.

**Shows up in.** `config/flag_catalog.csv` (I01, I02), `docs/integrity_findings_v3.md`

**Source.** This is a project definition.

**Related.** benchmark · benchmark figure · benchmark bound.

#### period of performance

*Award structure.* Also called period_of_performance_start_date, period_of_performance_current_end_date. The dates the contract work runs, from the start date to the current end date. The end date counts exercised options only.

**Why it matters here.** 2,229,493 rows show a start date after the end date (flag C06). Most are modifications before FY2020 that carry their own date as the start.

**Shows up in.** `period_of_performance_start_date`, `period_of_performance_current_end_date`, `docs/integrity_findings_v3.md`

> The date that the award begins, as agreed upon by the parties involved.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, term 'Period of Performance Start Date'. This is an official definition. Read more at [https://www.usaspending.gov/?glossary=period-of-performance-start-date](https://www.usaspending.gov/?glossary=period-of-performance-start-date).

**Related.** modification · option · action date.

#### PGI

*Oversight and law.* Also called DFARS Procedures, Guidance, and Information. DoD's companion to the DFARS. It holds procedures and guidance that sit beside the binding rules, including DoD's instructions for reporting to FPDS.

**Why it matters here.** The written basis for DoD's 90-day delay is PGI 204.604(2), first seen in its 2016 revision.

**Shows up in.** `docs/research/government_documented_gaps_v3.md`

**Source.** DoD (Defense Acquisition Regulations System), acquisition.gov, "DFARS Part 201 Federal Acquisition Regulations System", DFARS 201.201-70. The summary paraphrases an official source. Read more at [https://www.acquisition.gov/dfars/part-201-federal-acquisition-regulations-system](https://www.acquisition.gov/dfars/part-201-federal-acquisition-regulations-system).

**Related.** DFARS · DoD 90-day delay · FAR.

#### PIID

*Award structure.* Also called Procurement Instrument Identifier, award ID, contract number. The contract or order number the agency assigns. Agencies must keep each PIID unique government-wide.

**Why it matters here.** award_id_piid is easy to read but is not unique across agencies by itself, so we key awards on contract_award_unique_key.

**Shows up in.** `award_id_piid`, `parent_award_id_piid`, `tools/column_guide/colguide.json`

> A unique identifier assigned to a federal contract, purchase order, basic ordering agreement, basic agreement, and blanket purchase agreement.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, term 'Procurement Instrument Identifier (PIID)'. This is an official definition. Read more at [https://www.acquisition.gov/far/subpart-4.16](https://www.acquisition.gov/far/subpart-4.16).

**Related.** unique award key · referenced IDV · award.

#### placeholder vendor

*Our pipeline.* Also called flag E01. A vendor name that is a placeholder, such as MULTIPLE RECIPIENTS, UNKNOWN or MISCELLANEOUS FOREIGN AWARDEES, instead of a real firm.

**Why it matters here.** A concentration measure must not treat a placeholder as one company.

**Shows up in.** `recipient_name`, `config/flag_catalog.csv` (E01, E02)

**Source.** This is a project definition.

**Related.** MISCELLANEOUS FOREIGN AWARDEES · generic entity identifier · vendor.

#### potential total value of award

*Money.* Also called potential_total_value_of_award, potential award amount. For a contract, the total that could be obligated if the base and all options were used.

**Why it matters here.** It is an award-level ceiling and is never a measure of spending.

**Shows up in.** `potential_total_value_of_award`

> For procurement, the total amount that could be obligated on a contract, if the base and all options are exercised.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending data dictionary, API /api/v2/references/data_dictionary/", USAspending data dictionary, element PotentialTotalValueOfAward. This is an official definition. Read more at [https://www.usaspending.gov/?glossary=potential-award-amount](https://www.usaspending.gov/?glossary=potential-award-amount).

**Related.** base and all options value · option.

#### program activity

*Data systems and files.* A specific activity or project inside a budget account, as listed in the President's budget.

**Why it matters here.** program_activities_funding_this_award links an award to the budget programs that paid for it. We do not use it in the measure.

**Shows up in.** `program_activities_funding_this_award`

> A specific activity or project as listed in the program and financing schedules of the annual budget of the United States Government.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, term 'Program Activity', official text. This is an official definition. Read more at [https://www.usaspending.gov/?glossary=program-activity](https://www.usaspending.gov/?glossary=program-activity).

**Related.** object class · File B · Treasury Account Symbol.

#### PSC

*Codes.* Also called product or service code, product_or_service_code. A 4-character code for what was bought. Codes that start with a digit are products. Codes that start with a letter are services or research and development.

**Why it matters here.** PSC is the product side of our cell. One revision end-dated 721 research and development codes and added 155, which breaks those series across years.

**Shows up in.** `product_or_service_code`, `config/flag_catalog.csv` (F01), `docs/integrity_findings_v3.md`

> The Product and Service Codes (PSC) Manual provides codes to describe products, services, and research and development (R&D) purchased by the federal government.

**Source.** GSA, Federal Acquisition Service, "Product and Service Codes (PSC) Manual, Fiscal Year 2025 Edition", PSC Manual, Introduction, p. 4 (PDF p. 4). This is an official definition. Read more at [https://www.acquisition.gov/psc-manual](https://www.acquisition.gov/psc-manual).

**Related.** Federal Supply Class · NAICS · cell · market definition.

#### purchase order

*Award structure.* Also called PO. A simple order to buy goods or services under the simplified acquisition rules. It is award type B in our data.

**Why it matters here.** Purchase orders fell from 1,600,094 in FY2008 to 858,147 in FY2009, part of the FY2008 row-count step.

**Shows up in.** `award_type_code` B, `docs/integrity_findings_v3.md`

> means an offer by the Government to buy supplies or services, including construction and research and development, upon specified terms and conditions, using simplified acquisition procedures

**Source.** FAR Council (GSA, DoD, NASA), acquisition.gov, "FAR 2.101 Definitions", FAR 2.101(b), definition of purchase order. This is an official definition. Read more at [https://www.acquisition.gov/far/2.101](https://www.acquisition.gov/far/2.101).

**Related.** simplified acquisition threshold · definitive contract · award type · row-count jump.

### R

#### recipient hash

*Identifiers.* Also called recipient_id, recipient profile ID. An internal ID that USAspending gives each recipient profile on its website and its public data service. It ends in -P for a parent, -C for a child company, or -R for neither.

**Why it matters here.** It is not a column in our files. Our vendor grouping uses UEIs.

**Shows up in.** USAspending recipient profile pages and API (not in our files)

> A unique identifier for the recipient at a specific level (parent, child, or neither).

**Source.** Treasury (fedspendingtransparency/usaspending-api on GitHub), "API contract: Recipient overview /api/v2/recipient/{recipient_id}/", API contract /api/v2/recipient/{recipient_id}/, parameter recipient_id. This is an official definition. Read more at [https://github.com/fedspendingtransparency/usaspending-api/blob/master/usaspending_api/api_contracts/contracts/v2/recipient/recipient_id.md](https://github.com/fedspendingtransparency/usaspending-api/blob/master/usaspending_api/api_contracts/contracts/v2/recipient/recipient_id.md).

**Related.** UEI · parent UEI · ultimate parent.

#### referenced IDV

*Award structure.* Also called parent award, parent IDV, parent_award_id_piid. The IDV that an order was placed under. On an order row, parent_award_id_piid holds the IDV's PIID.

**Why it matters here.** Orders link to their IDV through this field. Three orders have no parent and three standalone contracts have one (flags G01 and G02).

**Shows up in.** `parent_award_id_piid`, `parent_award_agency_id`, `parent_award_type_code`, `config/flag_catalog.csv` (G01, G02)

> The identifier of the procurement award under which the specific award is issued, such as a Federal Supply Schedule.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, term 'Parent Award Identification (ID) Number'. This is an official definition. Read more at [https://www.usaspending.gov/?glossary=parent-award-identification-id-number](https://www.usaspending.gov/?glossary=parent-award-identification-id-number).

**Related.** IDV · PIID · delivery order · BPA call.

#### release date

*Our pipeline.* Also called snapshot date, 20260906. The date in an archive zip's name, which marks the snapshot it holds. All our zips come from the 2026-09-06 release.

**Why it matters here.** Every file is a snapshot, and one release for all years avoids small differences nobody could trace (flag A01).

**Shows up in.** file names *_20260906.zip, `data/manifest.csv` (data_as_of_date), `config/flag_catalog.csv` (A01, A02), `docs/data_stages.md`

**Source.** This is a project definition.

**Related.** Full file · Award Data Archive · Stage 0 · manifest.

#### reversal pair

*Our pipeline.* Also called entry and reversal, erroneous entry pair. A very large entry and a matching negative entry on the same contract a few days later, most likely an error and its correction. We found five, from $7.0 billion to $344.7 billion.

**Why it matters here.** Pairs inside one fiscal year cancel in net totals but distort gross totals. The Emerson pair crosses fiscal years and breaks two cells.

**Shows up in.** `docs/integrity_findings_v3.md`, `config/decisions.csv` (D0024)

**Source.** This is a project definition.

**Related.** Emerson pair · gross dollars · net dollars · exclusions ledger · deobligation.

#### Revolutionary FAR Overhaul

*Oversight and law.* Also called RFO. A rewrite of the FAR that began in 2025 to shorten it and move its rules into a new structure. The contract reporting rules of FAR subpart 4.6 become section 4.301.

**Why it matters here.** FY2025 rows were reported under the old rules, so the rewrite matters for later releases.

**Shows up in.** `docs/research/government_documented_gaps_v3.md`

**Source.** GSA Office of Governmentwide Policy, "FAR Class Deviation for FAR Part 4", GSA memo of 2025-08-13, background. The summary paraphrases an official source. Read more at [https://www.acquisition.gov/sites/default/files/page_file_uploads/GSA_RFO_Deviation_Part-4.pdf](https://www.acquisition.gov/sites/default/files/page_file_uploads/GSA_RFO_Deviation_Part-4.pdf).

**Related.** FAR · FAR subpart 4.6 · deviation.

#### row fingerprint

*Our pipeline.* Also called full-row fingerprint, row checksum. One number that sums up every field of every row in a file. Each row's 297 fields are joined and run through MD5, and the first 16 characters of each row's code are added up.

**Why it matters here.** Matching fingerprints on both readers is strong evidence that every field of every row was copied exactly.

**Shows up in.** `docs/data_stages.md` (Stage 1), `reports/integrity/stage1_mirror_proof.md`, `docs/data_stages.md`

**Source.** This is a project definition.

**Related.** MD5 · Stage 1 · Layer A.

#### row-count jump

*Our pipeline.* Also called FY2015 step, small-row jump. A sharp change in the number of rows with little change in dollars. Ours occur in FY2008, FY2015 and FY2019, each driven by small orders from one agency.

**Why it matters here.** Counts of actions or vendors step up with no change in spending, so count-based measures need a fixed size cutoff such as $10,000.

**Shows up in.** `docs/integrity_findings_v3.md`, `config/decisions.csv` (D0026)

**Source.** This is a project definition.

**Related.** micro-purchase threshold · delivery order · BPA call · purchase order · subtier agency.

### S

#### SAM.gov

*Data systems and files.* Also called SAM, System for Award Management. The government registry of companies and other entities that want federal awards. Vendors register there to get a UEI. SAM also records each vendor's CAGE code.

**Why it matters here.** The UEI and parent UEI that define our vendors come from SAM registrations.

**Shows up in.** `recipient_uei`, `recipient_parent_uei`, `cage_code`, `sam_exception`

> System for Award Management (SAM) which is the primary database for information on entities that do business with the federal government, and in which such entities must register

**Source.** GAO, "DATA Act: OMB, Treasury, and Agencies Need to Improve Completeness and Accuracy of Spending Data and Disclose Limitations", p. 8 (PDF p. 13). This is an official definition. Read more at [https://sam.gov](https://sam.gov).

**Related.** UEI · parent UEI · CAGE code · File E · GSA.

#### SBA

*Oversight and law.* Also called Small Business Administration. The agency that sets small business size standards and runs programs such as 8(a), HUBZone and the women-owned program.

**Why it matters here.** SBA rules decide which vendors count as small, which shapes set-asides in our data.

**Shows up in.** `type_of_set_aside_code`, `contracting_officers_determination_of_business_size_code`

**Source.** FAR Council, acquisition.gov, "FAR 19.102 Small business size standards and NAICS codes", FAR 19.102(a)(1) (SBA establishes size standards industry by industry). The summary paraphrases an official source. Read more at [https://www.sba.gov](https://www.sba.gov).

**Related.** small business size standard · 8(a) · HUBZone · WOSB · SDVOSB.

#### SDVOSB

*Competition and socioeconomic.* Also called service-disabled veteran-owned small business. A small business at least 51% owned and controlled by veterans with service-connected disabilities.

**Why it matters here.** SDVOSB set-asides limit who can bid, which can shape concentration in a cell.

**Shows up in.** `type_of_set_aside_code`

> Not less than 51 percent of which is owned and controlled by one or more service-disabled veterans

**Source.** FAR Council (GSA, DoD, NASA), acquisition.gov, "FAR 2.101 Definitions", FAR 2.101(b), definition of SDVOSB concern, paragraph (1)(i). This is an official definition. Read more at [https://www.acquisition.gov/far/2.101](https://www.acquisition.gov/far/2.101).

**Related.** set-aside · small business concern.

#### Senior Accountable Official

*Data systems and files.* Also called SAO. The official at each agency who signs off on the agency's DATA Act data each quarter.

**Why it matters here.** SAO sign-offs cover File A to File C and the links between files. They do not certify each FPDS row.

**Shows up in.** `docs/research/government_documented_gaps_v3.md`

> Each agency’s data must pass a series of validations in the broker and then be certified by the agency’s senior accountable official (SAO) before they are submitted for display on USAspending.gov.

**Source.** GAO, "DATA Act: Quality of Data Submissions Has Improved but Further Action Is Needed to Disclose Known Data Limitations", Appendix V, p. 66 (PDF p. 72). This is an official definition. Read more at [https://www.gao.gov/assets/gao-20-75.pdf](https://www.gao.gov/assets/gao-20-75.pdf).

**Related.** DATA Act · data quality certification · DATA Act Broker.

#### set-aside

*Competition and socioeconomic.* Also called type_of_set_aside_code, small business set-aside. An award reserved for a group of firms, usually small businesses or a type of small business such as 8(a) or HUBZone firms.

**Why it matters here.** type_of_set_aside_code is blank on 77% of FY2025 rows, so set-aside analysis needs care.

**Shows up in.** `type_of_set_aside_code`, `type_of_set_aside`, `docs/source_choice.md`

> A tool used to award contracts to specific types of businesses. Most set asides reserve contracts for small businesses.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, term 'Set Aside Type'. This is an official definition. Read more at [https://www.acquisition.gov/far/subpart-19.5](https://www.acquisition.gov/far/subpart-19.5).

**Related.** small business concern · 8(a) · HUBZone · SDVOSB · WOSB · full and open after exclusion of sources.

#### SHA-256

*Our pipeline.* Also called Secure Hash Algorithm 256. A fingerprint of a file's exact bytes. Changing even one byte gives a different value.

**Why it matters here.** Each zip's SHA-256 in the manifest was checked before and after every move, so Stage 0 is provably unchanged.

**Shows up in.** `data/manifest.csv` (sha256), `data/external/gov_sources/*.meta.json`, `docs/data_stages.md`

> This Standard specifies secure hash algorithms - SHA-1, SHA-224, SHA-256,

**Source.** NIST, "Secure Hash Standard (SHS)", FIPS 180-4, Explanation (PDF p. 4). This is an official definition. Read more at [https://csrc.nist.gov/pubs/fips/180-4/upd1/final](https://csrc.nist.gov/pubs/fips/180-4/upd1/final).

**Related.** MD5 · manifest · Stage 0.

#### simplified acquisition threshold

*Award structure.* Also called SAT. The dollar limit below which agencies may use simpler, faster buying procedures. It is $350,000 in the current FAR.

**Why it matters here.** Extent competed codes F and G mark actions competed or not competed under these simpler procedures.

**Shows up in.** `extent_competed_code` F and G, `solicitation_procedures_code`

> Simplified acquisition threshold means $350,000

**Source.** FAR Council (GSA, DoD, NASA), acquisition.gov, "FAR 2.101 Definitions", FAR 2.101(b), definition of simplified acquisition threshold (text as retrieved 2026-10-06). This is an official definition. Read more at [https://www.acquisition.gov/far/2.101](https://www.acquisition.gov/far/2.101).

**Related.** micro-purchase threshold · purchase order · extent competed.

#### small business concern

*Competition and socioeconomic.* Also called small business. A firm that is independently owned, does not dominate its field, and is under SBA's size standard for the contract, counting the firms it controls or that control it.

**Why it matters here.** Small business status changes which competition rules apply and is recorded on each row.

**Shows up in.** `contracting_officers_determination_of_business_size_code`

> that is independently owned and operated, not dominant in its field of operation, and qualified as a small business under the criteria and size standards in 13 CFR part 121

**Source.** FAR Council (GSA, DoD, NASA), acquisition.gov, "FAR 2.101 Definitions", FAR 2.101(b), definition of small business concern, paragraph (1). This is an official definition. Read more at [https://www.acquisition.gov/far/2.101](https://www.acquisition.gov/far/2.101).

**Related.** small business size standard · set-aside · SBA.

#### small business size standard

*Competition and socioeconomic.* Also called size standard. The largest a firm may be, in employees or yearly revenue, and still count as small for a contract. SBA sets one for each NAICS code.

**Why it matters here.** Size is judged per contract, so the same vendor can be small on one row and other than small on another.

**Shows up in.** `contracting_officers_determination_of_business_size_code`

> These size standards define the maximum size that a business — and its affiliates — can be to qualify as a small business for a particular contract.

**Source.** SBA, "Size standards", SBA, Size standards section. This is an official definition. Read more at [https://www.sba.gov/federal-contracting/contracting-guide/size-standards](https://www.sba.gov/federal-contracting/contracting-guide/size-standards).

**Related.** small business concern · NAICS · SBA · set-aside.

#### Stage 0

*Our pipeline.* Also called raw stage, Stage 0 raw. The zip files exactly as USAspending published them, locked read-only. Everything else is built from them.

**Why it matters here.** It is the fixed starting point that every later number can be traced back to.

**Shows up in.** `Project/DATA/raw/award_data_archive/release_2026-09-06/`, `docs/data_stages.md` (Stage 0), `reports/integrity/stage0_inventory.md`

**Source.** This is a project definition.

**Related.** Stage 1 · manifest · SHA-256 · release date · Award Data Archive.

#### Stage 1

*Our pipeline.* Also called mirror, Stage 1 mirror. A lossless copy of every row and all 297 columns in Parquet, with every value kept as text. Two independent readers prove it matches the zips, file by file.

**Why it matters here.** It lets us query 88.7 million rows quickly without trusting a conversion we have not checked.

**Shows up in.** `data/parquet/layer_a/fy{YYYY}/20260906/`, `docs/data_stages.md` (Stage 1), `reports/integrity/stage1_mirror_proof.md`

**Source.** This is a project definition.

**Related.** Layer A · Stage 0 · Stage 2 · row fingerprint · Parquet · DuckDB.

#### Stage 2

*Our pipeline.* Also called flags stage, Stage 2 flags. Facts about the data kept beside it, such as row flags, per-year profiles and cross-year checks. It changes nothing in Stage 0 or Stage 1 and can be rebuilt at any time.

**Why it matters here.** All integrity findings come from Stage 2.

**Shows up in.** `data/integrity/`, `reports/integrity/`, `docs/data_stages.md` (Stage 2)

**Source.** This is a project definition.

**Related.** flag · flag catalog · Stage 1 · Stage 3.

#### Stage 3

*Our pipeline.* Also called working set. The future typed and cleaned table for analysis. It is not built yet. Rows can be changed or left out only by rules recorded in the decision log.

**Why it matters here.** HHI and CR4 will be computed from Stage 3, and every left-out row will sit in the exclusions ledger.

**Shows up in.** `docs/data_stages.md` (Stage 3), `config/decisions.csv`

**Source.** This is a project definition.

**Related.** exclusions ledger · decision log · Stage 2.

#### sub-award

*Award structure.* Also called subaward, subcontract, sub-grant. Part of a federal award that the main recipient passes to another firm or group to carry out. Sub-awards are reported apart from the main awards and are outside our data.

**Why it matters here.** Money a vendor passes to its subcontractors stays with that vendor in our shares.

**Shows up in.** File F, `docs/research/government_documented_gaps_v3.md`

> An award provided by a pass-through entity to a subrecipient for the subrecipient to carry out part of a federal award received by the pass-through entity.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, Sub-Award, official text. This is an official definition. Read more at [https://www.usaspending.gov/](https://www.usaspending.gov/).

**Related.** award · File F · management and operating contract.

#### subtier agency

*Codes.* Also called sub-agency, awarding_sub_agency_code, subtier. A unit inside an agency, such as the Army or the Defense Logistics Agency inside Defense.

**Why it matters here.** Sub-agencies drive row counts. Defense Logistics Agency rows rose from 600,140 in FY2014 to 2,486,703 in FY2015.

**Shows up in.** `awarding_sub_agency_code`, `funding_sub_agency_code`, `config/flag_catalog.csv` (F06, H06 to H08), `docs/integrity_findings_v3.md`

> Name and identifier of the level 2 organization that awarded, executed or is otherwise responsible for the transaction.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, term 'Awarding Sub-Agency', official text. This is an official definition. Read more at [https://www.usaspending.gov/?glossary=awarding-sub-agency](https://www.usaspending.gov/?glossary=awarding-sub-agency).

**Related.** awarding agency · contracting office · row-count jump.

### T

#### task order

*Award structure.* An order for services placed under an existing contract.

**Why it matters here.** FPDS records task orders under an IDV as award type C, the same code as delivery orders, so our data cannot separate them by type.

**Shows up in.** `award_type_code` C

> Task order means an order for services placed against an established contract or with Government sources.

**Source.** FAR Council (GSA, DoD, NASA), acquisition.gov, "FAR 2.101 Definitions", FAR 2.101(b), definition of task order. This is an official definition. Read more at [https://www.acquisition.gov/far/2.101](https://www.acquisition.gov/far/2.101).

**Related.** delivery order · IDIQ · GWAC.

#### termination for convenience

*Award structure.* The government ends all or part of a contract because it no longer needs the work, with no fault by the vendor. The ending is recorded as a modification, often with a deobligation.

**Why it matters here.** Terminations in FY2025 add deobligations that can make vendor totals negative.

**Shows up in.** `action_type_code`, `docs/research/government_documented_gaps_v3.md`

> Termination for convenience means the exercise of the Government's right to completely or partially terminate performance of work under a contract when it is in the Government's interest.

**Source.** FAR Council (GSA, DoD, NASA), acquisition.gov, "FAR 2.101 Definitions", FAR 2.101(b), Termination for convenience. This is an official definition. Read more at [https://www.acquisition.gov/far/2.101](https://www.acquisition.gov/far/2.101).

**Related.** modification · deobligation · negative vendor total.

#### thin month

*Our pipeline.* Also called flags H01 and H02. A month whose rows or dollars fall below half the median month of its fiscal year.

**Why it matters here.** Only one month in 18 years is thin by dollars, January 2009, and the Emerson reversal alone causes it.

**Shows up in.** `config/flag_catalog.csv` (H01, H02), `docs/integrity_findings_v3.md`

**Source.** This is a project definition.

**Related.** Emerson pair · fiscal year.

#### top-4 share

*Concentration.* Also called CR4, four-firm concentration ratio. The combined share of the four largest firms in a market, from 0% to 100%.

**Why it matters here.** It is the project's second measure, computed per cell beside HHI.

**Shows up in.** `docs/integrity_findings_v3.md`

**Source.** This is a project definition.

**Related.** HHI · effective number of firms · cell · vendor.

#### total dollars obligated

*Money.* Also called total_dollars_obligated, total obligated amount. A system total of every row's obligation amount for one contract.

**Why it matters here.** The Emerson award's total, $16,293,527.48, equals the net of all its rows across years, which shows its $13.9 billion entry and reversal cancel out.

**Shows up in.** `total_dollars_obligated`, `docs/integrity_findings_v3.md`

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending data dictionary, API /api/v2/references/data_dictionary/", USAspending data dictionary, element TotalDollarsObligated. The summary paraphrases an official source. Read more at [https://www.usaspending.gov/data-dictionary](https://www.usaspending.gov/data-dictionary).

**Related.** federal action obligation · Emerson pair · current total value of award.

#### transaction

*Award structure.* Also called prime award transaction, row. One reported action on an award, either the original award or a later change. Each row in our files is one transaction.

**Why it matters here.** Our 88,753,968 rows are transactions. Counting rows counts actions, which is why small orders can move row counts without moving dollars.

**Shows up in.** `contract_transaction_unique_key`, `docs/integrity_findings_v3.md`

> A transaction can be the initial contract, grant, loan, or insurance award or any amendment or modification to that award.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, term 'Transaction'. This is an official definition. Read more at [https://www.usaspending.gov/?glossary=transaction](https://www.usaspending.gov/?glossary=transaction).

**Related.** award · modification · contract action · transaction key.

#### transaction key

*Award structure.* Also called contract_transaction_unique_key, ContractTransactionUniqueKey. USAspending's ID for one transaction row, built from the agency, PIID, modification number, parent IDV and transaction number.

**Why it matters here.** Flags B01 to B03 test that it is present and unique within and across fiscal years.

**Shows up in.** `contract_transaction_unique_key`, `config/flag_catalog.csv` (B01 to B03)

> Derived element and system-generated database key used to uniquely identify each contract transaction record and facilitate record lookup, correction, and deletion.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending data dictionary, API /api/v2/references/data_dictionary/", USAspending data dictionary, element ContractTransactionUniqueKey. This is an official definition. Read more at [https://www.usaspending.gov/data-dictionary](https://www.usaspending.gov/data-dictionary).

**Related.** unique award key · transaction · modification.

#### Treasury Account Symbol

*Data systems and files.* Also called TAS, Treasury account. The code Treasury and OMB give each federal account that money flows through, much like a bank account number.

**Why it matters here.** treasury_accounts_funding_this_award lists the accounts that paid for an award, which can help trace which programs fund a cell.

**Shows up in.** `treasury_accounts_funding_this_award`

> The account identification codes assigned by the Department of the Treasury to individual appropriation, receipt, or other fund accounts.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, term 'Treasury Account Symbol (TAS)', official text. This is an official definition. Read more at [https://www.usaspending.gov/?glossary=treasury-account-symbol-tas](https://www.usaspending.gov/?glossary=treasury-account-symbol-tas).

**Related.** federal account · appropriation · File A · GTAS · CGAC.

### U

#### UEI

*Identifiers.* Also called Unique Entity ID, Unique Entity Identifier, SAM UEI, recipient_uei. The 12-character ID that SAM.gov gives each registered entity. It replaced DUNS in April 2022.

**Why it matters here.** recipient_uei is never blank back to FY2008, because USAspending filled in UEIs for older rows after the switch.

**Shows up in.** `recipient_uei`, `recipient_parent_uei`, `config/flag_catalog.csv` (F03), `docs/integrity_findings_v3.md`

> Unique entity identifier means a number or other identifier used to identify a specific commercial, nonprofit, or Government entity.

**Source.** FAR Council (GSA, DoD, NASA), acquisition.gov, "FAR 2.101 Definitions", FAR 2.101(b), definition of unique entity identifier. This is an official definition. Read more at [https://sam.gov](https://sam.gov).

**Related.** DUNS · parent UEI · SAM.gov · CAGE code.

#### ultimate parent

*Identifiers.* Also called highest-level owner, parent company, parent recipient. The top company in a corporate family, the one that no other entity owns or controls. Grouping by ultimate parent counts a company's subsidiaries as one vendor.

**Why it matters here.** Concentration depends on whether subsidiaries count as one vendor. We use the parent recorded at the time of each action.

**Shows up in.** `recipient_parent_uei`, `recipient_parent_name`, `recipient_parent_name_raw`, `docs/integrity_findings_v3.md`

> The recipient_parent data elements reference the ultimate parent of an awardee or recipient and can be used to group together related recipients.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "Analyst's Guide to Federal Spending Data (PDF)", Analyst's Guide, Recipient data elements, p. 17 (PDF p. 17). This is an official definition. Read more at [https://www.acquisition.gov/far/subpart-4.18](https://www.acquisition.gov/far/subpart-4.18).

**Related.** parent UEI · parent DUNS · vendor · parent test.

#### unique award key

*Award structure.* Also called contract_award_unique_key, award key, PrimeAwardUniqueKey. USAspending's ID for a whole award, built from the PIID, the reporting agency and the parent IDV. It starts with CONT_AWD_ for contracts and orders and CONT_IDV_ for IDVs.

**Why it matters here.** Our award-level checks, such as flags B05, B06 and J03, group rows by this key.

**Shows up in.** `contract_award_unique_key`, `config/flag_catalog.csv` (B05, B06, J03)

> Derived unique record key used by the Broker to identify the prime award.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending data dictionary, API /api/v2/references/data_dictionary/", USAspending data dictionary, element PrimeAwardUniqueKey. This is an official definition. Read more at [https://www.usaspending.gov/data-dictionary](https://www.usaspending.gov/data-dictionary).

**Related.** PIID · transaction key · award · referenced IDV.

#### unlinked award

*Data systems and files.* An award that appears in agency account data (File C) or in award data (File D1 or D2), but not both, because the two lack a shared award ID.

**Why it matters here.** Unlinked contracts still appear in our files. They lack the account columns that File C supplies.

**Shows up in.** `treasury_accounts_funding_this_award` (blank on unlinked awards)

> Unlinked awards lack a shared award ID that allows a match between financial system data and award reporting data.

**Source.** Treasury, Bureau of the Fiscal Service (USAspending.gov), "USAspending glossary, API /api/v2/references/glossary/ (151 terms)", USAspending glossary, term 'Unlinked Award'. This is an official definition. Read more at [https://www.usaspending.gov/?glossary=unlinked-award](https://www.usaspending.gov/?glossary=unlinked-award).

**Related.** File C · File D1 · Treasury Account Symbol.

#### unusual and compelling urgency

*Competition and socioeconomic.* Also called urgency exception. An exception that lets an agency limit competition when waiting would seriously harm the government. Such awards may be reported to FPDS up to 30 days late.

**Why it matters here.** GAO found this exception miscoded in 28 of 62 sampled contracts, so the recorded reason for limited competition is unreliable.

**Shows up in.** `other_than_full_and_open_competition_code`, `docs/research/government_documented_gaps_v3.md`

> When the agency's need for the supplies or services is of such an unusual and compelling urgency that the Government would be seriously injured unless the agency is permitted to limit the number of sources from which it solicits bids or proposals, full and open competition need not be provided for.

**Source.** FAR Council, acquisition.gov, "FAR 6.302-2 Unusual and compelling urgency", FAR 6.302-2(a)(2). This is an official definition. Read more at [https://www.acquisition.gov/far/6.302-2](https://www.acquisition.gov/far/6.302-2).

**Related.** other than full and open competition · full and open competition · not competed.

#### US Mint rows

*Our pipeline.* Also called TMHQ10C0040, TMHQ10C0044. Two gold bullion contract vehicles from May 2010 that each record a $10 billion obligation on the vehicle record. The orders placed under them carry their own obligations.

**Why it matters here.** Counting the vehicle rows and the orders may double count. The proposal keeps both rows out of HHI until a source confirms them.

**Shows up in.** `docs/integrity_findings_v3.md`, `config/decisions.csv` (D0025)

**Source.** This is a project definition.

**Related.** IDV · BOA · base and all options value · delivery order.

#### USAspending.gov

*Data systems and files.* Also called USAspending. The official public website for federal spending data. It shows contract data copied from FPDS, along with grants and agency account data. Treasury runs it.

**Why it matters here.** All of our data comes from USAspending's Award Data Archive, so its rules for building files shape our data.

**Shows up in.** `data/manifest.csv` (source_url), `docs/source_choice.md`, `docs/data_stages.md` (Stage 0)

> Since 2007, USAspending.gov has reported information on federal awards (contracts, grants, loans, and other awards) as required by FFATA.

**Source.** GAO, "DATA Act: OMB, Treasury, and Agencies Need to Improve Completeness and Accuracy of Spending Data and Disclose Limitations", p. 2 (PDF p. 7). This is an official definition. Read more at [https://www.usaspending.gov](https://www.usaspending.gov).

**Related.** Award Data Archive · FFATA · DATA Act · FPDS · File D1 · DATA Act Broker.

### V

#### vendor

*Our pipeline.* In our measure, the parent UEI on a row, or the recipient UEI where the parent is blank. Rows with both blank form one vendor.

**Why it matters here.** Vendor shares feed HHI and CR4, so the vendor rule decides whether subsidiaries count together.

**Shows up in.** `docs/integrity_findings_v3.md`

**Source.** This is a project definition.

**Related.** parent UEI · UEI · vendor-cell · ultimate parent.

#### vendor share

*Our pipeline.* Also called market share, share of cell. A vendor's net dollars in a cell divided by the cell's net dollars. In version 2 illustrations, shares use vendors with a positive net only.

**Why it matters here.** HHI and CR4 are built from vendor shares, and shares of a negative cell total have no meaning.

**Shows up in.** `docs/integrity_findings_v3.md`

**Source.** This is a project definition.

**Related.** vendor-cell · HHI · top-4 share · negative vendor total.

#### vendor-cell

*Our pipeline.* One vendor's rows within one cell, summed to a net total.

**Why it matters here.** Vendor-cells are the units whose shares make up HHI. There are 7,847,575 of them.

**Shows up in.** `docs/integrity_findings_v3.md`

**Source.** This is a project definition.

**Related.** cell · vendor · negative vendor total · net dollars.

#### verification and validation

*Data systems and files.* Also called V&V, data verification and validation. Checks in which an agency samples its own FPDS records and compares them with the contract files. OMB has required them since 2007. The reviewer must not be the person who awarded the contract.

**Why it matters here.** Agency V&V results are the main government measure of FPDS field accuracy, the fields our measure relies on.

**Shows up in.** `docs/research/government_documented_gaps_v3.md`

> Establish an agency-wide requirement for routine, statistically-valid data verification and validation. The verification and validation must be conducted by an organization or person that did not award the contracts being reviewed.

**Source.** OMB, Office of Federal Procurement Policy, "Federal Procurement Data Verification and Validation (memorandum)", OFPP memorandum of March 9, 2007, p. 1 (PDF p. 1). This is an official definition. Read more at [https://obamawhitehouse.archives.gov/sites/default/files/omb/assets/omb/procurement/pro_data/fpds_030907.pdf](https://obamawhitehouse.archives.gov/sites/default/files/omb/assets/omb/procurement/pro_data/fpds_030907.pdf).

**Related.** data quality certification · FPDS · OMB.

### W

#### WOSB

*Competition and socioeconomic.* Also called women-owned small business, EDWOSB. A small business at least 51% owned and run by women.

**Why it matters here.** WOSB set-asides limit who can bid, which can shape concentration in a cell.

**Shows up in.** `type_of_set_aside_code`

> That is at least 51 percent owned by one or more women

**Source.** FAR Council (GSA, DoD, NASA), acquisition.gov, "FAR 2.101 Definitions", FAR 2.101(b), definition of women-owned small business concern, paragraph (1)(i). This is an official definition. Read more at [https://www.acquisition.gov/far/2.101](https://www.acquisition.gov/far/2.101).

**Related.** set-aside · small business concern · NAICS.

## Appendix. Flag codes

Every check in the flag catalog, with its one-line meaning. This list is generated from the catalog.

| Code | Meaning | Severity | Level |
|---|---|---|---|
| A01 | Release date differs | serious | year |
| A02 | Member file date inconsistent with zip date | review | year |
| A03 | Header differs from FY2025 | serious | year |
| A04 | Malformed records | serious | year |
| A05 | Blank lines in a member | info | year |
| B01 | Transaction key blank | serious | row |
| B02 | Transaction key repeated within the year | serious | row |
| B03 | Transaction key in more than one fiscal year | serious | row |
| B04 | Exact duplicate row | serious | row |
| B05 | Award spans several fiscal years | info | award |
| B06 | Award key prefix disagrees with award/IDV flag | review | row |
| C01 | Action date outside its file's fiscal year | serious | row |
| C02 | Fiscal year column disagrees with the file | serious | row |
| C03 | Action date missing or invalid | serious | row |
| C04 | Other date unparseable | review | row |
| C05 | Implausible date | review | row |
| C06 | Performance period starts after it ends | review | row |
| C07 | Reported more than 90 days after the action | info | row |
| C08 | Reported before the action date | review | row |
| C09 | Action date after the release date | serious | row |
| C10 | Last modified before the action date | review | row |
| D01 | Obligation blank | review | row |
| D02 | Obligation unparseable | serious | row |
| D03 | Obligation with more than 2 decimal places | review | row |
| D04 | IDV row carries dollars | info | row |
| E01 | Placeholder vendor | review | row |
| E02 | Placeholder ID | review | row |
| E03 | Placeholder-looking values (profile) | info | column |
| E04 | Leading/trailing whitespace and case variants (profile) | info | column |
| E05 | Blank share (profile) | info | column |
| F01 | PSC not 4 characters | review | row |
| F02 | NAICS not 6 digits | review | row |
| F03 | UEI not 12 characters | review | row |
| F04 | DUNS not 9 digits | review | row |
| F05 | Agency code not 3 characters | info | row |
| F06 | Sub-agency code not 4 characters | review | row |
| F07 | Code with more than one label in a year | review | code |
| F08 | Code whose label changes across years | info | code |
| F09 | Offers received not a whole number | review | row |
| F10 | Agency under both a 3- and a 4-character code | review | agency |
| G01 | Order without a parent award | review | row |
| G02 | Definitive contract or purchase order with a parent award | review | row |
| G03 | Code and label disagree on presence | review | row |
| G04 | Recipient UEI with many names in one year | review | entity |
| G05 | Parent UEI with many parent names in one year | review | entity |
| H01 | Thin month (rows) | review | year_month |
| H02 | Thin month (dollars) | review | year_month |
| H03 | Agency missing in a middle year | review | agency_year |
| H04 | Agency drop that recovers (dollars) | review | agency_year |
| H05 | Agency drop that recovers (rows) | review | agency_year |
| H06 | Sub-agency missing in a middle year | review | subagency_year |
| H07 | Sub-agency drop that recovers (dollars) | review | subagency_year |
| H08 | Sub-agency drop that recovers (rows) | review | subagency_year |
| H09 | ID and analysis-field coverage (profile) | info | year |
| I01 | Gap to published total: WARN | review | year |
| I02 | Gap to published total: FAIL | serious | year |
| J01 | Top 100 by absolute amount | info | row |
| J02 | Transaction of $1 billion or more | review | row |
| J03 | Deobligation larger than the award's obligations that year | review | row |
| J04 | Amount far from its peers | review | row |
| X01 | Whitespace around a key or code | review | row |
| X02 | Zero offers on a competed action | review | row |
