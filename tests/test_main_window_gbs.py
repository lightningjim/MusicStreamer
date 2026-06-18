"""Phase 60 / GBS-01a UI: hamburger menu wiring + worker flow + idempotent toasts.

Mirrors tests/ui_qt/test_main_window_node_indicator.py shape — direct MainWindow
construction with FakePlayer + FakeRepo doubles (no qtbot-injected monkeypatching
on the constructor itself). Tests exercise the GBS.FM handler methods directly
after the widget is up.
"""
from __future__ import annotations

import re
from unittest.mock import MagicMock

import pytest

from musicstreamer.ui_qt.main_window import MainWindow, _GbsImportWorker
from tests._fake_player import FakePlayer as _FakePlayer


class _FakeRepo:
    def __init__(self) -> None:
        self._settings: dict = {}

    def list_stations(self) -> list:
        return []

    def list_recently_played(self, n: int = 3) -> list:
        return []

    def get_setting(self, key: str, default=None):
        return self._settings.get(key, default)

    def set_setting(self, key: str, value) -> None:
        self._settings[key] = value

    def update_last_played(self, station_id: int) -> None:
        pass

    def set_station_favorite(self, station_id: int, is_favorite: bool) -> None:
        pass

    def is_favorite_station(self, station_id: int) -> bool:
        return False

    def list_favorite_stations(self) -> list:
        return []

    def list_favorites(self) -> list:
        return []

    def is_favorited(self, station_name: str, track_title: str) -> bool:
        return False

    def add_favorite(self, *args, **kwargs) -> None:
        pass

    def remove_favorite(self, *args, **kwargs) -> None:
        pass

    def list_streams(self, station_id: int) -> list:
        return []

    def list_providers(self) -> list:
        return []

    def get_station(self, station_id: int):
        return None

    def create_station(self) -> int:
        return 1

    def delete_station(self, station_id: int) -> None:
        pass


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def main_window(qtbot):
    """Construct a MainWindow with FakePlayer + FakeRepo doubles."""
    w = MainWindow(_FakePlayer(), _FakeRepo())
    qtbot.addWidget(w)
    return w


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_action(window, text: str):
    for action in window._menu.actions():
        if action.text() == text:
            return action
    return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_add_gbs_menu_entry_exists(main_window):
    """D-02: 'Add GBS.FM' menu entry is rendered in the hamburger menu."""
    action = _find_action(main_window, "Add GBS.FM")
    assert action is not None, "Expected 'Add GBS.FM' menu entry"
    assert action.isEnabled(), "D-02b: menu entry must always be enabled"


def test_add_gbs_triggers_worker_start(main_window, monkeypatch):
    """D-02: click should start a _GbsImportWorker."""
    started = {"flag": False}
    real_init = _GbsImportWorker.__init__

    def fake_init(self, parent=None):
        real_init(self, parent=parent)

    def fake_start(self):
        started["flag"] = True

    monkeypatch.setattr(_GbsImportWorker, "__init__", fake_init)
    monkeypatch.setattr(_GbsImportWorker, "start", fake_start)
    main_window._on_gbs_add_clicked()
    assert started["flag"] is True
    assert main_window._gbs_import_worker is not None


def test_import_finished_toasts_added_on_first_call(main_window, monkeypatch):
    """D-02a: finished(1, 0) -> 'GBS.FM added' toast."""
    captured = {}
    monkeypatch.setattr(main_window, "show_toast",
                        lambda text, *a, **kw: captured.setdefault("text", text))
    monkeypatch.setattr(main_window, "_refresh_station_list", lambda: None)
    main_window._gbs_import_worker = MagicMock()
    main_window._on_gbs_import_finished(1, 0)
    assert captured["text"] == "GBS.FM added"
    assert main_window._gbs_import_worker is None


def test_import_finished_toasts_updated_on_refresh(main_window, monkeypatch):
    """D-02a: finished(0, 1) -> 'GBS.FM streams updated' toast."""
    captured = {}
    monkeypatch.setattr(main_window, "show_toast",
                        lambda text, *a, **kw: captured.setdefault("text", text))
    monkeypatch.setattr(main_window, "_refresh_station_list", lambda: None)
    main_window._gbs_import_worker = MagicMock()
    main_window._on_gbs_import_finished(0, 1)
    assert captured["text"] == "GBS.FM streams updated"


def test_import_error_auth_expired_toasts_reconnect_prompt(main_window, monkeypatch):
    """Pitfall 3: error('auth_expired') -> reconnect-via-Accounts toast."""
    captured = {}
    monkeypatch.setattr(main_window, "show_toast",
                        lambda text, *a, **kw: captured.setdefault("text", text))
    main_window._gbs_import_worker = MagicMock()
    main_window._on_gbs_import_error("auth_expired")
    assert "session expired" in captured["text"].lower()
    assert "Accounts" in captured["text"]
    assert main_window._gbs_import_worker is None


