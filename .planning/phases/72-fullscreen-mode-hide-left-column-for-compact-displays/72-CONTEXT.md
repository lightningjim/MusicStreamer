# Phase 72: Fullscreen mode — hide left column for compact displays - Context

**Gathered:** 2026-05-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Add a "compact mode" that hides the left column (`StationListPanel`) so the right column (`NowPlayingPanel`) claims the full window width. The trigger problem: when the main window is moved to a small/secondary display and shrunk near its 560px minimum, the existing two-pane QSplitter forces both panels (left min 280px + right min 560px = 840px total) to overflow their stated minimums; the now-playing pane's bottom-bar controls then compress and overlap. Hiding the left column lets the right column occupy ~full window width and fits cleanly at the 560px floor.

The toggle must be fast (keyboard shortcut + visible button on the persistent right pane) because the user flips it as they physically move the laptop between a big primary display and a small secondary display. A hover-to-peek mechanism on the left edge lets the user briefly see the station list overlay without exiting compact mode.

**In scope:**
- New `QToolButton` (or similar) on the far right of the now-playing pane's control row, after the StreamPicker (`now_playing_panel.py` icy_row / control row near line 413+). Checkable, icon flips between expanded (sidebar visible) and collapsed (sidebar hidden) glyphs. Click toggles compact mode.
- Application-level `QShortcut(QKeySequence("Ctrl+B"), self)` registered on `MainWindow` (first keyboard shortcut in the codebase — establishes the pattern for future shortcuts). Triggers the same compact-mode toggle.
- Compact-mode ON behavior: `self.station_panel.hide()`. The QSplitter remains the `centralWidget`; only the left child is hidden. The right pane expands to fill the freed space. Splitter handle is hidden alongside (no dangling thin vertical line on the left edge).
- Compact-mode OFF behavior: `self.station_panel.show()`. Splitter sizes are restored to the in-memory snapshot captured at the moment compact mode was entered (`self._splitter.sizes()` before hide → cached → applied on show). Splitter handle re-shown.
- **No SQLite persistence.** Compact-mode toggle state is session-only and resets to OFF (expanded) on every app launch. This is a deliberate divergence from the Phase 47.1 / Phase 67 hamburger-toggle precedent because the user moves the device between screens; relaunching at home in compact mode would be annoying.
- **Hover-to-peek overlay:** Left 4-6px of the window acts as a hover trigger zone. After ~250-300ms dwell, an overlay panel slides out from the left edge containing a copy/instance of `StationListPanel` (or the underlying tree model rendered in an overlay-style container). Panel is positioned absolutely OVER the now-playing pane (NOT via QSplitter reflow); no layout churn in the right pane while peeking.
- Peek dismiss: ONLY mouse-leaves-the-overlay closes it. Clicking a station in the peeked overlay does NOT auto-dismiss (the user can browse and click multiple stations in succession). Esc and click-outside also do NOT dismiss — keep the interaction model minimal.
- Peek overlay interaction: must remain fully functional — click a station to play, right-click to edit, star toggle, search/filter chip row all work as in the docked mode.
- **No hamburger menu entry for the toggle.** This is explicit user-direction — the button on the now-playing pane and Ctrl+B are the only activation surfaces (since the now-playing pane is always visible, the button is always reachable).
- **No auto-exit on window resize.** Compact mode stays on until manually toggled off, even if the user resizes the window back to a wide size. Mental model: the user is the authority on screen size; the app doesn't second-guess.
- Tests: Qt-level toggle round-trip (entering and exiting compact preserves splitter sizes), peek-overlay lifecycle (hover triggers, dwell timer fires, mouse-leave dismisses, click-station keeps peek open), keyboard shortcut wiring (Ctrl+B toggles same state as the button), button icon flip per state, session-only persistence (no `repo.set_setting` call for compact mode).

