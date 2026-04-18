"""Tests for EditStationDialog — UI-05 station editor.

Phase 39-01 TDD RED: all tests initially fail with ImportError
until edit_station_dialog.py is implemented.
"""
from unittest.mock import MagicMock, call

import pytest

from musicstreamer.models import Provider, Station, StationStream
from musicstreamer.ui_qt.edit_station_dialog import EditStationDialog


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def station():
    return Station(
        id=1,
        name="Test FM",
        provider_id=1,
        provider_name="TestProvider",
        tags="jazz,electronic",
        station_art_path=None,
        album_fallback_path=None,
        icy_disabled=False,
    )


@pytest.fixture()
def repo():
    r = MagicMock()
    r.list_providers.return_value = [
        Provider(1, "TestProvider"),
        Provider(2, "Other"),
    ]
    r.list_streams.return_value = [
        StationStream(id=10, station_id=1, url="http://s1.mp3",
                      label="", quality="hi", position=1,
                      stream_type="", codec="MP3"),
    ]
    r.ensure_provider.return_value = 1
    return r


@pytest.fixture()
def player():
    p = MagicMock()
    p._current_station_name = ""
    return p


@pytest.fixture()
def dialog(qtbot, station, player, repo):
    d = EditStationDialog(station, player, repo, parent=None)
    qtbot.addWidget(d)
    return d


# ---------------------------------------------------------------------------
# Test 1: Station name populated
# ---------------------------------------------------------------------------


def test_name_field_populated(dialog):
    """Dialog opens with station name in name field."""
    assert dialog.name_edit.text() == "Test FM"


# ---------------------------------------------------------------------------
# Test 2: Provider combo editable and populated
# ---------------------------------------------------------------------------


def test_provider_combo_editable_and_populated(dialog, repo):
    """Provider combo is editable and populated from repo.list_providers()."""
    combo = dialog.provider_combo
    assert combo.isEditable()
    items = [combo.itemText(i) for i in range(combo.count())]
    assert "TestProvider" in items
    assert "Other" in items


# ---------------------------------------------------------------------------
# Test 3: Tag chips render and toggle
# ---------------------------------------------------------------------------


def test_tag_chips_render_and_toggle(dialog):
    """Tag chips render for comma-separated tags; toggling changes chipState."""
    chips = dialog._tag_chips
    assert "jazz" in chips
    assert "electronic" in chips

    jazz_chip = chips["jazz"]
    assert jazz_chip.property("chipState") == "selected"

    # toggle: click unselects
    jazz_chip.click()
    assert jazz_chip.property("chipState") == "unselected"

    # toggle again: click reselects
    jazz_chip.click()
    assert jazz_chip.property("chipState") == "selected"


# ---------------------------------------------------------------------------
# Test 4: Add Tag button adds new chip in selected state
# ---------------------------------------------------------------------------


def test_add_tag_creates_chip(qtbot, dialog):
    """Clicking Add Tag with non-empty text adds a selected chip."""
    dialog.new_tag_edit.setText("ambient")
    qtbot.mouseClick(dialog.add_tag_btn, __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.LeftButton)

    assert "ambient" in dialog._tag_chips
    new_chip = dialog._tag_chips["ambient"]
    assert new_chip.property("chipState") == "selected"


# ---------------------------------------------------------------------------
# Test 5: Stream table shows rows; Add button inserts row
# ---------------------------------------------------------------------------


def test_stream_table_populated_and_add(qtbot, dialog):
    """Stream table shows rows from repo.list_streams(); Add inserts a row."""
    table = dialog.streams_table
    assert table.rowCount() == 1
    assert table.item(0, 0).text() == "http://s1.mp3"

    initial_count = table.rowCount()
    qtbot.mouseClick(dialog.add_stream_btn, __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.LeftButton)
    assert table.rowCount() == initial_count + 1


# ---------------------------------------------------------------------------
# Test 6: Remove button removes selected stream row
# ---------------------------------------------------------------------------


