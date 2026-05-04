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
