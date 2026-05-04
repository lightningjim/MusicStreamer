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

import logging
import os
from typing import Optional

from PySide6.QtCore import QEvent, QSize, Qt, QTimer, Signal
from PySide6.QtCore import QThread
from PySide6.QtGui import QFont, QIcon, QPalette, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
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
from musicstreamer.url_helpers import find_aa_siblings, render_sibling_html


_FALLBACK_ICON = ":/icons/audio-x-generic-symbolic.svg"

# Phase 60 60-10 / D-10a: cap upcoming queue rendering. The widget already has
# setMaximumHeight(180) (~6 rows visible without scroll), so 10 leaves scroll
# room without bloating the QListWidget item count. Mitigates T-60-10-03.
_GBS_QUEUE_MAX_ROWS = 10

_log = logging.getLogger(__name__)


class _GbsPollWorker(QThread):
    """Phase 60 D-06a / GBS-01c: poll gbs_api.fetch_active_playlist on a worker thread.

    Mirrors cover_art's worker-thread + Qt-queued signal pattern. Pitfall 1
    + Pitfall 5: token guard on the consuming side discards stale responses
    when station re-binds mid-poll.
    """

    playlist_ready = Signal(int, object)   # (token, state_dict)
    playlist_error = Signal(int, str)      # (token, msg or sentinel)

    def __init__(self, token: int, cookies, cursor=None, parent=None):
        super().__init__(parent)
        self._token = token
        self._cookies = cookies
        self._cursor = cursor

    def run(self):
        from musicstreamer import gbs_api
        try:
            state = gbs_api.fetch_active_playlist(self._cookies, cursor=self._cursor)
            self.playlist_ready.emit(self._token, state)
        except Exception as exc:
            if isinstance(exc, gbs_api.GbsAuthExpiredError):
                self.playlist_error.emit(self._token, "auth_expired")
            else:
                self.playlist_error.emit(self._token, str(exc))


class _GbsVoteWorker(QThread):
    """Phase 60 D-07a / GBS-01d: send a vote off the UI thread.

    Mirrors _GbsPollWorker shape (Plan 60-05). Pitfall 2: server is truth —
    payload includes the API-returned user_vote so the consumer can confirm
    or rollback the optimistic highlight.
    """
    # finished payload: (token, server_user_vote, prior_vote_for_rollback_record, score_str)
    vote_finished = Signal(int, int, int, str)
    # error payload: (token, prior_vote_for_rollback, msg_or_'auth_expired')
    vote_error = Signal(int, int, str)

    def __init__(self, token: int, entryid: int, vote_value: int,
                 cookies, prior_vote: int, parent=None):
        super().__init__(parent)
        self._token = token
        self._entryid = entryid
        self._vote_value = vote_value
        self._cookies = cookies
        self._prior_vote = prior_vote

    def run(self):
        from musicstreamer import gbs_api
        try:
            result = gbs_api.vote_now_playing(self._entryid, self._vote_value, self._cookies)
            server_vote = int(result.get("user_vote", 0))
            score = str(result.get("score", ""))
            self.vote_finished.emit(self._token, server_vote, self._prior_vote, score)
        except Exception as exc:
            if isinstance(exc, gbs_api.GbsAuthExpiredError):
                self.vote_error.emit(self._token, self._prior_vote, "auth_expired")
            else:
                self.vote_error.emit(self._token, self._prior_vote, str(exc))


