"""Wave 0 RED tests for Twitch provider derivation on save (Phase 89b Plan 02).

Tests:
- test_save_derives_provider_for_blank_twitch: blank Provider + twitch.tv URL -> ensure_provider("Twitch: twitchdev")
- test_save_preserves_manual_provider_for_twitch: manual Provider + twitch.tv URL -> no override (D-04)
- test_save_non_twitch_url_unchanged: blank Provider + non-twitch URL -> no Twitch derivation

Run with: .venv/bin/python -m pytest tests/test_twitch_provider_assign.py -q
"""
import inspect
from unittest.mock import MagicMock

import pytest

from musicstreamer.models import Provider, Station, StationStream


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def station_blank_provider():
    """Twitch station with no provider yet (blank-provider case)."""
    return Station(
        id=5,
        name="TwitchDev Stream",
        provider_id=None,
        provider_name=None,
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
        Provider(2, "Live Sports"),
    ]
    r.list_streams.return_value = [
        StationStream(id=10, station_id=5, url="https://www.twitch.tv/twitchdev",
                      label="", quality="hi", position=1,
                      stream_type="", codec="MP3"),
    ]
    r.ensure_provider.return_value = 9
    return r


@pytest.fixture()
def player():
    p = MagicMock()
    p._current_station_name = ""
    return p


# ---------------------------------------------------------------------------
# Source-grep drift-guard
# ---------------------------------------------------------------------------


def test_save_source_has_twitch_derivation():
    """Source-grep gate: _on_save must contain the f-string Twitch provider derivation
    and a blank-provider guard (not provider_name) preceding it.

    This guard fires during the RED phase — these strings are not yet in _on_save.
    """
    import importlib.resources
    src = importlib.resources.files("musicstreamer.ui_qt").joinpath(
        "edit_station_dialog.py"
    ).read_text()

    # The f-string derivation form specifically (not a comment mentioning Twitch:)
    assert 'f"Twitch: ' in src or "f'Twitch: " in src, (
        "Drift-guard: _on_save must contain f\"Twitch: {login}\" f-string for "
        "provider name derivation. Not yet implemented."
    )

    # The blank-provider guard must precede the f-string Twitch derivation
    # Use the f-string form to locate the actual implementation (not the comment)
    if 'f"Twitch: ' in src:
        twitch_idx = src.find('f"Twitch: ')
    else:
        twitch_idx = src.find("f'Twitch: ")

    blank_guard_idx = src.find("not provider_name")
    assert blank_guard_idx != -1 and blank_guard_idx < twitch_idx, (
        "Drift-guard: blank-provider guard ('not provider_name') must appear "
        "before the Twitch derivation in _on_save. "
        f"blank_guard at {blank_guard_idx}, twitch_derivation at {twitch_idx}."
    )


# ---------------------------------------------------------------------------
# Test 1: Blank provider + twitch.tv URL => derive Twitch: <login>
# ---------------------------------------------------------------------------


def test_save_derives_provider_for_blank_twitch(qtbot, station_blank_provider, player, repo):
    """When Provider field is blank AND URL is twitch.tv/.../twitchdev, on save:
    ensure_provider is called with exactly 'Twitch: twitchdev' and the returned
    id is passed to update_station.
    """
    from musicstreamer.ui_qt.edit_station_dialog import EditStationDialog

    d = EditStationDialog(station_blank_provider, player, repo, parent=None)
    qtbot.addWidget(d)

    # URL pre-loaded from repo.list_streams via _populate() — no widget setText needed (Phase 97).

    # Clear the provider combo so it's blank
    d.provider_combo.setCurrentText("")

    # Configure the mock to return a specific provider_id
    repo.ensure_provider.return_value = 9

    # Trigger save
    d.button_box.accepted.emit()

    # ensure_provider should have been called with "Twitch: twitchdev"
    ensure_calls = [c.args[0] for c in repo.ensure_provider.call_args_list]
    assert "Twitch: twitchdev" in ensure_calls, (
        f"ensure_provider was called with {ensure_calls!r}. "
        "Expected 'Twitch: twitchdev' — blank-provider Twitch derivation not yet implemented."
    )

    # update_station should have received provider_id=9
    assert repo.update_station.called, "update_station should have been called"
    update_args = repo.update_station.call_args[0]
    assert update_args[2] == 9, (
        f"update_station called with provider_id={update_args[2]!r}, expected 9 "
        "(the return value of ensure_provider('Twitch: twitchdev'))"
    )


