---
phase: 73
status: PHASE COMPLETE
verified_at: 2026-05-13
score: 16/16 ART-MB requirements verified (manual UAT pending user)
verified_by: claude-opus-4-7-1m (gsd-verifier, goal-backward)
---

# Phase 73: MusicBrainz album-cover lookup — Verification Report

**Phase Goal (from ROADMAP.md):** Add MusicBrainz + Cover Art Archive as an additive per-station cover-art source complementing iTunes (3-mode selector: Auto / iTunes-only / MB-only; Auto = iTunes→MB fallback) with a 1-req/sec rate gate, Lucene-escaped recording search, score≥80 acceptance + Official+Album+earliest release selection, and round-trip persistence through settings_export, while preserving the existing iTunes path unchanged for legacy stations.

**Verification mode:** Initial. No prior VERIFICATION.md found.

## Goal Achievement — Clause-by-Clause

| # | Goal Clause | Status | Evidence in Codebase |
|---|-------------|--------|---------------------|
| 1 | "additive per-station cover-art source complementing iTunes" | VERIFIED | `cover_art.py:185` `_itunes_attempt(icy_string, callback)` is the historic worker, intact; the router delegates to MB only when needed |
| 2 | "preserving the existing iTunes path unchanged for legacy stations" | VERIFIED | `cover_art.py:91-128` `_itunes_attempt` is the verbatim historic worker body (extracted with no behavior change); `itunes_only` mode short-circuits to it directly |
| 3 | "3-mode selector: Auto / iTunes-only / MB-only" | VERIFIED | `models.py:36` `cover_art_source: Literal["auto","itunes_only","mb_only"] = "auto"`; `edit_station_dialog.py:412-418` three QComboBox entries, non-editable |
| 4 | "Auto = iTunes→MB fallback" | VERIFIED | `cover_art.py:212-226` `_on_itunes_done` closure dispatches to `_cover_art_mb.fetch_mb_cover` only when iTunes returned `None` |
| 5 | "1-req/sec rate gate" | VERIFIED | `cover_art_mb.py:130-155` `_MbGate.wait_then_mark()` uses `time.monotonic()` floor + `time.sleep` under lock; module-level singleton `_GATE` |
| 6 | "Lucene-escaped recording search" | VERIFIED | `cover_art_mb.py:82-111` `_escape_lucene` single-pass handles 13 specials + 2 two-char operators (&&, \|\|); applied at `_build_mb_query:121-122` |
| 7 | "score≥80 acceptance" | VERIFIED | `cover_art_mb.py:175` `accepted = [r for r in recordings if (r.get("score") or 0) >= 80]` |
| 8 | "Official+Album+earliest release selection" | VERIFIED | `cover_art_mb.py:182-215` `_pick_release_mbid` 2-step ladder (D-10 step 1+2, step 3 explicitly deferred per CONTEXT 2026-05-13) |
| 9 | "round-trip persistence through settings_export" | VERIFIED | `settings_export.py:120` `_station_to_dict`, line 510 INSERT, line 573 UPDATE all write `cover_art_source`; lines 522, 586 default to 'auto' on missing key (Pitfall 9 forward-compat) |

**All 9 clauses VERIFIED.**

