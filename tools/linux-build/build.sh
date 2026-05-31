#!/usr/bin/env bash
# Phase 85 production AppImage build driver (refactor of Phase 85a spike build.sh).
# Exit codes (matching Phase 43 + RESEARCH.md §Pattern 2):
#   0 = AppImage produced + GLIBC <= 2.35
#   1 = env missing (Docker not available, pins.env malformed, etc.)
#   2 = linuxdeploy/bundle failed
#   3 = smoke failed (reserved; smoke runs in Plan 06 / run-smoke.sh)
#   4 = GLIBC > 2.35 (Pitfall 1 negative pivot trigger)
#   5 = GPG_KEY_ID unset and SKIP_SIGN != 1 (D-09 fail-fast guard)
#   6 = gpg2 --detach-sign failed (D-08 signing step)
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

# D-09 fail-fast: signing is mandatory for release artifacts; SKIP_SIGN=1 is the
# local-iteration escape hatch (CI never sets SKIP_SIGN per D-09).
# POSITIONING: this block MUST stay above the first `docker run`/`docker build`
# call (currently around line 91 from Plan 85-01). Moving it below docker
# invocations would cause unset-key runs to hang on a daemon probe instead of
# failing fast -- see warning #2 in the Plan 85-02 checker pass.
if [[ -z "${GPG_KEY_ID:-}" && "${SKIP_SIGN:-0}" != "1" ]]; then
  echo "BUILD_FAIL reason=gpg_key_unset (set GPG_KEY_ID=<keyid> or SKIP_SIGN=1 for local iteration; CI must set the key) (D-09)" >&2
  exit 5
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARTIFACTS="${HERE}/artifacts"
# Repo root is two levels up from tools/linux-build/. It holds the installable
# musicstreamer package (pyproject.toml + musicstreamer/), which is NOT in HERE.
# Mounted read-only as /src so the in-container D-03 pip step can install it.
REPO_ROOT="$(cd "${HERE}/../.." && pwd)"
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
docker build -f "${HERE}/Dockerfile" -t ms-linux-build:22.04 "${HERE}"

# Step 3: run the build inside the container
#   - Mount HERE as /work
#   - Mount ARTIFACTS as /work/artifacts
#   - Pass through pins.env via -e LINUXDEPLOY_* (so the inner shell doesn't re-curl from raw URLs without the SHA gate)
# D-01: parse environment.yml at build start; YAML is the single source of truth.
# The pip: sublist is excluded (it feeds the post-step pip install --no-deps below per D-03);
# only the bare conda dependency strings become CONDA_PACKAGES.
# Pitfall 8 (plugin-conda doesn't consume environment.yml directly) is the reason
# this synthesis step exists.
command -v yq >/dev/null || { echo "BUILD_FAIL reason=yq_missing (install via: snap install yq OR apt install yq)" >&2; exit 1; }
CONDA_PACKAGES="$(yq -r '.dependencies[] | select(type=="string")' "${HERE}/environment.yml" | tr '\n' ';' | sed 's/;$//')"
export CONDA_PACKAGES
export CONDA_CHANNELS="conda-forge"
echo "BUILD_DIAG conda_packages=${CONDA_PACKAGES}"

