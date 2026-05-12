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
    # Phase 51-03 (W4 fix): _populate now calls _refresh_siblings ->
    # repo.list_stations(). Default to empty so existing tests deterministically
    # hit the "no siblings" path. Tests that need siblings override this in-test.
    r.list_stations.return_value = []
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


def test_bitrate_delegate_persists_empty_string_on_commit(qtbot, station, player, repo):
    """Gap-closure (UAT gap 1): driving the _BitrateDelegate full edit cycle
    with an empty editor must land an empty string on the item (not revert
    to the pre-edit value), so the save path's int(text or "0") coerces to 0.

    Regression for: user clears a Bitrate cell, presses Enter/Tab, cell
    reverts to its prior value instead of saving as 0.
    """
    from PySide6.QtWidgets import QStyleOptionViewItem
    from musicstreamer.ui_qt.edit_station_dialog import _COL_BITRATE

    repo.list_streams.return_value = [
        StationStream(id=10, station_id=1, url="http://s1", label="",
                      quality="hi", position=1, stream_type="",
                      codec="AAC", bitrate_kbps=320),
    ]

    d = EditStationDialog(station, player, repo, parent=None)
    qtbot.addWidget(d)

    delegate = d.streams_table.itemDelegateForColumn(_COL_BITRATE)
    assert delegate is not None, "bitrate column must have a custom delegate"

    index = d.streams_table.model().index(0, _COL_BITRATE)
    editor = delegate.createEditor(d.streams_table, QStyleOptionViewItem(), index)
    editor.setText("")  # user cleared the cell

    delegate.setModelData(editor, d.streams_table.model(), index)

    # CORE ASSERTION — the cleared value must reach the item, not revert.
    assert d.streams_table.item(0, _COL_BITRATE).text() == ""

    d._on_save()

    assert repo.update_stream.called
    call = repo.update_stream.call_args
    assert call.kwargs.get("bitrate_kbps") == 0


# ---------------------------------------------------------------------------
# Phase 999.1 Wave 0 — Add-New-Station primary-action test stubs (RED).
# These tests exercise the `is_new=True` EditStationDialog mode introduced by
# Plan 01 and the SAVE-CLEANUP flag flip. They are expected to FAIL until
# Plan 01 lands; do not fix production code from this plan.
# ---------------------------------------------------------------------------


@pytest.fixture()
def fresh_station():
    """A brand-new placeholder Station — provider unset, no streams, no tags.

    Mirrors what `repo.create_station()` would hand EditStationDialog in
    is_new mode: id=42, name="New Station" (the repo-assigned placeholder),
    provider_id=None, provider_name=None, streams=[], tags="".
    """
    return Station(
        id=42,
        name="New Station",
        provider_id=None,
        provider_name=None,
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        icy_disabled=False,
        streams=[],
    )


def test_is_new_mode_constructs_and_populates(qtbot, station, player, repo):
    """D-03b: constructing with is_new=True sets _is_new and populates the name."""
    d = EditStationDialog(station, player, repo, is_new=True)
    qtbot.addWidget(d)
    assert d._is_new is True
    assert d.name_edit.text() == station.name


def test_is_new_mode_pre_adds_blank_stream_row(qtbot, fresh_station, player, repo):
    """D-05: is_new mode with zero streams pre-adds one blank URL row."""
    # Fresh placeholder — no streams from repo.
    repo.list_streams.return_value = []
    d = EditStationDialog(fresh_station, player, repo, is_new=True)
    qtbot.addWidget(d)
    assert d.streams_table.rowCount() == 1
    # URL cell (column 0) must be empty string.
    cell = d.streams_table.item(0, 0)
    assert cell is None or cell.text() == ""


def test_reject_in_new_mode_deletes_placeholder(qtbot, station, player, repo):
    """D-04a: rejecting (Cancel) in is_new mode deletes the placeholder station."""
    station.id = 42
    d = EditStationDialog(station, player, repo, is_new=True)
    qtbot.addWidget(d)
    d.reject()
    repo.delete_station.assert_called_once_with(42)


def test_close_in_new_mode_deletes_placeholder(qtbot, station, player, repo):
    """D-04b: closing the dialog (X button / close()) in is_new mode deletes the placeholder."""
    station.id = 42
    d = EditStationDialog(station, player, repo, is_new=True)
    qtbot.addWidget(d)
    d.close()
    repo.delete_station.assert_called_once_with(42)


def test_reject_in_edit_mode_does_not_delete(qtbot, station, player, repo):
    """D-04c (REGRESSION GUARD): the default edit-mode path must NOT delete on reject."""
    d = EditStationDialog(station, player, repo)  # default: is_new absent/False
    qtbot.addWidget(d)
    d.reject()
    assert repo.delete_station.call_count == 0


def test_new_mode_empty_name_blocks_save(qtbot, station, player, repo, monkeypatch):
    """D-06: in is_new mode, blank name blocks save and surfaces a warning dialog."""
    from PySide6.QtWidgets import QMessageBox

    warning_calls: list = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda *a, **kw: warning_calls.append((a, kw)) or QMessageBox.Ok),
    )

    d = EditStationDialog(station, player, repo, is_new=True)
    qtbot.addWidget(d)
    d.name_edit.setText("")
    d._on_save()

    assert repo.update_station.call_count == 0
    assert len(warning_calls) == 1


def test_new_mode_provider_combo_blank(qtbot, fresh_station, player, repo):
    """D-08: is_new mode with no provider leaves the provider combo text blank."""
    d = EditStationDialog(fresh_station, player, repo, is_new=True)
    qtbot.addWidget(d)
    assert d.provider_combo.currentText() == ""


def test_save_clears_is_new_flag_to_prevent_delete_on_close(qtbot, station, player, repo):
    """SAVE-CLEANUP: a successful save must flip _is_new=False so a later
    reject()/close() does not delete the (now persisted) station."""
    station.id = 42
    d = EditStationDialog(station, player, repo, is_new=True)
    qtbot.addWidget(d)
    d.name_edit.setText("Saved Name")
    d._on_save()
    # The dialog has closed from the user's perspective; the close cleanup path
    # must see _is_new=False and NOT call delete_station.
    d.reject()
    assert repo.delete_station.call_count == 0


