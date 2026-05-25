# Phase 72: Fullscreen Mode — Hide Left Column for Compact Displays — Pattern Map

**Mapped:** 2026-05-13
**Files analyzed:** 8 (5 modified, 3 new — plus a regenerated artifact + at least one new test file)
**Analogs found:** 7 / 8 (one file — the Ctrl+B `QShortcut` — is first-of-its-kind and has no in-codebase analog; documented with Qt-doc references in lieu)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `musicstreamer/ui_qt/main_window.py` (MODIFY) | controller/composition root | request-response (signal/slot) + event-driven (event filter) | self (lines 269-287 splitter, 293 ToastOverlay, 743-758 toggle slots, 381-386 single-source-of-truth push) | **exact (self-precedent)** |
| `musicstreamer/ui_qt/now_playing_panel.py` (MODIFY) | widget composition + outbound signals | event-driven (button toggled → signal) | self (lines 479-488 `star_btn`, 492-507 `eq_toggle_btn`, 224-269 outbound `Signal(...)` declarations) | **exact (self-precedent)** |
| `musicstreamer/ui_qt/station_list_peek_overlay.py` (NEW) | container widget (overlay) | event-driven (mouse-leave detection) + parent-stacking (reparented child) | `musicstreamer/ui_qt/toast.py` `ToastOverlay` (overlay parented to centralWidget, event-filter on parent for repositioning) | **role-match, partial** (peek is **interactive** — `ToastOverlay` sets `WA_TransparentForMouseEvents` which the peek MUST NOT) |
| `musicstreamer/ui_qt/icons/sidebar-show-symbolic.svg` (NEW) | static asset (icon glyph) | n/a | `musicstreamer/ui_qt/icons/non-starred-symbolic.svg`, `document-edit-symbolic.svg`, `multimedia-equalizer-symbolic.svg` | **exact (family match)** |
| `musicstreamer/ui_qt/icons/sidebar-hide-symbolic.svg` (NEW) | static asset (icon glyph) | n/a | same as above | **exact (family match)** |
| `musicstreamer/ui_qt/icons.qrc` (MODIFY) | resource manifest | build-time | self (lines 4-15 of `icons.qrc` — alias→path entries) | **exact (self-precedent)** |
| `musicstreamer/ui_qt/icons_rc.py` (REGENERATED) | resource bundle (auto-generated) | build-time | self — produced via `pyside6-rcc icons.qrc -o icons_rc.py` | **exact (build artifact)** |
| `tests/test_phase72_*.py` (NEW — split between `test_main_window_integration.py` additions and a possible new file) | pytest-qt integration / unit tests | request-response (qtbot triggers → assertion) | `tests/test_main_window_integration.py:1186-1215` (`test_show_similar_toggle_persists_and_toggles_panel`), `tests/test_main_window_integration.py:631-652` (`test_buffer_percent_bound_method_connect_no_lambda` — QA-05 lambda-ban structural test), `tests/test_now_playing_panel.py:298-306` (`test_play_pause_icon_toggle` — icon-flip unit test) | **exact (test patterns) — plus one NEGATIVE-assertion variant for D-09** |

**Ctrl+B QShortcut** — verified zero existing usage in `musicstreamer/` (`grep -rn "QShortcut\|setShortcut\|QKeySequence"` returned empty). No in-codebase analog. Pattern sourced from Qt 6 docs (cited in RESEARCH.md Pattern 2). This phase establishes the codebase precedent.

---

## Pattern Assignments

### 1. `musicstreamer/ui_qt/main_window.py` (controller, request-response + event-driven)

**Self-precedent (this file IS the analog for itself).**

**Imports pattern** (`main_window.py:32-45`):
```python
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QCloseEvent, QCursor, QIcon
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
```
**For Phase 72:** Extend imports with `from PySide6.QtCore import QEvent, QTimer` (QEvent already imported in `now_playing_panel.py:32`; QTimer used by `_GbsPollWorker`), `from PySide6.QtGui import QKeySequence, QShortcut` (new — first-in-codebase), and `from musicstreamer.ui_qt.station_list_peek_overlay import StationListPeekOverlay` (new file).

---

**QSplitter construction pattern** (`main_window.py:269-287` — the surface compact mode operates on):
```python
# Central widget: QSplitter (D-06, UI-SPEC Layout Contracts)
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
```
**For Phase 72:** Do NOT touch this block. `setChildrenCollapsible(False)` stays (D-08). Compact mode uses `station_panel.hide()` (not splitter drag) so the collapsibility contract is preserved.

---

