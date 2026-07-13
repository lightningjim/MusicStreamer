---
phase: 85A-linux-packaging-spike
plan: 02
subsystem: spike-build-container-and-env
tags:
  - spike
  - linux-packaging
  - build-container
  - conda-env
  - wave-1
requires:
  - 85A-01
provides:
  - "ubuntu:22.04 Docker build container definition (GLIBC <= 2.35 baseline lock)"
  - "conda-forge env shape locked at 11 dependencies (channel-only conda-forge)"
  - "Spike artifact .gitignore covering build outputs + per-distro evidence files"
  - "Spike-tree README orienting future readers + documenting findings-doc-lives-here convention"
affects:
  - .planning/spikes/85a-linux-packaging-spike/Dockerfile
  - .planning/spikes/85a-linux-packaging-spike/environment-spike.yml
  - .planning/spikes/85a-linux-packaging-spike/.gitignore
  - .planning/spikes/85a-linux-packaging-spike/README.md
tech-stack:
  added:
    - "Dockerfile (ubuntu:22.04 base, 7 apt packages)"
    - "conda env spec (conda-forge channel, 11 deps incl. Linux-specific gst-libav/gst-python/glib-networking)"
  patterns:
    - "Generic build container (no COPY/ENTRYPOINT) driven by `docker run -v $(pwd):/work` from Plan 05's build.sh"
    - "Channel-only conda-forge env (no defaults, no nodefaults) — Phase 43 stack lock preserved"
    - "Findings doc co-located with sources (Phase 43 convention) so /gsd:spike-wrap-up grabs the tree whole"
key-files:
  created:
    - .planning/spikes/85a-linux-packaging-spike/Dockerfile
    - .planning/spikes/85a-linux-packaging-spike/environment-spike.yml
    - .planning/spikes/85a-linux-packaging-spike/.gitignore
    - .planning/spikes/85a-linux-packaging-spike/README.md
  modified: []
decisions:
  - "Do NOT pin `FROM ubuntu:22.04@sha256:<digest>` at authorship time — capture in Plan 05's build.sh on first pull and record in findings doc; keeps Dockerfile readable, no information loss"
  - "Do NOT add COPY/ENTRYPOINT — Plan 05's build.sh drives the container with `docker run -v $(pwd):/work`; keeps image generic + portable + avoids image-rebuild-on-build.sh-change loops"
  - "Only python is version-pinned (=3.12); other 10 deps let conda's solver pick latest compatible — keeps spike input minimal, Plan 08's findings doc captures the actually-resolved versions for Phase 85's pin decision"
  - "conda-forge channel-only (no defaults, no nodefaults) — Phase 43 stack lock preserved + T-85A-02-SC mitigation against package squatting"
metrics:
  duration: "~5 min"
  completed: "2026-05-26"
---

# Phase 85A Plan 02: Build Container + Conda Env Shape Summary

Locks the build-container definition (`ubuntu:22.04`) and conda-forge env shape that Plan 05's `build.sh` will consume, plus the spike-tree `.gitignore` and an orienting `README.md`.

## Goal

Implement RESEARCH.md §Standard Stack (lines 28-49) + §Conda-forge env shape (lines 52-88) verbatim into committed configuration files. These two artifacts are the deterministic input to the entire bundle pipeline; pinning them here means Plan 05's `build.sh` is pure orchestration over locked inputs.

## What was built

### Dockerfile (commit `4de7ca0`)

