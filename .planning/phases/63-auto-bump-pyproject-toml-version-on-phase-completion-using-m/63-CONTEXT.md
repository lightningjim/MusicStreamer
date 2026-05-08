# Phase 63: Auto-Bump pyproject Version on Phase Completion - Context

**Gathered:** 2026-05-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Adopt the `milestone_major.milestone_minor.phase` versioning scheme (e.g. `2.1.63`) and **automate the bump** so the `version` field in `pyproject.toml` is rewritten to `{major}.{minor}.{phase_number}` whenever a phase finishes — bundled into the existing phase-completion commit, gated by a config flag, with safe rollback if the commit fails.

**In scope:**
- A bump mechanism that runs at phase-completion time and rewrites `pyproject.toml`'s `version`
- A new `workflow.auto_version_bump` config flag in `.planning/config.json` (default `true`)
- A `tools/bump_version.py` Python helper (and any companion glue) that performs the actual rewrite
- Updates to `PROJECT.md` documenting the `major.minor.phase` schema with a worked example
- Rollback safety: if the commit fails, the working-tree change to `pyproject.toml` is reverted (no half-state)
- Tests covering: bump correctness, config-gate honoured (true / false), milestone parsed from PROJECT.md, rollback on simulated commit failure

**Out of scope:**
- Modifying the upstream `gsd-sdk` (lives in pnpm dlx cache; not project-owned)
- Auto-tagging git releases or pushing tags
- Republishing/uploading wheels — packaging stays manual
- Touching `__version__` strings inside the `musicstreamer/` package (pyproject is the single source)
- Retroactively bumping past phase commits — current `2.1.60` will be corrected on next phase completion (Phase 63 itself produces `2.1.63`)
- Multi-pyproject monorepo support — single root pyproject only

</domain>

<decisions>
## Implementation Decisions

