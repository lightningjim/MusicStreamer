---
phase: 72
plan: 02
subsystem: ui/qt-now-playing-panel
tags: [wave-1, layout-01, qt-toolbutton, qicon-resource, qsignal-bool, tdd, qa-05, d-09-session-only]
requires:
  - "72-01 (Wave 0 spike — A1 invalidated / A2 confirmed) — completed at ca4be24 in main repo"
provides:
  - "musicstreamer/ui_qt/now_playing_panel.py — compact_mode_toggled = Signal(bool) at class scope + compact_mode_toggle_btn QToolButton in controls row + _on_compact_btn_toggled bound-method slot + set_compact_button_icon(checked) public helper"
  - "musicstreamer/ui_qt/icons/sidebar-show-symbolic.svg + sidebar-hide-symbolic.svg (16x16 viewBox, fill='currentColor', new family members)"
  - "musicstreamer/ui_qt/icons.qrc — two new alias entries inside /icons qresource block"
  - "musicstreamer/ui_qt/icons_rc.py — regenerated via pyside6-rcc 6.11.0; resource count 12 -> 14"
  - "tests/test_phase72_now_playing_panel.py — 8 unit tests pinning button placement, sizes, checkable state, initial tooltip, icon-flip, signal-emission, D-09 negative-persistence invariant, QA-05 no-lambda gate"
affects:
  - ".planning/phases/72-fullscreen-mode-hide-left-column-for-compact-displays/72-03-PLAN.md (next wave) — will consume self.now_playing.compact_mode_toggled signal + self.now_playing.compact_mode_toggle_btn handle + self.now_playing.set_compact_button_icon helper; Plan 03 must also add the explicit splitter.handle(1).hide()/show() calls per A1 invalidation"
  - ".planning/phases/72-fullscreen-mode-hide-left-column-for-compact-displays/72-UI-SPEC.md §File Inventory — '24x24' viewBox declaration is superseded by codebase precedent 16x16 (acknowledged in 72-PATTERNS §planner_decisions §1; PATTERNS-driven decision applied here)"
tech_stack_added: []
tech_stack_patterns:
  - "QToolButton 28x28 + setIconSize(QSize(20, 20)) + setCheckable(True) + QIcon.fromTheme(name, QIcon(':/icons/{name}.svg')) fallback chain — direct mirror of star_btn (line 458-467) and eq_toggle_btn (line 471-486)"
  - "outbound Signal(bool) declared at class scope alongside existing Signal block (lines 220-266), forwarded by bound-method slot — mirrors stopped_by_user / track_starred forwarding shape"
  - "pyside6-rcc 6.11.0 idempotent regen of icons_rc.py from icons.qrc (Phase 36 / D-24 build step)"
key_files_created:
  - "musicstreamer/ui_qt/icons/sidebar-show-symbolic.svg"
  - "musicstreamer/ui_qt/icons/sidebar-hide-symbolic.svg"
  - "tests/test_phase72_now_playing_panel.py"
key_files_modified:
  - "musicstreamer/ui_qt/icons.qrc"
  - "musicstreamer/ui_qt/icons_rc.py"
  - "musicstreamer/ui_qt/now_playing_panel.py"
decisions:
  - "D-05 icon flip pinned by set_compact_button_icon helper + dedicated unit test (cacheKey delta)"
  - "D-09 panel-level half: NO repo.set_setting call inside NowPlayingPanel for any compact-* key — pinned by test_compact_button_no_repo_setting_write"
  - "Button insertion line: 518 (current state). UI-SPEC says 'line 514' as of plan-authoring time; the actual current file has additional comment lines so the button lands at 518 — between volume_slider at 498 and addStretch(1) at 520. Source-order awk gate PASSES."
  - "PATTERNS §planner_decisions §1: SVG viewBox = 16x16 (matches existing 12-icon family) instead of UI-SPEC's stale '24x24'. QIcon.setIconSize(QSize(20,20)) scales the viewBox transparently so visual size is identical."
  - "Glyph design (Claude's discretion per CONTEXT §Decisions §Claude's Discretion): 3-px-wide left rectangle (panel) + chevron pointing AWAY from the panel (right for sidebar-show 'reveal', left for sidebar-hide 'collapse'). 8x8 chevron at canvas center-right. Matches document-edit-symbolic.svg stroke-mass profile."
