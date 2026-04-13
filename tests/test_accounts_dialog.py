"""Tests for AccountsDialog — Twitch OAuth connection management.

UI-08: AccountsDialog shows Connected/Not connected, launches QProcess OAuth,
       Disconnect deletes token with confirmation.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QMessageBox

from musicstreamer import paths


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_data_dir(tmp_path, monkeypatch):
    """Redirect all paths.* accessors to tmp_path."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    return tmp_path


@pytest.fixture()
def app(qapp):
    """Re-use qtbot's QApplication; just return it."""
    return qapp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAccountsDialogStatus:
    """Status label and button text reflect token file presence."""

    def test_status_not_connected(self, tmp_data_dir, qtbot):
        """When token file does not exist: label 'Not connected', button 'Connect Twitch'."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        dlg = AccountsDialog()
        qtbot.addWidget(dlg)
        assert "not connected" in dlg._status_label.text().lower()
        assert dlg._action_btn.text() == "Connect Twitch"

    def test_status_connected(self, tmp_data_dir, qtbot):
        """When token file exists: label 'Connected', button 'Disconnect'."""
        token_path = paths.twitch_token_path()
        os.makedirs(os.path.dirname(token_path), exist_ok=True)
        Path(token_path).write_text("dummy-token")

        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        dlg = AccountsDialog()
        qtbot.addWidget(dlg)
        assert "connected" in dlg._status_label.text().lower()
        assert dlg._action_btn.text() == "Disconnect"


class TestAccountsDialogDisconnect:
    """Disconnect deletes token file after confirmation."""

    def test_disconnect_deletes_token(self, tmp_data_dir, qtbot, monkeypatch):
        """Clicking Disconnect and confirming removes the token file."""
        token_path = paths.twitch_token_path()
        os.makedirs(os.path.dirname(token_path), exist_ok=True)
        Path(token_path).write_text("dummy-token")

        # Auto-confirm the QMessageBox.question
        monkeypatch.setattr(
            QMessageBox, "question",
            staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Yes),
        )

        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        dlg = AccountsDialog()
        qtbot.addWidget(dlg)

        # Simulate disconnect click
        dlg._on_action_clicked()

        assert not os.path.exists(token_path)
        assert "not connected" in dlg._status_label.text().lower()
        assert dlg._action_btn.text() == "Connect Twitch"

    def test_disconnect_cancel_keeps_token(self, tmp_data_dir, qtbot, monkeypatch):
        """Cancelling the disconnect confirmation leaves token intact."""
        token_path = paths.twitch_token_path()
        os.makedirs(os.path.dirname(token_path), exist_ok=True)
        Path(token_path).write_text("dummy-token")

        monkeypatch.setattr(
            QMessageBox, "question",
            staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.No),
        )

        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        dlg = AccountsDialog()
        qtbot.addWidget(dlg)
        dlg._on_action_clicked()

        assert os.path.exists(token_path)


class TestAccountsDialogConnect:
    """Connect Twitch launches QProcess subprocess."""

    def test_connect_launches_qprocess(self, tmp_data_dir, qtbot):
        """Clicking Connect starts QProcess with oauth_helper --mode twitch args."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        from PySide6.QtCore import QProcess

        mock_proc = MagicMock(spec=QProcess)

        with patch("musicstreamer.ui_qt.accounts_dialog.QProcess", return_value=mock_proc):
            dlg = AccountsDialog()
            qtbot.addWidget(dlg)
            dlg._on_action_clicked()

        # start() should have been called
        assert mock_proc.start.called
        call_args = mock_proc.start.call_args
        # program is sys.executable; args list contains oauth_helper and twitch
        args_list = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("arguments", [])
        args_str = " ".join(args_list)
        assert "oauth_helper" in args_str
        assert "--mode" in args_str
        assert "twitch" in args_str

    def test_connect_shows_connecting_state(self, tmp_data_dir, qtbot):
        """While OAuth subprocess is running, button is disabled and label says Connecting."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        from PySide6.QtCore import QProcess

        mock_proc = MagicMock(spec=QProcess)

        with patch("musicstreamer.ui_qt.accounts_dialog.QProcess", return_value=mock_proc):
            dlg = AccountsDialog()
            qtbot.addWidget(dlg)
            dlg._on_action_clicked()

        assert not dlg._action_btn.isEnabled()
        assert "connecting" in dlg._status_label.text().lower()


class TestAccountsDialogOAuthFinished:
    """OAuth subprocess completion handling."""

    def test_oauth_finished_success_writes_token(self, tmp_data_dir, qtbot):
        """Exit code 0 with token in stdout: token written to twitch_token_path with 0o600."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        from PySide6.QtCore import QProcess

        token_path = paths.twitch_token_path()
        os.makedirs(os.path.dirname(token_path), exist_ok=True)

        mock_proc = MagicMock(spec=QProcess)
        fake_token = "oauth-abc123"
        mock_proc.readAllStandardOutput.return_value.data.return_value.decode.return_value = fake_token

        with patch("musicstreamer.ui_qt.accounts_dialog.QProcess", return_value=mock_proc):
            dlg = AccountsDialog()
            qtbot.addWidget(dlg)
            # Simulate process start
            dlg._on_action_clicked()
            # Simulate finished with success
            dlg._oauth_proc = mock_proc
            dlg._on_oauth_finished(0, QProcess.ExitStatus.NormalExit)

        assert os.path.exists(token_path)
        assert Path(token_path).read_text() == fake_token
        perms = oct(os.stat(token_path).st_mode & 0o777)
        assert perms == oct(0o600)
        assert "connected" in dlg._status_label.text().lower()

    def test_oauth_finished_failure_shows_warning(self, tmp_data_dir, qtbot, monkeypatch):
        """Exit code 1: QMessageBox.warning shown, status reverts to Not connected."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        from PySide6.QtCore import QProcess

        warning_calls = []
        monkeypatch.setattr(
            QMessageBox, "warning",
            staticmethod(lambda *args, **kwargs: warning_calls.append(args)),
        )

        mock_proc = MagicMock(spec=QProcess)
        mock_proc.readAllStandardOutput.return_value.data.return_value.decode.return_value = ""

        with patch("musicstreamer.ui_qt.accounts_dialog.QProcess", return_value=mock_proc):
            dlg = AccountsDialog()
            qtbot.addWidget(dlg)
            dlg._on_action_clicked()
            dlg._oauth_proc = mock_proc
            dlg._on_oauth_finished(1, QProcess.ExitStatus.NormalExit)

        assert len(warning_calls) > 0
        assert "not connected" in dlg._status_label.text().lower()
