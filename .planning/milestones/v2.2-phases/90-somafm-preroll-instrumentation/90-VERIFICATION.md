---
phase: 90-somafm-preroll-instrumentation
verified: 2026-06-18T19:23:04Z
status: passed
human_uat: passed 2026-06-18 — user confirmed audible preroll on bind (Boot Liquor + others previously missing now play) + random rotation; no station truly broken → Phase 90b not needed
score: 9/9 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Manual all-stations SomaFM run-through"
    expected: "Every SomaFM station that has prerolls in the DB plays an audible preroll on first bind (within a fresh launch); preroll-events.log contains a preroll_start entry for each such station with a real .m4a URL; Boot Liquor in particular plays a preroll (5 preroll rows confirmed in DB as of 2026-06-18)"
    why_human: "Audible playback + network reachability of the upstream .m4a URLs cannot be verified programmatically; GStreamer pipeline must be live; this is the SOMA-PRE-04 verify-half acceptance evidence — it is user-owned by design (90-CONTEXT.md)"
  - test: "'Open preroll log' action opens log in OS default viewer"
    expected: "After playing a SomaFM station (which creates preroll-events.log), clicking 'Open preroll log' opens the file in the system text viewer / log viewer; file contains structured INFO lines with timestamps"
    why_human: "QDesktopServices.openUrl is wired correctly (grep-verified, test_open_preroll_log_absent_shows_toast passes), but the live OS file-open behaviour requires a running desktop session to observe"
  - test: "'Re-fetch SomaFM prerolls' toasts outcome correctly"
    expected: "Clicking 'Re-fetch SomaFM prerolls' when some SomaFM stations have zero prerolls shows 'Re-fetching SomaFM prerolls...' then 'Prerolls refreshed for N station(s)' (or the no-new-prerolls variant); double-clicking while in-flight shows 'Re-fetch already in progress'"
    why_human: "The worker is wired and pattern-4 discipline verified; toast content and timing require a live Qt event loop with a real DB"
---

# Phase 90: SomaFM Preroll Instrumentation Verification Report

**Phase Goal:** Wire a non-destructive structured preroll event log (`musicstreamer/preroll_log.py`) + an "Open preroll log" hamburger action + a prerolls re-fetch lever (manual "Re-fetch SomaFM prerolls" menu action AND automatic staleness re-fetch), with ZERO behavior change to the existing preroll/buffer paths — so the user can verify (via a manual all-stations run-through) that the already-resolved Boot Liquor missing-preroll symptom stays fixed and is recoverable.
**Verified:** 2026-06-18T19:23:04Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `musicstreamer/preroll_log.py` installs an idempotent INFO RotatingFileHandler on `musicstreamer.preroll` logger writing to `preroll-events.log` (SOMA-PRE-01) | VERIFIED | File exists, 71 lines, `install_preroll_events_handler()` present with `log.setLevel(logging.INFO)`, idempotency loop on `baseFilename`, `propagate` left at default True |
| 2 | `paths.preroll_events_log_path()` resolves to `{data_root}/preroll-events.log` and honors `_root_override` for test isolation (D-04) | VERIFIED | `paths.py` line 73: `def preroll_events_log_path()` returns `os.path.join(_root(), "preroll-events.log")`; 7/7 path tests pass |
| 3 | Handler installs once (idempotent) at startup after migration, mirroring buffer_log (D-03) | VERIFIED | `__main__.py` lines 269-270: import and call after `run_migration()` (line 250 / 98) and after `install_buffer_events_handler()` (line 261) |
| 4 | Five preroll event log calls wired at gate + handoff with zero behavior change (SOMA-PRE-01, D-10) — `preroll_start`, `preroll_skipped_throttle`, `preroll_skipped_empty` (x2), `preroll_handoff_complete` | VERIFIED | All 5 event names present in `player.py` at lines 764, 777, 789, 801, 1627; all are pure `.info()` calls with no `set_property`; Phase 84 D-11 buffer-duration→uri ordering untouched (buffer apply at line 1685, set_property at 1692, log at 1627); `random.choice(urls)` at line 776 unchanged (D-06) |
| 5 | D-08 auto-staleness re-fetch fires only for fetched-with-0 stations older than 7 days, mutually exclusive with D-13 unfetched branch (SOMA-PRE-04 recovery) | VERIFIED | `_PREROLL_STALE_THRESHOLD_S = 7 * 24 * 3600` at player.py:88; D-08 branch at lines 809-819 inside the `else:` (fetched-empty branch) guarded by `prerolls_fetched_at is not None AND age > threshold AND not in_flight`; structurally mutually exclusive with D-13 branch which requires `prerolls_fetched_at IS None` |
| 6 | Phase 84 D-11 buffer-ordering preserved — 17 test buffer growth suite GREEN (SOMA-PRE-05) | VERIFIED | `.venv/bin/python -m pytest tests/test_player_buffer_growth.py -q` → **17 passed** |
| 7 | Hamburger menu gains "Open preroll log" action with existence-guard toast and QUrl.fromLocalFile (SOMA-PRE-02, D-05) | VERIFIED | `main_window.py` line 363 (action wired), line 1703 (`os.path.isfile` guard), line 1706 (`QUrl.fromLocalFile`); 2 UI tests green |
| 8 | Hamburger menu gains "Re-fetch SomaFM prerolls" action backed by `_PrerollRefetchWorker` (Pattern 4, SYNC-05 double-click guard, scheme-validated inserts) (SOMA-PRE-06, D-07) | VERIFIED | `_PrerollRefetchWorker` at line 177; `db_connect()` inside `run()` at line 202, `con.close()` in `finally` at line 237; `insert_preroll` exclusively (no raw SQL); `_soma_refetch_worker is not None` guard at line 1718; 14/14 main_window_soma tests pass |
| 9 | SOMA-PRE-03 (30s network probe) is DEFERRED and NOT present in any Phase 90 file | VERIFIED | No `requests` import, no `preroll-probe.log` reference in any Phase 90 file; REQUIREMENTS.md line 94 marks SOMA-PRE-03 as `DEFERRED to Phase 90b`; 90-CONTEXT.md documents deferral under D-01 |

