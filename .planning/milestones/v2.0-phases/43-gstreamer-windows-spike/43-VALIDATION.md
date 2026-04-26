---
phase: 43
slug: gstreamer-windows-spike
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-19
---

# Phase 43 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

This phase is a spike, not a pytest feature. Validation is the smoke test's exit code + user audibility confirmation, not a test suite. Nyquist still applies: every plan's tasks must carry verifiable acceptance criteria, and Wave 0 must create all four build artifacts (.spec, runtime_hook, build.ps1, smoke_test) before later waves can sample them.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Bespoke CLI contract (smoke_test.py exit-code + `SPIKE_OK` / `SPIKE_FAIL` / `SPIKE_DIAG` markers) |
| **Config file** | `.planning/phases/43-gstreamer-windows-spike/43-spike.spec` + `test_url.txt` (gitignored, contains user's AA HTTPS URL) |
| **Quick run command** | `.\build.ps1 -SkipSmoke` (build-only, used while iterating on the .spec) |
| **Full suite command** | `.\build.ps1` (build + smoke; produces `artifacts\smoke.log` the user pastes back) |
| **Estimated runtime** | ~60-120s on first build; ~20-40s on incremental iterations |

**Non-standard note:** The "suite" runs on the user's Windows 11 VM, not on Linux CI. D-09 locks this explicitly — no automated Linux run, no GitHub Actions windows runner. Claude samples feedback via paste-back.

---

## Sampling Rate

- **Per spike iteration:** `build.ps1` runs full build + smoke in one invocation. User pastes the full `artifacts\smoke.log` and the PyInstaller warnings summary. Claude diffs against the previous iteration.
- **Per task commit (pre-spike, during Wave 0):** File-existence checks via `test -f` on the four build artifacts. No Python test run.
- **Phase gate:** All three ROADMAP Phase 43 success criteria green on a single iteration, confirmed by paste-back markers + user audibility word ("audible" / "silent"). Then `/gsd-spike-wrap-up` persists findings.
- **Max feedback latency:** User's VM cycle time (install+build+smoke) ≈ 2 minutes. Target ≤5 iterations before escalating scope.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 43-01-01 | 01 | 1 | PKG-06 | — | Build artifacts created with exact skeleton from 43-RESEARCH.md | file-check | `test -f .planning/phases/43-gstreamer-windows-spike/43-spike.spec` | ❌ W0 | ⬜ pending |
| 43-01-02 | 01 | 1 | PKG-06 | — | Runtime hook sets GST/GIO/GI env vars before Gst.init | file-check | `grep -q 'GIO_EXTRA_MODULES' .planning/phases/43-gstreamer-windows-spike/runtime_hook.py` | ❌ W0 | ⬜ pending |
| 43-01-03 | 01 | 1 | PKG-06 | — | smoke_test.py emits SPIKE_OK / SPIKE_FAIL markers + exits 0/1/2/3 | file-check | `grep -q 'SPIKE_OK\|SPIKE_FAIL' .planning/phases/43-gstreamer-windows-spike/smoke_test.py` | ❌ W0 | ⬜ pending |
| 43-01-04 | 01 | 1 | PKG-06 | — | build.ps1 installs deps, runs PyInstaller, runs smoke, captures log | file-check | `grep -q 'pyinstaller\|smoke_test.py' .planning/phases/43-gstreamer-windows-spike/build.ps1` | ❌ W0 | ⬜ pending |
| 43-01-05 | 01 | 1 | PKG-06 | — | Redaction of URL query string (listen key) before logging | file-check | `grep -q 'redact\|?<redacted>' .planning/phases/43-gstreamer-windows-spike/smoke_test.py` | ❌ W0 | ⬜ pending |
| 43-02-XX | 02 | 2 | PKG-06 | — | Paste-back iteration produces SPIKE_OK + user "audible" | manual smoke | User runs `.\build.ps1` on VM, pastes `smoke.log`, confirms audible playback | — | ⬜ pending |
| 43-03-XX | 03 | 3 | PKG-06 | — | SPIKE-FINDINGS.md populated from final bundle + spike-findings skill persisted | file-check + manual | `test -f .planning/phases/43-gstreamer-windows-spike/43-SPIKE-FINDINGS.md` and `ls .claude/skills/spike-findings-43-*/SKILL.md` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

Plan numbering is indicative — the planner finalizes exact task IDs. The map reflects the three-wave shape the research implies: Wave 1 builds the skeleton artifacts, Wave 2 iterates with the user's paste-back on the VM, Wave 3 harvests findings + wrap-up skill.

---

## Wave 0 Requirements

- [ ] `.planning/phases/43-gstreamer-windows-spike/43-spike.spec` — PyInstaller .spec skeleton from RESEARCH §"PyInstaller .spec structure"
- [ ] `.planning/phases/43-gstreamer-windows-spike/runtime_hook.py` — from RESEARCH §"Runtime hook template" (sets `GIO_EXTRA_MODULES`, `GI_TYPELIB_PATH`, `GST_PLUGIN_SCANNER` before Gst.init)
- [ ] `.planning/phases/43-gstreamer-windows-spike/build.ps1` — from RESEARCH §"build.ps1 skeleton"; preflight checks for Python + GStreamer install paths; deterministic paste-back output
- [ ] `.planning/phases/43-gstreamer-windows-spike/smoke_test.py` — from RESEARCH §"smoke_test.py with exit-code contract"; emits SPIKE_OK / SPIKE_FAIL / SPIKE_DIAG lines; redacts URL query string
- [ ] `.planning/phases/43-gstreamer-windows-spike/.gitignore` — ignore `test_url.txt`, `artifacts/`, `build/`, `dist/`, `*.spec.log`
- [ ] No Python test framework installation — the spike is freestanding; pytest not invoked in this phase.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Audible HTTPS ShoutCast playback for ≥5s | PKG-06 / ROADMAP §43 SC-1 | Host-side audio routing can't be sampled from Claude; only the user hears the speakers | After `.\build.ps1` exits 0 with SPIKE_OK, user replies one word: `audible` or `silent`. If `SPIKE_OK` + `audible` → SC-1 passes. If `SPIKE_OK` + `silent` → log a VM audio config note in findings, SC-1 still passes at the GStreamer layer (pipeline reached PLAYING). |
| Clean-snapshot fidelity (no system GStreamer on PATH) | D-01 | VM state is owned by the user; Claude can't inspect registry | Before each iteration that requires a clean baseline, user confirms the VM was reverted to the no-GStreamer snapshot (yes/no). |
| libgiognutls.dll bundled and loaded | PKG-06 / ROADMAP §43 SC-2 | Dir listing of bundle + Gio TLS capability check at runtime | Post-build: `SPIKE_DIAG has_default_database=True` marker present in paste-back (proves Gio.TlsBackend loaded GnuTLS) AND `dist\spike\_internal\gio\modules\libgiognutls.dll` exists (user confirms via `dir` or paste of tree). |
| Final DLL + plugin list documented for Phase 44 | PKG-06 / ROADMAP §43 SC-3 | Bundle enumeration is a one-shot at spike-close | After final green iteration: user runs `gst-inspect-1.0.exe` against the bundled registry; Claude writes 43-SPIKE-FINDINGS.md tables from the paste. |

---

## Validation Sign-Off

- [ ] All Wave 1 tasks have `<acceptance_criteria>` with `test -f` / `grep -q` verification
- [ ] Wave 2 (spike iteration) has paste-back protocol with SPIKE_OK/FAIL markers as the sampling signal
- [ ] Wave 3 (findings + wrap-up) requires the findings doc exists AND the spike-findings skill was persisted via `/gsd-spike-wrap-up`
- [ ] Sampling continuity: every Wave 1 task has a file-check; the manual smoke in Wave 2 is sampled per-iteration, not per-task
- [ ] Wave 0 covers all four build artifacts listed above — no deferred dependencies
- [ ] No watch-mode flags (spike is one-shot per iteration)
- [ ] Max feedback latency: ≤2 minutes (user's VM cycle)
- [ ] `nyquist_compliant: true` set in frontmatter after the planner's tasks satisfy the verification map above

**Approval:** pending
