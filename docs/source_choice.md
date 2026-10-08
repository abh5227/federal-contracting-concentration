# Which source to use for contract transactions

This explains which USAspending source the project should load contract transactions from, and why. Each part starts in plain language. The evidence follows, in enough detail to check every number. The full comparison is in `reports/archive_vs_custom_export_q1fy2025.md` (machine-readable: `.json`).

## In plain language

**Use the Award Data Archive files** (the yearly "All Contracts Full" zips, e.g. `FY2025_All_Contracts_Full_20260906.zip`), as the pilot already does.

**Why we checked.** USAspending offers three ways to get the same data:
- the **archive**: a ready-made yearly snapshot;
- a **custom download**: you choose the dates and filters, and USAspending builds a file for you;
- the **search API**: you page through results 100 rows at a time.

The worry was that the archive might quietly leave out rows or columns that a custom download includes.

**What we did.**
- We asked USAspending for a custom download of the same data for one quarter: October–December 2024 (Q1 FY2025), all agencies, all 12 contract and IDV award types, every column.
- We compared it with the archive's rows for the same quarter.
- We matched rows one by one on the transaction key and compared all 297 columns on every matched row.

**What we found: the archive is complete relative to the custom download.**

- **Columns:** both have the same 297 columns, in the same order.
- **Rows:** of about 1.43 million rows, 1,427,484 are in both.
  - **73 rows are only in the custom download.** Every one was last changed *after* the archive's date (between 8 and 29 September 2026). These are changes made after the archive snapshot, not something the archive missed.
  - **50 rows are only in the archive.**
    - **44 of them pair one-for-one with a row in the custom download.** The pair has the same agency, award type, modification, date, amount and recipient, but a new contract number or contracting-agency code. That points strongly to the same actions moved to a new record, though it isn't proof.
    - The new copies are among the 73 rows above, and every one was changed after the archive's date.
    - When we asked USAspending's live API about a sample of 20, the old record was gone in every case.
  - The remaining 6 are all from the Defense Department, and one order accounts for 5 of them. That order's total is unchanged: the money on the removed rows now sits on another line of the same order.
- **Dollars:** the two totals differ by $1.5 million out of $159.4 billion (0.001%). That gap is entirely explained by the rows above plus 12 amounts that were revised after the archive's date.
- **Values:** on rows in both, **89% are identical in every column.**
  - Nearly all other differences are things USAspending refreshes on its own, from lookup tables, without marking the transaction as changed.
  - By far the biggest is the **parent company's name**, which changed on 130,264 rows.
  - The parent company's **ID number (UEI)** did not change on any of those rows. What changed is the name USAspending attaches to that ID.
    - About one in nine of these changes is punctuation or capitalisation.
    - The rest are real changes, and some now name a different company:
      - AmerisourceBergen became "CENCORA GLOBAL CONSULTING SERVICES US CORP" on 108,009 rows;
      - Honeywell Safety Products became PIP Manufacturing;
      - Novetta became Accenture.

**Why not the search API.**
- It can't return 17 of the 32 columns the project uses, including every parent-company column and the competition and set-aside codes.
- It stops at 50,000 rows per query, 100 rows per page.

**Two cautions for the team.**

1. **Group companies by parent UEI, not parent name.**
   - The parent UEI comes from the contract record and was stable here.
   - The parent name is looked up from the current reference data each time USAspending builds a file. So the same ID can carry a different name, sometimes a different company's name, from one snapshot to the next.
   - Whether concentration should credit the parent at the time of the action or the parent today is a team decision. Names can't answer it reliably.
2. **Every file is a snapshot.** The archive shows the data as of its date. A later download will differ a little, by records changed or moved since. So record which file every number came from.

**What this does not prove.** We compared **one quarter of one year (FY2025)**. It shows the archive and the custom download agree for that quarter. It doesn't prove the same for other quarters, other years, or later archive files, although they are built by the same USAspending code.

---

## Evidence

### 1. What was compared

