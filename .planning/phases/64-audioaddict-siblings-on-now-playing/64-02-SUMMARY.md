---
phase: 64-audioaddict-siblings-on-now-playing
plan: 02
subsystem: ui
tags: [pyside6, qlabel, qt-richtext, signal, audioaddict, sibling-link, now-playing-panel]

# Dependency graph
requires:
  - phase: 51-audioaddict-cross-network-siblings
    provides: find_aa_siblings (url_helpers.py:86) and EditStationDialog Phase-51 sibling label / click-handler shapes that this plan mirrors on the panel
  - phase: 64-audioaddict-siblings-on-now-playing
    provides: Plan 64-01 promotes _render_sibling_html to the free function render_sibling_html in url_helpers.py — this plan's panel imports it
provides:
  - NowPlayingPanel.sibling_activated = Signal(object) — D-02 contract that Plan 64-03 (MainWindow wiring, Wave 2) consumes
  - NowPlayingPanel._sibling_label QLabel (Qt.RichText, hidden-when-empty) between name_provider_label and icy_label
  - NowPlayingPanel._refresh_siblings — single-call-site (D-04) sibling refresher reachable only from bind_station
  - NowPlayingPanel._on_sibling_link_activated — sibling://{id} click handler with D-08 self-id guard and dual-shape repo.get_station exception handling (RESEARCH Pitfall #2)
  - tests/test_now_playing_panel.py FakeRepo extension (list_stations + get_station-raising-ValueError) and _make_aa_station factory (Wave 0 fixture gap fill)
  - 11 panel-level tests covering visibility (4 cases), self-exclusion, signal emission, D-08 guard, malformed-href robustness, Pitfall #2 exception handling, D-04 invariant, SC #4 import negative-spy
affects: [64-03 MainWindow wiring, future-phase any-panel-extension]

# Tech tracking
tech-stack:
  added: []  # No new libraries — pure PySide6 + existing url_helpers
  patterns:
    - "QLabel(Qt.RichText) deviation locked by html.escape inside shared renderer (T-39-01 mitigation pattern, second consumer after Phase 51 dialog)"
    - "Signal(object) for Station-shaped payload (mirrors edit_requested precedent at now_playing_panel.py:112)"
    - "Single-call-site invariant locked by negative-spy test (D-04: _refresh_siblings reachable ONLY from bind_station)"
    - "Dual-shape repo lookup wrapped in try/except Exception + is None check (Qt slots-never-raise; covers production ValueError + test-double None-return)"
    - "Import-negative-spy test pattern: forbidden symbol list asserts SC #4 single-source-of-AA-detection invariant via source-text scan"
    - "Hidden-by-default QLabel reclaims zero vertical space in QVBoxLayout (D-05 idiom, mirror of Phase 51)"

key-files:
  created: []
  modified:
    - musicstreamer/ui_qt/now_playing_panel.py
    - tests/test_now_playing_panel.py

key-decisions:
  - "Imported only find_aa_siblings + render_sibling_html from url_helpers (SC #4 single source of AA detection — locked by negative-spy test asserting forbidden-symbol absence)"
  - "FakeRepo.get_station raises ValueError on miss to match production semantics (locks the production-correct exception path; panel handler must wrap in try/except Exception per RESEARCH Pitfall #2)"
  - "_refresh_siblings is the single-call-site model — only invoked from bind_station tail (D-04 invariant; library-mutation signal subscriptions intentionally not wired to keep the contract minimal)"
  - "D-08 self-id no-op guard at top of click handler is defense-in-depth (find_aa_siblings already excludes self at url_helpers.py:122; the redundant guard locks against future rendering staleness)"
  - "Bare except Exception around repo.get_station rather than narrow except ValueError — narrowing leaves the test-double None-return shape unprotected per Pitfall #2"
  - "No setFont call on _sibling_label (UI-SPEC font lock — inherits Qt platform default for parity with Phase 51 dialog version)"
  - "Used a transient in-memory render_sibling_html shim to validate panel + 11 tests locally; no shim file committed and url_helpers.py left untouched (parallel-executor scope rule)"

