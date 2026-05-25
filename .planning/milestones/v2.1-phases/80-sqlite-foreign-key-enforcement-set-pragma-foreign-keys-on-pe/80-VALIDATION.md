---
phase: 80
slug: sqlite-foreign-key-enforcement-set-pragma-foreign-keys-on-pe
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-18
---

# Phase 80 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (via `uv run pytest`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_db_fk_invariants.py tests/test_db_connect_is_sole_connection_factory.py -x` |
| **Full suite command** | `uv run pytest tests/` |
| **Estimated runtime** | ~2 seconds (quick); full suite per Phase 77 baseline |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_db_fk_invariants.py tests/test_db_connect_is_sole_connection_factory.py -x`
- **After every plan wave:** Run `uv run pytest tests/test_db_fk_invariants.py tests/test_db_connect_is_sole_connection_factory.py tests/test_repo.py tests/test_station_siblings.py -x`
- **Before `/gsd:verify-work`:** Full suite (`uv run pytest tests/`) must be green
- **Max feedback latency:** ~2 seconds (quick), full suite per Phase 77 INFRA-01 baseline

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 80-XX-XX | TBD | TBD | BUG-10(a) | — | DELETE station cascades to station_streams | unit | `uv run pytest tests/test_db_fk_invariants.py::test_delete_station_cascades_station_streams -x` | ❌ W0 | ⬜ pending |
| 80-XX-XX | TBD | TBD | BUG-10(a) | — | DELETE station cascades to station_siblings (a_id) | unit | `uv run pytest tests/test_db_fk_invariants.py::test_delete_station_cascades_station_siblings_a_id -x` | ❌ W0 | ⬜ pending |
| 80-XX-XX | TBD | TBD | BUG-10(a) | — | DELETE station cascades to station_siblings (b_id) | unit | `uv run pytest tests/test_db_fk_invariants.py::test_delete_station_cascades_station_siblings_b_id -x` | ❌ W0 | ⬜ pending |
| 80-XX-XX | TBD | TBD | BUG-10(a) | — | PRAGMA OFF leaks orphans (negative proof) | unit | `uv run pytest tests/test_db_fk_invariants.py::test_pragma_off_leaks_orphans_proving_pragma_is_load_bearing -x` | ❌ W0 | ⬜ pending |
| 80-XX-XX | TBD | TBD | BUG-10(c) | — | sweep_orphans removes manufactured orphans | unit | `uv run pytest tests/test_db_fk_invariants.py::test_sweep_orphans_removes_orphan_streams_and_siblings -x` | ❌ W0 | ⬜ pending |
| 80-XX-XX | TBD | TBD | BUG-10(b) | — | Drift-guard WARN fires when PRAGMA reads OFF after SET | unit (caplog) | `uv run pytest tests/test_db_fk_invariants.py::test_drift_guard_warns_when_pragma_reads_off -x` | ❌ W0 | ⬜ pending |
| 80-XX-XX | TBD | TBD | BUG-10(b) | — | Drift-guard sentinel throttles to once per session | unit | `uv run pytest tests/test_db_fk_invariants.py::test_drift_guard_logs_at_most_once_per_session -x` | ❌ W0 | ⬜ pending |
| 80-XX-XX | TBD | TBD | BUG-10(d) | — | Sole `sqlite3.connect(` callsite in production lives in `repo.py` | source-grep | `uv run pytest tests/test_db_connect_is_sole_connection_factory.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Task IDs (80-XX-XX) get filled in once PLAN.md files are generated.*

---

## Wave 0 Requirements

- [ ] `tests/test_db_fk_invariants.py` — new file; 5-7 tests covering D-13..D-16 + drift-guard log + sentinel-throttle
- [ ] `tests/test_db_connect_is_sole_connection_factory.py` — new file; source-grep gate (D-09/D-12)
- [ ] `_reset_pragma_drift_sentinel_for_tests()` helper in `musicstreamer/repo.py` — sentinel reset for cross-test isolation
- [ ] Per-test autouse fixture in `tests/test_db_fk_invariants.py` — calls the reset helper before each test

*Existing pytest + `tests/conftest.py` infrastructure (Phase 77 INFRA-01 baseline) covers all runtime needs — no framework install required.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Synphaera-style wipe-and-re-import dedup works post-sweep | BUG-10 spiritual closure | Reproduces the Phase 74 Plan 07 F-07-03 motivating scenario end-to-end with SomaFM live data | (1) Manually corrupt local db with orphan station_streams rows (or restore from a Phase 74 snapshot); (2) start app; (3) confirm INFO log line `sweep_orphans: station_streams=N ...` appears with N > 0; (4) trigger SomaFM re-import via UI; (5) confirm no duplicate streams in the imported station. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s for quick command
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
