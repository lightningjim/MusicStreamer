"""GBS.FM session-expiry shared re-login handler.

Phase 87.1 GBS-AUTH-EXP-02: provides a single, reusable seam that catches
GBS session expiry signals from any consumer (active-playlist poller,
marquee worker, Phase 87b zero-token add) and launches exactly ONE
``oauth_helper --mode gbs`` subprocess via single-flight de-duplication.

Design decision (Claude's discretion, documented per CONTEXT.md):
    Direct ``oauth_helper --mode gbs`` launch with inline stderr-parse
    duplication rather than opening AccountsDialog or importing it.
    This avoids coupling to the Phase 88.2/88.3-hardened accounts_dialog,
    keeps the handler importable without pulling in the full AccountsDialog
    dependency tree, and mirrors the exact QProcess wiring shape already
    proven in accounts_dialog._launch_gbs_login_subprocess (lines 398-421)
    and accounts_dialog._on_gbs_login_finished (lines 552-625).

    The stderr-parse logic (~15 lines, stdlib only: json + string ops) is
    duplicated inline in _on_finished per assumption A4 from RESEARCH.md.
    Extraction to subprocess_utils._parse_oauth_stderr is deferred.

Signals:
    relogin_succeeded: Emitted after the subprocess writes valid Netscape
        cookies to gbs_cookies_path() with 0o600 permissions.
    relogin_failed(str): Emitted if the subprocess exits non-zero, is
        cancelled, or fails to start. Payload is a short human-readable
        reason string suitable for optional UI surface.

Thread safety:
    This QObject MUST live on the main thread. All public methods
    (notify_expiry_detected) are main-thread-only. Cross-thread callers
    (e.g. GbsMarqueeWorker) must emit a Signal connected with
    Qt.QueuedConnection so the call crosses to the main event loop.
"""
from __future__ import annotations

import json
import logging

from PySide6.QtCore import QObject, QProcess, Signal

_log = logging.getLogger(__name__)


