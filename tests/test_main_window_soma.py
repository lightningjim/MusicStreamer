"""Phase 74 / Wave 0: RED contract for MainWindow SomaFM hamburger entry + worker wiring.

Seven failing tests encoding the SomaFM UI spec (RESEARCH validation tests #10–12 + #16
plus the click-toast case). All tests RED-fail on collection until Plan 03 creates
_SomaImportWorker in musicstreamer/ui_qt/main_window.py.

Phase 90 Plan 03 (Wave 2): adds 4 tests for "Open preroll log" and "Re-fetch SomaFM prerolls"
hamburger actions (SOMA-PRE-02, D-05, D-07).

SOMA-NN traceability:
  test 1: SOMA-10 (menu entry 'Import SomaFM' exists and is enabled)
  test 2: SOMA-12 (click sets _soma_import_worker; SYNC-05 retention)
  test 3: SOMA-11a (finished toast 'SomaFM import: N stations added'; worker cleared)
  test 4: SOMA-11b (finished toast 'SomaFM import: no changes'; worker cleared)
  test 5: SOMA-11c + D-14 (error toast truncated at 80 chars + U+2026; short msg untruncated)
  test 6: click-toast 'Importing SomaFM…' (U+2026)
  test 7: SOMA-10 + QA-05 (no self-capturing lambda in act_soma_import.triggered.connect)
  test 8: SOMA-PRE-02 / D-05 ('Open preroll log' action exists in hamburger menu)
  test 9: SOMA-PRE-02 / D-05 (clicking when log absent toasts, does not call openUrl)
  test 10: D-07 ('Re-fetch SomaFM prerolls' action exists in hamburger menu)
  test 11: D-07 (_PrerollRefetchWorker skips stations that already have prerolls)
"""
from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

import pytest

from musicstreamer.ui_qt.main_window import MainWindow, _SomaImportWorker  # RED: ImportError until Plan 03
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
    # Phase 74 REVIEW WR-05: use Path.read_text so the file handle is closed
    # deterministically — open(...).read() leaks an FD until next GC and
    # trips ResourceWarning under `pytest -W error::ResourceWarning`.
    from pathlib import Path
    src = Path("musicstreamer/ui_qt/main_window.py").read_text(encoding="utf-8")
    matches = re.findall(r"act_soma_import\.triggered\.connect\(([^)]+)\)", src)
    assert matches, "Expected act_soma_import.triggered.connect(...) line in main_window.py"
    for m in matches:
        assert "lambda" not in m, f"QA-05 violation: lambda in soma connect: {m!r}"
        assert m.strip().startswith("self."), (
            f"QA-05: bound method starting with 'self.' expected, got: {m!r}"
        )


