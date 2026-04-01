---
phase: 13
slug: radio-browser-discovery
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-31
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | none (discovered via pyproject.toml presence) |
| **Quick run command** | `python3 -m pytest tests/ -q --tb=short` |
| **Full suite command** | `python3 -m pytest tests/ -q --tb=short` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/ -q --tb=short`
- **After every plan wave:** Run `python3 -m pytest tests/ -q --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 13-01-01 | 01 | 1 | DISC-01 | unit | `pytest tests/test_radio_browser.py -x` | ❌ W0 | ⬜ pending |
| 13-01-02 | 01 | 1 | DISC-02 | unit | `pytest tests/test_radio_browser.py -x` | ❌ W0 | ⬜ pending |
| 13-02-01 | 02 | 2 | DISC-04 | unit | `pytest tests/test_repo.py -x` | ✅ (add) | ⬜ pending |
| 13-02-02 | 02 | 2 | DISC-03 | manual | n/a — GStreamer/GTK | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_radio_browser.py` — stubs for DISC-01, DISC-02 (mock urllib, fixture JSON)

*Existing infrastructure (pytest) covers all framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Preview playback | DISC-03 | GStreamer/GTK integration | Play preview from dialog, verify audio plays |
| Dialog close resumes prior station | DISC-03 | Requires running app with active playback | Play station, open dialog, preview, close dialog, verify original resumes |
| Save to library appears in list | DISC-04 | Full UI integration | Save station from dialog, verify it appears in station list |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
