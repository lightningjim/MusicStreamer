# Phase 79: Fix YouTube 'stream exhausted' when launched via .desktop - Pattern Map

**Mapped:** 2026-05-16
**Files analyzed:** 8 (1 new module, 5 modified prod, 2-3 test files)
**Analogs found:** 8 / 8 — every file has an in-tree analog. No "no analog" cases.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `musicstreamer/yt_dlp_opts.py` (NEW) | utility (focused tiny module) | pure (no I/O) | `musicstreamer/cookie_utils.py` | exact |
| `musicstreamer/player.py` (MOD) | service / Qt facade | request-response (worker thread) | self — `Player.__init__` mirrors `MainWindow.__init__` kwarg shape | exact |
| `musicstreamer/yt_import.py` (MOD) | service (library API wrapper) | request-response | self — `scan_playlist` signature grows kwarg | exact |
| `musicstreamer/__main__.py` (MOD) | bootstrap | wire-up | self — existing `node_runtime` plumb to `MainWindow` (line 222) | exact |
| `musicstreamer/ui_qt/import_dialog.py` (MOD) | UI / QThread orchestrator | request-response | self — existing `_YtScanWorker` capture pattern (lines 78-93) | exact |
| `musicstreamer/ui_qt/main_window.py` (MOD) | UI orchestrator | wire-up | self — line 1405 `ImportDialog(...)` ctor call site | exact |
| `tests/test_yt_dlp_opts.py` (NEW) | unit test | pure | `tests/test_url_helpers.py` (focused-helper test shape) | role-match |
| `tests/test_player.py` (EXT) | integration test (mocked yt-dlp) | request-response | `tests/test_cookies.py:120-158` (FakeYDL opts-recording) | exact |
| `tests/test_yt_import_library.py` (EXT) | integration test (mocked yt-dlp) | request-response | self — `_patch_youtubedl` helper (lines 30-42) | exact |
| `tests/test_yt_dlp_opts_drift.py` (NEW, optional) | drift-guard test | source-grep | `tests/test_packaging_spec.py:201-208` (literal-substring pattern) | role-match |

---

## CRITICAL: Pitfall 2 — yt_import is an ADD, not a REPLACE

Per RESEARCH.md §Pitfall 2: **`scan_playlist`'s opts dict at `yt_import.py:62-71` does NOT currently set `js_runtimes`** — yt-dlp's `_clean_js_runtimes` defaults to `{'deno': {}}`. Phase 79 **inserts a new key** into the dict, unlike `player._youtube_resolve_worker` (line 1063) which **substitutes** an existing literal.

Insertion site (per RESEARCH.md): after `"skip_download": True,` (line 66), before `"remote_components": {"ejs:github"},` (line 70).

Planners and implementers writing the yt_import edit MUST NOT search-and-replace `{"path": None}` there — there is nothing to replace.

---

## Pattern Assignments

### 1. `musicstreamer/yt_dlp_opts.py` (NEW — utility, pure)

**Analog:** `musicstreamer/cookie_utils.py` (entire file — 83 lines, two helpers + module docstring)

**Header docstring pattern** (`cookie_utils.py:1-18`):
```python
"""Shared helpers for cookies.txt handling.

Provides:
  - is_cookie_file_corrupted(path) -> bool
      Pure predicate; returns True iff the file starts with the yt-dlp save
      header (see yt_dlp/cookies.py:1284).
  - temp_cookies_copy() -> Iterator[Optional[str]]
      @contextmanager that yields a per-call tempfile copy of paths.cookies_path(),
      or None when the canonical file is absent or shutil.copy2 raises OSError.

Phase 999.7 — restores the v1.5 FIX-02 protection that was lost when Plan
35-06 replaced the mpv subprocess with the yt_dlp library API. Call sites:
  - musicstreamer/player.py::_youtube_resolve_worker
  - musicstreamer/yt_import.py::scan_playlist
"""
from __future__ import annotations
```

