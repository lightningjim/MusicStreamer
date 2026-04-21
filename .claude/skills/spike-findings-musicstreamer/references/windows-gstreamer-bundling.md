# Windows GStreamer + PyInstaller Bundling

Validated empirically in Phase 43 on Windows 11 with GStreamer 1.28.2. Bundle self-containment proved — spike.exe runs without any conda env active.

## Validated Patterns

### Use conda-forge for the build environment

```powershell
# Miniforge from https://github.com/conda-forge/miniforge/releases
conda create -n spike -c conda-forge `
    python=3.12 `
    pygobject pycairo `
    pyinstaller pyinstaller-hooks-contrib `
    gstreamer gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly
conda activate spike
```

Confirmed working versions: PyInstaller 6.19.0, hooks-contrib 2026.2, PyGObject 3.56.2, Python 3.12.13, GStreamer 1.28.2.

### Custom runtime hook is required

PyInstaller's stock `pyi_rth_gstreamer.py` sets `GST_PLUGIN_PATH`/`GST_REGISTRY`/`GST_PLUGIN_SYSTEM_PATH` — good. But it does NOT set three env vars that GStreamer-on-Windows needs for HTTPS + introspection:

```python
# runtime_hook.py
os.environ["GIO_EXTRA_MODULES"]    = _bundle_path("gio", "modules")
os.environ["GI_TYPELIB_PATH"]      = _bundle_path("girepository-1.0")
os.environ["GST_PLUGIN_SCANNER"]   = _bundle_path("gst-plugin-scanner.exe")
```

Without `GIO_EXTRA_MODULES`, `souphttpsrc` fails HTTPS with "TLS/SSL support not available; install glib-networking". Without `GST_PLUGIN_SCANNER`, `playbin3` spawns scanner in-process (slow, crash-prone on bad plugins). Without `GI_TYPELIB_PATH`, GI type introspection fails intermittently.

### Explicit Tree() blocks override the broken stock `hook-gi.repository.Gio.py`

The 2026.2 contrib hook logs `WARNING: Could not determine Gio modules path!` on conda-forge layout and ships a broken bundle. Fix: explicit `Tree()` for `lib/gio/modules/`:

```python
gio_modules_tree = Tree(
    str(GST_ROOT / "lib" / "gio" / "modules"),
    prefix="gio/modules",
    excludes=["*.pdb"],
)
```

And explicit scanner placement (dual-path detection handles 1.24/1.26 bin/ vs 1.28+ libexec/gstreamer-1.0/):

```python
_scanner_libexec = GST_ROOT / "libexec" / "gstreamer-1.0" / "gst-plugin-scanner.exe"
_scanner_bin     = GST_ROOT / "bin" / "gst-plugin-scanner.exe"
SCANNER_SRC = _scanner_libexec if _scanner_libexec.is_file() else _scanner_bin
extra_binaries = [(str(SCANNER_SRC), ".")]
```

See `sources/43-gstreamer-windows-spike/43-spike.spec` for the full canonical recipe.

### Broad-collect, prune later

On iteration 1, let the contrib hook enumerate the live GStreamer registry and bundle everything (184 plugin DLLs, 16.4 MB). Don't hand-curate `exclude_plugins` until after smoke-test passes — `playbin3`'s autoplug needs `typefindfunctions`, `decodebin3`, and element factories it auto-wires, and hand-curating breaks discovery in non-obvious ways.

Common candidates for `exclude_plugins` after green: `gtk*`, `qt5*`, `qt6*`, `d3d11*`, `nv*`, `cuda*`, `vulkan`, `webrtc*`, `opencv`, `vaapi*`, `mse`, `rtsp*`, `rtmp*`, `srt`, `sctp`.

### Plugin subdir naming — `gst_plugins/` not `gstreamer-1.0/`

PyInstaller hooks-contrib 2026.2 places bundled plugins at `_internal/gst_plugins/`, not the older `_internal/gstreamer-1.0/` naming seen in pre-2024 guides. The stock rthook knows this; you don't need to override `GST_PLUGIN_PATH` manually.

## Landmines

### `pip install PyGObject` on Windows — never works

PyPI has sdist only across all versions (upstream policy). Source build needs Visual Studio Build Tools + meson + ninja + `PKG_CONFIG_PATH` at the GStreamer devel `.pc` files (~1 GB install + risky compile). **Solution: use conda-forge**; it's the only path that Just Works.

### GStreamer 1.28.x flipped the Windows TLS backend from GnuTLS to OpenSSL

