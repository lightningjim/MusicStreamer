# Phase 81: Station list case-insensitive sort - Context

**Gathered:** 2026-05-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix the station-list alphabetical sort so that mixed-case names interleave naturally — `deepSpace`, `Drone Zone`, `Groove Salad` should appear adjacent instead of grouped by ASCII case (`A-Z` block then `a-z` block). Surfaced post-Phase 74 SomaFM re-import (2026-05-14). Scope is intentionally narrow: SQLite-side fix on the two repo queries that drive the station tree and the favorites view. Everything else (provider list, filter chips, tag chips, search results) is explicitly out of scope for this phase.

</domain>

<decisions>
## Implementation Decisions

### Sort Layer
- **D-01:** Case-insensitive collation lives in SQLite, not Python. Append `COLLATE NOCASE` to the `ORDER BY` clauses in `repo.py`. Single source of truth per query — downstream UI consumers (`StationTreeModel._populate`, `StationListPanel.refresh_model`, `StationListPanel._populate_recent`) inherit ordering from the fetch and never re-sort. Reason: the repo is the only place row order is decided today; pushing it Python-side would create a second drift surface.
- **D-02:** `COLLATE NOCASE` applies to **both** ORDER BY columns: `COALESCE(p.name,'') COLLATE NOCASE, s.name COLLATE NOCASE`. Provider headers are all uppercase today (SomaFM, AudioAddict, GBS.FM) so the visible delta on the provider column is near-zero, but consistency is future-proof against any lowercase provider name that lands later.

### Scope of Fix
- **D-03:** In scope (this phase):
  - `Repo.list_stations()` — `musicstreamer/repo.py:441` (powers the main station tree under "All" mode)
  - `Repo.list_favorite_stations()` — `musicstreamer/repo.py:678` (powers the favorites view; same `ORDER BY` shape)
- **D-04:** Out of scope (deferred to follow-up phases if/when needed):
  - `Repo.list_providers()` (repo.py:324) — provider dropdown in EditStationDialog; all known provider names are uppercase so no visible bug
  - `StationListPanel._populate_recent` / `Repo.list_recent` — sorted by `last_played_at DESC`, not by name
  - `StationListPanel.refresh_model` provider filter chip set (station_list_panel.py:505) — Python `sorted({...})`; different surface, would need a Python-side change
  - StationListPanel tag chip set (station_list_panel.py:516) — same Python-side surface
  - GBS.FM search dialog results / EditStationDialog stream rows — user-driven order, not server-sorted

### Collation Type
- **D-05:** Use SQLite's built-in `NOCASE` collation. ASCII-only case-fold, native, zero new dependencies. Explicitly NOT in scope:
  - Unicode-aware case-folding (accents like `é`, `ü`, `ß`) — current library is English-station-only
  - Locale-aware sort (`locale.strcoll`)
  - Natural-numeric sort (`Drone Zone 2` before `Drone Zone 10`) — user did not ask for this; SomaFM/AA naming conventions don't currently produce ambiguous numeric ranges that hurt UX
  Rationale: match the reported bug exactly. Anything more is a different phase.

