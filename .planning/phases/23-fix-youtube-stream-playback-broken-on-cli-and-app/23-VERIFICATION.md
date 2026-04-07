---
phase: 23-fix-youtube-stream-playback-broken-on-cli-and-app
verified: 2026-04-07T13:00:00Z
status: human_needed
score: 4/4 must-haves verified
human_verification:
  - test: "Play a YouTube station, then inspect ~/.local/share/musicstreamer/cookies.txt"
    expected: "mtime and content hash unchanged after playback begins"
    why_human: "Cannot run mpv/GStreamer in test environment; file-system side effect requires live subprocess"
  - test: "After playback stops, run: ls /tmp/ms_cookies_* 2>/dev/null"
    expected: "No leftover temp files"
    why_human: "Cleanup depends on _stop_yt_proc being called by the live app; automated tests mock subprocess"
---

# Phase 23: Fix YouTube Stream Playback Verification Report

**Phase Goal:** yt-dlp and mpv use temporary copies of cookies.txt so the original imported file is never overwritten; corrupted cookies trigger automatic retry without auth
**Verified:** 2026-04-07T13:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Original cookies.txt is never modified by yt-dlp or mpv invocations | VERIFIED | `shutil.copy2(COOKIES_PATH, cookie_tmp/self._yt_cookie_tmp)` in both files; temp path passed to subprocess, not COOKIES_PATH; `test_ytdlp_uses_temp_cookie_copy` and `test_mpv_uses_temp_cookie_copy` assert original content unchanged |
| 2 | Temp cookie files are cleaned up after subprocess exits or is stopped | VERIFIED | `finally: os.unlink(cookie_tmp)` in yt_import.py; `_cleanup_cookie_tmp()` called in `_stop_yt_proc()` in player.py; `test_ytdlp_cleans_up_temp_cookie` and `test_mpv_cleans_up_temp_cookie_on_stop` pass |
| 3 | Copy failure falls back to no-cookies playback | VERIFIED | Both files catch `OSError` and set cookie_tmp/self._yt_cookie_tmp to None, proceeding without --cookies; `test_ytdlp_fallback_no_cookies_on_copy_failure` and `test_mpv_fallback_no_cookies_on_copy_failure` pass |
| 4 | mpv retries without cookies if it exits within 2 seconds | VERIFIED | `time.sleep(2)` + `self._yt_proc.poll() is not None` check triggers second Popen call with cookies flag stripped; `test_mpv_retry_without_cookies_on_fast_exit` and `test_mpv_no_retry_on_slow_exit` pass |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/player.py` | Temp cookie copy for mpv, cleanup on stop, retry-without-cookies logic | VERIFIED | Contains `import tempfile`, `import shutil`, `import time`, `self._yt_cookie_tmp`, `shutil.copy2(COOKIES_PATH, self._yt_cookie_tmp)`, `_cleanup_cookie_tmp()`, retry block with `retrying without` message |
| `musicstreamer/yt_import.py` | Temp cookie copy for yt-dlp, cleanup after subprocess.run | VERIFIED | Contains `import tempfile`, `import shutil`, `shutil.copy2(COOKIES_PATH, cookie_tmp)`, `os.unlink(cookie_tmp)` in finally block |
| `tests/test_cookies.py` | 8 new tests for temp-copy, cleanup, fallback, retry | VERIFIED | All 8 functions present in section 5; all 17 tests in file pass (0 failures) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `musicstreamer/player.py` | COOKIES_PATH | `shutil.copy2` to tempfile, temp path to mpv | WIRED | Line 107: `shutil.copy2(COOKIES_PATH, self._yt_cookie_tmp)` |
| `musicstreamer/yt_import.py` | COOKIES_PATH | `shutil.copy2` to tempfile, temp path to yt-dlp | WIRED | Line 40: `shutil.copy2(COOKIES_PATH, cookie_tmp)` |
| `musicstreamer/player.py` | `_stop_yt_proc` | cleanup temp cookie file on mpv termination | WIRED | Line 91: `self._cleanup_cookie_tmp()` called in `_stop_yt_proc` |

### Data-Flow Trace (Level 4)

Not applicable — this phase modifies subprocess invocation logic, not data rendering.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All cookie tests pass | `python -m pytest tests/test_cookies.py -v` | 17 passed in 0.05s | PASS |
| Temp copy used, not original path | test_ytdlp_uses_temp_cookie_copy, test_mpv_uses_temp_cookie_copy | Both PASS | PASS |
| Cleanup after subprocess | test_ytdlp_cleans_up_temp_cookie, test_mpv_cleans_up_temp_cookie_on_stop | Both PASS | PASS |
| Fallback on OSError | test_ytdlp_fallback_no_cookies_on_copy_failure, test_mpv_fallback_no_cookies_on_copy_failure | Both PASS | PASS |
| Retry on fast exit | test_mpv_retry_without_cookies_on_fast_exit | PASS | PASS |
| No retry on slow exit | test_mpv_no_retry_on_slow_exit | PASS | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| FIX-02 | 23-01-PLAN.md | yt-dlp/mpv cookie invocations use a temporary copy of cookies.txt so the original imported file is never overwritten | SATISFIED | Truths 1, 2, 3 verified; shutil.copy2 + mkstemp + finally-cleanup in both files |
| FIX-03 | 23-01-PLAN.md | If mpv exits immediately (~2s) with cookies, retry once without cookies to handle corrupted cookie files | SATISFIED | Truth 4 verified; time.sleep(2) + poll() + cmd_no_cookies retry in player.py |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `musicstreamer/player.py` | 112 | `launch_time = time.monotonic()` assigned but never read | Warning | None — retry works correctly via `time.sleep(2)` + `poll()`; dead variable is cosmetic |

### Human Verification Required

#### 1. Original cookies.txt integrity after live playback

**Test:** Start a YouTube station from the app. After mpv launches, check `~/.local/share/musicstreamer/cookies.txt` mtime and md5sum.
**Expected:** File is unchanged — same mtime and same content hash as before playback.
**Why human:** Cannot run mpv/GStreamer/yt-dlp in the test environment; the automated tests mock all subprocesses. File-system side-effect requires a live subprocess run.

#### 2. Temp file cleanup after live playback stop

**Test:** Start a YouTube station, then stop it. Run `ls /tmp/ms_cookies_* 2>/dev/null`.
**Expected:** No leftover temp files.
**Why human:** Cleanup depends on `_stop_yt_proc()` being called through the live GTK app's stop/pause path. Automated tests mock subprocess and verify cleanup in isolation, but the full signal chain through the UI has not been exercised.

### Gaps Summary

No automated gaps. All 4 roadmap success criteria are satisfied by substantive, wired, tested implementation. Two human verification items remain for live-run confirmation of the file-system side effects.

---

_Verified: 2026-04-07T13:00:00Z_
_Verifier: Claude (gsd-verifier)_
