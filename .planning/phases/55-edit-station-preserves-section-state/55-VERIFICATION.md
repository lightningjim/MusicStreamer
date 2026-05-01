---
phase: 55-edit-station-preserves-section-state
verified: 2026-05-01T00:00:00Z
status: human_needed
score: 11/11 must-haves verified (automated)
overrides_applied: 0
human_verification:
  - test: "Edit a station while several provider groups are expanded — confirm visually that the same groups are still expanded after Save with no flicker"
    expected: "Same provider groups remain expanded after the dialog closes; no perceptible collapse/re-expand flash during the save"
    why_human: "User-perceived 'no flicker' / no transient collapse during model.refresh — automated tests assert post-state but cannot observe transient frames"
  - test: "Repeat the edit-and-save flow with an active search filter applied"
    expected: "Filter remains active; group expansion state preserved per the captured pre-save state"
    why_human: "Confirms filter-active save path under real timing (Qt event loop) — distinct from offscreen pytest-qt environment"
  - test: "Collapse all groups, then edit a station and save"
    expected: "After save no group becomes expanded (the save event must not auto-expand any group)"
    why_human: "Locks SC #2 in real UI; automated coverage exists but per VALIDATION.md this is on the manual UAT checklist"
---

# Phase 55: Edit Station Preserves Section State — Verification Report

**Phase Goal:** Saving changes in EditStationDialog leaves expandable sections in the same open/closed state the user had before saving — no reset on save.

**Verified:** 2026-05-01
**Status:** human_needed — all automated must-haves verified; phase-VALIDATION.md flags 3 manual UAT items as Manual-Only Verifications.
**Re-verification:** No — initial verification

## Goal Achievement

### Roadmap Success Criteria

| #   | Truth                                                                          | Status     | Evidence                                                                                                                                                                                                                                                  |
| --- | ------------------------------------------------------------------------------ | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| SC1 | Sections expanded before Save remain expanded after the save                   | VERIFIED   | `tests/test_station_list_panel.py:552 test_refresh_model_preserves_user_expanded_groups` — 42-test suite passes (offscreen). Code path: `refresh_model` (`station_list_panel.py:314-327`) calls `_capture_expanded_provider_names` then re-applies via `_restore_expanded_provider_names`. |
| SC2 | Sections collapsed before Save remain collapsed after the save                 | VERIFIED   | `tests/test_station_list_panel.py:571 test_refresh_model_preserves_user_collapsed_groups` — passes; `_restore_expanded_provider_names` only expands names in `expanded_pre` or brand-new groups, otherwise leaves Qt's default-collapsed state.                                       |
| SC3 | Fix does not affect initial open state on freshly-launched dialog              | VERIFIED   | `tests/test_station_list_panel.py:103 test_provider_groups_collapsed_after_construction` — pre-existing regression lock; still passes. Construction uses default-collapsed Qt state, untouched by Plan 01.                                                  |

### Locked Decision Contracts (Plan 01 + Plan 02 must_haves)

