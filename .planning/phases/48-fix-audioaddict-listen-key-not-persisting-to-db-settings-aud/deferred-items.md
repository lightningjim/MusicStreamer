# Phase 48 — Deferred Items

Logged during plan 48-02 execution. These issues are pre-existing, out of scope,
and unrelated to phase 48's listen-key persistence work. Left for future cleanup.

## Pre-existing test failures (not caused by 48-02)

### ModuleNotFoundError: No module named 'gi'
Pre-existing gstreamer binding issue affecting these suites in sandboxed
environments without system gobject-introspection:
- `tests/test_cookies.py` (collection error)
- `tests/test_player_buffering.py` (collection error)
- `tests/test_player_failover.py` (collection error)
- `tests/test_player_tag.py` (collection error)
- `tests/test_twitch_auth.py` (collection error)
- `tests/test_twitch_playback.py` (collection error)
- `tests/test_windows_palette.py` (collection error)
- `tests/test_player_buffer.py` (all cases)
- `tests/test_player_pause.py` (all cases)
- `tests/test_player_volume.py` (all cases)
- `tests/test_player.py::test_elapsed_timer_*` + EQ cases
- `tests/test_headless_entry.py::test_headless_smoke_wires_without_error`

Root cause: these modules import `musicstreamer.player` → `gi`. Not reproducible
on a dev machine with system `python3-gi` installed; only surfaces in the uv
virtualenv. Unrelated to ImportDialog or Repo.

### test_station_list_panel.py::test_filter_strip_hidden_in_favorites_mode
Qt visibility-mode assertion failing at baseline (verified against 33d5205
before Task 1 landed). Unrelated to phase 48 scope — touches
`StationListPanel`, which 48-02 does not modify.
