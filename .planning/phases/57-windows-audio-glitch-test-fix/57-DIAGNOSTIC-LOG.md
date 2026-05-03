# Phase 57 / WIN-03 — Win11 VM Audio Diagnostic Log

**Started:** 2026-05-03
**Driver:** Linux orchestrator (interactive paste-back mode); user executed PowerShell + Python on Win11 VM
**Goal:** Capture the three D-04 readbacks (sink identity + `playbin3.volume` persistence across NULL→PLAYING + slider mid-stream effect), so Plan 57-03 knows whether to ship Option A (re-apply property), Option B (explicit `volume` element chained with EQ inside a `Gst.Bin`), or a hybrid; and so Plan 57-04 picks a glitch-smoothing approach that composes with the chosen volume fix.

---

## Pre-flight: VM environment readiness

| Check | Result | Notes |
|-------|--------|-------|
| Win11 22H2+ | ✓ | NT 10.0.26200 — Win11 25H2 |
| Conda env active | ✓ | `spike` env at `C:\Users\kcreasey\.conda\envs\spike` (activated before REPL) |
| Fresh installer artifact | ✓ | `Z:\musicstreamer\dist\installer\MusicStreamer-2.1.58-win64-setup.exe`, 67.2 MB, 2026-05-02. Built after Phase 58 merged while Phase 57 still in progress — WIN-03 wiring unchanged from `main` until 57-03/04 land, so PRE-FIX framing holds. |
| One playable HTTP stream available | ✓ | SomaFM Drone Zone (`http://ice1.somafm.com/dronezone-128-mp3`) reached PLAYING in self-contained REPL |
| Two PowerShell windows ready | self-managed | one for app, one for python introspection |

**Status:** READY

---

## D-04 Step 1: Audio Sink Identity (PRE-FIX)

