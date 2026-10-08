# FY2025 data viewer

> **Superseded (2026-10-05).** `python -m viewer.server` now serves the all-years data-health dashboard (see README and `docs/data_stages.md`). This page describes the earlier FY2025-only viewer over Layer B, whose engine (`viewer/data.py`) is kept in the repo but no longer served; `viewer/ui_check.mjs` belongs to it too.

A local web page for browsing all 6,639,176 FY2025 contract transactions as one table. It is for looking, not deciding:

- Every row is shown as it is in the pilot's Parquet files.
- There are no rollups, no award collapsing, no special handling of negative amounts, and no concentration measures.

## Start it

```bash
.venv/bin/python -m viewer.server
```

Then open **<http://127.0.0.1:8765/>**. It is ready in under a second. Stop it with Ctrl+C. Use `--port N` for a different port, and `--quiet` to stop it logging each request.

- **No new dependencies.** It uses Python's built-in web server and the DuckDB already pinned in `requirements.txt`.
- **No network access needed.** The page is plain HTML, CSS and JavaScript stored in [viewer/static/](../viewer/static/).

## What it reads (read-only)

| Table in the SQL | File | What it holds |
|---|---|---|
| `b` | `data/parquet/layer_b/fy2025_contracts_layer_b.parquet` | Layer B: 32 typed working columns, plus lineage |
| `a` | the 7 files `data/parquet/layer_a/fy2025/FY2025_All_Contracts_Full_20260907_{1..7}.parquet` | Layer A: all 297 source columns as text, plus lineage |
| — | `reports/reconciliation_fy2025.json` | the reference totals, and the explicit list of Layer A files (never a `*.parquet` glob; see review finding S5) |

- **How Layer A is reached.** A Layer-A-only column is read by joining `a` to `b` on the lineage columns (`_source_member_idx`, `_source_row`). The join happens only when a query needs such a column.
- **Read-only.** The viewer never writes to `data/`, `src/`, `reports/` or `docs/`. DuckDB's spill folder is set to the system temp folder, not the repo.
- **Startup check.** On start, the server checks that Layer A rows = Layer B rows = the report's 6,639,176, and prints the result.

## The page, panel by panel

**Totals (top right).**
- **What it shows:** the number of rows matching the current filters and their net obligations. The sum is exact: DuckDB adds the amounts as `DECIMAL`, and the page shows the exact decimal string with commas and cents, never rounded.
- **With no filters:** a green note confirms the numbers match `reports/reconciliation_fy2025.json` (6,639,176 rows; $793,189,920,124.27). If they ever disagree, the note turns red.

**Filters.**
- **Adding one:** type a column name; any of the 297 is offered. The controls then change to suit the column:
  - **Code columns with at most 200 distinct values:** a dropdown listing each code with its description and row count, for example `A — FULL AND OPEN COMPETITION (3,989,839 rows)`. "(blank)" is offered when blanks exist.
    - Descriptions come from the matching description column (`extent_competed`, `awarding_agency_name`, …).
    - The row counts are over all FY2025 rows, not the current filters.
    - This applies to all of the brief's examples: awarding agency (70), sub-agency (168), extent competed (10), award type, set-aside, pricing type, IDV type, and more.
  - **Other text columns:** "contains" or "equals", both case-insensitive. The filter is applied when you press Enter or **Add filter**, not on every keystroke.
  - **Dollar, date and number columns:** min and/or max. These are the typed Layer B columns `federal_action_obligation`, `action_date`, `action_date_fiscal_year` and `number_of_offers_received`.
- **Combining:** all filters combine with AND. Each one appears as a chip with ✕ to remove it, and **Clear all** removes everything.
- **The 200 cutoff:** it gives a dropdown to every column you would want one for (sub-agency is the largest at 168), while keeping lists short enough to scan. Recipient names (101,380 distinct values), PSC and NAICS codes stay text filters.

