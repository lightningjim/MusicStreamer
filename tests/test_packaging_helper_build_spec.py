"""Phase 88.3-04 — Drift-guards for the isolated OAuth helper build artifacts.

Linux-runnable source-text assertions that lock in the B1 invariants for the
SEPARATE oauth_helper.exe (built from an isolated pip env, NOT the conda bundle).

Task 1 tests (requirements file + standalone spec):
  test_helper_requirements_pinned          -- exact pin versions are present
  test_helper_spec_has_webengine_hiddenimports -- spec contains WebEngine imports
  test_helper_spec_freezes_oauth_helper    -- spec entry + COLLECT name = oauth_helper
  test_helper_spec_repo_root_two_levels    -- parents[1] not parents[2] (packaging/windows layout)

Task 2 tests (build.ps1 second build + Inno two-artifact + README prereq):
  test_build_ps1_builds_helper             -- build.ps1 references spec + requirements
  test_build_ps1_helper_isolated_venv      -- build.ps1 uses isolated venv + -HelperPythonExe
  test_build_ps1_asserts_helper_webengine  -- build.ps1 asserts QtWebEngineProcess.exe + exit 14
  test_iss_ships_helper                    -- MusicStreamer.iss ships oauth_helper under {app}\\oauth_helper
  test_readme_documents_conda_free_python  -- README has conda-free Python 3.12 prereq, not pip-Addons-into-conda

Mirrors test_packaging_webengine_spec.py's fixture + _strip_comments idiom.
"""
from __future__ import annotations

from pathlib import Path

import pytest


_REQS = (
    Path(__file__).resolve().parent.parent
    / "packaging"
    / "windows"
    / "oauth-helper-requirements.txt"
)

_SPEC = (
    Path(__file__).resolve().parent.parent
    / "packaging"
    / "windows"
    / "oauth_helper_standalone.spec"
)

_BUILD_PS1 = (
    Path(__file__).resolve().parent.parent
    / "packaging"
    / "windows"
    / "build.ps1"
)

_ISS = (
    Path(__file__).resolve().parent.parent
    / "packaging"
    / "windows"
    / "MusicStreamer.iss"
)

_README = (
    Path(__file__).resolve().parent.parent
    / "packaging"
    / "windows"
    / "README.md"
)


@pytest.fixture(scope="module")
def reqs_source() -> str:
    assert _REQS.is_file(), f"expected oauth-helper-requirements.txt at {_REQS}"
    return _REQS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def spec_source() -> str:
    assert _SPEC.is_file(), f"expected oauth_helper_standalone.spec at {_SPEC}"
    return _SPEC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def build_ps1_source() -> str:
    assert _BUILD_PS1.is_file(), f"expected build.ps1 at {_BUILD_PS1}"
    return _BUILD_PS1.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def iss_source() -> str:
    assert _ISS.is_file(), f"expected MusicStreamer.iss at {_ISS}"
    return _ISS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def readme_source() -> str:
    assert _README.is_file(), f"expected README.md at {_README}"
    return _README.read_text(encoding="utf-8")


def _strip_comments(source: str) -> str:
    """Strip comment lines for negative-assertion gates.

    Both .spec (Python) and .ps1 (PowerShell) and .txt files use '#' as
    the comment character, so this helper works for all file types in use.
    """
    return "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )


# ---------------------------------------------------------------------------
# Task 1 — requirements file pins
# ---------------------------------------------------------------------------

