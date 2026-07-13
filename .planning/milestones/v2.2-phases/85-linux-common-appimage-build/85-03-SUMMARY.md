---
phase: 85-linux-common-appimage-build
plan: "03"
subsystem: packaging/linux/ci
tags:
  - github-actions
  - appimage
  - ci-workflow
  - gpg-signing
  - workflow_dispatch
dependency_graph:
  requires:
    - "tools/linux-build/build.sh (Plan 85-01 production build driver)"
    - "tools/linux-build/verify-pins.sh (pin drift-guard called as CI step)"
    - "secrets.LINUX_SIGNING_KEY (GitHub repo secret — human-set, out of Phase 85 scope)"
    - "secrets.LINUX_SIGNING_KEY_ID (GitHub repo secret — human-set, out of Phase 85 scope)"
  provides:
    - ".github/workflows/linux-appimage.yml (manually-triggerable AppImage CI build, D-13/D-14/D-15/D-16)"
  affects:
    - "Plan 85-04 (cross-distro smoke — smoke_test.py absence tolerated by workflow; Plan 85-04 ships it)"
    - "PKG-LIN-APP-UPDATE follow-on infra milestone (artifact upload contract: MusicStreamer-*.AppImage*)"
tech_stack:
  added:
    - ".github/workflows/linux-appimage.yml — GitHub Actions workflow (workflow_dispatch-only)"
  patterns:
    - "D-13: workflow_dispatch-only manually-triggerable parity build on ubuntu-22.04"
    - "D-14: --appimage-extract-and-run for produced AppImage consumption in CI (Pitfall 11)"
    - "D-15: single-distro parity smoke only (no cross-distro, no GUI/MPRIS/screenshot)"
    - "D-16: ephemeral GNUPGHOME via mktemp -d; fail-fast if secrets absent; scrub on always()"
    - "T-85-03-02 mitigation: workflow_dispatch prevents fork-PR secret exposure"
key_files:
  created:
    - ".github/workflows/linux-appimage.yml"
  modified: []
decisions:
  - "D-16: LINUX_SIGNING_KEY imported into ephemeral mktemp GNUPGHOME; GPG_KEY_ID exported via GITHUB_ENV for build.sh D-09 gate"
  - "D-14: --appimage-extract-and-run used for smoke step (GitHub-hosted runners lack /dev/fuse, Pitfall 11)"
  - "D-15: smoke step tolerates absence of smoke_test.py — falls back to --smoke flag (Plan 85-04 ships smoke_test.py)"
  - "permissions: contents: read — no contents: write needed (no tag push, no release creation)"
  - "Locate step uses find -maxdepth 1 glob to robustly find the AppImage (same find-based approach as build.sh Task 4)"
metrics:
  duration: "~8 minutes (executor runtime)"
  completed: "2026-05-28"
  tasks_completed: 1
  tasks_total: 1
  files_created: 1
  files_modified: 0
---

# Phase 85 Plan 03: Create GitHub Actions CI Workflow for Linux AppImage Build Summary

**One-liner:** `workflow_dispatch`-only GitHub Actions CI workflow on ubuntu-22.04 that imports signing key into ephemeral GNUPGHOME, runs `build.sh`, performs single-distro parity smoke via `--appimage-extract-and-run`, verifies signature, and uploads AppImage + .sig as artifacts.

## What Was Built

One file created: `.github/workflows/linux-appimage.yml` (137 lines). This is the first GitHub Actions workflow in the repository (no `.github/` directory existed before this plan).

### Workflow Structure

The workflow has 9 steps across a single `build` job:

1. **Checkout** — `actions/checkout@v4`
2. **Install prerequisites** — `apt install yq` (needed by `build.sh` D-01 YAML parsing); verifies `docker --version` (preinstalled on ubuntu-22.04 runners)
3. **Validate signing secrets (D-16 fail-fast)** — checks `LINUX_SIGNING_KEY` and `LINUX_SIGNING_KEY_ID` are non-empty; emits `WORKFLOW_FAIL:` to stderr and exits 1 if either is missing
4. **Import signing key into ephemeral GNUPGHOME (D-16)** — `mktemp -d` keyring; `chmod 700`; loopback pinentry configuration; `printf '%s' | gpg --batch --import` (no shell expansion of key material); exports `GNUPGHOME` and `GPG_KEY_ID` via `$GITHUB_ENV`
5. **Verify toolchain pins** — `bash tools/linux-build/verify-pins.sh` (drift-guard, exits 2 on SHA mismatch)
6. **Build signed AppImage** — `bash tools/linux-build/build.sh` (same entry point as dev rig, inherits `GNUPGHOME` + `GPG_KEY_ID` from env)
7. **Locate produced artifacts** — `find tools/linux-build/artifacts -maxdepth 1 -name 'MusicStreamer-*.AppImage' -not -name '*.sig'`; fails fast if AppImage or .sig missing; exposes paths as step outputs
8. **Single-distro parity smoke (D-15)** — if `smoke_test.py` present: runs it via `--appimage-extract-and-run python smoke_test.py`; else: falls back to `--appimage-extract-and-run --smoke <url>`; `--appimage-extract-and-run` is mandatory (D-14 / Pitfall 11)
9. **Verify signature** — `gpg --verify <sig> <appimage>`
10. **Upload artifacts** — `actions/upload-artifact@v4`, glob `MusicStreamer-*.AppImage` + `MusicStreamer-*.AppImage.sig`, `if-no-files-found: error`, 30-day retention
11. **Scrub GNUPGHOME** (`if: always()`) — defense-in-depth deletion of ephemeral keyring even if earlier steps fail

