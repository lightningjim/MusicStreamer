"""Subprocess OAuth helper — isolated QWebEngineView for Twitch/Google login.

Runs in a SEPARATE process to avoid loading QtWebEngine (130MB) in the main app.
Communicates results back via stdout (token for Twitch, cookie text for Google)
and structured JSON-line diagnostics on stderr.

Usage:
  python -m musicstreamer.oauth_helper --mode twitch
  python -m musicstreamer.oauth_helper --mode google

Twitch flow (Phase 999.3, Path X — piggyback web client_id + implicit flow):
  1. Generate CSRF state (secrets.token_urlsafe(16)).
  2. Start a loopback HTTP listener on 127.0.0.1:TWITCH_REDIRECT_PORT.
     (# D-04: loopback HTTP listener + HTML bounce page
      # — NOT urlChanged fragment capture — that was the bug)
  3. Open QWebEngineView on build_authorize_url(state). User logs in on twitch.tv.
  4. Twitch redirects to http://127.0.0.1:PORT/#access_token=...&state=...
  5. Our server serves an inline HTML bounce page whose JS reads
     window.location.hash and POSTs {token, state} to /capture.
     (# T-999.3-04: bounce page is self-contained — no off-host refs)
  6. /capture validates the state and signals the main Qt thread
     (# Pitfall 3: HTTP handler thread cannot touch QWidgets
      # — signal main via threading.Event + QTimer poll).
  7. Main thread prints the token on stdout, emits Success on stderr, exits 0.
"""
from __future__ import annotations

import argparse
import http.server
import json
import secrets
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlencode, urlparse

# Guard QtWebEngineWidgets import — it is a separate apt package
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError as _qtwe_err:
    print(
        f"ERROR: PySide6.QtWebEngineWidgets is not installed.\n"
        f"Install it with: sudo apt install python3-pyside6.qtwebenginewidgets\n"
        f"Details: {_qtwe_err}",
        file=sys.stderr,
    )
    sys.exit(2)

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtNetwork import QNetworkCookie
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget

from musicstreamer.constants import (
    TWITCH_AUTH_URL_BASE,
    TWITCH_CLIENT_ID,
    TWITCH_REDIRECT_PORT,
)


# ---------------------------------------------------------------------------
# Structured stderr events (D-12)
# ---------------------------------------------------------------------------

def _emit_event(category: str, detail: str = "", **extra) -> None:
    """Emit a single JSON-line diagnostic event on stderr.

    Schema (fixed keys): {ts, category, detail, provider}.
    NEVER pass tokens, URL fragments, or query-string values as `detail`.
    Callers pass short enum-like strings (e.g. "state_mismatch", "access_denied",
    "120s", str(errno)).
    """
    event = {
        "ts": time.time(),
        "category": category,
        "detail": detail,
        "provider": "twitch",
    }
    if extra:
        event.update(extra)
    print(json.dumps(event, separators=(",", ":")), file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Twitch OAuth — loopback + bounce-page flow (Phase 999.3 D-01..D-07, D-12)
# ---------------------------------------------------------------------------

def _generate_state() -> str:
    """CSRF state parameter (D-06). secrets.token_urlsafe(16) yields >=22 chars
    from [A-Za-z0-9_-]."""
    return secrets.token_urlsafe(16)


def build_authorize_url(state: str) -> str:
    """Build the Twitch authorize URL for implicit flow with CSRF state.

    D-01: piggyback web client_id (only streamlink-compatible token source).
    D-02: implicit flow (response_type=token). Empty scope.
    D-03: fixed loopback redirect (http://127.0.0.1:17823).
    """
    params = {
        "client_id": TWITCH_CLIENT_ID,
        "redirect_uri": f"http://127.0.0.1:{TWITCH_REDIRECT_PORT}",
        "response_type": "token",
        "scope": "",
        "state": state,
    }
    return f"{TWITCH_AUTH_URL_BASE}?{urlencode(params)}"


# Self-contained HTML bounce page (T-999.3-04 — no off-host <script>/<img>/<link>).
# The inline JS reads window.location.hash, extracts access_token + state,
# and POSTs them to /capture on this same loopback server.
_BOUNCE_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>MusicStreamer — Twitch login</title>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       background: #18181b; color: #efeff1; margin: 0; padding: 2em;
       display: flex; align-items: center; justify-content: center;
       min-height: 100vh; }
