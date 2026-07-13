# Phase 95: YT URL-change replay bug — Context

**Gathered:** 2026-06-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix the YouTube URL-change replay bug: after a YouTube station's stream URL is
edited, the **first** play attempt fails with "stream exhausted" and only the
**second** play picks up the new URL.

Root cause (high confidence, from codebase investigation): on save,
`repo.update_stream()` persists the new URL and `NowPlayingPanel.bind_station()`
refreshes the *panel's* station reference, but the `Player`'s in-memory
`_streams_queue` (and the already-loaded playbin3 URI) is never invalidated. The
stale resolved-URL state survives the edit — the next play/failover re-uses the
old stream (already at EOS → "stream exhausted"), and only a full
`play(fresh_station)` rebuild picks up the new URL.

Scope is limited to invalidating/refreshing stale player state on stream edit so
the new URL takes effect on the first play. No new playback capabilities, no
editor redesign.

</domain>

<decisions>
## Implementation Decisions

### Currently-playing edit behavior
- **D-01:** When the user saves an edit to the URL of the station that is
  **currently playing**, the player restarts **immediately** on the new URL —
  stop the old stream, re-resolve, and play the new URL. The user should hear the
  new stream right after saving, with no second play required. This is the
  primary, user-facing fix for the reported bug.
- **D-02:** The immediate restart fires **only when the URL of the
  currently-playing stream actually changed**. Edits that change only metadata
  (label, quality, codec, bitrate, etc.) on the playing stream must NOT interrupt
  audio. Compare the edited stream's saved URL against what is currently loaded;
  restart only on a real URL change.

### Stale-state invalidation (the fix mechanism)
- **D-03:** The fix must invalidate the `Player`'s cached stream state on stream
  edit, not just the now-playing panel. After an edit, the player must never
  serve a stale resolved URL or a stale `_streams_queue` entry for the edited
  stream. The "first play exhausts, second play works" asymmetry must be gone:
  the first play after an edit uses the saved URL.

### Multi-stream / failover granularity (Claude's Discretion, defaulted)
- **D-04:** For stations with multiple streams (the Phase 27 multi-stream model /
  Phase 28 failover ordering): trigger the immediate restart (D-01) only when the
  **currently-playing** stream's URL changed. If a *different* (non-playing)
  stream in the same station is edited, do not interrupt current audio — just
  invalidate the player's queue so subsequent failover uses the fresh URLs.

### Edit-while-not-playing (Claude's Discretion, defaulted)
- **D-05:** When a station that is **not** currently playing is edited, there is
  no audio to interrupt; the requirement is simply that the **next** `play()`
  rebuilds from fresh DB state (no stale `_streams_queue` / playbin3 URI carried
  over from a prior session of that station). Pressing play after editing must
  always use the saved URL.

### Claude's Discretion
- Exact invalidation mechanism (e.g. a `Player.bind_station()` / queue-reset
  method vs. clearing the resolved-URL/playbin3 state vs. re-issuing `play()`),
  the precise URL-comparison normalization, and where the restart is wired
  (edit-save handler vs. `_sync_now_playing_station`) are left to
  research/planning, provided the behavior in D-01–D-05 holds.

</decisions>

<specifics>
## Specific Ideas

- The repro is specifically YouTube (yt-dlp-resolved) streams, where the resolved
  HLS URL is dynamic — but the fix should not be YouTube-only if the same stale
  `_streams_queue` / loaded-URI path affects direct or Twitch streams. The
  *observable* bug is YouTube; the *mechanism* (stale player state on edit) is
  generic. Prefer a generic invalidation over a YouTube special-case.
- "Stream exhausted" is the user-visible symptom string surfaced from the
  failover path when the loaded stream emits EOS immediately. Verifying the fix
  means: edit a playing YouTube station's URL → hear the new stream on the first
  play, with no "stream exhausted" toast.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

No formal external specs/ADRs exist for this bug fix. The authoritative behavior
contracts live in prior-phase artifacts and the codebase maps below.

### Multi-stream model & failover (behavior this fix must respect)
- `.planning/milestones/v1.5-ROADMAP.md` — Phase 27 (Multi-Stream Model) and
  Phase 28 (Stream Failover): how a station holds multiple ordered streams and
  how failover consumes the queue.
- `.planning/codebase/ARCHITECTURE.md` — Player responsibilities: failover queue
  management, YouTube resolver (yt-dlp + Node.js), GStreamer playbin3 pipeline.

### Primary source files (investigation citations)
- `musicstreamer/player.py` — `play()`, `_try_next_stream()`, `_play_youtube()`,
  `_youtube_resolve_worker()`, `_set_uri()`, `_streams_queue`; the
  "stream exhausted" / `failover(None)` path.
- `musicstreamer/ui_qt/edit_station_dialog.py` — `_on_save()` (writes URL via
  `repo.update_stream`, emits `station_saved`).
- `musicstreamer/ui_qt/main_window.py` — `_on_edit_requested()` /
  `_sync_now_playing_station()` (refreshes panel station, does NOT touch player).
- `musicstreamer/ui_qt/now_playing_panel.py` — `bind_station()` /
  `_populate_stream_picker()`.
- `musicstreamer/repo.py` — `update_stream()`, `get_station()`, `list_streams()`.
- `musicstreamer/models.py` — `Station`, `StationStream` dataclasses.
- `musicstreamer/stream_ordering.py` — `order_streams()` (failover ordering).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `NowPlayingPanel.bind_station(station)` already re-fetches and rebinds a fresh
  station from the DB on edit — the analog/missing piece is an equivalent
  player-side rebind/invalidation.
- `Player.play(station)` already rebuilds `_streams_queue` from
  `station.streams` via `order_streams()`; the fix can reuse this rebuild path
  rather than inventing a new one.

### Established Patterns
- Player runs YouTube resolution on a daemon thread and marshals the resolved URL
  back to the Qt main thread via the `youtube_resolved` signal → `_on_youtube_resolved` → `_set_uri`.
- Cross-thread state is signal/slot marshaled (QueuedConnection); any restart
  trigger must respect the main-thread/bus-thread boundary.

### Integration Points
- The edit→player wiring currently terminates at `_sync_now_playing_station`
  (panel-only). The fix adds a player-side notification at the same junction
  (edit-save handler or `_sync_now_playing_station`).

</code_context>

<deferred>
## Deferred Ideas

- None new — discussion stayed within the bug-fix scope.

### Reviewed Todos (not folded)
- `2026-05-10-pls-codec-bitrate-url-fallback.md` (PLS codec/bitrate URL fallback)
  — keyword-matched but unrelated; belongs to PLS import (Phase 92 territory).
- `2026-05-26-host-env-docker-info-probe.md` (docker daemon probe) — unrelated to
  this YT replay bug.

</deferred>

---

*Phase: 95-yt-url-change-replay-bug-post-edit-stream-exhausted-on-first*
*Context gathered: 2026-06-18*
