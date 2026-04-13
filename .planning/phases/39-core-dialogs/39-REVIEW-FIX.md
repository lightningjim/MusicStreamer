---
phase: 39-core-dialogs
fixed_at: 2026-04-13T00:00:00Z
review_path: .planning/phases/39-core-dialogs/39-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 39: Code Review Fix Report

**Fixed at:** 2026-04-13
**Source review:** .planning/phases/39-core-dialogs/39-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4
- Fixed: 4
- Skipped: 0

## Fixed Issues

### WR-01: Empty station name accepted on save

**Files modified:** `musicstreamer/ui_qt/edit_station_dialog.py`
**Commit:** d673c95
**Applied fix:** Added empty-name guard at the top of `_on_save` — strips the name field, and if empty shows a `QMessageBox.warning` and returns before calling `repo.update_station`.

### WR-02: YouTube scan dispatched without URL validation

**Files modified:** `musicstreamer/ui_qt/import_dialog.py`
**Commit:** 5ba46f6
**Applied fix:** Imported `is_yt_playlist_url` from `musicstreamer.yt_import` and added a validation check in `_on_yt_scan_clicked` — invalid URLs are rejected with a red status label before the worker is started.

### WR-03: Broken progress lambda in `_AaImportWorker.run`

**Files modified:** `musicstreamer/ui_qt/import_dialog.py`
**Commit:** 5ba46f6
**Applied fix:** Replaced `lambda cur, tot: self.progress.emit(cur + tot - tot, tot)` with `lambda cur, tot: self.progress.emit(cur, tot)`, removing the redundant and misleading arithmetic.

### WR-04: Direct private-attribute access across module boundary

**Files modified:** `musicstreamer/ui_qt/now_playing_panel.py`, `musicstreamer/ui_qt/main_window.py`
**Commit:** 8db6724
**Applied fix:** Added a `current_station` read-only property to `NowPlayingPanel` returning `self._station`. Updated `_on_station_deleted` in `main_window.py` to use `self.now_playing.current_station` instead of `self.now_playing._station`.

---

_Fixed: 2026-04-13_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
