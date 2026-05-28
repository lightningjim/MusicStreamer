---
phase: 85-linux-common-appimage-build
plan: "04"
subsystem: linux-packaging
tags:
  - appimage
  - distrobox
  - smoke-test
  - drift-guard
  - pytest
  - gpg-signing
dependency_graph:
  requires:
    - 85-01 (environment.yml, AppRun, build.sh base, desktop/)
    - 85-02 (GPG signing, zsync, build.sh hardening)
    - 85-03 (GitHub Actions workflow, build.sh CI additions)
  provides:
    - tools/linux-build/smoke_test.py (D-04 codec sweep + D-05 production import)
    - tools/linux-build/run-smoke.sh (cross-distro UAT harness)
    - tools/linux-build/create-distroboxes.sh (ms-linux-* provisioning)
    - tools/linux-build/teardown-distroboxes.sh (container cleanup)
    - tools/linux-build/README.md (production-side build documentation)
    - tests/test_packaging_linux_spec.py (Linux drift-guard pytest module)
  affects:
    - .planning/REQUIREMENTS.md (PKG-LIN-APP-01..10 rows — pending checkpoint approval)
tech_stack:
  added:
    - smoke_test.py: Python stdlib + gi (PyGObject) + GStreamer, no new deps
    - test_packaging_linux_spec.py: pytest (already in dev env), stdlib only
  patterns:
    - D-04 four-URL codec sweep (MP3/AAC/AACP/PLS) per 35s each
    - D-05 production import guard (from musicstreamer import url_helpers)
    - D-07 distrobox harness relocated from tools/linux-spike/ with ms-spike-* → ms-linux-* rename
    - D-17 distrobox-backend autodetect note folded into README
    - Drift-guard: pytest file-read fixture + substring assertion (mirrors tests/test_packaging_spec.py shape)
key_files:
  created:
    - tools/linux-build/create-distroboxes.sh
    - tools/linux-build/teardown-distroboxes.sh
    - tools/linux-build/run-smoke.sh
    - tools/linux-build/smoke_test.py
    - tests/test_packaging_linux_spec.py
    - tools/linux-build/README.md
  modified: []
decisions:
  - "D-05 resolver entry point: url_helpers.py has no .resolve() function; aa_normalize_stream_url() is the production URL normalization entry point (Phase 56 / WIN-01 / D-04). For SomaFM + .pls URLs this is an identity pass. D-05 guard is satisfied by the module import itself, which catches dependency-graph regressions regardless of which entry point is called."
  - "_resolve_via_production() wrapper uses aa_normalize_stream_url() rather than a hypothetical .resolve(); AttributeError path surfaces actual public API for diagnostics."
  - "15 tests in test_packaging_linux_spec.py (plan expected 13); 2 additional tests added for D-01/D-02 coverage (yq+environment.yml synthesis, musicstreamer-build env name) — these are correctness requirements, not gold-plating."
  - "REQUIREMENTS.md flip (Task 6) deferred pending Task 5 checkpoint approval — not executed in this agent run."
metrics:
  duration: "~15 minutes (Tasks 1-4 + SUMMARY)"
  completed: "2026-05-28"
  tasks_completed: 4
  tasks_total: 6
  files_created: 6
  files_modified: 0
---

# Phase 85 Plan 04: Cross-distro Verification Harness + Drift-Guards Summary

**One-liner:** Distrobox harness promoted from spike (ms-spike-* → ms-linux-*), production smoke_test.py with musicstreamer.url_helpers import guard + 4-URL codec sweep, 15-test Linux drift-guard pytest module, and README with D-17 distrobox-backend autodetect note.

## Tasks Executed

### Task 1: Relocate distrobox harness; rename ms-spike-* → ms-linux-* (D-07)
**Commit:** 67329cb