| | Archive | Custom download |
|---|---|---|
| File | `FY2025_All_Contracts_Full_20260906.zip` (pilot Layer A, text) | 3 zips from `POST /api/v2/bulk_download/awards/`, one per month |
| Data as of | file name 2026-09-06; newest `last_modified_date` 2026-09-04 23:49:58 UTC | requested 2026-10-02 05:27 UTC; newest `last_modified_date` 2026-09-29 21:58:31 UTC |
| Scope | rows with `action_date` 2024-10-01..2024-12-31 | `date_type: action_date`, same dates; all agencies; award types A, B, C, D, IDV_A, IDV_B, IDV_B_A, IDV_B_B, IDV_B_C, IDV_C, IDV_D, IDV_E; `columns: []` |
| Rows | 1,427,534 | 1,427,557 |
| Net obligations | $159,429,188,384.53 | $159,427,653,194.74 |

**How the request was built.**
- **All agencies:** the request lists one agency named `"All"`. The published contract (`bulk_download/awards.md`) doesn't document an "all" option. But the validator (`download/v2/request_validations.py`, `_update_custom_award_agencies`) drops any agency named "All", which leaves no agency filter. The server echoed back `"agencies": []`.
- **Award types:** the 12 types are the procurement types the archive holds. The archive's `award_type_code` is A–D for contracts. Its IDV type B is split by `type_of_idc` into USAspending's IDV_B and IDV_B_A/B/C.

**How it was downloaded.**
- **The first request failed.** It asked for the whole quarter as one file (2026-10-02 04:29 UTC) and failed on the server after 55 minutes with only "An error occurred." The custom-download path has no row limit in the code; the 500,000 limit applies only to Advanced Search downloads.
- **The quarter was re-requested as three calendar months** with otherwise identical filters. The months are contiguous, so together they cover exactly the quarter.
- **Loading checks:**
  - every row sits inside its own month;
  - no key appears twice across the three files;
  - each file's row count and Decimal sum, read independently with Python `csv`, matches the text Parquet.
  - All checks passed: 507,626 + 462,678 + 457,253 = 1,427,557 rows.
- **One download was resumed.** A connection stalled partway through one file, and the download was resumed with an HTTP range request. Each zip's SHA-256 is in `data/raw/comparison/request_log.json` and `data/manifest.csv`, where the rows are marked as comparison files, not pipeline inputs. The zip CRCs were checked when the files were read.

**How rows were compared.** Rows were matched on `contract_transaction_unique_key`, which is unique and non-blank on both sides. All 297 columns were compared as the original CSV text on every matched row: no sampling, no hashing.

### 2. Columns

297 in each file, identical names in identical order. Nothing is only in the custom download, and nothing is only in the archive.

### 3. Rows

**The verdict rules were written before the download:**
- "Gaps found" means a column only in the custom download, or a custom-only row last modified on or before 2026-09-06.
- "Inconclusive" means the comparison couldn't cover the full scope.

Neither condition occurred.

**Two integrity guards were added after the independent review.** Both can only make the verdict stricter, and both pass:
- no obligation has more than 2 decimal places, so summing as DECIMAL(38,2) rounds nothing;
- the cached archive Q1 extract still has the same row count as a fresh filter of Layer A.

**Where the $1,535,189.79 gap comes from.** It adds back exactly:

| Part | Rows | Net obligations |
|---|---|---|
| Rows only in the custom download | 73 | $15,391,773.05 |
| minus rows only in the archive | 50 | −$15,666,369.72 |
| plus revised amounts on rows in both | 12 | −$1,260,593.12 |
| **= custom − archive** | **+23** | **−$1,535,189.79** |

**Rows only in the custom download: 73, $15,391,773.05.**
- **Timing (modified after 2026-09-06):** 73, $15,391,773.05. They were last modified between 2026-09-08 and 2026-09-29.
- **Unexplained (modified on or before 2026-09-06): 0.**

**Rows only in the archive: 50, $15,666,369.72.**

These rows have no custom-side `last_modified_date` to check, so the evidence comes from three tests.

1. **Strict re-key test:** same award key, modification number and transaction number, but a different transaction key. Result: 0.
2. **Same-action test:** same `awarding_agency_name`, `award_type_code`, `idv_type_code`, `modification_number`, `action_date`, `federal_action_obligation` and `recipient_uei`; one-to-one pairs only.
   - This test was added after looking at the one-sided rows. It is evidence only and changes no count.
   - **44 of 50 rows pair, $14,564,735.81.**
     - In 29 pairs the PIID itself changed. For example, Treasury IDVs `20343125D…` now appear as `140D0426D…` under agency ID 1406. HUD's `86614924A…` now appear as GSA's `47QACA26A…`. OPM's $13,949,992.60 action on 2024-12-31 moved from `24322625C0002` to `47QACA26C0044`.
     - In 15 pairs only the parent award changed.
   - **Every custom-side (new-key) row in a pair was last modified after 2026-09-06.**
   - Per agency, Treasury, HUD, OPM and Interior net to zero rows and $0.
