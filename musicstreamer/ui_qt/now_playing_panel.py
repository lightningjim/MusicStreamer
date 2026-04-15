"""Phase 37-02: NowPlayingPanel.

Right-panel widget for the Qt main window. Three-column horizontal layout:

    [ 180x180 station logo | center stretch (Name/ICY/elapsed/controls) | 160x160 cover ]

Consumes:
  * Player signals (title_changed, elapsed_updated) — slots defined here, wired
    by MainWindow in Plan 37-04.
  * cover_art.fetch_cover_art — pure-Python worker; callback marshalled onto
    the Qt main thread via the ``cover_art_ready`` Signal with
    ``Qt.ConnectionType.QueuedConnection``.
  * repo.get_setting / set_setting — volume persistence.

Does NOT modify player.py or cover_art.py (consume only).

Security: ICY label is ``Qt.PlainText`` to prevent rich-text interpretation of
untrusted metadata from upstream streams.

Lifetime: all signal connections use bound methods (no self-capturing lambdas)
per QA-05. The single nested function ``_cb`` inside ``_fetch_cover_art_async``
is a worker-thread adapter; it is passed to ``fetch_cover_art`` as a raw
callable, not connected as a Qt slot, so it does not create a lifetime cycle
against the panel.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

# Side-effect import: registers :/icons/ resource prefix.
from musicstreamer.ui_qt import icons_rc  # noqa: F401
from musicstreamer.ui_qt._art_paths import abs_art_path
from musicstreamer.cover_art import fetch_cover_art, is_junk_title
from musicstreamer.models import Station


_FALLBACK_ICON = ":/icons/audio-x-generic-symbolic.svg"


def _load_scaled_pixmap(path: Optional[str], size: QSize) -> QPixmap:
    """Load ``path`` and scale into ``size`` preserving aspect ratio.

    Falls back to the bundled generic audio icon on load failure. The returned
    pixmap is never null.
    """
    resolved = abs_art_path(path)
    pix = QPixmap()
    if resolved:
        pix = QPixmap(resolved)
    if pix.isNull():
        pix = QPixmap(_FALLBACK_ICON)
    return pix.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


class NowPlayingPanel(QWidget):
    """Right-panel now-playing widget (UI-02 + UI-14).

    Public slots (wired by MainWindow in Plan 37-04):
      - on_title_changed(str)       from player.title_changed
      - on_elapsed_updated(int)     from player.elapsed_updated
      - on_playing_state_changed(bool)  called by MainWindow after play/stop
    """

    # Emitted by the cover_art worker thread with a temp file path, or empty
    # string to signal "no cover — fall back to station logo". Queued-connected
    # to ``_on_cover_art_ready`` so the slot runs on the main thread.
    cover_art_ready = Signal(str)

    # Emitted on track star toggle: (station_name, track_title, provider_name, is_now_favorited)
    track_starred = Signal(str, str, str, bool)

    # Emitted when user clicks edit button — passes current Station to MainWindow.
    edit_requested = Signal(object)

    def __init__(self, player, repo, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._player = player
        self._repo = repo
        self._station: Optional[Station] = None
        self._cover_fetch_token: int = 0
        self._last_cover_icy: Optional[str] = None
        self._is_playing: bool = False
        self._last_icy_title: str = ""
        self._streams: list = []

        self.setMinimumWidth(560)

        # ------------------------------------------------------------------
        # Outer three-column layout
        # ------------------------------------------------------------------
        outer = QHBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(24)

        # ------------------------------------------------------------------
        # Left column: 180x180 station logo
        # ------------------------------------------------------------------
        self.logo_label = QLabel(self)
        self.logo_label.setFixedSize(180, 180)
        self.logo_label.setAlignment(Qt.AlignCenter)
        self.logo_label.setScaledContents(False)
        outer.addWidget(self.logo_label)

        # ------------------------------------------------------------------
        # Center column: Name·Provider / ICY / elapsed / control row
        # ------------------------------------------------------------------
        center = QVBoxLayout()
        center.setSpacing(8)
        center.setAlignment(Qt.AlignVCenter)

        # Name · Provider (UI-SPEC Label role 9pt Normal)
        self.name_provider_label = QLabel("", self)
        np_font = QFont()
        np_font.setPointSize(9)
        np_font.setWeight(QFont.Normal)
        self.name_provider_label.setFont(np_font)
        self.name_provider_label.setTextFormat(Qt.PlainText)
        center.addWidget(self.name_provider_label)

        # ICY title (UI-SPEC Heading role 13pt DemiBold)
        self.icy_label = QLabel("No station playing", self)
        icy_font = QFont()
        icy_font.setPointSize(13)
        icy_font.setWeight(QFont.DemiBold)
        self.icy_label.setFont(icy_font)
        # Security lock-down: never interpret ICY strings as rich text.
        self.icy_label.setTextFormat(Qt.PlainText)
        center.addWidget(self.icy_label)

        # Elapsed timer (UI-SPEC Body role 10pt, TypeWriter hint for tabular digits)
        self.elapsed_label = QLabel("0:00", self)
        el_font = QFont()
        el_font.setPointSize(10)
        el_font.setWeight(QFont.Normal)
        el_font.setStyleHint(QFont.TypeWriter)
        self.elapsed_label.setFont(el_font)
        center.addWidget(self.elapsed_label)

        # Control row: play/pause + stop + volume slider
        controls = QHBoxLayout()
        controls.setSpacing(8)

        self.play_pause_btn = QToolButton(self)
        self.play_pause_btn.setIconSize(QSize(24, 24))
        self.play_pause_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.play_pause_btn.setFixedSize(36, 36)
        self.play_pause_btn.setIcon(
            QIcon.fromTheme(
                "media-playback-start-symbolic",
                QIcon(":/icons/media-playback-start-symbolic.svg"),
            )
        )
        self.play_pause_btn.setToolTip("Play")
        self.play_pause_btn.clicked.connect(self._on_play_pause_clicked)
        controls.addWidget(self.play_pause_btn)

        self.stop_btn = QToolButton(self)
        self.stop_btn.setIconSize(QSize(24, 24))
        self.stop_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.stop_btn.setFixedSize(36, 36)
        self.stop_btn.setIcon(
            QIcon.fromTheme(
                "media-playback-stop-symbolic",
                QIcon(":/icons/media-playback-stop-symbolic.svg"),
            )
        )
        self.stop_btn.setToolTip("Stop")
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        controls.addWidget(self.stop_btn)

        # Plan 39: edit button (D-08)
        self.edit_btn = QToolButton(self)
        self.edit_btn.setIconSize(QSize(24, 24))
        self.edit_btn.setFixedSize(36, 36)
        self.edit_btn.setIcon(
            QIcon.fromTheme("document-edit-symbolic", QIcon(":/icons/document-edit-symbolic.svg"))
        )
        self.edit_btn.setToolTip("Edit station")
        self.edit_btn.setEnabled(False)
        self.edit_btn.clicked.connect(self._on_edit_clicked)
        controls.addWidget(self.edit_btn)

        # Plan 39: stream picker (D-19..D-22)
        self.stream_combo = QComboBox(self)
        self.stream_combo.setMinimumWidth(140)
        self.stream_combo.setVisible(False)
        self.stream_combo.currentIndexChanged.connect(self._on_stream_selected)
        controls.addWidget(self.stream_combo)

        # Plan 38: track star button (D-08, D-11)
        self.star_btn = QToolButton(self)
        self.star_btn.setIconSize(QSize(20, 20))
        self.star_btn.setFixedSize(28, 28)
        self.star_btn.setCheckable(True)
        self.star_btn.setEnabled(False)  # disabled until station + ICY title available
        self.star_btn.setIcon(
            QIcon.fromTheme("non-starred-symbolic", QIcon(":/icons/non-starred-symbolic.svg"))
        )
        self.star_btn.clicked.connect(self._on_star_clicked)
        controls.addWidget(self.star_btn)

        self.volume_slider = QSlider(Qt.Horizontal, self)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setFixedWidth(120)
        self.volume_slider.setTickPosition(QSlider.NoTicks)
        controls.addWidget(self.volume_slider)

        controls.addStretch(1)
        center.addLayout(controls)

        outer.addLayout(center, 1)

        # ------------------------------------------------------------------
        # Right column: 160x160 cover art slot
        # ------------------------------------------------------------------
        self.cover_label = QLabel(self)
        self.cover_label.setFixedSize(160, 160)
        self.cover_label.setAlignment(Qt.AlignCenter)
        outer.addWidget(self.cover_label)

        # ------------------------------------------------------------------
        # Volume initialization (RESEARCH §6)
        # ------------------------------------------------------------------
        stored = self._repo.get_setting("volume", "80")
        try:
            initial = int(stored) if stored is not None else 80
        except (TypeError, ValueError):
            initial = 80
        self.volume_slider.setValue(initial)
        self._player.set_volume(initial / 100.0)
        self.volume_slider.setToolTip(f"Volume: {initial}%")

        # Wiring — bound methods only (QA-05).
        self.volume_slider.valueChanged.connect(self._on_volume_changed_live)
        self.volume_slider.sliderReleased.connect(self._on_volume_released)

        # Cover art signal adapter — queued connection so emission from the
        # cover_art worker thread is marshalled onto the main thread.
        self.cover_art_ready.connect(
            self._on_cover_art_ready, Qt.ConnectionType.QueuedConnection
        )

    # ----------------------------------------------------------------------
    # Public API — station binding
    # ----------------------------------------------------------------------

    @property
    def current_station(self) -> Optional[Station]:
        """Read-only access to the currently bound station."""
        return self._station

    def bind_station(self, station: Station) -> None:
        """Attach a Station and reset the panel for playback of that station."""
        self._station = station
        if station.provider_name:
            self.name_provider_label.setText(
                f"{station.name} \u00B7 {station.provider_name}"
            )
        else:
            self.name_provider_label.setText(station.name)
        if station is not None and getattr(station, "icy_disabled", False):
            self.icy_label.setText(station.name or "")
        else:
            self.icy_label.setText("")
        self._last_cover_icy = None
        self._last_icy_title = ""
        self.star_btn.setChecked(False)
        self._update_star_enabled()
        self._show_station_logo()
        self._show_station_logo_in_cover_slot()
        self._populate_stream_picker(station)

    # ----------------------------------------------------------------------
    # Player signal slots (wired by MainWindow in 37-04)
    # ----------------------------------------------------------------------

    def on_title_changed(self, title: str) -> None:
        if self._station is not None and self._station.icy_disabled:
            # Per-station ICY disable (D-15, D-16, D-17): do not display ICY
            # titles or trigger iTunes cover-art lookup. icy_label keeps the
            # station name fallback set by bind_station().
            return
        self.icy_label.setText(title or "")
        self._last_icy_title = title or ""
        self._update_star_enabled()
        if self._station and title:
            is_fav = self._repo.is_favorited(self._station.name, title)
            self.star_btn.setChecked(is_fav)
            icon_name = "starred-symbolic" if is_fav else "non-starred-symbolic"
            self.star_btn.setIcon(
                QIcon.fromTheme(icon_name, QIcon(f":/icons/{icon_name}.svg"))
            )
            self.star_btn.setToolTip(
                "Remove track from favorites" if is_fav else "Save track to favorites"
            )
        if (
            title
            and not is_junk_title(title)
            and self._station is not None
            and title != self._last_cover_icy
        ):
            self._last_cover_icy = title
            self._fetch_cover_art_async(title)

    def on_elapsed_updated(self, seconds: int) -> None:
        if seconds < 3600:
            self.elapsed_label.setText(f"{seconds // 60}:{seconds % 60:02d}")
        else:
            h = seconds // 3600
            m = (seconds % 3600) // 60
            s = seconds % 60
            self.elapsed_label.setText(f"{h}:{m:02d}:{s:02d}")

    def on_playing_state_changed(self, is_playing: bool) -> None:
        self._is_playing = bool(is_playing)
        if self._is_playing:
            self.play_pause_btn.setIcon(
                QIcon.fromTheme(
                    "media-playback-pause-symbolic",
                    QIcon(":/icons/media-playback-pause-symbolic.svg"),
                )
            )
            self.play_pause_btn.setToolTip("Pause")
        else:
            self.play_pause_btn.setIcon(
                QIcon.fromTheme(
                    "media-playback-start-symbolic",
                    QIcon(":/icons/media-playback-start-symbolic.svg"),
                )
            )
            self.play_pause_btn.setToolTip("Play")
        self.edit_btn.setEnabled(self._station is not None)
        self._update_star_enabled()

    # ----------------------------------------------------------------------
    # Internal slots
    # ----------------------------------------------------------------------

    def _on_play_pause_clicked(self) -> None:
        if self._is_playing:
            self._player.pause()
            self.on_playing_state_changed(False)
        elif self._station is not None:
            self._player.play(self._station)
            self.on_playing_state_changed(True)

    def _on_stop_clicked(self) -> None:
        self._player.stop()
        self.on_playing_state_changed(False)
        # Keep _station so edit button remains functional after stop (UAT #3 fix)
        self.stream_combo.setVisible(False)
        self._last_icy_title = ""
        self.star_btn.setChecked(False)
        self._update_star_enabled()
        self.name_provider_label.setText("")
        self.icy_label.setText("No station playing")
        self.elapsed_label.setText("0:00")
        self._last_cover_icy = None
        self.logo_label.clear()
        self.cover_label.clear()

    def _update_star_enabled(self) -> None:
        """Enable star_btn only when a station is playing and an ICY title is available."""
        has_track = self._station is not None and bool(self._last_icy_title)
        self.star_btn.setEnabled(has_track)
        if not has_track:
            if self._station is not None:
                self.star_btn.setToolTip("No track to favorite")
            else:
                self.star_btn.setToolTip("")

    def _on_star_clicked(self) -> None:
        if self._station is None or not self._last_icy_title:
            return
        is_fav = self._repo.is_favorited(self._station.name, self._last_icy_title)
        if is_fav:
            self._repo.remove_favorite(self._station.name, self._last_icy_title)
            self.star_btn.setChecked(False)
            self.star_btn.setIcon(
                QIcon.fromTheme("non-starred-symbolic", QIcon(":/icons/non-starred-symbolic.svg"))
            )
            self.star_btn.setToolTip("Save track to favorites")
            self.track_starred.emit(
                self._station.name, self._last_icy_title,
                self._station.provider_name or "", False
            )
        else:
            self._repo.add_favorite(
                self._station.name, self._station.provider_name or "",
                self._last_icy_title, ""
            )
            self.star_btn.setChecked(True)
            self.star_btn.setIcon(
                QIcon.fromTheme("starred-symbolic", QIcon(":/icons/starred-symbolic.svg"))
            )
            self.star_btn.setToolTip("Remove track from favorites")
            self.track_starred.emit(
                self._station.name, self._last_icy_title,
                self._station.provider_name or "", True
            )

    def _populate_stream_picker(self, station) -> None:
        """Populate stream picker combo for the bound station (D-19, D-20)."""
        streams = self._repo.list_streams(station.id)
        self._streams = streams
        self.stream_combo.blockSignals(True)
        self.stream_combo.clear()
        for s in streams:
            label = f"{s.quality} \u2014 {s.codec}" if s.codec else s.quality or s.label or "stream"
            self.stream_combo.addItem(label, userData=s.id)
        self.stream_combo.blockSignals(False)
        self.stream_combo.setVisible(len(streams) > 1)

    def _on_stream_selected(self, index: int) -> None:
        """User manually selected a stream from the picker (D-21)."""
        if index < 0 or not self._streams:
            return
        stream_id = self.stream_combo.itemData(index)
        for s in self._streams:
            if s.id == stream_id:
                self._player.play_stream(s)
                break

    def _sync_stream_picker(self, active_stream) -> None:
        """Sync stream picker to reflect failover-selected stream (D-22)."""
        if active_stream is None:
            return
        self.stream_combo.blockSignals(True)
        for i in range(self.stream_combo.count()):
            if self.stream_combo.itemData(i) == active_stream.id:
                self.stream_combo.setCurrentIndex(i)
                break
        self.stream_combo.blockSignals(False)

    def _on_edit_clicked(self) -> None:
        """Emit signal to open EditStationDialog for current station (D-08)."""
        if self._station is not None:
            self.edit_requested.emit(self._station)

    def _on_volume_changed_live(self, value: int) -> None:
        self._player.set_volume(value / 100.0)
        self.volume_slider.setToolTip(f"Volume: {value}%")

    def _on_volume_released(self) -> None:
        self._repo.set_setting("volume", str(self.volume_slider.value()))

    # ----------------------------------------------------------------------
    # Cover art (worker-thread adapter per RESEARCH §5 / D-19)
    # ----------------------------------------------------------------------

    def _fetch_cover_art_async(self, icy_title: str) -> None:
        self._cover_fetch_token += 1
        token = self._cover_fetch_token

        emit = self.cover_art_ready.emit  # bound Signal.emit — no self-capture

        def _cb(path_or_none):
            # Runs on worker thread — emit only, no widget access.
            # Pack token so _on_cover_art_ready can discard stale responses.
            emit(f"{token}:{path_or_none or ''}")

        fetch_cover_art(icy_title, _cb)

    def _on_cover_art_ready(self, payload: str) -> None:
        token_str, _, path = payload.partition(":")
        try:
            token = int(token_str)
        except ValueError:
            # Malformed payload — drop it rather than raising out of a Qt slot.
            # Slots-never-raise contract for queued connections. See WR-04.
            return
        if token != self._cover_fetch_token:
            return  # stale response — a newer fetch is in flight
        if not path:
            self._show_station_logo_in_cover_slot()
            return
        self._set_cover_pixmap(path)

    def _set_cover_pixmap(self, path: str) -> None:
        pix = QPixmap(path)
        if pix.isNull():
            self._show_station_logo_in_cover_slot()
            return
        scaled = pix.scaled(
            QSize(160, 160), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.cover_label.setPixmap(scaled)

    # ----------------------------------------------------------------------
    # Public accessor for cover pixmap (used by MainWindow media-keys bridge)
    # ----------------------------------------------------------------------

    def current_cover_pixmap(self) -> QPixmap | None:
        """Return the current cover-art pixmap, or None if label has no valid pixmap.

        Called by MainWindow._on_title_changed_for_media_keys to pass the
        cover art to the media-keys backend on every ICY title update (D-05).
        Returns None when the label's pixmap is null so callers can distinguish
        "no cover loaded" from "cover is present".
        """
        pix = self.cover_label.pixmap()
        if pix is None or pix.isNull():
            return None
        return pix

    # ----------------------------------------------------------------------
    # Station-logo fallbacks
    # ----------------------------------------------------------------------

    def _show_station_logo(self) -> None:
        path = self._station.station_art_path if self._station else None
        self.logo_label.setPixmap(_load_scaled_pixmap(path, QSize(180, 180)))

    def _show_station_logo_in_cover_slot(self) -> None:
        path = self._station.station_art_path if self._station else None
        self.cover_label.setPixmap(_load_scaled_pixmap(path, QSize(160, 160)))
