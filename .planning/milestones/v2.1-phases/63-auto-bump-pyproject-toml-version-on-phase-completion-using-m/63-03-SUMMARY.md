---
phase: 63
plan: 03
subsystem: tooling
tags: [version-bump, claude-code-hooks, bash, wave-3]
requires:
  - "tools/bump_version.py from Plans 01+02 (--phase NN, exit codes 0/1/3)"
  - ".planning/config.json::workflow.auto_version_bump (Plan 02 seeded default-true)"
provides:
  - ".claude/settings.json::hooks.PreToolUse[Bash matcher, if: Bash(gsd-sdk query commit *)]"
  - ".claude/hooks/bump-version-hook.sh (stdin JSON → stdout hookSpecificOutput JSON; mode 0755)"
  - "tests/test_bump_version.py::test_hook_files_committed (Pitfall 8 drift-guard)"
  - "tests/test_bump_version.py::test_bump_stages_pyproject (SC #2 mechanism integration)"
affects:
  - ".claude/ (gitignored top-level — both new files force-added; settings.local.json + skills/ + worktrees/ untouched)"
  - "tests/test_bump_version.py (7 → 9 tests; appended only; json/shutil/pytest imports added)"
tech-stack:
  added: []
  patterns:
    - "Claude Code PreToolUse hook with stdin JSON / stdout hookSpecificOutput protocol (RESEARCH §Pattern 2 verbatim)"
    - "jq -r '.tool_input.command' for payload extraction; jq -n --arg for output emission"
    - "grep -oP 'docs\\(phase-\\K[0-9]+(?=\\): complete phase execution)' digit-only phase-number extraction (T-V-INPUT-HOOK mitigation)"
    - "Bash safety idiom: #!/usr/bin/env bash + set -euo pipefail (mirrors scripts/dev-launch.sh)"
    - "git add -f for top-level gitignored .claude/ paths (Pitfall 8 mitigation)"
    - "subprocess.run(input=json_str, env={...CLAUDE_PROJECT_DIR}) for hook integration testing"
    - "shutil.which('jq') skip-gate for portable test execution"
key-files:
  created:
    - ".claude/settings.json (15 LOC — PreToolUse block only; Plan 04 will extend with PostToolUseFailure)"
    - ".claude/hooks/bump-version-hook.sh (49 LOC, mode 0755)"
  modified:
    - "tests/test_bump_version.py (260 → 345 LOC; +85 lines for 2 new tests + 3 new imports)"
decisions:
  - "Per-task atomic commits (executor protocol) required `git add -f` to land in Task 1's commit rather than Task 3's plan-level final commit. End state is identical — both files tracked, Warning 3 grep contract satisfied, Pitfall 8 closed."
  - "Task 3 became verification-only (idempotent re-run of `git add -f`); no new file changes, no commit. The grep contract `git ls-files .claude/settings.json .claude/hooks/bump-version-hook.sh` returns both paths is satisfied as of Task 1's commit fcbfe29."
  - "settings.json deliberately ships ONLY the PreToolUse block (no PostToolUseFailure). Plan 04 will diff against this and add the rollback hook. Keeps the Plan 03 diff reviewable and lets Plan 04's failure-mode review stand alone."
metrics:
  duration: "2m44s"
  completed: "2026-05-08"
  tasks: 3
  files_created: 2
  files_modified: 1
  tests_added: 2
  tests_passing: 9
---

# Phase 63 Plan 03: Hook Wiring Summary

Wired the bump helper into Claude Code's hook system: a `PreToolUse` hook on `Bash` matched by `Bash(gsd-sdk query commit *)` invokes a bash wrapper that runs `tools/bump_version.py` with the extracted phase number and rewrites the upcoming `gsd-sdk query commit` command to append `pyproject.toml` to its `--files` list — landing the bumped version field in the same commit object as the `.planning/*` files (SC #2 mechanism).

## What Shipped

**`.claude/hooks/bump-version-hook.sh`** (49 LOC, mode `0755`, RESEARCH §Pattern 2 verbatim) — bash wrapper that:

