"""AccountsDialog — Twitch OAuth connection management.

UI-08: Shows Connected / Not connected status based on twitch-token.txt,
       launches oauth_helper.py subprocess via QProcess to capture token,
       and handles Disconnect with confirmation prompt.
"""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import QProcess, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from musicstreamer import constants, paths


class AccountsDialog(QDialog):
    """Dialog for managing third-party account connections (Twitch OAuth).

    D-01: Shows connection status + Connect/Disconnect action button.
    D-02: Connect launches oauth_helper.py subprocess via QProcess.
    D-03: Disconnect deletes token file after user confirmation.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Accounts")
        self.setMinimumWidth(360)

        self._oauth_proc: QProcess | None = None

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

        # Close button
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        btn_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        layout.addWidget(twitch_box)
        layout.addWidget(btn_box)

        self._update_status()

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def _is_connected(self) -> bool:
        return os.path.exists(paths.twitch_token_path())

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
            self._oauth_proc = QProcess(self)
            self._oauth_proc.finished.connect(self._on_oauth_finished)
            # T-40-05: use sys.executable — no PATH injection; never shell=True
            self._oauth_proc.start(
                sys.executable,
                ["-m", "musicstreamer.oauth_helper", "--mode", "twitch"],
            )
            self._update_status()

    # ------------------------------------------------------------------
    # OAuth subprocess result
    # ------------------------------------------------------------------

    def _on_oauth_finished(
        self,
        exit_code: int,
        exit_status: QProcess.ExitStatus,
    ) -> None:
        if exit_code == 0:
            token = (
                self._oauth_proc.readAllStandardOutput()  # type: ignore[union-attr]
                .data()
                .decode()
                .strip()
            )
            if token:
                token_path = paths.twitch_token_path()
                os.makedirs(os.path.dirname(token_path), exist_ok=True)
                with open(token_path, "w") as fh:
                    fh.write(token)
                os.chmod(token_path, 0o600)  # T-40-03: restrict permissions immediately
        else:
            QMessageBox.warning(
                self,
                "Twitch Connection Failed",
                "Twitch connection failed. Try again.",
            )

        self._oauth_proc = None
        self._update_status()
