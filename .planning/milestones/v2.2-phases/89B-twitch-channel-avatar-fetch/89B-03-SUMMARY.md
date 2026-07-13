---
phase: 89B-twitch-channel-avatar-fetch
plan: 03
subsystem: ui_qt / channel-avatar
tags: [twitch, avatar, edit-station-dialog, gap-closure, ART-AVATAR-04]
gap_closure: true
requirements: [ART-AVATAR-04]
dependency_graph:
  requires:
    - "89B-02: Twitch fetcher registry dispatch + provider derivation in _on_save"
    - "89.1: per-provider {provider_id}.png storage + update_provider_avatar_path persist"
  provides:
    - "Synchronous add-path avatar fetch-and-persist in EditStationDialog._on_save (first-save resolution)"
    - "In-memory Station provider_id/provider_name refresh after ensure_provider"
  affects:
    - "EditStationDialog save path for new Twitch (and YouTube) stations"
tech_stack:
  added: []
  patterns:
    - "Synchronous fetch-before-accept (mirrors _AvatarFetchWorker.run inline to avoid teardown race)"
    - "In-memory model refresh after persist for downstream consumer consistency"
key_files:
  created: []
  modified:
    - "musicstreamer/ui_qt/edit_station_dialog.py"
    - "tests/test_twitch_provider_assign.py"
decisions:
  - "[Phase 89B Plan 03]: Add-path fetch is SYNCHRONOUS (not the async _AvatarFetchWorker) — accept()'s _shutdown_avatar_fetch_worker() disconnects the finished signal before the queued slot fires, so an async fetch kicked pre-accept() never persists"
  - "[Phase 89B Plan 03]: In-memory provider refresh (self._station.provider_id/provider_name) runs for BOTH derived-Twitch and manual-provider cases, outside the D-04 blank-provider branch but after ensure_provider"
  - "[Phase 89B Plan 03]: _maybe_fetch_avatar_sync's own provider_id None-check is a distinct save-path call site, NOT a duplicate of the line-1331 Pitfall-7 debounce guard"
metrics:
  tasks: 3
  files_changed: 2
  completed: 2026-06-17
---

# Phase 89B Plan 03: Add-Path Avatar Fetch Gap-Closure Summary

Closes the UAT-discovered add-path gap so a NEW Twitch station fetches and persists the
streamer avatar on the FIRST save — via an in-memory provider refresh plus a synchronous
fetch-and-persist in `_on_save` before `accept()`, no re-edit required.

## What Changed

### Root cause (from `.planning/debug/twitch-avatar-fails-on-new-add.md`)
On a new-station add, `self._station.provider_id` was `None` (placeholder from
`repo.create_station()` with no provider) and was never refreshed in-memory. The debounced
avatar fetch in `_on_url_timer_timeout` is gated on `provider_id is None` (Pitfall-7 guard,
line 1331), so it was skipped on the add path. `_on_save` derived and persisted `provider_id`
via `repo.ensure_provider` (line 1706) but never refreshed `self._station.provider_id` nor
triggered a fetch before `accept()`. On re-edit, `get_station()` rehydrated `provider_id` from
the DB, so the gate passed and the fetch fired — explaining why edit worked but first-add did not.

### Fix (`musicstreamer/ui_qt/edit_station_dialog.py`)
- **In-memory provider refresh:** immediately after `provider_id = repo.ensure_provider(provider_name)`,
  assign `self._station.provider_id = provider_id` and `self._station.provider_name = provider_name`.
  Runs for both the derived-Twitch and manual-provider cases; placed after `ensure_provider`, outside
  the D-04 `if not provider_name:` block.
- **Synchronous fetch-and-persist:** new private helper `_maybe_fetch_avatar_sync(url, provider_id)`
  called from `_on_save` before `self.accept()`. It mirrors `_AvatarFetchWorker.run()` inline:
  no-op if `provider_id is None`; URL-sniff gate (`youtube.com`/`youtu.be`/`twitch.tv`); D-07 reuse
  gate (skip if `provider_avatar_path` set and not `_force_avatar_refresh`); registry dispatch
  (`twitch` vs `youtube`, node_runtime only for YouTube); persist via
  `assets.write_provider_avatar(provider_id, data)` + `repo.update_provider_avatar_path(...)`;
  sets `self._station.provider_avatar_path`. Wrapped in `try/except Exception` (non-blocking, D-07)
  and a wait cursor.

It is a synchronous helper, not the async worker, because `accept()` →
`_shutdown_avatar_fetch_worker()` disconnects the `finished` signal and bounded-waits before the
queued `finished->_on_avatar_fetched` slot can run, so an async fetch kicked right before `accept()`
would never persist.

### Tests (`tests/test_twitch_provider_assign.py`)
Six new tests appended to the existing mocked-repo + qtbot harness (headless, no live token):
- `test_save_add_path_fetches_avatar` — first-save dispatch + `write_provider_avatar(9, b"PNGDATA")`
  + `update_provider_avatar_path(9, "...9.png")`.
- `test_save_add_path_refreshes_in_memory_provider` — `provider_id == 9`, `provider_name == "Twitch: twitchdev"`.
- `test_save_existing_provider_with_avatar_no_refetch` — D-07 reuse gate, no network, no persist.
- `test_save_manual_provider_not_overwritten_still_holds` — D-04, fetch keys on manual provider_id.
- `test_save_fetch_failure_is_nonblocking` — `RuntimeError` swallowed, `_save_succeeded` True, no persist.
- `test_on_save_has_inmemory_provider_assignment` — source drift-guard (non-comment, after ensure_provider).

## TDD Cycle
- **RED** (commit `6055a07c`): 3 of 6 new tests fail against the unfixed `_on_save` (fetch, in-memory
  refresh, drift-guard); the 3 gated tests pass vacuously; 4 existing tests still pass.
- **GREEN** (commit `29575e49`): all 13 tests in the file pass; avatar-dialog suite passes.

## Invariants Verified (by grep)
- D-04 blank-provider guard at line 1699 untouched; `f"Twitch: {_login}"` derivation stays inside `if not provider_name:`.
- Pitfall-7 single `provider_id is None` guard at line 1331 untouched and NOT duplicated.
- Per-provider `{provider_id}.png` keying unchanged (`write_provider_avatar(provider_id, data)`).

## Deviations from Plan

None - plan executed exactly as written.

## Tasks

| Task | Name | Type | Commit |
| ---- | ---- | ---- | ------ |
| 1 | Add-path RED tests | test (tdd) | 6055a07c |
| 2 | In-memory provider refresh + synchronous fetch-and-persist | feat (tdd) | 29575e49 |
| 3 | Regression sweep (edit-path + avatar + provider-assign + twitch_helix) | verify-only | (no code change) |

## Test Results
- `tests/test_twitch_provider_assign.py` + `tests/test_edit_station_dialog_avatar.py`: 13 passed.
- `tests/test_edit_station_dialog_avatar.py` + `tests/test_twitch_provider_assign.py` + `tests/test_twitch_helix.py`: 21 passed.
- `tests/test_edit_station_dialog.py`: 96 passed (2 benign warnings, no failures; the documented
  pre-existing failures did not surface in this focused run).

## Self-Check: PASSED

- SUMMARY.md present
- Commit 6055a07c (RED tests) present
- Commit 29575e49 (implementation) present
- `self._station.provider_id = provider_id` present in edit_station_dialog.py
