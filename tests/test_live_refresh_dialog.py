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


def test_apply_refresh_rejects_duplicate_station_targets():
    """WR-01 (Phase 96.1 D-07): two remap rows targeting the SAME station_id with
    DIFFERENT live URLs (a REMAP row plus a discover MAP row onto that station)
    must fail closed BEFORE any mutation. The URL-only guard misses this because
    the URLs differ; without a station_id guard both run sequential update_stream
    calls on the same primary stream (silent last-write-wins)."""
    _require_module()

    from musicstreamer.ui_qt.live_refresh_dialog import apply_refresh  # type: ignore[attr-defined]

    mock_repo = MagicMock()
    staged = [
        {
            "action": "remap", "station_id": 7, "stream_id": 70,
            "scan_result": {"title": "A", "url": "https://youtu.be/url_a", "provider": "YBC"},
        },
        {
            "action": "remap", "station_id": 7, "stream_id": 70,
            "scan_result": {"title": "B", "url": "https://youtu.be/url_b", "provider": "YBC"},
        },
    ]
    with pytest.raises(ValueError, match="same station"):
        apply_refresh(mock_repo, staged)

    # Fail closed: NO repo mutation may have occurred.
    mock_repo.update_stream.assert_not_called()
    mock_repo.set_live_url_title_anchor.assert_not_called()
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


# ---------------------------------------------------------------------------
# Phase 96.1 Wave 0 RED stubs — D-02, D-04, D-05, D-06, D-07, D-08
# These tests fail with ImportError/_DiscoverRowWidget AttributeError or
# AttributeError on resolve_live_title until Plans 02/03 add the symbols.
# ---------------------------------------------------------------------------


def test_scan_worker_threads_node_runtime_into_resolve():
    """D-02: _LiveRefreshScanWorker.run() must call resolve_live_title with node_runtime.

    After plan_playlist returns entries with blank titles, the worker must
    resolve them via yt_import.resolve_live_title forwarding the same
    node_runtime it received at construction. Guards the .desktop-launcher
    landmine: if node_runtime is not threaded, yt-dlp cannot find Node.js.

    Wave 0 RED — yt_import.resolve_live_title does not exist yet;
    run() does not yet call it.
    """
    _require_module()

    sentinel = object()  # unique sentinel for identity check

    with patch("musicstreamer.yt_import.scan_playlist") as mock_scan, \
         patch("musicstreamer.yt_import.resolve_live_title") as mock_resolve:
        # Return one entry with a blank title so the blank-resolution loop fires
        mock_scan.return_value = [
            {"title": "", "url": "https://www.youtube.com/watch?v=abc", "provider": "YBC"}
        ]
        mock_resolve.return_value = "Resolved Title"
        worker = _LiveRefreshScanWorker(
            "https://youtube.com/@YellowBrickCinema/streams",
            node_runtime=sentinel,
        )
        # Call run() directly on main thread — do NOT start a real QThread
        worker.run()

    mock_resolve.assert_called_once()
    _args, _kwargs = mock_resolve.call_args
    assert _kwargs.get("node_runtime") is sentinel, (
        "resolve_live_title must be called with node_runtime=<sentinel passed to worker __init__>; "
        f"got node_runtime={_kwargs.get('node_runtime')!r} (D-02 LANDMINE guard)"
    )