**Overlay parented to MainWindow, anchored to centralWidget** (`main_window.py:289-293`):
```python
# Toast overlay — parented to centralWidget, anchored bottom-centre.
# D-09/D-10: constructed AFTER centralWidget is set.
self._toast = ToastOverlay(self)
```
**For Phase 72 (peek overlay) — DIVERGES on parent:** Per RESEARCH Pitfall 8 + UI-SPEC Z-order contract, the peek overlay must parent to `self.centralWidget()` (NOT `self` like ToastOverlay) so toasts render **above** peek:
```python
# Phase 72 peek overlay — parent to centralWidget so toasts (parented to
# MainWindow itself) win z-order. See UI-SPEC §Z-order and Pitfall 8.
self._peek_overlay: StationListPeekOverlay | None = None  # lazy-constructed on first peek
```

---

**Single-source-of-truth toggle slot + initial-state push** (`main_window.py:381-386, 743-746`):
```python
# At end of __init__, AFTER all panels exist:
# Phase 47.1 WR-02: drive panel visibility from the QAction's initial
# checked state. Single source of truth — the panel no longer reads the
# setting itself, so the menu checkmark and panel visibility cannot drift.
self.now_playing.set_stats_visible(self._act_stats.isChecked())
self.now_playing.set_similar_visible(self._act_show_similar.isChecked())

# ...later, toggle slot...
def _on_stats_toggled(self, checked: bool) -> None:
    """Persist the Stats for Nerds toggle and update the panel (D-04, D-07). Phase 47.1."""
    self._repo.set_setting("show_stats_for_nerds", "1" if checked else "0")
    self.now_playing.set_stats_visible(checked)
```
**For Phase 72 — DIVERGES on persistence (D-09):**
```python
def _on_compact_toggle(self, checked: bool) -> None:
    """Phase 72 D-09 / LAYOUT-01: session-only — NO repo.set_setting call.
    Mirrors the Phase 47.1 / Phase 67 single-source-of-truth invariant but
    intentionally omits the persistence half. See PATTERNS §Anti-Precedent."""
    if checked:
        # CRITICAL (Pitfall 1): snapshot BEFORE hide — sizes() returns 0 once hidden.
        self._splitter_sizes_before_compact = self._splitter.sizes()
        self.station_panel.hide()
        self._install_peek_hover_filter()
    else:
        if self._peek_overlay is not None and self._peek_overlay.isVisible():
            self._peek_overlay.release(self._splitter, self.station_panel, None)
        self.station_panel.show()
        if self._splitter_sizes_before_compact:
            self._splitter.setSizes(self._splitter_sizes_before_compact)
            self._splitter_sizes_before_compact = None   # Pitfall 5: reset
        self._remove_peek_hover_filter()
    self.now_playing.set_compact_button_icon(checked)
```

Initial-state push (mirrors `main_window.py:381` shape but with constant `False` — D-09):
```python
# Phase 72 D-09: every launch starts expanded. NO repo.get_setting call.
self.station_panel.setVisible(not self.now_playing.compact_mode_toggle_btn.isChecked())
```

---

**Bound-method signal connect pattern** (`main_window.py:331-340` — mirror for new compact_mode_toggled signal):
```python
# Track star → toast (D-10)
self.now_playing.track_starred.connect(self._on_track_starred)
# Panel stop button → backend state sync (UI-REVIEW fix)
self.now_playing.stopped_by_user.connect(self._on_panel_stopped)
# Plan 39: edit button → dialog launch
self.now_playing.edit_requested.connect(self._on_edit_requested)
```
**For Phase 72:** Add one line, same shape:
```python
# Phase 72 / LAYOUT-01: compact-mode toggle from NowPlayingPanel button.
self.now_playing.compact_mode_toggled.connect(self._on_compact_toggle)  # QA-05
```

---

**QShortcut registration** (NO in-codebase analog — first of its kind):

Source: `doc.qt.io/qt-6/qshortcut.html` and `doc.qt.io/qtforpython-6/PySide6/QtGui/QShortcut.html` (cited in RESEARCH Pattern 2). Place AFTER all panels are constructed and signal wiring is done — same position as `set_stats_visible` at `main_window.py:381` (RESEARCH Pitfall 9):
```python
# Phase 72 D-02/D-03 / LAYOUT-01: first QShortcut in codebase.
# Window-scope context (Qt.WidgetWithChildrenShortcut) — modal QDialogs
# (EditStationDialog, AccountsDialog, etc.) naturally block it.
self._compact_shortcut = QShortcut(
    QKeySequence("Ctrl+B"),
    self,
    context=Qt.WidgetWithChildrenShortcut,
)
self._compact_shortcut.activated.connect(self._on_compact_shortcut_activated)  # QA-05

def _on_compact_shortcut_activated(self) -> None:
    """Single source of truth (Pitfall 4): toggle the button, never bypass it.
    Calling btn.toggle() fans out through compact_mode_toggled -> _on_compact_toggle."""
    self.now_playing.compact_mode_toggle_btn.toggle()
```

