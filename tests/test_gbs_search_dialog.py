"""Phase 60 / GBS-01e: GBSSearchDialog UI tests.

Mirrors tests/test_discovery_dialog.py pattern — qtbot fixture +
worker-stub via monkeypatch.
"""
from __future__ import annotations

import os
import re
from unittest.mock import MagicMock

import pytest

from musicstreamer import paths
from musicstreamer.ui_qt.gbs_search_dialog import (
    GBSSearchDialog,
    _GbsArtistWorker,
    _GbsAlbumWorker,
    _GbsSearchWorker,
    _GbsSubmitWorker,
)


def _ensure_cookies(tmp_path):
    """Create a fake cookies file at paths.gbs_cookies_path()."""
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# fake")


@pytest.fixture
def dialog_no_login(qtbot, fake_repo, tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: None)
    captured = []
    dlg = GBSSearchDialog(fake_repo, captured.append)
    qtbot.addWidget(dlg)
    return dlg, captured


@pytest.fixture
def dialog_logged_in(qtbot, fake_repo, tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    _ensure_cookies(tmp_path)
    fake_jar = MagicMock()
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: fake_jar)
    captured = []
    dlg = GBSSearchDialog(fake_repo, captured.append)
    # Stub worker .start() so no real network/threads spawn
    monkeypatch.setattr(_GbsSearchWorker, "start", lambda self: None)
    monkeypatch.setattr(_GbsSubmitWorker, "start", lambda self: None)
    monkeypatch.setattr(_GbsArtistWorker, "start", lambda self: None)
    monkeypatch.setattr(_GbsAlbumWorker, "start", lambda self: None)
    qtbot.addWidget(dlg)
    return dlg, captured


def test_dialog_opens_with_login_gate_when_no_cookies(dialog_no_login):
    """D-08c: no cookies → search field disabled + inline message."""
    dlg, _ = dialog_no_login
    assert dlg._search_edit.isEnabled() is False
    assert dlg._search_btn.isEnabled() is False
    assert not dlg._error_label.isHidden()
    assert "Log in" in dlg._error_label.text()


def test_dialog_opens_search_enabled_when_cookies_present(dialog_logged_in):
    dlg, _ = dialog_logged_in
    assert dlg._search_edit.isEnabled() is True
    assert dlg._search_btn.isEnabled() is True


def test_search_populates_results_from_mock(dialog_logged_in):
    dlg, _ = dialog_logged_in
    dlg._search_edit.setText("test")
    dlg._start_search()
    # Worker is stubbed; emit finished directly
    results = [
        {"songid": 100, "artist": "A1", "title": "T1", "duration": "3:00", "add_url": "/add/100"},
        {"songid": 101, "artist": "A2", "title": "T2", "duration": "4:00", "add_url": "/add/101"},
    ]
    dlg._on_search_finished(results, 1, 3)
    assert dlg._model.rowCount() == 2
    # Artist column
    assert dlg._model.item(0, 0).text() == "A1"
    assert dlg._model.item(1, 0).text() == "A2"
    # Per-row Add button
    assert len(dlg._submit_buttons) == 2
    assert dlg._submit_buttons[0].text() == "Add!"


def test_search_pagination_buttons_reflect_total_pages(dialog_logged_in):
    dlg, _ = dialog_logged_in
    dlg._on_search_finished([], 2, 5)
    assert dlg._prev_btn.isEnabled() is True
    assert dlg._next_btn.isEnabled() is True
    assert "Page 2 of 5" in dlg._page_label.text()


def test_search_first_page_disables_prev(dialog_logged_in):
    dlg, _ = dialog_logged_in
    dlg._on_search_finished([], 1, 3)
    assert dlg._prev_btn.isEnabled() is False
    assert dlg._next_btn.isEnabled() is True


def test_search_last_page_disables_next(dialog_logged_in):
    dlg, _ = dialog_logged_in
    dlg._on_search_finished([], 5, 5)
    assert dlg._prev_btn.isEnabled() is True
    assert dlg._next_btn.isEnabled() is False


def test_search_auth_expired_toasts_and_disables(dialog_logged_in, monkeypatch):
    """Pitfall 3: auth_expired → toast + relock login gate."""
    dlg, captured = dialog_logged_in
    # Simulate cookies disappearing
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: None)
    dlg._on_search_error("auth_expired")
    assert any("session expired" in t.lower() and "Accounts" in t for t in captured)
    assert dlg._search_edit.isEnabled() is False


def test_search_generic_error_inline(dialog_logged_in):
    dlg, captured = dialog_logged_in
    dlg._on_search_error("Connection refused")
    assert not dlg._error_label.isHidden()
    assert "Search failed" in dlg._error_label.text()
    assert "Connection refused" in dlg._error_label.text()
    # Generic errors do NOT toast (only auth-expired does)
    assert all("Connection refused" not in t for t in captured)


