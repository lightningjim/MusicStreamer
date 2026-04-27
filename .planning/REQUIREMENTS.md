# Requirements: MusicStreamer — v2.1 Fixes and Tweaks

**Defined:** 2026-04-27
**Core Value:** Finding and playing a stream should take seconds — the right station should always be one or two clicks away.

**Milestone shape:** Rolling polish milestone. Initial scope below seeds the roadmap; additional requirements (`BUG-NN`, `WIN-NN`, etc.) will be appended throughout v2.1 as Kyle plays with the app and reports new issues or improvements. Milestone closes when Kyle calls `/gsd-complete-milestone`, not at a fixed REQ count.

## v2.1 Requirements

Initial committed scope. Each maps to a roadmap phase.

### Backlog Bugs (BUG)

Closing v2.0 backlog bug stubs plus the live YouTube-on-Linux regression.

- [ ] **BUG-07** *(MUST BE FIRST PHASE)*: YouTube live stream playback works again on Linux — investigate regression (root cause + fix). Suspected to have broken since v2.0 ship; Phase 999.9 closed an earlier YT regression on the JS-runtime path, so this is either a new regression or a Linux-specific facet of the same area. Phase scope is **investigation-led**: identify the root cause first, then either ship the fix in the same phase (if scoped) or split into a follow-up.
- [ ] **BUG-01**: Recently played list updates live as new stations are played — no manual refresh required *(stub: 999.2)*
- [ ] **BUG-02**: Cross-network AudioAddict mirror/sibling streams surface as related streams when editing or playing a station *(stub: 999.4)*
- [ ] **BUG-03**: Toggling EQ on/off does not produce an audible audio dropout *(stub: 999.5)*
- [ ] **BUG-04**: YouTube cookies entry is consolidated into the Accounts menu (single accounts surface for Twitch + YouTube) *(stub: 999.6)*
- [ ] **BUG-05**: Rectangular brand logos display fully in the radio logo view (no square-only crop that cuts off content) *(stub: 999.10)*
- [ ] **BUG-06**: Saving an edit in `EditStationDialog` preserves the open/closed state of expandable sections (does not collapse all open sections on save) *(stub: 999.11)*

### Windows Polish (WIN)

Phase 44 carry-forward — items deferred from the v2.0 ship line.

- [ ] **WIN-01**: DI.fm premium streams play on Windows via a chosen HTTPS-fallback policy (HTTP-for-DI.fm-only or accept server-side HTTPS-unavailable with explicit user feedback)
- [ ] **WIN-02**: SMTC overlay shows "MusicStreamer" instead of "Unknown app" via a registered Start Menu shortcut carrying `System.AppUserModel.ID=org.lightningjim.MusicStreamer` (matches the in-process AUMID set during startup)
- [ ] **WIN-03**: Audio pause/resume on Windows produces no audible glitch; the volume slider takes effect on Windows playback (parity with Linux)
- [ ] **WIN-04**: `test_thumbnail_from_in_memory_stream` passes on Windows (`MagicMock` replaced with `AsyncMock` for the `store_async` await)

### Features (FEAT)

Small new capabilities harvested from backlog + dormant seeds.

- [ ] **STR-15**: User can paste a PLS URL into a station's Streams section and have it auto-resolve into N individual stream entries (one per playlist row) *(backlog: 999.12 — deferred Phase 49 work)*
- [ ] **ACCENT-02**: User can pick a custom accent color via a visual color picker (HSV/wheel surface), in addition to the existing 8 presets and hex entry *(harvest: SEED-006)*
- [ ] **GBS-01**: User can browse, save, and play GBS.FM streams from inside MusicStreamer (no browser bounce) *(harvest: SEED-008 — exact sub-capabilities to be refined at /gsd-discuss-phase time; may decompose into GBS-01..0N during planning)*

## Future Requirements

Acknowledged but not committed to v2.1 initial scope. Pull in opportunistically via `/gsd-add-phase` if Kyle wants to tackle them inside the milestone.

### Pending Notes

- **SDR-01**: Live radio support via SDR (Software Defined Radio) — `.planning/notes/2026-03-21-sdr-live-radio-support.md`
- **ART-04**: Station art fetching beyond YouTube/iTunes/AudioAddict (additional sources) — `.planning/notes/2026-04-03-station-art-fetching-beyond-youtube.md`

## Out of Scope

Explicitly excluded from v2.1. Carried forward from v2.0 OoS plus milestone-specific exclusions.

| Feature | Reason |
|---------|--------|
| 999.3-03 HUMAN-UAT (Twitch/Google login fall-back) | Backlog phase (refuted/resolved during v2.0); not a v2.1 gate |
| Radio-Browser.info as primary browse mode | Anti-feature — undermines curated library; modal/import flow only |
| Playback history distinct from favorites | Different use case; favorites are intentional stars |
| Auto-refresh saved Radio-Browser stations | Manual management; auto-refresh is unclear value |
| Social sharing / export of favorites | Single-user desktop app |
| MusicBrainz cover art fallback | iTunes sufficient; revisit if gaps found |
| Local music library / file playback | Streaming app only |
| Multi-user / authentication | Single-user desktop app |
| Podcast support | Different use case |
| Last.fm scrobbling | Future enhancement, not v2.1 |
| Mobile app | Desktop only (Linux + Windows) |
| Cloud-sync settings | Replaced by manual export/import (Phase 42) — explicit user-driven sync only |

## Traceability

Which phases cover which requirements. Empty initially — populated by `gsd-roadmapper`.

| Requirement | Phase | Status |
|-------------|-------|--------|
| BUG-07 | TBD (first phase) | Pending |
| BUG-01 | TBD | Pending |
| BUG-02 | TBD | Pending |
| BUG-03 | TBD | Pending |
| BUG-04 | TBD | Pending |
| BUG-05 | TBD | Pending |
| BUG-06 | TBD | Pending |
| WIN-01 | TBD | Pending |
| WIN-02 | TBD | Pending |
| WIN-03 | TBD | Pending |
| WIN-04 | TBD | Pending |
| STR-15 | TBD | Pending |
| ACCENT-02 | TBD | Pending |
| GBS-01 | TBD | Pending |

**Coverage (initial):**
- v2.1 requirements: 14 total
- Mapped to phases: 0 (roadmap pending)
- Unmapped: 14 ⚠️ — to be resolved by `gsd-roadmapper`

---
*Requirements defined: 2026-04-27 — milestone v2.1 Fixes and Tweaks (rolling)*
*Last updated: 2026-04-27 — initial definition*
