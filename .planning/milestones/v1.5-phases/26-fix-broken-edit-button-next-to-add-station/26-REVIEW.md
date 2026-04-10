---
phase: 26-fix-broken-edit-button-next-to-add-station
reviewed: 2026-04-08T00:00:00Z
depth: standard
files_reviewed: 1
files_reviewed_list:
  - musicstreamer/ui/main_window.py
findings:
  critical: 0
  warning: 2
  info: 2
  total: 4
status: issues_found
---

# Phase 26: Code Review Report

**Reviewed:** 2026-04-08
**Depth:** standard
**Files Reviewed:** 1
**Status:** issues_found

## Summary

Reviewed `main_window.py` after phase 26 changes. The core fix is correctly implemented: the broken filter-bar edit button is gone, `_edit_selected` is removed, and a now-playing edit button (`self.edit_btn`) is properly wired with sensitivity lifecycle (disabled at init, enabled on play, disabled on stop). No critical bugs introduced by the phase changes themselves.

Two pre-existing warnings found: a latent `AttributeError` in `_play_row` if `row-activated` fires on an `Adw.ExpanderRow`, and a functional gap where flat-mode rows (`StationRow`) have no per-row edit button. Two info items for redundant imports.

## Warnings

### WR-01: `_play_row` crashes if `row-activated` fires on an `Adw.ExpanderRow`

**File:** `musicstreamer/ui/main_window.py:776-778`
**Issue:** `_play_row` unconditionally accesses `row.station_id`. In grouped mode, `Adw.ExpanderRow` objects are appended directly to the listbox. If `row-activated` fires on an expander (Adw behavior is not guaranteed to always swallow it), the access raises `AttributeError` and crashes. The `Adw.ActionRow` children inside the expanders are already connected to `activated` directly (line 602) and do not rely on `_play_row`, so this handler is only needed for `StationRow` rows.

**Fix:**
```python
def _play_row(self, _listbox, row):
    station_id = getattr(row, "station_id", None)
    if station_id is None:
        return  # ExpanderRow or header row — not playable
    st = self.repo.get_station(station_id)
    self._play_station(st)
```

### WR-02: Flat-mode rows (`_rebuild_flat`) have no edit button

**File:** `musicstreamer/ui/main_window.py:551-562`
**Issue:** `_rebuild_flat` uses `StationRow`, which does not include a per-row edit button. When a provider chip filter is active, all stations render as `StationRow` instances. Users can only edit these stations by first playing them and using the now-playing edit button. Grouped mode uses `_make_action_row` which does include an edit button suffix. The inconsistency may confuse users who expect to edit a station without playing it.

**Fix:** Replace `StationRow` with `_make_action_row` in `_rebuild_flat`, or add an edit button suffix to `StationRow`. Using `_make_action_row` is lower effort since it already handles art, edit button, and activation:
```python
def _rebuild_flat(self, stations):
    self._clear_listbox()
    self._rp_rows = []

    for st in stations:
        row = self._make_action_row(st)   # has edit button; activated signal wired
        self.listbox.append(row)

    if not stations and self._any_filter_active():
        self.shell.set_content(self.empty_page)
    else:
        self.shell.set_content(self.scroller)
```
Note: `_make_action_row` rows use `ar.connect("activated", ...)` directly, so `_play_row` is not involved.

## Info

### IN-01: Redundant `import os` inside nested function

**File:** `musicstreamer/ui/main_window.py:690`
**Issue:** `import os` appears inside `_update_ui` (nested inside `_on_art_fetched`, itself nested inside `_on_cover_art`). The module already imports `os` at line 1.
**Fix:** Remove the inner `import os` at line 690.

### IN-02: Repeated inline `import dbus` in three method bodies

**File:** `musicstreamer/ui/main_window.py:667, 734, 867`
**Issue:** `import dbus` is repeated inside `_on_cover_art`, `_toggle_pause`, and `_play_station`. This is a lazy-import pattern that avoids a hard dependency, which is intentional, but the repetition across three methods is inconsistent. If the intent is to guard against missing `dbus`, a single module-level try/except is cleaner.
**Fix (optional):** Add a module-level guard:
```python
try:
    import dbus as _dbus
except ImportError:
    _dbus = None
```
Then reference `_dbus` in the methods, guarded by `if self.mpris and _dbus:`.

---

_Reviewed: 2026-04-08_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
