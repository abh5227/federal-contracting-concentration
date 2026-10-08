"""Settings shared by every pipeline step.

Everything that could change a number (column choices, types, seeds, pass/warn
thresholds, external reference figures) lives here so it can be reviewed in one
place. Thresholds were written down before the FY2025 data was looked at; do
not loosen them to make a check pass (ground rule 2).
"""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (all relative to the repo root, so a fresh clone works anywhere)
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
# Tests point PILOT_OUTPUT_ROOT at a throwaway folder so they never touch the
# real data/ and reports/. Normal runs leave it unset.
OUTPUT_ROOT = Path(os.environ.get("PILOT_OUTPUT_ROOT", REPO_ROOT))
DATA_DIR = OUTPUT_ROOT / "data"
SCRATCH_DIR = DATA_DIR / "scratch"
PARQUET_DIR = DATA_DIR / "parquet"
AUDIT_DIR = DATA_DIR / "audit"          # independent raw-CSV results (contains raw sample rows)
REJECTS_DIR = DATA_DIR / "rejects"      # rows the Parquet writer could not parse, if any
EXTERNAL_DIR = DATA_DIR / "external"    # cached API responses
MANIFEST_PATH = DATA_DIR / "manifest.csv"
REPORTS_DIR = OUTPUT_ROOT / "reports"
DOCS_DIR = REPO_ROOT / "docs"


def layer_a_dir(fiscal_year: int, release: str | None = None) -> Path:
    """Stage 1 (Layer A): one folder per fiscal year AND release, e.g. layer_a/fy2025/20260906/ (review S5),
    so files from two releases of the same year can never sit side by side. `_files.json` in the folder
    lists the members that make up the current Layer A."""
    return PARQUET_DIR / "layer_a" / f"fy{fiscal_year}" / (release or RELEASE_DATE)


def layer_a_legacy_dir(fiscal_year: int) -> Path:
    """The pilot's original flat layout (layer_a/fy2025/*.parquet), before review fix S5."""
    return PARQUET_DIR / "layer_a" / f"fy{fiscal_year}"


# ---------------------------------------------------------------------------
# Stages (docs/data_stages.md)
# ---------------------------------------------------------------------------
# Stage 0: the raw zips exactly as USAspending published them. They live outside
# the repo (Project/DATA), are read-only, and are never committed.
RAW_ROOT = Path(os.environ.get("PILOT_RAW_ROOT", REPO_ROOT.parent / "DATA" / "raw" / "award_data_archive"))
RELEASE_DATE = "20260906"                       # every in-scope year must come from this release
RELEASE_DIR = RAW_ROOT / "release_2026-09-06"
OUT_OF_SCOPE_DIR = RELEASE_DIR / "_out_of_scope"
ARCHIVE_URL_BASE = "https://files.usaspending.gov/award_data_archive/"
FIRST_FY, LAST_FY = 2008, 2025                  # fiscal years in scope
# The header every year is compared with (FY2025's 297 columns, from the pilot).
REFERENCE_COLUMNS_FILE = REPO_ROOT / "reports" / "columns_fy2025.txt"
# Stage 2 (flags, profiles, summaries) - rebuildable from Stage 1 at any time.
INTEGRITY_DIR = DATA_DIR / "integrity"
INTEGRITY_REPORTS_DIR = REPORTS_DIR / "integrity"


def archive_name(fiscal_year: int) -> str:
    return f"FY{fiscal_year}_All_Contracts_Full_{RELEASE_DATE}.zip"


def stage0_zip(fiscal_year: int) -> Path:
    return RELEASE_DIR / archive_name(fiscal_year)


def years_in_scope() -> list[int]:
    return list(range(FIRST_FY, LAST_FY + 1))


def years_present() -> list[int]:
    """In-scope years whose zip is in Stage 0. The others are pending (not yet downloaded)."""
    return [fy for fy in years_in_scope() if stage0_zip(fy).is_file()]


def years_pending() -> list[int]:
    return [fy for fy in years_in_scope() if not stage0_zip(fy).is_file()]


def layer_b_path(fiscal_year: int) -> Path:
    return PARQUET_DIR / "layer_b" / f"fy{fiscal_year}_contracts_layer_b.parquet"


# ---------------------------------------------------------------------------
# CSV reading
# ---------------------------------------------------------------------------
CSV_ENCODING = "utf-8"
# pyarrow reads the CSV in blocks of this many bytes; each block becomes one
# Parquet row group (roughly 60k rows for this file's ~2 KB rows).
ARROW_BLOCK_SIZE = 128 * 1024 * 1024
PARQUET_COMPRESSION = "zstd"

# Name of the money column summed in the reconciliation.
OBLIGATION_COL = "federal_action_obligation"

# Lineage columns the pipeline adds to every Layer A / Layer B row.
LINEAGE_COLS = ("_source_file", "_source_member_idx", "_source_row")

