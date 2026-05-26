# Phase 85a Linux Packaging Spike — Build Container
#
# Locks the AppImage build environment to Ubuntu 22.04 LTS so the produced
# AppImage links against GLIBC <= 2.35.
#
# Why ubuntu:22.04 (success criterion #2, RESEARCH.md §Pitfall 1):
#   GCC + glibc ELF symbol versioning is one-way. An AppImage built on a
#   newer-glibc host (Ubuntu 24.04+, Fedora 40+, this dev rig's Ubuntu 26.04)
#   embeds GLIBC_2.39+ references and refuses to load on Ubuntu 22.04 LTS
#   users. Ubuntu 22.04 (GLIBC 2.35) is the locked baseline; this is the only
#   build host that satisfies the spike's GLIBC <= 2.35 success criterion.
#
# What this image contains (and only this — Plan 05's build.sh adds everything else):
#   - ca-certificates : HTTPS trust roots for linuxdeploy + conda-forge fetches in build.sh
#   - curl, wget      : asset downloaders for linuxdeploy + linuxdeploy-plugin-* scripts
#   - bzip2           : Miniconda installer payload is bzip2'd
#   - file            : linuxdeploy-plugin-conda probes binary types via file(1)
#   - libfuse2        : linuxdeploy AppImage self-mounts to run; FUSE2 runtime required
#                       [Assumption A1, RESEARCH.md §Assumptions Log line 585] —
#                       if libfuse2 turns out to be replaced by libfuse2t64 on this
#                       Ubuntu 22.04 image at Plan 05 execution time, patch this
#                       line (or switch to `--appimage-extract-and-run` mode); the
#                       executor records the actual package used in spike findings.
#   - desktop-file-utils : linuxdeploy validates the bundled .desktop file via
#                          desktop-file-validate(1); without this, linuxdeploy aborts.
#   - patchelf         : linuxdeploy-plugin-gstreamer hard-requires patchelf to
#                        rewrite RPATH on bundled GStreamer .so files. Without
#                        it the plugin aborts with "Error: patchelf not found"
#                        before bundling a single plugin (observed Plan 05 first run).
#   - binutils         : provides strip(1); linuxdeploy-plugin-conda's prune pass
#                        invokes `find ... -exec strip {} \;` on every bundled .so.
#                        Missing strip is non-fatal (find prints "No such file or
#                        directory" warnings per .so and continues) but produces
#                        a much-larger AppImage and pollutes the build log; bundle
#                        with binutils so the size grep + log are clean.
#
# What this image does NOT contain (intentional — keeps Dockerfile readable + portable):
#   - No COPY of the spike source tree. Plan 05's build.sh drives the container
#     with `docker run -v $(pwd):/work` to mount the spike sources into /work
#     instead of baking a snapshot at image build time.
#   - No ENTRYPOINT for the same reason — `docker run ms-spike-build bash build.sh`
#     keeps the image generic and avoids "rebuild image when build.sh changes" loops.
#   - No `FROM ubuntu:22.04@sha256:<digest>` pin at authorship time. Plan 05's
#     build.sh captures the digest on first pull and records it in the findings
#     doc; pinning here would make this file noisier without adding any value the
#     findings doc isn't already capturing.

FROM ubuntu:22.04

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      wget \
      bzip2 \
      file \
      libfuse2 \
      desktop-file-utils \
      patchelf \
      binutils && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /work