# --user $(id -u):$(id -g) maps the container process to the host user so the
# produced AppDir/, artifacts/, and any _temp_home/ residue are owned by kcreasey
# (prior attempts left root-owned dirs that orphaned the worktree).
# HOME=/tmp/_home: linuxdeploy-plugin-conda writes to $HOME during install; with
# --user uid:gid (non-root) the default $HOME defaults to / which is unwritable.
# XDG_CACHE_HOME=/tmp/_cache: defensive for conda's cache.
# Plugin scripts placed in /tmp/ + PATH=/tmp:$PATH inside container — non-root cannot
# cp into /usr/local/bin; linuxdeploy resolves plugins via `command -v linuxdeploy-plugin-<name>`.
# CONDA_SKIP_CLEANUP=site-packages;strip — opt out of two linuxdeploy-plugin-conda
#   cleanups: (a) site-packages, which otherwise deletes pip and breaks the D-03
#   `pip install` below; (b) strip, whose container binutils segfaults (exit 139)
#   on a bundled Qt/PySide6 lib and aborts the build. Quoted because of the `;`.
# CONDA_REMOTE_{MAX_RETRIES,BACKOFF_FACTOR} — raise conda's download retry budget
#   above the default 3 so transient TLS record-layer failures on flaky links do
#   not abort a ~10-min build.
# -v REPO_ROOT:/src:ro — read-only repo root so the D-03 step can install the
#   musicstreamer package (which lives at the root, not under HERE=/work).
docker run --rm --privileged \
  --network=host \
  --user "$(id -u):$(id -g)" \
  -e HOME=/tmp/_home \
  -e XDG_CACHE_HOME=/tmp/_cache \
  -e CONDA_FETCH_THREADS=1 \
  -e "CONDA_SKIP_CLEANUP=site-packages;strip" \
  -e CONDA_REMOTE_MAX_RETRIES=6 \
  -e CONDA_REMOTE_BACKOFF_FACTOR=2 \
  -v "${HERE}":/work \
  -v "${ARTIFACTS}":/work/artifacts \
  -v "${REPO_ROOT}":/src:ro \
  -e LINUXDEPLOY_URL -e LINUXDEPLOY_SHA256 \
  -e LINUXDEPLOY_PLUGIN_CONDA_URL -e LINUXDEPLOY_PLUGIN_CONDA_SHA256 \
  -e LINUXDEPLOY_PLUGIN_CONDA_PATCHED_SHA256 \
  -e LINUXDEPLOY_PLUGIN_GSTREAMER_URL -e LINUXDEPLOY_PLUGIN_GSTREAMER_SHA256 \
  -e MINICONDA_VERSION \
  -e MINIFORGE_TAG -e MINIFORGE_URL -e MINIFORGE_SHA256 \
  -e CONDA_CHANNELS -e CONDA_PACKAGES \
  ms-linux-build:22.04 \
  bash -euo pipefail -c '
    set -x
    mkdir -p /tmp/_home /tmp/_cache
    cd /work
    APPDIR=/work/AppDir
    rm -rf "$APPDIR" && mkdir -p "$APPDIR"

    # Download + SHA-verify pinned assets.
    # --retry-all-errors makes curl retry transient TLS record-layer failures
    # (exit 56, "bad record mac") seen on flaky links; every asset is
    # sha256-checked immediately after, so a corrupted retry cannot slip through.
    curl -fsSL --retry 5 --retry-delay 2 --retry-all-errors -o /tmp/linuxdeploy.AppImage "$LINUXDEPLOY_URL"
    echo "$LINUXDEPLOY_SHA256  /tmp/linuxdeploy.AppImage" | sha256sum --check
    chmod +x /tmp/linuxdeploy.AppImage

    curl -fsSL --retry 5 --retry-delay 2 --retry-all-errors -o /tmp/linuxdeploy-plugin-conda.sh "$LINUXDEPLOY_PLUGIN_CONDA_URL"
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

    curl -fsSL --retry 5 --retry-delay 2 --retry-all-errors -o /tmp/linuxdeploy-plugin-gstreamer.sh "$LINUXDEPLOY_PLUGIN_GSTREAMER_URL"
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
    cp /work/desktop/org.lightningjim.MusicStreamer.desktop "$APPDIR/"
    cp /work/desktop/org.lightningjim.MusicStreamer.svg "$APPDIR/"

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
    # D-11 / PKG-LIN-APP-06: embed zsync update-info pointing at the GitHub-Releases-
    # flavored host. This is consumed by the appimage OUTPUT plugin (appimagetool),
    # NOT by linuxdeploy itself -- linuxdeploy has no such update-info flag and
    # aborts with "Flag could not be matched: updateinformation" if given one.
    # The pinned linuxdeploy continuous build (SHA f2aa8e8b...) bundles a plugin
    # that reads update-info ONLY from the LDAI_UPDATE_INFORMATION env var (verified
    # via `strings` on the bundled linuxdeploy-plugin-appimage binary -- it exposes
    # LDAI_-prefixed vars only, no legacy UPDATE_INFORMATION). Setting it makes
    # appimagetool write the .upd_info section AND emit the companion .zsync file.
    # The .zsync is served by a future infra milestone (PKG-LIN-APP-UPDATE --
    # REQUIREMENTS.md deferred); Phase 85 closes the embedding (D-12), not the serving.
    # Note the literal "kcreasey" matches the GitHub mirror namespace per
    # reference_qnap_github_mirror.md; do not change to "lightningjim" -- the
    # QNAP-Gitea origin pushes to github.com/kcreasey/MusicStreamer.
    export LDAI_UPDATE_INFORMATION="gh-releases-zsync|kcreasey|MusicStreamer|latest|MusicStreamer-*-x86_64.AppImage.zsync"
    # CONDA_SKIP_CLEANUP (skip site-packages + strip cleanups) and the conda
    # network-retry knobs are passed in via docker -e flags on the run command
    # above -- see the rationale block there. Kept out of this single-quoted
    # bash -c body to minimize apostrophe-quoting hazards.
    /tmp/linuxdeploy.AppImage --appimage-extract-and-run --appdir "$APPDIR" \
      --plugin conda \
      --plugin gstreamer \
      --desktop-file "$APPDIR/org.lightningjim.MusicStreamer.desktop" \
      --icon-file "$APPDIR/org.lightningjim.MusicStreamer.svg" \
      --output appimage

    # D-03: install musicstreamer itself via pip --no-deps into the bundled conda env.
    # Conda-forge does not package musicstreamer; --no-deps avoids re-resolving the
    # already-conda-managed dependency graph. The pip: sublist in environment.yml
    # is installed via plugin-conda BEFORE this step.
    #
    # Source: /src is the repo root, bind-mounted READ-ONLY (the package source
    # lives there, NOT in /work which is tools/linux-build/). We do NOT point pip
    # at /src directly: the working tree is multi-GB of gitignored build artifacts
    # and pip PEP517 copies its entire source dir into a temp build area. Instead
    # copy only the minimal buildable tree (pyproject.toml + the musicstreamer
    # package) into a scratch dir. pyproject.toml references no other files
    # (no readme/license/MANIFEST/dynamic fields -- verified), so this is complete.
    #
    # Invoke via `python -m pip` (not the bin/pip console script) so the install
    # is robust to the conda plugin console-script handling; pip itself is
    # preserved by CONDA_SKIP_CLEANUP=site-packages (set via docker -e above).
    export PATH="$APPDIR/usr/conda/bin:$PATH"
    PKGSRC=/tmp/pkgsrc
    rm -rf "$PKGSRC" && mkdir -p "$PKGSRC"
    cp -r /src/pyproject.toml /src/musicstreamer "$PKGSRC"/
    python -m pip install --no-deps "$PKGSRC"

    # Locate the produced AppImage robustly (Issue #5 fix):
    #   - linuxdeploy may use any of: MusicStreamer_Spike-*.AppImage, "MusicStreamer Spike-*.AppImage",
    #     MusicStreamer-Spike-*.AppImage, etc. — the exact form depends on .desktop Name= sanitization.
    #   - The broad "./*.AppImage" glob is unsafe: linuxdeploy.AppImage + linuxdeploy-plugin-*.AppImage
    #     also live in /tmp/ but could be copied into /work/ at any stage.
    #   - Use `find` with explicit exclusions of linuxdeploy plugin AppImages + `-newer /work/AppRun`
    #     so we only catch AppImages produced AFTER the AppDir was assembled.
    AppImage_path=$(find /work -maxdepth 1 -name "*.AppImage" -not -name "linuxdeploy*" -not -name "linuxdeploy-plugin-*" -newer /work/AppRun 2>/dev/null | head -1)
    [ -n "$AppImage_path" ] || { echo "BUILD_FAIL: no AppImage produced"; exit 2; }
    mv "$AppImage_path" /work/artifacts/MusicStreamer-x86_64.AppImage
  ' || { echo "BUILD_FAIL exit=$?" >&2; exit 2; }

