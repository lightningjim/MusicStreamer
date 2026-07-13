---
phase: 85A-linux-packaging-spike
plan: 02
type: execute
wave: 1
depends_on:
  - 85A-01
files_modified:
  - .planning/spikes/85a-linux-packaging-spike/Dockerfile
  - .planning/spikes/85a-linux-packaging-spike/environment-spike.yml
  - .planning/spikes/85a-linux-packaging-spike/.gitignore
  - .planning/spikes/85a-linux-packaging-spike/README.md
autonomous: true
requirements:
  - SPIKE-85A
tags:
  - spike
  - linux-packaging
  - build-container
  - conda-env

must_haves:
  truths:
    - "Ubuntu 22.04 LTS Docker build container definition exists (locked by GLIBC <= 2.35 success criterion #2)"
    - "Conda env shape pinned to conda-forge channel with the 10 packages from RESEARCH.md (mirrors Phase 43 + Linux-specific additions: gst-libav, gst-python, glib-networking)"
    - "Build artifacts (.AppImage, build.log, smoke.log, screenshots) gitignored under artifacts/"
    - "Sources directory README points readers at SPIKE-FINDINGS.md (when Plan 08 lands)"
  artifacts:
    - path: ".planning/spikes/85a-linux-packaging-spike/Dockerfile"
      provides: "ubuntu:22.04 build container definition with libfuse2 + ca-certificates + curl + wget + bzip2 + file + desktop-file-utils"
      contains: "FROM ubuntu:22.04"
    - path: ".planning/spikes/85a-linux-packaging-spike/environment-spike.yml"
      provides: "conda-forge env shape locked at 10 packages"
      contains: "conda-forge"
    - path: ".planning/spikes/85a-linux-packaging-spike/.gitignore"
      provides: "artifacts/ exclusion + .AppImage exclusion"
      contains: "artifacts/"
  key_links:
    - from: "Dockerfile"
      to: "build.sh (Plan 05)"
      via: "Plan 05's build.sh COPIES this Dockerfile into Docker build context and `docker build -f Dockerfile -t ms-spike-build .`"
      pattern: "FROM ubuntu:22.04"
    - from: "environment-spike.yml"
      to: "linuxdeploy-plugin-conda (Plan 05's build.sh)"
      via: "Plugin reads this file at bundle time to assemble $APPDIR/usr/conda/"
      pattern: "channels:\\s*\\n\\s*- conda-forge"
---

<objective>
Lock the build-container definition (`ubuntu:22.04`) and conda-forge env shape that Plan 05's `build.sh` consumes. These are the two configuration artifacts that determine what ends up inside the AppImage and what GLIBC baseline the AppImage links against.

Purpose: Implements RESEARCH.md §Standard Stack (lines 28-49) + §Conda-forge env shape (lines 52-88) verbatim. The Dockerfile + environment-spike.yml pair is the deterministic input to the entire bundle pipeline; pinning here means Plan 05's build.sh is just orchestration.
Output: 3 files (Dockerfile, environment-spike.yml, .gitignore) committed under `.planning/spikes/85a-linux-packaging-spike/`.
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/85A-linux-packaging-spike/85A-CONTEXT.md
@.planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md
@.claude/skills/spike-findings-musicstreamer/references/windows-gstreamer-bundling.md

<interfaces>
<!-- The exact conda env shape (locked by RESEARCH.md lines 70-86). Plan 05's build.sh inherits this verbatim. -->

From RESEARCH.md §environment-spike.yml shape:
```yaml
name: spike-linux
channels:
  - conda-forge
dependencies:
  - python=3.12
  - pyside6
  - pygobject
  - gst-python
  - gstreamer
  - gst-plugins-base
  - gst-plugins-good
  - gst-plugins-bad
  - gst-plugins-ugly
  - gst-libav
  - glib-networking
```

Locked by Phase 43 stack + Linux-specific additions per Pitfall 7 (gst-libav, gst-python, glib-networking explicit on Linux).
</interfaces>
</context>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| conda-forge channel -> AppImage | conda-forge is the only configured channel; channel-only pin per Phase 43 stack lock prevents package squatting from `defaults` |
| ubuntu:22.04 image -> Docker build | Docker Hub library image; standard trust chain |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-85A-02-SC | Tampering / Spoofing | conda-forge package squatting | mitigate | Channel-only `conda-forge` pin (no `defaults`); all 10 packages verified in RESEARCH.md §Package Legitimacy Audit (HTTP 200 + Phase 43 production use) |
| T-85A-02-DI | Information disclosure | environment-spike.yml committed publicly | accept | No secrets in conda env shape; all packages are public conda-forge artifacts |
</threat_model>

<tasks>

