---
phase: 17
slug: audioaddict-station-art
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-03
---

# Phase 17 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | none (pyproject.toml has no `[tool.pytest]` section) |
| **Quick run command** | `python -m pytest tests/test_aa_import.py tests/test_repo.py -q` |
| **Full suite command** | `python -m pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_aa_import.py tests/test_repo.py -q`
- **After every plan wave:** Run `python -m pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 17-01-01 | 01 | 0 | ART-01 | unit | `python -m pytest tests/test_aa_import.py -x -q` | ❌ W0 | ⬜ pending |
| 17-01-02 | 01 | 0 | ART-01 | unit | `python -m pytest tests/test_repo.py::test_update_station_art -x` | ❌ W0 | ⬜ pending |
| 17-01-03 | 01 | 0 | ART-02 | unit | `python -m pytest tests/test_aa_url_detection.py -x -q` | ❌ W0 | ⬜ pending |
| 17-01-04 | 01 | 1 | ART-01 | unit | `python -m pytest tests/test_aa_import.py::test_fetch_channels_includes_image_url -x` | ❌ W0 | ⬜ pending |
| 17-01-05 | 01 | 1 | ART-01 | unit | `python -m pytest tests/test_aa_import.py::test_fetch_channels_image_url_none_on_failure -x` | ❌ W0 | ⬜ pending |
| 17-01-06 | 01 | 1 | ART-01 | unit | `python -m pytest tests/test_aa_import.py::test_import_stations_calls_update_art -x` | ❌ W0 | ⬜ pending |
| 17-01-07 | 01 | 1 | ART-01 | unit | `python -m pytest tests/test_aa_import.py::test_import_stations_logo_failure_silent -x` | ❌ W0 | ⬜ pending |
| 17-02-01 | 02 | 2 | ART-02 | unit | `python -m pytest tests/test_aa_url_detection.py::test_is_aa_url -x` | ❌ W0 | ⬜ pending |
| 17-02-02 | 02 | 2 | ART-02 | unit | `python -m pytest tests/test_aa_url_detection.py::test_channel_key_extraction -x` | ❌ W0 | ⬜ pending |
| 17-02-03 | 02 | 2 | ART-02 | unit | `python -m pytest tests/test_aa_url_detection.py::test_fetch_aa_logo_success -x` | ❌ W0 | ⬜ pending |
| 17-02-04 | 02 | 2 | ART-02 | unit | `python -m pytest tests/test_aa_url_detection.py::test_fetch_aa_logo_failure -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_aa_import.py` — add 4 new test stubs: `test_fetch_channels_includes_image_url`, `test_fetch_channels_image_url_none_on_failure`, `test_import_stations_calls_update_art`, `test_import_stations_logo_failure_silent`
- [ ] `tests/test_repo.py` — add `test_update_station_art`
- [ ] `tests/test_aa_url_detection.py` — new file, 4 tests: `test_is_aa_url`, `test_channel_key_extraction`, `test_fetch_aa_logo_success`, `test_fetch_aa_logo_failure`

*(No new framework install needed — pytest already present and working.)*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Import dialog label transitions: "Importing stations…" → "Fetching logos…" → "Done — N imported, M skipped" | ART-01 | GTK UI state not testable via pytest | Run import with valid AA API key; observe dialog label sequence |
| Art appears in station list immediately after dialog closes | ART-01 | Visual rendering not testable via pytest | After import, verify station rows show channel logo thumbnails (not placeholder) |
| API key popover appears when no key stored; disappears on successful fetch | ART-02 | GTK popover interaction not testable via pytest | Clear stored AA key; paste AA URL in editor; verify popover shown and key saved |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