- Reads PreToolUse JSON payload from stdin via `PAYLOAD=$(cat)`.
- Extracts the upcoming Bash command via `jq -r '.tool_input.command'`.
- Regex-matches `docs(phase-NN): complete phase execution` to extract NN with `grep -oP 'docs\(phase-\K[0-9]+(?=\): complete phase execution)'`. Non-matches `exit 0` (no JSON output → command passes through unmodified).
- On match: runs `python "${CLAUDE_PROJECT_DIR}/tools/bump_version.py" --phase "$PHASE_NUM"`. On non-zero exit, logs to stderr and `exit 0` (per D-09 — never block the commit on a bump failure).
- On success: stages the bumped pyproject via `git -C "${CLAUDE_PROJECT_DIR}" add pyproject.toml`, then emits the `hookSpecificOutput` JSON via `jq -n` with `permissionDecision: "allow"` + `updatedInput.command` appending `pyproject.toml` to the upcoming command.

**`.claude/settings.json`** (15 LOC, RESEARCH §Pattern 2 verbatim):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "if": "Bash(gsd-sdk query commit *)",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/bump-version-hook.sh",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

**Plan 04 will extend** this file with a `PostToolUseFailure` block for rollback. This plan deliberately ships only the `PreToolUse` block — Plan 04's diff against this file will be the sole rollback addition.

**`tests/test_bump_version.py`** — 2 new tests appended (85 lines, 7 → 9):

| # | Test | Purpose |
|---|------|---------|
| 8 | `test_hook_files_committed` | Pitfall 8 drift-guard — asserts both `.claude/settings.json` and `.claude/hooks/bump-version-hook.sh` exist on disk and the hook script is executable (`os.access(hook, os.X_OK)`). Helpful failure messages list what's actually in `.claude/` and `.claude/hooks/` to make drift triage trivial. |
| 9 | `test_bump_stages_pyproject` | SC #2 MECHANISM integration test — synthesizes a fake_repo under `tmp_path` (with stub `tools/bump_version.py` that exits 0, init+commit so `git add` works), invokes `bash <repo>/.claude/hooks/bump-version-hook.sh` with `CLAUDE_PROJECT_DIR=<fake_repo>` and a synthetic JSON payload (`docs(phase-63): complete phase execution`), and asserts the rewritten command ends with ` pyproject.toml`. Skips gracefully via `shutil.which("jq") is None` on hosts without jq. |

New imports added: `json`, `shutil`, `pytest`. Existing imports (`os`, `re`, `subprocess`, `sys`, `tomllib`, `pathlib.Path`) retained from Plans 01+02.

## Force-Add Form Used (Warning 3 — explicit `-f` step)

The exact shell command that landed the gitignored files in the git index:

```bash
git add -f .claude/settings.json .claude/hooks/bump-version-hook.sh
```

This was run in Task 1 (rather than Task 3 as the plan textually specified) because the per-task atomic-commit protocol required Task 1's `feat` commit to actually land both files. The end state is identical to the plan's intent — both files tracked, Pitfall 8 closed, plan-level final commit doesn't need to re-stage them. Task 3 became verification-only (idempotent re-run of `git add -f` produces no diff and no error).

## `git ls-files` Output (Verbatim — Warning 3 Contract Closed)

```
$ git ls-files .claude/settings.json .claude/hooks/bump-version-hook.sh
.claude/hooks/bump-version-hook.sh
.claude/settings.json

$ git ls-files .claude/settings.json .claude/hooks/bump-version-hook.sh | wc -l
2
```

Both paths tracked. Warning 3 grep-verifiable acceptance criterion satisfied: the contract `git ls-files .claude/settings.json .claude/hooks/bump-version-hook.sh` returns BOTH paths is met as of commit `fcbfe29`.

```
$ git log -1 --name-only --format= fcbfe29
.claude/hooks/bump-version-hook.sh
.claude/settings.json
```

The Task 1 commit object's tree contains BOTH paths — proving index → commit object handoff worked, not just staging.

## Test Count + Status

- **Tests added this plan:** 2 (`test_hook_files_committed`, `test_bump_stages_pyproject`).
- **Tests passing:** 9/9 (5 from Plan 01 + 2 from Plan 02 + 2 new).
- **Runtime:** 1.33s (well under <1s-per-test budget for the whole module ~1.3s).
- **Skips:** 0 on this dev host (`jq` is available at `/usr/bin/jq` 1.8.1). On hosts without `jq`, `test_bump_stages_pyproject` will skip gracefully via the `shutil.which("jq") is None` gate; CI MUST have `jq` to exercise the integration path.
- **No regressions:** the 7 prior tests (5 from Plan 01 + 2 from Plan 02) stay GREEN. The new tests are pure additions — `test_hook_files_committed` is filesystem-only (no subprocess), `test_bump_stages_pyproject` runs the hook script in isolation against a `tmp_path/fake_repo`.