def test_re_import_emits_no_changes_toast_via_real_thread(main_window, qtbot, monkeypatch):
    """SOMA-11 / UAT-07 regression: re-import (inserted=0, skipped=46) emits
    'SomaFM import: no changes' toast via the live _SomaImportWorker thread.

    Exercises the real Qt event loop (start the worker, wait for the toast)
    — NOT a direct slot call. This is the test that catches the
    QThread.finished shadowing bug from 74-VERIFICATION.md G-01 / 74-REVIEW.md
    CR-02 + WR-04: when the worker's completion signal shadows the inherited
    QThread.finished, Qt's no-arg auto-emitted finished() dispatches into a
    2-int slot with the wrong arity, raising TypeError that Qt swallows,
    causing the toast to never appear.
    """
    import sqlite3

    from musicstreamer import soma_import

    captured_toasts: list[str] = []
    monkeypatch.setattr(main_window, "show_toast",
                        lambda text, *a, **kw: captured_toasts.append(text))
    monkeypatch.setattr(main_window, "_refresh_station_list", lambda: None)

    # Phase 74 REVIEW WR-04: monkeypatch db_connect + Repo so
    # _SomaImportWorker.run() does NOT hit the real filesystem from the
    # worker thread. _SomaImportWorker.run does `from musicstreamer.repo
    # import Repo` lazily, so the patch must target musicstreamer.repo.
    # main_window.py imports db_connect at module top level, so that one
    # is patched at the main_window path. import_stations is stubbed below
    # so the fake Repo is never actually called — its only job is to keep
    # Repo(db_connect()) from touching the dev database / CI runner state.
    monkeypatch.setattr(
        "musicstreamer.ui_qt.main_window.db_connect",
        lambda: sqlite3.connect(":memory:"),
    )
    monkeypatch.setattr(
        "musicstreamer.repo.Repo",
        lambda con: MagicMock(),
    )

    # Patch fetch_channels and import_stations so the live worker exits
    # immediately with (0, 46) — no network calls.
    monkeypatch.setattr(soma_import, "fetch_channels",
                        lambda *a, **kw: [{"id": "stub", "title": "stub",
                                           "description": "", "image_url": None,
                                           "streams": []}])
    monkeypatch.setattr(soma_import, "import_stations",
                        lambda channels, repo: (0, 46))

    # Click the action — this constructs _SomaImportWorker and calls .start().
    main_window._on_soma_import_clicked()

    # Wait up to 5 s for the worker to complete and dispatch the toast via
    # the real Qt event loop. The bug under test causes the toast to never
    # arrive — the test then times out and fails.
    qtbot.waitUntil(
        lambda: "SomaFM import: no changes" in captured_toasts,
        timeout=5000,
    )

    assert "SomaFM import: no changes" in captured_toasts, (
        "UAT-07 regression: live _SomaImportWorker.start() with "
        "(inserted=0, skipped=46) must produce a 'SomaFM import: no changes' "
        "toast — got toasts: " + repr(captured_toasts)
    )
    # Worker should be cleared by _on_soma_import_done
    assert main_window._soma_import_worker is None, (
        "SOMA-12: _soma_import_worker must be cleared in _on_soma_import_done"
    )


# ---------------------------------------------------------------------------
# Phase 90 Plan 03: "Open preroll log" + "Re-fetch SomaFM prerolls" tests
# ---------------------------------------------------------------------------

def test_open_preroll_log_action_exists(main_window):
    """SOMA-PRE-02 / D-05: 'Open preroll log' action is present in the hamburger menu and enabled.

    Net-new UI — there is no 'Open buffer-events log' to mirror; this action
    is the first log-viewer entry in the hamburger menu.
    """
    action = _find_action(main_window, "Open preroll log")
    assert action is not None, "Expected 'Open preroll log' menu entry in hamburger menu"
    assert action.isEnabled(), "SOMA-PRE-02: 'Open preroll log' must be enabled"


def test_open_preroll_log_absent_shows_toast(main_window, monkeypatch, tmp_path):
    """SOMA-PRE-02 / D-05 / Pitfall 5: clicking when log absent shows toast, not openUrl.

    Monkeypatches paths.preroll_events_log_path to a non-existent path so
    os.path.isfile returns False. Asserts show_toast is called and
    QDesktopServices.openUrl is NOT called (by monkeypatching PySide6.QtGui.QDesktopServices
    at the import source, since the handler does a local import).
    """
    from musicstreamer import paths
    # Point the log path to a non-existent file
    absent_path = str(tmp_path / "preroll-events.log")  # file does NOT exist
    monkeypatch.setattr(paths, "preroll_events_log_path", lambda: absent_path)

    captured_toasts: list[str] = []
    monkeypatch.setattr(main_window, "show_toast",
                        lambda text, *a, **kw: captured_toasts.append(text))

    # Patch QDesktopServices at the PySide6.QtGui level so the local import
    # inside _on_open_preroll_log_clicked picks up the mock.
    open_url_called: list[bool] = []
    mock_ds = MagicMock()
    mock_ds.openUrl.side_effect = lambda *a, **kw: open_url_called.append(True)
    monkeypatch.setattr("PySide6.QtGui.QDesktopServices", mock_ds, raising=False)

    main_window._on_open_preroll_log_clicked()

    assert any("No preroll log yet" in t for t in captured_toasts), (
        f"Expected toast containing 'No preroll log yet', got: {captured_toasts}"
    )
    assert not open_url_called, (
        "Pitfall 5: QDesktopServices.openUrl must NOT be called when log file absent"
    )


