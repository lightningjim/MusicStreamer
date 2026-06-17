"""Twitch channel-avatar fetcher via the GQL endpoint (ART-AVATAR-04).

Public API:
    fetch_channel_avatar(url: str) -> bytes
        Fetches the channel's profileImageURL for a twitch.tv URL (or a bare
        login).  Raises on all failure modes; the caller (_AvatarFetchWorker)
        catches and emits an empty-path signal.

Why GQL, not Helix (89b UAT fix):
    The Phase 32 token in twitch-token.txt is the harvested web `auth-token`
    cookie, scoped to Twitch's web SPA client-id (kimne78...).  That client has
    only legacy v5/Kraken scopes and NO Helix access — api.twitch.tv/helix/users
    returns HTTP 404 for it.  The same credential DOES work against Twitch's GQL
    endpoint (gql.twitch.tv/gql), which is exactly what streamlink uses for
    playback.  We query `user(login).profileImageURL` there with the streamlink
    framing (Authorization: OAuth <token> + Client-Id).

Security (T-89b-01):
    - The auth token is read only from paths.twitch_token_path(); it is sent
      ONLY to https://gql.twitch.tv via the Authorization header on the GQL
      Request object.  It is never logged, printed, or attached to the CDN
      image download request.

Threading: plain synchronous function; called from _AvatarFetchWorker.run()
    (worker thread).  No Qt dependency.
"""
from __future__ import annotations

import json
import re
import urllib.request

from musicstreamer import paths

# Twitch's public web SPA client-id (oauth_helper.py header) — the client the
# auth-token cookie is scoped to, and the one GQL accepts.
_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"
_GQL_URL = "https://gql.twitch.tv/gql"
# Parameterised query — the login is bound as a GraphQL variable (never string
# interpolated), so a malformed login cannot alter the query (T-89b-02).
_GQL_QUERY = (
    "query($login:String!){user(login:$login){profileImageURL(width:300)}}"
)


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
        https://www.twitch.tv/user&client_id=x -> "user"
        twitchdev                         -> "twitchdev"
    """
    s = url_or_login.rstrip("/")
    if "/" in s:
        s = s.split("/")[-1]
    # Strip query string and fragment
    s = s.split("?")[0].split("#")[0].strip().lower()
    # Twitch logins are [a-z0-9_] only. Clamp to the leading valid run so a
    # malformed URL segment (e.g. "user&client_id=x") cannot leak into the
    # persisted "Twitch: <login>" provider name (WR-01 / T-89b-02). The GQL
    # query binds the login as a variable, so it is already injection-safe there.
    m = re.match(r"[a-z0-9_]+", s)
    return m.group(0) if m else ""


# ---------------------------------------------------------------------------
# Fetcher
# ---------------------------------------------------------------------------


def fetch_channel_avatar(url: str) -> bytes:
    """Fetch the Twitch channel's profileImageURL and return the image bytes.

    Args:
        url: A twitch.tv channel URL (e.g. https://www.twitch.tv/twitchdev)
             or a bare Twitch login string.

    Returns:
        Raw image bytes for the channel's profile picture.

    Raises:
        ValueError: login is empty, or GQL returned no user / no image.
        RuntimeError: twitch-token.txt is absent or empty (user not logged in).
        urllib.error.HTTPError: GQL returned a non-2xx status.
        urllib.error.URLError: network error.

    The caller (_AvatarFetchWorker.run()) wraps this in a try/except and emits
    an empty path on failure — do NOT add a top-level try/except here.
    """
    login = _parse_login(url)
    if not login:
        raise ValueError(f"Cannot derive Twitch login from: {url!r}")

    # Read the Phase 32 auth-token cookie from disk (same credential streamlink
    # uses for playback). GQL accepts it with the OAuth framing + web Client-Id.
    try:
        with open(paths.twitch_token_path()) as fh:
            token = fh.read().strip()
    except OSError:
        token = ""

    if not token:
        raise RuntimeError(
            "No Twitch login — connect via Accounts to fetch avatar"
        )

    # POST the GQL query. The login is bound as a variable (injection-safe).
    # Authorization is scoped to THIS Request object only — not a global opener
    # — and uses the OAuth framing the web client requires (T-89b-01 / Pitfall 5).
    payload = json.dumps(
        {"query": _GQL_QUERY, "variables": {"login": login}}
    ).encode()
    gql_req = urllib.request.Request(
        _GQL_URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"OAuth {token}",
            "Client-Id": _CLIENT_ID,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(gql_req, timeout=10) as resp:  # noqa: S310
        body = json.loads(resp.read())

    user = (body.get("data") or {}).get("user")
    image_url = user.get("profileImageURL") if user else None
    if not image_url:
        raise ValueError(f"No Twitch user/avatar found for login: {login!r}")

    # Twitch profile images are always square (300x300) — no non-square guard
    # needed (D-05).  Plain CDN download, no auth headers.
    with urllib.request.urlopen(image_url, timeout=10) as resp:  # noqa: S310
        return resp.read()
