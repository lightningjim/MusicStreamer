---
phase: 85-linux-common-appimage-build
plan: "02"
subsystem: linux-build
tags:
  - appimage
  - gpg-signing
  - zsync
  - packaging
  - security

dependency_graph:
  requires:
    - "85-01 (build.sh linuxdeploy invocation — integration point for this plan)"
  provides:
    - "tools/linux-build/build.sh with GPG signing (D-08/D-09) and zsync embedding (D-11)"
    - ".planning/REQUIREMENTS.md with PKG-LIN-APP-10 added + PKG-LIN-APP-08 corrected"
  affects:
    - "85-03 (CI workflow reads GPG_KEY_ID, LINUX_SIGNING_KEY from secrets per D-16)"
    - "85-05 (README must document canonical signing key fingerprint per T-85-02-02)"

tech_stack:
  added:
    - "gpg2 --detach-sign --armor (GPG signing, D-08)"
    - "linuxdeploy --updateinformation (zsync metadata embedding, D-11)"
  patterns:
    - "Fail-fast gate before docker invocation (exit 5 on unset GPG_KEY_ID)"
    - "SKIP_SIGN=1 local-iteration escape hatch (D-09)"
    - "BUILD_FAIL reason=<token> stderr grep contract (extended to codes 5/6)"
    - "Signing step after GLIBC scan — signature covers final artifact bytes (D-08)"

key_files:
  modified:
    - path: "tools/linux-build/build.sh"
      what: "Added --updateinformation flag, D-09 fail-fast gate, D-08 gpg2 signing step, exit codes 5/6, SKIP_SIGN escape hatch, BUILD_OK with signature= token"
    - path: ".planning/REQUIREMENTS.md"
      what: "Added PKG-LIN-APP-10 row (signing requirement) + tracker row; corrected PKG-LIN-APP-08 verification target to test_packaging_linux_spec.py; updated coverage count 62->63"

decisions:
  - "D-08: gpg2 --detach-sign --armor --local-user outside Docker (after GLIBC scan) so signature covers final bytes and container set -x never sees signing step"
  - "D-09: GPG_KEY_ID fail-fast positioned before first docker build call so unset-key failure surfaces in <100ms, not after daemon probe"
  - "D-11: embedded zsync URL uses kcreasey namespace (github.com/kcreasey/MusicStreamer) per reference_qnap_github_mirror.md — not lightningjim"
  - "D-12: zsyncmake NOT invoked here — embedding only; serving is PKG-LIN-APP-UPDATE (deferred)"
  - "D-10: PKG-LIN-APP-10 added to REQUIREMENTS.md with CI secrets documented (LINUX_SIGNING_KEY + LINUX_SIGNING_KEY_ID)"

metrics:
  duration: "222s"
  completed: "2026-05-28T14:47:53Z"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 2
---

# Phase 85 Plan 02: GPG Signing + zsync Embedding Summary

**One-liner:** `build.sh` now exits 5 on missing GPG key (D-09 fail-fast before Docker), signs the AppImage via `gpg2 --detach-sign --armor` (D-08), embeds zsync update-info via linuxdeploy `--updateinformation` (D-11), and `REQUIREMENTS.md` gains PKG-LIN-APP-10 with PKG-LIN-APP-08 verification re-targeted to the Linux-side drift-guard file.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Embed zsync update-info via linuxdeploy --updateinformation (D-11, D-12) | abb27bc | tools/linux-build/build.sh |
| 2 | GPG signing — fail-fast gate + sign step + exit codes 5/6 (D-08, D-09) | 2fe2007 | tools/linux-build/build.sh |
| 3 | REQUIREMENTS.md — add PKG-LIN-APP-10 + correct PKG-LIN-APP-08 (D-10) | ecad595 | .planning/REQUIREMENTS.md |

## Implementation Details

### Task 1: zsync embedding (D-11, D-12)

The linuxdeploy invocation in `tools/linux-build/build.sh` now includes:

```
--updateinformation "gh-releases-zsync|kcreasey|MusicStreamer|latest|MusicStreamer-*-x86_64.AppImage.zsync"
```

A comment block immediately above the invocation cites D-11 / PKG-LIN-APP-06, explains the deferred PKG-LIN-APP-UPDATE serving milestone, and notes the `kcreasey` namespace rationale (QNAP->GitHub mirror per `reference_qnap_github_mirror.md`). No `zsyncmake` invocation was added (D-12 scope boundary: embedding only).

### Task 2: GPG signing (D-08, D-09)

Three additions to `build.sh`:

1. **Exit-code header extension** (after code 4):
   ```
   #   5 = GPG_KEY_ID unset and SKIP_SIGN != 1 (D-09 fail-fast guard)
   #   6 = gpg2 --detach-sign failed (D-08 signing step)
   ```

