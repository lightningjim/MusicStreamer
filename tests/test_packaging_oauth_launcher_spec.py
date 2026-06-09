"""Phase 88.2 / D-05 — __main__.py argv dispatch + build.ps1 oauth-helper guard drift-guards.

Linux-runnable source-text assertions that lock in the oauth-helper entrypoint
contract. No PyInstaller install required. Mirrors tests/test_packaging_winrt_spec.py.
"""
from __future__ import annotations

from pathlib import Path

import pytest


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
def build_ps1_source() -> str:
    assert _BUILD_PS1.is_file(), f"expected build.ps1 at {_BUILD_PS1}"
    return _BUILD_PS1.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def main_py_source() -> str:
    assert _MAIN_PY.is_file(), f"expected __main__.py at {_MAIN_PY}"
    return _MAIN_PY.read_text(encoding="utf-8")


def _strip_comments(source: str) -> str:
    """Strip comment lines for negative-assertion gates.

    Both .ps1 (PowerShell) and .py (Python) use '#' as the comment
    character, so this helper works for both file types.
    """
    return "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )


def test_build_ps1_oauth_guard_present(build_ps1_source: str) -> None:
    """Phase 88.2 D-05: build.ps1 must contain the OAUTH HELPER GUARD block that
    invokes the frozen exe with --oauth-helper --self-test and emits BUILD_FAIL
    on failure.

    Drift-guard: catches accidental removal of the guard block or rephrasing
    of the canonical BUILD_FAIL literal that CI / wrapper scripts grep for.
    Mirrors test_build_ps1_smtc_smoke_guard_present in test_packaging_winrt_spec.py.
    """
    assert "OAUTH HELPER GUARD" in build_ps1_source, (
        "build.ps1 must contain the literal 'OAUTH HELPER GUARD' in the step-4d "
        "header (Phase 88.2 D-05). If you renamed the step, update this test AND "
        "the rationale block in build.ps1 together."
    )
    assert "--oauth-helper" in build_ps1_source, (
        "build.ps1 step-4d must invoke the frozen exe with --oauth-helper "
        "(Phase 88.2 D-05). This flag is dispatched by __main__.py's "
        "_run_oauth_helper() — confirming the entrypoint is reachable in the bundle."
    )
    assert "BUILD_FAIL reason=oauth_helper_entrypoint_unreachable" in build_ps1_source, (
        "build.ps1 step-4d failure branch must emit the literal "
        "'BUILD_FAIL reason=oauth_helper_entrypoint_unreachable' so CI / wrapper "
        "scripts can grep the cause from build.log (Phase 88.2 D-05)."
    )


def test_build_ps1_oauth_guard_exit_12(build_ps1_source: str) -> None:
    """Phase 88.2 D-05: build.ps1 step-4d must exit 12 on guard failure, and
    exit 12 must be documented in the exit-codes header comment.

    WR-01 compliance: the failure path must use Write-Host (not Write-Error)
    so the documented exit 12 actually fires under $ErrorActionPreference='Stop'.
    Drift-guard: catches swap back to Write-Error or removal of the exit-code
    header documentation. Mirrors test_build_ps1_smtc_smoke_guard_exit_11.
    """
    assert "exit 12" in build_ps1_source, (
        "build.ps1 step-4d must `exit 12` on oauth-helper guard failure "
        "(Phase 88.2 D-05). The exit code must match the header documentation."
    )
    assert "12=oauth" in build_ps1_source, (
        "build.ps1 exit-codes header must document '12=oauth helper entrypoint "
        "unreachable in frozen bundle (Phase 88.2 / D-05)' so a future maintainer "
        "can map the exit code to its source step. Phase 88.2 D-05."
    )
    # WR-01: Write-Host precedes BUILD_FAIL reason=oauth_helper_entrypoint_unreachable
    idx = build_ps1_source.find("BUILD_FAIL reason=oauth_helper_entrypoint_unreachable")
    assert idx != -1
    before = build_ps1_source[max(0, idx - 120) : idx + 60]
    assert "Write-Host" in before, (
        "build.ps1 step-4d 'BUILD_FAIL reason=oauth_helper_entrypoint_unreachable' "
        "must be emitted via `Write-Host ... -ForegroundColor Red` (NOT `Write-Error`). "
        "Write-Error escalates to a terminating error under "
        "$ErrorActionPreference = 'Stop' and the documented `exit 12` below it "
        "never executes — the script returns 1 instead. See Phase 65 WR-01."
    )
    after = build_ps1_source[idx : idx + 400]
    assert "exit 12" in after, (
        "build.ps1 step-4d `BUILD_FAIL reason=oauth_helper_entrypoint_unreachable` "
        "must be followed by `exit 12` within the same failure block. Otherwise the "
        "documented exit code 12 would not actually fire on the guard failure."
    )


