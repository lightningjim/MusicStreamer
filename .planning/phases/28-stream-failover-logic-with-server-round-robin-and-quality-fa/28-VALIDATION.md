---
phase: 28
slug: stream-failover-logic-with-server-round-robin-and-quality-fa
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-09
---

# Phase 28 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | none — uses uv run |
| **Quick run command** | `uv run --with pytest python -m pytest tests/ -x -q --tb=short` |
| **Full suite command** | `uv run --with pytest python -m pytest tests/ -q --tb=short` |
| **Estimated runtime** | ~2 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run --with pytest python -m pytest tests/ -x -q --tb=short`
- **After every plan wave:** Run `uv run --with pytest python -m pytest tests/ -q --tb=short`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 28-01-01 | 01 | 1 | D-01,D-03,D-04,D-05 | — | N/A | unit | `uv run --with pytest python -m pytest tests/ -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Toast notification appears on failover | D-06 | GTK toast requires running app | Run app, kill stream server, observe toast |
| Stream picker popover shows streams | D-07 | GTK widget rendering requires display | Run app, click stream picker icon, verify list |
| Manual stream switch plays selected stream | D-08 | Requires live stream playback | Run app, select different stream from picker |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
