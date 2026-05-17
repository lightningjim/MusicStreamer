---
phase: 77-test-infrastructure-stabilization-fix-pre-existing-test-doub
plan: "01"
subsystem: test-infrastructure
tags: [test-infrastructure, drift-guard, pyside6, fakeplayer]
dependency_graph:
  requires: []
  provides: [tests/_fake_player.py, tests/test_fake_player_signal_parity.py, tests/test_fake_player_no_inline.py]
  affects: [Wave 2 plans (77-02 through 77-06) depend on _fake_player.py existing]
tech_stack:
  added: []
  patterns: [source-grep drift-guard, shared test-double module, rglob+ban-list]
key_files:
  created:
    - tests/_fake_player.py
    - tests/test_fake_player_signal_parity.py
    - tests/test_fake_player_no_inline.py
  modified: []
decisions:
  - "D-07: Canonical FakePlayer lives in tests/_fake_player.py; opt-in via direct import"
  - "D-16 deviation: Used source-grep for name parity instead of Player.__dict__ (gi not available in test env)"
  - "D-17: Only tests/_fake_player.py allowed to declare FakePlayer(QObject); KNOWN RED until 77-02"
metrics:
  duration: ~20 minutes
  completed: 2026-05-17
  tasks_completed: 3
  tasks_total: 3
  files_created: 3
  files_modified: 0
---

# Phase 77 Plan 01: Shared tests/_fake_player.py + 2 drift-guard tests Summary

Canonical FakePlayer(QObject) with all 18 Player signals and two source-grep drift-guards (D-16 name+arity parity, D-17 no-inline-QObject-FakePlayer) that prevent the 10-phase FakePlayer-drift recurrence.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create tests/_fake_player.py | 64b69e5 | tests/_fake_player.py |
| 2 | Create tests/test_fake_player_signal_parity.py | a64de34 | tests/test_fake_player_signal_parity.py |
| 3 | Create tests/test_fake_player_no_inline.py | cf59f2c | tests/test_fake_player_no_inline.py |

## Output Metrics

- **Signals declared:** 18 (matching musicstreamer/player.py:241-282 exactly)
- **Method stubs declared:** 9 (set_volume, play, pause, stop, restore_eq_from_settings, set_eq_enabled, set_eq_profile, set_eq_preamp, shutdown_underrun_tracker)
- **Wave 1 baseline offender count:** 11 (the 11 inline FakePlayer(QObject) sites Plan 77-02 will migrate)
- **Delta from RESEARCH.md L350-371 canonical signal list:** 0 (all 18 signals match production; no drift detected between planning and execution)

## Verification Results

1. `uv run python -c "from tests._fake_player import FakePlayer; FakePlayer()"` — PASS
2. `uv run pytest tests/test_fake_player_signal_parity.py -x` — PASS (2/2 tests)
3. Wave 1 baseline offender count: exactly 11 (Task 3 regex correctly scoped)
4. Drift injection verified manually: removing a signal from _fake_player.py causes test_fake_player_mirrors_every_player_signal to name the missing signal; changing Signal(int, int, int) to Signal(object) causes test_fake_player_signal_arity_matches_player to name the arity mismatch with both argument lists.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Used source-grep for name-parity check instead of Player.__dict__ introspection**

- **Found during:** Task 2
- **Issue:** RESEARCH.md draft uses `from musicstreamer.player import Player` + `Player.__dict__` for the name-parity check. `musicstreamer/player.py` imports `gi` at module level; `gi` is not available in the test environment (this is a pre-existing condition — 12 other test files already fail with `ModuleNotFoundError: No module named 'gi'` collection errors: test_player_caps.py, test_player_buffer.py, test_player_buffering.py, test_player_failover.py, test_player_node_runtime.py, test_player_tag.py, test_player_underrun.py, test_player_underrun_tracker.py, test_twitch_auth.py, test_twitch_playback.py, test_activation_token_strip.py, test_windows_palette.py).
- **Fix:** Both the name-parity and arity-parity checks use `_grep_signal_decls(ROOT / "musicstreamer" / "player.py")` (regex source-parse). This is equivalent in coverage — the production signal block is definitively grep-parseable — and is more portable than metaclass introspection (consistent with RESEARCH Pitfall 4's reasoning for avoiding PySide6 metaobject inspection). The arity check is unchanged from the RESEARCH.md draft.
- **Files modified:** tests/test_fake_player_signal_parity.py
- **Commit:** a64de34
- **Justification:** Using source-grep for name parity is semantically equivalent (the source block IS the canonical signal set; Player.__dict__ is derived from it). No correctness tradeoff. The RESEARCH.md draft's rationale for __dict__ was to exclude inherited QObject signals (destroyed, objectNameChanged) — source-grep of player.py:241-282 also excludes them because they are not declared in that block.

## Known Stubs

None — all three files are production-ready drift-guards, not stubs.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes introduced. The two drift-guard tests read repo-controlled source files via `Path.read_text` (bounded to project root). No secrets or credentials involved.

## Self-Check
