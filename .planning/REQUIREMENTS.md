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
- [ ] **BUG-10**: SQLite `PRAGMA foreign_keys = ON` is set on every connection opened by `db_connect()` (or equivalent), making the schema's existing `ON DELETE CASCADE` constraints actually enforce at runtime. Without the PRAGMA, every `DELETE FROM stations` (and any other parent-row deletion) silently leaks orphan child rows — `station_streams`, possibly `favorites`, `station_siblings`, and any other FK child table. Phase also (a) writes a regression test that DELETEs a station and asserts the cascade fires, (b) emits a one-time INFO log if `PRAGMA foreign_keys` was OFF at connection time (drift guard for any code path that forgets), (c) ships a one-shot orphan-sweep migration that scans every child table for rows whose FK parent no longer exists, deletes them, and logs the counts, and (d) documents the per-connection requirement in `musicstreamer/db.py` (or wherever `db_connect()` lives) so future contributors don't reintroduce the gap *(surfaced 2026-05-14 during Phase 74 Plan 07 UAT, finding F-07-03 — required manual `DELETE FROM station_streams WHERE url LIKE '%synphaera%'` cleanup mid-UAT to unblock dedup re-import; full root cause in 74-LEARNINGS.md and reference-musicstreamer-db-schema memory)*

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
- [x] **THEME-02**: Toast notifications track the active theme via QPalette.ToolTipBase/ToolTipText. When user picks a theme via the Picker (preset or Custom), the next-fired and currently-visible toasts retint to the theme's tooltip colors at alpha=220. theme='system' preserves the legacy rgba(40, 40, 40, 220) + white QSS byte-for-byte (no regression on day-one default). The Custom theme editor grows from 9 -> 11 editable roles (appending ToolTipBase and ToolTipText after Link). Custom JSON additive — no SQLite schema change. *(Phase 75)*
- [x] **HRES-01**: User sees an automatic two-tier audio-quality badge ("LOSSLESS" / "HI-RES") next to each station's now-playing panel, station-tree row, stream-picker entry, and EditStationDialog row, plus a "Hi-Res only" filter chip and a hi-res-preferring tiebreak in stream failover ordering — all driven from negotiated GStreamer caps cached per stream after first replay, mirroring moOde Audio's Hi-Res convention.

### Sibling Stations (SIB)

Manual user-curated cross-network/same-provider sibling linking, replacing the prior need for hand-edited DB rows.

- [x] **SIB-01**: Manual sibling-station linking via GUI replaces hand-DB-edits. User adds links from EditStationDialog's '+ Add sibling' button → two-step picker (provider → station). Per-chip × unlinks. Merges with AA URL-derived siblings in the 'Also on:' line on both EditStationDialog and NowPlayingPanel. ZIP export carries siblings by station name for cross-machine sync. Symmetric `station_siblings(a_id, b_id)` join table with `CHECK(a_id < b_id)`, `UNIQUE`, `ON DELETE CASCADE`.

### Cover-Art Sources (ART-MB)

Per-station MusicBrainz + Cover Art Archive lookup as an additive complement to the existing iTunes path. Three modes (`auto` / `itunes_only` / `mb_only`) selectable per station; default `auto` means iTunes-first with MB fallback on miss. Protocol-locked User-Agent + 1 req/sec rate gate + Lucene-escaped recording search + Official/Album release selection + ZIP round-trip. Source-grep gates (ART-MB-15/16) mirror the `feedback_gstreamer_mock_blind_spot.md` lesson — protocol-required literals must be testable at the source level.

- [ ] **ART-MB-01**: User-Agent header literal on MB API request matches `MusicStreamer/<version> (https://github.com/lightningjim/MusicStreamer)`
- [ ] **ART-MB-02**: User-Agent header literal on CAA image request
- [ ] **ART-MB-15**: Source-grep gate: literal `MusicStreamer/` AND `https://github.com/lightningjim/MusicStreamer` appear in cover_art_mb.py source
- [ ] **ART-MB-03**: 1 req/sec gate: 5 sequential MB calls span ≥ 4 seconds of monotonic clock
- [ ] **ART-MB-16**: Source-grep gate: gate actually references `time.monotonic` (not just a comment)
- [ ] **ART-MB-04**: Score=85 fixture accepted; score=79 rejected; bare-title ICY skips MB
- [ ] **ART-MB-05**: Release selection: Official+Album+earliest wins over Bootleg with same score
- [ ] **ART-MB-13**: MB tags → genre: highest-count tag wins; empty tags → genre=""
- [ ] **ART-MB-06**: Latest-wins queue: 5 rapid ICY arrivals → at most 1 wasted + 1 final
- [ ] **ART-MB-07**: MB-only mode: iTunes urlopen MUST NOT be called
- [ ] **ART-MB-08**: iTunes-only mode: MB urlopen MUST NOT be called
- [ ] **ART-MB-09**: Auto mode: iTunes miss → MB called → image shown via cover_art_ready signal
- [ ] **ART-MB-10**: Settings export ZIP round-trips `cover_art_source` field; old ZIPs default to 'auto'
- [ ] **ART-MB-11**: SQLite migration adds column with DEFAULT 'auto'; idempotent on re-run
- [ ] **ART-MB-12**: EditStationDialog selector reads + writes `station.cover_art_source`
- [ ] **ART-MB-14**: HTTP 503 from MB → callback(None), no raise out of worker