## Observable Truths (must-haves)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| T1 | iTunes path remains intact for legacy stations | VERIFIED | `cover_art.py:91-128`, `cover_art.py:185` ; junk-title gate unchanged at line 179-181 |
| T2 | Per-station mode is persisted in SQLite with default 'auto' | VERIFIED | `repo.py:190` `ALTER TABLE stations ADD COLUMN cover_art_source TEXT NOT NULL DEFAULT 'auto'`; `test_cover_art_source_migration_idempotent` GREEN |
| T3 | Mode selector wires read → save → DB persistence | VERIFIED | `edit_station_dialog.py:412-418` (combo), `:554-557` (read), `:1417-1436` (save passes `cover_art_source=` kwarg); `test_cover_art_source_combo_save_passes_kwarg_to_update_station` GREEN |
| T4 | MB-only mode never invokes iTunes | VERIFIED | `cover_art.py:188-198`: `mb_only` dispatches directly to `_cover_art_mb.fetch_mb_cover` without engaging iTunes; `test_mb_only_mode_does_not_call_itunes_urlopen` GREEN; `cover_art_mb.py` has no `itunes.apple.com` reference |
| T5 | iTunes-only mode never invokes MB | VERIFIED | `cover_art.py:183-186`: `itunes_only` dispatches to `_itunes_attempt` only; `test_itunes_only_mode_does_not_call_mb` GREEN |
| T6 | Auto mode falls through to MB on iTunes miss | VERIFIED | `cover_art.py:212-226`; `tests/test_cover_art_routing.py::test_auto_mode_falls_through_to_mb_when_itunes_misses` GREEN |
| T7 | 1-req/sec gate uses time.monotonic, not a comment | VERIFIED | `cover_art_mb.py:152-155` references `time.monotonic()` outside comments; `test_rate_gate_uses_monotonic` source-grep gate GREEN |
| T8 | User-Agent literal contains "MusicStreamer/" and the GitHub URL on BOTH MB and CAA | VERIFIED | `cover_art_mb.py:72-75` `_USER_AGENT` constant; `:247` and `:269` set on both `Request`; `test_user_agent_string_literals_present` GREEN; `test_mb_request_carries_user_agent` and `test_caa_request_carries_user_agent` GREEN |
| T9 | Score=85 accepted, score=79 rejected, bare-title skips MB | VERIFIED | `cover_art_mb.py:174-179`; `test_score_threshold_rejects_below_80_accepts_at_or_above_80` GREEN |
| T10 | D-07 bare-title gate enforced in router (mb_only and auto) | VERIFIED | `cover_art.py:192-195` (mb_only), `:208-222` (auto); `_split_artist_title:131-144` |
| T11 | Release ladder selects Official+Album+earliest over Bootleg with same score | VERIFIED | `cover_art_mb.py:182-215`; `test_release_selection_ladder_picks_official_album_over_bootleg` GREEN |
| T12 | Latest-wins queue collapses 5 rapid arrivals to ≤2 spawns | VERIFIED | `cover_art_mb.py:284-323` `_pending` + `_in_flight` + `_spawn_worker` seam; `test_latest_wins_queue_drops_superseded_jobs` GREEN |
| T13 | HTTP 503 from MB → callback(None), no raise | VERIFIED | `cover_art_mb.py:248-254` bare except → return None; `:362-369` worker also catches; `test_mb_503_falls_through_to_callback_none` GREEN |
| T14 | MB tags → genre: highest-count wins, empty → "" | VERIFIED | `cover_art_mb.py:218-232` sorted by `-count`; `test_genre_from_tags_picks_highest_count` GREEN |
| T15 | Settings export round-trips cover_art_source with forward-compat default | VERIFIED | `settings_export.py:120`, `:510-522`, `:573-586`; 5 tests (`test_export_payload_contains_cover_art_source`, `test_import_insert_persists_cover_art_source`, `test_import_replace_persists_cover_art_source`, `test_import_insert_missing_cover_art_source_defaults_to_auto`, `test_import_replace_missing_cover_art_source_defaults_to_auto`) all GREEN |
| T16 | NowPlayingPanel forwards station.cover_art_source as source kwarg | VERIFIED | `now_playing_panel.py:1192-1197`; 4 tests (mb_only/itunes_only/no-station/no-attr) all GREEN |

**Score: 16/16 truths VERIFIED.**

## Requirement Coverage (ART-MB-01..16)

