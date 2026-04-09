# Phase 28: Stream Failover Logic — Research

**Researched:** 2026-04-09
**Domain:** GStreamer bus error handling, GLib timeout, Adw.Toast, GTK4 Gtk.MenuButton popover
**Confidence:** HIGH (all findings from direct codebase inspection; no external library uncertainty)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Failover triggers on GStreamer pipeline ERROR bus message OR timeout — if no audio data arrives within 10 seconds of play start, treat as failure and try next stream.
- **D-02:** Silence detection is out of scope — only error and timeout trigger failover.
- **D-03:** Try every stream in the station's list exactly once. If all fail, stop playback and show error. No cycling/retrying.
- **D-04:** First stream selected via `get_preferred_stream_url()`. Fall back to position order if no preference set or no quality match.
- **D-05:** After the preferred/first stream fails, try remaining streams in position order. Predictable and user-controlled.
- **D-06:** Show `Adw.Toast` notifications: "Stream failed — trying next..." on each failover attempt, and "All streams failed" when exhausted.
- **D-07:** Stream picker menu button in the now-playing controls row (next to Edit/Star/Pause/Stop). Uses an antenna/signal-style icon. Opens a popover listing all streams by label + quality badge.
- **D-08:** Selecting a stream from the picker immediately switches playback to that stream. Does not affect the configured position order.

### Claude's Discretion
- Icon choice for stream picker button (antenna, signal, radio tower — whatever fits Adwaita icon set)
- Toast message wording and duration
- Timeout implementation mechanism (GLib.timeout_add vs GStreamer clock)
- Whether to show stream picker button only when station has 2+ streams (sensible default)

### Deferred Ideas (OUT OF SCOPE)
None
</user_constraints>

---

## Summary

Phase 28 wires up failover logic entirely within existing code paths. The Player already has `_on_gst_error` (catch errors), GLib is already imported (schedule timeouts), `get_preferred_stream_url()` exists but is unused by `play()`, and `Adw.Toast` is standard Adw — just not yet used in this app. The stream picker is a `Gtk.MenuButton` added to the existing `controls_box` horizontal box in `main_window.py`.

The only structural question is how to route toast notifications: the Player lives in main_window but has no reference back to the window for UI calls. The established pattern is callbacks — `player.play()` already takes `on_title`. The same approach (pass an `on_failover` callback or expose a toast method on the window) is the correct extension.

YouTube streams (mpv subprocess) need separate failover detection — mpv process exit code rather than a GStreamer bus message. This is called out in the CONTEXT.md specifics and is a distinct code path.

**Primary recommendation:** Extend `Player.play()` to accept a stream list and an `on_failover` callback. Player manages the failover loop internally (try next stream on error/timeout, call callback for each attempt). Window provides the callback that shows a toast.

---

## Architecture Patterns

### Failover State in Player

Player needs to track:
- `_streams_queue: list[StationStream]` — remaining streams to try (populated at play start, consumed on each failure)
- `_failover_timer_id: int | None` — GLib timeout source ID (cancel on success or manual stop)
- `_on_failover: callable | None` — callback for window to show toast

```python
# Source: direct codebase inspection
def play(self, station: Station, on_title: callable,
         preferred_quality: str = "",
         on_failover: callable = None):
    # Build ordered stream list: preferred first, then rest by position
    streams = list(station.streams)  # copy
    preferred_url = get_preferred_stream_url(station.id, preferred_quality)
    # reorder: preferred stream first, rest in position order
    ...
    self._streams_queue = streams
    self._on_failover = on_failover
    self._try_next_stream()
```

### Stream Queue Construction (D-04 + D-05)

`get_preferred_stream_url()` returns a URL string. Player needs the full `StationStream` objects to iterate. Build the queue by:
1. Finding the stream whose URL matches `get_preferred_stream_url()` result — put it first
2. Remaining streams in `position` order

`repo.list_streams(station_id)` already returns streams `ORDER BY position`. Player currently receives the station object which includes `station.streams` (pre-populated). No additional DB call needed.

**Note:** `get_preferred_stream_url()` is on `Repo`, not on `Player`. The player does not have a repo reference. Two options:
- Pass preferred_url (or preferred StationStream) into `play()` from the window (simplest — window already has repo)
- Give Player a reference to repo

The window-side resolution is simpler and keeps Player dependency-free. `_play_station()` in main_window already calls `player.play(st, on_title=_on_title)` — extend it to pass the resolved stream order.

### Timeout Implementation (D-01)

GLib.timeout_add is the correct mechanism — it runs on the GLib main loop (same thread as GTK). `BUFFER_DURATION_S = 10` in constants.py matches the 10s requirement exactly.

