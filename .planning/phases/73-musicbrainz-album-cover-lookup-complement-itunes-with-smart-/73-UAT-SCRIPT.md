---
phase: 73
plan: 05
task: 1
type: manual-uat
deployment: linux-wayland-gnome-shell-dpr1.0
created: 2026-05-13
status: PENDING
---

# Phase 73 — Manual UAT Script

> Three manual verifications mapped to `73-VALIDATION.md §Manual-Only Verifications`.
> Each scenario covers behavior that the 16 automated ART-MB-NN tests cannot reach:
> live MusicBrainz network correctness, subjective image quality at the 160×160 cover
> slot, and full cross-profile ZIP transport of the new `cover_art_source` field.
>
> **Deployment target:** Linux Wayland (GNOME Shell) at DPR=1.0. The app targets
> Wayland exclusively (project memory: `project_deployment_target.md`). Confirm
> `$XDG_SESSION_TYPE == wayland` before starting.
>
> **What is already proven (do NOT re-test here):**
> All 16 ART-MB-NN behaviors are GREEN against mocked MB + CAA responses
> (User-Agent literal, 1 req/sec gate, ≥80 score threshold, release ladder,
> latest-wins queue, 503 fallthrough, MB-only / iTunes-only mode lockouts,
> Auto-mode fall-through, schema migration, settings_export round-trip,
> EditStationDialog selector save path, MB tags → genre highest-count,
> source-grep gates for User-Agent literal + `time.monotonic` gate).
> This UAT only covers the three live-system pieces those mocks cannot.

---

## How to run

1. From a Wayland session (GNOME Shell on Linux), open a terminal.
2. Confirm session type:
   ```bash
   echo "$XDG_SESSION_TYPE"   # must print: wayland
   ```
3. Confirm internet access (the UAT hits MusicBrainz live):
   ```bash
   curl -sI -A "MusicStreamerUAT/0 (https://github.com/lightningjim/MusicStreamer)" \
     "https://musicbrainz.org/ws/2/recording/?query=artist%3A%22Daft+Punk%22+AND+recording%3A%22One+More+Time%22&fmt=json&limit=1" \
     | head -n 1
   # Expect: HTTP/2 200
   ```
4. Launch the app from the project root. Either form works:
   ```bash
   python -m musicstreamer
   # or, if the project is installed via `pip install -e .`:
   musicstreamer
   ```
5. The MusicStreamer main window appears with the station list visible on the
   left and the now-playing pane on the right. The new per-station "Cover art
   source:" QComboBox lives inside `EditStationDialog`, immediately below the
   "ICY metadata:" row.
6. Work through Scenario A → Scenario B → Scenario C in order. Tick the
   `[ ]` checkbox next to each Pass criteria as you confirm it. Leave notes in
   the "Notes / observations" block under each scenario for anything that
   feels off.
7. At the very bottom of this file, change `**Overall:** PENDING` to
   `**Overall:** PASS` (all three scenarios passed), `**Overall:** PASS WITH CAVEATS`
   (passed with non-blocking observations), or `**Overall:** FAIL`
   (one or more scenarios failed — record which in "Failure notes" so a Phase
   73.1 gap-closure plan can be scoped).

The orchestrator's checkpoint gate greps for the literal text
`**Overall:** PASS` (with or without ` WITH CAVEATS`) at the bottom of this
file. Leaving it as PENDING keeps the gate closed; setting it to PASS releases
the phase to its summary step.

**Time estimate:** Scenario A ~5 min · Scenario B ~3 min · Scenario C ~10 min
· Total ~20 min wall-clock.

---

## Scenario A — Real MB cover renders for a real station

**Maps to:** VALIDATION.md §Manual-Only Verifications row 1
**Why manual:** Live MusicBrainz network — cannot deterministically assert
against MB content from a unit test.
**Requirement covered:** E2E sanity for the full Plan 02 + Plan 03 + Plan 04 pipeline.

### Pre-conditions

- App builds and runs (Wayland, DPR=1.0).
- Internet access available; `musicbrainz.org` and `coverartarchive.org` reachable.
- At least one favorite station exists with ICY metadata enabled and known to
  emit `Artist - Title` ICY strings. Recommended:
  - **SomaFM Indie Pop Rocks** — consistent `Artist - Title` ICY,
    iTunes-friendly catalogue.
  - or **DI.fm Vocal Trance** — consistent `Artist - Title` ICY.
  - or any station you've previously seen the iTunes cover work on.

### Steps

1. Launch the app per "How to run" above.
2. Click the chosen station; play it. Observe an ICY title arrives within
   ~10 seconds (visible in the now-playing pane's track-title label as
   `Artist - Title`).
3. Verify the **Auto-mode baseline first**: with `cover_art_source = 'auto'`
   (the default for every existing station per D-05), confirm that the
   cover_label in the now-playing pane renders a real album cover (this is
   the existing iTunes-Auto path; it should already work). If the iTunes
   path itself is broken, STOP — that is a Phase 70 regression, not a
   Phase 73 UAT failure.
4. Right-click the station (or use whatever the existing per-station edit
   affordance is — the "..." menu, the context menu, etc.) → **Edit Station**
   → `EditStationDialog` opens.