---

**Event filter for mouse-tracking dwell** (NO direct in-codebase analog for `MouseMove`, but `ToastOverlay.eventFilter` at `toast.py:98-101` shows the `installEventFilter`/`eventFilter` shape):
```python
# Source: toast.py:78,98-101 (parent.installEventFilter + eventFilter override)
parent.installEventFilter(self)

def eventFilter(self, obj, event):
    if obj is self.parent() and event.type() == QEvent.Resize:
        self._reposition()
    return super().eventFilter(obj, event)
```
**For Phase 72:** Adapt to `QEvent.MouseMove` on centralWidget with `setMouseTracking(True)` (Pitfall 2):
```python
def _install_peek_hover_filter(self) -> None:
    """Pitfall 2: mouse tracking MUST be enabled on both MainWindow and
    centralWidget for MouseMove events to fire without a button held."""
    self.setMouseTracking(True)
    self.centralWidget().setMouseTracking(True)
    self.centralWidget().installEventFilter(self)

def _remove_peek_hover_filter(self) -> None:
    self.centralWidget().removeEventFilter(self)
    if self._peek_dwell_timer is not None:
        self._peek_dwell_timer.stop()
        self._peek_dwell_timer = None

def eventFilter(self, obj, event):
    if event.type() == QEvent.MouseMove and obj is self.centralWidget():
        pos = event.position().toPoint()  # Qt 6: position() returns QPointF
        if pos.x() <= _PEEK_TRIGGER_ZONE_PX and (
            self._peek_overlay is None or not self._peek_overlay.isVisible()
        ):
            if self._peek_dwell_timer is None:
                self._peek_dwell_timer = QTimer(self)
                self._peek_dwell_timer.setSingleShot(True)
                self._peek_dwell_timer.timeout.connect(self._open_peek_overlay)  # QA-05
            if not self._peek_dwell_timer.isActive():
                self._peek_dwell_timer.start(_PEEK_DWELL_MS)
        else:
            if self._peek_dwell_timer is not None and self._peek_dwell_timer.isActive():
                self._peek_dwell_timer.stop()
    return False  # do NOT consume — propagate to other handlers
```

---

### 2. `musicstreamer/ui_qt/now_playing_panel.py` (widget composition + outbound signals)

**Self-precedent.**

**Imports pattern** (`now_playing_panel.py:32-48`): Already includes everything needed (`QSize`, `Qt`, `Signal`, `QIcon`, `QToolButton`). No new imports required.

---

**Outbound Signal declaration pattern** (`now_playing_panel.py:224-269` — class-level `Signal(...)` declarations):
```python
# Emitted on track star toggle: (station_name, track_title, provider_name, is_now_favorited)
track_starred = Signal(str, str, str, bool)

# Emitted when user clicks edit button — passes current Station to MainWindow.
edit_requested = Signal(object)

# Emitted when the user stops playback via the in-panel Stop button (not via OS media key).
stopped_by_user = Signal()

# Phase 64 / D-02: emitted when user clicks an 'Also on:' sibling link.
sibling_activated = Signal(object)
```
**For Phase 72:** Add a single new outbound Signal in the same class-level block, mirroring the `stopped_by_user = Signal()` shape (boolean payload):
```python
# Phase 72 / LAYOUT-01: emitted when compact-mode toggle button is clicked.
# Payload is the new checked state. MainWindow connects to _on_compact_toggle
# (QA-05 bound method, no lambda). Session-only — no repo write side-effect.
compact_mode_toggled = Signal(bool)
```

---

**Checkable QToolButton with icon + tooltip** (`now_playing_panel.py:479-488` — `star_btn`; closest analog by size/family):
```python
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
```

Same pattern at `now_playing_panel.py:492-507` (`eq_toggle_btn`) — 28x28 checkable + 20x20 icon + tooltip + `clicked.connect`.

**For Phase 72** — insert immediately AFTER `controls.addWidget(self.volume_slider)` at **`now_playing_panel.py:513`** and BEFORE `controls.addStretch(1)` at **`now_playing_panel.py:515`** (per UI-SPEC §Interaction Contract, corrected from CONTEXT D-04 — actual control row order is `play_pause → stop → edit → stream_combo → star → eq_toggle → volume_slider → [NEW: compact_mode_toggle_btn] → addStretch(1)`):
```python
# Phase 72 / LAYOUT-01 / D-04 (corrected per UI-SPEC): compact-mode toggle.
# Inserted between volume_slider (line 513) and addStretch(1) (line 515).
# 28x28 / 20x20 sizes match star_btn (line 479-488) and eq_toggle_btn (492-507).
self.compact_mode_toggle_btn = QToolButton(self)
self.compact_mode_toggle_btn.setIconSize(QSize(20, 20))
self.compact_mode_toggle_btn.setFixedSize(28, 28)
self.compact_mode_toggle_btn.setCheckable(True)
self.compact_mode_toggle_btn.setIcon(
    QIcon.fromTheme(
        "sidebar-hide-symbolic",
        QIcon(":/icons/sidebar-hide-symbolic.svg"),
    )
)
self.compact_mode_toggle_btn.setToolTip("Hide stations (Ctrl+B)")
self.compact_mode_toggle_btn.toggled.connect(self._on_compact_btn_toggled)  # QA-05
controls.addWidget(self.compact_mode_toggle_btn)
```

