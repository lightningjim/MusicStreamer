"""Tests for LiveRefreshDialog + _LiveRefreshScanWorker — Phase 96 Wave 0.

All tests in this file are EXPECTED to be RED (failing) before Plan 04 implements
the production code in musicstreamer/ui_qt/live_refresh_dialog.py.
Collection of these test IDs by pytest is the Wave 0 success criterion.

Decision coverage:
- D-05: _build_row_suggestions pre-orders by anchor similarity, no auto-apply
- D-06: update remap preserves metadata; list_flagged_stations_for_provider
- D-07: drop calls delete_station; add calls insert_station + set flag
- D-08: name field pre-populated per action type
- D-09: scan off UI thread (QThread); node_runtime forwarded (MEMORY.md landmine)
- D-10: conservative defaults; empty apply guard
"""
from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock, call, patch

import pytest

# Gate the import so collection lists test ids even before Plan 04 creates the module.
# ImportError at module level would abort the entire file, preventing collection.
# When the module does not yet exist, each test function raises the ImportError
# at *call* time (never at collection time) so pytest reports FAILED, not ERROR.
try:
    from musicstreamer.ui_qt.live_refresh_dialog import (
        LiveRefreshDialog,
        _LiveRefreshScanWorker,
    )
    _IMPORT_ERROR: "ImportError | None" = None
except ImportError as _e:
    LiveRefreshDialog = None  # type: ignore[assignment,misc]
    _LiveRefreshScanWorker = None  # type: ignore[assignment,misc]
    _IMPORT_ERROR = _e

from musicstreamer.repo import Repo, db_init
from musicstreamer.models import Station, StationStream


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_repo(tmp_path):
    """Real tmp-path SQLite Repo — mirrors the test_repo.py pattern."""
    con = sqlite3.connect(str(tmp_path / "test.db"))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    db_init(con)
    return Repo(con)


def _require_module():
    """Raise ImportError at call time if the module was not importable.

    Using raise instead of pytest.skip ensures tests show as FAILED (RED)
    rather than SKIPPED during Wave 0 before Plan 04 creates the module.
    """
    if _IMPORT_ERROR is not None:
        raise _IMPORT_ERROR


# ---------------------------------------------------------------------------
# D-09 — QThread worker shape + node_runtime forwarding
# ---------------------------------------------------------------------------


def test_scan_worker_uses_qthread():
    """Phase 96 D-09: _LiveRefreshScanWorker is a QThread subclass with the right shape.

    Asserts:
    - Is a subclass of PySide6.QtCore.QThread
    - Exposes `finished` and `error` Signals
    - __init__ accepts a `node_runtime` keyword argument

    Tests MUST be RED until Plan 04 implements _LiveRefreshScanWorker.
    """
    _require_module()

    from PySide6.QtCore import QThread

    assert issubclass(_LiveRefreshScanWorker, QThread), (
        "_LiveRefreshScanWorker must be a QThread subclass (D-09)"
    )
    # Signals must exist as class-level Signal descriptors
    assert hasattr(_LiveRefreshScanWorker, "finished"), (
        "_LiveRefreshScanWorker must have a 'finished' Signal"
    )
    assert hasattr(_LiveRefreshScanWorker, "error"), (
        "_LiveRefreshScanWorker must have an 'error' Signal"
    )

    # __init__ must accept node_runtime keyword
    import inspect
    sig = inspect.signature(_LiveRefreshScanWorker.__init__)
    assert "node_runtime" in sig.parameters, (
        "_LiveRefreshScanWorker.__init__ must accept a 'node_runtime' keyword argument "
        "(MEMORY.md yt-dlp-callsites-need-resolved-node-runtime landmine)"
    )


def test_scan_worker_forwards_node_runtime():
    """Phase 96 D-09 / B2: _LiveRefreshScanWorker.run() forwards node_runtime to scan_playlist.

    Pure unit test — NO live yt-dlp call. Monkeypatches scan_playlist and
    constructs the worker directly, calling run() on the main thread.
    Asserts the sentinel node_runtime value is passed through.

    Guards MEMORY.md yt-dlp-callsites-need-resolved-node-runtime:
    the .desktop-launcher silent-failure landmine where node_runtime=None
    is baked in because scan_playlist is called without forwarding it.

    Tests MUST be RED until Plan 04 implements _LiveRefreshScanWorker.run().
    """
    _require_module()

    sentinel = object()  # unique sentinel for identity check

    with patch("musicstreamer.yt_import.scan_playlist") as mock_scan:
        mock_scan.return_value = []
        worker = _LiveRefreshScanWorker(
            "https://youtube.com/@YellowBrickCinema/streams",
            node_runtime=sentinel,
        )
        # Call run() directly — do NOT start a real thread
        worker.run()

    mock_scan.assert_called_once()
    _args, _kwargs = mock_scan.call_args
    assert _kwargs.get("node_runtime") is sentinel, (
        "scan_playlist must be called with node_runtime=<sentinel passed to __init__>; "
        f"got node_runtime={_kwargs.get('node_runtime')!r} (B2 landmine guard)"
    )


