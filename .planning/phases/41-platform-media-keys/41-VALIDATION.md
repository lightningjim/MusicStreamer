---
phase: 41
name: platform-media-keys
validated_by: gsd-nyquist-auditor
validation_date: 2026-04-15
status: green
---

# Phase 41 Validation Map

## Summary

| Plan | Requirements | Automated Tests | Status |
|------|-------------|-----------------|--------|
| 41-01 | MEDIA-01 | `pytest tests/test_media_keys_scaffold.py` (9 tests) | green |
| 41-02 | MEDIA-02, MEDIA-05 | `pytest tests/test_media_keys_mpris2.py -m "not integration"` (11 tests; Test 10 integration-gated) | green |
| 41-03 | MEDIA-04, MEDIA-05 | `pytest tests/test_main_window_media_keys.py` (8 tests) | green |
| 41-04 | MEDIA-04, MEDIA-05 | `pytest tests/test_main_window_media_keys.py` (5 stop-transition tests, 13 total) | green |
| T-41-09 | Path traversal guard | `pytest tests/test_media_keys_scaffold.py::test_cover_path_for_station_rejects_non_int` (4 parametrize cases) | green |
| T-41-06 | xesam:title passthrough | `pytest tests/test_media_keys_mpris2.py::test_xesam_title_passthrough_verbatim` (requires D-Bus) | green (skip_if_no_bus) |

## Verification Commands

```bash
# Scaffold + factory + T-41-09 path-traversal guard (no D-Bus required)
python -m pytest tests/test_media_keys_scaffold.py -v

# MainWindow wiring (no D-Bus required — uses _SpyBackend monkeypatch)
python -m pytest tests/test_main_window_media_keys.py -v

# MPRIS2 backend unit tests (requires D-Bus session bus; skip integration mark for CI)
python -m pytest tests/test_media_keys_mpris2.py -v -m "not integration"
```

## Verification Map

