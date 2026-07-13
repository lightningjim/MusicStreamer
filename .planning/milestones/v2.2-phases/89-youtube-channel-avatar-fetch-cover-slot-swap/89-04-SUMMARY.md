---
phase: 89-youtube-channel-avatar-fetch-cover-slot-swap
plan: 04
subsystem: ui
tags: [now-playing, cover-slot, avatar, circular-crop, qpainter, tier-replay]

# Dependency graph
requires:
  - phase: 89-youtube-channel-avatar-fetch-cover-slot-swap
    provides: "89-01 Station.channel_avatar_path field + paths.channel_avatars_dir()"
provides:
  - "_make_circular_pixmap helper (center-crop to square + antialiased circular clip, no border) in now_playing_panel.py"
  - "_set_avatar_pixmap_from_path render method with _last_avatar_path tracked state (self-healing on null PNG)"
  - "_apply_art_tier elif branch replays circular avatar on resize (between real-cover and station-logo fallback)"
  - "bind_station ICY-disabled avatar swap (thumbnail-first then circular avatar, D-09)"
affects:
  - "89-05 (EditStationDialog persists avatar that this render path displays)"
  - "89b Twitch avatar (reuses the same circular render path + bind-time load)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Separate avatar render path (D-05) — never alters _set_cover_pixmap (Phase 72.3) or _show_station_logo_in_cover_slot"
    - "Mutually-exclusive tracked state: _last_avatar_path vs _last_cover_path; only one set at a time"
    - "Self-healing render: null/corrupt PNG resets _last_avatar_path = None before logo fallback so resize never retries a bad path"

key-files:
  created: []
  modified:
    - musicstreamer/ui_qt/now_playing_panel.py
    - tests/test_now_playing_panel.py

key-decisions:
  - "Circular avatar is a distinct render path; Phase 72.3 square-cover render and station-thumbnail fallback are untouched (D-05)"
  - "On QPixmap.isNull() fallback, _last_avatar_path is cleared to None BEFORE _show_station_logo_in_cover_slot() so _apply_art_tier does not retry the corrupt path on resize (plan-checker revision)"
  - "bind_station shows the station thumbnail first, then swaps to the circular avatar only when icy_disabled AND channel_avatar_path is set (D-08/D-09)"

patterns-established:
  - "Tier-replay participation: any new cover-slot render path adds its own tracked-state elif in _apply_art_tier so it re-renders at the new tier on resize"

requirements-completed: [ART-AVATAR-06, ART-AVATAR-08]

# Metrics
duration: ~14min
completed: 2026-06-16
---

# Phase 89 Plan 04: Circular-avatar render path in now_playing_panel

**Circular-cropped channel avatar shown in the cover slot for ICY-disabled YT stations, with resize tier-replay, thumbnail-first bind, and self-healing fallback — Phase 72.3 cover render untouched (D-05).**

## Performance

- **Duration:** ~14 min (interrupted by an incidental Ctrl+C after task commits landed; closed out by orchestrator — all task commits present, final helper-rename + SUMMARY committed on resume)
- **Completed:** 2026-06-16
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added module-level `_make_circular_pixmap(source, size)` — center-crops the source to a square then clips to a circle with `QPainter` antialiasing, no border/ring (D-06)
- Added `_set_avatar_pixmap_from_path(rel_path)` render method with its own `_last_avatar_path` tracked state, distinct from `_set_cover_pixmap` (D-05)
- Added an `elif self._last_avatar_path is not None:` branch in `_apply_art_tier` BETWEEN the real-cover branch (`_last_cover_path`) and the station-logo fallback, so the circular avatar re-renders at the new tier on panel resize
- Wired `bind_station`: shows the station thumbnail first, resets `_last_avatar_path = None` (stale-station guard), then loads the circular avatar only when `icy_disabled` AND `channel_avatar_path` is set (D-08/D-09)
- Self-heal: on `QPixmap.isNull()` the method clears `_last_avatar_path = None` before falling back to `_show_station_logo_in_cover_slot()`, so a subsequent resize takes the clean thumbnail branch instead of retrying the corrupt PNG (plan-checker revision requirement)
- Cached-PNG load asserts `elapsed < 1.0` (ART-AVATAR-08 automated timing test)
- 9 new avatar tests; all 156 tests in `test_now_playing_panel.py` pass

## Task Commits

1. **Task 1: Circular-avatar render path** — `9f221b2d` (test RED) → `6ddd1f39` (feat GREEN)
2. **Task 2: bind-time load + _apply_art_tier replay** — `69374bde` (test RED) → `c72ecb22` (feat GREEN)
3. **Test helper rename (resume close-out)** — committed on resume: renamed local `_icy_disabled_station` → `_icy_disabled_yt_station` to avoid colliding with a pre-existing helper of the same name

## Files Created/Modified

- `musicstreamer/ui_qt/now_playing_panel.py` — `_make_circular_pixmap`, `_set_avatar_pixmap_from_path`, `_last_avatar_path` state, `_apply_art_tier` elif branch, `bind_station` avatar swap
- `tests/test_now_playing_panel.py` — 9 avatar tests (render, null-PNG self-heal, bind swap, stale-station reset, tier replay, <1s load)

## Decisions Made

- The circular avatar render path is fully separate from the square-cover render — `_set_cover_pixmap` (Phase 72.3) and `_show_station_logo_in_cover_slot` bodies are unchanged (D-05).
- `_last_avatar_path` and `_last_cover_path` are mutually exclusive; bind/fallback paths keep exactly one set.

## Deviations from Plan

**1. Test helper renamed to avoid a name collision.** The plan's avatar tests introduced a `_icy_disabled_station` helper, but a helper of that exact name already existed in `test_now_playing_panel.py` (~L494). Renamed the new one to `_icy_disabled_yt_station` to prevent shadowing the pre-existing helper. No production impact; all 156 module tests pass.

**Total deviations:** 1 (test-only helper rename). No scope change.

## Issues Encountered

Execution was interrupted by an incidental Ctrl+C after all four task commits (RED/GREEN ×2) had landed and only the test-helper rename was uncommitted. On resume the orchestrator verified the committed implementation (self-heal, new methods, tier-replay all present), ran the avatar tests (9 passed) and the full module (156 passed), committed the rename, and wrote this SUMMARY.

## Threat Surface Scan

No new network endpoints or trust boundaries. The render path reads a local cached PNG via `QPixmap` (path resolved under `paths.data_dir()`), validates with `isNull()`, and never raises from a Qt slot (WR-04). T-89-10 (corrupt-PNG resize retry) mitigated by the self-heal reset. T-89-13 (off-thread widget access) not applicable — bind-time load is synchronous on the Qt main thread.

## User Setup Required

None.

## Next Phase Readiness

- Render path and bind-time swap are live; ART-AVATAR-06/08 satisfied
- Plan 89-05 can wire `EditStationDialog` auto-fetch/refresh to persist avatars that this path renders

---
*Phase: 89-youtube-channel-avatar-fetch-cover-slot-swap*
*Completed: 2026-06-16*
