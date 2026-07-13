---
phase: 85A-linux-packaging-spike
plan: 08
subsystem: spike-wrap-up
tags:
  - spike
  - linux-packaging
  - findings-doc
  - skill-wrap-up
  - cleanup
  - exit-deliverable
dependency_graph:
  requires:
    - 85A-01-SUMMARY.md (host-environment manifest embedded)
    - 85A-02-SUMMARY.md (Dockerfile + environment-spike.yml in sources/)
    - 85A-03-SUMMARY.md (pins.env + verify-pins.sh in sources/)
    - 85A-04-SUMMARY.md (AppRun + smoke_test.py + hello_world.py + test_url.txt in sources/)
    - 85A-05-SUMMARY.md (build.sh in sources/; 9-round saga preserved)
    - 85A-06-SUMMARY.md (create-distroboxes.sh + run-smoke.sh in sources/; programmatic evidence)
    - 85A-07-SUMMARY.md (audible-pass-log.md; Pitfalls 18+19+20 surfaced)
  provides:
    - .planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md (THE spike exit deliverable; 710 lines)
    - .claude/skills/spike-findings-musicstreamer/references/linux-appimage-bundling.md (recompacted Linux reference)
    - .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/ (12 verbatim source files + README)
    - SKILL.md APPEND (findings_index row + processed_spikes line; Phase 43 entries preserved)
  affects:
    - Phase 85 plan-phase research input (research_flag=NO defensible)
    - Future Claude sessions via Skill('spike-findings-musicstreamer') auto-load routing
tech-stack:
  added: []
  patterns:
    - "Skill APPEND (not REPLACE) — sources/<spike-slug>/ subdir + new references/<area>.md + 2 surgical line APPENDs to SKILL.md"
    - "Findings doc co-located with sources (Phase 43 convention) so the doc travels with the skill"
    - "Per-distro evidence captured BOTH as a summary table AND H3 sections (satisfies plan-checker H3-count gate + reader-friendly density)"
    - "5 raw SHA256 lines explicitly listed for line-anchored grep gates (^[a-f0-9]{64})"
key-files:
  created:
    - .planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md
    - .claude/skills/spike-findings-musicstreamer/references/linux-appimage-bundling.md
    - .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md
    - .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/AppRun
    - .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/Dockerfile
    - .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/README.md
    - .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/build.sh
    - .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/create-distroboxes.sh
    - .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/environment-spike.yml
    - .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/hello_world.py
    - .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/pins.env
    - .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/run-smoke.sh
    - .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/smoke_test.py
    - .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/test_url.txt
    - .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/verify-pins.sh
  modified:
    - .claude/skills/spike-findings-musicstreamer/SKILL.md (surgical APPEND only; Phase 43 entries preserved)
decisions:
  - "APPEND, not replace — Phase 43's findings_index row + processed_spikes line + Source Files listing all preserved verbatim. The skill grows; existing content is untouched."
  - "Findings doc embeds Section 5 BOTH as a summary table AND as 3 H3-headed Distro sub-sections. Reader-friendly density (table = at-a-glance) + plan-checker compliance (PLAN.md acceptance gate counted ^### Distro: H3 headings)."
  - "Authored README.md inside sources/85a-linux-packaging-spike/ mirroring Phase 43's sources/43-gstreamer-windows-spike/README.md shape (file pointer list table + how-the-pieces-fit ASCII diagram + findings doc location explanation)."
  - "linux-appimage-bundling.md mirrors windows-gstreamer-bundling.md's 4-section shape (Validated Patterns / Landmines / Constraints / Origin). Cross-references the Phase 43 Windows analog so Claude can navigate Linux↔Windows invariants."
  - "Distrobox teardown ran via the plan-spec `sg docker -c bash tools/linux-spike/teardown-distroboxes.sh` BUT removed only 1 of 3 (Tumbleweed); rerun WITHOUT sg docker wrapper cleared the remaining 2. Root cause: under sg docker, distrobox elected the docker backend; the containers live under rootless podman. Final `distrobox list` returns zero ms-spike-* entries — D-04 satisfied."
metrics:
  duration: "~25 min (3 tasks + verification + commits)"
  completed: "2026-05-26"
  pitfalls_catalogued: 20
  findings_doc_lines: 710
  skill_files_added: 14
  source_files_copied_verbatim: 12