**Table.**
- **Default view:** the 32 Layer B columns, 100 rows per page, newest `action_date` first.
- **Sorting:** click a column header to sort by it, and click again to flip the direction. Ties are always broken by `contract_transaction_unique_key`, so paging is stable. The note beside the pager says what the table is sorted by.
- **Pager:** first, previous, page number box, next and last.
- **Blanks:** an empty cell means the value is blank.
- **Layer A columns:** their headers are in italics, and they are shown as stored text.

**Columns.** Opens a picker for all 297 columns: Layer B typed columns first, then the 265 Layer-A-only text columns. It has a search box over column names, plus "Layer B defaults" and "All 297" shortcuts. Columns appear in source-file order.

**Row detail.**
- **Opening it:** click any row to see all 297 fields of that transaction exactly as stored in Layer A, plus its three lineage fields. A search box finds a field quickly.
- **The award button:** **Show all FY2025 transactions for this award** replaces the filters with `contract_award_unique_key` = this row's award.

**Group-by summary.**
- **Choosing:** pick any column. For the current filters you see its top 50 values, ordered by row count, or by net obligations if you switch the order.
- **Each value shows:**
  - row count
  - net obligations
  - % of the filtered net
  - a bar for that share (red when the net is negative)
  - % of filtered rows
  - the number of negative-amount rows
- **The remainder row:** a final "all other N values" row holds the remainder, so the column always adds back to the filtered total.
- **Filtering from it:** click a value to add it as a filter.

**Export CSV.**
- **What it downloads:** the current filtered view, with the visible columns in the current sort. It is capped at **100,000 rows**.
- **When it's capped:** the note next to the button says how many rows were left out, before you click. The file name records it too, for example `fy2025_view_100000_of_6639176_rows.csv`.
- **Money in the file:** amounts are written as exact decimals.

**Show the SQL.** A collapsible panel at the bottom with the exact queries behind the current page, totals and group-by, with parameter values written in. It also shows the two `CREATE VIEW` statements, so you can paste everything into DuckDB yourself.

**Bookmarks.** Filters, sort, chosen columns, page and group-by column are all in the URL, so a bookmark reopens the same view. Back and Forward work.

## Safety

- **Local only.** It binds to `127.0.0.1` only, and refuses requests whose `Host` header isn't `127.0.0.1` or `localhost` on its own port. That guards against DNS rebinding.
- **Nothing external.** No telemetry, and no outbound calls: DuckDB's extension auto-install and auto-load are switched off. The page's Content-Security-Policy is `default-src 'self'`, so it cannot load anything from outside.
- **Safe queries.**
  - Filter values are always passed to DuckDB as bound parameters.
  - Column names, sort keys and operators are checked against the real Parquet column list and a fixed set of operators, then quoted.
  - Dollar, date and integer values are validated before use.
  - Anything invalid gets HTTP 400 with a message.
- **Read-only server.** Only `GET` is accepted, and only three static files are served.

## Known limits and anything slow

- **Export cap:** 100,000 rows. Exporting all 297 columns at the cap is about 220 MB and took 7–12 s over two runs. Most of that time is Python writing 30 million CSV cells; the default 32 columns take 1.2–1.5 s.
- **Sorting on a Layer-A-only column** takes about 0.7 s, because it has to join all 6.6M rows before sorting. Sorting on Layer B columns is under 0.1 s.
- **The last page** (offset 6.6M) takes about 0.5–0.7 s, because DuckDB must sort past every earlier row.
- **Dropdown counts are static:** they cover all of FY2025, not the current filters. The table totals and group-by do follow the filters.
- **Layer A dollar and date columns are text** (for example `total_dollars_obligated`, `period_of_performance_start_date`), so they get contains/equals, not min/max. Only Layer B columns are typed.
- **Fixed the first time round: wide pages were very slow.** The first version took about 90 s for a deep page with all 297 columns, because DuckDB decoded every row of every visible column before keeping 100. The page query now does "late materialization":
  - It first picks the page's 100 row IDs using only the filter and sort columns.
  - It then fetches the visible columns for just those rows.
  - An automated check confirms the result is identical to the plain one-step query.
