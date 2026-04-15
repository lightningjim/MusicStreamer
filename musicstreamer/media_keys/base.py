"""Abstract base class for platform media-key backends (Phase 41, D-02).

DO NOT use abc.ABCMeta — it conflicts with type(QObject) (PySide6 metaclass).
Use NotImplementedError in method bodies instead (PySide6 docs pattern).

The public set_playback_state() validates the Literal["playing","paused","stopped"]
contract in this base and delegates to _apply_playback_state() so every subclass
gets the validation for free.
"""
from __future__ import annotations

import logging
from typing import Literal

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QPixmap

from musicstreamer.models import Station

_log = logging.getLogger(__name__)

_VALID_STATES = frozenset({"playing", "paused", "stopped"})


class MediaKeysBackend(QObject):
    """Abstract base for OS media-session backends.

    Subclasses MUST override publish_metadata, _apply_playback_state,
    and shutdown.  Do NOT use abc.ABCMeta — metaclass conflict with QObject.
    """

    play_pause_requested = Signal()
    stop_requested       = Signal()
    next_requested       = Signal()   # wired but may never emit
    previous_requested   = Signal()   # wired but may never emit

    def publish_metadata(
        self,
        station: Station | None,
        title: str,
        cover_pixmap: QPixmap | None,
    ) -> None:
        """Publish station + track metadata to the OS media session."""
        raise NotImplementedError(f"{type(self).__name__}.publish_metadata not implemented")

    def set_playback_state(self, state: Literal["playing", "paused", "stopped"]) -> None:
        """Validate *state* then delegate to _apply_playback_state.

        Raises ValueError for unrecognised state strings so downstream
        wiring bugs surface immediately rather than silently doing nothing.
        """
        if state not in _VALID_STATES:
            raise ValueError(
                f"Invalid playback state {state!r}. "
                f"Must be one of: {sorted(_VALID_STATES)}"
            )
        self._apply_playback_state(state)

    def _apply_playback_state(self, state: Literal["playing", "paused", "stopped"]) -> None:
        """Hook for subclasses — called only after validation passes."""
        raise NotImplementedError(f"{type(self).__name__}._apply_playback_state not implemented")

    def shutdown(self) -> None:
        """Unregister from OS session cleanly. Call on application exit."""
        raise NotImplementedError(f"{type(self).__name__}.shutdown not implemented")


class NoOpMediaKeysBackend(MediaKeysBackend):
    """Fallback backend that satisfies the interface but does nothing.

    Used when D-Bus is unavailable, on unsupported platforms, or while
    Plan 02 (LinuxMprisBackend) is not yet installed. App startup never
    blocks on media-keys (D-06 requirement).
    """

    def publish_metadata(
        self,
        station: Station | None,
        title: str,
        cover_pixmap: QPixmap | None,
    ) -> None:
        return None

    def _apply_playback_state(self, state: Literal["playing", "paused", "stopped"]) -> None:
        return None

    def shutdown(self) -> None:
        return None
