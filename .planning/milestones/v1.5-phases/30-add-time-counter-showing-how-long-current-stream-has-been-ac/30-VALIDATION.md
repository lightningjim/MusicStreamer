---
phase: 30
slug: add-time-counter-showing-how-long-current-stream-has-been-ac
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-09
---

# Phase 30 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Manual verification (GTK UI timer) |
| **Config file** | none |
| **Quick run command** | `python -c "from musicstreamer.ui.main_window import MainWindow"` |
| **Full suite command** | `python -m musicstreamer` (launch and verify timer) |
| **Estimated runtime** | ~2 seconds (import check) |

---

## Sampling Rate

- **After every task commit:** Run `python -c "from musicstreamer.ui.main_window import MainWindow"`
- **After every plan wave:** Run `python -m musicstreamer` (launch and verify timer)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 2 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 30-01-01 | 01 | 1 | — | — | N/A | import | `python -c "from musicstreamer.ui.main_window import MainWindow"` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Timer shows 0:00 on play start | D-05 | GTK runtime | Play a station, verify timer appears with 0:00 |
| Timer ticks every second | D-06 | GTK runtime | Watch timer increment for 10+ seconds |
| Timer pauses when stream paused | D-03 | GTK runtime | Pause stream, verify timer freezes, unpause, verify resumes |
| Timer resets on station change | D-04 | GTK runtime | Switch stations, verify timer resets to 0:00 |
| Timer hidden when stopped | D-05 | GTK runtime | Stop playback, verify timer disappears |
| Timer icon visible | D-02 | GTK runtime | Verify timer-symbolic icon appears left of time |
| Format switches at 1 hour | D-07 | GTK runtime | Play for 60+ min or manually verify format logic |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 2s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
