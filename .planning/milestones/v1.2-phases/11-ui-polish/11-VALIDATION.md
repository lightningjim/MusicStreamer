---
phase: 11
slug: ui-polish
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-24
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` (autodiscovery) |
| **Quick run command** | `python3 -m pytest tests/ -x -q` |
| **Full suite command** | `python3 -m pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/ -x -q`
- **After every plan wave:** Run `python3 -m pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 11-01-01 | 01 | 1 | UI-01, UI-02, UI-04 | manual | N/A — visual rendering | N/A | ⬜ pending |
| 11-01-02 | 01 | 1 | UI-03 | manual | N/A — visual rendering | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

No new test files needed — all four requirements (UI-01–04) are visual/CSS only with no unit-testable behavior.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Rounded corners on panel | UI-01 | CSS visual rendering — no logic | Launch app, verify panel has rounded corners |
| Gradient background on panel | UI-02 | CSS visual rendering — no logic | Launch app, verify panel has subtle gradient |
| Station rows have more vertical padding | UI-03 | CSS visual rendering — no logic | Launch app with stations, verify rows are less cramped |
| Now Playing panel has more whitespace | UI-04 | CSS visual rendering — no logic | Play a station, verify panel has increased internal whitespace |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
