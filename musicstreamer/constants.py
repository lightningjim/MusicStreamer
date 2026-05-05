"""Application-wide constants.

Data-path constants (DATA_DIR, DB_PATH, ASSETS_DIR, COOKIES_PATH,
TWITCH_TOKEN_PATH) are exposed via PEP 562 ``__getattr__`` so they delegate
to ``musicstreamer.paths`` on every access. This is intentional — assigning
them as plain module-level attributes would snapshot the path once at import
time and break the ``paths._root_override`` test hook.

New code should import from ``musicstreamer.paths`` directly. The
``__getattr__`` shim exists only to keep existing call sites working without
churn during the Phase 35 backend isolation.
"""
import os

from musicstreamer import paths

APP_ID = "org.lightningjim.MusicStreamer"


def __getattr__(name):
    if name == "DATA_DIR":
        return paths.data_dir()
    if name == "DB_PATH":
        return paths.db_path()
    if name == "ASSETS_DIR":
        return paths.assets_dir()
    if name == "COOKIES_PATH":
        return paths.cookies_path()
    if name == "TWITCH_TOKEN_PATH":
        return paths.twitch_token_path()
    raise AttributeError(
        f"module 'musicstreamer.constants' has no attribute {name!r}"
    )


def clear_cookies() -> bool:
    """Delete cookies.txt if it exists. Returns True if file was removed."""
    p = paths.cookies_path()
    if os.path.exists(p):
        os.remove(p)
        return True
    return False


def clear_twitch_token() -> bool:
    """Delete twitch-token.txt if it exists. Returns True if file was removed."""
    p = paths.twitch_token_path()
    if os.path.exists(p):
        os.remove(p)
        return True
    return False


# GStreamer playbin3 buffer tuning (Phase 16 / STREAM-01)
BUFFER_DURATION_S = 10                    # seconds; applied as BUFFER_DURATION_S * Gst.SECOND
BUFFER_SIZE_BYTES = 10 * 1024 * 1024      # 5 MB

# YouTube mpv minimum wait window before failover (Phase 33 / FIX-07 / D-01)
YT_MIN_WAIT_S = 15

# Quality tiers (Phase 27 / D-05)
QUALITY_PRESETS = ("hi", "med", "low")
QUALITY_SETTING_KEY = "preferred_quality"

# Twitch login (Phase 999.3 pivot — cookie-harvest from twitch.tv web session).
# The OAuth-redirect approach was abandoned: the piggyback web client_id has
# redirect_uri whitelisting we cannot bypass. Instead, we harvest the auth-token
# cookie that twitch.tv sets after login — the same token streamlink's GQL
# endpoint accepts.
TWITCH_LOGIN_URL = "https://www.twitch.tv/login"

# Accent color (Phase 19 / ACCENT-01)
ACCENT_COLOR_DEFAULT = "#3584e4"
ACCENT_PRESETS = [
    "#3584e4",  # Blue (default)
    "#2190a4",  # Teal
    "#3a944a",  # Green
    "#c88800",  # Yellow
    "#ed5b00",  # Orange
    "#e62d42",  # Red
    "#9141ac",  # Purple
    "#c64d92",  # Pink
]
