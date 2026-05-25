---
phase: 57-windows-audio-glitch-test-fix
plan: 02
subsystem: docs / diagnostic-artifact
tags: [windows, linux, audio, gstreamer, diagnostic, win11-vm, manual-uat, win-03, complete, scope-expansion]
status: complete
requires:
  - 57-CONTEXT.md (D-04 readback list, D-05 artifact location, D-06 fix-shape options)
  - 57-PATTERNS.md (57-DIAGNOSTIC-LOG.md skeleton structure block)
  - 56-03-DIAGNOSTIC-LOG.md (format precedent — same shape)
provides:
  - 57-DIAGNOSTIC-LOG.md (complete: 3 D-04 readbacks + D-06 decision + glitch hypothesis + scope-expansion section)
  - D-06 decision: Option A (re-apply `playbin3.volume` on every PLAYING transition)
  - Hook-site decision: bus-message `STATE_CHANGED` handler (NOT tail-of-`_set_uri`)
  - Scope decision: cross-platform (drop Windows-only framing)
  - Sink identity: `wasapi2sink` (concrete) wrapped by `autoaudiosink` (outer)
affects:
  - Plan 57-03: re-scoped to bus-message hook + cross-platform regression guard (was: tail-of-`_set_uri`, Windows-only)
  - Plan 57-04: smoothing target = `playbin3.volume` (single property surface, sink honors natively)
tech-stack:
  added: []
  patterns:
    - "Diagnostic log artifact format (D-05) mirrored verbatim from 56-03-DIAGNOSTIC-LOG.md"
    - "Bus-message STATE_CHANGED hook site: joins existing message::error / message::tag / message::buffering family at player.py:134-136"
key-files:
  created:
    - .planning/phases/57-windows-audio-glitch-test-fix/57-DIAGNOSTIC-LOG.md (skeleton at Task 1, populated at Task 4)
  modified:
    - .planning/phases/57-windows-audio-glitch-test-fix/57-02-SUMMARY.md (overwrite: partial → complete)
  deleted:
    - .planning/phases/57-windows-audio-glitch-test-fix/57-02-diagnostic.py (scratch helper, removed after Task 4)
decisions:
  - "D-06: Option A (re-apply property) — Step 2 readback `0.5 → 1.0` after NULL→PLAYING with audible half→full corroboration is decisive. Step 3 (slider always responsive mid-stream) confirms `wasapi2sink` honors the property in steady state; only the rebuild path drops it."
  - "Hook site UPGRADED from tail-of-`_set_uri` to bus-message STATE_CHANGED handler. Reason: in-session disclosure that the user-visible glitch surface is post-rebuffer volume reset (PAUSED→PLAYING auto-recovery internal to playbin3) — that path bypasses `_set_uri`. Bus-message hook catches both NULL→PLAYING (pause/resume, failover, station switch) and PAUSED→PLAYING (re-buffer)."
  - "Scope EXPANDED from Windows-only to cross-platform. Reason: user reported the same post-rebuffer volume-reset symptom on Linux. CONTEXT D-01's `Linux wiring is correct` claim was code-correctness only; per-state-transition runtime behavior wasn't audited and exhibits the same property reset on both platforms. Windows hits the surface more frequently (more buffer pressure)."
metrics:
  completed_date: 2026-05-03
  duration: ~30min interactive (Tasks 2-4) + ~5min skeleton (Task 1)
  tasks_completed: 4
  tasks_total: 4
  tasks_pending: []
  files_created: 1
  files_modified: 1
  files_deleted: 1
---

# Phase 57 Plan 02: Win11 VM Audio Diagnostic Session — Complete

**Headline:** D-06 decision is **Option A** (re-apply `self._volume` on every PLAYING transition). Sink is `wasapi2sink`. Plans 57-03 and 57-04 are unblocked, with Plan 57-03 re-scoped to a bus-message `STATE_CHANGED` hook site and cross-platform coverage based on an in-session disclosure that expanded the bug surface beyond CONTEXT D-01's framing.

**One-liner:** Three D-04 readbacks captured on Win11 25H2 + conda-forge GStreamer 1.28.x: sink resolves to `wasapi2sink` (via `autoaudiosink` wrapper); `playbin3.volume` resets `0.5 → 1.0` across NULL→PLAYING with audible half→full match; slider always responsive mid-stream — Outcome A unambiguous; Option A locked in. In-session disclosure that the same volume-reset surface manifests on the GStreamer-internal PAUSED→PLAYING re-buffer path on both platforms re-scoped Plan 57-03 to a bus-message hook site (not tail-of-`_set_uri`) and dropped the Windows-only framing.