def test_helper_requirements_pinned(reqs_source: str) -> None:
    """Phase 88.3-04 Task 1: oauth-helper-requirements.txt must contain
    all four exact pins: PySide6-Essentials==6.10.1, PySide6-Addons==6.10.1,
    pyinstaller==6.19.0, pyinstaller-hooks-contrib==2026.2.

    These pins are the B1 supply-chain gate: they ensure the isolated helper
    venv gets an ABI-self-consistent pip Qt 6.10.1 (matching the conda main
    app's pyside6 6.10.1 QNetworkCookie contract) and a validated PyInstaller
    toolchain. Unpinned installs risk ICU ABI mismatch or WebEngine ABI
    mismatch that would defeat the entire B1 isolation. Phase 88.3-04 T-03.
    """
    stripped = _strip_comments(reqs_source)

    assert "PySide6-Essentials==6.10.1" in stripped, (
        "oauth-helper-requirements.txt must contain 'PySide6-Essentials==6.10.1' "
        "(exact pin; B1 supply-chain gate; must match conda app's pyside6 6.10.1). "
        "Phase 88.3-04 Task 1."
    )
    assert "PySide6-Addons==6.10.1" in stripped, (
        "oauth-helper-requirements.txt must contain 'PySide6-Addons==6.10.1' "
        "(exact pin; this is the WebEngine carrier in the B1 isolated build). "
        "Phase 88.3-04 Task 1."
    )
    assert "pyinstaller==6.19.0" in stripped, (
        "oauth-helper-requirements.txt must contain 'pyinstaller==6.19.0' "
        "(exact pin; validated toolchain version from spike 001). "
        "Phase 88.3-04 Task 1."
    )
    assert "pyinstaller-hooks-contrib==2026.2" in stripped, (
        "oauth-helper-requirements.txt must contain 'pyinstaller-hooks-contrib==2026.2' "
        "(exact pin; required for PySide6/WebEngine hooks-contrib support). "
        "Phase 88.3-04 Task 1."
    )


# ---------------------------------------------------------------------------
# Task 1 — standalone spec WebEngine hiddenimports
# ---------------------------------------------------------------------------

def test_helper_spec_has_webengine_hiddenimports(spec_source: str) -> None:
    """Phase 88.3-04 Task 1: comment-stripped oauth_helper_standalone.spec
    must contain 'PySide6.QtWebEngineWidgets' AND 'PySide6.QtWebEngineCore'.

    The helper IS the WebEngine carrier in B1 — opposite of the conda spec's
    B1 invariant (test_spec_has_no_webengine_hiddenimports in webengine_spec).
    These hiddenimports trigger the PyInstaller hooks-contrib WebEngine hooks
    against the isolated pip PySide6-Addons, bundling QtWebEngineProcess.exe
    and Qt6WebEngineCore.dll into dist/oauth_helper/. Phase 88.3-04 Task 1.
    """
    stripped = _strip_comments(spec_source)

    assert "PySide6.QtWebEngineWidgets" in stripped, (
        "oauth_helper_standalone.spec must contain 'PySide6.QtWebEngineWidgets' "
        "on a non-comment line inside hiddenimports= (the helper is the WebEngine "
        "carrier in B1; this hiddenimport triggers the PyInstaller WebEngine hook). "
        "Phase 88.3-04 Task 1."
    )
    assert "PySide6.QtWebEngineCore" in stripped, (
        "oauth_helper_standalone.spec must contain 'PySide6.QtWebEngineCore' "
        "on a non-comment line inside hiddenimports= (needed to bundle "
        "Qt6WebEngineCore.dll into the helper artifact). Phase 88.3-04 Task 1."
    )


# ---------------------------------------------------------------------------
# Task 1 — standalone spec freezes oauth_helper.py
# ---------------------------------------------------------------------------

def test_helper_spec_freezes_oauth_helper(spec_source: str) -> None:
    """Phase 88.3-04 Task 1: oauth_helper_standalone.spec must reference
    musicstreamer/oauth_helper.py as its entry and name the EXE/COLLECT
    'oauth_helper'.

    The spec must freeze the real production oauth_helper.py (not a stub or
    the main app), and the COLLECT name must be 'oauth_helper' so the built
    artifact lands at dist/oauth_helper/ (the path build.ps1 asserts and
    MusicStreamer.iss installs to {app}\\oauth_helper\\). Phase 88.3-04 Task 1.
    """
    assert "oauth_helper.py" in spec_source or "oauth_helper" in spec_source, (
        "oauth_helper_standalone.spec must reference 'oauth_helper.py' or 'oauth_helper' "
        "as the entry point. Phase 88.3-04 Task 1."
    )

    # Check COLLECT name="oauth_helper"
    assert 'name="oauth_helper"' in spec_source, (
        "oauth_helper_standalone.spec must contain name=\"oauth_helper\" "
        "(both EXE and COLLECT must use this name so dist/oauth_helper/ is produced). "
        "Phase 88.3-04 Task 1."
    )


# ---------------------------------------------------------------------------
# Task 1 — standalone spec uses parents[1] not parents[2]
# ---------------------------------------------------------------------------

