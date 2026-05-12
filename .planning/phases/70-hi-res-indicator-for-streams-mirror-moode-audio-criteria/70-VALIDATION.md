---
phase: 70
slug: hi-res-indicator-for-streams-mirror-moode-audio-criteria
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-11
---

# Phase 70 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: see `70-RESEARCH.md` `## Validation Architecture`.

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

> Task IDs land at planning time. This table seeds the planner with the row shape;
> planner replaces `{N}-{plan}-{task}` placeholders with locked IDs.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 70-{plan}-{task} | TBD | 0 | HRES-01 | — | N/A | unit (RED stub) | `uv run --with pytest pytest tests/test_hi_res.py -x` | ❌ Wave 0 | ⬜ pending |
| 70-{plan}-{task} | TBD | 1 | HRES-01 (T-01) | — | `classify_tier` returns closed enum {"hires","lossless",""} | unit | `uv run --with pytest pytest tests/test_hi_res.py::test_classify_tier_truth_table -x` | ❌ Wave 0 | ⬜ pending |
| 70-{plan}-{task} | TBD | 1 | HRES-01 (T-01) | — | `bit_depth_from_format("S16LE")=16`, full GstAudioFormat coverage | unit | `uv run --with pytest pytest tests/test_hi_res.py::test_bit_depth_from_format -x` | ❌ Wave 0 | ⬜ pending |
| 70-{plan}-{task} | TBD | 1 | HRES-01 (T-01) | — | `best_tier_for_station` Hi-Res > Lossless > "" across streams | unit | `uv run --with pytest pytest tests/test_hi_res.py::test_best_tier_for_station -x` | ❌ Wave 0 | ⬜ pending |
| 70-{plan}-{task} | TBD | 1 | HRES-01 (T-02) | — | Repo round-trip preserves `sample_rate_hz` + `bit_depth` | unit | `uv run --with pytest pytest tests/test_repo.py -k "sample_rate_hz or bit_depth" -x` | ✅ extend | ⬜ pending |
| 70-{plan}-{task} | TBD | 1 | HRES-01 (T-02) | — | Idempotent ALTER TABLE: second `db_init` doesn't raise | unit | `uv run --with pytest pytest tests/test_repo.py::test_db_init_idempotent_for_sample_rate_hz -x` | ❌ Wave 0 | ⬜ pending |
| 70-{plan}-{task} | TBD | 1 | HRES-01 (T-03) | — | FLAC-96/24 sorts above FLAC-44/16 in `order_streams` | unit | `uv run --with pytest pytest tests/test_stream_ordering.py::test_hires_flac_outranks_cd_flac -x` | ✅ extend | ⬜ pending |
| 70-{plan}-{task} | TBD | 1 | HRES-01 (T-03 regression) | — | `test_gbs_flac_ordering` still passes | unit | `uv run --with pytest pytest tests/test_stream_ordering.py::test_gbs_flac_ordering -x` | ✅ | ⬜ pending |
| 70-{plan}-{task} | TBD | 2 | HRES-01 (T-06) | T-70-01 (closed-enum tier text) | Synthetic `audio/x-raw,rate=96000,format=S24LE` caps → `repo.update_stream(stream_id, sample_rate_hz=96000, bit_depth=24)` invoked | integration | `uv run --with pytest --with pytest-qt pytest tests/test_player_caps.py::test_caps_persists_rate_and_bit_depth -x` | ❌ Wave 0 | ⬜ pending |
| 70-{plan}-{task} | TBD | 2 | HRES-01 (threading) | T-70-02 (bus-thread → Qt isolation) | Caps handler emits queued Signal; main-thread slot receives | integration | `uv run --with pytest --with pytest-qt pytest tests/test_player_caps.py::test_caps_emitted_as_queued_signal -x` | ❌ Wave 0 | ⬜ pending |
| 70-{plan}-{task} | TBD | 3 | HRES-01 (T-05) | T-70-01 | `station_star_delegate.paint` paints "HI-RES" pill for a station with one FLAC-96/24 stream | integration | `uv run --with pytest --with pytest-qt pytest tests/test_station_star_delegate.py::test_paints_hires_pill_for_hires_station -x` | ❌ Wave 0 | ⬜ pending |
| 70-{plan}-{task} | TBD | 3 | HRES-01 (UI badge) | T-70-01 | Now-playing `_quality_badge` shows "HI-RES" when bound station has hi-res stream; hidden when none | integration | `uv run --with pytest --with pytest-qt pytest tests/test_now_playing_panel.py -k quality_badge -x` | ✅ extend | ⬜ pending |
| 70-{plan}-{task} | TBD | 3 | HRES-01 (UI picker) | — | Stream picker item text suffix `" — HI-RES"` when tier non-empty | unit | `uv run --with pytest --with pytest-qt pytest tests/test_now_playing_panel.py -k picker -x` | ✅ extend | ⬜ pending |
| 70-{plan}-{task} | TBD | 3 | HRES-01 (EditDialog) | — | EditStationDialog streams table shows non-editable "Quality" column with cached tier | integration | `uv run --with pytest --with pytest-qt pytest tests/test_edit_station_dialog.py -k quality -x` | ✅ extend | ⬜ pending |
| 70-{plan}-{task} | TBD | 4 | HRES-01 (proxy) | — | `set_quality_map({1: "hires"})` + `set_hi_res_only(True)` filters tree to station_id=1 | integration | `uv run --with pytest --with pytest-qt pytest tests/test_station_filter_proxy.py::test_hi_res_only_filter -x` | ✅ extend | ⬜ pending |
| 70-{plan}-{task} | TBD | 4 | HRES-01 (proxy Pitfall 7) | — | `set_quality_map` does NOT call `invalidate()` when `_hi_res_only=False` | integration | `uv run --with pytest --with pytest-qt pytest tests/test_station_filter_proxy.py::test_set_quality_map_no_invalidate_when_chip_off -x` | ✅ extend | ⬜ pending |
| 70-{plan}-{task} | TBD | 4 | HRES-01 (chip) | — | `_hi_res_chip` hidden until library has any "hires" entry; visible after | integration | `uv run --with pytest --with pytest-qt pytest tests/test_station_list_panel.py -k hi_res_chip -x` | ✅ extend | ⬜ pending |
| 70-{plan}-{task} | TBD | 5 | HRES-01 (T-04) | — | Settings-export ZIP round-trip preserves `sample_rate_hz` + `bit_depth`; pre-70 ZIP missing keys → 0 | unit | `uv run --with pytest pytest tests/test_settings_export.py -k "sample_rate_hz or bit_depth" -x` | ✅ extend | ⬜ pending |
| 70-{plan}-{task} | TBD | 5 | HRES-01 (T-04) | — | `_station_to_dict` emits `sample_rate_hz` + `bit_depth` keys | unit | `uv run --with pytest pytest tests/test_settings_export.py::test_station_to_dict_emits_quality_keys -x` | ✅ extend | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_hi_res.py` — NEW. Covers HRES-01 T-01 (`classify_tier`, `bit_depth_from_format`, `best_tier_for_station`). RED stubs landed in Wave 0.
- [ ] `tests/test_player_caps.py` — NEW. Covers HRES-01 T-06 (mocked notify::caps signal → repo.update_stream; queued-signal contract). RED stubs.
- [ ] `tests/test_station_star_delegate.py` — NEW (or extension of `tests/test_station_list_panel.py`). Covers HRES-01 T-05 (best-tier-across-streams paint test). Confirm file existence in Wave 0; if absent, create.
- [ ] Extend `tests/test_repo.py` — `sample_rate_hz` + `bit_depth` round-trip + idempotent ALTER assertion.
- [ ] Extend `tests/test_settings_export.py` — `sample_rate_hz` / `bit_depth` round-trip + missing-key forward-compat.
- [ ] Extend `tests/test_stream_ordering.py` — FLAC-96/24-beats-FLAC-44/16 case (T-03). Existing `test_gbs_flac_ordering` regression must still pass.
- [ ] Extend `tests/test_station_filter_proxy.py` — hi-res-only filter + Pitfall 7 invalidate-guard cases. (File exists with Phase 68 live_only coverage.)
- [ ] Extend `tests/test_now_playing_panel.py` — `_quality_badge` visibility + stream picker tier suffix.
- [ ] Extend `tests/test_station_list_panel.py` — `_hi_res_chip` visibility gate.
- [ ] Extend `tests/test_edit_station_dialog.py` — read-only "Quality" column presence + value mapping.

*All Wave 0 RED stubs fail as ImportError/AttributeError until Wave 1+ ship; this is the project's standard RED-first contract (Phase 62-00 idiom).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real GBS.FM FLAC stream lights up "LOSSLESS" then upgrades to "HI-RES" if rate > 48 kHz | HRES-01 | Network + GStreamer + real caps — no synthetic substitute | 1. Clear cache (set `sample_rate_hz=0, bit_depth=0` on a GBS FLAC stream). 2. Play it. 3. Verify badge appears as "LOSSLESS" within 5 s of audio start. 4. If GBS serves >48 kHz at any point, badge upgrades to "HI-RES" without restart. |
| Cross-OS (Win11 VM) — caps detection works through the conda-forge GStreamer 1.28+ bundle | HRES-01 | Win11 VM only; matches Phase 43.1 cross-OS regression class | After this phase ships, Win11 UAT: play a FLAC stream, confirm badge state matches Linux. |
| Theme switch (Phase 66) keeps badge legible | HRES-01 | Visual; theme-switch live-update | Switch through System / Vaporwave / Overrun / Dark / Light themes with a Hi-Res station bound; confirm badge contrast remains readable in each. |
| Custom theme (Phase 66 user-editable) doesn't break badge | HRES-01 | Visual under user-customized palette | Build a Custom palette with extreme highlight/highlighted-text contrast inversion; confirm badge text remains legible. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90 s (full suite)
- [ ] `nyquist_compliant: true` set in frontmatter (planner sets after PLAN.md lands)

**Approval:** pending