# ---------------------------------------------------------------------------
# Test 2: Manual provider + twitch.tv URL => preserve manual provider (D-04)
# ---------------------------------------------------------------------------


def test_save_preserves_manual_provider_for_twitch(qtbot, station_blank_provider, player, repo):
    """When Provider field is 'Live Sports' (user-typed) AND URL is twitch.tv,
    on save ensure_provider is called with 'Live Sports' verbatim — NOT 'Twitch: ...'
    D-04 / Pitfall 3: manual provider must never be overwritten.
    """
    from musicstreamer.ui_qt.edit_station_dialog import EditStationDialog

    # Use a station with an existing provider
    station_with_provider = Station(
        id=5,
        name="TwitchDev Stream",
        provider_id=2,
        provider_name="Live Sports",
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        icy_disabled=True,
        provider_avatar_path=None,
    )
    d = EditStationDialog(station_with_provider, player, repo, parent=None)
    qtbot.addWidget(d)

    # URL pre-loaded from repo.list_streams via _populate() — no widget setText needed (Phase 97).

    # Explicitly set provider combo to a user-chosen value
    d.provider_combo.setCurrentText("Live Sports")

    repo.ensure_provider.return_value = 2

    # Trigger save
    d.button_box.accepted.emit()

    # ensure_provider should have been called with "Live Sports", NOT "Twitch: twitchdev"
    ensure_calls = [c.args[0] for c in repo.ensure_provider.call_args_list]
    assert "Twitch: twitchdev" not in ensure_calls, (
        f"D-04 violation: ensure_provider was called with {ensure_calls!r}. "
        "Manual provider 'Live Sports' should NOT be overwritten with 'Twitch: twitchdev'."
    )
    assert "Live Sports" in ensure_calls, (
        f"ensure_provider should be called with 'Live Sports' verbatim. "
        f"Got: {ensure_calls!r}"
    )


# ---------------------------------------------------------------------------
# Test 3: Non-twitch URL + blank provider => no Twitch derivation
# ---------------------------------------------------------------------------


def test_save_non_twitch_url_unchanged(qtbot, player, repo):
    """Blank provider + a non-twitch URL => ensure_provider called with blank/empty
    (no Twitch derivation injected) — regression guard for non-twitch stations.
    """
    from musicstreamer.ui_qt.edit_station_dialog import EditStationDialog

    non_twitch_station = Station(
        id=3,
        name="Soma FM",
        provider_id=None,
        provider_name=None,
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        icy_disabled=False,
        provider_avatar_path=None,
    )
    repo.list_streams.return_value = [
        StationStream(id=20, station_id=3, url="http://ice3.somafm.com/groovesalad-128.mp3",
                      label="", quality="hi", position=1,
                      stream_type="", codec="MP3"),
    ]
    d = EditStationDialog(non_twitch_station, player, repo, parent=None)
    qtbot.addWidget(d)

    # URL pre-loaded from overridden repo.list_streams via _populate() — no widget setText needed (Phase 97).

    # Blank provider
    d.provider_combo.setCurrentText("")

    repo.ensure_provider.return_value = None

    # Trigger save
    d.button_box.accepted.emit()

    ensure_calls = [c.args[0] for c in repo.ensure_provider.call_args_list]
    twitch_calls = [c for c in ensure_calls if "Twitch:" in c]
    assert not twitch_calls, (
        f"Regression: ensure_provider was called with Twitch-derived name {twitch_calls!r} "
        "for a non-twitch URL. Twitch derivation must only apply to twitch.tv URLs."
    )


# ---------------------------------------------------------------------------
# Phase 89B-03 add-path gap-closure tests (RED until Task 2 lands)
#
# These cover the synchronous fetch-and-persist + in-memory provider refresh
# that _on_save must perform on the FIRST save of a NEW Twitch station, so the
# avatar resolves without a re-edit (UAT-discovered gap; see
# .planning/debug/twitch-avatar-fails-on-new-add.md).
#
# Patch targets match the helper's import form (Task 2):
#   from musicstreamer import yt_import, assets as _assets
# => patch musicstreamer.yt_import.get_avatar_fetcher
#    and  musicstreamer.assets.write_provider_avatar
# ---------------------------------------------------------------------------


