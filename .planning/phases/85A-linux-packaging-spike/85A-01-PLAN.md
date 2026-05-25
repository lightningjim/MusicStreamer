---
phase: 85A-linux-packaging-spike
plan: 01
type: execute
wave: 0
depends_on: []
files_modified:
  - .planning/spikes/85a-linux-packaging-spike/host-environment.md
autonomous: false
requirements:
  - SPIKE-85A
tags:
  - spike
  - linux-packaging
  - host-tooling
  - wave-0

must_haves:
  truths:
    - "Host has distrobox installed and on PATH"
    - "Host has gnome-screenshot installed and on PATH"
    - "Host has grim installed (fallback Wayland screenshot tool)"
    - "Host has podman + docker + script(1) + sha256sum + strings + curl already present (per RESEARCH.md probe)"
    - "Host-environment manifest captured for findings doc reproducibility"
  artifacts:
    - path: ".planning/spikes/85a-linux-packaging-spike/host-environment.md"
      provides: "Host environment manifest (kernel, GNOME version, podman/docker versions, GLIBC, WAYLAND_DISPLAY, distrobox version)"
      contains: "GLIBC_, podman, distrobox, gnome-screenshot"
  key_links:
    - from: ".planning/spikes/85a-linux-packaging-spike/host-environment.md"
      to: "85A-SPIKE-FINDINGS.md (Plan 08)"
      via: "Plan 08 ingests this file verbatim into the per-distro evidence prefix"
      pattern: "Host Environment"
---

<objective>
Install missing host-side tooling (distrobox + gnome-screenshot + grim) and capture a host-environment manifest that the findings doc reproduces verbatim for the spike's reproducibility evidence.

Purpose: Establishes Wave 0 prerequisites flagged in RESEARCH.md §Environment Availability — distrobox + gnome-screenshot were verified ABSENT on the dev rig and MUST be installed before any downstream plan can drive cross-distro verification (D-02).
Output: Host tooling installed on PATH; `.planning/spikes/85a-linux-packaging-spike/host-environment.md` committed.
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@.planning/STATE.md
@.planning/phases/85A-linux-packaging-spike/85A-CONTEXT.md
@.planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md
@.planning/phases/85A-linux-packaging-spike/85A-VALIDATION.md
</context>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| host APT repos -> dev rig | apt-installed distrobox/gnome-screenshot/grim are trusted Ubuntu archive packages; same trust level as any other apt install |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-85A-01 | Tampering | apt-installed packages | accept | Distro-provided packages; standard apt trust chain; no third-party PPAs added |
| T-85A-02 | Information disclosure | host-environment.md committed to git | accept | Manifest captures versions, not secrets; QNAP-Gitea-mirrors-to-GitHub posture (per MEMORY.md) treats QNAP pushes as effectively public; reviewed at commit time |
</threat_model>

<tasks>

<task type="checkpoint:human-action" gate="blocking-human">
  <name>Task 1: Install distrobox + gnome-screenshot + grim on host (requires sudo)</name>
  <files>(host system; no repo files)</files>
  <read_first>
    - .planning/phases/85A-linux-packaging-spike/85A-CONTEXT.md (D-01, D-02 locked decisions)
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Environment Availability (lines 619-642) — confirms distrobox + gnome-screenshot ABSENT on dev rig; grim ABSENT; podman 5.7.0 + docker 29.5.2 already present
  </read_first>
  <acceptance_criteria>
    - shell-exit: `command -v distrobox && command -v gnome-screenshot && command -v grim` exits 0
    - shell-exit: `command -v podman && command -v docker && command -v script && command -v sha256sum && command -v strings && command -v curl` exits 0 (sanity re-probe)
    - manual-checkpoint: Kyle confirms `sudo apt install distrobox gnome-screenshot grim` ran without error
  </acceptance_criteria>
  <what-built>This is a sudo-gated package install. Claude cannot run sudo apt non-interactively in this sandbox; Kyle runs the install on the host then types "installed".</what-built>
  <how-to-verify>
    On the host, run:
    ```
    sudo apt update
    sudo apt install -y distrobox gnome-screenshot grim
    ```
    Confirm all three command names resolve:
    ```
    command -v distrobox && command -v gnome-screenshot && command -v grim && echo OK
    ```
  </how-to-verify>
  <resume-signal>Type "installed" once all three resolve, or describe failure (e.g., "grim not in 26.04 repos — using `flameshot` instead").</resume-signal>
  <action>HUMAN ACTION REQUIRED: sudo-gated. Kyle runs `sudo apt update && sudo apt install -y distrobox gnome-screenshot grim` on the Ubuntu 26.04 host. Per CONTEXT.md D-Discretion the Wayland screenshot default is `gnome-screenshot --window` (GNOME Wayland session), `grim` is the wlroots fallback. If the host's GNOME version enforces portal-only screenshots (Assumption A6 in RESEARCH.md), Kyle records the fallback path here.</action>
  <verify>
    <automated>command -v distrobox && command -v gnome-screenshot && command -v grim</automated>
    <human-check>Kyle types "installed" or describes the fallback he used.</human-check>
  </verify>
  <done>All three commands resolve on PATH; podman + docker + script + sha256sum + strings + curl re-confirmed present.</done>
