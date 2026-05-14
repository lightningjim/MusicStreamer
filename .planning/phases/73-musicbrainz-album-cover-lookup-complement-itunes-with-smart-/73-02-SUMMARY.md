---
phase: 73-musicbrainz-album-cover-lookup-complement-itunes-with-smart-
plan: 02
subsystem: cover-art
tags: [musicbrainz, cover-art-archive, urllib, threading, rate-gate, lucene-escape, worker-thread, importlib-metadata]

# Dependency graph
requires:
  - phase: 73-01
    provides: "Station.cover_art_source field; ALTER TABLE migration; 6 MB JSON fixtures; 10 xfail-marked RED scaffolds in test_cover_art_mb.py; pinned _spawn_worker contract"
provides:
  - "musicstreamer/cover_art_mb.py — single-public-entry MB+CAA worker module (~480 lines)"
  - "fetch_mb_cover(artist, title, callback) — public entry honoring D-07..D-20"
  - "_MbGate — monotonic-floor 1-req/sec rate gate singleton (_GATE)"
  - "_escape_lucene — single-pass Lucene-special-char escape (Pitfall 10 safe)"
  - "_pick_recording — score>=80 filter + earliest-first canonical sort"
  - "_pick_release_mbid — D-10 ladder steps 1+2 (Official+Album, then any Official)"
  - "_genre_from_tags — highest-count MB tag with '' on no-tags (Pitfall 3 safe)"
  - "_spawn_worker — pinned test seam for thread spawning (ART-MB-06 contract)"
  - "Latest-wins single-spawn semantics: _in_flight flag + _pending queue.Queue(maxsize=1)"
  - "11 GREEN tests in tests/test_cover_art_mb.py (10 from Plan 01 RED flipped + 1 new Lucene injection regression)"
affects:
  - "73-03: router plan — will call fetch_mb_cover(icy_string, callback) from cover_art.fetch_cover_art's MB branch under Auto+MB-only sources"
  - "73-04: UI plan — will pass station.cover_art_source through now_playing_panel._fetch_cover_art_async"

# Tech tracking
tech-stack:
  added:
    - "stdlib urllib.request Request with explicit User-Agent header (MB + CAA hosts)"
    - "queue.Queue(maxsize=1) for single-slot latest-wins enqueue"
    - "threading.Lock + time.monotonic floor for 1-req/sec gate (Phase 62 monotonic discipline)"
    - "importlib.metadata.version('musicstreamer') for dynamic UA version (VER-02 convention)"
  patterns:
    - "Persistent in-flight flag + drain-on-completion loop for D-13 max-1-spawn-under-burst semantics"
    - "Pinned _spawn_worker module-level seam — sole thread creation site, monkeypatch-friendly"
    - "Single-pass Lucene escape handling two-char operators (&&, ||) before single-char specials"
    - "Bare except Exception in worker → callback(None) (mirrors cover_art.py:98)"
    - "%r format specifier on ICY-derived log payloads (T-62-01 quote canary)"

key-files:
  created:
    - "musicstreamer/cover_art_mb.py — MB+CAA worker module (481 lines)"
    - ".planning/phases/73-musicbrainz-album-cover-lookup-complement-itunes-with-smart-/73-02-SUMMARY.md"
  modified:
    - "tests/test_cover_art_mb.py — flipped 10 xfail markers to GREEN; added _reset_cover_art_mb_state autouse fixture, _join_last_worker helper, D-11 URL-lock assertion, Lucene-injection regression test"

key-decisions:
  - "Drain-loop worker design: a single worker thread runs jobs sequentially, draining _pending after each job, before clearing _in_flight under the lock. Closes the lost-wakeup race that would otherwise drop the final job in a 5-rapid burst."
  - "Backward-compatible fetch_mb_cover signature: accepts both `fetch_mb_cover(icy_string, cb)` (legacy/scaffold) and `fetch_mb_cover(artist, title, cb)` (explicit-split). The Wave 0 RED scaffold uses the legacy shape; Plan 03 (router) can pick either."
  - "Reset fixture for test isolation: autouse `_reset_cover_art_mb_state` zeros _GATE._next_allowed_at, drains _pending, and clears _in_flight per test. Without this, ART-MB-14 (503 fall-through) would block up to 1s on the gate floor left by an earlier test."
  - "_last_thread handle exposed for failure-path tests only. Production callers rely on the Qt token-guard at now_playing_panel.py:1189 for sync, not on thread joins. Documented inline."
  - "_USER_AGENT split across two f-string literals (`f\"MusicStreamer/...\" f\"(https://...)\"`) so both ART-MB-15 source-grep substrings appear in a single conceptual line while staying under 79 cols."

