# Phase 80: SQLite foreign-key enforcement — set `PRAGMA foreign_keys = ON` per connection, sweep existing orphans, and add drift-guard logging so `ON DELETE CASCADE` actually fires - Context

**Gathered:** 2026-05-17 / resumed 2026-05-18
**Status:** Ready for planning

<domain>
## Phase Boundary

**Ground truth (verified):** `musicstreamer/repo.py:18-21` already sets `PRAGMA foreign_keys = ON;` on every connection — has done so since the original Phase 01-01 commit `59fc516`. The Phase 74 Plan 07 F-07-03 orphans (`Synphaera` station_streams rows that defeated dedup-by-URL on re-import) came from a manual `sqlite3`-shell `DELETE` that bypassed `db_connect()` entirely, not from a code bug.

Phase 80 is therefore mostly **tightening**, not adding:

1. **Lock the existing PRAGMA in via a regression test** — proves that `Repo.delete_station(id)` cascades to `station_streams` and `station_siblings`, and proves (via a negative test) that raw `sqlite3.connect()` without the PRAGMA leaks orphans. Future drift in either direction (PRAGMA line removed, or schema cascade flag flipped) gets caught at CI time.
2. **Sweep pre-existing orphans on every app start** — runs unconditionally; sub-millisecond when N=0; INFO-logs per-table counts only when N>0. Heals Synphaera-style ghosts left by manual shell-DELETE sessions.
3. **Drift-guard for future bypasses** — both runtime (WARN log if PRAGMA reads OFF after the SET, once per session) and static (source-grep test bans `sqlite3.connect(` outside `repo.db_connect`, allow tests/).
4. **Function-level docstring on `db_connect()`** documenting that the PRAGMA is load-bearing — so a future refactorer doesn't drop it on the floor.

**In scope:**

- **`musicstreamer/repo.py::db_connect`** — adds:
  - **Runtime drift-guard**: after the existing `PRAGMA foreign_keys = ON;` SET, read it back with `con.execute("PRAGMA foreign_keys").fetchone()[0]`; if `0`, emit `_log.warning("PRAGMA foreign_keys is OFF after SET — drift detected")`, throttled via a module-level boolean sentinel so the message appears at most once per session.
  - **Function docstring**: short docstring on `db_connect()` stating that the PRAGMA is the load-bearing FK-enforcement line for the entire app, must not be removed, and that anyone needing a SQLite connection MUST go through this function (no raw `sqlite3.connect(...)` in production code). Module-top docstring stays untouched (project convention is function-level docstrings).
  - Module-level `_log = logging.getLogger(__name__)` if not already present (mirror Phase 62 player.py pattern).
