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
from typing import Callable

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
from musicstreamer.subprocess_utils import _make_oauth_launch_args

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

    def __init__(
        self,
        repo,
        toast_callback: Callable[[str], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._repo = repo  # Phase 48 D-04: required for AA view/clear
        # Phase 53 D-06: forwarded toast surface for cookie-import success messages.
        # Defaulted to no-op so existing positional AccountsDialog(fake_repo) sites
        # (24 in tests/test_accounts_dialog.py) keep working without churn.
        self._toast_callback = toast_callback or (lambda _msg: None)
        self.setWindowTitle("Accounts")
        self.setMinimumWidth(360)

        self._oauth_proc: QProcess | None = None
        self._gbs_login_proc: QProcess | None = None  # Phase 76 D-09: GBS login subprocess
        self._oauth_logger: OAuthLogger | None = None  # Phase 999.3 D-11: lazy-init

        # Shared font for all three group status labels.
        status_font = QFont()
        status_font.setPointSize(10)

        # Phase 53: YouTube group box (D-01, D-09 — first / topmost group).
        self._youtube_box = QGroupBox("YouTube", self)
        youtube_layout = QVBoxLayout(self._youtube_box)

        self._youtube_status_label = QLabel(self)
        self._youtube_status_label.setTextFormat(Qt.TextFormat.PlainText)  # T-40-04
        self._youtube_status_label.setFont(status_font)
        youtube_layout.addWidget(self._youtube_status_label)

        self._youtube_action_btn = QPushButton(self)
        self._youtube_action_btn.clicked.connect(self._on_youtube_action_clicked)  # QA-05
        youtube_layout.addWidget(self._youtube_action_btn)

        # === Phase 60 D-04c: GBS.FM group (between YouTube and Twitch) ===
        self._gbs_box = QGroupBox("GBS.FM", self)
        gbs_layout = QVBoxLayout(self._gbs_box)

        self._gbs_status_label = QLabel(self)
        self._gbs_status_label.setTextFormat(Qt.TextFormat.PlainText)  # T-40-04
        self._gbs_status_label.setFont(status_font)
        gbs_layout.addWidget(self._gbs_status_label)

        self._gbs_action_btn = QPushButton(self)
        self._gbs_action_btn.clicked.connect(self._on_gbs_action_clicked)  # QA-05
        gbs_layout.addWidget(self._gbs_action_btn)

        # Phase 76 D-14: secondary path — preserve File/Paste tab access
        # in CookieImportDialog. Hidden when connected (see _update_status).
        self._gbs_import_btn = QPushButton("Import cookies file…", self)
        self._gbs_import_btn.clicked.connect(self._on_gbs_import_clicked)  # QA-05
        gbs_layout.addWidget(self._gbs_import_btn)

        # Twitch group box (existing — unchanged shape; status_font now shared)
        twitch_box = QGroupBox("Twitch", self)
        twitch_layout = QVBoxLayout(twitch_box)

        self._status_label = QLabel(self)
        self._status_label.setTextFormat(Qt.TextFormat.PlainText)  # T-40-04: no rich-text injection
        self._status_label.setFont(status_font)
        twitch_layout.addWidget(self._status_label)

        self._action_btn = QPushButton(self)
        self._action_btn.clicked.connect(self._on_action_clicked)
        twitch_layout.addWidget(self._action_btn)

        # AudioAddict group box (Phase 48 D-05 — unchanged)
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
        layout.addWidget(self._youtube_box)
        layout.addWidget(self._gbs_box)         # Phase 60 D-04c
        layout.addWidget(twitch_box)
        layout.addWidget(aa_box)
        layout.addWidget(btn_box)

        self._update_status()

    # ------------------------------------------------------------------
    # Lifecycle — subprocess cleanup (Phase 76 WR-02)
    # ------------------------------------------------------------------

    def closeEvent(self, event):  # noqa: N802 (Qt-mandated camelCase)
        """Terminate any still-running OAuth/GBS-login subprocess on dialog close.

        Phase 76 WR-02: Qt parent-ownership reaps the QProcess Python object
        when AccountsDialog is destroyed, but the underlying OS process
        (a Python interpreter hosting QtWebEngine) keeps running detached
        until its own 120s watchdog fires or the QWebEngine window is closed
        manually. Closing AccountsDialog mid-login therefore left an orphan
        subprocess + QWebEngine window for up to two minutes — and a second
        Connect click before the orphan timed out would spawn a concurrent
        QWebEngine window.

        Terminate-then-wait-then-kill is the standard Qt cleanup pattern;
        each step is wrapped in try/except so any single-subprocess failure
        cannot prevent the other from being cleaned up or block the dialog
        from closing.
        """
        for proc_attr in ("_oauth_proc", "_gbs_login_proc"):
            proc = getattr(self, proc_attr, None)
            if proc is None:
                continue
            try:
                proc.terminate()
                # waitForFinished returns False on timeout — fall through to kill.
                if not proc.waitForFinished(2000):
                    proc.kill()
            except Exception:
                # Defensive: any QProcess-side failure (already-dead, C++ object
                # gone, etc.) must not block close — the goal is best-effort.
                pass
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def _is_connected(self) -> bool:
        return os.path.exists(paths.twitch_token_path())

    def _is_youtube_connected(self) -> bool:
        """Phase 53 D-02: True when paths.cookies_path() exists on disk."""
        return os.path.exists(paths.cookies_path())

    def _is_aa_key_saved(self) -> bool:
        """Phase 48 D-07: True when ``audioaddict_listen_key`` is non-empty."""
        return bool(self._repo.get_setting("audioaddict_listen_key", ""))

    def _is_gbs_connected(self) -> bool:
        """Phase 60 D-04 ladder #3: True when paths.gbs_cookies_path() exists on disk."""
        return os.path.exists(paths.gbs_cookies_path())

    def _update_status(self) -> None:
        # Phase 53 D-02 / D-07 / D-08: YouTube status (top of method to mirror D-09 order).
        if self._is_youtube_connected():
            self._youtube_status_label.setText("Connected")
            self._youtube_action_btn.setText("Disconnect")
        else:
            self._youtube_status_label.setText("Not connected")
            self._youtube_action_btn.setText("Import YouTube Cookies...")

        # Phase 60 D-04c + Phase 76 D-03/D-14: GBS.FM status (2-state, with
        # secondary import-cookies button hidden when connected).
        # D-03 collapsed scope: 2-state only (no token half).
        # Phase 76 WR-03: mirror Twitch's "Connecting..." gate while subprocess
        # is in flight, so the user can't fire a second concurrent QWebEngine
        # window. The early-return in _launch_gbs_login_subprocess is the
        # belt-and-braces safety net behind this UX gate.
        if self._gbs_login_proc is not None:
            self._gbs_status_label.setText("Connecting...")
            self._gbs_action_btn.setEnabled(False)
            self._gbs_import_btn.setVisible(False)
        elif self._is_gbs_connected():
            self._gbs_status_label.setText("Connected")
            self._gbs_action_btn.setText("Disconnect")
            self._gbs_action_btn.setEnabled(True)
            self._gbs_import_btn.setVisible(False)
        else:
            self._gbs_status_label.setText("Not connected")
            self._gbs_action_btn.setText("Connect to GBS.FM…")
            self._gbs_action_btn.setEnabled(True)
            self._gbs_import_btn.setVisible(True)

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

    def _on_youtube_action_clicked(self) -> None:
        """Phase 53 D-03 / D-05: Disconnect (delete cookies.txt) or Import (launch CookieImportDialog).

        Connected state → confirm + os.remove with try/except FileNotFoundError
        (Phase 999.7 auto-clear race tolerance — T-53-01).

        Not connected state → launch CookieImportDialog as a child dialog with
        the forwarded toast_callback; refresh status unconditionally after exec
        returns (idempotent — D-discretion recommendation).

        T-53-02: handler is strictly limited to paths.cookies_path() removal +
        _update_status(); does NOT touch twitch_token_path or audioaddict_listen_key.
        """
        if self._is_youtube_connected():
            answer = QMessageBox.question(
                self,
                "Disconnect YouTube?",
                "This will delete your saved YouTube cookies. "
                "You will need to re-import to play cookie-protected YouTube streams.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                try:
                    os.remove(paths.cookies_path())
                except FileNotFoundError:
                    # Race with Phase 999.7 auto-clear — file already gone.
                    pass
                self._update_status()
        else:
            # In-slot import per Phase 53 D-12 (main_window.py drops the import).
            from musicstreamer.ui_qt.cookie_import_dialog import CookieImportDialog
            dlg = CookieImportDialog(self._toast_callback, parent=self)
            dlg.exec()
            # D-discretion: call _update_status unconditionally — idempotent.
            self._update_status()

    def _on_gbs_action_clicked(self) -> None:
        """Phase 60 D-04c + Phase 76 D-03/D-09: Connect (launch subprocess) or Disconnect."""
        if self._is_gbs_connected():
            answer = QMessageBox.question(
                self, "Disconnect GBS.FM?",
                "This will delete your saved GBS.FM cookies. "
                "You will need to reconnect to vote, view the active "
                "playlist, or submit songs.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                try:
                    os.remove(paths.gbs_cookies_path())
                except OSError:
                    # HIGH 2 fix: tolerate broader OSError tree
                    # (FileNotFoundError, PermissionError, IsADirectoryError, ...).
                    # Status update fires regardless so UI stays consistent.
                    pass
                self._update_status()
        else:
            # Phase 76 D-09: launch oauth_helper --mode gbs subprocess.
            self._launch_gbs_login_subprocess()

    def _launch_oauth_subprocess(self) -> None:
        """Phase 999.3 D-09: extracted helper so Retry can reuse the launch path."""
        self._oauth_proc = QProcess(self)
        self._oauth_proc.finished.connect(self._on_oauth_finished)
        # T-40-05 / Phase 88.2 D-01: _make_oauth_launch_args owns the
        # sys.executable contract (no PATH injection, never shell=True, mode
        # is a hardcoded literal). Frozen branch uses --oauth-helper dispatch;
        # non-frozen uses the standard -m module form.
        program, args = _make_oauth_launch_args("twitch")
        self._oauth_proc.start(program, args)
        self._update_status()

    def _launch_gbs_login_subprocess(self) -> None:
        """Phase 76 D-09: launch oauth_helper --mode gbs.

        Phase 76 WR-03: re-entrancy guard. If a previous launch is still
        in flight, ignore the click — without this guard a second click
        would overwrite ``self._gbs_login_proc`` with a fresh QProcess
        and drop the reference to the first, leaking the first subprocess
        and routing its eventual ``finished`` signal to the second
        process's stdout/stderr (wrong data).
        """
        if self._gbs_login_proc is not None:
            return  # WR-03: already running — ignore re-click
        self._gbs_login_proc = QProcess(self)
        self._gbs_login_proc.finished.connect(self._on_gbs_login_finished)  # QA-05
        # T-40-05 / Phase 88.2 D-01: _make_oauth_launch_args owns the
        # sys.executable contract (no PATH injection, never shell=True, mode
        # is a hardcoded literal). Frozen branch uses --oauth-helper dispatch;
        # non-frozen uses the standard -m module form.
        program, args = _make_oauth_launch_args("gbs")
        self._gbs_login_proc.start(program, args)
        self._update_status()

    def _on_gbs_import_clicked(self) -> None:
        """Phase 76 D-14: secondary path — open the existing File/Paste tabs."""
        from musicstreamer.ui_qt.cookie_import_dialog import CookieImportDialog
        from musicstreamer import gbs_api
        dlg = CookieImportDialog(
            self._toast_callback,
            parent=self,
            target_label="GBS.FM",
            cookies_path=paths.gbs_cookies_path,
            validator=gbs_api._validate_gbs_cookies,
            oauth_mode=None,   # Phase 60 v1: file + paste tabs only
        )
        dlg.exec()
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

    @staticmethod
    def _parse_oauth_stderr(proc: QProcess | None) -> dict | None:
        """Phase 76 IN-03: extracted shared D-12 stderr-parse helper.

        Both _on_oauth_finished and _on_gbs_login_finished previously inlined
        an identical 23-line block to read the subprocess's stderr and keep
        the last well-formed JSON event (T-999.3-05: malformed lines are
        skipped without eval). Factoring out the shared body means any
        future evolution of the stderr-event contract (new categories,
        schema changes, malformed-JSON tweaks) touches one location instead
        of two, with no test-surface change required.

        Returns the last dict that parsed AND carried a "category" key, or
        None if no such event was emitted.
        """
        if proc is None:
            return None
        try:
            stderr_bytes = proc.readAllStandardError().data()
        except Exception:
            stderr_bytes = b""
        try:
            stderr_text = stderr_bytes.decode("utf-8", errors="replace")
        except Exception:
            stderr_text = ""
        last_event: dict | None = None
        for raw_line in stderr_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                # T-999.3-05: malformed line → skip, no eval/no code path.
                continue
            if isinstance(obj, dict) and "category" in obj:
                last_event = obj
        return last_event

    def _on_oauth_finished(
        self,
        exit_code: int,
        exit_status: QProcess.ExitStatus,
    ) -> None:
        proc = self._oauth_proc
        self._oauth_proc = None

        # Phase 999.3 D-12 / Phase 76 IN-03: shared stderr parser.
        last_event = self._parse_oauth_stderr(proc)

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
        # Phase 76 Task 1 (PLAN 76-03): delegate to shared helper.
        # Source: accounts_dialog.py:424-458 extracted to
        # _classify_and_show_failure(provider, exit_code, output, last_event).
        # Mirrors PATTERNS.md File 2 Summary Table row 9 + RESEARCH
        # §_on_gbs_login_finished lines 741-746.
        self._classify_and_show_failure(
            provider="twitch",
            exit_code=exit_code,
            output=token,
            last_event=last_event,
        )

    def _on_gbs_login_finished(
        self,
        exit_code: int,
        exit_status: QProcess.ExitStatus,
    ) -> None:
        """Mirror _on_oauth_finished but for the Netscape-stdout contract."""
        proc = self._gbs_login_proc
        self._gbs_login_proc = None

        # Phase 999.3 D-12 / Phase 76 IN-03: shared stderr parser.
        # Previously this inlined the 23-line parse block verbatim per
        # Plan 76-03 Task 1's "minimize regression risk" framing; the
        # IN-03 refactor extracts it so any future D-12 evolution lands
        # in one place.
        last_event = self._parse_oauth_stderr(proc)

        # Read stdout (Netscape cookie dump on success).
        # CRITICAL: do NOT .strip() — Netscape format preserves leading newlines
        # (RESEARCH line 709 anti-pitfall).
        netscape_text: str = ""
        if proc is not None:
            try:
                netscape_text = proc.readAllStandardOutput().data().decode(
                    "utf-8", errors="replace"
                )
            except Exception:
                netscape_text = ""

        # Deferred import to avoid module-load cost (matches Phase 60 deferred
        # pattern in pre-Phase-76 _on_gbs_action_clicked).
        from musicstreamer.gbs_api import _validate_gbs_cookies

        # ---- Success path --------------------------------------------
        success_category = last_event is None or last_event.get("category") == "Success"
        if (
            exit_code == 0
            and netscape_text
            and success_category
            and _validate_gbs_cookies(netscape_text)
        ):
            cookies_path = paths.gbs_cookies_path()
            os.makedirs(os.path.dirname(cookies_path), exist_ok=True)
            with open(cookies_path, "w", encoding="utf-8") as fh:
                fh.write(netscape_text)
            os.chmod(cookies_path, 0o600)  # T-40-03 / Phase 999.7 — restrict immediately
            logger = self._get_oauth_logger()
            if logger is not None:
                try:
                    logger.log_event({
                        "ts": (last_event or {}).get("ts", 0.0),
                        "category": "Success",
                        "detail": "",
                        "provider": "gbs",
                    })
                except Exception:
                    pass
            self._toast_callback("GBS.FM logged in.")
            self._update_status()
            return

        # ---- Failure path --------------------------------------------
        # Delegate to the shared helper extracted in Task 1. Passing
        # netscape_text as ``output`` means the existing classification
        # precedence (empty output → InvalidTokenResponse empty_stdout)
        # works unchanged. Validator-rejection (garbage Netscape) also
        # falls through here because the success guard returned False
        # without writing; the helper then produces InvalidTokenResponse
        # on exit_code==0 / SubprocessCrash on non-zero.
        self._classify_and_show_failure(
            provider="gbs",
            exit_code=exit_code,
            output=netscape_text,
            last_event=last_event,
        )

    # ------------------------------------------------------------------
    # Failure dialog (Phase 999.3 D-08, D-09)
    # ------------------------------------------------------------------

    def _classify_and_show_failure(
        self,
        provider: str,
        exit_code: int,
        output: str,
        last_event: dict | None,
    ) -> None:
        """Phase 76 Task 1: shared failure-classification helper.

        Extracted from _on_oauth_finished (accounts_dialog.py:424-458 pre-Phase-76)
        so both Twitch (_on_oauth_finished) and GBS (_on_gbs_login_finished) reuse
        identical Phase 999.3 category-dialog plumbing.

        Mirrors PATTERNS.md File 2 Summary Table row 9 + RESEARCH
        §_on_gbs_login_finished lines 741-746 verbatim. The ``provider`` parameter
        flows into the synthetic events (T-76-D4 mitigation — never hardcoded).
        """
        # Defensive classification precedence (preserved verbatim from the
        # pre-Phase-76 _on_oauth_finished body — see PATTERNS.md Excerpt 2D
        # lines 650-657):
        # 1. exit_code==0 with empty output → InvalidTokenResponse empty_stdout
        #    (takes precedence over missing event; subprocess exited cleanly
        #    but produced no token — semantically an invalid response, not a crash)
        # 2. No parseable event at all → SubprocessCrash exit=<code>
        # 3. Event present → use it as-is.
        if exit_code == 0 and not output:
            last_event = {
                "ts": (last_event or {}).get("ts", 0.0),
                "category": "InvalidTokenResponse",
                "detail": "empty_stdout",
                "provider": provider,
            }
        elif last_event is None:
            last_event = {
                "ts": 0.0,
                "category": "SubprocessCrash",
                "detail": f"exit={exit_code}",
                "provider": provider,
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
        self._show_failure_dialog(provider, category, detail)

    # Phase 76 CR-01 fix: provider → user-facing prefix in the failure-dialog title.
    # Unknown providers fall back to the raw provider string so future additions
    # (e.g. "google") don't silently render "twitch" / "GBS.FM" — they render
    # `"google Connection Failed"`, which is visibly wrong rather than misleading.
    _PROVIDER_TITLES = {"twitch": "Twitch", "gbs": "GBS.FM"}

    def _show_failure_dialog(self, provider: str, category: str, detail: str) -> None:
        """Category + detail failure dialog with inline Retry.

        Phase 76 CR-01: ``provider`` parameter drives BOTH the window title
        ("Twitch Connection Failed" vs "GBS.FM Connection Failed") AND the
        Retry-button relaunch target — a GBS failure now correctly relaunches
        ``_launch_gbs_login_subprocess`` instead of dragging the user into the
        Twitch OAuth helper.

        T-40-04: all labels use PlainText format — user-visible detail
        strings cannot inject HTML/links.
        """
        label = _CATEGORY_LABELS.get(category, "Unknown error")
        provider_title = self._PROVIDER_TITLES.get(provider, provider)
        dlg = QDialog(self)
        dlg.setWindowTitle(f"{provider_title} Connection Failed")
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
        # Phase 76 CR-01: route the retry to the correct provider subprocess —
        # GBS failures must NOT silently relaunch the Twitch OAuth helper.
        if dlg.exec() == QDialog.DialogCode.Accepted:
            if provider == "gbs":
                self._launch_gbs_login_subprocess()
            else:
                self._launch_oauth_subprocess()