# ---------------------------------------------------------------------------
# Layer B: the working table
# ---------------------------------------------------------------------------
# kind:
#   text    -> VARCHAR, empty string becomes NULL, nothing else changes
#              (codes and IDs stay text so leading zeros survive)
#   decimal -> DECIMAL(18,2); only values matching ^-?[0-9]+(\.[0-9]{1,2})?$ are cast
#   date    -> DATE; only values matching ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ are cast
#   int     -> INTEGER; only values matching ^-?[0-9]+$ are cast
# requested: True if the column was named in the task brief; False if added here.
LAYER_B_COLUMNS: list[dict] = [
    # Transaction and award IDs
    {"name": "contract_transaction_unique_key", "group": "ids", "kind": "text", "requested": True},
    {"name": "contract_award_unique_key", "group": "ids", "kind": "text", "requested": True},
    {"name": "award_id_piid", "group": "ids", "kind": "text", "requested": True},
    {"name": "modification_number", "group": "ids", "kind": "text", "requested": True},
    {"name": "transaction_number", "group": "ids", "kind": "text", "requested": False,
     "why": "Part of contract_transaction_unique_key; needed to explain duplicate/split keys."},
    {"name": "parent_award_id_piid", "group": "ids", "kind": "text", "requested": True},
    {"name": "parent_award_agency_id", "group": "ids", "kind": "text", "requested": True},
    # Money and dates
    {"name": "federal_action_obligation", "group": "money", "kind": "decimal", "requested": True},
    {"name": "action_date", "group": "dates", "kind": "date", "requested": True},
    {"name": "action_date_fiscal_year", "group": "dates", "kind": "int", "requested": True},
    # Buyer
    {"name": "awarding_agency_code", "group": "buyer", "kind": "text", "requested": True},
    {"name": "awarding_agency_name", "group": "buyer", "kind": "text", "requested": True},
    {"name": "awarding_sub_agency_code", "group": "buyer", "kind": "text", "requested": True},
    {"name": "awarding_sub_agency_name", "group": "buyer", "kind": "text", "requested": True},
    {"name": "funding_agency_code", "group": "buyer", "kind": "text", "requested": True},
    # Vendor
    {"name": "recipient_uei", "group": "vendor", "kind": "text", "requested": True},
    {"name": "recipient_duns", "group": "vendor", "kind": "text", "requested": True,
     "why": "DUNS equivalent of recipient_uei (brief asked for any DUNS equivalents)."},
    {"name": "recipient_name", "group": "vendor", "kind": "text", "requested": True},
    {"name": "recipient_parent_uei", "group": "vendor", "kind": "text", "requested": True},
    {"name": "recipient_parent_duns", "group": "vendor", "kind": "text", "requested": True,
     "why": "DUNS equivalent of recipient_parent_uei (brief asked for any DUNS equivalents)."},
    {"name": "recipient_parent_name", "group": "vendor", "kind": "text", "requested": True},
    # Product
    {"name": "product_or_service_code", "group": "product", "kind": "text", "requested": True},
    {"name": "product_or_service_code_description", "group": "product", "kind": "text", "requested": True},
    {"name": "naics_code", "group": "product", "kind": "text", "requested": True},
    # Competition
    {"name": "extent_competed_code", "group": "competition", "kind": "text", "requested": True},
    {"name": "number_of_offers_received", "group": "competition", "kind": "int", "requested": True},
    {"name": "type_of_set_aside_code", "group": "competition", "kind": "text", "requested": True},
    {"name": "type_of_contract_pricing_code", "group": "competition", "kind": "text", "requested": True},
    {"name": "award_type_code", "group": "competition", "kind": "text", "requested": True},
    {"name": "award_or_idv_flag", "group": "competition", "kind": "text", "requested": True,
     "why": "Brief asked for the IDV / parent-award type if present: says whether the row is an award or an IDV."},
    {"name": "idv_type_code", "group": "competition", "kind": "text", "requested": True,
     "why": "Brief asked for the IDV / parent-award type if present."},
    {"name": "parent_award_type_code", "group": "competition", "kind": "text", "requested": True,
     "why": "Brief asked for the IDV / parent-award type if present."},
]

# The 26 column names listed in the task brief (before adding DUNS / IDV extras).
BRIEF_EXPECTED_COLUMNS = [
    "contract_transaction_unique_key", "contract_award_unique_key", "award_id_piid",
    "modification_number", "parent_award_id_piid", "parent_award_agency_id",
    "federal_action_obligation", "action_date", "action_date_fiscal_year",
    "awarding_agency_code", "awarding_agency_name", "awarding_sub_agency_code",
    "awarding_sub_agency_name", "funding_agency_code",
    "recipient_uei", "recipient_name", "recipient_parent_uei", "recipient_parent_name",
    "product_or_service_code", "product_or_service_code_description", "naics_code",
    "extent_competed_code", "number_of_offers_received", "type_of_set_aside_code",
    "type_of_contract_pricing_code", "award_type_code",
]
# Step 1 checkpoint: stop if more than this many brief columns are missing.
MAX_MISSING_BRIEF_COLUMNS = 2

