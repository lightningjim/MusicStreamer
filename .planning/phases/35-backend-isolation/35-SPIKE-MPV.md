# Phase 35 — mpv Drop Spike Result

**Ran:** 2026-04-11
**Environment:** GStreamer 1.26.6, yt-dlp 2026.03.17, Python 3.13.7
**Harness:** `.planning/phases/35-backend-isolation/spike/spike_mpv_drop.py`
**Cookies file:** `~/.local/share/musicstreamer/cookies.txt` (6324 bytes, present)

## Case Results

| Case | URL | Format selector | Result | Note |
|------|-----|-----------------|--------|------|
| a — YouTube live | `https://www.youtube.com/@LofiGirl/live` | `best[protocol^=m3u8]/best` | **PASS** | yt-dlp resolved cleanly; playbin3 received PLAYING + tag in 5.3s |
| b — HLS manifest | `https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8` | `best[protocol^=m3u8]/best` | **PASS** | Direct HLS manifest; playbin3 received PLAYING + tag in 1.4s |
| c — Cookie-protected | `https://www.youtube.com/@LofiGirl/live` (`cookiefile=~/.local/share/musicstreamer/cookies.txt`) | `best` | **FAIL** | yt-dlp resolve raised `DownloadError: [youtube] XSXEaikz0Bc: No video formats found!` when the cookie jar was attached. The same URL passes case (a) without cookies, isolating cookies as the failure surface. |
| d — Specific format | `https://www.youtube.com/@LofiGirl/live` | `best[height<=720][protocol^=m3u8]/best` | **PASS** | Format selector accepted; playbin3 received PLAYING + tag in 3.8s |

Spike was run twice with identical results to confirm reproducibility.

## Decision

**Decision:** KEEP_MPV

**Rationale:** Cases a, b, and d demonstrate that GStreamer `playbin3` can consume yt-dlp library-resolved URLs cleanly for the unauthenticated YouTube + HLS paths. However, case (c) — the cookie-protected path — fails reproducibly: when `cookiefile` is passed to `yt_dlp.YoutubeDL`, the resolver returns `No video formats found` for the same LoFi Girl live URL that resolves cleanly without cookies. This matches the A8 risk in 35-RESEARCH.md (cookie-jar injection is the most fragile path) and means we cannot guarantee that authenticated YouTube playback works through the pure-library path. Per D-22, any failing case mandates retaining mpv as the YouTube fallback so that real users with valid cookies (age-gated videos, members-only streams) keep working. The yt-dlp library API is still adopted for `yt_import.py` playlist scanning and unauthenticated resolution; only `_play_youtube()` retains its mpv subprocess fallback.

**Consequences for Plan 35-04:**
- Plan 35-04 retains `_play_youtube()` using `subprocess.Popen` for the mpv launcher path. The cookie-retry one-shot timer converts to `QTimer.singleShot`, and the YouTube poll timer converts to `QTimer`, but the mpv subprocess itself stays.
- Plan 35-04 introduces a minimal `musicstreamer/_popen.py` helper (PKG-03 pre-stage) that wraps `subprocess.Popen` so the future Windows port (Phase 44) only needs to add `CREATE_NO_WINDOW` in one place. This helper is used by `_play_youtube()` only this phase.
- `PKG-05` (mpv runtime dependency) **remains active** in REQUIREMENTS.md — do not retire it. The failing case above is the documented retention reason.
- `_play_twitch()` still ports to `streamlink.Streamlink().streams()` (D-18) — that path does not depend on this spike.
- `yt_import.py` still ports to `yt_dlp.YoutubeDL.extract_info(extract_flat='in_playlist')` (D-17) — playlist scanning does not need cookies and is unaffected by case (c).

**Followup risk to track:** If a future yt-dlp release fixes the cookies-injection regression for YouTube live, re-run this spike. If case (c) flips to PASS, mpv can be dropped at that time as a separate cleanup plan.

---

## Superseded 2026-04-11 (Plan 35-06)

Further investigation after this spike revealed that the case (c)
failure was misdiagnosed. The actual root cause is a YouTube
JavaScript challenge (n-sig decryption) that `yt-dlp` cannot solve
without a Node.js runtime and the EJS remote-components solver
script. Once YouTube's anti-bot system began pushing the challenge
globally (verified the same afternoon as the original spike run),
even cases (a), (b), and (d) — which had passed without cookies —
began failing with the same "No video formats found" error. Cookies
were a red herring on that specific error message.

**Verification (2026-04-11):** With `extractor_args={'youtubepot-jsruntime':
{'remote_components': ['ejs:github']}}` added to the yt-dlp library
call, the `LoFi Girl` live URL resolves to a direct HLS manifest in
library mode (without cookies, under a second), and GStreamer
`playbin3` plays that URL cleanly. The library API path — with EJS
enabled — handles every case the spike tested, including the
cookie-protected one in real-world conditions per user report.

**Critical insight:** mpv provides no *independent* URL resolution
path. mpv's `ytdl_hook.lua` shells out to the same `yt-dlp`
extractor code as the library API. When yt-dlp cannot solve the JS
challenge (because Node.js or the EJS solver script is missing),
mpv fails for the same reason. The KEEP_MPV branch was therefore
buying zero functional coverage over a pure library-API approach —
it was dead weight plus a binary that IT-restricted work machines
cannot install.

**Resolution:** Plan 35-06 drops mpv entirely, replaces
`_play_youtube()` with a `yt_dlp.YoutubeDL` worker-thread resolver
(mirroring the existing `_play_twitch` pattern), deletes
`musicstreamer/_popen.py`, retires `PKG-05` in `REQUIREMENTS.md`,
and adds `RUNTIME-01` (Node.js as a documented host prerequisite).

**Files:**
- `.planning/phases/35-backend-isolation/35-06-drop-mpv-yt-dlp-ejs-PLAN.md`
- `.planning/phases/35-backend-isolation/35-06-drop-mpv-yt-dlp-ejs-SUMMARY.md`
