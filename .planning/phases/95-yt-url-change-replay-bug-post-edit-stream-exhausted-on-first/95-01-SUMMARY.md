---
phase: 95-yt-url-change-replay-bug-post-edit-stream-exhausted-on-first
plan: 01
subsystem: player
tags: [gstreamer, playbin3, youtube, yt-dlp, qt, signals, failover, generation-guard, pyside6]

# Dependency graph
requires:
  - phase: 27-multi-stream-model
    provides: StationStream / Station multi-stream model + per-station ordered streams
  - phase: 28-stream-failover
    provides: order_streams() failover queue consumed by Player.play()
  - phase: 83-somafm-preroll
    provides: _preroll_seq generation-guard idiom mirrored here for _youtube_resolve_seq
provides:
  - "Player.invalidate_for_edit(station, is_playing) — stale-state invalidation decision method (D-01..D-05)"
  - "_youtube_resolve_seq generation guard — late YouTube resolutions no-op after an edit/restart"
  - "youtube_resolved widened to Signal(str, bool, int) carrying the resolve generation"
  - "MainWindow._sync_now_playing_station notifies the Player on every committed edit"
affects: [player, edit-station, youtube, failover, now-playing]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Generation guard for stale async results (mirrors _preroll_seq): bump on restart/invalidate, capture at worker spawn, reject deliveries whose stamp != current"
    - "Pass-and-let-player-decide: MainWindow forwards the updated station unconditionally; the Player owns the id-match / URL-diff decision in one place"

key-files:
  created:
    - tests/test_player_edit_invalidation.py
  modified:
    - musicstreamer/player.py
    - musicstreamer/ui_qt/main_window.py
    - tests/_fake_player.py
    - tests/test_main_window_integration.py
    - tests/test_player_failover.py

key-decisions:
  - "D-01 restart reuses Player.play(station) — no hand-rolled partial queue reset"
  - "URL comparison uses raw .strip() equality on the STORED StationStream.url, never the resolved playbin3 URI (Pitfall 3)"
  - "Q3: Signal-carry approach for the YT resolve guard (widen youtube_resolved arity), mirroring _preroll_seq for auditability"
  - "Q1: D-01-vs-D-05 gated on the panel's is_playing passed into invalidate_for_edit (Player has no playback-state field)"
  - "Q2: deleted playing-stream while live re-issues play(updated_station); play()'s no-streams guard handles the all-deleted case"

patterns-established:
  - "YouTube resolve-generation guard: _youtube_resolve_seq bumped in play() entry path and in invalidate_for_edit; _on_youtube_resolved returns early on stale seq"
  - "FakePlayer parity drift-guard self-enforces Signal arity changes within the same wave"

requirements-completed: []

# Metrics
duration: ~25min
completed: 2026-06-18
---

# Phase 95 Plan 01: invalidate_for_edit + YT resolve-seq guard Summary

**Stale-player-state invalidation on stream edit — first play after a URL change now uses the saved URL, with a `_youtube_resolve_seq` generation guard so a late YouTube resolution can never resurface the old URL.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-06-18 (session start)
- **Completed:** 2026-06-18
- **Tasks:** 3 (RED → GREEN → wire)
- **Files modified:** 5 (1 created, 4 modified)

## Accomplishments
- `Player.invalidate_for_edit(station, is_playing)` implements the full D-01..D-05 decision tree: restart on playing-stream URL change (D-01), no-op on metadata-only/same-URL edits (D-02/V4), queue-invalidate on non-playing sibling edits (D-04), fresh-rebuild reset when idle (D-05), and survivor-restart on deleted playing stream (Q2/V10).
- `_youtube_resolve_seq` generation guard added to the YouTube resolve path (declared alongside `_preroll_seq`, widened `youtube_resolved` to `Signal(str, bool, int)`, captured at worker spawn, rejected on stale delivery in `_on_youtube_resolved`) — kills the in-flight-resolution race (V5).
- MainWindow `_sync_now_playing_station` now notifies the Player on every committed edit, closing the panel-only gap that caused the "stream exhausted on first play" bug.
- FakePlayer mirrors the widened signal arity and exposes an `invalidate_for_edit` recording stub; the parity drift-guard stays green.

## Task Commits

Each task was committed atomically (TDD: test → feat → feat):

1. **Task 1: Wave-0 RED tests + FakePlayer parity stub** - `96488e0f` (test)
2. **Task 2: GREEN — Player.invalidate_for_edit + _youtube_resolve_seq guard** - `9f1ccdd3` (feat, includes Rule 1 test-arity fix)
3. **Task 3: Wire invalidate_for_edit into _sync_now_playing_station** - `ac6028b3` (feat)

_TDD note: the plan's RED/GREEN gate sequence is satisfied — `test(95-01)` (RED) precedes `feat(95-01)` (GREEN)._

