# Requirements: MusicStreamer — v2.1 Fixes and Tweaks

**Defined:** 2026-04-27
**Core Value:** Finding and playing a stream should take seconds — the right station should always be one or two clicks away.

**Milestone shape:** Rolling polish milestone. Initial scope below seeds the roadmap; additional requirements (`BUG-NN`, `WIN-NN`, etc.) will be appended throughout v2.1 as Kyle plays with the app and reports new issues or improvements. Milestone closes when Kyle calls `/gsd-complete-milestone`, not at a fixed REQ count.

## v2.1 Requirements

Initial committed scope. Each maps to a roadmap phase.

### Backlog Bugs (BUG)

Closing v2.0 backlog bug stubs plus the live YouTube-on-Linux regression.

- [x] **BUG-07** *(was MUST-BE-FIRST-PHASE — resolved 2026-04-27 without code change)*: YouTube live stream playback works again on Linux — Phase 49. Resolved before code-level investigation began; user reinstalled both `yt-dlp` and the GStreamer plugins at the OS level — suspected fix is one of those two but not bisected (both reinstalled together). Root cause not formally documented. If regression returns, reopen as new phase 49.1 and bisect (revert yt-dlp first, then GStreamer plugins).
- [x] **BUG-01**: Recently played list updates live as new stations are played — no manual refresh required *(stub: 999.2)*
- [ ] **BUG-02**: Cross-network AudioAddict mirror/sibling streams surface as related streams when editing or playing a station *(stub: 999.4)*
- [ ] **BUG-03**: Toggling EQ on/off does not produce an audible audio dropout *(stub: 999.5)*
- [ ] **BUG-04**: YouTube cookies entry is consolidated into the Accounts menu (single accounts surface for Twitch + YouTube) *(stub: 999.6)*
- [ ] **BUG-05**: Rectangular brand logos display fully in the radio logo view (no square-only crop that cuts off content) *(stub: 999.10)*
- [ ] **BUG-06**: Saving an edit in `EditStationDialog` preserves the open/closed state of expandable sections (does not collapse all open sections on save) *(stub: 999.11)*
- [ ] **BUG-08**: Linux force-quit and other WM-level dialogs display "MusicStreamer" instead of the reverse-DNS app ID "org.example.MusicStreamer" — Linux parallel to WIN-02 *(surfaced during Phase 50 UAT 2026-04-28)*
- [ ] **BUG-09**: Intermittent audio dropouts/stutters when the GStreamer buffer can't keep up are observable, attributable, and (once root-caused) mitigated. Repro is unclear at filing time — phase ships diagnostic instrumentation first, then a behavior fix once root cause is observable *(surfaced 2026-04-28)*

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

### Versioning Convention (VER)

Project-level convention introduced 2026-04-28.

- [ ] **VER-01**: Adopt `milestone_major.milestone_minor.phase` versioning (e.g. `2.1.50` for Phase 50 of v2.1). The `pyproject.toml` `version` field is rewritten automatically on phase completion via a GSD-workflow hook, gated by a per-project config flag, and the convention is documented in PROJECT.md *(applies to all future phase completions starting Phase 51+; Phase 50 was bumped manually as the first instance)*

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

Which phases cover which requirements.

| Requirement | Phase | Status |
|-------------|-------|--------|
| BUG-07 | Phase 49 | ✓ Complete (no code change) |
| BUG-01 | Phase 50 | Complete |
| BUG-02 | Phase 51 | In progress (1/5 plans) |
| BUG-03 | Phase 52 | Pending |
| BUG-04 | Phase 53 | Pending |
| BUG-05 | Phase 54 | Pending |
| BUG-06 | Phase 55 | Pending |
| WIN-01 | Phase 56 | Pending |
| WIN-02 | Phase 56 | Pending |
| WIN-03 | Phase 57 | Pending |
| WIN-04 | Phase 57 | Pending |
| STR-15 | Phase 58 | Pending |
| ACCENT-02 | Phase 59 | Pending |
| GBS-01 | Phase 60 | Pending |
| BUG-08 | Phase 61 | Pending |
| BUG-09 | Phase 62 | Pending |
| VER-01 | Phase 63 | Pending |

**Coverage:**
- v2.1 requirements: 17 total
- Mapped to phases: 17 ✓
- Unmapped: 0 ✓
- Complete: 2 (BUG-07 env-level; BUG-01 Phase 50)
- Pending: 15

---
*Requirements defined: 2026-04-27 — milestone v2.1 Fixes and Tweaks (rolling)*
*Last updated: 2026-04-28 — Phase 50 / BUG-01 complete (Recently Played live update). BUG-08 (Linux WM display name) + BUG-09 (audio buffer underrun resilience) + VER-01 (milestone.minor.phase versioning auto-bump) added post-Phase 50.*
