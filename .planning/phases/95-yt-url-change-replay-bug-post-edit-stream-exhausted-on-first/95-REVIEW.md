---
phase: 95-yt-url-change-replay-bug-post-edit-stream-exhausted-on-first
plan: 95-03
reviewed: 2026-06-20T18:39:49Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - musicstreamer/player.py
  - tests/test_player_edit_invalidation.py
findings:
  critical: 1
  warning: 4
  info: 1
  total: 6
status: issues_found
---

# Phase 95 (95-03): Code Review Report

**Reviewed:** 2026-06-20T18:39:49Z
**Depth:** standard (ultracode — all dimensions + adversarial refutation pass)
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Reviewed the Phase 95-03 gap-closure change: the `_youtube_resolve_in_flight`
gate added to `musicstreamer/player.py` and its V14/V15/V16 (plus reconciled
V12) regression tests in `tests/test_player_edit_invalidation.py`.

The gate is correctly placed for the single-generation case (a YouTube resolve
that succeeds or fails without an intervening restart). The success-path
staleness guard in `_on_youtube_resolved` is sound because it uses the
per-worker `seq` carried through the `youtube_resolved` Signal.

However, the **failure-path staleness guard is broken** and the gate **leaks
permanently** in the two real-world restart paths that this phase exists to
fix. The root cause is an asymmetry: the success path carries a per-worker
generation stamp through the Signal, but the failure path
(`youtube_resolution_failed = Signal(str)`) carries no stamp and instead
compares the **instance attribute** `_youtube_resolve_in_flight_seq`, which is
overwritten by every `_play_youtube` call and is only ever advanced by
`invalidate_for_edit` (never by `play()`). The V16 stale-failure test passes
only because its setup diverges from the real call path (it bumps
`_youtube_resolve_seq` without calling `_play_youtube`, so the instance stamp is
never updated the way production updates it).

This is a correctness BLOCKER: the same "spurious Stream exhausted" / "stuck
gate" symptom the gate was added to eliminate is still reachable.

## Critical Issues

### CR-01: Failure-path staleness guard is ineffective; in-flight gate leaks permanently across restarts

**File:** `musicstreamer/player.py:2096-2102` (guard), `musicstreamer/player.py:1965-1966` (stamp write), `musicstreamer/player.py:274` (Signal arity)

**Issue:**

`_on_youtube_resolution_failed` detects a stale (superseded) failure delivery by
comparing two **instance attributes**:

```python
if self._youtube_resolve_in_flight_seq != self._youtube_resolve_seq:
    return  # stale generation
```

`_youtube_resolve_in_flight_seq` is written in `_play_youtube` (line 1966) on
**every** spawn:

```python
self._youtube_resolve_in_flight = True
self._youtube_resolve_in_flight_seq = seq        # seq == current _youtube_resolve_seq
```

Two facts break the guard:

1. **`_youtube_resolve_seq` is bumped ONLY in `invalidate_for_edit`** (line 2136).
   `play()` (lines 712-753) does NOT bump it. So a normal station->station
   switch, or any restart that is not an edit, leaves `_youtube_resolve_seq`
   unchanged.

2. **`_youtube_resolve_in_flight_seq` is overwritten by the newer
   `_play_youtube`** before the old generation's failure callback is delivered.
   At delivery time the stored stamp already equals the current
   `_youtube_resolve_seq`, so the stale failure is treated as current.

**Three concrete failures (all survive refutation against the source):**

*Leak — permanent suppression of genuine exhaustion (edit to non-YouTube URL):*
1. Station A (YouTube) playing -> `_play_youtube` sets gate=True,
   `in_flight_seq=0`, `_youtube_resolve_seq=0`.
2. User edits the URL to a **non-YouTube direct stream**. `invalidate_for_edit`
   bumps `_youtube_resolve_seq`->1 and calls `play()`. `_try_next_stream` takes
   the `_set_uri` branch (line 1587) — `_play_youtube` is never called, so the
   gate is **never re-armed or cleared** and `in_flight_seq` stays 0.
3. Station A's old worker fails -> `_on_youtube_resolution_failed`:
   `in_flight_seq(0) != _youtube_resolve_seq(1)` -> early return (treated as
   stale). Gate stays True forever.
