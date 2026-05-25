---
phase: 63
plan: 01
subsystem: tooling
tags: [version-bump, pyproject, regex-rewrite, tdd, wave-0]
requires: []
provides:
  - "tools/bump_version.py::parse_milestone(project_md: str) -> tuple[int, int] | None"
  - "tools/bump_version.py::rewrite_pyproject_version(content: str, new_version: str) -> str | None"
  - "tools/bump_version.py::main() -> int (argparse: --phase, --pyproject, --project-md, --dry-run, --check)"
  - "tests/test_bump_version.py::_invoke_bump (subprocess test surface — same as the hook)"
  - "Exit code vocabulary: 0=success/dry-run, 1=parse error, 3=config disabled (reserved for Plan 02)"
affects:
  - "tools/ (new module added; check_subprocess_guard.py / check_spec_entry.py untouched)"
  - "tests/ (new module added; no other test files touched)"
tech-stack:
  added: []
  patterns:
    - "stdlib-only Python helper (no tomlkit/tomllib runtime dep — D-06)"
    - "section-aware regex rewrite (RESEARCH §Pattern 3 — verified live)"
    - "subprocess.run([sys.executable, ...]) test surface mirroring the hook (Pitfall 7)"
    - "from __future__ import annotations + encoding=\"utf-8\" file I/O (project convention)"
key-files:
  created:
    - "tools/bump_version.py (151 LOC)"
    - "tests/test_bump_version.py (162 LOC)"
  modified: []
decisions:
  - "Exit code 3 reserved (not used in this plan) for Plan 02's `is_auto_bump_enabled()` short-circuit."
  - "Phase < 0 rejected at argparse layer with stderr FAIL + exit 1 (V5 input validation)."
  - "Test surface drift mitigation (Pitfall 7): single `_invoke_bump` helper centralizes the subprocess call signature so tests and the live hook share one shape."
metrics:
  duration: "3m9s"
  completed: "2026-05-08"
  tasks: 2
  files_created: 2
  files_modified: 0
  tests_added: 5
  tests_passing: 5
---

# Phase 63 Plan 01: Bump Helper + Wave 0 Test Scaffold Summary

Section-aware pyproject.toml version rewriter (`tools/bump_version.py`) plus a 5-test scaffold (`tests/test_bump_version.py`) that locks the contract Plans 02–05 will extend.

## What Shipped

**`tools/bump_version.py`** — pure-stdlib Python helper that:

- Parses `(major, minor)` from `.planning/PROJECT.md`'s `## Current Milestone: vX.Y` heading via `_MILESTONE_RE`.
- Locates the `[project]` table in `pyproject.toml` via `_PROJECT_TABLE_RE`, scans to the next `^[` table boundary via `_NEXT_TABLE_RE`, and rewrites exactly one `version = "..."` line within that scope via `_VERSION_LINE_RE`.
- Refuses to write the file if any of the parse steps fails (D-09 — no partial writes).
- argparse surface: `--phase NN` (required, `int >= 0`), `--pyproject` and `--project-md` overrides (test-only per Pitfall 7), `--dry-run`, `--check` (alias of `--dry-run`).
- Text-mode I/O with explicit `encoding="utf-8"` on every read/write (Pitfall 6 — CRLF safety).

**`tests/test_bump_version.py`** — 5 tests:

| # | Test | Purpose |
|---|------|---------|
| 1 | `test_bump_rewrites_version_within_project_block` | SC #1 happy path — bump rewrites `version = "0.0.0"` to `"3.7.42"` and the rewritten file still parses as TOML (`tomllib.load` belt-and-braces). |
| 2 | `test_bump_does_not_touch_other_tables` | D-07 — sibling `[tool.poetry] version = "9.9.9"` stays byte-identical (occurrence count == 1). |
| 3 | `test_bump_aborts_when_no_project_table` | D-07/D-09 — missing `[project]` table → exit non-zero, file byte-identical. |
| 4 | `test_bump_aborts_when_no_milestone_heading` | D-05/D-09 — missing `## Current Milestone:` heading → exit non-zero, file byte-identical. |
| 5 | `test_project_md_milestone_heading_present` | Pitfall 2 drift-guard — live `.planning/PROJECT.md` carries the canonical heading. |

