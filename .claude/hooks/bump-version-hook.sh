#!/usr/bin/env bash
# Phase 63 / VER-01 — auto-bump pyproject.toml before phase-completion commit.
#
# Reads PreToolUse JSON payload from stdin; if the upcoming Bash command is a
# phase-completion commit (matches `docs(phase-NN): complete phase execution`),
# invokes tools/bump_version.py with the extracted phase number and rewrites
# the upcoming command to append pyproject.toml to its --files list. On bump
# failure, exits 0 with a stderr warning so the original commit proceeds
# unmodified (per D-09: never block the commit on a bump failure).

set -euo pipefail

PAYLOAD=$(cat)
COMMAND=$(jq -r '.tool_input.command' <<< "$PAYLOAD")

# Extract phase number ONLY when the command matches the canonical phase-completion
# commit message. Anything else: pass through unmodified (exit 0, no JSON output).
PHASE_NUM=$(echo "$COMMAND" | grep -oP 'docs\(phase-\K[0-9]+(?=\): complete phase execution)' || true)
if [[ -z "$PHASE_NUM" ]]; then
    exit 0
fi

# Run the bump. On non-zero exit, log to stderr and let the commit proceed.
if ! BUMP_OUTPUT=$(python "${CLAUDE_PROJECT_DIR}/tools/bump_version.py" --phase "$PHASE_NUM" 2>&1); then
    echo "[bump-version-hook] bump failed (phase=$PHASE_NUM): $BUMP_OUTPUT" >&2
    exit 0
fi

# Stage the bumped pyproject.toml so whatever path actually creates the commit
# object picks it up (Pitfall 1 robustness — gsd-sdk query commit may or may not
# land .planning/ files in this repo, but pyproject.toml is not gitignored and
# `git add` always works for it).
git -C "${CLAUDE_PROJECT_DIR}" add pyproject.toml

# Append pyproject.toml to the upcoming command's --files list (idempotent —
# if pyproject.toml is already present, the duplicate is harmless to git add).
NEW_COMMAND="$COMMAND pyproject.toml"

jq -n --arg cmd "$NEW_COMMAND" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "allow",
    permissionDecisionReason: "Phase 63 auto-bump appended pyproject.toml",
    updatedInput: { command: $cmd }
  }
}'