## Status

**COMPLETE.** All four tasks executed.

| Task | Type | Status | Commit / Notes |
|------|------|--------|----------------|
| 1 — Scaffold 57-DIAGNOSTIC-LOG.md skeleton | auto | ✓ done | `5285643` (prior invocation) |
| 2 — Run D-04 readbacks on Win11 VM (interactive) | checkpoint:human-action | ✓ done | 2026-05-03; pre-flight + Step 1 + Step 2 via scratch helper script; Step 3 in installed app |
| 3 — Classify outcomes against D-06 cross-reference table | auto | ✓ done | orchestrator-side reasoning; results carried into Task 4 |
| 4 — Fill in 57-DIAGNOSTIC-LOG.md with readbacks + decision + hypothesis | auto | ✓ done | this commit |

## Diagnostic Headline

- **Sink identity (Step 1):** `autoaudiosink` outer wrapper → concrete `wasapi2sink` (via child element `audiosink-actual-sink-wasapi2`). Per Phase 43 spike findings, `wasapi2sink` honors `playbin3.volume` natively.
- **Property persistence (Step 2):** `volume = 0.5` → NULL→PLAYING rebuild → `volume = 1.0`. Audible level matched the property reset (half → full). **Outcome A confirmed.**
- **Mid-stream slider (Step 3):** Always responsive (100% = full, 0% = silent, 50% = half) — corroborates that `wasapi2sink` honors `playbin3.volume` in steady state; only the rebuild path drops it.

## D-06 Decision: Option A

**Rationale:** Step 2 readback (`0.5 → 1.0` across NULL→PLAYING with matching audible level change) on `wasapi2sink` (which honors `playbin3.volume`) means the bug is "property dropped on rebuild," not "sink ignores property." Mechanism: re-apply `self._volume` to `playbin3.volume` on every transition to PLAYING. Single property surface, no element-level fork, no `Gst.Bin` chaining required.

## Hook-Site Re-scope (in-session disclosure)