**Score:** 9/9 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/preroll_log.py` | `install_preroll_events_handler()` — RotatingFileHandler on `musicstreamer.preroll` | VERIFIED | 71 lines, substantive implementation; idempotency, setLevel(INFO), format |
| `musicstreamer/paths.py` | `preroll_events_log_path()` path helper | VERIFIED | Line 73, mirrors `buffer_events_log_path()` at line 68 |
| `musicstreamer/__main__.py` | `install_preroll_events_handler()` called post-migration | VERIFIED | Lines 269-270, after `run_migration()` at line 250/98 |
| `musicstreamer/player.py` | 5 additive log calls + `_PREROLL_STALE_THRESHOLD_S` + D-08 branch | VERIFIED | Constant at line 88; 5 event names confirmed; D-08 branch lines 809-819 |
| `musicstreamer/ui_qt/main_window.py` | `_PrerollRefetchWorker` + 2 hamburger actions + handlers + `_soma_refetch_worker` field | VERIFIED | All components present; Pattern 4 discipline confirmed |
| `tests/test_preroll_events_log.py` | 5-test mirror of `test_buffer_events_log.py` | VERIFIED | 5 tests, all GREEN |
| `tests/test_paths.py` | 2 new preroll path tests | VERIFIED | Both GREEN (7 passed including 2 new) |
| `tests/test_player.py` | 7 new tests: 4 log-emission + 3 staleness | VERIFIED | 32 passed including all new tests |
| `tests/test_main_window_soma.py` | 4 new tests (2 open-log + 2 refetch) | VERIFIED | 14 passed (8 pre-existing + 4 new + 2 additional pre-existing) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `musicstreamer/preroll_log.py` | `musicstreamer/paths.py` | `paths.preroll_events_log_path()` | WIRED | Line 57 calls `paths.preroll_events_log_path()` |
| `musicstreamer/__main__.py` | `musicstreamer/preroll_log.py` | `install_preroll_events_handler()` called post-migration | WIRED | Lines 269-270, after `run_migration()` |
| `musicstreamer/player.py` | `musicstreamer.preroll` logger | `logging.getLogger("musicstreamer.preroll").info(...)` at gate + handoff | WIRED | 5 call sites verified at lines 764, 777, 789, 801, 1627 |
| `player.py` D-08 fetched-empty branch | `self._preroll_backfill_worker` | staleness threading.Thread | WIRED | Lines 809-819, `_PREROLL_STALE_THRESHOLD_S` gated |
| `main_window.py` "Open preroll log" action | `paths.preroll_events_log_path()` | `QDesktopServices.openUrl(QUrl.fromLocalFile(...))` with `os.path.isfile` guard | WIRED | Lines 1698-1706 |
| `main_window.py` "Re-fetch SomaFM prerolls" action | `soma_import.fetch_channels` + `repo.insert_preroll` | `_PrerollRefetchWorker(QThread).run()` Pattern 4 | WIRED | Lines 177-237, confirmed with `db_connect()` + `con.close()` in `finally` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `preroll_log.py` | log records | `logging.getLogger("musicstreamer.preroll").info(...)` calls in player.py | Yes — direct logger calls from decision points | FLOWING |
| `player.py` D-08 branch | `station.prerolls_fetched_at` | in-memory station object populated from DB (Pitfall 2 — no hot-path DB read) | Yes — real station attribute | FLOWING |
| `_PrerollRefetchWorker.run()` | `channels` | `soma_import.fetch_channels()` — real upstream API call | Yes — live SomaFM channels.json | FLOWING |
| `_on_open_preroll_log_clicked` | `log_path` | `paths.preroll_events_log_path()` + `os.path.isfile` | Yes — real filesystem path | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| preroll_log substrate (5 tests) | `.venv/bin/python -m pytest tests/test_preroll_events_log.py -q` | 5 passed | PASS |
| Path helper (preroll path tests) | `.venv/bin/python -m pytest tests/test_paths.py -k preroll -q` | 7 passed, 12 deselected | PASS |
| Phase 84 D-11 buffer regression gate (17 tests, SOMA-PRE-05) | `.venv/bin/python -m pytest tests/test_player_buffer_growth.py -q` | **17 passed** | PASS |
| Player preroll/throttle/drift_guard/staleness (32 tests) | `.venv/bin/python -m pytest tests/test_player.py -k "preroll or throttle or drift_guard or staleness" -q` | 32 passed, 27 deselected | PASS |
| SomaFM hamburger UI suite (14 tests) | `.venv/bin/python -m pytest tests/test_main_window_soma.py -q` | 14 passed | PASS |
| Separator count (Phase 90 change at 5) | `.venv/bin/python -m pytest tests/test_main_window_integration.py::test_hamburger_menu_separators -q` | 1 passed | PASS |
| Pre-existing failure (not attributed to Phase 90) | `.venv/bin/python -m pytest tests/test_main_window_integration.py::test_hamburger_menu_actions -q` | 1 failed — stale `EXPECTED_ACTION_TEXTS` missing Phase 74 "Import SomaFM"; pre-dates Phase 90 baseline | KNOWN PRE-EXISTING |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SOMA-PRE-01 | Plans 01, 02 | `preroll_log.py` mirrors `buffer_log.py`; wired at `_try_next_stream` + `_on_preroll_about_to_finish` with NO behavior change | SATISFIED | `preroll_log.py` substantive; 5 event names in player.py; 17 buffer-growth tests still pass |
| SOMA-PRE-02 | Plan 03 | Hamburger-menu "Open preroll log" entry | SATISFIED | Action at `main_window.py` line 363; `os.path.isfile` guard + `QUrl.fromLocalFile`; 2 tests green |
| SOMA-PRE-03 | (DEFERRED) | 30s network probe — DEFERRED to Phase 90b per D-06 / 90-CONTEXT.md | DEFERRED — documented | REQUIREMENTS.md line 94 marks as `DEFERRED to Phase 90b`; no probe code in any Phase 90 file |
| SOMA-PRE-04 | Plans 01, 02 | Verify-half: structured log + user manual all-stations run-through | SATISFIED (automated half) / HUMAN-NEEDED (verify half) | Log substrate wired; D-08 auto-staleness closes fetched-with-0 trap; manual run-through is a user-owned action classified as human_verification |
| SOMA-PRE-05 | Plan 02 | Instrumentation MUST NOT regress Phase 84 buffer adaptation | SATISFIED | 17/17 `test_player_buffer_growth.py` tests pass; `preroll_handoff_complete` log at line 1627 is before `_apply_pending_buffer_duration_to_pipeline` at line 1685 and `set_property("uri", ...)` at line 1692 |
| SOMA-PRE-06 | Plan 03 | Re-fetch lever: manual hamburger action + auto-staleness D-08 | SATISFIED | Manual: `_PrerollRefetchWorker` wired; Auto: `_PREROLL_STALE_THRESHOLD_S` + D-08 branch in player.py |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none in Phase 90 code) | — | No TBD/FIXME/XXX/placeholder in Phase 90 introduced lines | — | Clean |

**Debt-marker gate:** PASS — no unreferenced TBD/FIXME/XXX markers found in any Phase 90 modified file.

**Code review findings already incorporated:** WR-01 (`set_prerolls_fetched_at` called unconditionally for genuinely-empty channels), WR-02 (`updated += 1` gated on `inserted_any`), and WR-03 (cross-thread `discard` contract documented at `player.py:2096-2104`) were all addressed in commit `a4bfed15` / the codebase as verified. Review warnings are resolved; review info items (IN-01 through IN-04) are informational quality items with no functional impact.

### Human Verification Required

#### 1. Manual all-stations SomaFM run-through (SOMA-PRE-04 verify-half)

**Test:** Launch the app fresh. Cycle through every SomaFM station listed in the app. For each station that has prerolls in the DB, observe that an audible preroll plays before the main stream. Open `~/.local/share/musicstreamer/preroll-events.log` after the run and confirm each station's `preroll_start` entry includes a real `bootliquor/*.m4a`-style URL.
**Expected:** Boot Liquor (5 preroll rows as of 2026-06-18) plays an audible preroll; the log shows `preroll_start` with a real upstream URL; stations with zero prerolls show `preroll_skipped_empty reason=unfetched` (triggering D-13 backfill) or `reason=fetched_empty`; no station that should have prerolls silently skips them.
**Why human:** Audible playback and network reachability of upstream `.m4a` URLs cannot be verified programmatically. GStreamer pipeline must be live. This is the explicitly user-owned acceptance gate defined in 90-CONTEXT.md and SOMA-PRE-04.

#### 2. "Open preroll log" opens the file in OS viewer

**Test:** After playing at least one SomaFM station (to create `preroll-events.log`), open the hamburger menu and click "Open preroll log".
**Expected:** The OS default text/log viewer opens `preroll-events.log` showing timestamped structured lines (e.g. `2026-06-18 … preroll_start station_name=…`). Before the file exists, clicking the action shows the toast "No preroll log yet — play a SomaFM station first" with no file viewer opening.
**Why human:** `QDesktopServices.openUrl` is wired and the existence-guard is grep-verified; the live OS file-open behavior requires a running desktop session and a real `preroll-events.log` on disk.

#### 3. "Re-fetch SomaFM prerolls" toasts correct outcome and double-click guard works

**Test:** With one or more SomaFM stations having zero prerolls, click "Re-fetch SomaFM prerolls". Then immediately click it again before it finishes.
**Expected:** First click toasts "Re-fetching SomaFM prerolls…" then completes with "Prerolls refreshed for N station(s)" (or "Re-fetch: no new prerolls found" if none needed updating). Second click while running toasts "Re-fetch already in progress" and does not start a second worker.
**Why human:** Worker execution, toast sequencing, and double-click guard behavior require a live Qt event loop with a real DB and real network access.

---

## Gaps Summary

No automated gaps. All 9 must-haves are VERIFIED against the codebase. The three human verification items reflect the explicitly user-owned nature of SOMA-PRE-04 (audible confirmation of preroll playback) and the live-session-dependent behaviors of `QDesktopServices.openUrl` and the Qt worker toast flow. These are not blockers — the code is wired correctly; they simply require a human with a running app to confirm the end-to-end user experience.

The pre-existing `test_hamburger_menu_actions` failure is unrelated to Phase 90: it fails because `EXPECTED_ACTION_TEXTS` was never updated for the Phase 74 "Import SomaFM" entry. Phase 90's separator count change was separately fixed (`test_hamburger_menu_separators` passes at 5).

---

_Verified: 2026-06-18T19:23:04Z_
_Verifier: Claude (gsd-verifier)_
