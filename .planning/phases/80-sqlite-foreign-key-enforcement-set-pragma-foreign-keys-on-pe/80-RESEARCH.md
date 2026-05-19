# Phase 80: SQLite foreign-key enforcement — Research

**Researched:** 2026-05-18
**Domain:** SQLite FK enforcement (production-tree hardening — single-file refactor in `musicstreamer/repo.py` + one-line wiring in `musicstreamer/__main__.py` + two new test files)
**Confidence:** HIGH (all claims verified against current repo source; no external library knowledge required)

## Summary

Phase 80 is overwhelmingly a **tightening** phase — `PRAGMA foreign_keys = ON;` is **already** set on every connection at `musicstreamer/repo.py:20` (verified inline this session). The Synphaera orphan ghosts (Phase 74 Plan 07 F-07-03) came from a manual `sqlite3`-shell `DELETE` that bypassed `db_connect()` entirely, not from a code bug. So the planner's job is to lock the existing invariant into regression tests + add a drift-guard against future regressions + sweep the historical orphans the manual cleanup left behind.

CONTEXT.md is exceptionally detailed (17 locked decisions D-01..D-17, exact function signatures, test names, file paths). This research is **NOT** a re-discussion; it surfaces the concrete code shape — line numbers, imports, fixture analogs, source-grep precedent — the planner needs to write tight one-line-per-action plans.

**Primary recommendation:** Plan should be 4-5 small task waves: (Wave 1) `repo.py` edits — module logger + sentinel + `sweep_orphans` + docstring + drift-guard; (Wave 2) `__main__.py` edits — sweep call site + per-logger INFO escalation; (Wave 3) new `tests/test_db_fk_invariants.py` with 5 tests; (Wave 4) new `tests/test_db_connect_is_sole_connection_factory.py` source-grep gate. All tests use existing patterns from `tests/test_repo.py` and `tests/test_packaging_spec.py` — no new fixture infrastructure required.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Orphan-sweep policy + location:**
- **D-01:** Sweep action = delete + INFO-log per-table counts when N>0; silent on N=0.
- **D-02:** Sweep lives in a separate `sweep_orphans(con)` function in `musicstreamer/repo.py` — NOT inside `db_init()`. Called from `__main__._run_gui` immediately after `db_init(con)`, on the same connection.
- **D-03:** Sweep runs every app start, unconditionally. No user_version gate, no settings flag, no first-run-only marker.
- **D-04:** N=0 is silent. Only emit the INFO log line when at least one table had a positive rowcount.

**Which tables to sweep:**
- **D-05:** Sweep only the real FK-cascade child tables: `station_streams` and `station_siblings`.
- **D-06:** Favorites is excluded. No FK; uses `TEXT station_name`. v1.3 FAVES-01..04 intentionally persists track titles after a station is deleted.
- **D-07:** `station_siblings` swept via single DELETE handling both FK columns: `DELETE FROM station_siblings WHERE a_id NOT IN (SELECT id FROM stations) OR b_id NOT IN (SELECT id FROM stations)`.
- **D-08:** `stations.provider_id` orphans are out of scope (declared `ON DELETE SET NULL`, not `CASCADE`).

**Drift-guard mechanism:**
- **D-09:** Both runtime self-check AND source-grep test — defense in depth.
- **D-10:** Runtime drift-guard logs at WARN if PRAGMA reads OFF after the SET.
- **D-11:** Runtime drift-guard is throttled to once per session via a module-level boolean sentinel.
- **D-12:** Source-grep test scope = production tree only (allow tests/).

**Regression test surface:**
- **D-13:** Positive cascade test for `station_streams` is required.
- **D-14:** Symmetry coverage for `station_siblings` — TWO tests, one per FK column (`test_delete_station_cascades_station_siblings_a_id` and `test_delete_station_cascades_station_siblings_b_id`).
- **D-15:** Negative PRAGMA-OFF test is required (`test_pragma_off_leaks_orphans_proving_pragma_is_load_bearing`).
- **D-16:** One `sweep_orphans` happy-path test using OFF→DELETE→ON sequence to manufacture an orphan.
- **D-17:** Docstring placement = function-level on `db_connect()` ONLY (no module-top docstring).

### Claude's Discretion

- **Module-level `_log` placement in `repo.py`** — if a logger is already declared, use it. If not, add `_log = logging.getLogger(__name__)` near the top of the module.
- **Test fixtures** — `tests/test_db_fk_invariants.py` can either reuse existing fresh_station/station fixtures from `tests/test_repo.py` (if they fit) or stand up its own minimal `fresh_db_with_pragma()` / `fresh_db_no_pragma()` fixtures.
- **Source-grep test implementation** — pure-Python `pathlib.Path().rglob("*.py")` + regex vs. `git grep -n` via subprocess. Recommendation: pure Python.
- **Source-grep gate detail — whether to also flag `sqlite3.dbapi2.connect`** — Recommendation: include in grep pattern.
- **Throttle sentinel scope** — module-level `_pragma_drift_logged: bool = False` is the simplest shape; planner picks placement + reset semantics for test isolation.
- **Sweep log format detail** — `_log.info("sweep_orphans: station_streams=%d station_siblings=%d", ...)` is the working shape.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BUG-10 | `PRAGMA foreign_keys = ON` per connection + cascade regression test + drift-guard INFO log + orphan-sweep migration + per-connection requirement documented in repo.py docstring | (a) regression test: verified delete_station cascade test already exists at `tests/test_repo.py:584-594` (extend pattern); (b) drift-guard log: `_log` introduction mirrors Phase 62 `musicstreamer/player.py` precedent (per CONTEXT canonical_refs); (c) orphan-sweep migration: schema verified — `station_streams` cascade at `repo.py:72`, `station_siblings` cascade at `repo.py:78-79`; (d) docstring: `db_connect()` is the only production `sqlite3.connect(` callsite — verified via grep (`musicstreamer/repo.py:18` is the unique production hit). |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Per-connection PRAGMA enforcement | Database / Storage | — | Connection-factory responsibility; lives in `repo.py::db_connect`. |
| Orphan sweep on app start | Database / Storage | App entry (call site) | The DELETE logic owns the schema knowledge (which tables, which FK columns); `__main__._run_gui` only triggers it. |
| Runtime drift-guard log | Database / Storage | — | Read-back happens inside `db_connect` immediately after the SET — same tier as the SET itself. |
| Source-grep gate (sole-factory invariant) | Test infrastructure | — | Static analysis lives in the test tree, not production. Mirrors `tests/test_packaging_spec.py` precedent. |
| Per-logger INFO escalation | App entry (`__main__.main`) | — | Project precedent: all per-logger escalations live in `main()` (Phase 62 player, Phase 79 yt_import). |