| Req ID | Behavior | Test | Status | Source Evidence |
|--------|----------|------|--------|-----------------|
| ART-MB-01 | UA literal on MB API request | `test_mb_request_carries_user_agent` | SATISFIED | `cover_art_mb.py:247` |
| ART-MB-02 | UA literal on CAA image request | `test_caa_request_carries_user_agent` | SATISFIED | `cover_art_mb.py:269` |
| ART-MB-03 | 1 req/sec gate via monotonic clock | `test_mb_gate_serializes_with_1s_floor` | SATISFIED | `cover_art_mb.py:149-155` |
| ART-MB-04 | Score=85 accepted; score=79 rejected; bare-title skips | `test_score_threshold_rejects_below_80_accepts_at_or_above_80` | SATISFIED | `cover_art_mb.py:174-179` |
| ART-MB-05 | Release ladder: Official+Album wins | `test_release_selection_ladder_picks_official_album_over_bootleg` | SATISFIED | `cover_art_mb.py:198-212` |
| ART-MB-06 | Latest-wins queue ≤ 2 spawns | `test_latest_wins_queue_drops_superseded_jobs` | SATISFIED | `cover_art_mb.py:284-323`, `:449-471` |
| ART-MB-07 | MB-only must not call iTunes | `test_mb_only_mode_does_not_call_itunes_urlopen` | SATISFIED | `cover_art.py:188-198` |
| ART-MB-08 | iTunes-only must not call MB | `test_itunes_only_mode_does_not_call_mb` | SATISFIED | `cover_art.py:183-186` |
| ART-MB-09 | Auto falls through to MB on iTunes miss | `test_auto_mode_falls_through_to_mb_when_itunes_misses` | SATISFIED | `cover_art.py:212-226` |
| ART-MB-10 | Settings export round-trip + forward-compat | 5 tests in test_settings_export.py | SATISFIED | `settings_export.py:120, 510, 522, 573, 586` |
| ART-MB-11 | SQLite migration idempotent, DEFAULT 'auto' | `test_cover_art_source_migration_idempotent` | SATISFIED | `repo.py:190` |
| ART-MB-12 | EditStationDialog selector reads + writes field | `test_cover_art_source_combo_save_passes_kwarg_to_update_station` | SATISFIED | `edit_station_dialog.py:412-418, 554-557, 1417-1436` |
| ART-MB-13 | Highest-count MB tag → genre; empty → "" | `test_genre_from_tags_picks_highest_count` | SATISFIED | `cover_art_mb.py:218-232` |
| ART-MB-14 | HTTP 503 → callback(None), no raise | `test_mb_503_falls_through_to_callback_none` | SATISFIED | `cover_art_mb.py:248-254, 362-369` |
| ART-MB-15 | Source-grep: UA literals in cover_art_mb.py | `test_user_agent_string_literals_present` | SATISFIED | `cover_art_mb.py:72-75` |
| ART-MB-16 | Source-grep: gate references `time.monotonic` | `test_rate_gate_uses_monotonic` | SATISFIED | `cover_art_mb.py:152-155` |

**16/16 requirements SATISFIED with corresponding GREEN test.**

## Locked Decision (D-NN) Compliance

