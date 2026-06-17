"""Wave 0 unit tests for musicstreamer.twitch_helix (ART-AVATAR-04 / T-89b-01/02).

These tests run RED before twitch_helix.py is created and GREEN after Task 2
implements the module.  No live network calls — all urllib.request.urlopen and
token-file reads are monkeypatched.

Fixture-locked Helix /users response body matches RESEARCH Finding #1.
"""
from __future__ import annotations

import json
import urllib.error
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

#: Fixture-locked Helix /users 200 response (RESEARCH Finding #1 shape)
HELIX_USERS_RESPONSE = json.dumps(
    {
        "data": [
            {
                "id": "141981764",
                "login": "twitchdev",
                "display_name": "TwitchDev",
                "type": "",
                "broadcaster_type": "partner",
                "description": "Supporting third-party...",
                "profile_image_url": (
                    "https://static-cdn.jtvnw.net/jtv_user_pictures/"
                    "twitchdev-profile_image-300x300.png"
                ),
                "offline_image_url": "https://static-cdn.jtvnw.net/jtv_user_pictures/offline.png",
                "created_at": "2016-12-14T20:32:28Z",
            }
        ]
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


def _make_urlopen_side_effect(helix_bytes: bytes, cdn_bytes: bytes):
    """Return a side-effect function for urlopen.

    First call (Helix /users) returns helix_bytes; second call (CDN) returns
    cdn_bytes.  Distinguishes by call order so no URL inspection is needed.
    """
    calls = [0]  # mutable counter inside closure

    def _side_effect(request_or_url, timeout=None):
        calls[0] += 1
        if calls[0] == 1:
            return _make_cm(helix_bytes)
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


# ---------------------------------------------------------------------------
# test_fetch_calls_helix_with_bearer_and_client_id
# ---------------------------------------------------------------------------


def test_fetch_calls_helix_with_bearer_and_client_id(tmp_path, monkeypatch):
    """T-89b-01/D-06: Helix request carries Authorization: Bearer + Client-Id.

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
            return _make_cm(HELIX_USERS_RESPONSE)
        return _make_cm(CDN_IMAGE_BYTES)

    with patch("urllib.request.urlopen", side_effect=_urlopen_side_effect):
        from musicstreamer import twitch_helix  # noqa: PLC0415

        result = twitch_helix.fetch_channel_avatar("https://www.twitch.tv/twitchdev")

    assert result == CDN_IMAGE_BYTES

    # First call must be a Request object (not a plain URL string)
    helix_req = captured_requests[0]
    assert hasattr(helix_req, "get_header"), (
        "Helix call must use urllib.request.Request, not a bare URL string"
    )
    assert helix_req.full_url == "https://api.twitch.tv/helix/users?login=twitchdev"

    # Headers are stored with capitalised first letter by urllib internals
    assert helix_req.get_header("Authorization") == f"Bearer {FAKE_TOKEN}"
    assert helix_req.get_header("Client-id") == "kimne78kx3ncx6brgo4mv6wki5h1ko"

    # Second call (CDN) must NOT carry Authorization — token scope (T-89b-01 / Pitfall 5)
    cdn_req = captured_requests[1]
    if hasattr(cdn_req, "get_header"):
        # If it's a Request object, Authorization must be absent
        assert cdn_req.get_header("Authorization") is None


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
    """RESEARCH #1: Helix 200 with data:[] → raises ValueError."""
    import musicstreamer.paths as paths

    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    (tmp_path / "twitch-token.txt").write_text(FAKE_TOKEN)

    empty_response = json.dumps({"data": []}).encode("utf-8")

    with patch("urllib.request.urlopen", return_value=_make_cm(empty_response)):
        from musicstreamer import twitch_helix  # noqa: PLC0415

        with pytest.raises((ValueError, RuntimeError)):
            twitch_helix.fetch_channel_avatar(
                "https://www.twitch.tv/nonexistentuser12345"
            )


# ---------------------------------------------------------------------------
# test_fetch_raises_on_401
# ---------------------------------------------------------------------------


def test_fetch_raises_on_401(tmp_path, monkeypatch):
    """RESEARCH #1: Helix responds with HTTP 401 → raises (propagates)."""
    import musicstreamer.paths as paths

    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    (tmp_path / "twitch-token.txt").write_text(FAKE_TOKEN)

    http_401 = urllib.error.HTTPError(
        url="https://api.twitch.tv/helix/users?login=twitchdev",
        code=401,
        msg="Unauthorized",
        hdrs={},  # type: ignore[arg-type]
        fp=None,
    )

    with patch("urllib.request.urlopen", side_effect=http_401):
        from musicstreamer import twitch_helix  # noqa: PLC0415

        with pytest.raises(urllib.error.HTTPError):
            twitch_helix.fetch_channel_avatar("https://www.twitch.tv/twitchdev")


# ---------------------------------------------------------------------------
# test_no_square_guard  (source-grep drift-guard)
# ---------------------------------------------------------------------------


def test_no_square_guard():
    """D-05 / RESEARCH #3: Twitch images are always square — no width!=height guard needed.

    Source-grep drift-guard: confirm 'not square' is absent and
    'profile_image_url' is present in twitch_helix.py.
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
    assert "profile_image_url" in src, (
        "twitch_helix.py must reference 'profile_image_url' from the Helix response"
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
