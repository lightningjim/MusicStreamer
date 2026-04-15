"""Phase 37 Qt MainWindow — station list + now-playing integration.

Populates the Phase 36 bare-chrome scaffold:
  - QSplitter(Qt.Horizontal) as centralWidget
  - StationListPanel on the left (30%, min 280px)
  - NowPlayingPanel on the right (70%, min 560px)
  - ToastOverlay anchored to centralWidget bottom-centre
  - Player signals wired to NowPlayingPanel slots and MainWindow toast handlers

Phase 41 adds MediaKeysBackend wiring:
  - Constructed via media_keys.create(player, repo) after all panels are ready
  - Player.title_changed bridges to backend.publish_metadata (D-05)
  - backend.play_pause_requested / stop_requested bridge to NowPlayingPanel slots
  - Playback state transitions call backend.set_playback_state
  - closeEvent calls backend.shutdown() for clean MPRIS service unregistration

All signal connections use bound methods (no self-capturing lambdas) per QA-05.
"""
from __future__ import annotations

import logging

# Side-effect import: registers the :/icons/ resource prefix before any
# QIcon lookup. Must live at module top so tests that construct MainWindow
# (not just the GUI entry point) also get resources registered — per
# Phase 36 research Pitfall 2 and D-24.
from musicstreamer.ui_qt import icons_rc  # noqa: F401

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QMainWindow,
    QMenuBar,
    QSplitter,
    QStatusBar,
    QWidget,
)

from musicstreamer import media_keys
from musicstreamer.media_keys.base import NoOpMediaKeysBackend
from musicstreamer.models import Station

_log = logging.getLogger(__name__)
from musicstreamer.ui_qt.accent_color_dialog import AccentColorDialog
from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
from musicstreamer.ui_qt.cookie_import_dialog import CookieImportDialog
from musicstreamer.ui_qt.edit_station_dialog import EditStationDialog
from musicstreamer.ui_qt.discovery_dialog import DiscoveryDialog
from musicstreamer.ui_qt.import_dialog import ImportDialog
from musicstreamer.ui_qt.now_playing_panel import NowPlayingPanel
from musicstreamer.ui_qt.station_list_panel import StationListPanel
from musicstreamer.ui_qt.toast import ToastOverlay
from musicstreamer.accent_utils import apply_accent_palette, _is_valid_hex


