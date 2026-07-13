---
phase: 85A-linux-packaging-spike
plan: 03
type: execute
wave: 1
depends_on:
  - 85A-01
files_modified:
  - .planning/spikes/85a-linux-packaging-spike/pins.env
  - .planning/spikes/85a-linux-packaging-spike/verify-pins.sh
autonomous: false
requirements:
  - SPIKE-85A
tags:
  - spike
  - linux-packaging
  - supply-chain
  - sha256-pin

must_haves:
  truths:
    - "linuxdeploy + linuxdeploy-plugin-conda + linuxdeploy-plugin-gstreamer asset URLs pinned in a single source file"
    - "SHA256 of each of the three toolchain assets captured at first download and committed to pins.env"
    - "verify-pins.sh re-fetches each asset and fails non-zero on hash drift (supply-chain drift-guard)"
    - "Each [ASSUMED] (no formal release) pin has been verified by human at first-download checkpoint (RESEARCH.md §Package Legitimacy Audit / npm/pip/cargo policy adapted for raw GitHub assets)"
  artifacts:
    - path: ".planning/spikes/85a-linux-packaging-spike/pins.env"
      provides: "Authoritative pin manifest: LINUXDEPLOY_URL + SHA256, LINUXDEPLOY_PLUGIN_CONDA_URL + SHA256, LINUXDEPLOY_PLUGIN_GSTREAMER_URL + SHA256, MINICONDA_VERSION"
      contains: "SHA256"
    - path: ".planning/spikes/85a-linux-packaging-spike/verify-pins.sh"
      provides: "Drift-guard script: sources pins.env, curl-downloads each asset to a temp dir, sha256sum-compares, fails on mismatch"
      contains: "sha256sum"
  key_links:
    - from: ".planning/spikes/85a-linux-packaging-spike/pins.env"
      to: "build.sh (Plan 05)"
      via: "build.sh sources pins.env then curl-downloads + verifies BEFORE running linuxdeploy"
      pattern: "source.*pins\\.env"
    - from: "verify-pins.sh"
      to: "spike re-verification protocol (any later run)"
      via: "Run-by-itself entry point for drift check independent of full build"
      pattern: "sha256sum.*--check"
---

<objective>
Pin the three toolchain assets (`linuxdeploy`, `linuxdeploy-plugin-conda`, `linuxdeploy-plugin-gstreamer`) by URL + SHA256, and write a stand-alone `verify-pins.sh` drift-guard. Because none of these assets have a formal release tag (RESEARCH.md lines 47-50), the spike captures SHA256 at FIRST download and treats the resulting hash as the pin — any future drift fails the verify script.

Purpose: Implements RESEARCH.md §Package Legitimacy Audit (lines 109-136) + §Common Pitfalls / Pitfall 8 (linuxdeploy-plugin-gstreamer maintenance dormancy). Because slopcheck doesn't cover raw GitHub `.sh` scripts and the plugin repos publish NO releases, the spike's supply-chain mitigation is "pin SHA256 at first download + drift-guard." Per system prompt §package legitimacy gate, the first-download step is a blocking-human checkpoint since these assets are effectively [ASSUMED] (no registry-side verification surface).
Output: 2 files: `pins.env` (key=value source-able manifest) + `verify-pins.sh` (drift-guard).
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/85A-linux-packaging-spike/85A-CONTEXT.md
@.planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md

<interfaces>
<!-- The three pinned URLs from RESEARCH.md §Standard Stack lines 42-49. -->

LINUXDEPLOY_URL=https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage
LINUXDEPLOY_PLUGIN_CONDA_URL=https://raw.githubusercontent.com/linuxdeploy/linuxdeploy-plugin-conda/master/linuxdeploy-plugin-conda.sh
LINUXDEPLOY_PLUGIN_GSTREAMER_URL=https://raw.githubusercontent.com/linuxdeploy/linuxdeploy-plugin-gstreamer/master/linuxdeploy-plugin-gstreamer.sh

