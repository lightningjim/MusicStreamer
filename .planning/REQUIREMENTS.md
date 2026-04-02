# Requirements: MusicStreamer v1.3

**Defined:** 2026-03-27
**Core Value:** Finding and playing a stream should take seconds — the right station should always be one or two clicks away.

## v1.3 Requirements

### Favorites

- [ ] **FAVES-01**: User can star the currently playing ICY track title (star button in now-playing, gated on non-junk title)
- [x] **FAVES-02**: Favorited track is stored in DB with station name, provider name, track title, and iTunes genre (denormalized for station-deletion resilience)
- [ ] **FAVES-03**: User can toggle between Stations and Favorites inline list view in the sidebar
- [ ] **FAVES-04**: User can remove a track from the Favorites view

### Discovery (Radio-Browser.info)

- [x] **DISC-01**: User can search Radio-Browser.info stations by name or provider name from an in-app discovery dialog
- [x] **DISC-02**: User can filter Radio-Browser.info search results by tag (genre) or country
- [x] **DISC-03**: User can play a Radio-Browser.info station as a preview without saving it to the library
- [x] **DISC-04**: User can save a Radio-Browser.info station to their library from the discovery dialog

### Import (YouTube)

- [x] **IMPORT-01**: User can paste a public YouTube playlist URL and import its live streams as stations, with progress feedback (spinner + imported/skipped count)

### Import (AudioAddict)

- [ ] **IMPORT-02**: User can enter an AudioAddict API key to import channels from all AudioAddict networks, skipping stations already in library by URL (exact network list verified at implementation time)
- [ ] **IMPORT-03**: User can select stream quality (hi / med / low) before importing AudioAddict channels

## Future Requirements

### Discovery

- **DISC-F01**: Paginate Radio-Browser.info results beyond initial 100-station limit
- **DISC-F02**: Browse Radio-Browser.info by most popular or recently added (no search term)

### Favorites

- **FAVES-F01**: Export favorites list as CSV or plain text

## Out of Scope

| Feature | Reason |
|---------|--------|
| Radio-Browser.info as primary browse mode | Anti-feature — undermines curated library model; discovery is modal/import flow only |
| Playback history distinct from favorites | Different use case; favorites are intentional stars, not automatic history |
| Auto-refresh saved Radio-Browser stations | Stations in library are managed manually; auto-refresh adds complexity for unclear benefit |
| Social sharing / export of favorites | Single-user desktop app |
| MusicBrainz cover art fallback | iTunes sufficient; revisit if gaps found |
| Twitch stream support | yt-dlp supports it; revisit if user adds Twitch stations |
| Local music library / file playback | Streaming app only |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FAVES-01 | Phase 12 | Pending |
| FAVES-02 | Phase 12 | Complete |
| FAVES-03 | Phase 12 | Pending |
| FAVES-04 | Phase 12 | Pending |
| DISC-01 | Phase 13 | Complete |
| DISC-02 | Phase 13 | Complete |
| DISC-03 | Phase 13 | Complete |
| DISC-04 | Phase 13 | Complete |
| IMPORT-01 | Phase 14 | Complete |
| IMPORT-02 | Phase 15 | Pending |
| IMPORT-03 | Phase 15 | Pending |

**Coverage:**
- v1.3 requirements: 11 total
- Mapped to phases: 11
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-27*
*Last updated: 2026-03-27 — traceability mapped after roadmap creation*
