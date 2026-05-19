# Phase 80: SQLite foreign-key enforcement — set `PRAGMA foreign_keys = ON` per connection, sweep existing orphans, and add drift-guard logging so `ON DELETE CASCADE` actually fires - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-17 (Areas 1 & 2) / resumed 2026-05-18 (Areas 3 & 4, after power-outage interruption)
**Phase:** 80-sqlite-foreign-key-enforcement-set-pragma-foreign-keys-on-pe
**Areas discussed:** Orphan-sweep policy + location, Which tables to sweep, Drift-guard mechanism, Regression test surface

---

## Orphan-sweep policy + location (2026-05-17 — pre-interruption)

Resumed-context summary (full Q&A not in checkpoint JSON; captured from `.continue-here.md` and `80-DISCUSS-CHECKPOINT.json`):

**Sub-decisions captured:**

| Sub-question | Selected |
|--------------|----------|
| Sweep action | Delete + INFO-log per-table counts when N>0 |
| Sweep home | Separate `sweep_orphans(con)` function called from `__main__._run_gui` after `db_init()` |
| Run cadence | Every app start (idempotent; sub-millisecond when N=0) |
| N=0 logging | Silent on N=0; INFO line only when N>0 |

**User's choices:** All recommended options, per session note "all 7 sub-decisions so far align with the project's established patterns (focused tiny modules, log-only-when-interesting, self-healing-with-INFO-log)."

**Notes:** Rejected alternatives at the time: log-only-no-delete (defeats the dedup-by-URL re-import path that Synphaera ghosts broke), fold into `db_init` (conflates schema with data deletion), user_version-gated one-shot (would leak future drift silently).

---

## Which tables to sweep (2026-05-17 — pre-interruption)

Resumed-context summary (full Q&A not in checkpoint JSON):

**Sub-decisions captured:**

| Sub-question | Selected |
|--------------|----------|
| Tables | Only real FK child tables: `station_streams` + `station_siblings` |
| Favorites strategy | Excluded — no FK; v1.3 FAVES-01..04 intentionally persists track titles after station delete |
| `station_siblings` strategy | Single DELETE handles both `a_id` and `b_id` orphans atomically |
| Provider FK | Out of scope — `stations.provider_id` is `SET NULL` not `CASCADE`; dangling ref ≠ orphan |

**User's choices:** All recommended options.

**Notes:** Anti-pattern explicitly captured in `.continue-here.md`: "Sweep favorites as a 'soft orphan'" — would silently change documented v1.3 behavior.

---

## Drift-guard mechanism (2026-05-18 — resumed session)

### Q1 — Mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Both | Runtime self-check inside `db_connect()` AND source-grep test banning `sqlite3.connect(` outside repo.db_connect. Mirrors project precedent for source-grep gates per memory `feedback_gstreamer_mock_blind_spot.md`. | ✓ |
| Source-grep only | Static-only; cheap and deterministic but misses the case where someone removes the PRAGMA line inside `db_connect()` itself. | |
| Runtime self-check only | Catches in-factory drop, but a bypassing `sqlite3.connect()` elsewhere never touches `db_connect` and stays invisible. | |

**User's choice:** Both — defense in depth, two complementary failure modes.

### Q2 — Runtime log level if PRAGMA==OFF

| Option | Description | Selected |
|--------|-------------|----------|
| WARN | "Drift detected" — not fatal (app keeps running, just without FK enforcement); matches existing project pattern for "something is wrong but app survives." | ✓ |
| ERROR | More urgent, but app DOES still run; ERROR may be misleading. | |
| INFO | Quiet; consistent with sweep INFO line but easy to miss. | |

**User's choice:** WARN.

### Q3 — Runtime throttle

| Option | Description | Selected |
|--------|-------------|----------|
| Once per session | First `db_connect()` call checks + logs; subsequent calls in the same process skip. Uses module-level boolean sentinel. | ✓ |
| Every connection | Loudest signal but produces a wall of identical lines if drift is persistent. | |
| Once per session + cross-session persistence | Persist flag to user_data_dir; overengineered for a guard the source-grep already catches statically. | |

