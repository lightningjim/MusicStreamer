# Phase 87: GBS.FM Marquee + Themed-Day Detection — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in `87-CONTEXT.md`. This log preserves the discussion shape.

**Date:** 2026-05-25 (Memorial Day "da troops" window)
**Phase:** 87-gbs-fm-marquee-themed-day-detection
**Mode:** discuss (--chain)
**Areas discussed:** Baseline harvest + themed logo lifecycle, Auth/session reuse + marquee endpoint, Marquee parsing + keyword set + banner UI, Polling lifecycle

## Pre-discussion finding (surfaced during context gathering)

Roadmap entry for Phase 87 Success Criterion #4 + REQUIREMENTS.md GBS-MARQ-06 reference a `musicstreamer/gbs_auth.py` module exporting `GBS_WEB_PROFILE_NAME` + `GBS_WEB_STORAGE_PATH` constants tied to a persistent `QWebEngineProfile`. **No such module or profile exists.** Phase 76's actual auth surface is Netscape cookies at `paths.gbs_cookies_path()` loaded via `gbs_api.load_auth_context()`. The mirror-decisions-cite-source memory rule triggered the cross-check by prompting a Phase 76 CONTEXT.md re-read. Surfaced to the user before any gray-area selection.

## Area selection

**Asked:** "Which areas do you want to discuss for Phase 87?" (multiSelect)

**Selected (all four):**

1. Auth/session reuse + marquee endpoint
2. Baseline harvest TODAY (Memorial Day "da troops" window) + themed logo lifecycle
3. Marquee parsing + keyword set + banner UI
4. Polling lifecycle (start/stop/cadence/threading)

## Q1: Baseline-harvest sequencing

**Options:**
- a) Inline in Phase 87 — harvest as the first plan, today (Recommended) ✓
- b) Split: /gsd:spike harvest first, then Phase 87 plans use spike findings
- c) Inline harvest + capture more themed days opportunistically across milestone

**User chose:** (a) — Inline harvest, Plan 87-01 fires today

**Reason (implicit):** Time-sensitivity dominates. Themed days are limited; "da troops" is live now.

## Q2: GBS-THEME-06 "3+ themed / 5+ non-themed" rule interpretation

**Options:**
- a) Pragmatic: ship today; mark rule as aspirational with follow-up todo (Recommended) ✓
- b) Strict: defer phase ship until 3+ themed days observed
- c) Synthetic backfill: hash canonical multiple times + use local cached past-themed copies

**User chose:** (a) — Pragmatic; follow-up todo for hash table growth

## Q3: Themed logo runtime storage + fixture commit location

**Options:**
- a) In-memory QPixmap only + tests/fixtures/gbs_themed_logos/ + tests/fixtures/gbs_marquee/ (Recommended) ✓
- b) Cache to ~/.cache/musicstreamer/gbs-themed/<session-id>.png, cleared on app exit
- c) In-memory + persist last canonical SHA-256 to settings table

**User chose:** (a) — In-memory only; fixtures at standard paths

## Q4: GBS-MARQ-06 reinterpretation (the auth drift)

**Options:**
- a) Rewrite GBS-MARQ-06 to lock paths.gbs_cookies_path() + gbs_api.load_auth_context() (Recommended) ✓
- b) Honor literal: introduce a thin gbs_auth.py wrapping cookie constants
- c) Drop drift-guard entirely; GBS-MARQ-06 becomes informational

**User chose:** (a) — Rewrite the requirement to match Phase 76's actual reuse path

## Q5: Marquee endpoint discovery strategy

**Options:**
- a) Researcher probes gbs.fm to identify marquee source; plan-phase locks URL + parser (Recommended) ✓
- b) Assume HTML scrape of homepage; lock now, confirm selector only
- c) Defensive: try with cookies, fall back to anonymous

**User chose:** (a) — Defer to researcher; Phase 87 already has research_flag=YES

## Q6: Themed-day keyword set design

**Options:**
- a) Curated list in constants.py + "unknown theme observed" fallback (Recommended) ✓
- b) Strict keyword gate: themed logo applies only when hash drift AND keyword in list
- c) Hash drift alone enough; keyword informational only

**User chose:** (a) — Curated list with extensible fallback

## Q7: Banner widget style + dismissal storage

**Options:**
- a) Multi-line wrap at pipes + in-memory dismissal only (Recommended) ✓
- b) Multi-line wrap + dismissal persisted in settings table
- c) Single-line marquee-scroll widget

**User chose:** (a) — Wrap at pipes; in-memory dismissal only

## Q8: Polling threading + lifecycle

**Options:**
- a) QThread worker with QTimer, started on first GBS bind, stopped on app exit; themed detection fires once (Recommended) ✓
- b) QThread worker started on every GBS bind / stopped on every unbind
- c) Main-thread QTimer + QNetworkAccessManager (Qt-native async)

**User chose:** (a) — Worker thread, one-shot themed detection per session

## Q9: Error handling on marquee fetch failures

**Options:**
- a) Quiet: log to buffer_log.py at WARN, continue, no UI surface (Recommended) ✓
- b) Toast on first auth-expired error then quiet
- c) Exponential backoff: 60s → 120s → 240s → ceiling at 600s

**User chose:** (a) — Quiet, structured logging only

## Deferred ideas captured

- Themed accent re-tint (already deferred in REQUIREMENTS.md as GBS-THEME-RETINT)
- Exponential backoff on marquee errors
- Persistent banner dismissal in SQLite
- Per-session re-detection of themed day on unbind→rebind
- "Force refresh" UI affordance
- Auto-grow hash baseline via runtime observation
- WebSocket / SSE marquee push channel

## Todos reviewed (not folded)

- `todos/2026-05-10-pls-codec-bitrate-url-fallback.md` (FIX-PLS) — Matched on generic "parser" keyword; unrelated to GBS marquee scope. Belongs to dedicated FIX-PLS phase later in v2.2.

## Plan-phase obligations carried forward

1. Edit ROADMAP.md Phase 87 Success Criterion #4 (D-08) to drop `GBS_WEB_PROFILE_NAME` / `gbs_auth.py` framing.
2. Rewrite REQUIREMENTS.md GBS-MARQ-06 (D-07) to lock real Phase 76 reuse path.
3. Plan 87-01 must fire FIRST and capture today's live themed-day fixtures before researcher runs.
4. Add follow-up todo `2026-05-25-gbs-theme-hash-baseline-grow.md` at phase verification (D-04).

---

*Session ended cleanly; CONTEXT.md written; --chain auto-advance to /gsd:plan-phase 87 pending.*