def test_remove_stream_removes_row(qtbot, dialog):
    """Remove button removes the selected stream row."""
    table = dialog.streams_table
    table.selectRow(0)
    initial_count = table.rowCount()
    qtbot.mouseClick(dialog.remove_stream_btn, __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.LeftButton)
    assert table.rowCount() == initial_count - 1


# ---------------------------------------------------------------------------
# Test 7: Move Up / Move Down reorder rows
# ---------------------------------------------------------------------------


def test_move_up_down_reorder(qtbot, dialog):
    """Move Up / Move Down reorder rows in the stream table."""
    from PySide6.QtCore import Qt

    # Add a second row so we have 2 rows to reorder
    qtbot.mouseClick(dialog.add_stream_btn, Qt.LeftButton)
    dialog.streams_table.item(1, 0).setText("http://s2.mp3")

    table = dialog.streams_table
    # Select second row
    table.selectRow(1)
    qtbot.mouseClick(dialog.move_up_btn, Qt.LeftButton)
    # After move-up the previously-second row should now be row 0
    assert table.item(0, 0).text() == "http://s2.mp3"

    # Move it back down
    table.selectRow(0)
    qtbot.mouseClick(dialog.move_down_btn, Qt.LeftButton)
    assert table.item(1, 0).text() == "http://s2.mp3"


# ---------------------------------------------------------------------------
# Test 8: Delete disabled when station is currently playing
# ---------------------------------------------------------------------------


def test_delete_disabled_when_playing(qtbot, station, repo):
    """Delete button disabled when player._current_station_name matches station.name."""
    playing_player = MagicMock()
    playing_player._current_station_name = "Test FM"
    d = EditStationDialog(station, playing_player, repo, parent=None)
    qtbot.addWidget(d)
    assert d.delete_btn.isEnabled() is False


# ---------------------------------------------------------------------------
# Test 9: Delete enabled when station is not playing
# ---------------------------------------------------------------------------


def test_delete_enabled_when_not_playing(dialog):
    """Delete button enabled when player._current_station_name differs."""
    assert dialog.delete_btn.isEnabled() is True


# ---------------------------------------------------------------------------
# Test 10: Save calls ensure_provider then update_station
# ---------------------------------------------------------------------------


def test_save_calls_repo_correctly(qtbot, dialog, repo):
    """Save calls repo.ensure_provider then repo.update_station with correct args."""
    from PySide6.QtCore import Qt

    dialog.name_edit.setText("Updated FM")
    dialog.provider_combo.setCurrentText("TestProvider")

    # Trigger save via accept button
    dialog.button_box.accepted.emit()

    repo.ensure_provider.assert_called_once_with("TestProvider")
    repo.update_station.assert_called_once()
    args = repo.update_station.call_args[0]
    assert args[0] == 1          # station_id
    assert args[1] == "Updated FM"   # name
    assert args[2] == 1          # provider_id from ensure_provider mock


# ---------------------------------------------------------------------------
# Test 11: ICY checkbox maps to icy_disabled in update_station
# ---------------------------------------------------------------------------


def test_icy_checkbox_maps_to_icy_disabled(qtbot, dialog, repo, station):
    """ICY checkbox state maps to icy_disabled parameter in update_station."""
    from PySide6.QtCore import Qt

    # Station starts with icy_disabled=False, so checkbox should be unchecked
    assert dialog.icy_checkbox.isChecked() is False

    # Check the box to disable ICY
    dialog.icy_checkbox.setChecked(True)

    # Trigger save
    dialog.button_box.accepted.emit()

    args = repo.update_station.call_args[0]
    # icy_disabled is positional arg 6 (index 6)
    assert args[6] is True


# ---------------------------------------------------------------------------
# Phase 40.1-04: Logo picker + preview + auto-fetch (D-12, D-13, D-14)
# ---------------------------------------------------------------------------


