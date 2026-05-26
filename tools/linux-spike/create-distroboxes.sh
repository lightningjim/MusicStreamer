#!/usr/bin/env bash
# Phase 85a — create three named distroboxes per CONTEXT.md D-03.
# Per RESEARCH.md Anti-Patterns line 266: distrobox create runs WITHOUT the init
# flag (passing it would start systemd-in-container and hide host-process visibility).
# Containers are ephemeral per D-04; tools/linux-spike/teardown-distroboxes.sh removes them.
set -euo pipefail

declare -A BOXES=(
  [ms-spike-ubuntu22]="docker.io/library/ubuntu:22.04"
  [ms-spike-fedora40]="quay.io/fedora/fedora:40"
  [ms-spike-tumbleweed]="registry.opensuse.org/opensuse/tumbleweed:latest"
)

for name in "${!BOXES[@]}"; do
  image="${BOXES[$name]}"
  if distrobox list 2>/dev/null | grep -qE "(^|\s)$name(\s|$)"; then
    echo "EXISTS $name (skipping create)"
  else
    distrobox create --image "$image" --name "$name" --yes
    echo "CREATED $name image=$image"
  fi
done

distrobox list
echo "ALL_DISTROBOXES_READY"