| Decision | Honored? | Evidence |
|----------|----------|----------|
| D-01 | YES | `models.py:36` 3-value Literal field on Station |
| D-02 | YES | `cover_art.py:212-226` Auto = iTunes→MB closure chain |
| D-03 | YES | `cover_art.py:183-186` `itunes_only` dispatches only to `_itunes_attempt` |
| D-04 | YES | `cover_art.py:188-198` `mb_only` never calls iTunes; `cover_art_mb.py` has zero references to `itunes.apple.com` (only doc/comment mentions of `last_itunes_result` shared variable name) |
| D-05 | YES | `repo.py:190` `DEFAULT 'auto'` backfills all rows; new stations get 'auto' from dataclass default |
| D-06 | YES | `edit_station_dialog.py:412-418` combo placed in QFormLayout after icy_checkbox |
| D-07 | YES | `cover_art.py:131-144` `_split_artist_title` short-circuit; `cover_art_mb.py:432-447` also short-circuits |
| D-08 | YES | `cover_art_mb.py:121-127` Lucene query with limit=10 (RESEARCH OQ-4 RESOLVED) |
| D-09 | YES | `cover_art_mb.py:175` `score >= 80` filter |
| D-10 | YES (steps 1+2 only) | `cover_art_mb.py:198-215`; step 3 deferred per CONTEXT revision 2026-05-13 |
| D-11 | YES | `cover_art_mb.py:268` `/front-250` variant |
| D-12 | YES | No cache: zero `cache`, `TTL`, or `memo` references in cover_art_mb.py |
| D-13 | YES | `cover_art_mb.py:284-323` `_pending` (maxsize=1) + `_in_flight` flag |
| D-14 | YES | `cover_art_mb.py:152-155` `time.monotonic()` floor with sleep-under-lock |
| D-15 | YES | `cover_art_mb.py:218-232` highest-count tag, '' on no tags |
| D-16 | YES | `cover_art_mb.py` does not import or call iTunes endpoints |
| D-17 | YES | `cover_art.py:212-217` iTunes hit delivers directly; iTunes worker writes `last_itunes_result` at line 113-114 |
| D-18 | YES | `cover_art_mb.py:247` (MB) + `cover_art_mb.py:269` (CAA) both set User-Agent |
| D-19 | YES | `_GATE.wait_then_mark()` called only in `_do_mb_search:245`, NOT in `_fetch_caa_image:267-275` |
| D-20 | YES | `cover_art_mb.py:248-254` (MB), `:273-275` (CAA), `:362-369` (worker), `:472-481` (entry) all bare-except → callback(None) |

**All 20 locked decisions honored.**

## Source-Grep Gates

| Gate | Required | Actual | Status |
|------|----------|--------|--------|
| `grep "MusicStreamer/" cover_art_mb.py` | ≥1 | 3 | PASS |
| `grep "https://github.com/lightningjim/MusicStreamer" cover_art_mb.py` | ≥1 | 2 | PASS |
| `grep "time.monotonic" cover_art_mb.py` | ≥1 | 5 | PASS |
| `grep -c "_spawn_worker" cover_art_mb.py` | ≥2 | 3 | PASS |
| `update_station(` in edit_station_dialog.py passes `cover_art_source=` within 30 lines | 1/1 call site | 1/1 (line 1428→1436) | PASS |
| `test_every_update_station_call_passes_cover_art_source_kwarg` | passing | passing | PASS |

**All grep gates GREEN.**

## Test Suite Results

```
$ uv run --with pytest --with pytest-qt pytest \
    tests/test_cover_art.py tests/test_cover_art_mb.py tests/test_cover_art_routing.py \
    tests/test_repo.py tests/test_edit_station_dialog.py \
    tests/test_settings_export.py tests/test_now_playing_panel.py -q

345 passed, 2 warnings in 5.36s
```

The teardown stderr noise (`RuntimeError: Signal source has been deleted`) seen during `-x` runs is a pre-existing teardown race in `test_now_playing_panel.py` (the iTunes worker daemon thread fires its callback after the panel has been garbage-collected). It does NOT cause any test to fail — full suite reports `345 passed`. Confirmed via Plan 04 SUMMARY: pre-existing background-noise, unrelated to Phase 73 changes.

### Targeted requirement-test verification

```
test_repo.py::test_cover_art_source_migration_idempotent              PASSED  [ART-MB-11]
test_cover_art_mb.py::test_user_agent_string_literals_present         PASSED  [ART-MB-15]
test_cover_art_mb.py::test_rate_gate_uses_monotonic                   PASSED  [ART-MB-16]
test_cover_art_mb.py::test_caa_request_carries_user_agent             PASSED  [ART-MB-02]
test_cover_art_mb.py::test_mb_503_falls_through_to_callback_none      PASSED  [ART-MB-14]
test_cover_art_routing.py::test_auto_mode_falls_through_to_mb_...     PASSED  [ART-MB-09]
test_cover_art_routing.py::test_auto_mode_itunes_hit_does_not_call_mb PASSED
test_edit_station_dialog.py::test_every_update_station_call_...       PASSED  [source-grep kwarg gate]
test_edit_station_dialog.py::test_cover_art_source_combo_save_...     PASSED  [ART-MB-12]
```

