---
phase: 57-windows-audio-glitch-test-fix
plan: 03
subsystem: player / audio-pipeline
tags: [player, gstreamer, bus-message, state-changed, volume-reapply, cross-platform, regression-guard, win-03, tdd]
status: complete
requires:
  - 57-CONTEXT.md (D-11 cross-platform scope; D-12 hook site; D-13 single mechanism Option A)
  - 57-DIAGNOSTIC-LOG.md (sink = wasapi2sink; volume 0.5 -> 1.0 on NULL->PLAYING; Option A confirmed)
  - 57-PATTERNS.md (bus-handler idiom; player.py:134-136 handler family; test_player_failover.py fixture)
provides:
  - musicstreamer/player.py: _playbin_playing_state_reached Signal + bus connect + queued connection + 2 new methods
  - tests/test_player_failover.py: 4 cross-platform regression guard tests (NULL->PLAYING + PAUSED->PLAYING + filter invariants)
affects:
  - Plan 57-04: smoothing wrapper composes against self._pipeline.set_property("volume", ...) as single write surface
  - WIN-03 volume half: closed — every PLAYING-arrival now re-applies self._volume to playbin3.volume
tech-stack:
  added: []
  patterns:
    - "Bus-message STATE_CHANGED handler joining existing message::error / message::tag / message::buffering family"
    - "Queued Signal cross-thread marshalling (bus-loop -> main) — same pattern as _cancel_timers_requested"
    - "D-14 Linux CI regression guard: direct slot invocation on mocked pipeline"
key-files:
  created: []
  modified:
    - musicstreamer/player.py (Signal decl + bus connect + queued connect + 2 new methods — 50 lines added)
    - tests/test_player_failover.py (section divider + 4 new tests — 79 lines added)
decisions:
  - "D-12 hook site: bus-message STATE_CHANGED on playbin3 bus (NOT tail-of-_set_uri) — catches PAUSED->PLAYING rebuffer recovery that bypasses _set_uri"
  - "D-13 single mechanism: self._pipeline.set_property('volume', self._volume) is the one write surface — no _volume_element"
  - "D-11 cross-platform: ships in shared player.py without platform guard"
  - "D-14 regression guard: direct slot invocation (not real bus dispatch) — make_player replaces _pipeline with fresh MagicMock; assert_any_call pattern matches Phase 56 convention"
  - "TDD order: tests written first (RED: AttributeError on missing method), then implementation (GREEN: all 4 pass)"
metrics:
  duration: ~25min
  completed: "2026-05-03"
  tasks: 2
  files_modified: 2
---

# Phase 57 Plan 03: Bus-Message STATE_CHANGED Volume Re-Apply Summary

**One-liner:** Wired `playbin3` bus-message `STATE_CHANGED` handler that re-applies `self._volume` to `playbin3.volume` on every transition to `PLAYING` via queued Signal cross-thread marshalling, with 4 Linux CI regression guard tests covering both transition paths and the filter invariants.

## What Was Done

### Task 1: Wire bus-message STATE_CHANGED handler + queued main-thread re-apply slot (player.py)

**Diff summary (musicstreamer/player.py — 50 insertions):**

1. **New class-level Signal** added to the internal marshalling block after `_try_next_stream_requested`:
   ```python
   _playbin_playing_state_reached = Signal()    # bus-loop -> main: re-apply volume on PLAYING
   ```

2. **New bus connect** in `__init__` after the existing handler-family at line 136:
   ```python
   bus.connect("message::state-changed", self._on_gst_state_changed)  # Phase 57 / WIN-03 D-12
   ```

3. **New queued connection** in the queued-connect block after `_try_next_stream_requested.connect(...)`:
   ```python
   self._playbin_playing_state_reached.connect(
       self._on_playbin_state_changed, Qt.ConnectionType.QueuedConnection
   )
   ```

4. **`_on_gst_state_changed`** (bus-loop-thread handler): filters to `msg.src is self._pipeline` and `new == Gst.State.PLAYING`, then emits `_playbin_playing_state_reached`.

5. **`_on_playbin_state_changed`** (main-thread slot): writes `self._pipeline.set_property("volume", self._volume)`.

**Invariants preserved:**
- `_set_uri` untouched — `aa_normalize_stream_url(uri)` remains first executable line (Phase 56 D-04)
- No `_volume_element` reference anywhere (D-13)
- `set_volume` unchanged — its single-line write is the Linux happy path

### Task 2: Linux CI regression guard tests (tests/test_player_failover.py)

**New section** appended after the Phase 56 / WIN-01 block (line 483 in original):

