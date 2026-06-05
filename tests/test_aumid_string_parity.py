"""Static parity tests for Windows AUMID consistency and AAC plugin guard (Phase 88).

These tests run on Linux CI — no Windows VM or installed .lnk required.

Static 3-way AUMID parity (WIN-02-B CI half):
  Asserts the AUMID literal is byte-identical across:
    1. musicstreamer/constants.py::APP_ID
    2. musicstreamer/__main__.py::_set_windows_aumid (default-None path reads constants.APP_ID)
    3. packaging/windows/MusicStreamer.iss [Icons] AppUserModelID directive

  Drift between any of the three sources causes immediate CI failure. The live
  installed-.lnk System.AppUserModel.ID readback (``System.AppUserModel.ID``
  shell property) is the Plan 03 VM UAT step and cannot run on Linux.

AAC plugin-guard regression (WIN-05):
  Asserts tools/check_bundle_plugins.py REQUIRED_PLUGIN_DLLS maps gst-libav ->
  avdec_aac and returns exit code 10 when gstlibav.dll is absent from a bundle,
  pinning the guard against future weakening.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

# Repo root: two levels up from this file (tests/ -> repo root)
REPO_ROOT = Path(__file__).resolve().parents[1]

# The canonical AUMID value. All three sources must equal this exactly.
EXPECTED_AUMID = "org.lightningjim.MusicStreamer"


# ---------------------------------------------------------------------------
# Task 1: Static 3-way AUMID parity
# ---------------------------------------------------------------------------

def test_constants_app_id_is_canonical():
    """musicstreamer.constants.APP_ID equals the canonical AUMID literal."""
    from musicstreamer import constants

    assert constants.APP_ID == EXPECTED_AUMID, (
        f"constants.APP_ID is {constants.APP_ID!r}, expected {EXPECTED_AUMID!r}"
    )


def test_iss_icons_aumid_matches_constants():
    """The AppUserModelID directive in MusicStreamer.iss equals constants.APP_ID.

    Parses with a regex across the whole file so the line-continuation
    backslash in the [Icons] entry does not interfere.
    """
    from musicstreamer import constants

    iss_path = REPO_ROOT / "packaging" / "windows" / "MusicStreamer.iss"
    assert iss_path.is_file(), f"expected MusicStreamer.iss at {iss_path}"

    iss_source = iss_path.read_text(encoding="utf-8")
    matches = re.findall(r'AppUserModelID:\s*"([^"]+)"', iss_source)

    assert len(matches) == 1, (
        f"expected exactly one AppUserModelID directive in {iss_path}, "
        f"found {len(matches)}: {matches!r}"
    )

    iss_aumid = matches[0]
    assert iss_aumid == constants.APP_ID, (
        f"MusicStreamer.iss AppUserModelID is {iss_aumid!r}, "
        f"but constants.APP_ID is {constants.APP_ID!r}. "
        "These must be byte-identical."
    )


def test_main_aumid_default_resolves_to_constants():
    """_set_windows_aumid in __main__.py uses constants.APP_ID, not a hardcoded copy.

    Two assertions:
    1. The source line `app_id = constants.APP_ID` is present inside
       _set_windows_aumid (proves the default-None path reads from constants).
    2. The literal string "org.lightningjim.MusicStreamer" does NOT appear
       in __main__.py (proves __main__.py defers entirely to constants —
       no second copy of the AUMID lives there).
    """
    main_path = REPO_ROOT / "musicstreamer" / "__main__.py"
    assert main_path.is_file(), f"expected __main__.py at {main_path}"

    source_lines = main_path.read_text(encoding="utf-8").splitlines()

    # Check that `app_id = constants.APP_ID` appears in a non-comment line
    delegate_lines = [
        line for line in source_lines
        if "app_id = constants.APP_ID" in line
        and not line.lstrip().startswith("#")
    ]
    assert delegate_lines, (
        "__main__.py::_set_windows_aumid must contain the line "
        "`app_id = constants.APP_ID` (the default-None delegation). "
        "If this has changed, update constants.APP_ID to be the single source "
        "of truth and remove any hardcoded AUMID from __main__.py."
    )

    # Check the literal AUMID is NOT hardcoded in __main__.py
    literal_lines = [
        line for line in source_lines
        if EXPECTED_AUMID in line
        and not line.lstrip().startswith("#")
    ]
    assert not literal_lines, (
        f"__main__.py must not hardcode the AUMID literal {EXPECTED_AUMID!r}. "
        f"Found on line(s): {literal_lines!r}. "
        "The canonical value lives exclusively in musicstreamer/constants.py::APP_ID."
    )


def test_no_drift_three_way():
    """Single three-way assertion: constants.APP_ID == .iss AUMID == EXPECTED_AUMID.

    This is the canary test. If any source drifts, this assertion fails
    with a clear message identifying which value changed.
    """
    from musicstreamer import constants

    iss_path = REPO_ROOT / "packaging" / "windows" / "MusicStreamer.iss"
    iss_source = iss_path.read_text(encoding="utf-8")
    matches = re.findall(r'AppUserModelID:\s*"([^"]+)"', iss_source)
    # Tolerant: if no match, the other tests will catch it; here just skip the
    # three-way assertion gracefully rather than explode on IndexError.
    iss_aumid = matches[0] if matches else "<not found>"

    values = {
        "constants.APP_ID": constants.APP_ID,
        ".iss AppUserModelID": iss_aumid,
        "EXPECTED_AUMID": EXPECTED_AUMID,
    }

    unique_values = set(values.values())
    assert len(unique_values) == 1, (
        "Three-way AUMID drift detected. All sources must be byte-identical. "
        f"Current values: {values}"
    )


# ---------------------------------------------------------------------------
# Task 2: AAC plugin-guard regression (WIN-05)
# ---------------------------------------------------------------------------

def test_required_plugin_dlls_map_aac():
    """REQUIRED_PLUGIN_DLLS pins the gst-libav -> avdec_aac and aacparse mappings.

    If gstlibav.dll is dropped from REQUIRED_PLUGIN_DLLS or its element/package
    values change, this test fails immediately, catching any weakening of the
    AAC guard before it reaches CI.
    """
    from tools.check_bundle_plugins import REQUIRED_PLUGIN_DLLS

    assert "gstlibav.dll" in REQUIRED_PLUGIN_DLLS, (
        "gstlibav.dll must be in REQUIRED_PLUGIN_DLLS "
        "(provides avdec_aac AAC decoder from gst-libav)"
    )
    assert REQUIRED_PLUGIN_DLLS["gstlibav.dll"] == ("avdec_aac", "gst-libav"), (
        f"gstlibav.dll entry changed: {REQUIRED_PLUGIN_DLLS['gstlibav.dll']!r}, "
        "expected ('avdec_aac', 'gst-libav')"
    )

    assert "gstaudioparsers.dll" in REQUIRED_PLUGIN_DLLS, (
        "gstaudioparsers.dll must be in REQUIRED_PLUGIN_DLLS "
        "(provides aacparse from gst-plugins-good)"
    )
    assert REQUIRED_PLUGIN_DLLS["gstaudioparsers.dll"] == ("aacparse", "gst-plugins-good"), (
        f"gstaudioparsers.dll entry changed: "
        f"{REQUIRED_PLUGIN_DLLS['gstaudioparsers.dll']!r}, "
        "expected ('aacparse', 'gst-plugins-good')"
    )


def test_guard_returns_10_on_missing_gstlibav(tmp_path):
    """AAC guard fires (returns 10) when gstlibav.dll is absent from the bundle.

    Constructs a minimal bundle at tmp_path/_internal/gst_plugins/ containing
    gstaudioparsers.dll but NOT gstlibav.dll, simulating a conda env where
    gst-libav was never installed or omitted from the recipe. The guard must
    detect the missing DLL and return exit code 10.
    """
    from tools import check_bundle_plugins

    bundle_internal = tmp_path / "_internal"
    plugins_dir = bundle_internal / "gst_plugins"
    plugins_dir.mkdir(parents=True)

    # Only the parsers DLL is present — gstlibav.dll is intentionally absent
    (plugins_dir / "gstaudioparsers.dll").touch()

    result = check_bundle_plugins.main(["--bundle", str(bundle_internal)])
    assert result == 10, (
        f"Expected exit code 10 (missing gstlibav.dll guard), got {result}. "
        "The AAC plugin guard must fire when gstlibav.dll is absent."
    )


def test_guard_returns_0_when_all_present(tmp_path):
    """AAC guard returns 0 (clean) when both required DLLs are present in the bundle.

    Constructs a bundle with both gstlibav.dll and gstaudioparsers.dll as
    empty touch files. The guard must report clean (exit 0).
    """
    from tools import check_bundle_plugins

    bundle_internal = tmp_path / "_internal"
    plugins_dir = bundle_internal / "gst_plugins"
    plugins_dir.mkdir(parents=True)

    # Both required DLLs present (content irrelevant — guard only checks existence)
    (plugins_dir / "gstlibav.dll").touch()
    (plugins_dir / "gstaudioparsers.dll").touch()

    result = check_bundle_plugins.main(["--bundle", str(bundle_internal)])
    assert result == 0, (
        f"Expected exit code 0 (all plugins present), got {result}. "
        "The AAC plugin guard must pass when all required DLLs are present."
    )