**Import + helper body pattern** (mirrors `cookie_utils.py:19-49` shape — no class, single narrow public function, type hints throughout):
```python
from __future__ import annotations
from musicstreamer.runtime_check import NodeRuntime  # direct import — runtime_check does NOT import from yt_dlp_opts (verified Pitfall 4)


def build_js_runtimes(node_runtime: NodeRuntime | None) -> dict:
    """Return js_runtimes opts dict for yt_dlp.YoutubeDL. ..."""
    path = node_runtime.path if node_runtime is not None else None
    return {"node": {"path": path}}
```

**Why this analog:** Both `cookie_utils.py` and the planned `yt_dlp_opts.py` are tiny focused modules with narrow public surface, no class, called from BOTH `player.py` and `yt_import.py`. The module-docstring "Call sites:" block convention is project precedent — keep it.

---

### 2. `musicstreamer/player.py` (MOD — service / Qt facade)

**Analog:** `musicstreamer/ui_qt/main_window.py:190-202` (kwarg + storage), plus self (line 1063 substitution site).

**Constructor kwarg pattern to mirror** (`main_window.py:190-202`):
```python
def __init__(
    self,
    player,
    repo,
    *,
    node_runtime=None,
    parent: QWidget | None = None,
) -> None:
    super().__init__(parent)

    self._player = player
    self._repo = repo
    self._node_runtime = node_runtime
```

**Apply to** `Player.__init__` at `player.py:281`:
- Current: `def __init__(self, parent: QObject | None = None) -> None:`
- New: keyword-only `node_runtime: "NodeRuntime | None" = None` AFTER `parent`. Store as `self._node_runtime = node_runtime` right after `super().__init__(parent)` (line 282).

**Module logger precedent** (`player.py:76-78`) — already exists, no changes:
```python
# Phase 62 / BUG-09: module logger (first logger in player.py).
# Surfaced at INFO via __main__.py per-logger setLevel — see Plan 03.
_log = logging.getLogger(__name__)
```

**Opts substitution site** (`player.py:1058-1063` — current code):
```python
# Phase 999.9: yt-dlp's library API does NOT auto-discover JS runtimes
# the way the CLI does. Without an explicit js_runtimes entry the YouTube
# n-challenge solver cannot run, so extract_info returns "No video formats
# found!" even though `uv run yt-dlp <url>` works at the shell. Node is the
# runtime declared by RUNTIME-01; path=None lets yt-dlp resolve it via PATH.
"js_runtimes": {"node": {"path": None}},
```

**Replace with** (single-line substitution; preserve the existing multi-line comment block):
```python
"js_runtimes": yt_dlp_opts.build_js_runtimes(self._node_runtime),
```

**INFO log line** — insert near the top of `_youtube_resolve_worker` (after the cookies-corruption block at line 1051, BEFORE the `opts = {` literal at line 1053). Per Pitfall 3 use the explicit conditional, NOT short-circuit `and`:
```python
node_path = self._node_runtime.path if self._node_runtime else None
_log.info("youtube resolve: node_path=%s", node_path)
```

**New import to add** to `player.py:46` import block (alphabetical insertion):
```python
from musicstreamer import constants, cookie_utils, paths, yt_dlp_opts
```
And separately for the type annotation (TYPE_CHECKING or direct — both safe per Pitfall 4):
```python
from musicstreamer.runtime_check import NodeRuntime
```

---

### 3. `musicstreamer/yt_import.py` (MOD — service)

**Analog:** self — the existing `scan_playlist` signature at `yt_import.py:39-42`.

**Current signature** (`yt_import.py:39-42`):
```python
def scan_playlist(
    url: str,
    toast_callback: Optional[Callable[[str], None]] = None,
) -> list[dict]:
```

**Add a third keyword-only param**:
```python
def scan_playlist(
    url: str,
    toast_callback: Optional[Callable[[str], None]] = None,
    *,
    node_runtime: "NodeRuntime | None" = None,
) -> list[dict]:
```

**Opts INSERTION site** (`yt_import.py:62-71` — current code):
```python
opts = {
    "extract_flat": "in_playlist",
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    # BUG-YT-COOKIES: yt-dlp 2026.03.17+ requires the EJS remote component
    # when YouTube account cookies are detected (authenticated code path).
    # Same fix as player.py::_youtube_resolve_worker.
    "remote_components": {"ejs:github"},
}
```

