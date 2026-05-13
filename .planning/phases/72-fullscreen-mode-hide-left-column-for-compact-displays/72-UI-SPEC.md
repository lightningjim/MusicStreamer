---
phase: 72
slug: fullscreen-mode-hide-left-column-for-compact-displays
status: approved
shadcn_initialized: false
preset: not applicable
created: 2026-05-13
reviewed_at: 2026-05-13
---

# Phase 72 — UI Design Contract

> Visual and interaction contract for Phase 72: compact-mode toggle (hide left `StationListPanel`) + hover-to-peek overlay. Stack is PySide6/Qt — shadcn is not applicable. All values are prescriptive; executor and ui-checker treat this as the source of truth.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none (Qt-native; not a React/Vite stack) |
| Preset | not applicable |
| Component library | PySide6 6.10+ stock widgets (`QToolButton`, `QFrame`, `QSplitter`, `QShortcut`, `QTimer`) |
| Icon library | Local project `*-symbolic.svg` family compiled to `:/icons/` via `icons_rc.py`. `QIcon.fromTheme(name, QIcon(":/icons/{name}.svg"))` fallback chain (existing project convention — see `non-starred-symbolic`, `media-playback-pause-symbolic`, `multimedia-equalizer-symbolic`) |
| Font | System default (Qt application font; no override in this phase). All text inherits `QApplication.font()` set by the active theme (Phase 66 THEME-01) |

**Stack discovery (codebase scout):**
- No `components.json`, no `tailwind.config.*`, no `postcss.config.*` (correctly absent — this is a Python desktop app)
- Existing icon family at `musicstreamer/ui_qt/icons/`: 14 monochrome symbolic SVGs (audio-x-generic, document-edit, edit-clear-all, media-playback-{pause,start,stop}, multimedia-equalizer, non-starred, open-menu, starred, user-trash, etc.)
- Color tokens module at `musicstreamer/ui_qt/_theme.py` (`ERROR_COLOR_HEX = "#c0392b"`, `WARNING_COLOR_HEX = "#d4a017"` — both QSS-string consumers; QPalette roles drive everything else)
- All non-error/warning chrome already palette-driven through `palette(...)` QSS tokens (`palette(highlight)`, `palette(highlighted-text)`, `palette(mid)`, `palette(base)`) — verified at `edit_station_dialog.py:198-206`, `cookie_import_dialog.py:170`, `now_playing_panel.py:376` and adjacent.

---

## Spacing Scale