requirements:
  - SPIKE-85A
---

# Phase 85A Plan 08: Spike Exit Deliverable Summary

The spike's load-bearing exit deliverable: a 710-line `85A-SPIKE-FINDINGS.md` consolidating all 20 pitfalls, per-distro empirical evidence, the annotated AppRun template, and a Phase 85 hand-off manifest — plus a surgical APPEND to the `spike-findings-musicstreamer` skill that preserves Phase 43's entries verbatim while adding the new Linux AppImage Bundling feature area + 12-file verbatim sources tree.

## Goal

Author the load-bearing findings doc (`85A-SPIKE-FINDINGS.md`), wrap it into the existing `spike-findings-musicstreamer` skill as a new "Linux AppImage Bundling" feature area, and tear down the ephemeral distroboxes per D-04. Phase 85's planner consumes both deliverables as its primary research input (ROADMAP.md `research_flag=NO` on Phase 85 depends on this).

## What was built

### 1. `85A-SPIKE-FINDINGS.md` — the spike's exit deliverable (710 lines)

10 required sections per PLAN.md:

1. **Spike Outcome Summary** — All four ROADMAP.md success criteria pass; 20 pitfalls catalogued.
2. **Host Environment** — Reproducibility prefix (Ubuntu 26.04, kernel 7.0.0-15, GLIBC 2.43, podman 5.7.0, distrobox 1.8.2.4) — also embedded verbatim in Section 10.
3. **Toolchain Pins** — 3 SHA256-pinned raw-GitHub assets + Miniforge3 + Approach P patched plugin-conda SHA, plus 11-package conda-forge env spec.
4. **The Validated Build Pipeline** — Full ASCII diagram + load-bearing docker-run flag rationale.
5. **AppRun Template — Annotated** — Full template fenced verbatim + line-by-line rationale for each export (GST_REGISTRY_FORK vs GST_REGISTRY_REUSE_PLUGIN_SCANNER distinction explicit; SSL_CERT_FILE Pitfall 17 documented).
6. **Cross-Distro Empirical Evidence (Programmatic)** — Summary table AND 3 H3-headed Distro sub-sections (Ubuntu 22.04, Fedora 40, Tumbleweed).
7. **Audible-PASS Evidence (Ubuntu only — partial per wrap-now)** — Pitfall 3 empirically verified (relaunch 4.7× FASTER); Pitfalls 18+19 surface narratives.
8. **Pitfalls Catalog (1–20)** — Each entry: class, what, manifests, mitigation, negative-pivot trigger, Phase 85 action. Plus 6 supplementary mini-pitfalls from Plan 06 distrobox-runtime fixes.
9. **Open Questions Resolved** — RESEARCH.md Q1-Q5 all answered.
10. **Phase 85 Hand-Off Manifest** — 10 ready-for-copy-paste actionable items + deliberately-left-for-Phase-85 list.
11. **The 9-Round Plan 05 Saga** — Round-by-round table for discovery archaeology.
12. **Host Environment Captured at Spike Time** — Verbatim mirror of `.planning/spikes/85a-linux-packaging-spike/host-environment.md`.
13. **Wrap-Up** — Skill APPEND target documented.

### 2. Skill APPEND — surgical, not replacement

**New reference file:** `.claude/skills/spike-findings-musicstreamer/references/linux-appimage-bundling.md` — mirrors `windows-gstreamer-bundling.md` shape (Validated Patterns / Landmines / Constraints / Origin); recompacted all 20 pitfalls + AppRun template + plugin invocation order + cross-references the Phase 43 Windows analog.

**New sources subdir:** `.claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/` with 13 files:
- 10 verbatim spike sources: `Dockerfile`, `environment-spike.yml`, `pins.env`, `verify-pins.sh`, `build.sh`, `hello_world.py`, `AppRun`, `smoke_test.py`, `test_url.txt`, `85A-SPIKE-FINDINGS.md`
- 2 distrobox driver scripts (verbatim from `tools/linux-spike/`): `create-distroboxes.sh`, `run-smoke.sh`
- 1 new orienting `README.md` (mirrors Phase 43 source-tree README shape)

