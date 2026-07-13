---
phase: 95-yt-url-change-replay-bug-post-edit-stream-exhausted-on-first
plan: "04"
subsystem: player
tags: [gap-closure, tdd, youtube, resolve, exhaustion-gate, carried-seq, phase-95, cr-01]
dependency_graph:
  requires: [95-01, 95-02, 95-03]
  provides: [carried-seq failure staleness, play() resolve-seq bump, _set_uri gate clear, stop() gate clear, _youtube_resolve_in_flight_seq removed]
  affects: [musicstreamer/player.py, tests/_fake_player.py, tests/test_player_edit_invalidation.py]
tech_stack:
  added: []
  patterns:
    - "Carried Signal payload for per-worker generation stamp (mirrors youtube_resolved success-path pattern)"
    - "Monotonic seq bump at every restart entry (play() + stop()) to invalidate all prior in-flight generations"
    - "Idempotent gate clear at URI funnel (_set_uri) guards every non-YouTube restart path"
    - "TDD RED/GREEN: failing tests first (V16c/V16d/V17/V18/V19), then implementation"
key_files:
  created: []
  modified:
    - musicstreamer/player.py
    - tests/_fake_player.py
    - tests/test_player_edit_invalidation.py
decisions:
  - "youtube_resolution_failed widened to Signal(str, int) to carry per-worker seq stamp — the 95-03 decision to avoid arity change (instance-attribute approach) is reversed because the instance-attribute approach is the root cause of CR-01 (overwritten on every _play_youtube before old delivery lands)"
  - "play() bumps _youtube_resolve_seq alongside _recovery_seq so a plain station A->B switch also invalidates an in-flight A-resolve; invalidate_for_edit's pre-delegation bump harmlessly double-bumps (monotonic counter, equality compare)"
  - "stop() both clears _youtube_resolve_in_flight AND bumps _youtube_resolve_seq so any worker still in flight when stop() was called has its late failure rejected stale"
  - "_set_uri gate clear is idempotent for the success path (_on_youtube_resolved already clears at :2076 before calling _set_uri) and only fires for the direct-stream-restart path that bypasses _play_youtube"
  - "_on_youtube_resolution_failed seq=-1 default exempts no-arg direct test callers (mirrors _on_youtube_resolved seq=0 idiom); -1 chosen over 0 to avoid false-current classification if _youtube_resolve_seq is still at 0"
  - "V16d reconciled to drive real _play_youtube arming (patched thread) then bump generation via direct _youtube_resolve_seq += 1 between the two _play_youtube calls — mirrors what play() does in production; the second call alone does not bump seq"
metrics:
  duration: "~8m"
  completed: "2026-06-20"
  tasks_completed: 2
  files_modified: 3
---

# Phase 95 Plan 04: Carried-Seq Failure Staleness + play() Bump + Gate-Leak Reset Summary

**One-liner:** CR-01 closed — `youtube_resolution_failed` widened to `Signal(str, int)` carrying a per-worker generation stamp, `play()` and `stop()` bump `_youtube_resolve_seq`, `_set_uri` and `stop()` clear `_youtube_resolve_in_flight`, and the overwrite-prone `_youtube_resolve_in_flight_seq` instance attribute is removed.

## What Was Built

Phase 95-04 closes CR-01 (BLOCKER, 95-REVIEW.md, verified 2026-06-20): the 95-03 `_youtube_resolve_in_flight` gate had two correctness holes that made the original "spurious Stream exhausted" / "stuck gate" symptom still reachable.

### Root Cause (CR-01)

The failure path (`youtube_resolution_failed = Signal(str)`) carried no generation stamp. Staleness was detected via the instance attribute `_youtube_resolve_in_flight_seq`, which was **overwritten by every `_play_youtube` call** before the old worker's failure was delivered. At delivery time the stored stamp equalled the current `_youtube_resolve_seq`, so every stale failure was classified as current. Additionally, `play()` never bumped `_youtube_resolve_seq` (only `invalidate_for_edit` did), so a plain YouTube A->B station switch left both workers sharing generation 0.

**Leak path** (edit YouTube → direct URL mid-resolve): the `_set_uri` branch never cleared the gate, so the old YouTube worker's failure early-returned (the seq-mismatch guard fired), leaving `_youtube_resolve_in_flight = True` permanently. All future failovers were silently suppressed.

**Spurious-exhaustion path** (YouTube A→B switch): because `play()` didn't bump the seq, A and B shared generation 0. A's late failure passed the guard, cleared B's fresh gate, and called `_try_next_stream` on B's transiently-empty queue → spurious `failover(None)`.

**False-green test (V16d)**: drove the stale scenario by directly poking `_youtube_resolve_seq` without calling `_play_youtube`, producing a state never reachable in production (the instance attr was never updated), so CI was green while the code was broken.

### Implementation Details

**1. Signal arity widened** (`musicstreamer/player.py:274`):
```python
youtube_resolution_failed = Signal(str, int)  # (msg, resolve_seq) — mirrors youtube_resolved
```

