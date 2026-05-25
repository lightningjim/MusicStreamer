---
phase: 70
slug: hi-res-indicator-for-streams-mirror-moode-audio-criteria
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-11
plans_landed: 2026-05-12
---

# Phase 70 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: see `70-RESEARCH.md` `## Validation Architecture`.
> Task IDs locked by planner 2026-05-12 (plans 70-00..70-11 landed).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-qt (existing) + `unittest.mock` for PyGObject Gst messages |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (existing) |
| **Quick run command** | `uv run --with pytest --with pytest-qt pytest tests/test_hi_res.py tests/test_stream_ordering.py -x` |
| **Full suite command** | `uv run --with pytest --with pytest-qt pytest -x` |
| **Estimated runtime** | quick ≈ 6 s; full ≈ 75 s (current 399 tests baseline + Phase 70 additions) |

---

## Sampling Rate

- **After every task commit:** Run quick command (`uv run --with pytest --with pytest-qt pytest tests/test_hi_res.py tests/test_repo.py tests/test_stream_ordering.py -x`).
- **After every plan wave:** Run wave command (`uv run --with pytest --with pytest-qt pytest tests/test_hi_res.py tests/test_repo.py tests/test_stream_ordering.py tests/test_settings_export.py tests/test_station_filter_proxy.py tests/test_station_star_delegate.py tests/test_player_caps.py tests/test_now_playing_panel.py tests/test_station_list_panel.py tests/test_edit_station_dialog.py -x`).
- **Before `/gsd-verify-work`:** Full suite must be green (`uv run --with pytest --with pytest-qt pytest -x`).
- **Max feedback latency:** quick ≤ 10 s; wave ≤ 30 s; full ≤ 90 s.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 70-00-T1 | 70-00 | 0 | HRES-01 | — | RED stubs for tests/test_hi_res.py + empty hi_res.py skeleton | unit (RED stub) | `uv run --with pytest pytest tests/test_hi_res.py -x --co -q` (collection success; execution RED) | ❌ Wave 0 | ⬜ pending |
| 70-00-T2 | 70-00 | 0 | HRES-01 | T-70-W0-02 | RED stubs for tests/test_player_caps.py (notify::caps → queued Signal → repo.update_stream) | integration (RED stub) | `uv run --with pytest --with pytest-qt pytest tests/test_player_caps.py -x --co -q` | ❌ Wave 0 | ⬜ pending |
| 70-00-T3 | 70-00 | 0 | HRES-01 | — | RED stubs appended to 8 existing test modules (repo + stream_ordering + settings_export + station_filter_proxy + station_star_delegate + now_playing_panel + station_list_panel + edit_station_dialog) | unit + integration | `uv run --with pytest --with pytest-qt pytest tests/test_repo.py tests/test_stream_ordering.py tests/test_settings_export.py tests/test_station_filter_proxy.py tests/test_station_star_delegate.py tests/test_now_playing_panel.py tests/test_station_list_panel.py tests/test_edit_station_dialog.py --co -q` | ✅ extend | ⬜ pending |
| 70-01-T1 | 70-01 | 1 | HRES-01 (T-01) | T-70-01, T-70-02, T-70-03 | classify_tier returns closed enum {"hires","lossless",""} per D-01..D-04; bit_depth_from_format mapping DS-02; best_tier_for_station Hi-Res > Lossless > "" | unit | `uv run --with pytest pytest tests/test_hi_res.py -x` | ✅ extend | ⬜ pending |
| 70-02-T1 | 70-02 | 1 | HRES-01 (T-02 + M-01) | T-70-04, T-70-05, T-70-06 | StationStream + schema migration + list_streams hydration (parameterized SQL); idempotent ALTER absorbs OperationalError | unit | `uv run --with pytest pytest tests/test_repo.py -k "sample_rate_hz or bit_depth or db_init_idempotent" -x` | ✅ extend | ⬜ pending |
| 70-02-T2 | 70-02 | 1 | HRES-01 (T-02) | T-70-04 | insert_stream + update_stream kwargs preserve positional callers (Assumption A6); parameterized SQL | unit | `uv run --with pytest pytest tests/test_repo.py -x` | ✅ extend | ⬜ pending |
| 70-03-T1 | 70-03 | 1 | HRES-01 (T-03 + S-01 + S-02) | T-70-07, T-70-08 | order_streams sort key rate/depth tiebreak; cross-codec hi-res promotion forbidden; GBS regression intact | unit | `uv run --with pytest pytest tests/test_stream_ordering.py -x` | ✅ extend | ⬜ pending |
| 70-04-T1 | 70-04 | 2 | HRES-01 (T-06 threading) | T-70-09, T-70-10 | audio_caps_detected Signal declared with (int,int,int) signature; instance state initialized | integration | `uv run --with pytest --with pytest-qt pytest tests/test_player_caps.py::test_caps_emitted_as_queued_signal -x` | ✅ extend | ⬜ pending |
| 70-04-T2 | 70-04 | 2 | HRES-01 (T-06) | T-70-09, T-70-10, T-70-11, T-70-12 | Pattern 1b dual-path caps detection (main-thread sync-read + streaming-thread notify::caps async); Pitfall 2 streaming-thread emit-only invariant; Pitfall 6 one-shot disarm | integration | `uv run --with pytest --with pytest-qt pytest tests/test_player_caps.py -x` | ✅ extend | ⬜ pending |
| 70-05-T1 | 70-05 | 2 | HRES-01 (DB-write-first invariant) | T-70-13, T-70-14, T-70-15, T-70-16 | MainWindow._on_audio_caps_detected: DB write FIRST then quality_map rebuild then UI fan-out; idempotency cache prevents duplicate writes; stream-deleted-between-emit-and-slot graceful no-op | integration | `uv run --with pytest --with pytest-qt pytest tests/test_main_window.py -k "caps or quality_map or audio_caps" -x` | ✅ extend | ⬜ pending |
| 70-06-T1 | 70-06 | 3 | HRES-01 (UI badge construction) | T-70-17, T-70-18, T-70-19 | _quality_badge QLabel in icy_row LEFT of _live_badge; Qt.PlainText lock; Phase 68 LIVE QSS verbatim; T-40-04 grep baseline bumped 4 → 5 | integration | `uv run --with pytest --with pytest-qt pytest tests/test_now_playing_panel.py -k "quality_badge and (visible or hidden or text)" -x` | ✅ extend | ⬜ pending |
| 70-06-T2 | 70-06 | 3 | HRES-01 (UI badge slot + picker) | T-70-17, T-70-18, T-70-19 | _refresh_quality_badge slot-never-raise idiom; tooltip per UI-SPEC Copywriting Contract; picker tier-suffix em-dash separator | integration | `uv run --with pytest --with pytest-qt pytest tests/test_now_playing_panel.py -k "quality_badge or picker_label" -x` | ✅ extend | ⬜ pending |
| 70-07-T1 | 70-07 | 3 | HRES-01 (T-05) | T-70-20, T-70-21, T-70-22 | station_star_delegate paint renders tier pill BEFORE star; selection-state color swap (UI-SPEC OD-3); QPainter primitives only (no QSS); provider rows safe; sizeHint grows | integration | `uv run --with pytest --with pytest-qt pytest tests/test_station_star_delegate.py -x` | ✅ extend | ⬜ pending |
| 70-08-T1 | 70-08 | 3 | HRES-01 (EditDialog column header + width) | T-70-23, T-70-24 | _COL_AUDIO_QUALITY = 5 column with header "Audio quality" + Fixed 90px width + UI-SPEC OD-8 tooltip | integration | `uv run --with pytest --with pytest-qt pytest tests/test_edit_station_dialog.py -k "audio_quality_column" -x` | ✅ extend | ⬜ pending |
| 70-08-T2 | 70-08 | 3 | HRES-01 (EditDialog per-row cell) | T-70-23, T-70-24 | Per-row Audio quality cell renders TIER_LABEL_PROSE; read-only via setFlags(~ItemIsEditable) | integration | `uv run --with pytest --with pytest-qt pytest tests/test_edit_station_dialog.py -k "audio_quality" -x` | ✅ extend | ⬜ pending |
| 70-09-T1 | 70-09 | 4 | HRES-01 (proxy + Pitfall 7) | T-70-25, T-70-26 | StationFilterProxyModel.set_quality_map + set_hi_res_only + filterAcceptsRow hi-res branch; Pitfall 7 invalidate-guard (no invalidate when chip off) | integration | `uv run --with pytest --with pytest-qt pytest tests/test_station_filter_proxy.py -k "hi_res or quality_map" -x` | ✅ extend | ⬜ pending |
| 70-09-T2 | 70-09 | 4 | HRES-01 (chip + visibility gate) | T-70-26, T-70-27 | _hi_res_chip QPushButton parallel to _live_chip; F-02 visibility gate; bound-method toggle slot (QA-05); update_quality_map + set_hi_res_chip_visible public methods | integration | `uv run --with pytest --with pytest-qt pytest tests/test_station_list_panel.py -k "hi_res_chip" -x` | ✅ extend | ⬜ pending |
| 70-10-T1 | 70-10 | 5 | HRES-01 (T-04 + DS-04) | T-70-28, T-70-29, T-70-30 | ZIP round-trip preserves sample_rate_hz + bit_depth; forward-compat missing-key idiom int(x or 0); _station_to_dict emits both keys | unit | `uv run --with pytest pytest tests/test_settings_export.py -k "sample_rate_hz or bit_depth or quality_keys" -x` | ✅ extend | ⬜ pending |
| 70-11-T1 | 70-11 | 5 | HRES-01 (REQUIREMENTS) | T-70-31, T-70-32 | HRES-01 row in REQUIREMENTS.md Features + Traceability + coverage footer + Last-updated stamp | doc | `grep -c "HRES-01" .planning/REQUIREMENTS.md` returns ≥ 3 | ✅ extend | ⬜ pending |
| 70-11-T2 | 70-11 | 5 | HRES-01 (ROADMAP) | T-70-31, T-70-32 | ROADMAP.md Phase 70 entry Goal + Requirements + Plans count + Plans checklist updated from placeholders | doc | `grep -A 16 "### Phase 70:" .planning/ROADMAP.md \| grep -cE "TBD\|To be planned"` returns 0 | ✅ extend | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_hi_res.py` — NEW. Covers HRES-01 T-01 (`classify_tier`, `bit_depth_from_format`, `best_tier_for_station`). RED stubs land in Plan 70-00 Task 1.
- [x] `tests/test_player_caps.py` — NEW. Covers HRES-01 T-06 (mocked notify::caps signal → repo.update_stream; queued-signal contract). RED stubs land in Plan 70-00 Task 2.
- [x] `tests/test_station_star_delegate.py` exists (Phase 54 baseline); Plan 70-00 Task 3 extends with Phase 70 paint + sizeHint tests.
- [x] Extend `tests/test_repo.py` — `sample_rate_hz` + `bit_depth` round-trip + idempotent ALTER assertion. Plan 70-00 Task 3.
- [x] Extend `tests/test_settings_export.py` — `sample_rate_hz` / `bit_depth` round-trip + missing-key forward-compat. Plan 70-00 Task 3.
- [x] Extend `tests/test_stream_ordering.py` — FLAC-96/24-beats-FLAC-44/16 case (T-03). Plan 70-00 Task 3.
- [x] Extend `tests/test_station_filter_proxy.py` — hi-res-only filter + Pitfall 7 invalidate-guard cases. Plan 70-00 Task 3.
- [x] Extend `tests/test_now_playing_panel.py` — `_quality_badge` visibility + stream picker tier suffix. Plan 70-00 Task 3.
- [x] Extend `tests/test_station_list_panel.py` — `_hi_res_chip` visibility gate. Plan 70-00 Task 3.
- [x] Extend `tests/test_edit_station_dialog.py` — read-only "Audio quality" column presence + value mapping. Plan 70-00 Task 3.

*All Wave 0 RED stubs fail as ImportError/AttributeError until Wave 1+ ship; this is the project's standard RED-first contract (Phase 62-00 idiom).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real GBS.FM FLAC stream lights up "LOSSLESS" then upgrades to "HI-RES" if rate > 48 kHz | HRES-01 | Network + GStreamer + real caps — no synthetic substitute | 1. Clear cache (set `sample_rate_hz=0, bit_depth=0` on a GBS FLAC stream). 2. Play it. 3. Verify badge appears as "LOSSLESS" within 5 s of audio start. 4. If GBS serves >48 kHz at any point, badge upgrades to "HI-RES" without restart. |
| Cross-OS (Win11 VM) — caps detection works through the conda-forge GStreamer 1.28+ bundle | HRES-01 | Win11 VM only; matches Phase 43.1 cross-OS regression class | After this phase ships, Win11 UAT: play a FLAC stream, confirm badge state matches Linux. |
| Theme switch (Phase 66) keeps badge legible | HRES-01 | Visual; theme-switch live-update | Switch through System / Vaporwave / Overrun / Dark / Light themes with a Hi-Res station bound; confirm badge contrast remains readable in each. |
| Custom theme (Phase 66 user-editable) doesn't break badge | HRES-01 | Visual under user-customized palette | Build a Custom palette with extreme highlight/highlighted-text contrast inversion; confirm badge text remains legible. |
| Tree-row pill selection-state color swap (UI-SPEC OD-3) | HRES-01 | Visual under row-selection state | Select a Hi-Res station row; confirm pill remains visible (color-swap to palette(HighlightedText) fill). |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies — DONE 2026-05-12
- [x] Sampling continuity: no 3 consecutive tasks without automated verify — DONE
- [x] Wave 0 covers all MISSING references — DONE
- [x] No watch-mode flags — DONE
- [x] Feedback latency < 90 s (full suite) — DONE
- [x] `nyquist_compliant: true` set in frontmatter — DONE 2026-05-12

**Approval:** planner-locked 2026-05-12
