# Vendor concentration in federal contracting, FY2008 to FY2025

**Team.** Suchitra Hole, Shivram Nekkanti and Andy Hannah.

## Project summary

The federal government obligated $793 billion through contracts in FY2025. In defense, a few firms now lead most major weapon programs. US aerospace and defense prime contractors fell from 51 in 1993 to 5 in 2000, and at least one of those five is a prime contractor on 58 of the 78 major weapon systems in DoD's FY2024 budget. Studies that measure concentration directly also stay within defense. The closest one compares DoD with all other agencies combined but measures concentration for only five product categories, over FY2010 to FY2019. We found no measure for the rest of the government, so we build one for every agency, product and year from FY2008 to FY2025. A high score is not evidence of wrongdoing. One shipyard building aircraft carriers can be the sensible arrangement, so we describe where concentration sits and how it changes without claiming causes. The measure also has limits. It counts prime contractors only, and parent company IDs can lag a merger by 2 to 6 months. It also looks at one buyer at a time. A vendor can win most of one agency's purchases of a product and still face many rivals for other buyers, so the antitrust cutoffs for a concentrated market serve only as a rough guide.

We use every federal contract transaction in USAspending's Award Data Archive from FY2008 to FY2025, 88,753,968 rows in all. Each transaction carries a product or service code, a four-character label for what was bought, such as 1510 for fixed-wing aircraft. We group transactions into segments, one for each awarding agency, product code and fiscal year. Within each segment we compute the Herfindahl-Hirschman Index (HHI), the sum of each vendor's squared percentage share of the segment's dollars, which runs from near 0 to 10,000. Take two agencies that each spend $100M on one product across five vendors. Paying $20M to each scores 20² × 5 = 2,000. Paying $80M to one and $5M to each of the others scores 80² + 5² × 4 = 6,500. We score every segment, sort each agency and product's yearly trend into one of a few common shapes and compare the rising ones with the rest. The project asks three questions.

1. Can USAspending records support a trustworthy concentration score?
2. What common paths does concentration follow over time, such as a steady rise, a steady fall or a one-time jump?
3. What do agencies and products that came to rely on a few vendors have in common, such as sole-source awards?

The proposal, with its references, is `docs/proposal/proposal_v9.md` (PDF: `reports/proposal/proposal_v9.pdf`). Its methods notes and citation checks sit beside it, with matching PDFs.

## What is in the repo

| Folder | What it holds |
|---|---|
| `src/` | The pipeline (Stages 0 to 2), the analyses and the PDF builder |
| `tests/` | Tests for Stages 0 to 2. They build small fixture zips in a temporary folder and never touch real data. |
| `viewer/` | The local data-health dashboard and its tests |
| `config/` | Flag rules, the decision log, published benchmarks, the glossary, and the research findings and sources |
| `docs/` | The proposal, the integrity report, the research note, the glossary, and notes on the data stages, the choice of source and the viewer |
| `reports/` | PDFs of those documents, and the summary tables the figures, dashboard and proposal read |
| `tools/` | Builders for the glossary, the research note's appendix and the 297-column guide, and an optional writing-rule checker |
| `data/` | Not in git. The pipeline builds it on your machine. |

## Getting the data

The raw data is 18 zip files, one per fiscal year, from USAspending's Award Data Archive ([usaspending.gov/download_center/award_data_archive](https://www.usaspending.gov/download_center/award_data_archive)). Choose award type Contracts, agency All Agencies, and the Full file for each of FY2008 to FY2025. Our work uses the release of 2026-09-06, with files named `FY2008_All_Contracts_Full_20260906.zip` to `FY2025_All_Contracts_Full_20260906.zip`. The archive regenerates its files every month, so that release may no longer be offered. A later release needs `RELEASE_DATE` changed in `src/config.py`, and its totals will differ slightly from ours.

The code expects the zips in `DATA/raw/award_data_archive/release_2026-09-06/`, in a folder named `DATA` next to the repo (`RAW_ROOT` in `src/config.py`). Set the environment variable `PILOT_RAW_ROOT` to keep them elsewhere. Stage 0 checks each downloaded zip and moves it there for you.

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Stage 0: check every zip in a folder and move it into place, read-only
.venv/bin/python -m src.stage0 organize --source ~/Downloads
# Stage 1: a lossless Parquet copy of every row, checked against the zips
caffeinate -i .venv/bin/python -m src.stage1 build
# Stage 2: flags, profiles, cross-year checks and the summary tables in reports/integrity/
caffeinate -i .venv/bin/python -m src.stage2 all
# or every missing step in order, restartable
caffeinate -i .venv/bin/python -m src.stages refresh
```

`caffeinate -i` keeps a Mac awake during long runs. Leave it out on other systems.

| Stage | Folder | Size | Time on our Mac |
|---|---|---|---|
| 0. Raw zips | `../DATA/raw/award_data_archive/release_2026-09-06/` | 27.1 GB | Download time |
| 1. Parquet copy | `data/parquet/layer_a/` | 19.8 GB | About 1 hour 45 minutes |
| 2. Flags and profiles | `data/integrity/` | 2.1 GB | About 1 hour |

Plan for about 70 GB of free disk. Stage 1 checks for room before it starts. The sizes come from `docs/data_stages.md`, and the times from our build logs of 2026-10-05.

## Opening the dashboard

The dashboard needs Stages 1 and 2. It runs on your machine only, makes no network calls, and writes nothing except the decision log, `config/decisions.csv`.

```bash
.venv/bin/python -m viewer.server        # then open http://127.0.0.1:8765/
```

The tests run the same way.

```bash
.venv/bin/python -m tests.test_stages    # Stages 0 to 2, on fixture zips
.venv/bin/python -m viewer.test_viewer   # dashboard checks and screenshots, needs Stages 1 and 2
```

## Where to start reading

1. **The proposal.** `docs/proposal/proposal_v9.md` (PDF: `reports/proposal/proposal_v9.pdf`). The problem, the plan and the first results.
2. **The integrity report, version 3.** `docs/integrity_findings_v3.md` (PDF: `reports/integrity/integrity_report_v3.pdf`). Whether the data is complete, what would distort the measure, and the nine open team decisions.
3. **The research note, version 3.** `docs/research/government_documented_gaps_v3.md` (PDF: `reports/research/government_documented_gaps_v3.pdf`). What GAO, inspectors general and others have documented about gaps in this data.
4. **The glossary.** `docs/glossary_v3.md` (PDF: `reports/glossary_v3.pdf`). Every term the project uses, with its official definition where one exists.

## What is kept outside this repo

Earlier versions of the reports, the working notes and the code from the FY2025 pilot stay in a private archive outside this repo. Some shared documents mention those files by path, for example `docs/integrity_findings_v2.md`. Those paths do not exist here.

## License

Released under the MIT License, in the `LICENSE` file.
