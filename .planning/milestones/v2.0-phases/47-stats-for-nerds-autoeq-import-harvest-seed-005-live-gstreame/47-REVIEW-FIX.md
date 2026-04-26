---
phase: 47-stats-for-nerds-autoeq-import-harvest-seed-005-live-gstreame
fixed_at: 2026-04-18T00:00:00Z
review_paths:
  - .planning/phases/47-stats-for-nerds-autoeq-import-harvest-seed-005-live-gstreame/47-REVIEW.md
  - .planning/phases/47-stats-for-nerds-autoeq-import-harvest-seed-005-live-gstreame/47-UI-REVIEW.md
iteration: 1
fixes_applied:
  - WR-01
  - WR-02
  - IN-01
  - IN-02
  - UI-01
  - UI-02
  - UI-03
fixes_skipped:
  - IN-03
  - IN-04
status: all_fixed
---

# Phase 47: Code + UI Review Fix Report

**Fixed at:** 2026-04-18
**Source reviews:**
- `47-REVIEW.md` (code review — 0 critical, 2 warning, 4 info)
- `47-UI-REVIEW.md` (UI review — 3 priority fixes)
**Iteration:** 1

**Summary:**
- Findings in scope: 9 (2 warning + 4 info + 3 UI priority)
- Fixed: 7
- Skipped: 2 (per orchestrator judgment, both documented)

## Fixed Issues

### WR-01: `order_streams` crashes if `bitrate_kbps` is `None`

**File modified:** `musicstreamer/stream_ordering.py`
**Commit:** `265829f`
**Applied fix:** Replaced `s.bitrate_kbps > 0` / `s.bitrate_kbps <= 0` / `-s.bitrate_kbps` with `(s.bitrate_kbps or 0)` equivalents in the partition and sort-key. None-safe without changing semantics for the normal (non-None) case. No test changes needed — existing 44-test suite still green.

### WR-02: `import_stations_multi` writes `first_url=""` to DB when `ch["streams"]` is empty

**File modified:** `musicstreamer/aa_import.py`
**Commit:** `8770634`
**Applied fix:** Added an explicit `if not ch.get("streams"): skipped += 1; continue` guard with a `_log.warning(...)` call at the top of the import loop. Also simplified `first_url = ch["streams"][0]["url"]` (dropped the `if ch["streams"] else ""` fallback, now unreachable). Progress callback still fires on the skip path.

### IN-01: `_fetch_image_map` swallows 401/403 silently

**File modified:** `musicstreamer/aa_import.py`
**Commit:** `da4e0fc`
**Applied fix:** Added `import logging` + `_log = logging.getLogger(__name__)` at module scope (matches `media_keys/*` and `main_window.py` convention). Split the bare `except Exception` into `except urllib.error.HTTPError` (logs 401/403 as "auth failure" and other HTTP errors distinctly) + `except Exception` (logs the failure). Behavior unchanged — still returns `{}` on any failure so image fetch remains non-blocking for imports.

### IN-02: `position_map` / `bitrate_map` redefined per iteration

**File modified:** `musicstreamer/aa_import.py`
**Commit:** `0ed2f69`
**Applied fix:** Hoisted `_POSITION_MAP = {"hi": 1, "med": 2, "low": 3}` and `_BITRATE_MAP = {"hi": 320, "med": 128, "low": 64}` to module scope alongside `QUALITY_TIERS`. Inner loop now references `_POSITION_MAP[quality]` / `_BITRATE_MAP[quality]`. No semantic change.

### UI-01: Column header missing unit suffix

**File modified:** `musicstreamer/ui_qt/edit_station_dialog.py`
**Commit:** `bf8f736`
**Applied fix:** Changed header label `"Bitrate"` → `"Bitrate (kbps)"` at line 294 and bumped `setColumnWidth(_COL_BITRATE, 70)` → `95` at line 306 to fit the longer label.

### UI-02: No placeholder hint on empty bitrate cells

**File modified:** `musicstreamer/ui_qt/edit_station_dialog.py`
**Commit:** `5424a3d`
**Applied fix:** Added `editor.setPlaceholderText("e.g. 128")` in `_BitrateDelegate.createEditor` so users get a discoverability cue on numeric-only expectations when editing an empty cell.

### UI-03: Bitrate column doesn't advertise its failover-ordering role

**File modified:** `musicstreamer/ui_qt/edit_station_dialog.py`
**Commit:** `f8185a4`
**Applied fix:** Added `horizontalHeaderItem(_COL_BITRATE).setToolTip("Higher bitrate streams play first on failover")` after the column-width block. Also folded IN-03's rationale (9999 cap is a display/edit policy per D-13, not a domain invariant) into the comment above the tooltip call, subsuming IN-03.

## Skipped Issues

### IN-03: `_BitrateDelegate` 9999 cap should have an explanatory comment

**File:** `musicstreamer/ui_qt/edit_station_dialog.py:166`
**Reason:** Subsumed by UI-03. The rationale comment the reviewer requested (D-13 policy, not DB invariant) is now embedded in the UI-03 tooltip block, which documents the same decision in a more prominent location. Skipping the separate standalone comment avoids redundant noise.

### IN-04: `codec_rank` returns 0 for both OPUS and unknown

**File:** `musicstreamer/stream_ordering.py:17-23`
**Reason:** Advisory / future work per the reviewer's own Fix note ("When OPUS support lands, extend `_CODEC_RANK`… No change needed now"). No OPUS streams exist in the current AA provider matrix (all tiers are AAC or MP3), so adding `"OPUS": 2` to `_CODEC_RANK` would be unreachable code. Defer until a concrete OPUS source appears.

---

## Verification

- `python3 -m pytest tests/test_stream_ordering.py tests/test_aa_import.py -q` — **44 passed** (post-fix)
- `python3 -m pytest tests/test_edit_station_dialog.py -q` — 19 passed, 4 pre-existing pytestqt `QTest=None` environmental failures (confirmed reproducing on `HEAD~7` baseline, unrelated to these fixes)
- All 7 commits passed `python3 -c "import ast; ast.parse(...)"` syntax check before commit
- No commit bypassed hooks

---

_Fixed: 2026-04-18_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