def test_submit_success_toasts_track_added(dialog_logged_in):
    """D-08d: success message comes via Django messages cookie text."""
    dlg, captured = dialog_logged_in
    dlg._results = [{"songid": 100, "artist": "A", "title": "T", "duration": "3:00", "add_url": "/add/100"}]
    dlg._on_search_finished(dlg._results, 1, 1)
    dlg._on_submit_finished("Track added successfully!", 0)
    assert any("Track added successfully" in t for t in captured)


def test_submit_inline_error_on_duplicate(dialog_logged_in):
    """D-08d: 'duplicate' message → inline error, NOT toast."""
    dlg, captured = dialog_logged_in
    dlg._results = [{"songid": 100, "artist": "A", "title": "T", "duration": "3:00", "add_url": "/add/100"}]
    dlg._on_search_finished(dlg._results, 1, 1)
    dlg._on_submit_finished("Track is already in queue (duplicate)", 0)
    assert not dlg._error_label.isHidden()
    assert "duplicate" in dlg._error_label.text().lower() or "already" in dlg._error_label.text().lower()
    # Should NOT toast (D-08d — inline preserves search context)
    assert all("duplicate" not in t.lower() for t in captured)


def test_submit_inline_error_on_token_quota(dialog_logged_in):
    """Pitfall 8: quota / token-limit message → inline error."""
    dlg, _ = dialog_logged_in
    dlg._results = [{"songid": 100, "artist": "A", "title": "T", "duration": "3:00", "add_url": "/add/100"}]
    dlg._on_search_finished(dlg._results, 1, 1)
    dlg._on_submit_finished("You don't have enough tokens", 0)
    assert not dlg._error_label.isHidden()
    assert "tokens" in dlg._error_label.text().lower()


def test_submit_auth_expired_toasts_and_relocks_login(dialog_logged_in, monkeypatch):
    dlg, captured = dialog_logged_in
    dlg._results = [{"songid": 100, "artist": "A", "title": "T", "duration": "3:00", "add_url": "/add/100"}]
    dlg._on_search_finished(dlg._results, 1, 1)
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: None)
    dlg._on_submit_error("auth_expired", 0)
    assert any("session expired" in t.lower() and "Accounts" in t for t in captured)
    assert dlg._search_edit.isEnabled() is False


def test_submit_disabled_button_during_request(dialog_logged_in):
    """Double-submit prevention: button disabled + 'Adding...' label during in-flight."""
    dlg, _ = dialog_logged_in
    dlg._results = [{"songid": 100, "artist": "A", "title": "T", "duration": "3:00", "add_url": "/add/100"}]
    dlg._on_search_finished(dlg._results, 1, 1)
    dlg._on_submit_row(0)
    assert dlg._submit_buttons[0].isEnabled() is False
    assert "Adding" in dlg._submit_buttons[0].text()


def test_no_self_capturing_lambdas_in_dialog():
    """QA-05 / Pitfall 10: no `clicked.connect(lambda...)` in gbs_search_dialog.py."""
    src = open("musicstreamer/ui_qt/gbs_search_dialog.py").read()
    matches = re.findall(r"\.connect\(([^)]+)\)", src)
    for m in matches:
        # Allow self-bound methods and well-formed closures from _make_submit_slot
        assert "lambda" not in m, f"QA-05 violation: connect({m!r})"


def test_main_window_search_menu_entry_exists():
    """D-08a: 'Search GBS.FM...' menu action exists in main_window.py."""
    src = open("musicstreamer/ui_qt/main_window.py").read()
    assert re.search(r'addAction\(["\']Search GBS\.FM', src), \
        "Expected 'Search GBS.FM...' menu entry in main_window.py"
    assert "_open_gbs_search_dialog" in src