### Versioning Convention (VER)

Project-level convention introduced 2026-04-28.

- [x] **VER-01**: Adopt `milestone_major.milestone_minor.phase` versioning (e.g. `2.1.50` for Phase 50 of v2.1). The `pyproject.toml` `version` field is rewritten automatically on phase completion via a GSD-workflow hook, gated by a per-project config flag, and the convention is documented in PROJECT.md *(applies to all future phase completions starting Phase 51+; Phase 50 was bumped manually as the first instance)*
- [x] **VER-02**: The running app surfaces its current version (read from `pyproject.toml` via `importlib.metadata`) as a disabled informational entry at the bottom of the hamburger menu. The Windows PyInstaller bundle ships `musicstreamer.dist-info` so the bundled exe reads the same version dev sees. *(Phase 65 — consumes Phase 63's auto-bump output)*

### SomaFM Catalog Import (SOMA)

Bulk importer for the SomaFM public station catalog. Maps Phase 74 decisions D-01..D-16 and STRIDE mitigations T-74-01..T-74-05 to testable requirements pinned by RED unit tests in Plans 74-01..74-03.

- [ ] **SOMA-01**: Provider name pin — every imported SomaFM station has `provider_name = "SomaFM"` (CamelCase, no space, no period). Maps to CONTEXT D-02.
- [ ] **SOMA-02**: 4-tier × 5-relay stream scheme — each channel produces 20 stream rows whose `(codec, quality, bitrate_kbps)` tuples follow D-03's LOCKED map: `(MP3, hi, 128)` × 5 + `(AAC, hi2, 128)` × 5 + `(AAC, med, 64)` × 5 + `(AAC, low, 32)` × 5. Maps to CONTEXT D-03.
- [ ] **SOMA-03**: Position numbering — within each tier, `position = tier_base * 10 + relay_index` (`tier_base = {hi:1, hi2:2, med:3, low:4}`; `relay_index = 1..5`). Maps to CONTEXT D-03.
- [ ] **SOMA-04**: Codec normalization — format `"aacp"` stores codec field as `"AAC"` (NOT `"AAC+"`, NOT `"aacp"`). Maps to CONTEXT D-03 + Phase 69 WIN-05 closure + `stream_ordering._CODEC_RANK`.
- [ ] **SOMA-05**: PLS resolution before store — stored stream URLs are the direct `ice*.somafm.com` URLs returned by `playlist_parser.parse_playlist`, NOT the `.pls` URLs from the API response. Maps to T-74-03 mitigation.
- [ ] **SOMA-06**: Dedup-by-URL skip — if ANY of a fetched channel's resolved stream URLs match an existing station's stream URL (any provider), the whole channel is skipped. Maps to CONTEXT D-05 + D-09.
- [ ] **SOMA-07**: Full no-op on re-import — running the import a second time on an already-imported library results in `inserted=0, skipped=N`; no station/stream/logo updates fire. Maps to CONTEXT D-05.
- [ ] **SOMA-08**: Logo failure non-fatal — when the per-channel image GET fails, the station + streams stay inserted and `update_station_art` is NOT called. Maps to CONTEXT D-11 + T-74-04 mitigation.
- [ ] **SOMA-09**: Per-channel exception isolation — a malformed channel dict (KeyError, etc.) inside the catalog loop increments `skipped` and the import continues. Maps to CONTEXT D-15 + T-74-05 mitigation.
- [ ] **SOMA-10**: Hamburger entry — `MainWindow._menu` contains a top-level `"Import SomaFM"` action wired to a bound method (no lambda). Maps to CONTEXT D-06 + QA-05.
- [ ] **SOMA-11**: Toast verbatim strings — click toast `"Importing SomaFM…"` (U+2026), finished toast `"SomaFM import: {N} stations added"` or `"SomaFM import: no changes"`, error toast `"SomaFM import failed: {truncated}"` where truncation is `msg[:80] + "…"` when `len(msg) > 80`. Maps to CONTEXT D-06 + D-14.
- [ ] **SOMA-12**: Worker retention — clicking the menu action sets `MainWindow._soma_import_worker` to a non-None `_SomaImportWorker`; both `_on_soma_import_done` and `_on_soma_import_error` reset it to `None`. Maps to CONTEXT D-07 + Phase 60 SYNC-05.
- [ ] **SOMA-13**: User-Agent literal — outbound HTTP requests carry the literal UA `"MusicStreamer/{version} (https://github.com/lightningjim/MusicStreamer)"`. Maps to CONTEXT Discretion + Phase 73 protocol convention + T-74-01 mitigation.
- [ ] **SOMA-14**: Source-grep gate for UA — the literal `"MusicStreamer/"` AND `"https://github.com/lightningjim/MusicStreamer"` both appear in `musicstreamer/soma_import.py` source.
- [ ] **SOMA-15**: Source-grep gate against AAC+ literal — no STORED codec value equals `"AAC+"` inside `_TIER_BY_FORMAT_QUALITY` in `musicstreamer/soma_import.py`.
- [ ] **SOMA-16**: Logger registration — `musicstreamer/__main__.py` registers `musicstreamer.soma_import` at `logging.INFO`. Maps to CONTEXT D-16.
- [ ] **SOMA-17**: Network failure is a clean toast — `fetch_channels` raising `urllib.error.URLError`, `urllib.error.HTTPError`, `ValueError`, or `json.JSONDecodeError` surfaces as the error toast (D-14 full abort), NOT as a partial import. Maps to CONTEXT D-14.

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
| THEME-02 | Phase 75 | Complete |
| WIN-05 | Phase 69 | Complete |
| HRES-01 | Phase 70 | Complete |
| SIB-01 | Phase 71 | Complete |
| ART-MB-01 | Phase 73 | Pending |
| ART-MB-02 | Phase 73 | Pending |
| ART-MB-03 | Phase 73 | Pending |
| ART-MB-04 | Phase 73 | Pending |
| ART-MB-05 | Phase 73 | Pending |
| ART-MB-06 | Phase 73 | Pending |
| ART-MB-07 | Phase 73 | Pending |
| ART-MB-08 | Phase 73 | Pending |
| ART-MB-09 | Phase 73 | Pending |
| ART-MB-10 | Phase 73 | Pending |
| ART-MB-11 | Phase 73 | Pending |
| ART-MB-12 | Phase 73 | Pending |
| ART-MB-13 | Phase 73 | Pending |
| ART-MB-14 | Phase 73 | Pending |
| ART-MB-15 | Phase 73 | Pending |
| ART-MB-16 | Phase 73 | Pending |
| SOMA-01 | Phase 74 | Pending |
| SOMA-02 | Phase 74 | Pending |
| SOMA-03 | Phase 74 | Pending |
| SOMA-04 | Phase 74 | Pending |
| SOMA-05 | Phase 74 | Pending |
| SOMA-06 | Phase 74 | Pending |
| SOMA-07 | Phase 74 | Pending |
| SOMA-08 | Phase 74 | Pending |
| SOMA-09 | Phase 74 | Pending |
| SOMA-10 | Phase 74 | Pending |
| SOMA-11 | Phase 74 | Pending |
| SOMA-12 | Phase 74 | Pending |
| SOMA-13 | Phase 74 | Pending |
| SOMA-14 | Phase 74 | Pending |
| SOMA-15 | Phase 74 | Pending |
| SOMA-16 | Phase 74 | Pending |
| SOMA-17 | Phase 74 | Pending |
| BUG-10 | Phase 80 | Pending |

**Coverage:**
- v2.1 requirements: 56 total
- Mapped to phases: 56 ✓
- Unmapped: 0 ✓
- Complete: 20
- Pending: 36 (WIN-02 — SMTC Start Menu shortcut with AUMID; WIN-05 — AAC Win11 UAT; SOMA-01..SOMA-17 — Phase 74 in flight; BUG-10 — SQLite FK enforcement, Phase 80)

---
*Requirements defined: 2026-04-27 — milestone v2.1 Fixes and Tweaks (rolling)*
*Last updated: 2026-05-14 — BUG-10 (SQLite PRAGMA foreign_keys enforcement + orphan-sweep migration + regression test + drift-guard log + db.py header docs) added for Phase 80. Surfaced during Phase 74 Plan 07 UAT (F-07-03).*
