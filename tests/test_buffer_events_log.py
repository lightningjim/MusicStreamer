"""Tests for musicstreamer.buffer_log — Phase 78 / BUG-09 Commit A.

Verifies:
- Handler attached to musicstreamer.player logger (B-78A-01).
- INFO emit writes a line to the file (B-78A-02).
- Rotation at 1MB; backupCount=3 cap (B-78A-03).
- Idempotent install (B-78A-04).
- propagate=True invariant — record reaches both sinks (B-78A-05).
"""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

import pytest

from musicstreamer import paths


@pytest.fixture(autouse=True)
def _clean_player_handlers():
    """Snapshot musicstreamer.player.handlers + level at setup, restore at teardown.

    The musicstreamer.player logger is process-global so handler additions
    between tests would compound. Mirrors tests/test_paths.py:_reset_root_override
    shape (snapshot saved → yield → restore). Sets level to INFO during the test
    to mirror production wiring at __main__.main():
    ``logging.getLogger("musicstreamer.player").setLevel(logging.INFO)``.
    """
    log = logging.getLogger("musicstreamer.player")
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


def test_handler_attached_to_player_logger(tmp_path, monkeypatch):
    """B-78A-01: install attaches one RotatingFileHandler with D-02 params."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.buffer_log import install_buffer_events_handler
    install_buffer_events_handler()
    log = logging.getLogger("musicstreamer.player")
    rotating = [h for h in log.handlers if isinstance(h, RotatingFileHandler)]
    assert len(rotating) == 1
    h = rotating[0]
    assert h.baseFilename == str(tmp_path / "buffer-events.log")
    assert h.maxBytes == 1_048_576
    assert h.backupCount == 3


def test_emit_writes_line_to_file(tmp_path, monkeypatch):
    """B-78A-02: INFO record on musicstreamer.player lands in the file."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.buffer_log import install_buffer_events_handler
    install_buffer_events_handler()
    log = logging.getLogger("musicstreamer.player")
    log.info(
        "buffer_underrun start_ts=1.0 url=%r outcome=recovered",
        "http://x/",
    )
    # Flush any buffered writes by closing handler streams briefly.
    for h in log.handlers:
        if isinstance(h, RotatingFileHandler):
            h.flush()
    log_file = tmp_path / "buffer-events.log"
    assert log_file.exists()
    contents = log_file.read_text(encoding="utf-8")
    assert "buffer_underrun" in contents


def test_rotation_at_1mb(tmp_path, monkeypatch):
    """B-78A-03 part A: at >1MB of writes, buffer-events.log.1 appears."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.buffer_log import install_buffer_events_handler
    install_buffer_events_handler()
    log = logging.getLogger("musicstreamer.player")
    payload = "a" * 2000  # ~2KB per line incl asctime prefix
    for i in range(600):
        log.info("buffer_underrun bench=%d %s", i, payload)
    for h in log.handlers:
        if isinstance(h, RotatingFileHandler):
            h.flush()
    assert os.path.exists(str(tmp_path / "buffer-events.log.1"))


def test_never_creates_backup_4(tmp_path, monkeypatch):
    """B-78A-03 part B: backupCount=3 means buffer-events.log.4 is never created."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.buffer_log import install_buffer_events_handler
    install_buffer_events_handler()
    log = logging.getLogger("musicstreamer.player")
    payload = "a" * 2000
    for i in range(3000):
        log.info("buffer_underrun bench=%d %s", i, payload)
    for h in log.handlers:
        if isinstance(h, RotatingFileHandler):
            h.flush()
    assert os.path.exists(str(tmp_path / "buffer-events.log.4")) is False


def test_install_is_idempotent(tmp_path, monkeypatch):
    """B-78A-04: calling install twice does NOT add a second handler (Pitfall 7)."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.buffer_log import install_buffer_events_handler
    install_buffer_events_handler()
    install_buffer_events_handler()
    log = logging.getLogger("musicstreamer.player")
    rotating = [h for h in log.handlers if isinstance(h, RotatingFileHandler)]
    assert len(rotating) == 1


def test_record_reaches_both_sinks(tmp_path, monkeypatch):
    """B-78A-05: propagate=True invariant — record reaches both file + root.

    Pitfall 5: stderr parity comes from logger.propagate=True (default).
    The capsys / caplog dance against basicConfig is unreliable in pytest
    (basicConfig may have been replaced by pytest's caplog handler), so we
    enforce the configuration contract directly: the musicstreamer.player
    logger must retain propagate=True after install so its INFO records
    can reach the root logger's stderr StreamHandler.
    """
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    from musicstreamer.buffer_log import install_buffer_events_handler
    install_buffer_events_handler()
    log = logging.getLogger("musicstreamer.player")
    log.info("buffer_underrun start_ts=1.0 outcome=recovered")
    for h in log.handlers:
        if isinstance(h, RotatingFileHandler):
            h.flush()
    # (a) File sink received the record
    contents = (tmp_path / "buffer-events.log").read_text(encoding="utf-8")
    assert "buffer_underrun" in contents
    # (b) Propagate path is intact — record would reach root logger handlers
    assert logging.getLogger("musicstreamer.player").propagate is True
