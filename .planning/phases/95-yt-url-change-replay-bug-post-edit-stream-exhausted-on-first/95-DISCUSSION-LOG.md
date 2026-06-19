# Phase 95: YT URL-change replay bug - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-18
**Phase:** 95-yt-url-change-replay-bug-post-edit-stream-exhausted-on-first
**Areas discussed:** Currently-playing edit behavior

---

## Currently-playing edit behavior

### Q1 — What happens to playback when you edit/save the URL of the station currently playing?

| Option | Description | Selected |
|--------|-------------|----------|
| Restart on new URL now | Immediately stop the old stream and re-resolve/play the new URL; no second play needed. Most direct fix. | ✓ |
| Keep old until next play | Don't interrupt audio; just invalidate stale state so the next play/failover uses the new URL. | |
| Stop on save | Stop playback on save; press play to start the new URL. | |

**User's choice:** Restart on new URL now
**Notes:** Directly eliminates the "first play exhausts, second play works" asymmetry — user hears the new stream right after saving.

### Q2 — Should restart fire on every save, or only when the URL changed?

| Option | Description | Selected |
|--------|-------------|----------|
| Only when URL changed | Restart only if the playing stream's URL differs; label/quality/codec-only edits leave audio untouched. | ✓ |
| On any save | Restart whenever the playing station is saved, regardless of what changed. | |

**User's choice:** Only when URL changed
**Notes:** Avoids needless interruption for metadata-only edits (rename, quality tweak).

---

## Claude's Discretion

- Multi-stream / failover granularity (D-04): restart only when the
  *currently-playing* stream's URL changed; edits to other streams in the same
  station just invalidate the queue for future failover.
- Edit-while-not-playing (D-05): next `play()` must rebuild from fresh DB state.
- Exact invalidation mechanism, URL normalization, and wiring point left to
  research/planning.

## Deferred Ideas

- None new. Two keyword-matched todos reviewed and not folded (PLS codec/bitrate
  URL fallback; docker daemon probe) — both unrelated to this bug.
