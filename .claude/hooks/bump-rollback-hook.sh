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

# Self-guard: only fire when the failed command was actually a commit creator.
# Without this guard, ANY Bash failure whose command-text embeds a phase-completion
# string as DATA (a test loop, a grep over commit messages, etc.) would silently
# `git checkout HEAD -- pyproject.toml` and clobber an in-progress version bump.
if ! echo "$COMMAND" | grep -qE '^[[:space:]]*(gsd-sdk[[:space:]]+query[[:space:]]+commit|git[[:space:]]+commit)\b'; then
    exit 0
fi

# Only fire on a completion-marker commit shape — pass through any other commit
# failure (e.g., a fix-up commit, a doc tracking commit). Mirrors the line-start
# / post-`-m` anchoring in bump-version-hook.sh so body-bullet text describing
# other phases as examples cannot false-trigger a rollback (see 2026-05-24 note
# in bump-version-hook.sh for the discovery context).
if ! echo "$COMMAND" | grep -qPe "(?:^|-m\s+[\"'])docs\((?:phase-)?[0-9]+\):.*(complete phase execution|close phase|mark phase complete)"; then
    exit 0
fi

# Single-command rollback (Pitfall 4 — reverts BOTH index and working tree to HEAD).
# `|| true` so a missing pyproject.toml or out-of-repo invocation never raises beyond
# this script: the original commit failure is what the user needs to see, not a
# rollback error.
git -C "${CLAUDE_PROJECT_DIR}" checkout HEAD -- pyproject.toml || true
echo "[bump-rollback-hook] reverted pyproject.toml to HEAD after phase-commit failure" >&2
exit 0
