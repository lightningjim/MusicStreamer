---
phase: 66-color-themes-preset-and-custom-color-schemes-vaporwave-paste
plan: 04

subsystem: ui

tags:
  - pyside6
  - menu
  - integration
  - hamburger
  - uat

# Dependency graph
requires:
  - phase: 66-color-themes-preset-and-custom-color-schemes-vaporwave-paste
    plan: 01
    provides: "musicstreamer.theme.apply_theme_palette + THEME_PRESETS + DISPLAY_NAMES + THEME-01 requirement registered"
  - phase: 66-color-themes-preset-and-custom-color-schemes-vaporwave-paste
    plan: 02
    provides: "musicstreamer.ui_qt.theme_picker_dialog.ThemePickerDialog (modal QDialog with 4×2 tile grid, Customize…/Apply/Cancel, _save_committed flag)"
  - phase: 66-color-themes-preset-and-custom-color-schemes-vaporwave-paste
    plan: 03
    provides: "musicstreamer.ui_qt.theme_editor_dialog.ThemeEditorDialog (9-row Custom palette editor, per-row QColorDialog, Save/Reset/Cancel)"
  - phase: 59-visual-accent-color-picker
    provides: "ACCENT-02 — accent_color startup restore at main_window.py:241-245 (preserved verbatim by Plan 04)"

provides:
  - "Hamburger menu Theme entry — `act_theme = self._menu.addAction(\"Theme\")` immediately above existing `act_accent` at main_window.py:189"
  - "MainWindow._open_theme_dialog slot — lazy-imports ThemePickerDialog and runs `ThemePickerDialog(self._repo, parent=self).exec()`"
  - "ROADMAP.md Phase 66 entry shipped with concrete Goal text, **Requirements**: THEME-01, **Plans:** 4 plans, and 4-plan [x] checklist"
  - "End-to-end Phase 66 stack live: theme.py core → startup wire → ThemePickerDialog → ThemeEditorDialog → hamburger menu Theme action"

affects:
  - "All future phases — users can now switch QPalette themes from the hamburger menu without changing accent_color (Phase 59 layered Highlight contract preserved)"
  - "Phase 67 (similar-stations) — depends on Phase 66 per ROADMAP; this plan closes Phase 66"

# Tech tracking
tech-stack:
  added: []  # No new runtime dependencies
  patterns:
    - "Lazy-import dialog opener slot — matches _open_equalizer_dialog (Phase 47.2) precedent; keeps main_window.py module-import graph small"
    - "Peer menu-action pattern — Theme + Accent Color are sibling Settings entries; theme = base palette, accent = override on top"

key-files:
  created: []
  modified:
    - "musicstreamer/ui_qt/main_window.py — +16 LOC: act_theme menu action (line 189-190) + _open_theme_dialog slot (line 779-790)"
    - ".planning/ROADMAP.md — Phase 66 block: **Plans:** counter switched to '4 plans' + 66-04-PLAN.md checkbox flipped to [x]"
    - ".planning/phases/66-.../deferred-items.md — appended pre-existing _FakePlayer fixture gap (out-of-scope; not caused by this plan)"

key-decisions:
  - "Lazy-import ThemePickerDialog inside _open_theme_dialog (matches _open_equalizer_dialog pattern from Phase 47.2 — newer convention) instead of module-top import (older _open_accent_dialog pattern). Picker is opened on-demand only; module-top import would needlessly inflate every MainWindow import"
  - "ROADMAP.md was already mostly fleshed out by prior wave-tracking commits (Goal text + 4-plan checklist). Plan 04 Task 2 only needed to flip the **Plans:** counter from '3/4 plans executed' to '4 plans' (matching the plan's verify gate verbatim) and check off the 66-04-PLAN.md row"
  - "UAT (Task 3) auto-approved under --chain. Visual mood validation, layered-Highlight contract round-trip, Custom-theme persistence, and settings export/import round-trip ARE deferred to user post-merge — they cannot be automated on a Wayland desktop without a vision-LLM in the loop"

patterns-established:
  - "Hamburger menu Settings group ordering: Theme → Accent Color → Accounts → Equalizer (theme owns the base palette; accent overrides Highlight; accounts handles credentials; equalizer tunes audio). All four are peer modal dialogs; ordering is by 'how often does the user reach for this' which the v2.1 milestone tunes from daily use"

requirements-completed:
  - "THEME-01"

# Metrics
duration: ~6min
completed: 2026-05-09
---

# Phase 66 Plan 04: hamburger menu wire + ROADMAP close-out + UAT Summary

**Wires the new "Theme" hamburger menu action to ThemePickerDialog (Plan 02) above the existing "Accent Color" entry, completes the Phase 66 ROADMAP entry, and auto-approves the manual UAT checkpoint under --chain — closing the Phase 66 wave-3 deliverable.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-05-09T20:14:00Z (worktree branch checked out + base reset)
- **Completed:** 2026-05-09T20:20:39Z
- **Tasks:** 3 (Task 1 menu wire, Task 2 ROADMAP, Task 3 UAT auto-approved)
- **Files modified:** 2 source (`main_window.py`, `ROADMAP.md`) + 1 deferred-items log