# ---------------------------------------------------------------------------
# Phase 51-02 / D-11 / D-12 — EditStationDialog._is_dirty() snapshot predicate.
#
# These tests assert the dialog-level dirty-state mechanism that Plan 51-04
# will use to gate the Save / Discard / Cancel confirm when the user clicks
# a sibling "Also on:" link. Scope: name, URL, provider, tags, ICY, streams.
# The `_is_new` lifecycle flag is orthogonal and untouched.
# ---------------------------------------------------------------------------


def test_is_dirty_false_after_populate(dialog):
    """D-12: a freshly populated dialog reports clean (no edits)."""
    assert dialog._is_dirty() is False


def test_is_dirty_after_name_edit(dialog):
    """D-12: editing the name field marks the dialog dirty."""
    dialog.name_edit.setText("New Name")
    assert dialog._is_dirty() is True


def test_is_dirty_after_url_edit(dialog):
    """D-12: editing the URL field marks the dialog dirty."""
    dialog.url_edit.setText("http://other.example/stream")
    assert dialog._is_dirty() is True


def test_is_dirty_after_provider_change(dialog):
    """D-12: changing the provider combo marks the dialog dirty."""
    dialog.provider_combo.setCurrentText("Other")
    assert dialog._is_dirty() is True


def test_is_dirty_after_tag_toggle(dialog):
    """D-12: toggling a tag chip from selected -> unselected marks dirty."""
    # The `station` fixture has tags="jazz,electronic" — chips render selected.
    jazz_chip = dialog._tag_chips["jazz"]
    assert jazz_chip.property("chipState") == "selected"
    jazz_chip.click()  # toggles to unselected
    assert jazz_chip.property("chipState") == "unselected"
    assert dialog._is_dirty() is True


def test_is_dirty_after_icy_toggle(dialog):
    """D-12: flipping the ICY checkbox marks the dialog dirty."""
    initial = dialog.icy_checkbox.isChecked()
    dialog.icy_checkbox.setChecked(not initial)
    assert dialog._is_dirty() is True


def test_is_dirty_after_stream_cell_edit(dialog):
    """D-12: editing a cell in the streams table marks the dialog dirty."""
    from PySide6.QtWidgets import QTableWidgetItem

    table = dialog.streams_table
    assert table.rowCount() >= 1, "fixture must populate at least one stream row"

    cell = table.item(0, 0)
    if cell is None:
        table.setItem(0, 0, QTableWidgetItem("http://changed.example/stream"))
    else:
        cell.setText("http://changed.example/stream")
    assert dialog._is_dirty() is True


def test_is_dirty_after_stream_row_added(dialog):
    """D-12: adding a new stream row marks the dialog dirty.

    Also exercises the orthogonality of _is_new — calling _add_stream_row()
    on an existing-station dialog (is_new=False) must flip _is_dirty() to
    True. The is_new placeholder branch in __init__ re-captures the
    baseline AFTER its own _add_stream_row() so a fresh `is_new` dialog
    is still clean — that contract is verified separately by the existing
    `test_is_new_mode_pre_adds_blank_stream_row` plus the clean-baseline
    test above (constructed via the default `dialog` fixture which is
    is_new=False).
    """
    initial_rows = dialog.streams_table.rowCount()
    dialog._add_stream_row()
    assert dialog.streams_table.rowCount() == initial_rows + 1
    assert dialog._is_dirty() is True


# ---------------------------------------------------------------------------
# Phase 51-03 / D-04..D-08 — cross-network "Also on:" sibling label.
#
# These tests cover the rendering surface added in Plan 51-03: hide for
# non-AA stations, hide when no siblings, render with Qt.RichText <a> links
# when siblings exist, link-text format (network-only when names match,
# "Network — SiblingName" otherwise), and the html.escape mitigation for
# the T-39-01 deviation.
# ---------------------------------------------------------------------------


def _make_aa_station(station_id, name, url):
    """Factory: a minimal Station with one stream at `url`.

    Used by the sibling-label tests below to construct AA-flavored
    stations whose first stream URL drives find_aa_siblings.
    """
    return Station(
        id=station_id,
        name=name,
        provider_id=1,
        provider_name="DI.fm",
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        icy_disabled=False,
        streams=[
            StationStream(
                id=station_id * 10,
                station_id=station_id,
                url=url,
                position=1,
            )
        ],
    )


@pytest.fixture()
def aa_repo():
    r = MagicMock()
    r.list_providers.return_value = [Provider(1, "DI.fm")]
    # Default: no other stations in the library — sibling label hidden.
    # Tests that need siblings override list_stations.return_value in-test.
    r.list_stations.return_value = []
    # _populate calls list_streams for the current station (used to set url_edit).
    r.list_streams.return_value = [
        StationStream(
            id=10,
            station_id=1,
            url="http://prem1.di.fm:80/ambient_hi?listen_key=abc",
            position=1,
        )
    ]
    r.ensure_provider.return_value = 1
    return r


@pytest.fixture()
def aa_station():
    return _make_aa_station(
        1, "Ambient", "http://prem1.di.fm:80/ambient_hi?listen_key=abc"
    )


@pytest.fixture()
def aa_dialog(qtbot, aa_station, player, aa_repo):
    d = EditStationDialog(aa_station, player, aa_repo, parent=None)
    qtbot.addWidget(d)
    return d


def test_sibling_section_hidden_for_non_aa_station(qtbot, player):
    """D-04, D-06: a non-AA URL never derives siblings -> label hidden.

    Uses isHidden() rather than isVisible() so the assertion does not
    depend on the dialog being shown by the windowing system (parent
    hidden -> isVisible() is False even when setVisible(True) was called).
    isHidden() reflects the explicit setVisible(False) state directly.
    """
    non_aa = _make_aa_station(
        1, "Whatever", "https://www.youtube.com/watch?v=xyz"
    )
    repo = MagicMock()
    repo.list_providers.return_value = [Provider(1, "YouTube")]
    repo.list_streams.return_value = [
        StationStream(
            id=10,
            station_id=1,
            url="https://www.youtube.com/watch?v=xyz",
            position=1,
        )
    ]
    repo.list_stations.return_value = [non_aa]
    repo.ensure_provider.return_value = 1
    d = EditStationDialog(non_aa, player, repo, parent=None)
    qtbot.addWidget(d)
    assert d._sibling_label.isHidden() is True


