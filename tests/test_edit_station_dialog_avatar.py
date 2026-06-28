"""Wave 0 RED tests for _AvatarFetchWorker dispatch (Phase 89b Plan 02).

Tests:
- test_twitch_url_enables_refresh_btn: twitch.tv URL enables the Refresh-avatar button
- test_avatar_worker_dispatches_twitch: worker dispatch picks twitch fetcher for twitch.tv URL
- test_youtube_dispatch_passes_node_runtime: youtube URL routes to youtube fetcher + node_runtime forwarded

Run with: .venv/bin/python -m pytest tests/test_edit_station_dialog_avatar.py -q
"""
from unittest.mock import MagicMock, call, patch

import inspect
import pytest

from musicstreamer.models import Provider, Station, StationStream
from musicstreamer.ui_qt.edit_station_dialog import _COL_URL


# ---------------------------------------------------------------------------
# Fixtures — mirror test_edit_station_dialog.py harness
# ---------------------------------------------------------------------------


@pytest.fixture()
def station_with_provider():
    """Station that already has a provider_id (required for avatar fetch)."""
    return Station(
        id=1,
        name="TwitchDev FM",
        provider_id=7,
        provider_name="Twitch: twitchdev",
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        icy_disabled=True,
        provider_avatar_path=None,
    )


@pytest.fixture()
def repo():
    r = MagicMock()
    r.list_stations.return_value = []
    r.list_providers.return_value = [
        Provider(1, "TestProvider"),
        Provider(7, "Twitch: twitchdev"),
    ]
    r.list_streams.return_value = [
        StationStream(id=10, station_id=1, url="http://s1.mp3",
                      label="", quality="hi", position=1,
                      stream_type="", codec="MP3"),
    ]
    r.ensure_provider.return_value = 7
    return r


@pytest.fixture()
def player():
    p = MagicMock()
    p._current_station_name = ""
    return p


@pytest.fixture()
def twitch_dialog(qtbot, station_with_provider, player, repo):
    from musicstreamer.ui_qt.edit_station_dialog import EditStationDialog
    d = EditStationDialog(station_with_provider, player, repo, parent=None)
    qtbot.addWidget(d)
    return d


# ---------------------------------------------------------------------------
# Test 1: twitch.tv URL enables the Refresh-avatar button
# ---------------------------------------------------------------------------


def test_twitch_url_enables_refresh_btn(twitch_dialog):
    """After setting the canonical streams-table URL cell to a twitch.tv URL and firing
    _on_canonical_cell_changed, _refresh_avatar_btn.isEnabled() is True.

    Also verifies:
    - a YouTube URL also enables it (regression guard)
    - an unrelated URL disables it
    """
    d = twitch_dialog

    # Twitch URL should enable refresh
    d.streams_table.item(d._canonical_row, _COL_URL).setText("https://www.twitch.tv/twitchdev")
    d._on_canonical_cell_changed(d._canonical_row, _COL_URL)
    assert d._refresh_avatar_btn.isEnabled() is True, (
        "Refresh button should be enabled for twitch.tv URL — "
        "dispatch gate not yet added to _on_canonical_cell_changed"
    )

    # YouTube URL should still enable refresh (regression guard)
    d.streams_table.item(d._canonical_row, _COL_URL).setText("https://www.youtube.com/@lofiirl")
    d._on_canonical_cell_changed(d._canonical_row, _COL_URL)
    assert d._refresh_avatar_btn.isEnabled() is True, (
        "Refresh button should remain enabled for youtube.com URL"
    )

    # Unrelated URL should disable refresh
    d.streams_table.item(d._canonical_row, _COL_URL).setText("http://stream.example.com/live.mp3")
    d._on_canonical_cell_changed(d._canonical_row, _COL_URL)
    assert d._refresh_avatar_btn.isEnabled() is False, (
        "Refresh button should be disabled for non-avatar-capable URL"
    )


# ---------------------------------------------------------------------------
# Test 2: _AvatarFetchWorker dispatches to twitch fetcher (not YouTube)
# ---------------------------------------------------------------------------


