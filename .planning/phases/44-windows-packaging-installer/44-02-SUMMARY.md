---
phase: 44-windows-packaging-installer
plan: 02
subsystem: infra
tags: [pyside6, qlocalserver, qlocalsocket, single-instance, nodejs, runtime-detection, windows, version]

requires:
  - phase: 44-windows-packaging-installer
    provides: 44-01 RED tests for single_instance + runtime_check + missing-node dialog (parallel wave-1 sibling)
provides:
  - SingleInstanceServer (QObject) + acquire_or_forward() + raise_and_focus() with FlashWindowEx fallback (D-08, D-09)
  - NodeRuntime dataclass + check_node() + show_missing_node_dialog() (D-11..D-14)
  - __version__.py single source of truth + pyproject version 2.0.0 (D-06)
affects: [44-03, 44-04, 44-05, future about-dialog]

tech-stack:
  added:
    - PySide6.QtNetwork (QLocalServer, QLocalSocket) — single-instance IPC
  patterns:
    - "Parameter-only lambdas (QA-05): only `lambda: self._drain(socket)` — captures the local socket, not self"
    - "Lazy ctypes/wintypes import inside Windows-platform branch (matches __main__.py:115-116 pattern)"
    - "Lazy QDesktopServices/QUrl import inside dialog click branch (PATTERNS.md Lazy Imports for UI Modules)"
    - "Frozen dataclass for runtime detection results (NodeRuntime)"
    - "Windows shutil.which("node.exe") preference defends against CPython issue #109590"
    - "Graceful degradation: QLocalServer.listen failure logs warning + returns None — app continues without single-instance guard"

key-files:
  created:
    - musicstreamer/single_instance.py
    - musicstreamer/runtime_check.py
    - musicstreamer/__version__.py
  modified:
    - pyproject.toml

key-decisions:
  - "D-06 implemented: pyproject.toml version 1.1.0 -> 2.0.0; __version__.py mirrors literal"
  - "D-08 implemented: SERVER_NAME = 'org.lightningjim.MusicStreamer.single-instance'"
  - "D-09 implemented: raise_and_focus() with Windows FlashWindowEx fallback wrapped in try/except"
  - "D-11/D-14 implemented: one-shot Node.js detection cached in NodeRuntime dataclass; no runtime polling"
  - "D-12 implemented: missing-node QMessageBox with 'Open nodejs.org' (ActionRole) + 'OK' (AcceptRole default)"

patterns-established:
  - "QLocalServer/QLocalSocket single-instance pattern with stale-socket cleanup via removeServer()"
  - "FlashWindowEx ctypes fallback pattern for Windows focus-steal scenarios"
  - "CPython #109590 Windows shutil.which workaround: prefer 'node.exe' first, then validate '.exe' suffix on bare 'node' fallback"

requirements-completed: [PKG-04, PKG-03, QA-03]

duration: 14min
completed: 2026-04-25
---

# Phase 44 Plan 02: Single-Instance + Runtime-Check Modules Summary

**QLocalServer-based single-instance helper with FlashWindowEx focus fallback, Node.js host-runtime detection with CPython #109590 Windows safety, and version 2.0.0 source-of-truth landed.**

## Performance

- **Duration:** ~14 min
- **Started:** 2026-04-25T15:42:00Z
- **Completed:** 2026-04-25T15:56:28Z
- **Tasks:** 2 (both committed atomically)
- **Files created:** 3
- **Files modified:** 1

## Accomplishments

