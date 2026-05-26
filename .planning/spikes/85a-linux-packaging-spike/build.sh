#!/usr/bin/env bash
# Phase 85a build driver. Mirrors Phase 43 build.ps1 shape on Linux.
# Exit codes (matching Phase 43 + RESEARCH.md §Pattern 2):
#   0 = AppImage produced + GLIBC <= 2.35
#   1 = env missing (Docker not available, pins.env malformed, etc.)
#   2 = linuxdeploy/bundle failed
#   3 = smoke failed (reserved; smoke runs in Plan 06 / run-smoke.sh)
#   4 = GLIBC > 2.35 (Pitfall 1 negative pivot trigger)
#
# Pitfall 11 (spike-discovered): linuxdeploy.AppImage self-mounts via FUSE,
# which fails in rootless containers (--user mapping). The --appimage-extract-and-run
# flag is the documented escape hatch. The PRODUCED AppImage also inherits this
# behavior — consumers in containers/CI must use the same flag.
#
# Pitfall 12 (spike-discovered): docker bridge networking + conda parallel
# fetch over HTTPS = intermittent CondaSSLError record-layer failures on
# multi-MB conda-forge package downloads (qt6-main, libllvm22, etc.).
# Mitigations applied:
#   --network=host         : bypasses docker bridge MTU/proxy
#   CONDA_FETCH_THREADS=1  : serialize conda downloads (env var overrides condarc)
# Phase 85: production CI should use both. Alternative is to build natively
# on the host (loses GLIBC <= 2.35 baseline if host is newer than ubuntu:22.04).
#
# Pitfall 13 / 13b (spike-discovered, approach P): linuxdeploy-plugin-conda
# hardcodes the Miniconda3-latest installer URL. Miniconda3 24.x's base
# condarc declares Anaconda's `defaults` channels (pkgs/main + pkgs/r), and
# the ToS gate in conda 24.x trips on channel PRESENCE — so even with
# CONDA_CHANNELS=conda-forge the install aborts asking for ToS acceptance.
# The plugin's documented CONDA_DOWNLOAD_DIR hook does NOT let us substitute
# a pre-staged Miniforge installer either, because the plugin runs
# `touch -d '@0'` + `wget -N` (line 125 of pinned upstream), forcing a
# re-download regardless of the cached file's mtime.
#
# Approach P: post-download SHA-verify the upstream plugin-conda, then apply
# a deterministic sed transformation that swaps the Miniconda3 URL/filename
# for Miniforge3 (which ships with conda-forge only, no ToS). Re-verify
# against LINUXDEPLOY_PLUGIN_CONDA_PATCHED_SHA256 for auditability. Phase
# 85 production builds can either (a) re-derive the patched SHA from the
# documented transformation, or (b) maintain a vendored copy of the patched
# script in the repo and pin its SHA directly.
#
# Pitfall 14 (spike-discovered): linuxdeploy walks every .so file already
# present in the AppDir at invocation time and tries to resolve each one's
# DT_NEEDED entries via the host's standard library-search rules
# (/etc/ld.so.cache, /usr/lib, /usr/lib/x86_64-linux-gnu, LD_LIBRARY_PATH,
# and AppDir/usr/lib). The conda-bundled layout puts every GStreamer lib
# at $APPDIR/usr/conda/lib/ — which is NOT in any default search path.
# Without LD_LIBRARY_PATH set, linuxdeploy fails with
#   "Could not find dependency: libgstbase-1.0.so.0"
# even though the library is sitting right there in the AppDir. AppRun
# handles this at runtime via its own LD_LIBRARY_PATH/GST_PLUGIN_PATH
# exports; linuxdeploy needs the same hint at build time.
# Mitigation: export LD_LIBRARY_PATH covering $APPDIR/usr/conda/lib (and
# the gstreamer-1.0 subdir defensively) before invoking linuxdeploy.
#
# Pitfall 15 (spike-discovered): ubuntu:22.04's binutils 2.38 `strip` segfaults
# on newer conda-forge .so files (OpenVINO ~2026.0.0, absl ~2601.0.0, etc.)
# during plugin-conda's cleanup-strip pass. Mitigation: CONDA_SKIP_CLEANUP=strip
# (documented opt-out exposed by plugin-conda).
# Trade-off: larger AppImage. Conda-forge ships pre-stripped tarballs already
# so cost is mostly cosmetic. Alternative for Phase 85: upgrade build base to
# ubuntu:24.04 (newer binutils 2.42), but that pushes GLIBC baseline to 2.39
# (Pitfall 1 regression — fewer distros supported). Spike picks SKIP_CLEANUP.
#
# Pitfall 16 (spike-discovered): GLIBC detection via `strings | grep ^GLIBC_`
# yields false positives from random ASCII coincidences in the compressed
# squashfs payload (round 8 saw GLIBC_2.147 from one such coincidence even
# though real ELF symbols topped at 2.17). Mitigation: extract AppImage and
# walk ELFs with objdump -T to enumerate actual DT_VERNEED symbols. Adds
# ~10-30s to the build but eliminates the false-positive class.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARTIFACTS="${HERE}/artifacts"
mkdir -p "${ARTIFACTS}"