5. Verify the new selector exists with the exact shape:
   - Label text: `Cover art source:` (immediately below the `ICY metadata:` row).
   - Widget type: QComboBox, **non-editable** (you cannot type free text).
   - Three entries in this order:
     - `Auto (iTunes → MusicBrainz fallback)`
     - `iTunes only`
     - `MusicBrainz only`
   - Currently selected: `Auto (iTunes → MusicBrainz fallback)`.
6. Select `MusicBrainz only`. The Save button should become enabled (the dirty
   detector picked up the flip per Plan 04 D-04 snapshot key).
7. Click **Save**. The dialog closes.
8. Stop playback (transport stop button) and re-play the same station.
9. Wait for a fresh ICY title to arrive (the cover fetch fires on
   `on_title_changed`, not on start-playback; you must see a new
   `Artist - Title` reach the panel).
10. Observe the cover_label slot for **up to 30 seconds** after the new ICY
    arrives (MB calls are gated to 1 req/sec, and CAA-250 is a small image,
    so the round-trip should complete in 2–5 seconds; the 30s ceiling
    accommodates network jitter).
11. Try **2 to 3 tracks** before declaring FAIL — some tracks legitimately
    have no MB match (score < 80 → miss, per D-09) and that is correct
    behavior, not a UAT failure.

### Expected

- An album cover image renders in the cover_label slot for at least one of the
  3 tested tracks. The cover may DIFFER from the iTunes cover that Auto-mode
  showed in step 3 — that is correct (iTunes and MB pick different albums
  for the same recording).
- The cover is not the station-logo placeholder (that means MB fell through;
  either the track has no ≥80-score MB match or the chosen release has no
  CAA art).
- No application crash, no Python exception in the terminal, no `urlopen`
  traceback escaping the worker. MB worker MUST swallow all exceptions per
  Plan 02 D-20.

### Pass criteria

- [ ] **PASS** — At least one of 3 tested tracks renders a real album cover
      after the station is set to `MusicBrainz only`. No crash. No stuck
      placeholder for >30s on a track with an `Artist - Title` ICY shape.

### Fail criteria

- ❌ **FAIL** — All 3 tested tracks stay on the station-logo placeholder for
      >30s after a `' - '`-shaped ICY title arrives, OR the worker raises an
      exception out to the Qt main thread, OR the app crashes.

### Notes / observations

(leave blank — fill in during the run)

---

## Scenario B — CAA-250 image quality at 160×160

**Maps to:** VALIDATION.md §Manual-Only Verifications row 2
**Why manual:** Visual quality assessment is subjective; cannot be automated.
**Requirement covered:** RESEARCH A1 (assumption that CAA's `/front-250`
endpoint produces a clean 250×250 source that scales to 160×160 without
visible pixelation).

### Pre-conditions

- Scenario A completed (you have at least one station set to `MusicBrainz only`
  with a known-rendering track).
- Wayland session at DPR=1.0 — pixel-for-pixel rendering, no fractional
  scaling.

### Steps

1. With the same station set to `MusicBrainz only` from Scenario A, replay
   until the MB cover renders in the cover_label slot (the slot is 160×160
   per `now_playing_panel.py`).
2. Inspect the cover at native pixel ratio (no zoom; no screen magnifier).
   Look specifically for:
   - Visible pixelation along album-art edges (worst on text + logos).
   - JPEG compression artifacts (blocky 8×8 mosquito noise).
   - Blurring from the QPixmap scale-down from 250×250 → 160×160.
3. For comparison, **temporarily flip the same station back to `iTunes only`**
   via EditStationDialog → Save → replay → wait for cover to render. The
   iTunes worker fetches a 160×160 image directly (no scale-down); that is
   your baseline for "clean at 160×160".
4. Flip the station back to `MusicBrainz only` and replay. Compare the MB
   cover side-by-side (mentally — the slot only holds one at a time) against
   the iTunes baseline from step 3.

### Expected

- The CAA-250 image, scaled to 160×160, is **comparable in visual quality**
  to the iTunes 160×160 baseline. Minor differences in art selection are
  expected (different release picked); minor differences in colour grading
  are expected (CDN encoding differs). Visible pixelation or blur that the
  iTunes baseline does not show would indicate the CAA-250 variant is too
  small for this slot.
- No artifacts that make album text unreadable at native size.

### Pass criteria

- [ ] **PASS** — MB cover (CAA-250 scaled to 160×160) shows no visible
      pixelation or blur compared to the iTunes 160×160 baseline. Album
      text and band logos are readable. Visual quality is acceptable for
      production shipping.

### Fail criteria

- ❌ **FAIL (PIXELATED)** — MB cover is visibly pixelated, blurry, or shows
      compression artifacts the iTunes baseline does not. Album text or band
      logos become unreadable.

**If FAIL:** Recommend in "Notes" below that Phase 73.1 (gap-closure) bumps
the CAA variant from `/front-250` to `/front-500` in
`musicstreamer/cover_art_mb.py` (single-line change per CONTEXT D-11). Do NOT
auto-fix in this UAT — the verdict goes to the user and the planner picks the
next variant if needed.

