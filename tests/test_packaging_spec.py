"""Phase 65 / VER-02-H — PyInstaller spec source-text assertions.

The Windows PyInstaller bundle must ship musicstreamer's dist-info so that
importlib.metadata.version("musicstreamer") resolves inside the bundled exe
(used by both __main__._run_gui's setApplicationVersion call AND the
hamburger menu version footer). Without copy_metadata("musicstreamer"),
the bundle would raise PackageNotFoundError when MainWindow constructs.

These tests are SOURCE-TEXT tests — they read the .spec file as text and
assert substrings are present. They do NOT require PyInstaller to be
installed in the test environment, and they do NOT execute the .spec.

Pattern: mirrors tests/test_main_run_gui_ordering.py's `read_text` +
substring-assertion idiom (PATTERNS §8 — closer analog than
test_pkg03_compliance.py, which is a multi-file glob over musicstreamer/*.py).

Phase 65 Plan 04 extends this with two `build_ps1_source` tests covering
UAT gap VER-02-J (stale dist-info bundling defense): pre-bundle clean
step 3c + post-bundle dist-info assertion step 4a in build.ps1.
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


def test_spec_imports_copy_metadata(spec_source: str) -> None:
    """Phase 65 D-08: spec extends the existing PyInstaller.utils.hooks import
    to include copy_metadata alongside collect_all."""
    assert "copy_metadata" in spec_source, (
        "MusicStreamer.spec must import copy_metadata from "
        "PyInstaller.utils.hooks (alongside collect_all) so musicstreamer's "
        "dist-info ships in the Windows bundle."
    )
    assert (
        "from PyInstaller.utils.hooks import collect_all, copy_metadata"
        in spec_source
        or "from PyInstaller.utils.hooks import copy_metadata, collect_all"
        in spec_source
    ), (
        "Expected `from PyInstaller.utils.hooks import collect_all, "
        "copy_metadata` (or symmetric ordering) — the existing collect_all "
        "import line should be extended, not duplicated on a separate line."
    )


def test_spec_includes_copy_metadata_for_musicstreamer(spec_source: str) -> None:
    """Phase 65 D-08 / VER-02-H: spec calls copy_metadata("musicstreamer")
    so dist-info ships in the bundle. Accept either single- or double-quoted
    argument; the project does not enforce a quote style here."""
    has_call = (
        'copy_metadata("musicstreamer")' in spec_source
        or "copy_metadata('musicstreamer')" in spec_source
    )
    assert has_call, (
        "MusicStreamer.spec must call copy_metadata('musicstreamer') so the "
        "bundle ships musicstreamer.dist-info. Without this, "
        "importlib.metadata.version('musicstreamer') raises "
        "PackageNotFoundError inside the bundled exe at MainWindow "
        "construction time."
    )


def test_spec_concatenates_ms_datas_into_datas_list(spec_source: str) -> None:
    """Phase 65 D-08: the result of copy_metadata is appended to the datas
    list — proves the import isn't dead code and that dist-info actually
    ships. The variable name follows the existing _cn_datas / _sl_datas /
    _yt_datas convention."""
    assert "_ms_datas = copy_metadata" in spec_source, (
        "Expected `_ms_datas = copy_metadata(...)` assignment alongside "
        "the existing _cn_datas / _sl_datas / _yt_datas collect_all peers."
    )
    assert "+ _ms_datas" in spec_source, (
        "Expected `+ _ms_datas` in the datas concatenation at the "
        "Analysis(...) block — proves the dist-info actually ships in "
        "the bundle (not just imported and forgotten)."
    )


def test_spec_has_no_try_except_around_copy_metadata(spec_source: str) -> None:
    """Phase 65 D-08 (negative): CONTEXT explicitly prohibits a try/except
    fallback to a placeholder version. The bundle must fail loudly with
    PackageNotFoundError if metadata is missing, not ship a silent
    placeholder string. This regression-lock catches a future "well-meaning"
    defensive edit that would mask a broken install.

    Heuristic: scan the 200 bytes BEFORE the copy_metadata call site for
    `try:` / `PackageNotFoundError` tokens. This is intentionally a coarse
    proximity check — it catches the realistic regression shape (defensive
    wrap directly around the call) without requiring a full Python AST
    parse of the spec. If a future spec edit legitimately needs an
    unrelated try block within 200 bytes of the copy_metadata call, this
    test should be updated to anchor more precisely on the copy_metadata
    call's enclosing block (e.g. via ast.parse + walking the tree)."""
    # Find the copy_metadata call site and check the surrounding 200 chars.
    idx = spec_source.find('copy_metadata("musicstreamer")')
    if idx == -1:
        idx = spec_source.find("copy_metadata('musicstreamer')")
    assert idx != -1, "copy_metadata('musicstreamer') call not found"
    # Look at the 200 bytes BEFORE the call (and 100 bytes after) for
    # `try:` or `PackageNotFoundError` tokens — see docstring for the
    # heuristic limitation.
    nearby = spec_source[max(0, idx - 200) : idx + 100]
    assert "try:" not in nearby, (
        "Phase 65 D-08 explicit prohibition: NO try/except wrapping "
        "copy_metadata. Bundle must fail loudly if metadata is missing."
    )
    assert "PackageNotFoundError" not in nearby, (
        "Phase 65 D-08 explicit prohibition: NO PackageNotFoundError catch "
        "around copy_metadata. Hard fail at build time is the contract."
    )


