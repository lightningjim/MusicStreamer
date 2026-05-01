---
phase: 55-edit-station-preserves-section-state
plan: 02
subsystem: testing
tags: [pytest, pytest-qt, station-list, regression-lock, bug-fix, monkeypatch-spy, nyquist]

# Dependency graph
requires:
  - phase: 55-edit-station-preserves-section-state
    provides: "Plan 01 — provider_name_at accessor on StationTreeModel + capture/restore wrapping in StationListPanel.refresh_model (parallel Wave 1, merged after both worktrees complete)"
  - phase: 50-recently-played-live-update
    provides: "Phase 50 / BUG-01 banner style + Phase 50 mutation+refresh test pattern (test_refresh_recent_updates_list at line 504) — mirrored for the Phase 55 banner and the brand-new-group / cross-provider-move tests"
provides:
  - "8 new pytest-qt tests under '# Phase 55 / BUG-06: refresh_model preserves provider expand/collapse' banner in tests/test_station_list_panel.py"
  - "Permanent regression locks for D-03 (negative — refresh_model MUST NOT call _sync_tree_expansion) and D-05 (positive — _on_search_changed MUST still call _sync_tree_expansion) via monkeypatch spy pattern"
  - "Behavioral coverage of SC #1 (preserve user-expanded), SC #2 (preserve all-collapsed), D-04 (under active filter), D-06 (brand-new group default-expanded), D-07 (cross-provider move keeps destination collapsed)"
  - "Defensive coverage for Pitfall #2 (filtered-out captured-expanded provider does not crash restore)"
affects: [station-list-panel, station-tree-model, refresh_model-contract, future-bug-06-refactors]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "monkeypatch.setattr spy pattern for Qt signal-handler call-count assertions (Nyquist contract lock — covers both negative-contract and positive-lock evidence)"
    - "FakeRepo._stations in-place mutation drives refresh_model through new-station / cross-provider-move / brand-new-provider scenarios without redefining fixtures"
    - "Source-side proxy_idx = panel._proxy.mapFromSource(model.index(row, 0)) walk used to read post-refresh expansion state when proxy row order may have shifted"

key-files:
  created: []
  modified:
    - "tests/test_station_list_panel.py — appended Phase 55 / BUG-06 banner + 8 new tests at end of file (lines 535-763), 229 insertions"

key-decisions:
  - "Append-only — zero modification to existing imports, fixtures (FakeRepo, _sample_repo, make_station), or Phase 50 / earlier tests; matches plan directive and Phase 50 banner style at line 500-502"
  - "monkeypatch.setattr spy pattern used for D-03/D-05 — replaces bound method on a panel instance, NOT a Qt signal connection (project rule QA-05 self-capturing-lambda restriction does NOT apply per plan rationale at action lines 403-404)"
  - "Test 5 (D-04 under filter) uses early-return pattern when target group is filtered out post-refresh — preserves D-04 honoring without false-fails when proxy reshapes the row out (consistent with Pitfall #2 'restore is no-op for invalid proxy indices')"
  - "Test 6 (Pitfall #2) wraps panel.refresh_model() in try/except so any exception is re-raised as AssertionError with diagnostic — guards the .isValid() defense in _restore_expanded_provider_names from silent breakage in future refactors"
  - "Test 3 (D-06) asserts BOTH conditions in one test — new-group expanded AND pre-existing-collapsed-stay-collapsed — cheaper than two near-identical setups; matches plan behavior spec"

patterns-established:
  - "Nyquist spy lock for Qt signal handlers — when a behavioral contract has both a 'must-do-this' and 'must-not-do-this' shape (D-03 negative, D-05 positive), pair them as monkeypatch.setattr tests on the same private method, asserting calls == [] vs calls (truthy)"
  - "Phase / Bug-ID banner style — '# Phase NN / BUG-XX: <one-line scope>' framed by hyphens (matches Phase 50 line 500-502 precedent)"

requirements-completed: [BUG-06]

# Metrics
duration: 2min
completed: 2026-05-01
---

# Phase 55 Plan 02: Test Coverage for refresh_model Preserves Provider Expand/Collapse