patterns-established:
  - "MB+CAA worker module shape: imports → UA constant → escape helper → gate class → singletons → parsers → HTTP shims → queue+inflight → spawn seam → drain-loop worker → public entry"
  - "Source-grep gates pair with behavior tests for protocol invariants — single source mock could pass any UA string, so a literal source-level gate (ART-MB-15) is required alongside a behavior gate (ART-MB-01/02)"
  - "Worker drain-loop with _in_flight flag is project-canonical for D-13-style 'latest-wins, 1-in-flight, 1-queued' semantics; future modules with similar burst-collapse needs can mirror this pattern"

requirements-completed:
  - ART-MB-01
  - ART-MB-02
  - ART-MB-03
  - ART-MB-04
  - ART-MB-05
  - ART-MB-06
  - ART-MB-13
  - ART-MB-14
  - ART-MB-15
  - ART-MB-16

# Metrics
duration: 12min
completed: 2026-05-14
---

# Phase 73 Plan 02: MB+CAA lookup core Summary

**Self-contained MB+CAA worker module with 1-req/sec monotonic gate, Lucene-escaped recording search (T-73-01 mitigated), Official+Album release ladder, MB-tags-as-genre handoff, and a latest-wins single-spawn queue — all 10 Wave 0 RED scaffolds flipped to GREEN.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-05-14T00:27:18Z
- **Completed:** 2026-05-14T00:39:07Z
- **Tasks:** 2 (both auto)
- **Files modified:** 2 (1 new, 1 modified)

## Accomplishments

- Standalone `musicstreamer/cover_art_mb.py` (481 lines) — no imports from `ui_qt`, `repo`, or any other Phase 73-modified module; single public entry `fetch_mb_cover` plus six tested helpers.
- All 10 ART-MB requirements gated by Plan 02 flipped from xfail to GREEN:
  - ART-MB-01 (MB UA), ART-MB-02 (CAA UA + D-11 front-250 URL lock), ART-MB-03 (rate gate), ART-MB-04 (score>=80), ART-MB-05 (release ladder), ART-MB-06 (latest-wins spawns ≤ 2), ART-MB-13 (genre from highest-count tag), ART-MB-14 (503 fall-through), ART-MB-15 + ART-MB-16 (source-grep gates).
- T-73-01 Lucene-injection mitigation: defense-in-depth — source-grep gate ART-MB-15 covers the literal level, new `test_lucene_escape_neutralizes_injection_attack` covers the behavior level with the exact attack payload from RESEARCH §"Security Domain".
- Latest-wins semantics under rapid bursts: with `_spawn_worker` monkeypatched, 5 rapid `fetch_mb_cover` calls produce exactly 1 spawn (not 5, not 2). The remaining 4 are absorbed by the `_in_flight` flag + `_pending` queue. Production: the worker drains the queue on completion, so the last-arriving job is processed without an extra spawn.

## Task Commits

1. **Task 1: Implement cover_art_mb.py module (TDD GREEN of 10 Plan-01 RED scaffolds)** — `dcd7883` (feat)
2. **Task 2: Add Lucene-injection regression + D-11 CAA front-250 URL lock** — `18104e2` (test)

**Plan metadata:** (this SUMMARY commit — to follow)

_Note: Task 1 is structurally a single TDD-GREEN commit because Plan 01 already shipped the RED scaffolds (test commit `3fc8534`); Plan 02's Task 1 is the GREEN half of that cycle. The plan declares `tdd="true"` on Task 1 but the RED phase was Plan 01's responsibility, so Plan 02's single feat commit completes the cycle._

## Files Created/Modified

