---
phase: 44
plan: 03
subsystem: windows-packaging-installer
tags: [single-instance, node-detection, main-window, toast, hamburger-menu]
requires:
  - musicstreamer.single_instance.acquire_or_forward (44-02)
  - musicstreamer.single_instance.raise_and_focus (44-02)
  - musicstreamer.runtime_check.check_node (44-02)
  - musicstreamer.runtime_check.show_missing_node_dialog (44-02)
  - musicstreamer.runtime_check.NodeRuntime (44-02)
provides:
  - musicstreamer.__main__::_run_gui — single-instance + Node.js wiring
  - musicstreamer.ui_qt.main_window.MainWindow.__init__(*, node_runtime=None)
  - musicstreamer.ui_qt.main_window.MainWindow._on_node_install_clicked
  - hamburger-menu Node-missing QAction (D-13 part 3)
  - YT-fail Node-install toast branch (D-13 part 2)
affects:
  - musicstreamer/__main__.py
  - musicstreamer/ui_qt/main_window.py
  - musicstreamer/runtime_check.py
  - tests/test_main_window_integration.py
tech-stack:
  added: []
  patterns:
    - "Lazy import inside _run_gui (matches existing __main__.py:133-141 idiom)"
    - "Parameter-only lambda for activate_requested → raise_and_focus(window) — no self capture"
    - "Keyword-only kwarg expansion to preserve back-compat test callers"
    - "Module-level enum capture to insulate against test monkeypatching of QMessageBox"
key-files:
  created: []
  modified:
    - musicstreamer/__main__.py
    - musicstreamer/ui_qt/main_window.py
    - musicstreamer/runtime_check.py
    - tests/test_main_window_integration.py
    - .planning/phases/44-windows-packaging-installer/deferred-items.md
decisions:
  - "Inserted single-instance check after QApplication construction and before MainWindow (D-10) — required for QLocalServer event-loop binding."
  - "Added keyword-only node_runtime kwarg with default None to preserve back-compat with the 30+ existing tests that construct MainWindow positionally without it."
  - "Captured QMessageBox.Icon.Warning / ButtonRole.* enums at runtime_check module import to make show_missing_node_dialog robust against the Plan 01 test fake that replaces QMessageBox."
  - "Added inverse-case integration test (test_yt_fail_toast_uses_generic_when_node_present) beyond the spec to lock in that the Node-install toast does NOT fire when Node is available."
metrics:
  duration_seconds: 269
  tasks_completed: 2
  files_changed: 5
  tests_added: 3
  completed_at: "2026-04-25T16:25:06Z"
---

# Phase 44 Plan 03: Wire Single-Instance + Node-Detection into Entry Point and Main Window — Summary

Single-line: Wired Plan 02's `single_instance` and `runtime_check` modules into `_run_gui` and added a `node_runtime` kwarg, hamburger-menu indicator, and YT-fail Node-install toast branch to MainWindow — turning Plan 01's RED widget tests GREEN.

## Tasks Executed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Wire single_instance + runtime_check into _run_gui | `78e8ece` | `musicstreamer/__main__.py` |
| 2 | MainWindow node_runtime kwarg + hamburger indicator + YT-fail toast + integration tests | `f1b03cd` | `musicstreamer/ui_qt/main_window.py`, `tests/test_main_window_integration.py`, `musicstreamer/runtime_check.py` |
| — | Deferred-items log (pre-existing failures) | `2bd0e41` | `.planning/phases/44-windows-packaging-installer/deferred-items.md` |

## Implementation Notes

### `__main__.py::_run_gui`

The plan's Pattern from PATTERNS.md was applied verbatim:

1. After the `if sys.platform == "win32":` Fusion + palette block, before `db_connect()`, the new wiring:
   - `from musicstreamer import single_instance` (lazy)
   - `server = single_instance.acquire_or_forward()`; if `None` → `return 0`.
   - `from musicstreamer import runtime_check` (lazy)
   - `node_runtime = runtime_check.check_node()`; if `not .available` → `runtime_check.show_missing_node_dialog(parent=None)`.
