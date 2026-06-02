#!/usr/bin/env bash
# Phase 85 — drive smoke_test.py inside each named distrobox; capture transcripts.
# Usage: bash tools/linux-build/run-smoke.sh [ubuntu22|fedora40|tumbleweed|all]
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$(cd "${HERE}" && pwd)"
# Phase 85 production layout — artifacts and smoke harness colocated under tools/linux-build/.
APPIMG_GLOB="${BUILD_DIR}/artifacts/MusicStreamer-*x86_64.AppImage"
APPIMG="$(ls -t ${APPIMG_GLOB} 2>/dev/null | grep -v '\.sig$' | head -1)"
SMOKE_PY="${BUILD_DIR}/smoke_test.py"
[[ -n "$APPIMG" && -x "$APPIMG" ]] || { echo "MISSING_APPIMAGE ${APPIMG_GLOB} (run tools/linux-build/build.sh first)" >&2; exit 1; }
[[ -f "$SMOKE_PY" ]] || { echo "MISSING_SMOKE $SMOKE_PY (run Plan 85-04 first)" >&2; exit 1; }

TARGET="${1:-all}"
case "$TARGET" in
  ubuntu22)    DISTROS=(ms-linux-ubuntu22) ;;
  fedora40)    DISTROS=(ms-linux-fedora40) ;;
  tumbleweed)  DISTROS=(ms-linux-tumbleweed) ;;
  all)         DISTROS=(ms-linux-ubuntu22 ms-linux-fedora40 ms-linux-tumbleweed) ;;
  *)           echo "USAGE: $0 [ubuntu22|fedora40|tumbleweed|all]" >&2; exit 1 ;;
esac

