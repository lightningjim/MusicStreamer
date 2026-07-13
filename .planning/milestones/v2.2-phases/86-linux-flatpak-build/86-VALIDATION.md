---
phase: 86
slug: linux-flatpak-build
status: verified
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-02
validated: 2026-06-05
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

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|--------|
| T1 | 03 | 0 | PKG-LIN-FP-01 | — | App ID = `io.github.kcreasey.MusicStreamer` | YAML parse | `test_packaging_spec.py::test_flatpak_manifest_id` | ✅ green |
| T1 | 03 | 0 | PKG-LIN-FP-03 | — | Runtime/base version pins (6.8 / ffmpeg-full 24.08 / node20) | YAML parse | `test_packaging_spec.py::test_flatpak_runtime_version_pins` | ✅ green |
| T1 | 03 | 0 | PKG-LIN-FP-04 | T-86-01 / T-86-02 / T-86-07 | finish-args allow-list AND deny-list | YAML parse | `::test_flatpak_finish_args_allow_list` + `::test_flatpak_finish_args_deny_list` | ✅ green |
| T1 | 03 | 0 | PKG-LIN-FP-05 | T-86-03 / T-86-13 | `QTWEBENGINE_DISABLE_SANDBOX=1` + `QTWEBENGINEPROCESS_PATH` present | YAML parse | `::test_flatpak_qtwebengine_disable_sandbox` + `::test_flatpak_qtwebengineprocess_path` | ✅ green |
| T1 | 03 | 0 | PKG-LIN-FP-06 | T-86-04 / T-86-05 | `~/.local/share/musicstreamer:ro` mount; first-launch detect+offer | YAML parse + unit | `::test_flatpak_narrow_ro_mount` + `::test_first_launch_detection` + `test_flatpak_first_launch.py` (16) + `test_flatpak_import_wizard_wiring.py` (4) | ✅ green |
| T1 | 03 | 0 | PKG-LIN-FP-08 | T-86-14 | MPRIS2 `--own-name` matches `mpris2.py` source (semantic) | YAML parse + cross-check | `test_packaging_spec.py::test_flatpak_mpris2_own_name` | ✅ green |
| T1 | 03 | 0 | PKG-LIN-FP-09 | T-86-08 | `python3-modules.yaml` exists + valid YAML; PySide6 absent | file + parse | `::test_python3_modules_yaml_exists` | ✅ green |
| T1 | 03 | 0 | PKG-LIN-FP-10 | T-86-09 / T-86-12 | appstreamcli + desktop-file-validate pass; no playlist MIME | subprocess (skip-if-not-installed) | `::test_appstreamcli_validate_passes` + `::test_desktop_file_validate_passes` + `::test_flatpak_desktop_no_playlist_mime` | ✅ green |
| T1-T3 | 04 | — | PKG-LIN-FP-11 (signing) | T-86-10 / T-86-11 | build-script GPG signing + fail-fast + validator gate + CI dispatch-only | source-text | `test_packaging_linux_spec.py::test_flatpak_build_gpg_sign` + `::test_flatpak_build_fail_fast_gpg` + `::test_flatpak_build_validator_gate` + `::test_flatpak_ci_workflow_dispatch_only` | ✅ green |

*Manual-only (not headless-automatable — see Manual-Only Verifications below, all confirmed via human UAT): PKG-LIN-FP-02 (install/launch, SC1), PKG-LIN-FP-07 (audible AAC, SC2), and the in-sandbox functional behavior of FP-05 (GBS login, SC3) and FP-08 (MPRIS2 media keys, SC4).*

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Audit 2026-06-05: 60 tests pass (`test_packaging_spec.py` + `test_packaging_linux_spec.py` + `test_flatpak_first_launch.py` + `test_flatpak_import_wizard_wiring.py`), 0 skipped, 0 failed.*

---

## Wave 0 Requirements

- [x] `tests/test_packaging_spec.py` — Flatpak drift-guard suite (FP-01/03/04/05/06/08/09/10) extending the existing file (D-13/D-15)
- [x] `io.github.kcreasey.MusicStreamer.yaml` — the manifest itself (exists; YAML-parse tests green)
- [x] `python3-modules.yaml` — flatpak-pip-generator output (FP-09 test target)
- [x] `tools/linux-flatpak/metainfo/io.github.kcreasey.MusicStreamer.metainfo.xml` — appstreamcli target
- [x] `tools/linux-flatpak/desktop/io.github.kcreasey.MusicStreamer.desktop` — desktop-file-validate target
- [x] Tooling install: `flatpak-builder` + Flathub runtimes (validators installed on dev host — appstreamcli/desktop-file-validate tests run green, not skipped)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | UAT Result |
|----------|-------------|------------|------------|
| Install + GNOME Software listing + `flatpak run` launch | PKG-LIN-FP-02 / SC1 | Needs a real desktop session + flatpak runtime; not headless-testable | ✅ PASS (86-VERIFICATION.md, 2026-06-03) — required fix #6 (desktop integration) |
| AAC stream audible playback (DI.fm / AudioAddict / SomaFM AAC) | PKG-LIN-FP-07 / SC2 | Requires audible confirmation via PipeWire | ✅ PASS (86-VERIFICATION.md) — Open Question 2 resolved, no GST_PLUGIN_PATH needed |
| GBS.FM login + cookie persistence across restart | PKG-LIN-FP-05 / SC3 | Interactive QtWebEngine login flow | ✅ PASS (86-VERIFICATION.md) — required fix #5 (QtWebEngineProcess path) |
| MPRIS2 controls sandbox playback via media keys | PKG-LIN-FP-08 / SC4 | Requires real D-Bus session + media keys | ✅ PASS (86-VERIFICATION.md) — required fix #4 (own-name case mismatch) |
| First-launch import wizard offered + copy-only import | PKG-LIN-FP-06 (functional) / SC5 | Interactive first-launch GUI flow inside sandbox | ✅ PASS — initial SC5 FAIL (wizard unwired) resolved in Phase 86.1 (human UAT 3/3 PASS, 2026-06-05, 86.1-HUMAN-UAT.md) |

---

## Validation Audit 2026-06-05

| Metric | Count |
|--------|-------|
| Requirements audited | 13 (9 automatable + 4 manual-only; SC5 = manual functional half) |
| COVERED (automated, green) | 9 |
| PARTIAL (test exists, failing) | 0 |
| MISSING (no automatable test) | 0 |
| Manual-only (verified via human UAT) | 5 (SC1–SC5) |
| Tests run | 60 passed, 0 skipped, 0 failed |
| Gaps requiring auditor | 0 — no nyquist-auditor spawn needed |

All automatable requirements have green automated coverage; all manual-only criteria confirmed via human UAT (SC1–SC4 on 2026-06-03; SC5 resolved in Phase 86.1 on 2026-06-05).

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (zero MISSING)
- [x] No watch-mode flags
- [x] Feedback latency < 5s (quick subset — 0.23s observed)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** verified 2026-06-05
