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
    """PKG-LIN-APP-06 / D-11: linuxdeploy invocation must embed the
    canonical zsync update-info literal for the kcreasey/MusicStreamer
    GitHub Releases mirror."""
    assert "--updateinformation" in build_sh_source, (
        "build.sh must pass --updateinformation to linuxdeploy (D-11)."
    )
    assert (
        "gh-releases-zsync|kcreasey|MusicStreamer|latest|MusicStreamer-*-x86_64.AppImage.zsync"
        in build_sh_source
    ), (
        "The embedded zsync URL must match the canonical literal "
        "(PKG-LIN-APP-06 / reference_qnap_github_mirror.md). "
        "Do not change the namespace from 'kcreasey'."
    )


# --- PKG-LIN-APP-10 / D-08 / D-09: GPG signing ------------------------------

def test_build_sh_signs_appimage_with_gpg2(build_sh_source: str) -> None:
    """PKG-LIN-APP-10 / D-08: build.sh must invoke gpg2 --detach-sign
    --armor against the produced AppImage using the GPG_KEY_ID env var
    (no hardcoded fingerprint)."""
    assert "gpg2 --detach-sign --armor --local-user" in build_sh_source, (
        "build.sh must call `gpg2 --detach-sign --armor --local-user "
        "\"$GPG_KEY_ID\"` to produce the .sig sidecar (D-08)."
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