def test_build_ps1_skip_oauth_guard_param(build_ps1_source: str) -> None:
    """Phase 88.2 D-05 / WR-02: build.ps1 must expose a SkipOauthGuard bypass
    switch mirroring the SkipSmtcGuard pattern from Phase 88.1.

    The bypass switch is required for build iteration on a VM where the
    oauth-helper dispatch is being debugged independently of the bundle.
    Drift-guard: catches accidental removal of the escape-hatch parameter.
    """
    assert "SkipOauthGuard" in build_ps1_source, (
        "build.ps1 must expose a [switch]$SkipOauthGuard parameter that bypasses "
        "the step-4d oauth-helper guard (Phase 88.2 D-05 / WR-02). Mirrors the "
        "$SkipSmtcGuard parameter added in Phase 88.1."
    )


def test_main_py_oauth_helper_flag_present(main_py_source: str) -> None:
    """Phase 88.2 D-05: __main__.py must contain the --oauth-helper argument
    registration AND the _run_oauth_helper dispatch function.

    Drift-guard: catches removal of the argv-dispatch entrypoint that makes
    `MusicStreamer.exe --oauth-helper --self-test` return 0 (the D-05 contract).
    Check is applied to comment-stripped source to avoid false positives from
    e.g. a docstring mention or disabled code block.
    """
    stripped = _strip_comments(main_py_source)
    assert "--oauth-helper" in stripped, (
        "__main__.py (comment-stripped) must contain '--oauth-helper' on an "
        "executable line — the argparse registration for the frozen-exe argv "
        "dispatch arm (Phase 88.2 D-05). Without this, "
        "`MusicStreamer.exe --oauth-helper` is an unrecognized flag and falls "
        "through to _run_gui instead of reaching _run_oauth_helper."
    )
    assert "_run_oauth_helper" in main_py_source, (
        "__main__.py must define the _run_oauth_helper function that dispatches "
        "--oauth-helper to oauth_helper.main() (Phase 88.2 D-05 / Pattern 1). "
        "This is the entrypoint that MusicStreamer.exe --oauth-helper --self-test "
        "must reach for the build.ps1 guard to exit 0."
    )


def test_main_py_self_test_handling(main_py_source: str) -> None:
    """Phase 88.2 D-05: __main__.py must handle the --self-test flag within
    _run_oauth_helper so `MusicStreamer.exe --oauth-helper --self-test` returns 0
    without opening any window or constructing a QApplication.

    Drift-guard: catches removal of the early-return self-test branch that the
    build.ps1 OAUTH HELPER GUARD depends on. If the self-test branch is missing,
    the guard would open the login window on the headless build VM, hang, and
    eventually fail with a non-zero exit — triggering a false-positive exit 12.
    """
    assert "--self-test" in main_py_source, (
        "__main__.py must contain '--self-test' in _run_oauth_helper to support "
        "the D-05 headless smoke test (Phase 88.2 D-05 / Pitfall 3). "
        "Without this early-return branch, `MusicStreamer.exe --oauth-helper "
        "--self-test` would try to open the login window on the build VM — "
        "hanging or crashing with a non-zero exit, causing a false-positive "
        "build.ps1 exit 12."
    )
