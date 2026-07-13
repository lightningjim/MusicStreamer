---
phase: 93-buffer-monitor-followup
verified: 2026-06-15T00:00:00Z
status: closed
score: 3/3 success criteria satisfied (closed-via-deviation + residual no-action)
closure_model: deviation-plus-residual
condition_fired: true
triggers_fired: [long-event-recurrence, very-long-recovery, network-cause-hint]
overrides_applied: 0
nyquist_compliant: true
human_verification:
  - test: "Post-DVR-fix buffer-events.log re-monitor (~/.local/share/musicstreamer/buffer-events.log)"
    expected: "After commit f716f083 (2026-06-12), YouTube live 'lofi hip hop radio' long underruns (min_percent=0, >1s) cease; generic/SomaFM path holds steady (Phase 84 tuning not regressed)."
    result: "CONFIRMED. Zero YouTube long min_percent=0 recovered underruns from 2026-06-12 10:28 through 2026-06-15. SomaFM/Drone Zone network-hint cluster did not recur after 2026-05-30. User confirms 'working after a couple weeks.'"
---

# Phase 93: BUFFER-MONITOR Follow-Up — Verification Report

**Phase Goal:** Resolve any of Phase 84-VERIFICATION.md's 3 Follow-Up Triggers that fire during the v2.2 development window — diagnose, tune, or formally close as "no action".

**Verified:** 2026-06-15
**Status:** closed (condition fired; resolved via out-of-band fix + residual no-action close)
**Re-verification:** No — initial verification.

> **Origin note.** Phase 93 was a CONDITIONAL roadmap placeholder (no directory until now). The qualifying work — the YouTube live-HLS DVR-seek fix (commit `f716f083`, 2026-06-12) — was done out-of-band ("on the side"), not under a Phase 93 plan. This record is a **retroactive closure** that maps that work, plus a fresh re-read of `buffer-events.log`, onto Phase 93's three success criteria. It is a deviation-with-residual close, **not** a claim that the side work was a planned Phase 93 execution.

---

## Condition Check — Did Phase 93 Fire?

**YES — all three Follow-Up Triggers fired inside the 2-week post-Phase-84 monitor window.**

Monitor window: Phase 84 ship ≈ **2026-05-24** (84-VERIFICATION.md written) / version rollup 2026-05-25 → window ≈ **2026-05-24 → 2026-06-07**.
Evidence source: `~/.local/share/musicstreamer/buffer-events.log` (native install; the Flatpak data-dir log is empty/0-byte as of 2026-06-05 and contributes no evidence).
Harvest-week baseline (from 84-VERIFICATION.md): 12 events / 5 long (2 YouTube + 3 SomaFM), max magnitude 7389 ms.

Thresholds are **verbatim from 84-VERIFICATION.md §Follow-Up Triggers / CONTEXT.md D-13** — not paraphrased.

| Trigger | Threshold | In-window result | Fired? |
|---|---|---|---|
| Long-event recurrence | ≥3 long events (>1s) with `min_percent=0` | **14** long recovered min0 events (13 YouTube, 1 SomaFM); count then explodes to hundreds 06-08→06-12 (all YouTube "lofi hip hop radio") | ✅ FIRED (decisively) |
| Very-long recovery | any `recovered` event >10s | **4** in-window (e.g. 2026-05-29 SomaFM 26 555 ms; 2026-06-06 YouTube 11 492 ms) | ✅ FIRED |
| Network cause-hint | ≥1 `cause_hint=network` event | **3** — all SomaFM/Drone Zone (05-24, 05-29, 05-30); zero YouTube; none after 05-30 | ✅ FIRED |

Because the condition fired, Phase 93 legitimately **opens** — this is NOT a "never fired → skip" close.

---

## Diagnosis — Two Independent Signals

The fired triggers decompose into two unrelated root causes:

**1. YouTube live-edge starvation (the dominant signal — Triggers 1 & 2).**
The overwhelming mass of long `min_percent=0` underruns — 13 of 14 in-window, then hundreds across 06-08→06-12 — are all the YouTube live station "lofi hip hop radio". Root cause is **NOT a Phase 84 regression**: `hlsdemux2` owns its own segment-download buffer (`max-buffering-time`) that is independent of `playbin3.buffer-duration`, so the Phase 84 30→60→120s growth ladder never reached it. With no `EXT-X-HOLDBACK`, playback tracks ~6s behind the live edge and any CDN hiccup ≥2s drains to 0. See memory `[[hlsdemux2-owns-independent-segment-buffer]]`.