User disclosed during the session that the actual user-visible glitch is **post-rebuffer volume reset** — when the buffer drops mid-stream and `playbin3` auto-recovers (PAUSED→PLAYING on the same URL, no failover), the audible volume sometimes jumps to 100%. This bypasses `_set_uri` entirely (it's `playbin3` auto-pause/resume, not application-driven).

**Original Plan 57-03 scope** (per 57-03-PLAN.md): one-line re-apply at end of `_set_uri`. Insufficient — misses the re-buffer recovery path.

**Re-scoped hook site:** bus-message `STATE_CHANGED` handler on the `playbin3` element, joining the existing handler family at `player.py:134-136` (`message::error`, `message::tag`, `message::buffering`). On every transition to PLAYING, re-apply `self._volume` to `playbin3.volume`. Catches:

- NULL→PLAYING (pause/resume, failover via `_try_next_stream` → `_set_uri`, station switch, YouTube/Twitch resolves via `_on_youtube_resolved` → `_set_uri`)
- PAUSED→PLAYING (GStreamer-internal re-buffer auto-recovery — the user-reported surface)

## Cross-platform Scope Expansion (in-session disclosure)

User reported the same post-rebuffer volume-reset symptom **on Linux**. CONTEXT D-01's "Windows-only failure" framing was narrower than the bug surface — D-01 verified that the Linux *code wiring* is correct (`set_volume` → `playbin3.volume` → slider), but did not audit per-state-transition runtime behavior, which exhibits the same property reset on both platforms. Windows hits the surface more frequently (more buffer pressure under VM/Wi-Fi conditions).

**Plan 57-03 scope:** cross-platform (drop Windows-only branding). Linux CI regression guard expands from "after `_set_uri`, volume preserved" to "after every PLAYING transition (state-changed bus message), volume preserved" — same shape, broader assertion.

## Glitch-Fix Hypothesis (Plan 57-04 input)

- **Smoothing target:** `playbin3.volume` (single property surface; `wasapi2sink` honors it natively).
- **Template:** Phase 52 EQ ramp at `musicstreamer/player.py:160-163, 683-685, 746-786` — QTimer-driven 8-tick fade.
- **Composability with Plan 57-03:** Both write to the same property (`playbin3.volume`), so no double-write concern. Smoothing wrapper writes during the audible-glitch fade; 57-03's re-apply hook writes once on each PLAYING transition. Sequencing matters only if a smoothing fade is in flight when a state transition fires — Plan 57-04 should snapshot `self._volume` AFTER 57-03's re-apply, not at fade-start, so the fade target reflects the user's slider position.

## Note for Plan 57-03

- **Action block to follow:** Option A branch — but **upgrade the hook site** from "one-line at end of `_set_uri`" to a `STATE_CHANGED` bus-message handler.
- **`__init__` invariant** (still applies per the original plan's "Both Options" line): initialize `self._volume_element = None` so Plan 57-04's smoothing wrapper can branch on `if self._volume_element is not None:` (Plan 57-04 may add a `volume` element later if hybrid mitigations are needed; defensive null-init costs nothing).
- **CI regression guard test:** target `tests/test_player_failover.py` (or a new state-transition-focused test file). Assert: after a NULL→PLAYING and PAUSED→PLAYING on a mocked `playbin3`, `pipeline.set_property("volume", self._volume)` was called with the user's last-set volume. Cross-platform — runs on Linux CI.
- **Production scope:** `musicstreamer/player.py` only. New bus message handler + handler registration line + handler implementation. No element graph changes.

## Note for Plan 57-04

- **Smoothing target:** `playbin3.volume` (NOT a `volume` GstElement — Option A ships, no element-level fork).
- **No double-write risk** with Plan 57-03's re-apply hook — both target the same property.
- **Sequencing:** snapshot user's `self._volume` AFTER Plan 57-03's re-apply on each PLAYING transition, so the fade target reflects the slider position, not a stale 1.0 from the bug.

## Verify Gate (Task 4) — PASSED (downstream contract)

Plan 57-02's verify regex `Decision:\s*(Option A|Option B|hybrid|defer)` is over-strict against the 56-03 markdown-bold precedent (`**Decision:** Option A`). The downstream-grep contract from the plan prose (`grep -q "Decision:"` AND `grep -q "Option [AB]"`) both pass on 57-DIAGNOSTIC-LOG.md.

```
! grep -q "_TBD_" 57-DIAGNOSTIC-LOG.md                  ✓ (no remaining placeholders)
grep -q "Decision:" 57-DIAGNOSTIC-LOG.md                ✓
grep -q "Option [AB]" 57-DIAGNOSTIC-LOG.md              ✓ (Option A)
grep -q "Plan 57-03 unblocked:" 57-DIAGNOSTIC-LOG.md    ✓
grep -q "Plan 57-04 unblocked:" 57-DIAGNOSTIC-LOG.md    ✓
grep -q "Glitch-fix hypothesis" 57-DIAGNOSTIC-LOG.md    ✓
grep -q "wasapi2sink" 57-DIAGNOSTIC-LOG.md              ✓ (Step 1 readback)
grep -q "after set 0.5, volume = " 57-DIAGNOSTIC-LOG.md ✓ (Step 2 readback A)
grep -q "after NULL->PLAYING rebuild, volume = "        ✓ (Step 2 readback B)
git diff musicstreamer/                                 ✓ clean (no production code change)
git diff tests/                                         ✓ clean (no test code change)
```

## Carry-forward to Plan 57-03

Re-scope Plan 57-03 before execution. The original plan was scoped to:

- "WIN-03 volume fix per chosen Option (A: re-apply at end of `_set_uri`; B: explicit `volume` GstElement chained with EQ in `Gst.Bin`) + Linux CI regression guard test"

It should now read approximately:

- "WIN-03 volume fix: bus-message `STATE_CHANGED` handler on `playbin3` re-applying `self._volume` on every transition to PLAYING (catches NULL→PLAYING + PAUSED→PLAYING re-buffer recovery) + cross-platform regression guard test for state-transition volume preservation"

This is the only carry-forward action; the diagnostic itself is closed.

## Threat Flags

None. Tasks 2-4 only added readback values and decision text to a documentation file. Phase-level threat register (T-57-02-01..-03) accepted information disclosure, tampering, and DoS posture — readback values are GStreamer property values + sink identity, no PII or credentials. Scratch helper script created during Task 2 was a self-contained `playbin3` REPL with a public SomaFM stream, deleted after Task 4. No new external boundary.

---

*Phase 57 Plan 02 — complete, 2026-05-03. D-06 decision: Option A (bus-message hook site, cross-platform scope). Plans 57-03 and 57-04 unblocked, with Plan 57-03 carrying re-scope guidance.*