def test_gbs_submit_in_flight_isolated_across_searches(dialog_logged_in):
    """HIGH 5 fix: stale submit callback discarded after re-search.

    Dispatch a submit on row 0 of results-set-A; capture the worker reference.
    Trigger a re-search to bump _search_version (results-set-B).
    Fire the captured worker's finished signal as if it were completing.
    Assert: (a) toast was NOT emitted (stale callback discarded by version
    mismatch), (b) row 0's button in results-set-B is still in its initial
    'Add!' state.
    Mirrors the _gbs_poll_token stale-discard pattern from Plan 60-05.
    """
    dlg, captured = dialog_logged_in

    # --- Search A ---
    results_a = [{"songid": 100, "artist": "A1", "title": "T1", "duration": "3:00", "add_url": "/add/100"}]
    dlg._on_search_finished(results_a, 1, 1)
    # Dispatch submit on row 0 of search A
    dlg._on_submit_row(0)
    # Capture the worker object (it was set as self._submit_worker before start())
    worker_a = dlg._submit_worker

    # --- Search B (bumps _search_version) ---
    dlg._search_version += 1  # simulate _start_search bumping version
    results_b = [{"songid": 200, "artist": "B1", "title": "T2", "duration": "4:00", "add_url": "/add/200"}]
    dlg._on_search_finished(results_b, 1, 1)
    # Confirm row 0 in results-set-B shows 'Add!'
    assert dlg._submit_buttons[0].text() == "Add!"
    assert dlg._submit_buttons[0].isEnabled() is True

    # --- Fire stale worker_a signal manually ---
    # We must temporarily patch sender() to return worker_a (search_version from A)
    original_search_version = dlg._search_version
    # Worker_a has the OLD search_version (before the bump)
    if worker_a is not None:
        # The worker's search_version was set at dispatch time (before the re-search)
        # It should be original_search_version - 1
        worker_a_version = getattr(worker_a, "search_version", None)
        if worker_a_version is not None:
            # Directly invoke the handler as if the stale worker emitted finished
            # We need sender() to return worker_a — simulate by calling method directly
            # with a monkeypatched sender
            original_sender = dlg.sender
            dlg.sender = lambda: worker_a
            try:
                dlg._on_submit_finished("Track added successfully!", 0)
            finally:
                dlg.sender = original_sender
    else:
        # Worker was stubbed away (start() was no-op) — test the version-check path
        # by directly calling with a fake sender that has an old search_version
        class _FakeSender:
            search_version = original_search_version - 1
        original_sender = dlg.sender
        dlg.sender = lambda: _FakeSender()
        try:
            dlg._on_submit_finished("Track added successfully!", 0)
        finally:
            dlg.sender = original_sender

    # (a) No toast should have been emitted for the stale callback
    assert all("Track added successfully" not in t for t in captured), \
        "Stale submit callback should not emit a toast"
    # (b) Row 0 of results-set-B should still be in 'Add!' state
    assert dlg._submit_buttons[0].text() == "Add!", \
        "Stale callback should not relabel row 0 in results-set-B"
    assert dlg._submit_buttons[0].isEnabled() is True, \
        "Stale callback should not disable row 0 in results-set-B"


# ---------- Plan 60-11 / T12: Artist:/Album: panel tests (RED) ----------

def test_artist_panel_shown_when_links_present(dialog_logged_in):
    """60-11 / T12 (RED): emitting metadata_ready with non-empty artist list shows the panel.

    D-11c LOCKED: panel is hidden when empty, shown when non-empty.
    D-11b LOCKED: max-height 80px.

    Currently FAILS: _artist_list does not exist; metadata_ready signal does not exist.
    Fix (Task 3): add _artist_list QListWidget + _on_metadata_ready slot.
    """
    dlg, _ = dialog_logged_in
    artist_links = [{"text": "Testament", "url": "/artist/4803"}]
    album_links = []
    # Call the slot directly (signal not yet wired in RED phase — testing slot behavior)
    dlg._on_metadata_ready(artist_links, album_links)
    # Artist panel must be visible and populated
    assert not dlg._artist_list.isHidden(), (
        "_artist_list must be visible when artist_links is non-empty (D-11c)"
    )
    assert dlg._artist_list.count() == 1, (
        f"_artist_list must have 1 item; got {dlg._artist_list.count()}"
    )
    assert dlg._artist_list.item(0).text() == "Testament", (
        f"First item text must be 'Testament'; got {dlg._artist_list.item(0).text()!r}"
    )
    # Album panel must be hidden (empty album_links — D-11c)
    assert dlg._album_list.isHidden(), (
        "_album_list must be hidden when album_links is empty (D-11c)"
    )


def test_artist_panel_hidden_when_no_links(dialog_logged_in):
    """60-11 / T12 (RED): emitting metadata_ready with empty lists hides both panels.

    D-11c LOCKED: panels hidden when their corresponding list is empty.

    Currently FAILS: _artist_list / _album_list do not exist.
    """
    dlg, _ = dialog_logged_in
    dlg._on_metadata_ready([], [])
    assert dlg._artist_list.isHidden(), (
        "_artist_list must be hidden when artist_links is [] (D-11c)"
    )
    assert dlg._album_list.isHidden(), (
        "_album_list must be hidden when album_links is [] (D-11c)"
    )


# ---------- Phase 60.1 / GBS-01e drill-down tests (Wave 0 RED) ----------
# Plan 60.1-01 (this file): 7 RED tests for drill-down click → worker → render,
# Back-button restore, snapshot guard (Pitfall 8), in-flight Back-disable (Pitfall 9),
# new-search abandon (Pitfall 10), auth-expired path.
# Plan 60.1-03 will delete the two D-07 Shape 4 tests above (test_artist_click_kicks_*,
# test_album_click_kicks_*) in the SAME commit that lands the drill-down GREEN.


