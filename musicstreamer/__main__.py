"""Phase 36 Qt entry point. Default path opens QApplication + MainWindow.
``--smoke URL`` preserves the Phase 35 headless backend harness.
"""
from __future__ import annotations

import argparse
import logging
import sys
from importlib.metadata import version as _pkg_version

import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst

from musicstreamer import constants

DEFAULT_SMOKE_URL = "https://ice1.somafm.com/groovesalad-128-mp3"


def _run_check_mediakeys(argv: list[str]) -> int:
    """Phase 88.1 D-05: headless SMTC backend identity check.

    Constructs the media_keys factory under QCoreApplication (not QApplication —
    headless build machines have no display; QApplication crashes without one).
    Does NOT import ui_qt (D-05/D-24 lazy-import contract).

    Prints MEDIAKEYS_BACKEND=<classname> to stderr (WR-01: the frozen bundle is
    built console=False, so stdout is a no-op; stderr still reaches build.ps1's
    `2>&1 | Out-Host`, keeping the diagnostic visible). The exit code (0/1) is the
    actual contract the build.ps1 step-4c guard branches on.
    Exits 0 if WindowsMediaKeysBackend is constructed, 1 if NoOp or error.
    """
    from PySide6.QtCore import QCoreApplication

    from musicstreamer import media_keys

    app = QCoreApplication(argv)  # noqa: F841 — required for Qt init

    backend = media_keys.create(None, None)
    class_name = type(backend).__name__
    print(f"MEDIAKEYS_BACKEND={class_name}", file=sys.stderr, flush=True)

    if class_name == "WindowsMediaKeysBackend":
        return 0
    return 1


def _run_oauth_helper(argv: list[str]) -> int:
    """Phase 88.2 D-05: frozen-exe re-exec entry for the login helper.

    Dispatched from main() when ``--oauth-helper`` is present in argv,
    BEFORE ``_run_gui`` so no QApplication is constructed here.

    Modes:
    - ``--self-test``: exits 0 immediately (headless smoke guard for
      build.ps1 step 4d, exit code 12). No QApplication, no window.
    - Any other ``--oauth-helper`` invocation in the conda bundle is a
      bug. Under B1 the conda ``MusicStreamer.exe`` ships NO WebEngine and
      launches the separate ``oauth_helper.exe`` out-of-process via QProcess
      (``_make_oauth_launch_args``). It must NEVER import/run the WebEngine
      helper in-process — doing so triggers oauth_helper's module-level
      QtWebEngineWidgets import, which is absent in the conda bundle and
      bare ``sys.exit(2)``s from the wrong process with no diagnostic
      (Phase 88.3 WR-02). So this arm now emits a clear error and returns 2.
    """
    if "--self-test" in argv:
        return 0
    # B1: the conda exe must NEVER run the WebEngine helper in-process. It
    # launches the separate oauth_helper.exe via QProcess. Any other
    # --oauth-helper invocation reaching here is a bug (Phase 88.3 WR-02).
    print(
        "ERROR: --oauth-helper in-process dispatch is not supported in the "
        "conda bundle (B1: use the separate oauth_helper.exe launched via "
        "QProcess by _make_oauth_launch_args).",
        file=sys.stderr,
        flush=True,
    )
    return 2


def _run_smoke(argv: list[str], url: str) -> int:
    """Phase 35 headless smoke harness — QCoreApplication + Player only.

    Does NOT import ui_qt (D-05, D-24). Kept intact so backend regression
    checks stay cheap during Phase 37+ UI development.
    """
    from PySide6.QtCore import QCoreApplication, QTimer

    from musicstreamer import migration
    from musicstreamer.models import Station, StationStream
    from musicstreamer.player import Player
    from musicstreamer.repo import db_connect, db_init, sweep_orphans

    # GStreamer must be initialized before any pipeline construction.
    Gst.init(None)

    # PORT-06: first-launch data migration (no-op on Linux, writes marker).
    migration.run_migration()

    # Phase 80 / BUG-10 WR-01: parity with _run_gui — route the smoke
    # harness through db_connect() + sweep_orphans() so --smoke exercises
    # the same FK-PRAGMA + ghost-row healing invariants as --gui. The
    # smoke harness itself does not read the DB, but running the factory
    # here keeps `python -m musicstreamer --smoke ...` behaving identically
    # to `--gui` w.r.t. BUG-10 sweep semantics and the PRAGMA drift-guard.
    con = db_connect()
    db_init(con)
    sweep_orphans(con)
    con.close()

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