- **"Contains" filters are not slow** on this data: 25–60 ms over 6.6M rows. So the only measure needed was applying text filters on Enter rather than on each keystroke.

## Tests

```bash
.venv/bin/python -m viewer.test_viewer           # API checks + timings + headless-Chrome screenshots
node viewer/ui_check.mjs                         # optional: click-through check (needs the server running)
```

- **How `viewer/test_viewer.py` runs:** it starts its own server on a free port, writes nothing in the repo, and exits non-zero on any failure.
- **Where expected values come from:** straight from `reports/reconciliation_fy2025.json`, or from a separate DuckDB connection, never from the viewer's own code.
- **Results** of the run on 2026-10-02: **27/27 API checks passed; both render checks passed.**

| Check | Result |
|---|---|
| No filters: rows and net obligations = report | PASS: 6,639,176 rows, $793,189,920,124.27 |
| Top 5 awarding agencies (097, 036, 089, 070, 075) = report's by-agency figures | PASS ×5, exact (e.g. DoD 4,489,958 rows, $491,745,948,581.03) |
| Group-by awarding agency, no filters, adds back to the grand total | PASS: top 50 + "all other 20" = 6,639,176 rows, $793,189,920,124.27 |
| Group-by: the top 5 agencies equal the report | PASS |
| Pages 1 and 2 share no transaction keys (default sort) | PASS: 100 + 100, overlap 0 |
| Page contents = a plain one-step query (filtered, sorted on a Layer A column, page 3) | PASS: identical |
| `O'Brien` and `x'; DROP TABLE t; --` with "equals" and "contains" on `recipient_name` | PASS ×4: HTTP 200; counts equal an independent query (0, 112, 0, 0) |
| Data intact afterwards | PASS |
| Bad column, sort key, direction, operator, decimal and column list are rejected | PASS ×6 (HTTP 400) |
| Export of a filtered view (DOE): rows = filtered count | PASS: 12,719 rows; CSV obligations sum to $50,261,970,230.72 = report |
| Export, unfiltered: capped and flagged | PASS: 100,000 of 6,639,176, `X-Export-Truncated: true` |
| Row detail: 297 fields + 3 lineage; award button filter | PASS |
| Foreign `Host` header refused; page assets reference nothing external | PASS |
| Render (headless Chrome screenshots): default view, and filtered + group-by view | PASS: the rendered page shows "6,639,176" and the group-by table |
| Click-through (`ui_check.mjs`): every panel, bookmark reload, no JS errors or external requests | 19/19 PASS |

**Timings.** Each is a fresh (uncached) request on this Mac (Apple Silicon, 16 GB), measured as the full HTTP round trip. The table shows the first full run; a repeat run differed by tens of milliseconds, except where a range is given:

| What | Time |
|---|---|
| Unfiltered first page | 65 ms |
| Unfiltered totals | 17 ms |
| "Contains" on `recipient_name` (lockheed / booz allen / deloitte): page | 42 / 53 / 41 ms |
| …same: totals | 31 / 26 / 30 ms |
| Group-by `recipient_parent_name`, unfiltered | 101 ms |
| Group-by `recipient_parent_name`, filtered to VA | 52 ms |
| Filter on a Layer-A-only column (`recipient_state_code`) | 97 ms |
| Sort by a Layer-A-only column | 704 ms |
| Last page (offset 6.6M) | 520–663 ms |
| All 297 columns: page 1 / page 500 | 174 / 375 ms |
| Export at the cap: 32 columns / all 297 columns | 1.2–1.5 s (36 MB) / 7.3–12.4 s (221 MB) |

The screenshots and a `results.json` go to a temporary folder, printed at the end of the run, so you can look at them by eye.