2. `MainWindow(player, repo, node_runtime=node_runtime)` — kwarg added.
3. `server.activate_requested.connect(lambda: single_instance.raise_and_focus(window))` — parameter-only lambda capturing `window` (module-scope code, not a method, so the lambda does not violate QA-05's no-self-capture rule).

`_run_smoke`, `_apply_windows_palette`, `_set_windows_aumid`, `main()`, `DEFAULT_SMOKE_URL` were left untouched. Verified: `tests/test_headless_entry.py` still passes.

### `MainWindow`

- Constructor signature now: `__init__(self, player, repo, *, node_runtime=None, parent=None)`. The `*,` keyword-only barrier is what makes back-compat work — every existing test call site `MainWindow(player, repo)` continues to work; the new kwarg is opt-in.
- `self._node_runtime = node_runtime` stored after `self._repo = repo`.
- Hamburger menu indicator inserted AFTER the worker-reference-retention lines (the existing Group 3 boundary), preserving menu order. Surfaces only when `node_runtime is not None and not node_runtime.available`. Action text is the literal `"⚠ Node.js: Missing (click to install)"` — Plan 01's contract is `"Node.js: Missing"` substring match.
- New `_on_node_install_clicked` handler opens `https://nodejs.org/en/download` via `QDesktopServices`.
- `_on_playback_error` extended with an early-return branch: when Node is missing AND `"YouTube resolve failed"` is in the message → `show_toast("Install Node.js for YouTube playback")` and return. Generic truncation path is unchanged for all other cases.

### Tests Added

Three tests added to `tests/test_main_window_integration.py`:

1. `test_yt_fail_toast_when_node_missing` — emits `playback_error("YouTube resolve failed: ...")` with `node_runtime=NodeRuntime(False, None)`, asserts `show_toast` called with `"Install Node.js for YouTube playback"`.
2. `test_yt_fail_toast_uses_generic_when_node_present` — inverse case: with `node_runtime` available, asserts the same message routes to the generic `"Playback error: ..."` toast (no Node nudge).
3. `test_player_emits_expected_yt_failure_prefix` — issue-4 regression guard: greps `musicstreamer/player.py` for the literal `playback_error.emit("YouTube resolve failed:` so MainWindow's substring check stays in lockstep with Player.

## Verification

- `python -m py_compile` on both edited modules: PASS
- `pytest tests/ui_qt/test_main_window_node_indicator.py`: 2/2 PASS (Plan 01 RED tests now GREEN)
- `pytest tests/ui_qt/test_missing_node_dialog.py`: 1/1 PASS (auto-fix landed; see deviations)
- `pytest tests/test_runtime_check.py`: 3/3 PASS
- `pytest tests/test_single_instance.py`: 3/3 PASS
- `pytest tests/test_main_window_integration.py`: 40/40 PASS (37 existing + 3 new)
- `pytest tests/test_headless_entry.py`: 1/1 PASS (smoke path unchanged)
- Plan-spec verification suite combined: **49/49 PASS**
- `python tools/check_subprocess_guard.py`: PKG-03 OK (zero bare subprocess calls)
- Full repo `pytest -q`: 784 pass, 1 skipped, 3 failed (all 3 pre-existing on base commit; see Deferred Issues)

### Acceptance Criteria Cross-check

Task 1 (all PASS):
- `python -m py_compile musicstreamer/__main__.py` exits 0 — confirmed
- `grep -c 'single_instance' musicstreamer/__main__.py` ≥ 2 — 4 hits
- `grep -c 'runtime_check' musicstreamer/__main__.py` ≥ 2 — 3 hits
- `if server is None:` + `return 0` — confirmed at lines 154-155
- `show_missing_node_dialog(parent=None)` — line 163
- `MainWindow(player, repo, node_runtime=node_runtime)` — line 170
- `server.activate_requested.connect` — line 171
- `lambda: single_instance.raise_and_focus(window)` — line 172
- Order check: line 153 (acquire_or_forward) < 161 (check_node) < 170 (MainWindow) — confirmed
- `_run_smoke` body unchanged — confirmed via diff (no edits in lines 17-64)

Task 2 (all PASS):
- `node_runtime=None` in signature — line 108
- `self._node_runtime = node_runtime` — line 115
- `Node.js: Missing (click to install)` — line 187
- `_on_node_install_clicked` defined — line 363
- `Install Node.js for YouTube playback` — line 358
- `YouTube resolve failed` matched in `_on_playback_error` — line 356
- `nodejs.org` URL — line 368
- Plan 01 hamburger tests both PASS
- All integration tests PASS including 3 new
- Issue 4 regression guard test PASS — `musicstreamer/player.py:557` matches `playback_error.emit(f"YouTube resolve failed:`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `runtime_check.show_missing_node_dialog` AttributeError under Plan 01 test fake**

- **Found during:** Task 2 — when running `pytest tests/ui_qt/test_missing_node_dialog.py` per the plan's verification.
- **Issue:** `show_missing_node_dialog` referenced `QMessageBox.Icon.Warning`, `QMessageBox.ButtonRole.ActionRole`, `QMessageBox.ButtonRole.AcceptRole` lazily inside the function body. Plan 01's test (`tests/ui_qt/test_missing_node_dialog.py::test_dialog_has_open_and_ok_buttons`) replaces `runtime_check.QMessageBox` at module scope with a fake that does not expose the `Icon` or `ButtonRole` enums — so the lazy lookup raised `AttributeError`. Confirmed pre-existing via `git stash` on the Wave-1 base commit `a598aca`; Plan 02's SUMMARY explicitly says they substituted greps for this test in their isolated worktree, so the integration regression only surfaces post-merge.
- **Fix:** Added module-level captures `_ICON_WARNING`, `_ROLE_ACTION`, `_ROLE_ACCEPT` resolved at import time against the real `PySide6.QtWidgets.QMessageBox`. `show_missing_node_dialog` now uses the captured constants. Test fake's `addButton(text, role)` accepts any role object, so the captured PySide6 enum values pass through correctly.
- **Files modified:** `musicstreamer/runtime_check.py` (lines 22-31 added; 69, 76, 77 changed).
- **Commit:** `f1b03cd` (folded into Task 2 commit since the runtime_check edit was unblocking the verification gate).

### Auth gates

None.

## Threat Flags

None — no new network endpoints, schema changes, or auth paths introduced. The existing `_on_node_install_clicked` opens a hardcoded HTTPS URL (`https://nodejs.org/en/download`) via the user's default browser; the URL is a literal constant, not user-derived.

## Threat Surface — STRIDE Mitigations Applied

- **T-44-03-01 (T)** — Wiring order regression mitigated: line-order acceptance criteria all pass; `__main__.py` wiring block carries explicit `D-10` / `D-11` / `D-12` comments naming the ordering invariant.
- **T-44-03-02 (I)** — Player error truncation logic preserved unchanged; the new Node-missing branch returns a fixed string (no message echo), so it cannot leak credentials.
- **T-44-03-03 (S)** — accepted per the plan's risk register.

## Deferred Issues

Three pre-existing test failures exist on the base commit `a598aca` (verified via `git stash` + run; not introduced by Plan 03):

1. `tests/test_media_keys_smtc.py::test_thumbnail_from_in_memory_stream`
2. `tests/test_station_list_panel.py::test_filter_strip_hidden_in_favorites_mode`
3. `tests/test_twitch_auth.py::test_play_twitch_sets_plugin_option_when_token_present`

Logged at `.planning/phases/44-windows-packaging-installer/deferred-items.md` for triage. These do not block Plan 03 success criteria (which scoped to the explicit verification suite of 49 tests, all PASS).

## TDD Gate Compliance

Plan 03 is `type: execute` (not `type: tdd`), but tasks have `tdd="true"`:

- Plan 01's RED tests were already in place on the base commit (`tests/ui_qt/test_main_window_node_indicator.py` — 2 failing). Wave 0 + Plan 02 work satisfies the RED gate for Plan 03.
- Task 1 commit (`78e8ece`) is `feat(...)` — GREEN gate landed (made the entry-point behavior live).
- Task 2 commit (`f1b03cd`) is `feat(...)` — GREEN gate for hamburger indicator + toast (turned Plan 01's RED tests GREEN; added 3 new tests that pass on first run, matching the consolidated GREEN-on-arrival pattern Wave 2 plans use when the RED tests already exist upstream).
- No REFACTOR commit — none needed.

## Self-Check

Files claimed created/modified all verified to exist and contain the asserted content:

- `[FOUND]` musicstreamer/__main__.py (modified, lines 152-173 contain new wiring)
- `[FOUND]` musicstreamer/ui_qt/main_window.py (modified, kwarg + indicator + handler + toast branch all present)
- `[FOUND]` musicstreamer/runtime_check.py (modified, _ICON_WARNING/_ROLE_ACTION/_ROLE_ACCEPT captures present)
- `[FOUND]` tests/test_main_window_integration.py (modified, 3 new tests appended)
- `[FOUND]` .planning/phases/44-windows-packaging-installer/deferred-items.md (created)

Commits asserted all present in `git log --oneline`:

- `[FOUND]` 78e8ece — Task 1
- `[FOUND]` f1b03cd — Task 2
- `[FOUND]` 2bd0e41 — Deferred-items log

## Self-Check: PASSED