**2. All three worker failure emits carry `seq`** (`_youtube_resolve_worker`):
```python
self.youtube_resolution_failed.emit(str(e), seq)
self.youtube_resolution_failed.emit("No video formats returned", seq)
self.youtube_resolution_failed.emit(f"youtube resolve crashed: {e!r}", seq)
```

**3. `_on_youtube_resolution_failed` rewritten** with carried-seq guard:
```python
def _on_youtube_resolution_failed(self, msg: str, seq: int = -1) -> None:
    if seq != -1 and seq != self._youtube_resolve_seq:
        return  # stale generation — superseded
    self._youtube_resolve_in_flight = False
    self.playback_error.emit(f"YouTube resolve failed: {msg}")
    self._try_next_stream()
```
The `-1` default exempts no-arg direct test callers (mirrors `_on_youtube_resolved`'s `seq=0` default). `-1` chosen over `0` to avoid false-current on a freshly-initialized player.

**4. `play()` bumps `_youtube_resolve_seq`** alongside `_recovery_seq`:
- Every restart (not only edits via `invalidate_for_edit`) advances the YouTube generation.
- `invalidate_for_edit`'s pre-delegation bump double-bumps harmlessly (monotonic counter, equality compare at both ends, no off-by-one risk).

**5. `_set_uri` clears `_youtube_resolve_in_flight = False`** at method entry:
- `_set_uri` is the direct/non-YouTube URI funnel: every direct-stream restart calls it.
- Idempotent for the success path (`_on_youtube_resolved` already clears the gate at its seq-guard exit before calling `_set_uri`).
- Guarantees the YouTube→direct restart path cannot strand the gate.
- Does NOT regress V14: the `_try_next_stream` gate consult runs BEFORE `_set_uri` is ever reached.

**6. `stop()` clears `_youtube_resolve_in_flight = False` AND bumps `_youtube_resolve_seq`**:
- Gate clear: a stranded gate from a prior `_play_youtube` is always reset on stop.
- Seq bump: a YouTube worker still in flight when `stop()` is called has its late failure rejected stale (carried seq < new `_youtube_resolve_seq`), preventing a spurious `failover(None)` into a stopped player (closes IN-01 advisory from 95-REVIEW.md).

**7. `_youtube_resolve_in_flight_seq` fully removed**:
- Declaration deleted from `__init__`.
- Write in `_play_youtube` (`self._youtube_resolve_in_flight_seq = seq`) deleted.
- No executable `self._youtube_resolve_in_flight_seq` references remain in `musicstreamer/player.py`.
- The docstring/comment references explaining the removal are intentional documentation.

**8. FakePlayer parity** (`tests/_fake_player.py:65`):
```python
youtube_resolution_failed = Signal(str, int)  # Phase 95-04: widened to (msg, resolve_seq)
```
Updated in the same plan; `tests/test_fake_player_signal_parity.py` GREEN.

## V16c/V16d Reconciliation + V17/V18/V19 Coverage

**V16c (updated)**: now passes the carried current seq (`p._youtube_resolve_seq`) to `_on_youtube_resolution_failed`; also asserts the no-arg form (`seq=-1` default) still passes the guard. Both legs GREEN.

**V16d (reconciled — was false-green)**: drives the REAL `_play_youtube` arming path via `patch("musicstreamer.player.threading.Thread")`, captures `stale_seq`, bumps `_youtube_resolve_seq` (simulating what `play()` does in production), calls `_play_youtube` again to arm the new generation, then delivers the OLD seq as a carried argument. The `hasattr`/`old_stored` dead branch is removed. GREEN.

**V17 (CR-01 leak regression)**: arms gate N via `_play_youtube` (patched), simulates edit-to-direct restart (bump seq + `_set_uri`), asserts gate cleared; delivers stale failure (rejected); drives genuine exhaustion with cleared gate → `failover(None)` fires once. GREEN.

**V18 (CR-01 spurious-exhaustion regression)**: arms A (capture `seq_a`), bumps `_youtube_resolve_seq` + arms B (simulating `play()` semantics), delivers A's late failure with `seq_a` → B's gate stays True, NO `failover(None)`. GREEN.

**V19 (stop() gate cleanup)**: Part A — manual gate True → `stop()` → gate False. Part B — arms worker, captures `seq_a`, calls `stop()` (which bumps seq), delivers late failure carrying `seq_a` → rejected stale, no `failover(None)`. GREEN.

## Tests (TDD Red/Green)

**RED commit (06cdc5dd):** V16c/V16d/V17/V18/V19 added or updated; 5 tests FAIL for the CR-01 reasons (arity TypeError, gate not cleared, spurious failover). V1..V15, V16a, V16b unchanged and passing.

**GREEN commit (1ac58133):** Implementation landed. 23 tests pass (21 edit-invalidation + 2 parity).

### Test Coverage

| Test | Scenario | Result |
|------|----------|--------|
| V1..V15, V16a/b | All prior Phase 95-01/02/03 wins | GREEN |
| V16c | Current-gen failure with carried seq clears gate + failover(None); no-arg also passes | GREEN |
| V16d | Real `_play_youtube` arming + stale carried seq rejected (gate stays True) | GREEN |
| V17 | YouTube→direct restart clears gate; stale failure rejected; genuine exhaustion still fires | GREEN |
| V18 | Same-gen A→B switch — A's stale failure rejected, B's gate stays True, no spurious emit | GREEN |
| V19 | stop() clears stranded gate; stop() bumps seq, post-stop failure rejected stale | GREEN |
| parity | FakePlayer youtube_resolution_failed Signal(str, int) arity matches player.py | GREEN |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] V16d test needed explicit `_youtube_resolve_seq += 1` between two `_play_youtube` calls**
- **Found during:** Task 1 RED → Task 2 GREEN (V16d still failing after GREEN implementation)
- **Issue:** V16d called `_play_youtube` twice without bumping `_youtube_resolve_seq` between them. Since `_play_youtube` itself doesn't bump the seq (that's `play()`'s job), both calls used the same generation. The stale failure (`stale_seq`) equalled the current seq and passed the guard, calling `_try_next_stream`.
- **Fix:** Added `p._youtube_resolve_seq += 1` between the two `_play_youtube` calls in V16d to simulate what `play()` does in production. The test comment was updated to explain this pattern.
- **Files modified:** `tests/test_player_edit_invalidation.py`
- **Commit:** included in GREEN commit `1ac58133`

