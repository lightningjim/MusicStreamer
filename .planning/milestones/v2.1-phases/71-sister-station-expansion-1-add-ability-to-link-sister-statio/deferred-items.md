# Phase 71 — Deferred Items

Items discovered during Phase 71 execution that are **out of scope** for this phase
(Rule: only auto-fix issues directly caused by the current task's changes). Logged
here so the next executor / verifier / `/gsd-add-phase` can pick them up.

---

## Pre-existing test failures surfaced during 71-08 Task 4 verification

Phase 71 prior plans (71-00 through 71-07) all reported their **own** test suites
GREEN but did not gate the full project-wide pytest suite. Task 4 of plan 71-08
ran `pytest tests/ -x` for the first time post-Phase-71 and surfaced 17 failures +
18 errors. **All of these are latent Phase 62 / Phase 49 / DBus-infra issues that
pre-date Phase 71** — `git checkout` at the 71-01 tracking commit baseline shows
the same failures.

### A. Phase 62 test-double drift (FakePlayer missing `underrun_recovery_started` signal)

`musicstreamer/ui_qt/main_window.py:326` connects to
`self._player.underrun_recovery_started` (added in commit `b60e86c` for Phase 62).
Several test-double `_FakePlayer` / `FakePlayer` classes in unrelated tests still
ship the pre-Phase-62 shape.

**Affected test files:**

- `tests/test_ui_qt_scaffold.py::test_main_window_constructs_and_renders`
- `tests/test_ui_qt_scaffold.py::test_main_window_default_geometry`
- `tests/test_main_window_media_keys.py::test_close_calls_backend_shutdown`
- `tests/test_main_window_media_keys.py::test_factory_exception_does_not_crash_startup`
- `tests/test_main_window_media_keys.py::test_media_keys_backend_constructed` (and 9 sibling tests)
- `tests/test_main_window_gbs.py::test_add_gbs_menu_entry_exists` (and 6 sibling tests)
- `tests/test_station_list_panel.py::test_filter_strip_hidden_in_favorites_mode`
- `tests/test_station_list_panel.py::test_refresh_recent_updates_list`
- `tests/test_twitch_auth.py::test_play_twitch_sets_plugin_option_when_token_present`
- `tests/ui_qt/test_main_window_node_indicator.py::test_hamburger_indicator_absent_when_node_available`
- `tests/ui_qt/test_main_window_node_indicator.py::test_hamburger_indicator_present_when_node_missing`

**Fix shape (for a follow-up phase):** Add `underrun_recovery_started = Signal()`
(and parity for any other Phase 62 player signals — `underrun_recovery_ended`,
`buffer_underrun_observed`, etc.) to each `_FakePlayer` / `FakePlayer` class.
Or factor a shared `tests/conftest_player_double.py` with the canonical signal set.

### B. DBus name-collision in MPRIS2 unit tests

`tests/test_media_keys_mpris2.py` 7 tests:

- `test_linux_mpris_backend_constructs`
- `test_linux_mpris_backend_publish_metadata`
- `test_linux_mpris_backend_publish_metadata_none`
- `test_linux_mpris_backend_set_playback_state`
- `test_linux_mpris_backend_slot_play_pause_emits_signal`
- `test_linux_mpris_backend_shutdown_idempotent`
- `test_xesam_title_passthrough_verbatim`

All fail with `RuntimeError: registerService('org.mpris.MediaPlayer2.musicstreamer')
failed: name already taken or bus error`. Cause: session DBus has the bus name held
by another process (e.g., a previously-launched MusicStreamer instance or stale
test-runner pid). Pre-existing parallel-test infrastructure issue.

**Fix shape:** Per-test unique bus-name suffix (e.g., `f".test{os.getpid()}_{uuid4()}"`)
or `monkeypatch` `SERVICE_NAME` to a unique value in the fixture.

### C. Pre-existing import-dialog AA quality-combo regression

`tests/test_import_dialog_qt.py::test_audioaddict_tab_widgets` and
`::test_audioaddict_quality_combo` fail with
`AttributeError: 'ImportDialog' object has no attribute '_aa_quality'`. This is the
**single pre-existing failure noted in `.planning/PROJECT.md` line 51** — carried
forward from Phase 56 commit `414e236` ("chore(aa-import): remove dead Quality
dropdown") which removed the widget but missed the test references.

**Fix shape:** Delete the orphan test assertions, or restore a quality combo if
the UX is wanted back.

### D. test_main_window_underrun real-network logo-fetch causes Qt::fatal

`tests/test_main_window_underrun.py::test_first_call_shows_toast` triggers a real
`urllib.urlretrieve` on a logo-fetch worker thread inside EditStationDialog. The
worker hits the network, the parent widget gets garbage-collected mid-call, and
Qt aborts with a fatal assertion in `QObjectPrivate::deleteChildren`. Causes the
pytest process to abort, masking subsequent failures.

**Fix shape:** Monkeypatch `urllib.request.urlretrieve` for this test (or block
the network with `pytest-socket --disable-socket`).

---

## Phase 71 own tests — all GREEN

For the record:

- `tests/test_station_siblings.py` + `tests/test_add_sibling_dialog.py`: 22 passed
- Phase 71 sibling tests in `test_settings_export.py`, `test_now_playing_panel.py`,
  `test_edit_station_dialog.py`, `test_main_window_integration.py`: 25 passed (filter `-k "sibling or _siblings or merge_siblings or chip"`)

Phase 71 introduced zero new failures.

---

*Logged 2026-05-12 during plan 71-08 Task 4 final verification.*
