# Phase 63: Auto-Bump pyproject Version on Phase Completion - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-08
**Phase:** 63-auto-bump-pyproject-toml-version-on-phase-completion
**Areas discussed:** Integration site, Milestone source, Rewrite mechanism, Rollback shape

User opened the session with: *"I'm not sure if there is much discussion needed here"*. The spec from ROADMAP.md was tight (5 explicit success criteria, single VER-01 requirement), so the gray areas were presented as a single multi-select with strong recommendations. User answered: *"All recommends for 1-4 look good"*, locking all four decisions to the recommended option in one turn.

---

## Integration site

| Option | Description | Selected |
|--------|-------------|----------|
| Claude Code project-local hook | Hook in `.claude/settings.json` (PreToolUse on Bash matched on phase-complete commit pattern). Survives across sessions, no SDK fork, no surprise git-hook behavior. | ✓ |
| In-repo git pre-commit hook | Pattern-match commit message at git layer; works regardless of how the commit was initiated, but pre-commit hooks are easier to miss / harder to surface to the user. | |
| Workflow-override `python tools/bump_version.py` | Explicit call wired into a workflow override; cleanest signal but requires forking `~/.claude/.../execute-phase.md` per project. | |

**User's choice:** Option 1 (Claude Code project-local hook).
**Notes:** Decision captured as D-01/D-02. Open implementation question routed to the planner: if `PreToolUse` cannot mutate `--files`, fall back to a project-level `git pre-commit` hook that pattern-matches the commit message. Either route satisfies SC#2 if implemented correctly.

---

## Milestone source

| Option | Description | Selected |
|--------|-------------|----------|
| PROJECT.md heading parse | Regex on `## Current Milestone: vX.Y` — single source of truth, already maintained at milestone boundaries by `/gsd-complete-milestone`. | ✓ |
| Reuse pyproject's existing first two segments | Brittle: chicken/egg if version ever drifts to a wrong major.minor. | |
| Explicit `.planning/config.json` setting | Adds duplication; another field to keep in sync with PROJECT.md. | |

**User's choice:** Option 1 (PROJECT.md heading parse).
**Notes:** Decisions D-04 and D-05 — abort on parse failure rather than silently fall back.

---

## Rewrite mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Regex on `^version = "..."` | No new dependency, single-line edit, zero comment-loss risk on hand-formatted pyproject. | ✓ |
| `tomllib` read + regex write | `tomllib` is read-only; would still need a regex for the write half. No real benefit over plain regex. | |
| Add `tomlkit` for round-trip | New dependency for one line of TOML mutation. Overkill. | |

**User's choice:** Option 1 (regex).
**Notes:** D-06 / D-07 — anchor on the `[project]` table to avoid accidental matches in `[tool.X]` tables.

---

## Rollback shape

| Option | Description | Selected |
|--------|-------------|----------|
| `git checkout -- pyproject.toml` on commit failure | Returns file to pre-bump state; only mechanism that satisfies SC#5 ("no half-state"). | ✓ |
| Leave file dirty for user inspection | User has to manually clean up; violates SC#5. | |
| Separate post-commit bump+commit | Produces an orphan commit; violates SC#2 ("bundled with phase-completion commit"). | |

**User's choice:** Option 1 (checkout-on-failure).
**Notes:** D-08 / D-09 — also abort cleanly if the bump itself errors before any file write.

---

## Claude's Discretion

- Exact Claude Code hook event/matcher syntax (planner will research current Claude Code hooks docs).
- Test layout — new `tests/test_bump_version.py` vs folded into existing module.
- Whether the helper accepts phase number explicitly via `--phase NN` or auto-detects from STATE.md (recommendation: explicit, for testability).

## Deferred Ideas

- Auto-tagging git releases on milestone completion — separate phase keyed off `/gsd-complete-milestone`.
- Pushing tags / publishing wheels — packaging stays manual.
- Exposing `__version__` inside the `musicstreamer/` package — pyproject is the v2.1 single source.
- Retroactive backfill of Phase 61 / 62 commits — drift heals at Phase 63 close.
