"""Wave 0 unit tests for musicstreamer.twitch_helix (ART-AVATAR-04 / T-89b-01/02).

These tests run RED before twitch_helix.py is created and GREEN after Task 2
implements the module.  No live network calls — all urllib.request.urlopen and
token-file reads are monkeypatched.

Fixture-locked Twitch GQL user response body. (89b UAT fix: the web auth-token
cookie has no Helix REST access — it returns 404 — so the avatar is fetched via
the GQL endpoint, the same one streamlink uses for playback.)
"""
from __future__ import annotations

import json
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

#: Fixture-locked GQL user() 200 response (gql.twitch.tv/gql shape)
GQL_USER_RESPONSE = json.dumps(
    {
        "data": {
            "user": {
                "profileImageURL": (
                    "https://static-cdn.jtvnw.net/jtv_user_pictures/"
                    "twitchdev-profile_image-300x300.png"
                )
            }
        }
    }
).encode("utf-8")

#: Fake CDN image bytes (PNG magic header)
CDN_IMAGE_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

#: Known test token value (never hit the real network)
FAKE_TOKEN = "test_token_abc123"


def _make_cm(data: bytes) -> MagicMock:
    """Create a context-manager mock whose .read() returns `data`."""
    resp = MagicMock()
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    resp.read.return_value = data
    return resp


def _make_urlopen_side_effect(gql_bytes: bytes, cdn_bytes: bytes):
    """Return a side-effect function for urlopen.

    First call (GQL user) returns gql_bytes; second call (CDN) returns
    cdn_bytes.  Distinguishes by call order so no URL inspection is needed.
    """
    calls = [0]  # mutable counter inside closure

    def _side_effect(request_or_url, timeout=None):
        calls[0] += 1
        if calls[0] == 1:
            return _make_cm(gql_bytes)
        return _make_cm(cdn_bytes)

    return _side_effect


# ---------------------------------------------------------------------------
# test_parse_login
# ---------------------------------------------------------------------------


def test_parse_login():
    """RESEARCH Finding #2 / Pitfall 4/6: _parse_login handles all URL forms."""
    from musicstreamer.twitch_helix import _parse_login  # noqa: PLC0415

    assert _parse_login("https://www.twitch.tv/twitchdev") == "twitchdev"
    assert _parse_login("https://www.twitch.tv/twitchdev/") == "twitchdev"
    assert _parse_login("https://www.twitch.tv/twitchdev?ref=header") == "twitchdev"
    assert _parse_login("https://www.twitch.tv/twitchdev#x") == "twitchdev"
    assert _parse_login("https://www.twitch.tv/TwitchDev") == "twitchdev"
    assert _parse_login("twitchdev") == "twitchdev"  # bare login (no slash)
    assert _parse_login("twitch_dev_99") == "twitch_dev_99"  # underscores/digits kept

    # WR-01 / T-89b-02: a malformed segment with & or = must be clamped to the
    # leading [a-z0-9_] run so nothing can inject into the Helix query string or
    # the persisted "Twitch: <login>" provider name.
    assert _parse_login("https://www.twitch.tv/user&client_id=evil") == "user"
    assert _parse_login("user=admin") == "user"
    assert _parse_login("https://www.twitch.tv/a b") == "a"  # space terminates run
    assert _parse_login("") == ""  # empty input
    assert _parse_login("#frag") == ""  # nothing before the fragment


# ---------------------------------------------------------------------------
# test_fetch_calls_helix_with_bearer_and_client_id
# ---------------------------------------------------------------------------


