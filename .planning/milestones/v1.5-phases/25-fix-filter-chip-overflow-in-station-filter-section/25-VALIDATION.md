---
phase: 25
slug: fix-filter-chip-overflow-in-station-filter-section
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-08
---

# Phase 25 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Manual visual verification (no automated UI tests in project) |
| **Config file** | none |
| **Quick run command** | `python -m musicstreamer` |
| **Full suite command** | `python -m musicstreamer` |
| **Estimated runtime** | ~5 seconds (app launch) |

---

## Sampling Rate

- **After every task commit:** Run `python -m musicstreamer`
- **After every plan wave:** Run `python -m musicstreamer`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 25-01-01 | 01 | 1 | D-01 | — | N/A | manual-only | `python -m musicstreamer` | N/A | ⬜ pending |
| 25-01-02 | 01 | 1 | D-02 | — | N/A | manual-only | `python -m musicstreamer` | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Chips wrap to multiple lines | D-01 | Visual layout verification | Launch app with many providers/tags, verify chips wrap instead of scroll |
| Provider and tag chips in separate rows | D-02 | Visual layout verification | Launch app, verify two distinct chip rows |
| Buttons remain visible | D-01 | Visual layout verification | Launch app with many chips, verify Add/Edit/Clear buttons not pushed off-screen |
| Chip toggle still works | D-01 | Interactive verification | Click provider/tag chips, verify filter activates |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
