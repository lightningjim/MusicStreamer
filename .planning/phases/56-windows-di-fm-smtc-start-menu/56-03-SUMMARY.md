---
phase: 56-windows-di-fm-smtc-start-menu
plan: 03
subsystem: windows-packaging
tags: [windows, smtc, aumid, diagnostic, win11-vm, manual-uat, get-startapps]

requires:
  - phase: 43.1
    provides: AUMID setter wiring (`_set_windows_aumid`) and `LPCWSTR` argtypes pattern
  - phase: 44
    provides: Inno Setup Start Menu shortcut declaring `AppUserModelID: org.lightningjim.MusicStreamer`
provides:
  - Empirical evidence that the SMTC AUMID wiring is correct in code (LNK + in-process readback both match)
  - Empirical evidence that the original "Unknown app" symptom is a launch-discipline issue (D-09 #2, Pitfall #4), not a code bug
  - Diagnostic log + screenshot at `.planning/phases/56-windows-di-fm-smtc-start-menu/56-03-DIAGNOSTIC-LOG.md` and `screenshots/56-03-smtc-prefix.png`
  - Plan 56-04 scope decision: docs-only branch (README launch note + drift-guard pytest; no production code change)
affects: [56-04, 56-05]

tech-stack:
  added: []
  patterns:
    - "Operator-paste-back interactive checkpoint protocol (Linux orchestrator drives, user runs PowerShell on the VM, pastes outputs back)"
    - "No-patch in-process AUMID readback via one-liner that imports `_set_windows_aumid` from current source (avoids T-56-Diag-B revert risk entirely)"

key-files:
  created:
    - .planning/phases/56-windows-di-fm-smtc-start-menu/56-03-DIAGNOSTIC-LOG.md
    - .planning/phases/56-windows-di-fm-smtc-start-menu/screenshots/56-03-smtc-prefix.png
  modified: []

key-decisions:
  - "D-09 root cause: #2 (wrong launch path was the original 'Unknown app' source). LNK AppID, in-process AUMID, and SMTC overlay all read 'org.lightningjim.MusicStreamer' / 'MusicStreamer' correctly when launched via the Start Menu shortcut."
  - "D-10 Plan 04 scope: docs-only. NO change to `musicstreamer/__main__.py` or `packaging/windows/MusicStreamer.iss`. Add `tests/test_aumid_string_parity.py` drift guard (RESEARCH.md Open Question #1, adopted) + a Windows launch-discipline note in `packaging/windows/README.md`."
  - "Task 5 (force-fresh install) skipped per operator decision — symptom not reproducing means there is nothing to fix, only a regression-confirm test would remain, which is destructive without commensurate value on this run. Skip rationale recorded in DIAGNOSTIC-LOG.md."
  - "Method C used for Step 2 in-process AUMID readback: a no-patch Python one-liner that imports `_set_windows_aumid` from current source, calls it in a fresh `python.exe`, and reads back via `GetCurrentProcessExplicitAppUserModelID`. Cleaner than Method B (temporary patch + revert) — avoids T-56-Diag-B by construction."

patterns-established:
  - "When a 'never reproducible in code' bug surfaces, run the diagnose-first protocol BEFORE refactoring — D-07 / D-08 protected against speculative AUMID rewiring that would have broken Phase 43.1's working code."
  - "`Get-StartApps | Where-Object Name -like '<app>*'` is the canonical AUMID readback for Windows shell-mediated bindings, not `(New-Object -ComObject Shell.Application)…ExtendedProperty('System.AppUserModel.ID')` (Pitfall #3)."

requirements-completed: [WIN-02]

duration: ~15min
completed: 2026-05-02
---

# Phase 56 / Plan 03 Summary — Win11 SMTC AUMID Diagnostic

**Diagnose-first surfaced the truth: the AUMID wiring was never broken — the bug was launch-discipline. Plan 04 ships docs + a drift-guard, no production code change.**

## Performance

- **Duration:** ~15 min (interactive paste-back from Win11 VM)
- **Started:** 2026-05-02
- **Completed:** 2026-05-02
- **Tasks:** 6/6 (1 skipped per operator decision with rationale)
- **Files modified:** 1 created (`56-03-DIAGNOSTIC-LOG.md`) + 1 screenshot

## Accomplishments

1. **D-08 Step 1 (Get-StartApps PRE-FIX):** Outcome A — LNK AppID is exactly `org.lightningjim.MusicStreamer`; `MusicStreamer.lnk` exists at `%APPDATA%\Microsoft\Windows\Start Menu\Programs\`. Rules out D-09 #1 and #3.
2. **D-08 Step 2 (in-process readback PRE-FIX):** Method C (no-patch Python one-liner) returned `'org.lightningjim.MusicStreamer'` — MATCHES Step 1. Rules out D-09 #3 again.
3. **D-08 Step 3 (SMTC overlay PRE-FIX):** Launched via Start Menu shortcut, played SomaFM Drone Zone, opened SMTC overlay — header reads **`MusicStreamer`** (not "Unknown app"). Screenshot at `screenshots/56-03-smtc-prefix.png`. Definitively confirms D-09 #2.
4. **D-08 Step 4 (force-fresh install POST-FIX):** Skipped per operator decision — nothing to fix; rationale recorded in DIAGNOSTIC-LOG.md.
5. **D-09 classification:** **#2 (wrong launch path)** — original "Unknown app" observations were almost certainly from `python -m musicstreamer` or the installer's post-install Run checkbox, both of which bypass the Start-Menu-LNK → AUMID binding (Pitfall #4).
6. **D-10 Plan 04 scope:** **docs-only** — drift-guard pytest + Windows README launch note; NO change to `__main__.py` or `MusicStreamer.iss`.

## How Plan 56-04 reads this

Plan 56-04's first task is to read this SUMMARY for the D-10 branch decision. The branch is **docs-only**:
- Add `tests/test_aumid_string_parity.py` (drift-guard pytest, RESEARCH.md Open Question #1 adopted).
- Add a "Launching MusicStreamer on Windows" note to `packaging/windows/README.md` citing Pitfall #4 and D-09 #2.
- NO production code change. NO installer rebuild required.

## How Plan 56-05 reads this

UAT Plan 56-05 already has its WIN-02 attestation pre-staged: SMTC overlay reads `MusicStreamer` on this Win11 VM with the v2.0.0 installer, screenshot at `screenshots/56-03-smtc-prefix.png`. The UAT may re-attest after Plan 56-04 lands the README/drift-guard, OR cite this evidence directly if the operator considers the in-place verification sufficient (operator decision at UAT time).

## Verification

- `.planning/phases/56-windows-di-fm-smtc-start-menu/56-03-DIAGNOSTIC-LOG.md` exists with all four `## D-08 Step N` headings + `## D-09 Root Cause` heading present.
- `git status musicstreamer/__main__.py` clean (Method C avoided the patch surface).
- `git diff musicstreamer/ packaging/` empty (no production code change in this plan).
- Screenshot evidence at `.planning/phases/56-windows-di-fm-smtc-start-menu/screenshots/56-03-smtc-prefix.png`.

## Deferred Issues

None. Plan 56-04 picks up the docs-only follow-up work; Plan 56-05 picks up the final UAT.
