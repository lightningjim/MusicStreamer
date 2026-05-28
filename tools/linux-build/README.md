# MusicStreamer — Linux Packaging

This directory contains the Linux AppImage build pipeline: a pinned
Dockerfile (Ubuntu 22.04 LTS for GLIBC ≤ 2.35), a conda-forge environment
manifest (`environment.yml`), an AppRun launcher, and a Bash driver
(`build.sh`) that ties them together. Running `bash build.sh` on a
configured Linux host produces a single GPG-signed
`MusicStreamer-x86_64.AppImage` (and `.sig` sidecar) under `artifacts/`.

The pipeline is the production implementation of the patterns proven in
Phase 85a's AppImage spike. See
`.planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md` for the
canonical findings (20 pitfalls with documented mitigations) and
`.claude/skills/spike-findings-musicstreamer/references/linux-appimage-bundling.md`
for the skill mirror.

## Prerequisites

1. **Docker engine OR rootless podman + distrobox.** The build runs in a
   pinned `ubuntu:22.04` container. `docker info` (NOT just
   `docker --version`) must report a reachable daemon. If you use
   distrobox, note that it **autodetects the container backend per
   invocation** — see `reference_distrobox_backend_autodetect.md` in the
   project memory. Forcing the docker daemon view via `sg docker -c 'distrobox ...'`
   may produce a different container set than rootless podman — caught during
   Phase 85a teardown. (D-17 fold-in.)

2. **yq** — `build.sh` parses `environment.yml` to synthesize the
   `CONDA_PACKAGES` list consumed by `linuxdeploy-plugin-conda` (D-01).
   Install via `sudo apt install yq`, `sudo dnf install yq`, or
   `sudo snap install yq` depending on host.

3. **GPG with a signing key.** The build is GPG-signed by default
   (PKG-LIN-APP-10 / D-08). Set the `GPG_KEY_ID` environment variable to
   the key ID or fingerprint of an importable secret key in your local
   keyring before invoking `build.sh`. For local iteration without
   signing, set `SKIP_SIGN=1` (CI never sets this — release artifacts
   always sign).

4. **GLIBC baseline.** The pinned Ubuntu 22.04 build container is the
   only supported build host for ≤ GLIBC_2.35 output. Building on a
   newer-glibc host without the container produces an AppImage that
   refuses to load on Ubuntu 22.04 users (Pitfall 1).

5. **(Optional) distrobox**, for cross-distro UAT. `run-smoke.sh` drives
   the produced AppImage through Ubuntu 22.04 (`ms-linux-ubuntu22`),
   Fedora 40 (`ms-linux-fedora40`), and openSUSE Tumbleweed
   (`ms-linux-tumbleweed`) distroboxes. See `create-distroboxes.sh` /
   `teardown-distroboxes.sh`.

## Quick Start

```bash
# 1. Verify toolchain pins (~30s; SHA256s on 4 upstream assets)
bash tools/linux-build/verify-pins.sh

# 2. Build the AppImage (~10-15 min on first run; ~3-5 min on cached builds)
GPG_KEY_ID=<your-key-id> bash tools/linux-build/build.sh
# OR for local iteration without signing:
SKIP_SIGN=1 bash tools/linux-build/build.sh

# 3. Verify the signature (only meaningful if signed in step 2)
gpg --verify tools/linux-build/artifacts/MusicStreamer-x86_64.AppImage.sig \
             tools/linux-build/artifacts/MusicStreamer-x86_64.AppImage

# 4. (Optional) cross-distro smoke
bash tools/linux-build/create-distroboxes.sh   # create ms-linux-{ubuntu22,fedora40,tumbleweed}
bash tools/linux-build/run-smoke.sh all        # ~8 min total
bash tools/linux-build/teardown-distroboxes.sh # cleanup
```

## Build Step Reference

| Step                                              | Output                                              |
| ------------------------------------------------- | --------------------------------------------------- |
| `verify-pins.sh`                                  | `ALL_PINS_VERIFIED` (exit 2 on drift)               |
| `docker build -f Dockerfile`                      | `ms-linux-build:22.04` image                        |
| `yq` parse of `environment.yml` → `CONDA_PACKAGES` | exported env var (D-01)                            |
| `linuxdeploy --plugin conda --plugin gstreamer`   | `AppDir/` populated with conda env                  |
| `pip install --no-deps /work` (D-03)              | `musicstreamer` installed into bundled env          |
| `linuxdeploy --updateinformation ... --output appimage` | `MusicStreamer-x86_64.AppImage`               |
| `gpg2 --detach-sign --armor`                      | `MusicStreamer-x86_64.AppImage.sig`                 |
| `objdump -T` DT_VERNEED scan                      | `GLIBC_OK GLIBC_<≤2.35>` (exit 4 on drift)          |
| Final stdout                                      | `BUILD_OK appimage=... glibc=... signature=...`     |

