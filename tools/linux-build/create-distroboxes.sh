#!/usr/bin/env bash
# Phase 85 — create three named distroboxes for cross-distro AppImage smoke (D-07).
# Per RESEARCH.md Anti-Patterns line 266: distrobox create runs WITHOUT the init
# flag (passing it would start systemd-in-container and hide host-process visibility).
# Containers are ephemeral per D-04; tools/linux-build/teardown-distroboxes.sh removes them.
set -euo pipefail

declare -A BOXES=(
  [ms-linux-ubuntu22]="docker.io/library/ubuntu:22.04"
  [ms-linux-fedora40]="quay.io/fedora/fedora:40"
  [ms-linux-tumbleweed]="registry.opensuse.org/opensuse/tumbleweed:latest"
)

for name in "${!BOXES[@]}"; do
  image="${BOXES[$name]}"
  if distrobox list 2>/dev/null | grep -qE "(^|\s)$name(\s|$)"; then
    echo "EXISTS $name (skipping create)"
  else
    # --unshare-devsys: skip host /dev + /sys bind-mounts. Required on this host
    # because VirtualBox USB devices under /dev/vboxusb/* cannot be re-mounted
    # into rootless podman containers (user-namespace + char-device perms).
    # Audio via PipeWire socket lives in $XDG_RUNTIME_DIR (separate bind),
    # so this does NOT break Plan 07's audible test.
    extra_args=()
    # binutils provides `strings`, which smoke_test.py --check-glibc uses to
    # read GLIBC_X.Y symbol versions out of the AppImage. The base images for
    # all three distros omit binutils; distrobox --additional-packages installs
    # it during initial container setup so it's ready by the time run-smoke.sh
    # invokes the harness.
    extra_args+=(--additional-packages "binutils")
    case "$name" in
      ms-linux-tumbleweed)
        # Tumbleweed image (2026-05) ships zypp.conf only at /usr/etc/zypp/zypp.conf
        # (vendor path); distrobox-init's setup_zypper sed's /etc/zypp/zypp.conf and
        # fails when missing. Pre-init copy from vendor -> admin path keeps init
        # otherwise verbatim. Other distros do not need this hook.
        extra_args+=(--pre-init-hooks "mkdir -p /etc/zypp && [ -f /etc/zypp/zypp.conf ] || cp -p /usr/etc/zypp/zypp.conf /etc/zypp/zypp.conf")
        ;;
    esac
    distrobox create --image "$image" --name "$name" --unshare-devsys "${extra_args[@]}" --yes
    echo "CREATED $name image=$image"
  fi
done

distrobox list
echo "ALL_DISTROBOXES_READY"
