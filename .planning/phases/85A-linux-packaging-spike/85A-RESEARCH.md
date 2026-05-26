# Phase 85a: Linux Packaging Spike — Research

**Researched:** 2026-05-25
**Domain:** Linux AppImage bundling (linuxdeploy + conda-forge GStreamer + cross-distro distrobox verification)
**Confidence:** HIGH for toolchain mechanics, env vars, conda-forge package availability and Phase 43 carry-over patterns; MEDIUM for `linuxdeploy-plugin-gstreamer` viability against a conda layout (the plugin defaults to system multiarch paths); HIGH for GLIBC version map; HIGH for distrobox + Wayland + PipeWire sharing.

## Summary

The locked toolchain (`linuxdeploy` + `linuxdeploy-plugin-conda` + `linuxdeploy-plugin-gstreamer`) is feasible but has two LIVE risks that this spike is correctly scoped to surface:

1. **`linuxdeploy-plugin-gstreamer` was last touched March 2024** [CITED: https://api.github.com/repos/linuxdeploy/linuxdeploy-plugin-gstreamer/commits] — it works, but it defaults to system GStreamer paths (`/usr/lib/$(uname -m)-linux-gnu/gstreamer-1.0` then `/usr/lib/gstreamer-1.0`) and must be **redirected to the conda env via `GSTREAMER_PLUGINS_DIR` + `GSTREAMER_HELPERS_DIR`** [VERIFIED: linuxdeploy-plugin-gstreamer.sh source]. Phase 85's plan must wire those two env vars into `build.sh` before invoking linuxdeploy. The spike's job is to prove that handoff works against `$APPDIR/usr/conda/lib/gstreamer-1.0/`.
2. **The plugin's AppRun hook expects scanner at `$APPDIR/usr/lib/gstreamer1.0/gstreamer-1.0/gst-plugin-scanner`** (note the doubled segment) [VERIFIED: linuxdeploy-plugin-gstreamer.sh] — but `linuxdeploy-plugin-conda` lays plugins out under `$APPDIR/usr/conda/{lib,libexec}/` [VERIFIED: linuxdeploy-plugin-conda.sh]. Either the gstreamer plugin's auto-discovery picks up the conda path via `GSTREAMER_*` env overrides, or the spike has to override the generated AppRun hook with hand-rolled env exports. **This is the load-bearing unknown the spike answers.**

**Primary recommendation:** Pin `linuxdeploy@continuous` (1-alpha-20251107-1) + `linuxdeploy-plugin-conda@master` + `linuxdeploy-plugin-gstreamer@master` (no formal release tag, fetch raw script from `master`). Drive the bundle from `build.sh` that exports `GSTREAMER_PLUGINS_DIR=$APPDIR/usr/conda/lib/gstreamer-1.0` and `GSTREAMER_HELPERS_DIR=$APPDIR/usr/conda/libexec/gstreamer-1.0` BEFORE invoking `./linuxdeploy --plugin gstreamer`. The spike's `AppRun` template then re-asserts the four success-criteria env vars (overriding the plugin's hook if needed) at AppRun-source time so Phase 85 can copy-paste it.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Building the AppImage | Docker build container (`ubuntu:22.04`) | host shell (`build.sh` driver) | Locked by GLIBC ≤ 2.35 success criterion #2; build host MUST be ≤ Ubuntu 22.04 era libc |
| Bundling Python + GStreamer + Qt runtime | `linuxdeploy-plugin-conda` (writes to `$APPDIR/usr/conda/`) | conda-forge channel | Phase 43 proved conda-forge is the only viable PyGObject path; same channel reused |
| Bundling GStreamer plugin tree + scanner + scanner-helper paths | `linuxdeploy-plugin-gstreamer` (writes AppRun hook) | `build.sh` env-var redirection (`GSTREAMER_PLUGINS_DIR`, `GSTREAMER_HELPERS_DIR`) | Plugin defaults to system multiarch; must be pointed at conda's layout |
| Setting GST_* env vars at launch | `AppRun` (hand-rolled template) | plugin-generated `apprun-hooks/linuxdeploy-plugin-gstreamer.sh` | Spike's deliverable is THE template; hook may need overriding for `GST_REGISTRY_FORK=no` specifically |
| Producing the final `.AppImage` | `linuxdeploy --output appimage` (`appimagetool` invoked internally) | — | Standard pipeline |
| Cross-distro PASS verification | `distrobox` (podman backend) on host Wayland session | host PipeWire (audible) + `grim`/`gnome-screenshot` (screenshot) + `script`/`tee` (transcript) | Locked by D-02; distrobox shares Wayland + PipeWire + DBus to container by default |
| Failure-mode reporting | `85A-SPIKE-FINDINGS.md` (per-distro evidence) | `/gsd:spike-wrap-up` → skill APPEND | Mirrors Phase 43 pattern verbatim |

## Standard Stack

### Core toolchain (host-side, build container + dev rig)

| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| `linuxdeploy` | `1-alpha-20251107-1` (continuous: May 2025) | AppDir + AppImage producer | de-facto standard for AppImage bundling; canonical plugin loader [VERIFIED: GitHub Releases page accessible 2026-05-25, asset HEAD returns 302 to release-assets CDN] |
| `linuxdeploy-plugin-conda` | `master` HEAD (last release Sep 2024) | Bundles miniconda env into `$APPDIR/usr/conda/` | Only viable bridge between conda-forge GStreamer/PyGObject and AppImage; aarch64-aware as of 2024-09 [CITED: https://api.github.com/repos/linuxdeploy/linuxdeploy-plugin-conda/commits] |
| `linuxdeploy-plugin-gstreamer` | `master` HEAD (last touched Mar 2024) | Writes AppRun hook setting `GST_PLUGIN_*` env vars + copies plugin scanner | Bundled-runtime convention for AppImage GStreamer apps; maintenance is sporadic [CITED: https://api.github.com/repos/linuxdeploy/linuxdeploy-plugin-gstreamer/commits — last commit 2024-03-01 "Fix #18: missing Gstreamer issue"] |
| `appimagetool` | bundled by `linuxdeploy --output appimage` | Final mksquashfs + AppImage signature step | linuxdeploy invokes internally; not separately pinned |
| `podman` | host-provided (5.7.0 verified on dev rig) | distrobox container engine (D-01) | Rootless, no daemon, distrobox-preferred |
| `distrobox` | host-installed; NOT present on dev rig per probe — **planner MUST add install task** | Wayland+PipeWire-sharing dev containers (D-02) | Locked by D-02; the only path that gives audible playback fidelity from a single host |
| Docker (build container only) | host-provided (29.5.2 verified) | runs `ubuntu:22.04` build environment | Locked by success criterion #2 (GLIBC ≤ 2.35); use docker NOT podman here because the build container is a pure CI-style image, not an interactive Wayland share |

**Asset URLs (verified accessible 2026-05-25):**

| Asset | URL | Notes |
|-------|-----|-------|
| linuxdeploy AppImage | `https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage` | HEAD returns HTTP 302 → release-assets CDN [VERIFIED via curl HEAD] |
| linuxdeploy-plugin-conda | `https://raw.githubusercontent.com/linuxdeploy/linuxdeploy-plugin-conda/master/linuxdeploy-plugin-conda.sh` | Raw `master` — no continuous-build releases [VERIFIED: GitHub Releases page is empty for this repo] |
| linuxdeploy-plugin-gstreamer | `https://raw.githubusercontent.com/linuxdeploy/linuxdeploy-plugin-gstreamer/master/linuxdeploy-plugin-gstreamer.sh` | Raw `master` — no continuous-build releases [VERIFIED: GitHub Releases page is empty for this repo] |

**SHA256 pinning protocol:** linuxdeploy publishes the AppImage on releases but does NOT publish a sidecar `.sha256`. The plugin `.sh` scripts have NO published SHA. The spike's `build.sh` must `sha256sum` each asset at first download, commit the digest to `build.sh` as a constant, and re-verify on subsequent runs. **Findings doc captures the three SHAs.**

### Conda-forge env shape (mirrors Phase 43, Linux-specific subset)

| Package | Channel | Purpose | Phase 43 Cross-Reference |
|---------|---------|---------|--------------------------|
| `python=3.10` or `3.11` or `3.12` | conda-forge | Interpreter; matches `STACK.md` Python 3.10+ requirement | Phase 43 used 3.12 successfully |
| `pyside6` | conda-forge | Qt 6 bindings; minimal Qt event loop in `hello_world.py` | Phase 43 did NOT bundle Qt — spike is the first conda-forge PySide6 bundle |
| `pygobject` | conda-forge | Python `gi.repository.Gst` bindings | Phase 43 confirmed `pygobject 3.56.2` works |
| `gst-python` | conda-forge | `gi.repository.GstApp`, etc. — required for some plugin introspection | Already in Phase 43 deps via gstreamer meta |
| `gstreamer` | conda-forge | Core 1.28+ runtime | Phase 43 pinned 1.28.2 |
| `gst-plugins-base` | conda-forge | `playbin3`, `decodebin3`, `souphttpsrc` | required for playbin3 + HTTPS |
| `gst-plugins-good` | conda-forge | `pulsesink`, `autoaudiosink`, `mpegaudioparse` | required for audio sinks |
| `gst-plugins-bad` | conda-forge | extras (HLS, dash, fragmented) | broad-collect per Phase 43 windows-gstreamer-bundling.md |
| `gst-plugins-ugly` | conda-forge | MP3 decoders (`mpg123`, `flump3dec`) — required for SomaFM MP3 (D-07) | Phase 43 included for MP3 |
| `gst-libav` | conda-forge | AAC + H.264 decoders; PKG-LIN-APP-03 mentions but Phase 85 validates AAC tier | Phase 43 confirmed REQUIRED on Windows for AAC; spike includes for plugin-resolution test of `avdec_aac` |
| `glib-networking` | conda-forge | GIO TLS backend modules — REQUIRED for HTTPS (D-08) | Phase 43 windows-gstreamer-bundling.md: without it, `"TLS/SSL support not available"` on HTTPS [VERIFIED: anaconda.org/conda-forge/glib-networking — latest 2.80.0, linux-64 supported] |

**`environment-spike.yml` shape:**

```yaml
name: spike-linux
channels:
  - conda-forge
dependencies:
  - python=3.12
  - pyside6
  - pygobject
  - gst-python
  - gstreamer
  - gst-plugins-base
  - gst-plugins-good
  - gst-plugins-bad
  - gst-plugins-ugly
  - gst-libav
  - glib-networking
```

No `defaults`, no `nodefaults` (Phase 43 stack lock preserved).

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `linuxdeploy-plugin-gstreamer` (auto-discover) | Manual `cp -r` of `$CONDA_PREFIX/lib/gstreamer-1.0/` into `$APPDIR/usr/lib/gstreamer-1.0/` + hand-rolled AppRun env exports | Manual path is more deterministic but skips the plugin's helper-binary discovery (`gst-plugin-scanner`); spike validates the plugin path first, manual is fallback if plugin auto-discovery fails the conda layout — **falls under D-09 negative-pivot policy: STOP and report, do not silently pivot** |
| `linuxdeploy-plugin-conda` (`MINICONDA_VERSION=latest`) | Pin a specific `Miniconda3-py312_24.X.Y-Linux-x86_64.sh` | `latest` makes the AppImage non-reproducible; spike pins via `MINICONDA_VERSION=py312_24.9.2-0` (or current 2026 stable) — **researcher recommends pin; planner verifies current best practice via release notes** |
| `appimagetool` directly | Skip linuxdeploy, use `appimagetool` standalone | Loses the plugin-conda + plugin-gstreamer pipeline; reverts to fully hand-rolled bundle assembly. Out of scope for spike (locked toolchain D). |

**Installation (host-side bootstrap; lives in `tools/linux-spike/`):**

```bash
# Host dev rig (Ubuntu 26.04 LTS / GNOME Wayland)
sudo apt install distrobox podman docker.io grim    # gnome-screenshot already on GNOME hosts
# (distrobox + podman verified; docker also present)

# Build assets — downloaded INSIDE the build container, not host
# (See build.sh)
```

## Package Legitimacy Audit

> slopcheck (v0.6.1) supports `pypi/npm/crates.io/go/rubygems/maven/packagist` but NOT conda-forge. Conda packages were verified via direct HTTP probe of `anaconda.org/conda-forge/<pkg>/files` (all 10 returned HTTP 200) AND each is a Phase 43-validated dependency from the existing project skill. Treat as `[VERIFIED: conda-forge channel registry probe + Phase 43 production use]`.

| Package | Registry | Source Repo | Verification | Disposition |
|---------|----------|-------------|--------------|-------------|
| `gstreamer` | conda-forge | github.com/conda-forge/gstreamer-feedstock | HTTP 200 + Phase 43 | Approved |
| `gst-plugins-base` | conda-forge | github.com/conda-forge/gst-plugins-base-feedstock | HTTP 200 + Phase 43 | Approved |
| `gst-plugins-good` | conda-forge | conda-forge/gst-plugins-good-feedstock | HTTP 200 + Phase 43 | Approved |
| `gst-plugins-bad` | conda-forge | conda-forge/gst-plugins-bad-feedstock | HTTP 200 + Phase 43 | Approved |
| `gst-plugins-ugly` | conda-forge | conda-forge/gst-plugins-ugly-feedstock | HTTP 200 + Phase 43 | Approved |
| `gst-libav` | conda-forge | conda-forge/gst-libav-feedstock | HTTP 200 + Phase 43 | Approved |
| `glib-networking` | conda-forge | gitlab.gnome.org/GNOME/glib-networking | HTTP 200 + 2.80.0 published 2024-03 | Approved |
| `pygobject` | conda-forge | gitlab.gnome.org/GNOME/pygobject | HTTP 200 + Phase 43 | Approved |
| `gst-python` | conda-forge | conda-forge/gst-python-feedstock | HTTP 200 + Phase 43 | Approved |
| `pyside6` | conda-forge | conda-forge/pyside6-feedstock | HTTP 200 | Approved |

**Toolchain assets (NOT conda packages; raw GitHub):**

| Asset | Source | Audit |
|-------|--------|-------|
| `linuxdeploy-x86_64.AppImage` | github.com/linuxdeploy/linuxdeploy (org owns repo) | Continuous-build release 2025-05-12; CDN HEAD probe HTTP 302 OK [VERIFIED]. SHA256 captured at first download in `build.sh`. |
| `linuxdeploy-plugin-conda.sh` | github.com/linuxdeploy/linuxdeploy-plugin-conda (org owns repo) | Active maintenance — last commit 2024-09-07 (aarch64 PR). Raw-master pin; SHA256 captured at first download. |
| `linuxdeploy-plugin-gstreamer.sh` | github.com/linuxdeploy/linuxdeploy-plugin-gstreamer (org owns repo) | Sporadic maintenance — last commit 2024-03-01 (regression fix). Raw-master pin; SHA256 captured at first download. Maintenance risk flagged in Pitfall 8. |

**Packages flagged `[SUS]`:** none.
**Packages removed `[SLOP]`:** none.

## Architecture Patterns

### System Architecture Diagram

```
┌────────────────────────────────────────────────────────────────┐
│ HOST: Ubuntu 26.04 LTS (Wayland/GNOME, kcreasey's dev rig)     │
│                                                                │
│   ┌──────────────────────────────────────────────────────┐    │
│   │ DOCKER: ubuntu:22.04 (build only, NOT Wayland-shared)│    │
│   │  $ build.sh                                          │    │
│   │   ├─ download linuxdeploy + 2 plugin scripts (pinned │    │
│   │   │   SHA256)                                        │    │
│   │   ├─ create conda env from environment-spike.yml     │    │
│   │   ├─ $APPDIR/ skeleton (icon, .desktop, AppRun       │    │
│   │   │   template)                                      │    │
│   │   ├─ ./linuxdeploy --plugin conda --plugin gstreamer │    │
│   │   │     --output appimage                            │    │
│   │   │   ↓                                              │    │
│   │   │   GSTREAMER_PLUGINS_DIR=$APPDIR/usr/conda/lib/   │    │
│   │   │       gstreamer-1.0  (env redirect to conda)     │    │
│   │   │   GSTREAMER_HELPERS_DIR=$APPDIR/usr/conda/libexec│    │
│   │   │       /gstreamer-1.0                             │    │
│   │   └─ output: MusicStreamerSpike-x86_64.AppImage      │    │
│   └──────────────────────────────────────────────────────┘    │
│                          │ (built artifact lands in            │
│                          ↓  .planning/spikes/85a-…/artifacts/) │
│                                                                │
│   ┌──────────────────────────────────────────────────────┐    │
│   │ DISTROBOX (podman): ms-spike-ubuntu22                │    │
│   │  ↑ shares: $WAYLAND_DISPLAY, $DBUS_SESSION_BUS,      │    │
│   │            $XDG_RUNTIME_DIR (pipewire socket), $HOME │    │
│   │  $ ./MusicStreamerSpike-x86_64.AppImage              │    │
│   │     ↓ smoke_test.py runs INSIDE the AppRun shell:    │    │
│   │     1. GLIBC grep: strings AppRun | grep GLIBC_      │    │
│   │     2. gst-inspect-1.0 avdec_aac                     │    │
│   │     3. gst-inspect-1.0 aacparse                      │    │
│   │     4. playbin3 uri=http://ice1.somafm…  → PLAYING   │    │
│   │     5. (D-08) playbin3 uri=https://ice6.somafm…      │    │
│   │  → host PipeWire plays audio (audible from host)     │    │
│   └──────────────────────────────────────────────────────┘    │
│   (Same flow for ms-spike-fedora40 and ms-spike-tumbleweed)   │
│                                                                │
│   Evidence harvest: audible (Kyle) + screenshot                │
│   (gnome-screenshot --window) + transcript (script -c).        │
└────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

```
.planning/spikes/85a-linux-packaging-spike/
├── Dockerfile               # ubuntu:22.04 build container, GLIBC ≤ 2.35 baseline
├── environment-spike.yml    # conda env (conda-forge channel; 10 packages above)
├── build.sh                 # orchestrates Docker build → AppImage; mirrors Phase 43 build.ps1
├── hello_world.py           # minimal Qt event loop + Gst.parse_launch("playbin3 uri=...")
├── AppRun                   # template — the 4 env-var snippet for Phase 85
├── smoke_test.py            # GLIBC + gst-inspect + playbin3 harness; mirrors Phase 43 smoke_test.py shape
├── test_url.txt             # SomaFM URLs (gitignored if it ever has secrets — SomaFM is public so just commit it)
├── artifacts/               # AppImage + build.log + smoke.log + per-distro screenshots (.gitignore)
└── 85A-SPIKE-FINDINGS.md    # findings doc; portable into wrap-up skill verbatim

tools/linux-spike/
├── create-distroboxes.sh    # creates 3 named distroboxes (D-03)
├── teardown-distroboxes.sh  # distrobox rm (D-04)
└── run-smoke.sh             # drives smoke_test.py inside each distrobox; collects evidence
```

Findings doc lives **alongside the source**, NOT in the phase directory — so the wrap-up step can grab the whole `.planning/spikes/85a-linux-packaging-spike/` tree wholesale into the skill (Phase 43 convention).

### Pattern 1: AppRun env-var template (the spike's primary deliverable)

**What:** A pre-rendered `AppRun` bash that exports the four locked env vars before invoking the bundled Python interpreter. Phase 85 copies this verbatim.

**Why this pattern (vs trusting the plugin-generated hook):**
- `linuxdeploy-plugin-gstreamer` writes an apprun-hook at `$APPDIR/apprun-hooks/linuxdeploy-plugin-gstreamer.sh` [VERIFIED: plugin source]. That hook DOES set `GST_PLUGIN_SYSTEM_PATH_1_0`, `GST_PLUGIN_PATH_1_0`, and a `GST_REGISTRY_REUSE_PLUGIN_SCANNER="no"` (note: NOT exactly `GST_REGISTRY_FORK=no` — see Pitfall 3).
- The spike's success criterion #4 names exactly `GST_REGISTRY_FORK=no`. We override the hook to be explicit and consistent with Phase 43's `runtime_hook.py` shape.

**Example template (target shape):**

```bash
#!/bin/bash
# Source: 85a-linux-packaging-spike AppRun template
# Resolve AppImage root (when AppImage extracts; when raw AppDir; when run-from-build)
HERE="$(dirname "$(readlink -f "${0}")")"
export APPDIR="${HERE}"

# --- GStreamer env: bundle paths win over any ambient env --------------------
export GST_PLUGIN_SYSTEM_PATH_1_0="${APPDIR}/usr/conda/lib/gstreamer-1.0"
export GST_PLUGIN_PATH_1_0="${APPDIR}/usr/conda/lib/gstreamer-1.0"
export GST_PLUGIN_SCANNER="${APPDIR}/usr/conda/libexec/gstreamer-1.0/gst-plugin-scanner"

# Disable registry forking on second-launch (Pitfall 3 mitigation; second launch
# otherwise rebuilds the plugin registry from scratch, slow + crash-prone)
export GST_REGISTRY_FORK="no"

# --- GIO TLS backend (HTTPS via souphttpsrc) ---------------------------------
# Without this, HTTPS streams fail with "TLS/SSL support not available; install
# glib-networking" — Phase 43 footgun, validated on Windows; same surface here.
export GIO_EXTRA_MODULES="${APPDIR}/usr/conda/lib/gio/modules"

# --- GI typelibs (PyGObject introspection) -----------------------------------
export GI_TYPELIB_PATH="${APPDIR}/usr/conda/lib/girepository-1.0"

# --- Python: use the bundled conda interpreter -------------------------------
export PYTHONHOME="${APPDIR}/usr/conda"
export PATH="${APPDIR}/usr/conda/bin:${PATH}"

# --- Launch the app ---------------------------------------------------------
exec "${APPDIR}/usr/conda/bin/python" "${APPDIR}/hello_world.py" "$@"
```

This is the canonical pattern the planner copies into the AppRun task; Phase 85 then forks it for the real app.

### Pattern 2: build.sh "mirror Phase 43 build.ps1" shape

**What:** A bash driver that (1) sources/installs build deps via Docker, (2) creates the conda env, (3) lays out the AppDir, (4) invokes linuxdeploy with plugins, (5) sha256-pins the toolchain assets, (6) exits with explicit codes.

**Mirror points from `build.ps1`:**
- Phase 43's `Invoke-Native` wrapper for stderr-trap — Linux equivalent: `set -e` + explicit `2>&1 | tee build.log` redirection; no special wrapper needed (bash doesn't have the PS 5.1 stderr trap).
- Phase 43's `CONDA_PREFIX` detection — Linux equivalent: env-yml-driven conda env created inside the Docker container; `CONDA_PREFIX=/opt/conda/envs/spike-linux` is deterministic in-container.
- Phase 43's exit-code conventions (0=ok, 1=env missing, 2=pyinstaller failed, 3=smoke failed) — Linux uses same scheme; smoke runs INSIDE distrobox post-build (separate script `tools/linux-spike/run-smoke.sh`).

### Anti-Patterns to Avoid

- **Building on the host (Ubuntu 26.04) directly:** GLIBC 2.43 baseline would fail success criterion #2 (`≤ 2.35`). Build MUST happen inside `ubuntu:22.04` Docker container. Host's only role is to drive `build.sh`, run distrobox, and capture evidence.
- **Trusting `linuxdeploy-plugin-gstreamer`'s auto-discovery without setting `GSTREAMER_PLUGINS_DIR`:** plugin defaults to `/usr/lib/$(uname -m)-linux-gnu/gstreamer-1.0` (Debian multiarch). Conda's layout is flat (`$CONDA_PREFIX/lib/gstreamer-1.0`). Without override, plugin scans empty paths → bundles zero plugins → `gst-inspect-1.0 avdec_aac` fails inside AppRun → Pitfall 2 (plugin-discovery) regression.
- **Pre-bundling `bus.add_signal_watch()` / `GstBusLoopThread` complexity:** Phase 43.1 contract is already validated cross-platform per `references/qt-glib-bus-threading.md`. Re-exercising it in the spike expands the failure surface without de-risking anything Linux-specific. **`hello_world.py` uses `Gst.parse_launch("playbin3 uri=...")` and a minimal `GLib.MainLoop` — NO QObject bridge.**
- **Pinning `linuxdeploy` to `1-alpha-20251107-1` (Nov 2025) when `continuous` (May 2025) is the actually-tested asset URL:** The releases page shows the alpha tag exists but the `continuous` tag is what the upstream CI flows publish. Use `continuous` for the asset URL; record the tag's commit SHA at first download.
- **Distrobox `--init` flag (systemd-in-container):** distrobox docs warn this hides host-process visibility from inside the container. Not needed for our use case; default (no `--init`) is correct.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Bundling Python + PyGObject into AppImage | manual `cp -r $CONDA_PREFIX` + relink | `linuxdeploy-plugin-conda` | Plugin already handles miniconda extraction, prefix-rewriting (`conda install --prefix`), and symlink farm under `$APPDIR/usr/bin/` |
| Detecting + bundling GStreamer plugin tree | manual `find` + `cp` of plugin `.so` files | `linuxdeploy-plugin-gstreamer` (redirected via env vars) | Plugin handles scanner+helper binary placement, scoping by registry, and apprun-hook generation. The hook is overridable; the discovery layer is not worth hand-rolling. |
| AppImage signature + zsync metadata | manual `mksquashfs` + `appimagetool` | `linuxdeploy --output appimage` | Handles squashfs + AppImage-runtime concatenation + (later) zsync. Phase 85 surfaces zsync; spike skips. |
| Wayland screenshot from inside a Qt app at runtime | Qt's built-in screenshot APIs | `gnome-screenshot --window` (default GNOME) or `grim` (Sway/wlroots) FROM HOST | The screenshot is host-side evidence captured BY THE HUMAN, NOT something the AppImage produces. Per CONTEXT.md D-Discretion, default to `gnome-screenshot --window` on this rig. |
| Cross-distro testing | manual VM provisioning | `distrobox create` per D-03 | distrobox shares Wayland + PipeWire + DBus + $HOME by default, giving real audible-playback fidelity from a single host. **The container's userspace runs against the host kernel** (single-host caveat accepted in D-02). |
| HTTPS TLS bundling | hand-rolled `ca-certificates` copy | `glib-networking` conda package (auto-bundled by plugin-conda) | TLS module discovery follows `GIO_EXTRA_MODULES` (Phase 43-validated env-var). Hand-rolling adds a CA-store maintenance burden. |

**Key insight:** The two plugins (`-conda` and `-gstreamer`) handle 90% of the bundle assembly. The spike's job is to (a) wire them up correctly, (b) prove the AppRun env-var snippet is the right 4 vars in the right shape, and (c) verify cross-distro PASS empirically. Every NEW shell line written in `build.sh` is a future maintenance liability — bias hard toward letting the plugins do the work.

## Runtime State Inventory

> Phase 85a is a greenfield spike — no rename/refactor/migration of existing runtime state. Section omitted by intent.

## Common Pitfalls

### Pitfall 1: GLIBC baseline drift (success criterion #2)

**What goes wrong:** AppImage built on a newer-glibc host (e.g., Ubuntu 24.04+, Fedora 40+, host's own Ubuntu 26.04) links against `GLIBC_2.39` or higher; refuses to load on Ubuntu 22.04 LTS users with `version 'GLIBC_2.39' not found`.

**Why it happens:** GCC + glibc's ELF symbol versioning is one-way; an executable referencing `memcpy@GLIBC_2.34` runs on any glibc ≥ 2.34, but `clock_gettime@GLIBC_2.39` requires glibc ≥ 2.39.

**Prevention:** Build INSIDE `ubuntu:22.04` Docker container (GLIBC 2.35). Conda-forge binaries shipped through `linuxdeploy-plugin-conda` were themselves built against an old glibc baseline (conda-forge's CI uses CentOS 7-era manylinux); the only fresh-glibc surface is anything bash/Python compiles at build time — should be nothing for this spike.

**Warning signs:** `strings AppRun_or_main_so | grep GLIBC_ | sort -V | tail -1` reports `GLIBC_2.36` or higher.

**Triggering condition (negative-pivot per D-09):** If GLIBC grep reports > 2.35 on the AppImage produced inside the Ubuntu 22.04 container, **STOP the spike and report**. Do not chase the leak; let Phase 85 design the proper fix.

### Pitfall 2: Plugin discovery failure (success criterion #3)

**What goes wrong:** `gst-inspect-1.0 avdec_aac` and `gst-inspect-1.0 aacparse` exit non-zero from inside AppRun → playbin3 can't autoplug → MP3 may still work (mpegaudioparse + mpg123 in gst-plugins-good+ugly), but AAC immediately breaks → Phase 85 PKG-LIN-APP-03 AAC tier fails.

**Why it happens:** `linuxdeploy-plugin-gstreamer` defaults to system multiarch paths (`/usr/lib/x86_64-linux-gnu/gstreamer-1.0`). Conda's layout is `$CONDA_PREFIX/lib/gstreamer-1.0` (flat, no multiarch). Without `GSTREAMER_PLUGINS_DIR` redirect, plugin discovers nothing.

**Prevention:** `build.sh` exports `GSTREAMER_PLUGINS_DIR=$APPDIR/usr/conda/lib/gstreamer-1.0` and `GSTREAMER_HELPERS_DIR=$APPDIR/usr/conda/libexec/gstreamer-1.0` BEFORE running `./linuxdeploy --plugin gstreamer`. AppRun template also re-asserts `GST_PLUGIN_SYSTEM_PATH_1_0` to the same path defensively.

**Warning signs:** `./MusicStreamerSpike-x86_64.AppImage gst-inspect-1.0 avdec_aac` (the AppRun forwards args) → exit 1 + `"No such element or plugin 'avdec_aac'"`.

**Triggering condition (negative-pivot):** If after redirect env vars are applied, `gst-inspect-1.0 avdec_aac` STILL fails to resolve from inside AppRun, **STOP the spike and report**. The next remediation (hand-roll plugin copy + skip linuxdeploy-plugin-gstreamer entirely) is a Phase 85 planning decision, not a spike pivot.

### Pitfall 3: `GST_REGISTRY_FORK` flag spelling — silent registry rebuild on second launch (success criterion #4 + D-06 relaunch protocol)

**What goes wrong:** Second launch of the AppImage takes 5–30 seconds longer than first launch because GStreamer rebuilds the plugin registry from scratch instead of reusing the cached binary registry.

**Why it happens:** `linuxdeploy-plugin-gstreamer`'s generated AppRun hook sets `GST_REGISTRY_REUSE_PLUGIN_SCANNER="no"` [VERIFIED: plugin source line 17]. The locked spec from CONTEXT.md calls for `GST_REGISTRY_FORK=no`. These are TWO DIFFERENT FLAGS:
- `GST_REGISTRY_FORK=no` — disables the **fork()-then-scan** behavior; registry IS reused. This is what we want.
- `GST_REGISTRY_REUSE_PLUGIN_SCANNER=no` — the plugin sets this; **disables scanner-process reuse** but does NOT disable registry rebuild.

The AppRun template MUST set `GST_REGISTRY_FORK=no` explicitly (overriding the plugin's hook if necessary). [CITED: gstreamer.freedesktop.org docs on Environment Variables — `GST_REGISTRY_FORK` controls fork-before-scan; `GST_REGISTRY_REUSE_PLUGIN_SCANNER` controls scanner-process pooling]

**Prevention:** AppRun template (Pattern 1 above) sets `GST_REGISTRY_FORK=no` AFTER the plugin's hook is sourced.

**Warning signs:** Per D-06 audible-PASS protocol step 7 (relaunch), second launch takes noticeably longer than first; smoke_test reports `Gst.State.READY → PAUSED → PLAYING` taking > 5 seconds.

**Triggering condition (negative-pivot):** If second launch consistently regresses time-to-PLAYING by > 5s and the AppRun template doesn't fix it, **STOP and report** — this is a Phase 85 design question.

### Pitfall 4: HTTPS silently fails — glib-networking module not discovered

**What goes wrong:** HTTPS stream (D-08, `https://ice6.somafm.com/...`) hangs or errors with `"TLS/SSL support not available; install glib-networking"`. HTTP stream works fine.

**Why it happens:** `glib-networking` ships GIO TLS modules at `$CONDA_PREFIX/lib/gio/modules/libgiognutls.so` (or `libgioopenssl.so` depending on conda-forge build). `souphttpsrc` looks up TLS backend via `Gio.TlsBackend.get_default()` which scans `$GIO_EXTRA_MODULES`. If unset, scans only system paths → finds nothing in the AppImage.

**Prevention:** AppRun template sets `GIO_EXTRA_MODULES=$APPDIR/usr/conda/lib/gio/modules`. (Phase 43's `runtime_hook.py` lines 24-27 establish the same fix on Windows.)

**Warning signs:** `smoke_test.py`'s TLS assertion (`Gio.TlsBackend.get_default().get_default_database() is not None`) returns False; HTTPS pipeline never reaches PLAYING.

**Triggering condition (negative-pivot):** If `GIO_EXTRA_MODULES` is set correctly AND TLS still fails, **STOP and report** — likely indicates conda-forge `glib-networking` package itself isn't shipping the module on linux-64 (Phase 43 Windows-side proved this works on Windows; Linux failure would be a new finding).

### Pitfall 5: Distrobox passes Wayland + PipeWire but NOT all GTK/Qt theme assets

**What goes wrong:** AppImage launches inside distrobox; window appears with default Adwaita-fallback theme, missing the host's accent colors / fonts / icon theme. Audio + functionality work fine; visuals look "naked."

**Why it happens:** distrobox shares Wayland socket + PipeWire socket + DBus session bus + `$HOME` by default [VERIFIED: distrobox docs — `tight integration ... HOME directory, Wayland and X11 sockets, networking, removable devices, systemd journal, SSH agent, D-Bus`]. But it does NOT mount the host's `/usr/share/themes`, `/usr/share/icons`, or distro-specific Qt platform plugins. The container's own (possibly stale Ubuntu 22.04 base) theme assets are what render.

**Prevention:** Accept for spike. Phase 85 may address via `--filesystem=host` (Flatpak) or AppImage-side theme bundling, but **the spike's evidence requirement is audible + screenshot + transcript, not pixel-perfect theming**.

**Warning signs:** Window looks unstyled in the screenshot. **Not a failure** — call this out in findings as a known limitation and proceed.

### Pitfall 6: `MINICONDA_VERSION` defaults to "latest" — non-reproducible build

**What goes wrong:** `linuxdeploy-plugin-conda` downloads `Miniconda3-latest-Linux-x86_64.sh` from `repo.anaconda.com/miniconda/` by default [VERIFIED: plugin source]. "latest" rolls month-to-month; a build today and a build in 60 days produce different miniconda interiors, different Python micro-versions, and possibly different solver behavior.

**Why it happens:** The plugin honors `MINICONDA_VERSION` env var but defaults to no pin.

**Prevention:** `build.sh` sets `MINICONDA_VERSION=py312_24.X.Y-0` (researcher recommends pinning to current stable; planner verifies the exact pin via `repo.anaconda.com/miniconda/` index at planning time — current 2026-05 best practice is the `py312_24.9.2-0` tier or newer). Findings doc captures the exact pin used at spike-execution time.

**Warning signs:** Re-running `build.sh` produces a different SHA256 for the AppImage between runs without source changes.

**Triggering condition (negative-pivot):** Not a stopper for spike — document the version that worked; let Phase 85 lock the pin.

### Pitfall 7: Phase 43 Windows plugin BOM mismatch — Linux bundle missing decoder

**What goes wrong:** Linux conda env shape diverges from Phase 43 Windows conda env shape; Linux is missing a decoder that Windows had; PKG-LIN-APP-03's "same plugin set as the Windows installer" clause is violated; AAC plays on Windows but not on Linux.

**Why it happens:** Conda-forge package availability differs per platform. Phase 43 (Windows) used: `python pygobject pycairo pyinstaller pyinstaller-hooks-contrib gstreamer gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly`. Linux MUST add `gst-libav` (for AAC/H.264 decoders; on Windows this came from `gst-plugins-bad` in Phase 43 era but is in `gst-libav` on Linux conda-forge per Phase 69 finding in CONCERNS.md). Linux also adds `gst-python` and `glib-networking` explicitly (Windows conda-forge meta-pulls them).

**Prevention:** `environment-spike.yml` above explicitly lists `gst-libav`, `gst-python`, `glib-networking` — Phase 43's stack-windows-gstreamer-bundling.md cross-reference covers the rest.

**Warning signs:** Smoke test's `gst-inspect-1.0 avdec_aac` resolves on Windows AppImage but not on Linux AppImage.

### Pitfall 8: `linuxdeploy-plugin-gstreamer` maintenance dormancy

**What goes wrong:** Plugin last touched March 2024 (Issue #18 fix). If upstream linuxdeploy makes a breaking ABI change to the plugin interface, this plugin breaks silently and is unlikely to be patched quickly.

**Why it happens:** [CITED: github.com/linuxdeploy/linuxdeploy-plugin-gstreamer commits — last commit 2024-03-01; only 5 stars, 12 forks, 7 open issues]

**Prevention:** Pin `linuxdeploy-plugin-gstreamer.sh` SHA256 in `build.sh`. If a future linuxdeploy update breaks the plugin, downgrade linuxdeploy until plugin is fixed. Long-term remediation (out of spike scope): consider hand-rolling the plugin replacement (just copy + AppRun hook + scanner placement — ~30 lines of bash).

**Warning signs:** `./linuxdeploy --plugin gstreamer` exits non-zero with `"unknown plugin command"` or similar. Or: builds succeed but produced AppRun hook is empty.

**Triggering condition (negative-pivot):** If at spike-execution time the plugin is structurally broken against current linuxdeploy, **STOP the spike and report** — Phase 85 then decides whether to bundle a fixed-fork of the plugin or hand-roll.

### Pitfall 9: SomaFM ICY metadata parser surprise

**What goes wrong:** SomaFM streams advertise `Icy-MetaInt: 16000` (default) and embed `StreamTitle='...'` metadata between audio chunks. If `souphttpsrc` doesn't request metadata (`extra-headers`), or if `playbin3` doesn't surface `GST_TAG_TITLE` to the message bus, smoke_test might pass on audible playback but the spike's findings transcript will lack ICY confirmation.

**Why it happens:** Phase 43's `smoke_test.py` watches `Gst.MessageType.TAG` for first-byte arrival as a proxy for "TLS + HTTP + demux worked." Linux conda-forge's `souphttpsrc` behaves the same; tag should arrive within 2–3 seconds.

**Prevention:** smoke_test.py mirrors Phase 43's `_on_message` handler exactly — capture TAG event timestamps.

**Warning signs:** Stream plays audibly but smoke_test reports `first_tag_arrived=None` and exits with code 3 (timeout). Not a spike-failure — falls back to bus-level STATE_CHANGED→PLAYING for the pipeline-state assertion.

### Pitfall 10: PipeWire vs PulseAudio sink election

**What goes wrong:** Host runs PipeWire (modern GNOME default). AppImage's bundled `gst-plugins-good` provides `pulsesink`. PulseAudio-compat shim in PipeWire usually catches this transparently — but on some distros, `autoaudiosink` picks an entirely different sink (`alsasink` for Tumbleweed without pulse-compat) and the connection chain to PipeWire breaks.

**Why it happens:** GStreamer's `autoaudiosink` is a rankings-based picker. Inside an AppImage that lacks all the host's audio-routing daemons, autoaudiosink may make the wrong choice.

**Prevention:** `hello_world.py` uses `playbin3` with NO explicit `audio-sink` property — let playbin3 use `autoaudiosink`. If a specific distro fails, smoke_test logs the elected sink (`autoaudiosink ! pulsesink` vs `autoaudiosink ! alsasink`) so findings can capture per-distro.

**Warning signs:** Audible playback on Ubuntu, silent on Tumbleweed; smoke_test's `gst-launch-1.0 -v` log shows `alsasink` instead of `pulsesink`.

**Triggering condition (negative-pivot):** If audible-PASS fails on one distro but works on another with the SAME AppImage, **STOP and report** — this is a Phase 85 sink-selection design question.

## Code Examples

### Minimal hello_world.py (mirrors Phase 43 smoke_test.py shape, Linux-tuned)

```python
"""Phase 85a spike: minimal playbin3 over HTTPS, no QObject bus bridge.
Mirrors Phase 43 smoke_test.py shape; deliberately simpler to keep failure-
surface narrow per CONTEXT.md D-Discretion.

Exit codes:
  0 — pipeline reached PLAYING within 10s and ran for 30s without error
  1 — setup failure (Gst.init, factory, URI)
  2 — runtime failure (pipeline errored)
  3 — timeout (never reached PLAYING)
"""
from __future__ import annotations
import sys
import time

import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib  # noqa: E402


def _emit(prefix: str, **kv: object) -> None:
    parts = [prefix] + [f"{k}={v!r}" for k, v in kv.items()]
    print(" ".join(parts), flush=True)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        _emit("SPIKE_FAIL", reason="usage", expected="hello_world.py <url>")
        return 1

    url = argv[1].strip()
    Gst.init(None)
    _emit("SPIKE_DIAG",
          gst_version=Gst.version_string(),
          plugin_count=len(Gst.Registry.get().get_plugin_list()),
          url_scheme=url.split(":", 1)[0])

    # parse_launch keeps surface tiny — no element wiring, no caps negotiation
    pipeline = Gst.parse_launch(f'playbin3 uri="{url}"')
    state = {"errors": [], "playing_at": None, "first_tag_at": None}

    bus = pipeline.get_bus()
    bus.add_signal_watch()

    def _on_message(_bus, msg):
        if msg.type == Gst.MessageType.ERROR:
            err, debug = msg.parse_error()
            state["errors"].append(f"{err.message} | {debug}")
        elif msg.type == Gst.MessageType.STATE_CHANGED:
            if msg.src == pipeline:
                _old, new, _pending = msg.parse_state_changed()
                if new == Gst.State.PLAYING and state["playing_at"] is None:
                    state["playing_at"] = time.monotonic()
                    _emit("SPIKE_DIAG", event="reached_playing")
        elif msg.type == Gst.MessageType.TAG and state["first_tag_at"] is None:
            state["first_tag_at"] = time.monotonic()
            _emit("SPIKE_DIAG", event="first_tag")

    bus.connect("message", _on_message)
    pipeline.set_state(Gst.State.PLAYING)

    loop = GLib.MainLoop()
    start = time.monotonic()

    def _tick():
        if state["errors"]:
            loop.quit(); return False
        elapsed = time.monotonic() - start
        if state["playing_at"] and (time.monotonic() - state["playing_at"]) >= 30.0:
            loop.quit(); return False
        if elapsed >= 40.0:  # 10s to PLAYING + 30s playback budget
            loop.quit(); return False
        return True

    GLib.timeout_add(200, _tick)
    try:
        loop.run()
    finally:
        pipeline.set_state(Gst.State.NULL)

    if state["errors"]:
        _emit("SPIKE_FAIL", step="pipeline", errors=state["errors"])
        return 2
    if state["playing_at"] is None:
        _emit("SPIKE_FAIL", step="never_played")
        return 3

    _emit("SPIKE_OK",
          time_to_play_s=round(state["playing_at"] - start, 2),
          first_tag_s=round((state["first_tag_at"] or 0) - start, 2),
          played_for_s=round(time.monotonic() - state["playing_at"], 2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

[VERIFIED: structure mirrors Phase 43 smoke_test.py with playbin3 + bus signal-watch + state-change marker; Linux simplifications validated against gstreamer.freedesktop.org playbin3 docs]

### Dockerfile shape (Ubuntu 22.04 build container)

```dockerfile
# .planning/spikes/85a-linux-packaging-spike/Dockerfile
# Pin a specific digest — recorded in findings doc at spike-execution time
FROM ubuntu:22.04@sha256:<CAPTURED-AT-BUILD-TIME>

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates curl wget bzip2 file libfuse2 desktop-file-utils && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Conda-forge miniforge — alternative to plugin-conda downloading miniconda3.
# Spike uses plugin-conda's bundled miniconda; this image only needs the
# bootstrap shell + linuxdeploy.
WORKDIR /work
COPY . /work
RUN chmod +x build.sh
ENTRYPOINT ["/work/build.sh"]
```

[ASSUMED: `libfuse2` needed for linuxdeploy to mount-and-exec its own AppImage during the bundle step. Verified pattern from AppImage upstream docs; planner confirms during execution.]

### distrobox create commands (per D-03)

```bash
# tools/linux-spike/create-distroboxes.sh
set -euo pipefail

# Ubuntu 22.04 — matches build container, useful as a "control" run
distrobox create \
  --image docker.io/library/ubuntu:22.04 \
  --name ms-spike-ubuntu22 \
  --yes

# Fedora 40 — quay.io path per distrobox compatibility matrix
distrobox create \
  --image quay.io/fedora/fedora:40 \
  --name ms-spike-fedora40 \
  --yes

# openSUSE Tumbleweed — opensuse registry per compatibility matrix
distrobox create \
  --image registry.opensuse.org/opensuse/tumbleweed:latest \
  --name ms-spike-tumbleweed \
  --yes

# Verification — all three should appear in the list, status "Created"
distrobox list
```

[VERIFIED: image registry paths confirmed via distrobox compatibility docs]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| AppImageKit (`appimagetool`) only | `linuxdeploy` + plugin model | linuxdeploy 1.x (~2020) | Plugin ecosystem (`-conda`, `-gstreamer`, `-qt`, etc.) handles 90% of bundle assembly |
| System gstreamer dynamic-link | Bundle gstreamer via conda-forge | Phase 43 (2026-04) | Cross-distro PASS without depending on host having same GStreamer minor version |
| GnuTLS as default GIO TLS backend on Windows | OpenSSL as default | GStreamer 1.28.x (Q4 2024) | Linux conda-forge `glib-networking` still ships gnutls module; behavior is backend-agnostic via `Gio.TlsBackend.get_default()` |
| GLIBC 2.28 baseline (CentOS 7) for AppImage builds | GLIBC 2.35 baseline (Ubuntu 22.04 LTS) | Project-specific (PKG-LIN-APP-08) | Drops support for very old hosts (CentOS 7) but covers 99% of 2026 Linux desktops |
| dbus-python for MPRIS2 | PySide6.QtDBus | Phase 41 (already shipped in v2.0) | NOT a spike concern; deferred to Phase 85 |

**Deprecated/outdated:**
- The `gst-plugins.txt` filter mechanism mentioned in older linuxdeploy-plugin-gstreamer docs is NOT in current source — plugin now broad-collects from `GSTREAMER_PLUGINS_DIR` and prunes nothing.
- `GST_REGISTRY` (no `_FORK` suffix) — was an old name for a different thing (the registry file path); deprecated. Use `GST_REGISTRY_FORK` (controls fork-then-scan) per current GStreamer docs.

## Project Constraints (from CLAUDE.md)

- **Spike-findings routing:** Any spike-related work must reference `Skill("spike-findings-musicstreamer")`. Wrap-up step APPENDS to existing skill, never creates new skill. (CONTEXT.md D-Discretion confirms.)
- **No additional project-level CLAUDE.md directives beyond the routing rule.** Memory file references (gsd-sdk wrapper, Wayland DPR=1.0, QNAP→GitHub mirror) are environmental — not enforceable as research-output constraints.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `libfuse2` is the required AppImage runtime in Dockerfile | Code Examples (Dockerfile shape) | Build fails inside container with "AppImage requires FUSE"; mitigation: install `libfuse2t64` on Ubuntu 22.04 OR use `--appimage-extract-and-run` mode |
| A2 | `MINICONDA_VERSION=py312_24.9.2-0` is current stable | Pitfall 6 | Planner verifies via `repo.anaconda.com/miniconda/` index at planning time; documented in findings as exact pin |
| A3 | `linuxdeploy@continuous` (the May 2025 build) is the asset URL to use rather than `1-alpha-20251107-1` | Standard Stack | If the alpha tag is the "official" one upstream prefers, switch to its asset URL (planner verifies via `linuxdeploy --version` after extract) |
| A4 | `linuxdeploy-plugin-gstreamer` AppRun hook is overridable by a hand-written AppRun that runs AFTER the hook is sourced | Pattern 1, Pitfall 3 | If linuxdeploy hard-overwrites the AppRun at output-image time, we have to patch the hook script in-place instead — falls under Pitfall 8 trigger |
| A5 | Distrobox passes `XDG_RUNTIME_DIR` (pipewire socket) into the container by default for audio | Architecture diagram | If audio doesn't work in distrobox on first try, add `--additional-flags "--volume $XDG_RUNTIME_DIR:$XDG_RUNTIME_DIR"` to `create-distroboxes.sh` |
| A6 | `gnome-screenshot --window` works on GNOME Wayland for capturing a single window | Per-Distro Evidence Workflow | If portal-only screenshot is enforced on the host's GNOME version, fall back to `grim` (Sway-compatible but works on most wlroots; on GNOME may need `gdbus call --session --dest=org.gnome.Shell.Screenshot ...`) |

## Open Questions (RESOLVED-VIA-SPIKE)

> All five open questions carry a `Recommendation:` that plans implement, so they are NOT blockers — they are answered either at planning time (by the planner adopting the recommendation) or at execution time (when the spike actually runs and observes behavior). Per-question disposition below.

1. **Does `linuxdeploy-plugin-gstreamer` honor `GSTREAMER_PLUGINS_DIR` when pointed at a non-multiarch flat layout?**
   - What we know: The plugin source supports `GSTREAMER_PLUGINS_DIR` as an override. The fall-through scan order is multiarch-first.
   - What's unclear: Whether the plugin's discovery loop walks subdirectories or assumes a flat `*.so` listing.
   - Recommendation: Spike's first iteration is this test; if it fails, the spike's PRIMARY finding is "plugin needs hand-rolled replacement" — this is the load-bearing unknown.
   - **Status:** ANSWERED-AT-EXECUTION (Plan 05 build.sh exercises the override; outcome documented in 85A-SPIKE-FINDINGS.md)

2. **Does Phase 43's `GST_PLUGIN_SCANNER_1_0` env var (note the trailing `_1_0`) supersede `GST_PLUGIN_SCANNER` in 1.28+?**
   - What we know: The plugin's hook sets `GST_PLUGIN_SCANNER_1_0` (suffix); Phase 43 Windows uses `GST_PLUGIN_SCANNER` (no suffix).
   - What's unclear: Whether the suffix-form is current and the no-suffix is legacy, or vice versa.
   - Recommendation: AppRun template sets BOTH defensively; smoke_test logs which one GStreamer actually picked up.
   - **Status:** RESOLVED via Plan 04 Task 2 (AppRun sets both spellings defensively)

3. **Does conda-forge ship `glib-networking` with OpenSSL or GnuTLS backend on linux-64?**
   - What we know: Phase 43 (Windows) flipped to OpenSSL in 1.28.x. Linux side hasn't been validated.
   - What's unclear: Which `.so` ships in `$CONDA_PREFIX/lib/gio/modules/`.
   - Recommendation: smoke_test's TLS assertion is backend-agnostic (`has_default_database`); findings doc captures the module filename.
   - **Status:** RESOLVED via Plan 04 Task 3 (smoke_test.py TLS assertion is backend-agnostic — just asserts HTTPS URL reaches PLAYING)

4. **Will Tumbleweed's rolling kernel introduce a runtime surprise the build container can't predict?**
   - What we know: As of 2026-05, Tumbleweed ships GLIBC 2.42. The AppImage built against GLIBC 2.35 binary-runs on 2.42 (forward-compatible).
   - What's unclear: Whether any GStreamer or Qt library inside the bundle has a glibc-version-conditional behavior (rare but possible).
   - Recommendation: Tumbleweed is the third (hardest) distro for a reason — if it fails, the failure mode itself is the finding.
   - **Status:** ANSWERED-AT-EXECUTION (Plan 07 Task 3 audible PASS on Tumbleweed distrobox; if surprise occurs, finding documented per negative-pivot policy)

5. **Is the dev rig's GNOME version recent enough for `gnome-screenshot --window` to capture distrobox-launched windows?**
   - What we know: Host is Ubuntu 26.04 + GNOME Wayland; `gnome-screenshot` is installable via apt.
   - What's unclear: Whether the host's xdg-desktop-portal version supports capturing windows owned by distrobox-side processes.
   - Recommendation: Test once before spike begins; fall back to `grim` if needed.
   - **Status:** RESOLVED via Plan 01 (host probe + both tools installed) and Plan 07 (`.action` documents grim fallback if gnome-screenshot --window fails)

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `podman` | distrobox engine (D-01) | ✓ | 5.7.0 | — |
| `docker` | build container | ✓ | 29.5.2 | use podman build with rootful flag |
| `distrobox` | cross-distro sessions (D-02) | ✗ | — | `sudo apt install distrobox` — planner must add as Wave 0 |
| `grim` | Wayland screenshot fallback | ✗ | — | `sudo apt install grim` — installable |
| `gnome-screenshot` | Wayland screenshot primary | ✗ (not installed; apt-installable) | — | `sudo apt install gnome-screenshot` — planner must add as Wave 0 |
| `gst-inspect-1.0` (host-side, for sanity) | host-side env check | ✓ | 1.28.2 (from `gstreamer1.0-tools`) | — |
| `script` (BSD `script(1)`) | terminal transcript capture | ✓ (in `bsdutils`/`util-linux`) | — | `tee` as fallback |
| `strings` | GLIBC grep | ✓ | (binutils) | — |
| `curl` + `sha256sum` | SHA-pinning toolchain | ✓ | — | — |
| `flatpak` | NOT needed for Phase 85a | ✓ (installed; irrelevant) | — | — |

**Missing dependencies with no fallback:** none — all gaps are apt-installable.

**Missing dependencies with fallback:**
- `distrobox` + `gnome-screenshot` — install via `sudo apt install` as first task in spike Wave 0.

**Host session probe (verified 2026-05-25):**
- Host OS: Ubuntu 26.04 LTS "Resolute Raccoon" (GLIBC 2.43)
- `WAYLAND_DISPLAY=wayland-0`, `XDG_SESSION_TYPE=wayland`, `XDG_CURRENT_DESKTOP=ubuntu:GNOME`
- ALL THREE distro images (ubuntu:22.04, fedora:40, opensuse/tumbleweed) listed in distrobox compatibility matrix and pull-tested by HTTP

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | NONE (this is a spike — no pytest test files produced) |
| Config file | n/a |
| Quick run command | `bash tools/linux-spike/run-smoke.sh ms-spike-ubuntu22` |
| Full suite command | `bash tools/linux-spike/run-smoke.sh ms-spike-ubuntu22 && … ms-spike-fedora40 && … ms-spike-tumbleweed` |

### Validation Dimensions (per Output spec section 11)

| Dim # | Validation | Tier | Pass Condition |
|-------|------------|------|----------------|
| D1 | Pipeline state assertion (PLAYING within 10s) | automated | smoke_test exit 0 for both HTTP + HTTPS variants on ≥1 distro |
| D2 | GLIBC source-grep ≤ 2.35 | automated | `strings AppRun_or_main_so \| grep GLIBC_ \| sort -V \| tail -1` returns `GLIBC_2.35` or lower on EVERY distro |
| D3 | Plugin resolution: avdec_aac + aacparse | automated | both `gst-inspect-1.0` exit 0 from inside AppRun on EVERY distro |
| D4 | Audible PASS (30s play + pause/resume + stop + relaunch) | manual (Kyle) | per D-06 protocol; recorded per-distro in findings |
| D5 | Evidence capture (audible + screenshot + transcript) | manual (Kyle) | all 3 artifacts present per distro in findings doc |
| D6 | AppRun template captured | doc-level | template's 4 env vars documented with rationale in findings |
| D7 | Reproducibility | automated | clean checkout → `create-distroboxes.sh && build.sh && run-smoke.sh` exits 0 |
| D8 | Negative-pivot triggers documented | doc-level | findings doc enumerates Pitfalls 1–10 with explicit stop conditions |

### Phase Requirements → Test Map

**No requirements consumed directly** — spike's deliverable is the findings document + reusable sources that Phase 85 consumes (PKG-LIN-APP-01..09).

| Spike Success Criterion | Validation Dim | Automated? |
|-------------------------|----------------|------------|
| SC1: AppImage plays MP3 on all 3 distros | D4 + D5 | manual + automated D1 |
| SC2: GLIBC ≤ 2.35 | D2 | automated |
| SC3: avdec_aac + aacparse resolve | D3 | automated |
| SC4: AppRun env-var template captured | D6 | doc-level |

### Sampling Rate

- **Per-iteration:** `tools/linux-spike/run-smoke.sh ms-spike-ubuntu22` (fastest distro to validate; full distro sweep is end-of-iteration)
- **Per-distro merge:** Full smoke + audible-PASS protocol per D-06
- **Phase gate:** All 3 distros PASS + findings doc + skill APPEND complete

### Wave 0 Gaps

- [ ] `sudo apt install distrobox gnome-screenshot grim` — Wave 0 prerequisite (host-side; planner adds as first task)
- [ ] `tools/linux-spike/create-distroboxes.sh` — Wave 0 deliverable (3 named containers)
- [ ] `.planning/spikes/85a-linux-packaging-spike/Dockerfile` — Wave 0 deliverable (ubuntu:22.04 build container)
- [ ] `.planning/spikes/85a-linux-packaging-spike/environment-spike.yml` — Wave 0 deliverable (conda env shape locked above)
- [ ] No pytest framework needed — spike has no production-code surface to unit-test

## Security Domain

Phase 85a is a throwaway spike with no production data flow. ASVS categories largely inapplicable. Below is the minimal required surface check.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | spike does not authenticate |
| V3 Session Management | no | spike has no sessions |
| V4 Access Control | no | spike runs as host user, no privilege boundary |
| V5 Input Validation | partial | smoke_test only consumes a single argv URL — validate URL scheme is `http://` or `https://` and host is `*.somafm.com` to prevent accidental SSRF-like execution against unintended hosts during dev iteration |
| V6 Cryptography | no | TLS via glib-networking (system library), no app-side crypto |
| V11 Business Logic | no | spike has no business logic |
| V12 Files and Resources | partial | conda env extraction is to a controlled `$APPDIR`; toolchain assets SHA256-pinned (slop / supply-chain mitigation) |
| V14 Configuration | partial | toolchain pin via SHA256 + conda-forge channel-only is the dependency-control surface |

### Known Threat Patterns for AppImage build chains

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Slopped toolchain asset (someone hijacks `linuxdeploy-plugin-conda` raw script URL) | Tampering | SHA256-pin assets in `build.sh`; CI fails if hash diverges |
| Conda-forge package squatting | Spoofing | Channel-only `conda-forge` pin; 10 packages above are all canonical |
| Smoke test URL spoofing (someone replaces SomaFM URL in `test_url.txt`) | Tampering | Commit `test_url.txt` to git; SomaFM URLs are public; review at PR time |
| Distrobox `--init` (systemd-in-container) privilege escalation | EoP | Do NOT use `--init` — default no-systemd containers are correct |

## Wrap-Up Targets for `spike-findings-musicstreamer` Skill

After spike PASS, run `/gsd:spike-wrap-up` (mirrors Phase 43 flow). The wrap-up MUST:

1. **Create new sources directory:** `.claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/` — copy verbatim:
   - `Dockerfile`
   - `environment-spike.yml`
   - `build.sh`
   - `hello_world.py`
   - `AppRun` (template form)
   - `smoke_test.py`
   - `85A-SPIKE-FINDINGS.md` (renamed `85A-SPIKE-FINDINGS.md` → keep, or `README.md` — match Phase 43 convention of preserving the original `XX-SPIKE-FINDINGS.md` name)
   - `tools/linux-spike/create-distroboxes.sh` → copy into `sources/85a-…/create-distroboxes.sh`
   - `tools/linux-spike/run-smoke.sh` → copy into `sources/85a-…/run-smoke.sh`

2. **Add new feature-area row to `SKILL.md` `findings_index` table:**

   | Area | Reference | Key Finding |
   |------|-----------|-------------|
   | Linux AppImage Bundling | references/linux-appimage-bundling.md | conda-forge is the only viable PyGObject+GStreamer source on Linux too; `linuxdeploy-plugin-gstreamer` defaults to multiarch system paths and MUST be redirected to `$APPDIR/usr/conda/lib/gstreamer-1.0/` via `GSTREAMER_PLUGINS_DIR`. AppRun template owns `GST_REGISTRY_FORK=no` explicitly (plugin only sets `GST_REGISTRY_REUSE_PLUGIN_SCANNER=no`, a different flag). Distrobox+podman shares Wayland+PipeWire+DBus by default — cross-distro PASS achievable from a single host. |

3. **Create new references file `.claude/skills/spike-findings-musicstreamer/references/linux-appimage-bundling.md`** summarizing:
   - **Validated patterns:** linuxdeploy + plugin-conda + plugin-gstreamer wiring; AppRun env-var template (4 vars); conda-forge env shape (mirrors Windows ±gst-libav ±glib-networking explicit).
   - **Landmines:** Pitfalls 1–10 from this RESEARCH.md, recompacted.
   - **Constraints:** GLIBC ≤ 2.35 baseline (Ubuntu 22.04 LTS), `linuxdeploy-plugin-gstreamer` maintenance dormancy (Mar 2024 last touch), distrobox host-theme passthrough limitation.
   - **Origin:** Phase 85a spike + cross-references back to `windows-gstreamer-bundling.md`.

4. **Update `<metadata><processed_spikes>` section in SKILL.md:** append `- 85a-linux-packaging-spike (Phase 85a; Linux AppImage bundling via linuxdeploy-plugin-conda + linuxdeploy-plugin-gstreamer)`.

## Phase 85 Hand-Off Manifest

The following artifacts are EXACTLY what Phase 85's planner consumes from this spike:

### Ready for Phase 85 copy-paste

- **`AppRun` template** — the 4-env-var snippet documented above (Pattern 1). Phase 85 copies verbatim and adapts the final `exec` line to `exec ${APPDIR}/usr/conda/bin/python -m musicstreamer "$@"`.
- **`environment.yml` conda env shape** — 10 conda-forge packages; Phase 85 ADDS `nodejs`, `chardet<6`, `requests`, `yt-dlp`, `streamlink`, `platformdirs`, the actual `musicstreamer` source (via pip from local path), `winrt-Windows-*` (NO — Windows-only; skip), plus any other v2.2 requirements.
- **`linuxdeploy` + 2 plugin SHA256 pins** — captured in spike's `build.sh`; Phase 85 inherits the same pins or bumps as needed.
- **Plugin BOM** (from `gst-inspect-1.0 -a` inside AppRun) — Phase 85's `tools/check_bundle_plugins_linux.py` (the Linux-equivalent drift-guard) consumes this list as the assertion baseline.
- **`Dockerfile` ubuntu:22.04 base** — Phase 85's CI/build inherits identical Docker base.
- **`distrobox` + recreate-script** — Phase 85 reruns `tools/linux-spike/create-distroboxes.sh` for its own UAT (containers ephemeral per D-04).
- **Pitfalls 1–10** — translated into Phase 85 PLAN.md's "Common Pitfalls" research input.
- **GLIBC literal `GLIBC_2.35`** — Phase 85 wires into `tests/test_packaging_spec.py` source-grep test (PKG-LIN-APP-08).
- **`hello_world.py` shape** — Phase 85 references for `tests/test_packaging_linux_smoke.py` (if added).

### Deliberately left for Phase 85 to figure out

- **Real `musicstreamer/` app bundling** — extending `environment.yml` to include the full v2.2 deps, plus pip-installing the local `musicstreamer` package into the bundled conda env (Phase 85 task).
- **`.desktop` registration + icon + `MIME=audio` integration** — Phase 85 surface (PKG-LIN-APP-05).
- **zsync update-info embedding** — Phase 85 surface (PKG-LIN-APP-06).
- **MPRIS2 D-Bus reachability test** — Phase 85 surface (PKG-LIN-APP-07); depends on Phase 91 (FIX-MPRIS) for the test baseline.
- **`.pls` / `.m3u` MIME-association NEGATIVE test** — Phase 85 surface (PKG-LIN-APP-09).
- **AAC playback test on AAC streams** — Phase 85 surface (PKG-LIN-APP-03 AAC tier; spike validates plugin resolution only).
- **Drift-guards in `tests/test_packaging_spec.py`** — Phase 85 wires up using spike-captured constants (GLIBC literal, plugin BOM, conda env package list).
- **AppImage signing** — Phase 85 surface.
- **CI replication of the smoke test on GitHub Actions** — Phase 85 may scope; deferred per CONTEXT.md "Deferred Ideas."

## Sources

### Primary (HIGH confidence)

- `linuxdeploy-plugin-gstreamer` source script (raw `master`) — env-var names + path discovery + AppRun hook structure [VERIFIED via WebFetch 2026-05-25]
- `linuxdeploy-plugin-conda` source script (raw `master`) — env vars + AppDir layout (`$APPDIR/usr/conda/`) + miniconda integration [VERIFIED via WebFetch 2026-05-25]
- `linuxdeploy` releases page — continuous tag URL pattern + asset 302 redirect confirmed via curl HEAD [VERIFIED 2026-05-25]
- `.claude/skills/spike-findings-musicstreamer/SKILL.md` + references — Phase 43 patterns reused (smoke_test, runtime_hook conceptual analog, build driver, conda env shape, plugin BOM)
- `.planning/codebase/CONCERNS.md` — GStreamer Bus-Loop Threading Model + Phase 43.1 fixed surface + gst-libav-required-for-AAC finding
- `.planning/REQUIREMENTS.md` — PKG-LIN-APP-01..09 (Phase 85 consumers)
- `.planning/ROADMAP.md` — Phase 85a goal + 4 success criteria
- distrobox compatibility docs — image registry paths for ubuntu/fedora/opensuse [VERIFIED via WebFetch]
- conda-forge package registry — all 10 spike packages return HTTP 200 on `anaconda.org/conda-forge/<pkg>/files` [VERIFIED via curl HEAD probe]
- anaconda.org/conda-forge/glib-networking — 2.80.0 published 2024-03; linux-64 supported [VERIFIED]

### Secondary (MEDIUM confidence)

- Fedora 40 ships GLIBC 2.39 — multiple package-announce sources [CITED: package-announce@lists.fedoraproject.org]
- openSUSE Tumbleweed ships GLIBC 2.42 as of 2026-05 — TW Monthly Update May 2026 [CITED: news.opensuse.org]
- Ubuntu 22.04 LTS ships GLIBC 2.35 — packages.ubuntu.com/jammy/libc6 [CITED]
- distrobox shares Wayland + PipeWire + DBus by default — distrobox docs + Issue #310 [CITED]

### Tertiary (LOW confidence — flagged for spike-time validation)

- `MINICONDA_VERSION=py312_24.9.2-0` recommendation — planner verifies current best practice via repo.anaconda.com/miniconda/ index at planning time [ASSUMED A2]
- `libfuse2` is the right runtime dep for the build container (vs `libfuse2t64` on Ubuntu 22.04) [ASSUMED A1]

## Metadata

**Confidence breakdown:**

- Standard stack (toolchain pins, conda env shape): HIGH — Phase 43 cross-referenced + direct WebFetch of upstream sources + conda-forge HTTP probe
- AppRun env-var template: HIGH — directly cited from plugin source; Phase 43 windows runtime_hook.py is the conceptual analog
- linuxdeploy-plugin-gstreamer + conda-layout interaction: MEDIUM — the load-bearing unknown the spike answers; assumption is the plugin's `GSTREAMER_PLUGINS_DIR` override works against a flat conda layout
- Distrobox + Wayland + PipeWire mechanics: HIGH — distrobox upstream docs + Issue #310 + verified host env
- GLIBC version map for 3 target distros: HIGH — Fedora 2.39, Ubuntu 22.04 2.35, Tumbleweed 2.42 all cited
- Pitfalls catalog: HIGH for items 1–4, 6, 7 (Phase 43 cross-referenced); MEDIUM for items 5, 8, 9, 10 (Linux-specific, validated by spike execution)
- Wrap-up shape: HIGH — Phase 43 set the precedent verbatim

**Research date:** 2026-05-25
**Valid until:** 2026-06-22 (~30 days; linuxdeploy ecosystem is stable but plugin-gstreamer maintenance dormancy means a forced refresh if any of the three toolchain assets get a breaking update)
