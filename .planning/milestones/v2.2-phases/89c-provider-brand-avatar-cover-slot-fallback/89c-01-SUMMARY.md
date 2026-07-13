---
phase: 89c-provider-brand-avatar-cover-slot-fallback
plan: 01
subsystem: cover-art / brand-avatar fallback
tags: [brand-avatar, registry, cover-art, now-playing, pyinstaller, tdd]
completed: "2026-06-17T16:55:15Z"
duration: "~15 min"

dependency_graph:
  requires: []
  provides:
    - brand_avatars.lookup() — 7-key static registry mapping provider_name → bundled PNG path
    - musicstreamer/ui_qt/brand-avatars/ — git-tracked loose-PNG asset directory
    - _resolve_brand_avatar_fallback — three-tier D-08 cover-exhausted resolver in now_playing_panel
    - _set_brand_avatar_pixmap — absolute-path circular-crop render method
    - _last_brand_avatar — tier-replay state var (D-11)
    - brand-avatars PyInstaller datas entry for frozen-build importlib.resources resolution
  affects:
    - musicstreamer/ui_qt/now_playing_panel.py — _on_cover_art_ready if-not-path branch changed

tech_stack:
  added: []
  patterns:
    - Static registry dict + lookup() (mirroring yt_import register_avatar_fetcher shape)
    - importlib.resources.files() for frozen-build-safe package-data resolution
    - Source-grep drift-guards (structural contracts, no GStreamer/Qt behavioral mocks)
    - TDD Wave-0 scaffold: RED drift-guards written in Task 1, GREEN in Task 2

key_files:
  created:
    - musicstreamer/brand_avatars.py
    - musicstreamer/ui_qt/brand-avatars/.gitkeep
    - tests/test_brand_avatars.py
  modified:
    - musicstreamer/ui_qt/now_playing_panel.py
    - tests/test_cover_art_avatar.py
    - packaging/windows/MusicStreamer.spec

key_decisions:
  - D-01: GBS.FM excluded from _REGISTRY (not a supported brand-avatar provider)
  - D-04: missing PNG → None (graceful absent-asset, current station-logo behavior)
  - D-07: brand lookup fires only from _on_cover_art_ready if-not-path branch
  - D-08: three-tier resolution (user-override → registry → station-logo)
  - D-11: _last_brand_avatar tracks brand path for _apply_art_tier 4th-branch replay, reset in bind_station
  - D-12: source-grep drift-guard in test_cover_art_avatar.py confirms brand lookup placement

metrics:
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 3
  tests_added: 7  # 5 unit + 2 drift-guards in test_brand_avatars.py; 1 drift-guard in test_cover_art_avatar.py
  tests_passing: 18
---

# Phase 89c Plan 01: Brand Avatar Fallback — Registry, Wiring, and Tests Summary

**One-liner:** Static 7-key brand-avatar registry + now_playing_panel three-tier D-08 resolver wired at the cover-resolution-exhausted `if not path:` branch, with source-grep drift-guards and PyInstaller frozen-build datas entry.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | f0f91451 | feat(89c-01): brand_avatars registry + asset dir + unit tests (Wave 0) |
| Task 2 | 691b9d99 | feat(89c-01): now_playing_panel wiring + drift-guards + spec datas entry |

## Tasks Executed

### Task 1: Registry module, asset dir, and registry unit tests (Wave 0)

**TDD RED:** Wrote `tests/test_brand_avatars.py` first with 5 unit tests (all failing — `ModuleNotFoundError`) and 2 source-grep drift-guards (failing until Task 2 wiring lands).

**TDD GREEN:** Created `musicstreamer/brand_avatars.py` with:
- `_REGISTRY: dict[str, str]` — 7 exact provider_name keys mapped to PNG filenames
- `lookup(provider_name) -> Optional[str]` — importlib.resources path resolution + os.path.isfile guard (D-04); never raises
- GBS.FM NOT in registry (D-01)

Created `musicstreamer/ui_qt/brand-avatars/.gitkeep` and force-added to git (setuptools VCS discovery; PNGs arrive from user later per D-04).

**Verification:** 5 lookup tests GREEN; 2 source-grep drift-guards present (RED until Task 2).

### Task 2: now_playing_panel wiring, drift-guards, and PyInstaller datas

Edited `musicstreamer/ui_qt/now_playing_panel.py`:
1. `__init__`: added `self._last_brand_avatar: Optional[str] = None` (D-11)
2. `bind_station` reset block: added `self._last_brand_avatar = None` alongside `_last_avatar_path = None` (D-11 stale-station bleed guard)
3. `_apply_art_tier`: inserted 4th branch `elif self._last_brand_avatar is not None:` between `_last_avatar_path` and `else` (D-11 precedence: real cover > _last_avatar_path > _last_brand_avatar > logo)
4. `_on_cover_art_ready` `if not path:` body: replaced `_show_station_logo_in_cover_slot()` with `_resolve_brand_avatar_fallback()` (D-07 single hook point)
5. New `_resolve_brand_avatar_fallback(self)`: D-08 three-tier resolution (user-override → registry → logo)
6. New `_set_brand_avatar_pixmap(self, abs_path)`: absolute-path load + `_make_circular_pixmap` (D-06) + clear-before-fallback on isNull (D-11)

Added `test_brand_lookup_only_in_cover_exhausted_branch` to `tests/test_cover_art_avatar.py` (D-12 drift-guard: brand lookup in `_on_cover_art_ready` only, not in `bind_station` or `cover_art.py`).

Added brand-avatars datas entry to `packaging/windows/MusicStreamer.spec` with full namespace destination path `musicstreamer/ui_qt/brand-avatars` (D-05 / Pitfall 9 frozen-build importlib.resources resolution).

**Verification:** All 18 tests GREEN (5 registry unit + 2 source-grep drift-guards in test_brand_avatars.py; 11 existing + 1 new drift-guard in test_cover_art_avatar.py).

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

- `musicstreamer/ui_qt/brand-avatars/` contains only `.gitkeep` — the 7 brand PNGs arrive from the user later per D-04. Until then, `brand_avatars.lookup()` returns None for all keys (missing-asset path) and `_resolve_brand_avatar_fallback` falls through to `_show_station_logo_in_cover_slot()` (current behavior preserved). This is a fully tested and intentional stub state.

## Threat Flags

None — no new network endpoints or trust boundaries introduced. All bundle assets are read-only package data; decode failures degrade gracefully per T-89c-02 mitigation (D-04 + isNull guard).

## Self-Check: PASSED

All created files confirmed present on disk. Both task commits confirmed in git log.