def test_logo_row_shows_preview(qtbot, tmp_path, monkeypatch, player, repo):
    """Dialog shows 64x64 preview of current station logo."""
    import os
    from PySide6.QtGui import QPixmap
    from musicstreamer import paths as _paths

    monkeypatch.setattr(_paths, "_root_override", str(tmp_path))
    asset_dir = os.path.join(str(tmp_path), "assets", "1")
    os.makedirs(asset_dir, exist_ok=True)
    pix = QPixmap(32, 32)
    pix.fill(0xFF00AA00)
    asset_rel = "assets/1/station_art.png"
    assert pix.save(os.path.join(str(tmp_path), asset_rel), "PNG")

    st = Station(
        id=1, name="Test FM", provider_id=1, provider_name="TestProvider",
        tags="", station_art_path=asset_rel, album_fallback_path=None, icy_disabled=False,
    )
    d = EditStationDialog(st, player, repo, parent=None)
    qtbot.addWidget(d)

    assert hasattr(d, "_logo_preview")
    assert d._logo_preview.size().width() == 64
    assert d._logo_preview.size().height() == 64
    pm = d._logo_preview.pixmap()
    assert pm is not None and not pm.isNull()


def test_logo_picker_copies_via_assets(qtbot, tmp_path, monkeypatch, dialog, station):
    """Choose File button copies selected image via assets.copy_asset_for_station()."""
    from unittest.mock import MagicMock
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QFileDialog

    # Create source image file.
    src = tmp_path / "new_logo.png"
    pix = QPixmap(32, 32)
    pix.fill(0xFFAABBCC)
    assert pix.save(str(src), "PNG")

    monkeypatch.setattr(
        QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **kw: (str(src), "Images (*.png *.jpg *.jpeg *.webp *.svg)")),
    )

    import musicstreamer.ui_qt.edit_station_dialog as esd_mod
    mock_copy = MagicMock(return_value="assets/1/station_art.png")
    monkeypatch.setattr(esd_mod.assets, "copy_asset_for_station", mock_copy)

    assert hasattr(dialog, "_choose_logo_btn")
    dialog._choose_logo_btn.click()

    mock_copy.assert_called_once()
    call_args = mock_copy.call_args[0]
    assert call_args[0] == station.id
    assert call_args[1] == str(src)
    assert dialog._logo_path == "assets/1/station_art.png"


def test_save_persists_new_logo_path(qtbot, dialog, repo):
    """On save, repo.update_station gets the new _logo_path, not the stale station.station_art_path."""
    dialog._logo_path = "assets/5/new_art.png"
    dialog.button_box.accepted.emit()

    args = repo.update_station.call_args[0]
    # station_art_path is positional arg 4 (index 4) per _on_save
    assert args[4] == "assets/5/new_art.png"


def test_auto_fetch_worker_starts_on_url_change(qtbot, monkeypatch, dialog):
    """Timeout handler instantiates _LogoFetchWorker and starts it."""
    from unittest.mock import MagicMock

    import musicstreamer.ui_qt.edit_station_dialog as esd_mod

    fake_worker_instance = MagicMock()
    fake_worker_instance.isRunning.return_value = False
    fake_worker_cls = MagicMock(return_value=fake_worker_instance)
    monkeypatch.setattr(esd_mod, "_LogoFetchWorker", fake_worker_cls)

    dialog.url_edit.setText("https://www.youtube.com/watch?v=abc")
    # Fire the timer-timeout slot directly
    assert hasattr(dialog, "_on_url_timer_timeout")
    dialog._on_url_timer_timeout()

    fake_worker_cls.assert_called_once()
    assert "youtube.com" in fake_worker_cls.call_args[0][0]
    fake_worker_instance.start.assert_called_once()


