import os

APP_ID = "org.example.MusicStreamer"
DATA_DIR = os.path.join(os.path.expanduser("~/.local/share"), "musicstreamer")
DB_PATH = os.path.join(DATA_DIR, "musicstreamer.sqlite3")
ASSETS_DIR = os.path.join(DATA_DIR, "assets")

# GStreamer playbin3 buffer tuning (Phase 16 / STREAM-01)
BUFFER_DURATION_S = 10                    # seconds; applied as BUFFER_DURATION_S * Gst.SECOND
BUFFER_SIZE_BYTES = 10 * 1024 * 1024      # 5 MB