**Method (interactive Python REPL on the VM, scratch helper at `.planning/phases/57-windows-audio-glitch-test-fix/57-02-diagnostic.py` — self-contained `playbin3` mirroring the running app's conda-forge GStreamer env, NOT attached to the running app):**

Read back the running pipeline's selected audio sink. Capture the GStreamer element factory name. Drill through `Gst.Bin` children to find the concrete platform sink behind any wrapper.

**Output:**
```
=== STEP 1: sink identity (PRE-FIX) ===
outer audio-sink factory: autoaudiosink
  child: audiosink-actual-sink-wasapi2 factory: wasapi2sink
```

**Outcome classification:**
- **wasapi2sink** — GStreamer 1.28.x default on Windows; honors `playbin3.volume` natively (per Phase 43 spike findings) — **CONFIRMED**
- ~~directsoundsink — legacy fallback; volume behavior known-quirky~~ (ruled out)
- **autoaudiosink wrapping wasapi2sink** — wrapper resolved at PLAYING; the wrapped `wasapi2sink` decides
- ~~other — flag for D-09-style follow-up~~ (ruled out)

**Implication for Plan 57-04 (glitch fix):**
- `wasapi2sink` honors `playbin3.volume` directly, so the smoothing wrapper writes to `playbin3.volume` (single property surface). Phase 52 EQ ramp template (`musicstreamer/player.py:160-163, 683-685, 746-786`) applies — QTimer-driven 8-tick fade from current → 0 → state-bracket → 0 → current.

---

## D-04 Step 2: `playbin3.volume` Persistence Across NULL→PLAYING (PRE-FIX)

**Method:** Set volume to 0.5 via the property. Read back `pipeline.get_property("volume")` (expected 0.5). Tear down to NULL. Re-set URI. Transition to PLAYING. Read back `pipeline.get_property("volume")` again. Compare. Subjective audible level captured at both points.

**Output:**

| Read time | `pipeline.get_property("volume")` | Audible level (subjective) |
|-----------|-----------------------------------|----------------------------|
| After set 0.5, before NULL | `0.5` | half |
| After NULL→PLAYING rebuild | `1.0` | full |

Verbatim REPL output (Step 2 block):
```
=== STEP 2: playbin3.volume persistence across NULL->PLAYING (PRE-FIX) ===
after set 0.5, volume = 0.5
LISTEN A: audio should be at HALF volume now (hold ~3s)...
after NULL->PLAYING rebuild, volume = 1.0
LISTEN B: post-rebuild — is audio HALF or FULL volume? (hold ~5s)...
```
User attestation for LISTEN B: audible volume increased from half to full across the rebuild — corroborates the `0.5 → 1.0` property reset.

**Outcome classification:**
- **A — property resets to 1.0:** `playbin3.volume` is being lost on NULL→PLAYING rebuild. **Option A wins** (re-apply property). — **CONFIRMED**
- ~~B — property stays 0.5 but audio is full-volume: Sink ignores `playbin3.volume`.~~ (ruled out — property visibly resets to 1.0, no sink-ignores-property signal)
- ~~C — property stays 0.5 and audio is half-volume: bug not reproducible.~~ (ruled out — bug reproduced cleanly first try)

**Implication for D-06:**
- Outcome A confirmed. `playbin3.volume` is dropped on the GStreamer NULL→PLAYING rebuild path. Mechanism: re-apply `self._volume` after every transition to PLAYING.

---

## D-04 Step 3: Slider Mid-Stream Effect (PRE-FIX)

**Method:** Launch the installed app via Start Menu shortcut, start a stream, sweep the volume slider through 100% → 0% → 50% mid-stream and report audible response at each position.

**Output:**

| Slider move | Audible response | `pipeline.get_property("volume")` |
|-------------|------------------|----------------------------------|
| 100% → 0% | silent (responsive) | not captured (no live REPL attached) |
| 0% → 50% | half-loud (responsive) | not captured |

User attestation: "Confirmed what you expected" — slider always responsive mid-stream (100% = full, 0% = silent, 50% = half).

**Outcome classification:**
- **Always responsive** — bug is "post-rebuild only"; Step 2 is the deciding readback for D-06. — **CONFIRMED**
- ~~Always unresponsive~~ (ruled out)
- ~~Partially responsive~~ (ruled out)

**Implication for D-06:**
- Step 3 corroborates Outcome A from Step 2: property writes reach the audio path *during* PLAYING (`wasapi2sink` honors `playbin3.volume`); the bug is the rebuild path losing the property value, not the sink ignoring it.

---

## D-06 Fix-Shape Selection + Glitch Hypothesis

**Decision:** Option A

**D-06 classification:** Step 2 readback (`0.5 → 1.0` after NULL→PLAYING, audible half→full) is decisive; Step 3 (slider always responsive mid-stream) corroborates that the sink honors the property — only the rebuild path drops it.

**Rationale:** Step 2 readback shows `0.5 → 1.0` across NULL→PLAYING with matching audible level change; sink is `wasapi2sink` (honors `playbin3.volume`); therefore Plan 57-03 ships **Option A** (re-apply `self._volume` on every transition to PLAYING) and Plan 57-04 wraps `playbin3.volume` with a Phase 52-style ramp.

**Cross-reference table:**

| D-06 candidate | Hypothesis | Status | Evidence |
|---------------|-----------|--------|----------|
| Option A | `playbin3.volume` resets on NULL→PLAYING (and PAUSED→PLAYING — see scope expansion below) | ✅ confirmed | Step 2 readback `0.5 → 1.0` + audible half→full + Step 3 mid-stream slider always responsive |
| Option B | Sink ignores `playbin3.volume` entirely | ❌ ruled out | Step 3 mid-stream slider IS responsive — `wasapi2sink` honors the property in steady state |
| Hybrid | Both: re-apply AND own the element | ❌ ruled out | Single-mechanism (re-apply on PLAYING) is sufficient given Steps 2 + 3 |

**Glitch-fix hypothesis (Claude's discretion, sink-mediated):**

Sink identified in Step 1 = `wasapi2sink`. Most likely smoothing approach: write to `playbin3.volume` directly (single property surface; sink honors it natively). Approach composes with Plan 57-03 without double-writing — the smoothing wrapper writes `playbin3.volume`, and 57-03's re-apply hook writes `self._volume` to `playbin3.volume`; both target the same property, no element-level fork.

Plan 57-04 picks the exact ramp shape (Phase 52 EQ ramp template at `musicstreamer/player.py:160-163, 683-685, 746-786`).

---

## In-session scope expansion (2026-05-03)

User disclosed a bug surface that CONTEXT D-01 did not capture: **post-rebuffer volume reset** — when the buffer drops mid-stream and `playbin3` auto-recovers (PAUSED→PLAYING on the same URL, no failover, no UI change), the audible volume sometimes jumps to 100% until the user moves the slider. User has observed this on **both Windows and Linux**, contradicting CONTEXT D-01's "Windows-only" framing. Windows hits the surface more frequently (more buffer pressure), but the underlying mechanism is cross-platform.

**Codebase trace:** Every NULL→PLAYING transition in `player.py` funnels through `_set_uri` (line 485-490) — including failover via `_try_next_stream` (line 481) and YouTube/Twitch resolves (`_on_youtube_resolved` line 594). A tail-of-`_set_uri` re-apply would catch all those. **But** the GStreamer-internal PAUSED→PLAYING re-buffer path bypasses `_set_uri` entirely — it's `playbin3` auto-pausing when buffer drops below threshold and auto-resuming when refilled, all without revisiting application code.

**Hook-site decision (re-scopes Plan 57-03):**
- ~~Original scope: one-line re-apply at end of `_set_uri`~~ (insufficient — misses re-buffer recovery)
- **Adopted: bus-message `STATE_CHANGED` handler on the `playbin3` element**, joining the existing `message::error`, `message::tag`, `message::buffering` family at `player.py:134-136`. Re-applies `self._volume` to `playbin3.volume` on every transition to PLAYING (catches NULL→PLAYING, PAUSED→PLAYING, and any other PLAYING-arrival path).

**Scope decision:** Plan 57-03 ships cross-platform (drop "Windows-only" framing). Linux CI regression guard expands from "after `_set_uri`, volume preserved" to "after every PLAYING transition (state-changed), volume preserved" — same shape, broader assertion.

This expansion does not invalidate Steps 1-3 readbacks: the *fix mechanism* (re-apply property) is identical to the original Option A; only the *hook site* (bus-message vs. `_set_uri` tail) and *scope* (cross-platform vs. Windows-only) widened. Plan 57-04's smoothing target (`playbin3.volume`) is unchanged.

---

## Sign-off

- **Diagnostic complete:** 2026-05-03
- **D-06 decision recorded:** Option A (bus-message `STATE_CHANGED` hook site, cross-platform scope)
- **Plan 57-03 unblocked:** yes — re-scope to bus-message hook + cross-platform
- **Plan 57-04 unblocked:** yes — `wasapi2sink` honors `playbin3.volume`; smoothing wrapper writes to that property, Phase 52 ramp template applies
