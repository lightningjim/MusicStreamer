---
phase: 79-fix-youtube-stream-exhausted-when-launched-via-desktop-app-w
plan: "01"
subsystem: yt-dlp opts
tags: [youtube, yt-dlp, node-runtime, dependency-injection, bug-fix]
dependency_graph:
  requires: []
  provides:
    - musicstreamer.yt_dlp_opts.build_js_runtimes
  affects:
    - musicstreamer/player.py (Plans 79-02)
    - musicstreamer/yt_import.py (Plans 79-03)
tech_stack:
  added: []
  patterns:
    - focused-tiny-module (mirrors cookie_utils.py, url_helpers.py shape)
    - dependency-injection via NodeRuntime | None kwarg
key_files:
  created:
    - musicstreamer/yt_dlp_opts.py
    - tests/test_yt_dlp_opts.py
  modified: []
decisions:
  - "build_js_runtimes reads only node_runtime.path — never consults node_runtime.available (D-02: short-circuiting on available=False would regress JS-free streams)"
  - "Helper strictly scoped to js_runtimes only — no format, cookiefile, remote_components, etc. (D-11)"
  - "Single code path for Linux and Windows — no sys.platform gate (D-03)"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-16"
  tasks_completed: 2
  files_created: 2
  files_modified: 0
---

# Phase 79 Plan 01: yt_dlp_opts helper module + unit tests Summary

## One-Liner

Pure `build_js_runtimes(NodeRuntime | None) -> dict` helper that threads the resolved Node path into yt-dlp js_runtimes opts — single source of truth for both Player and yt_import call sites (BUG-11).

## What Was Built

### musicstreamer/yt_dlp_opts.py (NEW)

Focused tiny module following the `cookie_utils.py` shape: module-level docstring with "Provides:" and "Call sites:" blocks, `from __future__ import annotations`, single public function, no class.

Public surface:
```python
def build_js_runtimes(node_runtime: NodeRuntime | None) -> dict:
    """Return js_runtimes opts dict for yt_dlp.YoutubeDL."""
    path = node_runtime.path if node_runtime is not None else None
    return {"node": {"path": path}}
```

This is the second half of the fix started in commit `a06549f` (2026-04-25): where that commit taught `runtime_check` to find Node via version-manager fallback even under `.desktop`-stripped PATH, this module threads the resulting `NodeRuntime.path` into yt-dlp so it receives an explicit absolute path instead of performing its own (failing) PATH lookup.

### tests/test_yt_dlp_opts.py (NEW)

Three-input matrix unit tests pinning the helper's contract before Plans 79-02 and 79-03 wire it into production call sites:

- `test_build_js_runtimes_none_input` — B-79-01 / D-02: `build_js_runtimes(None)` returns `{"node": {"path": None}}`
- `test_build_js_runtimes_available_path` — B-79-02 / D-01 / D-04: `NodeRuntime(available=True, path="/fake/node")` → path threads through
- `test_build_js_runtimes_unavailable_none_path` — B-79-03 / D-02: `NodeRuntime(available=False, path=None)` → `{"node": {"path": None}}`

All three pass. No pytest fixtures, no parametrize, inline NodeRuntime literals per CONTEXT.md Claude's Discretion.

## Behaviors Pinned

| Behavior ID | Description | Status |
|-------------|-------------|--------|
| B-79-01 | `build_js_runtimes(None)` returns `{"node": {"path": None}}` | GREEN |
| B-79-02 | `build_js_runtimes(NodeRuntime(available=True, path="/fake/node"))` returns `{"node": {"path": "/fake/node"}}` | GREEN |
| B-79-03 | `build_js_runtimes(NodeRuntime(available=False, path=None))` returns `{"node": {"path": None}}` | GREEN |

## Helper Public Signature (for Plans 79-02 and 79-03)

```python
from musicstreamer.yt_dlp_opts import build_js_runtimes
from musicstreamer.runtime_check import NodeRuntime

# In player._youtube_resolve_worker:
"js_runtimes": yt_dlp_opts.build_js_runtimes(self._node_runtime),

# In yt_import.scan_playlist opts dict:
"js_runtimes": yt_dlp_opts.build_js_runtimes(node_runtime),
```

Import verified non-circular: `musicstreamer.runtime_check` does not import from `musicstreamer.player`, `musicstreamer.yt_import`, or `musicstreamer.yt_dlp_opts`.

## Commits

| Task | Commit | Files |
|------|--------|-------|
| Task 1: yt_dlp_opts.py module | 2665067 | musicstreamer/yt_dlp_opts.py |
| Task 2: test_yt_dlp_opts.py | 19399a7 | tests/test_yt_dlp_opts.py |

## Deviations from Plan

None — plan executed exactly as written.

The plan listed Task 1 (module) before Task 2 (tests), but both are `tdd="true"`. Applied TDD correctly: wrote tests first (RED — ImportError confirmed), then the module (GREEN — 3 passed). Both committed per-task per the plan's task structure.

## Known Stubs

None. Both files are pure logic with no UI rendering, no placeholder text, and no hardcoded empty values flowing anywhere.

## Threat Flags

None. The new module is a pure dict-builder with no I/O, no network access, no subprocess, no file operations, and no schema changes. The plan's threat model (T-79-01, T-79-02, both accepted) covers the downstream call sites in Plans 79-02/79-03.

## TDD Gate Compliance

- RED gate: `tests/test_yt_dlp_opts.py` written first; `ModuleNotFoundError` confirmed before module existed (ImportError IS the RED state)
- GREEN gate: `musicstreamer/yt_dlp_opts.py` written; 3 tests pass
- REFACTOR gate: not needed (module is minimal by design)

## Self-Check

### Files exist

- FOUND: musicstreamer/yt_dlp_opts.py
- FOUND: tests/test_yt_dlp_opts.py

### Commits exist

- FOUND: 2665067
- FOUND: 19399a7

## Self-Check: PASSED
