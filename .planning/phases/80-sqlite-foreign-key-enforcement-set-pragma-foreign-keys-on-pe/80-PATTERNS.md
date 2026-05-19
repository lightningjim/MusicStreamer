# Phase 80: SQLite foreign-key enforcement — Pattern Map

**Mapped:** 2026-05-18
**Files analyzed:** 4 (2 modified, 2 created)
**Analogs found:** 4 / 4

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `musicstreamer/repo.py` (MODIFIED) | data-access / connection-factory + utility | request-response (per-call factory) + batch (sweep DELETE) | `musicstreamer/player.py` (logger introduction) + own existing `db_init` (executescript/commit shape) | exact (same module precedent for logger intro) |
| `musicstreamer/__main__.py` (MODIFIED) | app entry / wiring | event-driven (startup sequence) | own existing `_run_gui` + `main` per-logger block (Phase 62 / Phase 79 precedents) | exact (in-file precedent — adding one more line of the same shape) |
| `tests/test_db_fk_invariants.py` (CREATED) | test (unit, regression) | CRUD + negative-proof + caplog (log assertion) | `tests/test_repo.py::test_cascade_delete` (lines 584-594) + `tests/test_station_siblings.py::test_cascade_on_station_delete` (lines 102-113) | exact (direct ancestors for D-13/D-14) |
| `tests/test_db_connect_is_sole_connection_factory.py` (CREATED) | test (source-grep gate / drift-guard) | static analysis (read_text + regex) | `tests/test_packaging_spec.py` (lines 1-80) | exact (project precedent for source-grep gate) |

## Pattern Assignments

### `musicstreamer/repo.py` (MODIFIED — connection factory + sweep utility + drift-guard sentinel)

**Analog 1 — module-level `_log` introduction:** `musicstreamer/player.py:79-81`

```python
# Phase 62 / BUG-09: module logger (first logger in player.py).
# Surfaced at INFO via __main__.py per-logger setLevel — see Plan 03.
_log = logging.getLogger(__name__)
```

**Apply to `repo.py`** — place `import logging` in the stdlib import block immediately after `import sqlite3` (line 1), then place `_log` declaration after the project-imports block (after line 5, before or after the `VALID_COVER_ART_SOURCES` constant at line 14). Mirror the Phase-X-rationale comment style.

Target shape (after Phase 80 — adapted from RESEARCH.md "Pattern 1"):
```python
import logging
import sqlite3
from typing import Optional, List

from musicstreamer.models import Station, Provider, Favorite, StationStream
from musicstreamer import paths

# Phase 80 / BUG-10: module logger (first logger in repo.py). Surfaced at
# INFO via __main__.py per-logger setLevel — mirrors Phase 62 player.py.
_log = logging.getLogger(__name__)

# Phase 80 / BUG-10 D-11: module-level sentinel throttling the PRAGMA
# drift-guard WARN to once per session. Reset for tests via
# _reset_pragma_drift_sentinel_for_tests() (Pitfall 3).
_pragma_drift_logged: bool = False
```

---

**Analog 2 — existing `db_connect()` shape:** `musicstreamer/repo.py:17-21` (the function Phase 80 modifies)

```python
def db_connect() -> sqlite3.Connection:
    con = sqlite3.connect(paths.db_path())
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    return con
```

**Apply to `db_connect()`** — keep all four existing lines (PRAGMA line is load-bearing per CONTEXT D-17; do NOT add a duplicate per anti-pattern in `.continue-here.md`). Append:
1. Function-level docstring (D-17) — stating PRAGMA is load-bearing FK-enforcement; production code MUST go through this function.
2. `global _pragma_drift_logged` declaration inside the function.
3. After the existing `con.execute("PRAGMA foreign_keys = ON;")`, add an `if not _pragma_drift_logged:` block that reads the PRAGMA back and emits `_log.warning("PRAGMA foreign_keys is OFF after SET — drift detected")` if the read returns `0` (Pitfall 6 — `== 0` truthy comparison, NOT `is False`).

Reference target shape: see RESEARCH.md "`db_connect()` — target shape after Phase 80" (research file lines 425-454).

---

**Analog 3 — existing `db_init()` commit + executescript pattern:** `musicstreamer/repo.py:24-85`

```python
def db_init(con: sqlite3.Connection):
    con.executescript(
        """
        ...
        CREATE TABLE IF NOT EXISTS station_streams (
            ...
            FOREIGN KEY(station_id) REFERENCES stations(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS station_siblings (
          a_id INTEGER NOT NULL,
          b_id INTEGER NOT NULL,
          FOREIGN KEY(a_id) REFERENCES stations(id) ON DELETE CASCADE,
          FOREIGN KEY(b_id) REFERENCES stations(id) ON DELETE CASCADE,
          ...
        );
        """
    )
    con.commit()
```

