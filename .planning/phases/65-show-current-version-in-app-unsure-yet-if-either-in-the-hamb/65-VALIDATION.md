---
phase: 65
slug: show-current-version-in-app
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-08
---

# Phase 65 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest>=9 + pytest-qt>=4 (already in `pyproject.toml [project.optional-dependencies].test`) |
| **Config file** | `pyproject.toml [tool.pytest.ini_options]` (line 50-54) |
| **Quick run command** | `uv run pytest tests/test_version.py tests/test_main_window_integration.py tests/test_main_run_gui_ordering.py -x` |
| **Full suite command** | `uv run pytest -x` |
| **Estimated runtime** | ~5–10 seconds (quick) / ~30–60 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_version.py tests/test_main_window_integration.py tests/test_main_run_gui_ordering.py -x`
- **After every plan wave:** Run `uv run pytest -x`
- **Before `/gsd-verify-work`:** Full suite must be green AND manual UAT items VER-02-I and VER-02-J both confirmed
- **Max feedback latency:** ~10 seconds (quick run)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| VER-02-A | TBD | TBD | VER-02 | — | `importlib.metadata.version("musicstreamer")` returns the same string as `pyproject.toml [project].version` | unit | `uv run pytest tests/test_version.py::test_metadata_version_matches_pyproject -x` | ❌ W0 | ⬜ pending |
| VER-02-B | TBD | TBD | VER-02 | — | Returned version string is M.m.p triple of integers | unit | `uv run pytest tests/test_version.py::test_metadata_version_is_semver_triple -x` | ❌ W0 | ⬜ pending |
| VER-02-C | TBD | TBD | VER-02 | — | Hamburger menu's last non-separator entry text matches `^v\d+\.\d+\.\d+$` | unit (pytest-qt) | `uv run pytest tests/test_main_window_integration.py::test_version_action_is_disabled_and_last -x` | ❌ W0 (extend) | ⬜ pending |
| VER-02-D | TBD | TBD | VER-02 | — | The version action returns `isEnabled() is False` | unit (pytest-qt) | `uv run pytest tests/test_main_window_integration.py::test_version_action_is_disabled_and_last -x` | ❌ W0 (extend) | ⬜ pending |
| VER-02-E | TBD | TBD | VER-02 | — | Hamburger menu has the expected separator count (was 3, now 4 with the new pre-version separator) | unit (pytest-qt) | `uv run pytest tests/test_main_window_integration.py::test_hamburger_menu_separators -x` | ✅ exists, count update | ⬜ pending |
| VER-02-F | TBD | TBD | VER-02 | — | `app.setApplicationVersion(...)` is invoked in `_run_gui` after `QApplication(argv)` | unit (source-text) | `uv run pytest tests/test_main_run_gui_ordering.py::test_set_application_version_in_run_gui -x` | ✅ exists, extend | ⬜ pending |
| VER-02-G | TBD | TBD | VER-02 | — | `__version__.py` deleted; zero remaining importers of `musicstreamer.__version__` outside ignored paths | shell (grep gate) | `! git grep -l "from musicstreamer\.__version__\|musicstreamer/__version__\|__version__\.py\|musicstreamer\.__version__" -- ':!.planning' ':!.claude/worktrees' ':!.venv'` | N/A — shell | ⬜ pending |
| VER-02-H | TBD | TBD | VER-02 | — | PyInstaller spec includes a `copy_metadata("musicstreamer")` reference | unit (source-text) | `uv run pytest tests/test_pkg03_compliance.py::test_spec_includes_copy_metadata_for_musicstreamer -x` *(new function — file path planner's choice)* | ❓ planner picks | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_version.py` — NEW file (~30 lines), covers VER-02-A and VER-02-B
- [ ] `tests/test_main_window_integration.py` — extend the `EXPECTED_ACTION_TEXTS` constant; update `test_hamburger_menu_separators` from count=3 → count=4; add `test_version_action_is_disabled_and_last` (VER-02-C, VER-02-D, VER-02-E)
- [ ] `tests/test_main_run_gui_ordering.py` — add `test_set_application_version_in_run_gui` (VER-02-F)
- [ ] `tests/test_pkg03_compliance.py` (or new `tests/test_packaging_spec.py` — planner picks) — add `test_spec_includes_copy_metadata_for_musicstreamer` (VER-02-H)
- [ ] No new framework install — `pytest>=9` and `pytest-qt>=4` already in `[project.optional-dependencies].test`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Kyle visually sees `v2.1.63` (or current bumped value) at the bottom of the hamburger menu when launching the dev app | VER-02-I | Visual rendering / disabled-action greyout / final layout cannot be asserted via pytest-qt without screenshot tooling | `uv run python -m musicstreamer` then open the hamburger menu (≡) and confirm the last entry reads `v{version}` and is greyed out |
| The Windows-bundled exe shows the same `v{version}` in its hamburger menu | VER-02-J | Bundle behavior with `copy_metadata` only validated by running the actual installer-built exe | Build via `packaging/windows/build.ps1`, install on the Win11 VM, launch, open the hamburger menu, confirm `v{version}` matches the dev value |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (`tests/test_version.py`, extensions to `test_main_window_integration.py` / `test_main_run_gui_ordering.py`, new `test_spec_includes_copy_metadata_for_musicstreamer` test)
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s (quick run estimated 5–10s)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
