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

        # Phase 76 CR-01: _show_failure_dialog signature is now (provider, cat, det).
        recorded: list[tuple[str, str, str]] = []
        monkeypatch.setattr(
            AccountsDialog,
            "_show_failure_dialog",
            lambda self, prov, cat, det: recorded.append((prov, cat, det)),
        )

        stderr = b'{"ts":1.0,"category":"WindowClosedBeforeLogin","detail":"","provider":"twitch"}\n'
        mock_proc = _mock_proc_with_stderr(stderr_bytes=stderr)

        with patch("musicstreamer.ui_qt.accounts_dialog.QProcess", return_value=mock_proc):
            dlg = AccountsDialog(fake_repo)
            qtbot.addWidget(dlg)
            dlg._on_action_clicked()
            dlg._oauth_proc = mock_proc
            dlg._on_oauth_finished(1, QProcess.ExitStatus.NormalExit)

        assert recorded == [("twitch", "WindowClosedBeforeLogin", "")]
        assert "not connected" in dlg._status_label.text().lower()


class TestAccountsDialogStderrParsing:
    """Phase 999.3 D-12: parent parses last valid JSON line from stderr."""

    def test_oauth_finished_parses_stderr_category(
        self, tmp_data_dir, qtbot, monkeypatch, fake_repo
    ):
        """Single valid JSON event → _show_failure_dialog receives (provider, category, detail)."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        from PySide6.QtCore import QProcess

        # Phase 76 CR-01: signature widened to (provider, category, detail).
        recorded: list[tuple[str, str, str]] = []
        monkeypatch.setattr(
            AccountsDialog, "_show_failure_dialog",
            lambda self, p, c, d: recorded.append((p, c, d)),
        )

        stderr = b'{"ts":1.0,"category":"LoginTimeout","detail":"120s","provider":"twitch"}\n'
        mock_proc = _mock_proc_with_stderr(stderr_bytes=stderr)

        with patch("musicstreamer.ui_qt.accounts_dialog.QProcess", return_value=mock_proc):
            dlg = AccountsDialog(fake_repo)
            qtbot.addWidget(dlg)
            dlg._oauth_proc = mock_proc
            dlg._on_oauth_finished(1, QProcess.ExitStatus.NormalExit)

        assert recorded == [("twitch", "LoginTimeout", "120s")]

    def test_oauth_finished_keeps_last_event(
        self, tmp_data_dir, qtbot, monkeypatch, fake_repo
    ):
        """Multiple valid events — parser keeps the LAST one (D-12)."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        from PySide6.QtCore import QProcess

        # Phase 76 CR-01: signature widened to (provider, category, detail).
        recorded: list[tuple[str, str, str]] = []
        monkeypatch.setattr(
            AccountsDialog, "_show_failure_dialog",
            lambda self, p, c, d: recorded.append((p, c, d)),
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

        assert recorded == [("twitch", "LoginTimeout", "120s")]

    def test_oauth_finished_skips_malformed_json(
        self, tmp_data_dir, qtbot, monkeypatch, fake_repo
    ):
        """T-999.3-05: malformed JSON lines are skipped, valid trailing event wins."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        from PySide6.QtCore import QProcess

        # Phase 76 CR-01: signature widened to (provider, category, detail).
        recorded: list[tuple[str, str, str]] = []
        monkeypatch.setattr(
            AccountsDialog, "_show_failure_dialog",
            lambda self, p, c, d: recorded.append((p, c, d)),
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

        assert recorded == [("twitch", "WindowClosedBeforeLogin", "")]

    def test_oauth_finished_synthesizes_crash_on_no_event(
        self, tmp_data_dir, qtbot, monkeypatch, fake_repo
    ):
        """No parseable event + non-zero exit → synthetic SubprocessCrash."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        from PySide6.QtCore import QProcess

        # Phase 76 CR-01: signature widened to (provider, category, detail).
        recorded: list[tuple[str, str, str]] = []
        monkeypatch.setattr(
            AccountsDialog, "_show_failure_dialog",
            lambda self, p, c, d: recorded.append((p, c, d)),
        )

        mock_proc = _mock_proc_with_stderr(stderr_bytes=b"")

        with patch("musicstreamer.ui_qt.accounts_dialog.QProcess", return_value=mock_proc):
            dlg = AccountsDialog(fake_repo)
            qtbot.addWidget(dlg)
            dlg._oauth_proc = mock_proc
            dlg._on_oauth_finished(1, QProcess.ExitStatus.NormalExit)

        assert recorded == [("twitch", "SubprocessCrash", "exit=1")]

    def test_oauth_finished_synthesizes_invalid_on_empty_token(
        self, tmp_data_dir, qtbot, monkeypatch, fake_repo
    ):
        """exit_code=0, empty stdout, empty stderr → InvalidTokenResponse empty_stdout."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        from PySide6.QtCore import QProcess

        # Phase 76 CR-01: signature widened to (provider, category, detail).
        recorded: list[tuple[str, str, str]] = []
        monkeypatch.setattr(
            AccountsDialog, "_show_failure_dialog",
            lambda self, p, c, d: recorded.append((p, c, d)),
        )

        mock_proc = _mock_proc_with_stderr(stderr_bytes=b"", stdout_bytes=b"")

        with patch("musicstreamer.ui_qt.accounts_dialog.QProcess", return_value=mock_proc):
            dlg = AccountsDialog(fake_repo)
            qtbot.addWidget(dlg)
            dlg._oauth_proc = mock_proc
            dlg._on_oauth_finished(0, QProcess.ExitStatus.NormalExit)

        assert recorded == [("twitch", "InvalidTokenResponse", "empty_stdout")]


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
        # Phase 76 CR-01: signature widened to (provider, category, detail).
        dlg._show_failure_dialog("twitch", "LoginTimeout", "120s")

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
        # Phase 76 CR-01: signature widened to (provider, category, detail).
        dlg._show_failure_dialog("twitch", "SomeUnknownCategory", "")

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
        # Phase 76 CR-01: signature widened to (provider, category, detail).
        monkeypatch.setattr(
            AccountsDialog, "_show_failure_dialog", lambda self, p, c, d: None
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

        # Phase 76 CR-01: signature widened to (provider, category, detail).
        recorded: list[tuple[str, str, str]] = []
        monkeypatch.setattr(
            AccountsDialog, "_show_failure_dialog",
            lambda self, p, c, d: recorded.append((p, c, d)),
        )

        stderr = b'{"ts":1.0,"category":"LoginTimeout","detail":"120s","provider":"twitch"}\n'
        mock_proc = _mock_proc_with_stderr(stderr_bytes=stderr)

        with patch("musicstreamer.ui_qt.accounts_dialog.QProcess", return_value=mock_proc):
            dlg = AccountsDialog(fake_repo)
            qtbot.addWidget(dlg)
            dlg._oauth_proc = mock_proc
            dlg._on_oauth_finished(1, QProcess.ExitStatus.NormalExit)

        # Logging failure must NOT prevent the user-facing dialog.
        assert recorded == [("twitch", "LoginTimeout", "120s")]


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
        toast_cb = toasts.append  # capture reference so 'is' comparison works
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        dlg = AccountsDialog(fake_repo, toast_callback=toast_cb)
        qtbot.addWidget(dlg)
        dlg._on_youtube_action_clicked()
        assert FakeCookieDlg.exec_called
        assert captured["toast_cb"] is toast_cb
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
        """Race: file deleted between _is_youtube_connected() and os.remove() — no exception escapes.

        Simulates Phase 999.7 auto-clear race by keeping the file present so
        _is_youtube_connected() returns True (entering the Disconnect branch),
        then patching os.remove to delete the file AND raise FileNotFoundError
        (simulating the file being auto-cleared a nanosecond before our os.remove).
        After the try/except silences the error, _update_status() finds the file
        gone and correctly sets status to "Not connected".
        """
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
        # Simulate the race: os.remove raises FileNotFoundError (auto-cleared between
        # _is_youtube_connected() check and os.remove() call — T-53-01).
        # Also delete the actual file so _update_status() sees "Not connected" correctly.
        def raise_fnf(path):
            if os.path.exists(path):
                os.unlink(path)  # clean up via unlink (not os.remove, to avoid recursion)
            raise FileNotFoundError("gone")
        monkeypatch.setattr("musicstreamer.ui_qt.accounts_dialog.os.remove", raise_fnf)
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
        """D-09 / D-04c: Group order in layout is YouTube → GBS.FM → Twitch → AudioAddict."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        dlg = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg)
        layout = dlg.layout()
        groupboxes = []
        for i in range(layout.count()):
            w = layout.itemAt(i).widget()
            if isinstance(w, QGroupBox):
                groupboxes.append(w.title())
        assert groupboxes == ["YouTube", "GBS.FM", "Twitch", "AudioAddict"]

    def test_status_label_plain_text(self, tmp_data_dir, qtbot, fake_repo):
        """T-40-04: YouTube status label uses Qt.TextFormat.PlainText."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        dlg = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg)
        assert dlg._youtube_status_label.textFormat() == Qt.TextFormat.PlainText


class TestAccountsDialogGBS:
    """Phase 60 / GBS-01b: AccountsDialog _gbs_box group."""

    def test_gbs_box_position_between_youtube_and_twitch(self, qtbot, fake_repo, tmp_path, monkeypatch):
        """D-04c: _gbs_box must render BETWEEN YouTube and Twitch."""
        import os
        from musicstreamer import paths
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        monkeypatch.setattr(paths, "_root_override", str(tmp_path))
        os.makedirs(str(tmp_path), exist_ok=True)  # HIGH 3: explicit setup boilerplate
        dlg = AccountsDialog(fake_repo, toast_callback=lambda t: None)
        qtbot.addWidget(dlg)
        # _gbs_box exists with correct title
        assert hasattr(dlg, "_gbs_box")
        assert dlg._gbs_box.title() == "GBS.FM"
        # Status label uses PlainText (T-40-04)
        from PySide6.QtCore import Qt
        assert dlg._gbs_status_label.textFormat() == Qt.TextFormat.PlainText
        # Layout: _youtube_box appears before _gbs_box appears before twitch group
        layout = dlg.layout()
        widgets = [layout.itemAt(i).widget() for i in range(layout.count())]
        # Filter to QGroupBoxes only
        from PySide6.QtWidgets import QGroupBox
        groups = [w for w in widgets if isinstance(w, QGroupBox)]
        titles = [g.title() for g in groups]
        # Expect YouTube, GBS.FM, Twitch in that order (followed by AudioAddict + maybe close button container)
        assert "YouTube" in titles
        assert "GBS.FM" in titles
        assert titles.index("YouTube") < titles.index("GBS.FM")
        # Twitch group title may be e.g. "Twitch" — just assert _gbs_box appears before whatever comes next
        if "Twitch" in titles:
            assert titles.index("GBS.FM") < titles.index("Twitch")

    # Migrated for Phase 76 D-03 collapse — was test_gbs_status_initial_not_connected
    # at tests/test_accounts_dialog.py:919-929 (pre-Plan-76-04). Original test
    # asserted the old primary-button text `"Import GBS.FM Cookies..."` which
    # 76-03 replaced with `"Connect to GBS.FM…"` (single U+2026). Migrated to
    # assert the new text AND that the secondary import button is visible in
    # the not-connected state (Plan 76-03 D-14 surface).
    def test_gbs_status_initial_not_connected(self, qtbot, fake_repo, tmp_path, monkeypatch):
        """Fresh state: cookies file missing → 'Not connected' label + 'Connect to GBS.FM…' primary button + visible import button."""
        import os
        from musicstreamer import paths
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        monkeypatch.setattr(paths, "_root_override", str(tmp_path))
        os.makedirs(str(tmp_path), exist_ok=True)  # HIGH 3: explicit setup boilerplate
        dlg = AccountsDialog(fake_repo, toast_callback=lambda t: None)
        qtbot.addWidget(dlg)
        assert dlg._gbs_status_label.text() == "Not connected"
        # Plan 76-03: primary button now says "Connect to GBS.FM…" (U+2026).
        assert dlg._gbs_action_btn.text() == "Connect to GBS.FM…"
        # Plan 76-03 D-14: secondary import button visible in not-connected state.
        # Use isHidden() instead of isVisible(): Qt widgets that have not been
        # shown report isVisible()==False regardless of setVisible(True), but
        # isHidden() reflects the explicit setVisible(False) state.
        assert dlg._gbs_import_btn.isHidden() is False

    def test_gbs_status_connected_when_cookies_present(self, qtbot, fake_repo, tmp_path, monkeypatch):
        """Cookies file exists → 'Connected' label + 'Disconnect' button."""
        import os
        from musicstreamer import paths
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        monkeypatch.setattr(paths, "_root_override", str(tmp_path))
        # Create the gbs cookies file
        os.makedirs(str(tmp_path), exist_ok=True)
        with open(paths.gbs_cookies_path(), "w") as f:
            f.write("# fake")
        dlg = AccountsDialog(fake_repo, toast_callback=lambda t: None)
        qtbot.addWidget(dlg)
        assert dlg._gbs_status_label.text() == "Connected"
        assert dlg._gbs_action_btn.text() == "Disconnect"

    def test_gbs_disconnect_removes_file_and_updates_status(self, qtbot, fake_repo, tmp_path, monkeypatch):
        """Disconnect path: confirm Yes → os.remove → status flips to 'Not connected'."""
        import os
        from PySide6.QtWidgets import QMessageBox
        from musicstreamer import paths
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        monkeypatch.setattr(paths, "_root_override", str(tmp_path))
        os.makedirs(str(tmp_path), exist_ok=True)
        with open(paths.gbs_cookies_path(), "w") as f:
            f.write("# fake")
        dlg = AccountsDialog(fake_repo, toast_callback=lambda t: None)
        qtbot.addWidget(dlg)
        # Stub QMessageBox.question to return Yes
        monkeypatch.setattr(QMessageBox, "question",
                            staticmethod(lambda *a, **kw: QMessageBox.StandardButton.Yes))
        dlg._on_gbs_action_clicked()
        assert not os.path.exists(paths.gbs_cookies_path())
        assert dlg._gbs_status_label.text() == "Not connected"

    def test_gbs_disconnect_oserror_tolerated(self, qtbot, fake_repo, tmp_path, monkeypatch):
        """HIGH 2 fix: cookie remove() raises OSError variant — must not propagate.

        Covers:
        - FileNotFoundError (race: cookie removed externally between is_connected and remove())
        - PermissionError (file mode flipped to 0o000 mid-flight)
        - IsADirectoryError (someone replaced the cookie file with a directory)
        """
        import os
        from PySide6.QtWidgets import QMessageBox
        from musicstreamer import paths
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        monkeypatch.setattr(paths, "_root_override", str(tmp_path))
        os.makedirs(str(tmp_path), exist_ok=True)
        dlg = AccountsDialog(fake_repo, toast_callback=lambda t: None)
        qtbot.addWidget(dlg)
        monkeypatch.setattr(dlg, "_is_gbs_connected", lambda: True)
        monkeypatch.setattr(QMessageBox, "question",
                            staticmethod(lambda *a, **kw: QMessageBox.StandardButton.Yes))

        # Variant A: file doesn't exist (FileNotFoundError)
        dlg._on_gbs_action_clicked()  # No exception expected

        # Variant B: simulate PermissionError via monkeypatched os.remove
        def _raise_permission(_path):
            raise PermissionError("simulated 0o000 perms")
        monkeypatch.setattr(os, "remove", _raise_permission)
        dlg._on_gbs_action_clicked()  # No exception expected

        # Variant C: simulate IsADirectoryError
        def _raise_isadir(_path):
            raise IsADirectoryError("simulated directory at cookie path")
        monkeypatch.setattr(os, "remove", _raise_isadir)
        dlg._on_gbs_action_clicked()  # No exception expected

    # Migrated for Phase 76 D-03 collapse — was test_gbs_connect_opens_dialog_with_correct_kwargs
    # at tests/test_accounts_dialog.py:1000-1020 (pre-Plan-76-04). Original test
    # asserted that the connect-branch of _on_gbs_action_clicked directly opened
    # CookieImportDialog with GBS.FM kwargs. Plan 76-03 D-09 rewired the connect
    # branch to delegate to _launch_gbs_login_subprocess() instead; the
    # CookieImportDialog flow MOVED to a separate _on_gbs_import_clicked slot
    # bound to the new secondary [Import cookies file…] button. The
    # CookieImportDialog-kwargs assertion is preserved by the new
    # test_gbs_import_button_opens_cookieimportdialog (Task 2 below).
    def test_gbs_connect_delegates_to_launch_subprocess(self, qtbot, fake_repo, tmp_path, monkeypatch):
        """Connect path: not-connected click delegates to _launch_gbs_login_subprocess (Plan 76-03 D-09)."""
        import os
        from musicstreamer import paths
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        monkeypatch.setattr(paths, "_root_override", str(tmp_path))
        os.makedirs(str(tmp_path), exist_ok=True)
        dlg = AccountsDialog(fake_repo, toast_callback=lambda t: None)
        qtbot.addWidget(dlg)
        # Sanity: ensure not-connected state (no cookies file).
        assert not dlg._is_gbs_connected()
        # Replace _launch_gbs_login_subprocess with a recorder so we don't
        # actually start a subprocess. The test asserts the delegation.
        called = {"count": 0}
        def _record():
            called["count"] += 1
        monkeypatch.setattr(dlg, "_launch_gbs_login_subprocess", _record)
        # Mirror: tests/test_accounts_dialog.py:158-178 (Twitch connect launches QProcess)
        dlg._on_gbs_action_clicked()
        assert called["count"] == 1

    # --------------------------------------------------------------
    # New for Plan 76-04: status enumeration + secondary import button
    # --------------------------------------------------------------

    def test_gbs_status_shows_connected_when_cookies_present(self, qtbot, fake_repo, tmp_path, monkeypatch):
        """Plan 76-03 D-03: 2-state enumeration — connected → 'Connected' + 'Disconnect' + import-btn hidden."""
        import os
        from musicstreamer import paths
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        monkeypatch.setattr(paths, "_root_override", str(tmp_path))
        os.makedirs(str(tmp_path), exist_ok=True)
        # Create the cookies file BEFORE dialog construction so initial _update_status
        # sees the connected state.
        with open(paths.gbs_cookies_path(), "w") as f:
            f.write("# fake cookies present")
        dlg = AccountsDialog(fake_repo, toast_callback=lambda t: None)
        qtbot.addWidget(dlg)
        # Plan 76-03 chose "Connected" (not "Connected (cookies)"); accept either.
        assert dlg._gbs_status_label.text() in {"Connected", "Connected (cookies)"}
        assert dlg._gbs_action_btn.text() == "Disconnect"
        # Plan 76-03 D-14: import button hidden when connected.
        # Use isHidden() (reflects setVisible(False) state) rather than
        # isVisible() which is False for any not-yet-shown widget.
        assert dlg._gbs_import_btn.isHidden() is True

    def test_gbs_status_shows_not_connected_when_no_cookies(self, qtbot, fake_repo, tmp_path, monkeypatch):
        """Plan 76-03 D-03: 2-state enumeration — not-connected → primary text 'Connect to GBS.FM…' + import-btn visible."""
        import os
        from musicstreamer import paths
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        monkeypatch.setattr(paths, "_root_override", str(tmp_path))
        os.makedirs(str(tmp_path), exist_ok=True)
        # No cookies file → not-connected.
        dlg = AccountsDialog(fake_repo, toast_callback=lambda t: None)
        qtbot.addWidget(dlg)
        # Belt-and-braces: monkeypatch _is_gbs_connected to False then call _update_status
        # so this test also exercises the explicit recompute path (independent of disk state).
        monkeypatch.setattr(dlg, "_is_gbs_connected", lambda: False)
        dlg._update_status()
        assert dlg._gbs_status_label.text() == "Not connected"
        assert dlg._gbs_action_btn.text() == "Connect to GBS.FM…"
        assert dlg._gbs_import_btn.isHidden() is False

    def test_gbs_import_button_exists_with_correct_text_and_handler(self, qtbot, fake_repo, tmp_path, monkeypatch):
        """Plan 76-03 D-14: secondary [Import cookies file…] button exists with the correct text + binds the import slot."""
        import os
        from PySide6.QtWidgets import QPushButton
        from musicstreamer import paths
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        monkeypatch.setattr(paths, "_root_override", str(tmp_path))
        os.makedirs(str(tmp_path), exist_ok=True)
        dlg = AccountsDialog(fake_repo, toast_callback=lambda t: None)
        qtbot.addWidget(dlg)
        # Type check.
        assert isinstance(dlg._gbs_import_btn, QPushButton)
        # Text contains "Import cookies file" and the single U+2026 ellipsis
        # (NOT three-dot variant "..." — T-76-D consistency with the 76-03 surface).
        text = dlg._gbs_import_btn.text()
        assert "Import cookies file" in text
        assert "…" in text  # U+2026 HORIZONTAL ELLIPSIS
        assert "..." not in text  # three-dot variant must NOT be present
        # Bound handler exists on the dialog.
        assert hasattr(dlg, "_on_gbs_import_clicked")
        assert callable(dlg._on_gbs_import_clicked)

    # --------------------------------------------------------------
    # Plan 76-04 Task 2: subprocess launch + disconnect-flow + import-button
    # --------------------------------------------------------------

    # Mirror: tests/test_accounts_dialog.py:158-178 (TestAccountsDialogConnect Twitch launch shape)
    def test_gbs_action_launches_subprocess_when_not_connected(self, qtbot, fake_repo, tmp_path, monkeypatch):
        """Plan 76-03 D-09: not-connected primary click starts QProcess with --mode gbs."""
        import os
        from PySide6.QtCore import QProcess
        from musicstreamer import paths
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        monkeypatch.setattr(paths, "_root_override", str(tmp_path))
        os.makedirs(str(tmp_path), exist_ok=True)

        mock_proc = MagicMock(spec=QProcess)

        with patch("musicstreamer.ui_qt.accounts_dialog.QProcess", return_value=mock_proc):
            dlg = AccountsDialog(fake_repo, toast_callback=lambda t: None)
            qtbot.addWidget(dlg)
            # Sanity: not connected.
            assert not dlg._is_gbs_connected()
            dlg._on_gbs_action_clicked()

        # start() called exactly once.
        assert mock_proc.start.called
        call_args = mock_proc.start.call_args
        # First positional arg: sys.executable.
        # Second positional arg: argv list.
        args_list = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("arguments", [])
        # Argv MUST be exactly ["-m", "musicstreamer.oauth_helper", "--mode", "gbs"].
        assert args_list == ["-m", "musicstreamer.oauth_helper", "--mode", "gbs"]
        # Defensive substring check: "--mode" + "gbs" pair present.
        joined = " ".join(args_list)
        assert "--mode" in joined
        assert "gbs" in joined
        assert "oauth_helper" in joined

    # Mirror: tests/test_accounts_dialog.py:113-134 (TestAccountsDialogDisconnect Twitch disconnect-Yes shape)
    def test_gbs_disconnect_clears_cookies_with_yes(self, qtbot, fake_repo, tmp_path, monkeypatch):
        """Plan 76-03: disconnect-Yes deletes cookies file and refreshes status."""
        import os
        from PySide6.QtWidgets import QMessageBox
        from musicstreamer import paths
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        monkeypatch.setattr(paths, "_root_override", str(tmp_path))
        os.makedirs(str(tmp_path), exist_ok=True)
        # Create the cookies file so we start in connected state.
        cookies_path = paths.gbs_cookies_path()
        with open(cookies_path, "w") as f:
            f.write("# fake cookies for disconnect-yes test")

        dlg = AccountsDialog(fake_repo, toast_callback=lambda t: None)
        qtbot.addWidget(dlg)
        # Auto-confirm: Yes.
        monkeypatch.setattr(
            QMessageBox, "question",
            staticmethod(lambda *a, **kw: QMessageBox.StandardButton.Yes),
        )

        # Capture os.remove calls — patch BEFORE the click (handler imports os at module level).
        remove_mock = MagicMock(wraps=os.remove)
        monkeypatch.setattr(
            "musicstreamer.ui_qt.accounts_dialog.os.remove", remove_mock
        )

        dlg._on_gbs_action_clicked()

        # os.remove called with the cookies path.
        assert remove_mock.call_count == 1
        assert remove_mock.call_args[0][0] == cookies_path
        # Status flipped to Not connected (status refresh fired).
        assert dlg._gbs_status_label.text() == "Not connected"
        assert dlg._gbs_action_btn.text() == "Connect to GBS.FM…"

    # Mirror: tests/test_accounts_dialog.py:136-153 (TestAccountsDialogDisconnect Twitch disconnect-No shape)
    def test_gbs_disconnect_no_op_with_no(self, qtbot, fake_repo, tmp_path, monkeypatch):
        """Plan 76-03: disconnect-No is a no-op — cookies file untouched."""
        import os
        from PySide6.QtWidgets import QMessageBox
        from musicstreamer import paths
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        monkeypatch.setattr(paths, "_root_override", str(tmp_path))
        os.makedirs(str(tmp_path), exist_ok=True)
        cookies_path = paths.gbs_cookies_path()
        with open(cookies_path, "w") as f:
            f.write("# fake cookies for disconnect-no test")

        dlg = AccountsDialog(fake_repo, toast_callback=lambda t: None)
        qtbot.addWidget(dlg)
        # Auto-decline: No.
        monkeypatch.setattr(
            QMessageBox, "question",
            staticmethod(lambda *a, **kw: QMessageBox.StandardButton.No),
        )

        remove_mock = MagicMock()
        monkeypatch.setattr(
            "musicstreamer.ui_qt.accounts_dialog.os.remove", remove_mock
        )

        dlg._on_gbs_action_clicked()

        # os.remove NOT called.
        remove_mock.assert_not_called()
        # Cookies file still present.
        assert os.path.exists(cookies_path)
        # Status stays Connected (no toast / no state change).
        assert dlg._gbs_status_label.text() in {"Connected", "Connected (cookies)"}

    # Phase 60 HIGH 2 regression guard — separate from the existing
    # test_gbs_disconnect_oserror_tolerated which only checks
    # FileNotFoundError/PermissionError/IsADirectoryError don't propagate.
    # This test pins the specific PermissionError path AND verifies
    # _update_status still fires (UI consistency invariant).
    def test_gbs_disconnect_tolerates_oserror(self, qtbot, fake_repo, tmp_path, monkeypatch):
        """Plan 76-03 / Phase 60 HIGH 2: PermissionError on os.remove is swallowed; _update_status still fires."""
        import os
        from PySide6.QtWidgets import QMessageBox
        from musicstreamer import paths
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        monkeypatch.setattr(paths, "_root_override", str(tmp_path))
        os.makedirs(str(tmp_path), exist_ok=True)
        cookies_path = paths.gbs_cookies_path()
        with open(cookies_path, "w") as f:
            f.write("# fake cookies")

        dlg = AccountsDialog(fake_repo, toast_callback=lambda t: None)
        qtbot.addWidget(dlg)
        monkeypatch.setattr(
            QMessageBox, "question",
            staticmethod(lambda *a, **kw: QMessageBox.StandardButton.Yes),
        )

        # Track _update_status invocations.
        update_calls = {"count": 0}
        original_update = dlg._update_status
        def _counting_update():
            update_calls["count"] += 1
            return original_update()
        monkeypatch.setattr(dlg, "_update_status", _counting_update)

        # os.remove raises PermissionError (an OSError subclass).
        def _raise_perm(_path):
            raise PermissionError("simulated read-only fs")
        monkeypatch.setattr(
            "musicstreamer.ui_qt.accounts_dialog.os.remove", _raise_perm
        )

        # Handler MUST NOT propagate OSError.
        try:
            dlg._on_gbs_action_clicked()
        except OSError as exc:
            pytest.fail(f"OSError should be swallowed by handler, got: {exc!r}")

        # _update_status fired despite the swallowed error (UI consistency).
        assert update_calls["count"] >= 1

    # Mirror: pre-Plan-76-04 test_gbs_connect_opens_dialog_with_correct_kwargs
    # at tests/test_accounts_dialog.py:1000-1020 — the kwargs-on-CookieImportDialog
    # invariant moves here and now exercises the secondary import-button slot
    # (Plan 76-03 D-14) instead of the connect-branch.
    def test_gbs_import_button_opens_cookieimportdialog(self, qtbot, fake_repo, tmp_path, monkeypatch):
        """Plan 76-03 D-14: _on_gbs_import_clicked constructs CookieImportDialog with the GBS-FM kwargs."""
        import os
        from musicstreamer import paths, gbs_api
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        monkeypatch.setattr(paths, "_root_override", str(tmp_path))
        os.makedirs(str(tmp_path), exist_ok=True)

        captured = {}
        class FakeDialog:
            def __init__(self, *args, **kwargs):
                captured["args"] = args
                captured["kwargs"] = kwargs
                captured["exec_called"] = False
            def exec(self):
                captured["exec_called"] = True
                return 0

        # _on_gbs_import_clicked uses a deferred import:
        # `from musicstreamer.ui_qt.cookie_import_dialog import CookieImportDialog`.
        # Patch at the source module — the deferred import resolves against the
        # real module's namespace at call time.
        monkeypatch.setattr(
            "musicstreamer.ui_qt.cookie_import_dialog.CookieImportDialog", FakeDialog
        )

        dlg = AccountsDialog(fake_repo, toast_callback=lambda t: None)
        qtbot.addWidget(dlg)
        dlg._on_gbs_import_clicked()

        # FakeDialog constructed once and exec()ed.
        assert "kwargs" in captured
        assert captured["exec_called"] is True
        # Four required kwargs (Plan 76-03 D-14 verbatim).
        assert captured["kwargs"]["target_label"] == "GBS.FM"
        assert captured["kwargs"]["cookies_path"] is paths.gbs_cookies_path
        assert captured["kwargs"]["validator"] is gbs_api._validate_gbs_cookies
        assert captured["kwargs"]["oauth_mode"] is None

    # --------------------------------------------------------------
    # Plan 76-04 Task 3: _on_gbs_login_finished — success / failure /
    # invalid-Netscape / anti-pitfall regression guards
    # Mirror sources for the shape:
    #   tests/test_accounts_dialog.py:196-251 (TestAccountsDialogOAuthFinished)
    #   tests/test_accounts_dialog.py:254-381 (TestAccountsDialogStderrParsing)
    #   tests/test_accounts_dialog.py:454-508 (TestAccountsDialogFailureDialogPlainText)
    #   tests/test_accounts_dialog.py:67     (_mock_proc_with_stderr helper)
    # --------------------------------------------------------------

    # Verbatim valid-Netscape fixture from PLAN 76-04 <interfaces> block.
    # Synthetic literals (T-76-T4 mitigation — no real session IDs).
    _GBS_NETSCAPE_VALID = (
        "# Netscape HTTP Cookie File\n"
        ".gbs.fm\tTRUE\t/\tTRUE\t1799999999\tsessionid\ttest_sessionid_value\n"
        ".gbs.fm\tTRUE\t/\tFALSE\t1799999999\tcsrftoken\ttest_csrftoken_value\n"
    )

    # Mirror: tests/test_accounts_dialog.py:199-224 (Twitch success-path token write)
    def test_gbs_login_finished_writes_cookies_on_success(self, qtbot, fake_repo, tmp_path, monkeypatch):
        """Plan 76-03: exit 0 + valid Netscape stdout writes to gbs_cookies_path with 0o600."""
        import os
        import stat
        from PySide6.QtCore import QProcess
        from musicstreamer import paths
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        monkeypatch.setattr(paths, "_root_override", str(tmp_path))
        os.makedirs(str(tmp_path), exist_ok=True)

        cookies_path = paths.gbs_cookies_path()
        netscape_bytes = self._GBS_NETSCAPE_VALID.encode("utf-8")
        success_event = b'{"ts":1.0,"category":"Success","detail":"","provider":"gbs"}\n'
        mock_proc = _mock_proc_with_stderr(
            stderr_bytes=success_event,
            stdout_bytes=netscape_bytes,
        )

        dlg = AccountsDialog(fake_repo, toast_callback=lambda t: None)
        qtbot.addWidget(dlg)
        dlg._gbs_login_proc = mock_proc
        dlg._on_gbs_login_finished(0, QProcess.ExitStatus.NormalExit)

        # File written.
        assert os.path.exists(cookies_path)
        # Content equals the fixture verbatim.
        assert Path(cookies_path).read_text(encoding="utf-8") == self._GBS_NETSCAPE_VALID
        # 0o600 permissions (T-40-03 / Phase 999.7).
        perms = stat.S_IMODE(os.stat(cookies_path).st_mode)
        assert perms == 0o600
        # Status flipped to Connected.
        assert dlg._gbs_status_label.text() in {"Connected", "Connected (cookies)"}

    # Anti-pitfall regression guard for RESEARCH line 709 (.strip() footgun).
    def test_gbs_login_finished_does_not_strip_netscape(self, qtbot, fake_repo, tmp_path, monkeypatch):
        """Netscape stdout with leading newlines must be written verbatim — no .strip()."""
        import os
        from PySide6.QtCore import QProcess
        from musicstreamer import paths
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        monkeypatch.setattr(paths, "_root_override", str(tmp_path))
        os.makedirs(str(tmp_path), exist_ok=True)

        # Prefix with leading newlines. _validate_gbs_cookies skips blank lines,
        # so the validator still passes; the WRITE must preserve the leading
        # newlines bytewise.
        netscape_with_lead = "\n\n" + self._GBS_NETSCAPE_VALID
        cookies_path = paths.gbs_cookies_path()
        success_event = b'{"ts":1.0,"category":"Success","detail":"","provider":"gbs"}\n'
        mock_proc = _mock_proc_with_stderr(
            stderr_bytes=success_event,
            stdout_bytes=netscape_with_lead.encode("utf-8"),
        )

        dlg = AccountsDialog(fake_repo, toast_callback=lambda t: None)
        qtbot.addWidget(dlg)
        dlg._gbs_login_proc = mock_proc
        dlg._on_gbs_login_finished(0, QProcess.ExitStatus.NormalExit)

        written = Path(cookies_path).read_text(encoding="utf-8")
        # The two leading newlines are still there.
        assert written.startswith("\n\n")
        # And the body matches.
        assert written == netscape_with_lead

    # Mirror: tests/test_accounts_dialog.py:199-224 (logger event recording)
    def test_gbs_login_finished_logs_provider_gbs_event(self, qtbot, fake_repo, tmp_path, monkeypatch):
        """OAuthLogger.log_event invoked on success with provider='gbs' (T-76-D4 Spoofing guard)."""
        import os
        from PySide6.QtCore import QProcess
        from musicstreamer import paths
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        monkeypatch.setattr(paths, "_root_override", str(tmp_path))
        os.makedirs(str(tmp_path), exist_ok=True)

        netscape_bytes = self._GBS_NETSCAPE_VALID.encode("utf-8")
        success_event = b'{"ts":1.0,"category":"Success","detail":"","provider":"gbs"}\n'
        mock_proc = _mock_proc_with_stderr(
            stderr_bytes=success_event,
            stdout_bytes=netscape_bytes,
        )

        logger_mock = MagicMock()
        dlg = AccountsDialog(fake_repo, toast_callback=lambda t: None)
        qtbot.addWidget(dlg)
        monkeypatch.setattr(dlg, "_get_oauth_logger", lambda: logger_mock)
        dlg._gbs_login_proc = mock_proc
        dlg._on_gbs_login_finished(0, QProcess.ExitStatus.NormalExit)

        # log_event was called.
        assert logger_mock.log_event.called
        event = logger_mock.log_event.call_args[0][0]
        # The synthesized event has provider="gbs" — NOT "twitch" (T-76-D4).
        assert event["provider"] == "gbs"
        assert event["category"] == "Success"

    # Mirror: tests/test_accounts_dialog.py:226-251 (failure-dialog delegation)
    def test_gbs_login_finished_invalidates_bad_netscape(self, qtbot, fake_repo, tmp_path, monkeypatch):
        """exit 0 + garbage stdout fails _validate_gbs_cookies → no file write + failure dialog."""
        import os
        from PySide6.QtCore import QProcess
        from musicstreamer import paths
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        monkeypatch.setattr(paths, "_root_override", str(tmp_path))
        os.makedirs(str(tmp_path), exist_ok=True)
        cookies_path = paths.gbs_cookies_path()

        # Capture _classify_and_show_failure invocations.
        classify_calls: list[dict] = []
        def _record_classify(self, provider, exit_code, output, last_event):
            classify_calls.append({
                "provider": provider,
                "exit_code": exit_code,
                "output": output,
                "last_event": last_event,
            })
        monkeypatch.setattr(
            AccountsDialog, "_classify_and_show_failure", _record_classify,
        )

        # Garbage stdout — fails _validate_gbs_cookies.
        mock_proc = _mock_proc_with_stderr(
            stderr_bytes=b'{"ts":1.0,"category":"Success","detail":"","provider":"gbs"}\n',
            stdout_bytes=b"garbage text not netscape format",
        )

        dlg = AccountsDialog(fake_repo, toast_callback=lambda t: None)
        qtbot.addWidget(dlg)
        dlg._gbs_login_proc = mock_proc
        dlg._on_gbs_login_finished(0, QProcess.ExitStatus.NormalExit)

        # File NOT written (validator rejected).
        assert not os.path.exists(cookies_path)
        # _classify_and_show_failure was invoked with provider="gbs".
        assert len(classify_calls) == 1
        assert classify_calls[0]["provider"] == "gbs"

    # Mirror: tests/test_accounts_dialog.py:226-251 (parametrized failure categories)
    @pytest.mark.parametrize("category", [
        "LoginTimeout",
        "WindowClosedBeforeLogin",
        "InvalidTokenResponse",
        "SubprocessCrash",
    ])
    def test_gbs_login_finished_failure_dialog_for_each_category(
        self, qtbot, fake_repo, tmp_path, monkeypatch, category,
    ):
        """Plan 76-03: each Phase 999.3 category funnels into _classify_and_show_failure with provider='gbs'."""
        import os
        from PySide6.QtCore import QProcess
        from musicstreamer import paths
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        monkeypatch.setattr(paths, "_root_override", str(tmp_path))
        os.makedirs(str(tmp_path), exist_ok=True)

        classify_calls: list[dict] = []
        def _record_classify(self, provider, exit_code, output, last_event):
            classify_calls.append({
                "provider": provider,
                "exit_code": exit_code,
                "output": output,
                "last_event": last_event,
            })
        monkeypatch.setattr(
            AccountsDialog, "_classify_and_show_failure", _record_classify,
        )

        stderr = (
            b'{"ts":1.0,"category":"' + category.encode("ascii") +
            b'","detail":"","provider":"gbs"}\n'
        )
        mock_proc = _mock_proc_with_stderr(
            stderr_bytes=stderr,
            stdout_bytes=b"",
        )

        dlg = AccountsDialog(fake_repo, toast_callback=lambda t: None)
        qtbot.addWidget(dlg)
        dlg._gbs_login_proc = mock_proc
        dlg._on_gbs_login_finished(1, QProcess.ExitStatus.NormalExit)

        assert len(classify_calls) == 1
        call = classify_calls[0]
        assert call["provider"] == "gbs"
        # The category from stderr is preserved in last_event.
        assert call["last_event"] is not None
        assert call["last_event"]["category"] == category

    # Anti-pitfall regression guard — source inspection (belt-and-braces beyond
    # the plan's source-level grep gates). RESEARCH line 709: .strip() on the
    # Netscape stdout would destroy the leading-newline contract.
    def test_gbs_login_finished_no_strip_anti_pitfall(self):
        """Source inspection: _on_gbs_login_finished must NOT .strip() netscape_text."""
        import inspect
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        src = inspect.getsource(AccountsDialog._on_gbs_login_finished)
        # No `.strip()` anywhere on a line that mentions netscape_text.
        for line in src.splitlines():
            if "netscape_text" in line:
                assert ".strip()" not in line, (
                    f"netscape_text must not be .strip()'d (RESEARCH line 709 anti-pitfall) "
                    f"but found in line: {line!r}"
                )

    # Anti-pitfall regression guard — T-76-D4 Spoofing: the synthetic event
    # must NEVER hardcode provider="twitch" inside _on_gbs_login_finished.
    def test_gbs_login_finished_no_provider_twitch_hardcode(self):
        """Source inspection: _on_gbs_login_finished must NOT hardcode provider='twitch'."""
        import inspect
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
        src = inspect.getsource(AccountsDialog._on_gbs_login_finished)
        # No literal "twitch" provider hardcode.
        assert '"provider": "twitch"' not in src, (
            "T-76-D4: _on_gbs_login_finished must not hardcode provider='twitch'"
        )
        assert "'provider': 'twitch'" not in src
        # Positive: at least one "gbs" provider reference appears (success log).
        assert '"provider": "gbs"' in src or "'provider': 'gbs'" in src, (
            "_on_gbs_login_finished should record provider='gbs' on success path"
        )


class TestAccountsDialogProviderAwareFailureDialog:
    """Phase 76 CR-01: _show_failure_dialog title + Retry target are provider-aware.

    Pre-fix: _show_failure_dialog hardcoded the window title "Twitch Connection
    Failed" and the Retry button unconditionally launched _launch_oauth_subprocess
    — so a GBS subprocess failure showed Twitch-branded copy AND the Retry click
    silently routed to the Twitch OAuth helper (wrong provider, wrong window).
    These tests guard the (provider="gbs") branch end-to-end.
    """

    def test_gbs_failure_dialog_title_is_gbs(self, tmp_data_dir, qtbot, monkeypatch, fake_repo):
        """provider="gbs" → window title is "GBS.FM Connection Failed" (not Twitch)."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog

        built: list[QDialog] = []

        def capture_exec(self):
            built.append(self)
            return QDialog.DialogCode.Rejected

        monkeypatch.setattr(QDialog, "exec", capture_exec)

        dlg = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg)
        dlg._show_failure_dialog("gbs", "LoginTimeout", "120s")

        assert len(built) == 1
        assert built[0].windowTitle() == "GBS.FM Connection Failed"

    def test_twitch_failure_dialog_title_unchanged(self, tmp_data_dir, qtbot, monkeypatch, fake_repo):
        """Regression: provider="twitch" still produces the original "Twitch Connection Failed"."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog

        built: list[QDialog] = []

        def capture_exec(self):
            built.append(self)
            return QDialog.DialogCode.Rejected

        monkeypatch.setattr(QDialog, "exec", capture_exec)

        dlg = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg)
        dlg._show_failure_dialog("twitch", "LoginTimeout", "120s")

        assert len(built) == 1
        assert built[0].windowTitle() == "Twitch Connection Failed"

    def test_gbs_failure_retry_launches_gbs_subprocess(
        self, tmp_data_dir, qtbot, monkeypatch, fake_repo,
    ):
        """provider="gbs" + Retry-clicked → _launch_gbs_login_subprocess fires (NOT Twitch)."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog

        # Simulate the Retry click (Accepted).
        monkeypatch.setattr(
            QDialog, "exec",
            lambda self: QDialog.DialogCode.Accepted,
        )

        gbs_launch_calls: list[int] = []
        twitch_launch_calls: list[int] = []

        def fake_gbs_launch(self):
            gbs_launch_calls.append(1)

        def fake_twitch_launch(self):
            twitch_launch_calls.append(1)

        monkeypatch.setattr(
            AccountsDialog, "_launch_gbs_login_subprocess", fake_gbs_launch,
        )
        monkeypatch.setattr(
            AccountsDialog, "_launch_oauth_subprocess", fake_twitch_launch,
        )

        dlg = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg)
        dlg._show_failure_dialog("gbs", "LoginTimeout", "120s")

        assert gbs_launch_calls == [1], "GBS Retry must relaunch the GBS subprocess"
        assert twitch_launch_calls == [], "GBS Retry must NOT launch the Twitch subprocess"

    def test_twitch_failure_retry_launches_twitch_subprocess(
        self, tmp_data_dir, qtbot, monkeypatch, fake_repo,
    ):
        """Regression: provider="twitch" + Retry-clicked still routes to Twitch launcher."""
        from musicstreamer.ui_qt.accounts_dialog import AccountsDialog

        monkeypatch.setattr(
            QDialog, "exec",
            lambda self: QDialog.DialogCode.Accepted,
        )

        gbs_launch_calls: list[int] = []
        twitch_launch_calls: list[int] = []

        def fake_gbs_launch(self):
            gbs_launch_calls.append(1)

        def fake_twitch_launch(self):
            twitch_launch_calls.append(1)

        monkeypatch.setattr(
            AccountsDialog, "_launch_gbs_login_subprocess", fake_gbs_launch,
        )
        monkeypatch.setattr(
            AccountsDialog, "_launch_oauth_subprocess", fake_twitch_launch,
        )

        dlg = AccountsDialog(fake_repo)
        qtbot.addWidget(dlg)
        dlg._show_failure_dialog("twitch", "LoginTimeout", "120s")

        assert twitch_launch_calls == [1]
        assert gbs_launch_calls == []
