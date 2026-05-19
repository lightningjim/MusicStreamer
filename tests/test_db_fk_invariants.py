"""Phase 80 / BUG-10 regression suite: FK invariants + drift-guard + sweep.

Locks in the Wave-1 hardening of ``musicstreamer/repo.py`` (Plan 80-01):

- D-13: positive cascade test for ``station_streams`` exercising the
  production ``db_connect()`` factory end-to-end (Strategy A).
- D-14: symmetry coverage for ``station_siblings`` cascade — one test
  per FK column (``a_id`` and ``b_id``).
- D-15: negative-proof test (Strategy B — raw ``sqlite3.connect(":memory:")``
  with PRAGMA OFF) naming the cause-effect in the function name:
  ``test_pragma_off_leaks_orphans_proving_pragma_is_load_bearing``.
- D-16: ``sweep_orphans`` happy-path test using the OFF→DELETE→ON
  manufacturing recipe (the actual Phase 74 F-07-03 Synphaera shape).
- D-10 (planner discretion): drift-guard WARN log fires when the PRAGMA
  read-back returns 0.
- D-11 (planner discretion): drift-guard logs at most once per session
  (the module-level ``_pragma_drift_logged`` sentinel throttle works).

A per-test autouse fixture calls ``_reset_pragma_drift_sentinel_for_tests``
so the once-per-session throttle is re-armed between tests (Pitfall 3 —
without this, the first test that triggers the drift-guard flips the
sentinel and masks the drift-guard for all subsequent tests in the run).

The Strategy-A ``db_con`` fixture monkeypatches ``musicstreamer.paths.db_path``
BEFORE the first ``db_connect()`` call (Pitfall 2 — ``paths.db_path()`` is
read at call time inside ``db_connect``'s body, not at import time).
"""
import logging
import sqlite3

import pytest

from musicstreamer import paths as _paths
from musicstreamer.repo import (
    Repo,
    _reset_pragma_drift_sentinel_for_tests,
    db_connect,
    db_init,
    sweep_orphans,
)

# DB filename matches project convention (memory reference_musicstreamer_db_schema:
# DB is ``musicstreamer.sqlite3``, NOT ``library.db`` or ``test.db``).
_DB_FILENAME = "musicstreamer.sqlite3"


@pytest.fixture(autouse=True)
def _reset_drift_sentinel():
    """Re-arm the module-level ``_pragma_drift_logged`` sentinel before
    every test in this file (RESEARCH Pitfall 3 — module state is
    process-scoped; pytest reuses the imported module across the whole
    session, so without an explicit reset the sentinel leaks across
    tests and masks real drift)."""
    _reset_pragma_drift_sentinel_for_tests()
    yield
    _reset_pragma_drift_sentinel_for_tests()


@pytest.fixture
def db_con(monkeypatch, tmp_path):
    """Open a SQLite connection via the production ``db_connect()`` factory.

    Strategy A (RESEARCH §"Fixture strategy A vs B"): routes through
    ``db_connect()`` so the test exercises the entire factory function
    — catching drift in the PRAGMA line OR any other body line
    (Pitfall 1 — open-coded fixtures that bypass ``db_connect`` don't
    catch drift in the factory itself).

    Pitfall 2: the monkeypatch of ``paths.db_path`` MUST land BEFORE
    the first ``db_connect()`` call — ``paths.db_path()`` is read at
    call time inside ``db_connect``'s body, not at import time.
    """
    monkeypatch.setattr(
        _paths,
        "db_path",
        lambda: str(tmp_path / _DB_FILENAME),
    )
    con = db_connect()
    db_init(con)
    yield con
    con.close()


@pytest.fixture
def repo(db_con):
    """Convenience: ``Repo`` built on the Strategy-A ``db_con`` fixture."""
    return Repo(db_con)


# --- D-13 positive cascade ---------------------------------------------------


def test_delete_station_cascades_station_streams(repo):
    """D-13: ``Repo.delete_station`` cascades to ``station_streams``.

    Mirrors the shape of ``tests/test_repo.py::test_cascade_delete``
    (lines 584-594) but routes through the production ``db_connect()``
    factory via the Strategy-A fixture (Pitfall 1). If a future commit
    removes the ``PRAGMA foreign_keys = ON;`` line from ``db_connect``,
    this test fails — locking the PRAGMA in.
    """
    sid = repo.insert_station("Test FM", "http://test.fm/stream", "", "")
    streams_before = repo.list_streams(sid)
    assert len(streams_before) == 1, (
        "precondition: insert_station should auto-create exactly one "
        "station_streams row for the given URL"
    )

    repo.delete_station(sid)

    rows = repo.con.execute(
        "SELECT COUNT(*) FROM station_streams WHERE station_id = ?", (sid,)
    ).fetchone()[0]
    assert rows == 0, (
        f"expected ON DELETE CASCADE to remove station_streams rows for "
        f"station_id={sid} but found {rows} surviving — PRAGMA "
        f"foreign_keys may be OFF in db_connect()"
    )


