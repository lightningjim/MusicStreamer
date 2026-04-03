# Roadmap: MusicStreamer

## Milestones

- ✅ **v1.0 MVP** — Phases 1–4 (shipped 2026-03-20)
- ✅ **v1.1 Polish & Station Management** — Phases 5–6 (shipped 2026-03-21)
- ✅ **v1.2 Station UX & Polish** — Phases 7–11 (shipped 2026-03-25)
- 🚧 **v1.3 Discovery & Favorites** — Phases 12–15 (in progress)

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

### 🚧 v1.3 Discovery & Favorites (In Progress)

**Milestone Goal:** Add station discovery and a favorites system — users can star ICY track titles, browse Radio-Browser.info, and bulk-import AudioAddict and YouTube stations.

- [x] **Phase 12: Favorites** (2/2 plans) — completed 2026-03-31
- [x] **Phase 13: Radio-Browser Discovery** — Browse, preview, and save Radio-Browser.info stations in-app (completed 2026-04-01)
- [x] **Phase 14: YouTube Playlist Import** — Paste a public playlist URL to import live streams as stations (completed 2026-04-02)
- [ ] **Phase 15: AudioAddict Import** — Import all AudioAddict network channels via API key with quality selection

## Phase Details

### Phase 12: Favorites
**Goal**: Users can star ICY track titles and revisit them in a dedicated view
**Depends on**: Phase 11
**Requirements**: FAVES-01, FAVES-02, FAVES-03, FAVES-04
**Success Criteria** (what must be TRUE):
  1. User can tap a star button in the now-playing panel to save the current ICY track title; button is disabled when the title is absent or junk
  2. Favorited track appears in the Favorites view with station name, provider, and track title
  3. User can toggle between the Stations list and the Favorites list via a control in the sidebar without leaving the main window
  4. User can remove a track from the Favorites view and it disappears immediately
  5. Favorites survive app restart (stored in SQLite with UNIQUE constraint preventing duplicates)
**Plans:** 1/2 plans executed
Plans:
- [x] 12-01-PLAN.md — Favorite dataclass, DB schema, repo CRUD methods, iTunes genre parser, unit tests
- [ ] 12-02-PLAN.md — Star button, Adw.ToggleGroup view toggle, favorites list with trash removal, CSS
**UI hint**: yes

### Phase 13: Radio-Browser Discovery
**Goal**: Users can browse Radio-Browser.info stations, preview them, and save any to their library
**Depends on**: Phase 12
**Requirements**: DISC-01, DISC-02, DISC-03, DISC-04
**Success Criteria** (what must be TRUE):
  1. User can open a discovery dialog and search Radio-Browser.info stations by name or provider
  2. User can narrow results by tag (genre) or country from within the dialog
  3. User can play a Radio-Browser.info station as a live preview without it being added to the library
  4. User can save a Radio-Browser.info station to their library and it appears in the station list
**Plans:** 2/2 plans complete
Plans:
- [x] 13-01-PLAN.md — Radio-Browser API client, repo URL-check + insert methods, unit tests
- [x] 13-02-PLAN.md — DiscoveryDialog UI (search, filters, preview, save), main window wiring
**UI hint**: yes

### Phase 14: YouTube Playlist Import
**Goal**: Users can import live streams from a public YouTube playlist as stations in one action
**Depends on**: Phase 13
**Requirements**: IMPORT-01
**Success Criteria** (what must be TRUE):
  1. User can paste a public YouTube playlist URL into an import dialog and trigger import
  2. Import shows a spinner and a running count of imported vs. skipped items while processing
  3. Only live streams from the playlist are imported; non-live videos are silently skipped
  4. Imported stations appear in the station list under the appropriate provider after import completes
**Plans:** 2/2 plans complete
Plans:
- [x] 14-01-PLAN.md — Backend scan/import logic (yt_import.py) + unit tests
- [x] 14-02-PLAN.md — ImportDialog UI + header bar wiring + human verification
**UI hint**: yes

### Phase 15: AudioAddict Import
**Goal**: Users can bulk-import AudioAddict network channels via API key with quality selection
**Depends on**: Phase 14
**Requirements**: IMPORT-02, IMPORT-03
**Success Criteria** (what must be TRUE):
  1. User can enter an AudioAddict API key and trigger import for all supported networks
  2. User can select stream quality (hi / med / low) before the import runs
  3. Stations already in the library (matched by URL) are skipped on re-import with no duplicates created
  4. Imported stations appear in the station list grouped by AudioAddict provider after import completes
**Plans:** 1/2 plans executed
Plans:
- [x] 15-01-PLAN.md — AudioAddict backend (aa_import.py) + TDD unit tests
- [ ] 15-02-PLAN.md — Refactor ImportDialog to tabbed layout + AudioAddict tab UI + human verification
**UI hint**: yes

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
| 12. Favorites | v1.3 | 1/2 | In Progress|  |
| 13. Radio-Browser Discovery | v1.3 | 2/2 | Complete    | 2026-04-01 |
| 14. YouTube Playlist Import | v1.3 | 2/2 | Complete    | 2026-04-02 |
| 15. AudioAddict Import | v1.3 | 1/2 | In Progress|  |
