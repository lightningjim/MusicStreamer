---
phase: 63
plan: 04
subsystem: tooling
tags: [version-bump, rollback, post-tool-use-failure, claude-code-hooks, wave-3]
requires:
  - ".claude/settings.json::hooks.PreToolUse from Plan 03 (PreToolUse block byte-preserved)"
  - ".claude/hooks/bump-version-hook.sh from Plan 03 (sibling pattern reference for shell idiom)"
  - "tests/test_bump_version.py from Plans 01-03 (9 tests; this plan APPENDS the 10th)"
provides:
  - ".claude/settings.json::hooks.PostToolUseFailure[Bash matcher, if: Bash(gsd-sdk query commit *)]"
  - ".claude/hooks/bump-rollback-hook.sh (stdin JSON → git checkout HEAD; mode 0755; single-command rollback form)"
  - "tests/test_bump_version.py::test_rollback_on_simulated_commit_failure (VALIDATION row 63-04-01, SC #5 closure)"
affects:
  - ".claude/settings.json (extended in place — PreToolUse block byte-preserved; only diff is trailing comma + new sibling key)"
  - "tests/test_bump_version.py (9 → 10 tests; appended only; no imports added — json/os/shutil/subprocess/Path/pytest already imported by Plan 03)"
tech-stack:
  added: []
  patterns:
    - "Claude Code PostToolUseFailure hook (RESEARCH §Code Example 4 verbatim — fires only on Bash tool failure, NOT on PostToolUse success per Pitfall 5)"
    - "Single-command rollback `git -C \"${CLAUDE_PROJECT_DIR}\" checkout HEAD -- pyproject.toml` (RESEARCH §Pitfall 4 — reverts BOTH index AND working tree; replaces D-08's bare-form which was a no-op against staged changes)"
    - "Regex gate `docs\\(phase-[0-9]+\\): complete phase execution` so the rollback fires ONLY on phase-completion commit failures (not every Bash failure)"
    - "Passive pass-through with `exit 0` on no-match (mirrors bump-version-hook.sh) — never escalates rollback errors over the original commit failure"
    - "Single integration test exercising BOTH happy-path rollback AND no-match pass-through (amortizes ~200ms fake-repo setup; clear stderr-marker assertions distinguish the two phases)"
key-files:
  created:
    - ".claude/hooks/bump-rollback-hook.sh (28 LOC, mode 0755)"
  modified:
    - ".claude/settings.json (17 → 30 LOC; PreToolUse block byte-preserved, only diff is trailing comma + new PostToolUseFailure sibling key)"
    - "tests/test_bump_version.py (346 → 505 LOC; +159 lines for 1 new test; no new imports needed)"
decisions:
  - "63-04: Used `git checkout HEAD -- pyproject.toml` (RESEARCH §Pitfall 4 corrected form) instead of D-08's literal `git checkout -- pyproject.toml`. D-08's intent (rollback to pre-bump state) is HONORED; the mechanism was corrected because the bare form is a live-verified no-op against staged changes (which is the only scenario this hook fires in). This is a mechanical correction the planner caught, not a scope deviation."
  - "63-04: Negative-grep gate (executable lines only) bans the bare form to prevent regression. Only the docstring/comment on line 7 mentions the bare form (intentionally, as documentation of what we don't use)."
  - "63-04: PostToolUseFailure timeout=10 (vs. PreToolUse's 30) — rollback is a single `git checkout` and completes in <100ms; the lower budget surfaces anomalies faster."
  - "63-04: Integration test combines happy-path AND no-match pass-through in one `def` to amortize the ~200ms fake-repo setup. The two `assert \"reverted\" in stderr` / `assert \"reverted\" not in stderr` lines distinguish the phases in failure messages."
metrics:
  duration: "3m37s"
  completed: "2026-05-08"
  tasks: 2
  files_created: 1
  files_modified: 2
  tests_added: 1
  tests_passing: 10