def test_build_ps1_pre_bundle_clean_present(build_ps1_source: str) -> None:
    """Phase 65 Plan 04 / VER-02-J defense: build.ps1 must contain a
    pre-bundle clean step that uninstalls + reinstalls musicstreamer in
    the build env BEFORE invoking pyinstaller. This guarantees exactly
    one fresh musicstreamer-{version}.dist-info exists when
    copy_metadata("musicstreamer") (MusicStreamer.spec line 41) runs,
    closing UAT gap VER-02-J (Win11 VM bundle showed v1.1.0 from a
    stale dist-info).

    DRIFT-GUARD: catches accidental removal of step 3c. If a future
    maintainer rewrites the clean step's commands (e.g. switches from
    `uv pip uninstall + install` to `uv sync --reinstall-package
    musicstreamer`), update the substring assertions below.
    """
    # Rationale tag — must cite the gap so the link to this regression
    # is grep-discoverable from the build script.
    assert "VER-02-J" in build_ps1_source, (
        "build.ps1 must reference VER-02-J in the pre-bundle clean step "
        "header so a future maintainer can trace the rationale. Without "
        "this tag, the step looks like dead code and is at risk of "
        "removal during script cleanup."
    )

    # Uninstall command — first half of the defense.
    assert "uv pip uninstall musicstreamer" in build_ps1_source, (
        "build.ps1 step 3c must call `uv pip uninstall musicstreamer` "
        "before running PyInstaller, so any stale dist-info from a "
        "prior install is removed from the build env."
    )

    # Reinstall command — second half. Accept either the explicit
    # editable install (preferred) OR `uv sync --reinstall-package
    # musicstreamer` form.
    has_reinstall = (
        "uv pip install -e" in build_ps1_source
        or "uv sync --reinstall-package musicstreamer" in build_ps1_source
    )
    assert has_reinstall, (
        "build.ps1 step 3c must reinstall musicstreamer after "
        "uninstalling, via either `uv pip install -e ..\\..` (editable, "
        "preferred) or `uv sync --reinstall-package musicstreamer`. "
        "Without the reinstall, copy_metadata has no dist-info to ship."
    )

    # Failure branch — the step must HAVE an exit-on-failure check, not
    # silently continue.
    assert "exit 8" in build_ps1_source, (
        "build.ps1 step 3c must exit 8 on reinstall failure (matching "
        "the exit-codes header at line 5). Silent failure here would "
        "let a wrong dist-info reach pyinstaller."
    )

    # Phase 65 WR-01 follow-up: `exit 8` must be reachable. With
    # `$ErrorActionPreference = "Stop"`, `Write-Error ... ; exit 8`
    # short-circuits at Write-Error (escalated to a terminating error)
    # and the `exit 8` line never executes — the script falls through
    # the surrounding try/finally and PowerShell emits its default
    # exit code 1. Drift-guard against accidental Write-Error
    # reintroduction by requiring the BUILD_FAIL diagnostic for the
    # pre-bundle clean failure path to ship via Write-Host (which does
    # not terminate under Stop).
    assert "BUILD_FAIL reason=pre_bundle_clean_failed" in build_ps1_source, (
        "build.ps1 step 3c must emit a `BUILD_FAIL "
        "reason=pre_bundle_clean_failed` diagnostic on the failure "
        "path so CI / wrapper scripts can grep the cause from build.log."
    )
    # Locate the failure-path block and verify `exit 8` immediately
    # follows a Write-Host (not a Write-Error which would terminate).
    fail_idx = build_ps1_source.find("BUILD_FAIL reason=pre_bundle_clean_failed")
    assert fail_idx != -1
    fail_block = build_ps1_source[fail_idx : fail_idx + 400]
    assert "Write-Host" in build_ps1_source[max(0, fail_idx - 80) : fail_idx + 60], (
        "build.ps1 step 3c BUILD_FAIL diagnostic must be emitted via "
        "`Write-Host ... -ForegroundColor Red` (NOT `Write-Error`). "
        "Write-Error escalates to a terminating error under "
        "$ErrorActionPreference = \"Stop\" and the documented `exit 8` "
        "below it never executes — the script returns 1 instead. See "
        "Phase 65 WR-01 for the full rationale."
    )
    assert "exit 8" in fail_block, (
        "build.ps1 step 3c `exit 8` must appear within the BUILD_FAIL "
        "pre_bundle_clean_failed block (i.e. immediately after the "
        "diagnostic Write-Host), not orphaned elsewhere. Otherwise the "
        "exit code documented at line 5 would not actually fire on "
        "reinstall failure."
    )


