---
phase: 80-sqlite-foreign-key-enforcement-set-pragma-foreign-keys-on-pe
plan: 03
subsystem: tests / FK-invariant regression suite + drift-guard caplog coverage
tags: [bug-10, sqlite, foreign-keys, regression-tests, drift-guard, caplog]
requirements: [BUG-10]
requirements_addressed: [BUG-10]
depends_on: [80-01]
wave: 2
dependency_graph:
  requires:
    - "Plan 80-01: musicstreamer.repo._reset_pragma_drift_sentinel_for_tests"
    - "Plan 80-01: musicstreamer.repo.sweep_orphans(con)"
    - "Plan 80-01: hardened musicstreamer.repo.db_connect (PRAGMA read-back + sentinel)"
  provides:
    - "tests/test_db_fk_invariants.py — 7 unit tests covering D-13/D-14/D-15/D-16 + drift-guard log (D-10) + sentinel throttle (D-11)"
    - "Per-test autouse `_reset_drift_sentinel` fixture (Pitfall 3 isolation)"
    - "Strategy-A `db_con` fixture (routes through `db_connect()` via paths.db_path monkeypatch)"
    - "`_PragmaOffConnection` test-only wrapper that forces the drift-guard read-back to return 0"
  affects:
    - "Phase 80 verify gate: phase cannot close without these regression tests being green"
    - "Future drift detection: a regression in db_connect()/sweep_orphans/drift-guard fails CI loudly"
tech_stack:
  added: []
  patterns:
    - "Strategy-A test fixture — monkeypatch `paths.db_path` BEFORE the first `db_connect()` call so the test exercises the production factory end-to-end (Pitfall 2 invariant)"
    - "Per-test autouse fixture for module-level sentinel reset (Pitfall 3 isolation)"
    - "`caplog.set_level(logging.WARNING, logger=\"musicstreamer.repo\")` explicit-capture idiom for asserting on log records emitted by a specific module logger"
    - "Connection-wrapper monkeypatch (`_PragmaOffConnection`) that intercepts a single SQL string (`'PRAGMA foreign_keys'`) while passing all other `execute` calls through to the real connection — minimal-surgery way to drive the drift-guard WARN path without modifying production code"
key_files:
  created:
    - tests/test_db_fk_invariants.py
  modified: []
decisions:
  - "Per-test autouse fixture resets the sentinel BOTH before AND after each test — defense-in-depth against any same-file test that flips the sentinel and exits without explicit teardown (Pitfall 3)."
  - "Strategy-A `db_con` fixture uses Wave-1's `db_connect()` directly rather than reusing the existing open-coded fixture from `tests/test_repo.py:7-13` — locks drift in the *factory function* surface, not just the PRAGMA line (Pitfall 1)."
  - "Drift-guard tests use a `_PragmaOffConnection` wrapper that intercepts ONLY the read-back string `\"PRAGMA foreign_keys\"` and passes everything else (including the SET statement `\"PRAGMA foreign_keys = ON;\"`) through. The SET happens against the real `:memory:` connection so all downstream `db_connect` body code stays exercised; only the read-back is forced to 0."
  - "Existing tests `tests/test_repo.py::test_cascade_delete` and `tests/test_station_siblings.py::test_cascade_on_station_delete` left in place per RESEARCH Open Questions 1+2 (duplication is cheap; coverage is the goal)."
metrics:
  duration_minutes: 8
  completed_at: 2026-05-18T00:00:00Z
  tasks_completed: 1
  files_created: 1
---

# Phase 80 Plan 03: tests/test_db_fk_invariants.py — FK Invariant Regression Suite Summary

Seven regression tests + Strategy-A fixture + autouse sentinel reset lock the Wave-1 hardening of `musicstreamer/repo.py` (Plan 80-01) into CI. Any future drift in `db_connect()`, the FK CASCADE schema, `sweep_orphans()`, or the `_pragma_drift_logged` sentinel throttle now fails loudly.

