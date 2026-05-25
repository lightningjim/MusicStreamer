---
phase: 80-sqlite-foreign-key-enforcement-set-pragma-foreign-keys-on-pe
reviewed: 2026-05-19T12:42:15Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - musicstreamer/__main__.py
  - musicstreamer/repo.py
  - tests/test_db_connect_is_sole_connection_factory.py
  - tests/test_db_fk_invariants.py
findings:
  critical: 0
  warning: 3
  info: 4
  total: 7
status: issues_found
---

# Phase 80: Code Review Report

**Reviewed:** 2026-05-19T12:42:15Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Phase 80 adds `PRAGMA foreign_keys = ON` enforcement to `db_connect()`, a runtime drift-guard read-back, a `sweep_orphans()` healer wired into `_run_gui()`, plus a source-grep gate and FK-invariant regression suite. The design is sound and the test coverage is unusually thorough (Strategy A + Strategy B fixture split, symmetry tests for sibling cascade, log-record assertions for the WARN sentinel).

The findings below are all secondary defects — no Critical issues. The most notable are: (1) `_run_smoke` is exempt from the new factory so the smoke harness never runs the PRAGMA SET; (2) the runtime drift-guard read-back inside `db_connect()` is itself untested for the happy path (no positive-control test that asserts a *non-drifted* connection emits ZERO WARN records); (3) `Repo(db_connect())` callers in `aa_import.py`, `soma_import.py`, `import_dialog.py`, `main_window.py`, and `settings_import_dialog.py` orphan the connection (no `.close()` / no `with` block) — pre-existing, but the Phase 80 hardening doubles down on this pattern and the leak is now per-thread, per-invocation. None of these block the phase but all should be tracked.

---

## Critical Issues

_(none)_

---

## Warnings

### WR-01: `_run_smoke` path bypasses the new connection factory entirely

**File:** `musicstreamer/__main__.py:20-66`
**Issue:** `_run_smoke` is now the only entry point in the program that does NOT route through `db_connect()`. It builds an in-memory `Station`/`StationStream` and calls `player.play(station)` directly — fine for that specific harness, but the smoke path also runs `migration.run_migration()` (line 36) which is the first-launch migration helper. If any future change to migration opens its own connection to the real on-disk `musicstreamer.sqlite3` via `sqlite3.connect(...)`, the source-grep gate in `tests/test_db_connect_is_sole_connection_factory.py` would catch it — but `_run_smoke` itself ALSO never exercises `sweep_orphans()`. A user running `python -m musicstreamer --smoke ...` to validate behavior after `BUG-10`-style ghost rows accumulate will not heal them, and the smoke output will not reflect the GUI-startup invariant. The docstrings on `db_connect` and `sweep_orphans` claim "every app start" / "every production caller MUST go through this function" — the smoke path is a documented exception that is not documented in either docstring.
**Fix:** Either (a) call `sweep_orphans(db_connect())` from `_run_smoke` for parity with `_run_gui`, or (b) add a one-line note to the `db_connect` docstring explicitly stating the smoke harness is exempt because it never touches the on-disk DB. Option (b) is cheapest if intentional. Recommended snippet for (a):
```python
def _run_smoke(argv: list[str], url: str) -> int:
    ...
    Gst.init(None)
    migration.run_migration()
    # Phase 80 parity: heal orphans in the smoke harness too so --smoke
    # behaves identically to --gui w.r.t. BUG-10 sweep semantics.
    from musicstreamer.repo import db_connect, db_init, sweep_orphans
    con = db_connect()
    db_init(con)
    sweep_orphans(con)
    con.close()
    ...
```

### WR-02: No positive-control test asserts the drift-guard stays SILENT under normal operation

**File:** `tests/test_db_fk_invariants.py:371-431`
**Issue:** `test_drift_guard_warns_when_pragma_reads_off` proves the WARN fires when the read-back returns 0, and `test_drift_guard_logs_at_most_once_per_session` proves the sentinel throttle works under continued drift. But there is no test that opens a real `db_connect()` (without the `_PragmaOffConnection` wrapper) and asserts ZERO WARN records were emitted. That gap means a refactor that accidentally swapped the condition (e.g. `if con.execute("PRAGMA foreign_keys").fetchone()[0] != 0:` — wrong) would still pass tests 6 and 7 (because the wrapper forces 0 → still no log under inverted logic) AND would silently start emitting the WARN on every clean startup in production. The Strategy-A `db_con` fixture already opens a real factory connection — adding a negative-control assertion to it is one line.
**Fix:** Add a test like:
```python
def test_drift_guard_silent_on_clean_connection(db_con, caplog):
    """Negative control: PRAGMA SET succeeds (read-back == 1) so the
    drift-guard MUST NOT log. Locks in the polarity of the condition
    (a future inverted check would flood the log on every startup)."""
    caplog.set_level(logging.WARNING, logger="musicstreamer.repo")
    # db_con fixture already invoked db_connect() — sentinel was flipped.
    # Re-arm and call again to capture a fresh read-back.
    _reset_pragma_drift_sentinel_for_tests()
    db_connect()
    matching = [r for r in caplog.records
                if r.name == "musicstreamer.repo"
                and "PRAGMA foreign_keys is OFF after SET" in r.getMessage()]
    assert matching == [], (
        f"drift-guard fired on a clean connection (PRAGMA ON took effect); "
        f"got {len(matching)} WARN records"
    )
```

### WR-03: Connection leaks at every `Repo(db_connect())` call site (pre-existing; amplified by Phase 80)