- `musicstreamer/single_instance.py` (150 lines) — `SingleInstanceServer(QObject)` with `activate_requested` signal, `acquire_or_forward()` probe-then-listen flow with stale-socket cleanup, and `raise_and_focus(window)` with Windows `FlashWindowEx` fallback. Implements D-08, D-09, D-10.
- `musicstreamer/runtime_check.py` (86 lines) — `NodeRuntime` frozen dataclass, `_which_node()` Windows-aware locator (defends CPython issue #109590 by preferring `node.exe`), `check_node()` one-shot detector, `show_missing_node_dialog()` Qt dialog with "Open nodejs.org" + "OK" buttons. Implements D-11, D-12, D-14. Module is import-safe from tests (no `musicstreamer.ui_qt` import).
- `musicstreamer/__version__.py` — `__version__ = "2.0.0"` literal kept in sync with pyproject.toml `[project].version`.
- `pyproject.toml` — version bumped from `1.1.0` to `2.0.0` per D-06.
- QA-05 compliance: only one lambda used in either module — `lambda: self._drain(socket)` — which is parameter-only (captures local `socket`, not `self`). All other signal connections use bound methods.

## Task Commits

1. **Task 1: Create musicstreamer/single_instance.py + bump version** — `a5c22d2` (feat)
2. **Task 2: Create musicstreamer/runtime_check.py** — `f557c94` (feat)

_Note: This plan is the GREEN half of a parallel wave-1 split: Plan 01 (separate worktree) lands the RED test commits; Plan 02 lands the implementation modules. Plan 01's pytest gates will verify these modules after the worktrees merge._

## Files Created/Modified

- `musicstreamer/single_instance.py` (CREATED, 150 lines) — QLocalServer/QLocalSocket single-instance helper with FlashWindowEx fallback
- `musicstreamer/runtime_check.py` (CREATED, 86 lines) — Node.js host-runtime detection + missing-node dialog
- `musicstreamer/__version__.py` (CREATED, 14 lines) — single-source `__version__ = "2.0.0"` literal
- `pyproject.toml` (MODIFIED, 1 line) — `version = "1.1.0"` → `version = "2.0.0"`

## Decisions Made

None — plan implementation copied verbatim from `44-RESEARCH.md` Pattern 2 (lines 357-502), Pattern 3 (lines 540-629), and Pattern 6 (lines 822-840) as instructed by the plan's `<action>` blocks. Spelling/wording adjusted only for consistency (e.g., backtick formatting in module docstrings).

## Deviations from Plan

None — plan executed exactly as written. The only minor cleanup: removed an unused `os` and `Callable` import that the verbatim research snippets contained but were never referenced (`runtime_check.py` and `single_instance.py` respectively). This is import-hygiene only, not a behavioral deviation.

**Verification gate substitution:** The plan's `<verify><automated>` blocks invoke `pytest tests/test_single_instance.py` / `pytest tests/test_runtime_check.py` / `pytest tests/ui_qt/test_missing_node_dialog.py`. These tests are landed by parallel sibling Plan 01 in a separate worktree and are not present here. Per Plan 02 frontmatter `wave: 1, depends_on: []` (parallel), the test verification will run after the orchestrator merges both worktrees. Inside this worktree I substituted the equivalent grep-based acceptance criteria + import smoke tests, all of which passed:

- All 7 grep checks for `single_instance.py` ✓
- All 10 grep checks for `runtime_check.py` (including the negative `grep -L 'from musicstreamer.ui_qt'` check) ✓
- `python -c "from musicstreamer import __version__; assert __version__.__version__ == '2.0.0'"` ✓
- `python -c "from musicstreamer.single_instance import SERVER_NAME, SingleInstanceServer, acquire_or_forward, raise_and_focus"` ✓
- `python -c "from musicstreamer.runtime_check import NodeRuntime, check_node, show_missing_node_dialog, NODEJS_INSTALL_URL"` ✓ (and `check_node()` resolved a real node.js install at `/run/user/1000/fnm_multishells/.../bin/node`)
- `grep -q '^version = "2.0.0"$' pyproject.toml` ✓

## Issues Encountered

None.

## Threat-Model Compliance

All STRIDE mitigations from the plan's `<threat_model>` section landed in code:

- **T-44-02-01 (S):** `_drain` checks `data == b"activate"` strictly; unknown payloads silently dropped.
- **T-44-02-02 (S):** `setSocketOptions(QLocalServer.SocketOption.UserAccessOption)` + `removeServer(SERVER_NAME)` before listen.
- **T-44-02-05 (D):** `listen()` failure path logs warning and returns `None`; caller continues without single-instance guard (no app crash).

## Self-Check: PASSED

- `musicstreamer/single_instance.py` — FOUND (150 lines)
- `musicstreamer/runtime_check.py` — FOUND (86 lines)
- `musicstreamer/__version__.py` — FOUND
- `pyproject.toml` — version 2.0.0 confirmed via grep
- Commit `a5c22d2` (Task 1) — FOUND in `git log --oneline`
- Commit `f557c94` (Task 2) — FOUND in `git log --oneline`

## Next Phase Readiness

- Plan 03 (`__main__.py` wiring + MainWindow integration) can now `from musicstreamer.single_instance import acquire_or_forward, raise_and_focus` and `from musicstreamer.runtime_check import check_node, show_missing_node_dialog, NodeRuntime`.
- Plan 04 (Inno Setup `.iss` + `build.ps1`) can read `[project].version = "2.0.0"` from pyproject and pass it as `/DAppVersion=2.0.0` to `iscc.exe`.
- Plan 01's pytest gates (in a parallel worktree) will exercise these modules after the orchestrator merges wave 1.

---
*Phase: 44-windows-packaging-installer*
*Plan: 02*
*Completed: 2026-04-25*
