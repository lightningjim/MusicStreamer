---
phase: 44-windows-packaging-installer
plan: 01
subsystem: testing
tags: [pytest, pytest-qt, pyinstaller, pkg-03, runtime-01, build-tooling, scaffolding]

# Dependency graph
requires:
  - phase: 35-yt-dlp
    provides: subprocess_utils.py legitimate site (PKG-03 retired all bare subprocess calls)
  - phase: 41-media-keys
    provides: tests/test_media_keys_scaffold.py qtbot + monkeypatch idiom (analog source)
  - phase: 43-gstreamer-windows-spike
    provides: 43-spike.spec / build.ps1 source artifacts (referenced by build-time guards)
provides:
  - tools/check_subprocess_guard.py (build-time PKG-03 guard, exit code 4 per D-22)
  - tools/check_spec_entry.py (build-time .spec entry-point guard, exit code 7)
  - tests/test_pkg03_compliance.py (cross-platform Python regression of build.ps1 ripgrep)
  - tests/test_spec_hidden_imports.py (PKG-01 .spec content guard, skipped until Plan 04)
  - tests/test_single_instance.py (RED scaffold for QLocalServer round-trip + activate forwarding)
  - tests/test_runtime_check.py (RED scaffold for NodeRuntime detection contract)
  - tests/ui_qt/test_main_window_node_indicator.py (RED scaffold for hamburger conditional QAction)
  - tests/ui_qt/test_missing_node_dialog.py (RED scaffold for dialog button-wiring contract)
