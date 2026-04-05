---
phase: 19
slug: custom-accent-color
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-05
---

# Phase 19 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | pyproject.toml |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 19-01-01 | 01 | 1 | ACCENT-01 | — | N/A | unit | `python -m pytest tests/test_accent_provider.py -x -q` | ❌ W0 | ⬜ pending |
| 19-01-02 | 01 | 1 | ACCENT-01 | — | Invalid hex rejected, previous color preserved | unit | `python -m pytest tests/test_accent_provider.py::test_invalid_hex -x -q` | ❌ W0 | ⬜ pending |
| 19-01-03 | 01 | 1 | ACCENT-01 | — | N/A | unit | `python -m pytest tests/test_accent_provider.py::test_persistence -x -q` | ❌ W0 | ⬜ pending |
| 19-02-01 | 02 | 2 | ACCENT-01 | — | N/A | manual | Visual: dialog opens from header bar | N/A | ⬜ pending |
| 19-02-02 | 02 | 2 | ACCENT-01 | — | N/A | manual | Visual: preset swatches apply color immediately | N/A | ⬜ pending |
| 19-02-03 | 02 | 2 | ACCENT-01 | — | N/A | manual | Visual: hex input applies color on confirm | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_accent_provider.py` — stubs for ACCENT-01 (CSS provider, hex validation, persistence)

*Existing test infrastructure (pytest + pyproject.toml) covers the framework setup.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dialog opens from header bar button | ACCENT-01 | GTK widget interaction requires running app | Launch app, click accent button in header, verify dialog appears |
| Preset swatch applies color live | ACCENT-01 | Visual rendering requires display | Click a swatch, verify app accent changes immediately without restart |
| Hex input applies color on confirm | ACCENT-01 | Visual rendering requires display | Enter valid hex in input, click apply, verify accent updates |
| Color restored on next launch | ACCENT-01 | Requires app restart | Set accent, quit app, relaunch, verify accent color matches saved value |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
