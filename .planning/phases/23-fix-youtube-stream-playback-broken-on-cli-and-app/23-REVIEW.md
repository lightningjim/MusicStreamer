---
phase: 23-fix-youtube-stream-playback-broken-on-cli-and-app
reviewed: 2026-04-07T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - musicstreamer/player.py
  - musicstreamer/yt_import.py
  - tests/test_cookies.py
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 23: Code Review Report

**Reviewed:** 2026-04-07
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Three files reviewed covering the YouTube playback and cookie-handling changes. No security vulnerabilities. The main actionable issue is a 2-second `time.sleep` on the main GTK thread which will freeze the UI. There is also a dead variable, a missing null guard in `yt_import`, and a redundant dead-assertion block in the test.

## Warnings

### WR-01: `time.sleep(2)` on main thread freezes the GTK UI

**File:** `musicstreamer/player.py:120`
**Issue:** `_play_youtube` is called from `play()` which runs on the GTK main thread. `time.sleep(2)` blocks that thread entirely, freezing the window for two seconds on every YouTube station switch. Even in a CLI context it blocks the event loop if one is running.
**Fix:** Move the poll-and-retry to a background thread or a `GLib.timeout_add` callback:

```python
def _play_youtube(self, url, fallback_name, on_title):
    self._stop_yt_proc()
    self._pipeline.set_state(Gst.State.NULL)
    env = ...
    cmd = ...
    self._yt_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, env=env)
    on_title(fallback_name)
    # Schedule the retry check off-thread so the UI stays responsive
    GLib.timeout_add(2000, self._check_yt_proc_retry, cmd, env)

def _check_yt_proc_retry(self, cmd, env):
    if self._yt_cookie_tmp and self._yt_proc and self._yt_proc.poll() is not None:
        import sys
        print("mpv exited immediately with cookies, retrying without", file=sys.stderr)
        self._cleanup_cookie_tmp()
        cmd_no_cookies = [a for a in cmd if not a.startswith("--ytdl-raw-options=cookies=")]
        self._yt_proc = subprocess.Popen(
            cmd_no_cookies, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env
        )
    return False  # don't repeat
```

---

### WR-02: Dead variable `launch_time` — unused after assignment

**File:** `musicstreamer/player.py:112`
**Issue:** `launch_time = time.monotonic()` is assigned but never read. The retry logic uses a fixed 2-second sleep, not a duration computed from `launch_time`. This is dead code that implies intent (e.g. a planned "fast-exit" threshold) that was never wired up — a future maintainer may rely on it incorrectly.
**Fix:** Remove the line, or wire it into the retry condition if a variable threshold was intended:

```python
# Remove entirely:
# launch_time = time.monotonic()

# OR, if the intent was "exited within N seconds of launch", replace time.sleep check with:
elapsed = time.monotonic() - launch_time
if self._yt_cookie_tmp and self._yt_proc.poll() is not None and elapsed < 3:
    ...
```

---

### WR-03: `entry.get("url")` can be `None` in `scan_playlist`, propagated to DB insert

**File:** `musicstreamer/yt_import.py:73`
**Issue:** `entry.get("url") or entry.get("webpage_url")` returns `None` if both keys are absent or falsy. This `None` is stored in the returned dict and then passed directly to `repo.station_exists_by_url(url)` and `repo.insert_station(url=...)` in `import_stations` (line 91, 95). Inserting a `None` URL will either raise a DB constraint error or silently store a broken station.
**Fix:** Skip entries with no resolvable URL:

```python
resolved_url = entry.get("url") or entry.get("webpage_url")
if not resolved_url:
    continue
entries.append({
    "title": entry.get("title", "Untitled"),
    "url": resolved_url,
    "provider": entry.get("playlist_channel") or entry.get("playlist_uploader", ""),
})
```

---

## Info

### IN-01: `import sys` deferred inside `_play_youtube` hot path

**File:** `musicstreamer/player.py:122`
**Issue:** `import sys` is inside a conditional branch that can execute on every fast-exit retry. `sys` is a stdlib module that is always already loaded, so this has no correctness impact, but it is a code-quality convention violation — imports belong at the top of the module.
**Fix:** Add `import sys` at the top of `player.py` alongside the other stdlib imports.

---

### IN-02: `_stop_yt_proc` leaves finished Popen referenced when process already exited

**File:** `musicstreamer/player.py:88-91`
**Issue:** When `self._yt_proc.poll()` returns non-`None` (process already finished), the guard skips `terminate()` but also skips `self._yt_proc = None`. The finished `Popen` object remains referenced until the next `_play_youtube` call overwrites it. This is not a crash, but prevents GC of the subprocess object and is inconsistent with the running-process branch.
**Fix:**
```python
def _stop_yt_proc(self):
    if self._yt_proc:
        if self._yt_proc.poll() is None:
            self._yt_proc.terminate()
        self._yt_proc = None
    self._cleanup_cookie_tmp()
```

---

### IN-03: Dead assertion block in `test_mpv_uses_cookies_when_file_exists`

**File:** `tests/test_cookies.py:117-130`
**Issue:** The test calls `_play_youtube` twice. The first call (lines 117-122) computes `cmd` from `mock_proc.call_args` but `mock_proc` is not the `Popen` mock — it is the return value. `cmd` ends up as `None` and no assertion is made on it. Only the second call (inside the second `with patch(...)` block) is actually tested. The first block is dead and misleading.
**Fix:** Remove the first `with patch("subprocess.Popen")` block (lines 117-123) entirely. The test is already complete with the second block.

---

_Reviewed: 2026-04-07_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
