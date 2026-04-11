"""No-op MPRIS2 stub for Phase 35.

Phase 41 (MEDIA-02) will rewrite this against PySide6.QtDBus. Between
Phase 35 and Phase 41 media keys are NON-FUNCTIONAL by design — see
.planning/phases/35-backend-isolation/35-CONTEXT.md D-09, D-10, D-11.

This module intentionally has zero dbus-python, zero GLib, and zero Qt
imports. Its only job is to preserve the public surface main_window.py
consumes so the GTK app still launches during the transition.

Public surface preserved (from grep of musicstreamer/ui/main_window.py):
  - MprisService(window)             # line 36
  - mpris.emit_properties_changed(d) # lines 702, 775, 809, 965
  - mpris._build_metadata()          # lines 811, 967
"""
import logging

_log = logging.getLogger(__name__)


class MprisService:
    """No-op stub. Accepts the same constructor arguments as the real service;
    every method is a no-op. Logs a one-line debug warning on construction so
    the non-functional state is discoverable in logs (D-11)."""

    def __init__(self, window=None):
        self._window = window
        _log.debug("MprisService stub active — media keys disabled until Phase 41 (MEDIA-02)")

    def emit_properties_changed(self, props: dict) -> None:
        """No-op. Accepts any dict shape (including dbus-typed values from
        main_window.py's legacy call sites) and silently discards it."""
        return None

    def _build_metadata(self) -> dict:
        """Return empty dict. main_window.py passes the result back into
        emit_properties_changed, which is itself a no-op."""
        return {}
