---
phase: 74
plan: "04"
status: pending-user
created: "2026-05-14"
---

# Phase 74 Plan 04: SomaFM Live UAT Log

Wave 2 (Plans 02 and 03) turned all 17 RED core tests plus the 2 drift-guard tests GREEN against mocked `urlopen`, confirming the full call chain from hamburger action through `_SomaImportWorker` to `soma_import.fetch_channels` + `import_stations` and into the SQLite repo. This plan verifies the same invariants against the LIVE `api.somafm.com:443` catalog and real audio playback — behaviors that the mocked CI suite cannot exercise. Any failures discovered here surface as Phase 74.1 gap-closure items, triaged by the user via `/gsd-plan-phase 74 --gaps`.

---

## Pre-test: Establish a baseline row count

Before running the import, confirm how many SomaFM station rows already exist in your library (if any). This is required to observe D-05 dedup (UAT-07).

**Option A — fresh dev DB (preferred):** Start the app with a clean/empty library so SomaFM stations definitely do not pre-exist.

**Option B — existing library:** Run the following query and record the output before proceeding:

```bash
sqlite3 ~/.local/share/musicstreamer/library.db \
  "SELECT count(*) FROM stations WHERE provider_name='SomaFM'"
```

Record the count here: ________ (expected: 0 if clean install)

**Optional backup** (recommended — protects your library from accidental pollution):

```bash
cp ~/.local/share/musicstreamer/library.db \
   ~/.local/share/musicstreamer/library.db.pre-phase74
```

---

## UAT Checklist

Walk the following rows in order. For each row, flip `[ ]` to `[x]` if it passes, or write `FAIL:` followed by what you observed.

---

- [ ] UAT-01 (D-06 click toast): Launch the app and click the hamburger menu → "Import SomaFM". Immediately — within 1 second of clicking — a toast appears with exactly the text `Importing SomaFM…`.

  _Notes:_

---

- [ ] UAT-02 (D-08 wall-clock): The import completes (the final success or error toast appears) within 5 seconds of the click. Record the observed elapsed time in seconds.

  _Elapsed time observed:_ ________ sec

---

- [ ] UAT-03 (D-06 success toast): The final toast text is `SomaFM import: N stations added` where N is at least 40 (the live catalog had 46 channels at research time on 2026-05-13; tolerate ±5 for catalog drift). Record the exact N shown.

  _N observed:_ ________

---

- [ ] UAT-04 (D-04 manual only): Close the app completely and reopen it. No SomaFM import fires automatically on startup — specifically, no `Importing SomaFM…` toast appears during launch.

  _Notes:_

---

- [ ] UAT-05 (D-11 logos render): Scroll the station tree to the SomaFM-imported rows. At least 3 of them show a non-placeholder station art image (a recognisable square channel logo, not a blank/grey square or a generic radio icon).

  _Notes (which stations showed logos):_

---

- [ ] UAT-06 (playback smoke): Click on a SomaFM station — for example "Groove Salad" if it was imported. Audio plays within 5 seconds and no error toast appears.

  _Station clicked:_
  _Notes:_

---

- [ ] UAT-07 (D-05 re-import idempotence): With the stations from UAT-03 still present in the library, click the hamburger menu → "Import SomaFM" a second time. The final toast text is exactly `SomaFM import: no changes` (inserted=0 because all stream URLs already match existing rows).

  _Toast text observed:_

---

- [ ] UAT-08 (D-13 cover_art_source default): Open EditStationDialog on any imported SomaFM station. If the dialog exposes a `cover_art_source` widget, confirm it shows `auto`. If the field is not visible in the dialog, run the sqlite3 query below and verify all rows show `auto`.

  ```bash
  sqlite3 ~/.local/share/musicstreamer/library.db \
    "SELECT cover_art_source FROM stations WHERE provider_name='SomaFM' LIMIT 5"
  ```

  _Query output (paste verbatim):_

---

- [ ] UAT-09 (D-02 provider name pin): Run the following query and verify SomaFM-imported rows show exactly `SomaFM` (CamelCase, no space, no period).

  ```bash
  sqlite3 ~/.local/share/musicstreamer/library.db \
    "SELECT DISTINCT provider_name FROM stations WHERE name LIKE '%Groove Salad%' OR name LIKE '%Drone Zone%'"
  ```

  _Query output (paste verbatim):_

---

- [ ] UAT-10 (D-03 stream count): Run the following query and verify each SomaFM station has exactly 20 stream rows (4 tiers × 5 ICE relays). If any station shows fewer than 20, record which station and its actual count for follow-up triage.

  ```bash
  sqlite3 ~/.local/share/musicstreamer/library.db \
    "SELECT s.name, count(ss.id) FROM stations s \
     JOIN station_streams ss ON ss.station_id=s.id \
     WHERE s.provider_name='SomaFM' \
     GROUP BY s.id ORDER BY count(ss.id) DESC LIMIT 5"
  ```

  _Query output (paste verbatim):_

---

## Findings

_Record any unexpected behavior, regressions, or items to defer to Phase 74.1 here. Empty if all rows pass._

---

## Sign-off

- [ ] All UAT rows pass OR all failures documented as Phase 74.1 gap-closure items.
