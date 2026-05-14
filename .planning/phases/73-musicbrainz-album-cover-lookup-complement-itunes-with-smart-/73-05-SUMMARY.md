---
phase: 73-musicbrainz-album-cover-lookup-complement-itunes-with-smart-
plan: 05
subsystem: testing
tags: [uat, manual-verification, phase-gate, wayland-dpr1, cover-art-source]

# Dependency graph
requires:
  - phase: 73
    provides: |
      Plan 01 (schema + Station.cover_art_source field + Wave 0 RED fixtures),
      Plan 02 (cover_art_mb.py worker — 1 req/sec gate + User-Agent + score≥80
      + CAA fetch + tag→genre handoff), Plan 03 (source-aware router in
      cover_art.py with iTunes/MB/Auto modes + ART-MB-09 fall-through),
      Plan 04 (EditStationDialog QComboBox + settings_export ZIP round-trip
      with Pitfall 9 forward-compat + NowPlayingPanel pass-through).
      All 16 ART-MB-NN automated tests are GREEN before Plan 05 runs.
provides:
  - 73-UAT-SCRIPT.md (3 manual-only scenarios; structured PASS/FAIL/notes
    template; Wayland DPR=1.0 deployment target locked)
  - Manual-verification surface complementary to the 16 ART-MB-NN
    automated tests; together they form the full Phase 73 verification
    contract per VALIDATION.md
  - Pending-UAT marker for the orchestrator's verify-work step
affects: [73-verify-work (downstream — runs auto-suite then prompts user
  through 73-UAT-SCRIPT.md), future Phase 73.1 gap-closure if any scenario
  fails (Scenario B failure → CAA variant 250→500 bump; Scenario A failure
  → MB pipeline regression; Scenario C failure → settings_export forward-
  compat regression)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "UAT script structure mirrors 72-UAT-SCRIPT.md: frontmatter (phase,
      plan, deployment) → How to run → Scenario H2 per row → Pass / Fail /
      Notes blocks per scenario → Failure notes → Overall PASS/FAIL marker."
    - "Manual-Only Verifications row from VALIDATION.md becomes one scenario;
      one-to-one mapping. Each scenario references its source row by exact
      behavior name."
    - "Auto-chain pass-through pattern: a non-autonomous plan whose
      checkpoint is satisfied by landing the artifact + a 'pending user'
      SUMMARY marker; the actual user-driven run is deferred to the
      orchestrator's verify-work step."

key-files:
  created:
    - .planning/phases/73-musicbrainz-album-cover-lookup-complement-itunes-with-smart-/73-UAT-SCRIPT.md
      (348 lines; 3 scenarios; mirrors 72-UAT-SCRIPT.md idiom)
  modified: []

key-decisions:
  - "Auto-chain pass-through: Task 2 (checkpoint:human-verify) is satisfied
    by writing this SUMMARY with status AUTOMATED VERIFICATION COMPLETE /
    MANUAL UAT PENDING USER. Did NOT block the orchestrator chain on a
    question that cannot be answered from an executor agent (the verdict
    requires a live human running the live app on a real Wayland session
    against a real MusicBrainz endpoint)."
  - "UAT script structure copies 72-UAT-SCRIPT.md verbatim where possible
    (How-to-run preamble, Scenario H2 anatomy, Pass criteria checkbox,
    Overall PASS/FAIL marker for orchestrator grep). Tester consistency
    > novelty."
  - "Scenario B includes a side-by-side iTunes baseline comparison step.
    Without an iTunes reference the user has no concrete benchmark for
    'no visible pixelation' — the iTunes 160x160 native render IS the
    benchmark, and switching the same station to iTunes only -> replay
    -> compare produces it in 30 seconds."
  - "Scenario C uses XDG_DATA_HOME=/tmp/phase73-uat-profile rather than a
    second OS user account: zero-cost on Linux, recoverable by rm -rf,
    no system-admin involvement. Bonus: also tests the optional unzip+
    jq sanity check on the exported JSON payload independent of the
    import path."
  - "Optional bonus checks (Lucene-special-char ICY, rapid ICY churn for
    1-req/sec gate runtime confirmation) listed but NOT required for
    Pass — keeps the wall-clock estimate honest at ~20 min and avoids
    Pass criteria creep."

