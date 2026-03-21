# Roadmap: MusicStreamer

## Milestones

- ✅ **v1.0 MVP** — Phases 1–4 (shipped 2026-03-20)
- 🚧 **v1.1 Polish & Station Management** — Phases 5–6 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1–4) — SHIPPED 2026-03-20</summary>

- [x] Phase 1: Module Extraction (3/3 plans) — completed 2026-03-18
- [x] Phase 2: Search and Filter (2/2 plans) — completed 2026-03-19
- [x] Phase 3: ICY Metadata Display (2/2 plans) — completed 2026-03-20
- [x] Phase 4: Cover Art (1/1 plan) — completed 2026-03-20

Full details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

### 🚧 v1.1 Polish & Station Management (In Progress)

**Milestone Goal:** Fix visual correctness issues and complete station management UX.

- [x] **Phase 5: Display Polish** - Fix GTK markup escaping and surface station art in the list (completed 2026-03-21)
- [ ] **Phase 6: Station Management** - Delete stations and improve the station editor with YT thumbnail auto-load and per-station ICY override

## Phase Details

### Phase 5: Display Polish
**Goal**: The station list and now-playing panel display content correctly with no visual defects
**Depends on**: Phase 4
**Requirements**: BUG-01, BUG-02, DISP-01
**Success Criteria** (what must be TRUE):
  1. ICY track titles containing `&`, `<`, `>`, or `"` display as readable text, not as broken GTK markup or blank labels
  2. Cover art slot shows the station's own logo when no ICY title is available (not the generic notes icon)
  3. Each station row in the list shows the station's logo image at the correct size alongside the station name
  4. Stations without a logo show a consistent placeholder in the row (no missing-image artifacts)
**Plans:** 2/2 plans complete

Plans:
- [ ] 05-01-PLAN.md — Fix ICY title markup escaping + station logo as cover art default
- [ ] 05-02-PLAN.md — Station row logo images with placeholder fallback

### Phase 6: Station Management
**Goal**: Users can delete stations and the station editor handles YouTube URLs and ICY behavior correctly
**Depends on**: Phase 5
**Requirements**: MGMT-01, MGMT-02, ICY-01
**Success Criteria** (what must be TRUE):
  1. User can delete a station from the list and it is removed immediately without restart
  2. Entering a YouTube URL in the station editor automatically populates the station image field with the video thumbnail
  3. User can toggle ICY metadata off for a specific station and the setting persists across sessions
  4. A station with ICY disabled plays without showing ICY track title metadata (station name or silence shown instead)
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Module Extraction | v1.0 | 3/3 | Complete | 2026-03-18 |
| 2. Search and Filter | v1.0 | 2/2 | Complete | 2026-03-19 |
| 3. ICY Metadata Display | v1.0 | 2/2 | Complete | 2026-03-20 |
| 4. Cover Art | v1.0 | 1/1 | Complete | 2026-03-20 |
| 5. Display Polish | 2/2 | Complete   | 2026-03-21 | - |
| 6. Station Management | v1.1 | 0/TBD | Not started | - |