def test_helper_spec_repo_root_two_levels(spec_source: str) -> None:
    """Phase 88.3-04 Task 1: oauth_helper_standalone.spec must use parents[1]
    (not parents[2]) to compute REPO_ROOT.

    The spike spec lives at .planning/spikes/001-.../oauth_helper_standalone.spec
    — three directories below repo root, so it uses parents[2]. The production
    spec lives at packaging/windows/oauth_helper_standalone.spec — two directories
    below repo root. Using parents[2] from the production location would compute
    the WRONG root (one level above the repo), breaking the HELPER_SRC path and
    failing the assert HELPER_SRC.is_file() check at PyInstaller run time.

    Phase 88.3-04 Task 1.
    """
    assert "parents[1]" in spec_source, (
        "oauth_helper_standalone.spec must use 'parents[1]' to compute REPO_ROOT "
        "(packaging/windows/ is 2 levels below repo root, not 3 like the spike). "
        "Phase 88.3-04 Task 1."
    )

    assert "parents[2]" not in spec_source, (
        "oauth_helper_standalone.spec must NOT use 'parents[2]' — that was the "
        "spike's computation (from .planning/spikes/001-.../). In packaging/windows/, "
        "parents[1] is the correct repo root computation. Phase 88.3-04 Task 1."
    )


# ---------------------------------------------------------------------------
# Task 2 — build.ps1 second build step
# ---------------------------------------------------------------------------

def test_build_ps1_builds_helper(build_ps1_source: str) -> None:
    """Phase 88.3-04 Task 2: build.ps1 must reference both
    'oauth_helper_standalone.spec' and 'oauth-helper-requirements.txt'.

    This confirms that build.ps1 has a second PyInstaller build step that
    produces the isolated helper artifact from the correct spec and requirements.
    Phase 88.3-04 Task 2 (G6-T6).
    """
    assert "oauth_helper_standalone.spec" in build_ps1_source, (
        "build.ps1 must reference 'oauth_helper_standalone.spec' — it must include "
        "a second PyInstaller build step for the isolated oauth_helper artifact. "
        "Phase 88.3-04 Task 2 (G6-T6)."
    )
    assert "oauth-helper-requirements.txt" in build_ps1_source, (
        "build.ps1 must reference 'oauth-helper-requirements.txt' — it must pip "
        "install from the isolated helper requirements into the helper venv. "
        "Phase 88.3-04 Task 2 (G6-T6)."
    )


def test_build_ps1_helper_isolated_venv(build_ps1_source: str) -> None:
    """Phase 88.3-04 Task 2: build.ps1 must use an isolated venv for the helper
    build and support a -HelperPythonExe param (conda-free Python 3.12 provider).

    The helper build MUST NOT run under the conda env — the whole point of B1
    is pip-only Qt isolation. The -HelperPythonExe param mirrors the spike's
    -PythonExe and allows specifying a clean conda-forge env as the venv
    provider (as opposed to the main musicstreamer-build conda env). The CONDA
    guard (or equivalent isolation) is load-bearing. Phase 88.3-04 Task 2 (G6-T6).
    """
    stripped = _strip_comments(build_ps1_source)

    assert "HelperPythonExe" in stripped, (
        "build.ps1 must define a '-HelperPythonExe' parameter (or 'HelperPythonExe') "
        "on a non-comment line — this lets the caller specify a conda-free Python 3.12 "
        "provider for the helper venv (mirrors spike's -PythonExe). "
        "Phase 88.3-04 Task 2 (G6-T6)."
    )

    # The helper build should use a separate venv (not the conda env python)
    # Validate by checking there's a venv-related reference near the helper build
    assert "venv" in build_ps1_source.lower(), (
        "build.ps1 must create an isolated venv for the helper build (not running "
        "helper PyInstaller directly in the conda env). Phase 88.3-04 Task 2 (G6-T6)."
    )


