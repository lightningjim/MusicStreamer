---
phase: 70
plan: "08"
subsystem: ui-dialog
tags: [edit-dialog, table-column, read-only, tdd-green, audio-quality]
dependency_graph:
  requires: [70-01, 70-02]
  provides: [_COL_AUDIO_QUALITY, EditStationDialog.audio-quality-column]
  affects: [musicstreamer/ui_qt/edit_station_dialog.py]
tech_stack:
  added: []
  patterns: [classify_tier-TIER_LABEL_PROSE-lookup, read-only-QTableWidgetItem-setFlags]
key_files:
  modified:
    - musicstreamer/ui_qt/edit_station_dialog.py
decisions:
  - "_COL_AUDIO_QUALITY = 5 appended after _COL_POSITION = 4 — keeps all existing indices stable, matches plan spec"
  - "sample_rate_hz + bit_depth passed as kwargs to _add_stream_row from _populate — mirrors existing positional args pattern, backward-compatible with new-row path (defaults 0)"
  - "read-only enforced via setFlags(flags & ~Qt.ItemIsEditable) not via a delegate — plain-text QTableWidgetItem requires no custom delegate; delegate-free approach is simpler and sufficient"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-12"
  tasks_completed: 2
  files_changed: 1
---

# Phase 70 Plan 08: EditStationDialog Audio Quality Column Summary

## One-liner

Added read-only `_COL_AUDIO_QUALITY = 5` column to EditStationDialog streams table rendering TIER_LABEL_PROSE labels ("Hi-Res" / "Lossless" / "") derived from classify_tier per stream.

## What Was Built

Extended `edit_station_dialog.py` to surface the cached per-stream audio tier as a read-only "Audio quality" column (index 5) in the streams table. The column is auto-derived from `sample_rate_hz` + `bit_depth` stored on each `StationStream` via `classify_tier` from `hi_res.py`, then rendered as prose via `TIER_LABEL_PROSE`. The column is not user-editable (DS-03 no-manual-override invariant: `setFlags(flags & ~Qt.ItemIsEditable)`).

The UI-SPEC OD-8 contract is fully satisfied:
- Header text: "Audio quality" (Sentence case — disambiguates from existing _COL_QUALITY=1 "Quality" user-authored string)
- Header tooltip: "Auto-detected from playback. Hi-Res ≥ 48 kHz or ≥ 24-bit on a lossless codec."
- Column width: 90 px, QHeaderView.Fixed
- Cell text: TIER_LABEL_PROSE[tier] — "Hi-Res" / "Lossless" / ""
- Cell flags: Qt.ItemIsEditable excluded (read-only)

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add _COL_AUDIO_QUALITY constant + extend streams_table to 6 columns + header + tooltip + 90px Fixed | 18df242 | musicstreamer/ui_qt/edit_station_dialog.py |
| 2 | Populate _COL_AUDIO_QUALITY cell per row via classify_tier + TIER_LABEL_PROSE (read-only) | 18df242 | musicstreamer/ui_qt/edit_station_dialog.py |

Tasks 1 and 2 committed atomically — the constant definition, table setup, and row-population logic are all tightly coupled within the same file and cannot be tested independently at the task level.

## Verification Results

- `pytest tests/test_edit_station_dialog.py -k "audio_quality" -x` — 3/3 passed (GREEN)
  - test_audio_quality_column_present_and_read_only PASSED
  - test_audio_quality_cell_shows_prose_label PASSED
  - test_audio_quality_header_tooltip PASSED
- `pytest tests/test_edit_station_dialog.py -x` — 71/71 passed (no regression)
- Grep gate: `_COL_AUDIO_QUALITY = 5` count == 1
- Grep gate: `_COL_URL = 0`, `_COL_QUALITY = 1`, `_COL_CODEC = 2`, `_COL_BITRATE = 3`, `_COL_POSITION = 4` each == 1 (existing indices unchanged)
- Grep gate: `from musicstreamer.hi_res import` == 1
- T-40-04 baseline: `setTextFormat|setHtml|RichText` count == 2 (unchanged — no new QLabel.setTextFormat or RichText calls introduced)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — the column renders live data from the streams returned by `repo.list_streams`. When `sample_rate_hz` and `bit_depth` are 0 (not yet detected via GStreamer caps), `classify_tier("FLAC", 0, 0)` returns "lossless" per D-03 fallback; for lossy codecs at 0/0 it returns "". No placeholder text.

## Threat Flags

None — the implementation uses a closed-enum TIER_LABEL_PROSE lookup (3 keys, no user input path), and all cells are rendered as plain-text QTableWidgetItem with no markup interpretation. T-70-23 (Tampering/cell text) and T-70-24 (Tampering/editability) mitigations are in place as specified in the plan's threat model.

## Self-Check: PASSED

- `musicstreamer/ui_qt/edit_station_dialog.py` — modified and committed (18df242)
- Commit 18df242 exists: confirmed via `git log`
- 3/3 Phase 70 audio quality tests GREEN
- 71/71 total dialog tests GREEN
- T-40-04 baseline unchanged
