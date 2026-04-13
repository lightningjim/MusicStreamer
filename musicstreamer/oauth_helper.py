"""Subprocess OAuth helper — isolated QWebEngineView for Twitch/Google login.

Runs in a SEPARATE process to avoid loading QtWebEngine (130MB) in the main app.
Communicates results back via stdout (token for Twitch, cookie text for Google).

Usage:
  python -m musicstreamer.oauth_helper --mode twitch
  python -m musicstreamer.oauth_helper --mode google
"""
from __future__ import annotations

import argparse
import sys

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

from PySide6.QtCore import QUrl
from PySide6.QtNetwork import QNetworkCookie
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton


# ---------------------------------------------------------------------------
# Twitch OAuth
# ---------------------------------------------------------------------------

TWITCH_AUTH_URL = (
    "https://id.twitch.tv/oauth2/authorize"
    "?client_id=kimne78kx3ncx6brgo4mv6wki5h1ko"
    "&redirect_uri=http://localhost"
    "&response_type=token"
    "&scope="
)


class _TwitchWindow(QMainWindow):
    """Minimal window that opens Twitch OAuth, captures token, prints to stdout."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Twitch Login")
        self.resize(800, 600)
        self._view = QWebEngineView(self)
        self.setCentralWidget(self._view)
        self._view.urlChanged.connect(self._on_url_changed)
        self._view.load(QUrl(TWITCH_AUTH_URL))

    def _on_url_changed(self, url: QUrl) -> None:
        fragment = url.fragment()  # text after '#'
        if "access_token=" in fragment:
            # Extract token from fragment: access_token=<TOKEN>&...
            for part in fragment.split("&"):
                if part.startswith("access_token="):
                    token = part[len("access_token="):]
                    print(token, end="")  # stdout only — no newline
                    QApplication.quit()
                    return

    def closeEvent(self, event):  # noqa: N802
        # User closed without token — exit with non-zero so caller knows
        QApplication.exit(1)
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Google / YouTube Cookie capture
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
        window = _TwitchWindow()
    else:
        window = _GoogleWindow()

    window.show()
    exit_code = app.exec()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
