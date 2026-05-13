---
phase: 73
slug: musicbrainz-album-cover-lookup-complement-itunes-with-smart
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-13
last_updated: 2026-05-13
---

# Phase 73 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. See `73-RESEARCH.md` § *Validation Architecture* (line 610) for source.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest ≥ 9 + pytest-qt ≥ 4 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=["tests"]) |
| **Quick run command** | `uv run --with pytest --with pytest-qt pytest tests/test_cover_art.py tests/test_cover_art_mb.py tests/test_now_playing_panel.py -x` |
| **Full suite command** | `uv run --with pytest --with pytest-qt pytest tests` |
| **Estimated runtime** | ~30 sec (Phase 73 surface); ~3 min (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `uv run --with pytest --with pytest-qt pytest tests/test_cover_art.py tests/test_cover_art_mb.py -x` (~2–4 sec)
- **After every plan wave:** Run wave-scoped quick command (covers all Phase 73 touch points: cover_art, cover_art_mb, now_playing_panel, settings_export, repo, edit_station_dialog) (~30 sec)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 sec (wave gate); 4 sec (task gate)

---

## Per-Task Verification Map

| Req ID | Plan | Wave | Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|----------|-----------|-------------------|-------------|--------|
| ART-MB-01 | 02 | 2 | User-Agent header literal on MB API request matches `MusicStreamer/<version> (https://github.com/lightningjim/MusicStreamer)` | unit | `pytest tests/test_cover_art_mb.py::test_mb_request_carries_user_agent -x` | W0→Plan 01; GREEN→Plan 02 | ⬜ pending |
| ART-MB-02 | 02 | 2 | User-Agent header literal on CAA image request | unit | `pytest tests/test_cover_art_mb.py::test_caa_request_carries_user_agent -x` | W0→Plan 01; GREEN→Plan 02 | ⬜ pending |
| ART-MB-03 | 02 | 2 | 1 req/sec gate: 5 sequential MB calls span ≥ 4 seconds of monotonic clock | unit (mocked clock) | `pytest tests/test_cover_art_mb.py::test_mb_gate_serializes_with_1s_floor -x` | W0→Plan 01; GREEN→Plan 02 | ⬜ pending |
| ART-MB-04 | 02 | 2 | Score=85 fixture accepted; score=79 rejected; bare-title ICY skips MB | unit | `pytest tests/test_cover_art_mb.py::test_score_threshold_rejects_below_80_accepts_at_or_above_80 -x` | W0→Plan 01; GREEN→Plan 02 | ⬜ pending |
| ART-MB-05 | 02 | 2 | Release selection: Official+Album+earliest wins over Bootleg with same score | unit | `pytest tests/test_cover_art_mb.py::test_release_selection_ladder_picks_official_album_over_bootleg -x` | W0→Plan 01; GREEN→Plan 02 | ⬜ pending |
| ART-MB-06 | 02 | 2 | Latest-wins queue: 5 rapid ICY arrivals → at most 1 wasted + 1 final | unit (mocked clock + queue) | `pytest tests/test_cover_art_mb.py::test_latest_wins_queue_drops_superseded_jobs -x` | W0→Plan 01; GREEN→Plan 02 | ⬜ pending |
| ART-MB-07 | 03 | 3 | MB-only mode: iTunes urlopen MUST NOT be called | unit | `pytest tests/test_cover_art.py::test_mb_only_mode_does_not_call_itunes_urlopen -x` | W0→Plan 01; GREEN→Plan 03 | ⬜ pending |
| ART-MB-08 | 03 | 3 | iTunes-only mode: MB urlopen MUST NOT be called | unit | `pytest tests/test_cover_art.py::test_itunes_only_mode_does_not_call_mb -x` | W0→Plan 01; GREEN→Plan 03 | ⬜ pending |
| ART-MB-09 | 03 | 3 | Auto mode: iTunes miss → MB called → image shown via cover_art_ready signal | integration (qtbot + mocked urlopen) | `pytest tests/test_cover_art_routing.py::test_auto_falls_through_to_mb -x` | W0→Plan 01; GREEN→Plan 03 | ⬜ pending |
| ART-MB-10 | 04 | 4 | Settings export ZIP round-trips `cover_art_source` field; old ZIPs default to 'auto' | unit | `pytest tests/test_settings_export.py::test_export_payload_contains_cover_art_source tests/test_settings_export.py::test_import_insert_persists_cover_art_source tests/test_settings_export.py::test_import_replace_persists_cover_art_source tests/test_settings_export.py::test_import_insert_missing_cover_art_source_defaults_to_auto tests/test_settings_export.py::test_import_replace_missing_cover_art_source_defaults_to_auto -x` | GREEN→Plan 04 | ⬜ pending |
| ART-MB-11 | 01 | 1 | SQLite migration adds column with DEFAULT 'auto'; idempotent on re-run | unit | `pytest tests/test_repo.py::test_cover_art_source_migration_idempotent -x` | GREEN→Plan 01 | ⬜ pending |
| ART-MB-12 | 04 | 4 | EditStationDialog selector reads + writes `station.cover_art_source` | qtbot | `pytest tests/test_edit_station_dialog.py::test_cover_art_source_combo_save_passes_kwarg_to_update_station -x` | GREEN→Plan 04 | ⬜ pending |
| ART-MB-13 | 02 | 2 | MB tags → genre: highest-count tag wins; empty tags → genre="" | unit | `pytest tests/test_cover_art_mb.py::test_genre_from_tags_picks_highest_count -x` | W0→Plan 01; GREEN→Plan 02 | ⬜ pending |
| ART-MB-14 | 02 | 2 | HTTP 503 from MB → callback(None), no raise out of worker | unit | `pytest tests/test_cover_art_mb.py::test_mb_503_falls_through_to_callback_none -x` | W0→Plan 01; GREEN→Plan 02 | ⬜ pending |
| ART-MB-15 | 02 | 2 | Source-grep gate: literal `MusicStreamer/` AND `https://github.com/lightningjim/MusicStreamer` appear in cover_art_mb.py source | source-grep | `pytest tests/test_cover_art_mb.py::test_user_agent_string_literals_present -x` | W0→Plan 01; GREEN→Plan 02 | ⬜ pending |
| ART-MB-16 | 02 | 2 | Source-grep gate: gate actually references `time.monotonic` (not just a comment) | source-grep | `pytest tests/test_cover_art_mb.py::test_rate_gate_uses_monotonic -x` | W0→Plan 01; GREEN→Plan 02 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*ART-MB-15/16 are source-grep gates mirroring the memory `feedback_gstreamer_mock_blind_spot.md` lesson — protocol-required strings must be tested at the source level, not just behaviorally.*

*Plan + Wave columns populated 2026-05-13 by planner (Plan 73-01 through 73-04). Status flips to ✅ as each executor turns its tests GREEN.*

---

## Wave 0 Requirements (delivered by Plan 73-01)

- [ ] `tests/test_cover_art_mb.py` — covers ART-MB-01..06, 13, 14, 15, 16 (RED scaffolds in Plan 01; GREEN in Plan 02)
- [ ] `tests/test_cover_art_routing.py` — covers ART-MB-09 (RED scaffold in Plan 01; GREEN in Plan 03)
- [ ] `tests/fixtures/mb_recording_search_*.json` — 6 mocked MB responses (delivered in Plan 01)
- [ ] Extension of `tests/test_cover_art.py` for routing — covers ART-MB-07/08 (RED scaffolds added in Plan 03 inline with the router refactor)
- [ ] Extension of `tests/test_repo.py` for migration — covers ART-MB-11 (delivered + GREEN in Plan 01)
- [ ] Extension of `tests/test_settings_export.py` for round-trip — covers ART-MB-10 (delivered + GREEN in Plan 04)
- [ ] Extension of `tests/test_edit_station_dialog.py` for selector — covers ART-MB-12 (delivered + GREEN in Plan 04)
- [ ] Extension of `tests/test_now_playing_panel.py` for source-aware `_fetch_cover_art_async` (delivered + GREEN in Plan 04)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real MB request renders real cover for a real station | E2E sanity | Live network; cannot deterministically assert against MB content | UAT script: launch app, play a station with strong ICY signal (e.g. SomaFM Indie Pop Rocks with iTunes-friendly artist), verify cover appears; then set station to MB-only, replay, verify cover still appears (potentially different art) — Plan 73-05 UAT Scenario A |
| CAA image at chosen size renders cleanly in 160×160 cover slot | A1 (assumption) | Visual quality assessment is subjective | UAT script: with one station set to MB-only, observe the cover_label pixmap; note any visible pixelation; if pixelation occurs, planner picks the next-larger CAA variant — Plan 73-05 UAT Scenario B |
| Settings export ZIP from machine A imports cleanly on machine B with `cover_art_source` preserved | ART-MB-10 cross-machine | Requires two machines or two profiles | UAT script: export from active profile, import into a fresh profile, verify a station that had MB-only retains MB-only after import — Plan 73-05 UAT Scenario C |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (Plan 01 supplies Wave 0; Plans 02-04 supply GREEN-turn)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (verified across Plans 01-04)
- [x] Wave 0 covers all MISSING references (Plan 01 frontmatter lists every Wave 0 file)
- [x] No watch-mode flags
- [x] Feedback latency < 30s for wave gate; < 4s for task gate
- [ ] `nyquist_compliant: true` set in frontmatter once Plan 04 turns all 16 rows ✅ — set by Plan 04 executor on completion

**Approval:** pending (Plan 73-05 UAT closes this line)
