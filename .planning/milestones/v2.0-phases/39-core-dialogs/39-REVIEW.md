---
phase: 39-core-dialogs
reviewed: 2026-04-13T00:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - musicstreamer/ui_qt/edit_station_dialog.py
  - musicstreamer/ui_qt/discovery_dialog.py
  - musicstreamer/ui_qt/import_dialog.py
  - musicstreamer/ui_qt/main_window.py
  - musicstreamer/ui_qt/now_playing_panel.py
  - musicstreamer/ui_qt/station_list_panel.py
  - tests/test_edit_station_dialog.py
  - tests/test_discovery_dialog.py
  - tests/test_import_dialog_qt.py
  - tests/test_main_window_integration.py
  - tests/test_now_playing_panel.py
  - tests/test_stream_picker.py
findings:
  critical: 0
  warning: 4
  info: 3
  total: 7
status: issues_found
---

# Phase 39: Code Review Report

**Reviewed:** 2026-04-13
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Phase 39 delivers the core dialogs (EditStationDialog, DiscoveryDialog, ImportDialog) and wires them into the existing MainWindow/NowPlayingPanel. The implementation is well-structured — threading discipline is correct, Qt.PlainText is enforced on all ICY/metadata labels, and the delete-guard logic is sound.

Four warnings were found: one unvalidated empty-name save path, one missing URL validation before scan, one broken progress lambda in `_AaImportWorker`, and one direct access to a private `_station` attribute across a module boundary. Three info items cover a duplicated QSS constant, a missing stream-deletion path on save, and a test that bypasses the worker it claims to exercise.

## Warnings

### WR-01: Empty station name accepted on save

**File:** `musicstreamer/ui_qt/edit_station_dialog.py:346`
**Issue:** `_on_save` strips the name field but passes it directly to `repo.update_station` without checking whether it is empty. A user can save a station with a blank name, which is likely invalid at the repo/DB level and would produce a confusing silent error or integrity failure.
**Fix:**
```python
name = self.name_edit.text().strip()
if not name:
    QMessageBox.warning(self, "Validation", "Station name cannot be empty.")
    return
```

### WR-02: YouTube scan dispatched without URL validation

**File:** `musicstreamer/ui_qt/import_dialog.py:263`
**Issue:** `_on_yt_scan_clicked` only checks that the URL field is non-empty before launching `_YtScanWorker`. The docstring references `is_yt_playlist_url()` (T-39-07), and the security note in the module docstring claims the URL is validated before scan, but no such check exists in the implementation. An arbitrary URL is passed to `yt_import.scan_playlist` on the worker thread.
**Fix:**
```python
from musicstreamer.yt_import import is_yt_playlist_url  # or wherever it lives

def _on_yt_scan_clicked(self):
    url = self._yt_url.text().strip()
    if not url:
        return
    if not is_yt_playlist_url(url):
        self._yt_status.setStyleSheet("color: #c0392b;")
        self._yt_status.setText("Not a valid YouTube playlist URL.")
        self._yt_status.setVisible(True)
        return
    # ... rest of method
```

### WR-03: Broken progress lambda in `_AaImportWorker.run`

**File:** `musicstreamer/ui_qt/import_dialog.py:122`
**Issue:** The `on_progress` lambda is `lambda cur, tot: self.progress.emit(cur + tot - tot, tot)`. The expression `cur + tot - tot` simplifies to `cur`, making the lambda correct but only by coincidence — the intended arithmetic masks an obvious copy-paste mistake. More critically, `self.progress.emit` is called from a worker thread but `self.progress` is a Qt signal connected to a main-thread slot. Signal emission from a worker thread is thread-safe in Qt only when the connection is a `QueuedConnection`. The `_on_aa_import_progress` connection (line 391) does use `Qt.QueuedConnection`, so emission is safe — but the redundant arithmetic is misleading and likely to be broken if modified.
**Fix:**
```python
result = aa_import.import_stations_multi(
    self._channels,
    repo,
    on_progress=lambda cur, tot: self.progress.emit(cur, tot),
)
```

### WR-04: Direct private-attribute access across module boundary

**File:** `musicstreamer/ui_qt/main_window.py:177`
**Issue:** `_on_station_deleted` reads `self.now_playing._station` directly (`if self.now_playing._station and self.now_playing._station.id == station_id`). `_station` is a private implementation detail of `NowPlayingPanel`. If the panel's internal state representation changes, this silently breaks without a compile-time error.
**Fix:** Add a public read-only property to `NowPlayingPanel`:
```python
# now_playing_panel.py
@property
def current_station(self) -> Optional[Station]:
    return self._station
```
Then in `main_window.py`:
```python
if self.now_playing.current_station and self.now_playing.current_station.id == station_id:
    self.now_playing._on_stop_clicked()
```

---

## Info

### IN-01: Duplicated `_CHIP_QSS` constant

**File:** `musicstreamer/ui_qt/edit_station_dialog.py:47`
**Issue:** `_CHIP_QSS` in `edit_station_dialog.py` is a verbatim copy of the same constant from `station_list_panel.py` (even noted with a comment). If the chip style changes, both copies must be updated in sync.
**Fix:** Extract to a shared module (e.g., `musicstreamer/ui_qt/chip_style.py`) and import from both files.

### IN-02: Existing streams not deleted on save when removed from table

**File:** `musicstreamer/ui_qt/edit_station_dialog.py:369-400`
**Issue:** `_on_save` iterates the table rows and updates/inserts streams, then calls `repo.reorder_streams`. If the user removes a stream row from the table (via the Remove button), the original stream record is never deleted from the repo — only excluded from `ordered_ids`. Whether `reorder_streams` performs an authoritative replace or a partial update determines whether this is a data-loss bug or a dangling-record issue. If it only reorders existing IDs, removed streams are silently orphaned.
**Fix:** Collect the set of original stream IDs (from `_populate`), diff against `ordered_ids`, and call `repo.delete_stream(id)` for each removed ID before the reorder call.

### IN-03: `test_youtube_import_calls_import_stations` does not exercise the worker

**File:** `tests/test_import_dialog_qt.py:107`
**Issue:** The test name claims it verifies that "Import button triggers import with only checked entries," but the body patches `yt_import` and then immediately calls `dialog._on_yt_import_complete(1)` directly — skipping the import worker entirely. The patch context manager is entered but the mock is never actually asserted. The `toast_cb.assert_called_once_with` assertion validates the completion handler, not the entry-filtering logic described in the test name.
**Fix:** Either rename the test to `test_yt_import_complete_shows_toast` to match what it actually tests, or add a separate test that calls `_on_yt_import_clicked` and verifies the worker receives only the checked entries.

---

_Reviewed: 2026-04-13_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