def test_fetch_calls_gql_with_oauth_and_client_id(tmp_path, monkeypatch):
    """T-89b-01: GQL request carries Authorization: OAuth + Client-Id and binds
    the login as a query variable (not string-interpolated — T-89b-02).

    The CDN download must NOT carry the Authorization header (token scope).
    """
    import musicstreamer.paths as paths

    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    token_path = tmp_path / "twitch-token.txt"
    token_path.write_text(FAKE_TOKEN)

    captured_requests: list = []

    def _urlopen_side_effect(request_or_url, timeout=None):
        captured_requests.append(request_or_url)
        idx = len(captured_requests)
        if idx == 1:
            return _make_cm(GQL_USER_RESPONSE)
        return _make_cm(CDN_IMAGE_BYTES)

    with patch("urllib.request.urlopen", side_effect=_urlopen_side_effect):
        from musicstreamer import twitch_helix  # noqa: PLC0415

        result = twitch_helix.fetch_channel_avatar("https://www.twitch.tv/twitchdev")

    assert result == CDN_IMAGE_BYTES

    # First call must be a POST Request to the GQL endpoint (not a bare URL string)
    gql_req = captured_requests[0]
    assert hasattr(gql_req, "get_header"), (
        "GQL call must use urllib.request.Request, not a bare URL string"
    )
    assert gql_req.full_url == "https://gql.twitch.tv/gql"
    assert gql_req.get_method() == "POST"

    # Web client requires the OAuth framing (NOT Bearer — Helix's Bearer 404s here)
    assert gql_req.get_header("Authorization") == f"OAuth {FAKE_TOKEN}"
    assert gql_req.get_header("Client-id") == "kimne78kx3ncx6brgo4mv6wki5h1ko"

    # The login is bound as a GraphQL variable, not interpolated into the query
    payload = json.loads(gql_req.data.decode("utf-8"))
    assert payload["variables"] == {"login": "twitchdev"}
    assert "profileImageURL" in payload["query"]
    assert "$login" in payload["query"]  # parameterised, injection-safe

    # Second call (CDN) must NOT carry Authorization — token scope (T-89b-01 / Pitfall 5).
    # The CDN download is invoked with a bare URL string, so by construction it can
    # carry no headers. Assert it is NOT a Request object (which could hold an auth
    # header) — a live drift-guard: if a future change wraps the CDN download in a
    # Request that attaches the token, this fails. (The old `if hasattr(...)` form was
    # dead code — a str has no get_header, so the assertion never ran. WR-02.)
    cdn_req = captured_requests[1]
    assert isinstance(cdn_req, str), (
        "CDN image download must use a bare URL string (no Request → no headers → "
        "no token leak); got a Request object that could carry Authorization"
    )
    assert not hasattr(cdn_req, "get_header")


# ---------------------------------------------------------------------------
# test_fetch_raises_on_missing_token
# ---------------------------------------------------------------------------


def test_fetch_raises_on_missing_token(tmp_path, monkeypatch):
    """D-07 / RESEARCH #1: missing twitch-token.txt → raises before any urlopen."""
    import musicstreamer.paths as paths

    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    # Do NOT write the token file — simulate absence

    with patch("urllib.request.urlopen") as mock_urlopen:
        from musicstreamer import twitch_helix  # noqa: PLC0415

        with pytest.raises((RuntimeError, OSError)):
            twitch_helix.fetch_channel_avatar("https://www.twitch.tv/twitchdev")

        # urlopen must NOT have been called (raise happens before any HTTP)
        mock_urlopen.assert_not_called()


# ---------------------------------------------------------------------------
# test_fetch_raises_on_empty_data
# ---------------------------------------------------------------------------


def test_fetch_raises_on_empty_data(tmp_path, monkeypatch):
    """GQL 200 with data.user == null (login not found) → raises ValueError."""
    import musicstreamer.paths as paths

    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    (tmp_path / "twitch-token.txt").write_text(FAKE_TOKEN)

    empty_response = json.dumps({"data": {"user": None}}).encode("utf-8")

    with patch("urllib.request.urlopen", return_value=_make_cm(empty_response)):
        from musicstreamer import twitch_helix  # noqa: PLC0415

        with pytest.raises((ValueError, RuntimeError)):
            twitch_helix.fetch_channel_avatar(
                "https://www.twitch.tv/nonexistentuser12345"
            )


# ---------------------------------------------------------------------------
# test_fetch_raises_on_401
# ---------------------------------------------------------------------------