patterns-established:
  - "Cross-plan parallel execution accommodation: panel imports a symbol that does not exist at the worktree's base; tests cannot collect until Plan 01 merges. This is the planned RED-until-merge state — the orchestrator's post-merge gate runs after both worktrees merge."
  - "Single-call-site negative spy: monkeypatch the method, count invocations, assert ==1 across the public entry point — proves no other call site (e.g., no library-mutation signal subscription)"
  - "Import-source negative spy: open the module's __file__ via panel_mod.__file__, scan source text for forbidden import lines, assert each is absent — locks SC #4 single-source-of-detection invariant cheaply without runtime introspection"

requirements-completed: [BUG-02]

# Metrics
duration: 6m
completed: 2026-05-01
---

# Phase 64 Plan 02: NowPlayingPanel Sibling Line Summary

**NowPlayingPanel exposes sibling_activated = Signal(object), renders the cross-network 'Also on:' line for AA stations with siblings via the shared render_sibling_html, hides cleanly otherwise, and locks the D-04 single-call-site invariant + SC #4 single-source-of-AA-detection invariant with negative-spy tests.**

## Performance

- **Duration:** ~6 min (5m49s)
- **Started:** 2026-05-01T16:19:38Z
- **Completed:** 2026-05-01T16:25:27Z
- **Tasks:** 2 (both committed atomically with --no-verify per parallel-executor protocol)
- **Files modified:** 2

## Accomplishments

- Added `sibling_activated = Signal(object)` to NowPlayingPanel — the contract Plan 64-03 (MainWindow wiring, Wave 2) consumes
- Inserted `_sibling_label` QLabel between `name_provider_label` and `icy_label` with Qt.RichText / setOpenExternalLinks(False) / setVisible(False) / bound-method linkActivated (QA-05); hidden-when-empty reclaims zero vertical space
- New `_refresh_siblings` reads `self._station.streams[0].url` with empty-streams + None-station defensive guards, calls find_aa_siblings + render_sibling_html OR hides the label (D-05 four cases)
- New `_on_sibling_link_activated` parses sibling://{id}, applies D-08 self-id no-op guard, wraps repo.get_station in try/except Exception (RESEARCH Pitfall #2: production raises ValueError; some test doubles return None), emits sibling_activated(Station)
- D-04 invariant: `_refresh_siblings` is reachable ONLY from `bind_station` — locked by negative-spy test
- SC #4 invariant: panel imports only find_aa_siblings + render_sibling_html from url_helpers; forbidden symbols (_is_aa_url, _aa_slug_from_url, _aa_channel_key_from_url, NETWORKS) absent — locked by source-text scan negative-spy
- Wave 0 fixture gap filled: FakeRepo grows `stations` kwarg + `list_stations()` + `get_station(id)` raising ValueError on miss; `_make_aa_station` factory mirrors Phase 51 pattern at module scope
- 11 new panel-level tests added; all pass under in-memory renderer shim (locally simulated post-merge state)

## Task Commits

Each task was committed atomically with --no-verify (parallel-executor protocol):

1. **Task 1: Wave 0 — extend FakeRepo with list_stations + get_station; add _make_aa_station factory** — `2491227` (test)
2. **Task 2: Add Signal, _sibling_label, _refresh_siblings, _on_sibling_link_activated to NowPlayingPanel + 11 panel tests** — `4c4ee35` (feat)

_Note: Task 2 in this plan does NOT use the strict TDD RED-then-GREEN cycle. The plan body explicitly states "Implementation first because the tests are widget-level and can't be RED-then-GREEN on a non-existent widget. The behavioral correctness is locked by the existing Phase 51 pattern + the Plan 01 renderer's already-passing tests." (lines 332-333). The plan frontmatter does not declare `tdd="true"` on Task 2._

## Files Created/Modified

