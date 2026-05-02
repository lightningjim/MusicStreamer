---
phase: 56
slug: windows-di-fm-smtc-start-menu
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-02
---

# Phase 56 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Detection layers fully specified in 56-RESEARCH.md `## Validation Architecture`. This file is the executable contract per task — see RESEARCH.md for the rationale, failure modes, and layer boundaries.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_aa_url_detection.py tests/test_player_failover.py -x` |
| **Full suite command** | `uv run pytest -x` |
| **Estimated runtime** | ~15s quick / ~90s full |

---

## Sampling Rate

- **After every task commit:** Run quick command (helper unit tests + player failover tests)
- **After every plan wave:** Run full suite
- **Before `/gsd-verify-work`:** Full suite must be green AND Win11 VM UAT must be signed off (manual)
- **Max feedback latency:** 15 seconds for quick, 90 seconds for full

---

## Per-Task Verification Map

> Plan IDs are placeholders aligned with the planner's expected breakdown (01 = WIN-01 helper + wire, 02 = WIN-02 SMTC diagnose+fix, 03 = drift guard + UAT). Plan-checker will reconcile against actual PLAN.md frontmatter.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 56-01-01 | 01 | 1 | WIN-01 | — | URL transform is pure / no I/O | unit | `uv run pytest tests/test_aa_url_detection.py -k normalize_stream_url -x` | ❌ W0 | ⬜ pending |
| 56-01-02 | 01 | 1 | WIN-01 | — | DI.fm https→http rewrite is idempotent | unit | `uv run pytest tests/test_aa_url_detection.py -k normalize_stream_url_idempotent -x` | ❌ W0 | ⬜ pending |
| 56-01-03 | 01 | 2 | WIN-01 | — | _set_uri funnels every uri through normalize | integration | `uv run pytest tests/test_player_failover.py -k normalize -x` | ❌ W0 | ⬜ pending |
| 56-01-04 | 01 | 2 | WIN-01 | — | Non-DI.fm URLs pass through unchanged at player layer | integration | `uv run pytest tests/test_player_failover.py -k normalize_passthrough -x` | ❌ W0 | ⬜ pending |
| 56-02-01 | 02 | 1 | WIN-02 | — | SMTC overlay shows "MusicStreamer" | manual UAT | (Win11 VM, see Manual-Only) | n/a | ⬜ pending |
| 56-02-02 | 02 | 1 | WIN-02 | — | Shortcut System.AppUserModel.ID matches in-process AUMID | manual diag | (Get-StartApps + ctypes readback, see Manual-Only) | n/a | ⬜ pending |
| 56-03-01 | 03 | 2 | WIN-02 | — | AUMID literal in __main__.py == AppUserModelID in MusicStreamer.iss | unit | `uv run pytest tests/test_aumid_string_parity.py -x` | ❌ W0 | ⬜ pending |
| 56-03-02 | 03 | 3 | WIN-01, WIN-02 | — | UAT trial set passes (DI.fm Lounge fresh import + roundtrip + SMTC) | manual UAT | (Win11 VM, see Manual-Only) | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_aa_url_detection.py` — extend existing file with `aa_normalize_stream_url` cases (DI.fm https→http, DI.fm http passthrough, non-DI.fm passthrough, empty/None passthrough, idempotency, malformed-URL passthrough)
- [ ] `tests/test_player_failover.py` — extend existing file with `_set_uri`-level integration test (assert `_pipeline.set_property("uri", ...)` receives the rewritten value, NOT mocking `_set_uri` itself per RESEARCH.md guidance)
- [ ] `tests/test_aumid_string_parity.py` — new file; regex grep across `musicstreamer/__main__.py` and `packaging/windows/MusicStreamer.iss` to assert the AUMID literal is identical (per Pitfall #6 in RESEARCH.md)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SMTC overlay reads "MusicStreamer" | WIN-02 | Shell-mediated rendering; not unit-testable without a Windows host (D-11) | On clean Win11 VM: (1) uninstall any prior MusicStreamer; delete `%LOCALAPPDATA%\Programs\MusicStreamer` and `%APPDATA%\Microsoft\Windows\Start Menu\Programs\MusicStreamer.lnk`; (2) install from freshly built `dist/installer/...exe`; (3) launch via Start Menu shortcut (NOT `python -m musicstreamer`); (4) start any stream; (5) press Win+K (or open SMTC overlay); (6) confirm app name reads "MusicStreamer" — NOT "Unknown app" or empty |
| Shortcut AUMID matches in-process AUMID | WIN-02 | Requires Windows COM + ctypes readback against running process (D-08) | On Win11 VM, after install: (1) `Get-StartApps \| Where-Object Name -like 'MusicStreamer*'` → AppID column must read `org.lightningjim.MusicStreamer`; (2) launch via Start Menu shortcut; (3) run the in-process AUMID readback PowerShell helper from RESEARCH.md against the running PID — must read `org.lightningjim.MusicStreamer` (same string) |
| DI.fm Lounge plays from fresh AA import | WIN-01 | DI.fm requires real network + premium key; CI cannot exercise real DI.fm endpoints | On Win11 VM after install: (1) settings → re-import AudioAddict premium credentials (fresh import flow); (2) navigate to DI.fm Lounge; (3) click play; (4) expect audible audio + ICY title display within 10 seconds |
| DI.fm Lounge plays from settings-import roundtrip | WIN-01 | Validates D-12 (rewrite covers DB rows already migrated from a Linux DB via Phase 42 settings-import ZIP) | On Win11 VM: (1) start with a Linux-exported settings ZIP that includes a stored `https://prem*.di.fm/...` row; (2) import the ZIP via Settings → Import; (3) play the imported DI.fm channel; (4) expect audible audio (rewrite must engage at the URI boundary, NOT require DB re-write) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (manual UAT items mapped to Manual-Only Verifications)
- [ ] Sampling continuity: no 3 consecutive automated tasks without verify (manual UAT tasks bracketed by automated tests on either side)
- [ ] Wave 0 covers all MISSING references (3 test file extensions / additions listed above)
- [ ] No watch-mode flags in command columns
- [ ] Feedback latency < 15s quick / 90s full
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