# Step 1: source pins, verify upstream hasn't drifted
# `set -a` auto-exports every variable assigned in pins.env so that the
# `docker run -e LINUXDEPLOY_URL` (value-less) flag below can forward them
# into the container. pins.env uses bare KEY=VALUE form (no `export`) so
# without this they're shell vars, not env vars, and the in-container
# `set -u` trips with "LINUXDEPLOY_URL: unbound variable".
set -a
# shellcheck source=./pins.env
source "${HERE}/pins.env"
set +a
bash "${HERE}/verify-pins.sh"  # exits 2 on drift; set -e propagates

# Step 2: docker build the ubuntu:22.04 base
docker build -f "${HERE}/Dockerfile" -t ms-spike-build:22.04 "${HERE}"

# Step 3: run the build inside the container
#   - Mount HERE as /work
#   - Mount ARTIFACTS as /work/artifacts
#   - Pass through pins.env via -e LINUXDEPLOY_* (so the inner shell doesn't re-curl from raw URLs without the SHA gate)
# conda env spec passed to plugin-conda via env vars.
# IMPORTANT: plugin-conda does NOT consume environment.yml — verified against
# the pinned plugin-conda.sh source (line 74 warns when CONDA_PACKAGES is empty,
# line 157 reads packages from CONDA_PACKAGES with ';' as IFS). The yml file
# in this repo is documentation/source-of-truth; Phase 85 may want to bypass
# plugin-conda and run `conda env create -f environment-spike.yml` directly
# so the yml is the functional input (see 85A-05-SUMMARY.md for the finding).
# Order matches environment-spike.yml (11 packages).
export CONDA_CHANNELS="conda-forge"
export CONDA_PACKAGES="python=3.12;pyside6;pygobject;gst-python;gstreamer;gst-plugins-base;gst-plugins-good;gst-plugins-bad;gst-plugins-ugly;gst-libav;glib-networking"