4. The new direct stream now plays with `_youtube_resolve_in_flight == True`
   stuck. On any later real failure, `_handle_gst_error_recovery` hits
   `if self._youtube_resolve_in_flight: return` (line 1075) and `_try_next_stream`
   returns at the empty-queue gate (line 1538): **no failover advance and no
   "Stream exhausted" toast, ever.** Audio silently dies with no recovery.

*Spurious exhaustion — the original UAT bug, still reproducible (YouTube->YouTube
station switch):*
1. Station A (YouTube): `_play_youtube` -> gate=True, `in_flight_seq=0`,
   `_youtube_resolve_seq=0`.
2. User clicks Station B (YouTube) -> `play(B)` (no resolve_seq bump) ->
   `_try_next_stream` -> `_play_youtube(B)` -> gate=True, `in_flight_seq=0`,
   `_youtube_resolve_seq=0`.
3. Station A's old worker fails late -> `_on_youtube_resolution_failed`:
   `in_flight_seq(0) == _youtube_resolve_seq(0)` -> NOT stale -> clears the gate
   that belongs to B and calls `_try_next_stream` on B's transiently-empty queue
   -> `failover.emit(None)` "Stream exhausted" while B is still resolving.

*Spurious exhaustion — YouTube->YouTube via edit:*
`invalidate_for_edit` bumps resolve_seq->1, then `play()`->`_play_youtube`
writes `in_flight_seq=1`. The old gen-0 failure then sees
`in_flight_seq(1) == _youtube_resolve_seq(1)` -> treated as current -> clears the
new gate and emits spurious exhaustion.

**Fix:** Carry the per-worker generation stamp on the failure path exactly as the
success path does, instead of reading a mutable instance attribute. Add `seq` to
the failure Signal and stamp it in the worker:

```python
# class attribute
youtube_resolution_failed = Signal(str, int)   # (msg, resolve_seq)

# in _youtube_resolve_worker — every failure emit carries the captured seq:
self.youtube_resolution_failed.emit(str(e), seq)
self.youtube_resolution_failed.emit("No video formats returned", seq)
self.youtube_resolution_failed.emit(f"youtube resolve crashed: {e!r}", seq)

# handler keyed off the carried stamp (mirrors _on_youtube_resolved):
def _on_youtube_resolution_failed(self, msg: str, seq: int = -1) -> None:
    if seq != -1 and seq != self._youtube_resolve_seq:
        return  # stale generation — superseded
    self._youtube_resolve_in_flight = False
    self.playback_error.emit(f"YouTube resolve failed: {msg}")
    self._try_next_stream()
```

Additionally, **bump `_youtube_resolve_seq` in `play()`** (next to the existing
`self._recovery_seq += 1` at line 725) so every restart — not just edits —
invalidates in-flight YouTube resolutions for both the success and failure
paths. Without this bump the success path also mis-fires (see WR-01).

The instance attribute `_youtube_resolve_in_flight_seq` should then be removed
(it becomes dead state once the stamp travels on the Signal). NOTE: the comments
at lines 2087-2090 explicitly chose the instance-attribute approach to avoid a
Signal arity change; that trade-off is precisely what introduces this bug, so
the arity change is the correct fix.

## Warnings

### WR-01: `play()` does not bump `_youtube_resolve_seq`, so the success-path staleness guard also fails on station-switch

**File:** `musicstreamer/player.py:712-725` and `musicstreamer/player.py:2072-2073`

**Issue:** The 95-01 success-path guard (`if seq != self._youtube_resolve_seq:
return`) relies on `_youtube_resolve_seq` advancing on each restart. It only
advances in `invalidate_for_edit`. For a plain Station A (YouTube) -> Station B
(YouTube) switch via `play()`, both workers capture `seq == 0`, so Station A's
late `youtube_resolved` delivery passes the guard and `_set_uri`s Station A's
resolved URL over Station B. This is the same class of bug as CR-01 on the
success side and is fixed by the same `play()` bump.

**Fix:** Add `self._youtube_resolve_seq += 1` alongside `self._recovery_seq += 1`
at line 725 so every restart invalidates in-flight resolutions regardless of
whether the restart came from an edit or a fresh play.

### WR-02: V16 stale-failure test gives false confidence — its setup cannot occur in production

**File:** `tests/test_player_edit_invalidation.py:608-650`
(`test_v16_stale_resolution_failed_does_not_clear_gate_or_advance`)