patterns-established:
  - "Pass criteria checkbox + Fail criteria explicit list + Notes box:
    every scenario follows this triad. Removes ambiguity from the
    user's verdict capture."
  - "Pre-conditions block per scenario: hard-locks the assumptions a
    later auditor could otherwise mis-read (e.g. Scenario A's
    'iTunes path already works — if it does not, that is a Phase 70
    regression, not a Phase 73 UAT failure' disclaimer)."

requirements-completed: []

# Metrics
duration: ~5min
completed: 2026-05-13
---

# Phase 73 Plan 05: UAT script landed — manual verification pending Summary

**Three-scenario manual UAT script (73-UAT-SCRIPT.md) landed; the 16
automated ART-MB-NN tests are GREEN and the manual verification surface is
now staged for the user to run via `/gsd-verify-work 73`.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-14T01:02:36Z
- **Completed:** 2026-05-14T01:04:33Z
- **Tasks:** 2 (Task 1 autonomous + Task 2 auto-chain checkpoint pass-through)
- **Files created:** 1 (`73-UAT-SCRIPT.md`)
- **Files modified:** 0

## Accomplishments

- **`73-UAT-SCRIPT.md` written and committed** (348 lines, 25 H2 sections):
  - **Scenario A** — Real MB cover renders for a real station. Steps:
    launch app, play a station with strong `Artist - Title` ICY
    (SomaFM Indie Pop Rocks / DI.fm Vocal Trance), verify Auto-mode
    iTunes baseline first, open EditStationDialog, verify the new
    combo's exact shape (label, 3 entries in order, non-editable),
    flip to `MusicBrainz only`, save, replay, observe cover renders.
    Try 2–3 tracks before declaring FAIL (score<80 misses are valid).
  - **Scenario B** — CAA-250 quality at 160×160. With station set to
    MB-only and a cover rendered, compare visually against an iTunes
    160×160 baseline (same station → iTunes only → replay → compare).
    Pass if no visible pixelation or compression artifacts beyond the
    iTunes baseline. Fail → recommends Phase 73.1 single-line bump
    of CAA variant 250 → 500 in `cover_art_mb.py`.
  - **Scenario C** — Cross-profile ZIP round-trip. Set 3 stations to
    Auto / iTunes only / MB only respectively; export ZIP from active
    profile; launch fresh profile via `XDG_DATA_HOME=/tmp/phase73-uat-profile`;
    import ZIP; verify EditStationDialog combo on each station reflects
    the source-profile value. Optional `unzip -p | python -c json.load`
    sanity check confirms the export-side write independent of import.
- **Optional bonus checks** included for: Lucene-special-char ICY
  (exercises T-73-01 mitigation in practice), rapid ICY churn
  (runtime confirmation of the 1-req/sec gate).
- **Wayland DPR=1.0 deployment target locked** at the top of the script
  per the `project_deployment_target` memory note. Tester confirms
  `$XDG_SESSION_TYPE == wayland` before running.
- **Pass criteria + Fail criteria + Notes triad** for every scenario —
  unambiguous verdict capture; orchestrator can grep
  `**Overall:** PASS` / `**Overall:** FAIL` / `**Overall:** PENDING`
  for the gate signal.

## Task Commits

1. **Task 1: Write 73-UAT-SCRIPT.md** — `aa80710` (docs)
2. **Task 2: Auto-chain checkpoint pass-through** — pending the final
   metadata commit below (no production-code commit; checkpoint
   satisfied by writing this SUMMARY)

**Plan metadata commit:** (filed at end of this plan; carries
73-05-SUMMARY.md, STATE.md, ROADMAP.md, REQUIREMENTS.md if touched)

## Files Created/Modified

- `.planning/phases/73-musicbrainz-album-cover-lookup-complement-itunes-with-smart-/73-UAT-SCRIPT.md`
  — 348-line, 25-H2-section manual UAT script. Structured: frontmatter
  (phase, plan, deployment=linux-wayland-gnome-shell-dpr1.0, status=PENDING),
  How-to-run preamble, three Scenario H2 blocks (A/B/C), Optional bonus
  checks block, Failure notes block, Overall PASS/FAIL marker at the
  bottom for orchestrator grep.

## Decisions Made

- **Auto-chain pass-through honored.** The orchestrator's runtime context
  explicitly said: in auto-chain mode, do NOT attempt a live UAT inside
  the executor agent. Task 2 is therefore satisfied by writing this
  SUMMARY with the AUTOMATED COMPLETE / MANUAL PENDING status; the
  actual user-driven UAT is deferred to `/gsd-verify-work 73`. Returning
  cleanly here keeps the orchestrator chain unblocked.
- **UAT structure mirrors 72-UAT-SCRIPT.md.** The Phase 72 script is the
  most recent precedent in this codebase; the tester is the same user
  who ran the Phase 72 UAT in May 2026 (the file's `## Overall: PASS`
  marker confirms). Reusing the H2 anatomy, the `[ ]` checkbox idiom for
  pass criteria, and the `**Overall:** PASS` grep gate at the bottom
  removes cognitive overhead — the user knows what to do.
- **Three scenarios, not four.** VALIDATION.md's "Manual-Only Verifications"
  table has exactly three rows; the UAT script has exactly three scenarios.
  No bonus invented scenarios that would inflate the wall-clock and
  blur the Pass-criteria audit trail.
- **CAA failure path documented in Scenario B but NOT auto-fixed.**
  CONTEXT D-11 explicitly says variant choice is planner's discretion;
  if the user reports pixelation, the fix is a single-line bump of
  `/front-250` → `/front-500` in `cover_art_mb.py` to be filed as a
  Phase 73.1 gap-closure plan. The UAT script does not pre-empt the
  user's judgment.

## Deviations from Plan

None — Task 1 followed `<action>` verbatim (required sections,
≥80-line floor, ≥4 H2 sections, references all three Manual-Only
Verifications by exact behavior name). Task 2's auto-chain pass-through
behavior was explicitly instructed in the runtime context (`<runtime_context>`
block in the executor prompt), so writing the SUMMARY with a PENDING
manual-UAT marker rather than blocking on a checkpoint is the
documented expected behavior in this mode, not a deviation.

## Issues Encountered

None. The plan, the precedent script, and the VALIDATION.md
Manual-Only Verifications table were all in place; writing the script
was a structured copy-and-adapt exercise.

## User Setup Required

**The user must run `73-UAT-SCRIPT.md` against a live session** before
Phase 73 can close. The orchestrator's downstream `/gsd-verify-work 73`
step will:

1. Run the full automated test suite (16 ART-MB-NN tests must all be GREEN).
2. Display the UAT script and prompt the user to run it.
3. Capture the user's three Scenario verdicts (Pass / Pass with caveats / Fail).
4. Either close Phase 73 (all Pass / Pass with caveats) or open a
   Phase 73.1 gap-closure plan (any Fail).

**Time investment for the user:** ~20 min wall-clock. ~5 min Scenario A,
~3 min Scenario B, ~10 min Scenario C (most of that is profile-switch
setup).

**Pre-flight:** Wayland session active (`$XDG_SESSION_TYPE == wayland`);
internet access; one favorite station with `Artist - Title` ICY signal
(SomaFM Indie Pop Rocks / DI.fm Vocal Trance recommended).

## Status

- **Automated verification:** ✅ COMPLETE
  - 16/16 ART-MB-NN tests GREEN across Plans 01–04
  - 345/345 pass across `test_cover_art*`, `test_repo`, `test_edit_station_dialog`,
    `test_settings_export`, `test_now_playing_panel`
  - Source-grep gates GREEN (User-Agent literal in `cover_art_mb.py`,
    `time.monotonic` references the rate gate, every
    `repo.update_station(` call in `edit_station_dialog.py` passes the
    `cover_art_source=` kwarg)
- **Manual verification:** ⏳ PENDING USER
  - 73-UAT-SCRIPT.md landed, status=PENDING
  - 3 scenarios staged for user execution
  - Awaiting `/gsd-verify-work 73` to drive the user through it

## Next Phase Readiness

- Phase 73 cannot close from inside this executor agent — the manual
  UAT requires a human + a live Wayland session + a live MusicBrainz
  endpoint. The next orchestrator step is `/gsd-verify-work 73`, which
  will run the automated suite, then surface the UAT script to the
  user.
- If all three scenarios PASS or PASS WITH CAVEATS → Phase 73 closes;
  REQUIREMENTS.md OoS line ("MusicBrainz cover art fallback | iTunes
  sufficient; revisit if gaps found") should be removed or rewritten
  per CONTEXT §Specifics. ROADMAP.md row for Phase 73 flips to
  complete.
- If any scenario FAILS → orchestrator opens `/gsd-plan-phase 73 --gaps`.
  Most-likely-to-fail scenario per CONTEXT D-11 is B (CAA-250 pixelation
  at 160×160 is the explicit RESEARCH assumption A1 that this UAT
  validates); fix is documented in-line in the script.

## Self-Check: PASSED

Files verified to exist:
- `.planning/phases/73-musicbrainz-album-cover-lookup-complement-itunes-with-smart-/73-UAT-SCRIPT.md` ✅ (348 lines, 25 H2 sections)
- `.planning/phases/73-musicbrainz-album-cover-lookup-complement-itunes-with-smart-/73-05-SUMMARY.md` ✅ (this file)

Commits verified in git log:
- `aa80710` docs(73-05): land Phase 73 UAT script (3 manual-only scenarios) ✅

Plan verify gate run from 73-05-PLAN.md Task 1 `<automated>` block:
- `test -f` → file exists ✅
- `wc -l | awk` → 348 lines (≥80) ✅
- `grep -c "^##"` → 25 H2 sections (≥4) ✅

---
*Phase: 73-musicbrainz-album-cover-lookup-complement-itunes-with-smart-*
*Completed: 2026-05-13 (autonomous half); manual UAT pending user*
