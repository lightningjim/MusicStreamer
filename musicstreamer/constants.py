import os

APP_ID = "org.example.MusicStreamer"
DATA_DIR = os.path.join(os.path.expanduser("~/.local/share"), "musicstreamer")
DB_PATH = os.path.join(DATA_DIR, "musicstreamer.sqlite3")
ASSETS_DIR = os.path.join(DATA_DIR, "assets")
COOKIES_PATH = os.path.join(DATA_DIR, "cookies.txt")


def clear_cookies() -> bool:
    """Delete cookies.txt if it exists. Returns True if file was removed."""
    if os.path.exists(COOKIES_PATH):
        os.remove(COOKIES_PATH)
        return True
    return False

# GStreamer playbin3 buffer tuning (Phase 16 / STREAM-01)
BUFFER_DURATION_S = 10                    # seconds; applied as BUFFER_DURATION_S * Gst.SECOND
BUFFER_SIZE_BYTES = 10 * 1024 * 1024      # 5 MB

# Quality tiers (Phase 27 / D-05)
QUALITY_PRESETS = ("hi", "med", "low")
QUALITY_SETTING_KEY = "preferred_quality"

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
