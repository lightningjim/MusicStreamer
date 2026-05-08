"""Phase 63 (VER-01) — bump_version helper test suite.

Covers SC #1 (rewrite happy path) + D-07 ([project] scope) + D-09 (no partial
writes on parse error) + Pitfall 2 (drift-guard against PROJECT.md milestone
heading reformat). Plans 02-05 extend this module with config-gate, hook
wiring, rollback, and PROJECT.md ## Versioning section tests.

Runtime budget: <1s for the whole module per RESEARCH §Validation Architecture.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest


def _repo_root() -> Path:
    # tests/test_bump_version.py -> repo root is parent.parent.
    return Path(__file__).resolve().parent.parent


def _invoke_bump(*, pyproject: Path, project_md: Path, phase: int) -> subprocess.CompletedProcess:
    """Mirror exactly how the Phase 63 hook will invoke the helper.

    Single point of subprocess invocation (Pitfall 7 mitigation): tests and
    the live hook both go through `python tools/bump_version.py --phase NN
    --pyproject ... --project-md ...`. If argparse defaults drift on either
    side, the drift surfaces here first.
    """
    return subprocess.run(
        [
            sys.executable,
            str(_repo_root() / "tools" / "bump_version.py"),
            "--phase", str(phase),
            "--pyproject", str(pyproject),
            "--project-md", str(project_md),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_bump_rewrites_version_within_project_block(tmp_path):
    """SC #1: bumping rewrites version = "M.m.NN" within [project]."""
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

    result = _invoke_bump(pyproject=pyproject, project_md=project_md, phase=42)

    assert result.returncode == 0, result.stderr
    body = pyproject.read_text(encoding="utf-8")
    assert 'version = "3.7.42"' in body
    # D-07: [tool.poetry] version is byte-untouched.
    assert 'version = "9.9.9"' in body

    # Belt-and-braces: the rewritten file still parses cleanly as TOML and the
    # parsed [project].version matches what we wrote.
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    assert data["project"]["version"] == "3.7.42"


def test_bump_does_not_touch_other_tables(tmp_path):
    """D-07: section-aware rewrite — only the [project] table is touched.

    The [tool.poetry] version = "9.9.9" line MUST appear exactly once,
    byte-identical to the pre-invocation value.
    """
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

    result = _invoke_bump(pyproject=pyproject, project_md=project_md, phase=42)

    assert result.returncode == 0, result.stderr
    body = pyproject.read_text(encoding="utf-8")
    # Exactly one occurrence — proving [tool.poetry].version is untouched.
    assert body.count('version = "9.9.9"') == 1


def test_bump_aborts_when_no_project_table(tmp_path):
    """D-07/D-09: missing [project] table -> exit non-zero, no file write."""
    pyproject = tmp_path / "pyproject.toml"
    original = '[build-system]\nrequires = []\n'
    pyproject.write_text(original, encoding="utf-8")
    project_md = tmp_path / "PROJECT.md"
    project_md.write_text(
        "# Test\n\n## Current Milestone: v3.7 Some Words\n\n",
        encoding="utf-8",
    )

    result = _invoke_bump(pyproject=pyproject, project_md=project_md, phase=42)

    assert result.returncode != 0, (
        f"expected non-zero exit; got 0 with stdout={result.stdout!r}"
    )
    # D-09: no partial writes on error.
    assert pyproject.read_text(encoding="utf-8") == original


def test_bump_aborts_when_no_milestone_heading(tmp_path):
    """D-05/D-09: missing ## Current Milestone heading -> exit non-zero, no write."""
    pyproject = tmp_path / "pyproject.toml"
    original = '[project]\nversion = "1.0.0"\n'
    pyproject.write_text(original, encoding="utf-8")
    project_md = tmp_path / "PROJECT.md"
    project_md.write_text("# No milestone here\n", encoding="utf-8")

    result = _invoke_bump(pyproject=pyproject, project_md=project_md, phase=42)

    assert result.returncode != 0, (
        f"expected non-zero exit; got 0 with stdout={result.stdout!r}"
    )
    # D-09: no partial writes on error.
    assert pyproject.read_text(encoding="utf-8") == original


