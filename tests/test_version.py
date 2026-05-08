"""Phase 65 / VER-02 — version read-mechanism tests.

VER-02-A: importlib.metadata.version("musicstreamer") matches pyproject.toml [project].version.
VER-02-B: the version string is M.m.p triple of integers (Phase 63 VER-01 contract).

These tests guard the dev path; the bundle path is guarded structurally by
Plan 65-02's `copy_metadata("musicstreamer")` spec edit + the PyInstaller build
failing if metadata is missing.
"""
from __future__ import annotations

import re
import tomllib
from importlib.metadata import version
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def test_metadata_version_matches_pyproject() -> None:
    """VER-02-A: importlib.metadata version equals pyproject.toml [project].version."""
    with open(_ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    expected = data["project"]["version"]
    actual = version("musicstreamer")
    assert actual == expected, (
        f"importlib.metadata.version('musicstreamer') = {actual!r} but "
        f"pyproject.toml [project].version = {expected!r}. Run `uv sync` "
        f"to refresh .venv dist-info."
    )


def test_metadata_version_is_semver_triple() -> None:
    """VER-02-B: version string is M.m.p triple of integers (Phase 63 VER-01 shape)."""
    v = version("musicstreamer")
    assert re.match(r"^\d+\.\d+\.\d+$", v), (
        f"Expected M.m.p triple, got {v!r}"
    )