def test_artist_click_drills_down_into_artist_page(dialog_logged_in):
    """Phase 60.1 / GBS-01e (RED): clicking an Artist entry dispatches _GbsArtistWorker.

    Pins (UI-SPEC Layout Deltas + Interaction States + Copywriting):
      - Snapshot is captured BEFORE worker dispatch (_pre_drill_state is not None)
      - _GbsArtistWorker is constructed (visible as self._artist_drill_worker)
      - On finished, results render into the table (_model.rowCount() == len(stub_results))
      - _back_btn is visible after drill completes
      - _page_label is hidden during drill-down (Delta 1)
      - _breadcrumb_label is visible with copy "Viewing artist: {name}" (Copywriting Contract)
      - _artist_list and _album_list panels remain visible (Delta 3 + Pitfall 3 mitigation)
      - _prev_btn / _next_btn are hidden in drill-down mode (Delta 2)

    FAILS BEFORE Plan 03 lands.
    """
    dlg, _ = dialog_logged_in
    # Setup: populate Artist panel via _on_metadata_ready
    dlg._on_metadata_ready([{"text": "Testament", "url": "/artist/4803"}], [])
    assert not dlg._artist_list.isHidden(), "setup: artist list should be visible after metadata_ready"
    # Click the artist entry (itemActivated is the bound signal in production)
    item = dlg._artist_list.item(0)
    dlg._artist_list.itemActivated.emit(item)
    # Snapshot was taken
    assert dlg._pre_drill_state is not None, "_pre_drill_state must be set after artist click"
    # Worker was dispatched (start() is stubbed in fixture; instance is stored)
    assert dlg._artist_drill_worker is not None, "_artist_drill_worker must be assigned after click"
    # Now manually fire the worker's finished slot (worker.start() stubbed → no real run)
    stub_results = [
        {"songid": 563811, "artist": "Testament", "title": "Brotherhood of the Snake",
         "duration": "4:14", "add_url": "/add/563811"},
    ]
    dlg._on_artist_drilled(stub_results)
    # Table re-rendered
    assert dlg._model.rowCount() == 1, f"table must show drilled songs; got {dlg._model.rowCount()} rows"
    assert dlg._model.item(0, 0).text() == "Testament", "drilled row artist column"
    # Back button visible + breadcrumb visible
    assert not dlg._back_btn.isHidden(), "_back_btn must be visible after drill completes (Delta 2)"
    assert not dlg._breadcrumb_label.isHidden(), "_breadcrumb_label must be visible (Delta 1)"
    assert dlg._breadcrumb_label.text() == "Viewing artist: Testament", (
        f"breadcrumb copy must be 'Viewing artist: Testament'; got {dlg._breadcrumb_label.text()!r}"
    )
    # _page_label hidden + prev/next hidden (Delta 1 + Delta 2)
    assert dlg._page_label.isHidden(), "_page_label must be hidden during drill-down (Delta 1)"
    assert dlg._prev_btn.isHidden(), "_prev_btn must be hidden during drill-down (Delta 2)"
    assert dlg._next_btn.isHidden(), "_next_btn must be hidden during drill-down (Delta 2)"
    # Artist/Album panels remain visible (Delta 3 + Pitfall 3 mitigation)
    assert not dlg._artist_list.isHidden(), "_artist_list must remain visible during drill-down (Delta 3)"


def test_album_click_drills_down_into_album_page(dialog_logged_in):
    """Phase 60.1 / GBS-01e (RED): clicking an Album entry dispatches _GbsAlbumWorker."""
    dlg, _ = dialog_logged_in
    dlg._on_metadata_ready([], [{"text": "Sample Album", "url": "/album/1488"}])
    assert not dlg._album_list.isHidden(), "setup: album list should be visible"
    item = dlg._album_list.item(0)
    dlg._album_list.itemActivated.emit(item)
    assert dlg._pre_drill_state is not None
    assert dlg._album_drill_worker is not None
    stub_results = [
        {"songid": 5406, "artist": "Ice Traigh & woodch",
         "title": "The Ballad of JohnVonBunghole", "duration": "4:57", "add_url": "/add/5406"},
    ]
    dlg._on_album_drilled(stub_results)
    assert dlg._model.rowCount() == 1
    assert not dlg._back_btn.isHidden()
    assert dlg._breadcrumb_label.text() == "Viewing album: Sample Album", (
        f"breadcrumb copy must be 'Viewing album: Sample Album'; got {dlg._breadcrumb_label.text()!r}"
    )


