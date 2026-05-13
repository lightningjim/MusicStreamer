---
phase: 72
plan: 05
task: 3
type: manual-uat
deployment: linux-wayland-gnome-shell-dpr1.0
created: 2026-05-13
status: PENDING
---

# Phase 72 — Manual UAT Script

> Five manual verifications mapped to `72-VALIDATION.md §Manual-Only Verifications`.
> Each item covers behavior that automated tests in Plans 02–05 cannot reach
> (visual judgment, subjective UX timing, real-device geometry, Wayland-shell
> behavior).
>
> **Deployment target:** Linux Wayland (GNOME Shell) at DPR=1.0. The app
> targets Wayland exclusively (project memory: `project_deployment_target.md`).
> Confirm `$XDG_SESSION_TYPE == wayland` before starting (UAT-05 below).

---

## How to run

1. From a Wayland session (GNOME Shell on Linux), open a terminal.
2. Confirm session type:
   ```bash
   echo "$XDG_SESSION_TYPE"   # must print: wayland
   ```
3. Launch the app from the project root. Either form works:
   ```bash
   python -m musicstreamer
   # or, if the project is installed via `pip install -e .`:
   musicstreamer
   ```
4. The MusicStreamer main window appears at its default size with the station
   list visible on the left and the now-playing pane on the right. The new
   compact-toggle button is the rightmost control in the now-playing control
   row (immediately right of the volume slider). Hover the button to confirm
   the tooltip reads `Hide stations (Ctrl+B)`.
5. Work through UAT-01 through UAT-05 in order. Tick the `[ ]` checkbox next
   to each Pass criteria as you confirm it. Leave notes in the
   "Notes / observations" section if anything feels off (timing, animation
   desire, visual quirk) — those go into Phase 72 deferred polish if you
   want them.
6. At the very bottom of this file, change the `**Overall:** PENDING` line to
   `**Overall:** PASS` (all five items passed) or `**Overall:** FAIL` (one or
   more items failed — note which ones in "Failure notes" so a Phase 72.1
   gap-closure plan can be scoped).

The orchestrator's checkpoint gate greps for the literal text
`**Overall:** PASS` at the bottom of this file. Leaving it as PENDING keeps
the gate closed; setting it to PASS releases the phase to its summary step.

---

## UAT-01: Icon flip visual correctness

**Maps to:** VALIDATION.md §Manual-Only Verifications row 1 + UI-SPEC §Interaction Contract §Compact-toggle button visual states
**Requirement covered:** D-05 (icon flips per state)

### Steps

1. Launch the app per "How to run" above.
2. Note the initial icon on the compact-toggle button (rightmost button in
   the now-playing control row). Hover the button — confirm tooltip reads
   `Hide stations (Ctrl+B)`.
3. Press `Ctrl+B`.
4. Observe the icon on the same button after the toggle. The glyph should
   visibly differ from step 2. Hover — confirm tooltip now reads
   `Show stations (Ctrl+B)`.
5. Press `Ctrl+B` again. Icon flips back; tooltip returns to
   `Hide stations (Ctrl+B)`.

### Expected

- Two distinct icon glyphs swap on every toggle. Both should be
  recognizable as "sidebar control" affordances — `sidebar-hide-symbolic`
  (panel + left chevron, "about to hide") when expanded, and
  `sidebar-show-symbolic` (panel + right chevron, "about to show") when
  compact.
- Tooltip text changes in lockstep with the icon and clearly communicates
  the next action (verb-first, sentence-case, with the keyboard shortcut
  in parens).
- The Qt-rendered "pressed" / "checked" appearance is also visible when
  the button is in the compact (checked) state (palette-driven highlight
  background per UI-SPEC §Color).

### Pass criteria

[ ] Both the icon AND the tooltip clearly communicate the next action; a
    first-time user could read them and predict what `Ctrl+B` will do.

### Notes / observations

(leave blank for user)

---

## UAT-02: Hover-peek feel and timing

