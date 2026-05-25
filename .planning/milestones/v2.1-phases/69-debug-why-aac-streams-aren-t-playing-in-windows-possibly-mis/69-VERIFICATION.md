---
phase: 69-debug-why-aac-streams-aren-t-playing-in-windows-possibly-mis
verified: 2026-05-11T22:24:19Z
status: passed
score: 10/10 must-haves verified
overrides_applied: 0
---

# Phase 69: Debug why AAC streams aren't playing in Windows Verification Report

**Phase Goal:** Bundle fix + build-time guard + plugin-presence pytest + Win11 VM UAT — debug + fix the AAC playback regression in the Windows PyInstaller bundle in one phase, no app-side runtime UX changes. Empirical PASS attestation for AAC playback on Win11 is the SHIP gate. (CONTEXT-D-02 boundary; ROADMAP also names WIN-05 explicitly.)

**Verified:** 2026-05-11T22:24:19Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
| -- | ----- | ------ | -------- |
| 1  | `tools/check_bundle_plugins.py` exists and exports correct `REQUIRED_PLUGIN_DLLS` dict | VERIFIED | File at `tools/check_bundle_plugins.py:38-41`. Runtime check: `uv run python -c "from tools.check_bundle_plugins import REQUIRED_PLUGIN_DLLS; ..."` confirms `{'gstlibav.dll': ('avdec_aac', 'gst-libav'), 'gstaudioparsers.dll': ('aacparse', 'gst-plugins-good')}` — matches RESEARCH correction (NOT CONTEXT-DG-01's incorrect gst-plugins-bad mapping). `m.main(['--bundle','/nonexistent/path'])` returns 10 with `PHASE-69 FAIL` stderr line. |
| 2  | `packaging/windows/build.ps1` step 4b wires the new guard with exit code 10 and WR-01 discipline | VERIFIED | `build.ps1:286-307` contains `=== POST-BUNDLE PLUGIN GUARD: python tools/check_bundle_plugins.py (Phase 69 / WIN-05) ===` header, `Invoke-Native { python ..\..\tools\check_bundle_plugins.py --bundle ..\..\dist\MusicStreamer\_internal ... }`, `Write-Host "BUILD_FAIL reason=plugin_missing ..." -ForegroundColor Red` (WR-01-compliant), `exit 10`, `Write-Host "POST-BUNDLE PLUGIN GUARD OK"`. Line ordering: 284 (POST-BUNDLE ASSERTION OK) < 301 (PLUGIN GUARD start) < 307 (PLUGIN GUARD OK) < 309 (Smoke test) — strictly increasing as spec'd. |
| 3  | `build.ps1` exit-code header documents code 10 | VERIFIED | `build.ps1:7` reads `#             10=post-bundle plugin-presence guard fail (Phase 69)` — exactly as RESEARCH Example 3 spec'd. |
| 4  | `packaging/windows/README.md` conda recipe lists all 5 plugin packages + gst-libav + pyside6 | VERIFIED | `README.md:17-32` fenced powershell block contains `gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly`, `gst-libav`, AND `pyside6` (Pitfall #1 productionization). Inline comments cite Phase 69 (lines 25-26) and Phase 43.1 Pitfall #1 (lines 27-31). |
| 5  | Two new drift-guard pytests in `tests/test_packaging_spec.py` pass | VERIFIED | `tests/test_packaging_spec.py:417-469` defines `test_readme_conda_recipe_lists_every_required_plugin_package`; lines 472-550 define `test_build_ps1_invokes_plugin_guard_with_exit_10`. `_README` constant at line 45, `readme_source` fixture at line 65. Ran `uv run pytest tests/test_packaging_spec.py -x` → **8 passed in 0.07s**. |
| 6  | `.planning/codebase/CONCERNS.md` DOC-01 reconciliation: stale "Phase 44 bundling confirmed" claim removed | VERIFIED | Positive: line 59 contains `Phase 69 confirmed gst-libav was missing from the conda recipe shipped through v2.0–v2.1.0`. Negative: `grep -c "Phase 44 bundling confirmed gst-libav is present" CONCERNS.md` → 0. Issue/Files/Impact bullets at lines 56-58 preserved. |
| 7  | `.planning/REQUIREMENTS.md` adds WIN-05 row in Windows Polish + Traceability + bumped Coverage tally | VERIFIED | Line 34: `- [ ] **WIN-05**: AAC-encoded streams play on Windows — DI.fm AAC tier + SomaFM HE-AAC fixtures verified post-bundle-fix *(Phase 69)*`. Line 105: `\| WIN-05 \| Phase 69 \| Pending \|`. Coverage tally (lines 108-112): `v2.1 requirements: 20 total / Mapped: 20 / Complete: 18 / Pending: 2 (WIN-02 — ...; WIN-05 — AAC Win11 UAT)`. WIN-05 still `[ ]` and Traceability "Pending" — correct interim state until `/gsd-complete-phase 69` flips it. |
| 8  | D-02 boundary: no app-side runtime UX changes; nothing modified under `musicstreamer/` | VERIFIED | `git log --name-only 8d9f0cc..HEAD \| grep '^musicstreamer/'` → empty. All Phase 69 commits (26041b2, 39a98f2, 3e4bd1d, 53c75de, 0f434c9, 866ad86, 83c1e88) touch only `tools/`, `packaging/windows/`, `tests/`, `.planning/`, and `pyproject.toml`. D-02 boundary preserved. |
| 9  | `pyproject.toml` PySide6 pin loosened to >=6.10 per Phase 43.1 Pitfall #1 productionization | VERIFIED | `pyproject.toml:13-18` reads `"PySide6>=6.10"` with multi-line comment block citing Phase 43.1 Pitfall #1 and the conda-forge ICU 78 ABI coupling. Loosened from prior >=6.11 as documented in 69-02-SUMMARY.md Deviation #2. |
| 10 | Empirical PASS attestation for AAC playback on Win11 (the SHIP gate) | VERIFIED | `69-02-UAT-LOG.md` contains all four section headers (`## WIN-05 §A/§B/§C/§D`), `**Decision:** ship-phase`, and three operator attestations: (a) the new step 4b guard fired in real life with `BUILD_FAIL reason=plugin_missing` + `$LASTEXITCODE = 10` against the operator's pre-existing env missing `gst-libav` (empirical G-01 proof, §B lines 31-38); (b) after env recreate, `POST-BUNDLE PLUGIN GUARD OK` was emitted and `gstlibav.dll`+`gstaudioparsers.dll` shipped in the bundle (§B lines 44-50); (c) operator verbatim: "the update built in forced me to install the plugins I needed to build the latest EXE. Which that works with all AACs I tested - AA and SomaFM" (§D lines 68-71). Phase Completion Decision: `ship-phase` with three sub-criteria checked. |

**Score:** 10/10 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `tools/check_bundle_plugins.py` | Source-of-truth REQUIRED_PLUGIN_DLLS + CLI guard | VERIFIED | 105 lines; exports `REQUIRED_PLUGIN_DLLS` (importable); exits 10 on missing bundle; ends with `sys.exit(main())` under `__main__` guard. Contains literal `gst_plugins` (underscore form, Pitfall 1) and zero references to `faad` (negative drift-guard). |
| `packaging/windows/build.ps1` | Step 4b post-bundle plugin guard with exit 10 + header doc | VERIFIED | Exit-code header at line 7; new step 4b block at lines 286-307; correctly slotted between step 4a (line 284) and step 5 smoke test (line 309). All five required literals present: `POST-BUNDLE PLUGIN GUARD`, `python ..\..\tools\check_bundle_plugins.py`, `BUILD_FAIL reason=plugin_missing`, `exit 10`, `POST-BUNDLE PLUGIN GUARD OK`. |
| `packaging/windows/README.md` | Conda recipe with all 5 plugin packages + gst-libav + pyside6 | VERIFIED | Fenced powershell block at lines 17-32; contains all 6 required packages with explanatory inline comments. |
| `tests/test_packaging_spec.py` | Two new drift-guard tests + _README/readme_source fixtures | VERIFIED | 8 tests pass clean (6 pre-existing + 2 new). New tests defined at lines 417 and 472. |
| `.planning/codebase/CONCERNS.md` | DOC-01 fix-approach line replaced | VERIFIED | Single-line edit at line 59; concern structure preserved. |
| `.planning/REQUIREMENTS.md` | WIN-05 row + Traceability + Coverage tally bumped | VERIFIED | All three sites edited consistently; tally arithmetic correct. |
| `.planning/phases/69-*/69-02-UAT-LOG.md` | Operator UAT attestation with PASS for WIN-05 | VERIFIED | All structural literals present; Decision: ship-phase; F1 documents Phase 43.1 Pitfall #1 rediscovery. |
| `pyproject.toml` | PySide6 pin loosened to >=6.10 | VERIFIED | Productionization of Phase 43.1 Pitfall #1. |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `tests/test_packaging_spec.py::test_readme_conda_recipe_lists_every_required_plugin_package` | `tools/check_bundle_plugins.py::REQUIRED_PLUGIN_DLLS` | `from tools.check_bundle_plugins import REQUIRED_PLUGIN_DLLS` | WIRED | Import resolves at test time (test passes); regex `r"conda create -n musicstreamer-build[^\n]*\n((?:[^\n]*\n)+?)\`\`\`"` matches the README recipe block (Pitfall 5-compliant fence anchor). |
| `tests/test_packaging_spec.py::test_build_ps1_invokes_plugin_guard_with_exit_10` | `packaging/windows/build.ps1` step 4b | `build_ps1_source` fixture + substring assertions | WIRED | All four substring assertions pass (POST-BUNDLE PLUGIN GUARD, python ..\..\tools\check_bundle_plugins.py, BUILD_FAIL reason=plugin_missing, exit 10) plus WR-01 Write-Host adjacency check (120-char before, 400-char after) |
| `packaging/windows/build.ps1` step 4b | `tools/check_bundle_plugins.py` | `Invoke-Native { python ..\..\tools\check_bundle_plugins.py --bundle ..\..\dist\MusicStreamer\_internal ... }` | WIRED | Empirically validated on Win11 VM during §B of 69-02-UAT-LOG.md — the guard fired correctly with exit code 10 against an env missing gst-libav, then emitted `POST-BUNDLE PLUGIN GUARD OK` after env recreate. |
| `tools/check_bundle_plugins.py::REQUIRED_PLUGIN_DLLS` | `packaging/windows/README.md` conda packages | Drift-guard pytest asserts every `(_, package)` tuple value appears in the recipe block | WIRED | Drift-guard pytest passes; both `gst-libav` and `gst-plugins-good` appear in the recipe. |
| `69-02-UAT-LOG.md` PASS attestation | `.planning/REQUIREMENTS.md` WIN-05 row | `/gsd-complete-phase` flips checkbox from `[ ]` to `[x]` and Traceability Pending → Complete | NOT_YET_INVOKED | Interim state is correct: WIN-05 row is `[ ]` with Pending status (Phase 69 verify-work has not yet been followed by complete-phase). This is expected pre-complete-phase state, not a gap. |

### Data-Flow Trace (Level 4)

Phase 69 produces tooling (`tools/check_bundle_plugins.py`), build-script wiring (`build.ps1`), drift-guard tests, and documentation reconciliation — no dynamic-data-rendering artifacts. Level 4 is not applicable to this phase.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| `REQUIRED_PLUGIN_DLLS` dict matches spec | `uv run python -c "from tools.check_bundle_plugins import REQUIRED_PLUGIN_DLLS; assert REQUIRED_PLUGIN_DLLS == {...}; print('OK')"` | OK dict + exit-10 verified | PASS |
| Guard exits 10 on missing bundle path | `uv run python -c "import tools.check_bundle_plugins as m; assert m.main(['--bundle','/nonexistent/path']) == 10"` | stderr: `PHASE-69 FAIL: bundle plugins dir not found at /nonexistent/path/gst_plugins`; return code 10 | PASS |
| Drift-guard tests pass | `uv run pytest tests/test_packaging_spec.py -x` | 8 passed, 1 warning in 0.07s | PASS |
| D-02 boundary check (no musicstreamer/ files touched) | `git log --name-only 8d9f0cc..HEAD \| grep '^musicstreamer/'` | empty (no matches) | PASS |
| Negative drift-guard: no `faad` references | `grep -c "faad" tools/check_bundle_plugins.py` | 0 | PASS |
| Empirical guard fires on operator VM (real-world G-01 attestation) | Operator ran `.\build.ps1` against env missing gst-libav | `BUILD_FAIL reason=plugin_missing` + `$LASTEXITCODE = 10` captured in 69-02-UAT-LOG.md §B | PASS (in field) |
| Empirical AAC playback on Win11 post-fix | Operator played multiple DI.fm + SomaFM AAC streams on rebuilt installer | All AAC fixtures play; no `Playback error` toast | PASS (in field, operator attested) |

### Probe Execution

No phase-declared probes (no `scripts/*/tests/probe-*.sh` paths referenced in PLAN/SUMMARY). Phase 69 uses pytest as the static drift-guard mechanism; the empirical "probe" is the Win11 VM UAT operator-execution loop, which is documented in 69-02-UAT-LOG.md. N/A.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| WIN-05 | 69-01-PLAN.md, 69-02-PLAN.md | AAC-encoded streams play on Windows — DI.fm AAC tier + SomaFM HE-AAC fixtures verified post-bundle-fix *(Phase 69)* | SATISFIED (pending complete-phase checkbox flip) | (a) Plan 01: tools/check_bundle_plugins.py + build.ps1 step 4b + README conda recipe + drift-guard pytests + CONCERNS.md + REQUIREMENTS.md WIN-05 row all landed. (b) Plan 02: 69-02-UAT-LOG.md empirically attests "all AACs I tested - AA and SomaFM" play on rebuilt installer; G-01 guard fired correctly in the field; Decision: ship-phase. REQUIREMENTS.md WIN-05 row sits at `[ ]` / Traceability "Pending" until `/gsd-complete-phase 69` flips it to `[x]` / "Complete" — interim state is correct. |

### Anti-Patterns Found

None.

- No `TBD`/`FIXME`/`XXX` markers added to files modified in this phase.
- No `TODO`/`HACK`/`PLACEHOLDER` markers in Phase 69 edits.
- `tools/check_bundle_plugins.py` has no empty implementations or console.log-only handlers.
- `build.ps1` step 4b uses `Write-Host -ForegroundColor Red` (not `Write-Error`) per Phase 65 WR-01 discipline — locked by drift-guard test.
- The "deferred-items.md" worktree artifact (mentioned in 69-01-SUMMARY.md) is intentionally not committed (`.planning/` gitignored; the file is for orchestrator handoff only).

### Human Verification Required

None. All must-haves are verifiable from codebase artifacts + the operator-attested UAT-LOG.md. The empirical "human verification" (AAC playback on Win11) has already been performed and recorded in `69-02-UAT-LOG.md` with operator attestation: "the update built in forced me to install the plugins I needed to build the latest EXE. Which that works with all AACs I tested - AA and SomaFM."

The G-01 guard's empirical field validation (the guard fired with exit code 10 when the operator's env was missing gst-libav) is documented in 69-02-UAT-LOG.md §B lines 31-38 — this is stronger evidence than a programmatic check could provide, because it proves the guard works end-to-end on a real Windows build environment, not just on Linux dev CI.

### Gaps Summary

No gaps. All 10 observable truths verified, all 8 artifacts present and substantive, all 4 active key links wired (the 5th key link — `/gsd-complete-phase` flip — is correctly NOT YET INVOKED for an interim verify-work step), drift-guard pytests pass on Linux dev CI, empirical PASS attestation captured on Win11 VM.

**Deviations from spec accepted (per verifier instructions):**

1. **UAT-LOG.md form streamlining** — 69-02-UAT-LOG.md is a single-pass empirical attestation rather than the four-stanza-with-detailed-per-fixture-command-captures form spec'd in 69-02-PLAN.md. All structural literals (`## WIN-05 §A/B/C/D`, `Decision: ship-phase`, `POST-BUNDLE PLUGIN GUARD OK`) are present, and the substance (G-01 guard fired in field, AAC streams play post-fix) is fully captured. Documented in 69-02-SUMMARY.md Deviations #1.

2. **R-03 pre-fix baseline reuse** — instead of re-running a fresh pre-fix repro against a deliberately-broken bundle, §A reuses Phase 56 Finding F2 as the documented baseline. Phase 56 F2 is the reason Phase 69 exists, so this is a valid baseline-by-reference. Documented in 69-02-SUMMARY.md Deviations #1.

3. **In-scope-by-spirit Pitfall #1 productionization** — Plan 02 additionally productionized Phase 43.1 Pitfall #1 (added `pyside6` to conda recipe + loosened `pyproject.toml` PySide6 pin from >=6.11 to >=6.10) when the orthogonal ICU/PySide6 ABI regression surfaced live during the rebuild attempt. This is technically out of 69-01-PLAN.md's locked `files_modified` but in-scope-by-spirit per CONTEXT-DOC-01 (reconcile documentation drift). Documented in 69-02-SUMMARY.md Deviations #2.

All three deviations preserve the phase goal. The empirical SHIP gate (AAC plays on Win11 post-fix) is met.

### Next Step

Phase 69 is ready for `/gsd-complete-phase 69`, which will:
- Flip WIN-05 row from `[ ]` to `[x]` in `.planning/REQUIREMENTS.md` Windows Polish section.
- Flip Traceability row from `Pending` to `Complete` (line 105).
- Update Coverage tally from `Pending: 2 (WIN-02, WIN-05)` to `Pending: 1 (WIN-02)` and bump `Complete: 18 → 19`.

Two non-blocking backlog follow-ups noted in 69-02-UAT-LOG.md F1 and 69-02-SUMMARY.md (Forward-protection note):
- Extend `tests/test_packaging_spec.py` drift guard to assert `pyside6` is in the conda recipe (mirror the AAC plugin parity pattern).
- Promote the ICU/PySide6 ABI saga to the `spike-findings-musicstreamer` skill.

These are tracked outside Phase 69's SHIP gate and do not block phase completion.

---

*Verified: 2026-05-11T22:24:19Z*
*Verifier: Claude (gsd-verifier)*
