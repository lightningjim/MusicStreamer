# Phase 69: Debug why AAC streams aren't playing in Windows (possibly missing codec) - Context

**Gathered:** 2026-05-10
**Status:** Ready for planning

<domain>
## Phase Boundary

AAC-encoded streams currently fail to play in the Windows PyInstaller bundle. Phase 56 UAT surfaced this as Finding F2 ("AAC streams don't play on the Win11 VM") and parked it out-of-scope for follow-up. Phase 69 owns the root-cause diagnosis and the bundle-level fix in a single phase — confirm which GStreamer plugin(s) are missing from `dist/MusicStreamer/_internal/gst_plugins/`, add the corresponding conda-forge package(s) to the build recipe (`packaging/windows/README.md` conda install line + `packaging/windows/build.ps1`), rebuild the installer, and attest end-to-end AAC playback on the Win11 VM against two known-failing fixture URLs the user supplies during planning.

The phase also adds a **post-bundle plugin-presence guard** to `build.ps1` (analog of the existing post-bundle dist-info assertion at `build.ps1:203–283`) so a future regression — e.g. a documentation update that quietly drops `gst-libav` from the conda recipe — fails the build loudly instead of shipping a broken codec set.

This is a **Windows-only** packaging+bundle phase. Linux playback is unaffected. No app-side Python code changes are required (per discussion — runtime error UX stays as-is).

**In scope:**
- Empirical confirmation on the Win11 VM of exactly which AAC-related plugin(s) are missing from the current bundle (e.g., `avdec_aac` from `gst-libav`, `aacparse`/`faad` from `gst-plugins-bad`).
- Update `packaging/windows/README.md` (currently line 18–20: `python=3.12 pygobject gstreamer=1.28 pyinstaller "pyinstaller-hooks-contrib>=2026.2"`) to explicitly list the missing GStreamer conda-forge packages alongside the existing ones.
- Update or document any equivalent in `packaging/windows/build.ps1` if the script enumerates installed packages anywhere (it does not today, but the chosen conda packages must be installable cleanly by `conda env update`).
- Add a **post-bundle plugin-presence guard** in `build.ps1` (placed after the existing post-bundle dist-info assertion, ~line 283) that fails the build with a documented exit code if the bundled `gst_plugins/` directory does not contain the required AAC decoder/parser plugin DLLs. Single source of truth for the required plugin list lives in this guard or in a `tools/check_bundle_plugins.py` Python helper invoked by `build.ps1` (parallels `tools/check_subprocess_guard.py`).
- Update `tests/test_packaging_spec.py` (or a new sibling test file) with a static drift-guard pytest that reads `packaging/windows/README.md` and asserts the conda recipe line mentions every plugin name the guard requires — prevents documentation drift like the one Phase 69's context-load just exposed (README vs spike command vs CONCERNS.md all disagreed).
- Operator-driven UAT on the Win11 VM: rebuild installer via `build.ps1`, force-fresh-install (Phase 56 D-08 pattern), play **two user-supplied fixture URLs** — one DI.fm AAC-tier stream, one SomaFM HE-AAC stream — log PASS/FAIL with timestamps in `69-UAT-LOG.md`.
- Reconcile the documentation drift surfaced during context-load: `.planning/codebase/CONCERNS.md:56–59` currently claims "Phase 44 bundling confirmed gst-libav is present in conda-forge build" which contradicts the Phase 56 F2 empirical reality. Update CONCERNS.md to reflect Phase 69's findings.

