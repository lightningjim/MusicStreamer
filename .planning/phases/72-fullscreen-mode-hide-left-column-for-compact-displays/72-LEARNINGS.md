---
phase: 72
phase_name: "fullscreen-mode-hide-left-column-for-compact-displays"
project: "MusicStreamer"
generated: "2026-05-13"
counts:
  decisions: 7
  lessons: 6
  patterns: 5
  surprises: 5
missing_artifacts: []
---

# Phase 72 Learnings: fullscreen-mode-hide-left-column-for-compact-displays

## Decisions

### Toggle activation: button on the always-visible pane, no hamburger entry

Compact-mode toggle lives as a `QToolButton` on the `NowPlayingPanel` control row plus a `Ctrl+B` shortcut — explicitly NOT a hamburger menu entry like every other show/hide toggle in the app (Phase 47.1 Stats, Phase 67 Similar).

**Rationale:** The now-playing pane is the pane that NEVER hides in compact mode, so a button there is always reachable. A hamburger entry would have been less discoverable AND less efficient when the user is physically moving the device between displays. Deliberate divergence from precedent — the pattern only applies when the toggle's target pane is the one that survives.
**Source:** 72-CONTEXT.md §D-01

### Shortcut key = Ctrl+B (not F11 or Ctrl+L)

First `QShortcut` in the entire codebase.

**Rationale:** F11 conventionally means OS-fullscreen and would mislead since this is internal-layout compact (not `showFullScreen()`). Ctrl+L would conflict with future location-bar / library-focus shortcuts. Ctrl+B matches the Chrome/Firefox/VS Code sidebar-toggle convention.
**Source:** 72-CONTEXT.md §D-02

### Button location: far right of the control row at `now_playing_panel.py:514`

Insertion point is AFTER `volume_slider` (line 513) and BEFORE `controls.addStretch(1)` (line 515). CONTEXT.md's "after StreamPicker" wording was stale (pre-EQ / pre-volume layout).

**Rationale:** Far-right placement keeps the new button out of the muscle-memory zone for transport controls. PATTERNS.md authoritative correction — RESEARCH.md re-read the actual control-row order during pattern mapping.
**Source:** 72-PATTERNS.md §planner_decisions + 72-RESEARCH.md §control-row-correction

### Session-only persistence — no SQLite for compact mode (D-09 divergence)

NO `repo.set_setting("compact_mode", ...)` call. Every app launch starts expanded.

**Rationale:** User physically moves the laptop between a big primary display and a small secondary display. Persisting compact would make wake-up on the big screen surprising. Deliberate divergence from Phase 47.1 / Phase 67 precedent. Locked by 4 negative-assertion tests.
**Source:** 72-CONTEXT.md §D-09 + 72-03-SUMMARY.md

### Hover-peek trigger zone = 4px, dwell = 280ms

Module constants `_PEEK_TRIGGER_ZONE_PX = 4` and `_PEEK_DWELL_MS = 280` in `main_window.py`.

**Rationale:** CONTEXT.md specified a 4-6px band and 250-300ms band — UI-SPEC committed to 4 (narrowest accidental-trigger band) and 280 (mid-band, matches Qt tooltip cadence). Confirmed natural-feeling on live Wayland during UAT-02 post-fix.
**Source:** 72-UI-SPEC.md §Spacing + 72-CONTEXT.md §D-13

### Peek dismiss: mouse-leave-overlay ONLY (D-14)

Esc does NOT dismiss. Click-outside does NOT dismiss. Click-on-station does NOT auto-dismiss.

**Rationale:** Deliberate "browse-while-peeked" model — user can scan stations, click one (it starts playing), click another, all while peeked. Restricting dismissal to mouse-leave keeps the interaction predictable.
**Source:** 72-CONTEXT.md §D-14

### Wave 0 spike pattern: verify load-bearing Qt assumptions before production code

72-01 is a dedicated Wave 0 spike whose only purpose is to lock A1 (splitter handle auto-hide) and A2 (reparenting safety) on the actually-deployed PySide6 version before Waves 1-4 commit to those assumptions.

