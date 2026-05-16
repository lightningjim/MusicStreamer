---
phase: 79
slug: fix-youtube-stream-exhausted-when-launched-via-desktop-app-w
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-16
---

# Phase 79 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: 79-RESEARCH.md §Validation Architecture (researcher-derived).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 (verified via `python3 -c "import pytest; print(pytest.__version__)"`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run --with pytest pytest tests/test_yt_dlp_opts.py tests/test_player.py tests/test_yt_import_library.py tests/test_cookies.py -x` |
| **Full suite command** | `uv run --with pytest pytest tests/ -x` |
| **Estimated runtime** | ~15s quick / ~30s full (local) |

---

## Sampling Rate

- **After every task commit:** Run the quick command above.
- **After every plan wave:** Run the full suite command above.
- **Before `/gsd:verify-work`:** Full suite must be green AND live UAT (B-79-10) signed off.
- **Max feedback latency:** ~15 seconds (quick command).

---

## Per-Task Verification Map

| Behavior ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| B-79-01 | 01 | 1 | BUG-11 | — | `build_js_runtimes(None)` returns `{"node": {"path": None}}` (preserves backwards-compat) | unit | `uv run --with pytest pytest tests/test_yt_dlp_opts.py::test_build_js_runtimes_none_input -x` | ❌ W0 | ⬜ pending |
| B-79-02 | 01 | 1 | BUG-11 | — | `build_js_runtimes(NodeRuntime(available=True, path="/fake/node"))` returns `{"node": {"path": "/fake/node"}}` (the fix — abs path threaded through) | unit | `uv run --with pytest pytest tests/test_yt_dlp_opts.py::test_build_js_runtimes_available_path -x` | ❌ W0 | ⬜ pending |
| B-79-03 | 01 | 1 | BUG-11 | — | `build_js_runtimes(NodeRuntime(available=False, path=None))` returns `{"node": {"path": None}}` (genuinely-absent Node case) | unit | `uv run --with pytest pytest tests/test_yt_dlp_opts.py::test_build_js_runtimes_unavailable_none_path -x` | ❌ W0 | ⬜ pending |
| B-79-04 | 02 | 2 | BUG-11 | — | `Player(node_runtime=NodeRuntime(available=True, path="/fake/node"))._youtube_resolve_worker` passes opts with `js_runtimes["node"]["path"] == "/fake/node"` to `yt_dlp.YoutubeDL` | integration (mocked) | `uv run --with pytest pytest tests/test_player.py::test_youtube_resolve_passes_node_path_when_available -x` | ❌ W0 | ⬜ pending |
| B-79-05 | 02 | 2 | BUG-11 | — | `Player(node_runtime=None)._youtube_resolve_worker` passes opts with `js_runtimes["node"]["path"] is None` (backwards-compat for smoke harness + existing tests) | integration | `uv run --with pytest pytest tests/test_player.py::test_youtube_resolve_passes_none_when_no_node_runtime -x` | ❌ W0 | ⬜ pending |
| B-79-06 | 02 | 2 | BUG-11 | — | `Player(node_runtime=NodeRuntime(available=False, path=None))._youtube_resolve_worker` passes opts with `js_runtimes["node"]["path"] is None` | integration | `uv run --with pytest pytest tests/test_player.py::test_youtube_resolve_passes_none_when_unavailable -x` | ❌ W0 | ⬜ pending |
| B-79-07 | 03 | 2 | BUG-11 | — | `yt_import.scan_playlist(url, node_runtime=NodeRuntime(available=True, path="/fake/node"))` passes opts with `js_runtimes["node"]["path"] == "/fake/node"` to `yt_dlp.YoutubeDL` | integration (mocked) | `uv run --with pytest pytest tests/test_yt_import_library.py::test_scan_playlist_passes_node_path_when_available -x` | ❌ W0 | ⬜ pending |
| B-79-08 | 03 | 2 | BUG-11 | — | `yt_import.scan_playlist(url)` (no `node_runtime` kwarg) passes opts with `js_runtimes["node"]["path"] is None` | integration | `uv run --with pytest pytest tests/test_yt_import_library.py::test_scan_playlist_default_none_node_runtime -x` | ❌ W0 | ⬜ pending |
| B-79-09 | 03 | 2 | BUG-11 | — | `yt_import.scan_playlist(url, node_runtime=NodeRuntime(available=False, path=None))` passes opts with `js_runtimes["node"]["path"] is None` | integration | `uv run --with pytest pytest tests/test_yt_import_library.py::test_scan_playlist_passes_none_when_unavailable -x` | ❌ W0 | ⬜ pending |
| B-79-10 | 05 | 3 | BUG-11 | — | Live UAT — `.desktop` launch resolves a YT live stream end-to-end | manual | (live click on a YT station after pipx install + GNOME logout/login) | manual | ⬜ pending |
| B-79-DG-1 *(optional, Claude's Discretion per CONTEXT.md)* | 04 | 2 | BUG-11 | — | Source-grep drift-guard: only `yt_dlp_opts.py` and `tests/test_yt_dlp_opts.py` may contain `"path": None` inside a `js_runtimes` dict literal | unit (source-text) | `uv run --with pytest pytest tests/test_yt_dlp_opts_drift.py -x` | ❌ W0 (if adopted) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_yt_dlp_opts.py` — new file. Covers B-79-01, B-79-02, B-79-03.
- [ ] Extend `tests/test_player.py` (or new `tests/test_player_node_runtime.py` for scope-isolation — planner's call per CONTEXT.md Claude's Discretion). Covers B-79-04, B-79-05, B-79-06.
- [ ] Extend `tests/test_yt_import_library.py`. Covers B-79-07, B-79-08, B-79-09.
- [ ] *(Optional)* `tests/test_yt_dlp_opts_drift.py` — covers B-79-DG-1 (Claude's Discretion per CONTEXT.md).
- [ ] Framework install: N/A — `pytest` is already provisioned via `uv run --with pytest`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| B-79-10 — `.desktop` launch resolves a YT live stream end-to-end | BUG-11 | Reproducing the bug requires (a) `.desktop` launch with systemd-session-stripped PATH AND (b) Node provided exclusively via version-manager shim (fnm/nvm/volta/asdf). No CI environment reliably reproduces both conditions. The unit + integration matrix (B-79-04..B-79-09) is the regression-lock; live UAT is the closure gate. | (1) `pipx install -e . --force` (or equivalent re-install). (2) GNOME logout / login (forces fresh `.desktop` Exec= invocation). (3) Click MusicStreamer in the dock — confirm the launch was via the `.desktop` entry, NOT a terminal. (4) Play a known-good YouTube live station (e.g. Lofi Girl). (5) Confirm: audio plays within 15s, no "Stream exhausted" toast, INFO log line `youtube resolve: node_path=/home/.../node` appears in the journal. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (B-79-10 is the sole manual-only behavior, per CONTEXT.md domain boundary)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (3 new/extended test files)
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s (quick command)
- [ ] `nyquist_compliant: true` set in frontmatter after Wave 0 lands

**Approval:** pending
