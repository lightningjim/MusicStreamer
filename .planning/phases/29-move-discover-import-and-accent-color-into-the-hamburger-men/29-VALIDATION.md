---
phase: 29
slug: move-discover-import-and-accent-color-into-the-hamburger-men
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-09
---

# Phase 29 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Manual verification (GTK UI changes) |
| **Config file** | none |
| **Quick run command** | `python -c "from musicstreamer.ui.main_window import MainWindow"` |
| **Full suite command** | `python -m musicstreamer` (launch and verify menu) |
| **Estimated runtime** | ~2 seconds (import check) |

---

## Sampling Rate

- **After every task commit:** Run `python -c "from musicstreamer.ui.main_window import MainWindow"`
- **After every plan wave:** Run `python -m musicstreamer` (launch and verify menu)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 2 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 29-01-01 | 01 | 1 | — | — | N/A | import | `python -c "from musicstreamer.ui.main_window import MainWindow"` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Hamburger menu shows 4 items in 2 sections | — | GTK menu rendering requires runtime | Launch app, click hamburger, verify Discover Stations/Import Stations in top section, Accent Color/YouTube Cookies in bottom section |
| Header bar has only search + hamburger | — | Visual layout verification | Launch app, verify no extra buttons in header bar |
| All menu items open correct dialogs | — | GTK dialog launching requires runtime | Click each menu item, verify correct dialog opens |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 2s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
