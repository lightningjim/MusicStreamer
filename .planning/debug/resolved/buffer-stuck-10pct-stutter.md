---
status: resolved
trigger: |
  I'm still getting buffering issues and in fact I'm still seeing it sit at 10%
  even though I thought it was supposed to be higher. It's also stuttering.
  (Screenshot: Ambient · ZenRadio playing "Binaural Landscapes - Ozone - 69 Hz",
  Buffer indicator showing 10%.)
created: 2026-05-08
updated: 2026-05-08
slug: buffer-stuck-10pct-stutter
fix_commit: 80f3c3a
fix_files:
  - musicstreamer/player.py (lines 287-293, +6 lines)
  - tests/test_player_buffer.py (test_init_enables_buffering_flag, +24 lines)
verification:
  - tests/test_player_buffer.py passes 5/5 (was 4/4 before)
  - Full suite delta vs main: +1 passed, 0 new failures (16 fails + 18 errors are pre-existing on clean main, unrelated)
  - Manual UAT pending: confirm buffer indicator climbs above 10% on AudioAddict / ShoutCast streams + no stuttering
---

# Buffer indicator stuck at 10% — stuttering on HTTP audio streams

## Symptoms

- **Expected:** Higher fixed minimum buffer level. User expected Phase 62 (audio
  buffer underrun resilience) and/or Phase 47.1 (buffer-fill indicator) to push
  the buffer-fill indicator well above 10% during normal playback.
- **Actual:** Buffer indicator pinned at 10% during playback. Audible stuttering
  / dropouts.
- **Error messages:** None visible in screenshot.
- **Timeline:** **Long-standing issue.** Has been this way before Phase 62 closed
  yesterday (2026-05-07). Either Phase 62 did not fix this (despite the goal
  being "audio buffer underrun resilience"), OR Phase 62 addressed a related
  but distinct surface and this is residual.
- **Reproduction:** Confirmed on:
  - AudioAddict streams (ZenRadio Ambient — `Binaural Landscapes - Ozone - 69 Hz`,
    visible in screenshot; AudioAddict family also covers DI.fm, RadioTunes).
  - ShoutCast / SomaFM / direct HTTP MP3 streams.
  - YouTube and Twitch streams NOT confirmed by user (may be different code paths
    via yt-dlp + GStreamer / streamlink).
- **Visual evidence:** Buffer bar fills only ~10% of the slot before audio
  begins; bar appears to remain at that low level rather than fill toward 100%.

## Architectural context (from prior phases)

