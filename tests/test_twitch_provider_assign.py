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

    # Set URL to twitch.tv
    d.url_edit.setText("https://www.twitch.tv/twitchdev")

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

    # Set URL to twitch.tv
    d.url_edit.setText("https://www.twitch.tv/twitchdev")

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

    # Non-twitch URL
    d.url_edit.setText("http://ice3.somafm.com/groovesalad-128.mp3")

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
