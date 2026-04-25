"""PyInstaller .spec content guard (Phase 44, PKG-01).

Asserts the canonical Phase 44 .spec contains the required hiddenimports + entry
point + EXE attributes. Skipped when the .spec file does not yet exist (Plan 04
lands the file; this test scaffold is created by Plan 01 so executors of later
plans have a single feedback loop).
"""
from __future__ import annotations

from pathlib import Path

import pytest

_SPEC_PATH = (
    Path(__file__).resolve().parent.parent
    / "packaging"
    / "windows"
    / "MusicStreamer.spec"
)

_REQUIRED_SUBSTRINGS = [
    '"../../musicstreamer/__main__.py"',
    '"PySide6.QtNetwork"',
    '"PySide6.QtSvg"',
    '"winrt.windows.media"',
    '"winrt.windows.media.playback"',
    'name="MusicStreamer"',
    "console=False",
    "upx=False",
    'icon="icons/MusicStreamer.ico"',
]


def test_spec_contains_required_imports():
    """The Phase 44 PyInstaller spec must declare every canonical hiddenimport / EXE attr."""
    if not _SPEC_PATH.exists():
        pytest.skip(
            "spec not yet created — Wave 1 Plan 04 dependency. "
            "This guard activates once packaging/windows/MusicStreamer.spec lands."
        )
    text = _SPEC_PATH.read_text(encoding="utf-8")
    for needle in _REQUIRED_SUBSTRINGS:
        assert needle in text, (
            f"PKG-01 violation: required string not found in {_SPEC_PATH}: {needle!r}"
        )