class _MutedLabel(QLabel):
    """QLabel that renders WindowText in the Disabled palette color and
    re-applies the muted color whenever the application palette changes.

    Phase 47.1 D-10: stats-for-nerds rows read dimmer than primary labels.
    IN-03 / UAT follow-up: static palette capture broke on light/dark theme
    flips; overriding ``changeEvent`` keeps the muted color in sync.
    """

    def __init__(self, text: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(text, parent)
        self._apply_muted_palette()

    def _apply_muted_palette(self) -> None:
        pal = self.palette()
        muted = pal.color(QPalette.Disabled, QPalette.WindowText)
        pal.setColor(QPalette.WindowText, muted)
        self.setPalette(pal)

    def changeEvent(self, event: QEvent) -> None:  # type: ignore[override]
        if event.type() in (QEvent.PaletteChange, QEvent.StyleChange):
            self._apply_muted_palette()
        super().changeEvent(event)


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

    # Emitted when the user stops playback via the in-panel Stop button (not via OS media key).
    stopped_by_user = Signal()

    # Phase 64 / D-02: emitted when user clicks an 'Also on:' sibling link.
    # Payload is the resolved sibling Station; MainWindow connects to
    # _on_sibling_activated which delegates to _on_station_activated to switch
    # active playback. Mirrors edit_requested in payload shape (Station via
    # Signal(object)).
    sibling_activated = Signal(object)

    # Phase 60 D-07a: fire on vote failure so MainWindow.show_toast surfaces
    # the error to the user. Mirrors track_starred pattern — forward via bound
    # method connection (QA-05).
    gbs_vote_error_toast = Signal(str)

    def __init__(self, player, repo, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._player = player
        self._repo = repo
        self._station: Optional[Station] = None
        self._cover_fetch_token: int = 0
        self._last_cover_icy: Optional[str] = None
        self._is_playing: bool = False
        self._is_stopped: bool = False  # True after full stop (vs pause); cleared on bind/play
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

        # Phase 64 / D-01, D-05, D-05a: cross-network "Also on:" sibling line.
        # Mirrors EditStationDialog._sibling_label config at edit_station_dialog.py:405-411.
        # First QLabel in NowPlayingPanel to use Qt.RichText (deviation from
        # T-39-01 PlainText convention) -- required for inline <a href> links.
        # Mitigation: html.escape on every Station.name interpolation inside
        # render_sibling_html (Plan 01, url_helpers.py). Network display names
        # come from the NETWORKS compile-time constant; the href payload is
        # integer-only ("sibling://{id}") so it cannot carry injectable content.
        # Hidden until populated (D-05) -- QVBoxLayout reclaims zero vertical
        # space for hidden children.
        # UI-SPEC font lock: NO setFont call (inherits Qt platform default,
        # parity with Phase 51 dialog version).
        self._sibling_label = QLabel("", self)
        self._sibling_label.setTextFormat(Qt.RichText)
        self._sibling_label.setOpenExternalLinks(False)
        self._sibling_label.setVisible(False)
        # QA-05: bound-method connection (no self-capturing lambda).
        self._sibling_label.linkActivated.connect(self._on_sibling_link_activated)
        center.addWidget(self._sibling_label)

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

        # Phase 47.2 D-08: EQ toggle -- A/B compare corrected vs flat without
        # opening the dialog. Mirrors star_btn shape (28x28 checkable icon-only).
        self.eq_toggle_btn = QToolButton(self)
        self.eq_toggle_btn.setIconSize(QSize(20, 20))
        self.eq_toggle_btn.setFixedSize(28, 28)
        self.eq_toggle_btn.setCheckable(True)
        self.eq_toggle_btn.setIcon(
            QIcon.fromTheme(
                "multimedia-equalizer-symbolic",
                QIcon(":/icons/multimedia-equalizer-symbolic.svg"),
            )
        )
        self.eq_toggle_btn.setToolTip("Toggle EQ")
        self.eq_toggle_btn.setChecked(
            self._repo.get_setting("eq_enabled", "0") == "1"
        )
        self.eq_toggle_btn.clicked.connect(self._on_eq_toggled)
        controls.addWidget(self.eq_toggle_btn)

        self.volume_slider = QSlider(Qt.Horizontal, self)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setFixedWidth(120)
        self.volume_slider.setTickPosition(QSlider.NoTicks)
        controls.addWidget(self.volume_slider)

        controls.addStretch(1)
        center.addLayout(controls)

        # Phase 47.1 stats widget (D-07: last center-column item; D-08: always constructed)
        # Default hidden (D-05); MainWindow drives visibility after construction
        # from the QAction's checked state so menu and panel cannot desync (WR-02).
        self._stats_widget = self._build_stats_widget()
        center.addWidget(self._stats_widget)

        # === Phase 60 D-06: GBS.FM active-playlist widget (hide-when-empty) ===
        # Phase 64 _sibling_label precedent — invisible until populated.
        # Pitfall 11: PlainText for gbs.fm-side strings (artist/title/score).
        self._gbs_playlist_widget = QListWidget(self)
        self._gbs_playlist_widget.setVisible(False)
        self._gbs_playlist_widget.setMaximumHeight(180)  # ~6 rows; lets controls keep prominence
        center.addWidget(self._gbs_playlist_widget)

        # Phase 60 D-06a RESOLVED: 15s poll cadence (matches gbs.fm web UI DELAY=15000)
        self._gbs_poll_timer = QTimer(self)
        self._gbs_poll_timer.setInterval(15000)
        self._gbs_poll_timer.timeout.connect(self._on_gbs_poll_tick)  # QA-05

        # Pitfall 1 + cover_art precedent: stale-response token guard
        self._gbs_poll_token: int = 0
        self._gbs_poll_worker = None  # SYNC-05 retention slot

        # Cursor for the /ajax endpoint — advanced by every successful poll.
        self._gbs_poll_cursor: dict = {}

        # === Phase 60 D-07: GBS.FM vote control (5 buttons, 1-5 score) ===
        # RESEARCH §Claude's Discretion: 5 separate buttons (NOT thumb-up/down) —
        # gbs.fm uses a 1-5 score system. setCheckable(True) lets us highlight
        # the user's current vote. Pitfall 11: PlainText on the labels (default).
        self._gbs_vote_row = QHBoxLayout()
        self._gbs_vote_row.setSpacing(4)
        self._gbs_vote_buttons: list = []
        for v in range(1, 6):
            btn = QPushButton(str(v), self)
            btn.setCheckable(True)
            btn.setVisible(False)
            btn.setProperty("vote_value", v)
            btn.setMinimumWidth(32)
            btn.setMaximumWidth(48)
            btn.clicked.connect(self._on_gbs_vote_clicked)  # QA-05 bound method
            btn.setEnabled(False)  # 60-09 / T10: disabled until /ajax stamps entryid (PINNED: after connect — wiring intact, button intentionally not yet usable)
            self._gbs_vote_row.addWidget(btn)
            self._gbs_vote_buttons.append(btn)
        # Add the vote row to center layout below the playlist widget.
        center.addLayout(self._gbs_vote_row)

        # Pitfall 1: entryid stamps ONLY from /ajax now_playing event
        self._gbs_current_entryid: Optional[int] = None

        # Pitfall 2 + cover_art precedent: stale-vote-response token guard
        self._gbs_vote_token: int = 0
        self._gbs_vote_worker = None  # SYNC-05 retain

        # BLOCKER 1 fix: server-confirmed vote tracked separately from
        # _current_highlighted_vote() (Qt toggles checkable buttons before
        # `clicked` fires, so post-toggle highlight is unreliable for the
        # "is this a vote-clear?" check).
        self._last_confirmed_vote: int = 0

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

    @property
    def is_playing(self) -> bool:
        """Read-only access to current playback state."""
        return self._is_playing

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
        # Phase 64 / D-04: re-derive 'Also on:' line for the newly bound station.
        # This is the ONLY call site for _refresh_siblings -- D-04 invariant
        # (locked by test_refresh_siblings_runs_once_per_bind_station_call).
        self._refresh_siblings()
        # Phase 60 D-06: re-derive GBS active-playlist visibility for the
        # newly bound station. Phase 64 D-04 invariant — _refresh_gbs_visibility
        # is the ONLY call site (test_refresh_gbs_visibility_runs_once_per_bind_station
        # locks this).
        self._refresh_gbs_visibility()

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

    def set_buffer_percent(self, percent: int) -> None:
        """Update the buffer indicator bar + {N}% label atomically (D-11). Phase 47.1."""
        self.buffer_bar.setValue(int(percent))
        self.buffer_pct_label.setText(f"{int(percent)}%")

    def set_stats_visible(self, visible: bool) -> None:
        """Toggle the stats-for-nerds wrapper visibility (D-07). Phase 47.1."""
        self._stats_widget.setVisible(bool(visible))

    # ----------------------------------------------------------------------
    # Internal slots
    # ----------------------------------------------------------------------

    def _on_play_pause_clicked(self) -> None:
        if self._is_playing:
            self._player.pause()
            self.on_playing_state_changed(False)
        elif self._station is not None:
            if self._is_stopped:
                self.bind_station(self._station)
                self._is_stopped = False
            self._player.play(self._station)
            self.on_playing_state_changed(True)

    def _on_stop_clicked(self) -> None:
        self._player.stop()
        self.on_playing_state_changed(False)
        self._is_stopped = True
        self.stopped_by_user.emit()
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
                self.star_btn.setToolTip("No station selected")

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

    def _on_eq_toggled(self, checked: bool) -> None:
        """Phase 47.2 D-08: Wire the toggle to Player + persist enable state (D-15)."""
        self._player.set_eq_enabled(checked)
        self._repo.set_setting("eq_enabled", "1" if checked else "0")

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

    # ----------------------------------------------------------------------
    # Phase 64 / D-01..D-08 -- cross-network sibling list (BUG-02 follow-up)
    # ----------------------------------------------------------------------

    def _refresh_siblings(self) -> None:
        """Phase 64 / D-04, D-05: refresh the 'Also on:' label for the bound station.

        Reads self._station.streams[0].url, scans repo.list_stations() for AA
        siblings on different networks, then either populates _sibling_label
        with HTML or hides it entirely (zero vertical space when no siblings).

        Hidden-when-empty (D-05) covers four cases:
          1. self._station is None (panel never bound).
          2. self._station.streams is empty (defensive -- find_aa_siblings
             returns [] for empty current_first_url anyway).
          3. Bound station is non-AA -> find_aa_siblings returns [].
          4. AA station with a key but no other AA stations on other networks
             share the key -> returns [].
        """
        if self._station is None or not self._station.streams:
            self._sibling_label.setVisible(False)
            self._sibling_label.setText("")
            return
        current_url = self._station.streams[0].url
        # Defense-in-depth (REVIEW WR-01): repo.list_stations() can in principle
        # raise on transient DB failures; this method runs from bind_station()
        # which is on the Qt slot path. Slots-never-raise -- on failure, hide
        # the label and bail silently.
        try:
            all_stations = self._repo.list_stations()
        except Exception:
            self._sibling_label.setVisible(False)
            self._sibling_label.setText("")
            return
        siblings = find_aa_siblings(
            stations=all_stations,
            current_station_id=self._station.id,
            current_first_url=current_url,
        )
        if not siblings:
            self._sibling_label.setVisible(False)
            self._sibling_label.setText("")
            return
        self._sibling_label.setText(
            render_sibling_html(siblings, self._station.name)
        )
        self._sibling_label.setVisible(True)

    def _on_sibling_link_activated(self, href: str) -> None:
        """Phase 64 / D-02, D-08: parse the sibling href, look up the Station,
        emit sibling_activated.

        Mirrors EditStationDialog._on_sibling_link_activated (lines 1004-1051) but
        has no dirty-state confirm path -- the panel has no editable form. The
        surface contract is 'user clicked a sibling -> switch playback to it',
        not 'user clicked a sibling -> navigate to its editor'.

        Dual-shape repo.get_station handling (RESEARCH Pitfall #2):
          - Production Repo.get_station raises ValueError on miss (repo.py:271).
          - Some test doubles (MainWindow.FakeRepo) return None.
        Wrap in try/except Exception + check `is None` to be safe in both
        shapes. Qt slots-never-raise: bail silently on any failure path.
        """
        prefix = "sibling://"
        if not href.startswith(prefix):
            return
        try:
            sibling_id = int(href[len(prefix):])
        except ValueError:
            return
        # D-08 defense-in-depth: silent no-op if no station bound, or if the
        # sibling id matches the bound station (find_aa_siblings excludes self
        # at url_helpers.py:122, but rendering staleness could theoretically
        # allow a stale link).
        if self._station is None or self._station.id == sibling_id:
            return
        try:
            sibling = self._repo.get_station(sibling_id)
        except Exception:
            return
        if sibling is None:
            return
        self.sibling_activated.emit(sibling)

    # ----------------------------------------------------------------------
    # Phase 60 / GBS-01c: active-playlist widget handlers (D-06/D-06a/D-06b)
    # ----------------------------------------------------------------------

    def _is_gbs_logged_in(self) -> bool:
        """Phase 60 D-04 ladder #3: true if cookies file exists."""
        from musicstreamer import paths
        return os.path.exists(paths.gbs_cookies_path())

    def _refresh_gbs_visibility(self) -> None:
        """Phase 60 D-06: show widget iff GBS.FM station bound AND logged in.

        Side effect: starts the 15s poll timer when shown; stops when hidden.
        Pitfall 5 — pause polling when not visible.
        """
        is_gbs = (self._station is not None
                  and self._station.provider_name == "GBS.FM")
        logged_in = self._is_gbs_logged_in()
        should_show = is_gbs and logged_in

        self._gbs_playlist_widget.setVisible(should_show)

        if should_show:
            # Reset cursor on station change — fresh start
            self._gbs_poll_cursor = {}
            self._gbs_playlist_widget.clear()
            placeholder = QListWidgetItem("Loading playlist…")
            self._gbs_playlist_widget.addItem(placeholder)
            # Trigger an immediate first poll (don't wait 15s)
            self._on_gbs_poll_tick()
            if not self._gbs_poll_timer.isActive():
                self._gbs_poll_timer.start()
        else:
            self._gbs_poll_timer.stop()
            self._gbs_playlist_widget.clear()

        # Phase 60 D-07: vote buttons share the same auth+provider gate.
        for btn in self._gbs_vote_buttons:
            btn.setVisible(should_show)
        if not should_show:
            # Reset highlighting when leaving GBS context
            for btn in self._gbs_vote_buttons:
                btn.setChecked(False)
            self._gbs_current_entryid = None
            self._apply_vote_buttons_enabled(False)  # 60-09 / T10: leaving GBS context, re-disable

    def _on_gbs_poll_tick(self) -> None:
        """Phase 60 D-06a: kick a worker that hits /ajax with the cursor."""
        from musicstreamer import gbs_api
        cookies = gbs_api.load_auth_context()
        if cookies is None:
            # Auth disappeared mid-poll — refresh visibility (which will stop timer)
            self._refresh_gbs_visibility()
            return
        self._gbs_poll_token += 1
        token = self._gbs_poll_token
        worker = _GbsPollWorker(
            token, cookies, cursor=dict(self._gbs_poll_cursor), parent=self
        )
        worker.playlist_ready.connect(self._on_gbs_playlist_ready)  # QA-05
        worker.playlist_error.connect(self._on_gbs_playlist_error)  # QA-05
        self._gbs_poll_worker = worker  # SYNC-05 retain
        worker.start()

    def _on_gbs_playlist_ready(self, token: int, state) -> None:
        """Render the playlist state. Pitfall 1 — discard stale tokens.

        HIGH 4 fix: `position` is a seconds-into-current-song cursor, NOT a
        monotonic pagination cursor. When the `now_playing` entryid changes
        (track transition), we MUST reset position=0 — carrying the previous
        song's `song_position` into the next /ajax call gives gbs.fm a stale
        delta reference. Track changes detected by comparing new entryid
        against the previously-seen one.
        """
        if token != self._gbs_poll_token:
            return  # stale — newer poll in flight
        # Advance cursor for next tick
        new_entryid = state.get("now_playing_entryid")
        prev_entryid = self._gbs_poll_cursor.get("now_playing")
        track_changed = (
            new_entryid is not None and new_entryid != prev_entryid
        )
        if new_entryid is not None:
            self._gbs_poll_cursor["now_playing"] = new_entryid
        if state.get("last_removal_id") is not None:
            self._gbs_poll_cursor["last_removal"] = state["last_removal_id"]
        if track_changed:
            # HIGH 4 fix: reset position cursor on track transition.
            self._gbs_poll_cursor["position"] = 0
        elif state.get("song_position") is not None:
            try:
                self._gbs_poll_cursor["position"] = int(state["song_position"])
            except (TypeError, ValueError):
                pass
        # Phase 60 D-07 / Pitfall 1: entryid captured ONLY from /ajax response
        if new_entryid is not None:
            new_entryid_int = int(new_entryid)
            if new_entryid_int != self._gbs_current_entryid:
                self._gbs_current_entryid = new_entryid_int
            self._apply_vote_buttons_enabled(True)  # 60-09 / T10: entryid known, buttons usable
        # Pitfall 2 / D-07d: server's userVote is the source of truth
        confirmed_vote = int(state.get("user_vote", 0) or 0)
        self._apply_vote_highlight(confirmed_vote)
        self._last_confirmed_vote = confirmed_vote  # BLOCKER 1 fix — drives vote-clear logic
        # Render: clear + add now-playing row + parsed queue rows.
        # Pitfall 11 — PlainText for everything; QListWidgetItem default is PlainText.
        self._gbs_playlist_widget.clear()
        icy = state.get("icy_title")
        if icy:
            # Pitfall 11: PlainText (QListWidgetItem default).
            self._gbs_playlist_widget.addItem(QListWidgetItem(f"▶ {icy}"))
        # 60-10 / T8: enumerate upcoming queue from parsed rows (per D-10a max 10 rows).
        queue_rows = state.get("queue_rows") or []
        for n, row in enumerate(queue_rows[:_GBS_QUEUE_MAX_ROWS], start=1):
            artist = (row.get("artist") or "").strip()
            title = (row.get("title") or "").strip()
            duration = (row.get("duration") or "").strip()
            # D-10b: "{n}. {artist} - {title} [{duration}]"
            if duration:
                label = f"{n}. {artist} - {title} [{duration}]"
            else:
                label = f"{n}. {artist} - {title}"
            self._gbs_playlist_widget.addItem(QListWidgetItem(label))
        # D-10c: pllength summary intentionally not rendered ('dongs' jargon).
        score = state.get("score")
        if score:
            self._gbs_playlist_widget.addItem(QListWidgetItem(f"Score: {score}"))

    def _on_gbs_playlist_error(self, token: int, msg: str) -> None:
        """Auth expiry -> hide widget + stop timer; other errors -> silent log."""
        if token != self._gbs_poll_token:
            return
        if msg == "auth_expired":
            # Pitfall 3: don't toast-spam on every poll tick; just hide.
            self._gbs_playlist_widget.setVisible(False)
            self._gbs_poll_timer.stop()
            self._gbs_playlist_widget.clear()
        else:
            # Pitfall 5 + 7: don't retry; just log.
            _log.warning("GBS.FM playlist poll failed: %s", msg)

    # ----------------------------------------------------------------------
    # Phase 60 / GBS-01d: vote control handlers (D-07a/D-07b/D-07c/D-07d)
    # ----------------------------------------------------------------------

    def _apply_vote_buttons_enabled(self, enabled: bool) -> None:
        """Phase 60 60-09 / T10: gate vote-button affordance behind entryid stamp.

        Disabled when no entryid is known (no successful /ajax poll yet) or
        when leaving GBS context entirely. Enabled once /ajax confirms the
        current playing entryid.
        """
        for btn in self._gbs_vote_buttons:
            btn.setEnabled(bool(enabled))

    def _apply_vote_highlight(self, vote_value: int) -> None:
        """Highlight the button matching vote_value; clear all others.

        vote_value=0 means no vote — all buttons unchecked.
        """
        for btn in self._gbs_vote_buttons:
            btn.setChecked(int(btn.property("vote_value") or 0) == int(vote_value))

    def _current_highlighted_vote(self) -> int:
        """Return the currently-highlighted vote value, or 0 if none."""
        for btn in self._gbs_vote_buttons:
            if btn.isChecked():
                v = btn.property("vote_value")
                try:
                    return int(v)
                except (TypeError, ValueError):
                    return 0
        return 0

    def _on_gbs_vote_clicked(self) -> None:
        """D-07 / D-07a: optimistic UI + worker-thread vote round-trip.

        Pitfall 1: requires self._gbs_current_entryid (sourced from /ajax).
        Pitfall 2: optimistic highlight will be CONFIRMED or ROLLED BACK
        by the worker's signal handlers — server is truth.

        BLOCKER 1 fix: read `prior_vote` from self._last_confirmed_vote, NOT
        from _current_highlighted_vote(). Qt toggles a checkable QPushButton's
        check state BEFORE emitting `clicked`, so reading the highlight here
        gives the post-toggle value (always wrong by one click).
        self._last_confirmed_vote is set by _on_gbs_playlist_ready from
        /ajax responses and by _on_gbs_vote_finished from vote round-trips —
        always reflects what the server thinks the user's vote is.
        """
        from musicstreamer import gbs_api
        sender = self.sender()
        if sender is None or self._gbs_current_entryid is None:
            return  # No track context — ignore the click
        try:
            vote_value = int(sender.property("vote_value"))
        except (TypeError, ValueError):
            return
        prior_vote = self._last_confirmed_vote  # BLOCKER 1 fix
        # If clicking the SAME button that's already server-confirmed, this is
        # a vote-0 (clear) per RESEARCH §Capability 4.
        if vote_value == prior_vote:
            submit_value = 0
            optimistic_value = 0
        else:
            submit_value = vote_value
            optimistic_value = vote_value
        # OPTIMISTIC highlight (will be confirmed by server response)
        self._apply_vote_highlight(optimistic_value)

        cookies = gbs_api.load_auth_context()
        if cookies is None:
            # 60-09 / T11: surface the silent auth-disappeared rollback as a toast
            # so the user knows why the optimistic highlight reverted.
            self.gbs_vote_error_toast.emit("GBS.FM session expired — reconnect via Accounts")
            # Auth disappeared — rollback + refresh visibility
            self._apply_vote_highlight(prior_vote)
            self._refresh_gbs_visibility()
            return

        self._gbs_vote_token += 1
        token = self._gbs_vote_token
        worker = _GbsVoteWorker(
            token=token,
            entryid=int(self._gbs_current_entryid),
            vote_value=submit_value,
            cookies=cookies,
            prior_vote=prior_vote,
            parent=self,
        )
        worker.vote_finished.connect(self._on_gbs_vote_finished)  # QA-05
        worker.vote_error.connect(self._on_gbs_vote_error)        # QA-05
        self._gbs_vote_worker = worker  # SYNC-05 retain
        worker.start()

    def _on_gbs_vote_finished(self, token: int, server_user_vote: int,
                              prior_vote: int, score: str) -> None:
        """Pitfall 2: server is source of truth; apply server-returned vote.

        BLOCKER 1 fix: also stash the server-confirmed value into
        self._last_confirmed_vote so the NEXT click computes prior_vote
        correctly (vote-clear logic depends on this).
        """
        if token != self._gbs_vote_token:
            return
        self._apply_vote_highlight(int(server_user_vote))
        self._last_confirmed_vote = int(server_user_vote)  # BLOCKER 1 fix

    def _on_gbs_vote_error(self, token: int, prior_vote: int, msg: str) -> None:
        """Pitfall 2 + Pitfall 7: rollback to prior_vote; surface error."""
        if token != self._gbs_vote_token:
            return
        self._apply_vote_highlight(int(prior_vote))
        if msg == "auth_expired":
            self.gbs_vote_error_toast.emit("GBS.FM session expired — reconnect via Accounts")
        else:
            truncated = (msg[:60] + "…") if len(msg) > 60 else msg
            self.gbs_vote_error_toast.emit(f"Vote failed: {truncated}")

    # ----------------------------------------------------------------------
    # Phase 47.1: Stats-for-nerds widget construction (D-07/D-08/D-09/D-10)
    # ----------------------------------------------------------------------

    def _build_stats_widget(self) -> QWidget:
        """Construct the stats-for-nerds wrapper (D-07/D-08/D-09). Phase 47.1."""
        wrapper = QWidget(self)
        form = QFormLayout(wrapper)
        form.setContentsMargins(0, 0, 0, 0)

        # Row label -- muted palette (D-10; RESEARCH §6 Option A: QPalette.Disabled).
        # _MutedLabel re-applies the muted color on palette/theme changes so
        # light<->dark flips stay readable (UAT follow-up).
        buffer_row_label = _MutedLabel("Buffer", wrapper)

        # Value side: QProgressBar + {N}% QLabel inside a QHBoxLayout
        value_row = QWidget(wrapper)
        value_layout = QHBoxLayout(value_row)
        value_layout.setContentsMargins(0, 0, 0, 0)
        value_layout.setSpacing(6)
        self.buffer_bar = QProgressBar(value_row)
        self.buffer_bar.setRange(0, 100)
        self.buffer_bar.setTextVisible(False)  # D-01: label next to it is authoritative
        self.buffer_bar.setFixedWidth(120)     # D-02
        # UAT follow-up: percent label also muted + theme-responsive; previous
        # version used a plain QLabel that went unreadable on theme flip.
        self.buffer_pct_label = _MutedLabel("0%", value_row)
        value_layout.addWidget(self.buffer_bar)
        value_layout.addWidget(self.buffer_pct_label)
        value_layout.addStretch(1)

        form.addRow(buffer_row_label, value_row)
        # D-05: default hidden. MainWindow drives visibility from the QAction's
        # checked state after construction (WR-02: single source of truth).
        wrapper.setVisible(False)
        return wrapper
