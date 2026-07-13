---
phase: 85A-linux-packaging-spike
plan: 01
subsystem: spike-host-tooling
tags:
  - spike
  - linux-packaging
  - host-tooling
  - wave-0
requires: []
provides:
  - "Host environment manifest for Plan 08 reproducibility prefix"
  - "distrobox + gnome-screenshot + grim installed on host PATH"
affects:
  - .planning/spikes/85a-linux-packaging-spike/host-environment.md
tech-stack:
  added:
    - "distrobox 1.8.2.4 (host package)"
    - "gnome-screenshot 41.0 (host package)"
    - "grim (host package, Wayland fallback)"
  patterns:
    - "Host environment manifest (command + verbatim output per section) — mirrors Phase 43 capture pattern for drift detection"
key-files:
  created:
    - .planning/spikes/85a-linux-packaging-spike/host-environment.md
  modified: []
decisions:
  - "No fallbacks required — Ubuntu 26.04 apt repos provided all three tools (distrobox, gnome-screenshot, grim) cleanly; D-Discretion screenshot-tool fallback to flameshot not exercised"
metrics:
  duration: "~3 min"
  completed: "2026-05-26"
---

# Phase 85A Plan 01: Host Tooling + Environment Manifest Summary

Host tooling prerequisites for the Linux packaging spike installed and a verbatim host-environment manifest committed for Plan 08 to ingest as reproducibility evidence.

## Goal

Install Wave 0 prerequisites flagged in RESEARCH.md §Environment Availability (distrobox + gnome-screenshot + grim ABSENT on dev rig) and capture a host-environment manifest the findings doc will reproduce verbatim.

## What was built

- Verified `distrobox`, `gnome-screenshot`, and `grim` resolve on host PATH (Task 1 confirmed by Kyle: "installed").
- Captured `.planning/spikes/85a-linux-packaging-spike/host-environment.md` with 10 sections (OS, Kernel, GLIBC, podman, docker, distrobox, gnome-screenshot, grim, Session, Notes), each containing the probe command in a fenced block followed by its raw verbatim output in a second fenced block — so Plan 08 can re-run any probe for drift detection.
- Recorded versions for the findings-doc reproducibility prefix:
  - Ubuntu 26.04 LTS (resolute), kernel 7.0.0-15-generic
  - GLIBC 2.43 (matches RESEARCH.md §Host session probe expectation)
  - podman 5.7.0, docker 29.5.2
  - distrobox 1.8.2.4
  - gnome-screenshot 41.0, grim present
  - Session: `wayland-0 wayland ubuntu:GNOME` (confirms GNOME Wayland)

## Key files (created)

- `.planning/spikes/85a-linux-packaging-spike/host-environment.md` — host probe manifest, 10 sections, commit `4c7b8cd`.

## Tasks completed

| Task | Name | Type | Commit | Notes |
|------|------|------|--------|-------|
| 1 | Install distrobox + gnome-screenshot + grim on host | checkpoint:human-action | (sudo apt; host-side only) | Confirmed by Kyle ("installed"); all three resolve on PATH. No fallbacks chosen — D-Discretion flameshot escape hatch not exercised. |
| 2 | Capture host-environment manifest | auto | `4c7b8cd` | All 5 content-grep acceptance checks pass (GLIBC, podman, distrobox, gnome-screenshot, WAYLAND_DISPLAY). |

## Deviations from Plan

None — plan executed exactly as written. No fallbacks required; Ubuntu 26.04 apt repos provided all three tools cleanly.

## Self-Check: PASSED

- `[x] FOUND: .planning/spikes/85a-linux-packaging-spike/host-environment.md`
- `[x] FOUND: commit 4c7b8cd (feat(85A-01): capture host-environment manifest)`
- `[x] grep '^## GLIBC' → present`
- `[x] grep '^## podman' → present`
- `[x] grep '^## distrobox' → present`
- `[x] grep 'WAYLAND_DISPLAY' → present`
