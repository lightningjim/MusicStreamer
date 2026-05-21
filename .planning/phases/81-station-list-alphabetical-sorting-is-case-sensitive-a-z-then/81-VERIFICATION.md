---
phase: 81-station-list-alphabetical-sorting-is-case-sensitive-a-z-then
verified: 2026-05-21T00:00:00Z
status: passed
score: 8/8
overrides_applied: 0
re_verification: false
---

# Phase 81: Station List Case-Insensitive Sort — Verification Report

**Phase Goal:** Fix station-list alphabetical sort so mixed-case station names (deepSpace, Drone Zone, Groove Salad) interleave naturally in case-insensitive A→Z order instead of ASCII order (A-Z then a-z).
**Verified:** 2026-05-21
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | D-01: Case-insensitive collation lives in SQLite ORDER BY clauses in repo.py; no Python-side re-sort. | VERIFIED | `COLLATE NOCASE` is in the two SQL strings only. `StationTreeModel._populate` has zero sort/casefold calls. |
| 2 | D-02: COLLATE NOCASE on BOTH ORDER BY columns — COALESCE(p.name,'') and s.name — in both target queries. | VERIFIED | Both lines read `ORDER BY COALESCE(p.name,'') COLLATE NOCASE, s.name COLLATE NOCASE`. `grep -c "COLLATE NOCASE" repo.py` = 2, with 4 literal occurrences of the keyword across the two lines. |
| 3 | D-03: Exactly two queries modified — Repo.list_stations() at line 441 and Repo.list_favorite_stations() at line 678. | VERIFIED | `grep -n "COLLATE NOCASE" repo.py` returns exactly lines 441 and 678. No other lines changed per commit 300ab45 diff (4 insertions of the keyword, 2 deletions of old text, 0 other lines touched). |
| 4 | D-04: Out-of-scope sort sites untouched — list_providers() (line 324), station_list_panel.py filter chips, tag chips, recent panel, search results, EditStationDialog. | VERIFIED | `list_providers()` at line 324 retains `ORDER BY name` (no COLLATE NOCASE). No COLLATE NOCASE found in station_list_panel.py or station_tree_model.py. |
| 5 | D-05: Built-in SQLite NOCASE only — no Unicode fold, no locale.strcoll, no natural-numeric helpers. | VERIFIED | Only the keyword `COLLATE NOCASE` added. No new imports in repo.py. No schema/user_version change. commit 300ab45 shows exactly 2 lines changed. |
| 6 | Behavioral truth: list_stations() returns mixed-case fixture stations in case-insensitive A→Z order. | VERIFIED | `test_list_stations_case_insensitive_order` passes: seeds [Zenith, deepSpace, aardvark, Groove Salad, Drone Zone], asserts result = [aardvark, deepSpace, Drone Zone, Groove Salad, Zenith]. |
| 7 | Behavioral truth: list_favorite_stations() returns the favorite-filtered subset in case-insensitive A→Z order. | VERIFIED | `test_list_favorite_stations_case_insensitive_order` passes: favorites subset sorted via `sorted(..., key=str.casefold)` expected value, DB result matches. |
| 8 | Drift-guard truth: source-grep test fails if COLLATE NOCASE is removed from either target ORDER BY clause. | VERIFIED | `test_collate_nocase_drift_guard` passes: reads repo.py, strips comment lines, asserts count == 2 with Phase 81 D-03 failure message. |

**Score:** 8/8 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/repo.py` | Two ORDER BY clauses with COLLATE NOCASE on both COALESCE(p.name,'') and s.name | VERIFIED | Lines 441 and 678 both carry the full `ORDER BY COALESCE(p.name,'') COLLATE NOCASE, s.name COLLATE NOCASE` clause. Grep count = 2. |
| `tests/test_repo.py` | Behavioral interleave tests + COLLATE NOCASE drift-guard | VERIFIED | Three new tests appended at lines 838, 846, 860. Helper `_seed_mixed_case_stations` at line 829. All three tests pass. No existing test modified. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `repo.py:441 (list_stations)` | `StationTreeModel._populate` | Fetch order inherited; no Python-side re-sort | VERIFIED | `station_tree_model.py` has no sort/casefold calls. Ordering flows from DB. |
| `repo.py:678 (list_favorite_stations)` | `MainWindow._refresh_station_list → favorites view` | Fetch order inherited; no Python-side re-sort | VERIFIED | No re-sort in consumption path. Pattern `ORDER BY COALESCE(p.name,'') COLLATE NOCASE, s.name COLLATE NOCASE` confirmed present. |

---

### Data-Flow Trace (Level 4)

Not applicable. Phase 81 modifies only ORDER BY collation on existing queries — no new data variables, no new rendering paths, no new components. The fetch → model → view chain is unchanged from pre-Phase-81 baseline; only the sort order of rows changes.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Three new Phase 81 tests pass | `pytest tests/test_repo.py -k "case_insensitive_order or collate_nocase_drift_guard" -q` | `3 passed in 0.18s` | PASS |
| Full test_repo.py suite — no regressions | `pytest tests/test_repo.py -q` | `69 passed in 0.58s` | PASS |
| Module imports cleanly | `python -c "import musicstreamer.repo; import musicstreamer.ui_qt.station_tree_model"` | No errors | PASS |
| COLLATE NOCASE count exactly 2 | `grep -c "COLLATE NOCASE" musicstreamer/repo.py` | `2` | PASS |
| COLLATE NOCASE at exactly lines 441 and 678 | `grep -n "COLLATE NOCASE" musicstreamer/repo.py` | Lines 441, 678 only | PASS |
| list_providers() untouched (D-04) | `grep -n "list_providers" musicstreamer/repo.py` shows line 324 ORDER BY without COLLATE NOCASE | `ORDER BY name` — no NOCASE | PASS |

---

### Probe Execution

No probes declared or conventional for this phase. Step 7c: SKIPPED (no probe-*.sh files; phase is a surgical SQL edit + tests, not a migration/tooling phase).

---

### Requirements Coverage

No formal REQ-* requirement IDs were assigned to Phase 81 (ROADMAP notes requirements as TBD; coverage contract is CONTEXT.md decisions D-01..D-05). All five decisions are verified above in the Observable Truths table.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | — | — | — |

Scan of `musicstreamer/repo.py` and `tests/test_repo.py`: no TBD, FIXME, XXX, TODO, HACK, PLACEHOLDER, or stub return patterns found. The `sorted(..., key=str.casefold)` in test line 856 computes the expected assertion value only — it does not re-sort DB results and is not a D-01 violation.

---

### Human Verification Required

None. All behaviors verifiable from code and automated tests:
- Sort order correctness verified by `test_list_stations_case_insensitive_order` passing.
- Favorites correctness verified by `test_list_favorite_stations_case_insensitive_order` passing.
- No visual layout changes, no new UI surfaces, no external service integration.

---

### Gaps Summary

No gaps. All 8 must-have truths verified. Phase goal achieved.

---

_Verified: 2026-05-21T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
