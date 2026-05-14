"""Phase 74 / Wave 0: RED contract for MainWindow SomaFM hamburger entry + worker wiring.

Seven failing tests encoding the SomaFM UI spec (RESEARCH validation tests #10–12 + #16
plus the click-toast case). All tests RED-fail on collection until Plan 03 creates
_SomaImportWorker in musicstreamer/ui_qt/main_window.py.

SOMA-NN traceability:
  test 1: SOMA-10 (menu entry 'Import SomaFM' exists and is enabled)
  test 2: SOMA-12 (click sets _soma_import_worker; SYNC-05 retention)
  test 3: SOMA-11a (finished toast 'SomaFM import: N stations added'; worker cleared)
  test 4: SOMA-11b (finished toast 'SomaFM import: no changes'; worker cleared)
  test 5: SOMA-11c + D-14 (error toast truncated at 80 chars + U+2026; short msg untruncated)
  test 6: click-toast 'Importing SomaFM…' (U+2026)
  test 7: SOMA-10 + QA-05 (no self-capturing lambda in act_soma_import.triggered.connect)
"""
from __future__ import annotations

import re
from unittest.mock import MagicMock
from typing import Optional

import pytest
from PySide6.QtCore import QObject, Signal

from musicstreamer.ui_qt.main_window import MainWindow, _SomaImportWorker  # RED: ImportError until Plan 03


# ---------------------------------------------------------------------------
# Test doubles — lifted verbatim from tests/test_main_window_gbs.py with module-path rename.
# Same Signal list, same no-op methods per plan spec.
# ---------------------------------------------------------------------------

