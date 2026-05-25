---
phase: 84-bug-09-commit-b-buffer-tuning-behavior-fix-reframed-from-str
reviewed: 2026-05-24T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - musicstreamer/constants.py
  - musicstreamer/player.py
  - musicstreamer/ui_qt/main_window.py
  - musicstreamer/ui_qt/now_playing_panel.py
  - tests/_fake_player.py
  - tests/test_main_window_underrun.py
  - tests/test_now_playing_panel.py
  - tests/test_playbin3_property_hygiene.py
  - tests/test_player_buffer.py
  - tests/test_player_buffer_growth.py
findings:
  critical: 2
  warning: 5
  info: 4
  total: 11
status: issues_found
---

# Phase 84: Code Review Report

**Reviewed:** 2026-05-24
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Phase 84 ships three coordinated changes: (D-10) baseline buffer bump 10s/10MB → 30s/20MB; (D-11) stage-and-apply adaptive growth schedule 30→60→120s with apply sites at both URI-bind locations; (D-12) new `buffer_duration_changed` Signal wired through to a new always-visible "Buf duration" stats-for-nerds row.

The state-machine implementation is internally clean and the Pattern 4 source-grep hygiene gate is well-constructed. However, two correctness defects were found in the growth trigger and the per-URL reset semantics, both of which cause user-visible incorrect behavior on common interaction paths (pause/stop, station change). Several quality issues around brittle Signal-value coupling, watchdog-window staleness, and tracker-close fan-out also surfaced.

The structural skeleton (state fields, Signal declaration, wire location, slot signature) matches CONTEXT and mirrors the Phase 78 pattern faithfully. The bugs below are in the *semantics* of when the state machine ticks, not in the wiring.

## Critical Issues

### CR-01: Growth triggers on pause/stop/shutdown outcomes — user input penalises the next session

**File:** `musicstreamer/player.py:1140-1163`
**Issue:**
`_on_underrun_cycle_closed` unconditionally calls `_maybe_grow_buffer_duration()` for **every** cycle-close outcome. The comment at line 1157-1159 explicitly acknowledges this covers `recovered / failover / stop / pause / shutdown`. But `pause()` (line 718-720) and `stop()` (line 757-759) call `tracker.force_close("pause" / "stop")` and emit `_underrun_cycle_closed` — these are user-initiated terminators, not actual buffer-recovery events. The cycle was open because the user pressed pause/stop **during** a buffer underrun, not because growth-worthy recovery happened.

Concrete failure scenario:
1. User plays station A; an underrun cycle opens (buffer drops below 100).
2. User presses Pause before the cycle naturally closes.
3. `tracker.force_close("pause")` queues a cycle_close record; main-thread slot fires `_maybe_grow_buffer_duration` → `_growth_step = 1`, `_pending_buffer_duration_s = 60`.
4. User presses Play again on station A (or any station). `_try_next_stream` applies the pending 60s — even though no recovered underrun ever occurred.

Worse: `shutdown` outcomes (via `shutdown_underrun_tracker` at line 764-784) write the log line SYNCHRONOUSLY and do NOT route through `_on_underrun_cycle_closed`, so growth_step is **not** bumped on shutdown — making the slot's "every outcome" comment factually wrong even within its own design intent. The behavior at line 1162-1163 is therefore inconsistent with the documented intent.

**Fix:**
Gate the growth call on outcome == "recovered" (the only outcome that represents actual queue2 recovery from an underrun):

```python
def _on_underrun_cycle_closed(self, record) -> None:
    self._underrun_dwell_timer.stop()
    _log.info(...)  # existing log line
    self._underrun_event_count += 1
    self.underrun_count_changed.emit(self._underrun_event_count)
    # Phase 84 / D-11: growth fires ONLY on actual recovery, not on
    # user terminators (pause/stop) or queue-advancement events (failover/preroll).
    if record.outcome == "recovered":
        self._maybe_grow_buffer_duration()
```