<task type="auto">
  <name>Task 1: Author Dockerfile (ubuntu:22.04 build container)</name>
  <files>.planning/spikes/85a-linux-packaging-spike/Dockerfile</files>
  <read_first>
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Dockerfile shape (lines 509-530) — base image + apt deps + ENTRYPOINT
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Pitfall 1 (lines 287-298) — GLIBC <= 2.35 baseline lock
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Assumption A1 (line 585) — libfuse2 vs libfuse2t64 caveat
  </read_first>
  <acceptance_criteria>
    - file-exists: `test -f .planning/spikes/85a-linux-packaging-spike/Dockerfile`
    - content-grep: `grep -qE '^FROM ubuntu:22\.04' .planning/spikes/85a-linux-packaging-spike/Dockerfile`
    - content-grep: `grep -q 'libfuse2' .planning/spikes/85a-linux-packaging-spike/Dockerfile` (required for linuxdeploy AppImage to self-mount)
    - content-grep: `grep -q 'ca-certificates' .planning/spikes/85a-linux-packaging-spike/Dockerfile` (required for HTTPS toolchain downloads in build.sh)
    - content-grep: `grep -q 'desktop-file-utils' .planning/spikes/85a-linux-packaging-spike/Dockerfile` (required for linuxdeploy .desktop validation)
    - shell-exit: `docker build -f .planning/spikes/85a-linux-packaging-spike/Dockerfile -t ms-spike-build-dry .planning/spikes/85a-linux-packaging-spike/ --no-cache --target=$(grep -c '^FROM ' .planning/spikes/85a-linux-packaging-spike/Dockerfile)*0` is NOT required at this plan (build is Plan 05); syntax validate via `docker build --check` if available
  </acceptance_criteria>
  <action>Create `.planning/spikes/85a-linux-packaging-spike/Dockerfile` per RESEARCH.md §Dockerfile shape. Required content: `FROM ubuntu:22.04` (do NOT add `@sha256:` digest at authorship time — capture digest in Plan 05's build.sh after first pull to keep this file readable; documented in findings as the actual digest used). `RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl wget bzip2 file libfuse2 desktop-file-utils && apt-get clean && rm -rf /var/lib/apt/lists/*`. `WORKDIR /work`. Add a comment block at the top citing the GLIBC <= 2.35 lock and Pitfall 1 + Assumption A1 (libfuse2 vs libfuse2t64) — if A1 turns out false at Plan 05 execution time, the executor patches this file and re-runs. Do NOT add COPY/ENTRYPOINT here — Plan 05's build.sh drives the container with `docker run -v $(pwd):/work` instead, keeping the Dockerfile minimal and host-pwd portable.</action>
  <verify>
    <automated>test -f .planning/spikes/85a-linux-packaging-spike/Dockerfile && grep -qE '^FROM ubuntu:22\.04' .planning/spikes/85a-linux-packaging-spike/Dockerfile && grep -q libfuse2 .planning/spikes/85a-linux-packaging-spike/Dockerfile && grep -q desktop-file-utils .planning/spikes/85a-linux-packaging-spike/Dockerfile</automated>
  </verify>
  <done>Dockerfile committed with FROM line, the 6 apt packages, a comment citing GLIBC 2.35 lock + Pitfall 1 + Assumption A1, and WORKDIR /work.</done>
</task>

<task type="auto">
  <name>Task 2: Author environment-spike.yml (conda-forge env shape)</name>
  <files>.planning/spikes/85a-linux-packaging-spike/environment-spike.yml</files>
  <read_first>
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Conda-forge env shape (lines 52-88) — the 10 packages + channel pin
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Pitfall 7 (lines 361-369) — why Linux env diverges from Phase 43's Windows env (adds gst-libav, gst-python, glib-networking explicitly)
    - .claude/skills/spike-findings-musicstreamer/references/windows-gstreamer-bundling.md (Phase 43 cross-reference for the "same plugin set" PKG-LIN-APP-03 clause)
  </read_first>
  <acceptance_criteria>
    - file-exists: `test -f .planning/spikes/85a-linux-packaging-spike/environment-spike.yml`
    - content-grep: `grep -qE '^name:\s*spike-linux' .planning/spikes/85a-linux-packaging-spike/environment-spike.yml`
    - content-grep: `grep -q '^  - conda-forge' .planning/spikes/85a-linux-packaging-spike/environment-spike.yml` (channel pin)
    - shell-exit: all 10 packages present: `for pkg in python=3.12 pyside6 pygobject gst-python gstreamer gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly gst-libav glib-networking; do grep -F "$pkg" .planning/spikes/85a-linux-packaging-spike/environment-spike.yml || { echo "MISSING $pkg"; exit 1; }; done`
    - shell-exit: no `defaults` channel leakage: `! grep -E '^\s*- defaults' .planning/spikes/85a-linux-packaging-spike/environment-spike.yml`
  </acceptance_criteria>
  <action>Create `.planning/spikes/85a-linux-packaging-spike/environment-spike.yml` verbatim from RESEARCH.md §environment-spike.yml shape (lines 70-86). Exact content (no `defaults`, no `nodefaults`, conda-forge channel ONLY):

```yaml
name: spike-linux
channels:
  - conda-forge
dependencies:
  - python=3.12
  - pyside6
  - pygobject
  - gst-python
  - gstreamer
  - gst-plugins-base
  - gst-plugins-good
  - gst-plugins-bad
  - gst-plugins-ugly
  - gst-libav
  - glib-networking
```

Add a top comment block (YAML `#` comments before `name:`) citing: Phase 43 stack lock (channel-only conda-forge), Pitfall 7 (Linux-specific additions of gst-libav + gst-python + glib-networking), and the conda-forge HTTP 200 audit from RESEARCH.md §Package Legitimacy Audit. Do NOT pin specific package versions — the spike lets conda's solver pick latest compatible; Plan 08's findings doc captures the actual resolved versions for Phase 85's pin decision.</action>
  <verify>
    <automated>test -f .planning/spikes/85a-linux-packaging-spike/environment-spike.yml && python3 -c "import yaml; d = yaml.safe_load(open('.planning/spikes/85a-linux-packaging-spike/environment-spike.yml')); assert d['channels'] == ['conda-forge'], d['channels']; deps = [str(x).split('=')[0] for x in d['dependencies']]; required = {'python','pyside6','pygobject','gst-python','gstreamer','gst-plugins-base','gst-plugins-good','gst-plugins-bad','gst-plugins-ugly','gst-libav','glib-networking'}; missing = required - set(deps); assert not missing, f'MISSING: {missing}'; print('OK', deps)"</automated>
  </verify>
  <done>environment-spike.yml committed; YAML parses; all 10 dependencies present; conda-forge is the only channel; comment block cites Phase 43 stack lock + Pitfall 7.</done>
</task>

<task type="auto">
  <name>Task 3: Author .gitignore + sources README</name>
  <files>.planning/spikes/85a-linux-packaging-spike/.gitignore, .planning/spikes/85a-linux-packaging-spike/README.md</files>
  <read_first>
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Recommended Project Structure (lines 187-205) — artifacts/ + .gitignore convention
    - .claude/skills/spike-findings-musicstreamer/sources/43-gstreamer-windows-spike/README.md (Phase 43 sources README shape)
  </read_first>
  <acceptance_criteria>
    - file-exists: `test -f .planning/spikes/85a-linux-packaging-spike/.gitignore`
    - file-exists: `test -f .planning/spikes/85a-linux-packaging-spike/README.md`
    - content-grep: `grep -q '^artifacts/' .planning/spikes/85a-linux-packaging-spike/.gitignore`
    - content-grep: `grep -qE '\.AppImage' .planning/spikes/85a-linux-packaging-spike/.gitignore`
    - content-grep: `grep -qi 'phase 85a' .planning/spikes/85a-linux-packaging-spike/README.md`
  </acceptance_criteria>
  <action>Create two files. (1) `.planning/spikes/85a-linux-packaging-spike/.gitignore` excluding: `artifacts/`, `*.AppImage`, `*.AppDir/`, `build.log`, `smoke.log`, `*-screenshot.png`, `*-transcript.log`, `verify-pins.lock` (lock file from Plan 03 capturing pinned SHA256s — keep the pin source IN build.sh, the lock file is regenerable). (2) `.planning/spikes/85a-linux-packaging-spike/README.md` with a short orientation block: `# Phase 85a Linux Packaging Spike` heading; one-paragraph summary mirroring CONTEXT.md §Phase Boundary; pointer list to the planned files (`Dockerfile`, `environment-spike.yml`, `hello_world.py`, `AppRun`, `smoke_test.py`, `build.sh`, `verify-pins.sh`, `85A-SPIKE-FINDINGS.md`); explicit note "Findings doc lives in this directory (NOT in .planning/phases/) so `/gsd:spike-wrap-up` can grab the whole tree wholesale into `spike-findings-musicstreamer` skill (Phase 43 convention)."</action>
  <verify>
    <automated>test -f .planning/spikes/85a-linux-packaging-spike/.gitignore && test -f .planning/spikes/85a-linux-packaging-spike/README.md && grep -q '^artifacts/' .planning/spikes/85a-linux-packaging-spike/.gitignore && grep -qi 'phase 85a' .planning/spikes/85a-linux-packaging-spike/README.md</automated>
  </verify>
  <done>.gitignore covers build artifacts + AppImage outputs; README orients future readers and explicitly documents the "findings doc lives here, not in phases dir" convention from Phase 43.</done>
</task>

</tasks>

<verification>
- `docker build -f .planning/spikes/85a-linux-packaging-spike/Dockerfile -t ms-spike-build-syntax-check .planning/spikes/85a-linux-packaging-spike/` runs to completion (Plan 05 actually USES the image; here we're syntax-validating)
- YAML parse of environment-spike.yml succeeds + all 10 required packages present
- .gitignore covers artifacts/ + *.AppImage
</verification>

<success_criteria>
- 3 committed files (Dockerfile, environment-spike.yml, .gitignore) + README.md
- All RESEARCH.md §Standard Stack pinned values present
- Plan 05's build.sh has deterministic input to build the container against
</success_criteria>

<output>
Create `.planning/phases/85A-linux-packaging-spike/85A-02-SUMMARY.md` when done. Capture: Dockerfile apt package list, environment-spike.yml dependency list (final 10), any deviations from RESEARCH.md.
</output>
