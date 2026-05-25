# Phase 69: Debug why AAC streams aren't playing in Windows (possibly missing codec) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-10
**Phase:** 69-debug-why-aac-streams-aren-t-playing-in-windows-possibly-mis
**Areas discussed:** Phase shape & deliverable, Repro target & test corpus, Runtime detection / user feedback, Verification path & gates

---

## Phase shape & deliverable

### Q1: Phase 69 deliverable — investigate-only, debug+fix in one phase, or instrument-first?

| Option | Description | Selected |
|--------|-------------|----------|
| Debug + fix in one phase | Confirm missing plugin(s) via gst-inspect on the VM bundle, add the right conda packages to packaging/windows/README.md + build.ps1, rebuild + UAT. Matches Phase 56 / 57 pattern. | ✓ |
| Investigate-only, fix in a follow-up phase | Phase 69 produces written root-cause + reproducible diagnostic; Phase 69.1 ships the actual change. | |
| Instrument-first, behavior fix later (Phase 62 BUG-09 pattern) | Phase 69 ships a startup plugin audit + richer error toast; defer bundle fix until instrumentation confirms what's missing. | |

**User's choice:** Debug + fix in one phase.
**Notes:** Cause is well-scoped (Windows-only, codec-specific). Bundles together diagnosis and fix in the established Windows-debug shape.

### Q2: Within the debug+fix scope, where does the boundary land?

| Option | Description | Selected |
|--------|-------------|----------|
| Bundle fix + verification only | Add missing GStreamer packages, rebuild installer, verify AAC plays. Smallest blast radius. | |
| Bundle fix + targeted runtime error message | Same plus: pattern-match GStreamer decoder errors and swap toast to "missing codec" message. | |
| Bundle fix + build-time guard | Same plus: build.ps1 fails loudly if avdec_aac not present in conda env. | |
| Bundle fix + runtime message + build guard | All three: bundle fix, runtime error swap, build-time presence assertion. Most thorough. | ✓ |

**User's choice:** Bundle fix + runtime message + build guard.
**Notes:** Initial pick was the broadest scope. Subsequent runtime-detection questions narrowed the runtime-message piece back to "no change" — see Runtime detection / user feedback area below. Final locked boundary in CONTEXT.md D-02: Bundle fix + build guard + plugin-registry pytest + VM UAT (no runtime UX changes).

---

## Repro target & test corpus

### Q1: Which AAC streams are the canonical fixtures we'll test against?

| Option | Description | Selected |
|--------|-------------|----------|
| DI.fm AAC tier + SomaFM HE-AAC | Two-provider coverage; hits AAC-LC + HE-AAC. | ✓ |
| DI.fm AAC tier only | Minimum sufficient; Phase 56 F2 surfaced via DI.fm. | |
| DI.fm AAC + SomaFM HE-AAC + a generic ShoutCast AAC | Three-stream coverage including pure generic AAC. | |

**User's choice:** DI.fm AAC tier + SomaFM HE-AAC.
**Notes:** Matches user's known listening surface; both codec dialects represented.

### Q2: Codec scope — do we also explicitly verify any other formats?

| Option | Description | Selected |
|--------|-------------|----------|
| AAC + HE-AAC only | Phase scope says AAC; don't expand. | ✓ |
| AAC + HE-AAC + regression smoke for MP3/Opus | Defensive against plugin loading order changes. | |
| Full codec matrix | Audit every codec in stream_ordering._CODEC_RANK. | |

**User's choice:** AAC + HE-AAC only.
**Notes:** Stays within stated phase scope.

### Q3: Failing-stream URL discovery — how do we lock the specific test URLs?

| Option | Description | Selected |
|--------|-------------|----------|
| User supplies known-failing URLs during planning | User pastes 2 URLs into PLAN.md / RESEARCH.md from their library. | ✓ |
| Researcher derives URLs from existing fixtures + AA import | Researcher pulls candidates from tests/fixtures + public SomaFM catalogue. | |
| Both — researcher proposes URLs, user confirms during plan-check | Researcher pulls candidates; user replaces if different. | |

