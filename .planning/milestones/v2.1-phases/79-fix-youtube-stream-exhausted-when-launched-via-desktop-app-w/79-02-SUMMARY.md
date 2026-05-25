---
phase: 79-fix-youtube-stream-exhausted-when-launched-via-desktop-app-w
plan: "02"
subsystem: youtube-playback
tags: [youtube, yt-dlp, node-runtime, dependency-injection, bug-fix, player]
dependency_graph:
  requires:
    - phase: 79-01
      provides: musicstreamer.yt_dlp_opts.build_js_runtimes
  provides:
    - Player.__init__ accepts keyword-only node_runtime kwarg (D-05/D-06)
    - _youtube_resolve_worker uses yt_dlp_opts.build_js_runtimes — single source of truth (D-10)
    - __main__._run_gui threads node_runtime to Player() (D-07)
    - musicstreamer.yt_import logger escalated to INFO in __main__.main
    - Three regression tests B-79-04/B-79-05/B-79-06 pin the contract
  affects:
    - 79-03 (yt_import.scan_playlist node_runtime wiring — mirrors this plan's shape)
tech_stack:
  added: []
  patterns:
    - constructor-kwarg DI with node_runtime=None default (mirrors MainWindow pattern)
    - INFO log line per YT play for live-debug visibility (D-13)
    - FakeYDL opts-recording regression test pattern (mirrors test_cookies.py)
key_files:
  created:
    - tests/test_player_node_runtime.py
  modified:
    - musicstreamer/player.py
    - musicstreamer/__main__.py
key-decisions:
  - "Player.__init__ keyword-only node_runtime=None default preserves backwards-compat (D-05/D-06) — _run_smoke at line 39 unchanged"
  - "Explicit conditional (self._node_runtime.path if self._node_runtime else None) — NOT short-circuit 'and' (Pitfall 3)"
  - "Forward-reference string annotation 'NodeRuntime | None' for import-order safety"
  - "yt_import logger escalated here alongside player/soma_import (same __main__.main block, disjoint file ownership from Plan 79-03)"
requirements-completed:
  - BUG-11
duration: ~4min
completed: "2026-05-16"
---

# Phase 79 Plan 02: Wire Player.__init__ node_runtime kwarg + regression matrix Summary

**Player now receives an absolute Node.js path from NodeRuntime and passes it to yt-dlp via yt_dlp_opts.build_js_runtimes — eliminating the .desktop-launch PATH-stripping bug for the YouTube playback path (BUG-11 player half).**

## Performance

- **Duration:** ~4 minutes
- **Started:** 2026-05-16T17:50:14Z
- **Completed:** 2026-05-16T17:54:14Z
- **Tasks:** 2
- **Files modified:** 3 (2 production + 1 new test file)

## Accomplishments

- `Player.__init__` accepts `node_runtime: NodeRuntime | None = None` keyword-only kwarg (D-05/D-06), stored as `self._node_runtime` immediately after `super().__init__(parent)` — mirrors `MainWindow.__init__` shape
- `_youtube_resolve_worker` replaces inline `{"node": {"path": None}}` literal with `yt_dlp_opts.build_js_runtimes(self._node_runtime)` — single source of truth per D-10; adds INFO log line `"youtube resolve: node_path=%s"` per D-13
- `__main__._run_gui` line 220 changed from `Player()` to `Player(node_runtime=node_runtime)` — the resolved `NodeRuntime` from line 215 now flows to yt-dlp (D-07)
- `__main__.main` escalates `musicstreamer.yt_import` logger to INFO alongside `musicstreamer.player` and `musicstreamer.soma_import` (Open Question 2 — positive answer per RESEARCH.md)
- Phase 999.7 `cookie_utils.temp_cookies_copy()` ctxmgr is UNCHANGED in position — `yt_dlp.YoutubeDL` construction still nests inside it; cookie invariant preserved
- Three regression tests in `tests/test_player_node_runtime.py` pin the B-79-04/B-79-05/B-79-06 contract; all pre-existing `tests/test_cookies.py:157,190` assertions stay green by construction

## Task Commits

1. **Task 1: Wire Player.__init__ node_runtime + _youtube_resolve_worker + __main__.py** — `856c020` (feat)
2. **Task 2: tests/test_player_node_runtime.py B-79-04/B-79-05/B-79-06 regression matrix** — `ec5ded8` (test)

## Files Created/Modified

- `musicstreamer/player.py` — imports `yt_dlp_opts` and `NodeRuntime`; `__init__` grows `node_runtime` kwarg; `_youtube_resolve_worker` uses helper + emits INFO log
- `musicstreamer/__main__.py` — `Player(node_runtime=node_runtime)` at line 220; `musicstreamer.yt_import` logger setLevel(INFO)
- `tests/test_player_node_runtime.py` (NEW) — three-input regression matrix for B-79-04, B-79-05, B-79-06

## Behaviors Pinned

| Behavior ID | Description | Status |
|-------------|-------------|--------|
| B-79-04 | `Player(node_runtime=NodeRuntime(available=True, path="/fake/node"))._youtube_resolve_worker` passes `js_runtimes["node"]["path"] == "/fake/node"` | GREEN |
| B-79-05 | `Player()` no-arg (node_runtime=None) passes `js_runtimes["node"]["path"] is None` (backwards-compat) | GREEN |
| B-79-06 | `Player(node_runtime=NodeRuntime(available=False, path=None))._youtube_resolve_worker` passes `js_runtimes["node"]["path"] is None` | GREEN |

## Invariants Confirmed

| Invariant | Verification |
|-----------|--------------|
| Phase 999.7 cookie temp-copy | `grep -c "with cookie_utils.temp_cookies_copy() as cookiefile" musicstreamer/player.py` returns `1` |
| test_cookies.py:157,190 assertions still green | `uv run --with pytest pytest tests/test_cookies.py -x` exits 0 (17 passed) |
| Inline literal gone from player.py | `grep -c '"node": {"path": None}' musicstreamer/player.py` returns `0` |
| Single source of truth | `grep -c "build_js_runtimes(self._node_runtime)" musicstreamer/player.py` returns `1` |
| _run_smoke unchanged | `grep -n "player = Player()" musicstreamer/__main__.py` returns only line 39 |

## Decisions Made

- Forward-reference string `"NodeRuntime | None"` for the type annotation — avoids any import-order brittleness (PATTERNS.md §2 guidance)
- `self._node_runtime = node_runtime` placed immediately after `super().__init__(parent)` — same position as `MainWindow` pattern
- Module docstring updated to replace the stale `{"path": None}` literal reference with description of the new behavior — auto-fix (Rule 1 / docstring accuracy)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated stale module docstring in player.py**
- **Found during:** Task 1 (acceptance criteria verification)
- **Issue:** Module docstring at line 20 contained `js_runtimes={"node": {"path": None}}` which triggered the plan's acceptance criterion `grep -c '"node": {"path": None}' returns 0`; the comment described the old behavior
- **Fix:** Updated the docstring to reference `{"path": <abs-path-or-None>}` and explain the Phase 79 BUG-11 context
- **Files modified:** musicstreamer/player.py
- **Verification:** `grep -c '"node": {"path": None}' musicstreamer/player.py` returns `0`
- **Committed in:** 856c020 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — docstring accuracy)
**Impact on plan:** Minor documentation fix; no behavior change.