## Files Created/Modified
- `tests/test_player_edit_invalidation.py` (created) - Player-unit coverage V1-V6, V10 + unrelated-station no-op; copies the `make_player`/`make_stream`/`make_station_with_streams` harness from test_player_failover.py.
- `musicstreamer/player.py` (modified) - `_youtube_resolve_seq` decl; `youtube_resolved` widened to `Signal(str, bool, int)`; seq captured in `_play_youtube`, carried through `_youtube_resolve_worker` → emit → `_on_youtube_resolved` (stale-seq early return); new `invalidate_for_edit` method.
- `musicstreamer/ui_qt/main_window.py` (modified) - `_sync_now_playing_station` calls `self._player.invalidate_for_edit(updated_station, is_playing=self.now_playing.is_playing)` unconditionally on a valid station.
- `tests/_fake_player.py` (modified) - `youtube_resolved` arity widened to mirror player.py; `invalidate_calls` list + `invalidate_for_edit` stub.
- `tests/test_main_window_integration.py` (modified) - V7 integration assertion on the sync→invalidate junction (closes the MainWindow to stop the GBS marquee QThread on teardown).
- `tests/test_player_failover.py` (modified) - Rule 1 fix: updated the `youtube_resolved` emit-args assertion to the new 3-arg arity.

## Decisions Made
- Followed the plan's resolved choices Q1/Q2/Q3 exactly. URL comparison uses raw `.strip()` on the stored `StationStream.url` (never the resolved URI). The restart path delegates to `play()` rather than reimplementing the queue rebuild.
- The seq bump in `invalidate_for_edit` happens unconditionally first (even for metadata-only or unrelated-station edits) — harmless when no resolution is pending, and it guarantees any pre-edit in-flight resolution no-ops.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_player_failover youtube_resolved emit-arity assertion**
- **Found during:** Task 2 (GREEN — scoped regression run)
- **Issue:** `test_youtube_resolve_success_sets_uri_and_arms_failover` asserted `blocker.args == [url, False]` against the old 2-arg `youtube_resolved` signature; the planned arity widening to `Signal(str, bool, int)` made the worker emit a 3rd arg (`seq=0`), breaking the assertion.
- **Fix:** Updated the assertion to `[url, False, 0]` and refreshed the explanatory comment.
- **Files modified:** tests/test_player_failover.py
- **Verification:** `tests/test_player_failover.py` + `tests/test_player.py` → 86 passed.
- **Committed in:** `9f1ccdd3` (Task 2 commit)

**2. [Rule 3 - Blocking] V7 integration test must close the MainWindow**
- **Found during:** Task 3 (V7 verify)
- **Issue:** The V7 test constructs a real MainWindow, which starts the GBS marquee QThread (`main_window.py:585`). Without `w.close()` the thread is still running at interpreter teardown and aborts the process — blocking the V7 assertion from being observed.
- **Fix:** Added `w.close()` at the end of the V7 test (mirrors the existing `closeEvent` cleanup pattern at main_window.py:853 and the `w.close()` usage already in this module).
- **Files modified:** tests/test_main_window_integration.py
- **Verification:** V7 test passes standalone (`1 passed`).
- **Committed in:** `ac6028b3` (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (1 bug from the planned arity change, 1 blocking test-teardown).
**Impact on plan:** Both essential to land the planned behavior; no scope creep.

## Issues Encountered
- **Pre-existing (OUT OF SCOPE):** `tests/test_main_window_integration.py` aborts/segfaults at Qt teardown when the full module (or the combined phase-gate suite) runs, originating at `gbs_marquee.py:657 run` (a leaked marquee QThread). Confirmed pre-existing: `test_window_default_size` — which constructs a MainWindow without `w.close()` and is untouched by this phase — aborts on the pristine baseline with the Task-3 edit stashed. This matches the project MEMORY note ("full suite >600s; two known pre-existing failures"). All phase-relevant modules pass individually: test_player_edit_invalidation (9), test_player_failover (27), test_player (59), test_edit_station_dialog (96), test_fake_player_signal_parity (2), and the integration edit/sync/invalidate subset (2). Logged here rather than fixed (deferred — broader test-teardown hygiene is unrelated to the YT replay bug).

## Threat Flags
None — no new network endpoints, auth paths, or trust-boundary surface. The restart re-feeds an already-user-controlled URL through the existing `play()`→`_set_uri` path (threat register T-95-01 disposition: accept; T-95-02 mitigate via the CPython-atomic seq int on a queued Signal).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The YT URL-change replay bug fix is complete end-to-end (unit V1-V6/V10 + integration V7 + parity V9). Manual end-to-end verification (95-VALIDATION.md Manual-Only): play a YouTube station, edit its URL to a different valid source, save → new audio should start immediately with no "stream exhausted" toast and no second play.
- No blockers for downstream work. The pre-existing integration-module teardown abort is a candidate for a separate test-hygiene cleanup.

---
*Phase: 95-yt-url-change-replay-bug-post-edit-stream-exhausted-on-first*
*Completed: 2026-06-18*
