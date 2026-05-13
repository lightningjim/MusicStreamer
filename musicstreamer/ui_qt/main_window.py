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

import datetime
import logging
import os
import time
from importlib.metadata import version as _pkg_version

# Side-effect import: registers the :/icons/ resource prefix before any
# QIcon lookup. Must live at module top so tests that construct MainWindow
# (not just the GUI entry point) also get resources registered — per
# Phase 36 research Pitfall 2 and D-24.
from musicstreamer.ui_qt import icons_rc  # noqa: F401

from PySide6.QtCore import QEvent, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QCursor, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QWidget,
)
from PySide6.QtCore import QStandardPaths

from musicstreamer import settings_export
from musicstreamer.hi_res import best_tier_for_station
from musicstreamer.repo import db_connect

from musicstreamer import media_keys
from musicstreamer.media_keys.base import NoOpMediaKeysBackend
from musicstreamer.models import Station

_log = logging.getLogger(__name__)

# ----------------------------------------------------------------------------
# Phase 72 / LAYOUT-01 / D-13 — Hover-to-peek tuning constants
# ----------------------------------------------------------------------------
# Trigger zone width (px): the cursor must be within the LEFT N pixels of the
# centralWidget to arm the dwell timer. 4 is the narrowest end of the
# CONTEXT D-13 4-6px band, chosen to fully eliminate accidental-trigger drift
# during cursor crossings.
_PEEK_TRIGGER_ZONE_PX = 4
# Dwell timer length (ms): how long the cursor must remain inside the trigger
# zone before the overlay opens. 280ms sits mid-band of CONTEXT D-13's
# 250-300ms band and matches Qt's stock tooltip cadence.
_PEEK_DWELL_MS = 280
# Fallback peek-overlay width (px): used when no pre-compact splitter
# snapshot is available (e.g., the user toggles compact before ever resizing).
# Matches the splitter design-default left width at main_window.py:285
# (`self._splitter.setSizes([360, 840])`).
_PEEK_FALLBACK_WIDTH_PX = 360


from musicstreamer.ui_qt.accent_color_dialog import AccentColorDialog
from musicstreamer.ui_qt.accounts_dialog import AccountsDialog
from musicstreamer.ui_qt.edit_station_dialog import EditStationDialog
from musicstreamer.ui_qt.discovery_dialog import DiscoveryDialog
from musicstreamer.ui_qt.import_dialog import ImportDialog
from musicstreamer.ui_qt.now_playing_panel import NowPlayingPanel
from musicstreamer.ui_qt.station_list_panel import StationListPanel
from musicstreamer.ui_qt.station_list_peek_overlay import StationListPeekOverlay
from musicstreamer.ui_qt.toast import ToastOverlay
from musicstreamer.accent_utils import apply_accent_palette, _is_valid_hex


class _ExportWorker(QThread):
    finished = Signal(str)   # emits dest_path on success
    error = Signal(str)

    def __init__(self, dest_path: str, parent=None):
        super().__init__(parent)
        self._dest_path = dest_path

    def run(self):
        try:
            from musicstreamer.repo import Repo
            repo = Repo(db_connect())
            settings_export.build_zip(repo, self._dest_path)
            self.finished.emit(self._dest_path)
        except Exception as exc:
            self.error.emit(str(exc))


class _ImportPreviewWorker(QThread):
    finished = Signal(object)   # emits ImportPreview
    error = Signal(str)

    def __init__(self, zip_path: str, parent=None):
        super().__init__(parent)
        self._zip_path = zip_path

    def run(self):
        try:
            from musicstreamer.repo import Repo
            repo = Repo(db_connect())
            result = settings_export.preview_import(self._zip_path, repo)
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class _GbsImportWorker(QThread):
    """Phase 60 D-02 / GBS-01a: kick gbs_api.import_station() off the UI thread.

    Mirrors _ExportWorker shape (main_window.py:64-79). Pitfall 3 — emits the
    sentinel string ``"auth_expired"`` via the error signal when the gbs_api
    raises GbsAuthExpiredError so the UI surfaces a re-auth prompt instead
    of the raw exception text.
    """
    finished = Signal(int, int)   # (inserted, updated) per import_station signature
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        try:
            from musicstreamer.repo import Repo
            from musicstreamer import gbs_api
            repo = Repo(db_connect())
            inserted, updated = gbs_api.import_station(repo)
            self.finished.emit(int(inserted), int(updated))
        except Exception as exc:
            from musicstreamer import gbs_api
            if isinstance(exc, gbs_api.GbsAuthExpiredError):
                self.error.emit("auth_expired")
            else:
                self.error.emit(str(exc))