**Out of scope:**
- OS-level fullscreen (`showFullScreen()`, hiding title bar / GNOME taskbar). The phase title says "fullscreen mode" but the goal is internal layout, not window-decoration removal. Title bar, menu bar, hamburger button all stay visible in compact mode.
- Hiding the menu bar or hamburger button alongside the left column. Only the StationListPanel is hidden.
- Persisting compact-mode state across app restarts (deliberate — see In Scope rationale).
- Per-display-geometry compact-mode memory (e.g., remembering which window size triggered compact). Manual toggle only.
- Auto-detecting small displays and prompting / auto-enabling compact mode. No display-resolution sniffing.
- Auto-exit when the window is widened past a threshold. No window-width watchers. (User Q on Scope: chose "Stay compact" over "Auto-exit on wide window" and "Auto-suggest only".)
- Hamburger menu entry for the toggle. (User Q on Activation: "Shortcut plus button on the now playing pane" — explicit no-hamburger.)
- A persistent edge-handle button on the left edge as an alternate reveal affordance. Hover-peek is the only secondary reveal mechanism. (User Q on Reveal: chose "Hover-to-peek on left edge" over "Edge-handle button on left edge".)
- Splitter reflow during peek (i.e., temporarily restoring the splitter to show the station list, then re-collapsing on mouse-leave). Overlay-floats-over is the chosen pattern. (User Q on Peek style: "Overlay (floats over)" over "Reflow (splitter restores)".)
- Esc key, click-outside, or click-station auto-dismiss for the peek overlay. ONLY mouse-leave-overlay closes it. (User Q on Dismiss: only "Mouse leaves the overlay" was selected.)
- Touch-friendly mode adjustments. The deployment is Wayland desktop with mouse; no touch-input considerations.
- X11 codepaths. Deployment target is Linux Wayland (GNOME Shell) at DPR=1.0; the ROADMAP line referencing "X11 DPR=1.0" is stale and will not be honored. See Canonical refs / memory note.

</domain>

<decisions>
## Implementation Decisions

### Activation surface

- **D-01:** **Keyboard shortcut Ctrl+B + button on the now-playing pane.** No hamburger menu entry. Ctrl+B matches Chrome/Firefox/VS Code's sidebar-toggle convention; the button is always reachable because the now-playing pane is the pane that NEVER hides. (User Q: explicit "Shortcut plus button on the now playing pane".)
- **D-02:** **Shortcut key = Ctrl+B.** Picked over F11 (which conventionally means OS-fullscreen and would be misleading here since the phase is internal-layout compact, not OS-fullscreen) and Ctrl+L (would conflict with a future location-bar / library-focus shortcut). (User Q: "Ctrl+B".)
- **D-03:** **First keyboard shortcut in the app.** No `QShortcut` / `setShortcut` / `QKeySequence` calls exist anywhere in `musicstreamer/ui_qt/`. This phase establishes the shortcut-registration pattern for future phases.
- **D-04:** **Button location = far right of now-playing control row, after StreamPicker.** Existing control row order: Edit, Star, Pause, Stop, StreamPicker. Compact-toggle button joins as the rightmost element. (User Q: "far right".)
- **D-05:** **Icon flips per state.** Two distinct glyphs — "sidebar-open" (left column visible — default state) vs. "sidebar-closed" (compact — left column hidden). Self-documents the next action. Tooltip should match ("Hide stations list (Ctrl+B)" vs. "Show stations list (Ctrl+B)"). (User Q: "Icon flips (Recommended)".)

### Scope of compact mode

- **D-06:** **Hide ONLY the left column (`StationListPanel`).** Menu bar, hamburger button, title bar, window decorations all stay visible. No `showFullScreen()`. The "fullscreen" in the phase name is a misnomer for "wider playback pane"; the actual problem is bottom-bar control overlap on narrow window widths, which hiding the left column resolves. (User Q: "Just the left column (Recommended)".)
- **D-07:** **Manual toggle only — no auto-exit on resize.** If the window is resized wider while compact mode is on, the right pane just gets wider. No threshold-based auto-toggle, no toast suggestion. The user explicitly framed the workflow as "flip in and out as I move the device between screens" — manual is the mental model. (User Q: "Stay compact (Recommended)".)
- **D-08:** **Splitter children remain `setChildrenCollapsible(False)` for normal drag.** Compact mode does NOT collapse the splitter; it hides the entire left child widget with `self.station_panel.hide()` plus hiding the splitter handle. This keeps the existing drag-to-collapse-prevention contract intact for the expanded mode.

### State persistence