**Bound-method slot for `toggled` (re-emits as panel signal)** — mirrors `_on_star_clicked` style at `now_playing_panel.py:487`:
```python
def _on_compact_btn_toggled(self, checked: bool) -> None:
    """Re-emit as panel signal. MainWindow connects compact_mode_toggled
    to _on_compact_toggle (D-09: no settings write here)."""
    self.compact_mode_toggled.emit(checked)

def set_compact_button_icon(self, checked: bool) -> None:
    """D-05: icon flips per state. Called from MainWindow._on_compact_toggle
    after the panel hide/show + splitter restore are done (so the icon
    is the LAST visible change of the transition)."""
    if checked:
        icon = QIcon.fromTheme(
            "sidebar-show-symbolic",
            QIcon(":/icons/sidebar-show-symbolic.svg"),
        )
        tooltip = "Show stations (Ctrl+B)"
    else:
        icon = QIcon.fromTheme(
            "sidebar-hide-symbolic",
            QIcon(":/icons/sidebar-hide-symbolic.svg"),
        )
        tooltip = "Hide stations (Ctrl+B)"
    self.compact_mode_toggle_btn.setIcon(icon)
    self.compact_mode_toggle_btn.setToolTip(tooltip)
```

---

### 3. `musicstreamer/ui_qt/station_list_peek_overlay.py` (NEW — overlay container)

**Closest analog:** `musicstreamer/ui_qt/toast.py` — `ToastOverlay(QWidget)` class. Role-match on "overlay anchored to a parent's geometry, event-filter-driven repositioning." **Key divergences:**

| Aspect | `ToastOverlay` (analog) | `StationListPeekOverlay` (new) |
|--------|-------------------------|-------------------------------|
| Parent | `MainWindow` (`ToastOverlay(self)` at `main_window.py:293`) | `centralWidget()` (Pitfall 8 — toasts must render above peek) |
| Mouse events | `WA_TransparentForMouseEvents = True` (`toast.py:31`) | **MUST NOT** set this — peek is interactive (D-15) |
| Lifetime | parent-owned, no `WA_DeleteOnClose` (`toast.py:33`) | same — parent-owned, reused across peek cycles |
| Show animation | `QPropertyAnimation` fade-in/out (`toast.py:62-75`) | **instant** (UI-SPEC discretion — no animation) |
| Child content | owned `QLabel` constructed in `__init__` | **reparented** `StationListPanel` (Pattern 4 below) |

**Imports** (mirror `toast.py:7-16`):
```python
from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QFrame, QSplitter, QVBoxLayout, QWidget

# Forward reference to avoid circular import; StationListPanel is reparented
# but not constructed here.
from musicstreamer.ui_qt.station_list_panel import StationListPanel
```

