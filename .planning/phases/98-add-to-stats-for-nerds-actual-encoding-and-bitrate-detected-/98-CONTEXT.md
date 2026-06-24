# Phase 98: Add to Stats for Nerds — Actual Encoding & Bitrate Detected - Context

**Gathered:** 2026-06-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Surface the **actually playing** audio encoding and bitrate in the Stats-for-Nerds
panel so the user can validate the live stream matches what they expect ("am I really
getting the AAC 256k I think I picked?"). Scope is the Stats-for-Nerds panel only —
the panel is hidden by default behind the existing toggle (Phase 47.1). Detection of
the actual values from the GStreamer pipeline is net-new for codec/bitrate; detected
sample-rate/bit-depth already exist (Phase 70) and are surfaced into the panel here.

Out of scope: changing the main Now Playing display, the stream picker labels, or how
declared metadata is parsed/stored.
</domain>

<decisions>
## Implementation Decisions

### Detected vs expected presentation
- **D-01:** For **Encoding** and **Bitrate**, the panel shows the detected value AND
  the declared/expected value together (always, not only on mismatch). This directly
  serves the phase goal "validate you are playing what you expect."
- **D-02:** A mismatch (detected ≠ expected) is flagged by rendering the **detected
  value in an amber/warning color**; when they match, the value uses the normal muted
  stats-label color. No warning icon, no tooltip — color only (keeps the plain panel
  aesthetic).
- **D-03:** "Expected" is sourced from the **declared `Stream.codec` and
  `Stream.bitrate_kbps`** fields (the PLS/URL-parsed metadata, FIX-PLS-01). No new
  source of truth is introduced.

### Which fields to surface
- **D-04:** Add **four** detected format rows to the Stats-for-Nerds panel:
  **Encoding, Bitrate, Sample-rate, Bit-depth.** Sample-rate/bit-depth are already
  detected (Phase 70) so surfacing them completes the "actual stream format" block.
- **D-05:** Only **Encoding** and **Bitrate** get the detected-vs-expected comparison
  and amber mismatch flag. **Sample-rate** and **Bit-depth** are **detected-only**
  rows — there is no independent declared/expected value to compare against (Phase 70
  writes the *detected* values into the same `Stream.sample_rate_hz` / `bit_depth`
  columns, so a comparison would be circular).

### Detection liveness
- **D-06:** Detected encoding/bitrate are captured as a **one-shot snapshot at
  preroll** (when the stream stabilizes), mirroring the existing Phase 70 one-shot
  caps-detection pattern. No live/continuous updates as VBR bitrate tags fluctuate —
  avoids a jittering number and stays consistent with the established pattern.

### Unknown / unavailable states
- **D-07:** When a stream exposes no codec or bitrate (raw PCM, some HLS/YouTube), the
  row value renders as an **em-dash `—`**. Rows are **always present** (stable panel
  layout regardless of station). When the expected value is also unknown, no mismatch
  flag is applied (nothing to compare).

### Claude's Discretion
- Exact GStreamer detection mechanism for codec/bitrate (e.g. `TAG_AUDIO_CODEC` /
  `TAG_BITRATE` / `TAG_NOMINAL_BITRATE` bus tag messages vs caps inspection) — for the
  researcher/planner to determine. The audio-sink caps are decoded PCM, so encoding
  must come from tags or an earlier pipeline element.
- For VBR, whether the one-shot snapshot prefers a nominal/average bitrate tag over an
  instantaneous one (user chose plain one-shot, not the "prefer nominal" variant — so
  this is a soft preference, not a requirement).
- Bitrate mismatch tolerance — whether a tiny declared-vs-detected delta (e.g. 320 vs
  319 kbps) should suppress the amber flag, or only flag on a meaningful/family
  difference. Pick a sensible tolerance to avoid false positives.
- Exact row labels and ordering within the panel; how detected+expected are formatted
  in a single value cell (e.g. `MP3  (expected AAC)`).
</decisions>

<specifics>
## Specific Ideas

- The point of the feature is validation/trust: a quick glance should confirm "yes,
  this is the AAC 256k I expect" or visibly warn that it isn't. The amber-on-mismatch
  treatment (D-02) is the mechanism for that signal.
</specifics>

<canonical_refs>
## Canonical References

No external specs or ADRs define this phase. ROADMAP.md lists no `Canonical refs:` for
Phase 98 and there is no SPEC.md. Requirements are fully captured in the decisions
above. Relevant prior-phase context is code-level (see Existing Code Insights), not
external documents.

- `.planning/REQUIREMENTS.md` §FIX-PLS-01 — defines how **declared** codec/bitrate are
  parsed/populated (the "expected" side of the D-01 comparison). Read to understand
  what `Stream.codec` / `Stream.bitrate_kbps` contain and when they're empty.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `musicstreamer/player.py` `_on_caps_negotiated` / `_arm_caps_watch_for_current_stream`
  (Phase 70 / DS-01): one-shot, streaming-thread caps read that emits the queued
  `audio_caps_detected(stream_id, rate_hz, bit_depth)` signal. The codec/bitrate
  detection (D-06 one-shot) should follow this exact pattern and likely emit an
  analogous queued signal.
- `musicstreamer/ui_qt/main_window.py` `_on_audio_caps_detected` (line ~701): main-thread
  receiver that persists detected rate/bit_depth via `repo.update_stream`. The natural
  integration point for delivering detected codec/bitrate to the panel.
- `musicstreamer/ui_qt/now_playing_panel.py` `_build_stats_widget` (line ~3471): the
  Stats-for-Nerds `QFormLayout` using `_MutedLabel` rows (Buffer / Underruns /
  Buf duration), all governed by the single `set_stats_visible` toggle. New format rows
  go here and inherit that visibility toggle (no per-row visibility code — Phase 47.1
  Pitfall 8).
- `_MutedLabel`: theme-responsive muted label used for stats values; extend/parameterize
  for the amber mismatch color (D-02) so light↔dark theme flips stay readable.

### Established Patterns
- Cross-thread rule (qt-glib-bus-threading.md): GStreamer streaming/bus-thread handlers
  MUST only emit queued Signals — never touch Qt widgets or the pipeline directly.
  Detected codec/bitrate must reach the panel via a QueuedConnection signal, same as
  `audio_caps_detected`.
- One-shot per-stream guard (`_caps_armed_for_stream_id`) prevents duplicate emissions;
  the codec/bitrate one-shot needs an equivalent disarm guard.
- Declared codec/bitrate live on the `Stream` record as `s.codec` / `s.bitrate_kbps`
  (used today for stream-picker labels in `now_playing_panel.py` ~1596/2813).

### Integration Points
- Detection added in `player.py` (GStreamer side) → queued signal → `main_window.py`
  receiver → `now_playing_panel` stats rows. The panel needs both the detected values
  AND the current stream's declared `codec`/`bitrate_kbps` to render the comparison.
</code_context>

<deferred>
## Deferred Ideas

- Live/continuous VBR bitrate updating (rejected in favor of D-06 one-shot snapshot) —
  could be revisited if a future "real-time stream telemetry" feature is wanted.

### Reviewed Todos (not folded)
- `pls-codec-bitrate-url-fallback` (matched score 0.9) — already resolved as FIX-PLS-01
  (Phase 92). It concerns the **declared** codec/bitrate; Phase 98 is about **detected**
  values. Not in scope. The other matched todos are unrelated test-failure / tooling
  items.
</deferred>

---

*Phase: 98-add-to-stats-for-nerds-actual-encoding-and-bitrate-detected*
*Context gathered: 2026-06-24*