def test_fetch_raises_on_http_error(tmp_path, monkeypatch):
    """A non-2xx HTTP status from GQL propagates (caller catches and falls back)."""
    import musicstreamer.paths as paths

    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    (tmp_path / "twitch-token.txt").write_text(FAKE_TOKEN)

    http_err = urllib.error.HTTPError(
        url="https://gql.twitch.tv/gql",
        code=401,
        msg="Unauthorized",
        hdrs={},  # type: ignore[arg-type]
        fp=None,
    )

    with patch("urllib.request.urlopen", side_effect=http_err):
        from musicstreamer import twitch_helix  # noqa: PLC0415

        with pytest.raises(urllib.error.HTTPError):
            twitch_helix.fetch_channel_avatar("https://www.twitch.tv/twitchdev")


# ---------------------------------------------------------------------------
# test_no_square_guard  (source-grep drift-guard)
# ---------------------------------------------------------------------------


def test_no_square_guard():
    """D-05 / RESEARCH #3: Twitch images are always square — no width!=height guard needed.

    Source-grep drift-guard: confirm 'not square' is absent and the GQL
    'profileImageURL' field is present in twitch_helix.py.
    """
    src_path = Path(__file__).parent.parent / "musicstreamer" / "twitch_helix.py"
    assert src_path.exists(), "musicstreamer/twitch_helix.py must exist"
    src = src_path.read_text(encoding="utf-8")
    assert "not square" not in src, (
        "twitch_helix.py must NOT contain a 'not square' guard "
        "(Twitch profile images are always square — D-05)"
    )
    assert "width != height" not in src, (
        "twitch_helix.py must NOT contain a width != height guard (D-05)"
    )
    assert "profileImageURL" in src, (
        "twitch_helix.py must reference the GQL 'profileImageURL' field"
    )


# ---------------------------------------------------------------------------
# test_token_never_logged  (source-grep drift-guard)
# ---------------------------------------------------------------------------


def test_token_never_logged():
    """T-89b-01: the token value must never be emitted via logging/print.

    Source-grep drift-guard: assert no print() or logger.*/logging.* call in
    twitch_helix.py contains the token variable identifier.
    """
    src_path = Path(__file__).parent.parent / "musicstreamer" / "twitch_helix.py"
    assert src_path.exists(), "musicstreamer/twitch_helix.py must exist"
    src = src_path.read_text(encoding="utf-8")

    # Scan each line for log/print statements that include the word 'token'
    for i, line in enumerate(src.splitlines(), 1):
        stripped = line.strip()
        # Skip comments
        if stripped.startswith("#"):
            continue
        has_log_or_print = (
            "print(" in line
            or "logging." in line
            or "logger." in line
            or "log." in line
        )
        if has_log_or_print and "token" in line:
            pytest.fail(
                f"twitch_helix.py line {i} emits the token variable via log/print "
                f"(T-89b-01 violation): {line!r}"
            )


# ---------------------------------------------------------------------------
# test_registry_registers_twitch
# ---------------------------------------------------------------------------


def test_registry_registers_twitch(tmp_path, monkeypatch):
    """D-05: get_avatar_fetcher('twitch') returns twitch_helix.fetch_channel_avatar
    after yt_import is imported (registration fires at module load).
    """
    # Use a fresh import after ensuring the modules are available
    import importlib
    import sys

    # Remove cached modules so reimport exercises registration
    for mod_name in list(sys.modules.keys()):
        if mod_name in ("musicstreamer.yt_import", "musicstreamer.twitch_helix"):
            del sys.modules[mod_name]

    import musicstreamer.paths as paths

    monkeypatch.setattr(paths, "_root_override", str(tmp_path))

    from musicstreamer import twitch_helix  # noqa: PLC0415
    from musicstreamer import yt_import  # noqa: PLC0415

    fetcher = yt_import.get_avatar_fetcher("twitch")
    assert fetcher is twitch_helix.fetch_channel_avatar, (
        "get_avatar_fetcher('twitch') must return twitch_helix.fetch_channel_avatar "
        "after yt_import is imported"
    )