- **D-09:** **Session-only — no SQLite persistence of compact-mode state.** Every app launch starts in expanded (non-compact) mode regardless of how the previous session ended. This is a DELIBERATE DIVERGENCE from the precedent set by Phase 47.1 (Stats for Nerds) and Phase 67 (Show similar stations), both of which persist via `repo.set_setting`. Rationale: the user physically moves the laptop between a big primary display (where compact is wrong) and a small secondary display (where compact is right); persisting would make wake-up on the big screen surprising. (User Q: "Session only".)
- **D-10:** **In-memory snapshot of splitter sizes for restore.** When entering compact mode, capture `self._splitter.sizes()` to an instance variable (e.g., `self._splitter_sizes_before_compact: list[int] | None`). When exiting compact, apply that snapshot back via `self._splitter.setSizes(...)`. Snapshot does NOT cross process boundaries — fresh launches start with the default `[360, 840]`. (User Q: "Restore previous live sizes (Recommended)".)

### Reveal mechanism (hover-to-peek)

- **D-11:** **Hover-to-peek on the left edge.** A secondary reveal that lets the user see the station list briefly without exiting compact mode. Triggered by mouse hover on the left edge; closes on mouse-leave. (User Q: "Hover-to-peek on left edge" over "No peek" and "Edge-handle button".)
- **D-12:** **Overlay floats over now-playing pane (NOT splitter reflow).** Peek panel is positioned absolutely on top of the now-playing pane content. The QSplitter and the right pane do NOT reflow during peek; the right pane's layout stays stable. Brief obscuration of the left edge of the now-playing pane during peek is acceptable. (User Q: "Overlay (floats over) (Recommended)".)
- **D-13:** **Trigger zone = left 4-6px of window + ~250-300ms dwell.** Narrow band prevents accidental triggers when dragging the cursor across the window; brief dwell timer matches standard tooltip-style timing. Implementation: window-level mouse-move event filter watching for cursor x ≤ ~6px, start a `QTimer.singleShot(280ms, ...)` to open the overlay if cursor still in the zone when timer fires. (User Q: "Narrow band + brief dwell (Recommended)".)
- **D-14:** **Dismiss = mouse-leaves-the-overlay ONLY.** Esc does NOT dismiss. Click outside the overlay does NOT dismiss. Clicking a station in the peeked overlay does NOT auto-dismiss (the user can browse and click multiple stations without re-triggering). The overlay closes when the cursor crosses out of the overlay's bounding rect (onto the now-playing pane area or out of the window). (User Q: multiSelect, only "Mouse leaves the overlay" selected.)
- **D-15:** **Peek overlay is fully interactive.** Click-to-play, right-click-edit, star toggle, search box, filter chips, scroll all work identically to the docked StationListPanel. The peek surface is the same panel rendered in an overlay-style container, not a stripped-down preview. Implementation choice (single instance hoisted between docked/overlay parents vs. two parallel instances driven by the same model) is left to the planner.

### Claude's Discretion

- **Icon selection** for the compact-toggle button. Two glyphs needed. Candidates: Qt's `QStyle::SP_TitleBarShadeButton` / `SP_TitleBarUnshadeButton` (built-in), custom SVGs in `musicstreamer/ui_qt/icons/`, or icon-font glyphs. Planner picks; visual consistency with existing toolbar icons is the priority.
- **Exact dwell timing** for the hover-peek trigger. CONTEXT specifies ~250-300ms; planner can finalize a single value based on UI-feel testing.
- **Exact hover-trigger-zone width** within the 4-6px band specified. Planner picks the single integer (likely 4 or 6 — round numbers).
- **Slide animation** for the peek overlay entrance/exit. Planner picks: instant show/hide, `QPropertyAnimation` on x-offset, or `QGraphicsOpacityEffect` fade. Standard pattern is a 150-200ms x-offset slide; fine to ship without animation if it complicates the overlay-z-order test.
- **Overlay width** when peeked. Reasonable defaults: same as the docked splitter size before compact (`self._splitter_sizes_before_compact[0]`), the splitter default 360px, or a fixed peek-overlay width (e.g., 360px). Planner picks; using the in-memory snapshot is most respectful of user preference.
- **Overlay z-order vs. toasts.** Existing `ToastOverlay` (`main_window.py:293`) is parented to centralWidget, anchored bottom-centre. The peek overlay should NOT be obscured by toasts (or vice versa) in a way that creates an interaction trap. Planner verifies z-order; expectation is toasts float on top.
- **Implementation choice for the peek overlay's StationListPanel content.** Two viable patterns:
  1. **Hoist the existing `self.station_panel` between the splitter (docked) and a `QFrame` overlay (peeking) by reparenting.** Single instance, preserves filter/search/scroll state across modes for free.
  2. **Construct a second `StationListPanel` instance backed by the same model and proxy.** Cleaner separation but doubles memory and requires syncing filter/search state.
  Recommendation: pattern 1 (reparenting). Planner confirms feasibility against StationListPanel's parent-assumption surface area.