**2. SomaFM/Drone Zone transient network drops (Trigger 3).**
All 3 `cause_hint=network` events are Drone Zone, clustered 2026-05-24 → 2026-05-30, all `outcome=recovered`, none since. These are transient CDN/network events, not a buffer-tuning regression. The Phase 84 buffer-duration tuning holds steady for the generic/SomaFM path (user-confirmed: "the problem addressed in 84 seems to be working after a couple weeks").

---

## Success Criteria

### SC #1 — Document which triggers fired, with timestamps + evidence; note non-fired as no-action.
**SATISFIED.** All three fired (table above) with in-window counts and representative timestamps drawn from `buffer-events.log`. No trigger was non-fired, so no "no action required" notation applies at the trigger level.

### SC #2 — Outcome is one of: (a) adaptive-buffer regression fix, (b) 30→60→120s ladder tuning, (c) explicit "no action — closed".
**SATISFIED VIA DEVIATION + RESIDUAL.** The outcome is a hybrid that does not map cleanly to a single sketched option — recorded here as an explicit deviation:

- **Primary (YouTube signal) → out-of-band fix, commit `f716f083` (2026-06-12).** One-shot 30s DVR seek-back into YouTube's ~7200s DVR window on first PLAYING for a live stream, plus `hlsdemux2 max-buffering-time/high-watermark` set in `_on_deep_element_added`, plus `_BufferUnderrunTracker.disarm_for_seek()` to suppress the post-seek re-fill from being logged as a false underrun. **This is a NEW mechanism — a deviation from outcomes (a)/(b)/(c).** It is neither reconnect-on-stall, nor 30→60→120 ladder-tuning, nor no-action; it is a live-edge DVR-seek specific to the actual root cause.
- **Residual (SomaFM/network signal) → outcome (c) "no action — closed".** Transient CDN/network, all recovered, no recurrence since 2026-05-30. Baseline preserved.
- **Reconnect-on-stall** (the originally-sketched Phase 93 scope, Phase 78 deferred item) → **NOT implemented and NOT needed.** The dominant signal had a more specific root cause better addressed by the DVR seek. Reconnect-on-stall remains parked as a deferred item.

### SC #3 — If a fix ships, Phase 84 D-11 acceptance test (12-event harvest replay) re-runs clean post-fix; else monitor concludes with baseline preserved.
**SATISFIED.** A fix shipped, so the D-11 path applies: `tests/test_player_buffer_growth.py` + `tests/test_player_buffer.py` (the D-11 30→60→120s state machine) re-run clean post-fix — **22 passed** (2026-06-15, `.venv/bin/python`). `disarm_for_seek()` affects only live-runtime logging, not the deterministic state machine, so D-11 is unaffected. The DVR-fix commit itself reported 196 tests passing.

**Post-fix monitor evidence:** from 2026-06-12 10:28 (fix commit) through 2026-06-15, **zero** YouTube long `min_percent=0` recovered underruns in `buffer-events.log` (only `min_percent=1` short preroll blips remain). The fired triggers are resolved in real-world daily use.

---

## Honest Caveats

- **Timing.** The DVR fix landed 2026-06-12, just **after** the formal 2-week window closed (~06-07). The triggers fired *within* the window; the fix is a delayed but direct response to them. Acceptable.
- **Evidence is native-install only.** The Flatpak data-dir `buffer-events.log` is empty; all trigger evidence is from `~/.local/share/musicstreamer/buffer-events.log`.
- **Scope.** This close credits the YouTube slice (fixed) and the SomaFM/network slice (no-action). No generic reconnect-on-stall capability was added; if a future non-YouTube long-underrun cluster appears with no network hint, reopen the reconnect-on-stall evaluation.

---

## Required Artifacts

| Artifact | Status |
|---|---|
| Fix commit | `f716f083` — `fix(player): eliminate YouTube live HLS buffer underruns via DVR seek` (2026-06-12) |
| Trigger evidence | `~/.local/share/musicstreamer/buffer-events.log` (in-window 05-24→06-07; post-fix 06-12→06-15) |
| D-11 regression | `tests/test_player_buffer_growth.py` + `tests/test_player_buffer.py` — 22 passed (2026-06-15) |
| Canonical reference | `.planning/milestones/v2.1-phases/84-bug-09-commit-b-buffer-tuning-behavior-fix-reframed-from-str/84-VERIFICATION.md` |
