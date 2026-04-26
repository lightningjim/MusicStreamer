---
phase: 35
plan: "35-06"
name: drop-mpv-yt-dlp-ejs
wave: 5
depends_on: ["35-04", "35-05"]
autonomous: true
requirements: [PORT-09]
files_modified:
  - musicstreamer/player.py
  - musicstreamer/_popen.py
  - tests/test_cookies.py
  - tests/test_player_failover.py
  - tests/test_player_pause.py
  - tests/test_player_volume.py
  - .planning/REQUIREMENTS.md
  - .planning/PROJECT.md
  - .planning/ROADMAP.md
must_haves:
  - `_play_youtube()` resolves URLs via `yt_dlp.YoutubeDL` library with EJS JS challenge solver and cookiefile, then plays through `playbin3` — no external player process
  - `musicstreamer/_popen.py` is deleted; no subprocess launches remain in `player.py`
  - `PKG-05` is retired in `REQUIREMENTS.md` and the rationale in `35-SPIKE-MPV.md` is annotated as superseded
  - `PROJECT.md` stack listing removes mpv and adds Node.js as a runtime requirement for yt-dlp EJS
  - All tests green under `QT_QPA_PLATFORM=offscreen pytest -q`
---

# Plan 35-06: Drop mpv, use yt-dlp library with EJS + cookies

## Objective

Supersede the KEEP_MPV branch from the original Phase 35 spike. After the spike decision was made, investigation revealed that:

1. The "cookie-protected YouTube fails" symptom is actually a separate yt-dlp JavaScript-challenge issue (unrelated to cookies), solvable with `extractor_args={'youtubepot-jsruntime': {'remote_components': ['ejs:github']}}` + a Node.js runtime.
2. mpv does not provide an independent resolution path — it shells out to the same yt-dlp extractor code via `ytdl_hook.lua`, so mpv cannot play streams that yt-dlp itself cannot resolve.
3. The user's work laptop has IT restrictions on mpv but already has Node.js and VLC installed. Node.js is the runtime requirement that actually matters for yt-dlp EJS.

Result: mpv is dead weight. Drop it entirely, call yt-dlp library directly, feed the resolved URL to GStreamer `playbin3`. Node.js becomes a documented runtime requirement.

## Context & Rationale

- The original spike (`35-SPIKE-MPV.md`) passed cases a/b/d by chance — they ran during a window when YouTube had not yet pushed the JS-challenge requirement. By 2026-04-11 afternoon, running the same spike without `--remote-components ejs:github` fails on those same cases. So the spike's "PASS" verdict was time-fragile.
- Case (c) (cookie-protected) failed with `No video formats found`, which the spike attributed to cookies. In fact the same error fires without cookies once JS-challenge solving is required — cookies were a red herring on that specific error message.
- EJS solver enabled through `extractor_args` successfully resolves LoFi Girl live (`https://www.youtube.com/@LofiGirl/live`) to a direct HLS manifest URL in library mode, verified 2026-04-11.
- The user confirmed: Node.js is available on both Linux dev machine and work laptop (for unrelated work projects), so adding it as a runtime dep has zero onboarding cost.

## Tasks

### Task 35-06-01 — player.py: drop mpv subprocess path, add yt-dlp resolver worker

<read_first>
- musicstreamer/player.py (the target)
- musicstreamer/_popen.py (to understand what it was)
- musicstreamer/paths.py (cookies_path helper)
</read_first>

<action>
Rewrite `_play_youtube()` to mirror the existing `_play_twitch()` pattern: resolve on a daemon worker thread via `yt_dlp.YoutubeDL`, emit a queued Qt signal carrying the resolved URL, handler on the main thread calls `_set_uri()` and arms `_failover_timer`.

Concrete changes inside `musicstreamer/player.py`:

1. Remove imports:
   - `from musicstreamer._popen import popen as _popen`
   - `import shutil` (only used for `shutil.which` in mpv path lookup and `shutil.copy2` for temp cookie copy — neither needed now)
   - `import tempfile` (only used for temp cookie copy)
   - Drop `YT_MIN_WAIT_S` from the constants import

