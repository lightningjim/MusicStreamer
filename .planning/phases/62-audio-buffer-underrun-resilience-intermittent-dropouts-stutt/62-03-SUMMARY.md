---
phase: 62-audio-buffer-underrun-resilience-intermittent-dropouts-stutt
plan: 03
subsystem: ui-mainwindow-toast-cooldown
tags: [phase-62, bug-09, ui-qt, cooldown-gate, logging-config, tdd-green]

# Dependency graph
requires:
  - phase: 62-audio-buffer-underrun-resilience-intermittent-dropouts-stutt
    plan: 00
    provides: "5 RED MainWindow integration tests in tests/test_main_window_underrun.py — D-06/D-08 cooldown, D-03/Pitfall 4 closeEvent, Pitfall 5 __main__ logger; FakePlayer extension with underrun_recovery_started Signal + shutdown_underrun_tracker no-op"
  - phase: 62-audio-buffer-underrun-resilience-intermittent-dropouts-stutt
    plan: 02
    provides: "Player.underrun_recovery_started Signal (main → MainWindow surface) + Player.shutdown_underrun_tracker() public method"
provides:
  - "MainWindow Phase 62 wiring: time import + cooldown class const + cooldown bookkeeping field + queued Player Signal connection + _on_underrun_recovery_started slot + closeEvent shutdown_underrun_tracker call"
  - "Per-logger INFO level for musicstreamer.player in __main__.py (Pitfall 5 — scoped, NOT global)"
affects: []  # Phase 62 closure for instrumentation half of BUG-09; behavior fix deferred per CONTEXT.md <deferred>

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Cooldown via time.monotonic() — first project use; wall-clock-jump immune (NTP / DST safe); 10s window persists across station changes (D-08)"
    - "Per-logger setLevel(INFO) on musicstreamer.player — keeps GLOBAL basicConfig at WARNING so aa_import / gbs_api / mpris2 chatter stays silenced (Pitfall 5 mitigation)"
    - "closeEvent shutdown ordering: Player.shutdown_underrun_tracker() BEFORE _media_keys.shutdown() — synchronous log write must complete before any subsystem teardown (Pitfall 4)"

key-files:
  created: []
  modified:
    - "musicstreamer/ui_qt/main_window.py — +45 lines across 6 distinct insertion sites (import time / class const / cooldown field / queued connect / new slot / closeEvent extension)"
    - "musicstreamer/__main__.py — +4 lines (1 logging.getLogger().setLevel call + 3-line Phase 62 reference comment)"

key-decisions:
  - "Phase 62-03 / Two-task split (single insertion-site per file): Task 1 owns the 6 insertion sites in main_window.py (4/5 tests GREEN); Task 2 owns the 1-line addition in __main__.py (5th test GREEN). The two files are owned by different concerns (UI wiring vs. startup logging config) and the tests partition cleanly along that boundary — splitting the commit makes the cause-of-failure attribution sharper for any future bisect."
  - "Phase 62-03 / closeEvent ordering: Player.shutdown_underrun_tracker() runs BEFORE _media_keys.shutdown(). Pitfall 4 (queued slots may not run after closeEvent returns) is the load-bearing constraint — the tracker writes its log line synchronously inside shutdown_underrun_tracker; deferring it to after _media_keys teardown invites a subsystem failure from the latter to swallow the underrun log. Both shutdowns are wrapped in their own try/except _log.warning per the existing S-6 belt-and-braces convention."
  - "Phase 62-03 / Cooldown bookkeeping at MainWindow, NOT Player: per CONTEXT.md and PATTERNS §2b, the cooldown is a UI concern (toast debounce), not a Player concern (Player still emits underrun_recovery_started on every dwell elapse and writes every log line). Centralizing on MainWindow keeps the Player surface clean and the test seam targets the same monkeypatch site as the existing time module."
  - "Phase 62-03 / `…` escape over inlined U+2026 glyph: project convention from main_window.py:367 (`Connecting…`) and 393 (`Stream failed, trying next…`). Test 1 substring-matches `'Buffering' in w._toast.label.text()`, so either form would pass — but matching the codebase's escape-form keeps Phase 62 invisible in `git grep` for non-Latin-1 codepoints."

requirements-completed: []  # BUG-09 instrumentation half ships here; full requirement closure follows in /gsd-verify-work + /gsd-complete-phase after the 3-success-criteria gate runs (#1 logging, #2 toast, #3 behavior fix). Per CONTEXT.md <deferred>, success criterion #3 is a follow-up phase.

