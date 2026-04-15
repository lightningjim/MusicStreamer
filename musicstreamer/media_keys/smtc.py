# TODO-43.1: Windows SMTC implementation deferred to Phase 43.1.
#
# When Phase 43.1 lands, this module will implement:
#   - winrt.windows.media.playback.MediaPlayer (or SystemMediaTransportControls)
#   - async button_pressed event via winrt event loop bridged to Qt
#   - Requires confirmed Windows runtime from Phase 43 GStreamer spike
#   - Optional dependency: winrt-Windows.Media.Playback (pyproject.toml
#     [project.optional-dependencies].windows)
#
# For now, create_windows_backend raises NotImplementedError so the factory
# in __init__.py can catch it and fall back to NoOpMediaKeysBackend (D-06).
# This file intentionally contains NO winrt imports at module scope so it
# is safely importable on Linux for test purposes.
from __future__ import annotations


def create_windows_backend(player, repo):
    """Windows SMTC backend factory stub.

    Raises NotImplementedError unconditionally pending Phase 43.1 implementation.
    The caller (musicstreamer.media_keys.create) catches this and falls back to
    NoOpMediaKeysBackend so the app does not crash on Windows during Phase 41-42.
    """
    raise NotImplementedError(
        "MEDIA-03: Windows SMTC backend deferred to Phase 43.1 -- "
        "see .planning/ROADMAP.md Phase 43.1"
    )
