---
phase: 98-add-to-stats-for-nerds-actual-encoding-and-bitrate-detected
verified: 2026-06-27T00:00:00Z
status: passed
score: 16/16 must-haves verified
has_blocking_gaps: false
human_verification:
  - test: "Open the app, play any MP3 or AAC stream, open Stats for Nerds. Check that Encoding and Bitrate rows populate with detected values and declared expected values."
    expected: "Encoding shows e.g. 'MP3  (exp: MP3)' or 'AAC  (exp: AAC)'; Bitrate shows e.g. '128 kbps  (exp: 128 kbps)'. Sample rate and Bit depth rows also fill in."
    why_human: "Requires a running GStreamer pipeline with a real network stream to exercise _on_gst_tag; not testable without a live backend."
  - test: "With a mismatched stream (e.g. stream declared AAC but actually MP3), open Stats for Nerds."
    expected: "Encoding row label text is amber/orange-colored (not the normal muted gray). The declared expected value is still appended in parentheses."
    why_human: "Color rendering is visual; cannot verify QPalette amber color is perceptibly different from muted gray through code inspection alone."
  - test: "Flip the OS/Qt theme between light and dark while a mismatched stream is playing."
    expected: "Amber label remains legible on both light and dark backgrounds (lighter amber on light background, brighter amber on dark background). No text illegibility on theme switch."
    why_human: "WCAG legibility of _AMBER_LIGHT (180,120,0) vs _AMBER_DARK (255,180,60) requires human eye — cannot be verified programmatically."
  - test: "Switch stations (bind_station reset). Verify the four format rows clear back to em-dash."
    expected: "All four rows show '—' after switching stations; no stale encoding/bitrate from the prior station persists."
    why_human: "Requires exercising the bind_station UI flow interactively; requires visual inspection."
---

# Phase 98: Stats-for-Nerds Actual Encoding & Bitrate Verification Report