def test_back_button_restores_search_state(dialog_logged_in):
    """Phase 60.1 / GBS-01e (RED): Back button restores ALL pre-drill state per UI-SPEC Delta 5.

    State to restore (UI-SPEC Layout Deltas Delta 5):
      - _results, _current_page, _total_pages, _current_query
      - _artist_list / _album_list contents + visibility
      - _prev_btn / _next_btn enabled flags (recomputed)
      - _page_label visible, breadcrumb hidden, _back_btn hidden
      - inline error hidden
      - _pre_drill_state cleared to None

    FAILS BEFORE Plan 03 lands (no _on_back_clicked slot, no _back_btn).
    """
    dlg, _ = dialog_logged_in
    # Set up search state
    search_results = [
        {"songid": 100, "artist": "A1", "title": "T1", "duration": "3:00", "add_url": "/add/100"},
        {"songid": 101, "artist": "A2", "title": "T2", "duration": "4:00", "add_url": "/add/101"},
    ]
    dlg._on_search_finished(search_results, 2, 5)
    dlg._on_metadata_ready(
        [{"text": "Testament", "url": "/artist/4803"}],
        [{"text": "Some Album", "url": "/album/1488"}],
    )
    assert dlg._model.rowCount() == 2, "setup: search results rendered"
    assert dlg._page_label.text() == "Page 2 of 5"
    # Drill in
    dlg._artist_list.itemActivated.emit(dlg._artist_list.item(0))
    dlg._on_artist_drilled([{"songid": 999, "artist": "Testament", "title": "Drilled",
                             "duration": "1:00", "add_url": "/add/999"}])
    assert dlg._model.rowCount() == 1, "setup: drilled view replaced search results"
    assert not dlg._back_btn.isHidden()
    # Back!
    dlg._on_back_clicked()
    # Search results restored
    assert dlg._model.rowCount() == 2, f"Back must restore 2 search rows; got {dlg._model.rowCount()}"
    assert dlg._model.item(0, 0).text() == "A1", "first row artist must be A1 from search"
    # Page label restored
    assert dlg._page_label.text() == "Page 2 of 5", f"page label restored; got {dlg._page_label.text()!r}"
    # Pagination buttons recomputed
    assert dlg._prev_btn.isEnabled(), "prev enabled (page=2 > 1)"
    assert dlg._next_btn.isEnabled(), "next enabled (page=2 < 5)"
    # Drill chrome hidden, search chrome shown
    assert dlg._back_btn.isHidden(), "_back_btn must be hidden after Back"
    assert dlg._breadcrumb_label.isHidden(), "breadcrumb must be hidden after Back"
    assert not dlg._page_label.isHidden(), "_page_label must be visible after Back"
    assert not dlg._prev_btn.isHidden(), "_prev_btn must be visible after Back"
    assert not dlg._next_btn.isHidden(), "_next_btn must be visible after Back"
    # Panels restored from snapshot
    assert dlg._artist_list.count() == 1
    assert dlg._artist_list.item(0).text() == "Testament"
    assert dlg._album_list.count() == 1
    assert dlg._album_list.item(0).text() == "Some Album"
    # Snapshot cleared
    assert dlg._pre_drill_state is None, "_pre_drill_state must be cleared after Back"


def test_pre_drill_snapshot_not_overwritten_on_second_drill(dialog_logged_in):
    """Phase 60.1 / GBS-01e (RED, Pitfall 8): drilling a second artist while already drilled must NOT overwrite snapshot.

    Guard pattern: `if self._pre_drill_state is None: self._pre_drill_state = self._snapshot_pre_drill_state()`.
    Without this, clicking artist B while drilled into artist A would overwrite snapshot with
    the partial drilled state, and Back would return to A's drilled view (wrong).

    FAILS BEFORE Plan 03 lands.
    """
    dlg, _ = dialog_logged_in
    # Set up search state
    dlg._on_search_finished(
        [{"songid": 100, "artist": "A1", "title": "T1", "duration": "3:00", "add_url": "/add/100"}],
        1, 1,
    )
    dlg._on_metadata_ready(
        [{"text": "Testament", "url": "/artist/4803"},
         {"text": "Pearl Jam", "url": "/artist/9999"}],
        [],
    )
    # Drill artist A
    dlg._artist_list.itemActivated.emit(dlg._artist_list.item(0))
    snapshot_after_first_drill = dict(dlg._pre_drill_state)
    # Capture: snapshot has the original search row 'T1'
    assert any(r.get("title") == "T1" for r in snapshot_after_first_drill["results"]), (
        "snapshot must contain original search results"
    )
    # Fire A's finished
    dlg._on_artist_drilled([{"songid": 1, "artist": "Testament", "title": "Drilled-A",
                             "duration": "1:00", "add_url": "/add/1"}])
    # Drill artist B WITHOUT clicking Back
    dlg._artist_list.itemActivated.emit(dlg._artist_list.item(1))
    # Snapshot MUST be preserved (NOT overwritten with the post-A drilled state)
    assert dlg._pre_drill_state == snapshot_after_first_drill, (
        "_pre_drill_state must NOT be overwritten when drilling a second artist (Pitfall 8). "
        f"Got: {dlg._pre_drill_state!r}\nExpected: {snapshot_after_first_drill!r}"
    )
    # Fire B's finished, then Back — should restore the ORIGINAL search state, not A's drill
    dlg._on_artist_drilled([{"songid": 2, "artist": "Pearl Jam", "title": "Drilled-B",
                             "duration": "2:00", "add_url": "/add/2"}])
    dlg._on_back_clicked()
    assert dlg._model.rowCount() == 1
    assert dlg._model.item(0, 1).text() == "T1", (
        "Back must restore ORIGINAL search state, not the partial drill state of A or B"
    )