- `musicstreamer/ui_qt/now_playing_panel.py` — 5 surgical edits: import (find_aa_siblings + render_sibling_html); signal (sibling_activated = Signal(object)); widget (_sibling_label QLabel between name_provider_label and icy_label); bind_station tail (`self._refresh_siblings()` after `self._populate_stream_picker(station)`); two new methods (_refresh_siblings + _on_sibling_link_activated)
- `tests/test_now_playing_panel.py` — Task 1: FakeRepo.__init__ accepts `stations` kwarg, two new methods (`list_stations` + `get_station` raising ValueError on miss), `_make_aa_station` factory at module scope. Task 2: 11 panel-level tests covering visibility (4 cases), self-exclusion, signal emission, D-08 guard, malformed-href robustness, Pitfall #2 exception path, D-04 invariant, SC #4 import negative-spy.

## Decisions Made

- **Strict adherence to single-source-of-AA-detection (SC #4):** Imported only `find_aa_siblings` and `render_sibling_html` from url_helpers; never `_is_aa_url`, `_aa_slug_from_url`, `_aa_channel_key_from_url`, or `NETWORKS`. Locked by `test_panel_does_not_reimplement_aa_detection` which scans the panel module's source for forbidden import lines.
- **FakeRepo.get_station raises ValueError on miss** to match production `Repo.get_station` semantics (`musicstreamer/repo.py:271`). The alternative (return None like `MainWindow.FakeRepo` at `tests/test_main_window_integration.py:152`) would have hidden the production-correct exception path in panel-level tests. Pitfall #2 test (`test_sibling_link_handler_no_op_when_repo_get_station_raises`) directly exercises the ValueError path to lock the contract.
- **D-04 single-call-site invariant locked at the test layer**, not at the implementation layer alone. `test_refresh_siblings_runs_once_per_bind_station_call` monkeypatches `_refresh_siblings` with a counter and asserts exactly 1 call across a single `bind_station` invocation — this proves no other call site exists (e.g., no library-mutation signal subscription).
- **D-08 self-id guard added even though find_aa_siblings already excludes self** at `url_helpers.py:122`. Defense-in-depth against future rendering staleness — a stale label could in principle present a self-link if the bound station mutated mid-flight. Cheap to lock; expensive to debug if absent.
- **Bare `except Exception` around repo.get_station, not narrow `except ValueError`.** Narrowing leaves the test-double `None`-return shape unprotected, which would crash on the subsequent `is None` check if the unhandled return type were unexpected. The dual-shape contract explicitly requires both paths.
- **No setFont call on _sibling_label** — UI-SPEC §Typography records this as a locked decision. Inherits Qt platform default for parity with Phase 51 dialog version, which also has no setFont (verified at `edit_station_dialog.py:405-411`).
- **Implementation-first task ordering for Task 2** rather than TDD RED-then-GREEN — the plan body justifies this at lines 332-333: widget-level tests cannot be authored against a non-existent widget. Behavioral correctness is locked by Phase 51's existing tests + the Plan 01 renderer's tests.

## Deviations from Plan

None — plan executed exactly as written.

The two minor stylistic items below are NOT deviations from the plan body, but I am calling them out so the reviewer does not have to reverse-engineer them:

1. **bind_station hook wrapped in 3 explanatory comment lines.** The plan body at lines 401-405 shows the same wrapping (the call is preceded by a 2-line comment in the plan). The acceptance criterion at line 682 specifies the strict grep `grep -A1 ... | grep self._refresh_siblings()` which returns 0 because of the intervening comments. Widening to `-A4` returns 1. The semantic acceptance criterion ("immediately after `self._populate_stream_picker(station)`") is satisfied — only explanatory comments matching the plan's own example intervene.
2. **No new lambda-vs-bound-method violations introduced.** The new `linkActivated.connect(self._on_sibling_link_activated)` is a bound-method connection per QA-05, as specified at plan line 49.

## Issues Encountered

- **Expected RED-until-merge state (cross-plan dependency on Plan 01 renderer):** At this worktree's base (commit `2853783`), `render_sibling_html` does not yet exist in `musicstreamer/url_helpers.py` — Plan 01 in a parallel worktree adds it. The panel module's import (`from musicstreamer.url_helpers import find_aa_siblings, render_sibling_html`) fails to resolve at the worktree base, which means `pytest tests/test_now_playing_panel.py` fails to COLLECT (ImportError at module-import time, not test failure). This is the planned RED-until-merge state per the parallel_execution context provided in the prompt; the orchestrator runs the post-merge gate after both worktrees merge.

  **Local validation strategy:** I created a transient in-memory shim (`/tmp/conftest_shim.py`) that injects a Plan-01-equivalent `render_sibling_html` function into `musicstreamer.url_helpers` BEFORE the panel module's import is resolved. With the shim active, `pytest tests/test_now_playing_panel.py` runs all 52 tests (41 existing + 11 new) and they all pass. I also confirmed `pytest tests/test_aa_siblings.py tests/test_edit_station_dialog.py` still passes (64 tests) — no regression in Plan 01's deliverables at this base. The shim file was deleted; no shim was committed to the repo; `musicstreamer/url_helpers.py` was NOT modified (parallel-executor scope rule).

  **Tests expected to fail collection at the worktree base (RED-until-merge):** all 52 tests in `tests/test_now_playing_panel.py`. After Plan 01 merges to the integration branch, the import resolves and the orchestrator's post-merge gate executes the full verification command at line 673 of the plan body to confirm GREEN.

## TDD Gate Compliance

This plan does NOT have `type: tdd` in its frontmatter (`type: execute`), so plan-level TDD gate enforcement does not apply. Task 2 also does NOT declare `tdd="true"`. The plan body explicitly justifies implementation-first ordering at lines 332-333: "Implementation first because the tests are widget-level and can't be RED-then-GREEN on a non-existent widget."

## User Setup Required

None — no external service configuration required. Pure Qt main-thread UI/plumbing change.

## Next Phase Readiness

- **`sibling_activated = Signal(object)` contract is ready** for Plan 64-03 (MainWindow wiring, Wave 2) consumption: `self.now_playing.sibling_activated.connect(self._on_sibling_activated)` then a one-line `_on_sibling_activated(station)` slot delegating to `_on_station_activated(station)` per the PATTERNS.md Phase 64 guidance.
- **Cross-plan invariant for the post-merge gate:** Plan 01 promotes `_render_sibling_html` to `render_sibling_html` (free function in url_helpers.py); after merge, the panel's import resolves and `pytest tests/test_now_playing_panel.py tests/test_aa_siblings.py tests/test_edit_station_dialog.py -x -q` should exit 0. The orchestrator's post-merge gate is responsible for running this command.
- **No blockers** for Plan 64-03. The signal contract and the panel surface are both in place; Plan 64-03 only needs to wire MainWindow.

## Threat Flags

No new threat surface introduced beyond what is already mitigated by the plan's `<threat_model>` section. Specifically:

- **T-64-01 (HTML injection on second Qt.RichText surface):** mitigated by the shared renderer (Plan 01) preserving `html.escape(station_name, quote=True)`. The panel does not bypass the renderer — verified by SC #4 negative-spy test.
- **T-64-02 (href payload tampering):** mitigated by `int(href[len(prefix):])` with `try/except ValueError`, prefix `startswith` check, and D-08 self-id guard. All failure paths are silent no-ops.
- **T-64-03 (slot raises uncaught):** mitigated by `try/except Exception` around `self._repo.get_station(sibling_id)` followed by `is None` check.

No previously undisclosed network endpoints, auth paths, file access patterns, or schema changes introduced. Threat model section in the PLAN.md is complete and accurate.

## Self-Check: PASSED

- FOUND: `musicstreamer/ui_qt/now_playing_panel.py`
- FOUND: `tests/test_now_playing_panel.py`
- FOUND: `.planning/phases/64-audioaddict-siblings-on-now-playing/64-02-SUMMARY.md`
- FOUND: commit `2491227` (Task 1)
- FOUND: commit `4c4ee35` (Task 2)

---
*Phase: 64-audioaddict-siblings-on-now-playing*
*Plan: 02*
*Completed: 2026-05-01*
