---
phase: 29-move-discover-import-and-accent-color-into-the-hamburger-men
reviewed: 2026-04-09T00:00:00Z
depth: standard
files_reviewed: 1
files_reviewed_list:
  - musicstreamer/ui/main_window.py
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 29: Code Review Report

**Reviewed:** 2026-04-09
**Depth:** standard
**Files Reviewed:** 1
**Status:** issues_found

## Summary

The phase moves Discover, Import, and Accent Color into a hamburger menu and wires them as `Gio.SimpleAction`s on the app. The structural change is clean. Three warning-level issues were found: a fragile attribute access on a private player field, a tag-chip selection bug that can leave stale state after a rebuild, and a resume-after-pause bug where `_paused_station` is cleared before `_play_station` uses it. Three info items cover a redundant `os` import, magic numbers, and a few `console.log`-style bare `import dbus` calls scattered inside methods.

---

## Warnings

### WR-01: `_toggle_pause` clears `_paused_station` before resuming

**File:** `musicstreamer/ui/main_window.py:732`

**Issue:** When resuming from pause, the code sets `self._paused_station = None` on line 735 and then calls `self._play_station(self._current_station)` on line 738. `_current_station` is relied upon for playback, so this specific bug is currently harmless — but the intent stated in the comment is to "replay same station" from `_paused_station`. If `_current_station` were ever cleared before `_toggle_pause` is called (e.g., by a race in a future change), the resume silently plays `None` and crashes in `_play_station` at `self.repo.update_last_played(st.id)`.

**Fix:** Either use `_paused_station` directly for the replay call (matching the stated intent), or remove `_paused_station` and rely solely on `_current_station`:

```python
def _toggle_pause(self):
    if self._paused and self._current_station:
        self._paused = False
        self._paused_station = None
        self.pause_btn.set_icon_name("media-playback-pause-symbolic")
        self.pause_btn.set_tooltip_text("Pause")
        self._play_station(self._current_station)  # _current_station is the source of truth
    elif self._current_station and not self._paused:
        ...
```

---

### WR-02: Tag chip rebuild can leave stale `_selected_tags` entries

**File:** `musicstreamer/ui/main_window.py:448-459`

**Issue:** `_rebuild_filter_state` uses `all_tags.values()` (display-form strings, e.g. `"Rock"`) as keys for `_selected_tags`, but the stale-selection pruning on line 458 computes `current_tag_displays` from `all_tags.values()`. If two tags normalize to the same casefold key but have different display forms across rebuilds (e.g., `"rock"` vs `"Rock"`), the pruning check passes while the actual chip label no longer matches the stored value. The chip will appear inactive even though `_selected_tags` still holds the old value, causing phantom filtering.

**Fix:** Normalize `_selected_tags` to casefold keys consistently, and look up display form only for rendering:

```python
# Store casefolded keys in _selected_tags
self._selected_tags: set[str] = set()   # casefold keys

# In _make_tag_toggle_cb, use tag_name.casefold():
def _cb(btn):
    if btn.get_active():
        self._selected_tags = {tag_name.casefold()}
    else:
        self._selected_tags.discard(tag_name.casefold())

# In _render_list, tag_set is already casefolded — no change needed there.
# In _rebuild_filter_state, prune against casefold keys:
current_tag_keys = set(all_tags.keys())  # already casefolded
self._selected_tags &= current_tag_keys
```

---

### WR-03: Direct access to `player._current_stream` (private attribute)

**File:** `musicstreamer/ui/main_window.py:942`

**Issue:** `self.player._current_stream` accesses a name-mangled private attribute of `Player`. If `Player` refactors its internal stream tracking, this silently returns `None` or raises `AttributeError`, breaking the "currently playing" checkmark in the stream picker without any obvious error at the call site.

**Fix:** Add a public property or accessor to `Player`:

```python
# In Player:
@property
def current_stream(self):
    return self._current_stream

# In main_window.py line 942:
if self.player.current_stream and s.id == self.player.current_stream.id:
```

---

## Info

### IN-01: Redundant `import os` inside `_on_art_fetched` closure

**File:** `musicstreamer/ui/main_window.py:705`

**Issue:** `import os` appears inside the `_update_ui` nested closure (line 705), but `os` is already imported at the module level (line 0). The inner import is dead weight — it works but adds noise and misleads readers into thinking the outer `os` is not available here.

**Fix:** Remove the inner `import os` at line 705; the module-level import is in scope.

---

### IN-02: `import dbus` repeated inside multiple methods

**File:** `musicstreamer/ui/main_window.py:682, 748, 781, 884`

**Issue:** `import dbus` is repeated inline inside `_on_cover_art`, `_toggle_pause`, `_stop`, and `_play_station`. This is a pattern used to defer the import when D-Bus is unavailable, which is intentional — but it should be documented with a comment, otherwise it reads as an oversight. Each call site also skips this import if `self.mpris is None`, so the guard already exists.

**Fix:** Add a one-line comment at each site, or hoist to a module-level optional import:

```python
# At module top, after other imports:
try:
    import dbus as _dbus
except ImportError:
    _dbus = None
```

Then replace `import dbus` + `dbus.String(...)` with `_dbus.String(...)` at each call site, which also avoids the repeated import overhead.

---

### IN-03: Magic number `50` in stream label truncation

**File:** `musicstreamer/ui/main_window.py:934`

**Issue:** `s.url[:50]` uses a magic literal for URL truncation in the stream picker label. The same truncation at line 916 uses `[:40]`. The inconsistency suggests one value was copied without adjustment.

**Fix:** Define a constant and use it consistently:

```python
_STREAM_LABEL_MAX = 40  # or 50 — pick one

label_text = s.label or s.url[:_STREAM_LABEL_MAX]   # line 934
label = stream.label or stream.url[:_STREAM_LABEL_MAX]  # line 916
```

---

_Reviewed: 2026-04-09_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
