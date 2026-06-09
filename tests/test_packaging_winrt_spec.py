"""Phase 88.1 / D-04 — Windows spec + build.ps1 winrt collection drift-guards.

Linux-runnable source-text assertions that lock in the winrt bundling contract.
No PyInstaller install required. Mirrors tests/test_packaging_spec.py's idiom.
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


@pytest.fixture(scope="module")
def spec_source() -> str:
    assert _SPEC.is_file(), f"expected MusicStreamer.spec at {_SPEC}"
    return _SPEC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def build_ps1_source() -> str:
    assert _BUILD_PS1.is_file(), f"expected build.ps1 at {_BUILD_PS1}"
    return _BUILD_PS1.read_text(encoding="utf-8")


def _strip_comments(source: str) -> str:
    """Strip comment lines for negative-assertion gates.

    Both .spec (Python) and .ps1 (PowerShell) use '#' as the comment
    character, so this helper works for both file types.
    """
    return "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )


def test_spec_collects_winrt_runtime(spec_source: str) -> None:
    """Phase 88.1 D-01/D-02: spec must call collect_all("winrt-runtime") to
    capture winrt/_winrt.cpXX-win_amd64.pyd (the core pywinrt bridge).

    Without winrt-runtime, the frozen bundle cannot import the winrt namespace
    at all — WindowsMediaKeysBackend degrades to NoOp silently (G2 root cause).
    Accepts single or double quotes around the distribution name.
    """
    has_call = (
        'collect_all("winrt-runtime")' in spec_source
        or "collect_all('winrt-runtime')" in spec_source
    )
    assert has_call, (
        "MusicStreamer.spec must call collect_all('winrt-runtime') to bundle "
        "the core pywinrt bridge .pyd. The argument is the PyPI distribution "
        "name 'winrt-runtime', NOT the Python import path 'winrt'. "
        "Phase 88.1 D-01: omitting this causes winrt import to fail in the "
        "frozen bundle, silently degrading SMTC to NoOpMediaKeysBackend."
    )


def test_spec_collects_winrt_namespace_packages(spec_source: str) -> None:
    """Phase 88.1 D-01/D-02: spec must call collect_all for all four winrt
    namespace distributions so their per-namespace .pyd extensions land in
    the bundle.

    Each distribution ships its own winrt/_winrt_<ns>.cpXX.pyd at the winrt/
    namespace root — a PEP 420 namespace package with no single __init__.py.
    PyInstaller's modulegraph cannot discover these via hiddenimports alone.
    Accepts single or double quotes.
    """
    namespace_dists = [
        "winrt-Windows.Media.Playback",
        "winrt-Windows.Media",
        "winrt-Windows.Storage.Streams",
        "winrt-Windows.Foundation",
    ]
    for dist in namespace_dists:
        has_call = (
            f'collect_all("{dist}")' in spec_source
            or f"collect_all('{dist}')" in spec_source
        )
        assert has_call, (
            f"MusicStreamer.spec must call collect_all('{dist}') to bundle the "
            f"corresponding winrt namespace .pyd. The argument is the PyPI "
            f"distribution name '{dist}' (hyphen+dots, title-case), NOT the "
            f"Python import path. Phase 88.1 D-01: missing this distribution "
            f"causes SMTC to degrade to NoOpMediaKeysBackend in the frozen bundle."
        )


def test_spec_wires_winrt_binaries_into_analysis(spec_source: str) -> None:
    """Phase 88.1 D-02: the collect_all outputs for all five winrt distributions
    must be wired into Analysis via + concatenation.

    Checks both the _wr_ (winrt-runtime) and _wf_ (winrt-Windows.Foundation)
    sentinel variables — if those are present the full set must be too, since
    they are added together by the same editing step.
    """
    assert "_wr_binaries" in spec_source, (
        "MusicStreamer.spec must wire _wr_binaries into the Analysis binaries= "
        "list (Phase 88.1 D-02). The collect_all('winrt-runtime') outputs must "
        "be concatenated, not just assigned."
    )
    assert "_wr_datas" in spec_source, (
        "MusicStreamer.spec must wire _wr_datas into the Analysis datas= list "
        "(Phase 88.1 D-02)."
    )
    assert "_wr_hiddenimports" in spec_source, (
        "MusicStreamer.spec must wire _wr_hiddenimports into the Analysis "
        "hiddenimports= list (Phase 88.1 D-02)."
    )
    assert "_wf_binaries" in spec_source, (
        "MusicStreamer.spec must wire _wf_binaries into the Analysis binaries= "
        "list (Phase 88.1 D-02). The collect_all('winrt-Windows.Foundation') "
        "outputs must be concatenated, not just assigned."
    )


def test_spec_removes_old_winrt_hiddenimports(spec_source: str) -> None:
    """Phase 88.1 D-01 (negative): the four old hiddenimport-only winrt.windows.*
    strings MUST be absent from non-comment lines.

    collect_all subsumes these strings — keeping them alongside collect_all is
    harmless but indicates a partial edit. Their presence in a commented-out line
    is allowed (e.g. a tombstone comment explaining the removal).
    """
    stripped = _strip_comments(spec_source)
    assert '"winrt.windows.media.playback"' not in stripped, (
        "MusicStreamer.spec must NOT contain the old hiddenimport string "
        "'winrt.windows.media.playback' on an executable (non-comment) line. "
        "Phase 88.1 D-01: collect_all('winrt-Windows.Media.Playback') subsumes "
        "this entry. Remove it to avoid ambiguity about the bundling mechanism."
    )
    assert '"winrt.windows.media"' not in stripped, (
        "MusicStreamer.spec must NOT contain the old hiddenimport string "
        "'winrt.windows.media' on an executable (non-comment) line. "
        "Phase 88.1 D-01: collect_all('winrt-Windows.Media') subsumes this entry."
    )
    assert '"winrt.windows.storage.streams"' not in stripped, (
        "MusicStreamer.spec must NOT contain the old hiddenimport string "
        "'winrt.windows.storage.streams' on an executable (non-comment) line. "
        "Phase 88.1 D-01: collect_all('winrt-Windows.Storage.Streams') subsumes it."
    )
    assert '"winrt.windows.foundation"' not in stripped, (
        "MusicStreamer.spec must NOT contain the old hiddenimport string "
        "'winrt.windows.foundation' on an executable (non-comment) line. "
        "Phase 88.1 D-01: collect_all('winrt-Windows.Foundation') subsumes it."
    )


def test_build_ps1_smtc_smoke_guard_present(build_ps1_source: str) -> None:
    """Phase 88.1 D-05: build.ps1 must contain a step-4c SMTC smoke guard that
    invokes the frozen exe with --check-mediakeys and emits BUILD_FAIL on failure.

    Drift-guard: catches accidental removal of step 4c or rephrasing of the
    canonical BUILD_FAIL literal that CI / wrapper scripts grep for.
    """
    assert "SMTC SMOKE GUARD" in build_ps1_source, (
        "build.ps1 must contain the literal 'SMTC SMOKE GUARD' in the step 4c "
        "header. If you renamed the step, update this test AND the rationale "
        "block in build.ps1 together. Phase 88.1 D-05."
    )
    assert "--check-mediakeys" in build_ps1_source, (
        "build.ps1 step 4c must invoke the frozen exe with --check-mediakeys "
        "(Phase 88.1 D-05). This flag is implemented by __main__.py's "
        "_run_check_mediakeys() and exits 0 only if WindowsMediaKeysBackend "
        "is constructed — confirming the winrt .pyd files landed in the bundle."
    )
    assert "BUILD_FAIL reason=smtc_backend_not_loaded" in build_ps1_source, (
        "build.ps1 step 4c failure branch must emit the literal "
        "'BUILD_FAIL reason=smtc_backend_not_loaded' so CI / wrapper scripts "
        "can grep the cause from build.log. Phase 88.1 D-05."
    )


def test_build_ps1_smtc_smoke_guard_exit_11(build_ps1_source: str) -> None:
    """Phase 88.1 D-05: build.ps1 step 4c must exit 11 on SMTC guard failure,
    and exit 11 must be documented in the exit-codes header comment.

    WR-01 compliance: the failure path must use Write-Host (not Write-Error)
    so the documented exit 11 actually fires under $ErrorActionPreference='Stop'.
    Drift-guard: catches swap back to Write-Error or removal of the exit-code
    header documentation.
    """
    assert "exit 11" in build_ps1_source, (
        "build.ps1 step 4c must `exit 11` on SMTC guard failure (Phase 88.1 "
        "D-05 / WIN-02). The exit code must match the header documentation."
    )
    assert "11=smtc" in build_ps1_source, (
        "build.ps1 exit-codes header must document '11=smtc backend not loaded "
        "in frozen bundle (Phase 88.1 / WIN-02)' so a future maintainer can map "
        "the exit code to its source step. Phase 88.1 D-05."
    )
    # WR-01: verify Write-Host precedes the BUILD_FAIL literal (not Write-Error)
    idx = build_ps1_source.find("BUILD_FAIL reason=smtc_backend_not_loaded")
    assert idx != -1
    before = build_ps1_source[max(0, idx - 120) : idx + 60]
    assert "Write-Host" in before, (
        "build.ps1 step 4c 'BUILD_FAIL reason=smtc_backend_not_loaded' must be "
        "emitted via `Write-Host ... -ForegroundColor Red` (NOT `Write-Error`). "
        "Write-Error escalates to a terminating error under "
        "$ErrorActionPreference = 'Stop' and the documented `exit 11` below it "
        "never executes — the script returns 1 instead. See Phase 65 WR-01."
    )
    after = build_ps1_source[idx : idx + 400]
    assert "exit 11" in after, (
        "build.ps1 step 4c `BUILD_FAIL reason=smtc_backend_not_loaded` must be "
        "followed by `exit 11` within the same failure block. Otherwise the "
        "documented exit code 11 would not actually fire on SMTC guard failure."
    )