**Out of scope:**
- No runtime error-message change in `musicstreamer/ui_qt/main_window.py:561` (`_on_playback_error`). The generic "Playback error: …" toast stays as-is; the fix is at the bundle level so a "missing AAC decoder" runtime path should not normally fire post-fix. (Discussed and explicitly rejected: codec-aware toast swap, "missing codecs" persistent hamburger indicator.)
- No startup plugin audit. The app does not probe `Gst.Registry` at launch to verify codec availability. (Discussed and rejected: quiet-log audit, visible startup banner.)
- No new app-side Python code in `musicstreamer/player.py`, `main_window.py`, or any UI module. Phase 69 is entirely in `packaging/windows/` + `tools/` + `tests/`.
- No expansion to other codecs. MP3, Opus, Vorbis, FLAC have no known regressions and are not re-verified as part of this phase's UAT. (Discussed and rejected: regression smoke for MP3/Opus, full codec matrix audit.)
- No Linux-side pytest of `gst-inspect` on the dev system. Linux's GStreamer is system-installed, not conda-forge MSVC — a Linux test proves nothing about the Windows bundle. (Discussed and rejected: Linux runtime pytest.)
- No fix for the PLS codec/bitrate URL-fallback todo (`2026-05-10-pls-codec-bitrate-url-fallback.md`) — surfaced by the todo cross-reference at score 0.4 but is a cosmetic EditStationDialog enhancement unrelated to AAC playback; stays in the backlog as its own future phase.
- No new investigation of the AA HTTPS rewrite from Phase 56 (D-01 / WIN-01) — that helper continues to operate as designed and is orthogonal to codec issues.
- No code-signing, SmartScreen mitigation, or installer signature work (orthogonal Windows-packaging deferred items).
- No Linux test for AAC playback — Linux is known-working; running an AAC stream through the Linux test suite would prove nothing about the Windows fix.

</domain>

<decisions>
## Implementation Decisions

### Phase shape & deliverable

- **D-01:** **Debug + fix in one phase.** The cause is highly probable (Windows conda-forge bundle missing the AAC decoder package); the deliverable is the bundle fix + verification, not a written-only investigation. This matches the Phase 56 / Phase 57 pattern (Windows debugs that ship the fix). Investigate-only and instrument-first patterns were considered and rejected.
- **D-02:** **Boundary set as: Bundle fix + build-time guard + plugin-presence pytest + VM UAT.** No app-side runtime UX changes. Runtime error toast (`main_window._on_playback_error`) stays as-is. (Initial discussion locked the broader "bundle fix + runtime message + build guard" boundary; subsequent discussion narrowed the runtime-message scope to zero, leaving the bundle + guard + pytest + UAT pieces.)

### Diagnosis path

- **DG-01:** **Empirical confirmation on the Win11 VM is the diagnostic gate.** Before changing the conda recipe, the operator runs `gst-inspect-1.0.exe --plugin avdec_aac`, `gst-inspect-1.0.exe --plugin faad`, and `gst-inspect-1.0.exe --plugin aacparse` against the **bundled** `dist/MusicStreamer/_internal/gst_plugins/` directory (NOT the host conda env) and records which are present/absent. This dictates the exact conda-forge package(s) to add. Researcher MUST document the expected mapping in `69-RESEARCH.md`:
  - `avdec_aac` → ships in `gst-libav` (conda-forge package: `gst-libav`)
  - `aacparse` → ships in `gst-plugins-bad`
  - `faad` → ships in `gst-plugins-bad` (license: optional; may not be in conda-forge build)
- **DG-02:** **Working hypothesis (not yet confirmed):** the current `packaging/windows/README.md:18–20` conda recipe (`python=3.12 pygobject gstreamer=1.28 pyinstaller "pyinstaller-hooks-contrib>=2026.2"`) installs ONLY the `gstreamer` meta-package and lets conda resolve dependencies. This likely yields `gst-plugins-base` + `gst-plugins-good` (for MP3/Opus/Vorbis — which work) but omits `gst-plugins-bad`, `gst-plugins-ugly`, and `gst-libav`. The Phase 43 spike recipe explicitly named the first four but still omitted `gst-libav`. Researcher's first task is to verify this hypothesis on the VM and amend accordingly.
- **DG-03:** **CONCERNS.md claim is suspect.** `.planning/codebase/CONCERNS.md:56–59` claims "Phase 44 bundling confirmed gst-libav is present in conda-forge build." This claim was made when gst-libav was believed necessary; the Phase 56 F2 empirical reality (AAC streams fail) contradicts it. Treat the CONCERNS.md statement as documentation drift, not as evidence. Phase 69 updates CONCERNS.md after the fix lands.

