# Phase 43 Spike Runbook

Throwaway experiment: validate HTTPS GStreamer playback inside a PyInstaller `--onedir` bundle on a clean Windows 11 VM. Produces `43-SPIKE-FINDINGS.md` + a draft `.spec` for Phase 44 to inherit.

## One-time VM setup (conda-forge path — recommended)

PyGObject ships no Windows wheels on PyPI (upstream policy). The MSVC GStreamer
installer + source-build PyGObject path requires ~1 GB of Visual Studio Build
Tools and a meson/ninja incantation. Conda-forge publishes pre-built
binaries of the exact same gvsbuild output, so we use that.

1. Revert the Win11 VM to a clean snapshot (no system GStreamer on PATH — D-01).
2. Install **Miniforge** from https://github.com/conda-forge/miniforge/releases
   (pick `Miniforge3-Windows-x86_64.exe`, ~80 MB; default options are fine).
3. Open a new **Miniforge Prompt** (Start menu → Miniforge Prompt — NOT plain PowerShell).
4. Create and activate the spike env:
   ```
   conda create -n spike -c conda-forge python=3.12 pygobject pycairo pyinstaller pyinstaller-hooks-contrib gstreamer gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly
   conda activate spike
   ```
5. Sanity check — must print a version + `has_default_database=True`-equivalent:
   ```
   python -c "import gi; gi.require_version('Gst', '1.0'); from gi.repository import Gst, Gio; Gst.init(None); print('Gst:', Gst.version_string()); print('TLS:', Gio.TlsBackend.get_default().get_default_database() is not None)"
   ```
6. Copy this phase directory to the VM (or `git clone` the repo).
7. Populate `test_url.txt` with one AA HTTPS channel URL from your library (contains live listen key — gitignored).

### Alternative: the MSVC installer path (if you want to validate the official MSI distribution)

Skip if you went conda-forge. Only relevant if Phase 44 specifically requires the
upstream MSI tree verbatim:

1. Download `gstreamer-1.0-msvc-x86_64-1.28.2.exe` (~500 MB) from
   https://gstreamer.freedesktop.org/data/pkg/windows/1.28.2/msvc/
2. Install with the **Complete** feature set to `C:\spike-gst\runtime\`.
   Post-install sanity: `C:\spike-gst\runtime\bin\` must contain
   `gstreamer-1.0-0.dll` and `gst-inspect-1.0.exe`.
3. Install Python 3.12 (3.13/3.14 are OK if you find PyGObject wheels — as of 2026 there are none on PyPI).
4. Install Visual Studio 2022 Build Tools with the C++ workload.
5. Set `PKG_CONFIG_PATH=C:\spike-gst\runtime\lib\pkgconfig` and `pip install pygobject pycairo`.
   (This path has not been exercised by this spike. If you take it, expect at least one
   iteration of env-var plumbing.)

## Per-iteration loop

1. Open a **Miniforge Prompt**, `conda activate spike`.
2. `cd` into this phase directory on the VM.
3. Run `.\build.ps1` — detects `CONDA_PREFIX`, skips the pip install, builds via PyInstaller, then smoke-tests.
4. Paste the full content of `artifacts\smoke.log` back into the chat.
5. After pasting, state one word: `audible` or `silent` (whether speakers produced sound).
6. Claude diffs the log, updates `43-spike.spec` or `runtime_hook.py`, commits, and you re-run step 3.

## Pass conditions

Spike passes when a single iteration produces:
- `SPIKE_OK audio_sample_received=True` in `smoke.log`
- `SPIKE_DIAG ... has_default_database=True` in `smoke.log` (proves a GIO TLS backend loaded — `gioopenssl.dll` on 1.28+, `libgiognutls.dll` on 1.26-)
- You reply `audible` (optional — `silent` with `SPIKE_OK` still counts, logs a VM audio note)

Then Claude runs `/gsd-spike-wrap-up` to persist findings. ≤5 iteration budget before scope revisit.

## Never commit

`test_url.txt`, `artifacts/`, `build/`, `dist/` — all in `.gitignore`.