class _FakePlayer(QObject):
    title_changed = Signal(str)
    failover = Signal(object)
    offline = Signal(str)
    playback_error = Signal(str)
    cookies_cleared = Signal(str)
    elapsed_updated = Signal(int)
    buffer_percent = Signal(int)
    underrun_recovery_started = Signal()   # Phase 62 BUG-09
    audio_caps_detected = Signal(object)   # Phase 70 DS-01

    def __init__(self) -> None:
        super().__init__()
        self.volume: Optional[float] = None

    def set_volume(self, value: float) -> None:
        self.volume = value

    def play(self, station, **kwargs) -> None:
        pass

    def pause(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def restore_eq_from_settings(self, repo) -> None:
        pass

    def set_eq_enabled(self, enabled: bool) -> None:
        pass

    def set_eq_profile(self, profile) -> None:
        pass

    def set_eq_preamp(self, db: float) -> None:
        pass


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
# Shared fixture — lifted verbatim from tests/test_main_window_gbs.py
# ---------------------------------------------------------------------------

@pytest.fixture
def main_window(qtbot):
    """Construct a MainWindow with FakePlayer + FakeRepo doubles."""
    w = MainWindow(_FakePlayer(), _FakeRepo())
    qtbot.addWidget(w)
    return w


# ---------------------------------------------------------------------------
# Helpers — lifted verbatim from tests/test_main_window_gbs.py
# ---------------------------------------------------------------------------

def _find_action(window, text: str):
    for action in window._menu.actions():
        if action.text() == text:
            return action
    return None


# ---------------------------------------------------------------------------
# Tests (RESEARCH validation tests #10, #11, #12, #16 + click-toast)
# ---------------------------------------------------------------------------

def test_import_soma_menu_entry_exists(main_window):
    """SOMA-10: 'Import SomaFM' menu entry is rendered in the hamburger menu and enabled.

    Maps to CONTEXT D-06 — hamburger action near existing 'Add GBS.FM'.
    """
    action = _find_action(main_window, "Import SomaFM")
    assert action is not None, "Expected 'Import SomaFM' menu entry in hamburger menu"
    assert action.isEnabled(), "SOMA-10b: 'Import SomaFM' menu entry must always be enabled"


def test_import_soma_triggers_worker_start_and_retains_reference(main_window, monkeypatch):
    """SOMA-12: click sets MainWindow._soma_import_worker to non-None _SomaImportWorker.

    Monkeypatches _SomaImportWorker.start so the thread doesn't actually run.
    Asserts started flag flips and _soma_import_worker is not None after click.
    Maps to CONTEXT D-07 + Phase 60 SYNC-05 worker-retention pattern.
    """
    started = {"flag": False}
    real_init = _SomaImportWorker.__init__

    def fake_init(self, parent=None):
        real_init(self, parent=parent)

    def fake_start(self):
        started["flag"] = True

    monkeypatch.setattr(_SomaImportWorker, "__init__", fake_init)
    monkeypatch.setattr(_SomaImportWorker, "start", fake_start)
    main_window._on_soma_import_clicked()
    assert started["flag"] is True, "SOMA-12: worker start() must be called on click"
    assert main_window._soma_import_worker is not None, (
        "SOMA-12 / SYNC-05: _soma_import_worker must be retained after click "
        "(Phase 60 D-02 pattern — prevents mid-run GC)"
    )


def test_import_soma_done_inserted_emits_added_toast(main_window, monkeypatch):
    """SOMA-11a: _on_soma_import_done(5, 0) emits 'SomaFM import: 5 stations added' toast.

    Also asserts _soma_import_worker is cleared to None after done.
    Maps to CONTEXT D-06 toast verbatim string.
    """
    captured = {}
    monkeypatch.setattr(main_window, "show_toast",
                        lambda text, *a, **kw: captured.setdefault("text", text))
    monkeypatch.setattr(main_window, "_refresh_station_list", lambda: None)
    main_window._soma_import_worker = MagicMock()
    main_window._on_soma_import_done(5, 0)
    assert captured.get("text") == "SomaFM import: 5 stations added", (
        f"SOMA-11a: expected literal toast 'SomaFM import: 5 stations added', "
        f"got {captured.get('text')!r}"
    )
    assert main_window._soma_import_worker is None, (
        "SOMA-12: _soma_import_worker must be cleared to None in _on_soma_import_done"
    )


def test_import_soma_done_zero_inserted_emits_no_changes_toast(main_window, monkeypatch):
    """SOMA-11b: _on_soma_import_done(0, 46) emits 'SomaFM import: no changes' toast.

    Maps to CONTEXT D-06 (all channels dedup-skipped case).
    """
    captured = {}
    monkeypatch.setattr(main_window, "show_toast",
                        lambda text, *a, **kw: captured.setdefault("text", text))
    monkeypatch.setattr(main_window, "_refresh_station_list", lambda: None)
    main_window._soma_import_worker = MagicMock()
    main_window._on_soma_import_done(0, 46)
    assert captured.get("text") == "SomaFM import: no changes", (
        f"SOMA-11b: expected literal toast 'SomaFM import: no changes', "
        f"got {captured.get('text')!r}"
    )


def test_import_soma_error_truncates_message_at_80_chars(main_window, monkeypatch):
    """SOMA-11c + D-14: error toast truncates msg at 80 chars with U+2026; short msg untruncated.

    Two sub-cases:
    1. Long message (200 chars): toast contains '…' (U+2026) and total length is
       len('SomaFM import failed: ') + 80 + len('…')
    2. Short message ('short'): toast is exactly 'SomaFM import failed: short' (no '…')

    Both calls clear _soma_import_worker to None. Maps to CONTEXT D-14.
    """
    PREFIX = "SomaFM import failed: "
    ELLIPSIS = "…"

    # Sub-case 1: long message
    captured_long: dict = {}
    monkeypatch.setattr(main_window, "show_toast",
                        lambda text, *a, **kw: captured_long.setdefault("text", text))
    main_window._soma_import_worker = MagicMock()
    main_window._on_soma_import_error("x" * 200)
    long_text = captured_long.get("text", "")
    assert long_text.startswith(PREFIX), (
        f"SOMA-11c: error toast must start with {PREFIX!r}, got {long_text!r}"
    )
    assert ELLIPSIS in long_text, (
        f"SOMA-11c: error toast must contain U+2026 for truncated message, got {long_text!r}"
    )
    expected_len = len(PREFIX) + 80 + len(ELLIPSIS)
    assert len(long_text) == expected_len, (
        f"SOMA-11c: expected toast length {expected_len}, got {len(long_text)}"
    )
    assert main_window._soma_import_worker is None, (
        "SOMA-12: _soma_import_worker must be cleared to None in _on_soma_import_error"
    )

    # Sub-case 2: short message (no truncation)
    captured_short: dict = {}
    monkeypatch.setattr(main_window, "show_toast",
                        lambda text, *a, **kw: captured_short.setdefault("text", text))
    main_window._soma_import_worker = MagicMock()
    main_window._on_soma_import_error("short")
    short_text = captured_short.get("text", "")
    assert short_text == "SomaFM import failed: short", (
        f"SOMA-11c: short msg must not be truncated, got {short_text!r}"
    )
    assert ELLIPSIS not in short_text, (
        f"SOMA-11c: U+2026 must not appear for short message, got {short_text!r}"
    )
    assert main_window._soma_import_worker is None


def test_import_soma_click_emits_importing_toast(main_window, monkeypatch):
    """SOMA-11 (click): _on_soma_import_clicked emits 'Importing SomaFM…' (U+2026) toast.

    Monkeypatches _SomaImportWorker.start to no-op so thread doesn't run.
    Maps to CONTEXT D-06 click-toast verbatim string.
    """
    captured = {}
    monkeypatch.setattr(main_window, "show_toast",
                        lambda text, *a, **kw: captured.setdefault("text", text))
    monkeypatch.setattr(_SomaImportWorker, "start", lambda self: None)
    main_window._on_soma_import_clicked()
    assert captured.get("text") == "Importing SomaFM…", (
        f"SOMA-11 click-toast: expected 'Importing SomaFM…' (U+2026), "
        f"got {captured.get('text')!r}"
    )


def test_no_self_capturing_lambda_in_soma_action():
    """SOMA-10 + QA-05: act_soma_import.triggered.connect must use a bound method, not a lambda.

    Mirrors tests/test_main_window_gbs.py:test_no_self_capturing_lambda_in_gbs_action.
    Regex: r"act_soma_import\\.triggered\\.connect\\(([^)]+)\\)"
    Maps to CONTEXT D-06 + Phase 60 QA-05 bound-method discipline.
    """
    src = open("musicstreamer/ui_qt/main_window.py", encoding="utf-8").read()
    matches = re.findall(r"act_soma_import\.triggered\.connect\(([^)]+)\)", src)
    assert matches, "Expected act_soma_import.triggered.connect(...) line in main_window.py"
    for m in matches:
        assert "lambda" not in m, f"QA-05 violation: lambda in soma connect: {m!r}"
        assert m.strip().startswith("self."), (
            f"QA-05: bound method starting with 'self.' expected, got: {m!r}"
        )
