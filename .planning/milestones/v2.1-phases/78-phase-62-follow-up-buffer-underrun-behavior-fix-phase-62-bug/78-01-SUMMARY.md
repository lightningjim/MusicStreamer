---
phase: 78-phase-62-follow-up-buffer-underrun-behavior-fix-phase-62-bug
plan: 01
subsystem: infra
tags: [logging, rotating-file-handler, buffer-underrun, bug-09, phase-62-followup, harvest-infra]

requires:
  - phase: 62-audio-buffer-underrun-resilience-intermittent-dropouts-stutt
    provides: musicstreamer.player logger with INFO-level buffer_underrun records; _on_underrun_cycle_closed slot at player.py:918
provides:
  - musicstreamer/buffer_log.py with idempotent install_buffer_events_handler()
  - paths.buffer_events_log_path() helper returning {data_dir}/buffer-events.log
  - boot-time install call wired into _run_gui post-migration
  - 6 unit tests covering handler attach, emit, rotation (1MB cap, backup .4 never created), idempotency, propagate=True invariant
  - 2 new path-helper tests + 2 existing tests extended (root-override + no-IO-on-import)
affects:
  - Phase 78 Commit B (behavior-fix plans, deferred until ~1-week harvest week completes)
  - Phase 78-02 (Player counter + Signal — Wave 0 dependency on this file sink for harvest data)
  - Phase 78-03 (UI row — Wave 0 dependency on this file sink)

tech-stack:
  added: []
  patterns:
    - "RotatingFileHandler on a named logger with propagate=True (sibling to oauth_log.py, but stderr-parity preserved)"
    - "Idempotent handler install via baseFilename match before addHandler (Pitfall 7)"
    - "Per-test process-global logger handler snapshot + level restore fixture (mirror of paths._reset_root_override)"

key-files:
  created:
    - musicstreamer/buffer_log.py
    - tests/test_buffer_events_log.py
    - .planning/phases/78-phase-62-follow-up-buffer-underrun-behavior-fix-phase-62-bug/78-01-SUMMARY.md
  modified:
    - musicstreamer/paths.py
    - musicstreamer/__main__.py
    - tests/test_paths.py

key-decisions:
  - "D-02 honored verbatim: RotatingFileHandler(maxBytes=1_048_576, backupCount=3, encoding='utf-8') on the named musicstreamer.player logger only — never musicstreamer.*"
  - "D-03 honored: no credential-grade chmod on buffer-events.log (deliberate departure from oauth_log.py's 0o600 — diagnostic data, not credentials)"
  - "Pitfall 1 honored: install call sits in _run_gui AFTER migration.run_migration() so DATA_DIR exists before RotatingFileHandler opens eagerly; install NOT placed in main()"
  - "Pitfall 5 honored: basicConfig(level=logging.WARNING) at __main__.py:242 byte-identical; per-logger setLevel(INFO) at line 246 unchanged; named-logger attach preserves stderr parity via propagate=True (default)"
  - "Pitfall 7 honored: install_buffer_events_handler() iterates log.handlers and short-circuits when an existing RotatingFileHandler matches paths.buffer_events_log_path()"
  - "Formatter chosen: %(asctime)s %(message)s — each file line is independently date-stampable (RESEARCH Open Q1 resolution)"
  - "Per-test autouse fixture _clean_player_handlers snapshots logger handlers + level — mirrors tests/test_paths.py:_reset_root_override; sets level to INFO during the test to match production wiring at __main__.main()"

patterns-established:
  - "Pattern: helper module install function (not class) for boot-time RotatingFileHandler attach — pairs with sibling oauth_log.py but installs a singleton on a shared logger rather than a per-instance unique logger"
  - "Pattern: idempotent named-logger handler install via baseFilename match — reusable shape for any future diagnostic file sink that lives alongside an existing stderr handler"
  - "Pattern: per-test logger handler snapshot/restore fixture — necessary whenever tests attach handlers to a process-global named logger"

requirements-completed: [BUG-09]

duration: 4m 26s
completed: 2026-05-18
---

# Phase 78 Plan 01: Buffer-event file sink (Commit A harvest infra) Summary

**Idempotent RotatingFileHandler on musicstreamer.player logger writing Phase 62 buffer_underrun INFO lines to ~/.local/share/musicstreamer/buffer-events.log, wired post-migration so DATA_DIR is guaranteed to exist; stderr parity preserved via propagate=True so the existing Pitfall-5 invariant holds byte-identical.**