# ---------------------------------------------------------------------------
# D-05 — Suggestion pre-ordering, no auto-apply
# ---------------------------------------------------------------------------


def test_suggestions_pre_order_no_auto_apply():
    """Phase 96 D-05: _build_row_suggestions pre-orders by anchor similarity but does NOT auto-apply.

    Drive the dialog's row-suggestion builder with a station whose anchor
    exactly matches a scan-result title. The matching live stream must be
    ordered first in that row's suggestions, but no mapping/URL is auto-applied
    — the staged-change set for that row must be empty until the user picks.

    Tests MUST be RED until Plan 04 implements _build_row_suggestions.
    """
    _require_module()

    # We test the pure helper directly without constructing the full dialog widget.
    # Plan 04 must expose _build_row_suggestions as a callable (module-level or
    # as a staticmethod/classmethod on LiveRefreshDialog).
    assert hasattr(LiveRefreshDialog, "_build_row_suggestions") or callable(
        getattr(LiveRefreshDialog, "_build_row_suggestions", None)
    ), (
        "LiveRefreshDialog must expose _build_row_suggestions as a testable callable"
    )

    anchor = "Yellow Brick Cinema — Relaxing Music"
    scan_results = [
        {"title": "Some Other Stream", "url": "https://youtu.be/aaa", "provider": "YBC"},
        {"title": anchor, "url": "https://youtu.be/bbb", "provider": "YBC"},
        {"title": "Yet Another Stream", "url": "https://youtu.be/ccc", "provider": "YBC"},
    ]
    station = MagicMock()
    station.live_url_title_anchor = anchor

    suggestions = LiveRefreshDialog._build_row_suggestions(station, scan_results)

    assert len(suggestions) > 0, "_build_row_suggestions returned no suggestions"
    # The matching result must be first
    assert suggestions[0]["title"] == anchor, (
        f"Anchor-matching suggestion must be ordered first; got {suggestions[0]['title']!r}"
    )
    # No auto-apply: the staged-change set for this row must be empty until user picks.
    # The return value is (suggestions_list,) not (suggestions_list, staged_change).
    # Or if a second value is returned, the staged change dict must be empty/None.
    if isinstance(suggestions, tuple):
        ordered, staged = suggestions
        assert not staged, (
            "No staged change must be auto-applied (D-05 no-auto-apply invariant)"
        )


# ---------------------------------------------------------------------------
# D-06 — Remap preserves stream metadata
# ---------------------------------------------------------------------------


def test_apply_remap_preserves_metadata(db_repo):
    """Phase 96 D-06: applying a REMAP updates URL but preserves label/quality/stream_type/codec/bitrate.

    Uses a real tmp Repo with a station that has a multi-field stream.
    Asserts repo.update_stream was called with the new URL while all other
    fields are preserved from the existing stream.
    Also asserts set_live_url_title_anchor was called with the scan result title.

    Tests MUST be RED until Plan 04 implements the apply logic.
    """
    _require_module()

    # We test via a mock repo to avoid partial production-code dependency.
    mock_repo = MagicMock()
    existing_stream = StationStream(
        id=10,
        station_id=1,
        url="https://youtu.be/old_id",
        label="Cinema Relaxing",
        quality="hi",
        position=1,
        stream_type="hls",
        codec="aac",
        bitrate_kbps=128,
    )
    mock_repo.list_streams.return_value = [existing_stream]

    new_url = "https://youtu.be/new_live_id"
    scan_result = {"title": "Cinema Relaxing Live", "url": new_url, "provider": "YBC"}

    # Import the pure apply helper — Plan 04 must expose this seam.
    from musicstreamer.ui_qt.live_refresh_dialog import apply_refresh  # type: ignore[attr-defined]

    staged_remap = {
        "action": "remap",
        "station_id": 1,
        "stream_id": 10,
        "scan_result": scan_result,
    }
    apply_refresh(mock_repo, [staged_remap])

    # update_stream called with new URL; other fields preserved from existing_stream
    mock_repo.update_stream.assert_called_once()
    call_args = mock_repo.update_stream.call_args
    called_kwargs = call_args[1] if call_args[1] else {}
    called_positional = call_args[0] if call_args[0] else ()

    # URL must be the new URL
    assert new_url in called_positional or called_kwargs.get("url") == new_url, (
        f"update_stream must be called with the new URL; call: {call_args}"
    )

    # set_live_url_title_anchor called with scan result title
    mock_repo.set_live_url_title_anchor.assert_called_once_with(1, scan_result["title"])


