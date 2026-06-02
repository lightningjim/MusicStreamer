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
step 3c + post-bundle dist-info assertion step 4a in build.ps1. Phase 65
Plan 05 amends the step 3c drift-guard to lock the `python -m pip`
command literals (replacing the original `uv pip` literals) after the
2026-05-09 retest revealed `uv` is not on PATH in the Win11 spike conda
env; the step 4a drift-guard is unchanged.
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

_README = (
    Path(__file__).resolve().parent.parent
    / "packaging"
    / "windows"
    / "README.md"
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
def readme_source() -> str:
    assert _README.is_file(), f"expected README.md at {_README}"
    return _README.read_text(encoding="utf-8")


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

    Phase 65 Plan 05 amendment: the original Plan 65-04 commands were
    `uv pip uninstall musicstreamer -y` + `uv pip install -e ..\\..`,
    but Win11 VM UAT (2026-05-09) surfaced that `uv` is not on PATH in
    the validated conda-forge spike env (per
    .claude/skills/spike-findings-musicstreamer/). Plan 65-05 swapped
    both calls to `python -m pip ...` (which IS on PATH in any conda
    env AND any uv-managed venv on Linux dev). The substring
    assertions below now lock the `python -m pip` literal as the
    primary; the legacy `uv pip install -e` / `uv sync
    --reinstall-package musicstreamer` shapes stay accepted in the
    reinstall set purely for forward-compat (in case a future
    maintainer reintroduces a uv-managed env on Windows).
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
    # Plan 65-05: swapped from `uv pip` to `python -m pip` because
    # `uv` is not provisioned in the Win11 spike conda env. The
    # `python -m pip` literal is now the authoritative substring;
    # `uv pip uninstall musicstreamer` must NOT be present on
    # executable lines (the negative check at the bottom of this
    # function enforces that).
    assert "python -m pip uninstall musicstreamer" in build_ps1_source, (
        "build.ps1 step 3c must call `python -m pip uninstall musicstreamer` "
        "before running PyInstaller, so any stale dist-info from a "
        "prior install is removed from the build env. (Plan 65-05 swap: "
        "was `uv pip uninstall musicstreamer` in Plan 65-04; switched "
        "to `python -m pip` so the step runs in the conda-forge spike "
        "env on the Win11 VM where `uv` is not on PATH.)"
    )

    # Reinstall command — second half. Accept the new Plan 65-05
    # `python -m pip install -e` form as the primary, with the legacy
    # `uv pip install -e` and `uv sync --reinstall-package
    # musicstreamer` shapes still accepted for forward-compat (in
    # case a future maintainer reintroduces a uv-managed env on
    # Windows). The CURRENT build.ps1 must contain the `python -m
    # pip install -e` form; the others are tolerated, not required.
    has_reinstall = (
        "python -m pip install -e" in build_ps1_source
        or "uv pip install -e" in build_ps1_source
        or "uv sync --reinstall-package musicstreamer" in build_ps1_source
    )
    assert has_reinstall, (
        "build.ps1 step 3c must reinstall musicstreamer after "
        "uninstalling, via one of: `python -m pip install -e ..\\..` "
        "(Plan 65-05 default; works in any conda env), `uv pip install "
        "-e ..\\..` (legacy Plan 65-04 form; only works on hosts with "
        "uv), or `uv sync --reinstall-package musicstreamer` (legacy "
        "alternative). Without the reinstall, copy_metadata has no "
        "dist-info to ship."
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

    # Plan 65-05 negative drift-guard: `uv pip uninstall musicstreamer`
    # and `uv pip install -e` MUST NOT appear on EXECUTABLE lines after
    # the swap. They may still appear in comment lines (the rationale
    # block legitimately discusses the pre-Plan-65-05 history), so we
    # split build.ps1 by line, drop comment-only lines (lines whose
    # first non-whitespace char is `#`), and assert the `uv pip` tokens
    # are absent from what remains. This catches the partial-revert
    # failure mode where a maintainer leaves the old `uv pip` calls in
    # place "as a fallback" — on the Win11 VM, the first `uv pip` call
    # crashes the script before any `python -m pip` line can execute,
    # so partial-revert is functionally equivalent to no-fix.
    executable_lines = "\n".join(
        line for line in build_ps1_source.splitlines()
        if not line.lstrip().startswith("#")
    )
    assert "uv pip uninstall musicstreamer" not in executable_lines, (
        "build.ps1 step 3c must NOT call `uv pip uninstall "
        "musicstreamer` on an executable (non-comment) line. Plan "
        "65-05 swapped this to `python -m pip uninstall musicstreamer` "
        "because `uv` is not on PATH in the Win11 spike conda env. If "
        "this assertion fires, a maintainer has either reverted the "
        "swap or left both forms in place; on Win11 the `uv pip` line "
        "crashes the script before the `python -m pip` line runs, so "
        "partial-revert is functionally equivalent to full-revert."
    )
    assert "uv pip install -e" not in executable_lines, (
        "build.ps1 step 3c must NOT call `uv pip install -e` on an "
        "executable (non-comment) line. Same rationale as above — Plan "
        "65-05 requires `python -m pip install -e ..\\..` for "
        "Win11-VM compatibility."
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


def test_readme_conda_recipe_lists_every_required_plugin_package(
    readme_source: str,
) -> None:
    """Phase 69 / P-01: packaging/windows/README.md conda recipe must
    mention every conda-forge package referenced in
    tools/check_bundle_plugins.py REQUIRED_PLUGIN_DLLS values.

    Drift-guard: catches the failure mode where a future maintainer
    edits the build-time guard's required-plugin list (e.g. adds Opus
    or Vorbis plugins after a new codec issue) but forgets to add the
    matching conda package to the README recipe. Without this test, the
    build would fail at G-01 plugin-presence check (exit code 10) only
    after a full PyInstaller run -- wasting ~5 minutes of build time
    per drift incident. This test fires in <1 second on Linux dev CI.

    Pitfall 5 mitigation: the regex anchors on the fenced code block's
    closing ``` so a stray `conda create -n musicstreamer-build`
    reference in markdown prose (e.g. a comment example) cannot match
    instead of the canonical recipe block.
    """
    import re

    from tools.check_bundle_plugins import REQUIRED_PLUGIN_DLLS

    # Locate the conda create / conda env update block in README.md.
    # The block is fenced as a powershell code block; the regex
    # terminates at the closing fence so comments outside fenced blocks
    # cannot match (Phase 69 RESEARCH Pitfall 5).
    block_match = re.search(
        r"conda create -n musicstreamer-build[^\n]*\n((?:[^\n]*\n)+?)```",
        readme_source,
    )
    assert block_match, (
        "packaging/windows/README.md must contain a fenced PowerShell "
        "code block starting with `conda create -n musicstreamer-build` "
        "(this is the canonical recipe location per Phase 69 DOC-02). "
        "If you renamed the env or moved the recipe, update this test "
        "AND tools/check_bundle_plugins.py together."
    )
    recipe_block = block_match.group(0)

    required_packages = {pkg for (_, pkg) in REQUIRED_PLUGIN_DLLS.values()}
    missing = [pkg for pkg in required_packages if pkg not in recipe_block]
    assert not missing, (
        "Phase 69 / P-01 drift-guard FAIL: the following conda-forge "
        f"package(s) are in tools/check_bundle_plugins.py "
        f"REQUIRED_PLUGIN_DLLS but absent from "
        f"packaging/windows/README.md's conda recipe block: {missing}. "
        f"Either remove them from the required-plugin list (if the "
        f"build-time guard no longer needs them) or add them to the "
        f"README recipe so a fresh build host produces a bundle that "
        f"passes the post-bundle plugin-presence guard."
    )


def test_build_ps1_invokes_plugin_guard_with_exit_10(
    build_ps1_source: str,
) -> None:
    """Phase 69 / G-01 / WIN-05: build.ps1 must contain a post-bundle
    plugin-presence guard step (step 4b) that invokes
    tools/check_bundle_plugins.py with the WR-01-compliant failure
    discipline (Write-Host -ForegroundColor Red + exit 10).

    Drift-guard: catches accidental removal of step 4b, accidental swap
    from Write-Host to Write-Error (which would escalate to a
    terminating error under $ErrorActionPreference = "Stop" and skip
    the documented exit 10 -- script returns 1 instead, breaking CI
    branching on $LASTEXITCODE), or accidental removal of the
    exit-code header documentation.
    """
    # Rationale-tag check: the step header literal must stay stable so
    # future grep discovery is reliable.
    assert "POST-BUNDLE PLUGIN GUARD" in build_ps1_source, (
        "build.ps1 must contain the literal `POST-BUNDLE PLUGIN GUARD` "
        "in the step 4b header. If you renamed the step, update this "
        "test AND the rationale block in build.ps1 together."
    )

    # Invocation-substring check: the PowerShell call site must use the
    # canonical Windows backslash path to tools/check_bundle_plugins.py.
    assert "python ..\\..\\tools\\check_bundle_plugins.py" in build_ps1_source, (
        "build.ps1 step 4b must invoke "
        "`python ..\\..\\tools\\check_bundle_plugins.py` (relative to "
        "the packaging/windows/ working directory). If the path layout "
        "changes, update this test alongside build.ps1."
    )

    # BUILD_FAIL substring check: drift-guard against a maintainer
    # rephrasing the failure reason away from the canonical literal
    # that CI / wrapper scripts grep for.
    assert "BUILD_FAIL reason=plugin_missing" in build_ps1_source, (
        "build.ps1 step 4b failure branch must emit the literal "
        "`BUILD_FAIL reason=plugin_missing` so wrapper scripts can "
        "grep the cause from build.log."
    )

    # Exit-code substring checks: both the literal failure-block
    # `exit 10` AND the header-comment documentation must be present.
    assert "exit 10" in build_ps1_source, (
        "build.ps1 step 4b must `exit 10` on plugin-missing failure "
        "(matches the exit-codes header documentation at line 5-7)."
    )
    assert "10=post-bundle plugin-presence guard fail" in build_ps1_source, (
        "build.ps1 exit-codes header (line 5-7 region) must document "
        "`10=post-bundle plugin-presence guard fail (Phase 69)` so a "
        "future maintainer can map the exit code to its source step "
        "without grep-spelunking."
    )

    # WR-01 Write-Host adjacency check -- locate the BUILD_FAIL
    # diagnostic and verify it sits within a Write-Host (NOT
    # Write-Error) line, followed by exit 10 within 400 chars of the
    # same site. Write-Error escalates to a terminating error under
    # $ErrorActionPreference = "Stop" and the documented `exit 10` line
    # never executes -- PowerShell returns 1 instead. See Phase 65
    # WR-01 rationale in build.ps1 lines 18-27.
    idx = build_ps1_source.find("BUILD_FAIL reason=plugin_missing")
    assert idx != -1
    before = build_ps1_source[max(0, idx - 120) : idx + 50]
    assert "Write-Host" in before, (
        "build.ps1 step 4b `BUILD_FAIL reason=plugin_missing` must be "
        "emitted via `Write-Host ... -ForegroundColor Red` (NOT "
        "`Write-Error`). Write-Error escalates to a terminating error "
        "under $ErrorActionPreference = \"Stop\" and the documented "
        "`exit 10` below it never executes -- the script returns 1 "
        "instead. See Phase 65 WR-01 for the full rationale."
    )
    after = build_ps1_source[idx : idx + 400]
    assert "exit 10" in after, (
        "build.ps1 step 4b `BUILD_FAIL reason=plugin_missing` must be "
        "followed by `exit 10` within the same failure block. "
        "Otherwise the documented exit code at line 7 would not "
        "actually fire on plugin-missing failure."
    )


# ===========================================================================
# Phase 86 / Flatpak drift-guard suite (D-13 / D-15)
#
# ALL guards parse the manifest YAML as data via yaml.safe_load — NOT text
# grep.  A permission placed inside a YAML comment is invisible to the parser
# and correctly stays out of finish-args
# (feedback_drift_guard_presence_not_semantics / T-86-07).
#
# Requirements covered: FP-01, FP-03, FP-04, FP-05, FP-06, FP-08, FP-09, FP-10
# ===========================================================================

import shutil
import subprocess

import yaml

# ---------------------------------------------------------------------------
# Path constants — Flatpak artifacts produced by Plan 01
# ---------------------------------------------------------------------------

_FLATPAK_MANIFEST = (
    Path(__file__).resolve().parent.parent / "io.github.kcreasey.MusicStreamer.yaml"
)
_PYTHON3_MODULES = (
    Path(__file__).resolve().parent.parent / "python3-modules.yaml"
)
_FLATPAK_DESKTOP = (
    Path(__file__).resolve().parent.parent
    / "tools" / "linux-flatpak" / "desktop"
    / "io.github.kcreasey.MusicStreamer.desktop"
)
_FLATPAK_METAINFO = (
    Path(__file__).resolve().parent.parent
    / "tools" / "linux-flatpak" / "metainfo"
    / "io.github.kcreasey.MusicStreamer.metainfo.xml"
)


# ---------------------------------------------------------------------------
# Module-scope YAML fixture — parse once, share across all manifest tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def manifest_data() -> dict:
    """Load and parse the Flatpak manifest as structured data (D-13).

    Uses yaml.safe_load so that permissions hidden in YAML comments are
    invisible to the parser and correctly absent from finish-args.
    """
    assert _FLATPAK_MANIFEST.is_file(), (
        f"Flatpak manifest not found at {_FLATPAK_MANIFEST}. "
        "Plan 01 must produce this artifact before Plan 03 tests can run."
    )
    return yaml.safe_load(_FLATPAK_MANIFEST.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# FP-01: App ID
# ---------------------------------------------------------------------------


def test_flatpak_manifest_id(manifest_data: dict) -> None:
    """FP-01: manifest id must be the locked app ID."""
    assert manifest_data["id"] == "io.github.kcreasey.MusicStreamer", (
        "Flatpak manifest id must be exactly 'io.github.kcreasey.MusicStreamer' (FP-01)."
    )


# ---------------------------------------------------------------------------
# FP-03: Runtime version pins
# ---------------------------------------------------------------------------


def test_flatpak_runtime_version_pins(manifest_data: dict) -> None:
    """FP-03: KDE Platform/BaseApp version, ffmpeg-full version, and node20
    presence are all pinned to the locked values.

    Checked as parsed data so a comment-only version string cannot slip through.
    """
    assert manifest_data.get("runtime-version") == "6.8", (
        "Manifest runtime-version must be '6.8' (FP-03). "
        f"Got: {manifest_data.get('runtime-version')!r}"
    )
    assert manifest_data.get("base-version") == "6.8", (
        "Manifest base-version must be '6.8' (FP-03 / io.qt.PySide.BaseApp). "
        f"Got: {manifest_data.get('base-version')!r}"
    )
    # ffmpeg-full extension version pin
    extensions = manifest_data.get("add-extensions", {})
    assert isinstance(extensions, dict), (
        "Expected 'add-extensions' to be a YAML mapping."
    )
    ffmpeg_ext = extensions.get("org.freedesktop.Platform.ffmpeg-full")
    assert ffmpeg_ext is not None, (
        "Manifest must declare org.freedesktop.Platform.ffmpeg-full under "
        "add-extensions (FP-03 / AAC codec path)."
    )
    assert ffmpeg_ext.get("version") == "24.08", (
        "org.freedesktop.Platform.ffmpeg-full version must be '24.08' (FP-03). "
        f"Got: {ffmpeg_ext.get('version')!r}"
    )
    # node20 SDK extension presence
    sdk_extensions = manifest_data.get("sdk-extensions", [])
    assert "org.freedesktop.Sdk.Extension.node20" in sdk_extensions, (
        "Manifest sdk-extensions must include org.freedesktop.Sdk.Extension.node20 "
        "(FP-03 / yt-dlp EJS solver requires Node at runtime)."
    )


# ---------------------------------------------------------------------------
# FP-04 / FP-05 / D-01: finish-args allow-list
# ---------------------------------------------------------------------------


def test_flatpak_finish_args_allow_list(manifest_data: dict) -> None:
    """FP-04 + FP-05 + D-01: every required finish-arg including the narrow :ro
    mount must be present in the parsed finish-args list.

    Parses YAML as data (D-13) so args hidden in YAML comments are invisible.
    """
    args = manifest_data.get("finish-args", [])
    assert isinstance(args, list), "finish-args must be a YAML sequence."

    required = [
        "--share=network",
        "--socket=pulseaudio",
        "--socket=wayland",
        "--socket=fallback-x11",
        "--own-name=org.mpris.MediaPlayer2.MusicStreamer",
        "--filesystem=~/.local/share/musicstreamer:ro",
        "--env=QTWEBENGINE_DISABLE_SANDBOX=1",
    ]
    for arg in required:
        assert arg in args, (
            f"Required finish-arg {arg!r} is absent from the parsed manifest "
            "finish-args list (FP-04 allow-list / D-13)."
        )


# ---------------------------------------------------------------------------
# FP-04 / D-13: finish-args DENY-LIST (SECURITY-CRITICAL)
# ---------------------------------------------------------------------------


def test_flatpak_finish_args_deny_list(manifest_data: dict) -> None:
    """FP-04 / D-13 SECURITY-CRITICAL: forbidden broad permissions must be
    ABSENT from the parsed finish-args list.

    This is the security-critical half of the drift-guard (D-13).  Parsing
    YAML as data means a permission added inside a YAML comment is invisible
    to yaml.safe_load and correctly stays out of the parsed list — a text
    grep check would miss it (feedback_drift_guard_presence_not_semantics /
    T-86-07).
    """
    args = manifest_data.get("finish-args", [])

    assert "--filesystem=home" not in args, (
        "SECURITY: --filesystem=home MUST NOT appear in finish-args. "
        "Broad home filesystem access is forbidden (FP-04 deny-list / D-13). "
        "Use the narrow --filesystem=~/.local/share/musicstreamer:ro instead (D-01)."
    )
    assert "--filesystem=home:rw" not in args, (
        "SECURITY: --filesystem=home:rw MUST NOT appear in finish-args. "
        "Broad home read-write access is forbidden (FP-04 deny-list / D-13)."
    )
    assert "--socket=session-bus" not in args, (
        "SECURITY: --socket=session-bus MUST NOT appear in finish-args. "
        "Broad session-bus access is forbidden (FP-04 deny-list / D-13 / T-86-02). "
        "Use --own-name=org.mpris.MediaPlayer2.MusicStreamer for MPRIS2 instead (FP-08)."
    )


# ---------------------------------------------------------------------------
# FP-05: QtWebEngine sandbox disable env var
# ---------------------------------------------------------------------------


def test_flatpak_qtwebengine_disable_sandbox(manifest_data: dict) -> None:
    """FP-05: QTWEBENGINE_DISABLE_SANDBOX=1 must be in finish-args so the
    QtWebEngine subprocess (oauth_helper.py / GBS.FM login) can run inside
    the Flatpak sandbox."""
    args = manifest_data.get("finish-args", [])
    assert "--env=QTWEBENGINE_DISABLE_SANDBOX=1" in args, (
        "finish-args must include --env=QTWEBENGINE_DISABLE_SANDBOX=1 (FP-05). "
        "Without it, the QtWebEngine subprocess fails inside the Flatpak sandbox "
        "(Pitfall 4 / verbatim spelling from flathub/io.qt.qtwebengine.BaseApp)."
    )


# ---------------------------------------------------------------------------
# FP-08 (static): MPRIS2 --own-name
# ---------------------------------------------------------------------------


def test_flatpak_mpris2_own_name(manifest_data: dict) -> None:
    """FP-08 static half: --own-name=org.mpris.MediaPlayer2.MusicStreamer must
    be in finish-args so MusicStreamer can register its MPRIS2 short name on
    the session bus without broad --socket=session-bus."""
    args = manifest_data.get("finish-args", [])
    assert "--own-name=org.mpris.MediaPlayer2.MusicStreamer" in args, (
        "finish-args must include --own-name=org.mpris.MediaPlayer2.MusicStreamer "
        "(FP-08 static half / RESEARCH.md Pattern 4 + Pitfall 6). "
        "This narrow permission lets MPRIS2 work without --socket=session-bus."
    )


# ---------------------------------------------------------------------------
# FP-06 / D-01 / D-05: narrow :ro mount is the ONLY filesystem exception
# ---------------------------------------------------------------------------


def test_flatpak_narrow_ro_mount(manifest_data: dict) -> None:
    """FP-06 / D-01 / D-05 reconciliation: the narrow read-only host mount is
    present, AND no other --filesystem entry exists in finish-args.

    The :ro mount is an APPROVED addition to the FP-04 allow-list (D-05).
    No other --filesystem paths are permitted.
    """
    args = manifest_data.get("finish-args", [])

    # Must have the approved :ro mount
    assert "--filesystem=~/.local/share/musicstreamer:ro" in args, (
        "finish-args must include --filesystem=~/.local/share/musicstreamer:ro "
        "(D-01 approved narrow :ro mount for first-launch import wizard / FP-06)."
    )

    # Exactly one --filesystem entry: the approved :ro path
    filesystem_args = [a for a in args if a.startswith("--filesystem=")]
    assert filesystem_args == ["--filesystem=~/.local/share/musicstreamer:ro"], (
        "finish-args must contain EXACTLY one --filesystem entry: "
        "--filesystem=~/.local/share/musicstreamer:ro. "
        f"Found: {filesystem_args!r}. "
        "No broad --filesystem=home or additional paths are permitted (D-01/D-05/FP-06)."
    )


# ===========================================================================
# Task 2: python3-modules.yaml, FP-10 validators, first-launch detection
# ===========================================================================

# ---------------------------------------------------------------------------
# FP-09: python3-modules.yaml validity
# ---------------------------------------------------------------------------


def test_python3_modules_yaml_exists() -> None:
    """FP-09 + T-86-08: python3-modules.yaml must exist, be valid YAML, and
    must NOT contain PySide6 (which conflicts with the PySide6 provided by
    io.qt.PySide.BaseApp — RESEARCH.md Pitfall 5).
    """
    assert _PYTHON3_MODULES.is_file(), (
        f"python3-modules.yaml not found at {_PYTHON3_MODULES}. "
        "Run flatpak-pip-generator to generate it (FP-09)."
    )
    content = _PYTHON3_MODULES.read_text(encoding="utf-8")
    data = yaml.safe_load(content)
    assert data is not None, (
        "python3-modules.yaml must be valid (non-empty) YAML (FP-09)."
    )
    # T-86-08: PySide6 in python3-modules.yaml causes ABI conflicts at
    # runtime because io.qt.PySide.BaseApp already provides PySide6.
    assert "PySide6" not in content, (
        "python3-modules.yaml must NOT contain 'PySide6'. "
        "PySide6 is provided by io.qt.PySide.BaseApp and must NOT be "
        "re-installed via flatpak-pip-generator (RESEARCH.md Pitfall 5 / T-86-08). "
        "Use a curated flatpak-requirements.txt that excludes PySide6."
    )


# ---------------------------------------------------------------------------
# FP-10: AppStream + .desktop validators (skip-if-not-installed — D-15)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not shutil.which("appstreamcli"),
    reason="appstreamcli not installed — validator test skipped (D-15 dual-mode)",
)
def test_appstreamcli_validate_passes() -> None:
    """FP-10 / T-86-09: appstreamcli must validate the metainfo XML cleanly.

    Skip guard keeps the suite green on hosts without appstreamcli while
    still gating where the tool is installed (D-15 dual-mode; the hard
    pre-flight gate lives in Plan 04 build.sh + CI).
    """
    assert _FLATPAK_METAINFO.is_file(), (
        f"Metainfo file not found at {_FLATPAK_METAINFO}. "
        "Plan 01 must produce this artifact."
    )
    # --no-net: skip URL-reachability checks (screenshot, homepage, bugtracker).
    # Those URLs reference the GitHub repo which may not yet be published at
    # the time the test runs (Phase 86 pre-publication dev workflow).
    # The structural validity of the XML is fully checked without network access.
    result = subprocess.run(
        ["appstreamcli", "validate", "--explain", "--no-net", str(_FLATPAK_METAINFO)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"appstreamcli validate failed for {_FLATPAK_METAINFO}.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


@pytest.mark.skipif(
    not shutil.which("desktop-file-validate"),
    reason="desktop-file-validate not installed — validator test skipped (D-15 dual-mode)",
)
def test_desktop_file_validate_passes() -> None:
    """FP-10 / T-86-09: desktop-file-validate must pass for the Flatpak .desktop.

    Skip guard keeps the suite green on hosts without desktop-file-validate
    while still gating where the tool is installed (D-15 dual-mode).
    """
    assert _FLATPAK_DESKTOP.is_file(), (
        f"Flatpak .desktop file not found at {_FLATPAK_DESKTOP}. "
        "Plan 01 must produce this artifact."
    )
    result = subprocess.run(
        ["desktop-file-validate", str(_FLATPAK_DESKTOP)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"desktop-file-validate failed for {_FLATPAK_DESKTOP}.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# PKG-LIN-APP-09 preserved: no playlist MIME in the Flatpak .desktop
# ---------------------------------------------------------------------------


def test_flatpak_desktop_no_playlist_mime() -> None:
    """PKG-LIN-APP-09 preserved: the Flatpak .desktop must not register
    playlist MIME types (.pls / .m3u), mirroring the AppImage guard in
    test_packaging_linux_spec.py::test_desktop_file_has_no_playlist_mime_entries.

    Playlist files are import inputs (curated-library identity), not
    file-open targets.
    """
    assert _FLATPAK_DESKTOP.is_file(), (
        f"Flatpak .desktop file not found at {_FLATPAK_DESKTOP}."
    )
    desktop_text = _FLATPAK_DESKTOP.read_text(encoding="utf-8")
    assert "audio/x-mpegurl" not in desktop_text, (
        "PKG-LIN-APP-09 violation: Flatpak .desktop must not register "
        "audio/x-mpegurl (x-mpegurl = .m3u playlist — import input, not "
        "file-open target)."
    )
    assert "x-scpls" not in desktop_text, (
        "PKG-LIN-APP-09 violation: Flatpak .desktop must not register "
        "audio/x-scpls (x-scpls = .pls playlist — import input, not "
        "file-open target)."
    )


# ---------------------------------------------------------------------------
# FP-06 (detection + offer-once): first-launch detection integration test
# ---------------------------------------------------------------------------


def test_first_launch_detection(tmp_path, monkeypatch) -> None:
    """FP-06 detection + offer-once (D-03): exercise the flatpak_first_launch
    module with a monkeypatched _HOST_DB and sandbox data dir.

    Scenario:
      1. Host DB exists → has_unsandboxed_data() True
      2. No offer flag → should_offer_import_wizard() True
      3. write_offered_flag() creates the flag
      4. should_offer_import_wizard() now False (offer-once D-03)
    """
    import musicstreamer.flatpak_first_launch as ffl
    import musicstreamer.paths as paths

    # Create a fake host DB file (Plan 02 _HOST_DB constant)
    fake_host_db = tmp_path / "host" / "musicstreamer.sqlite3"
    fake_host_db.parent.mkdir(parents=True)
    fake_host_db.touch()

    # Monkeypatch _HOST_DB to the fake path
    monkeypatch.setattr(ffl, "_HOST_DB", str(fake_host_db))

    # Monkeypatch paths._root_override to redirect data_dir() into tmp_path
    # so write_offered_flag() writes the flag into an isolated sandbox dir
    sandbox_data_dir = tmp_path / "sandbox"
    sandbox_data_dir.mkdir()
    monkeypatch.setattr(paths, "_root_override", str(sandbox_data_dir))

    # 1. Host DB exists → has_unsandboxed_data() True
    assert ffl.has_unsandboxed_data() is True, (
        "has_unsandboxed_data() must return True when _HOST_DB exists."
    )

    # 2. No offer flag → should_offer_import_wizard() True
    assert ffl.should_offer_import_wizard() is True, (
        "should_offer_import_wizard() must return True when host DB exists "
        "and the offer-once flag is absent."
    )

    # 3. write_offered_flag() creates the flag in the (monkeypatched) sandbox
    ffl.write_offered_flag()
    flag_path = ffl.import_offered_flag_path()
    assert Path(flag_path).is_file(), (
        f"write_offered_flag() must create the offer-once flag at {flag_path}."
    )

    # 4. should_offer_import_wizard() now False (offer-once D-03)
    assert ffl.should_offer_import_wizard() is False, (
        "should_offer_import_wizard() must return False after write_offered_flag() "
        "has been called (offer-once D-03)."
    )
