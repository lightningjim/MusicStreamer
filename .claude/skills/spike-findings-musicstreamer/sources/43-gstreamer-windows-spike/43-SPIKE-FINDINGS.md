# Phase 43 Spike Findings — GStreamer on Windows via PyInstaller

**Date:** 2026-04-20
**Iteration:** 1 (pass on first build)
**Verdict:** ✅ All three ROADMAP success criteria proved empirically. Phase 44 can inherit the artifacts in this directory.

## TL;DR for Phase 44

- **Use conda-forge**, not the upstream MSVC installer. PyGObject publishes no Windows wheels to PyPI (across every version); the installer+source-build path needs Visual Studio Build Tools + meson/ninja/pkg-config. Conda-forge ships binaries built from the same upstream gvsbuild toolchain — byte-for-byte equivalent DLLs, zero compilation.
- **Python 3.12** is the happy path. 3.13/3.14 may work if matching PyGObject wheels land; 3.11 is fine. The conda env recipe below is deterministic.
- **Copy `43-spike.spec` + `runtime_hook.py` verbatim** — they're the canonical bundling recipe. The only Phase 44 change is renaming `smoke_test.py` → your actual entry point.
- **Bundle size:** 110.7 MB (126 top-level DLLs + 184 plugins + 57 typelibs + support files).
- **GStreamer 1.28.2** MSVC (via conda-forge). TLS via OpenSSL (`gioopenssl.dll`), not GnuTLS — this is a 1.28.x upstream change.

## Evidence of Pass

### SC-1: PyInstaller bundle plays HTTPS audio via playbin3
```
SPIKE_OK audio_sample_received=True duration_s=5.42 errors=[] warnings_count=0
```
Test URL: `https://ice4.somafm.com/dronezone-256-mp3`
First `MessageType.TAG` arrived ≤200ms after `set_state(PLAYING)` returned `GST_STATE_CHANGE_ASYNC`.
User confirmed audibility: `audible`.

### SC-2: TLS backend loads and provides default cert database
```
SPIKE_DIAG tls_backend='GTlsBackendOpenssl' has_default_database=True
```
`Gio.TlsBackend.get_default().get_default_database()` returned a non-None result — the canonical proof that `souphttpsrc` can perform TLS handshakes. Backend DLL bundled at `_internal/gio/modules/gioopenssl.dll`.

### SC-3: Bundle is self-contained (runs outside any conda env)
Smoke test re-ran from a `(base)` PowerShell prompt with the `spike` env deactivated. Identical `plugin_count=185` and `SPIKE_OK audio_sample_received=True duration_s=5.42 errors=[]`. Plugins load from the bundled `_internal/gst_plugins/` directory, not a leaking env PATH.

## Environment (Canonical Recipe)

```powershell
# Miniforge (not Anaconda — lighter and conda-forge defaults)
# https://github.com/conda-forge/miniforge/releases → Miniforge3-Windows-x86_64.exe

conda create -n spike -c conda-forge `
    python=3.12 `
    pygobject pycairo `
    pyinstaller pyinstaller-hooks-contrib `
    gstreamer gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly
conda activate spike
```

**Exact versions observed on the passing iteration:**
- PyInstaller 6.19.0
- pyinstaller-hooks-contrib 2026.2
- PyGObject (gi) 3.56.2
- Python 3.12.13
- GStreamer 1.28.2

## PyInstaller Build Artifacts

### `.spec` structure — key Tree() blocks

