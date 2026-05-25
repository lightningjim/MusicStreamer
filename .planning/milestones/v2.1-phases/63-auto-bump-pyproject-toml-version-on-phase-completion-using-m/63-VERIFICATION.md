---
phase: 63-auto-bump-pyproject-toml-version-on-phase-completion-using-m
verified: 2026-05-08T00:00:00Z
status: passed
score: 5/5 success criteria verified
overrides_applied: 0
---

# Phase 63: Auto-Bump pyproject Version on Phase Completion — Verification Report

**Phase Goal:** Adopt the `milestone.minor.phase` versioning scheme (e.g. `2.1.50` after Phase 50) and automate it. A hook in `phase.complete` rewrites `pyproject.toml`'s `version` field to `{milestone_major}.{milestone_minor}.{phase_number}` whenever a phase finishes. The scheme is documented in PROJECT.md and gated by a config flag so it can be toggled per-project.

**Verified:** 2026-05-08
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Success Criterion | Status | Evidence |
|---|-------------------|--------|----------|
| 1 | Completing any v2.1 phase rewrites `pyproject.toml` `version` to `2.1.{phase_number}` without manual edits | VERIFIED | `tools/bump_version.py` (175 LOC) implements rewrite via `_VERSION_LINE_RE` regex scoped to `[project]` table; live `python tools/bump_version.py --phase 0 --dry-run` prints `[bump] would rewrite ... version to 2.1.0`; PreToolUse hook in `.claude/settings.json` invokes the helper on `gsd-sdk query commit "docs(phase-NN): complete phase execution"`. Working tree shows `pyproject.toml` already at `version = "2.1.63"` from prior hook activity. |
| 2 | Bump committed alongside phase-completion commit — no orphaned uncommitted state | VERIFIED (mechanism) + GATED (outcome) | **Mechanism:** `tests/test_bump_version.py::test_bump_stages_pyproject` GREEN — proves hook script appends `pyproject.toml` to `--files` list using fake_repo synthetic JSON payload. **Outcome gate:** `test_phase_63_self_completion_bundles_pyproject_with_planning` is correctly SKIPPED pre-self-completion (the Phase 63 commit has not yet landed); the gate fires on the next test run after `phase.complete` creates the commit. The hook script also calls `git -C "${CLAUDE_PROJECT_DIR}" add pyproject.toml` (line 33) so the bumped file enters the index. |
| 3 | Config flag `workflow.auto_version_bump` (default `true`) lets user opt out | VERIFIED | `.planning/config.json` line 14 contains `"auto_version_bump": true`. `gsd-sdk query config-get workflow.auto_version_bump --raw` returns `true` exit 0 (live verified). `tools/bump_version.py::is_auto_bump_enabled()` (lines 66-82) reads the flag via `gsd-sdk` subprocess; `main()` line 112-114 short-circuits with `return 3` and stderr `[bump] disabled via workflow.auto_version_bump` when flag is false. Tests `test_bump_skipped_when_flag_disabled` (returncode 3, no write) and `test_bump_runs_when_flag_unset` (default-true on `Error: Key not found:` from gsd-sdk exit 1) both GREEN. |
| 4 | Convention documented in PROJECT.md with schema + worked example | VERIFIED | `.planning/PROJECT.md` line 223 has `## Versioning` H2 heading immediately above `## Constraints` (line 229; ordering `awk` check passes). Section contains all 5 anchor strings: `tools/bump_version.py`, `workflow.auto_version_bump`, `2.1.50`, `2.1.63`, and the schema prose `{major}.{minor}.{phase}`. Drift-guard `test_project_md_has_versioning_section` GREEN against the live file. |
| 5 | Rollback safety — if phase-completion commit fails, version bump reverted from working tree | VERIFIED | `.claude/hooks/bump-rollback-hook.sh` (executable, mode 0755) wired via `PostToolUseFailure` block in `.claude/settings.json` (lines 16-28) with same `Bash(gsd-sdk query commit *)` matcher. Rollback uses the **corrected single-command form** `git -C "${CLAUDE_PROJECT_DIR}" checkout HEAD -- pyproject.toml` (line 28) — NOT the bare D-08-literal form which RESEARCH §Pitfall 4 proved is a no-op against staged changes. Negative grep `grep -vE '^\s*#' .claude/hooks/bump-rollback-hook.sh \| grep -E 'git[^|]*checkout\s+--\s+pyproject\.toml' \| grep -vE 'HEAD'` returns zero non-comment matches. Integration test `test_rollback_on_simulated_commit_failure` GREEN — proves both index and working-tree reversion AND the no-match pass-through. |

