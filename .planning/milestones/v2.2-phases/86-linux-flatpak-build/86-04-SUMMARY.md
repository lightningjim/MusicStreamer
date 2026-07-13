---
phase: 86-linux-flatpak-build
plan: "04"
subsystem: linux-packaging
tags: [flatpak, build-driver, ci, gpg-signing, drift-guards, requirements]
dependency_graph:
  requires: ["86-01"]
  provides: ["tools/linux-flatpak/build.sh", ".github/workflows/linux-flatpak.yml", "flatpak-drift-guards"]
  affects: ["tests/test_packaging_linux_spec.py", ".planning/REQUIREMENTS.md"]
tech_stack:
  added: [flatpak-builder, flatpak-build-bundle, appstreamcli, desktop-file-validate]
  patterns: ["Phase-85-mirror", "GPG-fail-fast", "ephemeral-GNUPGHOME", "workflow_dispatch-only-CI", "hard-validator-pre-flight", "inline-bundle-signing"]
key_files:
  created:
    - tools/linux-flatpak/build.sh
    - .github/workflows/linux-flatpak.yml
  modified:
    - tests/test_packaging_linux_spec.py
    - .planning/REQUIREMENTS.md
decisions:
  - "Inline GPG signing (flatpak build-bundle --gpg-sign) instead of detached .sig sidecar — OSTree bundle format embeds signature (Critical Note #1)"
  - "Hard validator pre-flight gate sequenced BEFORE flatpak build-bundle (D-15): build FAILS on validator error, not skips"
  - "SKIP_SIGN=1 escape hatch for local iteration; CI never sets SKIP_SIGN"
  - "VERSION derived from pyproject.toml grep at build time for artifact naming"
  - "flatpak-builder system binary preferred; falls back to flatpak run org.flatpak.Builder if absent"
  - "workflow_dispatch-only CI with --privileged container (FUSE/OSTree requirement per RESEARCH.md Pitfall 9)"
metrics:
  duration: "~25 minutes"
  completed: "2026-06-02"
  tasks_completed: 3
  files_changed: 4
---

# Phase 86 Plan 04: Flatpak Build Driver + CI + Drift-Guards Summary

Produced a signed `MusicStreamer-<version>.flatpak` build pipeline mirroring Phase 85's AppImage discipline: `flatpak-builder` invocation + hard `appstreamcli`/`desktop-file-validate` pre-flight gate (D-15) + inline GPG signing via `flatpak build-bundle --gpg-sign` + `workflow_dispatch`-only CI with ephemeral GNUPGHOME; added PKG-LIN-FP-11 signing requirement and FP-04 `:ro`-mount reconciliation to REQUIREMENTS.md.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | REQUIREMENTS.md — PKG-LIN-FP-11 + FP-04 :ro reconciliation | b8eefb68 | `.planning/REQUIREMENTS.md` |
| 2 | Flatpak build.sh driver | 0bd2fee0 | `tools/linux-flatpak/build.sh` |
| 3 | CI workflow + build-script drift-guards | 2986cb4b | `.github/workflows/linux-flatpak.yml`, `tests/test_packaging_linux_spec.py` |

## Verification Results

- `bash -n tools/linux-flatpak/build.sh` exits 0 (valid syntax)
- `uv run --with pytest pytest tests/test_packaging_linux_spec.py -x` — 21/21 passed (4 new Flatpak guards + 17 AppImage guards, no regressions)
- `linux-flatpak.yml` contains `workflow_dispatch`, `--privileged`, invokes `tools/linux-flatpak/build.sh`, `if-no-files-found: error`
- `REQUIREMENTS.md` contains `PKG-LIN-FP-11` requirement bullet + traceability row, and `musicstreamer:ro` approved exception in FP-04

## Deviations from Plan

None — plan executed exactly as written.

## Key Technical Decisions

### Inline vs Detached Signing
The AppImage uses `gpg --detach-sign` producing a `.sig` sidecar alongside the `.AppImage`. For Flatpak, `flatpak build-bundle --gpg-sign` embeds the signature inside the OSTree bundle itself. No `.flatpak.sig` sidecar exists or should be uploaded. The drift-guards assert `--gpg-sign` is present in `build.sh` source text (not a sidecar file presence check). This is Critical Note #1 from PATTERNS.md.

### Hard Validator Gate Placement
The `appstreamcli validate` + `desktop-file-validate` pre-flight runs BEFORE `flatpak build-bundle`. On validator failure, `build.sh` emits `BUILD_FAIL reason=validator_failed` and exits (not a soft warning). This is the build-time half of D-15; the `test_flatpak_build_validator_gate` test is the test-time half.

### CI --privileged
`flatpak-builder` uses FUSE for OSTree commit operations. Without `--privileged` the job fails with `fuse: failed to open /dev/fuse: Operation not permitted`. The `options: "--privileged"` container config is the documented pattern for Flatpak CI (RESEARCH.md Pitfall 9).

### No Auto-Publish
The workflow is `workflow_dispatch`-only (D-07). D-06 (publishing the `.flatpak` as a GitHub release asset alongside the AppImage) is a manual operator step documented in `tools/linux-flatpak/README.md`: trigger CI → download artifact → `gh release upload <tag> MusicStreamer-<version>.flatpak`.

## Known Stubs

None — all build infrastructure is fully wired. The actual `flatpak install --user` + GNOME Software launch verification (FP-02/SC1) is the human-verified portion covered by Plan 05.

## Threat Flags

No new security-relevant surface beyond what the plan's threat model covers:

| Threat ID | Status |
|-----------|--------|
| T-86-10 (unsigned .flatpak) | Mitigated: `build.sh` fail-fast + inline `--gpg-sign` + `test_flatpak_build_gpg_sign` guard |
| T-86-11 (signing key leak) | Mitigated: ephemeral GNUPGHOME in CI + `if: always()` scrub step |
| T-86-12 (invalid metainfo/.desktop) | Mitigated: hard pre-flight gate in `build.sh` + `test_flatpak_build_validator_gate` |

## Self-Check: PASSED

| Item | Status |
|------|--------|
| `tools/linux-flatpak/build.sh` | FOUND |
| `.github/workflows/linux-flatpak.yml` | FOUND |
| `86-04-SUMMARY.md` | FOUND |
| Commit b8eefb68 | FOUND |
| Commit 0bd2fee0 | FOUND |
| Commit 2986cb4b | FOUND |