```python
# GIO modules (TLS backend + schemas) — the stock hook-gi.repository.Gio.py
# WARNS "Could not determine Gio modules path!" on conda-forge layout and
# ships a broken bundle unless we override explicitly.
gio_modules_tree = Tree(
    str(GST_ROOT / "lib" / "gio" / "modules"),
    prefix="gio/modules",
    excludes=["*.pdb"],
)

# Scanner binary — 1.28.x ships at libexec/gstreamer-1.0/ (was bin/ in 1.24/1.26);
# spec auto-detects via SCANNER_SRC. Placed at bundle root.
extra_binaries = [(str(SCANNER_SRC), ".")]

# GI typelibs — belt-and-suspenders: contrib hook picks them up too, but
# MSVC layout detection has historically been unreliable. Dedup is safe.
typelib_tree = Tree(
    str(GST_ROOT / "lib" / "girepository-1.0"),
    prefix="girepository-1.0",
    excludes=["*.pdb"],
)

# glib-networking schemas
glib_share_tree = Tree(
    str(GST_ROOT / "share" / "glib-2.0" / "schemas"),
    prefix="share/glib-2.0/schemas",
)
```

`GST_ROOT` resolves to `$env:CONDA_PREFIX\Library` when inside an activated conda env.

### Runtime hook (`runtime_hook.py`) env vars

The stock `pyi_rth_gstreamer.py` sets `GST_PLUGIN_PATH`, `GST_PLUGIN_SYSTEM_PATH=""`, `GST_REGISTRY=<meipass>\registry.bin`, `GST_REGISTRY_FORK=no`. The stock rthook does NOT set these three — our custom `runtime_hook.py` does:

| Env var | Value | Why |
|---------|-------|-----|
| `GIO_EXTRA_MODULES` | `<meipass>/gio/modules` | Without this, `souphttpsrc` fails HTTPS with `"TLS/SSL support not available; install glib-networking"`. |
| `GI_TYPELIB_PATH` | `<meipass>/girepository-1.0` | stock `gi` hook sometimes mislocates the dir on Windows. Explicit override. |
| `GST_PLUGIN_SCANNER` | `<meipass>/gst-plugin-scanner.exe` | `playbin3` spawns the scanner for unknown plugins. If unset, GStreamer falls back to in-process scanning (slower, crash-prone on bad plugins). |

Verified at runtime via rthook diagnostic print:
```
SPIKE_DIAG_RTHOOK gio_extra_modules='Z:\\phase43\\dist\\spike\\_internal\\gio\\modules'
gi_typelib_path='Z:\\phase43\\dist\\spike\\_internal\\girepository-1.0'
gst_plugin_scanner='Z:\\phase43\\dist\\spike\\_internal\\gst-plugin-scanner.exe'
```

## Bill of Materials

### Bundle top-level `_internal/` — 126 DLLs, 110.7 MB total

**Core GStreamer libs (not plugins):**
`gstreamer-1.0-0.dll`, `gstbase-1.0-0.dll`, `gstapp-1.0-0.dll`, `gstaudio-1.0-0.dll`, `gstvideo-1.0-0.dll`, `gstadaptivedemux-1.0-0.dll`, `gstanalytics-1.0-0.dll`, `gstbasecamerabinsrc-1.0-0.dll`, `gstcodecparsers-1.0-0.dll`, `gstcodecs-1.0-0.dll`, `gstcuda-1.0-0.dll`, `gstd3d11-1.0-0.dll`, `gstd3dshader-1.0-0.dll`, `gstdxva-1.0-0.dll`, `gstfft-1.0-0.dll`, `gsthip-0.dll`, `gstinsertbin-1.0-0.dll`, `gstisoff-1.0-0.dll`, `gstmpegts-1.0-0.dll`, `gstmse-1.0-0.dll`, `gstnet-1.0-0.dll`, `gstpbutils-1.0-0.dll`, `gstphotography-1.0-0.dll`, `gstriff-1.0-0.dll`, `gstrtp-1.0-0.dll`, `gstrtsp-1.0-0.dll`, `gstsctp-1.0-0.dll`, `gstsdp-1.0-0.dll`, `gsttag-1.0-0.dll`, `gsturidownloader-1.0-0.dll`, `gstwinrt-1.0-0.dll`

**GLib + GObject + GIO:** `glib-2.0-0.dll`, `gobject-2.0-0.dll`, `gio-2.0-0.dll`, `gmodule-2.0-0.dll`, `girepository-2.0-0.dll`, `ffi-8.dll`, `iconv.dll`, `intl-8.dll`, `pcre2-8.dll`

