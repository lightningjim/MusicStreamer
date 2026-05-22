---
phase: 83-at-start-of-playing-a-station-randomly-select-and-play-one-o
plan: 04
subsystem: player
tags: [phase-83, player, somafm, preroll, gapless, playbin3, about-to-finish, gap-closure, qt-glib-threading, uat-fix]
gap_closure: true
requires: [83-03]
provides:
  - "_on_preroll_about_to_finish gapless URI handoff (D-05 UAT-corrected)"
  - "Direct-URL scope guard (YouTube/Twitch fallback to _try_next_stream)"
  - "Elapsed-timer first-attempt seeding across preroll->stream handoff"
  - "force_close('preroll') analytics distinguisher token"
  - "Slice-anchored drift-guard for set_property('uri',...) in slot body"
  - "4 new behavioral tests + 2 updated tests + 1 slice-anchored drift-guard"
affects: [musicstreamer/player.py, tests/test_player.py]
tech-stack:
  added: []
  patterns:
    - "playbin3 gapless URI handoff via plain set_property on still-PLAYING pipeline"
    - "Slice-extracted drift-guard (regex def-boundary slicing)"
    - "Parametrized scope-guard test (youtube.com / youtu.be / twitch.tv)"
key-files:
  created: []
  modified:
    - musicstreamer/player.py
    - tests/test_player.py
decisions:
  - "D-05 (UAT-corrected): preroll->stream handoff is a gapless URI swap (plain set_property), NOT a state cycle"
  - "force_close token 'preroll' (not 'failover') distinguishes gapless handoff from stream-error failover"
  - "Elapsed-timer seeding mirrors _try_next_stream:1073-1077 — without it the UI display freezes at 0"
  - "YouTube/Twitch URLs fall back to legacy _try_next_stream (async resolution required; playbin3 cannot stream watch URLs directly)"
  - "Drift-guard uses slice-extraction (def-boundary regex) — strictly stronger than global grep (would false-negative a revert-only-the-slot regression because _set_uri retains its own set_property('uri',...))"
metrics:
  duration: ~25min
  completed: 2026-05-22
  tasks_completed: 2
  files_modified: 2
  tests_added: 4
  tests_updated: 2
---

# Phase 83 Plan 04: SomaFM Preroll Gapless URI Handoff (UAT Gap Closure) Summary

JWT-style one-liner: `_on_preroll_about_to_finish` now performs a true playbin3 gapless URI handoff via `pipeline.set_property("uri", ...)` on the still-PLAYING pipeline — fixing the 83-UAT D-05 blocker where the preroll never reached audible playback because the shipped 83-03 slot called `_try_next_stream()` which cycled `set_state(NULL)` and tore down the preroll mid-playback.

## Root Cause Recap (83-UAT.md §D-05)

The shipped 83-03 slot body:

```python
def _on_preroll_about_to_finish(self) -> None:
    ...
    self._preroll_in_flight = False
    self._try_next_stream()                # ← THE BUG
```

`_try_next_stream()` does `set_state(NULL)` → `get_state(...)` → `_set_uri` → `set_state(PLAYING)` (player.py:1043,1091-1094). The live-spike (2026-05-22 Linux GStreamer 1.28.2; 83-RESEARCH §Q1 RESOLVED) confirmed `about-to-finish` fires at +7.849s for a 7.99s preroll — the state cycle tears the preroll down before it reaches the speakers.

playbin3's `about-to-finish` is the *gapless* handoff mechanism: the next URI MUST be installed on the still-PLAYING pipeline via a plain `pipeline.set_property("uri", next_url)`. playbin3 then plays the current track to EOS and transitions seamlessly.

## Implementation Surface

| Surface | File:Line (post-fix) | Notes |
|---------|----------------------|-------|
| `_on_preroll_about_to_finish` body rewrite | musicstreamer/player.py:1124-1205 | ~80 lines replacing the 12-line `_try_next_stream()` body. Mirrors _try_next_stream's bookkeeping but NOT its state cycle; adds direct-URL scope guard + elapsed-timer seeding. |
| 4 new tests + 2 updated tests | tests/test_player.py:1117-1488 | All Phase 83 cluster; appended after `test_phase_83_preroll_drift_guard`. |