**Maps to:** VALIDATION.md §Manual-Only Verifications row 2 + UI-SPEC §Interaction Contract §Hover-peek interaction contract
**Requirement covered:** D-13 (trigger zone = left ≤ 4px + 280ms dwell)

### Steps

1. Launch the app and enter compact mode (`Ctrl+B`). Station list disappears;
   the now-playing pane expands to fill the freed width.
2. Slowly move the cursor to the LEFT edge of the window — touch the very
   leftmost few pixels (the 4-pixel trigger zone). KEEP THE CURSOR THERE
   without moving it.
3. After a short, deliberate dwell (~280 ms), the station-list peek
   overlay slides in from the left.
4. Move the cursor RIGHT, away from the left edge but staying inside the
   peek overlay's bounds — the overlay stays open.
5. Move the cursor further right, OUT of the peek overlay's bounds (onto
   the now-playing pane area). The peek closes automatically.
6. Now do the opposite of step 2: drag the cursor RAPIDLY across the
   window starting from the left edge — DO NOT dwell on the left edge.
   The peek must NOT open during this rapid pass-through (the dwell timer
   must have cancelled on the cursor leaving the trigger zone).

### Expected

- 280 ms dwell + 4 px zone feels "natural" — long enough to avoid
  accidental triggers when dragging the cursor across the window, short
  enough that a deliberate hover doesn't feel laggy.
- The peek opens INSTANTLY (no animation) — UI-SPEC explicitly chose
  instant show/hide over a slide animation.
- Closing on mouse-leave-overlay also happens instantly.
- Rapid cursor traversal across the window (without dwell) does NOT open
  the peek.

### Pass criteria

[ ] 280 ms dwell feels natural (neither laggy nor twitchy), AND a fast
    cursor traversal across the left edge does NOT trigger the peek.

### Notes / observations

(leave blank for user — if the dwell feels too long or too short, note the
preferred ms value so it can be adjusted in deferred polish)

---

## UAT-03: Overlay z-order vs ToastOverlay

**Maps to:** VALIDATION.md §Manual-Only Verifications row 3 + UI-SPEC §Z-order contract
**Requirement covered:** D-12 (peek floats over now-playing; toasts above peek)

### Steps

1. Launch the app and enter compact mode (`Ctrl+B`).
2. Open the peek overlay (hover the left edge, dwell 280 ms).
3. While the peek is visible, trigger a toast. Easiest ways:
   - Star the currently-playing track (Star button in the now-playing
     pane) — toast: `Saved to favorites`.
   - OR right-click a station inside the peek overlay → Edit → Save
     without changes — usually emits a confirmation toast.
   - OR stop playback while a stream is connecting — toast: `Stream
     stopped` / `Could not connect`.
4. Observe the visual stacking: the toast bubble should render ABOVE the
   peek overlay (toast > peek > now-playing), not behind it.
5. Confirm there is no interaction trap: the toast does not block clicks
   inside the peek, and the peek does not hide the toast in a way that
   prevents reading it.

### Expected

- Z-order (front → back): ToastOverlay → StationListPeekOverlay →
  NowPlayingPanel → StationListPanel (docked).
- Toasts auto-dismiss on their own timer; clicks fall through to whichever
  layer makes sense (toasts are read-only chrome, peek panel is
  interactive).

### Pass criteria

[ ] Toast bubbles appear ABOVE the peek overlay; no interaction trap —
    user can both read the toast and continue interacting with the peek.

### Notes / observations

(leave blank for user)

---

## UAT-04: Bottom-bar overlap fix on small/secondary display

**Maps to:** VALIDATION.md §Manual-Only Verifications row 4 + CONTEXT §domain (bottom-bar overlap is the actual bug)
**Requirement covered:** LAYOUT-01 (phase root-cause goal)

### Steps

1. Launch the app.
2. Drag the window onto the SMALL / SECONDARY display (the physical
   reason this phase exists). The display does not have to be a "second
   monitor" — any narrow window context works; the bug only manifests
   when the window is shrunk near its 560 px floor.
3. Resize the window narrow — roughly 560–700 px wide. The bottom bar
   of the now-playing pane (transport controls, stream picker, volume
   slider, etc.) should compress and start to overlap (this reproduces
   the bug Phase 72 was scoped to fix).
