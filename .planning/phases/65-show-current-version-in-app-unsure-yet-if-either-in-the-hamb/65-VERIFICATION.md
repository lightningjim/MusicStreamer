---
phase: 65-show-current-version-in-app
verified: 2026-05-09T00:00:00Z
status: human_needed
score: 6/6 ROADMAP Success Criteria VERIFIED in codebase (8/8 automated VER-02 sub-checks GREEN; Plans 65-01..65-05 all complete; 1 manual UAT item pending — VER-02-J Win11 VM end-to-end retest)
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: "6/6 SCs (8/8 automated, 1 manual UAT pending VER-02-J post Plan 65-04)"
  gaps_closed:
    - "Plan 65-04 build-script defenses (step 3c PRE-BUNDLE CLEAN + step 4a POST-BUNDLE ASSERTION) shipped (Linux side: locked by drift-guard tests, GREEN)"
    - "Plan 65-05 closed Linux-detectable VER-02-J retest blocker — `uv pip` swapped to `python -m pip` in build.ps1 step 3c so the script can run on Win11 conda-forge spike env (where `uv` is not on PATH); drift-guard updated in lockstep with positive `python -m pip` lock + new negative drift-guard catching partial-revert"
    - "REVIEW-FIX commits (8bcb56f, 39ce373, d0b9b6a, 3e102e9, cb44374, a5a69ca) — all 5 in-scope code-review findings (BLK-01 + WR-01..04) remain fixed in current HEAD"
  gaps_remaining:
    - "VER-02-J final closure (Win11 VM end-to-end build + install + launch + hamburger inspection post-Plan-65-05) — pure manual UAT, cannot run on Linux dev (no PowerShell + PyInstaller + Inno Setup + conda-forge env)"
  regressions: []
human_verification:
  - test: "VER-02-J — Run packaging\\windows\\build.ps1 on the Win11 VM in the spike conda env (post-Plan-65-05). Confirm build log shows `=== PRE-BUNDLE CLEAN: python -m pip uninstall + reinstall musicstreamer ===`, `PRE-BUNDLE CLEAN OK -- fresh musicstreamer dist-info materialized in build env`, `BUILD_OK step=pyinstaller`, `POST-BUNDLE ASSERTION OK -- dist-info singleton: musicstreamer-2.1.65.dist-info (version 2.1.65 matches pyproject)`, exits 0. Install the produced .exe, launch MusicStreamer.exe, click hamburger menu (≡), confirm last entry shows `v2.1.65` (NOT `v1.1.0`), greyed out, non-clickable."
    expected: "All four log markers present (PRE-BUNDLE CLEAN OK, BUILD_OK step=pyinstaller, POST-BUNDLE ASSERTION OK with dist-info singleton + version-match phrase, exit 0). Installed exe shows `v2.1.65` in hamburger footer with no PackageNotFoundError at startup. Same VER-02-J validation_id reused from prior UAT cycle."
    why_human: "PowerShell + PyInstaller + Inno Setup + conda-forge spike env behavior cannot be exercised on Linux dev. The Linux orchestrator cannot drive Windows packaging directly. Drift-guard tests in tests/test_packaging_spec.py (6/6 GREEN) lock the build-script defenses structurally + assert `python -m pip` literals are on executable lines + assert zero `uv pip` literals on executable lines. But only a real Win11 VM build run can confirm: (a) the VER-02-J UAT retest blocker (Plan 65-04 step 3c crashing on missing `uv` CLI) is now actually unblocked by Plan 65-05's `python -m pip` swap, AND (b) the original VER-02-J failure mode (stale dist-info shipped → bundled exe shows v1.1.0) is now actually caught at build time by step 4a + the bundled exe finally shows the right version end-to-end."
---

# Phase 65: Show current version in app — Verification Report (Re-verification 2026-05-09)

**Phase Goal (from ROADMAP.md, lines 510):**

> The running app shows its current version (e.g. `v2.1.65`) as a disabled informational entry at the bottom of the hamburger menu, sourced at runtime from `pyproject.toml` via `importlib.metadata.version("musicstreamer")`. The stale `musicstreamer/__version__.py` mirror is retired; the Windows PyInstaller bundle ships the package's `dist-info` so the bundled exe reads the same version dev sees. Phase 65 is a pure consumer of Phase 63's auto-bump — `pyproject.toml [project].version` remains the single write site.

**Verified:** 2026-05-09T00:00:00Z (re-verification post Plans 65-04 + 65-05)
**Status:** `human_needed` — 6/6 ROADMAP Success Criteria VERIFIED in codebase. 8/8 automated VER-02 sub-checks GREEN. Build-tier double-defense (Plan 65-04: step 3c clean + step 4a assertion; Plan 65-05: pip-not-uv swap so step 3c runs on Win11 VM) shipped + locked by source-text drift-guards. Single remaining item: by-design Win11 VM end-to-end UAT confirmation.
**Re-verification:** Yes — supersedes prior 65-VERIFICATION.md (2026-05-08T22:00:00Z). The prior verification was `human_needed` pending VER-02-J post Plan 65-04; today's UAT retest surfaced that step 3c crashed on `uv` not being on PATH in the Win11 spike conda env; Plan 65-05 closed that Linux-detectable gap; the Win11 end-to-end retest is still by-design human-only and reuses the same VER-02-J validation_id.