- **Splitter handle visibility** during compact mode. Default: hide the handle alongside the left widget. Planner verifies the visual result with the right pane expanded full-width.
- **Whether to register Ctrl+B as a window-scope or app-scope shortcut.** `QShortcut(seq, MainWindow)` with `Qt.WidgetWithChildrenShortcut` (window-scope — only fires when MainWindow has focus) vs. `Qt.ApplicationShortcut` (fires app-wide including over dialogs). Default: window-scope; dialogs shouldn't be eaten by Ctrl+B.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase inputs
- `.planning/ROADMAP.md` — Phase 72 entry. **Note correction:** ROADMAP line states "Verify on the user's small-screen device and on the X11 DPR=1.0 deployment target." The X11 reference is stale; actual deployment is Linux Wayland (GNOME Shell) at DPR=1.0. See memory `project_deployment_target.md`. Do not add X11-specific codepaths.
- `.planning/PROJECT.md` — current state (Phase 71 complete; milestone v2.1 rolling polish). The 'Current State (Phase 69 complete)' section's panel layout description ("Now-playing: Three-column panel — logo | name+icy+controls | cover art") confirms the panel-internal structure the compact-mode button is added to.
- `.planning/REQUIREMENTS.md` — v2.1 requirements table. Phase 72 is rolling-milestone; planner may propose a new requirement code (e.g., `UX-NN` or `LAYOUT-NN`) if useful, otherwise the ROADMAP phase title serves as the active requirement entry.

### Code paths the phase extends
- `musicstreamer/ui_qt/main_window.py` lines 169-261 — hamburger menu construction pattern. **Phase 72 does NOT add a hamburger entry** (D-01) but the file remains the registration site for the Ctrl+B `QShortcut` and the central toggle slot the now-playing button calls.
- `musicstreamer/ui_qt/main_window.py` lines 270-287 — `_splitter` construction. `QSplitter(Qt.Horizontal, self)` with `setChildrenCollapsible(False)`, `station_panel.setMinimumWidth(280)`, `now_playing.setMinimumWidth(560)`, `_splitter.setSizes([360, 840])`. The compact toggle hides `self.station_panel` and the splitter handle; on exit it restores via the in-memory snapshot.
- `musicstreamer/ui_qt/main_window.py` line 310 — `self.setMinimumWidth(560)` on the MainWindow itself. With the left panel hidden, the window can shrink to 560px without forcing widget overflow (this is the size at which the bottom-bar overlap bug currently manifests).
- `musicstreamer/ui_qt/now_playing_panel.py` — control row construction. Existing pattern: badges + controls assembled into HBox layouts. The compact-toggle `QToolButton` is appended after the StreamPicker (the current rightmost control). New signal `compact_mode_toggled = Signal(bool)` (or analogous) on NowPlayingPanel that MainWindow connects to a central toggle slot. Reference signal-up-to-MainWindow patterns: `track_starred`, `stopped_by_user`, `edit_requested` (main_window.py:331-340).
- `musicstreamer/ui_qt/station_list_panel.py` — the panel that gets hidden in compact mode. No code changes inside this file are expected; it just becomes `.hide()`-able. For the peek overlay, planner decides between reparenting the existing instance (recommended) and instantiating a second one — either way, the existing panel's external API surface should not need to change.

