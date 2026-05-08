---
phase: 63
plan: 02
subsystem: tooling
tags: [version-bump, config-flag, gsd-sdk, tdd, wave-2]
requires:
  - "tools/bump_version.py from Plan 01 (parse_milestone, rewrite_pyproject_version, main)"
provides:
  - "tools/bump_version.py::is_auto_bump_enabled(repo_root: Path) -> bool"
  - "tools/bump_version.py::main() honoring workflow.auto_version_bump (D-11 short-circuit returns 3)"
  - ".planning/config.json::workflow.auto_version_bump = true (default-on per D-10)"
  - "Exit code 3 vocabulary: actively used (was reserved in Plan 01)"
affects:
  - "tools/bump_version.py (added subprocess import + is_auto_bump_enabled + gate in main)"
  - "tests/test_bump_version.py (5 → 7 tests; appended only)"
  - ".planning/config.json (one new key in workflow block)"
tech-stack:
  added: []
  patterns:
    - "subprocess.run([\"gsd-sdk\", \"query\", \"config-get\", ...]) — Code Example 3 from RESEARCH §"
    - "monkeypatch.setenv(\"PATH\", f\"{tmp_path}{os.pathsep}{...}\") — stub binary on PATH (PATTERNS §monkeypatch fixture style)"
    - "tmp_path-resident /bin/sh stub script (chmod 0o755) for subprocess fakes"
    - "Direct JSON round-trip edit of .planning/config.json (Pitfall 3 — `gsd-sdk query config-set` rejects unknown keys)"
key-files:
  created: []
  modified:
    - "tools/bump_version.py (151 → 175 LOC; +24 lines for is_auto_bump_enabled + gate)"
    - "tests/test_bump_version.py (162 → 260 LOC; +98 lines for 2 new tests + os import)"
    - ".planning/config.json (workflow block gains auto_version_bump: true)"
decisions:
  - "Direct JSON round-trip used to seed .planning/config.json (Pitfall 3 verified live: `gsd-sdk query config-set workflow.auto_version_bump true` exits 10 with `Unknown config key`)."
  - "is_auto_bump_enabled fails OPEN on any non-zero subprocess exit (D-10 default-true): the disabled state is reachable ONLY by an explicit `false` in config.json. Transient SDK errors will not silently disable bumping."
  - "Gate sits AFTER --phase guard, BEFORE milestone parse: the V5 input check still gets to reject negative phases even when the flag is disabled (preserves Plan 01's exit-1 vocabulary)."
metrics:
  duration: "4m3s"
  completed: "2026-05-08"
  tasks: 2
  files_created: 0
  files_modified: 3
  tests_added: 2
  tests_passing: 7
---

# Phase 63 Plan 02: Auto-Version-Bump Opt-Out Flag Summary

Added the `workflow.auto_version_bump` config flag (default `true`) and wired `tools/bump_version.py` to honor it via a `gsd-sdk query config-get` lookup, gated short-circuit returns 3 with an informational stderr line and zero file writes.

## What Shipped

**`tools/bump_version.py` — new helper + gate (15 lines added):**

- `is_auto_bump_enabled(repo_root: Path) -> bool` shells out to `gsd-sdk query config-get workflow.auto_version_bump --raw`. Returns `True` when stdout (stripped) is `"true"` OR the subprocess exited non-zero (D-10 default-true on `Error: Key not found:` and any other SDK error). Returns `False` only when stdout is exactly `"false"`. Fails open by design — a transient SDK error will not silently disable bumping.
- New `import subprocess` at module top.
- Gate landed in `main()` immediately after the `if args.phase < 0:` guard and before `repo = _repo_root()`. When disabled: prints `[bump] disabled via workflow.auto_version_bump` to stderr and returns 3 (D-11 short-circuit, informational not failure).
- Module docstring exit-codes block updated: code 3 is now active ("informational, not a hard failure") rather than reserved.

**`.planning/config.json` — flag seeded via direct JSON round-trip:**

```bash
python3 -c '
import json
p = ".planning/config.json"
with open(p) as f: data = json.load(f)
data["workflow"]["auto_version_bump"] = True
with open(p, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
'
```

