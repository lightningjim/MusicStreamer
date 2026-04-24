"""Windows SMTC media-keys backend (Phase 43.1, MEDIA-03/04/05).

Implements the Windows leaf of the musicstreamer.media_keys factory using
winrt-Windows.Media.Playback. The abstract base class, signal surface,
cover-art PNG helper, and MainWindow wiring were all built in Phase 41
-- this module replaces the NotImplementedError stub.

Import guard contract (CONTEXT D-06):
  All winrt imports live inside function/method bodies. Module scope is
  pure Python so the file stays importable on Linux for test discovery
  and factory introspection.

Failure fallback contract (CONTEXT D-07):
  If winrt wheels are not installed, `create_windows_backend` raises
  ImportError which the outer factory in media_keys/__init__.py catches
  and degrades to NoOpMediaKeysBackend -- app startup never blocks.

winrt namespace layout (pywinrt 3.2.x):
  winrt.windows.media.playback  -- MediaPlayer
  winrt.windows.media           -- MediaPlaybackStatus, MediaPlaybackType,
                                   SystemMediaTransportControls,
                                   SystemMediaTransportControlsButton
  winrt.windows.storage.streams -- InMemoryRandomAccessStream, DataWriter,
                                   RandomAccessStreamReference

Threading (D-02):
  button_pressed callbacks run on a winrt threadpool thread. Qt signal
  emits from this thread auto-queue to the main thread via queued
  connection semantics because WindowsMediaKeysBackend (a QObject) was
  constructed on the main thread. No QMetaObject.invokeMethod needed.

Installation: `pip install -e ".[windows]"` inside the conda-forge
Windows env (see .planning/phases/43-gstreamer-windows-spike/43-SPIKE-FINDINGS.md
and .claude/skills/spike-findings-musicstreamer/SKILL.md).
"""
from __future__ import annotations

import asyncio
import logging

from musicstreamer.media_keys._art_cache import write_cover_png
from musicstreamer.media_keys.base import MediaKeysBackend

_log = logging.getLogger(__name__)

_INSTALL_HINT = (
    "Windows media keys unavailable -- install with "
    '`pip install -e ".[windows]"` inside the Windows env.'
)


async def _await_store(writer) -> None:
    """Await DataWriter.store_async() without blocking the STA main thread.

    winrt IAsyncOperation instances implement __await__, completing on a
    winrt threadpool thread. asyncio.run drives a fresh event loop around
    this single await, which is safe to call from the Qt main thread because
    asyncio.run never re-enters Qt's loop. 43.1 UAT resolution of Pitfall #3.
    """
    await writer.store_async()


