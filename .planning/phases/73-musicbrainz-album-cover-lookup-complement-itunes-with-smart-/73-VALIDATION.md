---
phase: 73
slug: musicbrainz-album-cover-lookup-complement-itunes-with-smart
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-13
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

| Req ID (proposed) | Plan | Wave | Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|----------|-----------|-------------------|-------------|--------|
| ART-MB-01 | TBD | TBD | User-Agent header literal on MB API request matches `MusicStreamer/<version> (https://github.com/lightningjim/MusicStreamer)` | unit | `pytest tests/test_cover_art_mb.py::test_mb_request_carries_user_agent -x` | ❌ W0 | ⬜ pending |
| ART-MB-02 | TBD | TBD | User-Agent header literal on CAA image request | unit | `pytest tests/test_cover_art_mb.py::test_caa_request_carries_user_agent -x` | ❌ W0 | ⬜ pending |
| ART-MB-03 | TBD | TBD | 1 req/sec gate: 5 sequential MB calls span ≥ 4 seconds of monotonic clock | unit (mocked clock) | `pytest tests/test_cover_art_mb.py::test_mb_gate_serializes_with_1s_floor -x` | ❌ W0 | ⬜ pending |
| ART-MB-04 | TBD | TBD | Score=85 fixture accepted; score=79 rejected; bare-title ICY skips MB | unit | `pytest tests/test_cover_art_mb.py::test_score_threshold -x` | ❌ W0 | ⬜ pending |
| ART-MB-05 | TBD | TBD | Release selection: Official+Album+earliest wins over Bootleg with same score | unit | `pytest tests/test_cover_art_mb.py::test_release_selection_ladder -x` | ❌ W0 | ⬜ pending |
| ART-MB-06 | TBD | TBD | Latest-wins queue: 5 rapid ICY arrivals → at most 1 wasted + 1 final | unit (mocked clock + queue) | `pytest tests/test_cover_art_mb.py::test_latest_wins_queue -x` | ❌ W0 | ⬜ pending |
| ART-MB-07 | TBD | TBD | MB-only mode: iTunes urlopen MUST NOT be called | unit | `pytest tests/test_cover_art.py::test_mb_only_skips_itunes -x` | ❌ W0 | ⬜ pending |
| ART-MB-08 | TBD | TBD | iTunes-only mode: MB urlopen MUST NOT be called | unit | `pytest tests/test_cover_art.py::test_itunes_only_skips_mb -x` | ❌ W0 | ⬜ pending |
| ART-MB-09 | TBD | TBD | Auto mode: iTunes miss → MB called → image shown via cover_art_ready signal | integration (qtbot + mocked urlopen) | `pytest tests/test_cover_art_routing.py::test_auto_falls_through_to_mb -x` | ❌ W0 | ⬜ pending |
| ART-MB-10 | TBD | TBD | Settings export ZIP round-trips `cover_art_source` field; old ZIPs default to 'auto' | unit | `pytest tests/test_settings_export.py::test_cover_art_source_roundtrip -x` | ❌ W0 | ⬜ pending |
| ART-MB-11 | TBD | TBD | SQLite migration adds column with DEFAULT 'auto'; idempotent on re-run | unit | `pytest tests/test_repo.py::test_cover_art_source_migration_idempotent -x` | ❌ W0 | ⬜ pending |
| ART-MB-12 | TBD | TBD | EditStationDialog selector reads + writes `station.cover_art_source` | qtbot | `pytest tests/test_edit_station_dialog.py::test_cover_art_source_selector -x` | ❌ W0 | ⬜ pending |
| ART-MB-13 | TBD | TBD | MB tags → genre: highest-count tag wins; empty tags → genre="" | unit | `pytest tests/test_cover_art_mb.py::test_genre_from_tags -x` | ❌ W0 | ⬜ pending |
| ART-MB-14 | TBD | TBD | HTTP 503 from MB → callback(None), no raise out of worker | unit | `pytest tests/test_cover_art_mb.py::test_mb_503_falls_through -x` | ❌ W0 | ⬜ pending |
| ART-MB-15 | TBD | TBD | Source-grep gate: literal `MusicStreamer/` AND `https://github.com/lightningjim/MusicStreamer` appear in cover_art_mb.py source | source-grep | `pytest tests/test_cover_art_mb.py::test_user_agent_string_literals_present -x` | ❌ W0 | ⬜ pending |
| ART-MB-16 | TBD | TBD | Source-grep gate: gate actually references `time.monotonic` (not just a comment) | source-grep | `pytest tests/test_cover_art_mb.py::test_rate_gate_uses_monotonic -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*ART-MB-15/16 are source-grep gates mirroring the memory `feedback_gstreamer_mock_blind_spot.md` lesson — protocol-required strings must be tested at the source level, not just behaviorally.*

*Plan + Wave columns will be populated by the planner agent in step 8.*

---

## Wave 0 Requirements

- [ ] `tests/test_cover_art_mb.py` — covers ART-MB-01..06, 13, 14, 15, 16
- [ ] `tests/test_cover_art_routing.py` — covers ART-MB-09 (auto-mode fallthrough)
- [ ] `tests/fixtures/mb_recording_search_*.json` — mocked MB responses (at minimum: clean Official Album hit, Bootleg-only hit, score=79 reject, score=85 accept, no-tags response, 503 error body)
- [ ] Extension of `tests/test_cover_art.py` for routing — covers ART-MB-07/08
- [ ] Extension of `tests/test_repo.py` for migration — covers ART-MB-11
- [ ] Extension of `tests/test_settings_export.py` for round-trip — covers ART-MB-10
- [ ] Extension of `tests/test_edit_station_dialog.py` for selector — covers ART-MB-12
- [ ] Extension of `tests/test_now_playing_panel.py` for source-aware `_fetch_cover_art_async` — covers ART-MB-09 partial

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real MB request renders real cover for a real station | E2E sanity | Live network; cannot deterministically assert against MB content | UAT script: launch app, play a station with strong ICY signal (e.g. SomaFM Indie Pop Rocks with iTunes-friendly artist), verify cover appears; then set station to MB-only, replay, verify cover still appears (potentially different art) |
| CAA image at chosen size renders cleanly in 160×160 cover slot | A1 (assumption) | Visual quality assessment is subjective | UAT script: with one station set to MB-only, observe the cover_label pixmap; note any visible pixelation; if pixelation occurs, planner picks the next-larger CAA variant |
| Settings export ZIP from machine A imports cleanly on machine B with `cover_art_source` preserved | ART-MB-10 cross-machine | Requires two machines or two profiles | UAT script: export from active profile, import into a fresh profile, verify a station that had MB-only retains MB-only after import |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (filled by planner)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s for wave gate; < 4s for task gate
- [ ] `nyquist_compliant: true` set in frontmatter once planner has populated Plan/Wave columns and Wave 0 tests are scaffolded

**Approval:** pending