| Task / Threat ID | Requirement | Test File | Test Name | Command | Status |
|-----------------|-------------|-----------|-----------|---------|--------|
| 41-01 Task 1 | NoOpMediaKeysBackend instantiates, methods return None | test_media_keys_scaffold.py | test_noop_instantiates_and_methods_return_none | `pytest tests/test_media_keys_scaffold.py` | green |
| 41-01 Task 1 | play_pause_requested signal observable | test_media_keys_scaffold.py | test_signal_observable_via_qtbot | `pytest tests/test_media_keys_scaffold.py` | green |
| 41-01 Task 1 | Invalid state raises ValueError | test_media_keys_scaffold.py | test_invalid_playback_state_raises_value_error | `pytest tests/test_media_keys_scaffold.py` | green |
| 41-01 Task 1 | MediaKeysBackend importable without raising | test_media_keys_scaffold.py | test_media_keys_backend_importable | `pytest tests/test_media_keys_scaffold.py` | green |
| 41-01 Task 2 | create() returns MediaKeysBackend on Linux | test_media_keys_scaffold.py | test_create_returns_media_keys_backend_on_linux | `pytest tests/test_media_keys_scaffold.py` | green |
| 41-01 Task 2 | create() returns NoOp on win32 | test_media_keys_scaffold.py | test_create_returns_noop_on_win32 | `pytest tests/test_media_keys_scaffold.py` | green |
| 41-01 Task 2 | create() returns NoOp on freebsd | test_media_keys_scaffold.py | test_create_returns_noop_on_freebsd | `pytest tests/test_media_keys_scaffold.py` | green |
| 41-01 Task 2 | smtc raises NotImplementedError with 43.1 | test_media_keys_scaffold.py | test_smtc_create_windows_backend_raises_not_implemented | `pytest tests/test_media_keys_scaffold.py` | green |
| T-41-02 | No winrt in sys.modules on Linux | test_media_keys_scaffold.py | test_no_winrt_in_sys_modules | `pytest tests/test_media_keys_scaffold.py` | green |
| T-41-09 | cover_path_for_station rejects non-int (str, float, None) | test_media_keys_scaffold.py | test_cover_path_for_station_rejects_non_int[../evil] | `pytest tests/test_media_keys_scaffold.py` | green |
| T-41-09 | cover_path_for_station rejects non-int string "42" | test_media_keys_scaffold.py | test_cover_path_for_station_rejects_non_int[42] | `pytest tests/test_media_keys_scaffold.py` | green |
| T-41-09 | cover_path_for_station rejects float | test_media_keys_scaffold.py | test_cover_path_for_station_rejects_non_int[3.14] | `pytest tests/test_media_keys_scaffold.py` | green |
| T-41-09 | cover_path_for_station rejects None | test_media_keys_scaffold.py | test_cover_path_for_station_rejects_non_int[None] | `pytest tests/test_media_keys_scaffold.py` | green |
| 41-02 Task 1 | cover_path_for_station returns correct path, creates dir | test_media_keys_mpris2.py | test_cover_path_for_station_returns_correct_path_and_creates_dir | `pytest tests/test_media_keys_mpris2.py -m "not integration"` | green |
| 41-02 Task 1 | write_cover_png None pixmap returns None | test_media_keys_mpris2.py | test_write_cover_png_none_pixmap_returns_none | `pytest tests/test_media_keys_mpris2.py -m "not integration"` | green |
| 41-02 Task 1 | write_cover_png valid pixmap creates file >50 bytes | test_media_keys_mpris2.py | test_write_cover_png_valid_pixmap_creates_file | `pytest tests/test_media_keys_mpris2.py -m "not integration"` | green |
| 41-02 Task 1 | write_cover_png overwrites same file, no second file | test_media_keys_mpris2.py | test_write_cover_png_overwrites_same_file | `pytest tests/test_media_keys_mpris2.py -m "not integration"` | green |
| 41-02 Task 1 | write_cover_png respects _root_override | test_media_keys_mpris2.py | test_write_cover_png_respects_root_override | `pytest tests/test_media_keys_mpris2.py -m "not integration"` | green |
| 41-02 Task 2 | LinuxMprisBackend constructs and registers service | test_media_keys_mpris2.py | test_linux_mpris_backend_constructs | `pytest tests/test_media_keys_mpris2.py -m "not integration"` | green (skip_if_no_bus) |
| 41-02 Task 2 | publish_metadata updates station/title/art_url | test_media_keys_mpris2.py | test_linux_mpris_backend_publish_metadata | `pytest tests/test_media_keys_mpris2.py -m "not integration"` | green (skip_if_no_bus) |
| 41-02 Task 2 | publish_metadata(None) produces NoTrack trackid | test_media_keys_mpris2.py | test_linux_mpris_backend_publish_metadata_none | `pytest tests/test_media_keys_mpris2.py -m "not integration"` | green (skip_if_no_bus) |
| 41-02 Task 2 | set_playback_state valid states + bogus raises ValueError | test_media_keys_mpris2.py | test_linux_mpris_backend_set_playback_state | `pytest tests/test_media_keys_mpris2.py -m "not integration"` | green (skip_if_no_bus) |
| 41-02 Task 2 | PlayPause slot emits play_pause_requested signal | test_media_keys_mpris2.py | test_linux_mpris_backend_slot_play_pause_emits_signal | `pytest tests/test_media_keys_mpris2.py -m "not integration"` | green (skip_if_no_bus) |
| 41-02 Task 2 | shutdown() idempotent — no raise on double call | test_media_keys_mpris2.py | test_linux_mpris_backend_shutdown_idempotent | `pytest tests/test_media_keys_mpris2.py -m "not integration"` | green (skip_if_no_bus) |
| T-41-06 | xesam:title passes markup verbatim (no escaping) | test_media_keys_mpris2.py | test_xesam_title_passthrough_verbatim | `pytest tests/test_media_keys_mpris2.py -m "not integration"` | green (skip_if_no_bus) |
| 41-03 Task 1 | MainWindow _media_keys set, signals connected | test_main_window_media_keys.py | test_media_keys_backend_constructed | `pytest tests/test_main_window_media_keys.py` | green |
| 41-03 Task 1 | title_changed fires publish_metadata with station + title | test_main_window_media_keys.py | test_title_changed_fires_publish_metadata | `pytest tests/test_main_window_media_keys.py` | green |
| 41-03 Task 1 | station activated → set_playback_state("playing") | test_main_window_media_keys.py | test_station_activated_sets_playing_state | `pytest tests/test_main_window_media_keys.py` | green |
| 41-03 Task 1 | failover(None) → set_playback_state("stopped") | test_main_window_media_keys.py | test_failover_none_sets_stopped_state | `pytest tests/test_main_window_media_keys.py` | green |
| 41-03 Task 1 | play_pause_requested signal toggles playback | test_main_window_media_keys.py | test_play_pause_requested_toggles_playback | `pytest tests/test_main_window_media_keys.py` | green |
| 41-03 Task 1 | stop_requested signal stops playback | test_main_window_media_keys.py | test_stop_requested_stops_player | `pytest tests/test_main_window_media_keys.py` | green |
| 41-03 Task 1 | closeEvent calls backend.shutdown() | test_main_window_media_keys.py | test_close_calls_backend_shutdown | `pytest tests/test_main_window_media_keys.py` | green |
| 41-03 Task 1 | NoOp backend: all wiring completes without exception | test_main_window_media_keys.py | test_factory_exception_does_not_crash_startup | `pytest tests/test_main_window_media_keys.py` | green |
| 41-04 Task 1 | _on_panel_stopped calls publish_metadata(None, "", None) | test_main_window_media_keys.py | test_panel_stopped_clears_metadata | `pytest tests/test_main_window_media_keys.py` | green |
| 41-04 Task 1 | _on_media_key_stop calls publish_metadata(None, "", None) | test_main_window_media_keys.py | test_media_key_stop_clears_metadata | `pytest tests/test_main_window_media_keys.py` | green |
| 41-04 Task 1 | _on_failover(None) calls publish_metadata(None, "", None) | test_main_window_media_keys.py | test_failover_none_clears_metadata | `pytest tests/test_main_window_media_keys.py` | green |
| 41-04 Task 1 | _on_offline calls publish_metadata(None, "", None) | test_main_window_media_keys.py | test_offline_clears_metadata | `pytest tests/test_main_window_media_keys.py` | green |
| 41-04 Task 1 | _on_station_deleted clears metadata for playing station | test_main_window_media_keys.py | test_station_deleted_clears_metadata | `pytest tests/test_main_window_media_keys.py` | green |
| 41-04 Task 2 | logging.basicConfig present in main() | __main__.py | manual-only | `grep -c 'logging.basicConfig' musicstreamer/__main__.py` (expect: 1); end-to-end: `DBUS_SESSION_BUS_ADDRESS=/dev/null uv run python -m musicstreamer` shows "Media keys disabled" on stderr | green (manual) |

## Notes

- Tests 6, 7, 8, 9, 11, 12 in test_media_keys_mpris2.py (LinuxMprisBackend tests) use `skip_if_no_bus` — they are skipped in headless/CI environments without a D-Bus session bus. This is a pre-existing environment limitation, not a test authoring gap.
- Test 10 (playerctl integration) is gated with `@pytest.mark.integration` and additionally skipped if `playerctl` is not installed.
- T-41-09 test lives in test_media_keys_scaffold.py (not test_media_keys_mpris2.py) because test_media_keys_mpris2.py imports PySide6.QtDBus at module scope, making the file unimportable in envs without QtDBus. The art_cache module itself has no QtDBus dependency.
- UAT (41-03 Task 2) approved by user: commit efcfbbc — "docs(41): phase 41 complete — Linux MPRIS2 media keys UAT approved".
