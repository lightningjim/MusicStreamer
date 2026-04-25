"""PKG-03 compliance: no bare subprocess.{Popen,run,call} outside subprocess_utils.py.

Phase 44, D-22: enforces SC-4 / PKG-03 as a Python regression test (cross-platform —
runs on Linux CI too, mirroring the build.ps1 ripgrep guard).

The single legitimate call site is musicstreamer/subprocess_utils.py::_popen, which
sets CREATE_NO_WINDOW on Windows. All other modules MUST go through that helper.
"""
from __future__ import annotations

import re
from pathlib import Path

_FORBIDDEN = re.compile(r"\bsubprocess\.(Popen|run|call)\b")


def test_no_raw_subprocess_in_musicstreamer():
    """Pure-Python grep: zero bare subprocess.{Popen,run,call} hits outside subprocess_utils.py."""
    root = Path(__file__).resolve().parent.parent / "musicstreamer"
    assert root.is_dir(), f"musicstreamer/ not found at {root}"
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        if path.name == "subprocess_utils.py":
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if _FORBIDDEN.search(line):
                offenders.append(f"{path}:{lineno}: {stripped}")
    assert not offenders, "PKG-03 violation:\n" + "\n".join(offenders)
