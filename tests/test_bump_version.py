"""Phase 63 (VER-01) — bump_version helper test suite.

Covers SC #1 (rewrite happy path) + D-07 ([project] scope) + D-09 (no partial
writes on parse error) + Pitfall 2 (drift-guard against PROJECT.md milestone
heading reformat). Plans 02-05 extend this module with config-gate, hook
wiring, rollback, and PROJECT.md ## Versioning section tests.

Runtime budget: <1s for the whole module per RESEARCH §Validation Architecture.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from pathlib import Path


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