# Columns the brief singles out for attention in the missing-values check.
MISSINGNESS_FOCUS = [
    "recipient_parent_uei", "product_or_service_code", "extent_competed_code", "awarding_agency_code",
]

# ---------------------------------------------------------------------------
# Reconciliation settings (fixed before looking at the data)
# ---------------------------------------------------------------------------
SPOT_CHECK_SEED = 5500       # DS 5500; recorded in the report
SPOT_CHECK_ROWS = 20
EXAMPLES_PER_CHECK = 10      # how many example rows to show for exceptions

# Check 6: a focus column is flagged when its blank share is at or above this
# share of rows OR of gross (absolute) dollars.
MISSING_WARN_SHARE = Decimal("0.01")

# Check 13 (GAO): |our total - GAO| / GAO
GAO_PASS_GAP = Decimal("0.02")
GAO_WARN_GAP = Decimal("0.10")

# Check 14 (USAspending API): the API reflects data as of the day it is called,
# the archive as of its file date, so small differences are expected.
API_TOTAL_PASS_GAP = Decimal("0.005")   # 0.5% on the grand total
API_TOTAL_WARN_GAP = Decimal("0.02")    # 2% on the grand total
API_AGENCY_PASS_GAP = Decimal("0.01")   # each agency within 1% ...
API_AGENCY_PASS_ABS = Decimal("1000000")  # ... or within $1M, whichever is looser

# ---------------------------------------------------------------------------
# External reference figures (check 13)
# ---------------------------------------------------------------------------
# Researched 2026-10-01. GAO issued no numbered report for this figure; the
# source is a WatchBlog post plus an interactive dashboard.
GAO_REFERENCE = {
    "figure": Decimal("793000000000"),
    "label": "GAO: federal contract obligations, FY2025 (figure cited in team pitch)",
    "verified": True,
    # The quote comes from the dashboard's data file (textData.intro), not from the blog post (corrected 2026-10-05).
    "citation": ('GAO, dashboard "A Snapshot: Government-Wide Contracting - A 2025 Update", data file '
                 "static/data/data.json, field textData.intro (FPDS data as of April 2026); announced in the WatchBlog "
                 "post \"A Snapshot of Government-Wide Contracting for FY 2025 (interactive dashboard)\", May 5, 2026."),
    "url": "https://files.gao.gov/multimedia/Federal_Government_Contracting-FY2025/static/data/data.json",
    "blog_url": "https://www.gao.gov/blog/snapshot-government-wide-contracting-fy-2025-interactive-dashboard",
    "dashboard_url": "https://files.gao.gov/multimedia/Federal_Government_Contracting-FY2025/index.html",
    "quote": ("The federal government obligated $793 billion through contracts in fiscal year 2025, "
              "a $17.8 billion increase from fiscal year 2024 after adjusting for inflation."),
    "includes": [
        "Federal contract obligations reported to FPDS for FY2025 (GAO: 'GAO analysis of Federal Procurement "
        "Data System data as of April 2026' - dashboard footer, read by the research step, not re-read by hand).",
        "Appears to be net of deobligations (GAO's dashboard data contains negative agency/category values) - inferred, not stated.",
        "Stated in constant FY2025 dollars, which for FY2025 itself equals nominal dollars (the dashboard data file "
        "also contains a stale string saying 'constant FY 2024 dollars').",
    ],
    "excludes": [
        "Other transaction agreements (OTAs): 'Data on other transaction agreements are not included in data on "
        "federal contract obligations.' GAO reports $18.2B of FY2025 OTA spending separately.",
        "Breakdowns exclude 'missing or other values that represent less than one percent of total obligations' "
        "(stated for the category figures; unclear whether it affects the headline total).",
        "Not addressed by GAO: classified actions, purchase-card micro-purchases, IDV-vs-award treatment. FAR 4.606 "
        "keeps classified actions and most micro-purchases out of FPDS in general.",
    ],
    "notes": "GAO used FPDS data as of April 2026; our archive is as of September 2026, so late reporting and "
             "corrections between those dates are one expected source of a gap.",
}

# Glossary (config/glossary.csv, built by tools/build_glossary.py into docs/glossary_v2.md, the latest version,
# and shown in the dashboard)
GLOSSARY_CSV = REPO_ROOT / "config" / "glossary.csv"
GOV_SOURCES_CSV = REPO_ROOT / "config" / "gov_sources.csv"
GLOSSARY_CATEGORIES = ["Data systems and files", "Award structure", "Money", "Identifiers", "Codes",
                       "Competition and socioeconomic", "Concentration", "Oversight and law", "Our pipeline"]
