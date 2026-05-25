# Phase 60.4 — Deferred Items

> Out-of-scope discoveries during execution. NOT regressions of any 60.4 plan.
> Per executor SCOPE BOUNDARY (deviation rules): logged here rather than auto-fixed.
> Combined log from Plan 01 and Plan 03 executors (2026-05-07). Both executors independently surfaced the same set of pre-existing failures; entries reconciled below.

---

## Pre-existing environmental test failures (Plan 01 + Plan 03 execution, 2026-05-07)

Verified pre-existing via `git stash` round-trip / revert of plan changes; all failures reproduce on the pre-60.4 baseline. Plan 01 net delta: **+6 passing tests, 0 regressions** (1086 → 1092). Plan 03 quick-loop: **171/171 GREEN** in the GBS-relevant surfaces (`test_gbs_api.py`, `test_gbs_search_dialog.py`, `test_now_playing_panel.py`).

### 1. D-Bus session-bus name collision

- **Test:** `tests/test_media_keys_mpris2.py::test_linux_mpris_backend_constructs`
- **Error:** `RuntimeError: registerService('org.mpris.MediaPlayer2.musicstreamer') failed: name already taken or bus error`
- **Root cause:** A prior MusicStreamer instance (or leftover from earlier dev/test runs) holds the `org.mpris.MediaPlayer2.musicstreamer` D-Bus name on the current dev session bus. Confirmed via `dbus-send --session ... ListNames` showing the name is registered.
- **Fix path (out of scope here):** Either give the test a unique service-name suffix (the file already has a TODO at `mpris2.py:258` about this) or have the test register at a per-PID name. Tracked separately.

### 2. Native Qt/GLib crash mid-suite inside `test_import_dialog_qt`

- **Test module:** `tests/test_import_dialog_qt.py` (somewhere after the 12th test in the module — different runs may abort at slightly different points)
- **Symptom:** `Fatal Python error: Aborted` with PySide6/QtCore stack-frames visible in the trace.
- **Reproduces:** Pre-60.4 baseline — same crash. Module passes 25/25 when run in isolation; only fails under full-suite collection.
- **Root cause hypothesis:** Cross-module Qt event-loop / QApplication-instance state leak from an earlier test module. Unrelated to gbs_api / search dialog / now-playing panel.
- **Fix path (out of scope here):** Audit pytest-qt session-scope usage; possibly add per-test `qtbot` reset or process-isolated test runner for this module.

### 3. `tests/test_station_list_panel.py::test_filter_strip_hidden_in_favorites_mode` — FAIL

Reproducible in isolation; pre-existing on baseline before any 60.4 plan landed.

### 4. `tests/test_station_list_panel.py::test_refresh_recent_updates_list` — FAIL

Reproducible in isolation; pre-existing on baseline before any 60.4 plan landed.

### 5. `tests/test_twitch_auth.py::test_play_twitch_sets_plugin_option_when_token_present` — FAIL

Reproducible in isolation; pre-existing on baseline. No overlap with gbs_api / search dialog / now-playing panel.

### 6. `tests/test_edit_station_dialog.py::test_logo_status_clears_after_3s` — FLAKY (Plan 03 observation)

Passes in isolation, fails when run as part of full-suite. Suggests test interaction (likely a Qt timer / `QTest.qWait` race in a 3-second timeout). Plan 03 does not touch `edit_station_dialog.py`.

---

## Plan-spec grep precision (Plan 01 Task 3 Check 4)

Plan 60.4-01 Task 3 Check 4 specifies:
```
grep -A1 'spec=\[' tests/conftest.py | grep -c 'fetch_user_tokens'
```

`-A1` only emits the line immediately following `spec=[` (which is `"fetch_streams",`), so the count returns `0` even though `"fetch_user_tokens"` IS in the spec list. The intent of the check — confirm the spec list contains the new symbol — is satisfied via `grep -c '"fetch_user_tokens"' tests/conftest.py` (returns `1`) and `grep -A12 'spec=\[' tests/conftest.py | grep -c 'fetch_user_tokens'` (returns `1`). Documented as a plan-spec precision deviation, not a code defect. The conftest extension is correct.

---

## Scope boundary confirmation

| Plan | Touched files | Quick-loop result |
|------|---------------|-------------------|
| 60.4-01 | `musicstreamer/gbs_api.py`, `tests/test_gbs_api.py`, `tests/conftest.py` | 6 GREEN (new TestFetchUserTokens), 0 regressions |
| 60.4-03 | `musicstreamer/ui_qt/now_playing_panel.py`, `tests/test_now_playing_panel.py` | 171 GREEN across 3 GBS test files |

The 6 failures above are unrelated environmental / pre-existing issues. They should be addressed in a future stabilization phase (e.g., Phase 60.5 or a dedicated test-flakiness phase).
