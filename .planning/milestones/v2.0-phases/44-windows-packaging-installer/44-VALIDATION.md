---
phase: 44
slug: windows-packaging-installer
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-23
---

# Phase 44 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-qt (offscreen) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`), `conftest.py` at repo root |
| **Quick run command** | `pytest tests/ -x -q --ff` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~45 seconds (399 existing tests + ~20 new Phase 44 tests) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q --ff`
- **After every plan wave:** Run `pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~45 seconds (full suite)
- **Manual UAT (Windows VM):** gated — runs once at end of Phase 44 per D-19 cadence

---

## Per-Task Verification Map

> Filled by planner in Step 8. Placeholder shown below for structure; final task IDs emerge from PLAN.md files.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 44-01-01 | 01 | 0 | PKG-04 | — | Second-instance exits silently, never opens a second socket | unit | `pytest tests/test_single_instance.py::test_second_instance_forwards_activate -q` | ❌ W0 | ⬜ pending |
| 44-01-02 | 01 | 0 | RUNTIME-01 | — | Node absence surfaces warning; app continues | unit | `pytest tests/test_runtime_check.py::test_node_missing_returns_false -q` | ❌ W0 | ⬜ pending |
| 44-01-03 | 01 | 0 | PKG-03 | T-44-03 | No `subprocess.Popen/run/call` outside `_popen` helper or tests | lint | `python tools/check_subprocess_guard.py` | ❌ W0 | ⬜ pending |
| 44-02-01 | 02 | 1 | PKG-04 | — | QLocalServer binds on port/name; newConnection raises window | integration (pytest-qt) | `pytest tests/test_single_instance.py -q` | ❌ W0 | ⬜ pending |
| 44-02-02 | 02 | 1 | RUNTIME-01 | — | Hamburger menu shows conditional Node warning QAction | integration (pytest-qt) | `pytest tests/test_main_window_node_indicator.py -q` | ❌ W0 | ⬜ pending |
| 44-02-03 | 02 | 1 | PKG-01 | — | `.spec` builds a discoverable bundle entry (`musicstreamer/__main__.py`) | unit (AST parse) | `python tools/check_spec_entry.py` | ❌ W0 | ⬜ pending |
| 44-03-01 | 03 | 2 | PKG-02 | T-44-02 | Installer compiles without errors | manual (CLI) | `iscc.exe packaging/windows/MusicStreamer.iss` | ❌ W0 | ⬜ pending (UAT) |
| 44-03-02 | 03 | 2 | QA-03 | — | Installer round-trip on Windows VM | manual | `44-UAT.md` § "Installer Round-Trip" | ❌ W0 | ⬜ pending (UAT) |
| 44-04-01 | 04 | 3 | QA-05 | — | No dialog leaks `RuntimeError: Internal C++ object already deleted` | doc-audit | `grep -R "RuntimeError.*deleted" .planning/phases/` + write `44-QA05-AUDIT.md` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

> Planner: replace placeholder rows with actual task IDs/commands from generated PLAN.md files.

---

## Wave 0 Requirements

- [ ] `tests/test_single_instance.py` — stubs for PKG-04 (QLocalServer round-trip, stale-socket cleanup, activate payload)
- [ ] `tests/test_runtime_check.py` — stubs for RUNTIME-01 (`_which_node` with Windows `node.exe` preference, PATH variations)
- [ ] `tests/test_main_window_node_indicator.py` — stubs for hamburger-menu conditional QAction visibility
- [ ] `tools/check_subprocess_guard.py` — ripgrep wrapper that fails build if raw `subprocess.Popen|run|call` found in `musicstreamer/` outside `subprocess_utils.py` and `tests/`
- [ ] `tools/check_spec_entry.py` — AST parse of `packaging/windows/MusicStreamer.spec` to confirm entry point is `musicstreamer/__main__.py`
- [ ] `tests/conftest.py` — already exists; no new fixtures needed
- [ ] pytest framework — already installed (399 tests pass today)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| PyInstaller bundle plays SomaFM HTTPS audio (audible) | PKG-01 | Audio output requires real speakers + Windows VM | `44-UAT.md` § "Playback: SomaFM HTTPS" |
| DI.fm over HTTP plays (HTTPS rejected server-side) | PKG-01 | Live stream + audible check | `44-UAT.md` § "Playback: DI.fm HTTP" |
| HLS stream plays end-to-end | PKG-01 | Live stream + audible check | `44-UAT.md` § "Playback: HLS" |
| YouTube live plays WITH Node.js on PATH | PKG-01, RUNTIME-01 | yt-dlp EJS solver requires real Node.js | `44-UAT.md` § "Playback: YouTube w/ Node.js" |
| YouTube warning surfaces WITHOUT Node.js on PATH | RUNTIME-01 | Requires removing Node from PATH on live VM | `44-UAT.md` § "Playback: YouTube w/o Node.js" |
| Twitch live plays via streamlink + OAuth token | PKG-01 | Requires valid user OAuth token + live Twitch stream | `44-UAT.md` § "Playback: Twitch OAuth" |
| Multi-stream failover picks next stream on primary failure | PKG-01 | Requires forcing a stream to fail on live VM | `44-UAT.md` § "Failover" |
| SMTC overlay shows station + ICY + cover art via media keys | PKG-01, MEDIA-03 | Windows SMTC + keyboard hardware | `44-UAT.md` § "SMTC Round-Trip" |
| Installer installs to `%LOCALAPPDATA%\MusicStreamer` with Start Menu shortcut | PKG-02 | Windows installer requires real Windows shell | `44-UAT.md` § "Installer Round-Trip" |
| Second launch activates existing window (not a second instance) | PKG-04 | Windows shell shortcut + focus-steal behavior | `44-UAT.md` § "Single-Instance Activation" |
| AUMID/SMTC overlay shows app name "MusicStreamer" (not "Unknown app") | MEDIA-03, PKG-02 | Shell binding only occurs via registered Start Menu shortcut | `44-UAT.md` § "AUMID Shell Binding" |
| Uninstaller cleanly removes install dir; `%APPDATA%\musicstreamer` preserved | PKG-02 | Windows uninstaller + user data boundary | `44-UAT.md` § "Uninstaller" |
| Settings export Linux → Windows round-trip preserves stations/streams/favorites/tags/logos | QA-03 (SC-6) | Cross-OS move of ZIP + import dialog | `44-UAT.md` § "Settings Export Linux→Windows" |
| Settings export Windows → Linux round-trip preserves stations/streams/favorites/tags/logos | QA-03 (SC-6) | Cross-OS move of ZIP + import dialog | `44-UAT.md` § "Settings Export Windows→Linux" |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify (manual-UAT-only items isolated to Wave 3)
- [ ] Wave 0 covers all MISSING references (5 new test/tool stubs listed above)
- [ ] No watch-mode flags (Windows UAT is gated; not part of commit-loop)
- [ ] Feedback latency < 45s (full suite target)
- [ ] `nyquist_compliant: true` set in frontmatter (set by planner after Wave 0 stubs are written)

**Approval:** pending
