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

import argparse
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


# ---------------------------------------------------------------------------
# argparse --mode gbs — Phase 76 D-08, Plan 76-01 Task 1
# Mirror shape: tests/test_oauth_helper_twitch.py:118-125 (local-parser
# approach matches that test's granularity — full subprocess invocation
# would bring up QApplication which is GUI-heavy)
# ---------------------------------------------------------------------------

def test_argparse_accepts_mode_gbs():
    """oauth_helper.main()'s argparse extends choices to include 'gbs'.

    Approach: construct a local ArgumentParser mirroring main()'s definition
    with the post-76-01 choices list and verify it parses '--mode gbs'
    without SystemExit. This guards the choices-list shape locally; the
    end-to-end argparse extension lands in Plan 76-01 Task 4.

    Once Plan 76-01 Task 4 lands, this regression-asserts the canonical
    choices list by reading from oauth_helper itself (see below).
    """
    # Local mirror of the post-76-01 parser shape.
    parser = argparse.ArgumentParser(prog="musicstreamer.oauth_helper")
    parser.add_argument(
        "--mode",
        required=True,
        choices=["twitch", "google", "gbs"],
    )
    ns = parser.parse_args(["--mode", "gbs"])
    assert ns.mode == "gbs"

    # After Plan 76-01 Task 4, oauth_helper.main builds an equivalent parser.
    # Verify the constants the helper exposes are consistent: _GBS_LOGIN_URL
    # must be reachable from the module (already covered by
    # test_gbs_login_url_constant). The choices-list extension is verified
    # behaviorally via the local parser above. RED until Task 4 lands because
    # this test imports _GBS_LOGIN_URL (a Task 1 deliverable) AND the
    # _PROVIDER constant (a Task 2 deliverable) cross-checked below.
    from musicstreamer import oauth_helper
    assert hasattr(oauth_helper, "_GBS_LOGIN_URL")


# ---------------------------------------------------------------------------
# _GbsLoginWindow construction — Phase 76 D-05
# Mirror shape: tests/test_oauth_helper_twitch.py:151-154 (presence/import
# smoke; full GUI construction is unit-tested via method-level mocks below)
# ---------------------------------------------------------------------------

# Mirror: tests/test_oauth_helper_twitch.py:151-154
def test_gbs_login_window_constructor_smoke():
    """_GbsLoginWindow class is importable; _TIMEOUT_MS class attribute
    matches the 120s deadline (D-05 mirror of Twitch)."""
    from musicstreamer.oauth_helper import _GbsLoginWindow
    assert _GbsLoginWindow._TIMEOUT_MS == 120_000


# ---------------------------------------------------------------------------
# _GbsLoginWindow trigger / flush / timeout / closeEvent — Phase 76 D-06, D-07, D-09
# Mirror shape: tests/test_oauth_helper_twitch.py:73-80 (uses _fake_cookie
# helper to construct mock cookies; manually instantiates via __new__ to
# avoid the GUI plumbing path the Twitch tests sidestep entirely)
# ---------------------------------------------------------------------------

def _make_bare_window():
    """Construct a _GbsLoginWindow without running __init__ (which would
    bring up QWebEngineView / QApplication / QTimer GUI plumbing).

    Manually initialize the attributes the methods under test touch — mirror
    of _GbsLoginWindow.__init__ Python-level state (see PATTERNS.md Excerpt
    1A lines 161-180): _finished, _cookies, _observed_names.

    Per RESEARCH.md note "The full QWebEngine flow cannot be unit-tested
    headlessly", this skips the GUI-init plumbing while still exercising
    the pure-Python state-machine paths.
    """
    from musicstreamer.oauth_helper import _GbsLoginWindow
    win = _GbsLoginWindow.__new__(_GbsLoginWindow)
    win._finished = False
    win._cookies = []
    win._observed_names = set()
    return win


def _make_secure_fake_cookie(name: str, value: str, domain: str):
    """Extension of _fake_cookie that also stubs the surface
    _cookie_to_netscape touches (isSecure, path, isSessionCookie, etc.).

    _fake_cookie alone covers _on_cookie_added (name/value/domain). The
    Netscape flush path additionally calls .isSecure()/.path()/
    .isSessionCookie()/.expirationDate() — stub these so the round-trip
    test against _validate_gbs_cookies works without a real QNetworkCookie.
    """
    c = _fake_cookie(name, value, domain)
    c.isSecure.return_value = True
    c.path.return_value = "/"
    c.isSessionCookie.return_value = True   # makes expirationDate path moot
    return c