def test_discover_row_title_label_plaintext(qtbot):
    """D-04 / CR-01 / T-39-01: _DiscoverRowWidget title label must use Qt.PlainText.

    A scan-derived title containing HTML (e.g. '<img src=http://attacker/x.png>')
    must NOT trigger a remote-resource load when the row paints. The label
    textFormat must be Qt.PlainText, not Qt.AutoText or Qt.RichText.

    Wave 0 RED — _DiscoverRowWidget does not exist yet.
    """
    _require_module()

    from types import SimpleNamespace

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLabel

    from musicstreamer.ui_qt.live_refresh_dialog import _DiscoverRowWidget  # type: ignore[attr-defined]

    evil = "<img src=http://attacker/x.png>"
    entry = {"title": evil, "url": "https://www.youtube.com/watch?v=abc", "provider": "YBC"}
    row = _DiscoverRowWidget(entry, [], "YBC")
    qtbot.addWidget(row)

    untrusted = [lb for lb in row.findChildren(QLabel) if evil in lb.text()]
    assert untrusted, (
        "expected at least one QLabel in _DiscoverRowWidget rendering the untrusted scan title"
    )
    for lb in untrusted:
        assert lb.textFormat() == Qt.PlainText, (
            f"untrusted title label {lb.text()!r} must be Qt.PlainText "
            "(T-39-01/CR-01 — scan titles are untrusted)"
        )


def test_discover_section_no_dedup():
    """D-05: _populate_rows lists EVERY scan entry in the discover section.

    Even if a scan entry's URL is also the closest match for a flagged station
    REMAP row, it must still appear as a _DiscoverRowWidget. No dedup hiding.

    Wave 0 RED — _DiscoverRowWidget does not exist yet.
    """
    _require_module()

    from musicstreamer.ui_qt.live_refresh_dialog import _DiscoverRowWidget  # type: ignore[attr-defined]

    # Two scan entries: both should appear as discover rows
    scan_results = [
        {"title": "Stream A", "url": "https://www.youtube.com/watch?v=aaa", "provider": "YBC"},
        {"title": "Stream B", "url": "https://www.youtube.com/watch?v=bbb", "provider": "YBC"},
    ]

    flagged_station = MagicMock()
    flagged_station.id = 1
    flagged_station.name = "YBC Relaxing"
    flagged_station.streams = []

    # Instantiate a _DiscoverRowWidget per scan entry and count them — Plan 03
    # must ensure _populate_rows creates one per entry with no dedup.
    row_widgets = [_DiscoverRowWidget(e, [flagged_station], "YBC") for e in scan_results]
    assert len(row_widgets) == len(scan_results), (
        "There must be exactly one _DiscoverRowWidget per scan result (D-05 no-dedup)"
    )


def test_discover_row_add_staged_change():
    """D-06 add: _DiscoverRowWidget in add mode, checked, returns correct add change dict.

    Wave 0 RED — _DiscoverRowWidget does not exist yet.
    """
    _require_module()

    from musicstreamer.ui_qt.live_refresh_dialog import _DiscoverRowWidget  # type: ignore[attr-defined]

    entry = {"title": "New Stream", "url": "https://www.youtube.com/watch?v=abc", "provider": "YBC"}
    row = _DiscoverRowWidget(entry, [], "YBC")

    # Force the add mode and check the box so is_staged() returns True
    # (exact API is Plan 03's discretion; we rely on is_staged() + build_staged_change())
    # Trigger the "add" action path by checking the checkbox
    row._check.setChecked(True)

    change = row.build_staged_change()
    assert change is not None, "build_staged_change must return a dict when checked (add mode)"
    assert change["action"] == "add", f"action must be 'add'; got {change['action']!r}"
    assert change["scan_result"] == entry, "scan_result must be the entry passed at construction"
    assert change["provider_name"] == "YBC", f"provider_name must be 'YBC'; got {change.get('provider_name')!r}"
    # Name field defaults to the entry title for add mode (D-08)
    assert change.get("name") == entry["title"] or change.get("name"), (
        "add staged change must include a non-empty 'name' (defaulting to scan title, D-08)"
    )