def test_project_md_milestone_heading_present():
    """Pitfall 2 drift-guard: live PROJECT.md must carry the canonical heading.

    Failure mode: someone reformats `## Current Milestone: v2.1 Fixes...` into
    `## Milestone (current): v2.1` or `### Current Milestone:` and the bump
    helper silently aborts on every phase commit. This test fails LOUD before
    the hook ever runs.
    """
    project_md = _repo_root() / ".planning" / "PROJECT.md"
    text = project_md.read_text(encoding="utf-8")
    match = re.search(r'^##\s+Current Milestone:\s*v\d+\.\d+', text, re.MULTILINE)
    assert match, (
        f"Phase 63 drift: expected `## Current Milestone: vX.Y` at the start of "
        f"a line in {project_md}. "
        f"Found these `## ...Milestone...` lines instead: "
        f"{[ln for ln in text.splitlines() if 'Milestone' in ln][:5]}"
    )


def test_bump_skipped_when_flag_disabled(tmp_path, monkeypatch):
    """D-11: when workflow.auto_version_bump is "false", helper short-circuits.

    Stub `gsd-sdk` on PATH so the helper's `is_auto_bump_enabled()` reads
    "false" and the bump path never runs. Asserts:
      - exit code 3 (D-11 short-circuit, informational not failure)
      - stderr carries the "[bump] disabled via workflow.auto_version_bump" line
      - pyproject.toml is byte-identical pre/post invocation (no write)
    """
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\n'
        'name = "test"\n'
        'version = "0.0.0"\n',
        encoding="utf-8",
    )
    project_md = tmp_path / "PROJECT.md"
    project_md.write_text(
        "# Test\n\n## Current Milestone: v3.7 Some Words\n\n",
        encoding="utf-8",
    )

    fake_sdk = tmp_path / "gsd-sdk"
    fake_sdk.write_text(
        '#!/bin/sh\n'
        'if [ "$1 $2 $3" = "query config-get workflow.auto_version_bump" ]; then\n'
        '  echo false; exit 0\n'
        'fi\n'
        'exit 99\n',
        encoding="utf-8",
    )
    fake_sdk.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")

    pre_bytes = pyproject.read_bytes()
    result = _invoke_bump(pyproject=pyproject, project_md=project_md, phase=42)

    assert result.returncode == 3, (
        f"expected exit 3 (D-11 short-circuit); got {result.returncode} "
        f"with stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "disabled via workflow.auto_version_bump" in result.stderr, (
        f"expected the disabled-stderr marker; got stderr={result.stderr!r}"
    )
    # Strictest no-write assertion: byte-identical pre/post.
    assert pyproject.read_bytes() == pre_bytes, (
        "pyproject.toml was modified despite the flag being disabled"
    )


