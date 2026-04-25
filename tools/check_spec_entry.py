"""Build-time .spec entry-point guard (Phase 44, PKG-01).

Asserts packaging/windows/MusicStreamer.spec references the canonical
MusicStreamer entry point per RESEARCH §Pattern 4. If the .spec file does
not yet exist (Wave 1 Plan 04 hasn't landed it), this guard exits cleanly
with a notice — keeping Plan 01 unblocked on Plan 04 ordering.

Exit codes:
    0 — entry point present, OR .spec not yet created (guard inactive)
    7 — .spec exists but is missing the canonical entry point reference

Callable as ``python tools/check_spec_entry.py`` from the repo root.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ENTRY_LITERAL = '"../../musicstreamer/__main__.py"'


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main() -> int:
    spec_path = _repo_root() / "packaging" / "windows" / "MusicStreamer.spec"
    if not spec_path.exists():
        print("PKG-01 NOTICE: spec not yet created — guard inactive")
        sys.exit(0)

    text = spec_path.read_text(encoding="utf-8")
    if _ENTRY_LITERAL in text:
        print(f"PKG-01 OK: spec references {_ENTRY_LITERAL}")
        sys.exit(0)

    print(
        f"PKG-01 FAIL: {spec_path} is missing the canonical entry point "
        f"reference {_ENTRY_LITERAL}",
        file=sys.stderr,
    )
    sys.exit(7)


if __name__ == "__main__":
    main()
