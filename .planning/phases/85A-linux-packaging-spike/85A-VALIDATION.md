---
phase: 85a
slug: linux-packaging-spike
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-25
plans_written: 2026-05-25
revised: 2026-05-25  # Iteration 1 — checker BLOCKER #1 + 4 warnings applied
---

# Phase 85a — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
>
> **Spike-specific framing:** This phase produces a hello-world AppImage + findings doc, NOT production code in `musicstreamer/`. The validation harness is `smoke_test.py` itself — not pytest. Production-style test infrastructure is Phase 85's surface. The "tests" here are pipeline-state assertions, shell exit codes, and human-confirmed audible PASS.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | smoke_test.py (Python, self-contained — no pytest) + bash assertions in `build.sh` / `verify-pins.sh` / `run-smoke.sh` |
| **Config file** | None — Wave 0 installs distrobox + gnome-screenshot + grim host-side |
| **Quick run command** | `bash .planning/spikes/85a-linux-packaging-spike/build.sh && bash tools/linux-spike/run-smoke.sh ubuntu22` |
| **Full suite command** | `bash tools/linux-spike/run-smoke.sh all` (runs smoke + GLIBC + plugin-discovery across all three distroboxes) |
| **Estimated runtime** | ~15-25 min (build container build + AppImage assembly + per-distro smoke + manual audible loop) |

---

## Sampling Rate

- **After every task commit:** Run the relevant fragment (build → smoke for one distro → findings transcript append)
- **After every plan wave:** Run `bash tools/linux-spike/run-smoke.sh all` against all three distroboxes
- **Before `/gsd:verify-work`:** All three distros must produce audible+screenshot+transcript evidence; AppRun template captured; SPIKE-FINDINGS.md committed; spike wrapped into `spike-findings-musicstreamer` skill
- **Max feedback latency:** ~5 min per smoke cycle per distro (Wave 0 install one-time)

---

## Per-Task Verification Map

> Authoritative after plan write 2026-05-25. Each task is mapped to its automated verification command (or the explicit manual checkpoint when none possible).