**User's choice:** Once per session.

### Q4 — Source-grep gate scope

| Option | Description | Selected |
|--------|-------------|----------|
| Production only — allow tests/ | Production code MUST go through `repo.db_connect`; tests/ allowed to use raw `sqlite3.connect(":memory:")` directly (needed for the negative regression test in Area 4). | ✓ |
| Everywhere including tests/ | Strictest; would block the negative-proof test. | |
| Production + tests with allow-list comment | Adds a new convention just for this phase — not worth it. | |

**User's choice:** Production only — allow tests/.

**Notes:** Negative PRAGMA-OFF test (Area 4 D-15) is the explicit reason tests/ stays open.

---

## Regression test surface (2026-05-18 — resumed session)

### Q1 — Minimum positive regression test

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, required | Insert station + stream via Repo, call `Repo.delete_station(id)`, assert station_streams row was cascade-deleted. One test, one assertion, named to make intent obvious. End-to-end FK proof via production code path. | ✓ |
| Yes + assert via PRAGMA introspection | Same test plus `PRAGMA foreign_keys` sanity check inside test body. Cheap insurance, mild redundancy with the cascade assertion itself. | |
| Skip — cascade is SQLite's job | Trust SQLite. Saves a test, loses end-to-end proof + documentation value. | |

**User's choice:** Yes, required.

### Q2 — `station_siblings` cascade symmetry test

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — both `a_id` and `b_id` | Two tests (or one parametrized); station_siblings is the OTHER cascade-leak table from Area 2 — leaving it untested means future schema change goes uncaught. | ✓ |
| Yes, but only one direction (`a_id`) | SQLite cascades both FK columns identically — testing one proves the other. Saves a test but misses asymmetric drift. | |
| Skip | Trust the schema. station_siblings is the rarer code path, so MORE likely to drift unnoticed. | |

**User's choice:** Yes — both `a_id` and `b_id`.

### Q3 — Negative PRAGMA-OFF test

| Option | Description | Selected |
|--------|-------------|----------|
| Yes | Test opens in-memory db with raw `sqlite3.connect(":memory:")` (no PRAGMA), creates stations + station_streams with CASCADE clause, deletes parent, asserts child SURVIVES. Names invariant in test name. Locks intent for future maintainers. | ✓ |
| Skip — positive test is enough | Trust the docstring + drift-guard. Positive test could pass for the wrong reason if SQLite/Python defaults change. | |

**User's choice:** Yes.

### Q4 — Docstring placement

| Option | Description | Selected |
|--------|-------------|----------|
| On `db_connect()` function only | Single source of truth, right next to the line being protected. Matches existing repo.py convention (function-level docstrings, no module-level summary). | ✓ |
| Both module-top and function | Belt-and-suspenders. Adds slight duplication. | |
| Module top only | Drawback: someone editing `db_connect()` in isolation may not scroll up to see the warning. | |

**User's choice:** On `db_connect()` function only.

---

## Claude's Discretion

- Module-level `_log` placement in `repo.py` — planner picks (mirror Phase 62 player.py convention).
- Test fixture shape — reuse `conftest.py` fixtures vs. minimal `fresh_db_with_pragma()` / `fresh_db_no_pragma()` helpers — planner decides.
- Source-grep test implementation — pure-Python `rglob + regex` vs `git grep` subprocess. Recommendation: pure Python (no git dep in test env).
- Whether to include the `sqlite3.dbapi2.connect` spelling in the grep pattern. Recommendation: yes (`re.compile(r"sqlite3(\.dbapi2)?\.connect\(")`).
- Throttle sentinel exact location/reset semantics — planner picks (`_pragma_drift_logged: bool = False` at module top is the working shape).
- Sweep log format detail — one line vs two, formatter style.

## Deferred Ideas

None — discussion stayed within phase scope.
