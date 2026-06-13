---
phase: 89A-channel-avatar-db-migration-storage-layout
plan: "02"
subsystem: database-migration
tags: [sqlite, migration, idempotent, schema]
dependency_graph:
  requires: [89A-01]
  provides: [channel_avatar_path-column, ART-AVATAR-01]
  affects: [musicstreamer/repo.py, tests/test_repo.py]
tech_stack:
  added: []
  patterns: [idempotent-alter-table, try-except-OperationalError, pragma-table-info-assertion, make-bare-con-convergence]
key_files:
  modified:
    - musicstreamer/repo.py
    - tests/test_repo.py
decisions:
  - "D-04: Used try/except OperationalError idiom for idempotent ALTER TABLE"
  - "D-05: ALTER block placed after Phase 83 prerolls_fetched_at block (L311), before sweep_orphans (L327) — Pitfall 2 ordering satisfied"
  - "D-06: Migration ONLY — no changes to models.py Station dataclass, row mappers, or save_station()"
  - "D-07: Both idempotency (triple db_init no raise) and schema-convergence (pre-89a == fresh) proven by tests"
metrics:
  duration: "~8 minutes"
  completed: "2026-06-13"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
---

# Phase 89A Plan 02: Channel Avatar Path DB Migration Summary

**One-liner:** Idempotent `ALTER TABLE stations ADD COLUMN channel_avatar_path TEXT` placed after Phase 83 block, with idempotency and schema-convergence tests.

## What Was Built

Added the `channel_avatar_path TEXT` column to the `stations` table via the established idempotent additive-migration idiom in `repo.py:db_init()`. The column is nullable with no DEFAULT — all existing rows automatically receive NULL. Zero behavior change beyond the column existing.

Two migration tests were added to `tests/test_repo.py`:
1. `test_channel_avatar_path_migration_idempotent` — confirms triple `db_init()` does not raise and PRAGMA table_info shows TEXT/nullable/no-DEFAULT.
2. `test_channel_avatar_path_schema_convergence` — confirms a pre-89a stations schema (without the column) upgraded via `db_init()` converges to the same PRAGMA tuple as a fresh DB, and that the pre-existing `ExistingFM` row survives with `channel_avatar_path IS NULL`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing idempotency test | a7b34ce1 | tests/test_repo.py |
| 1 (GREEN) | ALTER block in db_init() | 9d048407 | musicstreamer/repo.py |
| 2 | Schema-convergence test | 52b0fcff | tests/test_repo.py |

## Verification Results

- `grep -n "ALTER TABLE stations ADD COLUMN channel_avatar_path TEXT" musicstreamer/repo.py` returns L321 (exactly one match)
- `prerolls_fetched_at` ALTER at L307 < `channel_avatar_path` ALTER at L321 < `def sweep_orphans` at L327 (Pitfall 2 ordering satisfied)
- `git diff --name-only 86f1cb90..HEAD` returns only `musicstreamer/repo.py` and `tests/test_repo.py` (D-06 satisfied)
- `uv run --with pytest pytest tests/test_repo.py tests/test_paths.py -x -q` passes with 103 tests, 0 failures

## Deviations from Plan

None — plan executed exactly as written.

The TDD flow for Task 2 proceeded directly to GREEN (no separate RED commit) because the Task 1 feat commit already provided the full implementation. This is expected: Task 2 adds only a new test function; the implementation it validates was committed in Task 1's GREEN phase.

## Known Stubs

None — the column exists in the DB schema; no UI rendering paths reference it yet (deferred to Phase 89 per D-06).

## Threat Surface Scan

No new trust boundaries introduced. The ALTER TABLE uses a fixed string literal with no parameter interpolation. The column accepts NULL only in this phase; no user-controlled data is written until Phase 89.

## Self-Check: PASSED

- `musicstreamer/repo.py` modified: FOUND (L321 ALTER line confirmed)
- `tests/test_repo.py` modified: FOUND (both new test functions appended)
- Commit a7b34ce1 (RED test): FOUND
- Commit 9d048407 (feat ALTER): FOUND
- Commit 52b0fcff (convergence test): FOUND
- All 103 tests green: CONFIRMED