class WindowsMediaKeysBackend(MediaKeysBackend):
    """Windows SMTC media-keys backend (Phase 43.1 MEDIA-03/04/05).

    Uses winrt-Windows.Media.Playback.MediaPlayer as a conduit to the
    SystemMediaTransportControls session. The MediaPlayer's audio engine
    is NOT used -- GStreamer still owns playback. SMTC is purely the OS
    media-session integration surface.

    Threading (D-02): winrt button_pressed callbacks run on a winrt
    threadpool thread. Qt signal emits from this thread auto-queue to the
    main thread via queued connection semantics. No QMetaObject.invokeMethod
    needed.
    """

    def __init__(self, player, repo, parent=None) -> None:
        super().__init__(parent)
        self._player = player
        self._repo = repo

        # Internal state (Plan 04 populates metadata)
        self._state: str = "stopped"
        self._station = None
        self._title: str = ""

        # D-06: deferred winrt imports (function body only -- keeps module Linux-importable)
        from winrt.windows.media.playback import MediaPlayer  # noqa: PLC0415
        from winrt.windows.media import (  # noqa: PLC0415
            MediaPlaybackStatus,
            MediaPlaybackType,
            SystemMediaTransportControlsButton,
        )

        self._media_player = MediaPlayer()
        self._smtc = self._media_player.system_media_transport_controls

        # Pitfall #1 (MANDATORY): disable MediaPlayer's auto-command routing BEFORE
        # subscribing to button_pressed. Without this, the handler never fires because
        # MediaPlayer intercepts buttons internally via its CommandManager.
        self._media_player.command_manager.is_enabled = False

        # Enable only the buttons we handle (CONTEXT D-01); next/previous disabled
        # because MusicStreamer has no queue concept (Phase 41 decision).
        self._smtc.is_play_enabled = True
        self._smtc.is_pause_enabled = True
        self._smtc.is_stop_enabled = True
        self._smtc.is_next_enabled = False
        self._smtc.is_previous_enabled = False

        # Cache enum refs for hot-path callback (avoids re-import on each call).
        # Must be set BEFORE the WR-03 placeholder seed below, which uses
        # self._type_enum.MUSIC.
        self._button_enum = SystemMediaTransportControlsButton
        self._status_enum = MediaPlaybackStatus
        self._type_enum = MediaPlaybackType  # consumed in Plan 04 (publish_metadata)

        # WR-03 (43.1 review): seed a neutral placeholder BEFORE enabling the
        # session, so the Win+V overlay never shows a blank "MusicStreamer"
        # entry with empty title/artist in the window between app launch and
        # the first publish_metadata() call. publish_metadata() overwrites
        # these values when a station is selected.
        du = self._smtc.display_updater
        du.type = self._type_enum.MUSIC
        du.music_properties.title = "MusicStreamer"
        du.music_properties.artist = "Idle"
        du.update()

        # UAT-discovered 2026-04-21 (Pitfall #7): must explicitly enable the SMTC
        # session -- default `is_enabled` is False, which means the session is
        # created but hidden from the Win+V media overlay. Without this flag,
        # buttons + metadata are configured but invisible to the user.
        self._smtc.is_enabled = True

        # Pitfall #4: store the token -- shutdown needs it for remove_button_pressed.
        self._bp_token = self._smtc.add_button_pressed(self._on_button_pressed)
        self._shutdown_complete: bool = False

        _log.debug("WindowsMediaKeysBackend initialized (SMTC session active)")

    def _on_button_pressed(self, sender, args) -> None:
        """SMTC button callback -- runs on winrt threadpool thread (D-02).

        T-43.1-04: wrap entire body in try/except so any exception does not
        poison the winrt threadpool. Log at WARNING and swallow.
        """
        try:
            btn = args.button
            if btn == self._button_enum.PLAY:
                self.play_pause_requested.emit()
            elif btn == self._button_enum.PAUSE:
                self.play_pause_requested.emit()
            elif btn == self._button_enum.STOP:
                self.stop_requested.emit()
            else:
                _log.debug("SMTC button %r not handled", btn)
        except Exception as exc:
            _log.warning("SMTC button handler raised: %s", exc, exc_info=True)

    def _apply_playback_state(self, state) -> None:
        """D-10: map Literal state -> MediaPlaybackStatus enum.

        Base class has already validated `state` is one of
        {"playing", "paused", "stopped"} before calling this hook.
        """
        status_map = {
            "playing": self._status_enum.PLAYING,
            "paused":  self._status_enum.PAUSED,
            "stopped": self._status_enum.STOPPED,
        }
        self._smtc.playback_status = status_map[state]
        self._state = state

    def publish_metadata(self, station, title, cover_pixmap) -> None:
        """Publish station + ICY title + cover art to SMTC DisplayUpdater (D-08).

        D-03 revised (Pitfall #2): thumbnail delivery uses
        InMemoryRandomAccessStream, NOT `create_from_uri("file://...")` --
        file:// is not a valid URI scheme for
        RandomAccessStreamReference.create_from_uri (only
        http/https/ms-appx/ms-appdata).
        """
        # D-06: deferred winrt imports (function body only)
        from winrt.windows.storage.streams import (  # noqa: PLC0415
            InMemoryRandomAccessStream,
            DataWriter,
            RandomAccessStreamReference,
        )

        self._station = station
        self._title = title or ""

        du = self._smtc.display_updater
        du.type = self._type_enum.MUSIC  # D-08

        if station is None:
            du.music_properties.title = ""
            du.music_properties.artist = ""
            du.thumbnail = None
        else:
            du.music_properties.title = self._title or station.name
            du.music_properties.artist = station.name
            du.thumbnail = self._build_thumbnail_ref(
                cover_pixmap, station.id,
                InMemoryRandomAccessStream, DataWriter, RandomAccessStreamReference,
            )

        du.update()  # D-08: single batched update per publish_metadata

    def _build_thumbnail_ref(
        self,
        cover_pixmap,
        station_id,
        InMemoryRandomAccessStream,
        DataWriter,
        RandomAccessStreamReference,
    ):
        """Wrap the cached PNG bytes in a RandomAccessStreamReference, or None on failure.

        D-03 revised: uses InMemoryRandomAccessStream + DataWriter instead of
        create_from_uri (Pitfall #2 -- file:// URIs rejected).
        Pitfall #3: store_async().get() is the synchronous path; if it
        deadlocks on Qt's STA main thread, Plan 06 UAT surfaces it and
        a follow-up can pivot to asyncio.run().
        """
        if cover_pixmap is None:
            return None

        path = write_cover_png(cover_pixmap, station_id)
        if not path:
            return None

        try:
            with open(path, "rb") as f:
                data = f.read()
            stream = InMemoryRandomAccessStream()
            writer = DataWriter(stream)
            writer.write_bytes(data)
            # 43.1 UAT finding (Pitfall #3 resolved): store_async().get() raises
            # "Cannot call blocking method from single-threaded apartment" on
            # Qt's STA main thread. Drive the IAsyncOperation with asyncio.run
            # instead -- winrt IAsyncOperation objects implement __await__ and
            # complete on a winrt threadpool thread, bypassing STA re-entry.
            # WR-01 (43.1 review): asyncio.run() raises if a loop is already
            # running in this thread. Qt's main loop is not asyncio today, but
            # future qasync/qtinter bridges would make this path fail silently.
            # Detect a running loop and schedule threadsafely as a fallback.
            try:
                running_loop = asyncio.get_running_loop()
            except RuntimeError:
                running_loop = None

            if running_loop is None:
                asyncio.run(_await_store(writer))
            else:
                fut = asyncio.run_coroutine_threadsafe(
                    _await_store(writer), running_loop
                )
                fut.result(timeout=5.0)
            # DataWriter owns the underlying stream until detach_stream() --
            # RandomAccessStreamReference readers get an unreadable stream
            # otherwise, which reads as "thumbnail missing" in SMTC overlay.
            writer.detach_stream()
            stream.seek(0)
            return RandomAccessStreamReference.create_from_stream(stream)
        except Exception as exc:
            _log.warning(
                "SMTC thumbnail build failed for station %s: %s", station_id, exc
            )
            return None

    def shutdown(self) -> None:
        """Detach from SMTC + release COM object (D-09).

        Symmetric with LinuxMprisBackend.shutdown -- idempotent, independent
        try/except per step so one failure does not skip the others.
        T-43.1-01: explicitly sets `is_enabled = False` to prevent the
        MusicStreamer SMTC session from lingering in the Windows media
        overlay if COM GC is slow.
        Pitfall #4: remove_button_pressed requires the exact token stored
        by __init__.
        """
        if self._shutdown_complete:
            return

        try:
            self._smtc.remove_button_pressed(self._bp_token)  # Pitfall #4
        except Exception as exc:
            _log.debug("SMTC remove_button_pressed failed: %s", exc)

        try:
            self._smtc.is_enabled = False  # T-43.1-01 defensive
        except Exception as exc:
            _log.debug("SMTC is_enabled=False failed: %s", exc)

        try:
            self._media_player.close()  # release COM object
        except Exception as exc:
            _log.debug("MediaPlayer.close() failed: %s", exc)

        self._shutdown_complete = True


def create_windows_backend(player, repo) -> MediaKeysBackend:
    """Construct the Windows SMTC backend, or raise ImportError on missing wheels.

    D-06: winrt imports happen inside this function body so smtc.py stays
    Linux-importable. D-07: any ImportError (or other Exception) propagates
    to the factory in media_keys/__init__.py which falls back to
    NoOpMediaKeysBackend.
    """
    try:
        # Deferred imports: triggers ImportError on Linux / Windows without
        # the [windows] extras. Names are also imported inside
        # WindowsMediaKeysBackend.__init__ to keep each entry point self-contained.
        from winrt.windows.media.playback import MediaPlayer  # noqa: F401, PLC0415
        from winrt.windows.media import (  # noqa: F401, PLC0415
            MediaPlaybackStatus,
            MediaPlaybackType,
            SystemMediaTransportControlsButton,
        )
    except ImportError as exc:
        raise ImportError(_INSTALL_HINT) from exc

    return WindowsMediaKeysBackend(player, repo)
