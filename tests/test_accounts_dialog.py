"""Tests for AccountsDialog — Twitch OAuth + AudioAddict view/clear.

UI-08: AccountsDialog shows Connected/Not connected, launches QProcess OAuth,
       Disconnect deletes token with confirmation.

Phase 48 D-04..D-07: AA group reflects ``audioaddict_listen_key`` saved state
       and lets the user clear it via Yes/No confirm. Dialog never writes a
       new AA key — editing lives in ImportDialog (plan 48-02).

Phase 999.3 D-08..D-12: Category+detail failure dialog with inline Retry;
       stderr JSON parser; persistent oauth.log.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QGroupBox, QLabel, QMessageBox

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


def _mock_proc_with_stderr(stderr_bytes: bytes = b"", stdout_bytes: bytes = b""):
    """Build a MagicMock QProcess whose readAll*Error/Output return given bytes."""
    from PySide6.QtCore import QProcess
    proc = MagicMock(spec=QProcess)
    # readAllStandardError().data() → bytes
    err_chunk = MagicMock()
    err_chunk.data.return_value = stderr_bytes
    proc.readAllStandardError.return_value = err_chunk
    # readAllStandardOutput().data() → bytes
    out_chunk = MagicMock()
    out_chunk.data.return_value = stdout_bytes
    proc.readAllStandardOutput.return_value = out_chunk
    return proc


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

        fake_token = "oauth-abc123"
        mock_proc = _mock_proc_with_stderr(
            stderr_bytes=b'{"ts":1.0,"category":"Success","detail":"","provider":"twitch"}\n',
            stdout_bytes=fake_token.encode(),
        )

        with patch("musicstreamer.ui_qt.accounts_dialog.QProcess", return_value=mock_proc):
            dlg = AccountsDialog(fake_repo)
            qtbot.addWidget(dlg)
            dlg._on_action_clicked()
            dlg._oauth_proc = mock_proc
            dlg._on_oauth_finished(0, QProcess.ExitStatus.NormalExit)

        assert os.path.exists(token_path)
        assert Path(token_path).read_text() == fake_token
        perms = oct(os.stat(token_path).st_mode & 0o777)
        assert perms == oct(0o600)
        assert "connected" in dlg._status_label.text().lower()

    def test_oauth_finished_failure_calls_show_failure_dialog(
        self, tmp_data_dir, qtbot, monkeypatch, fake_repo
    ):
        """Phase 999.3 D-08: failure calls _show_failure_dialog with parsed category+detail."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        from PySide6.QtCore import QProcess

        recorded: list[tuple[str, str]] = []
        monkeypatch.setattr(
            AccountsDialog,
            "_show_failure_dialog",
            lambda self, cat, det: recorded.append((cat, det)),
        )

        stderr = b'{"ts":1.0,"category":"WindowClosedBeforeLogin","detail":"","provider":"twitch"}\n'
        mock_proc = _mock_proc_with_stderr(stderr_bytes=stderr)

        with patch("musicstreamer.ui_qt.accounts_dialog.QProcess", return_value=mock_proc):
            dlg = AccountsDialog(fake_repo)
            qtbot.addWidget(dlg)
            dlg._on_action_clicked()
            dlg._oauth_proc = mock_proc
            dlg._on_oauth_finished(1, QProcess.ExitStatus.NormalExit)

        assert recorded == [("WindowClosedBeforeLogin", "")]
        assert "not connected" in dlg._status_label.text().lower()


