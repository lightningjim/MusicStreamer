---
phase: 77-test-infrastructure-stabilization-fix-pre-existing-test-doub
plan: 02
subsystem: tests
tags: [test-infrastructure, fakeplayer, migration, drift-guard]
dependency_graph:
  requires: [77-01]
  provides: [shared-fakeplayer-migration-complete, d17-drift-guard-green]
  affects: [tests/test_fake_player_no_inline.py, tests/_fake_player.py]
tech_stack:
  added: []
  patterns:
    - "Shared test double import pattern: `from tests._fake_player import FakePlayer`"
    - "Alias import for underscore-prefix sites: `from tests._fake_player import FakePlayer as _FakePlayer`"
    - "Function-local import split for multi-name transitive consumers"
    - "MagicMock post-construction override for play_stream in test_stream_picker player fixture"
key_files:
  created: []
  modified:
    - tests/_fake_player.py
    - tests/test_main_window_integration.py
    - tests/test_main_window_underrun.py
    - tests/test_phase72_1_stream_picker_reflow.py
    - tests/test_phase72_integration.py
    - tests/test_phase72_compact_toggle.py
    - tests/test_phase72_peek_overlay.py
    - tests/test_phase72_assumptions.py
    - tests/test_main_window_gbs.py
    - tests/test_main_window_soma.py
    - tests/test_now_playing_panel.py
    - tests/test_phase72_now_playing_panel.py
    - tests/test_ui_qt_scaffold.py
    - tests/test_main_window_media_keys.py
    - tests/test_discovery_dialog.py
    - tests/test_stream_picker.py
    - tests/ui_qt/test_main_window_node_indicator.py
    - tests/test_equalizer_dialog.py
decisions:
  - "D-09 Option A honored: test_equalizer_dialog.py non-QObject FakePlayer stays inline with documenting comment"
  - "Rule 2: Extended shared FakePlayer with set_volume_calls, stop_called, pause_called, calls attributes + tracking to satisfy NowPlayingPanel test assertions"
  - "Rule 2: Added play_stream() stub to shared FakePlayer (NowPlayingPanel calls player.play_stream on picker selection)"
  - "Rule 2: test_stream_picker player fixture overrides play_stream with MagicMock() post-construction to preserve assert_called_once assertions"
metrics:
  duration: "~25 minutes"
  completed: "2026-05-17"
  task_count: 2
  file_count: 18
---

# Phase 77 Plan 02: Migrate 11 inline FakePlayer(QObject) sites + 5 transitive consumers Summary

**One-liner:** Deleted all 11 inline FakePlayer(QObject) class definitions from tests/ and redirected 5 transitive importers to shared tests/_fake_player.py, turning the Plan 77-01 D-17 drift-guard GREEN.

## What Was Built

**Task 1 — SEED migration + 5 transitive consumers (commit 820a2cd)**

- Deleted the inline `FakePlayer(QObject)` class from `tests/test_main_window_integration.py` (lines 31-84; the SEED)
- Added `from tests._fake_player import FakePlayer` in its place
- Redirected 5 transitive `from tests.test_main_window_integration import FakePlayer` imports:
  - `test_main_window_underrun.py` — split to `from tests._fake_player import FakePlayer` + `from tests.test_main_window_integration import FakeRepo`
  - `test_phase72_integration.py`, `test_phase72_compact_toggle.py`, `test_phase72_peek_overlay.py`, `test_phase72_assumptions.py` — same split pattern
  - `test_phase72_1_stream_picker_reflow.py` — function-local import split, preserving `as MWFakePlayer` alias for line 448's `MainWindow(MWFakePlayer(), repo)` usage
- [Rule 2] Added `play_stream()` stub to `tests/_fake_player.py` — `NowPlayingPanel` calls `player.play_stream(s)` at `now_playing_panel.py:1198` on picker selection; required for `test_signal_survives_round_trip` to pass after migration

**Task 2 — 10 remaining inline sites + D-09 comment (commit 451dec3)**

- Deleted `_FakePlayer(QObject)` inline classes from 4 sites using underscore-prefix; aliased import: `from tests._fake_player import FakePlayer as _FakePlayer`
  - `test_main_window_gbs.py` — also removes WRONG `audio_caps_detected = Signal(object)` arity (auto-fixed)
  - `test_main_window_soma.py` — same arity auto-fix
  - `test_ui_qt_scaffold.py`
  - `tests/ui_qt/test_main_window_node_indicator.py` (subdirectory site)
- Deleted `FakePlayer(QObject)` inline classes from 6 sites; direct import: `from tests._fake_player import FakePlayer`
  - `test_now_playing_panel.py`
  - `test_phase72_now_playing_panel.py`
  - `test_main_window_media_keys.py`
  - `test_discovery_dialog.py`
  - `test_stream_picker.py`
  - `test_phase72_1_stream_picker_reflow.py` (inline class at line 79; Task 1 handled the line-422 transitive import)
