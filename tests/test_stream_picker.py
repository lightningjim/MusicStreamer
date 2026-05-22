"""Phase 39-04 TDD: NowPlayingPanel edit button + stream picker (UI-13).

Tests:
  1. Edit button exists and is initially disabled.
  2. Edit button becomes enabled after bind_station + on_playing_state_changed(True).
  3. Edit button becomes disabled after on_playing_state_changed(False).
  4. Stream picker is hidden when station has 1 stream.
  5. Stream picker is visible when station has 2+ streams.
  6. Stream picker populated with label "quality — codec" format.
  7. Changing stream picker selection calls player.play_stream with correct StationStream.
  8. Failover signal sync updates combo without triggering play_stream (blockSignals).
"""
from __future__ import annotations

from typing import Any, List
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

from musicstreamer.models import Station, StationStream
from musicstreamer.ui_qt import icons_rc  # noqa: F401
from musicstreamer.ui_qt.now_playing_panel import NowPlayingPanel
from tests._fake_player import FakePlayer


class FakeRepo:
    def __init__(self, streams_by_station_id=None, settings=None) -> None:
        self._streams: dict = dict(streams_by_station_id or {})
        self._settings: dict = dict(settings or {})
        self._favorites: list = []
        self.set_preferred_stream_calls: list = []

    def list_streams(self, station_id: int) -> List[StationStream]:
        return self._streams.get(station_id, [])

    def get_setting(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def set_setting(self, key: str, value: str) -> None:
        self._settings[key] = value

    def is_favorited(self, station_name: str, track_title: str) -> bool:
        return any(f == (station_name, track_title) for f in self._favorites)

    def add_favorite(self, station_name: str, provider_name: str, track_title: str, genre: str) -> None:
        key = (station_name, track_title)
        if key not in self._favorites:
            self._favorites.append(key)

    def remove_favorite(self, station_name: str, track_title: str) -> None:
        key = (station_name, track_title)
        if key in self._favorites:
            self._favorites.remove(key)

    def set_preferred_stream(self, station_id: int, stream_id) -> None:
        """Phase 82 D-02: record the call so behavioral tests can assert on args."""
        self.set_preferred_stream_calls.append((station_id, stream_id))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

single_stream_station = Station(
    id=1, name="FM1", provider_id=1, provider_name="P",
    tags="", station_art_path=None, album_fallback_path=None,
)

multi_stream_station = Station(
    id=2, name="FM2", provider_id=1, provider_name="P",
    tags="", station_art_path=None, album_fallback_path=None,
)

SINGLE_STREAMS = [
    StationStream(id=10, station_id=1, url="http://s1", quality="hi", codec="MP3", position=1),
]
MULTI_STREAMS = [
    StationStream(id=20, station_id=2, url="http://s1", quality="hi", codec="AAC", position=1),
    StationStream(id=21, station_id=2, url="http://s2", quality="med", codec="MP3", position=2),
]

# Re-declare with streams populated so behavioral tests can use multi_stream_station.streams[N].id
multi_stream_station = Station(
    id=2, name="FM2", provider_id=1, provider_name="P",
    tags="", station_art_path=None, album_fallback_path=None,
    streams=MULTI_STREAMS,
)


@pytest.fixture
def app(qtbot):
    """Ensure QApplication exists."""
    return QApplication.instance()


@pytest.fixture
def player():
    p = FakePlayer()
    # Override play_stream with a MagicMock so tests can assert call counts/args
    # (player.play_stream.assert_called_once_with(...), .assert_not_called(), etc.)
    p.play_stream = MagicMock()
    return p


@pytest.fixture
def repo():
    return FakeRepo(
        streams_by_station_id={
            1: SINGLE_STREAMS,
            2: MULTI_STREAMS,
        }
    )


@pytest.fixture
def panel(qtbot, player, repo):
    w = NowPlayingPanel(player, repo)
    qtbot.addWidget(w)
    return w


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_edit_btn_exists_and_disabled_initially(panel):
    """Test 1: edit_btn exists and is initially disabled."""
    assert hasattr(panel, "edit_btn"), "NowPlayingPanel must have edit_btn attribute"
    assert not panel.edit_btn.isEnabled(), "edit_btn must be disabled before any station is bound"


def test_edit_btn_enabled_when_playing(panel):
    """Test 2: edit_btn enabled after bind_station + on_playing_state_changed(True)."""
    panel.bind_station(single_stream_station)
    panel.on_playing_state_changed(True)
    assert panel.edit_btn.isEnabled(), "edit_btn must be enabled when a station is playing"


def test_edit_btn_enabled_when_stopped_with_station(panel):
    """Test 3: edit_btn stays enabled after stop if station is bound (UAT #3 fix)."""
    panel.bind_station(single_stream_station)
    panel.on_playing_state_changed(True)
    panel.on_playing_state_changed(False)
    assert panel.edit_btn.isEnabled(), "edit_btn must stay enabled when station is bound"


def test_stream_combo_hidden_for_single_stream(panel):
    """Test 4: stream_combo is hidden when station has only 1 stream."""
    assert hasattr(panel, "stream_combo"), "NowPlayingPanel must have stream_combo attribute"
    panel.bind_station(single_stream_station)
    # isHidden() checks the explicit hide flag regardless of parent visibility
    assert panel.stream_combo.isHidden(), "stream_combo must be hidden for single-stream station"


def test_stream_combo_visible_for_multi_stream(panel):
    """Test 5: stream_combo is visible when station has 2+ streams."""
    panel.bind_station(multi_stream_station)
    # isHidden() is False when setVisible(True) was called, even in offscreen tests
    assert not panel.stream_combo.isHidden(), "stream_combo must not be hidden for multi-stream station"


def test_stream_combo_populated_with_labels(panel):
    """Test 6: stream_combo populated with 'quality — codec' labels."""
    panel.bind_station(multi_stream_station)
    assert panel.stream_combo.count() == 2
    label_0 = panel.stream_combo.itemText(0)
    label_1 = panel.stream_combo.itemText(1)
    assert "hi" in label_0 and "AAC" in label_0, f"Expected 'hi — AAC' in '{label_0}'"
    assert "med" in label_1 and "MP3" in label_1, f"Expected 'med — MP3' in '{label_1}'"


def test_stream_selection_calls_play_stream(qtbot, player, repo):
    """Test 7: Changing stream picker selection calls player.play_stream with correct StationStream."""
    panel = NowPlayingPanel(player, repo)
    qtbot.addWidget(panel)
    panel.bind_station(multi_stream_station)

    player.play_stream.reset_mock()
    # Select index 1 (second stream)
    panel.stream_combo.setCurrentIndex(1)

    player.play_stream.assert_called_once()
    called_with = player.play_stream.call_args[0][0]
    assert called_with.id == MULTI_STREAMS[1].id, (
        f"Expected play_stream called with stream id={MULTI_STREAMS[1].id}, got {called_with.id}"
    )


def test_failover_sync_does_not_call_play_stream(qtbot, player, repo):
    """Test 8: _sync_stream_picker updates combo selection without triggering play_stream."""
    panel = NowPlayingPanel(player, repo)
    qtbot.addWidget(panel)
    panel.bind_station(multi_stream_station)

    player.play_stream.reset_mock()
    # Simulate failover sync to the second stream
    panel._sync_stream_picker(MULTI_STREAMS[1])

    # Combo selection must have updated
    assert panel.stream_combo.currentIndex() == 1, (
        "stream_combo must reflect the failed-over stream"
    )
    # play_stream must NOT have been called (blockSignals prevented it)
    player.play_stream.assert_not_called()


# ---------------------------------------------------------------------------
# Phase 82 D-02 behavioral tests + drift-guard
# ---------------------------------------------------------------------------


def test_on_stream_selected_persists_preferred_stream_id(qtbot, player, repo):
    """Phase 82 D-02: picking a stream persists to the DB."""
    panel = NowPlayingPanel(player, repo)
    qtbot.addWidget(panel)
    panel.bind_station(multi_stream_station)
    repo.set_preferred_stream_calls.clear()  # discard any bind_station noise
    panel.stream_combo.setCurrentIndex(1)
    assert len(repo.set_preferred_stream_calls) == 1
    station_id_arg, stream_id_arg = repo.set_preferred_stream_calls[0]
    assert station_id_arg == multi_stream_station.id
    assert stream_id_arg == multi_stream_station.streams[1].id


def test_bind_station_does_not_persist_preferred_stream_id(qtbot, player, repo):
    """Phase 82: blockSignals invariant — bind_station must NOT trigger persistence."""
    panel = NowPlayingPanel(player, repo)
    qtbot.addWidget(panel)
    panel.bind_station(multi_stream_station)
    assert repo.set_preferred_stream_calls == []


def test_on_stream_selected_with_invalid_index_does_not_persist(qtbot, player, repo):
    """Phase 82: early-return guard — invalid index must NOT trigger persistence."""
    panel = NowPlayingPanel(player, repo)
    qtbot.addWidget(panel)
    panel.bind_station(multi_stream_station)
    repo.set_preferred_stream_calls.clear()
    panel._on_stream_selected(-1)
    assert repo.set_preferred_stream_calls == []


def test_on_stream_selected_persists_even_when_reselecting_default(qtbot, player, repo):
    """Phase 82 D-02: every invocation persists, including reselection of the default."""
    panel = NowPlayingPanel(player, repo)
    qtbot.addWidget(panel)
    panel.bind_station(multi_stream_station)
    repo.set_preferred_stream_calls.clear()
    panel.stream_combo.setCurrentIndex(1)
    panel.stream_combo.setCurrentIndex(0)
    assert len(repo.set_preferred_stream_calls) == 2
    assert repo.set_preferred_stream_calls[1][1] == multi_stream_station.streams[0].id


def test_bind_station_syncs_combo_to_preferred_stream_id(qtbot, player, repo):
    """Phase 82 GAP-01: bind_station with preferred_stream_id set must point the combo's
    currentIndex at the matching item, NOT default to index 0. UI counterpart to
    Plan 82-02 queue-build precedence."""
    station_with_preferred = Station(
        id=2, name="FM2", provider_id=1, provider_name="P",
        tags="", station_art_path=None, album_fallback_path=None,
        streams=MULTI_STREAMS,
        preferred_stream_id=MULTI_STREAMS[1].id,  # 21 — second stream
    )
    panel = NowPlayingPanel(player, repo)
    qtbot.addWidget(panel)
    panel.bind_station(station_with_preferred)
    assert panel.stream_combo.currentIndex() == 1, (
        "Phase 82 GAP-01: combo must select preferred_stream_id's index on bind, "
        f"got index {panel.stream_combo.currentIndex()} instead of 1"
    )
    assert panel.stream_combo.itemData(panel.stream_combo.currentIndex()) == MULTI_STREAMS[1].id


def test_bind_station_without_preferred_stream_id_defaults_to_index_zero(qtbot, player, repo):
    """Phase 82 GAP-01: bind_station with preferred_stream_id=None preserves pre-Phase-82
    default behavior (combo lands on index 0)."""
    panel = NowPlayingPanel(player, repo)
    qtbot.addWidget(panel)
    panel.bind_station(multi_stream_station)  # preferred_stream_id is None
    assert panel.stream_combo.currentIndex() == 0, (
        "preferred_stream_id=None must leave combo at default index 0"
    )


def test_bind_station_with_stale_preferred_stream_id_defaults_to_index_zero(qtbot, player, repo):
    """Phase 82 GAP-01: preferred_stream_id pointing at a non-existent stream falls back
    to default behavior (combo lands on index 0) rather than raising or selecting -1."""
    station_with_stale = Station(
        id=2, name="FM2", provider_id=1, provider_name="P",
        tags="", station_art_path=None, album_fallback_path=None,
        streams=MULTI_STREAMS,
        preferred_stream_id=99999,  # not in MULTI_STREAMS
    )
    panel = NowPlayingPanel(player, repo)
    qtbot.addWidget(panel)
    panel.bind_station(station_with_stale)
    assert panel.stream_combo.currentIndex() == 0, (
        "stale preferred_stream_id must fall back to combo default (index 0)"
    )


def test_bind_station_with_preferred_does_not_trigger_play_stream(qtbot, player, repo):
    """Phase 82 GAP-01: the bind-time sync MUST stay inside blockSignals(True) — picking
    the preferred currentIndex must NOT fire _on_stream_selected (which would double-play
    and double-persist)."""
    station_with_preferred = Station(
        id=2, name="FM2", provider_id=1, provider_name="P",
        tags="", station_art_path=None, album_fallback_path=None,
        streams=MULTI_STREAMS,
        preferred_stream_id=MULTI_STREAMS[1].id,
    )
    panel = NowPlayingPanel(player, repo)
    qtbot.addWidget(panel)
    player.play_stream.reset_mock()
    repo.set_preferred_stream_calls.clear()
    panel.bind_station(station_with_preferred)
    player.play_stream.assert_not_called()
    assert repo.set_preferred_stream_calls == []


def test_set_preferred_stream_drift_guard_now_playing_panel():
    """Phase 82 D-02 drift-guard (Phase 51/55/61/63/81 precedent)."""
    from pathlib import Path
    source = (
        Path(__file__).resolve().parent.parent
        / "musicstreamer" / "ui_qt" / "now_playing_panel.py"
    ).read_text()
    non_comments = "\n".join(
        ln for ln in source.splitlines() if not ln.lstrip().startswith("#")
    )
    assert "set_preferred_stream" in non_comments, (
        "Phase 82 D-02: self._repo.set_preferred_stream call must exist in "
        "now_playing_panel.py (_on_stream_selected). Do not remove silently."
    )
