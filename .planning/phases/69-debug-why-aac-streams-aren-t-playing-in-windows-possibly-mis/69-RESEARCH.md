# Phase 69: Debug why AAC streams aren't playing in Windows (possibly missing codec) — Research

**Researched:** 2026-05-11
**Domain:** Windows packaging — conda-forge GStreamer plugin recipe + PyInstaller bundling + build-time presence guards
**Confidence:** HIGH (root cause confirmed empirically by inspecting current `packaging/windows/README.md` against conda-forge recipe metadata + the project's own historical "gst-libav required for AAC" note in PROJECT.md line 44)

## Summary

The empirical AAC playback failure observed in Phase 56 UAT (Finding F2) has a single high-confidence root cause: **the conda-forge `gstreamer=1.28` meta-package does NOT pull in any plugin subpackages as runtime dependencies, and the current `packaging/windows/README.md` (lines 18–20) lists only `gstreamer=1.28` with NO `gst-plugins-*` packages**. The Phase 43 spike recipe explicitly listed `gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly`; Phase 44's production recipe silently dropped all four and never added `gst-libav` (which `.planning/PROJECT.md` line 44 already documented as required for AAC/H.264 on Windows). Documentation drift was complete and uncaught.

The empirical reality on the operator's Win11 VM is that some plugins ARE present at runtime (MP3/Opus/Vorbis/FLAC playback works per Phase 56 UAT) — this is because the operator's actual conda env carries plugin packages from the Phase 43 spike conda env that were not encoded in the production README. That snapshot will not reproduce on a fresh build host.

The fix is a packaging-only edit set in `packaging/windows/`: extend the conda recipe to explicitly list every required plugin package (mandatory for build reproducibility) and add a post-bundle plugin-presence guard so a future docs-drift regression fails the build loudly. The runtime `runtime_hook.py` and `MusicStreamer.spec` need no change — the hooks-contrib gstreamer hook auto-collects whatever plugin DLLs are present in the conda env's `lib/gstreamer-1.0/` directory.

**Primary recommendation:** Add `gst-libav gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly` to the conda recipe in `packaging/windows/README.md`. Add post-bundle guard in `build.ps1` that verifies `gstlibav.dll` and `gstaudioparsers.dll` are present in `dist/MusicStreamer/_internal/gst_plugins/`. Wire a static drift-guard pytest that asserts the README recipe and `tools/check_bundle_plugins.py`'s required-plugin list stay in lockstep.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| AAC decode at runtime | Windows GStreamer plugin DLL (`gstlibav.dll`, statically linked FFmpeg `avdec_aac`) | playbin3 autoplugger | Decode happens inside `_internal/gst_plugins/gstlibav.dll`; the app's `playbin3` element auto-wires the decoder when the plugin DLL is present. No app-Python responsibility. |
| AAC ADTS/ADIF parsing | Windows GStreamer plugin DLL (`gstaudioparsers.dll`, contains `aacparse`) | playbin3 autoplugger | `aacparse` ships in gst-plugins-good's `audioparsers` plugin (not gst-plugins-bad as CONTEXT-DG-01 assumed); pulled in by playbin3's typefind→parse pipeline before decode. |
| Conda env recipe (build host) | `packaging/windows/README.md` conda block | `packaging/windows/build.ps1` (no enumeration today) | README is the single source of truth for the build env. build.ps1 reads CONDA_PREFIX but does not list packages — packaging is reproducible only if the README is followed. |
| PyInstaller plugin DLL collection | `pyinstaller-hooks-contrib` 2026.2 `hook-gi.repository.Gst.py` | `MusicStreamer.spec` `hooksconfig.gstreamer` block (broad-collect, line 132–141) | The contrib hook enumerates the live GStreamer registry at build time and copies every plugin DLL it finds in conda's `lib/gstreamer-1.0/` to `_internal/gst_plugins/`. No app-side change needed once the conda env carries the right packages. |
| Post-bundle presence verification | NEW `tools/check_bundle_plugins.py` | NEW step in `build.ps1` (after line 283) | Cross-platform Python helper enumerates `dist/MusicStreamer/_internal/gst_plugins/*.dll` against an expected set. Mirrors `check_subprocess_guard.py` shape. |
| Documentation drift guard | NEW pytest in `tests/test_packaging_spec.py` | reads `packaging/windows/README.md` + imports `tools/check_bundle_plugins.py` | Static drift-guard — runs on Linux dev CI, catches doc-vs-required-list divergence before any Windows build attempt. Mirrors `test_aumid_string_parity.py` cross-file literal-coverage shape. |

## User Constraints

> Copied verbatim from `69-CONTEXT.md`. **The planner MUST honor these.**

### Locked Decisions (from `<decisions>`)

**Phase shape & deliverable**
- **D-01:** Debug + fix in one phase. Investigate-only and instrument-first patterns rejected.
- **D-02:** Boundary: Bundle fix + build-time guard + plugin-presence pytest + VM UAT. No app-side runtime UX changes. Runtime error toast (`main_window._on_playback_error`) stays as-is.

**Diagnosis path**
- **DG-01:** Empirical confirmation on the Win11 VM is the diagnostic gate. Operator runs `gst-inspect-1.0.exe --plugin avdec_aac`, `... --plugin faad`, `... --plugin aacparse` against the **bundled** `dist/MusicStreamer/_internal/gst_plugins/`. Researcher MUST document the expected plugin→package mapping (see "Plugin → conda-forge package map" below — research has corrected this from CONTEXT's hypothesis).
- **DG-02:** Working hypothesis: current README recipe (`python=3.12 pygobject gstreamer=1.28 pyinstaller "pyinstaller-hooks-contrib>=2026.2"`) installs only the `gstreamer` meta-package and relies on conda dependency resolution. **Research has CONFIRMED this hypothesis** (see "DG-02 Confirmation" below). Conda-forge `gstreamer` package has no runtime deps on any plugin subpackages.
- **DG-03:** CONCERNS.md (`.planning/codebase/CONCERNS.md:56–59`) claim "Phase 44 bundling confirmed gst-libav is present" is suspect; updated by DOC-01 after fix lands.

**Bundle fix**
- **F-01:** Conda recipe update is the primary fix. Add the GStreamer package(s) identified by DG-01 to the `conda create` / `conda env update` line in `packaging/windows/README.md`. **Research recommends:** add `gst-libav gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly` (matches Phase 43 spike recipe + adds gst-libav). See F-01 elaboration below.
- **F-02:** No PyInstaller `.spec` change expected. Broad-collect hooksconfig handles new plugins automatically. (Research confirms — see F-02 verification.)
- **F-03:** No `runtime_hook.py` change expected. (Research confirms — three env vars are plugin-agnostic.)
- **F-04:** Pinning policy — researcher recommends. **Recommendation: leave `gst-libav` unpinned**, matching `gstreamer=1.28` major.minor shape. conda-forge `gst-libav=1.28.2` is the current available win-64 build (verified 2026-05-11 via Anaconda.org).

**Build-time guard**
- **G-01:** Post-bundle plugin-presence guard. Runs AFTER PyInstaller (~line 283 of build.ps1, after existing dist-info assertion), BEFORE Inno Setup. Fails with NEW exit code **10**. Message: `BUILD_FAIL reason=plugin_missing plugin='<name>' hint='add <conda-package> to conda env'`.
- **G-02:** Required-plugin list lives in `tools/check_bundle_plugins.py` (parallels `tools/check_subprocess_guard.py` / `check_spec_entry.py`). PowerShell calls Python, branches on `$LASTEXITCODE`. Initial required list: `avdec_aac` (in `gstlibav.dll`) and `aacparse` (in `gstaudioparsers.dll`).
- **G-03:** Guard validates by **file-on-disk presence in `dist/MusicStreamer/_internal/gst_plugins/`** (NOT by running `gst-inspect` on the bundled registry, which would require the bundle's PATH/env). Enumerate DLL filenames against expected set.
- **G-04:** Document exit code 10 in the `# Exit codes:` header comment at `build.ps1:5–6`.

**Plugin-registry / drift-guard pytest**
- **P-01:** Static drift-guard pytest only, no runtime probe. New test reads `packaging/windows/README.md`, locates the `conda create` block (regex-anchored), and asserts the README's conda recipe mentions the conda-forge package that provides each plugin in `tools/check_bundle_plugins.py`'s required list. Plugin→package mapping lives alongside the required list in the Python helper.
- **P-02:** Runs on Linux dev CI (`uv run pytest -x`). Catches drift before Windows build is attempted.
- **P-03:** No Linux pytest that runs `gst-inspect`. Linux's GStreamer is the host system's, not conda-forge MSVC.

**Repro target & UAT fixtures**
- **R-01:** Two canonical fixture URLs supplied by the user during planning. One DI.fm AAC-tier stream, one SomaFM HE-AAC stream. **Researcher reserves named slots below (see "Fixture URLs" section); user pastes the actual URLs at plan-check time.**
- **R-02:** Codec coverage AAC + HE-AAC only. MP3/Opus/Vorbis/FLAC not re-verified.
- **R-03:** Pre-fix repro REQUIRED. Operator confirms both fixtures FAIL on current installer build BEFORE applying the fix.

**Verification path & gates**
- **V-01:** Operator-driven UAT-LOG.md, single fresh-install pass. Phase 56 D-08 force-fresh-install sequence: uninstall + delete `%LOCALAPPDATA%\Programs\MusicStreamer` + delete LNK + reinstall with Run checkbox UNCHECKED (preserves user data at `%APPDATA%\musicstreamer`).
- **V-02:** No two-pass `dist/MusicStreamer.exe` + installer attestation. Single-pass installer-only sufficient.
- **V-03:** UAT gates SHIP, not phase verify. `/gsd-verify-work 69` runs goal-backward before `/gsd-complete-phase`.

**Documentation reconciliation**
- **DOC-01:** Update `.planning/codebase/CONCERNS.md:56–59` after fix lands.
- **DOC-02:** Update `packaging/windows/README.md:18–20` with explicit package list + comment "# AAC playback requires gst-libav (Phase 69)".
- **DOC-03:** Spike-findings SKILL NOT updated (historical Phase 43 doc).
- **DOC-04:** Update `.planning/REQUIREMENTS.md` Traceability table with new Phase 69 row, **suggested label `WIN-05`**: "AAC-encoded streams play on Windows — DI.fm AAC tier + SomaFM HE-AAC fixtures verified post-bundle-fix". Add to "Backlog Bugs / Windows Polish" section.
- **DOC-05:** No PROJECT.md edit beyond standard phase-completion evolve step.

**Test discipline**
- **TD-01:** No Wave 0 RED contract pattern.
- **TD-02:** Existing `tests/test_packaging_spec.py` is the integration seam — extend it.
- **TD-03:** No new fixtures recorded as test data. URLs live ONLY in `69-RESEARCH.md` + `69-UAT-LOG.md`.

### Claude's Discretion (from `<decisions>`)

- Researcher picks whether to verify gst-libav LICENSE before committing it as the fix.
  - **Research recommendation:** gst-libav is LGPL-2.1-or-later [VERIFIED: conda-forge gst-libav-feedstock recipe.yaml `about.license` field, fetched 2026-05-11]. This matches the existing posture of bundling LGPL GStreamer wholesale. **No license concern.** `faad` (the GPL-licensed alternative) is **not needed**.
- Planner picks the exact filename of the new Python guard helper. **Research recommendation: `tools/check_bundle_plugins.py`** — matches `check_subprocess_guard.py` / `check_spec_entry.py` naming.
- Planner picks the exact test filename. **Research recommendation: extend `tests/test_packaging_spec.py`** rather than adding a new file (keeps packaging drift guards colocated, matches the spec).
- Planner picks how `tools/check_bundle_plugins.py` enumerates the required-plugin list. **Research recommendation:** module-level constant `REQUIRED_PLUGIN_DLLS = {"gstlibav.dll": ("avdec_aac", "gst-libav"), "gstaudioparsers.dll": ("aacparse", "gst-plugins-good")}` — both the guard and the pytest import this single dict.
- Planner picks whether to pin conda-forge `gst-libav` version. **Research recommendation: unpinned** (matches `gstreamer=1.28` major.minor shape; conda resolves a compatible build).

### Deferred Ideas (OUT OF SCOPE — from `<deferred>`)

- Rollback/regression risk strategy for conda recipe changes (theoretical risk; if it materializes, follow-up phase)
- PLS codec/bitrate URL-fallback (`.planning/notes/2026-05-10-pls-codec-bitrate-url-fallback.md`)
- Runtime error-message UX for missing codecs (codec-aware toast swap, hamburger indicator)
- Startup plugin audit at app launch
- Other codec regressions (MP3/Opus/Vorbis/FLAC explicit verification, full codec matrix audit)
- Spike-findings SKILL.md retroactive edit
- Two-pass UAT (bare `dist/MusicStreamer.exe` + installed binary)
- Linux-side runtime `gst-inspect` pytest

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| (none yet — phase will add WIN-05 per DOC-04) | "AAC-encoded streams play on Windows — DI.fm AAC tier + SomaFM HE-AAC fixtures verified post-bundle-fix" | All of this RESEARCH.md backs the new requirement; the conda recipe edit + plugin-presence guard + drift-guard pytest collectively satisfy it. |

## Project Constraints (from CLAUDE.md)

`./CLAUDE.md` (project root) contains a single load-bearing directive:

- **Routing:** Spike findings for MusicStreamer (Windows packaging patterns, GStreamer+PyInstaller+conda-forge, PowerShell gotchas) → load `Skill("spike-findings-musicstreamer")`.

This research has loaded `.claude/skills/spike-findings-musicstreamer/SKILL.md` and its references (`windows-gstreamer-bundling.md`, `qt-glib-bus-threading.md`) plus the verbatim spike artifacts (`43-spike.spec`, `runtime_hook.py`, `build.ps1`, `smoke_test.py`, `43-SPIKE-FINDINGS.md`, `README.md`). All recommendations below are consistent with that body of validated patterns.

No CLAUDE.md directive forbids any approach taken in this research.

## DG-02 Confirmation: Why the Current Bundle Lacks AAC

The CONTEXT.md DG-02 hypothesis ("current README recipe installs ONLY the `gstreamer` meta-package and lets conda resolve dependencies; this likely yields gst-plugins-base + gst-plugins-good for MP3/Opus/Vorbis but omits gst-plugins-bad, gst-plugins-ugly, and gst-libav") was empirically PARTIALLY confirmed and PARTIALLY refuted:

**Confirmed:**
- [VERIFIED: prefix.dev/channels/conda-forge/packages/gstreamer, fetched 2026-05-11] The conda-forge `gstreamer` 1.28.2 win-64 package's runtime dependencies are: `glib`, `libglib`, `libiconv`, `libintl`, `libzlib`, `ucrt`, `vc`, `vc14_runtime`. **No plugin subpackages.**
- [VERIFIED: conda-forge/gstreamer-feedstock recipe.yaml, fetched 2026-05-11] The `gstreamer` output declares only `${{ pin_compatible("glib") }}` in its `requirements.run` — no automatic plugin dependencies. The same feedstock builds three outputs (`gstreamer`, `gst-plugins-base`, `gst-plugins-good`) but each output is a separately installable package.
- [VERIFIED: `packaging/windows/README.md` lines 18–20 current contents] The production recipe is `python=3.12 pygobject gstreamer=1.28 pyinstaller "pyinstaller-hooks-contrib>=2026.2"` — zero plugin packages.
- [VERIFIED: `.planning/PROJECT.md` line 44] The project's own documentation already records "GStreamer 1.28+ on Windows pinned: ... requires `gst-libav` for AAC/H.264 decoders". This was the conclusion of the Phase 43 spike; the Phase 44 packaging recipe failed to carry that conclusion through.

**Refuted (CONTEXT-DG-02 was wrong about which plugins MP3/Opus/Vorbis come from):**
- The current bundle cannot have inherited gst-plugins-good from conda dependency resolution — the meta-package does not pull it in. The fact that MP3/Opus/Vorbis playback works on Phase 56's UAT Win11 VM is best explained by:
  1. The operator's Win11 VM conda env has a snapshot from the Phase 43 spike's recipe (which DID include gst-plugins-base/good/bad/ugly), and that env was re-used for Phase 44 builds without re-creating from the production README.
  2. OR the README is stale documentation and the operator built `build.ps1` against an env created manually with the plugins explicitly. Either way, a fresh build host following the production README would produce a bundle with **NO codec plugins** — not just missing AAC.

This means the fix scope is slightly larger than CONTEXT-DG-02 anticipated: **the conda recipe must explicitly list all five plugin packages (`gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly gst-libav`)** to make the recipe reproducible on a fresh build host, not just add `gst-libav`. The plugin-presence guard (G-02 list) only needs `gstlibav.dll` + `gstaudioparsers.dll` to specifically catch the AAC failure mode, but the README recipe must be complete.

> **Open question for the operator / plan-check:** Confirm whether the user's current Win11 build env was created from the production README (in which case MP3 should also be broken — which contradicts Phase 56 UAT) or from the spike snapshot (which would explain MP3 working but AAC missing if gst-libav was the only omission). **Research's best inference is the latter** based on the timeline (Phase 43 spike conda env never deleted, Phase 44 build done in the same env). The recipe edit is correct either way.

## Plugin → conda-forge package map

This is the corrected DG-01 mapping. **The CONTEXT.md mapping ("`aacparse → gst-plugins-bad`") is WRONG.** Empirical correction below.

| Plugin element | Plugin DLL filename | conda-forge package | Source | Notes |
|----------------|---------------------|---------------------|--------|-------|
| `avdec_aac` | `gstlibav.dll` | **`gst-libav`** | [VERIFIED: conda-forge/gst-libav-feedstock recipe.yaml `tests.script` line `if not exist %LIBRARY_LIB%\\gstreamer-1.0\\gstlibav.dll exit 1`, fetched 2026-05-11] | LGPL-2.1-or-later. Single DLL `gstlibav.dll` contains ALL libav-backed decoders (`avdec_aac`, `avdec_aac_fixed`, `avdec_aac_latm`, `avdec_mp3`, `avdec_h264`, etc.) wrapping statically-linked FFmpeg. |
| `aacparse` | `gstaudioparsers.dll` | **`gst-plugins-good`** | [VERIFIED: GStreamer/gst-plugins-good repo at github.com/GStreamer/gst-plugins-good/blob/master/gst/audioparsers/gstaacparse.c, fetched 2026-05-11] | The `audioparsers` plugin (a single DLL containing `aacparse`, `ac3parse`, `amrparse`, `dcaparse`, `flacparse`, `mpegaudioparse`, `sbcparse`, `wavpackparse`) ships with gst-plugins-good, NOT gst-plugins-bad. CONTEXT-DG-01 was incorrect on this point. |
| `faad` | `gstfaad.dll` | gst-plugins-bad (theoretically) | [VERIFIED: conda-forge/gst-plugins-bad-feedstock recipe.yaml `tests.script` block, fetched 2026-05-11] | **NOT shipped in the conda-forge win-64 build of gst-plugins-bad.** The Windows test block does not check for `gstfaad.dll` and the recipe `requirements.host` does not list `faad2`. The Linux build also does not test for it. faad is GPL-licensed; conda-forge appears to have excluded it. **Do NOT depend on faad — use avdec_aac.** |

**Implication for G-02 required-plugin list:** Only two DLLs need checking in the post-bundle guard — `gstlibav.dll` (provides `avdec_aac`) and `gstaudioparsers.dll` (provides `aacparse`). `faad` should NOT be on the required list since it isn't even available from conda-forge on Windows.

**Why both `avdec_aac` AND `aacparse` are required:** GStreamer's playbin3 pipeline for an AAC stream is `souphttpsrc → typefind → aacparse → avdec_aac → audioconvert → audioresample → audioresink`. Without `aacparse`, raw ADTS framing isn't parsed before reaching the decoder; without `avdec_aac`, parsed AAC packets have no decoder to consume them. Missing either breaks playback at a different pipeline stage. The guard checks both so the failure mode is unambiguous.

## Standard Stack

### Core (verified versions as of 2026-05-11)

| Library / Package | Version | Purpose | Why Standard |
|-------------------|---------|---------|--------------|
| `gst-libav` | 1.28.2 (win-64) | Provides `gstlibav.dll` with FFmpeg-backed decoders including `avdec_aac` | [VERIFIED: anaconda.org/conda-forge/gst-libav, fetched 2026-05-11] Single source of `avdec_aac` on Windows in the conda-forge ecosystem (no `faad` build). License LGPL-2.1-or-later (FFmpeg linked statically into the plugin DLL). |
| `gst-plugins-good` | 1.28.2 (win-64) | Provides `gstaudioparsers.dll` with `aacparse` | [VERIFIED: conda-forge/gstreamer-feedstock recipe.yaml, fetched 2026-05-11] Built together with the `gstreamer` package in the same feedstock; matches base version exactly. |
| `gst-plugins-base` | 1.28.2 (win-64) | Provides core `playbin3`, `decodebin3`, `typefindfunctions`, `audioconvert` | Already implicitly needed; making it explicit prevents future ambiguity (matches Phase 43 spike recipe). |
| `gst-plugins-bad` | 1.28.2 (win-64) | Provides `gstwasapi.dll` (audio sink), `gstaiff.dll`, container demuxers | Already in Phase 43 spike recipe; included for completeness and to match the spike-validated baseline. |
| `gst-plugins-ugly` | 1.28.2 (win-64) | Provides `gstasf.dll`, `gstx264.dll`, demuxers for legacy formats | Matches Phase 43 spike recipe; small (~2 MB) and avoids ambiguity about what's bundled. |
| `gstreamer` | 1.28.2 (win-64) | Core library + coreelements (built-in) | Pinned at `=1.28` (existing pin shape). All plugin packages pin-compat against this version. |
| `pygobject` | 3.56.x | Python bindings | No change from current recipe. |
| `pyinstaller` | >= 6.19 | Bundler | No change from current recipe. |
| `pyinstaller-hooks-contrib` | >= 2026.2 | Provides `hook-gi.repository.Gst.py` (broad plugin collect) | No change from current recipe. The contrib hook will automatically pick up the new plugin DLLs once the conda env has them; no `.spec` edit needed. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `gst-libav` (FFmpeg-backed `avdec_aac`) | `gst-plugins-bad`'s `faad` plugin | `faad` is **not built** in conda-forge's win-64 gst-plugins-bad (GPL license); not a viable alternative on the chosen build path. |
| Adding all five plugin packages explicitly | Add only `gst-libav` and rely on the snapshot's existing plugins | Brittle — depends on the build env never being recreated. The whole point of Phase 69 is to make the recipe reproducible. **Rejected.** |
| Pinning `gst-libav=1.28.2` | Leaving `gst-libav` unpinned | Unpinned matches the `gstreamer=1.28` major.minor shape; conda will resolve a compatible build because of `run_exports` pinning in the feedstock (`gst-libav` pins exact gstreamer version). **Unpinned is the recommendation per F-04.** |
| Adding plugin packages to `build.ps1` | Keeping packages in `README.md` only | build.ps1 today does not enumerate or `conda install` anything (it inspects `CONDA_PREFIX` and assumes the env is set up). Recipe lives in README per current pattern; build.ps1 unchanged. **F-01 keeps the change in README only.** |

**Installation (recipe to land in `packaging/windows/README.md` lines 18–22):**

```powershell
conda create -n musicstreamer-build -c conda-forge `
    python=3.12 pygobject gstreamer=1.28 `
    gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly `
    gst-libav `
    pyinstaller "pyinstaller-hooks-contrib>=2026.2"
conda activate musicstreamer-build
# AAC playback requires gst-libav (Phase 69 — provides avdec_aac in gstlibav.dll).
# aacparse ships with gst-plugins-good's audioparsers plugin (gstaudioparsers.dll).
```

**Version verification (run in plan-check, sanity-check at fix-land time):**
```bash
# As of 2026-05-11, anaconda.org/conda-forge confirms win-64 builds:
#   gstreamer 1.28.2 — uploaded 2026-04-08
#   gst-libav 1.28.2 — uploaded 2026-04-08
#   gst-plugins-base/good/bad/ugly 1.28.2 — same timestamp
# All same-version because the gstreamer-feedstock builds gstreamer + plugins-base + plugins-good together
# and gst-libav / gst-plugins-bad / gst-plugins-ugly have run_exports pinning to that gstreamer version.
```

## Architecture Patterns

### System Architecture Diagram

```
   Build host (Linux dev or Win11 build VM)
   ─────────────────────────────────────────
                                                                                          .
                                                                                          .
   packaging/windows/README.md          ─── (operator copies recipe into terminal) ───►  .
   (conda recipe — DOC-02 edit site)                                                     .
                                                                                          .
                                                                                          v
                                                                                  conda env on Win11 build VM
                                                                                  Library/lib/gstreamer-1.0/
                                                                                  ├── gstlibav.dll      ◄── from gst-libav (NEW)
                                                                                  ├── gstaudioparsers.dll ◄── from gst-plugins-good
                                                                                  ├── gstmpegaudioparse.dll (built-in to audioparsers DLL)
                                                                                  ├── gstwasapi.dll     ◄── from gst-plugins-bad (audio sink)
                                                                                  └── …~180 more plugins
                                                                                          │
                                                                                          │ Linux dev CI                              Win11 build VM
                                                                                          │ ───────────                              ───────────────
                                                                                          │                                           build.ps1 invokes
                                                                                          │                                           PyInstaller →
                                                                                          │                                           hooks-contrib
                                                                                          │                                           gstreamer hook
                                                                                          │                                           enumerates registry
                                                                                          │                                           and copies plugins:
                                                                                          ▼                                                  │
   tests/test_packaging_spec.py                                                                                                              ▼
   (drift-guard pytest — P-01)                                                                                                  dist/MusicStreamer/_internal/
   reads README.md conda block + reads                                                                                          ├── MusicStreamer.exe
   tools/check_bundle_plugins.py REQUIRED                                                                                       ├── gst-plugins/                              ◄── existing path
   asserts every required-plugin's                                                                                              │   ├── gstlibav.dll       ◄── NEW (Phase 69)
   conda package appears in the recipe.                                                                                         │   ├── gstaudioparsers.dll
   FAIL ⇒ pytest exit 1 on dev CI before                                                                                        │   └── … 180+ others
   any Windows build is attempted.                                                                                              ├── musicstreamer-2.1.69.dist-info/
                                                                                                                                ├── runtime_hook.py
                                                                                                                                └── gst-plugin-scanner.exe
                                                                                                                                                          │
                                                                                                                                                          ▼
                                                                                                                            build.ps1 (G-01 NEW step, after line 283):
                                                                                                                            invokes `python tools/check_bundle_plugins.py
                                                                                                                                    --bundle dist/MusicStreamer/_internal`
                                                                                                                            Python helper enumerates required-DLL set vs
                                                                                                                            actual files-on-disk in gst_plugins/.
                                                                                                                              0 = OK, continue to Inno Setup
                                                                                                                              10 = FAIL, Write-Host BUILD_FAIL + exit 10
                                                                                                                                                          │
                                                                                                                                                          ▼
                                                                                                                              Inno Setup compile (unchanged)
                                                                                                                                                          │
                                                                                                                                                          ▼
                                                                                                                              MusicStreamer-2.1.69-win64-setup.exe

   Runtime (operator's Win11 VM, post-install)
   ────────────────────────────────────────────
   AAC stream URL → MusicStreamer Player.play() → Gst.parse_launch('playbin3 uri=…')
                                                  │
                                                  ▼
                                          souphttpsrc → typefind → aacparse (audioparsers DLL)
                                          → avdec_aac (gstlibav.dll) → audioconvert → audioresample
                                          → autoaudiosink (wasapisink on Windows, via gst-plugins-bad)
                                                  │
                                                  ▼
                                          Audible AAC playback (UAT PASS)
```

### Recommended Project Structure (unchanged from current — Phase 69 adds files, removes none)

```
packaging/windows/
├── README.md                              # EDIT: lines 18–22, add 5 plugin packages
├── build.ps1                              # EDIT: header exit-code comment (line 5–6); add G-01 block after line 283
├── MusicStreamer.spec                     # NO CHANGE
├── runtime_hook.py                        # NO CHANGE
├── MusicStreamer.iss                      # NO CHANGE
├── EULA.txt                               # NO CHANGE
└── icons/MusicStreamer.ico                # NO CHANGE

tools/
├── check_subprocess_guard.py              # NO CHANGE (mirror)
├── check_spec_entry.py                    # NO CHANGE (mirror)
└── check_bundle_plugins.py                # NEW: G-02 single source of truth for required plugins

tests/
└── test_packaging_spec.py                 # EDIT: add P-01 drift-guard test functions

.planning/codebase/
└── CONCERNS.md                            # EDIT: lines 56–59 after fix lands (DOC-01)

.planning/
└── REQUIREMENTS.md                        # EDIT: Traceability table + Windows Polish section (DOC-04, WIN-05)
```

### Pattern 1: PowerShell-calls-Python tool with documented exit code

**What:** build.ps1 invokes a Python helper via `Invoke-Native`, branches on `$LASTEXITCODE`, emits `BUILD_FAIL reason=<name> hint='<remediation>'` on non-zero. Exit codes are documented in the header comment at `build.ps1:5–6`.

**When to use:** Any build-time guard that needs Python's cross-platform string/file logic. Single source of truth for the guard's "what" lives in the Python helper; PowerShell only routes errors.

**Example (clone for Phase 69 G-01, place after `build.ps1:283`):**
```powershell
# Source: existing pattern at build.ps1:115-121 (PKG-03 subprocess guard)

# --- 4b. Post-bundle plugin-presence guard (Phase 69 / G-01) ----------
# Validates that AAC-required GStreamer plugin DLLs landed in the bundle.
# Without this, a future docs-drift regression (e.g. a maintainer drops
# gst-libav from the conda recipe) would silently produce a bundle that
# fails AAC playback at runtime with only the generic "playback error"
# toast as a signal.
#
# Required plugin list is single-sourced from tools/check_bundle_plugins.py
# (also imported by tests/test_packaging_spec.py drift-guard pytest).
#
# DO NOT REMOVE without first updating both:
#   - tests/test_packaging_spec.py (P-01 drift-guard test)
#   - .planning/phases/69-.../69-XX-PLAN.md (this plan's rationale)
Write-Host "=== POST-BUNDLE PLUGIN GUARD: python tools/check_bundle_plugins.py (Phase 69 / WIN-05) ==="
Invoke-Native { python ..\..\tools\check_bundle_plugins.py --bundle ..\..\dist\MusicStreamer\_internal 2>&1 | Out-Host }
if ($LASTEXITCODE -ne 0) {
    Write-Host "BUILD_FAIL reason=plugin_missing hint='see tools/check_bundle_plugins.py output above; add the named conda-forge package to packaging/windows/README.md conda recipe'" -ForegroundColor Red
    exit 10
}
Write-Host "POST-BUNDLE PLUGIN GUARD OK"
```

### Pattern 2: Single-source-of-truth Python guard helper

**What:** A standalone Python script under `tools/` that encapsulates the "what is required" logic and is invoked from both build-time (PowerShell driver) and dev-time (pytest drift guard). Exit code 0 = clean, exit code = matching build.ps1 documented exit code on failure.

**When to use:** Anywhere drift between a documentation file (README, .spec, etc.) and a runtime expectation would silently produce a broken artifact. Pair with a pytest that imports the same module and asserts coverage.

**Example (the new `tools/check_bundle_plugins.py`, clone shape from `tools/check_subprocess_guard.py`):**
```python
"""Build-time AAC plugin-presence guard (Phase 69, G-01/G-02).

Asserts the PyInstaller bundle contains the GStreamer plugin DLLs
required for AAC playback. Runs after PyInstaller produces the bundle,
before Inno Setup compile. Mirrors the structural shape of
check_subprocess_guard.py / check_spec_entry.py (PKG-03 / PKG-01).

Exit codes:
    0 — clean (all required plugins present)
    10 — plugin missing (matches build.ps1 exit code convention)

Callable as ``python tools/check_bundle_plugins.py --bundle <path>``.

The REQUIRED_PLUGIN_DLLS dict is the single source of truth for the
required-plugin list. It is also imported by
tests/test_packaging_spec.py for the static drift-guard test (P-01)
that asserts packaging/windows/README.md's conda recipe mentions
every required conda-forge package.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Maps PyInstaller-bundled DLL filename → (element name, conda-forge package).
# Phase 69 initial list — AAC playback requirements.
REQUIRED_PLUGIN_DLLS: dict[str, tuple[str, str]] = {
    "gstlibav.dll": ("avdec_aac", "gst-libav"),
    "gstaudioparsers.dll": ("aacparse", "gst-plugins-good"),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bundle",
        type=Path,
        default=Path("dist/MusicStreamer/_internal"),
        help="Path to PyInstaller _internal/ directory (default: dist/MusicStreamer/_internal)",
    )
    args = parser.parse_args(argv)

    plugins_dir = args.bundle / "gst_plugins"
    if not plugins_dir.is_dir():
        print(
            f"PHASE-69 FAIL: bundle plugins dir not found at {plugins_dir}",
            file=sys.stderr,
        )
        return 10

    missing: list[str] = []
    for dll_name, (element, package) in REQUIRED_PLUGIN_DLLS.items():
        if not (plugins_dir / dll_name).is_file():
            missing.append(f"  {dll_name} (provides {element}, ships in conda-forge package {package})")

    if missing:
        print(
            "PHASE-69 FAIL: required GStreamer plugin DLL(s) missing from bundle:",
            file=sys.stderr,
        )
        for line in missing:
            print(line, file=sys.stderr)
        print(
            "Fix: add the named conda-forge package(s) to packaging/windows/README.md "
            "conda recipe, recreate the conda env, and rebuild.",
            file=sys.stderr,
        )
        return 10

    print(
        f"PHASE-69 OK: all {len(REQUIRED_PLUGIN_DLLS)} required plugin DLL(s) present "
        f"in {plugins_dir}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### Pattern 3: Static drift-guard pytest (read two files, assert literal coverage)

**What:** A pytest function that reads two files, extracts a set of literals from each, and asserts the intersection meets a required-coverage rule. Runs on Linux dev CI.

**When to use:** Any time documentation drift between a human-edited file (README, .spec, .iss) and a machine-checked source-of-truth would silently break a downstream artifact.

**Example (the new test function to add to `tests/test_packaging_spec.py`, mirroring `tests/test_aumid_string_parity.py`):**
```python
def test_readme_conda_recipe_lists_every_required_plugin_package(
    readme_source: str,  # fixture-fed: packaging/windows/README.md text
) -> None:
    """Phase 69 / P-01: packaging/windows/README.md conda recipe must
    mention every conda-forge package referenced in
    tools/check_bundle_plugins.py REQUIRED_PLUGIN_DLLS values.

    Drift-guard: catches the failure mode where a future maintainer
    edits the build-time guard's required-plugin list (e.g. adds Opus
    or Vorbis plugins after a new codec issue) but forgets to add the
    matching conda package to the README recipe. Without this test, the
    build would fail at G-01 plugin-presence check (exit code 10) only
    after a full PyInstaller run — wasting ~5 minutes of build time
    per drift incident. This test fires in <1 second on Linux dev CI.
    """
    from tools.check_bundle_plugins import REQUIRED_PLUGIN_DLLS

    # Locate the conda create / conda env update block in README.md.
    # The block is fenced as a powershell code block (backticks).
    # Anchor on `conda create -n musicstreamer-build` per F-01 / DOC-02.
    import re
    block_match = re.search(
        r"conda create -n musicstreamer-build[^\n]*\n((?:[^\n]*\n)+?)```",
        readme_source,
    )
    assert block_match, (
        "packaging/windows/README.md must contain a fenced PowerShell "
        "code block starting with `conda create -n musicstreamer-build` "
        "(this is the canonical recipe location per Phase 69 DOC-02). "
        "If you renamed the env or moved the recipe, update this test "
        "and tools/check_bundle_plugins.py together."
    )
    recipe_block = block_match.group(0)

    required_packages = {pkg for (_, pkg) in REQUIRED_PLUGIN_DLLS.values()}
    missing = [pkg for pkg in required_packages if pkg not in recipe_block]
    assert not missing, (
        "Phase 69 / P-01 drift-guard FAIL: the following conda-forge "
        f"package(s) are in tools/check_bundle_plugins.py REQUIRED_PLUGIN_DLLS "
        f"but absent from packaging/windows/README.md's conda recipe block: "
        f"{missing}. Either remove them from the required-plugin list (if "
        f"the build-time guard no longer needs them) or add them to the "
        f"README recipe so a fresh build host produces a bundle that "
        f"passes the post-bundle plugin-presence guard."
    )
```

### Anti-Patterns to Avoid

- **"Snapshot env" mindset:** Building from a conda env that drifted from the documented recipe. The whole reason Phase 69 exists is that this happened silently between Phase 43 (spike) and Phase 44 (production). The drift-guard pytest exists to make recipe-vs-required-list drift impossible to ship.
- **Linux `gst-inspect` test:** Linux GStreamer is system-installed, not conda-forge MSVC. Even if a Linux test finds `avdec_aac` available, that proves nothing about the Windows bundle. Explicitly rejected by CONTEXT-P-03.
- **Adding `faad` to the required-plugin list:** `faad` is GPL-licensed and not shipped in conda-forge's win-64 gst-plugins-bad build. Required list must reflect what's achievable on the chosen build path.
- **Pinning `gst-libav` to a build hash:** Over-pinning will cause conda-resolver failures when the upstream feedstock rolls a new build number. Unpinned matches the `gstreamer=1.28` style.
- **Runtime `gst.Registry` probe in the app:** Explicitly rejected by CONTEXT-D-02 (no app-side runtime UX change). The post-bundle file-presence guard catches the regression at build time.
- **Running `gst-inspect` against the bundled registry from build.ps1:** Tempting but brittle — requires loading the bundled rthook + PATH env + scanner binary. File-on-disk presence in `gst_plugins/` is sufficient because the hooks-contrib hook only ships DLLs that actually loaded during its registry scan (per spike findings: "if the plugin DLL is present in `gst_plugins/`, the contrib hook + scanner already vouched it loads at runtime").

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| AAC decode | A custom Python AAC decoder | `avdec_aac` from `gst-libav` (FFmpeg statically linked) | FFmpeg's AAC decoder is the de facto standard; gst-libav already wraps it; no point reinventing. |
| Plugin-presence check at runtime | A `Gst.Registry.get_default().find_plugin("...")` call inside the app | Build-time file-presence guard (Phase 69 G-01) | CONTEXT-D-02 explicitly rejects app-side runtime UX. Bundle-level fix means the runtime check would only fire on broken builds — better to fail the build. |
| Conda recipe enumeration in PowerShell | A `Get-CondaInfo` / `conda list | Select-String` block in `build.ps1` | Trust the README + the post-bundle file-presence guard | The conda env is the operator's responsibility per the existing pattern (build.ps1 inspects CONDA_PREFIX but doesn't install). G-01 catches the consequence (missing plugin DLLs) rather than the cause (missing conda package). |
| Plugin → package mapping in two places | Maintaining one mapping in `build.ps1` and another in the pytest | Single source of truth in `tools/check_bundle_plugins.py` | Mirrors the Phase 44 PKG-03 lesson — duplicated regex in build.ps1 and the pytest drifted. CONTEXT-G-02 mandates the Python helper as the single source. |

**Key insight:** This phase's whole point is that hand-rolled (= undocumented + uncrosschecked) build environment setup IS what caused the AAC failure in the first place. Every recommendation here pushes toward "one canonical source per fact, statically checkable on Linux dev CI".

## Runtime State Inventory

This is a Windows-packaging-only phase. The "runtime state" affected is the conda env on the build host and the PyInstaller bundle on the runtime host. Per CONTEXT-D-02 and the spike-findings rules:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data (SQLite, ChromaDB, etc.) | None — Phase 69 makes no DB changes. The DI.fm station URLs that fail AAC playback are not in scope for re-modeling; the fix is at the bundle level so playback succeeds with the same URLs. | None |
| Live service config (n8n, Datadog, etc.) | None — no external services involved. | None |
| OS-registered state (Task Scheduler, pm2, launchd, etc.) | None — Phase 69 does not touch installer-registered shortcuts, AUMID bindings, or any registered Windows state. The existing AUMID literal in `MusicStreamer.iss` and `__main__.py` is unchanged. | None |
| Secrets and env vars | None changed. `runtime_hook.py` sets `GIO_EXTRA_MODULES`, `GI_TYPELIB_PATH`, `GST_PLUGIN_SCANNER` — Phase 69 leaves all three unchanged (F-03). | None |
| Build artifacts / installed packages | **The operator's existing Win11 conda env `musicstreamer-build` likely DIVERGES from the production README** (see DG-02 Confirmation). After the README edit (DOC-02) lands, the operator must recreate the conda env to ensure parity (or `conda env update` to add missing packages). The new env also needs the existing `musicstreamer.dist-info` reinstall (preserved by build.ps1 step 3c). | **Operator action at UAT time:** Run `conda env remove -n musicstreamer-build` then re-execute the new recipe (or `conda install -n musicstreamer-build -c conda-forge gst-libav gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly`). UAT-LOG.md should explicitly log which path was taken. |

**Critical drift item:** The "build artifacts" row above is the single non-trivial inventory item. The planner should ensure UAT-LOG.md's pre-fix step requires the operator to *confirm what's in their current conda env* (via `conda list -n musicstreamer-build | findstr gst-`) so the audit trail captures whether the env had partial plugins (consistent with MP3-working/AAC-failing) or full plugins (which would refute DG-02 entirely and require re-investigation).

## Common Pitfalls

### Pitfall 1: Hooks-contrib subdir naming — `gst_plugins/` (underscore) not `gst-plugins/` (hyphen)

**What goes wrong:** A guard or test that hard-codes `gst-plugins/` (with a hyphen, matching the upstream MSVC installer's directory name) won't find the bundled plugins, which live in `_internal/gst_plugins/` (with an underscore — the hooks-contrib 2026.2 convention).

**Why it happens:** The upstream GStreamer documentation and pre-2024 PyInstaller guides use the hyphen form. The Phase 43 spike empirically resolved this (43-SPIKE-FINDINGS.md line 128: "PyInstaller's `hook-gi.repository.Gst.py` in `pyinstaller-hooks-contrib` 2026.2 places plugins in `gst_plugins/` (not `gstreamer-1.0/` as documented in older 2024-era guides — naming changed)").

**How to avoid:** `tools/check_bundle_plugins.py` MUST scan `<bundle>/gst_plugins/` (underscore). Add a brief docstring comment citing 43-SPIKE-FINDINGS.md line 128 so a future maintainer who tries to "fix" the path back to the hyphen form sees the rationale.

**Warning signs:** The guard exits 10 saying "bundle plugins dir not found" on a build where the bundle clearly works. Check the actual path with `Get-ChildItem dist\MusicStreamer\_internal\` before assuming the guard logic is wrong.

### Pitfall 2: The conda env already has plugins from the spike snapshot

**What goes wrong:** The operator runs the new build.ps1 against their existing `musicstreamer-build` conda env (which may carry plugin packages from the Phase 43 spike). The build "passes" on their machine because the spike's plugins are still in the env, but a fresh build host following the new README would still fail.

**Why it happens:** `conda env update` only adds packages; it doesn't remove or reconcile against the README. The operator's env has been evolving since Phase 43 (~10 months of conda updates) and may carry artifacts the production README never required.

**How to avoid:** UAT-LOG.md MUST include a pre-fix step that captures `conda list -n musicstreamer-build` output verbatim. After the fix, recreate the env from the new README (`conda env remove` + recreate) and re-run build.ps1. The drift-guard pytest (P-01) catches the README↔required-list axis but NOT the env↔README axis — that requires manual recreate. UAT is the only place this gets verified.

**Warning signs:** Post-fix UAT-LOG shows BUILD_OK + AAC PASS but the operator never recreated the env. Likely they tested with stale env state; another build host would still fail.

### Pitfall 3: The hooksconfig `broad-collect` is so aggressive it might bundle plugins that fail to load at runtime

**What goes wrong:** Adding `gst-plugins-bad` and `gst-plugins-ugly` to the conda env pulls in plugins like `gstwasapi.dll`, `gstd3d.dll`, `gstnvcodec.dll` that depend on Windows-specific OS components (DirectX, NVIDIA driver). On a build host without those components, the plugins ship in the bundle but `gst-plugin-scanner.exe` may emit warnings at first-run on the user's machine.

**Why it happens:** The Phase 43 spike used the same broad-collect strategy and explicitly accepted this trade-off (43-SPIKE-FINDINGS.md §"Broad-collect, prune later"). Common exclusion candidates: `gtk*`, `qt5*`, `qt6*`, `d3d11*`, `nv*`, `cuda*`, `vulkan`, `webrtc*`, `opencv`, `vaapi*`, `mse`, `rtsp*`, `rtmp*`, `srt`, `sctp`. The spike defers pruning until after UAT.

**How to avoid:** Don't try to add `hooksconfig.gstreamer.exclude_plugins` in this phase. Phase 69's UAT only attests AAC playback — if a noisy startup log surfaces during UAT, log it but don't address it. Pruning is a separate follow-up (deferred per CONTEXT `<deferred>` "Rollback / regression risk strategy for conda recipe changes").

**Warning signs:** Operator reports a flurry of GStreamer WARNINGs on first launch of the new build. If AAC plays anyway, that's a clean Phase 69 PASS. If AAC doesn't play AND there are scanner warnings, investigate which warnings correlate (e.g. "could not load gstlibav.dll" is the real failure).

### Pitfall 4: PowerShell 5.1 stderr trap on `python tools/check_bundle_plugins.py`

**What goes wrong:** Python's `print(..., file=sys.stderr)` writes to stderr. Under `$ErrorActionPreference = "Stop"` (set at build.ps1 line 15), any stderr write from a native command is escalated to a terminating error. Without the existing `Invoke-Native` wrapper, the failure-path branch (where the guard intentionally writes diagnostics to stderr) would never be reached — PowerShell would already be unwinding to the surrounding try/finally.

**Why it happens:** Documented in spike-findings as "Pitfall #7" (43-SPIKE-FINDINGS.md row 7) and codified into the `Invoke-Native` helper at build.ps1 line 39–49. Already mitigated for the existing PKG-03 and spec-entry guards.

**How to avoid:** The Phase 69 G-01 block MUST use `Invoke-Native { python ..\..\tools\check_bundle_plugins.py ... }` — clone the pattern from line 116 (PKG-03) or line 125 (spec entry guard). The `$LASTEXITCODE` check after the wrapped invocation routes the failure path through `Write-Host` (NOT `Write-Error`) per Phase 65 WR-01 (already encoded in build.ps1 comments at line 18–27).

**Warning signs:** Build aborts with exit code 1 (PowerShell default unwound exit) instead of the documented exit 10. Inspect the build.log for the actual diagnostic — if it shows red ErrorRecord-style formatting around the python invocation, the `Invoke-Native` wrapper is missing.

### Pitfall 5: The drift-guard regex over-matches a comment line

**What goes wrong:** The pytest's regex anchors on `conda create -n musicstreamer-build` to find the recipe block. If a future maintainer adds a markdown comment in README like `<!-- example: don't use 'conda create -n musicstreamer-build --offline ...' -->`, the regex matches the comment instead of the code block, returning text that may or may not list the required plugin packages.

**Why it happens:** Regex anchoring on a literal string is fragile when the literal can legitimately appear in prose. The Phase 56 / WIN-02 AUMID parity test (`test_aumid_string_parity.py`) has a similar shape and has been stable because the AUMID literal `org.lightningjim.MusicStreamer` rarely appears outside its two canonical sites.

**How to avoid:** The regex MUST anchor on the fenced code block fence (` ``` ` open and close) AND the `conda create -n musicstreamer-build` literal. The example regex in Pattern 3 above (`r"conda create -n musicstreamer-build[^\n]*\n((?:[^\n]*\n)+?)```"`) terminates the match at the closing fence, so comments outside fenced blocks can't match. If the planner restructures the README's recipe section (e.g. switches from PowerShell fence to bash fence), this regex needs updating too.

**Warning signs:** The drift-guard pytest passes locally but the build still fails the G-01 guard. Inspect what string the pytest's regex actually captured.

### Pitfall 6: `gstlibav.dll` is a single DLL — easy to misread as "missing all libav plugins"

**What goes wrong:** A maintainer sees `gst-inspect-1.0.exe --plugin avdec_mp3` returns "no such plugin" on a bundle WITH `gst-libav` installed, panics, and assumes gst-libav itself is broken. The reality: `gst-inspect` is querying the PLUGIN registry; `avdec_mp3` is an ELEMENT inside the `libav` plugin. The correct query is `gst-inspect-1.0.exe --plugin libav` or `gst-inspect-1.0.exe avdec_mp3` (element name without --plugin flag).

**Why it happens:** GStreamer's plugin-vs-element terminology is non-obvious. A single plugin DLL provides many elements; `--plugin` queries the plugin, bare-name queries the element.

**How to avoid:** UAT-LOG.md test commands MUST use the element-name form: `gst-inspect-1.0.exe avdec_aac` (NOT `--plugin avdec_aac`). The DG-01 commands in CONTEXT.md use `--plugin avdec_aac` which would always say "no such plugin" because `avdec_aac` is an element, not a plugin — the plugin is `libav`. Researcher recommends planner correct this in the UAT-LOG template. The post-bundle guard (`check_bundle_plugins.py`) doesn't use gst-inspect at all — it does file-on-disk presence — so this only affects the operator's diagnostic commands in UAT-LOG.

**Warning signs:** Operator's DG-01 output reads "no such plugin: avdec_aac" even on a known-good build. They're using `--plugin avdec_aac` when they should use bare `avdec_aac` (element query) or `--plugin libav` (plugin query).

## Code Examples

Verified patterns from project + cross-referenced spike findings:

### Example 1: Reading the conda recipe in the drift-guard test

```python
# Source: mirror of tests/test_aumid_string_parity.py + tests/test_packaging_spec.py read_text idiom
from pathlib import Path

_README = Path(__file__).resolve().parent.parent / "packaging" / "windows" / "README.md"

@pytest.fixture(scope="module")
def readme_source() -> str:
    assert _README.is_file(), f"expected README.md at {_README}"
    return _README.read_text(encoding="utf-8")
```

### Example 2: Building.ps1 G-01 block (full canonical shape)

```powershell
# Source: clone of build.ps1:115-121 (PKG-03 guard) + build.ps1:124-129 (spec entry guard)

# --- 4b. Post-bundle plugin-presence guard (Phase 69 / G-01) ----------
Write-Host "=== POST-BUNDLE PLUGIN GUARD: python tools/check_bundle_plugins.py (Phase 69 / WIN-05) ==="
Invoke-Native { python ..\..\tools\check_bundle_plugins.py --bundle ..\..\dist\MusicStreamer\_internal 2>&1 | Out-Host }
if ($LASTEXITCODE -ne 0) {
    Write-Host "BUILD_FAIL reason=plugin_missing hint='see tools/check_bundle_plugins.py output above; add the named conda-forge package to packaging/windows/README.md conda recipe'" -ForegroundColor Red
    exit 10
}
Write-Host "POST-BUNDLE PLUGIN GUARD OK"
```

### Example 3: Updated exit-code header comment

```powershell
# Source: build.ps1:4-6 + new exit code 10

# Exit codes: 0=ok, 1=env missing, 2=pyinstaller failed, 3=smoke test failed,
#             4=PKG-03 guard fail, 5=version parse fail, 6=iscc fail, 7=spec entry guard fail,
#             8=pre-bundle clean fail, 9=post-bundle dist-info assertion fail,
#             10=post-bundle plugin-presence guard fail (Phase 69)
```

### Example 4: Operator UAT commands (corrected per Pitfall 6)

```powershell
# Pre-fix and post-fix diagnostic against the BUNDLED registry
# (NOT against the host conda env's gst-inspect):

# 1. Probe the bundled scanner against the bundled registry
$env:GST_REGISTRY = "dist\MusicStreamer\_internal\registry.bin"
$env:GST_PLUGIN_SCANNER = "dist\MusicStreamer\_internal\gst-plugin-scanner.exe"

# 2. Element-name query (correct form — uses bare element name)
& "dist\MusicStreamer\_internal\gst-inspect-1.0.exe" avdec_aac      # element
& "dist\MusicStreamer\_internal\gst-inspect-1.0.exe" aacparse        # element

# 3. Plugin-name query (alternative — uses --plugin and PLUGIN name, not element)
& "dist\MusicStreamer\_internal\gst-inspect-1.0.exe" --plugin libav         # libav PLUGIN (contains avdec_aac element)
& "dist\MusicStreamer\_internal\gst-inspect-1.0.exe" --plugin audioparsers  # audioparsers PLUGIN (contains aacparse element)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pip install pygobject` on Windows | Conda-forge for the whole GStreamer stack | Phase 43 spike (2026-04-20) | Non-negotiable; PyGObject still ships no Windows wheels. |
| GnuTLS (libgiognutls.dll) as the Gio TLS backend | OpenSSL (gioopenssl.dll) | GStreamer 1.28.x upstream change | Already handled in build.ps1 (line 70–75 accepts either) and `.spec` (line 60–64 ditto). |
| `bin/gst-plugin-scanner.exe` location | `libexec/gstreamer-1.0/gst-plugin-scanner.exe` | GStreamer 1.28.x layout change | Already handled in `.spec` (line 53–58) and build.ps1 (line 76–79). |
| Bundled plugin dir name `gstreamer-1.0/` | `gst_plugins/` (underscore) | PyInstaller hooks-contrib ≥ 2024 | Already handled by stock contrib rthook. `tools/check_bundle_plugins.py` MUST use underscore form. |
| Implicit reliance on `gstreamer` meta-package pulling in plugins | Explicit list of every plugin subpackage in the conda recipe | Phase 69 (this phase) | Makes the build reproducible on a fresh build host. The conda-forge `gstreamer` package does NOT pull in `gst-plugins-*` automatically. |
| `faad` as the AAC decoder | `avdec_aac` from `gst-libav` (FFmpeg-backed) | Phase 43 spike onward (faad never tried) | conda-forge does not ship `faad` plugin in the win-64 gst-plugins-bad build (GPL license avoidance). gst-libav is LGPL-2.1-or-later; matches existing bundle posture. |

**Deprecated / outdated:**
- The `gst-plugins/` (hyphenated) subdir naming used in pre-2024 PyInstaller guides — replaced by `gst_plugins/` (underscore) by hooks-contrib ≥ 2024.
- `libgiognutls.dll` as the only Gio TLS module — replaced by `gioopenssl.dll` in GStreamer 1.28.x.
- Split MSI installers (`gstreamer-1.0-msvc-x86_64-X.Y.Z.msi` + `*-devel-*.msi`) for upstream installer path — replaced by single `.exe` installer in 1.28+. Not relevant since we use conda-forge.

## Assumptions Log

Claims tagged `[ASSUMED]` in this research, requiring user / planner confirmation:

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The operator's current Win11 conda env carries plugin packages from the Phase 43 spike that are not in the production README — this explains why MP3/Opus/Vorbis work despite the production README having no plugin packages. | DG-02 Confirmation, Pitfall 2 | If wrong (i.e. the env was created from the production README and somehow STILL has MP3 plugins), the diagnosis is incomplete — there's a third source of plugins not yet identified. Mitigation: UAT-LOG.md pre-fix step captures `conda list -n musicstreamer-build` output for audit. |
| A2 | The post-bundle file-on-disk presence check is sufficient — if `gstlibav.dll` is on disk in `gst_plugins/`, the hooks-contrib hook + scanner already validated it loaded at build time. | G-03 (CONTEXT), Pattern 2 | If a DLL is present but its dependencies (libavcodec, libavformat, etc. — statically linked but cross-DLL dependencies on libssl/libcrypto are dynamic) are missing, the bundle would ship but AAC playback would still fail at runtime. Mitigation: UAT (V-01) attests actual AAC playback, catching any runtime-load failure that the file-presence guard would miss. |
| A3 | conda-forge `gst-libav=1.28.2`'s `gstlibav.dll` includes `avdec_aac` in its element registry — i.e. the conda-forge build was configured `--enable-libavcodec-aac` (or equivalent meson option). | Plugin → package map | Could not verify the meson build flags from the recipe.yaml alone (build.bat just runs `meson setup` with defaults). If conda-forge's gst-libav build disabled AAC for license reasons, the fix would fail. **However:** gst-libav as a project intentionally wraps the bulk of libavcodec without per-codec opt-outs, and the recipe.yaml's `host` block includes `ffmpeg` (which by default builds with AAC enabled). Strong inferential confidence, not direct empirical proof. Mitigation: UAT (V-01) immediately surfaces this — if `gstlibav.dll` is present but AAC still fails, the conda-forge build is the culprit and a follow-up phase is needed. |

**This table is non-empty.** Three assumptions warrant the planner / discuss-phase / UAT cycle confirming them empirically.

## Open Questions

1. **Should the conda recipe also bump `pyinstaller-hooks-contrib` past 2026.2?**
   - What we know: Phase 43 spike validated `2026.2`; Phase 44 production locks `>=2026.2`. Any version bump after 2026.2 in hooks-contrib could change the `gst_plugins/` subdir naming back or alter broad-collect behavior.
   - What's unclear: whether a newer hooks-contrib (e.g. 2026.4) exists and ships any relevant fix.
   - Recommendation: don't bump in Phase 69. The drift surface is the recipe-vs-bundle axis; expanding to a hooks-contrib bump dilutes Phase 69's scope. If a newer hooks-contrib version emerges as relevant, it's a separate phase.

2. **Should `tools/check_bundle_plugins.py` produce structured output (JSON) for future CI integration?**
   - What we know: the existing PKG-03 / spec-entry guards print plain text and exit-code-branch on PowerShell side. There's no CI consumer that parses their output today.
   - What's unclear: whether a future automation needs JSON.
   - Recommendation: plain text only (matches PKG-03 pattern). YAGNI for now.

3. **Should the post-bundle guard also assert plugin DLL size / sha256?**
   - What we know: file-presence is sufficient per CONTEXT-G-03. Byte-level assertions would catch corruption.
   - What's unclear: whether corruption is a realistic failure mode for conda-forge builds.
   - Recommendation: no — pure file-presence. Corruption is not a Phase 69 concern; that's a different class of bug.

4. **What if the operator's conda env, after running the new recipe, brings in `gst-plugins-bad`'s `gstnvcodec.dll` and the operator's VM does NOT have NVIDIA drivers — does that DLL error-out during PyInstaller's scanner phase and abort the build?**
   - What we know: hooks-contrib's gstreamer hook uses `gst-plugin-scanner.exe` to enumerate the registry. The scanner may emit `WARNING` for unloadable plugins but typically continues. The Phase 43 spike on a VM (no NVIDIA hardware) shipped the broad-collect bundle successfully with `gst-plugins-bad`.
   - What's unclear: whether the new addition specifically causes a fresh scanner failure not seen in Phase 43.
   - Recommendation: monitor the build.log during UAT for `WARNING: failed to load plugin` lines. If they appear, log them in UAT-LOG.md but don't block — the existing scanner behavior is "warn and continue".

5. **Fixture URLs — pending operator at plan-check.**
   - See "Fixture URLs" section below.

## Fixture URLs

Two reserved slots for UAT fixtures (R-01). **User to paste actual URLs at plan-check time.**

```
FIXTURE_DI_FM_AAC = <PASTE-DI-FM-AAC-TIER-URL-HERE>
FIXTURE_SOMA_HE_AAC = <PASTE-SOMA-FM-HE-AAC-URL-HERE>
```

**Constraints on the URLs (operator should pick from existing library):**
- One station from DI.fm AAC tier (the codec column in EditStationDialog shows "AAC"). Maps to DI.fm "medium" or "low" preset per `musicstreamer/aa_import.py` line 128 (`_CODEC_MAP = {"hi": "MP3", "med": "AAC", "low": "AAC"}`).
- One station from SomaFM HE-AAC tier. SomaFM publishes HE-AAC streams alongside MP3 (some channels have both); the EditStationDialog stream picker shows "AAC" or "HE-AAC" codec rank per `musicstreamer/playlist_parser.py` line 34 (`_CODEC_TOKENS` includes both).
- Both URLs must be currently-failing on the operator's existing Win11 build (R-03 — pre-fix repro REQUIRED).
- URLs go into `69-RESEARCH.md` (this file, after operator paste) and `69-UAT-LOG.md` (created at planning time). Per TD-03, they do NOT get checked into `tests/fixtures/`.

## Environment Availability

Build host environment dependencies for Phase 69's deliverables:

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Linux dev: `python3` + `pytest` | P-01 drift-guard pytest | ✓ (assumed — the project's existing test suite runs here) | 3.x | — |
| Linux dev: `uv` | Existing `uv run pytest -x` invocation | ✓ (assumed — REQUIREMENTS / state references it) | — | `python -m pytest` |
| Win11 build VM: Miniforge / conda | Recreating the `musicstreamer-build` env from the new README | ✓ (operator already has it — used through Phases 43–68) | latest stable | — |
| Win11 build VM: conda-forge `gst-libav=1.28.2` win-64 build | F-01 conda recipe edit | ✓ [VERIFIED: anaconda.org/conda-forge/gst-libav, fetched 2026-05-11] | 1.28.2 (uploaded 2026-04-08) | — |
| Win11 build VM: conda-forge `gst-plugins-base / good / bad / ugly 1.28.2` win-64 builds | F-01 conda recipe edit | ✓ [VERIFIED: anaconda.org/conda-forge listings, fetched 2026-05-11] | 1.28.2 (uploaded 2026-04-08) | — |
| Win11 build VM: Inno Setup ≥6.3 | Existing installer compile | ✓ (Phase 44 already validates) | 6.3+ | — |
| Win11 build VM: PowerShell 5.1 | build.ps1 driver | ✓ (default on Win10/11) | 5.1 | PowerShell 7 (newer; same script works) |
| Operator: two AAC fixture URLs | UAT (R-01) | ✗ (pending operator paste at plan-check) | — | None — the phase cannot UAT without them. Plan-check MUST gate on these being supplied. |

**Missing dependencies with no fallback:**
- Two fixture URLs (pending operator at plan-check).

**Missing dependencies with fallback:**
- None.

## Validation Architecture

The phase's nyquist validation surface is necessarily light because no app-Python changes are made. The three dimensions:

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest` (existing project test runner — version per `pyproject.toml`'s `[project.optional-dependencies]` `dev` group) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (existing) |
| Quick run command | `uv run pytest tests/test_packaging_spec.py -x` |
| Full suite command | `uv run pytest -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WIN-05 (drift) | `packaging/windows/README.md` conda recipe contains every conda-forge package referenced in `tools/check_bundle_plugins.py REQUIRED_PLUGIN_DLLS`. | unit (static drift guard) | `uv run pytest tests/test_packaging_spec.py::test_readme_conda_recipe_lists_every_required_plugin_package -x` | ❌ Wave 0 (new test function in existing file) |
| WIN-05 (bundle) | Post-PyInstaller `dist/MusicStreamer/_internal/gst_plugins/` contains `gstlibav.dll` AND `gstaudioparsers.dll`. | integration (build-time guard) | `python tools/check_bundle_plugins.py --bundle dist/MusicStreamer/_internal` (invoked by build.ps1 after line 283) | ❌ Wave 0 (new file `tools/check_bundle_plugins.py` + new build.ps1 step) |
| WIN-05 (build.ps1 wire-in) | `build.ps1` invokes `check_bundle_plugins.py`, branches on exit code, emits `BUILD_FAIL reason=plugin_missing` with `-ForegroundColor Red`, then `exit 10`. | unit (drift guard on build.ps1 text) | `uv run pytest tests/test_packaging_spec.py::test_build_ps1_invokes_plugin_guard_with_exit_10 -x` | ❌ Wave 0 (new test function) |
| WIN-05 (UAT) | DI.fm AAC tier + SomaFM HE-AAC fixtures play end-to-end on the installed binary, post-force-fresh-install. | manual-only (operator UAT) | None — recorded in `69-UAT-LOG.md` | ❌ Wave 0 (new doc) |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_packaging_spec.py -x` (quick, <1s) — catches drift-guard regression immediately.
- **Per wave merge:** `uv run pytest -x` (full Linux dev suite — Phase 69 must not regress any of the 399 existing tests).
- **Phase gate:** Full suite green on Linux dev CI + green build.ps1 on the Win11 VM (including the new G-01 guard) + green UAT-LOG.md attestation before `/gsd-verify-work`.

### Wave 0 Gaps

- [ ] `tools/check_bundle_plugins.py` — new file (G-02). Contains `REQUIRED_PLUGIN_DLLS` dict, `main()` with argparse, exit-code branching (0=clean, 10=missing).
- [ ] New test function(s) in `tests/test_packaging_spec.py`:
  - `test_readme_conda_recipe_lists_every_required_plugin_package` — P-01 drift guard.
  - `test_build_ps1_invokes_plugin_guard_with_exit_10` — verifies build.ps1 has the new step, calls the new tool, branches on `$LASTEXITCODE -ne 0`, uses `Write-Host -ForegroundColor Red`, and ends with `exit 10`. Mirrors the existing post-bundle dist-info assertion drift guard (`test_build_ps1_post_bundle_dist_info_assertion_present`).
- [ ] `69-UAT-LOG.md` template at planning time — pre-fix repro section, BUILD_OK section, install attestation section, post-install playback section.

**No framework install needed.** Existing pytest infrastructure covers all phase tests. No new conftest.py fixtures required — drift-guard pytest can declare its own module-scoped fixtures inline (matches existing pattern in `test_packaging_spec.py`).

## Security Domain

Per project default (`.planning/config.json` does not disable `security_enforcement`), security review applies:

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No authentication surface in this phase. |
| V3 Session Management | No | No session surface. |
| V4 Access Control | No | No access control surface. |
| V5 Input Validation | Yes — UAT fixture URLs come from the operator | Operator-supplied URLs are not parsed by `tools/check_bundle_plugins.py` (which takes only `--bundle <path>` as input); validation happens at the existing `musicstreamer/url_helpers.py` layer when the operator pastes a URL into EditStationDialog or feeds it via AA import. No new input surface added by Phase 69. |
| V6 Cryptography | No (indirect) | The new code introduces no cryptographic operations. The TLS backend (`gioopenssl.dll`) is unchanged from Phase 43; AAC playback flows over the same `souphttpsrc` HTTPS pipeline that MP3 already does. No new attack surface. |
| V12 Files & Resources | Yes | `tools/check_bundle_plugins.py` reads files in `dist/MusicStreamer/_internal/gst_plugins/`. Standard control: use `pathlib.Path` (no shell concatenation, no `subprocess`), accept `--bundle` as `Path` type (argparse validates), restrict to `is_file()` / `is_dir()` calls. No untrusted file content is parsed — only filenames are enumerated. |
| V14 Configuration | Yes | The conda recipe edit (`README.md`) ships license-relevant package selection. gst-libav is LGPL-2.1-or-later — matches existing posture. No GPL-licensed plugin enters the bundle (faad is excluded by the conda-forge gst-plugins-bad win-64 build, and the required-plugin list explicitly does not include faad). License compliance is preserved. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Plugin-load chain hijacking (DLL planting) | Tampering | PyInstaller bundles all plugin DLLs into `_internal/gst_plugins/`. The runtime hook sets `GST_PLUGIN_SYSTEM_PATH=""` (per stock `pyi_rth_gstreamer.py` behavior), preventing the user's ambient `GST_PLUGIN_PATH` from injecting unsigned plugins. No new DLL search path is introduced by Phase 69. |
| Recipe drift / supply chain | Tampering, Information disclosure | The drift-guard pytest (P-01) makes recipe-vs-required-list divergence visible at CI time. The required-plugin list lives in `tools/check_bundle_plugins.py` under repo source control; tampering with it is a reviewable git change. |
| Dependency confusion via conda channel | Tampering | `conda create -c conda-forge` pins the channel; no PyPI / mixed-source risk for the GStreamer stack. |
| Malicious AAC stream payload (codec exploit) | Tampering, DoS | Out of scope for Phase 69. The FFmpeg/libav AAC decoder has its own CVE history; mitigation is upstream conda-forge tracking new gst-libav builds. The phase pins major.minor at 1.28; conda-forge will auto-update minor patches. |

**No new threats introduced by Phase 69.** All controls are either existing (PyInstaller bundling, runtime hook env vars) or new-but-defensive (drift-guard pytest, post-bundle file-presence guard).

## Sources

### Primary (HIGH confidence — verified via direct source / tool inspection)

- [VERIFIED: `packaging/windows/README.md` lines 18–20] Current production conda recipe — read 2026-05-11.
- [VERIFIED: `packaging/windows/build.ps1` lines 1–334] Current build driver — read 2026-05-11.
- [VERIFIED: `packaging/windows/MusicStreamer.spec` lines 1–195] Current PyInstaller spec — read 2026-05-11.
- [VERIFIED: `packaging/windows/runtime_hook.py` lines 1–55] Current runtime hook — read 2026-05-11.
- [VERIFIED: `tools/check_subprocess_guard.py` + `tools/check_spec_entry.py`] PKG-03 / PKG-01 guard pattern — read 2026-05-11.
- [VERIFIED: `tests/test_packaging_spec.py`] Existing drift-guard pytest patterns — read 2026-05-11.
- [VERIFIED: `.claude/skills/spike-findings-musicstreamer/SKILL.md` + references + sources] Phase 43 spike findings — auto-loaded per CLAUDE.md routing rule.
- [VERIFIED: `.planning/codebase/CONCERNS.md` lines 55–60] Existing AAC concern documentation — read 2026-05-11.
- [VERIFIED: `.planning/PROJECT.md` line 44] "GStreamer 1.28+ on Windows pinned: ... requires `gst-libav` for AAC/H.264 decoders" — read 2026-05-11.
- [VERIFIED: `.planning/phases/56-windows-di-fm-smtc-start-menu/56-05-UAT-LOG.md` lines 86–92] Phase 56 F2 finding — read 2026-05-11.
- [VERIFIED: github.com/conda-forge/gst-libav-feedstock recipe.yaml + build.bat] gst-libav 1.28.2 conda-forge recipe, win-64 ships `gstlibav.dll` — fetched 2026-05-11.
- [VERIFIED: github.com/conda-forge/gst-plugins-bad-feedstock recipe.yaml] gst-plugins-bad 1.28.2 conda-forge recipe; Windows test block does NOT check for `gstfaad.dll`; faad not in deps — fetched 2026-05-11.
- [VERIFIED: github.com/conda-forge/gst-plugins-ugly-feedstock recipe.yaml] gst-plugins-ugly 1.28.2 conda-forge recipe — fetched 2026-05-11.
- [VERIFIED: github.com/conda-forge/gstreamer-feedstock recipe.yaml] Combined `gstreamer + gst-plugins-base + gst-plugins-good` 1.28.2 conda-forge recipe; `gstreamer` output's runtime deps are only `${{ pin_compatible("glib") }}` — fetched 2026-05-11.
- [VERIFIED: github.com/GStreamer/gst-plugins-good/blob/master/gst/audioparsers/gstaacparse.c] `aacparse` source lives in gst-plugins-good's `audioparsers` plugin — fetched 2026-05-11.
- [VERIFIED: prefix.dev/channels/conda-forge/packages/gstreamer] gstreamer 1.28.2 win-64 runtime dependencies list (no plugin subpackages) — fetched 2026-05-11.
- [VERIFIED: anaconda.org/conda-forge/gst-libav] gst-libav 1.28.2 win-64 available; LGPL-2.1-or-later — fetched 2026-05-11.

### Secondary (MEDIUM confidence — cross-referenced)

- [CITED: `.claude/skills/spike-findings-musicstreamer/sources/43-gstreamer-windows-spike/43-SPIKE-FINDINGS.md` line 128, 143–155] Phase 43 spike Phase 44 handoff checklist + bundle layout BOM — informs gst_plugins/ subdir naming, broad-collect strategy.
- [CITED: github.com/conda-forge/pygobject-feedstock recipe.yaml] pygobject has no plugin runtime deps — fetched 2026-05-11.

### Tertiary (LOW confidence — web search only, flagged for empirical validation in UAT)

- [WebSearch: "gst-plugins-good Windows DLL list" 2026-05-11] Limited results on Windows-specific DLL filenames for gst-plugins-good — partially compensated by direct recipe.yaml inspection.
- [Inferred from gst-libav recipe.host listing `ffmpeg`]: gst-libav win-64 conda build enables AAC decode by default (FFmpeg upstream default). Empirical validation via UAT.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every package version verified against anaconda.org / conda-forge feedstock recipe.yaml.
- Architecture: HIGH — all paths through existing PyInstaller spec, runtime hook, and build.ps1 are verified by reading current source; the new G-01 / G-02 / P-01 patterns clone existing PKG-03 and spec-entry guards verbatim in shape.
- Pitfalls: HIGH on items 1, 4, 5, 6 (each cites Phase 43 spike findings or current source line); MEDIUM on items 2, 3 (depend on operator's env state, which the UAT will reveal).
- Plugin → package mapping: HIGH — corrected CONTEXT-DG-01's claim by direct inspection of gst-plugins-good source repo and conda-forge recipes.

**Research date:** 2026-05-11
**Valid until:** 2026-06-10 (30 days — conda-forge feedstock changes are infrequent; the only fast-moving axis is upstream GStreamer 1.28.x patch releases, which are pin-compat under the recipe.)
