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

import logging

from musicstreamer.media_keys.base import MediaKeysBackend

_log = logging.getLogger(__name__)

_INSTALL_HINT = (
    "Windows media keys unavailable -- install with "
    '`pip install -e ".[windows]"` inside the Windows env.'
)


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

        # Pitfall #4: store the token -- shutdown (Plan 05) needs it for remove_button_pressed.
        self._bp_token = self._smtc.add_button_pressed(self._on_button_pressed)

        # Cache enum refs for hot-path callback (avoids re-import on each call)
        self._button_enum = SystemMediaTransportControlsButton
        self._status_enum = MediaPlaybackStatus
        self._type_enum = MediaPlaybackType  # consumed in Plan 04 (publish_metadata)

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