def test_refetch_prerolls_action_exists(main_window):
    """D-07: 'Re-fetch SomaFM prerolls' action is present in the hamburger menu and enabled."""
    action = _find_action(main_window, "Re-fetch SomaFM prerolls")
    assert action is not None, "Expected 'Re-fetch SomaFM prerolls' menu entry in hamburger menu"
    assert action.isEnabled(), "D-07: 'Re-fetch SomaFM prerolls' must be enabled"


def test_refetch_worker_skips_stations_with_prerolls(monkeypatch):
    """D-07 / Pitfall 4: _PrerollRefetchWorker skips stations that already have prerolls.

    Uses a stub fetch_channels + in-memory repo to verify that:
    - Stations with existing prerolls are NOT updated.
    - Only zero-preroll SomaFM stations get insert_preroll called.
    """
    import sqlite3
    from musicstreamer.ui_qt.main_window import _PrerollRefetchWorker

    # Stations: station_1 has prerolls already, station_2 has none.
    from types import SimpleNamespace
    station_with_prerolls = SimpleNamespace(id=1, name="Groove Salad", provider_name="SomaFM")
    station_without_prerolls = SimpleNamespace(id=2, name="Boot Liquor", provider_name="SomaFM")
    station_non_soma = SimpleNamespace(id=3, name="DI Radio", provider_name="DI")

    fake_channels = [
        {"id": "groovesalad", "title": "Groove Salad", "preroll_urls": ["https://example.com/pre.mp3"]},
        {"id": "bootliquor", "title": "Boot Liquor", "preroll_urls": ["https://example.com/boot.mp3"]},
    ]

    insert_calls: list[tuple] = []
    set_fetched_calls: list[int] = []

    class FakeRepo:
        def list_stations(self):
            return [station_with_prerolls, station_without_prerolls, station_non_soma]

        def list_prerolls(self, station_id: int):
            # station_1 already has prerolls; station_2 has none
            if station_id == 1:
                return ["https://existing.com/pre.mp3"]
            return []

        def insert_preroll(self, station_id, url, pos):
            insert_calls.append((station_id, url, pos))
            return len(insert_calls)

        def set_prerolls_fetched_at(self, station_id, ts):
            set_fetched_calls.append(station_id)

    import musicstreamer.soma_import as soma_import
    monkeypatch.setattr(soma_import, "fetch_channels", lambda: fake_channels)

    import musicstreamer.ui_qt.main_window as mw_mod
    monkeypatch.setattr(mw_mod, "db_connect", lambda: sqlite3.connect(":memory:"))
    from musicstreamer import repo as repo_mod
    monkeypatch.setattr(repo_mod, "Repo", lambda con: FakeRepo())

    worker = _PrerollRefetchWorker()
    done_values: list[int] = []
    worker.refetch_done.connect(lambda n: done_values.append(n))

    worker.run()

    # station_1 (Groove Salad) has prerolls → must be skipped
    for station_id, url, pos in insert_calls:
        assert station_id != 1, (
            f"Pitfall 4: station_id=1 (Groove Salad) already has prerolls — "
            f"insert_preroll must NOT be called for it; got insert_calls={insert_calls}"
        )

    # station_2 (Boot Liquor) has no prerolls → must get insert_preroll
    inserted_for_2 = [c for c in insert_calls if c[0] == 2]
    assert inserted_for_2, (
        f"D-07: station_id=2 (Boot Liquor) has zero prerolls — "
        f"insert_preroll must be called; got insert_calls={insert_calls}"
    )

    # station_3 (DI Radio) is not SomaFM → must be skipped entirely
    for station_id, url, pos in insert_calls:
        assert station_id != 3, (
            f"D-07: station_id=3 (DI Radio) is non-SomaFM — must be skipped; "
            f"got insert_calls={insert_calls}"
        )

    # Worker must emit refetch_done
    assert done_values, "D-07: _PrerollRefetchWorker must emit refetch_done signal"
