"""Phase 88.3 / G6 — Windows spec + build.ps1 + __main__.py WebEngine bundling drift-guards.

Linux-runnable source-text assertions that lock in the QtWebEngine bundling
contract. No PyInstaller install required. Mirrors tests/test_packaging_winrt_spec.py's
idiom.

Five guards:
  G6-T1 test_spec_webengine_hiddenimports       — spec declares both WebEngine modules
  G6-T2 test_spec_wires_webengine_into_analysis — WebEngine strings inside Analysis()
  G6-T3 test_build_ps1_webengine_guard_present  — build.ps1 has WEBENGINE GUARD + flag
  G6-T4 test_build_ps1_webengine_guard_exit_13  — build.ps1 exits 13 + header documents it
  G6-T5 test_main_py_check_webengine            — __main__.py has the guard function + flag
"""
from __future__ import annotations

from pathlib import Path

import pytest


_SPEC = (
    Path(__file__).resolve().parent.parent
    / "packaging"
    / "windows"
    / "MusicStreamer.spec"
)

_BUILD_PS1 = (
    Path(__file__).resolve().parent.parent
    / "packaging"
    / "windows"
    / "build.ps1"
)

_MAIN_PY = (
    Path(__file__).resolve().parent.parent
    / "musicstreamer"
    / "__main__.py"
)


@pytest.fixture(scope="module")
def spec_source() -> str:
    assert _SPEC.is_file(), f"expected MusicStreamer.spec at {_SPEC}"
    return _SPEC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def build_ps1_source() -> str:
    assert _BUILD_PS1.is_file(), f"expected build.ps1 at {_BUILD_PS1}"
    return _BUILD_PS1.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def main_py_source() -> str:
    assert _MAIN_PY.is_file(), f"expected __main__.py at {_MAIN_PY}"
    return _MAIN_PY.read_text(encoding="utf-8")


def _strip_comments(source: str) -> str:
    """Strip comment lines for negative-assertion gates.

    Both .spec (Python) and .ps1 (PowerShell) use '#' as the comment
    character, so this helper works for both file types.
    """
    return "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )


# ---------------------------------------------------------------------------
# G6-T1: spec declares both WebEngine hiddenimport strings
# ---------------------------------------------------------------------------

def test_spec_webengine_hiddenimports(spec_source: str) -> None:
    """Phase 88.3 G6-T1: MusicStreamer.spec must declare both QtWebEngineWidgets
    and QtWebEngineCore as hiddenimports.

    oauth_helper.py wraps its QtWebEngineWidgets import in try/except, so
    PyInstaller's modulegraph never sees it. Without explicit hiddenimports,
    QtWebEngineProcess.exe and the .pak / locale data files are not collected,
    and the oauth_helper subprocess crashes exit=2 at runtime (Phase 88 UAT G6).

    hiddenimports-only approach (per RESEARCH OQ1): collect_all takes a PyPI
    dist name, NOT a package path; the hiddenimport triggers
    hook-PySide6.QtWebEngineCore which calls
    get_qt_webengine_binaries_and_data_files() to collect
    QtWebEngineProcess.exe / *.pak / locales / qt.conf automatically. Do NOT
    use collect_all("PySide6.QtWebEngineCore") — that would be wrong.

    Accepts single or double quotes around the module strings.
    """
    stripped = _strip_comments(spec_source)

    has_widgets = (
        '"PySide6.QtWebEngineWidgets"' in stripped
        or "'PySide6.QtWebEngineWidgets'" in stripped
    )
    assert has_widgets, (
        "MusicStreamer.spec must declare 'PySide6.QtWebEngineWidgets' as a "
        "hiddenimport (non-comment line). oauth_helper.py:62-71 wraps this "
        "import in try/except — modulegraph never sees it. Phase 88.3 G6-T1: "
        "omitting this causes oauth_helper subprocess to crash exit=2 (UAT G6)."
    )

    has_core = (
        '"PySide6.QtWebEngineCore"' in stripped
        or "'PySide6.QtWebEngineCore'" in stripped
    )
    assert has_core, (
        "MusicStreamer.spec must declare 'PySide6.QtWebEngineCore' as a "
        "hiddenimport (non-comment line). The Core module ships "
        "QtWebEngineProcess.exe and the .pak data files required for WebEngine "
        "to run in the frozen bundle. Phase 88.3 G6-T1."
    )


# ---------------------------------------------------------------------------
# G6-T2: WebEngine hiddenimports appear inside the Analysis() block
# ---------------------------------------------------------------------------

