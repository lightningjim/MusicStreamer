---
phase: 70
plan: 09
subsystem: ui-filter
tags: [filter-chip, proxy, pitfall-7, tdd-green, hires]
dependency_graph:
  requires: [70-01, 70-02, 70-05, 70-06]
  provides: [hi-res-chip, quality-map-filter, set_hi_res_only, set_quality_map, update_quality_map]
  affects: [StationFilterProxyModel, StationListPanel, MainWindow-fan-out]
tech_stack:
  added: []
  patterns: [Phase-68-live-chip-mirror, Pitfall-7-invalidate-guard, QA-05-bound-method-connect]
key_files:
  created: []
  modified:
    - musicstreamer/ui_qt/station_filter_proxy.py
    - musicstreamer/ui_qt/station_list_panel.py
decisions:
  - "Hi-res chip placed in same live_chip_row HBoxLayout as _live_chip (not a new sibling row) — minimum-row-count visual per UI-SPEC Component Inventory item 5"
  - "lc_layout.setSpacing(8) added to achieve 8px gap between chips per UI-SPEC"
  - "Pitfall 7 invalidate-guard: set_quality_map guards invalidate() behind if _hi_res_only; set_hi_res_only always invalidates"
  - "filterAcceptsRow hi-res branch placed BEFORE live-only branch — both yield AND semantics, order is arbitrary"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-12T15:50:20Z"
  tasks_completed: 2
  files_modified: 2
---

# Phase 70 Plan 09: Hi-Res Filter Chip + Proxy Methods Summary

Hi-res-only filter chip added to StationListPanel + StationFilterProxyModel extended with set_quality_map / set_hi_res_only + Pitfall 7 invalidate-guard. Mirrors Phase 68 live_chip / set_live_map / set_live_only architecture verbatim.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Extend StationFilterProxyModel with hi-res-only filter + Pitfall 7 guard | d940048 | musicstreamer/ui_qt/station_filter_proxy.py |
| 2 | Add _hi_res_chip + update_quality_map + set_hi_res_chip_visible to StationListPanel | 282fbc4 | musicstreamer/ui_qt/station_list_panel.py |

## What Was Built

**StationFilterProxyModel** (`station_filter_proxy.py`):
- `self._hi_res_only: bool = False` and `self._hi_res_station_ids: set[int] = set()` adjacent to Phase 68 `_live_only` / `_live_channel_keys`
- `set_quality_map(quality_map: dict[int, str])` — builds `_hi_res_station_ids` from keys with `tier == "hires"`; calls `invalidate()` ONLY when `_hi_res_only is True` (Pitfall 7 guard)
- `set_hi_res_only(enabled: bool)` — sets flag, always invalidates
- `clear_all()` extended — resets `_hi_res_only = False` (cache `_hi_res_station_ids` preserved, matches Phase 68 pattern)
- `has_active_filter()` extended — OR chain now includes `_hi_res_only`
- `filterAcceptsRow` station-branch — short-circuit `if self._hi_res_only and int(node.station.id) not in self._hi_res_station_ids: return False` before live-only check

**StationListPanel** (`station_list_panel.py`):
- `self._hi_res_chip = QPushButton("Hi-Res only", live_chip_row)` in the same `live_chip_row` HBoxLayout as `_live_chip`
- `lc_layout.setSpacing(8)` for 8px chip-to-chip gap (UI-SPEC)
- `setCheckable(True)`, `setProperty("chipState", "unselected")`, `setStyleSheet(_CHIP_QSS)`, `setVisible(False)` (F-02 default)
- `setToolTip("Show only stations with at least one Hi-Res stream")` — UI-SPEC Copywriting Contract
- `setAccessibleName("Hi-Res only filter")` — UI-SPEC a11y
- `_hi_res_chip.toggled.connect(self._on_hi_res_chip_toggled)` — bound-method (QA-05, no lambda)
- `_on_hi_res_chip_toggled(checked)` — calls `_set_chip_state` + `proxy.set_hi_res_only(checked)`
- `update_quality_map(quality_map)` — forwards to `proxy.set_quality_map(quality_map)` + calls `set_hi_res_chip_visible(any(t == "hires" for t in values))`
- `set_hi_res_chip_visible(visible)` — sets visibility AND unchecks chip if hiding while checked (Pitfall 7 stuck-filter invariant mirror)

**MainWindow fan-out path**: Plan 70-05's `hasattr(self.station_panel, "update_quality_map")` guard now finds the real method. The fan-out is complete.

## Test Results

| Test File | Pre-existing Failures | New Phase 70 Tests | Result |
|-----------|----------------------|-------------------|--------|
| tests/test_station_filter_proxy.py | 0 | 3 (test_set_hi_res_only_with_quality_map_filters_stations, test_set_quality_map_no_invalidate_when_chip_off, test_clear_all_clears_hi_res_only) | All GREEN |
| tests/test_station_list_panel.py | 2 (pre-existing, unrelated) | 4 (test_hi_res_chip_hidden_when_no_hi_res_streams, test_hi_res_chip_visible_after_update_quality_map_with_hires, test_set_hi_res_chip_visible_unchecks_when_hiding, test_hi_res_chip_toggle_calls_proxy_set_hi_res_only) | All new GREEN; pre-existing unchanged |

Pre-existing failures in `test_station_list_panel.py`:
- `test_filter_strip_hidden_in_favorites_mode` — fails because `_filter_strip` is collapsed by default; `_search_box.isVisibleTo()` returns False. Pre-existing, not caused by this plan.
- `test_refresh_recent_updates_list` — fails with row count mismatch. Pre-existing, not caused by this plan.

## Deviations from Plan

None — plan executed exactly as written.

The `lc_layout.setSpacing(8)` was added as specified in the task `<behavior>` note about UI-SPEC 8px gap. This is an in-spec implementation choice, not a deviation.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. `set_quality_map` uses defensive `(quality_map or {}).items()` guard (T-70-25). Pitfall 7 invalidate-guard tested (T-70-26). Bound-method connect per QA-05 (T-70-27). All threat mitigations from plan threat register applied.

## Self-Check

**Files exist:**
- `musicstreamer/ui_qt/station_filter_proxy.py` — FOUND (modified)
- `musicstreamer/ui_qt/station_list_panel.py` — FOUND (modified)

**Commits exist:**
- d940048 (Task 1: proxy extension) — FOUND
- 282fbc4 (Task 2: panel chip + methods) — FOUND

## Self-Check: PASSED