## Standard Stack

Phase 80 introduces **zero new dependencies**. All work uses the existing standard library:

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `sqlite3` | stdlib | DB connection + PRAGMA + executescript | Already the project's DB layer; `db_connect()` returns `sqlite3.Connection`. |
| `logging` | stdlib | Module logger + WARN/INFO emission | Phase 62 `musicstreamer.player`, Phase 79 `musicstreamer.yt_import` precedent. |
| `pathlib` | stdlib | Source-tree walk for grep gate | Phase 65 `tests/test_packaging_spec.py` uses this exact pattern (`Path(__file__).resolve().parent.parent`). |
| `re` | stdlib | Regex for `sqlite3.connect(` match in grep gate | Standard idiom for source-grep tests in this codebase. |

**No `pip install` required.** No `npm view` / `pip index versions` calls relevant. Skipping Package Legitimacy Audit by design (zero packages installed).

## Existing Code Shape (concrete excerpts)

### `musicstreamer/repo.py` (verified lines 1-21)

```python
import sqlite3
from typing import Optional, List

from musicstreamer.models import Station, Provider, Favorite, StationStream
from musicstreamer import paths


# Phase 73 WR-03: valid values for the `cover_art_source` column. ...
VALID_COVER_ART_SOURCES: frozenset[str] = frozenset({"auto", "itunes_only", "mb_only"})


def db_connect() -> sqlite3.Connection:
    con = sqlite3.connect(paths.db_path())
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    return con
```

**Key findings:**
- **No module-level `_log` exists yet.** Planner must add `import logging` to the import block and `_log = logging.getLogger(__name__)` after the imports (recommended placement: right before line 8's `VALID_COVER_ART_SOURCES` block, or just below it — both are valid; the Phase 62 `player.py` precedent places it immediately after the module's top-of-file imports).
- **No module-top docstring.** Matches D-17 — keep it that way; place the docstring on `db_connect()` itself.
- **PRAGMA already at line 20** — confirmed. Phase 80 must NOT add a duplicate.
- **`db_connect()` has no docstring currently** — fresh slate for the D-17 docstring.

### `musicstreamer/repo.py::db_init` FK cascade schema (verified lines 60-82)

```python
CREATE TABLE IF NOT EXISTS station_streams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id INTEGER NOT NULL,
    url TEXT NOT NULL DEFAULT '',
    ...
    FOREIGN KEY(station_id) REFERENCES stations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS station_siblings (
  a_id INTEGER NOT NULL,
  b_id INTEGER NOT NULL,
  FOREIGN KEY(a_id) REFERENCES stations(id) ON DELETE CASCADE,
  FOREIGN KEY(b_id) REFERENCES stations(id) ON DELETE CASCADE,
  UNIQUE(a_id, b_id),
  CHECK(a_id < b_id)
);
```

**Sanity-check confirmed:** D-05 (sweep `station_streams` and `station_siblings`) and D-07 (sweep `station_siblings` symmetrically on `a_id` AND `b_id`) match the real schema exactly. The `CHECK(a_id < b_id)` constraint on `station_siblings` is **not relevant to the sweep** — the sweep DELETEs orphans, not inserts new rows.

### `musicstreamer/__main__.py::_run_gui` insertion site (verified lines 194-213)

```python
from musicstreamer.repo import Repo, db_connect, db_init

app = QApplication(argv)
app.setApplicationName("MusicStreamer")
...
# Phase 66 / THEME-01: theme palette FIRST, before MainWindow construction.
# ... (long comment block)
con = db_connect()
db_init(con)
repo = Repo(con)
from musicstreamer import theme
theme.apply_theme_palette(app, repo)
```

**Insertion point for `sweep_orphans(con)`:** Immediately after `db_init(con)` (line 209), BEFORE `repo = Repo(con)` (line 210). Same connection object. Single line: `sweep_orphans(con)`.

**Import update required:** Line 194 must add `sweep_orphans` to the `from musicstreamer.repo import ...` import — new shape: `from musicstreamer.repo import Repo, db_connect, db_init, sweep_orphans`.

### `musicstreamer/__main__.py::main` per-logger INFO escalation block (verified lines 241-250)

```python
def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING)
    # Phase 62 / BUG-09 / Pitfall 5: per-logger INFO level for musicstreamer.player ...
    logging.getLogger("musicstreamer.player").setLevel(logging.INFO)
    logging.getLogger("musicstreamer.soma_import").setLevel(logging.INFO)
    # Phase 79 / BUG-11: surface scan_playlist node_path INFO line at default
    # verbosity (consumed by Plan 79-03's yt_import.scan_playlist INFO log).
    logging.getLogger("musicstreamer.yt_import").setLevel(logging.INFO)
```

**Insertion point for Phase 80:** Add one line `logging.getLogger("musicstreamer.repo").setLevel(logging.INFO)` after the existing escalations (immediately after line 250). Mirror the Phase-X-rationale comment style.

### `tests/conftest.py` shape (verified lines 1-100)

- `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` runs at module import. **Phase 80's new tests do not need Qt** — pure stdlib `sqlite3` + `logging`. The conftest's `_stub_bus_bridge` autouse fixture imports `musicstreamer.player` (line 26-27), which is fine but irrelevant.
- **No DB-specific fixtures** in `tests/conftest.py`. Per-file `repo` fixtures are the project pattern (see `tests/test_repo.py:7-13` below).

### `tests/test_repo.py` `repo` fixture — closest analog (verified lines 7-13)

```python
@pytest.fixture
def repo(tmp_path):
    con = sqlite3.connect(str(tmp_path / "test.db"))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    db_init(con)
    return Repo(con)
```

**Critical observation:** This fixture does **NOT** call `db_connect()` — it open-codes the connection + PRAGMA + row_factory + db_init. That works for ordinary tests, but for Phase 80's D-13/D-14/D-16 tests that want to exercise the **production code path end-to-end**, the fixture should call `db_connect()` (monkeypatching `paths.db_path()` to return `str(tmp_path / "test.db")`). Otherwise the tests don't actually exercise `db_connect()`'s drift-guard — they only exercise the underlying sqlite3 PRAGMA, and a drift in `db_connect()` would not be caught.