## Behavioral Tests

| Test | Status | Purpose |
|------|--------|---------|
| `test_preroll_about_to_finish_uses_gapless_uri_swap` | NEW | Asserts set_property called with stream URL; set_state.call_count unchanged by slot; _try_next_stream NOT called on direct-URL path |
| `test_preroll_handoff_normalizes_url_via_aa_normalize` | NEW | URI funnel preserved: gapless set_property routes through aa_normalize_stream_url (Phase 70/WIN-01) |
| `test_preroll_handoff_falls_back_for_youtube_url` (parametrized: youtube.com / youtu.be / twitch.tv) | NEW | Scope guard: async-resolution URLs use legacy _try_next_stream() fallback |
| `test_preroll_handoff_invokes_tracker_bind_and_failover_timer_arm` | NEW | Bookkeeping parity: force_close("preroll"), bind_url, failover-timer arm with BUFFER_DURATION_S * 1000ms, elapsed-timer first-attempt seeding (`mock_elapsed_timer.start.assert_called_once()` + `_elapsed_seconds == 0`), _is_first_attempt flip to False |
| `test_streams_queue_failover_after_preroll_handoff` | UPDATED | Patches tracker + timers around slot invocation (slot no longer calls _set_uri); post-handoff Phase 82 failover semantics intact |
| `test_phase_83_preroll_drift_guard` | UPDATED | Adds slice-extraction assertion: regex `def _on_preroll_about_to_finish\(.*?\)(.*?)(?=\n    def |\Z)` extracts the method body; literal-match `set_property\([^)]{0,80}["\']uri["\']` runs ONLY on the extracted slice — fails loudly on a slot-only revert |

## Verification Results

```
$ uv run pytest tests/test_player.py -k "preroll or phase_83 or streams_queue_failover_after_preroll_handoff or about_to_finish" -x -q
17 passed, 27 deselected, 1 warning in 0.28s
```

```
$ uv run pytest tests/test_player.py -x -q
44 passed, 1 warning in 0.37s
```

```
$ uv run pytest tests/test_player.py tests/test_soma_import.py tests/test_repo.py tests/test_fake_player_signal_parity.py -q
157 passed, 1 warning in 2.75s
```

```
$ uv run pytest -q --tb=short
2 failed, 1733 passed, 1 skipped, 2 warnings in 25.13s
```

The 2 failures are the SAME pre-existing flakes documented in 83-03-SUMMARY.md §"Pre-existing Failures":

- `tests/test_main_window_integration.py::test_hamburger_menu_actions`
- `tests/test_media_keys_smtc.py::test_end_to_end_factory_fallback_on_win32_without_winrt`

Both are out of scope per `<deviation_rules>` SCOPE BOUNDARY (per 83-03-SUMMARY: "Confirmed via git stash + re-run on pre-83-03 state").

## Source-Grep Invariants

| Invariant | Expected | Actual |
|-----------|----------|--------|
| `self._pipeline.set_property("uri"` count | ≥ 2 | 2 (one in `_set_uri`, one new in `_on_preroll_about_to_finish` gapless branch) |
| `force_close("preroll")` count | 1 | 1 (new in gapless slot; analytics distinguisher token) |
| `def _on_preroll_about_to_finish` count | 1 (the slot itself; the callback is `_on_preroll_about_to_finish_callback`) | 1 |
| Slot body contains `set_state(...)` | 0 (gapless invariant) | 0 (only in docstring/comments) |
| Slot body contains `_elapsed_timer.start` | 1 (mirror of `_try_next_stream:1077`) | 1 |
| Slot body contains `_try_next_stream()` | 2 (YT/Twitch fallback + empty-queue defensive) | 2 |
| `aa_normalize_stream_url(stream.url)` in slot body | 1 (URI funnel preserved) | 1 |