4. Press `Ctrl+B` (or click the compact-toggle button on the now-playing
   pane) to enter compact mode.
5. With the station list hidden, the now-playing pane now claims the full
   window width. The bottom-bar controls should fit cleanly with no
   overlap. Try clicking each control — all should be fully reachable.

### Expected

- At ~560–700 px window width with compact mode OFF: bottom-bar controls
  visibly overlap or get clipped (the reproducible bug).
- At the same window width with compact mode ON: controls have room and
  are all fully clickable.
- The window's 560 px minimum width holds (the splitter does not collapse
  the now-playing pane below its design minimum).

### Pass criteria

[ ] Compact mode resolves the bottom-bar overlap at narrow widths on the
    small/secondary display. All transport controls are fully clickable
    in compact mode at ~560 px width.

### Notes / observations

(leave blank for user — if any control is still partially clipped at
560 px even in compact mode, note which one)

---

## UAT-05: Wayland GNOME Shell behavior

**Maps to:** VALIDATION.md §Manual-Only Verifications row 5 + CONTEXT §domain (deployment target)
**Requirement covered:** D-06, D-09, D-11, D-12, D-13, D-14 (full lifecycle under the real shell)

### Steps

1. Open a terminal and confirm:
   ```bash
   echo "$XDG_SESSION_TYPE"
   ```
   The output MUST be `wayland`. If it prints anything else, STOP and
   switch to a Wayland session before proceeding (the deployment target
   is Wayland; see project memory note `project_deployment_target.md`).
2. Launch the app: `python -m musicstreamer` (or `musicstreamer` if
   pip-installed).
3. Exercise the full lifecycle in one continuous session:
   - Toggle compact ON via Ctrl+B. Confirm the station list disappears
     and the splitter handle is no longer visible.
   - Hover the left edge, dwell ~280 ms. Confirm the peek overlay slides
     in instantly with the full station list, search box, and filter
     chips functional.
   - Click a station inside the peek overlay. Confirm playback starts and
     the peek STAYS open (D-14 — click-station does not auto-dismiss).
   - Move the cursor out of the peek overlay (rightward, into the
     now-playing pane area). Confirm the peek closes instantly.
   - Toggle compact OFF via Ctrl+B. Confirm the station list returns to
     its previous splitter width (the value you had before entering
     compact — not the default 360 px, unless you never resized the
     splitter).
4. During step 3, watch for any Wayland-specific visual or input glitch:
   - Compositor flicker on overlay open/close.
   - GNOME Shell freeze (cursor not responsive for >1 s).
   - Window decoration anomaly (title bar disappearing, drag-to-move
     failing).
   - DPR=1.0 anomaly (icons/text rendering at half-scale or 2× scale).
   - Cursor-position lag (peek opens at the wrong x-coordinate).

### Expected

- Behavior under Wayland matches the expected behavior listed in
  UAT-01 through UAT-04 (Wayland is the deployment target — UAT-05 is
  the confirmation that everything observed in UAT-01 through UAT-04
  also holds under the real shell).
- No compositor-level glitch. No DPR-related rendering bug. The 280 ms
  dwell timer fires reliably (Wayland's input routing is event-driven
  and `QTimer` is backend-agnostic, so dwell behavior should be
  indistinguishable from the offscreen automated tests).
- Quit the app cleanly (Ctrl+Q or window-close button). Confirm
  GStreamer pipeline shuts down without leaving an orphan process
  (check `ps aux | grep musicstreamer` after exit returns nothing).

### Pass criteria

[ ] Full lifecycle completes under Wayland GNOME Shell at DPR=1.0
    without any Wayland-specific glitch. App quits cleanly with no
    orphan process.

### Notes / observations

(leave blank for user)

---

## Failure notes

(If any UAT-01 through UAT-05 item failed, note which one and why here. A
follow-up Phase 72.1 gap-closure plan will be scoped to fix the specific
failure(s). Leave blank if all passed.)

---

## Overall

**Overall:** PENDING
