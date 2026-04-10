# Phase 30: Add Time Counter - Research

**Researched:** 2026-04-09
**Domain:** GTK4/Python — periodic UI updates, GLib timer management
**Confidence:** HIGH

## Summary

This phase adds an elapsed-time display to the now-playing panel. The implementation is self-contained: one new `Gtk.Box` row (icon + label), three new instance variables (`_elapsed_seconds`, `_timer_source_id`, `_timer_running`), and hooks in `_play_station`, `_toggle_pause`, and `_stop`. GLib already imported; no new dependencies.

The only non-trivial concern is timer source lifecycle — returning `False` from the callback removes the source, but `_toggle_pause` calls `_play_station` on resume which would add a second source if the first was not removed. The plan must ensure the old source is cancelled before starting a new one.

**Primary recommendation:** Store the GLib source ID on `self._timer_source_id`; call `GLib.source_remove(self._timer_source_id)` before adding a new one in every code path that starts playback.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** New label row between `station_name_label` and `controls_box` in the center column. Contains a small timer icon on the left and elapsed time text to its right.
- **D-02:** Horizontal `Gtk.Box` with `Gtk.Image` (icon) and `Gtk.Label` (time text). Icon: `timer-symbolic` or `hourglass-symbolic` (whichever is available).
- **D-03:** Timer pauses when stream is paused (`_toggle_pause`), resumes on unpause. Accumulated elapsed seconds, not wall-clock difference.
- **D-04:** Timer resets to 0:00 on station change. Failover (same station, different stream) does NOT reset.
- **D-05:** Timer hidden (`set_visible(False)`) when stopped. Shows `0:00` immediately when new station starts, then ticks up.
- **D-06:** Use `GLib.timeout_add_seconds(1, callback)`. Callback returns `True` while playing, `False` when stopped.
- **D-07:** Adaptive format: `M:SS` for < 1h, `H:MM:SS` for >= 1h. No leading zero on first digit.
- **D-08:** `dim-label` CSS class on both icon and time label.

### Claude's Discretion
- Whether to store elapsed seconds as an int on `MainWindow` or create a small helper
- Exact icon name resolution (try `timer-symbolic` first, fall back to `hourglass-symbolic`)
- Whether to use `Gtk.Image.new_from_icon_name` or set via `set_from_icon_name`

### Deferred Ideas (OUT OF SCOPE)
None
</user_constraints>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| GLib (gi.repository) | already imported | `timeout_add_seconds`, `source_remove` | Part of GTK stack; already in `from gi.repository import Gtk, Adw, Pango, GdkPixbuf, GLib, Gio` line 7 |
| Gtk.Box / Gtk.Image / Gtk.Label | already imported | Timer row widgets | Same widget types used throughout now-playing panel |

No new packages to install.

## Architecture Patterns

### Timer Lifecycle (the critical pattern)

Three state variables on `self`:

```python
self._elapsed_seconds: int = 0
self._timer_source_id: int | None = None  # GLib source handle
```

**Start timer** (call at end of `_play_station`, only when NOT resuming from pause with same station):

```python
def _start_timer(self):
    self._stop_timer()  # cancel any existing source first
    self._elapsed_seconds = 0
    self._update_timer_label()
    self.timer_row.set_visible(True)
    self._timer_source_id = GLib.timeout_add_seconds(1, self._on_timer_tick)

def _on_timer_tick(self) -> bool:
    self._elapsed_seconds += 1
    self._update_timer_label()
    return True  # keep ticking — caller removes via _stop_timer
```

**Pause timer** (add to `_toggle_pause` pause branch — do NOT return False from callback):

```python
def _pause_timer(self):
    if self._timer_source_id is not None:
        GLib.source_remove(self._timer_source_id)
        self._timer_source_id = None

def _resume_timer(self):
    if self._timer_source_id is None and self.timer_row.get_visible():
        self._timer_source_id = GLib.timeout_add_seconds(1, self._on_timer_tick)
```

**Stop timer** (call in `_stop`):

```python
def _stop_timer(self):
    if self._timer_source_id is not None:
        GLib.source_remove(self._timer_source_id)
        self._timer_source_id = None
    self._elapsed_seconds = 0
    self.timer_row.set_visible(False)
```

**Format helper:**

```python
def _format_elapsed(self, seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
```

### Critical: `_toggle_pause` calls `_play_station` on resume

[VERIFIED: codebase grep] Line 738: `self._play_station(self._current_station)` — resume goes through `_play_station`. This means `_play_station` must distinguish a station-change call (reset timer) from a resume call (continue timer). Options:

**Recommended approach (Claude's discretion):** `_play_station` always calls `_start_timer()` which resets. In `_toggle_pause` resume branch, save and restore elapsed seconds around the `_play_station` call:

```python
# In _toggle_pause resume branch:
saved_elapsed = self._elapsed_seconds
self._play_station(self._current_station)
self._elapsed_seconds = saved_elapsed  # restore after _play_station reset
self._update_timer_label()
```

This avoids adding a parameter to `_play_station` and keeps timer logic isolated.

### Widget construction (insert between station_name_label and controls_box)

[VERIFIED: codebase read, lines 125-172]

```python
# After station_name_label append (line 130), before controls_box construction
self.timer_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
self.timer_row.set_visible(False)

timer_icon = Gtk.Image.new_from_icon_name("timer-symbolic")
timer_icon.add_css_class("dim-label")
timer_icon.set_pixel_size(16)
self.timer_row.append(timer_icon)

self.timer_label = Gtk.Label(label="0:00")
self.timer_label.add_css_class("dim-label")
self.timer_label.set_xalign(0)
self.timer_row.append(self.timer_label)

center.append(self.timer_row)
```

Then append `controls_box` after (as currently done at line 172).

### Icon resolution

[VERIFIED: runtime check] Both `timer-symbolic` and `hourglass-symbolic` exist in the installed GTK icon theme. Use `timer-symbolic` directly — no fallback needed on this system, but the plan can include a try-except or `theme.has_icon()` check if robustness is desired.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Periodic callbacks | `threading.Timer` loop | `GLib.timeout_add_seconds` | Thread-safe GTK main loop integration; automatically stops when source removed |
| Source cleanup | Manual tracking via boolean | Store source ID, call `GLib.source_remove` | GLib source ID is the canonical handle; boolean flags lead to double-add bugs |

## Common Pitfalls

### Pitfall 1: Double timer source on resume
**What goes wrong:** `_toggle_pause` → `_play_station` → `_start_timer` adds a new source. If the paused source wasn't removed, two callbacks fire per second, elapsed doubles.
**Why it happens:** Resume path goes through `_play_station` (line 738).
**How to avoid:** `_start_timer` always calls `_stop_timer` first (unconditional `source_remove`).
**Warning signs:** Elapsed counter jumps 2 seconds per tick.

### Pitfall 2: Stale source after `_stop`
**What goes wrong:** `_stop()` hides the timer row but doesn't cancel the GLib source. Callback keeps firing, incrementing `_elapsed_seconds` invisibly. Next play resumes from stale value.
**How to avoid:** `_stop()` calls `_stop_timer()` which both calls `source_remove` and resets `_elapsed_seconds = 0`.

### Pitfall 3: Failover resets timer (violates D-04)
**What goes wrong:** Stream failover calls `_play_station` (same station), which resets the timer.
**Why it happens:** `_play_station` is the single entry point for all playback starts.
**How to avoid:** The save/restore pattern in `_toggle_pause` resume is not needed here — failover is handled in a different code path. Check the failover callback (`_on_stream_failover`, line 912) — it does NOT call `_play_station`; it just updates UI labels. So failover does not trigger `_start_timer`. D-04 is satisfied automatically.

### Pitfall 4: `set_pixel_size` on icon label
**What goes wrong:** `dim-label` CSS class on `Gtk.Image` applies color tinting but `set_pixel_size` must be called or icon renders at default size.
**How to avoid:** Always call `timer_icon.set_pixel_size(16)` (matches inline icon sizing used elsewhere in GTK4 apps).

## Code Examples

### GLib.timeout_add_seconds usage
```python
# Source: GLib Python documentation / verified in this codebase's gi.repository import
source_id = GLib.timeout_add_seconds(1, self._on_timer_tick)
# callback signature: def _on_timer_tick(self) -> bool
# return True = keep firing; return False = auto-remove source
GLib.source_remove(source_id)  # explicit cancel
```

### Format: M:SS / H:MM:SS
```python
def _format_elapsed(self, seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
# 0 → "0:00", 61 → "1:01", 3661 → "1:01:01"
```

## Environment Availability

Step 2.6: SKIPPED — phase is code-only, no new external dependencies. GLib and GTK already present.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | None detected (no pytest.ini, no tests/ directory) |
| Config file | none |
| Quick run command | manual smoke test |
| Full suite command | manual smoke test |

### Phase Requirements → Test Map
| Behavior | Test Type | Notes |
|----------|-----------|-------|
| Timer counts up 1s/tick | manual | Play a station, observe label update |
| Timer pauses when paused | manual | Pause, wait, observe label frozen |
| Timer resumes on unpause with correct value | manual | Unpause, confirm no reset |
| Timer resets on new station | manual | Switch stations, confirm `0:00` |
| Timer hidden when stopped | manual | Stop, confirm row invisible |
| `_format_elapsed` logic | unit-testable | Pure function — can be tested without GTK display |

### Wave 0 Gaps
- No automated test infrastructure exists for this project — all validation is manual smoke testing.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Failover path (`_on_stream_failover`) does not call `_play_station` | Common Pitfalls | If wrong, failover resets the timer (violates D-04); would need save/restore around failover call |

## Sources

### Primary (HIGH confidence)
- [VERIFIED: codebase read] `main_window.py` lines 7, 131, 317-319, 731-745, 760-785, 797-889 — confirmed widget patterns, GLib import, state variable locations, `_toggle_pause` resume flow
- [VERIFIED: runtime] `GLib.timeout_add_seconds` signature confirmed via `inspect.signature`; `GLib.source_remove` confirmed present
- [VERIFIED: runtime] `timer-symbolic` icon present in installed GTK icon theme

### Secondary (MEDIUM confidence)
- [CITED: GTK4 Python docs] `GLib.timeout_add_seconds(interval, function)` — callback returns bool to continue/stop

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all imports already present, verified in file
- Architecture: HIGH — widget patterns from existing code; timer API verified at runtime
- Pitfalls: HIGH — root causes traced directly to `_toggle_pause` source (line 738)

**Research date:** 2026-04-09
**Valid until:** Stable — GTK4/GLib API does not change frequently
