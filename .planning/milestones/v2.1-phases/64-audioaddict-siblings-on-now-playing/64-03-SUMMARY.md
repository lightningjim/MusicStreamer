---
phase: 64-audioaddict-siblings-on-now-playing
plan: 03
subsystem: ui
tags: [pyside6, signal-slot, main-window, audioaddict, sibling-link, integration-test, phase-51-followup, qa-05, bound-method]

# Dependency graph
requires:
  - phase: 51-audioaddict-cross-network-siblings
    provides: _on_navigate_to_sibling structural precedent at main_window.py:482-500 (the slot Phase 64 INVERTS for playback-touching semantics)
  - phase: 64-audioaddict-siblings-on-now-playing
    provides: Plan 64-02 NowPlayingPanel.sibling_activated = Signal(object) + _on_sibling_link_activated panel-side handler — both pre-existing at this worktree's base
provides:
  - MainWindow.now_playing.sibling_activated.connect(self._on_sibling_activated) — bound-method per QA-05 (no lambda)
  - MainWindow._on_sibling_activated(station: Station) — one-line delegating slot to _on_station_activated
  - tests/test_main_window_integration.py::test_sibling_click_switches_playback_via_main_window — end-to-end integration test asserting Player.play(sibling) + Repo.update_last_played(sibling.id) + panel re-bind on sibling click (the SC #2 contract)
  - Phase 64 BUG-02 closure: clicking an 'Also on:' link in NowPlayingPanel switches active playback (the user-visible promise of the phase)
affects: [phase-64-verification, future-phase-any-now-playing-extension]

# Tech tracking
tech-stack:
  added: []  # No new libraries — pure PySide6 Signal/Slot wiring
  patterns:
    - "Bound-method signal connect (QA-05): no self-capturing lambda"
    - "Delegating slot pattern: _on_sibling_activated → _on_station_activated (single canonical side-effect block fires regardless of activation source)"
    - "Phase 64 vs Phase 51 inversion: panel-side click DOES change playback (Phase 64); dialog-side navigate does NOT (Phase 51) — same shape, opposite semantic"
    - "Connection ordering invariant: signal connects land AFTER widget construction and adjacent to related connects (RESEARCH Pitfall #4)"

key-files:
  created: []
  modified:
    - musicstreamer/ui_qt/main_window.py
    - tests/test_main_window_integration.py

key-decisions:
  - "Delegating slot (D-02 default): _on_sibling_activated has a one-line body that calls self._on_station_activated(station). Single source of truth for activation side-effects (bind_station + Player.play + update_last_played + refresh_recent + toast + media-keys publish/state) — no risk of drift between station-list activation and sibling-click activation."
  - "Connection lands at line 253, immediately after the existing now_playing.edit_requested connect and before station_panel.edit_requested. Keeps related now_playing-* connects clustered; lands AFTER self.now_playing is constructed (RESEARCH Pitfall #4) and BEFORE the Phase 41 media-keys block at line ~272."
  - "Bound-method connect (QA-05) — no lambda. The plan body explicitly forbids lambdas; the acceptance grep `grep \"sibling_activated.connect\" main_window.py | grep -v lambda | grep -v \"#\"` confirms compliance."
  - "Toast wording inherited from _on_station_activated as 'Connecting…' (U+2026). RESEARCH Open Question #1 resolved per D-02 default — no separate 'Switched to ZenRadio' toast."
  - "Integration test drives panel._on_sibling_link_activated directly (not the QLabel.linkActivated signal). The Plan 02 panel test already exercises the linkActivated path; this integration test focuses on the MainWindow connect + slot + delegation chain, asserting the Player.play + update_last_played + bind_station spies fire on the sibling, NOT the originally-bound DI.fm station."
  - "Slight docstring tightening (10 lines instead of the plan's 13-line docstring) to keep the plan's strict acceptance grep `grep -A12 \"def _on_sibling_activated...\" | grep \"self._on_station_activated(station)\"` returning a match. Semantic content preserved verbatim — the Phase 51 inversion note, the canonical side-effect chain enumeration, and the ROADMAP SC #2 reference are all retained."

patterns-established:
  - "Delegating-slot pattern (D-02): when two distinct activation paths must produce identical side-effects, route both into a single canonical handler via a one-line delegator. Mirrors Phase 51's _on_navigate_to_sibling delegation to _on_edit_requested (line 500) — same shape, opposite semantic action."
  - "Phase-pair inversion test pattern: Phase 64's integration test directly cites the Phase 51 SC #4 assertion that the new test inverts (`fake_player.play_calls == []` becomes `fake_player.play_calls == [zen_station]`). Tracking the inversion at the test level — not just the implementation level — locks the load-bearing semantic distinction against future regression."
  - "RED-then-GREEN gate sequence for a one-line implementation: even when the implementation is a single connect line + a one-line delegator, the test was authored first as a failing test and committed RED before the implementation was added. RED commit (test) precedes GREEN commit (feat) in git log — gate compliance verified."

requirements-completed: [BUG-02]

# Metrics
duration: 9m
completed: 2026-05-01
---

# Phase 64 Plan 03: MainWindow Sibling-Click Wiring Summary

**MainWindow connects NowPlayingPanel.sibling_activated to a one-line delegating slot that routes through _on_station_activated, and an end-to-end integration test asserts Player.play(sibling) + Repo.update_last_played(sibling.id) fire on panel-side sibling click — closing BUG-02 by inverting Phase 51's no-playback-change semantics for the panel-flow.**

## Performance

- **Duration:** ~9 min (worktree base verification + RED+GREEN cycle + verification gates + summary)
- **Started:** 2026-05-01T16:25:53Z
- **Completed:** 2026-05-01T16:34:57Z
- **Tasks:** 1 (committed as RED + GREEN per TDD gate sequence)
- **Files modified:** 2

## Accomplishments

- Connected `now_playing.sibling_activated` to a new `MainWindow._on_sibling_activated` slot via bound-method connection (QA-05) at line 253 of main_window.py — alongside the existing now_playing.edit_requested connect, AFTER self.now_playing is constructed (RESEARCH Pitfall #4) and BEFORE the Phase 41 media-keys block.
- Added the one-line delegating slot `_on_sibling_activated(station)` adjacent to `_on_station_activated` (lines 328-339 in main_window.py). Body: `self._on_station_activated(station)` — single canonical side-effect block (bind_station + Player.play + update_last_played + refresh_recent + on_playing_state_changed + show_toast 'Connecting…' + media_keys.publish_metadata + set_playback_state('playing')).
- Authored end-to-end integration test `test_sibling_click_switches_playback_via_main_window` (tests/test_main_window_integration.py:1003-1080) that constructs a DI.fm + ZenRadio sibling pair, activates DI.fm, clears spies, drives `panel._on_sibling_link_activated("sibling://2")`, and asserts the canonical activation chain fires for the SIBLING. This is the Phase 64 vs Phase 51 inversion: Phase 51 SC #4 asserts `fake_player.play_calls == []`; Phase 64 SC #2 asserts `fake_player.play_calls == [zen_station]`.
- BUG-02 closure-follow-up complete: clicking 'Also on:' in NowPlayingPanel now switches active playback end-to-end (ROADMAP SC #2 satisfied).

## Task Commits

Each task was committed atomically with --no-verify (parallel-executor protocol). Task 1 was authored TDD-first per `tdd="true"` in the plan frontmatter, producing two commits:

1. **Task 1 RED gate: integration test added (failing)** — `18a9313` (test)
2. **Task 1 GREEN gate: connect line + _on_sibling_activated delegating slot** — `1325e79` (feat)

**Plan metadata commit:** to be created by the orchestrator after this SUMMARY.md lands (the parallel-executor protocol forbids us from touching STATE.md or ROADMAP.md).

_Note: The `<execution_context>` of the prompt declared `tdd="true"` for Task 1 in the plan body, so the strict RED-before-GREEN gate sequence was followed. The RED commit's test failed at the `assert fake_player.play_calls == [zen_station]` assertion (signal emit reached but no MainWindow slot connected); the GREEN commit's connect line + slot makes that assertion pass._

## Files Created/Modified

- `musicstreamer/ui_qt/main_window.py` — 2 surgical edits: (1) connect line at line 253 alongside `now_playing.edit_requested.connect`; (2) new 12-line `_on_sibling_activated` method at lines 328-339, between `_on_station_activated` and `_on_failover`. Total: +15 lines.
- `tests/test_main_window_integration.py` — 1 new integration test appended at the end of the file (lines 1003-1080). Constructs DI.fm + ZenRadio sibling pair, FakeRepo + FakePlayer, drives `w.now_playing._on_sibling_link_activated("sibling://2")`, asserts `fake_player.play_calls == [zen_station]` and `fake_repo._last_played_ids == [2]` and `w.now_playing._station is zen_station`. Total: +79 lines.

## Decisions Made

- **Delegating slot, not duplicated side-effect block.** D-02 default in the plan: `_on_sibling_activated` has a one-line body calling `self._on_station_activated(station)`. This locks the canonical activation chain as a single source of truth — any future change to the chain (e.g., new media-keys metadata field) automatically applies to sibling-click activation without touching the sibling slot.
- **Connect line placement at line 253.** Chose this location (alongside the existing `now_playing.edit_requested` connect) over alternatives (e.g., next to `_on_navigate_to_sibling` wiring, or in the media-keys block). Rationale: clusters all `now_playing.*` connects, satisfies RESEARCH Pitfall #4 (must land after `self.now_playing` is constructed), keeps the diff small.
- **Slot placement adjacent to `_on_station_activated` (line 328) rather than next to `_on_navigate_to_sibling` (line 482).** The PATTERNS.md guidance allows either; chose the former because the new slot's behavior is most naturally read as a sibling of `_on_station_activated` (it delegates directly to it). Reading the file top-to-bottom, the reader sees `_on_station_activated` at 316 and `_on_sibling_activated` at 328 — the relationship is immediately apparent.
- **Bound-method connect (QA-05 contract).** No lambda. The plan's acceptance criterion explicitly tests for this with `grep "sibling_activated.connect" | grep -v lambda | grep -v "#"`. Pass.
- **Driver in integration test: panel-side `_on_sibling_link_activated` direct call**, not QLabel.linkActivated emit. The Plan 02 panel test (`tests/test_now_playing_panel.py::test_sibling_link_emits_sibling_activated_with_station_payload`) already exercises the QLabel.linkActivated → handler path with `qtbot.waitSignal`. This integration test focuses on the connect + slot + delegation chain — it directly drives the panel handler, which emits sibling_activated, which the new MainWindow connect routes to `_on_sibling_activated` → `_on_station_activated` → spies fire.
- **Spy reset between DI.fm activation and sibling click.** The test calls `w._on_station_activated(di_station)` to bind DI.fm first (simulates user activating it from the list), then `fake_player.play_calls.clear()` and `fake_repo._last_played_ids = []` to isolate the sibling click's effects. This makes the assertion `fake_player.play_calls == [zen_station]` precise — it asserts the click added zen_station and only zen_station, not a `[di_station, zen_station]` list that would conflate the two activations.
- **Docstring length tightened from 13 to 10 lines on `_on_sibling_activated`** so the plan's strict acceptance grep `grep -A12 "def _on_sibling_activated(self, station: Station)" | grep "self._on_station_activated(station)"` returns a match. Semantic content fully preserved — the Phase 51 inversion note, the canonical side-effect chain enumeration, and the ROADMAP SC #2 reference are all retained. This is a minor stylistic adjustment, not a deviation; the plan's `<read_first>` block at line 359 explicitly says "planner picks based on what reads better in the file's existing slot ordering" and the body language at line 213 grants similar latitude.

## Deviations from Plan

**None — plan executed exactly as written.**

The one minor stylistic adjustment (docstring tightened by 3 lines on `_on_sibling_activated` to fit the plan's `-A12` acceptance grep window) is documented under Decisions above. The acceptance criterion is satisfied; no semantic content was dropped.

## Issues Encountered

- **Pre-existing environmental failure: `tests/test_media_keys_mpris2.py::test_linux_mpris_backend_constructs` (and 5 sibling MPRIS tests) fail with `registerService('org.mpris.MediaPlayer2.musicstreamer') failed: name already taken or bus error`.** Investigation showed PID 54033 (the running pipx-installed MusicStreamer app) holds the D-Bus name. **Confirmed pre-existing on the worktree base** by `git stash && pytest --deselect ... && git stash pop` — the same failures appear with my changes stashed. Per the SCOPE BOUNDARY rule in the executor protocol, this is out of scope (not caused by current task's changes).

  Total pre-existing environmental failures (all confirmed identical with stash): 9 — 6 in `tests/test_media_keys_mpris2.py`, 1 in `tests/test_media_keys_smtc.py::test_thumbnail_from_in_memory_stream`, 2 in `tests/test_station_list_panel.py` (filter_strip + refresh_recent), 1 in `tests/test_twitch_auth.py::test_play_twitch_sets_plugin_option_when_token_present`. None of these touch any code in `musicstreamer/ui_qt/main_window.py` or `tests/test_main_window_integration.py`.

  **Net Plan 64-03 result:** 870 passing tests with the 17 environment-dependent tests deselected. The new `test_sibling_click_switches_playback_via_main_window` is GREEN. All 46 tests in `test_main_window_integration.py` are GREEN. All 121 tests in Plan 01/02 deliverable suites (`test_now_playing_panel.py` + `test_aa_siblings.py` + `test_edit_station_dialog.py`) are GREEN.

- **Worktree base correction at startup:** the worktree HEAD was at `ff24420` instead of the expected `b6f0da9`. The mandatory `<worktree_branch_check>` step caught this immediately and `git reset --hard b6f0da92a2f18ff10514f0d1e72d37b16bf19b9e` corrected the base. Pre-execution `pytest tests/test_now_playing_panel.py tests/test_aa_siblings.py -q` confirmed GREEN (69 passed) before any work began.

## Phase 64 BUG-02 Closure-Follow-Up Status

Cross-referencing Plan 01 + Plan 02 + Plan 03 SUMMARYs:

| SC | Description | Plan | Status |
|----|-------------|------|--------|
| SC #1 | NowPlayingPanel renders 'Also on:' line for AA stations with siblings | Plan 02 | DONE (`test_sibling_label_visible_for_aa_station_with_siblings`) |
| SC #2 | Clicking a sibling link in NowPlayingPanel switches active playback | Plan 03 (this plan) | **DONE** (`test_sibling_click_switches_playback_via_main_window`) |
| SC #3 | Hidden-when-empty (no siblings, non-AA station, panel never bound) | Plan 02 | DONE (4 visibility cases tested) |
| SC #4 | Single source of AA-detection (panel imports only `find_aa_siblings` + `render_sibling_html`) | Plans 01+02 | DONE (negative-spy test at panel layer) |
| SC #5 | self-exclusion (find_aa_siblings excludes the bound station's own id) | Plan 02 | DONE (re-stated through panel) |

All five Phase 64 success criteria are now satisfied across Plans 01–03. The phase is ready for `/gsd-verify-work`.

## Phase 64 vs Phase 51 Inversion: Both Halves Green

The deliberate semantic inversion that defines this phase is locked at the test level:

| Surface | Test | Assertion | Plan |
|---------|------|-----------|------|
| Dialog flow (Phase 51) | `tests/test_main_window_integration.py:920-1000` (Phase 51's sibling-nav integration test) | `fake_player.play_calls == []` (NO playback change) | Phase 51 SC #4 |
| Panel flow (Phase 64) | `tests/test_main_window_integration.py:1003-1080` (this plan) | `fake_player.play_calls == [zen_station]` (DOES change playback) | Phase 64 SC #2 |

Both tests are GREEN at the same commit (1325e79). Future regressions in either direction would break a load-bearing assertion immediately.

## TDD Gate Compliance

The plan declares `tdd="true"` on Task 1. Gate sequence verified:

1. **RED gate:** `git log --oneline | grep "test(64-03):"` returns `18a9313 test(64-03): add failing integration test for sibling-click playback switch`. The test was authored first and committed before the implementation. Locally verified as RED before commit (`assert fake_player.play_calls == [zen_station]` failed because no MainWindow slot was connected).
2. **GREEN gate:** `git log --oneline | grep "feat(64-03):"` returns `1325e79 feat(64-03): wire sibling_activated to _on_sibling_activated delegating slot`. The implementation was added after the RED commit; the test now passes.
3. **REFACTOR gate:** Not needed — the implementation is already minimal (one connect line + one delegating call). No refactor commit.

Both gates present in git log in the correct order. Plan-level TDD compliance verified.

## User Setup Required

None — no external service configuration required. Pure Qt main-thread Signal/Slot wiring change.

## Next Phase Readiness

- Phase 64 BUG-02 closure-follow-up is functionally complete. SC #1–SC #5 all satisfied across Plans 01–03.
- The phase is ready for `/gsd-verify-work` to validate the full chain end-to-end across the integrated phase.
- **No blockers** for the next phase or for verification. The cross-plan dependency that Plan 02's SUMMARY noted (Plan 02's panel imports `render_sibling_html` from Plan 01's url_helpers) is fully resolved at this worktree's base — `b6f0da9` already has Wave 1 (Plans 01 + 02) merged in. All 121 cross-plan deliverable tests are GREEN at this base.

## Threat Flags

No new threat surface introduced beyond what is mitigated by the plan's `<threat_model>` section. Specifically:

- **T-64-06 (Elevation of Privilege via sibling click):** the canonical activation chain reused via the delegator is the same chain a user gets from clicking any station in the station list. Single-user desktop app — no multi-user privilege model. **accept** disposition unchanged.
- **T-64-07 (Spoofing — forged signal payload):** the integration test verifies the chain at the MainWindow boundary, not just at the panel boundary. The Station object in the signal payload is sourced from `FakeRepo.get_station(2)` which returns the registered `zen_station` from `_stations`. Production `Repo.get_station` is the equivalent single source of truth. **accept** disposition unchanged.

No previously undisclosed network endpoints, auth paths, file access patterns, or schema changes introduced. Threat model section in the PLAN.md is complete and accurate.

## Self-Check: PASSED

- FOUND: `musicstreamer/ui_qt/main_window.py` (modified, +15 lines)
- FOUND: `tests/test_main_window_integration.py` (modified, +79 lines)
- FOUND: `.planning/phases/64-audioaddict-siblings-on-now-playing/64-03-SUMMARY.md` (this file)
- FOUND: commit `18a9313` (Task 1 RED gate)
- FOUND: commit `1325e79` (Task 1 GREEN gate)
- VERIFIED: `grep -c "self.now_playing.sibling_activated.connect(self._on_sibling_activated)" musicstreamer/ui_qt/main_window.py` returns 1
- VERIFIED: `grep -c "def _on_sibling_activated" musicstreamer/ui_qt/main_window.py` returns 1
- VERIFIED: `grep -A12 "def _on_sibling_activated(self, station: Station)" main_window.py | grep "self._on_station_activated(station)"` returns 1 match
- VERIFIED: `grep "sibling_activated.connect" main_window.py | grep -v lambda | grep -v "#"` returns the bound-method connect line (no lambda — QA-05 compliant)
- VERIFIED: `pytest tests/test_main_window_integration.py::test_sibling_click_switches_playback_via_main_window -x -q` exits 0
- VERIFIED: `pytest tests/test_main_window_integration.py -x -q` exits 0 (46 tests pass — no regression)
- VERIFIED: `pytest tests/test_now_playing_panel.py tests/test_aa_siblings.py tests/test_edit_station_dialog.py -x -q` exits 0 (121 tests pass — Plan 01 + Plan 02 deliverables remain green)
- VERIFIED: `git diff --name-only HEAD~2 HEAD` shows only the two declared `files_modified` (no out-of-scope changes)

---
*Phase: 64-audioaddict-siblings-on-now-playing*
*Plan: 03*
*Completed: 2026-05-01*
