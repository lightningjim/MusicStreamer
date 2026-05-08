---
phase: 65-show-current-version-in-app
verified: 2026-05-08T20:00:00Z
status: human_needed
score: 6/6 success_criteria verified (8/8 automated VER-02 sub-checks GREEN; 2 manual UAT items pending)
overrides_applied: 0
---

# Phase 65: Show current version in app — Verification Report

**Phase Goal (ROADMAP backfilled by Plan 65-01 Task 1):**
> The running app shows its current version (e.g. `v2.1.65`) as a disabled informational entry at the bottom of the hamburger menu, sourced at runtime from `pyproject.toml` via `importlib.metadata.version("musicstreamer")`. The stale `musicstreamer/__version__.py` mirror is retired; the Windows PyInstaller bundle ships the package's `dist-info` so the bundled exe reads the same version dev sees. Phase 65 is a pure consumer of Phase 63's auto-bump — `pyproject.toml [project].version` remains the single write site.

**Verified:** 2026-05-08T20:00:00Z
**Status:** human_needed — all 8 automated VER-02 sub-checks GREEN; manual UAT VER-02-I (Linux Wayland visual confirm) and VER-02-J (Win11 VM bundle confirm) deferred to `/gsd-verify-work` per phase plan.
**Re-verification:** No — initial verification.

---

## Goal Achievement

### Success Criteria (Six)

| # | Success Criterion | Status | Evidence |
|---|-------------------|--------|----------|
| 1 | Opening the hamburger menu shows a greyed-out `v{version}` entry as the literal last item, format `^\d+\.\d+\.\d+$`, equals `pyproject.toml [project].version` | VERIFIED | `musicstreamer/ui_qt/main_window.py:232-239` — `self._menu.addSeparator()` + `self._act_version = self._menu.addAction(f"v{_pkg_version('musicstreamer')}")` + `setEnabled(False)`, placed AFTER the conditional Phase 44 Node-missing block (so it is the literal last entry in either branch). Locked by `tests/test_main_window_integration.py::test_version_action_is_disabled_and_last` (asserts `actions[-1] is window._act_version`, `isEnabled() is False`, regex `^v\d+\.\d+\.\d+$`) and `test_hamburger_menu_actions` (12 actions; last regex matched). LIVE: 56/56 plan-level tests pass. |
| 2 | `importlib.metadata.version("musicstreamer")` returns the same string as `pyproject.toml [project].version` | VERIFIED | `tests/test_version.py::test_metadata_version_matches_pyproject` parses `pyproject.toml` via `tomllib` and asserts equality with `importlib.metadata.version("musicstreamer")`. LIVE behavioral spot-check: `uv run python -c "from importlib.metadata import version; print(version('musicstreamer'))"` → `2.1.63` (matches `pyproject.toml:7` `version = "2.1.63"`). `tests/test_version.py::test_metadata_version_is_semver_triple` enforces M.m.p shape. |
| 3 | `app.setApplicationVersion(...)` is called in `_run_gui` after `QApplication(argv)` | VERIFIED | `musicstreamer/__main__.py:185-188`: `app = QApplication(argv)` (line 185) followed by `app.setApplicationName("MusicStreamer")` (186), `app.setApplicationDisplayName("MusicStreamer")` (187), `app.setApplicationVersion(_pkg_version("musicstreamer"))` (188). Pinned by `tests/test_main_run_gui_ordering.py::test_set_application_version_in_run_gui` — asserts setter byte-position > QApplication(argv) byte-position AND that `from importlib.metadata import` is imported AND that `_pkg_version(` or `version(` is in the 200 bytes after setter site. |
| 4 | `musicstreamer/__version__.py` is deleted with zero remaining importers (D-06a grep gate clean) | VERIFIED | `git ls-files musicstreamer/__version__.py` returns empty; `ls musicstreamer/__version__.py` returns "No such file or directory". LIVE D-06a grep gate run during this verification: `git grep -nl "from musicstreamer\.__version__\|musicstreamer/__version__\|__version__\.py\|musicstreamer\.__version__" -- ':!.planning' ':!.claude/worktrees' ':!.venv'` → zero hits → `GREP_GATE_OK`. Deleted in commit `ee4d1f7`. |
| 5 | The Windows PyInstaller spec includes `copy_metadata("musicstreamer")` so the bundled exe resolves `importlib.metadata.version` without `PackageNotFoundError` | VERIFIED | `packaging/windows/MusicStreamer.spec:17,41,111`: import extended to `from PyInstaller.utils.hooks import collect_all, copy_metadata`; `_ms_datas = copy_metadata("musicstreamer")` assignment alongside `_cn_datas`/`_sl_datas`/`_yt_datas`; concatenated into `datas=[…] + _cn_datas + _sl_datas + _yt_datas + _ms_datas`. Locked by 4 tests in `tests/test_packaging_spec.py` — `test_spec_imports_copy_metadata`, `test_spec_includes_copy_metadata_for_musicstreamer`, `test_spec_includes_copy_metadata_in_datas`, `test_spec_has_no_try_except_around_copy_metadata` (negative regression-lock for CONTEXT D-08 prohibition). 4/4 GREEN. |
| 6 | No drift introduced — `pyproject.toml [project].version` remains the single literal write site (Phase 63 auto-bump untouched) | VERIFIED | `pyproject.toml:7` `version = "2.1.63"` — unchanged from Phase 63 auto-bump output (`git diff HEAD -- pyproject.toml` empty across all three Plan 65 worktree merges). `packaging/windows/build.ps1` unchanged (`git diff HEAD -- packaging/windows/build.ps1` empty). `tools/bump_version.py` not touched by Phase 65 (no commits in 65-* touch it). The Phase 63 auto-bump for Phase 65's own completion commit will produce `2.1.65` on the closeout commit — that is the expected and untouched mechanism. |