| Task ID | Plan | Wave | Spike Output | Verification Type | Automated Command / Manual-Checkpoint | Status |
|---------|------|------|--------------|-------------------|---------------------------------------|--------|
| 85A-01-01 | 01 | 0 | distrobox + gnome-screenshot + grim installed (sudo apt) | manual-checkpoint + shell-exit | `command -v distrobox && command -v gnome-screenshot && command -v grim` + Kyle "installed" | ⬜ pending |
| 85A-01-02 | 01 | 0 | host-environment.md manifest | file-content-grep | `test -f host-environment.md && grep -cE '^## (GLIBC\|podman\|distrobox\|gnome-screenshot\|Session)' host-environment.md` | ⬜ pending |
| 85A-02-01 | 02 | 1 | Dockerfile (ubuntu:22.04 + libfuse2 + ca-certificates + desktop-file-utils) | file-content-grep | `grep -qE '^FROM ubuntu:22\.04' Dockerfile && grep -q libfuse2 Dockerfile && grep -q desktop-file-utils Dockerfile` | ⬜ pending |
| 85A-02-02 | 02 | 1 | environment-spike.yml (10 packages, conda-forge channel-only) | yaml-parse | `python3 -c "import yaml; d=yaml.safe_load(open('environment-spike.yml')); assert d['channels'] == ['conda-forge']"` + 10-package presence check | ⬜ pending |
| 85A-02-03 | 02 | 1 | .gitignore + README.md | file-exists + content-grep | `test -f .gitignore && grep -q '^artifacts/' .gitignore && test -f README.md` | ⬜ pending |
| 85A-03-01 | 03 | 1 | pins.env (3 SHA256s + URL + MINICONDA_VERSION) | manual-checkpoint (legitimacy gate) + content-grep | `grep -cE '_SHA256=[a-f0-9]{64}$' pins.env \| grep -qE '^3$'` + Kyle "approved" | ⬜ pending |
| 85A-03-02 | 03 | 1 | verify-pins.sh drift-guard | shell-exit | `bash verify-pins.sh` exits 0 + mutation test | ⬜ pending |
| 85A-04-01 | 04 | 2 | hello_world.py (playbin3 + GLib.MainLoop, no Qt bridge) | shell-exit + content-grep | `python3 -c "import ast; ast.parse(open('hello_world.py').read())"` + `! grep QObject hello_world.py` + `python3 hello_world.py 2>&1 \| grep SPIKE_FAIL.*usage` | ⬜ pending |
| 85A-04-02 | 04 | 2 | AppRun template (8 exports including GST_REGISTRY_FORK=no, paths under usr/conda/) | bash-syntax + content-grep | `bash -n AppRun && grep -qE 'export GST_REGISTRY_FORK=' AppRun && grep -qE 'APPDIR.*usr/conda/lib/gstreamer-1.0' AppRun && grep '^#' AppRun \| grep -q GST_REGISTRY_REUSE_PLUGIN_SCANNER` | ⬜ pending |
| 85A-04-03 | 04 | 2 | smoke_test.py + test_url.txt (4 SomaFM URLs) | shell-exit + content-grep | `python3 -c "import ast; ast.parse(open('smoke_test.py').read())"` + 4-URL check on test_url.txt | ⬜ pending |
| 85A-05-01 | 05 | 3 | desktop/.desktop + .svg placeholder | file-content-grep | `grep -q '^Exec=AppRun' desktop/musicstreamer-spike.desktop && head -1 desktop/musicstreamer-spike.svg \| grep -qiE '<\?xml\|<svg'` | ⬜ pending |
| 85A-05-02 | 05 | 3 | build.sh produces AppImage with GLIBC <= 2.35 | shell-exit + GLIBC-grep + manual-checkpoint | `bash build.sh && test -f artifacts/MusicStreamer-spike-x86_64.AppImage && strings artifacts/MusicStreamer-spike-x86_64.AppImage \| grep -E '^GLIBC_[0-9]+\.[0-9]+$' \| sort -V \| tail -1 \| grep -qE 'GLIBC_2\.(1[0-9]\|2[0-9]\|3[0-5])$'` + Kyle "built" | ⬜ pending |
| 85A-06-01 | 06 | 4 | create + teardown distrobox scripts; 3 named containers created | shell-exit | `bash create-distroboxes.sh && distrobox list \| grep -c 'ms-spike-' \| grep -qE '^3$'` | ⬜ pending |
| 85A-06-02 | 06 | 4 | Per-distro programmatic smoke transcripts (3 SPIKE_OK + GLIBC + plugin-resolved) | shell-exit + content-grep | `bash run-smoke.sh all && for d in ubuntu22 fedora40 tumbleweed; do grep -q SPIKE_OK artifacts/${d}-transcript.log && grep -qE 'plugin_resolved=.avdec_aac' artifacts/${d}-transcript.log; done` | ⬜ pending |
| 85A-07-01 | 07 | 5 | Audible PASS protocol — Ubuntu 22.04 (D-06 7-step + D-08 step 8 HTTPS audible + screenshot) | manual-checkpoint + PNG-magic + grep | `file artifacts/ubuntu22-screenshot.png \| grep -qi PNG` + `grep -q 'https_audible: PASS' artifacts/audible-pass-log.md` + Kyle "ubuntu22 audible OK + HTTPS audible PASS" + relaunch_time_to_play_s logged + step 8 HTTPS URL logged | ⬜ pending |
| 85A-07-02 | 07 | 5 | Audible PASS protocol — Fedora 40 | manual-checkpoint + PNG-magic | `file artifacts/fedora40-screenshot.png \| grep -qi PNG` + Kyle "fedora40 audible OK" | ⬜ pending |
| 85A-07-03 | 07 | 5 | Audible PASS protocol — Tumbleweed | manual-checkpoint + PNG-magic | `file artifacts/tumbleweed-screenshot.png \| grep -qi PNG` + Kyle "tumbleweed audible OK" | ⬜ pending |
| 85A-08-01 | 08 | 6 | 85A-SPIKE-FINDINGS.md with per-distro + pitfalls + Phase 85 hand-off | content-grep (multi-assertion) | 3 distro sections + GST_REGISTRY_FORK + GST_REGISTRY_REUSE_PLUGIN_SCANNER + 10 pitfalls + 3 SHA256 lines + >= 200 lines | ⬜ pending |
| 85A-08-02 | 08 | 6 | Skill APPEND (9 files copied verbatim; new reference; SKILL.md APPEND; Phase 43 preserved) | shell-exit + diff-q + manual | `diff -q AppRun .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/AppRun` + grep "Windows GStreamer Bundling" SKILL.md (preserved) + grep "Linux AppImage Bundling" SKILL.md (added) + Kyle "wrap-up complete" | ⬜ pending |
| 85A-08-03 | 08 | 6 | Distrobox teardown (D-04 ephemeral) | shell-exit | `bash tools/linux-spike/teardown-distroboxes.sh && distrobox list 2>/dev/null \| grep -c 'ms-spike-' \| grep -qE '^0$'` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Coverage:** 19 tasks → each has either an automated command, an explicit human-checkpoint, or both. No "blind" tasks. Audible PASS tasks (07-01/02/03) and skill APPEND (08-02) require human confirmation in addition to programmatic checks (PNG magic-byte sanity / diff-q verbatim copy). No three-task run without verification.