def test_auto_fetch_completion_copies_via_assets(qtbot, tmp_path, monkeypatch, dialog, station):
    """When the fetch worker emits finished(path), dialog copies via assets."""
    from unittest.mock import MagicMock
    from PySide6.QtGui import QPixmap

    import musicstreamer.ui_qt.edit_station_dialog as esd_mod

    fetched = tmp_path / "fetched.jpg"
    pix = QPixmap(16, 16)
    pix.fill(0xFF112233)
    assert pix.save(str(fetched), "PNG")

    mock_copy = MagicMock(return_value="assets/1/station_art.jpg")
    monkeypatch.setattr(esd_mod.assets, "copy_asset_for_station", mock_copy)

    assert hasattr(dialog, "_on_logo_fetched")
    dialog._on_logo_fetched(str(fetched))

    mock_copy.assert_called_once()
    args = mock_copy.call_args[0]
    assert args[0] == station.id
    assert args[1] == str(fetched)
    assert dialog._logo_path == "assets/1/station_art.jpg"


# ---------------------------------------------------------------------------
# Phase 46-02: Logo status UX — AA classification, auto-clear, cursor override
# ---------------------------------------------------------------------------


def test_aa_no_key_message_string(dialog):
    """_on_logo_fetched with classification='aa_no_key' sets the AA-distinct message."""
    dialog._on_logo_fetched("", token=0, classification="aa_no_key")
    assert dialog._logo_status.text() == (
        "AudioAddict station \u2014 use Choose File to supply a logo"
    )


def test_logo_status_clears_after_3s(dialog, qtbot, monkeypatch):
    """After a terminal status is set, the label auto-clears 3s later via the timer."""
    from unittest.mock import MagicMock
    import musicstreamer.ui_qt.edit_station_dialog as esd_mod

    # Defensive: prevent setText() from spawning a real _LogoFetchWorker via the
    # existing 500ms _url_timer debounce during the qtbot.wait(3100) below.
    # Without this, the real worker fires ~t=500ms, overwrites _logo_status
    # with "Fetching…" → (fetch result), restarts the 3s clear timer, and the
    # assertion at t=3100ms fails non-deterministically.
    monkeypatch.setattr(esd_mod, "_LogoFetchWorker", MagicMock())
    dialog.url_edit.setText("http://example.com/notsupported")
    dialog._url_timer.stop()  # cancel the existing 500ms debounce
    # Direct-call the slot to simulate fetch-completion with no tmp_path.
    dialog._on_logo_fetched("", token=0, classification="")
    assert dialog._logo_status.text() == "Fetch not supported for this URL"
    assert dialog._logo_status_clear_timer.isActive()
    # Wait slightly longer than the 3s interval.
    qtbot.wait(3100)
    assert dialog._logo_status.text() == ""
    assert not dialog._logo_status_clear_timer.isActive()


def test_text_changed_cancels_pending_clear(dialog, qtbot, monkeypatch):
    """Typing in url_edit immediately clears the label AND cancels the 3s timer."""
    from unittest.mock import MagicMock
    import musicstreamer.ui_qt.edit_station_dialog as esd_mod

    # Defensive: same rationale as test_logo_status_clears_after_3s. Assertions
    # below are synchronous, but stopping the debounce makes the test robust
    # against future changes to _on_url_text_changed's debounce behavior.
    monkeypatch.setattr(esd_mod, "_LogoFetchWorker", MagicMock())
    dialog.url_edit.setText("http://example.com/notsupported")
    dialog._url_timer.stop()
    dialog._on_logo_fetched("", token=0, classification="")
    assert dialog._logo_status.text() == "Fetch not supported for this URL"
    assert dialog._logo_status_clear_timer.isActive()
    # Simulate the user typing — this fires textChanged.
    dialog.url_edit.setText("http://something-new")
    # The timer must be stopped and the label must be empty immediately,
    # without needing to wait 3s.
    assert dialog._logo_status.text() == ""
    assert not dialog._logo_status_clear_timer.isActive()


