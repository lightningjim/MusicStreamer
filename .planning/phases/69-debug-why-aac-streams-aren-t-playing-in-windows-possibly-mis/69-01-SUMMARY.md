---
phase: 69-debug-why-aac-streams-aren-t-playing-in-windows-possibly-mis
plan: 01
subsystem: infra
tags:
  - windows
  - packaging
  - gstreamer
  - bundling
  - drift-guard
  - conda-forge
  - pyinstaller

requires:
  - phase: 43-gstreamer-windows-spike
    provides: GStreamer Windows bundling pattern (conda-forge, runtime_hook env vars, broad-collect plugin shipping, hooks-contrib 2026.2 gst_plugins/ subdir naming)
  - phase: 44-windows-installer-packaging
    provides: build.ps1 PowerShell driver, MusicStreamer.spec, MusicStreamer.iss, Invoke-Native PS 5.1 stderr-trap wrapper, tools/check_subprocess_guard.py + tools/check_spec_entry.py (PowerShell-calls-Python guard pattern)
  - phase: 56-windows-di-fm-smtc-start-menu
    provides: Empirical AAC-fails-on-Win11 finding (56-05-UAT-LOG.md F2), D-08 force-fresh-install UAT sequence
  - phase: 65-version-display
    provides: WR-01 Write-Host -ForegroundColor Red discipline (build.ps1 lines 18-27), post-bundle dist-info assertion structural analog (step 4a, exit 9)
provides:
  - tools/check_bundle_plugins.py single-source-of-truth REQUIRED_PLUGIN_DLLS dict
  - build.ps1 step 4b post-bundle plugin-presence guard with exit code 10
  - README.md conda recipe with five explicit plugin packages (gst-plugins-base/good/bad/ugly + gst-libav)
  - Two drift-guard pytest functions covering README<->required-list parity AND build.ps1<->exit-code-10 invocation parity
  - CONCERNS.md reconciled fix-approach line (DOC-01)
  - REQUIREMENTS.md WIN-05 row in Windows Polish + Traceability (DOC-04)
affects:
  - 69-02 (Win11 VM UAT — consumes the new bundle for end-to-end AAC playback attestation)
  - Future Windows-bundle codec phases (any new codec failure can extend REQUIRED_PLUGIN_DLLS in tools/check_bundle_plugins.py; drift-guard pytest auto-validates the README)

tech-stack:
  added: []
  patterns:
    - "Source-of-truth Python helper invoked by build.ps1 via Invoke-Native + paired drift-guard pytest that imports the same constant — eliminates documentation-vs-required-list drift between README recipe and bundle expectations"
    - "Post-bundle file-presence guard at PyInstaller-output stage (file-on-disk in gst_plugins/, NOT runtime gst-inspect probe) — files at known path is sufficient evidence the hooks-contrib + scanner already vouched the plugin loads"
    - "WR-01 discipline (Write-Host -ForegroundColor Red + exit N) preserved on the new step 4b failure block; pytest WR-01 adjacency check (120 chars before Write-Host, 400 chars after exit 10) locks the discipline"

key-files:
  created:
    - tools/check_bundle_plugins.py
    - .planning/phases/69-debug-why-aac-streams-aren-t-playing-in-windows-possibly-mis/69-01-SUMMARY.md
    - .planning/phases/69-debug-why-aac-streams-aren-t-playing-in-windows-possibly-mis/deferred-items.md
  modified:
    - packaging/windows/build.ps1
    - packaging/windows/README.md
    - tests/test_packaging_spec.py
    - .planning/codebase/CONCERNS.md
    - .planning/REQUIREMENTS.md

key-decisions:
  - "RESEARCH corrected CONTEXT-DG-01: aacparse ships in gst-plugins-good (audioparsers DLL), NOT gst-plugins-bad as initial draft asserted; REQUIRED_PLUGIN_DLLS reflects the corrected mapping"
  - "GPL-licensed faad alternative explicitly excluded from REQUIRED_PLUGIN_DLLS — conda-forge win-64 gst-plugins-bad does NOT build it (negative drift-guard: grep -c faad tools/check_bundle_plugins.py == 0)"
  - "Conda recipe expanded to all five plugin packages (RESEARCH DG-02 refuted CONTEXT-DG-02 assumption that gst-plugins-good would be pulled in via dependency resolution — the gstreamer feedstock declares only pin_compatible(glib))"
  - "REQUIREMENTS.md Coverage tally normalized to the plan's spec'd post-edit state (20 total / 18 complete / 2 pending WIN-02 + WIN-05). The on-disk pre-edit state was already stale (claimed 19 total / 2 complete / 17 pending); plan must_haves.truths gives the authoritative target shape."