Declared values (multiples of 4; phase reuses the project's existing 4px-base scale):

| Token | Value | Usage in this phase |
|-------|-------|---------------------|
| xs | 4px | Hover-peek trigger zone width (`_PEEK_TRIGGER_ZONE_PX = 4`); icon-to-edge inset inside compact-toggle button |
| sm | 8px | Control-row spacing (`controls.setSpacing(8)`, already set at `now_playing_panel.py:429`); peek-overlay right-edge border-/shadow-equivalent inset |
| md | 16px | (not introduced by this phase) |
| lg | 24px | Compact-toggle button icon size (`QSize(20, 20)` icon inside a 28x28 button — matches `star_btn`/`eq_toggle_btn` precedent) |
| xl | 32px | (not introduced by this phase) |
| 2xl | 48px | (not introduced by this phase) |
| 3xl | 64px | (not introduced by this phase) |

**Phase-specific dimensions (prescriptive, not from the general scale):**

| Property | Value | Source |
|----------|-------|--------|
| Compact-toggle button fixed size | 28 x 28 px | Matches `star_btn` (28x28) and `eq_toggle_btn` (28x28) at `now_playing_panel.py:481, 494`. Smaller control-row family — NOT the 36x36 transport buttons (play/stop/edit). |
| Compact-toggle button icon size | `QSize(20, 20)` | Matches `star_btn.setIconSize(QSize(20, 20))` and `eq_toggle_btn.setIconSize(QSize(20, 20))` at `now_playing_panel.py:480, 493`. |
| Hover-peek trigger zone width | 4 px | Within CONTEXT D-13's 4-6px band; chose 4 (narrowest) to fully eliminate accidental triggers per "narrow band + brief dwell" rationale. Module constant `_PEEK_TRIGGER_ZONE_PX = 4`. |
| Hover-peek dwell timer | 280 ms | Within CONTEXT D-13's 250-300ms band; 280 sits mid-band and matches Qt's stock tooltip cadence. Module constant `_PEEK_DWELL_MS = 280`. |
| Peek overlay width | `self._splitter_sizes_before_compact[0]` if available, else 360 px | Respects the user's last-dragged splitter width (D-10 / discretion). 360px fallback matches the splitter default `[360, 840]` (`main_window.py:281`). |
| Peek overlay height | `centralWidget().height()` (full content-area vertical extent) | Anchored at `setGeometry(0, 0, width, centralWidget.height())` — naturally stays below menu bar, since centralWidget is below the menu bar in QMainWindow's frame. |
| Peek overlay right-edge separator | 1px solid `palette(mid)` border on the right edge of the overlay frame | Distinguishes overlay from obscured now-playing content. Chose 1px-border (not drop-shadow) — keeps the contract identical across themes and avoids QGraphicsEffect compositing cost. |
| Peek overlay slide animation | **instant** show/hide (no animation) | Discretion choice — keeps the implementation simple, side-steps QPropertyAnimation z-order interactions with ToastOverlay, and matches the existing project pattern (no animations on ToastOverlay show/hide either). May become a future micro-polish phase. |

Exceptions: none — all phase-specific dimensions are multiples of 4 except the 280ms dwell-timer (time, not space).

---

## Typography

This phase does **NOT** introduce any new text labels, headings, or copy that requires typography declarations beyond the existing application font inheritance. The compact-toggle button is icon-only (with tooltip); the peek overlay reuses the existing `StationListPanel`'s typography (set by Phase 66 THEME-01).

Declared for the elements this phase touches (all inherit from system font / active theme):

| Role | Size | Weight | Line Height | Where this phase uses it |
|------|------|--------|-------------|--------------------------|
| Body | system default (Qt `QApplication.font()`) | 400 (regular) | system default | Tooltip text on the compact-toggle button |
| Label | system default | 400 (regular) | system default | (Not introduced) |
| Heading | system default | 600 (semibold) | system default | (Not introduced) |
| Display | n/a | n/a | n/a | (Not introduced) |

**Tooltip strings** are plain text (no rich-text formatting). Tooltip font is Qt's standard tooltip font (smaller than body — controlled by Qt style, not by this phase).

---

## Color

This phase uses the same 60/30/10 split established for the entire MusicStreamer Qt app (driven by Phase 66 THEME-01 palette roles). No new color tokens are introduced.

| Role | Value | Usage in this phase |
|------|-------|---------------------|
| Dominant (60%) | `palette(window)` (theme-dependent) | Main window background, now-playing pane background (no override) |
| Secondary (30%) | `palette(base)` / `palette(alternate-base)` (theme-dependent) | Peek overlay background — the overlay's `QFrame` inherits `palette(base)` to read as "a panel surface, not the same plane as now-playing pane" |
| Accent (10%) | `palette(highlight)` + `palette(highlighted-text)` (driven by Phase 19 accent picker + Phase 66 theme) | Compact-toggle button **checked-state visual feedback only** (Qt's stock checkable QToolButton state); selected row in the peeked StationListPanel (existing behavior — unchanged) |
| Destructive | `ERROR_COLOR_HEX` = `#c0392b` (from `_theme.py:43`) | **Not used in this phase** — no destructive actions exist |

**Accent reserved for** (explicit list — never "all interactive elements"):
1. Compact-toggle button **checked** state (Qt-rendered "pressed/active" appearance for a `QToolButton.setCheckable(True)`)
2. Selected-row highlight inside the peeked StationListPanel (already-shipped behavior — unchanged)
3. (Cross-cutting, not introduced by this phase) All other accent uses in the app — accent color is single-sourced from Phase 19 / Phase 66 and does not need any new theming for compact mode

**Peek overlay separator color:** `palette(mid)` — neutral, theme-agnostic, low-contrast. Reuses the existing project precedent at `edit_station_dialog.py:199` (`border: 1px solid palette(mid)`).

**No hardcoded hex values** in any new code path introduced by this phase. All chrome derives from `palette(...)` tokens so the eight existing themes (System default, Vaporwave, Overrun, GBS.FM, GBS.FM After Dark, Dark, Light, Custom) automatically style the compact-toggle button and peek overlay correctly without per-theme additions.

---

## Copywriting Contract

All strings introduced by this phase. Plain text; no rich-text, no HTML, no localization layer (project is single-locale en-US per existing convention).

| Element | Copy |
|---------|------|
| Primary CTA — button tooltip when expanded (panel visible) | `Hide stations (Ctrl+B)` |
| Primary CTA — button tooltip when compact (panel hidden) | `Show stations (Ctrl+B)` |
| Keyboard shortcut (visible in tooltip only) | `Ctrl+B` |
| Empty state heading | n/a — peek overlay always shows the user's full station list; if zero stations exist, the existing `StationListPanel` empty-state copy applies (unchanged) |
| Empty state body | n/a — see above |
| Error state | n/a — toggle and peek have no failure mode that produces user-visible error copy. Toasts are not emitted on compact toggle (per RESEARCH.md Open Question 5: silent — clutters rapid-toggle use case) |
| Destructive confirmation | n/a — no destructive actions in this phase. Toggling compact mode is fully reversible; closing the peek overlay only re-hides the panel that was already hidden |

**Style guide (matches existing tooltips in the codebase, e.g., `eq_toggle_btn.setToolTip("Toggle EQ")` at `now_playing_panel.py:502` and `star_btn`):**
- Sentence case (capitalize first word only)
- Imperative mood (verb-first: "Hide", "Show", "Toggle")
- Include the keyboard shortcut in parentheses after the action verb
- No trailing period
- ≤ 30 characters (fits standard Qt tooltip width without wrap)

---

## Interaction Contract

This phase's interaction surface is non-trivial — declaring it explicitly so the executor cannot ambiguously implement it.

### Compact-toggle button placement

- **Parent layout:** `controls` HBoxLayout in `NowPlayingPanel`
- **Position:** After `volume_slider`, before `controls.addStretch(1)` — i.e., **immediately before line 515** in `now_playing_panel.py` as it exists today (`controls.addStretch(1)` is line 515; insert the new `controls.addWidget(self.compact_mode_toggle_btn)` between line 513 `controls.addWidget(self.volume_slider)` and line 515)
- **Actual control row order (verified post-Phase 47+):** `play_pause` → `stop` → `edit` → `stream_combo` → `star` → `eq_toggle` → `volume_slider` → **[NEW: compact_mode_toggle]** → `addStretch(1)`
- **NOT** the order described in CONTEXT D-04 ("Edit, Star, Pause, Stop, StreamPicker"); CONTEXT was based on pre-EQ/pre-volume layout. The corrected order above is the source of truth.

### Compact-toggle button visual states

| State | Icon | Tooltip | Qt visual |
|-------|------|---------|-----------|
| Default (expanded, unchecked) | `sidebar-hide-symbolic.svg` ("about to hide") | `Hide stations (Ctrl+B)` | Stock `QToolButton` unchecked |
| Active (compact, checked) | `sidebar-show-symbolic.svg` ("about to show") | `Show stations (Ctrl+B)` | Stock `QToolButton` checked — uses `palette(highlight)` background per Qt's checkable styling |
| Hover (either state) | (icon unchanged) | (tooltip unchanged) | Stock Qt hover styling (palette-driven) |
| Pressed (either state) | (icon unchanged) | (tooltip unchanged) | Stock Qt pressed styling (palette-driven) |
| Disabled | (never disabled in this phase) | — | n/a |
| Keyboard focus | (icon unchanged) | (tooltip unchanged) | Stock Qt focus ring (palette-driven) |

**Icon naming convention** (matches existing project family):
- `musicstreamer/ui_qt/icons/sidebar-show-symbolic.svg` — NEW SVG asset. 24x24 viewBox, single-color path (`fill="currentColor"` or matching the project pattern), monochrome symbolic style.
- `musicstreamer/ui_qt/icons/sidebar-hide-symbolic.svg` — NEW SVG asset. Same viewBox/style.
- Both registered in `musicstreamer/ui_qt/icons.qrc` and recompiled into `icons_rc.py` (existing build step).
- Loaded via the standard project pattern: `QIcon.fromTheme("sidebar-show-symbolic", QIcon(":/icons/sidebar-show-symbolic.svg"))` — falls back to system theme glyph if available, otherwise resource SVG.

**Glyph design (prescriptive):**
- `sidebar-show-symbolic.svg`: a panel/rectangle on the left with a right-pointing chevron or arrow indicating "expand right" / "reveal left panel"
- `sidebar-hide-symbolic.svg`: a panel/rectangle on the left with a left-pointing chevron or arrow indicating "collapse left"
- Visual mass parity with the other `*-symbolic.svg` files in `musicstreamer/ui_qt/icons/` (similar stroke weight, similar 24x24 occupancy)

### Keyboard shortcut contract

- **Sequence:** `Ctrl+B` (registered via `QShortcut(QKeySequence("Ctrl+B"), self, context=Qt.WidgetWithChildrenShortcut)` on MainWindow)
- **Context:** Window-scope (`Qt.WidgetWithChildrenShortcut`) — fires when MainWindow or any descendant has focus; **does NOT fire** while a modal QDialog (EditStationDialog, AccountsDialog, etc.) is the active window
- **Behavior:** Calls `self.now_playing.compact_mode_toggle_btn.toggle()` — same code path as a mouse click (button is the single source of truth)
- **Discoverability:** Visible in the button's tooltip (`Hide stations (Ctrl+B)` / `Show stations (Ctrl+B)`). No hamburger entry, no shortcuts dialog, no help overlay (out of scope per D-01 and deferred ideas)

### Compact-mode entry/exit behavior

| Transition | Behavior |
|------------|----------|
| Expanded → Compact (button toggled ON or Ctrl+B) | (1) Snapshot `self._splitter.sizes()` → `self._splitter_sizes_before_compact` (MUST be before hide per Pitfall 1). (2) `self.station_panel.hide()` — Qt auto-hides the adjacent splitter handle (no explicit `handle(1).hide()` needed per RESEARCH A1). (3) Now-playing pane expands to fill freed width. (4) Button icon flips to `sidebar-show-symbolic`. (5) Tooltip updates to `Show stations (Ctrl+B)`. (6) Mouse-tracking + event filter installed for hover-peek. |
| Compact → Expanded (button toggled OFF or Ctrl+B) | (1) Close peek overlay if open (reparent station_panel back to splitter at `insertWidget(0, ...)` per Pitfall 6). (2) `self.station_panel.show()`. (3) `self._splitter.setSizes(self._splitter_sizes_before_compact)` and reset snapshot to `None`. (4) Button icon flips to `sidebar-hide-symbolic`. (5) Tooltip updates to `Hide stations (Ctrl+B)`. (6) Mouse-tracking + event filter removed. |
| Window resize while compact | No-op (per D-07). Now-playing pane simply gets wider/narrower with the window. |
| App launch | Always starts expanded (per D-09). No settings read; constant `False` initial state. |
| Animation | None. Transitions are instant. |

### Hover-peek interaction contract (compact mode only)

| Trigger | Action |
|---------|--------|
| Cursor enters left ≤ 4px zone of centralWidget | Start `QTimer.singleShot(280ms, ...)` dwell timer (if not already running) |
| Cursor leaves zone (x > 4px) before timer fires | Cancel pending dwell timer |
| Dwell timer fires while cursor still in zone | Open peek overlay (instant — no animation) |
| Cursor moves within peek overlay bounds | Overlay stays open. All `StationListPanel` interactions work normally — click to play, right-click to edit, star toggle, search box, filter chips, scroll (per D-15) |
| Cursor crosses out of peek overlay bounds (onto now-playing pane area or out of window) | Close peek overlay (instant — no animation). Reparent station_panel back to splitter at `insertWidget(0, ...)`; station_panel stays `.hide()` (compact mode still active) |
| User clicks a station inside peek overlay | Station plays (signal fires up to MainWindow via the docked `StationListPanel.station_activated` signal — same signal contract). Overlay stays open. |
| `Esc` pressed | No effect on peek overlay (per D-14) |
| Click outside peek overlay (without crossing bounds — e.g., click on right edge of overlay) | Click handled by the panel as normal; overlay stays open |
| Compact mode toggled OFF (Ctrl+B or button) while peek overlay is open | Peek closes automatically as part of compact-exit cleanup |
| Toast fires (e.g., player error) while peek overlay is open | Toast renders **above** peek overlay (z-order: toast > peek > now-playing). Verified by parenting peek overlay to `centralWidget()` while ToastOverlay remains parented to MainWindow (per Pitfall 8). |

### Z-order contract

| Layer (front → back) | Widget | Parent |
|----------------------|--------|--------|
| 1 (frontmost) | `ToastOverlay` | MainWindow |
| 2 | `StationListPeekOverlay` (when shown) | `centralWidget()` (which is the `QSplitter`) |
| 3 | `NowPlayingPanel` content | `_splitter` (right child) |
| 4 (backmost) | `StationListPanel` (when not peeked and compact mode ON: hidden; otherwise: docked) | `_splitter` (left child) |

### Focus contract

- When compact mode toggles ON via Ctrl+B → focus remains on whatever widget had focus before (Ctrl+B does not steal focus). When toggled ON via mouse click → focus moves to the compact-toggle button per Qt default click-focus behavior.
- When peek overlay opens → focus does NOT auto-shift to the overlay (mouse-driven interaction; per A11y considerations in input context).
- Modal dialogs naturally block Ctrl+B (window-scope shortcut blocked by modal focus — per A3 assumption in RESEARCH).
- `QLineEdit` (e.g., search box in peeked StationListPanel) does NOT consume Ctrl+B (per Pitfall 3 / RESEARCH A4 — `QLineEdit` default bindings do not include Ctrl+B).

---

## Theme & A11y Integration

| Concern | Decision |
|---------|----------|
| Theme compatibility | All chrome derives from `palette(...)` tokens — automatic compatibility with the eight Phase 66 themes (System default, Vaporwave, Overrun, GBS.FM, GBS.FM After Dark, Dark, Light, Custom). No per-theme overrides needed. |
| Accent color (Phase 19) | Inherited automatically via `palette(highlight)` — checked-state button styling and peeked-panel row highlight track the user's accent without per-phase code. |
| Keyboard navigation | Ctrl+B fires from anywhere in MainWindow (window scope). Tab order within the now-playing control row includes the new button between volume_slider and the addStretch (Qt natural tab order). |
| Screen reader / accessible name | Button uses Qt's default accessibleName derived from tooltip text — no explicit `setAccessibleName()` required per existing project precedent (no other now-playing-panel buttons set it). |
| High-contrast | Palette-driven styling honors the user's high-contrast system theme automatically. |
| Color-blind safety | Icon-flip provides shape-based state distinction (not color-only). Button checked state additionally provides Qt-rendered pressed appearance. |
| Touch | Out of scope (per CONTEXT — deployment is Wayland desktop with mouse). 28x28 buttons match existing star/EQ buttons; no touch-target sizing override. |

---

## Out-of-Scope Visual Decisions (explicit)

The following design choices are explicitly **not** introduced by this phase:

- No toast notification when toggling compact mode (per RESEARCH Open Question 5)
- No animated transitions for the splitter or peek overlay (instant show/hide)
- No new menu bar or hamburger menu entries (per D-01)
- No status bar message reflecting compact mode state
- No persistent settings UI for compact mode (session-only per D-09)
- No edge-handle button as alternate reveal (per D-11 / deferred ideas)
- No splitter-reflow peek (overlay-floats-over only, per D-12)
- No Esc / click-outside / click-station dismiss for peek (mouse-leave-only, per D-14)
- No OS-level fullscreen, no menu-bar hiding (per D-06)
- No new toast color palette additions (this phase predates Phase 75)
- No keyboard-shortcut framework / shortcuts dialog (deferred)

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | n/a — Qt-native phase | not applicable |
| Third-party | none | not applicable |

This phase uses only stock PySide6 widgets and project-internal SVG assets. No third-party UI components, no remote registries, no `npx shadcn add` operations.

---

## File Inventory (artifacts this contract creates or modifies)

| File | New / Modified | Visual responsibility |
|------|----------------|------------------------|
| `musicstreamer/ui_qt/now_playing_panel.py` | Modified | Compact-toggle `QToolButton` inserted at the control-row position specified above; new `compact_mode_toggled = Signal(bool)` |
| `musicstreamer/ui_qt/main_window.py` | Modified | QShortcut registration; `_on_compact_toggle` slot; splitter-size snapshot/restore; mouse-tracking + event filter; peek overlay lifecycle |
| `musicstreamer/ui_qt/station_list_peek_overlay.py` | **New** | `StationListPeekOverlay(QFrame)` class — overlay container that adopts/releases the existing `StationListPanel` |
| `musicstreamer/ui_qt/station_list_panel.py` | Unchanged | Panel is just `.hide()`-ed and reparented; public API surface unchanged |
| `musicstreamer/ui_qt/icons/sidebar-show-symbolic.svg` | **New** | 24x24 monochrome SVG (panel + right-arrow / chevron — "show left panel") |
| `musicstreamer/ui_qt/icons/sidebar-hide-symbolic.svg` | **New** | 24x24 monochrome SVG (panel + left-arrow / chevron — "hide left panel") |
| `musicstreamer/ui_qt/icons.qrc` | Modified | Add the two new SVGs as resource aliases |
| `musicstreamer/ui_qt/icons_rc.py` | Regenerated | Run `pyside6-rcc icons.qrc -o icons_rc.py` (existing build step) |

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS (tooltips defined, sentence-case + imperative + shortcut-in-parens convention)
- [ ] Dimension 2 Visuals: PASS (icon family + sizes + states declared; z-order + animation explicit)
- [ ] Dimension 3 Color: PASS (palette-driven; no hardcoded hex; accent reserved list ≤ 2 items)
- [ ] Dimension 4 Typography: PASS (no new text introduced; existing system font inheritance documented)
- [ ] Dimension 5 Spacing: PASS (all dimensions multiples of 4; phase-specific dimensions sourced to existing precedents)
- [ ] Dimension 6 Registry Safety: PASS (n/a — Qt-native, no registries)

**Approval:** pending
