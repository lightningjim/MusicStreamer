---
phase: 70-hi-res-indicator-for-streams-mirror-moode-audio-criteria
plan: 00
subsystem: testing
tags: [pytest, qt, gstreamer, classifier, tdd-red, wave-0, hi-res, hres-01]

# Dependency graph
requires:
  - phase: 47-stats-for-nerds-and-autoeq
    provides: "bitrate_kbps column + idempotent ALTER TABLE migration shape — mirrored verbatim by Plan 70-02 ALTER TABLE additions for sample_rate_hz / bit_depth (test_db_init_idempotent_for_sample_rate_hz pins the contract)"
  - phase: 62-audio-buffer-underrun-resilience-intermittent-dropouts-stutt
    provides: "Phase 62-00 idiom — RED via real ImportError/AttributeError/TypeError, no pytest.fail placeholders; locked into every Plan 70-00 test that references identifiers Plans 01-09 will introduce"
  - phase: 68-add-feature-for-detecting-live-performance-streams-di-fm-and
    provides: "_live_chip / set_live_only / update_live_map architecture in StationListPanel + StationFilterProxyModel — mirrored verbatim by _hi_res_chip / set_hi_res_only / update_quality_map per RESEARCH.md §Pattern 7"
provides:
  - "Wave 0 RED contract locking Phase 70 / HRES-01 public API across hi_res.py + Player + Repo + 6 UI surfaces"
  - "musicstreamer/hi_res.py empty skeleton — module docstring listing five public symbols Plan 70-01 implements"
  - "tests/test_hi_res.py — 5 RED functions covering classify_tier truth table + bit_depth_from_format (DS-02 mapping) + best_tier_for_station + TIER_LABEL_BADGE/PROSE constants"
  - "tests/test_player_caps.py — 6 RED functions covering audio_caps_detected Signal contract + threading invariant grep + Pitfall 6 one-shot disarm + ignore-unknown-format + ignore-zero-rate + no-double-emit"
  - "29 RED functions appended to 8 existing test modules (repo/stream_ordering/settings_export/station_filter_proxy/station_star_delegate/now_playing_panel/station_list_panel/edit_station_dialog) — pin Plans 70-02..70-09 contracts"
  - "Fixed prior-executor regression in test_repo.py — restored orphaned `assert b_streams[0].id == id_b1` to test_prune_streams_does_not_touch_other_stations (was misplaced at file end)"
affects: [70-01, 70-02, 70-03, 70-04, 70-05, 70-06, 70-07, 70-08, 70-09, 70-10]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wave 0 RED via real ImportError/AttributeError/TypeError — no pytest.fail() placeholders (Phase 62-00 / Phase 60.4 / Phase 999.1 idiom)"
    - "Threading invariant test via inspect.getsource() + comment-stripped substring assertion — locks qt-glib-bus-threading.md Rule 2 at the source level (Pattern 1b)"
    - "GREEN-by-coincidence regression-lock — test_picker_label_no_suffix_for_lossy_stream passes pre-70-06 because the label format already lacks the tier suffix; contract pins the lossy-branch guard once Plan 70-06 ships (Phase 60.2-01 precedent)"
    - "RED-on-two-axes — tests reference both NEW identifiers (Plan 70-01 hi_res.classify_tier) AND NEW StationStream fields (Plan 70-02 sample_rate_hz/bit_depth) so Plan 70-01 turns one axis GREEN, Plan 70-02 turns the other"
    - "Append-only test extension — section header `# --- Phase 70 / HRES-01 ---` marks the boundary in each of the 8 extended modules; existing tests untouched"

