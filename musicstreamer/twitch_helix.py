"""Twitch channel-avatar fetcher via the Helix /users endpoint (ART-AVATAR-04).

Public API:
    fetch_channel_avatar(url: str) -> bytes
        Fetches the profile_image_url for a Twitch channel given a twitch.tv URL
        (or a bare login).  Raises on all failure modes; the caller
        (_AvatarFetchWorker) catches and emits an empty-path signal.

Security (T-89b-01):
    - The auth token is read only from paths.twitch_token_path(); it is sent
      ONLY to https://api.twitch.tv via the Authorization: Bearer header on the
      Helix Request object.  It is never logged, printed, or attached to the
      CDN image download request.

Threading: plain synchronous function; called from _AvatarFetchWorker.run()
    (worker thread).  No Qt dependency.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from musicstreamer import paths

# Twitch's public web SPA client-id (D-06 / oauth_helper.py header).
_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"
_HELIX_USERS_URL = "https://api.twitch.tv/helix/users?login={login}"


# ---------------------------------------------------------------------------
# Login parse helper
# ---------------------------------------------------------------------------


def _parse_login(url_or_login: str) -> str:
    """Derive the Twitch login from a twitch.tv URL or bare login string.

    Handles: trailing slash, query string (?ref=...), fragment (#...), mixed
    case, and bare logins (no slash).

    Examples:
        https://www.twitch.tv/twitchdev   -> "twitchdev"
        https://www.twitch.tv/twitchdev/  -> "twitchdev"
        https://www.twitch.tv/TwitchDev   -> "twitchdev"
        https://www.twitch.tv/twitchdev?ref=header -> "twitchdev"
        https://www.twitch.tv/twitchdev#x -> "twitchdev"
        twitchdev                         -> "twitchdev"
    """
    s = url_or_login.rstrip("/")
    if "/" in s:
        s = s.split("/")[-1]
    # Strip query string and fragment
    s = s.split("?")[0].split("#")[0].strip()
    return s.lower()


# ---------------------------------------------------------------------------
# Fetcher
# ---------------------------------------------------------------------------


def fetch_channel_avatar(url: str) -> bytes:
    """Fetch the Twitch channel's profile_image_url and return the image bytes.

    Args:
        url: A twitch.tv channel URL (e.g. https://www.twitch.tv/twitchdev)
             or a bare Twitch login string.

    Returns:
        Raw image bytes for the channel's profile picture.

    Raises:
        ValueError: login is empty, or Helix returned data:[].
        RuntimeError: twitch-token.txt is absent or empty (user not logged in).
        urllib.error.HTTPError: Helix returned a non-2xx status (e.g. 401).
        urllib.error.URLError: network error.

    The caller (_AvatarFetchWorker.run()) wraps this in a try/except and emits
    an empty path on failure — do NOT add a top-level try/except here (WR-01).
    """
    login = _parse_login(url)
    if not login:
        raise ValueError(f"Cannot derive Twitch login from: {url!r}")

    # Read the Phase 32 auth-token cookie from disk (same credential streamlink uses;
    # Helix requires Bearer framing + Client-Id — D-06).
    try:
        with open(paths.twitch_token_path()) as fh:
            token = fh.read().strip()
    except OSError:
        token = ""

    if not token:
        raise RuntimeError(
            "No Twitch login — connect via Accounts to fetch avatar"
        )

    # Build the Helix /users request — Authorization scoped to this Request object
    # only, NOT a global opener (T-89b-01 / Pitfall 5).
    helix_req = urllib.request.Request(
        _HELIX_USERS_URL.format(login=login),
        headers={
            "Authorization": f"Bearer {token}",
            "Client-Id": _CLIENT_ID,
        },
    )
    with urllib.request.urlopen(helix_req, timeout=10) as resp:  # noqa: S310
        body = json.loads(resp.read())

    data = body.get("data", [])
    if not data:
        raise ValueError(f"No Twitch user found for login: {login!r}")

    image_url = data[0]["profile_image_url"]

    # Twitch profile images are always square (300x300) — no non-square guard
    # needed (D-05 / RESEARCH Finding #3).  Plain CDN download, no auth headers.
    with urllib.request.urlopen(image_url, timeout=10) as resp:  # noqa: S310
        return resp.read()