patterns-established:
  - "Plugin-presence drift-guard: tools/check_bundle_plugins.py exports REQUIRED_PLUGIN_DLLS dict; tests/test_packaging_spec.py imports it and asserts the README conda recipe lists every conda-forge package value. Cross-platform: pytest runs on Linux dev CI; build.ps1 step 4b runs on the Win11 build VM. Same source of truth, two enforcement points."
  - "Worktree-safe doc edits: gitignored .planning/ subdir files can still be committed via explicit `git add <path>` (the gitignore filter only suppresses bulk `git add .`; explicit paths bypass it). Note: .planning/phases/.../deferred-items.md was NOT committed because the rule applied to that file too — kept as a worktree-local artifact for the orchestrator."

requirements-completed: []  # WIN-05 is intentionally Pending until Plan 02 UAT lands

duration: ~30min
completed: 2026-05-11
---

# Phase 69 Plan 01: AAC Bundle Fix + Plugin-Presence Guard Summary

**Single-source-of-truth Python plugin guard (tools/check_bundle_plugins.py) wired into build.ps1 step 4b with exit code 10, conda recipe expanded with five explicit plugin packages including gst-libav, paired with two Linux-CI drift-guard pytests that lock README<->required-list parity and build.ps1<->exit-code-10 invocation parity.**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-05-11T13:04:00Z (approx)
- **Completed:** 2026-05-11T13:34:13Z
- **Tasks:** 4
- **Files modified:** 6 (1 created in tools/, 1 modified in packaging/windows/build.ps1, 1 in README.md, 1 in tests/, 2 in .planning/)

## Accomplishments