# Step 4: GLIBC check on host (Pitfall 1 / success criterion #2)
APPIMG="${ARTIFACTS}/MusicStreamer-x86_64.AppImage"
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

# D-08 / PKG-LIN-APP-10: GPG-sign the produced AppImage. The signature is a
# detached, armored sidecar at <appimage>.sig and is published alongside
# the AppImage in the release artifact set. linuxdeploy itself supports a
# --sign flag, but the standalone gpg invocation here keeps the signing
# surface visible at the build-driver level (easier to audit / disable).
# Binary resolution: GnuPG 2.x ships as `gpg` on modern distros (Ubuntu 24.04,
# Arch, Fedora) and as `gpg2` on older ones. Prefer gpg2 when present for
# back-compat, else fall back to gpg -- both are GnuPG 2.x here.
if [[ "${SKIP_SIGN:-0}" != "1" ]]; then
  GPG_BIN="$(command -v gpg2 || command -v gpg || true)"
  [[ -n "$GPG_BIN" ]] || { echo "BUILD_FAIL reason=no_gpg (install gnupg / gnupg2)" >&2; exit 6; }
  "$GPG_BIN" --detach-sign --armor --local-user "$GPG_KEY_ID" --output "${APPIMG}.sig" "$APPIMG" \
    || { echo "BUILD_FAIL reason=signing_failed ($GPG_BIN --detach-sign exited non-zero for key=$GPG_KEY_ID)" >&2; exit 6; }
  echo "SIGN_OK signature=${APPIMG}.sig key=$GPG_KEY_ID gpg=$GPG_BIN"
else
  echo "SIGN_SKIPPED SKIP_SIGN=1 (local-iteration mode; no .sig sidecar produced)"
fi

if [[ "${SKIP_SIGN:-0}" != "1" ]]; then
  echo "BUILD_OK appimage=$APPIMG glibc=$GLIBC_MAX signature=${APPIMG}.sig"
else
  echo "BUILD_OK appimage=$APPIMG glibc=$GLIBC_MAX signature=skipped"
fi
