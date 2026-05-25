---
phase: 79-fix-youtube-stream-exhausted-when-launched-via-desktop-app-w
reviewed: 2026-05-16T14:35:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - musicstreamer/__main__.py
  - musicstreamer/player.py
  - musicstreamer/ui_qt/import_dialog.py
  - musicstreamer/ui_qt/main_window.py
  - musicstreamer/yt_dlp_opts.py
  - musicstreamer/yt_import.py
  - tests/test_player_node_runtime.py
  - tests/test_yt_dlp_opts_drift.py
  - tests/test_yt_dlp_opts.py
  - tests/test_yt_import_library.py
findings:
  critical: 0
  warning: 3
  info: 4
  total: 7
status: issues_found
---

# Phase 79: Code Review Report

**Reviewed:** 2026-05-16T14:35:00Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Phase 79 fix is **functionally sound** for the headline regression (BUG-11 —
".desktop launch strips PATH → yt-dlp's own node lookup fails → Stream
exhausted"). The implementation:

- Introduces a single-source-of-truth helper `yt_dlp_opts.build_js_runtimes`
  used at both yt-dlp call sites (`player._youtube_resolve_worker` and
  `yt_import.scan_playlist`).
- Threads a `node_runtime: NodeRuntime | None` keyword-only argument through
  `Player.__init__`, `MainWindow.__init__`, `ImportDialog.__init__`,
  `_YtScanWorker.__init__`, and `scan_playlist()` — all kwargs default to
  `None`, so existing `Player()` / `scan_playlist(url)` / `MainWindow(player,
  repo)` call sites stay working (verified by grep across 30+ test files).
- Preserves the Phase 999.7 cookie temp-copy invariant: in both call sites
  the `yt_dlp.YoutubeDL` context manager remains nested INSIDE
  `cookie_utils.temp_cookies_copy()`, so yt-dlp's `save_cookies()` on
  `__exit__` writes to the temp path, never the canonical one.
- Adds a regression-matrix test pair (`tests/test_yt_dlp_opts.py`,
  `tests/test_player_node_runtime.py`, three new `scan_playlist` tests in
  `tests/test_yt_import_library.py`) covering the three NodeRuntime inputs
  (None / available+path / unavailable+None-path).
- Adds a source-grep drift-guard (`tests/test_yt_dlp_opts_drift.py`) that
  pins both call sites to the shared helper.

**Thread-safety:** All worker reads of `self._node_runtime.path` are safe.
`NodeRuntime` is `@dataclass(frozen=True)` and is set once at object
`__init__` then never mutated — no race window, no need for a lock.

**Concerns surfaced** (none blocking — all are quality / maintainability):

- WR-01 — The drift-guard's `==1` equality assertion is brittle: a legitimate
  future second helper call (or even a comment that mentions
  `build_js_runtimes(`) breaks the test without indicating a real
  regression. The intent ("don't reintroduce the inline literal") is
  better expressed positively.
- WR-02 — `yt_dlp_opts.py` imports `NodeRuntime` from `runtime_check`, which
  in turn imports `PySide6.QtWidgets.QMessageBox` at module load. The new
  "yt-dlp opts builder" thus transitively requires Qt to import, leaking
  a UI dependency into a logically pure helper module.
- WR-03 — `node_path` is recomputed inline in both call sites (player.py:1057,
  yt_import.py:68) purely for an INFO log; the same expression
  (`runtime.path if runtime else None`) is also embedded inside
  `build_js_runtimes`. Three copies of one trivial expression; if the
  "None means PATH lookup" contract ever changes, all three must change
  together.

## Warnings

### WR-01: drift-guard tests assert `== 1` instead of `>= 1`

**File:** `tests/test_yt_dlp_opts_drift.py:17,36`
**Issue:** Both drift-guard tests assert `src.count("build_js_runtimes(") == 1`. The intent is "this file must NOT carry the inline `{'node': {'path': None}}` literal that Phase 79 fixed." The literal-count assertion is a poor proxy:

1. A future, legitimate second helper call in `player.py` (e.g. a new yt-dlp invocation path) would FAIL this test even though the helper is being used correctly at all call sites.
2. The substring is matched anywhere in the file, including docstrings and comments. If a future maintainer adds a doc reference like `# uses build_js_runtimes(node_runtime) under the hood` to either file, the count goes to 2 and the test fails.
3. The test does NOT actually check for the regression substring (`{"node": {"path": None}}` or `{'node': {'path': None}}`) — so a regression that simultaneously adds the inline literal AND removes the helper call would still pass (count stays at 0).

**Fix:** Pin the intent directly — at least one helper call AND no inline literal:
```python
def test_player_uses_build_js_runtimes():
    src = (ROOT / "player.py").read_text()
    assert "build_js_runtimes(" in src, (
        "musicstreamer/player.py must route js_runtimes through "
        "yt_dlp_opts.build_js_runtimes(...). See Phase 79 / BUG-11."
    )
    # Negative half — guard against the exact Phase 79 regression literal.
    import re
    assert re.search(r"['\"]js_runtimes['\"]\s*:\s*\{['\"]node['\"]", src) is None, (
        "musicstreamer/player.py must NOT inline a js_runtimes dict literal. "
        "Phase 79 / BUG-11 introduced yt_dlp_opts.build_js_runtimes(...) "
        "precisely to centralize this."
    )
```
(Same shape for `test_yt_import_uses_build_js_runtimes`.)

### WR-02: `yt_dlp_opts` transitively imports PySide6

**File:** `musicstreamer/yt_dlp_opts.py:33`
**Issue:** Module-level `from musicstreamer.runtime_check import NodeRuntime` pulls in `musicstreamer.runtime_check`, which at module load executes `from PySide6.QtWidgets import QMessageBox` (runtime_check.py:20) and resolves three enum constants. Net effect: importing the logically pure "yt-dlp js_runtimes opts builder" requires Qt to be installed and importable. This breaks the layering the module's docstring claims ("single source of truth for yt-dlp js_runtimes opts"), and forecloses future reuse in any non-Qt context (CLI smoke harness already exists; a future yt-dlp-only test harness can't import the helper without Qt).