- `musicstreamer/cover_art_mb.py` (NEW, 481 lines) — MB+CAA worker module per D-07..D-20. Exposes `fetch_mb_cover`, `_MbGate`, `_escape_lucene`, `_build_mb_query`, `_pick_recording`, `_pick_release_mbid`, `_genre_from_tags`, `_do_mb_search`, `_fetch_caa_image`, `_spawn_worker`. Module-level singletons: `_USER_AGENT`, `_GATE`, `_pending`, `_inflight_lock`, `_in_flight`, `_last_thread`.
- `tests/test_cover_art_mb.py` — removed 10 `@pytest.mark.xfail` decorators; added `_reset_cover_art_mb_state` autouse fixture + `_join_last_worker` helper + D-11 URL-lock assertion in `test_caa_request_carries_user_agent` + new `test_lucene_escape_neutralizes_injection_attack`. Final count: 11 tests, all GREEN.

## Decisions Made

- **D-10 step 3 deferred (locked in CONTEXT, executed in code):** `_pick_release_mbid` implements steps 1+2 only — Official+Album earliest, then any Official. Step 3 (any release with CAA art on HEAD probe) returns None instead. Per CONTEXT D-10 revision 2026-05-13 + RESEARCH OQ-1 RESOLVED.
- **`limit=10` for MB recording search (RESEARCH OQ-4 RESOLVED):** Plan locked limit=10. Implemented in `_build_mb_query`. Trade-off — larger than D-08's default 5 to catch canonical-album hits beyond top-5 noise band (Pitfall 1 Hey Jude case); smaller than 25 to keep payload manageable.
- **`time.sleep` is called UNDER the lock in `_MbGate.wait_then_mark`:** explicit choice per RESEARCH §"Anti-Patterns" — the alternative (drop the lock to sleep) opens a race where two callers both read the same `_next_allowed_at` and both proceed. 1-second daemon-thread sleep is acceptable.
- **`fetch_mb_cover` accepts BOTH call shapes:** legacy `(icy_string, cb)` (matches Plan 01 RED scaffold's call) AND explicit `(artist, title, cb)` (intended Plan 03 router entry). The legacy shape does the `' - '` split itself; bare-title ICY short-circuits to `cb(None)` synchronously (D-07).
- **Worker uses drain-loop + in-flight flag (NOT one-thread-per-call):** D-13 demands "max 1 spawn under burst". A one-thread-per-call design with monkeypatched `_spawn_worker` would record 5 spawns. The drain-loop instead has the running worker pick up the queued successor itself, so production produces exactly 1 spawn per burst as well — token-guard at the Qt slot already handles stale dispatch.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Test-isolation autouse fixture for module state**

- **Found during:** Task 1 (initial test run)
- **Issue:** The plan specifies module-level singletons `_GATE` (with `_next_allowed_at` floor), `_pending` queue, and `_in_flight` flag. Without per-test reset, prior tests' calls to `_do_mb_search` leave `_GATE._next_allowed_at = monotonic() + 1.0`, causing later tests (esp. ART-MB-14's 503 fall-through, which spawns a real thread) to block up to 1 second on the stale gate floor. With monkeypatched `urlopen` raising immediately the thread would still complete fast — but only AFTER the assertion already ran.
- **Fix:** Added `@pytest.fixture(autouse=True) def _reset_cover_art_mb_state()` in test file. Pre- and post- each test it zeros `_GATE._next_allowed_at`, drains `_pending`, and clears `_in_flight` via the plan's `_reset_queue_for_tests()` helper (which I extended to also clear the flag).
- **Files modified:** `tests/test_cover_art_mb.py`
- **Verification:** All 11 tests pass in any pytest collection order; `pytest -p no:randomly` and default ordering both green.
- **Committed in:** `dcd7883` (Task 1 commit)

**2. [Rule 3 - Blocking] `_join_last_worker` helper for failure-path tests**

