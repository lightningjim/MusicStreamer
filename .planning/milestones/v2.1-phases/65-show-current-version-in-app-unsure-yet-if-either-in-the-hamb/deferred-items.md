# Phase 65 — Deferred Items

Out-of-scope discoveries surfaced during execution. Per `<deviation_rules>` SCOPE
BOUNDARY, executors only auto-fix issues directly caused by the current task's
changes; pre-existing flakes / failures in unrelated files are logged here, not
fixed in-plan.

---

## Pre-existing flake — `tests/test_import_dialog_qt.py::test_yt_scan_passes_through` (Qt teardown abort)

**Discovered by:** Plan 65-01 (full-suite regression check); independently re-confirmed by Plan 65-02.

**Symptom:** When the full pytest suite is run (`uv run pytest`), the run aborts
with `Fatal Python error: Aborted` deep inside `QObjectPrivate::deleteChildren`
→ `QWidget::~QWidget`, triggered after
`tests/test_import_dialog_qt.py::test_yt_scan_passes_through` (line 234) starts
a `_YtScanWorker` QThread via `qtbot.waitSignal(worker.finished, timeout=3000)`.

**Pre-existing:** Reverted the working tree to commit `f033cca` (the parent of
both Plan 65-01 and Plan 65-02) — the same Qt fatal occurs at the same site.
Phase 65 changes do not touch `tests/test_import_dialog_qt.py`,
`_YtScanWorker`, `import_dialog.py`, or the spec/menu/version surfaces relevant
to that test. The flake reproduces with or without Phase 65's changes.

**Isolation works:** `uv run pytest tests/test_import_dialog_qt.py` passes 25/25
in isolation. `uv run pytest tests/test_import_dialog_qt.py::test_yt_scan_passes_through`
also passes in isolation on both HEAD and `f033cca`. The race only manifests
when prior pytest-qt fixtures leave residual widget state that interacts badly
with `_YtScanWorker`'s thread cleanup.

**Last touched:** Phase 999.7 (`f4d8971`), well before Phase 65.

**Plan 65 plan-level suites are GREEN:**

```
uv run pytest tests/test_version.py tests/test_main_window_integration.py tests/test_main_run_gui_ordering.py -x
====== 52 passed, 1 warning in 1.11s ======

uv run pytest tests/test_packaging_spec.py -x
====== 4 passed in 0.06s ======
```

**Recommendation:** File as a follow-up maintenance phase. Likely tied to
fixture-cleanup ordering across the ~40+ Qt test files that run before
`test_import_dialog_qt.py`. Possible fixes: `@pytest.mark.qtisolated` markers
or splitting Qt-heavy test modules into sub-collections.

---

## Pre-existing test failures — `_FakePlayer` missing `underrun_recovery_started` signal (Phase 62 follow-up)

**Discovered by:** Plan 65-01 execution, 2026-05-08.

**Symptom:** Multiple test files using a local `_FakePlayer` stub crash
`MainWindow` construction with:

```
AttributeError: '_FakePlayer' object has no attribute 'underrun_recovery_started'
```

at `musicstreamer/ui_qt/main_window.py:304`. Phase 62 added
`underrun_recovery_started` to the real `Player` and connected it in
`MainWindow.__init__`, but these test stubs were not updated.

**Affected test files (≥18 errors + 16 failures at f033cca baseline):**

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

**Pre-existing:** Reverted the working tree to commit `f033cca` (the parent of
all Plan 65-01 work) — the same `AttributeError` reproduces in
`tests/test_ui_qt_scaffold.py::test_main_window_constructs_and_renders`. Plan
65-01 does not touch `_FakePlayer` stubs in any of these files.

**Plan 65-01 quick suite GREEN excluding the pre-existing failures:**
1145 passed / 0 failed.

**Recommendation:** A Phase 62 follow-up to add `underrun_recovery_started =
Signal()` to all local `_FakePlayer` stubs (or extract a shared
`tests/_FakePlayer.py` helper).
