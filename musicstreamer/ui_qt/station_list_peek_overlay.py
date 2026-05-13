"""Phase 72 / LAYOUT-01: Hover-to-peek overlay for compact mode.

Hosts a reparented `StationListPanel` instance over the now-playing pane
while compact mode is active. The overlay floats above the splitter children
but BELOW `ToastOverlay` (Pitfall 8 — toasts parent to MainWindow; the peek
overlay parents to centralWidget so the natural Qt z-order puts toasts on
top).

Decisions locked in this module:
  * D-11: Hover-to-peek is the chosen secondary reveal mechanism.
  * D-12: Overlay floats OVER now-playing (no splitter reflow during peek).
  * D-14: Dismiss is mouse-leaves-overlay ONLY — Esc / click-outside /
          click-station do NOT dismiss.
  * D-15: Overlay is fully interactive — the SAME StationListPanel instance
          is reparented (RESEARCH A2 confirmed safe by Wave 0 spike), so
          click-to-play, right-click-edit, star toggle, search, scroll, and
          filter chips all work without state syncing.

Two deliberate divergences from the `ToastOverlay` analog
(musicstreamer/ui_qt/toast.py — overlay-on-parent + event-filter precedent):
  1. Parent is `centralWidget()`, not `MainWindow` (Pitfall 8 — keeps toasts
     above peek in z-order).
  2. Mouse events are NOT transparent. ToastOverlay sets
     `WA_TransparentForMouseEvents` because it is read-only chrome; the peek
     overlay MUST accept clicks for the reparented panel to remain
     interactive (D-15).
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QFrame, QSplitter, QVBoxLayout, QWidget

# Side-effect import: defensively registers the :/icons/ resource prefix.
# The overlay itself does not load icons, but child widgets reparented into
# it (StationListPanel) do, and mirroring this pattern keeps Phase 36 D-24
# / RESEARCH Pitfall 2 conventions consistent across sibling modules.
from musicstreamer.ui_qt import icons_rc  # noqa: F401

# Forward import — StationListPanel is reparented but not constructed here.
from musicstreamer.ui_qt.station_list_panel import StationListPanel


class StationListPeekOverlay(QFrame):
    """Floating overlay that adopts the existing `StationListPanel` during peek.

    Lifetime: parent-owned (NO WA_DeleteOnClose). Constructed lazily by
    MainWindow on first peek; reused across peek cycles.

    Public API:
      * adopt(station_panel, width)
            Reparent `station_panel` INTO this overlay's layout, anchor at
            geometry (0, 0, width, parent.height()), and show.
      * release(splitter, station_panel, restore_sizes)
            Reparent `station_panel` BACK into the splitter at index 0
            (Pitfall 6 — `insertWidget(0, ...)` NOT `addWidget` to preserve
            visual order), keep the panel hidden (compact mode still active),
            and hide self.
    """

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        # 1px right-edge separator + base background — palette-driven for
        # automatic theme compatibility (Phase 66 THEME-01 / UI-SPEC §Color).
        self.setStyleSheet(
            "StationListPeekOverlay {"
            " background-color: palette(base);"
            " border-right: 1px solid palette(mid);"
            "}"
        )
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        # Pitfall 2: mouse tracking enabled so the overlay's eventFilter sees
        # MouseMove events without a button held — used by the Leave-detection
        # path (Qt fires QEvent.Leave automatically when the cursor crosses
        # out of self.rect()).
        self.setMouseTracking(True)
        self.installEventFilter(self)
        # Hidden until the first adopt() call.
        self.hide()

    def adopt(
        self,
        station_panel: StationListPanel,
        width: int,
        anchor_rect=None,
    ) -> None:
        """Reparent `station_panel` into the overlay layout and show.

        Caller (MainWindow._open_peek_overlay) is responsible for having
        captured the splitter snapshot so release() can reverse the move.

        Width is supplied by the caller — snapshot-present uses the captured
        pre-compact splitter[0]; snapshot-absent falls back to the splitter
        default (360px per main_window.py:285).

        `anchor_rect`: a QRect describing the content area the overlay should
        cover (typically `MainWindow.centralWidget().geometry()` so the peek
        sits BELOW the menu bar at the LEFT edge). Falls back to the
        overlay's parent geometry if None.
        """
        self._layout.addWidget(station_panel)  # implicit setParent(self)
        station_panel.show()  # was hidden in compact mode
        if anchor_rect is not None:
            x = anchor_rect.x()
            y = anchor_rect.y()
            h = anchor_rect.height()
        else:
            parent = self.parent()
            x = 0
            y = 0
            h = parent.height() if isinstance(parent, QWidget) else 0
        self.setGeometry(x, y, width, h)
        self.show()
        # Do NOT call self.raise_() here. The peek overlay must NOT come
        # above ToastOverlay (Pitfall 8 / UI-SPEC §Z-order). ToastOverlay
        # calls its own .raise_() in show_toast() — keeping peek
        # un-raised means a new toast naturally lands above the peek.

    def release(
        self,
        splitter: QSplitter,
        station_panel: StationListPanel,
        restore_sizes: list[int] | None,
    ) -> None:
        """Reparent `station_panel` back into `splitter` at index 0.

        Pitfall 6: use `insertWidget(0, ...)` — `addWidget` would append at
        index 1 and silently swap visual order with the now-playing pane.
        Wave 0 spike 72-01 test_station_panel_reparent_round_trip_preserves_state
        locks this contract.

        The `restore_sizes` argument is currently unused inside this method
        because the splitter's size-restore is handled by MainWindow's
        compact-OFF branch (which owns the snapshot lifecycle). It is part
        of the public signature for forward compatibility — a future refactor
        may move size-restore into the overlay if peek-only resize gestures
        are ever added.
        """
        self._layout.removeWidget(station_panel)
        splitter.insertWidget(0, station_panel)
        station_panel.hide()  # compact mode still active
        self.hide()

    def eventFilter(self, obj, event):
        """Detect QEvent.Leave on self and route close-request up to MainWindow.

        D-14: dismiss is mouse-leaves-overlay ONLY. Esc does NOT dismiss
        (no key handling here); click-station does NOT auto-dismiss (the
        overlay never consumes mouse clicks — children handle them).

        The overlay stays "dumb": it knows the cursor left, signals up to
        MainWindow via self.window()._close_peek_overlay(), and lets
        MainWindow drive the actual reparent-back via release(). This keeps
        the lifecycle ownership clear — MainWindow owns the overlay and the
        splitter/station_panel; the overlay just hosts a child.
        """
        if obj is self and event.type() == QEvent.Leave:
            mw = self.window()
            if hasattr(mw, "_close_peek_overlay"):
                mw._close_peek_overlay()
        return super().eventFilter(obj, event)
