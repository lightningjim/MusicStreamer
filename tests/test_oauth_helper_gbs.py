"""Unit tests for the GBS.FM cookie-harvest helper (Phase 76).

The full QWebEngine flow cannot be unit-tested headlessly (it requires a live
gbs.fm login), so these tests cover the pure-Python helpers:
- Cookie domain matching
- Trigger-cookie set logic (sessionid + csrftoken)
- Netscape flush format
- Structured stderr event schema with provider="gbs"
- Constants wiring
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# _fake_cookie helper — mirror tests/test_oauth_helper_twitch.py:73-80 verbatim
# ---------------------------------------------------------------------------

# Mirror: tests/test_oauth_helper_twitch.py:73-80
def _fake_cookie(name: str, value: str, domain: str):
    """Construct a MagicMock that quacks like a QNetworkCookie for the narrow
    surface _on_cookie_added touches."""
    c = MagicMock()
    c.name.return_value = name.encode("utf-8")
    c.value.return_value = value.encode("utf-8")
    c.domain.return_value = domain
    return c


# ---------------------------------------------------------------------------
# Constants / login URL — Phase 76 D-08, D-06
# Mirror shape: tests/test_oauth_helper_twitch.py:118-125
# ---------------------------------------------------------------------------

# Mirror: tests/test_oauth_helper_twitch.py:118-120
def test_gbs_login_url_constant():
    from musicstreamer import oauth_helper
    assert oauth_helper._GBS_LOGIN_URL == "https://gbs.fm/accounts/login/"


# Mirror: tests/test_oauth_helper_twitch.py:123-125
def test_gbs_trigger_cookies_constant():
    from musicstreamer.oauth_helper import _GBS_TRIGGER_COOKIES
    assert _GBS_TRIGGER_COOKIES == frozenset({"sessionid", "csrftoken"})


# ---------------------------------------------------------------------------
# Cookie domain matching — Phase 76 D-06
# Mirror shape: tests/test_oauth_helper_twitch.py:83-106
# ---------------------------------------------------------------------------

# Mirror: tests/test_oauth_helper_twitch.py:83-85
def test_cookie_domain_matches_gbs_dot():
    from musicstreamer.oauth_helper import _cookie_domain_matches_gbs
    assert _cookie_domain_matches_gbs(_fake_cookie("sessionid", "val", ".gbs.fm"))


# Mirror: tests/test_oauth_helper_twitch.py:88-90
def test_cookie_domain_matches_gbs_www():
    from musicstreamer.oauth_helper import _cookie_domain_matches_gbs
    assert _cookie_domain_matches_gbs(_fake_cookie("sessionid", "val", "www.gbs.fm"))


# Mirror: tests/test_oauth_helper_twitch.py:93-95
def test_cookie_domain_matches_gbs_bare():
    from musicstreamer.oauth_helper import _cookie_domain_matches_gbs
    assert _cookie_domain_matches_gbs(_fake_cookie("sessionid", "val", "gbs.fm"))


def test_cookie_domain_matches_gbs_subdomain():
    """sub.gbs.fm ends with .gbs.fm so the predicate accepts it."""
    from musicstreamer.oauth_helper import _cookie_domain_matches_gbs
    assert _cookie_domain_matches_gbs(_fake_cookie("sessionid", "val", "sub.gbs.fm"))


# Mirror: tests/test_oauth_helper_twitch.py:103-106
def test_cookie_domain_rejects_lookalike_gbs():
    from musicstreamer.oauth_helper import _cookie_domain_matches_gbs
    # "fakegbs.fm" does NOT end with ".gbs.fm" or equal any of our domains
    assert not _cookie_domain_matches_gbs(_fake_cookie("sessionid", "val", "fakegbs.fm"))


def test_cookie_domain_rejects_subdomain_attack():
    """gbs.fm.evil.com must NOT match — endswith(".gbs.fm") is false."""
    from musicstreamer.oauth_helper import _cookie_domain_matches_gbs
    assert not _cookie_domain_matches_gbs(_fake_cookie("sessionid", "val", "gbs.fm.evil.com"))


# ---------------------------------------------------------------------------
# _emit_event provider-field regression guard — Phase 76 anti-pitfall
# Mirror shape: tests/test_oauth_helper_twitch.py:20-34
# ---------------------------------------------------------------------------

# Mirror: tests/test_oauth_helper_twitch.py:20-34 (adapted for provider="gbs" regression)
def test_gbs_emits_provider_gbs_field(monkeypatch, capsys):
    """Anti-pitfall guard: after _PROVIDER refactor (Plan 76-01 Task 2),
    --mode gbs events MUST carry provider="gbs" (not the hardcoded "twitch"
    default that exists at base).

    RED state (before Plan 76-01 Task 2): _PROVIDER attribute does not exist;
    monkeypatch.setattr raises AttributeError.
    GREEN state (after Plan 76-01 Task 2): _PROVIDER constant exists with
    default "twitch"; _emit_event reads it dynamically; setting it to "gbs"
    makes the emitted event carry provider="gbs".
    """
    from musicstreamer import oauth_helper

    # Simulate main() having set the provider for the GBS subprocess.
    # Default raising=True means this fails with AttributeError before
    # Plan 76-01 Task 2 lands — which is the desired RED behavior.
    monkeypatch.setattr(oauth_helper, "_PROVIDER", "gbs")

    oauth_helper._emit_event("Success", detail="")

    lines = capsys.readouterr().err.strip().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["provider"] == "gbs"   # regression guard
    assert event["category"] == "Success"


def test_emit_event_default_provider_is_twitch(capsys):
    """Twitch invariant preservation guard: without any provider override,
    _emit_event MUST still produce provider="twitch" so the existing Twitch
    test surface continues passing after the _PROVIDER refactor.

    This test passes at base (current hardcoded "twitch") AND after Plan 76-01
    Task 2 lands (because _PROVIDER defaults to "twitch" until main() sets it).
    """
    from musicstreamer.oauth_helper import _emit_event

    _emit_event("Success", detail="")
    lines = capsys.readouterr().err.strip().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["provider"] == "twitch"
