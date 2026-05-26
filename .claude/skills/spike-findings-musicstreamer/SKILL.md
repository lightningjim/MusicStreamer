---
name: spike-findings-musicstreamer
description: Validated patterns, constraints, and implementation knowledge from MusicStreamer spike experiments. Auto-load during Windows packaging, GStreamer, PyInstaller, conda-forge, or Qt/GLib bus-handler threading work.
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
| Qt ↔ GLib Bus Threading | references/qt-glib-bus-threading.md | Two cross-platform correctness rules for GStreamer bus handlers in a PySide6 app. (1) `bus.add_signal_watch()` must run on the thread iterating its own thread-default MainContext — marshal onto the `GstBusLoopThread` via `run_sync`. (2) `QTimer.singleShot(0, callable)` from a non-QThread silently drops — any cross-thread work from a bus handler must go through a queued Qt `Signal`. Both rules validated by Phase 43.1 Windows failure + Linux latent-bug reproduction. |
| Linux AppImage Bundling | references/linux-appimage-bundling.md | conda-forge is the only viable PyGObject+GStreamer source on Linux too; `linuxdeploy-plugin-gstreamer` defaults to multiarch system paths and MUST be redirected to `$APPDIR/usr/conda/lib/gstreamer-1.0/` via `GSTREAMER_PLUGINS_DIR`. AppRun template owns `GST_REGISTRY_FORK=no` explicitly (plugin sets `GST_REGISTRY_REUSE_PLUGIN_SCANNER=no`, a different flag). HTTPS needs `GIO_EXTRA_MODULES` + `SSL_CERT_FILE` (Pitfall 17 — TLS backend probe alone misses cert-validation issues). Distrobox+podman shares Wayland+PipeWire+DBus by default — cross-distro PASS achievable from a single host. Phase 85a empirical: 503 MB AppImage, GLIBC_2.34, 188 plugins, HTTP+HTTPS PASS on Ubuntu 22.04 + Fedora 40 + Tumbleweed. |

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
- 85a-linux-packaging-spike (Phase 85a; 2026-05-26 — Linux AppImage build via linuxdeploy + plugin-conda + plugin-gstreamer + conda-forge; 20 pitfalls catalogued)
</metadata>
