---
phase: 73-musicbrainz-album-cover-lookup-complement-itunes-with-smart
plan: 01
subsystem: database
tags: [musicbrainz, cover-art, sqlite-migration, requirements-registration, pytest-xfail, wave-0]

# Dependency graph
requires:
  - phase: 71-sibling-stations
    provides: requirements-registration pattern (### Sibling Stations heading + Traceability table extension precedent)
  - phase: 47-bitrate-kbps-schema-migration
    provides: idempotent ALTER TABLE try/except sqlite3.OperationalError idiom
provides:
  - ART-MB requirement family registered in REQUIREMENTS.md (16 unchecked entries)
  - Station.cover_art_source dataclass field (Literal["auto","itunes_only","mb_only"] = "auto")
  - stations.cover_art_source SQLite column with DEFAULT 'auto' (idempotent migration)
  - Row -> Station mapping for cover_art_source at all 4 read sites in repo.py
  - 6 MB JSON fixtures under tests/fixtures/ (clean_album_hit, bootleg_only, score_79, score_85, no_tags, 503_body)
  - 11 RED xfail-marked test scaffolds (10 in test_cover_art_mb.py, 1 in test_cover_art_routing.py)
  - Wave 0 RED state pinned with `_spawn_worker` seam contract for Plan 02 Task 1 step 18
affects: [73-02, 73-03, 73-04, 73-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Idempotent ALTER TABLE placement post-rebuild (Pitfall 8 deviation)"
    - "xfail-marked Wave 0 RED scaffolds with raises=(ImportError, ModuleNotFoundError, AttributeError, AssertionError)"
    - "Pinned monkeypatch seam `_spawn_worker` so Plan 02 can wrap threading.Thread cleanly"
    - "Non-comment-line regex for source-grep gates (r'^[^#]*\\btime\\.monotonic\\b' MULTILINE)"

key-files:
  created:
    - tests/fixtures/mb_recording_search_clean_album_hit.json
    - tests/fixtures/mb_recording_search_bootleg_only.json
    - tests/fixtures/mb_recording_search_score_79.json
    - tests/fixtures/mb_recording_search_score_85.json
    - tests/fixtures/mb_recording_search_no_tags.json
    - tests/fixtures/mb_recording_search_503_body.json
    - tests/test_cover_art_mb.py
    - tests/test_cover_art_routing.py
    - .planning/phases/73-musicbrainz-album-cover-lookup-complement-itunes-with-smart-/deferred-items.md
  modified:
    - .planning/REQUIREMENTS.md
    - musicstreamer/models.py
    - musicstreamer/repo.py
    - tests/test_repo.py
    - .planning/phases/73-musicbrainz-album-cover-lookup-complement-itunes-with-smart-/73-VALIDATION.md

key-decisions:
  - "Rule 1 deviation: placed cover_art_source ALTER TABLE AFTER the legacy URL-column rebuild block (not before, as the plan's literal instruction said). The plan's narrative INTENT was 'the ALTER lands the column on the rebuilt table afterward' — the only way that is true is post-rebuild placement. Pre-rebuild placement would let the rebuild's CREATE TABLE stations_new + INSERT SELECT silently drop the column (verified by test_migration_url_to_streams failing with `IndexError: No item with that key` until the ALTER was moved)."
  - "Wave 0 RED scaffolds use @pytest.mark.xfail(raises=(ImportError, ModuleNotFoundError, AttributeError, AssertionError), reason=...) with strict=False (default) so the suite passes as a whole — Plans 02/03/04 flip them GREEN by landing cover_art_mb."
  - "ART-MB-06 latest-wins queue test pins `musicstreamer.cover_art_mb._spawn_worker(target, args)` as the SOLE threading.Thread call site — Plan 02 Task 1 step 18 must implement this contract so the test can monkeypatch the seam without spawning real threads."

patterns-established:
  - "Pitfall 8 (corrected): idempotent ALTER TABLE for new stations columns lands AFTER the legacy URL-rebuild block, not before. Future schema bumps on the stations table should follow this position unless the column is ALSO added to the rebuild's CREATE + INSERT SELECT."
  - "Wave 0 RED scaffold xfail idiom: raise the specific expected exception types (ImportError + AssertionError + AttributeError) so that Plan-02/03/04's GREEN-turn is unambiguous — pytest will report 'unexpectedly passed' if a downstream plan accidentally satisfies a Wave 0 contract differently than designed."

requirements-completed: [ART-MB-11]

# Metrics
duration: 14min
completed: 2026-05-13
---

# Phase 73 Plan 01: Foundation Summary

**ART-MB requirement family registered + Station.cover_art_source dataclass field + idempotent SQLite migration (post-rebuild placement) + 6 MB JSON fixtures + 11 xfail-marked Wave 0 RED scaffolds pinning the `_spawn_worker` latest-wins seam for Plan 02.**

## Performance

- **Duration:** ~14 min
- **Started:** 2026-05-13T19:08:00-05:00 (plan read)
- **Completed:** 2026-05-13T19:21:40-05:00 (final task commit)
- **Tasks:** 3 of 3
- **Files modified:** 5
- **Files created:** 9 (6 fixtures + 2 test files + 1 deferred-items.md)
- **Tests added:** 14 (3 GREEN repo migration tests + 11 xfail RED scaffolds)

## Accomplishments

- 16 unchecked **ART-MB-NN** rows registered under a new `### Cover-Art Sources (ART-MB)` heading in REQUIREMENTS.md; v2.1 OoS row "MusicBrainz cover art fallback" removed (this phase IS the revisit referenced by that line); Traceability table extended; Coverage bumped 22→38 total / 2→18 pending.
- `Station.cover_art_source: Literal["auto", "itunes_only", "mb_only"] = "auto"` added with a keyword default so positional-args callers (test_edit_station_dialog.py:252 args[6] for icy_disabled) continue to work.
- Idempotent `ALTER TABLE stations ADD COLUMN cover_art_source TEXT NOT NULL DEFAULT 'auto'` in `repo.db_init()`. Placed POST-rebuild (deviation Rule 1, documented below) — survives both fresh-DB and legacy-URL-rebuild migration paths. Verified via `test_cover_art_source_migration_idempotent`: PRAGMA reports name='cover_art_source', notnull=1, dflt_value="'auto'".
- All 4 `Station(...)` constructor sites in repo.py (`list_stations`, `get_station`, `list_recently_played`, `list_favorite_stations`) extended to read the new column with a defensive `or "auto"` fallback.
- 6 MB JSON fixtures land verbatim from RESEARCH §"Code Examples" live-probed shape (2026-05-13 probe of Daft Punk recording search). Covers Pitfall 1 (Hey-Jude bootleg-top-5), Pitfall 3 (tags-key-absent), Pitfall 7 (503 rate-limit body), D-09 boundary (score=79 reject / score=85 accept).
- `tests/test_cover_art_mb.py` ships 10 xfail-marked tests covering ART-MB-01/02/03/04/05/06/13/14/15/16. The ART-MB-06 test pins `_spawn_worker(target, args)` as the SOLE call site Plan 02 must wrap `threading.Thread` through — without that seam, Plan 02's latest-wins queue cannot be unit-tested without spawning real worker threads.
- `tests/test_cover_art_routing.py` ships 1 xfail-marked test for ART-MB-09 with the double-patch idiom (`cover_art_mod.urllib.request.urlopen` + `cover_art_mb.urllib.request.urlopen`) so Plan 03 can flip it GREEN by landing the router refactor.
- VALIDATION.md updated: `wave_0_complete: true`, ART-MB-11 status flipped to ✅ green, 4 of 8 Wave 0 checklist items marked complete.

## Task Commits

Each task was committed atomically:

1. **Task 1: Register ART-MB-01..16 in REQUIREMENTS.md and remove the now-stale OoS row** — `a541bf5` (docs)
2. **Task 2: Add Station.cover_art_source field and schema migration in repo.db_init** — `5429be4` (feat)
3. **Task 3: Scaffold Wave 0 test files + 6 MB JSON fixtures so Plans 02/03/04 can run RED→GREEN** — `3fc8534` (test)

_Task 2 includes the Rule 1 deviation discussed below — schema migration ordering moved post-rebuild within the same atomic commit (caught via test_migration_url_to_streams failure during in-task verification, before commit was created)._

## Files Created/Modified

- `.planning/REQUIREMENTS.md` — Added `### Cover-Art Sources (ART-MB)` section (16 reqs), removed stale OoS row, extended Traceability with 16 ART-MB → Phase 73 → Pending rows, bumped Coverage (22→38 total / 2→18 pending), updated Last-updated line to 2026-05-13.
- `musicstreamer/models.py` — Added `Literal` import; added `cover_art_source: Literal["auto", "itunes_only", "mb_only"] = "auto"` field between `icy_disabled` and `streams` (keyword default preserves positional-args compat).
- `musicstreamer/repo.py` — Added idempotent ALTER TABLE block POST-rebuild (lines ~180-194). Extended all 4 Station(...) constructor sites (list_stations / get_station / list_recently_played / list_favorite_stations) to read `cover_art_source=r["cover_art_source"] or "auto"`.
- `tests/test_repo.py` — Added 3 new GREEN tests: `test_cover_art_source_default_is_auto`, `test_cover_art_source_round_trip` (direct SQL UPDATE — Plan 03 extends `update_station`), `test_cover_art_source_migration_idempotent` (PRAGMA assertion satisfying ART-MB-11).
- `tests/fixtures/mb_recording_search_clean_album_hit.json` — Daft Punk shape: score=100, Official+Album, tags=[house:5, dance:1].
- `tests/fixtures/mb_recording_search_bootleg_only.json` — 5 recordings, all score=100, all Bootleg/Promotion (Pitfall 1: ladder must reject).
- `tests/fixtures/mb_recording_search_score_79.json` — D-09 reject boundary.
- `tests/fixtures/mb_recording_search_score_85.json` — D-09 accept boundary; distinct release MBID `aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee`.
- `tests/fixtures/mb_recording_search_no_tags.json` — Pitfall 3: `tags` key entirely absent from recording dict.
- `tests/fixtures/mb_recording_search_503_body.json` — Pitfall 7: MB 503 rate-limit body verbatim from MB API docs.
- `tests/test_cover_art_mb.py` (NEW, 369 lines) — 10 xfail-marked RED scaffolds for ART-MB-01/02/03/04/05/06/13/14/15/16.
- `tests/test_cover_art_routing.py` (NEW, 87 lines) — 1 xfail-marked RED scaffold for ART-MB-09 (double-patch idiom).
- `.planning/phases/73-musicbrainz-album-cover-lookup-complement-itunes-with-smart-/73-VALIDATION.md` — Flipped `wave_0_complete: true`; ART-MB-11 status → ✅ green; marked Wave 0 checklist items delivered by Plan 01.
- `.planning/phases/73-musicbrainz-album-cover-lookup-complement-itunes-with-smart-/deferred-items.md` (NEW) — Logged 3 pre-existing test failures discovered during Task 3 verification (test_import_dialog_qt, test_main_window_media_keys/gbs, test_main_window_node_indicator) — all confirmed via `git stash` bisect to predate Plan 01, all outside the Phase 73 cover-art surface.

## Decisions Made

- **Migration placement: POST-rebuild, not pre-rebuild.** Plan instruction literally said "Place it right after the existing is_favorite ALTER at line 91-94" (pre-rebuild), but the plan's narrative INTENT was "the ALTER lands the column on the rebuilt table afterward". Test evidence (test_migration_url_to_streams failing with `IndexError: No item with that key` at repo.py:332 — the new `cover_art_source=r["cover_art_source"]` mapping site, run against a row whose stations table got rebuilt without the column) forces post-rebuild placement. Pre-rebuild ALTER would land on the original stations table, then the legacy rebuild's CREATE TABLE stations_new (which DOES NOT mention cover_art_source) + INSERT SELECT + DROP/RENAME would silently strip the column. Post-rebuild placement reapplies the ALTER cleanly. Documented as Rule 1 deviation.
- **xfail with explicit `raises=` tuple, not bare xfail.** Each scaffold lists the exact exception types it expects (ImportError + ModuleNotFoundError + AttributeError + AssertionError [+ TypeError for the routing test, + FileNotFoundError for the source-grep tests]) so pytest will report "unexpectedly passed" if Plan 02/03/04 accidentally satisfies the contract via a different code path — sharper feedback than letting any exception count as xfail.
- **`_spawn_worker(target, args)` seam pinned in test name AND test body.** The ART-MB-06 test docstring and code explicitly call out `monkeypatch.setattr(cover_art_mb, "_spawn_worker", recording_stub)` — so the seam name is a contract between Plan 01's test and Plan 02's implementation. Renaming it later would break the pin and require a coordinated Plan 02 + Plan 01 amendment.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Moved ALTER TABLE cover_art_source from pre-rebuild to post-rebuild placement**
- **Found during:** Task 2 (Add Station.cover_art_source field and schema migration in repo.db_init) — caught by `test_migration_url_to_streams` failing during in-task pytest verification before the commit was created.
- **Issue:** Plan instruction said "Place it right after the existing is_favorite ALTER at line 91-94" (pre-rebuild). When the ALTER is placed there, the subsequent legacy URL-column rebuild block (lines 122-179) runs `CREATE TABLE stations_new (... id, name, provider_id, tags, station_art_path, album_fallback_path, icy_disabled, last_played_at, is_favorite, created_at, updated_at ...)` — which does NOT include `cover_art_source` — then `INSERT INTO stations_new SELECT ...` + `DROP TABLE stations` + `RENAME stations_new TO stations`. Net effect: the legacy rebuild silently strips the column added moments earlier. The next call to `list_stations()` then fails at `cover_art_source=r["cover_art_source"]` with `IndexError: No item with that key`.
- **Fix:** Moved the ALTER block AFTER the legacy-rebuild try/except (lines ~180-194 in the post-edit file). This satisfies the plan's narrative intent ("the ALTER lands the column on the rebuilt table afterward") and matches the actual Pitfall 8 contract ("either ALTER before AND include in rebuild's CREATE/SELECT, OR ALTER after the rebuild"). The Plan's literal instruction conflicted with its own stated intent; the test caught it.
- **Files modified:** `musicstreamer/repo.py` (post-rebuild placement + clarifying comment citing Pitfall 8).
- **Verification:** `test_migration_url_to_streams` GREEN; all 64 test_repo.py tests GREEN including the 3 new ART-MB-11 tests; full Phase 73 surface (309 + 11 xfailed) GREEN.
- **Committed in:** `5429be4` (Task 2 atomic commit).

---

**Total deviations:** 1 auto-fixed (1 Rule 1 bug)
**Impact on plan:** Necessary correction to a self-contradictory instruction. The plan's literal placement instruction conflicted with its narrative intent; the test caught it before commit. No scope creep — the fix preserves the plan's intent and the only changed line is the ALTER block's location within db_init. Pattern documented in the post-rebuild comment for future schema-bump phases.

## Issues Encountered

- **Pre-existing test failures discovered during Task 3 full-suite verification** — `tests/test_import_dialog_qt.py::test_audioaddict_tab_widgets` (AttributeError on `_aa_quality`), `tests/test_main_window_media_keys.py` setup ERRORs (FakePlayer missing `underrun_recovery_started`), `tests/test_main_window_gbs.py` (same FakePlayer setup), `tests/ui_qt/test_main_window_node_indicator.py::test_hamburger_indicator_present_when_node_missing`. All confirmed via `git stash` bisect to predate Plan 01 — none touch the cover-art / repo / models surface modified by this plan. Logged to `.planning/phases/73-.../deferred-items.md` per the GSD scope boundary rule. Not fixed.
- **Pre-existing typo in 73-RESEARCH.md** — `### Alternatives Considered/` (stray trailing slash) showed up in `git diff` as a modification I didn't make. Not staged, not in Plan 01's scope — left alone.

## User Setup Required

None — all changes are code/test/docs in-repo. No external service configuration, no new env vars, no Windows-bundle bumps.

## Next Phase Readiness

- **Plan 73-02 (Wave 2, MB worker module)** can begin: it consumes the 10 xfail scaffolds in `tests/test_cover_art_mb.py`, the 6 MB JSON fixtures, and the Station.cover_art_source field. The `_spawn_worker(target, args)` seam contract is pinned in the ART-MB-06 test — Plan 02 Task 1 step 18 must implement that exact attribute name.
- **Plan 73-03 (Wave 3, router refactor)** can begin in parallel with Plan 02 once cover_art_mb.py exists: it consumes the test_cover_art_routing.py xfail scaffold for ART-MB-09 and the new `source=` keyword on `fetch_cover_art`.
- **Plan 73-04 (Wave 4, UI + settings export)** is unblocked: the Station.cover_art_source field is the schema contract for the EditStationDialog selector and the settings_export round-trip.
- **No blockers.** The pre-existing test failures logged in deferred-items.md are not in the Phase 73 surface and will not block downstream plans.

## Self-Check: PASSED

**Verified post-creation:**

- File `tests/fixtures/mb_recording_search_clean_album_hit.json` — FOUND (commit 3fc8534).
- File `tests/fixtures/mb_recording_search_bootleg_only.json` — FOUND.
- File `tests/fixtures/mb_recording_search_score_79.json` — FOUND.
- File `tests/fixtures/mb_recording_search_score_85.json` — FOUND.
- File `tests/fixtures/mb_recording_search_no_tags.json` — FOUND.
- File `tests/fixtures/mb_recording_search_503_body.json` — FOUND.
- File `tests/test_cover_art_mb.py` — FOUND (10 xfail tests collect cleanly).
- File `tests/test_cover_art_routing.py` — FOUND (1 xfail test collects cleanly).
- File `musicstreamer/models.py` cover_art_source field — FOUND (`Station(id=1, ...).cover_art_source == 'auto'` smoke test passes).
- File `musicstreamer/repo.py` ALTER block — FOUND post-rebuild.
- File `.planning/REQUIREMENTS.md` ART-MB section — FOUND (16 unchecked entries; OoS row removed).
- Commit `a541bf5` (Task 1) — FOUND in git log.
- Commit `5429be4` (Task 2) — FOUND in git log.
- Commit `3fc8534` (Task 3) — FOUND in git log.

---
*Phase: 73-musicbrainz-album-cover-lookup-complement-itunes-with-smart-*
*Completed: 2026-05-13*