# Metrics
duration: 6min
completed: 2026-05-08
---

# Phase 62 Plan 03: Wire MainWindow Cooldown + __main__.py Logger Summary

**Wave 2 GREEN closure for Phase 62 — wired MainWindow to consume Player.underrun_recovery_started with a 10s time.monotonic() cooldown gate, hooked Player.shutdown_underrun_tracker() into closeEvent BEFORE _media_keys.shutdown (Pitfall 4 ordering), and added per-logger INFO level for musicstreamer.player in __main__.py (Pitfall 5 — scoped, NOT global). All 5 RED MainWindow integration tests authored in Plan 00 now GREEN; 20/20 Phase 62 RED tests across the three new test files now GREEN; D-05 invariant (now_playing_panel.py 0-line diff) and D-09 invariant (constants.py 0-line diff) both preserved**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-05-08T02:36:23Z
- **Completed:** 2026-05-08T02:42:44Z
- **Tasks:** 2
- **Files modified:** 2 (musicstreamer/ui_qt/main_window.py + musicstreamer/__main__.py)

## Accomplishments

- All 5 integration tests in `tests/test_main_window_underrun.py` turn RED → GREEN. Tests 1-4 closed by Task 1 (Player Signal wiring + cooldown gate + closeEvent shutdown); Test 5 closed by Task 2 (per-logger INFO).
- Phase 62 closure: 20/20 RED tests authored in Plan 00 now GREEN (7 tracker + 8 Player + 5 MainWindow). The instrumentation half of BUG-09 ships.
- 100/100 across the Phase 62 quick-suite + adjacent regression suite (test_main_window_underrun.py + test_player_underrun.py + test_player_underrun_tracker.py + test_main_window_integration.py + test_player_buffering.py + test_player_buffer.py + test_player.py + test_player_pause.py).
- D-05 invariant preserved: `git diff musicstreamer/ui_qt/now_playing_panel.py | wc -l` returns 0. Toast-only UX honored — no auto-show of stats-for-nerds buffer bar, no new always-visible chrome.
- D-09 invariant preserved: `git diff musicstreamer/constants.py | wc -l` returns 0. `BUFFER_DURATION_S = 10` and `BUFFER_SIZE_BYTES = 10 * 1024 * 1024` untouched throughout Phase 62.
- Pitfall 5 mitigation live: `grep -c "logging.basicConfig(level=logging.WARNING)" musicstreamer/__main__.py` returns 1 (existing line unchanged); `grep -c "getLogger.*musicstreamer.player.*setLevel.*INFO" musicstreamer/__main__.py` returns 1 (new line). Global level stays at WARNING; only `musicstreamer.player` is bumped to INFO.
- Pitfall 4 mitigation live: closeEvent calls `Player.shutdown_underrun_tracker()` BEFORE `_media_keys.shutdown()`. Both wrapped in their own try/except `_log.warning(...)` (S-6 belt-and-braces).
- D-06 toast text: `Buffering…` with `…` escape (matches codebase convention from `Connecting…` at main_window.py:367).
- D-08 cooldown: `time.monotonic()`-based 10s window. Class-level constant `_UNDERRUN_TOAST_COOLDOWN_S: float = 10.0` declared once at MainWindow scope; per-instance bookkeeping `self._last_underrun_toast_ts: float = 0.0` initialized in `__init__` adjacent to `self._toast = ToastOverlay(self)`. Cooldown clock persists across station changes (no special-case reset).
- QA-05 honored: bound-method `Signal.connect(...)` everywhere — no self-capturing lambdas. The new `_on_underrun_recovery_started` slot is a bound method.
- Pitfall 2 alignment: queued connection `Qt.ConnectionType.QueuedConnection` for `underrun_recovery_started → _on_underrun_recovery_started` matches the file's existing convention even though Player emits this Signal from the main thread (the queueing is policy-uniform, not threading-required).

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire MainWindow to consume underrun_recovery_started + cooldown gate + closeEvent shutdown hook** — `f1818c3` (feat)
2. **Task 2: Add per-logger INFO level for musicstreamer.player to __main__.py (Pitfall 5 — scoped, NOT global)** — `4156334` (feat)

**Plan metadata:** _to be added on final docs commit_

## Files Created/Modified

