---
phase: 47-stats-for-nerds-autoeq-import-harvest-seed-005-live-gstreame
plan: 02
subsystem: audio-playback
tags: [repo, migration, failover, player, tdd]

requires:
  - phase: 47
    plan: 01
    provides: StationStream.bitrate_kbps field + musicstreamer/stream_ordering.py (codec_rank, order_streams)
provides:
  - "station_streams.bitrate_kbps INTEGER NOT NULL DEFAULT 0 (CREATE TABLE + additive ALTER TABLE migration)"
  - "Repo.list_streams hydrates bitrate_kbps into StationStream"
  - "Repo.insert_stream / Repo.update_stream accept optional bitrate_kbps: int = 0 kwarg"
  - "player.py::play builds failover queue via order_streams(station.streams) (replaces position-only sort)"
affects: [47-03-ui-imports-settings]

tech-stack:
  added: []
  patterns:
    - "Additive ALTER TABLE migration wrapped in try/except sqlite3.OperationalError (idempotent, no user_version bump)"
    - "Minimal one-line failover integration — variable name streams_by_position retained to keep diff small"
    - "RED/GREEN TDD cycle with atomic test/feat commits (two cycles, one per task)"

key-files:
  created: []
  modified:
    - musicstreamer/repo.py
    - musicstreamer/player.py
    - tests/test_repo.py
    - tests/test_player_failover.py

key-decisions:
  - "ALTER TABLE block placed immediately after the is_favorite migration, targeting station_streams (not stations); wraps in try/except sqlite3.OperationalError so idempotent second run is a no-op (D-02)"
  - "insert_stream / update_stream kwargs default to 0 — existing positional callers (insert_station, settings_export, aa_import, edit_station_dialog, discovery_dialog) remain source-compatible; 47-03 can opt-in at its leisure"
  - "player.py:166 one-line swap; preferred_quality short-circuit (lines 167-177) untouched; variable name streams_by_position retained despite being semantically inaccurate now — minimal-diff cleanup deferred per plan note"

patterns-established:
  - "Post-47 idiom: every `bitrate_kbps` seam has an optional kwarg defaulting to 0; unknown = 0 is the system-wide sentinel"
  - "Migration test pattern: executescript pre-47 CREATE TABLE → db_init → assert column exists on legacy row → db_init again (idempotency)"

requirements-completed: []

duration: "3m"
completed: "2026-04-18"
---

# Phase 47 Plan 02: Repo + Player Bitrate Wiring Summary

**Extended `station_streams` with `bitrate_kbps INTEGER NOT NULL DEFAULT 0` (CREATE TABLE + idempotent ALTER TABLE), widened `Repo.insert_stream` / `Repo.update_stream` / `Repo.list_streams` to carry it, and swapped `player.py::play`'s position-only sort for `order_streams(station.streams)` — failover now prioritizes (codec rank desc, bitrate desc).**

## Performance

- **Duration:** ~3m (178s)
- **Started:** 2026-04-18T16:40:18Z
- **Completed:** 2026-04-18T16:43:16Z
- **Tasks:** 2 (both auto + TDD)
- **Files modified:** 4 (repo.py, player.py, test_repo.py, test_player_failover.py)
- **Files created:** 0

## Accomplishments

- `station_streams` gains `bitrate_kbps INTEGER NOT NULL DEFAULT 0` via BOTH `CREATE TABLE IF NOT EXISTS` (fresh installs) AND `ALTER TABLE ... ADD COLUMN` wrapped in `try/except sqlite3.OperationalError: pass` (pre-47 DB upgrades). Idempotency proven by test.
- `Repo.list_streams` hydrates the new field: `bitrate_kbps=r["bitrate_kbps"]` appended to the `StationStream(...)` constructor.
- `Repo.insert_stream` and `Repo.update_stream` both accept `bitrate_kbps: int = 0` kwarg (default preserves backward compat) — SQL widened from 7 to 8 columns; placeholder and tuple extended in lockstep.
- `player.py::play` replaces `sorted(station.streams, key=lambda s: s.position)` at line 166 with `order_streams(station.streams)`. Preferred-quality short-circuit logic (lines 167-177) untouched. Variable name `streams_by_position` retained to keep the diff to one line (semantically stale name, minor tech debt acknowledged in the PLAN).
- Import `from musicstreamer.stream_ordering import order_streams` added to player.py's module-level imports alongside `StationStream`.
- Three new tests added (2 repo, 2 player — total 4). PB-01 hydration, PB-02 migration idempotency, PB-18 failover queue ordering, and a regression guard for preferred_quality interaction with order_streams.
- All 54 `test_repo.py` tests pass. All 15 non-yt_dlp `test_player_failover.py` tests pass (the 3 yt_dlp tests fail with `ModuleNotFoundError` — pre-existing environment issue, see Deferred Issues below).