## Required Artifacts

| Artifact | Status | Evidence |
|----------|--------|----------|
| `musicstreamer/cover_art.py` (router) | VERIFIED | 226 lines, source-aware dispatch present (lines 147-226); iTunes path preserved at lines 91-128 |
| `musicstreamer/cover_art_mb.py` (NEW) | VERIFIED | 482 lines; UA constant, _MbGate (monotonic), _escape_lucene, _pick_recording (score≥80), _pick_release_mbid (D-10 steps 1+2), _genre_from_tags, _spawn_worker seam, _worker drain-loop, fetch_mb_cover entry |
| `musicstreamer/models.py` Station.cover_art_source | VERIFIED | Line 36 with default 'auto' |
| `musicstreamer/repo.py` migration + update_station kwarg | VERIFIED | Line 190 ALTER TABLE; line 389 `cover_art_source='auto'` kwarg; line 407 UPDATE SQL |
| `musicstreamer/ui_qt/edit_station_dialog.py` QComboBox | VERIFIED | Lines 412-418 combo, 554-557 populate, 1417-1436 save with kwarg |
| `musicstreamer/ui_qt/now_playing_panel.py` pass-through | VERIFIED | Lines 1192-1197 derive source + pass `source=source` to fetch_cover_art |
| `musicstreamer/settings_export.py` round-trip | VERIFIED | Line 120 export, 510 INSERT, 522 forward-compat, 573 UPDATE, 586 forward-compat |
| `tests/test_cover_art_mb.py` | VERIFIED | 11 tests, all GREEN |
| `tests/test_cover_art_routing.py` | VERIFIED | 2 tests, all GREEN |
| `tests/fixtures/mb_recording_search_*.json` | VERIFIED | 6 files present |

## Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| `cover_art.fetch_cover_art` | `cover_art_mb.fetch_mb_cover` | import + call in Auto + MB-only branches | WIRED (`cover_art.py:28, 197, 224`) |
| `edit_station_dialog._on_save` | `repo.update_station` | passes `cover_art_source=cover_art_source` kwarg | WIRED (`edit_station_dialog.py:1428-1437`) |
| `now_playing_panel._fetch_cover_art_async` | `cover_art.fetch_cover_art` | passes `source=source` derived from station | WIRED (`now_playing_panel.py:1197`) |
| `repo.update_station` | `stations.cover_art_source` column | SQL UPDATE SET clause | WIRED (`repo.py:407`) |
| `settings_export._station_to_dict` → ZIP → import | `stations.cover_art_source` | INSERT + UPDATE SQL both columns | WIRED (`settings_export.py:120, 510, 573`) |
| `cover_art_mb._do_mb_search` | `_GATE.wait_then_mark()` | first call before urlopen | WIRED (`cover_art_mb.py:245`) |
| `cover_art_mb._do_mb_search` + `_fetch_caa_image` | User-Agent header | `Request(url, headers={...})` | WIRED (`cover_art_mb.py:247, 269`) |
| `cover_art_mb.fetch_mb_cover` (production thread) | `_spawn_worker` | sole `threading.Thread` call site | WIRED (`cover_art_mb.py:310-323, 471`) |

## Data Flow Trace (Level 4)