- Added `# Phase 77 D-09 (Option A)` documenting comment to `tests/test_equalizer_dialog.py:40` (non-QObject FakePlayer stays inline)
- [Rule 2] Extended `tests/_fake_player.py` with `set_volume_calls`, `stop_called`, `pause_called`, `calls` tracking attributes — required by `test_now_playing_panel.py` assertions (`fp.set_volume_calls[-1]`, `fp.stop_called`, `player.calls`)
- [Rule 2] Updated `tests/test_stream_picker.py` `player` fixture: `p.play_stream = MagicMock()` post-construction, preserving `player.play_stream.assert_called_once()` and `player.play_stream.assert_not_called()` assertions

## Migration Statistics

| Category | Count |
|----------|-------|
| QObject FakePlayer sites migrated | 11 |
| Transitive consumer imports redirected | 5 |
| Underscore-prefix sites (aliased import) | 4 |
| Non-migration sites (D-09, stays inline) | 1 |
| Total files modified | 18 |

## Verification Results

- D-17 drift-guard (`tests/test_fake_player_no_inline.py`): **GREEN** — zero inline `class _?FakePlayer(QObject)` offenders remain
- `audio_caps_detected = Signal(object)` arity drift at gbs/soma: **AUTO-FIXED** (shared module uses production-correct `Signal(int, int, int)`)
- All 226 tests across the 11 affected files + the no-inline guard: **PASSED**
- Production code: **ZERO changes** (byte-identical musicstreamer/ directory)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Added play_stream() to shared FakePlayer**
- **Found during:** Task 1 analysis of test_phase72_1_stream_picker_reflow.py
- **Issue:** `NowPlayingPanel._on_stream_selected` calls `self._player.play_stream(s)` at `now_playing_panel.py:1198`. Shared FakePlayer had no `play_stream` method — `test_signal_survives_round_trip` would fail with `AttributeError` after migration
- **Fix:** Added `play_stream(self, stream) -> None` stub to `tests/_fake_player.py` that appends to `play_calls`
- **Files modified:** `tests/_fake_player.py`
- **Commit:** 820a2cd

**2. [Rule 2 - Missing Critical Functionality] Extended shared FakePlayer instance attributes**
- **Found during:** Task 2 analysis of test_now_playing_panel.py
- **Issue:** `test_now_playing_panel.py` assertions use `fp.set_volume_calls[-1]`, `fp.stop_called is True`, `player.calls` tuples — none present in original shared FakePlayer (which had `pause_calls: int`, `stop_calls: int`, `volume: float`)
- **Fix:** Added `set_volume_calls: list[float]`, `stop_called: bool`, `pause_called: bool`, `calls: list[tuple]` to `FakePlayer.__init__`; updated `set_volume`, `pause`, `stop`, `set_eq_enabled` methods to populate them alongside existing tracking
- **Files modified:** `tests/_fake_player.py`
- **Commit:** 451dec3

**3. [Rule 2 - Missing Critical Functionality] test_stream_picker play_stream MagicMock override**
- **Found during:** Task 2 analysis of test_stream_picker.py
- **Issue:** Inline FakePlayer used `self.play_stream = MagicMock()` in `__init__` to enable `player.play_stream.assert_called_once()` and `player.play_stream.assert_not_called()` assertions. Replacing with shared FakePlayer would break these since `play_stream` is now a real method
- **Fix:** Modified `player` fixture in `test_stream_picker.py` to add `p.play_stream = MagicMock()` after construction
- **Files modified:** `tests/test_stream_picker.py`
- **Commit:** 451dec3

### Pre-existing Failures (Not Introduced By This Plan)

- `test_hamburger_menu_actions` in `test_main_window_integration.py` — pre-existing menu text mismatch, present on the Wave 1 base commit before any changes
- Cross-file Qt-teardown crash when `test_main_window_integration.py` runs before `test_phase72_integration.py` — pre-existing cluster 3 issue (CONTEXT.md D-13); individual files pass in isolation

## Known Stubs

None — all migrations are import swaps. No new stubs introduced.

## Threat Flags

None — zero production-code changes; all changes are within test files and test helper module.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| All 13 modified test files exist | PASSED |
| Task 1 commit 820a2cd exists | PASSED |
| Task 2 commit 451dec3 exists | PASSED |
| D-17 drift-guard GREEN (zero inline FakePlayer(QObject)) | PASSED |
| test_fake_player_no_inline.py passes | PASSED |
| 226 tests across 11 affected files + no-inline guard pass | PASSED |
| Zero production-code changes | PASSED |
