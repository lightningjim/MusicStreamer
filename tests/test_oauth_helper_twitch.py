"""Unit tests for the Twitch cookie-harvest helper (Phase 999.3 pivot).

The full QWebEngine flow cannot be unit-tested headlessly (it requires a live
twitch.tv login), so these tests cover the pure-Python helpers:
- Cookie domain matching
- Structured stderr event schema
- Constants wiring
- Regression guards against the abandoned OAuth-redirect approach
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# _emit_event — structured JSON-line events on stderr
# ---------------------------------------------------------------------------

def test_emit_event_writes_json_line_to_stderr(capsys):
    from musicstreamer.oauth_helper import _emit_event

    _emit_event("Success", detail="")
    captured = capsys.readouterr()
    # stdout untouched
    assert captured.out == ""
    # stderr: exactly one JSON line
    lines = captured.err.strip().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["category"] == "Success"
    assert event["detail"] == ""
    assert event["provider"] == "twitch"
    assert isinstance(event["ts"], (int, float))


def test_emit_event_preserves_json_single_line_even_with_newlines(capsys):
    from musicstreamer.oauth_helper import _emit_event

    _emit_event("LoginTimeout", detail="line1\nline2")
    lines = capsys.readouterr().err.strip().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["detail"] == "line1\nline2"


def test_emit_event_failure_categories_match_parent_contract(capsys):
    """Parent (AccountsDialog) expects these exact category strings — regression
    guard to prevent silent contract drift."""
    from musicstreamer.oauth_helper import _emit_event

    for cat in (
        "Success",
        "InvalidTokenResponse",
        "WindowClosedBeforeLogin",
        "LoginTimeout",
    ):
        _emit_event(cat, detail="x")

    lines = capsys.readouterr().err.strip().splitlines()
    assert [json.loads(l)["category"] for l in lines] == [
        "Success",
        "InvalidTokenResponse",
        "WindowClosedBeforeLogin",
        "LoginTimeout",
    ]


# ---------------------------------------------------------------------------
# Cookie domain matching
# ---------------------------------------------------------------------------

def _fake_cookie(name: str, value: str, domain: str):
    """Construct a MagicMock that quacks like a QNetworkCookie for the narrow
    surface _on_cookie_added touches."""
    c = MagicMock()
    c.name.return_value = name.encode("utf-8")
    c.value.return_value = value.encode("utf-8")
    c.domain.return_value = domain
    return c


def test_cookie_domain_matches_dot_twitch():
    from musicstreamer.oauth_helper import _cookie_domain_matches
    assert _cookie_domain_matches(_fake_cookie("auth-token", "tok", ".twitch.tv"))


def test_cookie_domain_matches_www_twitch():
    from musicstreamer.oauth_helper import _cookie_domain_matches
    assert _cookie_domain_matches(_fake_cookie("auth-token", "tok", "www.twitch.tv"))


def test_cookie_domain_matches_bare_twitch():
    from musicstreamer.oauth_helper import _cookie_domain_matches
    assert _cookie_domain_matches(_fake_cookie("auth-token", "tok", "twitch.tv"))


def test_cookie_domain_rejects_unrelated():
    from musicstreamer.oauth_helper import _cookie_domain_matches
    assert not _cookie_domain_matches(_fake_cookie("auth-token", "tok", "example.com"))


def test_cookie_domain_rejects_lookalike():
    from musicstreamer.oauth_helper import _cookie_domain_matches
    # "faketwitch.tv" does NOT end with ".twitch.tv" or equal any of our domains
    assert not _cookie_domain_matches(_fake_cookie("auth-token", "tok", "faketwitch.tv"))


# ---------------------------------------------------------------------------
# Constants / login URL
# ---------------------------------------------------------------------------

def test_twitch_login_url_constant():
    from musicstreamer import constants
    assert constants.TWITCH_LOGIN_URL == "https://www.twitch.tv/login"


def test_oauth_helper_uses_same_login_url():
    from musicstreamer import oauth_helper
    assert oauth_helper._TWITCH_LOGIN_URL == "https://www.twitch.tv/login"


def test_auth_token_cookie_name_constant():
    from musicstreamer.oauth_helper import _TWITCH_AUTH_COOKIE
    assert _TWITCH_AUTH_COOKIE == "auth-token"


# ---------------------------------------------------------------------------
# Regression: abandoned OAuth-redirect flow must not reappear
# ---------------------------------------------------------------------------

def test_no_loopback_server_class():
    from musicstreamer import oauth_helper
    assert not hasattr(oauth_helper, "_TwitchLoopbackServer")
    assert not hasattr(oauth_helper, "_RedirectHandler")
    assert not hasattr(oauth_helper, "_BOUNCE_PAGE_HTML")
    assert not hasattr(oauth_helper, "build_authorize_url")


def test_constants_no_longer_export_oauth_redirect_symbols():
    from musicstreamer import constants
    assert not hasattr(constants, "TWITCH_REDIRECT_PORT")
    assert not hasattr(constants, "TWITCH_AUTH_URL_BASE")
    assert not hasattr(constants, "TWITCH_CLIENT_ID")


# ---------------------------------------------------------------------------
# _GoogleWindow regression: untouched surface
# ---------------------------------------------------------------------------

def test_google_window_class_still_present():
    from musicstreamer import oauth_helper
    assert hasattr(oauth_helper, "_GoogleWindow")
    assert hasattr(oauth_helper, "_cookie_to_netscape")