2. Add two new class-level Signals on `Player`:
   ```python
   youtube_resolved              = Signal(str)   # internal: resolved HLS URL, queued to main thread
   youtube_resolution_failed     = Signal(str)   # internal: yt-dlp error message, queued to main thread
   ```

3. In `Player.__init__`, wire queued connections immediately after the existing `twitch_resolved` connection:
   ```python
   self.youtube_resolved.connect(self._on_youtube_resolved, Qt.ConnectionType.QueuedConnection)
   self.youtube_resolution_failed.connect(self._on_youtube_resolution_failed, Qt.ConnectionType.QueuedConnection)
   ```

4. Remove from `__init__`:
   - `self._yt_poll_timer = QTimer(self)` block (three lines: constructor, setInterval, timeout.connect)
   - `self._yt_attempt_start_ts: float | None = None`
   - `self._yt_proc = None`
   - `self._yt_cookie_tmp: str | None = None`

5. Replace the existing `_play_youtube()` body with:
   ```python
   def _play_youtube(self, url: str) -> None:
       """Resolve YouTube URL via yt_dlp library on a worker thread (EJS JS
       challenge solver + cookies if available), then play the resolved HLS
       URL through playbin3. Requires a Node.js runtime for EJS solving.
       """
       self._pipeline.set_state(Gst.State.NULL)
       # Fallback title shows station name immediately while resolver runs.
       if self._current_station_name:
           self.title_changed.emit(self._current_station_name)
       threading.Thread(
           target=self._youtube_resolve_worker, args=(url,), daemon=True
       ).start()

   def _youtube_resolve_worker(self, url: str) -> None:
       import yt_dlp
       opts = {
           "quiet": True,
           "no_warnings": True,
           "skip_download": True,
           "format": "best[protocol^=m3u8]/bestaudio/best",
           "extractor_args": {
               "youtubepot-jsruntime": {"remote_components": ["ejs:github"]},
           },
       }
       cookies = paths.cookies_path()
       if os.path.exists(cookies):
           opts["cookiefile"] = cookies
       try:
           with yt_dlp.YoutubeDL(opts) as ydl:
               info = ydl.extract_info(url, download=False)
       except Exception as e:
           self.youtube_resolution_failed.emit(str(e))
           return
       resolved = (info or {}).get("url") or ""
       if not resolved:
           formats = (info or {}).get("formats") or []
           if formats:
               resolved = formats[-1].get("url") or ""
       if not resolved:
           self.youtube_resolution_failed.emit("No video formats returned")
           return
       self.youtube_resolved.emit(resolved)

   def _on_youtube_resolved(self, resolved_url: str) -> None:
       self._set_uri(resolved_url)
       self._failover_timer.start(BUFFER_DURATION_S * 1000)

   def _on_youtube_resolution_failed(self, msg: str) -> None:
       self.playback_error.emit(f"YouTube resolve failed: {msg}")
       self._try_next_stream()
   ```

6. Delete these methods entirely:
   - `_open_mpv_log`
   - `_check_cookie_retry`
   - `_yt_poll_cb`
   - `_stop_yt_proc`
   - `_cleanup_cookie_tmp`

7. Replace every `self._stop_yt_proc()` call site (pause(), stop(), failover timeout handler, _try_next_stream non-YT branch) with just removal — they are no-ops now.

8. Remove the `_yt_poll_timer.stop()` / `_yt_attempt_start_ts = None` lines from the failover timeout handler (~line 276).

9. Update the module docstring header: replace the "Spike branch ... KEEP_MPV" paragraph with a note that mpv was dropped in Plan 35-06 after the spike rationale was superseded; reference `35-SPIKE-MPV.md` for history.
</action>

