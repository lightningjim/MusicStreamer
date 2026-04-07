# Phase 23: Fix YouTube Stream Playback — Context

**Gathered:** 2026-04-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix YouTube stream playback regression caused by yt-dlp overwriting the user's imported cookies.txt. Make cookie usage resilient so playback never breaks due to cookie file corruption.

</domain>

<decisions>
## Implementation Decisions

### Root Cause
- **D-01:** yt-dlp's `--cookies` flag both READS and WRITES the cookie file. When mpv calls yt-dlp internally with `--cookies ~/.local/share/musicstreamer/cookies.txt`, yt-dlp overwrites the user's clean imported cookies with its own format (Chrome-epoch timestamps, all-domain cookies). Next playback attempt fails because the corrupted file confuses yt-dlp/mpv.

### Fix Strategy
- **D-02:** Use a temporary copy of cookies.txt for every yt-dlp/mpv invocation. Copy `COOKIES_PATH` to a temp file, pass the temp file path to `--cookies` / `--ytdl-raw-options=cookies=`. The original imported cookies stay pristine.
- **D-03:** The temp file should be cleaned up after the subprocess exits (for `scan_playlist`) or when the mpv process is terminated (for `_play_youtube`). Use `tempfile.NamedTemporaryFile(delete=False)` and manual cleanup.
- **D-04:** If cookies.txt exists but copying fails, fall back to no-cookies playback rather than failing silently.

### Resilience
- **D-05:** If mpv exits immediately (within ~2 seconds) when cookies are provided, retry once without the `--cookies` flag. This handles the case where existing cookies are already corrupted. Log the retry to stderr for debugging.

</decisions>

<canonical_refs>
## Canonical References

No external specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Files to Modify
- `musicstreamer/player.py:83-100` — `_play_youtube()`: copy cookies to temp, pass temp path to mpv, clean up on stop
- `musicstreamer/yt_import.py:32-34` — `scan_playlist()`: copy cookies to temp, pass temp path to yt-dlp, clean up after subprocess
- `tests/test_cookies.py` — Update tests to verify temp-copy behavior

### Established Patterns
- `subprocess.Popen` for mpv (player.py), `subprocess.run` for yt-dlp (yt_import.py)
- `COOKIES_PATH` constant from `musicstreamer/constants.py`
- `os.path.exists(COOKIES_PATH)` guard already in both files

### Integration Points
- `_stop_yt_proc()` in player.py — needs to clean up temp cookie file when mpv is terminated
- Both `player.py` and `yt_import.py` independently create temp copies (no shared helper needed — different lifecycles)

</code_context>

<specifics>
## Specific Ideas

- User experienced the same yt-dlp cookie overwrite issue in another project (yt-player). Temp working copy is the proven fix.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 23-fix-youtube-stream-playback-broken-on-cli-and-app*
*Context gathered: 2026-04-07*