#status { max-width: 32em; text-align: center; }
h1 { font-size: 1.25em; margin: 0 0 0.5em 0; }
p { margin: 0.25em 0; opacity: 0.8; }
</style>
</head>
<body>
<div id="status">
<h1>Completing Twitch login...</h1>
<p id="msg">Capturing token, please wait.</p>
</div>
<script>
(function () {
  var msgEl = document.getElementById('msg');
  var h1El = document.querySelector('h1');
  var hash = window.location.hash || '';
  if (hash.indexOf('#') === 0) { hash = hash.substring(1); }
  var params = new URLSearchParams(hash);
  var token = params.get('access_token');
  var state = params.get('state');
  if (!token || !state) {
    h1El.textContent = 'Login failed';
    msgEl.textContent = 'No access token present in redirect.';
    return;
  }
  fetch('/capture', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token: token, state: state })
  }).then(function (r) {
    if (r.ok) {
      h1El.textContent = 'Logged in';
      msgEl.textContent = 'You can close this window.';
    } else {
      h1El.textContent = 'Login failed';
      msgEl.textContent = 'Token was rejected (state mismatch).';
    }
  }).catch(function () {
    h1El.textContent = 'Login failed';
    msgEl.textContent = 'Could not reach local capture endpoint.';
  });
})();
</script>
</body>
</html>
"""


class _RedirectHandler(BaseHTTPRequestHandler):
    """Loopback HTTP request handler.

    Runs on the HTTPServer background thread. MUST NOT call any QWidget method
    (Pitfall 3). Communicates with the main Qt thread via the server's
    threading.Event + mutable attributes, which the main thread polls.
    """

    # Silence the default access log (T-999.3-05 — never write URLs to stderr).
    def log_message(self, format, *args):  # noqa: A002, N802
        return

    # ---- GET -------------------------------------------------------------
    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        # Handle Twitch error redirects that arrive as query-string
        # (e.g. http://127.0.0.1:17823/?error=access_denied).
        qs = parse_qs(parsed.query)
        if "error" in qs:
            err_val = qs.get("error", [""])[0] or "unknown_error"
            # Stored on server so main-thread poller can surface the category.
            self.server.twitch_error = err_val  # type: ignore[attr-defined]
            self.server.done.set()              # type: ignore[attr-defined]
            body = b"<html><body><p>Login rejected.</p></body></html>"
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # Otherwise: serve the self-contained bounce page.
        body = _BOUNCE_PAGE_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ---- POST ------------------------------------------------------------
    def do_POST(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/capture":
            body = b'{"error":"not_found"}'
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        raw = self.rfile.read(length) if length > 0 else b""
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}

        token = payload.get("token") if isinstance(payload, dict) else None
        state = payload.get("state") if isinstance(payload, dict) else None

        expected = self.server.expected_state  # type: ignore[attr-defined]
        if not token or not state or state != expected:
            # T-999.3-02: CSRF mismatch rejected as InvalidTokenResponse.
            # Detail is a short enum-like string — never includes token/state values.
            _emit_event("InvalidTokenResponse", detail="state_mismatch")
            body = b'{"error":"state_mismatch"}'
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # Success: record token for main-thread poll and signal done.
        self.server.captured_event = {"token": token}  # type: ignore[attr-defined]
        self.server.done.set()                          # type: ignore[attr-defined]
        body = b'{"status":"ok"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _TwitchLoopbackServer(http.server.HTTPServer):
    """Single-purpose loopback HTTPServer.

    # T-999.3-01: bind 127.0.0.1 ONLY — never 0.0.0.0, never 'localhost'
    # (localhost may resolve to ::, bypassing LAN-block intent).
    """

    allow_reuse_address = True  # Pitfall 4: avoid TIME_WAIT on rapid retry.

    def __init__(self, port: int, expected_state: str) -> None:
        super().__init__(("127.0.0.1", port), _RedirectHandler)
        self.expected_state: str = expected_state
        self.done: threading.Event = threading.Event()
        self.captured_event: dict | None = None
        self.twitch_error: str | None = None


class _TwitchAuthWindow(QMainWindow):
    """Main-thread Qt window. Hosts QWebEngineView + polls the loopback server.

    All QWidget mutations happen here on the main thread (Pitfall 3).
    """

    _POLL_MS = 50
    _TIMEOUT_MS = 120_000  # 120s login deadline (Pitfall 6 covers close-before-login)

    def __init__(self, server: _TwitchLoopbackServer, state: str) -> None:
        super().__init__()
        self.setWindowTitle("Twitch Login")
        self.resize(800, 600)
        self._server = server
        self._state = state
        self._finished = False

        self._view = QWebEngineView(self)
        self.setCentralWidget(self._view)
        self._view.load(QUrl(build_authorize_url(state)))

        # Poll the loopback server for capture/error events.
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(self._POLL_MS)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.start()

        # Login timeout watchdog.
        QTimer.singleShot(self._TIMEOUT_MS, self._on_timeout)

    def _poll(self) -> None:
        if self._finished:
            return
        if not self._server.done.is_set():
            return

        if self._server.captured_event:
            token = self._server.captured_event.get("token", "")
            # Stdout contract: token only, no newline (matches Google cookie path).
            sys.stdout.write(token)
            sys.stdout.flush()
            _emit_event("Success", detail="")
            self._shutdown_and_exit(0)
            return

        if self._server.twitch_error:
            _emit_event("TwitchRejectedRequest", detail=self._server.twitch_error)
            self._shutdown_and_exit(1)
            return

        # done set but no captured_event / twitch_error — defensive fallback.
        _emit_event("InvalidTokenResponse", detail="empty_capture")
        self._shutdown_and_exit(1)

    def _on_timeout(self) -> None:
        if self._finished or self._server.done.is_set():
            return
        _emit_event("LoginTimeout", detail="120s")
        self._shutdown_and_exit(1)

    def _shutdown_and_exit(self, code: int) -> None:
        self._finished = True
        try:
            self._poll_timer.stop()
        except Exception:
            pass
        # server.shutdown() must run outside the server thread — we're on main.
        try:
            self._server.shutdown()
        except Exception:
            pass
        try:
            self._server.server_close()
        except Exception:
            pass
        if code == 0:
            QApplication.quit()
        else:
            QApplication.exit(code)

    def closeEvent(self, event):  # noqa: N802
        if not self._finished and not self._server.done.is_set():
            _emit_event("WindowClosedBeforeLogin", detail="")
            self._shutdown_and_exit(1)
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Google / YouTube Cookie capture (D-07: UNTOUCHED — working as-is)
# ---------------------------------------------------------------------------

# Indicator that login is complete enough to harvest cookies
_YOUTUBE_DONE_URLS = ("myaccount.google.com", "accounts.google.com/v3/signin/challenge/pwd")


def _cookie_to_netscape(cookie: QNetworkCookie) -> str:
    """Format a single QNetworkCookie in Netscape/Wget format."""
    domain = cookie.domain()
    include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
    secure = "TRUE" if cookie.isSecure() else "FALSE"
    path = cookie.path() or "/"
    expires = cookie.expirationDate().toSecsSinceEpoch() if not cookie.isSessionCookie() else "0"
    name = str(cookie.name(), "utf-8")
    value = str(cookie.value(), "utf-8")
    return f"{domain}\t{include_subdomains}\t{path}\t{secure}\t{expires}\t{name}\t{value}"


class _GoogleWindow(QMainWindow):
    """Minimal window that opens Google login, harvests cookies, prints Netscape format."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Google Login")
        self.resize(800, 600)

        self._cookies: list[QNetworkCookie] = []
        self._collected = False

        # Central widget with view + done button
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self._view = QWebEngineView(self)
        layout.addWidget(self._view)

        self._done_btn = QPushButton("Done — save cookies", central)
        self._done_btn.clicked.connect(self._on_done)
        layout.addWidget(self._done_btn)

        self.setCentralWidget(central)

        # Wire cookie store
        profile = self._view.page().profile()
        profile.setPersistentCookiesPolicy(
            profile.PersistentCookiesPolicy.NoPersistentCookies  # type: ignore[attr-defined]
        )
        cookie_store = profile.cookieStore()
        cookie_store.cookieAdded.connect(self._on_cookie_added)

        self._view.load(QUrl("https://accounts.google.com/ServiceLogin"))

    def _on_cookie_added(self, cookie: QNetworkCookie) -> None:
        self._cookies.append(cookie)

    def _on_done(self) -> None:
        if self._collected:
            return
        self._collected = True
        self._flush_cookies()

    def _flush_cookies(self) -> None:
        lines = ["# Netscape HTTP Cookie File"]
        for c in self._cookies:
            lines.append(_cookie_to_netscape(c))
        print("\n".join(lines), end="")
        QApplication.quit()

    def closeEvent(self, event):  # noqa: N802
        if not self._collected:
            QApplication.exit(1)
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="musicstreamer.oauth_helper",
        description="Subprocess OAuth helper for MusicStreamer",
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["twitch", "google"],
        help="OAuth mode: twitch (token) or google (YouTube cookies)",
    )
    args = parser.parse_args()

    # Create standalone QApplication — this is a separate process
    app = QApplication(sys.argv)

    if args.mode == "twitch":
        state = _generate_state()
        try:
            server = _TwitchLoopbackServer(TWITCH_REDIRECT_PORT, state)
        except OSError as exc:
            _emit_event("PortBusy", detail=str(exc.errno) if exc.errno else "OSError")
            sys.exit(1)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        window = _TwitchAuthWindow(server, state)
    else:
        window = _GoogleWindow()

    window.show()
    exit_code = app.exec()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
