# Phase 23: Fix YouTube Stream Playback — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-07
**Phase:** 23-fix-youtube-stream-playback-broken-on-cli-and-app
**Areas discussed:** Root cause diagnosis, Fix strategy

---

## Root Cause Diagnosis

Diagnostic steps performed:
1. Verified mpv and yt-dlp both work from CLI — confirmed working
2. Tested app's exact Python code path — works from terminal
3. User reported: all YT stations fail, worked before today (phase 22 changes), blip of audio then silence
4. Tested with cookies.txt renamed away — playback restored immediately
5. Examined cookies.txt — contained Chrome-epoch timestamps and all-domain cookies from yt-dlp's browser extraction, not from the app's Google login
6. Root cause: yt-dlp's `--cookies` flag overwrites the file after reading it, corrupting the user's imported cookies

**User's insight:** Same issue encountered in yt-player project. yt-dlp overwrites cookie files passed via `--cookies`.

**Decision:** Use temp copies of cookies.txt for all yt-dlp/mpv invocations to keep the original pristine.

---

## Claude's Discretion

- Temp file cleanup strategy (NamedTemporaryFile vs manual)
- Retry-without-cookies timeout threshold (~2 seconds)

## Deferred Ideas

None
