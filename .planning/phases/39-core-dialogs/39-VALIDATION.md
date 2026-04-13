---
phase: 39
slug: core-dialogs
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-13
---

# Phase 39 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-qt |
| **Config file** | `pyproject.toml [tool.pytest]` |
| **Quick run command** | `python -m pytest tests/test_edit_station_dialog.py tests/test_discovery_dialog.py tests/test_import_dialog_qt.py tests/test_stream_picker.py -x` |
| **Full suite command** | `python -m pytest --ignore=tests/test_yt_import_library.py` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_edit_station_dialog.py tests/test_discovery_dialog.py tests/test_import_dialog_qt.py tests/test_stream_picker.py -x`
- **After every plan wave:** Run `python -m pytest --ignore=tests/test_yt_import_library.py`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 39-01-01 | 01 | 1 | UI-05 | — | N/A | unit (pytest-qt) | `pytest tests/test_edit_station_dialog.py -x` | ❌ W0 | ⬜ pending |
| 39-01-02 | 01 | 1 | UI-05 | — | N/A | unit | same file | ❌ W0 | ⬜ pending |
| 39-02-01 | 02 | 1 | UI-06 | — | N/A | unit (pytest-qt) | `pytest tests/test_discovery_dialog.py -x` | ❌ W0 | ⬜ pending |
| 39-03-01 | 03 | 1 | UI-07 | — | N/A | unit (pytest-qt) | `pytest tests/test_import_dialog_qt.py -x` | ❌ W0 | ⬜ pending |
| 39-04-01 | 04 | 1 | UI-13 | — | N/A | unit (pytest-qt) | `pytest tests/test_stream_picker.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_edit_station_dialog.py` — stubs for UI-05 (EditStationDialog CRUD, tag chips, stream table, delete guard)
- [ ] `tests/test_discovery_dialog.py` — stubs for UI-06 (search, preview, save)
- [ ] `tests/test_import_dialog_qt.py` — stubs for UI-07 (YouTube scan+checklist, AudioAddict import+progress)
- [ ] `tests/test_stream_picker.py` — stubs for UI-13 (visibility, selection, failover sync)

Note: `tests/test_import_dialog.py` already exists but tests the backend (`yt_import` module) only — not the Qt dialog widget. New `test_import_dialog_qt.py` covers the widget layer.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual layout of dialogs | UI-05, UI-06, UI-07 | Layout rendering requires human eye | Open each dialog, verify fields are readable and well-arranged |
| Progress bar animation during import | UI-07 | Animation timing is visual | Start an AA import, verify progress bar moves smoothly |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