**SKILL.md surgical APPEND:**
- New row in `findings_index` table: `Linux AppImage Bundling | references/linux-appimage-bundling.md | <key finding>`
- New line in `<metadata><processed_spikes>`: `- 85a-linux-packaging-spike (Phase 85a; 2026-05-26 — Linux AppImage build via linuxdeploy + plugin-conda + plugin-gstreamer + conda-forge; 20 pitfalls catalogued)`
- Phase 43 entries (Windows GStreamer Bundling row + Qt-GLib row + 43-gstreamer-windows-spike processed_spikes line + Source Files listing) **preserved verbatim**.
- AppRun verbatim-copy gate: `diff -q .planning/.../AppRun .claude/.../AppRun` returns clean.

### 3. Distroboxes torn down (D-04)

All three ephemeral distroboxes removed. The plan-spec invocation `sg docker -c 'bash tools/linux-spike/teardown-distroboxes.sh'` removed only Tumbleweed (under `sg docker`, distrobox elected the docker backend; the containers actually lived under rootless podman). Rerun without the `sg docker` wrapper cleared the remaining 2. Final `distrobox list` returns zero `ms-spike-*` entries.

## Key files

### Created

- `.planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md` (710 lines)
- `.claude/skills/spike-findings-musicstreamer/references/linux-appimage-bundling.md`
- `.claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/{README.md,Dockerfile,environment-spike.yml,pins.env,verify-pins.sh,build.sh,hello_world.py,AppRun,smoke_test.py,test_url.txt,create-distroboxes.sh,run-smoke.sh,85A-SPIKE-FINDINGS.md}` (13 files)

### Modified

- `.claude/skills/spike-findings-musicstreamer/SKILL.md` — surgical 2-line APPEND (findings_index row + processed_spikes line)

## Pitfalls captured (one-liner each)

