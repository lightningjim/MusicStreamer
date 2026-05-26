# Linux AppImage Bundling (GStreamer + conda-forge)

Validated empirically in Phase 85a on a `ubuntu:22.04` Docker build container,
shipped to Ubuntu 22.04 LTS + Fedora 40 + openSUSE Tumbleweed via distrobox.
Bundle self-containment proved — `MusicStreamer-spike-x86_64.AppImage` (503 MB,
`GLIBC_2.34`, 188 GStreamer plugins) plays HTTP and HTTPS SomaFM streams on all
three distros without any system GStreamer install.

The Linux side mirrors the cross-platform invariants in
`windows-gstreamer-bundling.md` (same `GIO_EXTRA_MODULES` semantic, same need
to keep `GST_PLUGIN_SCANNER` co-located with bundled libs, same conda-forge as
the only viable PyGObject source) and adds Linux-specific patterns for
AppImage assembly, FUSE, distrobox UAT, and supply-chain pinning for raw
GitHub `.sh` assets.

## Validated Patterns

### Use linuxdeploy + plugin-conda + plugin-gstreamer for the assembly layer

```bash
# Toolchain (SHA-pinned in pins.env — see sources/85a-linux-packaging-spike/pins.env)
curl -fsSL -o linuxdeploy.AppImage  "$LINUXDEPLOY_URL"
curl -fsSL -o linuxdeploy-plugin-conda.sh     "$LINUXDEPLOY_PLUGIN_CONDA_URL"
curl -fsSL -o linuxdeploy-plugin-gstreamer.sh "$LINUXDEPLOY_PLUGIN_GSTREAMER_URL"
chmod +x linuxdeploy.AppImage *.sh

# In docker run (--user $(id -u):$(id -g) --privileged --network=host ...):
./linuxdeploy.AppImage --appimage-extract-and-run \
    --appdir AppDir/ \
    --executable hello_world.py \
    --desktop-file desktop/musicstreamer-spike.desktop \
    --icon-file    desktop/musicstreamer-spike.svg \
    --plugin conda \
    --plugin gstreamer \
    --output appimage
```

The two plugins handle ~90% of bundle assembly. Every NEW shell line in
build.sh is a maintenance liability — bias hard toward letting the plugins do
the work.

Confirmed working versions: linuxdeploy continuous (2026-05-26 download),
plugin-conda master (2024-09-07), plugin-gstreamer master (2024-03-01),
Miniforge3 26.3.2-2, Python 3.12.13, PySide6 6.11.1, GStreamer 1.28.3.

### Custom AppRun template is required (sets env that the plugin's hook misses or sets wrong)

The plugin's generated AppRun hook gets the GStreamer paths right but sets
`GST_REGISTRY_REUSE_PLUGIN_SCANNER=no` (wrong flag for our use case) and does
not set `GIO_EXTRA_MODULES` or `SSL_CERT_FILE`. The Phase 85a `AppRun` template
overrides:

```bash
HERE="$(dirname "$(readlink -f "${0}")")"
export APPDIR="${HERE}"

export GST_PLUGIN_SYSTEM_PATH_1_0="${APPDIR}/usr/conda/lib/gstreamer-1.0"
export GST_PLUGIN_PATH_1_0="${APPDIR}/usr/conda/lib/gstreamer-1.0"
export GST_PLUGIN_SCANNER="${APPDIR}/usr/conda/libexec/gstreamer-1.0/gst-plugin-scanner"
export GST_PLUGIN_SCANNER_1_0="${APPDIR}/usr/conda/libexec/gstreamer-1.0/gst-plugin-scanner"
export GST_REGISTRY_FORK="no"              # NOT GST_REGISTRY_REUSE_PLUGIN_SCANNER

export GIO_EXTRA_MODULES="${APPDIR}/usr/conda/lib/gio/modules"          # HTTPS TLS backend
export SSL_CERT_FILE="${APPDIR}/usr/conda/ssl/cacert.pem"               # HTTPS cert validation
export GI_TYPELIB_PATH="${APPDIR}/usr/conda/lib/girepository-1.0"

export PYTHONHOME="${APPDIR}/usr/conda"
export PATH="${APPDIR}/usr/conda/bin:${PATH}"

exec "${APPDIR}/usr/conda/bin/python" -m musicstreamer "$@"
```

