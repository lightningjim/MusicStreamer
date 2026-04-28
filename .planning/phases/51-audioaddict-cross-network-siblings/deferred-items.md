# Phase 51 — Deferred Items

Out-of-scope discoveries during plan execution. NOT addressed; logged here for future visibility.

## Pre-existing test failures (not introduced by Phase 51)

Discovered during Plan 51-01 regression run. Confirmed pre-existing by re-running on the un-modified prior commit (66d0b9b, RED state) with the GREEN implementation stashed — same failures reproduce. None of these tests touch `musicstreamer/url_helpers.py` or any code modified in Phase 51 plans.

| Test | Module | Likely root cause (not investigated) |
|------|--------|--------------------------------------|
| `tests/test_media_keys_mpris2.py::test_linux_mpris_backend_constructs` | `musicstreamer/media_keys/mpris2.py` | DBus `registerObject` failing in this test environment |
| `tests/test_media_keys_mpris2.py::test_xesam_title_passthrough_verbatim` | `musicstreamer/media_keys/mpris2.py` | Same DBus environment issue |
| `tests/test_media_keys_smtc.py::test_thumbnail_from_in_memory_stream` | `musicstreamer/media_keys/smtc.py` | Windows-specific path on Linux runner |
| `tests/test_station_list_panel.py::test_filter_strip_hidden_in_favorites_mode` | `musicstreamer/ui_qt/station_list_panel.py` | Pre-existing — likely unrelated phase regression |
| `tests/test_twitch_auth.py::test_play_twitch_sets_plugin_option_when_token_present` | `musicstreamer/twitch_auth.py` | Pre-existing |
| Plus 4 additional pre-existing failures in the same set | — | — |

These should be triaged and fixed in their own bug-tracking phase. Out of scope for Phase 51 per executor scope-boundary rule.
