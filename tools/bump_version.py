"""Phase 63 / VER-01 — auto-bump pyproject.toml version on phase completion.

Rewrites the `version` line inside the `[project]` table of `pyproject.toml`
to `{major}.{minor}.{phase}`, where `{major}.{minor}` is parsed from
PROJECT.md's `## Current Milestone: vX.Y` heading and `{phase}` is the
--phase argument.

Exit codes:
    0 — success (rewrite landed) OR dry-run completed
    1 — parse error (PROJECT.md milestone heading not found OR
        pyproject.toml missing [project] table OR no parseable version line
        OR --phase arg is negative)
    3 — config disabled (D-11 short-circuit; informational, not a hard failure)

Callable as ``python tools/bump_version.py --phase NN`` from the repo root.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Module-level compiled regexes (all VERIFIED live in 63-RESEARCH §Pattern 3
# + §Pattern 4 against the actual pyproject.toml + PROJECT.md in this repo).
_PROJECT_TABLE_RE = re.compile(r'^\[project\]\s*$', re.MULTILINE)
_NEXT_TABLE_RE = re.compile(r'^\[', re.MULTILINE)
_VERSION_LINE_RE = re.compile(r'^(version\s*=\s*)"[^"]*"(\s*)$', re.MULTILINE)
_MILESTONE_RE = re.compile(r'^##\s+Current Milestone:\s*v(\d+)\.(\d+)', re.MULTILINE)


def _repo_root() -> Path:
    # tools/bump_version.py -> repo root is parent.parent.
    return Path(__file__).resolve().parent.parent


def parse_milestone(project_md: str) -> tuple[int, int] | None:
    """Return (major, minor) from PROJECT.md text, or None on no match."""
    m = _MILESTONE_RE.search(project_md)
    return (int(m.group(1)), int(m.group(2))) if m else None


def rewrite_pyproject_version(content: str, new_version: str) -> str | None:
    """Return content with [project].version replaced, or None on parse failure.

    Returns None when (a) no [project] table OR (b) zero/multiple version lines
    within the [project] block. The caller MUST treat None as a parse error
    and abort without writing (D-09).
    """
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


def is_auto_bump_enabled(repo_root: Path) -> bool:
    """Return True if workflow.auto_version_bump is "true" OR the key is absent.

    D-10: missing key (gsd-sdk exit 1) → default-true. Any other non-zero
    exit also returns True (fail open — better to bump than to silently skip
    on a transient SDK error). The disabled state is reached ONLY by an
    explicit ``"false"`` value present in ``.planning/config.json``.
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", type=int, required=True)
    parser.add_argument(
        "--pyproject", type=Path, default=None,
        help="Override pyproject.toml path (test-only).",
    )
    parser.add_argument(
        "--project-md", dest="project_md", type=Path, default=None,
        help="Override PROJECT.md path (test-only).",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--check", action="store_true",
        help="Reserved for future use; currently a no-op alias of --dry-run.",
    )
    args = parser.parse_args()

    # V5 input validation (ASVS): phase must be non-negative.
    if args.phase < 0:
        print(
            f"[bump] FAIL: --phase must be >= 0, got {args.phase}",
            file=sys.stderr,
        )
        return 1

    # D-11: short-circuit when flag is explicitly false (default-true on absence).
    if not is_auto_bump_enabled(_repo_root()):
        print("[bump] disabled via workflow.auto_version_bump", file=sys.stderr)
        return 3

    repo = _repo_root()
    pyproject_path = (
        args.pyproject if args.pyproject is not None else repo / "pyproject.toml"
    )
    project_md_path = (
        args.project_md if args.project_md is not None
        else repo / ".planning" / "PROJECT.md"
    )

    # 1. Parse milestone (D-04, D-05).
    try:
        project_md_text = project_md_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(
            f"[bump] FAIL: cannot read {project_md_path}: {exc}",
            file=sys.stderr,
        )
        return 1
    milestone = parse_milestone(project_md_text)
    if milestone is None:
        print(
            f"[bump] FAIL: '## Current Milestone: vX.Y' not found in "
            f"{project_md_path}",
            file=sys.stderr,
        )
        return 1
    major, minor = milestone
    new_version = f"{major}.{minor}.{args.phase}"

    # 2. Rewrite pyproject (D-06, D-07, Pitfall 6 — text mode, encoding="utf-8").
    try:
        content = pyproject_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(
            f"[bump] FAIL: cannot read {pyproject_path}: {exc}",
            file=sys.stderr,
        )
        return 1
    rewritten = rewrite_pyproject_version(content, new_version)
    if rewritten is None:
        print(
            f"[bump] FAIL: could not locate [project].version line in "
            f"{pyproject_path}",
            file=sys.stderr,
        )
        return 1

    # 3. Dry-run path (no write).
    if args.dry_run or args.check:
        print(f"[bump] would rewrite {pyproject_path} version to {new_version}")
        return 0

    # 4. Write (D-09: only here, only after all parses succeeded).
    pyproject_path.write_text(rewritten, encoding="utf-8")
    print(f"[bump] OK: wrote version = \"{new_version}\" to {pyproject_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
