---
phase: 81
plan: "01"
subsystem: repo
tags:
  - sqlite
  - sort
  - collation
dependency_graph:
  requires: []
  provides:
    - "Repo.list_stations() returns stations in case-insensitive A->Z order"
    - "Repo.list_favorite_stations() returns favorites in case-insensitive A->Z order"
  affects:
    - "musicstreamer/ui_qt/station_tree_model.py (StationTreeModel._populate)"
    - "musicstreamer/ui_qt/station_list_panel.py (favorites view)"
tech_stack:
  added: []
  patterns:
    - "SQLite COLLATE NOCASE on ORDER BY columns"
    - "Source-grep drift-guard test (Phase 51/55/61/63 precedent)"
key_files:
  modified:
    - musicstreamer/repo.py
    - tests/test_repo.py
decisions:
  - "D-01: COLLATE NOCASE in SQLite ORDER BY, not Python — single source of truth per query"
  - "D-02: Both ORDER BY columns covered — COALESCE(p.name,'') COLLATE NOCASE, s.name COLLATE NOCASE"
  - "D-03: Exactly two queries modified — list_stations() line 441, list_favorite_stations() line 678"
  - "D-04: Out-of-scope sites untouched — list_providers(), filter chips, tag chips, search results"
  - "D-05: Built-in SQLite NOCASE only — no Unicode fold, no locale.strcoll, no natural-numeric"
metrics:
  duration: "1m 57s"
  completed: "2026-05-21"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
---

# Phase 81 Plan 01: Station List Case-Insensitive Sort Summary

**One-liner:** SQLite COLLATE NOCASE on both ORDER BY columns in list_stations() and list_favorite_stations(), locked by behavioral interleave tests and a source-grep drift-guard.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Append COLLATE NOCASE to both ORDER BY clauses in repo.py | 300ab45 | musicstreamer/repo.py |
| 2 | Add behavioral interleave tests + COLLATE NOCASE drift-guard | 6f80b0d | tests/test_repo.py |

## What Was Built

**Task 1:** Surgical 2-line edit in `musicstreamer/repo.py`:

- Line 441 (`Repo.list_stations`): `ORDER BY COALESCE(p.name,''), s.name` → `ORDER BY COALESCE(p.name,'') COLLATE NOCASE, s.name COLLATE NOCASE`
- Line 678 (`Repo.list_favorite_stations`): same transformation

**Task 2:** Three new tests appended to `tests/test_repo.py`:

1. `test_list_stations_case_insensitive_order` — seeds `["Zenith", "deepSpace", "aardvark", "Groove Salad", "Drone Zone"]` in scrambled order, asserts `list_stations()` returns `["aardvark", "deepSpace", "Drone Zone", "Groove Salad", "Zenith"]`
2. `test_list_favorite_stations_case_insensitive_order` — seeds same 5 stations, favorites 1st/3rd/5th, asserts `list_favorite_stations()` returns the 3-item subset sorted by `str.casefold`
3. `test_collate_nocase_drift_guard` — reads `musicstreamer/repo.py` source, strips comment lines, counts `ORDER BY COALESCE(p.name,'') COLLATE NOCASE, s.name COLLATE NOCASE` occurrences, asserts exactly 2 with Phase 81 D-03 failure message

## Decisions Honored

- **D-01:** Collation lives entirely in SQLite `ORDER BY` clauses; no Python-side re-sort introduced. Downstream consumers (`StationTreeModel._populate`, `MainWindow._refresh_station_list`) inherit ordering unchanged.
- **D-02:** `COLLATE NOCASE` applied to BOTH columns — `COALESCE(p.name,'')` and `s.name` — in BOTH queries. Four total insertions of the literal.
- **D-03:** Exactly `Repo.list_stations()` (line 441) and `Repo.list_favorite_stations()` (line 678) modified. No other method in repo.py touched.
- **D-04:** `Repo.list_providers()` (line 324), `station_list_panel.py:505` provider chips, `station_list_panel.py:516` tag chips, recent panel, search results, EditStationDialog — all untouched. `grep -n "COLLATE NOCASE" musicstreamer/repo.py` returns exactly lines 441 and 678.
- **D-05:** SQLite built-in `NOCASE` only. No Unicode-aware fold, no `locale.strcoll`, no natural-numeric sort, no schema change, no `user_version` bump.

## Verification Results

```
grep -c "ORDER BY COALESCE(p.name,'') COLLATE NOCASE, s.name COLLATE NOCASE" musicstreamer/repo.py
2

grep -c "COLLATE NOCASE" musicstreamer/repo.py
2

pytest tests/test_repo.py -k "case_insensitive_order or collate_nocase_drift_guard" -q
3 passed in 0.17s

pytest tests/test_repo.py -q
69 passed in 0.59s

python -c "import musicstreamer.repo; import musicstreamer.ui_qt.station_tree_model"
# OK — no errors
```

## Deviations from Plan

None — plan executed exactly as written.

## Threat Flags

None — only SQL ORDER BY modifier changed. No new user input surfaces, no new auth paths, no new file I/O, no new network paths. T-81-00 disposition: accept.

## Self-Check: PASSED

- musicstreamer/repo.py: FOUND (lines 441 and 678 carry COLLATE NOCASE)
- tests/test_repo.py: FOUND (3 new tests appended at end)
- Commit 300ab45: FOUND (Task 1)
- Commit 6f80b0d: FOUND (Task 2)
- grep -c returns exactly 2: CONFIRMED
- 69 tests passing: CONFIRMED