def test_sibling_section_hidden_when_no_siblings(aa_dialog):
    """D-06: AA station, no other AA stations on other networks -> hidden."""
    # aa_repo.list_stations.return_value = [] by default.
    assert aa_dialog._sibling_label.isHidden() is True


def test_sibling_section_renders_links_for_aa_station_with_siblings(
    qtbot, player, aa_repo, aa_station
):
    """D-04, D-07: AA station with cross-network sibling -> label visible
    with <a href="sibling://..."> link to the sibling's network name."""
    zenradio_sibling = _make_aa_station(
        2, "Ambient", "http://prem1.zenradio.com/zrambient?listen_key=abc"
    )
    aa_repo.list_stations.return_value = [aa_station, zenradio_sibling]
    d = EditStationDialog(aa_station, player, aa_repo, parent=None)
    qtbot.addWidget(d)
    # isHidden() is False because _refresh_siblings called setVisible(True).
    # isVisible() would require the parent dialog to actually be shown by
    # the WM, which qtbot.addWidget does not do.
    assert d._sibling_label.isHidden() is False
    text = d._sibling_label.text()
    assert "Also on:" in text
    assert 'href="sibling://2"' in text
    assert "ZenRadio" in text


def test_sibling_link_text_uses_network_name_when_station_names_match(
    qtbot, player, aa_repo, aa_station
):
    """D-08: when current and sibling names match, link text is just the
    network display name (no em-dash, no station name)."""
    zenradio_sibling = _make_aa_station(
        2, "Ambient", "http://prem1.zenradio.com/zrambient?listen_key=abc"
    )
    aa_repo.list_stations.return_value = [aa_station, zenradio_sibling]
    d = EditStationDialog(aa_station, player, aa_repo, parent=None)
    qtbot.addWidget(d)
    text = d._sibling_label.text()
    # The em-dash (U+2014) only appears in the differing-names form.
    assert "—" not in text
    assert ">ZenRadio</a>" in text


def test_sibling_link_text_uses_network_dash_name_when_station_names_differ(
    qtbot, player, aa_repo, aa_station
):
    """D-08: when names differ, link text is "Network — SiblingName" with
    U+2014 EM DASH and surrounding spaces."""
    zenradio_sibling = _make_aa_station(
        2,
        "Ambient (Sleep)",
        "http://prem1.zenradio.com/zrambient?listen_key=abc",
    )
    aa_repo.list_stations.return_value = [aa_station, zenradio_sibling]
    d = EditStationDialog(aa_station, player, aa_repo, parent=None)
    qtbot.addWidget(d)
    text = d._sibling_label.text()
    assert "ZenRadio — Ambient (Sleep)" in text


def test_sibling_html_escapes_station_name(
    qtbot, player, aa_repo, aa_station
):
    """T-39-01 deviation mitigation: a malicious sibling station name must
    be HTML-escaped in the rendered RichText label so script tags are
    rendered as text, not parsed by Qt."""
    evil_sibling = _make_aa_station(
        2,
        "<script>alert(1)</script>",
        "http://prem1.zenradio.com/zrambient?listen_key=abc",
    )
    aa_repo.list_stations.return_value = [aa_station, evil_sibling]
    d = EditStationDialog(aa_station, player, aa_repo, parent=None)
    qtbot.addWidget(d)
    text = d._sibling_label.text()
    # Raw <script> tag must NOT appear; escaped form MUST appear.
    assert "<script>" not in text
    assert "&lt;script&gt;" in text


# ---------------------------------------------------------------------------
# Phase 51-04: navigate_to_sibling click handler — clean, Save, Discard, Cancel,
# malformed href.
# ---------------------------------------------------------------------------


def test_link_activated_emits_navigate_to_sibling_when_clean(
    qtbot, player, aa_repo, aa_station
):
    """SC #2: clicking a sibling link on a clean dialog emits the signal immediately."""
    zenradio_sibling = _make_aa_station(
        2, "Ambient", "http://prem1.zenradio.com/zrambient?listen_key=abc"
    )
    aa_repo.list_stations.return_value = [aa_station, zenradio_sibling]
    d = EditStationDialog(aa_station, player, aa_repo, parent=None)
    qtbot.addWidget(d)
    # Sanity: dialog is clean (Plan 51-02 baseline captured at end of _populate)
    assert d._is_dirty() is False

    with qtbot.waitSignal(d.navigate_to_sibling, timeout=1000) as blocker:
        d._on_sibling_link_activated("sibling://2")
    assert blocker.args == [2]


def test_link_activated_save_path_emits_when_save_succeeds(
    qtbot, player, aa_repo, aa_station, monkeypatch
):
    """D-11 Save path: dirty + valid → save runs, signal fires."""
    from PySide6.QtWidgets import QMessageBox

    zenradio_sibling = _make_aa_station(
        2, "Ambient", "http://prem1.zenradio.com/zrambient?listen_key=abc"
    )
    aa_repo.list_stations.return_value = [aa_station, zenradio_sibling]
    d = EditStationDialog(aa_station, player, aa_repo, parent=None)
    qtbot.addWidget(d)
    # Make dirty by editing the name (still valid — non-empty)
    d.name_edit.setText("Ambient (renamed)")
    assert d._is_dirty() is True

    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **kw: QMessageBox.StandardButton.Save),
    )

    with qtbot.waitSignal(d.navigate_to_sibling, timeout=1000) as blocker:
        d._on_sibling_link_activated("sibling://2")
    assert blocker.args == [2]
    assert aa_repo.update_station.called


def test_link_activated_save_path_does_not_emit_when_save_fails(
    qtbot, player, aa_repo, aa_station, monkeypatch
):
    """D-11 Save path: validation failure (empty name) → warning, NO navigate."""
    from PySide6.QtWidgets import QMessageBox

    zenradio_sibling = _make_aa_station(
        2, "Ambient", "http://prem1.zenradio.com/zrambient?listen_key=abc"
    )
    aa_repo.list_stations.return_value = [aa_station, zenradio_sibling]
    d = EditStationDialog(aa_station, player, aa_repo, parent=None)
    qtbot.addWidget(d)
    d.name_edit.setText("")
    assert d._is_dirty() is True

    warning_calls: list = []
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **kw: QMessageBox.StandardButton.Save),
    )
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(
            lambda *a, **kw: warning_calls.append((a, kw)) or QMessageBox.Ok
        ),
    )

    emitted: list = []
    d.navigate_to_sibling.connect(lambda sid: emitted.append(sid))
    d._on_sibling_link_activated("sibling://2")
    assert len(warning_calls) == 1
    assert emitted == []
    assert d._save_succeeded is False