<!-- MINICONDA_VERSION: researcher recommends py312_24.9.2-0, planner verifies at execution -->
MINICONDA_VERSION=py312_24.9.2-0   # Assumption A2 — verify at first download
</interfaces>
</context>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| github.com -> dev rig | Raw `.sh` script downloads + AppImage download cross this boundary; supply chain risk if asset is replaced upstream |
| github.com CDN (release-assets) -> dev rig | linuxdeploy AppImage HEAD returns HTTP 302 to release-assets CDN; same trust chain |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-85A-03-SC | Tampering | linuxdeploy-plugin-conda.sh (raw master, no release) | mitigate | SHA256-pin at first download; verify-pins.sh re-fetches and fails on drift; first-download is a blocking-human checkpoint (Task 1) because asset has no registry-side verification surface |
| T-85A-03-SC2 | Tampering | linuxdeploy-plugin-gstreamer.sh (raw master, dormant per Pitfall 8) | mitigate | Same as above; additional concern: maintenance dormancy means breaking upstream changes are unlikely to be reverted quickly (Pitfall 8). Drift-guard fails build, forcing manual review |
| T-85A-03-SC3 | Tampering | linuxdeploy continuous AppImage | mitigate | SHA256-pin; release-assets CDN with HTTP 302 confirmed accessible (RESEARCH.md line 130) |
</threat_model>

<tasks>