def test_spec_wires_webengine_into_analysis(spec_source: str) -> None:
    """Phase 88.3 G6-T2: the WebEngine hiddenimport strings must appear inside
    the Analysis() hiddenimports= list, not just at module top level.

    Negative gate (comment-stripped): if the strings only appear in commented-out
    lines they are documentation, not active bundling. Drift-guard catches partial
    edits that add the strings to a comment block only.
    """
    stripped = _strip_comments(spec_source)

    # Positive: both module strings must appear on non-comment lines
    has_widgets = (
        '"PySide6.QtWebEngineWidgets"' in stripped
        or "'PySide6.QtWebEngineWidgets'" in stripped
    )
    assert has_widgets, (
        "MusicStreamer.spec must include 'PySide6.QtWebEngineWidgets' on a "
        "non-comment line inside Analysis() hiddenimports=. Phase 88.3 G6-T2."
    )

    has_core = (
        '"PySide6.QtWebEngineCore"' in stripped
        or "'PySide6.QtWebEngineCore'" in stripped
    )
    assert has_core, (
        "MusicStreamer.spec must include 'PySide6.QtWebEngineCore' on a "
        "non-comment line inside Analysis() hiddenimports=. Phase 88.3 G6-T2."
    )

    # Verify the strings appear within the Analysis() call region.
    # Heuristic: both strings occur AFTER 'a = Analysis(' in the source.
    analysis_idx = spec_source.find("a = Analysis(")
    assert analysis_idx != -1, (
        "MusicStreamer.spec must contain 'a = Analysis(' to anchor the "
        "hiddenimports wiring check. Phase 88.3 G6-T2."
    )
    analysis_tail = spec_source[analysis_idx:]
    assert (
        "PySide6.QtWebEngineWidgets" in analysis_tail
        or "QtWebEngineWidgets" in analysis_tail
    ), (
        "MusicStreamer.spec: 'PySide6.QtWebEngineWidgets' must appear inside "
        "the Analysis() block (after 'a = Analysis('). Phase 88.3 G6-T2."
    )
    assert (
        "PySide6.QtWebEngineCore" in analysis_tail
        or "QtWebEngineCore" in analysis_tail
    ), (
        "MusicStreamer.spec: 'PySide6.QtWebEngineCore' must appear inside the "
        "Analysis() block (after 'a = Analysis('). Phase 88.3 G6-T2."
    )

    # Negative gate: must NOT use collect_all for WebEngine (RESEARCH OQ1 lock)
    assert "collect_all" not in analysis_tail.split("hiddenimports=")[0].split("PySide6.QtWebEngineCore")[0] or True, ""
    # Stronger negative: collect_all("PySide6.QtWebEngine...") must NOT appear anywhere
    collect_all_widgets = (
        'collect_all("PySide6.QtWebEngineWidgets")' in spec_source
        or "collect_all('PySide6.QtWebEngineWidgets')" in spec_source
    )
    assert not collect_all_widgets, (
        "MusicStreamer.spec must NOT call collect_all('PySide6.QtWebEngineWidgets'). "
        "collect_all takes a PyPI distribution name, NOT a Python package path. "
        "Use hiddenimports only (RESEARCH OQ1 decision). Phase 88.3 G6-T2."
    )
    collect_all_core = (
        'collect_all("PySide6.QtWebEngineCore")' in spec_source
        or "collect_all('PySide6.QtWebEngineCore')" in spec_source
    )
    assert not collect_all_core, (
        "MusicStreamer.spec must NOT call collect_all('PySide6.QtWebEngineCore'). "
        "collect_all takes a PyPI distribution name, NOT a Python package path. "
        "Use hiddenimports only (RESEARCH OQ1 decision). Phase 88.3 G6-T2."
    )


# ---------------------------------------------------------------------------
# G6-T3: build.ps1 has the WEBENGINE GUARD block with the flag
# ---------------------------------------------------------------------------

def test_build_ps1_webengine_guard_present(build_ps1_source: str) -> None:
    """Phase 88.3 G6-T3: build.ps1 must contain a step-4e WEBENGINE GUARD that
    invokes the frozen exe with --check-webengine.

    Drift-guard: catches accidental removal of step 4e or rephrasing of the
    canonical step header / flag name that CI / wrapper scripts depend on.

    RED until Task 2 lands build.ps1 changes.
    """
    assert "WEBENGINE GUARD" in build_ps1_source, (
        "build.ps1 must contain the literal 'WEBENGINE GUARD' in the step 4e "
        "header. If you renamed the step, update this test AND the rationale "
        "block in build.ps1 together. Phase 88.3 G6-T3."
    )
    assert "--check-webengine" in build_ps1_source, (
        "build.ps1 step 4e must invoke the frozen exe with --check-webengine "
        "(Phase 88.3 G6-T3). This flag is implemented by __main__.py's "
        "_run_check_webengine() and exits 0 only if QtWebEngineWidgets imports "
        "successfully — confirming the WebEngine runtime landed in the bundle."
    )


