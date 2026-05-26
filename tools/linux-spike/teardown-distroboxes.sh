#!/usr/bin/env bash
# Phase 85a — tear down all three distroboxes per CONTEXT.md D-04 (ephemeral).
set -euo pipefail

for name in ms-spike-ubuntu22 ms-spike-fedora40 ms-spike-tumbleweed; do
  if distrobox list 2>/dev/null | grep -qE "(^|\s)$name(\s|$)"; then
    distrobox rm --force "$name"
    echo "REMOVED $name"
  else
    echo "ABSENT $name (skipping)"
  fi
done
echo "TEARDOWN_COMPLETE"
