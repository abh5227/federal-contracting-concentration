# The decision log

`config/decisions.csv` records every data decision the team proposes or makes, one row per entry. The dashboard reads it and writes to it when someone saves a decision. A rebuild of the stages adds a routine entry for any flag that fires for the first time and never changes an existing row.

## The columns

| Column | What it holds |
|---|---|
| `decision_id` | D and four digits, given in order |
| `target_type` | flag, column or value pattern |
| `target` | The flag ID, the column name or a description of the rows |
| `scope` | The years or rows the entry covers |
| `status` | proposed, keep as is, clean (rule), exclude from analysis (with ledger) or investigate |
| `rationale` | The proposal or the decision, with its evidence |
| `decided_by` | Who decided, or "(not yet decided)" |
| `decided_date` | The date of the decision, blank until then |
| `created_utc`, `updated_utc` | The time the entry was created and the time it last changed, in UTC |

## Three groups of entries

**The nine main decisions, D0024 to D0032.** These are the nine decisions in integrity report version 3 (`docs/integrity_findings_v3.md`), in its numbered order. All nine are proposed, and none is decided yet.

| Entry | Decision in integrity report version 3 |
|---|---|
| D0024 | 1. Reversal pairs |
| D0025 | 2. The two $10 billion US Mint rows |
| D0026 | 3. The FY2015 step in row counts |
| D0027 | 4. Funding agency code 999 |
| D0028 | 5. Competition measure |
| D0029 | 6. Parent roll-up |
| D0030 | 7. Primary benchmark |
| D0031 | 8. Negative vendor totals |
| D0032 | 9. MISCELLANEOUS FOREIGN AWARDEES |

D0028 was updated on 2026-10-07. The report's table gives FY2011 to FY2017 for the number of offers, but the report's own evidence supports FY2012. FY2011 still has 64,905 competed actions with zero offers, against 14,557 or fewer in each year from FY2012. The entry now proposes FY2012 to FY2017, tentatively, and the team will look for another source to fill the other years.

**Two entries added after the first review, D0033 and D0034.**

- **D0033.** Segments where no vendor has a positive net get no HHI. The proposal is to leave them unscored and report their count and dollars for every year.
- **D0034.** Rows with neither a parent UEI nor an own UEI are pooled as one vendor, "(no ID)", in `src/analyses_v2.py`. The proposal is to leave them out of HHI and report their share of dollars.

**Routine entries, D0001 to D0023.** The dashboard's code creates one for each serious or review flag that fired, so that no flag is forgotten. Each names its flag and the count of rows or items on the day it was created, 2026-10-05. Those counts are never updated, and current counts are in `reports/integrity/flag_counts.csv`. D0020 and D0024 both name flag J02. D0024 is the main decision on the reversal pairs, and D0020 is the routine entry for the same flag.

## Changing an entry

The dashboard's decision form checks each field and records the time of the change. A change made by hand must keep every column in the format above.