key-files:
  created:
    - "musicstreamer/hi_res.py — empty skeleton (docstring-only, 25 lines) listing the five public symbols Plan 70-01 implements"
    - "tests/test_hi_res.py — 5 RED test functions (parametrized truth tables expand to ~30 collected cases)"
    - "tests/test_player_caps.py — 6 RED test functions covering T-06 + threading invariant"
    - ".planning/phases/70-hi-res-indicator-for-streams-mirror-moode-audio-criteria/70-00-SUMMARY.md"
  modified:
    - "tests/test_repo.py — +3 tests (sample_rate_hz/bit_depth hydrate + db_init idempotent ALTER); restored orphaned assertion"
    - "tests/test_stream_ordering.py — +1 test (test_hires_flac_outranks_cd_flac) + _s helper extended with sample_rate_hz/bit_depth kwargs"
    - "tests/test_settings_export.py — +3 tests (ZIP round-trip + missing-key forward-compat + station_to_dict_emits_quality_keys)"
    - "tests/test_station_filter_proxy.py — +3 tests (set_hi_res_only + Pitfall 7 invalidate-guard + clear_all_clears_hi_res_only)"
    - "tests/test_station_star_delegate.py — +5 tests (HI-RES pill paint + LOSSLESS pill paint + no-pill-lossy + no-pill-provider + sizeHint grows)"
    - "tests/test_now_playing_panel.py — +7 tests (_quality_badge visibility/text/tooltip + picker tier suffix; 1 GREEN-by-coincidence regression-lock)"
    - "tests/test_station_list_panel.py — +4 tests (_hi_res_chip visibility gate + proxy toggle wiring)"
    - "tests/test_edit_station_dialog.py — +3 tests (_COL_AUDIO_QUALITY read-only column + prose label + header tooltip)"

key-decisions:
  - "Wave 0 RED idiom: ImportError / AttributeError / TypeError IS the contract — no pytest.fail() placeholders (Phase 62-00 STATE.md decision)"
  - "test_picker_label_no_suffix_for_lossy_stream ships GREEN-by-coincidence — pre-70-06 the label format already lacks the tier suffix; contract pins the lossy-branch guard once Plan 70-06 introduces the new format (Phase 60.2-01 precedent: test_clear_table_clears_spans documented as contract pin not defect repro)"
  - "Threading invariant grep strips comments via `lines = [l for l in src.splitlines() if not l.lstrip().startswith('#')]; joined = '\\n'.join(lines)` before substring check — Pitfall 7 docstring/comment counting hygiene per planner critical-rules"
  - "Test bodies reference Plan 70-02 StationStream(sample_rate_hz=N, bit_depth=N) kwargs that do not yet exist — TypeError on construction IS the RED state for picker/badge/cell tests (RED-on-two-axes pattern)"
  - "Test 3 extension landed atomically as one commit (86ae34e, 8 files) per Plan 70-00 Task 3 instruction — 'append (do not rewrite)' executed file-by-file but committed once"

patterns-established:
  - "Section-header marker `# --- Phase 70 / HRES-01 ---` placed at the bottom of each extended test module — future readers locate the Phase 70 boundary via grep without parsing diffs"
  - "RED-on-two-axes test construction — a single test may reference NEW class fields (Plan 70-02) AND NEW module functions (Plan 70-01) simultaneously; Plan 70-01 turns one axis GREEN, Plan 70-02 turns the other; final GREEN requires both"
  - "Repo subclass test helper — `_RepoWithStreams(FakeRepo)` in test_now_playing_panel.py overrides list_streams() to return caller-supplied streams (FakeRepo's default `return []` blocks picker-population tests); preferred over monkey-patching the base"

requirements-completed: [HRES-01]

# Metrics
duration: ~recovered (Wave 0 split across two sessions due to terminal interruption mid-Task-3)
completed: 2026-05-12
---

# Phase 70 Plan 00: Wave 0 RED Test Contract Summary

**Locked the Phase 70 / HRES-01 executable contract — 11 RED test functions in 2 new files plus 29 RED functions appended to 8 existing modules — encoding D-01..D-05, DS-01..DS-05, T-01..T-06, and the full UI-SPEC copywriting + visibility contract as machine-checkable assertions before any production code is written**

## Performance

- **Duration:** Wave 0 split across two sessions (terminal interruption mid-Task-3 forced a /gsd-progress --next recovery)
- **Started:** 2026-05-12 (initial session) — see prior commits d720999 + 2fc1ef7
- **Completed:** 2026-05-12 (recovery session)
- **Tasks:** 3
- **Files modified:** 11 (1 production skeleton + 2 new test modules + 8 extended test modules)

## Accomplishments