Three scripts created at `tools/linux-build/`:
- `create-distroboxes.sh`: copied from `tools/linux-spike/`; all three container names renamed `ms-spike-{ubuntu22,fedora40,tumbleweed}` → `ms-linux-*`; header comment updated; `--unshare-devsys`, `--additional-packages binutils`, Tumbleweed zypp hook preserved verbatim.
- `teardown-distroboxes.sh`: for-loop names renamed `ms-spike-` → `ms-linux-`; header updated.
- `run-smoke.sh`: path resolution updated to `BUILD_DIR/artifacts/` glob; container names renamed; smoke modes replaced with D-04 four-URL codec sweep (`--check-mp3/aac/aacp/pls`); AppRun env-replay block (SSL_CERT_FILE, GST_PLUGIN_*, etc.) preserved verbatim.

Original `tools/linux-spike/` scripts kept as reference per CONTEXT.md Deferred.

### Task 2: smoke_test.py production-import + D-04 codec sweep (D-05, D-06)
**Commit:** caf047a

`tools/linux-build/smoke_test.py` created. Key additions over spike:
- **D-05 import guard**: `from musicstreamer import url_helpers` at module level; import failure captured and surfaced as `SPIKE_FAIL step=resolve reason=import_failed:...` at runtime rather than crashing.
- **_resolve_via_production()**: wraps `aa_normalize_stream_url()` (production URL normalization entry point per url_helpers.py source read at task time — no `.resolve()` function exists; see deviation note).
- **D-04 modes**: `--check-mp3/--check-aac/--check-aacp/--check-pls` argparse modes with SomaFM default URLs; each routes through `_resolve_via_production()` before GStreamer pipeline.
- **Multi-host URL allowlist**: extended to `*.somafm.com`, `*.di.fm`, `*.audioaddict.com` (D-04 codec-sweep URL families).
- All spike `SPIKE_OK`/`SPIKE_FAIL`/`SPIKE_DIAG`/`plugin_resolved=` markers preserved verbatim.
- Existing `--uri`/`--timeout`/`--assert-tls`/`--check-glibc`/`--check-plugins` codepaths preserved.
- `_log_sink_election` + TAG-event pattern (Pitfalls 9+10) preserved verbatim.

### Task 3: Linux drift-guard pytest module (Pitfall 16 + Success Criterion 4)
**Commit:** b50c49b

`tests/test_packaging_linux_spec.py` created. 15 tests pass in 0.03s:

| Test | Requirement |
|------|-------------|
| `test_build_sh_pins_glibc_ceiling_at_2_35` | PKG-LIN-APP-08 / Pitfall 16 |
| `test_build_sh_embeds_zsync_update_info` | PKG-LIN-APP-06 / D-11 |
| `test_build_sh_signs_appimage_with_gpg2` | PKG-LIN-APP-10 / D-08 |
| `test_build_sh_fail_fast_when_gpg_key_unset` | D-09 |
| `test_build_sh_fails_when_signing_fails` | D-08 |
| `test_environment_yml_includes_nodejs` | PKG-LIN-APP-04 |
| `test_environment_yml_is_production_named` | D-02 |
| `test_build_sh_synthesizes_conda_packages_from_yml` | D-01 |
| `test_apprun_execs_production_musicstreamer_module` | Pitfall 20 |
| `test_apprun_exports_pulse_prop` | Pitfall 19 |
| `test_apprun_exports_ssl_cert_file` | Pitfall 17 |
| `test_desktop_file_has_no_playlist_mime_entries` | PKG-LIN-APP-09 |
| `test_smoke_test_imports_production_url_helpers` | D-05 |
| `test_smoke_test_exposes_d04_codec_sweep_modes` | D-04 |
| `test_smoke_test_preserves_spike_grep_contract` | grep contract |

Windows drift-guards (`tests/test_packaging_spec.py`) verified green — 8 passed (Pitfall 16 / Success Criterion 4 source-level verified).

### Task 4: tools/linux-build/README.md (D-17 fold-in + signing key placeholder)
**Commit:** 2a8e2d4

`tools/linux-build/README.md` created. Documents:
- Host prerequisites: Docker/podman, yq (D-01), GPG_KEY_ID/SKIP_SIGN (D-09), GLIBC ≤ 2.35 (PKG-LIN-APP-08)
- **D-17 fold-in**: distrobox autodetects backend per invocation; `sg docker -c 'distrobox ...'` forces docker daemon view which may not match rootless podman containers (caught during Phase 85a teardown); cites `reference_distrobox_backend_autodetect.md`
- Quick Start: verify-pins → build → gpg verify → create/run/teardown distroboxes
- Build Step Reference table (7 steps)
- Exit Codes table (codes 0-6)
- `--appimage-extract-and-run` requirement for downstream CI consumers (D-14 / Pitfall 11)
- Signing Key section: developer-fill-in placeholder block
- Architecture / Pitfall Cross-Reference + File Map

