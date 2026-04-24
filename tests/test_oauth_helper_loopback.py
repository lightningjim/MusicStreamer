"""Unit tests for the Twitch OAuth loopback HTTP listener (Phase 999.3 Plan 01).

Covers:
- T-999.3-01: loopback binds only to 127.0.0.1 (never 0.0.0.0, never localhost)
- T-999.3-02: /capture POST requires matching state (CSRF)
- T-999.3-04: HTML bounce page is self-contained (no off-host resources)
- /capture success path populates server.captured_event + sets server.done
- Error redirect (?error=access_denied) stored on server for main-thread polling
"""
from __future__ import annotations

import http.client
import json
import re
import threading
import time

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_server(port: int, expected_state: str):
    """Instantiate _TwitchLoopbackServer and start serve_forever in a thread.
    Returns (server, thread). Caller must call server.shutdown() + server.server_close()."""
    from musicstreamer.oauth_helper import _TwitchLoopbackServer
    server = _TwitchLoopbackServer(port, expected_state)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server, t


def _next_port(base: int = 40000) -> int:
    """Each test grabs a unique port to avoid collision when running in parallel."""
    import random
    return base + random.randint(0, 9000)


# ---------------------------------------------------------------------------
# T-999.3-01: bind 127.0.0.1 only
# ---------------------------------------------------------------------------

def test_loopback_server_binds_127_only():
    """server.server_address[0] MUST be '127.0.0.1' — never '0.0.0.0', never '::' or 'localhost'."""
    from musicstreamer.oauth_helper import _TwitchLoopbackServer
    port = _next_port()
    server = _TwitchLoopbackServer(port, "statex")
    try:
        assert server.server_address[0] == "127.0.0.1"
    finally:
        server.server_close()


def test_loopback_server_allow_reuse_address():
    """Pitfall 4: allow_reuse_address avoids TIME_WAIT on rapid retry."""
    from musicstreamer.oauth_helper import _TwitchLoopbackServer
    port = _next_port()
    server = _TwitchLoopbackServer(port, "statex")
    try:
        assert server.allow_reuse_address is True
    finally:
        server.server_close()


# ---------------------------------------------------------------------------
# T-999.3-04: bounce page self-contained (no off-host refs)
# ---------------------------------------------------------------------------

def test_get_root_returns_self_contained_bounce_page():
    """GET / returns 200 text/html; body has NO src=http[s]:// or href=http[s]://."""
    port = _next_port()
    server, _t = _make_server(port, "statex")
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        conn.request("GET", "/")
        resp = conn.getresponse()
        body = resp.read().decode("utf-8", errors="replace")
        assert resp.status == 200
        ctype = resp.getheader("Content-Type", "")
        assert "text/html" in ctype
        # No off-host references (src= or href= pointing to http/https URL)
        assert re.search(r"""(src|href)=['"]https?://""", body) is None, (
            f"bounce page contains off-host ref: {body!r}"
        )
        # The inline JS must POST to /capture (relative path)
        assert "/capture" in body
    finally:
        server.shutdown()
        server.server_close()


# ---------------------------------------------------------------------------
# T-999.3-02: /capture requires matching state
# ---------------------------------------------------------------------------

def test_capture_accepts_matching_state():
    """POST /capture with matching state returns 200, populates captured_event."""
    port = _next_port()
    state = "STATE_OK_ABC"
    server, _t = _make_server(port, state)
    try:
        body = json.dumps({"token": "TKN_xyz", "state": state})
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        conn.request(
            "POST",
            "/capture",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        resp.read()
        assert resp.status == 200
        # Wait briefly for handler thread to set the event
        assert server.done.wait(timeout=2.0)
        assert server.captured_event is not None
        assert server.captured_event.get("token") == "TKN_xyz"
    finally:
        server.shutdown()
        server.server_close()


def test_capture_rejects_state_mismatch():
    """POST /capture with wrong state returns 400, does NOT populate captured_event."""
    port = _next_port()
    expected_state = "RIGHT_STATE"
    server, _t = _make_server(port, expected_state)
    try:
        body = json.dumps({"token": "TKN_leak", "state": "WRONG_STATE"})
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        conn.request(
            "POST",
            "/capture",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        resp.read()
        assert resp.status == 400
        # Handler must NOT have captured the token
        assert server.captured_event is None
    finally:
        server.shutdown()
        server.server_close()


def test_capture_rejects_missing_state():
    """POST /capture without state key returns 400, does NOT populate captured_event."""
    port = _next_port()
    server, _t = _make_server(port, "RIGHT_STATE")
    try:
        body = json.dumps({"token": "TKN_no_state"})
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        conn.request(
            "POST",
            "/capture",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        resp.read()
        assert resp.status == 400
        assert server.captured_event is None
    finally:
        server.shutdown()
        server.server_close()


# ---------------------------------------------------------------------------
# Twitch error redirect (?error=access_denied) handling
# ---------------------------------------------------------------------------

def test_get_with_error_query_records_twitch_error():
    """GET /?error=access_denied sets server.twitch_error and signals done."""
    port = _next_port()
    server, _t = _make_server(port, "statex")
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        conn.request("GET", "/?error=access_denied")
        resp = conn.getresponse()
        resp.read()
        # Status is not load-bearing; the signal is twitch_error + done
        assert server.done.wait(timeout=2.0)
        assert server.twitch_error == "access_denied"
        # captured_event remains None (no token was captured)
        assert server.captured_event is None
    finally:
        server.shutdown()
        server.server_close()


# ---------------------------------------------------------------------------
# 404 on unknown POST path
# ---------------------------------------------------------------------------

def test_post_to_unknown_path_returns_404():
    """Only /capture is accepted for POST."""
    port = _next_port()
    server, _t = _make_server(port, "statex")
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        conn.request(
            "POST",
            "/not-capture",
            body=json.dumps({"token": "x", "state": "statex"}),
            headers={"Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        resp.read()
        assert resp.status == 404
        assert server.captured_event is None
    finally:
        server.shutdown()
        server.server_close()
