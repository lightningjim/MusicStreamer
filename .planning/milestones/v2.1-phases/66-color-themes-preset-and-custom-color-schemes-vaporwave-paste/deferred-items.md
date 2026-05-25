# Phase 66 deferred items

Out-of-scope discoveries logged during execution per SCOPE BOUNDARY rule.

## Pre-existing flake: full-suite Qt teardown abort

**Discovered:** Plan 66-01 Task 3 verification (2026-05-09)

**Symptom:** Running `pytest tests/ -q` (full suite, without `-x`) triggers a
fatal Qt-internal abort (`qt_assert` → `QObjectPrivate::deleteChildren`
→ `~QWidget`) during the run, with the C stack dumping out of
`libQt6Core.so` / `libQt6Widgets.so`. The same crash reproduces with the
Phase 66 changes stashed (verified by `git stash --include-untracked` then
re-running) — so this is **not caused by** Plan 66-01.

**Reproduction:**
- `pytest tests/ -q --ignore=tests/test_theme_picker_dialog.py --ignore=tests/test_theme_editor_dialog.py`
  → crashes mid-run with no clear failing test.
- `pytest tests/test_edit_station_dialog.py` (full file, isolated) → 66 passed.
- `pytest tests/test_main_run_gui_ordering.py` (isolated) → 3 passed.
- `pytest tests/test_theme.py tests/test_accent_color_dialog.py tests/test_accent_provider.py`
  (Phase 66 + Phase 59 contract suites) → 48 passed.

**Why deferred:** Plan 66-01 Done criteria are all satisfied via the targeted
test runs (test_theme.py 21/21, test_accent_color_dialog.py + test_accent_provider.py
green, AST parse OK). The full-suite teardown crash is a pre-existing
test-isolation issue unrelated to theme palette work and is out of scope
for the Phase 66 surface.

**Recommended owner:** A future test-infrastructure phase that audits
`pytest-qt` widget-cleanup ordering across the Qt suite. Likely candidate
fixes: per-test `qtbot.addWidget(...)` discipline; explicit `widget.deleteLater()
+ qApp.processEvents()` between tests; or marking offending tests
`@pytest.mark.serial` to force ordering.

**Not blocking:** Plan 66-01 verification uses the targeted-test runs the
PLAN explicitly calls out (`pytest tests/test_theme.py -x -q`,
`pytest tests/test_accent_color_dialog.py tests/test_accent_provider.py -x -q`).
Both pass cleanly.

## Pre-existing flake: tests/test_main_window_*.py — `_FakePlayer` missing `underrun_recovery_started`

**Discovered:** Plan 66-04 Task 1 verification (2026-05-09)

**Symptom:** Running any of `tests/test_main_window_gbs.py`, `tests/test_main_window_integration.py`, etc. errors immediately with:

```
AttributeError: '_FakePlayer' object has no attribute 'underrun_recovery_started'
musicstreamer/ui_qt/main_window.py:308: AttributeError
```

**Reproduction (verified pre-existing):**
- Stash Plan 66-04 menu wiring → `pytest tests/test_main_window_gbs.py::test_add_gbs_menu_entry_exists` → SAME error.
- Re-apply Plan 66-04 changes → SAME error.

**Why deferred:** Out of scope per SCOPE BOUNDARY rule. The `_FakePlayer`
test fixtures across `tests/test_main_window_*.py` were never updated to
include the `underrun_recovery_started` Signal that Phase 62 added to
`musicstreamer.player`. Plan 66-04 only adds a menu action + slot — it
neither modifies the fixture nor the Phase 62 Signal wiring.

**Recommended owner:** A future Phase 62-cleanup or test-infra phase that
audits the `_FakePlayer` fakes for completeness against the real
`Player` Signal surface.

**Not blocking:** Plan 66-04 Task 1 verification uses the targeted theme
+ accent suites (`tests/test_theme.py tests/test_theme_picker_dialog.py
tests/test_theme_editor_dialog.py tests/test_accent_color_dialog.py
tests/test_accent_provider.py` — 75/75 green) plus AST parse +
load-bearing greps. The hamburger-menu wire is verified end-to-end at
the import boundary (`from musicstreamer.ui_qt.main_window import
MainWindow` succeeds).