affects: [44-02 (single_instance + runtime_check modules), 44-03 (MainWindow Node-indicator wiring), 44-04 (.spec activation), 44-05 (Inno Setup + build.ps1 PKG-03 step)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lazy-import-inside-test idiom for RED scaffolds (collection green, execution RED)"
    - "Pure-Python grep guards mirroring build.ps1 PowerShell guards (cross-platform feedback)"
    - "Build-tool exit code conventions: 4=PKG-03, 7=PKG-01 (matches D-22 / RESEARCH §Pattern 5)"

key-files:
  created:
    - tools/__init__.py
    - tools/check_subprocess_guard.py
    - tools/check_spec_entry.py
    - tests/test_pkg03_compliance.py
    - tests/test_spec_hidden_imports.py
    - tests/test_single_instance.py
    - tests/test_runtime_check.py
    - tests/ui_qt/__init__.py
    - tests/ui_qt/test_main_window_node_indicator.py
    - tests/ui_qt/test_missing_node_dialog.py
    - .planning/phases/44-windows-packaging-installer/deferred-items.md
  modified: []

key-decisions:
  - "Test imports of musicstreamer.single_instance / runtime_check moved INSIDE each test function (lazy) — keeps `pytest --collect-only` count ≥ 8 (plan verify) while preserving RED-on-execute semantics until Plan 02 lands the modules."
  - "FakePlayer/FakeRepo doubles inlined in tests/ui_qt/test_main_window_node_indicator.py rather than imported from tests/test_main_window_integration.py — avoids cross-test fixture coupling and keeps tests/ui_qt/ self-contained."
  - "FakeBox dialog-recording double used for tests/ui_qt/test_missing_node_dialog.py (monkeypatched onto runtime_check.QMessageBox) — short-circuits modal exec() so the test runs headless without Qt deadlocks."

patterns-established:
  - "Build-time guard pattern: tools/check_*.py scripts return canonical exit codes that build.ps1 forwards to its overall exit code (Pattern 5 in 44-RESEARCH.md)."
  - "Cross-platform compliance test pattern: pure-Python regex grep using pathlib.rglob, mirrors build-time PowerShell guards so the same invariant is enforced on Linux dev machines and the Windows build VM."
  - "RED scaffold pattern for Wave-0/Wave-1 multi-plan coordination: top-of-module imports stay restricted to existing modules; references to modules landed by later plans (this case: musicstreamer.single_instance, musicstreamer.runtime_check) move into per-test lazy imports."

requirements-completed: [PKG-03, PKG-04, QA-03]

# Metrics
duration: 22min
completed: 2026-04-25
---

# Phase 44 Plan 01: Wave 0 Test Scaffolds + Build-Time Guards Summary

**7 RED test scaffolds + 2 build-time guard tools land Wave 0 contracts (SERVER_NAME, NodeRuntime shape, "Node.js: Missing" QAction text, .spec hiddenimports list) so Plans 02–05 have a single feedback loop.**

## Performance

- **Duration:** 22 min
- **Started:** 2026-04-25T15:38:00Z (approx)
- **Completed:** 2026-04-25T16:00:25Z
- **Tasks:** 2 / 2
- **Files created:** 11 (10 source/test + 1 deferred-items.md)
- **Files modified:** 0

## Accomplishments

- PKG-03 compliance is now enforced as a Python test (cross-platform — runs on Linux dev too, mirroring the build.ps1 ripgrep guard) plus a standalone tools/check_subprocess_guard.py callable from build.ps1.
- PKG-01 .spec content guard scaffolded with pytest.skip until Plan 04 lands packaging/windows/MusicStreamer.spec; no hard ordering dependency between Plan 01 and Plan 04.
- Wave 0 contracts locked: SERVER_NAME, _CONNECT_TIMEOUT_MS, NodeRuntime dataclass shape (available, path), `_which_node()` win32 preference for node.exe, "Node.js: Missing (click to install)" menu text, "Open nodejs.org" + "OK" dialog buttons.
- 8 tests collected, 1 passes (PKG-03), 1 skipped (spec guard pre-Plan-04), 6 RED-scaffolded for Plan 02/03 to turn green.

## Task Commits

1. **Task 1: Create build-time tooling + PKG-03 / spec guards** — `257fd9d` (test)
2. **Task 2: Create RED test scaffolds for single_instance + runtime_check + Node UI** — `2e51ae1` (test)

_Note: This is a TDD plan — both commits are `test(...)`. Plan 02 will land the matching `feat(...)` commits that turn the RED scaffolds GREEN._

## Files Created

- `tools/__init__.py` — package marker for tools/
- `tools/check_subprocess_guard.py` — build-time PKG-03 guard (D-22). Walks musicstreamer/, regex-greps for `\bsubprocess\.(Popen|run|call)\b`, excludes subprocess_utils.py by literal filename per T-44-01-01 disposition. Exits 4 on any hits, 0 clean. Skips comment lines.
- `tools/check_spec_entry.py` — build-time .spec entry-point guard (PKG-01). Asserts packaging/windows/MusicStreamer.spec contains the canonical entry literal `"../../musicstreamer/__main__.py"`. Exits 7 on missing entry, 0 on found OR on .spec absent (so Plan 01 doesn't block on Plan 04).
- `tests/test_pkg03_compliance.py` — pure-Python regex grep over musicstreamer/, mirrors the build.ps1 ripgrep guard semantically. Currently passes (Plan 35-06 retired all bare subprocess uses).
- `tests/test_spec_hidden_imports.py` — asserts the .spec contains all canonical hiddenimports + entry + EXE attributes (`PySide6.QtNetwork`, `PySide6.QtSvg`, `winrt.windows.media`, `winrt.windows.media.playback`, `name="MusicStreamer"`, `console=False`, `upx=False`, `icon="icons/MusicStreamer.ico"`). Skipped until Plan 04 lands the file.
- `tests/test_single_instance.py` — 2 tests: first-instance acquires server bound to monkeypatched SERVER_NAME; second-instance acquire returns None and the first instance's `activate_requested` Signal fires (validated via `qtbot.waitSignal(timeout=1000)`). Per-test unique SERVER_NAME prevents named-pipe / unix-socket collisions in parallel runs.
- `tests/test_runtime_check.py` — 3 tests: `check_node()` returns NodeRuntime(available=True, path) on detection; returns NodeRuntime(False, None) on absence; `_which_node()` on win32 prefers `node.exe` per CPython issue #109590 guard.
- `tests/ui_qt/__init__.py` — package marker for tests/ui_qt/.
- `tests/ui_qt/test_main_window_node_indicator.py` — 2 tests: hamburger menu lacks any "Node.js" entry when node available; hamburger contains "Node.js: Missing" entry when absent. Inlines minimal FakePlayer (QObject with the 7 Player signals: title_changed, failover, offline, playback_error, cookies_cleared, elapsed_updated, buffer_percent) + FakeRepo doubles.
- `tests/ui_qt/test_missing_node_dialog.py` — 1 test: dialog wires "Open nodejs.org" + "OK" buttons via QMessageBox.addButton. Uses a `_FakeBox` recording double monkeypatched onto `runtime_check.QMessageBox` to short-circuit `exec()` (no headless Qt modal blocking).
- `.planning/phases/44-windows-packaging-installer/deferred-items.md` — log of 3 pre-existing test failures verified reproducible on plan-base commit (out of scope per Plan 01 boundary).

## Decisions Made

- **Lazy imports for RED scaffolds**: The plan's verify command (`pytest --collect-only ... | grep ... | wc -l ≥ 8`) requires successful test collection, but the `<done>` clause specifies tests must fail with ImportError on `from musicstreamer import single_instance / runtime_check`. Module-level imports of nonexistent modules raise during collection and yield 0 collected tests. Resolved by moving the `from musicstreamer import ...` lines INSIDE each test function — collection succeeds (8 tests visible to pytest), execution still RED-fails on the first import call inside each test. This is also a documented patterns ("RED scaffold pattern for Wave-0/Wave-1 multi-plan coordination") that future Wave 0 plans can apply.
- **Inlined FakePlayer/FakeRepo doubles** in tests/ui_qt/test_main_window_node_indicator.py rather than importing from tests/test_main_window_integration.py. Keeps tests/ui_qt/ a self-contained package with no cross-test-module fixture coupling. Plan referenced "main_window_factory fixture from conftest.py if present; otherwise construct MainWindow directly" — the factory does not exist, so direct construction was used.
- **FakeBox QMessageBox double** instead of monkeypatching `QMessageBox.exec`: the recording fake also captures `addButton(text, role)` invocations, which is exactly what the dialog contract test asserts on. Cleaner than introspecting a real QMessageBox post-exec.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Reconciled conflicting `<verify>` and `<done>` criteria for Task 2**

- **Found during:** Task 2 (after writing the RED scaffolds with module-level `from musicstreamer import single_instance / runtime_check` per the plan's `<action>` block)
- **Issue:** The plan's `<verify><automated>` requires `pytest --collect-only ... | grep -E '^tests/.*::test_' | wc -l ≥ 8`, but module-level imports of nonexistent modules cause ImportError during collection — pytest collects 0 tests, fails the verify command. Meanwhile the `<done>` clause says "tests fail with ImportError on `from musicstreamer import single_instance` / `runtime_check` (expected RED — Plan 02 lands the imports)" — the `<done>` clause expects RED at execute time, not at collection time.
- **Fix:** Moved each `from musicstreamer import single_instance` / `from musicstreamer import runtime_check` / `from musicstreamer.runtime_check import NodeRuntime` line into the test function body (lazy import). Collection now succeeds (8 tests visible) and execution still RED-fails on the lazy import inside each test until Plan 02 lands the modules. This honors both the verify count and the RED-on-execute intent.
- **Files modified:** tests/test_single_instance.py, tests/test_runtime_check.py, tests/ui_qt/test_main_window_node_indicator.py, tests/ui_qt/test_missing_node_dialog.py
- **Verification:** `pytest tests/test_single_instance.py tests/test_runtime_check.py tests/ui_qt/test_main_window_node_indicator.py tests/ui_qt/test_missing_node_dialog.py --collect-only -q | grep -E '^tests/.*::test_' | wc -l` → 8.
- **Committed in:** `2e51ae1` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking, no scope creep)
**Impact on plan:** The fix is mechanical and preserves every interface contract the plan locked in. It also documents a reusable pattern ("RED scaffold pattern for Wave-0 multi-plan coordination") for future GSD work where Wave 0 must scaffold tests for code that lands in a later wave.

## Issues Encountered

- **Pre-existing test failures (out of scope, logged):** During the broader `pytest -q` regression check, three tests failed: `test_thumbnail_from_in_memory_stream` (test_media_keys_smtc.py), `test_filter_strip_hidden_in_favorites_mode` (test_station_list_panel.py), `test_play_twitch_sets_plugin_option_when_token_present` (test_twitch_auth.py). Verified all three reproduce on the plan-base commit `00bdade` with no Plan 01 changes applied (`git stash; pytest …`). The first is a known blocker tracked in MEMORY.md (`MagicMock → AsyncMock` fix). All three are out of Plan 01 scope per the GSD scope-boundary rule and are logged in `.planning/phases/44-windows-packaging-installer/deferred-items.md`.

## TDD Gate Compliance

This plan is structured as `tdd="true"` per task. The complete RED→GREEN cycle for these scaffolds spans Plans 01→02:

- **RED gate (Plan 01):** test commits `257fd9d` (PKG-03 + spec guards) + `2e51ae1` (single_instance + runtime_check + Node UI scaffolds). 1 test passes (PKG-03), 1 skipped (spec guard inactive pre-Plan-04), 6 RED-fail at execute (lazy imports for missing musicstreamer.single_instance / runtime_check modules).
- **GREEN gate:** lands in Plan 02 when musicstreamer/single_instance.py and musicstreamer/runtime_check.py are implemented. Plan 03 turns the two ui_qt tests GREEN by adding the `node_runtime` kwarg + conditional QAction to MainWindow.
- **REFACTOR gate:** N/A this plan (pure scaffolding).

## Self-Check

- [x] tools/__init__.py exists
- [x] tools/check_subprocess_guard.py exists, exits 0 on current tree, exits 4 on offenders
- [x] tools/check_spec_entry.py exists, exits 0 (notice — spec not yet created)
- [x] tests/test_pkg03_compliance.py exists, 1 PASS
- [x] tests/test_spec_hidden_imports.py exists, 1 SKIP (spec absent)
- [x] tests/test_single_instance.py exists, 2 tests collected, contains `monkeypatch.setattr(single_instance, "SERVER_NAME"...)` + `qtbot.waitSignal`
- [x] tests/test_runtime_check.py exists, 3 tests collected, contains `NodeRuntime(available=True` + `node.exe`
- [x] tests/ui_qt/__init__.py exists
- [x] tests/ui_qt/test_main_window_node_indicator.py exists, 2 tests collected, contains `Node.js: Missing`
- [x] tests/ui_qt/test_missing_node_dialog.py exists, 1 test collected
- [x] Total `pytest --collect-only` over the four scaffold files = 8
- [x] Commits 257fd9d and 2e51ae1 present in git log
- [x] No production-code changes (pure scaffolding)
- [x] No modifications to STATE.md or ROADMAP.md (worktree mode)

## Self-Check: PASSED

## Next Phase Readiness

- **Plan 02 unblocked.** All Wave 0 contracts are locked. Plan 02 implementer can:
  - Land `musicstreamer/single_instance.py` with `SERVER_NAME = "org.lightningjim.MusicStreamer.single-instance"`, `_CONNECT_TIMEOUT_MS = 500`, `acquire_or_forward() -> Optional[SingleInstanceServer]`, `SingleInstanceServer.activate_requested: Signal()`, `SingleInstanceServer.close()`, `raise_and_focus(window)`. Tests turn GREEN immediately on import success + signal round-trip.
  - Land `musicstreamer/runtime_check.py` with `NODEJS_INSTALL_URL`, `@dataclass(frozen=True) class NodeRuntime(available: bool, path: Optional[str])`, `_which_node()` (win32 prefers node.exe), `check_node() -> NodeRuntime`, `show_missing_node_dialog(parent)` constructing a QMessageBox with "Open nodejs.org" + "OK" buttons.
- **Plan 03 unblocked.** MainWindow contract: add `*, node_runtime: NodeRuntime | None = None` keyword-only kwarg; when `node_runtime is not None and not node_runtime.available`, append a separator + QAction with text `"⚠ Node.js: Missing (click to install)"` to `self._menu`. Test `test_hamburger_indicator_present_when_node_missing` will pass once that wiring is in.
- **Plan 04 unblocked.** When packaging/windows/MusicStreamer.spec lands, `tests/test_spec_hidden_imports.py` automatically activates (no longer skipped) and asserts the 9 canonical strings. `tools/check_spec_entry.py` likewise activates.
- **Plan 05 unblocked.** build.ps1's PKG-03 step can shell out to `python tools/check_subprocess_guard.py` (or duplicate the regex with Select-String per RESEARCH §Pattern 5 — the Python script is the single-source-of-truth that runs on both dev Linux and the Windows build VM).

---
*Phase: 44-windows-packaging-installer*
*Completed: 2026-04-25*
