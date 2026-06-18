"""Tests for musicstreamer.preroll_log — Phase 90 / SOMA-PRE-01.

Verifies:
- Handler attached to musicstreamer.preroll logger (P-90-01).
- INFO emit writes a line to the file (P-90-02).
- Rotation at 1MB; backupCount=3 cap (P-90-03).
- Never creates backup 4 (P-90-03b).
- propagate=True invariant — record reaches both sinks (P-90-04).

Structural mirror of tests/test_buffer_events_log.py.
"""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

import pytest

from musicstreamer import paths


@pytest.fixture(autouse=True)
def _clean_preroll_handlers():
    """Snapshot musicstreamer.preroll.handlers + level at setup, restore at teardown.

    The musicstreamer.preroll logger is process-global so handler additions
    between tests would compound. Mirrors _clean_player_handlers shape in
    tests/test_buffer_events_log.py (snapshot saved → yield → restore). Sets
    level to INFO during the test to mirror production wiring.
    """
    log = logging.getLogger("musicstreamer.preroll")
    saved_handlers = list(log.handlers)
    saved_level = log.level
    log.setLevel(logging.INFO)
    yield
    # Remove any handlers added during the test; close file handles first to
    # avoid stale fds keeping rotated logs open across tests.
    for h in list(log.handlers):
        if h not in saved_handlers:
            try:
                h.close()
            except Exception:
                pass
            log.removeHandler(h)
    log.setLevel(saved_level)


def test_handler_attached_to_preroll_logger(tmp_path, monkeypatch):
    """P-90-01: install attaches one RotatingFileHandler with D-02 params."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.preroll_log import install_preroll_events_handler
    install_preroll_events_handler()
    log = logging.getLogger("musicstreamer.preroll")
    rotating = [h for h in log.handlers if isinstance(h, RotatingFileHandler)]
    assert len(rotating) == 1
    h = rotating[0]
    assert h.baseFilename == str(tmp_path / "preroll-events.log")
    assert h.maxBytes == 1_048_576
    assert h.backupCount == 3


def test_emit_writes_line_to_file(tmp_path, monkeypatch):
    """P-90-02: INFO record on musicstreamer.preroll lands in the file."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.preroll_log import install_preroll_events_handler
    install_preroll_events_handler()
    log = logging.getLogger("musicstreamer.preroll")
    log.info(
        "preroll_start station_name=%r station_id=%d url=%r",
        "Groove Salad",
        1,
        "https://somafm.com/preroll/groovesalad.mp3",
    )
    # Flush any buffered writes by closing handler streams briefly.
    for h in log.handlers:
        if isinstance(h, RotatingFileHandler):
            h.flush()
    log_file = tmp_path / "preroll-events.log"
    assert log_file.exists()
    contents = log_file.read_text(encoding="utf-8")
    assert "preroll_start" in contents


def test_rotation_at_1mb(tmp_path, monkeypatch):
    """P-90-03 part A: at >1MB of writes, preroll-events.log.1 appears."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.preroll_log import install_preroll_events_handler
    install_preroll_events_handler()
    log = logging.getLogger("musicstreamer.preroll")
    payload = "a" * 2000  # ~2KB per line incl asctime prefix
    for i in range(600):
        log.info("preroll_start bench=%d %s", i, payload)
    for h in log.handlers:
        if isinstance(h, RotatingFileHandler):
            h.flush()
    assert os.path.exists(str(tmp_path / "preroll-events.log.1"))


def test_never_creates_backup_4(tmp_path, monkeypatch):
    """P-90-03 part B: backupCount=3 means preroll-events.log.4 is never created."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.preroll_log import install_preroll_events_handler
    install_preroll_events_handler()
    log = logging.getLogger("musicstreamer.preroll")
    payload = "a" * 2000
    for i in range(3000):
        log.info("preroll_start bench=%d %s", i, payload)
    for h in log.handlers:
        if isinstance(h, RotatingFileHandler):
            h.flush()
    assert os.path.exists(str(tmp_path / "preroll-events.log.4")) is False


def test_record_reaches_both_sinks(tmp_path, monkeypatch):
    """P-90-04: propagate=True invariant — record reaches both file + root.

    Pitfall 5: stderr parity comes from logger.propagate=True (default).
    The capsys / caplog dance against basicConfig is unreliable in pytest
    (basicConfig may have been replaced by pytest's caplog handler), so we
    enforce the configuration contract directly: the musicstreamer.preroll
    logger must retain propagate=True after install so its INFO records
    can reach the root logger's stderr StreamHandler.
    """
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.preroll_log import install_preroll_events_handler
    install_preroll_events_handler()
    log = logging.getLogger("musicstreamer.preroll")
    log.info("preroll_start station_name=%r station_id=%d url=%r", "Groove Salad", 1, "x")
    for h in log.handlers:
        if isinstance(h, RotatingFileHandler):
            h.flush()
    # (a) File sink received the record
    contents = (tmp_path / "preroll-events.log").read_text(encoding="utf-8")
    assert "preroll_start" in contents
    # (b) Propagate path is intact — record would reach root logger handlers
    assert logging.getLogger("musicstreamer.preroll").propagate is True
