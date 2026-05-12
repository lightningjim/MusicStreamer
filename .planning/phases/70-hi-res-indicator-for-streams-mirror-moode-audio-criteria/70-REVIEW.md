---
phase: 70-hi-res-indicator-for-streams-mirror-moode-audio-criteria
reviewed: 2026-05-12T00:00:00Z
depth: standard
files_reviewed: 22
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
  - tests/test_hi_res.py
  - tests/test_player_caps.py
  - tests/test_stream_ordering.py
  - tests/test_repo.py
  - tests/test_settings_export.py
  - tests/test_station_filter_proxy.py
  - tests/test_station_list_panel.py
  - tests/test_edit_station_dialog.py
  - tests/test_now_playing_panel.py
  - tests/test_station_star_delegate.py
  - tests/test_main_window_integration.py
findings:
  critical: 3
  warning: 3
  info: 3
  total: 9
status: issues_found
---

# Phase 70: Code Review Report

**Reviewed:** 2026-05-12
**Depth:** standard
**Files Reviewed:** 22
**Status:** issues_found

## Summary

Phase 70 introduces a Hi-Res audio classification layer (`hi_res.py`), caps detection in `player.py`, DB persistence of `sample_rate_hz`/`bit_depth` via `repo.py`, and visual surface updates across four UI files. The pure classification module and SQL layer are clean. The threading contract (QueuedConnection, DB-write-first in `_on_audio_caps_detected`) is correctly implemented. The Phase 47.3 forward-compat idiom is present in `settings_export.py`.

Three blockers were found: a rate-threshold off-by-one in `classify_tier` that misclassifies 48 kHz FLAC streams; the `_on_save` path in `EditStationDialog` hardcodes empty strings for `label` and `stream_type` (data loss on every save cycle) and omits the new `sample_rate_hz`/`bit_depth` kwargs (silently zeros out caps-detected hi-res data on every edit); and `_clear_all_filters` resets the proxy predicates without unchecking the Live/Hi-Res chip widgets, leaving the UI filter-state desynced after Clear All.

---

## Critical Issues

### CR-01: `classify_tier` misclassifies FLAC at exactly 48 000 Hz as "lossless"

**File:** `musicstreamer/hi_res.py:65,154`

**Issue:** `_HIRES_RATE_THRESHOLD_HZ = 48_000` is compared with strict `>` (line 154: `rate > _HIRES_RATE_THRESHOLD_HZ`). D-02 specification reads "rate ≥ 48 000" — mirroring moOde's `hidef` flag which is set on `sample_rate >= 48000`. A FLAC stream captured at exactly 48 000 Hz (standard high-quality radio, e.g. BBC Radio 3 FLAC) returns `"lossless"` instead of `"hires"`. The in-module docstring at line 21 also states `"rate ≥ 48000"`, so the spec, the docstring, and the implementation are in three-way disagreement, with the implementation being the outlier. The test suite does not include the boundary case `("FLAC", 48000, 16, "hires")` so this defect passes CI.

**Fix:**
```python
# hi_res.py — change the operator to >=
if rate >= _HIRES_RATE_THRESHOLD_HZ or depth > _HIRES_BIT_DEPTH_THRESHOLD:
    return "hires"
```
Add the boundary test `("FLAC", 48000, 16, "hires")` to `test_hi_res.py::test_classify_tier_truth_table`.

---

### CR-02: `EditStationDialog._on_save` hardcodes `label=""` and `stream_type=""`, and drops `sample_rate_hz`/`bit_depth`

**File:** `musicstreamer/ui_qt/edit_station_dialog.py:1177`

**Issue:** The `repo.update_stream(...)` call inside `_on_save` passes positional empty strings for the `label` and `stream_type` parameters, and does not pass the `sample_rate_hz` or `bit_depth` keyword arguments:

```python
repo.update_stream(stream_id, url, "", quality, position, "", codec,
                   bitrate_kbps=bitrate_kbps)
```

This causes two distinct data-loss bugs on every save through the editor:

1. **Existing `label` and `stream_type` values are destroyed** — overwritten with `""` regardless of what was stored in the DB. Any stream that had a non-empty label or stream_type (e.g. set programmatically or imported) loses that data silently.

2. **Caps-detected `sample_rate_hz` and `bit_depth` are zeroed** — `update_stream` defaults these to `0` when omitted. So after a user opens the editor and saves, the hi-res badge disappears from the station until the next playback cycle re-detects the caps. Combined with the D-02 fix (CR-01), a 96 kHz / 24-bit stream would briefly show "Lossless" after every save.

The existing tests (`test_empty_bitrate_saves_as_zero`, `test_populated_bitrate_saves_as_int`) verify `bitrate_kbps` only and do not catch this regression.

**Fix:** Read the existing stream from the pre-populated cache before saving, and pass through the preserved fields plus the new kwargs:
```python
existing = {s.id: s for s in repo.list_streams(station.id)}
ex = existing.get(stream_id)
label = ex.label if ex else ""
stream_type = ex.stream_type if ex else ""
sample_rate_hz = ex.sample_rate_hz if ex else 0
bit_depth = ex.bit_depth if ex else 0

repo.update_stream(
    stream_id, url, label, quality, position, stream_type, codec,
    bitrate_kbps=bitrate_kbps,
    sample_rate_hz=sample_rate_hz,
    bit_depth=bit_depth,
)
```

---

### CR-03: `_clear_all_filters` resets proxy predicates without unchecking `_live_chip`/`_hi_res_chip`

**File:** `musicstreamer/ui_qt/station_list_panel.py:650-658`