**HTTP/TLS chain:** `soup-3.0-0.dll`, `nghttp2.dll`, `psl-5.dll`, `libssl-3-x64.dll`, `libcrypto-3-x64.dll`, `brotlicommon.dll`, `brotlidec.dll`

**Codecs (libs — plugins live in `gst_plugins/`):** `FLAC.dll`, `ogg.dll`, `vorbis.dll`, `vorbisenc.dll`, `opus.dll`, `mpg123.dll`, `libmp3lame.DLL`, `sndfile.dll`, `libx264-164.dll`

**Font/render chain (playbin3 optional decoders pull these in):** `cairo.dll`, `pango-1.0-0.dll`, `pangocairo-1.0-0.dll`, `pangoft2-1.0-0.dll`, `pangowin32-1.0-0.dll`, `harfbuzz.dll`, `graphite2.dll`, `freetype.dll`, `fontconfig-1.dll`, `fribidi-0.dll`, `jpeg8.dll`, `libpng16.dll`, `pixman-1-0.dll`

**Support:** `python312.dll`, `sqlite3.dll`, `zlib.dll`, `libbz2.dll`, `liblzma.dll`, `libexpat.dll`, `libxml2.dll`, `icudt78.dll`, `icuuc78.dll`, `charset.dll`

**VCRUNTIME + UCRT + api-ms shims:** `MSVCP140.dll`, `VCRUNTIME140.dll`, `VCRUNTIME140_1.dll`, `ucrtbase.dll`, 42× `api-ms-*.dll` (WinSxS redirection layer — PyInstaller ships all of them; pruning is risky and the size is negligible).

### `_internal/gst_plugins/` — 184 plugin DLLs, 16.4 MB

PyInstaller's `hook-gi.repository.Gst.py` in `pyinstaller-hooks-contrib` 2026.2 places plugins in `gst_plugins/` (not `gstreamer-1.0/` as documented in older 2024-era guides — naming changed). The stock `pyi_rth_gstreamer.py` knows this convention; no override needed.

Runtime registry reports `plugin_count=185` — the one extra over the 184 .dll files is a statically-linked coreelements plugin inside `gstreamer-1.0-0.dll`.

Broad-collect-then-prune strategy from the plan held: iteration 1 shipped everything the contrib hook enumerated from the live registry, smoke passed, zero pruning needed. Phase 44 can revisit `exclude_plugins` after integration testing of the full app — common candidates: `gtk*`, `qt5*`, `qt6*`, `d3d11*`, `nv*`, `cuda*`, `vulkan`, `webrtc*`, `opencv`, `vaapi*`, `mse`, `rtsp*`, `rtmp*`, `srt`, `sctp`.

### `_internal/girepository-1.0/` — 57 typelibs

Includes `GioWin32-2.0.typelib` and `GLibWin32-2.0.typelib`. Despite this, GLib emits a `CRITICAL` warning at startup: `"Unable to load platform-specific GIO introspection data: Typelib file for namespace 'GioWin32' (any version) not found"`. The warning is **benign** — the typelib IS bundled; GLib's version-detection logic doesn't locate it through `GI_TYPELIB_PATH` the first time. TLS handshake and playback work regardless. Phase 44 can silence the warning by pinning `GLIB_DISABLE_TYPELIB_VERSION_CHECK=1` or ignore it.

### `_internal/gio/modules/` — 1 DLL: `gioopenssl.dll`

Only one GIO module is strictly required: the TLS backend. `gioopenssl.dll` depends on `libssl-3-x64.dll` + `libcrypto-3-x64.dll` (both in `_internal/`).

## Known Gotchas (catalogue for Phase 44 + future Claude)