| Artifact | Variable | Source | Real Data? | Status |
|----------|----------|--------|------------|--------|
| `EditStationDialog.cover_art_source_combo` | currentData() | populated from `station.cover_art_source` read from DB | YES (read via `repo.get_station`, returns SQLite column) | FLOWING |
| `NowPlayingPanel._fetch_cover_art_async` source kwarg | `getattr(self._station, "cover_art_source", "auto")` | self._station is a Station dataclass instance from repo | YES | FLOWING |
| `cover_art_mb.fetch_mb_cover` cover image | returned via callback path | `tempfile.NamedTemporaryFile` written from real CAA bytes | YES (real HTTP fetch in production, mocked in tests) | FLOWING |
| `settings_export ZIP` | `cover_art_source` field in JSON | `_station_to_dict` reads from real Station instance | YES | FLOWING |

## Anti-Patterns Scan

| File | Pattern | Severity | Notes |
|------|---------|----------|-------|
| `cover_art_mb.py` | "deferred" debt marker | INFO | Line 36, 186, 214: D-10 step 3 explicitly deferred per CONTEXT 2026-05-13; not a code smell — locked planning decision |
| `cover_art_mb.py` | `pass` in worker bare-except (line 369, 481) | INFO | Intentional "never raise out" contract per D-20; mirrored from `cover_art.py:98` precedent |

No TBD/FIXME/XXX debt markers found in any Phase 73 modified file. No stub returns. No empty handlers. No hardcoded empty arrays at production sites.

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Station dataclass has new field with default 'auto' | `python -c "from musicstreamer.models import Station; s = Station(id=1, name='x', provider_id=None, provider_name=None, tags='', station_art_path=None, album_fallback_path=None); assert s.cover_art_source == 'auto'"` | OK | PASS |
| All 16 ART-MB rows in REQUIREMENTS.md | `grep -c "ART-MB-" .planning/REQUIREMENTS.md` (rows) | 16 reqs + 16 traceability | PASS |
| OoS row "MusicBrainz cover art fallback" removed | `grep "MusicBrainz cover art fallback" .planning/REQUIREMENTS.md` | (no match) | PASS |
| 6 MB fixtures exist | `ls tests/fixtures/mb_recording_search_*.json \| wc -l` | 6 | PASS |
| Full Phase 73 test surface | `pytest tests/test_cover_art*.py tests/test_repo.py tests/test_edit_station_dialog.py tests/test_settings_export.py tests/test_now_playing_panel.py -q` | 345 passed | PASS |

## Manual UAT (PENDING USER)

Per CONTEXT and Plan 05, three manual scenarios are documented in `73-UAT-SCRIPT.md` (348 lines, status=PENDING):

| Scenario | Behavior | Why Manual |
|----------|----------|------------|
| A | Real MB cover renders for a real station | Live MusicBrainz endpoint; non-deterministic content; requires running app |
| B | CAA-250 quality at 160×160 | Subjective visual assessment of pixelation |
| C | Cross-profile ZIP round-trip preserves cover_art_source | Two profiles + import/export workflow |

**These are NOT verification failures.** They are the manual half of the phase-completion contract per VALIDATION.md "Manual-Only Verifications". Pending the user running `73-UAT-SCRIPT.md` against a live Wayland session.

## Gaps Summary

**None.** All 16 ART-MB requirements have GREEN automated tests; all 20 locked CONTEXT decisions are honored in source; all source-grep gates pass; the iTunes path is preserved unchanged for legacy stations; all key links are wired end-to-end; data flows through every layer (UI → DB → router → worker → callback → Qt signal).

Pre-existing test failures (test_import_dialog_qt, test_main_window_media_keys, test_main_window_gbs, test_main_window_node_indicator) are logged in `deferred-items.md`; bisect-confirmed predates Phase 73; outside Phase 73 surface.

## PHASE COMPLETE

All automated verification gates GREEN. Phase 73 is implementation-complete. The orchestrator should display `73-UAT-SCRIPT.md` to the user for the three manual scenarios; on user PASS, mark Phase 73 closed and flip the 16 ART-MB-NN traceability rows from Pending → Complete.

---
*Verified: 2026-05-13*
*Verifier: Claude (gsd-verifier, goal-backward methodology)*