**Score:** 6/6 ROADMAP Success Criteria VERIFIED.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/__main__.py` | importlib.metadata import + setApplicationVersion call between QApplication and setDesktopFileName | VERIFIED (wired, data flowing) | Line 9: `from importlib.metadata import version as _pkg_version`. Line 185: `app = QApplication(argv)`. Line 188: `app.setApplicationVersion(_pkg_version("musicstreamer"))`. Live `_pkg_version("musicstreamer")` returns `"2.1.63"` — real data flowing into Qt slot. |
| `musicstreamer/ui_qt/main_window.py` | importlib.metadata import + addSeparator + addAction(f"v{version}") + setEnabled(False) at literal end of menu | VERIFIED (wired, data flowing) | Line 25: import. Lines 232-239: separator + addAction (`f"v{_pkg_version('musicstreamer')}"`) + `setEnabled(False)`. Placed AFTER the Phase 44 `act_node_missing` conditional block. Test `actions[-1] is window._act_version` proves literal-last position. Real data: action text resolves to `v2.1.63` at runtime via importlib.metadata. |
| `packaging/windows/MusicStreamer.spec` | copy_metadata import + _ms_datas assignment + concat into datas | VERIFIED (substantive, source-text locked) | Lines 17, 41, 111. 4/4 source-text tests GREEN. (Bundle-side runtime behavior is the manual UAT VER-02-J — see Human Verification.) |
| `musicstreamer/__version__.py` | DELETED | VERIFIED (deletion confirmed) | Filesystem absent; `git ls-files` empty; commit `ee4d1f7`. |
| `tests/test_version.py` | NEW file with VER-02-A and VER-02-B tests | VERIFIED | 39 lines; 2 tests; both GREEN in live run. |
| `tests/test_packaging_spec.py` | NEW file with VER-02-H (+ negative regression-lock) | VERIFIED | 4 source-text tests; all GREEN in live run. |
| `tests/test_main_window_integration.py` | extended for VER-02-C/D/E | VERIFIED | `test_version_action_is_disabled_and_last` added; `test_hamburger_menu_actions` updated for 12-action total + regex; `test_hamburger_menu_separators` updated 3→4. |
| `tests/test_main_run_gui_ordering.py` | extended for VER-02-F | VERIFIED | `test_set_application_version_in_run_gui` added; asserts byte-ordering + importlib usage. |
| `.planning/REQUIREMENTS.md` | VER-02 row added; Phase 65 column = `Phase 65` | VERIFIED | Line 48: `**VER-02**: The running app surfaces its current version…`. Line 101: traceability row `\| VER-02 \| Phase 65 \| Pending \|`. (Phase row status will be flipped Pending → Complete by the orchestrator's phase-completion step per the verifier's brief; verifier confirms the row exists.) |
| `.planning/ROADMAP.md` | Phase 65 entry backfilled with Goal/Requirements/SC/Plans | VERIFIED | Lines 509-525: full entry present (Goal, Depends on Phase 63, Requirements: VER-02, 6 Success Criteria, 3-plan listing). Progress table line 489: `\| 65. Show current version in app \| 3/3 \| Complete \| 2026-05-08 \|`. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| Hamburger menu construction | `pyproject.toml [project].version` | `_pkg_version('musicstreamer')` (importlib.metadata) | WIRED | `main_window.py:25,238` — direct import + call site at menu addAction; data flow proven by 56/56 tests + behavioral spot-check returning real `2.1.63`. |
| `_run_gui` Qt setup | `pyproject.toml [project].version` | `_pkg_version("musicstreamer")` → `app.setApplicationVersion(...)` | WIRED | `__main__.py:9,188` — same dynamic read mechanism; locked by `test_set_application_version_in_run_gui`. |
| Windows PyInstaller bundle | musicstreamer dist-info | `copy_metadata("musicstreamer")` in `_ms_datas` concat | WIRED (structural) | `MusicStreamer.spec:17,41,111` — source-text locked by 4 tests. Runtime bundle confirm is the manual UAT VER-02-J. |
| Read site mechanism | dev `.venv` dist-info | `importlib.metadata` machinery | WIRED (LIVE) | `uv run python -c "from importlib.metadata import version; print(version('musicstreamer'))"` returns `2.1.63` matching pyproject.toml. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `self._act_version` (menu footer) | `_pkg_version('musicstreamer')` | `.venv/lib/python3.14/site-packages/musicstreamer-2.1.63.dist-info/` (dev) → bundle dist-info via `copy_metadata` (Windows) | Yes (LIVE: `2.1.63`) | FLOWING — dev path proven by behavioral spot-check; bundle path structurally guaranteed by spec edit, deferred to manual UAT VER-02-J |
| `app.setApplicationVersion(...)` | `_pkg_version("musicstreamer")` | same as above | Yes | FLOWING — same import path as menu footer; locked by `test_set_application_version_in_run_gui` |

### CONTEXT.md Decisions D-01..D-13

| Decision | Implementation in Codebase | Status |
|----------|---------------------------|--------|
| D-01: Disabled QAction at bottom of `self._menu` after Group 3 + after Phase 44 Node-missing block | `main_window.py:232-239` — separator + addAction + setEnabled(False), placed AFTER the conditional Node-missing block (lines 221-230) | VERIFIED |
| D-02: `self._menu.addSeparator()` precedes the new action | `main_window.py:237` — `self._menu.addSeparator()` immediately before the addAction call. Test `test_hamburger_menu_separators` pins separator count at 4 (was 3 pre-Phase-65). | VERIFIED |
| D-03: Constructed via `addAction(label).setEnabled(False)` (or `act.setEnabled(False)` after capture) | `main_window.py:238-239` — `self._act_version = self._menu.addAction(...)` then `self._act_version.setEnabled(False)` (capture-then-disable variant per recommended retention pattern) | VERIFIED |
| D-04: Menubar right-corner widget DECLINED | `grep "setCornerWidget" musicstreamer/ui_qt/main_window.py` → zero hits. Decision honored. | VERIFIED (informational) |
| D-05: Runtime read uses `importlib.metadata.version("musicstreamer")` | `__main__.py:9` + `main_window.py:25`: `from importlib.metadata import version as _pkg_version`. Two read sites — one for Qt slot, one inline at menu construction (per Plan 65-01 deviation noted below). | VERIFIED |
| D-06: `musicstreamer/__version__.py` DELETED | File absent on filesystem; `git ls-files` empty; deletion commit `ee4d1f7`. | VERIFIED |
| D-06a: D-06a grep gate clean (zero importers) | LIVE re-run during this verification: zero hits. Same gate ran clean 4× across the phase (RESEARCH Q5, Plan 65-01 Task 1, Plan 65-03 pre-deletion, Plan 65-03 post-deletion). | VERIFIED |
| D-07: `app.setApplicationVersion(...)` added in `_run_gui` between `setApplicationDisplayName` and `setDesktopFileName` | `__main__.py:185-189`: `QApplication(argv)` → `setApplicationName` → `setApplicationDisplayName` → **`setApplicationVersion`** → `setDesktopFileName`. Exactly as specified. | VERIFIED |
| D-08: PyInstaller spec includes `copy_metadata("musicstreamer")`; NO try/except fallback to placeholder string | `MusicStreamer.spec:17,41,111` — import + `_ms_datas` assignment + concat. Negative regression-lock test `test_spec_has_no_try_except_around_copy_metadata` enforces no try/except wrapper. | VERIFIED |
| D-09: Bundle-aware test guarding regression — option (a) unit test for `importlib.metadata` non-empty SemVer | `tests/test_version.py::test_metadata_version_is_semver_triple` enforces `^\d+\.\d+\.\d+$`. CI-friendly automated test (option a in CONTEXT). | VERIFIED |
| D-10: Label format `v{version}` | `main_window.py:238`: `f"v{_pkg_version('musicstreamer')}"`. Test `test_version_action_is_disabled_and_last` enforces `^v\d+\.\d+\.\d+$`. | VERIFIED |
| D-11: Read via `QCoreApplication.applicationVersion()` (RECOMMENDED) OR direct `importlib.metadata` (DEVIATION ACCEPTED) | DEVIATED per Plan 65-01 SUMMARY — read `importlib.metadata` directly at the menu construction site (not via `QCoreApplication.applicationVersion()`) because pytest-qt `qtbot` fixture provides a bare QApplication and never runs `_run_gui`, so the Qt slot would return "" in tests. Qt slot is still set in `__main__.py` (D-07) for Qt-internal reasons. Deviation explicitly recorded in 65-01-SUMMARY.md "Decisions Made" section and CONTEXT D-11 lists this as a planner-discretion option. The defensive `v(unknown)` fallback was DROPPED per RESEARCH §"On the v(unknown) defensive fallback" + CONTEXT D-08 hard-fail spirit. | VERIFIED (within decision latitude — informational deviation) |
| D-12: Action is disabled (informational footer, no click target) | `main_window.py:239`: `self._act_version.setEnabled(False)`. Test `test_version_action_is_disabled_and_last` enforces `isEnabled() is False`. | VERIFIED |
| D-13: No tooltip beyond Qt's default | `grep -n "setToolTip\|setStatusTip" main_window.py | grep -i version` → zero hits. No tooltip/statustip set on `_act_version`. | VERIFIED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `importlib.metadata.version("musicstreamer")` returns the canonical version | `uv run python -c "from importlib.metadata import version; print(version('musicstreamer'))"` | `2.1.63` (matches `pyproject.toml:7`) | PASS |
| Plan-level pytest suite (the binding gate) is GREEN | `uv run pytest tests/test_version.py tests/test_main_window_integration.py tests/test_main_run_gui_ordering.py tests/test_packaging_spec.py -x` | `56 passed, 1 warning in 1.11s` | PASS |
| D-06a grep gate returns zero importers of `__version__.py` | `git grep -nl "from musicstreamer\.__version__\|musicstreamer/__version__\|__version__\.py\|musicstreamer\.__version__" -- ':!.planning' ':!.claude/worktrees' ':!.venv'` | empty (zero hits) | PASS |
| `__version__.py` is gone from working tree | `ls musicstreamer/__version__.py` | "No such file or directory" | PASS |
| `pyproject.toml [project].version` is unchanged from Phase 63 auto-bump (`2.1.63`) | `grep "^version" pyproject.toml` | `version = "2.1.63"` | PASS |
| `packaging/windows/build.ps1` is unchanged from HEAD | `git diff HEAD -- packaging/windows/build.ps1` | empty (no diff) | PASS |
| PyInstaller spec contains `copy_metadata` references | `grep -c "_ms_datas\|copy_metadata" packaging/windows/MusicStreamer.spec` | `4` (1 import + 1 assignment + 2 concatenations and references) | PASS |

All 7 spot-checks PASS.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| VER-02 | 65-01-PLAN, 65-02-PLAN, 65-03-PLAN | The running app surfaces its current version (read from `pyproject.toml` via `importlib.metadata`) as a disabled informational entry at the bottom of the hamburger menu. The Windows PyInstaller bundle ships `musicstreamer.dist-info` so the bundled exe reads the same version dev sees. | SATISFIED (8/8 automated sub-checks GREEN; 2 manual UAT items pending — VER-02-I + VER-02-J) | All 6 ROADMAP SCs verified above; row exists in REQUIREMENTS.md line 101. Status field "Pending" will flip to "Complete" via orchestrator's phase-completion step. |

No orphaned requirements. REQUIREMENTS.md maps VER-02 to Phase 65 only and Phase 65's three plans all declare `requirements-completed: [VER-02]`.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | (n/a) | (n/a) | (n/a) | No production-code stubs, TODOs, hardcoded empties, or placeholder strings introduced by Phase 65. The two `placeholder` token hits in `MusicStreamer.spec` and `tests/test_packaging_spec.py` are documentation comments referring to CONTEXT D-08's no-placeholder PROHIBITION (i.e., they describe what is forbidden, not what was shipped). |

### Pre-existing Issues Confirmed Not Caused by Phase 65

These are documented in `deferred-items.md` and confirmed pre-existing (reproduce on commit `f033cca`, the parent of all Phase 65 work):

1. `tests/test_import_dialog_qt.py::test_yt_scan_passes_through` — Qt fatal abort during `_YtScanWorker` thread cleanup when run as part of the full suite (passes 25/25 in isolation). Last touched in Phase 999.7. NOT caused by Phase 65.
2. `_FakePlayer` missing `underrun_recovery_started` signal — 18 errors + 16 failures across multiple test files using local `_FakePlayer` stubs that were not updated when Phase 62 added `Player.underrun_recovery_started`. NOT caused by Phase 65.

Plan 65-01 SUMMARY records: with both deselected, full suite runs 1145 passed / 0 failed.

### Human Verification Required

Two items, both already declared in 65-VALIDATION.md as manual-only and explicitly NOT a verifier blocker per the verification asks (item 9). They route to `/gsd-verify-work`:

#### 1. VER-02-I — Linux Wayland visual confirm

**Test:** `uv run python -m musicstreamer`, then click the hamburger menu (≡), and confirm the last entry reads `v{version}` and is greyed out.
**Expected:** A greyed-out `v2.1.63` (or whatever the running build's version is) entry sits at the literal bottom of the hamburger menu.
**Why human:** Visual rendering / disabled-action greyout / final layout cannot be asserted via pytest-qt without screenshot tooling. The disabled state is locked by `isEnabled() is False`, but the visual greyout is theme-dependent.

#### 2. VER-02-J — Win11 VM bundle confirm

**Test:** Run `packaging/windows/build.ps1` on the Win11 VM, install the resulting installer, launch `MusicStreamer.exe`, open the hamburger menu, confirm the last entry reads `v{version}` and matches the dev value.
**Expected:** Same `v{version}` shown in dev — no `PackageNotFoundError` at startup, no missing dist-info, footer renders correctly.
**Why human:** Bundle behavior with `copy_metadata` only validated by running the actual installer-built exe on Windows. Source-text spec test (VER-02-H) is the structural guard, but only a real bundle build can confirm the dist-info ships and `importlib.metadata` resolves inside the bundle.

---

## Gaps Summary

**No gaps.** All 6 ROADMAP Success Criteria are observably met in the codebase. All 8 automated VER-02 sub-checks (A through H) are GREEN. The two manual UAT items (VER-02-I, VER-02-J) are by-design human-verification items declared in the phase plan and are not a verifier blocker — they route to `/gsd-verify-work`. The phase implementation is complete pending those human checks.

The single decision-level deviation (D-11 read-site mechanism — reading `importlib.metadata` directly at the menu construction site instead of via `QCoreApplication.applicationVersion()`) is within the planner-discretion latitude that CONTEXT D-11 explicitly grants and is rigorously documented in 65-01-SUMMARY.md "Decisions Made". The Qt slot is still set in `__main__.py` for Qt-internal reasons (QSettings, crash handlers) — both paths exist; the menu reads the metadata directly to remain test-friendly under pytest-qt fixtures that don't run `_run_gui`.

---

## VERIFICATION COMPLETE — PASS (pending manual UAT)

| Check | Status |
|-------|--------|
| SC-1 (greyed-out v{version} as last menu entry) | VERIFIED |
| SC-2 (importlib.metadata.version equals pyproject.toml [project].version) | VERIFIED |
| SC-3 (app.setApplicationVersion called in _run_gui after QApplication(argv)) | VERIFIED |
| SC-4 (`__version__.py` deleted; D-06a grep gate clean) | VERIFIED |
| SC-5 (PyInstaller spec includes copy_metadata("musicstreamer")) | VERIFIED |
| SC-6 (No drift — pyproject.toml [project].version remains single literal write site) | VERIFIED |
| D-01..D-13 (CONTEXT decisions) | All implemented or honored as informational/declined; D-11 deviation accepted within planner discretion |
| VER-02-A..VER-02-H (automated sub-checks) | 8/8 GREEN |
| VER-02-I (Linux Wayland visual UAT) | PENDING — manual |
| VER-02-J (Win11 VM bundle UAT) | PENDING — manual |

**Status:** `human_needed` — implementation complete, two by-design manual UAT items deferred to `/gsd-verify-work`. The phase goal is achieved in the codebase.

---

*Verified: 2026-05-08T20:00:00Z*
*Verifier: Claude (gsd-verifier)*
