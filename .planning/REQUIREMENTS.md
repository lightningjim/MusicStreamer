# Requirements: MusicStreamer — v2.1 Fixes and Tweaks

**Defined:** 2026-04-27
**Core Value:** Finding and playing a stream should take seconds — the right station should always be one or two clicks away.

**Milestone shape:** Rolling polish milestone. Initial scope below seeds the roadmap; additional requirements (`BUG-NN`, `WIN-NN`, etc.) will be appended throughout v2.1 as Kyle plays with the app and reports new issues or improvements. Milestone closes when Kyle calls `/gsd-complete-milestone`, not at a fixed REQ count.

## v2.1 Requirements

Initial committed scope. Each maps to a roadmap phase.

### Backlog Bugs (BUG)

Closing v2.0 backlog bug stubs plus the live YouTube-on-Linux regression.

- [x] **BUG-07** *(was MUST-BE-FIRST-PHASE — resolved 2026-04-27 without code change)*: YouTube live stream playback works again on Linux — Phase 49. Resolved before code-level investigation began; user reinstalled both `yt-dlp` and the GStreamer plugins at the OS level — suspected fix is one of those two but not bisected (both reinstalled together). Root cause not formally documented. If regression returns, reopen as new phase 49.1 and bisect (revert yt-dlp first, then GStreamer plugins).
- [x] **BUG-01**: Recently played list updates live as new stations are played — no manual refresh required
- [x] **BUG-02**: Cross-network AudioAddict mirror/sibling streams surface as related streams when editing or playing a station
- [x] **BUG-03**: Toggling EQ on/off does not produce an audible audio dropout
- [x] **BUG-04**: YouTube cookies entry is consolidated into the Accounts menu (single accounts surface for Twitch + YouTube)
- [x] **BUG-05**: Rectangular brand logos display fully in the radio logo view (no square-only crop that cuts off content) — Phase 54 closed in two stages: Path B-1 canvas patch in `_art_paths.py` (commit `b1a9088`) fixed landscape, Path B-2 delegate `paint`+`sizeHint` overrides in `station_star_delegate.py` (commit `af63397`) fixed portrait on Linux X11/Wayland
- [x] **BUG-06**: Saving an edit in `EditStationDialog` preserves the open/closed state of expandable sections (does not collapse all open sections on save)
- [x] **BUG-08**: Linux force-quit and other WM-level dialogs display "MusicStreamer" instead of the reverse-DNS app ID "org.example.MusicStreamer" — Linux parallel to WIN-02 *(surfaced during Phase 50 UAT 2026-04-28)*
- [x] **BUG-09**: Intermittent audio dropouts/stutters when the GStreamer buffer can't keep up are observable, attributable, and (once root-caused) mitigated. Repro is unclear at filing time — phase ships diagnostic instrumentation first, then a behavior fix once root cause is observable *(surfaced 2026-04-28)*

### Windows Polish (WIN)

Phase 44 carry-forward — items deferred from the v2.0 ship line.

- [x] **WIN-01**: DI.fm premium streams play on Windows via a chosen HTTPS-fallback policy (HTTP-for-DI.fm-only or accept server-side HTTPS-unavailable with explicit user feedback)
- [ ] **WIN-02**: SMTC overlay shows "MusicStreamer" instead of "Unknown app" via a registered Start Menu shortcut carrying `System.AppUserModel.ID=org.lightningjim.MusicStreamer` (matches the in-process AUMID set during startup)
- [x] **WIN-03**: Audio pause/resume on Windows produces no audible glitch; the volume slider takes effect on Windows playback (parity with Linux)
- [x] **WIN-04**: `test_thumbnail_from_in_memory_stream` passes on Windows (`MagicMock` replaced with `AsyncMock` for the `store_async` await)
- [x] **WIN-05**: AAC-encoded streams play on Windows — DI.fm AAC tier + SomaFM HE-AAC fixtures verified post-bundle-fix *(Phase 69)*

### Features (FEAT)

Small new capabilities harvested from backlog + dormant seeds.