---

# Phase 63 Plan 04: Rollback Hook (PostToolUseFailure) Summary

Closed SC #5 ("if the phase-completion commit fails, the version bump is reverted from the working tree — no half-state") by adding a `PostToolUseFailure` hook that runs `git checkout HEAD -- pyproject.toml` when a phase-completion `gsd-sdk query commit` fails. This restores BOTH the index and the working tree to HEAD's bytes — the corrected single-command form per RESEARCH §Pitfall 4 (live-verified 2026-05-08 that D-08's literal `git checkout -- pyproject.toml` is a no-op against staged changes, which is the only scenario this hook fires in).

## What Shipped

**`.claude/hooks/bump-rollback-hook.sh`** (28 LOC, mode `0755`, RESEARCH §Code Example 4 verbatim):

- Reads `PostToolUseFailure` JSON payload from stdin via `PAYLOAD=$(cat)`.
- Extracts the failed Bash command via `jq -r '.tool_input.command'`.
- Regex-gates on `docs\(phase-[0-9]+\): complete phase execution` — non-matches `exit 0` silently (passive pass-through, mirrors `bump-version-hook.sh`).
- On match: runs `git -C "${CLAUDE_PROJECT_DIR}" checkout HEAD -- pyproject.toml || true` (the `|| true` ensures a missing pyproject or out-of-repo invocation never raises beyond the hook — the original commit failure is what the user needs to see).
- Logs `[bump-rollback-hook] reverted pyproject.toml to HEAD after phase-commit failure` to stderr so the action is visible in agent transcripts.
- `exit 0` on all paths (PostToolUseFailure is side-effect-only; failures here MUST NOT cascade).

**`.claude/settings.json`** extended with sibling `PostToolUseFailure` block (PreToolUse block byte-preserved):

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
    ],
    "PostToolUseFailure": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "if": "Bash(gsd-sdk query commit *)",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/bump-rollback-hook.sh",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

Both blocks share the same `Bash(gsd-sdk query commit *)` matcher — symmetric registration. The PreToolUse block from Plan 03 is byte-preserved (the only diff is the trailing `]` gaining a comma to admit the new sibling key — `git diff` confirmed verbatim).

**`tests/test_bump_version.py`** — 1 new test appended (159 lines):

| # | Test | Purpose |
|---|------|---------|
| 10 | `test_rollback_on_simulated_commit_failure` | SC #5 / VALIDATION row 63-04-01 — proves rollback restores BOTH index and working tree. Exercises happy-path (`docs(phase-63): complete phase execution` payload reverts staged 9.9.9 → HEAD's 0.0.0) AND no-match pass-through (`fix: unrelated bug` payload is a no-op; staged bump preserved) in one test for setup amortization. |

No new imports needed — `json`, `os`, `shutil`, `subprocess`, `Path`, `pytest` were already imported by Plan 03.

## Force-Add Form Used (Pitfall 8 — explicit `-f` step)

The exact shell command that landed the new gitignored file in the git index:

```bash
git add -f .claude/settings.json .claude/hooks/bump-rollback-hook.sh
```

`.claude/settings.json` was already tracked (force-added by Plan 03), so `-f` is harmless for it; `.claude/hooks/bump-rollback-hook.sh` is brand-new and required `-f` to bypass the `.gitignore:23` exclusion of top-level `.claude/`.

## `git ls-files` Output (Pitfall 8 Contract Closed)

```
$ git ls-files .claude/settings.json .claude/hooks/bump-rollback-hook.sh .claude/hooks/bump-version-hook.sh
.claude/hooks/bump-rollback-hook.sh
.claude/hooks/bump-version-hook.sh
.claude/settings.json
```

All three paths tracked. The new rollback hook joined the index in Task 1's commit `e42721a`; the existing settings + bump hook from Plan 03 stay tracked.

## Rollback Form Confirmation (RESEARCH §Pitfall 4)

