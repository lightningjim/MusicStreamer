# Roadmap: MusicStreamer

## Overview

Starting from a working but monolithic ~512-line GTK4/Python/GStreamer codebase, this milestone adds three user-facing features: live search and filter for the station list, ICY metadata display in the now-playing area, and cover art retrieval. The work proceeds in four phases: first extract the monolith into clean modules (zero user-visible change, but each subsequent phase needs a clean home), then deliver filtering (no network I/O, immediate value), then wire ICY metadata to the UI (track title and station logo), then fetch and display cover art from the ICY track data.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Module Extraction** - Refactor monolith into discrete modules so each feature has a clean home (completed 2026-03-18)
- [ ] **Phase 2: Search and Filter** - Live name search and provider/tag dropdown filters with composed AND logic
- [ ] **Phase 3: ICY Metadata Display** - Wire GStreamer TAG bus to show track title and station logo in now-playing area
- [ ] **Phase 4: Cover Art** - Fetch and display track/album art from ICY metadata via iTunes Search API

## Phase Details

### Phase 1: Module Extraction
**Goal**: The codebase is split into logical modules with the app running identically after rewiring
**Depends on**: Nothing (first phase)
**Requirements**: CODE-01
**Success Criteria** (what must be TRUE):
  1. App launches and all existing functionality works identically after the refactor
  2. Code is organized into discrete modules (models, repo, player, assets, UI) with no circular imports
  3. Each module can be read and understood in isolation without loading the full codebase in memory
**Plans:** 3 plans (2 complete, 1 gap closure)
Plans:
- [x] 01-01-PLAN.md — Create package structure, extract data-layer modules (constants, models, repo, assets), write smoke tests
- [x] 01-02-PLAN.md — Extract UI-layer modules (player, station_row, edit_dialog, main_window), wire entry point, delete main.py
- [ ] 01-03-PLAN.md — Fix YouTube audio playback and wire edit station button (gap closure)

### Phase 2: Search and Filter
**Goal**: Users can find any station in seconds using search and dropdowns that compose together
**Depends on**: Phase 1
**Requirements**: FILT-01, FILT-02, FILT-03, FILT-04, FILT-05
**Success Criteria** (what must be TRUE):
  1. User types in the search box and the station list filters in real time by station name
  2. User selects a provider from the dropdown and only stations from that provider appear
  3. User selects a genre/tag from the dropdown and only stations with that tag appear
  4. User has search text, a provider selected, and a tag selected simultaneously — only stations matching all three are shown
  5. User clears all filters (or clicks a clear control) and the full station list returns
**Plans**: TBD

### Phase 3: ICY Metadata Display
**Goal**: The now-playing area reflects what is actually playing — current track title and station identity
**Depends on**: Phase 1
**Requirements**: NOW-01, NOW-02, NOW-03, NOW-04
**Success Criteria** (what must be TRUE):
  1. While a ShoutCast/AAC stream plays, the now-playing area shows the current track title from ICY metadata
  2. When the track changes mid-stream, the displayed title updates automatically without user action
  3. While a YouTube live stream plays (no ICY metadata), the now-playing area shows the station name instead of a blank or error
  4. The station's brand logo is displayed top-left in the now-playing area while a station is playing
**Plans**: TBD

### Phase 4: Cover Art
**Goal**: Track/album art is displayed alongside the now-playing track title, updating as tracks change
**Depends on**: Phase 3
**Requirements**: NOW-05, NOW-06
**Success Criteria** (what must be TRUE):
  1. When a track with ICY metadata plays, artwork for that track appears in the top-right of the now-playing area
  2. When no track art is available (no ICY data, API returns no result), a generic placeholder image is shown in the top-right position
  3. When the track changes, the displayed artwork updates to match the new track
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Module Extraction | 2/3 | Gap closure | - |
| 2. Search and Filter | 0/? | Not started | - |
| 3. ICY Metadata Display | 0/? | Not started | - |
| 4. Cover Art | 0/? | Not started | - |
