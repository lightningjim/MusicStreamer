"""Phase 85 / PKG-LIN-APP — Linux AppImage source-text drift-guards.

Mirrors tests/test_packaging_spec.py's Windows-side discipline on the Linux
side: file-read fixtures + substring assertions, no subprocess, no docker,
no PyInstaller-equivalent installed. The drift-guards lock in the build
contract so that a future refactor cannot silently regress the GLIBC
ceiling (PKG-LIN-APP-08), the zsync update-info embedding (PKG-LIN-APP-06),
GPG signing (PKG-LIN-APP-10 / D-08 / D-09), the playlist-MIME absence
(PKG-LIN-APP-09), the production-import smoke (D-05), or the production
AppRun exec (Pitfall 20).

Cross-platform context: tests/test_packaging_spec.py (Windows) and this
file (Linux) are siblings. Per CONTEXT.md Success Criterion 4 / Pitfall 16,
Phase 85 lands without regressing the Windows drift-guards — running
`pytest tests/test_packaging_spec.py tests/test_packaging_linux_spec.py`
keeps both green.
"""
from __future__ import annotations

from pathlib import Path

import pytest


_BUILD_SH = (
    Path(__file__).resolve().parent.parent / "tools" / "linux-build" / "build.sh"
)
_APPRUN = (
    Path(__file__).resolve().parent.parent / "tools" / "linux-build" / "AppRun"
)
_ENVYML = (
    Path(__file__).resolve().parent.parent / "tools" / "linux-build" / "environment.yml"
)
_DESKTOP = (
    Path(__file__).resolve().parent.parent
    / "tools" / "linux-build" / "desktop" / "org.lightningjim.MusicStreamer.desktop"
)
_SMOKE = (
    Path(__file__).resolve().parent.parent / "tools" / "linux-build" / "smoke_test.py"
)


@pytest.fixture(scope="module")
def build_sh_source() -> str:
    assert _BUILD_SH.is_file(), f"expected build.sh at {_BUILD_SH}"
    return _BUILD_SH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def apprun_source() -> str:
    assert _APPRUN.is_file(), f"expected AppRun at {_APPRUN}"
    return _APPRUN.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def envyml_source() -> str:
    assert _ENVYML.is_file(), f"expected environment.yml at {_ENVYML}"
    return _ENVYML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def desktop_source() -> str:
    assert _DESKTOP.is_file(), f"expected .desktop at {_DESKTOP}"
    return _DESKTOP.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def smoke_source() -> str:
    assert _SMOKE.is_file(), f"expected smoke_test.py at {_SMOKE}"
    return _SMOKE.read_text(encoding="utf-8")


def _strip_comments_sh(source: str) -> str:
    """Strip shell-comment lines for negative-assertion gates (mirrors
    tests/test_packaging_spec.py lines 286-289 pattern). Lines beginning
    with optional whitespace then `#` are dropped."""
    return "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )


# --- PKG-LIN-APP-08: GLIBC ceiling ------------------------------------------

def test_build_sh_pins_glibc_ceiling_at_2_35(build_sh_source: str) -> None:
    """PKG-LIN-APP-08: build.sh's case statement must accept GLIBC_2.30..2.35
    as the ≤2.35 set (Pitfall 1 mitigation)."""
    assert "GLIBC_2.3[0-5]" in build_sh_source, (
        "build.sh must include the literal GLIBC_2.3[0-5] glob in its case "
        "statement so the GLIBC ceiling (PKG-LIN-APP-08) is enforced."
    )
    assert "GLIBC_FAIL" in build_sh_source, (
        "build.sh must emit GLIBC_FAIL on drift (numeric exit 4 per Pitfall 1)."
    )
    # Pitfall 16: must use objdump DT_VERNEED, not strings|grep.
    assert "objdump -T" in build_sh_source, (
        "build.sh must use `objdump -T` for GLIBC scan (Pitfall 16); the "
        "earlier `strings | grep GLIBC_` approach produced false positives "
        "from compressed-payload byte coincidence."
    )


# --- PKG-LIN-APP-06 / D-11: zsync update-info embedding ---------------------