metrics:
  duration_seconds: 204
  duration_human: "~3min 24sec"
  tasks_completed: 2
  files_created: 3
  files_modified: 3
  test_count_added: 8
  test_pass_rate: "135/135 PASS (8 new + 127 prior in tests/test_now_playing_panel.py)"
  completed: "2026-05-13"
---

# Phase 72 Plan 02: Compact-mode toggle button on NowPlayingPanel — Summary

**One-liner:** Added the panel-level half of the compact-mode feature — two new
`sidebar-{show,hide}-symbolic.svg` icons (16x16 family), a checkable
`compact_mode_toggle_btn` QToolButton at the far-right of the now-playing
control row (line 518 between volume_slider and addStretch), a
`compact_mode_toggled = Signal(bool)` re-emitted via bound-method slot, and a
`set_compact_button_icon(checked)` public helper that flips icon + tooltip for
the MainWindow slot (Plan 72-03) to call after splitter restore.

## Tasks Completed

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | SVG icons + icons.qrc + icons_rc.py regen | `bcc1319` | `musicstreamer/ui_qt/icons/sidebar-{show,hide}-symbolic.svg`, `musicstreamer/ui_qt/icons.qrc`, `musicstreamer/ui_qt/icons_rc.py` |
| 2-RED | Failing tests for compact_mode_toggle_btn | `bf04894` | `tests/test_phase72_now_playing_panel.py` |
| 2-GREEN | Signal + button + helper in NowPlayingPanel | `884b7f7` | `musicstreamer/ui_qt/now_playing_panel.py` |

TDD cycle: RED (`bf04894`) -> GREEN (`884b7f7`). No REFACTOR step — implementation
already mirrors the star_btn / eq_toggle_btn precedent exactly and needs no cleanup.

## Final Source Locations

| Element | File | Line |
| ------- | ---- | ---- |
| `compact_mode_toggled = Signal(bool)` declaration | `musicstreamer/ui_qt/now_playing_panel.py` | 272 |
| Button construction (`self.compact_mode_toggle_btn = QToolButton(self)`) | `musicstreamer/ui_qt/now_playing_panel.py` | 506 |
| `toggled.connect(self._on_compact_btn_toggled)` | `musicstreamer/ui_qt/now_playing_panel.py` | 517 |
| `controls.addWidget(self.compact_mode_toggle_btn)` | `musicstreamer/ui_qt/now_playing_panel.py` | 518 |
| `_on_compact_btn_toggled` slot definition | `musicstreamer/ui_qt/now_playing_panel.py` | 1054 |
| `set_compact_button_icon` public helper | `musicstreamer/ui_qt/now_playing_panel.py` | 1062 |

**Source-order assertion (per plan acceptance gate):**

```
volume_slider line: 498
compact_mode_toggle_btn line: 518
addStretch(1) line: 520
ORDER OK
```

The plan said "insert at line 514"; current file has additional comment lines so
the actual addWidget(...) call lands at line 518 — the invariant
(`volume_slider < compact_mode_toggle_btn < addStretch(1)`) is the substantive
ordering requirement and PASSES.

## Glyph Design Decisions (Claude's discretion)

Both new SVGs adopt the existing 12-icon `*-symbolic.svg` family:
- **viewBox:** `0 0 16 16` (matches non-starred-symbolic, document-edit-symbolic, etc.)
- **width / height:** `16` / `16` (no `px` suffix — matches document-edit-symbolic style)
- **fill:** `currentColor` (palette-driven theming — matches document-edit-symbolic;
  not the older hardcoded `#2e3434` style of non-starred-symbolic).
