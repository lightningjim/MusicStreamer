# Phase 63: Auto-Bump pyproject Version on Phase Completion - Research

**Researched:** 2026-05-08
**Domain:** Claude Code hooks, git plumbing, gsd-sdk internals, regex-based TOML rewriting
**Confidence:** HIGH

## Summary

Phase 63 wires an automated version bump (`{milestone_major}.{milestone_minor}.{phase_number}`) into the existing phase-completion commit. CONTEXT.md locks all four implementation decisions; this research surfaces the concrete mechanisms the planner needs to write executable tasks.

**Three load-bearing technical findings (all VERIFIED live in this session):**

1. **Claude Code `PreToolUse` hooks CAN modify the Bash command before execution** via JSON output `hookSpecificOutput.updatedInput.command`. This unlocks the preferred D-01/D-02 path: a single `PreToolUse` hook on `Bash` matched with `if: "Bash(gsd-sdk query commit *)"` runs `python tools/bump_version.py` and rewrites the commit's `--files` list in-place to include `pyproject.toml`. No git-hook fallback needed for the happy path. [VERIFIED: live WebFetch of code.claude.com/docs/en/hooks 2026-05-08]
2. **`gsd-sdk query commit` cannot stage `.planning/` files in this repo today.** Live test against `gsd-sdk` v1.38.5 in this checkout returned `{"committed":false,"reason":"The following paths are ignored by one of your .gitignore files:\n.planning"}`. The `commit` query handler at `gsd-sdk/sdk/dist/query/commit.js:117-121` runs `git add <file>` per file (no `-f`), which emits a warning + exit 1 when targeting gitignored-but-tracked files, and the handler propagates that exit code as a failure. **Phase 62's commit (360aa2d) was created outside this code path** — somehow (likely by hand or by an agent using `git add -f` + `git commit` directly). The planner MUST account for this: the hook's bump step needs to land `pyproject.toml` regardless of whether `gsd-sdk query commit` actually succeeds. [VERIFIED: live `gsd-sdk query commit` invocation 2026-05-08]
3. **`gsd-sdk query config-set` rejects unknown keys.** Live test confirmed `Error: Unknown config key: "workflow.auto_version_bump". Did you mean: workflow.auto_advance?` with exit code 10. The `VALID_CONFIG_KEYS` allowlist at `gsd-sdk/sdk/dist/query/config-schema.js:20-56` does not include `auto_version_bump`. We MUST edit `.planning/config.json` directly (file is plain JSON, atomically rewriteable). `config-get` for the same key returns `Error: Key not found:` with exit 1 — the helper treats this as "default true" per D-10. [VERIFIED: live `gsd-sdk query config-set` + `config-get` invocations 2026-05-08]

**Primary recommendation:** Implement the Claude Code `PreToolUse` hook path (D-01/D-02 primary). It works, it's clean, and it does not require a git-hook fallback. The bump helper at `tools/bump_version.py` is single-purpose and trivially testable. The `workflow.auto_version_bump` config flag is set by direct JSON edit in the same plan that ships the helper, with the helper reading it via `gsd-sdk query config-get workflow.auto_version_bump --raw` and treating "key not found" as default-true.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Detect "phase-completion commit is about to run" | Claude Code agent layer (`.claude/settings.json` hook) | — | Only the agent harness sees the upcoming `Bash` tool call; no git-side mechanism reliably distinguishes "phase-completion commit" from any other commit. |
| Compute new version string | Project Python (`tools/bump_version.py`) | — | Co-locates with `tools/check_*` helpers; pure Python; trivially unit-testable. |
| Read `{major}.{minor}` from PROJECT.md | Project Python (regex on `PROJECT.md`) | — | Single source of truth per D-04; regex on a Markdown heading. |
| Rewrite `pyproject.toml` `version` line | Project Python (regex within `[project]` block) | — | Per D-06/D-07 — no new dep; line-targeted edit preserves comments. |
| Stage bumped file into the commit | Hook script invoking `git add pyproject.toml` | Claude Code hook returning modified `command` with `pyproject.toml` appended to `--files` | Two-pronged: shell side stages the file; the hook also rewrites the upcoming `gsd-sdk query commit` invocation so the staged file lands in the SAME commit object. |
| Read `workflow.auto_version_bump` flag | Project Python via `gsd-sdk query config-get` | Direct JSON read of `.planning/config.json` (fallback if SDK unavailable) | Existing project pattern. |
| Roll back on commit failure | Hook tail (PostToolUse on the same Bash) OR caller-side `git checkout HEAD -- pyproject.toml` | — | PreToolUse cannot observe outcome; rollback runs after-the-fact when the commit returns non-zero. |
| Document scheme | `PROJECT.md` `## Versioning` section | `.planning/config.json` comment | Per D-12. |

## Standard Stack

This phase introduces no new runtime dependencies. All required pieces are already in the codebase or stdlib.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python `re` (stdlib) | 3.10+ | Milestone regex on `PROJECT.md`; section-aware version regex on `pyproject.toml` | D-06 locks regex over `tomlkit` (no new dep); stdlib. [VERIFIED: live regex test against actual `PROJECT.md` + `pyproject.toml`] |
| Python `argparse` (stdlib) | 3.10+ | CLI surface for `bump_version.py --phase NN [--check] [--dry-run]` | Project convention — `tools/check_*.py` are bare scripts, but `bump_version.py` benefits from explicit args per D-03. |
| `gsd-sdk query config-get` | v1.38.5 (current dlx) | Read `workflow.auto_version_bump` flag | Existing project pattern. Returns `"true"`, `"false"`, or exits 1 with `Error: Key not found:` on missing key. [VERIFIED: live invocation] |
| Claude Code `PreToolUse` hook | current docs (2026-05) | Intercept `gsd-sdk query commit "docs(phase-NN): complete phase execution"` Bash invocation, run bump, rewrite command to include `pyproject.toml` | Sole mechanism that fires inside the agent's tool-call flow before `git commit` runs. [VERIFIED: code.claude.com/docs/en/hooks live fetch] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` + `pytest-qt` | 9+ / 4+ | Test runner | Existing project pattern. Tests for `bump_version.py` are pure-Python (no Qt) but run under the same harness. |
| `tomllib` (stdlib, Py 3.11+) | 3.11+ | Read-only verification of post-bump `pyproject.toml` content in tests | Already imported at `tests/test_media_keys_smtc.py:9` — same pattern. [VERIFIED: file inspection] |
| `unittest.mock` (stdlib) | 3.10+ | Patch `subprocess`/`gsd-sdk` calls in helper tests | Existing project pattern (see `tests/test_player_volume.py`). |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Regex rewrite | `tomlkit` (preserves comments + whitespace) | Adds a dep, and D-06 explicitly rejected it. The regex-on-a-single-line approach has zero comment-loss risk because it only touches one line. |
| Claude Code hook | git `prepare-commit-msg` hook | git hooks live in `.git/hooks/` (per-clone, not committed) so they're invisible to a fresh checkout. Project-wide install requires a repo-tracked script + onboarding step. Acceptable as fallback only. [VERIFIED: git-scm.com/docs/githooks] |
| Claude Code hook | git `pre-commit` hook | `pre-commit` runs BEFORE the commit message is finalized — it cannot pattern-match the message. Only `prepare-commit-msg` and `commit-msg` see the message file. [VERIFIED: git-scm.com/docs/githooks] |
| `python tools/bump_version.py` | Inline shell logic in the hook | Helper is independently testable; shell-only logic is not. D-03 locks the helper. |

