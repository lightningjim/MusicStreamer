---
phase: 96
plan: "04"
subsystem: ui-dialog
tags: [wave-2, dialog, qthread, tdd-green]
dependency_graph:
  requires:
    - "96-01 (RED tests for D-05..D-10)"
    - "96-02 (list_flagged_stations_for_provider, update_stream, set_live_url_* setters)"
    - "96-03 (provider_refresh_requested Signal, LiveRefreshDialog wiring in StationListPanel)"
  provides:
    - "_LiveRefreshScanWorker(QThread) — off-UI-thread channel scan with node_runtime forwarding (D-09)"
    - "LiveRefreshDialog(QDialog) — review-and-confirm dialog for flagged-station refresh (D-04)"
    - "_build_row_suggestions — anchor-based suggestion pre-ordering, no auto-apply (D-05)"
    - "build_row_data — name pre-population by action type (D-08)"
    - "apply_refresh — pure apply helper (remap/drop/add with metadata preservation, D-06/D-07)"
    - "default_check_state — conservative default check states (DROP/ADD unchecked, REMAP checked, D-10)"
  affects:
    - musicstreamer/ui_qt/live_refresh_dialog.py
tech_stack:
  added: []
  patterns:
    - "_LiveRefreshScanWorker mirrors _YtScanWorker from import_dialog.py:75-101 (exact copy + rename)"
    - "LiveRefreshDialog mirrors ImportDialog constructor/scan-kick-off/scan-complete pattern"
    - "apply_refresh pure function (no Qt) — testable without QApplication event loop"
    - "Pitfall 5 full-row preserve: list_streams + preserve all non-URL fields before update_stream"
    - "Pitfall 6 bypass: apply path NEVER calls station_exists_by_url (remap by stream_id)"
    - "D-10 conservative defaults: DROP/ADD unchecked, REMAP checked; empty staged list = zero mutations"
key_files:
  created:
    - musicstreamer/ui_qt/live_refresh_dialog.py
  modified: []
decisions:
  - "Phase 96 D-05: _build_row_suggestions returns ALL scan results ordered by difflib.SequenceMatcher ratio vs anchor; nothing auto-applied"
  - "Phase 96 D-06: apply_refresh fetches list_streams and calls update_stream with preserved label/quality/position/stream_type/codec/bitrate_kbps/sample_rate_hz/bit_depth"
  - "Phase 96 D-07: DROP fires delete_station only on explicit tick; ADD fires insert_station + set_live_url_syncs_from_channel(True) + set_live_url_title_anchor"
  - "Phase 96 D-08: ADD row name = scan result title; REMAP/REPLACE row name = existing station name"
  - "Phase 96 D-09: node_runtime stored in _LiveRefreshScanWorker.__init__; forwarded to scan_playlist (MEMORY.md .desktop-launcher landmine guard)"
  - "Phase 96 D-10: default_check_state returns True only for remap; apply_refresh with empty staged list returns immediately (zero mutations)"
metrics:
  duration: "12 minutes"
  completed: "2026-06-21T18:15:00Z"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 1
---

# Phase 96 Plan 04: LiveRefreshDialog + Apply Path Summary

**One-liner:** New `live_refresh_dialog.py` with `_LiveRefreshScanWorker(QThread)`, `LiveRefreshDialog(QDialog)`, pure `apply_refresh` helper, and conservative-default UI turns all 7 D-05..D-10 dialog tests GREEN.

## What Was Built

Plan 04 delivers the complete Phase 96 review-and-confirm dialog: the off-UI-thread scan worker, the two-panel review UI, and the pure apply helper. Both tasks were implemented together in a single new file because the apply helpers are shared between the UI rows and unit tests.

### Task 1: _LiveRefreshScanWorker + dialog scaffold + anchor pre-ordering (D-05/D-08/D-09)

**`_LiveRefreshScanWorker(QThread)`** — mirrors `_YtScanWorker` from `import_dialog.py:75-101` exactly (copy + rename). Stores `node_runtime` in `__init__` and forwards it to `yt_import.scan_playlist(...)` in `run()`. This is the MEMORY.md .desktop-launcher landmine guard — without threading `node_runtime`, YouTube channel scans fail silently in environments with minimal PATH.

**`_build_row_suggestions(station, scan_results) -> list`** — pure function, exposed as `LiveRefreshDialog._build_row_suggestions` (class-level static). Pre-orders scan results by `difflib.SequenceMatcher` ratio vs. the station's `live_url_title_anchor`. Returns ALL results — anchor-closest first — and stages NO mapping (D-05 no-auto-apply invariant).

**`build_row_data(action, *, scan_result, station) -> dict`** — pure function for D-08 name pre-population: ADD rows default to scan result title; REMAP/REPLACE rows default to existing station name.

**`LiveRefreshDialog(QDialog)`** — constructor contract from Plan 04 interfaces block. On open: loads `repo.list_flagged_stations_for_provider(provider_id)` for left panel; kicks off `_LiveRefreshScanWorker` for right panel with `Qt.QueuedConnection` signal connections (threading discipline). Shows indeterminate `QProgressBar` during scan. Empty-flagged-list → shows "No stations marked for live URL re-sync — enable the flag via Edit Station" message. Scan error → `ERROR_COLOR_HEX` status.

**Review UI** — scroll-area of `_RowWidget` instances, one per flagged station (REMAP), plus one ADD row per scan result. Each row has: check box (default per `default_check_state`), action label, station/anchor info, editable name `QLineEdit`, and "map to currently-live" `QComboBox` pre-ordered by `_build_row_suggestions`.