class MainWindow(QMainWindow):
    """Main application window — station list + now-playing + toast overlay."""

    def __init__(self, player, repo, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._player = player
        self._repo = repo

        # D-02: window title + default geometry. No QSettings persistence.
        self.setWindowTitle("MusicStreamer")
        self.setWindowIcon(
            QIcon.fromTheme(
                "application-x-executable",
                QIcon(":/icons/app-icon.svg"),
            )
        )
        self.resize(1200, 800)

        # UI-10 hamburger menu (D-13)
        menubar: QMenuBar = self.menuBar()
        self._menu = menubar.addMenu("\u2261")

        # Group 1: Discovery + Import (D-14, D-15)
        act_discover = self._menu.addAction("Discover Stations")
        act_discover.triggered.connect(self._open_discovery_dialog)

        act_import = self._menu.addAction("Import Stations")
        act_import.triggered.connect(self._open_import_dialog)

        self._menu.addSeparator()

        # Group 2: Settings dialogs (D-16, D-17, D-18)
        act_accent = self._menu.addAction("Accent Color")
        act_accent.triggered.connect(self._open_accent_dialog)

        act_cookies = self._menu.addAction("YouTube Cookies")
        act_cookies.triggered.connect(self._open_cookie_dialog)

        act_accounts = self._menu.addAction("Accounts")
        act_accounts.triggered.connect(self._open_accounts_dialog)

        self._menu.addSeparator()

        # Group 3: Export/Import Settings — disabled placeholders (D-19)
        act_export = self._menu.addAction("Export Settings")
        act_export.setEnabled(False)
        act_export.setToolTip("Coming in a future update")

        act_import_settings = self._menu.addAction("Import Settings")
        act_import_settings.setEnabled(False)
        act_import_settings.setToolTip("Coming in a future update")

        # D-12: apply saved accent color on startup (UI-11)
        _saved_accent = self._repo.get_setting("accent_color", "")
        if _saved_accent and _is_valid_hex(_saved_accent):
            from PySide6.QtWidgets import QApplication
            apply_accent_palette(QApplication.instance(), _saved_accent)

        # ------------------------------------------------------------------
        # Central widget: QSplitter (D-06, UI-SPEC Layout Contracts)
        # ------------------------------------------------------------------
        self._splitter = QSplitter(Qt.Horizontal, self)
        self._splitter.setChildrenCollapsible(False)

        self.station_panel = StationListPanel(repo, parent=self._splitter)
        self.station_panel.setMinimumWidth(280)

        self.now_playing = NowPlayingPanel(player, repo, parent=self._splitter)
        self.now_playing.setMinimumWidth(560)

        self._splitter.addWidget(self.station_panel)
        self._splitter.addWidget(self.now_playing)

        # Initial 30/70 split at 1200px wide window.
        self._splitter.setSizes([360, 840])

        self.setCentralWidget(self._splitter)

        # ------------------------------------------------------------------
        # Toast overlay — parented to centralWidget, anchored bottom-centre.
        # D-09/D-10: constructed AFTER centralWidget is set.
        # ------------------------------------------------------------------
        self._toast = ToastOverlay(self)

        # ------------------------------------------------------------------
        # Status bar
        # ------------------------------------------------------------------
        self.setStatusBar(QStatusBar(self))

        # ------------------------------------------------------------------
        # Signal wiring (D-18, QA-05: bound methods only)
        # ------------------------------------------------------------------
        # Station list → play
        self.station_panel.station_activated.connect(self._on_station_activated)

        # Player → now-playing panel
        self._player.title_changed.connect(self.now_playing.on_title_changed)
        self._player.elapsed_updated.connect(self.now_playing.on_elapsed_updated)

        # Player → toast notifications (D-11)
        self._player.failover.connect(self._on_failover)
        self._player.offline.connect(self._on_offline)
        self._player.playback_error.connect(self._on_playback_error)

        # Track star → toast (D-10)
        self.now_playing.track_starred.connect(self._on_track_starred)

        # Station star → toast (D-10)
        self.station_panel.station_favorited.connect(self._on_station_favorited)

        # Plan 39: edit button → dialog launch
        self.now_playing.edit_requested.connect(self._on_edit_requested)
        # Right-click edit from station list
        self.station_panel.edit_requested.connect(self._on_edit_requested)

        # Plan 39: failover → stream picker sync
        self._player.failover.connect(self.now_playing._sync_stream_picker)

        # ------------------------------------------------------------------
        # Phase 41: MediaKeysBackend wiring (D-02, D-05, D-06)
        # Constructed last so the backend sees a fully-constructed window.
        # The factory never raises (D-06) — belt-and-braces try/except here
        # ensures a construction bug in the backend never crashes startup.
        # ------------------------------------------------------------------
        try:
            self._media_keys = media_keys.create(self._player, self._repo)
        except Exception as exc:  # pragma: no cover  — factory should never raise
            _log.warning("media_keys.create failed unexpectedly: %s", exc)
            self._media_keys = NoOpMediaKeysBackend()

        # Backend → MainWindow: OS session requests
        self._media_keys.play_pause_requested.connect(self._on_media_key_play_pause)
        self._media_keys.stop_requested.connect(self._on_media_key_stop)
        # next/previous wired per D-02 contract but backend never emits (D-03)
        self._media_keys.next_requested.connect(self._on_media_key_next)
        self._media_keys.previous_requested.connect(self._on_media_key_previous)

        # Player → Backend: metadata + state (both connect independently to title_changed)
        self._player.title_changed.connect(self._on_title_changed_for_media_keys)

    # ----------------------------------------------------------------------
    # Public helpers
    # ----------------------------------------------------------------------

    def show_toast(self, text: str, duration_ms: int = 3000) -> None:
        """Show a toast notification on the centralWidget bottom-centre."""
        self._toast.show_toast(text, duration_ms)

    # ----------------------------------------------------------------------
    # Slots (bound methods — no self-capturing lambdas, QA-05)
    # ----------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:
        """Unregister the MPRIS2 service cleanly before the window closes (T-41-13)."""
        try:
            self._media_keys.shutdown()
        except Exception as exc:
            _log.warning("media_keys shutdown failed: %s", exc)
        super().closeEvent(event)

    def _on_station_activated(self, station: Station) -> None:
        """Called when the user selects a station in StationListPanel."""
        self.now_playing.bind_station(station)
        self._player.play(station)
        self._repo.update_last_played(station.id)
        self.now_playing.on_playing_state_changed(True)
        self.show_toast("Connecting\u2026")  # UI-SPEC copywriting: U+2026
        # Seed the OS media session with station name before ICY title arrives (D-05)
        self._media_keys.publish_metadata(station, "", self.now_playing.current_cover_pixmap())
        self._media_keys.set_playback_state("playing")

    def _on_failover(self, next_stream) -> None:
        """Called by Player.failover(StationStream | None)."""
        if next_stream is None:
            self.show_toast("Stream exhausted")
            self.now_playing.on_playing_state_changed(False)
            self._media_keys.set_playback_state("stopped")
        else:
            self.show_toast("Stream failed, trying next\u2026")

    def _on_offline(self, _channel: str) -> None:
        """Called by Player.offline(channel_name) — Twitch channel offline."""
        self.show_toast("Channel offline")
        self.now_playing.on_playing_state_changed(False)
        self._media_keys.set_playback_state("stopped")

    def _on_playback_error(self, message: str) -> None:
        """Called by Player.playback_error(str)."""
        truncated = message[:80] + "\u2026" if len(message) > 80 else message
        self.show_toast(f"Playback error: {truncated}")

    def _on_track_starred(self, station_name: str, track_title: str, provider: str, is_fav: bool) -> None:
        """Called when the track star button is toggled in NowPlayingPanel."""
        self.show_toast("Saved to favorites" if is_fav else "Removed from favorites")

    def _on_station_favorited(self, station: Station, is_fav: bool) -> None:
        """Called when a station star is toggled in StationListPanel."""
        self.show_toast("Station added to favorites" if is_fav else "Station removed from favorites")

    def _on_edit_requested(self, station: Station) -> None:
        """Open EditStationDialog for the given station (D-08)."""
        # Re-fetch from DB so edits saved moments ago are visible (UAT #2 fix)
        fresh = self._repo.get_station(station.id)
        if fresh is None:
            return
        dlg = EditStationDialog(fresh, self._player, self._repo, parent=self)
        dlg.station_saved.connect(self._refresh_station_list)
        dlg.station_saved.connect(lambda: self._sync_now_playing_station(fresh.id))
        dlg.station_deleted.connect(self._on_station_deleted)
        dlg.exec()

    def _on_station_deleted(self, station_id: int) -> None:
        """After station deletion, refresh list and clear now-playing if needed."""
        self._refresh_station_list()
        if self.now_playing.current_station and self.now_playing.current_station.id == station_id:
            self.now_playing._on_stop_clicked()
            self._media_keys.set_playback_state("stopped")

    # ----------------------------------------------------------------------
    # Phase 41: MediaKeysBackend bridge slots (QA-05: bound methods only)
    # ----------------------------------------------------------------------

    def _on_title_changed_for_media_keys(self, title: str) -> None:
        """Bridge Player.title_changed -> backend.publish_metadata (D-05).

        Called on every ICY title update. The cover pixmap may still be showing
        the previous track's art for a few hundred ms (async iTunes fetch) —
        that's acceptable; the next title_changed after iTunes resolves updates it.
        """
        station = self.now_playing.current_station
        cover = self.now_playing.current_cover_pixmap()
        self._media_keys.publish_metadata(station, title, cover)

    def _on_media_key_play_pause(self) -> None:
        """OS play/pause request -> toggle playback in NowPlayingPanel."""
        if self.now_playing.current_station is None:
            return  # no station bound — ignore
        # Delegate to the same slot the in-panel button calls (QA-05)
        self.now_playing._on_play_pause_clicked()
        # Mirror the resulting state to the backend
        if self.now_playing._is_playing:
            self._media_keys.set_playback_state("playing")
        else:
            self._media_keys.set_playback_state("paused")

    def _on_media_key_stop(self) -> None:
        """OS stop request -> stop via NowPlayingPanel."""
        self.now_playing._on_stop_clicked()
        self._media_keys.set_playback_state("stopped")

    def _on_media_key_next(self) -> None:
        """OS next-track request — no-op (D-03: no queue concept in v2.0)."""
        pass  # Future: wire to queue navigation when a playlist concept exists

    def _on_media_key_previous(self) -> None:
        """OS previous-track request — no-op (D-03: no queue concept in v2.0)."""
        pass  # Future: wire to queue navigation when a playlist concept exists

    def _sync_now_playing_station(self, station_id: int) -> None:
        """Re-fetch station from DB and rebind the now-playing panel.

        If the edited station is the one currently bound to the now-playing
        panel, call bind_station() on the refreshed copy so field changes
        (notably icy_disabled, D-15/16/17) take effect without a restart.
        """
        updated_station = self._repo.get_station(station_id)
        if updated_station is None:
            return
        current = getattr(self.now_playing, "_station", None)
        if current is not None and current.id == updated_station.id:
            self.now_playing.bind_station(updated_station)

    def _refresh_station_list(self) -> None:
        """Reload station list model after edit/delete/import."""
        self.station_panel.refresh_model()

    def _open_discovery_dialog(self) -> None:
        """D-14: Open DiscoveryDialog from hamburger menu."""
        dlg = DiscoveryDialog(self._player, self._repo, self.show_toast, parent=self)
        dlg.exec()
        self._refresh_station_list()

    def _open_import_dialog(self) -> None:
        """D-15: Open ImportDialog from hamburger menu."""
        dlg = ImportDialog(self.show_toast, parent=self)
        dlg.import_complete.connect(self._refresh_station_list)
        dlg.exec()

    def _open_accent_dialog(self) -> None:
        """D-16: Open AccentColorDialog from hamburger menu."""
        dlg = AccentColorDialog(self._repo, parent=self)
        dlg.exec()

    def _open_cookie_dialog(self) -> None:
        """D-17: Open CookieImportDialog from hamburger menu."""
        dlg = CookieImportDialog(self.show_toast, parent=self)
        dlg.exec()

    def _open_accounts_dialog(self) -> None:
        """D-18: Open AccountsDialog from hamburger menu."""
        dlg = AccountsDialog(parent=self)
        dlg.exec()