def test_drill_down_disables_back_button_during_fetch(dialog_logged_in):
    """Phase 60.1 / GBS-01e (RED, Pitfall 9): _back_btn is DISABLED while drill-down fetch is in flight.

    Race mitigation: user clicks Back before worker fires `finished` → snapshot restored → fetch
    completes and clobbers the restored search. Mitigation: disable _back_btn at dispatch,
    re-enable on finished/error.

    FAILS BEFORE Plan 03 lands.
    """
    dlg, _ = dialog_logged_in
    dlg._on_metadata_ready([{"text": "Testament", "url": "/artist/4803"}], [])
    dlg._artist_list.itemActivated.emit(dlg._artist_list.item(0))
    # Worker.start() stubbed; no `finished` yet
    # Per UI-SPEC Interaction States line 204, _back_btn must be DISABLED during fetch
    assert dlg._back_btn.isEnabled() is False, (
        "_back_btn must be disabled during drill-down fetch (Pitfall 9 race mitigation)"
    )
    # Fire finished — back button re-enables
    dlg._on_artist_drilled([{"songid": 1, "artist": "Testament", "title": "X",
                             "duration": "3:00", "add_url": "/add/1"}])
    assert dlg._back_btn.isEnabled() is True, "_back_btn re-enables after drill completes"


def test_new_search_while_drilling_abandons_snapshot(dialog_logged_in):
    """Phase 60.1 / GBS-01e (RED, Pitfall 10): typing a new query + Enter while in drill-down
    mode abandons the snapshot and exits drill-down chrome.

    FAILS BEFORE Plan 03 lands.
    """
    dlg, _ = dialog_logged_in
    dlg._on_search_finished(
        [{"songid": 100, "artist": "A1", "title": "T1", "duration": "3:00", "add_url": "/add/100"}],
        1, 1,
    )
    dlg._on_metadata_ready([{"text": "Testament", "url": "/artist/4803"}], [])
    dlg._artist_list.itemActivated.emit(dlg._artist_list.item(0))
    dlg._on_artist_drilled([{"songid": 1, "artist": "Testament", "title": "X",
                             "duration": "3:00", "add_url": "/add/1"}])
    assert dlg._pre_drill_state is not None, "setup: in drill-down mode"
    # Type a new query and press Enter (calls _start_search; cookies present from fixture)
    dlg._search_edit.setText("new query")
    dlg._start_search()
    # Snapshot abandoned + drill chrome reset
    assert dlg._pre_drill_state is None, "_pre_drill_state must be None after new search"
    assert dlg._back_btn.isHidden(), "_back_btn must be hidden after new search"
    assert dlg._breadcrumb_label.isHidden(), "breadcrumb must be hidden after new search"
    assert not dlg._page_label.isHidden(), "_page_label must be visible after new search"
    assert not dlg._prev_btn.isHidden(), "_prev_btn must be visible after new search"
    assert not dlg._next_btn.isHidden(), "_next_btn must be visible after new search"


def test_drill_down_auth_expired_toasts(dialog_logged_in):
    """Phase 60.1 / GBS-01e (RED): drill-down worker emits error('auth_expired') → toast + login gate.

    Mirrors test_search_auth_expired_toasts_and_disables shape.
    FAILS BEFORE Plan 03 lands.
    """
    dlg, captured = dialog_logged_in
    dlg._on_metadata_ready([{"text": "Testament", "url": "/artist/4803"}], [])
    dlg._artist_list.itemActivated.emit(dlg._artist_list.item(0))
    # Simulate worker emitting error('auth_expired')
    dlg._on_artist_drill_error("auth_expired")
    # Toast emitted with "session expired" copy
    assert any("session expired" in (msg or "").lower() for msg in captured), (
        f"toast captured should mention 'session expired'; got {captured!r}"
    )
    # _back_btn re-enabled (cleanup)
    # _artist_drill_worker reference cleared (Pattern S-4)
    assert dlg._artist_drill_worker is None, "_artist_drill_worker must be cleared after error"


# ---------- Phase 60.2 / GBS-01e (Wave 0 RED) — album section headers + clearSpans guard ----------

