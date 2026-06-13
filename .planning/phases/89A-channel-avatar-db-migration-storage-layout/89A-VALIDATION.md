---
phase: 89A
slug: channel-avatar-db-migration-storage-layout
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-13
---

# Phase 89A — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` (implicit — no `pytest.ini`) |
| **Quick run command** | `uv run --with pytest pytest tests/test_repo.py tests/test_paths.py -x -q` |
| **Full suite command** | `uv run --with pytest pytest -x -q` |
| **Estimated runtime** | ~5 seconds (migration + path tests are in-memory/tmp_path) |

---

## Sampling Rate

- **After every task commit:** Run `uv run --with pytest pytest tests/test_repo.py tests/test_paths.py -x -q`
- **After every plan wave:** Run `uv run --with pytest pytest -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 89A-01-01 | 01 | 1 | ART-AVATAR-02 | — | N/A (pure accessor, no I/O) | unit | `pytest tests/test_paths.py::test_channel_avatars_dir_honors_root_override -x` | ❌ W0 | ⬜ pending |
| 89A-01-02 | 01 | 1 | ART-AVATAR-02 | — | N/A (purity — no mkdir on call) | unit | `pytest tests/test_paths.py::test_channel_avatars_dir_does_not_create_directory -x` | ❌ W0 | ⬜ pending |
| 89A-01-03 | 01 | 1 | ART-AVATAR-02 | — | Directory created eagerly at startup | unit | `pytest tests/test_repo.py::test_ensure_dirs_creates_channel_avatars_dir -x` | ❌ W0 | ⬜ pending |
| 89A-02-01 | 02 | 2 | ART-AVATAR-01 | — | Idempotent double `db_init()`; nullable TEXT no DEFAULT | unit | `pytest tests/test_repo.py::test_channel_avatar_path_migration_idempotent -x` | ❌ W0 | ⬜ pending |
| 89A-02-02 | 02 | 2 | ART-AVATAR-01 | — | Schema convergence: upgraded pre-89a DB == fresh DB; existing rows NULL, data preserved | unit | `pytest tests/test_repo.py::test_channel_avatar_path_schema_convergence -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Task IDs above are indicative — the planner assigns final IDs. Wave 1 = paths/directory (no dependency); Wave 2 = the `db_init()` column migration. Both can also be planned in a single wave since they touch disjoint files; the planner decides.*

---

## Wave 0 Requirements

- [ ] `tests/test_repo.py` — append `test_channel_avatar_path_migration_idempotent` (ART-AVATAR-01, D-07a)
- [ ] `tests/test_repo.py` — append `test_channel_avatar_path_schema_convergence` (ART-AVATAR-01, D-07b)
- [ ] `tests/test_repo.py` — append `test_ensure_dirs_creates_channel_avatars_dir` (ART-AVATAR-02, D-01) *(or `tests/test_assets.py` if created)*
- [ ] `tests/test_paths.py` — append `test_channel_avatars_dir_honors_root_override` (ART-AVATAR-02, D-02)
- [ ] `tests/test_paths.py` — append `test_channel_avatars_dir_does_not_create_directory` (ART-AVATAR-02, purity contract)

*Framework (pytest) already installed — no framework setup needed. Fixtures (`repo`, `_make_bare_con()`, `_reset_root_override`) already exist; reuse them.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live upgrade adds column to a real pre-existing `musicstreamer.sqlite3` | ART-AVATAR-01 | Optional sanity check against a real user DB, not just `:memory:`/tmp | On a copy of a real data dir, launch app once, then `sqlite3 musicstreamer.sqlite3 "PRAGMA table_info(stations)"` → confirm `channel_avatar_path TEXT` present with NULL for all rows |

*Automated coverage is complete for both requirements; the manual check is a belt-and-suspenders sanity pass, not a gate.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