The rollback command is the **single-command form** that reverts BOTH index and working tree. Grep evidence:

```
$ grep -c "checkout HEAD" .claude/hooks/bump-rollback-hook.sh
2
$ grep -c "checkout -- pyproject" .claude/hooks/bump-rollback-hook.sh
1     # ← this is ONLY the comment on line 7 documenting what we DON'T use
```

The `2` count includes (a) the comment on line 6 `# (`git checkout HEAD -- pyproject.toml`)` and (b) the executable line 26 `git -C "${CLAUDE_PROJECT_DIR}" checkout HEAD -- pyproject.toml || true`.

The `1` count is the comment on line 7: `# The bare `git checkout -- pyproject.toml` form D-08 specifies is a NO-OP against staged changes` — explicitly documenting why we don't use it.

**The Plan 04 negative-grep gate passes** (executable lines only, with `HEAD` filter):

```
$ grep -vE '^\s*#' .claude/hooks/bump-rollback-hook.sh | grep -E 'git[^|]*checkout\s+--\s+pyproject\.toml($|\s)' | grep -vE 'HEAD' | wc -l
0
```

Zero non-comment matches of the bare form. The contract is closed.

## Live Smoke Verification

Before committing Task 1, ran a self-contained smoke test in `/tmp/smoke-rollback`:

**Phase 1 — phase-completion failure payload:**
- Setup: fake repo, `pyproject.toml` committed at `version = "0.0.0"`, then bumped to `9.9.9` and `git add`'d.
- Pre-rollback: `git diff --cached pyproject.toml` shows `+version = "9.9.9"`.
- Hook fired with `'docs(phase-63): complete phase execution'` payload.
- Post-rollback: BOTH `git diff --cached pyproject.toml` AND `git diff pyproject.toml` are EMPTY; file content reverted to `0.0.0`.
- Stderr: `[bump-rollback-hook] reverted pyproject.toml to HEAD after phase-commit failure` (action logged).

**Phase 2 — no-match payload (negative case):**
- Re-staged the bump.
- Hook fired with `'gsd-sdk query commit "fix: unrelated bug"'` payload (no phase-completion regex match).
- Post-hook: `git diff --cached pyproject.toml` STILL shows the staged bump (regex gate worked — hook did not fire).
- Stderr: empty (no `reverted` log line).

Both phases of the smoke test passed; the test file mechanically exercises the same two phases against `tmp_path/fake_repo`.

## Test Count + Status

- **Tests added this plan:** 1 (`test_rollback_on_simulated_commit_failure`).
- **Tests passing:** 10/10 (5 from Plan 01 + 2 from Plan 02 + 2 from Plan 03 + 1 new).
- **Runtime:** 1.35-1.36s for the whole module (well under the <1s/test budget).
- **Skips:** 0 on this dev host (`jq` is available at `/usr/bin/jq` 1.8.1). On hosts without `jq`, BOTH `test_bump_stages_pyproject` (Plan 03) AND `test_rollback_on_simulated_commit_failure` skip together via `shutil.which("jq") is None`.
- **No regressions:** the 9 prior tests stay GREEN. The new test is a pure addition — uses `tmp_path/fake_repo` isolation; the live `pyproject.toml` is byte-untouched by the test (verified via `git diff pyproject.toml` after the test run was unaffected by the test itself; the staged 2.1.60→2.1.63 working-tree state is pre-existing from earlier hook activity, NOT introduced by Plan 04).

## Threat Model Mitigation Evidence