**ADD** (insertion, not replacement — Pitfall 2) after `"skip_download": True,` (line 66) and BEFORE the `# BUG-YT-COOKIES` comment block (line 67):
```python
    # Phase 79 / BUG-11: thread the resolved Node executable path through to
    # yt-dlp so .desktop-stripped PATH launches don't fail JS-requiring scans.
    # Single source of truth shared with player._youtube_resolve_worker.
    "js_runtimes": yt_dlp_opts.build_js_runtimes(node_runtime),
```

**Module logger to ADD** at top of `yt_import.py` (currently has NO logger — mirror `player.py:76-78`). Insert after line 13 (the `from typing import` line), before line 15 (`import yt_dlp`):
```python
import logging
_log = logging.getLogger(__name__)
```

**INFO log line** — insert at the top of `scan_playlist` body, AFTER the corruption-check block (line 61) and BEFORE the `opts = {` literal (line 62):
```python
node_path = node_runtime.path if node_runtime else None
_log.info("scan playlist: node_path=%s", node_path)
```

**New import to add** at `yt_import.py:17`:
```python
from musicstreamer import constants, cookie_utils, paths, yt_dlp_opts
```

---

### 4. `musicstreamer/__main__.py` (MOD — bootstrap, wire-up)

**Analog:** self — line 222 already passes `node_runtime=node_runtime` to `MainWindow`. Mirror for `Player`.

**Existing pattern** (`__main__.py:214-222`):
```python
from musicstreamer import runtime_check  # lazy
node_runtime = runtime_check.check_node()
if not node_runtime.available:
    runtime_check.show_missing_node_dialog(parent=None)

# con / db_init / repo already constructed above (Phase 66 hoist for theme).
player = Player()  # <-- LINE 220: change to Player(node_runtime=node_runtime)

window = MainWindow(player, repo, node_runtime=node_runtime)
```

**Single-token edit at line 220**:
```python
player = Player(node_runtime=node_runtime)
```

**Existing logger-level precedent** (`__main__.py:231-236`) — Phase 79 ADDS a third line below the existing two:
```python
logging.basicConfig(level=logging.WARNING)
# Phase 62 / BUG-09 / Pitfall 5: per-logger INFO level for musicstreamer.player
# so buffer-underrun cycle close lines surface to stderr without bumping the
# GLOBAL level (which would surface chatter from aa_import / gbs_api / mpris2).
logging.getLogger("musicstreamer.player").setLevel(logging.INFO)
logging.getLogger("musicstreamer.soma_import").setLevel(logging.INFO)
# Phase 79: surface scan_playlist node_path INFO line at default verbosity.
logging.getLogger("musicstreamer.yt_import").setLevel(logging.INFO)
```

---

### 5. `musicstreamer/ui_qt/import_dialog.py` (MOD — UI / QThread)

**Analog:** self — the existing `_YtScanWorker.__init__` capture pattern at `import_dialog.py:74-93` and `ImportDialog.__init__` at `import_dialog.py:168-184`.

**`_YtScanWorker` current signature** (`import_dialog.py:78-93`):
```python
class _YtScanWorker(QThread):
    finished = Signal(list)
    error = Signal(str)

    def __init__(
        self,
        url: str,
        toast_callback: Optional[Callable[[str], None]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._url = url
        self._toast = toast_callback

    def run(self):
        try:
            results = yt_import.scan_playlist(self._url, toast_callback=self._toast)
            self.finished.emit(results)
        except Exception as exc:
            self.error.emit(str(exc))
```

**Threading shape** (per RESEARCH.md Pitfall 6 — `_YtScanWorker` is `QThread`, NOT a daemon `threading.Thread`, so the parent's `_node_runtime` MUST be captured into the worker's own `__init__`):
1. `_YtScanWorker.__init__` grows `node_runtime` kwarg + stores `self._node_runtime`.
2. `_YtScanWorker.run()` forwards `node_runtime=self._node_runtime` to `scan_playlist`.
3. `ImportDialog.__init__` (currently `import_dialog.py:173`) grows `*, node_runtime=None` + stores `self._node_runtime`.
4. `_on_yt_scan_clicked` at line 337 passes `node_runtime=self._node_runtime` to `_YtScanWorker`.