- **`musicstreamer/repo.py::sweep_orphans(con)` (new function)** — single new function. Two DELETE statements, in this order:
  1. `DELETE FROM station_streams WHERE station_id NOT IN (SELECT id FROM stations)` — captures rows whose parent station was hard-deleted outside the app.
  2. `DELETE FROM station_siblings WHERE a_id NOT IN (SELECT id FROM stations) OR b_id NOT IN (SELECT id FROM stations)` — single atomic statement, one log line, handles both FK columns symmetrically.
  - Each `con.execute(...)` returns a cursor; capture `cur.rowcount` per table.
  - If both rowcounts are 0: silent (no log line).
  - If any rowcount is > 0: emit `_log.info("sweep_orphans: station_streams=%d station_siblings=%d", n_streams, n_siblings)`.
  - `con.commit()` at the end. Returns None (caller doesn't need the counts; the log line is the surface).
- **`musicstreamer/__main__.py::_run_gui`** — one new call site, immediately after `db_init(con)`: `sweep_orphans(con)`. Same `con` object — no second connection open. Runs on every app start; idempotent.
- **Regression tests (new file: `tests/test_db_fk_invariants.py`)** — five tests:
  1. **`test_delete_station_cascades_station_streams`** — open in-memory db via `repo.db_connect()` shape (i.e. with PRAGMA), insert station + stream, call `Repo.delete_station(id)`, assert `station_streams` row count == 0. Locks the positive cascade invariant.
  2. **`test_delete_station_cascades_station_siblings_a_id`** — insert sibling pair (X, Y), delete X, assert sibling row gone (proves `a_id` cascade).
  3. **`test_delete_station_cascades_station_siblings_b_id`** — insert sibling pair (X, Y), delete Y, assert sibling row gone (proves `b_id` cascade — symmetry coverage).
  4. **`test_pragma_off_leaks_orphans_proving_pragma_is_load_bearing`** — open raw `sqlite3.connect(":memory:")` WITHOUT setting the PRAGMA, create a minimal stations + station_streams schema (matching the CASCADE clause), insert a row, delete the parent, assert the child row SURVIVES. Names the cause-effect explicitly: PRAGMA OFF → cascade does NOT fire.
  5. **`test_sweep_orphans_removes_orphan_streams_and_siblings`** — open db via `db_connect()`, manually `con.execute("PRAGMA foreign_keys = OFF")` (Mid-test), insert a station, insert a stream pointing at it, hard-DELETE the station via raw SQL (bypassing the now-OFF cascade), turn the PRAGMA back ON, call `sweep_orphans(con)`, assert orphan stream is gone. Covers the actual Synphaera-shaped failure mode.
- **Source-grep drift-guard test (new file: `tests/test_db_connect_is_sole_connection_factory.py`)** — walks `musicstreamer/**/*.py` (production tree only, excludes `tests/`) and asserts the only `sqlite3.connect(` callsite is inside `musicstreamer/repo.py`'s `db_connect` function. Shape mirrors `tests/test_packaging_spec.py` per project precedent (memory `feedback_gstreamer_mock_blind_spot.md`: "add source-level grep gates to ban legacy `playbin` 1.x signals"). Asserts BOTH:
  - Exactly one `sqlite3.connect(` reference in the production tree.
  - That reference lives in `musicstreamer/repo.py`.
- **Logger config (`musicstreamer/__main__.py::main`)** — add per-logger INFO escalation for `musicstreamer.repo` next to the existing `musicstreamer.player` and `musicstreamer.soma_import` lines. Global level stays WARN. Without this, the sweep_orphans INFO line never reaches the user's log (Phase 62 D-09 precedent).

**Out of scope:**

- **Adding `PRAGMA foreign_keys = ON` to `db_connect()`** — already there since commit `59fc516`. Anti-pattern listed in `.continue-here.md` ("Assume db_connect() is missing the PRAGMA without checking"). The phase is *locking* the existing line in, not adding it.
- **Sweeping `favorites`** — favorites has NO FK to stations; it uses `TEXT station_name` and intentionally persists track titles after a station delete (v1.3 FAVES-01..04 design). Sweeping would silently change documented behavior. Anti-pattern listed in `.continue-here.md` ("Sweep favorites as a 'soft orphan'").
- **`stations.provider_id` orphan handling** — declared `ON DELETE SET NULL`, not `CASCADE`. A dangling `provider_id` is the documented graceful-degrade path, not an orphan. Out of scope.
- **Gating `sweep_orphans()` by `PRAGMA user_version`** — rejected. Once the version bumps, future drift would leak silently forever. Run every app start; it's sub-millisecond when N=0. Anti-pattern listed in `.continue-here.md` ("Do not gate sweep_orphans() by user_version").
- **Settings flag for sweep** — rejected. Same reason as the user_version gate. The sweep is the safety net; it does not need a knob.
- **Generic `PRAGMA foreign_key_list(...)` introspection to auto-discover all FK child tables** — too clever. Only two tables matter (`station_streams`, `station_siblings`); hard-coding them keeps the function trivially auditable. If a future FK child table is added, the developer adds one more DELETE line — that's also the moment they'll write the matching regression test.
- **Allow-list annotation (`# noqa: db-connect-bypass`) for the source-grep gate** — rejected. Tests/ is already excluded by the gate scope; production code has zero legitimate reason to use raw `sqlite3.connect`.
- **Cross-process / cross-launcher scenarios** — out of scope. The phase concerns FK enforcement inside one MusicStreamer process; what an outside `sqlite3` shell does is the human's responsibility (and the sweep at next app start heals it anyway).
- **Phase 77 (test infrastructure stabilization) coordination** — Phase 80's two new test files use simple per-test temp-file dbs / `:memory:` connections; they do not interact with the FakePlayer / MPRIS / Qt-teardown issues Phase 77 is fixing. No coupling.

</domain>

<decisions>
## Implementation Decisions

### Orphan-sweep policy + location

- **D-01:** **Sweep action = delete + INFO-log per-table counts when N>0; silent on N=0.** Delete (not log-and-keep) because the whole point is to heal the dedup-by-URL re-import path that the Synphaera ghosts broke. INFO-only-when-interesting matches the project's established "log when something actually happened" idiom (Phase 50 recent-played refresh, Phase 62 cycle_close, sweep is just another instance).
- **D-02:** **Sweep lives in a separate `sweep_orphans(con)` function in `musicstreamer/repo.py`** — NOT inside `db_init()`. Rationale: `db_init()` is schema-only (idempotent CREATEs); folding sweep into it would conflate "make sure tables exist" with "delete possibly-real user data." Separate function = separate intent + independently testable. Called from `__main__._run_gui` immediately after `db_init(con)`, on the same connection.
- **D-03:** **Sweep runs every app start, unconditionally.** No user_version gate, no settings flag, no first-run-only marker. Sub-millisecond when N=0 (two NOT IN subqueries against tiny tables); the cost of being wrong about "when to stop running it" massively outweighs the cost of running it always.
- **D-04:** **N=0 is silent.** Only emit the INFO log line when at least one table had a positive rowcount. Keeps a clean steady-state log; the line appearing at all is a signal worth grepping for.

### Which tables to sweep

- **D-05:** **Sweep only the real FK-cascade child tables: `station_streams` and `station_siblings`.** These are the two tables with `FOREIGN KEY ... ON DELETE CASCADE` clauses against `stations(id)` in the existing schema (repo.py db_init body).
- **D-06:** **Favorites is excluded.** No FK; uses `TEXT station_name`. v1.3 FAVES-01..04 intentionally persists track titles after a station is deleted (so the user's listening history survives station turnover). Sweeping would silently change this behavior.
- **D-07:** **`station_siblings` swept via single DELETE handling both FK columns.** Statement: `DELETE FROM station_siblings WHERE a_id NOT IN (SELECT id FROM stations) OR b_id NOT IN (SELECT id FROM stations)`. One atomic statement, one rowcount, one log entry.
- **D-08:** **`stations.provider_id` orphans are out of scope.** Declared `ON DELETE SET NULL`, not `CASCADE`. A `provider_id` pointing at a deleted provider becomes NULL by design (graceful-degrade station rendering). Not an orphan.

### Drift-guard mechanism

- **D-09:** **Both runtime self-check AND source-grep test — defense in depth.** Two complementary failure modes need two complementary guards:
  - Runtime self-check catches "someone refactored `db_connect()` and dropped the PRAGMA line."
  - Source-grep test catches "someone added a new file that opens its own `sqlite3.connect(...)` and never touches `db_connect`."
  - Either guard alone has a blind spot the other covers. Project precedent for source-grep gates is documented in memory `feedback_gstreamer_mock_blind_spot.md`.
- **D-10:** **Runtime drift-guard logs at WARN if PRAGMA reads OFF after the SET.** Not ERROR (app survives without FK enforcement, just leaks orphans; ERROR overstates), not INFO (drift is genuinely surprising and deserves more than the steady-state sweep line). WARN matches the existing project idiom for "something is wrong but app survives."
- **D-11:** **Runtime drift-guard is throttled to once per session via a module-level boolean sentinel.** `db_connect()` is called many times per session (Repo methods open short-lived connections); without a sentinel, a persistent drift would flood logs with identical lines. First call checks-and-logs; subsequent calls skip the check entirely. Module-level `bool` is sufficient — no cross-process persistence.
- **D-12:** **Source-grep test scope = production tree only (allow tests/).** `tests/test_db_fk_invariants.py::test_pragma_off_leaks_orphans_proving_pragma_is_load_bearing` (the negative regression test, D-15) needs raw `sqlite3.connect(":memory:")` WITHOUT the PRAGMA — that IS the test. Banning tests/ would block the negative-proof test. Production code has zero legitimate reason to use raw `sqlite3.connect`.

### Regression test surface

- **D-13:** **Positive cascade test for `station_streams` is required.** Insert station + stream via `Repo.*`, call `Repo.delete_station(id)`, assert `station_streams` row count for that station == 0. Uses the production code path (`db_connect()` → PRAGMA set) end-to-end so the test names the actual invariant.
- **D-14:** **Symmetry coverage for `station_siblings` — TWO tests, one per FK column.** `test_delete_station_cascades_station_siblings_a_id` and `test_delete_station_cascades_station_siblings_b_id`. SQLite cascades both identically today; testing both means a future asymmetric-drift commit (e.g., one column flipped to `NO ACTION`) gets caught.
- **D-15:** **Negative PRAGMA-OFF test is required.** Open raw `sqlite3.connect(":memory:")`, create minimal stations + station_streams schema with the CASCADE clause, insert a row, delete the parent, assert the child SURVIVES. Locks the cause-effect into the test name (`test_pragma_off_leaks_orphans_proving_pragma_is_load_bearing`). Future maintainers reading the test file see exactly why the PRAGMA matters.
- **D-16:** **One `sweep_orphans` happy-path test** — uses the OFF→DELETE→ON sequence to manufacture an orphan inside the test, then calls `sweep_orphans(con)` and asserts the orphan is gone. Covers the actual Synphaera-shaped failure mode.
- **D-17:** **Docstring placement = function-level on `db_connect()` ONLY.** No module-top docstring. Matches the project's existing repo.py convention (all functions have docstrings; no module summary at top). Single source of truth, right next to the load-bearing line. The docstring explicitly states that the PRAGMA is the FK-enforcement mechanism and that anyone needing a SQLite connection MUST go through this function.

### Claude's Discretion

- **Module-level `_log` placement in `repo.py`** — if a logger is already declared, use it. If not, add `_log = logging.getLogger(__name__)` near the top of the module (mirror Phase 62 player.py D-NN convention). Planner picks placement.
- **Test fixtures** — `tests/test_db_fk_invariants.py` can either reuse the existing fresh_station/station fixtures from `conftest.py` (if they fit) or stand up its own minimal `fresh_db_with_pragma()` and `fresh_db_no_pragma()` fixtures. Planner decides based on existing fixture surface.
- **Source-grep test implementation** — either pure-Python `pathlib.Path().rglob("*.py")` + regex (`re.compile(r"sqlite3\.connect\(")`) or invoke `git grep -n` via subprocess. Recommendation: pure Python (no git dependency in test env). Planner picks.
- **Source-grep gate detail — whether to also flag `sqlite3.dbapi2.connect`** — the alternative spelling reaches the same C function. Recommendation: include it in the grep pattern (`re.compile(r"sqlite3(\.dbapi2)?\.connect\(")`). Belt-and-suspenders, two characters. Planner can defer if it adds friction.
- **Throttle sentinel scope** — module-level `_pragma_drift_logged: bool = False` in `repo.py` is the simplest shape. Planner picks the exact location and reset semantics for test isolation (e.g., a private `_reset_pragma_drift_sentinel_for_tests()` helper if any test needs to re-arm the warning).
- **Sweep log format detail** — `_log.info("sweep_orphans: station_streams=%d station_siblings=%d", ...)` is the working shape. Planner can flatten to two lines if that's more grep-friendly. Match Phase 62 cycle_close shape if in doubt.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements

- `.planning/ROADMAP.md` — Phase 80 entry. "Depends on: none (independent fix; can run any time after Phase 74)."
- `.planning/REQUIREMENTS.md` — BUG-10 row (the full requirement text covers items (a)-(d): regression test, drift-guard log, orphan-sweep migration, per-connection docstring).
- `.planning/PROJECT.md` §Key Decisions — DB-path / schema gotchas memory (`reference-musicstreamer-db-schema`): DB filename is `musicstreamer.sqlite3` (NOT `library.db`); `stations.provider_id` FK to `providers.id`.

### Closest existing patterns (READ FIRST — Phase 80 modifies these)

- **`musicstreamer/repo.py:17-21`** — `db_connect()` itself. The PRAGMA line is already there; Phase 80 adds the runtime drift-guard and docstring to this function (does NOT add the PRAGMA — anti-pattern in `.continue-here.md`).
- **`musicstreamer/repo.py:24-100ish`** — `db_init()` schema body. Phase 80 reads (not edits) the FK CASCADE clauses for `station_streams` and `station_siblings` to confirm sweep targets. Schema CREATEs in this file are the canonical source of truth for which tables have cascades.
- **`musicstreamer/__main__.py::_run_gui`** — the call site Phase 80 inserts `sweep_orphans(con)` into, immediately after `db_init(con)`. Same connection object.
- **`musicstreamer/__main__.py::main`** — the per-logger INFO escalation block. Phase 80 adds `musicstreamer.repo` to the list (mirror Phase 62 D-NN pattern that escalated `musicstreamer.player` to INFO without bumping the global level).

### Closest existing test patterns (mirror these for shape)

- **`tests/test_packaging_spec.py`** — project precedent for source-grep gate tests (per memory `feedback_gstreamer_mock_blind_spot.md`). Phase 80's `tests/test_db_connect_is_sole_connection_factory.py` mirrors this shape.
- **Existing `tests/test_repo*.py`** (planner identifies the closest one) — fixture shape and Repo-usage patterns for the positive cascade tests.

### Phase precedent for logger-introduction pattern

- **Phase 62 `musicstreamer/player.py`** — first module-level `_log = logging.getLogger(__name__)` introduction in this project + per-logger INFO escalation in `__main__.main`. Phase 80 mirrors both for `musicstreamer.repo`.

### Anti-patterns from this session

- **`.planning/phases/80-sqlite-foreign-key-enforcement-set-pragma-foreign-keys-on-pe/.continue-here.md`** — three advisory anti-patterns (do NOT add PRAGMA; do NOT sweep favorites; do NOT gate sweep by user_version). Planner reads this before drafting plans.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`musicstreamer/repo.py::db_connect()`** — already sets `PRAGMA foreign_keys = ON;` since commit `59fc516` (Phase 01-01). Verified this session via `git log -L 17,21:musicstreamer/repo.py`. Reuse: drift-guard adds a single read-back after the existing SET; docstring is appended to the same function.
- **`musicstreamer/repo.py::db_init()`** — existing FK CASCADE schema for `station_streams.station_id → stations(id)` and `station_siblings.a_id/b_id → stations(id)`. Reused as-is; Phase 80 reads but does not modify.
- **`musicstreamer/__main__.py::_run_gui`** — existing `db_init(con)` call. Single-line insertion site for `sweep_orphans(con)`.
- **`musicstreamer/__main__.py::main` per-logger config** — existing INFO escalations for `musicstreamer.player` (Phase 62) and `musicstreamer.soma_import`. Established precedent for adding one more line.

### Established Patterns

- **PRAGMA-set-in-factory pattern** — every SQLite connection used by the app is opened via `Repo.*` methods that internally call `db_connect()`. There are no other connection sites in production code (Phase 80's source-grep test enforces this).
- **Tiny-module + focused-function project convention** — `cookie_utils.py`, `url_helpers.py`, `subprocess_utils.py`, `yt_dlp_opts.py` (new in Phase 79). `sweep_orphans()` does NOT need its own module; it lives in `repo.py` alongside `db_connect()` / `db_init()` because they share the connection lifecycle.
- **Per-logger INFO escalation pattern (Phase 62 D-NN)** — keep global root logger at WARN, escalate specific module loggers to INFO so their lines reach the user log without flooding with third-party noise.
- **Source-grep drift-guard test pattern** — `tests/test_packaging_spec.py` precedent + memory `feedback_gstreamer_mock_blind_spot.md` ("pipeline mocks pass through any `pipeline.emit(...)` call; add source-level grep gates to ban legacy `playbin` 1.x signals"). Phase 80 applies the same shape to the `sqlite3.connect(` invariant.

### Integration Points

- `repo.py` runtime drift-guard: adds the read-back + WARN after the existing PRAGMA SET inside `db_connect()`. Module-level `_pragma_drift_logged: bool = False` sentinel governs throttle.
- `repo.py::sweep_orphans(con)`: new sibling function adjacent to `db_init()`. Two DELETE statements; one conditional INFO log.
- `__main__.py::_run_gui`: one new line `sweep_orphans(con)` immediately after `db_init(con)`.
- `__main__.py::main`: one new line escalating `musicstreamer.repo` logger to INFO.
- `tests/test_db_fk_invariants.py`: NEW file, five tests (positive cascade × 1, sibling symmetry × 2, negative PRAGMA-off × 1, sweep_orphans happy path × 1).
- `tests/test_db_connect_is_sole_connection_factory.py`: NEW file, source-grep drift-guard test, mirrors `tests/test_packaging_spec.py` shape.

</code_context>

<specifics>
## Specific Ideas

- **Naming**: `sweep_orphans(con)` over alternatives like `cleanup_orphans`, `vacuum_orphans`, `prune_dangling_rows`. "Sweep" is the right semantic ("look across all tables, remove what's stale") and pairs naturally with the per-table count log line.
- **Test naming**: `test_pragma_off_leaks_orphans_proving_pragma_is_load_bearing` — the verbose name IS the documentation. A future reader sees the test name in a CI failure and immediately understands why the PRAGMA matters.
- **Source-grep test naming**: `tests/test_db_connect_is_sole_connection_factory.py` — names the invariant ("db_connect is the only legal connection factory in production") in the filename.
- **Drift-guard WARN line wording**: short and grep-friendly — `"PRAGMA foreign_keys is OFF after SET — drift detected"` (the literal SET wording is intentional; a future reader sees both the symptom and the cause in one line).
- **Phase 74 motivation**: F-07-03 (`Synphaera` orphan ghosts) is the test name's spiritual ancestor. Plan 05 verification phase should re-run a SomaFM-style wipe-and-re-import to confirm dedup-by-URL works against the now-swept tables.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 80-sqlite-foreign-key-enforcement-set-pragma-foreign-keys-on-pe*
*Context gathered: 2026-05-17, resumed 2026-05-18*