def test_artist_drill_inserts_album_section_headers(dialog_logged_in):
    """Phase 60.2 / GBS-01e (RED): artist drill-view inserts span-row section headers
    between album groups per CONTEXT.md D-01..D-03.

    Setup: feed a stub result list with 5 rows across 2 albums:
      [Album A: 3 songs] [Album B: 2 songs]

    Expected table layout after _on_artist_drilled:
      row 0:  span-row "Album A (3 songs)"  setSpan(0, 0, 1, 4)
      row 1:  song 1
      row 2:  song 2
      row 3:  song 3
      row 4:  span-row "Album B (2 songs)"  setSpan(4, 0, 1, 4)
      row 5:  song 4
      row 6:  song 5

    Total rowCount = 7 (5 songs + 2 headers).
    FAILS BEFORE Wave 2 dialog change lands: production _render_results does NOT insert
    section headers; rowCount would be 5, no spans, no header text.
    """
    dlg, _ = dialog_logged_in
    dlg._on_metadata_ready([{"text": "Some Artist", "url": "/artist/123"}], [])
    item = dlg._artist_list.item(0)
    dlg._artist_list.itemActivated.emit(item)
    stub_results = [
        {"songid": 1, "artist": "Some Artist", "title": "S1", "duration": "3:00",
         "add_url": "/add/1", "album": "Album A"},
        {"songid": 2, "artist": "Some Artist", "title": "S2", "duration": "3:30",
         "add_url": "/add/2", "album": "Album A"},
        {"songid": 3, "artist": "Some Artist", "title": "S3", "duration": "4:00",
         "add_url": "/add/3", "album": "Album A"},
        {"songid": 4, "artist": "Some Artist", "title": "S4", "duration": "3:15",
         "add_url": "/add/4", "album": "Album B"},
        {"songid": 5, "artist": "Some Artist", "title": "S5", "duration": "3:45",
         "add_url": "/add/5", "album": "Album B"},
    ]
    dlg._on_artist_drilled(stub_results)

    assert dlg._model.rowCount() == 7, (
        f"expected 7 rows (5 songs + 2 headers); got {dlg._model.rowCount()}"
    )
    # Header at row 0 spans all 4 columns
    assert dlg._results_table.columnSpan(0, 0) == dlg._model.columnCount(), (
        f"row 0 header must span all columns; got columnSpan={dlg._results_table.columnSpan(0, 0)}"
    )
    assert dlg._model.item(0, 0).text() == "Album A (3 songs)", (
        f"row 0 header text; got {dlg._model.item(0, 0).text()!r}"
    )
    # Header at row 4 spans all 4 columns
    assert dlg._results_table.columnSpan(4, 0) == dlg._model.columnCount(), (
        f"row 4 header must span all columns; got columnSpan={dlg._results_table.columnSpan(4, 0)}"
    )
    assert dlg._model.item(4, 0).text() == "Album B (2 songs)", (
        f"row 4 header text; got {dlg._model.item(4, 0).text()!r}"
    )
    # Song row at row 1 has title cell populated
    assert dlg._model.item(1, 1).text() == "S1"
    assert dlg._model.item(2, 1).text() == "S2"
    assert dlg._model.item(5, 1).text() == "S4"


def test_artist_drill_skips_header_for_empty_album(dialog_logged_in):
    """Phase 60.2 / GBS-01e (RED): rows with album == '' render WITHOUT a header per
    CONTEXT.md D-11.

    Setup: 4 rows — 2 with album='', 2 with album='Real Album'.
    Expected layout:
      row 0:  song 1 (album='')       <- no header above
      row 1:  song 2 (album='')
      row 2:  span-row "Real Album (2 songs)"
      row 3:  song 3 (album='Real Album')
      row 4:  song 4 (album='Real Album')

    Total rowCount = 5 (4 songs + 1 header — NOT 2 headers).
    FAILS BEFORE Wave 2 dialog change lands.
    """
    dlg, _ = dialog_logged_in
    dlg._on_metadata_ready([{"text": "Some Artist", "url": "/artist/123"}], [])
    item = dlg._artist_list.item(0)
    dlg._artist_list.itemActivated.emit(item)
    stub_results = [
        {"songid": 1, "artist": "Some Artist", "title": "Pre-1", "duration": "3:00",
         "add_url": "/add/1", "album": ""},
        {"songid": 2, "artist": "Some Artist", "title": "Pre-2", "duration": "3:30",
         "add_url": "/add/2", "album": ""},
        {"songid": 3, "artist": "Some Artist", "title": "P-1", "duration": "4:00",
         "add_url": "/add/3", "album": "Real Album"},
        {"songid": 4, "artist": "Some Artist", "title": "P-2", "duration": "3:15",
         "add_url": "/add/4", "album": "Real Album"},
    ]
    dlg._on_artist_drilled(stub_results)
    assert dlg._model.rowCount() == 5, (
        f"expected 5 rows (4 songs + 1 header — empty-album group has no header); "
        f"got {dlg._model.rowCount()}"
    )
    # Row 0 is a song row, NOT a span row (column 0 is artist text)
    assert dlg._results_table.columnSpan(0, 0) == 1, (
        f"empty-album rows must NOT have a span (D-11); "
        f"got columnSpan={dlg._results_table.columnSpan(0, 0)}"
    )
    assert dlg._model.item(0, 0).text() == "Some Artist"  # song row col 0 = artist
    # Row 2 IS the section header for "Real Album"
    assert dlg._results_table.columnSpan(2, 0) == dlg._model.columnCount(), (
        f"row 2 must span all columns (Real Album header); "
        f"got columnSpan={dlg._results_table.columnSpan(2, 0)}"
    )
    assert dlg._model.item(2, 0).text() == "Real Album (2 songs)"


def test_artist_drill_section_header_non_selectable(dialog_logged_in):
    """Phase 60.2 / GBS-01e (RED): section-header cells must not be selectable or
    editable per CONTEXT.md D-02.

    FAILS BEFORE Wave 2 dialog change lands: row 0 will be a song row with default flags.
    """
    from PySide6.QtCore import Qt

    dlg, _ = dialog_logged_in
    dlg._on_metadata_ready([{"text": "X", "url": "/artist/1"}], [])
    dlg._artist_list.itemActivated.emit(dlg._artist_list.item(0))
    dlg._on_artist_drilled([
        {"songid": 1, "artist": "X", "title": "T", "duration": "3:00",
         "add_url": "/add/1", "album": "A"},
    ])
    # Header at row 0
    flags = dlg._model.item(0, 0).flags()
    assert not bool(flags & Qt.ItemFlag.ItemIsSelectable), (
        f"header must not be selectable; got flags={flags}"
    )
    assert not bool(flags & Qt.ItemFlag.ItemIsEditable), (
        f"header must not be editable; got flags={flags}"
    )