# --- D-14 sibling cascade (symmetry coverage) --------------------------------


def test_delete_station_cascades_station_siblings_a_id(db_con):
    """D-14a: deleting the station that occupies the ``a_id`` column of a
    sibling row cascades the sibling row away.

    The ``a_id < b_id`` CHECK constraint means the lower-id station is
    always the ``a_id`` side. Inserting stations 1 and 2 with sibling
    ``(1, 2)`` and DELETing station id=1 exercises the ``a_id`` FK
    cascade. Mirrors ``tests/test_station_siblings.py::test_cascade_on_station_delete``
    but in the opposite direction (the existing test deletes id=2 — the
    ``b_id`` side).
    """
    db_con.execute("INSERT INTO stations(id, name, tags) VALUES (1, 'A', '')")
    db_con.execute("INSERT INTO stations(id, name, tags) VALUES (2, 'B', '')")
    db_con.execute("INSERT INTO station_siblings(a_id, b_id) VALUES (1, 2)")
    db_con.commit()

    db_con.execute("DELETE FROM stations WHERE id = 1")
    db_con.commit()

    count = db_con.execute(
        "SELECT COUNT(*) AS c FROM station_siblings"
    ).fetchone()["c"]
    assert count == 0, (
        f"expected sibling row to be cascade-deleted when its a_id station "
        f"was DELETEd; found {count} surviving"
    )


def test_delete_station_cascades_station_siblings_b_id(db_con):
    """D-14b: deleting the station that occupies the ``b_id`` column of a
    sibling row cascades the sibling row away.

    Direct mirror of ``tests/test_station_siblings.py::test_cascade_on_station_delete``
    (lines 102-113) but renamed for invariant clarity and run through the
    Strategy-A fixture (production factory path). Duplication with the
    existing test is intentional (RESEARCH Open Question 2 recommendation —
    duplication is cheap; coverage is the goal).
    """
    db_con.execute("INSERT INTO stations(id, name, tags) VALUES (1, 'A', '')")
    db_con.execute("INSERT INTO stations(id, name, tags) VALUES (2, 'B', '')")
    db_con.execute("INSERT INTO station_siblings(a_id, b_id) VALUES (1, 2)")
    db_con.commit()

    db_con.execute("DELETE FROM stations WHERE id = 2")
    db_con.commit()

    count = db_con.execute(
        "SELECT COUNT(*) AS c FROM station_siblings"
    ).fetchone()["c"]
    assert count == 0, (
        f"expected sibling row to be cascade-deleted when its b_id station "
        f"was DELETEd; found {count} surviving"
    )


# --- D-15 negative-proof (PRAGMA OFF leaks orphans) --------------------------


def test_pragma_off_leaks_orphans_proving_pragma_is_load_bearing():
    """D-15: without ``PRAGMA foreign_keys = ON``, ``ON DELETE CASCADE``
    does NOT fire — the PRAGMA in ``db_connect()`` is load-bearing.

    This test exists to lock the cause-effect into the test name. If it
    starts FAILING (i.e. the cascade DOES fire without the PRAGMA), then
    either SQLite's default changed or this test's setup is wrong — either
    way, a future maintainer needs to understand why ``db_connect()``'s
    PRAGMA line is load-bearing before changing it.

    Strategy B (RESEARCH §"Fixture strategy A vs B"): raw
    ``sqlite3.connect(":memory:")`` with DELIBERATELY no PRAGMA. The D-12
    source-grep gate (Plan 80-04) explicitly excludes ``tests/`` precisely
    so this negative-proof test can hold.
    """
    con = sqlite3.connect(":memory:")
    # NOTE: deliberately NOT setting PRAGMA foreign_keys = ON. The whole
    # point of this test is to prove that cascade does NOT fire when the
    # PRAGMA is OFF (SQLite's per-connection default).
    con.executescript(
        """
        CREATE TABLE stations (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE station_streams (
            id INTEGER PRIMARY KEY,
            station_id INTEGER NOT NULL,
            FOREIGN KEY(station_id) REFERENCES stations(id) ON DELETE CASCADE
        );
        """
    )
    con.execute("INSERT INTO stations(id, name) VALUES (1, 'X')")
    con.execute("INSERT INTO station_streams(id, station_id) VALUES (1, 1)")
    con.commit()

    con.execute("DELETE FROM stations WHERE id = 1")
    con.commit()

    rows = con.execute("SELECT COUNT(*) FROM station_streams").fetchone()[0]
    assert rows == 1, (
        "expected the orphan station_streams row to SURVIVE the parent "
        "DELETE because PRAGMA foreign_keys is OFF (SQLite's per-connection "
        "default) — if this assertion fails, either SQLite's default "
        "cascade behavior changed or this test set up the schema "
        "differently than db_init() does. The PRAGMA at db_connect() is "
        "load-bearing precisely because OF this default."
    )
    con.close()


