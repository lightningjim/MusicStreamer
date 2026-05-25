---
phase: 61
slug: linux-app-display-name-in-wm-dialogs-force-quit-and-other-wm
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-05
---

# Phase 61 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `61-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9+ + pytest-qt 4+ (per `pyproject.toml [project.optional-dependencies].test`) |
| **Config file** | `pyproject.toml [tool.pytest.ini_options]` (`testpaths = ["tests"]`, `markers: integration`) |
| **Quick run command** | `pytest tests/test_desktop_install.py tests/test_constants_drift.py -x` |
| **Full suite command** | `pytest` |
| **Estimated runtime** | ~3–5 s quick / ~30–60 s full |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_desktop_install.py tests/test_constants_drift.py -x`
- **After every plan wave:** Run `pytest`
- **Before `/gsd-verify-work`:** Full suite must be green AND `61-DIAGNOSTIC-LOG.md` POST-FIX section captured AND UAT signoff per D-16.
- **Max feedback latency:** ~5 seconds (quick) / ~60 seconds (full)

---

## Per-Task Verification Map

> Task IDs are placeholders matching the recommended plan structure (Plan 61-01 Diagnostic / Plan 61-02 Rename / Plan 61-03 Self-install / Plan 61-04 UAT). The planner may reslice; if so, the planner updates this map alongside PLAN.md.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 61-01-01 | 01 | 1 | BUG-08 | — | Capture BEFORE state of WM_CLASS / installed `.desktop` files / icons (no code change) | manual | (xprop / ls / gnome-shell --version) | n/a — diagnostic | ⬜ pending |
| 61-02-01 | 02 | 1 | BUG-08 | V12 | `constants.APP_ID == "org.lightningjim.MusicStreamer"` (drift guard) | unit | `pytest tests/test_constants_drift.py::test_app_id_is_lightningjim_and_matches_phase_56_aumid -x` | ❌ W0 | ⬜ pending |
| 61-02-02 | 02 | 1 | BUG-08 | V12 | No `org.example.MusicStreamer` literal remains in `musicstreamer/` Python sources | unit | `pytest tests/test_constants_drift.py::test_no_org_example_literal_remains_in_python_sources -x` | ❌ W0 | ⬜ pending |
| 61-02-03 | 02 | 1 | BUG-08 | V12 | `packaging/linux/<APP_ID>.desktop` exists | unit | `pytest tests/test_constants_drift.py::test_bundled_desktop_basename_matches_app_id -x` | ❌ W0 | ⬜ pending |
| 61-02-04 | 02 | 1 | BUG-08 | V12 | `packaging/linux/<APP_ID>.png` exists | unit | `pytest tests/test_constants_drift.py::test_bundled_icon_basename_matches_app_id -x` | ❌ W0 | ⬜ pending |
| 61-02-05 | 02 | 1 | BUG-08 | — | `__main__.py::_set_windows_aumid` + `_run_gui::setDesktopFileName` read `constants.APP_ID` | unit | `pytest tests/test_constants_drift.py -x` | ❌ W0 | ⬜ pending |
| 61-02-06 | 02 | 1 | BUG-08 | — | `mpris2._MprisRootAdaptor.DesktopEntry` returns `constants.APP_ID` | unit | `pytest tests/test_media_keys_mpris2.py -x` (existing file extended) | ✅ exists | ⬜ pending |
| 61-02-07 | 02 | 1 | BUG-08 | — | `Makefile` references the new `.desktop` basename | manual | grep check | ✅ exists | ⬜ pending |
| 61-03-01 | 03 | 2 | BUG-08 | V4 / V12 | `desktop_install.ensure_installed()` writes `.desktop` + icon to XDG paths on first call | unit | `pytest tests/test_desktop_install.py::test_first_launch_installs_files -x` | ❌ W0 | ⬜ pending |
| 61-03-02 | 03 | 2 | BUG-08 | V12 | `desktop_install.ensure_installed()` is idempotent (marker prevents repeat install) | unit | `pytest tests/test_desktop_install.py::test_idempotent_via_marker -x` | ❌ W0 | ⬜ pending |
| 61-03-03 | 03 | 2 | BUG-08 | — | `desktop_install` is a no-op on non-Linux platforms | unit | `pytest tests/test_desktop_install.py::test_no_op_off_linux -x` | ❌ W0 | ⬜ pending |
| 61-03-04 | 03 | 2 | BUG-08 | V12 | Existing user-modified `.desktop` is preserved (not overwritten) | unit | `pytest tests/test_desktop_install.py::test_existing_files_preserved -x` | ❌ W0 | ⬜ pending |
| 61-03-05 | 03 | 2 | BUG-08 | — | Best-effort hooks (`update-desktop-database`, `gtk-update-icon-cache`) are invoked | unit | `pytest tests/test_desktop_install.py::test_cache_hooks_called_best_effort -x` | ❌ W0 | ⬜ pending |
| 61-03-06 | 03 | 2 | BUG-08 | — | Missing cache tool does not raise (`FileNotFoundError` caught) | unit | `pytest tests/test_desktop_install.py::test_missing_cache_tool_does_not_raise -x` | ❌ W0 | ⬜ pending |
| 61-03-07 | 03 | 2 | BUG-08 | — | Self-install wired into `__main__.py::_run_gui` BEFORE `QApplication(...)` | unit | `pytest tests/test_main_run_gui.py -x` (NEW or existing) | ❌ W0 | ⬜ pending |
| 61-04-01 | 04 | 3 | BUG-08 | — | GNOME force-quit dialog reads "MusicStreamer" on Kyle's X11 rig (success criterion #1) | UAT (manual) | manual UAT script per RESEARCH Example 6 step 9 | n/a — D-16 gate | ⬜ pending |
| 61-04-02 | 04 | 3 | BUG-08 | — | Activities/Alt-Tab show "MusicStreamer" on Kyle's X11 rig (success criterion #2) | UAT (manual) | manual UAT script per RESEARCH Example 6 step 10 | n/a | ⬜ pending |
| 61-04-03 | 04 | 3 | BUG-08 | — | App ID migrated; D-Bus interface names + MPRIS bus name unchanged (success criterion #3 amended) | unit + manual | drift-guard tests + `busctl --user list` shows `org.mpris.MediaPlayer2.musicstreamer` | n/a | ⬜ pending |
| 61-04-04 | 04 | 3 | BUG-08 | — | Fix works on X11; Wayland behavior captured as side-effect note (success criterion #4) | UAT (manual + memo) | UAT log captures X11 behavior; CONTEXT.md notes Wayland is not a gate | n/a | ⬜ pending |
| 61-04-05 | 04 | 3 | BUG-08 | — | `61-DIAGNOSTIC-LOG.md` POST-FIX section appended | manual | grep diagnostic log for "## POST-FIX" header | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_desktop_install.py` — NEW. ~6–8 tests (~80–120 LOC) covering `ensure_installed()` idempotency, atomic writes, no-op-off-Linux, preservation of user-modified files, best-effort cache hooks, and missing-tool tolerance.
- [ ] `tests/test_constants_drift.py` — NEW. ~4 drift-guard tests (~30–40 LOC) asserting `APP_ID` value, bundled-file basenames match `APP_ID`, and no `org.example.*` Python literal remains.
- [ ] No framework install needed — pytest, pytest-qt, and `qtbot` are all already in `pyproject.toml [project.optional-dependencies].test`.
- [ ] No new `conftest.py` fixtures needed — `tmp_path` and `monkeypatch` are pytest built-ins; the existing `paths._root_override` test hook covers XDG path redirection (see `tests/test_migration.py` for the pattern).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| GNOME force-quit dialog shows "MusicStreamer" | BUG-08 / SC #1 | Shell-mediated rendering; not unit-testable without a live X11 session + GNOME Shell | RESEARCH Example 6 step 9: `xkill` the running window OR provoke hang via `kill -STOP $(pgrep -f musicstreamer)` and click. Capture screenshot; append to `61-DIAGNOSTIC-LOG.md` POST-FIX. |
| Activities / Alt-Tab show "MusicStreamer" | BUG-08 / SC #2 | Shell-mediated rendering | RESEARCH Example 6 step 10: open Activities (Super key), confirm tile name; Alt-Tab through windows, confirm name. Capture screenshot. |
| MPRIS bus name unchanged after rename (SC #3 amended) | BUG-08 / SC #3 | Verifies external-client compatibility on a live D-Bus session | `busctl --user list \| grep musicstreamer` — must show `org.mpris.MediaPlayer2.musicstreamer`. Capture in `61-DIAGNOSTIC-LOG.md` POST-FIX. |
| Wayland session note (SC #4) | BUG-08 / SC #4 | Memory locks deployment as X11; no Wayland UAT rig | Memo in `61-DIAGNOSTIC-LOG.md` noting `XDG_SESSION_TYPE` at test time and any observed Wayland behavior as a side-effect. Not a phase gate. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify (Plan 02 + 03 task chains are 100% unit-tested; Plan 01 + 04 are manual diagnostic/UAT — explicit per D-14, D-16)
- [ ] Wave 0 covers all MISSING references (`tests/test_desktop_install.py`, `tests/test_constants_drift.py`)
- [ ] No watch-mode flags
- [ ] Feedback latency < 5 s (quick) / 60 s (full)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
