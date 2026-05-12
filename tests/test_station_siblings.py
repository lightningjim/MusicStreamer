"""Phase 71 / Wave 0 RED contract: pure helper + repo CRUD tests.

Modeled on tests/test_aa_siblings.py (one-assertion-per-test, _mk factory) and
tests/test_repo.py (repo fixture with PRAGMA foreign_keys = ON — mandatory for
CASCADE behavior per 71-RESEARCH.md Pitfall 6).

This module ASSERTS the contract Plans 71-01 / 71-02 will implement:

- musicstreamer.repo:
    Repo.add_sibling_link(a_id, b_id) -> None   (INSERT OR IGNORE; lo,hi normalize)
    Repo.remove_sibling_link(a_id, b_id) -> None
    Repo.list_sibling_links(station_id) -> list[int]
    db_init creates the station_siblings table:
      a_id INTEGER NOT NULL, b_id INTEGER NOT NULL,
      FOREIGN KEY(a_id, b_id) -> stations(id) ON DELETE CASCADE,
      UNIQUE(a_id, b_id), CHECK(a_id < b_id)

- musicstreamer.url_helpers:
    find_manual_siblings(stations, current_station_id, link_ids)
        -> list[tuple[provider_name_or_empty, station_id, station_name]]
    merge_siblings(aa_siblings, manual_siblings)
        -> list[tuple[...]]   (dedup by station_id; AA wins)

Per project convention (Phases 47/62/68/70) the module-level
`from musicstreamer.url_helpers import find_manual_siblings, merge_siblings`
import WILL FAIL at collection time today — that IS the RED state. No
`pytest.importorskip`, no `pytest.fail` placeholders.
"""
import sqlite3

import pytest

from musicstreamer.models import Station, StationStream
from musicstreamer.repo import Repo, db_init
from musicstreamer.url_helpers import find_manual_siblings, merge_siblings


# ---------------------------------------------------------------------------
# Factories / fixtures
# ---------------------------------------------------------------------------


def _mk(id_, name, provider_name=None, url="http://example.com/stream"):
    """Factory: a minimal Station with one StationStream.

    Extends tests/test_aa_siblings.py _mk by accepting `provider_name` —
    needed for find_manual_siblings tuple-shape assertions.
    """
    return Station(
        id=id_,
        name=name,
        provider_id=None,
        provider_name=provider_name,
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        streams=[StationStream(id=id_ * 10, station_id=id_, url=url, position=1)],
    )


@pytest.fixture
def repo(tmp_path):
    """Mirrors tests/test_repo.py fixture verbatim.

    PRAGMA foreign_keys = ON is mandatory — without it, CASCADE behavior
    fails silently (71-RESEARCH Pitfall 6).
    """
    con = sqlite3.connect(str(tmp_path / "test.db"))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    db_init(con)
    return Repo(con)


# ---------------------------------------------------------------------------
# Schema / migration tests (D-05, D-06, D-08)
# ---------------------------------------------------------------------------


def test_schema_create_with_check_unique_cascade(repo):
    """D-05: CHECK(a_id < b_id) rejects reversed (lo, hi) insert."""
    # Seed two stations so the FKs can resolve.
    repo.con.execute("INSERT INTO stations(id, name, tags) VALUES (1, 'A', '')")
    repo.con.execute("INSERT INTO stations(id, name, tags) VALUES (2, 'B', '')")
    repo.con.commit()
    with pytest.raises(sqlite3.IntegrityError):
        # CHECK(a_id < b_id) MUST reject (2, 1).
        repo.con.execute("INSERT INTO station_siblings(a_id, b_id) VALUES (2, 1)")
        repo.con.commit()


def test_db_init_idempotent_with_siblings_table(tmp_path):
    """D-06: db_init must be safely callable twice on the same connection."""
    con = sqlite3.connect(str(tmp_path / "test.db"))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    db_init(con)
    # Second call must not raise (CREATE TABLE IF NOT EXISTS idiom).
    db_init(con)


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


# ---------------------------------------------------------------------------
# Repo CRUD round-trip tests
# ---------------------------------------------------------------------------


def test_add_sibling_link_round_trip(repo):
    """add_sibling_link(1, 2) → list_sibling_links(1) returns [2]."""
    repo.con.execute("INSERT INTO stations(id, name, tags) VALUES (1, 'A', '')")
    repo.con.execute("INSERT INTO stations(id, name, tags) VALUES (2, 'B', '')")
    repo.con.commit()
    repo.add_sibling_link(1, 2)
    assert repo.list_sibling_links(1) == [2]


