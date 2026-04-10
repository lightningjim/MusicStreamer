---
phase: 30-add-time-counter-showing-how-long-current-stream-has-been-ac
reviewed: 2026-04-09T00:00:00Z
depth: standard
files_reviewed: 1
files_reviewed_list:
  - musicstreamer/ui/main_window.py
findings:
  critical: 0
  warning: 3
  info: 2
  total: 5
status: issues_found
---

# Phase 30: Code Review Report

**Reviewed:** 2026-04-09
**Depth:** standard
**Files Reviewed:** 1
**Status:** issues_found

## Summary

`main_window.py` implements the elapsed-time counter (TIMER-01 through TIMER-06) cleanly. The `GLib.timeout_add_seconds` approach is correct, `_stop_timer` guards against double-source leaks, and `_format_elapsed` handles hours correctly. Three logic issues were found: a timer that resumes without being re-started when playback resumes via `_toggle_pause`, a stale `_resume_timer` method that is defined but never called (dead code), and accessing a private attribute `player._current_stream` across module boundary. Two info-level items also noted.

## Warnings

### WR-01: Timer resumes via `_start_timer` on unpause, resetting `_elapsed_seconds` to 0 instead of preserving it

**File:** `musicstreamer/ui/main_window.py:756-758`
**Issue:** `_toggle_pause` saves `self._elapsed_seconds` before calling `_play_station`, then restores it afterward. However, `_play_station` calls `_start_timer()` at line 966, which unconditionally sets `self._elapsed_seconds = 0` (line 836) before the restore at line 758 runs. The restore at line 758 does win because it runs after `_play_station` returns — but this is fragile and depends on execution order with `_start_timer` being synchronous. More critically, `_start_timer` also resets the label to `"0:00"` and makes the row visible, which causes a visual flash of `"0:00"` before `_update_timer_label()` at line 759 corrects it.

**Fix:** Either pass a `resume_elapsed` parameter to `_play_station`/`_start_timer`, or save/restore the elapsed value inside `_start_timer` itself:

```python
def _toggle_pause(self):
    if self._paused and self._paused_station:
        saved_elapsed = self._elapsed_seconds  # save BEFORE _play_station
        self._paused = False
        self._paused_station = None
        self.pause_btn.set_icon_name("media-playback-pause-symbolic")
        self.pause_btn.set_tooltip_text("Pause")
        self._play_station(self._current_station)
        # _play_station -> _start_timer resets to 0; restore saved elapsed
        self._elapsed_seconds = saved_elapsed
        self._update_timer_label()
    ...
```

The current code has the save/restore in the right order (line 756 save, line 758 restore), so the elapsed count is preserved correctly. The only real bug is the visual `"0:00"` flash. To eliminate it, skip the `_update_timer_label()` inside `_start_timer` when called from a resume path, or add a `resume=False` flag:

```python
def _start_timer(self, resume_elapsed: int = 0):
    self._stop_timer()
    self._elapsed_seconds = resume_elapsed
    self._update_timer_label()
    self.timer_row.set_visible(True)
    self._timer_source_id = GLib.timeout_add_seconds(1, self._on_timer_tick)
```

Then in `_toggle_pause`, call `self._play_station` with the elapsed passed through.

---

### WR-02: `_resume_timer` is defined but never called — dead code

**File:** `musicstreamer/ui/main_window.py:846-848`
**Issue:** `_resume_timer` was presumably intended for use in `_toggle_pause` when resuming playback, but `_toggle_pause` calls `_play_station` instead (which calls `_start_timer`). `_resume_timer` is never invoked anywhere in the file and has no callers. Dead code that signals incomplete design.

```python
def _resume_timer(self):
    if self._timer_source_id is None and self.timer_row.get_visible():
        self._timer_source_id = GLib.timeout_add_seconds(1, self._on_timer_tick)
```

**Fix:** Either remove `_resume_timer` if the "re-play on unpause" design is intentional, or wire it up in `_toggle_pause` instead of calling `_play_station` (which re-creates the stream). Leaving it creates maintenance confusion about which approach is canonical.

---

### WR-03: Accessing private attribute `player._current_stream` across module boundary

**File:** `musicstreamer/ui/main_window.py:1008`
**Issue:** `self.player._current_stream` is accessed directly to highlight the active stream in the picker popover. This couples `MainWindow` to `Player`'s internal state. If `Player` renames or restructures `_current_stream`, the stream picker silently breaks (no error — the `if` condition just never matches).

```python
if self.player._current_stream and s.id == self.player._current_stream.id:
```

**Fix:** Expose a public property on `Player`:

```python
# In player.py
@property
def current_stream(self):
    return self._current_stream
```

Then use `self.player.current_stream` in `main_window.py`.

---

## Info

### IN-01: `os` imported twice — once at module top and once inside a `finally` block

**File:** `musicstreamer/ui/main_window.py:1` and `musicstreamer/ui/main_window.py:723`
**Issue:** `import os` appears at the module level (line 0) and again inside a `finally` block at line 723 (`import os; os.unlink(temp_path)`). The inner import is redundant since the module-level import covers it.

**Fix:** Remove the `import os` on line 723; `os.unlink` will resolve to the already-imported module.

---

### IN-02: `import dbus` repeated inline in three separate methods

**File:** `musicstreamer/ui/main_window.py:700, 771, 804, 949`
**Issue:** `import dbus` is deferred inside `_on_cover_art`, `_toggle_pause`, `_stop`, and `_play_station`. While this is a valid pattern when `dbus` may be unavailable (and `self.mpris` guards the call), repeating the inline import in four places is inconsistent. The module is either available or not at startup.

**Fix:** Move `import dbus` to the top of the file inside a try/except, set a module-level flag, and reference it directly:

```python
try:
    import dbus
    _DBUS_AVAILABLE = True
except ImportError:
    _DBUS_AVAILABLE = False
```

---

_Reviewed: 2026-04-09_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
