---
phase: 7
slug: station-list-restructuring
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-22
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | pytest.ini or pyproject.toml (if exists) |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 7-01-01 | 01 | 0 | BROWSE-01 | unit | `python -m pytest tests/test_station_list.py -x -q` | ❌ W0 | ⬜ pending |
| 7-01-02 | 01 | 1 | BROWSE-01 | unit | `python -m pytest tests/test_station_list.py::test_grouped_render -x -q` | ❌ W0 | ⬜ pending |
| 7-01-03 | 01 | 1 | BROWSE-01 | unit | `python -m pytest tests/test_station_list.py::test_expander_collapsed -x -q` | ❌ W0 | ⬜ pending |
| 7-02-01 | 02 | 2 | BROWSE-04 | unit | `python -m pytest tests/test_recently_played.py -x -q` | ❌ W0 | ⬜ pending |
| 7-02-02 | 02 | 2 | BROWSE-04 | unit | `python -m pytest tests/test_recently_played.py::test_recently_played_order -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_station_list.py` — stubs for BROWSE-01 (grouped render, ExpanderRow collapse)
- [ ] `tests/test_recently_played.py` — stubs for BROWSE-04 (recently played persistence, ordering)
- [ ] `tests/conftest.py` — shared fixtures (DB setup, mock stations)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| ExpanderRow expand/collapse interaction | BROWSE-01 | GTK widget interaction requires display | Launch app, verify all groups collapsed by default, click header to expand |
| Recently Played updates after play session | BROWSE-04 | Requires live GStreamer playback | Play a station, stop, verify it appears at top of Recently Played |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
