---
phase: 79-fix-youtube-stream-exhausted-when-launched-via-desktop-app-w
verified: 2026-05-16T00:00:00Z
status: passed
score: 20/20 must-haves verified
overrides_applied: 0
re_verification: null
gaps: []
human_verification: []
---

# Phase 79: Fix YouTube 'stream exhausted' When Launched via .desktop — Verification Report

**Phase Goal:** Fix YouTube 'stream exhausted' regression when MusicStreamer is launched via the GNOME `.desktop` entry — specifically, the case where Node.js is provided exclusively via a version-manager shim (fnm/nvm/volta/asdf). Thread the resolved absolute Node path (already discovered by `runtime_check.check_node()`'s version-manager fallback) into yt-dlp's `js_runtimes` opt at BOTH yt-dlp call sites (`Player._youtube_resolve_worker` and `yt_import.scan_playlist`) via a new tiny focused module `musicstreamer/yt_dlp_opts.py`. Backwards-compat preserved; ONE INFO log line per YT play/scan; no new toast; no PATH augmentation.
**Verified:** 2026-05-16
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `build_js_runtimes(None)` returns `{"node": {"path": None}}` (B-79-01 / D-02) | VERIFIED | `yt_dlp_opts.py` body: `path = node_runtime.path if node_runtime is not None else None; return {"node": {"path": path}}`. Runtime confirmed via `.venv/bin/python` invocation: output `{'node': {'path': None}}`. |
| 2 | `build_js_runtimes(NodeRuntime(available=True, path='/fake/node'))` returns `{"node": {"path": "/fake/node"}}` (B-79-02 / D-01 / D-04) | VERIFIED | Same function body; runtime confirmed output `{'node': {'path': '/fake/node'}}`. |
| 3 | `build_js_runtimes(NodeRuntime(available=False, path=None))` returns `{"node": {"path": None}}` (B-79-03 / D-02 — available field not consulted) | VERIFIED | Same function body reads only `.path`; runtime confirmed output `{'node': {'path': None}}`. |
| 4 | Helper is strictly scoped to `js_runtimes` only — no `format`, `remote_components`, `cookiefile`, `extract_flat`, `quiet`, `skip_download` (D-11) | VERIFIED | `grep -E '"(format|remote_components|cookiefile|extract_flat|quiet|skip_download)"' musicstreamer/yt_dlp_opts.py` returns 0 matches. |
| 5 | Single source of truth: only `yt_dlp_opts.py` builds `js_runtimes`; both `player.py` and `yt_import.py` import and call it (D-10) | VERIFIED | `player.py` count: 1; `yt_import.py` count: 1 (via `src.count("build_js_runtimes(")`). Drift-guard tests lock this. |
| 6 | No `sys.platform` gate — helper works identically on Linux and Windows (D-03) | VERIFIED | `grep "sys.platform" musicstreamer/yt_dlp_opts.py musicstreamer/player.py musicstreamer/yt_import.py` returns 0 matches. |
| 7 | `Player.__init__` accepts keyword-only `node_runtime: NodeRuntime | None = None` param; stored as `self._node_runtime` (D-05 / D-06) | VERIFIED | `player.py:284`: `def __init__(self, parent: QObject | None = None, *, node_runtime: "NodeRuntime | None" = None) -> None:` and `player.py:286`: `self._node_runtime = node_runtime`. |
| 8 | `Player._youtube_resolve_worker` calls `yt_dlp_opts.build_js_runtimes(self._node_runtime)` — `js_runtimes` value threaded through; inline `{"node": {"path": None}}` literal removed (B-79-04 / D-01 / D-10) | VERIFIED | `player.py:1072`: `"js_runtimes": yt_dlp_opts.build_js_runtimes(self._node_runtime),`; `grep -c '"node": {"path": None}' musicstreamer/player.py` returns `0`. |
| 9 | `_youtube_resolve_worker` emits one INFO log line `"youtube resolve: node_path=<abs|None>"` per call using explicit conditional (D-13 / Pitfall 3) | VERIFIED | `player.py:1057-1058`: `node_path = self._node_runtime.path if self._node_runtime else None` and `_log.info("youtube resolve: node_path=%s", node_path)`. Count grep returns 1. |
| 10 | `__main__._run_gui` passes `node_runtime=node_runtime` to `Player()` at line 220; `_run_smoke` at line 39 remains `Player()` (D-07) | VERIFIED | `__main__.py:220`: `player = Player(node_runtime=node_runtime)`; line 39 is only other occurrence: `player = Player()`. |
| 11 | `__main__.main` escalates `musicstreamer.yt_import` logger to INFO alongside `musicstreamer.player` and `musicstreamer.soma_import` | VERIFIED | `__main__.py:239`: `logging.getLogger("musicstreamer.yt_import").setLevel(logging.INFO)`. Grep count returns 1. |
| 12 | Phase 999.7 `cookie_utils.temp_cookies_copy()` ctxmgr preserved unchanged at both call sites | VERIFIED | `grep -c "with cookie_utils.temp_cookies_copy() as cookiefile" musicstreamer/player.py` returns 1; same grep on `musicstreamer/yt_import.py` returns 1. |
| 13 | `yt_import.scan_playlist` accepts keyword-only `node_runtime: NodeRuntime | None = None` kwarg; opts dict INSERTs `"js_runtimes": yt_dlp_opts.build_js_runtimes(node_runtime)` between `skip_download` and `# BUG-YT-COOKIES` (B-79-07..09 / D-08 / D-09 / D-10 / Pitfall 2) | VERIFIED | `yt_import.py:44-47`: `*, node_runtime: "NodeRuntime | None" = None`. `yt_import.py:75,82,83`: `skip_download` at 75, `js_runtimes` at 82, `# BUG-YT-COOKIES` at 83. Correct ordering confirmed. |
| 14 | `scan_playlist` emits one INFO log line `"youtube scan: node_path=<abs|None>"` using explicit conditional; module logger `_log` present (D-13 / Pitfall 3) | VERIFIED | `yt_import.py:68-69`: explicit conditional form present; `grep -c '"youtube scan: node_path='` returns 1; `grep -c "^_log = logging.getLogger(__name__)" yt_import.py` returns 1. |
| 15 | `MainWindow → ImportDialog → _YtScanWorker → scan_playlist` call chain threads `node_runtime` at every layer; `_YtScanWorker` captures at `__init__` not lazy in `run()` (D-08 / Pitfall 5 / Pitfall 6) | VERIFIED | `main_window.py:1405`: `ImportDialog(self.show_toast, self._repo, parent=self, node_runtime=self._node_runtime)`. `import_dialog.py:84-90`: `_YtScanWorker.__init__` keyword-only `node_runtime`, stored as `self._node_runtime`. `import_dialog.py:94-97`: `run()` forwards `node_runtime=self._node_runtime` to `scan_playlist`. `import_dialog.py:181,185`: `ImportDialog.__init__` keyword-only `node_runtime`, stored as `self._node_runtime`. `import_dialog.py:346-349`: `_YtScanWorker(url, toast_callback=self._toast, node_runtime=self._node_runtime, parent=self)`. |
| 16 | Existing `tests/test_cookies.py:157,190` assertions stay green — default `Player()` no-arg construction yields `js_runtimes == {"node": {"path": None}}` (B-79-05 / D-02 backwards-compat / Pitfall 1) | VERIFIED | `make_player(qtbot)` constructs `Player()` with no args → `self._node_runtime is None` → `build_js_runtimes(None)` → `{"node": {"path": None}}`. 79-02 SUMMARY confirms `pytest tests/test_cookies.py -x` exits 0 (17 passed). Pre-existing test_cookies.py not modified. |
| 17 | Drift-guard tests `test_player_uses_build_js_runtimes` and `test_yt_import_uses_build_js_runtimes` use positive-form count assertions against both call-site source files (B-79-DG-1 / Pitfall 8) | VERIFIED | `test_yt_dlp_opts_drift.py` confirmed: `src.count("build_js_runtimes(") == 1` for both files. No negative-form `"path": None` grep. `pathlib.Path.read_text()` used. Both assertions pass since Plans 79-02 and 79-03 landed (counts are exactly 1 each). |
| 18 | All 9 automated regression behaviors pinned (B-79-01..B-79-09) by three test files with no `pytest.fixture` or `pytest.mark.parametrize` | VERIFIED | `test_yt_dlp_opts.py` (3 tests), `test_player_node_runtime.py` (3 tests), `tests/test_yt_import_library.py` (3 new tests appended). All test functions confirmed at module top-level. |
| 19 | Live UAT (B-79-10): `.desktop`-launched MusicStreamer plays known-good YouTube live station without "Stream exhausted" toast; journalctl shows `youtube resolve: node_path=<non-None abs path>` | VERIFIED | 79-05-SUMMARY.md records PASS with verbatim journal line: `May 16 14:28:21 hurricane org.lightningjim.MusicStreamer.desktop[138854]: INFO:musicstreamer.player:youtube resolve: node_path=/home/kcreasey/.local/share/fnm/aliases/default/bin/node`. All four sign-off criteria met. |
| 20 | `musicstreamer/yt_dlp_opts.py` imports `NodeRuntime` from `musicstreamer.runtime_check` at module level; no circular import (D-10 / Pitfall 4) | VERIFIED | `yt_dlp_opts.py:line`: `from musicstreamer.runtime_check import NodeRuntime`. Runtime import test confirmed no `ImportError`. |

**Score:** 20/20 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/yt_dlp_opts.py` | `build_js_runtimes(node_runtime: NodeRuntime | None) -> dict` — single source of truth | VERIFIED | Exists, substantive, wired: imported by `player.py` and `yt_import.py`. Function body confirmed. Commit `2665067`. |
| `tests/test_yt_dlp_opts.py` | Three-input matrix (B-79-01, B-79-02, B-79-03) | VERIFIED | Exists, 3 test functions confirmed by grep. No fixtures/parametrize. Commit `19399a7`. |
| `musicstreamer/player.py` | `__init__` accepts `node_runtime` kwarg; `_youtube_resolve_worker` uses `yt_dlp_opts.build_js_runtimes` | VERIFIED | `player.py:284,286,1057-1058,1072`. Imports `yt_dlp_opts` and `NodeRuntime`. Commit `856c020`. |
| `musicstreamer/__main__.py` | Threads `node_runtime` to `Player()`; escalates `yt_import` logger | VERIFIED | `__main__.py:220,239`. `_run_smoke` at line 39 unchanged. Commit `856c020`. |
| `tests/test_player_node_runtime.py` | B-79-04, B-79-05, B-79-06 regression matrix | VERIFIED | Exists, 3 test functions. `make_player` imported from `tests.test_cookies`, not redeclared. Commit `ec5ded8`. |
| `musicstreamer/yt_import.py` | `scan_playlist` keyword-only `node_runtime` kwarg; `js_runtimes` INSERT; module logger | VERIFIED | `yt_import.py:44-47,68-69,82`. `_log` module-level binding confirmed. Commit `2f5eee9`. |
| `musicstreamer/ui_qt/import_dialog.py` | `_YtScanWorker` and `ImportDialog` both accept `node_runtime`; `run()` forwards it | VERIFIED | Lines 75-97 (`_YtScanWorker`), lines 181-185 (`ImportDialog.__init__`), lines 346-349 (instantiation). Commit `dae4dca`. |
| `musicstreamer/ui_qt/main_window.py` | `ImportDialog` ctor call at line 1405 threads `self._node_runtime` | VERIFIED | `main_window.py:1405` confirmed. Commit `dae4dca`. |
| `tests/test_yt_import_library.py` | Three new tests (B-79-07, B-79-08, B-79-09) appended; `_patch_youtubedl` helper reused | VERIFIED | 3 test functions confirmed by grep. `NodeRuntime` import present. `_patch_youtubedl` helper unchanged. Commit `57d0ca7`. |
| `tests/test_yt_dlp_opts_drift.py` | Positive-form drift-guard (B-79-DG-1) with count assertions on both call-site files | VERIFIED | Exists, 2 test functions, `pathlib.Path` only import. Both assertions confirm count == 1. Commit `6ded01c`. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `musicstreamer/yt_dlp_opts.py` | `musicstreamer.runtime_check.NodeRuntime` | module-level import | WIRED | `from musicstreamer.runtime_check import NodeRuntime` confirmed in file. |
| `musicstreamer/player.py` | `musicstreamer.yt_dlp_opts.build_js_runtimes` | module-level import + call in `_youtube_resolve_worker` | WIRED | `from musicstreamer import constants, cookie_utils, paths, yt_dlp_opts` at line 48; call at line 1072. |
| `musicstreamer/__main__.py` | `musicstreamer.player.Player` | `Player(node_runtime=node_runtime)` at line 220 | WIRED | Grep returns 1 match; `node_runtime` in scope from line 215. |
| `musicstreamer/player.py:_youtube_resolve_worker` | `musicstreamer.cookie_utils.temp_cookies_copy` | ctxmgr wraps `yt_dlp.YoutubeDL` construction (Phase 999.7 invariant) | WIRED | `grep -c "with cookie_utils.temp_cookies_copy() as cookiefile"` returns 1; position unchanged. |
| `musicstreamer/yt_import.py` | `musicstreamer.yt_dlp_opts.build_js_runtimes` | module-level import + call inside `scan_playlist` opts dict | WIRED | `from musicstreamer import constants, cookie_utils, paths, yt_dlp_opts` at line 18; call at line 82. |
| `musicstreamer/ui_qt/main_window.py` | `musicstreamer/ui_qt/import_dialog.py` | `ImportDialog(self.show_toast, self._repo, parent=self, node_runtime=self._node_runtime)` at line 1405 | WIRED | Confirmed in file. |
| `musicstreamer/ui_qt/import_dialog.py:_YtScanWorker` | `musicstreamer.yt_import.scan_playlist` | `run()` forwards `node_runtime=self._node_runtime` | WIRED | `import_dialog.py:94-97` confirmed. |
| `tests/test_yt_dlp_opts_drift.py` | `musicstreamer/player.py` + `musicstreamer/yt_import.py` | `pathlib.Path.read_text()` + `src.count("build_js_runtimes(") == 1` | WIRED | Both file reads confirmed; counts are 1 each; tests pass. |

---

### Data-Flow Trace (Level 4)

Phase 79 does not render dynamic data to UI — it is a fix that threads a value through an existing call chain. The data flow is traced programmatically:

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `Player._youtube_resolve_worker` | `self._node_runtime.path` | `runtime_check.check_node()` called in `__main__._run_gui:215`; result passed via `Player(node_runtime=node_runtime)` at line 220 | Yes — fnm/volta/asdf fallback resolves absolute path from `$HOME`-rooted candidates | FLOWING |
| `yt_import.scan_playlist` | `node_runtime` kwarg | `MainWindow._open_import_dialog` → `ImportDialog(node_runtime=self._node_runtime)` → `_YtScanWorker(node_runtime=self._node_runtime)` → `scan_playlist(node_runtime=self._node_runtime)` | Yes — same `runtime_check.check_node()` origin | FLOWING |

Live UAT journal line (`node_path=/home/kcreasey/.local/share/fnm/aliases/default/bin/node`) confirms the data is non-None and flows end-to-end from `runtime_check` to yt-dlp at `.desktop` launch time.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `build_js_runtimes(None)` returns correct dict | `.venv/bin/python -c "from musicstreamer.yt_dlp_opts import build_js_runtimes; print(build_js_runtimes(None))"` | `{'node': {'path': None}}` | PASS |
| `build_js_runtimes(NodeRuntime(True, '/fake/node'))` threads path | `.venv/bin/python -c "... print(build_js_runtimes(NodeRuntime(available=True, path='/fake/node')))"` | `{'node': {'path': '/fake/node'}}` | PASS |
| `build_js_runtimes(NodeRuntime(False, None))` returns None path | `.venv/bin/python -c "... print(build_js_runtimes(NodeRuntime(available=False, path=None)))"` | `{'node': {'path': None}}` | PASS |
| Drift-guard counts (both files have exactly 1 call) | `python3 -c "from pathlib import Path; ..."` | `player.py count: 1, yt_import.py count: 1` | PASS |

---

### Probe Execution

No conventional `scripts/*/tests/probe-*.sh` probes declared or discoverable for this phase. The automated test matrix serves as the probe equivalent.

| Probe | Command | Result | Status |
|-------|---------|--------|--------|
| B-79-10 live UAT | `.desktop` launch + journalctl observation (Plan 79-05) | `youtube resolve: node_path=/home/kcreasey/.local/share/fnm/aliases/default/bin/node` | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| BUG-11 | 79-01, 79-02, 79-03, 79-04, 79-05 | YouTube live-stream playback works when launched via GNOME `.desktop` entry with version-manager-only Node | SATISFIED | All 6 enumerated sub-requirements in REQUIREMENTS.md BUG-11 description are implemented and verified: (1) `Player.__init__` node_runtime kwarg + `yt_dlp_opts.build_js_runtimes` helper; (2) `scan_playlist` node_runtime kwarg + js_runtimes INSERT; (3) `__main__._run_gui` threads node_runtime to `Player()`; (4) INFO log lines at both call sites; (5) `yt_import` logger escalated to INFO in `__main__.main`; (6) unit+integration regression tests on both call sites. Live UAT (B-79-10) confirmed PASS with fnm-rooted non-None node_path. |

**Note:** `REQUIREMENTS.md` still shows `[ ] BUG-11` and `Pending` in the traceability table. The 79-05-SUMMARY.md explicitly calls for flipping this to `[x]` and `Complete` as the final output of Plan 79-05. This is a documentation update that is not yet applied. The implementation is fully complete in the codebase; the checkbox flip is a housekeeping step for the orchestrator.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | — | — | — |

No `TBD`, `FIXME`, or `XXX` markers found in any Phase 79 modified file. No unreferenced debt markers. No stub return values, no hardcoded empty data flowing to rendering. The "placeholder" keyword match in `main_window.py:1176` is a pre-existing legitimate docstring describing the create-station flow — not introduced by Phase 79 and not a stub pattern.

---

### Human Verification Required

None. The live UAT (B-79-10) was completed by the user in Plan 79-05 with all four sign-off criteria met and journal evidence captured. No further human verification items remain.

---

### Gaps Summary

No gaps. All 20 must-have truths are verified against the actual codebase:

- `musicstreamer/yt_dlp_opts.py` exists, is substantive, is wired to both call sites, and data flows through it.
- All 10 test files/functions exist with correct structure, correct assertions, and confirmed behavior.
- The full call chain from `runtime_check.check_node()` through `__main__` → `Player` → `_youtube_resolve_worker` → `yt_dlp.YoutubeDL(opts)` and the parallel scan chain `MainWindow` → `ImportDialog` → `_YtScanWorker` → `scan_playlist` → `yt_dlp.YoutubeDL(opts)` are both wired and data-flowing.
- All 8 commits (2665067, 19399a7, 856c020, ec5ded8, 2f5eee9, dae4dca, 57d0ca7, 6ded01c) exist in git.
- Live UAT journal evidence confirms the fix operates end-to-end under the original bug-reproduction context.

The only post-phase housekeeping item is flipping `BUG-11` from `[ ]` to `[x]` in `REQUIREMENTS.md` and updating the traceability table status from `Pending` to `Complete` — this is documentation, not a code gap.

---

_Verified: 2026-05-16_
_Verifier: Claude (gsd-verifier)_
