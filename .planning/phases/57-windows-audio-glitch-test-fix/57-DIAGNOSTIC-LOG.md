# Phase 57 / WIN-03 — Win11 VM Audio Diagnostic Log

**Started:** _TBD: yyyy-mm-dd_
**Driver:** Linux orchestrator (interactive paste-back mode); user executes PowerShell + Python on Win11 VM
**Goal:** Capture the three D-04 readbacks (sink identity + `playbin3.volume` persistence across NULL→PLAYING + slider mid-stream effect), so Plan 57-03 knows whether to ship Option A (re-apply property), Option B (explicit `volume` element chained with EQ inside a `Gst.Bin`), or a hybrid; and so Plan 57-04 picks a glitch-smoothing approach that composes with the chosen volume fix.

---

## Pre-flight: VM environment readiness

| Check | Result | Notes |
|-------|--------|-------|
| Win11 22H2+ | _TBD_ | Same VM used in Phase 43 / 44 / 56-03 spike rig |
| Conda env active | _TBD_ | env name (Phase 56-03 used `spike`) |
| Fresh installer artifact | _TBD_ | path on VM, build date, byte size |
| One playable HTTP stream available | _TBD_ | e.g., SomaFM Drone Zone (no DI.fm premium needed for WIN-03 — different surface from Phase 56) |
| Two PowerShell windows ready | self-managed | one for app, one for python introspection |

**Status:** _TBD: READY / BLOCKED_

---

## D-04 Step 1: Audio Sink Identity (PRE-FIX)

**Method (interactive Python REPL on the VM, with the app launched and playing a stream — see Task 2 of Plan 57-02 for the exact snippet):**

Read back the running pipeline's selected audio sink. Capture the GStreamer element factory name (e.g., `wasapi2sink`, `directsoundsink`, `autoaudiosink`).

**Output:**
```
_TBD: paste the readback verbatim_
```

**Outcome classification:**
- **wasapi2sink** — GStreamer 1.28.x default on Windows; honors `playbin3.volume` natively (per Phase 43 spike findings)
- **directsoundsink** — legacy fallback; volume behavior known-quirky
- **autoaudiosink** wrapping one of the above — same final element decides
- **other** — flag for D-09-style follow-up

**Implication for Plan 57-04 (glitch fix):**
- _TBD: which sink → which smoothing wrapper shape (sink-volume mute window vs `playbin3.volume`-side fade vs `volume`-element ramp)._

---

## D-04 Step 2: `playbin3.volume` Persistence Across NULL→PLAYING (PRE-FIX)

**Method:** Set volume to 0.5 via the slider. Read back `pipeline.get_property("volume")` (expected 0.5). Press Pause (NULL). Press Resume (rebuild → PLAYING). Read back `pipeline.get_property("volume")` again. Compare.

**Output:**

| Read time | `pipeline.get_property("volume")` | Audible level (subjective) |
|-----------|-----------------------------------|----------------------------|
| After slider → 0.5, before pause | _TBD_ | _TBD_ |
| After Resume (post-rebuild) | _TBD_ | _TBD_ |

**Outcome classification:**
- **A — property resets to 1.0:** `playbin3.volume` is being lost on NULL→PLAYING rebuild. **Option A** wins (one-line re-apply at end of `_set_uri`).
- **B — property stays 0.5 but audio is full-volume:** Sink ignores `playbin3.volume`. **Option B** wins (explicit `volume` GstElement chained with EQ in a `Gst.Bin`, occupying the single `audio-filter` slot).
- **C — property stays 0.5 and audio is half-volume:** Bug not reproducible on this run. **Re-test** with a longer pause hold; if still not reproducible, escalate as "intermittent — defer".

**Implication for D-06:**
- _TBD: which classification fired._

---

## D-04 Step 3: Slider Mid-Stream Effect (PRE-FIX)

**Method:** While playing, move the slider 100% → 0% → 50%. Confirm whether the audible level changes immediately at each move.

**Output:**

| Slider move | Audible response | `pipeline.get_property("volume")` |
|-------------|------------------|----------------------------------|
| 100% → 0% | _TBD: silent / unchanged / partial_ | _TBD_ |
| 0% → 50% | _TBD: half-loud / silent / unchanged_ | _TBD_ |

**Outcome classification:**
- **Always responsive:** bug is "post-rebuild only" — Step 2 will be the deciding readback for D-06.
- **Always unresponsive:** property writes never reach the audio path — strengthens Option B (the sink isn't honoring `playbin3.volume`).
- **Partially responsive:** flag and follow up; rare.

**Implication for D-06:**
- _TBD: confirm or contradict the prior from Step 2._

---

## D-06 Fix-Shape Selection + Glitch Hypothesis

**Decision:** _TBD: Option A / Option B / hybrid_

**D-06 classification:** _TBD: which evidence path picked it_

**Rationale (one sentence):** _TBD_

**Cross-reference table:**

| D-06 candidate | Hypothesis | Status | Evidence |
|---------------|-----------|--------|----------|
| Option A | `playbin3.volume` resets on NULL→PLAYING (Win-only) | _TBD: confirmed / ruled out_ | Step 2 readback |
| Option B | Sink ignores `playbin3.volume` entirely | _TBD: confirmed / ruled out_ | Step 2 + Step 3 readbacks |
| Hybrid | Both: re-apply AND own the element | _TBD: warranted? unlikely_ | (only if Step 2 = A and Step 3 = "always unresponsive") |

**Glitch-fix hypothesis (Claude's discretion, sink-mediated):**

Sink identified in Step 1 = _TBD_. Most likely smoothing approach: _TBD_.
Approach must compose with the chosen volume fix without double-writing the volume property:
- If Option A ships: smoothing wrapper writes to `playbin3.volume`.
- If Option B ships: smoothing wrapper writes to the new `volume` GstElement (NOT to `playbin3.volume`, which would be unconnected).

Plan 57-04 picks the exact ramp shape (Phase 52 EQ ramp template at `musicstreamer/player.py:160-163, 683-685, 746-786`).

---

## Sign-off

- **Diagnostic complete:** _TBD: yyyy-mm-dd_
- **D-06 decision recorded:** _TBD: Option A / Option B / hybrid_
- **Plan 57-03 unblocked:** _TBD: yes / no_
- **Plan 57-04 unblocked:** _TBD: yes / no_
