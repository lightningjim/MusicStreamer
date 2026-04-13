"""Phase 36 Qt entry point. Default path opens QApplication + MainWindow.
``--smoke URL`` preserves the Phase 35 headless backend harness.
"""
from __future__ import annotations

import argparse
import sys

import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst

DEFAULT_SMOKE_URL = "https://ice1.somafm.com/groovesalad-128-mp3"


def _run_smoke(argv: list[str], url: str) -> int:
    """Phase 35 headless smoke harness — QCoreApplication + Player only.

    Does NOT import ui_qt (D-05, D-24). Kept intact so backend regression
    checks stay cheap during Phase 37+ UI development.
    """
    from PySide6.QtCore import QCoreApplication, QTimer

    from musicstreamer import migration
    from musicstreamer.models import Station, StationStream
    from musicstreamer.player import Player

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


def _apply_windows_palette(app) -> None:
    """Apply the canonical dark Fusion palette on Windows dark mode (D-15).

    No-op in light mode (light Fusion is acceptable per D-15). Never called
    on Linux — the ``sys.platform == "win32"`` gate in ``_run_gui`` is the
    single PORT-07 branch point.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QGuiApplication, QPalette

    hints = QGuiApplication.styleHints()
    if hints.colorScheme() != Qt.ColorScheme.Dark:
        return  # light Fusion is fine as-is

    p = QPalette()
    p.setColor(QPalette.Window, QColor(53, 53, 53))
    p.setColor(QPalette.WindowText, Qt.white)
    p.setColor(QPalette.Base, QColor(25, 25, 25))
    p.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    p.setColor(QPalette.ToolTipBase, Qt.white)
    p.setColor(QPalette.ToolTipText, Qt.white)
    p.setColor(QPalette.Text, Qt.white)
    p.setColor(QPalette.Button, QColor(53, 53, 53))
    p.setColor(QPalette.ButtonText, Qt.white)
    p.setColor(QPalette.BrightText, Qt.red)
    p.setColor(QPalette.Link, QColor(42, 130, 218))
    p.setColor(QPalette.Highlight, QColor(42, 130, 218))
    p.setColor(QPalette.HighlightedText, Qt.black)
    p.setColor(QPalette.Disabled, QPalette.Text, QColor(127, 127, 127))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(127, 127, 127))
    app.setPalette(p)


def _run_gui(argv: list[str]) -> int:
    """Open the Qt GUI — QApplication + MainWindow."""
    Gst.init(None)

    from musicstreamer import migration
    migration.run_migration()

    from PySide6.QtWidgets import QApplication
    from musicstreamer.ui_qt import icons_rc  # noqa: F401  (D-24 side-effect resource import)
    from musicstreamer.ui_qt.main_window import MainWindow
    from musicstreamer.player import Player
    from musicstreamer.repo import Repo, db_connect, db_init

    app = QApplication(argv)
    app.setApplicationName("MusicStreamer")
    app.setDesktopFileName("org.example.MusicStreamer")
    if sys.platform == "win32":
        app.setStyle("Fusion")          # D-14: BEFORE widget construction
        _apply_windows_palette(app)     # D-15: dark-mode palette if applicable

    con = db_connect()
    db_init(con)
    player = Player()
    repo = Repo(con)

    window = MainWindow(player, repo)
    window.show()
    return app.exec()


def main(argv: list[str] | None = None) -> int:
    argv = list(argv) if argv is not None else list(sys.argv)

    parser = argparse.ArgumentParser(
        prog="musicstreamer",
        description="Internet radio stream player",
    )
    parser.add_argument(
        "--smoke",
        metavar="URL",
        nargs="?",
        const=DEFAULT_SMOKE_URL,
        help="Run headless Phase 35 backend harness with the given (or default) stream URL",
    )
    # parse_known_args: let Qt consume its own flags (-platform, -style, etc.)
    args, qt_argv = parser.parse_known_args(argv[1:])
    remaining = [argv[0], *qt_argv]

    if args.smoke is not None:
        return _run_smoke(remaining, args.smoke)
    return _run_gui(remaining)


if __name__ == "__main__":
    sys.exit(main())
