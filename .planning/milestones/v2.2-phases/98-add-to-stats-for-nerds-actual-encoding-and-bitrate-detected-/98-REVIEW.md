---
phase: 98-add-to-stats-for-nerds-actual-encoding-and-bitrate-detected-
reviewed: 2026-06-27T15:15:41Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - musicstreamer/player.py
  - musicstreamer/ui_qt/main_window.py
  - musicstreamer/ui_qt/now_playing_panel.py
  - tests/_fake_player.py
  - tests/test_now_playing_panel.py
  - tests/test_now_playing_stats.py
  - tests/test_player_codec_tag.py
findings:
  critical: 0
  warning: 2
  info: 3
  total: 5
status: issues_found
---

# Phase 98: Code Review Report

**Reviewed:** 2026-06-27T15:15:41Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Reviewed the Phase 98 codec/bitrate detection feature: the GStreamer-side
`_normalise_audio_codec` mapper and the one-shot codec/bitrate tag block in
`Player._on_gst_tag`, the new `audio_format_detected` Signal, the panel's
`update_detected_format` / `update_detected_caps` methods, the four new
`_build_stats_widget` rows, the `_StatLabel` amber-mismatch widget, and the
MainWindow `QueuedConnection` wiring.

Overall the change is careful: threading discipline is correct (bus-loop handler
only emits a Signal; receiver connects `QueuedConnection`), the preroll guard was
correctly hoisted above the codec block, the bind-time reset of all four rows
prevents stale-station bleed, and `set_mismatch` is only invoked on the two
`_StatLabel` rows (not the plain `_MutedLabel` sample-rate / bit-depth rows). No
blockers found.

The two warnings both concern the lifecycle of the
`_codec_tag_armed_for_stream_id` one-shot guard, which is armed in two places with
an ordering gap that opens a narrow stream-id misattribution window and breaks the
"exactly one emission per stream" contract that the tests assert in isolation.

## Warnings

### WR-01: Codec guard armed AFTER `set_state(PLAYING)` — first codec tag can be missed or misattributed to the previous stream

**File:** `musicstreamer/player.py:1666-1684`
**Issue:** In `_set_uri`, the pipeline is started (`set_state(Gst.State.PLAYING)`,
line 1679) BEFORE the codec guard is armed (`_codec_tag_armed_for_stream_id =
self._current_stream.id`, line 1684). Once PLAYING is requested, GStreamer streaming
threads begin posting tag messages, which the bus-loop thread dispatches into
`_on_gst_tag`. If a codec tag for the new stream is dispatched in the window between
line 1679 and line 1684, the guard still holds its value from the *previous* stream:
- If the previous stream already emitted, the guard is `0` and the new stream's first
  codec tag is silently dropped (codec/bitrate row stays em-dash until a tag repeats).
- If the previous stream never emitted (its tag never arrived), the guard still holds
  the *old* `stream_id`. The new stream's codec tag then emits `audio_format_detected`
  with the **wrong `sid`**, so the panel looks up the wrong declared stream, shows the
  wrong `(exp: …)` value, and may flag a false amber mismatch.

The re-arm in `_on_playbin_state_changed` (line 1393-1395) partially self-heals this,
but only for streams whose codec tag *repeats* after the PLAYING transition; a
single-shot codec tag leaves the wrong/missing value displayed.

**Fix:** Arm the guard before starting the pipeline so it is ready when tags begin to
flow:
```python
def _set_uri(self, uri: str) -> None:
    self._youtube_resolve_in_flight = False
    uri = aa_normalize_stream_url(uri)
    self._pipeline.set_state(Gst.State.NULL)
    self._pipeline.get_state(Gst.CLOCK_TIME_NONE)
    # Phase 98: arm the codec guard BEFORE PLAYING so the bus-loop thread
    # cannot process the new stream's first codec tag against a stale guard.
    self._codec_tag_armed_for_stream_id = self._current_stream.id if self._current_stream else 0
    self._pipeline.set_property("uri", uri)
    self._pipeline.set_state(Gst.State.PLAYING)
    self._arm_caps_watch_for_current_stream()  # caps watch legitimately stays post-PLAYING
```

### WR-02: Re-arm on every PLAYING transition makes `audio_format_detected` fire repeatedly per stream — the "one-shot" contract the tests assert is not actually upheld at runtime

