# Phase 85a Linux Packaging Spike — Sources

Throwaway experiment: validate that a Qt + GStreamer AppImage built in
ubuntu:22.04 Docker via `linuxdeploy + linuxdeploy-plugin-conda +
linuxdeploy-plugin-gstreamer + conda-forge` plays SomaFM MP3 streams (HTTP +
HTTPS) across Ubuntu 22.04, Fedora 40, and openSUSE Tumbleweed. Produced
`85A-SPIKE-FINDINGS.md` + the AppRun env-var template Phase 85 inherits.

## File pointer list

| File | Owning plan | Role |
|------|-------------|------|
| `Dockerfile`                | 85A-02 | ubuntu:22.04 build container — locks GLIBC ≤ 2.35 baseline (Pitfall 1) |
| `environment-spike.yml`     | 85A-02 | conda-forge env spec — 11 packages, channel-only (Phase 43 stack lock) |
| `pins.env`                  | 85A-03 | SHA256 pin manifest for 3 toolchain assets + Miniforge3 + Approach P patched plugin-conda SHA |
| `verify-pins.sh`            | 85A-03 | Drift-guard (exit 2 on hash mismatch); sourceable bash, sets `-euo pipefail` |
| `hello_world.py`            | 85A-04 | Minimal playbin3 driver — no Qt/QObject; argv-pre-import gate so host-side liveness checks work without PyGObject |
| `AppRun`                    | 85A-04 | **PRIMARY DELIVERABLE** — 8 env-var exports under `${APPDIR}/usr/conda/`; documents the GST_REGISTRY_FORK vs GST_REGISTRY_REUSE_PLUGIN_SCANNER distinction (Pitfall 3); SSL_CERT_FILE export from Pitfall 17 fix |
| `smoke_test.py`             | 85A-04 | Validation harness — GLIBC + plugin + TLS + playback modes; locks the `plugin_resolved=<name>` literal marker for cross-plan grep contracts |
| `test_url.txt`              | 85A-04 | SomaFM fallback chain (HTTP + HTTPS variants per CONTEXT.md D-07/D-08/D-09) |
| `build.sh`                  | 85A-05 | End-to-end build driver — Phase 43 `build.ps1` Linux analog; 8 in-script Pitfall mitigations (8, 11, 12, 13/13b, 14, 15, 16) |
| `create-distroboxes.sh`     | 85A-06 | Idempotent 3-distrobox creation; runtime-hardened with `--unshare-devsys`, `--additional-packages binutils`, Tumbleweed-only `--pre-init-hooks` zypp shim |
| `run-smoke.sh`              | 85A-06 | Cross-distro smoke driver — invokes smoke_test.py inside each distrobox via stdin-piped heredoc |
| `85A-SPIKE-FINDINGS.md`     | 85A-08 | THIS SPIKE'S FINDINGS DOC — all 20 pitfalls catalogued, per-distro evidence, AppRun template, Phase 85 hand-off manifest |

## How the pieces fit

```
pins.env  -> verify-pins.sh  -> build.sh (Dockerfile + environment-spike.yml)
                                   |
                                   v
                            linuxdeploy + plugin-conda + plugin-gstreamer
                                   |
                                   v
                            AppImage (with AppRun + bundled conda env)
                                   |
                                   |--- HTTP/HTTPS smoke via smoke_test.py
                                   |    (programmatic: run-smoke.sh in 3 distroboxes
                                   |     created by create-distroboxes.sh)
                                   v
                            hello_world.py exec on a SomaFM URL (test_url.txt)
                                   |
                                   v
                            85A-SPIKE-FINDINGS.md captures all evidence + pitfalls
```

## Findings doc location

`85A-SPIKE-FINDINGS.md` is co-located with the sources it cites (Phase 43
convention). The doc travels with the source tree into this skill so future
Claude sessions answering Linux-packaging questions get both the findings
narrative and the exact files referenced.

## Related context

- Sibling skill reference: `../../references/linux-appimage-bundling.md` —
  recompacted patterns + landmines + constraints
- Phase 43 Windows analog: `../43-gstreamer-windows-spike/` + sibling reference
  `../../references/windows-gstreamer-bundling.md`
- Spike phase directory (planning artifacts): `.planning/phases/85A-linux-packaging-spike/`
  (CONTEXT.md, RESEARCH.md, all per-plan SUMMARYs)
