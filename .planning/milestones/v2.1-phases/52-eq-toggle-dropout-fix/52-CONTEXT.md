# Phase 52: EQ Toggle Dropout Fix — Context

**Gathered:** 2026-04-28
**Status:** Ready for planning

<domain>
## Phase Boundary

When the user clicks the EQ toggle in the Now Playing panel during playback, eliminate the brief audible click/pop that currently occurs in both directions (toggle-on AND toggle-off). The click is the classic IIR-filter coefficient-discontinuity signature — `equalizer-nbands` band gains snapping from zero to profile values (or vice versa) in a single buffer creates a transient in the filtered output.

In scope:
- Replace the atomic gain switch in `Player.set_eq_enabled` with a short gain-ramping transition (~40ms over 8 ticks of 5ms) that interpolates each band from its current gain to its target gain.
- Handle rapid re-toggles (user toggles again while a ramp is in progress) by reversing from the current in-progress gains rather than snapping or queuing.

Explicitly NOT in scope:
- Changing how `equalizer-nbands` is wired into `playbin3.audio-filter` (that pipeline-level decision is owned by Phase 47.2 D-01 and stays).
- Touching the profile-load path (`set_eq_profile` → `_rebuild_eq_element`) which intentionally goes through a `READY`-state pipeline transition for band-count changes. That path is not implicated in toggle dropouts.
- Audio-quality investigation beyond the toggle path (preamp slider, profile selection, etc.).
- Replacing `equalizer-nbands` with a different element or building a tee/crossfader sub-pipeline.
- UI redesign of the toggle button. Visual state stays as-is.

</domain>

<decisions>
## Implementation Decisions

### Symptom characterization

- **D-01:** The dropout symptom is a **brief click or pop, ≈10–50ms artifact**, on both toggle directions (off→on AND on→off). Audio resumes immediately; this is not silence, not a stutter, not a level jump. The symptom matches the IIR-filter coefficient-discontinuity signature exactly: `equalizer-nbands` band gains changing in a single buffer cause the biquad coefficients to recompute, producing a transient at the filter output.

### Fix mechanism

- **D-02:** Replace the atomic gain switch in `Player._apply_eq_state` with **smooth gain ramping**: when `set_eq_enabled` is called, interpolate each band's gain from its current value to its target value over ~40ms in 8 ticks of 5ms. The filter coefficients change incrementally instead of jumping, masking the discontinuity below the noise floor. No volume dip, no perceptible artifact — the EQ fades in/out smoothly.

  Pseudocode:
  ```
  set_eq_enabled(True):
    start_gain = [current per-band gain]
    target    = [profile gain ± preamp]
    for k in 1..8:  # tick every 5ms
      t = k / 8.0
      band[i].gain = lerp(start_gain[i], target[i], t)
    # tick 8 commits the final target exactly
  ```

  When `set_eq_enabled(False)` is called, the same ramp runs with target = all-zeroes (the existing bypass semantics from D-05 of Phase 47.2).

- **D-03:** The ramp **runs on the GUI thread via QTimer** (5ms interval, single-shot or interval timer with a counter). GStreamer band-gain mutations via GstChildProxy from the GUI thread are already the established pattern (`_apply_eq_state` runs there today) — the ramp continues that contract. No new threading.