class GbsReloginHandler(QObject):
    """Shared GBS session expiry → re-login handler.

    Lives on the main thread. Provides single-flight de-duplication so
    concurrent expiry signals from multiple workers (playlist poller,
    marquee worker, Phase 87b zero-token add) trigger only one
    oauth_helper subprocess.

    Usage::

        handler = GbsReloginHandler(parent=self)
        handler.relogin_succeeded.connect(self._on_gbs_relogin_succeeded)
        handler.relogin_failed.connect(self._on_gbs_relogin_failed)

        # From any consumer that caught GbsAuthExpiredError:
        handler.notify_expiry_detected()

    """

    relogin_succeeded = Signal()
    relogin_failed = Signal(str)  # reason — for optional UI surface

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._login_proc: QProcess | None = None  # WR-03 single-flight guard

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def notify_expiry_detected(self) -> None:
        """Called by any consumer that detects GbsAuthExpiredError.

        No-op if a login subprocess is already in flight (single-flight
        de-dup — WR-03 / T-87.1-01 / Pitfall 1).
        Safe to call from the main thread only.
        """
        if self._login_proc is not None:
            return  # WR-03: already in flight — ignore concurrent notification
        self._launch()

    # ------------------------------------------------------------------
    # Private: subprocess lifecycle
    # ------------------------------------------------------------------

    def _launch(self) -> None:
        """Construct and start the oauth_helper QProcess.

        WR-03: re-entrancy guard is checked in notify_expiry_detected
        before this method is called — guard is therefore always None here.
        """
        self._login_proc = QProcess(self)
        # QA-05: bound-method connections only — no self-capturing lambdas
        self._login_proc.finished.connect(self._on_finished)
        # Phase 88.2 D-02/D-03: errorOccurred fires INSTEAD of finished on
        # FailedToStart; wire it so the guard is never permanently stuck non-None
        # (Pitfall 2 / T-87.1-02).
        self._login_proc.errorOccurred.connect(self._on_error)
        from musicstreamer.subprocess_utils import _make_oauth_launch_args
        program, args = _make_oauth_launch_args("gbs")
        self._login_proc.start(program, args)

    def _on_finished(
        self, exit_code: int, exit_status: QProcess.ExitStatus
    ) -> None:
        """Handle subprocess exit — validate output and emit appropriate signal.

        Mirror of accounts_dialog._on_gbs_login_finished (lines 552-625).
        WR-03: reset _login_proc FIRST before any emission so re-entrant
        notify_expiry_detected() calls that fire from connected slots see
        _login_proc as None immediately.

        Success requires all four conditions (mirror AccountsDialog exactly):
            1. exit_code == 0
            2. netscape_text is non-empty
            3. stderr category is absent (None) or "Success"
            4. _validate_gbs_cookies(netscape_text) returns True

        On success: write cookies to gbs_cookies_path() with 0o600 perms
        immediately (T-40-03 / T-87.1-03), then emit relogin_succeeded.
        On failure: emit relogin_failed with a reason string.

        Security: NO GBS cookie bytes / credentials are passed to any
        logging call (T-87.1-05). Only categories, URLs, error enums logged.
        """
        proc = self._login_proc
        self._login_proc = None  # WR-03: clear guard FIRST

        # --- Inline stderr parse (mirrors accounts_dialog._parse_oauth_stderr)
        # ~15 lines, stdlib only. Duplicated here deliberately (see module
        # docstring design-decision note; extraction deferred per A4).
        # T-999.3-05: malformed lines skipped without eval.
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
            for raw_line in stderr_text.splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict) and "category" in obj:
                    last_event = obj

        # --- Read stdout (Netscape cookie dump on success)
        # CRITICAL: do NOT .strip() — Netscape format preserves leading
        # newlines (accounts_dialog.py:569-570 anti-pitfall).
        netscape_text: str = ""
        if proc is not None:
            try:
                netscape_text = (
                    proc.readAllStandardOutput().data().decode(
                        "utf-8", errors="replace"
                    )
                )
            except Exception:
                netscape_text = ""

        # Deferred imports — avoid module-load cost (matches Phase 60
        # deferred pattern; also avoids importing paths at module top
        # which would lock the platformdirs root before tests redirect it).
        from musicstreamer.gbs_api import _validate_gbs_cookies
        from musicstreamer import paths
        import os

        # --- Four-condition success gate (T-87.1-04)
        success_category = (
            last_event is None or last_event.get("category") == "Success"
        )
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
            # T-40-03: restrict file permissions IMMEDIATELY after write
            os.chmod(cookies_path, 0o600)
            self.relogin_succeeded.emit()
        else:
            self.relogin_failed.emit("Login was cancelled or failed")

    def _on_error(self, error: QProcess.ProcessError) -> None:
        """Handle QProcess error events (e.g. FailedToStart).

        Mirror of accounts_dialog._on_gbs_login_error (lines 627-652).

        Fires when the oauth_helper subprocess fails to start (or for other
        QProcess errors). finished is NOT emitted on FailedToStart, so this
        is the sole handler for that case — without it, _login_proc stays
        non-None permanently and the WR-03 guard blocks all future re-login
        attempts for the session (T-87.1-02 / Pitfall 2).

        Gate on FailedToStart specifically: Crashed also fires errorOccurred
        but finished IS also emitted for Crashed — the _on_finished failure
        path handles that case; we must not double-emit relogin_failed.

        Security: logs the ProcessError enum value only — no cookie bytes
        (T-87.1-05).
        """
        _log.warning(
            "GBS relogin subprocess errorOccurred (QProcess.ProcessError=%s).",
            error,
        )
        if error == QProcess.ProcessError.FailedToStart:
            # WR-03: reset re-entrancy guard FIRST (before emission) so
            # re-entrant notify_expiry_detected() calls see None immediately.
            self._login_proc = None
            self.relogin_failed.emit("Could not start login helper")