### Notes / observations

(leave blank — fill in during the run; note specific artifacts seen if any)

---

## Scenario C — Cross-profile ZIP round-trip preserves `cover_art_source`

**Maps to:** VALIDATION.md §Manual-Only Verifications row 3
**Why manual:** Requires two profiles (or two machines) — the automated
ART-MB-10 test covers the in-process round-trip via mocked DB but cannot
verify the filesystem-level export-then-import handoff.
**Requirement covered:** ART-MB-10 end-to-end (the cross-machine half).

### Pre-conditions

- Scenarios A and B completed.
- A second profile is available. Easiest on Linux: a fresh
  `XDG_DATA_HOME=/tmp/phase73-uat-profile` directory. Alternative: a second
  OS user account.
- Active profile has at least 3 favorite stations.

### Steps

1. On the **active profile**: open `EditStationDialog` on three distinct
   stations and set each to a different value:
   - Station 1: `Auto (iTunes → MusicBrainz fallback)` (the default — confirm
     it stays).
   - Station 2: `iTunes only`.
   - Station 3: `MusicBrainz only`.
   - Click Save on each.
2. Open the hamburger menu → **Settings** → **Export** (whichever label the
   existing affordance uses — `settings_export.build_zip` is the codepath;
   Plan 04 D-04 confirms the export side now emits `cover_art_source`).
3. Save the resulting ZIP to a known location, e.g. `~/phase73-uat-export.zip`.
4. (Optional sanity check before importing) Unzip and grep the JSON payload
   for the new field — this confirms Plan 04's export-side write
   independently of the import-side read:
   ```bash
   unzip -p ~/phase73-uat-export.zip stations.json \
     | python -c "import json, sys; d=json.load(sys.stdin); print([s.get('cover_art_source') for s in d[:5]])"
   # Expect: ['auto', 'auto', ..., 'mb_only', 'itunes_only'] — values present, not all 'None'.
   ```
5. Quit the running app.
6. Launch the app under a **fresh profile**:
   ```bash
   XDG_DATA_HOME=/tmp/phase73-uat-profile python -m musicstreamer
   ```
   The app should open with no favorites (clean slate).
7. In the fresh profile, hamburger menu → **Settings** → **Import** →
   select `~/phase73-uat-export.zip`. Choose whichever import mode the
   dialog defaults to (INSERT for a clean profile; REPLACE if a prompt
   appears). Both paths are covered by Plan 04 (ART-MB-10 import-side
   tests).
8. After import completes, the three test stations should appear in the
   station list.
9. Open `EditStationDialog` on each in turn and verify the
   `Cover art source:` combo reflects the value from the source profile:
   - Station 1 → `Auto (iTunes → MusicBrainz fallback)`.
   - Station 2 → `iTunes only`.
   - Station 3 → `MusicBrainz only`.

### Expected

- All 3 stations' `cover_art_source` values transit the ZIP correctly.
- No station's combo shows a different value, an empty value, or the dialog
  fails to open due to a missing-attribute error (which would mean the
  import did not write the column at all — different from Pitfall 9
  forward-compat which says a *missing key* defaults to `'auto'`; here the
  key IS present, so the value must be preserved).

### Pass criteria

- [ ] **PASS** — All three stations show the expected `cover_art_source`
      values in the fresh profile after import: Station 1 = Auto, Station 2
      = iTunes only, Station 3 = MusicBrainz only.

### Fail criteria

- ❌ **FAIL (FIELD RESET)** — Any station's combo shows `Auto` when the
      source profile had it set to `iTunes only` or `MusicBrainz only`
      (or vice versa). This means the round-trip lost the value.
- ❌ **FAIL (FIELD MISSING)** — The dialog crashes or shows the combo
      missing entirely for an imported station — means the import path
      did not write the column at all.

### Notes / observations

(leave blank — fill in during the run; include any export/import dialog
quirks observed)

---

## Optional bonus checks

These are not required for Pass; they exercise subtle paths that the 16
automated tests cover but a live session is the most natural way to confirm
end-to-end:

- **Lucene-special-char ICY:** If during Scenario A you encounter an ICY
  title containing `:` `"` `(` `)` `\\` `+` `-` `&&` `||` etc. (e.g. a track
  title like `Pink Floyd - Money (2011 Remaster)`), confirm the app does
  not crash and the cover slot either renders or stays on the placeholder
  cleanly. This exercises T-73-01 (Lucene injection mitigation) in practice.
- **Rapid ICY churn:** Leave the app running for ~3–5 minutes on a
  fast-rotating channel (e.g. a DJ-mix stream with `Artist - Title` changes
  every 20–30 seconds). Confirm no visible "request flood" symptoms —
  the cover slot updates smoothly, no terminal warnings about HTTP 503 or
  429 from MusicBrainz. This is the runtime confirmation of the 1-req/sec
  gate (ART-MB-03 covers the unit-level proof).

---

## Failure notes

(leave blank — fill in if any scenario failed; orchestrator reads this to
scope `/gsd-plan-phase 73 --gaps`)

---

## Overall

**Overall:** PENDING