<acceptance_criteria>
- `grep -c "subprocess" musicstreamer/player.py` returns `0`
- `grep -c "_popen" musicstreamer/player.py` returns `0`
- `grep -c "mpv" musicstreamer/player.py` returns `0`
- `grep -c "_yt_proc\|_yt_cookie_tmp\|_yt_poll_timer\|_yt_attempt_start_ts\|_open_mpv_log\|_check_cookie_retry\|_stop_yt_proc\|_cleanup_cookie_tmp" musicstreamer/player.py` returns `0`
- `grep -c "youtube_resolved\s*=\s*Signal" musicstreamer/player.py` returns `1`
- `grep -c "youtube_resolution_failed\s*=\s*Signal" musicstreamer/player.py` returns `1`
- `grep -c "extractor_args" musicstreamer/player.py` returns at least `1`
- `grep -c "ejs:github" musicstreamer/player.py` returns at least `1`
- `.venv/bin/python -c "from musicstreamer.player import Player; Player"` exits 0 (import smoke)
</acceptance_criteria>

### Task 35-06-02 — delete `_popen.py`

<read_first>
- musicstreamer/_popen.py (the file being deleted)
</read_first>

<action>
`git rm musicstreamer/_popen.py`. No other code in the project imports it once Task 35-06-01 lands (verify with `grep -r '_popen' musicstreamer/`).
</action>

<acceptance_criteria>
- `test ! -f musicstreamer/_popen.py`
- `grep -rc "from musicstreamer._popen" musicstreamer/ tests/` returns `0`
- `grep -rc "musicstreamer\._popen" musicstreamer/ tests/` returns `0`
</acceptance_criteria>

### Task 35-06-03 — test suite updates

<read_first>
- tests/test_cookies.py
- tests/test_player_failover.py
- tests/test_player_pause.py
- tests/test_player_volume.py
</read_first>

<action>
- `tests/test_cookies.py`: delete the 4 mpv tests (`test_mpv_uses_temp_cookie_copy`, `test_mpv_no_cookies_when_absent`, `test_mpv_fallback_no_cookies_on_copy_failure`, `test_mpv_cleans_up_temp_cookie_on_stop`) and the supporting "mpv YouTube playback cookie injection" comment block. Replace with two new tests:
  - `test_youtube_resolve_passes_cookiefile_when_present`: monkeypatch `paths.cookies_path` to return a real path and `yt_dlp.YoutubeDL` to a recording fake. Call `player._youtube_resolve_worker('https://youtube.com/live/abc')`. Assert the `opts` passed to `YoutubeDL` contains `"cookiefile"` equal to that path AND `"extractor_args"` contains the EJS remote component.
  - `test_youtube_resolve_omits_cookiefile_when_absent`: monkeypatch `paths.cookies_path` to return a non-existent path. Assert `"cookiefile"` is NOT in the `opts` dict.

- `tests/test_player_failover.py`: rewrite the `_play_youtube`-related tests (lines ~246 onward, including the FIX-07 15s-gate tests) to mock `yt_dlp.YoutubeDL`:
  - Happy-path test: patch `yt_dlp.YoutubeDL` to return a fake whose `extract_info` returns `{"url": "http://resolved.example/stream.m3u8"}`. Call `player.play(station)`. Use `qtbot.waitSignal(player.youtube_resolved, timeout=3000)`. Assert `_set_uri` was called with the resolved URL and `_failover_timer` is active.
  - Failure test: patch `extract_info` to raise `yt_dlp.utils.DownloadError("boom")`. Use `qtbot.waitSignal(player.youtube_resolution_failed)`. Assert `playback_error` fires and `_try_next_stream` is invoked (next stream in queue popped).
  - Delete `test_yt_poll_exit_before_15s_keeps_polling`, `test_yt_poll_alive_at_15s_succeeds`, `test_cookie_retry_reseeds_attempt_start`. Reason: FIX-07's 15s gate was a workaround for mpv startup latency, which no longer applies. BUFFER_DURATION_S failover timer (10s) gates all streams uniformly.

- `tests/test_player_pause.py::test_pause_kills_yt_proc`: delete this test. Pause now just sets pipeline to NULL; there's no subprocess to kill. Keep the other pause tests.

- `tests/test_player_volume.py::test_set_volume_stores_for_mpv`: rename to `test_set_volume_stores_on_player` and verify the volume is stored on the Player object (for use by GStreamer pipeline), not passed to any external process.
</action>

