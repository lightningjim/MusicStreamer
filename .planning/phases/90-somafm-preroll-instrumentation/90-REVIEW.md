---
phase: 90-somafm-preroll-instrumentation
reviewed: 2026-06-18T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - musicstreamer/preroll_log.py
  - musicstreamer/paths.py
  - musicstreamer/__main__.py
  - musicstreamer/player.py
  - musicstreamer/ui_qt/main_window.py
  - tests/test_preroll_events_log.py
  - tests/test_paths.py
  - tests/test_player.py
  - tests/test_main_window_soma.py
findings:
  critical: 0
  blocker: 0
  warning: 3
  info: 4
  total: 7
status: issues_found
---

# Phase 90: Code Review Report

**Reviewed:** 2026-06-18
**Depth:** standard (ultracode mode — all dimensions + adversarial refutation pass)
**Files Reviewed:** 9
**Status:** issues_found

## Summary

This phase adds non-destructive preroll instrumentation (a `RotatingFileHandler`
on `musicstreamer.preroll`, five additive INFO log calls in `player.py`, an
"Open preroll log" menu action) plus two re-fetch levers: the D-08 auto-staleness
daemon re-fetch in `player.py` and the manual `_PrerollRefetchWorker` QThread in
`main_window.py`.

The **zero-behavior-change guarantee (SOMA-PRE-05) holds.** I traced every new
log call:
- `play()`: `random.choice(urls)` (line 776) runs BEFORE the `preroll_start`
  log (777-780); the log is read-only and does not touch the selection,
  throttle, or `_start_preroll` ordering.
- `_on_preroll_about_to_finish`: the `preroll_handoff_complete` log (1627-1630)
  sits between the `_preroll_in_flight = False` clear and the empty-queue check —
  NOT between the buffer-apply (`_apply_pending_buffer_duration_to_pipeline`,
  1685) and `set_property("uri", ...)` (1692). The load-bearing apply→set_uri
  ordering is untouched.
- The throttle/empty/fetched-empty probes are pure read-only `.info()` calls.

**Concurrency** is sound on the inspected dimensions: both the D-08 daemon path
(`_preroll_backfill_worker`) and the manual lever (`_PrerollRefetchWorker.run`)
open their own `db_connect()` Repo inside the worker and close it in `finally`
(Pattern 4). `_backfill_in_flight` single-flight and the `_soma_refetch_worker`
double-click/GC-retention guards are correct. No second GStreamer pipeline is
ever constructed by either path. The D-08 staleness branch and the D-13 lazy
backfill (`IS NULL`) branch are mutually exclusive (one requires
`prerolls_fetched_at IS NULL`, the other `IS NOT NULL`).

The defects found are a real persistence asymmetry between the two re-fetch
paths (WR-01), an over-broad success count (WR-02), and a thread-safety gap on
`_backfill_in_flight` mutation from the daemon worker (WR-03), plus minor
quality items.

## Warnings

### WR-01: Manual re-fetch lever never closes the D-08 staleness trap for genuinely-empty channels

**File:** `musicstreamer/ui_qt/main_window.py:212-222`
**Issue:** `_PrerollRefetchWorker.run` skips `set_prerolls_fetched_at` entirely
when the upstream channel has no preroll URLs:

```python
preroll_urls = title_to_prerolls.get(station.name, [])
if not preroll_urls:
    continue                              # <-- returns WITHOUT updating fetched_at
for pos, url in enumerate(preroll_urls[:50], start=1):
    ...
repo.set_prerolls_fetched_at(station.id, int(time.time()))
```