**`ImportDialog.__init__` current** (`import_dialog.py:173`):
```python
def __init__(self, toast_callback: Callable[[str], None], repo, parent=None):
    super().__init__(parent)
    self._toast = toast_callback
    self._repo = repo
```

**New shape** (keyword-only kwarg per Pitfall 5 — no existing positional callers break):
```python
def __init__(self, toast_callback: Callable[[str], None], repo, parent=None, *, node_runtime=None):
    super().__init__(parent)
    self._toast = toast_callback
    self._repo = repo
    self._node_runtime = node_runtime
```

**`_YtScanWorker` instantiation** at line 337:
```python
self._yt_scan_worker = _YtScanWorker(url, toast_callback=self._toast, node_runtime=self._node_runtime, parent=self)
```

---

### 6. `musicstreamer/ui_qt/main_window.py` (MOD — wire-up)

**Analog:** self — the existing `ImportDialog(...)` call site at line 1405.

**Current line** (`main_window.py:1405`):
```python
dlg = ImportDialog(self.show_toast, self._repo, parent=self)
```

**New line**:
```python
dlg = ImportDialog(self.show_toast, self._repo, parent=self, node_runtime=self._node_runtime)
```

`self._node_runtime` is already stored on MainWindow per the existing `main_window.py:202` line — no other change needed.

---

### 7. `tests/test_yt_dlp_opts.py` (NEW — unit, pure)

**Analog:** any small focused-helper test file. Closest shape is `tests/test_yt_import_library.py:30-42` (focused-helper testing) but without yt-dlp mocking — `build_js_runtimes` is pure.

**Pattern to mirror — three deterministic input → expected-output cases** (one per behavior B-79-01 / B-79-02 / B-79-03):
```python
"""Tests for musicstreamer.yt_dlp_opts — js_runtimes opts builder (Phase 79 / BUG-11)."""
from __future__ import annotations

from musicstreamer.runtime_check import NodeRuntime
from musicstreamer.yt_dlp_opts import build_js_runtimes


def test_build_js_runtimes_none_input():
    """B-79-01: None NodeRuntime → {"node": {"path": None}}."""
    assert build_js_runtimes(None) == {"node": {"path": None}}


def test_build_js_runtimes_available_path():
    """B-79-02: NodeRuntime with resolved path → that path threads through."""
    rt = NodeRuntime(available=True, path="/fake/node")
    assert build_js_runtimes(rt) == {"node": {"path": "/fake/node"}}


def test_build_js_runtimes_unavailable_none_path():
    """B-79-03: NodeRuntime(available=False, path=None) → {"node": {"path": None}}."""
    rt = NodeRuntime(available=False, path=None)
    assert build_js_runtimes(rt) == {"node": {"path": None}}
```

**Note:** `NodeRuntime` is a `@dataclass(frozen=True)` (`runtime_check.py:36-39`) — inline-literal construction is trivial; no fixture needed per CONTEXT.md Claude's Discretion.

---

### 8. `tests/test_player.py` (EXT — integration, mocked yt-dlp)

**Analog:** `tests/test_cookies.py:120-158` — the `FakeYDL` opts-recording pattern (verbatim shape Phase 79 mirrors).

**FakeYDL opts-recording pattern** (`tests/test_cookies.py:130-146`):
```python
captured_opts = {}

class FakeYDL:
    def __init__(self, opts):
        captured_opts.update(opts)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=False):
        return {"url": "http://resolved.example/stream.m3u8"}

import yt_dlp
player = make_player(qtbot)
with patch.object(yt_dlp, "YoutubeDL", FakeYDL):
    player._youtube_resolve_worker("https://youtube.com/watch?v=test")
```

**Existing `make_player(qtbot)` helper** (`tests/test_player.py:16-33`):
```python
def make_player(qtbot):
    from musicstreamer.player import Player
    mock_pipeline = MagicMock()
    mock_bus = MagicMock()
    mock_pipeline.get_bus.return_value = mock_bus
    with patch(
        "musicstreamer.player.Gst.ElementFactory.make",
        return_value=mock_pipeline,
    ):
        player = Player()
    player._pipeline = MagicMock()
    return player
```

