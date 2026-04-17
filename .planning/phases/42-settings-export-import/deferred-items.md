# Phase 42 - Deferred Items (discovered during 42-03 execution)

## Environment-level test collection/execution failures (pre-existing)

These failures exist on the base commit (81bf97a) and are NOT caused by plan 42-03 changes.
They are scope-out per the SCOPE BOUNDARY rule (deviation_rules).

### Missing optional dependencies
- `tests/test_yt_import_library.py` - ModuleNotFoundError: yt_dlp
- `tests/test_import_dialog.py` - yt_dlp (import_dialog imports yt_import)
- `tests/test_import_dialog_qt.py` - yt_dlp
- `tests/test_main_window_integration.py` - yt_dlp (main_window imports yt helpers)
- `tests/test_main_window_media_keys.py` - yt_dlp
- `tests/test_media_keys_mpris2.py` - optional PyQt DBus binding
- `tests/test_ui_qt_scaffold.py` - dependency chain includes yt_dlp
- `tests/test_player_failover.py` - yt_dlp
- `tests/test_twitch_auth.py` - streamlink
- `tests/test_twitch_playback.py` - streamlink
- `tests/test_station_list_panel.py` - dependency chain

### Missing pytest-qt QtTest binding
- `tests/test_edit_station_dialog.py` (several tests) - `qt_api.QtTest.QTest` is None

**Remediation (not in scope for 42-03):** Install optional deps in the worktree environment
or mark these test modules with an import-level skipif so the full suite can run cleanly
in minimal environments. Phase-42 scope (`tests/test_settings_export.py`,
`tests/test_settings_import_dialog.py`) is 100% green — the UAT test 8 gap IS closed at
the automated-test layer.
