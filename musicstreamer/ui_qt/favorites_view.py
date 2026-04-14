"""Phase 38-02: FavoritesView widget.

Two-section favorites panel shown when Favorites mode is active:
  - "Favorite Stations" flat QListWidget (starred stations from DB)
  - "Favorite Tracks" flat QListWidget (starred ICY tracks, newest first, with trash)

Empty state: centered "No favorites yet" heading + body text shown when both lists empty.

Signals:
  station_activated(Station) — re-emitted through StationListPanel for play
  favorites_changed()        — emitted after trash removal so callers can refresh

All signal connections use bound methods (QA-05).
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

# Side-effect import: registers :/icons/ resource prefix.
from musicstreamer.ui_qt import icons_rc  # noqa: F401
from musicstreamer.models import Station
from musicstreamer.ui_qt._art_paths import load_station_icon


class FavoritesView(QWidget):
    """Favorites panel — starred stations + starred ICY tracks with trash removal."""

    station_activated = Signal(Station)
    favorites_changed = Signal()

    def __init__(self, repo, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._repo = repo

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ------------------------------------------------------------------
        # Empty state (shown when both lists are empty)
        # ------------------------------------------------------------------
        self._empty_widget = QWidget(self)
        empty_layout = QVBoxLayout(self._empty_widget)
        empty_layout.setAlignment(Qt.AlignCenter)

        self._empty_label = QLabel("No favorites yet", self._empty_widget)
        empty_heading_font = QFont()
        empty_heading_font.setPointSize(16)
        empty_heading_font.setWeight(QFont.DemiBold)
        self._empty_label.setFont(empty_heading_font)
        self._empty_label.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(self._empty_label)

        empty_body = QLabel("Star a station or track to save it here.", self._empty_widget)
        empty_body_font = QFont()
        empty_body_font.setPointSize(10)
        empty_body_font.setWeight(QFont.Normal)
        empty_body.setFont(empty_body_font)
        empty_body.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(empty_body)

        layout.addWidget(self._empty_widget)

        # ------------------------------------------------------------------
        # Content widget (shown when favorites exist)
        # ------------------------------------------------------------------
        self._content_widget = QWidget(self)
        content_layout = QVBoxLayout(self._content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # "Favorite Stations" section header
        stations_label = QLabel("Favorite Stations", self._content_widget)
        sl_font = QFont()
        sl_font.setPointSize(9)
        sl_font.setWeight(QFont.Normal)
        stations_label.setFont(sl_font)
        stations_label.setContentsMargins(8, 8, 0, 0)
        content_layout.addWidget(stations_label)

        # Stations list
        self._stations_list = QListWidget(self._content_widget)
        self._stations_list.setIconSize(QSize(32, 32))
        self._stations_list.setEditTriggers(QListWidget.NoEditTriggers)
        content_layout.addWidget(self._stations_list, stretch=1)
        self._stations_list.itemClicked.connect(self._on_station_item_clicked)

        # Separator
        sep = QFrame(self._content_widget)
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        content_layout.addWidget(sep)

        # "Favorite Tracks" section header
        tracks_label = QLabel("Favorite Tracks", self._content_widget)
        tl_font = QFont()
        tl_font.setPointSize(9)
        tl_font.setWeight(QFont.Normal)
        tracks_label.setFont(tl_font)
        tracks_label.setContentsMargins(8, 8, 0, 0)
        content_layout.addWidget(tracks_label)

        # Tracks list
        self._tracks_list = QListWidget(self._content_widget)
        self._tracks_list.setEditTriggers(QListWidget.NoEditTriggers)
        content_layout.addWidget(self._tracks_list, stretch=1)

        layout.addWidget(self._content_widget)

        # Initial populate
        self.refresh()

    # ----------------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------------

    def refresh(self) -> None:
        """Repopulate both lists from repo. Show empty state if both empty."""
        self._populate_stations()
        self._populate_tracks()
        has_content = self._stations_list.count() > 0 or self._tracks_list.count() > 0
        self._empty_widget.setVisible(not has_content)
        self._content_widget.setVisible(has_content)

    def remove_station_favorite(self, station_id: int) -> None:
        """Unstar a station and refresh."""
        self._repo.set_station_favorite(station_id, False)
        self.refresh()

    # ----------------------------------------------------------------------
    # Population helpers
    # ----------------------------------------------------------------------

    def _populate_stations(self) -> None:
        self._stations_list.clear()
        for station in self._repo.list_favorite_stations():
            item = QListWidgetItem(station.name)
            item.setIcon(load_station_icon(station))
            item.setSizeHint(QSize(0, 40))
            item.setData(Qt.UserRole, station)
            self._stations_list.addItem(item)

    def _populate_tracks(self) -> None:
        self._tracks_list.clear()
        for fav in self._repo.list_favorites():
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 40))
            self._tracks_list.addItem(item)

            # Row widget: text + trash button
            row_widget = self._make_track_row_widget(fav)
            self._tracks_list.setItemWidget(item, row_widget)

    def _make_track_row_widget(self, fav) -> QWidget:
        """Build row widget for a track favorite: label + trash button."""
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(8, 0, 4, 0)
        row_layout.setSpacing(4)

        # "Track Title — Station Name" (em dash U+2014 per UI-SPEC)
        label = QLabel(f"{fav.track_title} \u2014 {fav.station_name}", row)
        label_font = QFont()
        label_font.setPointSize(10)
        label_font.setWeight(QFont.Normal)
        label.setFont(label_font)
        label.setTextFormat(Qt.PlainText)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        row_layout.addWidget(label, stretch=1)

        trash_btn = QToolButton(row)
        trash_btn.setFixedSize(24, 24)
        trash_btn.setIconSize(QSize(16, 16))
        trash_btn.setIcon(
            QIcon.fromTheme("user-trash-symbolic", QIcon(":/icons/user-trash-symbolic.svg"))
        )
        trash_btn.setToolTip("Remove from favorites")
        # Bind the specific fav data to the click handler via a default-arg capture.
        # Per QA-05 guidance this is the approved pattern for per-item closures
        # where no widget lifetime cycle is created.
        trash_btn.clicked.connect(
            lambda checked=False, sn=fav.station_name, tt=fav.track_title:
            self._on_trash_clicked(sn, tt)
        )
        row_layout.addWidget(trash_btn)

        return row

    # ----------------------------------------------------------------------
    # Slots
    # ----------------------------------------------------------------------

    def _on_station_item_clicked(self, item: QListWidgetItem) -> None:
        station = item.data(Qt.UserRole)
        if isinstance(station, Station):
            self.station_activated.emit(station)

    def _on_trash_clicked(self, station_name: str, track_title: str) -> None:
        self._repo.remove_favorite(station_name, track_title)
        # Repopulate tracks list
        self._populate_tracks()
        # Update empty state visibility
        has_content = self._stations_list.count() > 0 or self._tracks_list.count() > 0
        self._empty_widget.setVisible(not has_content)
        self._content_widget.setVisible(has_content)
        self.favorites_changed.emit()
