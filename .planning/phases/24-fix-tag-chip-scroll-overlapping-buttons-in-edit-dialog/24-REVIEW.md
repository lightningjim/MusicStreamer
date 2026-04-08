---
phase: 24-fix-tag-chip-scroll-overlapping-buttons-in-edit-dialog
reviewed: 2026-04-08T00:00:00Z
depth: standard
files_reviewed: 1
files_reviewed_list:
  - musicstreamer/ui/edit_dialog.py
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 24: Code Review Report

**Reviewed:** 2026-04-08
**Depth:** standard
**Files Reviewed:** 1
**Status:** issues_found

## Summary

`edit_dialog.py` is a 603-line GTK4/Adw dialog with async thumbnail fetching, tag chip selection, and provider management. No security vulnerabilities or crashes found. Three warnings relate to missing spinner stop on close, an art-stack state leak if fetch completes after dialog destruction, and the `_chip_box` not being in a scrollable container (which is likely the bug this phase is fixing). Three info items cover minor quality issues.

## Warnings

### WR-01: Art spinner not stopped on dialog close

**File:** `musicstreamer/ui/edit_dialog.py:465-469`
**Issue:** `_on_close_request` sets `_fetch_cancelled = True` but never calls `self._art_spinner.stop()`. If a fetch is in progress when the user closes the dialog, the spinner keeps running until GTK destroys the widget. On some GTK versions a running spinner on a detached widget emits warnings or causes reference leaks.
**Fix:**
```python
def _on_close_request(self, *_):
    self._fetch_cancelled = True
    self._art_spinner.stop()
    self._art_stack.set_visible_child_name("pic")
    if hasattr(self, '_aa_key_popover'):
        self._aa_key_popover.unparent()
    return False
```

### WR-02: `_on_thumbnail_fetched` touches widgets after dialog destruction

**File:** `musicstreamer/ui/edit_dialog.py:448-463`
**Issue:** The guard `if self._fetch_cancelled: return` runs after `self._art_spinner.stop()` on line 451. If the window was destroyed (not just closed via `close-request`), calling `self._art_spinner.stop()` before checking the cancel flag can touch a destroyed widget. The cancel-flag check should come first.
**Fix:**
```python
def _on_thumbnail_fetched(self, temp_path):
    self._thumb_fetch_in_progress = False
    if self._fetch_cancelled:
        return
    self._art_spinner.stop()
    ...
```

### WR-03: Tag chip `FlowBox` is not wrapped in a scrolled window

**File:** `musicstreamer/ui/edit_dialog.py:234-260`
**Issue:** `_chip_box` (a `Gtk.FlowBox`) is appended directly to `tags_box`, which is packed into a fixed-size `Gtk.Grid` row inside an unscrolled `Gtk.Box`. With many tags the chips will overflow the dialog vertically and be clipped or cause the window to grow unboundedly. This is almost certainly the layout bug this phase targets.
**Fix:** Wrap `_chip_box` in a `Gtk.ScrolledWindow` with a capped height:
```python
chip_scroll = Gtk.ScrolledWindow()
chip_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
chip_scroll.set_min_content_height(40)
chip_scroll.set_max_content_height(120)
chip_scroll.set_child(self._chip_box)

tags_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
tags_box.append(chip_scroll)
tags_box.append(self.new_tag_entry)
```

## Info

### IN-01: `_rebuilding` set twice before chip loop

**File:** `musicstreamer/ui/edit_dialog.py:232, 246`
**Issue:** `self._rebuilding = False` is set on line 232 inside `__init__`, then immediately set to `True` on line 246 before the chip-building loop. The first assignment on line 232 is dead — `_rebuilding` is an instance attribute that doesn't exist yet. Harmless, but confusing.
**Fix:** Remove line 232; initialize once on line 246 or declare `self._rebuilding = False` in a logical init block, then set `True` just before the loop.

### IN-02: `hasattr` guard for `_aa_key_popover` is unnecessary

**File:** `musicstreamer/ui/edit_dialog.py:467`
**Issue:** `_aa_key_popover` is always created in `__init__` (line 287) before `connect("close-request", ...)` (line 363), so it is always present when `_on_close_request` fires. The `hasattr` check is dead defensive code.
**Fix:** Replace with a direct call: `self._aa_key_popover.unparent()`.

### IN-03: Magic number `480` for default window height with no tag scroll budget

**File:** `musicstreamer/ui/edit_dialog.py:169`
**Issue:** `self.set_default_size(560, 480)` was sized before a scrollable chip area existed. Once a `ScrolledWindow` is added (WR-03 fix), the default height may need adjustment so the form fits without its own scrollbar. Track this as a tuning note when implementing WR-03.
**Fix:** After adding the chip scroll, verify the 480px height is still appropriate; adjust or add a comment explaining the sizing rationale.

---

_Reviewed: 2026-04-08_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
