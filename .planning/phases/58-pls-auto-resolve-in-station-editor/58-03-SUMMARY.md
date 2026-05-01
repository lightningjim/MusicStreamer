---
phase: 58-pls-auto-resolve-in-station-editor
plan: "03"
subsystem: ui-qt
tags: [ui, qt, pyside6, dialog, worker, qthread, pls, m3u, xspf]
dependency_graph:
  requires:
    - musicstreamer/playlist_parser.parse_playlist  # Plan 01 output
  provides:
    - musicstreamer/ui_qt/edit_station_dialog._PlaylistFetchWorker
    - musicstreamer/ui_qt/edit_station_dialog.EditStationDialog.add_pls_btn
    - musicstreamer/ui_qt/edit_station_dialog.EditStationDialog._on_add_pls
    - musicstreamer/ui_qt/edit_station_dialog.EditStationDialog._on_pls_fetched
    - musicstreamer/ui_qt/edit_station_dialog.EditStationDialog._apply_pls_entries
    - musicstreamer/ui_qt/edit_station_dialog.EditStationDialog._shutdown_pls_fetch_worker
  affects:
    - musicstreamer/ui_qt/edit_station_dialog.EditStationDialog  (5th stream-toolbar button added)
tech_stack:
  added: []
  patterns:
    - QThread worker with monotonic stale-discard token (mirrors _LogoFetchWorker)
    - Restore-cursor-first-unconditionally invariant (D-03/D-10)
    - Three-site teardown shutdown (accept/closeEvent/reject — bb1c518 pattern)
    - UI-only setRowCount(0) replace (no repo.delete_stream — _on_save reconcile prunes)
    - Position-continuation append (max(existing) + 1)
key_files:
  created: []
  modified:
    - musicstreamer/ui_qt/edit_station_dialog.py
    - tests/test_edit_station_dialog.py
decisions:
  - "D-01: 5th button 'Add from PLS…' (U+2026) added to btn_row after Move Down; tooltip lists PLS / M3U / M3U8 / XSPF"
  - "D-02: QInputDialog.getText with empty initial; Cancel / whitespace-only URL is absolute no-op"
  - "D-03/D-10: restoreOverrideCursor + setEnabled(True) are the FIRST two lines of _on_pls_fetched, before stale-token check"
  - "D-04: _PlaylistFetchWorker(url, token, self) mirrors _LogoFetchWorker; finished=Signal(list,str,int); token monotonically increments"
  - "D-05: HTTP/parse failure shows QMessageBox.warning; streams table unchanged; no legacy pls_url-as-row fallback"
  - "D-06: empty table silent append; non-empty table 3-button QMessageBox (Replace/Append/Cancel; default Append)"
  - "D-07: Replace = setRowCount(0) UI-only; no repo.delete_stream call; _on_save reconcile prunes orphaned stream_ids"
  - "D-08: Append continues from max(existing position) + 1"
metrics:
  duration: "~25m"
  completed: "2026-05-01"
  tasks_completed: 2
  files_created: 0
  lines_written: 520
---

# Phase 58 Plan 03: Wire PLS Auto-Resolve into EditStationDialog

`_PlaylistFetchWorker(QThread)` + `add_pls_btn` + four new dialog methods wiring playlist-URL import into `EditStationDialog`, plus 14 pytest-qt tests covering all outcome branches and invariants.

## What Was Built

### musicstreamer/ui_qt/edit_station_dialog.py

**New class: `_PlaylistFetchWorker(QThread)` (lines 126-186)**

Mirrors `_LogoFetchWorker` shape:

```python
class _PlaylistFetchWorker(QThread):
    finished = Signal(list, str, int)  # entries, error_message, token

    def __init__(self, url: str, token: int, parent=None): ...
    def run(self) -> None: ...
```

Exception strategy: `HTTPError` → `f"HTTP {exc.code}: {exc.reason}"`, `URLError` → `f"Could not connect: {exc.reason}"`, `(TimeoutError, socket.timeout)` → `"Timed out after 10 seconds."`, `UnicodeDecodeError`, bare `except Exception` backstop.

**5th button in streams toolbar (line 434)**

```
btn_row order: Add | Remove | Move Up | Move Down | Add from PLS… | [stretch]
```

Label: `"Add from PLS…"` (U+2026 HORIZONTAL ELLIPSIS — verified by test). Tooltip: `"Paste a playlist URL (PLS / M3U / M3U8 / XSPF) and import each stream entry as a row."`. Connection: `self.add_pls_btn.clicked.connect(self._on_add_pls)` (bound-method, no lambda — QA-05).

**New method signatures:**

```python
def _on_add_pls(self) -> None:
    # Opens QInputDialog.getText("Add from PLS", "Playlist URL:", QLineEdit.Normal, "")
    # Cancel / empty → no-op. Valid URL → increment token, disable button, setOverrideCursor, start worker.

def _on_pls_fetched(self, entries: list, error_message: str, token: int) -> None:
    # FIRST: restoreOverrideCursor() + setEnabled(True) UNCONDITIONALLY
    # THEN: stale-token discard
    # THEN: Branch A/B (warning), Branch C (empty table silent append), Branch D (3-button QMessageBox)

def _apply_pls_entries(self, entries: list, mode: str) -> None:
    # mode="replace": setRowCount(0) (UI-only), then insert
    # mode="append": continue from max(existing position) + 1
    # Calls _add_stream_row(stream_id=None) per entry

def _shutdown_pls_fetch_worker(self) -> None:
    # worker.finished.disconnect() + worker.wait(2000) — mirrors _shutdown_logo_fetch_worker
```

**Instance attributes added (lines 255-257):**

```python
self._pls_fetch_worker: Optional[_PlaylistFetchWorker] = None
self._pls_fetch_token: int = 0
```