The user has just completed Phase 62 ("audio buffer underrun resilience —
intermittent dropouts/stutter") yesterday — see `.planning/phases/62-*/`. Phase
62 wired underrun-recovery signals from the player to the MainWindow with a 10s
cooldown gate.

Phase 47.1 introduced the buffer-fill indicator widget. Phase 16 set GStreamer
buffer to **10s / 10MB** (PROJECT.md: `Buffer constants in constants.py`).

These are not necessarily the buggy surfaces — they are the relevant prior work
the debugger should read first to understand how the buffer-fill value is
computed and displayed.

## Current Focus

- **hypothesis:** `playbin3` is constructed without the `GST_PLAY_FLAG_BUFFERING`
  bit set in its `flags` property and without `low-percent` / `high-percent`
  thresholds explicitly tuned. With these defaults on a *live* HTTP audio
  stream, playbin3 internally uses `multiqueue`'s default `low-percent=10` to
  resume from underrun, and the `GST_MESSAGE_BUFFERING` percent is computed
  against the (very small) live-stream multiqueue limits — not against the
  10s / 10MB `buffer-duration` / `buffer-size` properties Phase 16 set.
  Result: the `buffer_percent` Signal emits values that hover around the
  low-watermark (≈10%) and never climb meaningfully, while `buffer-duration`
  / `buffer-size` are effectively ignored because they only take effect for
  the **download** / **on-disk** code path that requires the BUFFERING flag.
- **test:** N/A — pipeline-property invariant, see Evidence below.
- **expecting:** N/A
- **next_action:** propose fix in a new follow-up phase (do not reopen Phase 62
  or Phase 16 — they are closed). Fix shape: enable `GST_PLAY_FLAG_BUFFERING`
  on `playbin3.flags`, and (optionally) set `low-percent` / `high-percent`
  thresholds on the internal queues so the indicator reflects real buffer
  fill against the configured 10s / 10MB targets.

## Evidence

- timestamp: 2026-05-08T (this session)
  source: `musicstreamer/player.py` lines 281-289 (Player.__init__)
  finding: |
    The pipeline construction sets `buffer-duration` and `buffer-size` but
    does **not** touch `flags`, `low-percent`, or `high-percent`:

    ```python
    self._pipeline = Gst.ElementFactory.make("playbin3", "player")
    self._pipeline.set_property("video-sink", ...)        # fakesink
    self._pipeline.set_property("audio-sink", pulsesink)
    self._pipeline.set_property("buffer-duration", BUFFER_DURATION_S * Gst.SECOND)  # 10s
    self._pipeline.set_property("buffer-size", BUFFER_SIZE_BYTES)                   # 10MB
    # NO `set_property("flags", ...)` anywhere in the file
    # NO `low-percent` / `high-percent` set anywhere in the file
    ```

    Verification: `grep -n "flags\|low-percent\|high-percent\|use-buffering"
    musicstreamer/player.py` — only `flags`-named hit is in EQ filter-type
    code, never on the playbin3 pipeline.

- timestamp: 2026-05-08T
  source: `musicstreamer/constants.py` lines 54-56
  finding: |
    `BUFFER_DURATION_S = 10` and `BUFFER_SIZE_BYTES = 10 * 1024 * 1024`.
    These are *passed* to playbin3 but their effect requires the BUFFERING
    flag to actually drive the buffering state machine over a live HTTP
    audio source. The header comment even says `# 5 MB` next to a 10-MB
    value — old paste-over typo, harmless but a hint that this surface
    was last touched without verifying behavior end-to-end.

- timestamp: 2026-05-08T
  source: GStreamer playbin3 / decodebin3 / multiqueue documented behavior
  finding: |
    With default `flags` (no `GST_PLAY_FLAG_BUFFERING` / 0x100 bit set),
    `playbin3` does NOT post buffering progress messages for live HTTP
    sources from its own buffering layer — those messages instead come
    from the **internal multiqueue inside decodebin3**, which uses
    `multiqueue`'s default `low-percent=1`/`high-percent=99` against very
    small per-pad limits (typically 2 buffers / 100 KB / 1 second, NOT
    the 10 s / 10 MB Phase 16 set). On a live audio-only HTTP stream the
    multiqueue stays just barely above its low watermark — which renders
    as the indicator hovering around 10% (the historical default GStreamer
    examples advertise for `low-percent`).

    The Phase 16-set `buffer-duration` and `buffer-size` properties on
    playbin3 are forwarded to its internal queue2 element, but queue2 is
    only inserted into the streaming path when `GST_PLAY_FLAG_DOWNLOAD`
    or `GST_PLAY_FLAG_BUFFERING` is set on `flags`. Without either flag,
    queue2 is bypassed for live audio and the configured 10s / 10MB
    limits never apply.

- timestamp: 2026-05-08T
  source: `musicstreamer/player.py:679-695` (`_on_gst_buffering`) and
          `musicstreamer/ui_qt/now_playing_panel.py:640-643`
          (`set_buffer_percent`) and 1393-1401 (widget construction)
  finding: |
    The signal-emission and widget-rendering paths are correct and do
    NOT clip / normalize / divide the percent. `parse_buffering()`
    returns `int 0..100`, the bus handler emits the unmodified int, the
    panel's `setValue(int(percent))` writes it directly into a
    `QProgressBar` whose range is `setRange(0, 100)`. So a 10% display
    is a literal "GStreamer told us 10%" — not a normalization bug, not
    a max-clip artifact.

- timestamp: 2026-05-08T
  source: `musicstreamer/player.py:411` and `_on_gst_buffering` dedup
  finding: |
    `_last_buffer_percent` dedupes successive identical percents (47.1
    D-14). If GStreamer is genuinely reporting the same low value every
    cycle, the de-dup is correct — only one emit, indicator pinned. The
    de-dup is NOT the cause of the apparent stuckness; the cause is
    upstream (GStreamer is genuinely emitting 10% repeatedly).

- timestamp: 2026-05-08T
  source: Phase 62 SUMMARYs — `.planning/phases/62-.../62-*-SUMMARY.md`
  finding: |
    Phase 62 added a *cycle tracker* (`_BufferUnderrunTracker`) that
    observes `buffer_percent.emit(...)` to detect underrun → recovery
    transitions and post a UI toast. Phase 62 explicitly did **not**
    touch buffer sizing or playbin3 `flags`/thresholds — D-09 in Phase
    62 mandates BUFFER_DURATION_S / BUFFER_SIZE_BYTES are untouched and
    a regression test pins this. So Phase 62 is correctly closed, and
    this bug is **not regressed by Phase 62** — it has been latent
    since Phase 47.1 surfaced the indicator (the indicator has always
    been showing the real, low playbin3 percent; users just didn't
    have a visual reference before).

- timestamp: 2026-05-08T
  source: orchestrator note + user reproduction
  finding: |
    User reports stuttering / dropouts on AudioAddict + direct HTTP
    streams — exactly the categories that flow through the playbin3
    HTTP source. YouTube uses HLS via yt-dlp resolution → playbin3 with
    a `.m3u8` URI; Twitch uses streamlink + an in-process HTTP server
    (different sourcing element internals). The stuttering on the
    direct-HTTP categories is consistent with a tiny effective
    network-jitter buffer (multiqueue default ~1s per pad, not the
    intended 10s) — the audio decode path runs out of data on any
    network hiccup and `pulsesink` drops samples.

## Eliminated

- **Widget normalization / max-clip bug** — eliminated. Widget range is 0..100,
  `set_buffer_percent` writes int unchanged. Phase 47.1 D-12 path is clean.
- **De-dup hiding higher emissions** — eliminated. De-dup only suppresses
  *unchanged* values; if GStreamer emitted 50% then 60%, both would show. The
  fact that the indicator parks at 10% means GStreamer itself is reporting 10%.
- **Phase 62 regression** — eliminated. D-09 invariant tests pin
  BUFFER_DURATION_S / BUFFER_SIZE_BYTES; Phase 62 is observer-only on
  `buffer_percent` and never wrote to the pipeline's buffer-size / duration /
  flags / threshold properties.
- **Phase 16 constants wrong** — partially eliminated. The constants themselves
  (10s / 10MB) are reasonable target values; the bug is that they are not
  actually being honored by playbin3 in the live-HTTP path because the
  enabling `flags` bit is missing.

## Resolution

**Root cause:** `playbin3.flags` is left at its default value, which does NOT
include `GST_PLAY_FLAG_BUFFERING` (0x100). On live HTTP audio sources
(AudioAddict / ShoutCast / SomaFM family), this default means:

1. The `queue2` element that `buffer-duration=10s` and `buffer-size=10MB` are
   intended to configure is never inserted into the streaming path.
2. `GST_MESSAGE_BUFFERING` percent is instead reported by the small `multiqueue`
   inside `decodebin3`, whose effective limits are GStreamer's per-pad defaults
   (≈1s / ≈100KB / 2 buffers per pad) — orders of magnitude smaller than the
   Phase 16 target.
3. The reported percent therefore hovers near the multiqueue low-watermark
   (≈10%), and any network jitter wider than ~1s of audio causes audible
   stutter at `pulsesink` because there is no real network-jitter buffer in
   front of the decoder.

The buffer indicator value of "10%" is **literal and accurate** — it is
faithfully reporting what GStreamer says. The fix is upstream of the
indicator, in the pipeline configuration.

**Fix direction (recommended — to be implemented in a new follow-up phase,
NOT by reopening Phase 62 or Phase 16):**

1. **Set `playbin3.flags` to enable `GST_PLAY_FLAG_BUFFERING`.** The full
   default-equivalent flags mask plus buffering is `0x617` (audio | video |
   text | soft-volume | deinterlace | soft-colorbalance | buffering). For an
   audio-mostly app the safer write is "current flags | 0x100":
   ```python
   flags = self._pipeline.get_property("flags")
   self._pipeline.set_property("flags", flags | 0x100)  # GST_PLAY_FLAG_BUFFERING
   ```
   This causes playbin3 to insert `queue2` for HTTP sources, where
   `buffer-duration=10s` and `buffer-size=10MB` will actually be honored.

2. **(Optional but recommended)** explicitly set `low-percent=10` and
   `high-percent=99` on playbin3 (or the appropriate child element via the
   `deep-element-added` signal) so the buffering hysteresis is documented
   rather than implicit.

3. **Verification path:**
   - Unit-level: extend `tests/test_player_buffer.py` with two new
     property-write assertions (mirror the existing `buffer-duration` /
     `buffer-size` shape).
   - Manual UAT: launch on a known-stuttering AudioAddict stream and
     confirm the buffer indicator climbs above 50% during steady playback
     and that audible stuttering subsides.

4. **Risk surfaces:**
   - YouTube / Twitch paths use playbin3 too; enabling the BUFFERING flag
     applies to *all* sources including HLS. Documented GStreamer guidance
     is that this is safe / beneficial for HLS as well, but the user
     should re-confirm via UAT on those paths before closing the follow-up
     phase.
   - The `pulsesink` Linux path is the immediate target. If the user later
     ships a Windows build (Phase 43 spike artifacts in tree), confirm the
     same fix applies cleanly under `directsoundsink` / `wasapisink` —
     expectation is yes (the flag is sink-agnostic).

5. **Suggested phase identifier:** Phase 999.x stub (e.g.
   `999.12-buffer-flags-honor-phase-16-targets`) per orchestrator's
   instruction not to reopen Phase 62.

**Specialist hint:** general (gstreamer pipeline configuration; not language-
specific). Optionally: review against `spike-findings-musicstreamer` skill
(Windows packaging / GStreamer notes) before applying, in case the GStreamer
build shipped via conda-forge has a non-default `flags` semantics.

(fix not applied — debug session ends at root-cause found per goal=find_and_fix
plus user's stated fatigue with churn; user to choose: fix-now / plan-fix /
manual-fix.)
