---
phase: 98-add-to-stats-for-nerds-actual-encoding-and-bitrate-detected
plan: 02
subsystem: now_playing_panel
tags: [stats-for-nerds, ui, amber-mismatch, codec-detection, bitrate]
dependency_graph:
  requires: [98-01]
  provides: [_StatLabel, update_detected_format, update_detected_caps, four-format-rows]
  affects: [musicstreamer/ui_qt/now_playing_panel.py, tests/test_now_playing_stats.py]
tech_stack:
  added: []
  patterns: [_MutedLabel-subclass-override, QPalette-amber-theme-safe, QFormLayout-row-addRow]
key_files:
  created:
    - tests/test_now_playing_stats.py
  modified:
    - musicstreamer/ui_qt/now_playing_panel.py
    - tests/test_now_playing_panel.py
decisions:
  - "_mismatch set before super().__init__() in _StatLabel to avoid MRO dispatch before attribute exists"
  - "bind_station reset places format-row resets alongside existing _last_cover_icy reset block"
  - "test_buffer_duration_row_present updated to scan by label text (not hardcoded index) for row-insertion resilience"
metrics:
  duration_seconds: 281
  completed_date: "2026-06-27"
  tasks_completed: 2
  files_modified: 3
---

# Phase 98 Plan 02: Stats-for-Nerds Format Rows — Consumer UI Summary

**One-liner:** `_StatLabel` amber-on-mismatch subclass + four QFormLayout format rows (Encoding, Bitrate, Sample rate, Bit depth) + `update_detected_format` / `update_detected_caps` panel methods implementing D-01/D-02/D-05/D-07.

## What Was Built

### `_StatLabel` Amber Subclass (D-02)

Added `_StatLabel(_MutedLabel)` immediately after `_MutedLabel` in `now_playing_panel.py`. Key design:
- Class attributes `_AMBER_LIGHT = QColor(180, 120, 0)` and `_AMBER_DARK = QColor(255, 180, 60)` for light/dark theme variants
- `set_mismatch(bool)` no-ops on unchanged state; calls `_apply_muted_palette()` on change
- `_apply_muted_palette()` override: picks amber by `QPalette.Window.lightness() < 128` (Pitfall 6 theme-safety); falls back to parent's muted palette when not mismatched
- `changeEvent` inherited from `_MutedLabel` — dispatches to the overridden `_apply_muted_palette` via MRO, keeping amber in sync on theme flip
- `_mismatch` initialized **before** `super().__init__()` (MRO dispatch fix: parent `__init__` calls `_apply_muted_palette` which reads `_mismatch`)

### Four Format Rows in `_build_stats_widget` (D-04)

Inserted before the existing Buffer/Underruns/Buf-duration performance rows:
1. **Encoding** — `_StatLabel("—", wrapper)` stored as `self._encoding_label`
2. **Bitrate** — `_StatLabel("—", wrapper)` stored as `self._bitrate_label`
3. **Sample rate** — `_MutedLabel("—", wrapper)` stored as `self._sample_rate_label` (detected-only, D-05)
4. **Bit depth** — `_MutedLabel("—", wrapper)` stored as `self._bit_depth_label` (detected-only, D-05)

No per-row `setVisible` added — rows inherit visibility from `wrapper.setVisible(False)` (Pitfall 8).

### `bind_station` Reset (Pitfall 7)

Added reset block alongside `_last_cover_icy = None` / `_last_icy_title = ""`:
- All four labels reset to `"—"`
- Both `_StatLabel` rows have `set_mismatch(False)` called

### `update_detected_format(stream_id, detected_codec, detected_bitrate_kbps)` (D-01/D-02/D-07)

- Looks up declared values from `self._streams` by `stream_id` (D-03: no new source of truth)
- Encoding row: shows `"CODEC  (exp: DECLARED)"` when both known; `"—  (exp: DECLARED)"` when detected unknown; `"—"` when both unknown (D-07); mismatch = case-insensitive compare, False when detected unknown
- Bitrate row: 5 kbps tolerance (Finding 5); same em-dash and suffix pattern
- No `repo.update_stream()` call (Finding 6 — transient panel-only values)