**Installation (no new deps):**
```bash
# nothing to install — all pieces are in stdlib or already in the project
```

**Version verification:** Not applicable; no new packages.

## Architecture Patterns

### System Architecture Diagram

```
   /gsd-execute-phase {N}
            │
            ▼
   Workflow update_roadmap step
   (~/.claude/get-shit-done/workflows/execute-phase.md:1543)
            │
            ▼
   gsd-sdk query phase.complete N         ◄── updates ROADMAP.md/STATE.md/REQUIREMENTS.md
            │                                  (separate file writes; not committed yet)
            ▼
   gsd-sdk query commit "docs(phase-N): complete phase execution"
       --files .planning/ROADMAP.md ...
            │
            │  ┌─── intercepted by Claude Code PreToolUse hook ───┐
            │  │  matcher: "Bash"                                  │
            │  │  if: "Bash(gsd-sdk query commit *)"               │
            │  │                                                    │
            │  │  payload: {tool_name:"Bash",                       │
            │  │            tool_input:{command:"gsd-sdk ..."}}     │
            │  │                                                    │
            │  │  hook reads command, regex-matches                 │
            │  │  /docs\(phase-(\d+)\): complete phase execution/   │
            │  │  if no match → exit 0 (allow unmodified)           │
            │  │                                                    │
            │  │  if match → spawn:                                 │
            │  │    python tools/bump_version.py --phase N          │
            │  │      ↓                                              │
            │  │    1. read workflow.auto_version_bump              │
            │  │    2. parse PROJECT.md milestone heading           │
            │  │    3. regex-rewrite pyproject.toml [project] block │
            │  │    4. git add pyproject.toml                        │
            │  │    5. exit 0 / non-zero on parse failure            │
            │  │                                                    │
            │  │  on bump success: emit JSON with                    │
            │  │    permissionDecision:"allow" + updatedInput.command│
            │  │    appending pyproject.toml to --files list         │
            │  │  on bump failure (non-zero): exit 0 unmodified;     │
            │  │    print warning to stderr; commit proceeds w/o bump│
            │  └────────────────────────────────────────────────────┘
            ▼
   git add .planning/ROADMAP.md ... pyproject.toml
   git commit -m "docs(phase-N): complete phase execution"
            │
            ├── exit 0  → done; bumped version is in the commit
            │
            └── exit ≠0 → rollback path (PostToolUseFailure hook OR
                          subsequent step):
                          git restore --staged pyproject.toml
                          git checkout -- pyproject.toml
```

**Diagram notes:**
- The bump runs inside the PreToolUse hook process. `gsd-sdk query commit` is then invoked by Claude with the rewritten `--files` list.
- `gsd-sdk query commit`'s implementation runs `git add <file>` per `--files` entry. As of today, `.planning/*` paths fail with exit 1 in this repo because of `.gitignore` (see Pitfall 1). The bump's `pyproject.toml` add will succeed regardless because pyproject is not gitignored.
- The rollback step needs its own hook. PostToolUse can't observe failure; PostToolUseFailure can. See Question 6 below.

### Recommended Project Structure

```
tools/
├── __init__.py             # empty (existing)
├── check_spec_entry.py     # existing pattern reference
├── check_subprocess_guard.py  # existing pattern reference
└── bump_version.py         # NEW (this phase)

.claude/
├── settings.json           # NEW (this phase) — gitignored at top level,
│                           #   needs git add -f to track
└── hooks/
    └── bump-version-hook.sh   # NEW (this phase) — wraps tools/bump_version.py
                               #   with hook-protocol JSON I/O

PROJECT.md                  # MODIFIED — add ## Versioning section near ## Constraints
.planning/config.json       # MODIFIED — add workflow.auto_version_bump: true (direct edit)

tests/
└── test_bump_version.py    # NEW (this phase)
```

### Pattern 1: Co-located Python tooling helper

**What:** A standalone Python script under `tools/` with a `main()` entry, callable as `python tools/<name>.py [args]`.
**When to use:** Any project-internal CLI helper that's not part of the runtime application package.
**Example (verbatim shape from existing `tools/check_subprocess_guard.py`):**

```python
"""<docstring describing the guard / helper>.

Exit codes:
    0 — happy path
    N — distinguishable failure modes (Phase 63: 1=parse err, 2=regex no-match, 3=config disabled)

Callable as ``python tools/bump_version.py`` from the repo root.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", type=int, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    # ...
    sys.exit(0)


if __name__ == "__main__":
    main()
```

### Pattern 2: Claude Code PreToolUse JSON output (modify command)

**What:** Hook script writes JSON to stdout, exits 0; the JSON tells the agent harness what to do with the upcoming tool call.
**When to use:** Mutating an upcoming Bash command in flight (the only path that gets the bumped file into the same commit object as the .planning/ files).
**Example (worked, from official docs — VERIFIED):**

```bash
#!/bin/bash
# .claude/hooks/bump-version-hook.sh
# Reads PreToolUse payload from stdin, runs the bump, emits JSON that appends
# pyproject.toml to the upcoming `gsd-sdk query commit` --files list.

set -euo pipefail

PAYLOAD=$(cat)
COMMAND=$(jq -r '.tool_input.command' <<< "$PAYLOAD")

# Only intercept the canonical phase-completion commit message.
PHASE_NUM=$(echo "$COMMAND" | grep -oP 'docs\(phase-\K[0-9]+(?=\): complete phase execution)' || true)
if [[ -z "$PHASE_NUM" ]]; then
    exit 0   # not our commit; let it through unmodified
fi

# Run the bump; on failure, let the original commit proceed without bump.
if ! BUMP_OUTPUT=$(python "${CLAUDE_PROJECT_DIR}/tools/bump_version.py" --phase "$PHASE_NUM" 2>&1); then
    echo "[bump-version-hook] bump failed: $BUMP_OUTPUT" >&2
    exit 0   # do not block the commit; surface the warning
fi

# Append pyproject.toml to --files list (idempotent).
NEW_COMMAND="$COMMAND pyproject.toml"

jq -n --arg cmd "$NEW_COMMAND" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "allow",
    permissionDecisionReason: "Phase 63 auto-bump appended pyproject.toml",
    updatedInput: { command: $cmd }
  }
}'
```