**Phase Goal:** Surface the actually-playing audio encoding and bitrate (plus already-detected sample-rate/bit-depth) in the hidden-by-default Stats-for-Nerds panel, shown alongside the declared/expected values with an amber mismatch flag, so the user can validate they are playing what they expect.
**Verified:** 2026-06-27
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | D-06: detected codec/bitrate captured one-shot at preroll, emitted exactly once per stream | VERIFIED | `_codec_tag_armed_for_stream_id` guard in `__init__`; disarm-before-emit pattern at player.py:1202; preroll guard at :1186 covers codec block; armed at `_set_uri` (:1684) and Pattern 1b (:1394-1395) |
| 2  | Player exposes `audio_format_detected = Signal(int, str, int)` and FakePlayer mirrors it with identical arity | VERIFIED | player.py:397 `audio_format_detected = Signal(int, str, int)`; _fake_player.py:91 identical; `test_fake_player_signal_parity` 2/2 green |
| 3  | Raw GStreamer TAG_AUDIO_CODEC strings are normalised to Stream.codec vocabulary (MP3/AAC/FLAC/OPUS/OGG/'') | VERIFIED | `_normalise_audio_codec` at player.py:80-111; pure function, no Qt/GStreamer imports; truth-table in `test_normalise_audio_codec` 5/5 green |
| 4  | Bitrate tags (bps) converted to kbps with TAG_NOMINAL_BITRATE preferred over TAG_BITRATE | VERIFIED | player.py:1195-1198 `nb_bps // 1000` preferred; fallback to `b_bps // 1000`; `test_bitrate_bps_to_kbps_conversion` green |
| 5  | SomaFM preroll tags are suppressed (no codec emission while _preroll_in_flight) | VERIFIED | player.py:1186-1187 `if self._preroll_in_flight: return` precedes codec block at :1190; `test_codec_tag_suppressed_during_preroll` green |
| 6  | D-04: Stats-for-Nerds panel shows four detected format rows — Encoding, Bitrate, Sample rate, Bit depth | VERIFIED | now_playing_panel.py:3609-3623 — all four rows in `_build_stats_widget`; `test_four_format_labels_default_em_dash` green |
| 7  | D-01: Encoding and Bitrate rows show detected AND declared/expected together, always | VERIFIED | now_playing_panel.py:1286-1316 `update_detected_format` appends `"  (exp: {declared})"` when declared known; `test_encoding_row_shows_detected_and_expected` green |
| 8  | D-02: a detected-vs-declared mismatch renders the detected value amber via _StatLabel.set_mismatch; a match renders muted | VERIFIED | `_StatLabel._apply_muted_palette` at :235-249 picks `_AMBER_LIGHT`/`_AMBER_DARK` by `QPalette.Window.lightness()`; `test_encoding_mismatch_sets_amber` and `test_no_mismatch_flag_when_codec_matches` green |
| 9  | D-05: Sample rate and Bit depth are plain _MutedLabel detected-only rows with no mismatch flag | VERIFIED | now_playing_panel.py:3618,3622 both assigned `_MutedLabel` not `_StatLabel`; `test_sample_rate_label_is_muted_not_stat` and `test_bit_depth_label_is_muted_not_stat` green |
| 10 | D-07: unknown detected values render em-dash '—'; rows always present; no flag when both unknown | VERIFIED | now_playing_panel.py:1295 `enc_text = "—"`, :1311 `brate_text = "—"`; `mismatch_enc = False` when detected unknown (:1298); `test_em_dash_when_codec_unknown` and `test_no_mismatch_when_both_unknown` green |
| 11 | Bitrate mismatch tolerance of 5 kbps suppresses small drift; >5 kbps flags amber | VERIFIED | now_playing_panel.py:1283 `_BITRATE_TOLERANCE_KBPS = 5`; condition at :1308 `abs(...) > _BITRATE_TOLERANCE_KBPS`; `test_bitrate_mismatch_tolerance` green |
| 12 | Pitfall 8: the four new rows carry no per-row setVisible — they inherit set_stats_visible from the wrapper | VERIFIED | `_build_stats_widget` body (:3600-3669) has exactly one `setVisible` call (`wrapper.setVisible(False)` at :3668); `test_no_per_row_visible_in_build_stats` green |
| 13 | Player.audio_format_detected is connected to a MainWindow slot with QueuedConnection | VERIFIED | main_window.py:551-553 `self._player.audio_format_detected.connect(self._on_audio_format_detected, Qt.ConnectionType.QueuedConnection)` |
| 14 | _on_audio_format_detected delivers detected codec/bitrate to the panel via update_detected_format and never raises | VERIFIED | main_window.py:811-818 `try: if hasattr(...): update_detected_format(...); except Exception: _log.exception(...)` |
| 15 | _on_audio_format_detected does NOT persist detected codec/bitrate to the DB (D-03) | VERIFIED | main_window.py:797-818 — no `repo.update_stream` call inside the slot; confirmed by grep |
| 16 | _on_audio_caps_detected fans detected sample-rate/bit-depth to the panel via update_detected_caps (D-04 completes the format block) | VERIFIED | main_window.py:783-785 `if hasattr(self.now_playing, "update_detected_caps"): self.now_playing.update_detected_caps(stream_id, rate_hz, bit_depth)` after existing `_refresh_quality_badge` fan-out |

**Score:** 16/16 truths verified

---

### Decision Coverage (D-01..D-07 from CONTEXT.md)

| Decision | Description | Status | Evidence |
|----------|-------------|--------|----------|
| D-01 | Encoding and Bitrate show detected AND declared/expected together, always | SATISFIED | `update_detected_format` appends `(exp: X)` suffix; truth #7 above |
| D-02 | Mismatch flagged amber via detected value color; match uses muted color | SATISFIED | `_StatLabel.set_mismatch` + `_apply_muted_palette` override; truths #8, #11 |
| D-03 | Expected sourced from declared `Stream.codec`/`bitrate_kbps`; no new source of truth; detected not persisted | SATISFIED | `self._streams` lookup in `update_detected_format`; no `repo.update_stream` in slot; truths #7, #15 |
| D-04 | Four detected format rows: Encoding, Bitrate, Sample rate, Bit depth | SATISFIED | `_build_stats_widget` has all four rows; `update_detected_caps` fan-out; truths #6, #16 |
| D-05 | Sample rate and Bit depth are detected-only (no declared comparison); plain `_MutedLabel` | SATISFIED | `_sample_rate_label` and `_bit_depth_label` are `_MutedLabel` not `_StatLabel`; truth #9 |
| D-06 | One-shot snapshot at preroll — no continuous/live VBR updates | SATISFIED | `_codec_tag_armed_for_stream_id` guard disarms after first emission; truth #1 |
| D-07 | Unknown → em-dash; rows always present; no flag when both unknown | SATISFIED | Default "—" in all four labels; em-dash branch in `update_detected_format`; truth #10 |