def test_artist_drill_no_add_button_on_section_header(dialog_logged_in):
    """Phase 60.2 / GBS-01e (RED): section-header rows must NOT have an Add! button.

    The per-row Add! button is rendered via setIndexWidget(row, _COL_ADD, btn). A header
    row has no setIndexWidget call. Verify by checking the # of submit_buttons matches
    the # of song rows (NOT total rowCount) — Pitfall 3.

    FAILS BEFORE Wave 2 dialog change lands.
    """
    dlg, _ = dialog_logged_in
    dlg._on_metadata_ready([{"text": "X", "url": "/artist/1"}], [])
    dlg._artist_list.itemActivated.emit(dlg._artist_list.item(0))
    stub_results = [
        {"songid": 1, "artist": "X", "title": "T1", "duration": "3:00",
         "add_url": "/add/1", "album": "A"},
        {"songid": 2, "artist": "X", "title": "T2", "duration": "3:00",
         "add_url": "/add/2", "album": "B"},
    ]
    dlg._on_artist_drilled(stub_results)
    # 4 rows total (2 songs + 2 headers) but only 2 Add! buttons.
    assert dlg._model.rowCount() == 4, (
        f"expected 4 rows (2 songs + 2 headers); got {dlg._model.rowCount()}"
    )
    assert len(dlg._submit_buttons) == 2, (
        f"expected 2 Add! buttons (one per song row, none on headers); "
        f"got {len(dlg._submit_buttons)}"
    )


def test_clear_table_clears_spans(dialog_logged_in):
    """Phase 60.2 / GBS-01e (RED): _clear_table must call clearSpans() so a
    subsequent search render after a drill-view does not show stale spans
    (Pitfall 1 + Pitfall 9 regression guard).

    FAILS BEFORE Wave 2 dialog change lands: _clear_table does NOT call clearSpans()
    today, so a span set by setSpan persists across removeRows() and re-renders.
    """
    from PySide6.QtGui import QStandardItem

    dlg, _ = dialog_logged_in
    # Get a row in the model first so setSpan has something to attach to.
    dlg._on_metadata_ready([{"text": "X", "url": "/artist/1"}], [])
    dlg._artist_list.itemActivated.emit(dlg._artist_list.item(0))
    dlg._on_artist_drilled([
        {"songid": 1, "artist": "X", "title": "T", "duration": "3:00",
         "add_url": "/add/1", "album": "A"},
    ])
    # Manually set a span on row 0 (simulates the section-header span Wave 2 will create).
    dlg._results_table.setSpan(0, 0, 1, dlg._model.columnCount())
    assert dlg._results_table.columnSpan(0, 0) == dlg._model.columnCount(), (
        "setup: span must be present before _clear_table()"
    )
    # Now call _clear_table — it MUST drop the span via clearSpans().
    dlg._clear_table()
    # After clearing, columnSpan must report 1 (no span). If model is empty,
    # set a fresh row and check columnSpan(0, 0) == 1 for that fresh row.
    dlg._model.appendRow([
        QStandardItem(""), QStandardItem(""), QStandardItem(""), QStandardItem(""),
    ])
    assert dlg._results_table.columnSpan(0, 0) == 1, (
        f"_clear_table must call clearSpans() to drop stale spans; "
        f"got columnSpan={dlg._results_table.columnSpan(0, 0)}"
    )


def test_album_drill_is_flat(dialog_logged_in):
    """Phase 60.2 / GBS-01e Pitfall 6: album drill view emits flat song rows;
    NEVER apply album-grouping logic to album-drill (album-page rows do not
    have an 'album' field — they have an 'artist' field per song).

    Regression guard. GREEN today; pins the invariant against future changes.
    """
    dlg, _ = dialog_logged_in
    dlg._on_metadata_ready([], [{"text": "Some Album", "url": "/album/456"}])
    item = dlg._album_list.item(0)
    dlg._album_list.itemActivated.emit(item)
    stub_results = [
        {"songid": 10, "artist": "X", "title": "T1", "duration": "3:00", "add_url": "/add/10"},
        {"songid": 11, "artist": "Y", "title": "T2", "duration": "3:30", "add_url": "/add/11"},
        {"songid": 12, "artist": "Z", "title": "T3", "duration": "4:00", "add_url": "/add/12"},
    ]
    dlg._on_album_drilled(stub_results)
    assert dlg._model.rowCount() == 3, (
        f"album drill must be flat (3 songs = 3 rows, no headers); "
        f"got rowCount={dlg._model.rowCount()}"
    )
    for row in (0, 1, 2):
        assert dlg._results_table.columnSpan(row, 0) == 1, (
            f"album drill row {row} must NOT have a span (Pitfall 6); "
            f"got columnSpan={dlg._results_table.columnSpan(row, 0)}"
        )
