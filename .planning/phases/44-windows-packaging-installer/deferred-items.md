# Phase 44 — Deferred Items

Pre-existing test failures observed during Plan 01 execution. Out-of-scope per
GSD scope boundary rule (these failures exist on the plan-base commit and are
not caused by Plan 01 changes).

| Test | File | Notes |
|------|------|-------|
| `test_thumbnail_from_in_memory_stream` | `tests/test_media_keys_smtc.py` | Documented pre-existing blocker per MEMORY.md / STATE.md (MagicMock → AsyncMock fix) |
| `test_filter_strip_hidden_in_favorites_mode` | `tests/test_station_list_panel.py` | Pre-existing on plan-44-01 base (00bdade) |
| `test_play_twitch_sets_plugin_option_when_token_present` | `tests/test_twitch_auth.py` | Pre-existing on plan-44-01 base (00bdade) |

Verification: `git stash; pytest <these tests>` on commit 00bdade reproduces all 3 failures with no Plan 01 changes applied.
