---
phase: 83
slug: at-start-of-playing-a-station-randomly-select-and-play-one-o
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-22
---

# Phase 83 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Sourced from `83-RESEARCH.md` §Validation Architecture (researcher-authored).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-qt (project standard) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (inline) |
| **Quick run command** | `uv run pytest tests/test_player.py tests/test_soma_import.py tests/test_repo.py -q` |
| **Full suite command** | `uv run pytest -q --tb=short` |
| **Estimated runtime** | ~1.5s (quick) · ~22s (full, ~1500+ tests) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_player.py tests/test_soma_import.py tests/test_repo.py -q`
- **After every plan wave:** Run `uv run pytest -q --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~22 seconds (full suite)

---

## Per-Task Verification Map

> Per-task `<automated>` commands are authored by the planner; this map fixes the phase-level decision → test mapping. Each row points to the canonical behavioral assertion that proves the decision is honored. Planner expands per-task rows during plan emission.

| Decision ID | Plan (expected) | Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|-----------------|----------|-----------|-------------------|-------------|--------|
| D-01 | 83-01 | `station_prerolls` table + `prerolls_fetched_at` column exist after migration; idempotent re-init | unit | `uv run pytest tests/test_repo.py -k 'station_prerolls or prerolls_fetched_at' -q` | ✅ | ⬜ pending |
| D-02 | 83-02 | `fetch_channels` returns `preroll_urls` per channel; `import_stations` inserts `station_prerolls` rows | unit | `uv run pytest tests/test_soma_import.py -k 'preroll' -q` | ✅ | ⬜ pending |
| D-03 | 83-03 | Background fetch scheduled when `prerolls_fetched_at IS NULL` and 0 prerolls in DB | behavioral | `uv run pytest tests/test_player.py::test_preroll_backfill_scheduled_when_unfetched -q` | ✅ | ⬜ pending |
| D-04 | 83-02 | `prerolls_fetched_at` set after fetch even when 0 prerolls returned | unit + behavioral | `uv run pytest tests/test_soma_import.py::test_import_sets_prerolls_fetched_at_for_empty_preroll -q` | ✅ | ⬜ pending |
| D-05 | 83-03 | preroll URI set on playbin3; about-to-finish handler connected; queue built but not yet played | behavioral | `uv run pytest tests/test_player.py::test_preroll_sets_uri_and_connects_handler -q` | ✅ | ⬜ pending |
| D-06 | 83-03 | `_streams_queue` unchanged by preroll path (no preroll URLs in queue) | behavioral | `uv run pytest tests/test_player.py::test_preroll_does_not_pollute_streams_queue -q` | ✅ | ⬜ pending |
| D-07 | 83-03 | `title_changed` NOT emitted while `_preroll_in_flight` (m4a TAG suppressed) | behavioral | `uv run pytest tests/test_player.py::test_title_tag_suppressed_during_preroll -q` | ✅ | ⬜ pending |
| D-09 | 83-03 | Preroll bus error → `_try_next_stream` invoked; queue advances to `_streams_queue[0]` | behavioral | `uv run pytest tests/test_player.py::test_preroll_bus_error_advances_to_stream -q` | ✅ | ⬜ pending |
| D-11 | 83-03 | Non-SomaFM station with synthetic preroll rows → preroll path NOT taken | behavioral | `uv run pytest tests/test_player.py::test_non_somafm_provider_bypasses_preroll -q` | ✅ | ⬜ pending |
| D-12 (window) | 83-03 | Throttle window NOT expired → preroll path NOT taken | behavioral | `uv run pytest tests/test_player.py::test_throttle_window_suppresses_preroll -q` | ✅ | ⬜ pending |
| D-12 (timestamp) | 83-03 | `_last_preroll_played_at` updated at preroll START (not handoff) | behavioral | `uv run pytest tests/test_player.py::test_throttle_timestamp_set_on_start -q` | ✅ | ⬜ pending |
| D-13 | 83-03 | Background fetch is non-blocking — play proceeds to stream without waiting | behavioral | `uv run pytest tests/test_player.py::test_backfill_non_blocking -q` | ✅ | ⬜ pending |
| D-14 | 83-03 | Source-grep drift-guard pins `"SomaFM"` literal AND `_last_preroll_played_at` in non-comment lines of `musicstreamer/player.py` | source-grep | `uv run pytest tests/test_player.py::test_phase_83_preroll_drift_guard -q` | ✅ | ⬜ pending |

---

## Wave 0 Requirements

- [x] `tests/test_player.py` — exists; phase appends 7 behavioral tests + 1 drift-guard
- [x] `tests/test_soma_import.py` — exists; phase appends preroll-capture tests (preroll_urls in returned dict, insert_preroll called per URL, set_prerolls_fetched_at called for both populated and empty preroll lists, per-channel rollback CASCADEs station_prerolls)
- [x] `tests/test_repo.py` — exists; phase appends migration + new-method tests (insert_preroll, list_prerolls ordering, set_prerolls_fetched_at, CASCADE on delete_station, list_stations carries prerolls_fetched_at and prerolls list)
- [x] Existing pytest-qt fixture infrastructure (conftest.py:13 `QT_QPA_PLATFORM=offscreen`; autouse `_stub_bus_bridge`) — covers all Player tests

*All test infrastructure exists. No Wave 0 setup needed.*

---

## Manual-Only Verifications

| Behavior | Decision | Why Manual | Test Instructions |
|----------|----------|------------|-------------------|
| Live SomaFM Beat Blender preroll plays then transitions gaplessly to deep-house stream | D-05 | Real-pipeline about-to-finish handoff cannot be reliably mocked; pipeline mocks pass any `pipeline.emit(...)` call (MEMORY: `feedback_gstreamer_mock_blind_spot.md`). | Linux Wayland live audio test — bind Beat Blender → click Play → listen for station-ID voiceover followed by deep-house track with no audible gap. |
| Seven Inch Soul (no prerolls) plays without delay | D-04 + D-11 | Confirms `prerolls_fetched_at` semantics and provider gate end-to-end. | Bind Seven Inch Soul → Play → confirms straight-to-stream (no preroll preamble). |
| Throttle (10 min): replay Beat Blender within window → NO preroll; replay after window → preroll again | D-12 | Confirms in-memory throttle timestamp + 10-min window. | Play Beat Blender → preroll plays → stop → immediately replay → confirm no preroll. Wait 10 minutes → replay → confirm preroll plays. |

Record manual UAT outcomes in `83-HUMAN-UAT.md` per Phase 82 precedent.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (none — all test files exist)
- [ ] No watch-mode flags
- [ ] Feedback latency < 22s (full suite)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
