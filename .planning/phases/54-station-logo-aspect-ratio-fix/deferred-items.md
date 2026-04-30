---
phase: 54
plan: 01
created: 2026-04-29
---

# Phase 54 — Plan 01 Deferred Items

## Pre-existing test failures (out of scope)

The full-suite run (`pytest`) reveals 11 pre-existing failures in modules **untouched** by Plan 54-01. Verified pre-existing by reverting `tests/test_art_paths.py` to commit `bc5ad0f` (parent of Task 1) and re-running: **same 11 failures**.

These are not caused by this plan and are out of scope per the executor's SCOPE BOUNDARY rule.

| Test | Module | Suspected category |
|------|--------|--------------------|
| `test_linux_mpris_backend_constructs` | `tests/test_media_keys_mpris2.py` | Linux MPRIS / dbus environment |
| `test_linux_mpris_backend_publish_metadata` | `tests/test_media_keys_mpris2.py` | Linux MPRIS / dbus environment |
| `test_linux_mpris_backend_publish_metadata_none` | `tests/test_media_keys_mpris2.py` | Linux MPRIS / dbus environment |
| `test_linux_mpris_backend_set_playback_state` | `tests/test_media_keys_mpris2.py` | Linux MPRIS / dbus environment |
| `test_linux_mpris_backend_slot_play_pause_emits_signal` | `tests/test_media_keys_mpris2.py` | Linux MPRIS / dbus environment |
| `test_linux_mpris_backend_shutdown_idempotent` | `tests/test_media_keys_mpris2.py` | Linux MPRIS / dbus environment |
| `test_xesam_title_passthrough_verbatim` | `tests/test_media_keys_mpris2.py` | Linux MPRIS / dbus environment |
| `test_thumbnail_from_in_memory_stream` | `tests/test_media_keys_smtc.py` | Windows SMTC backend (likely Linux skip drift) |
| `test_filter_strip_hidden_in_favorites_mode` | `tests/test_station_list_panel.py` | Provider-tree filter UI state |
| `test_refresh_recent_updates_list` | `tests/test_station_list_panel.py` | Recently-Played list refresh |
| `test_play_twitch_sets_plugin_option_when_token_present` | `tests/test_twitch_auth.py` | Twitch auth plugin option |
| `test_logo_status_clears_after_3s` | `tests/test_edit_station_dialog.py` | Timing-sensitive 3s timer (flaky in `-x` runs only) |

(The Plan 03 test_edit_station_dialog timer flake is the one that fired first under `pytest -x`; not deterministic.)

## Why deferred (not fixed in this plan)

Per Plan 54-01's scope (D-09: smallest-diff regression-lock for BUG-05) and CLAUDE.md, none of these modules are in scope. Fixing them would:

1. Violate the smallest-diff principle.
2. Mix unrelated concerns into a regression-lock commit.
3. Risk masking the actual phase verification signal.

## Recommendation

These failures should be triaged in a follow-up phase (or immediate hot-fix) **outside** the Phase 54 scope. The phase 54 verifier can confirm `pytest tests/test_art_paths.py -x` passes and disregard the cross-module failures as pre-existing.
