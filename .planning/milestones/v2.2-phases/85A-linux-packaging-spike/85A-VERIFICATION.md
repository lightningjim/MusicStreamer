---
phase: 85A-linux-packaging-spike
verified: 2026-05-26T23:45:51Z
status: passed
score: 4/4 success criteria verified
verifier: Claude (gsd-verifier, goal-backward + spike-aware)
requirements:
  - SPIKE-85A  # spike — not listed in REQUIREMENTS.md by design; outputs feed Phase 85
---

# Phase 85A Linux Packaging Spike — Verification Report

**Phase Goal (verbatim from ROADMAP.md):** "De-risk the linuxdeploy-plugin-conda + linuxdeploy-plugin-gstreamer toolchain before committing to the full Linux build recipe; produce a working hello-world AppImage that plays a remote MP3 stream on all three target distros."

**Verified:** 2026-05-26
**Status:** PASSED — all 4 ROADMAP success criteria verified against on-disk artifacts; Plan 07 intentionally partial per documented wrap-now decision (NOT a gap).
**Re-verification:** No — initial verification.

---

## Goal Achievement Summary

The spike achieved its de-risking objective. A 503 MiB (527,538,680 byte) ELF AppImage was built inside `ubuntu:22.04` via `linuxdeploy + linuxdeploy-plugin-conda + linuxdeploy-plugin-gstreamer + conda-forge GStreamer 1.28.3`, and programmatic transcripts on Ubuntu 22.04, Fedora 40, and openSUSE Tumbleweed all show:

- `SPIKE_DIAG glibc_max='GLIBC_2.17'` on the bundled `usr/conda/bin/python` (far below the 2.35 cap)
- `SPIKE_DIAG plugin_resolved='avdec_aac' status='ok'` + `aacparse status='ok'`
- `SPIKE_DIAG tls_backend='GTlsBackendOpenssl' has_default_database=True`
- `SPIKE_OK url='http://ice1.somafm.com/groovesalad-128-mp3' ... played_for_s=35.0+` (HTTP)
- `SPIKE_OK url='https://ice6.somafm.com/groovesalad-128-mp3' ... played_for_s=35.0+` (HTTPS)

The Phase 85 hand-off package — annotated AppRun template, `build.sh` with 8 in-script Pitfall mitigations, `pins.env` + `verify-pins.sh` supply-chain manifest, and a 711-line `85A-SPIKE-FINDINGS.md` cataloguing all 20 pitfalls — is on disk and the surgical skill APPEND preserves Phase 43 Windows entries verbatim.

---

## Per-Success-Criterion Verdict

### SC#1 — Cross-distro empirical PASS (Ubuntu 22.04 + Fedora 40 + openSUSE Tumbleweed)

**Status:** VERIFIED

**Evidence chain:**
- `/.planning/spikes/85a-linux-packaging-spike/artifacts/ubuntu22-transcript.log` (10,660 bytes)
  - `SPIKE_OK url='http://ice1.somafm.com/groovesalad-128-mp3' time_to_play_s=0.28 first_tag_s=0.28 played_for_s=35.16`
  - `SPIKE_OK url='https://ice6.somafm.com/groovesalad-128-mp3' time_to_play_s=0.36 first_tag_s=0.36 played_for_s=35.08`
- `/.planning/spikes/85a-linux-packaging-spike/artifacts/fedora40-transcript.log` (11,005 bytes)
  - HTTP `SPIKE_OK ... played_for_s=35.16`; HTTPS `SPIKE_OK ... played_for_s=35.08`
- `/.planning/spikes/85a-linux-packaging-spike/artifacts/tumbleweed-transcript.log` (10,829 bytes)
  - HTTP `SPIKE_OK ... played_for_s=35.15`; HTTPS `SPIKE_OK ... played_for_s=35.07`