**Issue:** `_clear_all_filters` calls `self._proxy.clear_all()` which sets `proxy._live_only = False` and `proxy._hi_res_only = False`, but it does not uncheck `self._live_chip` or `self._hi_res_chip`. After Clear All is pressed: the proxy shows all stations correctly, but both chips remain visually checked. The user sees "Live now" and "Hi-Res only" buttons appearing to be active filters when they are not. Additionally, because `setChecked(False)` is not called, the `toggled` signal is not fired, so `_set_chip_state(chip, False)` is never reached and the button's `chipState` style property is not reset — leaving the styled highlight on the chip as well.

There are no tests for the panel-level chip visual state after Clear All (only proxy-level `test_clear_all_clears_hi_res_only` in `test_station_filter_proxy.py`), so this passes CI.

**Fix:** Mirror the provider/tag chip reset loop already present in `_clear_all_filters`:
```python
def _clear_all_filters(self) -> None:
    self._search_box.clear()
    for btn in self._provider_chip_group.buttons():
        btn.setChecked(False)
        self._set_chip_state(btn, False)
    for btn in self._tag_chip_group.buttons():
        btn.setChecked(False)
        self._set_chip_state(btn, False)
    # Add these two blocks — mirrors provider/tag chip reset above:
    if self._live_chip.isChecked():
        self._live_chip.setChecked(False)
        self._set_chip_state(self._live_chip, False)
    if self._hi_res_chip.isChecked():
        self._hi_res_chip.setChecked(False)
        self._set_chip_state(self._hi_res_chip, False)
    self._proxy.clear_all()
    self._sync_tree_expansion()
```

---

## Warnings

### WR-01: `_HIRES_BIT_DEPTH_THRESHOLD = 16` with `depth > 16` accepts non-standard depths 17–23

**File:** `musicstreamer/hi_res.py:66,154`

**Issue:** The D-02 specification states the hi-res criterion is `depth ≥ 24`. The implementation uses `depth > _HIRES_BIT_DEPTH_THRESHOLD` where `_HIRES_BIT_DEPTH_THRESHOLD = 16`. This means bit depths of 17, 18, 19, 20, or 22 (none of which exist in practice, but could arrive via malformed metadata or a future codec) would be classified as `"hires"`. The comment in the constant definition says `"≥ 24"` while the code implements `> 16`. These are equivalent only for the two values that exist in practice (16 and 24), but the logic is fragile and inconsistent with its own documentation.

**Fix:** Use `depth >= 24` directly (with threshold 23, or just hard-code 24 with `depth >= 24`).

---

### WR-02: Dead predicate in `_refresh_quality_badge`

**File:** `musicstreamer/ui_qt/now_playing_panel.py:1556`

**Issue:** The fallback branch inside `_refresh_quality_badge` contains an unreachable `elif` guard:

```python
if self._streams:
    if 0 <= idx < len(self._streams):
        s = self._streams[idx]
    elif self._streams:   # ← always True: outer if guarantees _streams is truthy
        s = self._streams[0]
```

The `elif self._streams:` condition is always true because the enclosing `if self._streams:` guarantees `_streams` is non-empty when this branch is reached. The fallback path (`s = self._streams[0]`) does execute when `idx` is out of range, but only by accident — the condition that gates it provides no actual guard. A future editor could remove the inner `if` block believing the outer `elif` is meaningfully distinct, introducing a silent correctness hole.

**Fix:**
```python
if self._streams:
    if 0 <= idx < len(self._streams):
        s = self._streams[idx]
    else:
        s = self._streams[0]
```

---

### WR-03: Integer-index access on `sqlite3.Row` in `_on_audio_caps_detected`

**File:** `musicstreamer/ui_qt/main_window.py:508`

**Issue:** The caps handler reads the stream row with a positional integer index:

```python
station_id = int(row[0])
```

The rest of the codebase uses named column access (`row["station_id"]`, `row["codec"]`, etc.) against `sqlite3.Row` objects. Using `row[0]` is fragile: if the column order in the `SELECT` statement in `repo.get_stream` changes (e.g., a new column is prepended), this silently reads the wrong value without raising an exception. The value could be any integer from an unrelated column.

**Fix:**
```python
station_id = int(row["station_id"])
```

---

## Info

### IN-01: `classify_tier` docstring says "rate ≥ 48 000" but code implements `> 48 000`

**File:** `musicstreamer/hi_res.py:21,127,139`

**Issue:** The module docstring (line 21: `"rate ≥ 48000 OR depth ≥ 24 → 'hires'"`) and the `classify_tier` function docstring both state `≥ 48000`, but the implementation uses `> 48000`. Resolved by the CR-01 fix; noting separately for the copywriting precision invariant.

**Fix:** Resolved by CR-01 fix. No separate change needed.

---

### IN-02: Missing boundary test `classify_tier("FLAC", 48000, 16)` in `test_hi_res.py`

**File:** `tests/test_hi_res.py` (truth table)

**Issue:** The parametrized truth table in `test_classify_tier_truth_table` does not include `("FLAC", 48000, 16, "hires")`. This is the exact boundary value that would have caught CR-01.

**Fix:** Add to the parametrize list:
```python
# D-02 boundary: 48 kHz exactly qualifies as hi-res
("FLAC", 48000, 16, "hires"),
```

---

### IN-03: Relative path in `test_main_window_integration.py` is fragile

**File:** `tests/test_main_window_integration.py:932`

**Issue:** A source-introspection test reads the player source file using a relative path:

```python
pathlib.Path("musicstreamer/player.py").read_text()
```

This silently fails (raises `FileNotFoundError`) if `pytest` is invoked from any directory other than the project root. All other source-introspection tests in this suite use `inspect.getsource(...)` which is CWD-independent.

**Fix:**
```python
import inspect
import musicstreamer.player as _player_mod
src = inspect.getsource(_player_mod)
```

---

_Reviewed: 2026-05-12_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