3. **Live API, 20 sampled archive-only rows** (`compare/api_evidence.py`): the 10 largest by amount plus 10 chosen by `md5(key)`.
   - **19:** the award no longer exists under its old key (HTTP 404 from `GET /api/v2/awards/<key>/`).
   - **1:** the award still exists, but that modification is now listed under a different transaction key. This is DoD order `FA872124F0004`.
   - **Control:** two rows present in both files were looked up the same way, and both were found under their own keys, so the key check works.
   - The API shows today's data, so this is evidence, not proof of what happened when.

**Rows left without a pair: 6, $1,101,633.91, all DoD.**
- **5 are transaction number 14 of order `FA872124F0004`,** for mods P00009, P00010, P00012, P00013 and P00014. (P00011's transaction 14 is still in both files.)
  - **The order's Q1 total is the same in both files:** $21,365,234.40.
  - The $1,101,633.91 on the removed P00014 transaction-14 row now sits on P00014 transaction 16, which went from $2,536,027.24 to $3,637,661.15. The other four removed rows were $0.
  - The order's 13 remaining Q1 rows in the custom download were last modified on 2026-09-25 (4) or 2026-09-28 (9).
  - So this looks like a consolidation of the order's lines after the archive's date. The live API agrees: P00014 is now listed under a different transaction key.
- **1 is a $0 modification of `N0010425PUA29`** (archive `last_modified_date` 2026-08-20), with no further evidence either way.

**Rows in both: 1,427,484.**
- 1,273,046 (89.2%) are identical in all 297 columns.
- 154,438 differ in at least one column:

| Bucket (by the custom row's `last_modified_date`) | Rows | Meaning |
|---|---|---|
| Timing: modified after 2026-09-06 | 5,323 | changed after the archive's date |
| Modified 2026-09-05 or 06, after the archive's newest record | 62 | the archive was cut about a day before its file-name date; strictly "unexplained" under the rule |
| `last_modified_date` unchanged | 149,053 | values changed without the transaction being marked modified |

**All 12 revised `federal_action_obligation` values are timing rows.**

**What changed in the 149,053 rows where `last_modified_date` is unchanged.** In columns the project uses, almost all of it is names that USAspending fills in from reference tables:

| Column | Rows | What changed |
|---|---|---|
| `recipient_parent_name` | 130,264 | **The name attached to an unchanged `recipient_parent_uei`.** 14,719 rows are punctuation or capitalisation only. 115,545 rows, across 303 parent UEIs, carry a different name, often a renamed or acquiring company. The source sets the column as `UPPER(parent_recipient.parent_recipient_name)`, a reference-table name (`search/delta_models/dataframes/transaction_search.py`). The as-reported FPDS value, `recipient_parent_name_raw`, has **0** changes in this bucket. The parent UEI changed on only 14 rows overall, all of them timing. |
| `recipient_name` | 1,137 | It takes the recipient-lookup (SAM) legal name first, falling back to FPDS (same source). `recipient_name_raw`: 0 unexplained changes. |
| `funding_office_name` / `awarding_office_name` | 246 / 59 | Office reference names, e.g. `LIBRARY STAFF (JMD)` became `DOJ LIBRARY STAFF (JMD)`. The office codes are unchanged. |
| Award-level and derived amounts (`total_outlayed_amount_for_overall_award`, IIJA/COVID amounts, etc.) | up to 18,571 | Whole-award figures refreshed from account data, not transaction fields. |
| Location (`recipient_country_code`/`state`, place of performance) | 6 / 52 | The Marshall Islands, Micronesia and Palau were recoded from `USA` + state `MH`/`FM`/`PW` to countries `MHL`/`FSM`/`PLW`. Not used by the project. |

**The 62 rows modified on 2026-09-05 or 06** differ in:
- `last_modified_date` itself (62);
- award-level value columns (up to 13);
- executive compensation (6);
- `recipient_parent_name` (3).

**No differences outside the timing buckets** in any transaction field the project uses:
- PSC, NAICS, recipient or parent UEI, agency or sub-agency codes;
- competition, set-aside and pricing codes;
- action date and obligation.

The full per-column table is in the report.

**By awarding agency:** 68 agencies.
- **57 have the same row count and net total in both files.**
  - That includes Treasury, HUD, OPM and Interior, whose 44 paired rows stayed within the same agency.
- **11 have a gap.**
  - For 10 of them the gap is entirely rows added, or amounts revised, after the archive's date.
  - The Department of Defense's gap (+9 rows, −$2,070,156.29) also includes the 6 unpaired archive-only rows: $487,712.07 in custom-only rows, minus $1,101,633.91 in unpaired rows, minus $1,456,234.45 in revised amounts.

### 4. The search API: what it can and can't give us

Everything here comes from documentation and source code only; no search request was sent.

**Where it was read.** The API contracts and code were read from the `fedspendingtransparency/usaspending-api` repository on GitHub (`master`, fetched 2026-10-02). That includes `api_contracts/contracts/v2/search/spending_by_transaction.md`, `spending_by_award.md`, `search_filters.md`, `bulk_download/awards.md`, `settings.py`, and the search and download views and validators. These documents are not served from api.usaspending.gov itself.

#### 4.1 Columns: 17 of our 32 Layer B columns are not available

`spending_by_transaction` is the only search endpoint at our grain (one row per transaction). Of the 32 Layer B data columns:
- **12** are returned directly;
- **1** can be derived (`action_date_fiscal_year`);
- **2** come back as descriptions only (`award_type_code`, `idv_type_code`);
- **17 are not returned at all.**

| Layer B column | `spending_by_transaction` | `spending_by_award` | Project use |
|---|---|---|---|
| contract_transaction_unique_key | **no** (in the index, never returned) | no | join key |
| contract_award_unique_key | yes (`generated_internal_id`) | yes | award key |
| award_id_piid | yes (`Award ID`) | yes | award key |
| modification_number | yes (`Mod`) | no | transaction |
| transaction_number | **no** (not in the index) | no | transaction |
| parent_award_id_piid | **no** (only inside the award-key string) | no | award-key option |
| parent_award_agency_id | **no** (same) | no | award-key option |
| federal_action_obligation | yes (`Transaction Amount`) | no (award totals only) | dollars |
| action_date | yes | no | dates |
| action_date_fiscal_year | derivable | no | dates |
| awarding_agency_code | **no** (name only; `awarding_agency_id` is an internal key) | yes | agency |
| awarding_agency_name | yes | yes | agency |
| awarding_sub_agency_code | **no** (name only) | yes | agency |
| awarding_sub_agency_name | yes | yes | agency |
| funding_agency_code | **no** (name only) | yes | agency |
| recipient_uei | yes | yes | vendor |
| recipient_duns | **no** | yes | vendor |
| recipient_name | yes | yes | vendor |
| recipient_parent_uei | **no** | no | parent company |
| recipient_parent_duns | **no** | no | parent company |
| recipient_parent_name | **no** | no | parent company |
| product_or_service_code | yes (`PSC.code`) | yes | product code |
| product_or_service_code_description | yes | yes (reference-table text) | product code |
| naics_code | yes (`NAICS.code`) | yes | product code |
| extent_competed_code | **no** (filter only) | no | competition |
| number_of_offers_received | **no** | no | competition |
| type_of_set_aside_code | **no** (filter only) | no | set-aside |
| type_of_contract_pricing_code | **no** (filter only) | no | competition |
| award_type_code | description only | description only | award type |
| award_or_idv_flag | **no** (implied by the type codes requested) | no | award type |
| idv_type_code | description only | description only | award type |
| parent_award_type_code | **no** | no | award type |

**Some missing codes exist only as request filters:** `extent_competed_type_codes`, `set_aside_type_codes` and `contract_pricing_type_codes`. A code could in principle be recovered by sending one request per code value. That multiplies the requests, still hits the cap below, and can't recover the parent-company columns at all.

`spending_by_award` is award-level. It has no modification number, transaction amount or action date, so it can't replace transaction data.

#### 4.2 The row cap: 50,000 confirmed for transactions, with a correction for awards

- **`spending_by_transaction`: 50,000 rows per filter set. Confirmed, with no way around it.**
  - The view rejects any page that would start at or past `ES_TRANSACTIONS_MAX_RESULT_WINDOW = 50000` (`settings.py`).
  - It returns HTTP 422: "Page #… of size … is over the maximum result limit (50000). Consider using custom data downloads to obtain large data sets." (`search/v2/views/spending_by_transaction.py`)
  - There is no cursor parameter.
  - **Possibly 49,900 in practice (unverified inference).** The view asks for one extra row to set `hasNext`, so the last page may fail and leave 49,900 reachable.
- **`spending_by_award`: 50,000 applies only to page-number paging.**
  - When both `last_record_sort_value` and `last_record_unique_id` are sent, the view uses `search_after` and can page past 50,000 (`search/v2/views/spending_by_award.py`).
  - The contract calls these fields "experimental" and doesn't say they bypass the cap.
- **Page size: at most 100 rows** (`common/validator/pagination.py`).
- **Neither cap is stated in the published API contracts.** Both come from settings and view code, so they could change without notice.
- **Scale, as arithmetic rather than a measurement:**
  - Q1 FY2025 alone is 1,427,534 transactions.
  - Paging them would take at least 14,276 requests, spread over at least 29 filter slices, each kept under 50,000 rows.
  - The transaction sort has no unique tiebreaker. So offset paging can repeat or skip rows that tie on the sort value, and each slice would need its own check.

**Other limits that matter for bulk use:**
- **Award search returns overlapping awards, not actions in the period.** By default it matches awards whose latest action is on or after the start date and whose base award was signed on or before the end date (`search_filters.md`). The same award comes back in every period it overlaps.
- **Agencies are filtered by name, not code.**
- **`spending_by_award` needs contracts and IDVs in separate requests** ("must only contain types from one group").

### 5. The snapshot caveat

**Every source is a snapshot of a live database.**
- The archive file is named 2026-09-06, but its newest record is from 2026-09-04 23:49:58 UTC.
- The custom download reflected data up to 2026-09-29.
- In those few weeks, about 0.4% of Q1 rows changed:
  - 5,323 matched rows were modified;
  - 73 rows appeared;
  - 50 disappeared, most of them moved to new keys.
- Reference names (parent company, recipient, office) were refreshed on even more rows without any change to `last_modified_date`.

**So any rerun from a newer file will differ slightly.** The project should:
1. record the exact file (name and SHA-256) behind every number, as `data/manifest.csv` does;
2. use stable identifiers (UEI, parent UEI, codes), not names, for grouping;
3. expect moved records. A contract can change PIID or contracting agency between snapshots, so award-level counts can shift even when dollars don't.

### 6. What this does not prove

- **One quarter of one year.** Q1 FY2025 only. Other quarters, other fiscal years, and archive files generated on other dates were not compared. They are produced by the same USAspending code, which makes a difference unlikely, but this comparison doesn't show it.
- **Timing is inferred from `last_modified_date`.** USAspending keeps no history of deletions, so we can't see when the 50 archive-only rows disappeared. The same-action test and the API lookups are strong evidence of moved records, not proof.
- **The 62 rows modified on 2026-09-05/06** are counted as "unexplained" under the rule fixed beforehand, because they fall on or before the archive's file-name date. They are value changes on rows present in both files, not missing rows, so they don't affect the verdict.
- **The search API section rests on documents and code read on 2026-10-02.** No search request was made, and the deployed service could behave differently.

### 7. How to reproduce

```
.venv/bin/python -m compare.custom_export request    # three monthly requests, logged
.venv/bin/python -m compare.custom_export wait
.venv/bin/python -m compare.custom_export download   # refuses any file over 3 GB
.venv/bin/python -m compare.load_export              # text Parquet + independent row/Decimal checks
.venv/bin/python -m compare.api_evidence             # optional live-API lookups (today's data)
.venv/bin/python -m compare.compare_q1               # writes reports/archive_vs_custom_export_q1fy2025.{md,json}
```

**Where these steps write:**
- `data/raw/comparison/` (the zips and `request_log.json`);
- `data/comparison/` (text Parquet, the load summary, the archive's Q1 extract, the API evidence; rejected rows would go to `data/comparison/rejects/`, and there were none);
- three appended rows in `data/manifest.csv`, each marked `registered_via=comparison` and "not a pipeline input";
- temporary files in `data/scratch/` (each extracted CSV is deleted after loading; DuckDB spill files);
- the two new report files.

**The pilot's `data/parquet/`, `src/`, `data/audit/` and existing reports are only read.** A new request returns a newer snapshot, so its numbers will differ from the ones above.