**Two viable fixture strategies for `tests/test_db_fk_invariants.py`:**

1. **Strategy A (production path, recommended for D-13/D-14/D-16):** monkeypatch `musicstreamer.paths.db_path` to return a tmp_path string, then call `db_connect()`. Catches drift in the whole factory function, not just the PRAGMA line.
2. **Strategy B (raw sqlite3, required for D-15):** open `sqlite3.connect(":memory:")` directly, then `executescript` a minimal stations + station_streams schema with the CASCADE clause but explicitly skip the PRAGMA. This IS the test — the negative-proof path.

Planner should use Strategy A for cascade tests (D-13/D-14) and the sweep test (D-16), and Strategy B for the negative PRAGMA-off test (D-15).

### Closest existing cascade test (verified `tests/test_repo.py:584-594`)

```python
def test_cascade_delete(repo):
    """Deleting a station also deletes its station_streams rows."""
    sid = repo.insert_station("Test FM", "http://test.fm/stream", "", "")
    streams_before = repo.list_streams(sid)
    assert len(streams_before) == 1
    repo.delete_station(sid)
    # station is gone, verify streams are gone too via direct query
    rows = repo.con.execute(
        "SELECT * FROM station_streams WHERE station_id=?", (sid,)
    ).fetchall()
    assert len(rows) == 0
```

**This is the direct ancestor of D-13's `test_delete_station_cascades_station_streams`.** The new test is essentially this one renamed + relocated to `tests/test_db_fk_invariants.py` with a more explicit name. Planner should NOT delete the existing `test_cascade_delete` — leaving both is fine (the new one names the invariant more loudly; the old one is a passing regression already). Alternative: rename `test_cascade_delete` to the new name in-place and move it to the new file. Planner decides.

### Closest existing sibling cascade test (verified `tests/test_station_siblings.py:102-113`)

```python
def test_cascade_on_station_delete(repo):
    """D-08: ON DELETE CASCADE removes link rows when partner deleted."""
    repo.con.execute("INSERT INTO stations(id, name, tags) VALUES (1, 'A', '')")
    repo.con.execute("INSERT INTO stations(id, name, tags) VALUES (2, 'B', '')")
    repo.con.execute("INSERT INTO station_siblings(a_id, b_id) VALUES (1, 2)")
    repo.con.commit()
    repo.con.execute("DELETE FROM stations WHERE id = 2")
    repo.con.commit()
    count = repo.con.execute(
        "SELECT COUNT(*) AS c FROM station_siblings"
    ).fetchone()["c"]
    assert count == 0
```

**This covers ONE of the two sibling-FK directions** (deletes station id=2, which is `b_id`). D-14 requires both — `_a_id` (delete the lower-id station) AND `_b_id` (delete the higher-id station). The above existing test covers the `_b_id` case. Planner can either:
- (a) move + rename it to `test_delete_station_cascades_station_siblings_b_id` and add a sibling `_a_id` variant in the new file, OR
- (b) leave it in place and add both new tests in the new file.

Recommendation: option (b). Two cheap extra tests with clear invariant names — the duplication cost is near-zero and keeps Phase 80's new test file self-contained.

### `tests/test_packaging_spec.py` source-grep gate precedent (verified lines 1-50, 158-305)

The shape Phase 80's `tests/test_db_connect_is_sole_connection_factory.py` mirrors:

```python
from pathlib import Path
import pytest

_SPEC = (
    Path(__file__).resolve().parent.parent
    / "packaging" / "windows" / "MusicStreamer.spec"
)

@pytest.fixture(scope="module")
def spec_source() -> str:
    assert _SPEC.is_file(), f"expected MusicStreamer.spec at {_SPEC}"
    return _SPEC.read_text(encoding="utf-8")

def test_spec_imports_copy_metadata(spec_source: str) -> None:
    assert "copy_metadata" in spec_source, (...)
```

**Adapted shape for Phase 80:** walk `musicstreamer/**/*.py` via `rglob`, regex-match `re.compile(r"sqlite3(\.dbapi2)?\.connect\(")` per file, assert exactly one hit and it lives in `musicstreamer/repo.py`. The test file uses a module-scoped fixture returning a `dict[Path, list[int]]` of {file → matching line numbers} for grep-friendly failure messages.

## Verified `sqlite3.connect(` callsite inventory

Production tree (`musicstreamer/`):

| File | Line | Context | Status |
|------|------|---------|--------|
| `musicstreamer/repo.py` | 18 | `db_connect()` body | LEGAL — the sole-factory itself |

**Total production callsites: 1.** The source-grep gate asserts this exactly.

Test tree (`tests/`) — for awareness, the gate does NOT touch this tree (D-12):

| File | Line | Purpose |
|------|------|---------|
| `tests/test_repo.py` | 9, 19, 621 | Per-test fixtures + bare-con helper |
| `tests/test_station_siblings.py` | 68, 94 | Per-test fixtures |
| `tests/test_settings_export.py` | 31, 619 | Per-test fixtures + export inspector |
| `tests/test_theme.py` | 135 | Per-test fixture |
| `tests/test_main_window_integration.py` | 1344 | In-memory test setup |
| `tests/test_main_window_soma.py` | 303 | `lambda: sqlite3.connect(":memory:")` (monkeypatch shape) |

The above are **all legitimate**. D-12's "production tree only" scope automatically excludes them.

## Architecture Patterns

### Pattern 1: Module-level logger introduction (Phase 62 precedent)

**What:** Add `import logging` to the module's import block; declare `_log = logging.getLogger(__name__)` near the top.

**When to use:** Whenever a module needs to emit log lines (info/warning/error). Project convention is `_log` (single underscore, lowercase) — NOT `LOG` or `logger`.

**Example (target shape after Phase 80):**

```python
# musicstreamer/repo.py — top of file after Phase 80
import logging
import sqlite3
from typing import Optional, List

from musicstreamer.models import Station, Provider, Favorite, StationStream
from musicstreamer import paths

_log = logging.getLogger(__name__)

# Phase 80: module-level sentinel for drift-guard one-shot WARN log.
# Reset to False by tests via _reset_pragma_drift_sentinel_for_tests() if needed.
_pragma_drift_logged: bool = False
```

### Pattern 2: Per-logger INFO escalation (Phase 62 / Phase 79 precedent)

**What:** `__main__.main()` keeps the global root logger at WARN, then escalates specific module loggers to INFO so their lines reach stderr without the user seeing chatter from third-party loggers (Qt, gi, etc.).

