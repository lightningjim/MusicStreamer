---
phase: 70-hi-res-indicator-for-streams-mirror-moode-audio-criteria
fixed_at: 2026-05-12T00:00:00Z
review_path: .planning/phases/70-hi-res-indicator-for-streams-mirror-moode-audio-criteria/70-REVIEW.md
iteration: 1
fix_scope: critical_warning
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 70: Code Review Fix Report

**Fixed at:** 2026-05-12
**Source review:** `.planning/phases/70-hi-res-indicator-for-streams-mirror-moode-audio-criteria/70-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 6
- Fixed: 6
- Skipped: 0

## Fixed Issues

### CR-01: `classify_tier` misclassifies FLAC at exactly 48 000 Hz as "lossless"

**Files modified:** `musicstreamer/hi_res.py`, `tests/test_hi_res.py`
**Commit:** `49eae47`
**Applied fix:** Changed `rate > _HIRES_RATE_THRESHOLD_HZ` to `rate >= _HIRES_RATE_THRESHOLD_HZ` in `classify_tier`. Also added the boundary test case `("FLAC", 48000, 16, "hires")` to `test_classify_tier_truth_table` (resolves IN-02 simultaneously). Updated the adjacent comment on the `("FLAC", 48000, 24, "hires")` case to reflect the corrected `>=` semantics.

---

### CR-02: `EditStationDialog._on_save` hardcodes `label=""` and `stream_type=""`, and drops `sample_rate_hz`/`bit_depth`

**Files modified:** `musicstreamer/ui_qt/edit_station_dialog.py`
**Commit:** `bec9bd0`
**Applied fix:** Built an `existing_streams` dict from `repo.list_streams(station.id)` before the stream-row loop. For each existing stream (identified by `stream_id`), the preserved `label`, `stream_type`, `sample_rate_hz`, and `bit_depth` values are read from the dict and passed through to `repo.update_stream` via the new keyword arguments.

---

### CR-03: `_clear_all_filters` resets proxy predicates without unchecking `_live_chip`/`_hi_res_chip`

**Files modified:** `musicstreamer/ui_qt/station_list_panel.py`
**Commit:** `b645a85`
**Applied fix:** Added conditional `setChecked(False)` + `_set_chip_state(..., False)` blocks for `_live_chip` and `_hi_res_chip` immediately before the `self._proxy.clear_all()` call, mirroring the existing provider/tag chip reset loop.

---

### WR-01: `_HIRES_BIT_DEPTH_THRESHOLD = 16` with `depth > 16` accepts non-standard depths 17-23

**Files modified:** `musicstreamer/hi_res.py`
**Commit:** `9ffc87f`
**Applied fix:** Changed `_HIRES_BIT_DEPTH_THRESHOLD` from `16` to `23` so the existing `depth > _HIRES_BIT_DEPTH_THRESHOLD` comparison becomes equivalent to `depth >= 24`, which matches D-02's documented threshold. Updated the comment to explain the threshold value.

---

### WR-02: Dead predicate in `_refresh_quality_badge`

**Files modified:** `musicstreamer/ui_qt/now_playing_panel.py`
**Commit:** `c75183a`
**Applied fix:** Replaced `elif self._streams:` with a plain `else:` branch. The old condition was always true when reached (the enclosing `if self._streams:` guaranteed non-emptiness), so the guard provided no real protection and was misleading.

---

### WR-03: Integer-index access on `sqlite3.Row` in `_on_audio_caps_detected`

**Files modified:** `musicstreamer/ui_qt/main_window.py`
**Commit:** `651b379`
**Applied fix:** Changed `int(row[0])` to `int(row["station_id"])` to use named column access consistent with the rest of the codebase. This removes fragility against future column-order changes in the `SELECT` statement.

---

_Fixed: 2026-05-12_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