## Performance

- **Duration:** 4m 26s
- **Started:** 2026-05-18T00:39:59Z
- **Completed:** 2026-05-18T00:44:25Z
- **Tasks:** 3
- **Files modified/created:** 5 (3 new — buffer_log.py, test_buffer_events_log.py, SUMMARY.md; 3 modified — paths.py, __main__.py, test_paths.py)

## Accomplishments

- `musicstreamer/buffer_log.py` ships with a single public function `install_buffer_events_handler()` that attaches a `RotatingFileHandler(maxBytes=1_048_576, backupCount=3, encoding="utf-8")` to the `musicstreamer.player` logger, idempotently and only after migration has guaranteed DATA_DIR exists.
- `paths.buffer_events_log_path()` is the single source of truth for the file path; honors `_root_override` test hook automatically via the existing `_root()` route.
- `__main__._run_gui` now invokes the install function immediately after `migration.run_migration()` returns, before the `QApplication` import block. The Pitfall-5 drift-guard `test_main_module_sets_player_logger_to_info` stays green — `basicConfig(level=logging.WARNING)` at line 242 and the per-logger `setLevel(INFO)` at line 246 are byte-identical to their pre-phase form.
- 8 new tests across `tests/test_buffer_events_log.py` (6) and `tests/test_paths.py` (2 new + 2 extended) cover behavior IDs B-78A-01..06; B-78A-13 drift-guard remains green (the install call lives in `_run_gui`, never in `main()`).

## Task Commits

Each task was committed atomically:

1. **Task 1: paths.buffer_events_log_path() + tests** — `d0c6898` (feat)
2. **Task 2: musicstreamer/buffer_log.py + tests** — `ddec98a` (feat)
3. **Task 3: install call wired into _run_gui** — `54376f6` (feat)

## Files Created/Modified

- `musicstreamer/buffer_log.py` (NEW, 66 lines) — Idempotent `install_buffer_events_handler()` attaches RotatingFileHandler to musicstreamer.player logger at `paths.buffer_events_log_path()`. Pitfall 7 idempotency via baseFilename match. D-02 rotation params. D-03 default perms (no chmod).
- `musicstreamer/paths.py` (MODIFIED, +5 lines) — Sibling helper `buffer_events_log_path() -> str` returning `{_root()}/buffer-events.log`. Pure; no I/O; honors `_root_override`.
- `musicstreamer/__main__.py` (MODIFIED, +11 lines) — Lazy import + call in `_run_gui` immediately after `migration.run_migration()` and before `from PySide6.QtWidgets import QApplication`. Comment block tags Pitfall 1 (DATA_DIR ordering), Pitfall 5 (stderr parity), and idempotency. No changes to `basicConfig(WARNING)` or per-logger `setLevel(INFO)` in `main()`.
- `tests/test_paths.py` (MODIFIED, +14 lines) — Added `test_buffer_events_log_path` + `test_buffer_events_log_path_does_not_create_file` sibling tests; extended `test_root_override_redirects_all_accessors` and `test_paths_do_no_io_on_import` to include the new accessor.
- `tests/test_buffer_events_log.py` (NEW, 140 lines) — 6 tests covering B-78A-01..05: handler attach + maxBytes/backupCount/baseFilename assertions, INFO emit reaches file, rotation produces `.1` at >1MB, `.4` never created (backupCount=3 cap), idempotency (single handler after two installs), and propagate=True invariant (record reaches file sink + propagate path intact for root stderr handler). Autouse `_clean_player_handlers` fixture snapshots/restores handlers + level (process-global hygiene).

## Decisions Made

- **Formatter choice:** `%(asctime)s %(message)s` (RESEARCH Open Question 1, resolution). Each file line is independently date-stampable; redundant with in-line `start_ts=%.3f` but cheap and useful for the harvest analysis.
- **Logger level handling in tests:** the autouse fixture sets `musicstreamer.player` level to INFO during the test and restores after — mirrors production wiring (`__main__.main()` does the same). Without it, INFO records would be filtered at the logger level before reaching the new handler. This is a test-environment concern, not a behavior of the install function (which intentionally leaves `setLevel` untouched per Pitfall 5).
- **Propagate-sanity test contract (B-78A-05):** test asserts `propagate=True` attribute introspection rather than depending on `capsys`/`caplog` to capture stderr from `basicConfig`. The plan action explicitly directs this — pytest's caplog may replace the basicConfig StreamHandler in some configurations, so direct attribute assertion is the reliable contract test.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Adjusted `_clean_player_handlers` autouse fixture to also set logger level to INFO during the test**