Note: `yt_import.py` already had this coupling pre-Phase 79 (it imported `NodeRuntime` only via the new kwarg type hint), but `yt_import.py` is a higher layer that legitimately participates in the import-dialog flow. `yt_dlp_opts.py` is meant to be the leaf utility.

**Fix:** Either (a) make the import TYPE_CHECKING-only and switch the parameter annotation to a string, or (b) accept a `str | None` directly and let callers do the `.path` extraction.

Option (a) — minimal diff:
```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from musicstreamer.runtime_check import NodeRuntime


def build_js_runtimes(node_runtime: "NodeRuntime | None") -> dict:
    path = node_runtime.path if node_runtime is not None else None
    return {"node": {"path": path}}
```

Option (b) is cleaner long-term but changes the helper's signature and touches both call sites + 9 tests.

### WR-03: `node_path` logging line duplicates helper's internal logic

**File:** `musicstreamer/player.py:1057`, `musicstreamer/yt_import.py:68`
**Issue:** Both call sites compute `node_path = self._node_runtime.path if self._node_runtime else None` (or the non-self form) immediately before calling `yt_dlp_opts.build_js_runtimes(...)`, then log it via `_log.info(...)`. This is the *third* copy of the same one-liner — the helper itself computes it identically at `yt_dlp_opts.py:52`. Three call sites of one expression == fan-out drift risk if the "None means PATH lookup" contract ever changes (e.g. someone decides to substitute a sentinel for the bare-None branch). The drift-guard catches only the dict literal, not the `.path if ... else None` extraction.

**Fix:** Have the helper return the resolved path (or expose a sibling helper) so the log call can use a single source:
```python
# yt_dlp_opts.py — add:
def resolved_node_path(node_runtime: NodeRuntime | None) -> str | None:
    return node_runtime.path if node_runtime is not None else None


def build_js_runtimes(node_runtime: NodeRuntime | None) -> dict:
    return {"node": {"path": resolved_node_path(node_runtime)}}
```

Then both call sites become:
```python
node_path = yt_dlp_opts.resolved_node_path(self._node_runtime)
_log.info("youtube resolve: node_path=%s", node_path)
```

Lower-effort alternative: drop the redundant log-line locals entirely and emit `_log.info("youtube resolve: node_path=%s", yt_dlp_opts.build_js_runtimes(self._node_runtime)["node"]["path"])` — uglier but eliminates the duplicate.

## Info

### IN-01: `_make_player_with_node` discards the constructed pipeline