### Bundle fix

- **F-01:** **Conda recipe update is the primary fix.** Add the GStreamer package(s) identified by DG-01 to the `conda create` / `conda env update` line in `packaging/windows/README.md`. Most-likely outcome: add `gst-libav` (and probably also `gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly` to make the recipe explicit and prevent future ambiguity).
- **F-02:** **No PyInstaller `.spec` change expected.** The existing `hooksconfig.gstreamer` block (lines 132–141) uses "broad collect" — once the plugin DLLs exist in the conda env, the hook ships them automatically. If a plugin lands in an unexpected sub-directory layout, researcher revisits this assumption.
- **F-03:** **No `runtime_hook.py` change expected.** The three env vars set there (`GIO_EXTRA_MODULES`, `GI_TYPELIB_PATH`, `GST_PLUGIN_SCANNER`) cover plugin discovery already. Adding new plugins to `gst_plugins/` is transparent to the rthook.
- **F-04:** **Pinning policy** — researcher recommends whether to pin `gst-libav` to a specific minor version or leave unpinned. Default: leave unpinned, matching the existing `gstreamer=1.28` pin shape (major.minor only).

### Build-time guard

- **G-01:** **Post-bundle plugin-presence guard.** Runs AFTER PyInstaller produces `dist/MusicStreamer/_internal/`, BEFORE Inno Setup compile. Mirrors the existing post-bundle dist-info assertion structurally (`build.ps1:203–283`). Fails the build with a NEW documented exit code (suggest exit 10) and a `BUILD_FAIL reason=plugin_missing plugin='<name>' hint='add gst-libav to conda env'` message.
- **G-02:** **Required-plugin list lives in a Python helper.** Add `tools/check_bundle_plugins.py` (parallels `tools/check_subprocess_guard.py` invoked from `build.ps1:116` and `tools/check_spec_entry.py` invoked from line 125). The PowerShell side just calls the Python tool and branches on `$LASTEXITCODE`. Required plugin list (initial): `avdec_aac`, `aacparse`. May extend after researcher confirms `faad` necessity.
- **G-03:** **Guard validates by file presence in `dist/MusicStreamer/_internal/gst_plugins/`** (not by running `gst-inspect` on the bundled registry, which would require the bundle's runtime hook + PATH to be active). The Python helper enumerates DLL filenames against an expected set. Files-on-disk presence is sufficient — if the plugin DLL is present in `gst_plugins/`, the contrib hook + scanner already vouched it loads at runtime (Phase 43 finding).
- **G-04:** **Documented exit code 10** added to the `# Exit codes:` header comment at `build.ps1:5–6`. Updates: `0=ok, 1=env missing, ..., 9=post-bundle dist-info assertion fail, 10=plugin-presence guard fail`.

### Plugin-registry / drift-guard pytest

- **P-01:** **Static drift-guard pytest only, no runtime probe.** New test in `tests/test_packaging_spec.py` (or `tests/test_bundle_plugins_drift.py`) that:
  - Reads `packaging/windows/README.md` and locates the `conda create` block (regex-anchored).
  - Reads the required-plugin list from `tools/check_bundle_plugins.py` (the source of truth from G-02).
  - For each plugin in the required list, asserts the README's conda recipe mentions the conda-forge package that provides it. Mapping (initial): `avdec_aac → gst-libav`, `aacparse → gst-plugins-bad`. Mapping lives alongside the required-plugin list in the Python helper.
- **P-02:** **Test runs on Linux dev CI** (the same `uv run pytest -x` that already enforces `test_aumid_string_parity` and `test_packaging_spec`). Catches doc-vs-recipe drift before a build is even attempted on Windows.
- **P-03:** **No Linux pytest that runs `gst-inspect`.** Linux's GStreamer is the host system's, not conda-forge MSVC — a Linux gst-inspect result tells us nothing about the Windows bundle. Don't write a "feel-good" test that doesn't actually catch the bug.

### Repro target & UAT fixtures

- **R-01:** **Two canonical fixture URLs supplied by the user during planning.** One DI.fm AAC-tier stream, one SomaFM HE-AAC stream. The user knows which stations in their library fail today; researcher reserves named slots in `69-RESEARCH.md` (e.g., `<FIXTURE_DI_FM_AAC>`, `<FIXTURE_SOMA_HE_AAC>`) and user pastes the actual URLs at plan-check time. UAT-LOG.md test steps embed the URLs verbatim once locked.
- **R-02:** **Codec coverage: AAC + HE-AAC only.** MP3, Opus, Vorbis, FLAC are not re-verified. If the bundle fix inadvertently breaks one of those, that's caught by the operator's normal "still works" use of the app, not by Phase 69's UAT.
- **R-03:** **Pre-fix repro REQUIRED.** Before applying any conda recipe change, the operator confirms the two fixtures FAIL on the current installer build. This establishes a baseline so the post-fix PASS is meaningful (avoids the Phase 56 F1 "test confirmed only that wire-in didn't break happy path" pitfall).

### Verification path & gates

- **V-01:** **Operator-driven UAT-LOG.md, single fresh-install pass.** Phase 56 D-08 force-fresh-install sequence: uninstall + delete `%LOCALAPPDATA%\Programs\MusicStreamer` + delete LNK + reinstall with Run checkbox UNCHECKED (preserves user data at `%APPDATA%\musicstreamer`). Operator logs:
  - Pre-fix baseline (R-03): both fixtures FAIL on the existing build.
  - Build.ps1 rebuild with updated conda env: BUILD_OK or BUILD_FAIL with exit code.
  - Post-build guard (G-01) result: plugin-presence assertion PASS.
  - Post-install playback test: both fixtures PASS.
- **V-02:** **No two-pass `dist/MusicStreamer.exe` + installer attestation.** Single-pass installer-only is sufficient because Phase 69's guard (G-01) runs against `dist/MusicStreamer/_internal/` directly — if the guard passes, the installed binary trivially carries the same bundle.
- **V-03:** **UAT gates SHIP, not phase verify.** `/gsd-verify-work 69` runs goal-backward before `/gsd-complete-phase`. UAT is the operator-clicked confirmation that the artifact does what the goal says.

### Documentation reconciliation

- **DOC-01:** **Update `.planning/codebase/CONCERNS.md:56–59`** after the fix lands. Replace the "Phase 44 bundling confirmed gst-libav is present" sentence with: "Phase 69 confirmed gst-libav was missing from the conda recipe shipped through v2.0–v2.1.0; recipe now explicitly lists `gst-libav` and a post-bundle guard prevents future regressions."
- **DOC-02:** **Update `packaging/windows/README.md:18–20`** (the `conda create` block) with the new explicit package list and a single-line comment pointing at the relevant Phase 69 finding ("# AAC playback requires gst-libav (Phase 69)").
- **DOC-03:** **Spike-findings SKILL not updated.** The spike findings reference (`.claude/skills/spike-findings-musicstreamer/SKILL.md`) is historical Phase 43 documentation; do not retroactively edit it. Phase 69's `69-SUMMARY.md` is the new canonical reference for what the bundle now contains.
- **DOC-04:** **Update `.planning/REQUIREMENTS.md` Traceability table** with a new Phase 69 row. Suggested requirement label: `WIN-05` ("AAC-encoded streams play on Windows — DI.fm AAC tier + SomaFM HE-AAC fixtures verified post-bundle-fix"). Add to the "Backlog Bugs / Windows Polish" section.
- **DOC-05:** **No PROJECT.md edit beyond the standard phase-completion evolve step.** The v2.0 milestone line that already mentions `gst-libav` is historically accurate — Phase 43 spike DID identify gst-libav as required, even though the recipe didn't carry it through. Leave as-is.

### Test discipline

- **TD-01:** **No Wave 0 RED contract pattern.** The phase has no Python application code; the test surface is one static drift-guard pytest (P-01) plus the build-time guard (G-01). RED-first doesn't apply.
- **TD-02:** **Existing test_packaging_spec.py is the integration seam.** Add the new drift-guard test as a sibling assertion or new top-level test in the same file (keeps packaging-related tests colocated).
- **TD-03:** **No new fixtures recorded as test data.** Unlike Phase 68's `tests/fixtures/aa_*.pls` pattern (AA API responses), Phase 69's fixtures are LIVE streaming URLs — they cannot be recorded as static fixtures because the test reads metadata at runtime and the URLs may go offline. URLs live ONLY in `69-RESEARCH.md` + `69-UAT-LOG.md` for operator reference.

### Claude's Discretion

- Researcher picks whether to verify the gst-libav LICENSE terms (LGPL ffmpeg redistribution) before committing to it as the fix. If a license concern emerges, the alternative is `faad` from `gst-plugins-bad` (which conda-forge MAY have excluded for license reasons of its own). Default assumption: gst-libav LGPL is fine for a personal-use single-user app and matches the existing posture (the bundle already ships LGPL GStreamer wholesale).
- Planner picks the exact filename of the new Python guard helper. Recommendation: `tools/check_bundle_plugins.py`.
- Planner picks the exact test filename. Recommendation: extend `tests/test_packaging_spec.py` rather than adding a new file — keeps packaging-related drift guards colocated.
- Planner picks how `tools/check_bundle_plugins.py` enumerates the required-plugin list — module-level constant (simplest), JSON file, or a function that derives from the conda recipe (most DRY but circular). Default: module-level constant `REQUIRED_PLUGINS = {"avdec_aac": "gst-libav", "aacparse": "gst-plugins-bad"}` — simple dict, both the guard and the pytest import it.
- Planner picks whether to pin the conda-forge `gst-libav` package version. Default: unpinned (matches the existing `gstreamer=1.28` major.minor pin posture; conda will resolve a compatible build).

### Folded Todos

No todos folded. (See Reviewed Todos in `<deferred>`.)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 69 inputs
- `.planning/ROADMAP.md` §"Phase 69" — high-level goal (single sentence; this CONTEXT.md is the operative source for everything else)
- `.planning/PROJECT.md` — current state (Phase 68 complete, milestone v2.1, GStreamer 1.28+ on Windows pinned line in v2.0 milestone block)
- `.planning/REQUIREMENTS.md` — v2.1 requirements table; Phase 69 likely adds a new WIN-05 row

### Smoking-gun evidence
- `.planning/phases/56-windows-di-fm-smtc-start-menu/56-05-UAT-LOG.md:86–92` — Phase 56 F2 finding "AAC streams don't play on Windows", explicit suspicion of missing `faad` / `avdec_aac` plugin
- `.planning/codebase/CONCERNS.md:56–59` — claims gst-libav is present (CONTRADICTED by F2 above; Phase 69 updates this)

### Windows bundle pipeline (the change surface)
- `packaging/windows/README.md` line 18–20 — current conda recipe (target of F-01 / DOC-02 update)
- `packaging/windows/build.ps1` line 5–6 — exit-code header comment (target of G-04 update)
- `packaging/windows/build.ps1` line 203–283 — post-bundle dist-info assertion (structural analog for G-01)
- `packaging/windows/build.ps1` line 116, 125 — existing Python-tool invocation pattern (`tools/check_subprocess_guard.py`, `tools/check_spec_entry.py` — pattern for G-02)
- `packaging/windows/MusicStreamer.spec` line 132–141 — `hooksconfig.gstreamer` broad-collect (F-02 assumption — researcher confirms no change needed)
- `packaging/windows/runtime_hook.py` — three env vars (F-03 assumption — researcher confirms no change needed)

### Spike findings (Phase 43 ground truth)
- `.claude/skills/spike-findings-musicstreamer/SKILL.md` — auto-load for Windows packaging / GStreamer / conda-forge work
- `.claude/skills/spike-findings-musicstreamer/sources/43-gstreamer-windows-spike/README.md` line 18 — original spike conda recipe (included `gst-plugins-base/good/bad/ugly` but NOT `gst-libav`)
- `.claude/skills/spike-findings-musicstreamer/sources/43-gstreamer-windows-spike/43-SPIKE-FINDINGS.md` line 130–132 — broad-collect strategy + prune-later note
- `.claude/skills/spike-findings-musicstreamer/references/windows-gstreamer-bundling.md` — full conda-forge layout documentation

### Playback code path (read-only; no edits expected)
- `musicstreamer/player.py:633–641` — `_on_gst_error` bus handler emits `playback_error` signal (the path an AAC failure would flow through)
- `musicstreamer/ui_qt/main_window.py:561–583` — `_on_playback_error` toast (unchanged per D-02)
- `musicstreamer/playlist_parser.py:34` — `_CODEC_TOKENS` includes HE-AAC and AAC (informational; explains how SomaFM HE-AAC streams are categorized at import time)
- `musicstreamer/aa_import.py:128` — `_CODEC_MAP = {"hi": "MP3", "med": "AAC", "low": "AAC"}` (explains the DI.fm "AAC tier" terminology)
- `musicstreamer/stream_ordering.py:18` — `_CODEC_RANK = {"FLAC": 3, "AAC": 2, "MP3": 1}` (informational)

### Existing tool/test patterns to mirror
- `tools/check_subprocess_guard.py` — single-source-of-truth Python guard invoked by build.ps1 (mirror for G-02)
- `tools/check_spec_entry.py` — similar PowerShell-calls-Python pattern (mirror for G-02)
- `tests/test_packaging_spec.py` — existing packaging drift-guard tests (host for P-01 new test)
- `tests/test_aumid_string_parity.py` — example of cross-file string-drift pytest (similar shape to P-01)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`tools/check_subprocess_guard.py` invocation pattern** in `build.ps1:115–121` — Python helper called via `Invoke-Native`, exit code branching, hint message in BUILD_FAIL line. Phase 69's plugin-presence guard (G-01/G-02) clones this shape verbatim.
- **`build.ps1:203–283` post-bundle dist-info assertion** — same structural slot Phase 69 uses for the plugin-presence guard. Both are post-PyInstaller, pre-Inno-Setup, fail-fast with documented exit codes.
- **`tests/test_packaging_spec.py`** — existing host for packaging drift-guard tests (subprocess-guard literal, spec-entry literal). Phase 69's drift-guard pytest (P-01) sits alongside.

### Established Patterns
- **PowerShell-calls-Python tool with documented exit code** — `build.ps1` invokes `python tools/check_*.py`, captures `$LASTEXITCODE`, emits `BUILD_FAIL reason=<name> hint='<remediation>'` on non-zero. Documented in `build.ps1:5–6` exit-code header.
- **Documentation-drift pytest pattern** — `tests/test_aumid_string_parity.py` reads two files (Python source + Inno Setup script) and asserts a literal string appears in both. Phase 69's P-01 follows: read `README.md` conda block + read `tools/check_bundle_plugins.py` required list, assert mapping coverage.
- **Operator-driven UAT-LOG.md** — Phase 56 / 57 pattern. Phase 69's `69-UAT-LOG.md` follows the same structure: pre-fix baseline, build attestation, post-install playback, RELEASE-grade re-attestation.
- **Force-fresh-install on Win11 VM** — Phase 56 D-08 sequence preserved verbatim. Documented in `.planning/phases/56-*/56-05-UAT-LOG.md:102–113`.
- **conda-forge as the only viable Windows GStreamer source** — Phase 43 spike finding. Phase 69's fix adds to the conda recipe, never proposes installing GStreamer outside conda-forge.

### Integration Points
- **`packaging/windows/README.md`** — single edit site for the conda recipe (F-01 / DOC-02)
- **`packaging/windows/build.ps1`** — two edits: header exit-code comment (G-04) + new guard block after line 283 (G-01)
- **`tools/check_bundle_plugins.py`** — NEW file (G-02), parallels `check_subprocess_guard.py` shape
- **`tests/test_packaging_spec.py`** — extend with new drift-guard test function (P-01)
- **`.planning/codebase/CONCERNS.md`** — edit lines 56–59 after fix lands (DOC-01)

</code_context>

<specifics>
## Specific Ideas

- The user pulled back from changing app-side runtime UX twice during discussion (rejected codec-aware toast swap, rejected startup audit) — preference is "fix it at the bundle level so the runtime path never fires; don't add error-message complexity for a class of error that shouldn't happen post-fix." Phase 69 stays in `packaging/` + `tools/` + `tests/`.
- The user supplied no specific AAC stream URLs upfront — researcher will reserve named placeholders in `69-RESEARCH.md` and the user supplies the URLs during plan-check (R-01).
- The user picked the most thorough verification path early ("Bundle fix + runtime message + build guard"), then narrowed it back to "Bundle fix + build guard + pytest" as runtime UX questions were answered "no change." The locked boundary reflects the final narrowed scope, not the initial pick.
- The user chose the Phase 56 single-pass UAT pattern over the two-pass dist/+installer pattern (V-02). Matches their established release-grade attestation flow.
- The user noted the documentation drift between CONCERNS.md and the empirical reality should be reconciled as part of the phase (DOC-01) — surface the actual ground truth rather than letting stale claims persist.
- The user disabled the `--chain` flag at the end of discussion ("Ready for context; disable chain and do not move to plan phase") — Phase 69 will be planned manually via `/gsd-plan-phase 69` after CONTEXT.md is reviewed.

</specifics>

<deferred>
## Deferred Ideas

- **Rollback / regression risk strategy for conda recipe changes** — if adding `gst-libav` breaks an unrelated codec (plugin-load order conflict, symbol clash), the mitigation playbook is: pin `gst-libav` to a known-good build, exclude conflicting plugins via `hooksconfig.gstreamer.exclude_plugins`, or roll back the recipe entry. Deferred because the risk is theoretical; if it materializes, address in a Phase 69 follow-up rather than pre-emptively scoping.
- **PLS codec/bitrate URL-fallback** (`.planning/notes/2026-05-10-pls-codec-bitrate-url-fallback.md`) — surfaced by todo-cross-reference at score 0.4 because of keyword overlap on "codec". Cosmetic EditStationDialog enhancement (column population), entirely unrelated to playback. Stays in `.planning/notes/` as a future opportunistic phase.
- **Runtime error-message UX for missing codecs** (codec-aware toast swap, hamburger "missing codec" persistent indicator) — discussed and explicitly rejected. Revisit only if Phase 69's bundle fix is incomplete or another codec regression appears.
- **Startup plugin audit at app launch** (quiet log-only, visible warning banner) — discussed and explicitly rejected. Same revisit condition as above.
- **Other codec regressions** (MP3/Opus/Vorbis/FLAC explicit verification, full codec matrix audit) — out of scope for "debug AAC". If a regression surfaces in another codec, that's a new phase.
- **Spike-findings SKILL.md retroactive edit** — historical Phase 43 doc; do not edit. Phase 69's SUMMARY.md is the new canonical reference.
- **Two-pass UAT** (bare `dist/MusicStreamer.exe` + installed binary) — rejected in favor of single-pass (V-02). Revisit if Phase 69's V-01 reveals a discrepancy between `dist/` and installed-binary behavior.
- **Linux-side runtime gst-inspect pytest** — rejected (P-03). A test that doesn't exercise the actual failure surface is anti-value.

### Reviewed Todos (not folded)

- **`2026-05-10-pls-codec-bitrate-url-fallback.md`** — PLS auto-resolve URL fallback for codec/bitrate extraction. Reason for not folding: keyword overlap on "codec" but actual scope is EditStationDialog UI column population from import-time PLS parsing — entirely orthogonal to runtime AAC playback. Score 0.4 reflects the weak keyword match, not topical relevance. Promote when starting a future "PLS / playlist parser polish" phase.

</deferred>

---

*Phase: 69-debug-why-aac-streams-aren-t-playing-in-windows-possibly-mis*
*Context gathered: 2026-05-10*
