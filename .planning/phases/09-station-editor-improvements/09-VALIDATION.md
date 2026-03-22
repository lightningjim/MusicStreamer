---
phase: 9
slug: station-editor-improvements
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-22
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | pytest.ini or pyproject.toml |
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
| 09-01-01 | 01 | 1 | MGMT-01 | unit | `python -m pytest tests/test_station_editor.py::test_provider_picker -x -q` | ❌ W0 | ⬜ pending |
| 09-01-02 | 01 | 1 | MGMT-02 | unit | `python -m pytest tests/test_station_editor.py::test_tag_chips -x -q` | ❌ W0 | ⬜ pending |
| 09-01-03 | 01 | 1 | MGMT-03 | unit | `python -m pytest tests/test_station_editor.py::test_inline_new_provider -x -q` | ❌ W0 | ⬜ pending |
| 09-02-01 | 02 | 2 | MGMT-04 | unit | `python -m pytest tests/test_station_editor.py::test_youtube_title_fetch -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_station_editor.py` — stubs for MGMT-01, MGMT-02, MGMT-03, MGMT-04

*Existing infrastructure may cover shared fixtures if pytest is already configured.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Provider ComboRow renders existing providers from DB | MGMT-01 | Requires GTK runtime | Open station editor, verify provider dropdown populated |
| Tag chips render for station's current tags | MGMT-02 | Requires GTK runtime | Open station editor for a station with tags, verify chips shown |
| New provider entry saves without leaving dialog | MGMT-03 | Requires GTK runtime | Type new provider name, save station, verify provider persisted |
| YouTube URL auto-fills station name | MGMT-04 | Requires network + GTK | Paste YouTube URL, verify name field populated on focus-out |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