## Threading Discipline (qt-glib-bus-threading Rule 2)

- `_on_preroll_about_to_finish_callback` body remains EXACTLY ONE LINE: `self._preroll_about_to_finish_requested.emit()` — streaming-thread callback NEVER touches the pipeline directly.
- `_on_preroll_about_to_finish` runs on the MAIN thread (queued slot via `QueuedConnection` in `__init__`); `pipeline.set_property("uri", ...)` from main is the canonical playbin3 gapless idiom and is safe per Rule 2 ("Qt-thread rules apply to Qt operations and pipeline STATE changes; plain GObject property sets on the pipeline from the main thread are allowed").

## Deviations from Plan

None — plan executed exactly as written. No Rule 1-4 deviations.

## Known Stubs

None.

## Threat Surface Scan

No new threat-surface flags introduced. The plan-level `<threat_model>` covered T-83-15 (drift-guard), T-83-16 (URI funnel), T-83-17 (force_close token), T-83-18 (DoS via repeated handoff), T-83-19 (scope-guard spoofing), T-83-20 (elapsed-timer regression) — all `mitigate` dispositions in the threat register are implemented in this plan.

## Commit Hashes

| Task | Type | Hash | Description |
|------|------|------|-------------|
| 1 (RED) | test | `6994b3d` | Failing tests for gapless URI handoff (4 new + 2 updated) |
| 1 (GREEN) | fix | `72a0ebf` | `_on_preroll_about_to_finish` gapless implementation |

(Task 2 is verification-only — no code/test changes; no commit.)

## Manual UAT Recommendations (for `/gsd:verify-work 83`)

Per 83-VALIDATION.md §"Manual-Only Verifications" — run on Linux Wayland (deployment target):

1. **Beat Blender preroll → stream gapless handoff** (Test 1 from 83-UAT.md): Bind SomaFM Beat Blender. Click Play. Hear one of three station-ID voiceover clips (~5-8s), then deep-house stream begins gaplessly. Now Playing shows "Beat Blender" throughout. Covers D-05 + D-07.
2. **Throttle within 10 minutes — replay suppresses preroll** (Test 3, previously blocked_by Test 1): Immediately after Test 1, Stop, then Play Beat Blender again. Stream starts immediately with NO preroll (D-12 throttle).
3. **Throttle after 10 minutes — preroll plays again** (Test 4, previously blocked_by Test 1): Wait 10+ minutes (or restart the app) and click Play on Beat Blender. Preroll plays this time.

Test 2 (Seven Inch Soul no-preroll) already passed in 83-UAT.md and is unaffected by this plan.

## Self-Check: PASSED

- [x] `musicstreamer/player.py` exists and modified (commit `72a0ebf`)
- [x] `tests/test_player.py` exists and modified (commit `6994b3d`)
- [x] Both commit hashes resolve in `git log --oneline -5`:
  - `6994b3d test(83-04): add failing tests for gapless URI handoff in _on_preroll_about_to_finish`
  - `72a0ebf fix(83-04): _on_preroll_about_to_finish performs gapless URI handoff`
- [x] 17 Phase 83 tests pass (13 existing + 4 new)
- [x] 44 tests/test_player.py tests pass (full file)
- [x] 157 quick-run suite tests pass
- [x] Full suite: 1733 passed (2 pre-existing flakes documented in 83-03-SUMMARY.md unchanged)
- [x] Source-grep invariants all green (see table above)
- [x] Slot body contains NO `set_state(...)` calls (only docstring/comments)
- [x] Slot body contains `set_property("uri",...)` literal — slice-anchored drift-guard PASSES
- [x] Elapsed-timer seeding block present (closes checker WARNING)
- [x] force_close("preroll") distinguisher token present (closes checker concern)
- [x] aa_normalize_stream_url called on stream.url (URI funnel invariant preserved)
- [x] STATE.md and ROADMAP.md NOT modified (worktree mode; orchestrator owns those writes after merge)