**Score:** 5/5 ROADMAP success criteria verified.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tools/bump_version.py` | Bump CLI helper (175 LOC, ≥80 expected) | VERIFIED | argparse `--phase --pyproject --project-md --dry-run --check`, regex constants `_PROJECT_TABLE_RE / _NEXT_TABLE_RE / _VERSION_LINE_RE / _MILESTONE_RE`, `parse_milestone() / rewrite_pyproject_version() / is_auto_bump_enabled() / main()`, exit codes 0/1/3 documented in module docstring. UTF-8 encoding declared on every read/write. |
| `tests/test_bump_version.py` | Test suite ≥280 LOC | VERIFIED | 644 LOC; 12 test functions defined: 5 from Plan 01 + 2 from Plan 02 + 2 from Plan 03 + 1 from Plan 04 + 2 from Plan 05. |
| `.planning/config.json` | `workflow.auto_version_bump: true` flag | VERIFIED | Line 14: `"auto_version_bump": true`. JSON valid (`python3 -m json.tool` passes). All 6 prior workflow keys preserved. |
| `.claude/settings.json` | PreToolUse + PostToolUseFailure hook registrations | VERIFIED | 30 LOC. Both blocks present, both use same `"matcher": "Bash"` + `"if": "Bash(gsd-sdk query commit *)"` glob. PreToolUse `timeout: 30`, PostToolUseFailure `timeout: 10`. |
| `.claude/hooks/bump-version-hook.sh` | PreToolUse bump hook | VERIFIED | 46 LOC, mode 0755, `#!/usr/bin/env bash` + `set -euo pipefail`. Reads PreToolUse JSON via `jq`, regex-extracts phase number from `docs(phase-NN): complete phase execution`, invokes `tools/bump_version.py --phase NN`, runs `git add pyproject.toml`, emits `hookSpecificOutput` JSON appending `pyproject.toml` to the upcoming command. |
| `.claude/hooks/bump-rollback-hook.sh` | PostToolUseFailure rollback hook | VERIFIED | 30 LOC, mode 0755, `#!/usr/bin/env bash` + `set -euo pipefail`. Reads PostToolUseFailure JSON, gates on `docs(phase-[0-9]+): complete phase execution` regex, runs `git -C "${CLAUDE_PROJECT_DIR}" checkout HEAD -- pyproject.toml \|\| true`, logs to stderr, exits 0. |
| `.planning/PROJECT.md` | `## Versioning` section | VERIFIED | Pure additive insert (6 lines) at line 223, immediately above `## Constraints` (line 229). Contains all 5 anchor strings + worked example. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `tools/bump_version.py::main` | `rewrite_pyproject_version()` | section-aware regex rewrite (`_PROJECT_TABLE_RE`/`_VERSION_LINE_RE`) | WIRED | line 154; preserves comments and key ordering by per-section `subn`. |
| `tools/bump_version.py::main` | `parse_milestone()` | `_MILESTONE_RE` against PROJECT.md text | WIRED | line 134. |
| `tools/bump_version.py::main` | `is_auto_bump_enabled()` | `subprocess.run(["gsd-sdk", "query", "config-get", "workflow.auto_version_bump", "--raw"])` | WIRED | line 112; `cwd=repo_root`, default-true on non-zero exit. |
| `.claude/settings.json` | `.claude/hooks/bump-version-hook.sh` | PreToolUse `command` field | WIRED | line 10; matcher `Bash(gsd-sdk query commit *)`. |
| `.claude/settings.json` | `.claude/hooks/bump-rollback-hook.sh` | PostToolUseFailure `command` field | WIRED | line 23; same matcher. |
| `.claude/hooks/bump-version-hook.sh` | `tools/bump_version.py` | `python "${CLAUDE_PROJECT_DIR}/tools/bump_version.py" --phase "$PHASE_NUM"` | WIRED | line 24. |
| `.claude/hooks/bump-version-hook.sh` | Claude Code agent | stdout `hookSpecificOutput` JSON via `jq -n` | WIRED | lines 39-46. |
| `.claude/hooks/bump-rollback-hook.sh` | `pyproject.toml` in HEAD | `git -C "${CLAUDE_PROJECT_DIR}" checkout HEAD -- pyproject.toml` | WIRED (corrected form) | line 28; **NOT** the bare D-08-literal form. |
| git index | `.claude/settings.json` + `.claude/hooks/bump-{version,rollback}-hook.sh` | `git add -f` (Plans 03 + 04) | WIRED | `git ls-files .claude/settings.json .claude/hooks/bump-version-hook.sh .claude/hooks/bump-rollback-hook.sh` returns all three paths. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Dry-run helper invocation | `python tools/bump_version.py --phase 0 --dry-run` | `[bump] would rewrite /home/kcreasey/.../pyproject.toml version to 2.1.0` exit 0 | PASS |
| Negative phase rejected | `python tools/bump_version.py --phase -1 --dry-run` | `[bump] FAIL: --phase must be >= 0, got -1` exit 1 | PASS |
| Config flag readable via SDK | `gsd-sdk query config-get workflow.auto_version_bump --raw` | `true` exit 0 | PASS |
| Hook script syntax-valid | `bash -n .claude/hooks/bump-version-hook.sh` | exit 0 | PASS |
| Rollback script syntax-valid | `bash -n .claude/hooks/bump-rollback-hook.sh` | exit 0 | PASS |
| settings.json valid JSON | `python3 -m json.tool .claude/settings.json` | exit 0 | PASS |
| config.json valid JSON | `python3 -m json.tool .planning/config.json` | exit 0 | PASS |
| Test suite | `uv run --with pytest pytest tests/test_bump_version.py` | 11 passed, 1 skipped, 1.39s | PASS |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|---------------|-------------|--------|----------|
| VER-01 | 63-01, 63-02, 63-03, 63-04, 63-05 | Adopt `milestone_major.milestone_minor.phase` versioning. Auto-bump via GSD-workflow hook gated by config flag and documented in PROJECT.md | SATISFIED | All 5 SC delivered; `.planning/REQUIREMENTS.md` line 99 already shows `\| VER-01 \| Phase 63 \| Complete \|`. The bump helper, hook, rollback, config flag, and PROJECT.md docs are all in place. |

