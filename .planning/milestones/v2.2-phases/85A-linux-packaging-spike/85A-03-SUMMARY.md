---
phase: 85A-linux-packaging-spike
plan: 03
subsystem: spike-supply-chain-pinning
tags:
  - spike
  - linux-packaging
  - supply-chain
  - sha256-pin
  - wave-1
requires:
  - 85A-01
provides:
  - "pins.env: SHA256 pin manifest for 3 toolchain assets (linuxdeploy + 2 plugins) + MINICONDA_VERSION"
  - "verify-pins.sh: stand-alone drift-guard that re-fetches each pinned asset and exits 2 on hash drift"
  - "Project-specific supply-chain mitigation for raw GitHub .sh assets (which npm/pip/cargo slopcheck does not cover)"
affects:
  - .planning/spikes/85a-linux-packaging-spike/pins.env
  - .planning/spikes/85a-linux-packaging-spike/verify-pins.sh
tech-stack:
  added:
    - "bash drift-guard script (set -euo pipefail, curl --retry 3 --retry-delay 2, sha256sum compare)"
  patterns:
    - "Pin SHA256 at first-download for raw GitHub .sh assets that have no formal release tag (RESEARCH.md Pattern 2)"
    - "Drift-guard exits 2 (not 1) on mismatch — reserves exit 1 for unexpected bash errors under set -e; matches RESEARCH.md §Pattern 2"
    - "Stand-alone verify entry point independent of full build (run `bash verify-pins.sh` any time to re-check)"
    - "Linux mirror of Phase 43 stderr-trap discipline: set -euo pipefail forces fail-fast on any subshell error"
key-files:
  created:
    - .planning/spikes/85a-linux-packaging-spike/pins.env
    - .planning/spikes/85a-linux-packaging-spike/verify-pins.sh
  modified: []
decisions:
  - "Pin SHA256 at FIRST download, not at any later 'stable' revisit — once captured the hash IS the pin; any subsequent drift fails verify (RESEARCH.md Pattern 2)"
  - "Exit code 2 on drift (not 1) — set -euo pipefail uses exit 1 for unexpected bash errors; reserving 2 for 'intentional drift detected' keeps CI/diagnostic signal clean"
  - "Sourceable KEY=VALUE format for pins.env (no quotes around hex, no spaces around =) — lets build.sh `source pins.env` instead of parsing"
  - "MINICONDA_VERSION pinned to py312_24.9.2-0 (researcher's recommendation) — spike's job is capture-what-research-said, not chase newer versions"
  - "Trust threshold for [ASSUMED no-formal-release] dormant plugins: Kyle's 2026-05-26 observation that 'the plugins are old because just looking at them it was future proofed anyways (variable for the version of gstreamer for example)' — softens Pitfall 8 dormancy concern. Treat dormant plugin scripts as 'stable interface, mature implementation,' not abandoned."
metrics:
  duration: "~10 min (across both task commits)"
  completed: "2026-05-26"
---

# Phase 85A Plan 03: Supply-Chain Pin Manifest + Drift-Guard Summary

Capture-at-first-download SHA256 pinning for the 3 raw-GitHub toolchain assets (linuxdeploy + linuxdeploy-plugin-conda + linuxdeploy-plugin-gstreamer) plus a stand-alone bash drift-guard that re-verifies them on demand.

## Goal

Implement RESEARCH.md §Package Legitimacy Audit (lines 109-136) + §Common Pitfalls / Pitfall 8 (linuxdeploy-plugin-gstreamer maintenance dormancy). Because npm/pip/cargo slopcheck does not cover raw GitHub `.sh` script assets and the plugin repos publish no formal releases, the spike's project-specific supply-chain mitigation is "pin SHA256 at first download + drift-guard."

## What was built

### pins.env (commit `b07ff0c` — Task 1, already on main)

Sourceable shell `KEY=VALUE` manifest with 4 pins:

- `LINUXDEPLOY_URL` + `LINUXDEPLOY_SHA256`
- `LINUXDEPLOY_PLUGIN_CONDA_URL` + `LINUXDEPLOY_PLUGIN_CONDA_SHA256`
- `LINUXDEPLOY_PLUGIN_GSTREAMER_URL` + `LINUXDEPLOY_PLUGIN_GSTREAMER_SHA256`
- `MINICONDA_VERSION=py312_24.9.2-0`

Top comment block cites: RESEARCH.md §Package Legitimacy Audit (provenance), Pitfall 8 (gstreamer-plugin dormancy rationale), and the npm/pip/cargo-policy-equivalent justification for adopting SHA256-at-first-download.

### verify-pins.sh (commit `a5d33c5` — Task 2)

Stand-alone bash drift-guard, executable (chmod +x at write time):