**File:** `tests/test_player_node_runtime.py:46-49`
**Issue:** Inside the `with patch(...)` block the test constructs `player = Player(node_runtime=node_runtime)`, then on the very next line **outside** the patch block does `player._pipeline = MagicMock()`. The freshly-constructed pipeline (the same `mock_pipeline` returned by the patched `Gst.ElementFactory.make`) is immediately replaced by an unrelated MagicMock that has no bus wiring, no audio-sink, no equalizer. This works for the test as written (only `_youtube_resolve_worker` is exercised, which calls `self._pipeline.set_state(NULL)` — a MagicMock no-op), but it bypasses the realistic mock setup that `tests/test_cookies.py::make_player` keeps intact. Risk of cargo-culting if someone copies this helper for a test that *does* exercise the pipeline.

**Fix:** Drop the post-construction overwrite or document why it's needed:
```python
def _make_player_with_node(qtbot, node_runtime):
    mock_pipeline = MagicMock()
    mock_pipeline.get_bus.return_value = MagicMock()
    with patch("musicstreamer.player.Gst.ElementFactory.make", return_value=mock_pipeline):
        return Player(node_runtime=node_runtime)
```

### IN-02: `qtbot` fixture parameter is unused

**File:** `tests/test_player_node_runtime.py:39,52,63,77`
**Issue:** The three test functions and `_make_player_with_node` all accept `qtbot` as a positional fixture parameter but never call any of its methods. The fixture's only side effect (registering a top-level QWidget for auto-cleanup) is not exercised. Matches the precedent in `tests/test_cookies.py::make_player`, so it's stylistic parity — but worth noting that the dependency is purely cosmetic.

**Fix:** Drop the unused parameter, or rename to `_qtbot` so the linter doesn't flag it. Acceptable to leave as-is to match `test_cookies.py` style.

### IN-03: Phase 999.9 comment block still claims "path=None lets yt-dlp resolve it via PATH"

**File:** `musicstreamer/player.py:1065-1069`
**Issue:** The comment retained from Phase 999.9 reads:

> Node is the runtime declared by RUNTIME-01; path=None lets yt-dlp resolve it via PATH.

Followed immediately by the Phase 79 addendum on the next line:

> Phase 79 / BUG-11: pass the resolved absolute path so .desktop-launched
> instances (with stripped PATH) don't fall back to yt-dlp's own PATH lookup.

The two halves are jointly correct (path=None DOES fall through to yt-dlp's PATH lookup; Phase 79's win is exactly that we now pass a non-None path when fnm/nvm/volta/asdf resolves one). But the juxtaposition reads as contradictory on first scan. A maintainer might assume the Phase 999.9 comment is now stale and delete it, which would lose the fallback semantics rationale (`yt_dlp_opts.build_js_runtimes` returns `{"node": {"path": None}}` for the None case precisely because yt-dlp's own PATH lookup is the right fallback when NodeRuntime is genuinely absent — see `yt_dlp_opts.py:43` D-02).

**Fix:** Reword the Phase 999.9 line to make the layering explicit:
```python
# Phase 999.9: yt-dlp's library API does NOT auto-discover JS runtimes the
# way the CLI does, so an explicit js_runtimes entry is required. Phase 79
# / BUG-11 threads the resolved absolute path (or None to fall through to
# yt-dlp's own PATH lookup when NodeRuntime is genuinely absent — see
# yt_dlp_opts.build_js_runtimes D-02) through the single-source helper.
```

### IN-04: `_log.info("youtube resolve: node_path=%s", node_path)` may leak filesystem paths into logs

**File:** `musicstreamer/player.py:1058`, `musicstreamer/yt_import.py:69`
**Issue:** The INFO log emits the absolute path to the user's Node binary (e.g. `/home/kcreasey/.local/share/fnm/aliases/default/bin/node`). On its own this is fine — it's the user's own machine and `node` paths are not secret. But Phase 79's `__main__.py:239` raises `musicstreamer.yt_import` from WARNING to INFO at default verbosity *specifically* so this line surfaces in production stderr. The path leaks the username, the version manager in use, and (for nvm) the exact installed Node version. If a user pastes their console output into a bug report they're disclosing more environmental fingerprinting than they may intend.

Low severity because: (a) the path is not a secret, (b) `~` expansion would leak the username anyway, (c) the value is bounded to one log line per YouTube play / playlist scan, not spammed.

**Fix (optional)**: Log only the basename + presence flag, or move the full-path line to DEBUG and keep an INFO-level "node_path resolved (yes/no)" line:
```python
_log.info("youtube resolve: node_runtime=%s", "found" if node_path else "missing")
_log.debug("youtube resolve: node_path=%s", node_path)
```

---

_Reviewed: 2026-05-16T14:35:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
