#!/usr/bin/env bash
# Phase 85 — tear down the three cross-distro AppImage smoke containers.
set -euo pipefail

for name in ms-linux-ubuntu22 ms-linux-fedora40 ms-linux-tumbleweed; do
  if distrobox list 2>/dev/null | grep -qE "(^|\s)$name(\s|$)"; then
    distrobox rm --force "$name"
    echo "REMOVED $name"
  else
    echo "ABSENT $name (skipping)"
  fi
done
echo "TEARDOWN_COMPLETE"
