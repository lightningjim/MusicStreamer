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