# --user $(id -u):$(id -g) maps the container process to the host user so the
# produced AppDir/, artifacts/, and any _temp_home/ residue are owned by kcreasey
# (prior attempts left root-owned dirs that orphaned the worktree).
# HOME=/tmp/_home: linuxdeploy-plugin-conda writes to $HOME during install; with
# --user uid:gid (non-root) the default $HOME defaults to / which is unwritable.
# XDG_CACHE_HOME=/tmp/_cache: defensive for conda's cache.
# Plugin scripts placed in /tmp/ + PATH=/tmp:$PATH inside container — non-root cannot
# cp into /usr/local/bin; linuxdeploy resolves plugins via `command -v linuxdeploy-plugin-<name>`.
docker run --rm --privileged \
  --network=host \
  --user "$(id -u):$(id -g)" \
  -e HOME=/tmp/_home \
  -e XDG_CACHE_HOME=/tmp/_cache \
  -e CONDA_FETCH_THREADS=1 \
  -e CONDA_SKIP_CLEANUP=strip \
  -v "${HERE}":/work \
  -v "${ARTIFACTS}":/work/artifacts \
  -e LINUXDEPLOY_URL -e LINUXDEPLOY_SHA256 \
  -e LINUXDEPLOY_PLUGIN_CONDA_URL -e LINUXDEPLOY_PLUGIN_CONDA_SHA256 \
  -e LINUXDEPLOY_PLUGIN_CONDA_PATCHED_SHA256 \
  -e LINUXDEPLOY_PLUGIN_GSTREAMER_URL -e LINUXDEPLOY_PLUGIN_GSTREAMER_SHA256 \
  -e MINICONDA_VERSION \
  -e MINIFORGE_TAG -e MINIFORGE_URL -e MINIFORGE_SHA256 \
  -e CONDA_CHANNELS -e CONDA_PACKAGES \
  ms-spike-build:22.04 \
  bash -euo pipefail -c '
    set -x
    mkdir -p /tmp/_home /tmp/_cache
    cd /work
    APPDIR=/work/AppDir
    rm -rf "$APPDIR" && mkdir -p "$APPDIR"

    # Download + SHA-verify pinned assets
    curl -fsSL -o /tmp/linuxdeploy.AppImage "$LINUXDEPLOY_URL"
    echo "$LINUXDEPLOY_SHA256  /tmp/linuxdeploy.AppImage" | sha256sum --check
    chmod +x /tmp/linuxdeploy.AppImage

    curl -fsSL -o /tmp/linuxdeploy-plugin-conda.sh "$LINUXDEPLOY_PLUGIN_CONDA_URL"
    echo "$LINUXDEPLOY_PLUGIN_CONDA_SHA256  /tmp/linuxdeploy-plugin-conda.sh" | sha256sum --check
    # Approach P (Pitfall 13/13b mitigation): deterministic sed patch to swap
    # the hardcoded Miniconda3 URL to Miniforge3. We narrowly target the
    # x86_64 path; the dead x86 (32-bit) and aarch64 branches in the upstream
    # script are intentionally left untouched (they never execute on x86_64
    # hosts). Re-verify post-patch SHA against the documented pin for audit.
    sed -i \
      -e "s|Miniconda3-latest-Linux-x86_64\.sh|Miniforge3-${MINIFORGE_TAG}-Linux-x86_64.sh|g" \
      -e "s|https://repo\.anaconda\.com/miniconda/|https://github.com/conda-forge/miniforge/releases/download/${MINIFORGE_TAG}/|g" \
      /tmp/linuxdeploy-plugin-conda.sh
    echo "$LINUXDEPLOY_PLUGIN_CONDA_PATCHED_SHA256  /tmp/linuxdeploy-plugin-conda.sh" | sha256sum --check
    chmod +x /tmp/linuxdeploy-plugin-conda.sh

    curl -fsSL -o /tmp/linuxdeploy-plugin-gstreamer.sh "$LINUXDEPLOY_PLUGIN_GSTREAMER_URL"
    echo "$LINUXDEPLOY_PLUGIN_GSTREAMER_SHA256  /tmp/linuxdeploy-plugin-gstreamer.sh" | sha256sum --check
    chmod +x /tmp/linuxdeploy-plugin-gstreamer.sh

    # Plugin scripts go in /tmp/ (non-root cannot write /usr/local/bin).
    # linuxdeploy resolves plugins via `command -v linuxdeploy-plugin-<name>`
    # (NO .sh suffix) — create extensionless wrappers and put /tmp on PATH.
    ln -sf /tmp/linuxdeploy-plugin-conda.sh /tmp/linuxdeploy-plugin-conda
    ln -sf /tmp/linuxdeploy-plugin-gstreamer.sh /tmp/linuxdeploy-plugin-gstreamer
    chmod +x /tmp/linuxdeploy-plugin-conda /tmp/linuxdeploy-plugin-gstreamer
    export PATH=/tmp:$PATH

    # AppDir skeleton
    cp /work/AppRun "$APPDIR/AppRun"
    chmod +x "$APPDIR/AppRun"
    cp /work/hello_world.py "$APPDIR/"
    cp /work/smoke_test.py "$APPDIR/"
    cp /work/test_url.txt "$APPDIR/"
    cp /work/desktop/musicstreamer-spike.desktop "$APPDIR/"
    cp /work/desktop/musicstreamer-spike.svg "$APPDIR/"

    # CRITICAL: redirect plugin-gstreamer to the conda layout BEFORE linuxdeploy invocation
    # (Pitfall 2 mitigation; without this the plugin scans /usr/lib/$(uname -m)-linux-gnu/gstreamer-1.0 and bundles nothing)
    export GSTREAMER_PLUGINS_DIR="$APPDIR/usr/conda/lib/gstreamer-1.0"
    export GSTREAMER_HELPERS_DIR="$APPDIR/usr/conda/libexec/gstreamer-1.0"

    # Pitfall 14 mitigation: linuxdeploy walks the AppDir for existing .so
    # files and tries to resolve their NEEDED deps via standard library
    # search (/usr/lib, /usr/lib/x86_64-linux-gnu, LD_LIBRARY_PATH,
    # AppDir/usr/lib). The conda layout puts GStreamer libs at
    # $APPDIR/usr/conda/lib/ — NOT in any default search path. Without
    # LD_LIBRARY_PATH set, linuxdeploy fails with "Could not find
    # dependency: libgstbase-1.0.so.0" even though the lib is right there
    # in the AppDir. AppRun handles this at runtime via its own env
    # exports; linuxdeploy needs the same hint at build time.
    # See 85A-SPIKE-FINDINGS.md (Plan 08) Pitfall 14.
    # NOTE: no apostrophes in these comments — the entire docker bash -c
    # body is wrapped in a single-quoted string and an unescaped quote
    # would terminate the heredoc.
    export LD_LIBRARY_PATH="$APPDIR/usr/conda/lib:$APPDIR/usr/conda/lib/gstreamer-1.0:${LD_LIBRARY_PATH:-}"

    # Bundle
    # --appimage-extract-and-run: FUSE escape hatch for rootless container.
    # Required because we run as non-root via --user; FUSE setuid fallback
    # (which works for root) is unavailable. Extract-and-run unpacks the
    # AppImage to a temp dir and execs the inner binary directly, skipping
    # FUSE entirely. See Pitfall 11 in 85A-SPIKE-FINDINGS.md (Plan 08).
    /tmp/linuxdeploy.AppImage --appimage-extract-and-run --appdir "$APPDIR" \
      --plugin conda \
      --plugin gstreamer \
      --desktop-file "$APPDIR/musicstreamer-spike.desktop" \
      --icon-file "$APPDIR/musicstreamer-spike.svg" \
      --output appimage

    # Locate the produced AppImage robustly (Issue #5 fix):
    #   - linuxdeploy may use any of: MusicStreamer_Spike-*.AppImage, "MusicStreamer Spike-*.AppImage",
    #     MusicStreamer-Spike-*.AppImage, etc. — the exact form depends on .desktop Name= sanitization.
    #   - The broad "./*.AppImage" glob is unsafe: linuxdeploy.AppImage + linuxdeploy-plugin-*.AppImage
    #     also live in /tmp/ but could be copied into /work/ at any stage.
    #   - Use `find` with explicit exclusions of linuxdeploy plugin AppImages + `-newer /work/AppRun`
    #     so we only catch AppImages produced AFTER the AppDir was assembled.
    AppImage_path=$(find /work -maxdepth 1 -name '*.AppImage' -not -name 'linuxdeploy*' -not -name 'linuxdeploy-plugin-*' -newer /work/AppRun 2>/dev/null | head -1)
    [ -n "$AppImage_path" ] || { echo "SPIKE_FAIL: no AppImage produced"; exit 2; }
    mv "$AppImage_path" /work/artifacts/MusicStreamer-spike-x86_64.AppImage
  ' || { echo "BUILD_FAIL exit=$?" >&2; exit 2; }

