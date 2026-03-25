---
phase: 8
slug: filter-bar-multi-select
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-22
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | none — runs via `pytest tests/` |
| **Quick run command** | `cd /home/kcreasey/OneDrive/Projects/MusicStreamer && python -m pytest tests/test_filter_utils.py -x -q` |
| **Full suite command** | `cd /home/kcreasey/OneDrive/Projects/MusicStreamer && python -m pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_filter_utils.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 8-01-01 | 01 | 0 | BROWSE-02, BROWSE-03 | unit | `python -m pytest tests/test_filter_utils.py -x -q` | ❌ W0 | ⬜ pending |
| 8-01-02 | 01 | 1 | BROWSE-02, BROWSE-03 | unit | `python -m pytest tests/test_filter_utils.py -x -q` | ✅ after W0 | ⬜ pending |
| 8-01-03 | 01 | 1 | BROWSE-02, BROWSE-03 | unit | `python -m pytest tests/ -q` | ✅ after W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_filter_utils.py` — append `test_matches_filter_multi_*` cases covering:
  - multi-provider OR logic (station matches any selected provider)
  - multi-tag OR logic (station matches any selected tag)
  - provider AND tag AND composition
  - empty sets = inactive (returns all)
  - casefold normalization for tag matching

*Existing test file present — new test functions appended, not a new file.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Chip × button dismisses chip visually and removes filter | BROWSE-02, BROWSE-03 | GTK widget interaction | Click a chip to select it; click × — chip should deactivate, list should update |
| Chips scroll horizontally when overflow | BROWSE-02 | Visual layout | Add enough stations with distinct providers to overflow chip row; verify horizontal scroll appears |
| Clear button deselects all chips | BROWSE-02, BROWSE-03 | GTK widget interaction | Select multiple chips, click Clear — all chips deselect, full grouped list returns |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