def test_build_sh_embeds_zsync_update_info(build_sh_source: str) -> None:
    """PKG-LIN-APP-06 / D-11: the build must embed the canonical zsync
    update-info literal for the kcreasey/MusicStreamer GitHub Releases
    mirror via the appimage output plugin's LDAI_UPDATE_INFORMATION env
    var. linuxdeploy has no --updateinformation flag (it aborts the run);
    the var is what appimagetool actually reads (verified against the
    pinned plugin binary)."""
    assert "LDAI_UPDATE_INFORMATION" in build_sh_source, (
        "build.sh must export LDAI_UPDATE_INFORMATION for the appimage "
        "output plugin (D-11). The legacy --updateinformation flag is NOT "
        "accepted by linuxdeploy and fails the build."
    )
    assert "--updateinformation" not in build_sh_source, (
        "build.sh must NOT pass --updateinformation as a linuxdeploy flag "
        "-- linuxdeploy rejects it with 'Flag could not be matched'."
    )
    assert (
        "gh-releases-zsync|kcreasey|MusicStreamer|latest|MusicStreamer-*-x86_64.AppImage.zsync"
        in build_sh_source
    ), (
        "The embedded zsync URL must match the canonical literal "
        "(PKG-LIN-APP-06 / reference_qnap_github_mirror.md). "
        "Do not change the namespace from 'kcreasey'."
    )


def test_build_sh_preserves_pip_for_app_install(build_sh_source: str) -> None:
    """D-03: musicstreamer is installed via `pip install --no-deps` into the
    bundled conda env AFTER linuxdeploy runs. linuxdeploy-plugin-conda deletes
    site-packages/{setuptools,pip} during cleanup by default, which breaks that
    install ('No module named pip'). build.sh must opt out of the site-packages
    cleanup so pip survives for the app install step."""
    assert "CONDA_SKIP_CLEANUP" in build_sh_source and "site-packages" in build_sh_source, (
        "build.sh must include 'site-packages' in CONDA_SKIP_CLEANUP, or "
        "linuxdeploy-plugin-conda removes pip and the D-03 pip install fails."
    )
    assert "strip" in build_sh_source, (
        "build.sh must include 'strip' in CONDA_SKIP_CLEANUP: the container "
        "binutils strip segfaults (exit 139) on a bundled Qt/PySide6 lib and "
        "aborts the build. Skipping the strip cleanup keeps the build correct."
    )
    assert "pip install --no-deps" in build_sh_source, (
        "build.sh must install musicstreamer with --no-deps (D-03) so the "
        "conda-managed dependency graph is not re-resolved."
    )


def test_build_sh_installs_app_from_repo_root_not_work(build_sh_source: str) -> None:
    """D-03: the musicstreamer package lives at the repo root, not in
    HERE=/work (tools/linux-build/). build.sh must mount the repo root and
    install from there -- NOT `pip install ... /work`, which has no
    pyproject.toml and fails with 'Neither setup.py nor pyproject.toml found'."""
    assert "/src" in build_sh_source and ":ro" in build_sh_source, (
        "build.sh must bind-mount the repo root read-only (e.g. -v REPO_ROOT:/src:ro) "
        "so the package source is reachable inside the container."
    )
    assert "pip install --no-deps /work" not in build_sh_source, (
        "build.sh must NOT install from /work (tools/linux-build/) -- that dir "
        "has no pyproject.toml. Install the package from the repo-root source."
    )


# --- PKG-LIN-APP-10 / D-08 / D-09: GPG signing ------------------------------

def test_build_sh_signs_appimage_with_gpg2(build_sh_source: str) -> None:
    """PKG-LIN-APP-10 / D-08: build.sh must invoke a GnuPG 2.x binary with
    --detach-sign --armor against the produced AppImage using the GPG_KEY_ID
    env var (no hardcoded fingerprint). The binary is resolved at runtime as
    gpg2-or-gpg, since GnuPG 2.x ships as `gpg` on modern distros."""
    assert "--detach-sign --armor --local-user" in build_sh_source, (
        "build.sh must call `<gpg> --detach-sign --armor --local-user "
        "\"$GPG_KEY_ID\"` to produce the .sig sidecar (D-08)."
    )
    assert "command -v gpg2" in build_sh_source and "command -v gpg" in build_sh_source, (
        "build.sh must resolve the GnuPG binary as gpg2-or-gpg (command -v gpg2 "
        "|| command -v gpg); hardcoding `gpg2` fails on distros where GnuPG 2.x "
        "is installed as `gpg` (no gpg2 symlink)."
    )
    assert '"$GPG_KEY_ID"' in build_sh_source, (
        "build.sh must reference $GPG_KEY_ID; no hardcoded key ID allowed (D-09)."
    )


