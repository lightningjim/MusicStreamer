---
phase: 74
slug: somafm-full-station-catalog-art-pull-all-somafm-streams-and
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-14
---

# Phase 74 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + pytest-qt 4.x |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` + `tests/conftest.py` |
| **Quick run command** | `uv run --with pytest pytest tests/test_soma_import.py tests/test_main_window_soma.py -x` |
| **Full suite command** | `uv run --with pytest pytest -x` |
| **Estimated runtime** | ~30 seconds quick / ~tests baseline + ~17 new for full |

---

## Sampling Rate

- **After every task commit:** Run quick command (test_soma_import + test_main_window_soma)
- **After every plan wave:** Run wave-merge bundle (soma + aa + gbs + constants_drift + requirements_coverage)
- **Before `/gsd-verify-work`:** Full suite must be green (no new failures vs current baseline of 1 pre-existing failure per STATE.md)
- **Max feedback latency:** ~30 seconds (quick), ~30 seconds (wave merge)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 74-NN-NN | NN | N | REQ-SOMA-NN | T-74-NN / — | (to be filled by planner) | unit / qtbot / source-grep | `pytest tests/test_soma_import.py::<id> -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

> Planner fills concrete rows from RESEARCH.md "Phase Requirements → Test Map" (tests 1–17) once SOMA-NN IDs are issued in Plan 01.

---

## Wave 0 Requirements

- [ ] `tests/test_soma_import.py` — NEW; covers tests 1-9 + 14-15. Lift `_urlopen_factory` + `_make_http_error` helpers verbatim from `tests/test_aa_import.py`.
- [ ] `tests/test_main_window_soma.py` — NEW; covers tests 10-12 + 16. Lift `_FakePlayer` + `_FakeRepo` doubles + `_find_action` helper verbatim from `tests/test_main_window_gbs.py`.
- [ ] `tests/fixtures/soma_channels_3ch.json` — NEW; pruned 3-channel fixture for tests 6 + 8.
- [ ] `tests/fixtures/soma_channels_with_dedup_hit.json` — NEW; fixture whose first channel's stream URL collides with a stub repo row (test 5).
- [ ] Extend `tests/test_requirements_coverage.py` (or stub `tests/test_soma_requirements_registered.py`) — covers test 13.
- [ ] Extend `tests/test_constants_drift.py` for test 17 (Phase 61's drift-guard module is the precedent).
- No framework install needed — pytest + pytest-qt already in tree (STACK.md lines 53-54).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live SomaFM import on real catalog | SOMA-NN (TBD) | Requires live `api.somafm.com:443` reachability — guarded behind UAT to avoid CI flake | Run `/gsd-verify-work` for Phase 74; trigger hamburger → "Import SomaFM"; confirm three-state toast sequence + 46 (current snapshot) stations appear; logos render |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
