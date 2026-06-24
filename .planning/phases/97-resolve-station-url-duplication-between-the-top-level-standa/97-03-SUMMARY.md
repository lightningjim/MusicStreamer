---
phase: 97-resolve-station-url-duplication-between-the-top-level-standa
plan: "03"
subsystem: ui-dialog
tags: [tdd, wave-3, canonical, url-edit-removal, edit-station-dialog, green-tests]
dependency_graph:
  requires:
    - "97-01 (Wave-0 RED tests in test_edit_station_dialog.py)"
    - "97-02 (Station.canonical_stream_id + repo.set_canonical_stream)"
  provides:
    - "url_edit QLineEdit removed from EditStationDialog (D-01)"
    - "_COL_CANONICAL=6 trailing column with QToolButton star marker (D-04)"
    - "_get_canonical_url_live() live canonical cell read accessor (D-02)"
    - "cellChanged-driven debounce replacing url_edit.textChanged (D-02)"
    - "D-03 auto-row on empty/new station"
    - "_on_save canonical persist via repo.set_canonical_stream (D-04)"
    - "Full 104-test dialog suite GREEN including 7 Plan-01 canonical tests"
  affects:
    - musicstreamer/ui_qt/edit_station_dialog.py
    - tests/test_edit_station_dialog.py
tech_stack:
  added:
    - "QToolButton (PySide6.QtWidgets) — canonical star marker widget"
  patterns:
    - "Phase 97 D-02: cellChanged(row,col) filtered by _populating guard + (row==_canonical_row and col==_COL_URL) — Pitfall 5"
    - "Phase 97 D-04: QToolButton star with manual single-select (no QButtonGroup) — Pitfall 8"
    - "Phase 97 Pitfall 4: _canonical_row updated on _on_move_up/_on_move_down to follow content"
    - "Phase 97 Pitfall 7: _snapshot_form_state 'url' key -> 'canonical_url' key"
    - "Phase 97 Pitfall 6: deleted-stream fallback in _on_save canonical persist"
key_files:
  created: []
  modified:
    - path: musicstreamer/ui_qt/edit_station_dialog.py
      purpose: "url_edit removed; _COL_CANONICAL=6; canonical marker QToolButton; _get_canonical_url_live; cellChanged wiring; auto-row; reorder tracking; set_canonical_stream on save"
    - path: tests/test_edit_station_dialog.py
      purpose: "14 url_edit-referencing tests migrated to canonical cell edits; FakeRepo set_canonical_stream assertion; full 104-test suite GREEN"
decisions:
  - "_on_url_text_changed becomes a no-op shim (not removed) for backward-compat"
  - "D-03 auto-row skips when is_new=True to avoid double-adding with existing D-05 pre-add in __init__"
  - "_populating guard wraps both the main streams loop and the D-03 auto-row (separate try/finally blocks)"
  - "setCellWidget swap in _swap_rows uses two setCellWidget calls (btn1 into r2, btn2 into r1) — no reparent step needed"
metrics:
  duration: "~12 minutes"
  completed: "2026-06-24"
  tasks_completed: 3
  tasks_total: 3
  files_created: 0
  files_modified: 2
---

# Phase 97 Plan 03: EditStationDialog Canonical Rewire Summary

**One-liner:** url_edit QLineEdit removed from EditStationDialog; streams table made the sole URL editor via _COL_CANONICAL=6 star marker, _get_canonical_url_live() accessor, cellChanged debounce, and set_canonical_stream on save — all 104 dialog tests GREEN.

## What Was Built

Rewired `EditStationDialog` to eliminate the duplicate URL surface. The top-level `url_edit` field is gone; the streams table now owns all URL editing via a new "Primary" canonical marker column.

### Task 1 — Canonical column + live accessor + cellChanged wiring (commit `d0ae8ab5`)

Added to `musicstreamer/ui_qt/edit_station_dialog.py`:

