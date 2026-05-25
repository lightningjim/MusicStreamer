---
phase: 85A-linux-packaging-spike
plan: 08
type: execute
wave: 6
depends_on:
  - 85A-07
files_modified:
  - .planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md
  - .claude/skills/spike-findings-musicstreamer/SKILL.md
  - .claude/skills/spike-findings-musicstreamer/references/linux-appimage-bundling.md
  - .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/README.md
  - .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/Dockerfile
  - .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/environment-spike.yml
  - .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/build.sh
  - .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/hello_world.py
  - .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/AppRun
  - .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/smoke_test.py
  - .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md
  - .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/create-distroboxes.sh
  - .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/run-smoke.sh
autonomous: false
requirements:
  - SPIKE-85A
tags:
  - spike
  - linux-packaging
  - findings-doc
  - skill-wrap-up
  - cleanup

must_haves:
  truths:
    - "85A-SPIKE-FINDINGS.md exists with per-distro evidence sections (audible+screenshot+transcript) for all three distros"
    - "AppRun env-var template is documented in findings with rationale for each of the 4 success-criteria env vars + Pitfall 3 (GST_REGISTRY_FORK vs GST_REGISTRY_REUSE_PLUGIN_SCANNER) distinction explicit"
    - "Pitfalls 1-10 catalog reproduced in findings + each pitfall's negative-pivot trigger condition recorded"
    - "Phase 85 hand-off manifest enumerated (RESEARCH.md §Phase 85 Hand-Off Manifest verbatim, plus any spike-discovered additions)"
    - "spike-findings-musicstreamer skill APPENDED with new 'Linux AppImage Bundling' feature area (NOT a new skill created)"
    - "Sources copied verbatim into .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/"
    - "Distroboxes torn down per D-04 (ephemeral)"
  artifacts:
    - path: ".planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md"
      provides: "Full findings doc: per-distro evidence, AppRun template, pitfalls catalog, Phase 85 hand-off"
      contains: "GST_REGISTRY_FORK"
      min_lines: 200
    - path: ".claude/skills/spike-findings-musicstreamer/references/linux-appimage-bundling.md"
      provides: "Recompacted reference for future Linux packaging work"
      contains: "linuxdeploy-plugin-gstreamer"
    - path: ".claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/"
      provides: "Verbatim copy of spike sources (Dockerfile, environment-spike.yml, build.sh, hello_world.py, AppRun, smoke_test.py, findings, distrobox scripts)"
      contains: "(directory)"
  key_links:
    - from: "85A-SPIKE-FINDINGS.md"
      to: "Phase 85 plan-phase research input"
      via: "Phase 85's planner reads this doc + the wrapped skill as primary research (per ROADMAP.md research_flag NO on Phase 85)"
      pattern: "Phase 85 Hand-Off"
    - from: "spike-findings-musicstreamer skill"
      to: "future Linux packaging questions"
      via: "Claude auto-loads the skill via CLAUDE.md routing (Skill('spike-findings-musicstreamer'))"
      pattern: "linux-appimage-bundling"
---

<objective>
Author the load-bearing findings doc (`85A-SPIKE-FINDINGS.md`), wrap it into the existing `spike-findings-musicstreamer` skill as a new "Linux AppImage Bundling" feature area, and tear down the ephemeral distroboxes per D-04. This is the spike's exit deliverable — Phase 85 consumes this and the wrapped skill as its primary research input.

Purpose: Implements CONTEXT.md §Wrap-up shape D-Discretion + RESEARCH.md §Wrap-Up Targets (lines 719-746) + Phase 43 precedent (the existing skill demonstrates the verbatim copy pattern + new reference file + SKILL.md findings_index APPEND). The skill APPEND (not create-new) is the critical distinction — the skill already exists from Phase 43.
Output: 1 findings doc + 1 new reference file inside skill + verbatim-copied sources directory inside skill + SKILL.md APPEND + 3 distroboxes torn down.
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/85A-linux-packaging-spike/85A-CONTEXT.md
@.planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md
@.planning/spikes/85a-linux-packaging-spike/host-environment.md
@.planning/spikes/85a-linux-packaging-spike/pins.env
@.planning/spikes/85a-linux-packaging-spike/AppRun
@.planning/spikes/85a-linux-packaging-spike/artifacts/audible-pass-log.md
@.claude/skills/spike-findings-musicstreamer/SKILL.md
@.claude/skills/spike-findings-musicstreamer/references/windows-gstreamer-bundling.md

