---
phase: 65-show-current-version-in-app
verified: 2026-05-08T22:00:00Z
status: human_needed
score: 6/6 success_criteria verified (8/8 automated VER-02 sub-checks GREEN; 1 manual UAT item pending — VER-02-J final closure on Win11 VM)
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 6/6 (8/8 automated, 2 manual UAT pending)
  gaps_closed:
    - "VER-02-I (Linux Wayland visual confirm) — closed by 65-UAT.md test 1 result=pass"
    - "Build-tier hardening for VER-02-J — Plan 65-04 added pre-bundle clean (step 3c) + post-bundle dist-info singleton+version assertion (step 4a) + 2 source-text drift-guard tests"
    - "BLK-01 (vacuous _run_gui ordering test) — REVIEW-FIX commit 8bcb56f added _slice_run_gui body slicing"
    - "WR-01 (Write-Error preempts exit N) — REVIEW-FIX commit 39ce373 swapped Write-Error → Write-Host -ForegroundColor Red"
    - "WR-02 (fragile pyproject regex) — REVIEW-FIX commit d0b9b6a tightened to [^\\[]*?"
    - "WR-03 (loose version( substring match) — REVIEW-FIX commit 3e102e9 pinned to _pkg_version( or metadata.version("
    - "WR-04 (over-broad dist-info filter) — REVIEW-FIX commit cb44374 added regex post-filter for canonical X.Y.Z shape"
  gaps_remaining:
    - "VER-02-J final closure (Win11 VM bundle confirm post-Plan-65-04 hardening) — manual UAT, cannot be run on Linux dev"
  regressions: []
human_verification:
  - test: "VER-02-J — Re-run packaging/windows/build.ps1 on the Win11 VM with the Plan 65-04 hardening (steps 3c + 4a) in place, install the resulting installer, launch MusicStreamer.exe, open the hamburger menu, confirm the last entry shows v2.1.65 (matching pyproject.toml [project].version) — NOT v1.1.0"
    expected: "Build log contains 'PRE-BUNDLE CLEAN OK' AND 'POST-BUNDLE ASSERTION OK -- dist-info singleton: musicstreamer-2.1.65.dist-info (version 2.1.65 matches pyproject)'. Installed exe shows v2.1.65 in hamburger footer with no PackageNotFoundError at startup."
    why_human: "PowerShell + PyInstaller + Inno Setup + dist-info bundling behavior cannot be exercised on Linux dev. The source-text drift-guards (test_packaging_spec.py 6/6 GREEN) lock the build-script defenses structurally, but only a real Win11 VM build run can confirm the VER-02-J failure mode (stale dist-info shipped) is now actually caught + the bundled exe finally shows the right version."
---

# Phase 65: Show current version in app — Verification Report (Re-verification)

**Phase Goal (from ROADMAP.md):**
> The running app shows its current version (e.g. `v2.1.65`) as a disabled informational entry at the bottom of the hamburger menu, sourced at runtime from `pyproject.toml` via `importlib.metadata.version("musicstreamer")`. The stale `musicstreamer/__version__.py` mirror is retired; the Windows PyInstaller bundle ships the package's `dist-info` so the bundled exe reads the same version dev sees. Phase 65 is a pure consumer of Phase 63's auto-bump — `pyproject.toml [project].version` remains the single write site.

**Verified:** 2026-05-08T22:00:00Z
**Status:** human_needed — all 8 automated VER-02 sub-checks GREEN; build-tier hardening (Plan 65-04 + 5 review fixes) shipped; final VER-02-J closure requires manual Win11 VM UAT.
**Re-verification:** Yes — initial verification (2026-05-08T20:00:00Z) was status=human_needed with VER-02-J UAT showing v1.1.0 in the bundled exe. Plan 65-04 (gap-closure) added build-script hardening; code review surfaced 5 in-scope findings (BLK-01 + WR-01..04) which were all fixed.

---

## Goal Achievement

### Success Criteria (Six)