def test_build_sh_fail_fast_when_gpg_key_unset(build_sh_source: str) -> None:
    """D-09: build.sh exits 5 with `BUILD_FAIL reason=gpg_key_unset` when
    GPG_KEY_ID is unset AND SKIP_SIGN!=1. CI never sets SKIP_SIGN."""
    assert "BUILD_FAIL reason=gpg_key_unset" in build_sh_source
    assert "exit 5" in build_sh_source
    # The fail-fast must check SKIP_SIGN
    executable = _strip_comments_sh(build_sh_source)
    assert "SKIP_SIGN" in executable, (
        "build.sh must reference SKIP_SIGN in an executable (non-comment) "
        "line so the local-iteration escape hatch works (D-09)."
    )


def test_build_sh_fails_when_signing_fails(build_sh_source: str) -> None:
    """D-08: gpg2 invocation failure must exit 6 with
    `BUILD_FAIL reason=signing_failed`."""
    assert "BUILD_FAIL reason=signing_failed" in build_sh_source
    assert "exit 6" in build_sh_source


# --- PKG-LIN-APP-04: nodejs in bundle ---------------------------------------

def test_environment_yml_includes_nodejs(envyml_source: str) -> None:
    """PKG-LIN-APP-04: environment.yml must declare nodejs so the bundled
    yt-dlp EJS solver can resolve YouTube streams without requiring a
    host Node installation."""
    assert "nodejs" in envyml_source, (
        "environment.yml must include `nodejs` in its conda-forge dependencies "
        "(PKG-LIN-APP-04)."
    )


# --- D-02 / D-01: source-of-truth identity ----------------------------------

def test_environment_yml_is_production_named(envyml_source: str) -> None:
    """D-02: production env name is `musicstreamer-build`, not the
    `spike-linux` placeholder."""
    assert "name: musicstreamer-build" in envyml_source, (
        "environment.yml must declare `name: musicstreamer-build` (D-02 "
        "production identity; renamed from spike's `spike-linux`)."
    )


def test_build_sh_synthesizes_conda_packages_from_yml(build_sh_source: str) -> None:
    """D-01: build.sh must derive CONDA_PACKAGES from environment.yml via
    yq, not maintain a duplicate hardcoded list."""
    executable = _strip_comments_sh(build_sh_source)
    assert "yq" in executable and "environment.yml" in executable, (
        "build.sh must invoke yq against environment.yml in an executable "
        "(non-comment) line — D-01 single-source-of-truth contract."
    )


# --- Pitfall 20 / production exec ------------------------------------------

def test_apprun_execs_production_musicstreamer_module(apprun_source: str) -> None:
    """Pitfall 20 / spike hand-off item 5: AppRun's final exec must launch
    `python -m musicstreamer`, not the spike's `hello_world.py`."""
    assert 'exec "${APPDIR}/usr/conda/bin/python" -m musicstreamer "$@"' in apprun_source, (
        "AppRun must end with the production exec `python -m musicstreamer "
        "\"$@\"` (Pitfall 20)."
    )
    assert "hello_world" not in apprun_source, (
        "AppRun must not reference hello_world.py (spike artifact; production "
        "exec replaces it)."
    )


# --- Pitfall 19: PipeWire identity ------------------------------------------

def test_apprun_exports_pulse_prop(apprun_source: str) -> None:
    """Pitfall 19: AppRun must export PULSE_PROP so Wireplumber stream-restore
    state is deterministic across --appimage-extract-and-run random tmpdirs."""
    assert "PULSE_PROP=" in apprun_source, (
        "AppRun must export PULSE_PROP for deterministic PipeWire app identity "
        "(Pitfall 19)."
    )
    assert "application.name=MusicStreamer" in apprun_source


# --- Pitfall 17 carried over from spike -------------------------------------

def test_apprun_exports_ssl_cert_file(apprun_source: str) -> None:
    """Pitfall 17 (spike-discovered): bundled OpenSSL needs SSL_CERT_FILE
    pointed at the conda CA bundle for HTTPS playback."""
    assert "SSL_CERT_FILE=" in apprun_source
    assert "cacert.pem" in apprun_source


# --- PKG-LIN-APP-09: no playlist MIME entries -------------------------------

def test_desktop_file_has_no_playlist_mime_entries(desktop_source: str) -> None:
    """PKG-LIN-APP-09: curated-library identity — playlist files are import
    inputs, not user-facing files. The .desktop must NOT register .pls/.m3u
    MIME associations."""
    assert "audio/x-mpegurl" not in desktop_source, (
        "PKG-LIN-APP-09 violation: .desktop must not register audio/x-mpegurl "
        "(playlist files are import inputs)."
    )
    assert "audio/x-scpls" not in desktop_source, (
        "PKG-LIN-APP-09 violation: .desktop must not register audio/x-scpls."
    )


