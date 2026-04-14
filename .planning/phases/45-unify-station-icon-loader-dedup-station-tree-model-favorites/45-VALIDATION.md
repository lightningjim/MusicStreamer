---
phase: 45
phase_slug: unify-station-icon-loader-dedup-station-tree-model-favorites
status: validated
validated: 2026-04-14
auditor: gsd-validate-phase (Nyquist)
---

# Phase 45 Validation — Unify station-icon loader

## Requirement → Test Verification Map

| Requirement ID | Truth | Test File | Test Name | Command | Status |
|----------------|-------|-----------|-----------|---------|--------|
| PHASE-45-UNIFY-LOADER | Single `load_station_icon` in `_art_paths.py` resolves, caches, scales, and falls back correctly | `tests/test_art_paths.py` | `test_relative_station_art_path_resolves_via_abs_art_path` | `.venv/bin/python -m pytest tests/test_art_paths.py::test_relative_station_art_path_resolves_via_abs_art_path -v` | green |
| PHASE-45-UNIFY-LOADER | Missing file falls back cleanly, no raise | `tests/test_art_paths.py` | `test_missing_file_falls_back_without_raising` | `.venv/bin/python -m pytest tests/test_art_paths.py::test_missing_file_falls_back_without_raising -v` | green |
| PHASE-45-UNIFY-LOADER | `None` art path falls back cleanly | `tests/test_art_paths.py` | `test_none_station_art_path_uses_fallback` | `.venv/bin/python -m pytest tests/test_art_paths.py::test_none_station_art_path_uses_fallback -v` | green |
| PHASE-45-UNIFY-LOADER | Absolute path passes through unchanged | `tests/test_art_paths.py` | `test_absolute_path_passes_through_unchanged` | `.venv/bin/python -m pytest tests/test_art_paths.py::test_absolute_path_passes_through_unchanged -v` | green |
| PHASE-45-UNIFY-LOADER | Default size = 32px bound | `tests/test_art_paths.py` | `test_default_size_is_32px` | `.venv/bin/python -m pytest tests/test_art_paths.py::test_default_size_is_32px -v` | green |
| PHASE-45-UNIFY-LOADER | Explicit `size=64` honored | `tests/test_art_paths.py` | `test_explicit_size_honored` | `.venv/bin/python -m pytest tests/test_art_paths.py::test_explicit_size_honored -v` | green |
| PHASE-45-UNIFY-LOADER | Cache keyed on resolved absolute path (D-03) | `tests/test_art_paths.py` | `test_cache_hit_on_second_call` | `.venv/bin/python -m pytest tests/test_art_paths.py::test_cache_hit_on_second_call -v` | green |
| PHASE-45-FIX-LIST-LOGO | Station tree's `DecorationRole` returns real logo, not fallback, for valid relative `station_art_path` | `tests/test_station_icon_integration.py` | `test_station_tree_model_decoration_role_returns_real_logo` | `.venv/bin/python -m pytest tests/test_station_icon_integration.py::test_station_tree_model_decoration_role_returns_real_logo -v` | green |
| PHASE-45-FIX-LIST-LOGO | Station tree falls back cleanly when art is missing | `tests/test_station_icon_integration.py` | `test_station_tree_model_decoration_role_falls_back_when_missing` | `.venv/bin/python -m pytest tests/test_station_icon_integration.py::test_station_tree_model_decoration_role_falls_back_when_missing -v` | green |
| PHASE-45-FIX-LIST-LOGO | Panel-level helper consumption resolves rel path to real pixmap | `tests/test_station_list_panel.py` | `test_station_row_logo_loads_via_abs_path` | `.venv/bin/python -m pytest tests/test_station_list_panel.py::test_station_row_logo_loads_via_abs_path -v` | green |
| PHASE-45-FIX-LIST-LOGO | Cache invalidation on path change returns different pixmap | `tests/test_station_list_panel.py` | `test_cache_invalidation_on_logo_change` | `.venv/bin/python -m pytest tests/test_station_list_panel.py::test_cache_invalidation_on_logo_change -v` | green |
| PHASE-45-FIX-FAVES-LOGO | Favorites list item icon is the real logo, not fallback, for favorited station with valid art | `tests/test_station_icon_integration.py` | `test_favorites_view_station_item_icon_is_real_logo` | `.venv/bin/python -m pytest tests/test_station_icon_integration.py::test_favorites_view_station_item_icon_is_real_logo -v` | green |
| PHASE-45-FIX-FAVES-LOGO | Favorites view falls back cleanly when art is missing | `tests/test_station_icon_integration.py` | `test_favorites_view_missing_art_falls_back_cleanly` | `.venv/bin/python -m pytest tests/test_station_icon_integration.py::test_favorites_view_missing_art_falls_back_cleanly -v` | green |

## Gap Analysis — Pre-Audit State

Plan 45-01 shipped `tests/test_art_paths.py` with 7 passing unit tests covering the shared `load_station_icon` helper in isolation and `tests/test_station_list_panel.py::test_station_row_logo_loads_via_abs_path` that exercises the helper via the panel's import. Two behavioral gaps remained:

1. **PHASE-45-FIX-LIST-LOGO was not verified end-to-end.** The panel test only proved that the panel's *import* of the helper works — not that `StationTreeModel.data(DecorationRole)` (the live code path the `QTreeView` actually invokes) returns a real logo. A regression that re-introduces raw `QPixmap(station.station_art_path)` in `_icon_for_station` would leave the existing tests green.
2. **PHASE-45-FIX-FAVES-LOGO had no behavioral test.** No test verified `FavoritesView._populate_stations` sets a real (non-fallback) icon on its list items for favorited stations with valid art.

## Gap Remediation

Added `tests/test_station_icon_integration.py` with 4 behavioral tests that drive the two previously-broken call sites end-to-end and assert the rendered icon's center pixel matches the source color (green), ruling out the fallback. These tests would FAIL against the pre-phase-45 implementation and now PASS against the unified helper — making them effective regression guards.

## Full Suite Status

- `tests/test_art_paths.py` — 7/7 green
- `tests/test_station_icon_integration.py` — 4/4 green (new)
- `tests/test_station_list_panel.py` — 19/20 green; 1 pre-existing unrelated failure (`test_filter_strip_hidden_in_favorites_mode`) documented in 45-01-SUMMARY.md as a pre-phase-45 baseline failure (filter strip starts collapsed by design).

## Files for Commit

- `tests/test_station_icon_integration.py` (new)

## VALIDATION Not Committed

Per orchestrator instructions, this VALIDATION.md is written but not committed.
