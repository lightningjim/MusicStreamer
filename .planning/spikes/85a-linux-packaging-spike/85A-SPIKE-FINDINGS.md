# Phase 85a Linux Packaging Spike — Findings

> Spike date: 2026-05-26
> Spike status: **PASS** (with one intentional partial — Plan 07 audible-PASS deferred to Phase 85 for two of three distros per CONTEXT.md D-09 wrap-now policy)
> Phase 85 hand-off readiness: **READY**
> Predecessor spike (Windows analog): Phase 43 — `references/windows-gstreamer-bundling.md` inside the `spike-findings-musicstreamer` skill

---

## Spike Outcome Summary

The Phase 85a Linux packaging spike successfully built a functional AppImage that plays both HTTP and HTTPS SomaFM MP3 streams across the three target distros (Ubuntu 22.04 LTS, Fedora 40, openSUSE Tumbleweed) from a single `ubuntu:22.04` Docker build container, validating the `linuxdeploy + linuxdeploy-plugin-conda + linuxdeploy-plugin-gstreamer + conda-forge` toolchain end-to-end. The four ROADMAP.md success criteria report:

| # | Success criterion | Result | Evidence |
|---|---|---|---|
| 1 | `gst-inspect-1.0 avdec_aac` + `aacparse` resolve from inside AppRun on all 3 distros | **PASS** | Plan 06 transcripts — `SPIKE_DIAG plugin_resolved='avdec_aac' status='ok'` + `plugin_resolved='aacparse' status='ok'` on Ubuntu 22.04 + Fedora 40 + Tumbleweed |
| 2 | GLIBC max ≤ 2.35 | **PASS** | objdump DT_VERNEED scan reports `GLIBC_2.34` on the build host; bundled `usr/conda/bin/python` reports `GLIBC_2.17` inside all 3 distroboxes — well below 2.35 cap |
| 3 | HTTP + HTTPS playback reach `Gst.State.PLAYING` cleanly on all 3 distros | **PASS** | Plan 06 transcripts — `SPIKE_OK time_to_play_s=0.22 played_for_s=35.02` (HTTP) + `SPIKE_OK time_to_play_s=0.37 played_for_s=35.08` (HTTPS, after Pitfall 17 fix) |
| 4 | AppRun env-var template captured + relaunch verified | **PASS** | AppRun template documented in Section 4 below; relaunch empirically 4.7× faster than first launch (Pitfall 3 GST_REGISTRY_FORK=no mitigation conclusively validated — Plan 07) |

The spike surfaced **20 pitfalls** in total: 10 anticipated in RESEARCH.md (Pitfalls 1–10) and **10 NEW pitfalls discovered during execution** (Pitfalls 11–20). All 20 have documented mitigations; Phase 85's PLAN.md must consume this catalog as primary research input (per ROADMAP.md `research_flag: NO` on Phase 85).

The one intentional partial is Plan 07's audible-PASS protocol: only Ubuntu 22.04 was exercised manually before wrap-now per CONTEXT.md D-09 (the surfaced Pitfall 19 would reproduce cross-distro without changing Phase 85's action item). Programmatic playback is GREEN on all 3 distros; the manual-listening loop was descoped after the first distro caught the bug it was designed to catch.

---

## Host Environment

Reproducibility prefix captured at spike-execution time (verbatim from `.planning/spikes/85a-linux-packaging-spike/host-environment.md`):

```
OS:           Ubuntu 26.04 LTS (resolute)
Kernel:       7.0.0-15-generic
GLIBC:        2.43 (host) — bundled conda env's python reports GLIBC_2.17
podman:       5.7.0
docker:       29.5.2, build 79eb04c
distrobox:    1.8.2.4
screenshot:   gnome-screenshot 41.0; grim present (Pitfall 18 — both broken on GNOME 49 Wayland)
session:      wayland-0 wayland ubuntu:GNOME
```

**Phase 85 reproducibility note:** any future rebuild needs the same `distrobox` ≥ 1.8.2.4 (older versions lack `--unshare-devsys`; see Pitfall-grade Plan 06 deviation table) and the same rootless `podman` (distrobox auto-selects podman over docker when both are present).

---

## Toolchain Pins

Three SHA256-pinned raw-GitHub assets + one pinned Miniforge3 release. Stored in `pins.env`; drift-verified by `verify-pins.sh` (exits 2 on drift, 0 on match):

| Asset | URL | SHA256 |
|-------|-----|--------|
| linuxdeploy (AppImage) | `https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage` | `f2aa8e8bb6265d0edc0b0c666c494dc8975650af589408748d75c9b99434b570` |
| linuxdeploy-plugin-conda (.sh) | `https://raw.githubusercontent.com/linuxdeploy/linuxdeploy-plugin-conda/master/linuxdeploy-plugin-conda.sh` | `00ab1cb015ec7d97c8278a285fa5025b49c6bf3de1bc0bcf62ec38cfb6e1544a` |
| linuxdeploy-plugin-gstreamer (.sh) | `https://raw.githubusercontent.com/linuxdeploy/linuxdeploy-plugin-gstreamer/master/linuxdeploy-plugin-gstreamer.sh` | `c107b49d84edbffc6ab226ed1007e0626a4f7aa2c3a36b7782bef62351d49e94` |
| Miniforge3 installer | `https://github.com/conda-forge/miniforge/releases/download/26.3.2-2/Miniforge3-26.3.2-2-Linux-x86_64.sh` | `42260ffe3830fb953d5eee1bbb32229ff06aa7c3833c1ed7a9a0420a95685d94` |
| plugin-conda (Approach P patched) | (re-derived from upstream + sed transformation) | `49bf6cddfc2b9c2f70bd80b22ba030621c19532f2bd7df26a40bf624afdbdc26` |

**Raw SHA256 lines (for grep-based drift comparison; identical to table above):**

```
f2aa8e8bb6265d0edc0b0c666c494dc8975650af589408748d75c9b99434b570  linuxdeploy-x86_64.AppImage
00ab1cb015ec7d97c8278a285fa5025b49c6bf3de1bc0bcf62ec38cfb6e1544a  linuxdeploy-plugin-conda.sh
c107b49d84edbffc6ab226ed1007e0626a4f7aa2c3a36b7782bef62351d49e94  linuxdeploy-plugin-gstreamer.sh
42260ffe3830fb953d5eee1bbb32229ff06aa7c3833c1ed7a9a0420a95685d94  Miniforge3-26.3.2-2-Linux-x86_64.sh
49bf6cddfc2b9c2f70bd80b22ba030621c19532f2bd7df26a40bf624afdbdc26  linuxdeploy-plugin-conda.sh (Approach P patched)
```

**Miniconda → Miniforge swap rationale (Pitfall 13/13b):** plugin-conda hardcodes the Miniconda3-latest installer URL; Miniconda3's base condarc declares Anaconda `defaults` channels and trips conda 24.x's ToS gate on channel **presence** (not use), so `CONDA_CHANNELS=conda-forge` does NOT neutralize it. Approach P swaps the URL via deterministic sed and re-verifies the patched SHA — see Pitfall 13/13b below.