All three transcripts show `SPIKE_DIAG event='reached_playing'` followed by 35+ second uninterrupted play windows on the SomaFM Groove Salad MP3 stream (D-07 channel-won). HTTPS coverage extends beyond ROADMAP minimum (SC#1 specifies MP3 only) — D-08 explicit per CONTEXT.md.

**Note on the apparent narrative inconsistency:** FINDINGS doc Section 6 reports `time_to_play_s=0.22` for HTTP Ubuntu, but the actual `ubuntu22-transcript.log` shows `0.28`. The transcript is authoritative; the narrative number is from an earlier run. This is a minor documentation drift, not a verification gap — both numbers are well under the implicit "plays quickly" expectation, and the PASS markers themselves agree.

### SC#2 — GLIBC ceiling ≤ 2.35

**Status:** VERIFIED (with pivot from strings-grep to objdump scan)

**Evidence chain:**
- `build.sh` lines 246–267 implement the canonical Pitfall-16-safe objdump DT_VERNEED scan. The find-objdump-grep-sort pipeline produced `GLIBC_OBJDUMP GLIBC_2.34` on the final 503 MiB AppImage.
- All three distrobox transcripts independently report `SPIKE_DIAG glibc_max='GLIBC_2.17'` on the bundled `usr/conda/bin/python` (because conda-forge binaries themselves are built against a CentOS 7-era manylinux baseline — `GLIBC_2.34` is the host-supplied syscall stub layer, `GLIBC_2.17` is what the bundled interpreter requires).
- FINDINGS doc Section 1 documents this in the per-SC table.

**Note on the ROADMAP wording deviation (literal scan command):** ROADMAP SC#2 specifies `strings AppRun_or_main_so | grep GLIBC_ | sort -V | tail -1`. The spike discovered (Pitfall 16, Plan 05 round 8) that strings-on-compressed-squashfs returns false positives (saw `GLIBC_2.147` from random byte coincidence). The spike pivoted to `objdump -T` on the extracted ELFs — strictly more rigorous than the original literal. This is a documented, narrative-justified pivot, not a gap. The verification request explicitly anticipates and accepts this pivot.

### SC#3 — `gst-inspect-1.0 avdec_aac` + `aacparse` resolve from inside AppRun

**Status:** VERIFIED

**Evidence chain:**
- All three distrobox transcripts (Ubuntu/Fedora/Tumbleweed) contain `SPIKE_DIAG plugin_resolved='avdec_aac' status='ok'` AND `SPIKE_DIAG plugin_resolved='aacparse' status='ok'`.
- `build.sh` lines 182-183 wires the build-time Pitfall 2 mitigation: `GSTREAMER_PLUGINS_DIR="$APPDIR/usr/conda/lib/gstreamer-1.0"` + `GSTREAMER_HELPERS_DIR="$APPDIR/usr/conda/libexec/gstreamer-1.0"` BEFORE invoking `./linuxdeploy --plugin gstreamer`.
- `AppRun` lines 48-50 re-asserts the runtime Pitfall 2 mitigation: `GST_PLUGIN_SYSTEM_PATH_1_0` + `GST_PLUGIN_PATH_1_0` + `GST_PLUGIN_SCANNER` all point under `${APPDIR}/usr/conda/`.
- Plugin BOM count from FINDINGS: 188 plugin `.so` files at `${APPDIR}/usr/conda/lib/gstreamer-1.0/` — Phase 85's drift-guard baseline.

### SC#4 — AppRun env-var template captured for Phase 85 consumption

**Status:** VERIFIED

**Evidence chain:**
- `/.planning/spikes/85a-linux-packaging-spike/AppRun` (5,119 bytes, executable, present and committed; this is the PRIMARY DELIVERABLE).
- All four ROADMAP-required exports present on the file:
  - `GST_PLUGIN_SYSTEM_PATH_1_0` (line 48)
  - `GST_PLUGIN_PATH_1_0` (line 49)
  - `GST_PLUGIN_SCANNER` + `GST_PLUGIN_SCANNER_1_0` defensive doubling (lines 50, 58)
  - `GST_REGISTRY_FORK="no"` (line 62) — with explicit comment-block distinguishing it from `GST_REGISTRY_REUSE_PLUGIN_SCANNER=no` (Pitfall 3)
- Bonus exports beyond the ROADMAP minimum, all documented with rationale: `GIO_EXTRA_MODULES` (Pitfall 4, HTTPS), `SSL_CERT_FILE` (Pitfall 17 — spike-discovered, OpenSSL CA bundle path), `GI_TYPELIB_PATH` (PyGObject introspection), `PYTHONHOME` + `PATH` (bundled interpreter).
- Empirically validated: Plan 07 relaunch protocol on Ubuntu shows first-launch `time_to_play_s=1.636`, second-launch `time_to_play_s=0.345` — **relaunch 4.7× FASTER**, far inside the negative-pivot trigger of "≥5s slower" (CONTEXT.md D-06). `GST_REGISTRY_FORK=no` mitigation conclusively validated.

---

## Required-Artifact Verification

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `AppRun` | Annotated template, primary deliverable | VERIFIED | 5,119 bytes; 4/4 ROADMAP env vars + 3 bonus exports (`GIO_EXTRA_MODULES`, `SSL_CERT_FILE`, `GI_TYPELIB_PATH`); annotated with per-export rationale |
| `build.sh` | End-to-end driver with 8 Pitfall mitigations | VERIFIED | 14,775 bytes, executable; implements Pitfalls 1, 2, 11, 12, 13/13b, 14, 15, 16 inline with rationale comments |
| `pins.env` | SHA256 supply-chain manifest | VERIFIED | 3 raw-GitHub asset pins + Miniforge3 tag + Approach-P-patched plugin-conda SHA (5 distinct `^[a-f0-9]{64}` lines) |
| `verify-pins.sh` | Drift-guard for pins.env | VERIFIED | 1,150 bytes, executable |
| `Dockerfile` | `FROM ubuntu:22.04` GLIBC ≤ 2.35 lock | VERIFIED | 3,599 bytes |
| `host-environment.md` | Reproducibility prefix | VERIFIED | Ubuntu 26.04 LTS / kernel 7.0.0-15 / GLIBC 2.43 host / podman 5.7.0 / distrobox 1.8.2.4 captured |
| `environment-spike.yml` | conda-forge-only channel + 11-package set | VERIFIED | 2,127 bytes; channel-only pin, all 11 packages including 3 Linux-specific additions (`gst-libav`, `gst-python`, `glib-networking`) |
| `hello_world.py` | Smoke target | VERIFIED | 4,693 bytes |
| `smoke_test.py` | Programmatic verification harness | VERIFIED | 16,015 bytes; emits `SPIKE_DIAG` / `SPIKE_OK` / `SPIKE_FAIL` markers consumed by run-smoke.sh |
| `MusicStreamer-spike-x86_64.AppImage` | The exit-deliverable AppImage | VERIFIED ON DISK | 527,538,680 bytes (503 MiB); real `ELF 64-bit LSB pie executable, x86-64, static-pie linked, BuildID[sha1]=db3b55ac…`; gitignored (regenerable from build.sh) |
| `artifacts/{ubuntu22,fedora40,tumbleweed}-transcript.log` | Per-distro programmatic smoke transcripts | VERIFIED ON DISK | 10,660 / 11,005 / 10,829 bytes respectively; gitignored; all 3 contain SPIKE_OK markers for both HTTP and HTTPS |
| `artifacts/audible-pass-log.md` | Plan 07 audible-PASS evidence | VERIFIED | Ubuntu section filled with Pitfall 19 evidence + Pitfall 3 relaunch numbers (1.636s → 0.345s); Fedora + Tumbleweed sections marked SKIPPED with wrap-now rationale |
| `85A-SPIKE-FINDINGS.md` | The 710-line exit-deliverable findings doc | VERIFIED | 711 lines / 56,003 bytes; 20 pitfalls catalogued; 13 H2 sections; 3 H3 per-distro sections in Section 6 |
| `.claude/skills/spike-findings-musicstreamer/references/linux-appimage-bundling.md` | New skill reference file | VERIFIED | 16,555 bytes (substantive; ~2× the Phase 43 windows-gstreamer-bundling.md size at 7,616 bytes) |
| `.claude/skills/spike-findings-musicstreamer/sources/85a-linux-packaging-spike/` | 12 verbatim source copies + README | VERIFIED | Directory present (peer of `43-gstreamer-windows-spike/` — Phase 43 sources preserved) |
| `.claude/skills/spike-findings-musicstreamer/SKILL.md` | Surgical APPEND, Phase 43 entries preserved | VERIFIED | Phase 43 row at line 19 and Qt-GLib row at line 20 retained verbatim; Linux row APPENDED at line 21; processed_spikes line APPENDED at line 39 |

---

## Pitfalls Catalog Verification

| Check | Expected | Observed | Status |
|---|---|---|---|
| Pitfalls 1-10 (RESEARCH.md-anticipated) | All 10 present in FINDINGS catalog | All present, numbered as `### Pitfall N` | VERIFIED |
| Pitfalls 11-20 (spike-discovered) | All 10 present with discovery context | 11 (FUSE), 12 (Docker SSL), 13 + 13b (Miniconda ToS + plugin internals), 14 (LD_LIBRARY_PATH), 15 (binutils strip), 16 (strings false-positive), 17 (SSL_CERT_FILE), 18 (screenshot tools), 19 (PipeWire routing), 20 (AppRun hardcode) — all present | VERIFIED |
| Pitfall 19 documented as load-bearing | Phase 85 mitigation must be explicit | Section "AppRun template surface alone insufficient" — recommends `PULSE_PROP="application.name=... application.id=..."` AND FUSE self-mount for production | VERIFIED |
| Each pitfall has Phase 85 action item | All 20 must list `Phase 85 action:` | All 20 entries have explicit `**Phase 85 action:**` line | VERIFIED |
| `grep -c '### Pitfall ' FINDINGS.md` | 21 H3 lines (20 numbered + Pitfall 13b sub-entry) | 21 H3 lines found | VERIFIED |

---

## Skill APPEND Surgical-ness Verification

| Check | Expected | Observed | Status |
|---|---|---|---|
| Phase 43 Windows GStreamer Bundling row | Preserved verbatim at row 1 of findings_index table | Line 19 of SKILL.md retains original Phase 43 entry word-for-word | VERIFIED |
| Phase 43 Qt-GLib Bus Threading row | Preserved verbatim at row 2 | Line 20 of SKILL.md retains Phase 43.1 entry word-for-word | VERIFIED |
| Phase 43 Source Files list | All 6 entries preserved | Lines 27-32 of SKILL.md preserve all Phase 43 sources/ entries | VERIFIED |
| Phase 43 processed_spikes line | Preserved | Line 38 of SKILL.md still reads `- 43-gstreamer-windows-spike (Phase 43; GStreamer Windows bundling via PyInstaller + conda-forge)` | VERIFIED |
| Linux AppImage Bundling row APPENDED | Row 3, after Phase 43 entries | Line 21 of SKILL.md adds the new Linux row | VERIFIED |
| 85a processed_spikes line APPENDED | Second line in processed_spikes block | Line 39 of SKILL.md APPENDS the new 85a line | VERIFIED |
| `sources/43-gstreamer-windows-spike/` preserved | Directory untouched | Present alongside new `sources/85a-linux-packaging-spike/` peer | VERIFIED |

---

## Plan-Checkbox / Roadmap Coverage

| Plan | Wave | Checkbox in ROADMAP | SUMMARY status |
|---|---|---|---|
| 85A-01 — Host tooling + environment manifest | 0 | [x] | implicit pass (no status field, key outputs present) |
| 85A-02 — Dockerfile + environment-spike.yml | 1 | [x] | implicit pass |
| 85A-03 — pins.env + verify-pins.sh | 1 | [x] | implicit pass |
| 85A-04 — hello_world.py + AppRun + smoke_test.py | 2 | [x] | implicit pass |
| 85A-05 — build.sh (9-round saga) | 3 | [x] | BUILD_OK on round 9 |
| 85A-06 — Distrobox scripts + programmatic smoke | 4 | [x] | All 3 distros PASS |
| 85A-07 — Audible-PASS protocol | 5 | [x] (ROADMAP-side checked) | `partial (wrap-now per CONTEXT.md D-09 + user-owned retry budget)` |
| 85A-08 — SPIKE-FINDINGS + skill APPEND + teardown | 6 | [x] | implicit pass (711-line findings doc + surgical APPEND verified) |

---

## Plan 07 Partial — NOT a Gap (Per Verification Request)

The verification request anticipates and accepts the Plan 07 partial. Confirmed:

1. **Plan 07 SUMMARY explicitly captures the wrap-now rationale.** Lines 24, 26, 30, 90-91, 98, 100, 108 all document the intentional skip and justify it: Pitfall 19 (PipeWire routing non-determinism) was discovered on Ubuntu; cross-distro reproduction would not change Phase 85's action item.
2. **Pitfall 19 is documented with Phase 85 mitigation recommendation.** FINDINGS lines 541-548 prescribe explicit PipeWire app identity (`PULSE_PROP="application.name=MusicStreamer application.id=org.musicstreamer.app"`) + FUSE self-mount for production AppImage (deterministic mount path per content hash).
3. **CONTEXT.md negative-pivot policy applies.** CONTEXT line 79 establishes "the spike stops and reports the failure mode in findings (does not silently pivot to a different toolchain)" — Plan 07 followed this policy correctly. (Minor: SUMMARYs colloquially reference this as "D-09 negative-pivot policy" — D-09 is actually the SomaFM-only fallback chain decision; the negative-pivot policy is a separate prose paragraph in CONTEXT. This is a documentation cross-reference imprecision, not a substantive gap.)
4. **The audible-PASS protocol did its job.** It exists to catch GStreamer-reports-success-but-no-audio bugs (Plan 07 SUMMARY line 26). It caught one. Job done.
5. **Pitfall 3 (`GST_REGISTRY_FORK=no`) WAS empirically verified before the wrap-now** — Plan 07 ran the relaunch protocol on Ubuntu, observed 4.7× faster relaunch (1.636s → 0.345s). SC#4 satisfied.

---

## Anti-Pattern / Drift Scan

| File | Pattern | Severity | Note |
|---|---|---|---|
| `build.sh` line 7 | `# 3 = smoke failed (reserved; smoke runs in Plan 06 / run-smoke.sh)` | INFO | Reserved exit-code documentation — explicitly intentional, not orphaned debt |
| `AppRun` lines 12-41 | Long comment block citing 85A-RESEARCH.md line numbers + Pitfall numbers | INFO | This is by design — AppRun is the spike's PRIMARY DELIVERABLE and is meant to be read top-to-bottom by Phase 85's implementer |
| `pins.env` | `MINICONDA_VERSION=py312_24.9.2-0` (unused alongside the Miniforge swap) | INFO | Retained as documentation of the original pre-Approach-P pin; not load-bearing at runtime — see Pitfall 13b rationale in build.sh comments |
| `audible-pass-log.md` Fedora + Tumbleweed sections | `status: SKIPPED` | INFO | Explicit wrap-now markers; not stub content — captured rationale and references Pitfall 19 |

No TBD / FIXME / XXX debt markers found in spike sources. No orphaned `placeholder` / `coming soon` / `not yet implemented` strings.

---

## Findings Worth Flagging (Not Gaps)

1. **HTTP `time_to_play_s` numbers drift between FINDINGS narrative (0.22) and actual transcript (0.28).** Both are well inside any reasonable acceptance window; the transcript is authoritative. Phase 85 should source numbers from transcripts, not from the prose narrative in FINDINGS Section 6. This is a minor documentation cleanup, not a verification gap.

2. **The "D-09 negative-pivot" naming in the audible-pass-log.md and Plan 07 SUMMARY is slightly imprecise.** CONTEXT.md D-09 is the SomaFM-only fallback chain; the negative-pivot policy is a separate prose paragraph (line 79). Future cross-references should distinguish "D-09 (fallback chain)" from "negative-pivot policy (line 79)" — both decisions are present in CONTEXT, just under different labels.

3. **`MINICONDA_VERSION` pin in `pins.env` (line 28) is functionally dead.** Approach P (sed-patch to Miniforge3) means Miniconda3 is never actually downloaded. The pin is retained as discovery-archaeology documentation. Consider deleting it OR adding a `# DEAD PIN — see Pitfall 13/13b` comment in Phase 85's port.

4. **Plan 07 audible verification on Fedora 40 + Tumbleweed is genuinely deferred to Phase 85 UAT.** This is acknowledged by the spike's wrap-now decision (CONTEXT line 79 policy). Phase 85's UAT plan should explicitly include "audible-PASS on Fedora 40 + openSUSE Tumbleweed" as a deliverable that this spike intentionally did not close.

None of these are blockers. They are forward-pointing observations for Phase 85's plan-phase consumption.

---

## Deferred Items (Already Addressed by Later Phases)

| Concern | Addressed In | Evidence |
|---|---|---|
| `.desktop` + icon + `MIME=audio` integration | Phase 85 | ROADMAP success criterion #3 + PKG-LIN-APP-05 |
| zsync update-info embedding | Phase 85 | PKG-LIN-APP-06 |
| MPRIS2 in AppImage | Phase 85 | PKG-LIN-APP-07 |
| AAC stream playback (not just plugin resolution) | Phase 85 | ROADMAP success criterion #2 + PKG-LIN-APP-03 |
| `.pls`/`.m3u` MIME-association negative test | Phase 85 | PKG-LIN-APP-09 |
| Drift-guards (`tests/test_packaging_spec.py` GLIBC literal, plugin BOM) | Phase 85 | PKG-LIN-APP-08 |
| AppImage signing | Phase 85 (TBD plans) | "Phase 85 surface" per FINDINGS hand-off manifest |
| Pitfall 19 mitigation (PipeWire app identity + FUSE self-mount) | Phase 85 (TBD plans) | FINDINGS Pitfall 19 Phase-85-action |
| Pitfall 20 mitigation (`-m musicstreamer` exec line) | Phase 85 (TBD plans) | FINDINGS Pitfall 20 Phase-85-action |
| AAC playback on AAC streams (not just MP3) | Phase 85 | PKG-LIN-APP-03 AAC tier |
| Audible-PASS on Fedora 40 + Tumbleweed | Phase 85 UAT | Plan 07 wrap-now rationale; Phase 85 UAT consumes cross-distro audible per the implicit hand-off |

---

## Verifier Self-Check

- [x] Phase goal explicitly stated and verified end-to-end (de-risk + working AppImage on all 3 distros — done)
- [x] All 4 ROADMAP success criteria mapped to on-disk evidence
- [x] AppImage exists on disk (527,538,680 bytes, real ELF, executable)
- [x] All 3 per-distro programmatic transcripts exist on disk
- [x] AppRun template includes all 4 ROADMAP-required env-var exports + bonus Pitfall mitigations
- [x] All 20 pitfalls catalogued in FINDINGS doc
- [x] Pitfall 19 (load-bearing audible finding) has Phase 85 mitigation recommendation
- [x] Skill APPEND verified surgical (Phase 43 entries preserved verbatim, line-by-line checked)
- [x] Plan 07 partial verified as intentional (rationale documented in SUMMARY + audible-pass-log)
- [x] Drift-guards / debt-marker scan run on spike sources — clean
- [x] Cross-reference to REQUIREMENTS.md — SPIKE-85A correctly absent (spike pattern)
- [x] All 8 plan checkboxes in ROADMAP set to [x]
- [x] Status = `passed` (no gaps; no human verification items routed — audible cross-distro is Phase 85's UAT surface, not this verification's)

---

## Final Verdict

**PASSED.** The Phase 85a Linux Packaging Spike achieved its de-risking goal. All 4 ROADMAP success criteria are met with verifiable on-disk evidence. The Phase 85 hand-off package — annotated AppRun template, build.sh with 8 in-script pitfall mitigations, supply-chain manifest, and 711-line findings doc cataloguing 20 pitfalls — is intact. Phase 85's planner can consume this spike's outputs verbatim per the documented hand-off manifest, justifying ROADMAP's `Research flag: NO` on Phase 85.

The Plan 07 partial is an intentional wrap-now per the CONTEXT.md negative-pivot policy; it surfaced Pitfall 19 (PipeWire routing non-determinism) and captured a concrete Phase 85 mitigation. This is a successful spike outcome, not a gap.

_Verified: 2026-05-26T23:45:51Z_
_Verifier: Claude (gsd-verifier, goal-backward + spike-aware)_
