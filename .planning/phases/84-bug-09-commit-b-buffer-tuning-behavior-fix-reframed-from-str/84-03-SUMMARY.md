---
phase: 84-bug-09-commit-b-buffer-tuning-behavior-fix-reframed-from-str
plan: 03
subsystem: ui
tags: [qt-signal, pyside6, stats-for-nerds, signal-wire, ui-wiring, bug-09, d-12]

# Dependency graph
requires:
  - phase: 84
    plan: 01
    provides: "Wave 0 RED tests — test_buffer_duration_row_present, test_set_buffer_duration_baseline_format, test_set_buffer_duration_adapted_format, test_buffer_duration_changed_updates_stats_row + FakePlayer buffer_duration_changed Signal parity"
  - phase: 84
    plan: 02
    provides: "Player.buffer_duration_changed Signal + BUFFER_DURATION_S=30 baseline bump (parallel-wave coupling — see Wave-merge coupling note below)"
  - phase: 78
    plan: A (Commit A)
    provides: "set_underrun_count slot template + Underruns stats row + underrun_count_changed wire (1:1 mirror pattern)"
  - phase: 47.1
    plan: -
    provides: "_MutedLabel theme-responsive wrapper + _build_stats_widget QFormLayout pattern + hamburger-toggle visibility"
provides:
  - "NowPlayingPanel.set_buffer_duration(seconds: int) -> None slot (always-visible adaptive buffer-duration receiver)"
  - "self._buffer_duration_label attribute on NowPlayingPanel (live label, initial 'Ns' from BUFFER_DURATION_S)"
  - "'Buf duration' QFormLayout row in _build_stats_widget (row 2, after Underruns row, always-visible per D-12)"
  - "MainWindow bound-method DirectConnection wire from Player.buffer_duration_changed → NowPlayingPanel.set_buffer_duration"
affects: [phase-85-anything-touching-stats-for-nerds, future-buffer-tuning-phases, future-adaptive-growth-extensions]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Bound-method DirectConnection Signal wire (no lambda, no QueuedConnection arg) — mirrors Phase 78 underrun_count_changed pattern"
    - "Always-visible stats row (D-12 override of Phase 78 D-08 adapted-only default) — wrapper-level visibility governs whole widget, no per-row toggle"
    - "Function-local import of BUFFER_DURATION_S in both slot + stats row construction to avoid hoisting a single-call constant"

key-files:
  created: []
  modified:
    - "musicstreamer/ui_qt/now_playing_panel.py — set_buffer_duration slot + 'Buf duration' stats row"
    - "musicstreamer/ui_qt/main_window.py — buffer_duration_changed Signal wire"

key-decisions:
  - "Function-local import of BUFFER_DURATION_S (not module-level) — matches the micro-convention of importing constants at call-site when they are referenced in exactly one or two places in a file; keeps the module-level import block lean"
  - "Label text 'Buf duration' (NOT 'Buffer') — disambiguates from the existing 'Buffer' progressbar row label one row above; locked in by Wave 0 RED test assertion"
  - "Comment blocks at both edit sites explicitly cite RESEARCH §Pattern 3 + Pitfall 2 + the 'do NOT harmonize with nearby QueuedConnection sibling' warning"
  - "Wave-merge coupling acknowledged: test_buffer_duration_changed_updates_stats_row second-half assertion (emit(30) → '30s') requires Plan 84-02's BUFFER_DURATION_S=30 baseline; flips fully GREEN post-merge"

patterns-established:
  - "Phase 78 Commit A's set_underrun_count slot + Underruns row + DirectConnection wire trio is the canonical 1:1 mirror template for new stats-for-nerds Signal-driven rows — all three sites copy-edited here with one divergence (always-visible vs adapted-only)"

requirements-completed: [BUG-09]

# Metrics
duration: ~12min
completed: 2026-05-24
---

# Phase 84 Plan 03: D-12 UI Surface — Buf duration stats row + MainWindow Signal wire Summary

**Always-visible 'Buf duration' stats-for-nerds row with adaptive 'Ns (adapted)' label, driven by a bound-method DirectConnection wire from Player.buffer_duration_changed — 1:1 mirror of Phase 78 Commit A's Underruns row with always-visible D-12 override.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-24T22:36:08Z (approximate — Plan 03 spawn time)
- **Completed:** 2026-05-24T22:48:23Z
- **Tasks:** 2 (both `type=auto tdd=true`)
- **Files modified:** 2 (`musicstreamer/ui_qt/now_playing_panel.py`, `musicstreamer/ui_qt/main_window.py`)
- **Net code change:** +40 lines (+28 in now_playing_panel.py, +12 in main_window.py)

## Accomplishments