# --- D-05: production-import smoke ------------------------------------------

def test_smoke_test_imports_production_url_helpers(smoke_source: str) -> None:
    """D-05: smoke_test.py must import musicstreamer.url_helpers so it
    catches dependency-graph and import-path regressions in the bundled
    env, not just media-pipeline issues."""
    assert "from musicstreamer import url_helpers" in smoke_source, (
        "smoke_test.py must import the production resolver via "
        "`from musicstreamer import url_helpers` (D-05). This catches "
        "import-path regressions that a GStreamer-only smoke would miss."
    )


def test_smoke_test_exposes_d04_codec_sweep_modes(smoke_source: str) -> None:
    """D-04: smoke_test.py must expose --check-mp3, --check-aac,
    --check-aacp, --check-pls argparse modes for the four-URL codec sweep."""
    for flag in ("--check-mp3", "--check-aac", "--check-aacp", "--check-pls"):
        assert flag in smoke_source, (
            f"smoke_test.py must declare {flag} argparse mode (D-04 codec sweep)."
        )


def test_smoke_test_preserves_spike_grep_contract(smoke_source: str) -> None:
    """Grep contract from spike (PATTERNS.md §smoke_test.py lines 295-302):
    Plan 85-04 Task 1's run-smoke.sh transcript grep depends on these
    literal stdout markers."""
    for marker in ("SPIKE_OK", "SPIKE_FAIL", "SPIKE_DIAG", "plugin_resolved="):
        assert marker in smoke_source, (
            f"smoke_test.py must preserve the spike stdout marker `{marker}` "
            "(downstream run-smoke.sh greps for it)."
        )


# =============================================================================
# Phase 86 / PKG-LIN-FP — Flatpak build.sh and CI drift-guards
# =============================================================================
# Source-text assertions that lock in the Flatpak build contract so a future
# refactor cannot silently regress GPG signing (PKG-LIN-FP-11 / D-08), the
# hard validator pre-flight (FP-10 / D-15), or the workflow_dispatch-only CI
# trigger (D-07). Guards follow the same fixture+assertion idiom as the AppImage
# section above (PATTERNS.md §Drift-guard Fixture Shape).

_FLATPAK_BUILD_SH = (
    Path(__file__).resolve().parent.parent / "tools" / "linux-flatpak" / "build.sh"
)
_FLATPAK_CI_WORKFLOW = (
    Path(__file__).resolve().parent.parent
    / ".github" / "workflows" / "linux-flatpak.yml"
)


@pytest.fixture(scope="module")
def flatpak_build_sh_source() -> str:
    assert _FLATPAK_BUILD_SH.is_file(), (
        f"expected Flatpak build.sh at {_FLATPAK_BUILD_SH}"
    )
    return _FLATPAK_BUILD_SH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def flatpak_ci_workflow_source() -> str:
    assert _FLATPAK_CI_WORKFLOW.is_file(), (
        f"expected linux-flatpak.yml at {_FLATPAK_CI_WORKFLOW}"
    )
    return _FLATPAK_CI_WORKFLOW.read_text(encoding="utf-8")


# --- PKG-LIN-FP-11 / D-08: inline GPG signing --------------------------------

def test_flatpak_build_gpg_sign(flatpak_build_sh_source: str) -> None:
    """PKG-LIN-FP-11 / D-08: tools/linux-flatpak/build.sh must invoke
    `flatpak build-bundle` with `--gpg-sign` to embed the signature inline
    in the .flatpak bundle. Unlike the AppImage (detached .sig sidecar),
    Flatpak signing is inline — no separate .sig file is produced.
    (Critical Note #1 / PATTERNS.md line 527)"""
    assert "flatpak build-bundle" in flatpak_build_sh_source, (
        "tools/linux-flatpak/build.sh must invoke `flatpak build-bundle` to "
        "produce the .flatpak bundle (PKG-LIN-FP-02 / D-08)."
    )
    assert "--gpg-sign" in flatpak_build_sh_source, (
        "tools/linux-flatpak/build.sh must pass `--gpg-sign` to flatpak "
        "build-bundle (PKG-LIN-FP-11 / D-08 inline signing; no .sig sidecar)."
    )