### Security Properties (D-16)

- `workflow_dispatch:` is the ONLY trigger — no `push:`, `pull_request:`, `schedule:`. Fork-PR cannot invoke this workflow and cannot therefore expose `LINUX_SIGNING_KEY` (T-85-03-02 mitigation).
- `LINUX_SIGNING_KEY` is mapped to step `env:` (not global env); GitHub Actions auto-masks secret values in logs.
- Key material imported via stdin (`printf '%s' ... | gpg --batch --import`), never shell-expanded.
- `permissions: contents: read` — default; no write access, no release creation, no tag push.
- GNUPGHOME scrubbed on `if: always()` even if build or smoke fails.

## Key Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create .github/workflows/linux-appimage.yml | 6196124 | .github/workflows/linux-appimage.yml |

## Must-Haves Verification

All `must_haves.truths` from the plan frontmatter verified via source-grep + YAML parse:

| Truth | Verified | Method |
|-------|----------|--------|
| `workflow_dispatch:` only trigger | PASS | `! grep "push:\|pull_request:\|schedule:"` |
| `runs-on: ubuntu-22.04` | PASS | `grep -q "runs-on: ubuntu-22.04"` |
| Ephemeral GNUPGHOME via `mktemp -d` | PASS | `grep -q "GNUPGHOME="` + source review |
| Fail-fast if secrets unset | PASS | `if [[ -z ... ]] exit 1` block present |
| Imports key before `build.sh` | PASS | step order: import → verify-pins → build |
| Runs `bash tools/linux-build/build.sh` | PASS | `grep -q "bash tools/linux-build/build.sh"` |
| `--appimage-extract-and-run` for produced AppImage | PASS | smoke step uses flag |
| No GUI/MPRIS/screenshot steps | PASS | no xvfb, no dbus-launch, no screenshot commands |
| `actions/upload-artifact@v4` with `if-no-files-found: error` | PASS | both present |
| `gpg --verify` step | PASS | present after smoke step |
| No `permissions: contents: write` | PASS | only `contents: read` declared |
| Valid YAML | PASS | `python3 -c "import yaml; yaml.safe_load(...)"` |

### Artifact Upload Glob Contract

Upload path globs are:
- `tools/linux-build/artifacts/MusicStreamer-*.AppImage`
- `tools/linux-build/artifacts/MusicStreamer-*.AppImage.sig`

These match the current `build.sh` output (`MusicStreamer-x86_64.AppImage` + `MusicStreamer-x86_64.AppImage.sig`) and will also match any future versioned naming (e.g., `MusicStreamer-2.2.0-x86_64.AppImage`).

### smoke_test.py Tolerance

The smoke step checks for `tools/linux-build/smoke_test.py` at workflow run time. Plan 85-04 ships that file. Until then, the workflow falls back to `--smoke http://ice1.somafm.com/groovesalad-128-mp3` which exercises the bundled GStreamer + production module import path.

## Deviations from Plan

None — plan executed exactly as written. The YAML content follows the plan's Task 1 `<action>` block verbatim. The one note about `yaml.safe_load` interpreting `on:` as `True` (boolean key) is a known Python pyyaml behavior, not a file defect: GitHub Actions processes `on:` correctly. The verify command from the plan passes (`python3 -c "import yaml; yaml.safe_load(open(...))"`).

## Known Stubs

None — the workflow is complete. The only conditional branch is the `smoke_test.py` presence check, which has a documented fallback and is not a stub.

## Threat Flags

Per plan threat model (T-85-03-01 through T-85-03-06):

| Flag | File | Description |
|------|------|-------------|
| threat_flag: secret-in-workflow-env | .github/workflows/linux-appimage.yml | LINUX_SIGNING_KEY crosses from GitHub secret store to step env. Mitigated: GitHub auto-masks; stdin import; ephemeral GNUPGHOME; scrub on always(). |

T-85-03-SC (apt install yq): accepted — Ubuntu APT repos are Canonical-signed; no npm/pip/cargo install.

## Self-Check: PASSED

**Files exist check:**

| File | Status |
|------|--------|
| .github/workflows/linux-appimage.yml | FOUND |

**Commits exist check:**

| Commit | Status |
|--------|--------|
| 6196124 (Task 1) | FOUND |