**User's choice:** User supplies known-failing URLs during planning.
**Notes:** Researcher reserves named placeholders in RESEARCH.md; user supplies URLs at plan-check time. Captured in CONTEXT.md R-01.

### Q4: Test format — unit test, integration test, or UAT-only?

| Option | Description | Selected |
|--------|-------------|----------|
| Plugin-registry unit test + Win11 VM UAT | Linux-host pytest verifies plugin presence in bundle; VM UAT plays fixtures. | ✓ |
| Build.ps1 plugin-presence guard + VM UAT | No pytest; build guard IS the test. | |
| VM UAT only (operator-driven) | Phase 56 pattern; no automated test. | |

**User's choice:** Plugin-registry unit test + Win11 VM UAT.
**Notes:** Most regression-safe combination. Note: pytest scope was subsequently refined to a static drift-guard test (README ↔ guard list) rather than a runtime gst-inspect probe — see CONTEXT.md P-01/P-02/P-03 for the final shape.

---

## Runtime detection / user feedback

### Q1: What does the runtime error toast say when an AAC decoder is missing?

| Option | Description | Selected |
|--------|-------------|----------|
| Generic "Playback error: <gst error truncated>" (current behavior) | Keep main_window._on_playback_error as-is. | ✓ |
| Detect codec/decoder errors, swap toast to "Missing codec: AAC — reinstall to fix" | Pattern-match GStreamer error text and swap toast. | |
| Same as recommended PLUS hamburger-menu "Missing codecs" persistent indicator | Toast plus sticky entry near version/Node-status row. | |

**User's choice:** Generic "Playback error: <gst error truncated>" (current behavior).
**Notes:** Reversal from Q2 of Phase shape area. Effectively narrows the locked boundary by removing the "runtime message" piece. Rationale (implied): fix the bundle so this runtime path never fires; don't add error-message complexity for an error class that shouldn't happen post-fix.

### Q2: Startup plugin audit — do we proactively check at app launch?

| Option | Description | Selected |
|--------|-------------|----------|
| No startup audit — react only on actual playback error | Don't probe Gst.Registry on startup. | ✓ |
| Quiet startup audit, log-only | Log result to stderr/log file; no user-visible warning. | |
| Visible startup audit — toast/banner if AAC decoder absent | Non-blocking startup notification. | |

**User's choice:** No startup audit — react only on actual playback error.
**Notes:** Consistent with Q1's "don't change app-side runtime behavior." Phase 69 stays entirely in packaging/ + tools/ + tests/.

---

## Verification path & gates

### Q1: Where does the build.ps1 plugin-presence guard run — pre-bundle or post-bundle?

| Option | Description | Selected |
|--------|-------------|----------|
| Post-bundle, on the actual bundled registry | Run gst-inspect against dist/MusicStreamer/_internal/ AFTER PyInstaller. | ✓ |
| Pre-bundle, against the conda env | Run gst-inspect against $GSTREAMER_ROOT before PyInstaller. | |
| Both — pre AND post | Belt-and-braces. | |

**User's choice:** Post-bundle, on the actual bundled registry.
**Notes:** Mirrors existing post-bundle dist-info assertion structurally. Verifies what's actually shipping. Captured as CONTEXT.md G-01/G-03.

### Q2: Linux-side plugin-registry pytest — against dev env, bundle layout, or recorded fixture?

| Option | Description | Selected |
|--------|-------------|----------|
| Skip pytest on Linux; rely on build.ps1 guard + VM UAT | Linux dev host's GStreamer is system-installed, not conda-forge MSVC. | ✓ |
| Linux pytest that reads packaging/windows/README.md + build.ps1 for the conda recipe | Static drift-guard test for README↔build.ps1 consistency. | |
| Both — build.ps1 runtime guard AND Linux static drift-guard pytest | Most thorough. | |

