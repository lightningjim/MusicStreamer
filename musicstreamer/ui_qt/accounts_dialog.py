"""AccountsDialog — third-party account connection management.

UI-08: Shows Connected / Not connected status based on twitch-token.txt,
       launches oauth_helper.py subprocess via QProcess to capture token,
       and handles Disconnect with confirmation prompt.

Phase 48 (D-04/D-05/D-06/D-07): Adds an AudioAddict view/clear group
       alongside the Twitch group. The AA group reflects whether a listen
       key is persisted in the settings table and lets the user clear it
       with a Yes/No confirmation. AccountsDialog never writes a new AA key
       — editing lives in ImportDialog on successful fetch (plan 48-02).

Phase 999.3 (D-08/D-09/D-11/D-12): Replaces the generic "Try again"
       QMessageBox with a category+detail failure QDialog that offers an
       inline Retry button. Parses the structured JSON-line stderr events
       emitted by oauth_helper.py and appends them to a persistent rotating
       log at paths.oauth_log_path().
"""
from __future__ import annotations

import json
import os
import sys

from PySide6.QtCore import QProcess, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from musicstreamer import constants, paths
from musicstreamer.oauth_log import OAuthLogger

# Phase 999.3 D-08: category → user-facing label.
# Keep in sync with oauth_helper._emit_event categories (post-pivot contract:
# cookie-harvest flow from twitch.tv — no OAuth-redirect categories).
_CATEGORY_LABELS = {
    "InvalidTokenResponse":    "Login did not return a valid token",
    "LoginTimeout":            "Login took too long (2 min)",
    "WindowClosedBeforeLogin": "Login window was closed before completing",
    "SubprocessCrash":         "Login helper crashed unexpectedly",
}