Without `GIO_EXTRA_MODULES`, `souphttpsrc` fails HTTPS with "TLS/SSL support
not available; install glib-networking". Without `SSL_CERT_FILE`, HTTPS
playback fails downstream at the libsoup layer with "Unacceptable TLS
certificate" even though the TLS backend itself loads correctly (the spike's
`--assert-tls` probe passed misleadingly while end-to-end HTTPS failed).
Without `GST_REGISTRY_FORK=no`, second launch rebuilds the plugin registry
from scratch — empirically 4.7× slower than first launch on a cached registry
in the Phase 85a Plan 07 measurement.

See `sources/85a-linux-packaging-spike/AppRun` for the full canonical template
(with annotated comments documenting each Pitfall mitigation).

### Bundle layout differs from Phase 43 Windows — all conda files live under `usr/conda/`

`linuxdeploy-plugin-conda` extracts the conda env into `$APPDIR/usr/conda/`.
Plugins live at `$APPDIR/usr/conda/lib/gstreamer-1.0/` (flat, no multiarch
suffix), gio modules at `$APPDIR/usr/conda/lib/gio/modules/`, typelibs at
`$APPDIR/usr/conda/lib/girepository-1.0/`, scanner at
`$APPDIR/usr/conda/libexec/gstreamer-1.0/gst-plugin-scanner`. Same conceptual
shape as the Phase 43 Windows `bin/` + `lib/` + `lib/gstreamer-1.0/`
arrangement, but rooted under `usr/conda/` rather than the AppImage's root.

### Conda env shape on Linux explicitly includes three packages Windows didn't need

```yaml
channels: [conda-forge]   # channel-only; no defaults, no nodefaults
dependencies:
  - python=3.12
  - pyside6
  - pygobject
  - gst-python          # Linux-specific
  - gstreamer
  - gst-plugins-base
  - gst-plugins-good
  - gst-plugins-bad
  - gst-plugins-ugly
  - gst-libav           # Linux-specific — AAC/H.264 decoders
  - glib-networking     # Linux-specific — TLS modules for HTTPS
```

Without `gst-libav`, `avdec_aac` fails to resolve on Linux even though it
worked on Windows from `gst-plugins-bad`. `gst-python` and `glib-networking`
need explicit listing on Linux conda-forge; Windows conda-forge meta-pulled
them in Phase 43.

### Build inside `ubuntu:22.04` Docker container — locks GLIBC baseline

The compile-time GLIBC baseline is set by the build host, not the conda
binaries (conda-forge binaries are themselves built against CentOS-7-era
manylinux glibc). Building inside ubuntu:22.04 (GLIBC 2.35) means any
bash/Python compiled at build time also targets glibc ≤ 2.35. Confirmed:
final AppImage reports `GLIBC_2.34` via `objdump -T` DT_VERNEED scan. Going
newer (ubuntu:24.04, glibc 2.39) cuts off Ubuntu 22.04 LTS users entirely.

### Programmatic cross-distro UAT via distrobox + podman

```bash
distrobox create --name ms-spike-ubuntu22 --image docker.io/library/ubuntu:22.04 \
    --unshare-devsys --additional-packages "binutils"
distrobox create --name ms-spike-fedora40 --image quay.io/fedora/fedora:40 \
    --unshare-devsys --additional-packages "binutils"
distrobox create --name ms-spike-tumbleweed --image registry.opensuse.org/opensuse/tumbleweed:latest \
    --unshare-devsys --additional-packages "binutils" \
    --pre-init-hooks "mkdir -p /etc/zypp && cp -p /usr/etc/zypp/zypp.conf /etc/zypp/zypp.conf"
```