- `_COL_CANONICAL = 6` (trailing — all `_COL_URL=0` refs unaffected)
- `QToolButton` import added to PySide6.QtWidgets block
- `url_edit` QLineEdit and `form.addRow("URL:", ...)` removed (D-01); `_url_timer` kept and rewired
- `self._canonical_row: int = -1` and `self._populating: bool = False` instance attrs
- `QTableWidget(0, 7)` + "Primary" header + `Fixed` resize + 50px width + tooltip
- `cellChanged.connect(self._on_canonical_cell_changed)` (Pitfall 5 guard inside handler)
- `_add_stream_row`: canonical `QToolButton("★")` appended via `setCellWidget` (Pitfall 8 — no QButtonGroup)
- `_on_canonical_btn_clicked(row)`: manual single-select, updates `_canonical_row`, fires debounce
- `_on_canonical_cell_changed(row, col)`: early-exit unless `not _populating and row==_canonical_row and col==_COL_URL`
- `_sync_canonical_buttons()`: post-populate checked-state sync
- `_get_canonical_url_live() -> str`: reads `streams_table.item(_canonical_row, _COL_URL).text()`
- `_populate`: `_populating` guard around streams loop + D-03 auto-row (skips if `is_new=True`) + `_canonical_row` resolution from `station.canonical_stream_id`
- `_swap_rows`: skip `_COL_CANONICAL` in item loop; swap `cellWidget` separately (Pitfall re: `takeItem` doesn't move widgets)
- `_on_move_up/_on_move_down`: update `_canonical_row` to follow content (Pitfall 4)
- `_snapshot_form_state`: `"url": url_edit.text()` → `"canonical_url": _get_canonical_url_live()` (Pitfall 7)
- 7 remaining `url_edit.text()` call sites rewired to `_get_canonical_url_live()` in `_refresh_siblings`, `_on_add_sibling_clicked`, `_on_url_timer_timeout`, `_on_fetch_logo_clicked`, `_on_logo_fetched`, `_on_refresh_avatar_clicked`, `_on_save` (Twitch derive + avatar sync)

6 of 7 Plan-01 canonical dialog tests GREEN.

### Task 2 — Persist canonical_stream_id on save (commit `dc18f512`)

Added to `_on_save` in `musicstreamer/ui_qt/edit_station_dialog.py`:

- Canonical persist block placed AFTER `repo.reorder_streams` and BEFORE Phase-96 setters
- Reads `_canonical_row` URL item's `Qt.UserRole` stream_id
- Deleted-stream fallback: if `_can_stream_id not in ordered_ids`, falls back to `ordered_ids[0] if ordered_ids else None` (Pitfall 6)
- Calls `repo.set_canonical_stream(station.id, _can_stream_id)`

7th Plan-01 canonical test (`test_save_persists_canonical_stream_id`) GREEN.

### Task 3 — Migrate url_edit-referencing tests; full suite GREEN (commit `d223860e`)

Updated `tests/test_edit_station_dialog.py`:

- 13 failing tests fixed: each `dialog.url_edit.setText(X)` replaced with canonical cell item `setText(X)` pattern
- `test_text_changed_cancels_pending_clear`: uses `item.setText(...)` twice; `cellChanged` auto-fires `_on_canonical_cell_changed` to clear logo status
- `test_live_resync_checkbox_gating`: `_on_url_text_changed()` (now no-op shim) replaced with canonical cell `setText` (signal auto-fires)
- `test_is_dirty_after_url_edit`: canonical cell `setText` triggers dirty state via streams snapshot change
- `is_new` D-03 double-add bug fixed: D-03 auto-row in `_populate` now guards `not self._is_new`
- All 104 dialog tests GREEN; 0 `dialog.url_edit.` accesses remain; all 7 Plan-01 canonical tests GREEN

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] D-03 auto-row double-added when is_new=True**
- **Found during:** Task 3 (test_is_new_mode_pre_adds_blank_stream_row failed: expected 1 row, got 2)
- **Issue:** When `is_new=True` and `list_streams` returns empty, both the D-03 `_populate` auto-row AND the `__init__` D-05 pre-add fired, creating 2 rows instead of 1
- **Fix:** Added `and not self._is_new` guard to the D-03 auto-row in `_populate`; `is_new=True` stations get their blank row from `__init__`'s D-05 pre-add
- **Files modified:** musicstreamer/ui_qt/edit_station_dialog.py
- **Commit:** `d223860e`

**2. [Rule 2 - Missing Critical Functionality] _on_url_text_changed made no-op shim**
- **Found during:** Task 3 (test_live_resync_checkbox_gating called `_on_url_text_changed()`)
- **Issue:** `_on_url_text_changed` still referenced `self.url_edit.text()` in its body; the test called it directly
- **Fix:** Replaced body with a no-op shim comment (no longer connected to any signal; the canonical cell path handles this via `_on_canonical_cell_changed`); test updated to use canonical cell `setText` which auto-fires the signal
- **Files modified:** musicstreamer/ui_qt/edit_station_dialog.py, tests/test_edit_station_dialog.py
- **Commit:** `d0ae8ab5`, `d223860e`

## Threat Mitigations Applied

| Threat | Applied |
|--------|---------|
| T-97-05: Input validation on canonical URL cell | No new validation surface added; url_helpers validates at worker boundary (unchanged) |
| T-97-06: Tampering — deleted/stale canonical stream_id on save | Pitfall 6 fallback: `ordered_ids[0] if ordered_ids else None` when `_can_stream_id not in ordered_ids` |
| T-97-07: cellChanged firing during programmatic populate | `_populating` guard + `(row==_canonical_row and col==_COL_URL)` early-exit in `_on_canonical_cell_changed` |

## Known Stubs

None — all canonical logic is fully wired end-to-end. The streams table is the sole URL editor, canonical marker persists on save, and metadata reads the live canonical cell.

## Self-Check: PASSED

### Files exist:
- FOUND: musicstreamer/ui_qt/edit_station_dialog.py
- FOUND: tests/test_edit_station_dialog.py

### Commits exist:
- FOUND: `d0ae8ab5` — feat(97-03): add canonical marker column + live accessor + cellChanged + auto-row; url_edit removed
- FOUND: `dc18f512` — feat(97-03): persist canonical_stream_id on save via set_canonical_stream
- FOUND: `d223860e` — feat(97-03): migrate all url_edit-referencing tests to canonical cell edits; full suite GREEN

### Acceptance criteria verified:
- `grep -c "self.url_edit" musicstreamer/ui_qt/edit_station_dialog.py` = 0 (D-01: fully removed)
- `grep -c "_COL_CANONICAL" musicstreamer/ui_qt/edit_station_dialog.py` = 14 (>= 4)
- `grep -c "def _get_canonical_url_live" musicstreamer/ui_qt/edit_station_dialog.py` = 1
- `grep -c "self._url_timer" musicstreamer/ui_qt/edit_station_dialog.py` = 8 (>= 2)
- `grep -c "cellChanged.connect" musicstreamer/ui_qt/edit_station_dialog.py` = 1
- `grep -c "_get_canonical_url_live" musicstreamer/ui_qt/edit_station_dialog.py` = 15 (>= 9)
- `grep -c "set_canonical_stream" musicstreamer/ui_qt/edit_station_dialog.py` = 1
- `grep -c "dialog.url_edit." tests/test_edit_station_dialog.py` = 0
- `.venv/bin/python -m pytest tests/test_edit_station_dialog.py -x` exits 0 (104 passed)