**File:** `musicstreamer/aa_import.py:267`, `musicstreamer/soma_import.py:398`, `musicstreamer/ui_qt/import_dialog.py:114,156`, `musicstreamer/ui_qt/main_window.py:99,117,142,170`, `musicstreamer/ui_qt/settings_import_dialog.py:70`
**Issue:** Phase 80 reinforces the "always route through `db_connect()`" contract with both a runtime guard and a source-grep gate — but every call site that wraps `Repo(db_connect())` never closes the connection. Each call opens a fresh SQLite file handle that lives until process exit (or thread exit for the QThread workers). For long-lived sessions with many imports / dialog opens this accumulates dozens of open handles per session. The pattern is pre-existing (not in the Phase 80 diff), but Phase 80 effectively blesses it by adding a per-call PRAGMA read-back (small but real wasted work on each leak) and by writing extensive docstrings that recommend `db_connect()` without telling the caller they own the lifecycle. The Strategy-A test fixture `db_con` (`tests/test_db_fk_invariants.py:60-81`) correctly calls `con.close()` in its teardown — the production code does not match this discipline.
**Fix:** Out-of-scope to fix in this phase, but worth tracking: introduce a context-manager wrapper (e.g. `with db_session() as repo:`) and migrate call sites incrementally. At minimum, add a one-line note to the `db_connect` docstring: `"Caller owns the connection lifecycle and is responsible for calling con.close()."` This matches the wording already present on `sweep_orphans` (`repo.py:290-291`).

---

## Info

### IN-01: Implicit transaction state at PRAGMA read-back is brittle

**File:** `musicstreamer/repo.py:67-76`
**Issue:** The drift-guard read-back assumes no implicit transaction is open between the `PRAGMA foreign_keys = ON;` SET and the subsequent read. This holds in the current code (`db_connect()` is the very first thing the function does on a fresh connection — no prior statements), but PRAGMA changes ARE silently ignored when issued inside a transaction in SQLite. If a future refactor inserts any DML statement between line 67 and line 69, the SET would silently no-op, and the read-back would correctly fire the WARN. So the design is robust — but a one-line comment cementing the invariant would prevent a future maintainer from "reordering for clarity" and breaking it.
**Fix:** Add a comment above line 69:
```python
# PRAGMA must precede any other statement on this connection — SQLite
# silently ignores `PRAGMA foreign_keys` issued inside an open transaction.
```

### IN-02: Sentinel write happens unconditionally — even when the read-back raises

**File:** `musicstreamer/repo.py:70-75`
**Issue:** If `con.execute("PRAGMA foreign_keys").fetchone()` raises (e.g. the connection was poisoned, or future SQLite versions change PRAGMA semantics), the exception propagates BEFORE `_pragma_drift_logged = True` runs — so subsequent calls would retry the read-back and potentially raise again. That's actually arguably the safer behavior (don't silence drift), but it means the `at most once per session` invariant the test in `tests/test_db_fk_invariants.py:402` claims is conditional on the read-back not raising. Minor.
**Fix:** Either move the sentinel assignment to a `finally` clause, or document the exception-path semantics. Recommended documentation-only fix in the docstring of `_reset_pragma_drift_sentinel_for_tests`:
```python
# Note: the sentinel is set AFTER the read-back; an exception during
# read-back leaves the sentinel un-flipped so the next db_connect() retries.
```

### IN-03: `_run_smoke` smoke harness still constructs `Station(provider_name=None)` despite the column not existing

**File:** `musicstreamer/__main__.py:53-62`
**Issue:** The Phase 80 context note explicitly calls out: "`stations.provider_id` FK to `providers.id`, no `provider_name` column — JOIN required." But `_run_smoke` constructs `Station(provider_id=None, provider_name=None, ...)`. This works fine because `Station` is a dataclass and `provider_name` is a Python-level field populated by the `LEFT JOIN providers p ON p.id = s.provider_id` in `Repo.list_stations` (`repo.py:429`). However, the smoke path never reads from the DB at all, so `provider_name=None` is technically fine. The defect is documentation-only: a future reader looking at `_run_smoke` to understand the data model would conclude `Station.provider_name` is a column, contradicting the project's documented schema. Not in the Phase 80 diff, but adjacent to the file under review.
**Fix:** Either drop the `provider_name` kwarg from the smoke `Station` literal (it's optional with a default in the dataclass — verify), or add a `# in-memory only; real Station.provider_name is hydrated via JOIN in Repo.list_stations` comment.

### IN-04: Source-grep gate name does not match its module docstring's example

**File:** `tests/test_db_connect_is_sole_connection_factory.py:1`
**Issue:** The filename describes the assertion ("connect is sole connection factory") but the actual test functions are named `test_only_one_sqlite_connect_callsite_in_production` and `test_sole_sqlite_connect_callsite_lives_in_repo_py`. Slightly verbose but extremely greppable, which is the stated intent. The only nit: the regex `_PATTERN = re.compile(r"sqlite3(\.dbapi2)?\.connect\(")` does NOT match `from sqlite3 import connect; connect(path)` — a re-export-via-import callsite. Unlikely-to-occur in practice but reachable; the docstring should acknowledge this blind spot.
**Fix:** Either widen the regex (probably overkill) or add a sentence to the module docstring noting the gate matches the `sqlite3.connect(` and `sqlite3.dbapi2.connect(` forms but not `from sqlite3 import connect` aliasing — and that the gate is "best-effort static" rather than total coverage. The runtime drift-guard covers the call-it-and-PRAGMA-stays-OFF case orthogonally, so the combined coverage is acceptable.

---

_Reviewed: 2026-05-19T12:42:15Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
