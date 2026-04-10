# Phase 33: Fix YT Video Playback Delay Until All Streams Failed Toast - Research

**Researched:** 2026-04-10
**Domain:** GLib timer choreography in `musicstreamer/player.py` + Adw.Toast feedback in `main_window.py`
**Confidence:** HIGH (focal code is small, fully read; test infrastructure is established)

## Summary

This is a small, surgical bug-fix phase in a single file (`player.py`) plus two toast call-site additions in `main_window.py`. The root cause is well isolated: `_yt_poll_cb` (lines 206-220) calls `_try_next_stream()` the moment mpv exits with non-zero, with no minimum wait — so a yt-dlp resolve blip on a still-good URL drains the queue in 1-2 seconds and surfaces "All streams failed" before the user sees any UI activity (Phase 28's `_is_first_attempt` gating intentionally suppresses the first failover toast). The fix has two independent halves: (1) gate `_yt_poll_cb`'s failover branch on a 15s monotonic-time window seeded in `_play_youtube`; (2) fire an `Adw.Toast` "Connecting…" on every `play()` and `play_stream()` call from `main_window`, regardless of stream type.

The codebase already establishes every pattern needed: `GLib.timeout_add` polling, `_*_timer_id` state, central `_cancel_failover_timer`, `Adw.ToastOverlay.add_toast`, and a fully mocked `Player` test pattern in `tests/test_player_failover.py` that already monkey-patches `musicstreamer.player.GLib` and `musicstreamer.player.time`. There is **no need** for a fake clock library — `time.monotonic` is already patchable via the existing `mock_time` pattern.

**Primary recommendation:** Use a `_yt_attempt_start_ts: float | None` monotonic timestamp seeded in `_play_youtube` and (re-seeded inside `_check_cookie_retry`), gated inside `_yt_poll_cb` against a new `YT_MIN_WAIT_S = 15` constant. Do NOT add a second `GLib.timeout_add` watchdog — the existing 1s poll loop already has the cadence we need; we just need it to defer the failover branch until the window elapses. For the toast, fire `_show_toast("Connecting\u2026", timeout=4)` from `main_window._on_play` and `_on_stream_picker_row_activated` immediately before calling `player.play(...)` / `player.play_stream(...)`. Keep it dead simple: do NOT try to programmatically dismiss the connecting toast when audio starts — Adw.ToastOverlay stacks gracefully and the 4s timeout is shorter than the 15s YT window anyway.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**YT Stream Minimum Wait Window**
- **D-01:** YT streams get a 15-second hard minimum wait window before `_try_next_stream` can fire. `_yt_poll_cb` may observe mpv exit earlier, but failover must not trigger until the window elapses. Matches yt-dlp's typical resolve-and-start-playback budget.
- **D-02:** The 15s window applies to **every** YT attempt in the queue, not just the first. Predictable and simple; a dead station with N streams takes up to N×15s to exhaust. This is an accepted tradeoff — the bug is user-visible premature failure, not slow dead-station recovery.
- **D-03:** "Stream is working" signal: **mpv process still running at end of the 15s window**. No mpv IPC, no stdout parsing. If mpv is alive at 15s, cancel the watchdog and let normal playback continue. If mpv has exited (any code) or hangs and then exits, fail over after the window closes.

**Connecting Feedback**
- **D-04:** On every `play()` / `play_stream()` invocation, show an `Adw.Toast` "Connecting…" immediately (before any stream resolution work). Applies to **all stream types** (GStreamer, YouTube, Twitch) — consistent feedback pattern, not YT-specific.
- **D-05:** The "Connecting…" toast auto-dismisses on a short timer (Claude's discretion — 3–5s) OR when audio actually starts (`_on_gst_tag` for GStreamer, 15s mpv-alive signal for YT). Toast overlap with "Stream failed — trying next…" is acceptable; Adw.ToastOverlay handles stacking.
- **D-06:** This supersedes Phase 28 D-06's "silent on first attempt" implicit behavior. Phase 28 decision was about failover toasts; this adds a distinct "connecting" toast on top without removing failover toasts.

**Cookie Retry Interaction**
- **D-07:** Existing 2-second "no-cookies retry" path in `_play_youtube` (`_check_cookie_retry`) stays as-is. The new 15s watchdog supervises the **current** mpv process — if the first mpv (with cookies) dies at 1s and gets replaced by a cookies-less mpv at 2s, the 15s window is measured against the replacement process. Net effect: a YT stream gets ~15s of mpv runtime to prove itself, regardless of cookie-retry substitution.

### Claude's Discretion
- Exact "Connecting…" toast message wording and timeout duration (3–5s range)
- Whether the 15s watchdog is implemented as a separate `GLib.timeout_add` guard on top of the existing `_yt_poll_cb`, or by adding a `_yt_attempt_start_ts` timestamp and gating `_try_next_stream` inside `_yt_poll_cb`
- Whether to reset/restart the 15s window when the cookie retry replaces the mpv process, or keep the original start time
- Whether `play_stream()` (manual stream picker) also gets the "Connecting…" toast (recommended: yes, for consistency)

### Deferred Ideas (OUT OF SCOPE)
- Detect specific mpv/yt-dlp failure modes (video unavailable, network error, auth required) for fast-fail on dead URLs
- Progress indicator in the title area (Connecting…/Resolving…/Buffering…) instead of a toast
- Adaptive timeout based on observed yt-dlp resolve time
</user_constraints>

<phase_requirements>
## Phase Requirements

Planner must add a new requirement (suggested ID: **FIX-07**) to `.planning/REQUIREMENTS.md` v1.5 Bug Fixes section, and map it in the Traceability table.

| ID | Description | Research Support |
|----|-------------|------------------|
| FIX-07 | YouTube streams get a 15s minimum wait window before failover (any mpv exit before 15s does not trigger `_try_next_stream`); a "Connecting…" Adw.Toast fires on every `play()`/`play_stream()` call for all stream types | `_yt_poll_cb` gating via `_yt_attempt_start_ts` seeded in `_play_youtube`; `_show_toast("Connecting\u2026", timeout=4)` added to `main_window._on_play` and `_on_stream_picker_row_activated` |

The single FIX-07 captures D-01 through D-05 as a unified bug fix. Sub-criteria for verification:
- (a) YT mpv exit at any time < 15s after attempt start does NOT call `_try_next_stream`
- (b) YT mpv still running at >= 15s clears `_yt_poll_timer_id` and lets playback continue
- (c) Cookie-retry substitution at 2s re-seeds `_yt_attempt_start_ts` so the replacement process gets its full 15s
- (d) `_show_toast("Connecting\u2026", ...)` is invoked on `_on_play` before `player.play(...)` and on `_on_stream_picker_row_activated` before `player.play_stream(...)`
- (e) `play()` invoked while a previous YT attempt is in flight cancels and re-seeds (covered by existing `_cancel_failover_timer` path; new state must be cleared there)
</phase_requirements>

## Project Constraints (from PROJECT.md / global CLAUDE.md)

- No project-level `./CLAUDE.md` exists; no `.claude/skills/` or `.agents/skills/` present.
- **Tech stack locked:** Python + GTK4/Libadwaita + GStreamer — no framework changes.
- **Test runner:** `uv run --with pytest pytest` (no system pip).
- **Developer profile directives:** terse responses, single recommended option, scope tight to request, minimal explanation. Plan should NOT include speculative refactors of `_yt_poll_cb` beyond what D-01..D-07 require.
- **Platform:** Linux GNOME desktop only — no cross-platform abstraction needed.

## Standard Stack

This phase touches **only existing dependencies**. No new packages.

### Core (already in tree, verified by reading source)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyGObject (`gi`) — `GLib`, `Gst` | system | Timer scheduling (`GLib.timeout_add`, `GLib.source_remove`) and pipeline control | The entire player is built on it; established pattern |
| libadwaita (`Adw`) via `gi` | system | `Adw.Toast`, `Adw.ToastOverlay.add_toast` for the connecting toast | Already used by `_show_toast` helper at `main_window.py:979` |
| `time` (stdlib) | 3.x | `time.monotonic()` for the attempt-start timestamp | Already imported at `player.py:6`; monotonic is correct here (not affected by wall-clock changes) |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `unittest.mock.MagicMock` / `patch` | stdlib | Mocks for `Player`, `GLib`, `subprocess.Popen`, `time` | Already the test pattern in `tests/test_player_failover.py` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Monotonic timestamp gate inside `_yt_poll_cb` | Separate `GLib.timeout_add(15000, _yt_min_wait_elapsed_cb)` watchdog | A second timer doubles the state to clean up in `_cancel_failover_timer`, doubles the chance of leaks on rapid play()→play(), and doesn't actually buy anything because the existing 1s poll loop is already running. **Recommended: timestamp gate.** [VERIFIED: read of player.py:206-220] |
| `time.monotonic()` | `time.time()` | Wall-clock can jump (NTP, suspend/resume); monotonic cannot. Use monotonic. [CITED: docs.python.org/3/library/time.html#time.monotonic] |
| Programmatic `Adw.Toast.dismiss()` when audio starts | Just rely on 4s timeout | Adw.Toast does have a `.dismiss()` method [CITED: gnome.pages.gitlab.gnome.org/libadwaita Adw.Toast]; however the connecting toast's 4s timeout is already shorter than the 15s YT window, so by the time the YT mpv-alive signal could fire, the toast is gone. For GStreamer streams, the 4s timeout matches typical buffer-fill latency. **Recommended: skip programmatic dismiss; D-05 explicitly allows visual overlap.** |

**Installation:**
```bash
# No new packages — phase uses existing imports only
```

**Version verification:** Skipped — no new packages introduced. Existing imports (`gi.repository.GLib`, `gi.repository.Gst`, `gi.repository.Adw`, stdlib `time`, `subprocess`) are already pinned via system PyGObject and have been working through Phases 1-32.

## Architecture Patterns

### Recommended Project Structure
No structural changes. Edits live in two files only:
```
musicstreamer/
├── constants.py        # Add: YT_MIN_WAIT_S = 15
├── player.py           # Edit: _play_youtube, _yt_poll_cb, _cancel_failover_timer, __init__
└── ui/
    └── main_window.py  # Edit: _on_play, _on_stream_picker_row_activated (add toast call)

tests/
└── test_player_failover.py  # Add: 4-5 new test functions for the 15s window
```

### Pattern 1: Monotonic Timestamp Gate (the focal change)
**What:** Record `time.monotonic()` when `_play_youtube` launches mpv. In `_yt_poll_cb`, before calling `_try_next_stream()`, check `time.monotonic() - self._yt_attempt_start_ts >= YT_MIN_WAIT_S`. If not yet elapsed, return `True` to keep polling.

**When to use:** Whenever you need a "minimum wait before action" gate alongside an existing poll loop. Cheaper than a second timer; trivially testable by patching `time.monotonic`.

**Example (proposed shape, not yet in tree):**
```python
# Source: derived from player.py:206-220 + tests/test_player_failover.py mock_time pattern
import time
from musicstreamer.constants import YT_MIN_WAIT_S

def _yt_poll_cb(self) -> bool:
    """Poll mpv. Failover only if mpv died AND minimum wait window elapsed."""
    if self._yt_proc is None:
        self._yt_poll_timer_id = None
        return False
    exit_code = self._yt_proc.poll()
    if exit_code is None:
        # Still running. Check if we've crossed the alive-at-15s threshold.
        if self._yt_attempt_start_ts is not None and \
           time.monotonic() - self._yt_attempt_start_ts >= YT_MIN_WAIT_S:
            # D-03: mpv alive at end of window = success signal. Stop polling.
            self._yt_poll_timer_id = None
            self._yt_attempt_start_ts = None
            return False
        return True  # keep polling
    # mpv has exited. Did the wait window elapse?
    if self._yt_attempt_start_ts is not None and \
       time.monotonic() - self._yt_attempt_start_ts < YT_MIN_WAIT_S:
        # Premature exit — keep waiting. The window enforces minimum dwell.
        # Note: mpv is dead, but we will not fail over until the window closes.
        return True
    # Exited and window elapsed (or nonzero) — fail over (or stop on clean exit)
    self._yt_poll_timer_id = None
    self._yt_attempt_start_ts = None
    if exit_code != 0:
        self._try_next_stream()
    return False
```

### Pattern 2: Toast on Every Play Call (the user feedback fix)
**What:** Wrap each `player.play(...)` / `player.play_stream(...)` call site in `main_window.py` with a preceding `self._show_toast("Connecting\u2026", timeout=4)`.

**Example:**
```python
# Source: main_window.py:962-971 (the play() call site)
self._show_toast("Connecting\u2026", timeout=4)  # NEW
self.player.play(st, on_title=_on_title,
                 preferred_quality=preferred_quality,
                 on_failover=self._on_player_failover,
                 on_offline=self._on_twitch_offline)
```

### Pattern 3: Centralized Timer Cleanup
**What:** Every new piece of timer/state on `Player` MUST be cleared by `_cancel_failover_timer` AND zeroed in `__init__`. The codebase has had timer leaks before; the central helper exists precisely so each new feature can hook in.

**Required cleanup additions:**
- `_cancel_failover_timer` must clear `self._yt_attempt_start_ts = None` (defensive — the gate is conditional on `is not None`).
- `__init__` must initialize `self._yt_attempt_start_ts: float | None = None`.

### Anti-Patterns to Avoid
- **Don't add a second `GLib.timeout_add(15000, …)`:** doubles state, doubles leak surface, no benefit over the timestamp gate. The existing 1s poll loop already runs.
- **Don't use `time.time()`:** susceptible to wall-clock jumps from NTP/suspend. Use `time.monotonic()`.
- **Don't try to dismiss the connecting toast when audio starts:** D-05 explicitly permits visual overlap; Adw.ToastOverlay stacks; the 4s timeout is shorter than the 15s YT alive signal anyway, so the dismiss code path would only ever fire for GStreamer streams that start in 0-4s — adds complexity for a degenerate case.
- **Don't gate the connecting toast on stream type:** D-04 says all stream types, unconditionally.
- **Don't remove `_is_first_attempt` gating in `_try_next_stream`:** Phase 33 specifics line 102 says it should NOT be removed. The connecting toast handles the initial-feedback gap; the failover-toast suppression on first attempt is still correct.
- **Don't reset `_yt_attempt_start_ts` inside `_yt_poll_cb`:** only `_play_youtube` (and `_check_cookie_retry`) should seed it; only `_cancel_failover_timer` and the success/failure terminals in `_yt_poll_cb` itself should clear it.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Sub-second wait gate | A custom thread `time.sleep(15)` then callback | `time.monotonic()` checked inside the existing 1s `GLib.timeout_add` poll | Threads in this player are reserved for `subprocess.run` blocking calls (Twitch resolve); GLib timers are the convention for everything else |
| "Stream is working" detection | mpv IPC socket parsing, stdout scraping, GStreamer pre-roll detection | `mpv_proc.poll() is None` after 15s | D-03 explicitly chose this — no IPC, no stdout parse |
| Toast lifecycle management | Custom GLib.timeout to manually destroy toasts | `Adw.Toast.set_timeout(seconds)` | Already used by `_show_toast`; libadwaita handles the rest |
| Fake clock for tests | `freezegun`, `time-machine` library | `patch("musicstreamer.player.time")` with `mock_time.monotonic.side_effect = [0.0, 1.0, 14.9, 15.1, ...]` | Already the established pattern in `test_player_failover.py:368` (`patch("musicstreamer.player.time")`) |

**Key insight:** Every primitive needed already lives in `player.py` or is one stdlib call away. This phase is gluework, not invention.

## Runtime State Inventory

This is a code-only bug fix. No rename, no migration, no data shape change.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — verified by reading constants.py and the focal player.py functions; no DB writes touched | None |
| Live service config | None — no external services configured by name | None |
| OS-registered state | None — no systemd/launchd/Task Scheduler/MPRIS metadata changes | None |
| Secrets/env vars | None — no env var or secret name changes | None |
| Build artifacts | None — pyproject.toml unchanged; pure Python edits | None |

## Common Pitfalls

### Pitfall 1: Forgetting to clear `_yt_attempt_start_ts` in `_cancel_failover_timer`
**What goes wrong:** A second `play()` arrives while a YT attempt is mid-flight. `_cancel_failover_timer` cancels the poll timer ID, but `_yt_attempt_start_ts` is still set to the old value. The new YT attempt's `_play_youtube` re-seeds it correctly so this is harmless **for YT→YT transitions**, but for **YT→GStreamer** transitions there's no re-seed and the stale timestamp lingers. Defensive cleanup avoids any future surprise.
**Why it happens:** Easy to forget; the existing helper only handles two timer IDs.
**How to avoid:** Add `self._yt_attempt_start_ts = None` to `_cancel_failover_timer`. Verified harmless because `_yt_poll_cb` only checks the value if the timer is also active.
**Warning signs:** A test that calls `play()` for YT, then `play()` for HTTP, then asserts `_yt_attempt_start_ts is None` would fail without the cleanup.

### Pitfall 2: Cookie retry path leaks the 15s window
**What goes wrong:** `_check_cookie_retry` (player.py:253-265) replaces `self._yt_proc` at the 2s mark. If `_yt_attempt_start_ts` is NOT re-seeded, the new mpv process inherits the original 0s timestamp and only gets 13s to prove itself. D-07 says the replacement process should get its full 15s.
**Why it happens:** The cookie retry was written before the 15s window existed.
**How to avoid:** Inside `_check_cookie_retry`, after the new `Popen`, re-seed `self._yt_attempt_start_ts = time.monotonic()`. This is the recommendation for the Claude's-discretion question on cookie-retry timestamp reset.
**Warning signs:** A test where the cookies-with mpv exits at 1s, the no-cookies mpv runs from 2s to 16s, and yet failover fires at second 15 (because the gate measured from second 0).

### Pitfall 3: `_yt_poll_cb` returning `False` accidentally on the "still running, window not yet elapsed" branch
**What goes wrong:** If you return `False` instead of `True` in the "still running" branch, GLib stops calling the timer, and a stream that's actually about to start playing gets abandoned silently (no failover, no success, just dead).
**Why it happens:** Boolean return values for GLib.timeout_add are easy to flip.
**How to avoid:** The "still running" branch returns `True` (keep polling). The "still running AND window elapsed = success" branch returns `False` (we're done). The "exited AND window elapsed" branch returns `False` (failover or terminate). The "exited AND window not yet elapsed" branch returns `True` (keep polling — yes, even though the process is gone; we just sit idle and wait for the window).
**Warning signs:** A test that asserts the timer survives until second 15 even when mpv has been dead since second 1.

### Pitfall 4: Connecting toast wired to `Player` instead of `MainWindow`
**What goes wrong:** Tempting to put the toast trigger inside `Player.play()` for tidiness. But `Player` has no toast overlay reference, and giving it one would break the clean separation that Phase 28 established (Player communicates via callbacks). The toast belongs at the `main_window` call sites.
**How to avoid:** Add `self._show_toast(...)` directly in `_on_play` and `_on_stream_picker_row_activated`, immediately before the `player.play(...)` / `player.play_stream(...)` line. Two lines of code, two locations.

### Pitfall 5: Twitch flow regression
**What goes wrong:** Twitch (`_play_twitch`) does NOT use `_yt_poll_cb` — it goes through `_on_twitch_resolved` → `_set_uri` → GStreamer playbin3, which arms the existing GStreamer 10s watchdog (`_failover_timer_id`). The new YT 15s window must NOT apply to Twitch. Verify by reading `_try_next_stream` (player.py:128): the GStreamer watchdog is armed only when the URL is neither YouTube nor Twitch, and Twitch arms its own GStreamer watchdog after `_on_twitch_resolved`. The new code touches `_play_youtube` only — Twitch is not affected.
**Verification:** `_play_twitch` does not set `_yt_attempt_start_ts`, does not set `_yt_proc`, and does not arm `_yt_poll_timer_id`. The new gate runs inside `_yt_poll_cb`, which never fires for Twitch. Confirmed by reading player.py:275-318.

### Pitfall 6: 15s test wall-clock blocking
**What goes wrong:** Naively writing `time.sleep(16)` in a test makes the suite take 16 seconds per test. With 4-5 new tests that's a minute of dead time.
**How to avoid:** Patch `musicstreamer.player.time` (the existing test pattern at `test_player_failover.py:368`). Set `mock_time.monotonic.side_effect = [0.0, 14.9, 15.1, ...]` to feed deterministic monotonic readings. Each call to `time.monotonic()` inside `_yt_poll_cb` consumes one value. Tests run in milliseconds.

## Code Examples

### Example 1: Constants addition
```python
# Source: musicstreamer/constants.py — add after line 28
# Phase 33 / FIX-07: minimum wait window before YT mpv failover can fire
YT_MIN_WAIT_S = 15
```

### Example 2: `__init__` state addition
```python
# Source: musicstreamer/player.py:48 — add after _is_first_attempt
self._yt_attempt_start_ts: float | None = None
```

### Example 3: `_cancel_failover_timer` cleanup addition
```python
# Source: musicstreamer/player.py:90-97 — add to existing helper
def _cancel_failover_timer(self):
    """Cancel pending failover timeout and YouTube poll timer."""
    if self._failover_timer_id is not None:
        GLib.source_remove(self._failover_timer_id)
        self._failover_timer_id = None
    if self._yt_poll_timer_id is not None:
        GLib.source_remove(self._yt_poll_timer_id)
        self._yt_poll_timer_id = None
    self._yt_attempt_start_ts = None  # NEW: Phase 33
```

### Example 4: `_play_youtube` seed
```python
# Source: musicstreamer/player.py:244 — immediately after Popen succeeds
self._yt_proc = subprocess.Popen(cmd, ...)
self._yt_attempt_start_ts = time.monotonic()  # NEW: Phase 33 / D-01
```

### Example 5: Cookie retry re-seed
```python
# Source: musicstreamer/player.py:259 — inside _check_cookie_retry, after new Popen
self._yt_proc = subprocess.Popen(cmd_no_cookies, ...)
self._yt_attempt_start_ts = time.monotonic()  # NEW: Phase 33 / D-07
```

### Example 6: main_window connecting toast (two call sites)
```python
# Source: main_window.py:968 — before player.play(...)
self._show_toast("Connecting\u2026", timeout=4)
self.player.play(st, on_title=_on_title, ...)

# Source: main_window.py:1044 — before player.play_stream(...)
self._show_toast("Connecting\u2026", timeout=4)
self.player.play_stream(stream, on_title=_on_title, ...)
```

### Example 7: Test pattern with mocked monotonic clock
```python
# Source: tests/test_player_failover.py — new test, derived from existing
# test_youtube_failover_polling pattern at line 343
def test_yt_premature_exit_does_not_failover_before_15s():
    p = make_player()
    p._pipeline = MagicMock()
    p._on_title = MagicMock()
    yt_stream = StationStream(id=1, station_id=1,
                              url="https://www.youtube.com/watch?v=test",
                              quality="hi", position=1)
    backup = make_stream(2, 2, "med")
    station = make_station_with_streams([yt_stream, backup])

    mock_yt_proc = MagicMock()
    mock_yt_proc.poll.return_value = 1  # exited non-zero
    poll_callbacks = []

    def capture_timeout(ms, cb):
        poll_callbacks.append(cb)
        return 100 + len(poll_callbacks)

    with patch.object(p, "_stop_yt_proc"), \
         patch("musicstreamer.player.subprocess.Popen", return_value=mock_yt_proc), \
         patch("musicstreamer.player.time") as mock_time, \
         patch("musicstreamer.player.GLib") as mock_glib:
        mock_glib.timeout_add.side_effect = capture_timeout
        mock_glib.idle_add.side_effect = lambda fn, *args: fn(*args)
        mock_glib.source_remove = MagicMock()
        # Feed monotonic readings: seed at 0.0, then poll at 1.0 (premature)
        mock_time.monotonic.side_effect = [0.0, 1.0]
        p.play(station, p._on_title)
        # Trigger the YT poll callback
        yt_poll_cb = poll_callbacks[-1]
        result = yt_poll_cb()
    # mpv exited at 1s but window not elapsed — must keep polling, NOT fail over
    assert result is True
    assert p._current_stream.url.endswith("v=test")  # still on YT, not on backup
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `_yt_poll_cb` fails over on any non-zero mpv exit | `_yt_poll_cb` defers failover until 15s monotonic window elapses | Phase 33 (this phase) | YT streams no longer drain queue in 1-2 seconds on transient resolve blips |
| Phase 28: silent on first attempt (no UI feedback until 2nd stream) | Phase 33: explicit "Connecting…" toast on every play() / play_stream() call | Phase 33 (this phase) | User sees immediate feedback that playback was attempted; first-attempt failover toast suppression remains in place |

**Deprecated/outdated:**
- None — this is additive. Phase 28's `_is_first_attempt` gating remains correct; Phase 33 simply provides a different feedback channel for the initial-attempt user experience.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Adw.Toast `set_timeout(4)` is honored as 4 seconds (not ms) and the toast auto-dismisses | Don't Hand-Roll, Code Examples | Low — already the established convention in `_show_toast(timeout=3)` and `_show_toast(timeout=5)` calls in main_window.py (lines 987, 990, 995) so this is consistent with existing usage and works in production. [VERIFIED: main_window.py:979-982] |
| A2 | `time.monotonic()` is the right clock here | Standard Stack | Negligible — Python docs recommend monotonic for elapsed-time measurements explicitly; suspend/resume on a desktop is exactly the case it handles correctly. [CITED: docs.python.org/3/library/time.html] |
| A3 | Patching `musicstreamer.player.time` will intercept `time.monotonic()` calls inside `_yt_poll_cb` and `_play_youtube` | Test infrastructure, Example 7 | Low — `test_player_failover.py:368` already does `patch("musicstreamer.player.time")` and it works because `player.py` does `import time` at module top (line 6), making `time` a name in the `musicstreamer.player` namespace. [VERIFIED: player.py:6 + test_player_failover.py:368] |
| A4 | Cookie retry path is exercised by enough real-world cookie failures that re-seeding the timestamp matters | Pitfall 2, Example 5 | Low — D-07 explicitly states the desired behavior; the cost of re-seeding is one line of code regardless of frequency. |
| A5 | The `Adw.ToastOverlay` stacks toasts cleanly when "Connecting…" overlaps with "Stream failed — trying…" | Don't Hand-Roll | Low — D-05 accepts overlap; libadwaita is documented to queue/stack toasts. If visual overlap is ugly in practice, that's a follow-up tweak, not a phase blocker. [ASSUMED based on libadwaita design intent] |

## Open Questions (RESOLVED)

1. **Should the connecting toast text include the station name?**
   - What we know: D-04 says "Connecting…" — message wording is Claude's discretion.
   - What's unclear: "Connecting to Lofi Girl…" is more informative but longer; "Connecting…" matches the terse style.
   - RESOLVED: Keep it short — `"Connecting\u2026"`. Station name is already visible in the now-playing panel.

2. **Should `play_stream()` (manual stream picker) get the connecting toast?**
   - What we know: CONTEXT.md Claude's discretion bullet recommends "yes, for consistency".
   - RESOLVED: Yes. Plan adds the toast at both `_on_play` and `_on_stream_picker_row_activated`.

## Environment Availability

This phase is pure code/config edits in two existing Python files plus tests. No external dependencies introduced or required beyond what's already running.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python `time` (stdlib) | Monotonic timestamp | ✓ | 3.x | — |
| PyGObject GLib | Existing timer | ✓ | system | — |
| PyGObject Adw | Existing toast helper | ✓ | system | — |
| pytest via `uv run --with pytest` | Test runner | ✓ | as used by 255 existing tests | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (with `unittest.mock`) |
| Config file | `pyproject.toml` (verified present in repo root) |
| Quick run command | `uv run --with pytest pytest tests/test_player_failover.py -x` |
| Full suite command | `uv run --with pytest pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FIX-07 (a) | YT mpv exit at < 15s does NOT call `_try_next_stream` | unit | `uv run --with pytest pytest tests/test_player_failover.py::test_yt_premature_exit_does_not_failover_before_15s -x` | ❌ Wave 0 |
| FIX-07 (b) | YT mpv alive at >= 15s clears poll timer + start timestamp, returns False | unit | `uv run --with pytest pytest tests/test_player_failover.py::test_yt_alive_at_window_close_succeeds -x` | ❌ Wave 0 |
| FIX-07 (c) | Cookie retry replacement re-seeds `_yt_attempt_start_ts` | unit | `uv run --with pytest pytest tests/test_player_failover.py::test_cookie_retry_reseeds_yt_window -x` | ❌ Wave 0 |
| FIX-07 (d) | `_show_toast("Connecting\u2026", ...)` invoked on `_on_play` and `_on_stream_picker_row_activated` | unit (main_window) | `uv run --with pytest pytest tests/test_player_failover.py::test_connecting_toast_fires_on_play -x` (or new file `tests/test_connecting_toast.py`) | ❌ Wave 0 |
| FIX-07 (e) | `_cancel_failover_timer` clears `_yt_attempt_start_ts` | unit | `uv run --with pytest pytest tests/test_player_failover.py::test_cancel_clears_yt_attempt_ts -x` | ❌ Wave 0 |
| FIX-07 regression | Twitch flow does not arm `_yt_poll_timer_id` or set `_yt_attempt_start_ts` | unit (sanity) | `uv run --with pytest pytest tests/test_twitch_playback.py -x` (existing) | ✓ |
| FIX-07 regression | Existing failover behavior on HTTP streams unchanged | unit (sanity) | `uv run --with pytest pytest tests/test_player_failover.py -x` (existing 14 tests) | ✓ |

### Sampling Rate
- **Per task commit:** `uv run --with pytest pytest tests/test_player_failover.py -x`
- **Per wave merge:** `uv run --with pytest pytest tests/test_player_failover.py tests/test_twitch_playback.py tests/test_player_buffer.py -x`
- **Phase gate:** Full suite green: `uv run --with pytest pytest` (255+ tests)

### Wave 0 Gaps
- [ ] Add 5 new test functions to `tests/test_player_failover.py` covering FIX-07 (a)–(e). Use existing `make_player()`, `patch("musicstreamer.player.GLib")`, `patch("musicstreamer.player.time")` patterns from test at line 343.
- [ ] No new test file required — `test_player_failover.py` is the right home. Connecting-toast assertion CAN live in a new `tests/test_connecting_toast.py` if main_window unit testing is preferred separated, but main_window has no existing test file in the listing — recommend adding the toast assertion as a focused unit test of the call-site by patching `MainWindow._show_toast` and `MainWindow.player.play` (this requires constructing a `MainWindow`, which may be heavy; easier alternative: refactor the toast call into a tiny helper and unit-test the helper, OR cover via UAT manually). **Recommended:** add a UAT step in plan verification rather than unit-testing main_window for FIX-07 (d), unless the planner wants the extra rigor.
- [ ] Framework install: not needed — pytest already used by 255 existing passing tests.

## Security Domain

Phase 33 is a UX/timing bug fix in trusted local code. No new attack surface.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — (no auth changes) |
| V3 Session Management | no | — (no sessions) |
| V4 Access Control | no | — (single-user desktop) |
| V5 Input Validation | no | — (no new input handled; URLs already validated upstream) |
| V6 Cryptography | no | — (no crypto) |
| V12 Files & Resources | no | — (no new file handling; cookie temp file logic already in place from Phase 22 unchanged) |

### Known Threat Patterns for {Python+GTK4+subprocess}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Subprocess argv injection via station URL | Tampering | Already mitigated: `subprocess.Popen(cmd, ...)` uses list args (no `shell=True`); URL passed as final positional arg. Phase 33 does not change this. [VERIFIED: player.py:244-248] |
| Timer leak under rapid play()→play() | DoS (resource) | `_cancel_failover_timer` centralizes cleanup; new state must hook in (Pitfall 1). |
| Stale tmp cookie files on crash | Information Disclosure (low) | Already mitigated: `__init__` cleans up `ms_cookies_*.txt` from `tempfile.gettempdir()` on each Player construction. [VERIFIED: player.py:51-57] |

No new threats introduced by Phase 33. Existing controls remain in place.

## Sources

### Primary (HIGH confidence)
- `musicstreamer/player.py` (full read) — every line of focal logic verified
- `musicstreamer/constants.py` (full read) — confirmed no `YT_MIN_WAIT_S` exists yet
- `musicstreamer/ui/main_window.py` lines 340-371, 950-1052 — toast helper and play call sites verified
- `tests/test_player_failover.py` (full read) — established test patterns for `Player`, `GLib`, `time`, `subprocess.Popen` mocking
- `.planning/phases/33-.../33-CONTEXT.md` — locked decisions (D-01..D-07)
- `.planning/phases/28-.../28-CONTEXT.md` — Phase 28 failover semantics still in force
- `.planning/phases/31-.../31-CONTEXT.md` — Twitch flow confirmed not affected
- `.planning/REQUIREMENTS.md`, `.planning/PROJECT.md`, `.planning/STATE.md` — milestone, requirements ID conventions, milestone deadline (2026-04-19)
- `.planning/config.json` — `nyquist_validation: true` confirmed → Validation Architecture section required

### Secondary (MEDIUM confidence)
- Python `time.monotonic()` semantics — stdlib documented behavior, well-known [CITED: docs.python.org/3/library/time.html#time.monotonic]
- `Adw.Toast.set_timeout` semantics — already used in `_show_toast` helper across the codebase, runtime-verified by app daily use [VERIFIED: main_window.py:979-991 + 11 phases of production use]

### Tertiary (LOW confidence)
- None — no claims in this research are based on unverified sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all primitives already in tree and verified by direct read
- Architecture: HIGH — focal change is small, isolated, and follows two existing patterns (timer state + central cleanup)
- Pitfalls: HIGH — pitfalls derived from reading the actual control flow and from the test file's existing assertions
- Validation: HIGH — test infrastructure mature (255 passing tests), monkey-patch idiom for `time` already proven in `test_player_failover.py:368`

**Research date:** 2026-04-10
**Valid until:** 2026-04-24 (14 days — focal code is stable, no upstream library updates expected to affect this)