| Threat ID | Mitigation Evidence |
|-----------|---------------------|
| T-V-ROLLBACK | Line 26 of `bump-rollback-hook.sh`: `git -C "${CLAUDE_PROJECT_DIR}" checkout HEAD -- pyproject.toml || true`. The `HEAD` tree-ish ensures BOTH index and working tree revert atomically — the bare form would leave staged changes (RESEARCH §Pitfall 4 live evidence). Negative-grep gate in test acceptance bans regression to bare form. |
| T-V-ROLLBACK-INPUT | Line 21: `if ! echo "$COMMAND" | grep -qE 'docs\(phase-[0-9]+\): complete phase execution'; then exit 0; fi`. Only the canonical phase-completion shape matches; everything else is a no-op pass-through. Phase 2 of the integration test mechanically proves this. |
| T-V-ROLLBACK-LEAK | Test uses `CLAUDE_PROJECT_DIR=tmp_path/fake_repo`; the `git -C "${CLAUDE_PROJECT_DIR}"` line cannot escape the fake repo. Independent verification: `git diff pyproject.toml` against the real repo post-test-run did NOT show test-induced changes — only the pre-existing 2.1.60→2.1.63 working-tree state from earlier hook activity (which long predates Plan 04 Task 2). |
| T-V-ROLLBACK-CASCADE | Line 26: `\|\| true` after the checkout step ensures rollback errors don't cascade. Final `exit 0` is unconditional. The original tool failure is what the agent surfaces to the user. |

## settings.json Confirmation: Both Blocks Present

```
$ grep -E '"PreToolUse"|"PostToolUseFailure"' .claude/settings.json
    "PreToolUse": [
    "PostToolUseFailure": [
$ grep -c '"timeout"' .claude/settings.json
2
```

Both event registrations live; symmetric matchers (`Bash(gsd-sdk query commit *)` glob); two `timeout` declarations (30s for PreToolUse, 10s for PostToolUseFailure).

## D-08 Honored, Mechanism Corrected (RESEARCH §Pitfall 4)

D-08 in CONTEXT.md specifies the rollback as `git checkout -- pyproject.toml`. RESEARCH §Pitfall 4 LIVE-VERIFIED (2026-05-08) that the bare form is a no-op against staged changes:

```
$ echo "MODIFIED3" > file.txt; git add file.txt
$ git checkout -- file.txt        # D-08 verbatim — NO-OP
$ cat file.txt
MODIFIED3                         # ← still bumped
$ git diff --cached
+MODIFIED3                        # ← still staged
```

Since the bump-version-hook.sh from Plan 03 stages `pyproject.toml` (line 33: `git -C "${CLAUDE_PROJECT_DIR}" add pyproject.toml`), the rollback scenario is precisely the "staged + dirty working tree" case where D-08's literal command is a no-op. Plan 04 honors D-08's INTENT (rollback to pre-bump state on commit failure, no half-state) but uses the corrected mechanism `git checkout HEAD -- pyproject.toml` per Pitfall 4 — single-command form, replaces both index and working tree with HEAD's version (also live-verified in the same RESEARCH session).

**This is NOT scope reduction or scope deviation.** It's a mechanical correction the planner caught and the executor honored.

**Future Claude sessions inheriting this code MUST NOT regress to D-08's literal form.** The negative-grep gate in Plan 04 acceptance criteria is the live tripwire.

## Deviations from Plan

**No Rule 1/2/3 auto-fixes were needed during implementation.** The hook script is RESEARCH §Code Example 4 verbatim. The integration test follows the established `_invoke_bump` + `tmp_path` + `subprocess.run` patterns from Plans 01-03.

**One scope-boundary observation (NOT a deviation, NOT a Rule N fix):**

The repo's `pyproject.toml` was already in working-tree state `version = "2.1.63"` at the start of Plan 04 — the version was rewritten by an earlier `bump-version-hook.sh` PreToolUse fire (likely during Plan 03's commits). This was visible as `M pyproject.toml` in `git status` throughout Plan 04 execution. **It is OUT OF SCOPE for Plan 04** and was deliberately NOT included in either Task 1's or Task 2's commit. The live `pyproject.toml` will land in the actual phase-completion commit (Plan 05 or the eventual `/gsd-execute-phase` close), where the PreToolUse hook will fire and the new PostToolUseFailure hook will provide the rollback safety net being shipped here.