1. `test_volume_reapplied_on_null_to_playing`: sets volume 0.5, resets mock, invokes `_on_playbin_state_changed()` directly, asserts `set_property("volume", 0.5)`.
2. `test_volume_reapplied_on_paused_to_playing`: same shape with 0.7 (documents PAUSED->PLAYING rebuffer recovery path explicitly).
3. `test_bus_state_changed_handler_filters_non_playing_transitions`: PLAYING->PAUSED transition with pipeline as msg.src — asserts `sig.emit.assert_not_called()`.
4. `test_bus_state_changed_handler_filters_child_element_messages`: child element msg.src (not pipeline) with PLAYING as new_state — asserts `sig.emit.assert_not_called()`.

## Acceptance Gate Results

```
Gate 1: grep -c "message::state-changed" musicstreamer/player.py  => 1   PASS
Gate 2: grep -c "_on_gst_state_changed" musicstreamer/player.py   => 2   PASS (1 connect + 1 def)
Gate 3: grep -c "_on_playbin_state_changed" musicstreamer/player.py => 2 PASS (1 queued connect + 1 def)
Gate 4: grep -c "_playbin_playing_state_reached" musicstreamer/player.py => 3 PASS (1 Signal + 1 connect + 1 emit)
Gate 5: ! grep -q "_volume_element" musicstreamer/player.py        => PASS (D-13 invariant)
Gate 6: grep non-comment set_property("volume", self._volume) count => 2  PASS (set_volume + _on_playbin_state_changed)
Gate 7: grep -q "aa_normalize_stream_url(uri)" musicstreamer/player.py => PASS (Phase 56 D-04 preserved)
Gate 8: 4 new test defs in tests/test_player_failover.py           => 4   PASS
Gate 9: grep -c "Phase 57 / WIN-03 D-12" tests/test_player_failover.py => 1 PASS
```

## Test Results

```
PYTHONPATH=. uv run pytest tests/test_player_failover.py tests/test_player_pause.py tests/test_player_volume.py -v

collected 36 items — 36 passed, 1 warning in 0.65s
```

All 4 new tests GREEN. All 32 pre-existing tests in the three files remain GREEN.

## Task Commits

| Task | Description | Commit |
|------|-------------|--------|
| 1 | feat(57-03): wire bus-message STATE_CHANGED volume re-apply in player.py | 6cfd0c6 |
| 2 | test(57-03): 4 regression guard tests for STATE_CHANGED volume re-apply (D-14) | 70e24cc |

## Deviations from Plan

**1. [Rule N/A - Worktree Commit Routing] Player.py changes accidentally committed to main branch first**

- **Found during:** Task 1 commit
- **Issue:** `cd /home/kcreasey/OneDrive/Projects/MusicStreamer` commands operated on the main repo (not the worktree), causing `feat(57-03)` to land on `main` (commit 1040079) instead of `worktree-agent-a2f5e74f966fc4809`.
- **Fix:** Cherry-picked 1040079 into the worktree branch (became 6cfd0c6). Then `git reset --hard 3ba6db6` on main to remove the errant commit. Test file changes were applied directly to the worktree file (they had not been committed to main).
- **Files modified:** musicstreamer/player.py, tests/test_player_failover.py (both now on correct worktree branch)
- **Commits:** 6cfd0c6 (player.py), 70e24cc (tests)

No other deviations — plan executed as written. `_set_uri` untouched, no `_volume_element` reference, all invariants held.

## Note for Plan 57-04

The single volume write surface established by this plan is:

```python
self._pipeline.set_property("volume", self._volume)
```

This write occurs:
1. In `set_volume()` — immediate response to slider movement (steady-state)
2. In `_on_playbin_state_changed()` — on every PLAYING-arrival (post-rebuild re-apply)

Plan 57-04's smoothing wrapper composes by intercepting the `playbin3.volume` property writes during the NULL->PLAYING transition window. The composition contract (D-15) requires that 57-04 does NOT add a third write site — it should either:
- Own the re-apply write during the ramp (i.e., the ramp's final tick lands at `self._volume`), OR
- Let the bus-message hook write `self._volume` as the ramp's post-condition

Both approaches keep the property at `self._volume` after every PLAYING-arrival, matching the diagnostic Step 2 requirement. Plan 57-04 chooses the exact ordering; this plan only ships the hook.

## Known Stubs

None — the bus-message handler is fully wired. The volume re-apply fires on every PLAYING-arrival; no mocked or placeholder data flows to any rendering surface.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. The bus-message handler reads only the GStreamer state-changed message payload (old/new/pending state tuple + msg.src identity) — no external data ingested, no trust boundary crossed beyond the existing GStreamer bus -> bus-loop thread boundary already enumerated in the plan's threat model (T-57-03-01 through T-57-03-05 all mitigated as designed).

## Self-Check: PASSED

- FOUND: musicstreamer/player.py
- FOUND: tests/test_player_failover.py
- FOUND: .planning/phases/57-windows-audio-glitch-test-fix/57-03-SUMMARY.md
- FOUND: commit 6cfd0c6 (feat(57-03): player.py)
- FOUND: commit 70e24cc (test(57-03): tests)
