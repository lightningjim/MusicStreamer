---
created: 2026-05-26T00:00:00.000Z
title: host-environment.md should probe docker daemon access (not just CLI version)
area: spike-prereq
resolves_phase: 85
files:
  - .planning/spikes/85a-linux-packaging-spike/host-environment.md — currently probes `docker --version` only
  - Phase 85 equivalent host-env capture (TBD when Phase 85 plans)
---

## Problem

Phase 85a Plan 01's `host-environment.md` runs `docker --version` to confirm Docker is installed. That probe succeeded on the dev rig (`Docker version 29.5.2`) but Plan 05's first `docker build` invocation failed because `kcreasey` was not in the `docker` group — the daemon socket `/var/run/docker.sock` was unreadable from the user shell.

The gap surfaced 4 plans deep into the spike instead of at host-env capture time.

## Fix

When Phase 85 (or any successor host-env capture) probes Docker, add a daemon-access probe **in addition to** the CLI version probe:

```bash
# In addition to `docker --version`:
docker info > /dev/null 2>&1 && echo "## docker daemon: accessible" || echo "## docker daemon: NOT accessible — user likely not in docker group"
# Or:
docker ps > /dev/null 2>&1 && echo OK || echo "FAIL"
```

`docker info` and `docker ps` both round-trip through the daemon socket, so either would have surfaced the group-membership gap at Plan 01 instead of Plan 05.

## Phase 85 application

Apply this to the equivalent host-env capture in Phase 85's Linux Common + AppImage Build phase. Probably bundle into a `## docker daemon access` section right after `## docker` in the manifest format.

## Provenance

Captured during Phase 85a Plan 05 execution (2026-05-26). Kyle resolved with `sudo usermod -aG docker kcreasey` after the failure.
