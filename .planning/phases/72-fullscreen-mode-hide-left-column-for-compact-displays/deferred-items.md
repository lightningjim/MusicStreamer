# Phase 72 — Deferred Items (out of scope for Plan 72-01)

Items discovered during Wave 0 spike (Plan 72-01) that are pre-existing in the
worktree's base commit and NOT introduced by Phase 72 work.

## Pre-existing test suite failures on worktree base (commit 83c1e88)

The worktree was created from a base commit (`83c1e88 fix(69): productionize
Phase 43.1 Pitfall #1 (pyside6 from conda-forge)`) that predates Phase 70 / 71
test-suite repair work. Running the full `pytest tests/` from this base produces
these failures, none of which are introduced by Plan 72-01:

| File | Test | Symptom |
| ---- | ---- | ------- |
| `tests/test_import_dialog_qt.py` | `test_audioaddict_tab_widgets` | `AttributeError: 'ImportDialog' object has no attribute '_aa_quality'` |
| `tests/test_main_window_gbs.py` | `test_add_gbs_menu_entry_exists` | setup ERROR |
| `tests/test_main_window_gbs.py` | `test_add_gbs_triggers_worker_start` | setup ERROR |
| `tests/test_main_window_gbs.py` | several `test_import_*` | setup ERROR |
| `tests/test_main_window_media_keys.py` | `test_media_keys_backend_constructed` | setup ERROR |
| `tests/test_main_window_media_keys.py` | `test_title_changed_fires_publish_metadata` | setup ERROR |
| (one mid-suite Qt-level abort observed running `tests/` end-to-end) | | unrelated to Wave 0 |

**Disposition:** Out of scope for Phase 72. These will be resolved when the
worktree branch merges onto current `main` (or are already fixed there — verify
during the orchestrator merge step). Phase 72's targeted tests
(`tests/test_phase72_assumptions.py`) PASS in isolation on this base.

## Pre-existing system-Python PyGI deprecation warning

`pytest -W error` against any pytest-qt test in this project escalates a system-wide
warning to error:

```
gi.PyGIDeprecationWarning: GLib.unix_signal_add_full is deprecated;
use GLibUnix.signal_add_full instead
```

Source: `/usr/lib/python3/dist-packages/gi/overrides/__init__.py:159`.

**Disposition:** Out of scope. The warning originates from the system Python's PyGI
package (Debian/Ubuntu packaging), not from MusicStreamer. The Task 2 acceptance
criterion's intent ("no NEW warnings from Wave 0") is satisfied. Wave 0 adds zero
new warnings. Fix path (if ever desired): pin a newer PyGI inside `.venv` or move
the bus-bridge import behind a try/except that suppresses the deprecation.

## Pre-existing Qt teardown crash crossing test_phase72_now_playing_panel → test_phase72_assumptions (Plan 72-03)

Found during Plan 72-03 verification when running multiple test files together.

**Symptom:** Running `pytest tests/test_main_window_integration.py tests/test_phase72_now_playing_panel.py tests/test_phase72_assumptions.py` (or any ordering that puts the assumptions file LAST after now_playing_panel) aborts with `Fatal Python error: Aborted` inside Qt's teardown path between the last test in `test_phase72_now_playing_panel.py` and the first test in `test_phase72_assumptions.py`.

**Reproduction:** Confirmed pre-existing — reproduces on the bare worktree branch HEAD with Plan 72-03's `main_window.py` impl reverted. The crash is in the C teardown stack (`_ZN7QWidgetD1Ev` / `_ZN14QObjectPrivate14deleteChildrenEv`), suggesting a Qt singleton or QApplication-lifecycle issue between the two test modules' fixtures, NOT a regression from Plan 03.

**Disposition:** Out of scope for Plan 72-03. Each of the four files passes individually:
- `pytest tests/test_main_window_integration.py` → 66 passed
- `pytest tests/test_phase72_compact_toggle.py` → 12 passed
- `pytest tests/test_phase72_now_playing_panel.py` → 8 passed (in isolation)
- `pytest tests/test_phase72_assumptions.py` → 2 passed (in isolation)

The plan's verification command (`pytest tests/test_phase72_compact_toggle.py tests/test_main_window_integration.py -x -v`) — the specific ordering the plan body specifies — runs cleanly: 78 passed.

Reordering to `pytest tests/test_phase72_assumptions.py tests/test_phase72_now_playing_panel.py tests/test_phase72_compact_toggle.py tests/test_main_window_integration.py` also runs cleanly: 88 passed. So the crash is reproducible only in the specific ordering `…now_playing_panel.py → …assumptions.py`.

Fix path (out of scope for Plan 72-03): investigate whether `test_phase72_now_playing_panel.py` is leaving a dangling QObject parented to QApplication that the next test's qtbot teardown stumbles on (likely the cover-art worker thread issue Plan 72-02 already documented under "Pre-existing test-teardown warning"). Would belong to a test-infrastructure cleanup phase, not a feature phase.