```python
# Source: direct codebase inspection of constants.py + GLib pattern in player.py
self._failover_timer_id = GLib.timeout_add(
    BUFFER_DURATION_S * 1000,  # milliseconds
    self._on_timeout
)

def _on_timeout(self):
    self._failover_timer_id = None
    self._try_next_stream()
    return False  # don't repeat
```

Cancel timer on success (first audio tag received or pipeline reaches PLAYING state):

```python
def _cancel_timeout(self):
    if self._failover_timer_id is not None:
        GLib.source_remove(self._failover_timer_id)
        self._failover_timer_id = None
```

The existing `_on_gst_tag` handler (fires on first ICY metadata) is a good proxy for "audio data received" — cancel timeout there. Alternatively use GStreamer's `message::state-changed` to PLAYING, but tag arrival is simpler and already wired.

### GStreamer Error Path (D-01)

`_on_gst_error` currently just prints. Extend to call `_try_next_stream()`:

```python
def _on_gst_error(self, bus, msg):
    err, debug = msg.parse_error()
    print(f"GStreamer ERROR: {err}\n  debug: {debug}")
    self._cancel_timeout()
    self._try_next_stream()
```

### `_try_next_stream()` Core Logic (D-03 + D-05 + D-06)

```python
def _try_next_stream(self):
    self._pipeline.set_state(Gst.State.NULL)
    if not self._streams_queue:
        # All failed
        if self._on_failover:
            GLib.idle_add(self._on_failover, None)  # None signals exhausted
        return
    stream = self._streams_queue.pop(0)
    if self._streams_queue:  # more remain — notify failover
        if self._on_failover:
            GLib.idle_add(self._on_failover, stream)
    url = stream.url.strip()
    if "youtube.com" in url or "youtu.be" in url:
        self._play_youtube(url, self._current_station_name, self._on_title)
    else:
        self._stop_yt_proc()
        self._set_uri(url, self._current_station_name, self._on_title)
    # Arm timeout
    self._failover_timer_id = GLib.timeout_add(
        BUFFER_DURATION_S * 1000, self._on_timeout
    )
```

### YouTube Failover (CONTEXT.md specifics)

mpv is fire-and-forget subprocess. FIX-03 (Phase 23) already adds a 2-second polling check for immediate exit. For failover, a similar polling approach works: check `_yt_proc.poll()` after a delay. However, the 2s check is blocking (`time.sleep(2)`) which is a problem.

Better: use `GLib.timeout_add` to poll `_yt_proc.poll()` periodically (every 500ms for 10s), and if it exits with non-zero code, trigger `_try_next_stream()`. This keeps the UI thread non-blocking.

The existing blocking `time.sleep(2)` in `_play_youtube` is a known issue but out of scope to fix here — just ensure the failover timeout doesn't conflict with it. The simplest safe approach: arm the failover timeout after the 2s sleep completes (i.e., inside `_play_youtube` after the retry logic). This is already the effective behavior since the sleep blocks.

### Adw.Toast for Notifications (D-06)

`Adw.Toast` is straightforward. Requires an `Adw.ToastOverlay` widget wrapping the content.

Currently `main_window.py` uses `Adw.ToolbarView` → `shell.set_content(scroller)`. The ToastOverlay must wrap the content area:

```python
# Source: [ASSUMED] standard Adw.ToastOverlay pattern
self.toast_overlay = Adw.ToastOverlay()
self.toast_overlay.set_child(scroller)
shell.set_content(self.toast_overlay)
```

Then to show a toast:
```python
def _show_toast(self, message: str, timeout: int = 3):
    toast = Adw.Toast.new(message)
    toast.set_timeout(timeout)
    self.toast_overlay.add_toast(toast)
```

The `on_failover` callback passed to Player calls `_show_toast`. Called via `GLib.idle_add` from player (cross-thread safe, same pattern as `on_title`).

### Stream Picker Button (D-07)

Add `self.stream_btn` to `controls_box` (the horizontal Gtk.Box at line 126 of main_window.py). Insert before `self.edit_btn` or after `self.stop_btn` — after stop is cleaner.

```python
self.stream_btn = Gtk.MenuButton()
self.stream_btn.set_icon_name("network-wireless-signal-excellent-symbolic")  # or "audio-input-microphone-symbolic"
self.stream_btn.add_css_class("flat")
self.stream_btn.set_tooltip_text("Switch stream")
self.stream_btn.set_visible(False)  # hidden until station with 2+ streams plays
controls_box.append(self.stream_btn)
```

The popover is a `Gtk.Popover` containing a `Gtk.ListBox` of stream rows. Each row shows label + quality badge. Clicking a row calls `_on_manual_stream_select(stream)`.