def test_link_activated_discard_path_emits_without_saving(
    qtbot, player, aa_repo, aa_station, monkeypatch
):
    """D-11 Discard path: emit signal, no save attempted, reject() runs."""
    from PySide6.QtWidgets import QMessageBox

    zenradio_sibling = _make_aa_station(
        2, "Ambient", "http://prem1.zenradio.com/zrambient?listen_key=abc"
    )
    aa_repo.list_stations.return_value = [aa_station, zenradio_sibling]
    d = EditStationDialog(aa_station, player, aa_repo, parent=None)
    qtbot.addWidget(d)
    d.name_edit.setText("Ambient (renamed)")
    assert d._is_dirty() is True

    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **kw: QMessageBox.StandardButton.Discard),
    )

    with qtbot.waitSignal(d.navigate_to_sibling, timeout=1000) as blocker:
        d._on_sibling_link_activated("sibling://2")
    assert blocker.args == [2]
    assert not aa_repo.update_station.called


def test_link_activated_cancel_path_no_signal(
    qtbot, player, aa_repo, aa_station, monkeypatch
):
    """D-11 Cancel path: no signal, no save, dialog stays open."""
    from PySide6.QtWidgets import QMessageBox

    zenradio_sibling = _make_aa_station(
        2, "Ambient", "http://prem1.zenradio.com/zrambient?listen_key=abc"
    )
    aa_repo.list_stations.return_value = [aa_station, zenradio_sibling]
    d = EditStationDialog(aa_station, player, aa_repo, parent=None)
    qtbot.addWidget(d)
    d.name_edit.setText("Ambient (renamed)")
    assert d._is_dirty() is True

    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **kw: QMessageBox.StandardButton.Cancel),
    )

    emitted: list = []
    d.navigate_to_sibling.connect(lambda sid: emitted.append(sid))
    d._on_sibling_link_activated("sibling://2")
    assert emitted == []
    assert not aa_repo.update_station.called
    # Dialog is still open (not accepted, not rejected)
    assert d.result() == 0


def test_link_activated_ignores_malformed_href(aa_dialog):
    """Defensive: malformed hrefs are silently ignored (no exception, no signal)."""
    emitted: list = []
    aa_dialog.navigate_to_sibling.connect(lambda sid: emitted.append(sid))
    aa_dialog._on_sibling_link_activated("not://a/sibling")
    aa_dialog._on_sibling_link_activated("sibling://notanint")
    aa_dialog._on_sibling_link_activated("")
    assert emitted == []


# ----------------------------------------------------------------------
# Phase 58 / STR-15: PLS Auto-Resolve flow
# ----------------------------------------------------------------------


def test_add_pls_button_exists(dialog):
    """D-01: add_pls_btn exists with correct label (U+2026) and tooltip."""
    assert hasattr(dialog, "add_pls_btn")
    assert dialog.add_pls_btn.text() == "Add from PLS…"
    tooltip = dialog.add_pls_btn.toolTip()
    assert "PLS" in tooltip
    assert "M3U" in tooltip
    assert "M3U8" in tooltip
    assert "XSPF" in tooltip


def test_add_pls_worker_starts_on_valid_url(qtbot, monkeypatch, dialog):
    """D-02/D-04: a valid URL kicks off _PlaylistFetchWorker and disables the button."""
    from unittest.mock import MagicMock
    import musicstreamer.ui_qt.edit_station_dialog as esd_mod

    fake_worker_instance = MagicMock()
    fake_worker_instance.isRunning.return_value = False
    fake_worker_cls = MagicMock(return_value=fake_worker_instance)
    monkeypatch.setattr(esd_mod, "_PlaylistFetchWorker", fake_worker_cls)
    monkeypatch.setattr(
        esd_mod.QInputDialog,
        "getText",
        staticmethod(lambda *a, **kw: ("http://host/playlist.pls", True)),
    )

    dialog._on_add_pls()

    fake_worker_cls.assert_called_once()
    # First positional arg is the URL (stripped)
    assert fake_worker_cls.call_args.args[0] == "http://host/playlist.pls"
    fake_worker_instance.start.assert_called_once()
    assert dialog.add_pls_btn.isEnabled() is False


def test_add_pls_cancel_is_noop(qtbot, monkeypatch, dialog):
    """D-02: Cancel in QInputDialog is a complete no-op — worker not started, button stays enabled."""
    from unittest.mock import MagicMock
    import musicstreamer.ui_qt.edit_station_dialog as esd_mod

    fake_worker_cls = MagicMock()
    monkeypatch.setattr(esd_mod, "_PlaylistFetchWorker", fake_worker_cls)
    monkeypatch.setattr(
        esd_mod.QInputDialog,
        "getText",
        staticmethod(lambda *a, **kw: ("", False)),
    )

    dialog._on_add_pls()

    fake_worker_cls.assert_not_called()
    assert dialog.add_pls_btn.isEnabled() is True


def test_add_pls_empty_url_is_noop(qtbot, monkeypatch, dialog):
    """D-02: whitespace-only URL with ok=True is treated as empty — no-op."""
    from unittest.mock import MagicMock
    import musicstreamer.ui_qt.edit_station_dialog as esd_mod

    fake_worker_cls = MagicMock()
    monkeypatch.setattr(esd_mod, "_PlaylistFetchWorker", fake_worker_cls)
    monkeypatch.setattr(
        esd_mod.QInputDialog,
        "getText",
        staticmethod(lambda *a, **kw: ("   ", True)),
    )

    dialog._on_add_pls()

    fake_worker_cls.assert_not_called()
    assert dialog.add_pls_btn.isEnabled() is True