Contrast the daemon path `player._preroll_backfill_worker` (player.py:2085-2087),
whose comment explicitly says "mark fetched regardless of count" and calls
`set_prerolls_fetched_at` for the empty case too. Because the manual lever does
NOT advance `prerolls_fetched_at` for a genuinely-empty SomaFM channel, that
station's stored timestamp stays ancient, so the D-08 staleness branch in
`player.play()` (player.py:809-819) keeps re-scheduling the daemon re-fetch on
every play, and clicking the manual lever re-attempts the same channels every
time with no convergence. The whole point of D-08 (close the
"fetched-with-0 never re-fetches" trap) is undermined by the lever that is meant
to be the user's escape hatch.
**Fix:** Mark fetched unconditionally for SomaFM stations the worker actually
examined, mirroring the daemon path:
```python
preroll_urls = title_to_prerolls.get(station.name, [])
inserted_any = False
for pos, url in enumerate(preroll_urls[:50], start=1):
    try:
        repo.insert_preroll(station.id, url, pos)
        inserted_any = True
    except ValueError:
        continue
# Mark fetched regardless of count (D-04 / D-08 — stop the re-fetch loop).
repo.set_prerolls_fetched_at(station.id, int(time.time()))
if inserted_any:
    updated += 1
```

### WR-02: Re-fetch success count increments even when every URL was rejected by the scheme gate

**File:** `musicstreamer/ui_qt/main_window.py:215-222`
**Issue:** `updated += 1` (line 222) runs unconditionally once `preroll_urls` is
non-empty, even if every `repo.insert_preroll` call raised `ValueError`
(non-HTTP(S) scheme, or position > 50) and was swallowed by the `except ValueError:
continue` at 218-220. In that case zero rows actually landed in
`station_prerolls`, yet the user is toasted "Prerolls refreshed for N station(s)"
(`_on_preroll_refetch_done`, 1718-1724). The count overstates real success and
masks a hostile/garbage upstream response — the exact T-83-01 scenario the scheme
gate exists to catch.
**Fix:** Gate `updated += 1` on whether at least one insert succeeded (see the
`inserted_any` flag in the WR-01 fix). The two warnings share one corrected loop.

### WR-03: `_backfill_in_flight` set is mutated from a daemon thread without synchronization

**File:** `musicstreamer/player.py:793-819` (add), `player.py:2096` (discard)
**Issue:** `self._backfill_in_flight.add(station.id)` runs on the main thread in
`play()`, but `self._backfill_in_flight.discard(station.id)` runs on the daemon
worker thread in `_preroll_backfill_worker`'s `finally` (line 2096). The
membership test `station.id not in self._backfill_in_flight` (lines 785, 812) and
the `add` are on the main thread; the `discard` is cross-thread. `set.add` /
`set.discard` / `in` are individually atomic under CPython's GIL, so this will
not corrupt the set, but the single-flight invariant is read-modify-not-atomic:
between the main-thread `if id not in set` check and the `set.add`, no lock is
held. In practice both schedule sites run on the main thread so they cannot race
each other, and the only cross-thread writer is `discard` — so the worst case is
a benign "second play schedules a duplicate worker because discard already
fired." The existing code leans on the GIL (consistent with the documented
Pattern 2 elsewhere), but unlike the `bool`/`int` cross-thread reads that are
explicitly justified in comments, this set mutation has NO comment acknowledging
the cross-thread `discard` and the check-then-add gap. This is fragile if the
schedule path is ever moved off the main thread.
**Fix:** Either (a) document the cross-thread contract at the `discard` site and
assert both schedule sites are main-thread-only, or (b) marshal the `discard`
back to the main thread via a queued Signal (the same pattern the file already
uses for every other worker→main handoff), keeping all `_backfill_in_flight`
mutation on one thread.

## Info

### IN-01: Redundant `prerolls_fetched_at is not None` re-check in the D-08 branch

