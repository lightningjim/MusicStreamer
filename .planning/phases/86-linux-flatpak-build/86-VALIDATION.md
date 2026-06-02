---
phase: 86
slug: linux-flatpak-build
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-02
---

# Phase 86 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (already in project) |
| **Config file** | `pyproject.toml [tool.pytest.ini_options]` |
| **Quick run command** | `uv run --with pytest pytest tests/test_packaging_spec.py tests/test_packaging_linux_spec.py -x` |
| **Full suite command** | `uv run --with pytest pytest` |
| **Estimated runtime** | ~5 seconds (drift-guard subset); full suite ~minutes |

---

## Sampling Rate

- **After every task commit:** Run `uv run --with pytest pytest tests/test_packaging_spec.py tests/test_packaging_linux_spec.py -x`
- **After every plan wave:** Run `uv run --with pytest pytest`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds (quick subset)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| (tbd) | 01 | 0 | PKG-LIN-FP-01 | — | App ID = `io.github.kcreasey.MusicStreamer` | YAML parse | `pytest tests/test_packaging_spec.py::test_flatpak_manifest_id` | ❌ W0 | ⬜ pending |
| (tbd) | 01 | 0 | PKG-LIN-FP-03 | — | Runtime/base version pins (6.8 / ffmpeg-full 24.08 / node20) | YAML parse | `pytest tests/test_packaging_spec.py::test_flatpak_runtime_version_pins` | ❌ W0 | ⬜ pending |
| (tbd) | 01 | 0 | PKG-LIN-FP-04 | T-FP-fs / T-FP-bus | finish-args allow-list AND deny-list | YAML parse | `pytest tests/test_packaging_spec.py::test_flatpak_finish_args_allow_list` + `::test_flatpak_finish_args_deny_list` | ❌ W0 | ⬜ pending |
| (tbd) | 01 | 0 | PKG-LIN-FP-05 | T-FP-webengine | `QTWEBENGINE_DISABLE_SANDBOX=1` present | YAML parse | `pytest tests/test_packaging_spec.py::test_flatpak_qtwebengine_disable_sandbox` | ❌ W0 | ⬜ pending |
| (tbd) | 01 | 0 | PKG-LIN-FP-06 | T-FP-fs | `~/.local/share/musicstreamer:ro` mount; first-launch detect+offer | YAML parse + unit | `::test_flatpak_narrow_ro_mount` + `::test_first_launch_detection` | ❌ W0 | ⬜ pending |
| (tbd) | 01 | 0 | PKG-LIN-FP-08 | — | MPRIS2 `--own-name` present | YAML parse | `pytest tests/test_packaging_spec.py::test_flatpak_mpris2_own_name` | ❌ W0 | ⬜ pending |
| (tbd) | 01 | 0 | PKG-LIN-FP-09 | T-FP-zip | `python3-modules.yaml` exists + valid YAML | file + parse | `pytest tests/test_packaging_spec.py::test_python3_modules_yaml_exists` | ❌ W0 | ⬜ pending |
| (tbd) | 01 | 0 | PKG-LIN-FP-10 | — | appstreamcli + desktop-file-validate pass | subprocess (skip-if-not-installed) | `::test_appstreamcli_validate_passes` + `::test_desktop_file_validate_passes` | ❌ W0 | ⬜ pending |
| (tbd) | (sign) | — | signing | T-FP-tamper | build script GPG signing discipline | source-text | `pytest tests/test_packaging_linux_spec.py::test_flatpak_build_gpg_sign` | ❌ W0 | ⬜ pending |

*Manual-only (no automated coverage — see below): PKG-LIN-FP-02 (install/launch), PKG-LIN-FP-07 (audible AAC), and the in-sandbox MPRIS2/GBS-login functional behavior of FP-05/FP-08.*

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_packaging_spec.py` — Flatpak drift-guard stubs (FP-01/03/04/05/06/08/09/10) extending the existing file (D-13/D-15)
- [ ] `io.github.kcreasey.MusicStreamer.yaml` — the manifest itself (must exist before YAML-parse tests pass)
- [ ] `python3-modules.yaml` — flatpak-pip-generator output (FP-09 test target)
- [ ] `tools/linux-flatpak/metainfo/io.github.kcreasey.MusicStreamer.metainfo.xml` — appstreamcli target
- [ ] `tools/linux-flatpak/desktop/io.github.kcreasey.MusicStreamer.desktop` — desktop-file-validate target
- [ ] Tooling install: `flatpak-builder` + `flatpak install flathub org.kde.Platform//6.8 org.kde.Sdk//6.8 io.qt.PySide.BaseApp//6.8 org.freedesktop.Platform.ffmpeg-full//24.08`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Install + GNOME Software listing + `flatpak run` launch | PKG-LIN-FP-02 / SC1 | Needs a real desktop session + flatpak runtime; not headless-testable | `flatpak install --user MusicStreamer-<ver>.flatpak`; confirm GNOME Software entry; `flatpak run io.github.kcreasey.MusicStreamer` launches |
| AAC stream audible playback (DI.fm / AudioAddict / SomaFM AAC) | PKG-LIN-FP-07 / SC2 | Requires audible confirmation via PipeWire | Play each AAC tier inside the sandbox; capture audible + screenshot + transcript (evidence bundle, D-09) |
| GBS.FM login + cookie persistence across restart | PKG-LIN-FP-05 / SC3 | Interactive QtWebEngine login flow | Log in → full quit → relaunch → still logged in; no namespace error in subprocess (D-12) |
| MPRIS2 controls sandbox playback via media keys | PKG-LIN-FP-08 / SC4 | Requires real D-Bus session + media keys | `busctl --user` / `playerctl` introspect `org.mpris.MediaPlayer2.MusicStreamer` from outside sandbox + media-key press test (D-10) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s (quick subset)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