## settings.json Confirmation: PreToolUse Only

```
$ grep -E "PreToolUse|PostToolUseFailure" .claude/settings.json
        "PreToolUse": [
$ grep -c "PostToolUseFailure" .claude/settings.json
0
```

This plan ships ONLY the `PreToolUse` block. Plan 04 will diff against this file and add the `PostToolUseFailure` block for rollback (D-08 / Pitfall 5 — `PostToolUse` cannot observe failure; only `PostToolUseFailure` can).

## Pre-existing Observation: `gsd-sdk query commit` for `.planning/` files

Per RESEARCH §Pitfall 1: `gsd-sdk query commit ... --files .planning/...` fails with exit 1 in this repo because `gsd-sdk`'s commit handler runs `git add <file>` per `--files` entry without `-f`, and top-level `.planning/` is gitignored (line 27). The pre-existing phase-completion commits (e.g. `360aa2d` for Phase 62) succeeded via an alternate path that bypasses the SDK's `git add` step (likely manual `git add -f` + `git commit`).

This is a **pre-existing project condition** that predates Phase 63 and is **OUT OF SCOPE** per planner constraints — Phase 63 does not introduce it and does not fix it. The bump's `git -C "${CLAUDE_PROJECT_DIR}" add pyproject.toml` step inside the hook is **independent** of this issue: `pyproject.toml` is NOT gitignored, so `git add pyproject.toml` always succeeds without `-f`. Whether the wrapping `gsd-sdk query commit` itself succeeds is orthogonal — the bumped pyproject lands in the staging area regardless, and whatever path actually creates the commit object will pick it up.

Documented as non-blocking observation per the plan's explicit guidance: *"Do NOT plan a task to fix this; documented as non-blocking observation per planner constraints."*

## SC #2 Verification Split

Per the plan's design:

- **THIS plan (Task 2)** verifies SC #2's **MECHANISM** — `test_bump_stages_pyproject` proves the hook script appends `pyproject.toml` to the upcoming `gsd-sdk query commit` command, given a synthetic PreToolUse payload. This is the synthetic `fake_repo` integration test against the hook in isolation.
- **Plan 05's final task** will verify SC #2's **OUTCOME** — a `git log`-based gate that fires on the live Phase 63 self-completion commit, proving the bump actually landed in the same commit object as the `.planning/*` files (Warning 4 Option A). That gate cannot run today (the commit doesn't exist yet) and is intentionally Plan 05's job.

## Threat Model Mitigation Evidence

| Threat ID | Mitigation Evidence |
|-----------|---------------------|
| T-V-INPUT-HOOK | `grep -oP 'docs\(phase-\K[0-9]+(?=\): complete phase execution)'` at line 18 of the hook — only digits can match the `[0-9]+` capture. Helper's argparse `type=int` is the second guard. |
| T-V-STAGE | `git -C "${CLAUDE_PROJECT_DIR}" add pyproject.toml` at line 33 of the hook — pinned to single literal path; no glob, no `-A`, no recursive add. |
| T-V-FORCE-ADD | `git add -f .claude/settings.json .claude/hooks/bump-version-hook.sh` — TWO literal paths only; no glob, no `-f .`. The `git ls-files` grep contract verifies the exact-two-paths outcome. |
| T-V-TIMEOUT | `"timeout": 30` declared in `.claude/settings.json` line 11. Bump completes in <500ms in practice; the 30s ceiling is a safety valve, not the operating budget. |

## Deviations from Plan

**One procedural shift, no functional deviation:** Task 3 was specified as a separate `git add -f` staging step preceding the plan-level final commit. The executor's per-task atomic-commit protocol required Task 1's `feat` commit to actually land the new files, so the `git add -f` was performed inline before Task 1's commit (instead of in a standalone Task 3 commit). Task 3 became verification-only — idempotent re-run of `git add -f` produced no diff and no error. The end state is identical to the plan's intent: both files tracked, Pitfall 8 closed, Warning 3 grep-verifiable contract satisfied as of commit `fcbfe29`. Documented here for transparency; no Rule 1/2/3 auto-fix was needed (this is a procedural sequencing detail, not a behavioral deviation).

**No Rule 1/2/3 auto-fixes were needed during implementation.** The hook script and settings.json are RESEARCH §Pattern 2 verbatim. The two new tests follow the established `_invoke_bump` + `tmp_path` + `monkeypatch` patterns from Plans 01+02.

## Plan 04 Hand-Off Surface

Plan 04 will:

1. Extend `.claude/settings.json` with a `PostToolUseFailure` block matching `Bash(gsd-sdk query commit *)` that invokes a NEW `bump-rollback-hook.sh`. The PreToolUse block this plan shipped MUST remain unchanged (Plan 04's diff is purely additive).
2. Create `.claude/hooks/bump-rollback-hook.sh` using RESEARCH §Code Example 4 verbatim (single-command rollback `git -C "$CLAUDE_PROJECT_DIR" checkout HEAD -- pyproject.toml`, NOT D-08's literal `git checkout -- pyproject.toml` per Pitfall 4).
3. Force-add the new rollback hook via the same `git add -f` mechanism (single new path; the existing two paths remain tracked and don't need re-adding).
4. Add a rollback integration test (likely simulating a `git commit` failure with the bump staged, asserting `pyproject.toml` reverts to HEAD).

The contract Plan 04 will rely on:

- The PreToolUse hook stages `pyproject.toml` (line 33 of `bump-version-hook.sh`); on a failed commit, it stays in the index. The rollback hook MUST `git checkout HEAD -- pyproject.toml` (not `git checkout --`) to fully revert both index and working tree.
- The hook script's stdout/stderr/exit-code contract is locked: stdout = hookSpecificOutput JSON or empty, stderr = warnings, exit 0 = success, exit non-zero = blocking error. Plan 04's rollback hook should follow the same contract.

## Commits

- `fcbfe29` — `feat(63-03): add Claude Code PreToolUse hook for auto-version-bump` (Task 1; force-adds both .claude/ files)
- `95740ca` — `test(63-03): add hook drift-guard + JSON-output integration tests` (Task 2; 2 new tests, 7 → 9 GREEN)
- (Task 3: verification-only, no commit — see Deviations section above)

## Self-Check: PASSED

- `.claude/settings.json` exists (15 LOC) — confirmed via `test -f .claude/settings.json`.
- `.claude/hooks/bump-version-hook.sh` exists (49 LOC) and is executable (mode 0755) — confirmed via `test -x .claude/hooks/bump-version-hook.sh`.
- `bash -n .claude/hooks/bump-version-hook.sh` exits 0 (syntax-clean) — confirmed.
- `python3 -m json.tool .claude/settings.json` exits 0 — confirmed.
- Hook script body matches RESEARCH §Pattern 2 verbatim (regex, jq usage, hookSpecificOutput emission shape) — verified by direct comparison.
- `settings.json` has the PreToolUse block; does NOT have a PostToolUseFailure block (Plan 04's job) — verified via `grep -c "PostToolUseFailure" .claude/settings.json` returning 0.
- 9 tests in `tests/test_bump_version.py` are GREEN — confirmed via `uv run --with pytest pytest tests/test_bump_version.py` (1.33s, 9 passed, 1 warning).
- No regression on the 7 prior tests — verified by full module run staying GREEN.
- `pyproject.toml` is byte-identical pre/post plan execution — confirmed via `git diff pyproject.toml` returning empty.
- Both `.claude/settings.json` AND `.claude/hooks/bump-version-hook.sh` are tracked in git via `git add -f` — confirmed via `git ls-files .claude/settings.json .claude/hooks/bump-version-hook.sh` returning BOTH paths (Warning 3 / Pitfall 1+8 contract closed).
- After Task 1's commit (`fcbfe29`): `git log -1 --name-only --format= fcbfe29` shows BOTH paths — proves index → commit object handoff worked.
- Commit `fcbfe29` (feat) on `main` — confirmed via `git log --oneline | grep fcbfe29`.
- Commit `95740ca` (test) on `main` — confirmed via `git log --oneline | grep 95740ca`.
