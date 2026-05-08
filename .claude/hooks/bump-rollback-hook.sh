#!/usr/bin/env bash
# Phase 63 / VER-01 — rollback pyproject.toml when a phase-completion commit fails.
#
# Reads PostToolUseFailure JSON payload from stdin; if the failed Bash command
# was a phase-completion commit (matches `docs(phase-NN): complete phase execution`),
# reverts pyproject.toml to HEAD via the SINGLE-COMMAND rollback form
# (`git checkout HEAD -- pyproject.toml`). The bare `git checkout -- pyproject.toml`
# form D-08 specifies is a NO-OP against staged changes — RESEARCH §Pitfall 4
# live-verified this on 2026-05-08; do NOT regress to the bare form.
#
# Exit 0 in all paths: PostToolUseFailure hooks are side-effect-only; the agent
# harness does not consume stdout from this event. Failures here MUST NOT cascade.

set -euo pipefail

PAYLOAD=$(cat)
COMMAND=$(jq -r '.tool_input.command' <<< "$PAYLOAD")

# Only fire on the canonical phase-completion commit shape — pass through everything else.
if ! echo "$COMMAND" | grep -qE 'docs\(phase-[0-9]+\): complete phase execution'; then
    exit 0
fi

# Single-command rollback (Pitfall 4 — reverts BOTH index and working tree to HEAD).
# `|| true` so a missing pyproject.toml or out-of-repo invocation never raises beyond
# this script: the original commit failure is what the user needs to see, not a
# rollback error.
git -C "${CLAUDE_PROJECT_DIR}" checkout HEAD -- pyproject.toml || true
echo "[bump-rollback-hook] reverted pyproject.toml to HEAD after phase-commit failure" >&2
exit 0