**When to use:** Any module that emits an INFO line the user is meant to see at default verbosity.

**Example (target shape after Phase 80):**

```python
logging.getLogger("musicstreamer.player").setLevel(logging.INFO)
logging.getLogger("musicstreamer.soma_import").setLevel(logging.INFO)
logging.getLogger("musicstreamer.yt_import").setLevel(logging.INFO)
# Phase 80 / BUG-10: surface sweep_orphans INFO line + PRAGMA drift WARN.
logging.getLogger("musicstreamer.repo").setLevel(logging.INFO)
```

### Pattern 3: Source-grep drift-guard test (Phase 65 packaging spec precedent)

**What:** A pytest test that reads source files as text and asserts substring presence/absence. Catches drift in source-level invariants without requiring runtime execution of the asserted code.

**When to use:** Any invariant that depends on source-text presence/absence (e.g., "this function must call X", "this module must not import Y"). Phase 80's grep gate fits exactly: "there must be exactly one `sqlite3.connect(` callsite in production code, and it must live in `musicstreamer/repo.py`."

### Anti-Patterns to Avoid

- **Adding `PRAGMA foreign_keys = ON` to `db_connect()` again.** It's already at line 20. A duplicate SET is a code smell that signals to a future reader the original may have been removed.
- **Sweeping `favorites`.** No FK; persists track titles by design (FAVES-01..04). Sweeping silently changes documented behavior.
- **Gating `sweep_orphans()` by `PRAGMA user_version`.** Once the version bumps, future drift would leak silently forever.
- **Folding `sweep_orphans()` into `db_init()`.** Conflates schema idempotency (CREATEs) with data mutation (DELETEs). Keep separate.
- **`Write-Error`-style logging that escalates to a terminating error** is a PowerShell concern from Phase 65; in Python, `_log.warning(...)` does NOT raise — no analogous trap. (Listed only to clarify the scope of the project's drift-guard discipline.)
- **Generic `PRAGMA foreign_key_list(...)` introspection** to auto-discover child tables. Only two tables matter; hard-coding them keeps the function trivially auditable.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| FK enforcement | Application-level cascade walking in Python | SQLite's native `ON DELETE CASCADE` + the PRAGMA | The schema already declares cascades; the engine handles them when the PRAGMA is ON. Python-level walking would silently diverge from the schema. |
| Orphan-detection via introspection | `con.execute("PRAGMA foreign_key_list(...)")` + dynamic SQL | Two hard-coded DELETE statements | Only two tables matter; the introspection cost is real (per CONTEXT D-N "too clever"), the hard-coded shape is auditable in one screen of code. |
| One-shot WARN log throttle | `set` of seen messages + check-each-call | Module-level `bool` sentinel | Single boolean, single check. Tests can flip it back to False via a small helper. |
| Connection-factory invariant enforcement | Runtime decorator pattern + registry | Pure source-grep test | Static analysis catches the structural invariant at zero runtime cost. The runtime drift-guard is the complementary safeguard for SET-then-mutated cases. |

## Common Pitfalls

### Pitfall 1: Fixture that bypasses `db_connect()` won't catch drift in the factory itself

**What goes wrong:** A test fixture that open-codes `sqlite3.connect(...) + PRAGMA + db_init` (like the existing `tests/test_repo.py:7-13` `repo` fixture) does NOT exercise `db_connect()`. If a future commit removes the PRAGMA SET from `db_connect()`, the fixture continues to pass because the fixture sets the PRAGMA itself.

**Why it happens:** The fixture pattern was established before there was a drift-guard requirement. It was correct for testing `Repo` methods (which only depend on the connection's behavior, not the factory's source).

**How to avoid:** For Phase 80's D-13/D-14/D-16 tests specifically, the fixture must call `musicstreamer.repo.db_connect()` directly (with `paths.db_path` monkeypatched to a tmp_path string). This makes the drift surface the entire `db_connect()` function, not just the PRAGMA line.

**Warning signs:** Tests pass locally but a manual `git revert` of the PRAGMA line at `repo.py:20` doesn't cause a single test failure. If that's the case, the fixture is the wrong shape.

### Pitfall 2: `paths.db_path()` is read at call time, not import time

**What goes wrong:** Naive monkeypatching of `musicstreamer.paths.db_path` AFTER `db_connect()` has been called won't help; subsequent calls will use the new value, but a connection already opened against the production DB persists.

**Why it happens:** `db_connect()` calls `paths.db_path()` inside the function body (line 18), not at module import.

**How to avoid:** Monkeypatch BEFORE calling `db_connect()` in the test. `monkeypatch.setattr("musicstreamer.paths.db_path", lambda: str(tmp_path / "test.db"))` set inside the fixture (before the first `db_connect()` call) is the correct shape.

**Warning signs:** Test creates a `~/.local/share/musicstreamer/musicstreamer.sqlite3` file or stomps on the user's real DB during a test run. If a developer reports their station list got wiped, this pitfall fired.

### Pitfall 3: `_pragma_drift_logged` sentinel leaks across tests

**What goes wrong:** The sentinel is a module-level boolean. Once flipped to True by the negative test (D-15), subsequent tests in the same pytest session will skip the drift-guard check, masking a real drift if a later test triggers one.

**Why it happens:** Python module state is process-scoped. pytest reuses the imported module across all tests in the run.

**How to avoid:** Add a tiny test-only helper `_reset_pragma_drift_sentinel_for_tests()` in `repo.py` that sets `_pragma_drift_logged = False`. Call it from a pytest fixture (autouse=True with function scope, scoped to `tests/test_db_fk_invariants.py` only). Alternative: name the helper with a `_for_tests` suffix so it's grep-discoverable as test-only API.

**Warning signs:** Test passes alone but fails when the test file is run twice in a single session, or fails when other test files run before it.

### Pitfall 4: `delete_station` short-circuit when station already gone

**What goes wrong:** `Repo.delete_station(id)` (verified `repo.py:385-387`) is a single `DELETE ... WHERE id = ?`. If the row doesn't exist, the DELETE is a no-op. A test that asserts cascade firing must assert on the CHILD row count, not on the DELETE's rowcount.

**Why it happens:** SQLite cascade behavior fires on the parent DELETE; the child DELETEs are atomic with it. If the parent row didn't exist, no cascade runs.

**How to avoid:** D-13/D-14 tests should: (a) INSERT the station, (b) verify the child row exists pre-DELETE, (c) DELETE the parent, (d) assert the child row count is now 0. The existing `test_cascade_delete` at `tests/test_repo.py:584-594` already follows this shape — mirror it exactly.

### Pitfall 5: `__main__._run_gui` is hard to unit-test directly

**What goes wrong:** A test that wants to assert "`_run_gui` calls `sweep_orphans(con)` immediately after `db_init(con)`" runs head-first into the QApplication construction at line 196.

**Why it happens:** `_run_gui` is a top-level integration function; it constructs QApplication, MainWindow, Player, etc.

**How to avoid:** This phase does NOT need an integration test for the call site. The Phase 65 precedent (`tests/test_main_run_gui_ordering.py` per CONTEXT canonical_refs) is `read_text` + substring-assertion against `__main__.py` source — verify the literal `sweep_orphans(con)` substring appears AFTER the literal `db_init(con)` substring within `_run_gui`'s body. Planner can include this as a sixth source-grep test in `tests/test_db_connect_is_sole_connection_factory.py` (or a separate file) if a call-site drift-guard is desired. CONTEXT does not require this — it's a Claude's-discretion add.

### Pitfall 6: SQLite PRAGMA read-back returns int, not bool

**What goes wrong:** `con.execute("PRAGMA foreign_keys").fetchone()[0]` returns `1` or `0` (int), not `True`/`False`. A naive `if not result:` works correctly (0 is falsy), but `if result is False:` does NOT.

**Why it happens:** SQLite PRAGMA returns SQL integers, mapped to Python int.

**How to avoid:** Use truthy comparison: `if con.execute("PRAGMA foreign_keys").fetchone()[0] == 0:` or `if not con.execute(...).fetchone()[0]:`. Both correct. Avoid `is False` / `is True`.

### Pitfall 7: PRAGMA value with `row_factory = sqlite3.Row` returns Row, not tuple

**What goes wrong:** After `con.row_factory = sqlite3.Row` (set at line 19), `fetchone()` returns a `sqlite3.Row` object, not a tuple. Indexing by `[0]` still works on Row objects, so the recommended read-back pattern `con.execute("PRAGMA foreign_keys").fetchone()[0]` is correct as-is.

**Why this is worth flagging:** A reader unfamiliar with sqlite3.Row's indexing semantics might second-guess the pattern. The pattern is fine — Row supports `__getitem__(int)`.

## Code Examples

Verified patterns the planner can lift verbatim.

### `db_connect()` — target shape after Phase 80

```python
# Source: Phase 80 CONTEXT D-10/D-11/D-17 + Phase 62 player.py logger precedent
def db_connect() -> sqlite3.Connection:
    """Return a SQLite connection with foreign-key enforcement enabled.

    The ``PRAGMA foreign_keys = ON;`` line below is load-bearing: every
    ON DELETE CASCADE in db_init()'s schema (station_streams.station_id,
    station_siblings.a_id / b_id) only fires when this PRAGMA is set on
    the connection that issues the parent DELETE. SQLite defaults the
    PRAGMA to OFF per connection — so removing this line silently leaks
    orphan rows on every station deletion (BUG-10, Phase 74 F-07-03).

    Anyone needing a SQLite connection MUST go through this function;
    a source-grep regression test asserts no other call site of
    sqlite3.connect(...) exists in production code
    (tests/test_db_connect_is_sole_connection_factory.py).
    """
    global _pragma_drift_logged
    con = sqlite3.connect(paths.db_path())
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    if not _pragma_drift_logged:
        if con.execute("PRAGMA foreign_keys").fetchone()[0] == 0:
            _log.warning(
                "PRAGMA foreign_keys is OFF after SET — drift detected"
            )
        _pragma_drift_logged = True
    return con
```

### `sweep_orphans(con)` — target shape

```python
# Source: Phase 80 CONTEXT D-01/D-02/D-04/D-05/D-07
def sweep_orphans(con: sqlite3.Connection) -> None:
    """Delete orphan rows in FK-child tables and log per-table counts when N>0.

    Heals orphan rows left by manual sqlite3-shell DELETEs that bypassed
    db_connect()'s PRAGMA (Phase 74 F-07-03 Synphaera ghosts). Runs every
    app start; sub-millisecond when N=0; silent on N=0 (D-04).

    Covers the two FK-cascade child tables (D-05): station_streams (cascade
    on stations.id) and station_siblings (cascade on stations.id via both
    a_id and b_id columns, swept symmetrically per D-07).

    favorites is intentionally excluded (D-06 — no FK, persists by design).
    stations.provider_id is out of scope (D-08 — ON DELETE SET NULL).
    """
    cur1 = con.execute(
        "DELETE FROM station_streams WHERE station_id NOT IN "
        "(SELECT id FROM stations)"
    )
    cur2 = con.execute(
        "DELETE FROM station_siblings WHERE a_id NOT IN "
        "(SELECT id FROM stations) OR b_id NOT IN (SELECT id FROM stations)"
    )
    if cur1.rowcount > 0 or cur2.rowcount > 0:
        _log.info(
            "sweep_orphans: station_streams=%d station_siblings=%d",
            cur1.rowcount, cur2.rowcount,
        )
    con.commit()
```

### Negative PRAGMA-off test — target shape (D-15)

```python
# Source: Phase 80 CONTEXT D-15
def test_pragma_off_leaks_orphans_proving_pragma_is_load_bearing():
    """Without PRAGMA foreign_keys = ON, ON DELETE CASCADE does NOT fire.

    This test exists to lock the cause-effect into the test name. If it
    starts failing (i.e. the cascade DOES fire without the PRAGMA), then
    either SQLite's default changed or this test's setup is wrong — either
    way, a future maintainer needs to understand why db_connect()'s PRAGMA
    line at musicstreamer/repo.py:20 is load-bearing before changing it.
    """
    con = sqlite3.connect(":memory:")
    # NOTE: deliberately NOT setting PRAGMA foreign_keys = ON.
    con.executescript("""
        CREATE TABLE stations (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE station_streams (
            id INTEGER PRIMARY KEY,
            station_id INTEGER NOT NULL,
            FOREIGN KEY(station_id) REFERENCES stations(id) ON DELETE CASCADE
        );
    """)
    con.execute("INSERT INTO stations(id, name) VALUES (1, 'X')")
    con.execute("INSERT INTO station_streams(id, station_id) VALUES (1, 1)")
    con.commit()
    con.execute("DELETE FROM stations WHERE id = 1")
    con.commit()
    rows = con.execute("SELECT COUNT(*) FROM station_streams").fetchone()[0]
    assert rows == 1, (
        "Expected orphan to survive (cascade does NOT fire with PRAGMA OFF). "
        "If this assertion fails, SQLite's default cascade behavior changed "
        "or this test set up the schema differently than db_init() does."
    )
```

### Source-grep gate — target shape

```python
# Source: tests/test_packaging_spec.py shape (Phase 65) + Phase 80 D-12
import re
from pathlib import Path
import pytest

_MUSICSTREAMER_PKG = Path(__file__).resolve().parent.parent / "musicstreamer"
_PATTERN = re.compile(r"sqlite3(\.dbapi2)?\.connect\(")

@pytest.fixture(scope="module")
def production_callsites() -> dict[Path, list[int]]:
    hits: dict[Path, list[int]] = {}
    for py_file in _MUSICSTREAMER_PKG.rglob("*.py"):
        lines = py_file.read_text(encoding="utf-8").splitlines()
        matched = [i + 1 for i, line in enumerate(lines) if _PATTERN.search(line)]
        if matched:
            hits[py_file] = matched
    return hits

def test_only_one_sqlite_connect_callsite_in_production(production_callsites):
    """Phase 80 / BUG-10 D-12: production code has exactly one
    sqlite3.connect(...) callsite, and it lives in db_connect()."""
    total = sum(len(v) for v in production_callsites.values())
    assert total == 1, (
        f"Expected exactly one sqlite3.connect(...) callsite in "
        f"musicstreamer/; found {total}: "
        f"{ {str(k): v for k, v in production_callsites.items()} }. "
        f"All production connections MUST go through db_connect() so the "
        f"PRAGMA foreign_keys = ON line at repo.py:20 is guaranteed."
    )

def test_sole_sqlite_connect_callsite_lives_in_repo_py(production_callsites):
    """The single legal callsite is musicstreamer/repo.py."""
    files = list(production_callsites.keys())
    assert len(files) == 1
    assert files[0].name == "repo.py", (
        f"Expected the sole sqlite3.connect(...) callsite to live in "
        f"musicstreamer/repo.py (inside db_connect); found it in "
        f"{files[0]}. Move the callsite into db_connect() or refactor it "
        f"to call db_connect() instead."
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Implicit reliance on PRAGMA being set at unknown call sites | Per-connection PRAGMA-in-factory + source-grep gate forbidding bypasses | Phase 80 | Drift becomes a CI-failing test, not a silent prod bug. |
| Per-test fixtures that open-code `sqlite3.connect(...) + PRAGMA` | Phase 80's new tests use `db_connect()` directly (via `paths.db_path` monkeypatch) | Phase 80 | New tests exercise the factory function, catching drift in the factory itself. Old fixtures stay as-is — they test `Repo`, not `db_connect`. |

**Deprecated/outdated:** Nothing. Phase 80 is additive.

## Runtime State Inventory

**N/A — not a rename/refactor/migration phase.** Phase 80 is additive (new function, new tests, new docstring, new log line) plus three small edits to existing code (drift-guard read-back inside `db_connect`, `sweep_orphans` call in `_run_gui`, per-logger INFO escalation in `main`). There are no stored strings being renamed and no external services touched.

## Environment Availability

**N/A — phase has no external dependencies.** All work uses Python stdlib (`sqlite3`, `logging`, `pathlib`, `re`) already imported elsewhere in the codebase.

## Validation Architecture

Nyquist validation is enabled (`.planning/config.json` `nyquist_validation: true`). Below is the test surface VALIDATION.md will lock in.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x (via `uv run pytest`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (project default) |
| Quick run command | `uv run pytest tests/test_db_fk_invariants.py tests/test_db_connect_is_sole_connection_factory.py -x` |
| Full suite command | `uv run pytest tests/` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BUG-10(a) | DELETE station cascades to station_streams | unit | `uv run pytest tests/test_db_fk_invariants.py::test_delete_station_cascades_station_streams -x` | ❌ Wave 0 |
| BUG-10(a) | DELETE station cascades to station_siblings (a_id direction) | unit | `uv run pytest tests/test_db_fk_invariants.py::test_delete_station_cascades_station_siblings_a_id -x` | ❌ Wave 0 |
| BUG-10(a) | DELETE station cascades to station_siblings (b_id direction) | unit | `uv run pytest tests/test_db_fk_invariants.py::test_delete_station_cascades_station_siblings_b_id -x` | ❌ Wave 0 |
| BUG-10(a) | Negative: PRAGMA OFF leaks orphans | unit | `uv run pytest tests/test_db_fk_invariants.py::test_pragma_off_leaks_orphans_proving_pragma_is_load_bearing -x` | ❌ Wave 0 |
| BUG-10(c) | sweep_orphans removes manufactured orphans | unit | `uv run pytest tests/test_db_fk_invariants.py::test_sweep_orphans_removes_orphan_streams_and_siblings -x` | ❌ Wave 0 |
| BUG-10(b) | Drift-guard WARN log fires when PRAGMA reads OFF after SET | unit (caplog) | `uv run pytest tests/test_db_fk_invariants.py::test_drift_guard_warns_when_pragma_reads_off -x` *(planner discretion — not explicitly required by CONTEXT but is the obvious closing test for D-10/D-11)* | ❌ Wave 0 |
| BUG-10(b) | Drift-guard sentinel throttles to once per session | unit | `uv run pytest tests/test_db_fk_invariants.py::test_drift_guard_logs_at_most_once_per_session -x` *(planner discretion — covers D-11)* | ❌ Wave 0 |
| BUG-10(d) + structural invariant | Sole sqlite3.connect callsite in production lives in repo.py | source-grep | `uv run pytest tests/test_db_connect_is_sole_connection_factory.py -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_db_fk_invariants.py tests/test_db_connect_is_sole_connection_factory.py -x` (sub-second; runs both new files)
- **Per wave merge:** `uv run pytest tests/test_db_fk_invariants.py tests/test_db_connect_is_sole_connection_factory.py tests/test_repo.py tests/test_station_siblings.py -x` (still sub-2-seconds; adds the two existing files that already cover cascade behavior — catches regressions in either direction)
- **Phase gate:** Full suite `uv run pytest tests/` green before `/gsd:verify-work`. Phase 77 INFRA-01 closed all known flakes — the full-suite gate is now reliable.

### Wave 0 Gaps

- [ ] `tests/test_db_fk_invariants.py` — new file; 5-7 tests covering D-13..D-16 + (planner-discretion) drift-guard log + sentinel-throttle
- [ ] `tests/test_db_connect_is_sole_connection_factory.py` — new file; source-grep gate per D-09/D-12
- [ ] `_reset_pragma_drift_sentinel_for_tests()` helper in `musicstreamer/repo.py` — needed for sentinel-reset between tests in same session (Pitfall 3)
- [ ] Per-test autouse fixture in `tests/test_db_fk_invariants.py` calling `_reset_pragma_drift_sentinel_for_tests()` — prevents cross-test sentinel leakage

*Existing test infrastructure (pytest, conftest.py, `tests/test_repo.py` fixture pattern) covers all needed runtime — no framework install required.*

## Security Domain

`security_enforcement` is not explicitly set in `.planning/config.json`, so treat as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase 80 touches DB connection factory only; no auth surface. |
| V3 Session Management | no | No session state introduced. |
| V4 Access Control | no | Single-user local desktop app; no access control surface. |
| V5 Input Validation | partial | Phase 80 introduces no new input surface; the sweep DELETEs are parameterless static SQL — no injection vector. |
| V6 Cryptography | no | No crypto in phase scope. |
| V8 Data Protection | yes | **Data integrity**: phase explicitly hardens referential integrity (FK cascades). Sweep is destructive (DELETE) but only on orphan rows whose parent is already gone — definitionally unreachable user data. |
| V13 API / V14 Configuration | no | No external API; PRAGMA is per-connection config, hardened. |

### Known Threat Patterns for SQLite + Python sqlite3 stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via dynamic table names in sweep | Tampering | All table names in `sweep_orphans` are hard-coded literals (D-05). No dynamic identifier interpolation. |
| Destructive sweep wiping live data | Repudiation / Tampering | `DELETE ... WHERE NOT IN (SELECT id FROM stations)` is mathematically restricted to rows whose parent is gone — by FK contract, those rows are already unreachable from any user-facing query. Sweep is a no-op for any reachable data. |
| Sentinel state corrupted by concurrent threads | Tampering | `_pragma_drift_logged` is a module-level bool; sqlite3 connections in Python are not thread-shared by default (project doesn't share `con` across threads — verified by Phase 77 work). Race is theoretical, not practical. |
| Log injection via INFO line | (Logging hygiene) | Format args (`%d`, `%d`) are integers from `cursor.rowcount` — typed, no user-controlled string. No injection vector. |

## Implementation Knowledge Gaps the Planner Should Resolve

These are the **Claude's-discretion** items from CONTEXT that the planner picks based on research above:

1. **`_log` placement in `repo.py`** — Recommendation: place `import logging` in the stdlib import block (line 2 region) and `_log = logging.getLogger(__name__)` after the project-imports block (line 7 region, before or after the `VALID_COVER_ART_SOURCES` constant). Either position is fine; the Phase 62 `player.py` shape places it immediately after the top-of-file imports.

2. **Test fixture strategy** — Recommendation: own fixtures inside `tests/test_db_fk_invariants.py` (do NOT reuse `tests/test_repo.py:7-13`). Reasons: (a) the new fixtures must call `db_connect()` directly (Pitfall 1), the existing fixture open-codes the connection; (b) keeping fixtures local makes the new test file self-contained for grep + cherry-pick.

3. **Source-grep implementation** — Recommendation: pure-Python `pathlib.rglob` + `re.compile` (no `git grep` subprocess). Reasons: (a) zero external-tool dependency in test env; (b) project precedent at `tests/test_packaging_spec.py` is pure-Python; (c) regex returns line numbers for grep-friendly failure messages.

4. **Whether to flag `sqlite3.dbapi2.connect`** — Recommendation: include in regex (`re.compile(r"sqlite3(\.dbapi2)?\.connect\(")`). Reasons: (a) belt-and-suspenders, two characters of regex; (b) no false-positive risk in this codebase (zero current `dbapi2` references); (c) future-proof against a maintainer trying to evade the gate by spelling the import differently.

5. **Throttle sentinel reset semantics** — Recommendation: add `_reset_pragma_drift_sentinel_for_tests()` helper function in `repo.py` (single line: `global _pragma_drift_logged; _pragma_drift_logged = False`). Reasons: (a) needed for cross-test isolation (Pitfall 3); (b) `_for_tests` suffix makes it grep-discoverable as test-only API; (c) leaving the sentinel module-level (no per-instance state) keeps `db_connect()` re-entrant and stateless aside from the one bit of session memory.

6. **Sweep log format** — Recommendation: single-line `_log.info("sweep_orphans: station_streams=%d station_siblings=%d", n1, n2)` per the CONTEXT shape. Reasons: (a) one log line per sweep is grep-friendly; (b) matches the project's "one structured INFO line per event" idiom (Phase 62 `cycle_close`).

7. **Optional call-site grep gate** (NOT required by CONTEXT — Claude's-discretion add): add a sixth source-grep test that reads `musicstreamer/__main__.py` source and asserts `sweep_orphans(con)` appears AFTER `db_init(con)` within `_run_gui`'s body. Mirrors the Phase 65 `tests/test_main_run_gui_ordering.py` shape. Cheap regression-lock; planner can defer if it adds friction.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `tests/test_main_run_gui_ordering.py` exists and uses `read_text` + substring assertions on `__main__.py` source | Claude's-discretion item #7, Pitfall 5 | LOW. The recommendation is a Claude's-discretion add, not a required output. If the file doesn't exist, the planner can either skip the call-site grep gate or create a new test file using `tests/test_packaging_spec.py` as the precedent. |
| A2 | The `con` object reused across `db_init(con)` and `sweep_orphans(con)` shares the PRAGMA state set inside `db_connect()` | Existing Code Shape § `_run_gui` | NONE. SQLite PRAGMAs set with `con.execute("PRAGMA ...")` are per-connection and persist for the connection's lifetime. Verified behavior. |
| A3 | `caplog` fixture captures `_log.warning()` calls from `musicstreamer.repo` logger correctly when the logger is escalated to INFO in `__main__.main` BUT the test runs in isolation (no `__main__.main` call) | Validation Architecture (drift-guard log test) | LOW. `caplog` captures at root level by default; the test can call `caplog.set_level(logging.WARNING, logger="musicstreamer.repo")` to be explicit. Planner should specify this in the test action. |

**All other claims in this research are tagged as VERIFIED via direct read of repo source this session (repo.py, __main__.py, conftest.py, tests/test_repo.py, tests/test_station_siblings.py, tests/test_packaging_spec.py, ROADMAP.md, REQUIREMENTS.md, CONTEXT.md).**

## Open Questions

1. **Should the existing `test_cascade_delete` (tests/test_repo.py:584-594) be moved/renamed, or left in place alongside the new D-13 test?**
   - What we know: the test already passes and exercises the same invariant as D-13's new test.
   - What's unclear: whether the planner prefers consolidation (single source of truth) or layered defense (two tests with different framings).
   - Recommendation: leave the existing test in place; add the new D-13 test with the more explicit name and Strategy-A fixture (calls `db_connect()`). Duplication is cheap; coverage is the goal.

2. **Should the existing sibling cascade test (tests/test_station_siblings.py:102-113) be moved/renamed?**
   - What we know: it covers ONE direction (`b_id`); D-14 requires both directions.
   - What's unclear: whether to add only the missing `_a_id` test in the new file (leaving the existing as `_b_id` coverage) or add both new tests in the new file.
   - Recommendation: add both new tests in the new file, leave the existing in place. Same rationale as Q1.

3. **Does the drift-guard read-back need to happen INSIDE the same `con` object after the SET, or is the SET-and-trust pattern sufficient?**
   - What we know: CONTEXT D-10/D-11 explicitly require the read-back ("after the existing SET ... read it back with `con.execute("PRAGMA foreign_keys").fetchone()[0]`").
   - What's unclear: nothing — CONTEXT is explicit. Listed here only to flag that there is no ambiguity; planner should not "optimize" the read-back away.

## Landmines / Pitfalls Discovered During Code Reading

1. **`db_init()` itself temporarily turns the PRAGMA OFF** (verified `repo.py:148-185` — the legacy `url` column rebuild block does `PRAGMA foreign_keys = OFF;` … `CREATE TABLE stations_new` … `INSERT INTO ... SELECT FROM stations` … `DROP TABLE stations` … `ALTER TABLE stations_new RENAME TO stations` … `PRAGMA foreign_keys = ON;` inside an `executescript`). This is a one-time legacy-schema migration that should never run on a v2.1-era DB (the legacy `url` column has been gone for many phases). **Impact on Phase 80:** If `db_init()` runs after the drift-guard read-back fires inside `db_connect()`, the sentinel will already be set to `True` and the brief OFF window during the executescript won't trip the WARN. This is **correct behavior** — the OFF is intentional and bracketed. But it means the runtime drift-guard read-back must happen INSIDE `db_connect()` BEFORE `db_init()` is ever called. Verified: that's exactly what the recommended shape does (`db_connect()` returns before `db_init()` is invoked).

2. **`tests/test_repo.py:620-624` has a `_make_bare_con()` helper that already follows the right pattern** — pure `sqlite3.connect(":memory:")` + row_factory + PRAGMA. Phase 80 could reuse this helper for D-13/D-14 if Strategy-A fixture proves awkward. Worth noting in case planner wants a fallback.

3. **`__main__._run_gui` is non-trivial — line 208-212 has Phase 66 / THEME-01 ordering constraints** (`con = db_connect()` then `db_init(con)` then `repo = Repo(con)` then `theme.apply_theme_palette(app, repo)`). The `sweep_orphans(con)` insertion at line 209-210 boundary is safe — it doesn't interact with theme apply, MainWindow construction, or single-instance acquisition. But planner should respect the existing comment block at line 202-207 (Phase 66 hoist rationale) — do NOT relocate the `db_connect`/`db_init` pair.

4. **`__main__._run_gui` also imports from `musicstreamer.repo` at line 194** — `from musicstreamer.repo import Repo, db_connect, db_init`. Phase 80 must extend this to `from musicstreamer.repo import Repo, db_connect, db_init, sweep_orphans`. Lint will catch a missing import; just a heads-up.

5. **CONTEXT mentions `.continue-here.md` ("Anti-patterns from this session") in canonical_refs**, but the file **does not currently exist** at `.planning/phases/80-sqlite-foreign-key-enforcement-set-pragma-foreign-keys-on-pe/.continue-here.md` (verified via `find`). The anti-patterns are nonetheless preserved verbatim in the CONTEXT.md `<domain>` section ("Out of scope" bullet list) — planner can read them there. No action needed; just noting the canonical_refs reference is currently dangling.

## Sources

### Primary (HIGH confidence)

- `musicstreamer/repo.py` — verified lines 1-21 (`db_connect`), 24-204 (`db_init`), 385-387 (`Repo.delete_station`). All FK cascade clauses and PRAGMA presence confirmed inline.
- `musicstreamer/__main__.py` — verified lines 163-238 (`_run_gui`) and 241-270 (`main`). Insertion points and per-logger escalation pattern confirmed.
- `tests/conftest.py` — verified lines 1-100. No DB fixtures present; per-file pattern confirmed.
- `tests/test_repo.py` — verified lines 1-65 (fixtures), 105-120 (existing delete_station tests), 584-594 (existing cascade test), 620-624 (`_make_bare_con` helper).
- `tests/test_station_siblings.py` — verified lines 60-113. Existing sibling cascade test confirmed at lines 102-113.
- `tests/test_packaging_spec.py` — verified lines 1-105. Source-grep gate precedent shape confirmed.
- `.planning/phases/80-sqlite-foreign-key-enforcement-set-pragma-foreign-keys-on-pe/80-CONTEXT.md` — all 17 decisions + Claude's-discretion items + out-of-scope list quoted verbatim above.
- `.planning/REQUIREMENTS.md` BUG-10 row — verified line 25.
- `.planning/ROADMAP.md` Phase 80 entry — verified lines 915-924.
- `.planning/config.json` — verified `nyquist_validation: true`.

### Secondary (MEDIUM confidence)

None required — Phase 80 is a pure local-codebase phase, no external library docs touched.

### Tertiary (LOW confidence)

None.

## Metadata

**Confidence breakdown:**

- **Existing code shape:** HIGH — every line cited was read directly this session.
- **Test analog identification:** HIGH — cascade test, sibling test, and source-grep precedent all confirmed.
- **Pitfalls:** HIGH — derived from concrete code reading, not training knowledge.
- **Validation Architecture:** HIGH — test commands and file names are all derivable from CONTEXT + verified pytest project layout.
- **Implementation knowledge gaps:** HIGH — recommendations are reasoned from concrete file inspection.

**Research date:** 2026-05-18
**Valid until:** 2026-06-18 (30-day stable window; Phase 80 has no fast-moving dependencies)

## RESEARCH COMPLETE
