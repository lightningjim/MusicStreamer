# Phase 60.4 — Deferred Items

> Out-of-scope discoveries during execution. NOT regressions of any 60.4 plan.
> Per executor SCOPE BOUNDARY (deviation rules): logged here rather than auto-fixed.

---

## Pre-existing environmental test failures (Plan 01 execution, 2026-05-07)

While running Plan 01's Task 3 verification gate (`pytest -x`), 4 distinct
test failures surfaced. ALL of them reproduce on the pre-Plan-01 baseline
(verified by reverting `musicstreamer/gbs_api.py`, `tests/test_gbs_api.py`,
and `tests/conftest.py` to `HEAD~2` and re-running). Plan 01's three-file
delta adds exactly 6 passing tests and ZERO regressions
(pass count: 1086 pre → 1092 post — delta of 6 == new `TestFetchUserTokens`).

### Failure 1: D-Bus session-bus name collision

- **Test:** `tests/test_media_keys_mpris2.py::test_linux_mpris_backend_constructs`
- **Error:** `RuntimeError: registerService('org.mpris.MediaPlayer2.musicstreamer') failed: name already taken or bus error`
- **Root cause:** A prior MusicStreamer instance (or leftover from earlier dev/test
  runs) holds the `org.mpris.MediaPlayer2.musicstreamer` D-Bus name on the
  current dev session bus. Confirmed via `dbus-send --session ... ListNames`
  showing the name is registered.
- **Fix path (out of scope here):** Either give the test a unique service-name
  suffix (the file already has a TODO at `mpris2.py:258` about this) or have
  the test register at a per-PID name. Tracked separately.

### Failure 2: Native Qt/GLib crash mid-suite inside test_import_dialog_qt

- **Test module:** `tests/test_import_dialog_qt.py` (somewhere after the 12th
  test in the module — different runs may abort at slightly different points)
- **Symptom:** `Fatal Python error: Aborted` with PySide6/QtCore stack-frames
  visible in the trace.
- **Reproduces:** Pre-Plan-01 baseline — same crash. Module passes 25/25 when
  run in isolation; only fails under full-suite collection.
- **Root cause hypothesis:** Cross-module Qt event-loop / QApplication-instance
  state leak from an earlier test module. Unrelated to gbs_api.
- **Fix path (out of scope here):** Audit pytest-qt session-scope usage; possibly
  add per-test `qtbot` reset or process-isolated test runner for this module.

### Failure 3 + 4 + 5: pre-existing assertion failures

- `tests/test_station_list_panel.py::test_filter_strip_hidden_in_favorites_mode`
- `tests/test_station_list_panel.py::test_refresh_recent_updates_list`
- `tests/test_twitch_auth.py::test_play_twitch_sets_plugin_option_when_token_present`

All three reproduce on the pre-Plan-01 baseline with identical error messages.
They have no overlap with `gbs_api`, the search dialog, the now-playing panel,
or the conftest spec extension. Tracked outside this phase.

---

## Plan-spec grep precision (Task 3 Check 4)

Plan 60.4-01 Task 3 Check 4 specifies:
```
grep -A1 'spec=\[' tests/conftest.py | grep -c 'fetch_user_tokens'
```

`-A1` only emits the line immediately following `spec=[` (which is
`"fetch_streams",`), so the count returns `0` even though
`"fetch_user_tokens"` IS in the spec list. The intent of the check —
confirm the spec list contains the new symbol — is satisfied via
`grep -c '"fetch_user_tokens"' tests/conftest.py` (returns `1`) and
`grep -A12 'spec=\[' tests/conftest.py | grep -c 'fetch_user_tokens'`
(returns `1`). Documented as a plan-spec precision deviation, not a
code defect. The conftest extension is correct.