| # | Success Criterion | Status | Evidence |
|---|-------------------|--------|----------|
| 1 | Opening the hamburger menu shows a greyed-out `v{version}` entry as the literal last item, format `^\d+\.\d+\.\d+$`, equals `pyproject.toml [project].version` | VERIFIED | `musicstreamer/ui_qt/main_window.py:232-239`: separator + `self._act_version = self._menu.addAction(f"v{_pkg_version('musicstreamer')}")` + `setEnabled(False)`, placed AFTER the Phase 44 Node-missing block (line 225-230) so it is the literal last entry in either branch. Test `tests/test_main_window_integration.py::test_version_action_is_disabled_and_last` asserts `actions[-1] is window._act_version`, `isEnabled() is False`, regex `^v\d+\.\d+\.\d+$`. Direct grep verified: zero `addAction`/`addSeparator` calls on `self._menu` after `self._act_version`. LIVE: 3/3 menu tests GREEN; 58/58 plan-level tests GREEN. |
| 2 | `importlib.metadata.version("musicstreamer")` returns the same string as `pyproject.toml [project].version` | VERIFIED | Behavioral spot-check: `uv run python -c "from importlib.metadata import version; print(version('musicstreamer'))"` → `2.1.65` (matches `pyproject.toml:7` `version = "2.1.65"`). Test `tests/test_version.py::test_metadata_version_matches_pyproject` parses pyproject.toml via tomllib and asserts equality. `tests/test_version.py::test_metadata_version_is_semver_triple` enforces M.m.p shape. |
| 3 | `app.setApplicationVersion(...)` is called in `_run_gui` after `QApplication(argv)` | VERIFIED | `musicstreamer/__main__.py:185-189`: `app = QApplication(argv)` (185) → `setApplicationName` (186) → `setApplicationDisplayName` (187) → **`setApplicationVersion(_pkg_version("musicstreamer"))`** (188) → `setDesktopFileName` (189). Top-of-file import: line 9 `from importlib.metadata import version as _pkg_version`. Test `tests/test_main_run_gui_ordering.py::test_set_application_version_in_run_gui` (post-BLK-01 + WR-03 fix) asserts setver > qapp WITHIN _run_gui body slice (no longer cross-function-vacuous), AND requires the specific `from importlib.metadata import version` import (not bare `from importlib.metadata import`), AND requires `_pkg_version(` or `metadata.version(` near the setter site (not bare `version(` — defends against `packaging.version.version` regression). |
| 4 | `musicstreamer/__version__.py` deleted with zero remaining importers (D-06a grep gate clean) | VERIFIED | LIVE: `ls musicstreamer/__version__.py` → "No such file or directory". `git ls-files musicstreamer/__version__.py` → empty. D-06a grep gate re-run during this verification: `git grep -nl "from musicstreamer\.__version__\|musicstreamer/__version__\|__version__\.py\|musicstreamer\.__version__" -- ':!.planning' ':!.claude/worktrees' ':!.venv'` → exit 1 (zero hits). Deleted in commit `ee4d1f7`. |
| 5 | Windows PyInstaller spec includes `copy_metadata("musicstreamer")` so the bundled exe resolves `importlib.metadata.version` without `PackageNotFoundError` | VERIFIED | `packaging/windows/MusicStreamer.spec:17,41,111`: import `from PyInstaller.utils.hooks import collect_all, copy_metadata`; `_ms_datas = copy_metadata("musicstreamer")`; concatenated into `datas=[…] + _cn_datas + _sl_datas + _yt_datas + _ms_datas`. Locked by 4 source-text tests in `tests/test_packaging_spec.py` (test_spec_imports_copy_metadata, test_spec_includes_copy_metadata_for_musicstreamer, test_spec_concatenates_ms_datas_into_datas_list, test_spec_has_no_try_except_around_copy_metadata) — 4/4 GREEN. **Plus** Plan 65-04 build-tier hardening (see Key Link #3 below) catches drift if the bundle ever ships a stale or wrong dist-info. |
| 6 | No drift — `pyproject.toml [project].version` remains the single literal write site (Phase 63 auto-bump untouched) | VERIFIED | `pyproject.toml:7` `version = "2.1.65"` — produced by Phase 63 auto-bump (commit `14ffb02 chore(version): bump to 2.1.65 for Phase 65 completion`). `tools/bump_version.py` not modified by Phase 65 (no commits in 65-* touch it). Plan 65-04 modified ONLY `packaging/windows/build.ps1` and `tests/test_packaging_spec.py` — runtime read sites (`__main__.py`, `main_window.py`) and the spec are byte-identical to pre-Plan-65-04 state per 65-04-SUMMARY sha256 evidence. |

**Score:** 6/6 ROADMAP Success Criteria VERIFIED.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/__main__.py` | importlib.metadata import + setApplicationVersion call after QApplication(argv) | VERIFIED (wired, data flowing) | Line 9: `from importlib.metadata import version as _pkg_version`. Line 185: `app = QApplication(argv)`. Line 188: `app.setApplicationVersion(_pkg_version("musicstreamer"))`. Live `_pkg_version("musicstreamer")` returns `"2.1.65"` — real data flowing into Qt slot. Locked by `test_set_application_version_in_run_gui`. |
| `musicstreamer/ui_qt/main_window.py` | importlib.metadata import + addSeparator + addAction(f"v{version}") + setEnabled(False) at literal end of menu | VERIFIED (wired, data flowing) | Line 25 import; lines 232-239: comment block + separator + addAction (`f"v{_pkg_version('musicstreamer')}"`) + `setEnabled(False)`. Placed AFTER the Phase 44 conditional Node-missing block (lines 225-230). Test `test_version_action_is_disabled_and_last` proves literal-last position via `actions[-1] is window._act_version`. Direct grep verified: zero `self._menu.addAction\|addSeparator` calls after the version action site. Real data: action text resolves to `v2.1.65` at runtime via importlib.metadata. |
| `packaging/windows/MusicStreamer.spec` | copy_metadata import + _ms_datas assignment + concat into datas | VERIFIED (substantive, source-text locked) | Lines 17, 41, 111. 4/4 source-text tests GREEN. Spec sha256 unchanged across Plan 65-04 (locked by build.ps1 step 4a's dist-info singleton + version-match assertion at runtime, plus drift-guard tests). |
| `packaging/windows/build.ps1` | Pre-bundle clean step 3c + post-bundle dist-info assertion step 4a (Plan 65-04 hardening) + WR-01 Write-Host pattern (REVIEW-FIX) | VERIFIED (substantive, source-text locked) | Step ordering verified via grep: 3b → 3c → 4 → 4a → 5 → 6 (lines 123, 131, 164, 174, 279, 288). Step 3c contains: `Invoke-Native { uv pip uninstall musicstreamer -y ... }` (line 152), `Invoke-Native { uv pip install -e ..\.. ... }` (line 157), `BUILD_FAIL reason=pre_bundle_clean_failed` via `Write-Host` then `exit 8` (lines 159-160). Step 4a contains: `Get-ChildItem -Filter "musicstreamer-*.dist-info"` (line 236), regex post-filter to canonical `^musicstreamer-\d+\.\d+\.\d+\.dist-info$` shape (WR-04 fix), `$msDistInfos.Count -ne 1` singleton check, `$bundledVersion -ne $appVersion` version-match check, all failure paths via `Write-Host BUILD_FAIL reason=... -ForegroundColor Red` then `exit 9` (WR-01 fix). 2/2 drift-guard tests GREEN. |
| `musicstreamer/__version__.py` | DELETED | VERIFIED (deletion confirmed) | Filesystem absent; `git ls-files` empty; commit `ee4d1f7`. D-06a grep gate clean. |
| `tests/test_version.py` | NEW file with VER-02-A and VER-02-B tests | VERIFIED | 2 tests; both GREEN in live run (1.21s suite). |
| `tests/test_packaging_spec.py` | NEW file with VER-02-H + Plan 65-04 build_ps1_source drift guards | VERIFIED | 6 tests total: 4 spec_source (VER-02-H), 2 build_ps1_source (VER-02-J defense drift guards, with WR-01 follow-up tightening that requires `BUILD_FAIL` diagnostics emit via `Write-Host` not `Write-Error`). All 6 GREEN. |
| `tests/test_main_window_integration.py` | extended for VER-02-C/D/E | VERIFIED | `test_version_action_is_disabled_and_last` added; `test_hamburger_menu_actions` updated for 12-action total + regex; `test_hamburger_menu_separators` updated 3→4. All GREEN. |
| `tests/test_main_run_gui_ordering.py` | extended for VER-02-F + BLK-01 + WR-03 fixes | VERIFIED | `test_set_application_version_in_run_gui` added. Phase 65 BLK-01 fix: `_slice_run_gui()` helper (lines 35-55) restricts ordering tests to `_run_gui` body so they no longer cross-function-vacuously match `Gst.init(None)` in `_run_smoke`. Phase 65 WR-03 fix: setter-site check pinned to `_pkg_version(` or `metadata.version(` (not bare `version(`); import pinned to specific `version` symbol. All 3 ordering tests GREEN. |
| `.planning/REQUIREMENTS.md` | VER-02 row added; Phase 65 column = `Phase 65` | VERIFIED | Line 48: `**VER-02**: The running app surfaces its current version…` (marked `[x]` complete). Line 101: traceability row `\| VER-02 \| Phase 65 \| Complete \|`. Line 112: last-updated note references VER-02 + Phase 65. |
| `.planning/ROADMAP.md` | Phase 65 entry backfilled with Goal/Requirements/SC/Plans | VERIFIED | Line 509: `### Phase 65: Show current version in app` heading; lines 510-525 (approx): Goal + Depends on Phase 63 + Requirements: VER-02 + 6 Success Criteria + plan listing. Phase 65 also referenced as a dependency by Phase 66+ (line 531). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| Hamburger menu construction | `pyproject.toml [project].version` | `_pkg_version('musicstreamer')` (importlib.metadata) | WIRED | `main_window.py:25,238` — direct import + call site at menu addAction; data flow proven by 58/58 plan-level tests + behavioral spot-check returning real `2.1.65`. |
| `_run_gui` Qt setup | `pyproject.toml [project].version` | `_pkg_version("musicstreamer")` → `app.setApplicationVersion(...)` | WIRED | `__main__.py:9,188` — same dynamic read mechanism; locked by `test_set_application_version_in_run_gui` (post-BLK-01 + WR-03 fix; defends against both vacuous-ordering and wrong-`version`-symbol regressions). |
| Windows PyInstaller bundle | musicstreamer dist-info | `copy_metadata("musicstreamer")` in `_ms_datas` concat | WIRED (structural) | `MusicStreamer.spec:17,41,111` — source-text locked by 4 tests. |
| Windows build script (build.ps1) | bundled musicstreamer dist-info correctness | Plan 65-04 step 3c (pre-bundle clean) + step 4a (post-bundle singleton+version assertion) | WIRED (structural, post-Plan-65-04) | `build.ps1:131-162` (step 3c: uninstall+reinstall musicstreamer to materialize a fresh dist-info before pyinstaller) + `build.ps1:174-277` (step 4a: scan `dist/MusicStreamer/_internal` for `musicstreamer-X.Y.Z.dist-info`, assert singleton, read METADATA `Version:` line, assert equality with `$appVersion` parsed from pyproject.toml). On any failure, dump offending state to build log and `exit 9`. WR-01 fix: failure paths emit via `Write-Host -ForegroundColor Red` so the documented exit code actually fires (was previously masked by `$ErrorActionPreference = "Stop"` escalating `Write-Error` to a terminating error). 2/2 drift-guard tests GREEN. **Runtime confirmation requires manual UAT VER-02-J on Win11 VM.** |
| Read site mechanism | dev `.venv` dist-info | `importlib.metadata` machinery | WIRED (LIVE) | `uv run python -c "from importlib.metadata import version; print(version('musicstreamer'))"` returns `2.1.65` matching pyproject.toml. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `self._act_version` (menu footer) | `_pkg_version('musicstreamer')` | `.venv/lib/python3.14/site-packages/musicstreamer-2.1.65.dist-info/` (dev) → bundle dist-info via `copy_metadata` (Windows) | Yes (LIVE: `2.1.65`) | FLOWING — dev path proven by behavioral spot-check + 58/58 plan-level tests. Bundle path structurally guaranteed by spec edit + Plan 65-04 build-tier double-defense (pre-bundle clean materializes the right dist-info; post-bundle assertion fails the build if anything else ships). Final Win11 confirmation deferred to manual UAT VER-02-J. |
| `app.setApplicationVersion(...)` | `_pkg_version("musicstreamer")` | same as above | Yes | FLOWING — same import path as menu footer; locked by `test_set_application_version_in_run_gui` (post-BLK-01 + WR-03 fix). |

### CONTEXT.md Decisions D-01..D-13

| Decision | Implementation in Codebase | Status |
|----------|---------------------------|--------|
| D-01: Disabled QAction at bottom of `self._menu` after Group 3 + after Phase 44 Node-missing block | `main_window.py:232-239` — separator + addAction + setEnabled(False), placed AFTER the conditional Node-missing block (lines 225-230) | VERIFIED |
| D-02: `self._menu.addSeparator()` precedes the new action | `main_window.py:237` — separator immediately before addAction. `test_hamburger_menu_separators` pins separator count at 4 (was 3 pre-Phase-65). | VERIFIED |
| D-03: Constructed via `addAction(label).setEnabled(False)` (or `act.setEnabled(False)` after capture) | `main_window.py:238-239` — capture-then-disable variant per recommended retention pattern | VERIFIED |
| D-04: Menubar right-corner widget DECLINED | `grep "setCornerWidget" musicstreamer/ui_qt/main_window.py` → zero hits | VERIFIED (informational) |
| D-05: Runtime read uses `importlib.metadata.version("musicstreamer")` | `__main__.py:9` + `main_window.py:25` | VERIFIED |
| D-06: `musicstreamer/__version__.py` DELETED | File absent; `git ls-files` empty; deletion commit `ee4d1f7` | VERIFIED |
| D-06a: D-06a grep gate clean (zero importers) | LIVE re-run during this verification: zero hits (exit 1) | VERIFIED |
| D-07: `app.setApplicationVersion(...)` added in `_run_gui` after `QApplication(argv)` | `__main__.py:185-189`: QApplication → setApplicationName → setApplicationDisplayName → **setApplicationVersion** → setDesktopFileName | VERIFIED |
| D-08: PyInstaller spec includes `copy_metadata("musicstreamer")`; NO try/except fallback to placeholder | `MusicStreamer.spec:17,41,111`. Negative regression-lock test `test_spec_has_no_try_except_around_copy_metadata` GREEN. **Plan 65-04 EXTENDS** D-08's contract: D-08 says "fail loudly if metadata missing"; Plan 65-04 step 4a says "fail loudly if metadata is WRONG (stale dist-info shipped)" — strictly stronger, never weaker. | VERIFIED |
| D-09: Bundle-aware test guarding regression — option (a) unit test for `importlib.metadata` non-empty SemVer | `tests/test_version.py::test_metadata_version_is_semver_triple` enforces `^\d+\.\d+\.\d+$` | VERIFIED |
| D-10: Label format `v{version}` | `main_window.py:238`: `f"v{_pkg_version('musicstreamer')}"`. Test enforces `^v\d+\.\d+\.\d+$`. | VERIFIED |
| D-11: Read via QCoreApplication.applicationVersion() (RECOMMENDED) OR direct importlib.metadata (DEVIATION ACCEPTED) | DEVIATED per Plan 65-01 — read importlib.metadata directly at the menu construction site (test-friendly under pytest-qt fixtures that don't run `_run_gui`). Qt slot still set in `__main__.py` for Qt-internal reasons. Within planner-discretion latitude. | VERIFIED (within decision latitude) |
| D-12: Action is disabled (informational footer, no click target) | `main_window.py:239`: `setEnabled(False)`. Test `test_version_action_is_disabled_and_last` enforces `isEnabled() is False`. | VERIFIED |
| D-13: No tooltip beyond Qt's default | `grep "setToolTip\|setStatusTip" main_window.py | grep -i version` → zero hits | VERIFIED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `importlib.metadata.version("musicstreamer")` returns the canonical version | `uv run python -c "from importlib.metadata import version; print(version('musicstreamer'))"` | `2.1.65` (matches `pyproject.toml:7`) | PASS |
| Plan-level pytest suite (the binding gate) is GREEN | `uv run pytest tests/test_version.py tests/test_main_window_integration.py tests/test_main_run_gui_ordering.py tests/test_packaging_spec.py -x` | `58 passed, 1 warning in 1.21s` | PASS |
| `tests/test_packaging_spec.py` (post-Plan-65-04 + WR-01 follow-up) is GREEN | `uv run pytest tests/test_packaging_spec.py -v` | `6 passed, 1 warning in 0.09s` (4 spec + 2 build.ps1 drift guards) | PASS |
| D-06a grep gate returns zero importers of `__version__.py` | `git grep -nl "from musicstreamer\.__version__\|musicstreamer/__version__\|__version__\.py\|musicstreamer\.__version__" -- ':!.planning' ':!.claude/worktrees' ':!.venv'` | empty (exit 1) | PASS |
| `__version__.py` is gone from working tree | `ls musicstreamer/__version__.py` | "No such file or directory" | PASS |
| `pyproject.toml [project].version` matches Phase 63 auto-bump output for Phase 65 | `grep "^version" pyproject.toml` | `version = "2.1.65"` | PASS |
| Version footer is the literal last `addAction`/`addSeparator` on `self._menu` | Python regex over `main_window.py` source after `self._act_version` assignment | `[]` (zero hits — nothing comes after) | PASS |
| build.ps1 step ordering: 3b → 3c → 4 → 4a → 5 → 6 | `grep -n "^    # --- " packaging/windows/build.ps1` | Lines 94 (3), 111 (3a), 123 (3b), 131 (3c), 164 (4), 174 (4a), 279 (5), 288 (6), 317 (7) — exactly the order Plan 65-04 specified | PASS |
| build.ps1 WR-01 fix: zero `Write-Error` calls in failure paths (only the comment block describing the prohibition remains) | `grep -n "Write-Error" packaging/windows/build.ps1` | Only lines 19-20 (rationale comment block) | PASS |

All 9 spot-checks PASS.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| VER-02 | 65-01-PLAN, 65-02-PLAN, 65-03-PLAN, 65-04-PLAN | The running app surfaces its current version (read from `pyproject.toml` via `importlib.metadata`) as a disabled informational entry at the bottom of the hamburger menu. The Windows PyInstaller bundle ships `musicstreamer.dist-info` so the bundled exe reads the same version dev sees. | SATISFIED (8/8 automated sub-checks GREEN; 1 manual UAT item pending — VER-02-J final closure) | All 6 ROADMAP SCs verified above. REQUIREMENTS.md row marked `[x]` complete (line 48); traceability row `VER-02 \| Phase 65 \| Complete` (line 101). |

No orphaned requirements. REQUIREMENTS.md maps VER-02 to Phase 65 only; all four Phase 65 plans declare `requirements: [VER-02]` (Plans 65-01..65-04).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | (n/a) | (n/a) | (n/a) | No production-code stubs, TODOs, hardcoded empties, or placeholder strings introduced by Phase 65. The two `placeholder` token hits in `MusicStreamer.spec` and `tests/test_packaging_spec.py` are documentation comments referring to CONTEXT D-08's no-placeholder PROHIBITION (i.e., they describe what is forbidden, not what was shipped). build.ps1 contains the string "Write-Error" only in the WR-01 rationale comment block (lines 19-20) — every actual failure path uses `Write-Host ... -ForegroundColor Red` so `exit N` is reachable. |

### Pre-existing Issues Confirmed Not Caused by Phase 65

These are documented in `deferred-items.md` and confirmed pre-existing (reproduce on commit `f033cca`, the parent of all Phase 65 work):

1. `tests/test_import_dialog_qt.py::test_yt_scan_passes_through` — Qt fatal abort during `_YtScanWorker` thread cleanup when run as part of the full suite (passes 25/25 in isolation). Last touched in Phase 999.7. NOT caused by Phase 65.
2. `_FakePlayer` missing `underrun_recovery_started` signal — 18 errors + 16 failures across multiple test files using local `_FakePlayer` stubs that were not updated when Phase 62 added `Player.underrun_recovery_started`. NOT caused by Phase 65.

Plan 65-01 SUMMARY records: with both deselected, full suite runs 1145 passed / 0 failed.

### Code Review (REVIEW.md → REVIEW-FIX.md)

The phase code review (`65-REVIEW.md`, depth=standard) surfaced 9 findings: 1 BLOCKER, 4 WARNING, 4 INFO. The 5 in-scope findings (BLK-01 + WR-01..04) were all fixed in `65-REVIEW-FIX.md`:

| Finding | Type | Issue | Fix Commit | Verification |
|---------|------|-------|------------|--------------|
| BLK-01 | Blocker | `test_ensure_installed_runs_after_gst_init` was vacuously true — `str.find()` matched `Gst.init(None)` in `_run_smoke` (line 33) instead of `_run_gui` (line 167), comparing two unrelated functions | `8bcb56f` | `_slice_run_gui()` helper added; all 3 ordering tests now slice to `_run_gui` body before asserting. Verified by re-running tests post-fix. |
| WR-01 | Warning | `Write-Error ... ; exit N` never reached the `exit N` because `$ErrorActionPreference = "Stop"` escalated Write-Error to terminating; script always exited 1 instead of 8/9/etc. | `39ce373` | All 15+ failure paths swapped to `Write-Host ... -ForegroundColor Red` + `exit N`. Drift-guard tests (commit `a5a69ca`) now require `BUILD_FAIL reason=...` strings ship via `Write-Host` not `Write-Error`. |
| WR-02 | Warning | Fragile pyproject regex `(?ms)^\[project\].*?^version=...` could match `version=` lines in sibling tables | `d0b9b6a` | Regex tightened to `(?ms)^\[project\][^\[]*?^version=...` (lazy non-`[` prevents crossing into sibling tables). Diagnostic message clarified. |
| WR-03 | Warning | Permissive substring check `version(` in setter-site context window matched any `version(` call (e.g. `packaging.version.version("1.0")`) | `3e102e9` | Tightened to `_pkg_version(` or `metadata.version(`. Import pin tightened to specific `version` symbol (was: bare `from importlib.metadata import`). |
| WR-04 | Warning | `Get-ChildItem -Filter "musicstreamer-*.dist-info"` would over-match `musicstreamer-extras-1.0.0.dist-info` etc., causing false-positive `exit 9` | `cb44374` | Two-stage enumeration: broad filter preserved (drift-guard test compatibility) + regex post-filter to canonical `^musicstreamer-\d+\.\d+\.\d+\.dist-info$` shape. Failure-path diagnostic dump shows BOTH matching set AND broad set's rejected siblings. |

INFO-severity findings (IN-01..IN-04) were excluded per `fix_scope: critical_warning`. IN-01 was incidentally addressed by BLK-01's edits. IN-02..IN-04 remain open as future-hygiene items (none affect goal achievement).

After fixes: `uv run pytest tests/test_packaging_spec.py tests/test_main_run_gui_ordering.py -x` → 9 passed.

### Human Verification Required

One remaining manual UAT item — VER-02-J final closure on the Win11 VM, post-Plan-65-04 hardening.

#### 1. VER-02-J — Win11 VM bundle confirm (post-Plan-65-04 hardening)

**Test:** Pull main on the Win11 VM after Phase 65 closes. Run `packaging/windows/build.ps1` from a conda-forge GStreamer env. Confirm build log shows `PRE-BUNDLE CLEAN OK -- fresh musicstreamer dist-info materialized in build env` AND `POST-BUNDLE ASSERTION OK -- dist-info singleton: musicstreamer-2.1.65.dist-info (version 2.1.65 matches pyproject)`. Then install the produced `.exe`, launch `MusicStreamer.exe` from Start Menu, open the hamburger menu (≡), and confirm the last entry shows `v2.1.65` (matching `pyproject.toml [project].version`) — NOT `v1.1.0`.
**Expected:** Same `v{version}` shown in dev (`2.1.65`); no `PackageNotFoundError` at startup; no missing dist-info; footer renders correctly. Build log shows both PRE-BUNDLE CLEAN OK and POST-BUNDLE ASSERTION OK markers.
**Why human:** PowerShell + PyInstaller + Inno Setup + Windows dist-info bundling behavior cannot be exercised on Linux dev. Source-text drift-guards (`tests/test_packaging_spec.py` 6/6 GREEN) lock the build-script defenses structurally, but only a real Win11 VM build can confirm the VER-02-J failure mode (stale dist-info shipped) is now actually caught at build time + the bundled exe finally shows the right version.

**Note:** VER-02-I (Linux Wayland visual confirm) was PASSED in the previous UAT cycle (`65-UAT.md` test 1, result=pass). Re-running it after Plan 65-04 is not required — Plan 65-04 only modified `packaging/windows/build.ps1` and `tests/test_packaging_spec.py`; the Linux dev path is unaffected and the menu rendering test (`test_version_action_is_disabled_and_last`) is still GREEN.

---

## Gaps Summary

**No automated gaps.** All 6 ROADMAP Success Criteria are observably met in the codebase. All 8 automated VER-02 sub-checks (A through H) are GREEN. Plan 65-04 added defense-in-depth at the build-script tier to close the VER-02-J failure mode discovered during prior UAT (`65-UAT.md` test 2, result=issue, "No, I see v1.1.0"). Code review surfaced 5 in-scope findings, all fixed.

The **single remaining item** is the manual UAT confirmation that the Plan 65-04 hardening actually fixes the bundled-exe-shows-stale-version bug on the Win11 VM — this is by-design human-verification and cannot be tested on Linux dev (no PowerShell + PyInstaller + Inno Setup environment).

The single decision-level deviation (D-11 read-site mechanism — reading `importlib.metadata` directly at the menu construction site instead of via `QCoreApplication.applicationVersion()`) is within the planner-discretion latitude that CONTEXT D-11 explicitly grants and is rigorously documented in 65-01-SUMMARY.md.

---

## Re-verification Summary

| Aspect | Initial Verification (2026-05-08T20:00:00Z) | Re-verification (2026-05-08T22:00:00Z) |
|--------|---------------------------------------------|----------------------------------------|
| Status | human_needed | human_needed |
| Score | 6/6 SCs (8/8 automated; 2 manual UAT pending) | 6/6 SCs (8/8 automated; 1 manual UAT pending) |
| pyproject version | 2.1.63 | 2.1.65 (Phase 63 auto-bump for Phase 65 closeout) |
| VER-02-I | PENDING | CLOSED (PASS in 65-UAT.md test 1) |
| VER-02-J | PENDING (UAT showed v1.1.0 — gap surfaced) | PENDING-final-confirm (Plan 65-04 build-tier hardening shipped + 5 review fixes applied; final Win11 re-build UAT still required to close the gap end-to-end) |
| New artifacts since prior verification | — | `packaging/windows/build.ps1` step 3c + 4a; `tests/test_packaging_spec.py` 2 new build_ps1_source tests (with WR-01 follow-up tightening); 5 REVIEW-FIX commits (BLK-01 + WR-01..04) |
| Plan-level test count | 56 GREEN | 58 GREEN (4 spec + 2 build.ps1 drift guards = +2 tests; 3 ordering tests now also enforce body slicing) |
| Regressions | — | None |

---

## VERIFICATION COMPLETE — PASS (pending VER-02-J final UAT)

| Check | Status |
|-------|--------|
| SC-1 (greyed-out v{version} as last menu entry) | VERIFIED |
| SC-2 (importlib.metadata.version equals pyproject.toml [project].version) | VERIFIED |
| SC-3 (app.setApplicationVersion called in _run_gui after QApplication(argv)) | VERIFIED |
| SC-4 (`__version__.py` deleted; D-06a grep gate clean) | VERIFIED |
| SC-5 (PyInstaller spec includes copy_metadata("musicstreamer")) | VERIFIED |
| SC-6 (No drift — pyproject.toml [project].version remains single literal write site) | VERIFIED |
| D-01..D-13 (CONTEXT decisions) | All implemented or honored as informational/declined; D-11 deviation accepted within planner discretion; D-08 contract STRENGTHENED by Plan 65-04 |
| VER-02-A..VER-02-H (automated sub-checks) | 8/8 GREEN |
| VER-02-I (Linux Wayland visual UAT) | CLOSED (PASS in 65-UAT.md) |
| VER-02-J (Win11 VM bundle UAT — final confirmation post-Plan-65-04) | PENDING — manual UAT required |
| BLK-01 + WR-01..04 (code review findings) | All 5 in-scope findings FIXED (REVIEW-FIX.md commits 8bcb56f, 39ce373, d0b9b6a, 3e102e9, cb44374, a5a69ca) |

**Status:** `human_needed` — implementation + build-tier hardening + code-review fixes all complete. Single remaining item is the by-design VER-02-J Win11 VM final-confirmation UAT. The phase goal is achieved in the codebase; the Win11 bundled-exe behavior is structurally guaranteed by the new build-script invariants but final user-visible confirmation requires a real Win11 build run.

---

*Verified: 2026-05-08T22:00:00Z*
*Verifier: Claude (gsd-verifier)*
*Re-verification mode: post-Plan-65-04 + post-REVIEW-FIX*
