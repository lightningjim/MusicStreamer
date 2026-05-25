# Phase 72.1 — Deferred Items

Out-of-scope discoveries during Phase 72.1 execution. Documented per
`agents/gsd-executor.md` SCOPE BOUNDARY: pre-existing failures and lint
warnings in unrelated files are NOT fixed by the active plan.

## Pre-existing test failures (NOT caused by Phase 72.1)

### `tests/test_main_window_integration.py::test_hamburger_menu_actions` (FAILED)

- **Surfaced during:** Plan 72.1-02 Task 3 regression-check sweep.
- **Verified pre-existing:** YES — runs and fails at the Phase 72.1 base
  commit `b581a36` (verified via `git stash` + bare-tree test run).
- **Disposition:** OUT OF SCOPE for Phase 72.1. Phase 72.1 modifies only
  `musicstreamer/ui_qt/now_playing_panel.py` plus the test file
  `tests/test_phase72_1_stream_picker_reflow.py`; this hamburger-menu test
  does not exercise either the row-1/row-2 reflow path or the
  stream-picker fixture infrastructure.
- **Recommended owner:** A future MainWindow/hamburger-menu-related phase
  or a dedicated test-infrastructure phase.