def test_add_sibling_link_idempotent(repo):
    """INSERT OR IGNORE: re-adding the same link does not raise and stays at 1 row."""
    repo.con.execute("INSERT INTO stations(id, name, tags) VALUES (1, 'A', '')")
    repo.con.execute("INSERT INTO stations(id, name, tags) VALUES (2, 'B', '')")
    repo.con.commit()
    repo.add_sibling_link(1, 2)
    repo.add_sibling_link(1, 2)  # MUST NOT raise
    count = repo.con.execute(
        "SELECT COUNT(*) AS c FROM station_siblings"
    ).fetchone()["c"]
    assert count == 1


def test_add_sibling_link_normalizes_order(repo):
    """add_sibling_link(2, 1) MUST store (a_id=1, b_id=2) and be queryable from either end."""
    repo.con.execute("INSERT INTO stations(id, name, tags) VALUES (1, 'A', '')")
    repo.con.execute("INSERT INTO stations(id, name, tags) VALUES (2, 'B', '')")
    repo.con.commit()
    repo.add_sibling_link(2, 1)  # reversed input
    row = repo.con.execute(
        "SELECT a_id, b_id FROM station_siblings"
    ).fetchone()
    assert (row["a_id"], row["b_id"]) == (1, 2)
    # And the symmetric query from the "larger" id still finds the partner.
    assert repo.list_sibling_links(2) == [1]


def test_remove_sibling_link(repo):
    """add then remove → list_sibling_links returns []."""
    repo.con.execute("INSERT INTO stations(id, name, tags) VALUES (1, 'A', '')")
    repo.con.execute("INSERT INTO stations(id, name, tags) VALUES (2, 'B', '')")
    repo.con.commit()
    repo.add_sibling_link(1, 2)
    repo.remove_sibling_link(1, 2)
    assert repo.list_sibling_links(1) == []


def test_remove_sibling_link_noop_when_absent(repo):
    """remove_sibling_link on an empty table MUST NOT raise (silent no-op)."""
    repo.con.execute("INSERT INTO stations(id, name, tags) VALUES (1, 'A', '')")
    repo.con.execute("INSERT INTO stations(id, name, tags) VALUES (2, 'B', '')")
    repo.con.commit()
    repo.remove_sibling_link(1, 2)  # MUST NOT raise


def test_list_sibling_links_symmetric(repo):
    """UNION query: a link inserted as (1, 2) must be visible from BOTH endpoints."""
    repo.con.execute("INSERT INTO stations(id, name, tags) VALUES (1, 'A', '')")
    repo.con.execute("INSERT INTO stations(id, name, tags) VALUES (2, 'B', '')")
    repo.con.commit()
    repo.add_sibling_link(1, 2)
    assert repo.list_sibling_links(1) == [2]
    assert repo.list_sibling_links(2) == [1]


# ---------------------------------------------------------------------------
# Pure helper tests — find_manual_siblings
# ---------------------------------------------------------------------------


def test_find_manual_siblings_tuple_shape():
    """find_manual_siblings returns list[tuple[provider_name_str, station_id_int, station_name_str]]."""
    a = _mk(1, "Self", provider_name="ProviderA")
    b = _mk(2, "Partner", provider_name="ProviderB")
    result = find_manual_siblings([a, b], current_station_id=1, link_ids=[2])
    assert result == [("ProviderB", 2, "Partner")]


def test_find_manual_siblings_excludes_self():
    """Defensive: current_station_id never appears in result, even if listed in link_ids."""
    a = _mk(1, "Self", provider_name="ProviderA")
    b = _mk(2, "Partner", provider_name="ProviderB")
    # link_ids includes current_station_id (defensive against caller bugs).
    result = find_manual_siblings([a, b], current_station_id=1, link_ids=[1, 2])
    ids = [t[1] for t in result]
    assert 1 not in ids


def test_find_manual_siblings_sorts_alphabetically():
    """Three stations linked in arbitrary order; result is alphabetical (casefold) by name."""
    current = _mk(1, "Current", provider_name="P")
    bb = _mk(2, "B Station", provider_name="P")
    aa = _mk(3, "A Station", provider_name="P")
    cc = _mk(4, "C Station", provider_name="P")
    result = find_manual_siblings(
        [current, bb, aa, cc], current_station_id=1, link_ids=[2, 3, 4]
    )
    names = [t[2] for t in result]
    assert names == ["A Station", "B Station", "C Station"]


# ---------------------------------------------------------------------------
# Pure helper tests — merge_siblings
# ---------------------------------------------------------------------------


def test_merge_siblings_dedup_by_station_id():
    """If the same station_id appears in both aa_list and manual_list, AA wins.

    Per 71-RESEARCH Q2: dedup key is station_id; AA entry takes precedence
    (so the entry surfaces as an AA chip with no × per D-15).
    """
    aa_list = [("zenradio", 42, "Ambient")]
    manual_list = [("SomaFM", 42, "Ambient")]   # same station_id 42, different first element
    merged = merge_siblings(aa_list, manual_list)
    assert merged == [("zenradio", 42, "Ambient")]