**Issue:** The test simulates a stale failure by doing
`p._youtube_resolve_seq += 1` and `p._youtube_resolve_in_flight = True` **without
calling `_play_youtube`**, leaving `_youtube_resolve_in_flight_seq` at its
initial 0. That makes `in_flight_seq(0) != _youtube_resolve_seq(1)` true and the
guard fires. But in real code the new generation is always started via
`_play_youtube`, which overwrites `_youtube_resolve_in_flight_seq` to the new
value — so the guard never fires in production (see CR-01). The test passes while
the code is broken. The `hasattr(p, "_youtube_resolve_in_flight_seq")` branch
(lines 635-644) is also dead/no-op: both branches call the identical
`p._on_youtube_resolution_failed("...")` and the captured `old_stored`
(line 637) is never used.

**Fix:** After applying CR-01, drive the stale scenario through the real call
path: spawn a first resolve (with the worker thread patched so no real `yt_dlp`
runs), bump the generation via a second `_play_youtube`/`play()`, then deliver
the OLD generation's failure with the OLD `seq` argument
(`p._on_youtube_resolution_failed("old stream ended", stale_seq)`). Assert the
gate stays True and `_try_next_stream` is not called. Remove the dead
`hasattr`/`old_stored` branch.

### WR-03: V14/V15/V16 set the gate by direct attribute poke, never exercising `_play_youtube`'s gate arming

**File:** `tests/test_player_edit_invalidation.py:482, 490, 547, 572, 593, 623`

**Issue:** Every gate-related test sets `p._youtube_resolve_in_flight = True`
manually rather than driving it through `_play_youtube`. No test verifies that
`_play_youtube` actually arms the gate (line 1965) or that the
gate/`in_flight_seq` pair is set together and consistently. Because the tests
bypass the spawn path entirely, the production asymmetry in CR-01/WR-01 is
invisible to the suite. The CR-01 leak (gate stuck True after a non-YouTube
restart) would not be caught by any current test.

**Fix:** Add a test that calls `_play_youtube` (with the worker thread
mocked/patched) and asserts `_youtube_resolve_in_flight is True` and
`_youtube_resolve_in_flight_seq == _youtube_resolve_seq`. Add a regression test
for the CR-01 leak: YouTube playing -> edit URL to a direct (non-YouTube) stream
-> old worker failure -> assert the gate is cleared (not stuck True) and a later
genuine exhaustion still emits `failover(None)`.

### WR-04: Gate check in `_try_next_stream` only guards the empty-queue branch, leaving gate semantics inconsistent

**File:** `musicstreamer/player.py:1533-1542`

**Issue:** The `_youtube_resolve_in_flight` check sits **inside** the
`if not self._streams_queue:` block. When the gate is set but the queue is
non-empty, `_try_next_stream` still pops and starts the next stream while a
resolve is "in flight," and the gate remains True. Combined with the CR-01 leak
(gate stuck True), this produces inconsistent behavior: `_handle_gst_error_recovery`
is fully blocked by the gate (line 1075) while `_try_next_stream` is only
partially blocked. The intent ("the pending resolve owns the next transition")
is not uniformly enforced — a latent correctness/maintainability hazard.

**Fix:** Once CR-01 is fixed (gate can no longer leak), document the invariant
"gate True => exactly one resolve owns the next transition" and either gate the
whole `_try_next_stream` entry or assert the gate is clear on the non-empty path
so the two consult sites agree.

## Info

### IN-01: Stale-bool atomicity comment is misleading — all gate access is main-thread

**File:** `musicstreamer/player.py:613-615` and `2096`

**Issue:** The comment "CPython-atomic bool read (same as `_preroll_in_flight`)"
implies cross-thread access. In fact `_youtube_resolve_in_flight` is written in
`_play_youtube` (main thread) and the settle handlers (queued to main), and read
in `_handle_gst_error_recovery`/`_try_next_stream` (main). There is no
cross-thread read of this gate, so the atomicity justification is inaccurate and
could mislead a future maintainer.

**Fix:** Reword the comment to state that all gate access is on the main thread
(set on spawn, cleared on queued settle, read on the recovery/advance path), so
no atomicity argument is needed.

---

_Reviewed: 2026-06-20T18:39:49Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard (ultracode)_
