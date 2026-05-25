# Phase 83: At start of playing a SomaFM station, randomly select and play one of its prerolls - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-22
**Phase:** 83-at-start-of-playing-a-station-randomly-select-and-play-one-o
**Areas discussed:** Preroll storage / refresh, Playback transition mechanism, Trigger scope / frequency, Failure handling

---

## Preroll storage / refresh

### Where preroll URLs live

| Option | Description | Selected |
|--------|-------------|----------|
| DB at SomaFM import | Capture preroll[] in soma_import; store at import time; refresh on re-import. Offline-clean. | |
| Live fetch at play time | Hit channels.json on every Player.play(station). Always fresh; needs network. | |
| DB + opportunistic refresh | Store at import, but also refresh in background on first play of a station with no prerolls. | ✓ |

**User's choice:** DB + opportunistic refresh
**Notes:** Hybrid approach — import-time as default, lazy on-demand backfill for pre-Phase-83 SomaFM stations.

### Schema shape

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated station_prerolls table | FK station_id ON DELETE CASCADE; mirrors station_streams pattern (Phase 47/74). | ✓ |
| JSON column on stations | Add preroll_urls TEXT (JSON list). Fewer joins, breaks relational shape. | |
| Reuse station_streams w/ kind flag | Add kind column; widespread SELECT changes across repo.py. | |

**User's choice:** Dedicated station_prerolls table
**Notes:** Pattern reuse from Phase 47/74; clean additive migration.

### Opportunistic refresh trigger

| Option | Description | Selected |
|--------|-------------|----------|
| On-demand: only when needed | Refresh only when user plays a SomaFM station with no prerolls in DB. | ✓ |
| App startup background sweep | Fetch channels.json on every app launch and update all SomaFM stations. | |
| Both: on-demand AND startup | Belt + suspenders. Two code paths. | |

**User's choice:** On-demand: only when needed
**Notes:** Minimal network surface; only one extra fetch path to maintain.

### Migration policy for pre-Phase-83 SomaFM stations

| Option | Description | Selected |
|--------|-------------|----------|
| Additive only — lazy backfill | Migration creates empty table; existing stations get prerolls on first play via on-demand refresh. | ✓ |
| Eager backfill at migration time | Run a channels.json fetch + populate prerolls for all existing SomaFM stations at migration. | |
| Force a SomaFM re-import banner | One-time UI prompt to re-import. | |

**User's choice:** Additive only — lazy backfill
**Notes:** Matches Phase 82's silent / minimal-UI philosophy.

---

## Playback transition mechanism

### Preroll → stream handoff

| Option | Description | Selected |
|--------|-------------|----------|
| playbin3 about-to-finish gapless | Set URI to preroll; on about-to-finish, set next URI to stream. Single pipeline, gapless. | ✓ |
| EOS handler with URI swap | Set URI to preroll; on bus EOS, set_state(NULL) → URI → PLAYING. Two cycles, brief gap. | |
| Queue-as-stream | Prepend preroll URL to _streams_queue. Reuses failover, but wrong semantics. | |

**User's choice:** playbin3 about-to-finish gapless
**Notes:** GStreamer's canonical gapless idiom; no audible gap.

### Now Playing display during preroll

| Option | Description | Selected |
|--------|-------------|----------|
| Show station name; suppress track title | Title bar = station name; ICY-metadata/tag suppressed for the preroll. | ✓ |
| Show "Station ID" label | Title bar shows "Station ID" for the ~5s. | |
| Show whatever metadata the preroll emits | Pass through whatever the m4a contains. | |

**User's choice:** Show station name; suppress track title
**Notes:** Keeps UI stable; no flicker.

### Failover queue ordering relative to preroll

| Option | Description | Selected |
|--------|-------------|----------|
| Preroll doesn't touch the queue | _streams_queue built exactly as today; preroll plays via about-to-finish into queue[0]. | ✓ |
| Replay preroll if first stream fails | If queue[0] errors immediately, replay preroll before queue[1]. | |
| Skip preroll if failover is mid-recovery | Bypass preroll when called from a recovery path. | |

**User's choice:** Preroll doesn't touch the queue
**Notes:** Clean separation; preroll never replays during failover.

### User controls during preroll

| Option | Description | Selected |
|--------|-------------|----------|
| Same as today — pause/stop the pipeline | Treat preroll as normal playback; pause freezes preroll mid-clip. | ✓ |
| Pause/Stop skips straight to the stream | Any user interaction during preroll abandons it. | |
| Disable controls during preroll | Gray out play/pause/stop until preroll finishes. | |

**User's choice:** Same as today — pause/stop the pipeline
**Notes:** No special-case logic; prerolls are ~5s so a skip button is overkill.

---

## Trigger scope / frequency

### Frequency of preroll triggering

| Option | Description | Selected |
|--------|-------------|----------|
| Every Player.play(station) call | Preroll plays on every Player.play(); re-pressing Play re-rolls. | |
| Only when binding a NEW station | Skip preroll when the station is already bound. | |
| Throttled: skip if last preroll < N minutes ago | Global timestamp; suppress within window. | ✓ |