def test_aa_url_no_key_worker_emits_aa_no_key_classification(qtbot, monkeypatch):
    """_LogoFetchWorker emits finished(..., 'aa_no_key') when AA URL parses but key is missing."""
    import musicstreamer.ui_qt.edit_station_dialog as esd_mod

    # NOTE: This test depends on _LogoFetchWorker.run importing _is_aa_url /
    # _aa_slug_from_url / _aa_channel_key_from_url from musicstreamer.url_helpers
    # at call time, AND on the no-key early-return firing BEFORE _fetch_image_map
    # is imported from musicstreamer.aa_import. If that ordering changes, this
    # test will break silently — refactor the classification logic into an
    # extractable helper before moving the imports.

    # Force the AA-branch to take the "no key" early-return path.
    monkeypatch.setattr(
        "musicstreamer.url_helpers._is_aa_url", lambda url: True
    )
    monkeypatch.setattr(
        "musicstreamer.url_helpers._aa_slug_from_url", lambda url: None
    )
    monkeypatch.setattr(
        "musicstreamer.url_helpers._aa_channel_key_from_url",
        lambda url, slug=None: None,
    )

    captured: list[tuple] = []
    worker = esd_mod._LogoFetchWorker("http://di.fm/chillout", token=7)
    worker.finished.connect(lambda *args: captured.append(args))
    # Run the worker's logic synchronously (avoid qthread wait).
    worker.run()

    assert len(captured) == 1
    tmp_path, token, classification = captured[0]
    assert tmp_path == ""
    assert token == 7
    assert classification == "aa_no_key"


# ---------------------------------------------------------------------------
# PB-16 / PB-17: Bitrate column (Phase 47-03)
# ---------------------------------------------------------------------------


def test_bitrate_column_populated(qtbot, station, player, repo):
    """PB-16: Bitrate column shows str(bitrate_kbps) when non-zero, empty string when 0."""
    repo.list_streams.return_value = [
        StationStream(id=10, station_id=1, url="http://s1", label="",
                      quality="hi", position=1, stream_type="",
                      codec="AAC", bitrate_kbps=320),
        StationStream(id=11, station_id=1, url="http://s2", label="",
                      quality="low", position=2, stream_type="",
                      codec="MP3", bitrate_kbps=0),
    ]
    from musicstreamer.ui_qt.edit_station_dialog import _COL_BITRATE

    d = EditStationDialog(station, player, repo, parent=None)
    qtbot.addWidget(d)

    assert d.streams_table.item(0, _COL_BITRATE).text() == "320"
    assert d.streams_table.item(1, _COL_BITRATE).text() == ""


def test_empty_bitrate_saves_as_zero(qtbot, station, player, repo):
    """PB-17: empty Bitrate cell -> int(text or '0') = 0, no ValueError, update_stream gets 0."""
    repo.list_streams.return_value = [
        StationStream(id=10, station_id=1, url="http://s1", label="",
                      quality="hi", position=1, stream_type="",
                      codec="AAC", bitrate_kbps=320),
    ]
    from musicstreamer.ui_qt.edit_station_dialog import _COL_BITRATE

    d = EditStationDialog(station, player, repo, parent=None)
    qtbot.addWidget(d)

    # Clear the bitrate cell (simulate user deleting the value)
    d.streams_table.item(0, _COL_BITRATE).setText("")

    d._on_save()

    assert repo.update_stream.called
    call = repo.update_stream.call_args
    assert call.kwargs.get("bitrate_kbps") == 0


def test_populated_bitrate_saves_as_int(qtbot, station, player, repo):
    """PB-17b: numeric cell text -> int(text) parsed and passed to update_stream."""
    repo.list_streams.return_value = [
        StationStream(id=10, station_id=1, url="http://s1", label="",
                      quality="hi", position=1, stream_type="",
                      codec="AAC", bitrate_kbps=320),
    ]
    from musicstreamer.ui_qt.edit_station_dialog import _COL_BITRATE

    d = EditStationDialog(station, player, repo, parent=None)
    qtbot.addWidget(d)

    d.streams_table.item(0, _COL_BITRATE).setText("192")
    d._on_save()

    call = repo.update_stream.call_args
    assert call.kwargs.get("bitrate_kbps") == 192