All 5 GREEN under `uv run --with pytest pytest tests/test_bump_version.py` in ~0.25s.

## Final Exit-Code Vocabulary

Documented in the helper's module docstring:

| Code | Meaning | Triggered By |
|------|---------|--------------|
| 0 | Success, or dry-run completed | Successful rewrite OR `--dry-run` / `--check` after all parses succeed |
| 1 | Parse error | `--phase < 0`, missing/unparseable `## Current Milestone: vX.Y`, missing `[project]` table, no parseable `version` line in `[project]`, OR file-read OSError |
| 3 | Config disabled (reserved) | **Not used in this plan.** Plan 02 will return 3 from a `is_auto_bump_enabled()` short-circuit when `workflow.auto_version_bump` is `false` (D-11). |

Code 2 was discussed in the plan as "regex no-match in version line (reserved; folded into 1 if simpler)" — folded into 1 as planned. Helper currently returns only {0, 1}.

## Deviations from RESEARCH-Verbatim Regex

**None.** All four module-level regexes (`_PROJECT_TABLE_RE`, `_NEXT_TABLE_RE`, `_VERSION_LINE_RE`, `_MILESTONE_RE`) are copied byte-identical from RESEARCH §Pattern 3 and §Pattern 4. Live verification during this plan confirmed they still match the actual repo content (pyproject.toml line 7 `version = "2.1.60"`; PROJECT.md line 11 `## Current Milestone: v2.1 Fixes and Tweaks`).

## Deviations from Plan

**None.** Both tasks executed exactly as written. No Rule 1/2/3 auto-fixes were needed during implementation. The minor "3 passed, 2 failed" intermediate state during Task 1 RED verification was expected behavior — `subprocess.run([sys.executable, "<missing-script>"])` returns exit code 2, which makes the abort-path tests "pass" their `returncode != 0` assertion as a happy accident; once the helper landed in Task 2, the abort-path tests started passing for the correct reason (helper returns 1 with a FAIL message). No code change needed.

## Plan 02 Hand-Off Surface

The helper does **not** currently read `.planning/config.json`. Plan 02 will introduce the `is_auto_bump_enabled()` slot that:

- Reads `workflow.auto_version_bump` via `gsd-sdk query config-get workflow.auto_version_bump --raw` (RESEARCH §Code Example 3).
- Treats "key not found" (gsd-sdk exit 1, missing key per D-10) as default-true.
- Returns exit code 3 from `main()` when the flag is `false` (the helper short-circuits without writing).

This contract is documented in the helper's module docstring under the `Exit codes:` block (`3 — config disabled (D-11 short-circuit; reserved for Plan 02 wiring; this plan never returns 3)`). No source code change is needed in this plan to reserve the slot — the docstring is authoritative.

## Test Count + Status

- **Tests added this plan:** 5
- **Tests passing:** 5/5 (RED → GREEN over 2 commits)
- **Runtime:** ~0.25s
- **No regressions** in adjacent test modules (helper is self-contained; touches no production source under `musicstreamer/`).

## Commits

- `531cba4` — `test(63-01): add bump_version test scaffold (Wave 0 RED)`
- `9c0cda8` — `feat(63-01): implement bump_version helper (Wave 0 GREEN)`

## Self-Check: PASSED

- `tools/bump_version.py` exists (151 LOC) — confirmed.
- `tests/test_bump_version.py` exists (162 LOC) — confirmed.
- Commit `531cba4` (test scaffold) on `main` — confirmed.
- Commit `9c0cda8` (helper implementation) on `main` — confirmed.
- All 5 tests green under `uv run --with pytest pytest tests/test_bump_version.py` — confirmed.
- `python tools/bump_version.py --phase 0 --dry-run` exits 0 with `[bump] would rewrite ... version to 2.1.0` — confirmed.
- `python tools/bump_version.py --phase -1 --dry-run` exits 1 with `[bump] FAIL: --phase must be >= 0, got -1` — confirmed.
- `git diff pyproject.toml` empty (no live writes) — confirmed.
- `git diff .planning/PROJECT.md` empty — confirmed.