**User's choice:** Throttled: skip preroll if last preroll < N minutes ago
**Notes:** Dampens rapid station-flipping while still feeling radio-like.

### Throttle window

| Option | Description | Selected |
|--------|-------------|----------|
| 10 minutes | Matches typical SomaFM station-ID cadence. | ✓ |
| 30 minutes | Prerolls feel rare; closer to "per-session" behavior. | |
| 5 minutes | More radio-like; some users may find it repetitive. | |

**User's choice:** 10 minutes
**Notes:** Default sweet spot.

### Throttle timestamp storage

| Option | Description | Selected |
|--------|-------------|----------|
| In-memory on Player | self._last_preroll_played_at = None on init; resets on app restart. | ✓ |
| Persisted to DB / state file | Survives restarts; app restart within the window suppresses preroll. | |
| Per-station throttle, not global | Track per-station; column required. More chatty. | |

**User's choice:** In-memory on Player
**Notes:** Fresh launch always feels like "radio coming on."

### Provider scoping

| Option | Description | Selected |
|--------|-------------|----------|
| Generic: any station with prerolls in DB | Player provider-agnostic; future providers Just Work. | |
| SomaFM-only check in Player | Defensive provider gate (station.provider_name == "SomaFM"). | ✓ |
| Configurable per-provider toggle | Add a settings.providers.{name}.enable_prerolls toggle. | |

**User's choice:** SomaFM-only check in Player
**Notes:** Explicit scope per the phase title; future providers can relax the gate.

---

## Failure handling

### Preroll URL fails (404 / network drop / mid-play error)

| Option | Description | Selected |
|--------|-------------|----------|
| Silent skip — jump straight to the stream | Cancel preroll; call _try_next_stream() immediately; log warning. | ✓ |
| Retry preroll once, then skip | Pick a different preroll and try again before falling through. | |
| Treat preroll failure as station failure | Show toast / error UI. | |

**User's choice:** Silent skip — jump straight to the stream
**Notes:** A missing preroll shouldn't ruin the play attempt.

### On-demand preroll refresh fails (offline / SomaFM API down)

| Option | Description | Selected |
|--------|-------------|----------|
| Silent skip; cache empty; move on | Fetch runs in background; on error, log and move on; retry next time. | ✓ |
| Cache an empty marker so we stop retrying | Distinguish "never fetched" from "fetched, 0 prerolls"; add a sentinel column. | |
| Surface the failure | Toast/log visible to the user. | |

**User's choice:** Silent skip; cache empty; move on
**Notes:** User flagged the sentinel approach as also worth doing — captured in CONTEXT.md D-04 as a `prerolls_fetched_at` column to prevent hammering the API for channels that genuinely have no prerolls.

### Race condition: in-flight fetch + user re-presses Play

| Option | Description | Selected |
|--------|-------------|----------|
| Don't block play; let fetch run in background | Player.play does NOT wait for fetch; goes to stream; next play may get preroll. | ✓ |
| Block briefly (e.g. 500ms timeout) | Wait up to 500ms; first play of new stations slowed. | |
| Cancel fetch on Player.play() re-entry | Cancel in-flight fetch; threading complexity. | |

**User's choice:** Don't block play; let fetch run in background
**Notes:** No UI delay; lazy backfill catches up over time.

### Test coverage shape

| Option | Description | Selected |
|--------|-------------|----------|
| Standard set + drift-guard | 7 behavioral tests + source-grep drift-guard pinning preroll-selection literal. | ✓ |
| Standard set; no drift-guard | Skip the source-grep test. | |
| Standard set + integration test | Real-pipeline test for about-to-finish; flaky due to GStreamer mock blind spot. | |

**User's choice:** Standard set + drift-guard
**Notes:** Follows Phase 51/55/61/63/81/82 precedent.

---

## Claude's Discretion

- About-to-finish callback marshaling pattern (queued signal vs direct next-URI set) — researcher/planner picks the cleanest pattern; existing `_try_next_stream_requested` queued signal at player.py:261-263 is the precedent.
- Random selection algorithm — `random.choice` from stdlib is sufficient; no seeding, weighting, or no-repeat memory.
- Preroll source element selection — playbin3 picks souphttpsrc automatically for https; no explicit element selection needed.
- Drift-guard literals — at minimum `"SomaFM"` provider gate + a stable token like `station_prerolls` table name or `_last_preroll_played_at` attribute.

## Deferred Ideas

- "Skip preroll" UX affordance (button or hotkey).
- Per-station throttle (instead of global).
- Persisted last-preroll timestamp (survives restart).
- Weighted / no-repeat random selection.
- "Replay preroll on first-stream failover."
- Toast / UI surface for preroll fetch failures.
- Generic preroll support for non-SomaFM providers (AudioAddict, GBS.FM, etc.).
- Eager backfill at migration time.
- Periodic background refresh of prerolls (e.g. weekly).
- Integration test that exercises about-to-finish end-to-end.