<interfaces>
<!-- The skill APPEND surface (RESEARCH.md §Wrap-Up Targets lines 719-746). -->

1. NEW directory: .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/
   Verbatim copies: Dockerfile, environment-spike.yml, build.sh, hello_world.py, AppRun,
   smoke_test.py, 85A-SPIKE-FINDINGS.md, create-distroboxes.sh, run-smoke.sh

2. NEW reference file: .claude/skills/spike-findings-musicstreamer/references/linux-appimage-bundling.md
   Sections: Validated patterns / Landmines / Constraints / Origin

3. APPEND to .claude/skills/spike-findings-musicstreamer/SKILL.md:
   - New row in <findings_index> table: "Linux AppImage Bundling"
   - New line in <metadata><processed_spikes>: "- 85a-linux-packaging-spike (Phase 85a; ...)"

4. NO new skill created — the routing in CLAUDE.md already points at spike-findings-musicstreamer.
</interfaces>
</context>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| spike artifacts -> public skill (via QNAP-Gitea-mirror-to-GitHub) | Per MEMORY.md "QNAP pushes are effectively public": SHA256s + container image digests + AppRun template all end up in the public GitHub mirror; SomaFM URLs are public; no secrets in findings doc |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-85A-08-DI | Information disclosure | Findings doc contents go public via QNAP→GitHub mirror | accept | No secrets in findings (SHA256s, AppRun template, plugin BOMs are intentionally public artifacts); MEMORY.md cookie-leak scrub history demonstrates the pipeline scrub posture |
</threat_model>

<tasks>