class AccountsDialog(QDialog):
    """Dialog for managing third-party account connections.

    D-01: Shows connection status + Connect/Disconnect action button (Twitch).
    D-02: Connect launches oauth_helper.py subprocess via QProcess.
    D-03: Disconnect deletes token file after user confirmation.

    Phase 48 D-04/D-05/D-06/D-07: Adds an AudioAddict view/clear group.
    Status label reflects whether ``audioaddict_listen_key`` is saved in
    the settings table. Clear button prompts Yes/No confirm; Yes clears
    the setting, No is a no-op. Dialog never writes a new AA key.

    Phase 999.3 D-08..D-12: Category-aware failure UX + persistent log.
    """

    def __init__(self, repo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._repo = repo  # Phase 48 D-04: required for AA view/clear
        self.setWindowTitle("Accounts")
        self.setMinimumWidth(360)

        self._oauth_proc: QProcess | None = None
        self._oauth_logger: OAuthLogger | None = None  # Phase 999.3 D-11: lazy-init

        # Twitch group box
        twitch_box = QGroupBox("Twitch", self)
        twitch_layout = QVBoxLayout(twitch_box)

        self._status_label = QLabel(self)
        self._status_label.setTextFormat(Qt.TextFormat.PlainText)  # T-40-04: no rich-text injection
        status_font = QFont()
        status_font.setPointSize(10)
        self._status_label.setFont(status_font)
        twitch_layout.addWidget(self._status_label)

        self._action_btn = QPushButton(self)
        self._action_btn.clicked.connect(self._on_action_clicked)
        twitch_layout.addWidget(self._action_btn)

        # AudioAddict group box (Phase 48 D-05)
        aa_box = QGroupBox("AudioAddict", self)
        aa_layout = QVBoxLayout(aa_box)

        self._aa_status_label = QLabel(self)
        self._aa_status_label.setTextFormat(Qt.TextFormat.PlainText)  # T-48-04: no rich-text injection
        self._aa_status_label.setFont(status_font)
        aa_layout.addWidget(self._aa_status_label)

        self._aa_clear_btn = QPushButton(self)
        self._aa_clear_btn.clicked.connect(self._on_aa_clear_clicked)
        aa_layout.addWidget(self._aa_clear_btn)

        # Close button
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        btn_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        layout.addWidget(twitch_box)
        layout.addWidget(aa_box)
        layout.addWidget(btn_box)

        self._update_status()

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def _is_connected(self) -> bool:
        return os.path.exists(paths.twitch_token_path())

    def _is_aa_key_saved(self) -> bool:
        """Phase 48 D-07: True when ``audioaddict_listen_key`` is non-empty."""
        return bool(self._repo.get_setting("audioaddict_listen_key", ""))

    def _update_status(self) -> None:
        if self._oauth_proc is not None:
            self._status_label.setText("Connecting...")
            self._action_btn.setEnabled(False)
        elif self._is_connected():
            self._status_label.setText("Connected")
            self._action_btn.setText("Disconnect")
            self._action_btn.setEnabled(True)
        else:
            self._status_label.setText("Not connected")
            self._action_btn.setText("Connect Twitch")
            self._action_btn.setEnabled(True)

        # AA group status (Phase 48 D-07)
        if self._is_aa_key_saved():
            self._aa_status_label.setText("Saved")
            self._aa_clear_btn.setText("Clear saved key")
            self._aa_clear_btn.setEnabled(True)
        else:
            self._aa_status_label.setText("Not saved")
            self._aa_clear_btn.setText("No key saved")
            self._aa_clear_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # OAuth logger (lazy)
    # ------------------------------------------------------------------

    def _get_oauth_logger(self) -> OAuthLogger | None:
        """Phase 999.3 D-11: lazy-init OAuthLogger.

        Returns None on failure — logging is supplementary and MUST NOT
        block the user from seeing the failure dialog.
        """
        if self._oauth_logger is not None:
            return self._oauth_logger
        try:
            log_path = paths.oauth_log_path()
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            self._oauth_logger = OAuthLogger(log_path)
        except OSError:
            return None
        except Exception:
            # Defensive: any logger-init failure is swallowed (D-11 accept disposition).
            return None
        return self._oauth_logger

    # ------------------------------------------------------------------
    # Action slot
    # ------------------------------------------------------------------

    def _on_action_clicked(self) -> None:
        if self._is_connected():
            # D-03: confirm before disconnect
            answer = QMessageBox.question(
                self,
                "Disconnect Twitch?",
                "This will delete your saved Twitch token. "
                "You will need to reconnect to stream Twitch channels.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                constants.clear_twitch_token()
                self._update_status()
        else:
            # D-02: launch OAuth subprocess
            self._launch_oauth_subprocess()

    def _launch_oauth_subprocess(self) -> None:
        """Phase 999.3 D-09: extracted helper so Retry can reuse the launch path."""
        self._oauth_proc = QProcess(self)
        self._oauth_proc.finished.connect(self._on_oauth_finished)
        # T-40-05: use sys.executable — no PATH injection; never shell=True
        self._oauth_proc.start(
            sys.executable,
            ["-m", "musicstreamer.oauth_helper", "--mode", "twitch"],
        )
        self._update_status()

    def _on_aa_clear_clicked(self) -> None:
        """Phase 48 D-06: confirm then clear the saved AudioAddict listen key."""
        answer = QMessageBox.question(
            self,
            "Clear AudioAddict key?",
            "This will delete your saved AudioAddict listen key. "
            "You will need to re-enter it from Import Stations.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._repo.set_setting("audioaddict_listen_key", "")
            self._update_status()

    # ------------------------------------------------------------------
    # OAuth subprocess result
    # ------------------------------------------------------------------

    def _on_oauth_finished(
        self,
        exit_code: int,
        exit_status: QProcess.ExitStatus,
    ) -> None:
        proc = self._oauth_proc
        self._oauth_proc = None

        # Phase 999.3 D-12: parse stderr line-by-line, keep last valid event.
        last_event: dict | None = None
        if proc is not None:
            try:
                stderr_bytes = proc.readAllStandardError().data()
            except Exception:
                stderr_bytes = b""
            try:
                stderr_text = stderr_bytes.decode("utf-8", errors="replace")
            except Exception:
                stderr_text = ""
            for line in stderr_text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    # T-999.3-05: malformed line → skip, no eval/no code path.
                    continue
                if isinstance(obj, dict) and "category" in obj:
                    last_event = obj

        # Read stdout (token on success)
        token = ""
        if proc is not None:
            try:
                token = (
                    proc.readAllStandardOutput().data().decode("utf-8", errors="replace").strip()
                )
            except Exception:
                token = ""

        # ---- Success path --------------------------------------------
        success_category = last_event is None or last_event.get("category") == "Success"
        if exit_code == 0 and token and success_category:
            token_path = paths.twitch_token_path()
            os.makedirs(os.path.dirname(token_path), exist_ok=True)
            with open(token_path, "w") as fh:
                fh.write(token)
            os.chmod(token_path, 0o600)  # T-40-03: restrict permissions immediately
            logger = self._get_oauth_logger()
            if logger is not None:
                try:
                    logger.log_event({
                        "ts": (last_event or {}).get("ts", 0.0),
                        "category": "Success",
                        "detail": "",
                        "provider": "twitch",
                    })
                except Exception:
                    pass
            self._update_status()
            return

        # ---- Failure path --------------------------------------------
        # Defensive classification precedence:
        # 1. exit_code==0 with empty token → InvalidTokenResponse empty_stdout
        #    (takes precedence over missing event; subprocess exited cleanly
        #    but produced no token — semantically an invalid response, not a crash)
        # 2. No parseable event at all → SubprocessCrash exit=<code>
        # 3. Event present and exit_code==0 but empty token → upgrade to
        #    InvalidTokenResponse empty_stdout
        if exit_code == 0 and not token:
            last_event = {
                "ts": (last_event or {}).get("ts", 0.0),
                "category": "InvalidTokenResponse",
                "detail": "empty_stdout",
                "provider": "twitch",
            }
        elif last_event is None:
            last_event = {
                "ts": 0.0,
                "category": "SubprocessCrash",
                "detail": f"exit={exit_code}",
                "provider": "twitch",
            }

        logger = self._get_oauth_logger()
        if logger is not None:
            try:
                logger.log_event(last_event)
            except Exception:
                pass

        self._update_status()
        # T-999.3-05: coerce category/detail to str before UI consumption.
        category = str(last_event.get("category", "SubprocessCrash"))
        detail = str(last_event.get("detail", ""))
        self._show_failure_dialog(category, detail)

    # ------------------------------------------------------------------
    # Failure dialog (Phase 999.3 D-08, D-09)
    # ------------------------------------------------------------------

    def _show_failure_dialog(self, category: str, detail: str) -> None:
        """Category + detail failure dialog with inline Retry.

        T-40-04: all labels use PlainText format — user-visible detail
        strings cannot inject HTML/links.
        """
        label = _CATEGORY_LABELS.get(category, "Unknown error")
        dlg = QDialog(self)
        dlg.setWindowTitle("Twitch Connection Failed")
        dlg.setMinimumWidth(380)

        title_lbl = QLabel(label, dlg)
        title_lbl.setTextFormat(Qt.TextFormat.PlainText)  # T-40-04
        title_lbl.setWordWrap(True)
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title_lbl.setFont(title_font)

        detail_text = detail if detail else "(no details provided)"
        detail_lbl = QLabel(detail_text, dlg)
        detail_lbl.setTextFormat(Qt.TextFormat.PlainText)  # T-40-04
        detail_lbl.setWordWrap(True)
        detail_font = QFont()
        detail_font.setPointSize(9)
        detail_lbl.setFont(detail_font)

        retry_btn = QPushButton("Retry", dlg)
        close_btn = QPushButton("Close", dlg)
        close_btn.clicked.connect(dlg.reject)
        retry_btn.clicked.connect(dlg.accept)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        btn_row.addWidget(retry_btn)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.addWidget(title_lbl)
        layout.addWidget(detail_lbl)
        layout.addLayout(btn_row)

        # D-09: Retry (Accepted) relaunches inline without closing AccountsDialog.
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._launch_oauth_subprocess()
