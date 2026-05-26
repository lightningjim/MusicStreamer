# Phase 85a Linux Packaging Spike

A throwaway spike that produces a hello-world Qt + GStreamer AppImage, built in
an Ubuntu 22.04 LTS Docker container, and verifies it launches and plays a
remote MP3 stream on Ubuntu 22.04, Fedora 40, and openSUSE Tumbleweed (via
distrobox sessions on the dev rig's Wayland host). Validates the
`linuxdeploy-plugin-conda` + `linuxdeploy-plugin-gstreamer` toolchain
end-to-end and produces the AppRun env-var template
(`GST_PLUGIN_SYSTEM_PATH_1_0`, `GST_PLUGIN_PATH_1_0`, `GST_PLUGIN_SCANNER`,
`GST_REGISTRY_FORK=no`) ready for Phase 85 copy-paste consumption.

This directory holds the spike's source tree. The findings doc lives here too
(see "Findings doc location" below).

## Files in this directory

| File | Plan | Role |
|------|------|------|
| `host-environment.md` | 85A-01 | Host probe manifest (OS, kernel, GLIBC, podman, docker, distrobox, screenshot tools, Wayland session) — reproducibility prefix for findings |
| `Dockerfile` | 85A-02 | `ubuntu:22.04` build container (GLIBC <= 2.35 lock); driven by `build.sh` via `docker run -v $(pwd):/work` |
| `environment-spike.yml` | 85A-02 | conda-forge env shape (11 packages, channel-only `conda-forge`); consumed by `linuxdeploy-plugin-conda` |
| `.gitignore` | 85A-02 | Excludes build artifacts (`artifacts/`, `*.AppImage`, `*.AppDir/`, logs, screenshots, transcripts, lock file) |
| `hello_world.py` | 85A-04 | Minimal `playbin3` HTTPS smoke app (mirrors Phase 43 `smoke_test.py` shape, Linux-tuned) |
| `AppRun` | 85A-04 | AppRun env-var template — the four GST_* exports that are this spike's primary deliverable |
| `smoke_test.py` | 85A-04 | Plugin-discovery + GLIBC + state-machine verifier; runs from inside the AppRun shell |
| `build.sh` | 85A-05 | Build driver; pins linuxdeploy + plugin SHA256s, runs the Docker build container, produces the AppImage |
| `verify-pins.sh` | 85A-03 | SHA256 pin verification (Plan 03 captures the pins; this script asserts them on every build) |
| `85A-SPIKE-FINDINGS.md` | 85A-08 | Per-distro evidence bundle (audible + screenshot + transcript) and the spike's overall PASS/FAIL story |

## Findings doc location

`85A-SPIKE-FINDINGS.md` lives in this directory (`.planning/spikes/85a-linux-packaging-spike/`),
NOT in `.planning/phases/85A-linux-packaging-spike/`. This is intentional and
mirrors the Phase 43 convention: `/gsd:spike-wrap-up` packages this entire
directory verbatim into the `spike-findings-musicstreamer` skill at
`sources/85a-linux-packaging-spike/`, so the findings doc must travel with the
sources it cites. Keeping it in `.planning/phases/` would split the spike's
evidence from its source tree and break the wrap-up flow.

(The phase tree under `.planning/phases/85A-linux-packaging-spike/` holds
the planning documents — `85A-CONTEXT.md`, `85A-RESEARCH.md`, `85A-VALIDATION.md`,
`85A-NN-PLAN.md`, `85A-NN-SUMMARY.md` — which stay in the planning tree and
do NOT get copied into the skill.)

## Related context

- `.planning/phases/85A-linux-packaging-spike/85A-CONTEXT.md` — locked decisions (D-01 .. D-09 + Claude's Discretion)
- `.planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md` — toolchain mechanics, pitfalls, asset URLs
- `.claude/skills/spike-findings-musicstreamer/` — Phase 43 Windows-spike analog (the proven pattern this spike mirrors)
