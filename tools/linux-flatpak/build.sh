#!/usr/bin/env bash
# Phase 86 Flatpak build driver — mirrors tools/linux-build/build.sh (Phase 85).
# Exit codes (matching Phase 85 / PATTERNS.md §tools/linux-flatpak/build.sh):
#   0 = MusicStreamer-<version>.flatpak produced (and signed when SKIP_SIGN != 1)
#   1 = env missing (required tools not available, etc.)
#   2 = flatpak-builder or build-bundle failed
#   5 = GPG_KEY_ID unset and SKIP_SIGN != 1 (D-09 fail-fast guard)
#   6 = signing failed (flatpak build-bundle --gpg-sign exited non-zero)
#
# Flatpak-specific signing note (Critical Note #1 / PATTERNS.md line 527):
#   Unlike the AppImage (gpg --detach-sign sidecar), flatpak build-bundle
#   embeds the GPG signature INLINE inside the .flatpak bundle. There is no
#   .flatpak.sig sidecar. This is a deliberate design choice of the OSTree
#   bundle format. Drift-guards assert --gpg-sign is present in this file
#   (not a sidecar presence check).
#
# CI key import (RESEARCH.md Pitfall 8 / Phase 85 D-16):
#   CI imports a passphrase-less key into an ephemeral GNUPGHOME. The
#   flatpak build-bundle --gpg-sign step does not prompt for a passphrase
#   because the signing key has no passphrase in CI. Mirrors Phase 85's
#   ephemeral GNUPGHOME + allow-loopback-pinentry discipline.

set -euo pipefail

# D-08 / PKG-LIN-FP-11 fail-fast: signing is mandatory for release artifacts.
# SKIP_SIGN=1 is the local-iteration escape hatch (CI never sets SKIP_SIGN).
# POSITIONING: this block MUST stay above the flatpak-builder invocation so
# unset-key runs fail fast before a potentially long build begins.
if [[ -z "${GPG_KEY_ID:-}" && "${SKIP_SIGN:-0}" != "1" ]]; then
  echo "BUILD_FAIL reason=gpg_key_unset (set GPG_KEY_ID=<keyid> or SKIP_SIGN=1 for local iteration; CI must set the key) (D-08)" >&2
  exit 5
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARTIFACTS="${HERE}/artifacts"
# Repo root is two levels up from tools/linux-flatpak/. The Flatpak manifest
# (io.github.kcreasey.MusicStreamer.yaml) lives at the repo root.
REPO_ROOT="$(cd "${HERE}/../.." && pwd)"
mkdir -p "${ARTIFACTS}"

# Derive VERSION from pyproject.toml at repo root (mirrors Phase 85 approach).
# The flatpak bundle artifact name includes the version for traceability.
VERSION="$(grep -m1 '^version = ' "${REPO_ROOT}/pyproject.toml" | tr -d '"' | awk '{print $3}')"
[[ -n "${VERSION}" ]] || { echo "BUILD_FAIL reason=version_unresolvable (check pyproject.toml version field)" >&2; exit 1; }
echo "BUILD_DIAG version=${VERSION}"

# Step 1: require flatpak-builder
# flatpak-builder may be installed as a system package (sudo apt install flatpak-builder)
# OR as a Flatpak itself (flatpak install flathub org.flatpak.Builder). Prefer the
# system binary; fall back to the Flatpak wrapper if the system binary is absent.
if command -v flatpak-builder &>/dev/null; then
  FLATPAK_BUILDER="flatpak-builder"
elif flatpak run org.flatpak.Builder --version &>/dev/null 2>&1; then
  FLATPAK_BUILDER="flatpak run org.flatpak.Builder"
else
  echo "BUILD_FAIL reason=flatpak_builder_missing (install via: flatpak install flathub org.flatpak.Builder OR sudo apt install flatpak-builder)" >&2
  exit 1
fi