def _set_windows_aumid(app_id: str | None = None) -> None:
    """Set the Windows AppUserModelID so the SMTC overlay + taskbar group
    under the app's own identity instead of 'Unknown app' / python.exe.

    Must be called BEFORE QApplication is constructed -- Windows binds the
    process AUMID at first window creation. No-op off Windows.

    AUMID -> friendly display name mapping requires a registered Start Menu
    shortcut that carries the same AUMID (System.AppUserModel.ID property).
    Without it the shell falls back to a generic label even when the AUMID
    is correctly set on the process. Shortcut registration lands in the
    Phase 44 installer; for Phase 43.1 we only guarantee the AUMID value
    is correct (verified by the readback below).

    Phase 61 / D-02: app_id default is None; reads constants.APP_ID when
    unspecified so the Linux app id and the Windows AUMID share a single
    source of truth.
    """
    if app_id is None:
        app_id = constants.APP_ID
    if sys.platform != "win32":
        return
    import ctypes
    from ctypes import wintypes

    shell32 = ctypes.windll.shell32
    # Explicit LPCWSTR signature -- default ctypes marshaling can pass
    # Python str as a narrow (A) pointer on some CPython builds; this
    # Win32 call only accepts wide strings. Readback confirmed via
    # GetCurrentProcessExplicitAppUserModelID during 43.1 UAT.
    shell32.SetCurrentProcessExplicitAppUserModelID.argtypes = [wintypes.LPCWSTR]
    shell32.SetCurrentProcessExplicitAppUserModelID.restype = ctypes.HRESULT
    shell32.SetCurrentProcessExplicitAppUserModelID(app_id)


def _strip_inherited_activation_tokens() -> None:
    """Pop XDG_ACTIVATION_TOKEN + DESKTOP_STARTUP_ID from our env.

    Phase 61 follow-up to BUG-08 (Plan 04 UAT FAIL → Plan 05 fix).

    When MusicStreamer is launched from a parent process that exports a
    wayland activation token (notably JetBrains terminals, which export
    XDG_ACTIVATION_TOKEN/DESKTOP_STARTUP_ID into every child shell),
    Qt's wayland plugin forwards that stale token to mutter via
    ``xdg_activation_v1.activate(<token>, <our first surface>)``. Mutter
    then binds our surface to the parent's launch context, which
    short-circuits the wayland-app-id → .desktop basename match and
    leaves us with a generic gear icon + raw app_id in the dock and
    force-quit dialog (BUG-08 symptom).

    The freedesktop xdg-activation-v1 spec scopes a token to a single
    launch event; carrying it across an unrelated process boundary is
    already a misuse by the launcher. We refuse to forward a token we
    did not earn. No-op on platforms that don't set these (Windows /
    macOS / well-behaved Linux launchers).
    """
    import os
    os.environ.pop("XDG_ACTIVATION_TOKEN", None)
    os.environ.pop("DESKTOP_STARTUP_ID", None)


