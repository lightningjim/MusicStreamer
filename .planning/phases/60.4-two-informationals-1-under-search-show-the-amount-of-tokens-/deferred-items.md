# Phase 60.4 — Deferred Items

> Out-of-scope test failures and environmental issues discovered during plan execution.
> Per `<deviation_rules>` SCOPE BOUNDARY: pre-existing failures in unrelated files are NOT fixed by Plan 03 — they are logged here for a future phase.

---

## Pre-existing flaky / failing tests (NOT caused by Plan 03)

Discovered during full-suite run after Task 2 of Plan 03. Verified pre-existing via `git stash` round-trip on the prior commit; all failures reproduced before Plan 03's production-code change landed.

### 1. `tests/test_station_list_panel.py::test_filter_strip_hidden_in_favorites_mode` — FAIL

Reproducible in isolation: `pytest tests/test_station_list_panel.py` fails this test even on the commit before Task 2's production code change.

### 2. `tests/test_station_list_panel.py::test_refresh_recent_updates_list` — FAIL

Reproducible in isolation: `pytest tests/test_station_list_panel.py` fails this test even on the commit before Task 2's production code change.

### 3. `tests/test_twitch_auth.py::test_play_twitch_sets_plugin_option_when_token_present` — FAIL

Reproducible in isolation: `pytest tests/test_twitch_auth.py` fails this test even on the commit before Task 2's production code change.

### 4. `tests/test_edit_station_dialog.py::test_logo_status_clears_after_3s` — FLAKY

Passes in isolation, fails when run as part of full-suite. Suggests test interaction (likely a Qt timer / `QTest.qWait` race in a 3-second timeout). Plan 03 does not touch `edit_station_dialog.py`.

### 5. Fatal Python crash in `tests/test_import_dialog_qt.py` (during full-suite run) — ENVIRONMENTAL

`Fatal Python error: Aborted` mid-collection of `test_import_dialog_qt.py`. Suggests Qt/PySide6 lifecycle issue when running the entire suite back-to-back. Plan 03 does not touch any import-dialog code.

---

## Scope boundary confirmation

Plan 03 touched ONLY:
- `musicstreamer/ui_qt/now_playing_panel.py` — single 5-line guarded `addItem` insertion
- `tests/test_now_playing_panel.py` — 1 polarity flip + 4 new tests

The Plan 03 quick-loop (`pytest tests/test_gbs_api.py tests/test_gbs_search_dialog.py tests/test_now_playing_panel.py`) returns **171 passed** — no regression in any GBS-related surface.

The above 5 failures are unrelated environmental / pre-existing issues. They should be addressed in a future stabilization phase (e.g., Phase 60.5 or a dedicated test-flakiness phase).