- **Found during:** Task 1 (ART-MB-14 503 test failed because the spawned thread had not completed before the assertion)
- **Issue:** The 503 test (ART-MB-14) scaffolded by Plan 01 asserts `cb_calls == [None]` immediately after `fetch_mb_cover` returns. With my (correct) async-thread design, the callback fires from the worker thread; the assertion races the thread.
- **Fix:** Exposed `_last_thread: Optional[threading.Thread]` on the module (set inside `_spawn_worker`). Added `_join_last_worker(mb_module, timeout=2.0)` helper in the test file. Modified ONLY the ART-MB-14 test to call `_join_last_worker(cover_art_mb)` after `fetch_mb_cover`. No other test needed it because they either don't spawn (helpers tested directly) or monkeypatch `_spawn_worker` to a no-op (ART-MB-06).
- **Files modified:** `musicstreamer/cover_art_mb.py` (added `_last_thread` global + assignment in `_spawn_worker`); `tests/test_cover_art_mb.py` (added helper + call site)
- **Verification:** ART-MB-14 passes in <100ms; the worker completes synchronously under mocked `urlopen` that raises.
- **Committed in:** `dcd7883` (Task 1 commit)

**3. [Rule 1 - Bug] Drain-loop worker design to satisfy ART-MB-06 ≤2 spawn budget**