---

## Wave 0 Requirements

- [ ] **Host tooling** — `podman` (already installed), `distrobox`, `gnome-screenshot`, `grim`, `script` available on the Wayland host (Plan 01 Task 1)
- [ ] **Pin verification script** — `.planning/spikes/85a-linux-packaging-spike/verify-pins.sh` (Plan 03 Task 2) — re-fetches SHA256 of pinned linuxdeploy + plugin AppImages and fails-fast on drift
- [ ] **No production test framework needed** — spike validates via shell exit codes + smoke_test.py state-machine; pytest tests are Phase 85's surface

*Existing test infrastructure (musicstreamer's 1462 pytest suite) is NOT exercised by this spike — the spike runs entirely outside the production code path.*

---

## Manual-Only Verifications

| Behavior | Plan/Task | Why Manual | Test Instructions |
|----------|-----------|------------|-------------------|
| `sudo apt install distrobox gnome-screenshot grim` | 85A-01-01 | sudo gate; Claude sandbox cannot run sudo interactively | Plan 01 Task 1 how-to-verify block |
| Toolchain legitimacy spot-check (org owns repo + commit-date sanity + no slop) | 85A-03-01 | Per system prompt §package legitimacy gate; raw GitHub `.sh` assets have no registry verification surface | Plan 03 Task 1 how-to-verify block |
| build.sh produces AppImage (full container build + linuxdeploy invocation) | 85A-05-02 | Build runtime is ~10 min + Claude needs to see exit-code result; checkpoint confirms success or negative-pivot capture | Plan 05 Task 2 how-to-verify block |
| Audible playback on Ubuntu 22.04 distrobox | 85A-07-01 | Audio fidelity cannot be programmatically asserted; requires Kyle's ears on host pipewire | Plan 07 Task 1 how-to-verify block (D-06 7-step protocol) |
| Audible playback on Fedora 40 distrobox | 85A-07-02 | Same; Pitfall 10 sink-election is per-distro | Plan 07 Task 2 |
| Audible playback on openSUSE Tumbleweed distrobox | 85A-07-03 | Same; Tumbleweed is the third (hardest) distro per CONTEXT.md D-05 rationale | Plan 07 Task 3 |
| Wayland screenshot captures running AppImage window | 85A-07-01..03 | Visual confirmation; tool-dependent on session compositor | `gnome-screenshot --window` (primary) or `grim` (fallback per Assumption A6) |
| HTTPS variant audibly plays (TLS bundle coverage; D-08) | 85A-07-01 step 8 (Ubuntu primary) | TLS path failure mode is silent at smoke level; require Kyle's ear-on-PipeWire confirmation | Plan 07 Task 1 step 8 (8-step protocol): relaunch AppImage with `https://ice6.somafm.com/groovesalad-128-mp3`, confirm 10s audible playback, log `https_audible: PASS` + URL to `audible-pass-log.md` under `## Ubuntu 22.04` |
| /gsd:spike-wrap-up APPEND completed | 85A-08-02 | Slash-command workflow; Claude monitors output but human invokes | Plan 08 Task 2 |

---

## Validation Sign-Off

- [x] All spike outputs have either shell-exit verification or manual-only checkpoint (19/19 tasks mapped)
- [x] Sampling continuity: no 3 consecutive tasks without verification (W4 audible loop punctuates programmatic checks, every task in 05/06/08 has shell-exit + Wave 5 has PNG-magic + checkpoint)
- [x] Wave 0 covers all host-side prerequisites (distrobox, gnome-screenshot, grim — Plan 01)
- [x] No watch-mode flags
- [x] Feedback latency: each per-distro smoke cycle < 5 min
- [x] `nyquist_compliant: true` flipped in frontmatter (per quality-gate from planning context)
- [x] Spike findings include per-distro evidence section with all three artifacts (audible confirmation, screenshot, transcript) — Plan 08 Task 1 enforces grep gates
- [x] AppRun template documents all four env vars + the research-discovered `GST_REGISTRY_REUSE_PLUGIN_SCANNER` vs `GST_REGISTRY_FORK` distinction (Plan 04 Task 2 + Plan 08 Task 1)

**Approval:** approved (planner sign-off 2026-05-25)