**Critical:** **Do NOT modify `make_player`.** Per Pitfall 1 the no-arg `Player()` construction is intentional — it keeps the two existing `assert captured_opts.get("js_runtimes") == {"node": {"path": None}}` lines at `test_cookies.py:157,190` green by construction (default `node_runtime=None` → `build_js_runtimes(None) == {"node": {"path": None}}`).

**New regression tests** (B-79-04 / B-79-05 / B-79-06) — construct `Player(node_runtime=...)` inline with three NodeRuntime literals, mirror the FakeYDL pattern from `test_cookies.py:120-158`:
```python
def test_youtube_resolve_passes_node_path_when_available(qtbot, tmp_path, monkeypatch):
    """B-79-04: Player with NodeRuntime(path='/fake/node') → opts['js_runtimes']['node']['path'] == '/fake/node'."""
    from musicstreamer import paths
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.runtime_check import NodeRuntime
    from musicstreamer.player import Player

    captured_opts = {}
    class FakeYDL:
        def __init__(self, opts): captured_opts.update(opts)
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def extract_info(self, url, download=False): return {"url": "http://x/s.m3u8"}

    mock_pipeline = MagicMock()
    mock_pipeline.get_bus.return_value = MagicMock()
    with patch("musicstreamer.player.Gst.ElementFactory.make", return_value=mock_pipeline):
        player = Player(node_runtime=NodeRuntime(available=True, path="/fake/node"))

    import yt_dlp
    with patch.object(yt_dlp, "YoutubeDL", FakeYDL):
        player._youtube_resolve_worker("https://youtube.com/watch?v=test")

    assert captured_opts["js_runtimes"] == {"node": {"path": "/fake/node"}}
```

**B-79-05** (`node_runtime=None` default → backwards-compat): same shape, construct `Player()` (no kwarg), assert `{"node": {"path": None}}`.
**B-79-06** (`NodeRuntime(available=False, path=None)`): same shape, assert `{"node": {"path": None}}`.

**Scope-isolation nuance:** `tests/test_player.py` is 577 lines. Per CONTEXT.md the planner MAY put these in a new `tests/test_player_node_runtime.py` instead of extending. Either is fine; the pattern is identical.

---

### 9. `tests/test_yt_import_library.py` (EXT — integration, mocked yt-dlp)

**Analog:** self — the existing `_patch_youtubedl` helper at `tests/test_yt_import_library.py:30-42`.

**Helper pattern** (verbatim from `tests/test_yt_import_library.py:30-42`):
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

**Caveat:** the existing helper returns a `MagicMock(return_value=cm)` for `youtubedl_cls` — to record opts captured at `__init__` the new test inspects `youtubedl_cls.call_args` (a `unittest.mock` idiom):
```python
def test_scan_playlist_passes_node_path_when_available():
    """B-79-07: scan_playlist(node_runtime=NodeRuntime(path='/fake/node')) → opts['js_runtimes']['node']['path'] == '/fake/node'."""
    from musicstreamer.runtime_check import NodeRuntime
    p, youtubedl_cls, _ = _patch_youtubedl(extract_info_return={"entries": []})
    with p:
        yt_import.scan_playlist(
            "https://youtube.com/@x/streams",
            node_runtime=NodeRuntime(available=True, path="/fake/node"),
        )
    opts = youtubedl_cls.call_args[0][0]  # first positional arg of YoutubeDL(opts)
    assert opts["js_runtimes"] == {"node": {"path": "/fake/node"}}
```

**B-79-08** (no kwarg / default): assert `opts["js_runtimes"] == {"node": {"path": None}}`.
**B-79-09** (`NodeRuntime(available=False, path=None)`): assert `opts["js_runtimes"] == {"node": {"path": None}}`.

---

### 10. `tests/test_yt_dlp_opts_drift.py` (NEW — OPTIONAL drift-guard)

**Analog:** `tests/test_packaging_spec.py:201-208` — substring assertion shape.

