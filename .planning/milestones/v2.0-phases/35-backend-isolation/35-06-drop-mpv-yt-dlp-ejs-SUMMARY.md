# Plan 35-06: Drop mpv, use yt-dlp library with EJS + cookies — Summary

**Completed:** 2026-04-11
**Supersedes:** Phase 35 KEEP_MPV spike decision
**Requirements closed:** PORT-09 (full), RUNTIME-01 (new), PKG-05 (retired)

## Outcome

mpv is fully removed from MusicStreamer. `_play_youtube()` now resolves
YouTube stream URLs via `yt_dlp.YoutubeDL` with the EJS JavaScript
challenge solver enabled, and feeds the resolved HLS manifest URL to
GStreamer `playbin3`. No external player process is launched.

GStreamer is the sole playback backend for every stream type:
ShoutCast/HTTP, HLS, Radio-Browser, AudioAddict, Twitch (via streamlink
library), and YouTube (via yt-dlp library). `musicstreamer/_popen.py`
is deleted; `musicstreamer/player.py` has zero `subprocess` usage.

## Why this supersedes the original spike

The original Phase 35 spike (`35-SPIKE-MPV.md`) reported case (c)
— cookie-protected YouTube — as a fatal failure that mandated keeping
mpv. The error message ("No video formats found") was interpreted as
evidence that yt-dlp's library API couldn't handle cookiefile
injection.

That diagnosis was wrong. The same afternoon as the spike run, YouTube
pushed a global JS challenge (n-sig decryption) that blocks all
unauthenticated stream URL resolution. The "cases (a), (b), (d) pass"
results from the spike were time-fragile — a retest hours later
failed the same way without cookies.

The real fix is `extractor_args={'youtubepot-jsruntime': {'remote_components':
['ejs:github']}}` + a Node.js runtime on PATH. Verified 2026-04-11:
the LoFi Girl live URL resolves cleanly through the library API with
EJS enabled, and `playbin3` plays the returned HLS manifest directly.

The user's real-world experience confirms: cookies + EJS is a
legitimate path they need, but mpv never provided an independent
resolution — mpv shells out to the same `yt-dlp` extractor code via
its `ytdl_hook.lua` script, so mpv is broken whenever yt-dlp is. Thus
keeping mpv bought zero functional coverage while adding a binary
dependency that the user's IT-restricted work laptop blocks.

## What changed

### Code (`musicstreamer/`)

- **`player.py`** — `_play_youtube()` rewritten as a thin kicker that
  spawns `_youtube_resolve_worker` on a daemon thread (mirrors the
  existing `_play_twitch` pattern). The worker calls
  `yt_dlp.YoutubeDL.extract_info` with `extractor_args` for EJS and
  `cookiefile` if present, then emits `youtube_resolved(url)` or
  `youtube_resolution_failed(msg)` back to the main thread via queued
  Qt signal. `_on_youtube_resolved` calls `_set_uri()` and arms the
  normal failover timer; `_on_youtube_resolution_failed` emits
  `playback_error` and advances the failover queue.
  Removed entirely: `_open_mpv_log`, `_check_cookie_retry`,
  `_yt_poll_cb`, `_stop_yt_proc`, `_cleanup_cookie_tmp`, the
  `_yt_poll_timer` QTimer, `_yt_proc`, `_yt_cookie_tmp`,
  `_yt_attempt_start_ts`, and the `YT_MIN_WAIT_S` gate (the 15s
  workaround for mpv startup latency is unnecessary with the
  library-API resolver which completes in 1-3 seconds).
- **`_popen.py`** — deleted. No subprocess launches remain in
  `musicstreamer/`.
- **New class-level Qt Signals on `Player`:** `youtube_resolved`,
  `youtube_resolution_failed` (both queued to main thread).

### Tests

- `tests/test_cookies.py` — replaced the 4 mpv-era tests
  (`test_mpv_uses_temp_cookie_copy`,
  `test_mpv_no_cookies_when_absent`,
  `test_mpv_fallback_no_cookies_on_copy_failure`,
  `test_mpv_cleans_up_temp_cookie_on_stop`) with 2 library-API tests
  that verify `cookiefile` + EJS `extractor_args` are passed through
  correctly.
- `tests/test_player_failover.py` — replaced the `_yt_poll_timer` /
  FIX-07 15s-gate tests with 3 library-resolver tests (happy path,
  DownloadError path, thread-spawn). Dropped all `_stop_yt_proc`
  patches from the 8 surrounding tests since the helper is gone.
- `tests/test_player_pause.py` — deleted `test_pause_kills_yt_proc`;
  added `test_pause_clears_streams_queue` instead.
- `tests/test_player_volume.py` — renamed
  `test_set_volume_stores_for_mpv` → `test_set_volume_stores_on_player`.
- `tests/test_player_tag.py`, `tests/test_twitch_playback.py` —
  dropped `_stop_yt_proc` patches from the unrelated tests that
  referenced the now-gone helper.

### Documentation

- **`REQUIREMENTS.md`** — PORT-09 marked Complete with a note
  referencing Plan 35-06. PKG-05 marked Retired (Plan 35-06),
  struck-through with explanation. New RUNTIME-01 requirement added
  describing the Node.js host prerequisite. Traceability table updated
  (PORT-09 Complete, RUNTIME-01 Complete, PKG-05 Retired).
- **`PROJECT.md`** — Stack listing annotated with v2.0 Phase 35
  changes (PySide6 replaces GTK4, Node.js joins the stack, mpv
  removed). New Key Decisions row capturing the supersession of the
  KEEP_MPV spike decision.
- **`ROADMAP.md`** — Phase 35 plans list updated to include 35-06.
  Phase 44 scope note updated: PKG-05 removed from the requirements
  list, success criteria rewritten to document Node.js as a host
  prerequisite (not bundled) and PKG-03 as a no-op at ship time.
- **`35-SPIKE-MPV.md`** — new "Superseded 2026-04-11 (Plan 35-06)"
  section appended at the bottom explaining the misdiagnosis and the
  correct resolution.

## Test results

```
$ QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q
272 passed in 2.67s
```

Net test delta: -3 (removed 4 mpv-specific tests + 1 cookie-retry
test; added 3 library-API resolver tests + 2 cookiefile/EJS option
tests). QA-02's ≥265-test gate remains satisfied.

## Commits

- `4e0d791` feat(35-06): drop mpv, resolve YouTube via yt-dlp library + EJS solver
- `d589ad9` test(35-06): rewrite YouTube-playback tests against yt-dlp library API
- (doc commits to follow in same session)

## Runtime requirements added

**RUNTIME-01 (new):** Node.js must be present on PATH at app startup.
yt-dlp uses it via the EJS solver to handle YouTube JS challenges.
Not bundled by the Windows installer — documented as a host
prerequisite. Both target machines for v2.0 already have Node.js
installed for unrelated work (confirmed by user 2026-04-11).

## Deferred / no followups

None. Phase 35 is now truly complete, including the YouTube path.
Phase 36 (Qt Scaffold + GTK Cutover) can proceed without any
carry-over from 35-06.
</content>
</invoke>
