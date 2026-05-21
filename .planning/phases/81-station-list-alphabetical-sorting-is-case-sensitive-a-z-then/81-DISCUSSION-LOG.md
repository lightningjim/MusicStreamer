# Phase 81: Station list case-insensitive sort - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-21
**Phase:** 81-station-list-alphabetical-sorting-is-case-sensitive-a-z-then
**Areas discussed:** Sort layer choice, Scope of fix, Collation type

---

## Sort Layer Choice

| Option | Description | Selected |
|--------|-------------|----------|
| SQLite COLLATE NOCASE (Recommended) | Append COLLATE NOCASE to each ORDER BY clause in repo.py. Single line per query, can't be forgotten by downstream consumers, no Python re-sort overhead. SQLite native, ASCII-only. | ✓ |
| Python-side casefold key | Leave repo.py SQL alone; re-sort lists after fetch with sorted(stations, key=lambda s: ...casefold()). Matches the url_helpers.py / add_sibling_dialog.py / filter_utils.py precedent. | |
| Both — SQL + Python guard | Add COLLATE NOCASE in SQL AND have UI-side consumers casefold-sort defensively. Belt-and-suspenders but more drift surface. | |

**User's choice:** SQLite COLLATE NOCASE
**Notes:** Single source of truth in repo.py — downstream UI never re-sorts, so the SQL layer is the natural place to lock the order.

### Follow-up: Which columns get COLLATE NOCASE?

| Option | Description | Selected |
|--------|-------------|----------|
| Both columns (Recommended) | `ORDER BY COALESCE(p.name,'') COLLATE NOCASE, s.name COLLATE NOCASE`. Consistent, future-proof against lowercase provider names. | ✓ |
| Station name only | `ORDER BY COALESCE(p.name,''), s.name COLLATE NOCASE`. Minimum-diff — only fixes the observed station-row issue. | |

**User's choice:** Both columns
**Notes:** Consistency over minimum-diff; provider names are all uppercase today so visual delta is near-zero but pattern is uniform.

---

## Scope of Fix

| Option | Description | Selected |
|--------|-------------|----------|
| Station tree (list_stations — repo.py:441) | The main bug locus. Drone Zone / Groove Salad / deepSpace case lives here. Must be in scope. | ✓ |
| Favorites view (list_favorite_stations — repo.py:678) | Same ORDER BY shape, same bug. Trivial to fix in the same edit. | ✓ |
| Provider list (list_providers — repo.py:324) | ORDER BY name used by EditStationDialog provider dropdown. Less visible — providers are all capitalized so visual delta is near-zero today. | |
| Provider filter chips + tag chips (station_list_panel.py:505,516) | Python set `sorted(...)` for filter chip ordering. Different surface (UI-side, post-fetch) — would require a small Python edit on top of the SQL changes. | |

**User's choice:** Station tree + Favorites view only
**Notes:** Kept the phase tight to the user-reported surface. Provider list and filter chip changes deferred — captured in CONTEXT.md `<deferred>` for follow-up phases.

---

## Collation Type

| Option | Description | Selected |
|--------|-------------|----------|
| SQLite NOCASE — ASCII case-insensitive (Recommended) | Folds A-Z and a-z together. Built into SQLite, zero dependencies. Does NOT handle accents or natural-numeric sort. Matches the user-reported bug exactly. | ✓ |
| Custom Python collation via con.create_collation | Register a collation function calling str.casefold() on both sides; same fold result as NOCASE plus full Unicode coverage. Tiny perf cost. | |
| Locale-aware natural sort (locale.strcoll or natsort) | Handles both case and embedded numbers ('Drone Zone 2' < 'Drone Zone 10'). Adds a new dependency or relies on system locale. Overkill for the reported bug. | |

**User's choice:** SQLite NOCASE
**Notes:** Match the bug exactly. Anything more (Unicode, natural-numeric) is a different phase if/when it's needed.

---

## Claude's Discretion

- **Test approach** — User opted out of explicit discussion. Recommendation captured in CONTEXT.md `<decisions>` D-Claude-Discretion: behavioral interleave test in `tests/test_repo.py` + source-grep drift-guard pinning `COLLATE NOCASE` presence (Phase 51/55/61/63 precedent).
- **SQLite `user_version` bump** — Not required; `COLLATE NOCASE` is a query-side annotation, not a schema change. No migration, no data rewrite.
- **Indexes** — Library is 50-200 rows; ORDER BY with COLLATE NOCASE is sub-millisecond on a full scan. Defer any index work.

## Deferred Ideas

- Provider-name case-insensitive sort (`Repo.list_providers()`)
- Filter chip + tag chip case-insensitive sort (`StationListPanel.refresh_model` Python `sorted({...})` sites)
- Natural-numeric sort (`Drone Zone 2` before `Drone Zone 10`)
- Unicode-aware collation (`é`, `ü`, `ß`)
