# Phase 79: Fix YouTube 'stream exhausted' when launched via desktop app — Research

**Researched:** 2026-05-16
**Domain:** yt-dlp library-API JS-runtime resolution + Linux .desktop launcher PATH stripping
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Fix mechanism**
- **D-01:** Pass resolved node path into yt-dlp opts. Replace inline `{"node": {"path": None}}` literal at `player.py:1063` (and the parallel path in `yt_import.py`) with a call to a shared helper that reads from `NodeRuntime.path`. Rejected: `os.environ['PATH']` augmentation, belt-and-braces both.
- **D-02:** When `node_runtime.path` is None, preserve today's `{"path": None}` behavior. yt-dlp may still resolve JS-free streams (live HLS manifests); short-circuiting would regress those.
- **D-03:** Single code path for Linux and Windows. No `sys.platform` gate; `NodeRuntime.path` is already platform-aware.
- **D-04:** Regression-test bar = unit test asserting `opts["js_runtimes"]["node"]["path"] == <injected abs>`. Monkeypatch `yt_dlp.YoutubeDL` to record opts. Matrix covers three NodeRuntime inputs (None / available+path / unavailable+None).

**Plumbing route**
- **D-05:** `Player.__init__` grows `node_runtime: NodeRuntime | None = None` kwarg. Mirrors `MainWindow.__init__(node_runtime=None)` at `main_window.py:195-202`.
- **D-06:** `node_runtime=None` is the default. Backwards-compat for `_run_smoke` and existing tests.
- **D-07:** `__main__._run_gui` passes the existing `node_runtime` (already detected at line 215) to `Player()`.
- **D-08:** `yt_import.scan_playlist` grows a `node_runtime: NodeRuntime | None = None` kwarg. Same dependency-injection shape as Player.

**yt_import parity**
- **D-09:** Fix BOTH yt-dlp call sites in this phase. Leaving the playlist-import dialog for a follow-up would intentionally ship a known bug.
- **D-10:** New module `musicstreamer/yt_dlp_opts.py` is the single source of truth for `js_runtimes`. Public surface: `build_js_runtimes(node_runtime: NodeRuntime | None) -> dict`.
- **D-11:** Helper is strictly scoped to `js_runtimes`. Does NOT own `format`, `remote_components`, `quiet`, `skip_download`, `cookiefile`, `extract_flat`.

**Error visibility**
- **D-12:** Keep existing `_on_playback_error` toast machinery; no new branch. After the fix, the "found via fallback but yt-dlp rejected it" case is structurally eliminated.
- **D-13:** Add ONE INFO log line per YT play in `_youtube_resolve_worker` AND `scan_playlist` showing the resolved node path: `_log.info("youtube resolve: node_path=%s", <abs|None>)`.

### Claude's Discretion

- **Helper function name** — `build_js_runtimes(node_runtime)` is the working name. Planner may pick alternative if it reads better. Single function; not a class.
- **Import-dialog plumbing** — dialog constructor kwarg vs accessing `parent._node_runtime` directly. Recommendation: constructor kwarg for explicitness.
- **Test fixture for `NodeRuntime`** — inline literals vs small `@pytest.fixture` helper. Recommendation: inline.
- **Drift-guard test** — grep source for the literal `"path": None` inside `js_runtimes` dicts. Recommendation: YES if one-liner via `tests/test_packaging_spec.py` shape.

### Deferred Ideas (OUT OF SCOPE)