No orphaned requirements: REQUIREMENTS.md maps VER-01 to Phase 63 exclusively, and all 5 plans declare `requirements: [VER-01]` in their frontmatter.

### Anti-Patterns Found

None. Scanned `tools/bump_version.py`, `tests/test_bump_version.py`, `.claude/settings.json`, `.claude/hooks/bump-version-hook.sh`, `.claude/hooks/bump-rollback-hook.sh` for `TODO|FIXME|XXX|HACK|PLACEHOLDER|placeholder|coming soon|not yet implemented` — zero matches. Negative grep for the bare `git checkout -- pyproject.toml` form in executable code returned zero matches (only present in comments documenting it as the broken D-08 literal that Pitfall 4 fixed).

### Re-Verification / Gap-Closure

Initial verification — no prior VERIFICATION.md exists.

### SC #2 Verification Architecture (Two-Layer)

SC #2 ("bump committed alongside phase-completion commit — no orphaned uncommitted state") is verified by **two complementary layers** (Warning 4 Option A, documented in 63-03-SUMMARY.md and 63-05-SUMMARY.md):

1. **Mechanism layer** — `test_bump_stages_pyproject` (Plan 03) — synthetic `fake_repo` integration test proves the PreToolUse hook script appends `pyproject.toml` to the upcoming command's `--files` list AND runs `git add pyproject.toml`. **Currently GREEN.**
2. **Outcome layer** — `test_phase_63_self_completion_bundles_pyproject_with_planning` (Plan 05) — gated `git log --grep` test that fires AFTER `docs(phase-63): complete phase execution` lands in the repo's commit history. Asserts `pyproject.toml` AND at least one `.planning/` path co-occur in the same commit object AND the version is `"2.1.63"`. **Currently SKIPPED — and the prompt confirms this is the correct, expected pre-self-completion state.** The gate becomes a permanent regression net for all future phases once Phase 63 self-completes.

The skip is mechanically verified: `git log --grep='^docs(phase-63): complete phase execution' -1 --format=%H` returns empty stdout in the current repo state (no such commit yet), which triggers `pytest.skip(...)` per the gate's `if not commit_hash: pytest.skip(...)` branch.

### Gaps Summary

None. All five ROADMAP success criteria are satisfied by tangible artifacts in the codebase, all key links are wired, the test suite passes (11 passed + 1 correctly skipped), and the documentation is in place. The phase is ready for `phase.complete` to issue the canonical commit, which will simultaneously:

- Fire the PreToolUse hook → bump `pyproject.toml` (already at `2.1.63` in the working tree) → `git add pyproject.toml` → land it in the same commit object as `.planning/*` files (closing SC #2 outcome gate)
- Flip `test_phase_63_self_completion_bundles_pyproject_with_planning` from SKIP to GREEN on the next test run

### Self-Completion Trigger State

| Indicator | State | Notes |
|-----------|-------|-------|
| `pyproject.toml` working-tree version | `2.1.63` | Matches the expected post-bump value for Phase 63 of v2.1 (already modified from prior session hook activity per 63-05-SUMMARY.md §"Dirty Working-Tree State"). |
| `pyproject.toml` git status | `M pyproject.toml` (also `M uv.lock`) | Deliberately left dirty by Plan 05 so `phase.complete` can land the bump in the same commit object as `.planning/*` files. |
| Phase 63 self-completion commit | NOT YET CREATED | The hook + outcome gate are designed for this exact next step. The verifier is correctly running PRIOR to that commit. |

---

_Verified: 2026-05-08_
_Verifier: Claude (gsd-verifier)_