| # | Gotcha | Severity | Mitigation |
|---|--------|----------|------------|
| 1 | `pip install pygobject` on Windows always builds from source — no wheels on PyPI | BLOCKER | Use conda-forge. Non-negotiable. |
| 2 | GStreamer 1.28.x switched TLS backend from GnuTLS → OpenSSL. `libgiognutls.dll` no longer exists | MEDIUM | Pre-flight in `build.ps1` accepts either `gioopenssl.dll` (1.28+) or `libgiognutls.dll` (1.26-). Same for .spec assertion. Downstream code uses `Gio.TlsBackend.get_default()` + `get_default_database()` — backend-agnostic. |
| 3 | PyInstaller's stock `hook-gi.repository.Gio.py` logs `"Could not determine Gio modules path!"` on conda-forge layout and ships a broken bundle | BLOCKER | Our `.spec` adds an explicit `gio_modules_tree = Tree(...)` block that bundles `gio/modules/` regardless of hook behavior. Do not remove. |
| 4 | `gst-plugin-scanner.exe` moved from `bin/` (1.24/1.26) to `libexec/gstreamer-1.0/` (1.28+) | MEDIUM | `.spec` detects via `SCANNER_SRC` with `libexec` preferred, `bin/` fallback. |
| 5 | 1.28.x MSVC installer dropped the `\1.0\msvc_x86_64\` subdir — flat tree under INSTALLDIR | LOW | Detectable via `Test-Path "$GstRoot\bin\gstreamer-1.0-0.dll"`. build.ps1 auto-detects from `CONDA_PREFIX`; MSVC path requires explicit `-GstRoot` override. |
| 6 | DI.fm premium URLs reject HTTPS — TLS handshake succeeds but server returns `"Internal data stream error. streaming stopped, reason error (-5)"` | MEDIUM | Phase 44 decision needed: either accept HTTP-only for DI.fm (SC-2 compromise per-provider) OR treat this as a server-side issue DI.fm may fix. For spike, SomaFM HTTPS proved the TLS path works — the GStreamer bundle isn't at fault. |
| 7 | Windows PowerShell 5.1 treats native-command stderr writes as terminating errors under `$ErrorActionPreference = "Stop"`. PyInstaller INFO logs go to stderr | LOW | `build.ps1` uses an `Invoke-Native` helper that locally flips EAP to `Continue`. Red error-text display in the console is cosmetic; `$LASTEXITCODE` checks catch real failures. |
| 8 | `.ps1` script files in Miniforge Prompt (cmd-based) open in Notepad — file association wins | LOW | Launch PowerShell explicitly: `powershell -ExecutionPolicy Bypass -File .\build.ps1`, or run `conda init powershell` + use a real PowerShell window with `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. Documented in README. |
| 9 | UTF-8 em-dashes in `.ps1` files parsed as cp1252/ANSI on PS 5.1 without BOM → multi-byte garbage breaks string literals | LOW | ASCII-only comments/strings in `.ps1`. Use `--` not `—`. |

## Phase 44 Handoff Checklist

- [ ] Copy `43-spike.spec` verbatim into Phase 44's build dir; rename `smoke_test.py` reference to the actual MusicStreamer entry point
- [ ] Copy `runtime_hook.py` verbatim — env vars are app-independent
- [ ] Copy `build.ps1` as the build driver; update `$GstRoot` default if Phase 44 targets a non-conda install path
- [ ] Use the same conda env recipe above as the build env (pin PyInstaller ≥ 6.19, hooks-contrib ≥ 2026.2)
- [ ] Revisit `exclude_plugins` in the hooksconfig once the full MusicStreamer integration is smoke-tested — the 184-plugin broad collect is the starting point, not the final state
- [ ] Decide HTTPS-vs-HTTP policy for DI.fm (gotcha #6) — out of scope for this spike, in-scope for Phase 44 feature completeness
- [ ] Port HLS, cover art HTTP fetch, ICY TAG propagation, yt-dlp integration (explicitly deferred to Phase 44 per D-05)

---

**Provenance:** Empirically validated on Windows 11 VM, iteration 1, no pruning. Evidence in `artifacts/smoke.log` (in-env run) and `artifacts/smoke-clean.log` (deactivated run, SC-3 proof). Both files are gitignored — findings above capture the relevant markers verbatim.