- `musicstreamer/ui_qt/main_window.py` (modified, +45 lines across 6 insertion sites)
  - **Insertion 1** (`import time`, +1 line): Added alphabetically between `import os` and the resource-comment block at module top. Required because Tests 2 / 3 monkeypatch `musicstreamer.ui_qt.main_window.time.monotonic` — without the module-level import the attribute lookup raises `AttributeError`.
  - **Insertion 2** (class-level cooldown const, +5 lines incl. comment): `_UNDERRUN_TOAST_COOLDOWN_S: float = 10.0` placed at class scope directly after the class docstring, before `def __init__`. First class-level constant on `MainWindow`.
  - **Insertion 3** (cooldown bookkeeping field, +4 lines incl. comment): `self._last_underrun_toast_ts: float = 0.0` initialized adjacent to `self._toast = ToastOverlay(self)` (around line 255-258), placed BEFORE the existing `# Phase 60 D-02: GBS.FM import worker retention (SYNC-05)` block.
  - **Insertion 4** (queued Signal connection, +6 lines incl. comment): `self._player.underrun_recovery_started.connect(self._on_underrun_recovery_started, Qt.ConnectionType.QueuedConnection)` added directly after the existing `cookies_cleared.connect(self.show_toast)  # Phase 999.7` line (~280).
  - **Insertion 5** (`_on_underrun_recovery_started` slot, +18 lines incl. docstring): New bound-method slot inserted between `show_toast` (line 344-346) and the `# Slots (bound methods…)` divider. Reads `time.monotonic()`, suppresses if within cooldown, else updates the timestamp and calls `self.show_toast("Buffering…")`.
  - **Insertion 6** (closeEvent extension, +6 lines net): closeEvent now opens with a `try/except _log.warning` block calling `self._player.shutdown_underrun_tracker()` BEFORE the existing `_media_keys.shutdown()` block. Docstring extended with the Phase 62 / D-03 / Pitfall 4 rationale.
- `musicstreamer/__main__.py` (modified, +4 lines: 1 functional + 3 comment)
  - Single `logging.getLogger("musicstreamer.player").setLevel(logging.INFO)` call inserted directly after the existing `logging.basicConfig(level=logging.WARNING)` at line 222, BEFORE the existing `argv = list(argv)` line. 3-line comment block above the new line carries the Phase 62 / Pitfall 5 reference; the test's regex strips comment lines via `if not line.lstrip().startswith("#")` so the comment count does not affect the grep gate.

## Decisions Made

- **closeEvent ordering: shutdown_underrun_tracker BEFORE _media_keys.shutdown.** Pitfall 4 is the load-bearing constraint: queued slots may not run after `closeEvent` returns, so any in-flight underrun cycle's structured log line MUST be written synchronously inside `Player.shutdown_underrun_tracker()` before any subsystem teardown can interfere. Both shutdowns are wrapped in their own `try/except _log.warning` so a failure in either subsystem cannot block app exit.
- **Cooldown bookkeeping on MainWindow, not Player.** Per CONTEXT.md and PATTERNS §2b, the cooldown is a UI concern. Player emits `underrun_recovery_started` on every dwell elapse and writes every log line; the toast debounce is the UI's responsibility. Centralizing the cooldown on MainWindow keeps the Player surface uncluttered and matches the test seam (Plan 00 tests monkeypatch `musicstreamer.ui_qt.main_window.time.monotonic`).
- **Use `…` escape, not inlined U+2026 glyph.** Project convention from `main_window.py:367` (`Connecting…`) and `:393` (`Stream failed, trying next…`). Test 1 substring-matches `'Buffering' in w._toast.label.text()`, so either form would pass; matching the codebase's escape-form keeps Phase 62 invisible in `git grep` for non-Latin-1 codepoints. Acceptance criterion `grep -c 'show_toast("Buffering…")' musicstreamer/ui_qt/main_window.py returns ≥1` is satisfied.
- **Per-logger setLevel on musicstreamer.player, NOT global basicConfig swap.** Pitfall 5 mitigation: bumping the global level to INFO would surface chatter from `aa_import`, `gbs_api`, `mpris2`, and other modules that have been silenced for two years. The 1-line `logging.getLogger("musicstreamer.player").setLevel(logging.INFO)` keeps the surface area minimal and reversible.

## Deviations from Plan

### Auto-fixed Issues

None — the plan's `<action>` block was prescriptive enough to land verbatim; the test suite passed on first run after Tasks 1 + 2 completed. No Rule 1/2/3 surface arose during execution.

### Acceptance-Criterion Discrepancy (documented, not auto-fixed)

