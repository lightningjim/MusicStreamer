---
phase: 89A-channel-avatar-db-migration-storage-layout
verified: 2026-06-13T22:00:00Z
status: passed
score: 3/3 must-haves verified
overrides_applied: 0
---

# Phase 89A: Channel-Avatar DB Migration + Storage Layout — Verification Report

**Phase Goal:** Foundation for both YT and Twitch avatar work — additive SQLite column + filesystem layout in place, idempotent and rollback-safe, with zero behavior change.
**Verified:** 2026-06-13
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (3 Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC-1 | After upgrade, `PRAGMA table_info(stations)` shows `channel_avatar_path TEXT` column, NULL default, existing data unchanged | VERIFIED | `repo.py:L321` ALTER TABLE; `test_channel_avatar_path_migration_idempotent` asserts TEXT type, notnull=0, dflt_value=None; `test_channel_avatar_path_schema_convergence` asserts `ExistingFM` row survives with `channel_avatar_path IS NULL` |
| SC-2 | Migration is idempotent — `db_init()` twice does not raise; rollback/convergence test confirms fresh DB and upgraded pre-89a DB produce identical schema | VERIFIED | `test_channel_avatar_path_migration_idempotent` calls `db_init()` three times (initial + two extras) on the same connection with no raise; `test_channel_avatar_path_schema_convergence` builds a pre-89a schema (column absent), applies `db_init()`, and asserts `PRAGMA table_info` matches a fresh DB — convergence confirmed |
| SC-3 | `assets/channel-avatars/` directory created via `ensure_dirs()` eager makedirs with appropriate layout | VERIFIED | `assets.py:L10` calls `os.makedirs(paths.channel_avatars_dir(), exist_ok=True)`; `paths.channel_avatars_dir()` returns `<root>/assets/channel-avatars` (L103-110 in paths.py); `test_ensure_dirs_creates_channel_avatars_dir` confirms directory created under `tmp_path` at runtime |

**Score: 3/3 truths verified**

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/paths.py` L103-110 | `channel_avatars_dir()` pure accessor returning `<root>/assets/channel-avatars` | VERIFIED | Present, returns `os.path.join(_root(), "assets", "channel-avatars")`, respects `_root_override` |
| `musicstreamer/assets.py` L10 | `ensure_dirs()` eager makedirs for channel-avatars | VERIFIED | Third line of `ensure_dirs()` is `os.makedirs(paths.channel_avatars_dir(), exist_ok=True)` |
| `musicstreamer/repo.py` L313-324 | Idempotent `ALTER TABLE stations ADD COLUMN channel_avatar_path TEXT` after stations_new rebuild | VERIFIED | Block at L313-324, placed after Phase 83 `prerolls_fetched_at` block (L305-311) and before `sweep_orphans` (L327) — Pitfall 2 ordering satisfied |
| `tests/test_paths.py` L105-115 | Two tests: override and purity contracts for `channel_avatars_dir()` | VERIFIED | `test_channel_avatars_dir_honors_root_override` and `test_channel_avatars_dir_does_not_create_directory` present and passing |
| `tests/test_repo.py` L1156-1264 | Three tests: ensure_dirs creation, idempotency, schema convergence | VERIFIED | All three test functions present and passing |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `paths.channel_avatars_dir()` | `assets/channel-avatars` directory | `_root()` join | WIRED | Returns `os.path.join(_root(), "assets", "channel-avatars")`; `_root_override` respected |
| `assets.ensure_dirs()` | `paths.channel_avatars_dir()` | direct call | WIRED | `assets.py:L10` calls `os.makedirs(paths.channel_avatars_dir(), exist_ok=True)` |
| `repo.db_init()` ALTER block | `stations` table `channel_avatar_path` column | SQL `ALTER TABLE` | WIRED | L321 executes the ALTER; L323 catches `sqlite3.OperationalError` for idempotency |
| ALTER block placement | After stations_new rebuild | Pitfall 2 ordering | WIRED | `stations_new` rebuild ends ~L252; channel_avatar ALTER at L321; `sweep_orphans` at L327 |

---

### Scope Boundary Compliance (D-06)

| Item | Expected | Status | Evidence |
|------|----------|--------|---------|
| `models.py` Station dataclass | `channel_avatar_path` field ABSENT | VERIFIED | `grep channel_avatar_path musicstreamer/models.py` returns no output |
| Row-to-Station mappers in `repo.py` | No hydration of `channel_avatar_path` | VERIFIED | No `r["channel_avatar_path"]` or `channel_avatar_path=` assignments in mapper blocks; the only occurrence in repo.py is the ALTER statement at L321 |
| `save_station()` in `repo.py` | No persistence of `channel_avatar_path` | VERIFIED | Confirmed by absence of any `channel_avatar_path` references outside the migration block |

The "stranded column" (CR-01) and "no round-trip hydration test" (WR-01) flags from 89A-REVIEW.md are correctly out of scope per D-06. That wiring is deferred to Phase 89.

---

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|---------|
| ART-AVATAR-01 | `stations` table gains `channel_avatar_path TEXT` via idempotent additive migration; existing rows default to NULL | SATISFIED | `repo.py:L321` ALTER; three migration tests (idempotency + convergence + data preservation) |
| ART-AVATAR-02 | New filesystem directory `~/.local/share/musicstreamer/assets/channel-avatars/` for avatar PNGs | SATISFIED | `paths.channel_avatars_dir()` returns flat directory path; `ensure_dirs()` creates it eagerly; `test_ensure_dirs_creates_channel_avatars_dir` confirms |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Idempotency test | `uv run --with pytest pytest tests/test_repo.py::test_channel_avatar_path_migration_idempotent -q` | 1 passed | PASS |
| Schema convergence test | `uv run --with pytest pytest tests/test_repo.py::test_channel_avatar_path_schema_convergence -q` | 1 passed | PASS |
| Directory creation test | `uv run --with pytest pytest tests/test_repo.py::test_ensure_dirs_creates_channel_avatars_dir -q` | 1 passed | PASS |
| All phase paths tests | `uv run --with pytest pytest tests/test_paths.py -q` | 12 passed | PASS |
| Full targeted suite | `uv run --with pytest pytest tests/test_repo.py::test_channel_avatar_path_migration_idempotent tests/test_repo.py::test_channel_avatar_path_schema_convergence tests/test_repo.py::test_ensure_dirs_creates_channel_avatars_dir tests/test_paths.py -q` | 15 passed in 0.13s | PASS |

---

### Anti-Patterns Found

No blockers found. Scanned all five modified files:

- No `TBD`, `FIXME`, or `XXX` markers introduced
- No stub values or placeholder text
- No empty implementations
- `channel_avatars_dir()` is pure — confirmed by purity test passing
- `ensure_dirs()` new makedirs line has no hardcoded path (delegates to `paths.channel_avatars_dir()`)
- The column default is intentionally NULL (not a stub — this is the correct per-D-04 design)

---

### Human Verification Required

None. This is a pure DB-migration + filesystem-layout phase with no UI, no network calls, no external services, and no visual output. All three success criteria are programmatically verifiable and confirmed by tests run in this session.

---

## Summary

Phase 89A delivers exactly its stated goal and no more. All three success criteria are met by substantive, wired, tested code:

- SC-1 (column present, NULL default, data preserved): ALTER block at `repo.py:L321`, proven by idempotency and convergence tests
- SC-2 (idempotent + rollback/convergence safe): triple `db_init()` and pre-89a-to-fresh schema comparison both pass
- SC-3 (channel-avatars directory via ensure_dirs): `paths.channel_avatars_dir()` accessor wired into `assets.ensure_dirs()`, confirmed by test

The D-06 scope boundary is honored: `models.py`, the row mappers, and `save_station()` are untouched. The 15 targeted tests all pass in 0.13 seconds with zero regressions.

---

_Verified: 2026-06-13T22:00:00Z_
_Verifier: Claude (gsd-verifier)_