# --- D-16 sweep_orphans happy path -------------------------------------------


def test_sweep_orphans_removes_orphan_streams_and_siblings(db_con):
    """D-16: ``sweep_orphans(con)`` removes orphan rows manufactured via
    the OFF→DELETE→ON sequence.

    Covers the actual Phase 74 F-07-03 ``Synphaera``-shaped failure mode:
    a manual ``sqlite3``-shell DELETE that bypassed ``db_connect()``'s
    PRAGMA left orphan station_streams rows. The sweep heals them on the
    next app start.

    Recipe: open via Strategy-A fixture (PRAGMA ON), turn the PRAGMA OFF
    inside the test, insert parent + children, DELETE the parent (cascade
    does NOT fire because the PRAGMA is OFF), turn the PRAGMA back ON,
    call ``sweep_orphans``, assert both orphan tables are clean.
    """
    # Temporarily disable PRAGMA to manufacture orphans the way Phase 74
    # F-07-03 produced them in production (manual sqlite3-shell session).
    db_con.execute("PRAGMA foreign_keys = OFF")

    # Insert two stations + one stream pointing at station 10 + one
    # sibling row linking stations 10 and 20.
    db_con.execute("INSERT INTO stations(id, name, tags) VALUES (10, 'Orphaned', '')")
    db_con.execute("INSERT INTO stations(id, name, tags) VALUES (20, 'Partner', '')")
    db_con.execute(
        "INSERT INTO station_streams(station_id, url) VALUES (10, 'http://x.y/stream')"
    )
    # Respect CHECK(a_id < b_id) — 10 < 20.
    db_con.execute("INSERT INTO station_siblings(a_id, b_id) VALUES (10, 20)")
    db_con.commit()

    # Hard-DELETE station 10. Cascade does NOT fire because PRAGMA is OFF.
    db_con.execute("DELETE FROM stations WHERE id = 10")
    db_con.commit()

    # Confirm orphans exist pre-sweep (precondition).
    orphan_streams_pre = db_con.execute(
        "SELECT COUNT(*) FROM station_streams WHERE station_id = 10"
    ).fetchone()[0]
    orphan_siblings_pre = db_con.execute(
        "SELECT COUNT(*) FROM station_siblings WHERE a_id = 10 OR b_id = 10"
    ).fetchone()[0]
    assert orphan_streams_pre == 1, (
        "precondition: orphan station_streams row should exist after "
        "PRAGMA-OFF DELETE of its parent"
    )
    assert orphan_siblings_pre == 1, (
        "precondition: orphan station_siblings row should exist after "
        "PRAGMA-OFF DELETE of one of its endpoints"
    )

    # Restore PRAGMA, then sweep.
    db_con.execute("PRAGMA foreign_keys = ON")
    sweep_orphans(db_con)

    # Both orphan tables should now be clean.
    orphan_streams_post = db_con.execute(
        "SELECT COUNT(*) FROM station_streams WHERE station_id = 10"
    ).fetchone()[0]
    orphan_siblings_post = db_con.execute(
        "SELECT COUNT(*) FROM station_siblings WHERE a_id = 10 OR b_id = 10"
    ).fetchone()[0]
    assert orphan_streams_post == 0, (
        f"sweep_orphans should have removed the orphan station_streams "
        f"row (station_id=10) but {orphan_streams_post} remain"
    )
    assert orphan_siblings_post == 0, (
        f"sweep_orphans should have removed the orphan station_siblings "
        f"row (a_id=10 OR b_id=10) but {orphan_siblings_post} remain"
    )


# --- D-10 / D-11 drift-guard log surface (Claude's-discretion adds) ---------


class _FakeCursor:
    """Cursor stub whose ``fetchone()`` returns ``(0,)`` — used by
    ``_PragmaOffConnection`` to force the drift-guard read-back to see
    ``0`` (PRAGMA OFF) regardless of what the underlying SQLite did.
    """

    def fetchone(self):
        return (0,)


