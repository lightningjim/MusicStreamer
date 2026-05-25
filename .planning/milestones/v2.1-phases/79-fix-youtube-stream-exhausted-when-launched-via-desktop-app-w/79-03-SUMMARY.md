---
phase: 79-fix-youtube-stream-exhausted-when-launched-via-desktop-app-w
plan: "03"
subsystem: yt-import scan path + ImportDialog UI plumbing
tags: [youtube, yt-dlp, node-runtime, dependency-injection, scan-playlist, bug-fix, tdd]
dependency_graph:
  requires:
    - 79-01 (musicstreamer.yt_dlp_opts.build_js_runtimes)
  provides:
    - scan_playlist accepts node_runtime kwarg (B-79-07, B-79-08, B-79-09)
    - ImportDialog → _YtScanWorker → scan_playlist DI chain
    - MainWindow threads self._node_runtime to ImportDialog
  affects:
    - musicstreamer/yt_import.py (node_runtime kwarg + js_runtimes + logger)
    - musicstreamer/ui_qt/import_dialog.py (_YtScanWorker + ImportDialog)
    - musicstreamer/ui_qt/main_window.py (single-line ImportDialog ctor edit)
    - tests/test_yt_import_library.py (three new regression tests)
tech_stack:
  added: []
  patterns:
    - keyword-only default-None kwarg for backwards-compat (Pitfall 5)
    - capture at __init__ not lazy-read (Pitfall 6 — QThread safety)
    - single source of truth via yt_dlp_opts.build_js_runtimes (D-10)
    - module logger _log = logging.getLogger(__name__) mirroring player.py
key_files:
  created: []
  modified:
    - musicstreamer/yt_import.py
    - musicstreamer/ui_qt/import_dialog.py
    - musicstreamer/ui_qt/main_window.py
    - tests/test_yt_import_library.py
decisions:
  - "js_runtimes is INSERTed into scan_playlist opts dict (not substituted) — scan-side had no existing js_runtimes literal (Pitfall 2); yt-dlp default was {'deno': {}} via _clean_js_runtimes"
  - "node_runtime is keyword-only on scan_playlist, _YtScanWorker.__init__, and ImportDialog.__init__ — preserves all existing positional call sites in tests (Pitfall 5)"
  - "_YtScanWorker captures node_runtime at __init__ not in run() — dialog may close mid-scan; frozen dataclass is cross-thread safe (Pitfall 6 / T-79-03)"
  - "extract_flat='in_playlist' short-circuits per-entry JS solving today — this is defensive parity for D-10 invariant, not a live-bug fix on the scan path (A5)"
  - "Explicit conditional for INFO log: 'node_runtime.path if node_runtime else None' — NOT node_runtime and node_runtime.path (Pitfall 3)"
metrics:
  duration: "~15 minutes"
  completed: "2026-05-16"
  tasks_completed: 3
  files_created: 0
  files_modified: 4
---

# Phase 79 Plan 03: scan_playlist node_runtime DI + ImportDialog plumbing + regression tests Summary

## One-Liner

Wires `NodeRuntime` into `scan_playlist` (opts INSERT + module logger) and threads it through `MainWindow → ImportDialog → _YtScanWorker → scan_playlist` via keyword-only DI kwargs, adding three regression tests that pin the single-source-of-truth invariant (BUG-11 scan-path parity).

## What Was Built

### Task 1: musicstreamer/yt_import.py

Four changes to complete the scan-side half of BUG-11:

1. **New imports:** `import logging`, `from musicstreamer import ... yt_dlp_opts` (alphabetical insertion), `from musicstreamer.runtime_check import NodeRuntime`
2. **Module logger:** `_log = logging.getLogger(__name__)` — mirrors `player.py:76-78`
3. **Signature extension:** `scan_playlist` gains a keyword-only `node_runtime: "NodeRuntime | None" = None` parameter after `toast_callback`, with `*,` keyword-only marker (Pitfall 5)
4. **INFO log line:** `node_path = node_runtime.path if node_runtime else None` + `_log.info("youtube scan: node_path=%s", node_path)` — inserted after the cookies-corruption block and before `opts = {` (D-13 parity)
5. **opts dict INSERT:** `"js_runtimes": yt_dlp_opts.build_js_runtimes(node_runtime),` inserted after `"skip_download": True,` and before the `# BUG-YT-COOKIES` comment block — this is an ADDITION not a substitution (Pitfall 2 — scan-side had no existing `js_runtimes` literal)

The `with cookie_utils.temp_cookies_copy() as cookiefile:` ctxmgr at line 93 is unchanged (Phase 999.7 invariant preserved).

Note on `extract_flat`: Per Pitfall 2 and RESEARCH.md A5, `extract_flat='in_playlist'` short-circuits per-entry JS solving inside yt-dlp 2026.03.17 (YoutubeDL.py:1894-1909). The scan-side fix is therefore **defensive parity** — it pre-empts a future bug if the scan path ever stops using `extract_flat`, AND keeps the single-source-of-truth invariant (D-10) intact. The live-bug surface is exclusively the playback path (Plan 79-02).

### Task 2: musicstreamer/ui_qt/import_dialog.py + main_window.py

Four-layer dependency injection chain:

1. **`_YtScanWorker.__init__`:** gains keyword-only `node_runtime: "NodeRuntime | None" = None` after `toast_callback`; stored as `self._node_runtime`. Captured at construction time per Pitfall 6 (dialog may close mid-scan; `NodeRuntime` is a frozen dataclass so cross-thread `.path` reads are safe Python semantics)
2. **`_YtScanWorker.run()`:** forwards `node_runtime=self._node_runtime` to `scan_playlist` call
3. **`ImportDialog.__init__`:** gains keyword-only `node_runtime: "NodeRuntime | None" = None` after `parent`; stored as `self._node_runtime` adjacent to `_toast` and `_repo`
4. **`_on_yt_scan_clicked`:** passes `node_runtime=self._node_runtime` to `_YtScanWorker` ctor call (reformatted multi-line)
5. **`MainWindow._open_import_dialog`:** single-line edit threads `node_runtime=self._node_runtime` into `ImportDialog(...)` ctor. `self._node_runtime` was already stored at `main_window.py:202` — no new MainWindow state

`NodeRuntime` imported via `from musicstreamer.runtime_check import NodeRuntime` in import_dialog.py.

### Task 3: tests/test_yt_import_library.py

Three new regression tests appended at end of file (no modifications to existing tests or `_patch_youtubedl` helper):

- `test_scan_playlist_passes_node_path_when_available` — B-79-07: `NodeRuntime(available=True, path="/fake/node")` → `opts["js_runtimes"] == {"node": {"path": "/fake/node"}}`
- `test_scan_playlist_default_none_node_runtime` — B-79-08: no `node_runtime` kwarg → `opts["js_runtimes"] == {"node": {"path": None}}` (backwards-compat)
- `test_scan_playlist_passes_none_when_unavailable` — B-79-09: `NodeRuntime(available=False, path=None)` → `opts["js_runtimes"] == {"node": {"path": None}}` (D-02)

All three use the existing `_patch_youtubedl` helper and `youtubedl_cls.call_args[0][0]` to capture opts. No `pytest.fixture` or `pytest.mark.parametrize` — inline NodeRuntime literals per CONTEXT.md Claude's Discretion. `NodeRuntime` import added to file header.

## Behaviors Pinned

| Behavior ID | Description | Status |
|-------------|-------------|--------|
| B-79-07 | `scan_playlist(url, node_runtime=NodeRuntime(available=True, path="/fake/node"))` → `opts["js_runtimes"]["node"]["path"] == "/fake/node"` | GREEN |
| B-79-08 | `scan_playlist(url)` (no kwarg) → `opts["js_runtimes"]["node"]["path"] is None` | GREEN |
| B-79-09 | `scan_playlist(url, node_runtime=NodeRuntime(available=False, path=None))` → `opts["js_runtimes"]["node"]["path"] is None` | GREEN |

## Commits

| Task | Commit | Files |
|------|--------|-------|
| Task 1: yt_import.py — kwarg + js_runtimes INSERT + logger | 2f5eee9 | musicstreamer/yt_import.py |
| Task 2: UI plumbing — ImportDialog + _YtScanWorker + main_window | dae4dca | musicstreamer/ui_qt/import_dialog.py, musicstreamer/ui_qt/main_window.py |
| Task 3: regression tests B-79-07/08/09 | 57d0ca7 | tests/test_yt_import_library.py |

## Deviations from Plan

None — plan executed exactly as written.

The `test_import_dialog_qt.py` file has a pre-existing failure (missing `qtbot` fixture — requires pytest-qt which is not installed in this environment). This is unrelated to Phase 79 changes and was failing before any modifications; confirmed by `git stash` verification.

## Known Stubs

None. All four modified files contain production logic or regression tests with no placeholder values, hardcoded empty returns, or TODO/FIXME markers introduced by this plan.

## Threat Flags

No new threat surface beyond what the plan's threat model documents. The three STRIDE entries (T-79-01, T-79-02, T-79-03) all have accepted/mitigated dispositions:
- T-79-01 (subprocess path threading): INACTIVE under current yt-dlp behavior (`extract_flat` short-circuits JS solving); defensive parity for D-10 invariant
- T-79-02 (INFO log disclosure): accepted — local stderr only, same precedent as player-side INFO line
- T-79-03 (cross-thread QThread capture): mitigated by construction — capture at `__init__`, frozen dataclass

## TDD Gate Compliance

All three tasks are `tdd="true"`. The TDD flow in this plan is:
- Tasks 1 and 2 (implementation): verified against pre-existing tests (RED confirmed = existing tests pass before changes; GREEN = existing tests still pass after changes, default `None` branch)
- Task 3 (regression tests): the three new tests pin the new behavior introduced in Task 1; all three passed immediately after Task 1's implementation landed (GREEN gate)

No REFACTOR gate needed — all code is minimal by design.

## Self-Check

### Files exist

- FOUND: musicstreamer/yt_import.py
- FOUND: musicstreamer/ui_qt/import_dialog.py
- FOUND: musicstreamer/ui_qt/main_window.py
- FOUND: tests/test_yt_import_library.py

### Commits exist

- FOUND: 2f5eee9
- FOUND: dae4dca
- FOUND: 57d0ca7

## Self-Check: PASSED