- **D-04:** During a ramp, `_apply_eq_state` per-tick uses the same band-property write pattern that exists today (`band.set_property("gain", ...)`). No new GStreamer plumbing — only the timing of the writes changes. The biquad type / freq / bandwidth properties are written once at ramp start (since they don't change between tick gain values), not on every tick.

### Rapid re-toggle behavior

- **D-05:** **Reverse from current point on re-toggle.** If the user toggles again while a ramp is in progress, the ramp's current per-band in-progress gains become the new `start_gain`, the new target replaces the old target, and the timer continues running for a fresh ~40ms ramp from the new start to the new target. State machine:
  - Ramp state: `(start_gain[], target_gain[], tick_index, is_running)`.
  - On `set_eq_enabled(new_value)`: capture `current_gain[]` from the running tick (or directly from the equalizer element via GstChildProxy), set as new `start_gain`, recompute new `target` from `new_value` + current profile + preamp, reset `tick_index = 0`, ensure timer is running.
  - This produces a smooth, audible reversal even on rapid clicks. No clicks, no queued ramps, no UI lockout.

### State-write semantics

- **D-06:** `self._eq_enabled = bool(enabled)` (the in-memory flag) is set **immediately** on `set_eq_enabled` entry — i.e., before the ramp completes. The ramp affects only the audio-output path, not the state flag. This matches existing semantics: `_eq_enabled` reflects user intent the moment the toggle clicks, and any code reading it sees the new value immediately. The ramp is purely about smoothing the gain transition.

- **D-07:** The SQLite `eq_enabled` setting persistence in `_on_eq_toggled` (now_playing_panel.py:492) stays as-is — it writes the boolean immediately on click. No interaction with the ramp.

### Claude's Discretion

- **Acceptance bar interpretation** — "no audible dropout" means UAT-pass: Kyle clicks the toggle 10× rapidly during playback of a representative AA station and reports zero audible artifacts. No formal SNR / spectrogram thresholds; this is a single-user perceptual test.
- **SC #3 ("toggle fires exactly once per click")** — verified at scout time: only `clicked` is connected (not `toggled`), no programmatic `.click()` calls. The wiring is already clean. Planner should add a defensive test that asserts the button uses `clicked` (not `toggled`) and that `_on_eq_toggled` is invoked once per simulated click — but no behavior change is needed to satisfy SC #3. The phrasing in ROADMAP suggests Kyle may have perceived double-fires; once the click artifact is gone, the perceived double-fire likely goes too (one click + audible artifact ≈ "did that even register?").
- Ramp timer attribute name (`self._eq_ramp_timer`, `self._eq_smooth_timer`, etc.) — planner picks.
- Whether to expose ramp duration as a constant in `constants.py` (consistent with `BUFFER_DURATION_S` pattern) or inline as a `_EQ_RAMP_MS = 40` module-level constant in `player.py` — planner picks.
- Whether the ramp can be skipped (e.g., if `_eq is None` or `_eq_profile is None`) — planner figures out the early-exit conditions; `_apply_eq_state`'s existing early-return for `_eq is None` should still apply.
- Whether to add a unit test that captures multiple per-tick band gains (assertion: gains progress linearly across ticks) — planner picks; would be a behavioral test against a fake/spy `equalizer-nbands` element.
- Whether to lerp gain in **dB linearly** (current band.gain_db is dB, lerp dB linearly) or in **linear amplitude** (convert dB → linear, lerp, convert back). dB-linear is the simpler choice and is psychoacoustically reasonable for a 40ms transition. Planner picks; recommend dB-linear unless there's a reason not to.

</decisions>

<specifics>
## Specific Ideas

- The IIR coefficient-discontinuity diagnosis is the most likely cause given the click symptom on both directions. Smooth ramping is the textbook DSP fix.
- Volume changes via `pipeline.set_property("volume", ...)` (`set_volume` at player.py:203) do NOT produce a click — confirms the dropout is specific to `equalizer-nbands` band-gain mutation, not the property-write mechanism itself.
- `_rebuild_eq_element` (player.py:661) intentionally goes through `Gst.State.READY` to handle band-count changes (e.g., loading a profile with a different number of bands). That path is **not** the toggle path — toggling never changes band count. Planner does not need to touch `_rebuild_eq_element`.
- 40ms ramp at 48 kHz sample rate = ~1920 samples. Plenty of room for the biquad transient response to settle smoothly.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` §"Phase 52: EQ Toggle Dropout Fix" — goal, dependencies, three success criteria.
- `.planning/REQUIREMENTS.md` §BUG-03 — the underlying bug requirement.
- `.planning/PROJECT.md` Key Decisions table — Phase 47.2 EQ decisions (D-01: equalizer-nbands in audio-filter slot; D-04: rebuild element for band-count change; D-05: bypass via zeroed gains; D-15: settings persistence; Pitfalls 1, 4, 5).

### Code touch points (load these to understand current state)

#### EQ pipeline (the surface being changed)
- `musicstreamer/player.py:111–114` — `equalizer-nbands` element installed in `playbin3.audio-filter` slot (Phase 47.2 D-01). Element constructed once at Player init.
- `musicstreamer/player.py:191–193` — `_eq_enabled`, `_eq_preamp_db`, `_eq_profile` instance fields. State the ramp reads.
- `musicstreamer/player.py:211–214` — `set_eq_enabled(enabled)` — entry point Phase 52 modifies. Currently calls `_apply_eq_state()` synchronously.
- `musicstreamer/player.py:637–659` — `_apply_eq_state()` — atomic gain writer Phase 52 replaces with a ramp. Bypass path (lines 646–649) zeroes all band gains in a single pass; profile path (lines 650–659) writes freq/bandwidth/gain/type for each band. Both paths must become ramp-aware.
- `musicstreamer/player.py:661–671` — `_rebuild_eq_element` — DO NOT touch. Profile-load READY-state transition stays.

#### Toggle UI (verifying SC #3)
- `musicstreamer/ui_qt/now_playing_panel.py:247–262` — `eq_toggle_btn` construction. Verify only `clicked` is connected, no `toggled`, no programmatic `.click()`. SC #3 already satisfied at the wiring level.
- `musicstreamer/ui_qt/now_playing_panel.py:489–492` — `_on_eq_toggled(checked)` — calls `player.set_eq_enabled(checked)` and writes the SQLite setting. No change here for Phase 52 — the ramp is a Player-internal concern.

#### Volume precedent (no-dropout property mutation)
- `musicstreamer/player.py:203–205` — `set_volume(value)` — single property write, no dropout. Reference for "GStreamer property mutations from the GUI thread don't dropout in general; the dropout is specific to band-gain coefficient discontinuity."

#### Existing test surface
- `tests/test_player.py:205–360` — `set_eq_enabled` functional tests (verify gains apply correctly). Phase 52 adds tests for the ramp behavior (gains progress through intermediate values).
- `tests/test_now_playing_panel.py:60, 662–673` — toggle UI test (verifies `_on_eq_toggled` calls `set_eq_enabled` + persists setting). Phase 52 may add a defensive test that the wiring uses `clicked` (not `toggled`) for SC #3.

### Project conventions
- QA-05: Bound-method connections, no self-capturing lambdas. Applies to any new QTimer.timeout connections.
- Phase 47.2 Pitfall 4: GStreamer `bandwidth` is Hz, not Q — preserved during ramp (bandwidth is set once at ramp start, not per-tick).
- Phase 47.2 Pitfall 5: preamp ADDS to band gain (don't subtract abs). Applies to target-gain calculation in the ramp.
- Phase 47.2 Pitfall 1: `equalizer-nbands` `num-bands` realloc is unreliable — handled by `_rebuild_eq_element` for profile-load. Ramp does NOT change band count, so this pitfall doesn't apply.

### No external specs
No ADRs or external design docs referenced — the bug is fully captured by the three ROADMAP success criteria + the touch points above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`Player._apply_eq_state()`** — current synchronous gain writer. The ramp wraps this: at each tick, the ramp computes interpolated gains and calls a slimmer writer (or inlines the band-property writes).
- **GstChildProxy + `band.set_property("gain", float)`** — already the established mutation pattern. The ramp uses the same primitive, just at multiple timesteps.
- **`QTimer` (5ms interval)** — established pattern for timing-driven UI work elsewhere (`_url_timer` debouncer in `EditStationDialog`, `_failover_timer` in Player). Ramp timer follows same shape.
- **`_eq` element + `_eq_profile` + `_eq_preamp_db`** — all the inputs the ramp needs. No new state shape required beyond a small ramp state struct.

### Established Patterns
- **GUI-thread band mutation** — `_apply_eq_state` runs on the main thread today; `set_eq_enabled` is called from `_on_eq_toggled` on the main thread. No threading boundaries cross. The ramp keeps that contract.
- **Single-shot QTimer + counter idiom** — for fixed-tick-count timed sequences. Alternative: an interval timer with a tick counter that stops itself when reaching N. Either works.
- **Property writes via GstChildProxy** — `equalizer-nbands` exposes per-band as children indexed 0..n-1; `get_child_by_index(i).set_property(...)` is the established access pattern (lines 647–648, 653–659).

### Integration Points
- **No new public API** — `set_eq_enabled(bool)` keeps its signature. The ramp is entirely internal to `Player`.
- **No now_playing_panel changes** — the panel calls `set_eq_enabled` and that's it. UI behavior is unchanged.
- **No SQLite changes** — settings persistence stays atomic in `_on_eq_toggled`.
- **No constants change** required (planner may choose to add `_EQ_RAMP_MS = 40` and `_EQ_RAMP_TICKS = 8` constants — Claude's discretion).

</code_context>

<deferred>
## Deferred Ideas

- **Smoothing on `set_eq_profile` (profile change)** — Phase 47.2's `_rebuild_eq_element` does a `READY`-state transition when band count changes, which produces its own brief silence. Smoothing that path would require a different mechanism (READY transition is not amenable to gain-ramp smoothing). Out of scope for Phase 52; revisit only if Kyle reports dropouts during profile changes.
- **Smoothing on `set_eq_preamp` (preamp slider drag)** — currently writes immediately on slider change. May produce small clicks during fast drags. Could reuse the same ramp infrastructure if needed; out of scope for Phase 52 (slider ergonomics aren't part of BUG-03).
- **Replacing `equalizer-nbands` with a different element** — overkill for the click symptom. Element choice is locked by Phase 47.2 D-01.
- **Moving SQLite write off the GUI thread** — confirmed not the dropout cause (GStreamer runs in its own threads), so no benefit. Not in scope.
- **Disabling toggle button during ramp** — explicitly rejected (D-05) in favor of reverse-from-current. Could revisit if rapid-toggle artifacts persist after smoothing, but unlikely.

</deferred>

---

*Phase: 52-eq-toggle-dropout-fix*
*Context gathered: 2026-04-28*
