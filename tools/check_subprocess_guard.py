"""Build-time PKG-03 guard (Phase 44, D-22).

Walks musicstreamer/ and fails if any bare subprocess.{Popen,run,call} call
appears outside the single legitimate site (subprocess_utils.py). Mirrors
the build.ps1 ripgrep guard semantically; runs cross-platform (Linux dev,
Windows build VM) so the same check works in both contexts.

Exit codes:
    0 — clean (zero bare subprocess.* calls)
    4 — violations found (matches build.ps1 exit code convention, D-22)

Callable as ``python tools/check_subprocess_guard.py`` from the repo root.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_FORBIDDEN = re.compile(r"\bsubprocess\.(Popen|run|call)\b")


def _repo_root() -> Path:
    # tools/check_subprocess_guard.py → repo root is parent.parent.
    return Path(__file__).resolve().parent.parent


def main() -> int:
    root = _repo_root() / "musicstreamer"
    if not root.is_dir():
        print(f"PKG-03 FAIL: musicstreamer/ not found at {root}", file=sys.stderr)
        return 4

    offenders: list[str] = []
    for path in root.rglob("*.py"):
        # Exclude the single legitimate call site by exact filename match
        # (T-44-01-01 disposition: literal Name comparison, not glob).
        if path.name == "subprocess_utils.py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"PKG-03 WARN: could not read {path}: {exc}", file=sys.stderr)
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if _FORBIDDEN.search(line):
                offenders.append(f"{path}:{lineno}: {stripped}")

    if offenders:
        print("PKG-03 FAIL: bare subprocess.{Popen,run,call} found outside subprocess_utils.py")
        for hit in offenders:
            print(f"  {hit}")
        sys.exit(4)

    print("PKG-03 OK: zero bare subprocess.* calls in musicstreamer/")
    sys.exit(0)


if __name__ == "__main__":
    main()
