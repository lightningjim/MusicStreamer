---
phase: 98-add-to-stats-for-nerds-actual-encoding-and-bitrate-detected
plan: "01"
subsystem: player
tags: [gstreamer, signal, tdd, codec-detection, bitrate, one-shot-guard]
dependency_graph:
  requires: []
  provides:
    - audio_format_detected Signal in Player + FakePlayer parity
    - _normalise_audio_codec pure function
    - _codec_tag_armed_for_stream_id one-shot guard
    - Wave 0 codec-tag detection tests
  affects:
    - musicstreamer/player.py (_on_gst_tag, __init__, _set_uri, _on_playbin_state_changed)
    - tests/_fake_player.py (Signal parity)
    - tests/test_player_codec_tag.py (new Wave 0 test file)
tech_stack:
  added: []
  patterns:
    - one-shot guard (disarm-before-emit, Pitfall 6) — mirrors _caps_armed_for_stream_id
    - TDD RED/GREEN for both tasks
    - arg-routing side_effect mock for GStreamer taglist in tests
key_files:
  created:
    - tests/test_player_codec_tag.py
  modified:
    - musicstreamer/player.py
    - tests/_fake_player.py
decisions:
  - "D-06: one-shot guard arms at _set_uri and _on_playbin_state_changed Pattern 1b (NOT inside _arm_caps_watch_for_current_stream — Open Question 1)"
  - "_normalise_audio_codec: case-insensitive substring checks in fixed order (layer3>layer2/mp2>aac>flac>opus_exact>vorbis) ensures MPEG-4 AAC matches AAC and MP2 maps to MP3 per assumption A5"
  - "Preroll guard (_preroll_in_flight) moved before codec block — covers both tag paths in one guard"
metrics:
  duration: "~3 min 23s"
  completed: "2026-06-27"
  tasks_completed: 2
  files_changed: 3
---

# Phase 98 Plan 01: Add audio_format_detected Signal + One-Shot Codec/Bitrate Detection Summary

One-liner: GStreamer TAG_AUDIO_CODEC/bitrate one-shot detection emitting `audio_format_detected(int, str, int)` via refactored `_on_gst_tag`, with closed-vocabulary normalization and FakePlayer parity.

## What Was Built

### Task 1 (TDD: RED+GREEN)
Added the producer-side signal contract for Phase 98 codec/bitrate detection:

**`musicstreamer/player.py`:**
- `audio_format_detected = Signal(int, str, int)` — new class-level signal (stream_id, codec_norm, bitrate_kbps) added immediately after `audio_caps_detected`
- `_normalise_audio_codec(raw: str | None) -> str` — module-level pure function (no Qt/GStreamer imports) mapping GStreamer TAG_AUDIO_CODEC strings to the D-03 vocabulary: MP3/AAC/FLAC/OPUS/OGG/''. Case-insensitive substring checks in fixed order (layer3 → layer2/mp2 → aac → flac → exact-opus → vorbis)

**`tests/_fake_player.py`:**
- `audio_format_detected = Signal(int, str, int)` parity line added immediately after `audio_caps_detected`, ensuring `test_fake_player_signal_parity` stays green

### Task 2 (TDD: RED+GREEN)
Created test file and implemented one-shot detection:

**`tests/test_player_codec_tag.py`** (new):
- Module-local `make_player` fixture (independent copy per plan instruction)
- `_fake_codec_tag_msg` helper using arg-routing `side_effect` (routes TAG_AUDIO_CODEC vs TAG_TITLE via `"audio-codec" in str(tag)`, TAG_NOMINAL_BITRATE vs TAG_BITRATE via `"nominal" in str(tag)`)
- 5 tests: `test_normalise_audio_codec` (truth-table), `test_bitrate_bps_to_kbps_conversion`, `test_codec_tag_emits_on_first_tag`, `test_codec_tag_one_shot_disarm`, `test_codec_tag_suppressed_during_preroll`

**`musicstreamer/player.py`** changes:
- `__init__`: `self._codec_tag_armed_for_stream_id: int = 0` added after `_caps_armed_for_stream_id`
- `_on_gst_tag` refactored (Critical Sequencing Note):
  - Renamed `found` → `found_title`
  - Moved `_preroll_in_flight` guard BEFORE the codec block and BEFORE `if not found_title: return` so it covers both paths
  - New codec/bitrate block: reads TAG_AUDIO_CODEC, TAG_NOMINAL_BITRATE, TAG_BITRATE; prefers nominal (`nb_bps // 1000`), falls back to bitrate; disarms BEFORE emit (Pitfall 6)
- `_set_uri`: `self._codec_tag_armed_for_stream_id = self._current_stream.id if self._current_stream else 0` armed after `_arm_caps_watch_for_current_stream()`
- `_on_playbin_state_changed` Pattern 1b: `self._codec_tag_armed_for_stream_id = self._current_stream.id` armed (with `if self._current_stream:` guard) after `_arm_caps_watch_for_current_stream()`

## Verification Results

```
.venv/bin/python -m pytest tests/test_player_codec_tag.py tests/test_fake_player_signal_parity.py tests/test_player_tag.py tests/test_player_caps.py -x -q
25 passed, 1 warning in 1.05s
```

All 5 acceptance tests pass. All existing tag and caps suites unaffected.

## Commits

| Hash | Type | Description |
|------|------|-------------|
| 43db21b1 | test | Add audio_format_detected Signal to player.py (RED) |
| 552af516 | feat | Add _normalise_audio_codec and FakePlayer parity (GREEN Task 1) |
| f38840b3 | test | Add failing codec/bitrate detection tests (RED Task 2) |
| 8edd365e | feat | One-shot codec/bitrate detection in _on_gst_tag + guard arming (GREEN Task 2) |

## Deviations from Plan

None — plan executed exactly as written.

## Threat Model Compliance

- **T-98-01 (Tampering):** `_normalise_audio_codec` returns only from a closed vocabulary (MP3/AAC/FLAC/OPUS/OGG/''); any unrecognised remote TAG_AUDIO_CODEC string returns '' — no hostile string propagates to the emitted signal
- **T-98-02 (DoS):** `_codec_tag_armed_for_stream_id` one-shot guard disarms before emit; repeated tag bus messages yield at most one emission per stream
- **T-98-03 (Info disclosure):** Accepted — read-only diagnostic metadata, no persistence
- **T-98-SC:** No package installs in this plan

## Known Stubs

None — `audio_format_detected` signal is fully wired. Panel display and declared-vs-detected comparison are deferred to Plans 02 and 03 by design (this plan is the producer half only).

## Self-Check: PASSED

All 3 source files exist. All 4 task commits verified in git log.