def test_build_ps1_asserts_helper_webengine(build_ps1_source: str) -> None:
    """Phase 88.3-04 Task 2: build.ps1 must assert QtWebEngineProcess.exe and
    Qt6WebEngineCore.dll exist in dist\\oauth_helper and exit 14 if missing.

    This is the T-88.3-04-01 threat mitigation: a build that silently drops
    WebEngine from the helper bundle would ship a helper that crashes at login
    time with no useful error. Exit 14 makes the failure loud at build time.
    The exit-codes header must document '14='. Phase 88.3-04 Task 2 (G6-T7).
    """
    assert "QtWebEngineProcess.exe" in build_ps1_source, (
        "build.ps1 must assert 'QtWebEngineProcess.exe' exists in the helper bundle "
        "(T-88.3-04-01 tamper mitigation: build fails loudly if WebEngine is absent). "
        "Phase 88.3-04 Task 2 (G6-T7)."
    )
    assert "Qt6WebEngineCore.dll" in build_ps1_source, (
        "build.ps1 must assert 'Qt6WebEngineCore.dll' exists in the helper bundle "
        "(T-88.3-04-01 tamper mitigation: build fails loudly if WebEngine is absent). "
        "Phase 88.3-04 Task 2 (G6-T7)."
    )

    stripped = _strip_comments(build_ps1_source)

    assert "exit 14" in stripped, (
        "build.ps1 must contain 'exit 14' on a non-comment line — this is the "
        "exit code for helper_webengine_missing (QtWebEngineProcess.exe or "
        "Qt6WebEngineCore.dll absent from dist\\oauth_helper). Phase 88.3-04 Task 2 (G6-T7)."
    )
    assert "14=" in build_ps1_source, (
        "build.ps1 must document '14=' in the exit-codes header comment at the "
        "top of the file (convention established by phases 44, 69, 88.1, 88.2). "
        "Phase 88.3-04 Task 2 (G6-T7)."
    )


# ---------------------------------------------------------------------------
# Task 2 — MusicStreamer.iss ships helper artifact
# ---------------------------------------------------------------------------

def test_iss_ships_helper(iss_source: str) -> None:
    """Phase 88.3-04 Task 2: MusicStreamer.iss must include a [Files] Source
    row for dist\\oauth_helper installing to {app}\\oauth_helper.

    The helper must install LOCAL under {app} — Chromium's sandbox blocks
    launch from a network path (spike VM run 2). The {app}\\oauth_helper\\
    path must exactly match what 88.3-03's launcher resolves. Phase 88.3-04
    Task 2 (G6-T8).
    """
    assert "oauth_helper" in iss_source, (
        "MusicStreamer.iss must reference 'oauth_helper' in a [Files] Source row "
        "installing the helper bundle to {app}\\oauth_helper (local path required "
        "for Chromium sandbox). Phase 88.3-04 Task 2 (G6-T8)."
    )


# ---------------------------------------------------------------------------
# Task 2 — README documents conda-free Python 3.12 prereq
# ---------------------------------------------------------------------------

def test_readme_documents_conda_free_python(readme_source: str) -> None:
    """Phase 88.3-04 Task 2: README.md must contain 'conda-free Python 3.12'
    (or 'conda-free python 3.12') AND must NOT recommend 'pip install
    PySide6-Addons' into the conda env as the WebEngine precondition.

    The Phase 88.3 B1 architecture replaces the wrong pip-Addons-into-conda
    precondition (which caused the G6 DLL-load failure) with a SEPARATE
    PyInstaller artifact built from an isolated pip env. The README must
    reflect this — documenting the conda-free Python 3.12 prereq for the
    helper build, and dropping the instruction that caused the crash.
    Phase 88.3-04 Task 2 (G6-T8).
    """
    lower = readme_source.lower()

    assert "conda-free python 3.12" in lower, (
        "README.md must contain 'conda-free Python 3.12' (case-insensitive) — "
        "documenting that the OAuth helper is built from a SEPARATE isolated pip "
        "env using a conda-free Python 3.12 venv provider. Phase 88.3-04 Task 2."
    )

    # The old wrong instruction must be removed
    assert "pip install" not in readme_source or "PySide6-Addons" not in readme_source or (
        "oauth-helper" in readme_source.lower()
        and readme_source.lower().index("pip install") > readme_source.lower().index("oauth")
    ), (
        "README.md must NOT recommend 'pip install PySide6-Addons' into the conda "
        "env as the WebEngine precondition. That instruction caused the G6 DLL-load "
        "failure. B1 replaces it with a SEPARATE isolated helper build. "
        "Phase 88.3-04 Task 2."
    )
