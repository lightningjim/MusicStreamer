---
phase: 45
plan: "45-01"
subsystem: ui_qt
tags: [refactor, bugfix, qt, icons, dedup]
requires:
  - musicstreamer.ui_qt._art_paths.abs_art_path
  - musicstreamer.paths.data_dir
provides:
  - musicstreamer.ui_qt._art_paths.load_station_icon
  - musicstreamer.ui_qt._art_paths.FALLBACK_ICON
affects:
  - musicstreamer/ui_qt/station_tree_model.py
  - musicstreamer/ui_qt/favorites_view.py
  - musicstreamer/ui_qt/station_list_panel.py
tech-stack:
  added: []
  patterns:
    - shared-helper-dedup
    - QPixmapCache-keyed-on-absolute-path
key-files:
  created:
    - tests/test_art_paths.py
  modified:
    - musicstreamer/ui_qt/_art_paths.py
    - musicstreamer/ui_qt/station_tree_model.py
    - musicstreamer/ui_qt/favorites_view.py
    - musicstreamer/ui_qt/station_list_panel.py
    - tests/test_station_list_panel.py
decisions:
  - D-01 Helper location — extend _art_paths.py (already houses abs_art_path)
  - D-02 Shared API — load_station_icon(station, size=32) -> QIcon; FALLBACK_ICON constant
  - D-03 Cache key — f"station-logo:{abs_path or FALLBACK_ICON}" (always keyed on resolved absolute path)
  - D-04 Delete duplicates — no back-compat shims; all three in-tree callers migrated
metrics:
  duration_minutes: 8
  tasks_completed: 2
  files_changed: 5
  tests_added: 7
  completed: 2026-04-14
---

# Phase 45 Plan 01: Unify Station Icon Loader Summary

Deduplicated three parallel station-icon loaders (`StationTreeModel._icon_for_station`, `FavoritesView._load_station_icon`, `station_list_panel._load_station_icon`) into a single shared `load_station_icon(station, size=32)` helper in `musicstreamer/ui_qt/_art_paths.py`. Fixes the live regression where the main station tree and favorites list rendered the generic fallback icon even when a valid `station_art_path` existed on disk — both broken call sites were passing raw relative paths to `QPixmap()`, which silently returns null against a non-CWD working directory.

## Tasks

| # | Name | Commit | Status |
|---|------|--------|--------|
| 1 | TDD RED: 7 failing tests in `tests/test_art_paths.py` | `8a583b3` | done |
| 1 | TDD GREEN: implement `load_station_icon` + `FALLBACK_ICON` in `_art_paths.py` | `77ac7fa` | done |
| 2 | Refactor: migrate 3 loaders + delete duplicates + update test imports | `24e4fc6` | done |
| 3 | UAT checkpoint (human-verify) | — | awaiting user |

## Implementation Notes

**Cache key parity.** The old code stored entries under `f"station-logo:{path}"` where `path` was the raw input — so the same logo hit different cache slots when referenced as relative vs absolute. The new helper always resolves through `abs_art_path()` first, so every caller shares a single cache entry per logo.

**No back-compat shims.** All three duplicate loaders were private (`_load_station_icon`) or instance methods (`_icon_for_station`). Per D-04, they were deleted outright; the only out-of-module reference was two tests in `tests/test_station_list_panel.py` that imported `_load_station_icon` from `station_list_panel` — updated to import the shared helper via an alias so the existing assertions continue to compile.

**Import hygiene.** Stale `QPixmap`, `QPixmapCache`, and `icons_rc` imports were pruned from the three migrated modules (helper owns them now). `abs_art_path` import in `station_list_panel.py` was replaced by `load_station_icon` since that was its only use site.

## Test Results

- **Added:** 7 tests in `tests/test_art_paths.py` — all pass.
  - Relative path resolves via `abs_art_path` → non-null real logo (regression guard)
  - Missing file falls back cleanly
  - `None` station_art_path falls back cleanly
  - Absolute path passes through unchanged
  - Default size = 32px bound
  - Explicit size = 64px bound honored
  - Second call hits QPixmapCache (verified by deleting file between calls)
- **Scope-adjacent regression run:** 53 pass, 1 pre-existing unrelated failure (`test_filter_strip_hidden_in_favorites_mode` — filter strip starts collapsed by design; confirmed to fail on HEAD before my changes via `git stash` baseline).
- **Broader failures** (25): all pre-existing and caused by missing `yt_dlp`, GStreamer `Gst` binding, Twitch/yt_import collection errors — unrelated to this plan.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocker] Updated two stale test imports in `tests/test_station_list_panel.py`**
- **Found during:** Task 2
- **Issue:** Two tests imported the deleted `_load_station_icon` from `station_list_panel` by name.
- **Fix:** Rewrote the imports as `from musicstreamer.ui_qt._art_paths import load_station_icon as _load_station_icon` — preserved the local alias so call-site assertions did not need to change.
- **Files modified:** `tests/test_station_list_panel.py`
- **Commit:** `24e4fc6` (folded into Task 2 refactor commit, as the plan explicitly allows test import updates)

No other deviations.

## UAT Checkpoint (Task 3 — human-verify)

**Awaiting user verification.** Please:

1. Launch the Qt UI: `python -m musicstreamer.ui_qt` (or your usual entry point).
2. In the **Stations** mode (left panel), expand a provider group that contains stations with valid logos (e.g. AudioAddict / DI.fm stations — any station where you've seen the note-replacement icon previously).
3. **Expected:** Each station row shows the station's own logo at 32px, not the generic `audio-x-generic-symbolic` note icon.
4. Switch to **Favorites** mode. Star a station with a known-good logo if you haven't already.
5. **Expected:** The favorited station in the "Favorite Stations" list also shows its real logo.
6. Check **Recently Played** (top of Stations mode) for a station you've recently played — logo should also render.
7. Confirm both the fallback case still works: a station with missing/null `station_art_path` falls back to the generic icon cleanly (no crash, no broken-image placeholder).

If all four surfaces (tree, favorites, recently-played, and fallback) render correctly, the plan is verified.

## Self-Check: PASSED

- Created files verified:
  - `tests/test_art_paths.py` — FOUND
  - `.planning/phases/45-unify-station-icon-loader-dedup-station-tree-model-favorites/45-01-SUMMARY.md` — FOUND (this file)
- Commits verified (via `git log --oneline`):
  - `8a583b3` test(45-01) RED — FOUND
  - `77ac7fa` feat(45-01) GREEN — FOUND
  - `24e4fc6` refactor(45-01) migrate — FOUND
