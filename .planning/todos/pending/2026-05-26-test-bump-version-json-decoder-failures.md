---
created: 2026-05-26T23:55:00.000Z
title: test_bump_version — 2 failures with JSON decoder errors
area: release-tooling
resolves_phase: TBD
files:
  - tests/test_bump_version.py::test_bump_stages_pyproject
  - tests/test_bump_version.py::test_rollback_on_simulated_commit_failure
  - tools/bump_version.py (likely)
---

## Problem

Surfaced during Phase 91 discuss-phase scout (2026-05-26). On commit `d2efdae`, `uv run pytest tests/` reports two failures in `tests/test_bump_version.py`:

- `test_bump_stages_pyproject — json.decoder...`
- `test_rollback_on_simulated_commit_failure`

Both are in the release-tooling test family, not in runtime code. Neither was in scope for Phase 91 (MPRIS bookkeeping). Failing on the current `main` baseline; not new — present at least since Phase 91 scout.

## Solution (sketch)

1. Reproduce both failures via `uv run pytest tests/test_bump_version.py -v --tb=long`.
2. Inspect the JSON decoder traceback — likely a stale fixture or a `pyproject.toml` parse step that hits a malformed test fixture.
3. Decide whether the test is asserting against a stale schema (planner moves test to match impl) or whether `tools/bump_version.py` regressed against the test (impl moves to match test).
4. Land alongside other release-tooling housekeeping; not blocking any v2.2 phase.

## Disposition

Capture for a future test-baseline cleanup phase. Not urgent — `bump_version` is dev-only tooling, not user-facing.