**Class skeleton (overlay-with-reparented-child pattern; mirrors `toast.py:19-79` shape but with `QFrame` base + interactive event filter):**
```python
class StationListPeekOverlay(QFrame):
    """Phase 72 / LAYOUT-01 / D-11..D-15: floating peek overlay that adopts
    the existing StationListPanel via reparenting (Pattern 4 / RESEARCH A2 —
    StationListPanel has zero parent-assumption code, verified by grep).

    Parent strategy mirrors ToastOverlay (toast.py:28-79) but with two
    deliberate divergences:
      1. Parent is centralWidget(), not MainWindow, so toasts win z-order
         (Pitfall 8).
      2. Mouse events are NOT transparent — overlay must accept clicks for
         the reparented StationListPanel to remain interactive (D-15).
    """

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        # 1px border on the right edge — palette-driven (UI-SPEC Color §peek-separator).
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            "StationListPeekOverlay {"
            " background-color: palette(base);"
            " border-right: 1px solid palette(mid);"
            "}"
        )
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        # Pitfall 2: mouse tracking so this overlay's own eventFilter sees
        # MouseMove events without a button held — needed for "cursor crossed
        # OUT of overlay bounds" detection.
        self.setMouseTracking(True)
        self.installEventFilter(self)
        self.hide()  # mirrors ToastOverlay (toast.py:77)

    def adopt(self, station_panel: StationListPanel, width: int) -> None:
        """Reparent station_panel INTO the overlay (Pattern 4)."""
        self._layout.addWidget(station_panel)   # implicit setParent(self)
        station_panel.show()                    # was hidden in compact mode
        self.setGeometry(0, 0, width, self.parent().height())
        self.show()
        self.raise_()                           # above splitter children

    def release(
        self,
        splitter: QSplitter,
        station_panel: StationListPanel,
        restore_sizes: list[int] | None,
    ) -> None:
        """Pitfall 6: use insertWidget(0, ...) — addWidget would swap visual order."""
        self._layout.removeWidget(station_panel)
        splitter.insertWidget(0, station_panel)
        station_panel.hide()                    # still in compact mode
        self.hide()

    def eventFilter(self, obj, event):
        # Close peek when cursor crosses OUT of overlay bounds (D-14).
        if obj is self and event.type() == QEvent.Leave:
            # MainWindow handles the actual reparent-back via release(); we
            # signal "user left" via a Qt event, not a custom signal, to keep
            # ownership clear (MainWindow drives lifecycle, overlay is dumb).
            mw = self.window()
            if hasattr(mw, "_close_peek_overlay"):
                mw._close_peek_overlay()
        return super().eventFilter(obj, event)
```

---

### 4. `musicstreamer/ui_qt/icons/sidebar-{show,hide}-symbolic.svg` (NEW)

**Closest analog:** `musicstreamer/ui_qt/icons/document-edit-symbolic.svg` (single `<path fill="currentColor"/>` form, 16x16 viewBox).

**Existing icon family conventions** (verified by reading `non-starred-symbolic.svg` and `document-edit-symbolic.svg`):
- viewBox: **`0 0 16 16`** (NOT 24x24 as UI-SPEC §Interaction Contract / §File Inventory states — **this is a divergence to flag for the planner**)
- width / height: `16` / `"16px"` (mixed: `non-starred-symbolic.svg` uses `"16px"`, `document-edit-symbolic.svg` uses `16`)
- fill: either `"currentColor"` (modern — see `document-edit-symbolic.svg`) or `fill="#2e3434" fill-opacity="0.34902"` (older — see `non-starred-symbolic.svg`). **Prefer `currentColor`** so palette-driven theming works.

**Sample concrete excerpt** (`document-edit-symbolic.svg` — entire file):
```xml
<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">
  <path d="M 11.5 0 L 10 1.5 L 14.5 6 L 16 4.5 Z M 8.5 3 L 0 11.5 L 0 16 L 4.5 16 L 13 7.5 Z M 1.5 12.5 L 3.5 14.5 L 1 15 Z" fill="currentColor"/>
</svg>
```

**For Phase 72** — produce two new SVGs in the same family. **PLANNER DECISION REQUIRED:** Reconcile with UI-SPEC §Spacing Scale which states "24x24 viewBox." The codebase precedent is **16x16**. Recommend the planner either:
- Use **16x16** to match existing family (and amend UI-SPEC), OR
- Use **24x24** (and accept that the two new icons will be visually larger / inconsistent with the existing 12-icon family — but render fine since `QIcon.setIconSize(QSize(20, 20))` scales the SVG anyway).

The 20x20 button icon size at `now_playing_panel.py:480, 493, 511 (in Phase 72)` will scale either viewBox cleanly.

---

### 5. `musicstreamer/ui_qt/icons.qrc` (MODIFY)

**Self-precedent** (`icons.qrc` lines 1-17 — entire file shown above in §Imports patterns).

**Add two entries** in the same alias→path form (insert before the closing `</qresource>`):
```xml
<file alias="sidebar-show-symbolic.svg">icons/sidebar-show-symbolic.svg</file>
<file alias="sidebar-hide-symbolic.svg">icons/sidebar-hide-symbolic.svg</file>
```

**Build step** (standard project convention referenced in UI-SPEC §File Inventory): `pyside6-rcc icons.qrc -o icons_rc.py`. This regenerates `icons_rc.py` to include the new resources. Do NOT hand-edit `icons_rc.py`.

---

### 6. `tests/test_phase72_*.py` (NEW — split between integration & unit tests)

**Test framework** (per conftest.py + pytest-qt): pytest 9+ with `qtbot` fixture, `QT_QPA_PLATFORM=offscreen` (set in `tests/conftest.py:13`).