## What Was Built

### Task 1: `tests/test_db_fk_invariants.py` — seven green tests + fixtures

Created a single new file (431 lines, 7 `def test_` functions + 2 fixtures + 1 helper class + 1 helper function + 1 module-level constant) at `tests/test_db_fk_invariants.py`.

**Fixtures (both function-scoped):**

| Fixture | Role |
|---------|------|
| `_reset_drift_sentinel` (autouse) | Calls `_reset_pragma_drift_sentinel_for_tests()` before AND after every test in this file. Defense-in-depth against cross-test sentinel leak (Pitfall 3). |
| `db_con` | Strategy-A: monkeypatches `musicstreamer.paths.db_path` to return `str(tmp_path / "musicstreamer.sqlite3")` BEFORE the first `db_connect()` call (Pitfall 2), then calls `db_connect()` + `db_init(con)`. Yields the connection. Closes on teardown. |
| `repo` | Convenience: returns `Repo(db_con)` for the cascade tests that use `Repo.insert_station` / `Repo.delete_station`. |

**Tests:**

| # | Test | Maps to | Strategy | Shape |
|---|------|---------|----------|-------|
| 1 | `test_delete_station_cascades_station_streams` | D-13 | A | `repo.insert_station` → verify pre → `repo.delete_station` → assert `station_streams` count == 0 |
| 2 | `test_delete_station_cascades_station_siblings_a_id` | D-14a | A | INSERT stations 1+2 + sibling(1,2) → DELETE id=1 → assert sibling count == 0 |
| 3 | `test_delete_station_cascades_station_siblings_b_id` | D-14b | A | INSERT stations 1+2 + sibling(1,2) → DELETE id=2 → assert sibling count == 0 |
| 4 | `test_pragma_off_leaks_orphans_proving_pragma_is_load_bearing` | D-15 | B (raw `:memory:`) | NO PRAGMA SET → `executescript` minimal stations+streams schema with CASCADE → INSERT + DELETE parent → assert child SURVIVES |
| 5 | `test_sweep_orphans_removes_orphan_streams_and_siblings` | D-16 | A | PRAGMA OFF → INSERT parent+child+sibling → DELETE parent (cascade doesn't fire) → PRAGMA ON → `sweep_orphans(db_con)` → assert orphans gone |
| 6 | `test_drift_guard_warns_when_pragma_reads_off` | D-10 (planner discretion) | A + `_PragmaOffConnection` | force read-back to `(0,)` via wrapper monkeypatched into `musicstreamer.repo.sqlite3.connect` → `db_connect()` → assert exactly one WARN record on logger `musicstreamer.repo` containing `"PRAGMA foreign_keys is OFF after SET"` |
| 7 | `test_drift_guard_logs_at_most_once_per_session` | D-11 (planner discretion) | A + `_PragmaOffConnection` | same forced-OFF setup → call `db_connect()` THREE times → assert exactly one matching WARN record (sentinel throttle works) |

**Helpers (test-private):**

- `_FakeCursor` — cursor stub whose `fetchone()` returns `(0,)`.
- `_PragmaOffConnection` — wraps a real `sqlite3.Connection`; intercepts `con.execute("PRAGMA foreign_keys")` (the drift-guard read-back) and returns `_FakeCursor()`. All other `execute` calls pass through. Includes `__getattr__` / `__setattr__` so `con.row_factory = sqlite3.Row` and other attribute writes inside `db_connect()` reach the real connection.
- `_install_pragma_off_factory(monkeypatch, tmp_path)` — single-call helper used by tests 6 and 7. Monkeypatches `paths.db_path` AND `musicstreamer.repo.sqlite3.connect` so `db_connect()` opens a wrapped `:memory:` connection and the read-back returns 0.

Commit: `2d9b7ed`.

## Files Created

| File | Lines | Reason |
|------|-------|--------|
| `tests/test_db_fk_invariants.py` | 431 | 7 regression tests + Strategy-A fixture + autouse sentinel reset + drift-guard wrapper helpers |

## Verification Results

### Per-test commands (all exit 0)

| Test | Command | Result |
|------|---------|--------|
| 1 | `uv run pytest tests/test_db_fk_invariants.py::test_delete_station_cascades_station_streams -x` | passed |
| 2 | `uv run pytest tests/test_db_fk_invariants.py::test_delete_station_cascades_station_siblings_a_id -x` | passed |
| 3 | `uv run pytest tests/test_db_fk_invariants.py::test_delete_station_cascades_station_siblings_b_id -x` | passed |
| 4 | `uv run pytest tests/test_db_fk_invariants.py::test_pragma_off_leaks_orphans_proving_pragma_is_load_bearing -x` | passed |
| 5 | `uv run pytest tests/test_db_fk_invariants.py::test_sweep_orphans_removes_orphan_streams_and_siblings -x` | passed |
| 6 | `uv run pytest tests/test_db_fk_invariants.py::test_drift_guard_warns_when_pragma_reads_off -x` | passed |
| 7 | `uv run pytest tests/test_db_fk_invariants.py::test_drift_guard_logs_at_most_once_per_session -x` | passed |
| omnibus | `uv run pytest tests/test_db_fk_invariants.py -x` | 7 passed in 0.07s |

### Wider regression net

| Command | Result |
|---------|--------|
| `uv run pytest tests/test_db_fk_invariants.py tests/test_repo.py tests/test_station_siblings.py -x` | 86 passed in 0.66s |

### Source-grep gates

| Gate | Expected | Actual | Status |
|------|----------|--------|--------|
| `grep -c "^def test_" tests/test_db_fk_invariants.py` | 7 | 7 | OK |
| `grep -c "_reset_pragma_drift_sentinel_for_tests" tests/test_db_fk_invariants.py` | ≥1 | 6 | OK |
| `grep -c "monkeypatch.setattr" tests/test_db_fk_invariants.py` | ≥1 | 3 | OK |
| `grep -c "share/musicstreamer\|local/share" tests/test_db_fk_invariants.py` (must be 0 — no real-DB references) | 0 | 0 | OK |
| `grep -c 'sqlite3.connect(":memory:")' tests/test_db_fk_invariants.py` (D-15 uses raw `:memory:`) | ≥1 | 3 (1 callsite at line 197 + 2 docstring refs) | OK |

### Pitfall invariants (manual inspection)

| Pitfall | Invariant | Status |
|---------|-----------|--------|
| 1 (fixture bypass) | `db_con` fixture calls `db_connect()` directly, NOT `sqlite3.connect(...)` + PRAGMA open-coding | OK — line 80 calls `db_connect()` |
| 2 (paths.db_path read-time) | `monkeypatch.setattr` lands BEFORE the first `db_connect()` call in the fixture | OK — `monkeypatch.setattr` at lines 76-80; `db_connect()` at line 81 |
| 3 (sentinel leak) | Autouse function-scoped fixture calls `_reset_pragma_drift_sentinel_for_tests()` | OK — `_reset_drift_sentinel` autouse fixture at lines 51-59 |
| 6 (PRAGMA returns int) | Tests assert truthy-comparable values, not `is True` / `is False` | OK — `fetchone()[0] == 0` in `_PragmaOffConnection`, `COUNT(*) == 0` in cascade tests |

## Drift-Guard Test Surface Notes

- **Wrapper strategy chosen:** `_PragmaOffConnection` is monkeypatched into `musicstreamer.repo.sqlite3.connect` rather than the global `sqlite3.connect`. Reasons: (a) doesn't accidentally break other tests in the same session; (b) makes the test-only nature of the override grep-discoverable (the wrapper class lives in this test file, not in `conftest.py`); (c) the wrapper opens a *real* `:memory:` connection internally so `db_init(con)` would still work if called — though tests 6 and 7 don't call `db_init`, they only call `db_connect()`.
- **Why intercept the read-back string, not the SET:** the PRAGMA SET statement is `"PRAGMA foreign_keys = ON;"` (note the `= ON` and trailing `;`); the read-back is `"PRAGMA foreign_keys"` (no equals, no semicolon). The wrapper's `if sql == "PRAGMA foreign_keys":` check matches only the read-back, so the SET passes through to the real connection. This means `db_connect()`'s body still executes the SET as in production — only the read-back is faked.
- **Sentinel reset placement:** the autouse fixture resets BEFORE *and* AFTER every test. The AFTER reset is belt-and-suspenders — in case a test sets the sentinel via a `db_connect()` call but errors out before its own teardown.

## Deviations from Plan

None — plan executed exactly as written. All seven tests use the names specified in 80-CONTEXT.md D-13/D-14/D-15/D-16 + the planner-discretion D-10/D-11 adds. The Strategy-A vs Strategy-B fixture split matches the RESEARCH §"Fixture strategy A vs B" recommendation (Strategy A for tests 1, 2, 3, 5, 6, 7; Strategy B for test 4).

## Known Stubs

None. All seven tests are fully wired and exercise real `db_connect()`, real `db_init()`, real `sweep_orphans()`, and real `_reset_pragma_drift_sentinel_for_tests()` from `musicstreamer/repo.py` (Wave 1 surface). The drift-guard tests use a test-private `_PragmaOffConnection` wrapper — that's an intentional test fixture, not a stub of production code.

## Threat Flags

None. This plan only adds tests — no new network endpoints, no new auth paths, no new file-access patterns, no schema changes. The Strategy-A `db_con` fixture is locked to `tmp_path` (pytest-managed); the negative-proof test uses `:memory:`. T-80-08 (paths.db_path monkeypatch ordering), T-80-09 (sentinel cross-test leak), and T-80-10 (test touches real user DB) are all mitigated as specified in the plan's `<threat_model>` block.

## Decisions Made

1. **Autouse fixture resets sentinel BOTH before AND after each test** — defense in depth against any future test that flips the sentinel and exits via exception before reaching its own teardown. Cheap (one extra line of code); eliminates a latent class of test-ordering bugs.
2. **`_PragmaOffConnection` lives in the test file, not in `conftest.py`** — keeps the test file self-contained and grep-discoverable. The wrapper is narrowly scoped to "force the PRAGMA read-back to return 0" and has no value to any other test.
3. **`_install_pragma_off_factory` helper deduplicates tests 6 and 7 setup** — both tests need the exact same monkeypatch sequence (paths.db_path + sqlite3.connect). Extracting the helper makes the test intent (the assert block) the visual centerpiece of each test body.
4. **Strategy-A `db_con` is function-scoped, not module-scoped** — each test gets a fresh tmp_path DB. Module-scoped would shave a few ms per file but introduces order dependence (test 5's mid-test PRAGMA OFF would persist into a later test if it shared the connection).

## Self-Check: PASSED

- File `tests/test_db_fk_invariants.py` exists (verified inline; 431 lines; 7 `def test_` functions).
- Commit `2d9b7ed` exists in git log (verified via `git rev-parse --short HEAD`).
- All 7 individually-named pytest commands exit 0.
- Omnibus `uv run pytest tests/test_db_fk_invariants.py -x` exits 0 (7 passed in 0.07s).
- Wider regression net `uv run pytest tests/test_db_fk_invariants.py tests/test_repo.py tests/test_station_siblings.py -x` exits 0 (86 passed in 0.66s).
- All source-grep gates pass.
- Strategy-A fixture monkeypatches `paths.db_path` BEFORE the first `db_connect()` call (Pitfall 2 invariant — verified by source ordering in the fixture body at lines 76-81).
- The negative-proof test opens raw `sqlite3.connect(":memory:")` at line 197 (D-12 allows this in tests/).
- The two drift-guard tests use `caplog` and assert on log records emitted by the `musicstreamer.repo` logger.