### Claude's Discretion
- **Test approach** — user opted out of explicit discussion. Recommend a behavioral interleave test: insert fixture stations with names like `deepSpace`, `Drone Zone`, `Groove Salad`, `aardvark`, `Zenith`, fetch via `Repo.list_stations()`, assert returned order is the expected case-insensitive list. Add a lightweight source-grep drift-guard pinning `COLLATE NOCASE` presence in the two target `ORDER BY` clauses (precedent: Phase 51 / 55 / 61 / 63 source-grep tests).
- **SQLite `user_version` bump** — not required. `COLLATE NOCASE` is a query-side annotation, not a schema change. No migration, no data rewrite.
- **Indexes** — the `stations.name` column has no covering index today and this phase doesn't add one. The station library is 50-200 rows; a full table scan with `ORDER BY ... COLLATE NOCASE` is sub-millisecond. Defer any index work unless a future profiling phase flags it.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Sort sites being modified
- `musicstreamer/repo.py:441` — `Repo.list_stations()` ORDER BY clause (D-03 target #1)
- `musicstreamer/repo.py:678` — `Repo.list_favorite_stations()` ORDER BY clause (D-03 target #2)

### Reference precedent (existing case-insensitive sort sites that stay untouched)
- `musicstreamer/url_helpers.py:257` — `find_aa_siblings` already sorts via `casefold()` (Python-side)
- `musicstreamer/ui_qt/add_sibling_dialog.py:337` — sibling-picker eligibility list already uses `casefold()`
- `musicstreamer/filter_utils.py:16,36,44,45,67,75,76` — search/tag filtering already case-folds for matching (not sorting)

### Out-of-scope sort sites (D-04 — explicitly NOT in this phase)
- `musicstreamer/repo.py:324` — `Repo.list_providers()`
- `musicstreamer/ui_qt/station_list_panel.py:505` — provider filter chip set
- `musicstreamer/ui_qt/station_list_panel.py:516` — tag chip set

### Project conventions
- `.planning/PROJECT.md` §Key Decisions — for source-grep drift-guard pattern (Phase 51 / 55 / 61 / 63)
- `.planning/ROADMAP.md` Phase 81 entry — promoted from backlog 999.1 (2026-05-14 surfacing during Phase 74 SomaFM re-import)

No external specs / ADRs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Repo.list_stations()` / `Repo.list_favorite_stations()` already use `COALESCE(p.name,'')` to keep NULL-provider stations from sorting to the end unpredictably. The `COLLATE NOCASE` modifier composes with `COALESCE` without any change to the COALESCE layer.
- Two test fixtures already exist that exercise `list_stations()` ordering with mixed-case names — see `tests/test_repo.py` (D-03 target tests will extend this file, not create a new one).

### Established Patterns
- **Source-grep drift-guards:** Phases 51, 55, 61, 63 all ship a regex-on-source test that fails if the expected literal disappears from a production file. Same idiom would lock the `COLLATE NOCASE` clauses in `repo.py`.
- **Casefold (Python) as the alternative path:** The pre-existing case-insensitive sites all use `str.casefold()` (not `lower()`). If a future phase ever needs to mirror the SQL behavior in Python, `casefold()` is the established choice — but Phase 81 stays SQL-side per D-01.
- **Repo function signatures unchanged:** No new kwargs, no new return shape — pure ORDER BY edit. UI consumers won't notice anything except the visual ordering shift.

### Integration Points
- `StationTreeModel._populate` (`musicstreamer/ui_qt/station_tree_model.py:73-95`) — consumes `Repo.list_stations()` output and groups by provider via dict insertion order. The new case-insensitive fetch order will flow through to the visible tree without any model changes.
- `StationListPanel._set_station_tree_data` consumers — same: they iterate the model in fetch order, no re-sort.
- Favorites view path: `MainWindow._refresh_station_list` → `Repo.list_favorite_stations()` → same StationTreeModel population.

</code_context>

<specifics>
## Specific Ideas

- User-reported repro fixture: stations `deepSpace`, `Drone Zone`, `Groove Salad` (all SomaFM, post-Phase 74 re-import). After fix, these should appear in alphabetical-case-insensitive interleave.
- Phase tone: minimum-diff, surgical. Two `ORDER BY` clauses get a one-word modifier. No model changes, no UI changes, no new files except the test.

</specifics>

<deferred>
## Deferred Ideas

- **Provider-name case-insensitive sort** (`Repo.list_providers()`) — needed only if a lowercase provider name lands in the library. Tiny one-line change when it does.
- **Filter chip + tag chip case-insensitive sort** (`StationListPanel.refresh_model` Python `sorted({...})` sites) — UI-side cosmetic ordering of the filter strip. Different layer (Python set sort vs. SQL ORDER BY) so it'd need a separate code change. Capture as a future polish phase if the user notices.
- **Natural-numeric sort** (`Drone Zone 2` before `Drone Zone 10`) — only matters if SomaFM/AA ever ship numbered station families with double-digit members. Not present today.
- **Unicode-aware collation** (`é`, `ü`, `ß`) — only relevant for non-English station libraries. Out of scope until the library actually contains such names.

### Reviewed Todos (not folded)
None — discussion stayed within phase scope.

</deferred>

---

*Phase: 81-station-list-alphabetical-sorting-is-case-sensitive-a-z-then*
*Context gathered: 2026-05-21*
