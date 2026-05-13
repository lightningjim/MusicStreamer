---
status: testing
phase: 71-sister-station-expansion-1-add-ability-to-link-sister-statio
source:
  - 71-00-SUMMARY.md
  - 71-01-SUMMARY.md
  - 71-02-SUMMARY.md
  - 71-03-SUMMARY.md
  - 71-04-SUMMARY.md
  - 71-05-SUMMARY.md
  - 71-06-SUMMARY.md
  - 71-07-SUMMARY.md
  - 71-08-SUMMARY.md
  - 71-VERIFICATION.md
  - 71-VALIDATION.md
started: "2026-05-13T00:00:00Z"
updated: "2026-05-13T00:00:00Z"
---

## Current Test

1. Cross-provider AA name-mismatch link (Classical Relaxation / Relaxing Classical)

## Tests

### 1. Cross-provider AA name-mismatch link
expected: |
  Open EditStationDialog on "Classical Relaxation" (or its cross-provider sister).
  Click `+ Add sibling`. Pick the other provider in the combo, select the sister station,
  click `Link Station`. A new chip appears in the "Also on:" row of the dialog with
  the partner's name and an `×` unlink button. Close + reopen the dialog — chip persists.
  Click the partner chip name — dialog switches to that station's editor. Open NowPlaying
  for either station — "Also on:" line shows the partner.
result: [pending]

### 2. SomaFM 3× Groove Salad multi-link
expected: |
  Open EditStationDialog on "Groove Salad". Click `+ Add sibling`, link "Classic Groove Salad".
  Click `+ Add sibling` again, link "Groove Salad 2". Both manual chips visible in
  the "Also on:" row, each with `×`. Open EditStationDialog on "Classic Groove Salad" —
  the chip row shows Groove Salad (the one we linked from) but NOT Groove Salad 2
  (per CONTEXT D-04 — no transitive closure). Click `×` on one chip — link removed,
  toast appears confirming the unlink, the chip disappears from the row.
result: [pending]

### 3. ZIP export/import round-trip carries siblings
expected: |
  Link 2 sibling pairs in your source DB (e.g., A↔B and C↔D). Hamburger menu →
  Export settings → save ZIP. Manually delete the partner stations B and D from
  the source DB (via Edit dialog delete or station CRUD). Hamburger → Import
  settings → pick the ZIP. All 4 stations restored. Sibling links restored
  (A↔B and C↔D). Open NowPlaying for A and C — "Also on:" rows render correctly
  showing B and D respectively.
result: [pending]

### 4. AA auto + manual co-exist on "Also on:" line
expected: |
  Pick a DI.fm station that has a known cross-network AA sibling (one already
  shown in "Also on:" via Phase 51 — bare chip, no `×`). Add a manual sibling
  to that same station pointing to a DIFFERENT (non-AA) station. NowPlaying
  shows two chips in "Also on:": the AA chip (bare, no `×`) and the manual chip
  (with `×`). Click `×` on the manual chip — manual link removed, AA chip
  remains visible and clickable.
result: [pending]

### 5. CR-02 regression — AA + manual collision (verifier-flagged)
expected: |
  Manually link a station that is ALSO an AA auto-detected sibling (i.e., the
  same partner station shows up in both lists). Open EditStationDialog on the
  current station. After the fix, this collision case renders as a single bare
  AA chip (no `×`) — NOT a manual chip with `×`. This matches `merge_siblings`
  AA-wins precedence on both surfaces (EditStationDialog and NowPlaying). If
  you remove the manual link via Repo CRUD or by editing the URL so the AA
  detection no longer matches, the manual chip then reappears with `×`. Both
  surfaces stay in sync — never show different chips for the same partner.
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
