"""Build-time AAC plugin-presence guard (Phase 69, G-01 / G-02).

Asserts the PyInstaller bundle contains the GStreamer plugin DLLs required
for AAC playback on Windows. Runs after PyInstaller produces the bundle,
before Inno Setup compile (build.ps1 step 4b). Mirrors the structural shape
of tools/check_subprocess_guard.py and tools/check_spec_entry.py (PKG-03 /
PKG-01) — Python helper invoked by build.ps1 via Invoke-Native, exit code
branching, single source of truth for the required-plugin list.

Exit codes:
    0 — clean (all required plugin DLLs present in the bundle)
    10 — plugin missing (matches build.ps1 exit code convention per G-04)

Callable as ``python tools/check_bundle_plugins.py --bundle <path>`` from
the repo root.

The REQUIRED_PLUGIN_DLLS dict is the single source of truth for the
required-plugin list. It is also imported by tests/test_packaging_spec.py
for the static drift-guard test (P-01) that asserts
packaging/windows/README.md's conda recipe mentions every required
conda-forge package.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Phase 69 G-02: maps PyInstaller-bundled DLL filename -> (element name,
# conda-forge package). RESEARCH corrected CONTEXT-DG-01:
#   - avdec_aac ships in gst-libav (NOT gst-plugins-bad as the early
#     context draft asserted)
#   - aacparse ships in gst-plugins-good's audioparsers plugin (NOT
#     gst-plugins-bad as the early context draft asserted)
# The GPL-licensed alternative decoder is NOT viable on conda-forge win-64
# (excluded for licensing reasons); the required list intentionally does
# not reference it.
REQUIRED_PLUGIN_DLLS: dict[str, tuple[str, str]] = {
    "gstlibav.dll": ("avdec_aac", "gst-libav"),
    "gstaudioparsers.dll": ("aacparse", "gst-plugins-good"),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 69 G-01: assert AAC-required GStreamer plugin DLLs landed "
            "in the PyInstaller bundle's gst_plugins/ subdir."
        )
    )
    parser.add_argument(
        "--bundle",
        type=Path,
        default=Path("dist/MusicStreamer/_internal"),
        help=(
            "Path to PyInstaller _internal/ directory "
            "(default: dist/MusicStreamer/_internal)"
        ),
    )
    args = parser.parse_args(argv)

    # Spike-finding 43-SPIKE-FINDINGS.md line 128: PyInstaller hooks-contrib
    # 2026.2 places plugins under `gst_plugins/` (underscore), NOT
    # `gst-plugins/` (hyphen) as older 2024-era guides documented.
    plugins_dir = args.bundle / "gst_plugins"
    if not plugins_dir.is_dir():
        print(
            f"PHASE-69 FAIL: bundle plugins dir not found at {plugins_dir}",
            file=sys.stderr,
        )
        return 10

    missing: list[str] = []
    for dll_name, (element, package) in REQUIRED_PLUGIN_DLLS.items():
        if not (plugins_dir / dll_name).is_file():
            missing.append(
                f"  {dll_name} (provides {element}, ships in conda-forge "
                f"package {package})"
            )

    if missing:
        print(
            "PHASE-69 FAIL: required GStreamer plugin DLL(s) missing from bundle:",
            file=sys.stderr,
        )
        for line in missing:
            print(line, file=sys.stderr)
        print(
            "Fix: add the named conda-forge package(s) to "
            "packaging/windows/README.md conda recipe, recreate the conda "
            "env, and rebuild.",
            file=sys.stderr,
        )
        return 10

    print(
        f"PHASE-69 OK: all {len(REQUIRED_PLUGIN_DLLS)} required plugin "
        f"DLL(s) present in {plugins_dir}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