# Build the in-container script body. Host-side variables ($SMOKE_PY) are
# interpolated at emit time via the UNQUOTED heredoc tag `<<INNER`. The in-container
# script reads $APPIMG from the env passed via `env APPIMG="$APPIMG"` below.
#
# IMPORTANT (plan-template bug fix): the original Plan 06 template used
# `"$APPIMG" --appimage-extract-and-run python smoke_test.py ...` to drive
# smoke_test.py. That does NOT work — the AppImage's AppRun (see
# tools/linux-build/AppRun) hard-codes `exec "${APPDIR}/usr/conda/bin/python"
# -m musicstreamer "$@"`, so anything after `python` is forwarded to musicstreamer
# (which expects normal app args). The correct approach is to
# `--appimage-extract` once, export the AppRun env vars manually, then invoke
# the bundled python with smoke_test.py directly. We preserve smoke_test.py's
# stdout markers (SPIKE_OK / SPIKE_FAIL / plugin_resolved=) verbatim.
run_modes_in_box() {
  cat <<INNER
set -x
echo "DISTRO_PROBE start=\$(date -u +%s)"
echo "CONTAINER_OS_RELEASE_BEGIN"
cat /etc/os-release || true
echo "CONTAINER_OS_RELEASE_END"

# SMOKE_PY interpolates at emit time (host path; \$HOME is shared into the container).
SMOKE_PY="${SMOKE_PY}"

# Extract the AppImage once per container into a per-container tmpdir so
# subsequent smoke modes reuse the same squashfs tree (faster + lets us pin
# APPDIR exactly). --appimage-extract dumps to ./squashfs-root by default.
WORKDIR="\$(mktemp -d -t ms-linux-XXXXXX)"
cd "\$WORKDIR"
"\$APPIMG" --appimage-extract >/dev/null
APPDIR="\$WORKDIR/squashfs-root"
test -d "\$APPDIR" || { echo "SPIKE_FAIL reason=extract_missing dir=\$APPDIR"; exit 1; }

# Export AppRun's env vars manually (we cannot \`source AppRun\` — its last line
# is \`exec ... -m musicstreamer "\$@"\`). These mirror AppRun lines 47-74 verbatim.
export APPDIR
export GST_PLUGIN_SYSTEM_PATH_1_0="\${APPDIR}/usr/conda/lib/gstreamer-1.0"
export GST_PLUGIN_PATH_1_0="\${APPDIR}/usr/conda/lib/gstreamer-1.0"
export GST_PLUGIN_SCANNER="\${APPDIR}/usr/conda/libexec/gstreamer-1.0/gst-plugin-scanner"
export GST_PLUGIN_SCANNER_1_0="\${APPDIR}/usr/conda/libexec/gstreamer-1.0/gst-plugin-scanner"
export GST_REGISTRY_FORK="no"
export GIO_EXTRA_MODULES="\${APPDIR}/usr/conda/lib/gio/modules"
# Pitfall 17 mitigation — must mirror AppRun's SSL_CERT_FILE so bundled OpenSSL
# can validate the conda-forge CA bundle (HTTPS playback). Without this the
# smoke harness reproduces the "Unacceptable TLS certificate" failure that AppRun
# itself was patched to avoid; see 85A-SPIKE-FINDINGS.md Pitfall 17.
export SSL_CERT_FILE="\${APPDIR}/usr/conda/ssl/cacert.pem"
export GI_TYPELIB_PATH="\${APPDIR}/usr/conda/lib/girepository-1.0"
export PYTHONHOME="\${APPDIR}/usr/conda"
export PATH="\${APPDIR}/usr/conda/bin:\${PATH}"

PYBIN="\${APPDIR}/usr/conda/bin/python"
test -x "\$PYBIN" || { echo "SPIKE_FAIL reason=python_missing path=\$PYBIN"; exit 1; }

# Phase 85 D-04: four-URL codec sweep — MP3 + AAC + AACP + PLS-resolved.
# smoke_test.py argparse modes (Plan 85-04 Task 2) drive each URL family with
# the production resolver (D-05). Per-URL playback duration: 35s (D-06).
"\$PYBIN" "\$SMOKE_PY" --check-glibc "\$PYBIN" || echo "SPIKE_FAIL mode=glibc"
"\$PYBIN" "\$SMOKE_PY" --check-plugins avdec_aac,aacparse
"\$PYBIN" "\$SMOKE_PY" --assert-tls
"\$PYBIN" "\$SMOKE_PY" --check-mp3   --timeout 35
"\$PYBIN" "\$SMOKE_PY" --check-aac   --timeout 35
"\$PYBIN" "\$SMOKE_PY" --check-aacp  --timeout 35
"\$PYBIN" "\$SMOKE_PY" --check-pls   --timeout 35

cd /
rm -rf "\$WORKDIR"
echo "DISTRO_PROBE end=\$(date -u +%s)"
INNER
}

for box in "${DISTROS[@]}"; do
  short="${box#ms-linux-}"
  log="${BUILD_DIR}/artifacts/${short}-transcript.log"
  body_file="$(mktemp -t "85-inner-${short}.XXXXXX.sh")"
  trap 'rm -f "$body_file"' EXIT
  run_modes_in_box > "$body_file"
  echo "RUN_SMOKE box=$box log=$log body=$body_file"
  # NOTE 1: env APPIMG="$APPIMG" uses DOUBLE quotes so the host shell interpolates
  # $APPIMG before `distrobox enter` is invoked. (Single quotes would pass the
  # literal string $APPIMG to env.)
  # NOTE 2: We pipe the heredoc body to `bash` via stdin (NOT `bash -c "..."`)
  # because the body contains literal " characters (around $APPIMG / $SMOKE_PY)
  # that would terminate any outer double-quoted -c argument. `script -q -c CMD
  # FILE < INPUT` redirects INPUT to the CMD's stdin inside `script`'s pty.
  script -q -c "distrobox enter $box --no-tty -- env APPIMG=\"$APPIMG\" bash" "$log" < "$body_file"
  rm -f "$body_file"
done

echo "ALL_DISTROS_SMOKED"