- [x] **STR-15**: User can paste a PLS URL into a station's Streams section and have it auto-resolve into N individual stream entries (one per playlist row)
- [x] **ACCENT-02**: User can pick a custom accent color via a visual color picker (HSV/wheel surface), in addition to the existing 8 presets and hex entry *(harvest: SEED-006)*
- [x] **GBS-01**: User can browse, save, and play GBS.FM streams from inside MusicStreamer (no browser bounce) *(harvest: SEED-008 — exact sub-capabilities to be refined at /gsd-discuss-phase time; may decompose into GBS-01..0N during planning)*
- [x] **THEME-01**: User can switch between preset color themes (System default, Vaporwave, Overrun, GBS.FM, GBS.FM After Dark, Dark, Light) and one user-editable Custom palette via a Theme picker in the hamburger menu. The chosen theme drives the application QPalette's 9 primary roles (Window, WindowText, Base, AlternateBase, Text, Button, ButtonText, HighlightedText, Link). The accent_color override (Phase 59 / ACCENT-02) continues to layer on top of the theme's Highlight baseline; selecting a theme does NOT mutate `accent_color`. The Custom slot is duplicate-and-edit only with snapshot-restore-on-Cancel.
- [x] **HRES-01**: User sees an automatic two-tier audio-quality badge ("LOSSLESS" / "HI-RES") next to each station's now-playing panel, station-tree row, stream-picker entry, and EditStationDialog row, plus a "Hi-Res only" filter chip and a hi-res-preferring tiebreak in stream failover ordering — all driven from negotiated GStreamer caps cached per stream after first replay, mirroring moOde Audio's Hi-Res convention.

### Versioning Convention (VER)

Project-level convention introduced 2026-04-28.

- [x] **VER-01**: Adopt `milestone_major.milestone_minor.phase` versioning (e.g. `2.1.50` for Phase 50 of v2.1). The `pyproject.toml` `version` field is rewritten automatically on phase completion via a GSD-workflow hook, gated by a per-project config flag, and the convention is documented in PROJECT.md *(applies to all future phase completions starting Phase 51+; Phase 50 was bumped manually as the first instance)*
- [x] **VER-02**: The running app surfaces its current version (read from `pyproject.toml` via `importlib.metadata`) as a disabled informational entry at the bottom of the hamburger menu. The Windows PyInstaller bundle ships `musicstreamer.dist-info` so the bundled exe reads the same version dev sees. *(Phase 65 — consumes Phase 63's auto-bump output)*

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
| BUG-02 | Phase 51 | Complete |
| BUG-03 | Phase 52 | Complete |
| BUG-04 | Phase 53 | Complete |
| BUG-05 | Phase 54 | Complete — landscape fixed (Path B-1, `b1a9088`) + portrait fixed (Path B-2, `af63397`) |
| BUG-06 | Phase 55 | Complete |
| WIN-01 | Phase 56 | Complete |
| WIN-02 | Phase 56 | Pending |
| WIN-03 | Phase 57 | Complete |
| WIN-04 | Phase 57 | Complete |
| STR-15 | Phase 58 | Complete |
| ACCENT-02 | Phase 59 | Complete |
| GBS-01 | Phase 60 | Complete |
| BUG-08 | Phase 61 | Complete |
| BUG-09 | Phase 62 | Complete |
| VER-01 | Phase 63 | Complete |
| VER-02 | Phase 65 | Complete |
| THEME-01 | Phase 66 | Complete |
| WIN-05 | Phase 69 | Complete |
| HRES-01 | Phase 70 | Complete |

**Coverage:**
- v2.1 requirements: 21 total
- Mapped to phases: 21 ✓
- Unmapped: 0 ✓
- Complete: 19
- Pending: 2 (WIN-02 — SMTC Start Menu shortcut with AUMID; WIN-05 — AAC Win11 UAT)

---
*Requirements defined: 2026-04-27 — milestone v2.1 Fixes and Tweaks (rolling)*
*Last updated: 2026-05-12 — HRES-01 (two-tier hi-res audio badge + caps-driven cache + Hi-Res only filter chip + rate/depth tiebreak in stream ordering) added for Phase 70.*