def test_on_pls_fetched_restores_cursor_first_unconditionally(qtbot, monkeypatch, dialog):
    """D-03/D-10: cursor restore + button re-enable happen BEFORE stale-token check."""
    import musicstreamer.ui_qt.edit_station_dialog as esd_mod

    restore_count = []
    monkeypatch.setattr(
        esd_mod.QApplication,
        "restoreOverrideCursor",
        staticmethod(lambda: restore_count.append(True)),
    )
    # Stale token — emission's token (1) does not match dialog's current (5)
    dialog._pls_fetch_token = 5

    dialog._on_pls_fetched([], "", token=1)

    # Cursor restored even though emission is stale (D-03/D-10)
    assert len(restore_count) == 1
    assert dialog.add_pls_btn.isEnabled() is True


def test_on_pls_fetched_failure_shows_warning_and_leaves_table_unchanged(
    qtbot, monkeypatch, dialog
):
    """D-05: HTTP error shows QMessageBox.warning and leaves the streams table unchanged."""
    from PySide6.QtWidgets import QMessageBox

    warning_calls: list = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda *a, **kw: warning_calls.append((a, kw)) or QMessageBox.Ok),
    )

    dialog._add_stream_row("http://existing.example", "Q", "MP3", 128, 1)
    rows_before = dialog.streams_table.rowCount()

    dialog._pls_fetch_token = 1
    dialog._on_pls_fetched([], "HTTP 404: Not Found", token=1)

    assert len(warning_calls) == 1
    warning_args = warning_calls[0][0]
    assert any("HTTP 404" in str(arg) for arg in warning_args)
    assert dialog.streams_table.rowCount() == rows_before  # table unchanged


def test_on_pls_fetched_empty_table_silent_append(qtbot, monkeypatch, dialog):
    """D-06 Branch C: success on empty table → silent append without any QMessageBox."""
    from unittest.mock import MagicMock
    import musicstreamer.ui_qt.edit_station_dialog as esd_mod

    # Ensure table is empty (default dialog has 1 pre-existing stream row from repo fixture)
    dialog.streams_table.setRowCount(0)
    assert dialog.streams_table.rowCount() == 0

    # QMessageBox should NOT be invoked at all
    mock_qmb = MagicMock()
    monkeypatch.setattr(esd_mod, "QMessageBox", mock_qmb)

    dialog._pls_fetch_token = 1
    dialog._on_pls_fetched(
        [{"url": "http://x", "title": "T", "bitrate_kbps": 128, "codec": "MP3"}],
        "",
        token=1,
    )

    assert dialog.streams_table.rowCount() == 1
    mock_qmb.assert_not_called()


def test_on_pls_fetched_replace_clears_existing_rows(qtbot, dialog):
    """D-06/D-07: _apply_pls_entries with mode='replace' clears the table then inserts new rows."""
    dialog._add_stream_row("http://old1", "Q1", "MP3", 128, 1)
    dialog._add_stream_row("http://old2", "Q2", "AAC", 192, 2)
    assert dialog.streams_table.rowCount() >= 2  # at least 2 user-added rows

    dialog._apply_pls_entries(
        [{"url": "http://new", "title": "N", "bitrate_kbps": 192, "codec": "AAC"}],
        mode="replace",
    )

    assert dialog.streams_table.rowCount() == 1
    assert dialog.streams_table.item(0, 0).text() == "http://new"


def test_on_pls_fetched_append_preserves_existing_rows(qtbot, dialog):
    """D-06/D-08: append mode continues position numbering from max(existing) + 1."""
    # Clear default rows and add exactly 2 rows with positions 1, 2
    dialog.streams_table.setRowCount(0)
    dialog._add_stream_row("http://old1", "Q1", "MP3", 128, 1)
    dialog._add_stream_row("http://old2", "Q2", "AAC", 192, 2)
    assert dialog.streams_table.rowCount() == 2

    entries = [
        {"url": "http://new1", "title": "", "bitrate_kbps": 0, "codec": ""},
        {"url": "http://new2", "title": "", "bitrate_kbps": 0, "codec": ""},
    ]
    dialog._apply_pls_entries(entries, mode="append")

    assert dialog.streams_table.rowCount() == 4
    from musicstreamer.ui_qt.edit_station_dialog import _COL_POSITION
    assert dialog.streams_table.item(2, _COL_POSITION).text() == "3"
    assert dialog.streams_table.item(3, _COL_POSITION).text() == "4"


def test_apply_pls_entries_columns_mapped_correctly(qtbot, dialog):
    """D-11/D-14/D-15/D-16: resolved entry dict keys map to the correct table columns."""
    from musicstreamer.ui_qt.edit_station_dialog import (
        _COL_URL, _COL_QUALITY, _COL_CODEC, _COL_BITRATE, _COL_POSITION,
    )
    dialog.streams_table.setRowCount(0)
    dialog._apply_pls_entries(
        [
            {"url": "http://s.aac", "title": "AAC 128k", "bitrate_kbps": 128, "codec": "AAC"},
            {"url": "http://s.no-meta", "title": "", "bitrate_kbps": 0, "codec": ""},
        ],
        mode="append",
    )

    assert dialog.streams_table.rowCount() == 2

    # Row 0: fully-populated entry
    assert dialog.streams_table.item(0, _COL_URL).text() == "http://s.aac"
    assert dialog.streams_table.item(0, _COL_QUALITY).text() == "AAC 128k"
    assert dialog.streams_table.item(0, _COL_CODEC).text() == "AAC"
    assert dialog.streams_table.item(0, _COL_BITRATE).text() == "128"
    assert dialog.streams_table.item(0, _COL_POSITION).text() == "1"

    # Row 1: empty-meta entry — codec and bitrate render as blank (D-15/D-16)
    assert dialog.streams_table.item(1, _COL_URL).text() == "http://s.no-meta"
    assert dialog.streams_table.item(1, _COL_QUALITY).text() == ""
    assert dialog.streams_table.item(1, _COL_CODEC).text() == ""
    assert dialog.streams_table.item(1, _COL_BITRATE).text() == ""
    assert dialog.streams_table.item(1, _COL_POSITION).text() == "2"


def test_apply_pls_entries_trips_dirty_state(qtbot, dialog):
    """D-Discretion / Phase 51-02: inserting resolved rows trips _is_dirty()."""
    dialog._capture_dirty_baseline()
    assert dialog._is_dirty() is False

    dialog._apply_pls_entries(
        [{"url": "http://x", "title": "", "bitrate_kbps": 0, "codec": ""}],
        mode="append",
    )

    assert dialog._is_dirty() is True


