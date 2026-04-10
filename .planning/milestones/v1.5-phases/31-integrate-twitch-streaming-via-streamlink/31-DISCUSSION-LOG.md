# Phase 31: Integrate Twitch streaming via streamlink - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-09
**Phase:** 31-integrate-twitch-streaming-via-streamlink
**Areas discussed:** Playback mechanism, Stream detection, Quality handling, Offline behavior

---

## Playback Mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| streamlink URL extraction | Use streamlink to resolve Twitch URL to direct HLS URL, then feed to GStreamer playbin3 | ✓ |
| streamlink pipe to mpv | Pipe streamlink output through mpv subprocess (similar to YouTube path) | |
| streamlink stdout pipe to GStreamer | Run streamlink piping raw audio to stdout, feed into GStreamer via fdsrc | |

**User's choice:** streamlink URL extraction
**Notes:** Keeps audio pipeline unified with ShoutCast path. Reuses existing GStreamer playbin3.

### Follow-up: HLS URL Expiry

| Option | Description | Selected |
|--------|-------------|----------|
| Re-resolve on error | When GStreamer hits error (expired URL), re-run streamlink for fresh URL | ✓ |
| Periodic re-resolve | Proactively re-resolve on timer before expiry | |
| Accept the gap | Let stream fail, rely on manual replay | |

**User's choice:** Re-resolve on error
**Notes:** Fits naturally into existing failover logic.

---

## Stream Detection

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-detect from URL | Check for twitch.tv domain, matching YouTube detection pattern | ✓ |
| Rely on stream_type field | User/import sets stream_type='twitch' explicitly | |
| Both — auto-detect + stream_type | Auto-detect primary, honor stream_type for edge cases | |

**User's choice:** Auto-detect from URL
**Notes:** Matches existing YouTube URL detection pattern. No user friction.

---

## Quality Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Single 'best' quality | Always request 'best' from streamlink. One stream entry per channel. | ✓ |
| Map to hi/med/low | Create 3 streams per channel mapping to existing quality tiers | |
| Expose all Twitch qualities | Query available qualities and create stream entry for each | |

**User's choice:** Single 'best' quality
**Notes:** Twitch ABR handles quality adaptation. Avoids 6+ stream entries per channel.

---

## Offline Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Show 'Channel offline' status | Detect streamlink's specific error, show distinct message, don't trigger failover | ✓ |
| Treat as normal stream error | Let it flow through existing failover logic | |
| Check online status before playing | Query Twitch API before play attempt | |

**User's choice:** Show 'Channel offline' status
**Notes:** Offline is not a stream error — station stays selected, toast notification shown.

---

## Claude's Discretion

- Exact streamlink subprocess invocation details
- Whether to auto-set stream_type='twitch' on URL detection at add time
- Toast wording and duration for offline state

## Deferred Ideas

None — discussion stayed within phase scope