All 7 user decisions honored.

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/player.py` | `audio_format_detected` signal, `_normalise_audio_codec`, one-shot tag block, guard arming | VERIFIED | Signal at :397; normaliser at :80-111; tag block at :1190-1203; arming at :1684 and :1394 |
| `tests/_fake_player.py` | `audio_format_detected Signal` parity | VERIFIED | Line 91: `audio_format_detected = Signal(int, str, int)` |
| `tests/test_player_codec_tag.py` | 5 Wave 0 unit tests for codec/bitrate detection | VERIFIED | 5 tests, all green: `test_normalise_audio_codec`, `test_bitrate_bps_to_kbps_conversion`, `test_codec_tag_emits_on_first_tag`, `test_codec_tag_one_shot_disarm`, `test_codec_tag_suppressed_during_preroll` |
| `musicstreamer/ui_qt/now_playing_panel.py` | `_StatLabel`, four format rows, `update_detected_format`, `update_detected_caps`, `bind_station` reset | VERIFIED | All present; `_StatLabel` at :204; rows at :3609-3623; methods at :1262, :1318; reset at :1032-1037 |
| `tests/test_now_playing_stats.py` | 12 Wave 0 panel rendering tests | VERIFIED | 12 tests, all green |
| `musicstreamer/ui_qt/main_window.py` | `audio_format_detected` QueuedConnection, `_on_audio_format_detected` slot, `update_detected_caps` fan-out | VERIFIED | Connection at :551-553; slot at :797-818; fan-out at :784-785 |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `player.py _on_gst_tag` | `audio_format_detected.emit` | one-shot guard + normalise + bps→kbps | WIRED | :1190-1203 confirmed |
| `tests/_fake_player.py` | signal parity test | `audio_format_detected = Signal(int, str, int)` | WIRED | :91; parity test green |
| `Player.audio_format_detected` (bus-loop thread) | `MainWindow._on_audio_format_detected` (main thread) | QueuedConnection | WIRED | main_window.py:551-553 |
| `MainWindow._on_audio_format_detected` | `now_playing.update_detected_format` | hasattr-guarded call | WIRED | :812-813 |
| `MainWindow._on_audio_caps_detected` | `now_playing.update_detected_caps` | hasattr-guarded fan-out after `_refresh_quality_badge` | WIRED | :784-785 |
| `now_playing_panel.update_detected_format` | `self._streams` (declared codec/bitrate_kbps) | `next((s for s in self._streams if s.id == stream_id), None)` | WIRED | :1279 |
| `_StatLabel.set_mismatch` | amber `QPalette.WindowText` | `_apply_muted_palette` override | WIRED | :235-249 |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `_on_gst_tag` | `raw_codec`, `nb_bps`, `b_bps` | GStreamer taglist via `taglist.get_string` / `taglist.get_uint` | Yes — real GStreamer tag bus | FLOWING (when pipeline running) |
| `update_detected_format` | `detected_codec`, `detected_bitrate_kbps` | `audio_format_detected` signal payload | Flows from `_on_gst_tag` via QueuedConnection | FLOWING |
| `update_detected_format` declared lookup | `declared_codec`, `declared_kbps` | `self._streams` (populated from `repo.list_streams`) | Real DB query upstream | FLOWING |
| `update_detected_caps` | `rate_hz`, `bit_depth` | `audio_caps_detected` signal + `_on_audio_caps_detected` fan-out | Pre-existing Phase 70 pipeline | FLOWING |

Note: Data flow through `_on_gst_tag` → `audio_format_detected` requires an active GStreamer pipeline with a real network stream. The one-shot guard correctly prevents any emission until armed at `_set_uri`/`_on_playbin_state_changed`. No static/hardcoded values in the data path.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Codec/bitrate detection unit tests | `.venv/bin/python -m pytest tests/test_player_codec_tag.py -x -q` | 5 passed, 1 warning | PASS |
| Panel rendering unit tests | `.venv/bin/python -m pytest tests/test_now_playing_stats.py -x -q` | 12 passed, 1 warning | PASS |
| FakePlayer signal parity | `.venv/bin/python -m pytest tests/test_fake_player_signal_parity.py -x -q` | 2 passed, 1 warning | PASS |
| Existing player tag/caps suites (regression) | `.venv/bin/python -m pytest tests/test_player_tag.py tests/test_player_caps.py -x -q` | 18 passed, 1 warning | PASS |
| MainWindow integration (known failure deselected) | `.venv/bin/python -m pytest tests/test_main_window_integration.py --deselect ...::test_hamburger_menu_actions -x -q` | 66 passed, 1 deselected, 63 warnings | PASS |
| Existing panel suite (regression) | `.venv/bin/python -m pytest tests/test_now_playing_panel.py -x -q` | 166 passed, 1 warning | PASS |

---

### Anti-Patterns Found

No `TBD`, `FIXME`, or `XXX` markers found in any phase-98 modified files. No placeholder returns, no empty implementations, no hardcoded empty data in the signal/rendering path.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | None found | — | — |

---

### Human Verification Required

#### 1. Real-playback Stats-for-Nerds population

**Test:** Play any MP3 or AAC stream. Open Stats for Nerds (from the menu or keyboard shortcut). Observe the Encoding, Bitrate, Sample rate, and Bit depth rows.
**Expected:** All four rows populate within a few seconds of stream start. Encoding shows detected codec and "(exp: DECLARED)" suffix. Bitrate shows detected kbps and expected kbps if declared. Sample rate and Bit depth show detected values without an expected suffix.
**Why human:** Requires a running GStreamer pipeline with a live network stream to exercise `_on_gst_tag` and `_on_audio_caps_detected`. Cannot verify without a running application.

#### 2. Amber mismatch visual legibility on light theme

**Test:** Using a stream whose declared encoding or bitrate does not match the actual stream, open Stats for Nerds on a light Qt theme.
**Expected:** The detected value in the mismatched row renders in amber/orange (`_AMBER_LIGHT` = RGB 180,120,0), clearly distinguishable from the normal muted gray label color. The "(exp: X)" suffix is readable.
**Why human:** WCAG contrast between amber and background requires human eye inspection. Code confirms the color value is set, but perceptual legibility is not machine-verifiable.

#### 3. Amber mismatch visual legibility on dark theme

**Test:** Flip to a dark Qt theme while a mismatched stream is playing and Stats for Nerds is open.
**Expected:** The amber label transitions to `_AMBER_DARK` (RGB 255,180,60 — brighter) and remains legible on the dark background. The `changeEvent` inherited from `_MutedLabel` triggers the re-paint automatically.
**Why human:** Light/dark theme flip behavior and color legibility require visual confirmation.

#### 4. Station-switch clears all four rows (bind_station reset)

**Test:** Play a stream with detected values visible in Stats for Nerds, then switch to a different station.
**Expected:** All four format rows (Encoding, Bitrate, Sample rate, Bit depth) immediately reset to "—" with no mismatch amber. They repopulate once the new stream's tags arrive.
**Why human:** Requires interactive UI flow (station switch) and live playback observation.

---

### Commits Verified

| Hash | Plan | Description |
|------|------|-------------|
| 43db21b1 | 98-01 | test: add audio_format_detected Signal to player.py (RED) |
| 552af516 | 98-01 | feat: add _normalise_audio_codec and FakePlayer audio_format_detected parity |
| f38840b3 | 98-01 | test: add failing codec/bitrate detection tests (RED) |
| 8edd365e | 98-01 | feat: one-shot codec/bitrate detection in _on_gst_tag + guard arming |
| 3a6e3c89 | 98-02 | feat: add _StatLabel amber subclass + four format rows in _build_stats_widget + bind_station reset |
| e80ee5ba | 98-02 | feat: update_detected_format + update_detected_caps panel methods + Wave 0 stats test file |
| 926bf6ac | 98-03 | feat: wire audio_format_detected QueuedConnection + slot + caps fan-out |

All 7 commits verified present in git log.

---

_Verified: 2026-06-27_
_Verifier: Claude (gsd-verifier)_