**8 pytest-qt tests appended to tests/test_station_list_panel.py that lock the entire BUG-06 contract — 5 behavioral assertions (SC #1, SC #2, D-04, D-06, D-07), 1 defensive guard (Pitfall #2 / filtered-out provider), and 2 Nyquist spy locks (D-03 negative + D-05 positive on _sync_tree_expansion).**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-05-01T11:59:48Z
- **Completed:** 2026-05-01T12:01:39Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- 8 new pytest-qt tests added under a clear `# Phase 55 / BUG-06: refresh_model preserves provider expand/collapse` banner at the end of `tests/test_station_list_panel.py`
- Complete coverage of BUG-06 success criteria + decision contracts: SC #1 (test 1), SC #2 (test 2), D-03 (test 7), D-04 (tests 1+2+5), D-05 (test 8), D-06 (test 3), D-07 (test 4), Pitfall #2 (test 6); SC #3 already locked by the existing `test_provider_groups_collapsed_after_construction` regression test
- Two Nyquist evidence-based spy tests (D-03 negative contract + D-05 positive lock) wired via `monkeypatch.setattr(panel, "_sync_tree_expansion", lambda: calls.append(True))` — guards against future re-introduction of the bug AND against silent removal of filter-driven auto-expand
- Zero modifications to existing imports, fixtures, helpers, or any of the 22 pre-existing tests in the file
- Pytest collection confirms 30 tests collected (22 pre-existing + 8 new), file is syntactically valid Python

## Task Commits

1. **Task 1: Add 8 Phase 55 / BUG-06 tests to tests/test_station_list_panel.py** — `1b2ed3a` (test)

_Note: This plan is a TDD-only "test-add" plan; only a single `test(...)` commit is produced in this worktree. The corresponding `feat(...)` GREEN commit is owned by Plan 01 in a parallel worktree — once the orchestrator merges both Wave 1 worktrees, the full RED→GREEN cycle is captured in git history with separate commits._

## Files Created/Modified

- `tests/test_station_list_panel.py` — appended Phase 55 / BUG-06 banner + 8 new test functions at the end of the file (229 insertions, 0 deletions). Banner mirrors the Phase 50 / BUG-01 style at lines 500-502. Each test docstring references the decision ID it implements (D-03..D-07, SC #1, SC #2, Pitfall #2) per GSD context fidelity rules.

## Decisions Made

- **Append-only mutation:** All 8 tests appended at the end of the file with no edits to existing tests, fixtures, or imports — preserves the Phase 50 + Phase 38-02 + Phase 40.1-04 + Phase 999.1 banner sequence and avoids any merge-conflict surface with Plan 01's parallel-worktree edits to source-side files (`station_tree_model.py`, `station_list_panel.py`).
- **Spy pattern via `monkeypatch.setattr` is NOT a Qt signal connection:** The project rule against self-capturing lambdas on Qt signal handlers (QA-05) targets `widget.signal.connect(lambda: ...)` patterns where lambda lifetime is tied to the widget. `monkeypatch.setattr(panel, "_sync_tree_expansion", lambda: calls.append(True))` is a pytest fixture-scoped method replacement, never wired as a Qt signal handler — and is the spy pattern explicitly recommended by 55-RESEARCH.md §"Code Examples". Documented inline at action notes 403-404.
- **`_sample_repo()` provides 2 provider groups (SomaFM + DI.fm) — no inline setup needed:** Confirmed by reading the existing fixture at lines 59-70: 3 stations across 2 distinct provider names. The plan's contingency for "if `_sample_repo()` only has one group, prepend setup" was not triggered.
- **Test 5 (D-04 under filter) uses an early-return pattern:** When the captured-expanded group is filtered out post-refresh, the test returns without asserting (matches the "restore is a no-op for invalid proxy indices" contract from Pitfall #2). When the group survives the filter, the test asserts `panel.tree.isExpanded(proxy_idx) is True`. This avoids brittle assertions about whether a broad filter `"a"` retains the SomaFM group's `Groove Salad` / `Drone Zone` matches across future Qt-version drift.

## Deviations from Plan

None — plan executed exactly as written.

The plan's `<action>` block specified the exact 8 test bodies; I appended them verbatim with no logic changes. The only code-shape adjustment was to use 4-space indentation (matching the rest of the file) where the plan source was indented an extra level inside its triple-backtick fence — this is purely a textual paste-fidelity matter, not a deviation.

## Issues Encountered

**Expected RED state in this worktree** — per the parallel-execution note, my tests were known to fail at this base (commit `72bf899`) because Plan 01 in a parallel worktree owns the source-side fix:

```
5 failed, 3 passed, 22 deselected
```

Failures:
- `test_refresh_model_preserves_user_expanded_groups` — refresh_model still calls `_sync_tree_expansion`, which collapses the manually-expanded group
- `test_refresh_model_expands_brand_new_provider_group` — `panel.model.provider_name_at` does not yet exist (added by Plan 01 Task 1)
- `test_refresh_model_preserves_collapsed_destination_on_cross_provider_move` — same `provider_name_at` AttributeError
- `test_refresh_model_preserves_state_under_active_filter` — same `provider_name_at` AttributeError
- `test_refresh_model_does_not_call_sync_tree_expansion` — D-03 negative contract: refresh_model in unfixed code DOES call `_sync_tree_expansion`

Pre-fix passes (consistent with plan documentation at line 51):
- `test_refresh_model_preserves_user_collapsed_groups` — accidentally green pre-fix because `_sync_tree_expansion` collapses everything when no filter is active
- `test_refresh_model_handles_filtered_out_expanded_provider_safely` — accidentally green pre-fix because the unfixed restore path doesn't walk captured indices (no crash possible)
- `test_filter_change_still_calls_sync_tree_expansion` — D-05 positive lock: the unfixed codebase already calls `_sync_tree_expansion` from `_on_search_changed` (this is the unchanged-behavior side of the contract)

These failure/pass counts match the plan's pre-merge prediction exactly. After Plan 01's worktree merges, all 8 tests will go green.

**Pre-existing uv.lock drift:** The repository's initial git status already showed `uv.lock` as modified (unrelated to this plan). Running `uv run pytest` updated the lock again. I did NOT stage `uv.lock` in my commit — only the task-related `tests/test_station_list_panel.py` was staged individually. Per the parallel-executor protocol, no `git add .` / `git add -A` was used.

## User Setup Required

None — no external service configuration required. Tests run inside the existing `pytest` + `pytest-qt` + `QT_QPA_PLATFORM=offscreen` setup already configured in `tests/conftest.py`.

## Next Phase Readiness

- Plan 02 worktree is ready for the orchestrator's post-wave merge with Plan 01's worktree
- After merge, the full suite (`pytest tests/test_station_list_panel.py -q`) is expected to be 30/30 green — 22 pre-existing tests still pass, all 8 new tests turn green once `provider_name_at` and the capture/restore wrapping ship in source
- Permanent regression locks for D-03 (negative) and D-05 (positive) are now in place — any future refactor that re-introduces the bug or silently breaks filter-driven auto-expand will be caught by `pytest tests/test_station_list_panel.py`

## Self-Check: PASSED

- [x] FOUND: tests/test_station_list_panel.py (modified)
- [x] FOUND commit 1b2ed3a (test(55-02): add 8 Phase 55 / BUG-06 refresh_model tests)
- [x] FOUND: 8 new test function definitions (verified by grep, count = 1 each)
- [x] FOUND: banner `# Phase 55 / BUG-06` (count = 1)
- [x] FOUND: monkeypatch.setattr (count = 4 — exceeds plan's >= 2 requirement)
- [x] FOUND: pre-existing regression locks intact (test_provider_groups_collapsed_after_construction, test_provider_groups_expand_when_search_active, test_refresh_recent_does_not_touch_tree — all count = 1)
- [x] FOUND: file is syntactically valid Python (`ast.parse` succeeded)
- [x] FOUND: pytest collects 30 tests (22 pre-existing + 8 new), no collection errors

---

*Phase: 55-edit-station-preserves-section-state*
*Completed: 2026-05-01*
