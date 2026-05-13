# Phase 72: Fullscreen mode — hide left column for compact displays - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-13
**Phase:** 72-fullscreen-mode-hide-left-column-for-compact-displays
**Areas discussed:** Activation surface, Scope of 'fullscreen', State persistence, Reveal mechanism

---

## Gray-area selection

| Option | Description | Selected |
|--------|-------------|----------|
| Activation surface | Hamburger menu + keyboard shortcut + (optional) toolbar button? Which shortcut key? | ✓ |
| Scope of 'fullscreen' | Just hide left column, or also OS-fullscreen / hide menu bar? | ✓ |
| State persistence | Remember across restarts (Stats/Similar precedent) or session-only? | ✓ |
| Reveal mechanism | Toggle only, hover-to-peek, or edge-handle button? | ✓ |

**User's choice:** All four areas selected.

---

## Activation surface

### Q1: How should the user toggle compact mode?

| Option | Description | Selected |
|--------|-------------|----------|
| Menu + shortcut (Recommended) | Checkable hamburger entry + keyboard shortcut. Discoverability + speed. | |
| Keyboard shortcut only | No menu entry — just a shortcut. | |
| Menu entry only | Matches every other toggle (no shortcut precedent). | |
| Other (free text) | — | ✓ |

**User's choice:** "Shortcut plus button on the now playing pane" — explicit no-hamburger; toggle button on the persistent right pane instead.

**Notes:** Skips the hamburger menu pattern that Stats/Similar followed. Reasoning is that the now-playing pane is the surface that never disappears in compact mode, so a button there is always reachable. Establishes a new pattern for "show/hide" toggles whose target panel doesn't survive the toggle.

### Q2 (plain-text follow-up): Which keyboard shortcut?

**User's choice:** **Ctrl+B**.

**Notes:** Matches Chrome/Firefox/VS Code/file-manager convention for sidebar-toggle. Rejected F11 (conflicts with conventional OS-fullscreen meaning) and Ctrl+L (potential future address-bar/library-focus conflict). First QShortcut in the codebase — sets the pattern for future shortcuts.

### Q3 (plain-text follow-up): Button placement on the now-playing pane?

**User's choice:** **Far right** of the control row, after StreamPicker.

**Notes:** Current control row order: Edit, Star, Pause, Stop, StreamPicker. New compact-toggle becomes the 6th, rightmost.

### Q4: Should the button change appearance based on state?

| Option | Description | Selected |
|--------|-------------|----------|
| Icon flips (Recommended) | Different icon when collapsed vs. expanded — self-documents. | ✓ |
| Same icon, checked state | One icon + QToolButton checkable visual feedback. | |
| Same icon, no visual change | Column visibility itself is the only feedback. | |

**User's choice:** Icon flips.

**Notes:** Two glyphs — "sidebar-open" (default, left column visible) vs "sidebar-closed" (compact). Tooltip should match the next-action. Icon selection deferred to planner discretion.

---

## Scope of 'fullscreen'

### Q1: What does 'compact mode' actually hide?

| Option | Description | Selected |
|--------|-------------|----------|
| Just the left column (Recommended) | StationListPanel only. Menu bar / title bar / hamburger stay. | ✓ |
| Left column + OS fullscreen | + showFullScreen(); no title bar, no taskbar. | |
| Left column + hide menu bar | + collapse hamburger menu bar. | |

**User's choice:** Just the left column.

**Notes:** The "fullscreen" in the phase name is a misnomer for "wider playback pane." The actual problem is bottom-bar control overlap when the window is narrow, which hiding the left column resolves. Title bar / menu bar / hamburger all stay visible.

### Q2: Auto-behavior on window resize?

| Option | Description | Selected |
|--------|-------------|----------|
| Stay compact (Recommended) | Manual control only — toggle stays on until manually toggled off. | ✓ |
| Auto-exit on wide window | App watches window width, auto-disables compact above threshold. | |
| Auto-suggest only | Detect wide window, show a toast with quick-action. | |

**User's choice:** Stay compact.

**Notes:** "Flip in and out as I move the device between screens" — user is the authority on screen size, not the app. No threshold watchers, no toast.

---

## State persistence

### Q1: When you quit in compact mode and relaunch?

| Option | Description | Selected |
|--------|-------------|----------|
| Persist across restarts (Recommended) | Save via repo.set_setting; matches Stats/Similar. | |
| Session only | Always launch in expanded mode regardless of last state. | ✓ |
| Per-window-geometry | Restore compact when relaunching narrow, expanded when wide. | |

**User's choice:** Session only.

**Notes:** Deliberate divergence from Phase 47.1 / Phase 67 precedent. Reason: user physically moves the laptop between big primary display and small secondary display; persisting compact would make wake-up on the big screen annoying. Tests must assert no `set_setting` call for the compact-mode key.

### Q2: Splitter sizes on toggle OFF?

| Option | Description | Selected |
|--------|-------------|----------|
| Restore previous live sizes (Recommended) | Capture splitter sizes just before going compact, restore them on exit. | ✓ |
| Always restore to default [360, 840] | Snap to default 30/70; toggle doubles as 'reset layout.' | |