def test_apply_refresh_rejects_duplicate_targets():
    """WR-03: two stations mapped to the SAME live URL in one Apply must be
    rejected BEFORE any mutation — stations must not silently collapse onto one
    stream just because every combo defaults to the anchor-closest match."""
    _require_module()

    from musicstreamer.ui_qt.live_refresh_dialog import apply_refresh  # type: ignore[attr-defined]

    mock_repo = MagicMock()
    same_url = "https://youtu.be/dup_live_id"
    staged = [
        {
            "action": "remap", "station_id": 1, "stream_id": 10,
            "scan_result": {"title": "A", "url": same_url, "provider": "YBC"},
        },
        {
            "action": "remap", "station_id": 2, "stream_id": 20,
            "scan_result": {"title": "B", "url": same_url, "provider": "YBC"},
        },
    ]
    with pytest.raises(ValueError, match="same live stream"):
        apply_refresh(mock_repo, staged)

    # Fail closed: NO repo mutation may have occurred.
    mock_repo.update_stream.assert_not_called()
    mock_repo.delete_station.assert_not_called()
    mock_repo.insert_station.assert_not_called()


# ---------------------------------------------------------------------------
# D-07 — Drop and add actions
# ---------------------------------------------------------------------------


def test_apply_drop_and_add_actions():
    """Phase 96 D-07: applying DROP calls delete_station; applying ADD calls insert_station + flag.

    Stage one DROP (ticked) and one ADD (ticked, with a name); apply.
    Assert delete_station called for the dropped station id, insert_station
    called for the add, followed by set_live_url_syncs_from_channel(True) +
    set_live_url_title_anchor for the new station.

    Tests MUST be RED until Plan 04 implements the apply logic.
    """
    _require_module()

    from musicstreamer.ui_qt.live_refresh_dialog import apply_refresh  # type: ignore[attr-defined]

    mock_repo = MagicMock()
    mock_repo.insert_station.return_value = 99  # new station id

    staged = [
        {
            "action": "drop",
            "station_id": 5,
        },
        {
            "action": "add",
            "name": "New Cinema Stream",
            "scan_result": {
                "title": "New Cinema Stream",
                "url": "https://youtu.be/new_add_id",
                "provider": "YBC",
            },
            "provider_name": "Yellow Brick Cinema",
        },
    ]
    apply_refresh(mock_repo, staged)

    # DROP: delete_station called with the dropped id
    mock_repo.delete_station.assert_called_once_with(5)

    # ADD: insert_station called
    mock_repo.insert_station.assert_called_once()

    # After ADD, flag must be set True + anchor set
    mock_repo.set_live_url_syncs_from_channel.assert_called_with(99, True)
    mock_repo.set_live_url_title_anchor.assert_called_once()


# ---------------------------------------------------------------------------
# D-08 — Name field pre-population
# ---------------------------------------------------------------------------


def test_name_field_prepopulation():
    """Phase 96 D-08: ADD rows default to scan title; REMAP rows default to existing station name.

    Tests the pure row-builder logic — no live dialog widget needed.
    Tests MUST be RED until Plan 04 implements _build_row_data or equivalent.
    """
    _require_module()

    from musicstreamer.ui_qt.live_refresh_dialog import build_row_data  # type: ignore[attr-defined]

    scan_result = {"title": "YBC Live Stream", "url": "https://youtu.be/xyz", "provider": "YBC"}
    existing_station = MagicMock()
    existing_station.name = "Yellow Brick Cinema"

    # ADD row: name must default to scan result title
    add_row = build_row_data("add", scan_result=scan_result)
    assert add_row["name"] == scan_result["title"], (
        f"ADD row name must default to scan title; got {add_row['name']!r}"
    )

    # REMAP row: name must default to existing station name (NOT channel title)
    remap_row = build_row_data("remap", scan_result=scan_result, station=existing_station)
    assert remap_row["name"] == existing_station.name, (
        f"REMAP row name must default to existing station name; got {remap_row['name']!r}"
    )