distrobox shares Wayland + PipeWire + DBus + `$HOME` by default — gives real
audible-playback fidelity from a single host. Treat the host kernel + glibc as
fixed (single-host caveat); the userspace under test is the AppImage's own
bundled tree. Tear down per CONTEXT.md D-04 (ephemeral): `distrobox rm` after
UAT.

### Pin raw GitHub `.sh` assets with SHA256-at-first-download

npm/pip/cargo slopcheck does not cover raw GitHub `.sh` assets. Phase 85a's
`pins.env` + `verify-pins.sh` (exit 2 on drift) is the project-specific
mitigation. Capture SHA256 at FIRST download; once captured the hash IS the
pin — any subsequent drift fails the verifier. Plugin-conda and
plugin-gstreamer publish no formal releases; their `master` branch is the
versioning surface.

## Landmines

### `GST_REGISTRY_FORK=no` is NOT the same flag as `GST_REGISTRY_REUSE_PLUGIN_SCANNER=no`

`linuxdeploy-plugin-gstreamer`'s generated AppRun hook sets the LATTER
(`REUSE_PLUGIN_SCANNER`) which disables scanner-process pooling but does NOT
prevent registry rebuild on second launch. The flag you actually want is
`GST_REGISTRY_FORK=no` (disables fork-then-scan; registry IS reused). Set the
correct flag explicitly in your AppRun, AFTER any plugin-generated hook would
have been sourced. Empirically validated on Phase 85a Plan 07: relaunch 4.7×
faster than first launch with the correct flag.

### linuxdeploy-plugin-gstreamer defaults to multiarch system paths

Plugin discovers plugins at `/usr/lib/x86_64-linux-gnu/gstreamer-1.0` by
default — invisible to the conda layout. Export
`GSTREAMER_PLUGINS_DIR=$APPDIR/usr/conda/lib/gstreamer-1.0` and
`GSTREAMER_HELPERS_DIR=$APPDIR/usr/conda/libexec/gstreamer-1.0` BEFORE
invoking `./linuxdeploy --plugin gstreamer`. AppRun re-asserts the same paths
at runtime.

### HTTPS needs three env exports, not one

`GIO_EXTRA_MODULES` makes the TLS backend findable. `SSL_CERT_FILE` makes the
trust store findable. (Optionally, hand-roll `LD_LIBRARY_PATH` if anything
else fails to resolve.) `GIO_EXTRA_MODULES` alone is NOT sufficient — the
spike's `--assert-tls` probe passed (TLS backend loaded) while end-to-end
HTTPS still failed with "Unacceptable TLS certificate" because OpenSSL's
default trust-store search path doesn't include `cacert.pem`. End-to-end
HTTPS playback is the only honest test.

### `--appimage-extract-and-run` is required in rootless containers

`docker run --user $(id -u):$(id -g)` cannot use setuid FUSE; AppImage runtime
aborts. Pass `--appimage-extract-and-run` to linuxdeploy's invocation. The
PRODUCED AppImage inherits the same FUSE constraint when consumed in CI —
downstream CI consumers also need the flag. Production user-facing AppImages
should self-mount via FUSE (deterministic mount path per content hash).

### Miniconda3 trips conda 24.x ToS gate; use Miniforge3 via sed-patch

Miniconda3 24.x base condarc declares Anaconda `defaults` channels.
conda 24.x's ToS gate trips on channel **presence**, not channel usage —
`CONDA_CHANNELS=conda-forge` does NOT neutralize it. plugin-conda hardcodes
the Miniconda3 URL and its `CONDA_DOWNLOAD_DIR` override is defeated by the
plugin's own `touch -d '@0' + wget -N`. Approach P: sed-patch the URL inside
the plugin script before invocation; capture the patched SHA in `pins.env` as
`LINUXDEPLOY_PLUGIN_CONDA_PATCHED_SHA256`. See `sources/85a-linux-packaging-spike/build.sh`
for the deterministic sed transformation.