def test_build_ps1_post_bundle_dist_info_assertion_present(build_ps1_source: str) -> None:
    """Phase 65 Plan 04 / VER-02-J defense: build.ps1 must contain a
    post-bundle assertion step that scans dist/MusicStreamer/_internal
    for musicstreamer-*.dist-info, asserts exactly one exists, and
    asserts its METADATA Version: matches pyproject.toml
    [project].version. This catches any stale dist-info that survives
    step 3c's pre-bundle clean (defense in depth).

    DRIFT-GUARD: catches accidental removal of step 4a. The negative
    failure-mode this defends against — a wrong bundle silently
    shipping — is high-severity (production user sees wrong version),
    so the assertion is locked here AND in the build script.
    """
    # Rationale tag — same shape as test_build_ps1_pre_bundle_clean_present.
    # Note: a single 'VER-02-J' appearance covers both step 3c and 4a if
    # they share a single VER-02-J rationale block, but typically each
    # step has its own header. Allow either: just assert the tag is
    # present at least twice (once per step) OR a `count >= 2` shape.
    # We use a simple count check.
    assert build_ps1_source.count("VER-02-J") >= 2, (
        "build.ps1 must reference VER-02-J in BOTH step 3c (pre-bundle "
        "clean) AND step 4a (post-bundle assertion) headers. Found "
        f"{build_ps1_source.count('VER-02-J')} occurrence(s); expected "
        "at least 2 (one per defensive step)."
    )

    # Get-ChildItem against the bundled _internal directory with the
    # dist-info filter — the structural shape of the singleton check.
    assert 'Get-ChildItem' in build_ps1_source, (
        "build.ps1 step 4a must use Get-ChildItem to enumerate "
        "musicstreamer-*.dist-info directories in the bundle."
    )
    assert 'musicstreamer-*.dist-info' in build_ps1_source, (
        "build.ps1 step 4a must filter Get-ChildItem with "
        "`musicstreamer-*.dist-info` to find the bundled dist-info(s)."
    )

    # The singleton check — count must be exactly 1, not 0, not 2+.
    # PowerShell idiom: `$msDistInfos.Count -ne 1` or equivalent.
    assert ".Count -ne 1" in build_ps1_source, (
        "build.ps1 step 4a must assert exactly one musicstreamer-*.dist-info "
        "exists in the bundle (count != 1 → fail). A 0-count means the "
        "spec dropped copy_metadata; a 2+ count is the VER-02-J failure "
        "mode (stale dist-info shipped alongside fresh one)."
    )

    # The version-match check — bundled METADATA Version: must equal
    # pyproject.toml [project].version (i.e. $appVersion).
    assert "$bundledVersion -ne $appVersion" in build_ps1_source, (
        "build.ps1 step 4a must compare the bundled METADATA Version: "
        "line to pyproject.toml [project].version (the `$appVersion` "
        "variable already used by step 6 / iscc.exe). Without this "
        "compare, a stale 1.1.0 dist-info that somehow becomes the "
        "singleton (after pre-bundle clean removed the new one) would "
        "still ship as a wrong-but-singleton bundle."
    )

    # Failure branch — exit 9 on any of the three failure modes.
    assert "exit 9" in build_ps1_source, (
        "build.ps1 step 4a must exit 9 on assertion failure (matching "
        "the exit-codes header at line 5). The three failure modes "
        "(no _internal dir, count != 1, version mismatch) all share "
        "this exit code."
    )

    # Phase 65 WR-01 follow-up: each of the three step-4a failure paths
    # must be reachable. Drift-guard against accidental Write-Error
    # reintroduction by requiring each BUILD_FAIL reason string is
    # paired with `Write-Host` (not `Write-Error`) within ~120 chars
    # AND followed by `exit 9` within ~400 chars. With
    # `$ErrorActionPreference = "Stop"`, Write-Error escalates to a
    # terminating error and the `exit 9` line never executes — the
    # script returns 1 instead, breaking CI branching on $LASTEXITCODE.
    fail_reasons = (
        "BUILD_FAIL reason=bundle_internal_not_found",
        "BUILD_FAIL reason=post_bundle_distinfo_not_singleton",
        "BUILD_FAIL reason=bundled_metadata_missing",
        "BUILD_FAIL reason=bundled_metadata_no_version_line",
        "BUILD_FAIL reason=post_bundle_version_mismatch",
    )
    for reason in fail_reasons:
        assert reason in build_ps1_source, (
            f"build.ps1 step 4a must emit `{reason}` diagnostic so "
            "CI / wrapper scripts can grep the cause from build.log."
        )
        idx = build_ps1_source.find(reason)
        assert idx != -1
        # Look 120 chars BEFORE the BUILD_FAIL token for the diagnostic
        # emitter (Write-Host vs Write-Error). Write-Error here would
        # silently regress WR-01.
        before = build_ps1_source[max(0, idx - 120) : idx + 50]
        assert "Write-Host" in before, (
            f"build.ps1 step 4a `{reason}` must be emitted via "
            "`Write-Host ... -ForegroundColor Red` (NOT `Write-Error`). "
            "Write-Error escalates to a terminating error under "
            "$ErrorActionPreference = \"Stop\" and the documented "
            "`exit 9` below it never executes — the script returns 1 "
            "instead. See Phase 65 WR-01 for the full rationale."
        )
        # The matching `exit 9` should appear within the next ~400 chars
        # (allowing for multi-line diagnostic dumps before the exit).
        after = build_ps1_source[idx : idx + 400]
        assert "exit 9" in after, (
            f"build.ps1 step 4a `{reason}` must be followed by `exit 9` "
            "within the same failure block. Otherwise the documented "
            "exit code at line 5 would not actually fire."
        )