**File:** `musicstreamer/player.py:809-810`
**Issue:** The D-08 block lives inside the `else:` of the
`getattr(station, "prerolls_fetched_at", None) is None` branch (783), so reaching
line 809 already guarantees `prerolls_fetched_at is not None`. The re-check
`getattr(station, "prerolls_fetched_at", None) is not None` at 810 is dead-true.
Harmless, but it obscures the control-flow invariant and invites a future reader
to think the branch is reachable with a `None` timestamp (which would make the
`int(time.time()) - station.prerolls_fetched_at` arithmetic on line 811 a
`TypeError`).
**Fix:** Drop the redundant clause; keep only the age + single-flight checks, or
add a comment that the `is not None` is defensive belt-and-suspenders.

### IN-02: `time.monotonic()` read multiple times within the throttle probe / gate

**File:** `musicstreamer/player.py:762, 767, 771, 772`
**Issue:** The throttle probe reads `time.monotonic()` at 762 and again at 767 to
compute `remaining_s`; the real gate reads it again at 771 and 772. Four separate
clock reads across the probe+gate. The two reads inside the probe (762 vs 767)
can differ by microseconds, so the logged `remaining_s` is computed against a
slightly later `now` than the suppression decision used. Purely cosmetic for a
diagnostic field, but a single `now = time.monotonic()` hoisted above both blocks
would make the log value exactly consistent with the decision.
**Fix:** Hoist `now = time.monotonic()` once and reuse it in the probe and gate.

### IN-03: `_PrerollRefetchWorker.run` re-imports `time` locally, shadowing the module-level `time`

**File:** `musicstreamer/ui_qt/main_window.py:191`
**Issue:** `run()` does `import time` at the top of the method even though
`main_window.py` already imports `time` at module scope (used at line 221's
`int(time.time())` and elsewhere). The local import is harmless but inconsistent
with the rest of the file's import discipline and adds noise. Not a bug.
**Fix:** Remove the method-local `import time`; rely on the module-level import.

### IN-04: `preroll_log.install_preroll_events_handler` idempotency compares `baseFilename` to a possibly-unnormalized path

**File:** `musicstreamer/preroll_log.py:57-61`
**Issue:** The idempotency short-circuit compares `h.baseFilename == path` where
`path = paths.preroll_events_log_path()`. `RotatingFileHandler` stores
`baseFilename` as `os.path.abspath(filename)`. `paths.preroll_events_log_path()`
returns `os.path.join(_root(), "preroll-events.log")`, which is already absolute
in production (platformdirs/`_root_override` are absolute), so the comparison
holds and the test `test_handler_attached_to_preroll_logger` passes. But if a
caller ever set `_root_override` to a relative path, the second
`install_*` call would not match (`abspath` differs from the joined relative
path) and would attach a SECOND handler, doubling every file line. The
buffer_log.py sibling has the same shape, so this mirrors existing behavior, but
it is a latent idempotency gap.
**Fix:** Normalize before comparing: `path = os.path.abspath(paths.preroll_events_log_path())`,
or compare `os.path.abspath(h.baseFilename) == os.path.abspath(path)`.

---

## Test Quality Notes (no defects — informational)

The Phase 90 tests are genuinely additive and well-targeted:
- `test_player.py` preroll-log tests assert ONLY on emitted log records via an
  in-memory `_ListHandler`, never on pipeline state — correctly honoring the
  zero-behavior-change contract.
- The D-08 staleness trio covers the three branch outcomes (stale→fire,
  prerolls-exist→no-fire, recent→no-fire) and pins `daemon=True`, the worker
  target, the args tuple, and `_backfill_in_flight` membership.
- `test_main_window_soma.py::test_refetch_worker_skips_stations_with_prerolls`
  drives the real `run()` and verifies the skip-with-prerolls + non-SomaFM
  filtering.

Gap worth noting (not a defect in the code under review, but a test-coverage
hole that lets WR-01/WR-02 ship): no test asserts that the manual lever updates
`prerolls_fetched_at` for a fetched-empty SomaFM station, and no test asserts the
`updated` count is NOT incremented when all inserts are rejected. Adding those
two assertions would have caught WR-01 and WR-02.

---

_Reviewed: 2026-06-18_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard (ultracode)_