- **Found during:** Task 2 (initial test run after `test_emit_writes_line_to_file`)
- **Issue:** With only the handler attached but no level set on `musicstreamer.player`, the logger inherits root WARNING and the INFO record is filtered at the logger level before reaching the file handler. The first test run produced an empty file and the emit assertion failed (`assert 'buffer_underrun' in ''`).
- **Fix:** Extended the autouse fixture to snapshot `log.level`, set it to `logging.INFO` during the test, and restore on teardown. Mirrors production wiring at `__main__.main()` where `logging.getLogger("musicstreamer.player").setLevel(logging.INFO)` is set globally.
- **Files modified:** `tests/test_buffer_events_log.py` (fixture body only — public test assertions unchanged)
- **Verification:** All 6 tests green after the fix; oauth_log regression suite still green.
- **Committed in:** `ddec98a` (Task 2 commit — fixture change landed before commit)

**2. [Rule 2 - Missing Critical] Removed literal `0o600` from buffer_log.py docstring to satisfy acceptance-criteria grep gate**

- **Found during:** Task 2 acceptance criteria verification (`grep -c "0o600" musicstreamer/buffer_log.py` returned 1, expected 0)
- **Issue:** The module docstring originally said "uses default permissions (no `0o600` chmod — diagnostic data, not credentials)" — which is exactly what the design intends, but the literal `0o600` token tripped the grep gate intended to prevent accidental credential-grade chmod calls.
- **Fix:** Rephrased to "uses default permissions (no credential-grade chmod — diagnostic data, not credentials; deliberate departure from oauth_log.py's tightening pattern)" — preserves the semantic warning without the literal token.
- **Files modified:** `musicstreamer/buffer_log.py` (docstring only — no behavior change)
- **Verification:** Grep gate now returns 0; tests still pass.
- **Committed in:** `ddec98a` (Task 2 commit — landed before commit was created)

---

**Total deviations:** 2 auto-fixed (1 bug in test fixture, 1 minor doc/grep alignment)
**Impact on plan:** Both auto-fixes were trivial and preserved all behavioral contracts. No scope creep; no architectural changes required.

## Issues Encountered

None beyond the auto-fixed items above. All three tasks executed in their planned order with no checkpoint pauses required.

## User Setup Required

None — no external service configuration, no new dependencies installed, no manual steps. The harvest week itself is a manual UAT step covered by `78-VALIDATION.md` `<manual-only-verifications>` — it begins automatically the next time the user launches the app in daily use.

## Next Phase Readiness

- Plan 78-02 (Player counter + Signal) Wave-0 ready — the file sink it depends on is shipping in this plan.
- Plan 78-03 (UI row + MainWindow wiring) Wave-0 ready — same dependency.
- Phase 78 Commit B (behavior-fix planning pass, deferred per D-01 until ~1 week of harvest data accumulates) — no work required from this plan beyond enabling the harvest.

## Self-Check: PASSED

**Created files exist:**
- FOUND: `musicstreamer/buffer_log.py`
- FOUND: `tests/test_buffer_events_log.py`
- FOUND: `.planning/phases/78-phase-62-follow-up-buffer-underrun-behavior-fix-phase-62-bug/78-01-SUMMARY.md` (this file)

**Modified files exist:**
- FOUND: `musicstreamer/paths.py` (buffer_events_log_path helper present at line 68)
- FOUND: `musicstreamer/__main__.py` (install_buffer_events_handler call at line 188)
- FOUND: `tests/test_paths.py` (4 buffer_events_log_path references)

**Commits exist:**
- FOUND: `d0c6898` (Task 1)
- FOUND: `ddec98a` (Task 2)
- FOUND: `54376f6` (Task 3)

**Behavior IDs satisfied:**
- B-78A-01..05 covered by `tests/test_buffer_events_log.py` (6 tests, all green)
- B-78A-06 covered by `tests/test_paths.py::test_buffer_events_log_path` + `test_buffer_events_log_path_does_not_create_file` (green)
- B-78A-13 drift-guard `test_main_window_underrun.py::test_main_module_sets_player_logger_to_info` (green — Pitfall 5 invariant preserved)

---
*Phase: 78-phase-62-follow-up-buffer-underrun-behavior-fix-phase-62-bug*
*Completed: 2026-05-18*
