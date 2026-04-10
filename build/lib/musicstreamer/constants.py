import os

APP_ID = "org.example.MusicStreamer"
DATA_DIR = os.path.join(os.path.expanduser("~/.local/share"), "musicstreamer")
DB_PATH = os.path.join(DATA_DIR, "musicstreamer.sqlite3")
ASSETS_DIR = os.path.join(DATA_DIR, "assets")
