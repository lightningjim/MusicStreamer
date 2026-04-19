"""Tests for AccountsDialog — Twitch OAuth + AudioAddict view/clear.

UI-08: AccountsDialog shows Connected/Not connected, launches QProcess OAuth,
       Disconnect deletes token with confirmation.

Phase 48 D-04..D-07: AA group reflects ``audioaddict_listen_key`` saved state
       and lets the user clear it via Yes/No confirm. Dialog never writes a
       new AA key — editing lives in ImportDialog (plan 48-02).
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

class FakeRepo:
    """Minimal Repo stub for settings round-trip tests.

    Mirrors the FakeRepo in tests/test_accent_color_dialog.py (project
    convention — no shared conftest fixture for this shape).
    """

    def __init__(self) -> None:
        self._settings: dict[str, str] = {}

    def get_setting(self, key: str, default: str = "") -> str:
        return self._settings.get(key, default)

    def set_setting(self, key: str, value: str) -> None:
        self._settings[key] = value


@pytest.fixture()
def fake_repo():
    """Phase 48: FakeRepo for AccountsDialog settings interactions."""
    return FakeRepo()


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

    def test_status_not_connected(self, tmp_data_dir, qtbot, fake_repo):
        """When token file does not exist: label 'Not connected', button 'Connect Twitch'."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        dlg = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg)
        assert "not connected" in dlg._status_label.text().lower()
        assert dlg._action_btn.text() == "Connect Twitch"

    def test_status_connected(self, tmp_data_dir, qtbot, fake_repo):
        """When token file exists: label 'Connected', button 'Disconnect'."""
        token_path = paths.twitch_token_path()
        os.makedirs(os.path.dirname(token_path), exist_ok=True)
        Path(token_path).write_text("dummy-token")

        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        dlg = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg)
        assert "connected" in dlg._status_label.text().lower()
        assert dlg._action_btn.text() == "Disconnect"


class TestAccountsDialogDisconnect:
    """Disconnect deletes token file after confirmation."""

    def test_disconnect_deletes_token(self, tmp_data_dir, qtbot, monkeypatch, fake_repo):
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
        dlg = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg)

        # Simulate disconnect click
        dlg._on_action_clicked()

        assert not os.path.exists(token_path)
        assert "not connected" in dlg._status_label.text().lower()
        assert dlg._action_btn.text() == "Connect Twitch"

    def test_disconnect_cancel_keeps_token(self, tmp_data_dir, qtbot, monkeypatch, fake_repo):
        """Cancelling the disconnect confirmation leaves token intact."""
        token_path = paths.twitch_token_path()
        os.makedirs(os.path.dirname(token_path), exist_ok=True)
        Path(token_path).write_text("dummy-token")

        monkeypatch.setattr(
            QMessageBox, "question",
            staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.No),
        )

        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        dlg = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg)
        dlg._on_action_clicked()

        assert os.path.exists(token_path)


class TestAccountsDialogConnect:
    """Connect Twitch launches QProcess subprocess."""

    def test_connect_launches_qprocess(self, tmp_data_dir, qtbot, fake_repo):
        """Clicking Connect starts QProcess with oauth_helper --mode twitch args."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        from PySide6.QtCore import QProcess

        mock_proc = MagicMock(spec=QProcess)

        with patch("musicstreamer.ui_qt.accounts_dialog.QProcess", return_value=mock_proc):
            dlg = AccountsDialog(fake_repo)
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

    def test_connect_shows_connecting_state(self, tmp_data_dir, qtbot, fake_repo):
        """While OAuth subprocess is running, button is disabled and label says Connecting."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        from PySide6.QtCore import QProcess

        mock_proc = MagicMock(spec=QProcess)

        with patch("musicstreamer.ui_qt.accounts_dialog.QProcess", return_value=mock_proc):
            dlg = AccountsDialog(fake_repo)
            qtbot.addWidget(dlg)
            dlg._on_action_clicked()

        assert not dlg._action_btn.isEnabled()
        assert "connecting" in dlg._status_label.text().lower()


class TestAccountsDialogOAuthFinished:
    """OAuth subprocess completion handling."""

    def test_oauth_finished_success_writes_token(self, tmp_data_dir, qtbot, fake_repo):
        """Exit code 0 with token in stdout: token written to twitch_token_path with 0o600."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        from PySide6.QtCore import QProcess

        token_path = paths.twitch_token_path()
        os.makedirs(os.path.dirname(token_path), exist_ok=True)

        mock_proc = MagicMock(spec=QProcess)
        fake_token = "oauth-abc123"
        mock_proc.readAllStandardOutput.return_value.data.return_value.decode.return_value = fake_token

        with patch("musicstreamer.ui_qt.accounts_dialog.QProcess", return_value=mock_proc):
            dlg = AccountsDialog(fake_repo)
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

    def test_oauth_finished_failure_shows_warning(self, tmp_data_dir, qtbot, monkeypatch, fake_repo):
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
            dlg = AccountsDialog(fake_repo)
            qtbot.addWidget(dlg)
            dlg._on_action_clicked()
            dlg._oauth_proc = mock_proc
            dlg._on_oauth_finished(1, QProcess.ExitStatus.NormalExit)

        assert len(warning_calls) > 0
        assert "not connected" in dlg._status_label.text().lower()


class TestAccountsDialogAudioAddict:
    """Phase 48 D-05/D-06/D-07: AudioAddict view/clear group."""

    def test_aa_group_reflects_saved_status(self, tmp_data_dir, qtbot, fake_repo):
        """AA status label + clear button reflect audioaddict_listen_key state."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog

        # Empty repo: 'Not saved' + disabled button
        dlg = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg)
        assert dlg._aa_status_label.text() == "Not saved"
        assert dlg._aa_clear_btn.isEnabled() is False
        assert dlg._aa_clear_btn.text() == "No key saved"

        # Saved repo: 'Saved' + enabled button
        fake_repo.set_setting("audioaddict_listen_key", "test-key-abc")
        dlg2 = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg2)
        assert dlg2._aa_status_label.text() == "Saved"
        assert dlg2._aa_clear_btn.isEnabled() is True
        assert dlg2._aa_clear_btn.text() == "Clear saved key"

    def test_clear_aa_key_requires_confirm_yes(
        self, tmp_data_dir, qtbot, fake_repo, monkeypatch
    ):
        """Yes on the confirm → setting cleared and status flips to Not saved."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog

        fake_repo.set_setting("audioaddict_listen_key", "test-key-abc")
        monkeypatch.setattr(
            QMessageBox, "question",
            staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Yes),
        )

        dlg = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg)
        dlg._on_aa_clear_clicked()

        assert fake_repo.get_setting("audioaddict_listen_key", "") == ""
        assert dlg._aa_status_label.text() == "Not saved"
        assert dlg._aa_clear_btn.isEnabled() is False

    def test_clear_aa_key_requires_confirm_no(
        self, tmp_data_dir, qtbot, fake_repo, monkeypatch
    ):
        """No on the confirm → setting unchanged, status stays Saved."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog

        fake_repo.set_setting("audioaddict_listen_key", "test-key-abc")
        monkeypatch.setattr(
            QMessageBox, "question",
            staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.No),
        )

        dlg = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg)
        dlg._on_aa_clear_clicked()

        assert fake_repo.get_setting("audioaddict_listen_key", "") == "test-key-abc"
        assert dlg._aa_status_label.text() == "Saved"