### Task 5: Cross-distro audible-PASS protocol
**Status:** CHECKPOINT — awaiting human verification (see checkpoint section below)

### Task 6: REQUIREMENTS.md tracker flip
**Status:** DEFERRED — executes only after Task 5 checkpoint returns `approved`

## Deviations from Plan

### Auto-noted: url_helpers.py has no resolve() function

**Found during:** Task 2

**Issue:** The plan's `<interfaces>` section referenced `url_helpers.resolve(url) -> str` as the production resolver entry point. Reading `musicstreamer/url_helpers.py` at task time confirmed there is NO `resolve()` function in the module. The module provides URL classification and normalization helpers including `aa_normalize_stream_url()` (production URL normalization entry point at the Player boundary, Phase 56 / WIN-01 / D-04).

**Fix applied:** Per plan's explicit instruction ("executor confirms at task time by reading musicstreamer/url_helpers.py ... if the actual export is named differently, update this wrapper accordingly and document the choice in the SUMMARY"), `_resolve_via_production()` uses `aa_normalize_stream_url()` instead. For SomaFM and .pls URLs this is an identity pass (those domains are not DI.fm). The D-05 guard is satisfied by the module-level import itself — `from musicstreamer import url_helpers` fires at IMPORT time regardless of which entry point is called.

**Plan note preserved:** The wrapper's `AttributeError` path now displays the actual public API to aid diagnosis if `aa_normalize_stream_url` is ever renamed.

**Files modified:** `tools/linux-build/smoke_test.py`

### Test count: 15 vs 13 expected

**Found during:** Task 3

**Issue:** Plan expected 13 tests; 15 were created. Two additional tests cover D-01 (`test_build_sh_synthesizes_conda_packages_from_yml`) and D-02 (`test_environment_yml_is_production_named`) — both are source-truth contracts that belong in the drift-guard module and are as load-bearing as the others.

**Classification:** Rule 2 (missing critical drift-guard coverage) — not gold-plating.

## Drift-Guard Test Results

```
tests/test_packaging_linux_spec.py: 15 passed in 0.03s
tests/test_packaging_spec.py: 8 passed in 0.05s
```

Both suites run in < 2s total (pure file-read assertions; no subprocess, no docker).

## Known Stubs

None. All six files created/modified in this plan are complete artifacts. `smoke_test.py`'s `_resolve_via_production()` wrapper handles the `import_failed` case gracefully (captures and reports rather than crashing) — this is intentional defensive design, not a stub.

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes introduced. `smoke_test.py`'s URL allowlist extension (somafm.com + di.fm + audioaddict.com) is documented in the plan's threat model (T-85-04-IV disposition: accept with multi-host allowlist).

## Self-Check: PASSED

All files verified to exist:
- FOUND: tools/linux-build/create-distroboxes.sh (67329cb)
- FOUND: tools/linux-build/teardown-distroboxes.sh (67329cb)
- FOUND: tools/linux-build/run-smoke.sh (67329cb)
- FOUND: tools/linux-build/smoke_test.py (caf047a)
- FOUND: tests/test_packaging_linux_spec.py (b50c49b)
- FOUND: tools/linux-build/README.md (2a8e2d4)
- FOUND: .planning/phases/85-linux-common-appimage-build/85-04-SUMMARY.md

All 4 task commits verified via `git log`:
- 67329cb: feat(85-04): relocate distrobox harness; rename ms-spike-* → ms-linux-*
- caf047a: feat(85-04): smoke_test.py production-import + D-04 codec sweep
- b50c49b: feat(85-04): Linux drift-guard pytest module
- 2a8e2d4: docs(85-04): tools/linux-build/README.md

Tests green:
- tests/test_packaging_linux_spec.py: 15 passed
- tests/test_packaging_spec.py: 8 passed (Windows side unregressed)
