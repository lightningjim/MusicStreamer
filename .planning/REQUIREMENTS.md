# Requirements: MusicStreamer

**Defined:** 2026-03-21
**Core Value:** Finding and playing a stream should take seconds — the right station should always be one or two clicks away.

## v1.2 Requirements

### Browsing

- [ ] **BROWSE-01**: Stations are grouped by provider in the station list, collapsed by default, expandable per group
- [ ] **BROWSE-02**: User can filter by multiple providers simultaneously (multi-select)
- [ ] **BROWSE-03**: User can filter by multiple genres/tags simultaneously (multi-select)
- [ ] **BROWSE-04**: A "Recently Played" section sits at the top of the station list (above provider groups) showing the last 3 played stations, most recent first

### Station Management

- [ ] **MGMT-01**: Station editor shows existing providers as selectable options (not just freeform text)
- [ ] **MGMT-02**: Station editor shows existing genres/tags as selectable options with multi-select
- [ ] **MGMT-03**: User can add a new provider or genre/tag inline from the station editor
- [ ] **MGMT-04**: YouTube station URL auto-imports the stream title into the station name field

### Now Playing

- [ ] **NP-01**: Now Playing panel shows the provider name alongside the station name

### Audio

- [ ] **AUDIO-01**: Volume slider in main window controls playback volume
- [ ] **AUDIO-02**: Volume setting persists between sessions

### UI Polish

- [ ] **UI-01**: Panels and cards use rounded corners
- [ ] **UI-02**: Color palette softened with subtle gradients (less harsh contrast)
- [ ] **UI-03**: Station list rows have increased vertical padding
- [ ] **UI-04**: Now Playing panel has increased internal whitespace

## Future Requirements

### Station Auto-Loading

- **AUTO-01**: User can import stations from AudioAddict/DI.fm via API key
- **AUTO-02**: User can import stations from a YouTube live channel playlist

### Sync

- **SYNC-01**: User can sync station config between computers (e.g. QNAP share)

### SDR

- **SDR-01**: User can tune to AM/FM/digital radio via SDR hardware or remote SDR server

## Out of Scope

| Feature | Reason |
|---------|--------|
| MusicBrainz cover art fallback | iTunes sufficient; revisit if gaps found |
| Twitch stream support | yt-dlp supports it; revisit if user adds Twitch stations |
| Local music library / file playback | Streaming app only |
| Multi-user / authentication | Single-user desktop app |
| Podcast support | Different use case |
| Last.fm scrobbling | Future enhancement |
| Mobile app | Linux GNOME desktop only |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| BROWSE-01 | Phase 7 | Pending |
| BROWSE-04 | Phase 7 | Pending |
| BROWSE-02 | Phase 8 | Pending |
| BROWSE-03 | Phase 8 | Pending |
| MGMT-01 | Phase 9 | Pending |
| MGMT-02 | Phase 9 | Pending |
| MGMT-03 | Phase 9 | Pending |
| MGMT-04 | Phase 9 | Pending |
| NP-01 | Phase 10 | Pending |
| AUDIO-01 | Phase 10 | Pending |
| AUDIO-02 | Phase 10 | Pending |
| UI-01 | Phase 11 | Pending |
| UI-02 | Phase 11 | Pending |
| UI-03 | Phase 11 | Pending |
| UI-04 | Phase 11 | Pending |

**Coverage:**
- v1.2 requirements: 15 total
- Mapped to phases: 15
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-21*
*Last updated: 2026-03-21 after v1.2 roadmap created*