This also aligns the implementation with the user-facing intent — adaptive growth is a response to network jitter, not a response to UI interactions.

---

### CR-02: Per-URL "reset to baseline" applies the grown value to the new URL, not the baseline

**File:** `musicstreamer/player.py:1280-1282, 1486-1488, 1230-1258`
**Issue:**
The intended semantics, stated in docstrings (line 1232-1238 and the test docstring at `test_try_next_stream_resets_growth_to_baseline:281-291`), are that **each new station starts fresh at the BUFFER_DURATION_S baseline**. The implementation does not achieve this for the *current* bind — only for the bind *after* the current one.

Trace at line 1280-1282:
1. `_apply_pending_buffer_duration_to_pipeline()` — writes the staged value (e.g. 60s from prior growth) to playbin3 and sets `_pending_buffer_duration_s = None`.
2. `_reset_buffer_duration_to_baseline()` — sets `_pending_buffer_duration_s = BUFFER_DURATION_S` (30).
3. Later in `_try_next_stream`, `_set_uri(url)` performs the actual `set_property("uri", ...)`.

playbin3 reads `buffer-duration` at URI-bind time from the property struct. After step 1 the property struct holds **60s**, and step 2 only updates the in-Python `_pending` field — it does NOT write the baseline value to playbin3 before the URI bind. Result: the **new** station opens with the grown buffer (60s), and the baseline gets applied only at the *next* `_try_next_stream` call.

This contradicts the docstring at `_reset_buffer_duration_to_baseline` (line 1244-1248) which claims the baseline is "written to playbin3 at the next `_apply_pending` call — flushes any prior growth value that may have been applied to a previous URL session." The flush happens one URL bind too late.

Same defect at line 1486-1488 (preroll handoff path).

The existing test `test_try_next_stream_resets_growth_to_baseline` does NOT catch this — it asserts on `_pending_buffer_duration_s` and Signal emission only, never on the value written to `_pipeline.set_property("buffer-duration", ...)`. The Pattern 4 hygiene gate likewise only inspects property *names*, not values, so the bug is invisible to the existing test suite.

**Fix:**
Reorder so the reset happens **before** the apply, so the apply writes the baseline (when the reset fired):

```python
# In _try_next_stream (line 1280-1282) and _on_preroll_about_to_finish (line 1486-1488):
# Phase 84 / D-11 per-URL reset MUST run BEFORE the apply so the baseline
# value (not the prior URL's grown value) is what reaches playbin3 at this
# URI bind. Reset stages _pending = BUFFER_DURATION_S; apply then writes it.
self._reset_buffer_duration_to_baseline()
self._apply_pending_buffer_duration_to_pipeline()
```

Add a behavioural test that asserts the **value** written to `set_property("buffer-duration", ...)` at line 1280 equals `BUFFER_DURATION_S * Gst.SECOND` after a growth-then-station-change sequence, not `60 * Gst.SECOND`.

## Warnings

### WR-01: Failover-timeout watchdog still uses baseline `BUFFER_DURATION_S` after growth

**File:** `musicstreamer/player.py:1313, 1372, 1511, 1650, 1727`
**Issue:**
Every `_failover_timer.start(BUFFER_DURATION_S * 1000)` callsite uses the unconditional baseline `BUFFER_DURATION_S` (30s), not `self._current_buffer_duration_s`. After growth bumps the buffer target to 60s or 120s, the watchdog still fires at 30s — meaning a stream that legitimately needs the full 60s to fill its enlarged buffer will be incorrectly failed-over to the next queue entry before it ever has a chance to recover.

This actively defeats Commit B's intent: the larger buffer is supposed to give jittery streams more headroom to recover; the watchdog cancels that headroom.

**Fix:**
Replace the literal at all five callsites with `self._current_buffer_duration_s * 1000`. Add a regression test that bumps `_growth_step` then asserts the failover-timer was started with the grown interval, not the baseline.

---

### WR-02: `set_buffer_duration` formatting is brittle against a future `BUFFER_DURATION_S` bump

