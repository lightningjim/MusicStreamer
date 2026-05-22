# Phase 82: User-selected stream provider is honored on next Play - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-21
**Phase:** 82-twitch-only-station-still-tries-to-play-youtube-stream-first
**Areas discussed:** Persistence scope, Entry points, Failover behavior, Dropdown UX

---

## User-supplied repro context

User invoked discuss-phase with the following hint:

> "I can tell you this happened while the main Lofi Girl Yt channel was down so I was getting the 'expired YT link' every time even selecting the Twitch dropdown then clicking play."

This anchored the gray-area analysis to a real-world scenario: a 2-stream station (YT + Twitch), the higher-quality stream is offline, the user picks the secondary stream from the dropdown, and the next press of Play silently overrides the pick.

---

## Persistence scope

| Option | Description | Selected |
|--------|-------------|----------|
| Per-station sticky (DB) | Save selected stream_id on the stations row. Next time the user opens this station, it remembers. Survives app restarts. Adds a column + small migration. | ✓ |
| Current-binding only | Remembered while this station is the bound Now-Playing. Forgets on station switch or app restart. No DB change. | |
| Session-only | Remembered for the lifetime of the app process. No DB change. Lightest fix. | |

**User's choice:** Per-station sticky (DB) — Recommended option.
**Notes:** User wants the selection to survive app restarts because the Lofi Girl scenario will recur whenever the main YT channel is down. A session-only fix would not solve the real problem.

---

## Entry points to fix

| Option | Description | Selected |
|--------|-------------|----------|
| All `player.play(station)` callsites | Fix at the Player layer: if station has preferred_stream_id, route to that stream first. Covers play button, station-list re-click, sibling/similar activation, media keys. | ✓ |
| Play button + station re-activation only | Narrower: fix `_on_play_pause_clicked` and `_on_station_activated` explicitly. Leaves sibling/similar/media-key paths on the old behavior. | |
| Play button only | Minimum diff: only `_on_play_pause_clicked`. Station-list re-click still reverts to YT-first. | |

**User's choice:** All `player.play(station)` callsites — Recommended option.
**Notes:** Player-layer fix is one change covering every entry point. Avoids scattering equivalent logic across `_on_play_pause_clicked`, `_on_station_activated`, `_on_sibling_activated`, `_on_similar_activated`, and the media-keys handlers.

---

## Failover behavior when the picked stream fails

| Option | Description | Selected |
|--------|-------------|----------|
| Fall back through the rest | If picked stream fails, advance through `order_streams`'s ordering as today. Preferred-first, not preferred-only. | ✓ |
| Stop and toast the error | Honor pick strictly. Surface "Selected stream failed" toast and stop. | |
| Toast + offer retry-with-default | Show "Selected stream failed — retry with default order?" toast button. | |

**User's choice:** Fall back through the rest — Recommended option.
**Notes:** Better to have *something* play if Twitch also fails (e.g., network outage). User can always manually re-pick.

---

## Dropdown UX feedback

| Option | Description | Selected |
|--------|-------------|----------|
| Silent — no extra UI | Just remember the selection and play accordingly. Dropdown current-text already shows the selection. | ✓ |
| Pinned icon on the combo | Small pin/lock glyph next to the dropdown when a non-default stream is the active preference. Tooltip explains. | |
| Pinned icon + 'Use default' menu action | Pin icon plus an explicit reset affordance in the hamburger menu or right-click on the combo. | |

**User's choice:** Silent — no extra UI — Recommended option.
**Notes:** Minimum visual noise. Persistence-by-design is invisible; the user already sees the current selection in the combo text.

---

## Final gate

| Option | Description | Selected |
|--------|-------------|----------|
| I'm ready — write context | Lock in the four decisions and chain into plan-phase. | ✓ |
| Explore more gray areas | More questions about stream-id stability, reset-to-default affordance, dual-failure UX. | |

**User's choice:** I'm ready — write context.
**Notes:** Stream-id stability across SomaFM/AA/GBS.FM re-imports deferred to gsd-phase-researcher (will surface in RESEARCH.md). Reset-to-default affordance deferred (D-07 / Deferred Ideas). Dual-failure UX covered by D-05's "fall back through the rest" semantics.

---

## Claude's Discretion

- **Test fixture scope.** Recommend a behavioral test exercising the full repro path (pick secondary stream → re-call `Player.play(station)` → assert head-of-queue), plus a failover regression test (picked stream fails → queue advances through remaining `order_streams` order), plus a source-grep drift-guard pinning the `preferred_stream_id` access in `Player.play()` per the Phase 51/55/61/63/81 precedent.
- **Stream-id stability across re-imports.** Deferred to gsd-phase-researcher. If SomaFM/AA/GBS.FM imports rebuild stream ids per re-import, the `ON DELETE SET NULL` FK silently clears stale picks (acceptable behavior; user re-picks once).
- **Column naming.** Working name `preferred_stream_id`; researcher/planner may pick a clearer alternative (`last_picked_stream_id`, `user_preferred_stream_id`) as long as semantics match D-01.

## Deferred Ideas

- "Stop and toast" mode (alternative to D-05) — defer until telemetry shows D-05 is wrong in practice.
- "Retry with default order" toast button — defer.
- Pinned-stream UX cue (icon next to dropdown) — explicitly rejected in D-07.
- "Reset to default stream order" hamburger / right-click action — defer (user can manually re-pick).
- Cross-device sync of preferred-stream picks — out of scope; no cloud surface.
- Per-quality fallback policy (e.g., "prefer highest-quality of codec X") — different mental model from per-stream-id pick.
- Bulk "clear all preferred-stream picks" admin action — defer.