class TestAccountsDialogStderrParsing:
    """Phase 999.3 D-12: parent parses last valid JSON line from stderr."""

    def test_oauth_finished_parses_stderr_category(
        self, tmp_data_dir, qtbot, monkeypatch, fake_repo
    ):
        """Single valid JSON event → _show_failure_dialog receives (category, detail)."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        from PySide6.QtCore import QProcess

        recorded: list[tuple[str, str]] = []
        monkeypatch.setattr(
            AccountsDialog, "_show_failure_dialog",
            lambda self, c, d: recorded.append((c, d)),
        )

        stderr = b'{"ts":1.0,"category":"LoginTimeout","detail":"120s","provider":"twitch"}\n'
        mock_proc = _mock_proc_with_stderr(stderr_bytes=stderr)

        with patch("musicstreamer.ui_qt.accounts_dialog.QProcess", return_value=mock_proc):
            dlg = AccountsDialog(fake_repo)
            qtbot.addWidget(dlg)
            dlg._oauth_proc = mock_proc
            dlg._on_oauth_finished(1, QProcess.ExitStatus.NormalExit)

        assert recorded == [("LoginTimeout", "120s")]

    def test_oauth_finished_keeps_last_event(
        self, tmp_data_dir, qtbot, monkeypatch, fake_repo
    ):
        """Multiple valid events — parser keeps the LAST one (D-12)."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        from PySide6.QtCore import QProcess

        recorded: list[tuple[str, str]] = []
        monkeypatch.setattr(
            AccountsDialog, "_show_failure_dialog",
            lambda self, c, d: recorded.append((c, d)),
        )

        stderr = (
            b'{"ts":1.0,"category":"WindowClosedBeforeLogin","detail":"","provider":"twitch"}\n'
            b'{"ts":2.0,"category":"LoginTimeout","detail":"120s","provider":"twitch"}\n'
        )
        mock_proc = _mock_proc_with_stderr(stderr_bytes=stderr)

        with patch("musicstreamer.ui_qt.accounts_dialog.QProcess", return_value=mock_proc):
            dlg = AccountsDialog(fake_repo)
            qtbot.addWidget(dlg)
            dlg._oauth_proc = mock_proc
            dlg._on_oauth_finished(1, QProcess.ExitStatus.NormalExit)

        assert recorded == [("LoginTimeout", "120s")]

    def test_oauth_finished_skips_malformed_json(
        self, tmp_data_dir, qtbot, monkeypatch, fake_repo
    ):
        """T-999.3-05: malformed JSON lines are skipped, valid trailing event wins."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        from PySide6.QtCore import QProcess

        recorded: list[tuple[str, str]] = []
        monkeypatch.setattr(
            AccountsDialog, "_show_failure_dialog",
            lambda self, c, d: recorded.append((c, d)),
        )

        stderr = (
            b'not json at all\n'
            b'{"garbage": true}\n'  # dict but no category key → skipped
            b'{"ts":1.0,"category":"WindowClosedBeforeLogin","detail":"","provider":"twitch"}\n'
        )
        mock_proc = _mock_proc_with_stderr(stderr_bytes=stderr)

        with patch("musicstreamer.ui_qt.accounts_dialog.QProcess", return_value=mock_proc):
            dlg = AccountsDialog(fake_repo)
            qtbot.addWidget(dlg)
            dlg._oauth_proc = mock_proc
            dlg._on_oauth_finished(1, QProcess.ExitStatus.NormalExit)

        assert recorded == [("WindowClosedBeforeLogin", "")]

    def test_oauth_finished_synthesizes_crash_on_no_event(
        self, tmp_data_dir, qtbot, monkeypatch, fake_repo
    ):
        """No parseable event + non-zero exit → synthetic SubprocessCrash."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        from PySide6.QtCore import QProcess

        recorded: list[tuple[str, str]] = []
        monkeypatch.setattr(
            AccountsDialog, "_show_failure_dialog",
            lambda self, c, d: recorded.append((c, d)),
        )

        mock_proc = _mock_proc_with_stderr(stderr_bytes=b"")

        with patch("musicstreamer.ui_qt.accounts_dialog.QProcess", return_value=mock_proc):
            dlg = AccountsDialog(fake_repo)
            qtbot.addWidget(dlg)
            dlg._oauth_proc = mock_proc
            dlg._on_oauth_finished(1, QProcess.ExitStatus.NormalExit)

        assert recorded == [("SubprocessCrash", "exit=1")]

    def test_oauth_finished_synthesizes_invalid_on_empty_token(
        self, tmp_data_dir, qtbot, monkeypatch, fake_repo
    ):
        """exit_code=0, empty stdout, empty stderr → InvalidTokenResponse empty_stdout."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        from PySide6.QtCore import QProcess

        recorded: list[tuple[str, str]] = []
        monkeypatch.setattr(
            AccountsDialog, "_show_failure_dialog",
            lambda self, c, d: recorded.append((c, d)),
        )

        mock_proc = _mock_proc_with_stderr(stderr_bytes=b"", stdout_bytes=b"")

        with patch("musicstreamer.ui_qt.accounts_dialog.QProcess", return_value=mock_proc):
            dlg = AccountsDialog(fake_repo)
            qtbot.addWidget(dlg)
            dlg._oauth_proc = mock_proc
            dlg._on_oauth_finished(0, QProcess.ExitStatus.NormalExit)

        assert recorded == [("InvalidTokenResponse", "empty_stdout")]


class TestAccountsDialogRetry:
    """Phase 999.3 D-09: Retry relaunches subprocess inline."""

    def test_retry_relaunches_subprocess(
        self, tmp_data_dir, qtbot, monkeypatch, fake_repo
    ):
        """Clicking Retry in the failure dialog re-invokes _launch_oauth_subprocess."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        from PySide6.QtCore import QProcess

        # Simulate the dialog exec() returning Accepted (Retry clicked).
        monkeypatch.setattr(
            QDialog, "exec",
            lambda self: QDialog.DialogCode.Accepted,
        )

        relaunch_calls: list[int] = []
        # Patch AFTER the first launch via _on_action_clicked is done — we
        # want to observe the RETRY call specifically.
        original_launch = AccountsDialog._launch_oauth_subprocess

        def counting_launch(self):
            relaunch_calls.append(1)

        stderr = b'{"ts":1.0,"category":"LoginTimeout","detail":"120s","provider":"twitch"}\n'
        mock_proc = _mock_proc_with_stderr(stderr_bytes=stderr)

        with patch("musicstreamer.ui_qt.accounts_dialog.QProcess", return_value=mock_proc):
            dlg = AccountsDialog(fake_repo)
            qtbot.addWidget(dlg)
            dlg._oauth_proc = mock_proc
            # Now swap the launch method so the Retry invocation is observable.
            monkeypatch.setattr(
                AccountsDialog, "_launch_oauth_subprocess", counting_launch
            )
            dlg._on_oauth_finished(1, QProcess.ExitStatus.NormalExit)

        assert len(relaunch_calls) == 1

    def test_close_does_not_relaunch(
        self, tmp_data_dir, qtbot, monkeypatch, fake_repo
    ):
        """Close (Rejected) does NOT relaunch subprocess."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        from PySide6.QtCore import QProcess

        monkeypatch.setattr(
            QDialog, "exec",
            lambda self: QDialog.DialogCode.Rejected,
        )

        relaunch_calls: list[int] = []

        def counting_launch(self):
            relaunch_calls.append(1)

        stderr = b'{"ts":1.0,"category":"LoginTimeout","detail":"120s","provider":"twitch"}\n'
        mock_proc = _mock_proc_with_stderr(stderr_bytes=stderr)

        with patch("musicstreamer.ui_qt.accounts_dialog.QProcess", return_value=mock_proc):
            dlg = AccountsDialog(fake_repo)
            qtbot.addWidget(dlg)
            dlg._oauth_proc = mock_proc
            monkeypatch.setattr(
                AccountsDialog, "_launch_oauth_subprocess", counting_launch
            )
            dlg._on_oauth_finished(1, QProcess.ExitStatus.NormalExit)

        assert relaunch_calls == []


class TestAccountsDialogFailureDialogPlainText:
    """T-40-04: every QLabel in the failure dialog uses PlainText format."""

    def test_failure_dialog_uses_plain_text(
        self, tmp_data_dir, qtbot, monkeypatch, fake_repo
    ):
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog

        built_dialogs: list[QDialog] = []
        original_exec = QDialog.exec

        def capture_exec(self):
            built_dialogs.append(self)
            # Walk children; we don't actually need to show the dialog.
            return QDialog.DialogCode.Rejected

        monkeypatch.setattr(QDialog, "exec", capture_exec)

        dlg = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg)
        dlg._show_failure_dialog("LoginTimeout", "120s")

        assert len(built_dialogs) == 1
        failure_dlg = built_dialogs[0]
        labels = failure_dlg.findChildren(QLabel)
        assert len(labels) >= 2, "dialog should contain at least title+detail labels"
        for lbl in labels:
            assert lbl.textFormat() == Qt.TextFormat.PlainText, (
                f"T-40-04: label {lbl.text()!r} is not PlainText"
            )

    def test_failure_dialog_unknown_category_uses_fallback(
        self, tmp_data_dir, qtbot, monkeypatch, fake_repo
    ):
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog

        built: list[QDialog] = []

        def capture_exec(self):
            built.append(self)
            return QDialog.DialogCode.Rejected

        monkeypatch.setattr(QDialog, "exec", capture_exec)

        dlg = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg)
        dlg._show_failure_dialog("SomeUnknownCategory", "")

        assert len(built) == 1
        labels = built[0].findChildren(QLabel)
        texts = " | ".join(lbl.text() for lbl in labels)
        assert "Unknown error" in texts
        assert "(no details provided)" in texts


class TestAccountsDialogOAuthLog:
    """Phase 999.3 D-11: failure + success events persist to oauth.log."""

    def test_failure_logs_event_to_oauth_log(
        self, tmp_data_dir, qtbot, monkeypatch, fake_repo
    ):
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        from PySide6.QtCore import QProcess

        # Swallow the dialog exec so the test doesn't block.
        monkeypatch.setattr(
            AccountsDialog, "_show_failure_dialog", lambda self, c, d: None
        )

        stderr = b'{"ts":1.0,"category":"LoginTimeout","detail":"120s","provider":"twitch"}\n'
        mock_proc = _mock_proc_with_stderr(stderr_bytes=stderr)

        with patch("musicstreamer.ui_qt.accounts_dialog.QProcess", return_value=mock_proc):
            dlg = AccountsDialog(fake_repo)
            qtbot.addWidget(dlg)
            dlg._oauth_proc = mock_proc
            dlg._on_oauth_finished(1, QProcess.ExitStatus.NormalExit)

        log_path = paths.oauth_log_path()
        assert os.path.exists(log_path), "oauth.log should have been created"
        with open(log_path) as fh:
            lines = fh.readlines()
        assert len(lines) == 1
        obj = json.loads(lines[0])
        assert obj["category"] == "LoginTimeout"
        assert obj["detail"] == "120s"
        assert obj["provider"] == "twitch"

    def test_success_logs_success_event(
        self, tmp_data_dir, qtbot, fake_repo
    ):
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        from PySide6.QtCore import QProcess

        token_path = paths.twitch_token_path()
        os.makedirs(os.path.dirname(token_path), exist_ok=True)

        stderr = b'{"ts":2.5,"category":"Success","detail":"","provider":"twitch"}\n'
        mock_proc = _mock_proc_with_stderr(
            stderr_bytes=stderr, stdout_bytes=b"abc123token"
        )

        with patch("musicstreamer.ui_qt.accounts_dialog.QProcess", return_value=mock_proc):
            dlg = AccountsDialog(fake_repo)
            qtbot.addWidget(dlg)
            dlg._oauth_proc = mock_proc
            dlg._on_oauth_finished(0, QProcess.ExitStatus.NormalExit)

        log_path = paths.oauth_log_path()
        assert os.path.exists(log_path)
        with open(log_path) as fh:
            lines = fh.readlines()
        assert len(lines) == 1
        obj = json.loads(lines[0])
        assert obj["category"] == "Success"
        assert obj["provider"] == "twitch"

    def test_logger_failure_does_not_block_dialog(
        self, tmp_data_dir, qtbot, monkeypatch, fake_repo
    ):
        """Phase 999.3 D-11: if OAuthLogger init raises, failure dialog still shown."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        from musicstreamer import oauth_log
        from PySide6.QtCore import QProcess

        def boom(self, log_path):  # replaces __init__
            raise OSError("disk full")

        monkeypatch.setattr(oauth_log.OAuthLogger, "__init__", boom)

        recorded: list[tuple[str, str]] = []
        monkeypatch.setattr(
            AccountsDialog, "_show_failure_dialog",
            lambda self, c, d: recorded.append((c, d)),
        )

        stderr = b'{"ts":1.0,"category":"LoginTimeout","detail":"120s","provider":"twitch"}\n'
        mock_proc = _mock_proc_with_stderr(stderr_bytes=stderr)

        with patch("musicstreamer.ui_qt.accounts_dialog.QProcess", return_value=mock_proc):
            dlg = AccountsDialog(fake_repo)
            qtbot.addWidget(dlg)
            dlg._oauth_proc = mock_proc
            dlg._on_oauth_finished(1, QProcess.ExitStatus.NormalExit)

        # Logging failure must NOT prevent the user-facing dialog.
        assert recorded == [("LoginTimeout", "120s")]


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


