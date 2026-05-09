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


def _slice_run_gui(source: str) -> tuple[str, int]:
    """Return ``(run_gui_body, offset_into_source)``.

    Phase 65 BLK-01: the previous test layout searched the WHOLE file for
    ``Gst.init(None)`` / ``QApplication(`` / ``desktop_install.ensure_installed(``,
    but ``Gst.init(None)`` also appears at module top in ``_run_smoke`` (the
    Phase 35 headless harness). ``str.find`` returns the FIRST hit, so the
    "in _run_gui" ordering assertion compared a token in ``_run_smoke``
    against a token in ``_run_gui`` — two unrelated functions — and was
    always trivially satisfied. Restricting the search to the ``_run_gui``
    body makes the assertions test what their docstrings claim.

    Slice end is the next top-level ``def`` (``main`` follows ``_run_gui``)
    or EOF.
    """
    start = source.find("def _run_gui(")
    assert start != -1, "could not locate _run_gui definition in __main__.py"
    end = source.find("\ndef ", start + 1)
    if end == -1:
        end = len(source)
    return source[start:end], start


def test_ensure_installed_runs_before_qapplication(main_source: str) -> None:
    body, _ = _slice_run_gui(main_source)
    ensure = body.find("desktop_install.ensure_installed(")
    qapp = body.find("QApplication(")
    assert ensure != -1, "desktop_install.ensure_installed( missing from _run_gui"
    assert qapp != -1, "QApplication( missing from _run_gui"
    assert ensure < qapp, (
        "desktop_install.ensure_installed() must precede QApplication(...) so "
        "the .desktop file is in the XDG path before the first window binds. "
        f"Got ensure_installed @ char {ensure}, QApplication @ char {qapp} "
        "(offsets are within _run_gui body)."
    )


def test_ensure_installed_runs_after_gst_init(main_source: str) -> None:
    body, _ = _slice_run_gui(main_source)
    gst = body.find("Gst.init(None)")
    ensure = body.find("desktop_install.ensure_installed(")
    assert gst != -1, "Gst.init(None) missing from _run_gui"
    assert ensure != -1, "desktop_install.ensure_installed( missing from _run_gui"
    assert gst < ensure, (
        "Gst.init(None) must precede desktop_install.ensure_installed() so "
        "GStreamer is initialized before any other startup work. "
        f"Got Gst.init @ char {gst}, ensure_installed @ char {ensure} "
        "(offsets are within _run_gui body)."
    )


def test_set_application_version_in_run_gui(main_source: str) -> None:
    """Phase 65 / VER-02-F (D-07): app.setApplicationVersion(...) is called in
    _run_gui AFTER QApplication(argv) construction (so the singleton exists),
    and reads via importlib.metadata (not a hardcoded literal) — single source
    of truth in pyproject.toml."""
    body, _ = _slice_run_gui(main_source)
    qapp = body.find("QApplication(argv)")
    setver = body.find("setApplicationVersion(")
    assert qapp != -1, "QApplication(argv) missing from _run_gui"
    assert setver != -1, "setApplicationVersion( missing from _run_gui"
    assert setver > qapp, (
        "app.setApplicationVersion(...) must run AFTER QApplication(argv) "
        "construction so the application singleton exists. "
        f"Got QApplication(argv) @ char {qapp}, setApplicationVersion @ char "
        f"{setver} (offsets are within _run_gui body)."
    )
    # D-07 contract: the setter argument must be sourced from importlib.metadata,
    # not a hardcoded literal. Check the file imports importlib.metadata AND the
    # setter site references the imported name (allow either `_pkg_version(`
    # or `version(` since the helper alias is up to the implementer).
    assert "from importlib.metadata import" in main_source, (
        "musicstreamer/__main__.py must import from importlib.metadata "
        "(single source of truth = pyproject.toml [project].version)."
    )
    # Window the proximity check against the _run_gui body slice (NOT the
    # whole file): `setver` is an offset into `body`, so indexing
    # `main_source[setver:...]` would land inside `_run_smoke`'s
    # `Gst.init` block — exactly the cross-function bug BLK-01 fixed for
    # the ordering checks.
    nearby = body[setver : setver + 200]
    assert "_pkg_version(" in nearby or "version(" in nearby, (
        "setApplicationVersion(...) must read via importlib.metadata.version "
        "(not a literal string). Got setter context: "
        f"{nearby!r}"
    )