<task type="auto">
  <name>Task 1: Author 85A-SPIKE-FINDINGS.md (the spike's exit deliverable)</name>
  <files>.planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md</files>
  <read_first>
    - .planning/phases/85A-linux-packaging-spike/85A-CONTEXT.md (entire file — every locked decision is reflected somewhere in findings)
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Phase 85 Hand-Off Manifest (lines 748-774)
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Wrap-Up Targets (lines 719-746) — the exact shape this findings doc must take to be wrap-up-able
    - .planning/spikes/85a-linux-packaging-spike/host-environment.md (Plan 01)
    - .planning/spikes/85a-linux-packaging-spike/pins.env (Plan 03 — three SHA256s for findings)
    - .planning/spikes/85a-linux-packaging-spike/AppRun (Plan 04 — the template to document)
    - .planning/spikes/85a-linux-packaging-spike/artifacts/audible-pass-log.md (Plan 07 — per-distro evidence)
    - .planning/spikes/85a-linux-packaging-spike/artifacts/{ubuntu22,fedora40,tumbleweed}-transcript.log (Plan 06)
    - .planning/spikes/85a-linux-packaging-spike/artifacts/{ubuntu22,fedora40,tumbleweed}-screenshot.png (Plan 07)
    - .claude/skills/spike-findings-musicstreamer/sources/43-gstreamer-windows-spike/43-SPIKE-FINDINGS.md (shape mirror for the findings doc itself)
  </read_first>
  <acceptance_criteria>
    - file-exists: `test -f .planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md`
    - content-grep (per-distro sections, all three): `grep -c '^### Distro: ' .planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md | grep -qE '^3$'` OR `grep -c '^## Distro: ' .planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md | grep -qE '^3$'` (use H2 or H3 — verify-pins.sh-style flexibility)
    - content-grep: `grep -q 'GST_REGISTRY_FORK' .planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md`
    - content-grep: `grep -q 'GST_REGISTRY_REUSE_PLUGIN_SCANNER' .planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md` (Pitfall 3 distinction documented)
    - content-grep: `grep -q 'GLIBC_2\\.35\|GLIBC_2.35' .planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md`
    - content-grep: `grep -q 'linuxdeploy-plugin-gstreamer' .planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md`
    - content-grep: `grep -q 'GSTREAMER_PLUGINS_DIR' .planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md`
    - content-grep: `grep -cE 'Pitfall ([1-9]|10)' .planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md | grep -qE '^[1-9][0-9]+$'` (all 10 pitfalls referenced)
    - content-grep: `grep -q '^## Phase 85 Hand-Off' .planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md`
    - content-grep (3 SHA256 pins documented): `grep -cE '^[a-f0-9]{64}' .planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md | grep -qE '^[3-9]|^[1-9][0-9]+'`
    - content-grep (negative-pivot triggers): `grep -qE 'negative.pivot|STOP and report' .planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md`
    - content-grep (Phase 43 cross-reference): `grep -q 'Phase 43\|windows-gstreamer-bundling' .planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md`
    - file-content (length sanity): `wc -l .planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md | awk '{ exit ($1 >= 200) ? 0 : 1 }'`
  </acceptance_criteria>
  <action>Create `.planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md` with the following section layout (use H2 `## ` for top-level sections, H3 `### ` for per-distro):

```
# Phase 85a Linux Packaging Spike — Findings

> Spike date: <YYYY-MM-DD>
> Spike status: PASS | NEGATIVE-PIVOT (state explicitly which)
> Phase 85 hand-off readiness: READY | DEFERRED-PENDING-FOLLOWUP

## Spike Outcome Summary

(One paragraph: did the linuxdeploy + plugin-conda + plugin-gstreamer toolchain
work end-to-end on all three target distros? Cite the four success criteria
from ROADMAP.md §Phase 85a and report PASS/FAIL on each.)

## Host Environment

(Embed `.planning/spikes/85a-linux-packaging-spike/host-environment.md` content
or include a link to it. Mention any tool fallbacks Kyle used in Plan 01.)

## Toolchain Pins

| Asset | URL | SHA256 | First-Download Date |
|-------|-----|--------|---------------------|
| linuxdeploy | <url> | <64-hex> | <yyyy-mm-dd> |
| linuxdeploy-plugin-conda | <url> | <64-hex> | <yyyy-mm-dd> |
| linuxdeploy-plugin-gstreamer | <url> | <64-hex> | <yyyy-mm-dd> |

`MINICONDA_VERSION` used: <pin value> (rationale per Assumption A2)

## AppRun Env-Var Template

(The full AppRun script, fenced in ```bash```, with annotations on each export
explaining: WHY this env var, which Pitfall it mitigates, and the Phase 43
cross-reference where applicable.

CRITICAL: explicitly document the GST_REGISTRY_FORK=no vs GST_REGISTRY_REUSE_PLUGIN_SCANNER=no
distinction per Pitfall 3 — this is the most likely-to-be-confused finding in the doc.)

## Conda Env Shape (`environment-spike.yml`)

(The 10 packages, with rationale for each Linux-specific addition vs Phase 43 Windows env.
Cite RESEARCH.md §Pitfall 7 for the divergences.)

## Per-Distro Empirical Evidence

### Distro: Ubuntu 22.04 (ms-spike-ubuntu22)

- Programmatic transcript: see `artifacts/ubuntu22-transcript.log`
- Wayland screenshot: see `artifacts/ubuntu22-screenshot.png`
- Audible PASS: see `artifacts/audible-pass-log.md` §"Ubuntu 22.04"
- GLIBC max observed: GLIBC_2.x (must be <= 2.35)
- Elected audio sink: <pulsesink|alsasink|autoaudiosink-chain>
- TLS backend module: <libgiognutls.so|libgioopenssl.so>  (per Open Q3)
- relaunch_time_to_play_s: <N> (vs first launch <M>; delta <D>s; Pitfall 3 mitigation: <PASS|FAIL>)
- Notes: <any anomalies>

### Distro: Fedora 40 (ms-spike-fedora40)

(Same fields as Ubuntu section.)

### Distro: openSUSE Tumbleweed (ms-spike-tumbleweed)

(Same fields as Ubuntu section.)

## Pitfalls Catalog (1-10) + Negative-Pivot Triggers

(Recompacted form of RESEARCH.md §Common Pitfalls. For each Pitfall 1-10:
- ONE-LINE summary
- Trigger condition (what would have made us STOP and report)
- Spike outcome (did this pitfall fire? what mitigation worked?)
- Phase 85 carry-over (if any))

## Open Questions Resolved

(Walk RESEARCH.md §Open Questions 1-5, state which the spike answered.
Q1 is the load-bearing unknown — answer it explicitly.)

## Phase 85 Hand-Off Manifest

(Verbatim from RESEARCH.md §Phase 85 Hand-Off Manifest lines 748-774, plus any
spike-discovered additions or revisions. Each bullet is a deliverable Phase 85
consumes.)

## Wrap-Up

- Skill APPEND: see `.claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/`
- New reference: `references/linux-appimage-bundling.md`
- SKILL.md findings_index updated: <yyyy-mm-dd>
- Distroboxes torn down: <yyyy-mm-dd>
```

Fill in every angle-bracket placeholder with actual captured data from Plans 01-07. The findings doc is the spike's audit surface — if a field is missing, the spike isn't complete.</action>
  <verify>
    <automated>test -f .planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md && grep -q 'GST_REGISTRY_FORK' .planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md && grep -q 'GST_REGISTRY_REUSE_PLUGIN_SCANNER' .planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md && grep -q 'GSTREAMER_PLUGINS_DIR' .planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md && grep -q 'Phase 85 Hand-Off' .planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md && grep -cE 'Pitfall ([1-9]|10)' .planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md | grep -qE '^[1-9][0-9]+$' && { grep -c '^### Distro: ' .planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md | grep -qE '^3$' || grep -c '^## Distro: ' .planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md | grep -qE '^3$'; } && grep -cE '^[a-f0-9]{64}' .planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md | grep -qE '^[3-9]|^[1-9][0-9]+' && wc -l .planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md | awk '{ exit ($1 >= 200) ? 0 : 1 }'</automated>
  </verify>
  <done>Findings doc exists; >= 200 lines; per-distro sections (3) + AppRun template + 10 pitfalls + Phase 85 hand-off + 3 SHA256 pins + GST_REGISTRY_FORK vs REUSE_PLUGIN_SCANNER distinction explicitly documented.</done>
</task>

<task type="checkpoint:human-action" gate="blocking-human">
  <name>Task 2: Run /gsd:spike-wrap-up to APPEND new feature area to existing skill</name>
  <files>.claude/skills/spike-findings-musicstreamer/SKILL.md, .claude/skills/spike-findings-musicstreamer/references/linux-appimage-bundling.md, .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/*</files>
  <read_first>
    - .planning/phases/85A-linux-packaging-spike/85A-RESEARCH.md §Wrap-Up Targets (lines 719-746) — exact APPEND shape
    - .planning/phases/85A-linux-packaging-spike/85A-CONTEXT.md §Claude's Discretion / "Wrap-up shape" — APPEND, never create new
    - .claude/skills/spike-findings-musicstreamer/SKILL.md (current state — table to APPEND to)
    - .claude/skills/spike-findings-musicstreamer/references/windows-gstreamer-bundling.md (sibling reference; new linux-appimage-bundling.md mirrors shape)
    - CLAUDE.md (routing rule confirms Skill('spike-findings-musicstreamer') is the existing target)
  </read_first>
  <what-built>The /gsd:spike-wrap-up workflow APPENDS a new feature area to the existing skill. Per CONTEXT.md D-Discretion: do NOT create a new skill — the spike-findings-musicstreamer skill already exists from Phase 43 and the CLAUDE.md routing already points at it. The wrap-up creates: (1) a new sources/85a-linux-packaging-spike/ directory with verbatim copies; (2) a new references/linux-appimage-bundling.md; (3) appends a row to SKILL.md findings_index table; (4) appends a line to SKILL.md processed_spikes metadata.</what-built>
  <how-to-verify>
    Kyle runs `/gsd:spike-wrap-up` from the project root. The workflow asks Kyle to confirm:
    - target skill name: `spike-findings-musicstreamer` (existing)
    - source dir: `.planning/spikes/85a-linux-packaging-spike/`
    - sub-directory name inside skill: `85a-linux-packaging-spike`
    - findings filename to copy: `85A-SPIKE-FINDINGS.md`
    - new reference file to create: `linux-appimage-bundling.md`

    After wrap-up completes, verify:
    ```
    test -d .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike
    test -f .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/AppRun
    test -f .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md
    test -f .claude/skills/spike-findings-musicstreamer/references/linux-appimage-bundling.md
    grep -q 'Linux AppImage Bundling' .claude/skills/spike-findings-musicstreamer/SKILL.md
    grep -q '85a-linux-packaging-spike' .claude/skills/spike-findings-musicstreamer/SKILL.md
    ```
  </how-to-verify>
  <acceptance_criteria>
    - file-exists: `test -d .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike`
    - file-exists (8 source files copied verbatim): `for f in Dockerfile environment-spike.yml build.sh hello_world.py AppRun smoke_test.py 85A-SPIKE-FINDINGS.md create-distroboxes.sh run-smoke.sh; do test -f .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/$f || { echo "MISSING $f"; exit 1; }; done`
    - file-exists: `test -f .claude/skills/spike-findings-musicstreamer/references/linux-appimage-bundling.md`
    - content-grep: `grep -q 'Linux AppImage Bundling' .claude/skills/spike-findings-musicstreamer/SKILL.md` (findings_index row APPENDED)
    - content-grep: `grep -q 'references/linux-appimage-bundling.md' .claude/skills/spike-findings-musicstreamer/SKILL.md`
    - content-grep: `grep -q '85a-linux-packaging-spike' .claude/skills/spike-findings-musicstreamer/SKILL.md` (processed_spikes line APPENDED)
    - content-grep: `grep -q 'Windows GStreamer Bundling' .claude/skills/spike-findings-musicstreamer/SKILL.md` (Phase 43 row PRESERVED — APPEND not REPLACE)
    - content-grep: `grep -q '43-gstreamer-windows-spike' .claude/skills/spike-findings-musicstreamer/SKILL.md` (Phase 43 processed_spikes line PRESERVED)
    - content-grep (reference file shape): `grep -E '^## (Validated patterns|Landmines|Constraints|Origin)' .claude/skills/spike-findings-musicstreamer/references/linux-appimage-bundling.md | wc -l | awk '{ exit ($1 >= 3) ? 0 : 1 }'`
    - shell-exit (verbatim copy of AppRun): `diff -q .planning/spikes/85a-linux-packaging-spike/AppRun .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/AppRun`
    - manual-checkpoint: Kyle confirms "/gsd:spike-wrap-up complete".
  </acceptance_criteria>
  <action>Kyle runs `/gsd:spike-wrap-up` (the slash-command workflow registered with gsd). The workflow handles the file copying + reference-file authoring + SKILL.md APPEND atomically.

Critical verifications the workflow must satisfy (Claude monitors during wrap-up and rejects on mismatch):
- Phase 43 findings_index row is PRESERVED (APPEND not REPLACE)
- new sources/85a-linux-packaging-spike/ directory exists with all 9 files
- new references/linux-appimage-bundling.md authored with the 4 sections (Validated patterns, Landmines, Constraints, Origin)
- SKILL.md processed_spikes list now has 2 entries (43-... + 85a-...)

If `/gsd:spike-wrap-up` slash command is not available in this environment, Claude executes the APPEND manually per RESEARCH.md §Wrap-Up Targets specification: copy 9 files into sources/, author linux-appimage-bundling.md with the 4 sections (cribbing from windows-gstreamer-bundling.md shape), append the findings_index row to SKILL.md, append the processed_spikes line to SKILL.md.</action>
  <resume-signal>Kyle types "wrap-up complete" once `/gsd:spike-wrap-up` exits cleanly OR Claude completes the manual APPEND.</resume-signal>
  <verify>
    <automated>test -d .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike && test -f .claude/skills/spike-findings-musicstreamer/references/linux-appimage-bundling.md && grep -q 'Linux AppImage Bundling' .claude/skills/spike-findings-musicstreamer/SKILL.md && grep -q '85a-linux-packaging-spike' .claude/skills/spike-findings-musicstreamer/SKILL.md && grep -q 'Windows GStreamer Bundling' .claude/skills/spike-findings-musicstreamer/SKILL.md && grep -q '43-gstreamer-windows-spike' .claude/skills/spike-findings-musicstreamer/SKILL.md && diff -q .planning/spikes/85a-linux-packaging-spike/AppRun .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/AppRun && grep -E '^## (Validated patterns|Landmines|Constraints|Origin)' .claude/skills/spike-findings-musicstreamer/references/linux-appimage-bundling.md | wc -l | awk '{ exit ($1 >= 3) ? 0 : 1 }'</automated>
    <human-check>Kyle confirms wrap-up complete.</human-check>
  </verify>
  <done>Skill APPENDED (not replaced): Phase 43 entries preserved; new Linux AppImage Bundling row in findings_index; new processed_spikes line; new linux-appimage-bundling.md reference; 9 sources copied verbatim; AppRun diff-q-clean between source and skill copy.</done>
</task>

<task type="auto">
  <name>Task 3: Tear down ephemeral distroboxes (D-04)</name>
  <files>(no repo files — runs tools/linux-spike/teardown-distroboxes.sh)</files>
  <read_first>
    - .planning/phases/85A-linux-packaging-spike/85A-CONTEXT.md §D-04 — ephemeral; teardown at end of spike
    - tools/linux-spike/teardown-distroboxes.sh (Plan 06 deliverable)
  </read_first>
  <acceptance_criteria>
    - shell-exit: `bash tools/linux-spike/teardown-distroboxes.sh`
    - shell-exit (none left): `distrobox list 2>/dev/null | grep -c 'ms-spike-' | grep -qE '^0$'`
  </acceptance_criteria>
  <action>Run `bash tools/linux-spike/teardown-distroboxes.sh`. The script idempotently removes ms-spike-ubuntu22, ms-spike-fedora40, ms-spike-tumbleweed. Confirms none remain in `distrobox list`. Note this is autonomous because podman/distrobox rm doesn't require sudo for rootless containers (the engine is podman per D-01).</action>
  <verify>
    <automated>bash tools/linux-spike/teardown-distroboxes.sh && distrobox list 2>/dev/null | grep -c 'ms-spike-' | grep -qE '^0$'</automated>
  </verify>
  <done>All three named distroboxes removed; `distrobox list` shows zero ms-spike-* entries. Phase 85 can recreate from create-distroboxes.sh for its own UAT.</done>
</task>

</tasks>

<verification>
- 85A-SPIKE-FINDINGS.md exists, >= 200 lines, has all required sections + per-distro evidence references
- spike-findings-musicstreamer skill APPENDED (Phase 43 entries preserved, new Linux AppImage Bundling area added)
- 9 source files verbatim-copied into skill's sources/85a-linux-packaging-spike/ subdir
- Distroboxes torn down (D-04)
</verification>

<success_criteria>
- All 4 success criteria from ROADMAP.md §Phase 85a Success Criteria documented in findings as PASS/FAIL with empirical evidence
- Spike findings discoverable by future Claude sessions via Skill('spike-findings-musicstreamer') routing
- Phase 85's planner has all the inputs ROADMAP.md says it should have (research_flag NO is now defensible)
- Repo state is "clean" — no orphan distroboxes, AppImage gitignored, sources in skill have verbatim copies
</success_criteria>

<output>
Create `.planning/phases/85A-linux-packaging-spike/85A-08-SUMMARY.md` when done. Capture: findings doc final line count, skill APPEND verification (Phase 43 row preserved confirmation), distrobox teardown log, any open follow-ups for Phase 85.

This SUMMARY also serves as the phase exit — `/gsd:verify-work 85a` should run cleanly after this commits.
</output>