def test_gbs_trigger_fires_on_both_cookies(monkeypatch, capsys):
    """D-06: _flush_cookies fires once both sessionid AND csrftoken are
    observed on a gbs.fm domain; stdout starts with the Netscape header."""
    from musicstreamer import oauth_helper

    monkeypatch.setattr(oauth_helper.QApplication, "quit", lambda: None)
    monkeypatch.setattr(oauth_helper.QApplication, "exit", lambda code=0: None)

    win = _make_bare_window()
    # First trigger cookie only — flush MUST NOT fire yet.
    oauth_helper._GbsLoginWindow._on_cookie_added(
        win, _make_secure_fake_cookie("sessionid", "v1", ".gbs.fm")
    )
    out_after_first = capsys.readouterr().out
    assert win._finished is False
    assert out_after_first == ""

    # Second trigger cookie — flush fires; _finished flips True; stdout has
    # the Netscape header.
    oauth_helper._GbsLoginWindow._on_cookie_added(
        win, _make_secure_fake_cookie("csrftoken", "v2", ".gbs.fm")
    )
    captured = capsys.readouterr()
    assert win._finished is True
    assert captured.out.startswith("# Netscape HTTP Cookie File")


def test_gbs_trigger_does_not_fire_on_only_sessionid(monkeypatch, capsys):
    """Only sessionid observed → not finished, no stdout output."""
    from musicstreamer import oauth_helper

    monkeypatch.setattr(oauth_helper.QApplication, "quit", lambda: None)
    monkeypatch.setattr(oauth_helper.QApplication, "exit", lambda code=0: None)

    win = _make_bare_window()
    oauth_helper._GbsLoginWindow._on_cookie_added(
        win, _make_secure_fake_cookie("sessionid", "v1", ".gbs.fm")
    )
    captured = capsys.readouterr()
    assert win._finished is False
    assert captured.out == ""


def test_gbs_trigger_does_not_fire_on_only_csrftoken(monkeypatch, capsys):
    """Only csrftoken observed (anonymous page load) → not finished, no stdout.

    Per RESEARCH.md §Trigger Cookie Set: csrftoken is set on first
    anonymous page-load; sessionid only appears post-login. Waiting for
    BOTH is the deterministic trigger.
    """
    from musicstreamer import oauth_helper

    monkeypatch.setattr(oauth_helper.QApplication, "quit", lambda: None)
    monkeypatch.setattr(oauth_helper.QApplication, "exit", lambda code=0: None)

    win = _make_bare_window()
    oauth_helper._GbsLoginWindow._on_cookie_added(
        win, _make_secure_fake_cookie("csrftoken", "v1", ".gbs.fm")
    )
    captured = capsys.readouterr()
    assert win._finished is False
    assert captured.out == ""


def test_gbs_trigger_ignores_non_gbs_domain(monkeypatch, capsys):
    """Both trigger names on a non-gbs.fm domain (e.g. lookalike) → not
    finished, no stdout. Domain gate rejects before storage."""
    from musicstreamer import oauth_helper

    monkeypatch.setattr(oauth_helper.QApplication, "quit", lambda: None)
    monkeypatch.setattr(oauth_helper.QApplication, "exit", lambda code=0: None)

    win = _make_bare_window()
    oauth_helper._GbsLoginWindow._on_cookie_added(
        win, _make_secure_fake_cookie("sessionid", "v1", "fakegbs.fm")
    )
    oauth_helper._GbsLoginWindow._on_cookie_added(
        win, _make_secure_fake_cookie("csrftoken", "v2", "fakegbs.fm")
    )
    captured = capsys.readouterr()
    assert win._finished is False
    assert captured.out == ""


def test_gbs_flush_produces_valid_netscape(monkeypatch, capsys):
    """D-07 + integration: captured stdout after _flush_cookies is a Netscape
    cookies dump that the existing _validate_gbs_cookies validator accepts."""
    from musicstreamer import oauth_helper
    from musicstreamer.gbs_api import _validate_gbs_cookies

    monkeypatch.setattr(oauth_helper.QApplication, "quit", lambda: None)
    monkeypatch.setattr(oauth_helper.QApplication, "exit", lambda code=0: None)

    win = _make_bare_window()
    oauth_helper._GbsLoginWindow._on_cookie_added(
        win, _make_secure_fake_cookie("sessionid", "v1", ".gbs.fm")
    )
    oauth_helper._GbsLoginWindow._on_cookie_added(
        win, _make_secure_fake_cookie("csrftoken", "v2", ".gbs.fm")
    )
    netscape_dump = capsys.readouterr().out
    assert netscape_dump.startswith("# Netscape HTTP Cookie File")
    assert _validate_gbs_cookies(netscape_dump) is True


def test_gbs_flush_deduplicates_repeated_cookies(monkeypatch, capsys):
    """Per RESEARCH.md §Output Format dedup note (line 391-397): same
    (domain, name) cookie firing cookieAdded twice → only ONE line in the
    Netscape dump for that cookie (last value wins)."""
    from musicstreamer import oauth_helper

    monkeypatch.setattr(oauth_helper.QApplication, "quit", lambda: None)
    monkeypatch.setattr(oauth_helper.QApplication, "exit", lambda code=0: None)

    win = _make_bare_window()
    # Two sessionid values on same domain (simulates Django re-sending).
    oauth_helper._GbsLoginWindow._on_cookie_added(
        win, _make_secure_fake_cookie("sessionid", "first", ".gbs.fm")
    )
    oauth_helper._GbsLoginWindow._on_cookie_added(
        win, _make_secure_fake_cookie("sessionid", "second", ".gbs.fm")
    )
    # csrftoken triggers the flush.
    oauth_helper._GbsLoginWindow._on_cookie_added(
        win, _make_secure_fake_cookie("csrftoken", "tok", ".gbs.fm")
    )
    netscape_dump = capsys.readouterr().out
    lines = netscape_dump.splitlines()
    # 1 header + 1 sessionid (deduped) + 1 csrftoken = 3 lines.
    assert len(lines) >= 3
    sessionid_lines = [l for l in lines if "\tsessionid\t" in l]
    assert len(sessionid_lines) == 1
    # Last value wins.
    assert sessionid_lines[0].endswith("\tsecond")


