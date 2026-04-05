---
phase: 19-custom-accent-color
plan: "01"
subsystem: accent-color
tags: [css, gtk, settings, tdd]
dependency_graph:
  requires: []
  provides: [accent_utils._is_valid_hex, accent_utils.build_accent_css, App.accent_provider, App.repo]
  affects: [musicstreamer/__main__.py, musicstreamer/constants.py]
tech_stack:
  added: [musicstreamer/accent_utils.py]
  patterns: [CssProvider at PRIORITY_USER, repo.get_setting for persistence]
key_files:
  created: [musicstreamer/accent_utils.py, tests/test_accent_provider.py]
  modified: [musicstreamer/constants.py, musicstreamer/__main__.py]
decisions:
  - "ACCENT_COLOR_DEFAULT (#3584e4) included in ACCENT_PRESETS list for test_default_in_presets coverage"
  - "self.repo stored on App instance so AccentDialog (Plan 02) can access it via app.repo"
  - "PRIORITY_USER chosen over PRIORITY_APPLICATION so accent overrides app-level theme tokens"
metrics:
  duration_minutes: 8
  completed_date: "2026-04-05"
  tasks_completed: 2
  files_changed: 4
requirements:
  - ACCENT-01
---

# Phase 19 Plan 01: Accent Color Backend Summary

Hex validation utility, accent CSS provider injection at app startup, and persistence via SQLite settings — all implemented TDD with 14 tests green.

## What Was Built

- `musicstreamer/accent_utils.py` — `_is_valid_hex(value)` (regex validates 3- or 6-digit hex) and `build_accent_css(hex_value)` (returns `@define-color accent_bg_color <hex>;`)
- `musicstreamer/constants.py` — Added `ACCENT_COLOR_DEFAULT = "#3584e4"` and `ACCENT_PRESETS` list (8 colors)
- `musicstreamer/__main__.py` — `do_activate` now creates a second `Gtk.CssProvider` at `PRIORITY_USER`, loads accent hex from `repo.get_setting("accent_color", ACCENT_COLOR_DEFAULT)`, stores it as `self.accent_provider` and `self.repo` on the App instance
- `tests/test_accent_provider.py` — 14 tests: hex validation (8), CSS format (2), settings roundtrip (2), preset validity (2)

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 (RED) | f8aecbf | test(19-01): add failing tests for accent color backend |
| 2 (GREEN) | ef32026 | feat(19-01): implement accent color constants, utils, and CSS provider injection |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. The accent provider reads from SQLite on startup and injects live CSS. No placeholders.

## Threat Flags

None. No new network endpoints, auth paths, or trust boundaries introduced. All operations local (SQLite read + GTK CSS inject).

## Self-Check: PASSED

- `musicstreamer/accent_utils.py` exists: FOUND
- `musicstreamer/constants.py` contains ACCENT_COLOR_DEFAULT: FOUND
- `musicstreamer/__main__.py` contains accent_provider: FOUND
- Commit f8aecbf: FOUND
- Commit ef32026: FOUND
- All 14 tests pass, 169 total passing