## Issues Encountered

- `uv run --with pytest` created a new virtualenv without `gi` (system package) and without `pytest-qt`. Switched to using the project's existing `.venv` via `/home/kcreasey/OneDrive/Projects/MusicStreamer/.venv/bin/python -m pytest`. `pytest-qt` was also installed into that venv (it was missing; required by `[project.optional-dependencies.test]`).

## Known Stubs

None. All files are production code or regression tests with no placeholder text, no hardcoded empty values flowing to UI rendering.

## Threat Flags

None. The changes add a constructor kwarg and substitute a dict key value — no new network endpoints, no new file access patterns, no new auth paths, no schema changes. The INFO log line falls under the existing accepted T-79-02 pattern (local stderr only; same data as `runtime_check._log.debug` at runtime_check.py:115).

## Next Phase Readiness

- Plan 79-02 complete: Player playback path now threads the resolved Node abs path to yt-dlp
- Plan 79-03 (yt_import.scan_playlist) should mirror this shape exactly: same `node_runtime` kwarg DI, same `yt_dlp_opts.build_js_runtimes(node_runtime)` call, same INFO log line
- `musicstreamer.yt_import` logger is already escalated to INFO in `__main__.main` (this plan), so the Plan 79-03 INFO line will surface at default verbosity without further `__main__.py` edits

## Self-Check

### Files exist

- FOUND: musicstreamer/player.py
- FOUND: musicstreamer/__main__.py
- FOUND: tests/test_player_node_runtime.py

### Commits exist

- FOUND: 856c020
- FOUND: ec5ded8

## Self-Check: PASSED

---
*Phase: 79-fix-youtube-stream-exhausted-when-launched-via-desktop-app-w*
*Completed: 2026-05-16*
