---
phase: 85a
slug: linux-packaging-spike
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-25
---

# Phase 85a — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
>
> **Spike-specific framing:** This phase produces a hello-world AppImage + findings doc, NOT production code in `musicstreamer/`. The validation harness is `smoke_test.py` itself — not pytest. Production-style test infrastructure is Phase 85's surface. The "tests" here are pipeline-state assertions, shell exit codes, and human-confirmed audible PASS.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | smoke_test.py (Python, self-contained — no pytest) + bash assertions in `build.sh` / `run-smoke.sh` |
| **Config file** | None — Wave 0 installs distrobox + podman (host-side) + gnome-screenshot + grim |
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

> Filled by gsd-planner after PLAN.md files are written. Initial template — planner overrides.

| Task ID | Plan | Wave | Spike Output | Verification Type | Automated Command | File Exists | Status |
|---------|------|------|--------------|-------------------|-------------------|-------------|--------|
| 85A-01-01 | 01 | 0 | Host tooling installed | shell-exit | `which podman distrobox gnome-screenshot grim` | ✅ | ⬜ pending |
| 85A-02-01 | 02 | 1 | Dockerfile + environment-spike.yml | file-exists | `test -f .planning/spikes/85a-linux-packaging-spike/Dockerfile -a -f .planning/spikes/85a-linux-packaging-spike/environment-spike.yml` | ❌ W1 | ⬜ pending |
| 85A-03-01 | 03 | 1 | Pinned toolchain assets | sha256-check | `bash .planning/spikes/85a-linux-packaging-spike/verify-pins.sh` | ❌ W1 | ⬜ pending |
| 85A-04-01 | 04 | 2 | hello_world.py + AppRun template + smoke_test.py | file-exists + shell-exit | `python3 -c 'import ast; ast.parse(open(".planning/spikes/85a-linux-packaging-spike/hello_world.py").read())'` | ❌ W2 | ⬜ pending |
| 85A-05-01 | 05 | 2 | build.sh produces AppImage | shell-exit + GLIBC | `bash .planning/spikes/85a-linux-packaging-spike/build.sh && strings ./MusicStreamer-spike-x86_64.AppImage \| grep GLIBC_ \| sort -V \| tail -1 \| grep -E 'GLIBC_2\\.(1\|2[0-9]\|3[0-5])$'` | ❌ W2 | ⬜ pending |
| 85A-06-01 | 06 | 3 | distrobox recreate-scripts | file-exists + shell-exit | `bash tools/linux-spike/create-distroboxes.sh --dry-run` | ❌ W3 | ⬜ pending |
| 85A-07-01 | 07 | 4 | Plugin discovery per distro | shell-exit inside distrobox | `distrobox enter ms-spike-ubuntu22 -- ./MusicStreamer-spike-x86_64.AppImage --gst-inspect avdec_aac aacparse` | ❌ W4 | ⬜ pending |
| 85A-08-01 | 08 | 4 | Programmatic playback PASS per distro | smoke-state-machine | `distrobox enter ms-spike-{distro} -- python smoke_test.py --uri http://ice1.somafm.com/groovesalad-128-mp3 --timeout 30` | ❌ W4 | ⬜ pending |
| 85A-08-02 | 08 | 4 | HTTPS variant PASS (TLS bundle coverage) | smoke-state-machine | `distrobox enter ms-spike-ubuntu22 -- python smoke_test.py --uri https://ice6.somafm.com/groovesalad-128-mp3 --timeout 30` | ❌ W4 | ⬜ pending |
| 85A-09-01 | 09 | 4 | Audible PASS protocol (manual, per distro) | manual-checkpoint | `distrobox enter ms-spike-{distro} -- ./MusicStreamer-spike-x86_64.AppImage` then Kyle confirms 30s + pause/resume + stop + relaunch | ❌ W4 | ⬜ pending |
| 85A-10-01 | 10 | 5 | SPIKE-FINDINGS.md exists with per-distro evidence | file-content-grep | `grep -c '^### Distro: ' .planning/phases/85A-linux-packaging-spike/85A-SPIKE-FINDINGS.md \| grep -q '^3$'` | ❌ W5 | ⬜ pending |
| 85A-11-01 | 11 | 5 | spike wrapped into existing skill | file-exists | `test -d .claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike` | ❌ W5 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] **Host tooling** — `podman` (already installed), `distrobox`, `gnome-screenshot`, `grim`, `script` available on the Wayland host
- [ ] **Pin verification script** — `.planning/spikes/85a-linux-packaging-spike/verify-pins.sh` that re-fetches SHA256 of pinned linuxdeploy + plugin AppImages and fails-fast on drift
- [ ] **No production test framework needed** — spike validates via shell exit codes + smoke_test.py state-machine; pytest tests are Phase 85's surface

*Existing test infrastructure (musicstreamer's 1462 pytest suite) is NOT exercised by this spike — the spike runs entirely outside the production code path.*

---

## Manual-Only Verifications

| Behavior | Spike Output | Why Manual | Test Instructions |
|----------|--------------|------------|-------------------|
| Audible playback on Ubuntu 22.04 distrobox | D-06 audible PASS | Audio fidelity cannot be programmatically asserted; requires Kyle's ears on host pipewire | `distrobox enter ms-spike-ubuntu22 -- ./MusicStreamer-spike-x86_64.AppImage`; play 30s; pause (verify silence); play (verify resume); stop; close; relaunch; verify second launch plays |
| Audible playback on Fedora 40 distrobox | D-06 audible PASS | Same | Same protocol via `ms-spike-fedora40` |
| Audible playback on openSUSE Tumbleweed distrobox | D-06 audible PASS | Same | Same protocol via `ms-spike-tumbleweed` |
| Wayland screenshot captures running AppImage window | D-05 evidence | Visual confirmation; tool-dependent on session compositor | `gnome-screenshot --window --file <distro>-screenshot.png` while AppImage focused; verify PNG embeds the app frame |
| Terminal transcript captures gst-inspect + GLIBC grep + AppImage stdout | D-05 evidence | Per-distro session recording | Run smoke inside `script -q -c '...' <distro>-transcript.log`; verify transcript embeds all three checks |
| HTTPS variant audibly plays (TLS bundle coverage) | D-08 | TLS path failure mode is silent at the smoke level | On at least Ubuntu 22.04 distrobox: launch AppImage pointing at https://ice6.somafm.com/groovesalad-128-mp3 and confirm audible playback |

---

## Validation Sign-Off

- [ ] All spike outputs have either shell-exit verification or manual-only checkpoint
- [ ] Sampling continuity: no 3 consecutive tasks without verification (W4 audible loop punctuates programmatic checks)
- [ ] Wave 0 covers all host-side prerequisites (distrobox, gnome-screenshot, grim)
- [ ] No watch-mode flags
- [ ] Feedback latency: each per-distro smoke cycle < 5 min
- [ ] `nyquist_compliant: true` set in frontmatter once planner fills the per-task map
- [ ] Spike findings include per-distro evidence section with all three artifacts (audible confirmation, screenshot, transcript)
- [ ] AppRun template documents all four env vars + the research-discovered `GST_REGISTRY_REUSE_PLUGIN_SCANNER` vs `GST_REGISTRY_FORK` distinction

**Approval:** pending