| #     | Truth                                                                                                                              | Status     | Evidence                                                                                                                                                                                                                            |
| ----- | ---------------------------------------------------------------------------------------------------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D-01  | Fix lives in `StationListPanel.refresh_model()` — all five callers benefit automatically                                            | VERIFIED   | `station_list_panel.py:314-327` is the single edit-site; `MainWindow._refresh_station_list()` callers unchanged.                                                                                                                    |
| D-02  | `refresh_model()` modified in place — no sibling like `refresh_model_preserving_expansion()`                                        | VERIFIED   | `grep -n "def refresh_model" station_list_panel.py` returns one match (line 314). No sibling method exists.                                                                                                                          |
| D-03  | `refresh_model` body does NOT call `_sync_tree_expansion()` (negative contract)                                                     | VERIFIED   | `grep -A 12 "def refresh_model" station_list_panel.py | grep -c "_sync_tree_expansion()"` returns 0. Spy test `test_refresh_model_does_not_call_sync_tree_expansion` (line 734) passes.                                                |
| D-04  | Refresh-after-mutation preserves manual expand state under any filter condition                                                     | VERIFIED   | `test_refresh_model_preserves_state_under_active_filter` (line 670) passes; capture occurs pre-`model.refresh`, restore re-applies post-refresh independent of filter state.                                                          |
| D-05  | Filter-change handlers continue to call `_sync_tree_expansion()` (positive lock)                                                    | VERIFIED   | `_on_search_changed` (492), `_on_provider_chip_clicked` (496), `_on_tag_chip_clicked` (506), `_clear_all_filters` (521) all call `self._sync_tree_expansion()`. Spy test `test_filter_change_still_calls_sync_tree_expansion` passes. |
| D-06  | Brand-new provider group introduced by save defaults to expanded                                                                    | VERIFIED   | `_restore_expanded_provider_names` (385-407): set difference `name not in all_pre` → expand. `test_refresh_model_expands_brand_new_provider_group` (line 589) passes.                                                                |
| D-07  | Existing destination group when a station moves into it stays in its captured state                                                 | VERIFIED   | `test_refresh_model_preserves_collapsed_destination_on_cross_provider_move` (line 629) passes. Restore guard: only expand when `was_expanded or is_brand_new`.                                                                       |
| P1    | Capture/restore keys by raw provider name string, never QModelIndex (RESEARCH Pitfall #1)                                           | VERIFIED   | `provider_name_at(row)` returns raw string from `_TreeNode.provider_name` (separate from `(N)`-suffixed `label`). Both helpers call `self.model.provider_name_at` (2 occurrences in panel).                                          |
| P2    | Restore loop guards `proxy.mapFromSource(...)` results with `.isValid()` before view ops (Pitfall #2)                               | VERIFIED   | `proxy_idx.isValid()` appears 2 times in panel — once in capture (line 374), once in restore (line 405). `test_refresh_model_handles_filtered_out_expanded_provider_safely` (line 709) confirms no crash.                            |
| ORD   | `refresh_model` still calls `_populate_recent()` then `_build_chip_rows()` after restore (in that order)                            | VERIFIED   | Lines 326-327: `self._populate_recent(); self._build_chip_rows()` are the final two calls inside `refresh_model`.                                                                                                                    |
| HELP  | `_capture_expanded_provider_names` and `_restore_expanded_provider_names` exist as bound methods on `StationListPanel` (Plan 01)    | VERIFIED   | Defined at lines 349 and 380; `test_capture_and_restore_helpers_exist` (line 544) asserts existence.                                                                                                                                  |

**Score:** 11/11 automated must-haves verified (3 SC + 7 decisions + supporting contracts).

### Required Artifacts

| Artifact                                       | Expected                                                                                                | Status     | Details                                                                                                                                                              |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `musicstreamer/ui_qt/station_tree_model.py`    | `_TreeNode.provider_name` field + `StationTreeModel.provider_name_at(row) -> Optional[str]`            | VERIFIED   | Field at line 33 (`provider_name: Optional[str] = None`); accessor at lines 62-72; `_populate` sets `provider_name=pname` at line 88; `(N)` label suffix preserved.   |
| `musicstreamer/ui_qt/station_list_panel.py`    | `refresh_model` rewritten with capture-then-restore; 2 new private helpers; `_sync_tree_expansion` only called from filter handlers | VERIFIED   | `refresh_model` at 314-327; helpers at 349-378 and 380-407; only 4 non-comment `_sync_tree_expansion()` callers (all filter handlers).                                |
| `tests/test_station_list_panel.py`             | 9 phase-55 tests (1 from Plan 01 + 8 from Plan 02) under `# Phase 55 / BUG-06` banner                  | VERIFIED   | Banner at line 538; 9 phase-55 test functions present at lines 544, 552, 571, 589, 629, 670, 709, 734, 755.                                                          |
| `tests/test_station_tree_model.py`             | 4 accessor tests for `provider_name_at`                                                                  | VERIFIED   | Tests at lines 139, 156, 163, 174 (raw name without count suffix; out-of-range; parens-in-name preserved; post-refresh state).                                       |

### Key Link Verification

| From                                                   | To                                                  | Via                                                                       | Status   | Details                                                                                                                                |
| ------------------------------------------------------ | --------------------------------------------------- | ------------------------------------------------------------------------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `StationListPanel.refresh_model`                       | `StationListPanel._capture_expanded_provider_names` | direct call BEFORE `self.model.refresh(...)`                              | WIRED    | Line 323: `expanded_pre, all_pre = self._capture_expanded_provider_names()`                                                            |
| `StationListPanel.refresh_model`                       | `StationListPanel._restore_expanded_provider_names` | direct call AFTER `self.model.refresh(...)`                                | WIRED    | Line 325: `self._restore_expanded_provider_names(expanded_pre, all_pre)`                                                                |
| `StationListPanel._capture_expanded_provider_names`    | `StationTreeModel.provider_name_at`                 | scalar-from-row accessor — bypasses `(N)` label suffix                    | WIRED    | Line 368: `name = self.model.provider_name_at(prov_row)`                                                                                |
| `StationListPanel._restore_expanded_provider_names`    | `self._proxy.mapFromSource`                         | source-to-proxy mapping at view boundary, `.isValid()`-guarded            | WIRED    | Line 404: `proxy_idx = self._proxy.mapFromSource(source_idx)`; guarded by `if not proxy_idx.isValid(): continue` at line 405.            |
| Tests (Plan 02 spy tests)                              | `StationListPanel._sync_tree_expansion`              | `monkeypatch.setattr(panel, "_sync_tree_expansion", ...)`                  | WIRED    | Two spy tests at lines 734 and 755 use `monkeypatch.setattr` against `_sync_tree_expansion`.                                            |
| Tests (Plan 02 mutation tests)                         | `FakeRepo._stations`                                | in-place mutation (append / `.provider_name` reassignment)                 | WIRED    | `repo._stations.append(...)` at line ~613 (D-06 test) and `.provider_name = destination_provider` at ~654 (D-07 test).                  |

### Data-Flow Trace (Level 4)

| Artifact                       | Data Variable               | Source                                       | Produces Real Data | Status    |
| ------------------------------ | --------------------------- | -------------------------------------------- | ------------------ | --------- |
| `StationListPanel.refresh_model` | `expanded_pre, all_pre`     | `self.model.rowCount()` + `provider_name_at` | Yes — derived from live `StationTreeModel._root.children` populated by `self._repo.list_stations()` | FLOWING   |
| `_TreeNode.provider_name`      | `pname` from `Station.provider_name` | `_populate(stations)` from real `Station` rows | Yes — direct attribute copy | FLOWING |

### Behavioral Spot-Checks

| Behavior                                                                                        | Command                                                                                                          | Result          | Status |
| ----------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- | --------------- | ------ |
| Test gate: phase-55 tests + station_list_panel + station_tree_model pass on offscreen Qt        | `QT_QPA_PLATFORM=offscreen uv run pytest tests/test_station_list_panel.py tests/test_station_tree_model.py --deselect <2 pre-existing> -q` | 42 passed, 2 deselected | PASS   |
| `refresh_model` body has no `_sync_tree_expansion()` call                                        | `grep -A 12 "def refresh_model" musicstreamer/ui_qt/station_list_panel.py | grep -c "_sync_tree_expansion()"`     | `0`             | PASS   |
| Exactly 4 non-comment `_sync_tree_expansion()` call sites (the filter-change handlers)           | `grep -v '^[[:space:]]*#' musicstreamer/ui_qt/station_list_panel.py | grep -c "_sync_tree_expansion()"`           | `4`             | PASS   |
| `proxy_idx.isValid()` guard appears in capture and restore                                       | `grep -c "proxy_idx.isValid()" musicstreamer/ui_qt/station_list_panel.py`                                         | `2`             | PASS   |
| `provider_name_at` is the capture/restore key (no `Qt.DisplayRole` parsing)                      | `grep -c "self.model.provider_name_at" musicstreamer/ui_qt/station_list_panel.py`                                | `2`             | PASS   |
| No `preserve_expansion` kwarg added                                                              | `grep -c "preserve_expansion" musicstreamer/ui_qt/station_list_panel.py`                                          | `0`             | PASS   |

### Requirements Coverage

| Requirement | Source Plan       | Description                                                                                                                | Status      | Evidence                                                                                                                                                          |
| ----------- | ----------------- | -------------------------------------------------------------------------------------------------------------------------- | ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| BUG-06      | 55-01-PLAN, 55-02-PLAN | Saving an edit in `EditStationDialog` preserves the open/closed state of expandable sections (does not collapse all open sections on save) | SATISFIED   | All 3 SC verified above (SC1, SC2 via Plan-02 tests; SC3 via existing regression lock). `REQUIREMENTS.md:22` traceability row matches Phase 55 Wave 1 deliverables. |

No orphaned requirements: `REQUIREMENTS.md:89` traces BUG-06 → Phase 55 only. Both plans declare `requirements: [BUG-06]`. No additional IDs map to this phase.

### Anti-Patterns Found

| File                                          | Line | Pattern                                              | Severity | Impact                                                                                                                              |
| --------------------------------------------- | ---- | ---------------------------------------------------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| (none in changed files)                       | —    | TODO/FIXME/HACK/PLACEHOLDER absent                   | —        | Anti-pattern grep on `station_tree_model.py` and `station_list_panel.py` returns zero matches.                                       |
| (none)                                        | —    | No empty-stub `return null/[]/{}` in helpers          | —        | Helpers return real `set[str]` data and apply real view-side `tree.expand` calls; no placeholder code paths.                         |

Code review (`55-REVIEW.md`) confirms: 0 critical, 0 warning, 3 info. Info findings are stylistic suggestions, not bugs (per phase-close-gate policy).

### Human Verification Required

Per `55-VALIDATION.md` "Manual-Only Verifications" the following items are intentionally outside automated coverage:

1. **Visual no-flicker on Save**
   - Test: Launch app → expand 2-3 provider groups → right-click a station → Edit → change name → Save.
   - Expected: Same groups remain expanded; no perceptible collapse/expand flash during the save commit.
   - Why human: The capture/restore is synchronous in `refresh_model`, but the `beginResetModel/endResetModel` cycle still triggers Qt to repaint. Whether this is perceived as flicker is a frame-timing observation only humans can render.

2. **Filter-active save flow**
   - Test: Type a search string into the filter, expand a surviving group, edit a station, save.
   - Expected: Filter remains applied; expansion state of surviving groups is preserved.
   - Why human: Real Qt event-loop timing differs from offscreen pytest-qt; Pitfall #2 guard is automated, but filter-redraw ordering is event-loop dependent.

3. **All-collapsed regression check**
   - Test: Collapse every group → edit a station → save.
   - Expected: No group is expanded after save.
   - Why human: Locks SC #2 in real UI per VALIDATION.md UAT checklist.

### Gaps Summary

No gaps found. All 3 roadmap success criteria, 7 locked decisions, and 4 supporting contracts (Pitfall #1/#2, ordering, helper existence) are verified by:
- Source-side implementation in `musicstreamer/ui_qt/station_tree_model.py` (provider_name_at accessor + _TreeNode.provider_name field)
- Source-side implementation in `musicstreamer/ui_qt/station_list_panel.py` (refresh_model rewrite + 2 helpers)
- Plan-01 structural test + 4 tree-model accessor tests + 8 Plan-02 contract tests
- Existing regression lock at `tests/test_station_list_panel.py:103` (SC #3)
- Spy-based Nyquist locks: D-03 negative (test 7) + D-05 positive (test 8)

The 2 deselected pre-existing failures (`test_filter_strip_hidden_in_favorites_mode`, `test_refresh_recent_updates_list`) are documented in `deferred-items.md` and confirmed against base commit `72bf899`. They do not touch any code path modified by Phase 55.

The 9 unrelated failures in the full-suite regression gate (test_media_keys_*, test_twitch_auth) are confirmed pre-existing on base `72bf899`, not introduced by Phase 55.

**Status: human_needed** — no codebase gaps; 3 manual UAT items per VALIDATION.md "Manual-Only Verifications" require human visual confirmation before phase close.

---

_Verified: 2026-05-01_
_Verifier: Claude (gsd-verifier)_
