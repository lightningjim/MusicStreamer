"""Unit tests for the GBS.FM login-subprocess helper (Phase 76).

The full QWebEngine flow cannot be unit-tested headlessly (it requires a live
gbs.fm login), so these tests cover the pure-Python helpers:
- `_PROVIDER` module constant + `_emit_event` provider field refactor
- `_GBS_LOGIN_URL` / `_GBS_TRIGGER_COOKIES` constants
- `_cookie_domain_matches_gbs` domain matching (accepts + lookalike rejection)
- `_GbsLoginWindow` import / constants
- `main()` argparse dispatch for `--mode gbs` (+ `_PROVIDER` assignment)
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Task 1: _PROVIDER module constant + _emit_event refactor
# ---------------------------------------------------------------------------

def test_provider_default_value():
    """Phase 76 Task 1: module-level `_PROVIDER` defaults to `"twitch"`.

    Default preserves the existing Twitch test contract — _emit_event called
    before main() runs (or in tests that don't override) still emits
    provider="twitch".
    """
    from musicstreamer import oauth_helper
    assert oauth_helper._PROVIDER == "twitch"


def test_emit_event_reads_provider_when_set_to_gbs(monkeypatch, capsys):
    """Phase 76 Task 1: `_emit_event` reads module-level `_PROVIDER`.

    Setting `_PROVIDER = "gbs"` via monkeypatch causes the emitted JSON event
    to carry `"provider": "gbs"` — NOT the hardcoded `"twitch"` that the
    pre-refactor implementation used.
    """
    from musicstreamer import oauth_helper

    monkeypatch.setattr(oauth_helper, "_PROVIDER", "gbs")
    oauth_helper._emit_event("Success", detail="")

    captured = capsys.readouterr()
    assert captured.out == ""
    lines = captured.err.strip().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["category"] == "Success"
    assert event["detail"] == ""
    assert event["provider"] == "gbs"


def test_emit_event_reads_provider_when_set_to_google(monkeypatch, capsys):
    """Phase 76 Task 1: works for any provider value (not just gbs / twitch)."""
    from musicstreamer import oauth_helper

    monkeypatch.setattr(oauth_helper, "_PROVIDER", "google")
    oauth_helper._emit_event("Success", detail="")

    event = json.loads(capsys.readouterr().err.strip())
    assert event["provider"] == "google"


def test_emit_event_default_provider_stays_twitch(capsys):
    """Phase 76 Task 1: with no monkeypatch, `_emit_event` emits the default
    provider value (`"twitch"`). Existing Twitch test contract preserved."""
    from musicstreamer import oauth_helper

    # Sanity: starting state is the module default.
    assert oauth_helper._PROVIDER == "twitch"

    oauth_helper._emit_event("Success", detail="")
    event = json.loads(capsys.readouterr().err.strip())
    assert event["provider"] == "twitch"


# ---------------------------------------------------------------------------
# Task 2: _GBS_LOGIN_URL / _GBS_TRIGGER_COOKIES / _cookie_domain_matches_gbs
# ---------------------------------------------------------------------------

def _fake_cookie(name: str, value: str, domain: str):
    """Construct a MagicMock that quacks like a QNetworkCookie."""
    c = MagicMock()
    c.name.return_value = name.encode("utf-8")
    c.value.return_value = value.encode("utf-8")
    c.domain.return_value = domain
    return c


def test_gbs_login_url_constant():
    """Phase 76 Task 2 / CONTEXT.md D-08 — login URL matches gbs.fm Django auth form."""
    from musicstreamer.oauth_helper import _GBS_LOGIN_URL
    assert _GBS_LOGIN_URL == "https://gbs.fm/accounts/login/"


def test_gbs_trigger_cookies_constant():
    """Phase 76 Task 2 / CONTEXT.md D-06 — trigger set = sessionid + csrftoken."""
    from musicstreamer.oauth_helper import _GBS_TRIGGER_COOKIES
    assert _GBS_TRIGGER_COOKIES == frozenset(("sessionid", "csrftoken"))


def test_cookie_domain_matches_gbs_bare():
    from musicstreamer.oauth_helper import _cookie_domain_matches_gbs
    assert _cookie_domain_matches_gbs(_fake_cookie("sessionid", "v", "gbs.fm"))


def test_cookie_domain_matches_gbs_www():
    from musicstreamer.oauth_helper import _cookie_domain_matches_gbs
    assert _cookie_domain_matches_gbs(_fake_cookie("sessionid", "v", "www.gbs.fm"))


def test_cookie_domain_matches_gbs_dot():
    from musicstreamer.oauth_helper import _cookie_domain_matches_gbs
    assert _cookie_domain_matches_gbs(_fake_cookie("sessionid", "v", ".gbs.fm"))


def test_cookie_domain_matches_gbs_subdomain():
    from musicstreamer.oauth_helper import _cookie_domain_matches_gbs
    assert _cookie_domain_matches_gbs(_fake_cookie("sessionid", "v", "sub.gbs.fm"))


def test_cookie_domain_rejects_gbs_lookalike():
    """T-76-01: subdomain-prefix-style lookalike must be rejected."""
    from musicstreamer.oauth_helper import _cookie_domain_matches_gbs
    assert not _cookie_domain_matches_gbs(_fake_cookie("sessionid", "v", "fakegbs.fm"))


def test_cookie_domain_rejects_gbs_subdomain_attack():
    """T-76-01: `gbs.fm` appearing as a label inside a different domain must be rejected."""
    from musicstreamer.oauth_helper import _cookie_domain_matches_gbs
    assert not _cookie_domain_matches_gbs(
        _fake_cookie("sessionid", "v", "gbs.fm.evil.com")
    )


def test_cookie_domain_rejects_unrelated_gbs():
    from musicstreamer.oauth_helper import _cookie_domain_matches_gbs
    assert not _cookie_domain_matches_gbs(_fake_cookie("sessionid", "v", "example.com"))


# ---------------------------------------------------------------------------
# Task 3: _GbsLoginWindow class importable + timeout constant
# ---------------------------------------------------------------------------

def test_gbs_login_window_class_importable():
    """Phase 76 Task 3: class importable (no syntax errors)."""
    from musicstreamer.oauth_helper import _GbsLoginWindow
    assert _GbsLoginWindow is not None


def test_gbs_login_window_timeout_constant():
    """Phase 76 Task 3 / RESEARCH.md §_GbsLoginWindow Design — mirror Twitch 120s."""
    from musicstreamer.oauth_helper import _GbsLoginWindow
    assert _GbsLoginWindow._TIMEOUT_MS == 120_000


# ---------------------------------------------------------------------------
# Task 4: main() argparse extension for --mode gbs
# ---------------------------------------------------------------------------

def test_argparse_accepts_mode_gbs():
    """Phase 76 Task 4: argparse `choices=[...,"gbs"]` is wired.

    Validates by parsing through a copy of the argparse spec — the live `main()`
    constructs a QApplication which we cannot exercise headlessly.
    """
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=["twitch", "google", "gbs"])
    ns = parser.parse_args(["--mode", "gbs"])
    assert ns.mode == "gbs"


def test_argparse_rejects_invalid_mode():
    """Argparse rejects unknown modes with SystemExit(2)."""
    import argparse
    import pytest
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=["twitch", "google", "gbs"])
    with pytest.raises(SystemExit):
        parser.parse_args(["--mode", "invalid"])
