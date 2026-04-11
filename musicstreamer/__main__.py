"""Phase 35 headless entry — QCoreApplication + Player only.

Success Criterion #1: ``python -m musicstreamer <stream_url>`` plays the
stream via GStreamer and prints ICY titles to stdout.

Phase 36 will replace this with a QApplication + QMainWindow entry point.
The old GTK entry (``main.py``) stays on disk until Phase 36 deletes it
per PORT-04 / D-06.
"""
from __future__ import annotations

import sys

import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst
from PySide6.QtCore import QCoreApplication, QTimer

from musicstreamer import migration
from musicstreamer.models import Station, StationStream
from musicstreamer.player import Player

DEFAULT_SMOKE_URL = "https://ice1.somafm.com/groovesalad-128-mp3"


def main(argv: list[str] | None = None) -> int:
    argv = list(argv) if argv is not None else list(sys.argv)

    # GStreamer must be initialized before any pipeline construction.
    Gst.init(None)

    # PORT-06: first-launch data migration (no-op on Linux, writes marker).
    migration.run_migration()

    app = QCoreApplication(argv)
    player = Player()

    player.title_changed.connect(lambda t: print(f"ICY: {t}", flush=True))
    player.playback_error.connect(lambda m: print(f"ERROR: {m}", flush=True))
    player.failover.connect(
        lambda s: print(
            f"FAILOVER: {'exhausted' if s is None else s.url}", flush=True
        )
    )
    player.offline.connect(lambda ch: print(f"OFFLINE: {ch}", flush=True))

    url = argv[1] if len(argv) > 1 else DEFAULT_SMOKE_URL
    stream = StationStream(
        id=0, station_id=0, url=url, quality="hi", position=0
    )
    station = Station(
        id=0,
        name="Smoke Test",
        provider_id=None,
        provider_name=None,
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        streams=[stream],
    )

    # Kick off AFTER the event loop starts so queued signal connections are live.
    QTimer.singleShot(0, lambda: player.play(station))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
