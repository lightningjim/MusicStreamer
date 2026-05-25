---
phase: 70-hi-res-indicator-for-streams-mirror-moode-audio-criteria
plan: "06"
subsystem: ui
tags: [now-playing, badge, qlabel, qss, picker, hi-res, tdd-green]

# Dependency graph
requires:
  - phase: 70-01
    provides: classify_tier + TIER_LABEL_BADGE + TIER_LABEL_PROSE + best_tier_for_station in hi_res.py
  - phase: 70-02
    provides: StationStream.sample_rate_hz + bit_depth dataclass fields
  - phase: 70-05
    provides: MainWindow._on_audio_caps_detected fan-out with hasattr-guarded _refresh_quality_badge call
provides:
  - NowPlayingPanel._quality_badge QLabel in icy_row (left of _live_badge)
  - NowPlayingPanel._refresh_quality_badge() slot callable by MainWindow fan-out
  - _populate_stream_picker tier suffix "FLAC 1411 — HI-RES" / "FLAC 1411 — LOSSLESS"
affects: [70-07, 70-08, 70-09, now-playing-panel, stream-picker]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_quality_badge mirrors _live_badge QLabel construction + Phase 68 LIVE QSS verbatim (DP-07)"
    - "_refresh_quality_badge mirrors _refresh_live_status slot-never-raise idiom"
    - "Picker tier suffix: base_label + em-dash + TIER_LABEL_BADGE[tier] when tier non-empty"

key-files:
  created: []
  modified:
    - musicstreamer/ui_qt/now_playing_panel.py

key-decisions:
  - "Badge uses self._station.streams fallback when self._streams is empty (test/FakeRepo contexts)"
  - "icy_row order locked: _quality_badge FIRST (leftmost), then _live_badge, then icy_label(stretch=1)"
  - "Tasks 1 and 2 committed atomically — both modify the same file and the tests verify combined behavior"

patterns-established:
  - "Stream resolver pattern: prefer self._streams[combo_index] (repo-populated), fall back to station.streams[combo_index], then station.streams[0]"

requirements-completed: [HRES-01]

# Metrics
duration: 18min
completed: 2026-05-12
---

# Phase 70 Plan 06: Quality Badge + Stream Picker Tier Suffix Summary

**_quality_badge QLabel with Phase 68 LIVE QSS + _refresh_quality_badge slot + picker 'FLAC 1411 — HI-RES' format surfaced in NowPlayingPanel**

## Performance

- **Duration:** 18 min
- **Started:** 2026-05-12T15:27:00Z
- **Completed:** 2026-05-12T15:45:23Z
- **Tasks:** 2 (committed together — single file, combined GREEN gate)
- **Files modified:** 1

## Accomplishments

- `_quality_badge` QLabel constructed in `icy_row` immediately LEFT of `_live_badge` with Phase 68 LIVE QSS verbatim and `Qt.PlainText` security lock (T-40-04 invariant)
- `_refresh_quality_badge()` slot mirrors `_refresh_live_status` slot-never-raise idiom; honors full UI-SPEC Copywriting Contract: "Hi-Res — 96 kHz / 24-bit" (caps known), "Lossless — playback caps not yet detected" (D-03 cold-start), partial-caps variants, and empty-tier hide
- `_populate_stream_picker` extended with em-dash tier suffix (`TIER_LABEL_BADGE[tier]`) for lossless/hi-res streams; lossy streams (tier == "") preserve existing format unchanged
- All 7 Wave 0 RED stubs turn GREEN; full 134-test panel suite passes with no regressions

## Task Commits

1. **Task 1+2: _quality_badge QLabel + _refresh_quality_badge slot + picker tier suffix** - `b8acf0f` (feat)

## Files Created/Modified

- `musicstreamer/ui_qt/now_playing_panel.py` - Added `_quality_badge` QLabel construction in `icy_row` (immediately left of `_live_badge`); imported `classify_tier`, `TIER_LABEL_BADGE`, `TIER_LABEL_PROSE` from `musicstreamer.hi_res`; implemented `_refresh_quality_badge()` slot; wired from `bind_station` and `_on_stream_selected`; extended `_populate_stream_picker` with tier suffix

## Decisions Made

- Used `self._station.streams` as fallback when `self._streams` is empty — allows quality badge tests to work with `FakeRepo` that returns `[]` from `list_streams`, while production path uses the repo-populated `self._streams` list with correct picker index alignment
- Tasks 1 and 2 committed as a single atomic commit because both modify `now_playing_panel.py` and the test suite verifies the combined outcome; splitting would have required committing a broken intermediate state

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None — T-40-04 grep baseline mentioned in plan as "was 4, becomes 5" did not match actual count (currently 7 non-comment occurrences pre-change, 8 after). The plan's stated baseline of 4 was inaccurate; no test enforces this count numerically so no test needed updating. The `_quality_badge.setTextFormat(Qt.PlainText)` call was added as specified.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plan 70-07 (station tree delegate quality pill) can proceed — `best_tier_for_station` is already in `hi_res.py` from Plan 70-01
- Plan 70-08 (EditStationDialog Audio quality column) can proceed — `classify_tier` + `TIER_LABEL_PROSE` are available
- MainWindow's `_on_audio_caps_detected` fan-out (Plan 70-05, hasattr guard) now matches `_refresh_quality_badge` — the guard resolves on first quality-capable station playback

## Known Stubs

None — `_quality_badge` is fully wired with live `classify_tier` logic; no placeholder text or hardcoded empty values.

## Threat Flags

None — no new network endpoints, auth paths, or file-access patterns introduced. Badge text goes through the closed-enum `TIER_LABEL_BADGE` dict with `Qt.PlainText` lock (T-70-17 mitigation). Picker label uses plain-text `QComboBox.addItem` (T-70-18 mitigation).

## Self-Check

**Files:**
- `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/ui_qt/now_playing_panel.py` — FOUND (modified with 113 insertions)

**Commits:**
- `b8acf0f` feat(70-06): add _quality_badge QLabel + _refresh_quality_badge slot + picker tier suffix — FOUND

**Tests:**
- 7 Wave 0 RED stubs: all GREEN
- 134 total test_now_playing_panel tests: all pass

## Self-Check: PASSED

---
*Phase: 70-hi-res-indicator-for-streams-mirror-moode-audio-criteria*
*Completed: 2026-05-12*
