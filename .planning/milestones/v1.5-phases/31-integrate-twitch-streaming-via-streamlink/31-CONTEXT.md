# Phase 31: Integrate Twitch streaming via streamlink - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Enable playback of Twitch live streams using streamlink as the stream URL resolver, integrated into the existing multi-stream player and failover architecture. Twitch URLs are auto-detected and resolved to direct HLS URLs fed to GStreamer playbin3.

</domain>

<decisions>
## Implementation Decisions

### Playback Mechanism
- **D-01:** Use `streamlink --stream-url <twitch_url> best` to resolve Twitch URLs to direct HLS/MPEG-TS URLs, then feed the resolved URL to GStreamer playbin3 (same pipeline as ShoutCast/HTTP streams).
- **D-02:** On GStreamer error (including expired HLS URL), re-run streamlink to get a fresh URL and resume playback. This reuses the existing failover error handler — when the error is from a Twitch stream, re-resolve before trying the next stream in the queue.

### Stream Detection
- **D-03:** Auto-detect Twitch URLs by checking for `twitch.tv` in the URL string, matching the existing pattern for YouTube (`youtube.com`/`youtu.be` checks in player.py). No need for the user to set `stream_type` explicitly.

### Quality Handling
- **D-04:** Always request `best` quality from streamlink. Twitch stations are modeled as a single stream entry per channel — no multi-quality stream variants. Twitch ABR handles quality adaptation natively.

### Offline Behavior
- **D-05:** Detect streamlink's "no playable streams" error specifically and show "Channel offline" status in now-playing. Do NOT trigger failover — offline is not a stream error. Station stays selected (like pause). Show `Adw.Toast` with "[channel] is offline".

### Claude's Discretion
- Exact streamlink subprocess invocation details (env setup, error parsing)
- Whether to store `stream_type='twitch'` automatically when a twitch.tv URL is detected at add/import time
- Toast message wording and duration for offline state

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Player
- `musicstreamer/player.py` — Current playback paths: GStreamer playbin3 for HTTP streams, mpv subprocess for YouTube. Twitch adds a third detection branch (streamlink URL resolution → GStreamer).
- `musicstreamer/player.py:93-117` — `_try_next_stream()` failover logic; Twitch re-resolve on error hooks in here.
- `musicstreamer/player.py:202-245` — `_play_youtube()` as reference for subprocess-based URL resolution pattern.

### Models & Data
- `musicstreamer/models.py` — `StationStream` dataclass with `stream_type` field (can be set to 'twitch')
- `musicstreamer/repo.py` — Station/stream CRUD; no changes expected unless stream_type auto-detection at insert time

### Failover (Phase 28)
- `.planning/phases/28-stream-failover-logic-with-server-round-robin-and-quality-fa/28-CONTEXT.md` — D-01 through D-06 define failover triggers, retry strategy, and toast notifications that Twitch integration must respect.

### Multi-stream model (Phase 27)
- `.planning/phases/27-add-multiple-streams-per-station-for-backup-round-robin-and-/27-CONTEXT.md` — D-01 defines `station_streams` table schema including `stream_type` field.

No external specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- GStreamer playbin3 pipeline — Twitch HLS URLs play directly through existing pipeline after streamlink resolution
- `_try_next_stream()` failover loop — Twitch re-resolve integrates as a pre-step before advancing to next stream
- `Adw.Toast` pattern — used for failover notifications; reuse for "Channel offline"
- `_play_youtube()` subprocess pattern — reference for streamlink subprocess invocation (env setup, PATH handling)

### Established Patterns
- URL domain detection in `_try_next_stream()` — `if "youtube.com" in url or "youtu.be" in url` pattern; extend with `"twitch.tv" in url`
- `GLib.idle_add` for cross-thread UI updates from subprocess results
- `subprocess.Popen` with `DEVNULL` stderr for external tool invocation

### Integration Points
- `_try_next_stream()` — add Twitch URL detection branch alongside YouTube detection
- `_on_gst_error()` — for Twitch streams, re-resolve URL via streamlink before calling `_try_next_stream()`
- `main_window` — needs to handle "Channel offline" callback distinct from failover notification

</code_context>

<specifics>
## Specific Ideas

- streamlink must be installed as an external dependency (like mpv/yt-dlp) — document this as a runtime requirement
- The `--stream-url` flag outputs just the URL to stdout, perfect for extraction
- HLS URLs from streamlink typically expire after ~6 hours; re-resolve on error handles this transparently
- Twitch offline state is distinct from stream failure — streamlink returns a specific error message that can be parsed

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 31-integrate-twitch-streaming-via-streamlink*
*Context gathered: 2026-04-09*