def test_avatar_worker_dispatches_twitch():
    """_AvatarFetchWorker.run() dispatches through get_avatar_fetcher("twitch")
    for a twitch.tv URL, and does NOT call the YouTube fetcher directly.

    Source-grep drift-guard: assert run() source contains 'get_avatar_fetcher'
    and no longer hard-codes 'fetch_channel_avatar(self._url'.
    """
    from musicstreamer.ui_qt.edit_station_dialog import _AvatarFetchWorker
    from musicstreamer import yt_import

    # --- Source-grep drift-guard ---
    run_src = inspect.getsource(_AvatarFetchWorker.run)
    assert "get_avatar_fetcher" in run_src, (
        "Drift-guard: _AvatarFetchWorker.run() must dispatch via "
        "yt_import.get_avatar_fetcher(...). Not yet implemented."
    )
    assert "fetch_channel_avatar(self._url" not in run_src, (
        "Drift-guard: _AvatarFetchWorker.run() still hard-codes the YouTube "
        "fetch_channel_avatar(self._url, ...) call — remove this and dispatch "
        "through get_avatar_fetcher instead."
    )

    # --- Behavioral spy test ---
    fake_twitch_bytes = b"\x89PNG twitch avatar"
    twitch_spy = MagicMock(return_value=fake_twitch_bytes)
    youtube_spy = MagicMock(return_value=b"yt bytes")

    def fake_get_avatar_fetcher(provider_key):
        if provider_key == "twitch":
            return twitch_spy
        if provider_key == "youtube":
            return youtube_spy
        return None

    with patch.object(yt_import, "get_avatar_fetcher", side_effect=fake_get_avatar_fetcher) as mock_get, \
         patch("musicstreamer.assets.write_provider_avatar", return_value="assets/channel-avatars/7.png"):

        worker = _AvatarFetchWorker(
            url="https://www.twitch.tv/twitchdev",
            token=1,
            station_id=1,
            parent=None,
            node_runtime=None,
            provider_id=7,
        )
        # Collect emitted signal values
        emitted = []
        worker.finished.connect(lambda p, t: emitted.append((p, t)))
        worker.run()

    # get_avatar_fetcher should have been called with "twitch"
    calls = [c.args[0] for c in mock_get.call_args_list]
    assert "twitch" in calls, (
        f"get_avatar_fetcher was called with {calls!r} — expected 'twitch' "
        "for a twitch.tv URL"
    )

    # YouTube fetcher was NOT called
    youtube_spy.assert_not_called()

    # Twitch fetcher was called (with the URL)
    twitch_spy.assert_called_once()
    twitch_call_url = twitch_spy.call_args[0][0]
    assert "twitch.tv" in twitch_call_url, (
        f"Twitch fetcher called with unexpected URL: {twitch_call_url!r}"
    )

    # Worker should emit a non-empty path on success
    assert emitted, "Worker should have emitted finished signal"
    rel_path, token_val = emitted[0]
    assert rel_path != "", "Worker emitted empty rel_path — expected success"


# ---------------------------------------------------------------------------
# Test 3: YouTube dispatch still passes node_runtime (regression guard Pitfall 1)
# ---------------------------------------------------------------------------


def test_youtube_dispatch_passes_node_runtime():
    """A youtube.com URL still routes to the youtube fetcher and node_runtime
    is forwarded to it (regression guard for Pitfall 1 — Twitch fetcher has
    no node_runtime param; YouTube does).
    """
    from musicstreamer.ui_qt.edit_station_dialog import _AvatarFetchWorker
    from musicstreamer import yt_import

    fake_yt_bytes = b"\x89PNG youtube avatar"
    youtube_spy = MagicMock(return_value=fake_yt_bytes)
    twitch_spy = MagicMock(return_value=b"twitch bytes")

    FAKE_NODE_RUNTIME = "/usr/local/bin/node"

    def fake_get_avatar_fetcher(provider_key):
        if provider_key == "youtube":
            return youtube_spy
        if provider_key == "twitch":
            return twitch_spy
        return None

    with patch.object(yt_import, "get_avatar_fetcher", side_effect=fake_get_avatar_fetcher), \
         patch("musicstreamer.assets.write_provider_avatar", return_value="assets/channel-avatars/1.png"):

        worker = _AvatarFetchWorker(
            url="https://www.youtube.com/@LofiGirl",
            token=2,
            station_id=1,
            parent=None,
            node_runtime=FAKE_NODE_RUNTIME,
            provider_id=1,
        )
        emitted = []
        worker.finished.connect(lambda p, t: emitted.append((p, t)))
        worker.run()

    # Twitch fetcher NOT called
    twitch_spy.assert_not_called()

    # YouTube fetcher called with node_runtime
    youtube_spy.assert_called_once()
    call_kwargs = youtube_spy.call_args.kwargs
    call_args = youtube_spy.call_args.args
    # node_runtime may be passed positionally or as kwarg
    node_runtime_passed = (
        call_kwargs.get("node_runtime") == FAKE_NODE_RUNTIME or
        (len(call_args) > 1 and call_args[1] == FAKE_NODE_RUNTIME)
    )
    assert node_runtime_passed, (
        f"node_runtime not forwarded to YouTube fetcher. "
        f"call_args={call_args!r}, call_kwargs={call_kwargs!r}"
    )

    # Success emit
    assert emitted, "Worker should have emitted finished signal"
    rel_path, token_val = emitted[0]
    assert rel_path != "", "Worker should emit non-empty path on YouTube success"
