---
phase: 18
slug: youtube-thumbnail-16-9
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-05
---

# Phase 18 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | pyproject.toml (no pytest section — uses defaults) |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 18-01-01 | 01 | 1 | ART-03 | — | N/A | unit | `pytest tests/ -x -q` | ✅ existing | ⬜ pending |
| 18-01-02 | 01 | 1 | ART-03 | — | N/A | manual | visual inspection (GTK rendering) | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements. No new test files needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| YouTube thumbnail displays as full 16:9 (CONTAIN) | ART-03 | GTK widget rendering requires display/visual inspection | Play a YouTube station; verify now-playing art shows full 16:9 thumbnail without center-crop |
| Non-YouTube station shows square art without distortion | ART-03 | GTK widget rendering requires display/visual inspection | Play a non-YouTube station; verify art is not letterboxed |
| iTunes cover art continues to display correctly | ART-03 | GTK widget rendering requires display/visual inspection | Play a station with ICY track titles; verify cover art updates normally |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