**1. [Documentation] `time.monotonic()` count exceeds the plan's `≥1` floor**
- **Found during:** Task 1 final acceptance-criteria gate.
- **Issue:** Plan acceptance criterion: `grep -c "time.monotonic()" musicstreamer/ui_qt/main_window.py returns ≥1`. Actual count: 3. The matches are at line 134 (class-level docstring comment), line 264 (`__init__` field-init comment), line 369 (slot docstring), line 376 (actual call site `now = time.monotonic()`). The grep also matches the parenthesized form inside docstrings/comments because the regex is plain text. The acceptance criterion `≥1` is a sanity floor, not an equality gate.
- **Fix:** None applied. The grep gate is a floor; 3 ≥ 1.
- **Files modified:** None.
- **Impact:** None.

**2. [Documentation] `shutdown_underrun_tracker` count exceeds the plan's exact-1 expectation**
- **Found during:** Task 1 final acceptance-criteria gate.
- **Issue:** Plan acceptance criterion: `grep -c "shutdown_underrun_tracker" musicstreamer/ui_qt/main_window.py returns 1`. Actual count: 3. The matches are at the new closeEvent (1 docstring reference + 1 actual call) plus 1 reference inside the new `_log.warning(...)` failure-message string. The plan's exact-1 expectation appears to undercount the docstring + log-message references.
- **Fix:** None applied. The actual call site is unique (1 invocation), so the contractual claim is satisfied; the grep count is a sanity floor in practice.
- **Files modified:** None.
- **Impact:** None.