### plugin-conda does NOT consume environment.yml — enumerate CONDA_PACKAGES

Despite naming, plugin-conda does not parse environment.yml. Pass
`CONDA_PACKAGES="python=3.12;pyside6;pygobject;gst-python;..."` (semicolon-
separated) explicitly. Either keep the list in sync with environment.yml
manually, OR parse environment.yml at build start and synthesize the list,
OR skip plugin-conda entirely with `conda env create -f environment.yml -p
$APPDIR/usr/conda` followed by manual linuxdeploy invocation. Option C is the
cleanest source-of-truth alignment; the spike used Option A for scope-bound
minimal change.

### LD_LIBRARY_PATH must include conda's lib at BUILD time too

linuxdeploy walks DT_NEEDED entries via standard library search. The conda
layout's `usr/conda/lib/` is NOT in default search paths. Export
`LD_LIBRARY_PATH="$APPDIR/usr/conda/lib:$APPDIR/usr/conda/lib/gstreamer-1.0:..."`
BEFORE invoking linuxdeploy. AppRun handles the same hint at runtime. This is
the "build vs runtime: both need the hint" pattern.

### ubuntu:22.04 binutils 2.38 strip segfaults on newer conda-forge .so files

Plugin-conda's cleanup pass calls `strip` on each `.so` after bundling. Newer
conda-forge packages (OpenVINO ~2026.0.0, absl ~2601.0.0) segfault the
ubuntu:22.04 binutils 2.38 `strip`. Set `CONDA_SKIP_CLEANUP=strip` to opt out
of the strip pass. Costs ~100 MB in AppImage size; conda-forge tarballs ship
pre-stripped, so the cost is mostly cosmetic. Upgrading to ubuntu:24.04
(binutils 2.42) would solve this but pushes the GLIBC baseline to 2.39.

### `strings | grep ^GLIBC_` produces false positives on compressed squashfs

The AppImage's zstd-compressed squashfs payload contains symbol-version-shaped
byte sequences that don't correspond to any real linker reference (spike
observed false `GLIBC_2.147`). Use objdump-based DT_VERNEED scan instead:
extract via `--appimage-extract` → walk ELFs (`.so` or `+x`) → `objdump -T`
→ `grep -oE 'GLIBC_[0-9]+\.[0-9]+' | sort -V -u | tail -1`. Cost: ~10–30s on
top of build time. Real GLIBC requirements live in DT_VERNEED sections only.

### PipeWire routing is non-deterministic for re-extracted AppImage

Each `--appimage-extract-and-run` creates a new `/tmp/appimage_extracted_<sha>/`
path. PipeWire/Wireplumber identifies apps partly by binary path; new path =
new app identity = stale stream-restore state. GStreamer pipeline reports
PLAYING and exits 0 with `SPIKE_OK`, but actual audio routing to speakers is
sometimes silent. Two-part fix: (a) set explicit PipeWire app identity in
AppRun via `PULSE_PROP="application.name=... application.id=..."`; (b) ship
production AppImage with FUSE self-mount (deterministic per-content-hash
mount path), reserving `--appimage-extract-and-run` for containers/CI.

### CLI screenshot tools broken on GNOME 49+ Wayland

`gnome-screenshot --window` returns errors via fallback X11 path on GNOME 49
Wayland. `grim` not applicable to GNOME (Mutter, not wlroots). Use
`xdg-desktop-portal-gnome` D-Bus API
(`org.freedesktop.portal.Screenshot.Screenshot`) for production CI screenshot
capture.

### plugin-conda's AppRun hardcodes the entry-point script

linuxdeploy's `--executable hello_world.py` causes the generated AppRun to
`exec ... python hello_world.py "$@"` — anything after `python` is forwarded
to the script, not honored as a script-to-run. Either (a) use `-m
musicstreamer` (avoids the script-path argument entirely), or (b)
parameterize via env var `exec ... python "${APP_ENTRY:-${APPDIR}/musicstreamer/__main__.py}" "$@"`.

