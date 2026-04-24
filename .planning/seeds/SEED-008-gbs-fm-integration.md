---
id: SEED-008
status: dormant
planted: 2026-04-24
planted_during: v2.0 OS-Agnostic Revamp (Phase 43 just completed, Phase 44 next)
trigger_when: After v2.0 OS-agnostic revamp ships
scope: Large
---

# SEED-008: Integrate GBS.FM into the player

## Why This Matters

**Personal listening value.** Kyle uses GBS.FM and wants to interact with it from
inside MusicStreamer instead of bouncing out to a browser. The must-have
interactions are:

- **Voting/rating** the currently-playing track via the GBS.FM API
- **Searching and submitting** songs into the station's playlist

Those two alone are what justifies the work. Everything else on the platform
(per-song comments, mirrored Discord/IRC live chat, song upload) is
"would be nice" and can be scoped out without killing the milestone's value.

## When to Surface

**Trigger:** After v2.0 OS-agnostic revamp ships.

This seed should be presented during `/gsd-new-milestone` when the next
milestone is being planned after v2.0 closes. Reason: v2.0 is a heavy
Qt/PySide6 port + Windows packaging effort — layering a large
API-integration milestone on top of it would blow the bug-fix→revamp cadence
and mix UI-framework churn with new feature work.

Matching conditions:
- v2.0 milestone status changes to shipped
- A new post-v2.0 milestone is being scoped (v2.1 or v3.0)
- Any milestone framed around "station-specific integrations" or
  "interactive station features"

## Scope Estimate

**Large — full milestone.** The API surface is broad:

- GBS.FM voting/ratings API (core)
- Search + submit-to-playlist API (core)
- Per-song comments (nice-to-have)
- Live chat, mirrored between Discord and IRC (nice-to-have, highest complexity)
- Song upload (nice-to-have)

A realistic milestone would ship the two core flows as v1 and park the rest as
follow-on phases or their own backlog seeds. Expect this to span multiple
phases: auth/account setup, API client, now-playing vote UI, search/submit
dialog, and a separate phase each for comments / chat / upload if they make
the cut.

## Breadcrumbs

No existing GBS.FM references in the codebase (grep -ri 'gbs.fm|gbsfm' — 0 hits
on 2026-04-24). Closest analogs already in-tree:

- `musicstreamer/yt_import.py` — pattern for pulling station/track metadata from
  a third-party API and wiring it to the station list
- `musicstreamer/` Twitch OAuth flow (Phases 31–32) and YouTube cookies flow
  (Phases 22–23, 40) — templates for "authenticated third-party account"
  plumbing, especially the AccountsDialog consolidation work in Phase 40
- Phase 40 `AccountsDialog` (Qt) — where GBS.FM credentials would almost
  certainly live
- AudioAddict import (Phase 15, 17) — template for "search external catalog,
  bring results into the player" UX
- Now-playing panel / ICY title handling (Phases 3, 10, 37) — where a
  "vote on current track" control would attach

Related backlog / project memory:

- `project_audioaddict_integration.md` in auto-memory — same shape of idea
  (external API → station list), scoped for a future milestone
- Phase 999.6 (just planted) — AccountsDialog consolidation argues for GBS.FM
  credentials landing in Accounts, not a separate menu

## Notes

- Kyle explicitly flagged that this should be "itself a milestone" when
  capturing the idea — don't try to squeeze it into a polish milestone.
- Chat mirroring (Discord ↔ IRC) is the single highest-risk subfeature; if
  scope has to shrink, drop chat first.
- Revisit whether Node.js runtime requirement from Phase 35-06 (added for
  yt-dlp EJS solver) has any bearing on GBS.FM client choice before
  committing to an implementation language/library.
- **Single-user scope:** MusicStreamer is Kyle-only (confirmed 2026-04-24).
  Assume one GBS.FM account, one credential set. Skip multi-profile UX,
  account switching, and anti-abuse/moderation UI aimed at third parties.
  See memory: `project_single_user_scope.md`.