class TestAccountsDialogYouTube:
    """Phase 53: YouTube cookie group — status, button toggle, disconnect, post-import refresh."""

    def test_youtube_group_present(self, tmp_data_dir, qtbot, fake_repo):
        """AccountsDialog has a YouTube QGroupBox with status label + action button."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        dlg = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg)
        group_titles = [box.title() for box in dlg.findChildren(QGroupBox)]
        assert "YouTube" in group_titles

    def test_status_not_connected(self, tmp_data_dir, qtbot, fake_repo):
        """When cookies.txt does not exist: status label 'Not connected'."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        dlg = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg)
        assert dlg._youtube_status_label.text() == "Not connected"

    def test_status_connected(self, tmp_data_dir, qtbot, fake_repo):
        """When cookies.txt exists: status label 'Connected'."""
        cookies_path = paths.cookies_path()
        os.makedirs(os.path.dirname(cookies_path), exist_ok=True)
        Path(cookies_path).write_text("# dummy cookies")
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        dlg = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg)
        assert dlg._youtube_status_label.text() == "Connected"

    def test_button_label_not_connected(self, tmp_data_dir, qtbot, fake_repo):
        """When not connected: action button label is 'Import YouTube Cookies...'."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        dlg = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg)
        assert dlg._youtube_action_btn.text() == "Import YouTube Cookies..."

    def test_button_label_connected(self, tmp_data_dir, qtbot, fake_repo):
        """When connected: action button label is 'Disconnect'."""
        cookies_path = paths.cookies_path()
        os.makedirs(os.path.dirname(cookies_path), exist_ok=True)
        Path(cookies_path).write_text("# dummy cookies")
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        dlg = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg)
        assert dlg._youtube_action_btn.text() == "Disconnect"

    def test_import_launches_cookie_dialog(self, tmp_data_dir, qtbot, fake_repo, monkeypatch):
        """Clicking Import... constructs CookieImportDialog with forwarded toast_callback."""
        from musicstreamer.ui_qt import cookie_import_dialog as cid_mod
        captured: dict = {}

        class FakeCookieDlg:
            exec_called = False

            def __init__(self, toast_cb, parent=None):
                captured["toast_cb"] = toast_cb
                captured["parent"] = parent

            def exec(self):
                FakeCookieDlg.exec_called = True
                return QDialog.DialogCode.Rejected

        monkeypatch.setattr(cid_mod, "CookieImportDialog", FakeCookieDlg)
        toasts: list[str] = []
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        dlg = AccountsDialog(fake_repo, toast_callback=toasts.append)
        qtbot.addWidget(dlg)
        dlg._on_youtube_action_clicked()
        assert FakeCookieDlg.exec_called
        assert captured["toast_cb"] is toasts.append
        assert captured["parent"] is dlg

    def test_post_import_refreshes_status(self, tmp_data_dir, qtbot, fake_repo, monkeypatch):
        """After FakeCookieDlg.exec() writes a cookies file, status flips to 'Connected'."""
        from musicstreamer.ui_qt import cookie_import_dialog as cid_mod
        cookies_path = paths.cookies_path()

        class FakeCookieDlg:
            def __init__(self, toast_cb, parent=None):
                pass

            def exec(self):
                os.makedirs(os.path.dirname(cookies_path), exist_ok=True)
                Path(cookies_path).write_text("# imported")
                return QDialog.DialogCode.Accepted

        monkeypatch.setattr(cid_mod, "CookieImportDialog", FakeCookieDlg)
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        dlg = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg)
        dlg._on_youtube_action_clicked()
        assert dlg._youtube_status_label.text() == "Connected"
        assert dlg._youtube_action_btn.text() == "Disconnect"

    def test_post_cancel_status_unchanged(self, tmp_data_dir, qtbot, fake_repo, monkeypatch):
        """After FakeCookieDlg.exec() returns Rejected (no file), status stays 'Not connected'."""
        from musicstreamer.ui_qt import cookie_import_dialog as cid_mod

        class FakeCookieDlg:
            def __init__(self, toast_cb, parent=None):
                pass

            def exec(self):
                # No file written — simulates cancel
                return QDialog.DialogCode.Rejected

        monkeypatch.setattr(cid_mod, "CookieImportDialog", FakeCookieDlg)
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        dlg = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg)
        dlg._on_youtube_action_clicked()
        # _update_status() was called unconditionally — idempotent, status unchanged
        assert dlg._youtube_status_label.text() == "Not connected"
        assert dlg._youtube_action_btn.text() == "Import YouTube Cookies..."

    def test_disconnect_removes_cookies(self, tmp_data_dir, qtbot, fake_repo, monkeypatch):
        """Disconnect → Yes → os.remove(cookies_path) + status refresh to 'Not connected'."""
        cookies_path = paths.cookies_path()
        os.makedirs(os.path.dirname(cookies_path), exist_ok=True)
        Path(cookies_path).write_text("# dummy")
        monkeypatch.setattr(
            QMessageBox, "question",
            lambda *_args, **_kw: QMessageBox.StandardButton.Yes,
        )
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        dlg = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg)
        dlg._on_youtube_action_clicked()
        assert not os.path.exists(cookies_path)
        assert dlg._youtube_status_label.text() == "Not connected"

    def test_disconnect_cancel_keeps_cookies(self, tmp_data_dir, qtbot, fake_repo, monkeypatch):
        """Disconnect → No → cookies file untouched, status stays 'Connected'."""
        cookies_path = paths.cookies_path()
        os.makedirs(os.path.dirname(cookies_path), exist_ok=True)
        Path(cookies_path).write_text("# dummy")
        monkeypatch.setattr(
            QMessageBox, "question",
            lambda *_args, **_kw: QMessageBox.StandardButton.No,
        )
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        dlg = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg)
        dlg._on_youtube_action_clicked()
        assert os.path.exists(cookies_path)
        assert dlg._youtube_status_label.text() == "Connected"

    def test_disconnect_file_already_gone(self, tmp_data_dir, qtbot, fake_repo, monkeypatch):
        """Race: file deleted between status check and Disconnect click — no exception escapes."""
        cookies_path = paths.cookies_path()
        os.makedirs(os.path.dirname(cookies_path), exist_ok=True)
        Path(cookies_path).write_text("# transient")
        monkeypatch.setattr(
            QMessageBox, "question",
            lambda *_a, **_kw: QMessageBox.StandardButton.Yes,
        )
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        dlg = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg)
        # Simulate Phase 999.7 auto-clear racing between status check and click:
        os.remove(cookies_path)
        # Must not raise:
        dlg._on_youtube_action_clicked()
        assert dlg._youtube_status_label.text() == "Not connected"

    def test_disconnect_isolates_youtube(self, tmp_data_dir, qtbot, fake_repo, monkeypatch):
        """D-04: YouTube Disconnect does not touch Twitch token or AA listen key."""
        cookies_path = paths.cookies_path()
        os.makedirs(os.path.dirname(cookies_path), exist_ok=True)
        Path(cookies_path).write_text("# yt cookies")
        twitch_token = paths.twitch_token_path()
        os.makedirs(os.path.dirname(twitch_token), exist_ok=True)
        Path(twitch_token).write_text("twitch-token-value")
        fake_repo.set_setting("audioaddict_listen_key", "dummykey")
        monkeypatch.setattr(
            QMessageBox, "question",
            lambda *_a, **_kw: QMessageBox.StandardButton.Yes,
        )
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        dlg = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg)
        dlg._on_youtube_action_clicked()
        assert not os.path.exists(cookies_path)
        assert os.path.exists(twitch_token)  # D-04: untouched
        assert fake_repo.get_setting("audioaddict_listen_key", "") == "dummykey"  # D-04: untouched

    def test_group_order(self, tmp_data_dir, qtbot, fake_repo):
        """D-09: Group order in layout is YouTube → Twitch → AudioAddict."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        dlg = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg)
        layout = dlg.layout()
        groupboxes = []
        for i in range(layout.count()):
            w = layout.itemAt(i).widget()
            if isinstance(w, QGroupBox):
                groupboxes.append(w.title())
        assert groupboxes == ["YouTube", "Twitch", "AudioAddict"]

    def test_status_label_plain_text(self, tmp_data_dir, qtbot, fake_repo):
        """T-40-04: YouTube status label uses Qt.TextFormat.PlainText."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        dlg = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg)
        assert dlg._youtube_status_label.textFormat() == Qt.TextFormat.PlainText