**Pattern A: Toggle round-trip with single-source-of-truth invariant** (analog: `tests/test_main_window_integration.py:1186-1215`):
```python
def test_show_similar_toggle_persists_and_toggles_panel(qtbot, fake_player, fake_repo):
    """Phase 67 / SIM-01 + SIM-02 / S-01, M-01: triggering the action persists
    '1'/'0' AND flips the panel's _similar_container visibility accordingly.

    CRITICAL invariant (Pitfall 4): after each trigger,
    w._act_show_similar.isChecked() == (not w.now_playing._similar_container.isHidden()).
    """
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    # Initial: unchecked, container hidden
    assert w._act_show_similar.isChecked() is False
    assert w.now_playing._similar_container.isHidden() is True

    # Trigger ON
    w._act_show_similar.trigger()
    assert w._act_show_similar.isChecked() is True
    assert fake_repo.get_setting("show_similar_stations", "0") == "1"
    assert w.now_playing._similar_container.isHidden() is False
    # Invariant: action checked state matches container visibility
    assert w._act_show_similar.isChecked() == (not w.now_playing._similar_container.isHidden())
```

**For Phase 72** — mirror the shape, but **INVERT the persistence assertion** (NEGATIVE — D-09):
```python
def test_compact_mode_toggle_does_not_persist_to_repo(qtbot, fake_player, fake_repo):
    """Phase 72 D-09 / LAYOUT-01: session-only — toggling compact mode MUST NOT
    write to repo settings. INVERSE of Phase 47.1 / Phase 67 positive-persistence
    pattern (test_show_similar_toggle_persists_and_toggles_panel at line 1186).
    """
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    keys_before = set(fake_repo._settings.keys())

    btn = w.now_playing.compact_mode_toggle_btn
    btn.toggle()  # ON
    btn.toggle()  # OFF
    btn.toggle()  # ON again

    keys_after = set(fake_repo._settings.keys())
    new_keys = keys_after - keys_before
    assert not any("compact" in k for k in new_keys), (
        f"D-09 violated — compact-mode key(s) written to repo: "
        f"{new_keys & {k for k in new_keys if 'compact' in k}}"
    )
```

**Pattern B: Single-source-of-truth invariant** (mirror `_act_show_similar.isChecked() == ...`):
```python
def test_compact_button_checked_matches_station_panel_hidden(qtbot, fake_player, fake_repo):
    """Mirrors Phase 67 SIM-02 invariant at test_main_window_integration.py:1191
    but with button.isChecked() instead of action.isChecked()."""
    w = MainWindow(fake_player, fake_repo)
    qtbot.addWidget(w)
    btn = w.now_playing.compact_mode_toggle_btn
    assert btn.isChecked() is False
    assert w.station_panel.isHidden() is False
    btn.toggle()
    assert btn.isChecked() is True
    assert w.station_panel.isHidden() is True
```

**Pattern C: Icon-flip unit test** (analog: `tests/test_now_playing_panel.py:298-306`):
```python
def test_play_pause_icon_toggle(qtbot):
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    # Initial: paused → tooltip "Play"
    assert panel.play_pause_btn.toolTip() == "Play"
    panel.on_playing_state_changed(True)
    assert panel.play_pause_btn.toolTip() == "Pause"
```
**For Phase 72** — mirror this shape for the compact button:
```python
def test_compact_button_icon_flips_per_state(qtbot):
    """Phase 72 D-05 / LAYOUT-01: button icon + tooltip flip on toggle.
    Mirrors test_play_pause_icon_toggle (test_now_playing_panel.py:298)."""
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    assert panel.compact_mode_toggle_btn.toolTip() == "Hide stations (Ctrl+B)"
    panel.set_compact_button_icon(checked=True)
    assert panel.compact_mode_toggle_btn.toolTip() == "Show stations (Ctrl+B)"
    panel.set_compact_button_icon(checked=False)
    assert panel.compact_mode_toggle_btn.toolTip() == "Hide stations (Ctrl+B)"
```

**Pattern D: QA-05 no-lambda structural test** (analog: `tests/test_main_window_integration.py:631-652`):
```python
def test_buffer_percent_bound_method_connect_no_lambda(qtbot, window, fake_player):
    """D-13 + QA-05: emitting Player.buffer_percent updates both bar and
    label on the now-playing panel via a bound-method connect (no lambda)."""
    import inspect
    from musicstreamer.ui_qt import main_window as mw_mod

    fake_player.buffer_percent.emit(42)
    assert window.now_playing.buffer_bar.value() == 42
    assert window.now_playing.buffer_pct_label.text() == "42%"

    src = inspect.getsource(mw_mod.MainWindow)
    for line in src.splitlines():
        if "buffer_percent.connect" in line:
            assert "lambda" not in line, (
                f"D-13 violated — lambda found on buffer_percent.connect line: {line!r}"
            )
            break
    else:
        raise AssertionError("buffer_percent.connect line not found in MainWindow source")
```
**For Phase 72** — apply to BOTH new signal-connect sites (`compact_mode_toggled.connect` AND `self._compact_shortcut.activated.connect`):
```python
def test_compact_mode_signal_connections_no_lambda():
    """QA-05: bound-method connects only — no self-capturing lambdas.
    Mirrors test_buffer_percent_bound_method_connect_no_lambda."""
    import inspect
    from musicstreamer.ui_qt import main_window as mw_mod
    src = inspect.getsource(mw_mod.MainWindow)
    for needle in ("compact_mode_toggled.connect", "_compact_shortcut.activated.connect"):
        for line in src.splitlines():
            if needle in line:
                assert "lambda" not in line, f"QA-05 violated on {needle}: {line!r}"
                break
        else:
            raise AssertionError(f"{needle} line not found in MainWindow source")
```