## Task Commits

Each task was committed atomically with its RED/GREEN cycle:

1. **Task 1 RED: failing bitrate_kbps hydration + migration tests** — `cbda9b8` (test)
2. **Task 1 GREEN: bitrate_kbps column + CRUD widening** — `8e978a6` (feat)
3. **Task 2 RED: failing order_streams failover integration test** — `7a879c8` (test)
4. **Task 2 GREEN: wire order_streams into player failover queue** — `fb1e3ca` (feat)

_No REFACTOR commits — both GREEN implementations were minimal and idiomatic (identical pattern to existing CRUD + existing ALTER TABLE blocks). The one cosmetic cleanup — renaming the stale `streams_by_position` variable — is deferred per the plan's explicit instruction to minimize the failover hook diff._

## Files Created/Modified

### `musicstreamer/repo.py` (+17 / -7)

- Line ~60: added `bitrate_kbps INTEGER NOT NULL DEFAULT 0,` between `codec` and `FOREIGN KEY` inside the `CREATE TABLE IF NOT EXISTS station_streams` body.
- Lines ~84-88: new `try: con.execute("ALTER TABLE station_streams ADD COLUMN bitrate_kbps INTEGER NOT NULL DEFAULT 0"); con.commit(); except sqlite3.OperationalError: pass` block placed directly after the `is_favorite` migration block.
- Line ~176: `list_streams` now hydrates `bitrate_kbps=r["bitrate_kbps"]`.
- Lines ~180-186: `insert_stream` signature widened with `bitrate_kbps: int = 0`, 8-column `INSERT` SQL, 8-slot tuple.
- Lines ~189-194: `update_stream` signature widened with `bitrate_kbps: int = 0`, new `bitrate_kbps=?` in SET clause, 8-slot tuple.

### `musicstreamer/player.py` (+3 / -2)

- Line 36: `from musicstreamer.stream_ordering import order_streams` import added.
- Line 166: `sorted(station.streams, key=lambda s: s.position)` → `order_streams(station.streams)`. Comment on line 165 updated from "position order" to "order_streams order (Phase 47)".

### `tests/test_repo.py` (+65 / 0)

- New section header "Phase 47-02: bitrate_kbps schema + hydration + migration (PB-01, PB-02)".
- New helper `_make_bare_con()` — bare `:memory:` sqlite3 connection with `row_factory = Row` + foreign_keys ON (separate from the `repo` fixture because migration tests need to run db_init themselves on a pre-47 schema).
- `test_bitrate_kbps_hydrated_from_row` — PB-01.
- `test_bitrate_kbps_migration_adds_column` — PB-02 (simulates pre-47 CREATE TABLE without bitrate_kbps, runs db_init twice for idempotency).

### `tests/test_player_failover.py` (+49 / 0)

- `test_failover_queue_uses_order_streams` — PB-18. Builds a station with MP3/pos=1/64kbps, FLAC/pos=2/320kbps, AAC/pos=3/128kbps and asserts the queue ordering is FLAC → AAC → MP3 (codec rank wins).
- `test_failover_preferred_quality_still_works_with_order_streams` — regression guard: preferred="low" pins MP3 first, remainder follows order_streams (FLAC → AAC).

## Decisions Made

- **`_make_bare_con` helper vs. reuse of `repo` fixture:** the existing `repo` fixture runs `db_init` automatically, which is not what the migration test wants (we need to set up the pre-47 schema ourselves before calling `db_init`). Added a small local helper rather than refactoring the shared fixture.
- **`bitrate_kbps: int = 0` default vs. required:** plan prescribed optional kwarg with default 0; kept the default so `insert_station` (which calls `insert_stream(station_id, url)` with only positional args, repo.py ~line 406) continues to work unchanged. Plan 47-03 will thread real values through the AA/RadioBrowser import paths.
- **Variable name `streams_by_position` left stale:** plan explicitly called for minimum diff; renaming it would touch lines 166/170/175/177 (4 lines instead of 1) without changing behavior. Accepted as intentional minor tech debt.
- **Did NOT fix `test_preferred_stream_first` / `test_no_preferred_quality_uses_position_order` tests:** both existing tests pass because they use all-zero-bitrate streams (the `make_stream` helper does not set `bitrate_kbps`). `order_streams` gracefully degenerates to position order for all-unknown input (D-07), which is the existing contract of those tests. No regressions.

