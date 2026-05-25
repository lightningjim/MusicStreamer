---
phase: 52-eq-toggle-dropout-fix
plan: 02
subsystem: testing
tags: [pytest, pytest-qt, qt, signal-wiring, regression-guard, ui-test]

# Dependency graph
requires:
  - phase: 47.2-eq-profiles
    provides: FakePlayer.calls list pattern (D-08); eq_toggle_btn clicked.connect wiring (D-08)
provides:
  - Defensive call-count regression guard for eq_toggle_btn signal wiring (SC #3)
  - Exact-delta assertion idiom for FakePlayer.calls (locks against double-fire from accidental clicked+toggled wiring or programmatic .click())
affects: [phase-52-eq-toggle-dropout-fix, future-now-playing-panel-refactors, future-eq-toggle-changes]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Call-count delta assertion (`len(player.calls) - initial == 1`) for Qt signal-once invariants — locks against accidental double-wiring without source-level introspection"
    - "Per-value-count assertion (`player.calls.count((\"enabled\", True)) == 1`) for sanity-checking toggle alternation across multiple clicks"

key-files:
  created: []
  modified:
    - tests/test_now_playing_panel.py

key-decisions:
  - "Test asserts call-count delta (not source-level grep of clicked/toggled connections) — call-count is the runtime-observable invariant; production wiring is verified implicitly because any double-wiring would produce delta == 2"
  - "Two click cycles tested (False→True→False) with per-cycle delta assertion AND per-value occurrence count — guards against both extra-fire-on-one-click AND extra-fire-on-only-one-direction regressions"
  - "No FakePlayer changes needed — existing `calls: list` shape from Phase 47.2 D-08 already supports the assertion (CONTEXT.md D-10 confirmed the wiring is already clean today)"

patterns-established:
  - "SC #3 defensive test pattern: capture `initial = len(player.calls)`, click, assert delta == 1; repeat; assert per-value `count(...)` == 1 to lock alternation"

requirements-completed: [BUG-03]

# Metrics
duration: 1 min
completed: 2026-04-28
---

# Phase 52 Plan 02: SC #3 Defensive Test for EQ Toggle Wiring Summary

**Added `test_eq_toggle_fires_exactly_once_per_click` regression guard that locks SC #3 by asserting exact call-count delta (1 per click) on `FakePlayer.calls` — defends against future accidental double-wiring of `clicked` + `toggled` signals or programmatic `.click()` insertion in the toggle path.**

## Performance

- **Duration:** 1 min (~98 seconds)
- **Started:** 2026-04-28T23:19:26Z
- **Completed:** 2026-04-28T23:21:04Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- New `test_eq_toggle_fires_exactly_once_per_click` test function added to `tests/test_now_playing_panel.py` immediately after the existing `test_eq_toggle_click_calls_player_and_persists` (line 679+).
- Test asserts the exact call-count delta (`len(player.calls) - initial == 1`) on each of two simulated clicks — distinguishes 1 call from 2 of the same value, which the existing `in`-membership-based test cannot.
- Sanity assertions on per-value occurrence count (`("enabled", True)` appears exactly once, `("enabled", False)` appears exactly once across the two clicks) lock alternation behavior.
- Confirmed no production source modifications — the wiring at `musicstreamer/ui_qt/now_playing_panel.py:261` already uses `clicked.connect(self._on_eq_toggled)` (no `toggled` connection anywhere in `now_playing_panel.py`), per CONTEXT.md D-10.
- All 3 EQ-toggle tests pass (`test_eq_toggle_initial_state_from_setting`, `test_eq_toggle_click_calls_player_and_persists`, `test_eq_toggle_fires_exactly_once_per_click`); full file (41 tests) passes with no regression.

## Task Commits

Each task was committed atomically:

1. **Task 1: SC #3 defensive call-count test** — `beac205` (test)

This is a TDD-flavored test-only task (no production GREEN counterpart needed because CONTEXT.md D-10 established that the production wiring is already clean today; the test codifies that correctness as a regression guard). No `feat` commit follows because there is no behavior change.

## Files Created/Modified

- `tests/test_now_playing_panel.py` — Added `test_eq_toggle_fires_exactly_once_per_click` (41 lines inserted: function body + docstring + comment block). Inserted directly after the existing `test_eq_toggle_click_calls_player_and_persists` at the end of the file.

## Decisions Made

- **Call-count delta over source-level grep**: The plan's optional secondary assertion (using `inspect.getsource` or `pathlib.Path.read_text` to grep production source for `clicked.connect`/`toggled.connect`) was not implemented. Rationale: the call-count delta assertion catches the same regression at the runtime layer, which is more meaningful than a source-text check (a future refactor could rename `_on_eq_toggled` and the source-grep would fail unnecessarily; a future refactor could add a programmatic `.click()` and the source-grep would miss it). The plan's `<acceptance_criteria>` and `<verification>` blocks also use shell-level grep checks against the production source for the same purpose, performed at the gate level.
- **Two click cycles instead of one**: The plan's `<behavior>` requires two cycles (False→True→False); both `len()` deltas asserted independently AND per-value `count(...)` checks lock the alternation. This is strictly more defensive than the minimal single-click form mentioned in PATTERNS.md.
- **No FakePlayer changes**: The existing `calls: list` (Phase 47.2 D-08) already records every `set_eq_enabled` invocation as `("enabled", bool(enabled))`. No new test infrastructure needed.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Authentication Gates

None - this plan is purely test-only with no external services or auth requirements.

## User Setup Required

None - no external service configuration required.

## Verification Results

All plan-level `<verification>` gates passed:

| Gate | Command | Result |
|------|---------|--------|
| 1 | `grep -q 'def test_eq_toggle_fires_exactly_once_per_click' tests/test_now_playing_panel.py` | PASS |
| 2 | `grep -q 'len(player.calls) - initial == 1' tests/test_now_playing_panel.py` | PASS |
| 3 | `grep -q 'self.eq_toggle_btn.clicked.connect(self._on_eq_toggled)' musicstreamer/ui_qt/now_playing_panel.py` | PASS |
| 4 | `! grep -nE 'eq_toggle_btn\.toggled\.connect' musicstreamer/ui_qt/now_playing_panel.py` | PASS (no match) |
| 5 | `uv run --with pytest --with pytest-qt pytest tests/test_now_playing_panel.py -k "eq_toggle" -x` | PASS (3 passed) |
| 6 | `uv run --with pytest --with pytest-qt pytest tests/test_now_playing_panel.py -x` | PASS (41 passed) |

All 6 task-level `<acceptance_criteria>` also pass (same checks plus the per-value `count(...)` grep gates and full-file no-regression check).

## Cross-Links

- **Plan 52-01** (Wave 1 sibling, parallel execution): covers SC #1 ("no audible dropout on toggle-on") and SC #2 ("no audible dropout on toggle-off") via the gain-ramping fix in `musicstreamer/player.py`. SC #3 is locked here in 52-02 via this defensive test.
- **CONTEXT.md D-10** (Claude's Discretion): predicted that SC #3 is already satisfied at the wiring level — verified by the `! grep` gate above. This plan's test codifies that correctness as a regression guard rather than introducing new behavior.
- **PATTERNS.md** "tests/test_now_playing_panel.py — SC #3 defensive test" section (lines 246-303): provided the analog pattern (call-count delta assertion + FakePlayer reuse). The implemented test extends it with a second click cycle and per-value `count(...)` assertions for defense-in-depth.
- **Phase 47.2 D-08** (FakePlayer canonical shape, `tests/test_now_playing_panel.py:60-62`): reused without modification.

## Threat Flags

None - this plan adds a regression-guard test only. No new attack surface.

## Threat Mitigation

T-52-06 (Tampering — UX correctness regression: future refactor accidentally double-wires `clicked` + `toggled` to `_on_eq_toggled`): MITIGATED by `test_eq_toggle_fires_exactly_once_per_click`. A future change introducing a `eq_toggle_btn.toggled.connect(self._on_eq_toggled)` line would cause each click to fire `_on_eq_toggled` twice, producing `len(player.calls) - initial == 2` and failing the assertion loudly. Equivalently, a programmatic `.click()` added in `_on_eq_toggled` would cause infinite recursion or double-fire, both caught by the same assertion.

## Next Phase Readiness

- SC #3 locked via call-count regression guard. Ready for Plan 52-01 to land (covers SC #1/SC #2 via gain ramping).
- Phase 52 success criteria coverage:
  - SC #1 (no toggle-on dropout) — covered by Plan 52-01.
  - SC #2 (no toggle-off dropout) — covered by Plan 52-01.
  - SC #3 (toggle fires exactly once per click) — covered HERE by `test_eq_toggle_fires_exactly_once_per_click`.
- No blockers for Plan 52-01 (files modified are disjoint: `tests/test_now_playing_panel.py` here vs. `musicstreamer/player.py` + `tests/test_player.py` there).
- After both plans land: Phase 52 verifier should run the full test suite + UAT (Kyle clicks toggle 10× rapidly during AA station playback, reports zero audible artifacts per CONTEXT.md "Acceptance bar interpretation").

## Self-Check: PASSED

- `.planning/phases/52-eq-toggle-dropout-fix/52-02-SUMMARY.md` exists on disk
- `tests/test_now_playing_panel.py` exists and contains `def test_eq_toggle_fires_exactly_once_per_click`
- Task commit `beac205` (`test(52-02): add SC #3 defensive call-count test for eq_toggle wiring`) is present in git log
- All 6 plan-level verification gates passed
- All 8 task-level acceptance criteria passed
- Full `tests/test_now_playing_panel.py` (41 tests) passes with no regression

---
*Phase: 52-eq-toggle-dropout-fix*
*Completed: 2026-04-28*
