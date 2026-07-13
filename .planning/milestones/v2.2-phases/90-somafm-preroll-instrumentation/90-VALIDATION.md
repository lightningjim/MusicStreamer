---
phase: 90
slug: somafm-preroll-instrumentation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-18
---

# Phase 90 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml / pytest.ini |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_preroll_events_log.py tests/test_player_buffer_growth.py -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q` |
| **Estimated runtime** | ~600+ seconds (full suite — scope per-task runs to relevant files) |

---

## Sampling Rate

- **After every task commit:** Run the quick run command (scoped to the touched test files)
- **After every plan wave:** Run the relevant test modules (full suite >600s — scope it)
- **Before `/gsd:verify-work`:** Phase 84 D-11 replay (`tests/test_player_buffer_growth.py`) must be green
- **Max feedback latency:** ~60 seconds (scoped runs)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| {planner fills} | | | SOMA-PRE-01 | — | N/A | unit | `.venv/bin/python -m pytest tests/test_preroll_events_log.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_preroll_events_log.py` — mirror of `tests/test_buffer_events_log.py` for `preroll_log.py` (SOMA-PRE-01)
- [ ] Zero-behavior-change assertions extend `tests/test_player_buffer_growth.py` (`_set_uri` ordering + D-11 replay, SOMA-PRE-05)

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Preroll plays on bind across all SomaFM stations | SOMA-PRE-04 (verify) | Audible playback + real network; user-owned proof run | Fresh launch, play each SomaFM station, cross-check `preroll-events.log` chosen-URL + decision path |

*If none: "All phase behaviors have automated verification."*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
