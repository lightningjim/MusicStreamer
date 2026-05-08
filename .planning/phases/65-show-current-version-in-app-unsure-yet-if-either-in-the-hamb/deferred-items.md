# Phase 65 Deferred Items

Out-of-scope discoveries surfaced during execution. Deviation Rule SCOPE BOUNDARY:
only auto-fix issues directly caused by the current task's changes; pre-existing flakes
are logged here, not fixed in this plan.

## Pre-existing flake — `tests/test_import_dialog_qt.py::test_yt_scan_passes_through`

**Discovered:** Plan 65-01 execution, 2026-05-08

**Symptom:** When the full pytest suite is run (`uv run pytest`), the suite aborts with
`Fatal Python error: Aborted` deep inside `QObjectPrivate::deleteChildren` after the test
`tests/test_import_dialog_qt.py::test_yt_scan_passes_through` (line 234) starts a
`_YtScanWorker` QThread via `qtbot.waitSignal(worker.finished, timeout=3000)`. The
process aborts with a Qt fatal during widget tree teardown.

**Confirmed pre-existing:** Reverted the working tree to commit `f033cca` (the parent of
all Plan 65-01 work) — the same Qt fatal occurs at the same site. Plan 65-01 changes
do not touch `tests/test_import_dialog_qt.py`, `_YtScanWorker`, or `import_dialog.py`.
The flake reproduces with or without my changes. Out of scope per SCOPE BOUNDARY rule.

**Isolation works:** `uv run pytest tests/test_import_dialog_qt.py` passes 25/25 in
isolation. The race only manifests when prior pytest-qt fixtures leave residual widget
state that interacts badly with `_YtScanWorker`'s thread cleanup.

**Plan 65-01 contract is GREEN:** The plan's quick-loop suite is fully green:

```
uv run pytest tests/test_version.py tests/test_main_window_integration.py tests/test_main_run_gui_ordering.py -x
====== 52 passed, 1 warning in 1.11s ======
```

This pre-existing flake should be filed as its own bug phase if it becomes annoying;
it does not block Plan 65-01.

## Pre-existing test failures — `_FakePlayer` missing `underrun_recovery_started` signal

**Discovered:** Plan 65-01 execution, 2026-05-08

**Symptom:** Multiple test files using a local `_FakePlayer` stub crash MainWindow
construction with `AttributeError: '_FakePlayer' object has no attribute
'underrun_recovery_started'` at `musicstreamer/ui_qt/main_window.py:304`. Phase 62
added `underrun_recovery_started` to the real `Player` and connected it in
MainWindow.__init__, but these test stubs were not updated.

**Affected test files (≥18 errors + 16 failures total at f033cca baseline):**

- `tests/test_main_window_media_keys.py` (errors at setup)
- `tests/test_main_window_gbs.py` (errors at setup)
- `tests/test_media_keys_mpris2.py`
- `tests/test_station_list_panel.py::test_filter_strip_hidden_in_favorites_mode`
- `tests/test_station_list_panel.py::test_refresh_recent_updates_list`
- `tests/test_twitch_auth.py::test_play_twitch_sets_plugin_option_when_token_present`
- `tests/test_ui_qt_scaffold.py::test_main_window_constructs_and_renders`
- `tests/test_ui_qt_scaffold.py::test_main_window_default_geometry`
- `tests/ui_qt/test_main_window_node_indicator.py::test_hamburger_indicator_absent_when_node_available`
- `tests/ui_qt/test_main_window_node_indicator.py::test_hamburger_indicator_present_when_node_missing`

**Confirmed pre-existing:** Reverted the working tree to commit `f033cca` (the parent of
all Plan 65-01 work) — same `AttributeError` reproduces in
`tests/test_ui_qt_scaffold.py::test_main_window_constructs_and_renders`. Plan 65-01 does
not touch `_FakePlayer` stubs in any of these files.

**Mitigation:** Out of scope for Plan 65-01. Should be filed as a Phase 62 follow-up
to add `underrun_recovery_started = Signal()` to all local `_FakePlayer` stubs (or
extract a shared `tests/_FakePlayer.py` helper). Plan 65-01's quick suite plus a
deselection of these pre-existing failures runs **1145 passed / 0 failed**.