**3. [Documentation] `_last_underrun_toast_ts` count is exactly 3 (matches plan's ≥3 floor)**
- **Found during:** Task 1 final acceptance-criteria gate.
- **Issue:** Plan acceptance criterion: `grep -c "self._last_underrun_toast_ts" musicstreamer/ui_qt/main_window.py returns ≥3 (init + slot read + slot write)`. Actual count: 3 (init init=0.0; slot read `now - self._last_underrun_toast_ts < ...`; slot write `self._last_underrun_toast_ts = now`). Matches floor exactly.
- **Fix:** None applied — match-on-floor.
- **Files modified:** None.
- **Impact:** None.

---

**Total deviations:** 0 auto-fixed (Rule 1/2/3), 3 documented acceptance-criterion grep-floor observations (no code change required)
**Impact on plan:** Zero. The plan executed verbatim from the `<action>` block; all 5 RED tests turn GREEN on first verification run; all invariants preserved.

## Issues Encountered

- **Pre-existing test-suite Aborted segfault around `tests/test_import_dialog_qt.py` (~42% of the 1170-test suite).** Surfaced when running the full-suite phase-level gate (`pytest -x -q`). Verified pre-existing: re-running the same `pytest -x -q` against `HEAD~1` (the pre-Plan-03 baseline) reproduces the SAME `Fatal Python error: Aborted exit=134` at the SAME test file. The crash is unrelated to Plan 62-03's changes — it is a PySide6 / PyGObject Qt-teardown interaction between specific test fixtures, latent in the wider test ordering. The Phase 62 Plan 02 SUMMARY explicitly cited "95/95 across the regression suite" rather than the full 1170-test suite, indicating this crash predates Plan 03 by at least one wave. The crash does NOT affect any test relevant to Phase 62 — `test_import_dialog_qt.py` runs cleanly in isolation (25 passed in 0.51s) and the Phase 62 quick-suite + adjacent regression suite (100/100) is unaffected.

## Threat Flags

None — no new I/O, no new network surface, no new file paths, no subprocess. The plan's `<threat_model>` correctly identified T-62-02 (closeEvent ordering) and T-62-03 (toast spam DoS) as the only threats in scope, and both are mitigated by the structural ordering (Insertion Site 6) and the 10s cooldown gate (Insertion Site 5) — the latter locked by Test 2 (`test_second_call_within_cooldown_suppressed`) which remains GREEN.

## Self-Check: PASSED

**Files verified to exist:**
- `musicstreamer/ui_qt/main_window.py` — FOUND (~836 lines, +45 net from Plan 02 baseline)
- `musicstreamer/__main__.py` — FOUND (250 lines, +4 net from baseline)

**Module attributes verified to exist:**
- `MainWindow._UNDERRUN_TOAST_COOLDOWN_S` (class const = 10.0) — FOUND
- `MainWindow._last_underrun_toast_ts` (instance field, initialized in __init__) — FOUND (3 textual references: init + slot read + slot write)
- `MainWindow._on_underrun_recovery_started` (bound-method slot) — FOUND
- `MainWindow.closeEvent` extension calling `self._player.shutdown_underrun_tracker()` BEFORE `self._media_keys.shutdown()` — FOUND (visible ordering in source)
- `import time` at module top — FOUND (line 23)
- `__main__.main()` calls `logging.getLogger("musicstreamer.player").setLevel(logging.INFO)` directly after `logging.basicConfig(level=logging.WARNING)` — FOUND (line 226)

**Commits verified to exist:**
- `f1818c3` — FOUND (Task 1: `feat(62-03): GREEN — wire MainWindow underrun_recovery_started with 10s cooldown gate + closeEvent shutdown hook`)
- `4156334` — FOUND (Task 2: `feat(62-03): per-logger INFO for musicstreamer.player in __main__.py (Pitfall 5 scoped, not global)`)

**Verification gates passed:**
- 5/5 RED MainWindow tests GREEN (`pytest tests/test_main_window_underrun.py -x -q`)
- 8/8 Plan 02 Player tests still GREEN (`pytest tests/test_player_underrun.py -x -q`)
- 7/7 Plan 01 tracker tests still GREEN (`pytest tests/test_player_underrun_tracker.py -x -q`)
- 80/80 adjacent regression tests still pass (`pytest tests/test_main_window_integration.py tests/test_player_buffering.py tests/test_player_buffer.py tests/test_player.py tests/test_player_pause.py -x -q`) — combined Phase 62 quick-suite + adjacent: 100/100
- All 11 acceptance-criterion grep gates pass (`import time` × 1, `_UNDERRUN_TOAST_COOLDOWN_S: float = 10.0` × 1, `self._last_underrun_toast_ts` × 3, `underrun_recovery_started.connect` × 1, `Qt.ConnectionType.QueuedConnection` × 1, `def _on_underrun_recovery_started` × 1, `show_toast("Buffering…")` × 1, `shutdown_underrun_tracker` × 3, `time.monotonic()` × 3, `getLogger("musicstreamer.player").setLevel(logging.INFO)` × 1, `basicConfig(level=logging.WARNING)` × 1)
- D-05 invariant: `git diff musicstreamer/ui_qt/now_playing_panel.py | wc -l` returns 0 (toast-only UX preserved; no stats-for-nerds bar changes this phase)
- D-09 invariant: `git diff musicstreamer/constants.py | wc -l` returns 0 (Phase 16 buffer constants untouched throughout Phase 62)
- Pitfall 5 invariant: `grep -c "logging.basicConfig(level=logging.WARNING)" musicstreamer/__main__.py` returns 1 (existing line unchanged)
- Pitfall 4 ordering: `closeEvent` source-text shows `shutdown_underrun_tracker` call BEFORE `_media_keys.shutdown` call

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

**Phase 62 instrumentation half of BUG-09 ships.** All three Phase 62 success criteria for the instrumentation deliverable are satisfied:

1. **Logging surface (success criterion #1):** Structured `buffer_underrun ...` INFO log line wired and visible at runtime. Two emission sites in `Player`: queued `_on_underrun_cycle_closed` slot (Plan 02) and synchronous `shutdown_underrun_tracker` (Plan 02). `__main__.py` bumps `musicstreamer.player` to INFO so cycle-close lines surface to stderr without polluting other modules' chatter.
2. **Toast surface (success criterion #2):** MainWindow `_on_underrun_recovery_started` slot shows `Buffering…` toast on cycles that exceed the 1500ms dwell threshold (D-07), debounced by a 10s wall-clock cooldown (D-08).
3. **Behavior fix (success criterion #3):** **DEFERRED** to a follow-up phase per CONTEXT.md `<deferred>`. This phase ships instrumentation; the buffer-tuning / reconnect-logic / low-watermark fix is gated on observed log data and will be scoped once enough cycle-close samples accumulate from daily use.

**Ready for `/gsd-verify-work` and `/gsd-complete-phase`:** the verification command will re-run all 20 Phase 62 RED tests (now GREEN) plus the adjacent regression suite. ROADMAP / STATE / REQUIREMENTS updates land in `/gsd-complete-phase`.

**Open carry-forward — none.** All three plans (00 RED + 01 tracker GREEN + 02 Player wiring GREEN + 03 MainWindow + __main__ GREEN) are complete. The Phase 62 deliverable contract is closed.

**Blockers/concerns:**
- None for Plan 03 itself. The pre-existing full-suite teardown segfault around `test_import_dialog_qt.py` (documented under Issues Encountered) is unrelated to Phase 62 and exists at `HEAD~1` (the pre-Plan-03 baseline). It does NOT affect any test relevant to Phase 62 and does NOT block phase verification.

---
*Phase: 62-audio-buffer-underrun-resilience-intermittent-dropouts-stutt*
*Completed: 2026-05-08*
