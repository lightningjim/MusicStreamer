"""Phase 88.3 / G6 — Windows spec + build.ps1 + __main__.py B1 WebEngine drift-guards.

Linux-runnable source-text assertions that lock in the B1 invariants:
WebEngine is NOT in the conda bundle (it lives in the SEPARATE oauth_helper.exe
built by 88.3-04; conda-forge has no PySide6 WebEngine bindings — spike 001).

Mirrors tests/test_packaging_winrt_spec.py's idiom (module fixtures,
_strip_comments helper, negative + positive gates).

Five guards (G6-T1..G6-T5 IDs retained — requirement INTENT "logins work from
the frozen build" is now expressed as "WebEngine is NOT in the conda artifact"):

  G6-T1 test_spec_has_no_webengine_hiddenimports     — spec has NO WebEngine strings (B1 negative)
  G6-T2 test_spec_still_has_network_and_svg          — PySide6.QtNetwork/QtSvg still present (surgical revert)
  G6-T3 test_main_py_has_no_conda_webengine_guard    — __main__.py has NO conda-process WebEngine guard
  G6-T4 test_build_ps1_has_no_conda_webengine_guard  — build.ps1 has NO conda-side WebEngine preflight/step-4e
  G6-T5 test_build_ps1_keeps_smtc_and_oauth_guards   — build.ps1 still has SMTC + OAUTH HELPER guards (no collateral)
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
# G6-T1: spec has NO WebEngine hiddenimport strings (B1 invariant: WebEngine
#         is NOT in the conda bundle — it ships in the SEPARATE oauth_helper.exe)
# ---------------------------------------------------------------------------

def test_spec_has_no_webengine_hiddenimports(spec_source: str) -> None:
    """Phase 88.3 G6-T1: MusicStreamer.spec must NOT declare QtWebEngineWidgets
    or QtWebEngineCore on any non-comment line.

    B1 invariant (spike 001 VALIDATED 2026-06-12): conda-forge ships zero PySide6
    WebEngine bindings; layering pip PySide6-Addons over conda qt6-main causes a
    Qt6Core DLL-load failure (the Phase 88.3 G6 root cause). Under B1, WebEngine
    lives exclusively in the SEPARATE pip-only oauth_helper.exe (88.3-04).
    Adding WebEngine back to this spec re-triggers the ABI conflict.

    Uses _strip_comments so a tombstone comment mentioning WebEngine does NOT
    fail this guard — only executable lines matter. See spike 001 README
    'Why This Is the Whole Ballgame'.
    """
    stripped = _strip_comments(spec_source)

    assert "PySide6.QtWebEngineWidgets" not in stripped, (
        "MusicStreamer.spec must NOT declare 'PySide6.QtWebEngineWidgets' on a "
        "non-comment line (B1 invariant). conda-forge has no PySide6 WebEngine "
        "bindings; adding this hiddenimport re-triggers the G6 DLL-load failure. "
        "WebEngine ships in the SEPARATE oauth_helper.exe (88.3-04, spike 001). "
        "Phase 88.3 G6-T1."
    )

    assert "PySide6.QtWebEngineCore" not in stripped, (
        "MusicStreamer.spec must NOT declare 'PySide6.QtWebEngineCore' on a "
        "non-comment line (B1 invariant). conda-forge has no PySide6 WebEngine "
        "bindings; adding this hiddenimport re-triggers the G6 DLL-load failure. "
        "WebEngine ships in the SEPARATE oauth_helper.exe (88.3-04, spike 001). "
        "Phase 88.3 G6-T1."
    )


# ---------------------------------------------------------------------------
# G6-T2: PySide6.QtNetwork and PySide6.QtSvg are still present in the spec
#         (proves the revert was surgical, not a wholesale hiddenimports deletion)
# ---------------------------------------------------------------------------

def test_spec_still_has_network_and_svg(spec_source: str) -> None:
    """Phase 88.3 G6-T2: comment-stripped MusicStreamer.spec must still contain
    'PySide6.QtNetwork' and 'PySide6.QtSvg' inside the Analysis() hiddenimports.

    These entries predate 88.3-01 and are unrelated to WebEngine — they cover
    QLocalServer/QLocalSocket (single-instance) and SVG icon rendering. Their
    presence confirms the 88.3-02 revert removed ONLY the WebEngine entries and
    did not accidentally delete the whole hiddenimports block. B1 invariant: a
    surgical, targeted revert, not a wholesale deletion.

    Phase 88.3 G6-T2 (spike 001 — WebEngine absent from conda artifact).
    """
    stripped = _strip_comments(spec_source)

    assert "PySide6.QtNetwork" in stripped, (
        "MusicStreamer.spec must still contain 'PySide6.QtNetwork' on a non-comment "
        "line inside Analysis() hiddenimports= (QLocalServer/QLocalSocket for "
        "single-instance; predates 88.3-01). The 88.3-02 revert must be surgical. "
        "Phase 88.3 G6-T2."
    )

    assert "PySide6.QtSvg" in stripped, (
        "MusicStreamer.spec must still contain 'PySide6.QtSvg' on a non-comment "
        "line inside Analysis() hiddenimports= (SVG icon rendering; predates "
        "88.3-01). The 88.3-02 revert must be surgical. Phase 88.3 G6-T2."
    )

    analysis_idx = spec_source.find("a = Analysis(")
    assert analysis_idx != -1, (
        "MusicStreamer.spec must contain 'a = Analysis(' to anchor the "
        "hiddenimports wiring check. Phase 88.3 G6-T2."
    )
    analysis_tail = spec_source[analysis_idx:]
    assert "PySide6.QtNetwork" in analysis_tail, (
        "MusicStreamer.spec: 'PySide6.QtNetwork' must appear inside the Analysis() "
        "block (after 'a = Analysis('). Phase 88.3 G6-T2."
    )
    assert "PySide6.QtSvg" in analysis_tail, (
        "MusicStreamer.spec: 'PySide6.QtSvg' must appear inside the Analysis() "
        "block (after 'a = Analysis('). Phase 88.3 G6-T2."
    )


# ---------------------------------------------------------------------------
# G6-T3: __main__.py has NO conda-process WebEngine guard, but STILL has
#         the --oauth-helper dispatch (88.2 arm preserved)
# ---------------------------------------------------------------------------

def test_main_py_has_no_conda_webengine_guard(main_py_source: str) -> None:
    """Phase 88.3 G6-T3: comment-stripped musicstreamer/__main__.py must NOT
    contain '_run_check_webengine' or '--check-webengine' (the conda-process
    WebEngine guard is gone under B1), but must STILL contain '--oauth-helper'
    (the 88.2 dispatch that launches the separate helper exe is preserved).

    B1 invariant (spike 001): the conda exe never touches WebEngine — it only
    launches the separate oauth_helper.exe as a child process. The
    _run_check_webengine function was a conda-process guard that attempted to
    import QtWebEngineWidgets inside the conda bundle (which has no WebEngine
    bindings), causing the G6 DLL-load failure. Under B1 it is removed.

    '--oauth-helper' must remain: the conda exe dispatches to the SEPARATE helper
    for login (88.2 _run_oauth_helper arm). Phase 88.3 G6-T3.
    """
    stripped = _strip_comments(main_py_source)

    assert "_run_check_webengine" not in stripped, (
        "musicstreamer/__main__.py must NOT contain '_run_check_webengine' on a "
        "non-comment line (B1 invariant — conda process must not touch WebEngine; "
        "the guard function has been removed in 88.3-02). "
        "WebEngine imports live exclusively in the SEPARATE oauth_helper.exe "
        "(88.3-04, spike 001). Phase 88.3 G6-T3."
    )

    assert "--check-webengine" not in stripped, (
        "musicstreamer/__main__.py must NOT contain '--check-webengine' on a "
        "non-comment line (B1 invariant — the argparse flag for the removed "
        "conda-process WebEngine guard). Phase 88.3 G6-T3."
    )

    assert "--oauth-helper" in stripped, (
        "musicstreamer/__main__.py must STILL contain '--oauth-helper' on a "
        "non-comment line (Phase 88.2 dispatch arm — preserved under B1). "
        "The conda exe uses --oauth-helper to launch the SEPARATE helper exe "
        "for login. Phase 88.3 G6-T3."
    )


# ---------------------------------------------------------------------------
# G6-T4: build.ps1 has NO conda-side WebEngine preflight, -SkipWebEngineGuard
#         param, WEBENGINE GUARD block, or pyside6_webengine_missing exit code
# ---------------------------------------------------------------------------

def test_build_ps1_has_no_conda_webengine_guard(build_ps1_source: str) -> None:
    """Phase 88.3 G6-T4: comment-stripped build.ps1 must NOT contain 'WEBENGINE
    GUARD', '--check-webengine', 'pyside6_webengine_missing', or
    'SkipWebEngineGuard'.

    B1 invariant (spike 001): no conda-side WebEngine preflight or step-4e guard
    is needed. The conda build env has no PySide6 WebEngine bindings; the preflight
    that checked for them (step-0) and the post-build guard (step-4e) are removed.
    Exit code 13 is retired (88.3-04 adds a NEW exit code for the SEPARATE helper
    bundle assertion).

    Uses _strip_comments so a tombstone comment mentioning these strings does NOT
    fail this guard — only executable lines matter. Phase 88.3 G6-T4.
    """
    stripped = _strip_comments(build_ps1_source)

    assert "WEBENGINE GUARD" not in stripped, (
        "build.ps1 must NOT contain 'WEBENGINE GUARD' on a non-comment line "
        "(B1 invariant: the step-4e conda-side WebEngine guard is removed in "
        "88.3-02; 88.3-04 adds a NEW guard for the SEPARATE helper bundle). "
        "Phase 88.3 G6-T4."
    )

    assert "--check-webengine" not in stripped, (
        "build.ps1 must NOT contain '--check-webengine' on a non-comment line "
        "(B1 invariant: the conda-process WebEngine guard invocation is removed). "
        "Phase 88.3 G6-T4."
    )

    assert "pyside6_webengine_missing" not in stripped, (
        "build.ps1 must NOT contain 'pyside6_webengine_missing' on a non-comment "
        "line (B1 invariant: the step-0 PySide6-Addons preflight for the conda env "
        "is removed; conda-forge has no WebEngine bindings). Phase 88.3 G6-T4."
    )

    assert "SkipWebEngineGuard" not in stripped, (
        "build.ps1 must NOT contain 'SkipWebEngineGuard' on a non-comment line "
        "(B1 invariant: the -SkipWebEngineGuard bypass parameter and step-4e guard "
        "are removed in 88.3-02). Phase 88.3 G6-T4."
    )


# ---------------------------------------------------------------------------
# G6-T5: build.ps1 still has SMTC SMOKE GUARD (exit 11) and OAUTH HELPER GUARD
#         (exit 12) — proves the revert did not collateral-damage 88.1/88.2 guards
# ---------------------------------------------------------------------------

def test_build_ps1_keeps_smtc_and_oauth_guards(build_ps1_source: str) -> None:
    """Phase 88.3 G6-T5: build.ps1 must STILL contain 'SMTC SMOKE GUARD' and
    'OAUTH HELPER GUARD' after the 88.3-02 revert.

    These guards were added by Phase 88.1 (SMTC, exit 11) and Phase 88.2
    (OAUTH HELPER, exit 12) and are orthogonal to WebEngine. G6-T5 confirms that
    removing step-4e WEBENGINE GUARD did NOT accidentally delete the 88.1/88.2
    guards (a copy-paste or hunk-drift error during the revert edit). B1 invariant:
    SMTC (winrt bundling) and OAUTH HELPER (frozen-exe dispatch) guards survive
    unchanged. Phase 88.3 G6-T5.
    """
    assert "SMTC SMOKE GUARD" in build_ps1_source, (
        "build.ps1 must STILL contain 'SMTC SMOKE GUARD' (Phase 88.1 / WIN-02, "
        "exit 11) after the 88.3-02 WebEngine revert. If this is missing, the "
        "88.3-02 edit accidentally removed the 88.1 guard — restore it from "
        "88.1-02-SUMMARY.md. Phase 88.3 G6-T5."
    )

    assert "OAUTH HELPER GUARD" in build_ps1_source, (
        "build.ps1 must STILL contain 'OAUTH HELPER GUARD' (Phase 88.2 / D-05, "
        "exit 12) after the 88.3-02 WebEngine revert. If this is missing, the "
        "88.3-02 edit accidentally removed the 88.2 guard — restore it from "
        "88.2-SUMMARY.md. Phase 88.3 G6-T5."
    )