class MainWindow(QMainWindow):
    """Main application window — station list + now-playing + toast overlay."""

    # Phase 70 — quality_map fan-out (DS-01); payload is dict[int, str] keyed on station_id.
    # Signal(object) mirrors Phase 68 live_map_changed = Signal(object) pattern —
    # PySide6 cannot carry a Python dict as a typed Signal arg without copy errors.
    quality_map_changed = Signal(object)

    # Phase 62 / D-08 / BUG-09: cooldown for the `Buffering…` toast.
    # 10 seconds, wall-clock-based via time.monotonic; persists across station
    # changes so rapid hops don't spam the user.
    _UNDERRUN_TOAST_COOLDOWN_S: float = 10.0

    def __init__(
        self,
        player,
        repo,
        *,
        node_runtime=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._player = player
        self._repo = repo
        self._node_runtime = node_runtime

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

        # Group 1: New + Discovery + Import (D-01, D-14, D-15)
        act_new = self._menu.addAction("New Station")
        act_new.triggered.connect(self._on_new_station_clicked)

        act_discover = self._menu.addAction("Discover Stations")
        act_discover.triggered.connect(self._open_discovery_dialog)

        act_import = self._menu.addAction("Import Stations")
        act_import.triggered.connect(self._open_import_dialog)

        # Phase 60 D-02 / GBS-01a: idempotent multi-quality GBS.FM import
        act_gbs_add = self._menu.addAction("Add GBS.FM")
        act_gbs_add.triggered.connect(self._on_gbs_add_clicked)  # QA-05 bound method

        # Phase 60 D-08a / GBS-01e: search-and-submit dialog
        act_gbs_search = self._menu.addAction("Search GBS.FM…")  # U+2026 ellipsis
        act_gbs_search.triggered.connect(self._open_gbs_search_dialog)  # QA-05

        self._menu.addSeparator()

        # Group 2: Settings dialogs (D-16, D-17, D-18)
        # Phase 66 D-15 / THEME-01: Theme picker — peer above Accent Color.
        act_theme = self._menu.addAction("Theme")
        act_theme.triggered.connect(self._open_theme_dialog)  # QA-05 bound method

        # Phase 67 / S-01, M-01: Show similar stations master toggle.
        # Placed in Settings group (D-16) adjacent to Theme picker per
        # CONTEXT.md M-01. Mirrors Phase 47.1 _act_stats shape verbatim
        # (lines 205-210) — checkable QAction + initial state from
        # persisted setting + bound-method connect (QA-05).
        self._act_show_similar = self._menu.addAction("Show similar stations")
        self._act_show_similar.setCheckable(True)
        self._act_show_similar.setChecked(
            self._repo.get_setting("show_similar_stations", "0") == "1"
        )
        self._act_show_similar.toggled.connect(self._on_show_similar_toggled)  # QA-05

        act_accent = self._menu.addAction("Accent Color")
        act_accent.triggered.connect(self._open_accent_dialog)

        act_accounts = self._menu.addAction("Accounts")
        act_accounts.triggered.connect(self._open_accounts_dialog)

        # Phase 47.2 D-07: Equalizer action in Group 2 (Settings-style dialogs).
        act_equalizer = self._menu.addAction("Equalizer")
        act_equalizer.triggered.connect(self._open_equalizer_dialog)

        self._menu.addSeparator()

        # Phase 47.1 D-03: Stats for Nerds toggle -- its own menu group.
        self._act_stats = self._menu.addAction("Stats for Nerds")
        self._act_stats.setCheckable(True)
        self._act_stats.setChecked(
            self._repo.get_setting("show_stats_for_nerds", "0") == "1"
        )
        self._act_stats.toggled.connect(self._on_stats_toggled)
        self._menu.addSeparator()

        # Group 3: Export/Import Settings (SYNC-05)
        # Keep refs so we can disable the actions while a worker is running
        # (UI-REVIEW fix #1: prevent double-starts during background export/preview).
        self._act_export = self._menu.addAction("Export Settings")
        self._act_export.triggered.connect(self._on_export_settings)
        self._act_import_settings = self._menu.addAction("Import Settings")
        self._act_import_settings.triggered.connect(self._on_import_settings)

        # Worker reference retention (SYNC-05) — prevents GC before thread finishes
        self._export_worker: QThread | None = None
        self._import_preview_worker: QThread | None = None

        # Phase 44 D-13 part 3: persistent Node-missing indicator. Added AFTER
        # existing Group 3 to keep menu order stable; only surfaces when
        # node_runtime was passed AND Node is absent. The "⚠" warning glyph
        # matches the existing copywriting convention (e.g., "…" ellipsis).
        if self._node_runtime is not None and not self._node_runtime.available:
            self._menu.addSeparator()
            self._act_node_missing = self._menu.addAction(
                "⚠ Node.js: Missing (click to install)"
            )
            self._act_node_missing.triggered.connect(self._on_node_install_clicked)

        # Phase 65 D-01/D-02/D-03/D-12 (VER-02): version footer. Always last, always
        # disabled. Read via importlib.metadata so this works without _run_gui having
        # been called (test fixtures construct MainWindow without going through
        # __main__._run_gui, so QCoreApplication.applicationVersion() returns "" in
        # tests on Linux — RESEARCH Landmine 1).
        self._menu.addSeparator()
        self._act_version = self._menu.addAction(f"v{_pkg_version('musicstreamer')}")
        self._act_version.setEnabled(False)

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
        # Phase 72 / D-10 / Pitfall 1+5: in-memory splitter-size snapshot
        # for compact-mode round-trip. None when expanded; list[int] while
        # compact mode is ON. Reset to None on every restore — see
        # _on_compact_toggle for the snapshot-before-hide / reset-after-
        # restore ordering. NOT persisted (D-09 session-only).
        # ------------------------------------------------------------------
        self._splitter_sizes_before_compact: list[int] | None = None
        # Plan 04 will lazy-construct these for the hover-peek overlay. Plan
        # 03 declares the attributes so the toggle slot can refer to the
        # peek-related stubs without AttributeError on first toggle.
        self._peek_overlay = None
        self._peek_dwell_timer = None

        # ------------------------------------------------------------------
        # Toast overlay — parented to centralWidget, anchored bottom-centre.
        # D-09/D-10: constructed AFTER centralWidget is set.
        # ------------------------------------------------------------------
        self._toast = ToastOverlay(self)

        # Phase 62 / D-08 / BUG-09: cooldown bookkeeping for `Buffering…` toast.
        # time.monotonic() is wall-clock-jump immune (NTP / DST safe).
        self._last_underrun_toast_ts: float = 0.0

        # Phase 60 D-02: GBS.FM import worker retention (SYNC-05)
        self._gbs_import_worker = None

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
        self._player.buffer_percent.connect(self.now_playing.set_buffer_percent)

        # Player → toast notifications (D-11)
        self._player.failover.connect(self._on_failover)
        self._player.offline.connect(self._on_offline)
        self._player.playback_error.connect(self._on_playback_error)
        self._player.cookies_cleared.connect(self.show_toast)  # Phase 999.7
        # Phase 62 / D-07-D-08 / BUG-09: dwell-elapsed → cooldown-gated toast.
        # Queued connection per file convention (Player Signals are queued to
        # MainWindow throughout this file). Bound method per QA-05 — no lambda.
        self._player.underrun_recovery_started.connect(
            self._on_underrun_recovery_started, Qt.ConnectionType.QueuedConnection
        )

        # Track star → toast (D-10)
        self.now_playing.track_starred.connect(self._on_track_starred)

        # Panel stop button → backend state sync (UI-REVIEW fix)
        self.now_playing.stopped_by_user.connect(self._on_panel_stopped)

        # Station star → toast (D-10)
        self.station_panel.station_favorited.connect(self._on_station_favorited)

        # Plan 39: edit button → dialog launch
        self.now_playing.edit_requested.connect(self._on_edit_requested)
        # Phase 64 / D-02a: 'Also on:' sibling click → switch playback (bound-method per QA-05).
        self.now_playing.sibling_activated.connect(self._on_sibling_activated)
        # Phase 67 / I-02, M-01: Similar Stations link click → switch
        # playback. Distinct signal from sibling_activated for traceability
        # (RESEARCH Pitfall 8 — distinct surfaces test independently).
        self.now_playing.similar_activated.connect(self._on_similar_activated)  # QA-05
        # Phase 60 D-07a: forward vote-error toasts from NowPlayingPanel to show_toast (QA-05).
        self.now_playing.gbs_vote_error_toast.connect(self.show_toast)
        # Phase 68 / T-01: forward live-status transition toasts (T-01a/b/c)
        # from NowPlayingPanel to show_toast (QA-05 — bound method).
        self.now_playing.live_status_toast.connect(self.show_toast)
        # Phase 68 / B-02 fan-out: route poll-cycle live_map updates from
        # NowPlayingPanel into StationListPanel's filter proxy (so the
        # "Live now" chip's predicate stays fresh). Distinct slot rather
        # than a direct connect to station_panel.update_live_map so the
        # signal payload type is validated (must be dict).
        self.now_playing.live_map_changed.connect(self._on_live_map_changed)

        # Phase 72 / D-01 / LAYOUT-01: compact-mode button (NowPlayingPanel,
        # Plan 02) drives station_panel visibility via the central toggle
        # slot. Bound method per QA-05 — no lambda.
        self.now_playing.compact_mode_toggled.connect(self._on_compact_toggle)

        # Phase 70 / DS-01 / Pitfall 9 Option A: Player has no repo handle so
        # persistence + cross-component fan-out live here.
        # Idempotency cache — dedupes back-to-back caps emits for the same stream.
        self._last_quality_payload: dict[int, tuple[int, int]] = {}
        # Explicit QueuedConnection for documentation clarity (belt-and-suspenders
        # — Qt auto-queues cross-thread; Plan 70-00 grep test requires QueuedConnection
        # near audio_caps_detected).
        self._player.audio_caps_detected.connect(
            self._on_audio_caps_detected, Qt.ConnectionType.QueuedConnection
        )

        # Right-click edit from station list
        self.station_panel.edit_requested.connect(self._on_edit_requested)
        # Phase 999.1 D-02: "+" button in panel header shares MainWindow slot
        self.station_panel.new_station_requested.connect(self._on_new_station_clicked)

        # Plan 39: failover → stream picker sync
        self._player.failover.connect(self.now_playing._sync_stream_picker)

        # Phase 47.1 WR-02: drive panel visibility from the QAction's initial
        # checked state. Single source of truth — the panel no longer reads the
        # setting itself, so the menu checkmark and panel visibility cannot drift.
        self.now_playing.set_stats_visible(self._act_stats.isChecked())
        # Phase 67 / M-02: drive Similar Stations container visibility from
        # the QAction's initial checked state. Same single-source-of-truth
        # invariant as Phase 47.1 WR-02 — locked by
        # test_show_similar_toggle_persists_and_toggles_panel (Pitfall 4).
        self.now_playing.set_similar_visible(self._act_show_similar.isChecked())

        # Phase 72 / D-09 single-source-of-truth initial-state push: drive
        # station_panel visibility from the compact button's initial checked
        # state (constant False per D-09 — the button starts unchecked, so
        # the panel starts visible). Deliberately uses a CONSTANT False
        # rather than self._repo.get_setting("compact_mode", ...) — session-
        # only persistence (D-09) means every launch starts expanded. The
        # negative-assertion test `test_compact_mode_starts_expanded_on_launch`
        # locks this invariant.
        self.station_panel.setVisible(
            not self.now_playing.compact_mode_toggle_btn.isChecked()
        )

        # ------------------------------------------------------------------
        # Phase 68 / B-03 / F-07: live-detection startup. start_aa_poll_loop
        # is a silent no-op when no audioaddict_listen_key is saved
        # (Plan 03 guard). set_live_chip_visible drives the chip's initial
        # visibility from the same key check (F-07 — chip hidden until key
        # is added; N-03 — _check_and_start_aa_poll re-evaluates after
        # AccountsDialog/ImportDialog close).
        # ------------------------------------------------------------------
        self.now_playing.start_aa_poll_loop()
        _aa_key_initial = bool(self._repo.get_setting("audioaddict_listen_key", ""))
        self.station_panel.set_live_chip_visible(_aa_key_initial)

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

        # Phase 47.2 D-15: restore last-active EQ profile + preamp + enabled state.
        # Safe no-op if no active profile persisted or plugin missing. Defensive
        # try/except — an EQ startup failure must never prevent the app launching.
        try:
            self._player.restore_eq_from_settings(self._repo)
        except Exception as exc:
            _log.warning("EQ restore failed: %s", exc)

        # ------------------------------------------------------------------
        # Phase 72 / D-02 / D-03 / Pitfall 9: register Ctrl+B QShortcut LAST,
        # AFTER all panels are constructed and signal wiring is done. This
        # is the FIRST QShortcut in the codebase — establishes the pattern
        # for future shortcut-registration phases.
        #
        # context=Qt.WidgetWithChildrenShortcut (RESEARCH §Pattern 2 /
        # RESEARCH A3): window-scope — modal QDialogs (EditStationDialog,
        # AccountsDialog, …) block the shortcut naturally because their
        # focus is outside MainWindow's child tree while exec()-ing.
        #
        # Single source of truth (Pitfall 4): the shortcut activates the
        # button, NOT the slot directly. button.toggle() fans out via
        # compact_mode_toggled → _on_compact_toggle, so mouse-click and
        # Ctrl+B traverse the same code path.
        # ------------------------------------------------------------------
        self._compact_shortcut = QShortcut(
            QKeySequence("Ctrl+B"),
            self,
            context=Qt.WidgetWithChildrenShortcut,
        )
        self._compact_shortcut.activated.connect(self._on_compact_shortcut_activated)

    # ----------------------------------------------------------------------
    # Public helpers
    # ----------------------------------------------------------------------

    def show_toast(self, text: str, duration_ms: int = 3000) -> None:
        """Show a toast notification on the centralWidget bottom-centre."""
        self._toast.show_toast(text, duration_ms)

    def _on_underrun_recovery_started(self) -> None:
        """Phase 62 / D-06 + D-08 + BUG-09: cooldown-gated `Buffering…` toast.

        Player emits underrun_recovery_started after a cycle exceeds the
        1500ms dwell threshold (D-07). This slot:
          - reads time.monotonic() (wall-clock-jump immune);
          - if the previous toast was less than _UNDERRUN_TOAST_COOLDOWN_S
            ago, suppresses (D-08); the cycle is still logged on the
            Player side — only the user-facing toast is debounced;
          - else updates the timestamp and calls show_toast('Buffering…')
            (D-06 — U+2026 ellipsis, matches `Connecting…` style).
        """
        now = time.monotonic()
        if now - self._last_underrun_toast_ts < self._UNDERRUN_TOAST_COOLDOWN_S:
            return
        self.show_toast("Buffering…")    # D-06 — U+2026 ellipsis
        self._last_underrun_toast_ts = now

    # ----------------------------------------------------------------------
    # Phase 68 / B-02 / B-04: live-detection fan-out + reactivity hook
    # ----------------------------------------------------------------------

    def _on_live_map_changed(self, live_map: object) -> None:
        """Phase 68 / B-02: forward poll-cycle live_map to StationListPanel.

        Payload type-check (dict isinstance) is defensive — Signal(object)
        does not enforce the dict contract at the Qt boundary. Non-dict
        payloads are silently ignored.
        """
        if not isinstance(live_map, dict):
            return
        self.station_panel.update_live_map(live_map)

    def _on_audio_caps_detected(
        self, stream_id: int, rate_hz: int, bit_depth: int
    ) -> None:
        """Phase 70 / DS-01 / Pitfall 4 DB-write-first invariant.

        Player emits audio_caps_detected(stream_id, rate_hz, bit_depth) from the
        GStreamer bus-loop thread; Qt auto-queues it to this main-thread slot (plus
        explicit QueuedConnection on the connect side for documentation clarity).

        Strict ordering per Phase 50 D-04 / Pitfall 4:
          1. Idempotency check — bail early if cache already matches.
          2. DB write FIRST: fetch existing stream row to preserve all fields,
             then call repo.update_stream with sample_rate_hz / bit_depth updated.
          3. Update in-memory cache.
          4. Rebuild quality_map from list_stations() (DB-consistent after step 2).
          5. Fan-out to NowPlayingPanel + StationListPanel (hasattr-guarded for
             forward compat with Wave 3 plans 70-06 / 70-09).
          6. Emit quality_map_changed (non-blocking; downstream consumers optional).

        NOTE: DB-write-first / fan-out-second ordering is LOAD-BEARING. Any
        refactor that emits quality_map_changed BEFORE repo.update_stream
        introduces the Phase 50 BUG-01 class of bug (UI re-reads stale data).
        """
        try:
            # Step 1 — idempotency: skip if rate/depth already cached for this stream.
            if self._last_quality_payload.get(stream_id) == (rate_hz, bit_depth):
                return

            # Step 2 — DB write FIRST (Phase 50 D-04 / Pitfall 4).
            # Lightweight lookup: find the station_id for this stream_id via a
            # parameterized SELECT (T-70-13 — parameterized, no string interpolation).
            row = self._repo.con.execute(
                "SELECT station_id FROM station_streams WHERE id=?", (stream_id,)
            ).fetchone()
            if row is None:
                # Stream deleted between caps-emit and slot-fire — T-70-14 race handled.
                return
            station_id = int(row["station_id"])

            # Fetch the full existing stream row so update_stream preserves all fields.
            existing = next(
                (s for s in self._repo.list_streams(station_id) if s.id == stream_id),
                None,
            )
            if existing is None:
                # Deleted between the two lookups — T-70-14 race handled.
                return

            self._repo.update_stream(
                stream_id=existing.id,
                url=existing.url,
                label=existing.label,
                quality=existing.quality,
                position=existing.position,
                stream_type=existing.stream_type,
                codec=existing.codec,
                bitrate_kbps=existing.bitrate_kbps,
                sample_rate_hz=rate_hz,
                bit_depth=bit_depth,
            )

            # Step 3 — update in-memory cache (after successful DB write).
            self._last_quality_payload[stream_id] = (rate_hz, bit_depth)

            # Step 4 — rebuild quality_map from freshly-written DB state.
            quality_map: dict[int, str] = {
                st.id: best_tier_for_station(st)
                for st in self._repo.list_stations()
            }

            # Step 5 — fan-out (hasattr-guarded for Wave 3 plan compat).
            # NowPlayingPanel._refresh_quality_badge lands in Plan 70-06.
            if hasattr(self.now_playing, "_refresh_quality_badge"):
                self.now_playing._refresh_quality_badge()
            # StationListPanel.update_quality_map lands in Plan 70-09.
            if hasattr(self.station_panel, "update_quality_map"):
                self.station_panel.update_quality_map(quality_map)

            # Step 6 — emit quality_map_changed last (non-blocking).
            self.quality_map_changed.emit(quality_map)

        except Exception:
            # Never-raise invariant (Phase 50 + 68 slot pattern).
            _log.exception("_on_audio_caps_detected: unhandled exception (stream_id=%r)", stream_id)

    def _check_and_start_aa_poll(self) -> None:
        """Phase 68 / B-04 / F-07 / N-03: reactive lifecycle hook after
        AccountsDialog/ImportDialog close.

        Lazy-poll-cycle approach (RESEARCH §Pattern 7 option 2) — avoids
        modifying AccountsDialog/ImportDialog with a new signal. Reads
        audioaddict_listen_key fresh from the repo on each call.

        - Key newly present: start the poll loop if not already running;
          show the chip.
        - Key newly absent: stop the poll loop; hide the chip (which also
          uncheck the chip if it's currently checked, per
          StationListPanel.set_live_chip_visible behaviour).

        Idempotent — safe to call multiple times in a row.
        """
        has_key = bool(self._repo.get_setting("audioaddict_listen_key", ""))
        if has_key:
            if not self.now_playing.is_aa_poll_active():
                self.now_playing.start_aa_poll_loop()
        else:
            self.now_playing.stop_aa_poll_loop()
        self.station_panel.set_live_chip_visible(has_key)

    # ----------------------------------------------------------------------
    # Slots (bound methods — no self-capturing lambdas, QA-05)
    # ----------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:
        """Unregister the MPRIS2 service cleanly before the window closes (T-41-13).

        Phase 62 / D-03 + Pitfall 4 / BUG-09: also force-close any in-flight
        underrun cycle as outcome=shutdown so its log line is written before
        app exit. SYNCHRONOUS log write inside Player.shutdown_underrun_tracker;
        queued slots may never run after closeEvent returns.

        Phase 72 / BL-01: remove the global hover-peek event filter and stop
        the dwell timer BEFORE super().closeEvent() destroys widget state.
        Mirrors the Phase 62 BUG-09 closeEvent discipline — no queued slot
        may fire against a partially-destroyed MainWindow. If compact mode
        is still active at close time and the peek overlay is visible, the
        explicit release() reparents station_panel back to the splitter so
        any save-on-close hook (or downstream destructor) sees a consistent
        layout rather than the overlay's adopted child.
        """
        # Phase 72 / BL-01: tear down hover-peek FIRST — a MouseMove queued
        # by Qt between here and super().closeEvent() would otherwise dispatch
        # through a filter installed on a destroyed MainWindow.
        try:
            if (
                self._peek_overlay is not None
                and self._peek_overlay.isVisible()
            ):
                self._peek_overlay.release(
                    self._splitter, self.station_panel, None
                )
        except Exception as exc:
            _log.warning("peek overlay teardown failed: %s", exc)
        try:
            self._remove_peek_hover_filter()
        except Exception as exc:
            _log.warning("peek hover filter teardown failed: %s", exc)
        try:
            self._player.shutdown_underrun_tracker()
        except Exception as exc:
            _log.warning("player shutdown_underrun_tracker failed: %s", exc)
        try:
            self._media_keys.shutdown()
        except Exception as exc:
            _log.warning("media_keys shutdown failed: %s", exc)
        # Phase 68 / B-03 closeEvent: stop the AA events poll timer so
        # no further worker spawns occur after the window closes.
        # Idempotent — Plan 03's stop_aa_poll_loop is safe to call when
        # the timer was never started (no key saved at startup).
        try:
            self.now_playing.stop_aa_poll_loop()
        except Exception as exc:
            _log.warning("stop_aa_poll_loop failed: %s", exc)
        super().closeEvent(event)

    def _on_station_activated(self, station: Station) -> None:
        """Called when the user selects a station in StationListPanel."""
        self.now_playing.bind_station(station)
        self._player.play(station)
        self._repo.update_last_played(station.id)
        self.station_panel.refresh_recent()  # Phase 50 / BUG-01: live recent-list update (D-01, D-04)
        self.now_playing.on_playing_state_changed(True)
        self.show_toast("Connecting\u2026")  # UI-SPEC copywriting: U+2026
        # Seed the OS media session with station name before ICY title arrives (D-05)
        self._media_keys.publish_metadata(station, "", self.now_playing.current_cover_pixmap())
        self._media_keys.set_playback_state("playing")

    def _on_sibling_activated(self, station: Station) -> None:
        """Phase 64 / D-02: user clicked an 'Also on:' link in NowPlayingPanel.

        Delegate to _on_station_activated so the canonical 'user picked a
        station' side-effect block (bind_station, player.play,
        update_last_played, refresh_recent, toast, media-keys publish + state)
        fires identically regardless of activation source (station list vs
        sibling click). Unlike Phase 51's _on_navigate_to_sibling (lines
        482-500) \u2014 which re-opens EditStationDialog and avoids touching
        playback \u2014 this slot DOES change playback (ROADMAP SC #2).
        """
        self._on_station_activated(station)

    def _on_similar_activated(self, station: Station) -> None:
        """Phase 67 / C-01: user clicked a Similar Stations link in NowPlayingPanel.

        Delegate to _on_station_activated for the canonical 'user picked a
        station' side-effect block (bind_station, player.play,
        update_last_played, refresh_recent, 'Connecting\u2026' toast, media-keys
        publish + state). Mirrors Phase 64's _on_sibling_activated; the only
        divergence from _on_station_activated is the originating signal,
        not the side-effect set.
        """
        self._on_station_activated(station)

    def _on_failover(self, next_stream) -> None:
        """Called by Player.failover(StationStream | None)."""
        if next_stream is None:
            self.show_toast("Stream exhausted")
            self.now_playing.on_playing_state_changed(False)
            self._media_keys.publish_metadata(None, "", None)
            self._media_keys.set_playback_state("stopped")
        else:
            self.show_toast("Stream failed, trying next\u2026")

    def _on_offline(self, _channel: str) -> None:
        """Called by Player.offline(channel_name) — Twitch channel offline."""
        self.show_toast("Channel offline")
        self.now_playing.on_playing_state_changed(False)
        self._media_keys.publish_metadata(None, "", None)
        self._media_keys.set_playback_state("stopped")

    def _on_playback_error(self, message: str) -> None:
        """Called by Player.playback_error(str)."""
        # YouTube live stream that has ended (broadcaster stopped the live
        # recording \u2014 usually relaunched as a new video ID). yt-dlp surfaces
        # this as "This live stream recording is not available." Surface a
        # persistent dialog instead of a toast so the user can update or
        # delete the dead station.
        if "live stream recording is not available" in message:
            self._show_youtube_stream_ended_dialog()
            return
        # Phase 44 D-13 part 2: nudge toward Node install when YT resolve fails
        # AND Node is known missing. Early-return keeps non-YT errors on the
        # existing truncation path. The "YouTube resolve failed" prefix is
        # pinned to player.py:557 \u2014 see test_player_emits_expected_yt_failure_prefix.
        if (
            self._node_runtime is not None
            and not self._node_runtime.available
            and "YouTube resolve failed" in message
        ):
            self.show_toast("Install Node.js for YouTube playback")
            return
        truncated = message[:80] + "\u2026" if len(message) > 80 else message
        self.show_toast(f"Playback error: {truncated}")

    def _show_youtube_stream_ended_dialog(self) -> None:
        """Persistent acknowledgment for an ended YouTube live stream.

        Offers Update URL\u2026 / Delete station / Dismiss. Update routes through
        the existing EditStationDialog flow; delete confirms then reuses
        _on_station_deleted for list refresh + now-playing teardown.
        """
        station = self.now_playing.current_station
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("YouTube live stream ended")
        body = (
            "This YouTube live stream is no longer available.\n\n"
            "The broadcaster has ended the recording \u2014 often because they "
            "relaunched a new stream with a different video ID."
        )
        if station is not None:
            body += f"\n\nStation: {station.name}"
        box.setText(body)
        update_btn = box.addButton("Update URL\u2026", QMessageBox.ButtonRole.AcceptRole)
        delete_btn = box.addButton("Delete station", QMessageBox.ButtonRole.DestructiveRole)
        dismiss_btn = box.addButton("Dismiss", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(dismiss_btn)
        # Disable station-scoped actions if no station context is available.
        if station is None:
            update_btn.setEnabled(False)
            delete_btn.setEnabled(False)
        box.exec()
        clicked = box.clickedButton()
        if clicked is update_btn and station is not None:
            self._on_edit_requested(station)
        elif clicked is delete_btn and station is not None:
            confirm = QMessageBox(self)
            confirm.setIcon(QMessageBox.Icon.Warning)
            confirm.setWindowTitle("Delete station?")
            confirm.setText(f"Permanently delete \u201c{station.name}\u201d?")
            confirm.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            confirm.setDefaultButton(QMessageBox.StandardButton.No)
            if confirm.exec() == QMessageBox.StandardButton.Yes:
                self._repo.delete_station(station.id)
                self._on_station_deleted(station.id)

    def _on_node_install_clicked(self) -> None:
        """Phase 44 D-13: hamburger Node-missing indicator click handler.
        Opens nodejs.org in the user's default browser."""
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl("https://nodejs.org/en/download"))

    def _on_track_starred(self, station_name: str, track_title: str, provider: str, is_fav: bool) -> None:
        """Called when the track star button is toggled in NowPlayingPanel."""
        self.show_toast("Saved to favorites" if is_fav else "Removed from favorites")

    def _on_stats_toggled(self, checked: bool) -> None:
        """Persist the Stats for Nerds toggle and update the panel (D-04, D-07). Phase 47.1."""
        self._repo.set_setting("show_stats_for_nerds", "1" if checked else "0")
        self.now_playing.set_stats_visible(checked)

    def _on_show_similar_toggled(self, checked: bool) -> None:
        """Phase 67 / S-01, M-01: persist the Show Similar Stations toggle
        and update the panel container visibility.

        Same dual-write pattern as Phase 47.1 _on_stats_toggled (line 539-542):
        (1) repo.set_setting writes the persisted state.
        (2) panel.set_similar_visible flips the container — single source of
            truth for menu-state vs panel-visibility (Pitfall 4 / WR-02).
        """
        self._repo.set_setting("show_similar_stations", "1" if checked else "0")
        self.now_playing.set_similar_visible(checked)

    # ------------------------------------------------------------------
    # Phase 72 / LAYOUT-01 — compact-mode toggle
    # ------------------------------------------------------------------

    def _on_compact_toggle(self, checked: bool) -> None:
        """Phase 72 / D-01 / D-06 / D-08 / D-09 / D-10 central toggle slot.

        Drives station_panel visibility + splitter-handle visibility from
        the compact button's checked state (single source of truth — both
        mouse click and Ctrl+B traverse this slot via the button).

        Ordering (LOAD-BEARING):
          ON branch:
            (1) Snapshot sizes BEFORE station_panel.hide() (Pitfall 1 — if
                you read sizes() AFTER hide, Qt has already redistributed).
            (2) Hide the station_panel.
            (3) Explicit self._splitter.handle(1).hide() — Wave 0 spike
                72-01 INVALIDATED RESEARCH A1 on PySide6 6.11; the handle
                does NOT auto-hide when an adjacent child is hidden.
            (4) Install peek-overlay hover filter (Plan 04 fills body).
          OFF branch:
            (1) Plan 04 hand-off marker (peek-release guard); Plan 04 will
                replace the marker with the actual overlay-release call.
            (2) Show the station_panel.
            (3) Explicit self._splitter.handle(1).show() — symmetric
                restore for the explicit hide above.
            (4) If a snapshot exists, restore sizes and RESET the snapshot
                to None (Pitfall 5 — leaving stale state means the next
                cycle would restore the wrong sizes if .sizes() returns
                unexpected values mid-hide).
            (5) Remove peek-overlay hover filter (Plan 04 fills body).
          Both branches end with set_compact_button_icon(checked) so the
          icon + tooltip reflect the new state.

        D-09 session-only: NO repo.set_setting / get_setting call. Every
        app launch starts expanded regardless of how the previous session
        ended (the user physically moves the laptop between screens —
        persistence would be surprising).
        """
        if checked:
            self._splitter_sizes_before_compact = self._splitter.sizes()
            self.station_panel.hide()
            self._splitter.handle(1).hide()
            self._install_peek_hover_filter()
        else:
            # Peek-release guard (Plan 04): if the peek overlay is visible
            # when the user exits compact, reparent station_panel back to
            # the splitter at index 0 (Pitfall 6) BEFORE the panel.show() +
            # splitter resize sequence below. Otherwise station_panel would
            # remain a child of the overlay and the splitter would have an
            # orphan index-0 slot, breaking the size restore.
            if (
                self._peek_overlay is not None
                and self._peek_overlay.isVisible()
            ):
                self._peek_overlay.release(
                    self._splitter, self.station_panel, None
                )
            self.station_panel.show()
            self._splitter.handle(1).show()
            if self._splitter_sizes_before_compact:
                self._splitter.setSizes(self._splitter_sizes_before_compact)
                self._splitter_sizes_before_compact = None
            self._remove_peek_hover_filter()
        self.now_playing.set_compact_button_icon(checked)

    def _on_compact_shortcut_activated(self) -> None:
        """Phase 72 / D-02 / D-03 / Pitfall 4: Ctrl+B activates the button.

        Flips compact_mode_toggle_btn (the single source of truth) rather
        than calling _on_compact_toggle directly. The button's `toggled`
        signal then drives the rest of the flow, so mouse-click and
        Ctrl+B produce identical state changes.
        """
        self.now_playing.compact_mode_toggle_btn.toggle()

    # ------------------------------------------------------------------
    # Phase 72 / LAYOUT-01 / D-11..D-15 — Hover-to-peek lifecycle.
    # Filled in by Plan 04. The Plan 03 toggle slot already calls these
    # at the entry/exit points (compact-ON / compact-OFF branches), so
    # the bodies below own the actual hover-filter wiring + overlay
    # construction + reparent-back.
    # ------------------------------------------------------------------

    def _install_peek_hover_filter(self) -> None:
        """Install a global QApplication-level event filter for MouseMove.

        Why global, not centralWidget: Qt delivers MouseMove to the widget
        UNDER THE CURSOR (NowPlayingPanel in compact mode), never to the
        parent QSplitter that is centralWidget(). A filter on centralWidget
        only fires when the cursor sits over centralWidget's own pixels —
        i.e. the splitter handle — which is hidden in compact mode, so the
        filter never fires in practice. (Debug session
        phase-72-hover-peek-wayland — root cause confirmed 2026-05-13.)

        A global filter sees MouseMove regardless of receiver. We then map
        QCursor.pos() to centralWidget-local coordinates and gate on
        compact-mode + in-window in eventFilter.

        setMouseTracking calls retained for any code paths that still rely
        on bare MouseMove arriving at MainWindow/centralWidget directly.
        """
        self.setMouseTracking(True)
        self.centralWidget().setMouseTracking(True)
        QApplication.instance().installEventFilter(self)

    def _remove_peek_hover_filter(self) -> None:
        """Remove the global event filter and reset the dwell timer.

        Mirror of _install_peek_hover_filter: pulls the filter off
        QApplication.instance() (not centralWidget) so re-toggling compact
        mode doesn't double-install.

        Setting `self._peek_dwell_timer = None` (rather than just stop())
        forces the next compact-ON cycle to lazy-reconstruct the timer.
        """
        QApplication.instance().removeEventFilter(self)
        if self._peek_dwell_timer is not None:
            if self._peek_dwell_timer.isActive():
                self._peek_dwell_timer.stop()
            self._peek_dwell_timer = None

    def _open_peek_overlay(self) -> None:
        """Lazy-construct `StationListPeekOverlay` and adopt `station_panel`.

        Parent strategy (deviation from plan body — Rule 1 fix discovered
        during execution; documented in 72-04-SUMMARY): the overlay is
        parented to `MainWindow` (self), NOT `centralWidget()`. The plan
        body prescribed `centralWidget()` to avoid raising peek above
        ToastOverlay, but `centralWidget()` is the QSplitter; parenting a
        QFrame to a QSplitter causes the splitter to auto-manage it as a
        third child (sibling to station_panel + now_playing), repositioning
        the overlay into the right pane's area. Mirroring the established
        ToastOverlay parent strategy (main_window.py:328, `ToastOverlay(self)`)
        + skipping `.raise_()` inside `adopt` preserves the z-order intent
        (toasts always raise above peek) without breaking the layout.

        Width is the captured pre-compact splitter[0] when available,
        otherwise the design-default fallback (360px per UI-SPEC §Spacing).

        D-12 preservation: when `station_panel` is reparented out of the
        splitter, Qt creates a placeholder slot at the old index that
        claims a few pixels of width (~25-30px in offscreen), narrowing
        `now_playing`. Capture the splitter sizes before adopt and restore
        them after, so `now_playing` keeps its full compact-mode width and
        the overlay genuinely "floats over" without forcing a layout shift.
        """
        if self._peek_overlay is None:
            # Rule 1 fix: parent = MainWindow, NOT centralWidget. See docstring.
            self._peek_overlay = StationListPeekOverlay(self)
        if self._splitter_sizes_before_compact:
            width = self._splitter_sizes_before_compact[0]
        else:
            width = _PEEK_FALLBACK_WIDTH_PX
        # Snapshot the now-compact splitter sizes (`[0, total]` after
        # station_panel.hide()) so we can restore them after the reparent.
        sizes_during_compact = self._splitter.sizes()
        # Anchor the overlay to centralWidget's geometry — keeps the peek
        # BELOW the menu bar at the LEFT edge of the content area.
        self._peek_overlay.adopt(
            self.station_panel,
            width,
            anchor_rect=self.centralWidget().geometry(),
        )
        # Restore — counteracts Qt's placeholder-slot reflow on reparent-out.
        self._splitter.setSizes(sizes_during_compact)

    def _close_peek_overlay(self) -> None:
        """Called from the overlay's own mouse-leave eventFilter. Reparents
        `station_panel` back to `_splitter` at index 0 (Pitfall 6 —
        `insertWidget(0, ...)` NOT `addWidget`) and hides the overlay. The
        panel stays hidden because compact mode is still active; only the
        toggle-OFF path in `_on_compact_toggle` makes it visible again.
        """
        if self._peek_overlay is not None and self._peek_overlay.isVisible():
            self._peek_overlay.release(
                self._splitter, self.station_panel, None
            )

    def eventFilter(self, obj, event):
        """Phase 72 / D-13 — hover-peek dwell trigger (global filter).

        Filter is installed on QApplication.instance() so it sees MouseMove
        regardless of receiver. We use QCursor.pos() mapped to centralWidget
        coordinates rather than event.position() (which is in the receiver
        widget's local frame and varies per event).

        Gates (cheap-first ordering, short-circuit on early failures):
          1. event type is MouseMove
          2. compact mode is active (station_panel is hidden)
          3. cursor maps to a point inside centralWidget's rect
          4. cursor x is in [0, _PEEK_TRIGGER_ZONE_PX]
          5. no peek overlay currently visible

        Returns super().eventFilter(...) (False under normal flow) — the
        filter never consumes events (T-72-05 mitigation).
        """
        if event.type() != QEvent.MouseMove:
            return super().eventFilter(obj, event)
        if not self.station_panel.isHidden():
            return super().eventFilter(obj, event)

        cw = self.centralWidget()
        pos = cw.mapFromGlobal(QCursor.pos())
        in_cw = 0 <= pos.x() < cw.width() and 0 <= pos.y() < cw.height()
        if not in_cw:
            if (
                self._peek_dwell_timer is not None
                and self._peek_dwell_timer.isActive()
            ):
                self._peek_dwell_timer.stop()
            return super().eventFilter(obj, event)

        in_zone = pos.x() <= _PEEK_TRIGGER_ZONE_PX
        no_visible_peek = (
            self._peek_overlay is None
            or not self._peek_overlay.isVisible()
        )
        if in_zone and no_visible_peek:
            if self._peek_dwell_timer is None:
                self._peek_dwell_timer = QTimer(self)
                self._peek_dwell_timer.setSingleShot(True)
                # QA-05 bound method — NO lambda.
                self._peek_dwell_timer.timeout.connect(
                    self._open_peek_overlay
                )
            if not self._peek_dwell_timer.isActive():
                self._peek_dwell_timer.start(_PEEK_DWELL_MS)
        else:
            if (
                self._peek_dwell_timer is not None
                and self._peek_dwell_timer.isActive()
            ):
                self._peek_dwell_timer.stop()
        return super().eventFilter(obj, event)

    def _on_station_favorited(self, station: Station, is_fav: bool) -> None:
        """Called when a station star is toggled in StationListPanel."""
        self.show_toast("Station added to favorites" if is_fav else "Station removed from favorites")

    def _on_new_station_clicked(self) -> None:
        """Create a placeholder station and open EditStationDialog in new-station mode.

        D-03: placeholder row is INSERTed by repo.create_station() so the dialog's
        existing update_station / insert_stream / assets paths work unchanged.
        D-04 cleanup-on-cancel is handled inside EditStationDialog — no cleanup here.
        D-07: on save, refresh list and select the new station (no auto-play).
        """
        new_id = self._repo.create_station()
        fresh = self._repo.get_station(new_id)
        dlg = EditStationDialog(
            fresh, self._player, self._repo,
            parent=self, is_new=True,
        )
        dlg.station_saved.connect(self._refresh_station_list)
        # D-07: select the new station after save. Lambda matches the precedent
        # set by _on_edit_requested (self-capturing id is accepted pattern here).
        dlg.station_saved.connect(
            lambda: self.station_panel.select_station(new_id)
        )
        # D-07: intentionally NOT wired to the now-playing-sync slot — a brand-new
        # station is never the currently-playing one. No auto-play.
        dlg.station_deleted.connect(self._on_station_deleted)
        # Phase 51 / D-09: a brand-new station can be an AA URL — same wiring as edit path.
        dlg.navigate_to_sibling.connect(self._on_navigate_to_sibling)
        dlg.sibling_toast.connect(self.show_toast)   # Phase 71 / D-14 / D-11
        dlg.exec()

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
        # Phase 51 / D-09: re-open editor for sibling when user clicks "Also on:" link.
        dlg.navigate_to_sibling.connect(self._on_navigate_to_sibling)
        dlg.sibling_toast.connect(self.show_toast)   # Phase 71 / D-14 / D-11
        dlg.exec()

    def _on_station_deleted(self, station_id: int) -> None:
        """After station deletion, refresh list and clear now-playing if needed."""
        self._refresh_station_list()
        if self.now_playing.current_station and self.now_playing.current_station.id == station_id:
            self._media_keys.publish_metadata(None, "", None)
            self.now_playing._on_stop_clicked()
            self._media_keys.set_playback_state("stopped")

    def _on_navigate_to_sibling(self, sibling_id: int) -> None:
        """Phase 51 / D-09, D-10: re-open EditStationDialog for the sibling station.

        Called when the user clicks an 'Also on:' link in the current edit
        dialog. The originating dialog has already accepted/rejected itself
        via _on_sibling_link_activated's clean / Save / Discard paths — by
        the time this slot fires, that dialog is closing.

        D-10 invariant: this slot does NOT touch playback. No player.failover,
        no player.play, no multi-stream queue manipulation. The currently
        playing station continues regardless of which dialog is open.

        Implementation: delegate to _on_edit_requested so signal wiring lives
        in one place (single source of truth for dialog setup).

        Dual-shape repo.get_station handling (Phase 64 REVIEW WR-02):
          - Production Repo.get_station raises ValueError on miss (repo.py:271).
          - Some test doubles return None.
        Wrap in try/except Exception + None-check to be safe in both shapes.
        Qt slots-never-raise: bail silently on any failure path.
        """
        try:
            sibling = self._repo.get_station(sibling_id)
        except Exception:
            return  # sibling deleted between render and click — silent no-op
        if sibling is None:
            return  # sibling deleted between render and click — silent no-op
        self._on_edit_requested(sibling)

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
        # Capture state before toggling so we report the outcome, not an
        # intermediate value (immune to async signal chains — WR-03).
        was_playing = self.now_playing.is_playing
        self.now_playing._on_play_pause_clicked()
        new_state = "paused" if was_playing else "playing"
        self._media_keys.set_playback_state(new_state)

    def _on_panel_stopped(self) -> None:
        """In-panel Stop button clicked — notify backend so OS overlay stays in sync."""
        self._media_keys.publish_metadata(None, "", None)
        self._media_keys.set_playback_state("stopped")

    def _on_media_key_stop(self) -> None:
        """OS stop request -> stop via NowPlayingPanel."""
        self.now_playing._on_stop_clicked()
        self._media_keys.publish_metadata(None, "", None)
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

    # ----------------------------------------------------------------------
    # UI-REVIEW fix #1 helpers: busy cursor + menu-action disable during
    # background export / import-preview so the user gets feedback and
    # cannot double-start a worker.
    # ----------------------------------------------------------------------

    def _begin_busy(self) -> None:
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        self._act_export.setEnabled(False)
        self._act_import_settings.setEnabled(False)

    def _end_busy(self) -> None:
        QApplication.restoreOverrideCursor()
        self._act_export.setEnabled(True)
        self._act_import_settings.setEnabled(True)

    def _on_export_settings(self) -> None:
        """Open file save picker and export settings ZIP on background thread (SYNC-05)."""
        docs = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation
        )
        default = os.path.join(
            docs, f"musicstreamer-export-{datetime.date.today().isoformat()}.zip"
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Settings", default, "ZIP Archive (*.zip)"
        )
        if not path:
            return
        self._begin_busy()
        self._export_worker = _ExportWorker(path, parent=self)
        self._export_worker.finished.connect(self._on_export_done, Qt.QueuedConnection)
        self._export_worker.error.connect(self._on_export_error, Qt.QueuedConnection)
        self._export_worker.start()

    def _on_export_done(self, dest_path: str) -> None:
        self._end_busy()
        filename = os.path.basename(dest_path)
        self.show_toast(f"Settings exported to {filename}")

    def _on_export_error(self, msg: str) -> None:
        self._end_busy()
        self.show_toast(f"Export failed \u2014 {msg}")

    def _on_import_settings(self) -> None:
        """Open file picker and preview import ZIP on background thread (SYNC-05)."""
        docs = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation
        )
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Settings", docs, "ZIP Archive (*.zip)"
        )
        if not path:
            return
        self._begin_busy()
        self._import_preview_worker = _ImportPreviewWorker(path, parent=self)
        self._import_preview_worker.finished.connect(
            self._on_import_preview_ready, Qt.QueuedConnection
        )
        self._import_preview_worker.error.connect(
            self._on_import_preview_error, Qt.QueuedConnection
        )
        self._import_preview_worker.start()

    def _on_import_preview_ready(self, preview) -> None:
        self._end_busy()
        from musicstreamer.ui_qt.settings_import_dialog import SettingsImportDialog
        dlg = SettingsImportDialog(preview, self.show_toast, parent=self)
        dlg.import_complete.connect(self._refresh_station_list)
        dlg.exec()

    def _on_import_preview_error(self, msg: str) -> None:
        self._end_busy()
        # IN-01: include the specific ValueError detail (truncated) so the user
        # can distinguish between "Unsupported version: 99", "Missing
        # settings.json", "Unsafe path in archive: ...", etc.
        truncated = msg[:80] + "\u2026" if len(msg) > 80 else msg
        self.show_toast(f"Invalid settings file: {truncated}")

    def _open_discovery_dialog(self) -> None:
        """D-14: Open DiscoveryDialog from hamburger menu."""
        dlg = DiscoveryDialog(self._player, self._repo, self.show_toast, parent=self)
        dlg.exec()
        self._refresh_station_list()

    def _open_import_dialog(self) -> None:
        """D-15: Open ImportDialog from hamburger menu."""
        dlg = ImportDialog(self.show_toast, self._repo, parent=self)
        dlg.import_complete.connect(self._refresh_station_list)
        dlg.exec()
        # Phase 68 / B-04: re-evaluate AA listen-key state after the
        # dialog closes (the import flow may have written a new key).
        self._check_and_start_aa_poll()

    def _open_theme_dialog(self) -> None:
        """Phase 66 D-15 / THEME-01: Open ThemePickerDialog from hamburger menu.

        Lazy import matches _open_equalizer_dialog precedent (line 793).
        The dialog handles its own snapshot/restore on Cancel; Apply persists
        `theme` setting. The existing accent_color restore at line 241-245
        continues to layer on top (Phase 59 D-02 contract preserved).
        """
        from musicstreamer.ui_qt.theme_picker_dialog import ThemePickerDialog
        dlg = ThemePickerDialog(self._repo, parent=self)
        dlg.exec()

    def _open_accent_dialog(self) -> None:
        """D-16: Open AccentColorDialog from hamburger menu."""
        dlg = AccentColorDialog(self._repo, parent=self)
        dlg.exec()

    def _open_accounts_dialog(self) -> None:
        """D-18: Open AccountsDialog from hamburger menu.

        Phase 48 D-04: pass ``self._repo`` so the AA group can read/clear
        the ``audioaddict_listen_key`` setting.
        Phase 53 D-14: pass ``self.show_toast`` so the YouTube cookie import
        flow can surface its success toast through the same overlay.
        """
        dlg = AccountsDialog(self._repo, toast_callback=self.show_toast, parent=self)
        dlg.exec()
        # Phase 68 / B-04: re-evaluate AA listen-key state after the
        # dialog closes. Lazy approach — AccountsDialog is unmodified.
        self._check_and_start_aa_poll()

    def _open_equalizer_dialog(self) -> None:
        """Phase 47.2 D-07: Open EqualizerDialog from hamburger menu."""
        from musicstreamer.ui_qt.equalizer_dialog import EqualizerDialog
        dlg = EqualizerDialog(self._player, self._repo, self.show_toast, parent=self)
        dlg.exec()

    # ------------------------------------------------------------------
    # Phase 60 D-02 / GBS-01a: GBS.FM import handlers
    # ------------------------------------------------------------------

    def _on_gbs_add_clicked(self) -> None:
        """Phase 60 D-02 / D-02a: kick the GBS.FM import on a worker thread.

        Idempotent: re-clicking refreshes streams in place. UI never blocks —
        worker runs the urllib calls + logo download off-thread. Pitfall 3:
        auth-expired surfaces as a re-auth toast.
        """
        self.show_toast("Importing GBS.FM…")
        self._gbs_import_worker = _GbsImportWorker(parent=self)  # SYNC-05 retain
        self._gbs_import_worker.finished.connect(self._on_gbs_import_finished)  # QA-05
        self._gbs_import_worker.error.connect(self._on_gbs_import_error)        # QA-05
        self._gbs_import_worker.start()

    def _on_gbs_import_finished(self, inserted: int, updated: int) -> None:
        """D-02a: distinct toast for fresh insert vs in-place refresh."""
        if inserted:
            self.show_toast("GBS.FM added")
        elif updated:
            self.show_toast("GBS.FM streams updated")
        else:
            self.show_toast("GBS.FM import: no changes")
        self._refresh_station_list()
        self._gbs_import_worker = None

    def _on_gbs_import_error(self, msg: str) -> None:
        """Pitfall 3: auth_expired sentinel → reconnect prompt; else generic."""
        if msg == "auth_expired":
            self.show_toast("GBS.FM session expired — reconnect via Accounts")
        else:
            truncated = (msg[:80] + "…") if len(msg) > 80 else msg
            self.show_toast(f"GBS.FM import failed: {truncated}")
        self._gbs_import_worker = None

    def _open_gbs_search_dialog(self) -> None:
        """Phase 60 D-08 / GBS-01e: open the search-and-submit dialog.

        Mirrors _open_discovery_dialog at line 704 (drops the player arg per
        CONTEXT.md "Phase 60's search dialog does NOT need preview play").
        submission_completed is not connected here — submitting a song does not
        touch the local library, so no station-list refresh is needed.
        """
        from musicstreamer.ui_qt.gbs_search_dialog import GBSSearchDialog
        dlg = GBSSearchDialog(self._repo, self.show_toast, parent=self)
        dlg.exec()