def _run_gui(argv: list[str]) -> int:
    """Open the Qt GUI — QApplication + MainWindow."""
    _strip_inherited_activation_tokens()  # Phase 61 Plan 05: BUG-08 follow-up
    _set_windows_aumid()  # Phase 43.1: before QApplication (binds on first window)
    Gst.init(None)

    # Phase 61 / D-09: first-launch self-install of .desktop + icon for
    # Linux WM display-name resolution (BUG-08). No-op on non-Linux.
    # Runs BEFORE QApplication so the very first window emits a
    # _GTK_APPLICATION_ID that has a matching .desktop in the XDG path.
    from musicstreamer import desktop_install
    desktop_install.ensure_installed()

    from musicstreamer import migration
    migration.run_migration()

    # Phase 78 / BUG-09 Commit A: install rotating file handler on the
    # musicstreamer.player logger so buffer_underrun lines also land at
    # ~/.local/share/musicstreamer/buffer-events.log regardless of launch
    # context (.desktop vs terminal). MUST run AFTER migration.run_migration()
    # so DATA_DIR exists (Pitfall 1 — RotatingFileHandler opens eagerly). The
    # install function is idempotent so re-entry / hot-reload is safe. The
    # named-logger attach preserves Pitfall 5 (basicConfig WARNING is global
    # and stays untouched at __main__.py line 231).
    from musicstreamer.buffer_log import install_buffer_events_handler
    install_buffer_events_handler()

    # Phase 90 / SOMA-PRE-01: install rotating file handler on the
    # musicstreamer.preroll logger so preroll gate INFO lines also land at
    # ~/.local/share/musicstreamer/preroll-events.log regardless of launch
    # context (.desktop vs terminal). MUST run AFTER migration.run_migration()
    # so DATA_DIR exists (Pitfall 1 — RotatingFileHandler opens eagerly). The
    # install function is idempotent so re-entry / hot-reload is safe.
    from musicstreamer.preroll_log import install_preroll_events_handler
    install_preroll_events_handler()

    from PySide6.QtWidgets import QApplication
    from musicstreamer.ui_qt import icons_rc  # noqa: F401  (D-24 side-effect resource import)
    from musicstreamer.ui_qt.main_window import MainWindow
    from musicstreamer.player import Player
    from musicstreamer.repo import Repo, db_connect, db_init, sweep_orphans

    app = QApplication(argv)
    app.setApplicationName("MusicStreamer")              # D-07: keep
    app.setApplicationDisplayName("MusicStreamer")       # D-06: NEW (Phase 61)
    app.setApplicationVersion(_pkg_version("musicstreamer"))  # Phase 65 D-07
    app.setDesktopFileName(constants.APP_ID)             # D-02: read from constants (no .desktop suffix per Qt convention)

    # Phase 66 / THEME-01: theme palette FIRST, before MainWindow construction.
    # The existing accent_color restore in main_window.py:241-245 layers on top.
    # Pitfall 5 (RESEARCH): db_connect must be hoisted from below to here so the
    # same repo instance is reused for theme + MainWindow (single connection).
    # The win32 setStyle("Fusion") + _apply_windows_palette branch is now
    # invoked from inside theme.apply_theme_palette when theme=='system' on Windows.
    con = db_connect()
    db_init(con)
    # Phase 80 / BUG-10 D-02: heal orphans left by manual sqlite3-shell DELETEs
    # (Phase 74 F-07-03 Synphaera ghosts). Same con — no second connection.
    # D-03: runs unconditionally every app start; sub-millisecond no-op when N=0.
    sweep_orphans(con)
    repo = Repo(con)
    from musicstreamer import theme
    theme.apply_theme_palette(app, repo)

    # D-10: single-instance BEFORE MainWindow construction (after QApplication).
    # ORDER REQUIRED — QLocalServer needs the event loop; MainWindow must not be
    # constructed if another instance already owns the lock.
    from musicstreamer import single_instance  # lazy
    server = single_instance.acquire_or_forward()
    if server is None:
        return 0  # second instance forwarded — exit cleanly

    # D-11/D-12: Node.js detection BEFORE MainWindow so node_runtime can be passed
    # as kwarg, and AFTER single-instance so a forwarded second invocation never
    # shows the dialog.
    from musicstreamer import runtime_check  # lazy
    node_runtime = runtime_check.check_node()
    if not node_runtime.available:
        runtime_check.show_missing_node_dialog(parent=None)

    # con / db_init / repo already constructed above (Phase 66 hoist for theme).
    player = Player(node_runtime=node_runtime)

    window = MainWindow(player, repo, node_runtime=node_runtime)
    server.activate_requested.connect(  # parameter-only lambda — captures `window`, not self
        lambda: single_instance.raise_and_focus(window)
    )
    window.show()

    # Phase 86.1 Plan 02: offer the FlatpakImportWizard on first sandboxed launch
    # with existing host data.  Gates on BOTH is_sandboxed() (Plan 01 helper —
    # prevents firing on native Linux where host path == sandbox path) AND
    # should_offer_import_wizard() (host-data-present + offer-once-flag-absent).
    # Deferred via QTimer.singleShot(0, ...) so the modal renders OVER the shown
    # main window, not before it.  All imports are lazy (consistent with the
    # existing lazy-import style above) to keep _run_smoke Qt-light and ui_qt-free
    # (D-05/D-24).
    def _maybe_offer_import() -> None:
        from musicstreamer import flatpak_first_launch  # lazy
        from musicstreamer import paths  # lazy
        from musicstreamer.ui_qt.flatpak_import_wizard import FlatpakImportWizard  # lazy

        if flatpak_first_launch.is_sandboxed() and flatpak_first_launch.should_offer_import_wizard():
            wizard = FlatpakImportWizard(
                paths.db_path(),
                toast_callback=window.show_toast,
                parent=window,
            )
            wizard.exec()

    from PySide6.QtCore import QTimer  # lazy
    QTimer.singleShot(0, _maybe_offer_import)

    return app.exec()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING)
    # Phase 62 / BUG-09 / Pitfall 5: per-logger INFO level for musicstreamer.player
    # so buffer-underrun cycle close lines surface to stderr without bumping the
    # GLOBAL level (which would surface chatter from aa_import / gbs_api / mpris2).
    logging.getLogger("musicstreamer.player").setLevel(logging.INFO)
    logging.getLogger("musicstreamer.soma_import").setLevel(logging.INFO)
    # Phase 79 / BUG-11: surface scan_playlist node_path INFO line at default
    # verbosity (consumed by Plan 79-03's yt_import.scan_playlist INFO log).
    logging.getLogger("musicstreamer.yt_import").setLevel(logging.INFO)
    # Phase 80 / BUG-10: surface sweep_orphans INFO line + PRAGMA drift WARN
    # line without bumping the global level. sweep_orphans is silent on N=0
    # (D-04) so steady-state output is unchanged; the line appears only when
    # the sweep actually removed at least one orphan row.
    logging.getLogger("musicstreamer.repo").setLevel(logging.INFO)
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
    parser.add_argument(
        "--check-mediakeys",
        action="store_true",
        default=False,
        help=(
            "Phase 88.1 D-05: headless SMTC backend identity check. "
            "Prints MEDIAKEYS_BACKEND=<classname>; exits 0 if WindowsMediaKeysBackend, "
            "1 if NoOp. Used by build.ps1 SMTC smoke guard."
        ),
    )
    parser.add_argument(
        "--oauth-helper",
        action="store_true",
        default=False,
        help=(
            "Phase 88.2 D-05: frozen-exe re-exec entry for login helper. "
            "Routes argv to oauth_helper.main() before GUI builds. "
            "Pass --self-test for a headless smoke guard (exits 0, no window)."
        ),
    )
    # parse_known_args: let Qt consume its own flags (-platform, -style, etc.)
    args, qt_argv = parser.parse_known_args(argv[1:])
    remaining = [argv[0], *qt_argv]

    if args.oauth_helper:
        return _run_oauth_helper(remaining)
    if args.check_mediakeys:
        return _run_check_mediakeys(remaining)
    if args.smoke is not None:
        return _run_smoke(remaining, args.smoke)
    return _run_gui(remaining)


if __name__ == "__main__":
    sys.exit(main())