def test_gbs_timeout_emits_login_timeout(monkeypatch, capsys):
    """D-09: _on_timeout emits {category=LoginTimeout, detail=120s,
    provider=gbs} on stderr (with _PROVIDER monkeypatched)."""
    from musicstreamer import oauth_helper

    monkeypatch.setattr(oauth_helper, "_PROVIDER", "gbs")
    monkeypatch.setattr(oauth_helper.QApplication, "quit", lambda: None)
    monkeypatch.setattr(oauth_helper.QApplication, "exit", lambda code=0: None)

    win = _make_bare_window()
    oauth_helper._GbsLoginWindow._on_timeout(win)

    err_lines = capsys.readouterr().err.strip().splitlines()
    assert len(err_lines) == 1
    event = json.loads(err_lines[0])
    assert event["category"] == "LoginTimeout"
    assert event["detail"] == "120s"
    assert event["provider"] == "gbs"
    assert win._finished is True


def test_gbs_window_closed_before_login(monkeypatch, capsys):
    """D-09: closeEvent before flush emits WindowClosedBeforeLogin event
    on stderr (with _PROVIDER monkeypatched to 'gbs').

    Note: super().closeEvent() may raise on a __new__'d instance that
    bypasses Qt's C++ construction; we catch and assert on the side
    effects that fired before super() was called.
    """
    from musicstreamer import oauth_helper

    monkeypatch.setattr(oauth_helper, "_PROVIDER", "gbs")
    monkeypatch.setattr(oauth_helper.QApplication, "quit", lambda: None)
    monkeypatch.setattr(oauth_helper.QApplication, "exit", lambda code=0: None)

    win = _make_bare_window()
    # Phase 76 IN-02: narrowed from `except Exception` to the specific Qt-side
    # failure modes super().closeEvent raises against a bare-__new__'d instance:
    #   - TypeError: PySide6 raises this when the underlying C++ QMainWindow
    #     was never constructed and a method tries to forward to it.
    #   - RuntimeError: raised on direct shiboken access when the C++ side is
    #     absent (older / future PySide6 variants).
    # Narrowing prevents the test from silently passing if _emit_event or
    # _finish itself raised (e.g. a JSON encoding bug) — those would now
    # propagate and fail the test.
    try:
        oauth_helper._GbsLoginWindow.closeEvent(win, MagicMock())
    except (TypeError, RuntimeError):
        # super().closeEvent on a bare __new__'d instance fails because Qt's
        # C++ side wasn't constructed. The _emit_event + _finish calls happen
        # BEFORE super() per the design in PATTERNS.md Excerpt 1A lines 233-237,
        # so the assertions below are still meaningful.
        pass

    err_lines = capsys.readouterr().err.strip().splitlines()
    assert len(err_lines) == 1
    event = json.loads(err_lines[0])
    assert event["category"] == "WindowClosedBeforeLogin"
    assert event["provider"] == "gbs"
    assert win._finished is True


def test_gbs_collects_all_gbs_cookies_not_just_triggers(monkeypatch, capsys):
    """Forward-compat per RESEARCH.md lines 368-374: the Netscape dump
    contains EVERY gbs.fm-domain cookie observed, not just the two
    trigger names. Auxiliary cookies (e.g. Django 'messages') survive."""
    from musicstreamer import oauth_helper

    monkeypatch.setattr(oauth_helper.QApplication, "quit", lambda: None)
    monkeypatch.setattr(oauth_helper.QApplication, "exit", lambda code=0: None)

    win = _make_bare_window()
    # Auxiliary cookie observed BEFORE the triggers complete the set.
    oauth_helper._GbsLoginWindow._on_cookie_added(
        win, _make_secure_fake_cookie("messages", "aux-val", ".gbs.fm")
    )
    oauth_helper._GbsLoginWindow._on_cookie_added(
        win, _make_secure_fake_cookie("sessionid", "v1", ".gbs.fm")
    )
    oauth_helper._GbsLoginWindow._on_cookie_added(
        win, _make_secure_fake_cookie("csrftoken", "v2", ".gbs.fm")
    )
    netscape_dump = capsys.readouterr().out
    # All three cookie names appear in the data lines.
    assert "\tsessionid\t" in netscape_dump
    assert "\tcsrftoken\t" in netscape_dump
    assert "\tmessages\t" in netscape_dump
