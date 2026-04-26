---
phase: 47-stats-for-nerds-autoeq-import-harvest-seed-005-live-gstreame
reviewed: 2026-04-18T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - musicstreamer/ui_qt/edit_station_dialog.py
  - musicstreamer/player.py
  - musicstreamer/aa_import.py
findings:
  critical: 0
  warning: 1
  info: 3
  total: 4
status: issues_found
---

# Phase 47 Gap-Closure Code Review

**Reviewed:** 2026-04-18
**Depth:** standard
**Files Reviewed:** 3
**Scope:** Diff from base `c8687413` to HEAD, limited to gap-closure commits 47-04 through 47-07.
**Status:** issues_found

## Summary

Reviewed the four gap-closure fixes on top of base commit `c8687413`:

- `1c6e133` (47-04): `_BitrateDelegate.setModelData` persists editor text verbatim.
- `a8e6e0b` (47-05): `_recovery_in_flight` guard coalesces cascading GStreamer bus errors per URL.
- `b725488` (47-06): `_resolve_pls` returns all `File=` entries; `fetch_channels_multi` emits one stream per PLS entry.
- `8196a34` (47-07): ground-truth AA codec map (`hi=MP3, med=AAC, low=AAC`).

The 47-04 delegate fix and 47-05 recovery guard are correct and well-contained. The 47-06 PLS multi-entry change is sound. The 47-07 codec map is ground-truth-correct but produces a subtle behavioral regression when combined with `order_streams`' (codec_rank desc, bitrate_kbps desc) sort — MP3 hi-320 now sorts AFTER AAC med-128 in automatic failover. This is user-visible only when `preferred_quality` is unset or not "hi"; the primary `play()` path with preferred="hi" masks it.

## Warnings

### WR-01: AA paid codec map inverts failover quality order when `preferred_quality` is not "hi"

**File:** `musicstreamer/aa_import.py:110` (interacts with `musicstreamer/stream_ordering.py:39` and `musicstreamer/player.py:169-182`)

**Issue:**
Gap-07 set `_CODEC_MAP = {"hi": "MP3", "med": "AAC", "low": "AAC"}` to match AudioAddict ground truth. `order_streams` sorts by `(-codec_rank, -bitrate_kbps, position)` with ranks `FLAC=3, AAC=2, MP3=1`. With the new mapping, the resulting sort for a paid-AA channel is:

1. `med` (AAC, 128 kbps, pos 21)
2. `med` fallback (AAC, 128 kbps, pos 22)
3. `low` (AAC, 64 kbps, pos 31)
4. `low` fallback (AAC, 64 kbps, pos 32)
5. `hi` (MP3, 320 kbps, pos 11)
6. `hi` fallback (MP3, 320 kbps, pos 12)

Automatic failover therefore prefers 128 kbps AAC over 320 kbps MP3. The `Player.play()` path (`player.py:169-182`) masks this when `preferred_quality == "hi"` by hoisting the preferred stream to queue head, but any caller that omits `preferred_quality` or passes `"med"`/`"low"` will see inverted quality order. Phase 47's stated goal was "high-quality-first failover," so this is a meaningful behavioral regression introduced by the otherwise-correct codec-map fix.

**Fix:**
Option A (recommended): treat `quality` (hi/med/low) as the primary sort key in `order_streams`, falling back to codec_rank/bitrate only within the same tier. This preserves user intent ("hi means tried first") regardless of codec:
```python
_QUALITY_RANK = {"hi": 3, "med": 2, "low": 1}
known_sorted = sorted(
    known,
    key=lambda s: (
        -_QUALITY_RANK.get((s.quality or "").lower(), 0),
        -codec_rank(s.codec),
        -(s.bitrate_kbps or 0),
        s.position,
    ),
)
```

Option B (minimal): leave `order_streams` alone and ensure every AA caller always passes `preferred_quality="hi"`. Fragile — any future code path that forgets becomes a regression.

Option C: document the intentional trade-off (AAC-128 preferred over MP3-320 for listening quality) in `order_streams` and `47-PATTERNS.md`, and drop the "hi first" framing. Requires product sign-off.

## Info

### IN-01: Dead defensive branch in `fetch_channels` after gap-06

**File:** `musicstreamer/aa_import.py:136`

**Issue:**
```python
urls = _resolve_pls(pls_url)  # gap-06: list, not str
stream_url = urls[0] if urls else pls_url
```
Post-gap-06, `_resolve_pls` is documented and implemented to always return a non-empty list — on any failure it falls back to `[pls_url]`. The `else pls_url` branch is unreachable. Harmless, but misleading to readers.

**Fix:**
```python
stream_url = _resolve_pls(pls_url)[0]
```
Or add an assertion / comment that `_resolve_pls` is contractually non-empty.

### IN-02: `_resolve_pls` decodes response with default encoding

**File:** `musicstreamer/aa_import.py:34`

**Issue:** `body = resp.read().decode()` relies on the default (UTF-8) codec. PLS files are typically ASCII and this is fine in practice, but the Content-Type header is ignored and a latin-1 PLS would raise `UnicodeDecodeError`, which the broad `except Exception` then swallows — the caller silently gets `[pls_url]` back with no diagnostic.

**Fix:** `body = resp.read().decode("utf-8", errors="replace")` — or log the exception at WARNING in the `except` clause (consistent with `_fetch_image_map`'s pattern at line 82-84).

### IN-03: `setModelData` docstring overstates Qt default behavior

**File:** `musicstreamer/ui_qt/edit_station_dialog.py:170-181`

**Issue:**
The docstring claims "the inherited default setModelData path for a QLineEdit with empty text could leave the model's display value unchanged." In reality, `QStyledItemDelegate`'s default implementation writes `editor.text()` via the widget's `USER` property ("text" for QLineEdit), which would persist `""` correctly. The root cause of UAT gap 1 was more likely a committer / focus-order subtlety, not an inherited-default bug. The override is still the right defensive fix, but the rationale in the docstring is misleading and may confuse future maintainers diagnosing related issues.

**Fix:** Tighten the docstring to describe what the override guarantees, without speculating about the default path:
```python
"""Explicitly persist editor.text() (including empty) to EditRole.

Ensures an empty bitrate cell always commits as "" on the item so the
save loop's int(text or "0") coerces it to bitrate_kbps=0 (D-14,
edit_station_dialog.py:730). UAT gap 1 regression guard.
"""
```

---

_Reviewed: 2026-04-18_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