def test_save_add_path_fetches_avatar(qtbot, station_blank_provider, player, repo):
    """First save of a NEW blank-provider Twitch station must synchronously fetch
    the avatar bytes and persist them per-provider (gap closure)."""
    from unittest.mock import patch

    from musicstreamer.ui_qt.edit_station_dialog import EditStationDialog

    repo.ensure_provider.return_value = 9

    d = EditStationDialog(station_blank_provider, player, repo, parent=None)
    qtbot.addWidget(d)
    # URL pre-loaded from repo.list_streams via _populate() — no widget setText needed (Phase 97).
    d.provider_combo.setCurrentText("")

    stub_fetcher = MagicMock(return_value=b"PNGDATA")

    with patch(
        "musicstreamer.yt_import.get_avatar_fetcher",
        return_value=stub_fetcher,
    ) as mock_get_fetcher, patch(
        "musicstreamer.assets.write_provider_avatar",
        return_value="assets/channel-avatars/9.png",
    ) as mock_write:
        d.button_box.accepted.emit()

    # Dispatched through the "twitch" registry key
    assert mock_get_fetcher.called
    assert "twitch" in [c.args[0] for c in mock_get_fetcher.call_args_list]

    # Bytes written under the derived provider_id (9)
    assert mock_write.called, "write_provider_avatar must be called on the add path"
    write_args = mock_write.call_args[0]
    assert write_args[0] == 9, f"expected provider_id=9, got {write_args[0]!r}"
    assert write_args[1] == b"PNGDATA"

    # DB persist of the relative path
    assert repo.update_provider_avatar_path.called
    assert repo.update_provider_avatar_path.call_args[0] == (
        9,
        "assets/channel-avatars/9.png",
    )


def test_save_add_path_refreshes_in_memory_provider(
    qtbot, station_blank_provider, player, repo
):
    """After ensure_provider, _on_save must refresh the in-memory Station so
    provider_id / provider_name reflect the derived provider (D-02/D-04)."""
    from unittest.mock import patch

    from musicstreamer.ui_qt.edit_station_dialog import EditStationDialog

    repo.ensure_provider.return_value = 9

    d = EditStationDialog(station_blank_provider, player, repo, parent=None)
    qtbot.addWidget(d)
    # URL pre-loaded from repo.list_streams via _populate() — no widget setText needed (Phase 97).
    d.provider_combo.setCurrentText("")

    stub_fetcher = MagicMock(return_value=b"PNGDATA")
    with patch(
        "musicstreamer.yt_import.get_avatar_fetcher", return_value=stub_fetcher
    ), patch(
        "musicstreamer.assets.write_provider_avatar",
        return_value="assets/channel-avatars/9.png",
    ):
        d.button_box.accepted.emit()

    assert d._station.provider_id == 9
    assert d._station.provider_name == "Twitch: twitchdev"


def test_save_existing_provider_with_avatar_no_refetch(qtbot, player, repo):
    """Adding a Twitch station under an EXISTING provider that already has an
    avatar must NOT trigger a network fetch (D-07 reuse gate)."""
    from unittest.mock import patch

    from musicstreamer.ui_qt.edit_station_dialog import EditStationDialog

    station_existing = Station(
        id=5,
        name="TwitchDev Stream",
        provider_id=7,
        provider_name="Twitch: existing",
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        icy_disabled=True,
        provider_avatar_path="assets/channel-avatars/7.png",
    )
    repo.ensure_provider.return_value = 7

    d = EditStationDialog(station_existing, player, repo, parent=None)
    qtbot.addWidget(d)
    # URL pre-loaded from repo.list_streams via _populate() — no widget setText needed (Phase 97).
    d.provider_combo.setCurrentText("Twitch: existing")

    stub_fetcher = MagicMock(return_value=b"PNGDATA")
    with patch(
        "musicstreamer.yt_import.get_avatar_fetcher", return_value=stub_fetcher
    ), patch(
        "musicstreamer.assets.write_provider_avatar",
        return_value="assets/channel-avatars/7.png",
    ) as mock_write:
        d.button_box.accepted.emit()

    assert not stub_fetcher.called, "D-07: existing avatar must NOT be refetched"
    assert not mock_write.called
    assert not repo.update_provider_avatar_path.called