### distrobox 1.8.2.4 quirks

- `--volume /dev:/dev:rslave` (the default) fails on hosts with VirtualBox USB
  devices. Use `--unshare-devsys`. Audio still works via the PipeWire socket
  at `$XDG_RUNTIME_DIR/pipewire-0` (separate bind from `/dev`).
- Base images for Ubuntu, Fedora, Tumbleweed omit `binutils`. Add
  `--additional-packages "binutils"` so `smoke_test.py --check-glibc` finds
  `strings`.
- 2026-05 Tumbleweed images ship `/usr/etc/zypp/zypp.conf` (vendor path) but
  distrobox-init's `setup_zypper` sed's `/etc/zypp/zypp.conf` (admin path).
  Add Tumbleweed-only `--pre-init-hooks "mkdir -p /etc/zypp && cp -p
  /usr/etc/zypp/zypp.conf /etc/zypp/zypp.conf"`.

### Heredoc shell-injection inside `distrobox enter --no-tty -- bash -c "..."`

Heredoc bodies with literal `"` characters terminate the outer `bash -c
"..."` argument early. Write the heredoc body to a `mktemp` file and pipe to
`bash` via stdin (FD 0). The `env APPIMG="$APPIMG"` passthrough is preserved
at the `distrobox enter` boundary.

## Constraints

| Fact | Source |
|------|--------|
| AppImage size ~503 MB | Phase 85a Plan 05 round 9 measurement (build host) |
| GLIBC max `GLIBC_2.34` | objdump DT_VERNEED scan on the build host |
| Bundled python's GLIBC max `GLIBC_2.17` | `smoke_test.py --check-glibc` inside each distrobox |
| 188 GStreamer plugins bundled | inventory at `$APPDIR/usr/conda/lib/gstreamer-1.0/*.so` |
| PyGObject only via conda-forge on Linux too | upstream policy, all versions (mirrors Windows; see windows-gstreamer-bundling.md) |
| GStreamer 1.28+ TLS backend is OpenSSL | conda-forge `glib-networking` on linux-64 reports `GTlsBackendOpenssl` |
| `linuxdeploy-plugin-gstreamer` last commit 2024-03-01 | upstream dormancy (Pitfall 8); SHA-pin is the mitigation |
| `linuxdeploy-plugin-conda` last commit 2024-09-07 | upstream low-activity; SHA-pin + Approach P sed-patch are the mitigations |
| Build container baseline: ubuntu:22.04 (GLIBC 2.35) | locked to support Ubuntu 22.04 LTS downstream users |
| Distrobox baseline: 1.8.2.4 | `--unshare-devsys` is required on hosts with VirtualBox USB devices |
| 9 rounds to a green build in Plan 05 | discovery archaeology preserved in `sources/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md` §"The 9-Round Plan 05 Saga" |

## Origin

Synthesized from Phase 85a spike (Linux AppImage bundling validation;
2026-05-26). Source files: `sources/85a-linux-packaging-spike/` — full
`Dockerfile`, `environment-spike.yml`, `pins.env`, `verify-pins.sh`,
`build.sh`, `hello_world.py`, `AppRun`, `smoke_test.py`, `test_url.txt`,
`create-distroboxes.sh`, `run-smoke.sh`, README.md, and the canonical
`85A-SPIKE-FINDINGS.md` with all 20 pitfalls catalogued + per-distro
empirical evidence + Phase 85 hand-off manifest.

Cross-reference: `windows-gstreamer-bundling.md` documents the Phase 43
Windows analog. The cross-platform invariants
(`GIO_EXTRA_MODULES`/`GI_TYPELIB_PATH`/scanner placement; conda-forge as the
only viable PyGObject path; the same broad-collect-prune-later plugin
philosophy) hold on Linux. The Linux deltas (FUSE handling, AppRun script,
distrobox UAT, supply-chain pinning for raw GitHub `.sh` assets) are
captured here.
