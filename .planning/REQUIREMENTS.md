# Requirements: MusicStreamer

**Defined:** 2026-03-20
**Core Value:** Finding and playing a stream should take seconds — the right station should always be one or two clicks away.

## v1.1 Requirements

### Bug Fix

- [ ] **BUG-01**: ICY track title displays correctly when title contains `&`, `<`, `>`, or other GTK markup special characters

### Station Management

- [ ] **MGMT-01**: User can delete a station from the station list
- [ ] **MGMT-02**: Station editor auto-populates station image from YouTube thumbnail when a YouTube URL is entered

### Station Display

- [ ] **DISP-01**: Station list shows each station's logo image inline in the row

### ICY Behavior

- [ ] **ICY-01**: User can disable ICY metadata per station (for stations where ICY returns wrong/irrelevant data)

## v2 Requirements

*(None captured yet)*

## Out of Scope

| Feature | Reason |
|---------|--------|
| MusicBrainz cover art fallback | iTunes sufficient; revisit if gaps found |
| Twitch stream support | No Twitch stations in library to validate against |
| Last.fm scrobbling | Future enhancement, out of v1.x scope |
| Mobile app | Linux GNOME desktop only |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| BUG-01 | Phase 5 | Pending |
| MGMT-01 | Phase 5 | Pending |
| MGMT-02 | Phase 5 | Pending |
| DISP-01 | Phase 5 | Pending |
| ICY-01 | Phase 5 | Pending |

**Coverage:**
- v1.1 requirements: 5 total
- Mapped to phases: 0
- Unmapped: 5 ⚠️

---
*Requirements defined: 2026-03-20*
*Last updated: 2026-03-20 after initial v1.1 definition*