- 11 RED test functions in 2 new files (parametrized truth tables expand to ~40 collected cases)
- 29 RED functions appended to 8 existing test modules (HRES-01 SC #5 requires ≥25)
- Threading invariant for Player.audio_caps_detected pinned via inspect.getsource() + comment-stripped substring assertion (qt-glib-bus-threading.md Rule 2)
- Migration idempotency contract pinned via test_db_init_idempotent_for_sample_rate_hz (Phase 47.2 idiom)
- ZIP forward-compat for pre-Phase-70 settings exports locked via test_commit_import_forward_compat_missing_quality_keys (Phase 47.3 idiom)
- Pre-existing test_repo.py regression fixed — `assert b_streams[0].id == id_b1` restored to test_prune_streams_does_not_touch_other_stations after prior executor appended Phase 70 stubs in the middle of the function

## Task Commits

Each task was committed atomically (note: split across two sessions):

1. **Task 1: Create musicstreamer/hi_res.py empty skeleton + tests/test_hi_res.py RED stubs (T-01)** — `d720999` (test)
2. **Task 2: Create tests/test_player_caps.py RED stubs (T-06 + threading invariant)** — `2fc1ef7` (test)
3. **Task 3: Extend 8 existing test modules with RED stubs (T-02..T-05)** — `86ae34e` (test)

**Plan metadata:** _to be added on final docs commit_

## Files Created/Modified

- `musicstreamer/hi_res.py` (created, 25 lines) — docstring-only module skeleton; `python -c "import musicstreamer.hi_res"` succeeds, `python -c "from musicstreamer.hi_res import classify_tier"` raises ImportError (RED contract for Plan 70-01)
- `tests/test_hi_res.py` (created) — 5 functions: test_classify_tier_truth_table (parametrized 12 cases), test_bit_depth_from_format (parametrized DS-02 mapping ~17 cases), test_best_tier_for_station (4 sub-variants), test_tier_label_badge_constants, test_tier_label_prose_constants
- `tests/test_player_caps.py` (created, ~200 lines) — 6 functions: persists_rate_and_bit_depth, emitted_as_queued_signal, disarm_after_emit, ignores_unknown_format, ignores_zero_rate, no_double_emit_for_same_stream; local `make_player(qtbot)` + `_fake_caps_pad` helpers (no shared conftest extraction per PATTERNS.md)
- `tests/test_repo.py` (+3 tests) — sample_rate_hz_hydrated_from_row, bit_depth_hydrated_from_row, db_init_idempotent_for_sample_rate_hz (Phase 47.2 migration shape mirror)
- `tests/test_stream_ordering.py` (+1 test, _s helper extended) — test_hires_flac_outranks_cd_flac; `_s` helper gains sample_rate_hz/bit_depth kwargs (default 0 preserves test_gbs_flac_ordering regression invariant)
- `tests/test_settings_export.py` (+3 tests) — export_import_roundtrip_preserves_sample_rate_hz_and_bit_depth, commit_import_forward_compat_missing_quality_keys, station_to_dict_emits_quality_keys
- `tests/test_station_filter_proxy.py` (+3 tests) — set_hi_res_only_with_quality_map_filters_stations, set_quality_map_no_invalidate_when_chip_off (Pitfall 7 mirror), clear_all_clears_hi_res_only
- `tests/test_station_star_delegate.py` (+5 tests) — paints_hires_pill_for_hires_station, paints_lossless_pill_for_cd_flac_station, no_pill_for_lossy_station, no_pill_for_provider_row, sizehint_grows_for_pill
- `tests/test_now_playing_panel.py` (+7 tests, _RepoWithStreams helper) — quality_badge_visible_for_hires_stream, quality_badge_hidden_for_lossy_stream, quality_badge_text_matches_tier, quality_badge_tooltip_when_caps_known, quality_badge_tooltip_cold_start, picker_label_appends_tier_suffix, picker_label_no_suffix_for_lossy_stream (GREEN-by-coincidence regression-lock)
- `tests/test_station_list_panel.py` (+4 tests) — hi_res_chip_hidden_when_no_hi_res_streams, hi_res_chip_visible_after_update_quality_map_with_hires, set_hi_res_chip_visible_unchecks_when_hiding (Pitfall 7 mirror), hi_res_chip_toggle_calls_proxy_set_hi_res_only
- `tests/test_edit_station_dialog.py` (+3 tests) — audio_quality_column_present_and_read_only, audio_quality_cell_shows_prose_label, audio_quality_header_tooltip (UI-SPEC OD-8 string match)

## Decisions Made

- **Wave 0 RED via real ImportError/AttributeError/TypeError** — no `pytest.fail("not yet implemented")` placeholders. The import-time / access-time / construction-time failure IS the contract. Mirrors Phase 62-00 / Phase 60.4 / Phase 999.1 Wave 0 convention.
- **test_picker_label_no_suffix_for_lossy_stream as GREEN-by-coincidence regression-lock** — pre-Plan-70-06 the picker label format `f"{quality} — {codec}"` already lacks any tier suffix, so this test passes today; the contract pins the lossy-branch guard once Plan 70-06 introduces the new format that conditionally appends "— HI-RES" / "— LOSSLESS". Phase 60.2-01 precedent: `test_clear_table_clears_spans` was GREEN-by-coincidence and documented as contract pin not defect repro.
- **Threading invariant via comment-stripped substring assertion** — `inspect.getsource(musicstreamer.player)` + `lines = [l for l in src.splitlines() if not l.lstrip().startswith('#')]; joined = '\n'.join(lines); assert "audio_caps_detected" in joined and "QueuedConnection" in joined`. Locks qt-glib-bus-threading.md Rule 2 at the source level without counting comment lines (planner critical-rule on hygiene).
- **RED-on-two-axes test construction** — picker / badge / dialog cell tests use `StationStream(..., sample_rate_hz=N, bit_depth=N)` kwargs that do not yet exist (Plan 70-02 adds). The TypeError on construction IS the RED state for those tests in addition to the later assertion failure once Plan 70-02 ships.
- **Test 3 atomic commit, 8 files** — per Plan 70-00 Task 3 instruction "append (do not rewrite)" executed file-by-file (each module gains a Phase 70 / HRES-01 section after the last pre-existing test) but committed once as a single Task 3 atomic commit.

## Deviations from Plan

### Auto-fixed Issues

**1. [Test correctness] Prior-executor regression in test_repo.py**
- **Found during:** Task 3 worktree inspection (recovery session)
- **Issue:** The prior executor session (which committed Tasks 1 + 2) appended Phase 70 RED stubs in the MIDDLE of test_prune_streams_does_not_touch_other_stations, splitting the function. The final assertion `assert b_streams[0].id == id_b1` was orphaned at the file end (referencing variables not in scope), and test_prune_streams_does_not_touch_other_stations was left missing its last assertion. This would cause NameError on the orphaned line and weakened coverage on the prune test.
- **Fix:** Moved `assert b_streams[0].id == id_b1` back into test_prune_streams_does_not_touch_other_stations (right after `assert len(b_streams) == 1`) AND removed the orphaned trailing line. Net effect: test_prune_streams_does_not_touch_other_stations restored to its original 3-assertion form; Phase 70 db_init test still ends cleanly.
- **Files modified:** tests/test_repo.py
- **Verification:** `python3 -m pytest tests/test_repo.py -q --tb=no` runs without NameError; test_prune_streams_does_not_touch_other_stations passes (regression intact); 3 new Phase 70 tests fail RED as expected.
- **Committed in:** `86ae34e` (Task 3 commit)

### Acceptance-Criterion Discrepancy (documented, not auto-fixed)

**1. [Environmental] pytest collection via `uv run --with pytest --with pytest-qt pytest` fails for test_player_caps.py**
- **Found during:** Task 2 verification (recovery session)
- **Issue:** The plan's `<verify>` block specifies `uv run --with pytest --with pytest-qt pytest tests/test_player_caps.py --co -q`. This fails with `ModuleNotFoundError: No module named 'gi'` because musicstreamer/player.py imports `gi` (PyGObject) at module top, and PyGObject is not installable from PyPI on this platform — only the system Python (`/usr/bin/python3`) has it. The pre-existing test_player_tag.py has the same issue (also imports Player → import gi). This is a project-wide environmental constraint already documented in Phase 60.4-01 deferred-items (commit `a8e313a`).
- **Fix:** None applied in this plan. Used `python3 -m pytest` (system Python with PyGObject) for collection verification instead of `uv run`. Collection succeeds: 433 tests collected including all 6 test_player_caps.py functions.
- **Files modified:** None
- **Verification:** `python3 -m pytest tests/test_hi_res.py tests/test_player_caps.py tests/test_repo.py tests/test_stream_ordering.py tests/test_settings_export.py tests/test_station_filter_proxy.py tests/test_station_star_delegate.py tests/test_now_playing_panel.py tests/test_station_list_panel.py tests/test_edit_station_dialog.py --co -q` reports `433 tests collected in 0.62s`.
- **Committed in:** N/A (no code change; documented here for Plans 70-01..70-09 awareness)

---

**Total deviations:** 2 (1 auto-fixed prior-executor bug; 1 documented environmental constraint)
**Impact on plan:** Zero impact on the Phase 70 contract — all 40 new RED functions encode the contract Plans 70-01..70-09 must satisfy.

## Issues Encountered

- **Terminal interrupted mid-Task-3** — the previous /gsd-execute-phase session died between Task 2 commit (`2fc1ef7`) and Task 3 commit, leaving 5 of 8 test files modified in the worktree with no commit. The /gsd-progress --next recovery flow inspected the worktree, fixed the orphaned test_repo.py assertion, added the 3 missing test file extensions (test_now_playing_panel, test_station_list_panel, test_edit_station_dialog), verified RED state via system python3, and committed Task 3 as a single atomic commit. Three stale Phase 60.4 worktrees were also cleaned up during the recovery (all merged into main per `git merge-base --is-ancestor`).
- **Pre-existing test_logo_status_clears_after_3s flakiness** — passes 3/3 when run in isolation, fails intermittently in larger suites due to timing. Not a Phase 70 regression; pre-existing test_filter_strip_hidden_in_favorites_mode and test_refresh_recent_updates_list failures also pre-exist on main (verified by running them on the main checkout).

## Self-Check: PASSED

**Files verified to exist:**
- `musicstreamer/hi_res.py` — FOUND (docstring-only skeleton)
- `tests/test_hi_res.py` — FOUND (5 functions)
- `tests/test_player_caps.py` — FOUND (6 functions)
- 8 extended test modules — FOUND (each gains `# --- Phase 70 / HRES-01 ---` section)

**Commits verified to exist:**
- `d720999` — FOUND (Task 1: hi_res.py skeleton + test_hi_res.py)
- `2fc1ef7` — FOUND (Task 2: test_player_caps.py stubs)
- `86ae34e` — FOUND (Task 3: 8 module extensions, atomic)

**Verification gates passed:**
- ≥5 functions in test_hi_res.py (5 ✓)
- ≥6 functions in test_player_caps.py (6 ✓)
- ≥25 new functions across 8 extended modules (29 ✓)
- All new tests fail RED via real ImportError/AttributeError/TypeError (no pytest.fail) — verified by running each test file in isolation
- 1 GREEN-by-coincidence (test_picker_label_no_suffix_for_lossy_stream) documented as contract pin per Phase 60.2-01 precedent
- musicstreamer/hi_res.py import success; symbol import raises ImportError (RED contract for Plan 70-01)
- Existing tests in extended modules still pass (pre-existing failures verified to pre-date Phase 70)

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

**Ready for Wave 1 (Plans 70-01 + 70-02 in parallel):**
- Plan 70-01: implement pure-Python classifier in musicstreamer/hi_res.py — turns test_hi_res.py GREEN
- Plan 70-02: add StationStream.sample_rate_hz / bit_depth fields + Repo CRUD kwargs + idempotent ALTER TABLE migration — turns test_repo.py extensions GREEN AND unblocks test_stream_ordering / test_settings_export / test_now_playing_panel / test_edit_station_dialog tests that construct StationStream with the new kwargs

**Open questions for Plans 70-01..70-10:**
1. **Plan 70-01 / FLAC (0,0) default** — D-03 says FLAC with unknown rate/depth defaults to "lossless"; truth table test_classify_tier_truth_table pins `("FLAC", 0, 0) → "lossless"`. Plan 70-01's classify_tier must honor this default before the caps detector populates the cache.
2. **Plan 70-02 / migration shape** — test_db_init_idempotent_for_sample_rate_hz pins both `ALTER TABLE station_streams ADD COLUMN sample_rate_hz INTEGER NOT NULL DEFAULT 0` AND the idempotency (second db_init must not raise). Use the Phase 47.2 try/except sqlite3.OperationalError pattern verbatim.
3. **Plan 70-06 / picker label format** — UI-SPEC Component Inventory item 5 locks `"FLAC 1411 — HI-RES"` (em-dash + uppercase badge). Plan 70-06 _populate_stream_picker must conditionally append `" — {TIER_LABEL_BADGE[tier]}"` ONLY when tier != "" (D-04 guard). test_picker_label_no_suffix_for_lossy_stream pins the negative case.
4. **Plan 70-08 / _COL_AUDIO_QUALITY column index** — Plan 70-00 referenced _COL_AUDIO_QUALITY = 5 in test docstrings, but the actual column index depends on existing _COL_* constants in edit_station_dialog.py. Plan 70-08 should pick the next available index after the existing columns; the test imports the symbol by name, not the integer value.

**Blockers/concerns:**
- None. Wave 0 contract fully encoded; D-09 invariants preserved; no production code touched beyond the empty hi_res.py skeleton.

---
*Phase: 70-hi-res-indicator-for-streams-mirror-moode-audio-criteria*
*Completed: 2026-05-12*
