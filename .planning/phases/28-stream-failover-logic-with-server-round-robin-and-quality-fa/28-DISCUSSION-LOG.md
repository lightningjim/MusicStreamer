# Phase 28: Stream Failover Logic - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-09
**Phase:** 28-stream-failover-logic-with-server-round-robin-and-quality-fa
**Areas discussed:** Failover trigger, Stream selection, User feedback, Manual switching

---

## Failover Trigger

| Option | Description | Selected |
|--------|-------------|----------|
| GStreamer error only | Failover on pipeline ERROR bus message. Simple and reliable. | |
| Error + timeout | Also failover if no audio data arrives within N seconds. Catches silent failures. | ✓ |
| Error + timeout + silence | Also detect prolonged silence mid-stream. Most aggressive. | |

**User's choice:** Error + timeout
**Notes:** None

### Timeout Duration

| Option | Description | Selected |
|--------|-------------|----------|
| 10 seconds | Matches current GStreamer buffer-duration. | ✓ |
| 15 seconds | More forgiving for slow connections. | |
| 5 seconds | Fast failover, may false-trigger on slow startup. | |

**User's choice:** 10 seconds

### Max Retries

| Option | Description | Selected |
|--------|-------------|----------|
| All streams once | Try every stream exactly once. If all fail, stop. | ✓ |
| All streams twice | Cycle through all streams a second time. | |
| 3 attempts total | Cap at 3 regardless of stream count. | |

**User's choice:** All streams once

---

## Stream Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Quality preference first | Use get_preferred_stream_url(). Fall back to position order. | ✓ |
| Position order only | Always play in position order. Ignore quality preference. | |
| Round-robin rotation | Rotate starting stream each play. | |

**User's choice:** Quality preference first

### Fallback Order

| Option | Description | Selected |
|--------|-------------|----------|
| Position order | Try remaining streams in position order. | ✓ |
| Quality descending | Try hi → med → low regardless of position. | |
| You decide | Claude picks best approach. | |

**User's choice:** Position order

---

## User Feedback

| Option | Description | Selected |
|--------|-------------|----------|
| Toast notification | Adw.Toast: "Stream failed — trying next..." Auto-dismisses. | ✓ |
| Silent retry | No visible indication. | |
| Track title update | Show "Switching stream..." in title area temporarily. | |

**User's choice:** Toast notification

---

## Manual Switching

| Option | Description | Selected |
|--------|-------------|----------|
| No manual switching | Keep now-playing clean. Automatic selection only. | |
| Quality dropdown | Small hi/med/low dropdown in now-playing. | |
| Stream picker menu | Menu button listing all streams by label/quality. | ✓ |

**User's choice:** Stream picker menu

### Placement

| Option | Description | Selected |
|--------|-------------|----------|
| Menu button in controls row | New button next to Edit/Star/Pause/Stop. Opens popover. | ✓ |
| Right-click context menu | Right-click on now-playing panel. | |
| You decide | Claude picks placement. | |

**User's choice:** Menu button in controls row

---

## Claude's Discretion

- Icon choice for stream picker button
- Toast message wording and duration
- Timeout implementation mechanism
- Whether to hide picker for single-stream stations

## Deferred Ideas

None