# Step 2: build via flatpak-builder.
# --user: build in user's local Flatpak installation (no root required).
# --repo=flatpak-repo: write the OSTree repo to tools/linux-flatpak/flatpak-repo/.
# --force-clean: remove previous build-dir for deterministic builds.
# Manifest path is relative to REPO_ROOT so the `path: .` source entry resolves correctly.
echo "BUILD_DIAG flatpak_builder=${FLATPAK_BUILDER}"
(
  cd "${REPO_ROOT}"
  $FLATPAK_BUILDER \
    --user \
    --repo=flatpak-repo \
    --force-clean \
    "tools/linux-flatpak/build-dir" \
    "io.github.kcreasey.MusicStreamer.yaml"
) || { echo "BUILD_FAIL reason=builder_failed (flatpak-builder exited non-zero)" >&2; exit 2; }

# Step 3: HARD pre-flight validator gate (D-15 / FP-10).
# Both validators run BEFORE flatpak build-bundle. A non-zero exit from either
# FAILS the build immediately — this is a hard gate, not a skippable warning.
METAINFO="${HERE}/metainfo/io.github.kcreasey.MusicStreamer.metainfo.xml"
DESKTOP="${HERE}/desktop/io.github.kcreasey.MusicStreamer.desktop"

if command -v appstreamcli &>/dev/null; then
  echo "BUILD_DIAG running appstreamcli validate on ${METAINFO}"
  appstreamcli validate "${METAINFO}" \
    || { echo "BUILD_FAIL reason=validator_failed (appstreamcli validate exited non-zero — fix metainfo.xml before bundling)" >&2; exit 2; }
  echo "BUILD_DIAG appstreamcli validate OK"
else
  echo "BUILD_FAIL reason=validator_failed (appstreamcli not found; install libappstream-dev or appstream-utils) (D-15)" >&2
  exit 1
fi

if command -v desktop-file-validate &>/dev/null; then
  echo "BUILD_DIAG running desktop-file-validate on ${DESKTOP}"
  desktop-file-validate "${DESKTOP}" \
    || { echo "BUILD_FAIL reason=validator_failed (desktop-file-validate exited non-zero — fix .desktop file before bundling)" >&2; exit 2; }
  echo "BUILD_DIAG desktop-file-validate OK"
else
  echo "BUILD_FAIL reason=validator_failed (desktop-file-validate not found; install desktop-file-utils) (D-15)" >&2
  exit 1
fi

# Step 4: sign + bundle (inline signing — Critical Note #1; no .sig sidecar).
# flatpak build-bundle embeds the GPG signature inside the .flatpak OSTree bundle
# itself (unlike the AppImage's detached gpg --detach-sign .sig sidecar).
# When SKIP_SIGN=1, omit --gpg-sign so unsigned local-iteration builds work
# without needing GPG at all (SKIP_SIGN=1 is never set in CI — D-08).
BUNDLE="${ARTIFACTS}/MusicStreamer-${VERSION}.flatpak"
if [[ "${SKIP_SIGN:-0}" != "1" ]]; then
  flatpak build-bundle \
    --gpg-sign="${GPG_KEY_ID}" \
    --gpg-homedir="${GNUPGHOME:-${HOME}/.gnupg}" \
    "${REPO_ROOT}/flatpak-repo" \
    "${BUNDLE}" \
    io.github.kcreasey.MusicStreamer \
    || { echo "BUILD_FAIL reason=signing_failed (flatpak build-bundle --gpg-sign exited non-zero for key=${GPG_KEY_ID})" >&2; exit 6; }
  echo "SIGN_OK bundle=${BUNDLE} key=${GPG_KEY_ID}"
else
  # SKIP_SIGN=1: produce an unsigned bundle for local iteration.
  # Note: flatpak install --user --no-gpg-verify is required to install unsigned bundles.
  flatpak build-bundle \
    "${REPO_ROOT}/flatpak-repo" \
    "${BUNDLE}" \
    io.github.kcreasey.MusicStreamer \
    || { echo "BUILD_FAIL reason=bundle_failed (flatpak build-bundle exited non-zero)" >&2; exit 2; }
  echo "SIGN_SKIPPED SKIP_SIGN=1 (local-iteration mode; bundle is unsigned)"
fi

if [[ "${SKIP_SIGN:-0}" != "1" ]]; then
  echo "BUILD_OK bundle=${BUNDLE} version=${VERSION} signed=true"
else
  echo "BUILD_OK bundle=${BUNDLE} version=${VERSION} signed=false"
fi
