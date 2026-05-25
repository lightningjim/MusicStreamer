# Phase 73 — Deferred Items

Out-of-scope discoveries during execution. Per the GSD scope boundary rule,
these are NOT fixed by the current phase's executor — they are logged for a
future maintainer or a dedicated phase.

## Pre-existing test failures (unrelated to Phase 73)

### `tests/test_import_dialog_qt.py::test_audioaddict_tab_widgets`

- **Discovered:** Plan 73-01, Task 3 verification
- **Reproduces on:** Unmodified main branch at HEAD before Plan 73-01 changes
- **Error:** `AttributeError: 'ImportDialog' object has no attribute '_aa_quality'` at line 143
- **Why deferred:** Failure is in `import_dialog_qt.py`, completely unrelated
  to the cover-art / repo / models surface of Phase 73. Triggered by a stash
  bisect: `git stash → run test → fail → git stash pop`, confirming the bug
  pre-exists Plan 73-01's first commit.
- **Recommended fix:** File a follow-up bug (BUG-NN) and triage independently
  — likely a Phase 72 carry-over or earlier regression.

### `tests/test_main_window_media_keys.py` + `tests/test_main_window_gbs.py` ERRORs

- **Discovered:** Plan 73-01, Task 3 full-suite verification
- **Reproduces on:** Unmodified main branch (these are setup-time ERRORs, not
  failures — distinct from the `test_import_dialog_qt` AttributeError above)
- **Error:** `AttributeError: 'FakePlayer' object has no attribute 'underrun_recovery_started'` at `musicstreamer/ui_qt/main_window.py:361`
- **Why deferred:** Pre-existing FakePlayer fixture is missing an underrun
  recovery attribute that main_window references. Completely outside the
  Phase 73 cover-art surface — affects main window construction in tests
  only. Triggered before any cover-art code executes.
- **Recommended fix:** Extend FakePlayer with the missing attribute or set a
  default-False signal stub. File as a follow-up bug.

### `tests/ui_qt/test_main_window_node_indicator.py::test_hamburger_indicator_present_when_node_missing`

- **Discovered:** Plan 73-01, Task 3 full-suite verification
- **Reproduces on:** Unmodified main branch
- **Why deferred:** Pre-existing assertion failure in the hamburger-indicator
  test — unrelated to cover-art routing.
- **Recommended fix:** Triage independently.
