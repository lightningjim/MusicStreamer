---
phase: 56-windows-di-fm-smtc-start-menu
plan: 05
subsystem: uat
tags: [uat, win11-vm, di-fm, smtc, settings-import-roundtrip, release-grade]

requires:
  - phase: 56
    provides: "Plans 56-01 (helper) + 56-02 (wire) + 56-03 (diagnostic) + 56-04 (drift guard + README) all complete"
provides:
  - "All four ROADMAP SC attestations for Phase 56 (SC #1-#4 all PASS)"
  - "Release-grade re-attestation against the freshly-built installer"
  - "Surfaced F1 (AA insert format on Windows differs from CONTEXT.md premise — no code impact, idempotency saves us)"
  - "Surfaced F2 (AAC streams broken on Windows — Phase 57+ candidate)"
  - "Surfaced F3 (edit-while-fetching crash, already fixed in main, now baked into the Windows installer)"
affects: [phase-56-completion, phase-57-candidates]

tech-stack:
  added: []
  patterns:
    - "Operator-paste-back UAT protocol for Win11 VM work driven from Linux orchestrator"
    - "Path C (python -m direct from current source) as a fast WIN-01 attestation when installer rebuild isn't needed; Path A (full rebuild + force-fresh) as the release-grade follow-up"

key-files:
  created:
    - .planning/phases/56-windows-di-fm-smtc-start-menu/56-05-UAT-LOG.md
  modified: []

key-decisions:
  - "Phase 56 ships — all four ROADMAP SCs attested PASS at release-grade (post-rebuild + force-fresh-install + Start-Menu launch)"
  - "WIN-01a (fresh AA import): operator played DI.fm Afro House in 3s with ICY title 'Ame, Busiswa - Pha Na Pha (Original Mix)' — first via Path C (python -m current source), then re-attested in the installed binary"
  - "WIN-01b (settings-import ZIP roundtrip): operator imported a Linux-edited https://di.fm row, pressed Play, and it played fine — strict proof the play-time rewrite at _set_uri engages on stored https rows (the only meaningful test of D-01 given F1)"
  - "WIN-02 SMTC: overlay reads 'MusicStreamer' on the freshly-installed binary launched via Start Menu shortcut — confirmed both in 56-03 PRE-FIX (screenshot at screenshots/56-03-smtc-prefix.png) and re-attested post-rebuild"
  - "F1 (AA import on Windows produces http:// directly, not https:// as CONTEXT.md assumed) — documentation drift only; helper is still correct (idempotent passthrough)"
  - "F2 (AAC streams don't play on Windows) — captured as Phase 57+ candidate; out of scope for Phase 56"
  - "F3 (edit-while-fetching crash, already fixed in main but absent from v2.0.0 installer) — now baked into the rebuilt installer; release-grade bonus"

patterns-established:
  - "Diagnose-first protocol (D-07/D-08) saved this phase from a speculative refactor — the SMTC wiring was never broken, just under-documented and under-guarded against future drift"
  - "When a phase's own UAT surfaces a CONTEXT.md premise mismatch (here: AA insert format on Windows), record it as a Finding in the UAT log + carry forward to next phase's discuss session — don't silently rewrite history"

requirements-completed: [WIN-01, WIN-02]

duration: ~30min
completed: 2026-05-02
---

# Phase 56 / Plan 05 Summary — UAT PASS, ship phase

**Both halves of Phase 56 attested PASS on a release-grade install. WIN-01 helper engages on stored https://di.fm rows at the play-time URI boundary as D-01 specifies; WIN-02 SMTC overlay reads "MusicStreamer" via the Start Menu launch path. Phase ready to ship.**

## Performance

- **Duration:** ~30 min total (Path C unit attestation + Path A release-grade rebuild + force-fresh-install + re-attestation)
- **Started:** 2026-05-02
- **Completed:** 2026-05-02
- **Tasks:** 5/5 (Task 4 / WIN-02 cited from 56-03 evidence + re-attested post-rebuild)
- **Files modified:** 1 created (`56-05-UAT-LOG.md`)

## Three attestations

| Criterion | Result | Evidence |
|-----------|--------|----------|
| WIN-01a (fresh AA import) | ✓ PASS | DI.fm Afro House played in 3s with ICY title; re-attested in installed binary post-rebuild |
| WIN-01b (settings-ZIP roundtrip — strict D-01 test) | ✓ PASS | Linux-edited https://di.fm row imported, played fine on VM; play-time rewrite at `_set_uri` confirmed |
| WIN-02 (SMTC overlay reads "MusicStreamer") | ✓ PASS | 56-03 screenshot + Get-StartApps confirms AppID `org.lightningjim.MusicStreamer`; re-attested in rebuilt installer |

## Phase-completion decision

**ship-phase.** Run `/gsd-verify-work 56` for goal-backward verification, then `/gsd-complete-phase` (or `/gsd-ship`) to close.

## Findings to carry forward

- **F1: AA import on Windows produces `http://` rows natively** (not `https://` as CONTEXT.md assumed). Documentation drift; helper's idempotency masks this from being a defect. Capture in next phase's discuss session.
- **F2: AAC streams don't play on Windows.** Suspected missing/misbundled GStreamer AAC decoder. New bug for Phase 57+ (target id e.g. `WIN-05`).
- **F3: Edit-while-fetching crash** — already fixed in `main`; the rebuild bakes it into the Windows installer (release-grade bonus).

## Verification

- `.planning/phases/56-windows-di-fm-smtc-start-menu/56-05-UAT-LOG.md` exists with `## WIN-01a`, `## WIN-01b`, `## WIN-02`, `## Phase Completion Decision` sections all present
- `grep -ic 'PASS' 56-05-UAT-LOG.md` returns >= 3
- No literal `listen_key=...` values present (T-56-03 — discipline maintained; UAT log redacted by construction since the operator never pasted raw debug logs containing the key)
- All four ROADMAP SCs covered (SC #1, #2, #3, #4)

## Deferred Issues

- F2 (AAC bug) — Phase 57+ candidate; capture in REQUIREMENTS.md as `WIN-05` (or next available WIN-NN)
- F1 (AA import format premise mismatch) — documentation note; bring up in next phase's discuss session
- Pre-existing test failures in `test_media_keys_*` documented in 56-01-SUMMARY.md / 56-02-SUMMARY.md remain deferred to Phase 57 (WIN-04)