## Deviations from Plan

None — plan executed exactly as written. Both RED phases produced the expected failures (TypeError on unexpected kwarg for PB-01, ordering assertion mismatch for PB-18); both GREEN phases produced passing tests on first run.

## Issues Encountered

### Deferred Issues (pre-existing environment — not caused by this plan)

- **`yt_dlp` ModuleNotFoundError** in `tests/test_player_failover.py` (3 tests) — documented in `47-stats-for-nerds-autoeq-import-harvest-seed-005-live-gstreame/deferred-items.md`. Verified these are the SAME failures present before 47-02's edits landed (see 47-01 SUMMARY for the same observation). The 3 affected tests (`test_youtube_resolve_success_sets_uri_and_arms_failover`, `test_youtube_resolve_failure_emits_error_and_advances_queue`, `test_play_youtube_spawns_resolver_thread`) all require `import yt_dlp` inside the test body or target function. Not in scope for Phase 47.
- **`pytest-qt qtbot.mouseClick` AttributeError** also documented in deferred-items.md. None of the 4 tests added by this plan use `qtbot.mouseClick` — they only use `patch.object` + direct method calls (PB-01/PB-02 are pure Python, PB-18 and the regression guard use the shared `make_player` + `patch.object(p, "_set_uri")` pattern that avoids qtbot interaction).

### Full-suite check

Running `pytest tests/` (excluding the 6 yt_dlp collection-error modules also in deferred-items.md): **474 passed, 25 failed**. All 25 failures match the pre-existing pattern documented in Wave 1's SUMMARY (yt_dlp + pytest-qt env issues). No NEW regressions introduced by this plan.

## User Setup Required

None — all changes are backward-compatible at the DB level (idempotent ALTER TABLE) and at the Python API level (optional kwarg with default). Existing DBs gain the column silently on next launch.

## Next Phase Readiness

- **47-03 (UI + imports + settings)** can now:
  - Call `repo.insert_stream(..., bitrate_kbps=320)` / `repo.update_stream(..., bitrate_kbps=...)` in aa_import.py, discovery_dialog.py, settings_export.py, edit_station_dialog.py — the kwarg is present.
  - Trust that `Station.streams[*].bitrate_kbps` is always populated (0 = unknown) in widgets bound to the repo.
  - Trust that player failover already re-orders by codec+bitrate — no further player-side work needed in 47-03.
- **Phase 47 runtime end-to-end:** once a user's DB has at least one station with non-zero `bitrate_kbps` (either via manual edit, AA import, or RadioBrowser import after 47-03 lands), `player.play(station)` will dequeue the highest-codec-rank, highest-bitrate stream first. Verified by PB-18 integration test.

No blockers.

## Self-Check: PASSED

- `musicstreamer/repo.py` — modified, verified on HEAD
- `musicstreamer/player.py` — modified, verified on HEAD
- `tests/test_repo.py` — modified, verified on HEAD (54 tests pass)
- `tests/test_player_failover.py` — modified, verified on HEAD (15 non-yt_dlp tests pass)
- Commit `cbda9b8` (Task 1 RED) — FOUND
- Commit `8e978a6` (Task 1 GREEN) — FOUND
- Commit `7a879c8` (Task 2 RED) — FOUND
- Commit `fb1e3ca` (Task 2 GREEN) — FOUND
- Acceptance grep `bitrate_kbps INTEGER NOT NULL DEFAULT 0` in repo.py — 2 matches (CREATE + ALTER) ✓
- Acceptance grep `ALTER TABLE station_streams ADD COLUMN bitrate_kbps` in repo.py — 1 match ✓
- Acceptance grep `bitrate_kbps=r["bitrate_kbps"]` in repo.py — 1 match ✓
- Acceptance grep `bitrate_kbps: int = 0` in repo.py — 2 matches (insert_stream + update_stream) ✓
- Acceptance grep `from musicstreamer.stream_ordering import order_streams` in player.py — 1 match ✓
- Acceptance grep `order_streams(station.streams)` in player.py — 1 match ✓
- Acceptance grep `sorted(station.streams, key=lambda s: s.position)` in player.py — 0 matches ✓
- Acceptance grep `streams_by_position` in player.py — 4 matches (variable retained in preferred-quality logic) ✓

---

*Phase: 47-stats-for-nerds-autoeq-import-harvest-seed-005-live-gstreame*
*Completed: 2026-04-18*