- `os.environ['PATH']` augmentation at startup
- Short-circuiting yt-dlp when Node absent
- New toast category for "Node found but yt-dlp rejected" case
- Expanding `yt_dlp_opts.py` to own `remote_components`, `format`, `cookiefile`, etc.
- Diagnostic-only / log-first phase
- Re-probing for non-PATH env diffs between `.desktop` and pipx-from-terminal
- Changes to `runtime_check.check_node()` or `_which_node_version_manager_fallback`
- Drift-guard for `"path": None` literal (Claude's Discretion — may include preemptively)
- Parallel env-diff investigation, PyInstaller/Windows installer changes
</user_constraints>

## Project Constraints (from CLAUDE.md)

CLAUDE.md routes to `Skill("spike-findings-musicstreamer")` for Windows-packaging / GStreamer / PyInstaller patterns. **Not applicable to this phase** — Phase 79 is a Linux `.desktop` launcher bug with a cross-platform fix. No spike-findings consultation required during planning or execution.

Other project conventions (from `.planning/codebase/CONVENTIONS.md`):
- snake_case + type hints throughout, no formatter
- Modern union syntax (`X | Y` not `Union[X, Y]`)
- Imports ordered: future, stdlib, third-party, `musicstreamer.*` (absolute)
- No new dependencies (yt-dlp and runtime_check already imported)
- `# noqa: BLE001` for top-level `except Exception` in worker threads (already used in `_youtube_resolve_worker`)

## Phase Requirements

CONTEXT.md `<canonical_refs>` notes that no Phase 79 requirement entry exists in `.planning/REQUIREMENTS.md` yet. Planner SHOULD add an entry parallel to BUG-09 / BUG-07:

| ID | Description | Research Support |
|----|-------------|------------------|
| BUG-11 *(proposed)* | YouTube live-stream playback works when MusicStreamer is launched via the GNOME `.desktop` entry (not only via pipx-from-terminal). | This research; threading `NodeRuntime.path` through to yt-dlp's `js_runtimes` opts in both `player._youtube_resolve_worker` and `yt_import.scan_playlist`. |

The new ID number must be confirmed against REQUIREMENTS.md to avoid collisions (existing pending: BUG-10 at Phase 80; the next available BUG-* slot is BUG-11).

## Summary

Phase 79 fixes a confirmed, narrow regression: launching MusicStreamer via the GNOME `.desktop` entry produces "Stream exhausted" on YouTube stations 100% of the time when Node.js is installed via fnm/nvm/volta/asdf, while launching the same install via a terminal works. The bug is direct-readable in `musicstreamer/player.py:1063`: the yt-dlp library-API opts dict carries a hard-coded `"js_runtimes": {"node": {"path": None}}`. yt-dlp's `NodeJsRuntime._info` resolves `path=None` by returning the literal `"node"` (on non-Windows; see `yt_dlp/utils/_jsruntime.py:59-64`), and the subsequent `subprocess.run(["node", "--version"])` fails under the `.desktop`-stripped PATH where version-manager shims are absent — even though `runtime_check.check_node()` already correctly resolved the absolute path at startup via `_which_node_version_manager_fallback`.

Phase 999.9 added the `js_runtimes` dict in the first place (commit message preserved in `player.py:1058-1063`), but at the time `path: None` was sufficient because the user had Node on a stable PATH location. The 2026-04-25 fnm/nvm/volta/asdf fallback (commit `a06549f`) made detection robust without changing the threading. Phase 79 finishes the same fix by passing the detected path THROUGH to yt-dlp opts in **both** call sites (`Player._youtube_resolve_worker` and `yt_import.scan_playlist`).

**Primary recommendation:** Add a new module `musicstreamer/yt_dlp_opts.py` exporting `build_js_runtimes(node_runtime: NodeRuntime | None) -> dict` (returns `{"node": {"path": node_runtime.path}}` when `node_runtime is not None`, else `{"node": {"path": None}}`). Thread `node_runtime` via constructor kwargs to `Player` and `scan_playlist`. Mirror the existing `MainWindow.__init__(node_runtime=None)` pattern. Add five unit tests (3 for the helper, 1 each for the two integration sites) plus one INFO log line per yt-dlp call site for live-debugging visibility.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Node.js detection (fnm/nvm/volta/asdf fallback) | Detection helper (`runtime_check.py`) | — | Already correct; consumed by — not changed in — Phase 79 |
| Carrying `NodeRuntime` from startup to consumers | Process bootstrap (`__main__._run_gui`) | UI ctor (`MainWindow`), Player ctor, dialog ctor | Single detection at startup, fan-out via DI |
| Threading node path into yt-dlp opts | New helper module (`yt_dlp_opts.py`) | Player + yt_import call sites | Single source of truth for js_runtimes shape |
| Resolving YouTube streams to HLS | Worker thread inside Player (`_youtube_resolve_worker`) | — | Existing; gains node_runtime input + INFO log |
| Scanning YouTube playlists | `yt_import.scan_playlist` (called from `_YtScanWorker` QThread in ImportDialog) | — | Existing; gains node_runtime kwarg + INFO log |
| Surfacing playback errors | `MainWindow._on_playback_error` toast | — | Existing; unchanged (D-12) |

**Why this matters for planning:** The fix is exclusively in the **plumbing tier** (dependency injection of an already-detected value). No runtime detection or PATH-mutation code is added. The yt-dlp library and the Node.js installation are external dependencies; this phase touches neither.

## Standard Stack

### Already in use (no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `yt-dlp` | 2026.03.17 (verified via `python3 -c 'import yt_dlp; print(yt_dlp.version.__version__)'`) | YouTube stream resolution via library API (Plan 35-06) | Already the YouTube backend; replacing it is out of scope |
| `runtime_check.NodeRuntime` | in-tree (`musicstreamer/runtime_check.py`) | Node detection + version-manager fallback (Phase 44 + 2026-04-25 commit `a06549f`) | Existing dataclass; this phase consumes its `.path` attribute |

### New module to add

| Module | Purpose | Pattern source |
|--------|---------|----------------|
| `musicstreamer/yt_dlp_opts.py` (new file, ~20 LOC) | Build `js_runtimes` opts dict from `NodeRuntime` | Mirrors `cookie_utils.py`, `url_helpers.py`, `subprocess_utils.py` (focused tiny-module pattern documented in CONVENTIONS.md) |

### Alternatives Considered

| Instead of | Could Use | Why Rejected |
|------------|-----------|--------------|
| Helper module | Inline literal at both call sites | Drift risk between the two sites; D-10 chose single source of truth |
| `os.environ['PATH']` augmentation | Mutate process PATH at startup | Too broad — changes behavior for streamlink, oauth_helper, every subprocess. D-01 rejects. |
| Required kwarg `Player(node_runtime=...)` | Make kwarg required | Breaks `_run_smoke` and `tests/test_cookies.py::make_player(qtbot)` which constructs `Player()` directly. D-06 rejects. |
| `runtime_check` module-level cache | Player calls `check_node()` itself | Hidden global state; redundant probes per YT play. D-05 rejects. |
| Short-circuit when Node absent | Skip yt-dlp entirely when `node_runtime.available is False` | Some YT streams resolve without JS (live HLS manifests). D-02 rejects. |

**Installation:** None. No new pyproject.toml entries.

**Version verification (Linux dev box, 2026-05-16):**
```bash
$ python3 -c "import yt_dlp; print(yt_dlp.version.__version__)"
2026.03.17
$ command -v node
/home/kcreasey/.local/share/fnm/node-versions/v25.9.0/installation/bin/node
$ node --version
v25.9.0
```
[VERIFIED: dev box probe at research time] yt-dlp version pinned by `pyproject.toml`; Node v25.9.0 is via fnm's version-manager layout (the exact scenario `_which_node_version_manager_fallback` was written for, commit `a06549f`).

## Package Legitimacy Audit

This phase installs **no new external packages**. The single new module is in-tree (`musicstreamer/yt_dlp_opts.py`). All dependencies (`yt_dlp`, `runtime_check`) are already used by `player.py` and `yt_import.py` today.

**Disposition: N/A — no `pip install` step in plan.** Slopcheck not required.

## Architecture Patterns

### System Architecture Diagram

```
                        startup
                           │
        ┌──────────────────┴───────────────────┐
        │  __main__._run_gui (line 215)        │
        │   node_runtime = check_node()        │
        │   ├─ shutil.which("node") OR         │
        │   └─ _which_node_version_manager_    │
        │      fallback (fnm/nvm/volta/asdf)   │
        └──────────────────┬───────────────────┘
                           │  passes node_runtime via ctor kwarg
                           ▼
        ┌───────────────────────────────────────────────────────────────┐
        │                                                               │
        ▼                                                               ▼
┌───────────────────────────┐                          ┌──────────────────────────────┐
│ Player(node_runtime=...)  │                          │ MainWindow(node_runtime=...) │
│   stores self._node_runtime│                         │   stores self._node_runtime  │
└──────────┬────────────────┘                          │   (already in place)         │
           │                                            └──────────┬───────────────────┘
           │ ImportDialog opens                                    │
           │   (threading-discretion-A or -B per below)            │
           │                                                       ▼
           │                                            ┌──────────────────────────────┐
           │                                            │ ImportDialog                 │
           │                                            │   YouTube tab → _YtScanWorker│
           │                                            │   .run() calls               │
           │                                            │   yt_import.scan_playlist(   │
           │                                            │     node_runtime=...)        │
           ▼                                            └──────────┬───────────────────┘
┌──────────────────────────────┐                                   │
│ Player._play_youtube(url)    │                                   │
│   spawns worker thread →     │                                   │
│ Player._youtube_resolve_worker│                                  │
│   (1) corruption check       │                                   │
│   (2) build opts:            │                                   │
│   "js_runtimes":             │                                   │
│   yt_dlp_opts.build_         │                                   │
│   js_runtimes(self._node_    │                                   │
│   runtime)                   │                                   │
│   (3) INFO log: node_path=…  │                                   │
│   (4) yt_dlp.YoutubeDL(opts) │                                   │
└──────────┬───────────────────┘                                   │
           │                                                       │
           └──────────────┬────────────────────────────────────────┘
                          │  shared helper, single source of truth
                          ▼
        ┌───────────────────────────────────────────────────┐
        │ yt_dlp_opts.build_js_runtimes(node_runtime)       │
        │   if node_runtime is None or node_runtime.path    │
        │      is None:                                     │
        │     return {"node": {"path": None}}               │
        │   return {"node": {"path": node_runtime.path}}    │
        └───────────────────────────────────────────────────┘
                          │
                          ▼
        ┌───────────────────────────────────────────────────┐
        │ yt-dlp's NodeJsRuntime._info()                    │
        │   path = _determine_runtime_path(path, "node")    │
        │   ├─ if path: use as-is                           │
        │   └─ if None: _find_exe("node")                   │
        │      └─ non-Windows: return literal "node"        │
        │      └─ Windows: scan PATH + cwd + PATHEXT        │
        │   subprocess(["{path}", "--version"])             │
        │   ✓ succeeds → JsRuntimeInfo(supported=True)      │
        │   ✗ fails → returns None → "No video formats…"    │
        └───────────────────────────────────────────────────┘
```

### File-level Change Inventory

| File | Action | Lines (estimate) |
|------|--------|------------------|
| `musicstreamer/yt_dlp_opts.py` | CREATE | ~25 (incl. docstring) |
| `musicstreamer/player.py` | EDIT — Player.__init__ kwarg + storage; _youtube_resolve_worker opts + INFO log + import | +5, modified |
| `musicstreamer/yt_import.py` | EDIT — scan_playlist signature + opts + INFO log + module logger + import | +6, modified |
| `musicstreamer/__main__.py` | EDIT — `Player(node_runtime=node_runtime)` at line 220 | +1 token |
| `musicstreamer/ui_qt/import_dialog.py` | EDIT — thread node_runtime through to scan_playlist | ~5 lines (signature + storage + forward to worker) |
| `musicstreamer/ui_qt/main_window.py` | EDIT — pass node_runtime to ImportDialog constructor at line 1405 | +1 token |
| `tests/test_yt_dlp_opts.py` | CREATE | ~40 |
| `tests/test_player.py` (or new `tests/test_player_node_runtime.py`) | EXTEND | ~50 (three-case regression test) |
| `tests/test_yt_import_library.py` | EXTEND | ~50 (three-case regression test) |
| `tests/test_packaging_spec.py` (or new `tests/test_yt_dlp_opts_drift.py`) | EXTEND (optional, Claude's Discretion) | ~25 |

### Recommended Project Structure

```
musicstreamer/
├── runtime_check.py          # UNCHANGED — source of NodeRuntime + check_node()
├── yt_dlp_opts.py            # NEW — build_js_runtimes(node_runtime) helper
├── cookie_utils.py           # sibling pattern reference
├── url_helpers.py            # sibling pattern reference
├── subprocess_utils.py       # sibling pattern reference
├── player.py                 # EDIT — Player.__init__ kwarg + _youtube_resolve_worker rewire
├── yt_import.py              # EDIT — scan_playlist kwarg + opts rewire + module logger
├── __main__.py               # EDIT — pass node_runtime to Player() at line 220
└── ui_qt/
    ├── main_window.py        # EDIT — pass node_runtime to ImportDialog ctor
    └── import_dialog.py      # EDIT — accept and forward node_runtime
tests/
├── test_yt_dlp_opts.py       # NEW — 3 helper tests (None / available / unavailable)
├── test_player.py            # EXTEND — opts-recording regression test (3 NodeRuntime inputs)
└── test_yt_import_library.py # EXTEND — opts-recording regression test (3 NodeRuntime inputs)
```

### Pattern 1: New `yt_dlp_opts.py` module shape

**What:** A tiny focused module with a single public function. Mirrors `cookie_utils.py` shape (already imported by `player.py` and `yt_import.py`).

**When to use:** Always — this is the locked design (D-10, D-11).

**Reference template (mirrors `musicstreamer/cookie_utils.py` header):**
```python
"""Shared helper for building yt-dlp's js_runtimes opts dict.

Provides:
  - build_js_runtimes(node_runtime: NodeRuntime | None) -> dict
      Returns the shape yt-dlp's library API expects:
      {"node": {"path": <abs-path-or-None>}}.
      When node_runtime is None or its path is None, yields
      {"node": {"path": None}} — yt-dlp then runs its own PATH lookup
      (which may succeed for pipx-from-terminal launches and fails
      under the .desktop launch context where version-manager shims
      are missing).

Phase 79 — single source of truth used by both yt-dlp call sites:
  - musicstreamer/player.py::_youtube_resolve_worker
  - musicstreamer/yt_import.py::scan_playlist

Why a module: yt-dlp's library API does NOT auto-discover JS runtimes
the way the CLI does (Phase 999.9 baseline). When the path resolved by
musicstreamer.runtime_check.check_node() is not passed through, yt-dlp's
NodeJsRuntime._info() resolves path=None → "node" literal → subprocess
fails under the .desktop-stripped PATH.

Reference: yt_dlp/utils/_jsruntime.py::_determine_runtime_path (yt-dlp
2026.03.17).
"""
from __future__ import annotations

from musicstreamer.runtime_check import NodeRuntime


def build_js_runtimes(node_runtime: NodeRuntime | None) -> dict:
    """Return js_runtimes opts dict for yt_dlp.YoutubeDL.

    Returns the shape yt-dlp's library API expects:
      {"node": {"path": <abs-path-or-None>}}

    When node_runtime is None or its path is None, returns
    {"node": {"path": None}} (preserves yt-dlp's own PATH-lookup behavior
    for the genuinely-absent case).
    """
    path = node_runtime.path if node_runtime is not None else None
    return {"node": {"path": path}}
```

[CITED: musicstreamer/cookie_utils.py — sibling pattern]

### Pattern 2: Constructor kwarg DI (mirrors `MainWindow.__init__`)

**What:** `Player.__init__` and `scan_playlist` grow a `node_runtime: NodeRuntime | None = None` kwarg, identical in shape to the existing `MainWindow.__init__(node_runtime=None)` at `main_window.py:195-202`.

**When to use:** Always — Phase 79's locked plumbing pattern.

**Reference template (verbatim shape from `main_window.py:190-202`):**
```python
# In musicstreamer/player.py — Player class body:
def __init__(self, parent: QObject | None = None,
             *, node_runtime: "NodeRuntime | None" = None) -> None:
    super().__init__(parent)
    self._node_runtime = node_runtime
    # ... existing body unchanged
```

The forward-reference string `"NodeRuntime | None"` avoids a circular import. `from musicstreamer.runtime_check import NodeRuntime` belongs in a `TYPE_CHECKING` block OR at module level (runtime_check does not import player, so direct import is safe — see Pitfall 4 below).

### Pattern 3: Module logger for yt_import

**What:** `yt_import.py` currently has no module logger. Phase 79 adds one (for D-13 INFO log).

**Reference template (mirrors `musicstreamer/player.py:78`):**
```python
# Top of musicstreamer/yt_import.py, near other imports:
import logging
_log = logging.getLogger(__name__)
```

The logger name `musicstreamer.yt_import` will inherit from root logger (`logging.basicConfig(level=logging.WARNING)` in `__main__.main`). If the user wants the INFO line surfaced, planner adds:
```python
# In __main__.main, alongside the existing player + soma_import lines (235-236):
logging.getLogger("musicstreamer.yt_import").setLevel(logging.INFO)
```

This is consistent with the Phase 62 / Phase 74 pattern for per-logger INFO escalation (existing precedent at `__main__.py:235-236`).

### Pattern 4: Test-side `monkeypatch yt_dlp.YoutubeDL` opts-recording

**What:** Capture the opts dict by stubbing `yt_dlp.YoutubeDL` with a Fake that records `__init__`'s first arg. Existing tests already do this — extend with NodeRuntime assertions.

**Reference template (verbatim from `tests/test_yt_import_library.py:30-42`):**
```python
def _patch_youtubedl(extract_info_return=None, extract_info_side_effect=None):
    fake_ydl = MagicMock()
    if extract_info_side_effect is not None:
        fake_ydl.extract_info.side_effect = extract_info_side_effect
    else:
        fake_ydl.extract_info.return_value = extract_info_return
    cm = MagicMock()
    cm.__enter__.return_value = fake_ydl
    cm.__exit__.return_value = False
    youtubedl_cls = MagicMock(return_value=cm)
    return patch("musicstreamer.yt_import.yt_dlp.YoutubeDL", youtubedl_cls), youtubedl_cls, fake_ydl
```

For Player-side opts recording, the equivalent pattern is `tests/test_cookies.py:120-158` (FakeYDL class that captures `opts` on `__init__`). Phase 79's new tests can reuse either idiom.

### Pattern 5: Helper-function name (Claude's Discretion)

Candidates in style-order:
1. **`build_js_runtimes(node_runtime)`** — the working name from CONTEXT.md. Reads as "build the js_runtimes dict". Verb-first like `is_yt_playlist_url`, `aa_normalize_stream_url`. **Recommended.**
2. `js_runtimes_opts(node_runtime)` — noun-first; matches `temp_cookies_copy()` shape but less imperative.
3. `node_js_runtime_opts(node_runtime)` — overly specific, locks scope (D-11 already says the helper IS js_runtimes-only, so the name needn't repeat).

### Anti-Patterns to Avoid

- **Hidden global state via module-level cache in `runtime_check.py`** — explicitly rejected (D-05). Tests cannot easily inject; risks redundant probes per call.
- **Calling `check_node()` inside Player or scan_playlist** — explicitly rejected (D-05). Couples consumers to detection; runs detection more than once per process.
- **Owning more yt-dlp opts in the helper** — explicitly rejected (D-11). `format`, `remote_components`, `cookiefile`, `extract_flat` differ between sites; centralizing would couple unrelated decisions.
- **Required kwarg for `node_runtime`** — rejected (D-06). Breaks `_run_smoke` and the existing `make_player(qtbot)` helper in `tests/test_cookies.py:21-30` and `tests/test_player.py:16-33`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Locating `node` on disk | `subprocess.run(["which", "node"])` or custom path probe | `runtime_check.check_node()` — already detects fnm/nvm/volta/asdf | Phase 44 + commit `a06549f` already solved this; reuse the existing `NodeRuntime` instance from `_run_gui`. |
| Wrapping yt-dlp's JS-runtime registry | New class to manage `JsRuntime` instances | yt-dlp's `supported_js_runtimes` global — accepts plain `{"node": {"path": "<abs>"}}` dict | yt-dlp's library API takes a dict opt directly. The `NodeJsRuntime` class is constructed from the path internally. |
| Cross-platform `node` vs `node.exe` resolution | Custom Windows-vs-Linux branch in the helper | `runtime_check._which_node` (already platform-aware: prefers `.exe` on win32, plain `node` on POSIX) | Single code path per D-03. The resolved path string is whatever the OS gives us; yt-dlp's `_determine_runtime_path` does not transform it further. |
| Detecting `.desktop`-stripped PATH at runtime | Probe `os.environ['PATH']` for fnm/nvm/asdf paths inside Player | Trust `NodeRuntime.path` from `check_node()` | The fallback already runs the relevant home-directory probes; downstream consumers should not duplicate the heuristic. |

**Key insight:** Phase 79 is exclusively a wiring change. The two pieces it joins (`NodeRuntime.path` from `runtime_check`, and yt-dlp's `js_runtimes` opt) are both stable, documented, and already in the codebase. Anything beyond plumbing belongs in another phase.

## Common Pitfalls

### Pitfall 1: `tests/test_cookies.py:157,190` already asserts `js_runtimes == {"node": {"path": None}}`

**What goes wrong:** After Phase 79's edit at `player.py:1063`, if the test helper `make_player(qtbot)` is left unchanged and Phase 79's `Player.__init__(node_runtime=None)` default is honored, the existing assertion at `tests/test_cookies.py:157` and `tests/test_cookies.py:190` **continues to pass by construction** — the helper constructs `Player()` with no args, so `self._node_runtime is None`, so `build_js_runtimes(None) == {"node": {"path": None}}`. **This is the intended D-06 backwards-compat behavior.**

**Why it works:** `make_player(qtbot)` at `tests/test_cookies.py:21-30` and `tests/test_player.py:16-33` constructs `Player()` with no kwargs. Default `node_runtime=None` preserves the historical `{"path": None}` shape that the cookie tests already assert.

**How to avoid:** Do NOT delete or modify the `make_player` helper. Phase 79's new regression tests for the `available=True, path="/fake/node"` case construct `Player(node_runtime=NodeRuntime(...))` explicitly (one-liner inline literal per CONTEXT.md Claude's Discretion).

**Verification at plan-time:** Grep `tests/test_cookies.py` for `js_runtimes` — should find only the two existing assertions (lines 157, 190). Both stay green unchanged.

### Pitfall 2: CONTEXT.md `<code_context>` line 73-ish reference is stale — `scan_playlist` does NOT currently set `js_runtimes`

**What goes wrong:** CONTEXT.md says "replace the literal js_runtimes" at "yt_import.py:73-ish". **The actual `scan_playlist` opts dict at `musicstreamer/yt_import.py:62-71` does NOT set `js_runtimes` at all** — yt-dlp's `_clean_js_runtimes` defaults it to `{'deno': {}}` (`yt_dlp/YoutubeDL.py:735`). Phase 79 is ADDING `js_runtimes` to `scan_playlist`'s opts, not replacing an existing literal.

**Why it happens:** Drift between CONTEXT.md prose and the live code. The literal exists in `player.py:1063` but never landed in `yt_import.py`.

**How to avoid:** Planner must verify exact insertion points by reading the live code before writing the plan. The new line for `scan_playlist` is an **insertion** into the opts dict, not a substitution. Recommended insertion site: after the `"skip_download": True` line, before the `"remote_components"` line — preserves alphabetical-ish grouping.

**Practical impact:** `extract_flat='in_playlist'` at `yt_import.py:63` means yt-dlp's `process_ie_result` short-circuits per-entry resolution at `yt_dlp/YoutubeDL.py:1894-1909` and does NOT invoke per-entry JS solving. So the scan-side js_runtimes addition is **defensive parity** — it pre-empts a future bug if the scan path stops using `extract_flat`, and keeps the single-source-of-truth invariant (D-10). The reported "stream exhausted" bug surface is exclusively the playback path (`Player._youtube_resolve_worker`), not the scan path.

**Test consequence:** The `scan_playlist` regression test (`tests/test_yt_import_library.py`) asserts `opts["js_runtimes"]["node"]["path"]` shape but does NOT depend on `extract_flat` execution to surface the bug — it just verifies the opts dict is wired correctly. Both the playback-side and scan-side tests are equally rigorous; only the live UAT defines which path the user actually exercises.

### Pitfall 3: `_youtube_resolve_worker` is a daemon thread — emitting the INFO log inside a `try/except` matters

**What goes wrong:** The INFO log line for D-13 must NOT itself raise inside the top-level `try/except Exception` backstop at `player.py:1097`. The `_log.info(...)` call is unlikely to raise, but `self._node_runtime.path if self._node_runtime else None` is the safer formulation than `self._node_runtime and self._node_runtime.path` (which masks the path-is-None case).

**Why it happens:** Python truthy short-circuits treat `None` and the empty-string path identically. The conditional expression preserves the distinction (which yt-dlp itself disambiguates).

**How to avoid:** Use the explicit conditional: `node_path = self._node_runtime.path if self._node_runtime else None; _log.info("youtube resolve: node_path=%s", node_path)`. Mirror exactly in `scan_playlist`.

### Pitfall 4: `Player` importing `NodeRuntime` from `runtime_check` — circular-import check

**What goes wrong:** Adding `from musicstreamer.runtime_check import NodeRuntime` to `player.py` could in theory create a cycle.

**Verification:** `musicstreamer/runtime_check.py` imports `PySide6.QtWidgets.QMessageBox` (line 20) but does NOT import from `musicstreamer.player`. So `player.py` → `runtime_check` → `PySide6` is acyclic. **Safe to import at module level.**

**Alternative:** Use a `TYPE_CHECKING` guard + string forward reference. Either is fine.

[VERIFIED: grep `from musicstreamer.player` in `runtime_check.py` returns no results]

### Pitfall 5: `ImportDialog` constructor signature change is a tier-2 ripple

**What goes wrong:** Adding `node_runtime` to `ImportDialog.__init__` requires updating both call sites in `main_window.py`:
- `main_window.py:1405` — `_open_import_dialog` — currently `ImportDialog(self.show_toast, self._repo, parent=self)`.
- (no other production call site exists; grep verified)

**Test ripple:** `tests/test_import_dialog.py` and `tests/test_import_dialog_qt.py` construct `ImportDialog` directly. If Phase 79 makes `node_runtime` a keyword-only kwarg with default None, **no test changes are required** (D-06 backwards-compat).

**How to avoid:** Make `node_runtime` keyword-only with default None. Grep `ImportDialog(` in tests/ to confirm no positional-argument call sites exist (a quick `grep -rn 'ImportDialog(' tests/ musicstreamer/` at plan-time before edit).

### Pitfall 6: `_YtScanWorker` is a `QThread`, not a daemon `threading.Thread` — node_runtime threading shape differs

**What goes wrong:** `Player._youtube_resolve_worker` runs as a `daemon=True threading.Thread` and reads `self._node_runtime` directly (closure-via-self). `_YtScanWorker` is a `QThread` subclass with `__init__` capture — `node_runtime` must be passed through `_YtScanWorker.__init__(self, url, toast_callback, node_runtime=None, parent=None)` and stored on `self._node_runtime` for `run()` to forward to `scan_playlist`.

**Why it matters:** Storing `node_runtime` as `_YtScanWorker._node_runtime` is the safe pattern. Reading it from the dialog parent inside `run()` would cross the GIL into the dialog's QObject lifetime (the dialog could close mid-scan — `_YtScanWorker.wait()` defends against this but the dialog ctor is the cleanest anchor).

**How to avoid:** Thread `node_runtime` via the dialog ctor → store on `self._node_runtime` → pass to `_YtScanWorker(..., node_runtime=self._node_runtime)` → store on the worker → forward to `scan_playlist(..., node_runtime=self._node_runtime)` in `run()`. Four lines total.

**Reference call chain (lines verified 2026-05-16):**
- `main_window.py:1405` → `ImportDialog(self.show_toast, self._repo, parent=self)` — add `node_runtime=self._node_runtime`
- `import_dialog.py:173` → `ImportDialog.__init__(self, toast_callback, repo, parent=None)` — add `*, node_runtime: NodeRuntime | None = None`, store `self._node_runtime`
- `import_dialog.py:78-93` → `_YtScanWorker(url, toast_callback, parent)` — add `node_runtime` arg, store on worker
- `import_dialog.py:90` → `yt_import.scan_playlist(self._url, toast_callback=self._toast)` — add `node_runtime=self._node_runtime`

### Pitfall 7: yt-dlp's `_find_exe` checks `sysconfig.get_path('scripts')` first — pipx-bundled binaries are found WITHOUT PATH

**What goes wrong (informational, NOT a regression):** When `path=None`, yt-dlp's `_find_exe` at `yt_dlp/utils/_jsruntime.py:17-22` first checks `sysconfig.get_path('scripts')` — that is, the pipx venv's `bin/` directory. **If Node were bundled in the pipx venv, the bug would never have surfaced.** It's not bundled (Node is the user's system install via fnm), so the fallback path returns `"node"` literal and subprocess fails.

**Why this matters for planning:** This is why the bug is so narrow — it only surfaces when:
1. The yt-dlp library API is invoked (i.e. not the CLI)
2. `path=None` is passed
3. Node is NOT in the pipx venv's `bin/` dir
4. Node is NOT on the inherited PATH (i.e. `.desktop`-stripped)
5. Node IS resolvable via a version-manager shim that `_which_node_version_manager_fallback` knows about

Phase 79's fix (always pass the resolved path) makes the bug impossible at the test-recordable opts layer, independent of any of those five conditions.

**Reference:** `yt_dlp/utils/_jsruntime.py:16-56` [CITED: yt-dlp 2026.03.17].

### Pitfall 8: Drift-guard for `"path": None` would need to allow the helper's OWN literal

**What goes wrong:** A test like `grep -rn '"path": None' musicstreamer/` would correctly flag a future regression — but would also flag `yt_dlp_opts.py` itself, where `path = None` literally appears in the return for the absent case.

**How to avoid (if drift-guard is added per Claude's Discretion):** Scope the grep to `player.py` and `yt_import.py` only; exclude `yt_dlp_opts.py`. Or assert the inline `"path": None` literal is absent INSIDE a dict whose preceding context contains `"js_runtimes"` (a stricter regex). The simpler scoped form (file-list exclusion) is the project-precedent shape per `tests/test_packaging_spec.py`.

**Recommendation:** If included, write the drift-guard as a positive assertion: "exactly one occurrence of `build_js_runtimes(` exists in `player.py`" + "exactly one occurrence of `build_js_runtimes(` exists in `yt_import.py`". This is more robust than a negative `"path": None` grep and survives whitespace/quoting changes.

## Runtime State Inventory

Phase 79 is a code-only fix. No databases, no live service configs, no OS-registered state, no secrets, no build artifacts change.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — `NodeRuntime` is a frozen dataclass detected fresh at every process start; not persisted. | None |
| Live service config | None — yt-dlp is a Python library, not an external service. | None |
| OS-registered state | None — the GNOME `.desktop` entry (`packaging/linux/org.lightningjim.MusicStreamer.desktop`) is the bug's reproduction context but its content does not change. | None |
| Secrets/env vars | None — no new env vars; the fix bypasses environment-PATH augmentation entirely (D-01 rejection). | None |
| Build artifacts | None — no `pyproject.toml` change, no new package install. Existing pipx install of `musicstreamer` continues to work; the shim binary at `~/.local/bin/musicstreamer` is unchanged. | None |

**Verified by:** Code inspection only — no Phase 79 changes touch persistence, services, or registrations. `runtime_check.check_node()` already runs at every `_run_gui` start (line 215 — no caching).

## Validation Architecture

> Per `.planning/config.json` `workflow.nyquist_validation = true` — included.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 (verified via `python3 -c "import pytest; print(pytest.__version__)"`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (verified existing) |
| Quick run command | `uv run --with pytest pytest tests/test_yt_dlp_opts.py tests/test_player.py tests/test_yt_import_library.py tests/test_cookies.py -x` |
| Full suite command | `uv run --with pytest pytest tests/ -x` |

### Phase Requirements → Test Map

The phase has no formal `REQ-XX` ID yet (CONTEXT.md proposes `BUG-11`). The implementation-derived behaviors:

| Behavior ID | Behavior | Test Type | Automated Command | File Exists? |
|-------------|----------|-----------|-------------------|-------------|
| B-79-01 | `build_js_runtimes(None)` returns `{"node": {"path": None}}` | unit | `uv run --with pytest pytest tests/test_yt_dlp_opts.py::test_build_js_runtimes_none_input -x` | ❌ Wave 0 |
| B-79-02 | `build_js_runtimes(NodeRuntime(available=True, path="/fake/node"))` returns `{"node": {"path": "/fake/node"}}` | unit | `uv run --with pytest pytest tests/test_yt_dlp_opts.py::test_build_js_runtimes_available_path -x` | ❌ Wave 0 |
| B-79-03 | `build_js_runtimes(NodeRuntime(available=False, path=None))` returns `{"node": {"path": None}}` | unit | `uv run --with pytest pytest tests/test_yt_dlp_opts.py::test_build_js_runtimes_unavailable_none_path -x` | ❌ Wave 0 |
| B-79-04 | `Player(node_runtime=NodeRuntime(available=True, path="/fake/node"))._youtube_resolve_worker` passes opts with `js_runtimes["node"]["path"] == "/fake/node"` to `yt_dlp.YoutubeDL` | integration (mocked yt-dlp) | `uv run --with pytest pytest tests/test_player.py::test_youtube_resolve_passes_node_path_when_available -x` | ❌ Wave 0 (extend existing file) |
| B-79-05 | `Player(node_runtime=None)._youtube_resolve_worker` passes opts with `js_runtimes["node"]["path"] is None` (backwards-compat) | integration | `uv run --with pytest pytest tests/test_player.py::test_youtube_resolve_passes_none_when_no_node_runtime -x` | ❌ Wave 0 |
| B-79-06 | `Player(node_runtime=NodeRuntime(available=False, path=None))._youtube_resolve_worker` passes opts with `js_runtimes["node"]["path"] is None` | integration | `uv run --with pytest pytest tests/test_player.py::test_youtube_resolve_passes_none_when_unavailable -x` | ❌ Wave 0 |
| B-79-07 | `yt_import.scan_playlist(url, node_runtime=NodeRuntime(available=True, path="/fake/node"))` passes opts with `js_runtimes["node"]["path"] == "/fake/node"` to `yt_dlp.YoutubeDL` | integration | `uv run --with pytest pytest tests/test_yt_import_library.py::test_scan_playlist_passes_node_path_when_available -x` | ❌ Wave 0 (extend existing file) |
| B-79-08 | `yt_import.scan_playlist(url)` (no node_runtime kwarg) passes opts with `js_runtimes["node"]["path"] is None` | integration | `uv run --with pytest pytest tests/test_yt_import_library.py::test_scan_playlist_default_none_node_runtime -x` | ❌ Wave 0 |
| B-79-09 | `yt_import.scan_playlist(url, node_runtime=NodeRuntime(available=False, path=None))` passes opts with `js_runtimes["node"]["path"] is None` | integration | `uv run --with pytest pytest tests/test_yt_import_library.py::test_scan_playlist_passes_none_when_unavailable -x` | ❌ Wave 0 |
| B-79-10 | Live UAT — `.desktop` launch resolves a YT live stream | manual-only | (live click on a YT station after install + reboot or fresh login) | manual |
| B-79-DG-1 *(optional, Claude's Discretion)* | Source-grep drift-guard: only `yt_dlp_opts.py` contains the literal `"path": None` inside `js_runtimes` dicts | unit (source-text) | `uv run --with pytest pytest tests/test_yt_dlp_opts_drift.py -x` | ❌ Wave 0 if adopted |

### Sampling Rate

- **Per task commit:** `uv run --with pytest pytest tests/test_yt_dlp_opts.py tests/test_player.py tests/test_yt_import_library.py tests/test_cookies.py -x` (under 15 seconds local)
- **Per wave merge:** `uv run --with pytest pytest tests/ -x` (full suite, ~30s local)
- **Phase gate:** Full suite green BEFORE `/gsd:verify-work`; live UAT (B-79-10) sign-off required from user.

### Wave 0 Gaps

- [ ] `tests/test_yt_dlp_opts.py` — covers B-79-01, B-79-02, B-79-03 (NEW file)
- [ ] Extend `tests/test_player.py` (or a new `tests/test_player_node_runtime.py` if scope-isolation is preferred) — covers B-79-04, B-79-05, B-79-06
- [ ] Extend `tests/test_yt_import_library.py` — covers B-79-07, B-79-08, B-79-09
- [ ] (Optional) `tests/test_yt_dlp_opts_drift.py` — covers B-79-DG-1 (Claude's Discretion)
- [ ] Framework install: N/A — `pytest` is already provisioned via `uv run --with pytest`

**Live UAT (B-79-10) is manual-only:** the bug's reproduction requires (a) `.desktop` launch with stripped PATH AND (b) Node provided exclusively via version-manager shim. No CI environment reliably reproduces both conditions. The unit + integration matrix (B-79-04 ... B-79-09) is the regression-lock; live UAT is the closure gate.

## Code Examples

### Example 1: Player._youtube_resolve_worker — opts construction (after Phase 79)

```python
# Source: musicstreamer/player.py, Phase 79 edit at line 1053-1071
# Replaces the literal {"node": {"path": None}} at line 1063.

import yt_dlp
from musicstreamer import yt_dlp_opts

# Phase 999.7 corruption check — MUST run BEFORE building opts.
canonical = paths.cookies_path()
if os.path.exists(canonical) and cookie_utils.is_cookie_file_corrupted(canonical):
    constants.clear_cookies()
    self.cookies_cleared.emit(
        "YouTube cookies cleared — re-import via Accounts menu."
    )

# Phase 79 / BUG-11: one INFO log line per YT play, visible at INFO level
# (musicstreamer.player is already at INFO via __main__.main:235).
node_path = self._node_runtime.path if self._node_runtime else None
_log.info("youtube resolve: node_path=%s", node_path)

opts = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "format": "best[protocol^=m3u8]/bestaudio/best",
    # Phase 999.9 + Phase 79: js_runtimes carries the explicit Node path
    # so yt-dlp's NodeJsRuntime._info() runs the right binary even when
    # the .desktop-inherited PATH lacks fnm/nvm/volta/asdf shims.
    "js_runtimes": yt_dlp_opts.build_js_runtimes(self._node_runtime),
    "remote_components": {"ejs:github"},
}
```

### Example 2: yt_import.scan_playlist — opts construction (after Phase 79)

```python
# Source: musicstreamer/yt_import.py, Phase 79 edit at line 62-71
# Inserts a new "js_runtimes" entry into the opts dict.

import logging
from typing import Callable, Optional

from musicstreamer import constants, cookie_utils, paths, yt_dlp_opts
from musicstreamer.runtime_check import NodeRuntime

_log = logging.getLogger(__name__)


def scan_playlist(
    url: str,
    toast_callback: Optional[Callable[[str], None]] = None,
    *,
    node_runtime: NodeRuntime | None = None,
) -> list[dict]:
    """... (existing docstring unchanged) ...

    Phase 79: js_runtimes carries the explicit Node path so playlist
    metadata extraction works under .desktop-launched contexts where
    fnm/nvm/volta/asdf shims are missing from PATH. Defensive parity
    with player._youtube_resolve_worker — extract_flat='in_playlist'
    short-circuits per-entry JS solving today, but the parity
    preserves the single-source-of-truth invariant for the helper.
    """
    canonical = paths.cookies_path()
    if os.path.exists(canonical) and cookie_utils.is_cookie_file_corrupted(canonical):
        constants.clear_cookies()
        if toast_callback is not None:
            toast_callback("YouTube cookies cleared — re-import via Accounts menu.")

    # Phase 79 / BUG-11: one INFO log line per scan, visible at INFO level
    # (musicstreamer.yt_import logger is escalated in __main__.main).
    node_path = node_runtime.path if node_runtime is not None else None
    _log.info("youtube scan: node_path=%s", node_path)

    opts = {
        "extract_flat": "in_playlist",
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "js_runtimes": yt_dlp_opts.build_js_runtimes(node_runtime),
        "remote_components": {"ejs:github"},
    }
    # ... rest of body unchanged ...
```

### Example 3: New helper module (full module body)

```python
# Source: musicstreamer/yt_dlp_opts.py (NEW FILE)
"""Shared helper for building yt-dlp's js_runtimes opts dict.

Provides:
  - build_js_runtimes(node_runtime: NodeRuntime | None) -> dict
      Returns the shape yt-dlp's library API expects:
      {"node": {"path": <abs-path-or-None>}}.
      When node_runtime is None or its path is None, yields
      {"node": {"path": None}} — yt-dlp then runs its own PATH lookup
      (which may succeed for pipx-from-terminal launches and fails
      under the .desktop launch context where version-manager shims
      are missing).

Phase 79 / BUG-11 — single source of truth used by both yt-dlp call sites:
  - musicstreamer/player.py::_youtube_resolve_worker
  - musicstreamer/yt_import.py::scan_playlist

Why a module: yt-dlp's library API does NOT auto-discover JS runtimes
the way the CLI does (Phase 999.9 baseline). When the path resolved by
musicstreamer.runtime_check.check_node() is not passed through, yt-dlp's
NodeJsRuntime._info() resolves path=None → "node" literal → subprocess
fails under the .desktop-stripped PATH.

Reference: yt_dlp/utils/_jsruntime.py::_determine_runtime_path (yt-dlp
2026.03.17).
"""
from __future__ import annotations

from musicstreamer.runtime_check import NodeRuntime


def build_js_runtimes(node_runtime: NodeRuntime | None) -> dict:
    """Return js_runtimes opts dict for yt_dlp.YoutubeDL.

    Returns the shape yt-dlp's library API expects:
      {"node": {"path": <abs-path-or-None>}}

    When node_runtime is None or its path is None, returns
    {"node": {"path": None}} (preserves yt-dlp's own PATH-lookup behavior
    for the genuinely-absent case).
    """
    path = node_runtime.path if node_runtime is not None else None
    return {"node": {"path": path}}
```

### Example 4: New test file (full body for tests/test_yt_dlp_opts.py)

```python
# Source: tests/test_yt_dlp_opts.py (NEW FILE)
"""Tests for musicstreamer.yt_dlp_opts (Phase 79 / BUG-11).

Three-input matrix locks the helper's contract: the Player and yt_import
regression tests (tests/test_player.py, tests/test_yt_import_library.py)
then assert the helper's output is wired through to yt_dlp.YoutubeDL opts.
"""
from __future__ import annotations

from musicstreamer.runtime_check import NodeRuntime
from musicstreamer.yt_dlp_opts import build_js_runtimes


def test_build_js_runtimes_none_input():
    """node_runtime=None preserves today's {"path": None} behavior (D-02)."""
    assert build_js_runtimes(None) == {"node": {"path": None}}


def test_build_js_runtimes_available_path():
    """Resolved path threads through to opts (D-01)."""
    nr = NodeRuntime(available=True, path="/fake/node")
    assert build_js_runtimes(nr) == {"node": {"path": "/fake/node"}}


def test_build_js_runtimes_unavailable_none_path():
    """Genuinely-absent Node yields {"path": None} (D-02 absent branch)."""
    nr = NodeRuntime(available=False, path=None)
    assert build_js_runtimes(nr) == {"node": {"path": None}}
```

### Example 5: Player opts-recording regression test (extend tests/test_player.py)

```python
# Source: tests/test_player.py — append (or new tests/test_player_node_runtime.py)
"""Phase 79 / BUG-11: _youtube_resolve_worker must thread NodeRuntime.path
into opts["js_runtimes"]["node"]["path"] so yt-dlp invokes the right
binary under .desktop-stripped PATH contexts."""
from unittest.mock import patch
from musicstreamer.player import Player
from musicstreamer.runtime_check import NodeRuntime
from tests.test_cookies import make_player  # existing helper, do NOT modify


def _make_player_with_node(qtbot, node_runtime):
    """Mirror make_player but construct Player(node_runtime=...)."""
    from unittest.mock import MagicMock
    mock_pipeline = MagicMock()
    mock_pipeline.get_bus.return_value = MagicMock()
    with patch(
        "musicstreamer.player.Gst.ElementFactory.make",
        return_value=mock_pipeline,
    ):
        return Player(node_runtime=node_runtime)


def test_youtube_resolve_passes_node_path_when_available(qtbot):
    """B-79-04: opts["js_runtimes"]["node"]["path"] == <abs> when
    NodeRuntime(available=True, path=<abs>) is injected at ctor."""
    captured = {}

    class FakeYDL:
        def __init__(self, opts):
            captured.update(opts)
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def extract_info(self, url, download=False):
            return {"url": "http://resolved.example/stream.m3u8"}

    import yt_dlp
    nr = NodeRuntime(available=True, path="/fake/node")
    player = _make_player_with_node(qtbot, nr)
    with patch.object(yt_dlp, "YoutubeDL", FakeYDL):
        player._youtube_resolve_worker("https://youtube.com/watch?v=test")

    assert captured["js_runtimes"] == {"node": {"path": "/fake/node"}}


def test_youtube_resolve_passes_none_when_no_node_runtime(qtbot):
    """B-79-05: backwards-compat — default node_runtime=None yields
    {"path": None} so today's tests at tests/test_cookies.py:157,190 stay
    green and yt-dlp's own PATH lookup still runs."""
    captured = {}

    class FakeYDL:
        def __init__(self, opts):
            captured.update(opts)
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def extract_info(self, url, download=False):
            return {"url": "http://resolved.example/stream.m3u8"}

    import yt_dlp
    player = make_player(qtbot)  # node_runtime defaults to None
    with patch.object(yt_dlp, "YoutubeDL", FakeYDL):
        player._youtube_resolve_worker("https://youtube.com/watch?v=test")

    assert captured["js_runtimes"] == {"node": {"path": None}}


def test_youtube_resolve_passes_none_when_unavailable(qtbot):
    """B-79-06: NodeRuntime(available=False, path=None) — preserves
    D-02 behavior (yt-dlp tries its own PATH lookup; may succeed for
    JS-free streams)."""
    captured = {}

    class FakeYDL:
        def __init__(self, opts):
            captured.update(opts)
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def extract_info(self, url, download=False):
            return {"url": "http://resolved.example/stream.m3u8"}

    import yt_dlp
    nr = NodeRuntime(available=False, path=None)
    player = _make_player_with_node(qtbot, nr)
    with patch.object(yt_dlp, "YoutubeDL", FakeYDL):
        player._youtube_resolve_worker("https://youtube.com/watch?v=test")

    assert captured["js_runtimes"] == {"node": {"path": None}}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `yt_dlp` CLI subprocess (Phase 35 KEEP_MPV spike) | `yt_dlp.YoutubeDL` library API (Plan 35-06) | v2.0 (2026-04 milestone) | Phase 79 is exclusively in the library-API path; the CLI path was retired in v2.0 |
| `extractor_args={"youtubepot-jsruntime": ...}` | `js_runtimes={"node": {"path": ...}}` (top-level opt) | yt-dlp 2026.03.17 | Phase 999.9 baseline; Phase 79 is the next iteration |
| `path=None` (yt-dlp does PATH lookup) | `path=<abs>` (yt-dlp invokes binary directly) | Phase 79 | This phase |
| `shutil.which("node")` only | `_which_node_version_manager_fallback` (fnm/nvm/volta/asdf probe) | commit `a06549f` (2026-04-25) | First half of Phase 79's fix; Phase 79 is the second half |

**Deprecated/outdated:**
- `extractor_args={"youtubepot-jsruntime": ...}` — yt-dlp 2026.03.17 silently dropped this. The `js_runtimes` opt is the current entry point. (Already addressed in Phase 999.9.)
- `mpv` subprocess fallback for YouTube — superseded by Plan 35-06. (Already removed.)

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The `BUG-11` ID is available for the new REQUIREMENTS.md entry. | Phase Requirements | If `BUG-11` is taken, planner picks the next free slot. Low-risk; one-line update. |
| A2 | The `.desktop` launcher under Wayland / GNOME Shell strips fnm/nvm/volta/asdf shims from the inherited PATH. | Summary | [VERIFIED at root-cause time per CONTEXT.md] — confirmed by user observation + commit `a06549f` message + direct code-path analysis. |
| A3 | yt-dlp's `NodeJsRuntime._info()` failure when subprocess fails returns None (not raise), which yt-dlp then surfaces as "No video formats found!" at extract_info time. | Pitfall 7 | [VERIFIED: yt_dlp/utils/_jsruntime.py:122-131 — returns None when `out` is empty; the downstream code paths drop the runtime from `_js_runtimes`] |
| A4 | The dev box's fnm-installed Node (v25.9.0 at `/home/kcreasey/.local/share/fnm/node-versions/v25.9.0/installation/bin/node`) reproduces the `.desktop`-launch failure mode but works from terminal. | Summary | [VERIFIED: dev box probe at research time] — CONTEXT.md attests user-confirmed root cause. The unit-test matrix is platform-independent; live UAT is the only verification of the .desktop fix. |
| A5 | `extract_flat='in_playlist'` in `scan_playlist` short-circuits per-entry JS solving in yt-dlp 2026.03.17. | Pitfall 2 | [VERIFIED: yt_dlp/YoutubeDL.py:1894-1909 — the flat-extraction branch returns `ie_result` before per-entry resolution]. Means the scan-side fix is defensive parity, not a live bug fix. Planner SHOULD note this in the plan rationale; live UAT does not need to exercise scan. |
| A6 | `Player(node_runtime=None)` default in tests/test_cookies.py + tests/test_player.py preserves the existing `js_runtimes == {"node": {"path": None}}` assertion (lines 157, 190 in test_cookies.py). | Pitfall 1 | [VERIFIED via code reading] — default kwarg path yields the same shape today's tests assert. If wrong, two existing tests would need rewriting; the planner should grep them at plan-time to reconfirm. |
| A7 | `runtime_check.py` does not import `musicstreamer.player`, so adding `from musicstreamer.runtime_check import NodeRuntime` to `player.py` is acyclic. | Pitfall 4 | [VERIFIED: grep returned no results]. If a future commit adds the back-edge, use `TYPE_CHECKING` + forward-ref string. |
| A8 | `_YtScanWorker` (`import_dialog.py:74-93`) is the only path from the YouTube tab to `scan_playlist`. | Pitfall 6 | [VERIFIED: grep `scan_playlist` returned 3 sites — `import_dialog.py:90` (production) and `tests/test_import_dialog.py:73,90,125` (mocked tests at module import level only)]. |
| A9 | The user wants the INFO log line at the existing `musicstreamer.player` and `musicstreamer.yt_import` logger names (i.e., respects per-module logger discipline). | D-13 / Code Examples | LOW risk — matches Phase 62 / Phase 74 precedent for per-logger INFO escalation (`__main__.py:235-236`). |

**If this table is empty:** N/A — Phase 79 makes 9 small assumptions about repo state and external library behavior, the highest-risk of which (A5) is internally verified against the live yt-dlp source.

## Open Questions

1. **`BUG-11` REQUIREMENTS.md entry — title and acceptance criteria wording**
   - **What we know:** No requirement entry exists yet. CONTEXT.md suggests "YouTube playback works when MusicStreamer is launched via the GNOME .desktop entry".
   - **What's unclear:** Should the requirement include Windows in scope (D-03 says yes; the live bug surface is Linux-only)? Should it carry a sub-bullet for the import-dialog parity (D-09)?
   - **Recommendation:** Planner drafts the entry following BUG-09's shape, includes both call sites in the acceptance criteria, and notes "Linux primary; Windows defensive parity (no live UAT required for Windows)".

2. **Should `__main__.main` add `logging.getLogger("musicstreamer.yt_import").setLevel(logging.INFO)`?**
   - **What we know:** `musicstreamer.player` is already at INFO (`__main__.py:235`). `musicstreamer.yt_import` is at WARNING (default).
   - **What's unclear:** D-13 says "add ONE INFO log line per YT play" — does the user want it visible at the default WARNING level (which would mean upgrading the line to `_log.warning` — semantically wrong) or are they assuming the per-logger INFO escalation comes for free?
   - **Recommendation:** Add `logging.getLogger("musicstreamer.yt_import").setLevel(logging.INFO)` alongside the two existing escalations (`__main__.py:235-236`). Mirrors Phase 62 / Phase 74 precedent. Single-line addition. Planner confirms with user only if they want a WARNING-level alternative.

3. **Drift-guard scope — Claude's Discretion item from CONTEXT.md**
   - **What we know:** CONTEXT.md says "YES if one-liner via existing `tests/test_packaging_spec.py` shape".
   - **What's unclear:** Is the user happy with the positive-form drift-guard (assert `build_js_runtimes(` appears in both call sites) vs the negative-form (assert `"path": None` literal absent from `player.py` and `yt_import.py`)? Both are one-liners.
   - **Recommendation:** Positive form — counts `build_js_runtimes(` occurrences. More robust to whitespace/quoting drift; harder to silently break with a refactor that loses the helper call.

4. **Test-file organization — extend `tests/test_player.py` vs create `tests/test_player_node_runtime.py`?**
   - **What we know:** Project precedent is mixed — `test_cookies.py` is a topic file shared by Player + yt_import; `test_player_pause.py`, `test_player_volume.py` are concern-scoped files.
   - **What's unclear:** Whether the user prefers scope-isolation or growing `test_player.py` (currently 577 lines).
   - **Recommendation:** Create `tests/test_player_node_runtime.py` — keeps the Player file growth modest and the regression test trivially discoverable by grep on the phase number. The yt_import test extends the existing file (consistent with other Phase 79-style additions).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All | ✓ | 3.14 (verified via `/home/kcreasey/OneDrive/Projects/MusicStreamer/.venv/lib/python3.14/`) | — |
| pytest | Test execution | ✓ | 9.0.2 | — |
| yt-dlp | Production code (Player + yt_import) | ✓ | 2026.03.17 | — |
| Node.js (for live UAT only) | yt-dlp EJS solver under live YouTube playback | ✓ | v25.9.0 via fnm | If absent: live UAT skipped; unit tests still verify the wiring. |
| PySide6 | UI tests (qtbot) | ✓ | (resolved via venv) | — |
| `gsd-sdk` wrapper | Phase tooling | ✓ | (PATH wrapper at `~/.local/bin/gsd-sdk`) | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None — every dependency required for code execution is present. Node.js absence would only affect the live UAT (B-79-10); the entire unit + integration matrix runs against mocked `yt_dlp.YoutubeDL` and never invokes Node.

## Security Domain

Phase 79's security surface is narrow but non-zero. It thread an absolute filesystem path (`NodeRuntime.path`) into a yt-dlp opts dict that yt-dlp uses as `subprocess.run([<path>, '--version'])` argv[0].

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes (path provenance) | `_which_node` returns absolute paths from constructed candidate lists (POSIX) or `shutil.which` (`runtime_check.py:53-66`); not user-controlled input |
| V6 Cryptography | no | — |
| V12 Files / Resources | yes (executable path used in subprocess) | The path is sourced exclusively from `runtime_check.NodeRuntime` — never from env vars or user input. `subprocess.run([abs_path, "--version"])` is yt-dlp's call, not ours; argv[0] is not shell-interpreted. |
| V14 Configuration | yes | No new env vars, no new configuration file. No new dependencies. |

### Known Threat Patterns for {python + yt-dlp + GStreamer + PySide6}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path injection into subprocess argv[0] | Tampering / Elevation of Privilege | `NodeRuntime.path` is sourced from `runtime_check._which_node` or `_which_node_version_manager_fallback`; both compose paths from `os.path.join(home, "<known-vendor>", "bin", "node")` literals — no user-supplied input. yt-dlp's own subprocess call uses argv as a list (no shell), so even a path with shell metacharacters would not be interpreted. **No new mitigation required.** |
| ReDoS via opts dict | Tampering | The new helper does not parse strings; it stores an already-resolved path. **N/A.** |
| Information leakage via INFO log | Information Disclosure | The INFO log line emits `node_path=/abs/path/to/node`. This is the user's home-directory-anchored install location — exposing it in the log is consistent with the existing `runtime_check._log.debug("Node.js detected at %s", path)` at line 115. **No new sensitive data exposure.** Logs are written to stderr only (no file logging configured). |
| Dependency confusion / supply-chain | All | No new packages installed. yt-dlp version is locked in pyproject.toml. **N/A.** |

**Verdict:** No new ASVS controls required. The new code path is a single-line dict construction and a single-line log call; both consume already-vetted data.

## Sources

### Primary (HIGH confidence)
- **yt-dlp source code 2026.03.17** (installed in `.venv`):
  - `yt_dlp/utils/_jsruntime.py:16-64` — `_find_exe`, `_determine_runtime_path`, `NodeJsRuntime._info`. The smoking gun: line 60-64 returns `_find_exe("node")` when `path` is falsy; `_find_exe` on non-Windows (line 24) returns the literal basename, leaving yt-dlp to invoke `node --version` via subprocess which then PATH-resolves.
  - `yt_dlp/YoutubeDL.py:534-544` — `js_runtimes` opt docstring: "A dictionary of JavaScript runtime keys (in lower case) to enable and a dictionary of additional configuration for the runtime."
  - `yt_dlp/YoutubeDL.py:735-736` — default `{'deno': {}}` when omitted; `_clean_js_runtimes` validates shape.
  - `yt_dlp/YoutubeDL.py:1894-1909` — `extract_flat` short-circuit branch confirms scan-side is JS-free for flat playlists.
- **MusicStreamer codebase (verified at research time, 2026-05-16):**
  - `musicstreamer/runtime_check.py:36-116` — `NodeRuntime` dataclass + `check_node()` + `_which_node` (incl. fnm/nvm/volta/asdf fallback).
  - `musicstreamer/player.py:1005-1098` — `_play_youtube` + `_youtube_resolve_worker` (the smoking-gun literal at line 1063).
  - `musicstreamer/yt_import.py:39-105` — `scan_playlist` (notable: does NOT currently set `js_runtimes`; defaults to yt-dlp's `{'deno': {}}`).
  - `musicstreamer/__main__.py:163-227` — `_run_gui` where `node_runtime` is detected (line 215) and passed to MainWindow (line 222).
  - `musicstreamer/ui_qt/main_window.py:190-202` — the exact `node_runtime=None` ctor-kwarg pattern Phase 79 mirrors.
  - `musicstreamer/ui_qt/main_window.py:795-815` — `_on_playback_error` toast (unchanged by Phase 79 per D-12).
  - `musicstreamer/ui_qt/import_dialog.py:74-93,168-195` — `_YtScanWorker` + `ImportDialog.__init__`.
  - `musicstreamer/cookie_utils.py:1-83` — sibling-module shape reference.
  - `tests/test_cookies.py:120-191` — existing opts-recording test shape (mirror for Phase 79's regression test).
  - `tests/test_yt_import_library.py:30-100` — existing `_patch_youtubedl` helper.
  - `tests/test_runtime_check.py:1-101` — NodeRuntime test patterns.
  - `tests/test_packaging_spec.py:1-100` — drift-guard test shape.
- **Phase 79 CONTEXT.md** — locked decisions D-01..D-13.

### Secondary (MEDIUM confidence)
- **commit `a06549f` (2026-04-25)** — "fix: detect Node.js installed via fnm/nvm/volta/asdf". Commit message explicitly documents the `.desktop` PATH gap. [CITED: per CONTEXT.md `<canonical_refs>`; not re-read at research time.]
- **Phase 999.9 commit message** — "yt-dlp 2026.03.17 silently dropped extractor_args['youtubepot-jsruntime']; pinned player_client=web in `musicstreamer/player.py::_youtube_resolve_worker`. Bundled `yt_dlp_ejs` handles JS challenges without `--remote-components`". [CITED: STATE.md Decisions log.]
- **freedesktop `.desktop` spec** — `Exec=` env inheritance is implementation-defined (systemd-session vs gnome-session-binary vs dbus-activated launches differ). The PATH-stripping reproduction is empirically verified by the user; no spec citation will tighten that any further.

### Tertiary (LOW confidence)
- **pipx shim PATH inheritance** — Documented behavior is "the shim's child Python inherits the parent shell's PATH unchanged". Verified empirically (the bug doesn't reproduce from a terminal). No formal-spec citation required for this phase.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — yt-dlp library API confirmed from source; runtime_check.NodeRuntime confirmed in-tree.
- Architecture: HIGH — every plumbing decision (D-05..D-08) mirrors an existing project precedent (`MainWindow.__init__(node_runtime=None)`).
- Pitfalls: HIGH — Pitfall 2 (the CONTEXT.md drift about `scan_playlist`'s nonexistent js_runtimes literal) was caught by direct file reading at research time, not from CONTEXT.md prose. Pitfall 7 derived from yt-dlp source. All others verified.
- Security: HIGH — no new attack surface; subprocess argv[0] is yt-dlp's call, not ours, and the path is internally sourced.
- Testing: HIGH — three existing test files extend cleanly; one new test file at the helper level.

**Research date:** 2026-05-16
**Valid until:** 2026-06-15 (30 days for stable code; yt-dlp's API is the only churn risk, and the locked 2026.03.17 pin makes that bounded).
