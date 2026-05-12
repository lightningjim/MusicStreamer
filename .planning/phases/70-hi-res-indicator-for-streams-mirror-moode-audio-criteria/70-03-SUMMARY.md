---
phase: 70-hi-res-indicator-for-streams-mirror-moode-audio-criteria
plan: "03"
subsystem: stream-ordering
tags: [stream-ordering, sort-key, tiebreak, hi-res, flac, python]

requires:
  - phase: 70-02
    provides: StationStream.sample_rate_hz / bit_depth dataclass fields

provides:
  - order_streams sort key extended with -(sample_rate_hz or 0) and -(bit_depth or 0) tiebreak terms
  - FLAC-96/24 outranks FLAC-44/16 within same codec rank (HRES-01 / S-01)
  - S-02 cross-codec promotion lock preserved: codec_rank still primary after quality_rank

affects: [stream-failover, hi-res-indicator-ui, caps-detection]

tech-stack:
  added: []
  patterns:
    - "Descending-integer tiebreak: negate field with 'or 0' guard for None-safety and 0-last behavior"
    - "Sort key ordering: quality_rank > codec_rank > bitrate_kbps > sample_rate_hz > bit_depth > position"

key-files:
  created: []
  modified:
    - musicstreamer/stream_ordering.py

key-decisions:
  - "sample_rate_hz tiebreak precedes bit_depth tiebreak — matches schema column order and S-01 final key spec"
  - "unknown bitrate branch (bitrate_kbps <= 0) not extended — rate/depth irrelevant for streams with no known bitrate"
  - "S-02 enforced by sort key structure: codec_rank at position 2 prevents any hi-res codec from leaping a lossless codec boundary"

patterns-established:
  - "Rate/depth tiebreak pattern: -(s.sample_rate_hz or 0), -(s.bit_depth or 0) — None-safe, 0-last, pure"

requirements-completed: [HRES-01]

duration: 8min
completed: 2026-05-12
---

# Phase 70 Plan 03: Extend order_streams Sort Key with Hi-Res Rate/Depth Tiebreak Summary

**order_streams sort key extended with -(sample_rate_hz or 0) / -(bit_depth or 0) tiebreak so FLAC-96/24 sorts above FLAC-44/16 within same codec rank (S-01), while lossless-over-lossy invariant (S-02) and GBS sentinel-bitrate regression remain intact.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-12T15:00:00Z
- **Completed:** 2026-05-12T15:08:11Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Extended `order_streams` known-stream sort key with two new tiebreak terms between `-(bitrate_kbps or 0)` and `position`
- `test_hires_flac_outranks_cd_flac` now passes for the correct reason (rate/depth tiebreak, not position accident)
- `test_gbs_flac_ordering` regression preserved: GBS fixtures use `sample_rate_hz=0, bit_depth=0` so `-0` tiebreak produces no change
- All 34 tests in `test_stream_ordering.py` pass; full Wave 1 quick-suite (130 tests) passes

## Task Commits

1. **Task 1: Extend order_streams sort key** - `10ee416` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `musicstreamer/stream_ordering.py` - Two new tiebreak terms inserted in known_sorted lambda; module and function docstrings updated to document S-01 extension

## Decisions Made

- `sample_rate_hz` before `bit_depth` — matches schema column order and CONTEXT S-01 final key specification
- `unknown` branch (bitrate_kbps <= 0) intentionally not extended — streams without a known bitrate sort by position only; rate/depth information there is not actionable
- No new helper functions or constants; single sort-key extension, consistent with existing descending-integer idiom

## Deviations from Plan

None - plan executed exactly as written.

Note: `test_hires_flac_outranks_cd_flac` was already passing before this change (by accident — the test fixture used position=1 for the 96kHz stream, so the position tiebreak produced the correct answer). The fix makes it pass for the right reason (rate/depth tiebreak). This was observed and documented; no deviation rule applies.

## Issues Encountered

None.

## Known Stubs

None — `order_streams` is a pure function with no UI data paths.

## Threat Flags

None — the change is confined to a pure sort function with no network, auth, file, or DB surface.

## Self-Check

Files:
- `musicstreamer/stream_ordering.py`: FOUND
- `-(s.sample_rate_hz or 0)` in non-comment lines (count=1): PASS
- `-(s.bit_depth or 0)` in non-comment lines (count=1): PASS

Commits:
- `10ee416` feat(70-03): FOUND

Tests: 34/34 in test_stream_ordering.py, 130/130 in Wave 1 quick-suite — all GREEN.

## Self-Check: PASSED

## Next Phase Readiness

- Wave 2 GREEN complete: `order_streams` now prefers hi-res streams within same codec rank
- Wave 3 (UI indicator) can rely on `classify_tier` (70-01) and `order_streams` (70-03) both being in place
- No blockers

---
*Phase: 70-hi-res-indicator-for-streams-mirror-moode-audio-criteria*
*Completed: 2026-05-12*
