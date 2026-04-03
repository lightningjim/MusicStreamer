# Roadmap: MusicStreamer

## Milestones

- ✅ **v1.0 MVP** — Phases 1–4 (shipped 2026-03-20)
- ✅ **v1.1 Polish & Station Management** — Phases 5–6 (shipped 2026-03-21)
- ✅ **v1.2 Station UX & Polish** — Phases 7–11 (shipped 2026-03-25)
- ✅ **v1.3 Discovery & Favorites** — Phases 12–15 (shipped 2026-04-03)
- 🚧 **v1.4 Media & Art Polish** — Phases 16–19 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1–4) — SHIPPED 2026-03-20</summary>

- [x] Phase 1: Module Extraction (3/3 plans) — completed 2026-03-18
- [x] Phase 2: Search and Filter (2/2 plans) — completed 2026-03-19
- [x] Phase 3: ICY Metadata Display (2/2 plans) — completed 2026-03-20
- [x] Phase 4: Cover Art (1/1 plan) — completed 2026-03-20

Full details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

<details>
<summary>✅ v1.1 Polish & Station Management (Phases 5–6) — SHIPPED 2026-03-21</summary>

- [x] Phase 5: Display Polish (2/2 plans) — completed 2026-03-21
- [x] Phase 6: Station Management (2/2 plans) — completed 2026-03-21

Full details: `.planning/milestones/v1.1-ROADMAP.md`

</details>

<details>
<summary>✅ v1.2 Station UX & Polish (Phases 7–11) — SHIPPED 2026-03-25</summary>

- [x] Phase 7: Station List Restructuring (3/3 plans) — completed 2026-03-22
- [x] Phase 8: Filter Bar Multi-Select (2/2 plans) — completed 2026-03-22
- [x] Phase 9: Station Editor Improvements (2/2 plans) — completed 2026-03-23
- [x] Phase 10: Now Playing & Audio (2/2 plans) — completed 2026-03-24
- [x] Phase 11: UI Polish (1/1 plan) — completed 2026-03-25

Full details: `.planning/milestones/v1.2-ROADMAP.md`

</details>

<details>
<summary>✅ v1.3 Discovery & Favorites (Phases 12–15) — SHIPPED 2026-04-03</summary>

- [x] Phase 12: Favorites (2/2 plans) — completed 2026-03-31
- [x] Phase 13: Radio-Browser Discovery (2/2 plans) — completed 2026-04-01
- [x] Phase 14: YouTube Playlist Import (2/2 plans) — completed 2026-04-02
- [x] Phase 15: AudioAddict Import (2/2 plans) — completed 2026-04-03

Full details: `.planning/milestones/v1.3-ROADMAP.md`

</details>

### 🚧 v1.4 Media & Art Polish (In Progress)

**Milestone Goal:** Improve stream reliability, station art quality, display fidelity, and add basic UI personalization.

- [x] **Phase 16: GStreamer Buffer Tuning** — Tune playbin3 buffer properties to eliminate ShoutCast/HTTP drop-outs (completed 2026-04-03)
- [x] **Phase 17: AudioAddict Station Art** — Fetch AA channel logos at import time and auto-fetch in the station editor (completed 2026-04-03)
- [ ] **Phase 18: YouTube Thumbnail 16:9** — Display full 16:9 YouTube thumbnails in now-playing without distorting square art
- [ ] **Phase 19: Custom Accent Color** — Add preset/hex accent color picker persisted in SQLite settings

## Phase Details

### Phase 16: GStreamer Buffer Tuning
**Goal**: ShoutCast and HTTP streams play without audible drop-outs
**Depends on**: Phase 15
**Requirements**: STREAM-01
**Success Criteria** (what must be TRUE):
  1. A ShoutCast stream plays for 5+ minutes without audible drop-outs that were previously reproducible
  2. ICY track title appears within the same time window as before tuning (no noticeable extra delay)
  3. YouTube streams (mpv path) are unaffected — they continue to play correctly
**Plans**: 1 plan

Plans:
- [x] 16-01: Set buffer-duration and buffer-size on playbin3 pipeline; validate ICY TAG latency