**Pattern E: FakeRepo for assertion** — use the integration-test FakeRepo at `tests/test_main_window_integration.py:97-105` (has `_settings: dict[str, str]`, `get_setting`, `set_setting`). For now-playing panel unit tests, use the simpler `FakeRepo` form from `tests/test_now_playing_panel.py` (constructed as `FakeRepo({"volume": "80"})`).

---

## Shared Patterns

### Shared Pattern 1: Bound-method signal-slot connects (QA-05 — project-wide invariant)

**Source:** `musicstreamer/ui_qt/main_window.py:331-358` (every connect uses bound method, never lambda).
**Apply to:** All new signal connects in Phase 72 — `compact_mode_toggled.connect`, `_compact_shortcut.activated.connect`, `_peek_dwell_timer.timeout.connect`, `compact_mode_toggle_btn.toggled.connect`.
**Structural test enforcing it:** `tests/test_main_window_integration.py:631-652`.

```python
# Correct:
self._compact_shortcut.activated.connect(self._on_compact_shortcut_activated)

# WRONG — Phase 72 plan-check will fail:
self._compact_shortcut.activated.connect(
    lambda: self.now_playing.compact_mode_toggle_btn.toggle()
)
```

---

### Shared Pattern 2: Side-effect import of `icons_rc` before any `QIcon` lookup

**Source:** `musicstreamer/ui_qt/main_window.py:31` and `musicstreamer/ui_qt/now_playing_panel.py:51`:
```python
# Side-effect import: registers the :/icons/ resource prefix before any
# QIcon lookup. Must live at module top so tests that construct MainWindow
# (not just the GUI entry point) also get resources registered — per
# Phase 36 research Pitfall 2 and D-24.
from musicstreamer.ui_qt import icons_rc  # noqa: F401
```
**Apply to:** `station_list_peek_overlay.py` (NEW file) MUST include this side-effect import if it does any `QIcon(":/icons/...")` lookup. Currently the peek overlay does NOT load icons itself (it just hosts a reparented panel), so this may not be strictly necessary — but include it defensively for symmetry with sibling modules.

---

### Shared Pattern 3: `QIcon.fromTheme(name, QIcon(":/icons/{name}.svg"))` fallback chain

**Source:** `now_playing_panel.py:484-486` (star_btn), `now_playing_panel.py:496-500` (eq_toggle_btn), `now_playing_panel.py:435-440` (play_pause_btn).
```python
QIcon.fromTheme("non-starred-symbolic", QIcon(":/icons/non-starred-symbolic.svg"))
```
**Apply to:** Both icon-load sites for the new compact-toggle button — initial set in `__init__` AND in `set_compact_button_icon()`. Theme lookup falls back to the resource SVG if the system theme doesn't provide the glyph (per project convention).

---

### Shared Pattern 4: `setMouseTracking(True)` on the event-filter source widget

**Source:** RESEARCH Pattern 3 + Pitfall 2. No existing in-codebase precedent (this phase introduces mouse-move event filtering for the first time).
**Apply to:** MainWindow (for the dwell-trigger filter) AND the peek overlay (for the leave-bounds filter). Without it, `MouseMove` only fires during drags.

```python
# In _install_peek_hover_filter:
self.setMouseTracking(True)
self.centralWidget().setMouseTracking(True)

# In StationListPeekOverlay.__init__:
self.setMouseTracking(True)
```

---

### Shared Pattern 5: Phase 47.1 / Phase 67 single-source-of-truth toggle invariant — **APPLIED WITHOUT PERSISTENCE (anti-precedent)**

**Source (positive form — Phase 47.1):** `main_window.py:743-746` + initial-state push at `main_window.py:381`.
**Source (positive test):** `tests/test_main_window_integration.py:1186-1215`.

Phase 72 applies the **visibility-mirror** half of the invariant (button.isChecked() ⇔ station_panel.isVisible()) but **inverts the persistence half** (no `repo.set_setting`). This is documented as a deliberate divergence per **D-09**.