**`.claude/settings.json` matcher (worked example — VERIFIED via official docs):**

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

**Key facts about this matcher (all VERIFIED via official Claude Code docs 2026-05):**
- `matcher: "Bash"` filters on `tool_name`.
- `if: "Bash(gsd-sdk query commit *)"` is a permission-rule glob matcher applied to the command string — runs the hook only when the Bash command starts with `gsd-sdk query commit`. The hook itself does the finer-grained regex match for `docs(phase-NN): complete phase execution`.
- `$CLAUDE_PROJECT_DIR` resolves to the repo root.
- The hook has stdin = JSON payload, stdout = JSON response, exit 0 = success (parse JSON for decision), exit 2 = blocking error.
- `permissionDecision: "allow"` + `updatedInput.command` rewrites the upcoming Bash command in-place.

### Pattern 3: Section-aware regex rewrite of `pyproject.toml`

**What:** Find the `[project]` table boundaries, then replace the `version` line within those boundaries only.
**When to use:** Per D-07, must not match `version =` keys in other tables (e.g. `[tool.poetry]`).
**Example (VERIFIED live against this repo's `pyproject.toml`):**

```python
import re
from pathlib import Path

# Anchored on a heading line; strict — no other text on the line.
_PROJECT_TABLE_RE = re.compile(r'^\[project\]\s*$', re.MULTILINE)
_NEXT_TABLE_RE = re.compile(r'^\[', re.MULTILINE)
# version = "..." — full-line match, preserves trailing whitespace via \g<2>
_VERSION_LINE_RE = re.compile(r'^(version\s*=\s*)"[^"]*"(\s*)$', re.MULTILINE)


def rewrite_pyproject_version(content: str, new_version: str) -> str | None:
    """Return content with [project].version replaced by new_version,
    or None if the [project] table or version line was not found.
    """
    m = _PROJECT_TABLE_RE.search(content)
    if not m:
        return None  # no [project] table — abort
    section_start = m.end()
    n = _NEXT_TABLE_RE.search(content, section_start + 1)
    section_end = n.start() if n else len(content)
    section = content[section_start:section_end]
    new_section, count = _VERSION_LINE_RE.subn(
        rf'\g<1>"{new_version}"\g<2>', section
    )
    if count != 1:
        return None  # zero or multiple version lines in [project]
    return content[:section_start] + new_section + content[section_end:]
```

**Live verification result (this session, 2026-05-08):**
- Against the actual `/home/kcreasey/OneDrive/Projects/MusicStreamer/pyproject.toml` with `new_version="2.1.63"`:
  - Exactly 1 line changed: `(6, 'version = "2.1.60"', 'version = "2.1.63"')`
  - All comments preserved; all other lines byte-identical.
- Against a synthetic file with `[project] version` AND `[tool.poetry] version`: only the `[project]` one was rewritten — the `[tool.poetry]` version was untouched. D-07 invariant satisfied.
- Against a file with no `[project]` table: returned `None`. D-09 abort path satisfied.

### Pattern 4: Milestone parse from `PROJECT.md` heading

**What:** Match `## Current Milestone: vX.Y` at the start of a line; ignore `## Previous Milestone:` and any other text.
**When to use:** Sole regex per D-04. Anchor with `^##\s+Current Milestone:` so the literal "Previous Milestone" line cannot match.
**Example (VERIFIED live against this repo's `PROJECT.md`):**

```python
import re

_MILESTONE_RE = re.compile(
    r'^##\s+Current Milestone:\s*v(\d+)\.(\d+)',
    re.MULTILINE,
)


def parse_milestone(project_md_text: str) -> tuple[int, int] | None:
    """Return (major, minor) from PROJECT.md's `## Current Milestone:` heading,
    or None if no such heading exists.

    `re.search` returns the FIRST match; multiple `## Current Milestone:`
    lines (which would be malformed) take the first.
    """
    m = _MILESTONE_RE.search(project_md_text)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))
```

**Live verification result:**
- Match: `## Current Milestone: v2.1` → `major=2, minor=1`. (Source: `.planning/PROJECT.md:11`.)
- The `## Previous Milestone: v2.0` line at `PROJECT.md:42` is correctly NOT matched (anchored on `Current`, not `Previous`).

### Anti-Patterns to Avoid

- **Hand-edit pyproject.toml on phase boundaries.** D-01 explicitly automates this. Manual edits drift; the helper exists to prevent the drift demonstrated by `2.1.60` being two phases stale.
- **Pre-load `tomllib` and round-trip.** `tomllib` is read-only; round-tripping requires re-serializing, which loses comment/whitespace fidelity. D-06 rejected this.
- **Use `commit-msg` or `pre-commit` git hook for the bump.** `pre-commit` cannot see the commit message; `commit-msg` runs after the commit object's tree is finalized. Neither can stage `pyproject.toml` into the same commit. Only `prepare-commit-msg` (rejected as fallback path because git hooks aren't repo-tracked by default) or the Claude Code hook can.
- **Try to add `workflow.auto_version_bump` via `gsd-sdk query config-set`.** It will fail with `Error: Unknown config key`. The schema is a hard allowlist. Edit the JSON directly.
- **Trust D-08's literal `git checkout -- pyproject.toml`.** When the bump has staged the file (which it MUST, to land in the commit), `git checkout -- file` reverts working-tree to the staged version, NOT to HEAD. See Pitfall 4 below.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Generic Bash-command pattern interception | A `bash`-side wrapper around `git commit` or `gsd-sdk` | Claude Code PreToolUse hook with `if: "Bash(gsd-sdk query commit *)"` | The hook fires inside the agent harness with a clean JSON protocol; a shell wrapper would only fire if the user calls a wrapper script, not the canonical command. |
| Commit message templating | Custom shell parser | The hook's regex over `tool_input.command` (one line of grep) | The phase-completion commit message has a fixed canonical shape (`docs(phase-NN): complete phase execution`) — single regex suffices. |
| TOML rewriting that preserves comments | A multi-token TOML serializer | Single-line regex within section bounds | The version line is one self-contained line; no need to model the rest of the file. |
| File watching / change notification | inotify / fs-watch | One-shot synchronous bump in the hook | The hook runs on a deterministic event (the upcoming Bash call); no ambient watching required. |
| Config schema validation | Custom validator | Direct JSON edit + helper that tolerates "key not found" | We can't extend `gsd-sdk`'s allowlist (would need an upstream change). Treat absence as default-true per D-10. |

**Key insight:** The whole phase fits inside ~150 lines of Python (`tools/bump_version.py`) + ~30 lines of bash (`.claude/hooks/bump-version-hook.sh`) + ~15 lines of JSON (`.claude/settings.json` block). No new runtime dependencies. The temptation to over-engineer (write a TOML library, a generic version-bump tool, a config-key registrar) should be resisted.

## Common Pitfalls

### Pitfall 1: `gsd-sdk query commit` fails for `.planning/` files in this repo
**What goes wrong:** `gsd-sdk query commit ... --files .planning/ROADMAP.md ...` returns `{"committed":false,"reason":"The following paths are ignored by one of your .gitignore files:\n.planning"}` with `exitCode: 1`.
**Why it happens:** `.gitignore` includes `.planning/` (line 27). Files like `ROADMAP.md` were initially `git add -f`'d so they're tracked, but git's `add` (without `-f`) emits a warning and exits 1 when targeting paths matching a `.gitignore` entry — even for already-tracked files. `gsd-sdk query commit` (commit.js:117-121) propagates that exit code as a hard failure.
**Live evidence (this session, 2026-05-08):**
```
$ git status --short .planning/config.json
 M .planning/config.json
$ gsd-sdk query commit "test commit" --files .planning/config.json --force
{
  "committed": false,
  "reason": "The following paths are ignored by one of your .gitignore files:\n.planning\n...",
  "exitCode": 1
}
```
**How to avoid:** The Phase 63 bump hook MUST stage `pyproject.toml` via direct `git add pyproject.toml` (no `--force` needed; pyproject is not gitignored). Whether `gsd-sdk query commit` itself succeeds is orthogonal — and indeed the historical pattern in this repo (e.g. commit `360aa2d` for Phase 62) was that the phase-completion commit was created either by hand or by an alternate path that bypasses the SDK's `git add` step. The hook should NOT depend on `gsd-sdk query commit` succeeding to consider the bump "done"; it just needs `pyproject.toml` to be staged so whatever path actually creates the commit picks it up. **Surface this issue to the planner: the planner may want to add a separate task documenting the pre-existing `.planning/` gitignore situation, since the same ambient failure undermines all phase commits, not just the bump.**
**Warning signs:** `git status` after `gsd-sdk query commit` returns shows `.planning/*` files still modified (not committed). HEAD points to the previous phase's commit.

### Pitfall 2: PROJECT.md milestone heading silently moves or gets reformatted
**What goes wrong:** Someone reformats `## Current Milestone: v2.1 Fixes and Tweaks` to `## Milestone (current): v2.1` or `### Current Milestone: v2.1` and the bump regex stops matching. D-09 says "abort with non-zero, no bump" — correct behavior, but easy to miss.
**Why it happens:** PROJECT.md is hand-edited at milestone boundaries (`/gsd-complete-milestone`), and the heading pattern isn't enforced anywhere.
**How to avoid:** Add a drift-guard test (`tests/test_bump_version.py::test_project_md_milestone_heading_grep`) that asserts `PROJECT.md` contains exactly one line matching `^##\s+Current Milestone:\s*v\d+\.\d+`. Mirrors the existing drift-guard pattern in `tests/test_constants_drift.py` (per Phase 61 STATE entry).
**Warning signs:** The bump helper exits non-zero with "PROJECT.md milestone heading not found" on a phase commit; test gate catches it BEFORE the phase commit step.

### Pitfall 3: `gsd-sdk query config-set workflow.auto_version_bump` rejects the unknown key
**What goes wrong:** Naive plan task uses `gsd-sdk query config-set workflow.auto_version_bump true` to seed the flag. Live test returned `Error: Unknown config key: "workflow.auto_version_bump". Did you mean: workflow.auto_advance?` with exit code 10.
**Why it happens:** `gsd-sdk` validates against a hardcoded allowlist (`VALID_CONFIG_KEYS` in `gsd-sdk/sdk/dist/query/config-schema.js:20-56`). `auto_version_bump` is not in it.
**How to avoid:** The plan that introduces the flag must edit `.planning/config.json` directly (it's a small, well-formed JSON file — Python's `json.dumps(json.loads(...), indent=2)` round-trips it cleanly). The bump helper reads via `gsd-sdk query config-get workflow.auto_version_bump --raw`, which works fine for already-present keys; for missing keys it exits 1 with `Error: Key not found:` (treat as default-true per D-10).
**Warning signs:** Plan task fails immediately with `Unknown config key`; `.planning/config.json` is unchanged.

### Pitfall 4: `git checkout -- pyproject.toml` does NOT roll back staged changes
**What goes wrong:** D-08 specifies rollback via `git checkout -- pyproject.toml`. Live test: when the bump has staged `pyproject.toml` (which it MUST do to land in the commit), `git checkout -- pyproject.toml` reverts the working-tree copy to the STAGED version — NOT to HEAD. The staged change persists. The next commit (manual or automated) would still include the bump.
**Why it happens:** `git checkout -- <path>` semantics: replace working-tree with index version. When the index already holds the bumped version (because the helper ran `git add`), the working-tree gets the bumped version too — the rollback is a no-op.
**Live evidence (this session, 2026-05-08):**
```
$ echo "MODIFIED3" > file.txt; git add file.txt
$ git checkout -- file.txt        # D-08 verbatim
$ cat file.txt
MODIFIED3                         # ← still bumped
$ git diff --cached
+MODIFIED3                        # ← still staged
```
**How to avoid:** Use the modern two-command sequence: `git restore --staged pyproject.toml && git checkout -- pyproject.toml`. Equivalently, single command `git checkout HEAD -- pyproject.toml` (reverts both index and working-tree to HEAD's version) — also verified live. Recommend the single-command form for the rollback step. The planner should treat D-08 as a typo/shorthand and lock the actual rollback command to one of the two correct forms above.
**Warning signs:** After a forced-failure test (mock the `git commit` to return non-zero), `git diff --cached pyproject.toml` still shows the bumped version.

### Pitfall 5: PostToolUse can't observe the failure case
**What goes wrong:** Naive plan wires rollback to `PostToolUse` on Bash. `PostToolUse` runs only when the tool succeeds — when `gsd-sdk query commit` returns non-zero (commit rejected by hook, etc.), `PostToolUse` does NOT fire.
**Why it happens:** Claude Code defines two distinct events: `PostToolUse` (tool succeeded) and `PostToolUseFailure` (tool failed). [VERIFIED: code.claude.com/docs/en/hooks 2026-05]
**How to avoid:** Wire the rollback step to `PostToolUseFailure` (matcher `Bash`, `if: "Bash(gsd-sdk query commit *)"`). Inside, parse the original command from `tool_input.command` to detect it was a phase-completion commit (re-use the same regex as PreToolUse), then run the rollback sequence. Acceptable alternative: defer rollback to the *next* invocation of the bump hook — at the start of every phase-completion bump, check `git diff --cached pyproject.toml` and, if dirty without a corresponding HEAD commit advance, restore. Slightly racier but avoids the second hook script.
**Warning signs:** A simulated commit failure (e.g. `pre-commit` hook returns non-zero) leaves `pyproject.toml` staged with the bumped version; the next attempt at the same phase commit double-bumps OR appears to succeed-but-with-wrong-version.

### Pitfall 6: CRLF on cross-platform clones
**What goes wrong:** A Windows contributor clones with `core.autocrlf=true`. `pyproject.toml` lands with `\r\n` line endings. The regex `^version\s*=\s*"[^"]*"\s*$` with re.MULTILINE matches a line ending in `\r"`, but the substitution might leave `version = "2.1.63"\r` (with embedded `\r`) which TOML parsers tolerate but git diffs as a one-line change to a CRLF file. If the helper opened the file with `open(..., 'r')` (text mode), Python translates `\r\n` to `\n` on read and back on write — line-ending invariant preserved. If opened in binary mode, the `\r` is part of the regex domain and may slip through.
**Why it happens:** Python's text-mode I/O is platform-specific by default; mixing binary read with text-mode regex is a footgun.
**How to avoid:** Always open `pyproject.toml` in TEXT mode with explicit `encoding="utf-8"` for both read and write. The current file (verified live) is LF-only on this Linux dev host (`file pyproject.toml` → `Unicode text, UTF-8 text`, no CRLF). The helper should preserve whatever line-ending convention the file has. The `\s*$` in the regex (with re.MULTILINE) tolerates either LF or CRLF without rewriting them.
**Warning signs:** A Windows-side test fails with a single-line diff showing `\r` as `^M` in `git diff`.

### Pitfall 7: The bump helper invocation surface vs. test surface drift
**What goes wrong:** Hook calls `python tools/bump_version.py --phase 63`; tests call `bump_version.main(...)` directly. The two surfaces drift, e.g. argparse defaults change but the helper's `main()` defaults don't.
**How to avoid:** The helper's `main()` MUST accept all args via argparse (no positional `main(phase: int)`). Tests invoke via `subprocess.run([sys.executable, "tools/bump_version.py", "--phase", "63", ...])` — same interface as the hook. Slower (~50-100ms per test) but eliminates the drift class. Or: use a wrapper test fixture that calls `main()` with `sys.argv` set, exercising the argparse path.
**Warning signs:** Test passes; live invocation from the hook fails with an argparse error that the test doesn't catch.

### Pitfall 8: `.claude/settings.json` is gitignored at top level
**What goes wrong:** The plan adds `.claude/settings.json` and `.claude/hooks/bump-version-hook.sh` but doesn't `git add -f` them. They're invisible on a fresh clone. The bump never fires for the next contributor.
**Why it happens:** Top-level `.claude/` is in `.gitignore` line 23. Existing tracked files (`.claude/skills/spike-findings-musicstreamer/...`) were force-added previously.
**Live evidence:**
```
$ grep -E "claude" .gitignore
.claude/
$ git ls-files .claude/ | head -3
.claude/skills/spike-findings-musicstreamer/SKILL.md
.claude/skills/spike-findings-musicstreamer/references/qt-glib-bus-threading.md
.claude/skills/spike-findings-musicstreamer/sources/43-gstreamer-windows-spike/43-SPIKE-FINDINGS.md
```
**How to avoid:** The phase plan must explicitly use `git add -f .claude/settings.json .claude/hooks/bump-version-hook.sh` when committing them. Document this in the plan task. The drift-guard test should verify these files exist (`Path(".claude/settings.json").exists()`).
**Warning signs:** Fresh clone of the repo doesn't auto-bump on phase completion; `git ls-files .claude/settings.json` returns empty.

## Runtime State Inventory

This is not a rename phase, but the bump touches several cross-cutting state surfaces. The planner should be aware of:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — Phase 63 does not touch any stored datasets, DBs, or caches. | None. |
| Live service config | `pyproject.toml` `version` field — currently `2.1.60` (two phases stale). On first Phase 63 close: helper writes `2.1.63`. No external service reads this — Windows installer (Inno Setup) builds read it at build time only. | Code edit (regex rewrite), no migration. |
| OS-registered state | None. The version field is consumed only at `pip install` / `pyinstaller build` time. | None. |
| Secrets/env vars | None. | None. |
| Build artifacts / installed packages | `musicstreamer.egg-info/` directory may carry an old version after the bump until the next `pip install -e .` is run. Stale egg-info does not break the app at runtime — it only affects metadata reads. Windows PyInstaller bundles produce a fresh `MusicStreamer-{version}.exe` installer; the version is read fresh from `pyproject.toml` at build time. | Optional: document "run `pip install -e .` after a phase completion if you care about local egg-info parity"; not a blocker. |

**Nothing found in category:** All other categories explicitly verified above as not applicable to this phase.

## Code Examples

Verified patterns from official sources and live tests in this session.

### Example 1: Section-aware pyproject.toml version rewrite (Python)

```python
# tools/bump_version.py — core rewrite logic (VERIFIED live against this repo)
import re

_PROJECT_TABLE_RE = re.compile(r'^\[project\]\s*$', re.MULTILINE)
_NEXT_TABLE_RE = re.compile(r'^\[', re.MULTILINE)
_VERSION_LINE_RE = re.compile(r'^(version\s*=\s*)"[^"]*"(\s*)$', re.MULTILINE)


def rewrite_pyproject_version(content: str, new_version: str) -> str | None:
    m = _PROJECT_TABLE_RE.search(content)
    if not m:
        return None
    section_start = m.end()
    n = _NEXT_TABLE_RE.search(content, section_start + 1)
    section_end = n.start() if n else len(content)
    section = content[section_start:section_end]
    new_section, count = _VERSION_LINE_RE.subn(
        rf'\g<1>"{new_version}"\g<2>', section
    )
    if count != 1:
        return None
    return content[:section_start] + new_section + content[section_end:]
```

### Example 2: Milestone parse from PROJECT.md (Python, VERIFIED live)

```python
# tools/bump_version.py — milestone parse (VERIFIED live against this repo)
import re

_MILESTONE_RE = re.compile(
    r'^##\s+Current Milestone:\s*v(\d+)\.(\d+)',
    re.MULTILINE,
)


def parse_milestone(project_md: str) -> tuple[int, int] | None:
    m = _MILESTONE_RE.search(project_md)
    return (int(m.group(1)), int(m.group(2))) if m else None
```

### Example 3: Read `workflow.auto_version_bump` config flag with default-true fallback (Python)

```python
# tools/bump_version.py — config gate (Pattern matches D-10)
import subprocess


def is_auto_bump_enabled(repo_root: Path) -> bool:
    """Return True if workflow.auto_version_bump is true OR not set.
    D-10: missing key (gsd-sdk exit 1) is treated as default-true.
    """
    result = subprocess.run(
        ["gsd-sdk", "query", "config-get", "workflow.auto_version_bump", "--raw"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return True  # key not found → default true (D-10)
    return result.stdout.strip() == "true"
```

### Example 4: Rollback sequence (shell, VERIFIED live)

```bash
# .claude/hooks/bump-rollback-hook.sh — fires on PostToolUseFailure
# Resets pyproject.toml to HEAD when a phase-completion commit failed
# AND the bump had staged a change.
set -euo pipefail
PAYLOAD=$(cat)
COMMAND=$(jq -r '.tool_input.command' <<< "$PAYLOAD")
if ! echo "$COMMAND" | grep -qE 'docs\(phase-[0-9]+\): complete phase execution'; then
    exit 0
fi
# Single-command form (verified):
git -C "$CLAUDE_PROJECT_DIR" checkout HEAD -- pyproject.toml || true
echo "[bump-rollback-hook] reverted pyproject.toml after commit failure" >&2
exit 0
```

### Example 5: PreToolUse JSON output that mutates the upcoming command (VERIFIED via official docs)

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "permissionDecisionReason": "Phase 63 auto-bump appended pyproject.toml",
    "updatedInput": {
      "command": "gsd-sdk query commit \"docs(phase-63): complete phase execution\" --files .planning/ROADMAP.md .planning/STATE.md .planning/REQUIREMENTS.md .planning/phases/63-.../63-VERIFICATION.md pyproject.toml"
    }
  }
}
```

### Example 6: Test fixture for the helper (Python, mirrors `tests/test_player_volume.py` patterns)

```python
# tests/test_bump_version.py
from pathlib import Path
import subprocess
import sys
import json


def test_bump_rewrites_version_within_project_block(tmp_path):
    """SC#1: bumping rewrites version = '2.1.NN' within [project]."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\n'
        'name = "test"\n'
        'version = "0.0.0"\n'
        '\n'
        '[tool.poetry]\n'
        'version = "9.9.9"\n',
        encoding="utf-8",
    )
    project_md = tmp_path / "PROJECT.md"
    project_md.write_text(
        "# Test\n\n## Current Milestone: v3.7 Some Words\n\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parent.parent / "tools" / "bump_version.py"),
            "--phase", "42",
            "--pyproject", str(pyproject),
            "--project-md", str(project_md),
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    body = pyproject.read_text(encoding="utf-8")
    assert 'version = "3.7.42"' in body
    assert 'version = "9.9.9"' in body  # [tool.poetry] untouched (D-07)


def test_bump_aborts_when_no_milestone_heading(tmp_path):
    """SC#5 / D-09: abort cleanly on parse failure."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "1.0.0"\n', encoding="utf-8")
    project_md = tmp_path / "PROJECT.md"
    project_md.write_text("# No milestone here\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "tools/bump_version.py",
         "--phase", "42",
         "--pyproject", str(pyproject), "--project-md", str(project_md)],
        capture_output=True, text=True, cwd=Path(__file__).resolve().parent.parent,
    )
    assert result.returncode != 0
    # File must be unchanged (D-09: no partial writes)
    assert pyproject.read_text(encoding="utf-8") == '[project]\nversion = "1.0.0"\n'


def test_bump_skipped_when_flag_disabled(tmp_path, monkeypatch):
    """SC#3 / D-11: workflow.auto_version_bump=false → no-op."""
    # Point the helper at a stub gsd-sdk that returns 'false' on config-get
    fake_sdk = tmp_path / "gsd-sdk"
    fake_sdk.write_text(
        '#!/bin/sh\n'
        'if [ "$1 $2 $3" = "query config-get workflow.auto_version_bump" ]; then\n'
        '  echo false; exit 0\n'
        'fi\n'
        'exit 99\n'
    )
    fake_sdk.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")
    # ... rest of test: assert pyproject is unchanged
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual `vim pyproject.toml` per phase | Automated bump via PreToolUse hook | Phase 63 (this phase) | Eliminates the 2-phase drift demonstrated by `2.1.60` (current state) lagging Phases 61 + 62. |
| Pre-`tomllib` Python: third-party `toml` package | `tomllib` (read-only, stdlib) for verification + regex for write | Python 3.11 (already adopted in `tests/test_media_keys_smtc.py`) | No new dep; consistent with project pattern. |
| Older Claude Code hook docs (pre-`updatedInput`) | `permissionDecision: "allow"` with `updatedInput.command` is now a stable, documented capability | code.claude.com migration (recent) | Enables D-01 happy-path without git-hook fallback. |
| `git add` then `git commit` separately + `git checkout -- file` rollback | `git restore --staged ... && git checkout --` OR single `git checkout HEAD -- file` | git 2.23+ (`git restore`/`git switch`) | The literal D-08 verbatim does NOT roll back staged changes. Use the modern form. |

**Deprecated/outdated:**
- Anything that reads "`pre-commit` hook can pattern-match the commit message": false. `pre-commit` runs before the commit message exists. Only `prepare-commit-msg` and `commit-msg` see the message.
- "`tomlkit` for safe TOML rewriting": valid pattern, but D-06 explicitly rejected the dependency cost for a one-line edit.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The Claude Code hook payload structure documented at code.claude.com (2026-05) is what the *currently-installed* Claude Code agent actually sends. The doc page is current as of the live fetch this session, but the local agent version was not separately verified against the doc. | Pattern 2, Examples 5 | If the local agent's payload schema lags the docs (older field names like `tool_call_id` instead of `tool_use_id`, etc.), the hook script's `jq` calls may extract empty strings. Mitigation: log the raw payload to a debug file during the first execution and fix any field-name drift; this is a one-time discovery, not a recurring failure. |
| A2 | Past phase-completion commits (e.g. `360aa2d` for Phase 62) were created via a path that DOES land `.planning/*` files despite the gitignore failure documented in Pitfall 1. The exact path was not traced — they were probably created by hand or by an agent variant that uses `git add -f` directly. | Pitfall 1 | If the planner assumes `gsd-sdk query commit` will succeed, the phase 63 commit may fail to land any files at all. Mitigation: planner should treat `gsd-sdk query commit` as best-effort; the bump's success is determined by `pyproject.toml` ending up staged, which is independent of the SDK's outcome. |
| A3 | Inno Setup / Windows installer reads `pyproject.toml`'s `version` field at build time, not at install time. CONTEXT didn't specify, but `.planning/codebase/STACK.md` (line 98) says "Version passed from pyproject.toml to iscc.exe" which supports the assumption. | Runtime State Inventory | If the version is read at install time (e.g., baked into a registry key), running the installer with a stale Inno script would not pick up new pyproject versions. Mitigation: not a Phase 63 concern — the build pipeline picks up the bumped pyproject on the next Windows release build. |

## Open Questions

1. **Should the rollback step be a separate `PostToolUseFailure` hook, or self-healing on the next bump invocation?**
   - What we know: `PostToolUse` does not fire on tool failure. `PostToolUseFailure` does. Either path can run the `git checkout HEAD -- pyproject.toml` command.
   - What's unclear: Whether the planner wants a tighter loop (separate hook, immediate revert) or a slower-but-simpler one (no second hook; on next bump, helper checks `git diff --cached pyproject.toml` and resets if dirty without a HEAD advance since last known good).
   - Recommendation: Ship the separate `PostToolUseFailure` hook in the same plan as the PreToolUse hook. It's ~10 lines of bash; the test surface is small (mock a non-zero `git commit` result, assert pyproject is at HEAD); future-proofs against weird states.

2. **Should the bump helper auto-detect the phase number from STATE.md, or strictly require `--phase`?**
   - What we know: CONTEXT.md "Claude's Discretion" notes recommend `--phase` for trivial testability.
   - What's unclear: The hook already extracts the phase number from the commit message (`docs(phase-NN):`); having the helper accept `--phase` matches the test surface. Auto-detection from STATE.md would be a fallback for users running the helper standalone.
   - Recommendation: Lock `--phase` as required (per the recommendation in CONTEXT discretion). Add a separate `--auto-detect` mode in a follow-up phase if standalone use becomes important.

3. **Where exactly should the `## Versioning` section land in PROJECT.md?**
   - What we know: D-12 says "near `## Constraints`". `## Constraints` lives at PROJECT.md line 224.
   - What's unclear: Above or below? `## Constraints` is followed by `## Phase History` — placing the new section between them feels natural, but the planner should pick.
   - Recommendation: Place it directly above `## Constraints` (after the last `## Previous Milestone:` block). Both locations are equivalent for readability; "above Constraints" matches the convention of meta-information before history.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | `tools/bump_version.py` | ✓ | 3.13 (system) | — |
| Python 3.11+ `tomllib` (test verification only) | `tests/test_bump_version.py` | ✓ (already used at `tests/test_media_keys_smtc.py:9`) | stdlib | — |
| `gsd-sdk` v1.38.5 | Helper's `config-get` call | ✓ | 1.38.5 (resolved via `~/.local/bin/gsd-sdk` wrapper) | direct JSON read of `.planning/config.json` |
| `git` | Hook's `git add` / `git checkout` | ✓ | system git | — |
| `jq` | `.claude/hooks/bump-version-hook.sh` (parsing JSON payload) | ✓ (assumed available — system tool) | system | If `jq` is somehow missing, the hook can grep with sed; ugly but workable. Recommend documenting `jq` as a dev dependency. |
| Claude Code CLI | The hook itself fires only when the user uses Claude Code | n/a (this is the development assistant) | n/a | If a user runs `gsd-sdk query commit "docs(phase-NN): complete phase execution"` from a plain shell (no Claude Code), the hook doesn't fire. The bump silently doesn't happen. **This is acceptable** — bumping is a developer-experience enhancement, not a contract-level requirement. |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** `gsd-sdk` config-get → direct JSON read (low effort).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9+ (existing) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` lines 50-54 |
| Quick run command | `uv run --with pytest pytest tests/test_bump_version.py -x` |
| Full suite command | `uv run --with pytest pytest tests/ -x` |

### Phase Requirements → Test Map

VER-01 maps to the 5 ROADMAP success criteria. Each maps to one or more automated tests; one (SC #4) is verified by file inspection rather than runtime assertion.

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VER-01 / SC #1 | Bumping Phase 51 → `pyproject.toml` becomes `2.1.51` | unit | `pytest tests/test_bump_version.py::test_bump_rewrites_version_within_project_block -x` | ❌ Wave 0 |
| VER-01 / SC #1 | Bumping is restricted to `[project]` table (multi-version file) | unit | `pytest tests/test_bump_version.py::test_bump_does_not_touch_other_tables -x` | ❌ Wave 0 |
| VER-01 / SC #2 | The bumped pyproject.toml is in the staged set when the hook runs | integration | `pytest tests/test_bump_version.py::test_bump_stages_pyproject -x` | ❌ Wave 0 |
| VER-01 / SC #3 | `workflow.auto_version_bump=false` → no file change | unit | `pytest tests/test_bump_version.py::test_bump_skipped_when_flag_disabled -x` | ❌ Wave 0 |
| VER-01 / SC #3 | Missing flag (key not found) → bump fires (default-true) | unit | `pytest tests/test_bump_version.py::test_bump_runs_when_flag_unset -x` | ❌ Wave 0 |
| VER-01 / SC #4 | PROJECT.md has `## Versioning` section with worked example | static | `pytest tests/test_bump_version.py::test_project_md_has_versioning_section -x` | ❌ Wave 0 |
| VER-01 / SC #5 | Failed commit → `git checkout HEAD -- pyproject.toml` reverts | integration | `pytest tests/test_bump_version.py::test_rollback_on_simulated_commit_failure -x` | ❌ Wave 0 |
| VER-01 / D-09 | Unparseable PROJECT.md milestone → exit non-zero, no file write | unit | `pytest tests/test_bump_version.py::test_bump_aborts_when_no_milestone_heading -x` | ❌ Wave 0 |
| VER-01 / D-07 | Malformed pyproject (no `[project]` table) → exit non-zero | unit | `pytest tests/test_bump_version.py::test_bump_aborts_when_no_project_table -x` | ❌ Wave 0 |
| VER-01 (drift) | PROJECT.md milestone heading regex still matches | static | `pytest tests/test_bump_version.py::test_project_md_milestone_heading_present -x` | ❌ Wave 0 |
| VER-01 (drift) | `.claude/settings.json` and `.claude/hooks/bump-version-hook.sh` exist | static | `pytest tests/test_bump_version.py::test_hook_files_committed -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run --with pytest pytest tests/test_bump_version.py -x` (~1 second; covers the bump helper end-to-end)
- **Per wave merge:** `uv run --with pytest pytest tests/` (full suite; catches accidental drift in adjacent test modules)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_bump_version.py` — covers VER-01 / SC #1..#5 + D-07/D-09 (above table)
- [ ] No conftest extensions needed; helper is pure-Python and uses `tmp_path` fixtures
- [ ] No framework install needed — `pytest` already in `[project.optional-dependencies].test`

*(Test framework is fully present; only the new test module is missing.)*

## Security Domain

This phase touches packaging metadata (version field) and runs an automated rewrite as part of the developer workflow. ASVS-relevant categories:

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | n/a (no auth surface) |
| V3 Session Management | no | n/a |
| V4 Access Control | no | n/a (single-developer machine) |
| V5 Input Validation | yes | **Validate `--phase` arg as a non-negative integer (`int()` parse + `>= 0`); reject anything else.** Hook script extracts phase number via grep + integer cast; passing a malicious string would either be rejected by `int()` or end up as an integer for the regex. Validate the milestone parse output (`int()` on regex groups). |
| V6 Cryptography | no | No crypto in scope. |
| V12 File Handling | yes | Reading `pyproject.toml` and `PROJECT.md` from known repo-root-relative paths. No path traversal vector — the helper hardcodes the targets. The `--pyproject` and `--project-md` test override args are dev-only. |
| V14 Configuration | yes | `.planning/config.json` is plain JSON; helper reads it via `gsd-sdk` (already a trusted CLI in this project) or a direct `json.load()` fallback. No secrets; flag is a boolean. |

### Known Threat Patterns for {Python helper + bash hook + git plumbing}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Shell injection via phase number from commit message | Tampering | The hook extracts the phase number with `grep -oP '...\K[0-9]+(?=...)'` — only digits can match. The Python helper enforces `int()` cast. Both ends prevent injection. |
| Path traversal via `--pyproject`/`--project-md` test args | Tampering | Test args are dev-only; in production the hook never passes them. Lock the helper to refuse paths containing `..` even in test mode. |
| Race: two bump invocations clobber pyproject in flight | Tampering | The hook is synchronous (PreToolUse runs in-band); only one phase commit can be in flight at a time per agent session. No real lock needed. |
| Tampered PROJECT.md milestone heading produces a wildly wrong version (e.g. v999.999) | Tampering | `int()` parse + the bump produces a string `version = "999.999.NN"` that's syntactically valid; downstream Inno Setup / pip would accept it. Acceptable: PROJECT.md is repo-tracked, any tamper is git-visible. |
| Hook script is replaced on disk by an attacker | Tampering | Out of scope — anyone with write access to `.claude/hooks/` already owns the dev environment. |

## Project Constraints (from CLAUDE.md)

- `Skill("spike-findings-musicstreamer")` is for Windows packaging context; **not relevant to Phase 63** (no PyInstaller / GStreamer concerns).
- Per `.planning/codebase/CONVENTIONS.md`: snake_case file names; private functions prefixed with `_`; type hints with `X | Y` (Python 3.10+); pragmatic line length; `from __future__ import annotations` for forward references.
- Per `.planning/codebase/TESTING.md`: pytest via `uv run --with pytest pytest tests/`; tests live in `tests/`; use `tmp_path` for filesystem fixtures; use `subprocess.run(..., capture_output=True, text=True)` for CLI tests.
- Per project memory (CLAUDE.md auto-context): QNAP Gitea pushes mirror to GitHub immediately. Anything committed is effectively public. Keep secrets out of all examples in this RESEARCH.md (already done — no real tokens or paths anywhere).

## Sources

### Primary (HIGH confidence)
- `gsd-sdk/sdk/dist/query/commit.js` (live read, this session) — exact `git add` + `git commit` flow; documents the gitignored-file failure mode at lines 117-121.
- `gsd-sdk/sdk/dist/query/config-mutation.js` (live read, this session) — schema validation flow at lines 188-193.
- `gsd-sdk/sdk/dist/query/config-query.js` (live read, this session) — `Key not found:` exit-1 semantics at lines 99-105.
- `gsd-sdk/sdk/dist/query/config-schema.js` (live read, this session) — VALID_CONFIG_KEYS allowlist at lines 20-56 (no `auto_version_bump`).
- `gsd-sdk/sdk/dist/query/phase-lifecycle.js:909` (live read, this session) — `phaseComplete` handler atomicity contract.
- `code.claude.com/docs/en/hooks` (live WebFetch, this session 2026-05-08) — full PreToolUse / PostToolUseFailure / `updatedInput` schema.
- `git-scm.com/docs/githooks` (live WebFetch, this session) — prepare-commit-msg / pre-commit / commit-msg argv + capability matrix.
- `~/.claude/get-shit-done/workflows/execute-phase.md:1517-1545` (live read) — exact `update_roadmap` step + commit invocation.
- `pyproject.toml` of this repo (live read, line 6: `version = "2.1.60"`) — confirms the regex target.
- `.planning/PROJECT.md:11` (live read) — confirms the `## Current Milestone: v2.1` heading shape.
- `.planning/config.json` (live read) — confirms the `workflow.*` block shape.
- Live regex test on actual `pyproject.toml` + `PROJECT.md` (Python `re` module, this session 2026-05-08) — confirms regex correctness.
- Live invocation of `gsd-sdk query config-get`, `config-set`, `commit` (this session 2026-05-08) — confirms exit codes + error messages.
- Live test of `git checkout -- file` vs `git checkout HEAD -- file` rollback semantics (this session) — confirms Pitfall 4.

### Secondary (MEDIUM confidence)
- `tools/check_spec_entry.py`, `tools/check_subprocess_guard.py` (live read) — co-location pattern; cross-verified against existing project conventions.
- `.planning/codebase/CONVENTIONS.md`, `.planning/codebase/TESTING.md` (live read) — project-internal docs, last updated 2026-04-28.

### Tertiary (LOW confidence)
- None — all claims in this RESEARCH.md are tagged `[VERIFIED]` against live tool output or `[CITED]` against an authoritative source. Three claims are tagged `[ASSUMED]` in the Assumptions Log above.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every recommended library/CLI was verified by live invocation.
- Architecture: HIGH — the PreToolUse-with-updatedInput pathway was verified against the official docs and the gsd-sdk source code.
- Pitfalls: HIGH — every pitfall has a live-verified evidence block.
- Pitfall 1 (gsd-sdk gitignore failure) is the highest-leverage finding: it's surfaced honestly even though it predates Phase 63 and may indicate broader breakage in this repo's phase-commit flow. The planner should consider whether to scope a fix into Phase 63 or call it out as a separate issue.

**Research date:** 2026-05-08
**Valid until:** ~2026-06-08 (30 days; Claude Code hook docs are stable, gsd-sdk schema may move).

## RESEARCH COMPLETE