def test_bump_runs_when_flag_unset(tmp_path, monkeypatch):
    """D-10: when the key is absent (gsd-sdk exit 1), bump fires (default-true).

    Stub `gsd-sdk` to mimic the live SDK's "Error: Key not found:" exit-1
    response. The helper MUST treat this as default-true and proceed with
    the rewrite. Asserts:
      - exit code 0
      - pyproject.toml contains 'version = "3.7.42"' (bump fired)
    """
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\n'
        'name = "test"\n'
        'version = "0.0.0"\n',
        encoding="utf-8",
    )
    project_md = tmp_path / "PROJECT.md"
    project_md.write_text(
        "# Test\n\n## Current Milestone: v3.7 Some Words\n\n",
        encoding="utf-8",
    )

    fake_sdk = tmp_path / "gsd-sdk"
    fake_sdk.write_text(
        '#!/bin/sh\n'
        'if [ "$1 $2 $3" = "query config-get workflow.auto_version_bump" ]; then\n'
        '  echo "Error: Key not found: workflow.auto_version_bump" 1>&2; exit 1\n'
        'fi\n'
        'exit 99\n',
        encoding="utf-8",
    )
    fake_sdk.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")

    result = _invoke_bump(pyproject=pyproject, project_md=project_md, phase=42)

    assert result.returncode == 0, (
        f"expected exit 0 (default-true on key-not-found); got "
        f"{result.returncode} with stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    body = pyproject.read_text(encoding="utf-8")
    assert 'version = "3.7.42"' in body, (
        f"expected bump to fire under default-true; got body={body!r}"
    )


def test_hook_files_committed():
    """Phase 63 Plan 03: .claude/settings.json + .claude/hooks/bump-version-hook.sh

    must exist and be tracked. Top-level .claude/ is gitignored so a careless
    `git add` would silently miss them — drift-guard fails loud (Pitfall 8).
    """
    repo = _repo_root()
    settings = repo / ".claude" / "settings.json"
    hook = repo / ".claude" / "hooks" / "bump-version-hook.sh"
    assert settings.exists(), (
        f"Phase 63 drift: expected {settings}; "
        f"found in .claude/: "
        f"{sorted(p.name for p in (repo / '.claude').iterdir())}"
    )
    assert hook.exists(), (
        f"Phase 63 drift: expected {hook}; "
        f"found in .claude/hooks/: "
        f"{sorted(p.name for p in (repo / '.claude' / 'hooks').iterdir()) if (repo / '.claude' / 'hooks').exists() else 'directory missing'}"
    )
    assert os.access(hook, os.X_OK), f"{hook} must be executable (chmod 0755)"


def test_bump_stages_pyproject(tmp_path):
    """SC #2 (integration, mechanism): the PreToolUse hook script appends

    pyproject.toml to the upcoming `gsd-sdk query commit` --files list, so
    the bumped file lands in the same commit object as the .planning/ files.

    This test proves the hook MECHANISM. Plan 05's final task adds a
    complementary outcome-level gate (`test_phase_63_self_completion_*`)
    that runs against the live Phase 63 commit object once it exists —
    Warning 4 Option A.
    """
    if shutil.which("jq") is None:
        pytest.skip("jq not available — hook integration cannot run")

    # Build a fake repo so `git add pyproject.toml` doesn't touch the real one.
    fake_repo = tmp_path / "fake_repo"
    fake_repo.mkdir()
    (fake_repo / "pyproject.toml").write_text(
        '[project]\nname = "fake"\nversion = "0.0.0"\n', encoding="utf-8"
    )
    # Stub bump_version.py: do nothing, exit 0 (we're testing the hook, not the helper).
    (fake_repo / "tools").mkdir()
    (fake_repo / "tools" / "bump_version.py").write_text(
        "#!/usr/bin/env python3\nimport sys\nsys.exit(0)\n", encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q"], cwd=fake_repo, check=True)
    subprocess.run(["git", "-C", str(fake_repo), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(fake_repo), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
        check=True,
    )

    repo = _repo_root()
    hook = repo / ".claude" / "hooks" / "bump-version-hook.sh"

    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {
            "command": 'gsd-sdk query commit "docs(phase-63): complete phase execution" --files foo.md'
        },
    })
    result = subprocess.run(
        ["bash", str(hook)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=15,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(fake_repo)},
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["hookSpecificOutput"]["permissionDecision"] == "allow"
    new_cmd = data["hookSpecificOutput"]["updatedInput"]["command"]
    assert new_cmd.endswith(" pyproject.toml"), (
        f"Expected hook to append ' pyproject.toml' to the command; got: {new_cmd!r}"
    )


def test_rollback_on_simulated_commit_failure(tmp_path):
    """SC #5 / VALIDATION row 63-04-01: when a phase-completion commit fails,
    the PostToolUseFailure rollback hook reverts pyproject.toml to HEAD —
    both index and working tree — using the SINGLE-COMMAND form
    `git checkout HEAD -- pyproject.toml` (RESEARCH §Pitfall 4: D-08's literal
    `git checkout -- pyproject.toml` is a NO-OP against staged changes).

    Negative case (same test): a non-phase-completion commit failure is a
    no-op pass-through — the staged bump is preserved.
    """
    if shutil.which("jq") is None:
        pytest.skip("jq not available — rollback hook integration cannot run")

    # --- Build a fake repo with a known HEAD ----------------------------------
    fake_repo = tmp_path / "fake_repo"
    fake_repo.mkdir()
    original_pyproject = '[project]\nname = "fake"\nversion = "0.0.0"\n'
    (fake_repo / "pyproject.toml").write_text(original_pyproject, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=fake_repo, check=True)
    subprocess.run(
        ["git", "-C", str(fake_repo),
         "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "--allow-empty", "-q", "-m", "init-empty"],
        check=True,
    )  # establish HEAD before adding pyproject so we can git-checkout-HEAD-clean
    subprocess.run(
        ["git", "-C", str(fake_repo), "add", "pyproject.toml"], check=True,
    )
    subprocess.run(
        ["git", "-C", str(fake_repo),
         "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "add pyproject"],
        check=True,
    )

    # Sanity: HEAD now contains the original pyproject content.
    head_show = subprocess.run(
        ["git", "-C", str(fake_repo), "show", "HEAD:pyproject.toml"],
        capture_output=True, text=True, check=True,
    )
    assert head_show.stdout == original_pyproject, (
        f"Test setup error: HEAD's pyproject.toml is not the expected baseline. "
        f"Got: {head_show.stdout!r}"
    )

    # --- Simulate the post-bump-pre-commit staged state -----------------------
    bumped_pyproject = '[project]\nname = "fake"\nversion = "9.9.9"\n'
    (fake_repo / "pyproject.toml").write_text(bumped_pyproject, encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(fake_repo), "add", "pyproject.toml"], check=True,
    )
    # Sanity: the bump is staged.
    diff_cached_before = subprocess.run(
        ["git", "-C", str(fake_repo), "diff", "--cached", "pyproject.toml"],
        capture_output=True, text=True, check=True,
    )
    assert diff_cached_before.stdout, (
        "Test setup error: expected staged change to pyproject.toml, "
        "got empty diff --cached"
    )

    # --- Phase 1: phase-completion commit failure → rollback fires -----------
    repo = Path(__file__).resolve().parent.parent
    rollback_hook = repo / ".claude" / "hooks" / "bump-rollback-hook.sh"
    assert rollback_hook.exists(), f"Plan 04 Task 1 must create {rollback_hook}"

    phase_payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {
            "command": (
                'gsd-sdk query commit '
                '"docs(phase-63): complete phase execution" '
                '--files foo.md pyproject.toml'
            )
        },
    })
    result = subprocess.run(
        ["bash", str(rollback_hook)],
        input=phase_payload,
        capture_output=True,
        text=True,
        timeout=10,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(fake_repo)},
    )
    assert result.returncode == 0, (
        f"Rollback hook must exit 0 on success path; got {result.returncode}. "
        f"stderr: {result.stderr!r}"
    )
    assert "reverted pyproject.toml" in result.stderr, (
        f"Rollback hook must log its action to stderr; got: {result.stderr!r}"
    )

    # Index restored to HEAD (Pitfall 4: bare `git checkout -- file` would FAIL this).
    diff_cached_after = subprocess.run(
        ["git", "-C", str(fake_repo), "diff", "--cached", "pyproject.toml"],
        capture_output=True, text=True, check=True,
    )
    assert diff_cached_after.stdout == "", (
        f"Index NOT restored — D-08 literal bug regressed. "
        f"Expected empty diff --cached after rollback; got: {diff_cached_after.stdout!r}. "
        f"This is exactly the no-op behavior RESEARCH §Pitfall 4 documented."
    )

    # Working tree restored to HEAD.
    diff_wt_after = subprocess.run(
        ["git", "-C", str(fake_repo), "diff", "pyproject.toml"],
        capture_output=True, text=True, check=True,
    )
    assert diff_wt_after.stdout == "", (
        f"Working tree NOT restored; got: {diff_wt_after.stdout!r}"
    )

    # Bytes match HEAD's original.
    post_rollback = (fake_repo / "pyproject.toml").read_text(encoding="utf-8")
    assert post_rollback == original_pyproject, (
        f"pyproject.toml content not reverted to HEAD. "
        f"Expected: {original_pyproject!r}; got: {post_rollback!r}"
    )

    # --- Phase 2: non-phase-commit failure → pass-through (no-op) -------------
    # Re-stage a bump so we can prove the hook leaves it alone.
    (fake_repo / "pyproject.toml").write_text(bumped_pyproject, encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(fake_repo), "add", "pyproject.toml"], check=True,
    )

    unrelated_payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {
            "command": 'gsd-sdk query commit "fix: unrelated bug"',
        },
    })
    result_unrelated = subprocess.run(
        ["bash", str(rollback_hook)],
        input=unrelated_payload,
        capture_output=True,
        text=True,
        timeout=10,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(fake_repo)},
    )
    assert result_unrelated.returncode == 0, (
        f"Rollback hook must exit 0 on no-match pass-through; "
        f"got {result_unrelated.returncode}, stderr: {result_unrelated.stderr!r}"
    )
    assert "reverted" not in result_unrelated.stderr, (
        f"Rollback hook fired on a non-phase-completion command — regex gate broken. "
        f"stderr: {result_unrelated.stderr!r}"
    )
    # Bump is STILL staged — pass-through did not touch it.
    diff_cached_passthrough = subprocess.run(
        ["git", "-C", str(fake_repo), "diff", "--cached", "pyproject.toml"],
        capture_output=True, text=True, check=True,
    )
    assert diff_cached_passthrough.stdout, (
        "Pass-through path incorrectly cleared the staged bump; "
        "the hook should be a no-op for non-phase-completion commits."
    )


