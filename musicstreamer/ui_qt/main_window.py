"""Phase 37 Qt MainWindow — station list + now-playing integration.

Populates the Phase 36 bare-chrome scaffold:
  - QSplitter(Qt.Horizontal) as centralWidget
  - StationListPanel on the left (30%, min 280px)
  - NowPlayingPanel on the right (70%, min 560px)
  - ToastOverlay anchored to centralWidget bottom-centre
  - Player signals wired to NowPlayingPanel slots and MainWindow toast handlers

All signal connections use bound methods (no self-capturing lambdas) per QA-05.
"""
from __future__ import annotations

# Side-effect import: registers the :/icons/ resource prefix before any
# QIcon lookup. Must live at module top so tests that construct MainWindow
# (not just the GUI entry point) also get resources registered — per
# Phase 36 research Pitfall 2 and D-24.
from musicstreamer.ui_qt import icons_rc  # noqa: F401

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QMainWindow,
    QMenuBar,
    QSplitter,
    QStatusBar,
    QWidget,
)

from musicstreamer.models import Station
from musicstreamer.ui_qt.now_playing_panel import NowPlayingPanel
from musicstreamer.ui_qt.station_list_panel import StationListPanel
from musicstreamer.ui_qt.toast import ToastOverlay


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

        # D-03: menubar placeholder — one empty menu, zero QActions.
        # Phase 40 (UI-10) wires real menu actions.
        menubar: QMenuBar = self.menuBar()
        menubar.addMenu("\u2261")  # ≡ hamburger placeholder

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

    # ----------------------------------------------------------------------
    # Public helpers
    # ----------------------------------------------------------------------

    def show_toast(self, text: str, duration_ms: int = 3000) -> None:
        """Show a toast notification on the centralWidget bottom-centre."""
        self._toast.show_toast(text, duration_ms)

    # ----------------------------------------------------------------------
    # Slots (bound methods — no self-capturing lambdas, QA-05)
    # ----------------------------------------------------------------------

    def _on_station_activated(self, station: Station) -> None:
        """Called when the user selects a station in StationListPanel."""
        self.now_playing.bind_station(station)
        self._player.play(station)
        self._repo.update_last_played(station.id)
        self.now_playing.on_playing_state_changed(True)
        self.show_toast("Connecting\u2026")  # UI-SPEC copywriting: U+2026

    def _on_failover(self, next_stream) -> None:
        """Called by Player.failover(StationStream | None)."""
        if next_stream is None:
            self.show_toast("Stream exhausted")
            self.now_playing.on_playing_state_changed(False)
        else:
            self.show_toast("Stream failed, trying next\u2026")

    def _on_offline(self, _channel: str) -> None:
        """Called by Player.offline(channel_name) — Twitch channel offline."""
        self.show_toast("Channel offline")
        self.now_playing.on_playing_state_changed(False)

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