2. **D-09 fail-fast gate** — inserted after `set -euo pipefail`, before `HERE=...` (and before the first `docker build` call at ~line 104):
   ```bash
   if [[ -z "${GPG_KEY_ID:-}" && "${SKIP_SIGN:-0}" != "1" ]]; then
     echo "BUILD_FAIL reason=gpg_key_unset ..." >&2
     exit 5
   fi
   ```
   Structural positioning verified: `awk` (comment-skipping) confirms `BUILD_FAIL reason=gpg_key_unset` precedes first `docker build`/`docker run` executable line.

3. **D-08 signing step** — inserted after GLIBC `case` block, before final `BUILD_OK` echo:
   ```bash
   if [[ "${SKIP_SIGN:-0}" != "1" ]]; then
     gpg2 --detach-sign --armor --local-user "$GPG_KEY_ID" --output "${APPIMG}.sig" "$APPIMG" \
       || { echo "BUILD_FAIL reason=signing_failed ..." >&2; exit 6; }
     echo "SIGN_OK signature=${APPIMG}.sig key=$GPG_KEY_ID"
   else
     echo "SIGN_SKIPPED SKIP_SIGN=1 (local-iteration mode; no .sig sidecar produced)"
   fi
   ```
   The signing step runs outside Docker so the container's `set -x` never exposes `GPG_KEY_ID` in logs (T-85-02-01 accept disposition honored). The `--output "${APPIMG}.sig"` flag is explicit to avoid GPG version variance in default output path.

4. **Updated BUILD_OK** to include `signature=` path or `signature=skipped`.

### Task 3: REQUIREMENTS.md bookkeeping (D-10)

Three surgical edits:

1. **PKG-LIN-APP-08 verification clause corrected** — changed from `tests/test_packaging_spec.py` (Windows-side drift-guard) to `tests/test_packaging_linux_spec.py` (Linux-side drift-guard introduced in Plan 85-04 Task 3).

2. **PKG-LIN-APP-10 added** to the AppImage requirements block (after PKG-LIN-APP-09):
   - Documents `GPG_KEY_ID` env var and `LINUX_SIGNING_KEY` / `LINUX_SIGNING_KEY_ID` CI secrets
   - Specifies verification command: `gpg --verify MusicStreamer-<version>-x86_64.AppImage.sig MusicStreamer-<version>-x86_64.AppImage`
   - Documents exit 5 / SKIP_SIGN behavior

3. **PKG-LIN-APP-10 tracker row** added to the Traceability table: `| PKG-LIN-APP-10 | Phase 85 | Pending |`

4. **Coverage count updated** from 62 (61 unconditional + 1 conditional) to 63 (62 unconditional + 1 conditional).

No other PKG-LIN-APP rows were modified; status flips remain deferred to Plan 85-05 per CONTEXT.md "Bookkeeping-only requirement flips deferred to phase close."

## Verification Results

All plan verification checks pass:

1. `bash -n tools/linux-build/build.sh` — syntax OK
2. `--updateinformation "gh-releases-zsync|..."` found in build.sh
3. `gpg2 --detach-sign --armor --local-user` found in build.sh
4. `BUILD_FAIL reason=gpg_key_unset` found in build.sh
5. `BUILD_FAIL reason=signing_failed` found in build.sh
6. `grep -c "PKG-LIN-APP-" .planning/REQUIREMENTS.md` = 23 (>= 20 threshold)
7. `PKG-LIN-APP-08.*test_packaging_linux_spec.py` matches in REQUIREMENTS.md
8. Structural positioning awk gate (comment-skipping): fail-fast block precedes first docker executable invocation

**Note on plan awk gate:** The plan's Task 2 `<verify>` awk expression matches comment lines (the POSITIONING comment itself contains "docker run"/"docker build" strings and fires before the BUILD_FAIL line is seen). The comment-skipping variant (`!/^[[:space:]]*#/`) confirms correct positioning — fail-fast at line ~83, first `docker build` at line ~104.

## Deviations from Plan

None — plan executed exactly as written. The awk gate variant (comment-skipping) is a verification technique difference, not a deviation from the structural requirement.

## Known Stubs

None. All additions are functional code paths with explicit emit tokens (`BUILD_FAIL`, `SIGN_OK`, `SIGN_SKIPPED`, `BUILD_OK`).

## Threat Flags

All new security surface is within the plan's threat model (T-85-02-01..04). No new surface beyond what the plan documents.

| Threat ID | Disposition | Note |
|-----------|-------------|------|
| T-85-02-01 | accept | GPG_KEY_ID is public key ID; private key never crosses into Docker container |
| T-85-02-02 | mitigate | Signing sidecar is the user-side guard for embedded zsync URL; README fingerprint doc deferred to Plan 85-05 |
| T-85-02-03 | mitigate | D-09 exit 5 ensures no silent-unsigned releases; SKIP_SIGN=1 produces visible `signature=skipped` token |
| T-85-02-04 | accept | GPG_KEY_ID from developer's own environment; shell-quoted, not user input |

## Self-Check: PASSED