### `update_detected_caps(stream_id, rate_hz, bit_depth)` (D-05)

- `_sample_rate_label`: `f"{rate_hz / 1000:g} kHz"` or `"—"`
- `_bit_depth_label`: `f"{bit_depth}-bit"` or `"—"`
- `stream_id` accepted but unused (panel-wide rows)

### Tests — `tests/test_now_playing_stats.py`

10 tests across two categories:

Structural (4):
- `test_four_format_labels_default_em_dash` — D-07 default values
- `test_sample_rate_label_is_muted_not_stat` — D-05 type check
- `test_bit_depth_label_is_muted_not_stat` — D-05 type check
- `test_no_per_row_visible_in_build_stats` — Pitfall 8 source-grep

Behavioral (6):
- `test_encoding_row_shows_detected_and_expected` — D-01
- `test_encoding_mismatch_sets_amber` — D-02
- `test_no_mismatch_flag_when_codec_matches` — D-02
- `test_bitrate_mismatch_tolerance` — Finding 5 (5 kbps tolerance)
- `test_em_dash_when_codec_unknown` — D-07
- `test_no_mismatch_when_both_unknown` — D-07
- `test_update_detected_caps_sample_rate` — D-05 formatting
- `test_update_detected_caps_bit_depth` — D-05 formatting

## Task Commits

| Task | Commit | Files |
|------|--------|-------|
| Task 1: _StatLabel + rows + bind_station reset | 3a6e3c89 | now_playing_panel.py, test_now_playing_panel.py, tests/test_now_playing_stats.py (partial) |
| Task 2: update_detected_format + update_detected_caps | e80ee5ba | now_playing_panel.py |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `_mismatch` attribute not yet set when `super().__init__()` calls `_apply_muted_palette`**
- **Found during:** Task 1 GREEN phase
- **Issue:** `_MutedLabel.__init__` calls `self._apply_muted_palette()`, which via MRO dispatches to `_StatLabel._apply_muted_palette`. That method reads `self._mismatch` but the attribute is only set after `super().__init__()` returns — `AttributeError`.
- **Fix:** Set `self._mismatch = False` before calling `super().__init__()` in `_StatLabel.__init__`.
- **Files modified:** `musicstreamer/ui_qt/now_playing_panel.py`
- **Commit:** 3a6e3c89

**2. [Rule 1 - Bug] `test_buffer_duration_row_present` hardcoded row index 2 broke after 4 rows inserted**
- **Found during:** Task 1 GREEN phase (existing suite regression)
- **Issue:** The Phase 84 test asserted "Buf duration" was at `form.itemAt(2, ...)` — absolute row index. After inserting 4 new rows before the existing rows, "Buf duration" moved to index 6.
- **Fix:** Replaced hardcoded index with a label-text scan loop (robust to future row insertions). Updated `rowCount >= 3` to `>= 7`.
- **Files modified:** `tests/test_now_playing_panel.py`
- **Commit:** 3a6e3c89

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes.

T-98-04 (Injection): `update_detected_format` renders values via `QLabel.setText()` (plain text only, not rich text). The detected codec string arrives via the closed-vocabulary `_normalise_audio_codec` normaliser (Plan 98-01); no arbitrary strings reach the label.

T-98-05 (Amber illegibility): `_AMBER_LIGHT`/`_AMBER_DARK` selection via `QPalette.Window.lightness()` probe; `changeEvent` inherited and dispatches to overridden `_apply_muted_palette`. Theme-flip safety confirmed by MRO design.

## Known Stubs

None. All methods are fully wired. The wiring from `Player.audio_format_detected` signal to `NowPlayingPanel.update_detected_format` is Plan 98-03's responsibility (this plan is the consumer half; Plan 98-03 is the wiring half).

## Self-Check: PASSED

- `tests/test_now_playing_stats.py` exists: FOUND
- `musicstreamer/ui_qt/now_playing_panel.py` modified: FOUND
- `tests/test_now_playing_panel.py` modified: FOUND
- Task 1 commit 3a6e3c89: verified
- Task 2 commit e80ee5ba: verified
- All 178 tests (166 panel + 10 stats + 2 from new file) pass