**Rationale:** Two RESEARCH.md hypotheses depended on Qt behaviors documented only in old forum threads (Qt 4/5 era). A 30-line spike protects 4 waves of production work from a baseless assumption. Paid off immediately — A1 was invalidated and the mitigation was wired into 72-03 before it ran.
**Source:** 72-01-PLAN.md + 72-01-SUMMARY.md

---

## Lessons

### A 2014-era Qt forum claim does NOT carry to Qt 6.11

`forum.qt.io/topic/45377` ("QSplitter disappears once child widget is hidden") was the source for assumption A1: that hiding a splitter child auto-hides the adjacent handle. The thread is from Qt 4/5 era. On PySide6 6.11.0 / Qt 6.11.0, `QSplitter.handle(1).isVisible()` remains `True` after `station_panel.hide()`. The contract does not generalize across major Qt versions.

**Context:** RESEARCH.md rated A1 as LOW risk because the mitigation (one-line `handle(1).hide()`) is trivial. Wave 0 spike empirically invalidated it. RESEARCH.md was updated post-spike to mark A1 INVALIDATED, and 72-03's `_on_compact_toggle` now contains explicit `handle(1).hide()/show()` calls.
**Source:** 72-01-SUMMARY.md + 72-RESEARCH.md §Assumptions Log A1

### `pytest-qt` synthetic events can mask receiver-identity bugs

All 16 automated peek-overlay tests passed but the feature was completely non-functional on live Wayland. Tests called `QApplication.sendEvent(centralWidget, ev)` which bypasses Qt's real dispatcher (which routes MouseMove to the widget under the cursor). The event filter's `obj is self.centralWidget()` gate happened to match in the synthetic path and never matched in real dispatch.

**Context:** UAT-02 was the only test that exercised the real Wayland event-delivery path. The 16 unit tests gave false confidence. A new regression test (`test_global_filter_fires_when_event_targets_now_playing`) now sends MouseMove to a DIFFERENT receiver to lock the bug class.
**Source:** debug session `phase-72-hover-peek-wayland.md` + 72-VERIFICATION.md

### `centralWidget()` IS the QSplitter — overlay parenting must compensate

Plan 04 originally prescribed parenting `StationListPeekOverlay` to `centralWidget()`. In practice `centralWidget()` is the `QSplitter`, which auto-manages any child `QFrame` as a third managed widget. The overlay landed at ~640px instead of the design's 360px.

**Context:** Mirrored `ToastOverlay`'s parent strategy (`MainWindow` itself), then skipped `self.raise_()` inside `adopt()` so toasts (which DO raise on show) remain above peek by default. Z-order intent preserved without breaking the layout.
**Source:** 72-04-SUMMARY.md §deviations + 72-VERIFICATION.md

### Qt creates a placeholder slot when a QSplitter child is reparented OUT

When `station_panel.setParent(overlay)` runs, Qt leaves a placeholder slot at index 0 that claims ~25-30px of splitter width, narrowing `now_playing`.

**Context:** D-12 was originally tested as strict `splitter.sizes()` equality before/after peek. That invariant cannot hold across reparenting on PySide6 6.11. Fix: capture-and-restore splitter sizes around `adopt()` AND test the user-observable contract via `now_playing.geometry()` drift tolerance (32px) instead of strict equality.
**Source:** 72-04-SUMMARY.md §deviations

### Pitfall 1: snapshot splitter sizes BEFORE `child.hide()`

`splitter.sizes()` returns `[0, total]` immediately after `child.hide()` because Qt redistributes space synchronously. Capture order matters: snapshot must come first.

**Context:** Caught in 72-03 implementation; locked by a positional test that asserts the snapshot equals pre-hide sizes and NOT post-hide sizes. Without this ordering, "restore on exit" would silently restore `[0, total]` and visually collapse the station_panel to zero width.
**Source:** 72-RESEARCH.md §Pitfall 1 + 72-03-PLAN.md

### Plan-body wording can drift from frontmatter must_haves

