#!/usr/bin/env bash
# Phase 85a — toolchain pin drift-guard
# Sources pins.env, re-fetches each asset, sha256sum-compares, exits 2 on drift.
# Exit codes (per RESEARCH.md §Pattern 2): 0=ok, 2=drift.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./pins.env
source "${HERE}/pins.env"

check_pin() {
  local name="$1" url="$2" expected="$3"
  local tmp
  tmp="$(mktemp "${TMPDIR:-/tmp}/${name}.XXXXXX")"
  trap 'rm -f "$tmp"' RETURN
  curl -fsSL --retry 3 --retry-delay 2 -o "$tmp" "$url"
  local actual
  actual="$(sha256sum "$tmp" | awk '{print $1}')"
  if [[ "$actual" != "$expected" ]]; then
    printf 'PIN_DRIFT %s\n  expected=%s\n  actual=%s\n' "$name" "$expected" "$actual" >&2
    return 2
  fi
  printf 'PIN_OK %s\n' "$name"
}

check_pin linuxdeploy "$LINUXDEPLOY_URL" "$LINUXDEPLOY_SHA256"
check_pin linuxdeploy-plugin-conda "$LINUXDEPLOY_PLUGIN_CONDA_URL" "$LINUXDEPLOY_PLUGIN_CONDA_SHA256"
check_pin linuxdeploy-plugin-gstreamer "$LINUXDEPLOY_PLUGIN_GSTREAMER_URL" "$LINUXDEPLOY_PLUGIN_GSTREAMER_SHA256"
check_pin miniforge "$MINIFORGE_URL" "$MINIFORGE_SHA256"

printf 'ALL_PINS_VERIFIED\n'