**File:** `musicstreamer/player.py:1393-1395` (re-arm) and `1189-1203` (one-shot block)
**Issue:** `_on_playbin_state_changed` re-arms `_codec_tag_armed_for_stream_id` on
*every* transition to PLAYING. Per its own docstring (player.py:1356-1361) this slot
fires not only on NULL→PLAYING but also on **PAUSED→PLAYING auto-rebuffer recovery**
and pause/resume. Each such transition re-arms the guard, so the next repeated codec
tag re-emits `audio_format_detected` for a stream that already reported its format.
This contradicts the documented "exactly one emission per stream" intent
(player.py:1189 "one-shot", test_player_codec_tag.py:147 `test_codec_tag_one_shot_disarm`).
The one-shot tests call `_on_gst_tag` twice directly and never exercise the re-arm
path, so they give false confidence that re-emission cannot happen.

The data effect is currently benign (the panel recomputes the same declared/detected
comparison idempotently), so this is a WARNING, not a blocker. But it is a latent
trap: any future `update_detected_format` side effect that is *not* idempotent (e.g.
a toast, a one-time DB write, an animation) would fire on every rebuffer. The
behavior is also load-bearing for WR-01's self-heal, so the two findings should be
resolved together rather than independently.

**Fix:** Make the intent explicit and tested. Either (a) document that re-detection
per PLAYING transition is intentional and add a regression test that drives
`_on_playbin_state_changed` → tag → second emission, or (b) if true one-shot per
stream is desired, gate the re-arm on a "have not yet emitted for this stream id"
flag rather than unconditionally re-arming. Recommended minimal change — only re-arm
when the guard would otherwise be lost for a not-yet-detected stream:
```python
# Only (re)arm if this stream has not already reported its format, so a
# rebuffer PAUSED->PLAYING does not re-emit for an already-detected stream.
if self._current_stream and self._codec_detected_for_stream_id != self._current_stream.id:
    self._codec_tag_armed_for_stream_id = self._current_stream.id
```
(set `_codec_detected_for_stream_id = sid` in the emit block at player.py:1201-1203).

## Info

### IN-01: `_BITRATE_TOLERANCE_KBPS` is a magic number defined as a local inside a hot method

**File:** `musicstreamer/ui_qt/now_playing_panel.py:1283`
**Issue:** `_BITRATE_TOLERANCE_KBPS = 5` is defined as a local variable inside
`update_detected_format`, re-bound on every call. Every other tuning constant in this
phase and module (`_GBS_QUEUE_MAX_ROWS`, `_AA_POLL_INTERVAL_*`, `_GROWTH_SCHEDULE`,
`_LIVE_DVR_SEEK_OFFSET_S`) lives at module or class scope where it is searchable and
documented. The 5 kbps tolerance is a meaningful behavioral threshold (locked by
`test_bitrate_mismatch_tolerance`) and should be hoisted alongside them.
**Fix:** Promote to module scope: `_BITRATE_TOLERANCE_KBPS = 5  # Phase 98 Finding 5`
and reference it from the method.

### IN-02: `_codec_tag_armed_for_stream_id` is not reset in `stop()` / `pause()`

**File:** `musicstreamer/player.py:952-997` (stop), `922-950` (pause)
**Issue:** Unlike `_streams_queue`, `_recovery_in_flight`, `_preroll_in_flight`, etc.,
the codec guard is never cleared on `stop()` or `pause()`. After a stop the guard can
remain armed with the just-stopped stream's id. Combined with WR-01's ordering gap,
this is the source state that lets a stale non-zero id survive into the next
`_set_uri`. `set_state(NULL)` flushes the bus so a real late tag is unlikely, but
explicitly disarming on stop removes the stale-id hazard and matches the disarm
discipline used elsewhere in this file.
**Fix:** Add `self._codec_tag_armed_for_stream_id = 0` to `stop()` (and optionally
`pause()`) alongside the existing state resets.

### IN-03: Declared-codec variants outside the normalized vocabulary can raise false amber mismatches

**File:** `musicstreamer/ui_qt/now_playing_panel.py:1291-1293`
**Issue:** The mismatch check compares the *normalized* detected codec (always one of
MP3/AAC/FLAC/OPUS/OGG) against the raw declared `Stream.codec` string,
case-insensitively but without normalization. A station whose declared codec is a
variant label such as `"AAC+"`, `"HE-AAC"`, or `"AAC-LC"` will detect as `"AAC"` and
be flagged as a mismatch (amber) even though it is the same family. Today the declared
vocabulary is constrained to the same five tokens (D-03), so this is latent rather
than active, but it is an asymmetry: detected values are normalized through
`_normalise_audio_codec` while declared values are not.
**Fix:** Normalize the declared codec through the same mapper before comparing, e.g.
compare `_normalise_audio_codec(declared_codec)` (imported into the panel) against
`detected_codec`, so both sides share one vocabulary.

---

_Reviewed: 2026-06-27T15:15:41Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
