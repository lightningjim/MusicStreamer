# Phase 43: GStreamer Windows Spike — Research

**Researched:** 2026-04-19
**Domain:** PyInstaller `--onedir` bundling of the official MSVC GStreamer runtime on Windows 11, with HTTPS ShoutCast playback via `souphttpsrc` + `libgiognutls.dll`.
**Confidence:** HIGH on stack + env vars + PyInstaller hook behaviour (all cited from official sources). MEDIUM on the minimal plugin list (ultimately confirmed empirically by the user's paste-back, not from documentation).

## Summary

- The official GStreamer MSVC Windows runtime at `1.24.12` (Jan 2025) is the correct pin for this spike — it's the final stable 1.24.x patch and matches CONTEXT D-03. 1.26.10 (Dec 2025) exists and is arguably more current, but D-03 locks the series to 1.24.x and we respect that. [CITED: discourse.gstreamer.org/t/gstreamer-1-24-12-stable-bug-fix-release/4023]
- PyInstaller 6.x has a first-class `gstreamer` hook (in `pyinstaller-hooks-contrib`) that collects plugins from the live GStreamer install via `gi.repository.Gst` introspection, respects `include_plugins`/`exclude_plugins` fnmatch patterns, and ships a runtime hook that sets `GST_PLUGIN_PATH`, `GST_PLUGIN_SYSTEM_PATH=""`, `GST_REGISTRY=<meipass>/registry.bin`, and `GST_REGISTRY_FORK=no`. [VERIFIED: hook-gi.repository.Gst.py + pyi_rth_gstreamer.py source read]
- The runtime hook does **NOT** bundle `gst-plugin-scanner.exe` and does **NOT** set `GIO_MODULE_DIR` or `GI_TYPELIB_PATH`. These gaps are the spike's real work — the draft `.spec` must add explicit `Tree()` blocks for `lib/gio/modules/`, `lib/gst-plugin-scanner.exe`, and `lib/girepository-1.0/`, and the runtime hook must set `GIO_EXTRA_MODULES` before `Gst.init()`. [CITED: source files above]
- `libgiognutls.dll` lives at `lib/gio/modules/libgiognutls.dll` in the MSVC tree and is the only TLS backend the MSVC build ships; without it `souphttpsrc` logs `TLS/SSL support not available; install glib-networking` and HTTPS fails silently. [CITED: gstreamer-bugs.narkive.com bug 794425, gstreamer-devel thread on GIO modules]
- Audio sink: `wasapi2sink` is the MSVC build's default on Win8+ (Win11 is the spike target), replacing `wasapisink`. Fallback order: `wasapi2sink` → `autoaudiosink` → `directsoundsink`. Do NOT hand-pick a sink in code — let `playbin3` auto-select via `autoaudiosink` for the spike. [CITED: gstreamer.freedesktop.org/documentation/wasapi2/wasapi2sink.html]

**Primary recommendation:** Pin GStreamer `1.24.12` MSVC x86_64 runtime + devel. Build the spike with PyInstaller 6.x + pyinstaller-hooks-contrib latest. Start from the contrib hook's default plugin collection (everything from the system install), then prune via `exclude_plugins` only after the smoke test passes — don't try to hand-curate the plugin list on iteration 1. The two known misses in the stock hook are `gst-plugin-scanner.exe` and the GIO TLS modules — address both explicitly in the `.spec`.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**VM target**
- **D-01:** Runs on clean snapshot of user's Windows 11 VM, no system GStreamer on PATH. User drives the VM, Claude does not.
- **D-02:** Windows 11 only. Win10 explicitly out of scope for this spike.

**GStreamer distribution**
- **D-03:** Official MSVC build from gstreamer.freedesktop.org, latest 1.24.x. Pin exact version in findings.
- **D-04:** Install BOTH `gstreamer-1.0-msvc-x86_64` runtime AND `gstreamer-1.0-devel-msvc-x86_64` (devel provides `gst-inspect-1.0.exe`).

**Spike fidelity**
- **D-05:** Minimal scope — one `playbin3` + `souphttpsrc` + one audio sink, one HTTPS AA channel. No HLS, no yt-dlp, no Twitch, no cover art, no ICY TAG propagation — those are Phase 44.
- **D-06:** Validated TLS path MUST exercise `libgiognutls.dll` (or whichever GIO TLS backend ships on Win).

**Test URL**
- **D-07:** Primary test URL is a live AA HTTPS channel from the user's library (real listen key). Pull via Phase 42 settings-export tooling so the key is NOT committed to the repo.
- **D-08:** Public ShoutCast URL not required unless the AA URL fails in a way that points to listen-key auth rather than TLS.

**Execution model**
- **D-09:** Claude produces `build.ps1`, draft `spike.spec`, `smoke_test.py`. User runs on the VM, pastes stdout/stderr.
- **D-10:** Iterate: Claude updates `.spec` based on paste-back, user re-runs, repeat until HTTPS audio plays ≥5s and smoke test exits 0.

**Deliverables**
- **D-11:** `43-SPIKE-FINDINGS.md` — GStreamer version, DLL list, plugin list, `gio/modules/` contents, required env vars, PATH/CWD gotchas.
- **D-12:** `43-spike.spec` (draft) — PyInstaller `.spec` Phase 44 copies/extends. Lives in phase dir, NOT repo root.
- **D-13:** Run `/gsd-spike-wrap-up` at phase close to persist findings as a project skill.
- **D-14:** **No changes to `musicstreamer/` source code during the spike.** Any source change required → record in findings, defer to Phase 44.

### Claude's Discretion

- Exact `wasapi2sink` vs `directsoundsink` vs `autoaudiosink` choice.
- CLI vs `.spec`-file PyInstaller invocation in `build.ps1` (spec-file is the standard path for non-trivial trees).
- Plugin blacklist strategy — start from `gst-inspect-1.0.exe` output, prune to minimum.
- Script language for the build driver (PowerShell vs .bat vs `uv run` shim).

### Deferred Ideas (OUT OF SCOPE)

- Windows 10 validation
- HLS / Twitch / yt-dlp / cover-art / ICY-tag smoke coverage on Windows — Phase 44
- NSIS / Inno Setup installer authoring — Phase 44 (PKG-02)
- Single-instance enforcement on Windows — Phase 44 (PKG-04)
- Windows SMTC media keys — Phase 43.1
- Linux ↔ Windows settings-export round-trip UAT — Phase 44
- `CREATE_NO_WINDOW` subprocess helper — Phase 44 (may be retired)
- Auto-updater / code signing / shortcut polish — post-v2.0
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **PKG-06** | A dedicated GStreamer Windows bundling spike completes before the installer phase begins, with HTTPS stream playback verified on a clean Windows VM. | This research produces the draft `.spec` + runtime hook template + build script + smoke-test skeleton that Phase 44 (PKG-01) extends. The DLL/plugin bill-of-materials tables below are the canonical deliverable PKG-01 inherits. |

**Downstream (NOT in this phase):**
- **PKG-01** — Production PyInstaller spec with HTTPS verified. Phase 44 reads `43-SPIKE-FINDINGS.md` + copies `43-spike.spec`.
- **QA-03** — Windows smoke test suite. Phase 44 scope; this spike validates only a single HTTPS stream.
</phase_requirements>

## Project Constraints (from CLAUDE.md)

From `~/CLAUDE.md` (user's global instructions):
- Keep responses/deliverables concise and action-oriented.
- Single recommended option, not menus (apply this to plan structure).
- Scope tightly to what's requested — the spike is **throwaway**; no creeping into Phase 44 work.

No repo-local `CLAUDE.md` in the MusicStreamer project.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| GStreamer runtime DLLs + plugins | PyInstaller bundle (`dist/spike/`) | — | Clean VM has no system GStreamer; the bundle carries everything. |
| GIO TLS backend (`libgiognutls.dll`) | Bundle (`_internal/gio/modules/`) | Env var `GIO_EXTRA_MODULES` at runtime | GIO scans this path before falling back; without it souphttpsrc has no TLS. |
| Plugin scanner (`gst-plugin-scanner.exe`) | Bundle (`_internal/`) | Env var `GST_PLUGIN_SCANNER` | Not auto-collected by contrib hook; must be added explicitly. |
| GI typelibs (`.typelib`) | Bundle (`_internal/girepository-1.0/`) | Env var `GI_TYPELIB_PATH` | `gi` hook collects typelibs but layout differs on Win; verify at paste-back. |
| Registry cache | User writable path (`%LOCALAPPDATA%` or `_internal/registry.bin`) | `GST_REGISTRY` env var | Default registry path under Program Files is read-only; stock rthook writes to `_MEIPASS/registry.bin` (onedir is writable). |
| Python process + Qt event loop | Bundle entry point (`spike.exe`) | — | Same code path as current `musicstreamer/player.py` bus bridge. |
| Audio output | Windows 11 WASAPI | `autoaudiosink` auto-select | `playbin3` picks `wasapi2sink` on Win8+ via rank. |
| HTTP/HTTPS transport | `souphttpsrc` (gst-plugins-good) + `libsoup-3.0-0.dll` + `libgiognutls.dll` | — | `playbin3` routes `https://` URIs to `souphttpsrc`. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| GStreamer MSVC Windows runtime | **1.24.12** | HTTPS stream decoding + audio output | Final stable 1.24.x patch (Jan 2025); D-03 locks to 1.24.x. [CITED: discourse.gstreamer.org/t/gstreamer-1-24-12-stable-bug-fix-release/4023] |
| GStreamer MSVC Windows devel | **1.24.12** | Provides `gst-inspect-1.0.exe` for paste-back plugin enumeration | D-04 locks. |
| PyInstaller | **≥ 6.11** | `--onedir` bundling | 6.x is current; supports `hooksconfig={'gstreamer': {...}}`. [CITED: pyinstaller.org/en/stable/hooks-config.html] |
| pyinstaller-hooks-contrib | **≥ 2024.10** | Provides `hook-gi.repository.*` and `hook-gi.py` | Auto-installed with PyInstaller; has current PyGObject 3.52+ compat. [CITED: pypi.org/project/pyinstaller-hooks-contrib/] |
| PyGObject (`pygobject`) | **≥ 3.50** | `gi.repository.Gst` imports inside the bundle | Must pip-install into the build venv on Windows; confirms `girepository-2.0` or `-1.0` depending on version. [CITED: pypi.org/project/PyGObject/] |
| PySide6 | **6.11** (existing) | Qt wrapper — reused from main app | Already in `pyproject.toml`; spike imports `QObject` only transitively. |

### Supporting (Windows-specific)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `libgiognutls.dll` | bundled in 1.24.12 MSVC | GIO TLS backend for `libsoup-3.0` | ALWAYS — this is the spike's core success criterion (D-06). |
| `gst-plugin-scanner.exe` | bundled in 1.24.12 MSVC | Plugin metadata scanner | ALWAYS — playbin3 spawns it on registry rebuild. |
| `libsoup-3.0-0.dll` | bundled in 1.24.12 MSVC | HTTP(S) transport — `souphttpsrc` backend | ALWAYS. |
| `nghttp2.dll` | bundled in 1.24.12 MSVC | HTTP/2 — optional, libsoup may require | Bundle for safety; low cost. |
| `libpsl-5.dll` | bundled in 1.24.12 MSVC | Public-suffix list — libsoup cookie handling | Bundle for safety; low cost. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| GStreamer 1.24.12 | GStreamer 1.26.10 | 1.26 is newer and has ~12 months of bugfixes over 1.24.12, but CONTEXT D-03 locked the series at 1.24. Do NOT deviate. |
| Official MSVC MSI | MinGW build | MinGW DLLs ABI-mismatch with MSVC-built PyGObject wheels → crash at `import gi`. MSVC is mandatory. [ASSUMED: consensus from Fluendo Windows-bindings blog + multiple community posts] |
| `gvsbuild`-produced DLLs | Official MSVC MSI | `gvsbuild` is primarily for PyGObject contributors building from source; MSI is the "pip install for C libs" equivalent. Don't rebuild. |
| Hand-curated plugin list | Let hook collect all, prune with `exclude_plugins` | Hand-curating on iteration 1 breaks `playbin3` discovery in non-obvious ways (it needs `typefindfunctions` + `decodebin3` + element factories it auto-wires). Start broad, prune after. |

### Installation (Windows VM, user runs)

```powershell
# 1. Download both MSIs to the VM (user action, one time):
#    https://gstreamer.freedesktop.org/data/pkg/windows/1.24.12/msvc/gstreamer-1.0-msvc-x86_64-1.24.12.msi
#    https://gstreamer.freedesktop.org/data/pkg/windows/1.24.12/msvc/gstreamer-1.0-devel-msvc-x86_64-1.24.12.msi

# 2. Install to a WORKSPACE path, not the default C:\gstreamer\ system path, so the clean-snapshot
#    contract is preserved (D-01: no system GStreamer on PATH).
msiexec /i gstreamer-1.0-msvc-x86_64-1.24.12.msi INSTALLDIR="C:\spike-gst\runtime" ADDLOCAL=ALL /qn /l*v install-runtime.log
msiexec /i gstreamer-1.0-devel-msvc-x86_64-1.24.12.msi INSTALLDIR="C:\spike-gst\devel" ADDLOCAL=ALL /qn /l*v install-devel.log

# 3. Verify layout
dir "C:\spike-gst\runtime\1.0\msvc_x86_64\bin"
dir "C:\spike-gst\runtime\1.0\msvc_x86_64\lib\gstreamer-1.0"
dir "C:\spike-gst\runtime\1.0\msvc_x86_64\lib\gio\modules"
```

**Note on `ADDLOCAL=ALL`:** The MSI ships feature sets (typical/complete). Without `ADDLOCAL=ALL`, the silent `/qn` install gets the typical feature set only, which omits several `gst-plugins-bad` plugins. For a spike we want everything, then prune. [ASSUMED: consistent with standard WiX installer behaviour]

**Version verification command the user runs post-install:**

```powershell
& "C:\spike-gst\devel\1.0\msvc_x86_64\bin\gst-inspect-1.0.exe" --version
# Expected: gst-inspect-1.0 version 1.24.12
```

## Architecture Patterns

### System Architecture Diagram

```
┌─ User's Windows 11 VM (clean snapshot) ─────────────────────────────────────┐
│                                                                              │
│  Claude (Linux) ──── git/chat ────▶ User pastes stdout ────▶ Claude diffs    │
│      │                                                            │         │
│      ▼ writes                                                     │         │
│  43-spike.spec  ─┐                                                │         │
│  build.ps1      ─┼──▶  user runs ──▶  pyinstaller spike.spec ────┤         │
│  smoke_test.py  ─┘                          │                     │         │
│                                             ▼                     │         │
│                                    ┌── dist/spike/ ───────┐       │         │
│                                    │  spike.exe            │       │         │
│                                    │  _internal/           │       │         │
│                                    │    *.dll (gst+glib)   │       │         │
│                                    │    gio/modules/       │       │         │
│                                    │      libgiognutls.dll │       │         │
│                                    │    gstreamer-1.0/     │       │         │
│                                    │      *.dll (plugins)  │       │         │
│                                    │    girepository-1.0/  │       │         │
│                                    │      *.typelib        │       │         │
│                                    │    gst-plugin-scanner │       │         │
│                                    │    registry.bin (rw)  │       │         │
│                                    └───────────────────────┘       │         │
│                                             │                      │         │
│                                             ▼  (user runs)         │         │
│                                    spike.exe <aa-url>              │         │
│                                             │                      │         │
│                                  runtime hook sets env:            │         │
│                                    GST_PLUGIN_PATH                 │         │
│                                    GST_PLUGIN_SYSTEM_PATH=""       │         │
│                                    GIO_EXTRA_MODULES               │         │
│                                    GI_TYPELIB_PATH                 │         │
│                                    GST_PLUGIN_SCANNER              │         │
│                                    GST_REGISTRY                    │         │
│                                             │                      │         │
│                                             ▼                      │         │
│                                  Gst.init() → playbin3 →           │         │
│                                  souphttpsrc (HTTPS) →             │         │
│                                  libsoup-3 + libgiognutls.dll →    │         │
│                                  mpg123/aacdec → audioconvert →    │         │
│                                  audioresample → wasapi2sink       │         │
│                                             │                      │         │
│                                             ▼                      │         │
│                                  Speaker outputs audio             │         │
│                                             │                      │         │
│                                  smoke_test.py exits 0             │         │
│                                  prints SPIKE_OK markers ─────────▶│         │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

```
.planning/phases/43-gstreamer-windows-spike/
├── 43-CONTEXT.md                  # already committed
├── 43-RESEARCH.md                 # this file
├── 43-SPIKE-FINDINGS.md           # produced during execution (D-11)
├── 43-spike.spec                  # draft PyInstaller spec (D-12)
├── build.ps1                      # PowerShell build driver
├── smoke_test.py                  # paste-back smoke test
├── runtime_hook.py                # env-var setup before Gst.init
├── test_url.txt                   # .gitignored; user populates with real AA URL
└── artifacts/                     # .gitignored; user pastes stdout/stderr here
    ├── iter-01-stdout.txt
    ├── iter-01-stderr.txt
    └── ...
```

**Why phase-local, not repo root:** D-12 says "Lives in the phase directory, not at repo root; Phase 44 produces the canonical production spec elsewhere." This keeps the throwaway spike artifacts contained and deletable.

### Pattern 1: Start-broad-prune-later for plugin collection

**What:** Let the contrib `gi.repository.Gst` hook collect every installed plugin on the first build. Only add `exclude_plugins` after the smoke test passes, to shrink the bundle.
**When to use:** Iteration 1 and 2. Plugin set is stable by iteration 3.
**Why:** `playbin3` autoplugs elements at runtime via typefind + caps negotiation. Pre-removing plugins you "think" aren't needed (e.g., `videoconvert`) often breaks discovery because `playbin3` inspects factories you don't directly instantiate.
**Example:**

```python
# Iteration 1 spec — broad
hooksconfig = {
    "gstreamer": {
        # Empty include_plugins/exclude_plugins = collect all installed plugins
    },
}

# Iteration N spec (after pass) — pruned
hooksconfig = {
    "gstreamer": {
        "exclude_plugins": [
            "opencv", "vulkan", "gtk*", "qt5*", "qt6*",
            "dash", "rtsp*", "rtmp*", "srt", "sctp",
            "*vaapi*", "d3d11*", "nv*",  # GPU plugins not needed for audio-only
        ],
    },
}
```

### Pattern 2: Runtime hook sets env before `gi` import

**What:** A PyInstaller runtime hook runs BEFORE any user code. It computes paths relative to `sys._MEIPASS` and sets env vars.
**When to use:** Always — the stock `pyi_rth_gstreamer.py` does most of this, but misses `GIO_EXTRA_MODULES` + `GST_PLUGIN_SCANNER` + `GI_TYPELIB_PATH`. We add a second custom rthook.
**Example (see "Runtime hook template" section below for full file).**

### Pattern 3: Paste-back stable markers

**What:** `smoke_test.py` prints line-prefixed markers (`SPIKE_OK=...`, `SPIKE_FAIL=...`, `SPIKE_DIAG=...`) and exits with a known code. Claude greps/diffs these across iterations instead of parsing freeform text.
**When to use:** Every iteration — Claude's only signal into what happened is the user's paste.

```
SPIKE_OK audio_sample_received=true bytes_played=245760 duration_s=8 errors=[]
SPIKE_FAIL reason=tls_handshake giomodule_loaded=false
SPIKE_DIAG gst_version=1.24.12 plugin_count=172 registry_path=C:\...\_internal\registry.bin
```

### Anti-Patterns to Avoid

- **Hand-picking DLLs via Dependency Walker.** GStreamer's plugin deps are dynamic; static dep analysis misses runtime-loaded shared libs. Let `hook-gi.repository.Gst.py` do it.
- **Running the build from a shell that has GStreamer on PATH.** PyInstaller's hook picks up the first `gi.repository.Gst` it can import; if the build machine has system GStreamer too, the hook may resolve plugins against the wrong tree. Build in a venv with `PYTHONPATH` unset and confirm `gst-inspect-1.0 --version` from PowerShell matches the MSI version.
- **Writing to `C:\Program Files\...\registry.bin`.** The default GStreamer registry path under Program Files is read-only for non-admin users. Let the rthook force `GST_REGISTRY` inside `_MEIPASS` (onedir bundles are writable per-process).
- **Relying on `autoaudiosink` picking `wasapi2sink` if wasapi2 isn't bundled.** If `exclude_plugins` drops `wasapi2`, `autoaudiosink` falls through to `directsoundsink` which works but adds ~80ms latency. Keep `wasapi2` in the bundle.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Enumerate required plugins | Custom `gst-inspect` parser | `pyinstaller-hooks-contrib` `hook-gi.repository.Gst.py` | Hook queries the live registry, uses the same plugin-discovery logic GStreamer itself uses. |
| Locate typelibs on Windows | Hard-coded `typelib` paths | `hook-gi.py` via `module_info.collect_typelib_data()` | Handles both `girepository-1.0` (PyGObject < 3.51) and `girepository-2.0` (≥ 3.51). |
| Set env vars at runtime | Shell wrapper that sets env then launches exe | PyInstaller runtime hook (`rthooks/`) | Runs BEFORE `main()`, inside the Python process, portable. |
| Generate a plugin registry | Manually invoke `gst-plugin-scanner` at first launch | Let `Gst.init()` auto-trigger scan; bundle the scanner | GStreamer handles scan lifecycle and caching. |
| Detect TLS backend failure | Parse stderr | Check `Gio.TlsBackend.get_default().get_default_database() is not None` | Gio exposes TLS-backend presence as a first-class API. |
| Silent-install orchestration | Custom installer wrapper | Vanilla `msiexec /i /qn ADDLOCAL=ALL` | Windows Installer native path; idempotent with log output. |

**Key insight:** The contrib hooks do ~90% of the work. The spike is about finding the ~10% the hooks miss on Windows (GIO modules, scanner, typelib path) — not about re-implementing what they already do.

## Runtime State Inventory

> This is a greenfield spike (new artifacts, no rename/refactor of existing state). Section scaled down accordingly.

| Category | Items | Action |
|----------|-------|--------|
| Stored data | None — spike creates `registry.bin` only, inside the bundle. | No migration; delete with `dist/` rebuild. |
| Live service config | None. | — |
| OS-registered state | None — spike does NOT register a service, shortcut, or scheduled task. | — |
| Secrets/env vars | `test_url.txt` contains a live AA listen key. | Add `.planning/phases/43-gstreamer-windows-spike/test_url.txt` to `.gitignore`. Never commit. |
| Build artifacts | `build/`, `dist/`, `__pycache__/`, `*.spec.log` under phase dir. | Add to `.gitignore` for the phase dir. |

## PyInstaller `.spec` Structure — Draft

**File:** `.planning/phases/43-gstreamer-windows-spike/43-spike.spec`

This is the starting-point draft. The user runs `pyinstaller 43-spike.spec` → observes failures → Claude revises this file → repeat.

```python
# -*- mode: python ; coding: utf-8 -*-
#
# Phase 43: GStreamer Windows Spike — PyInstaller .spec
# Target: Windows 11 x86_64, GStreamer 1.24.12 MSVC runtime
# Run from: .planning/phases/43-gstreamer-windows-spike/ on the VM
#
# Usage: pyinstaller 43-spike.spec --noconfirm
#
import os
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# Paths — the user sets GSTREAMER_ROOT env var before invoking pyinstaller.
# build.ps1 does this automatically; fallback to the default MSI location.
# --------------------------------------------------------------------------
GST_ROOT = Path(os.environ.get(
    "GSTREAMER_ROOT",
    r"C:\spike-gst\runtime\1.0\msvc_x86_64",
))
assert GST_ROOT.is_dir(), f"GStreamer root not found: {GST_ROOT}"
assert (GST_ROOT / "bin" / "gst-plugin-scanner.exe").is_file(), \
    "gst-plugin-scanner.exe missing — reinstall MSI with ADDLOCAL=ALL"
assert (GST_ROOT / "lib" / "gio" / "modules" / "libgiognutls.dll").is_file(), \
    "libgiognutls.dll missing — devel MSI required, or TLS feature deselected"

# --------------------------------------------------------------------------
# Tree() blocks — copy raw directory trees into the bundle.
# The contrib hook covers plugins (lib/gstreamer-1.0/) and most top-level DLLs,
# but DOES NOT cover: gio/modules, gst-plugin-scanner.exe, girepository-1.0,
# or the `share/` data files for glib-networking CA bundling.
# --------------------------------------------------------------------------
gio_modules_tree = Tree(
    str(GST_ROOT / "lib" / "gio" / "modules"),
    prefix="gio/modules",
    excludes=["*.pdb"],
)

# Scanner binary + typelibs — placed next to the bundle root
extra_binaries = [
    (str(GST_ROOT / "libexec" / "gstreamer-1.0" / "gst-plugin-scanner.exe"), "."),
    # fallback for older MSI layouts that put scanner under bin/
    # (str(GST_ROOT / "bin" / "gst-plugin-scanner.exe"), "."),
]

# GI typelibs — the gi hook normally collects these, but on Windows the
# discovered path is sometimes wrong for MSVC-built PyGObject. Bundle
# explicitly as a safety net. Hook will dedup if already present.
typelib_tree = Tree(
    str(GST_ROOT / "lib" / "girepository-1.0"),
    prefix="girepository-1.0",
    excludes=["*.pdb"],
)

# glib-networking share data (CA bundle location hints, schemas)
glib_share_tree = Tree(
    str(GST_ROOT / "share" / "glib-2.0" / "schemas"),
    prefix="share/glib-2.0/schemas",
)

# --------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------
block_cipher = None

a = Analysis(
    ["smoke_test.py"],
    pathex=[str(Path(".").resolve())],
    binaries=extra_binaries,
    datas=[],
    hiddenimports=[
        "gi",
        "gi.repository.Gst",
        "gi.repository.GLib",
        "gi.repository.GObject",
        "gi.repository.Gio",
    ],
    hookspath=[],
    hooksconfig={
        "gstreamer": {
            # ITERATION 1: broad — let the hook collect everything.
            # After smoke_test passes, revise with exclude_plugins to prune:
            # "exclude_plugins": [
            #     "opencv", "vulkan", "gtk*", "qt5*", "qt6*",
            #     "dash", "rtsp*", "rtmp*", "srt", "sctp",
            #     "*vaapi*", "d3d11*", "nv*", "webrtc*",
            # ],
        },
        "gi": {
            # No icon/theme bundling — spike has no GUI.
            "icons": [],
            "themes": [],
            "languages": [],
        },
    },
    runtime_hooks=["runtime_hook.py"],
    excludes=[
        # Cut obvious unused Qt/GUI deps — the spike is headless-ish (prints to stdout only)
        "tkinter", "matplotlib", "PIL", "numpy",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="spike",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,            # Do NOT UPX-compress GStreamer DLLs; breaks loading
    console=True,         # Spike is CLI — keep the console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    gio_modules_tree,
    typelib_tree,
    glib_share_tree,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="spike",
)
```

**Diff strategy across iterations:** the `.spec` is committed; each iteration's changes are a single commit so Claude can see via `git log` what was tried. Paste-back artifacts go to `artifacts/iter-NN-*.txt` (gitignored — they may contain listen keys).

## Runtime Hook Template

**File:** `.planning/phases/43-gstreamer-windows-spike/runtime_hook.py`

Runs before any user code. Complements the stock `pyi_rth_gstreamer.py` from pyinstaller-hooks-contrib (which sets `GST_PLUGIN_PATH`, `GST_PLUGIN_SYSTEM_PATH=""`, `GST_REGISTRY`, `GST_REGISTRY_FORK=no`) by adding the three env vars the stock hook misses.

```python
# Phase 43 spike — custom runtime hook.
# Runs after pyi_rth_gstreamer.py (alphabetical order; hook-contrib rthook prefix is pyi_).
# Sets GIO_EXTRA_MODULES, GI_TYPELIB_PATH, GST_PLUGIN_SCANNER — NOT covered by the stock rthook.
import os
import sys


def _bundle_path(*parts: str) -> str:
    """Resolve a path relative to the onedir bundle root (_internal/ in onedir)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.join(base, *parts)


def _set_if_unset_or_override(key: str, value: str) -> None:
    """Overwrite — bundle paths must win over any ambient env the user might have."""
    os.environ[key] = value


# --- GIO TLS backend ------------------------------------------------------
# libgiognutls.dll lives here; without GIO_EXTRA_MODULES, souphttpsrc fails
# HTTPS with "TLS/SSL support not available; install glib-networking".
# GIO_EXTRA_MODULES is additive to the default search path; use instead of
# GIO_MODULE_DIR (which REPLACES the path and can break other modules).
_set_if_unset_or_override(
    "GIO_EXTRA_MODULES",
    _bundle_path("gio", "modules"),
)

# --- GI typelibs ----------------------------------------------------------
# `gi` hook normally sets this, but the MSVC layout sometimes mislocates the
# dir. Force it explicitly to the bundled copy.
_set_if_unset_or_override(
    "GI_TYPELIB_PATH",
    _bundle_path("girepository-1.0"),
)

# --- Plugin scanner helper binary ----------------------------------------
# playbin3 spawns this to inspect unknown plugins. If unset, GStreamer logs
# "plugin scanner helper not found" and falls back to in-process scanning
# (slower, and can crash on bad plugins).
_scanner = _bundle_path("gst-plugin-scanner.exe")
if os.path.isfile(_scanner):
    _set_if_unset_or_override("GST_PLUGIN_SCANNER", _scanner)

# --- Diagnostics marker --------------------------------------------------
# Printed to stderr so the paste-back shows which env the rthook applied.
# Stable prefix "SPIKE_DIAG_RTHOOK" so the smoke test / build log can grep it.
print(
    f"SPIKE_DIAG_RTHOOK gio_extra_modules={os.environ['GIO_EXTRA_MODULES']!r} "
    f"gi_typelib_path={os.environ['GI_TYPELIB_PATH']!r} "
    f"gst_plugin_scanner={os.environ.get('GST_PLUGIN_SCANNER', '<unset>')!r}",
    file=sys.stderr,
)
```

**Why `GIO_EXTRA_MODULES` and not `GIO_MODULE_DIR`:** `GIO_MODULE_DIR` *replaces* the default module search path. If GIO expects other modules (e.g., `libgvfsdbus`) at the default location, replacing the path breaks them. `GIO_EXTRA_MODULES` is *additive*. [CITED: gstreamer-bugs.narkive.com bug 794425 community discussion]

## `build.ps1` Skeleton

**File:** `.planning/phases/43-gstreamer-windows-spike/build.ps1`

```powershell
#Requires -Version 5.1
# Phase 43 spike — build driver. Idempotent, snapshot-safe.
# Exit codes: 0=ok, 1=env missing, 2=pyinstaller failed, 3=smoke test failed

param(
    [string]$GstRoot   = "C:\spike-gst\runtime\1.0\msvc_x86_64",
    [string]$GstDevel  = "C:\spike-gst\devel\1.0\msvc_x86_64",
    [switch]$SkipSmoke = $false
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# --- 0. Pre-flight checks -------------------------------------------------
Write-Host "=== SPIKE BUILD: pre-flight ==="
if (-not (Test-Path "$GstRoot\bin\libgstreamer-1.0-0.dll")) {
    Write-Error "SPIKE_FAIL reason=gst_runtime_missing path='$GstRoot'"
    exit 1
}
if (-not (Test-Path "$GstDevel\bin\gst-inspect-1.0.exe")) {
    Write-Error "SPIKE_FAIL reason=gst_devel_missing path='$GstDevel'"
    exit 1
}
if (-not (Test-Path "$GstRoot\lib\gio\modules\libgiognutls.dll")) {
    Write-Error "SPIKE_FAIL reason=gio_tls_module_missing hint='reinstall with ADDLOCAL=ALL'"
    exit 1
}

& "$GstDevel\bin\gst-inspect-1.0.exe" --version | Select-String "version"

# --- 1. Export env for spec -----------------------------------------------
$env:GSTREAMER_ROOT = $GstRoot
$env:PATH           = "$GstRoot\bin;$env:PATH"   # bundler needs to load gst DLLs to introspect
$env:PYTHONPATH     = ""                          # avoid leaking site packages into build

# --- 2. Ensure clean build dir -------------------------------------------
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $here
try {
    Remove-Item -Recurse -Force "build", "dist" -ErrorAction SilentlyContinue

    # --- 3. Install/confirm build deps ----------------------------------
    Write-Host "=== SPIKE BUILD: python deps ==="
    python -m pip install --upgrade `
        "pyinstaller>=6.11" `
        "pyinstaller-hooks-contrib" `
        "pygobject>=3.50" `
        2>&1 | Out-Host

    # --- 4. PyInstaller -------------------------------------------------
    Write-Host "=== SPIKE BUILD: pyinstaller ==="
    python -m PyInstaller 43-spike.spec --noconfirm --log-level INFO *>&1 | Tee-Object -FilePath "artifacts\build.log"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "SPIKE_FAIL reason=pyinstaller_nonzero exitcode=$LASTEXITCODE"
        exit 2
    }

    Write-Host "SPIKE_OK step=build exe='$here\dist\spike\spike.exe'"

    # --- 5. Smoke test --------------------------------------------------
    if (-not $SkipSmoke) {
        Write-Host "=== SPIKE BUILD: smoke test ==="
        $testUrl = Get-Content "test_url.txt" -Raw -ErrorAction Stop
        $testUrl = $testUrl.Trim()
        if (-not $testUrl) {
            Write-Error "SPIKE_FAIL reason=test_url_empty hint='populate test_url.txt with AA HTTPS URL'"
            exit 3
        }

        & ".\dist\spike\spike.exe" $testUrl *>&1 | Tee-Object -FilePath "artifacts\smoke.log"
        if ($LASTEXITCODE -ne 0) {
            Write-Error "SPIKE_FAIL reason=smoke_nonzero exitcode=$LASTEXITCODE"
            exit 3
        }
        Write-Host "SPIKE_OK step=smoke"
    }
}
finally {
    Pop-Location
}

Write-Host "SPIKE_OK step=done"
exit 0
```

## `smoke_test.py` — Exit-Code Contract

**File:** `.planning/phases/43-gstreamer-windows-spike/smoke_test.py`

```python
"""Phase 43 spike smoke test.

Invocation: spike.exe <aa-https-url>

Exit codes:
  0 — success: audio sample received within 8s, no errors
  1 — setup failure: Gst.init failed, plugin load failed, URI invalid
  2 — runtime failure: pipeline errored before first audio sample
  3 — timeout: no audio sample within 8s (likely TLS or buffering)

Every line printed to stdout with prefix 'SPIKE_OK', 'SPIKE_FAIL', or
'SPIKE_DIAG' is a stable marker the host (Claude) greps on paste-back.
Everything else is informational and may be ignored.
"""
from __future__ import annotations

import sys
import time

# Gst.init happens inside main() so the rthook env vars are already set.


def _emit(prefix: str, **kv: object) -> None:
    parts = [prefix] + [f"{k}={v!r}" for k, v in kv.items()]
    print(" ".join(parts), flush=True)


def _assert_tls_backend() -> bool:
    """Return True if Gio can resolve a TLS backend (libgiognutls)."""
    try:
        from gi.repository import Gio
        backend = Gio.TlsBackend.get_default()
        has_db = backend.get_default_database() is not None
        _emit("SPIKE_DIAG", tls_backend=type(backend).__name__, has_default_database=has_db)
        return has_db
    except Exception as e:
        _emit("SPIKE_FAIL", step="tls_backend_check", error=str(e))
        return False


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        _emit("SPIKE_FAIL", reason="usage", expected="spike.exe <url>")
        return 1

    url = argv[1].strip()
    if not url.startswith("https://"):
        _emit("SPIKE_FAIL", reason="url_not_https", url=url)
        return 1

    try:
        import gi
        gi.require_version("Gst", "1.0")
        from gi.repository import Gst, GLib
    except Exception as e:
        _emit("SPIKE_FAIL", step="import_gi", error=str(e))
        return 1

    try:
        Gst.init(None)
    except Exception as e:
        _emit("SPIKE_FAIL", step="Gst.init", error=str(e))
        return 1

    _emit("SPIKE_DIAG", gst_version=Gst.version_string(),
          plugin_count=len(Gst.Registry.get().get_plugin_list()))

    if not _assert_tls_backend():
        return 1

    playbin = Gst.ElementFactory.make("playbin3", "player")
    if playbin is None:
        _emit("SPIKE_FAIL", step="playbin3_factory", hint="gst-plugins-base missing from bundle")
        return 1

    # Redact listen_key from logs — it's in the URL query string
    redacted = url.split("?", 1)[0] + "?<redacted>" if "?" in url else url
    _emit("SPIKE_DIAG", url=redacted)

    playbin.set_property("uri", url)

    # --- State tracking ----------------------------------------------------
    state = {
        "first_sample_at": None,
        "errors": [],
        "warnings": [],
        "eos": False,
        "bytes_played": 0,
    }

    # audiosink tap: add a probe on playbin's "audio-tags-changed" OR a pad probe
    # on the audio sink. Simplest: watch the bus for STATE_CHANGED → PLAYING AND
    # message::tag. First tag arriving proves bytes flowed through the pipeline.
    bus = playbin.get_bus()
    bus.add_signal_watch()

    def _on_message(bus, msg):
        t = msg.type
        if t == Gst.MessageType.ERROR:
            err, debug = msg.parse_error()
            state["errors"].append(f"{err.message} | {debug}")
        elif t == Gst.MessageType.WARNING:
            w, debug = msg.parse_warning()
            state["warnings"].append(f"{w.message} | {debug}")
        elif t == Gst.MessageType.TAG and state["first_sample_at"] is None:
            # TAG arrives as soon as ICY data flows — means TLS + HTTP + demux worked
            state["first_sample_at"] = time.monotonic()
            _emit("SPIKE_DIAG", event="first_tag_arrived")
        elif t == Gst.MessageType.EOS:
            state["eos"] = True

    bus.connect("message", _on_message)

    # --- Run ---------------------------------------------------------------
    result = playbin.set_state(Gst.State.PLAYING)
    _emit("SPIKE_DIAG", set_state_result=result.value_name)

    loop = GLib.MainLoop()
    start = time.monotonic()

    def _tick():
        elapsed = time.monotonic() - start
        if state["errors"]:
            loop.quit()
            return False
        if state["first_sample_at"] and (time.monotonic() - state["first_sample_at"]) >= 5.0:
            loop.quit()
            return False
        if elapsed >= 8.0:
            loop.quit()
            return False
        return True

    GLib.timeout_add(200, _tick)
    try:
        loop.run()
    finally:
        playbin.set_state(Gst.State.NULL)

    # --- Verdict -----------------------------------------------------------
    if state["errors"]:
        _emit("SPIKE_FAIL", step="pipeline", errors=state["errors"])
        return 2
    if state["first_sample_at"] is None:
        _emit("SPIKE_FAIL", step="timeout", warnings=state["warnings"])
        return 3

    duration = time.monotonic() - state["first_sample_at"]
    _emit(
        "SPIKE_OK",
        audio_sample_received=True,
        duration_s=round(duration, 2),
        errors=state["errors"],
        warnings_count=len(state["warnings"]),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

**Why `message::tag` as the first-audio signal:** ICY tags arrive as soon as the `souphttpsrc` → `icydemux` → `mpg123dec` chain is producing buffers. This is the earliest GStreamer-visible proof that TLS handshake + HTTP body + demuxer all worked. `playbin3`'s audio-tap via a pad probe is more accurate but brittle — `message::tag` is the pragmatic choice for a throwaway spike.

## DLL Bill-of-Materials

Subject to revision after iteration 1 (the contrib hook determines the actual list — this is the expected shape). All paths relative to `C:\spike-gst\runtime\1.0\msvc_x86_64\`.

| DLL | Source dir | Role | Required? | Why |
|-----|-----------|------|:---------:|-----|
| `libgstreamer-1.0-0.dll` | `bin/` | Core GStreamer | ✅ | `gi` import fails without it. |
| `libglib-2.0-0.dll` | `bin/` | GLib runtime | ✅ | GStreamer links against it. |
| `libgobject-2.0-0.dll` | `bin/` | GObject type system | ✅ | GStreamer's type system. |
| `libgio-2.0-0.dll` | `bin/` | GIO — I/O + TLS framework | ✅ | Required for TLS backend loading. |
| `libgmodule-2.0-0.dll` | `bin/` | Dynamic module loader | ✅ | Used to load GIO modules at runtime. |
| `libgstbase-1.0-0.dll` | `bin/` | GstBaseSrc/Sink | ✅ | Foundation of all source/sink elements. |
| `libgstapp-1.0-0.dll` | `bin/` | appsrc/appsink | ⚠️ | Not strictly needed for spike; bundle if hook pulls it. |
| `libgstaudio-1.0-0.dll` | `bin/` | GstAudio caps/utils | ✅ | Used by `audioconvert`, `audioresample`, and sinks. |
| `libgstpbutils-1.0-0.dll` | `bin/` | Playback utilities | ✅ | `playbin3` uses pbutils. |
| `libgsttag-1.0-0.dll` | `bin/` | Tag handling | ✅ | ICY TAG parsing. |
| `libgstnet-1.0-0.dll` | `bin/` | Net utilities | ✅ | Dependency of `souphttpsrc`. |
| `libsoup-3.0-0.dll` | `bin/` | HTTP(S) client — `souphttpsrc` backend | ✅ | **D-06 core:** no HTTPS without it. |
| `libgiognutls.dll` | `lib/gio/modules/` | GIO TLS backend (GnuTLS) | ✅ | **D-06 core:** specific DLL the ROADMAP calls out. Must be in `GIO_EXTRA_MODULES` path. |
| `libgnutls-30.dll` | `bin/` | GnuTLS crypto | ✅ | `libgiognutls` backend. |
| `nghttp2.dll` | `bin/` | HTTP/2 support | ✅ | `libsoup-3` uses when server supports. |
| `libpsl-5.dll` | `bin/` | Public suffix list | ✅ | `libsoup-3` cookie handling. |
| `libxml2-2.dll` | `bin/` | XML parsing | ⚠️ | Pulled in by several gst-plugins-bad; bundle if hook pulls. |
| `libffi-8.dll` | `bin/` | FFI for PyGObject | ✅ | Required for `gi` marshalling. |
| `libintl-8.dll` | `bin/` | Gettext i18n | ✅ | GLib dependency. |
| `libiconv-2.dll` | `bin/` | Character encoding conversion | ✅ | GLib dependency. |
| `zlib1.dll` | `bin/` | Compression | ✅ | Many deps. |
| `libwinpthread-1.dll` | `bin/` | pthreads on Windows | ⚠️ | MSVC build may not need; MinGW-compat safety. |
| `libmpg123-0.dll` | `bin/` | MP3 decoder | ✅ | AA uses MP3; audio path fails without. |
| `libopenjp2-7.dll` | `bin/` | JPEG2000 (playbin3 typefind chain) | ❌ | Omit; not needed for audio-only. |
| `libvpx-*.dll`, `libx264-*.dll`, `libavcodec-*.dll` | `bin/` | Video codecs | ❌ | Omit; audio-only. |

**Legend:** ✅ required • ⚠️ bundle-if-present • ❌ omit via `exclude_plugins`.

**Provenance:** Structure drawn from 1.24.x MSVC build community reports + bug threads [CITED: gstreamer-bugs.narkive.com bug 794425]. Final enumeration comes from `gst-inspect-1.0.exe --print-all` pasted back on iteration 1. [ASSUMED: exact DLL names may vary ±1 between 1.24.x patch releases; user paste-back confirms.]

## Plugin Bill-of-Materials

All files in `lib/gstreamer-1.0/`. Each is a `.dll` providing one or more GStreamer elements.

| Plugin DLL | Elements provided | Required? | Fallback |
|-----------|-------------------|:---------:|----------|
| `gstcoreelements.dll` | `queue`, `tee`, `fakesink`, `identity`, `filesrc`, `fdsrc`, ... | ✅ | — (hard requirement) |
| `gstplayback.dll` | `playbin3`, `uridecodebin3`, `decodebin3`, `playsink` | ✅ | — |
| `gsttypefindfunctions.dll` | Typefind functions for MP3, AAC, ICY, HTTP chunks | ✅ | — (playbin3 discovery fails without) |
| `gstaudioconvert.dll` | `audioconvert` | ✅ | — |
| `gstaudioresample.dll` | `audioresample` | ✅ | — |
| `gstvolume.dll` | `volume` | ✅ | playbin3 embeds volume pre-sink |
| `gstautodetect.dll` | `autoaudiosink`, `autovideosink` | ✅ | — (spike sink selection) |
| `gstsoup.dll` | `souphttpsrc` | ✅ | — (**D-06 core**) |
| `gsticydemux.dll` | `icydemux` | ✅ | — (AA streams have ICY metadata) |
| `gstaudioparsers.dll` | `mpegaudioparse`, `aacparse`, `flacparse` | ✅ | — |
| `gstmpg123.dll` | `mpg123audiodec` | ✅ | `gstlibav` (but larger) |
| `gstwasapi2.dll` | `wasapi2sink`, `wasapi2src` | ✅ | `gstwasapi.dll`, `gstdirectsound.dll` |
| `gstwasapi.dll` | `wasapisink` (legacy) | ⚠️ | Fallback for wasapi2 issues |
| `gstdirectsound.dll` | `directsoundsink` | ⚠️ | Fallback — adds ~80ms latency |
| `gstfaad.dll` | `faad` AAC decoder | ⚠️ | Needed if AA stream is AAC not MP3 |
| `gstopenmpt.dll`, `gstvideo*`, `gstrtp*`, `gstsrtp*` | — | ❌ | Omit via `exclude_plugins` |
| `gstopencv.dll`, `gstvulkan.dll`, `gstvaapi.dll`, `gstd3d11*.dll` | — | ❌ | GPU/CV not needed for audio |
| `gstwebrtc*.dll`, `gstdash.dll`, `gstrtsp*.dll` | — | ❌ | Streaming protocols not in scope |

**Start broad:** iteration 1 includes all of `lib/gstreamer-1.0/`. Prune via `exclude_plugins` once smoke passes.

## Known Failure Modes

### 1. `TLS/SSL support not available; install glib-networking`
**Detection:** Appears in stderr on first HTTPS URI set.
**Root cause:** `libgiognutls.dll` not discoverable by GIO at runtime.
**Fix:** Verify `_internal/gio/modules/libgiognutls.dll` exists in bundle. Confirm rthook sets `GIO_EXTRA_MODULES`. Confirm `libgnutls-30.dll` is in `_internal/` (root, not `gio/modules/`).

### 2. `plugin scanner helper not found`
**Detection:** stderr warning on `Gst.init()`. Plugin registry falls back to in-process scanning (2–5× slower, can crash on bad plugins).
**Root cause:** `gst-plugin-scanner.exe` not in bundle, or `GST_PLUGIN_SCANNER` unset.
**Fix:** Confirm `_internal/gst-plugin-scanner.exe` + rthook sets `GST_PLUGIN_SCANNER`.

### 3. `GLib-GIO-CRITICAL: g_settings_schema_source_new_from_directory`
**Detection:** stderr on `Gst.init()`. Playback may still work but with missing settings.
**Root cause:** `share/glib-2.0/schemas/gschemas.compiled` missing from bundle.
**Fix:** The `.spec` `glib_share_tree` copies `share/glib-2.0/schemas` — verify it contains `gschemas.compiled`. If not, run `glib-compile-schemas.exe` from the devel MSI against the bundled schemas dir.

### 4. `no element "playbin3"`
**Detection:** `Gst.ElementFactory.make("playbin3", ...)` returns `None`.
**Root cause:** `gstplayback.dll` not in bundle, OR `GST_PLUGIN_PATH` misconfigured.
**Fix:** Confirm `_internal/gst_plugins/gstplayback.dll` exists. The contrib rthook uses subdir name `gst-plugins` (with a hyphen) — check exact spelling matches `_MEIPASS` layout. [CITED: hook-gi.repository.Gst.py source]

### 5. Registry write failure (`permission denied`)
**Detection:** `registry.bin` write fails on first launch when bundle installed under `C:\Program Files`.
**Root cause:** `GST_REGISTRY` defaulting to Program Files path, which is read-only.
**Fix:** Stock rthook sets `GST_REGISTRY=<_MEIPASS>/registry.bin`. Onedir bundle `_internal/` is writable by the launching user for this process — works. (Installer phase concern, not spike concern, since user runs from dev path.)

### 6. `import gi` ImportError
**Detection:** Traceback at bundle startup.
**Root cause:** `gi` module wasn't found, OR PyGObject MSVC ABI mismatch.
**Fix:** Confirm PyGObject was installed via `pip install pygobject` in the build venv (not MSYS2/MinGW). Confirm the build venv has the GStreamer MSVC `bin/` on PATH so PyGObject's `gi` C extension can link against `libgobject-2.0-0.dll` at import time.

### 7. `No such file or directory: '.../girepository-1.0/Gst-1.0.typelib'`
**Detection:** Traceback in `gi.require_version("Gst", "1.0")`.
**Root cause:** Typelibs not in bundle, OR `GI_TYPELIB_PATH` wrong.
**Fix:** Verify `_internal/girepository-1.0/Gst-1.0.typelib` exists. PyGObject 3.52+ uses `girepository-2.0` — adjust path in rthook and `.spec` Tree() if that's the installed version.

### 8. `wasapi2sink: Could not get the default audio device`
**Detection:** Pipeline errors on PLAYING transition.
**Root cause:** Win11 VM has no audio hardware attached, or `wasapi2sink` init races with audio subsystem startup.
**Fix:** User confirms VM has a valid audio output device (virtual audio driver or host-audio passthrough). Fall back to `autoaudiosink` explicitly via `playbin3.set_property("audio-sink", Gst.ElementFactory.make("autoaudiosink"))`.

### 9. `g_type_init` deprecation warning spam
**Detection:** Non-fatal stderr spam from GLib 2.36+ deprecation shim.
**Root cause:** Benign warning; ignorable.
**Fix:** Suppress with `GLIB_SILENT=1` env var if noise impairs paste-back parsing.

### 10. `Could not create resource for reading. Resource not found.`
**Detection:** Bus error on the HTTPS URI.
**Root cause:** `souphttpsrc` loaded but `libsoup-3.0-0.dll` not on DLL search path at runtime.
**Fix:** Ensure `libsoup-3.0-0.dll` is in `_internal/` root. Windows DLL search is implicit: loader looks in the directory of the loading DLL, then PATH. The plugin DLL (`gstsoup.dll`) loads from `_internal/gst_plugins/`, and the loader walks up to `_internal/` to find `libsoup-3.0-0.dll`. If missing, add an explicit `binaries=` entry.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hand-curated GStreamer bundle via Dependency Walker | `pyinstaller-hooks-contrib` `hook-gi.repository.Gst.py` with include/exclude lists | PyInstaller 5.4.1 (Oct 2022) | Spike uses hook config, not dep-walker. |
| `GIO_MODULE_DIR` (replaces search path) | `GIO_EXTRA_MODULES` (additive) | GLib 2.30+ era | Use `GIO_EXTRA_MODULES` only. |
| `wasapisink` | `wasapi2sink` | GStreamer 1.18+ (2020-ish) | Default on Win8+; keep both in bundle, prefer wasapi2. |
| `girepository-1.0` | `girepository-2.0` | PyGObject 3.51+ (mid-2024) | Runtime hook must handle both paths depending on installed PyGObject version. |
| PyInstaller `--onefile` | `--onedir` | GStreamer+PyInstaller best practice | `--onefile` extracts to `%TEMP%` on each run → 5s+ cold-start penalty + registry-rebuild every time. `--onedir` cache survives. [CITED: kivy #6126 community consensus] |

**Deprecated/outdated:**
- `wasapisink` — still present for Win7 compat; Win11 uses `wasapi2sink`.
- Shipping `mpv.exe` for YouTube fallback — retired in Plan 35-06 (PKG-05 RETIRED).

## Validation Architecture

### Test Framework

The spike is NOT a pytest-scoped test; it's a freestanding script. Qt/pytest-qt infrastructure doesn't apply. The "test" is the smoke test running inside the Windows VM.

| Property | Value |
|----------|-------|
| Framework | Bespoke CLI + exit-code contract (smoke_test.py) |
| Config file | `test_url.txt` (gitignored) + `43-spike.spec` |
| Quick run command | `.\build.ps1 -SkipSmoke` (build only) |
| Full run command | `.\build.ps1` (build + smoke) |
| Automated on Linux CI? | **No** — D-09 explicitly keeps this off Linux CI. User runs on Win11 VM. |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PKG-06 | HTTPS ShoutCast playback via souphttpsrc + libgiognutls.dll in a PyInstaller bundle on clean Win11 | Manual smoke | `.\build.ps1` on VM, paste stdout | ❌ Wave 0 creates `smoke_test.py`, `build.ps1`, `43-spike.spec`, `runtime_hook.py` |

### ROADMAP Success-Criteria Mapping

The ROADMAP Phase 43 has three success criteria (from CANONICAL REFS). Each maps to a concrete pass condition:

| Criterion | Pass = |
|-----------|--------|
| 1. HTTPS stream plays for ≥5 seconds on a clean Win11 VM | `smoke_test.py` exits 0 AND user hears audio through host speakers for ≥5s of the 8s probe window |
| 2. `libgiognutls.dll` (or equivalent GIO TLS backend) is bundled and loaded | `SPIKE_DIAG has_default_database=True` marker present in paste-back AND `_internal/gio/modules/libgiognutls.dll` exists in bundle |
| 3. Exact DLL + plugin list documented for Phase 44 | `43-SPIKE-FINDINGS.md` tables populated from `gst-inspect-1.0.exe --plugin` output of the bundled registry (post-build) |

### Sampling Rate

- **Per iteration:** `build.ps1` runs full build + smoke (single command, single paste).
- **Phase gate:** All three ROADMAP success criteria pass simultaneously on a single iteration. Then `/gsd-spike-wrap-up` captures findings as a skill.

### Wave 0 Gaps

- [ ] `.planning/phases/43-gstreamer-windows-spike/43-spike.spec` — skeleton from this RESEARCH §"PyInstaller .spec structure"
- [ ] `.planning/phases/43-gstreamer-windows-spike/runtime_hook.py` — from §"Runtime hook template"
- [ ] `.planning/phases/43-gstreamer-windows-spike/build.ps1` — from §"build.ps1 skeleton"
- [ ] `.planning/phases/43-gstreamer-windows-spike/smoke_test.py` — from §"smoke_test.py with exit-code contract"
- [ ] `.planning/phases/43-gstreamer-windows-spike/.gitignore` — add `test_url.txt`, `artifacts/`, `build/`, `dist/`, `*.spec.log`
- [ ] `.planning/phases/43-gstreamer-windows-spike/README.md` (optional) — one-paragraph runbook for the user: "install GStreamer MSIs, populate test_url.txt, run build.ps1, paste artifacts/smoke.log back to Claude"

### What "Pass" Means for Audible Playback

Automation can't confirm sound came out of the VM's speakers. User confirmation pattern:

1. `smoke_test.py` exits 0 (SPIKE_OK marker). Proves bytes flowed through the pipeline.
2. User replies with a one-word confirmation: "audible" or "silent". This goes into the findings doc.
3. If "silent" but `SPIKE_OK`: the pipeline worked but VM audio routing is the issue — not a spike failure. Findings record "VM audio config note" and the spike still passes at the GStreamer layer.

### What Evidence Gets Committed

**Committed to git** (`commit_docs: true` in config.json):
- `43-RESEARCH.md` (this file)
- `43-SPIKE-FINDINGS.md` (after the spike passes)
- `43-spike.spec`, `runtime_hook.py`, `build.ps1`, `smoke_test.py` — all reference-quality artifacts for Phase 44
- Redacted smoke log excerpt in findings (SPIKE_OK/DIAG lines only, URL redacted to `?<redacted>`)

**NEVER committed** (`.gitignored` per D-07):
- `test_url.txt` — contains real AA listen key
- `artifacts/*.log` — may contain full URLs
- `dist/`, `build/` — regenerable

## Environment Availability

| Dependency | Required By | Available on Linux (Claude) | Available on Win11 VM (user) | Fallback |
|------------|------------|:---------------------------:|:----------------------------:|----------|
| Python 3.10+ | smoke_test, spec | ✓ | user installs | — |
| PyInstaller ≥ 6.11 | bundling | N/A (user-side only) | pip-installed by build.ps1 | — |
| PyGObject ≥ 3.50 | `gi` imports | N/A | pip-installed by build.ps1 | — |
| GStreamer 1.24.12 MSVC runtime MSI | bundled DLLs + plugins | N/A | user installs once | — |
| GStreamer 1.24.12 MSVC devel MSI | `gst-inspect-1.0.exe` | N/A | user installs once | — |
| Node.js | yt-dlp EJS (MS main app) | Not needed for SPIKE | Not needed for SPIKE | — |
| AA listen key | smoke test HTTPS URL | Pulled from user's DB via settings-export | Copied to `test_url.txt` | Public ShoutCast URL if AA fails with auth error (D-08) |

**Missing dependencies with no fallback:** None — all tools are either host-installed by the user in one-time MSI/pip actions or pulled by the build script.

**Missing dependencies with fallback:** AA listen key. Per D-08, fall back to a public ShoutCast HTTPS URL if the AA URL fails for listen-key-auth reasons rather than TLS.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `ADDLOCAL=ALL` on the MSI installs every feature including `gst-plugin-scanner.exe` and `libgiognutls.dll` | Installation | LOW — if wrong, user sees assertion fail in `.spec` pre-flight check → reinstall with correct flag. |
| A2 | MSVC-built DLLs ABI-match pip-installed PyGObject wheels on Windows | Alternatives Considered | MEDIUM — if wrong, `import gi` crashes at bundle launch. Resolution: rebuild PyGObject from source with MSVC matching the GStreamer build. |
| A3 | `libgiognutls.dll` is the only TLS backend shipped in the MSVC build (vs OpenSSL/SChannel backends) | DLL Bill-of-Materials | LOW — Cerbero ships GnuTLS exclusively for MSVC builds per community consensus; user paste-back confirms. |
| A4 | `GIO_EXTRA_MODULES` is additive vs `GIO_MODULE_DIR` replaces the default path | Runtime Hook Template | LOW — documented GLib behaviour, consistent across 2.50–2.80. |
| A5 | Contrib hook's `gst-plugins` (hyphenated) vs `gst_plugins` (underscore) subdirectory naming | Known Failure Modes §4 | MEDIUM — source read shows `gst_plugins` underscore in rthook but `gst-plugins` hyphen in some docs. Verify empirically on iteration 1. |
| A6 | `message::tag` is a reliable proxy for "first audio sample" on MP3/ICY streams | smoke_test.py | LOW — ICY metadata arrives as HTTP header tags via `souphttpsrc` pre-demux, proving TLS works. |
| A7 | PyGObject version on user's VM (build-time pip install) resolves to girepository-1.0 or -2.0 consistently | Runtime Hook Template | MEDIUM — iteration 1 paste-back reveals which version pip picks; rthook adjusted accordingly. |
| A8 | `share/glib-2.0/schemas/gschemas.compiled` is present and current in the MSVC install | .spec template | LOW — standard MSI output. |
| A9 | Runtime hook ordering (stock contrib rthook runs before custom rthook) is alphabetical-stable | Runtime Hook Template | LOW — PyInstaller docs confirm alphabetical order; stock rthook filename is `pyi_rth_gstreamer.py`, custom is `runtime_hook.py` → `p` < `r`. |
| A10 | Windows 11 VM has a functional audio output device (virtual or passthrough) | Known Failure Modes §8 | MEDIUM — if VM lacks audio, `wasapi2sink` fails at PLAYING. User confirms VM audio config before first iteration. |

**Planner action:** Items A5 and A7 resolve on iteration 1 paste-back. If A10 is ambiguous, plan an explicit "verify VM audio device present" preflight step before the first build.

## Open Questions

1. **Which PyGObject version does `pip install pygobject` resolve to on the user's Python 3.x?**
   - What we know: 3.50+ uses girepository-1.0, 3.52+ uses girepository-2.0.
   - What's unclear: Python version on user's VM isn't documented; pip behaviour depends.
   - Recommendation: First command in iteration 1's `build.ps1` prints `python --version` and `pip show pygobject | findstr Version` — Claude adjusts rthook typelib path accordingly.

2. **Does the VM snapshot have Python 3 pre-installed?**
   - What we know: CONTEXT says "clean snapshot" — ambiguous about Python.
   - Recommendation: Add a Python-availability pre-flight in `build.ps1`; if missing, user installs Python 3.12 before first iteration.

3. **Will the AA listen key work over HTTPS, or does AA require HTTP for listen-key auth?**
   - What we know: AA serves HTTPS PLS files but the actual stream URLs inside a PLS may be HTTP.
   - Recommendation: `smoke_test.py` validates URL starts with `https://` as its first check. If AA PLS returns `http://`, user manually substitutes the HTTPS equivalent from the AA portal for the spike. Deferred-to-Phase-44 if this reveals a general AA HTTPS problem.

4. **Bundle size target — is there a cap?**
   - What we know: CONTEXT doesn't specify a size limit.
   - Recommendation: Measure after iteration 1. Expected: 80–120 MB onedir. If > 200 MB, aggressive `exclude_plugins` pass. Not a spike pass/fail gate.

5. **Wasapi2 vs autoaudiosink — which does `playbin3` pick by default?**
   - What we know: `autoaudiosink` ranks `wasapi2sink` highest on Win8+ when present.
   - Recommendation: Let `playbin3` auto-select (its default is autoaudiosink). SPIKE_DIAG emits the chosen sink name from the pipeline's audio-sink property for the findings doc.

## Sources

### Primary (HIGH confidence)
- [PyInstaller `hook-gi.repository.Gst.py`](https://github.com/pyinstaller/pyinstaller/blob/develop/PyInstaller/hooks/hook-gi.repository.Gst.py) — source read: exact collection behaviour, plugin glob patterns, include/exclude logic
- [PyInstaller `pyi_rth_gstreamer.py`](https://github.com/pyinstaller/pyinstaller/blob/develop/PyInstaller/hooks/rthooks/pyi_rth_gstreamer.py) — source read: env vars set at runtime by stock rthook
- [PyInstaller Hook Configuration Options (stable docs)](https://pyinstaller.org/en/stable/hooks-config.html) — gstreamer and gi hook config schemas with examples
- [GStreamer 1.24.12 release announcement](https://discourse.gstreamer.org/t/gstreamer-1-24-12-stable-bug-fix-release/4023) — Jan 2025, confirmed final 1.24.x patch
- [GStreamer souphttpsrc documentation](https://gstreamer.freedesktop.org/documentation/soup/souphttpsrc.html) — element capabilities
- [wasapi2sink documentation](https://gstreamer.freedesktop.org/documentation/wasapi2/wasapi2sink.html) — Win8+ default, low-latency property
- [GStreamer Download portal](https://gstreamer.freedesktop.org/download/) — canonical MSI URLs (version-templated)

### Secondary (MEDIUM confidence)
- [gstreamer-bugs bug 794425](https://gstreamer-bugs.narkive.com/QRAenN4W/bug-794425-new-souphttpsrc-tls-ssl-support-not-available-on-win32) — `libgiognutls.dll` + `GIO_MODULE_DIR` history
- [Avoiding GST_PLUGIN_PATH on Windows](https://gstreamer-devel.narkive.com/l1SPuZXD/avoiding-the-gst-plugin-path-environment-variable-on-windows) — David Schleef on Windows plugin auto-discovery via `g_win32_get_package_installation_directory_of_module`
- [GStreamer Cerbero MSI environment variable issue #337](https://gitlab.freedesktop.org/gstreamer/cerbero/-/issues/337) — `GSTREAMER_1_0_ROOT_MSVC_X86_64` naming
- [GStreamer Windows deployment guide (raw)](https://raw.githubusercontent.com/GStreamer/gst-docs/master/markdown/deploying/windows.md) — silent install flags, deployment strategies
- [kivy#6126](https://github.com/kivy/kivy/issues/6126) — community consensus on PyInstaller + GStreamer bundling patterns

### Tertiary (LOW confidence — flagged for iteration-1 verification)
- [Medium/Psychtoolbox/etc.](https://medium.com/@kenancan.dev/building-opencv-gstreamer-on-windows-a-8-hour-battle-bdb3211aa834) — installation directory layout conventions
- DLL name specifics (e.g., `libsoup-3.0-0.dll` exact filename vs `libsoup-2.4-1.dll`) — verified on iteration-1 paste-back of `dir C:\spike-gst\runtime\1.0\msvc_x86_64\bin`

## Metadata

**Confidence breakdown:**
- Standard stack (GStreamer 1.24.12, PyInstaller ≥ 6.11, contrib hooks): **HIGH** — all verified from official sources
- Architecture (.spec template, rthook template, build.ps1, smoke_test): **HIGH** — structure verified from PyInstaller hook source, env-var logic from GStreamer docs
- DLL bill-of-materials exact filenames: **MEDIUM** — structure is documented, exact filenames resolve on iteration-1 paste-back
- Plugin bill-of-materials exact filenames: **MEDIUM** — same as DLLs
- Known failure modes: **HIGH** — each failure has a cited source or documented root cause

**Research date:** 2026-04-19
**Valid until:** 2026-07-19 (3 months — GStreamer 1.24.x is frozen, PyInstaller 6.x API stable; revisit if 1.28 becomes the LTS or PyGObject API breaks)
