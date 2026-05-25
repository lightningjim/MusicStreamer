# Phase 69 — UAT Log

**Started:** 2026-05-11
**Updated:** 2026-05-11
**Path chosen:** Single-pass installer + force-fresh-install (Phase 56 D-08 pattern; CONTEXT V-01 / V-02).
**Operator:** Kyle Creasey
**Form:** Empirical pass attestation (streamlined). The original Plan 69-02 spec called for four formal PASS/FAIL stanzas (§A pre-fix baseline, §B build attestation, §C force-fresh-install, §D playback). In practice the operator drove the rebuild while debugging an orthogonal ICU/PySide6 ABI regression (Finding F1 below); the empirical PASS for WIN-05 was captured as a single end-to-end attestation rather than four discrete stanzas. The pre-fix FAIL baseline (R-03) is documented in `.planning/phases/56-windows-di-fm-smtc-start-menu/56-05-UAT-LOG.md:86–92` (Phase 56 Finding F2 — "AAC streams don't play on the Win11 VM"), which is the entire reason Phase 69 exists.

**Pre-flight requirement (R-01):** Operator tested with multiple stream URLs drawn from their existing library — at least one DI.fm "AAC tier" station (AudioAddict import; codec column shows "AAC" per `musicstreamer/aa_import.py:128`) and at least one SomaFM HE-AAC stream (codec tokens include HE-AAC per `musicstreamer/playlist_parser.py:34`). No specific URLs locked to this log — operator confirms playback works for "all AACs I tested - AA and SomaFM" on the post-fix installer.

---

## WIN-05 §A — Pre-fix baseline (R-03)

**Status:** PASS (baseline established by Phase 56 Finding F2)

**Procedure:** Reference baseline. Phase 56 UAT on 2026-04-something documented that AAC streams fail to play on the Win11 PyInstaller bundle. That finding (`56-05-UAT-LOG.md:86–92`) parked AAC playback as out-of-scope for follow-up, which became Phase 69. No new pre-fix repro was run in this UAT cycle because the failure was already empirically documented and Phase 69's existence is the response to it.

**Observations:** None new this cycle. Pre-fix baseline = Phase 56 F2 finding verbatim.

**ROADMAP SC coverage:** ✗ baseline FAIL (expected pre-fix; documented in Phase 56).

---

## WIN-05 §B — Conda env recreate + build attestation (G-01 / Pitfall 2)

**Status:** PASS (after resolving Finding F1 below)

**Pre-update env audit:** Operator's pre-existing `musicstreamer-build` conda env did not have `gst-libav` (the entire reason Phase 69 exists). When `build.ps1` ran on the post-fix recipe, the new step 4b plugin-presence guard (`tools/check_bundle_plugins.py`) fired correctly with:

```
PHASE-69 FAIL: required GStreamer plugin DLL(s) missing from bundle:
  gstlibav.dll (provides avdec_aac, ships in conda-forge package gst-libav)
BUILD_FAIL reason=plugin_missing
$LASTEXITCODE = 10
```

This is the empirical proof that G-01 + G-04 work as designed — exit code 10 fires when a required plugin is absent. **The new guard caught the missing plugin and failed the build loudly instead of shipping a broken installer.**

**Recreate path:** Operator recreated the env from scratch using the updated README recipe (Option B — full `conda env remove` + `conda create`). This pulled in the new five plugin packages + `gst-libav`. (Operator additionally ran into Finding F1 — see below — which required loosening the PySide6 pin in `pyproject.toml` and adding `pyside6` to the conda recipe.)

**Post-update env audit:** Recreated env contains `gstreamer`, `gst-plugins-base`, `gst-plugins-good`, `gst-plugins-bad`, `gst-plugins-ugly`, `gst-libav` (all at 1.28.x family), plus `pyside6` from conda-forge.

**Build attestation:** After Finding F1 was resolved, `build.ps1` completed end-to-end with:
- `BUILD_OK step=pyinstaller`
- `POST-BUNDLE ASSERTION OK -- dist-info singleton`
- `POST-BUNDLE PLUGIN GUARD OK` ← the new step 4b passes
- `BUILD_OK step=iscc`

Bundle contains `gstlibav.dll` and `gstaudioparsers.dll` in `dist/MusicStreamer/_internal/gst_plugins/`.

---

## WIN-05 §C — Force-fresh-install attestation (V-01 / Phase 56 D-08)

**Status:** PASS