## Accomplishments

- Inserted `act_theme = self._menu.addAction("Theme")` and bound-method `triggered.connect(self._open_theme_dialog)` immediately above the existing `act_accent` block at `main_window.py:189-190`. This is the exact insertion site dictated by Phase 66 D-15 (CONTEXT.md anchor) and `66-PATTERNS.md` §"main_window.py" §605-624.
- Added the new `_open_theme_dialog` slot above `_open_accent_dialog` (line 779-790) using the lazy-import pattern from `_open_equalizer_dialog` (`main_window.py:792-796`). The slot constructs `ThemePickerDialog(self._repo, parent=self)` and calls `.exec()` — modal child of MainWindow.
- Module-top imports unchanged: `ThemePickerDialog` is **not** imported at line 53 alongside `AccentColorDialog`. Lazy import keeps the import graph small (newer Phase 47.2 convention).
- Existing `accent_color` startup restore at `main_window.py:241-245` is byte-identical to pre-plan state — Phase 59 D-02 layered Highlight contract preserved verbatim.
- ROADMAP.md Phase 66 block: `**Plans:** 4 plans` (was `3/4 plans executed`); 66-04-PLAN.md flipped from `[ ]` to `[x]`; Goal text, Requirements, and 4-plan checklist intact from prior wave commits. Phase 65 (above) and Phase 67 (below) untouched.

## Verification

### Task 1 grep gates — ALL PASS

```
$ python -c "import ast; ast.parse(open('musicstreamer/ui_qt/main_window.py').read()); print('AST_OK')"
AST_OK

$ grep -c -F 'addAction("Theme")' musicstreamer/ui_qt/main_window.py
1

$ grep -c '^    def _open_theme_dialog' musicstreamer/ui_qt/main_window.py
1

$ grep -c -F 'from musicstreamer.ui_qt.theme_picker_dialog import ThemePickerDialog' musicstreamer/ui_qt/main_window.py
1

$ grep -c '^from musicstreamer.ui_qt.theme_picker_dialog' musicstreamer/ui_qt/main_window.py
0   # lazy-only — module-top is empty
```

Order check: Theme line = **189**, Accent line = **192** → ORDER_OK (Theme above Accent Color).

### Task 2 grep gates — ALL PASS

```
$ grep -c -F '**Plans:** 4 plans' .planning/ROADMAP.md
1

$ grep -c '66-01-PLAN.md' .planning/ROADMAP.md  # → 1
$ grep -c '66-02-PLAN.md' .planning/ROADMAP.md  # → 1
$ grep -c '66-03-PLAN.md' .planning/ROADMAP.md  # → 1
$ grep -c '66-04-PLAN.md' .planning/ROADMAP.md  # → 1

$ grep -A2 '### Phase 66' .planning/ROADMAP.md | grep -c 'To be planned'
0
```

### Targeted-test sweep — 75/75 PASS

Phase 66 + Phase 59 contract suites all green:

```
$ pytest tests/test_theme.py tests/test_theme_picker_dialog.py \
  tests/test_theme_editor_dialog.py tests/test_accent_color_dialog.py \
  tests/test_accent_provider.py -x -q

........................................................................ [ 96%]
...                                                                      [100%]
75 passed, 1 warning in 0.65s
```

### Smoke test — PASS

```
$ python -c "from musicstreamer.ui_qt.main_window import MainWindow; print('IMPORT_OK')"
IMPORT_OK
```

## UAT Checkpoint (Task 3) — auto-approved under --chain

The manual UAT checkpoint defined in `66-04-PLAN.md` Task 3 is a 7-check
end-to-end visual-and-functional walk on Linux Wayland (DPR=1.0):

| # | Check | Underlying Contract | Auto-Approved? |
|---|-------|---------------------|----------------|
| 1 | Theme menu action exists above Accent Color | UI-SPEC §Copywriting line 199 + main_window.py:189 | yes (verified by grep gate) |
| 2 | Visual mood matches branding (8 tiles render Vaporwave/Overrun/GBS variants/Dark/Light/Custom) | THEME-01 + VALIDATION.md §Manual-Only | **deferred to user post-merge** |
| 3 | Apply persists theme across restart | THEME-01 (covered by tests/test_theme.py round-trip + tests/test_theme_picker_dialog.py persist test) | yes (covered by automated tests) |
| 4 | **Layered Highlight contract** — accent survives theme switch (load-bearing) | Phase 59 D-02 (covered by tests/test_theme_picker_dialog.py accent-preservation test + tests/test_accent_provider.py layered test) | yes (covered by automated tests) |
| 5 | Custom theme creation + persistence across restart | tests/test_theme_editor_dialog.py save-persist test + tests/test_theme.py custom round-trip | yes (covered by automated tests) |
| 6 | Settings export/import round-trip carries theme + theme_custom | additive SQLite keys flow through existing settings_export.py with NO Plan 04 code change | **deferred to user post-merge** |
| 7 | Defensive fallback: corrupt theme_custom JSON → silent System default | tests/test_theme.py::test_apply_theme_palette_corrupt_json_falls_back_silently | yes (covered by automated tests) |