The `workflow` block now reads (preserving 2-space indent, trailing newline, all sibling keys):

```json
"workflow": {
  "research": true,
  "plan_check": true,
  "verifier": true,
  "nyquist_validation": true,
  "_auto_chain_active": true,
  "auto_advance": false,
  "auto_version_bump": true
}
```

Live verification: `gsd-sdk query config-get workflow.auto_version_bump --raw` returns `true` and exits 0.

**Pitfall 3 honored:** `gsd-sdk query config-set workflow.auto_version_bump true` was NEVER invoked. Live attempt during RESEARCH confirmed it exits 10 with `Error: Unknown config key: "workflow.auto_version_bump". Did you mean: workflow.auto_advance?`. The SDK's `VALID_CONFIG_KEYS` allowlist (`config-schema.js:20-56`) does not include `auto_version_bump`. Direct JSON edit was the only viable route.

**`tests/test_bump_version.py` — 2 new tests appended (98 lines):**

| # | Test | Purpose |
|---|------|---------|
| 6 | `test_bump_skipped_when_flag_disabled` | D-11 — stub `gsd-sdk` on PATH returns `"false"`; helper exits 3 with stderr disabled-marker; pyproject is byte-identical pre/post (no write). |
| 7 | `test_bump_runs_when_flag_unset` | D-10 — stub `gsd-sdk` mimics live `Error: Key not found:` exit 1; helper treats absence as default-true and bump fires (`version = "3.7.42"` lands in pyproject). |

Stub pattern (verbatim from RESEARCH §Code Example 6 and §`tests/test_desktop_install.py` monkeypatch idiom):

```python
fake_sdk = tmp_path / "gsd-sdk"
fake_sdk.write_text(
    '#!/bin/sh\n'
    'if [ "$1 $2 $3" = "query config-get workflow.auto_version_bump" ]; then\n'
    '  echo false; exit 0\n'  # or "Error: Key not found: ..." 1>&2; exit 1
    'fi\n'
    'exit 99\n',
    encoding="utf-8",
)
fake_sdk.chmod(0o755)
monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
```

Both tests use the existing Plan 01 `_invoke_bump(...)` helper — single subprocess invocation point (Pitfall 7 mitigation).

`import os` was added to support `os.pathsep` in the PATH manipulation; everything else (`subprocess`, `sys`, `tomllib`, `re`, `Path`) was already imported by Plan 01.

## TDD Gate Compliance

- **RED commit (5cca704):** `test(63-02): add failing tests for auto_version_bump flag gate (RED)` — `test_bump_skipped_when_flag_disabled` failed with `assert 0 == 3` (helper had no gate; bump ran and returned 0 instead of short-circuiting with 3). The "default-true" test passed accidentally because the gate was absent — bump always fired.
- **GREEN commit (8dfe0b5):** `feat(63-02): wire workflow.auto_version_bump gate into bump_version (GREEN)` — both new tests pass; all 7 tests green in 1.27s.
- **REFACTOR:** Not needed — implementation is direct from RESEARCH §Code Example 3 reference, no cleanup pass added value.

Gate sequence: RED `test(...)` commit → GREEN `feat(...)` commit. Compliant.

## Verification Evidence

```
$ uv run --with pytest pytest tests/test_bump_version.py
========================= 7 passed, 1 warning in 1.27s =========================

$ python3 -m json.tool .planning/config.json > /dev/null && echo OK
OK

$ gsd-sdk query config-get workflow.auto_version_bump --raw
true
EXIT:0

$ python tools/bump_version.py --phase 0 --dry-run
[bump] would rewrite /home/kcreasey/OneDrive/Projects/MusicStreamer/pyproject.toml version to 2.1.0
EXIT:0

$ git diff pyproject.toml
(empty — no live writes)
```

All 5 plan-level success criteria satisfied:

- [x] `.planning/config.json` has `workflow.auto_version_bump: true` — verified by `gsd-sdk query config-get workflow.auto_version_bump --raw` returning `true`/exit 0.
- [x] `tools/bump_version.py` has `is_auto_bump_enabled(repo_root)` and a gate in `main()` returning 3 when the flag is `false` — verified by `test_bump_skipped_when_flag_disabled` GREEN.
- [x] 7 tests GREEN in `tests/test_bump_version.py` (5 from Plan 01 + 2 new; no regression).
- [x] No `gsd-sdk query config-set` invocation in any commit — Pitfall 3 boundary respected.
- [x] `pyproject.toml` is byte-identical pre/post plan execution — `git diff pyproject.toml` is empty.

## Plan 03 Hand-Off Surface

Plan 03 wires the Claude Code `PreToolUse` hook to invoke this helper. The contract Plan 03 will rely on:

- **CLI shape (unchanged from Plan 01):** `python tools/bump_version.py --phase <N>` from the repo root.
- **New gate behavior (this plan):** When `workflow.auto_version_bump` is `false`, the helper exits 3 silently (stderr-only log). Plan 03's hook MUST treat exit 3 as a **non-blocking opt-out** — the phase-completion commit proceeds unmodified, no error surfaced to the user beyond the one-line log.
- **Default-true semantics:** With the flag set to `true` (this plan's seeded value), the helper proceeds through to the rewrite step exactly as Plan 01 designed — Plan 03's hook sees the same exit-0 / exit-1 vocabulary as before.
- **Stub mocking pattern:** Plan 04 (rollback testing) and beyond can copy the `monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}...")` + `chmod 0o755` shell stub idiom established here.

## Deviations from Plan

**One observation, not a deviation:** The `_auto_chain_active: true` value was already modified in `.planning/config.json` at the start of this plan (the orchestrator flips it during auto-chained runs). It rode along in the Task 2 commit since both keys are siblings in the same `workflow` block. The commit message documents this explicitly. No code change resulted; the `_auto_chain_active` flip is the orchestrator's runtime state, not Plan 02 work.

No Rule 1/2/3 auto-fixes were needed during implementation. The plan's task actions were followed verbatim.

## Test Count + Status

- **Tests added this plan:** 2 (`test_bump_skipped_when_flag_disabled`, `test_bump_runs_when_flag_unset`).
- **Tests passing:** 7/7 (5 from Plan 01 + 2 new).
- **Runtime:** 1.27s (well under the <1s-per-test budget; whole module ~1.3s).
- **No regressions:** the 5 Plan 01 tests stay GREEN — the gate sits AFTER the V5 phase guard and BEFORE the milestone parse, so the abort-paths from Plan 01 still trigger correctly when the flag is true (the default).

## Commits

- `5cca704` — `test(63-02): add failing tests for auto_version_bump flag gate (RED)`
- `8dfe0b5` — `feat(63-02): wire workflow.auto_version_bump gate into bump_version (GREEN)`

## Self-Check: PASSED

- `tools/bump_version.py` exists (175 LOC) and contains `def is_auto_bump_enabled` + `import subprocess` + `return 3` + `disabled via workflow.auto_version_bump` — confirmed.
- `tests/test_bump_version.py` exists (260 LOC) with 7 `def test_*` functions — confirmed.
- `.planning/config.json` is valid JSON (`python3 -m json.tool` exits 0) and contains `"auto_version_bump": true` — confirmed.
- Commit `5cca704` (RED scaffold) on `main` — confirmed via `git log --oneline | grep 5cca704`.
- Commit `8dfe0b5` (GREEN gate) on `main` — confirmed via `git log --oneline | grep 8dfe0b5`.
- `uv run --with pytest pytest tests/test_bump_version.py` — 7/7 GREEN — confirmed.
- `gsd-sdk query config-get workflow.auto_version_bump --raw` returns `true` and exits 0 — confirmed.
- `python tools/bump_version.py --phase 0 --dry-run` exits 0 with the gate-passes-through dry-run path — confirmed.
- `git diff pyproject.toml` empty (no live writes) — confirmed.
- No `gsd-sdk query config-set` invocation in any Plan 02 commit — confirmed by `git log --all -p | grep -c "config-set workflow.auto_version_bump"` returning 0.