- `set -euo pipefail` (Linux mirror of Phase 43 stderr-trap discipline)
- `source ./pins.env` (no command-line args; single source of truth)
- `check_pin name url expected_sha`: curl `-fsSL --retry 3 --retry-delay 2` to a `mktemp` file, `sha256sum | awk '{print $1}'`, compare, print `PIN_OK <name>` on match or `PIN_DRIFT <name>` + expected/actual hex on mismatch (`return 2`)
- Runs `check_pin` for all 3 assets, prints `ALL_PINS_VERIFIED` on full pass
- Exit codes (per RESEARCH.md §Pattern 2): 0 = ok, 2 = drift

## Pinned SHA256s

Full 64-hex pins (canonical record; these are also in `pins.env` and verifiable via `bash verify-pins.sh`):

| Asset                            | SHA256                                                             |
| -------------------------------- | ------------------------------------------------------------------ |
| linuxdeploy (AppImage)           | `f2aa8e8bb6265d0edc0b0c666c494dc8975650af589408748d75c9b99434b570` |
| linuxdeploy-plugin-conda (.sh)   | `00ab1cb015ec7d97c8278a285fa5025b49c6bf3de1bc0bcf62ec38cfb6e1544a` |
| linuxdeploy-plugin-gstreamer (.sh) | `c107b49d84edbffc6ab226ed1007e0626a4f7aa2c3a36b7782bef62351d49e94` |
| MINICONDA_VERSION                | `py312_24.9.2-0` (researcher's recommended pin; spike's job is capture not chase) |

## Legitimacy gate

Kyle approved the package-legitimacy spot-check on 2026-05-26 with the verbatim observation:

> "APPROVED, doesn't seem like much concern here for me either. I assume the plugins are old because just looking at them it was future proofed anyways (variable for the version of gstreamer for example)"

This softens RESEARCH.md Pitfall 8 (linuxdeploy-plugin-gstreamer maintenance dormancy) — the dormant plugin scripts parameterize over downstream tool versions (e.g., gstreamer version is a script variable), so dormancy reads as "stable interface, mature implementation" rather than "abandoned." Pin-at-first-download + drift-guard remains the right mitigation regardless, because supply-chain integrity is independent of upstream activity level.

GitHub org `linuxdeploy` confirmed via HTTP 200 on all three canonical URLs; commit-log dates match RESEARCH.md (linuxdeploy-plugin-conda 2024-09-07 exact, linuxdeploy-plugin-gstreamer 2024-03-01 exact).

## Tasks completed

| Task | Name | Type | Commit | Files |
|------|------|------|--------|-------|
| 1 | Capture first-download SHA256 for 3 toolchain assets (legitimacy gate) | checkpoint:human-verify | `b07ff0c` (already on main) | `.planning/spikes/85a-linux-packaging-spike/pins.env` |
| 2 | Author verify-pins.sh drift-guard + mutation-test it | auto | `a5d33c5` | `.planning/spikes/85a-linux-packaging-spike/verify-pins.sh` |

## Verification

Acceptance gates for verify-pins.sh:

1. `test -x .planning/spikes/85a-linux-packaging-spike/verify-pins.sh` — PASS (chmod +x at write)
2. `bash -n .planning/spikes/85a-linux-packaging-spike/verify-pins.sh` — PASS (clean parse)
3. `bash .planning/spikes/85a-linux-packaging-spike/verify-pins.sh` against current pins — exit 0, printed `PIN_OK linuxdeploy`, `PIN_OK linuxdeploy-plugin-conda`, `PIN_OK linuxdeploy-plugin-gstreamer`, `ALL_PINS_VERIFIED`
4. Mutation test — see next section

## Mutation test evidence

Negative-path coverage executed: pins.env was copied to `pins.env.tmp`, then `sed -i 's/^LINUXDEPLOY_SHA256=f/LINUXDEPLOY_SHA256=0/' pins.env` mutated the first hex char of the linuxdeploy pin. Re-running `bash verify-pins.sh` produced `PIN_DRIFT linuxdeploy` with full expected/actual hex on stderr and exit code **2** (as required by RESEARCH.md §Pattern 2 — not 0, not 1). pins.env was then restored from the backup; `git diff .planning/spikes/85a-linux-packaging-spike/pins.env` is empty and `git status --short .planning/spikes/85a-linux-packaging-spike/pins.env` is empty — zero residue.

## Deviations from Plan

None — plan executed exactly as written. The verify-pins.sh body is verbatim from the Task 2 spec; the only authorial decision was during testing (chose to mutate `LINUXDEPLOY_SHA256` first hex char specifically), which is operational not structural.

## Self-Check: PASSED

- `[x] FOUND: .planning/spikes/85a-linux-packaging-spike/pins.env`
- `[x] FOUND: .planning/spikes/85a-linux-packaging-spike/verify-pins.sh`
- `[x] FOUND: commit b07ff0c (feat(85A-03): pin toolchain SHA256s at first download)` — already on main
- `[x] FOUND: commit a5d33c5 (feat(85A-03): add verify-pins.sh drift-guard)`
- `[x] FOUND: verify-pins.sh exit 0 against current pins`
- `[x] FOUND: verify-pins.sh exit 2 under mutation; pins.env restored with zero git diff`
