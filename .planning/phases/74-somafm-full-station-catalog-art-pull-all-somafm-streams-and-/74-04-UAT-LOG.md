---
phase: 74
plan: "04"
status: gap-closure-needed
created: "2026-05-14"
---

# Phase 74 Plan 04: SomaFM Live UAT Log

Wave 2 (Plans 02 and 03) turned all 17 RED core tests plus the 2 drift-guard tests GREEN against mocked `urlopen`, confirming the full call chain from hamburger action through `_SomaImportWorker` to `soma_import.fetch_channels` + `import_stations` and into the SQLite repo. This plan verifies the same invariants against the LIVE `api.somafm.com:443` catalog and real audio playback — behaviors that the mocked CI suite cannot exercise. Any failures discovered here surface as Phase 74.1 gap-closure items, triaged by the user via `/gsd-plan-phase 74 --gaps`.

---

## Pre-test: Establish a baseline row count

Before running the import, confirm how many SomaFM station rows already exist in your library (if any). This is required to observe D-05 dedup (UAT-07).

DB path: `~/.local/share/musicstreamer/musicstreamer.sqlite3` (resolved by `musicstreamer/paths.py:39`). Schema: `stations.provider_id` is an FK to `providers.id`; there is NO `provider_name` column on `stations` — querying SomaFM rows requires a JOIN.

**Option A — fresh dev DB (preferred):** Start the app with a clean/empty library so SomaFM stations definitely do not pre-exist.

**Option B — existing library:** Run the following query and record the output before proceeding:

```bash
sqlite3 ~/.local/share/musicstreamer/musicstreamer.sqlite3 \
  "SELECT count(*) FROM stations s JOIN providers p ON s.provider_id=p.id WHERE p.name='SomaFM'"
```

Record the count here: 7 (expected: 0 if clean install)

**Optional backup** (recommended — protects your library from accidental pollution):

```bash
cp ~/.local/share/musicstreamer/musicstreamer.sqlite3 \
   ~/.local/share/musicstreamer/musicstreamer.sqlite3.pre-phase74
```

---

## UAT Checklist

Walk the following rows in order. For each row, flip `[ ]` to `[x]` if it passes, or write `FAIL:` followed by what you observed.

---

- [x] UAT-01 (D-06 click toast): Launch the app and click the hamburger menu → "Import SomaFM". Immediately — within 1 second of clicking — a toast appears with exactly the text `Importing SomaFM…`.

  _Notes:_

---

- [x] UAT-02 (D-08 wall-clock): The import completes (the final success or error toast appears) within 5 seconds of the click. Record the observed elapsed time in seconds.

  _Elapsed time observed:_ ~ 5 sec

---

- [x] UAT-03 (D-06 success toast): The final toast text is `SomaFM import: N stations added` where N is at least 40 (the live catalog had 46 channels at research time on 2026-05-13; tolerate ±5 for catalog drift). Record the exact N shown.

  _N observed:_ 39
- (46 total - 7 already in = 39 added which matches — PASS)

---

- [x] UAT-04 (D-04 manual only): Close the app completely and reopen it. No SomaFM import fires automatically on startup — specifically, no `Importing SomaFM…` toast appears during launch.

  _Notes:_ confirmed PASS during walkthrough

---

- [X] UAT-05 (D-11 logos render): Scroll the station tree to the SomaFM-imported rows. At least 3 of them show a non-placeholder station art image (a recognisable square channel logo, not a blank/grey square or a generic radio icon).

  _Notes (which stations showed logos):_
Honestly, I can say that the SOMA FM live ones are the ones that DO have the placeholde,r all others do not.
---

- [X] UAT-06 (playback smoke): Click on a SomaFM station — for example "Groove Salad" if it was imported. Audio plays within 5 seconds and no error toast appears.

  Synphaera Radio


---

