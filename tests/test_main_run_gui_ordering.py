"""Phase 61 / Plan 03 Task 3 — startup-ordering sanity guard.

`desktop_install.ensure_installed()` must run BEFORE `QApplication(...)`
in `_run_gui`. Per RESEARCH §Open Question #7: if the call lands after
`QApplication`, the very first window can emit a `_GTK_APPLICATION_ID`
without a matching `.desktop` file in the XDG path, causing the GNOME
force-quit dialog to fall back to the raw app_id (the BUG-08 surface this
phase fixes).

The test parses `musicstreamer/__main__.py` as text and checks the call
order. It does NOT execute `_run_gui` (which would require Qt + GStreamer
startup); a regex-on-source check is enough to catch a future refactor
that accidentally reorders the calls.
"""
from __future__ import annotations

from pathlib import Path

import pytest

_MAIN = Path(__file__).resolve().parent.parent / "musicstreamer" / "__main__.py"


@pytest.fixture(scope="module")
def main_source() -> str:
    return _MAIN.read_text(encoding="utf-8")


def _index(haystack: str, needle: str) -> int:
    idx = haystack.find(needle)
    assert idx != -1, f"expected {needle!r} in musicstreamer/__main__.py"
    return idx


def test_ensure_installed_runs_before_qapplication(main_source: str) -> None:
    ensure = _index(main_source, "desktop_install.ensure_installed(")
    qapp = _index(main_source, "QApplication(")
    assert ensure < qapp, (
        "desktop_install.ensure_installed() must precede QApplication(...) so "
        "the .desktop file is in the XDG path before the first window binds. "
        f"Got ensure_installed @ byte {ensure}, QApplication @ byte {qapp}."
    )


def test_ensure_installed_runs_after_gst_init(main_source: str) -> None:
    gst = _index(main_source, "Gst.init(None)")
    ensure = _index(main_source, "desktop_install.ensure_installed(")
    assert gst < ensure, (
        "Gst.init(None) must precede desktop_install.ensure_installed() so "
        "GStreamer is initialized before any other startup work. "
        f"Got Gst.init @ byte {gst}, ensure_installed @ byte {ensure}."
    )