def test_flatpak_build_fail_fast_gpg(flatpak_build_sh_source: str) -> None:
    """PKG-LIN-FP-11 / D-08: tools/linux-flatpak/build.sh exits 5 with
    `BUILD_FAIL reason=gpg_key_unset` when GPG_KEY_ID is unset AND
    SKIP_SIGN!=1. CI never sets SKIP_SIGN. Mirrors Phase 85 D-09 discipline."""
    assert "BUILD_FAIL reason=gpg_key_unset" in flatpak_build_sh_source, (
        "build.sh must emit BUILD_FAIL reason=gpg_key_unset when GPG_KEY_ID "
        "is unset and SKIP_SIGN!=1 (PKG-LIN-FP-11 / D-08 fail-fast)."
    )
    assert "exit 5" in flatpak_build_sh_source, (
        "build.sh must exit 5 for the gpg_key_unset case (Phase 85 exit-code "
        "parity — D-08)."
    )
    # SKIP_SIGN must appear in an EXECUTABLE (non-comment) line so the
    # local-iteration escape hatch actually works.
    executable = _strip_comments_sh(flatpak_build_sh_source)
    assert "SKIP_SIGN" in executable, (
        "build.sh must reference SKIP_SIGN in an executable (non-comment) "
        "line so `SKIP_SIGN=1` local-iteration mode works (D-08)."
    )


# --- FP-10 / D-15: hard validator pre-flight gate ----------------------------

def test_flatpak_build_validator_gate(flatpak_build_sh_source: str) -> None:
    """FP-10 / D-15: tools/linux-flatpak/build.sh must run BOTH
    `appstreamcli validate` and `desktop-file-validate` as a HARD pre-flight
    gate before flatpak build-bundle. A non-zero exit from either FAILS the
    build immediately (not a warning). This is the build-time half of D-15;
    the pytest subprocess gate in this file is the test-time half."""
    assert "appstreamcli validate" in flatpak_build_sh_source, (
        "build.sh must run `appstreamcli validate` as a hard pre-flight gate "
        "before bundling (FP-10 / D-15). Omitting it allows invalid metainfo "
        "to ship silently."
    )
    assert "desktop-file-validate" in flatpak_build_sh_source, (
        "build.sh must run `desktop-file-validate` as a hard pre-flight gate "
        "before bundling (FP-10 / D-15). Omitting it allows an invalid .desktop "
        "entry to ship silently."
    )
    # The build must FAIL (not skip) on validator error — assert the error path
    # exists as a non-comment line.
    executable = _strip_comments_sh(flatpak_build_sh_source)
    assert "BUILD_FAIL reason=validator_failed" in executable, (
        "build.sh must emit BUILD_FAIL reason=validator_failed on validator "
        "error in an executable line (D-15 hard gate — build FAILS, not warns)."
    )


# --- D-07: workflow_dispatch-only CI, --privileged, invokes build.sh ---------

def test_flatpak_ci_workflow_dispatch_only(flatpak_ci_workflow_source: str) -> None:
    """D-07 / PATTERNS.md §linux-flatpak.yml: the CI workflow must be
    workflow_dispatch-only (no push/release auto-trigger) to prevent
    accidental auto-publish and guard signing key exposure (fork-PRs cannot
    trigger workflow_dispatch and thus cannot access LINUX_SIGNING_KEY).
    --privileged is required for FUSE/OSTree (RESEARCH.md Pitfall 9)."""
    assert "workflow_dispatch" in flatpak_ci_workflow_source, (
        "linux-flatpak.yml must use `workflow_dispatch` as the only trigger "
        "(D-07 — manual trigger prevents accidental publish)."
    )
    # Deny-list: no push or release auto-trigger.
    assert "on:\n  push" not in flatpak_ci_workflow_source, (
        "linux-flatpak.yml must NOT have a `push:` trigger (D-07 — "
        "workflow_dispatch-only)."
    )
    assert "\n  push:" not in flatpak_ci_workflow_source, (
        "linux-flatpak.yml must NOT have a `push:` trigger (D-07 — "
        "workflow_dispatch-only; deny-list check)."
    )
    assert "--privileged" in flatpak_ci_workflow_source, (
        "linux-flatpak.yml must specify --privileged for the job container "
        "(RESEARCH.md Pitfall 9 — FUSE/OSTree require privileged mode; without "
        "it the build fails with 'fuse: failed to open /dev/fuse')."
    )
    assert "tools/linux-flatpak/build.sh" in flatpak_ci_workflow_source, (
        "linux-flatpak.yml must invoke tools/linux-flatpak/build.sh in the "
        "build step (key_links contract — the workflow delegates to the build driver)."
    )
    assert "if-no-files-found: error" in flatpak_ci_workflow_source, (
        "linux-flatpak.yml upload-artifact step must set if-no-files-found: error "
        "so CI fails loudly when the .flatpak bundle is not produced."
    )