def test_save_manual_provider_not_overwritten_still_holds(qtbot, player, repo):
    """Regression (D-04): a manual provider + twitch URL with no avatar yet must
    key the fetch on the MANUAL provider_id, never on a derived 'Twitch:' name."""
    from unittest.mock import patch

    from musicstreamer.ui_qt.edit_station_dialog import EditStationDialog

    station_manual = Station(
        id=5,
        name="TwitchDev Stream",
        provider_id=2,
        provider_name="Live Sports",
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        icy_disabled=True,
        provider_avatar_path=None,
    )
    # ensure_provider("Live Sports") -> the MANUAL provider id
    repo.ensure_provider.return_value = 2

    d = EditStationDialog(station_manual, player, repo, parent=None)
    qtbot.addWidget(d)
    # URL pre-loaded from repo.list_streams via _populate() — no widget setText needed (Phase 97).
    d.provider_combo.setCurrentText("Live Sports")

    stub_fetcher = MagicMock(return_value=b"PNGDATA")
    with patch(
        "musicstreamer.yt_import.get_avatar_fetcher", return_value=stub_fetcher
    ), patch(
        "musicstreamer.assets.write_provider_avatar",
        return_value="assets/channel-avatars/2.png",
    ) as mock_write:
        d.button_box.accepted.emit()

    # Manual provider preserved, never overwritten with "Twitch: twitchdev"
    ensure_calls = [c.args[0] for c in repo.ensure_provider.call_args_list]
    assert "Twitch: twitchdev" not in ensure_calls
    assert "Live Sports" in ensure_calls

    # Fetch keys on the MANUAL provider_id (2), not a derived name
    if mock_write.called:
        assert mock_write.call_args[0][0] == 2
    if repo.update_provider_avatar_path.called:
        assert repo.update_provider_avatar_path.call_args[0][0] == 2


def test_save_fetch_failure_is_nonblocking(qtbot, station_blank_provider, player, repo):
    """A fetch failure on the add path must be swallowed: no exception, Save still
    succeeds, accept() runs, and no DB avatar persist occurs (D-07)."""
    from unittest.mock import patch

    from musicstreamer.ui_qt.edit_station_dialog import EditStationDialog

    repo.ensure_provider.return_value = 9

    d = EditStationDialog(station_blank_provider, player, repo, parent=None)
    qtbot.addWidget(d)
    # URL pre-loaded from repo.list_streams via _populate() — no widget setText needed (Phase 97).
    d.provider_combo.setCurrentText("")

    failing_fetcher = MagicMock(side_effect=RuntimeError("no token"))
    with patch(
        "musicstreamer.yt_import.get_avatar_fetcher", return_value=failing_fetcher
    ), patch(
        "musicstreamer.assets.write_provider_avatar",
        return_value="assets/channel-avatars/9.png",
    ) as mock_write:
        # Must not raise
        d.button_box.accepted.emit()

    assert d._save_succeeded is True
    assert not mock_write.called
    assert not repo.update_provider_avatar_path.called


def test_on_save_has_inmemory_provider_assignment():
    """Drift-guard: _on_save must assign provider_id/provider_name in-memory AFTER
    the ensure_provider call (non-comment source)."""
    import importlib.resources

    raw = importlib.resources.files("musicstreamer.ui_qt").joinpath(
        "edit_station_dialog.py"
    ).read_text()
    # Strip comment-only lines so a comment can't satisfy the guard.
    code = "\n".join(
        line for line in raw.splitlines() if not line.lstrip().startswith("#")
    )

    assert "self._station.provider_id = provider_id" in code
    assert "self._station.provider_name = provider_name" in code

    ensure_idx = code.find("repo.ensure_provider(")
    assign_idx = code.find("self._station.provider_id = provider_id")
    assert ensure_idx != -1 and assign_idx != -1
    assert assign_idx > ensure_idx, (
        "in-memory provider assignment must appear AFTER repo.ensure_provider()"
    )
