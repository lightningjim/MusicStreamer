---
phase: 3
slug: icy-metadata-display
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (uv run --with pytest) |
| **Config file** | none — inline discovery |
| **Quick run command** | `uv run --with pytest pytest tests/ -q` |
| **Full suite command** | `uv run --with pytest pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run --with pytest pytest tests/ -q`
- **After every plan wave:** Run `uv run --with pytest pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 3-01-01 | 01 | 0 | NOW-01, NOW-02, NOW-03 | unit | `uv run --with pytest pytest tests/test_player_tag.py -x -q` | ❌ W0 | ⬜ pending |
| 3-02-01 | 02 | 1 | NOW-01, NOW-02 | unit | `uv run --with pytest pytest tests/test_player_tag.py -x -q` | ❌ W0 | ⬜ pending |
| 3-02-02 | 02 | 1 | NOW-03 | unit | `uv run --with pytest pytest tests/test_player_tag.py -x -q` | ❌ W0 | ⬜ pending |
| 3-03-01 | 03 | 1 | NOW-04 | manual | visual inspection — GTK widget rendering | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_player_tag.py` — stubs for NOW-01, NOW-02, NOW-03, ICY encoding heuristic, stale callback guard

*Existing test infrastructure (28 tests) covers filter and repo logic; only player TAG behavior requires new test file.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Station logo renders in left slot | NOW-04 | GTK widget rendering requires display | Run app, play station with known art path, verify 96x96 logo renders |
| Fallback icon shows when art missing | NOW-04 | GTK widget rendering requires display | Play station with no art path; verify `audio-x-generic-symbolic` appears |
| Panel background matches header | Visual | GTK CSS rendering | Run app, verify panel background color is consistent with ToolbarView header |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
