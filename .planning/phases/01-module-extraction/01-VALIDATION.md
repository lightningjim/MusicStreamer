---
phase: 1
slug: module-extraction
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-18
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | none — Wave 0 installs |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 0 | CODE-01 | infrastructure | `python -m pytest tests/ -x -q` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 1 | CODE-01 | unit | `python -m pytest tests/test_models.py -x -q` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 1 | CODE-01 | unit | `python -m pytest tests/test_repo.py -x -q` | ❌ W0 | ⬜ pending |
| 1-01-04 | 01 | 1 | CODE-01 | unit | `python -m pytest tests/test_player.py -x -q` | ❌ W0 | ⬜ pending |
| 1-01-05 | 01 | 2 | CODE-01 | integration | `python -m pytest tests/ -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/__init__.py` — package marker
- [ ] `tests/conftest.py` — shared fixtures (mock GStreamer, mock station data)
- [ ] `tests/test_models.py` — stubs for Station/StationRow module tests
- [ ] `tests/test_repo.py` — stubs for repository/data loading tests
- [ ] `tests/test_player.py` — stubs for player module tests (Gst mocked)
- [ ] `pytest` install — `pip install pytest` (not currently installed)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| App launches and plays audio | CODE-01 | GStreamer requires real hardware/audio daemon | Run `python main.py`, select a station, verify playback starts |
| UI renders correctly | CODE-01 | GTK window requires display | Run `python main.py`, verify station list appears and is scrollable |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
