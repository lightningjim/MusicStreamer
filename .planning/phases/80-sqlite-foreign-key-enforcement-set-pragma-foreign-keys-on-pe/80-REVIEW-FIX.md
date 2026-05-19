---
phase: 80-sqlite-foreign-key-enforcement-set-pragma-foreign-keys-on-pe
fixed_at: 2026-05-19T12:55:00Z
review_path: .planning/phases/80-sqlite-foreign-key-enforcement-set-pragma-foreign-keys-on-pe/80-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 80: Code Review Fix Report

**Fixed at:** 2026-05-19T12:55:00Z
**Source review:** `.planning/phases/80-sqlite-foreign-key-enforcement-set-pragma-foreign-keys-on-pe/80-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 3 (Critical + Warning; the 4 Info findings are out of scope for this iteration)
- Fixed: 3
- Skipped: 0

## Fixed Issues

### WR-01: `_run_smoke` path bypasses the new connection factory entirely

**Files modified:** `musicstreamer/__main__.py`
**Commit:** `21fd908`
**Applied fix:** Adopted the reviewer's recommended option (a). After
`migration.run_migration()` in `_run_smoke`, added a parity block that calls
`db_connect()` + `db_init(con)` + `sweep_orphans(con)` + `con.close()`. The
smoke harness now exercises the same FK-PRAGMA invariant + BUG-10 ghost-row
healing as `_run_gui`, eliminating the documented-but-unexplained exemption.
Comment annotates the rationale and the WR-01 finding ID for grep traceability.

### WR-02: No positive-control test asserts the drift-guard stays SILENT under normal operation

**Files modified:** `tests/test_db_fk_invariants.py`
**Commit:** `3732864`
**Applied fix:** Added `test_drift_guard_silent_on_clean_connection(db_con, caplog)`
to the bottom of the suite. The test uses the existing Strategy-A `db_con`
fixture (so `paths.db_path` is monkeypatched to `tmp_path`), clears caplog,
resets the drift sentinel, opens a fresh `db_connect()` against the same
monkeypatched path, and asserts ZERO WARN records mentioning
`"PRAGMA foreign_keys is OFF after SET"`. This locks the condition polarity
in `repo.py:80` — a future inverted check (`!= 0` instead of `== 0`) would
no longer pass tests 6+7 silently. The new connection is closed in a `finally`
to avoid leaking it. Full suite (8 FK-invariant tests + 2 sole-connection-factory
tests = 10 tests) passes. Net: 8 tests in this file, up from 7.

### WR-03: Connection leaks at every `Repo(db_connect())` call site

**Files modified:** `musicstreamer/repo.py`
**Commit:** `721dec0`
**Applied fix:** Adopted the reviewer's explicit minimum-fix recommendation:
"Out-of-scope to fix in this phase, but worth tracking... At minimum, add a
one-line note to the `db_connect` docstring." Expanded the `db_connect`
docstring with a paragraph stating "Caller owns the connection lifecycle and
is responsible for calling `con.close()` — matching `sweep_orphans`'s
contract." The paragraph also enumerates the five known leaking call sites
(`aa_import.py`, `soma_import.py`, `ui_qt/import_dialog.py`,
`ui_qt/main_window.py`, `ui_qt/settings_import_dialog.py`) and references the
WR-03 finding ID + the proposed follow-up (`with db_session() as repo:`
context-manager wrapper) so the leak pattern is grep-discoverable for the
follow-up phase. Touching the call sites themselves is intentionally out of
scope per the reviewer's guidance.

## Out-of-Scope Findings (not addressed in this iteration)

The 4 Info findings (IN-01 through IN-04) are out of scope for the
`critical_warning` fix scope. They are documented in REVIEW.md for follow-up:

- **IN-01:** Implicit transaction state at PRAGMA read-back is brittle —
  add a one-line invariant comment above the read-back.
- **IN-02:** Sentinel write happens unconditionally — even when the
  read-back raises. Doc-only.
- **IN-03:** `_run_smoke` constructs `Station(provider_name=None)` despite
  the column not existing. Doc-only / cosmetic.
- **IN-04:** Source-grep gate's regex does not match `from sqlite3 import connect`
  aliasing. Doc-only acknowledgement of the static blind spot.

## Verification

- Tier 1 (re-read): performed on all 3 modified files.
- Tier 2 (syntax check): `python -c "import ast; ast.parse(...)"` on each
  modified `.py` file — all OK.
- Tier 3 (test re-run): `tests/test_db_fk_invariants.py` (8 tests, including
  the new WR-02 negative-control test) + `tests/test_db_connect_is_sole_connection_factory.py`
  (2 tests) — 10/10 pass, 0.22s.

---

_Fixed: 2026-05-19T12:55:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