1. **Pitfall 1** — GLIBC baseline drift (ubuntu:22.04 mitigates; objdump scan verifies)
2. **Pitfall 2** — plugin-gstreamer defaults to multiarch paths (`GSTREAMER_PLUGINS_DIR` override)
3. **Pitfall 3** — `GST_REGISTRY_FORK=no` ≠ `GST_REGISTRY_REUSE_PLUGIN_SCANNER=no` (different flags; spike empirically verified 4.7× relaunch speedup)
4. **Pitfall 4** — HTTPS needs `GIO_EXTRA_MODULES` (glib-networking TLS modules)
5. **Pitfall 5** — distrobox passes Wayland/PipeWire but not GTK/Qt themes (cosmetic)
6. **Pitfall 6** — `MINICONDA_VERSION` defaults to "latest" (pin Miniforge3 tag)
7. **Pitfall 7** — Linux conda env needs `gst-libav` + `gst-python` + `glib-networking` explicit
8. **Pitfall 8** — plugin-gstreamer dormancy (SHA-pin mitigates supply chain; "future-proofed via variable substitution" softens dormancy)
9. **Pitfall 9** — SomaFM ICY metadata parse (TAG event timestamp captured)
10. **Pitfall 10** — PipeWire vs PulseAudio sink election (autoaudiosink on all 3 distros)
11. **Pitfall 11** — FUSE-mount fails in rootless container (`--appimage-extract-and-run`)
12. **Pitfall 12** — Docker bridge + parallel conda fetch = SSL errors (`--network=host` + `CONDA_FETCH_THREADS=1`)
13. **Pitfall 13** — Miniconda3 condarc trips conda 24.x ToS gate (Approach P sed-patch)
13b. **Pitfall 13b** — plugin-conda's `touch -d '@0' + wget -N` defeats `CONDA_DOWNLOAD_DIR` cache override
14. **Pitfall 14** — `LD_LIBRARY_PATH` required for linuxdeploy ELF dep walker (build-time)
15. **Pitfall 15** — ubuntu:22.04 binutils 2.38 `strip` segfaults on newer conda-forge .so (`CONDA_SKIP_CLEANUP=strip`)
16. **Pitfall 16** — `strings | grep ^GLIBC_` false positives on compressed squashfs (objdump DT_VERNEED scan)
17. **Pitfall 17** — Bundled OpenSSL doesn't see conda's CA bundle (`SSL_CERT_FILE` export; spike's `--assert-tls` passed misleadingly)
18. **Pitfall 18** — CLI screenshot tools broken on GNOME 49+ Wayland (use xdg-desktop-portal D-Bus API)
19. **Pitfall 19** — PipeWire routing non-determinism for re-extracted AppImage (explicit PULSE_PROP app identity + FUSE self-mount for production)
20. **Pitfall 20** — AppRun's `exec` line hardcoded to hello_world.py (parameterize for production)

Plus 6 supplementary mini-pitfalls from Plan 06 (distrobox `--unshare-devsys`, `--additional-packages binutils`, Tumbleweed `--pre-init-hooks` zypp shim, stdin-piped bash for heredoc literal-quote collision, `--appimage-extract` + manual env-export workaround for Pitfall 20, `--check-glibc` against extracted python binary not raw squashfs payload).

## Phase 85 hand-off summary

10 numbered actionable items in `85A-SPIKE-FINDINGS.md` §"Phase 85 Hand-Off Manifest":

1. Copy `build.sh` verbatim (8 in-script mitigations preserved)
2. Copy `Dockerfile` verbatim (GLIBC ≤ 2.35 baseline)
3. Adapt `environment-spike.yml` → `environment.yml` (ADD v2.2 deps)
4. Copy `pins.env` + `verify-pins.sh` verbatim (supply-chain)
5. Copy AppRun template + replace exec line with `python -m musicstreamer` + ADD `PULSE_PROP` export (Pitfall 19)
6. Copy distrobox driver scripts for CI/UAT
7. Inherit Pitfalls 1-20 catalog as PLAN.md research input
8. Wire `GLIBC_2.35` literal into `tests/test_packaging_spec.py` source-grep (PKG-LIN-APP-08)
9. Inherit `hello_world.py` shape for `tests/test_packaging_linux_smoke.py` if added
10. Inherit 188-plugin BOM as `tools/check_bundle_plugins_linux.py` baseline

Deliberately left for Phase 85: real `musicstreamer/` app bundling, `.desktop`+icon+MIME, production FUSE self-mount path, plugin-conda env.yml bypass investigation, `xdg-desktop-portal-gnome` CI screenshots, `docker info` daemon probe, zsync, MPRIS2, .pls/.m3u MIME-association NEGATIVE test, AAC playback test, AppImage signing, GitHub Actions CI replication.

## Tasks completed

| Task | Name | Type | Commit | Files |
|------|------|------|--------|-------|
| 1    | Author 85A-SPIKE-FINDINGS.md (the spike's exit deliverable) | auto | `c6e4836` | 1 file, 710 lines |
| 2    | Wrap into spike-findings-musicstreamer skill (APPEND) | auto (manual APPEND per plan fallback) | `651cff1` | 15 files (1 modified + 14 new) |
| 3    | Tear down 3 distroboxes (D-04) | auto | (no commit; `distrobox rm`) | 0 files; `distrobox list` returns 0 ms-spike-* |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocker] PLAN.md acceptance gate requires `^[a-f0-9]{64}` line-anchored SHA256s**

- **Found during:** Task 1 verification — initial draft had SHA256s only inside markdown table cells (with leading `|`), failing `grep -cE '^[a-f0-9]{64}'` count gate.
- **Fix:** Added a fenced code block listing the 5 raw SHA256s (one per line) alongside the table — table preserves readability, code block satisfies the line-anchored grep gate.
- **Files modified:** `.planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md`
- **Commit:** Folded into `c6e4836` (the Task 1 commit; pre-commit verification re-ran all gates green).

**2. [Rule 3 — Blocker] PLAN.md acceptance gate requires `^### Distro: ` or `^## Distro: ` H2/H3 headings (count=3)**

- **Found during:** Task 1 verification — initial draft had a per-distro summary table in Section 5 (as the user's objective spec described) but no H2/H3 per-distro headings.
- **Fix:** Added 3 H3 sub-sections (`### Distro: Ubuntu 22.04`, `### Distro: Fedora 40`, `### Distro: openSUSE Tumbleweed`) immediately after the summary table — table for at-a-glance density, H3 sub-sections for plan-checker compliance + reader navigation.
- **Files modified:** `.planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md`
- **Commit:** Folded into `c6e4836`.

**3. [Rule 3 — Blocker] `.claude/` is in root `.gitignore` but skill files were force-tracked in Phase 43**

- **Found during:** Task 2 staging — `git add .claude/skills/...` rejected new files (`.claude/` is gitignored at line 23).
- **Fix:** Used `git add -f` for new skill files (mirrors how Phase 43 originally added the existing tracked files; only NEW additions need `-f`; the MODIFIED `SKILL.md` was already tracked so plain `git add` worked).
- **Files modified:** none — staging policy adjustment only.
- **Commit:** Reflected in `651cff1`.

**4. [Rule 3 — Blocker] `sg docker -c 'bash teardown-distroboxes.sh'` only removed 1 of 3 distroboxes**

- **Found during:** Task 3 execution — Tumbleweed removed under `sg docker` wrapper; Ubuntu + Fedora still visible to `distrobox list`.
- **Root cause:** Under `sg docker`, the distrobox CLI elected the docker engine backend (which had no `ms-spike-*` containers); the actual containers lived under rootless podman.
- **Fix:** Re-ran `bash tools/linux-spike/teardown-distroboxes.sh` WITHOUT the `sg docker` wrapper. distrobox then elected the podman backend (matching Plan 06's create context) and cleanly removed Ubuntu + Fedora.
- **Files modified:** none.
- **Commit:** N/A (teardown is not committed per Task 3 spec).
- **Phase 85 note:** Document in CI scripts that distrobox teardown must run with the same backend context as creation. Either always wrap both or never wrap either; mixing produces visibility splits.

### No Rule 4 (architectural) deviations.

## Threat Surface Scan

No new trust boundaries introduced by Plan 08. The findings doc + skill APPEND surface threat boundary `T-85A-08-DI` (findings doc → public via QNAP→GitHub mirror) is `accept` per the plan's threat register — no secrets in findings (SHA256s, AppRun template, plugin BOMs are intentionally public artifacts; per MEMORY.md's 2026-05-04 cookie-leak scrub, the pipeline's scrub posture is established).

## Known Stubs

None. All 13 new skill source files are verbatim copies of spike sources from Plans 02-06. The findings doc is fully populated (no `<TBD>` or `<placeholder>` tokens). SKILL.md additions are functional rows/lines, not stubs.

## Self-Check: PASSED

- [x] FOUND `.planning/spikes/85a-linux-packaging-spike/85A-SPIKE-FINDINGS.md` (710 lines >= 200)
- [x] FOUND `GST_REGISTRY_FORK` in findings doc
- [x] FOUND `GST_REGISTRY_REUSE_PLUGIN_SCANNER` in findings doc (Pitfall 3 distinction)
- [x] FOUND `GSTREAMER_PLUGINS_DIR` in findings doc
- [x] FOUND `^## Phase 85 Hand-Off` section
- [x] FOUND 3× `^### Distro: ` H3 headings
- [x] FOUND 5× `^[a-f0-9]{64}` line-anchored SHA256s
- [x] FOUND >10 `Pitfall ([1-9]|10)` references (counted 32)
- [x] FOUND `negative.pivot|STOP and report` in findings doc
- [x] FOUND Phase 43 cross-reference (`Phase 43` + `windows-gstreamer-bundling`)
- [x] FOUND commit `c6e4836` (feat(85A-08): author SPIKE-FINDINGS.md)
- [x] FOUND `.claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/` directory
- [x] FOUND all 12 verbatim sources + new README (13 files total in sources subdir)
- [x] FOUND `.claude/skills/spike-findings-musicstreamer/references/linux-appimage-bundling.md`
- [x] FOUND all 4 sections in reference file (`^## (Validated Patterns|Landmines|Constraints|Origin)`)
- [x] FOUND new SKILL.md row `Linux AppImage Bundling`
- [x] FOUND new SKILL.md processed_spikes line `85a-linux-packaging-spike`
- [x] FOUND PRESERVED `Windows GStreamer Bundling` row in SKILL.md (Phase 43 not deleted)
- [x] FOUND PRESERVED `43-gstreamer-windows-spike` processed_spikes line (Phase 43 not deleted)
- [x] AppRun diff-q-clean between source and skill copy
- [x] FOUND commit `651cff1` (feat(spike-findings): append Linux AppImage Bundling feature area to skill)
- [x] CONFIRMED `distrobox list` returns 0 `ms-spike-*` entries (D-04 satisfied)
- [x] STATE.md / ROADMAP.md NOT modified (orchestrator owns those)
