#!/usr/bin/env bash
# Phase 85a — drive smoke_test.py inside each named distrobox; capture transcripts.
# Usage: bash tools/linux-spike/run-smoke.sh [ubuntu22|fedora40|tumbleweed|all]
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPIKE_DIR="$(cd "${HERE}/../../.planning/spikes/85a-linux-packaging-spike" && pwd)"
APPIMG="${SPIKE_DIR}/artifacts/MusicStreamer-spike-x86_64.AppImage"
SMOKE_PY="${SPIKE_DIR}/smoke_test.py"
[[ -x "$APPIMG" ]] || { echo "MISSING_APPIMAGE $APPIMG (run Plan 05 build.sh first)" >&2; exit 1; }
[[ -f "$SMOKE_PY" ]] || { echo "MISSING_SMOKE $SMOKE_PY (run Plan 04 first)" >&2; exit 1; }

TARGET="${1:-all}"
case "$TARGET" in
  ubuntu22)    DISTROS=(ms-spike-ubuntu22) ;;
  fedora40)    DISTROS=(ms-spike-fedora40) ;;
  tumbleweed)  DISTROS=(ms-spike-tumbleweed) ;;
  all)         DISTROS=(ms-spike-ubuntu22 ms-spike-fedora40 ms-spike-tumbleweed) ;;
  *)           echo "USAGE: $0 [ubuntu22|fedora40|tumbleweed|all]" >&2; exit 1 ;;
esac

# Build the in-container script body. Host-side variables ($SMOKE_PY) are
# interpolated at emit time via the UNQUOTED heredoc tag `<<INNER`. The in-container
# script reads $APPIMG from the env passed via `env APPIMG="$APPIMG"` below.
#
# IMPORTANT (plan-template bug fix): the original Plan 06 template used
# `"$APPIMG" --appimage-extract-and-run python smoke_test.py ...` to drive
# smoke_test.py. That does NOT work — the AppImage's AppRun (see
# .planning/spikes/85a-linux-packaging-spike/AppRun line 80) hard-codes
# `exec "${APPDIR}/usr/conda/bin/python" "${APPDIR}/hello_world.py" "$@"`, so
# anything after `python` is forwarded to hello_world.py (which expects a URL
# and emits `SPIKE_FAIL reason='usage'`). The correct approach is to
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
WORKDIR="\$(mktemp -d -t ms-spike-XXXXXX)"
cd "\$WORKDIR"
"\$APPIMG" --appimage-extract >/dev/null
APPDIR="\$WORKDIR/squashfs-root"
test -d "\$APPDIR" || { echo "SPIKE_FAIL reason=extract_missing dir=\$APPDIR"; exit 1; }

# Export AppRun's env vars manually (we cannot \`source AppRun\` — its last line
# is \`exec ... hello_world.py "\$@"\`). These mirror AppRun lines 47-74 verbatim.
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

# Mode 1: GLIBC (scan the EXTRACTED python binary, not the raw AppImage blob —
# strings on the squashfs-compressed AppImage matches symbol-version-shaped
# garbage in the compressed payload that doesn't correspond to any real
# linker reference. The extracted python binary is the canonical representative;
# if its max GLIBC requirement is <= 2.35, the bundle is portable.)
"\$PYBIN" "\$SMOKE_PY" --check-glibc "\$PYBIN" || echo "SPIKE_FAIL mode=glibc"
# Mode 2: plugin resolution (greps for plugin_resolved=.avdec_aac / .aacparse)
"\$PYBIN" "\$SMOKE_PY" --check-plugins avdec_aac,aacparse
# Mode 3: TLS backend (Gio.TlsBackend.get_default has a default database)
"\$PYBIN" "\$SMOKE_PY" --assert-tls
# Mode 4: HTTP playback (primary stream, D-07)
"\$PYBIN" "\$SMOKE_PY" --uri http://ice1.somafm.com/groovesalad-128-mp3 --timeout 35
# Mode 5: HTTPS playback (D-08)
"\$PYBIN" "\$SMOKE_PY" --uri https://ice6.somafm.com/groovesalad-128-mp3 --timeout 35

cd /
rm -rf "\$WORKDIR"
echo "DISTRO_PROBE end=\$(date -u +%s)"
INNER
}

for box in "${DISTROS[@]}"; do
  short="${box#ms-spike-}"
  log="${SPIKE_DIR}/artifacts/${short}-transcript.log"
  body_file="$(mktemp -t "85a-inner-${short}.XXXXXX.sh")"
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
