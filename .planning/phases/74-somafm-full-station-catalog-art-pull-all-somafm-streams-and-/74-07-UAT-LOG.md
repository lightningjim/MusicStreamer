---
phase: 74
plan: "07"
status: gap-closure-uat-passed
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

Recorded count: **46** (matches Phase 74.0 UAT-03 — full SomaFM catalog already imported)

Pre-fix Synphaera bitrate state (verifies G-02 was real):
```
Synphaera Radio | ice2.somafm.com/synphaera-256-mp3 | bitrate_kbps=128
Synphaera Radio | ice3.somafm.com/synphaera-256-mp3 | bitrate_kbps=128
Synphaera Radio | ice4.somafm.com/synphaera-256-mp3 | bitrate_kbps=128
Synphaera Radio | ice5.somafm.com/synphaera-256-mp3 | bitrate_kbps=128
Synphaera Radio | ice6.somafm.com/synphaera-256-mp3 | bitrate_kbps=128
```
URL slug says 256, DB says 128 — exactly the G-02 bug. Row 2 will DELETE these and re-import.

**Optional backup** (strongly recommended — Row 2 may require a targeted DELETE):

```bash
cp ~/.local/share/musicstreamer/musicstreamer.sqlite3 \
   ~/.local/share/musicstreamer/musicstreamer.sqlite3.pre-phase74-07
```

---

## UAT Checklist

### Row 1 — UAT-07-RETEST (G-01 closure / SOMA-11)

- [x] UAT-07-RETEST: re-import emits "SomaFM import: no changes" toast on second click — PASS

**Steps:**
1. Launch the app: `uv run python -m musicstreamer`
2. Confirm SomaFM rows exist in the library (see pre-test count above). If 0, click hamburger → "Import SomaFM" once first; wait for the "N stations added" success toast; then proceed.
3. Click hamburger menu → "Import SomaFM" a SECOND time.
4. Expected within ~5 s: toast appears with EXACTLY the text `SomaFM import: no changes`.

**Recorded toast text:** `SomaFM import: no changes` (verbatim match)
**Pre-click SomaFM count:** 46
**Observed duration:** ~20 s (slower than D-08's 5 s target; not a regression — see Findings)

---

### Row 2 — UAT-F01-RETEST (G-02 closure / SOMA-02)

- [x] UAT-F01-RETEST: Synphaera Radio's MP3-highest tier is stored with bitrate_kbps=256 — PASS

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

**Live toast on re-import:** `SomaFM import: 1 stations imported` (typo flagged — should be "1 station" singular; see Findings)

**SQL output (verbatim):**
```
name            | url                                          | bitrate_kbps | codec | quality
Synphaera Radio | https://ice4.somafm.com/synphaera-256-mp3    | 256          | MP3   | hi
Synphaera Radio | https://ice2.somafm.com/synphaera-256-mp3    | 256          | MP3   | hi
Synphaera Radio | https://ice6.somafm.com/synphaera-256-mp3    | 256          | MP3   | hi
Synphaera Radio | https://ice5.somafm.com/synphaera-256-mp3    | 256          | MP3   | hi
Synphaera Radio | https://ice3.somafm.com/synphaera-256-mp3    | 256          | MP3   | hi
```

All 5 `-256-mp3` rows store `bitrate_kbps=256` ✓ (vs pre-fix state where all 5 stored 128).

---

### Row 3 — UAT-REGRESSION (no regression on previously-passing rows)

- [x] UAT-REGRESSION: no regression in click-toast and playback — PASS

**Spot-checks:**
- **UAT-01 re-check:** When you clicked Import SomaFM in Row 1 or Row 2, did the `Importing SomaFM…` toast appear within ~1 s of the click? **PASS** (user confirmed in Row 1)
- **UAT-06 re-check:** Click any SomaFM station (Synphaera Radio or Groove Salad recommended); confirm audio plays within ~5 s with no error toast. **PASS** (Synphaera Radio played)

---

## Sign-off

- [x] All three rows pass → Phase 74 gap closure is COMPLETE.

---

## Findings

Three observations surfaced during the gap-closure UAT. None block Phase 74 closure; each is a candidate follow-up.

**F-07-01: Re-import wall-clock is ~20 s (vs D-08's 5 s target).** When SomaFM stations already exist, the user observed ~20 s between click and the "no changes" toast. Root cause: `fetch_channels` still does the full `channels.json` fetch + 184 sequential PLS GETs (4 tiers × 46 channels) before `import_stations` can short-circuit on dedup. The dedup check happens AFTER PLS resolution. Possible fix: short-circuit at the channel level by checking the channel's `image_url` or a stable channel identifier before running `_resolve_pls`. Out of scope for Phase 74; candidate for a follow-up perf phase.

**F-07-02: Toast typo — "1 stations imported" should be "1 station imported".** When a single station is imported (e.g. Synphaera re-import in Row 2), the toast incorrectly pluralises "stations". Should pluralise conditionally based on count. One-line fix in `main_window.py::_on_soma_import_done`. Candidate for a tiny follow-up.

**F-07-03: SQLite foreign-key enforcement disabled at runtime.** `PRAGMA foreign_keys` returns `0` in interactive sessions against `musicstreamer.sqlite3`, even though the `station_streams` schema declares `FOREIGN KEY(station_id) REFERENCES stations(id) ON DELETE CASCADE`. SQLite requires `PRAGMA foreign_keys = ON` per connection; without it, the CASCADE is silently a no-op. Manifested during this UAT: deleting the Synphaera station row left 20 orphaned stream rows that defeated dedup. Real bug — every `DELETE FROM stations` in the app currently leaks streams. Candidate for a separate BUG-NN entry against the app's DB connection setup (likely `db_connect()` in `musicstreamer/db.py` or `repo.py`).
