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
