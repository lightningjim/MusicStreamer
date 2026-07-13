---
phase: 98
slug: add-to-stats-for-nerds-actual-encoding-and-bitrate-detected
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-24
---

# Phase 98 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from 98-RESEARCH.md §Validation Architecture (four testable seams, no live GStreamer stream required).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (project standard) |
| **Config file** | none — inline pytest; run via `.venv/bin/python` (system python3 lacks PySide6.QtWidgets) |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_player_codec_tag.py tests/test_now_playing_stats.py tests/test_fake_player_signal_parity.py -x -q` |
| **Full suite command** | `.venv/bin/python -m pytest tests/ -x -q` (full suite >600s — scope to relevant tests during execution) |
| **Estimated runtime** | ~10–20s scoped; >600s full |

---

## Sampling Rate

- **After every task commit:** Run quick command (codec-tag + stats + fake-player parity).
- **After every plan wave:** `.venv/bin/python -m pytest tests/test_player_codec_tag.py tests/test_now_playing_stats.py tests/test_fake_player_signal_parity.py tests/test_now_playing_panel.py tests/test_player_tag.py tests/test_player_caps.py -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green.
- **Max feedback latency:** ~20 seconds (scoped runs).

---

## Per-Task Verification Map

> Task IDs are assigned during planning; the capability→test mapping below is authoritative and each
> test must land on a task. The planner MUST cover every row.

| Capability (D-NN) | Wave | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|-------------------|------|-----------------|-----------|-------------------|-------------|--------|
| Codec normalisation truth-table | 1 | N/A | unit | `pytest tests/test_player_codec_tag.py::test_normalise_audio_codec` | ❌ W0 | ⬜ pending |
| Bitrate bps→kbps (nominal preferred) | 1 | N/A | unit | `pytest tests/test_player_codec_tag.py::test_bitrate_bps_to_kbps_conversion` | ❌ W0 | ⬜ pending |
| D-06 one-shot tag capture emits signal | 1 | N/A | unit | `pytest tests/test_player_codec_tag.py::test_codec_tag_emits_on_first_tag` | ❌ W0 | ⬜ pending |
| D-06 one-shot guard disarm (no double emit) | 1 | N/A | unit | `pytest tests/test_player_codec_tag.py::test_codec_tag_one_shot_disarm` | ❌ W0 | ⬜ pending |
| Preroll guard suppresses codec tag emit | 1 | N/A | unit | `pytest tests/test_player_codec_tag.py::test_codec_tag_suppressed_during_preroll` | ❌ W0 | ⬜ pending |
| FakePlayer signal parity (D-16 drift guard) | 1 | N/A | drift-guard | `pytest tests/test_fake_player_signal_parity.py` | ❌ W0 | ⬜ pending |
| D-01 detected + expected both in label | 1 | N/A | unit | `pytest tests/test_now_playing_stats.py::test_encoding_row_shows_detected_and_expected` | ❌ W0 | ⬜ pending |
| D-02 amber on codec mismatch | 1 | N/A | unit | `pytest tests/test_now_playing_stats.py::test_encoding_mismatch_sets_amber` | ❌ W0 | ⬜ pending |
| D-02 no flag on codec match | 1 | N/A | unit | `pytest tests/test_now_playing_stats.py::test_no_mismatch_flag_when_codec_matches` | ❌ W0 | ⬜ pending |
| D-02 bitrate tolerance (≤5 kbps no flag) | 1 | N/A | unit | `pytest tests/test_now_playing_stats.py::test_bitrate_mismatch_tolerance` | ❌ W0 | ⬜ pending |
| D-05 sample-rate row is plain muted (no flag) | 1 | N/A | source-grep | `pytest tests/test_now_playing_stats.py::test_sample_rate_label_is_muted_not_stat` | ❌ W0 | ⬜ pending |
| D-07 em-dash when codec unknown | 1 | N/A | unit | `pytest tests/test_now_playing_stats.py::test_em_dash_when_codec_unknown` | ❌ W0 | ⬜ pending |
| D-07 no mismatch when both unknown | 1 | N/A | unit | `pytest tests/test_now_playing_stats.py::test_no_mismatch_when_both_unknown` | ❌ W0 | ⬜ pending |
| Pitfall 8 no per-row visibility | 1 | N/A | source-grep | `pytest tests/test_now_playing_stats.py::test_no_per_row_visible_in_build_stats` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_player_codec_tag.py` — new file; Seam 2 (tag extraction) + Seam 3 (one-shot guard) + normalisation + preroll suppression
- [ ] `tests/test_now_playing_stats.py` — new file; Seam 4 (panel rendering: D-01, D-02, D-05, D-07, Pitfall 8, tolerance)
- [ ] `tests/_fake_player.py` — add `audio_format_detected = Signal(int, str, int)` (D-16 parity; blocks `test_fake_player_signal_parity.py`)

*Existing `test_player_tag.py`, `test_player_caps.py`, `test_now_playing_panel.py` need no changes — they test unchanged paths.*

---

## Manual-Only Verifications

| Behavior | Why Manual | Test Instructions |
|----------|------------|-------------------|
| Amber mismatch color is readable in light AND dark themes (WCAG) | Visual/perceptual; theme-flip rendering | With Stats-for-Nerds visible, play a station whose declared codec differs from actual; flip theme; confirm amber detected value stays legible in both. |
| Real GStreamer tag arrival timing at preroll | Requires a live network audio stream | Play an MP3 and an AAC station; confirm Encoding/Bitrate rows populate within preroll with correct detected values; confirm a known-mismatched station shows amber. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (3 new/updated test files)
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