def test_project_md_has_versioning_section():
    """Phase 63 Plan 05 (SC #4 / D-12 / VALIDATION row 63-05-01): PROJECT.md
    must document the `major.minor.phase` schema with a worked example.

    Drift-guard: if a future edit reformats `## Versioning` away (or moves it
    below `## Constraints`, or strips the worked-example anchors), this test
    fails loud and tells you what to put back.

    The four anchor strings (helper path, flag name, two worked-example
    version values) ensure the section's CONTENT is intact — not just the
    heading. Plan 05's source content is in CONTEXT.md §specifics line 112.
    """
    repo = Path(__file__).resolve().parent.parent
    project_md = repo / ".planning" / "PROJECT.md"
    assert project_md.exists(), (
        f"Phase 63 drift: expected {project_md}; "
        f"found in .planning/: "
        f"{sorted(p.name for p in (repo / '.planning').iterdir())}"
    )

    text = project_md.read_text(encoding="utf-8")

    # 1. ## Versioning H2 heading present, unique.
    versioning_matches = re.findall(r'^## Versioning$', text, re.MULTILINE)
    assert len(versioning_matches) == 1, (
        f"Phase 63 Plan 05 drift: expected exactly one `## Versioning` H2 "
        f"heading in {project_md}, found {len(versioning_matches)}. "
        f"PATTERNS.md §`.planning/PROJECT.md` insertion target: "
        f"immediately above `## Constraints`. "
        f"Existing H2 headings nearby: "
        f"{re.findall(r'^## .+$', text, re.MULTILINE)[:8]}"
    )

    # 2. Four content anchors — helper path, flag, two worked examples.
    anchors = {
        "helper path (tools/bump_version.py)": "tools/bump_version.py",
        "config flag (workflow.auto_version_bump)": "workflow.auto_version_bump",
        "worked example anchor 2.1.50": "2.1.50",
        "worked example anchor 2.1.63": "2.1.63",
    }
    missing = [
        label for label, needle in anchors.items() if needle not in text
    ]
    assert not missing, (
        f"Phase 63 Plan 05 drift: PROJECT.md `## Versioning` section is "
        f"missing required anchor(s): {missing}. "
        f"Source-of-truth content lives in CONTEXT.md §specifics line 112. "
        f"Re-add the section (Task 1 of Plan 05) to fix."
    )

    # 3. Section ordering — Versioning BEFORE Constraints.
    ver_line = next(
        (i for i, line in enumerate(text.splitlines(), 1)
         if line.strip() == "## Versioning"),
        None,
    )
    cons_line = next(
        (i for i, line in enumerate(text.splitlines(), 1)
         if line.strip() == "## Constraints"),
        None,
    )
    assert ver_line is not None, "## Versioning heading not found by line scan"
    assert cons_line is not None, "## Constraints heading not found by line scan"
    assert ver_line < cons_line, (
        f"Phase 63 Plan 05 drift: `## Versioning` (line {ver_line}) must "
        f"appear BEFORE `## Constraints` (line {cons_line}) per "
        f"PATTERNS.md §`.planning/PROJECT.md` insertion target."
    )


