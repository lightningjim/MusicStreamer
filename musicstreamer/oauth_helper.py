"""Subprocess OAuth helper — isolated QWebEngineView for Twitch/Google login.

Runs in a SEPARATE process to avoid loading QtWebEngine (130MB) in the main app.
Communicates results back via stdout (token for Twitch, cookie text for Google)
and structured JSON-line diagnostics on stderr.

Usage:
  python -m musicstreamer.oauth_helper --mode twitch
  python -m musicstreamer.oauth_helper --mode google

Twitch flow (Phase 999.3 pivot — cookie-harvest):
  Rationale: the piggyback web client_id ("kimne78...") is Twitch's own SPA client
  whose server-side redirect_uri whitelist only accepts twitch.tv pages — so
  OAuth-implicit-flow + loopback-redirect cannot work for this client_id. And
  registering our own Twitch app yields a Helix Bearer token that streamlink's
  private GQL endpoint rejects. The only streamlink-compatible token is the one
  the Twitch web UI itself uses — which lives in the `auth-token` cookie on
  `.twitch.tv` after login.

  1. Open QWebEngineView on https://www.twitch.tv/login.
  2. Watch QWebEngineCookieStore.cookieAdded for the auth-token cookie on .twitch.tv
     (or www.twitch.tv).
  3. Once the cookie is observed, extract its value, print to stdout (no newline,
     matches existing contract), emit Success on stderr, exit 0.
  4. On window-close-before-login: emit WindowClosedBeforeLogin, exit 1.
  5. On 120s timeout: emit LoginTimeout, exit 1.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

# Must be set BEFORE any QtWebEngine imports or QApplication construction.
# Twitch's page-level browser sniffing rejects QtWebEngine's default UA with
# "Your browser is not currently supported." The profile-level setHttpUserAgent
# is applied too late for Twitch's initial detection; we need the browser
# process itself to advertise Chrome from the start.
_CHROME_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36"
)
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    + f' --user-agent="{_CHROME_UA}"'
).strip()

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


# ---------------------------------------------------------------------------
# Structured stderr events (D-12)
# ---------------------------------------------------------------------------

def _emit_event(category: str, detail: str = "", **extra) -> None:
    """Emit a single JSON-line diagnostic event on stderr.

    Schema (fixed keys): {ts, category, detail, provider}.
    NEVER pass token values, cookie values, or URL fragments as `detail`.
    Callers pass short enum-like strings (e.g. "no_auth_token", "120s").
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
# Twitch cookie-harvest (Phase 999.3 pivot)
# ---------------------------------------------------------------------------

_TWITCH_LOGIN_URL = "https://www.twitch.tv/login"
_TWITCH_AUTH_COOKIE = "auth-token"
def _cookie_domain_matches(cookie: QNetworkCookie) -> bool:
    """True if the cookie's domain is a Twitch domain we accept.

    Accepts: "twitch.tv", "www.twitch.tv", ".twitch.tv", or any "*.twitch.tv"
    subdomain. Rejects lookalikes like "faketwitch.tv" or "twitch.tv.evil.com".
    """
    domain = cookie.domain()
    if domain in ("twitch.tv", "www.twitch.tv", ".twitch.tv"):
        return True
    # "*.twitch.tv" — must have at least one additional label before ".twitch.tv"
    return domain.endswith(".twitch.tv")


class _TwitchCookieWindow(QMainWindow):
    """Log in to twitch.tv; capture the auth-token cookie streamlink needs.

    Uses QWebEngineCookieStore.cookieAdded — the same pattern as _GoogleWindow —
    but auto-completes as soon as the auth-token cookie is observed (no "Done"
    button). The auth-token cookie is set by twitch.tv the moment the login
    form completes successfully.
    """

    _TIMEOUT_MS = 120_000  # 120s login deadline

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Twitch Login")
        self.resize(800, 600)
        self._finished = False

        self._view = QWebEngineView(self)
        self.setCentralWidget(self._view)

        # Session-only cookies — never persist to disk in the subprocess profile.
        profile = self._view.page().profile()
        profile.setPersistentCookiesPolicy(
            profile.PersistentCookiesPolicy.NoPersistentCookies  # type: ignore[attr-defined]
        )
        # Belt-and-suspenders UA override at the profile level.
        # Primary UA override is the --user-agent Chromium flag set at module
        # import time (above); this profile-level call keeps the two in sync
        # so any later page() → profile() inspection shows the same string.
        profile.setHttpUserAgent(_CHROME_UA)
        cookie_store = profile.cookieStore()
        cookie_store.cookieAdded.connect(self._on_cookie_added)

        self._view.load(QUrl(_TWITCH_LOGIN_URL))

        # Login timeout watchdog.
        QTimer.singleShot(self._TIMEOUT_MS, self._on_timeout)

    def _on_cookie_added(self, cookie: QNetworkCookie) -> None:
        if self._finished:
            return
        try:
            name = str(cookie.name(), "utf-8")
        except Exception:
            return
        if name != _TWITCH_AUTH_COOKIE:
            return
        if not _cookie_domain_matches(cookie):
            return
        try:
            value = str(cookie.value(), "utf-8").strip()
        except Exception:
            _emit_event("InvalidTokenResponse", detail="cookie_decode_error")
            self._finish(1)
            return
        if not value:
            # Empty cookie value — treat as invalid.
            _emit_event("InvalidTokenResponse", detail="empty_auth_token")
            self._finish(1)
            return
        # Success: stdout contract = raw token, no newline (matches Google path
        # and what AccountsDialog._on_oauth_finished expects).
        sys.stdout.write(value)
        sys.stdout.flush()
        _emit_event("Success", detail="")
        self._finish(0)

    def _on_timeout(self) -> None:
        if self._finished:
            return
        _emit_event("LoginTimeout", detail="120s")
        self._finish(1)

    def _finish(self, code: int) -> None:
        self._finished = True
        if code == 0:
            QApplication.quit()
        else:
            QApplication.exit(code)

    def closeEvent(self, event):  # noqa: N802
        if not self._finished:
            _emit_event("WindowClosedBeforeLogin", detail="")
            self._finish(1)
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Google / YouTube Cookie capture (UNTOUCHED — working as-is)
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
        help="OAuth mode: twitch (cookie-harvest) or google (YouTube cookies)",
    )
    args = parser.parse_args()

    # Create standalone QApplication — this is a separate process
    app = QApplication(sys.argv)

    if args.mode == "twitch":
        window: QMainWindow = _TwitchCookieWindow()
    else:
        window = _GoogleWindow()

    window.show()
    exit_code = app.exec()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