def test_shutdown_pls_fetch_worker_called_from_accept_close_reject():
    """_shutdown_pls_fetch_worker must appear in accept, closeEvent, and reject (bb1c518 fix)."""
    import inspect
    from musicstreamer.ui_qt.edit_station_dialog import EditStationDialog

    for method_name in ("accept", "closeEvent", "reject"):
        method = getattr(EditStationDialog, method_name)
        src = inspect.getsource(method)
        assert "_shutdown_pls_fetch_worker" in src, (
            f"{method_name}() does not call _shutdown_pls_fetch_worker — "
            f"missing teardown will cause QThread destroy crash (commit bb1c518)"
        )


def test_pls_fetch_token_monotonically_increments(qtbot, monkeypatch, dialog):
    """D-04: _pls_fetch_token increments with each _on_add_pls call."""
    from unittest.mock import MagicMock
    import musicstreamer.ui_qt.edit_station_dialog as esd_mod

    assert dialog._pls_fetch_token == 0

    fake_worker_instance = MagicMock()
    fake_worker_instance.isRunning.return_value = False
    fake_worker_cls = MagicMock(return_value=fake_worker_instance)
    monkeypatch.setattr(esd_mod, "_PlaylistFetchWorker", fake_worker_cls)
    monkeypatch.setattr(
        esd_mod.QInputDialog,
        "getText",
        staticmethod(lambda *a, **kw: ("http://host/a.pls", True)),
    )

    # Re-enable the button between calls to simulate two independent invocations
    dialog._on_add_pls()
    assert dialog._pls_fetch_token == 1

    dialog.add_pls_btn.setEnabled(True)
    dialog._on_add_pls()
    assert dialog._pls_fetch_token == 2


def test_on_pls_fetched_stale_token_does_not_modify_table(qtbot, monkeypatch, dialog):
    """Stale emission (token != _pls_fetch_token) must not modify the streams table."""
    import musicstreamer.ui_qt.edit_station_dialog as esd_mod

    # Silence cursor restore to avoid Qt state side effects
    monkeypatch.setattr(
        esd_mod.QApplication,
        "restoreOverrideCursor",
        staticmethod(lambda: None),
    )

    dialog.streams_table.setRowCount(0)
    dialog._add_stream_row("http://existing", "Q", "MP3", 128, 1)
    assert dialog.streams_table.rowCount() == 1

    dialog._pls_fetch_token = 5
    # Emit with stale token=1 (not 5)
    dialog._on_pls_fetched(
        [{"url": "http://stale", "title": "", "bitrate_kbps": 0, "codec": ""}],
        "",
        token=1,
    )

    assert dialog.streams_table.rowCount() == 1  # unchanged


# ---------------------------------------------------------------------------
# Regression: stream-remove-not-persisted (bug fix)
#
# When the user removes a stream row from the table and clicks Save, the
# row must be deleted from the DB. Previously _on_save called only
# repo.reorder_streams() which updates positions but never deletes rows —
# removed streams silently survived in the DB.
# ---------------------------------------------------------------------------


def test_save_calls_prune_streams_with_remaining_ids(qtbot, station, player, repo):
    """_on_save must call repo.prune_streams(station_id, ordered_ids) so that
    streams the user removed from the UI table are deleted from the DB.

    This is the direct regression guard for the stream-remove-not-persisted bug.
    The mock repo's update_stream returns None and insert_stream returns a fresh
    int, so we can inspect the prune_streams call args precisely.
    """
    # Two streams loaded: id=10 (kept) and id=11 (user will remove)
    repo.list_streams.return_value = [
        StationStream(id=10, station_id=1, url="http://s1.mp3",
                      label="", quality="hi", position=1,
                      stream_type="", codec="MP3"),
        StationStream(id=11, station_id=1, url="http://s2.mp3",
                      label="", quality="med", position=2,
                      stream_type="", codec="MP3"),
    ]
    d = EditStationDialog(station, player, repo, parent=None)
    qtbot.addWidget(d)

    # Verify both rows loaded
    assert d.streams_table.rowCount() == 2

    # Remove row 1 (stream id=11)
    d.streams_table.selectRow(1)
    d._on_remove_stream()
    assert d.streams_table.rowCount() == 1

    # Save
    d._on_save()

    # prune_streams must have been called with only the kept stream id
    repo.prune_streams.assert_called_once()
    call_args = repo.prune_streams.call_args
    station_id_arg, keep_ids_arg = call_args.args
    assert station_id_arg == station.id
    assert 10 in keep_ids_arg
    assert 11 not in keep_ids_arg


def test_save_calls_prune_streams_when_all_streams_removed(qtbot, station, player, repo):
    """Edge case: user removes ALL streams. prune_streams must be called with
    an empty keep_ids list so all DB rows are cleared."""
    repo.list_streams.return_value = [
        StationStream(id=10, station_id=1, url="http://s1.mp3",
                      label="", quality="hi", position=1,
                      stream_type="", codec="MP3"),
    ]
    d = EditStationDialog(station, player, repo, parent=None)
    qtbot.addWidget(d)

    # Remove the only row
    d.streams_table.selectRow(0)
    d._on_remove_stream()
    assert d.streams_table.rowCount() == 0

    d._on_save()

    repo.prune_streams.assert_called_once()
    call_args = repo.prune_streams.call_args
    station_id_arg, keep_ids_arg = call_args.args
    assert station_id_arg == station.id
    assert keep_ids_arg == []


# ---------------------------------------------------------------------------
# Phase 70 / HRES-01: Audio quality column (read-only, prose tier label)
# ---------------------------------------------------------------------------
#
# RED stubs for the new "Audio quality" column. Plan 70-08 ships:
#   - _COL_AUDIO_QUALITY = 5 (new module-level column index)
#   - read-only cell (no Qt.ItemIsEditable flag)
#   - prose label from TIER_LABEL_PROSE ("Hi-Res", "Lossless", "")
#   - header tooltip locked by UI-SPEC OD-8
#
# Distinct from existing _COL_QUALITY (user-authored "FLAC 1411") — the new
# column is auto-derived from cached sample_rate_hz / bit_depth per stream.


