---
phase: 70-hi-res-indicator-for-streams-mirror-moode-audio-criteria
reviewed: 2026-05-12T00:00:00Z
depth: standard
files_reviewed: 21
files_reviewed_list:
  - musicstreamer/hi_res.py
  - musicstreamer/models.py
  - musicstreamer/repo.py
  - musicstreamer/settings_export.py
  - musicstreamer/stream_ordering.py
  - musicstreamer/ui_qt/edit_station_dialog.py
  - musicstreamer/ui_qt/main_window.py
  - musicstreamer/ui_qt/now_playing_panel.py
  - musicstreamer/ui_qt/station_filter_proxy.py
  - musicstreamer/ui_qt/station_list_panel.py
  - musicstreamer/ui_qt/station_star_delegate.py
  - tests/test_edit_station_dialog.py
  - tests/test_hi_res.py
  - tests/test_main_window_integration.py
  - tests/test_now_playing_panel.py
  - tests/test_player_caps.py
  - tests/test_repo.py
  - tests/test_settings_export.py
  - tests/test_station_filter_proxy.py
  - tests/test_station_list_panel.py
  - tests/test_stream_ordering.py
findings:
  critical: 0
  warning: 0
  info: 2
  total: 2
status: issues_found
---

# Phase 70: Code Review Report (Re-review)

**Reviewed:** 2026-05-12
**Depth:** standard
**Files Reviewed:** 21
**Status:** issues_found (info-level only)

## Summary

Re-review of Phase 70 after six prior fixes. All six fixes are confirmed
correctly landed:

1. **CR-01** (`hi_res.py::classify_tier`) — `rate >= _HIRES_RATE_THRESHOLD_HZ`
   and `depth > _HIRES_BIT_DEPTH_THRESHOLD` (i.e., `>= 24`) are correct at
   line 158. `_HIRES_BIT_DEPTH_THRESHOLD = 23` at line 70. Verified.

2. **CR-02** (`edit_station_dialog.py::_on_save`) — `existing_streams` dict
   built at line 1157; `ex.label`, `ex.stream_type`, `ex.sample_rate_hz`,
   `ex.bit_depth` preserved at lines 1184-1187 on `update_stream`. Verified.

3. **CR-03** (`station_list_panel.py::_clear_all_filters`) — both
   `_live_chip` and `_hi_res_chip` unchecked and chip-state reset at lines
   661-666. Verified.

4. **WR-01** (`now_playing_panel.py::_refresh_quality_badge`) — the
   `elif self._streams` branch replaced with `if s is None` plus
   station-streams fallback at lines 1558-1564. Verified.

5. **WR-02** (`main_window.py::_on_audio_caps_detected`) — `row["station_id"]`
   named-key access at line 508. Verified.

6. **WR-03** (`tests/test_hi_res.py`) — boundary case
   `("FLAC", 48000, 16, "hires")` present at line 70. Verified.

No new correctness bugs or security issues were introduced by the fixes. Two
pre-existing info-level items remain: one is a minor cosmetic inaccuracy in
tooltip kHz formatting; the other (IN-02, formerly IN-03 in the prior review)
is the unresolved relative-path test that is CWD-sensitive.

---

## Info

### IN-01: Tooltip kHz display truncates 44.1 kHz to "44 kHz"

**File:** `musicstreamer/ui_qt/now_playing_panel.py:1584,1587`

**Issue:** `rate // 1000` performs integer floor division. For a 44.1 kHz
stream (`sample_rate_hz=44100`), the tooltip reads `"Lossless — 44 kHz /
16-bit"` instead of `"Lossless — 44.1 kHz / 16-bit"`. The same truncation
applies to the rate-only branch at line 1587. For standard hi-res rates
(48 kHz, 96 kHz, 192 kHz) the display is exact. The inaccuracy is therefore
limited to the CD-quality Lossless case when `sample_rate_hz=44100` and caps
are known. No existing test pins the 44.1 kHz tooltip, so this does not
currently cause test failures.

**Fix:**
```python
# Line 1584 — full caps branch:
tooltip = f"{prose} — {rate / 1000:g} kHz / {depth}-bit"
# Line 1587 — rate-only branch:
tooltip = f"{prose} — {rate / 1000:g} kHz"
# The :g format removes trailing zeros: 96000/1000 → "96", 44100/1000 → "44.1"
```

### IN-02: Relative path in test makes it CWD-sensitive

**File:** `tests/test_main_window_integration.py:932`

**Issue:** `pathlib.Path("musicstreamer/player.py").read_text()` uses a bare
relative path. The test passes when pytest is run from the project root (the
common case) but raises `FileNotFoundError` when the working directory differs
— for example, running `cd tests && pytest`, an IDE that sets cwd to the test
file's directory, or a CI runner with a non-standard working directory. This
is the same finding as IN-03 in the prior review; it was explicitly outside
the prior auto-fix scope.

**Fix:**
```python
# Replace line 932 with a path anchored to this file's location:
src = (pathlib.Path(__file__).parent.parent / "musicstreamer" / "player.py").read_text()
```

---

_Reviewed: 2026-05-12_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