### Task 2: Apply path (D-06/D-07/D-10)

**`apply_refresh(repo, staged_changes) -> None`** — pure function (no Qt). Handles three action types:

- **REMAP**: fetches `list_streams`, locates the primary stream by `stream_id`, calls `update_stream(primary.id, new_url, primary.label, primary.quality, primary.position, primary.stream_type, primary.codec, bitrate_kbps=..., sample_rate_hz=..., bit_depth=...)` preserving ALL non-URL fields (Pitfall 5), then calls `set_live_url_title_anchor(station_id, new_title)` (D-06). NEVER calls `station_exists_by_url` (Pitfall 6).
- **DROP**: calls `delete_station(station_id)` (D-07) — fires only for explicit "drop" records.
- **ADD**: calls `insert_station(name, url, provider_name, "")`, then `set_live_url_syncs_from_channel(new_id, True)` and `set_live_url_title_anchor(new_id, title)` so the new station is itself refresh-eligible (D-07).
- **Empty list guard**: early return with zero repo mutations (D-10 W4).

**`default_check_state(action) -> bool`** — returns `True` only for `"remap"`. DROP and ADD are `False` (D-10 conservative defaults). Exposed for test assertion and used by `_RowWidget` constructor.

**Apply button** in dialog: collects staged rows via `build_staged_change()` per `_RowWidget`, calls `apply_refresh`, emits `refresh_complete`, calls `accept()`. Shows toast on success/failure.

## Verification

```
.venv/bin/python -m pytest tests/test_live_refresh_dialog.py -x -q
7 passed, 1 warning in 0.32s
```

All 7 Phase 96 D-05..D-10 dialog tests GREEN:
- `test_scan_worker_uses_qthread` PASS (D-09 QThread shape + node_runtime kwarg)
- `test_scan_worker_forwards_node_runtime` PASS (D-09 / B2 landmine guard)
- `test_suggestions_pre_order_no_auto_apply` PASS (D-05 anchor-closest first, no auto-apply)
- `test_apply_remap_preserves_metadata` PASS (D-06 full-row preserve)
- `test_apply_drop_and_add_actions` PASS (D-07 delete_station / insert_station + flag)
- `test_name_field_prepopulation` PASS (D-08 ADD→title, REMAP→station name)
- `test_conservative_defaults` PASS (D-10 DROP/ADD unchecked, REMAP checked, empty-apply guard)

```
.venv/bin/python -m pytest tests/test_live_refresh_dialog.py tests/test_repo.py -q
122 passed, 1 warning in 1.13s
```

No repo regressions.

Acceptance criteria verified:
- `grep -n "class _LiveRefreshScanWorker\|class LiveRefreshDialog\|def _build_row_suggestions\|refresh_complete" live_refresh_dialog.py` — all four present ✓
- `grep -n "scan_playlist" live_refresh_dialog.py` — shows `node_runtime=self._node_runtime` at L89 ✓
- `grep -n "station_exists_by_url" live_refresh_dialog.py` — only in comments, never called ✓

## Deviations from Plan

**None — plan executed exactly as written.**

The plan tasks (Task 1: scaffold + worker, Task 2: apply path) were naturally implemented together since `apply_refresh`, `default_check_state`, and `build_row_data` are all pure helpers in the same file. Both TDD tasks went GREEN in one pass.

## Commits

| Task | Commit | Files |
|------|--------|-------|
| Task 1+2: _LiveRefreshScanWorker + LiveRefreshDialog + apply helpers | c28f121f | musicstreamer/ui_qt/live_refresh_dialog.py (627 lines created) |

## Known Stubs

None — all public surfaces are fully wired:
- `_LiveRefreshScanWorker.run()` calls `yt_import.scan_playlist` with `node_runtime`
- `apply_refresh` calls real repo methods (`update_stream`, `delete_station`, `insert_station`, `set_live_url_syncs_from_channel`, `set_live_url_title_anchor`)
- `LiveRefreshDialog._start_scan()` connects worker signals with `Qt.QueuedConnection`
- `LiveRefreshDialog._on_apply()` calls `apply_refresh` and emits `refresh_complete`

## Threat Flags

None — `live_refresh_dialog.py` introduces no new network endpoints or auth paths. All threat model mitigations from the plan are implemented:
- T-96-09: DROP defaults `Qt.Unchecked`; `delete_station` only fires on explicit tick
- T-96-10: `set_live_url_title_anchor` caps at 500 chars (enforced at repo layer from Plan 02); name fields are user-editable
- T-96-11: fully manual map, no auto-apply, `_build_row_suggestions` only pre-orders
- T-96-12: full-row preserve before `update_stream` (Pitfall 5 in apply_refresh)
- T-96-13: apply path never calls `station_exists_by_url` (Pitfall 6)

## Self-Check: PASSED

- musicstreamer/ui_qt/live_refresh_dialog.py created: FOUND (627 lines)
- Commit c28f121f: FOUND (`git log --oneline | grep c28f121f`)
- `grep "class _LiveRefreshScanWorker"` = L62: CONFIRMED
- `grep "class LiveRefreshDialog"` = L407: CONFIRMED
- `grep "def _build_row_suggestions"` = L104: CONFIRMED
- `grep "refresh_complete = Signal"` = L423: CONFIRMED
- `grep "scan_playlist" live_refresh_dialog.py` shows node_runtime=self._node_runtime at L89-91: CONFIRMED
- `grep "station_exists_by_url" live_refresh_dialog.py` = comments only, never called: CONFIRMED
- 122 tests PASS (test_live_refresh_dialog + test_repo), 0 regressions: CONFIRMED