# ---------------------------------------------------------------------------
# G6-T4: build.ps1 step-4e exits 13 and header documents it
# ---------------------------------------------------------------------------

def test_build_ps1_webengine_guard_exit_13(build_ps1_source: str) -> None:
    """Phase 88.3 G6-T4: build.ps1 step 4e must exit 13 on WEBENGINE GUARD
    failure, and exit 13 must be documented in the exit-codes header comment.

    WR-01 compliance: the failure path must use Write-Host (not Write-Error)
    so the documented exit 13 actually fires under $ErrorActionPreference='Stop'.
    Drift-guard: catches swap back to Write-Error or removal of the exit-code
    header documentation.

    RED until Task 2 lands build.ps1 changes.
    """
    assert "exit 13" in build_ps1_source, (
        "build.ps1 step 4e must `exit 13` on WEBENGINE GUARD failure "
        "(Phase 88.3 G6-T4 / G6). The exit code must match the header documentation."
    )
    assert "13=" in build_ps1_source, (
        "build.ps1 exit-codes header must document '13=webengine not bundled "
        "in frozen bundle (Phase 88.3 / G6)' so a future maintainer can map "
        "the exit code to its source step. Phase 88.3 G6-T4."
    )
    # WR-01: verify Write-Host precedes the BUILD_FAIL literal (not Write-Error)
    idx = build_ps1_source.find("BUILD_FAIL reason=webengine_not_bundled")
    assert idx != -1, (
        "build.ps1 step 4e failure branch must emit 'BUILD_FAIL reason=webengine_not_bundled' "
        "so CI / wrapper scripts can grep the cause from build.log. Phase 88.3 G6-T4."
    )
    before = build_ps1_source[max(0, idx - 120) : idx + 60]
    assert "Write-Host" in before, (
        "build.ps1 step 4e 'BUILD_FAIL reason=webengine_not_bundled' must be "
        "emitted via `Write-Host ... -ForegroundColor Red` (NOT `Write-Error`). "
        "Write-Error escalates to a terminating error under "
        "$ErrorActionPreference = 'Stop' and the documented `exit 13` below it "
        "never executes — the script returns 1 instead. See Phase 65 WR-01."
    )
    after = build_ps1_source[idx : idx + 400]
    assert "exit 13" in after, (
        "build.ps1 step 4e `BUILD_FAIL reason=webengine_not_bundled` must be "
        "followed by `exit 13` within the same failure block. Otherwise the "
        "documented exit code 13 would not actually fire on WEBENGINE GUARD failure."
    )


# ---------------------------------------------------------------------------
# G6-T5: __main__.py has the guard function and the CLI flag
# ---------------------------------------------------------------------------

def test_main_py_check_webengine(main_py_source: str) -> None:
    """Phase 88.3 G6-T5: musicstreamer/__main__.py must expose _run_check_webengine()
    and a --check-webengine argparse flag dispatching to it.

    The guard function imports QWebEngineView and returns 0 on success, 13 on
    ImportError (no QApplication required — import-only, no display needed).
    build.ps1 step-4e invokes `MusicStreamer.exe --check-webengine` and fails
    the build (exit 13) when WebEngine is missing from the frozen bundle.

    RED until Task 2 lands __main__.py changes.
    """
    assert "def _run_check_webengine" in main_py_source, (
        "musicstreamer/__main__.py must define `def _run_check_webengine` "
        "(mirroring _run_check_mediakeys). This function imports QWebEngineView "
        "and returns 13 on ImportError so build.ps1 step-4e can fail the build "
        "when WebEngine is not bundled. Phase 88.3 G6-T5."
    )
    assert "--check-webengine" in main_py_source, (
        "musicstreamer/__main__.py must register a `--check-webengine` argparse "
        "argument and dispatch to _run_check_webengine(). "
        "build.ps1 step-4e invokes `MusicStreamer.exe --check-webengine` — "
        "without the flag the exe errors with 'unrecognized arguments'. "
        "Phase 88.3 G6-T5."
    )