The `uv.lock` modification observed during the test run is a downstream effect of the same pre-existing `pyproject.toml` working-tree state — `uv run` auto-updates lockfile metadata to match `[project].version`. Also out of scope for Plan 04.

## Plan 05 Hand-Off Surface

Plan 05 will:

1. Add the `## Versioning` section to `PROJECT.md` (D-12, SC #4).
2. Add the corresponding drift-guard test (`test_project_md_has_versioning_section`).
3. Run the live phase-completion commit that exercises BOTH the PreToolUse bump hook AND the PostToolUseFailure rollback hook in production.

The contract Plan 05 inherits:
- The PreToolUse hook will rewrite `pyproject.toml` from `2.1.60` (HEAD) to `2.1.63` and stage it (already happened pre-Plan 04 in working-tree state).
- If the phase-completion commit fails for any reason, the PostToolUseFailure rollback hook will fire and revert both index and working tree to HEAD via `git checkout HEAD -- pyproject.toml` — closing SC #5.
- The hook script's stdout/stderr/exit-code contract is locked: stdout = empty (PostToolUseFailure does not consume stdout), stderr = action log, exit 0 = success in all paths.

## Commits

- `e42721a` — `feat(63-04): add PostToolUseFailure rollback hook for phase-commit failure` (Task 1; force-adds bump-rollback-hook.sh + extends settings.json)
- `c777d29` — `test(63-04): add rollback integration test (VALIDATION row 63-04-01)` (Task 2; +1 test, 9 → 10 GREEN)

## Self-Check: PASSED

- `.claude/hooks/bump-rollback-hook.sh` exists (28 LOC) and is executable (mode 0755) — confirmed via `test -x`.
- `bash -n .claude/hooks/bump-rollback-hook.sh` exits 0 (syntax-clean) — confirmed.
- `grep -q "checkout HEAD -- pyproject.toml" .claude/hooks/bump-rollback-hook.sh` — PASS (line 26).
- Negative grep `grep -vE '^\s*#' .claude/hooks/bump-rollback-hook.sh | grep -E 'git[^|]*checkout\s+--\s+pyproject\.toml($|\s)' | grep -vE 'HEAD' | wc -l` returns **0** — bare form NOT in executable code.
- `python3 -m json.tool .claude/settings.json` exits 0 — valid JSON post-edit.
- `grep -q '"PostToolUseFailure"' .claude/settings.json` — PASS (new sibling block added).
- `grep -q '"PreToolUse"' .claude/settings.json` — PASS (Plan 03's block preserved).
- `git diff` against pre-Plan-04 settings.json shows ONLY the additive new block (PreToolUse block byte-identical except for trailing comma) — confirmed.
- `grep -c '"timeout"' .claude/settings.json` returns 2 — confirmed (one per hook entry).
- Both `.claude/settings.json` AND `.claude/hooks/bump-rollback-hook.sh` tracked in git — confirmed via `git ls-files` returning both.
- 10 tests in `tests/test_bump_version.py` are GREEN (1.35s, 0 skip on this host) — confirmed via `uv run --with pytest pytest`.
- No regression on the 9 prior tests — full module run staying GREEN.
- Commit `e42721a` (feat) on `main` — confirmed via `git log --oneline | grep e42721a`.
- Commit `c777d29` (test) on `main` — confirmed via `git log --oneline | grep c777d29`.
- After Task 1's commit (`e42721a`): `git log -1 --name-only --format= e42721a` shows BOTH `.claude/settings.json` AND `.claude/hooks/bump-rollback-hook.sh` — proves index → commit object handoff.
- Live smoke (in /tmp/smoke-rollback): both `git diff --cached pyproject.toml` and `git diff pyproject.toml` empty after rollback hook fires on phase-completion failure payload; staged bump preserved on no-match payload — confirmed (output captured in execution log).
