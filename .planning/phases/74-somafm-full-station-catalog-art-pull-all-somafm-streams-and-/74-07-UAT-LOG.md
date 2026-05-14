---
phase: 74
plan: "07"
status: gap-closure-uat-pending
created: "2026-05-14"
addresses_gaps:
  - "G-01 (SOMA-11 / UAT-07): _SomaImportWorker.finished shadowing — re-import 'no changes' toast"
  - "G-02 (SOMA-02 / UAT Finding F-01): hardcoded bitrate_kbps=128 for MP3-highest tier — Synphaera 256 kbps stored as 128"
---

# Phase 74 Plan 07: Gap-Closure UAT Re-Verification

Plans 74-05 and 74-06 closed both VERIFICATION.md blockers via code changes plus automated tests (31/31 tests pass: 15 soma_import + 8 main_window_soma + 8 constants_drift). This plan re-runs the two previously-failing live-UAT rows against the running app + live `api.somafm.com` to confirm the fixes hold end-to-end.

**Source-grep gates (already confirmed against `main` at commit `46c8e15`):**
- G-01: `grep -E '^\s+finished\s*=\s*Signal' musicstreamer/ui_qt/main_window.py` → 0 matches. All four worker classes now use distinct names (`export_finished`, `preview_finished`, `import_finished` × 2).
- G-02: `import re` present, `_bitrate_from_url` defined and called at the `fetch_channels` streams.append site, regex literal is exactly `r"-(\d+)-(?:mp3|aac|aacp)\b"`.

---

## Pre-test: Establish DB state

DB path: `~/.local/share/musicstreamer/musicstreamer.sqlite3` (resolved by `musicstreamer/paths.py:39`). Schema reminder: `stations.provider_id` is an FK to `providers.id`; there is NO `provider_name` column on `stations` — SomaFM queries require a JOIN.

Confirm SomaFM rows already exist (from Phase 74.0 import):

```bash
sqlite3 ~/.local/share/musicstreamer/musicstreamer.sqlite3 \
  "SELECT count(*) FROM stations s JOIN providers p ON s.provider_id=p.id WHERE p.name='SomaFM'"
```

Record the count here: _____ (expected ≥ 1 from Phase 74.0 UAT-03)

**Optional backup** (strongly recommended — Row 2 may require a targeted DELETE):

```bash
cp ~/.local/share/musicstreamer/musicstreamer.sqlite3 \
   ~/.local/share/musicstreamer/musicstreamer.sqlite3.pre-phase74-07
```

---

## UAT Checklist

### Row 1 — UAT-07-RETEST (G-01 closure / SOMA-11)

- [ ] UAT-07-RETEST: re-import emits "SomaFM import: no changes" toast on second click

**Steps:**
1. Launch the app: `uv run python -m musicstreamer`
2. Confirm SomaFM rows exist in the library (see pre-test count above). If 0, click hamburger → "Import SomaFM" once first; wait for the "N stations added" success toast; then proceed.
3. Click hamburger menu → "Import SomaFM" a SECOND time.
4. Expected within ~5 s: toast appears with EXACTLY the text `SomaFM import: no changes`.

**Recorded toast text:** _____
**Pre-click SomaFM count:** _____

---

### Row 2 — UAT-F01-RETEST (G-02 closure / SOMA-02)

- [ ] UAT-F01-RETEST: Synphaera Radio's MP3-highest tier is stored with bitrate_kbps=256

**Important — dedup interaction:** If existing Synphaera rows have `bitrate_kbps=128` (from the original Phase 74.0 import that pre-dated the parser), those rows survive Plan 74-05's fix unchanged. D-05 dedup means a fresh re-import is a no-op on URL match — the parser only affects NEW imports. To re-verify against the live parser, delete the Synphaera rows then re-import.

**Cleanup (after pre-test backup):**
```bash
# Check current state first
sqlite3 ~/.local/share/musicstreamer/musicstreamer.sqlite3 \
  "SELECT s.name, ss.url, ss.bitrate_kbps FROM stations s
   JOIN station_streams ss ON ss.station_id=s.id
   WHERE s.name LIKE '%Synphaera%' AND ss.url LIKE '%-256-mp3%'"

# If bitrate_kbps=128 appears, delete and re-import:
sqlite3 ~/.local/share/musicstreamer/musicstreamer.sqlite3 \
  "DELETE FROM stations WHERE name LIKE '%Synphaera%'"
```

Then click hamburger → "Import SomaFM" in the app and wait for the success toast.

**Verification SQL:**
```bash
sqlite3 ~/.local/share/musicstreamer/musicstreamer.sqlite3 \
  "SELECT s.name, ss.url, ss.bitrate_kbps, ss.codec, ss.quality
   FROM stations s
   JOIN providers p ON s.provider_id=p.id
   JOIN station_streams ss ON ss.station_id=s.id
   WHERE p.name='SomaFM'
     AND s.name LIKE '%Synphaera%'
     AND ss.url LIKE '%-256-mp3%'"
```

**Expected:** at least one row where `bitrate_kbps = 256`.

**SQL output (paste verbatim):**
```
_____
```

---

### Row 3 — UAT-REGRESSION (no regression on previously-passing rows)

- [ ] UAT-REGRESSION: no regression in click-toast and playback

**Spot-checks:**
- **UAT-01 re-check:** When you clicked Import SomaFM in Row 1 or Row 2, did the `Importing SomaFM…` toast appear within ~1 s of the click? PASS / FAIL: _____
- **UAT-06 re-check:** Click any SomaFM station (Synphaera Radio or Groove Salad recommended); confirm audio plays within ~5 s with no error toast. PASS / FAIL: _____

---

## Sign-off

- [ ] All three rows pass → Phase 74 gap closure is COMPLETE. If any row fails, the failure routes back to a Phase 74.2 gap-closure cycle.

---

## Findings

_(Add any unexpected observations here — e.g. toast appears but text differs, bitrate parses to an unexpected value, regression in a previously-passing path.)_