- **Task 1** — Added `NowPlayingPanel.set_buffer_duration(self, seconds: int) -> None` slot at `now_playing_panel.py:1012` (immediately after Phase 78's `set_underrun_count` at line 1002). Defensive `int()` coercion per Pattern S-5; baseline value (`BUFFER_DURATION_S`) renders bare `"Ns"`; any other value renders `"Ns (adapted)"`.
- **Task 1** — Added always-visible 'Buf duration' QFormLayout row in `_build_stats_widget` at `now_playing_panel.py:2966` (between the Phase 78 Underruns row at line 2956 and the trailing `wrapper.setVisible(False)` at line 2969). Initial text from live `BUFFER_DURATION_S`. Label text 'Buf duration' disambiguates from the row 0 'Buffer' progressbar label.
- **Task 2** — Added bound-method DirectConnection wire at `main_window.py:402` (immediately after the Phase 78 `underrun_count_changed` wire at line 390 with an 11-line comment block citing RESEARCH §Pattern 3 + qt-glib-bus-threading.md Pitfall 2 + the "do NOT harmonize with nearby QueuedConnection sibling" warning).

## Task Commits

Each task was committed atomically:

1. **Task 1: D-12 NowPlayingPanel — set_buffer_duration slot + 'Buf duration' stats row** — `e60d165` (feat)
2. **Task 2: D-12 MainWindow Signal wire — buffer_duration_changed → set_buffer_duration** — `3f0c82c` (feat)

**Plan metadata (this SUMMARY):** committed below.

## Files Created/Modified

- `musicstreamer/ui_qt/now_playing_panel.py` — Added `set_buffer_duration` slot (lines 1012–1029) and 'Buf duration' stats row (lines 2958–2966); +28 lines including comments and docstrings.
- `musicstreamer/ui_qt/main_window.py` — Added 1 `.connect(...)` line (line 402) with 11-line comment block above; +12 lines.

## Post-edit line anchors (per Plan 03 `<output>` requirement)

| Element | File | Line |
|---|---|---|
| `def set_buffer_duration(self, seconds: int) -> None:` | `musicstreamer/ui_qt/now_playing_panel.py` | 1012 |
| `form.addRow(buffer_duration_row_label, self._buffer_duration_label)` | `musicstreamer/ui_qt/now_playing_panel.py` | 2966 |
| `self._player.buffer_duration_changed.connect(self.now_playing.set_buffer_duration)` | `musicstreamer/ui_qt/main_window.py` | 402 |

## Pytest summary lines

- `uv run pytest tests/test_now_playing_panel.py` → **146 passed, 1 warning** (all 4 RED tests for this plan flipped to GREEN: `test_buffer_duration_row_present`, `test_set_buffer_duration_baseline_format`, `test_set_buffer_duration_adapted_format[60-60s (adapted)]`, `test_set_buffer_duration_adapted_format[120-120s (adapted)]`).
- `uv run pytest tests/test_main_window_underrun.py` → **6 passed, 1 failed, 1 warning** (the 1 failure is `test_buffer_duration_changed_updates_stats_row` — wave-merge coupling, see below).

## Wave-merge coupling note (NOT a bug — expected parallel-execution artifact)

`test_buffer_duration_changed_updates_stats_row` has two assertions:

1. `fake_player.buffer_duration_changed.emit(60)` → expect `_buffer_duration_label.text() == "60s (adapted)"` — **PASSES** here (60 ≠ BUFFER_DURATION_S in any reasonable baseline, so the slot writes `"60s (adapted)"`).
2. `fake_player.buffer_duration_changed.emit(30)` → expect `_buffer_duration_label.text() == "30s"` — **FAILS** here because this worktree still has `BUFFER_DURATION_S=10` (the pre-Plan-02 baseline); the slot writes `"30s (adapted)"` since 30 ≠ 10.

The slot implementation is correct against the live `BUFFER_DURATION_S` value — verified via inline monkeypatch simulation (set `c.BUFFER_DURATION_S = 30` then call the slot; both assertions pass). The test was authored in Wave 0 against the post-Plan-02 baseline (30), per the parallel-wave coordination model. **This failure will resolve automatically when Plan 84-02's `BUFFER_DURATION_S=30` bump merges in** during wave-merge. No code change required in Plan 03.

## Grep gate compliance

| Gate | Result |
|---|---|
| `grep -nE "buffer_duration_changed.*Qt\.ConnectionType\.QueuedConnection" main_window.py` | **0 matches** (DirectConnection regression-locked) |
| `grep -nE "buffer_duration_changed.*lambda" main_window.py` | **0 matches** (bound-method regression-locked, QA-05) |
| `grep -nE "Qt\.TextFormat\.RichText\|setTextFormat" now_playing_panel.py` (new additions) | **0 new matches** (T-40-04 plain-text invariant preserved) |
| `grep -nE "^\s*def set_buffer_duration\(self, seconds: int\) -> None:" now_playing_panel.py` | **1 match** (exact signature) |
| `grep -nE "self\._buffer_duration_label\.setText" now_playing_panel.py` | **2 matches** (baseline + adapted branches) |
| `grep -nE "_MutedLabel\(.Buf duration." now_playing_panel.py` | **1 match** (label text locked) |
| `grep -nE "form\.addRow\(buffer_duration_row_label" now_playing_panel.py` | **1 match at line 2966**, between underrun_row at 2956 and wrapper.setVisible at 2969 ✓ |
| `git diff --stat musicstreamer/__main__.py musicstreamer/player.py musicstreamer/constants.py` | **0 lines changed** (parallel-plan scope contract respected) |

## Decisions Made

- **Function-local `BUFFER_DURATION_S` import** at both call sites (slot + stats row construction) rather than hoisting to the module-level import block. Rationale: the constant is referenced in exactly two places in this file; hoisting one constant doesn't pay for the import-block real-estate. Reversible if a future phase brings the count to 3+ references.
- **No drive-by edits** to surrounding code. Plan 03 scope is tight (Signal wire + slot + row); the existing Phase 78 + Phase 47.1 patterns were copy-edited verbatim.
- **Comment block at the Signal wire** includes the "do NOT harmonize with nearby QueuedConnection sibling" warning verbatim from the plan — protects the next maintainer from incorrectly unifying the wires.

## Deviations from Plan

None — plan executed exactly as written. Both tasks landed verbatim per the `<action>` blocks; the only "deviation" worth noting is the wave-merge coupling on `test_buffer_duration_changed_updates_stats_row` which is an expected parallel-execution artifact, not a code-level deviation.

## Issues Encountered

**Issue 1 — Absolute-path resolution from worktree (#3099 reminder).** Initial Edit calls used the literal absolute path `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/ui_qt/now_playing_panel.py`, which silently resolved to the **main repo** (not the worktree at `.claude/worktrees/agent-a97a205c2114f00e6/`). Caught when `git status` in the worktree showed no changes and `git status` in the main repo showed the modification. **Resolution:** reverted the main-repo change with `git checkout -- musicstreamer/ui_qt/now_playing_panel.py`, then re-applied Edit using the worktree-prefixed absolute path. Subsequent Task 2 edit used the worktree path correctly. No data loss; no commits landed on the main repo. The worktree-path-safety reference (`@$HOME/.claude/get-shit-done/references/worktree-path-safety.md`) documents this exact failure mode.

## User Setup Required

None — no external service configuration. All changes are in-process Qt Signal wires and UI label additions.

## Next Phase Readiness

- **Plan 84-03 complete.** The D-12 UI surface (slot + always-visible row + Signal wire) is shipped. The wave-merge dependency on Plan 84-02 (`BUFFER_DURATION_S=30` baseline + `buffer_duration_changed` Signal emit logic in Player) is documented and resolves automatically at merge time.
- **Wave 1 complete after Plan 84-02 merges.** All four production files in scope ({constants.py, player.py, main_window.py, now_playing_panel.py}) will be edited; Wave 0 test surface + Wave 1 implementation will be jointly GREEN.
- **Plan 84-04 (verification)** can proceed once the wave merges — confirms the closed-loop integration (Player emit → MainWindow wire → NowPlayingPanel label) end-to-end with the live `BUFFER_DURATION_S=30` baseline.

## Self-Check: PASSED

**File existence verification:**
- `musicstreamer/ui_qt/now_playing_panel.py` — FOUND (modified, contains `set_buffer_duration` slot + 'Buf duration' row)
- `musicstreamer/ui_qt/main_window.py` — FOUND (modified, contains `buffer_duration_changed.connect(...)` at line 402)
- `.planning/phases/84-bug-09-commit-b-buffer-tuning-behavior-fix-reframed-from-str/84-03-SUMMARY.md` — FOUND (this file)

**Commit existence verification:**
- `e60d165` (Task 1) — FOUND in `git log`
- `3f0c82c` (Task 2) — FOUND in `git log`

**Untouched-file verification:**
- `musicstreamer/__main__.py` — 0 diff ✓
- `musicstreamer/player.py` — 0 diff ✓ (Plan 02 scope)
- `musicstreamer/constants.py` — 0 diff ✓ (Plan 02 scope)
- `.planning/STATE.md` — 0 diff ✓ (executor instruction: do NOT update)
- `.planning/ROADMAP.md` — 0 diff ✓ (executor instruction: do NOT update)

---
*Phase: 84-bug-09-commit-b-buffer-tuning-behavior-fix-reframed-from-str*
*Plan: 03*
*Completed: 2026-05-24*
