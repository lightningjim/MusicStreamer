---
phase: 99
slug: migrate-avatar-add-path-tests-off-removed-url-edit-widget-ga
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-28
---

# Phase 99 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-qt |
| **Config file** | existing (`pytest.ini` / `pyproject.toml`) — Phase 89B/97 infra |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_twitch_provider_assign.py tests/test_edit_station_dialog_avatar.py -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q` |
| **Estimated runtime** | quick ~20-40s · full >600s (scope per project memory) |

---

## Sampling Rate

- **After every task commit:** Run the quick run command (the two migrated files)
- **After every plan wave:** Run the quick run command (single wave in this phase)
- **Before `/gsd:verify-work`:** Full suite must return to the test-clean baseline (the 9 previously-failing avatar add-path tests now green; no new failures introduced)
- **Max feedback latency:** ~40 seconds (quick); full-suite gate run once at phase close

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 99-01-01 | 01 | 1 | TEST-REGRESSION-97x89B | — | N/A | unit | `.venv/bin/python -m pytest tests/test_twitch_provider_assign.py -q` | ✅ | ⬜ pending |
| 99-01-02 | 01 | 1 | TEST-REGRESSION-97x89B | — | N/A | unit | `.venv/bin/python -m pytest tests/test_edit_station_dialog_avatar.py::test_twitch_url_enables_refresh_btn -q` | ✅ | ⬜ pending |
| 99-01-03 | 01 | 1 | TEST-REGRESSION-97x89B | — | N/A | regression | `.venv/bin/python -m pytest -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.* The two target test files already exist; this phase migrates assertions off the removed `url_edit` widget onto the `_get_canonical_url_live` / streams-table path. No new framework, fixtures, or stubs required (the reference pattern already exists in `tests/test_edit_station_dialog.py`).

---

## Manual-Only Verifications

*All phase behaviors have automated verification.* The migrated tests are themselves the verification: each still asserts the original behavioral intent (Twitch/YouTube URL enables the refresh button; provider assignment derives correctly from the canonical URL).

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none — existing infra)
- [x] No watch-mode flags
- [x] Feedback latency < 40s (quick run)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-28 (plan-checker: 0 blockers; Nyquist 8a–8d satisfied)
