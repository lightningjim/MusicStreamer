---
name: spike-findings-musicstreamer
description: Validated patterns, constraints, and implementation knowledge from MusicStreamer spike experiments. Auto-load during Windows packaging, GStreamer, PyInstaller, or conda-forge-related implementation work.
---

<context>
## Project: MusicStreamer

Python/Qt audio streamer (AudioAddict, SomaFM, generic ShoutCast/Icecast, YouTube live via yt-dlp). v2.0 milestone is the OS-agnostic revamp — PySide6 + GStreamer + conda-forge bundling for Windows distribution. Phase 43 validated the GStreamer+PyInstaller+conda-forge bundling pattern on Windows 11; Phase 44 implements the real Windows packaging.

Spike wrapped: 2026-04-20
</context>

<findings_index>
## Feature Areas

| Area | Reference | Key Finding |
|------|-----------|-------------|
| Windows GStreamer Bundling | references/windows-gstreamer-bundling.md | conda-forge is the only viable path for PyGObject on Windows. Custom runtime hook sets `GIO_EXTRA_MODULES`/`GI_TYPELIB_PATH`/`GST_PLUGIN_SCANNER` that the stock rthook misses. Explicit `Tree()` blocks override the broken stock `hook-gi.repository.Gio.py` on conda-forge layout. Empirically proved self-contained ~110 MB bundle. |

## Source Files

Canonical artifacts from Phase 43 are preserved verbatim for copy-paste into Phase 44:

- `sources/43-gstreamer-windows-spike/43-spike.spec` — PyInstaller spec with `GST_ROOT` auto-detect, dual-path scanner resolution, explicit `Tree()` for gio/modules + typelibs
- `sources/43-gstreamer-windows-spike/runtime_hook.py` — env vars for TLS backend, typelib path, plugin scanner
- `sources/43-gstreamer-windows-spike/build.ps1` — build driver with CONDA_PREFIX auto-detect, `Invoke-Native` helper for PS 5.1 stderr trap
- `sources/43-gstreamer-windows-spike/smoke_test.py` — self-contained HTTPS playback test (drop-in pattern for any playbin3 integration test)
- `sources/43-gstreamer-windows-spike/43-SPIKE-FINDINGS.md` — full Phase 43 findings with DLL/plugin/typelib BOMs
- `sources/43-gstreamer-windows-spike/README.md` — VM setup runbook (Miniforge + conda env recipe)
</findings_index>

<metadata>
## Processed Spikes

- 43-gstreamer-windows-spike (Phase 43; GStreamer Windows bundling via PyInstaller + conda-forge)
</metadata>