def test_audio_quality_column_present_and_read_only(qtbot, station, player, repo):
    """HRES-01 / Plan 70-08: _COL_AUDIO_QUALITY column exists and is read-only.

    Cell flags MUST NOT include Qt.ItemIsEditable; auto-derived data cannot be
    user-edited (UI-SPEC FLAG-03).
    """
    repo.list_streams.return_value = [
        StationStream(id=10, station_id=1, url="http://s1", label="",
                      quality="FLAC 1411", position=1, stream_type="",
                      codec="FLAC", bitrate_kbps=1411),
    ]
    # RED: ImportError until Plan 70-08 introduces _COL_AUDIO_QUALITY.
    from musicstreamer.ui_qt.edit_station_dialog import _COL_AUDIO_QUALITY

    d = EditStationDialog(station, player, repo, parent=None)
    qtbot.addWidget(d)

    item = d.streams_table.item(0, _COL_AUDIO_QUALITY)
    assert item is not None
    from PySide6.QtCore import Qt
    # Read-only: ItemIsEditable bit MUST NOT be set.
    assert not bool(item.flags() & Qt.ItemFlag.ItemIsEditable)


def test_audio_quality_cell_shows_prose_label(qtbot, station, player, repo):
    """HRES-01 / Plan 70-08 / UI-SPEC Copywriting Contract: cell text uses
    title-case TIER_LABEL_PROSE — 'Hi-Res', 'Lossless', '' (empty for lossy).

    Three streams cover the truth table. The MP3 row uses bitrate 96 kbps to
    land in the "no badge" branch — the post-UAT D-04 revision treats lossy
    at bitrate > 128 kbps as Hi-Res (mirrors moOde RADIO_BITRATE_THRESHOLD).
    A 320 kbps MP3 is covered by test_audio_quality_cell_shows_hires_for_high_bitrate_lossy.
    """
    repo.list_streams.return_value = [
        StationStream(
            id=10, station_id=1, url="http://s1", label="",
            quality="FLAC 96/24", position=1, stream_type="",
            codec="FLAC", bitrate_kbps=2304,
            sample_rate_hz=96000, bit_depth=24,
        ),
        StationStream(
            id=11, station_id=1, url="http://s2", label="",
            quality="FLAC 1411", position=2, stream_type="",
            codec="FLAC", bitrate_kbps=1411,
            sample_rate_hz=44100, bit_depth=16,
        ),
        StationStream(
            id=12, station_id=1, url="http://s3", label="",
            quality="MP3 96", position=3, stream_type="",
            codec="MP3", bitrate_kbps=96,
        ),
    ]
    from musicstreamer.ui_qt.edit_station_dialog import _COL_AUDIO_QUALITY

    d = EditStationDialog(station, player, repo, parent=None)
    qtbot.addWidget(d)

    assert d.streams_table.item(0, _COL_AUDIO_QUALITY).text() == "Hi-Res"
    assert d.streams_table.item(1, _COL_AUDIO_QUALITY).text() == "Lossless"
    # MP3 at 96 kbps is below the 128-kbps moOde RADIO_BITRATE_THRESHOLD, so
    # the lossy branch returns "" (empty prose label).
    assert d.streams_table.item(2, _COL_AUDIO_QUALITY).text() == ""


def test_audio_quality_cell_shows_hires_for_high_bitrate_lossy(qtbot, station, player, repo):
    """HRES-01 / Plan 70-08 / D-04 revised post-UAT: lossy at bitrate > 128
    kbps renders 'Hi-Res' in the Audio quality column (matches the moOde
    radio-station badge logic — RADIO_BITRATE_THRESHOLD = 128 in
    playerlib.js)."""
    repo.list_streams.return_value = [
        StationStream(
            id=20, station_id=1, url="http://di-lounge", label="",
            quality="MP3 320K", position=1, stream_type="",
            codec="MP3", bitrate_kbps=320,
        ),
        StationStream(
            id=21, station_id=1, url="http://aac-256", label="",
            quality="AAC 256K", position=2, stream_type="",
            codec="AAC", bitrate_kbps=256,
        ),
        StationStream(
            id=22, station_id=1, url="http://mp3-128", label="",
            quality="MP3 128K", position=3, stream_type="",
            codec="MP3", bitrate_kbps=128,
        ),
    ]
    from musicstreamer.ui_qt.edit_station_dialog import _COL_AUDIO_QUALITY

    d = EditStationDialog(station, player, repo, parent=None)
    qtbot.addWidget(d)

    assert d.streams_table.item(0, _COL_AUDIO_QUALITY).text() == "Hi-Res"
    assert d.streams_table.item(1, _COL_AUDIO_QUALITY).text() == "Hi-Res"
    # 128 kbps lies exactly at threshold; moOde uses strict > not >=.
    assert d.streams_table.item(2, _COL_AUDIO_QUALITY).text() == ""


def test_audio_quality_header_tooltip(qtbot, station, player, repo):
    """HRES-01 / Plan 70-08 / UI-SPEC OD-8: header text 'Audio quality' (Sentence
    case) + tooltip prose locked verbatim:
      'Auto-detected from playback. Hi-Res >= 48 kHz or >= 24-bit on a lossless codec.'

    Stored as a horizontal header item so QHeaderView surfaces the tooltip via
    the toolTip role.
    """
    repo.list_streams.return_value = [
        StationStream(id=10, station_id=1, url="http://s1", label="",
                      quality="FLAC 1411", position=1, stream_type="",
                      codec="FLAC", bitrate_kbps=1411),
    ]
    from musicstreamer.ui_qt.edit_station_dialog import _COL_AUDIO_QUALITY

    d = EditStationDialog(station, player, repo, parent=None)
    qtbot.addWidget(d)

    header_item = d.streams_table.horizontalHeaderItem(_COL_AUDIO_QUALITY)
    # RED: pre-70-08 there is no header item at this column index.
    assert header_item is not None
    assert header_item.text() == "Audio quality"
    expected_tooltip = (
        "Auto-detected from playback. "
        "Hi-Res ≥ 48 kHz or ≥ 24-bit on a lossless codec."
    )
    assert header_item.toolTip() == expected_tooltip


# ---------------------------------------------------------------------------
# Phase 71 / Plan 71-03: chip row + sibling_toast Signal RED tests
# ---------------------------------------------------------------------------
# 6 RED tests for EditStationDialog chip-row behavior. Today these fail because
# the production widgets do not exist yet (Plan 71-03 implements them).
# Mappings: D-11, D-14, D-15, Navigation invariant from 71-VALIDATION.md.