**User's choice:** Skip pytest on Linux; rely on build.ps1 guard + VM UAT.
**Notes:** Refinement against the Q4 "Plugin-registry unit test" answer from earlier — the user clarified they want the build-side guard + VM UAT, not a Linux pytest that runs gst-inspect. CONTEXT.md P-01/P-02/P-03 captures the final shape as a **static drift-guard pytest** (option 2 here, READ as the README↔guard-list drift check) — this preserves the catch-doc-drift value of having a pytest while honoring the user's "no Linux runtime probe" preference. The pytest checks documentation consistency, not codec presence.

### Q3: VM UAT structure — how do we attest the fix on the Win11 VM?

| Option | Description | Selected |
|--------|-------------|----------|
| Operator-driven UAT-LOG.md, single fresh-install pass | Phase 56 pattern: force-fresh-install, play fixtures, log PASS/FAIL. | ✓ |
| Two-pass UAT: bare-bundle then installed binary | Path C + release-grade pattern. | |
| Skip UAT — build.ps1 post-bundle guard is sufficient | No human clicks; guard is mechanical proof. | |

**User's choice:** Operator-driven UAT-LOG.md, single fresh-install pass.
**Notes:** Matches established Phase 56 release-grade attestation flow. Single pass is sufficient because guard runs against dist/ directly; installed binary trivially carries the same bundle.

### Q4: Did we forget anything? Should we discuss anything else before locking context?

| Option | Description | Selected |
|--------|-------------|----------|
| I'm ready for context | All 4 areas covered; move to writing CONTEXT.md and chaining into plan-phase. | |
| One more gray area — rollback / regression risk | Discuss conda recipe rollback strategy if a new package breaks something. | |
| One more gray area — documentation update scope | Discuss which docs need touching (CONCERNS.md, README, SKILL.md, PROJECT.md). | |
| Other (free-text) | — | ✓ |

**User's choice (free-text):** "Ready for context; disable chain and do not move to plan phase."
**Notes:** User wants CONTEXT.md written + committed but NOT auto-advanced to /gsd-plan-phase. Phase 69 will be planned manually after CONTEXT.md review. The two declined extra-area discussions (rollback risk, documentation update scope) were both captured in CONTEXT.md proactively — rollback in `<deferred>`, documentation update scope in `<decisions>` as DOC-01..DOC-05.

---

## Claude's Discretion

The following decisions were left to Claude / downstream agents (captured in CONTEXT.md `### Claude's Discretion`):

- Whether researcher should verify gst-libav LGPL ffmpeg redistribution license terms before committing to it (default: gst-libav LGPL is fine; matches existing bundle posture).
- Exact filename of the new Python guard helper (recommendation: `tools/check_bundle_plugins.py`).
- Exact pytest filename (recommendation: extend `tests/test_packaging_spec.py`).
- Required-plugin list data structure (recommendation: module-level constant dict).
- Whether to pin the conda-forge `gst-libav` package version (recommendation: unpinned, matches existing `gstreamer=1.28` major.minor pin posture).

## Deferred Ideas

- **Rollback / regression risk strategy for conda recipe changes** — declined as a discussion area but captured in CONTEXT.md `<deferred>`.
- **PLS codec/bitrate URL-fallback todo** (`2026-05-10-pls-codec-bitrate-url-fallback.md`) — reviewed in cross_reference_todos (score 0.4) but not folded; orthogonal to playback. Stays in backlog.
- **Runtime error-message UX for missing codecs** — explicitly rejected during Runtime detection area.
- **Startup plugin audit at app launch** — explicitly rejected during Runtime detection area.
- **Other-codec regression verification** (MP3/Opus/Vorbis/FLAC) — out of scope per Repro area Q2.
- **Spike-findings SKILL.md retroactive edit** — declined; Phase 69 SUMMARY.md is the new canonical reference.
- **Two-pass UAT pattern** — declined in favor of single-pass per V-02.
- **Linux-side runtime gst-inspect pytest** — declined per P-03.
