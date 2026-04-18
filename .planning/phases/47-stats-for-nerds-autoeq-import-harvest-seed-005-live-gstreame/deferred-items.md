# Phase 47 — Deferred Items

Pre-existing test environment issues surfaced during execution of plan 47-01.
These were **not caused by any change in this phase**. They exist on `main`
prior to plan 47-01's first edit. Verified by `git stash`-ing the edit and
reproducing the failure identically.

## Environment issues (not code bugs)

### Missing `yt_dlp` module
- **Impact:** Collection errors / test skips on 5 modules
  - tests/test_import_dialog_qt.py
  - tests/test_main_window_integration.py
  - tests/test_main_window_media_keys.py
  - tests/test_media_keys_mpris2.py
  - tests/test_ui_qt_scaffold.py
  - tests/test_yt_import_library.py
- **Fix:** `pip install yt-dlp` in this environment
- **Out of scope** for Phase 47.

### pytest-qt `QtTest` None-type
- **Impact:** ~10 Qt-widget tests fail with
  `AttributeError: 'NoneType' object has no attribute 'QTest'`
  in `pytest-qt`'s `qtbot.mouseClick`.
- **Affected suites:** test_edit_station_dialog, test_station_list_panel,
  test_player_failover, test_twitch_auth, test_twitch_playback, test_cookies
- **Likely cause:** pytest-qt picked a Qt backend that didn't load QtTest.
- **Out of scope** for Phase 47.

All new tests landed by this phase (tests/test_stream_ordering.py) are pure
Python with no Qt or yt_dlp dependency, and pass cleanly.