72-03's plan body had pre-Wave-0 wording forbidding explicit `handle.hide()/show()` calls. The frontmatter `must_haves.truths` (correctly amended post-spike) required them. Executor honored the frontmatter and flagged the inconsistency.

**Context:** Plans are revised at multiple levels (frontmatter, body) and revisions can land asymmetrically. Frontmatter is the contract for downstream agents; plan body is human-readable context. When they disagree, frontmatter wins — but the discrepancy should be flagged.
**Source:** 72-03-SUMMARY.md §deviations

---

## Patterns

### Wave 0 spike pattern

Dedicate a single low-cost plan (one task, one test file, ~30 lines of test code) to empirically verifying any RESEARCH.md assumption that production code will depend on. Spike runs FIRST (wave: 0, no `depends_on`); all other waves declare `depends_on: ["72-01"]` so spike failure is caught before downstream work.

**When to use:** Any phase whose RESEARCH.md cites a behavior from a Qt forum thread, an older major-version source, or a "should work" assumption. Especially valuable for cross-platform / cross-version Qt behavior, where the cost of an empirical test (5-10 minutes) is dwarfed by the cost of a wave's worth of production code built on a wrong assumption.
**Source:** 72-01-PLAN.md + 72-01-SUMMARY.md

### Global QApplication event filter + `QCursor.pos()` for cursor-in-zone detection

When you need to detect "cursor is in zone X of widget Y" regardless of which widget is currently under the cursor, install the event filter on `QApplication.instance()` (NOT on widget Y) and read cursor position from `QCursor.pos()` mapped to widget Y's local coordinates. Gate on `event.type() == QEvent.MouseMove` and then on your zone predicate. Receiver identity (`obj is widgetY`) is the wrong abstraction because Qt delivers MouseMove to the widget under the cursor, not to the parent you want to monitor.

**When to use:** Any hover-region detection, edge-trigger affordance, or cursor-tracking feature where the receiver under the cursor is not a single fixed widget (e.g., changes based on dynamic layout, panel visibility, or overlay state).
**Source:** debug session `phase-72-hover-peek-wayland.md` + commit 43ba666

### TODO-marker handoff between plans

When Plan N produces a function/slot that Plan N+1 must modify later, Plan N inserts a literal comment marker (e.g., `# TODO Plan 04: insert peek-release guard here`) at the exact insertion point. Plan N+1 grep-replaces the marker with the actual implementation. Both plans include grep gates: Plan N's acceptance asserts `grep -c MARKER == 1`; Plan N+1's acceptance asserts `grep -c MARKER == 0` AND the replacement-content grep `>= 1`.

**When to use:** Cross-plan code editing where the receiver of the edit doesn't exist yet at the time of the earlier plan. Makes the hand-off explicit, testable, and resistant to "the executor noticed Plan N didn't include the guard, so they added it conditionally" drift.
**Source:** 72-03-PLAN.md + 72-04-PLAN.md (warning W3 in iteration-1 review)

### Negative-assertion test for divergent persistence

When a phase deliberately diverges from an established persistence precedent (e.g., session-only vs SQLite-persisted toggle), add tests that ASSERT `repo.set_setting` is NOT called for the relevant key, AND test that `repo.get_setting` is NOT called for it during widget construction. Locks the divergence so a future "consistency" refactor can't silently revert it.

**When to use:** Any toggle/preference whose persistence semantics differ from the dominant pattern in the codebase. Generalizes to any "we explicitly chose NOT to do X" decision that has no source-level positive proof.
**Source:** 72-CONTEXT.md §D-09 + 72-03-PLAN.md acceptance criteria

### Reparenting (single instance) with `insertWidget(0, ...)` for round-trip

To show the SAME widget (with its filter/search/scroll state intact) in two different parents alternately: keep one instance, `setParent(new_parent)` to move it, and on return use `splitter.insertWidget(0, widget)` (NOT `addWidget` — which would put it on the wrong side of a 2-pane splitter). The widget's signals, model, and internal state survive the round-trip. Wave 0 spike A2 validated this on the project's actual `StationListPanel` instance.