# Step 4: GLIBC check on host (Pitfall 1 / success criterion #2)
APPIMG="${ARTIFACTS}/MusicStreamer-spike-x86_64.AppImage"
[[ -f "$APPIMG" ]] || { echo "BUILD_FAIL no_appimage=$APPIMG" >&2; exit 2; }

# Pitfall 16 mitigation: objdump-based DT_VERNEED scan replaces the prior
# strings-grep which produced false-positive GLIBC_2.147 from random ASCII
# coincidence in the compressed squashfs payload. Real GLIBC requirements
# live in ELF DT_VERNEED sections, which objdump -T enumerates explicitly.
TMPEXTRACT="$(mktemp -d "${TMPDIR:-/tmp}/85a-glibc-scan.XXXXXX")"
# Defensive cleanup: trap is per-script-end; we also rm at end of block
trap 'rm -rf "$TMPEXTRACT"' EXIT INT TERM

(
  cd "$TMPEXTRACT"
  "$APPIMG" --appimage-extract-and-run --appimage-extract > /dev/null 2>&1 \
    || "$APPIMG" --appimage-extract > /dev/null 2>&1 \
    || { echo "BUILD_FAIL: could not extract AppImage for GLIBC scan" >&2; exit 2; }
)

# Walk all ELFs (objdump silently errors on non-ELFs; harmless). Use find -L
# to follow conda's symlink farm for libs. Aggregate distinct GLIBC_* tokens.
GLIBC_MAX="$(
  find -L "$TMPEXTRACT/squashfs-root" -type f \
    \( -name '*.so' -o -name '*.so.*' -o -perm /u+x \) \
    -exec objdump -T {} \; 2>/dev/null \
  | grep -oE 'GLIBC_[0-9]+\.[0-9]+' \
  | sort -V -u \
  | tail -1
)"
GLIBC_MAX="${GLIBC_MAX:-GLIBC_unknown}"
echo "GLIBC_OBJDUMP $GLIBC_MAX (real DT_VERNEED scan)"

# Clean up scan dir before exit-code branches
rm -rf "$TMPEXTRACT"
trap - EXIT INT TERM

# Compare against 2.35. The GLIBC_2.[0-9] clause covers single-digit minor
# (e.g., GLIBC_2.4); GLIBC_2.1? and GLIBC_2.2? cover 10-19 and 20-29;
# GLIBC_2.3[0-5] covers 30-35.
case "$GLIBC_MAX" in
  GLIBC_2.[0-9]|GLIBC_2.1?|GLIBC_2.2?|GLIBC_2.3[0-5]) echo "GLIBC_OK $GLIBC_MAX <= 2.35" ;;
  *) echo "GLIBC_FAIL $GLIBC_MAX > 2.35  (Pitfall 1 negative pivot trigger)" >&2; exit 4 ;;
esac

echo "BUILD_OK appimage=$APPIMG glibc=$GLIBC_MAX"
