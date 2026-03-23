# Roadmap: MusicStreamer

## Milestones

- ✅ **v1.0 MVP** — Phases 1–4 (shipped 2026-03-20)
- ✅ **v1.1 Polish & Station Management** — Phases 5–6 (shipped 2026-03-21)
- 🚧 **v1.2 Station UX & Polish** — Phases 7–11 (in progress)

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

### 🚧 v1.2 Station UX & Polish (In Progress)

**Milestone Goal:** Better station browsing with provider grouping, multi-select filters, recently played, volume control, and visual polish.

- [x] **Phase 7: Station List Restructuring** — Provider-grouped list with recently played section (completed 2026-03-22)
- [x] **Phase 8: Filter Bar Multi-Select** — Replace dropdowns with multi-select provider/genre filters (completed 2026-03-22)
- [x] **Phase 9: Station Editor Improvements** — Structured provider/genre selectors with inline creation and YouTube title import (completed 2026-03-23)
- [ ] **Phase 10: Now Playing & Audio** — Provider name in now-playing panel, volume slider with persistence
- [ ] **Phase 11: UI Polish** — Rounded corners, softened colors, improved spacing throughout

## Phase Details

### Phase 7: Station List Restructuring
**Goal**: Users can browse stations organized by provider, with recently played stations surfaced at the top
**Depends on**: Phase 6
**Requirements**: BROWSE-01, BROWSE-04
**Success Criteria** (what must be TRUE):
  1. Station list displays stations grouped under their provider as a collapsible header row
  2. All provider groups are collapsed by default; clicking a header expands that group
  3. A "Recently Played" section appears above all provider groups, showing the last 3 played stations in order (most recent first)
  4. Recently Played updates after each play session without requiring restart
**Plans:** 3/3 plans complete

Plans:
- [x] 07-01-PLAN.md — Data layer: schema migrations, Station model update, repo methods for recently played and settings
- [x] 07-02-PLAN.md — UI restructuring: provider-grouped ExpanderRow layout with dual render modes
- [x] 07-03-PLAN.md — Recently Played section integration and play hook wiring

### Phase 8: Filter Bar Multi-Select
**Goal**: Users can filter the station list by multiple providers and/or genres simultaneously
**Depends on**: Phase 7
**Requirements**: BROWSE-02, BROWSE-03
**Success Criteria** (what must be TRUE):
  1. User can select more than one provider in the filter bar and the list shows stations from all selected providers
  2. User can select more than one genre/tag and the list shows stations matching any selected genre
  3. Provider and genre filters compose with AND logic (selected providers AND selected genres)
  4. Clearing all filter selections returns the full grouped station list
**Plans:** 2/2 plans complete

Plans:
- [x] 08-01-PLAN.md — TDD: matches_filter_multi function for multi-select OR/AND filter logic
- [x] 08-02-PLAN.md — Replace DropDown widgets with ToggleButton chip strips and wire multi-select state

### Phase 9: Station Editor Improvements
**Goal**: Users can assign providers and genres from existing values without manual typing, add new values inline, and get station names auto-filled from YouTube URLs
**Depends on**: Phase 6
**Requirements**: MGMT-01, MGMT-02, MGMT-03, MGMT-04
**Success Criteria** (what must be TRUE):
  1. Station editor shows a dropdown/picker of existing providers instead of a freeform text field
  2. Station editor shows existing genres/tags as multi-select checkboxes or chips
  3. User can type a new provider or genre name in the editor and save it without leaving the dialog
  4. Entering a YouTube URL auto-populates the station name field with the stream title fetched from YouTube
**Plans:** 2/2 plans complete

Plans:
- [x] 09-01-PLAN.md — Provider ComboRow picker + tag chip panel with inline creation
- [x] 09-02-PLAN.md — YouTube title auto-import on URL focus-out

### Phase 10: Now Playing & Audio
**Goal**: Users can see which provider a playing station belongs to and control playback volume persistently
**Depends on**: Phase 6
**Requirements**: NP-01, AUDIO-01, AUDIO-02
**Success Criteria** (what must be TRUE):
  1. Now Playing panel shows the station's provider name alongside the station name
  2. A volume slider in the main window controls GStreamer playback volume in real time
  3. Volume setting is restored to its previous value when the app is restarted
**Plans:** 2 plans

Plans:
- [ ] 10-01-PLAN.md — TDD: Player.set_volume with clamping and mpv --volume arg
- [ ] 10-02-PLAN.md — Provider label formatting and volume slider UI with persistence

### Phase 11: UI Polish
**Goal**: The app has a visually refined appearance with consistent rounded corners, softened colors, and improved spacing
**Depends on**: Phase 10
**Requirements**: UI-01, UI-02, UI-03, UI-04
**Success Criteria** (what must be TRUE):
  1. Panels and cards display with rounded corners (no sharp rectangular edges)
  2. Background and surface colors use subtle gradients rather than flat fills
  3. Station list rows have noticeably more vertical padding (station names and logos are not cramped)
  4. Now Playing panel has increased internal whitespace around its content areas
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Module Extraction | v1.0 | 3/3 | Complete | 2026-03-18 |
| 2. Search and Filter | v1.0 | 2/2 | Complete | 2026-03-19 |
| 3. ICY Metadata Display | v1.0 | 2/2 | Complete | 2026-03-20 |
| 4. Cover Art | v1.0 | 1/1 | Complete | 2026-03-20 |
| 5. Display Polish | v1.1 | 2/2 | Complete | 2026-03-21 |
| 6. Station Management | v1.1 | 2/2 | Complete | 2026-03-21 |
| 7. Station List Restructuring | v1.2 | 3/3 | Complete    | 2026-03-22 |
| 8. Filter Bar Multi-Select | v1.2 | 2/2 | Complete   | 2026-03-22 |
| 9. Station Editor Improvements | v1.2 | 2/2 | Complete   | 2026-03-23 |
| 10. Now Playing & Audio | v1.2 | 0/2 | Planned | - |
| 11. UI Polish | v1.2 | 0/? | Not started | - |
