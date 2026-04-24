"""Unit tests for Twitch OAuth helper (Phase 999.3 Plan 01).

Covers:
- TWITCH_* constants wiring in musicstreamer.constants
- build_authorize_url() URL shape
- _emit_event() JSON-line stderr schema
- _generate_state() CSPRNG state generation

These tests exercise pure helpers — no QApplication or network required.
"""
from __future__ import annotations

import io
import json
import re
import string
import sys
from contextlib import redirect_stderr


# ---------------------------------------------------------------------------
# Constants (musicstreamer.constants)
# ---------------------------------------------------------------------------

def test_twitch_client_id_constant():
    """D-01: piggyback Twitch web client_id is hardcoded."""
    from musicstreamer import constants
    assert constants.TWITCH_CLIENT_ID == "kimne78kx3ncx6brgo4mv6wki5h1ko"


def test_twitch_redirect_port_constant():
    """D-03: redirect port is a fixed int in the dynamic range."""
    from musicstreamer import constants
    assert isinstance(constants.TWITCH_REDIRECT_PORT, int)
    # Must be 17823 specifically, or at least in IANA dynamic/unassigned range.
    assert constants.TWITCH_REDIRECT_PORT == 17823
    assert 49152 > constants.TWITCH_REDIRECT_PORT >= 1024 or 49152 <= constants.TWITCH_REDIRECT_PORT <= 65535


def test_twitch_auth_url_base_constant():
    """Authorize endpoint base URL."""
    from musicstreamer import constants
    assert constants.TWITCH_AUTH_URL_BASE == "https://id.twitch.tv/oauth2/authorize"


# ---------------------------------------------------------------------------
# build_authorize_url()
# ---------------------------------------------------------------------------

def test_build_authorize_url_includes_required_params():
    """URL must contain client_id, redirect_uri, response_type=token, scope=, state."""
    from musicstreamer.oauth_helper import build_authorize_url
    url = build_authorize_url("statevalue123")
    assert url.startswith("https://id.twitch.tv/oauth2/authorize?")
    # client_id piggyback
    assert "client_id=kimne78kx3ncx6brgo4mv6wki5h1ko" in url
    # implicit flow
    assert "response_type=token" in url
    # fixed loopback redirect — value may be URL-encoded
    assert ("redirect_uri=http%3A%2F%2F127.0.0.1%3A17823" in url
            or "redirect_uri=http%3A//127.0.0.1%3A17823" in url
            or "redirect_uri=http://127.0.0.1:17823" in url)
    # empty scope
    assert "scope=" in url
    # state pass-through
    assert "state=statevalue123" in url


def test_build_authorize_url_state_is_reflected():
    """A different state value yields a different URL containing that state."""
    from musicstreamer.oauth_helper import build_authorize_url
    url_a = build_authorize_url("AAA")
    url_b = build_authorize_url("BBB")
    assert "state=AAA" in url_a
    assert "state=BBB" in url_b
    assert url_a != url_b


# ---------------------------------------------------------------------------
# _emit_event() — structured stderr JSON lines
# ---------------------------------------------------------------------------

def test_emit_event_writes_json_line_to_stderr():
    """_emit_event writes exactly one newline-terminated JSON line to stderr
    with keys {ts, category, detail, provider}; ts is a float."""
    from musicstreamer.oauth_helper import _emit_event
    buf = io.StringIO()
    with redirect_stderr(buf):
        _emit_event("Success", detail="")
    text = buf.getvalue()
    # Exactly one newline-terminated line
    assert text.endswith("\n"), repr(text)
    assert text.count("\n") == 1, repr(text)
    event = json.loads(text.strip())
    assert set(event.keys()) >= {"ts", "category", "detail", "provider"}
    assert event["category"] == "Success"
    assert event["detail"] == ""
    assert event["provider"] == "twitch"
    assert isinstance(event["ts"], float)


def test_emit_event_category_values():
    """Subsequent calls yield independent events with the provided category."""
    from musicstreamer.oauth_helper import _emit_event
    buf = io.StringIO()
    with redirect_stderr(buf):
        _emit_event("InvalidTokenResponse", detail="state_mismatch")
        _emit_event("LoginTimeout", detail="120s")
    lines = [line for line in buf.getvalue().splitlines() if line.strip()]
    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["category"] == "InvalidTokenResponse"
    assert first["detail"] == "state_mismatch"
    assert second["category"] == "LoginTimeout"
    assert second["detail"] == "120s"


def test_emit_event_never_includes_token_like_detail():
    """Sanity: _emit_event preserves the detail as passed — callers are
    responsible for not passing tokens/URLs. This test documents the
    contract: detail is a short string and the function does not add
    additional fields that could leak."""
    from musicstreamer.oauth_helper import _emit_event
    buf = io.StringIO()
    with redirect_stderr(buf):
        _emit_event("TwitchRejectedRequest", detail="access_denied")
    event = json.loads(buf.getvalue().strip())
    # No token, URL, or fragment in the emitted JSON
    assert "access_token" not in buf.getvalue()
    assert "http://" not in buf.getvalue()
    assert event["detail"] == "access_denied"


# ---------------------------------------------------------------------------
# _generate_state() — CSPRNG state parameter
# ---------------------------------------------------------------------------

def test_generate_state_length_and_charset():
    """secrets.token_urlsafe(16) yields >= 22 chars from the URL-safe alphabet."""
    from musicstreamer.oauth_helper import _generate_state
    s = _generate_state()
    assert isinstance(s, str)
    assert len(s) >= 22
    # URL-safe base64 alphabet: [A-Za-z0-9_-]
    allowed = set(string.ascii_letters + string.digits + "-_")
    assert set(s) <= allowed, f"unexpected chars in state: {set(s) - allowed!r}"


def test_generate_state_is_unique():
    """Two invocations must differ (CSPRNG)."""
    from musicstreamer.oauth_helper import _generate_state
    a = _generate_state()
    b = _generate_state()
    assert a != b
