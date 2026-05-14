---
phase: 74
plan: "04"
status: gap-closure-needed
created: "2026-05-14"
type: execute
wave: 3
---

# Plan 74-04 Summary: Live SomaFM UAT

## Outcome

User walked the 10-row UAT checklist against `api.somafm.com:443` on 2026-05-14 with 7 pre-existing SomaFM rows in the library.

| UAT | Decision | Verdict | Detail |
|-----|----------|---------|--------|
| UAT-01 | D-06 | PASS | `Importing SomaFM…` toast on hamburger click |
| UAT-02 | D-08 | PASS | ~5 sec wall-clock to final toast |
| UAT-03 | D-06 | PASS | `SomaFM import: 39 stations added` (39 + 7 baseline = 46 = live catalog count) |
| UAT-04 | D-04 | PASS | No auto-import on app reopen |
| UAT-05 | D-11 | PASS | SomaFM logos render in station tree |
| UAT-06 | — | PASS | Synphaera Radio plays within 5 sec |
| **UAT-07** | **D-05** | **FAIL** | **No toast on second import — `SomaFM import: no changes` was never emitted** |
| UAT-08 | D-13 | PASS | All 5 sample rows show `cover_art_source = auto` |
| UAT-09 | D-02 | PASS | Provider name resolves to exactly `SomaFM` via JOIN |
| UAT-10 | D-03 | PASS | Stream counts: Groove Salad/Drone Zone show 25 (user pre-added 128 MP3+AAC, 5 extra streams — accepted), all other SomaFM stations show exactly 20 (4 tiers × 5 ICE relays) |

**Result:** 9 PASS / 1 FAIL — phase routes to Phase 74.1 gap closure.

## Open items routed to Phase 74.1

### G-01 (UAT-07): re-import emits no toast
- Repro: import SomaFM successfully → click hamburger → "Import SomaFM" again.
- Expected: final toast `SomaFM import: no changes` per D-05.
- Observed: NO toast at all (neither progress nor final).
- Likely path: `MainWindow._on_soma_import_finished` (or the `_SomaImportWorker` → `import_finished` signal flow) skips the toast emission when `inserted == 0`. Could also be: dedup raises an exception that the error toast doesn't surface, or the menu action becomes inert after first run.
- Triage steps for the gap-closure plan:
  1. Add a Wave-2-style RED qtbot test in `tests/test_main_window_soma.py` that mocks `import_stations` to return `(inserted=0, skipped=46)` and asserts the toast text is exactly `SomaFM import: no changes`.
  2. Walk the `_on_soma_import_finished` slot and verify it emits the toast even when `inserted == 0`.

### G-02 (Findings F-01): bitrate parser returns 128 for high-bitrate streams
- Repro: import SomaFM → query Synphaera Radio's streams → URL `https://ice2.somafm.com/synphaera-256-mp3` is stored with `bitrate_kbps = 128`.
- Suspect: `musicstreamer/soma_import.py::_resolve_pls` bitrate-from-URL parser fails on the SomaFM `<slug>-<kbps>-<codec>` URL pattern and falls through to the 128 default.
- Impact: Phase 70 hi-res indicator + station-streams sort order downgrade these streams; the `hi`/`hi2`/`med`/`low` tier mapping (D-03) is poisoned for any SomaFM channel that publishes a non-128 stream.
- Triage steps for the gap-closure plan:
  1. Add a Wave-1-style RED unit test in `tests/test_soma_import.py` that feeds a PLS containing `synphaera-256-mp3` URLs and asserts `bitrate_kbps == 256`.
  2. Walk `_resolve_pls` and the bitrate parser; likely a regex anchored to the wrong group or a missing branch for `-NNN-mp3` / `-NNN-aac` slug patterns.

## Process notes

- Live UAT also surfaced a planning defect: the planner's UAT scaffold used `library.db` and a non-existent `stations.provider_name` column. Fixed in commit `e960008` (and recorded as `reference_musicstreamer_db_schema.md` in user memory) before the user walked the checklist. Future UAT plans against this DB must JOIN `stations.provider_id → providers.id`.
- UAT-05's wording is ambiguous in the LOG (the user said the SomaFM stations "DO have the placeholder" while marking it [X]) — interpreted as PASS per the user's verdict, but worth a one-line clarification in any Phase 74.1 UAT-LOG.

## Sign-off

`74-04-UAT-LOG.md` status: `gap-closure-needed`. Sign-off checkbox ticked. Phase 74 is **not** marked complete — proceed to `/gsd-plan-phase 74 --gaps`.