<acceptance_criteria>
- `QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q tests/test_cookies.py tests/test_player_failover.py tests/test_player_pause.py tests/test_player_volume.py` exits 0 with no failures
- `grep -c "_popen\|mpv" tests/test_cookies.py tests/test_player_failover.py tests/test_player_pause.py tests/test_player_volume.py` returns `0`
- `grep -c "extractor_args\|ejs:github" tests/test_cookies.py` returns at least `2` (one per new test)
- `QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q` full suite exits 0 with ≥265 tests passing
</acceptance_criteria>

### Task 35-06-04 — documentation updates

<read_first>
- .planning/REQUIREMENTS.md
- .planning/PROJECT.md
- .planning/ROADMAP.md
- .planning/phases/35-backend-isolation/35-SPIKE-MPV.md
</read_first>

<action>
- `REQUIREMENTS.md`:
  - PKG-05: change status to "Retired (Plan 35-06)" or move to a new "Retired" subsection. Add one-line note: "Superseded by yt-dlp EJS solver + Node.js runtime dep; see Plan 35-06."
  - PORT-09: update notes to say "yt-dlp library API covers all paths including cookie-protected YouTube via EJS JS-challenge solver."
  - Add runtime requirement (NEW): "RUNTIME-01: Node.js runtime must be present on PATH for yt-dlp EJS JavaScript challenge solver (yt-dlp `--remote-components ejs:github` code path)."

- `PROJECT.md`:
  - Stack section: remove mpv reference; add "Node.js (runtime — yt-dlp JS challenge solver)".
  - Key Decisions table: add row "Dropped mpv subprocess fallback | yt-dlp library with EJS solver handles cookie-protected + JS-challenged YouTube | Plan 35-06, supersedes Phase 35 spike KEEP_MPV decision".

- `ROADMAP.md`:
  - Phase 44 section: update scope note to remove mpv bundling; change to "PyInstaller + GStreamer runtime. No external player to bundle; Node.js is a host-system requirement, not bundled."
  - Phase 35 section: append a one-line note that Plan 35-06 superseded the KEEP_MPV spike decision.

- `35-SPIKE-MPV.md`: append a new section at the bottom:
  ```
  ## Superseded 2026-04-11 (Plan 35-06)

  Further investigation after this spike revealed that the case (c)
  failure was misdiagnosed: the real culprit is a YouTube JS challenge
  that yt-dlp cannot solve without `--remote-components ejs:github` +
  a Node.js runtime. With EJS enabled, the yt-dlp library API
  successfully resolves YouTube live streams (including cookie-
  protected paths in most cases). mpv provides no independent
  resolution — it shells out to the same yt-dlp extractor internally.

  Plan 35-06 drops mpv entirely. See
  `.planning/phases/35-backend-isolation/35-06-drop-mpv-yt-dlp-ejs-PLAN.md`.
  ```
</action>

<acceptance_criteria>
- `grep -c "PKG-05.*[Rr]etired\|PKG-05.*[Ss]uperseded" .planning/REQUIREMENTS.md` returns at least `1`
- `grep -c "RUNTIME-01\|Node.js runtime" .planning/REQUIREMENTS.md` returns at least `1`
- `grep -c "mpv" .planning/PROJECT.md` returns `0` (or only historical mentions inside completed-phase narrative, which stay)
- `grep -c "Superseded.*Plan 35-06" .planning/phases/35-backend-isolation/35-SPIKE-MPV.md` returns `1`
</acceptance_criteria>

## Verification

Run after all tasks complete:
```
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q
```
Must show ≥265 tests passing with zero failures.

Manual smoke (optional, network-dependent):
```
.venv/bin/python -m musicstreamer https://www.youtube.com/@LofiGirl/live
```
Should print `ICY: ...` updates and playback audio (if a sink is available).

## Rollback

If Plan 35-06 causes unforeseen breakage, revert the commits. The prior KEEP_MPV state is fully committed (`028be0a` through `e87a78b`) and restores cleanly with `git revert`.
</content>
</invoke>
