# Phase 33: Fix YT video playback delay until all streams failed toast - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-10
**Phase:** 33-fix-yt-video-playback-delay-until-all-streams-failed-toast
**Areas discussed:** Symptom diagnosis, YT minimum wait, Connecting feedback, Success signal, Scope, Cookies interaction

---

## Symptom Diagnosis

| Option | Description | Selected |
|--------|-------------|----------|
| Dead YT URL (video removed/private) | Station points at a video that no longer exists — mpv/yt-dlp fails, but slowly | |
| yt-dlp resolve is just slow | Network/yt-dlp takes 10-30s per stream before mpv starts or dies | |
| mpv hangs without exiting | mpv stays alive but no audio ever comes through — poll never sees non-zero exit | |
| Not sure — just know it's slow | User notices the delay but hasn't diagnosed the cause | ✓ |

**User's choice:** "Not sure, it just stops with [the all streams failed toast] before any streams seems to maybe start"
**Notes:** This clarified the real symptom — it's not a slow delay to the toast, it's a premature toast with zero prior feedback. Root cause traced to `_yt_poll_cb` (player.py:206–220) firing failover on any mpv non-zero exit with no minimum window, combined with Phase 28's intentional silence on first attempt.

---

## YT Stream Minimum Wait Window

| Option | Description | Selected |
|--------|-------------|----------|
| 15s hard minimum | Don't fail over a YT stream until 15s have passed, regardless of mpv exit | ✓ |
| 10s (match GStreamer) | Reuse BUFFER_DURATION_S | |
| 30s generous | Headroom for slow networks but slow dead-station recovery | |

**User's choice:** 15s hard minimum
**Notes:** Tighter than 30s to keep dead-station exhaustion reasonable, looser than 10s because yt-dlp resolve alone can burn 5–10s.

---

## Connecting Feedback

| Option | Description | Selected |
|--------|-------------|----------|
| Show 'Connecting…' toast on first attempt | Immediate feedback so user knows something is happening | ✓ |
| Keep silent on first attempt | Match Phase 28 D-06 literally | |
| Use title_label as 'Connecting…' indicator | Status in title area instead of toast | |

**User's choice:** Show 'Connecting…' toast on first attempt
**Notes:** Addresses the "zero UI activity before failure" symptom without disturbing Phase 28's failover toast semantics.

---

## Success Signal

| Option | Description | Selected |
|--------|-------------|----------|
| mpv still running at end of min-wait window | Simple: if alive at 15s, consider it successful | ✓ |
| Parse mpv stdout for 'AO:' audio output line | True audio-playing signal but requires capturing stdout | |
| mpv IPC socket for playback-time property | Most robust but adds complexity | |

**User's choice:** mpv still running at end of min-wait window
**Notes:** Chosen for simplicity — no mpv IPC, no stdout parsing, fits existing GLib.timeout_add pattern.

---

## Scope of 15s Window

| Option | Description | Selected |
|--------|-------------|----------|
| Every attempt | Each YT stream in the queue gets its own 15s window | ✓ |
| First attempt only | Subsequent failovers use faster detection | |

**User's choice:** Every attempt
**Notes:** Predictable, simple; accepted tradeoff of up to N×15s on dead stations with N streams.

---

## Connecting Toast Breadth

| Option | Description | Selected |
|--------|-------------|----------|
| All stream types | Consistent feedback regardless of protocol | ✓ |
| YT-only | Narrowest fix — only address reported symptom | |

**User's choice:** All stream types
**Notes:** GStreamer streams also benefit — the 10s watchdog can feel silent to users.

---

## Cookie Retry Interaction

| Option | Description | Selected |
|--------|-------------|----------|
| Keep as-is, add on top | 2s cookie retry still fires; 15s window applies to whichever mpv is current | ✓ |
| Fold into new watchdog | Unified YT supervision loop | |

**User's choice:** Keep as-is, add on top
**Notes:** Minimal change to existing Phase 19 cookie-retry path; new watchdog layered on top.

---

## Claude's Discretion

- Exact "Connecting…" toast wording and timeout (3–5s)
- Implementation: separate GLib.timeout_add guard vs attempt-start timestamp gate inside `_yt_poll_cb`
- Whether cookie-retry substitution resets the 15s window or keeps original start time
- Whether `play_stream()` (manual picker) also triggers "Connecting…" toast (recommended: yes)

## Deferred Ideas

- Detect specific mpv/yt-dlp failure modes for faster dead-URL detection (future phase)
- Rich connecting-state indicator in title area instead of toast (scope creep)
- Adaptive timeout based on observed yt-dlp resolve time (deferred indefinitely)