### Integration Site
- **D-01:** Integration runs as a **Claude Code project-local hook in `.claude/settings.json`**, not as a `gsd-sdk` fork or a global GSD workflow override. Rationale: project-scoped, no SDK fork, no surprise git-hook behavior for users running ad-hoc commits.
- **D-02:** The hook MUST fire **before** the phase-completion commit lands so the bumped `pyproject.toml` is part of the same commit (Success Criterion #2: "no orphaned uncommitted state"). The planner/researcher will pick the exact Claude Code hook event — likely `PreToolUse` matched on `gsd-sdk query commit "docs(phase-NN): complete phase execution"` (or equivalent regex). If `PreToolUse` cannot mutate the underlying command's `--files` list, fallback path is a project-level **`git pre-commit` hook** that pattern-matches the commit message and re-stages `pyproject.toml`. Open implementation question for the planner — both routes are acceptable provided SC#2 holds.
- **D-03:** Bump logic lives in a project-local Python helper at `tools/bump_version.py`, callable as `python tools/bump_version.py --phase NN` (and `--check` / `--dry-run` for tests). Co-locates with existing `tools/check_spec_entry.py` and `tools/check_subprocess_guard.py`.

### Milestone Source
- **D-04:** `{major}.{minor}` is parsed from **`PROJECT.md`'s `## Current Milestone: vX.Y` heading** (regex on `Current Milestone:\s*v(\d+)\.(\d+)`). Single source of truth; PROJECT.md already updates at milestone boundaries via `/gsd-complete-milestone`. Reading from `pyproject.toml` itself was rejected (chicken/egg if version drifted); a separate config setting was rejected (duplication).
- **D-05:** If the heading cannot be parsed, the bump aborts with a non-zero exit and a clear error message — **never silently fall back** to a guessed milestone. The phase-complete commit then proceeds without a bump, and the user is told to fix PROJECT.md.

### Rewrite Mechanism
- **D-06:** Rewrite via **regex on the `version = "..."` line** in `pyproject.toml`. No new dependency (`tomlkit` rejected; `tomllib` is read-only and would still need a regex on write). Rationale: pyproject is hand-formatted, single-line edit, zero comment-loss risk.
- **D-07:** Regex anchors on `^version\s*=\s*"[^"]*"\s*$` within the `[project]` table block (use a lightweight section-aware scan; do NOT match `version` keys in other tables like `[tool.X]` if any appear later). Tests cover: malformed file (no `[project]` table), multiple `version =` lines (must pick the `[project]` one), trailing comments preserved.

### Rollback Shape
- **D-08:** On phase-completion commit failure (pre-commit hook rejection, signing failure, etc.), the bump is rolled back via **`git checkout -- pyproject.toml`** in the same hook flow that performed the bump — the file returns to its pre-bump state (the staged-but-not-committed change is discarded). Satisfies SC#5 ("no half-state").
- **D-09:** If the bump itself errors (e.g., PROJECT.md unparseable, regex no-match), the helper exits non-zero **before any file write**, the original commit proceeds without a bump, and a warning is surfaced. No partial writes.

### Config Flag
- **D-10:** New flag `workflow.auto_version_bump` in `.planning/config.json`, default `true`. Read via `gsd-sdk query config-get workflow.auto_version_bump --raw` (returns `"true"`/`"false"`/`Error: Key not found:` — treat key-not-found as the default `true`).
- **D-11:** When the flag is `false`, the hook short-circuits with a one-line log (`[bump] disabled via workflow.auto_version_bump`) and the phase-complete commit proceeds unmodified. No file touch.

### Documentation
- **D-12:** Add a `## Versioning` section to `PROJECT.md` (placed near `## Constraints`) that documents the `major.minor.phase` schema with a worked example (e.g., "Phase 50 of v2.1 → `2.1.50`") and notes that the bump is automated via `workflow.auto_version_bump`. The schema doc is committed in this phase, not bumped separately.

### Claude's Discretion
- Exact Claude Code hook event/matcher syntax (planner researches against current Claude Code hooks docs)
- Test layout (new `tests/test_bump_version.py` vs folded into existing test module — planner picks)
- Whether the helper accepts phase number as an argument or auto-detects from STATE.md (recommend explicit `--phase` to keep the helper trivially testable)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Spec & Requirements
- `.planning/ROADMAP.md` (Phase 63 entry) — Goal, success criteria, VER-01 mapping. The 5 success criteria are the acceptance test set.
- `.planning/REQUIREMENTS.md` (VER-01) — Active requirement statement.
- `.planning/PROJECT.md` (`## Current Milestone: v2.1 Fixes and Tweaks`) — Authoritative milestone heading; the bump helper parses `{major}.{minor}` from this.

### Existing artifacts the phase will touch
- `pyproject.toml` (line 6: `version = "2.1.60"`) — Current value is two phases stale (last completed: Phase 62). Phase 63's own completion will produce `2.1.63`, retroactively correcting drift.
- `.planning/config.json` — Will gain `workflow.auto_version_bump: true` under the `workflow` block.
- `tools/__init__.py`, `tools/check_spec_entry.py`, `tools/check_subprocess_guard.py` — Co-location pattern for the new `tools/bump_version.py`.

### GSD integration points (read-only — do not modify these files)
- `~/.claude/get-shit-done/workflows/execute-phase.md` §`update_roadmap` (line 1517) — Where `gsd-sdk query phase.complete` and the wrapping `gsd-sdk query commit "docs(phase-NN): complete phase execution"` are invoked. The hook must fire before this commit lands.
- `~/.claude/get-shit-done/workflows/transition.md` — Reference for transition mechanics; not modified by this phase.

### Project conventions
- `.planning/codebase/STACK.md`, `.planning/codebase/STRUCTURE.md`, `.planning/codebase/CONVENTIONS.md` — Project conventions for new tooling helpers.
- `tests/test_media_keys_smtc.py:9,148` — Existing `tomllib` usage pattern (read-only) for reference if tests need to load pyproject.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tools/` Python package with `__init__.py` already exists — drop `bump_version.py` alongside the existing helpers (no new top-level dir needed).
- `tomllib` (Python 3.11+ stdlib) already imported in `tests/test_media_keys_smtc.py` for read-only pyproject inspection — same pattern available for tests of the new helper.
- `gsd-sdk query config-set` / `config-get` already write to `.planning/config.json`'s `workflow.*` namespace (`auto_advance`, `_auto_chain_active` already present) — `auto_version_bump` slots in cleanly.

### Established Patterns
- **Project-local Claude hooks:** Repo currently has no `.claude/settings.json` hooks block — this phase introduces one. Settings file likely needs creation under `.claude/` next to existing `.claude/skills/spike-findings-musicstreamer/`.
- **CLI helpers in `tools/`:** Module-level entry points run via `python tools/<name>.py` (no console_scripts shim); follow the same shape for `bump_version.py`.
- **Test runner:** `pytest` via `uv run --with pytest` — new tests follow that invocation.

### Integration Points
- The bump fires at the `gsd-sdk query commit "docs(phase-NN): complete phase execution" --files .planning/ROADMAP.md .planning/STATE.md .planning/REQUIREMENTS.md ...` boundary inside `execute-phase.md`'s `update_roadmap` step. The hook needs to either (a) prepend the bump and add `pyproject.toml` to the staged set before `git commit` runs, or (b) intercept at git's `pre-commit` level so the bump is part of the same commit object regardless of how the commit was initiated.
- `.planning/config.json`'s existing `workflow` object is the canonical home for the new flag — no new config file.

</code_context>

<specifics>
## Specific Ideas

- The user noted upfront that little discussion was needed — the spec is tight. Decisions D-01 through D-12 lock the gray areas with the user's accepted recommendations; the planner should not re-litigate them.
- Current `pyproject.toml` value `2.1.60` is two behind reality (Phases 61 and 62 completed without bumps). Phase 63's own completion will jump it to `2.1.63`. This jump is expected and acceptable — no retroactive backfill of 61/62 commits.
- Worked example for the new PROJECT.md `## Versioning` section: "Closing Phase 50 of v2.1 yields `version = \"2.1.50\"`; closing Phase 63 yields `2.1.63`. The leading `2.1` comes from `## Current Milestone: v2.1` in this file."

</specifics>

<deferred>
## Deferred Ideas

- **Auto-tagging git releases on milestone completion** — out of scope for VER-01; would be a separate phase keyed off `/gsd-complete-milestone` rather than `phase.complete`.
- **Pushing tags / publishing wheels** — manual packaging stays manual; revisit if PyPI distribution ever becomes a goal.
- **`__version__` exposure inside the `musicstreamer/` package** — pyproject is the single source for v2.1; if a runtime version string is ever needed, that's a follow-up phase.
- **Retroactive backfill of Phase 61 / 62 commits** — the version drift heals on next phase completion (Phase 63 → `2.1.63`); rewriting history was rejected as not worth the disruption.

</deferred>

---

*Phase: 63-Auto-Bump pyproject Version on Phase Completion*
*Context gathered: 2026-05-08*
