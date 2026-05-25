# Phase 61 — Deferred Items (Out-of-scope discoveries)

Tracked per executor scope boundary rule (do not auto-fix pre-existing issues unrelated to current task).

## Plan 02 deferrals

### `tests/test_media_keys_mpris2.py` integration tests fail when a live MusicStreamer instance owns the MPRIS bus name

- **Found during:** Plan 02 Task 1 verification (running `pytest tests/test_media_keys_mpris2.py -x`).
- **Symptom:** 4 tests fail with `RuntimeError: registerService('org.mpris.MediaPlayer2.musicstreamer') failed: name already taken or bus error`. Affected tests:
  - `test_linux_mpris_backend_constructs`
  - `test_linux_mpris_backend_set_playback_state`
  - `test_linux_mpris_backend_slot_play_pause_emits_signal`
  - `test_linux_mpris_backend_shutdown_idempotent`
  - `test_xesam_title_passthrough_verbatim`
- **Root cause:** A live `musicstreamer` process (PID 68681, ELAPSED 19:52 at the time of the test run) was running on the user's desktop, holding `org.mpris.MediaPlayer2.musicstreamer` on the session bus. The tests re-register the same well-known name on the user's live session bus instead of an isolated bus, so they fail any time another instance is running.
- **Pre-existing:** Yes — these failures would reproduce identically on `main` before Plan 02. The Plan 02 rename does not touch `SERVICE_NAME` (D-04 explicitly preserves it) and the failing tests do not assert on the renamed `DesktopEntry` property value.
- **Action taken:** None (out of scope). The 5 tests that do not register on the live bus all passed.
- **Recommended fix (future phase):** Either spin up a private `dbus-daemon --session` per test (pytest fixture) or wrap the integration tests behind a `pytest.mark.integration` marker that the dev-rig opt-in (`-m integration`) consciously enables — and skip cleanly otherwise. Not a Phase 61 problem.

## Plan 03 deferrals

### `tests/test_station_list_panel.py` — 2 unrelated failures pre-existing on Plan 02's parent commit

- **Found during:** Plan 03 Task 3 full-suite validation gate.
- **Symptom:** Two failures unrelated to Phase 61's surface:
  - `test_filter_strip_hidden_in_favorites_mode`
  - `test_refresh_recent_updates_list`
- **Pre-existing:** Yes — verified by `git stash` + `git checkout d7de853 -- musicstreamer/ tests/` (Plan 02's last commit, parent of Plan 03), then re-running both failing tests. Both fail identically on the pre-Plan-03 tree, so they are not Plan 03 regressions.
- **Plan 03's actual touch surface** (`musicstreamer/desktop_install.py`, `musicstreamer/__main__.py` startup wire-in, `tests/test_*` for desktop_install + ordering) does not interact with the station-list panel. Coincidental co-failure.
- **Recommended fix (future phase):** Triage in a dedicated bug-fix phase if the failures persist; could be a Qt fixture-ordering issue or stale test fixture data. Not a Phase 61 problem.

### Docstring trap on PKG-03 regex

- **Found during:** Plan 03 Task 3 PKG-03 compliance gate.
- **Symptom:** `tests/test_pkg03_compliance.py::test_no_raw_subprocess_in_musicstreamer` failed even after `desktop_install._best_effort` was refactored to call `subprocess_utils._run` instead of bare `subprocess.run`. The PKG-03 regex (`\bsubprocess\.(Popen|run|call)\b`) matched a docstring sentence that mentioned the forbidden API by name to explain why the helper was routing through `subprocess_utils`.
- **Resolution:** Rephrased the docstring to avoid the literal `subprocess.run` token (now reads "bare blocking subprocess calls"). Compliance gate green.
- **Recommended hardening (future phase, optional):** The PKG-03 test's regex skips lines that start with `#` but does not skip docstrings or string literals more generally. A future fix could narrow the test to only flag actual call sites (e.g., by parsing AST instead of grepping). Low priority — the workaround is trivial and the false-positive surfaces immediately.

## Plan 05 deferrals

### `tests/test_import_dialog_qt.py::test_yt_scan_passes_through` aborts the pytest process during teardown

- **Found during:** Plan 05 Task 1 full-suite validation gate (`uv run pytest -q`).
- **Symptom:** `Fatal Python error: Aborted` partway through the test run. C-level stack: three `[logo-fetch-work]` worker threads still inside `ssl.SSLSocket.read` → `_fetch_image_map` (live HTTP fetch from `aa_import.py:69`) when the QApplication tears down. Qt aborts because background QThreads are still running real I/O against destroyed QObjects.
- **Pre-existing:** Yes. Verified by `git stash`-ing Plan 05's `__main__.py` change and re-running the same test set — same abort signature surfaces. Plan 05 only adds an env-strip helper called inside `_run_gui` (never reached by tests, no Qt or test fixture interaction).
- **Action taken:** None (out of scope). Documented for future cleanup.
- **Recommended fix (future phase):** `test_yt_scan_passes_through` (or the underlying `_PlaylistFetchWorker` setup) should mock the network layer rather than performing live HTTPS GETs against image maps; alternatively the test should `qtbot.waitSignal` on worker `finished` before returning so all threads join cleanly before QApplication teardown. Not a Phase 61 problem.

### `tests/test_station_list_panel.py` + `tests/test_twitch_auth.py` — same pre-existing failures as Plan 03

- **Found during:** Plan 05 Task 1 full-suite validation gate.
- **Symptom:** Same `test_filter_strip_hidden_in_favorites_mode`, `test_refresh_recent_updates_list`, plus `test_play_twitch_sets_plugin_option_when_token_present` failures.
- **Pre-existing:** Yes. Verified by `git stash`-ing Plan 05's change and re-running those test files in isolation — identical 3 failures on baseline.
- **Action taken:** None (out of scope). Inherits Plan 03's recommendation.

### `tests/test_media_keys_mpris2.py` — order-dependent flake (1–2 tests in full-suite runs only)

- **Found during:** Plan 05 Task 1 full-suite validation gate.
- **Symptom:** 1–2 mpris-backend tests fail in full-suite runs, but pass when the file is run in isolation. Different test names fail across runs (flake pattern).
- **Pre-existing:** Yes. Same root cause as Plan 02's deferred mpris item (live MPRIS bus name collision with whatever owns the session bus); the order-dependent flavor is just a test-ordering wrinkle on top.
- **Action taken:** None. Same future-phase recommendation as Plan 02 deferred mpris item.