**User's choice:** Restore previous live sizes.

**Notes:** In-memory snapshot only (consistent with session-only persistence above). Splitter sizes are NOT written to repo settings. Fresh launches start with the default `[360, 840]`.

---

## Reveal mechanism

### Q1: Any peek-style way to see the station list without exiting compact?

| Option | Description | Selected |
|--------|-------------|----------|
| No peek — toggle only (Recommended) | Cleanest. To see stations, toggle back. | |
| Hover-to-peek on left edge | Slide-out overlay when cursor hovers left edge for ~300ms. | ✓ |
| Edge-handle button on left edge | Always-visible thin strip with expand chevron. | |

**User's choice:** Hover-to-peek on left edge.

**Notes:** Adds a slide-out drawer pattern. Less discoverable than an edge handle but more elegant; less complexity than always-visible chrome.

### Q2: Overlay style — overlay vs. reflow?

| Option | Description | Selected |
|--------|-------------|----------|
| Overlay (floats over) (Recommended) | Slides out as overlay over now-playing pane. No reflow. | ✓ |
| Reflow (splitter restores) | Hover temporarily restores the splitter; pane shrinks. | |

**User's choice:** Overlay floats over.

**Notes:** Accepts that the left edge of the now-playing pane is briefly obscured during peek (cover art / leftmost controls). Trade vs. reflow-jitter: stable right pane is preferred.

### Q3: What dismisses the peeked overlay? (multiSelect)

| Option | Description | Selected |
|--------|-------------|----------|
| Mouse leaves the overlay (Recommended) | Cursor crosses out of overlay bounds → close. | ✓ |
| Clicking a station auto-dismisses | Click-to-play also closes the overlay. | |
| Esc key dismisses | Esc closes the peek. | |
| Click outside the overlay | Clicking now-playing area closes the peek. | |

**User's choice:** Mouse leaves the overlay ONLY.

**Notes:** Deliberate "browse-while-peeked" model — user can scan stations, click one (it starts playing), click another, all while peeked. Esc and click-outside are NOT escapes; only mouse-exit closes.

### Q4: Hover-trigger sensitivity?

| Option | Description | Selected |
|--------|-------------|----------|
| Narrow band + brief dwell (Recommended) | Left 4-6px, ~250-300ms dwell. Tooltip-style. | ✓ |
| Wider band + instant | Left ~16px, instant trigger. Faster but accidental. | |
| Narrow band + instant | Left 4-6px, no dwell. Hard to hit accidentally, opens immediately. | |

**User's choice:** Narrow band + brief dwell.

**Notes:** Prevents accidental triggers when dragging cursor across the window; matches standard tooltip-style timing. Planner picks the exact integer (4 or 6) and the exact dwell ms (250-300).

---

## Claude's Discretion

Areas where the user deferred to Claude or planner-discretion was explicit:

- Exact icon glyphs for the compact-toggle button (sidebar-open / sidebar-closed variants — built-in `QStyle::SP_*` vs custom SVG vs icon-font).
- Exact dwell timer ms (within 250-300ms range).
- Exact hover-trigger-zone width (within 4-6px band).
- Slide-animation timing/style for the peek overlay (instant vs ~150-200ms x-offset slide vs fade).
- Overlay width when peeked (in-memory snapshot vs splitter default 360px vs fixed peek-width).
- Z-order vs. existing `ToastOverlay` — planner verifies no interaction trap.
- Implementation choice for peek-overlay's StationListPanel content (reparent existing instance vs construct second instance backed by same model).
- Splitter handle visibility during compact mode (default: hide alongside left widget).
- QShortcut context — window-scope (`Qt.WidgetWithChildrenShortcut`) vs app-scope (`Qt.ApplicationShortcut`). Default: window-scope.

---

## Deferred Ideas

See CONTEXT.md `<deferred>` block for the full list. Highlights:

- OS-level fullscreen (`showFullScreen()`) — separate phase if kiosk-style ever wanted.
- Hamburger menu entry for the toggle — could be added if discoverability is poor.
- Persisted compact-mode state across restarts — flip from session-only if usage pattern shifts.
- Auto-exit on window resize, auto-suggest toast — declined; revisit if compact stickiness is a problem.
- Edge-handle button as alternate reveal — declined in favor of hover-peek.
- Esc / click-outside / click-station dismiss for peek — explicitly restricted to mouse-leave.
- Splitter-reflow peek alternative.
- Slide / fade animation polish.
- Touch-friendly compact mode.
- Broader keyboard-shortcut framework (shortcuts dialog, configurable bindings).

---

## Stale ROADMAP note flagged

ROADMAP.md Phase 72 line mentions "Verify on the user's small-screen device and on the X11 DPR=1.0 deployment target." Memory `project_deployment_target.md` confirms deployment is Linux Wayland (GNOME Shell) only — never X11. Downstream agents will target Wayland exclusively; no X11-fallback codepaths. ROADMAP wording is stale but does not block planning.