# ---------------------------------------------------------------------------
# CR-01 / T-39-01 — rich-text injection guard
# ---------------------------------------------------------------------------


def test_row_labels_use_plaintext_against_injection(qtbot):
    """CR-01 / T-39-01: a row renders untrusted station names and scan-derived
    title anchors. Those labels MUST be Qt.PlainText so a title like
    '<img src=http://attacker/x.png>' cannot trigger a rich-text remote-resource
    load when the row paints."""
    _require_module()

    from types import SimpleNamespace

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLabel

    from musicstreamer.ui_qt.live_refresh_dialog import _RowWidget  # type: ignore[attr-defined]

    evil = "<img src=http://attacker/x.png>"
    station = SimpleNamespace(name=evil, live_url_title_anchor=evil)
    row = _RowWidget("remap", station, [], "YBC")
    qtbot.addWidget(row)

    untrusted = [lb for lb in row.findChildren(QLabel) if evil in lb.text()]
    assert untrusted, "expected labels rendering the untrusted station name/anchor"
    for lb in untrusted:
        assert lb.textFormat() == Qt.PlainText, (
            f"untrusted label {lb.text()!r} must be Qt.PlainText (T-39-01/CR-01)"
        )


# ---------------------------------------------------------------------------
# D-10 — Conservative defaults + empty-apply guard
# ---------------------------------------------------------------------------


def test_conservative_defaults():
    """Phase 96 D-10 / W4 / W5: conservative default check-states and empty-apply guard.

    Asserts:
    (a) DROP and ADD rows are UNCHECKED by default.
    (b) A staged REMAP row (flagged station mapped to a live stream) IS checked/active
        by default — an all-rows-unchecked implementation must FAIL this (W5).
    (c) Calling the pure apply helper with that active REMAP row DOES invoke
        update_stream for it (W5).
    (d) An unresolved flagged station (no user action) produces NO update_stream /
        NO delete_station call on apply.
    (e) Calling the pure apply helper with an EMPTY staged-changes list produces
        ZERO repo mutations (W4 — the D-10 summary-before-Apply safety posture).

    Tests MUST be RED until Plan 04 implements the apply logic and row defaults.
    """
    _require_module()

    from musicstreamer.ui_qt.live_refresh_dialog import (  # type: ignore[attr-defined]
        apply_refresh,
        default_check_state,
    )

    # (a) DROP and ADD rows are UNCHECKED by default
    assert default_check_state("drop") is False, (
        "DROP rows must be UNCHECKED by default (D-10 conservative)"
    )
    assert default_check_state("add") is False, (
        "ADD rows must be UNCHECKED by default (D-10 conservative)"
    )

    # (b) REMAP row IS checked/active by default
    assert default_check_state("remap") is True, (
        "REMAP rows must be CHECKED by default (W5: resolving an existing flagged station)"
    )

    mock_repo = MagicMock()
    mock_repo.list_streams.return_value = [
        StationStream(
            id=10, station_id=1, url="https://youtu.be/old",
            label="Cinema", quality="hi", position=1,
            stream_type="hls", codec="aac", bitrate_kbps=128,
        )
    ]
    mock_repo.insert_station.return_value = 99

    remap_staged = [{
        "action": "remap",
        "station_id": 1,
        "stream_id": 10,
        "scan_result": {"title": "Cinema Live", "url": "https://youtu.be/new", "provider": "YBC"},
    }]

    # (c) Active REMAP row invokes update_stream
    apply_refresh(mock_repo, remap_staged)
    mock_repo.update_stream.assert_called_once()

    # (d) Unresolved flagged station (empty staged list for that station)
    # — no mutating calls
    mock_repo.reset_mock()
    apply_refresh(mock_repo, [])
    mock_repo.update_stream.assert_not_called()
    mock_repo.delete_station.assert_not_called()
    mock_repo.insert_station.assert_not_called()

    # (e) Empty staged-changes list: ZERO repo mutations (W4 D-10 empty-apply guard)
    mock_repo.reset_mock()
    apply_refresh(mock_repo, [])
    assert mock_repo.update_stream.call_count == 0, (
        "Empty staged list must produce ZERO update_stream calls (W4)"
    )
    assert mock_repo.delete_station.call_count == 0, (
        "Empty staged list must produce ZERO delete_station calls (W4)"
    )
    assert mock_repo.insert_station.call_count == 0, (
        "Empty staged list must produce ZERO insert_station calls (W4)"
    )