from PySide6.QtWidgets import QPushButton, QWidget  # noqa: E402 — append-only section


@pytest.fixture()
def repo_with_siblings(repo):
    """Extends the existing MagicMock `repo` fixture with sibling-CRUD mocks.

    MagicMock auto-mocks attribute access, but the .return_value defaults to
    a MagicMock object (not [] / None) — explicit return values make tests
    deterministic.
    """
    repo.list_sibling_links.return_value = []
    repo.add_sibling_link.return_value = None
    repo.remove_sibling_link.return_value = None
    return repo


def test_add_sibling_button_present(qtbot, station, player, repo_with_siblings):
    """D-11: '+ Add sibling' button (objectName "add_sibling_btn") is present
    in the chip row after dialog construction."""
    d = EditStationDialog(station, player, repo_with_siblings, parent=None)
    qtbot.addWidget(d)
    btn = d.findChild(QPushButton, "add_sibling_btn")
    assert btn is not None


def test_manual_chip_has_x_button(qtbot, aa_repo, aa_station, player):
    """D-14: manual sibling chip is a compound widget objectName
    "sibling_chip_<id>" containing TWO QPushButtons (name + "×")."""
    # Seed a second station (id=42) that is manually linked.
    partner = _make_aa_station(42, "Manual Partner",
                               "http://prem4.zenradio.com/zrambient?listen_key=abc")
    aa_repo.list_stations.return_value = [aa_station, partner]
    aa_repo.list_sibling_links = MagicMock(return_value=[42])
    aa_repo.add_sibling_link = MagicMock(return_value=None)
    aa_repo.remove_sibling_link = MagicMock(return_value=None)
    d = EditStationDialog(aa_station, player, aa_repo, parent=None)
    qtbot.addWidget(d)
    chip = d.findChild(QWidget, "sibling_chip_42")
    assert chip is not None
    buttons = chip.findChildren(QPushButton)
    assert len(buttons) >= 2
    # Second button is the "×" unlink trigger (UI-SPEC line 188).
    assert any(b.text() == "×" for b in buttons)


def test_aa_chip_has_no_x_button(qtbot, aa_repo, aa_station, player):
    """D-15: AA auto-detected chip is a bare QPushButton with NO "×".

    AA chips have objectName "sibling_aa_chip_<id>" and NO compound
    "sibling_chip_<id>" wrapper.
    """
    zr_sibling = _make_aa_station(
        2, "Ambient",
        "http://prem4.zenradio.com/zrambient?listen_key=abc",
    )
    aa_repo.list_stations.return_value = [aa_station, zr_sibling]
    aa_repo.list_sibling_links = MagicMock(return_value=[])  # no manual links
    aa_repo.add_sibling_link = MagicMock(return_value=None)
    aa_repo.remove_sibling_link = MagicMock(return_value=None)
    d = EditStationDialog(aa_station, player, aa_repo, parent=None)
    qtbot.addWidget(d)
    # AA chip MUST NOT have the compound sibling_chip_ wrapper.
    assert d.findChild(QWidget, "sibling_chip_2") is None


def test_x_click_calls_remove_sibling_link(qtbot, aa_repo, aa_station, player):
    """D-14: clicking the × button calls Repo.remove_sibling_link(self.id, sibling_id)."""
    partner = _make_aa_station(42, "Manual Partner",
                               "http://prem4.zenradio.com/zrambient?listen_key=abc")
    aa_repo.list_stations.return_value = [aa_station, partner]
    aa_repo.list_sibling_links = MagicMock(return_value=[42])
    aa_repo.add_sibling_link = MagicMock(return_value=None)
    aa_repo.remove_sibling_link = MagicMock(return_value=None)
    d = EditStationDialog(aa_station, player, aa_repo, parent=None)
    qtbot.addWidget(d)
    chip = d.findChild(QWidget, "sibling_chip_42")
    assert chip is not None
    # Find the × button — UI-SPEC lines 188-200: name button first, "×" second.
    unlink_btn = next(b for b in chip.findChildren(QPushButton) if b.text() == "×")
    unlink_btn.click()
    assert aa_repo.remove_sibling_link.call_args == call(aa_station.id, 42)


def test_x_click_fires_unlinked_toast(qtbot, aa_repo, aa_station, player):
    """D-14: clicking × emits sibling_toast(str) with text matching '^Unlinked from '."""
    import re
    partner = _make_aa_station(42, "Manual Partner",
                               "http://prem4.zenradio.com/zrambient?listen_key=abc")
    aa_repo.list_stations.return_value = [aa_station, partner]
    aa_repo.list_sibling_links = MagicMock(return_value=[42])
    aa_repo.add_sibling_link = MagicMock(return_value=None)
    aa_repo.remove_sibling_link = MagicMock(return_value=None)
    d = EditStationDialog(aa_station, player, aa_repo, parent=None)
    qtbot.addWidget(d)
    emitted = []
    d.sibling_toast.connect(emitted.append)
    chip = d.findChild(QWidget, "sibling_chip_42")
    unlink_btn = next(b for b in chip.findChildren(QPushButton) if b.text() == "×")
    unlink_btn.click()
    assert len(emitted) == 1
    assert re.match(r"^Unlinked from ", emitted[0])


def test_chip_click_emits_navigate_signal(qtbot, aa_repo, aa_station, player):
    """Navigation invariant: clicking the chip's name button emits
    navigate_to_sibling(int) with the sibling's station_id."""
    partner = _make_aa_station(42, "Manual Partner",
                               "http://prem4.zenradio.com/zrambient?listen_key=abc")
    aa_repo.list_stations.return_value = [aa_station, partner]
    aa_repo.list_sibling_links = MagicMock(return_value=[42])
    aa_repo.add_sibling_link = MagicMock(return_value=None)
    aa_repo.remove_sibling_link = MagicMock(return_value=None)
    d = EditStationDialog(aa_station, player, aa_repo, parent=None)
    qtbot.addWidget(d)
    emitted = []
    d.navigate_to_sibling.connect(emitted.append)
    chip = d.findChild(QWidget, "sibling_chip_42")
    # The name button is the one whose text is the station name (not "×").
    name_btn = next(b for b in chip.findChildren(QPushButton) if b.text() != "×")
    name_btn.click()
    assert emitted == [42]