class _PragmaOffConnection:
    """Wrapper around a real ``sqlite3.Connection`` that intercepts the
    drift-guard read-back (``con.execute("PRAGMA foreign_keys")``) and
    returns a cursor whose ``fetchone()`` yields ``(0,)`` — simulating
    a PRAGMA drift (the SET succeeded silently but the read-back says
    OFF). All other ``execute`` calls pass through to the real connection.

    This is the minimal-surgery way to drive the WARN log path in
    ``db_connect()`` without modifying production code or the SQLite
    backend itself.
    """

    def __init__(self, real_con):
        self._real = real_con

    def execute(self, sql, *args, **kwargs):
        # Intercept ONLY the drift-guard read-back. The PRAGMA SET
        # statement ``PRAGMA foreign_keys = ON;`` (note the trailing ``;``
        # and the ``= ON``) is a different string and passes through.
        if sql == "PRAGMA foreign_keys":
            return _FakeCursor()
        return self._real.execute(sql, *args, **kwargs)

    # Pass-through for everything else db_connect() touches before return.
    def __setattr__(self, name, value):
        if name == "_real":
            object.__setattr__(self, name, value)
        else:
            setattr(self._real, name, value)

    def __getattr__(self, name):
        return getattr(self._real, name)


def _install_pragma_off_factory(monkeypatch, tmp_path):
    """Helper for tests 6 + 7: monkeypatch ``musicstreamer.repo.sqlite3.connect``
    to return ``_PragmaOffConnection`` wrapping a real ``:memory:`` con,
    AND monkeypatch ``paths.db_path`` so ``db_connect()`` doesn't hit
    the real user DB. The wrapper forces the read-back inside
    ``db_connect()`` to return ``0``, triggering the drift-guard WARN.
    """
    import musicstreamer.repo as _repo_mod
    real_connect = sqlite3.connect

    def _fake_connect(path, *args, **kwargs):
        # Open a real :memory: con so subsequent execute() calls in
        # db_connect() (the PRAGMA SET) succeed; the wrapper intercepts
        # only the read-back string.
        real_con = real_connect(":memory:")
        return _PragmaOffConnection(real_con)

    monkeypatch.setattr(_paths, "db_path", lambda: str(tmp_path / _DB_FILENAME))
    monkeypatch.setattr(_repo_mod.sqlite3, "connect", _fake_connect)


def test_drift_guard_warns_when_pragma_reads_off(monkeypatch, tmp_path, caplog):
    """D-10: when the PRAGMA read-back returns ``0`` (drift detected),
    ``db_connect()`` emits exactly one WARN log record naming the cause.

    Verifies the WARN line at ``musicstreamer.repo.db_connect`` fires
    against the ``musicstreamer.repo`` logger at WARNING level with the
    grep-friendly substring ``PRAGMA foreign_keys is OFF after SET``.
    """
    caplog.set_level(logging.WARNING, logger="musicstreamer.repo")
    _install_pragma_off_factory(monkeypatch, tmp_path)

    # Autouse fixture already reset the sentinel; be explicit for clarity.
    _reset_pragma_drift_sentinel_for_tests()

    db_connect()  # triggers the read-back → 0 → WARN

    matching = [
        rec
        for rec in caplog.records
        if rec.name == "musicstreamer.repo"
        and rec.levelno == logging.WARNING
        and "PRAGMA foreign_keys is OFF after SET" in rec.getMessage()
    ]
    assert len(matching) == 1, (
        f"expected exactly one WARN log record matching "
        f"'PRAGMA foreign_keys is OFF after SET' from logger "
        f"'musicstreamer.repo'; found {len(matching)}: "
        f"{[rec.getMessage() for rec in caplog.records]}"
    )


def test_drift_guard_logs_at_most_once_per_session(monkeypatch, tmp_path, caplog):
    """D-11: the module-level ``_pragma_drift_logged`` sentinel throttles
    the WARN to once per session.

    Calls ``db_connect()`` three times under the forced-OFF condition;
    asserts only the FIRST call emits a WARN (sentinel flipped after the
    first call). If the sentinel throttle regresses, this test catches it.
    """
    caplog.set_level(logging.WARNING, logger="musicstreamer.repo")
    _install_pragma_off_factory(monkeypatch, tmp_path)

    _reset_pragma_drift_sentinel_for_tests()

    db_connect()
    db_connect()
    db_connect()

    matching = [
        rec
        for rec in caplog.records
        if rec.name == "musicstreamer.repo"
        and rec.levelno == logging.WARNING
        and "PRAGMA foreign_keys is OFF after SET" in rec.getMessage()
    ]
    assert len(matching) == 1, (
        f"expected sentinel throttle to limit the drift-guard WARN to "
        f"exactly one record per session even across multiple db_connect() "
        f"calls; found {len(matching)} records: "
        f"{[rec.getMessage() for rec in caplog.records]}"
    )