**3 shutdown call sites:**

| Method | Line | Context |
|--------|------|---------|
| `accept()` | 1062 | After `_shutdown_logo_fetch_worker()` — Save path |
| `closeEvent()` | 1075 | After `_shutdown_logo_fetch_worker()` — X-button / window close |
| `reject()` | 1084 | After `_shutdown_logo_fetch_worker()` — Discard / Esc |

**Column mapping (D-11/D-14/D-15/D-16):**

| Column | Source key | Renders as |
|--------|------------|------------|
| URL (`_COL_URL = 0`) | `entry["url"]` | URL string |
| Quality (`_COL_QUALITY = 1`) | `entry["title"]` | Human-readable; may be blank |
| Codec (`_COL_CODEC = 2`) | `entry["codec"]` | Recognized token or `""` |
| Bitrate (`_COL_BITRATE = 3`) | `entry["bitrate_kbps"]` | `str(n)` or `""` when 0 |
| Position (`_COL_POSITION = 4`) | `start_position + i` | Integer string |

### tests/test_edit_station_dialog.py

14 new test functions appended under the `# Phase 58 / STR-15: PLS Auto-Resolve flow` section header:

| Test | What it covers |
|------|---------------|
| `test_add_pls_button_exists` | Button present, label has U+2026, tooltip lists all 4 formats |
| `test_add_pls_worker_starts_on_valid_url` | Worker instantiated with stripped URL, `.start()` called, button disabled |
| `test_add_pls_cancel_is_noop` | Cancel in QInputDialog → no worker, button stays enabled |
| `test_add_pls_empty_url_is_noop` | Whitespace-only URL (ok=True) → no-op |
| `test_on_pls_fetched_restores_cursor_first_unconditionally` | D-03/D-10 restore-first invariant even on stale token |
| `test_on_pls_fetched_failure_shows_warning_and_leaves_table_unchanged` | D-05 branch — HTTP 404 shows warning, table unchanged |
| `test_on_pls_fetched_empty_table_silent_append` | D-06 branch C — no QMessageBox when table is empty |
| `test_on_pls_fetched_replace_clears_existing_rows` | D-07 setRowCount(0) removes old rows |
| `test_on_pls_fetched_append_preserves_existing_rows` | D-08 position continuation (max+1) |
| `test_apply_pls_entries_columns_mapped_correctly` | D-11/D-14/D-15/D-16 all 5 columns for full and empty-meta entries |
| `test_apply_pls_entries_trips_dirty_state` | Phase 51-02 dirty-state propagation |
| `test_shutdown_pls_fetch_worker_called_from_accept_close_reject` | inspect-based 3-site teardown wiring |
| `test_pls_fetch_token_monotonically_increments` | D-04 monotonic increment after two calls |
| `test_on_pls_fetched_stale_token_does_not_modify_table` | Stale emission silently discarded, table unchanged |

All 14 tests pass. Full dialog suite: 65 passed (excluding pre-existing flaky timing test `test_logo_status_clears_after_3s` which was already flaky before this plan).

## Manual UAT Instructions

1. Open the app, right-click a station, open the station editor.
2. Click **"Add from PLS…"** — the 5th button after "Move Down" in the streams section.
3. Paste a real PLS URL, e.g. `http://somafm.com/groovesalad.pls` or `https://somafm.com/m3u/groovesalad320.m3u`.
4. Observe wait cursor + disabled button during fetch.
5. On success with existing rows: the Replace/Append/Cancel dialog appears. Verify Enter activates **Append** (not Replace — the default button is non-destructive per D-06).
6. Verify rows appear in the Streams table with URL, Quality (title), Codec, Bitrate columns populated.
7. Verify the dialog is now dirty (Save button is active).
8. Click Discard — verify all imported rows are discarded (dialog hasn't committed yet, D-07).
9. Test Cancel in QInputDialog: no-op, table unchanged.
10. Test with an invalid URL (e.g. `http://localhost:9999/noexist.pls`) — verify warning dialog with message text.

## Deviations from Plan

None — plan executed exactly as written. All six edits were applied to `edit_station_dialog.py` as specified. The 14 tests listed in the plan were implemented verbatim using the provided sample code. All D-01..D-19 decisions were implemented without simplification or deferral.

**Note on pre-existing flaky test:** `test_logo_status_clears_after_3s` uses `qtbot.wait(3100)` to test a 3-second timer. This test passes when run in isolation but is timing-sensitive and can fail intermittently in full-suite runs. This is a pre-existing condition unrelated to Plan 03.

## Threat Surface Scan

No new threat surface beyond what is documented in the plan's `<threat_model>` section. All T-58U-01 through T-58U-08 mitigations are implemented:

- T-58U-03 (DoS / stall): `urlopen(timeout=10)` + worker runs on QThread
- T-58U-05 (QThread crash): `_shutdown_pls_fetch_worker()` in all 3 teardown paths
- T-58U-07 (re-entrancy): `add_pls_btn.setEnabled(False)` during fetch + `_pls_fetch_token` stale-discard

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `musicstreamer/ui_qt/edit_station_dialog.py` modified | FOUND |
| `tests/test_edit_station_dialog.py` extended | FOUND |
| `58-03-SUMMARY.md` created | FOUND |
| Commit f00d9e1 (Task 1) exists | FOUND |
| Commit 6b5665b (Task 2) exists | FOUND |
| `_PlaylistFetchWorker` class present | FOUND (line 126) |
| `add_pls_btn` with U+2026 | FOUND (line 434) |
| 3 shutdown call sites | FOUND (lines 1062, 1075, 1084) |
| 4 new methods on EditStationDialog | FOUND |
| 14 new test functions | FOUND (all pass) |
| Full dialog suite | 65 passed |