- **Stroke-mass parity:** Each glyph occupies similar canvas mass to
  document-edit-symbolic — a 3-px-wide left rectangle (representing the panel)
  + a center-right chevron occupying ~6-8 px width.

**Glyph 1 — `sidebar-show-symbolic.svg` (used when panel hidden, "click to show"):**

```svg
<path d="M 1 2 L 1 14 L 4 14 L 4 2 Z M 9 4.5 L 7.5 6 L 9.5 8 L 7.5 10 L 9 11.5 L 12 8.5 L 12 7.5 Z" fill="currentColor"/>
```

Composition: a 3x12 rectangle at the left edge (the "panel" — visible because
it's about to be revealed) + a right-pointing chevron (8x8 envelope) at canvas
mid-right pointing away from the panel. Reads as "reveal the panel from the left."

**Glyph 2 — `sidebar-hide-symbolic.svg` (used when panel visible, "click to hide"):**

```svg
<path d="M 1 2 L 1 14 L 4 14 L 4 2 Z M 11 4.5 L 8 7.5 L 8 8.5 L 11 11.5 L 12.5 10 L 10.5 8 L 12.5 6 Z" fill="currentColor"/>
```

Composition: the same left 3x12 rectangle (the "panel" — currently docked) + a
left-pointing chevron at canvas right pointing back toward the panel. Reads as
"collapse the panel into the left edge."

The two glyphs share the rectangle subpath verbatim so the visual diff between
states is **only** the chevron direction — a minimal-change idiom that aligns
with the icon-flip-only-on-state-change Qt convention.

**Rejected alternatives:**
- `SP_TitleBarShadeButton` / `SP_TitleBarUnshadeButton` — Qt built-in, but they
  render at 16x16 with an OS-styled bevel that does not match the project's
  flat-monochrome `*-symbolic` family.
- Drawing a more elaborate "panel-with-content" glyph (lines representing list
  rows inside the rectangle) — rejected because 16x16 leaves too little room
  for legible inner detail at 20x20 render size and the chevron-direction
  read is the load-bearing affordance.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Acceptance criterion grep counts are off by encoding**

- **Found during:** Task 1 verify step.
- **Issue:** Plan acceptance criterion says
  `grep -c 'sidebar-show-symbolic.svg' musicstreamer/ui_qt/icons.qrc` should
  return 2 (alias + path). It returns 1 because both occurrences are on the
  same line and `grep -c` counts lines, not occurrences. Same fundamental issue
  with `grep -c sidebar musicstreamer/ui_qt/icons_rc.py` — pyside6-rcc encodes
  filenames as Qt's internal wide-char binary format, so plain ASCII `grep`
  returns 0 even when the resources ARE bundled.
- **Fix:** Replaced the brittle grep counts with semantic equivalents that
  verify the underlying contract:
  - For qrc: `grep -o 'sidebar-show-symbolic.svg' musicstreamer/ui_qt/icons.qrc | wc -l` returns 2 (alias + path occurrences).
  - For icons_rc.py: Python `QDir(':/icons').entryList()` returns 14 names
    (was 12 before), with both `sidebar-show-symbolic.svg` and
    `sidebar-hide-symbolic.svg` present. This is a strictly stronger semantic
    check than the planned grep.
- **Files modified:** none — verification methodology was adjusted, not source code.
- **Commit:** verification documented here; no separate fix commit needed.

**2. [Rule 3 - Blocking] Plan verification regex `grep -E "lambda" ... | grep -c "compact"` triggers on comments**

- **Found during:** plan-level `<verification>` block.
- **Issue:** The plan's negative source assertion
  `grep -E "lambda" musicstreamer/ui_qt/now_playing_panel.py | grep -c "compact"`
  expects 0 hits but returns 1 — the hit is in my docstring on the Signal
  declaration: `# _on_compact_toggle slot (QA-05 bound method, no lambda).`
  This is a comment ABOUT the lambda ban, not an actual lambda.
- **Fix:** The stronger semantic check — `grep "compact_mode_toggle_btn.toggled.connect" | grep -c lambda` — returns 0 (the literal anti-pattern the rule is trying to ban). This is what `test_no_lambda_in_compact_connect` verifies via `inspect.getsource` (already passing). The plan's commentary-triggered grep is a known-false-positive of regex-on-source vs AST-on-source; the test #8 is the actual gate.
- **Files modified:** none — verification methodology was adjusted.

### Pre-existing test-teardown warning (out of scope)

- **Type:** Out-of-scope / pre-existing thread-teardown warning
- **Observation:** Running `pytest tests/test_now_playing_panel.py` emits
  `RuntimeError: Signal source has been deleted` from
  `musicstreamer/cover_art.py:99 -> now_playing_panel.py:_cb` during test
  teardown (cover-art worker thread emitting after panel destruction). This
  warning appears on stderr but does NOT fail any test — `pytest 2>/dev/null`
  reports `127 passed`.
- **Disposition:** Pre-existing — reproduces on this worktree's base commit
  (83c1e88) when my changes are stashed. Out of scope per SCOPE BOUNDARY rule.
  Logged here for awareness; the underlying race (`_cb` keeping a captured
  reference to the deleted panel's `cover_art_ready` Signal) predates Phase 72.

## Verification Results

| Check | Result |
| ----- | ------ |
| `pytest tests/test_phase72_now_playing_panel.py -x -v` | 8 passed |
| `pytest tests/test_phase72_now_playing_panel.py tests/test_now_playing_panel.py` | 135 passed (8 new + 127 prior) |
| `python -c "from musicstreamer.ui_qt.now_playing_panel import NowPlayingPanel; assert hasattr(NowPlayingPanel, 'compact_mode_toggled')"` | exit 0 |
| `python -c "from musicstreamer.ui_qt import icons_rc; from PySide6.QtCore import QFile; assert QFile(':/icons/sidebar-show-symbolic.svg').exists()"` | exit 0 |
| `python -c "from PySide6.QtCore import QDir; from musicstreamer.ui_qt import icons_rc; print(len(QDir(':/icons').entryList()))"` | `14` (was 12 — both new SVGs bundled) |
| `grep -c 'viewBox="0 0 16 16"' musicstreamer/ui_qt/icons/sidebar-show-symbolic.svg` | `1` (and same for sidebar-hide) |
| `grep -c 'fill="currentColor"' musicstreamer/ui_qt/icons/sidebar-show-symbolic.svg` | `1` (and same for sidebar-hide) |
| `grep -E 'fill="#' musicstreamer/ui_qt/icons/sidebar-{show,hide}-symbolic.svg` | no matches (no hardcoded hex) |
| `grep -nc "compact_mode_toggled = Signal(bool)" musicstreamer/ui_qt/now_playing_panel.py` | `1` (line 272) |
| `grep -nc "compact_mode_toggle_btn = QToolButton" musicstreamer/ui_qt/now_playing_panel.py` | `1` (line 506) |
| `awk` source-order gate (volume_slider < compact_mode_toggle_btn < addStretch) | `ORDER OK` (498 < 518 < 520) |
| `grep "compact_mode_toggle_btn.toggled.connect" musicstreamer/ui_qt/now_playing_panel.py \| grep -c lambda` | `0` (QA-05 OK) |
| `grep -E "set_setting.*compact" musicstreamer/ui_qt/now_playing_panel.py` | no matches (D-09 OK) |
| `grep -E "_act_compact\|_act.*sidebar" musicstreamer/ui_qt/main_window.py` | no matches (D-01 OK — no hamburger entry added) |

## Known Stubs

None. Every element introduced by this plan is fully wired to a deterministic
test that exercises it end-to-end at the panel level. The MainWindow-side
half of the wiring (consuming `compact_mode_toggled` to drive `station_panel.hide()`
+ `_splitter.handle(1).hide()`) is intentionally deferred to Plan 72-03 per
the plan's scope statement.

## Threat Flags

None. This plan introduces zero I/O, zero auth, zero network surface, zero new
file system access patterns. The compact-toggle button is a checkable QToolButton
emitting a bool Signal — entirely within-process Qt widget state. Per plan's
`<threat_model>` STRIDE row T-72-02: Disposition: accept; mitigation plan: n/a.

## Recommendations for Plan 72-03 (next plan in wave)

1. **Consume `self.now_playing.compact_mode_toggled.connect(self._on_compact_toggle)`** via bound method (QA-05).
2. **A1 invalidation requires explicit splitter handle management** (per 72-01 SUMMARY recommendation #1):
   ```python
   def _on_compact_toggle(self, checked: bool) -> None:
       if checked:
           self._splitter_sizes_before_compact = self._splitter.sizes()  # Pitfall 1: BEFORE hide
           self.station_panel.hide()
           self._splitter.handle(1).hide()  # REQUIRED — A1 INVALIDATED
       else:
           self.station_panel.show()
           self._splitter.handle(1).show()
           if self._splitter_sizes_before_compact:
               self._splitter.setSizes(self._splitter_sizes_before_compact)
               self._splitter_sizes_before_compact = None  # Pitfall 5 reset
       self.now_playing.set_compact_button_icon(checked)  # use the helper this plan exposes
   ```
3. **Do NOT add a `self._repo.set_setting("compact_mode", ...)` call** to `_on_compact_toggle` (D-09 session-only — the MainWindow half of the panel-level negative test).
4. **D-01 (no hamburger entry)** must hold — Plan 72-02 verified the assertion negatively in main_window.py; Plan 72-03 must not regress this by adding `_act_compact = QAction(...)`.
5. The `compact_mode_toggle_btn` is the single source of truth (Pattern 5 / QA-05). Ctrl+B shortcut (Plan 72-03 scope) should call `self.now_playing.compact_mode_toggle_btn.toggle()` — never bypass it.

## Self-Check: PASSED

- **Created files exist:**
  - `musicstreamer/ui_qt/icons/sidebar-show-symbolic.svg` — present (verified via `ls -la` and `QFile(':/icons/sidebar-show-symbolic.svg').exists()` returns True).
  - `musicstreamer/ui_qt/icons/sidebar-hide-symbolic.svg` — present (same verification).
  - `tests/test_phase72_now_playing_panel.py` — present (8 tests collected by pytest, all PASS).
- **Modified files contain the changes:**
  - `musicstreamer/ui_qt/icons.qrc` — verified contains both new alias lines.
  - `musicstreamer/ui_qt/icons_rc.py` — verified resource count 14 (was 12).
  - `musicstreamer/ui_qt/now_playing_panel.py` — verified `compact_mode_toggled = Signal(bool)` at line 272 and `compact_mode_toggle_btn = QToolButton(self)` at line 506.
- **Commits exist in the worktree branch `worktree-agent-a2a461ddf29ba9159`:**
  - `bcc1319` `feat(72-02): add sidebar-show/hide SVG icons + qrc registration` — `git log --oneline | grep bcc1319` PASS.
  - `bf04894` `test(72-02): add failing tests for compact_mode_toggle_btn` — PASS.
  - `884b7f7` `feat(72-02): add compact_mode_toggle_btn + Signal to NowPlayingPanel` — PASS.
- **TDD gate compliance:** `test(72-02)` commit precedes `feat(72-02): add compact_mode_toggle_btn` (RED before GREEN). Task 1 was a `feat(72-02)` commit for the resource bundle (not behavior-adding under the MVP+TDD predicate — pure resource artifacts), so it correctly does not require its own RED. Task 2 (the behavior-adding task) followed the strict RED -> GREEN sequence.

---

*Plan 72-02 completed: 2026-05-13*
*Phase: 72-fullscreen-mode-hide-left-column-for-compact-displays*