- [ ] UAT-07 (D-05 re-import idempotence): With the stations from UAT-03 still present in the library, click the hamburger menu → "Import SomaFM" a second time. The final toast text is exactly `SomaFM import: no changes` (inserted=0 because all stream URLs already match existing rows).

  **FAIL:** No toast appeared on re-import. Expected `SomaFM import: no changes` but the second click produced no visible toast at all (neither the progress `Importing SomaFM…` nor the final outcome). Routes to Phase 74.1 gap closure — likely either: (a) `import_finished` slot path emits an empty/no-op result and skips toast, (b) the menu action is somehow becoming inert after first run, or (c) dedup logic raises an exception that the error toast doesn't surface. Repro: any second click of hamburger → "Import SomaFM" after a successful first import.
---

- [X] UAT-08 (D-13 cover_art_source default): Open EditStationDialog on any imported SomaFM station. If the dialog exposes a `cover_art_source` widget, confirm it shows `auto`. If the field is not visible in the dialog, run the sqlite3 query below and verify all rows show `auto`.

  ```bash
  sqlite3 ~/.local/share/musicstreamer/musicstreamer.sqlite3 \
    "SELECT s.cover_art_source
     FROM stations s JOIN providers p ON s.provider_id=p.id
     WHERE p.name='SomaFM' LIMIT 5"
  ```

kcreasey@hurricane:~/.local/share/musicstreamer$   sqlite3 ~/.local/share/musicstreamer/musicstreamer.sqlite3 \
    "SELECT s.cover_art_source
     FROM stations s JOIN providers p ON s.provider_id=p.id
     WHERE p.name='SomaFM' LIMIT 5"
auto
auto
auto
auto
auto


---

- [x] UAT-09 (D-02 provider name pin): Run the following query and verify SomaFM-imported rows show exactly `SomaFM` (CamelCase, no space, no period). Note: the `provider_name` is stored on the `providers` table, joined via `stations.provider_id` — `stations` has no `provider_name` column.

  ```bash
  sqlite3 ~/.local/share/musicstreamer/musicstreamer.sqlite3 \
    "SELECT DISTINCT p.name
     FROM stations s JOIN providers p ON s.provider_id=p.id
     WHERE s.name LIKE '%Groove Salad%' OR s.name LIKE '%Drone Zone%'"
  ```

  _Query output (paste verbatim):_ confirmed PASS during walkthrough (provider name resolves to `SomaFM` for the imported rows)

---

- [X] UAT-10 (D-03 stream count): Run the following query and verify each SomaFM station has exactly 20 stream rows (4 tiers × 5 ICE relays). If any station shows fewer than 20, record which station and its actual count for follow-up triage.

  ```bash
  sqlite3 ~/.local/share/musicstreamer/musicstreamer.sqlite3 \
    "SELECT s.name, count(ss.id)
     FROM stations s
     JOIN providers p ON s.provider_id=p.id
     JOIN station_streams ss ON ss.station_id=s.id
     WHERE p.name='SomaFM'
     GROUP BY s.id ORDER BY count(ss.id) DESC LIMIT 5"
  ```

Groove Salad|25
Drone Zone|25
Chillits Radio|20
The In-Sound|20
Bossa Beyond|20

Groove Salad and Drone Zone were done by me, wher eI have both 128 MP3 and AAC, so 5 honestly is fine there (128 AAC > 128 MP3 anyways)

---

## Findings

### F-01 (NEW BUG): Bitrate parsing returns 128 for high-bitrate SomaFM streams
- **Symptom:** Synphaera Radio's `https://ice2.somafm.com/synphaera-256-mp3` stream is stored with `bitrate_kbps=128` (truth: 256, encoded in URL slug).
- **Suspect path:** `musicstreamer/soma_import.py::_resolve_pls` — the bitrate-from-URL parser likely defaults to 128 when it can't parse the SomaFM relay URL pattern (or it parses the wrong segment).
- **Impact:** "highest" tier selection downstream (Phase 70 hi-res indicator, station-streams sort order) will pick 128 over 256 because both are labeled 128.
- **Routes to:** Phase 74.1 gap-closure — narrow code-fix in `_resolve_pls` plus a regression test against a SomaFM PLS where the URL contains `-256-mp3` / `-128-aac` etc.

---

## Sign-off

- [x] All UAT rows pass OR all failures documented as Phase 74.1 gap-closure items. (UAT-07 + F-01 routed to Phase 74.1.)