- **Found during:** Task 1 (designing fetch_mb_cover to meet `len(spawned) <= 2`)
- **Issue:** A naive one-thread-per-call design would record 5 spawns when 5 rapid `fetch_mb_cover` calls happen with `_spawn_worker` monkeypatched (because the monkeypatched stub doesn't run the worker, so nothing ever clears any in-flight state, and each call still spawns). Test would fail with `len(spawned) == 5`.
- **Fix:** Added `_in_flight: bool` + `_inflight_lock` module globals. `fetch_mb_cover` checks `_in_flight` under the lock — if True, only updates the `_pending` queue and does NOT spawn. If False, sets it True and spawns. `_worker` runs jobs in a loop, draining `_pending` between iterations, and clears `_in_flight` under the lock only when the queue is empty (closing the lost-wakeup race). With the test stub: call 1 spawns (1 in flight, never cleared); calls 2-5 only update the queue. Total spawns = 1. In production: spawn is fast enough that the gate naturally serializes; the worker drains the queue cleanly.
- **Files modified:** `musicstreamer/cover_art_mb.py`
- **Verification:** ART-MB-06 passes with exactly 1 recorded spawn (well below the ≤2 budget). No production behavior regression — the worker still processes one job per gate tick.
- **Committed in:** `dcd7883` (Task 1 commit)

---

**Total deviations:** 3 auto-fixed (1 missing critical = test isolation, 1 blocking = thread join helper, 1 bug-fix-during-design = drain-loop)

**Impact on plan:** All three fixes are inside the plan's task surface (Task 1 step 15/16 + step 18 contract). No scope creep. The plan's `_pending` + `_reset_queue_for_tests()` shape was retained verbatim; I added `_in_flight` and `_inflight_lock` alongside, and folded `_reset_queue_for_tests()` to also clear them. The pinned `_spawn_worker(target, args)` contract is honored verbatim — it is still the SOLE thread creation site.

## Issues Encountered

- **Stash/uv.lock interaction during regression check:** A mid-execution sanity check (`git stash` to compare against the prior commit) couldn't pop cleanly because uv.lock had drifted. Resolved by `git checkout -- uv.lock && git stash pop`. No code lost; the stash captured my test file changes intact. No production impact.

## Threat Surface Verification

The plan's `<threat_model>` lists T-73-01..T-73-06 with explicit mitigations. All locked in code:

- **T-73-01 (Tampering):** `_escape_lucene` covers all 13 Lucene specials + 2 two-char operators; verified by `test_lucene_escape_neutralizes_injection_attack` (behavior gate) + ART-MB-15 source-grep (literal gate).
- **T-73-02 (DoS):** Bare `except Exception` in `_worker` → `callback(None)` (mirrors cover_art.py:98). Logged at WARNING with `%r` ICY echoes for T-62-01 quote-canary alignment.
- **T-73-03 (Info Disclosure):** GitHub URL (not email) in `_USER_AGENT` per D-18 + user memory `project_publishing_history.md`. Locked by ART-MB-15.
- **T-73-04 (DoS / Disk):** `tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)` mirrors existing `cover_art.py:94` precedent. GC is the caching phase's job.
- **T-73-05 (Slowloris):** `urlopen(..., timeout=5)` on BOTH MB API and CAA image fetch.
- **T-73-06 (Privacy):** Covered by T-73-03 mitigation; GitHub URL contains no PII.

No new threat surface was introduced beyond the locked register. No `## Threat Flags` section needed.

## Verification Evidence

```text
$ uv run --with pytest --with pytest-qt pytest tests/test_cover_art_mb.py -v
========================= 11 passed, 1 warning in 0.10s =========================
- test_mb_request_carries_user_agent           PASSED   [ART-MB-01]
- test_caa_request_carries_user_agent          PASSED   [ART-MB-02 + D-11 lock]
- test_mb_gate_serializes_with_1s_floor        PASSED   [ART-MB-03]
- test_score_threshold_rejects_below_80_...    PASSED   [ART-MB-04]
- test_release_selection_ladder_picks_...      PASSED   [ART-MB-05]
- test_latest_wins_queue_drops_superseded_jobs PASSED   [ART-MB-06]
- test_genre_from_tags_picks_highest_count     PASSED   [ART-MB-13]
- test_mb_503_falls_through_to_callback_none   PASSED   [ART-MB-14]
- test_user_agent_string_literals_present      PASSED   [ART-MB-15]
- test_rate_gate_uses_monotonic                PASSED   [ART-MB-16]
- test_lucene_escape_neutralizes_injection_... PASSED   [T-73-01 behavior gate]

$ uv run --with pytest --with pytest-qt pytest tests/test_cover_art_mb.py tests/test_cover_art.py tests/test_repo.py -x
========================= 80 passed in 0.60s =========================

$ grep -c "_spawn_worker" musicstreamer/cover_art_mb.py
3   [≥ 2 required by plan's blocker-2 gate]

$ grep -c "MusicStreamer/" musicstreamer/cover_art_mb.py
3   [≥ 1 required by ART-MB-15]

$ grep -c "https://github.com/lightningjim/MusicStreamer" musicstreamer/cover_art_mb.py
2   [≥ 1 required by ART-MB-15]

$ grep -c "time.monotonic" musicstreamer/cover_art_mb.py
5   [≥ 1 required by ART-MB-16]

$ grep -E "from musicstreamer\.(ui_qt|repo)" musicstreamer/cover_art_mb.py
(empty)   [standalone module per success_criteria]

$ grep -i "itunes.apple.com\|itunes.search" musicstreamer/cover_art_mb.py
(empty)   [D-16 honored: no iTunes call from MB module]

$ wc -l musicstreamer/cover_art_mb.py
481   [≥ 150 required by plan]
```

## User Setup Required

None — no external service configuration required. MB and CAA are both public anonymous APIs.

## Next Phase Readiness

**Plan 03 (router) prerequisites met:**

- `fetch_mb_cover(icy_string, callback)` (legacy shape) callable directly from `cover_art.fetch_cover_art`'s MB branch.
- `last_itunes_result` channel writes the MB-sourced genre on hit — Plan 03's router need not handle genre differently per source.
- Token-guard at `now_playing_panel.py:1189` already discards stale results — Plan 03 does not need to add any cancellation primitive.
- The 1-req/sec gate is module-global and survives station changes — Plan 03's MB-only mode will share the gate with Auto-mode's MB fallback.

**Blockers / concerns for Plan 03:** None. The single remaining xfail (`tests/test_cover_art_routing.py::test_auto_mode_falls_through_to_mb_when_itunes_misses`) is the ART-MB-09 scaffold Plan 03 will flip to GREEN.

## Self-Check: PASSED

- `musicstreamer/cover_art_mb.py` exists (481 lines).
- Task 1 commit `dcd7883` exists in `git log`.
- Task 2 commit `18104e2` exists in `git log`.
- All 11 `tests/test_cover_art_mb.py` tests pass; `tests/test_cover_art_routing.py` still 1 xfail (Plan 03's responsibility).
- All source-grep gates green: `_spawn_worker` ≥ 2, `MusicStreamer/` ≥ 1, GitHub URL ≥ 1, `time.monotonic` ≥ 1, no `ui_qt`/`repo` imports, no `iTunes` HTTP endpoint, no inline `Thread(...).start()` outside `_spawn_worker`.

---

*Phase: 73-musicbrainz-album-cover-lookup-complement-itunes-with-smart-*
*Plan: 02*
*Completed: 2026-05-14*
