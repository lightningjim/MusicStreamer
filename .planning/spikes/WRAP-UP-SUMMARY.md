# Spike Wrap-Up Summary

**Date:** 2026-04-20
**Spikes processed:** 1 (Phase 43 — executed via `/gsd-plan-phase` workflow, adapted into skill format post-hoc)
**Feature areas:** Windows GStreamer Bundling
**Skill output:** `./.claude/skills/spike-findings-musicstreamer/`

## Included Spikes

| # | Name | Verdict | Feature Area |
|---|------|---------|--------------|
| 43 | gstreamer-windows-spike | ✅ VALIDATED | Windows GStreamer Bundling |

## Excluded Spikes

_None._

## Key Findings

- **conda-forge is the only viable path** for PyGObject on Windows. PyPI ships sdist only across all versions; the MSVC-installer + source-build route needs Visual Studio Build Tools + meson/ninja/pkg-config (~1 GB). conda-forge packages are byte-for-byte equivalent (same upstream gvsbuild toolchain).
- **Custom runtime hook is required** — the stock `pyi_rth_gstreamer.py` sets `GST_PLUGIN_PATH`/`GST_REGISTRY` but NOT `GIO_EXTRA_MODULES` (souphttpsrc fails HTTPS without it), `GI_TYPELIB_PATH` (GI introspection flaky without it), or `GST_PLUGIN_SCANNER` (playbin3 spawns scanner in-process as fallback, slower + crash-prone).
- **Explicit `Tree()` blocks** compensate for broken stock `hook-gi.repository.Gio.py` on conda-forge layout. Without them, the bundle ships no TLS backend and HTTPS fails silently.
- **GStreamer 1.28.x upstream changes** caught at iteration-1: flat install layout (no `\1.0\msvc_x86_64\`), OpenSSL TLS (`gioopenssl.dll`) not GnuTLS, scanner moved to `libexec/gstreamer-1.0/`, single `.exe` installer (not split runtime/devel MSIs).
- **Bundle is self-contained** — 110.7 MB, proved via deactivated-conda re-run. 184 plugin DLLs in `_internal/gst_plugins/` (new subdir name in hooks-contrib 2026.2), 57 typelibs, 126 top-level DLLs.
- **Known server-side gotcha:** DI.fm premium URLs reject HTTPS even though TLS handshake succeeds. GStreamer not at fault. Phase 44 policy decision.
- **PowerShell 5.1 specific workarounds** documented: native-stderr trap, `.ps1` encoding, Miniforge Prompt vs real PowerShell, execution policy.

Full findings: `.planning/phases/43-gstreamer-windows-spike/43-SPIKE-FINDINGS.md`.
Reference + verbatim source artifacts: `.claude/skills/spike-findings-musicstreamer/`.
