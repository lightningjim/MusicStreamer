"""Unit tests for musicstreamer.ui_qt.gbs_relogin_handler.GbsReloginHandler.

TDD Wave 0 (RED state): tests are written before the implementation exists.
Running this file before Task 2 MUST fail with ImportError / ModuleNotFoundError.

Coverage:
    - Single-flight de-duplication (GBS-AUTH-EXP-02 / WR-03)
    - relogin_succeeded emitted after valid cookie write with 0o600 permissions
    - relogin_failed emitted on non-zero exit (cancel / subprocess failure)
    - FailedToStart resets the guard (_login_proc = None) so a fresh
      notify_expiry_detected() call can launch a new subprocess
"""
from __future__ import annotations

import os
import stat
import sys

import pytest
from unittest.mock import MagicMock


def _get_qapp():
    """Return the running QApplication or create one (module-scoped singleton)."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app


# ---------------------------------------------------------------------------
# test_single_flight_dedup
# GBS-AUTH-EXP-02 / T-87.1-01: concurrent expiry notifications must launch
# exactly ONE oauth_helper subprocess.
# ---------------------------------------------------------------------------

def test_single_flight_dedup(monkeypatch):
    """Two calls to notify_expiry_detected() launch exactly one QProcess."""
    _get_qapp()
    from musicstreamer.ui_qt.gbs_relogin_handler import GbsReloginHandler
    from PySide6.QtCore import QProcess

    start_calls = []
    monkeypatch.setattr(QProcess, "start", lambda self, prog, args: start_calls.append(1))
    monkeypatch.setattr(
        "musicstreamer.subprocess_utils._make_oauth_launch_args",
        lambda mode: ("fake_prog", ["--mode", mode]),
    )

    handler = GbsReloginHandler()
    handler.notify_expiry_detected()
    handler.notify_expiry_detected()  # second call — must be a no-op (single-flight)

    assert len(start_calls) == 1, (
        f"Expected exactly 1 QProcess.start call; got {len(start_calls)}. "
        "Single-flight de-dup (WR-03) is not working."
    )


# ---------------------------------------------------------------------------
# test_relogin_succeeded_on_valid_cookies
# T-87.1-03/T-87.1-04: success path writes cookies 0o600, emits relogin_succeeded.
# ---------------------------------------------------------------------------

def test_relogin_succeeded_on_valid_cookies(monkeypatch, tmp_path):
    """relogin_succeeded emitted after valid Netscape cookie write with 0o600 perms."""
    _get_qapp()
    from musicstreamer import paths
    from PySide6.QtCore import QProcess

    # Redirect all path accessors to tmp_path so the cookie write lands there.
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))

    from musicstreamer.ui_qt.gbs_relogin_handler import GbsReloginHandler

    monkeypatch.setattr(QProcess, "start", lambda self, prog, args: None)
    monkeypatch.setattr(
        "musicstreamer.subprocess_utils._make_oauth_launch_args",
        lambda mode: ("fake", []),
    )
    monkeypatch.setattr(
        "musicstreamer.gbs_api._validate_gbs_cookies",
        lambda text: True,
    )

    FAKE_NETSCAPE = (
        "# Netscape HTTP Cookie File\n"
        ".gbs.fm\tTRUE\t/\tFALSE\t9999999999\tsessionid\tabc123\n"
    )

    emissions: list[str] = []
    handler = GbsReloginHandler()
    handler.relogin_succeeded.connect(lambda: emissions.append("succeeded"))

    # Launch subprocess (QProcess.start is monkeypatched — no real process)
    handler.notify_expiry_detected()

    # Simulate a real QProcess finishing successfully:
    # We call _on_finished directly with a mock proc that has stdout pre-loaded.
    mock_proc = MagicMock()
    mock_stdout = MagicMock()
    mock_stdout.data.return_value = FAKE_NETSCAPE.encode("utf-8")
    mock_proc.readAllStandardOutput.return_value = mock_stdout
    mock_stderr = MagicMock()
    mock_stderr.data.return_value = b'{"category": "Success", "ts": 1.0}\n'
    mock_proc.readAllStandardError.return_value = mock_stderr

    # Inject the mock proc (it was stored as _login_proc after _launch)
    handler._login_proc = mock_proc
    handler._on_finished(0, QProcess.ExitStatus.NormalExit)

    assert "succeeded" in emissions, (
        "Expected relogin_succeeded to be emitted after valid cookie write; "
        f"emissions={emissions}"
    )

    cookie_path = paths.gbs_cookies_path()
    assert os.path.exists(cookie_path), f"Cookie file not written at {cookie_path}"
    mode = stat.S_IMODE(os.stat(cookie_path).st_mode)
    assert mode == 0o600, f"Cookie file permissions should be 0o600, got {oct(mode)}"


# ---------------------------------------------------------------------------
# test_relogin_failed_on_nonzero_exit
# T-87.1-04: non-zero exit code must emit relogin_failed, no cookie written.
# ---------------------------------------------------------------------------

def test_relogin_failed_on_nonzero_exit(monkeypatch, tmp_path):
    """relogin_failed emitted on non-zero exit (cancel); no cookie written."""
    _get_qapp()
    from musicstreamer import paths
    from PySide6.QtCore import QProcess

    monkeypatch.setattr(paths, "_root_override", str(tmp_path))

    from musicstreamer.ui_qt.gbs_relogin_handler import GbsReloginHandler

    monkeypatch.setattr(QProcess, "start", lambda self, prog, args: None)
    monkeypatch.setattr(
        "musicstreamer.subprocess_utils._make_oauth_launch_args",
        lambda mode: ("fake", []),
    )

    failure_reasons: list[str] = []
    handler = GbsReloginHandler()
    handler.relogin_failed.connect(lambda reason: failure_reasons.append(reason))

    handler.notify_expiry_detected()

    mock_proc = MagicMock()
    mock_stdout = MagicMock()
    mock_stdout.data.return_value = b""
    mock_proc.readAllStandardOutput.return_value = mock_stdout
    mock_stderr = MagicMock()
    mock_stderr.data.return_value = b""
    mock_proc.readAllStandardError.return_value = mock_stderr

    handler._login_proc = mock_proc
    handler._on_finished(1, QProcess.ExitStatus.NormalExit)

    assert len(failure_reasons) >= 1, (
        "Expected relogin_failed to be emitted on non-zero exit; "
        f"failure_reasons={failure_reasons}"
    )
    cookie_path = paths.gbs_cookies_path()
    assert not os.path.exists(cookie_path), (
        "Cookie file MUST NOT be written on non-zero exit"
    )


# ---------------------------------------------------------------------------
# test_failed_to_start_resets_guard
# T-87.1-02: FailedToStart must reset _login_proc to None so the handler
# is never permanently jammed.
# ---------------------------------------------------------------------------

def test_failed_to_start_resets_guard(monkeypatch):
    """FailedToStart emits relogin_failed AND resets guard so a fresh launch is possible."""
    _get_qapp()
    from musicstreamer.ui_qt.gbs_relogin_handler import GbsReloginHandler
    from PySide6.QtCore import QProcess

    start_calls: list[int] = []

    def _fake_start(self, prog, args):
        start_calls.append(1)

    monkeypatch.setattr(QProcess, "start", _fake_start)
    monkeypatch.setattr(
        "musicstreamer.subprocess_utils._make_oauth_launch_args",
        lambda mode: ("fake", []),
    )

    failure_reasons: list[str] = []
    handler = GbsReloginHandler()
    handler.relogin_failed.connect(lambda reason: failure_reasons.append(reason))

    # First notify — starts the subprocess
    handler.notify_expiry_detected()
    assert len(start_calls) == 1

    # Simulate FailedToStart — must reset guard and emit relogin_failed
    handler._on_error(QProcess.ProcessError.FailedToStart)

    assert len(failure_reasons) >= 1, (
        "Expected relogin_failed to be emitted on FailedToStart; "
        f"failure_reasons={failure_reasons}"
    )
    assert handler._login_proc is None, (
        "_login_proc must be reset to None after FailedToStart so the handler "
        "is not permanently jammed (T-87.1-02 / Pitfall 2)"
    )

    # A subsequent notify_expiry_detected() must launch a fresh subprocess
    # (guard was reset to None by _on_error)
    handler.notify_expiry_detected()
    assert len(start_calls) == 2, (
        f"Expected 2 QProcess.start calls total (first + post-FailedToStart retry); "
        f"got {len(start_calls)}"
    )