- **Build-time guard:** New `tools/check_bundle_plugins.py` exports the single-source `REQUIRED_PLUGIN_DLLS = {"gstlibav.dll": ("avdec_aac", "gst-libav"), "gstaudioparsers.dll": ("aacparse", "gst-plugins-good")}` dict. CLI: `python tools/check_bundle_plugins.py --bundle <path>` exits 10 if gst_plugins/ subdir or any required DLL is missing, exits 0 with a one-line OK message otherwise.
- **Build driver wired:** `packaging/windows/build.ps1` step 4b inserted between the existing post-bundle dist-info assertion (step 4a / exit 9) and the smoke-test block (step 5). Invokes the new Python guard via `Invoke-Native` (PS 5.1 stderr-trap mitigation), branches on `$LASTEXITCODE`, emits `BUILD_FAIL reason=plugin_missing` via `Write-Host -ForegroundColor Red` and exits 10. The exit-code header (lines 4-7) now documents `10=post-bundle plugin-presence guard fail (Phase 69)` as the new code.
- **Conda recipe expanded:** `packaging/windows/README.md` conda recipe block now lists `gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly gst-libav` alongside the existing `gstreamer=1.28` pin. Inline PowerShell comments cite Phase 69 (gst-libav -> avdec_aac in gstlibav.dll, aacparse in gst-plugins-good's audioparsers plugin).
- **Drift-guard pytests:** Two new functions in `tests/test_packaging_spec.py` (alongside a new `_README` constant + `readme_source` fixture). `test_readme_conda_recipe_lists_every_required_plugin_package` imports `REQUIRED_PLUGIN_DLLS` from the tool and asserts every conda-forge package appears inside the fenced powershell recipe block (Pitfall 5 regex terminates at closing fence). `test_build_ps1_invokes_plugin_guard_with_exit_10` locks step 4b shape including WR-01 Write-Host adjacency (120 chars before, 400 chars after the BUILD_FAIL site).
- **Documentation reconciled:** `.planning/codebase/CONCERNS.md` GStreamer Windows Plugin Availability concern's `Fix approach:` line replaced with the Phase 69 ground truth (Phase 44 stale claim removed). `.planning/REQUIREMENTS.md` carries the new `WIN-05` row in both Windows Polish (checkbox unchecked) and Traceability table (Pending); Coverage tally updated to `20 total / 18 complete / 2 pending (WIN-02, WIN-05)`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create tools/check_bundle_plugins.py source-of-truth helper** — `26041b2` (feat)
2. **Task 2: Wire build.ps1 step 4b plugin-presence guard with exit 10** — `39a98f2` (feat)
3. **Task 3: Expand conda recipe + add two drift-guard tests** — `3e4bd1d` (feat)
4. **Task 4: Reconcile CONCERNS.md fix-approach + add WIN-05 requirement** — `53c75de` (docs)

## Files Created/Modified

- `tools/check_bundle_plugins.py` (CREATED, 104 lines) — Source-of-truth REQUIRED_PLUGIN_DLLS dict + CLI guard. Mirrors the structural shape of `tools/check_subprocess_guard.py` (Phase 44 PKG-03 guard).
- `packaging/windows/build.ps1` (MODIFIED, +25 lines / -1 line) — Exit-code header line 7 added (`10=post-bundle plugin-presence guard fail (Phase 69)`); new step 4b block inserted at line 286-308.
- `packaging/windows/README.md` (MODIFIED) — Conda recipe block at lines 16-26 expanded with five plugin packages + two-line PowerShell comment block citing Phase 69.
- `tests/test_packaging_spec.py` (MODIFIED, +153 lines) — `_README` constant + `readme_source` fixture + two new test functions appended at end of file.
- `.planning/codebase/CONCERNS.md` (MODIFIED, 1-line edit) — GStreamer Windows Plugin Availability section's `Fix approach:` line replaced.
- `.planning/REQUIREMENTS.md` (MODIFIED) — Windows Polish section + Traceability table each gained a WIN-05 row; Coverage tally normalized to 20-total post-edit state.

## Decisions Made

- **RESEARCH-corrected REQUIRED_PLUGIN_DLLS mapping:** Trusted the RESEARCH "Plugin -> conda-forge package map" (verified against the live conda-forge feedstocks 2026-05-11) over the older CONTEXT-DG-01 default mapping. `aacparse` ships in `gst-plugins-good`'s audioparsers plugin (`gstaudioparsers.dll`), NOT `gst-plugins-bad` as CONTEXT-DG-01 stated.
- **faad explicitly excluded from required list:** Negative drift-guard `grep -c "faad" tools/check_bundle_plugins.py == 0` enforced. The original GPL-licensed alternative decoder is not built in conda-forge win-64 gst-plugins-bad — listing it as required would make the bundle un-shippable on the chosen build path.
- **Conda recipe expanded to all five plugin packages (RESEARCH DG-02 over CONTEXT-DG-02):** CONTEXT-DG-02 assumed `gst-plugins-good` would be pulled in via dependency resolution from the `gstreamer` meta-package. RESEARCH refuted this empirically (the conda-forge feedstock declares only `pin_compatible(glib)`, no plugin dependencies). Recipe now explicit; recipe-vs-required-list drift is statically caught by the new pytest.
- **REQUIREMENTS.md Coverage tally normalized from stale pre-edit state:** The on-disk pre-edit tally read `Complete: 2 / Pending: 17` (stale from initial v2.1 milestone open). The plan's `must_haves.truths` gives the authoritative target shape (`20 total / 18 complete / 2 pending (WIN-02, WIN-05)`). Applied the target shape directly rather than preserving the stale intermediate state.

## Deviations from Plan

### Stale-state normalization (within plan boundary)

**1. REQUIREMENTS.md Coverage tally — applied target shape rather than spec'd delta**

- **Found during:** Task 4 (Reconcile documentation)
- **Issue:** The plan's Task 4.B.3 instructed me to update the Coverage tally FROM the "19 total / 18 complete / 1 pending (WIN-02 — SMTC Start Menu shortcut with AUMID)" intermediate shape. The on-disk pre-edit state actually read `Complete: 2 (BUG-07 env-level; BUG-01 Phase 50) / Pending: 17` — a stale state from milestone open that prior phases never updated incrementally.
- **Fix:** Applied the plan's authoritative target shape verbatim per `must_haves.truths` line: `v2.1 requirements: 20 total / Mapped to phases: 20 ✓ / Unmapped: 0 ✓ / Complete: 18 / Pending: 2 (WIN-02, WIN-05)`. This is the post-edit state the plan and all success criteria specify; the intermediate delta the plan documented is moot because the on-disk state was already stale.
- **Files modified:** .planning/REQUIREMENTS.md
- **Verification:** All four `grep -q` acceptance checks in Task 4's verify block pass.
- **Committed in:** 53c75de (Task 4 commit)

---

**Total deviations:** 1 stale-state normalization (intent fully preserved; target shape matches must_haves.truths)
**Impact on plan:** None — the final state matches all six lines of the plan's success_criteria and frontmatter must_haves.truths. The pre-edit intermediate was a stale-data artifact, not a load-bearing reference.

## Issues Encountered

- **Pre-existing Linux test failures (out of scope per SCOPE BOUNDARY):** Running `uv run pytest -x` on the worktree surfaced ~17 failures and ~18 collection errors clustered in `tests/test_main_window_*.py`, `tests/test_media_keys_*.py`, `tests/test_import_dialog_qt.py`, `tests/test_station_list_panel.py`, `tests/test_twitch_auth.py`, `tests/test_ui_qt_scaffold.py`, and `tests/ui_qt/test_main_window_node_indicator.py`. **None of these test files import any of Phase 69's edited files.** Targeted re-run of one failing case (`tests/test_media_keys_mpris2.py::test_linux_mpris_backend_constructs`) PASSES in isolation, confirming the batch failures are pytest-collection / fixture artifacts on the Python 3.14 / PySide6 6.11 stack rather than deterministic regressions. The two new drift-guard pytests + the full `tests/test_packaging_spec.py` file (8 tests) + `tests/test_constants_drift.py` (5 tests) all pass clean. Logged inventory in `deferred-items.md` (worktree-local, not committed since `.planning/` is gitignored).
- **`uv.lock` mutated by `uv run` (env churn):** Each `uv run pytest` invocation rebuilds the venv and rewrites `uv.lock` (`version 2.1.63 -> 2.1.68` in the project line, irrelevant to Phase 69 scope). Excluded from all task commits to keep them focused on the intentional changes.
- **Stash-pop conflict on uv.lock during failure inventory:** Mid-Task-4, an exploratory `git stash` was used to confirm whether the test failures pre-existed the Phase 69 commits. The subsequent `git stash pop` conflicted on `uv.lock` (rewritten in the meantime by another `uv run`). Resolved by `git checkout -- uv.lock` to discard the env-churn diff, then `git stash pop` succeeded with all Task 4 edits intact. Verified post-pop via the six `grep -q` checks before committing.

## User Setup Required

None — all changes ship on Linux dev. Plan 02 will require operator-driven Win11 VM UAT (uninstall + recreate conda env from updated recipe + reinstall + AAC fixture playback).

## Next Phase Readiness

- **Plan 69-02 (Win11 VM UAT) is ready to dequeue.** Inputs ready: updated conda recipe in `packaging/windows/README.md`, build-time guard wired in `build.ps1` step 4b, post-bundle exit code 10 documented. Operator path: recreate `musicstreamer-build` conda env from the new README recipe, run `.\build.ps1`, verify step 4b emits `POST-BUNDLE PLUGIN GUARD OK`, install, attest both AAC fixture URLs play (DI.fm AAC + SomaFM HE-AAC), and flip WIN-05 from Pending to Complete.
- **No app-side code (`musicstreamer/`) was touched** — CONTEXT-D-02 boundary preserved.
- **No PyInstaller .spec or runtime_hook.py changes** — CONTEXT F-02 / F-03 assumptions preserved.
- **No Linux `gst-inspect` runtime test added** — CONTEXT P-03 explicitly rejected.
- **Drift-guard pytest live on Linux dev CI** — any future maintainer who edits `REQUIRED_PLUGIN_DLLS` without updating the README recipe (or vice versa) fails CI before any Windows build is attempted. Same for accidental Write-Error reintroduction or `exit 10` removal in build.ps1 step 4b.

## Self-Check: PASSED

- [x] `tools/check_bundle_plugins.py` exists — FOUND
- [x] `tools/check_bundle_plugins.py::REQUIRED_PLUGIN_DLLS` exact spec match — VERIFIED via `uv run python -c "..."` (Task 1 verify command)
- [x] `python tools/check_bundle_plugins.py --bundle /nonexistent/path` exits 10 — VERIFIED
- [x] `packaging/windows/build.ps1` contains `10=post-bundle plugin-presence guard fail (Phase 69)` in exit-code header — FOUND (line 7)
- [x] `packaging/windows/build.ps1` step 4b contains all five literals (POST-BUNDLE PLUGIN GUARD, python ..\..\tools\check_bundle_plugins.py, BUILD_FAIL reason=plugin_missing, exit 10, POST-BUNDLE PLUGIN GUARD OK) — VERIFIED
- [x] Ordering: line 284 (POST-BUNDLE ASSERTION OK) < line 301 (PLUGIN GUARD start) < line 307 (PLUGIN GUARD OK) < line 309 (Smoke test) — VERIFIED
- [x] `packaging/windows/README.md` conda recipe lists all five plugin packages + `gst-libav` + AAC rationale comment — VERIFIED
- [x] `tests/test_packaging_spec.py` defines `_README` + `readme_source` + two new test functions — FOUND at lines 45, 66, 417, 472
- [x] `uv run pytest tests/test_packaging_spec.py -x` exits 0 — 8 passed, 0 failed
- [x] `.planning/codebase/CONCERNS.md` reconciled (negative: no "Phase 44 bundling confirmed" / positive: "Phase 69 confirmed gst-libav was missing") — VERIFIED both checks
- [x] `.planning/REQUIREMENTS.md` WIN-05 in both sections + Coverage tally 20 total / 18 complete / 2 pending (WIN-02, WIN-05) — VERIFIED all four `grep -q` checks
- [x] Task 1 commit `26041b2` — FOUND in `git log --oneline`
- [x] Task 2 commit `39a98f2` — FOUND
- [x] Task 3 commit `3e4bd1d` — FOUND
- [x] Task 4 commit `53c75de` — FOUND

---
*Phase: 69-debug-why-aac-streams-aren-t-playing-in-windows-possibly-mis*
*Completed: 2026-05-11*