**Base Docker image:** `FROM ubuntu:22.04` (locked by success criterion #2 GLIBC ≤ 2.35). NOT pinned at `@sha256:<digest>` at authorship time per Plan 02 decision (kept Dockerfile readable; digest captured in build.log on first pull).

**Conda-forge package set** (11 packages, `environment-spike.yml`):

```yaml
channels: [conda-forge]   # channel-only; no defaults, no nodefaults — Phase 43 stack lock
dependencies:
  - python=3.12             # only version-pinned package
  - pyside6
  - pygobject
  - gst-python              # Linux-specific addition (Pitfall 7)
  - gstreamer
  - gst-plugins-base
  - gst-plugins-good
  - gst-plugins-bad
  - gst-plugins-ugly
  - gst-libav               # Linux-specific addition (Pitfall 7) — AAC/H.264 decoders
  - glib-networking         # Linux-specific addition (Pitfall 7) — TLS modules for HTTPS
```

Resolver picked: Python 3.12.13, PySide6 6.11.1, GStreamer 1.28.3 (final build = `503 MB` AppImage with 188 plugin `.so` files).

---

## The Validated Build Pipeline

ASCII overview of the build flow that produced the working AppImage (per Plan 05 `build.sh`):

```
pins.env  (3 toolchain SHA256s + Miniforge3 tag + patched plugin-conda SHA)
   |
   v
verify-pins.sh   (drift-guard; exit 2 on hash mismatch — fail-fast before any download work)
   |
   v
docker build  ubuntu:22.04   +   apt(libfuse2, patchelf, binutils, ca-certificates,
                                       curl, wget, bzip2, file, desktop-file-utils)
   |
   v
docker run --network=host --user $(id -u):$(id -g) --privileged
            -e CONDA_FETCH_THREADS=1 -e CONDA_CHANNELS=conda-forge
            -e CONDA_PACKAGES="python=3.12;pyside6;pygobject;gst-python;..." (Pitfall 8)
            -e CONDA_SKIP_CLEANUP=strip (Pitfall 15)
            -e LD_LIBRARY_PATH="$APPDIR/usr/conda/lib:..." (Pitfall 14)
            -e GSTREAMER_PLUGINS_DIR="$APPDIR/usr/conda/lib/gstreamer-1.0" (Pitfall 2)
            -e GSTREAMER_HELPERS_DIR="$APPDIR/usr/conda/libexec/gstreamer-1.0" (Pitfall 2)
   |
   |---> sed-patch plugin-conda Miniconda3 URL -> Miniforge3 (Approach P; Pitfall 13/13b)
   |
   v
./linuxdeploy.AppImage --appimage-extract-and-run  (Pitfall 11; FUSE escape for rootless container)
        --appdir AppDir/
        --executable hello_world.py
        --desktop-file desktop/musicstreamer-spike.desktop
        --icon-file desktop/musicstreamer-spike.svg
        --plugin conda
        --plugin gstreamer
   |
   |---> plugin-conda: Miniforge3 installer -> conda env -> $APPDIR/usr/conda/
   |---> plugin-gstreamer: discover plugins via $GSTREAMER_PLUGINS_DIR -> wire scanner + apprun-hook
   |---> linuxdeploy: walk DT_NEEDED, copy AppRun template, assemble AppImage
   |
   v
host-side: extract AppImage -> objdump -T DT_VERNEED -> sort -V GLIBC_* (Pitfall 16)
            FAIL if > GLIBC_2.35
   |
   v
artifacts/MusicStreamer-spike-x86_64.AppImage  (503 MB, GLIBC_2.34, 188 plugins)
```

**Why each `docker run` flag is load-bearing:**
- `--network=host` — defeats Docker bridge MTU + parallel conda fetch SSL errors (Pitfall 12)
- `--user $(id -u):$(id -g)` — produces host-owned artifacts (no root residue)
- `--privileged` — required for the `--appimage-extract-and-run` FUSE escape (rootless container; Pitfall 11)
- `-e CONDA_FETCH_THREADS=1` — serializes conda downloads (Pitfall 12)
- `-e CONDA_SKIP_CLEANUP=strip` — opt-out of plugin-conda's strip pass (Pitfall 15; ubuntu:22.04 binutils 2.38 strip segfaults on newer conda-forge .so files like OpenVINO 2026.x, absl 2601.x)

---

## AppRun Template — Annotated

The spike's **PRIMARY DELIVERABLE**: the AppRun env-var template Phase 85 copies verbatim and adapts only the final `exec` line. Reproduced here in full with line-by-line rationale.

```bash
#!/bin/bash
# Phase 85a spike AppRun template — PRIMARY DELIVERABLE.
#
# CRITICAL: GST_REGISTRY_FORK="no" is NOT the same flag as
# GST_REGISTRY_REUSE_PLUGIN_SCANNER="no" (see Pitfall 3 below).
#
# CRITICAL: GIO_EXTRA_MODULES is required for HTTPS support (Pitfall 4).
#
# CRITICAL: SSL_CERT_FILE is required for HTTPS cert validation (Pitfall 17 —
# spike-discovered; not in RESEARCH.md).
#
# Path layout: ALL GST_* paths point under ${APPDIR}/usr/conda/ — the
# linuxdeploy-plugin-conda layout — NOT ${APPDIR}/usr/lib/ (Pitfall 2).

HERE="$(dirname "$(readlink -f "${0}")")"
export APPDIR="${HERE}"

# --- GStreamer env: bundle paths win over any ambient env --------------------
export GST_PLUGIN_SYSTEM_PATH_1_0="${APPDIR}/usr/conda/lib/gstreamer-1.0"
export GST_PLUGIN_PATH_1_0="${APPDIR}/usr/conda/lib/gstreamer-1.0"
export GST_PLUGIN_SCANNER="${APPDIR}/usr/conda/libexec/gstreamer-1.0/gst-plugin-scanner"
export GST_PLUGIN_SCANNER_1_0="${APPDIR}/usr/conda/libexec/gstreamer-1.0/gst-plugin-scanner"

# Pitfall 3 mitigation — disable fork-then-scan so the cached registry IS
# reused on the second launch (D-06 relaunch protocol).
# NOT to be confused with GST_REGISTRY_REUSE_PLUGIN_SCANNER (different flag;
# plugin-gstreamer sets that one, which does NOT prevent registry rebuild).
export GST_REGISTRY_FORK="no"

# --- GIO TLS backend (HTTPS via souphttpsrc) ---------------------------------
# Pitfall 4 mitigation. conda-forge `glib-networking` ships TLS module(s) here.
export GIO_EXTRA_MODULES="${APPDIR}/usr/conda/lib/gio/modules"

# Pitfall 17 mitigation (spike-discovered) — bundled OpenSSL's default trust
# store search path doesn't include the conda env's CA bundle. Without this,
# HTTPS playback fails with "Unacceptable TLS certificate" even though the TLS
# backend itself loads correctly (--assert-tls passes). conda-forge's
# `ca-certificates` package ships the bundle at this path.
export SSL_CERT_FILE="${APPDIR}/usr/conda/ssl/cacert.pem"

# --- GI typelibs (PyGObject introspection) -----------------------------------
export GI_TYPELIB_PATH="${APPDIR}/usr/conda/lib/girepository-1.0"

# --- Python: use the bundled conda interpreter -------------------------------
export PYTHONHOME="${APPDIR}/usr/conda"
export PATH="${APPDIR}/usr/conda/bin:${PATH}"

# --- Launch the app ----------------------------------------------------------
# In the spike, "the app" is hello_world.py with a SomaFM URL forwarded from
# the caller. Phase 85 replaces this line with:
#     exec "${APPDIR}/usr/conda/bin/python" -m musicstreamer "$@"
exec "${APPDIR}/usr/conda/bin/python" "${APPDIR}/hello_world.py" "$@"
```

**Per-export rationale:**

| Export | Mitigates | Why |
|---|---|---|
| `APPDIR` | (standard) | Resolved via `readlink -f` to follow symlinks; all subsequent paths use it as root |
| `GST_PLUGIN_SYSTEM_PATH_1_0` | Pitfall 2 | Overrides plugin-gstreamer's default multiarch path (`/usr/lib/x86_64-linux-gnu/gstreamer-1.0`) which doesn't exist in the conda layout |
| `GST_PLUGIN_PATH_1_0` | Pitfall 2 | Belt-and-suspenders on top of `GST_PLUGIN_SYSTEM_PATH_1_0` |
| `GST_PLUGIN_SCANNER` (no suffix) | (defensive) | GStreamer 1.24/1.26 honored this spelling |
| `GST_PLUGIN_SCANNER_1_0` (with suffix) | (defensive — Open Q2) | GStreamer 1.28+ may honor either spelling; both are set so neither code path silently breaks |
| `GST_REGISTRY_FORK=no` | **Pitfall 3** | Disables fork-then-scan; registry IS reused on second launch. **DISTINCT from `GST_REGISTRY_REUSE_PLUGIN_SCANNER=no`** which plugin-gstreamer's apprun-hook sets and which does NOT prevent registry rebuild. Plan 07 empirically verified: relaunch 4.7× faster than first launch (1.636s → 0.345s). |
| `GIO_EXTRA_MODULES` | **Pitfall 4** | Required for HTTPS — souphttpsrc → `Gio.TlsBackend.get_default()` scans this path for `libgiognutls.so` / `libgioopenssl.so` |
| `SSL_CERT_FILE` | **Pitfall 17** (spike-discovered) | OpenSSL default trust store search path doesn't include conda's CA bundle. TLS backend loads fine without this (Plan 06 `--assert-tls` passed) but HTTPS playback fails with `Unacceptable TLS certificate`. Spike caught this only because Plan 06 ran end-to-end HTTPS streaming, not just TLS-backend assertion. |
| `GI_TYPELIB_PATH` | (correctness) | PyGObject introspection needs the bundled typelibs; without this `gi.require_version` works but `from gi.repository import X` fails intermittently |
| `PYTHONHOME` | (correctness) | Bundled Python sees its own stdlib + site-packages rather than the host's (which may not exist or may be wrong version) |
| `PATH` prepend | (correctness) | `conda activate` semantic — bundled `bin/` wins over host equivalents |

Phase 43's `runtime_hook.py` is the conceptual Windows analog of this AppRun (sets the same env-var semantics at process start); the cross-reference in `references/windows-gstreamer-bundling.md` shows the Windows side.

---

## Cross-Distro Empirical Evidence (Programmatic)

Plan 06 ran `smoke_test.py` inside each distrobox via `distrobox enter ... --no-tty` with the AppImage extracted via `--appimage-extract` and AppRun env exports applied manually (Pitfall 20 — AppRun's hardcoded `exec ... hello_world.py "$@"` prevents passing `--check-glibc` / `--check-plugins` / etc. through AppRun).

Final state after Pitfall 17 fix was applied and AppImage was rebuilt:

| Distro | GLIBC max | avdec_aac | aacparse | TLS backend | HTTP playback | HTTPS playback | Elected sink |
|---|---|---|---|---|---|---|---|
| ms-spike-ubuntu22 (Ubuntu 22.04.5 LTS jammy) | `GLIBC_2.17` | ok | ok | `GTlsBackendOpenssl` + has_default_database=True | SPIKE_OK 35.02s | SPIKE_OK 35.08s | autoaudiosink |
| ms-spike-fedora40 (Fedora Linux 40 Container Image) | `GLIBC_2.17` | ok | ok | `GTlsBackendOpenssl` + has_default_database=True | SPIKE_OK 35.05s | SPIKE_OK 35.08s | autoaudiosink |
| ms-spike-tumbleweed (openSUSE Tumbleweed 20260524) | `GLIBC_2.17` | ok | ok | `GTlsBackendOpenssl` + has_default_database=True | SPIKE_OK 35.02s | SPIKE_OK 35.07s | autoaudiosink |

GLIBC ceiling of 2.17 on all three is far below the 2.35 cap. All three distros see identical GLIBC + TLS + plugin paths because the bundled `usr/conda/bin/python` is the same blob; the per-distro variability lives at the host-kernel + container-userspace boundary (D-02 single-host caveat acknowledged).

Plugin BOM: 188 plugin `.so` files at `${APPDIR}/usr/conda/lib/gstreamer-1.0/` — Phase 85's `tools/check_bundle_plugins_linux.py` drift-guard consumes this list as its assertion baseline.

**Transcript excerpt (Ubuntu 22.04 — same shape on Fedora 40 + Tumbleweed):**

```
SPIKE_DIAG glibc_max='GLIBC_2.17' path='/tmp/ms-spike-qf4GFF/squashfs-root/usr/conda/bin/python'
SPIKE_DIAG plugin_resolved='avdec_aac' status='ok'
SPIKE_DIAG plugin_resolved='aacparse' status='ok'
SPIKE_DIAG tls_backend='GTlsBackendOpenssl' has_default_database=True \
    gio_modules='/tmp/ms-spike-qf4GFF/squashfs-root/usr/conda/lib/gio/modules'
SPIKE_DIAG gst_version='GStreamer 1.28.3' plugin_count=189 url_scheme='http'
SPIKE_DIAG event='reached_playing'
SPIKE_DIAG sink_elected='autoaudiosink'
SPIKE_OK url='http://ice1.somafm.com/groovesalad-128-mp3' time_to_play_s=0.22 first_tag_s=0.22 played_for_s=35.02
```

Full per-distro transcripts in `.planning/spikes/85a-linux-packaging-spike/artifacts/{ubuntu22,fedora40,tumbleweed}-transcript.log` (gitignored runtime artifacts; logs preserved on disk for Phase 85 inspection).

### Distro: Ubuntu 22.04 (ms-spike-ubuntu22)

- OS-release: `Ubuntu 22.04.5 LTS` (jammy)
- Programmatic transcript: `artifacts/ubuntu22-transcript.log` (10,913 bytes)
- Wayland screenshot: N/A — Pitfall 18 surfaced
- Audible PASS: `artifacts/audible-pass-log.md` §Ubuntu 22.04 (Pitfall 3 verified; Pitfall 19 surfaced)
- GLIBC max observed: `GLIBC_2.17` (well below 2.35 cap)
- Elected audio sink: `autoaudiosink`
- TLS backend module: `GTlsBackendOpenssl` + has_default_database=True
- HTTP playback: SPIKE_OK time_to_play_s=0.22 played_for_s=35.02
- HTTPS playback: SPIKE_OK time_to_play_s=0.37 played_for_s=35.08 (post-Pitfall-17 fix)
- relaunch_time_to_play_s: 0.345 (vs first launch 1.636; delta -1.291s; Pitfall 3 mitigation PASS — relaunch 4.7× FASTER)
- Notes: Pitfall 18 surfaced (CLI screenshot tools broken on GNOME 49 Wayland); Pitfall 19 surfaced (PipeWire routing non-determinism on re-extracted AppImage).

### Distro: Fedora 40 (ms-spike-fedora40)

- OS-release: `Fedora Linux 40 (Container Image)`
- Programmatic transcript: `artifacts/fedora40-transcript.log` (11,258 bytes)
- Wayland screenshot: N/A — Pitfall 18 + cross-distro descope per wrap-now
- Audible PASS: SKIPPED (wrap-now per CONTEXT.md D-09; cross-distro reproduction of Pitfall 19 not load-bearing for Phase 85 action item)
- GLIBC max observed: `GLIBC_2.17` (well below 2.35 cap)
- Elected audio sink: `autoaudiosink`
- TLS backend module: `GTlsBackendOpenssl` + has_default_database=True
- HTTP playback: SPIKE_OK time_to_play_s=0.22 played_for_s=35.05
- HTTPS playback: SPIKE_OK time_to_play_s=0.37 played_for_s=35.08 (post-Pitfall-17 fix)
- relaunch_time_to_play_s: not exercised (wrap-now)
- Notes: programmatic results identical to Ubuntu (single-host caveat per CONTEXT.md D-02; bundled python is the same blob across distros).

### Distro: openSUSE Tumbleweed (ms-spike-tumbleweed)

- OS-release: `openSUSE Tumbleweed` (20260524)
- Programmatic transcript: `artifacts/tumbleweed-transcript.log` (11,082 bytes)
- Wayland screenshot: N/A — Pitfall 18 + cross-distro descope per wrap-now
- Audible PASS: SKIPPED (same reason as Fedora 40)
- GLIBC max observed: `GLIBC_2.17` (well below 2.35 cap)
- Elected audio sink: `autoaudiosink`
- TLS backend module: `GTlsBackendOpenssl` + has_default_database=True
- HTTP playback: SPIKE_OK time_to_play_s=0.23 played_for_s=35.02
- HTTPS playback: SPIKE_OK time_to_play_s=0.37 played_for_s=35.07 (post-Pitfall-17 fix)
- relaunch_time_to_play_s: not exercised (wrap-now)
- Notes: distrobox-init `setup_zypper` failure on this distro required Plan 06 Tumbleweed-only `--pre-init-hooks` shim (vendor → admin zypp.conf copy); not a runtime concern for the produced AppImage.

---

## Audible-PASS Evidence (Ubuntu 22.04 only — partial per wrap-now)

Plan 07's D-06 audible-PASS protocol exercised the AppImage on the bare host via `--appimage-extract-and-run` against PipeWire. Two distros (Fedora 40, Tumbleweed) were SKIPPED after Pitfall 19 surfaced on Ubuntu — cross-distro reproduction would not change Phase 85's action item.

**Pitfall 3 (GST_REGISTRY_FORK=no) — empirically VERIFIED:**
- Run 1 (fresh `~/.cache/gstreamer-1.0/`): time-to-PLAYING = **1.636s**
- Run 2 (cached registry from run 1): time-to-PLAYING = **0.345s**

Per CONTEXT.md D-06 the negative-pivot trigger was "relaunch ≥ 5s slower than first launch." Observed: **4.7× FASTER**. Mitigation conclusively validated.

**Pitfall 19 — surfaced during audible-PASS:**
Both runs reach pulsesink PLAYING cleanly per GST_DEBUG state-machine traces and exit 0 with `SPIKE_OK`, but **one run was silent and the other audible** (and the pattern flipped between Kyle's sessions — earlier session "first works, second silent"; this session "first silent, second works"). Pipeline is healthy; failure is downstream at the PipeWire/Wireplumber routing layer. See Pitfall 19 below.

**Pitfall 18 — surfaced while attempting to capture screenshots:**
`gnome-screenshot --window` returned errors via fallback X11 path on GNOME 49 Wayland; `grim` not applicable to GNOME (Mutter, not wlroots). Only the GNOME Screenshot UI portal works reliably and is non-scriptable. CLI screenshot capture descoped from spike; documented as a Phase 85 production-CI issue. See Pitfall 18 below.

Full Ubuntu 22.04 audible log in `.planning/spikes/85a-linux-packaging-spike/artifacts/audible-pass-log.md` (Fedora 40 + Tumbleweed sections marked SKIPPED).

---

## Pitfalls Catalog (1–20)

Twenty pitfalls total: 10 anticipated in RESEARCH.md and 10 NEW pitfalls discovered during spike execution. Each entry: name + class, what it is, how it manifests, mitigation applied in this spike, Phase 85 action item.

---

### Pitfall 1 — GLIBC baseline drift (success criterion #2)

**Class:** Toolchain / compile-time portability.
**What:** AppImage built on a newer-glibc host links against `GLIBC_2.39+`; refuses to load on Ubuntu 22.04 LTS users with `version 'GLIBC_2.39' not found`.
**Manifests:** `objdump -T <bundled .so> | grep GLIBC_` reports any version > 2.35.
**Mitigation applied:** Build inside `FROM ubuntu:22.04` Docker container; conda-forge binaries themselves built against CentOS 7-era manylinux glibc baseline. Final bundle reports `GLIBC_2.34` via objdump DT_VERNEED scan (well below 2.35 cap).
**Negative-pivot trigger:** STOP and report if GLIBC scan reports > 2.35.
**Phase 85 action:** Inherit `FROM ubuntu:22.04` verbatim; wire the GLIBC literal `GLIBC_2.35` into `tests/test_packaging_spec.py` source-grep (PKG-LIN-APP-08).

---

### Pitfall 2 — `linuxdeploy-plugin-gstreamer` defaults to multiarch system paths

**Class:** Plugin-discovery / build-time.
**What:** `linuxdeploy-plugin-gstreamer` discovers plugins via `/usr/lib/x86_64-linux-gnu/gstreamer-1.0` by default. Conda's flat layout (`$APPDIR/usr/conda/lib/gstreamer-1.0`) is invisible.
**Manifests:** `./linuxdeploy --plugin gstreamer` runs, exits 0, but the produced AppDir's `gstreamer-1.0/` is empty or stale; `gst-inspect-1.0 avdec_aac` fails inside AppRun.
**Mitigation applied:** `build.sh` exports `GSTREAMER_PLUGINS_DIR=$APPDIR/usr/conda/lib/gstreamer-1.0` and `GSTREAMER_HELPERS_DIR=$APPDIR/usr/conda/libexec/gstreamer-1.0` BEFORE invoking `./linuxdeploy --plugin gstreamer`. AppRun re-asserts `GST_PLUGIN_SYSTEM_PATH_1_0` to the same path at runtime.
**Negative-pivot trigger:** STOP and report if `gst-inspect-1.0 avdec_aac` still fails after redirect env vars are applied.
**Phase 85 action:** Inherit both env-var exports verbatim from spike's `build.sh`. Document as the "build vs runtime: both need the hint" pattern.

---

### Pitfall 3 — `GST_REGISTRY_FORK` flag spelling (success criterion #4 + D-06 relaunch)

**Class:** Runtime / env-var spelling.
**What:** `GST_REGISTRY_FORK=no` (disables fork-then-scan; registry IS reused on second launch) and `GST_REGISTRY_REUSE_PLUGIN_SCANNER=no` (disables scanner-process pool; does NOT prevent registry rebuild) are **two different flags**. `linuxdeploy-plugin-gstreamer`'s generated apprun-hook sets the latter (plugin source line 17). The CONTEXT.md spec calls for the former.
**Manifests:** Second launch takes 5–30s longer than first launch because plugin registry is rebuilt from scratch.
**Mitigation applied:** AppRun template exports `GST_REGISTRY_FORK="no"` explicitly AFTER the plugin's hook would have been sourced. Comment block on the AppRun documents the distinction.
**Empirically verified:** Plan 07 relaunch was 4.7× FASTER than first launch (1.636s → 0.345s; well within negative-pivot trigger of "≥5s slower").
**Negative-pivot trigger:** STOP and report if second launch consistently regresses time-to-PLAYING by ≥5s after both flags are set.
**Phase 85 action:** Inherit AppRun template verbatim. Add a regression test that exercises relaunch and asserts `relaunch_time_to_play_s < first_launch_time_to_play_s + 5`.

---

### Pitfall 4 — HTTPS silently fails without `GIO_EXTRA_MODULES`

**Class:** Runtime / TLS bundling.
**What:** `souphttpsrc` looks up TLS backend via `Gio.TlsBackend.get_default()` which scans `$GIO_EXTRA_MODULES`. Without it, HTTPS streams fail with `"TLS/SSL support not available; install glib-networking"` even though glib-networking IS bundled.
**Manifests:** HTTP plays; HTTPS hangs or errors; `smoke_test.py --assert-tls` returns False.
**Mitigation applied:** AppRun exports `GIO_EXTRA_MODULES=${APPDIR}/usr/conda/lib/gio/modules`. Mirrors Phase 43 Windows `runtime_hook.py` lines 24–27.
**Negative-pivot trigger:** STOP and report if HTTPS still fails after `GIO_EXTRA_MODULES` is set correctly.
**Phase 85 action:** Inherit `GIO_EXTRA_MODULES` export verbatim. Add a TLS-backend probe to `tests/test_packaging_linux_smoke.py`.

---

### Pitfall 5 — Distrobox passes Wayland + PipeWire but not GTK/Qt theme assets

**Class:** Test-infrastructure / cosmetic.
**What:** distrobox shares Wayland socket + PipeWire socket + DBus session bus + `$HOME` by default but does NOT mount the host's `/usr/share/themes`, `/usr/share/icons`, or distro-specific Qt platform plugins.
**Manifests:** AppImage window renders with default Adwaita-fallback theme; missing host accent colors / fonts / icon theme.
**Mitigation applied:** Accept for spike (RESEARCH.md says this is a known limitation, not a failure). Programmatic transcripts (Plan 06) carry the load-bearing evidence; theme drift is non-functional.
**Negative-pivot trigger:** None (cosmetic; not a stopper).
**Phase 85 action:** Production AppImage may use `--filesystem=host`-equivalent or bundle Adwaita theme assets if pixel-fidelity matters. Out of spike scope.

---

### Pitfall 6 — `MINICONDA_VERSION` defaults to "latest" (non-reproducible build)

**Class:** Supply-chain / reproducibility.
**What:** `linuxdeploy-plugin-conda` downloads `Miniconda3-latest-Linux-x86_64.sh` by default; "latest" rolls month-to-month.
**Manifests:** Re-running `build.sh` produces different SHA256 between runs without source changes.
**Mitigation applied:** Pinned `MINIFORGE_TAG=26.3.2-2` in `pins.env` with full URL + SHA256. (Note: Pitfall 13/13b forced Miniforge over Miniconda regardless; Pitfall 6 mitigation folds into Approach P.)
**Negative-pivot trigger:** None (documented version is the working version).
**Phase 85 action:** Inherit Miniforge pin; bump deliberately (not via "latest" symlink).

---

### Pitfall 7 — Phase 43 Windows conda env shape diverges on Linux

**Class:** Cross-platform / plugin BOM.
**What:** Linux conda-forge needs three packages Windows didn't explicitly require: `gst-libav` (AAC/H.264 decoders on Linux), `gst-python` (PyGObject GStreamer bindings on Linux), `glib-networking` (TLS modules explicit).
**Manifests:** Without `gst-libav`, `avdec_aac` fails to resolve on Linux even though it worked on Windows from `gst-plugins-bad`.
**Mitigation applied:** `environment-spike.yml` explicitly lists all three (lines 9–11). Final BOM = 188 plugins.
**Negative-pivot trigger:** STOP and report if `gst-inspect-1.0 avdec_aac` resolves on Windows AppImage but not on Linux AppImage with the same conda env shape.
**Phase 85 action:** Cross-link to `references/windows-gstreamer-bundling.md` (Phase 43 skill) in `tools/check_bundle_plugins_linux.py` to keep the Linux/Windows plugin-set delta documented.

---

### Pitfall 8 — `linuxdeploy-plugin-gstreamer` maintenance dormancy

**Class:** Supply-chain / upstream-risk.
**What:** Plugin last touched March 2024; only 5 stars, 12 forks, 7 open issues.
**Manifests:** If upstream linuxdeploy makes a breaking ABI change to the plugin interface, the plugin breaks silently and is unlikely to be patched quickly.
**Mitigation applied:** SHA256-pinned at first download (`pins.env`). Kyle's 2026-05-26 observation softens the concern: "the plugins are old because just looking at them it was future-proofed anyways (variable for the version of gstreamer for example)" — the dormant scripts parameterize over downstream tool versions, so dormancy reads as "stable interface, mature implementation" rather than "abandoned." Supply-chain pin remains the primary mitigation regardless.
**Negative-pivot trigger:** STOP and report if `./linuxdeploy --plugin gstreamer` exits non-zero with `"unknown plugin command"` or similar against current linuxdeploy.
**Phase 85 action:** Maintain SHA256 pin. Long-term, consider vendoring the plugin script in-repo with its own pinned SHA, or hand-rolling the ~30 lines of bash the plugin actually does (apprun-hook + scanner placement + plugin tree walk).

---

### Pitfall 9 — SomaFM ICY metadata parser surprise

**Class:** Streaming protocol / smoke-test design.
**What:** SomaFM streams advertise `Icy-MetaInt: 16000` and embed `StreamTitle='...'` between audio chunks. If `playbin3` doesn't surface `GST_TAG_TITLE` to the message bus, smoke_test passes audible playback but the findings transcript lacks ICY confirmation.
**Manifests:** Stream plays audibly but smoke_test reports `first_tag_arrived=None` and exits with code 3.
**Mitigation applied:** `smoke_test.py` records `first_tag_s` separately from `time_to_play_s` and reports both. Empirical: TAG arrived within 0.22s on all three distros (transcript: `first_tag_s=0.22`).
**Negative-pivot trigger:** None (falls back to bus-level STATE_CHANGED→PLAYING assertion).
**Phase 85 action:** Inherit `_on_message` TAG-event timestamp pattern.

---

### Pitfall 10 — PipeWire vs PulseAudio sink election

**Class:** Audio routing.
**What:** GStreamer's `autoaudiosink` is a rankings-based picker. Inside an AppImage that lacks all host audio-routing daemons, autoaudiosink may pick `alsasink` (Tumbleweed without pulse-compat) instead of `pulsesink`.
**Manifests:** Audible playback on Ubuntu, silent on Tumbleweed; smoke_test's elected-sink log shows `alsasink`.
**Mitigation applied:** smoke_test.py logs `sink_elected=<name>` via best-effort `pipeline.get_property("audio-sink")` + `iterate_recurse()` looking for a Sink-class factory. All three distros elected `autoaudiosink` (no per-distro divergence under `--unshare-devsys`; container's `/dev` is its own ephemeral mount, host audio devices not visible through `/dev/snd/*`, audio routes via PipeWire socket at `$XDG_RUNTIME_DIR/pipewire-0` instead).
**Negative-pivot trigger:** STOP and report if audible-PASS fails on one distro but works on another with the same AppImage.
**Phase 85 action:** Inherit the sink-election logging in production smoke test. Note that Pitfall 19 supersedes this for the per-host non-determinism problem.

---

### Pitfall 11 — FUSE-mount fails in rootless container (Plan 05 round 1; spike-discovered)

**Class:** Container runtime / build-time.
**What:** `docker run --user $(id -u):$(id -g)` cannot use setuid FUSE; AppImage runtime aborts with `"fuse: device not found"` or `"fusermount: failed to setup"`.
**Manifests:** Plan 05 round 1 — `./linuxdeploy.AppImage --appdir AppDir/...` failed immediately.
**Mitigation applied:** Pass `--appimage-extract-and-run` flag to linuxdeploy.AppImage. Unpacks to a tempdir and execs the inner binary directly. Documented escape hatch.
**Negative-pivot trigger:** None (auto-recoverable).
**Phase 85 action:** CI containers always use `--appimage-extract-and-run` for the linuxdeploy invocation. The PRODUCED AppImage inherits the same FUSE constraint when consumed in CI — downstream CI users also need the flag. Document in README.

---

### Pitfall 12 — Docker bridge + parallel conda fetch = intermittent SSL errors (Plan 05 round 3; spike-discovered)

**Class:** Network / build-time flakiness.
**What:** Mid-fetch `CondaSSLError: Error encountered during SSL/TLS record-layer write` on multi-MB conda-forge tarballs (qt6-main, libllvm22, etc.). Docker bridge MTU + parallel HTTPS = packet loss.
**Manifests:** Plan 05 round 3 — build aborts mid-conda-fetch with SSL record-layer error on a different tarball each retry.
**Mitigation applied:** Both `--network=host` (bypass Docker bridge MTU/proxy) AND `CONDA_FETCH_THREADS=1` (serialize downloads via env-var override of condarc) in `docker run`.
**Negative-pivot trigger:** None (auto-recoverable with both fixes).
**Phase 85 action:** Inherit both flags. Alternative: build natively on host (loses ubuntu:22.04 GLIBC ≤ 2.35 baseline if host is newer — not viable for this project).

---

### Pitfall 13 — Miniconda3 base condarc trips conda 24.x ToS gate (Plan 05 round 4; spike-discovered)

**Class:** Toolchain / licensing-gate.
**What:** Miniconda3 24.x base condarc declares Anaconda `defaults` channels (pkgs/main + pkgs/r). conda 24.x's ToS gate trips on channel **presence**, not channel usage — so `CONDA_CHANNELS=conda-forge` does NOT neutralize it. Install aborts asking for ToS acceptance.
**Manifests:** Plan 05 round 4 — `conda install` aborts with `CondaToSMissingError: Terms of Service have not been accepted for the following channels...`.
**Mitigation applied:** Approach P — sed-patch plugin-conda's hardcoded Miniconda3 URL to Miniforge3 (conda-forge-only base, no ToS). See Pitfall 13b for why the documented `CONDA_DOWNLOAD_DIR` override doesn't work.
**Negative-pivot trigger:** None (auto-recoverable via Approach P).
**Phase 85 action:** Inherit Approach P (or vendor patched plugin-conda fork). Re-derive patched SHA from upstream + the documented sed transformation on every plugin-conda upstream bump.

---

### Pitfall 13b — `CONDA_DOWNLOAD_DIR` override defeated by plugin-conda's `touch -d '@0' + wget -N` (Plan 05 round 5; spike-discovered)

**Class:** Toolchain / plugin internals.
**What:** plugin-conda's documented `CONDA_DOWNLOAD_DIR` hook for pre-staging the Miniconda installer is useless: line 125 of pinned plugin runs `touch -d '@0' Miniconda3-...` then `wget -N`, forcing re-download regardless of cached mtime.
**Manifests:** Plan 05 round 5 — even with `CONDA_DOWNLOAD_DIR` pointing at a pre-fetched Miniforge3 installer, plugin re-downloaded Miniconda3 and tripped Pitfall 13 anyway.
**Mitigation applied:** Approach P (sed-patch the URL inside the plugin script before invoking it; capture patched SHA in `pins.env` as `LINUXDEPLOY_PLUGIN_CONDA_PATCHED_SHA256`).
**Negative-pivot trigger:** None (auto-recoverable).
**Phase 85 action:** Inherit Approach P. Re-derive patched SHA per upstream plugin-conda bump (or vendor a fork).

---

### Pitfall 14 — `LD_LIBRARY_PATH` required for linuxdeploy's ELF dep walker (Plan 05 round 6; spike-discovered)

**Class:** Build-time / linker.
**What:** linuxdeploy walks every `.so` in the AppDir at invocation time and resolves DT_NEEDED entries via standard library search (`/etc/ld.so.cache`, `/usr/lib`, `/usr/lib/x86_64-linux-gnu`, `LD_LIBRARY_PATH`, `AppDir/usr/lib`). The conda layout puts all GStreamer libs at `$APPDIR/usr/conda/lib/` — NOT in any default search path. linuxdeploy fails with `Could not find dependency: libgstbase-1.0.so.0` even though the lib is sitting in the AppDir.
**Manifests:** Plan 05 round 6 — linuxdeploy aborted with `Could not find dependency: libgstbase-1.0.so.0`.
**Mitigation applied:** `export LD_LIBRARY_PATH="$APPDIR/usr/conda/lib:$APPDIR/usr/conda/lib/gstreamer-1.0:${LD_LIBRARY_PATH:-}"` BEFORE invoking linuxdeploy. AppRun handles the same at runtime via its env exports.
**Negative-pivot trigger:** None (auto-recoverable).
**Phase 85 action:** Inherit the `LD_LIBRARY_PATH` export. Document as the "build vs runtime: both need the hint" pattern (mirrors Pitfall 2 shape).

---

### Pitfall 15 — ubuntu:22.04 binutils 2.38 `strip` segfaults on newer conda-forge `.so` (Plan 05 round 7; spike-discovered)

**Class:** Toolchain / cross-version compatibility.
**What:** During plugin-conda cleanup-strip pass on newer conda-forge `.so` files (OpenVINO ~2026.0.0, absl ~2601.0.0, etc.), ubuntu:22.04's binutils 2.38 `strip` segfaults.
**Manifests:** Plan 05 round 7 — strip segfault aborts plugin-conda mid-cleanup.
**Mitigation applied:** `CONDA_SKIP_CLEANUP=strip` (documented plugin-conda opt-out). Trade-off: larger AppImage (~503 MB vs ~400 MB stripped). Conda-forge tarballs ship pre-stripped already, so cost is mostly cosmetic.
**Negative-pivot trigger:** None (auto-recoverable).
**Phase 85 action:** Either (a) accept `CONDA_SKIP_CLEANUP=strip` (spike's choice — keeps GLIBC 2.35 baseline), OR (b) upgrade base to ubuntu:24.04 with binutils 2.42 (pushes GLIBC baseline to 2.39 — Pitfall 1 regression, fewer distros supported). Spike's call: ship larger but more-portable AppImage.

---

### Pitfall 16 — `strings | grep ^GLIBC_` false positives on compressed squashfs (Plan 05 round 8; spike-discovered)

**Class:** Verification / scanning hygiene.
**What:** `strings` on the AppImage payload (zstd-compressed squashfs blob) matches symbol-version-shaped strings in the COMPRESSED payload that don't correspond to any real linker reference (saw fake `GLIBC_2.147`).
**Manifests:** Plan 05 round 8 — functional AppImage with real ELF symbols topping at `GLIBC_2.17`, but post-build `strings | grep ^GLIBC_ | sort -V | tail -1` returned `GLIBC_2.147` → false `exit 4`.
**Mitigation applied:** Replace strings-grep with objdump-based ELF walk: (1) extract AppImage to temp dir via `--appimage-extract`, (2) walk `.so` and executable files, (3) `objdump -T <file> | grep -oE 'GLIBC_[0-9]+\.[0-9]+' | sort -V -u | tail -1`, (4) case-statement compare. Cost: ~10–30s. Eliminates the false-positive class entirely.
**Negative-pivot trigger:** None (auto-recoverable).
**Phase 85 action:** Adopt objdump DT_VERNEED scan as production-grade GLIBC verification. Strings-on-compressed-archive is fundamentally unsafe.

---

### Pitfall 17 — Bundled OpenSSL trust store doesn't include conda's CA bundle (post-Plan-06 debug; spike-discovered)

**Class:** Runtime / TLS cert validation.
**What:** Bundled OpenSSL's default trust-store search path doesn't include the conda env's `cacert.pem`. TLS backend itself loads correctly (`--assert-tls` passes; `has_default_database=True`) but HTTPS playback fails downstream at the libsoup layer with `"Unacceptable TLS certificate"`.
**Manifests:** Plan 06 initial run — all three distros uniformly failed HTTPS with souphttpsrc typefinder error; root-cause-traced to cert validation, not bundle defect (since `--assert-tls` had passed misleadingly). Reproducible on bare host with same extracted AppImage.
**Mitigation applied:** `export SSL_CERT_FILE="${APPDIR}/usr/conda/ssl/cacert.pem"` in AppRun (and in `run-smoke.sh`'s manual env-export block). conda-forge `ca-certificates` package ships the bundle at this path. AppImage now self-contained for cert validation (no host `/etc/ssl/certs/` dependency).
**Re-verified post-fix:** HTTPS playback PASS on Ubuntu 22.04: 35.08s, Fedora 40: 35.08s, Tumbleweed: 35.07s (all `time_to_play_s ≤ 0.37`).
**Negative-pivot trigger:** None (auto-recoverable).
**Phase 85 action:** Inherit `SSL_CERT_FILE` export in AppRun. Add HTTPS playback (not just TLS-backend probe) to `tests/test_packaging_linux_smoke.py` — TLS-backend probe is necessary but not sufficient; only end-to-end HTTPS streaming catches cert-validation issues.

---

### Pitfall 18 — CLI screenshot tools broken on GNOME 49+ Wayland (Plan 07; spike-discovered)

**Class:** Test-infrastructure / desktop integration.
**What:** `gnome-screenshot --window --file ...` returns "command not found" / Wayland portal restriction errors on GNOME 49+ even though apt-installed. `gnome-screenshot --interactive` falls back to X11 path with `Unable to use GNOME Shell's builtin screenshot interface, resorting to fallback X11` + bus errors. `grim` not applicable — GNOME uses Mutter, not wlroots. Only the GNOME Screenshot UI portal (Print Screen key) reliably works, but it's interactive and non-scriptable.
**Manifests:** Plan 07 — multiple CLI screenshot attempts failed; spike-evidence screenshots could not be captured programmatically.
**Mitigation applied:** Descope CLI screenshot capture from spike (transcripts carry programmatic evidence load). Document for Phase 85.
**Negative-pivot trigger:** None (descoped, not a stopper).
**Phase 85 action:** Production CI screenshot capture must use `xdg-desktop-portal-gnome` D-Bus API (`org.freedesktop.portal.Screenshot.Screenshot`) directly. Avoid CLI tools.

---

### Pitfall 19 — PipeWire routing non-determinism for re-extracted AppImage (Plan 07; spike-discovered)

**Class:** Runtime / session-manager routing.
**What:** Each `--appimage-extract-and-run` creates a new `/tmp/appimage_extracted_<random-sha>/` path. PipeWire/Wireplumber identifies apps partly by binary path; new path = new app identity = stale stream-restore state possible. Wireplumber's restore-stream rules depend on previous app-identity records — non-deterministic.
**Manifests:** Plan 07 — both runs from the same AppImage reach pulsesink PLAYING cleanly (GST_DEBUG state-machine traces clean) and exit 0 with `SPIKE_OK`, but one run is silent and the other audible (pattern flips between sessions). Failure is downstream of the GStreamer pipeline.
**Mitigation applied:** Documented for Phase 85; not fixable at the spike's AppRun template surface alone without product-identity decisions.
**Negative-pivot trigger:** None (Plan 07 caught it; cross-distro reproduction descoped per wrap-now since action item is uniform).
**Phase 85 action:** Two-part mitigation: (a) set explicit PipeWire app identity in AppRun — `export PULSE_PROP="application.name=MusicStreamer application.id=org.musicstreamer.app"` (and/or `GST_PIPEWIRE_NODE_NAME="MusicStreamer"`); (b) ship production AppImage with FUSE self-mount (deterministic mount path per content hash, not per-launch random sha). Use `--appimage-extract-and-run` only in CI/containers where FUSE is unavailable.

---

### Pitfall 20 — AppRun's `exec` line hardcoded to `hello_world.py` (Plan 06 Deviation 5; spike-discovered)

**Class:** AppRun template / parameterization.
**What:** Spike's AppRun template ends with `exec "${APPDIR}/usr/conda/bin/python" "${APPDIR}/hello_world.py" "$@"` — anything after `python` is forwarded to hello_world.py, not honored as a script-to-run. Plan 06 couldn't invoke `smoke_test.py` via AppRun and had to do `--appimage-extract` + manual env-export workaround.
**Manifests:** Plan 06 — `./MusicStreamer-spike-x86_64.AppImage --appimage-extract-and-run python smoke_test.py --check-glibc ...` was interpreted as `python smoke_test.py` being argv for hello_world.py; smoke modes returned `SPIKE_FAIL reason='usage'`.
**Mitigation applied:** Documented for Phase 85; the spike's intentional hardcode kept scope tight.
**Negative-pivot trigger:** None.
**Phase 85 action:** Replace AppRun's final exec line with `exec "${APPDIR}/usr/conda/bin/python" -m musicstreamer "$@"`. Or accept the python script as an env var (`exec ... python "${APP_ENTRY:-${APPDIR}/musicstreamer/__main__.py}" "$@"`).

---

### Supplementary mini-pitfalls (Plan 06 distrobox-runtime fixes)

Six additional Plan 06 deviations from the host-runtime environment (NOT in the numbered Pitfalls catalog — these are container-engine integration fixes specific to distrobox 1.8.2.4 + this rig, but Phase 85's CI/test infrastructure will hit the same surface):

| Surface | Fix | Phase 85 action |
|---|---|---|
| distrobox `--volume /dev:/dev:rslave` fails on hosts with VirtualBox USB devices (rootless podman + user-NS can't remap) | `--unshare-devsys` flag in create-distroboxes.sh | Inherit flag in CI distrobox creates |
| distrobox-init `setup_zypper` sed's `/etc/zypp/zypp.conf` (admin path); 2026-05 Tumbleweed ships only `/usr/etc/zypp/zypp.conf` (vendor path) | Tumbleweed-only `--pre-init-hooks "mkdir -p /etc/zypp && cp -p /usr/etc/zypp/zypp.conf /etc/zypp/zypp.conf"` | Inherit hook (or upstream a fix to distrobox-init) |
| Base images for all 3 distros omit `binutils`; smoke_test.py `--check-glibc` needs `strings` | `--additional-packages "binutils"` on distrobox creates | Inherit flag |
| Heredoc body with literal `"` characters terminates outer `bash -c "..."` argument early | Write heredoc body to `mktemp` file, pipe to `bash` via stdin (FD 0) | Pattern documented in run-smoke.sh |
| Cannot pass smoke_test.py args through AppRun (Pitfall 20 surface) | `--appimage-extract` (no `-and-run`) + manual env-export + direct python invocation | Production: parameterize AppRun exec line (Pitfall 20) |
| `strings` on raw AppImage blob matches squashfs noise | `--check-glibc` scans the EXTRACTED `$APPDIR/usr/conda/bin/python` instead | Pattern documented in run-smoke.sh; also `build.sh` uses objdump DT_VERNEED scan (Pitfall 16) |

---

## Open Questions Resolved

| RESEARCH.md Open Q | Status | Answer from spike |
|---|---|---|
| Q1: Does `linuxdeploy-plugin-conda + plugin-gstreamer` end-to-end produce a working AppImage on conda-forge GStreamer 1.28+? | **RESOLVED YES** | Plan 05 round 9: `BUILD_OK` + Plan 06: all 3 distros pass HTTP playback + Plan 07: Ubuntu audible-PASS with relaunch (modulo Pitfall 19). |
| Q2: Does GStreamer 1.28+ honor `GST_PLUGIN_SCANNER` (no suffix) or `GST_PLUGIN_SCANNER_1_0` (with suffix)? | **RESOLVED — set both defensively** | Both spellings exported in AppRun; smoke_test.py logs which one is consumed (spike didn't surface a determinant since both pass; production should keep both exports). |
| Q3: Which TLS backend does conda-forge `glib-networking` ship on linux-64 — gnutls or openssl? | **RESOLVED openssl** | All 3 distros reported `tls_backend='GTlsBackendOpenssl'` (matches Phase 43 Windows 1.28+ which also flipped from gnutls to openssl). |
| Q4: Does `--unshare-devsys` break audio routing via PipeWire? | **RESOLVED NO** | PipeWire socket lives at `$XDG_RUNTIME_DIR/pipewire-0` (separate bind from `/dev`); audio reaches pulsesink PLAYING on all 3 distros even with `/dev` unshared. |
| Q5: Is plugin-conda's `CONDA_DOWNLOAD_DIR` override viable for pre-staging Miniforge3? | **RESOLVED NO** | Pitfall 13b — plugin's `touch -d '@0' + wget -N` defeats cached file; Approach P (sed-patch) is the only viable path. |

---

## Phase 85 Hand-Off Manifest

Numbered actionable items Phase 85's planner consumes verbatim. Each item is a deliverable, not a hand-wave.

### Ready for Phase 85 copy-paste

1. **Copy `build.sh` verbatim** — all 8 in-script mitigations (Pitfalls 1, 2, 8, 11, 12, 13/13b, 14, 15, 16) are production-relevant.
2. **Copy `Dockerfile` verbatim** — `FROM ubuntu:22.04` + `apt-get install --no-install-recommends` set of 7 packages locks GLIBC ≤ 2.35 baseline.
3. **Copy `environment-spike.yml`** — rename to `environment.yml` and ADD MusicStreamer v2.2 deps (`mutagen`, `pillow`, `requests`, `yt-dlp`, `streamlink`, `platformdirs`, `chardet<6`, `nodejs`, the actual `musicstreamer` package). Keep the conda-forge channel-only pin.
4. **Copy `pins.env` + `verify-pins.sh` verbatim** — supply-chain mitigation for raw GitHub `.sh` assets that npm/pip/cargo slopcheck doesn't cover.
5. **Copy AppRun template verbatim**, with two modifications:
   - Replace `exec "${APPDIR}/usr/conda/bin/python" "${APPDIR}/hello_world.py" "$@"` with `exec "${APPDIR}/usr/conda/bin/python" -m musicstreamer "$@"` (Pitfall 20).
   - Add `export PULSE_PROP="application.name=MusicStreamer application.id=org.musicstreamer.app"` (Pitfall 19; before the final exec).
6. **Copy `tools/linux-spike/create-distroboxes.sh` + `run-smoke.sh` + `teardown-distroboxes.sh`** — Phase 85 reruns these for its own cross-distro UAT (containers ephemeral per CONTEXT.md D-04).
7. **Inherit Pitfalls 1–20 catalog as the "Common Pitfalls" research input for Phase 85's PLAN.md** — every pitfall has a documented mitigation; Phase 85's task list either inherits the mitigation or addresses the carry-over.
8. **Wire `GLIBC_2.35` literal into `tests/test_packaging_spec.py` source-grep** (PKG-LIN-APP-08).
9. **Inherit `hello_world.py` shape for `tests/test_packaging_linux_smoke.py`** (if Phase 85 adds it).
10. **Inherit plugin BOM (188 plugins) as the assertion baseline for `tools/check_bundle_plugins_linux.py`** — Linux-equivalent of Phase 43's Windows drift-guard.

### Deliberately left for Phase 85 to figure out

- **Real `musicstreamer/` app bundling** — extending `environment.yml` with the full v2.2 deps, plus pip-installing the local `musicstreamer` package into the bundled conda env.
- **`.desktop` registration + icon + `MIME=audio` integration** — spike used placeholders (`musicstreamer-spike.desktop` + 5-line `musicstreamer-spike.svg`); Phase 85 surface (PKG-LIN-APP-05).
- **Production AppImage should ship with FUSE self-mount** (Pitfall 19); use `--appimage-extract-and-run` only in CI/containers.
- **Investigate plugin-conda env.yml bypass** — this spike used `CONDA_PACKAGES=...` enumeration (Pitfall 8 workaround); Phase 85 may prefer parsing `environment.yml` at build start (Kyle's "future-proof via variable substitution") OR `conda env create -f environment.yml -p $APPDIR/usr/conda` directly + manual linuxdeploy invocation. Option (b) makes the yml the functional input — cleaner source-of-truth.
- **Production CI screenshot capture via `xdg-desktop-portal-gnome` D-Bus API** (Pitfall 18) — avoid CLI tools.
- **Add `docker info` daemon-access probe to `host-environment.md`** — Plan 01 only probed `docker --version` (passes even when daemon is unreachable); a `docker info` probe would have caught a permission/daemon problem earlier.
- **zsync update-info embedding** — Phase 85 surface (PKG-LIN-APP-06).
- **MPRIS2 D-Bus reachability test in the AppImage** — Phase 85 surface (PKG-LIN-APP-07); depends on Phase 91 (FIX-MPRIS).
- **`.pls` / `.m3u` MIME-association NEGATIVE test** — Phase 85 surface (PKG-LIN-APP-09).
- **AAC playback test on AAC streams** — Phase 85 surface (PKG-LIN-APP-03 AAC tier; spike validates plugin resolution only).
- **AppImage signing** — Phase 85 surface.
- **Drift-guards in `tests/test_packaging_spec.py`** — Phase 85 wires up using spike-captured constants (GLIBC literal, plugin BOM, conda env package list).
- **CI replication on GitHub Actions** — Phase 85 may scope; deferred per CONTEXT.md "Deferred Ideas."

---

## The 9-Round Plan 05 Saga

Plan 05 (build driver) took 9 rounds of iteration to reach a green build. Each round surfaced one or more pitfalls; this table is the discovery archaeology for future readers (cross-reference: 85A-05-SUMMARY.md "9-round journey" table).

| Round | Attempted fix | Outcome | Pitfall surfaced |
|---|---|---|---|
| 1 | Initial plan-spec build.sh | linuxdeploy.AppImage FUSE-mount failed in container | **Pitfall 11**: rootless container + setuid FUSE |
| 2 | Add `--appimage-extract-and-run` | conda plugin failed: `CONDA_PACKAGES` empty + plugin doesn't consume `environment.yml` | **Pitfall 8** (re-cast): plugin-conda doesn't honor environment.yml |
| 3 | Enumerate `CONDA_PACKAGES`; add `--user $(id -u):$(id -g)` | Build progressed; conda downloads tripped intermittent SSL errors | **Pitfall 12**: Docker bridge MTU + parallel conda fetch |
| 4 | `--network=host` + `CONDA_FETCH_THREADS=1` | Plugin-conda hit `defaults` channel ToS gate from Miniconda3 condarc | **Pitfall 13**: Miniconda3 base condarc declares Anaconda defaults |
| 5 | Try `CONDA_DOWNLOAD_DIR` hook to pre-stage Miniforge installer | Plugin's `touch -d '@0' + wget -N` forces re-download regardless of cache | **Pitfall 13b**: plugin-conda hook unbypassable |
| 6 | **Approach P**: sed-patch hardcoded Miniconda3 URL → Miniforge3 + re-verify SHA | linuxdeploy couldn't resolve `libgstbase-1.0.so.0` from conda layout | **Pitfall 14**: linuxdeploy ld-search ignores `$APPDIR/usr/conda/lib/` |
| 7 | Export `LD_LIBRARY_PATH=$APPDIR/usr/conda/lib:...` before linuxdeploy | Plugin-conda cleanup-strip pass segfaulted on newer conda .so files | **Pitfall 15**: ubuntu:22.04 binutils 2.38 strip segfault |
| 8 | `CONDA_SKIP_CLEANUP=strip` | **AppImage produced (503 MB).** Functional validations passed. But host-side `strings | grep GLIBC_` returned false `GLIBC_2.147` from squashfs noise → `exit 4` | **Pitfall 16**: strings-grep on compressed payload |
| 9 | **Pitfall 16 fix**: objdump-based DT_VERNEED scan (extract → walk ELFs → objdump → aggregate → sort -V) | **SUCCESS.** `GLIBC_OBJDUMP GLIBC_2.34` + `GLIBC_OK GLIBC_2.34 <= 2.35` + `BUILD_OK` | (none — round 9 is the success state) |

Plan 06 then surfaced Pitfall 17 (post-Plan-06 debug session) and 5 distrobox-runtime mini-pitfalls; Plan 07 surfaced Pitfalls 18 + 19 + 20. Total: 10 RESEARCH.md pitfalls + 10 spike-discovered pitfalls = 20.

---

## Host Environment Captured at Spike Time

Verbatim copy of `.planning/spikes/85a-linux-packaging-spike/host-environment.md` (for findings-doc self-containment):

```
# Phase 85a Host Environment

Captured: 2026-05-26

## OS
$ lsb_release -a
Distributor ID:	Ubuntu
Description:	Ubuntu 26.04 LTS
Release:	26.04
Codename:	resolute

## Kernel
$ uname -r
7.0.0-15-generic

## GLIBC
$ ldd --version | head -1
ldd (Ubuntu GLIBC 2.43-2ubuntu2) 2.43

## podman
$ podman --version
podman version 5.7.0

## docker
$ docker --version
Docker version 29.5.2, build 79eb04c

## distrobox
$ distrobox --version
distrobox: 1.8.2.4

## gnome-screenshot
$ gnome-screenshot --version
gnome-screenshot 41.0

## grim
$ grim -h 2>&1 | head -1
Usage: grim [options...] [output-file]

## Session
$ echo "$WAYLAND_DISPLAY $XDG_SESSION_TYPE $XDG_CURRENT_DESKTOP"
wayland-0 wayland ubuntu:GNOME

## Notes
No fallbacks required — distrobox, gnome-screenshot, and grim all installed cleanly from
Ubuntu 26.04 apt repos.
```

---

## Wrap-Up

- **Findings doc location:** `.planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md` (THIS FILE). Co-located with the spike source tree so `/gsd:spike-wrap-up` packages the directory whole into `.claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/`.
- **Skill APPEND target:** `.claude/skills/spike-findings-musicstreamer/` — appended (not replaced); Phase 43's Windows-bundling entries preserved verbatim.
- **New skill reference file:** `.claude/skills/spike-findings-musicstreamer/references/linux-appimage-bundling.md` (mirrors Phase 43's `windows-gstreamer-bundling.md` shape).
- **SKILL.md `findings_index` updated:** new row "Linux AppImage Bundling | references/linux-appimage-bundling.md | sources/85a-linux-packaging-spike/" appended.
- **SKILL.md `processed_spikes` updated:** new line `- 85a-linux-packaging-spike (Phase 85a; 2026-05-26 — Linux AppImage build via linuxdeploy + conda-forge; 20 pitfalls catalogued)` appended.
- **Distroboxes torn down:** 2026-05-26 — per CONTEXT.md D-04 (containers ephemeral); Phase 85 recreates from `tools/linux-spike/create-distroboxes.sh` for its own UAT.
- **Cross-reference to Phase 43 Windows analog:** `references/windows-gstreamer-bundling.md` documents the cross-platform invariants (`GIO_EXTRA_MODULES`, `GI_TYPELIB_PATH`, plugin scanner placement) that hold on Linux too. The Linux delta is captured in this findings doc + the new `linux-appimage-bundling.md` reference.