### Phase 17: AudioAddict Station Art
**Goal**: AudioAddict stations display channel logos fetched from the AA API
**Depends on**: Phase 16
**Requirements**: ART-01, ART-02
**Success Criteria** (what must be TRUE):
  1. After bulk AA import, imported stations show channel logo art (not placeholder) where the AA API returned an image
  2. Import completes in the same approximate time as before — logo download does not block or visibly slow the import dialog
  3. Pasting an AudioAddict stream URL in the station editor auto-populates the art field with the channel logo (same UX as YouTube thumbnail fetch)
  4. Import and editor art fetch fail silently — no error dialog when an image is unavailable or the API returns an unexpected structure
**Plans**: 2 plans
**UI hint**: yes

Plans:
- [x] 17-01: AA art fetch backend — live API field inspection, fetch logic in aa_import.py, async image download, tests
- [x] 17-02: Editor auto-fetch UI — _on_url_focus_out wiring in edit_dialog.py for AA URLs, same UX as YT thumbnail

### Phase 18: YouTube Thumbnail 16:9
**Goal**: YouTube thumbnails display as full 16:9 in now-playing without cropping or distorting other art
**Depends on**: Phase 17
**Requirements**: ART-03
**Success Criteria** (what must be TRUE):
  1. A YouTube station's now-playing art slot shows the full 16:9 thumbnail — no center-crop, full width visible
  2. A non-YouTube station's now-playing art slot shows its square art without distortion or letterboxing
  3. iTunes cover art continues to display correctly for stations with active ICY track titles
**Plans**: 1 plan
**UI hint**: yes

Plans:
- [ ] 18-01: GdkPixbuf scale args + ContentFit.CONTAIN in main_window.py; validate both station types visually

### Phase 19: Custom Accent Color
**Goal**: Users can set and persist a custom highlight color for the app UI
**Depends on**: Phase 18
**Requirements**: ACCENT-01
**Success Criteria** (what must be TRUE):
  1. User can open an accent color picker from the header bar and select from preset swatches
  2. User can enter a hex value and have it applied as the accent color
  3. Chosen color takes effect immediately — no restart required
  4. Accent color is restored automatically on next app launch
  5. An invalid hex value is rejected without crashing — the previous color is preserved
**Plans**: 2 plans
**UI hint**: yes

Plans:
- [ ] 19-01: CSS provider backend — CssProvider injection, hex validation, settings persistence, tests
- [ ] 19-02: Accent dialog UI — preset swatches + hex input in accent_dialog.py, header bar trigger in main_window.py

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Module Extraction | v1.0 | 3/3 | Complete | 2026-03-18 |
| 2. Search and Filter | v1.0 | 2/2 | Complete | 2026-03-19 |
| 3. ICY Metadata Display | v1.0 | 2/2 | Complete | 2026-03-20 |
| 4. Cover Art | v1.0 | 1/1 | Complete | 2026-03-20 |
| 5. Display Polish | v1.1 | 2/2 | Complete | 2026-03-21 |
| 6. Station Management | v1.1 | 2/2 | Complete | 2026-03-21 |
| 7. Station List Restructuring | v1.2 | 3/3 | Complete | 2026-03-22 |
| 8. Filter Bar Multi-Select | v1.2 | 2/2 | Complete | 2026-03-22 |
| 9. Station Editor Improvements | v1.2 | 2/2 | Complete | 2026-03-23 |
| 10. Now Playing & Audio | v1.2 | 2/2 | Complete | 2026-03-24 |
| 11. UI Polish | v1.2 | 2/2 | Complete | 2026-03-27 |
| 12. Favorites | v1.3 | 2/2 | Complete | 2026-03-31 |
| 13. Radio-Browser Discovery | v1.3 | 2/2 | Complete | 2026-04-01 |
| 14. YouTube Playlist Import | v1.3 | 2/2 | Complete | 2026-04-02 |
| 15. AudioAddict Import | v1.3 | 2/2 | Complete | 2026-04-03 |
| 16. GStreamer Buffer Tuning | v1.4 | 1/1 | Complete   | 2026-04-03 |
| 17. AudioAddict Station Art | v1.4 | 2/2 | Complete    | 2026-04-03 |
| 18. YouTube Thumbnail 16:9 | v1.4 | 0/1 | Not started | - |
| 19. Custom Accent Color | v1.4 | 0/2 | Not started | - |
