---
phase: 31-integrate-twitch-streaming-via-streamlink
reviewed: 2026-04-09T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - musicstreamer/player.py
  - musicstreamer/ui/main_window.py
  - tests/test_twitch_playback.py
findings:
  critical: 0
  warning: 3
  info: 2
  total: 5
status: issues_found
---

# Phase 31: Code Review Report

**Reviewed:** 2026-04-09
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed Twitch streamlink integration in `player.py` and the corresponding UI wiring in `main_window.py`, plus the new test suite. The core flow (thread → streamlink → GLib.idle_add → GStreamer) is sound. Three logic issues were found: a `time.sleep(2)` on the GLib main thread in `_play_youtube`, offline detection keying on `result.stdout` only (misses cases where the message lands in `stderr`), and `_on_twitch_offline` not stopping the playback state. Two info items: a late `import glob` inside `__init__` and test boilerplate duplication across the file.

---

## Warnings

### WR-01: `time.sleep(2)` blocks the GLib main thread in `_play_youtube`

**File:** `musicstreamer/player.py:247`
**Issue:** `_play_youtube` is called from the GLib main loop (via `_try_next_stream`). The `time.sleep(2)` at line 247 blocks that thread for two full seconds on every YouTube play, freezing the UI (no redraws, no event handling). This is pre-existing but is made more visible by the new Twitch path drawing attention to the correct pattern (daemon thread + `GLib.idle_add`).
**Fix:** Move the cookie-retry logic into a short `GLib.timeout_add` callback instead of sleeping inline:
```python
def _check_cookie_retry():
    if self._yt_cookie_tmp and self._yt_proc and self._yt_proc.poll() is not None:
        import sys
        print("mpv exited immediately with cookies, retrying without", file=sys.stderr)
        self._cleanup_cookie_tmp()
        cmd_no_cookies = [a for a in cmd if not a.startswith("--ytdl-raw-options=cookies=")]
        self._yt_proc = subprocess.Popen(
            cmd_no_cookies,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env=env,
        )
    return False  # one-shot

# Replace time.sleep(2) + inline check with:
GLib.timeout_add(2000, _check_cookie_retry)
```

---

### WR-02: Offline detection checks `result.stdout` only — misses `stderr`

**File:** `musicstreamer/player.py:283`
**Issue:** The `_resolve` thread checks `"No playable streams found" in result.stdout`. Streamlink writes this error to `stderr`, not `stdout`. `subprocess.run` with `capture_output=True` populates both, but the current code ignores `result.stderr`, so the offline branch is never reached: the channel will always fall through to `_on_twitch_error` → `_try_next_stream` instead of the correct `_on_twitch_offline` path.
**Fix:**
```python
output = result.stdout + result.stderr
if result.returncode == 0 and resolved.startswith("http"):
    GLib.idle_add(self._on_twitch_resolved, resolved)
elif "No playable streams found" in output:
    GLib.idle_add(self._on_twitch_offline, url)
else:
    GLib.idle_add(self._on_twitch_error)
```

---

### WR-03: `_on_twitch_offline` does not stop the pipeline or clear `_on_title`

**File:** `musicstreamer/ui/main_window.py:993`
**Issue:** When a Twitch channel is offline, `_on_twitch_offline` shows a toast and calls `_pause_timer()` but does not tell the `Player` to stop. The GStreamer pipeline remains in whatever state `_play_twitch` left it (NULL after the `set_state(NULL)` call, but `_on_title` and `_on_failover` are still registered). If the user then clicks a different station, the previous callbacks are still live until `play()` clears them. More practically, calling `stop()` on the player was not done, so a re-resolve retry could still fire if a GStreamer error arrives asynchronously.
**Fix:** Call `self.player.stop()` before (or instead of) just `_pause_timer()`:
```python
def _on_twitch_offline(self, channel: str):
    self._show_toast(f"{channel} is offline", timeout=5)
    self.player.stop()   # clear pipeline + callbacks
    self._pause_timer()
    return False
```

---

## Info

### IN-01: `import glob` inside `__init__` should be a top-level import

**File:** `musicstreamer/player.py:52`
**Issue:** `import glob` is deferred inside `__init__`. The module is part of the standard library; there is no reason to defer it. It also imports `sys` late at line 250 for the same reason.
**Fix:** Move both to the top of the file alongside `os`, `shutil`, etc.:
```python
import glob
import sys
```

---

### IN-02: Test helper `capture_thread` is duplicated across six test functions

**File:** `tests/test_twitch_playback.py:127-133`
**Issue:** The pattern of intercepting `threading.Thread` and immediately running the target is copy-pasted into `test_streamlink_called_with_correct_args`, `test_streamlink_env_includes_local_bin`, `test_live_channel_calls_set_uri`, `test_offline_channel_calls_on_offline`, and `test_non_offline_error_calls_try_next`. This makes the tests harder to maintain.
**Fix:** Extract it into a module-level fixture or helper:
```python
def _make_thread_runner():
    """Returns a side_effect for mock Thread that runs the target synchronously."""
    captured = []
    def side_effect(**kwargs):
        captured.append(kwargs.get("target"))
        t = MagicMock()
        t.start = lambda: captured[0]() if captured else None
        return t
    return side_effect
```

---

_Reviewed: 2026-04-09_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