For D-08 (manual selection doesn't change position order): `_on_manual_stream_select` calls `player.play_stream(stream)` — a new method that plays a specific stream without altering the queue order. Or simpler: clear the failover queue and set it to just the selected stream (no fallback on manual pick, consistent with "user chose this explicitly").

**Icon recommendation:** `network-wireless-symbolic` or `audio-card-symbolic` are available in Adwaita. `network-wireless-symbolic` is the best semantic fit (signal/stream). [ASSUMED — verify icon name exists at runtime]

### Updating Stream Picker on Station Change

In `_play_station()`, after setting `_current_station`, rebuild the stream picker popover:

```python
def _update_stream_picker(self, station: Station):
    streams = station.streams
    self.stream_btn.set_visible(len(streams) > 1)
    # rebuild popover contents
    popover = Gtk.Popover()
    listbox = Gtk.ListBox()
    listbox.set_selection_mode(Gtk.SelectionMode.NONE)
    for s in sorted(streams, key=lambda x: x.position):
        row = self._make_stream_row(s)
        listbox.append(row)
    popover.set_child(listbox)
    self.stream_btn.set_popover(popover)
```

### Currently-Playing Stream Highlight (CONTEXT.md specifics)

Player needs to expose `_current_stream_id: int | None` so the picker can show a checkmark or bold the active row. Set this when a stream starts playing, clear on stop.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| Stream failover sequencing | Custom retry loop | Simple list + pop(0) — streams are finite (D-03: try once each) |
| Toast notifications | Custom overlay widget | `Adw.ToastOverlay` + `Adw.Toast` |
| Timeout management | Thread-based timer | `GLib.timeout_add` / `GLib.source_remove` |
| Popover menu | Custom Gtk.Window | `Gtk.Popover` set on `Gtk.MenuButton` |

---

## Common Pitfalls

### Pitfall 1: GLib.timeout_add not cancelled on manual stop
**What goes wrong:** User clicks Stop mid-timeout. Timer fires after stop, calls `_try_next_stream()` on a cleared state — NullPointerError or spurious playback.
**How to avoid:** `_cancel_timeout()` must be called in `Player.stop()`, `Player.pause()`, and at the start of every `play()` call.

### Pitfall 2: Toast shown before ToastOverlay is in the widget tree
**What goes wrong:** `add_toast()` called before `toast_overlay` is realized — silently dropped.
**How to avoid:** ToastOverlay must wrap content set on `shell` before `self.set_content(shell)` is called.

### Pitfall 3: Failover fires after user switches station
**What goes wrong:** Station A fails, user clicks Station B. Failover timer fires for Station A, tries A's next stream, interrupts B.
**How to avoid:** Cancel all timers and clear `_streams_queue` at the start of every `play()` call. Also clear `_on_failover` callback.

### Pitfall 4: Blocking time.sleep(2) in `_play_youtube` blocks GTK main loop
**What goes wrong:** `_play_youtube` calls `time.sleep(2)` on the main thread — freezes UI for 2 seconds.
**What to do:** This is pre-existing debt. Don't introduce additional blocking in this phase. The failover timeout for YouTube should be deferred until after the 2s sleep via the GLib timer — which it is, since the timer is armed after `_play_youtube` returns.

### Pitfall 5: `_streams_queue` includes the preferred stream twice
**What goes wrong:** preferred stream is first in queue AND also in its position-ordered slot — gets tried twice.
**How to avoid:** When building the queue, exclude the preferred stream from the position-ordered tail before appending it at the front.

### Pitfall 6: Adw.Toast `timeout=0` means "no auto-dismiss"
**What goes wrong:** Setting `timeout=0` thinking it means "immediate" — it actually means the toast stays until dismissed.
**How to avoid:** Use `timeout=3` (seconds) for "trying next" toasts; `timeout=5` for "all failed" toasts.

---

## Code Examples

### Correct GLib timeout pattern

```python
# Source: direct codebase inspection (GLib already imported in player.py)
self._failover_timer_id = GLib.timeout_add(
    BUFFER_DURATION_S * 1000,  # ms
    self._on_timeout_cb
)

def _on_timeout_cb(self) -> bool:
    self._failover_timer_id = None
    self._try_next_stream()
    return False  # CRITICAL: return False or it repeats every 10s
```

### Correct cross-thread callback via GLib.idle_add

```python
# Source: direct codebase inspection (player.py _on_gst_tag pattern)
# In player (bus callback thread):
if self._on_failover:
    GLib.idle_add(self._on_failover, failed_stream)

# In main_window (GTK main thread):
def _on_player_failover(self, stream):
    if stream is None:
        self._show_toast("All streams failed", timeout=5)
    else:
        self._show_toast("Stream failed — trying next...", timeout=3)
    return False  # GLib.idle_add expects False to not repeat
```

### Adw.ToastOverlay wrapping

```python
# Source: [ASSUMED] standard Adwaita pattern
self.toast_overlay = Adw.ToastOverlay()
self.toast_overlay.set_child(scroller)  # replaces shell.set_content(scroller)
shell.set_content(self.toast_overlay)
```

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (no config file — runs from project root) |
| Config file | none (implicit) |
| Quick run command | `python -m pytest tests/test_player_pause.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req | Behavior | Test Type | Command | File Exists? |
|-----|----------|-----------|---------|-------------|
| FAIL-01 | `_try_next_stream()` pops first stream and arms timeout | unit | `pytest tests/test_player_failover.py -x -q` | No — Wave 0 |
| FAIL-02 | GStreamer error triggers `_try_next_stream()` | unit | `pytest tests/test_player_failover.py::test_gst_error_triggers_failover -x -q` | No — Wave 0 |
| FAIL-03 | Timeout fires if no tag received within 10s | unit (mocked GLib) | `pytest tests/test_player_failover.py::test_timeout_triggers_failover -x -q` | No — Wave 0 |
| FAIL-04 | All streams exhausted stops playback and calls on_failover(None) | unit | `pytest tests/test_player_failover.py::test_all_streams_exhausted -x -q` | No — Wave 0 |
| FAIL-05 | Preferred stream goes first in queue | unit | `pytest tests/test_player_failover.py::test_preferred_stream_first -x -q` | No — Wave 0 |
| FAIL-06 | Manual stream pick bypasses queue (D-08) | unit | `pytest tests/test_player_failover.py::test_manual_pick_overrides_queue -x -q` | No — Wave 0 |
| FAIL-07 | Timer cancelled on stop/pause/new play | unit | `pytest tests/test_player_failover.py::test_timer_cancelled_on_stop -x -q` | No — Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_player_failover.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_player_failover.py` — covers FAIL-01 through FAIL-07
- All other test infrastructure already in place

---

## Open Questions

1. **Where to arm timeout for YouTube streams given the blocking sleep(2)**
   - What we know: `_play_youtube` blocks for 2s on the main thread. After that it returns. The GLib timer would be armed after return.
   - What's unclear: Is 10s measured from `_play_youtube()` return or from play() call? For consistency, measure from when the subprocess is launched (arm inside `_play_youtube` after the retry logic completes).
   - Recommendation: Arm timeout inside `_play_youtube` after the retry block. Accept the 2s pre-timer delay for YouTube — total effective timeout is ~12s which is fine.

2. **Icon name for stream picker**
   - What we know: Adwaita icon theme is used; icon names are checked at runtime.
   - What's unclear: Which signal/antenna icon names are available in the installed GTK4/Adw version.
   - Recommendation: Use `network-wireless-symbolic` as primary; fall back to `audio-card-symbolic`. Implementer should verify at runtime with `Gtk.IconTheme.get_for_display(...).has_icon(name)` or visually test.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `Adw.ToastOverlay` + `Adw.Toast.new()` + `set_timeout()` API is standard Adw 1.x | Architecture Patterns | Low — this is core Adwaita; safe to assume |
| A2 | `network-wireless-symbolic` is available in the Adwaita icon set | Open Questions | Low — fallback icon exists; visual-only impact |

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: `musicstreamer/player.py` — error handling, YouTube path, GLib usage
- Direct codebase inspection: `musicstreamer/repo.py` — `get_preferred_stream_url()` implementation
- Direct codebase inspection: `musicstreamer/ui/main_window.py` — controls_box layout, `_play_station()`, `_current_station` state
- Direct codebase inspection: `musicstreamer/constants.py` — `BUFFER_DURATION_S = 10`, `QUALITY_SETTING_KEY`
- Direct codebase inspection: `musicstreamer/models.py` — `StationStream` fields

### Secondary (MEDIUM confidence)
- `tests/test_player_pause.py` — established mocking pattern for Player tests
- `.planning/phases/28-stream-failover-logic-with-server-round-robin-and-quality-fa/28-CONTEXT.md` — all decisions verified

---

## Metadata

**Confidence breakdown:**
- Player failover logic: HIGH — all code paths visible, patterns clear
- Toast integration: HIGH — Adw.ToastOverlay is standard; one layout change needed
- Stream picker UI: HIGH — controls_box layout inspected, Gtk.MenuButton+Popover is standard
- YouTube failover: MEDIUM — mpv subprocess polling is more complex than GStreamer bus

**Research date:** 2026-04-09
**Valid until:** 2026-05-09