**File:** `musicstreamer/ui_qt/now_playing_panel.py:1012-1028`
**Issue:**
The "adapted" suffix logic compares `s == BUFFER_DURATION_S` to decide whether to render `"30s"` or `"60s (adapted)"`. If Phase 85+ ever bumps `BUFFER_DURATION_S` from 30 to 60 (the same value as growth-step-1), the slot would suddenly render the grown 60s value as plain `"60s"` with no "(adapted)" suffix — the user could no longer tell at a glance that adaptive growth had fired. The label semantics depend on a global constant that is precisely the constant most likely to change next.

**Fix:**
Have the Signal carry both the value and a `is_baseline: bool` flag, or have the Player pass `growth_step` as the Signal payload and let the slot derive the label from step != 0. Either decouples the slot from `BUFFER_DURATION_S`.

Minimum acceptable: add a test that monkeypatches `BUFFER_DURATION_S` to 60 and verifies the label still shows "(adapted)" for grown values.

---

### WR-03: `_maybe_grow_buffer_duration` schedule literals via dict-indexed lookup is unnecessarily indirect

**File:** `musicstreamer/player.py:1185-1191`
**Issue:**
```python
self._growth_step += 1
new_s = {1: 60, 2: 120}[self._growth_step]
```
Constructs a new dict on every call just to index it. A direct conditional or tuple lookup is clearer and avoids the dict allocation. More importantly, the dict-literal style obscures the schedule — a maintainer reading this in 6 months has to mentally evaluate the dict construction to see that step 3 (if the cap guard were bypassed) would raise `KeyError`, which is the *opposite* invariant from the cap-guard's silent-no-op intent. If someone refactors the cap guard incorrectly, the failure mode changes from "no-op at cap" to "KeyError at cap".

**Fix:**
```python
_GROWTH_SCHEDULE = (60, 120)  # class-level; _growth_step indexes [step-1]

# In _maybe_grow_buffer_duration:
if self._growth_step >= len(self._GROWTH_SCHEDULE):
    return
new_s = self._GROWTH_SCHEDULE[self._growth_step]  # before increment
self._growth_step += 1
```

This makes the schedule a single class-level constant, ties the cap-guard to the schedule's length (no separate `>= 2` magic number), and surfaces the schedule for future tuning.

---

### WR-04: `_apply_pending` runs unconditionally even when pending equals current playbin3 value

**File:** `musicstreamer/player.py:1223-1228`
**Issue:**
After CR-02's fix, `_reset_buffer_duration_to_baseline` will set `_pending = BUFFER_DURATION_S` on every URL change (because the reset's early-return guard only triggers when growth_step is already 0). For the common case (no growth happened on the prior URL), `_apply_pending` would then re-write the baseline value that playbin3 already holds — a harmless no-op, but it does mean every URL bind incurs an extra property write and (more importantly) makes the call-trace harder to audit.

Coupled with WR-02, the lack of a "did this value actually change" guard means the Signal also re-emits with the same value, which the panel's `set_buffer_duration` does not de-dup.

**Fix:**
Add an idempotency guard in `_apply_pending` and `_reset_buffer_duration_to_baseline` so the no-op case is truly silent. Alternatively, only stage when the value differs from `_current_buffer_duration_s` at the time of staging.

---

### WR-05: `shutdown_underrun_tracker` writes log line directly but bypasses `_maybe_grow_buffer_duration`, creating an inconsistency with CR-01

**File:** `musicstreamer/player.py:764-784`
**Issue:**
This method calls `tracker.force_close("shutdown")` synchronously and writes the log line inline (correct given that closeEvent runs before `QApplication.quit()`). But it does NOT go through `_on_underrun_cycle_closed`, which means it ALSO does not increment `_underrun_event_count`, does not emit `underrun_count_changed`, and does not call `_maybe_grow_buffer_duration`.