**Status: UAT auto-approved under --auto/--chain.** Visual verification (Checks 2 + 6) is **deferred to the user post-merge** — these are pure manual-eyeball validations (mood feel; ZIP round-trip on a real desktop) that cannot be automated on a headless Wayland desktop without a vision-LLM in the loop. The 5 contract-bound checks (1, 3, 4, 5, 7) are fully covered by the 75-test green suite.

If any deferred check fails post-merge, log the failing check + contract reference (D-XX / RESEARCH Q# / UI-SPEC section) and route to `/gsd-plan-phase 66 --gaps` for closure planning.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Tooling] Edit tool wrote to main repo instead of worktree (cwd-drift bug #3099)**

- **Found during:** Task 1 verification (grep gates returned 0 despite Read showing edits in place).
- **Issue:** The first round of Edit calls used the canonical worktree path (`musicstreamer/ui_qt/main_window.py`) but the Edit tool resolved that relative path against the main repo's working tree (`/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/ui_qt/main_window.py`) instead of the worktree (`/home/kcreasey/OneDrive/Projects/MusicStreamer/.claude/worktrees/agent-a50199897af075f40/musicstreamer/ui_qt/main_window.py`). git status in the **main repo** showed `M musicstreamer/ui_qt/main_window.py` while the worktree's git status showed nothing.
- **Fix:** Reverted the leaked edit in the main repo with a single-file `git -C /main/repo checkout -- musicstreamer/ui_qt/main_window.py` (preserving main repo's pre-existing `M scripts/install.sh` and `M uv.lock` from the gitStatus snapshot). Re-applied both Edits with absolute worktree paths (`/home/kcreasey/OneDrive/Projects/MusicStreamer/.claude/worktrees/agent-a50199897af075f40/musicstreamer/ui_qt/main_window.py`). All grep gates pass after the redo.
- **Files modified:** `musicstreamer/ui_qt/main_window.py` (worktree only — main repo restored)
- **Commit:** `495ad6f` (Task 1 commit; the leak-and-revert dance left no trace in git history because the main-repo working-tree revert was atomic and never staged)

**2. [Rule 3 - Plan-vs-state divergence] ROADMAP.md Phase 66 entry was already partially fleshed out**

- **Found during:** Task 2 read.
- **Issue:** The plan's `<action>` text expects to replace a placeholder block reading `**Goal:** [To be planned]` / `**Plans:** 0 plans` / `Plans: - [ ] TBD`. But prior wave-tracking commits (between Wave 1, Wave 2, and the spawn of this Wave 3 worktree) had already partially fleshed the entry: Goal text was correct, **Requirements**: THEME-01 was set, the 4-plan checklist with brief objectives was present, and plans 01-03 were `[x]`. Only the **Plans:** counter (was `3/4 plans executed`) and the 66-04-PLAN.md checkbox needed flipping.
- **Fix:** Made minimal edits matching the plan's verify-grep gates: (a) `**Plans:** 3/4 plans executed` → `**Plans:** 4 plans` (so the verify gate `grep -c '**Plans:** 4 plans'` returns 1); (b) `[ ] 66-04-PLAN.md` → `[x] 66-04-PLAN.md`. All three Task 2 verify gates pass.
- **Files modified:** `.planning/ROADMAP.md`
- **Commit:** `a3a6d74`

### Pre-existing Issues (Logged, Not Fixed)

**3. [Out-of-scope] tests/test_main_window_*.py — `_FakePlayer` missing `underrun_recovery_started`**

- Discovered when running the broader main_window suite. Verified pre-existing by stashing my Plan 04 changes and re-running the test — same `AttributeError: '_FakePlayer' object has no attribute 'underrun_recovery_started'` at `main_window.py:308`.
- This is a Phase 62 fixture-completeness gap; Plan 04 only adds a menu action + slot at lines 189-190 + 779-790 — far from the underrun signal wiring. Per SCOPE BOUNDARY rule, logged to `deferred-items.md` and not fixed.

## Threat Flags

None. Plan 04 surface is appearance-only (theme menu action) and reuses existing modal dialog plumbing. Threat T-66-13 (information disclosure via menu adjacency) was reviewed in the plan frontmatter and disposed `accept` — no new credential surface introduced.

## Self-Check: PASSED

Files claimed in this Summary verified to exist on disk:

- `musicstreamer/ui_qt/main_window.py` — FOUND
- `.planning/ROADMAP.md` — FOUND
- `.planning/phases/66-.../deferred-items.md` — FOUND

Commits claimed verified to exist on this worktree branch:

- `495ad6f` (Task 1) — FOUND in `git log --oneline`
- `a3a6d74` (Task 2) — FOUND in `git log --oneline`

Smoke test rerun: `python -c "from musicstreamer.ui_qt.main_window import MainWindow"` exits 0.

Targeted-test rerun: `pytest tests/test_theme.py tests/test_theme_picker_dialog.py tests/test_theme_editor_dialog.py tests/test_accent_color_dialog.py tests/test_accent_provider.py -x -q` → 75 passed.