### Established patterns referenced
- **Hamburger checkable toggle pattern** (NOT followed for this phase, but cited for awareness): `main_window.py:222-228` (`_act_stats` — Phase 47.1) and `main_window.py:203-208` (`_act_show_similar` — Phase 67). Both use `setCheckable(True)` + `setChecked(repo.get_setting(...))` + `toggled.connect(...)`. Phase 72 explicitly diverges by (a) skipping the hamburger entry and (b) skipping the SQLite persistence half of the pattern.
- **Settings persistence via repo** (NOT used for this phase, cited for contrast): `self._repo.get_setting("key", "default")` / `self._repo.set_setting("key", "value")`. Compact mode is session-only (D-09), so no repo write.
- **Panel signal up to MainWindow** for cross-panel coordination: `main_window.py:331-340` shows the established pattern (`track_starred`, `stopped_by_user`, `edit_requested`). The new compact-mode signal from NowPlayingPanel follows the same shape.
- **Overlay anchored to centralWidget**: `main_window.py:293` shows `ToastOverlay(self)` anchored to centralWidget. The peek overlay should parent to the same centralWidget for consistent z-order behavior; verify it doesn't conflict with toast positioning (bottom-centre).

### Prior phase precedents (toggle-pattern reference)
- `.planning/phases/47-stream-quality-by-codec-rank/47-01-PLAN.md` — Phase 47.1 (Stats for Nerds toggle). WR-02 single-source-of-truth invariant (the QAction's checked state drives panel visibility; the panel does not read the setting independently). Compact mode mirrors this invariant: the toggle state (held in MainWindow or NowPlayingPanel) drives StationListPanel visibility; the panel does not self-toggle.
- `.planning/phases/67-show-similar-stations-below-now-playing-for-switching-from-s/67-CONTEXT.md` — Phase 67 (Show similar stations toggle). M-01 / M-02 pattern: drive container visibility from the QAction's initial checked state. Compact mode follows the same single-source-of-truth principle.

### Deployment target (memory-sourced)
- Memory `project_deployment_target.md` — Linux Wayland (GNOME Shell) at DPR=1.0. No X11. No HiDPI rig. Defensive HiDPI one-liners are fine; HiDPI-only manual verification does not gate phase completion.

### Routing skill (auto-loaded contextually; not directly load-bearing for this phase)
- `.claude/skills/spike-findings-musicstreamer/SKILL.md` — referenced by `CLAUDE.md` routing for Windows-packaging / GStreamer / PyInstaller work. Not load-bearing for a pure UI-layout phase.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `self._splitter` (`main_window.py:272`) — `QSplitter(Qt.Horizontal, self)` already exists; compact mode operates on it directly via `station_panel.hide()` / `.show()` and `_splitter.setSizes(...)`. No new container widget needed.
- `self.station_panel.setMinimumWidth(280)` and `self.now_playing.setMinimumWidth(560)` — Qt size policies; with `station_panel.hide()`, only the 560px right-pane minimum applies, so the main window can comfortably reach its `setMinimumWidth(560)` floor (`main_window.py:310`).
- `self._splitter.setChildrenCollapsible(False)` — kept as-is for the expanded mode. Compact mode bypasses the collapsibility contract by hiding the entire widget rather than dragging it to zero width.
- `ToastOverlay` pattern (`main_window.py:293`) — overlay-on-centralWidget precedent for the peek overlay's parent + z-order setup. Centralizes overlay management.
- `now_playing_panel.py` control row — established pattern for adding buttons next to existing controls (Edit, Star, Pause, Stop, StreamPicker exist; compact-toggle becomes the 6th button at the far right).
- `NowPlayingPanel` outbound signals — `track_starred`, `stopped_by_user`, `edit_requested`, `sibling_activated`, `similar_activated`, `gbs_vote_error_toast`, `live_status_toast`, `live_map_changed`, `compact_mode_toggled` (NEW). Follow the bound-method-connect convention (QA-05) — no lambdas.
- `StationListPanel` (`musicstreamer/ui_qt/station_list_panel.py`) — the entire panel being hidden/peeked. Public methods used by the rest of the app: `station_activated`, `edit_requested`, `new_station_requested`, `station_favorited`, `update_live_map(...)`. None of these need to change for compact mode; the panel just stops rendering when hidden.

### Established Patterns

- **`QSplitter` as `centralWidget` with two children**: Set in Phase 36's PySide6 revamp. Compact mode doesn't restructure the splitter — it just toggles the left child's visibility. No new layout container.
- **Settings persistence via `Repo.get_setting` / `Repo.set_setting`**: Used by every toggleable preference in the app. Phase 72 DELIBERATELY DOES NOT FOLLOW this pattern (D-09) — session-only is the explicit choice. Test harness must assert that NO `set_setting` call happens for the compact-mode key.
- **Hamburger menu checkable toggle (Phase 47.1 / Phase 67)**: NOT followed here. The button-on-now-playing-pane pattern is novel to this phase and may become a precedent for future "show/hide" toggles that target panels the right pane survives.
- **Bound-method slot connects, no lambdas (QA-05)**: All signal connections in `main_window.py` use bound methods. The new `compact_mode_toggled` slot follows this convention.
- **Single-source-of-truth panel visibility (Phase 47.1 WR-02, Phase 67 M-02)**: The toggle state (held centrally) drives panel visibility; the panel does NOT read the toggle state itself. Compact mode mirrors this — `StationListPanel.hide()` is called from MainWindow when the toggle flips.
- **`QueuedConnection` for cross-thread signals**: Used liberally in `main_window.py` for player→UI signals. The compact-mode toggle is main-thread-only (button click → signal → MainWindow slot), so `Qt.AutoConnection` (default) is fine. No queued connection needed.

### Integration Points

- **MainWindow constructor:** Add `QShortcut(QKeySequence("Ctrl+B"), self, member=self._on_compact_toggle, context=Qt.WidgetWithChildrenShortcut)` (planner picks exact signature). Add `self._splitter_sizes_before_compact: list[int] | None = None` as an instance variable. Add `self._is_compact: bool = False` (or read from the button's checked state — single source of truth).
- **NowPlayingPanel constructor:** Add compact-toggle `QToolButton` to the control row layout. Wire its `toggled` signal to a new `compact_mode_toggled = Signal(bool)`. MainWindow connects this signal to `self._on_compact_toggle`.
- **MainWindow `_on_compact_toggle(checked: bool)` slot:**
  ```python
  if checked:
      self._splitter_sizes_before_compact = self._splitter.sizes()
      self.station_panel.hide()
      self._splitter.handle(1).hide()  # or splitter handle index
  else:
      self.station_panel.show()
      self._splitter.handle(1).show()
      if self._splitter_sizes_before_compact:
          self._splitter.setSizes(self._splitter_sizes_before_compact)
  ```
  Planner finalizes the splitter-handle index call (Qt's `QSplitter.handle(int)` returns the handle widget; index 1 is the divider between widgets 0 and 1).
- **Ctrl+B shortcut wiring:** Calls the same `_on_compact_toggle` slot (or toggles the now-playing button's checked state, which fan-outs through the signal). The button's checked state is the single source of truth.
- **Peek overlay:** New widget class (e.g., `StationListPeekOverlay`) parented to `centralWidget`. Owns either a reparented `self.station_panel` instance or a new instance. Mouse-tracking event filter installed on MainWindow (or centralWidget) to detect left-edge hover. `QTimer.singleShot(280, ...)` for dwell. On overlay shown, install another event filter to detect mouse-leave-overlay-bounds.
- **Test surface:** Existing `tests/test_main_window.py` (or wherever main-window QSplitter tests live) gets new test cases for compact-mode toggle, splitter-size round-trip, button-and-shortcut parity, peek-overlay lifecycle, session-only persistence.

</code_context>

<specifics>
## Specific Ideas

- **Use case anchor:** "moving the device between screens" — laptop physically moves between a big primary display (compact OFF works fine, full station list visible) and a small secondary display (compact ON needed because bottom-bar controls overlap at narrow window widths). The user wants to flip in/out manually as the physical move happens.
- **Bottom-bar overlap is the actual bug:** when the main window shrinks toward its 560px `setMinimumWidth`, both panels share that width below their stated minimums (280+560=840 total), the now-playing pane's bottom controls compress horizontally and overlap. Hiding the left column gives the right pane the full 560px+, which is its designed minimum.
- **Reference shortcut:** "Ctrl+B" matches the sidebar-toggle convention from Chrome, Firefox, VS Code, and most file managers. The user picked this directly. F11 was rejected as misleading (it conventionally means OS-fullscreen).
- **Peek timing:** ~250-300ms dwell on the left 4-6px edge is "standard tooltip-style timing." The user picked the narrow-band + brief-dwell option specifically to avoid accidental triggers.
- **Peek interaction expectation:** Clicking a station in the peek overlay does NOT close the overlay. Implication: user can scan stations, click one (it starts playing), then click another, all while peeked. The mouse must leave the overlay for it to close. This is a deliberate "browse-while-peeked" choice.
- **First keyboard shortcut in the codebase:** No `QShortcut`, `setShortcut`, or `QKeySequence` references exist in `musicstreamer/ui_qt/` today. Phase 72 establishes the pattern. Future phases adding shortcuts can follow this precedent.
- **Deployment correction:** ROADMAP line for Phase 72 says "X11 DPR=1.0" — this is stale (memory confirms Wayland-only, never X11). Downstream agents should silently ignore the X11 reference and target Wayland exclusively. No X11-fallback codepaths.

</specifics>

<deferred>
## Deferred Ideas

- **OS-level fullscreen toggle (`showFullScreen()`).** Different feature: hides title bar, GNOME taskbar, gives true edge-to-edge. Could be a separate phase if the user ever wants kiosk-style display. Not raised this discussion; out of scope here.
- **Hamburger menu entry for the compact toggle.** User explicitly chose "no hamburger entry." Could be added later if discoverability becomes an issue, but the button-on-now-playing-pane + Ctrl+B was deemed sufficient.
- **Persisted compact-mode state across restarts.** User explicitly chose session-only. If the user later wants persistence (e.g., they discover they're always on the small screen for a stretch and want the app to remember), trivial future polish — flip from `self._is_compact` in-memory to `repo.get_setting/set_setting`. Test harness already asserts no setting write today; would need to relax.
- **Per-display-geometry compact memory.** "If window width is < X on launch, restore compact." User declined as over-engineered. Could become useful if the user adds more displays or wants compact to "just work."
- **Auto-exit compact when window is widened past a threshold.** User declined ("Stay compact"). If the workflow ever shifts to "compact is sticky and I always forget to exit," revisit.
- **Auto-suggest toast** when window goes narrow ("Window is small — hide stations?"). User declined as noisy. Could be reconsidered if compact-mode discoverability turns out to be a problem.
- **Hide menu bar in compact mode.** User chose "Just the left column." If desk-real-estate becomes precious on the secondary display, a future phase could collapse the hamburger button into a compact icon-only form or hide the menu bar entirely.
- **Edge-handle button on the left edge** as an alternate reveal affordance (always-visible thin vertical strip with an expand chevron). User chose hover-peek instead. If hover-peek discoverability is poor in practice, the edge-handle could be added as a third surface.
- **Esc / click-outside / click-station dismiss for the peek overlay.** User explicitly restricted dismissal to mouse-leave-overlay only. If the peek-while-browsing flow turns out to feel "sticky" in practice, Esc or click-outside could be added as additional escapes.
- **Splitter-reflow peek (alternative to overlay)** — restoring the splitter sizes temporarily during peek so the now-playing pane shrinks to make room. User chose overlay. If the overlay's obscured-content issue turns out to bother the user in practice (the cover art / left edge of controls disappear during peek), reflow could be revisited.
- **Slide / fade animation for the peek overlay.** Planner-discretion in this phase; could become its own micro-polish phase if the instant show/hide feels jarring.
- **Touch-friendly compact mode** (larger hit targets, swipe-to-peek). Not on the roadmap. Deployment is desktop with mouse; would be a separate touch-input phase if a touchscreen device enters scope.
- **Wider keyboard-shortcut framework.** Phase 72 introduces the first `QShortcut`. A future polish phase could add a shortcuts dialog, configurable shortcuts, or a uniform shortcut-registration helper if shortcuts proliferate.

</deferred>

---

*Phase: 72-fullscreen-mode-hide-left-column-for-compact-displays*
*Context gathered: 2026-05-13*