After CR-01's fix this becomes consistent (no growth on shutdown is correct). But the absence of `_underrun_event_count += 1` here is a real inconsistency with the slot's "every outcome — recovered / failover / stop / pause / shutdown" comment at line 1157-1159. A shutdown-during-cycle is lost from the cumulative cycle counter even though the log line is written.

If the cumulative counter is intended to track every cycle's existence (regardless of outcome), this method is missing the increment + emit. If it's intended to track only "what user sessions saw" (excluding shutdown), the comment in `_on_underrun_cycle_closed` should say so explicitly.

**Fix:**
Either (a) call `self._underrun_event_count += 1` here and document why no emit happens (no receivers at shutdown), or (b) update the comment at line 1157-1159 to say "every NON-SHUTDOWN outcome" so a future maintainer doesn't add the shutdown call expecting symmetry.

## Info

### IN-01: Inline `from musicstreamer.constants import BUFFER_DURATION_S` inside methods

**File:** `musicstreamer/ui_qt/now_playing_panel.py:1023, 2963`
**Issue:**
Two inline imports of `BUFFER_DURATION_S` inside method bodies. The module already imports many constants at the top. Inline imports are slower (re-resolved per call) and inconsistent with the rest of the file.

**Fix:**
Hoist `from musicstreamer.constants import BUFFER_DURATION_S` to the module top-level import block (next to the existing `cover_art` / `hi_res` imports).

---

### IN-02: Stale `_underrun_event_count: int = 0` comment cross-references Plan 78-02 only

**File:** `musicstreamer/player.py:512-515`
**Issue:**
The block comment at line 512-515 references Phase 78 only. The adjacent Phase 84 growth-state block at line 517-525 is the new neighbour; cross-referencing the two (both are "BUG-09" cycle-related cumulative state) would help a future maintainer.

**Fix:**
Add a one-line comment at the seam: `# See _growth_step block below for the Phase 84 / D-11 sibling state.`

---

### IN-03: Pattern 4 hygiene gate allowlist + banned set should reference each other

**File:** `tests/test_playbin3_property_hygiene.py:71-96`
**Issue:**
The `_ALLOWED_PIPELINE_PROPERTIES` and `_BANNED_SPELLINGS` sets are defined independently. If a future commit adds an entry to one without the other, the gate's failure mode shifts. A defensive `assert _ALLOWED_PIPELINE_PROPERTIES.isdisjoint(_BANNED_SPELLINGS)` at module scope would lock the invariant that no property can be on both lists.

**Fix:**
```python
# Module-level invariant lock:
assert _ALLOWED_PIPELINE_PROPERTIES.isdisjoint(_BANNED_SPELLINGS), (
    "Pattern 4 drift-guard config FAIL: a property appears on both the "
    "allowlist and the banned set."
)
```

---

### IN-04: FakePlayer docstring claims "21 signals total" but list arity disagrees with stated count

**File:** `tests/_fake_player.py:42-47`
**Issue:**
The class docstring says "21 signals total on FakePlayer in Wave 0". Counting the Signal declarations in the file:
- Public: 10 (`title_changed` through `buffer_percent`)
- Internal: 10 (lines 75-84, including `_preroll_about_to_finish_requested`, `_underrun_cycle_opened`, `_underrun_cycle_closed`, `underrun_recovery_started`, `underrun_count_changed`, `buffer_duration_changed`)
- caps: 1 (`audio_caps_detected`)

Total: 21. The count is correct, but the in-line comment at line 71 says "9 — 7 underscore-prefixed + 2 non-underscore: underrun_recovery_started + underrun_count_changed". With Phase 84's addition of `buffer_duration_changed` (line 84), the count is now 10 internal signals (8 + 2 → 7 underscore + 3 non-underscore), not 9. The comment was not refreshed when D-12 added the new signal.

**Fix:**
Update the comment at line 71-74 to: `# Internal cross-thread marshaling signals (10 — 7 underscore-prefixed + 3 non-underscore: underrun_recovery_started + underrun_count_changed + buffer_duration_changed).`

---

_Reviewed: 2026-05-24_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
