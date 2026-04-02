---
phase: 14
slug: youtube-playlist-import
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-01
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | none (pytest auto-discovers `tests/`) |
| **Quick run command** | `python3 -m pytest tests/test_import_dialog.py -x -q` |
| **Full suite command** | `python3 -m pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/test_import_dialog.py -x -q`
- **After every plan wave:** Run `python3 -m pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 14-01-01 | 01 | 0 | IMPORT-01 | unit | `python3 -m pytest tests/test_import_dialog.py::test_scan_filters_live_only -x` | ❌ W0 | ⬜ pending |
| 14-01-02 | 01 | 0 | IMPORT-01 | unit | `python3 -m pytest tests/test_import_dialog.py::test_import_skips_duplicate -x` | ❌ W0 | ⬜ pending |
| 14-01-03 | 01 | 0 | IMPORT-01 | unit | `python3 -m pytest tests/test_import_dialog.py::test_provider_from_playlist_channel -x` | ❌ W0 | ⬜ pending |
| 14-01-04 | 01 | 0 | IMPORT-01 | unit | `python3 -m pytest tests/test_import_dialog.py::test_parse_flat_playlist_json -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_import_dialog.py` — unit tests covering scan filtering, duplicate skip, provider derivation, JSON parsing (all IMPORT-01 cases)

*Existing pytest infrastructure requires no other changes — just add the new test file.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dialog opens from header "Import" button | IMPORT-01 | GTK4 UI — no headless test harness | Launch app, click Import button, verify dialog appears |
| Spinner shows during scan and import | IMPORT-01 | GTK4 animation state | Paste valid playlist URL, verify spinner visible during scan |
| Real-time count updates | IMPORT-01 | GTK4 label refresh during thread | Verify label changes from "0 imported" during import run |
| Stations appear in list after import | IMPORT-01 | Full app integration | Complete import, verify stations visible in station list under channel provider |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