def test_import_error_generic_toasts_failure(main_window, monkeypatch):
    """Generic error -> 'GBS.FM import failed: {msg}' toast."""
    captured = {}
    monkeypatch.setattr(main_window, "show_toast",
                        lambda text, *a, **kw: captured.setdefault("text", text))
    main_window._gbs_import_worker = MagicMock()
    main_window._on_gbs_import_error("Connection refused")
    assert "GBS.FM import failed" in captured["text"]
    assert "Connection refused" in captured["text"]


def test_import_error_long_message_truncated(main_window, monkeypatch):
    """T-60-15: long error messages are truncated to 80 chars before display."""
    captured = {}
    monkeypatch.setattr(main_window, "show_toast",
                        lambda text, *a, **kw: captured.setdefault("text", text))
    main_window._gbs_import_worker = MagicMock()
    long_msg = "very long error " * 20  # 320 chars
    main_window._on_gbs_import_error(long_msg)
    assert "GBS.FM import failed" in captured["text"]
    # The toast text must contain the ellipsis truncation marker
    assert "…" in captured["text"]


def test_no_self_capturing_lambda_in_gbs_action():
    """QA-05 / Pitfall 10: act_gbs_add must use a bound method, not a lambda."""
    # Phase 74 REVIEW WR-05: use Path.read_text so the file handle is closed
    # deterministically — open(...).read() leaks an FD until next GC and
    # trips ResourceWarning under `pytest -W error::ResourceWarning`.
    from pathlib import Path
    src = Path("musicstreamer/ui_qt/main_window.py").read_text(encoding="utf-8")
    # The connection line must look like:
    #   act_gbs_add.triggered.connect(self._on_gbs_add_clicked)
    matches = re.findall(r"act_gbs_add\.triggered\.connect\(([^)]+)\)", src)
    assert matches, "Expected act_gbs_add.triggered.connect(...) line"
    for m in matches:
        assert "lambda" not in m, f"QA-05 violation: {m!r}"
        assert m.strip().startswith("self."), \
            f"QA-05 expects bound method starting with 'self.', got: {m!r}"


# ---------------------------------------------------------------------------
# Phase 87B / GBS-TOKEN-01/D-09/D-10: dialog launch + re-poll wiring
# ---------------------------------------------------------------------------


def test_submission_completed_wired_to_repoll(main_window, monkeypatch):
    """D-09: _open_gbs_search_dialog connects submission_completed → trigger_gbs_repoll.

    Stubs GBSSearchDialog.exec() to avoid Qt modal loop; captures the
    trigger_gbs_repoll call on the panel.
    """
    from musicstreamer.ui_qt.gbs_search_dialog import GBSSearchDialog

    repoll_called = {"count": 0}
    # Stub trigger_gbs_repoll on the panel
    monkeypatch.setattr(main_window.now_playing, "trigger_gbs_repoll",
                        lambda: repoll_called.__setitem__("count", repoll_called["count"] + 1))

    # Capture the dialog instance and emit submission_completed from it
    dialog_ref = {}

    def fake_exec(self):
        dialog_ref["dlg"] = self
        # Simulate successful add → emit submission_completed
        self.submission_completed.emit()

    monkeypatch.setattr(GBSSearchDialog, "exec", fake_exec)

    main_window._open_gbs_search_dialog()

    assert repoll_called["count"] == 1, (
        "submission_completed must trigger trigger_gbs_repoll on the panel (D-09)"
    )


def test_add_song_requested_opens_dialog(main_window, monkeypatch):
    """D-10: emitting panel.add_song_requested invokes _open_gbs_search_dialog."""
    calls = {"count": 0}
    monkeypatch.setattr(main_window, "_open_gbs_search_dialog",
                        lambda: calls.__setitem__("count", calls["count"] + 1))

    main_window.now_playing.add_song_requested.emit()
    assert calls["count"] == 1, (
        "add_song_requested signal must invoke _open_gbs_search_dialog (D-10)"
    )


def test_stale_submission_docstring_gone(main_window):
    """D-09: the stale 'submission_completed is not connected here' line must be removed."""
    import inspect
    doc = inspect.getdoc(main_window._open_gbs_search_dialog) or ""
    assert "submission_completed is not connected here" not in doc, (
        "Stale docstring must be removed from _open_gbs_search_dialog"
    )


def test_submit_worker_calls_add_song_zero_token():
    """GBS-TOKEN-03: _GbsSubmitWorker.run must call add_song_zero_token, not bare submit."""
    from pathlib import Path
    src = Path("musicstreamer/ui_qt/gbs_search_dialog.py").read_text(encoding="utf-8")
    # Find _GbsSubmitWorker.run body
    m = re.search(r"def run\(self\).*?(?=\n    def |\nclass |\Z)", src, re.S)
    assert m, "_GbsSubmitWorker.run not found in gbs_search_dialog.py"
    run_body = m.group(0)
    assert "add_song_zero_token" in run_body, (
        "GBS-TOKEN-03: _GbsSubmitWorker.run must call gbs_api.add_song_zero_token()"
    )
    # Ensure no bare gbs_api.submit( call remains in _GbsSubmitWorker.run
    assert "gbs_api.submit(" not in run_body, (
        "Bare gbs_api.submit() must be replaced by add_song_zero_token() in _GbsSubmitWorker.run"
    )