<task type="checkpoint:human-verify" gate="blocking-human">
  <name>Task 1: Capture first-download SHA256 for all three toolchain assets (legitimacy gate)</name>
  <files>.planning/spikes/85a-linux-packaging-spike/pins.env</files>
  <read_first>
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Standard Stack (lines 28-51) — three URLs verified accessible 2026-05-25
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Package Legitimacy Audit (lines 109-136) — disposition + npm/pip/cargo policy adapted for raw GitHub assets
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Pitfall 8 (lines 371-381) — plugin-gstreamer dormancy risk that this pin mitigates
  </read_first>
  <what-built>This is a supply-chain legitimacy checkpoint. None of the three assets have a release-tag pin available; per system prompt §package legitimacy gate, the first-download SHA256 capture is treated as `[ASSUMED]` and gated by human verification BEFORE the pins enter `build.sh`.</what-built>
  <how-to-verify>
    Claude runs:
    ```
    mkdir -p .planning/spikes/85a-linux-packaging-spike/.pin-capture
    cd .planning/spikes/85a-linux-packaging-spike/.pin-capture
    curl -fsSL -o linuxdeploy.AppImage 'https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage'
    curl -fsSL -o linuxdeploy-plugin-conda.sh 'https://raw.githubusercontent.com/linuxdeploy/linuxdeploy-plugin-conda/master/linuxdeploy-plugin-conda.sh'
    curl -fsSL -o linuxdeploy-plugin-gstreamer.sh 'https://raw.githubusercontent.com/linuxdeploy/linuxdeploy-plugin-gstreamer/master/linuxdeploy-plugin-gstreamer.sh'
    sha256sum linuxdeploy.AppImage linuxdeploy-plugin-conda.sh linuxdeploy-plugin-gstreamer.sh
    ```
    Then Claude PRINTS the three URLs + computed SHA256s + asks Kyle to spot-check (a) the GitHub org owns each repo (`linuxdeploy` org for all three), (b) the plugin commit logs show recent activity matching RESEARCH.md cited dates (conda last touched 2024-09-07, gstreamer last touched 2024-03-01), (c) no obvious slop (random forks, suspicious owner accounts) shows up.

    Resume after Kyle confirms.
  </how-to-verify>
  <acceptance_criteria>
    - file-exists: `test -f .planning/spikes/85a-linux-packaging-spike/pins.env`
    - content-grep: `grep -E '^LINUXDEPLOY_URL=' .planning/spikes/85a-linux-packaging-spike/pins.env`
    - content-grep: `grep -E '^LINUXDEPLOY_SHA256=[a-f0-9]{64}$' .planning/spikes/85a-linux-packaging-spike/pins.env` (full 64-hex sha256)
    - content-grep: `grep -E '^LINUXDEPLOY_PLUGIN_CONDA_SHA256=[a-f0-9]{64}$' .planning/spikes/85a-linux-packaging-spike/pins.env`
    - content-grep: `grep -E '^LINUXDEPLOY_PLUGIN_GSTREAMER_SHA256=[a-f0-9]{64}$' .planning/spikes/85a-linux-packaging-spike/pins.env`
    - content-grep: `grep -E '^MINICONDA_VERSION=' .planning/spikes/85a-linux-packaging-spike/pins.env`
    - manual-checkpoint: Kyle confirms (a) GitHub org `linuxdeploy` owns all 3 repos, (b) commit log dates match RESEARCH.md cited dates within reason, (c) no slop signals.
    - shell-exit: `rm -rf .planning/spikes/85a-linux-packaging-spike/.pin-capture` cleanup (don't commit the downloaded artifacts to git)
  </acceptance_criteria>
  <action>Claude performs the download + sha256 capture per the how-to-verify block, then writes `pins.env` as a source-able shell file with KEY=VALUE lines (no spaces around `=`, no quotes around hex). Required keys: `LINUXDEPLOY_URL`, `LINUXDEPLOY_SHA256`, `LINUXDEPLOY_PLUGIN_CONDA_URL`, `LINUXDEPLOY_PLUGIN_CONDA_SHA256`, `LINUXDEPLOY_PLUGIN_GSTREAMER_URL`, `LINUXDEPLOY_PLUGIN_GSTREAMER_SHA256`, `MINICONDA_VERSION` (defaults to `py312_24.9.2-0` per Assumption A2 — Claude checks `repo.anaconda.com/miniconda/` index for a newer stable and uses that if available; documents the pick in Plan 08 findings). File header comment block citing: RESEARCH.md §Package Legitimacy Audit, Pitfall 8, the date of first download, and a note "first-download SHA256 captured per system-prompt legitimacy gate; npm/pip/cargo policy does not cover raw GitHub `.sh` assets so this is the project-specific equivalent." Then Claude PAUSES and asks Kyle to spot-check per the legitimacy gate.</action>
  <resume-signal>Kyle types "approved" once the org-owns-repo + commit-date + no-slop spot-check passes.</resume-signal>
  <verify>
    <automated>test -f .planning/spikes/85a-linux-packaging-spike/pins.env && grep -cE '^(LINUXDEPLOY|LINUXDEPLOY_PLUGIN_CONDA|LINUXDEPLOY_PLUGIN_GSTREAMER)_(URL|SHA256)=' .planning/spikes/85a-linux-packaging-spike/pins.env | grep -qE '^6$' && grep -qE '^MINICONDA_VERSION=' .planning/spikes/85a-linux-packaging-spike/pins.env && grep -qE '^[A-Z_]+_SHA256=[a-f0-9]{64}$' .planning/spikes/85a-linux-packaging-spike/pins.env</automated>
    <human-check>Kyle confirms legitimacy spot-check ("approved").</human-check>
  </verify>
  <done>pins.env committed with all 6 URL/SHA256 pairs + MINICONDA_VERSION; Kyle approved the legitimacy spot-check; .pin-capture/ scratch dir removed.</done>
</task>

<task type="auto">
  <name>Task 2: Author verify-pins.sh drift-guard</name>
  <files>.planning/spikes/85a-linux-packaging-spike/verify-pins.sh</files>
  <read_first>
    - .planning/spikes/85a-linux-packaging-spike/pins.env (just-authored)
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Standard Stack lines 50 — "build.sh must sha256sum each asset at first download, commit the digest, and re-verify on subsequent runs"
    - .claude/skills/spike-findings-musicstreamer/sources/43-gstreamer-windows-spike/build.ps1 (Phase 43 build.ps1 stderr-trap discipline — Linux equivalent is `set -euo pipefail`)
  </read_first>
  <acceptance_criteria>
    - file-exists: `test -x .planning/spikes/85a-linux-packaging-spike/verify-pins.sh` (executable bit set)
    - content-grep: `grep -q 'set -euo pipefail' .planning/spikes/85a-linux-packaging-spike/verify-pins.sh`
    - content-grep: `grep -q 'source.*pins.env\|\. .*pins\.env' .planning/spikes/85a-linux-packaging-spike/verify-pins.sh` (sources the pin manifest, doesn't hardcode hashes)
    - content-grep: `grep -q 'sha256sum' .planning/spikes/85a-linux-packaging-spike/verify-pins.sh`
    - shell-exit: `bash .planning/spikes/85a-linux-packaging-spike/verify-pins.sh` exits 0 (verifies pins still match upstream right now — same check Task 1 performed)
    - shell-exit (negative): introduce a 1-char mutation in pins.env, re-run, confirm script exits non-zero, revert mutation
  </acceptance_criteria>
  <action>Create `.planning/spikes/85a-linux-packaging-spike/verify-pins.sh`:
- `#!/usr/bin/env bash` shebang.
- `set -euo pipefail` (per Phase 43 build.ps1's stderr-trap discipline; Linux equivalent).
- Resolve the script's directory: `HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"`.
- Source the pin manifest: `# shellcheck source=./pins.env` then `source "${HERE}/pins.env"`.
- For each of the three pinned assets:
  1. `curl -fsSL --retry 3 --retry-delay 2 -o "${TMPDIR:-/tmp}/${asset_name}" "$URL"` (curl-only, no wget — pinning a single tool is part of the supply-chain story).
  2. `actual=$(sha256sum "${TMPDIR:-/tmp}/${asset_name}" | awk '{print $1}')`
  3. `if [[ "$actual" != "$EXPECTED_SHA256" ]]; then printf 'PIN_DRIFT %s\n  expected=%s\n  actual=%s\n' "$asset_name" "$EXPECTED_SHA256" "$actual" >&2; exit 2; fi`
  4. `rm -f "${TMPDIR:-/tmp}/${asset_name}"` cleanup.
- On success: `printf 'PIN_OK %s\n' "$asset_name"` for each of the three, then `printf 'ALL_PINS_VERIFIED\n'`.
- Exit codes: `0` = all match, `2` = drift detected (matches RESEARCH.md §Pattern 2 exit-code scheme — 0/1/2/3 for ok/env/build/smoke).
- `chmod +x` the file after writing.

The script must NOT modify pins.env itself; drift detection is informational — Phase 85 / spike re-runs decide whether to update the pin or pin upstream.</action>
  <verify>
    <automated>test -x .planning/spikes/85a-linux-packaging-spike/verify-pins.sh && bash -n .planning/spikes/85a-linux-packaging-spike/verify-pins.sh && bash .planning/spikes/85a-linux-packaging-spike/verify-pins.sh && echo OK</automated>
  </verify>
  <done>verify-pins.sh exists, is executable, passes `bash -n` syntax check, and a fresh run exits 0 against the just-pinned hashes. Drift-guard is ready for build.sh + future re-runs.</done>
</task>

</tasks>

<verification>
- pins.env committed with 6 URL/SHA256 lines (3 assets × URL+SHA256 each) + MINICONDA_VERSION line
- verify-pins.sh exits 0 against current pins
- Mutation test: any 1-character change to a SHA256 in pins.env causes verify-pins.sh to exit 2
</verification>

<success_criteria>
- Supply-chain mitigation (per RESEARCH.md §Pitfall 8) is in place BEFORE build.sh (Plan 05) consumes the pinned assets
- Phase 85 inherits these pins verbatim; Plan 08 findings doc cites the three SHA256s
</success_criteria>

<output>
Create `.planning/phases/85A-linux-packaging-spike/85A-03-SUMMARY.md` when done. Capture: the three SHA256s (full 64-hex), MINICONDA_VERSION final pick + rationale, Kyle's legitimacy approval timestamp.
</output>
