---
phase: 69
slug: debug-why-aac-streams-aren-t-playing-in-windows-possibly-mis
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-11
---

# Phase 69 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (existing) |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/test_packaging_spec.py -x` |
| **Full suite command** | `uv run pytest -x` |
| **Estimated runtime** | ~5–15 seconds (packaging tests are static-text drift guards) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_packaging_spec.py -x`
- **After every plan wave:** Run `uv run pytest -x`
- **Before `/gsd-verify-work`:** Full suite must be green AND Windows-side UAT-LOG.md must show PASS for both AAC fixture URLs
- **Max feedback latency:** 30 seconds (Linux CI) / single-pass installer build on Win11 VM for UAT

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | WIN-05 (to be added) | — | N/A | static-drift | `uv run pytest tests/test_packaging_spec.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Filled by planner — tasks introduce: (a) `tools/check_bundle_plugins.py` source-of-truth helper, (b) `packaging/windows/build.ps1` post-bundle plugin-presence guard, (c) extension(s) to `tests/test_packaging_spec.py` drift guard, (d) `packaging/windows/README.md` conda recipe update, (e) `.planning/codebase/CONCERNS.md` documentation reconciliation, (f) operator UAT on Win11 VM logged in `69-UAT-LOG.md`.*

---

## Wave 0 Requirements

- [ ] No pytest stub additions required — `tests/test_packaging_spec.py` already exists and Phase 69 extends it
- [ ] No new framework install — pytest is already pinned

*Existing infrastructure covers all Phase 69 Linux-side validation. The phase's primary validation surface is operator-driven on the Win11 VM, gated by the static drift-guard pytest catching doc/recipe inconsistency before a build is even attempted.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| AAC stream playback on Win11 (DI.fm AAC tier fixture) | WIN-05 | Live streaming URL + Windows-only bundle; cannot be exercised by Linux pytest | Per `69-UAT-LOG.md`: force-fresh-install per Phase 56 D-08, paste fixture URL into Add Station, click Play, observe audio. Pre-fix baseline must FAIL; post-fix must PASS. |
| HE-AAC stream playback on Win11 (SomaFM HE-AAC fixture) | WIN-05 | Same as above (different codec profile) | Same UAT sequence; second fixture URL. |
| Build-time plugin-presence guard fails build when `gst_plugins/` lacks required DLLs | — (G-01) | Windows build pipeline; PowerShell exit code path | Operator deletes `dist/MusicStreamer/_internal/gst_plugins/gstlibav.dll` after a successful bundle and re-runs `build.ps1`; expects `BUILD_FAIL reason=plugin_missing` with exit code 10. |
| Post-fix bundle actually contains the required plugin DLLs | — (G-03) | Disk inspection on Win11 host | Operator runs `Get-ChildItem dist/MusicStreamer/_internal/gst_plugins/gstlibav.dll, gstaudioparsers.dll`; both files exist (>1KB). |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify (drift-guard tests) or are explicitly Manual-Only (Win11 UAT, build-time guard exercise)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (none needed — existing pytest infrastructure suffices)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s on Linux CI
- [ ] `nyquist_compliant: true` set in frontmatter (after planner fills the Per-Task table)

**Approval:** pending
