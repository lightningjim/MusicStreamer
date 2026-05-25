---
phase: 63
slug: auto-bump-pyproject-toml-version-on-phase-completion-using-m
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-08
---

# Phase 63 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9+ (already declared in `pyproject.toml` `[project.optional-dependencies].test`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (lines 50–54) |
| **Quick run command** | `uv run --with pytest pytest tests/test_bump_version.py -x` |
| **Full suite command** | `uv run --with pytest pytest tests/ -x` |
| **Estimated runtime** | ~1 s for the bump-version module; ~30–60 s for the full suite |

---

## Sampling Rate

- **After every task commit:** Run `uv run --with pytest pytest tests/test_bump_version.py -x`
- **After every plan wave:** Run `uv run --with pytest pytest tests/ -x`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~1 s (per-task), ~60 s (full suite)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 63-01-W0 | 01 | 0 | VER-01 | — | N/A — Wave 0 stub | unit | `pytest tests/test_bump_version.py -x --collect-only` | ❌ W0 | ⬜ pending |
| 63-01-01 | 01 | 1 | VER-01 (SC #1) | T-V-INPUT | `--phase` arg validated as non-negative int before any file read | unit | `pytest tests/test_bump_version.py::test_bump_rewrites_version_within_project_block -x` | ❌ W0 | ⬜ pending |
| 63-01-02 | 01 | 1 | VER-01 (SC #1) | T-V-PARSE | `[project]` table block scoped — `[tool.X]` version untouched | unit | `pytest tests/test_bump_version.py::test_bump_does_not_touch_other_tables -x` | ❌ W0 | ⬜ pending |
| 63-01-03 | 01 | 1 | VER-01 (D-07) | T-V-PARSE | Malformed pyproject (no `[project]` table) → exit non-zero, no write | unit | `pytest tests/test_bump_version.py::test_bump_aborts_when_no_project_table -x` | ❌ W0 | ⬜ pending |
| 63-01-04 | 01 | 1 | VER-01 (D-04/D-09) | T-V-PARSE | Unparseable PROJECT.md milestone → exit non-zero, no write | unit | `pytest tests/test_bump_version.py::test_bump_aborts_when_no_milestone_heading -x` | ❌ W0 | ⬜ pending |
| 63-01-05 | 01 | 1 | VER-01 (drift) | — | PROJECT.md milestone heading regex matches the live file | static | `pytest tests/test_bump_version.py::test_project_md_milestone_heading_present -x` | ❌ W0 | ⬜ pending |
| 63-02-01 | 02 | 2 | VER-01 (SC #3) | T-V-CONFIG | `workflow.auto_version_bump=false` → no file change | unit | `pytest tests/test_bump_version.py::test_bump_skipped_when_flag_disabled -x` | ❌ W0 | ⬜ pending |
| 63-02-02 | 02 | 2 | VER-01 (SC #3) | T-V-CONFIG | Missing flag (key not found) → bump fires (default-true) | unit | `pytest tests/test_bump_version.py::test_bump_runs_when_flag_unset -x` | ❌ W0 | ⬜ pending |
| 63-03-01 | 03 | 3 | VER-01 (SC #2) | T-V-STAGE | Hook stages `pyproject.toml` so the bump lands in the same commit | integration | `pytest tests/test_bump_version.py::test_bump_stages_pyproject -x` | ❌ W0 | ⬜ pending |
| 63-03-02 | 03 | 3 | VER-01 (drift) | — | `.claude/settings.json` and the hook script exist + are committed | static | `pytest tests/test_bump_version.py::test_hook_files_committed -x` | ❌ W0 | ⬜ pending |
| 63-04-01 | 04 | 3 | VER-01 (SC #5) | T-V-ROLLBACK | Failed commit → `git checkout HEAD -- pyproject.toml` reverts cleanly | integration | `pytest tests/test_bump_version.py::test_rollback_on_simulated_commit_failure -x` | ❌ W0 | ⬜ pending |
| 63-05-01 | 05 | 3 | VER-01 (SC #4) | — | `PROJECT.md` contains a `## Versioning` section with worked example | static | `pytest tests/test_bump_version.py::test_project_md_has_versioning_section -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_bump_version.py` — pytest module with stubs for every row above; runs the helper end-to-end via `subprocess.run`
- [ ] `tools/bump_version.py` (skeleton with `--phase`, `--pyproject`, `--project-md`, `--check`, `--dry-run` argv shape) so the test module can collect imports without `ModuleNotFoundError`
- [ ] No `conftest.py` extension needed — helper is pure-Python and tests use `tmp_path`

*Existing infrastructure: pytest 9+ is already declared in `pyproject.toml`'s `[project.optional-dependencies].test` block (line 27). No framework install required.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| End-to-end live phase-complete commit on Phase 63 itself bumps `pyproject.toml` to `2.1.63` and lands in the same commit | VER-01 (SC #1, #2) | The full pipeline only triggers when `gsd-sdk query phase.complete 63` runs at real phase closure — cannot be exercised inside a unit test without simulating the full GSD workflow. | At phase-close time, run `/gsd-execute-phase 63` to completion; observe that the resulting `docs(phase-63): complete phase execution` commit contains `pyproject.toml` and the version line is `2.1.63`. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s (full suite)
- [ ] `nyquist_compliant: true` set in frontmatter (after Wave 0 lands)

**Approval:** pending