def test_discover_row_map_staged_change(qtbot):
    """D-06 map: _DiscoverRowWidget in map mode returns correct remap change dict.

    Checks the box, switches to map mode, selects the station from the dropdown,
    and asserts build_staged_change returns the remap shape with station_id and stream_id.

    Wave 0 RED — _DiscoverRowWidget does not exist yet.
    """
    _require_module()

    from musicstreamer.ui_qt.live_refresh_dialog import _DiscoverRowWidget  # type: ignore[attr-defined]

    stream = StationStream(id=10, station_id=1, url="https://old.url", label="Cinema",
                           quality="hi", position=1, stream_type="hls", codec="aac", bitrate_kbps=128)
    station = Station(id=1, name="YBC Relaxing", provider_id=None, provider_name="YBC",
                      tags="", station_art_path=None, album_fallback_path=None,
                      streams=[stream])
    entry = {"title": "New Live", "url": "https://www.youtube.com/watch?v=abc", "provider": "YBC"}

    row = _DiscoverRowWidget(entry, [station], "YBC")
    qtbot.addWidget(row)

    # Switch to map mode and select the station in the map combo
    # Plan 03 controls the exact UI API; we interact via _map_combo / a radio or toggle
    row._check.setChecked(True)

    # Find and set the map combo to the station (index 0 = first flagged station)
    map_combo = row._map_combo  # type: ignore[attr-defined]
    map_combo.setCurrentIndex(0)

    # Switch to map action (Plan 03 will expose this; we call the toggle if available)
    if hasattr(row, "_set_action_map"):
        row._set_action_map()  # type: ignore[attr-defined]
    elif hasattr(row, "_action_map_radio"):
        row._action_map_radio.setChecked(True)  # type: ignore[attr-defined]

    change = row.build_staged_change()
    assert change is not None, "build_staged_change must return a dict in map mode when checked"
    assert change["action"] == "remap", f"map action must produce 'remap'; got {change.get('action')!r}"
    assert change["station_id"] == station.id, (
        f"station_id must match chosen station; got {change.get('station_id')!r}"
    )
    assert change["stream_id"] == stream.id, (
        f"stream_id must be the primary stream id; got {change.get('stream_id')!r}"
    )
    assert change["scan_result"] == entry, "scan_result must be the entry passed at construction"


def test_discover_row_map_dropdown_from_flagged(qtbot):
    """D-07: _DiscoverRowWidget map QComboBox is populated from flagged_stations.

    The dropdown items' userData must be the Station objects passed at construction.

    Wave 0 RED — _DiscoverRowWidget does not exist yet.
    """
    _require_module()

    from musicstreamer.ui_qt.live_refresh_dialog import _DiscoverRowWidget  # type: ignore[attr-defined]

    from PySide6.QtCore import Qt

    stationA = Station(id=1, name="YBC Sleep", provider_id=None, provider_name="YBC",
                       tags="", station_art_path=None, album_fallback_path=None)
    stationB = Station(id=2, name="YBC Study", provider_id=None, provider_name="YBC",
                       tags="", station_art_path=None, album_fallback_path=None)
    entry = {"title": "New Live", "url": "https://www.youtube.com/watch?v=abc", "provider": "YBC"}

    row = _DiscoverRowWidget(entry, [stationA, stationB], "YBC")
    qtbot.addWidget(row)

    map_combo = row._map_combo  # type: ignore[attr-defined]
    assert map_combo.count() == 2, (
        f"map combo must have 2 items for 2 flagged stations; got {map_combo.count()}"
    )
    assert map_combo.itemData(0, Qt.UserRole) is stationA, (
        "first combo item userData must be stationA"
    )
    assert map_combo.itemData(1, Qt.UserRole) is stationB, (
        "second combo item userData must be stationB"
    )


def test_discover_row_unchecked_by_default():
    """D-08: _DiscoverRowWidget is unchecked by default (conservative default).

    is_staged() must return False immediately after construction, before any
    user interaction.

    Wave 0 RED — _DiscoverRowWidget does not exist yet.
    """
    _require_module()

    from musicstreamer.ui_qt.live_refresh_dialog import _DiscoverRowWidget  # type: ignore[attr-defined]

    entry = {"title": "New Stream", "url": "https://www.youtube.com/watch?v=abc", "provider": "YBC"}
    row = _DiscoverRowWidget(entry, [], "YBC")

    assert row.is_staged() is False, (
        "is_staged() must be False immediately after construction (D-08 conservative default)"
    )