</task>

<task type="auto">
  <name>Task 2: Capture host-environment manifest</name>
  <files>.planning/spikes/85a-linux-packaging-spike/host-environment.md</files>
  <read_first>
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Host session probe (lines 639-643) — known-good values to verify against (Ubuntu 26.04 / GLIBC 2.43 / GNOME Wayland)
    - .claude/skills/spike-findings-musicstreamer/sources/43-gstreamer-windows-spike/README.md (Phase 43 host-env capture pattern)
  </read_first>
  <acceptance_criteria>
    - file-exists: `test -f .planning/spikes/85a-linux-packaging-spike/host-environment.md`
    - content-grep: `grep -q '^## GLIBC' .planning/spikes/85a-linux-packaging-spike/host-environment.md`
    - content-grep: `grep -q '^## podman' .planning/spikes/85a-linux-packaging-spike/host-environment.md`
    - content-grep: `grep -q '^## distrobox' .planning/spikes/85a-linux-packaging-spike/host-environment.md`
    - content-grep: `grep -q 'WAYLAND_DISPLAY' .planning/spikes/85a-linux-packaging-spike/host-environment.md`
  </acceptance_criteria>
  <action>Create `.planning/spikes/85a-linux-packaging-spike/host-environment.md` capturing the values listed below verbatim from these commands (record the COMMAND and OUTPUT for each section, so Plan 08 can re-run for drift detection): `lsb_release -a` (## OS), `uname -r` (## Kernel), `ldd --version | head -1` (## GLIBC), `podman --version` (## podman), `docker --version` (## docker), `distrobox --version` (## distrobox), `gnome-screenshot --version` (## gnome-screenshot), `grim -h | head -1` (## grim), `echo $WAYLAND_DISPLAY $XDG_SESSION_TYPE $XDG_CURRENT_DESKTOP` (## Session). Add a trailing `## Notes` section flagging any fallbacks Kyle chose in Task 1 (e.g., flameshot for grim). File header: `# Phase 85a Host Environment` with capture date `Captured: $(date -u +%Y-%m-%d)`.</action>
  <verify>
    <automated>test -f .planning/spikes/85a-linux-packaging-spike/host-environment.md && grep -cE '^## (GLIBC|podman|distrobox|gnome-screenshot|Session)' .planning/spikes/85a-linux-packaging-spike/host-environment.md | grep -qE '^[5-9]|^[1-9][0-9]+'</automated>
  </verify>
  <done>Manifest file exists with at least 5 of the named sections (GLIBC, podman, distrobox, gnome-screenshot, Session) plus their command outputs.</done>
</task>

</tasks>

<verification>
- distrobox + gnome-screenshot + grim on PATH (sudo apt install completed by Kyle)
- host-environment.md committed to git under .planning/spikes/85a-linux-packaging-spike/
- Manifest captures GLIBC version (expected 2.43 on Ubuntu 26.04 host), podman 5.7.0, distrobox version, GNOME Wayland confirmation
</verification>

<success_criteria>
- `command -v distrobox && command -v gnome-screenshot && command -v grim && command -v podman && command -v docker` exits 0
- `.planning/spikes/85a-linux-packaging-spike/host-environment.md` exists with all 5 named sections
- Plan 08 (SPIKE-FINDINGS.md) can ingest this manifest verbatim for the reproducibility prefix
</success_criteria>

<output>
Create `.planning/phases/85A-linux-packaging-spike/85A-01-SUMMARY.md` when done. Summary lists: distrobox version installed, gnome-screenshot version, grim version, GLIBC version, any fallbacks chosen (e.g., flameshot for grim).
</output>