**Apply to new `sweep_orphans(con)` function** — place it adjacent to `db_init` in the same module (D-02). Mirror the `con.commit()` at the end. Use two `con.execute(...)` calls (not `executescript`) because the function needs `cursor.rowcount` per statement (D-01, D-07).

Target shape: see RESEARCH.md "`sweep_orphans(con)` — target shape" (research file lines 458-487). Critical details:
- Two separate `con.execute(...)` calls, capturing `cur1.rowcount` and `cur2.rowcount`.
- Conditional INFO log: `if cur1.rowcount > 0 or cur2.rowcount > 0` (D-04 silent on N=0).
- Log format: `_log.info("sweep_orphans: station_streams=%d station_siblings=%d", cur1.rowcount, cur2.rowcount)` — matches Phase 62 cycle_close shape.
- `con.commit()` at the end. Returns None.
- Function-level docstring citing D-01/D-02/D-04/D-05/D-07/D-06/D-08 rationale.

---

**Analog 4 — test-only helper convention** (Claude's discretion item #5)

No direct in-codebase precedent for `_for_tests` suffix helpers in `repo.py`. Closest pattern: project convention is function-level docstrings + private (`_`-prefixed) helpers for module-internal state. Recommended shape:

```python
def _reset_pragma_drift_sentinel_for_tests() -> None:
    """Test-only helper: re-arm the drift-guard WARN throttle.

    The module-level _pragma_drift_logged sentinel persists across the
    pytest session (Pitfall 3). Tests that exercise the drift-guard log
    surface must call this helper in their setup to ensure the WARN
    fires deterministically rather than being swallowed by a flip in
    an earlier test.

    The _for_tests suffix makes this grep-discoverable as test-only API.
    """
    global _pragma_drift_logged
    _pragma_drift_logged = False
```

Place adjacent to the `_pragma_drift_logged` sentinel declaration (or at the bottom of `db_connect()` block — planner picks).

---

### `musicstreamer/__main__.py` (MODIFIED — insert sweep call + add per-logger INFO escalation)

**Analog 1 — `_run_gui` startup sequence:** `musicstreamer/__main__.py:194` (imports) + `208-210` (db lifecycle)

```python
from musicstreamer.repo import Repo, db_connect, db_init
...
con = db_connect()
db_init(con)
repo = Repo(con)
```

**Apply (two edits):**

1. **Import line (line 194):** extend to add `sweep_orphans`:
   ```python
   from musicstreamer.repo import Repo, db_connect, db_init, sweep_orphans
   ```

2. **Call site (between lines 209 and 210):** insert `sweep_orphans(con)` immediately after `db_init(con)` and BEFORE `repo = Repo(con)`. Same `con` object — no new connection (CONTEXT D-02).

Target shape:
```python
con = db_connect()
db_init(con)
sweep_orphans(con)  # Phase 80 / BUG-10 D-02: heal orphans left by manual sqlite3-shell DELETEs.
repo = Repo(con)
```

**Pitfall reminder (RESEARCH Pitfall 5):** Do NOT relocate the `db_connect`/`db_init`/`repo` block — Phase 66/THEME-01 ordering at lines 202-207 is load-bearing. The insertion is a single line between two existing lines.

---

**Analog 2 — per-logger INFO escalation:** `musicstreamer/__main__.py:241-250`

```python
def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING)
    # Phase 62 / BUG-09 / Pitfall 5: per-logger INFO level for musicstreamer.player
    # so buffer-underrun cycle close lines surface to stderr without bumping the
    # GLOBAL level (which would surface chatter from aa_import / gbs_api / mpris2).
    logging.getLogger("musicstreamer.player").setLevel(logging.INFO)
    logging.getLogger("musicstreamer.soma_import").setLevel(logging.INFO)
    # Phase 79 / BUG-11: surface scan_playlist node_path INFO line at default
    # verbosity (consumed by Plan 79-03's yt_import.scan_playlist INFO log).
    logging.getLogger("musicstreamer.yt_import").setLevel(logging.INFO)
```

**Apply** — add one line after line 250, mirroring the Phase-X-rationale comment style:

```python
# Phase 80 / BUG-10: surface sweep_orphans INFO line + PRAGMA drift WARN
# without bumping the global level. sweep_orphans is silent on N=0 (D-04)
# so steady-state output is unchanged.
logging.getLogger("musicstreamer.repo").setLevel(logging.INFO)
```

---

### `tests/test_db_fk_invariants.py` (CREATED — 5-7 unit tests)

**Analog 1 — positive cascade test pattern:** `tests/test_repo.py:584-594`

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

**Apply to D-13 `test_delete_station_cascades_station_streams`** — mirror this shape EXACTLY (insert → verify pre → delete → assert child rowcount == 0; Pitfall 4 says assert on the CHILD row count, not the DELETE's rowcount). DEVIATION: use a Phase-80-specific fixture that calls `db_connect()` directly (NOT the open-coded `tests/test_repo.py:7-13` fixture), so the test exercises the production code path end-to-end (Pitfall 1: open-coded fixtures don't catch drift in the factory itself).

---

**Analog 2 — sibling cascade test pattern:** `tests/test_station_siblings.py:102-113`

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

**Apply to D-14 (two tests):**
- `test_delete_station_cascades_station_siblings_a_id` — delete station id=1 (the `a_id` side); assert sibling row gone.
- `test_delete_station_cascades_station_siblings_b_id` — delete station id=2 (the `b_id` side); assert sibling row gone. This is the direct mirror of the existing test, renamed for invariant clarity.

Note: the existing `test_cascade_on_station_delete` at `tests/test_station_siblings.py:102-113` stays in place (Open Question 2 recommendation: duplication is cheap; coverage is the goal).

---

**Analog 3 — bare-connection / negative-proof pattern:** `tests/test_repo.py:620-624`

```python
def _make_bare_con():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    return con
```

**Apply to D-15 `test_pragma_off_leaks_orphans_proving_pragma_is_load_bearing`** — same `sqlite3.connect(":memory:")` shape, but DELIBERATELY do NOT set the PRAGMA. Use `executescript` to lay down a minimal stations + station_streams schema matching the real CASCADE clause (RESEARCH "Negative PRAGMA-off test — target shape" lines 491-524).

This is the ONE test in the file that needs raw `sqlite3.connect(":memory:")`. The source-grep gate (D-12) explicitly excludes `tests/` so the bare `sqlite3.connect(":memory:")` here is legal.

---

**Analog 4 — sweep happy-path test** — no direct codebase analog (this is the Phase-80-original test). Recipe (D-16):
1. Open a connection via `db_connect()` (production factory path).
2. `con.execute("PRAGMA foreign_keys = OFF")` mid-test.
3. Insert a station + a stream pointing at it.
4. Hard-DELETE the station via raw SQL (cascade does NOT fire because PRAGMA is OFF).
5. `con.execute("PRAGMA foreign_keys = ON")` to restore.
6. Call `sweep_orphans(con)`.
7. Assert the orphan stream is gone (`SELECT COUNT(*) FROM station_streams WHERE station_id=?` == 0).

Mirrors the actual Synphaera-shaped failure mode (Phase 74 F-07-03).

---

**Analog 5 — caplog usage for drift-guard log assertion** (Claude's-discretion tests covering D-10 and D-11). No exact codebase analog for drift-guard log shape, but pytest `caplog` fixture is standard. Use `caplog.set_level(logging.WARNING, logger="musicstreamer.repo")` to be explicit (Assumption A3). Test recipe:
- For D-10 `test_drift_guard_warns_when_pragma_reads_off`: monkeypatch `sqlite3.Connection.execute` or use a wrapper that forces the PRAGMA read-back to return 0; call `db_connect()`; assert the WARN line was emitted to `caplog.records`.
- For D-11 `test_drift_guard_logs_at_most_once_per_session`: call `db_connect()` multiple times under the forced-OFF condition; assert exactly one WARN record. Reset sentinel via `_reset_pragma_drift_sentinel_for_tests()` in a per-test autouse fixture (Pitfall 3).

---

**Fixture strategy — Strategy A (production path) for D-13/D-14/D-16:**

```python
# Pattern derived from RESEARCH §"Existing Code Shape § tests/conftest.py" + Pitfall 2.
@pytest.fixture
def db_con(monkeypatch, tmp_path):
    """Open a SQLite connection via the production db_connect() factory.

    Monkeypatches paths.db_path BEFORE calling db_connect() (Pitfall 2 —
    paths.db_path() is read at call time inside db_connect()'s body, so
    the patch must be in place before the call). Calls db_init(con) to
    lay down the schema so the FK CASCADE clauses are present.

    UNLIKE tests/test_repo.py:7-13's `repo` fixture, this routes through
    db_connect() so the test exercises the entire factory function —
    catching drift in the PRAGMA line OR any other body line (Pitfall 1).
    """
    from musicstreamer import paths as _paths
    from musicstreamer.repo import db_connect, db_init, _reset_pragma_drift_sentinel_for_tests
    monkeypatch.setattr(_paths, "db_path", lambda: str(tmp_path / "test.db"))
    _reset_pragma_drift_sentinel_for_tests()
    con = db_connect()
    db_init(con)
    yield con
    con.close()
```

**Fixture strategy — Strategy B (raw sqlite3) for D-15 only:** open `sqlite3.connect(":memory:")` directly inside the test body; no fixture needed.

---

### `tests/test_db_connect_is_sole_connection_factory.py` (CREATED — source-grep gate)

**Analog — `tests/test_packaging_spec.py:25-69`:**

```python
from __future__ import annotations

from pathlib import Path

import pytest

_SPEC = (
    Path(__file__).resolve().parent.parent
    / "packaging"
    / "windows"
    / "MusicStreamer.spec"
)

@pytest.fixture(scope="module")
def spec_source() -> str:
    assert _SPEC.is_file(), f"expected MusicStreamer.spec at {_SPEC}"
    return _SPEC.read_text(encoding="utf-8")


def test_spec_imports_copy_metadata(spec_source: str) -> None:
    """Phase 65 D-08: spec extends the existing PyInstaller.utils.hooks import
    to include copy_metadata alongside collect_all."""
    assert "copy_metadata" in spec_source, (
        "MusicStreamer.spec must import copy_metadata from "
        ...
    )
```

**Apply** — mirror this shape (project precedent per memory `feedback_gstreamer_mock_blind_spot.md`). Key adaptations:
- Path target: `musicstreamer/` package directory (NOT a single file).
- Walk strategy: `rglob("*.py")` over the production package.
- Match: compiled regex `re.compile(r"sqlite3(\.dbapi2)?\.connect\(")` (RESEARCH knowledge gap #4 — belt-and-suspenders against `dbapi2` spelling).
- Fixture: `scope="module"`, returns `dict[Path, list[int]]` of `{file → line numbers with hits}` for grep-friendly failure messages.
- Two test functions:
  1. `test_only_one_sqlite_connect_callsite_in_production` — assert exactly one hit total.
  2. `test_sole_sqlite_connect_callsite_lives_in_repo_py` — assert the file is `repo.py`.

Target shape: see RESEARCH "Source-grep gate — target shape" (research file lines 528-568).

---

## Shared Patterns

### Pattern: Module-level `_log = logging.getLogger(__name__)` + Phase-X comment
**Source:** `musicstreamer/player.py:79-81`
**Apply to:** `musicstreamer/repo.py` (new logger introduction)
**Comment convention:** `# Phase X / BUG-Y: module logger (first logger in <file>.py). Surfaced at INFO via __main__.py per-logger setLevel — see Plan NN.`

### Pattern: Per-logger INFO escalation with Phase-X rationale comment
**Source:** `musicstreamer/__main__.py:243-250` (Phase 62 player + Phase 79 yt_import precedents)
**Apply to:** `musicstreamer/__main__.py::main` — add `musicstreamer.repo` line
**Shape:** Two-line comment naming the phase + reason; one `setLevel(logging.INFO)` line.

### Pattern: Sub-second test command convention
**Source:** RESEARCH "Validation Architecture" — `uv run pytest tests/test_db_fk_invariants.py tests/test_db_connect_is_sole_connection_factory.py -x`
**Apply to:** Per-task commit verification in both new test files.

### Pattern: `caplog.set_level(logging.WARNING, logger="musicstreamer.repo")` explicit-capture
**Source:** Assumption A3 — pytest caplog standard idiom (no direct codebase analog in research scope; planner uses pytest docs).
**Apply to:** D-10 and D-11 drift-guard log tests (Claude's-discretion add).

### Pattern: `monkeypatch.setattr` BEFORE first factory call
**Source:** Pitfall 2 — `paths.db_path()` is read at call time, not import time.
**Apply to:** All fixtures in `tests/test_db_fk_invariants.py` that use Strategy A (production factory path). Patch `musicstreamer.paths.db_path` BEFORE the first `db_connect()` call.

### Anti-Pattern Reminders (from CONTEXT `.continue-here.md` / RESEARCH)
- **Do NOT** add `PRAGMA foreign_keys = ON;` to `db_connect()` — it's already at line 20. The phase is *locking* it in, not adding it.
- **Do NOT** sweep `favorites` — no FK, intentional persistence (D-06).
- **Do NOT** gate `sweep_orphans()` by `PRAGMA user_version`.
- **Do NOT** fold `sweep_orphans()` into `db_init()` (D-02 — separate intent, separately testable).
- **Do NOT** use `PRAGMA foreign_key_list(...)` introspection (CONTEXT "too clever").
- **Do NOT** add an allow-list `# noqa: db-connect-bypass` annotation (CONTEXT D-12 rejected).

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| — | — | — | All four new/modified files have direct in-codebase analogs. Phase 80 is overwhelmingly a tightening phase; nothing requires inventing a new pattern. |

## Metadata

**Analog search scope:** `musicstreamer/` (production tree), `tests/` (test tree)
**Files scanned:** `musicstreamer/repo.py`, `musicstreamer/player.py`, `musicstreamer/__main__.py`, `tests/test_repo.py`, `tests/test_station_siblings.py`, `tests/test_packaging_spec.py`, `tests/conftest.py`
**Files read this session:** 7 (all RESEARCH-recommended analogs verified)
**Pattern extraction date:** 2026-05-18