## Exit Codes

| Code | Meaning                                                              |
| ---- | -------------------------------------------------------------------- |
| 0    | AppImage produced, GLIBC ≤ 2.35, signature OK (or SKIP_SIGN=1)       |
| 1    | Env missing (Docker not reachable, yq missing, pins.env malformed)   |
| 2    | linuxdeploy / bundle assembly failed                                 |
| 3    | (reserved — smoke runs in run-smoke.sh, not build.sh)                |
| 4    | GLIBC > 2.35 — Pitfall 1 negative pivot                              |
| 5    | GPG_KEY_ID unset and SKIP_SIGN != 1 (D-09)                           |
| 6    | gpg2 --detach-sign failed                                            |

## Downstream Consumers — CI and Containers

Any downstream CI or container context that consumes the **produced**
AppImage (not the linuxdeploy AppImage used during build) MUST invoke it
via `--appimage-extract-and-run`. Container environments typically do
not grant `/dev/fuse` to ordinary processes (Pitfall 11 / D-14). The
`.github/workflows/linux-appimage.yml` workflow follows this rule in its
smoke step; downstream users should too.

## Signing Key

The canonical signing key for MusicStreamer Linux release artifacts has
the fingerprint:

```
<DEVELOPER: replace this block with the actual GPG fingerprint output
 from `gpg --fingerprint <GPG_KEY_ID>`. The fingerprint is the
 out-of-band trust anchor users verify against before trusting an
 update channel (T-85-02-02 mitigation per Plan 85-02). Once committed,
 this fingerprint is the canonical reference; rotating the key requires
 a coordinated rotation announcement.>
```

To verify a downloaded AppImage:

```bash
gpg --verify MusicStreamer-x86_64.AppImage.sig MusicStreamer-x86_64.AppImage
```

The output must include `Good signature from "...MusicStreamer..."` and
the fingerprint above. A `WARNING: This key is not certified with a
trusted signature!` line is expected if the user has not pre-imported
and trusted the signing key.

## Architecture / Pitfall Cross-Reference

Every load-bearing line in `build.sh` and `AppRun` carries a
`# Pitfall N` comment. To survey all mitigations:

```bash
grep -n 'Pitfall' tools/linux-build/build.sh tools/linux-build/AppRun
```

The canonical pitfall catalog lives at
`.planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md`
(sections Pitfall 1 through Pitfall 20). The catalog is also mirrored
in the `spike-findings-musicstreamer` skill for editor recall during
future Linux packaging work.

## File Map

| File                     | Role                                                                  |
| ------------------------ | --------------------------------------------------------------------- |
| `build.sh`               | Top-level driver: pins → docker build → linuxdeploy → sign → GLIBC scan |
| `environment.yml`        | conda-forge env definition (D-01 single source of truth for CONDA_PACKAGES) |
| `AppRun`                 | AppImage launcher: sets GStreamer/GIO/SSL env, PULSE_PROP, execs musicstreamer |
| `Dockerfile`             | Pinned ubuntu:22.04 build container (GLIBC ≤ 2.35 baseline)          |
| `pins.env`               | SHA256 pins for linuxdeploy, plugin-conda, plugin-gstreamer, Miniforge |
| `verify-pins.sh`         | Download + SHA-verify all 4 pinned assets; exit 2 on drift            |
| `smoke_test.py`          | Production smoke harness: D-04 codec sweep + D-05 production import   |
| `run-smoke.sh`           | Cross-distro UAT driver (3 distroboxes × 4 URL families)              |
| `create-distroboxes.sh`  | Provision ms-linux-{ubuntu22,fedora40,tumbleweed} distroboxes         |
| `teardown-distroboxes.sh`| Remove the three cross-distro smoke containers                        |
| `desktop/`               | `.desktop` file + SVG icon for AppImageLauncher integration           |
| `artifacts/`             | Build outputs (AppImage, .sig, transcript logs) — gitignored          |