- `FROM ubuntu:22.04` — locks GLIBC <= 2.35 baseline (Pitfall 1 / success criterion #2)
- Single `RUN apt-get install --no-install-recommends` with 7 packages:
  - `ca-certificates` (HTTPS trust for linuxdeploy + conda fetches)
  - `curl`, `wget` (asset downloaders for the linuxdeploy plugin scripts)
  - `bzip2` (Miniconda installer is bzip2'd)
  - `file` (linuxdeploy-plugin-conda probes binary types)
  - `libfuse2` (linuxdeploy self-mounts; FUSE2 runtime required — Assumption A1)
  - `desktop-file-utils` (linuxdeploy validates the bundled .desktop file)
- `WORKDIR /work`
- NO `COPY`, NO `ENTRYPOINT` — Plan 05's `build.sh` drives the container with `docker run -v $(pwd):/work`
- Top comment block cites: GLIBC <= 2.35 lock, Pitfall 1 (GLIBC drift), and Assumption A1 (libfuse2 vs libfuse2t64 fallback path)
- NOT pinned at `FROM ubuntu:22.04@sha256:<digest>` — digest captured at Plan 05 first-pull and recorded in spike findings (keeps file readable)

### environment-spike.yml (commit `a469935`)

YAML parses; verbatim from RESEARCH.md §environment-spike.yml shape:

- `name: spike-linux`
- `channels: [conda-forge]` (channel-only; no defaults, no nodefaults — Phase 43 stack lock)
- `dependencies:` (11 entries):
  1. `python=3.12` (only pinned package)
  2. `pyside6`
  3. `pygobject`
  4. `gst-python`
  5. `gstreamer`
  6. `gst-plugins-base`
  7. `gst-plugins-good`
  8. `gst-plugins-bad`
  9. `gst-plugins-ugly`
  10. `gst-libav` (Linux-specific addition — Pitfall 7; AAC/H.264 decoders)
  11. `glib-networking` (Linux-specific addition — Pitfall 7; TLS modules for HTTPS streams)

Top comment block cites: Phase 43 stack lock, Pitfall 7 (Linux divergence rationale), and package-legitimacy audit reference (RESEARCH.md lines 109-127).

### .gitignore + README.md (commit `103f64a`)

`.gitignore` excludes:
- `artifacts/` (linuxdeploy output tree)
- `*.AppImage` (binary outputs; regenerable)
- `*.AppDir/` (intermediate staging trees)
- `build.log`, `smoke.log` (per-run logs)
- `*-screenshot.png`, `*-transcript.log` (per-distro evidence files; originals embedded in findings doc)
- `verify-pins.lock` (Plan 03 verification artifact; pin SOURCE lives in build.sh as committed SHA256 constants)

`README.md`:
- `# Phase 85a Linux Packaging Spike` heading
- Brief CONTEXT.md mirror (phase boundary summary)
- Pointer list table mapping all spike files to their owning plan: Dockerfile, environment-spike.yml, hello_world.py, AppRun, smoke_test.py, build.sh, verify-pins.sh, host-environment.md, 85A-SPIKE-FINDINGS.md
- Explicit "Findings doc location" section documenting why `85A-SPIKE-FINDINGS.md` lives in `.planning/spikes/85a-linux-packaging-spike/` (NOT in `.planning/phases/85A-linux-packaging-spike/`) — `/gsd:spike-wrap-up` packages this directory verbatim into the `spike-findings-musicstreamer` skill; the findings doc must travel with the sources it cites. Phase 43 convention.
- Related context links to CONTEXT.md, RESEARCH.md, and the Phase 43 analog skill

## Tasks completed

| Task | Name | Type | Commit | Files |
|------|------|------|--------|-------|
| 1 | Author Dockerfile (ubuntu:22.04 build container) | auto | `4de7ca0` | `.planning/spikes/85a-linux-packaging-spike/Dockerfile` |
| 2 | Author environment-spike.yml (conda-forge env shape) | auto | `a469935` | `.planning/spikes/85a-linux-packaging-spike/environment-spike.yml` |
| 3 | Author .gitignore + sources README | auto | `103f64a` | `.planning/spikes/85a-linux-packaging-spike/.gitignore`, `.planning/spikes/85a-linux-packaging-spike/README.md` |

## Verification

- Dockerfile: 6 content-grep acceptance checks pass (FROM ubuntu:22.04, libfuse2, ca-certificates, desktop-file-utils, WORKDIR /work; all present)
- environment-spike.yml: YAML parses; `channels == ['conda-forge']`; all 11 required deps present (verified by `python3 -c "import yaml; ..."`); no `defaults` channel leakage
- .gitignore: all 8 required patterns present (`artifacts/`, `*.AppImage`, `*.AppDir/`, `build.log`, `smoke.log`, `*-screenshot.png`, `*-transcript.log`, `verify-pins.lock`)
- README.md: `Phase 85a` heading, all 8 file pointers present, findings-doc-location note present, `/gsd:spike-wrap-up` reference present

## Deviations from Plan

None — plan executed exactly as written. RESEARCH.md content was transcribed verbatim per task acceptance criteria; the only authorial additions are comment-block headers (explicitly requested by the plan) and the README's pointer-list table shape (the plan called for a "pointer list" and a table is the cleanest expression).

## Self-Check: PASSED

- `[x] FOUND: .planning/spikes/85a-linux-packaging-spike/Dockerfile`
- `[x] FOUND: .planning/spikes/85a-linux-packaging-spike/environment-spike.yml`
- `[x] FOUND: .planning/spikes/85a-linux-packaging-spike/.gitignore`
- `[x] FOUND: .planning/spikes/85a-linux-packaging-spike/README.md`
- `[x] FOUND: commit 4de7ca0 (feat(85A-02): pin ubuntu:22.04 Dockerfile)`
- `[x] FOUND: commit a469935 (feat(85A-02): pin conda-forge env shape)`
- `[x] FOUND: commit 103f64a (feat(85A-02): add spike .gitignore + README)`