`libgiognutls.dll` is gone; the new backend is `gioopenssl.dll`, backed by `libssl-3-x64.dll` + `libcrypto-3-x64.dll` (both auto-picked up by PyInstaller from `<root>/bin/`). Code using `Gio.TlsBackend.get_default().get_default_database()` is backend-agnostic — no app change needed. But pre-flight scripts that hard-code `libgiognutls.dll` existence checks will fail.

### 1.28.x dropped the `\1.0\msvc_x86_64\` subdir

Old upstream layout: `C:\gstreamer\1.0\msvc_x86_64\{bin,lib,share,libexec}\`.
New layout: `C:\gstreamer\{bin,lib,share,libexec}\` (flat under INSTALLDIR).
`GST_ROOT` defaults need updating when bumping across this boundary.

### Upstream installer format changed: split MSIs → single `.exe`

1.24/1.26 shipped separate `gstreamer-1.0-msvc-x86_64-X.Y.Z.msi` + `gstreamer-1.0-devel-msvc-x86_64-X.Y.Z.msi`. 1.28+ consolidated into `gstreamer-1.0-msvc-x86_64-X.Y.Z.exe` (InnoSetup-style wizard with "Complete" feature set). Any automation that silently-installs both MSIs (`msiexec /qn /i`) needs rework. Not relevant if using conda-forge.

### DI.fm premium URLs reject HTTPS

TLS handshake succeeds (`has_default_database=True`), but the server returns `"Internal data stream error. streaming stopped, reason error (-5)"` + `"Stream doesn't contain enough data. Can't typefind"` — server rejects/closes the TLS stream. Confirmed against `https://prem1.di.fm/lounge?<listen_key>`. GStreamer bundle is not at fault. Workaround: accept HTTP for DI.fm streams (compromises SC-2 per-provider), or use a non-DI.fm test URL for validating the TLS path.

### `GioWin32` typelib warning is cosmetic

GLib prints `CRITICAL: Unable to load platform-specific GIO introspection data: Typelib file for namespace 'GioWin32' (any version) not found` at startup. The typelib IS bundled in `girepository-1.0/`; GLib's version-detection doesn't locate it through `GI_TYPELIB_PATH`. TLS + playback work regardless. Silence with `GLIB_DISABLE_TYPELIB_VERSION_CHECK=1` or ignore.

### PowerShell 5.1 native-stderr trap

Any native command's stderr write is treated as a terminating error under `$ErrorActionPreference = "Stop"`. PyInstaller logs INFO to stderr; first INFO line aborts the script.

Fix (see `sources/.../build.ps1`):

```powershell
function Invoke-Native {
    param([scriptblock]$Block)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { & $Block } finally { $ErrorActionPreference = $prev }
}
Invoke-Native { python -m PyInstaller app.spec --noconfirm *>&1 | Tee-Object "build.log" }
```

### UTF-8 in `.ps1` files without a BOM

PS 5.1 parses `.ps1` as cp1252/ANSI. Em-dashes (`—`) become multi-byte garbage that includes quote characters; strings break mid-literal. **Use ASCII only in `.ps1`** or save with UTF-8 BOM.

### Miniforge Prompt is cmd.exe, not PowerShell

`.\build.ps1` in the default Miniforge Prompt opens Notepad (file association). Invoke explicitly: `powershell -ExecutionPolicy Bypass -File .\build.ps1`, or `conda init powershell` and use real PowerShell with `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## Constraints

| Fact | Source |
|------|--------|
| Bundle size ~110 MB | measured on passing build (126 top-level DLLs + 184 plugins + 57 typelibs + support) |
| PyGObject requires C extension build; no wheels on PyPI | upstream policy, all versions including 3.56.2 |
| 1.28.x ships OpenSSL TLS, not GnuTLS | upstream change |
| 1.28.x flat install layout | upstream change |
| PS 5.1 native stderr trap | Windows PowerShell 5.1 only; PS 7+ has `$PSNativeCommandUseErrorActionPreference` |
| Stock `hook-gi.repository.Gio.py` broken on conda-forge | PyInstaller hooks-contrib ≤ 2026.2 |

## Origin

Synthesized from Phase 43 spike (GStreamer Windows bundling validation).
Source files: `sources/43-gstreamer-windows-spike/` — full `.spec`, `runtime_hook.py`, `build.ps1`, `smoke_test.py`, `README.md`, and the canonical `43-SPIKE-FINDINGS.md`.