**When to use:** Any "same panel, two contexts" UI pattern (docked + peeked, expanded + thumbnail, normal + dialog-popout). Cheaper and state-preserving compared to a parallel-instance approach.
**Source:** 72-01-SUMMARY.md §A2 + 72-04-SUMMARY.md

---

## Surprises

### A1 invalidated by Wave 0 spike

The Qt forum thread `forum.qt.io/topic/45377` claims `QSplitter` auto-hides the adjacent handle when a child is hidden. On PySide6 6.11.0 / Qt 6.11.0 this is false: `splitter.handle(1).isVisible()` remains `True` after `station_panel.hide()`.

**Impact:** Forced an explicit `self._splitter.handle(1).hide()/show()` call into `_on_compact_toggle`. Caught BEFORE Wave 2 ran by the Wave 0 spike. Zero downstream cost; would have been a visual bug ("thin vertical line where the station list used to be") if it had shipped.
**Source:** 72-01-SUMMARY.md

### 16 automated tests passed; the feature was non-functional

`test_dwell_fires_after_280ms_in_zone` and 15 sibling tests all passed via `pytest-qt`. The first live-device UAT (UAT-02) revealed that hover-peek never opened at all. Root cause: receiver-identity event filter — `pytest-qt` calls `QApplication.sendEvent(centralWidget, ev)` directly, which bypasses Qt's real dispatcher (which delivers MouseMove to the widget under the cursor, not the widget you `sendEvent` to).

**Impact:** Forced a real UAT before phase completion (UAT-04 had passed; the chain would have closed without UAT-02 surfacing this). Generated a major lesson about the limits of synthetic-event testing for cursor-tracking code. New regression test now sends MouseMove to a DIFFERENT receiver to prove the global filter doesn't depend on receiver identity.
**Source:** UAT-02 result + debug session `phase-72-hover-peek-wayland.md`

### `centralWidget()` is not a simple container

Parenting `StationListPeekOverlay` (a `QFrame`) to `centralWidget()` made `QSplitter` auto-manage it as a third sibling, repositioning the overlay into the right pane's area at ~640px instead of the design 360px. The plan body's "parent to centralWidget" prescription was load-bearingly wrong.

**Impact:** Forced executor to deviate from the plan body. Final design parents to `MainWindow` (matching `ToastOverlay`'s precedent) and relies on the fact that `ToastOverlay.show()` calls `raise_()` while `StationListPeekOverlay` deliberately does not, preserving the z-order intent (toast > peek > now-playing).
**Source:** 72-04-SUMMARY.md §deviations

### Qt creates a placeholder slot on QSplitter child reparent

Reparenting `station_panel` out of the splitter (`station_panel.setParent(overlay)`) leaves a ~25-30px placeholder slot at the old index, narrowing `now_playing` by that much.

**Impact:** Invalidated the originally-planned "splitter.sizes() unchanged during peek" invariant. Fixed by capturing-and-restoring splitter sizes around the adopt call AND reframing the D-12 test in terms of `now_playing.geometry()` drift (32px tolerance) — the user-observable contract, not the raw `sizes()` API.
**Source:** 72-04-SUMMARY.md §deviations

### The actual root-cause bug was already fixed before hover-peek was even implemented

UAT-04 (bottom-bar overlap fix on small/secondary display — the original phase goal) PASSED after Plan 72-03 landed. The hover-peek mechanism is a secondary affordance that took 2x more code than the core fix and is the part that failed UAT first.

**Impact:** Confirms that compact-mode = `station_panel.hide()` + splitter handle hide is the load-bearing 90% of the phase value. The hover-peek overlay is polish — slick when it works, but the user's stated problem ("bottom-bar overlap when I move to the small display") was already solved without it. Useful framing for future similar "primary mechanism + nice-to-have peek/preview affordance" phases: ship the primary first, gate the secondary on a UAT of its own.
**Source:** 72-UAT-SCRIPT.md + 72-VERIFICATION.md
