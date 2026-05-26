#!/usr/bin/env bash
# Phase 85a build driver. Mirrors Phase 43 build.ps1 shape on Linux.
# Exit codes (matching Phase 43 + RESEARCH.md §Pattern 2):
#   0 = AppImage produced + GLIBC <= 2.35
#   1 = env missing (Docker not available, pins.env malformed, etc.)
#   2 = linuxdeploy/bundle failed
#   3 = smoke failed (reserved; smoke runs in Plan 06 / run-smoke.sh)
#   4 = GLIBC > 2.35 (Pitfall 1 negative pivot trigger)

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
  --user "$(id -u):$(id -g)" \
  -e HOME=/tmp/_home \
  -e XDG_CACHE_HOME=/tmp/_cache \
  -v "${HERE}":/work \
  -v "${ARTIFACTS}":/work/artifacts \
  -e LINUXDEPLOY_URL -e LINUXDEPLOY_SHA256 \
  -e LINUXDEPLOY_PLUGIN_CONDA_URL -e LINUXDEPLOY_PLUGIN_CONDA_SHA256 \
  -e LINUXDEPLOY_PLUGIN_GSTREAMER_URL -e LINUXDEPLOY_PLUGIN_GSTREAMER_SHA256 \
  -e MINICONDA_VERSION \
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

    # Bundle
    /tmp/linuxdeploy.AppImage --appdir "$APPDIR" \
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

# Step 4: GLIBC grep on host (Pitfall 1 / success criterion #2)
APPIMG="${ARTIFACTS}/MusicStreamer-spike-x86_64.AppImage"
[[ -f "$APPIMG" ]] || { echo "BUILD_FAIL no_appimage=$APPIMG" >&2; exit 2; }

GLIBC_MAX="$(strings "$APPIMG" | grep -E '^GLIBC_[0-9]+\.[0-9]+$' | sort -V | tail -1 || echo "GLIBC_unknown")"
echo "GLIBC_GREP $GLIBC_MAX"

# Compare against 2.35
case "$GLIBC_MAX" in
  GLIBC_2.1?|GLIBC_2.2?|GLIBC_2.3[0-5]) echo "GLIBC_OK $GLIBC_MAX <= 2.35" ;;
  *) echo "GLIBC_FAIL $GLIBC_MAX > 2.35  (Pitfall 1 negative pivot trigger)" >&2; exit 4 ;;
esac

echo "BUILD_OK appimage=$APPIMG glibc=$GLIBC_MAX"