---

## Goal Achievement

### ROADMAP Success Criteria (Six)

| # | Success Criterion | Status | Evidence |
|---|-------------------|--------|----------|
| 1 | Hamburger menu shows greyed-out `v{version}` as literal last item, format `^\d+\.\d+\.\d+$`, equals `pyproject.toml [project].version` | VERIFIED | `musicstreamer/ui_qt/main_window.py:237-239`: separator → `self._act_version = self._menu.addAction(f"v{_pkg_version('musicstreamer')}")` → `setEnabled(False)`. Placed AFTER the conditional Phase 44 Node-missing block (lines 225-230) so it is the literal last entry in either branch. Live regex spot-check: zero `self._menu.add(Action|Separator)` calls after `self._act_version` assignment. Test `tests/test_main_window_integration.py::test_version_action_is_disabled_and_last` enforces `actions[-1] is window._act_version` AND `isEnabled() is False` AND label regex `^v\d+\.\d+\.\d+$`. `test_hamburger_menu_actions` asserts `texts[:11] == EXPECTED_ACTION_TEXTS` + `len(actions) == 12` + regex on `texts[11]`. `test_hamburger_menu_separators` pins separator count at 4. All GREEN in current run (58/58). |
| 2 | `importlib.metadata.version("musicstreamer")` matches `pyproject.toml [project].version` (no drift) | VERIFIED | Live spot-check: `uv run python -c "from importlib.metadata import version; print(version('musicstreamer'))"` → `2.1.65` (matches `pyproject.toml:7` `version = "2.1.65"`). `tests/test_version.py::test_metadata_version_matches_pyproject` parses pyproject.toml via tomllib and asserts equality (GREEN). `tests/test_version.py::test_metadata_version_is_semver_triple` enforces M.m.p shape (GREEN). |
| 3 | `app.setApplicationVersion(...)` is called in `_run_gui` after `QApplication(argv)` | VERIFIED | `musicstreamer/__main__.py:185-189`: `app = QApplication(argv)` (185) → `setApplicationName("MusicStreamer")` (186) → `setApplicationDisplayName("MusicStreamer")` (187) → **`app.setApplicationVersion(_pkg_version("musicstreamer"))  # Phase 65 D-07`** (188) → `setDesktopFileName(constants.APP_ID)` (189). Top-of-file import: line 9 `from importlib.metadata import version as _pkg_version`. Test `tests/test_main_run_gui_ordering.py::test_set_application_version_in_run_gui` enforces setver > qapp WITHIN _run_gui body slice (post-BLK-01 `_slice_run_gui` fix), specific `from importlib.metadata import version` import, and `_pkg_version(` or `metadata.version(` proximity to setter (post-WR-03 fix). GREEN. |
| 4 | `musicstreamer/__version__.py` deleted with zero importers | VERIFIED | LIVE: `ls musicstreamer/__version__.py` → "No such file or directory". `git ls-files musicstreamer/__version__.py` → empty. D-06a grep gate re-run during this verification: `git grep -nl "from musicstreamer\.__version__\|musicstreamer/__version__\|__version__\.py\|musicstreamer\.__version__" -- ':!.planning' ':!.claude/worktrees' ':!.venv'` → exit 1 (zero hits). Deletion commit `ee4d1f7`. |
| 5 | Windows PyInstaller spec includes `copy_metadata("musicstreamer")` | VERIFIED | `packaging/windows/MusicStreamer.spec:17` — `from PyInstaller.utils.hooks import collect_all, copy_metadata`. Line 41 — `_ms_datas = copy_metadata("musicstreamer")`. Line 111 — `+ _ms_datas` concatenated into `datas=[…] + _cn_datas + _sl_datas + _yt_datas + _ms_datas`. Locked by 4 source-text tests in `tests/test_packaging_spec.py` (test_spec_imports_copy_metadata, test_spec_includes_copy_metadata_for_musicstreamer, test_spec_concatenates_ms_datas_into_datas_list, test_spec_has_no_try_except_around_copy_metadata) — 4/4 GREEN. **Plus** Plan 65-04 build-tier double-defense (Key Link #3 + #4 below) catches drift if the bundle ever ships a stale or wrong dist-info — independent of whether step 3c clean materialized the right one. |
| 6 | No drift — `pyproject.toml [project].version` remains single literal write site (Phase 63 auto-bump untouched) | VERIFIED | `pyproject.toml:7` `version = "2.1.65"` — Phase 63 auto-bump output for Phase 65 closeout. `tools/bump_version.py` not modified by any Phase 65 plan. Plans 65-04 and 65-05 modified ONLY `packaging/windows/build.ps1` and `tests/test_packaging_spec.py` (build-tier defenses + their drift-guards); Plans 65-01..65-03 modified the runtime read sites (`__main__.py`, `main_window.py`), the spec, deleted `__version__.py`, and added the version-read tests — none introduced an alternative write site for the version literal. `pyproject.toml [project].version` remains the single source of truth. |

**Score:** 6/6 ROADMAP Success Criteria VERIFIED.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/__main__.py` | importlib.metadata import + setApplicationVersion call after QApplication(argv) | VERIFIED (wired, data flowing) | Line 9 import; line 185 `app = QApplication(argv)`; line 188 `app.setApplicationVersion(_pkg_version("musicstreamer"))`. Live `_pkg_version("musicstreamer")` returns `"2.1.65"` — real data flowing into Qt slot. Locked by `test_set_application_version_in_run_gui`. |
| `musicstreamer/ui_qt/main_window.py` | importlib.metadata import + addSeparator + addAction(f"v{version}") + setEnabled(False) at literal end of menu | VERIFIED (wired, data flowing) | Line 25 import; lines 237-239 separator + addAction(`f"v{_pkg_version('musicstreamer')}"`) + setEnabled(False). Placed AFTER the conditional Phase 44 Node-missing block (225-230). Test `test_version_action_is_disabled_and_last` proves literal-last via `actions[-1] is window._act_version`. Live regex spot-check confirms zero `self._menu.add(Action|Separator)` calls after the version line. Real data: action text resolves to `v2.1.65` at runtime. |
| `packaging/windows/MusicStreamer.spec` | copy_metadata import + _ms_datas assignment + concat into datas | VERIFIED (substantive, source-text locked) | Lines 17, 41, 111. 4/4 source-text tests GREEN. Spec sha256 unchanged across Plans 65-04/05 per their SUMMARY evidence. |
| `packaging/windows/build.ps1` | Pre-bundle clean step 3c (Plan 65-04 + Plan 65-05 hardening) + post-bundle dist-info assertion step 4a + WR-01 Write-Host failure-emit pattern | VERIFIED (substantive, source-text locked) | Step ordering verified via grep: 3b(123) → 3c(131) → 4(170) → 4a(180) → 5(285) → 6(294). Step 3c contains: `Invoke-Native { python -m pip uninstall musicstreamer -y ... }` (line 158 — Plan 65-05 swap), `Invoke-Native { python -m pip install -e ..\.. ... }` (line 163), `BUILD_FAIL reason=pre_bundle_clean_failed` via `Write-Host -ForegroundColor Red` (line 165) then `exit 8` (line 166). Step 4a contains: `Get-ChildItem -Filter "musicstreamer-*.dist-info"` (line 242), regex post-filter to canonical `^musicstreamer-\d+\.\d+\.\d+\.dist-info$` shape (WR-04 fix), `$msDistInfos.Count -ne 1` singleton check (line 244), `$bundledVersion -ne $appVersion` version-match check (line 274), all failure paths via `Write-Host BUILD_FAIL reason=... -ForegroundColor Red` (WR-01) then `exit 9`. **Plan 65-05 negative-grep verified:** zero `uv pip uninstall musicstreamer` and zero `uv pip install -e` substrings on executable (non-comment) lines. **2/2 build_ps1_source drift-guard tests GREEN** (positive lock on `python -m pip` literals + new negative drift-guard catching partial-revert). |
| `musicstreamer/__version__.py` | DELETED | VERIFIED (deletion confirmed) | Filesystem absent; `git ls-files` empty; commit `ee4d1f7`. D-06a grep gate clean. |
| `tests/test_version.py` | NEW file with VER-02-A and VER-02-B tests | VERIFIED | 2 tests; both GREEN in 2026-05-09 run. |
| `tests/test_packaging_spec.py` | VER-02-H spec-source tests + Plan 65-04 build_ps1_source drift-guards + Plan 65-05 negative drift-guard | VERIFIED | 6 tests total: 4 spec_source (Plan 65-02 / VER-02-H), 2 build_ps1_source (Plans 65-04/05 / VER-02-J defenses, including Plan 65-05's negative drift-guard against partial-revert). All 6 GREEN. |
| `tests/test_main_window_integration.py` | extended for VER-02-C/D/E | VERIFIED | `test_version_action_is_disabled_and_last` + `test_hamburger_menu_actions` (12-action total + regex on texts[11]) + `test_hamburger_menu_separators` (count = 4). All GREEN. |
| `tests/test_main_run_gui_ordering.py` | extended for VER-02-F + BLK-01 body-slicing fix + WR-03 setter-site tightening | VERIFIED | `test_set_application_version_in_run_gui` + `_slice_run_gui()` helper restricting ordering tests to `_run_gui` body. All 3 ordering tests GREEN. |
| `.planning/REQUIREMENTS.md` | VER-02 row added; mapped to Phase 65 = Complete | VERIFIED | Line 48 `**VER-02**: ... *(Phase 65 — consumes Phase 63's auto-bump output)*` marked `[x]` complete. Line 101 traceability row `\| VER-02 \| Phase 65 \| Complete \|`. Line 112 last-updated note references VER-02 + Phase 65. |
| `.planning/ROADMAP.md` | Phase 65 entry backfilled with Goal/Requirements/SC/Plans | VERIFIED | Line 509 `### Phase 65: Show current version in app` heading; lines 510-525 Goal + Depends on Phase 63 + Requirements: VER-02 + 6 Success Criteria + plan listing. Phase 65 referenced as a dependency by Phase 66+ (line 533). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| Hamburger menu construction | `pyproject.toml [project].version` | `_pkg_version('musicstreamer')` (importlib.metadata) | WIRED | `main_window.py:25` import + `:238` call site at menu addAction. Data flow proven by 58/58 plan-level tests + behavioral spot-check returning real `2.1.65`. |
| `_run_gui` Qt setup | `pyproject.toml [project].version` | `_pkg_version("musicstreamer")` → `app.setApplicationVersion(...)` | WIRED | `__main__.py:9` import + `:188` setter call. Locked by `test_set_application_version_in_run_gui` (post-BLK-01 + WR-03 fix). |
| Windows PyInstaller bundle | musicstreamer dist-info | `copy_metadata("musicstreamer")` in `_ms_datas` concat | WIRED (structural) | `MusicStreamer.spec:17,41,111`. Source-text locked by 4 tests. |
| Windows build script (build.ps1) | bundled musicstreamer dist-info correctness — pre-bundle | Plan 65-04 step 3c (uninstall + reinstall musicstreamer in build env) — Plan 65-05 swapped `uv pip` → `python -m pip` for Win11 conda-env compatibility | WIRED (structural, post-Plans-65-04+05) | `build.ps1:131-168` (step 3c with the Plan 65-05 swap). Failure paths emit via `Write-Host -ForegroundColor Red` so `exit 8` is reachable (WR-01). 2/2 drift-guard tests GREEN; positive lock on `python -m pip` literals + negative drift-guard catches partial-revert. **Runtime confirmation requires manual UAT VER-02-J on Win11 VM.** |
| Windows build script (build.ps1) | bundled musicstreamer dist-info correctness — post-bundle | Plan 65-04 step 4a (scan `dist/MusicStreamer/_internal` for `musicstreamer-X.Y.Z.dist-info`, assert singleton, read METADATA `Version:`, assert equality with `$appVersion`) | WIRED (structural) | `build.ps1:180-283`. Lifted `$appVersion` parse from step 6 to step 4a (single source of truth). All 5 failure paths exit 9 with diagnostic `Write-Host BUILD_FAIL reason=... -ForegroundColor Red` then `exit 9`. WR-04 narrowed dist-info filter to canonical `^musicstreamer-\d+\.\d+\.\d+\.dist-info$` shape. **Runtime confirmation requires manual UAT VER-02-J on Win11 VM.** |
| Read site mechanism | dev `.venv` dist-info | `importlib.metadata` machinery | WIRED (LIVE) | `uv run python -c "from importlib.metadata import version; print(version('musicstreamer'))"` returns `2.1.65` matching pyproject.toml. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `self._act_version` (menu footer) | `_pkg_version('musicstreamer')` | `.venv/.../musicstreamer-2.1.65.dist-info/` (dev) → bundle dist-info via `copy_metadata` (Win) | Yes (LIVE: `2.1.65`) | FLOWING — dev path proven by behavioral spot-check + 58/58 tests. Bundle path structurally guaranteed by spec edit (Plan 65-02) + Plan 65-04 build-tier double-defense (3c clean + 4a assertion) + Plan 65-05 ensuring step 3c runs on Win11 VM. Final Win11 confirmation deferred to manual UAT VER-02-J. |
| `app.setApplicationVersion(...)` | `_pkg_version("musicstreamer")` | same as above | Yes | FLOWING — same import path; locked by `test_set_application_version_in_run_gui`. |

### CONTEXT.md Decisions D-01..D-13

| Decision | Implementation in Codebase | Status |
|----------|---------------------------|--------|
| D-01: Disabled QAction at bottom of `self._menu` after Group 3 + after Phase 44 Node-missing block | `main_window.py:237-239` — separator + addAction + setEnabled(False), placed AFTER the conditional Node-missing block (225-230) | VERIFIED |
| D-02: `self._menu.addSeparator()` precedes the new action | `main_window.py:237` — separator immediately before addAction. `test_hamburger_menu_separators` pins separator count at 4 (was 3 pre-Phase-65). | VERIFIED |
| D-03: Constructed via `addAction(label).setEnabled(False)` (or `act.setEnabled(False)` after capture) | `main_window.py:238-239` — capture-then-disable variant | VERIFIED |
| D-04: Menubar right-corner widget DECLINED | `grep "setCornerWidget" main_window.py` → zero hits | VERIFIED (informational) |
| D-05: Runtime read uses `importlib.metadata.version("musicstreamer")` | `__main__.py:9` + `main_window.py:25` | VERIFIED |
| D-06: `musicstreamer/__version__.py` DELETED | File absent; `git ls-files` empty; commit `ee4d1f7` | VERIFIED |
| D-06a: D-06a grep gate clean (zero importers) | LIVE re-run during this verification: zero hits (exit 1) | VERIFIED |
| D-07: `app.setApplicationVersion(...)` added in `_run_gui` after `QApplication(argv)` | `__main__.py:185-189`: QApplication → setApplicationName → setApplicationDisplayName → **setApplicationVersion** → setDesktopFileName | VERIFIED |
| D-08: PyInstaller spec includes `copy_metadata("musicstreamer")`; NO try/except fallback to placeholder | `MusicStreamer.spec:17,41,111`. Negative regression-lock test `test_spec_has_no_try_except_around_copy_metadata` GREEN. **Plans 65-04 + 65-05 EXTEND** D-08's contract: D-08 says "fail loudly if metadata is missing"; step 4a says "fail loudly if metadata is WRONG (stale dist-info shipped)" — strictly stronger, never weaker. | VERIFIED |
| D-09: Bundle-aware test guarding regression — option (a) unit test for `importlib.metadata` non-empty SemVer | `tests/test_version.py::test_metadata_version_is_semver_triple` enforces `^\d+\.\d+\.\d+$` | VERIFIED |
| D-10: Label format `v{version}` | `main_window.py:238`: `f"v{_pkg_version('musicstreamer')}"`. Test enforces `^v\d+\.\d+\.\d+$`. | VERIFIED |
| D-11: Read via QCoreApplication.applicationVersion() (RECOMMENDED) OR direct importlib.metadata (DEVIATION ACCEPTED) | DEVIATED per Plan 65-01 — read importlib.metadata directly at the menu construction site (test-friendly under pytest-qt fixtures that don't run `_run_gui`). Qt slot still set in `__main__.py` for Qt-internal reasons. Within planner-discretion latitude. | VERIFIED (within decision latitude) |
| D-12: Action is disabled (informational footer, no click target) | `main_window.py:239`: `setEnabled(False)`. Test `test_version_action_is_disabled_and_last` enforces `isEnabled() is False`. | VERIFIED |
| D-13: No tooltip beyond Qt's default | `grep "setToolTip\|setStatusTip" main_window.py | grep -i version` → zero hits | VERIFIED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `importlib.metadata.version("musicstreamer")` returns the canonical version | `uv run python -c "from importlib.metadata import version; print(version('musicstreamer'))"` | `2.1.65` (matches `pyproject.toml:7`) | PASS |
| Plan-level pytest suite (the binding gate) is GREEN | `uv run pytest tests/test_version.py tests/test_packaging_spec.py tests/test_main_run_gui_ordering.py tests/test_main_window_integration.py -x` | `58 passed, 1 warning in 1.20s` | PASS |
| `tests/test_packaging_spec.py` (post-Plan-65-04 + 65-05) is GREEN | included in above run | `6 tests passed` (4 spec_source + 2 build_ps1_source) | PASS |
| D-06a grep gate returns zero importers of `__version__.py` | `git grep -nl "from musicstreamer\.__version__\|musicstreamer/__version__\|__version__\.py\|musicstreamer\.__version__" -- ':!.planning' ':!.claude/worktrees' ':!.venv'` | empty (exit 1) | PASS |
| `__version__.py` is gone from working tree | `ls musicstreamer/__version__.py` | "No such file or directory" | PASS |
| `pyproject.toml [project].version` matches Phase 63 auto-bump output for Phase 65 | `grep "^version" pyproject.toml` | `version = "2.1.65"` | PASS |
| Version footer is the literal last `addAction`/`addSeparator` on `self._menu` | Python regex over `main_window.py` source after `self._act_version` assignment | `[]` (zero hits — nothing comes after) | PASS |
| build.ps1 step ordering: 3b → 3c → 4 → 4a → 5 → 6 | `grep -nE '^[[:space:]]+# --- (3b\|3c\|4\|4a\|5\|6)' packaging/windows/build.ps1` | 123, 131, 170, 180, 285, 294 — exact ordering | PASS |
| build.ps1 WR-01 fix: zero `Write-Error` calls in failure paths (only the comment block describing the prohibition remains) | `grep -n "Write-Error" packaging/windows/build.ps1` | Only lines 19-20 (rationale comment block) | PASS |
| build.ps1 Plan-65-05 swap: zero `uv pip uninstall musicstreamer` / `uv pip install -e` on executable lines | `grep -vE '^[[:space:]]*#' build.ps1 \| grep -c 'uv pip uninstall musicstreamer\|uv pip install -e'` | `0` | PASS |
| build.ps1 Plan-65-05 swap: positive `python -m pip uninstall musicstreamer` + `python -m pip install -e` present on executable lines | grep on build.ps1 | line 158 + line 163 (executable) | PASS |

All 11 spot-checks PASS.

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| VER-02 | 65-01-PLAN, 65-02-PLAN, 65-03-PLAN, 65-04-PLAN, 65-05-PLAN | The running app surfaces its current version (read from `pyproject.toml` via `importlib.metadata`) as a disabled informational entry at the bottom of the hamburger menu. The Windows PyInstaller bundle ships `musicstreamer.dist-info` so the bundled exe reads the same version dev sees. | SATISFIED on Linux dev (8/8 automated sub-checks GREEN) — pending Win11 VM end-to-end UAT (VER-02-J) | All 6 ROADMAP SCs verified above. REQUIREMENTS.md row marked `[x]` complete (line 48); traceability row `VER-02 \| Phase 65 \| Complete` (line 101). |

No orphaned requirements. REQUIREMENTS.md maps VER-02 to Phase 65 only; all five Phase 65 plans declare `requirements: [VER-02]`. The plan-level `requirements:` declarations cover the full set of ROADMAP success criteria.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | (n/a) | (n/a) | (n/a) | No production-code stubs, TODOs, hardcoded empties, or placeholder strings introduced by Phase 65. The two `placeholder` token hits in `MusicStreamer.spec` and `tests/test_packaging_spec.py` are documentation comments referring to CONTEXT D-08's no-placeholder PROHIBITION (i.e., they describe what is forbidden, not what was shipped). build.ps1 contains the string "Write-Error" only in the WR-01 rationale comment block (lines 19-20) — every actual failure path uses `Write-Host ... -ForegroundColor Red` so `exit N` is reachable. The `uv pip` token in build.ps1 appears only in the Plan-65-05 historical-rationale comment block (lines 132-156) — every executable command line uses `python -m pip` (verified by negative grep). |

### Pre-existing Issues Confirmed Not Caused by Phase 65

These are documented in `deferred-items.md` and confirmed pre-existing (reproduce on commit `f033cca`, the parent of all Phase 65 work):

1. `tests/test_import_dialog_qt.py::test_yt_scan_passes_through` — Qt fatal abort during `_YtScanWorker` thread cleanup when run as part of the full suite (passes 25/25 in isolation). Last touched in Phase 999.7. NOT caused by Phase 65.
2. `_FakePlayer` missing `underrun_recovery_started` signal — 18 errors + 16 failures across multiple test files using local `_FakePlayer` stubs that were not updated when Phase 62 added `Player.underrun_recovery_started`. NOT caused by Phase 65.

The Phase 65 plan-level suite (`uv run pytest tests/test_version.py tests/test_packaging_spec.py tests/test_main_run_gui_ordering.py tests/test_main_window_integration.py -x`) is the binding gate and runs 58/58 GREEN.

### Code Review (REVIEW.md → REVIEW-FIX.md) — carried forward from prior verification

The phase code review (`65-REVIEW.md`, depth=standard) surfaced 9 findings: 1 BLOCKER, 4 WARNING, 4 INFO. The 5 in-scope findings (BLK-01 + WR-01..04) were all fixed in `65-REVIEW-FIX.md`. Today's re-verification confirms they remain fixed in HEAD:

| Finding | Type | Issue | Fix Commit | Verification |
|---------|------|-------|------------|--------------|
| BLK-01 | Blocker | `test_ensure_installed_runs_after_gst_init` was vacuously true — `str.find()` matched `Gst.init(None)` in `_run_smoke` (line 33) instead of `_run_gui` (line 167) | `8bcb56f` | `_slice_run_gui()` helper added; all 3 ordering tests now slice to `_run_gui` body. Verified GREEN in current run. |
| WR-01 | Warning | `Write-Error ... ; exit N` never reached `exit N` because `$ErrorActionPreference = "Stop"` escalated Write-Error to terminating; script always exited 1 | `39ce373` | All failure paths swapped to `Write-Host ... -ForegroundColor Red` + `exit N`. Verified by current grep: zero `Write-Error` calls outside the rationale-comment block (lines 19-20). |
| WR-02 | Warning | Fragile pyproject regex could match `version=` lines in sibling tables | `d0b9b6a` | Regex tightened to `(?ms)^\[project\][^\[]*?^version=...` (lazy non-`[` prevents crossing into sibling tables). |
| WR-03 | Warning | Permissive substring check `version(` in setter-site context window matched any `version(` call | `3e102e9` | Tightened to `_pkg_version(` or `metadata.version(`. Verified GREEN in current run. |
| WR-04 | Warning | `Get-ChildItem -Filter "musicstreamer-*.dist-info"` would over-match `musicstreamer-extras-1.0.0.dist-info` etc. | `cb44374` | Two-stage enumeration: broad filter preserved (drift-guard test compatibility) + regex post-filter to canonical `^musicstreamer-\d+\.\d+\.\d+\.dist-info$` shape. |

INFO-severity findings (IN-01..IN-04) excluded per `fix_scope: critical_warning`. IN-01 was incidentally addressed by BLK-01's edits. IN-02..IN-04 remain open as future-hygiene items (none affect goal achievement).

### Plan-Level Closure Status

| Plan | Title | Status | Evidence |
|------|-------|--------|----------|
| 65-01 | Runtime version-read site (hamburger menu footer + setApplicationVersion + tests + REQUIREMENTS backfill) | COMPLETE | All artifacts shipped + tests GREEN |
| 65-02 | PyInstaller spec ships musicstreamer dist-info (copy_metadata + drift-guard tests) | COMPLETE | Spec edited + 4 source-text tests GREEN |
| 65-03 | Delete musicstreamer/__version__.py | COMPLETE | File deleted (commit `ee4d1f7`); D-06a grep gate clean |
| 65-04 | build.ps1 PRE-BUNDLE CLEAN + POST-BUNDLE ASSERTION (close VER-02-J) | COMPLETE on Linux dev (build-script defenses shipped + drift-guards GREEN); pending Win11 UAT for end-to-end runtime confirmation |
| 65-05 | build.ps1 step 3c `uv pip` → `python -m pip` swap (close UAT-discovered gap that the spike conda env doesn't ship `uv`) | COMPLETE on Linux dev (positive `python -m pip` lock + new negative drift-guard against partial-revert; both GREEN); pending Win11 UAT for end-to-end runtime confirmation |

### Human Verification Required

One remaining manual UAT item — VER-02-J final closure on the Win11 VM, post-Plan-65-05 hardening.

#### 1. VER-02-J — Win11 VM end-to-end build + install + version-display retest (post-Plan-65-05)

**Test:**
1. Pull main on the Win11 VM after Phase 65 closes (`git pull`).
2. Open a fresh PowerShell with the spike conda env activated (`conda activate spike`).
3. Run `cd packaging\windows; .\build.ps1` (or, per the spike-findings landmine for Miniforge cmd.exe, `powershell -ExecutionPolicy Bypass -File .\build.ps1`).
4. Confirm the build log shows ALL FOUR markers in order:
   - `=== PRE-BUNDLE CLEAN: python -m pip uninstall + reinstall musicstreamer ===` (Plan 65-05 banner — confirms the swap reached the VM)
   - `PRE-BUNDLE CLEAN OK -- fresh musicstreamer dist-info materialized in build env`
   - `BUILD_OK step=pyinstaller exe='...'`
   - `POST-BUNDLE ASSERTION OK -- dist-info singleton: musicstreamer-2.1.65.dist-info (version 2.1.65 matches pyproject)`
   - Build exits 0.
5. Install the produced `MusicStreamer-2.1.65-win64-setup.exe`, launch `MusicStreamer.exe` from Start Menu.
6. Open the hamburger menu (≡), confirm the last entry shows `v2.1.65` (matching `pyproject.toml [project].version`) — NOT `v1.1.0`. Confirm it's greyed out and non-clickable.

**Expected:** All four log markers present + exit 0 + installed exe shows `v2.1.65` in hamburger footer with no `PackageNotFoundError` at startup.

**Why human:** PowerShell + PyInstaller + Inno Setup + conda-forge spike env behavior cannot be exercised on Linux dev. The Linux orchestrator cannot drive Windows packaging directly. Drift-guard tests in `tests/test_packaging_spec.py` (6/6 GREEN) lock the build-script defenses structurally + assert `python -m pip` literals are on executable lines + assert zero `uv pip` literals on executable lines via the new negative drift-guard. But only a real Win11 VM build run can confirm the two end-to-end conditions: (a) the Plan-65-05 swap actually unblocks the build (no more `uv : The term 'uv' is not recognized as the name of a cmdlet...` crash), AND (b) the original VER-02-J failure mode (stale dist-info → bundled exe shows v1.1.0) is now actually caught at build time by step 4a + the bundled exe finally shows the right version end-to-end.

**Note:** VER-02-I (Linux Wayland visual confirm) was PASSED in 65-UAT.md test 1 (result=pass). Re-running VER-02-I after Plans 65-04/05 is NOT required — both plans only modified `packaging/windows/build.ps1` and `tests/test_packaging_spec.py`; the Linux dev path is unaffected and the menu rendering tests are still GREEN.

---

## Gaps Summary

**No automated gaps.** All 6 ROADMAP Success Criteria are observably met in the codebase. All 8 automated VER-02 sub-checks (A through H) are GREEN. Plans 65-01..65-05 all complete on the Linux dev side. Plan 65-04 added defense-in-depth at the build-script tier; Plan 65-05 closed the Linux-detectable gap surfaced during today's UAT retest (`uv` not on PATH in the Win11 spike conda env). The Linux drift-guards are in lockstep with the build script.

The **single remaining item** is the manual UAT confirmation that the Plans 65-04 + 65-05 hardening together actually fixes the bundled-exe-shows-stale-version bug on the Win11 VM end-to-end — this is by-design human-verification and cannot be tested on Linux dev (no PowerShell + PyInstaller + Inno Setup + conda-forge env).

The single decision-level deviation (D-11 read-site mechanism — reading `importlib.metadata` directly at the menu construction site instead of via `QCoreApplication.applicationVersion()`) is within the planner-discretion latitude that CONTEXT D-11 explicitly grants and is rigorously documented in 65-01-SUMMARY.md.

---

## Re-verification Summary

| Aspect | Initial Verification (2026-05-08T20:00:00Z) | Prior Re-verification (2026-05-08T22:00:00Z) | Today's Re-verification (2026-05-09T00:00:00Z) |
|--------|---------------------------------------------|----------------------------------------------|---|
| Status | human_needed | human_needed | human_needed |
| Score | 6/6 SCs (8/8 automated; 2 manual UAT pending) | 6/6 SCs (8/8 automated; 1 manual UAT pending post-65-04) | 6/6 SCs (8/8 automated; 1 manual UAT pending post-65-05) |
| pyproject version | 2.1.63 | 2.1.65 (Phase 63 auto-bump for Phase 65) | 2.1.65 (unchanged; single write site invariant holds) |
| VER-02-I | PENDING | CLOSED (PASS in 65-UAT.md test 1) | CLOSED (carried forward; runtime read path on Linux untouched by Plans 65-04/05) |
| VER-02-J | PENDING (UAT showed v1.1.0) | PENDING-final-confirm (Plan 65-04 hardening shipped + 5 review fixes applied) | PENDING-final-confirm (Plan 65-05 closed the Linux-detectable retest blocker `uv not on PATH`; Win11 end-to-end retest still required) |
| New artifacts since prior verification | — | `packaging/windows/build.ps1` step 3c+4a; `tests/test_packaging_spec.py` 2 build_ps1_source tests; 5 REVIEW-FIX commits | `packaging/windows/build.ps1` step 3c rewritten (`uv pip` → `python -m pip`) + DO-NOT-REMOVE breadcrumb; `tests/test_packaging_spec.py::test_build_ps1_pre_bundle_clean_present` updated assertions + new negative drift-guard against partial-revert |
| Plan-level test count | 56 GREEN | 58 GREEN (+2 build_ps1_source drift guards; +3 ordering body-slicing fixes) | 58 GREEN (same count; one test body extended with negative drift-guard sanity-check, one with positive lock-swap) |
| Regressions | — | None | None |

---

## VERIFICATION COMPLETE — PASS (pending VER-02-J Win11 VM final UAT)

| Check | Status |
|-------|--------|
| SC-1 (greyed-out v{version} as last menu entry) | VERIFIED |
| SC-2 (importlib.metadata.version equals pyproject.toml [project].version) | VERIFIED |
| SC-3 (app.setApplicationVersion called in _run_gui after QApplication(argv)) | VERIFIED |
| SC-4 (`__version__.py` deleted; D-06a grep gate clean) | VERIFIED |
| SC-5 (PyInstaller spec includes copy_metadata("musicstreamer")) | VERIFIED |
| SC-6 (No drift — pyproject.toml [project].version remains single literal write site) | VERIFIED |
| D-01..D-13 (CONTEXT decisions) | All implemented or honored as informational/declined; D-11 deviation accepted within planner discretion; D-08 contract STRENGTHENED by Plans 65-04+05 |
| VER-02-A..VER-02-H (automated sub-checks) | 8/8 GREEN |
| VER-02-I (Linux Wayland visual UAT) | CLOSED (PASS in 65-UAT.md) |
| VER-02-J (Win11 VM bundle end-to-end UAT — post Plans 65-04+05) | PENDING — manual UAT required (Win11 VM end-to-end build + install + hamburger inspection) |
| BLK-01 + WR-01..04 (code review findings) | All 5 in-scope findings remain FIXED |
| Plans 65-01..65-05 plan-level completion | All 5 plans COMPLETE on Linux dev side |

**Status:** `human_needed` — implementation + build-tier hardening (Plans 65-01..65-04) + Win11-VM-compatibility fix (Plan 65-05) + code-review fixes are all complete on the Linux dev side. Single remaining item is the by-design VER-02-J Win11 VM final-confirmation UAT. The phase goal is achieved in the codebase; the Win11 bundled-exe behavior is structurally guaranteed by the new build-script invariants (step 3c clean materializes one fresh dist-info; step 4a asserts singleton + version-match) but final user-visible end-to-end confirmation requires a real Win11 build run.

---

*Verified: 2026-05-09T00:00:00Z*
*Verifier: Claude (gsd-verifier)*
*Re-verification mode: post-Plan-65-05 (supersedes 2026-05-08T22:00:00Z verification post-Plan-65-04 + REVIEW-FIX)*