## Known Stubs

None — all gate logic is fully wired. Tests exercise the actual production code paths through the real `_play_youtube` arming path (patched worker thread).

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. The carried seq travels on the Signal payload (QueuedConnection); all gate and seq accesses remain on the Qt main thread. The only trust boundary change is that the `youtube_resolution_failed` Signal now carries an `int` — this is an additive widening that existing PySide6 Signal infrastructure handles transparently. No new cross-thread shared mutable state introduced; the removed `_youtube_resolve_in_flight_seq` was the only attribute whose cross-call mutation caused the bug.

## Threat Register Disposition

| Threat ID | Disposition |
|-----------|-------------|
| T-95-04-01 (DoS — gate stranded True, future failovers suppressed) | MITIGATED: `_set_uri` + `stop()` clear the gate; stale failures rejected via carried seq. V17 + V19 pin both paths. |
| T-95-04-02 (Tampering — stale failure mis-classified, spurious failover) | MITIGATED: Carried seq guards; `play()` bumps seq on every restart. V16d + V18 pin stale rejection. |
| T-95-04-03 (Tampering — genuine exhaustion over-suppressed) | MITIGATED: Guard only rejects mismatched generations; V15 + V17 genuine-exhaustion leg assert empty queue + cleared gate still toasts. |
| T-95-04-04 (Tampering — Signal arity drift FakePlayer vs Player) | MITIGATED: `tests/_fake_player.py` updated in same plan; parity guard GREEN. |

## Self-Check

### Created files exist
- `.planning/phases/95-yt-url-change-replay-bug-post-edit-stream-exhausted-on-first/95-04-SUMMARY.md` — this file

### Commits exist
- `06cdc5dd` — RED commit (test(95-04): add failing V17/V18/V19 + reconcile V16c/V16d)
- `1ac58133` — GREEN commit (feat(95-04): close CR-01 — carried-seq failure staleness...)

### Source assertions verified
- `youtube_resolution_failed = Signal(str, int)` in both `player.py` and `_fake_player.py` ✓
- All three worker failure emits carry `seq` ✓
- `_on_youtube_resolution_failed(self, msg, seq=-1)` with carried-seq guard ✓
- `_youtube_resolve_seq += 1` in `play()`, `stop()`, and `invalidate_for_edit` (3 sites) ✓
- `_youtube_resolve_in_flight = False` in `stop()`, `_set_uri`, `_on_youtube_resolution_failed`, `_on_youtube_resolved` (4 sites) ✓
- No `self._youtube_resolve_in_flight_seq` in executable code ✓
- 95-01 (`_on_youtube_resolved` seq guard), 95-02 (`_recovery_seq` guard), `_try_next_stream` gate consult, `_handle_gst_error_recovery` early-return all intact ✓

## Self-Check: PASSED

- [x] `musicstreamer/player.py`: Signal widened, emits carry seq, handler rewritten, play() + stop() bump seq, _set_uri + stop() clear gate, dead attr removed
- [x] `tests/_fake_player.py`: youtube_resolution_failed = Signal(str, int) parity
- [x] `tests/test_player_edit_invalidation.py`: V16c/V16d updated, V17/V18/V19 added
- [x] `06cdc5dd` (RED commit) exists
- [x] `1ac58133` (GREEN commit) exists
- [x] 23 tests pass: `23 passed, 1 warning in 0.20s`
- [x] FakePlayer parity guard: 2 passed
- [x] V5 (play() double-bump on edit path): PASSED (harmless)
- [x] 95-01/95-02 guards intact