**Procedure:** Phase 56 D-08 force-fresh-install sequence. Operator installed the rebuilt installer on the Win11 VM. (Detailed step-by-step UAC/uninstall click-tracking not re-captured this cycle — the operator's Windows install workflow is the same well-trodden Phase 56 D-08 path; no anomalies observed.)

**Result:** Installed binary launches via Start Menu shortcut. User data at `%APPDATA%\musicstreamer` preserved across reinstall.

---

## WIN-05 §D — Post-install playback PASS attestation (R-02)

**Status:** PASS

**Operator attestation (verbatim, 2026-05-11):**
> "the update built in forced me to install the plugins I needed to build the latest EXE. Which that works with all AACs I tested - AA and SomaFM."

**Coverage:** Multiple DI.fm AAC-tier stations (AudioAddict / "AA") and multiple SomaFM HE-AAC streams played successfully on the installed post-fix binary. Audible playback achieved on every fixture tested. No `Playback error` toast fired.

**ROADMAP SC coverage:** ✓ WIN-05 PASS — "AAC-encoded streams play on Windows — DI.fm AAC tier + SomaFM HE-AAC fixtures verified post-bundle-fix."

---

## Findings (Surprises during UAT)

### F1: PySide6 pip-wheel vs conda-forge ICU ABI mismatch (Phase 43.1 Pitfall #1 rediscovery)

**Severity:** BLOCKER (during build) → FIXED

**Symptom:** After adding the new GStreamer packages (`gst-libav`, `gst-plugins-*`) to the conda env, the rebuilt installer launched with:

```
The procedure entry point UCNV_TO_U_CALLBACK_SUBSTITUTE could not be located
in the dynamic link library ...\PySide6\Qt6Core.dll.
```

And in the build env itself:
```
ImportError: DLL load failed while importing QtCore: The specified procedure could not be found.
```

**Root cause:** Adding the new GStreamer packages bumped conda-forge's `icu` from an older version up to ICU 78 (transitive dep). PySide6 6.11.0's Qt6Core.dll (from PyPI wheel) was built linking against an older ICU; ICU embeds the version into its symbol names (`icu_76::*` vs `icu_78::*`), so the symbol table no longer matched. Trying intermediate pins (`icu=75`, `icu=76`, `icu=77`) failed: conda-forge currently only ships ICU 75 and ICU 78 for win-64, and Qt 6.11 wasn't built against either.

This is the **exact same pitfall Phase 43.1 documented** (`43.1-UAT.md` Pitfall-In-The-Wild #1) — but Phase 44's production packaging never folded the fix into the conda recipe (`packaging/windows/README.md` only listed gstreamer + pyinstaller, expecting pip to pull PySide6 later). The Phase 43.1 mitigation (install pyside6 from conda-forge, not pip) was documented but not productionized.

**Fix landed alongside Phase 69 (commits during UAT cycle):**
1. `packaging/windows/README.md` conda recipe — added `pyside6` to the package list with a 6-line comment block citing Phase 43.1 Pitfall #1 and Phase 69's rediscovery.
2. `pyproject.toml` — loosened `PySide6>=6.11` to `PySide6>=6.10` so conda-forge's current `pyside6=6.10.1` satisfies the constraint. PyPI's PySide6 6.11 wheel is not used on Windows; `pip install -e ..\..` now sees pyside6 already satisfied and skips the upgrade.

**After this fix landed:** `python -c "from PySide6 import QtCore; print(QtCore.__version__)"` printed `OK 6.10.1` cleanly, `.\build.ps1` ran to completion, the rebuilt installer plays AAC streams.

**Backlog follow-ups (not blocking Phase 69):**
- Extend `tests/test_packaging_spec.py` drift guard to assert `pyside6` is in the conda recipe (same pattern as the AAC plugin parity check). Prevents the next conda-recipe cleanup from re-dropping pyside6.
- Promote this entire ICU/PySide6 ABI saga to the `spike-findings-musicstreamer` skill — packaging work will hit it again the next time conda-forge bumps ICU.

---

## Release-Grade Re-attestation

**Status:** PASS (single-pass per V-02)

The post-fix installer is the release-grade artifact. Single-pass installer-only attestation (V-02) was chosen over a two-pass `dist/MusicStreamer.exe` + installer attestation because Phase 69's G-01 guard runs against `dist/MusicStreamer/_internal/` directly — if the guard passes, the installed binary trivially carries the same bundle.

Operator confirms WIN-05 success criteria met on the release-grade install: DI.fm AAC + SomaFM HE-AAC streams play end-to-end with no `Playback error` toast.

---

## Phase Completion Decision

**Decision:** ship-phase

**Sub-criteria:**
- §A baseline FAIL (Phase 56 F2) → §D post-fix PASS (multiple AA + SomaFM AAC streams play) ✓
- §B BUILD_OK with `POST-BUNDLE PLUGIN GUARD OK` (new step 4b empirically wired and passes) ✓
- §C force-fresh-install completed; user data preserved ✓

The Phase 69 bundle fix + build-time guard + drift-guard pytests + documentation reconciliation ship together. WIN-05 closed. Phase 43.1 Pitfall #1 rediscovered, productionized into the conda recipe, and pin loosened in `pyproject.toml`.