**Anti-precedent test (apply to Phase 72):**
```python
# Phase 47.1 / Phase 67 form (DO NOT COPY for Phase 72):
assert fake_repo.get_setting("show_similar_stations", "0") == "1"

# Phase 72 form (INVERSE):
assert "compact_mode" not in fake_repo._settings
assert not any("compact" in k for k in fake_repo._settings.keys())
```

---

## No Analog Found

| File / Pattern | Reason | Mitigation |
|----------------|--------|-----------|
| `QShortcut(QKeySequence("Ctrl+B"), self, context=Qt.WidgetWithChildrenShortcut)` (Ctrl+B registration in `main_window.py`) | **First QShortcut in the codebase.** Verified zero existing usage via `grep -rn "QShortcut\|setShortcut\|QKeySequence" musicstreamer/` returning empty. | Use Qt 6 documentation directly: `doc.qt.io/qtforpython-6/PySide6/QtGui/QShortcut.html` (cited in RESEARCH Pattern 2). RESEARCH.md §"Pattern 2: First-In-Codebase QShortcut" provides the canonical code form. Phase 72 establishes the precedent for any future shortcut. |
| `setMouseTracking(True)` + `QEvent.MouseMove` event-filter pattern | No in-codebase use of `QEvent.MouseMove`. `ToastOverlay.eventFilter` only handles `QEvent.Resize`. | Use RESEARCH §Pattern 3 (cited from `doc.qt.io QMouseEvent` + `pythonguis.com`). Pitfall 2 documents the most common failure mode (tracking not enabled). |
| Negative-assertion test for "no setting written" | All existing toggle tests assert POSITIVE persistence. Phase 72's session-only invariant requires the INVERSE form. | Mirror `test_show_similar_toggle_persists_and_toggles_panel` (line 1186-1215) shape but flip the `assert fake_repo.get_setting(...) == "1"` line into `assert "compact" not in fake_repo._settings`. Pattern shown in §"Pattern A" above. |

---

## Metadata

**Analog search scope:**
- `musicstreamer/ui_qt/` (all `.py` files — full tree listing)
- `musicstreamer/ui_qt/icons/` (full SVG family)
- `tests/` (`test_main_window_integration.py`, `test_now_playing_panel.py`, `test_main_window_*.py`)
- `musicstreamer/` (grep for `QShortcut|setShortcut|QKeySequence` — empty)

**Files scanned (Read):**
- `musicstreamer/ui_qt/main_window.py` (lines 1-100, 160-261, 270-360, 375-394, 740-758)
- `musicstreamer/ui_qt/now_playing_panel.py` (lines 1-80, 200-300, 410-530)
- `musicstreamer/ui_qt/toast.py` (full file, 1-114)
- `musicstreamer/ui_qt/icons.qrc` (full file)
- `musicstreamer/ui_qt/icons/non-starred-symbolic.svg` (full file)
- `tests/test_main_window_integration.py` (lines 100-200, 630-660, 1185-1220)
- `tests/test_now_playing_panel.py` (lines 170-200, 295-315)
- `tests/conftest.py` (lines 1-60)

**Files greped (Bash):**
- `musicstreamer/ui_qt/main_window.py` — found 4 toggle slot locations
- `musicstreamer/` (recursive) — confirmed zero `QShortcut` usage
- `musicstreamer/ui_qt/station_list_panel.py` — confirmed zero parent-assumption code
- `tests/test_main_window_integration.py` — found persistence-test pattern at line 1186, lambda-ban pattern at line 631
- `musicstreamer/ui_qt/icons/*.svg` — verified 16x16 viewBox convention (NOT 24x24 as UI-SPEC §Spacing claims — flagged for planner)

**Pattern extraction date:** 2026-05-13

**Planner notes — divergences to resolve:**
1. **Icon viewBox size:** UI-SPEC §Spacing Scale and §File Inventory state "24x24" but the entire existing 12-icon family uses 16x16. Planner should choose one and amend UI-SPEC if 16x16 is selected.
2. **CONTEXT D-04 vs UI-SPEC §Interaction Contract on control-row order:** CONTEXT D-04 says "after StreamPicker" (was correct pre-EQ/pre-volume). UI-SPEC §Interaction Contract states the corrected order is `... volume_slider → [NEW] → addStretch(1)` (insert at line 514, between line 513 `controls.addWidget(self.volume_slider)` and line 515 `controls.addStretch(1)`). **UI-SPEC is authoritative.** Verified against `now_playing_panel.py:509-515`.
3. **Z-order parent strategy:** ToastOverlay parents to MainWindow; peek overlay MUST parent to centralWidget so toasts win z-order. This is opposite of the obvious "mirror ToastOverlay verbatim" approach — flagged in §Pattern Assignments §3 and Shared Pattern §"ToastOverlay analog".