**Project precedent** (`tests/test_packaging_spec.py:201-208`):
```python
assert "python -m pip uninstall musicstreamer" in build_ps1_source, (
    "build.ps1 step 3c must call `python -m pip uninstall musicstreamer` "
    "before running PyInstaller, so any stale dist-info from a "
    "prior install is removed from the build env. ..."
)
```

**Per RESEARCH.md Pitfall 8** — write as a POSITIVE assertion against `build_js_runtimes(` (more robust than a negative `"path": None` grep that would also flag `yt_dlp_opts.py` itself):
```python
"""Phase 79 drift-guard: both yt-dlp call sites must use build_js_runtimes()."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "musicstreamer"


def test_player_uses_build_js_runtimes():
    src = (ROOT / "player.py").read_text()
    assert src.count("build_js_runtimes(") == 1, (
        "player.py must call yt_dlp_opts.build_js_runtimes(...) exactly once "
        "(in _youtube_resolve_worker). A regression that re-introduces the "
        "inline {\"node\": {\"path\": None}} literal here is the exact bug "
        "Phase 79 / BUG-11 fixed — see commit a06549f context."
    )


def test_yt_import_uses_build_js_runtimes():
    src = (ROOT / "yt_import.py").read_text()
    assert src.count("build_js_runtimes(") == 1, (
        "yt_import.py::scan_playlist must call yt_dlp_opts.build_js_runtimes(...) "
        "exactly once. Single-source-of-truth invariant (D-10)."
    )
```

**Status:** OPTIONAL per CONTEXT.md Claude's Discretion. If included, this is a one-time test addition with no per-phase maintenance cost.

---

## Shared Patterns

### Constructor-kwarg dependency injection (default-None)
**Source:** `musicstreamer/ui_qt/main_window.py:190-202`
**Apply to:** `Player.__init__`, `scan_playlist`, `ImportDialog.__init__`, `_YtScanWorker.__init__`
```python
def __init__(self, ..., *, node_runtime=None, ...) -> None:
    ...
    self._node_runtime = node_runtime  # default None preserves backwards-compat (D-06)
```
**Why:** Threads the existing single `NodeRuntime` instance (detected once at `__main__.py:215`) without hidden global state or redundant probes. Keyword-only with default None means no existing call site breaks (Pitfall 1 / Pitfall 5).

### Module logger at INFO via `__main__.main` per-logger setLevel
**Source:** `musicstreamer/__main__.py:235-236` (existing pattern for `musicstreamer.player`, `musicstreamer.soma_import`)
**Apply to:** new `musicstreamer.yt_import` logger entry (Phase 79 adds the third line)
```python
logging.getLogger("musicstreamer.yt_import").setLevel(logging.INFO)
```

### INFO log emission inside daemon worker — use explicit conditional
**Source:** `musicstreamer/player.py:76-78` (module logger) + Pitfall 3
**Apply to:** both `_youtube_resolve_worker` and `scan_playlist`
```python
node_path = self._node_runtime.path if self._node_runtime else None  # NOT `and` — preserves None vs path-is-None distinction
_log.info("youtube resolve: node_path=%s", node_path)
```

### FakeYDL opts-recording test pattern
**Source:** `tests/test_cookies.py:120-158` (Player side) and `tests/test_yt_import_library.py:30-42` (yt_import side)
**Apply to:** all new B-79-04 through B-79-09 regression tests
**Reuse rule:** Player-side tests reuse `make_player(qtbot)` for `Player()` no-arg construction. New tests with `node_runtime=` injected MUST construct `Player(node_runtime=...)` inline (mock the pipeline factory manually). DO NOT MODIFY `make_player`.

---

## No Analog Found

None. Every Phase 79 file has a direct in-tree analog.

---

## Metadata

**Analog search scope:** `musicstreamer/`, `musicstreamer/ui_qt/`, `tests/`
**Files read for excerpts:** 9 (cookie_utils.py, runtime_check.py, main_window.py, player.py, yt_import.py, __main__.py, import_dialog.py, test_cookies.py, test_yt_import_library.py, test_player.py, test_packaging_spec.py)
**Pattern extraction date:** 2026-05-16
**Total length:** ~290 lines (target ≤ 300)
