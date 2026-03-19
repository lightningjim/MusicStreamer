# Requirements: MusicStreamer

**Defined:** 2026-03-18
**Core Value:** Finding and playing a stream should take seconds — the right station should always be one or two clicks away.

## v1 Requirements

### Code Health

- [x] **CODE-01**: Codebase refactored from monolith into logical modules (models, repo, player, assets, UI) before feature work begins

### Filtering & Search

- [x] **FILT-01**: User can search stations by name via a search box that filters the list in real time
- [x] **FILT-02**: User can filter stations by provider/source via a dropdown (e.g., Soma.FM, AudioAddict)
- [x] **FILT-03**: User can filter stations by genre/tag via a dropdown populated from station tags
- [x] **FILT-04**: Search and both dropdowns compose with AND logic — all active filters narrow the list simultaneously
- [x] **FILT-05**: User can clear all filters to return to full station list

### Now Playing

- [ ] **NOW-01**: User sees currently playing track title from ICY metadata for mp3/aac streams
- [ ] **NOW-02**: Track title display updates automatically when ICY metadata changes mid-stream
- [ ] **NOW-03**: When no ICY metadata is available (e.g., YouTube streams), now-playing area shows station name instead
- [ ] **NOW-04**: Station brand logo displayed top-left (1:1 aspect, from existing station art)
- [ ] **NOW-05**: Track/album art displayed top-right, mirroring the station logo position
- [ ] **NOW-06**: Top-right art falls back to a generic placeholder when no track art is available from the stream

## v2 Requirements

### Now Playing (Enhanced)

- **NOW-V2-01**: Cover art fetched from iTunes Search API based on ICY artist/title metadata
- **NOW-V2-02**: Cover art falls back to station art when lookup returns no results
- **NOW-V2-03**: Cover art lookup is debounced and cached to avoid API hammering on repeated TAG messages
- **NOW-V2-04**: MusicBrainz used as optional fallback when iTunes returns no result

### Stream Sources

- **SRC-V2-01**: Twitch stream URLs supported via yt-dlp (music-only streams)

### Filtering (Enhanced)

- **FILT-V2-01**: Active filter state persists across app restarts

### Station Management

- **MGMT-V2-01**: User can delete a station from the list

## Out of Scope

| Feature | Reason |
|---------|--------|
| Local music library / file playback | Different use case — this is a streaming app |
| Multi-user / authentication | Single-user desktop app |
| Podcast support | Different use case, different feed format |
| Last.fm scrobbling | Future enhancement |
| Mobile app | Linux GNOME desktop only |
| Real-time chat / social features | Out of domain |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CODE-01 | Phase 1 | Complete |
| FILT-01 | Phase 2 | Complete |
| FILT-02 | Phase 2 | Complete |
| FILT-03 | Phase 2 | Complete |
| FILT-04 | Phase 2 | Complete |
| FILT-05 | Phase 2 | Complete |
| NOW-01 | Phase 3 | Pending |
| NOW-02 | Phase 3 | Pending |
| NOW-03 | Phase 3 | Pending |
| NOW-04 | Phase 3 | Pending |
| NOW-05 | Phase 4 | Pending |
| NOW-06 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-18*
*Last updated: 2026-03-18 after roadmap creation*