def test_phase_63_self_completion_bundles_pyproject_with_planning():
    """Phase 63 Plan 05 (SC #2 / Warning 4 Option A): when Phase 63's own
    self-completion commit lands, the resulting commit object MUST contain
    BOTH `pyproject.toml` (the bump) AND at least one `.planning/` file
    (the phase-completion bookkeeping) — proving the bump is bundled into
    the same commit, not landed in a separate orphan commit (D-02).

    SKIPPED until Phase 63 self-completes: the trigger is the canonical
    commit message `docs(phase-63): complete phase execution`. After the
    first such commit lands in the repo, this test becomes a permanent
    regression net for SC #2 across all future phases.
    """
    repo = Path(__file__).resolve().parent.parent

    # Find the most-recent Phase 63 self-completion commit.
    result = subprocess.run(
        ["git", "-C", str(repo), "log",
         "--grep=^docs(phase-63): complete phase execution",
         "-1", "--format=%H"],
        capture_output=True, text=True, timeout=10,
    )
    commit_hash = result.stdout.strip()
    if not commit_hash:
        pytest.skip(
            "Phase 63 self-completion commit not yet present — "
            "gate fires on next /gsd-execute-phase 63 close. "
            "Searched: git log --grep='^docs(phase-63): complete phase execution' -1"
        )

    # List files in the commit's tree.
    files_result = subprocess.run(
        ["git", "-C", str(repo), "show", "--name-only", "--format=",
         commit_hash],
        capture_output=True, text=True, check=True, timeout=10,
    )
    files = [f for f in files_result.stdout.splitlines() if f.strip()]

    # Assert pyproject.toml is in the commit (the bump landed).
    assert "pyproject.toml" in files, (
        f"SC #2 regression: Phase 63 self-completion commit {commit_hash} "
        f"did NOT include pyproject.toml. The bump was either skipped or "
        f"landed in a separate orphan commit (violating D-02). "
        f"Files in commit: {files}"
    )

    # Assert at least one .planning/ path is in the commit (bookkeeping landed).
    planning_files = [f for f in files if f.startswith(".planning/")]
    assert planning_files, (
        f"SC #2 regression: Phase 63 self-completion commit {commit_hash} "
        f"did NOT include any .planning/ files alongside pyproject.toml. "
        f"The phase-completion bookkeeping must land in the SAME commit "
        f"object as the bump (SC #2: 'no orphaned uncommitted state'). "
        f"Files in commit: {files}"
    )

    # Assert the bumped version value is 2.1.63 (the expected value for
    # Phase 63 of v2.1).
    show_result = subprocess.run(
        ["git", "-C", str(repo), "show", f"{commit_hash}:pyproject.toml"],
        capture_output=True, text=True, check=True, timeout=10,
    )
    assert 'version = "2.1.63"' in show_result.stdout, (
        f"SC #2 regression: Phase 63 self-completion commit {commit_hash} "
        f"contains pyproject.toml but the version value is not '2.1.63'. "
        f"This indicates the bump helper either ran with the wrong --phase "
        f"argument or computed the wrong milestone. Got pyproject.toml content: "
        f"{show_result.stdout[:200]!r}..."
    )
