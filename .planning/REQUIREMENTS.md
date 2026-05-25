# Requirements: MusicStreamer v2.2 — Package Building and QOL features/tweaks

**Defined:** 2026-05-25
**Core Value:** Finding and playing a stream should take seconds — the right station should always be one or two clicks away.
**Milestone Goal:** Close packaging parity across Linux (AppImage + Flatpak) and Windows (SMTC AUMID + Win11 packaging UAT), and deliver a focused QOL polish pass across GBS.FM integration, SomaFM preroll consistency, ICY-disabled cover visuals, and Phase 77 test debt.

---

## v2.2 Requirements

Requirements for v2.2. Each maps to roadmap phases. IDs continue the existing categorical numbering (WIN-, ART-, SOMA-, FIX-, etc.).

### Linux Packaging — AppImage (PKG-LIN-APP)

- [ ] **PKG-LIN-APP-01**: User can download a single `MusicStreamer-<version>-x86_64.AppImage`, mark executable, and double-click to launch with no install step
- [ ] **PKG-LIN-APP-02**: AppImage runs on Ubuntu 22.04 LTS, Fedora 40, and openSUSE Tumbleweed (cross-distro target verified during build)
- [ ] **PKG-LIN-APP-03**: AppImage bundles GStreamer 1.28+ with `gst-libav`, `gst-plugins-base/good/bad/ugly` from the conda recipe (same plugin set as the Windows installer; AAC, MP3, AACP, PLS resolution all work)
- [ ] **PKG-LIN-APP-04**: AppImage bundles Node.js runtime so yt-dlp EJS solver resolves YouTube streams without requiring host Node installation
- [ ] **PKG-LIN-APP-05**: AppImage registers a `.desktop` entry (icon, name, MIME=audio) when run via AppImageLauncher; standalone execution still works without integration
- [ ] **PKG-LIN-APP-06**: AppImage embeds zsync update info pointing at the GitHub-releases-flavored host (via the QNAP→GitHub mirror) so future AppImageUpdate clients can find newer builds
- [ ] **PKG-LIN-APP-07**: AppImage's MPRIS2 D-Bus service is reachable from the host session — OS media keys control pause/resume/stop just like the conda-from-source run
- [ ] **PKG-LIN-APP-08**: AppImage's GLIBC baseline stays at GLIBC_2.35 or lower (Ubuntu 22.04 LTS baseline) verified by source-grep check in `tests/test_packaging_spec.py`
- [ ] **PKG-LIN-APP-09**: AppImage build does NOT register MIME associations for `.pls` / `.m3u` (curated-library identity — playlist files are import inputs, not user-facing files)

### Linux Packaging — Flatpak (PKG-LIN-FP)

- [ ] **PKG-LIN-FP-01**: Flatpak app ID is **`io.github.kcreasey.MusicStreamer`** (locked at first manifest commit; reverse-DNS conformant; matches the public GitHub mirror namespace)
- [ ] **PKG-LIN-FP-02**: User can install via `flatpak install --user io.github.kcreasey.MusicStreamer.flatpak` and launch via GNOME Software or `flatpak run`
- [ ] **PKG-LIN-FP-03**: Flatpak uses `org.kde.Platform//6.8` + `org.kde.Sdk//6.8` + `io.qt.PySide.BaseApp//6.8` + `org.freedesktop.Platform.ffmpeg-full//24.08` + `org.freedesktop.Sdk.Extension.node20`
- [ ] **PKG-LIN-FP-04**: Flatpak finish-args expose: `--share=network`, `--socket=pulseaudio`, `--socket=wayland`, `--socket=fallback-x11`, `--own-name=org.mpris.MediaPlayer2.MusicStreamer` — explicitly NOT `--filesystem=home` and NOT `--socket=session-bus` (broadly)
- [ ] **PKG-LIN-FP-05**: Flatpak's QtWebEngine GBS-FM login flow works inside the sandbox via `QTWEBENGINE_DISABLE_SANDBOX=1` env-var in `finish-args` (verbatim spelling per Flathub `io.qt.qtwebengine.BaseApp` manifest)
- [ ] **PKG-LIN-FP-06**: Flatpak's first launch detects existing unsandboxed data at `~/.local/share/musicstreamer/` and offers an in-app import wizard using the existing Phase 25 settings-export ZIP flow (no broad filesystem permission)
- [ ] **PKG-LIN-FP-07**: Flatpak ships AAC stream playback working (DI.fm, AudioAddict, SomaFM AAC tiers) via the `ffmpeg-full` extension — verified by audible playback during UAT
- [ ] **PKG-LIN-FP-08**: Flatpak's MPRIS2 binding is verified from inside the sandbox AFTER FIX-MPRIS lands (FIX-MPRIS-01 blocks PKG-LIN-FP-08 acceptance)
- [ ] **PKG-LIN-FP-09**: `flatpak-pip-generator` outputs a checked-in `python3-modules.yaml` capturing all `pyproject.toml` dependencies for offline Flathub builds
- [ ] **PKG-LIN-FP-10**: Flatpak appstream metainfo XML passes `appstreamcli validate` and `.desktop` entry passes `desktop-file-validate` (Flathub mandatory pre-flight)

### Windows Packaging Polish (WIN bundle — single Win11 VM session)

- [ ] **WIN-02**: User's Start-Menu shortcut has AppUserModelID baked in via Inno Setup `[Icons]` directive, so SMTC media controls bind correctly (carry-over from v2.1)
- [ ] **WIN-02-A**: Inno Setup `[InstallDelete]` clause removes the previous version's `.lnk` before creating the new one (avoid taskbar-pinned AUMID staleness; document "unpin from taskbar before upgrading" in release notes)
- [ ] **WIN-02-B**: `tests/test_aumid_string_parity.py` is extended to grep the installed `.lnk` AUMID and assert identity with `SetCurrentProcessExplicitAppUserModelID` literal
- [ ] **VER-02-J**: Win11 VM packaging UAT — fresh install of v2.2 installer on a Win11 VM that had v2.1 previously installed, all golden-path features verified (launch, station play, ICY metadata, media keys, AAC stream playback, cover art)
- [ ] **WIN-05**: AAC stream playback retest on Win11 — DI.fm + AudioAddict + SomaFM AAC tiers all play (Phase 69 acceptance re-confirmed on the v2.2 installer)

### GBS.FM — Themed-Day Detection (GBS-THEME)

- [ ] **GBS-THEME-01**: When a GBS.FM station is bound at session start, the app fetches `https://gbs.fm/images/logo_3.png` and SHA-256 hashes it against a known-baseline list of non-themed-day responses
- [ ] **GBS-THEME-02**: If the SHA-256 differs from the baseline AND the GBS marquee text matches one of a small keyword set (e.g., "da troops", "ho ho", "spooky"), the themed logo is applied for the session
- [ ] **GBS-THEME-03**: Themed logo replaces the canonical GBS.FM station logo in the now-playing logo slot ONLY (NEVER the cover slot; NEVER the station-list row)
- [ ] **GBS-THEME-04**: Themed-logo application is session-scoped — does not persist to the SQLite station record; resets to canonical logo on next app launch
- [ ] **GBS-THEME-05**: No libnotify toast, banner, or other notification fires when a themed day is detected — the themed logo IS the notification
- [ ] **GBS-THEME-06**: The baseline logo SHA-256 list is captured by a research-phase spike harvest of 3+ known themed-day responses and 5+ non-themed-day responses; the resulting hash table is committed as test fixture data

### GBS.FM — Announcement Banner (GBS-MARQ)

- [ ] **GBS-MARQ-01**: When a GBS.FM station is playing, the app polls the GBS marquee endpoint every 60 seconds; when GBS is bound but not playing, it polls every 5 minutes
- [ ] **GBS-MARQ-02**: The marquee response is split on the `|` (pipe) delimiter; the **first segment** is treated as the changeable announcement; subsequent segments are considered perpetual and ignored
- [ ] **GBS-MARQ-03**: A new top-of-NowPlayingPanel banner widget displays the first-segment announcement; banner is hidden by default and visible only when bound station is GBS.FM AND announcement is non-empty AND announcement-hash differs from last-seen
- [ ] **GBS-MARQ-04**: Banner displays the announcement with the `|` pipe boundaries preserved as wrap hints; long announcements wrap across multiple lines at pipe boundaries when present
- [ ] **GBS-MARQ-05**: User can dismiss the banner with an inline × button; dismissal stores the announcement-hash so the same banner doesn't re-appear until the marquee text changes
- [ ] **GBS-MARQ-06**: The marquee fetcher reuses Phase 76 GBS authenticated session cookies via shared `QWebEngineProfile` constants `GBS_WEB_PROFILE_NAME` + `GBS_WEB_STORAGE_PATH` in `musicstreamer/gbs_auth.py`; the marquee module imports these constants — does NOT construct a parallel session
- [ ] **GBS-MARQ-07**: The marquee parser is locked against a fixture of 10+ real GBS marquee samples committed under `tests/fixtures/gbs_marquee/` (per `feedback_mirror_decisions_cite_source.md` — quote samples, don't paraphrase the rule)

### GBS.FM — Zero-Token Single-Song Add (GBS-TOKEN)

- [ ] **GBS-TOKEN-01**: When the bound station is GBS.FM AND `tokens_available_count == 0` AND the user's queued-song count is 0, the now-playing panel renders an "Add a song" affordance (Phase 60.4 token-count state coupling)
- [ ] **GBS-TOKEN-02**: UI never uses the word "token" anywhere in the zero-token affordance label, tooltip, or surrounding text (per PROJECT.md milestone goal; honors that this is one-shot, not a token grant)
- [ ] **GBS-TOKEN-03**: Activating the affordance opens the existing GBS search-drill-down dialog (Phase 60.1/60.2); confirming a song calls `gbs_api.add_song_zero_token()` which posts to the GBS one-shot endpoint
- [ ] **GBS-TOKEN-04**: After a successful add, the affordance hides immediately and re-appears only when `tokens_available_count == 0 AND queue empty` again (i.e., after the queued song plays out)
- [ ] **GBS-TOKEN-05**: Backend exposes the zero-token endpoint spec via Phase 87 spike research (live observation of the GBS Settings page POST behavior when tokens==0); spec is fixture-locked in `tests/fixtures/gbs_zero_token/`

### Cover Art — Channel Avatar Fallback (ART-AVATAR)

- [ ] **ART-AVATAR-01**: `stations` table gains a `channel_avatar_path TEXT` column via idempotent additive migration in `repo.py:db_init()` (matches existing `station_art_path` pattern); existing rows default to NULL
- [ ] **ART-AVATAR-02**: New filesystem directory `~/.local/share/musicstreamer/assets/channel-avatars/` stores avatar PNGs keyed by station ID
- [ ] **ART-AVATAR-03**: For YouTube stations, `yt_import.fetch_channel_avatar(channel_url) -> bytes` returns a square channel-avatar image; filters `info.get('thumbnails', [])` for entries with `id == 'avatar_uncropped'` (preferred) or `id == 'avatar'`; rejects entries where `width != height`
- [ ] **ART-AVATAR-04**: For Twitch stations, `musicstreamer/twitch_helix.py` fetches the channel `profile_image_url` from `GET https://api.twitch.tv/helix/users?login=<x>` using the existing Phase 32 `twitch-token.txt` user token (no new OAuth scopes)
- [ ] **ART-AVATAR-05**: Avatar auto-fetches on URL paste in `EditStationDialog` (consistent with the Phase 6/17 YT thumbnail behavior) AND surfaces a "Refresh avatar" button for manual re-fetch on demand
- [ ] **ART-AVATAR-06**: When ICY metadata is disabled for a YT or Twitch station AND a channel avatar exists, the now-playing cover slot displays the channel avatar (circular crop) instead of duplicating the station thumbnail
- [ ] **ART-AVATAR-07**: When ICY metadata is enabled (any station, any provider), cover-resolver precedence stays **`ICY → iTunes → MB-CAA → channel-avatar → placeholder`** — channel-avatar fallback fires ONLY when ICY is empty/disabled; never short-circuits Phase 73 MB-CAA Vaporwave/niche-electronic coverage
- [ ] **ART-AVATAR-08**: Avatar load completes in under 1 second from station-bind (cached after first fetch); cover-slot reverts to current behavior (placeholder or station thumbnail) if avatar fetch fails
- [ ] **ART-AVATAR-09**: Source-grep drift-guard `test_cover_resolution_precedence` asserts `_mb_caa_lookup` appears in source BEFORE `_channel_avatar_lookup` (per `feedback_gstreamer_mock_blind_spot.md` lesson — source-level gates beat behavioral mocks)
- [ ] **ART-AVATAR-10**: Phase 71 sibling rendering parity preserved — new drift-guard `test_richtext_baseline_unchanged_by_phase_89` mirrors the existing Phase 71 baseline test

### SomaFM Preroll Consistency (SOMA-PRE)

- [ ] **SOMA-PRE-01**: New module `musicstreamer/preroll_log.py` mirrors `musicstreamer/buffer_log.py` (Phase 78 size-rotated structured event log); wires at `player.py:_try_next_stream` and `_on_preroll_about_to_finish` decision points with NO behavior change
- [ ] **SOMA-PRE-02**: Hamburger-menu gains "Open preroll log" entry mirroring the existing "Open buffer-events log" entry (Phase 78)
- [ ] **SOMA-PRE-03**: A new opt-in (hamburger-menu) "Probe SomaFM preroll" action runs a non-destructive `requests.get(stream_url, stream=True, headers={'Icy-MetaData': '1'})` for 30 seconds against the currently-bound SomaFM station and the 4 known-good baselines (Groove Salad, Drone Zone, Beat Blender, + one more); records to a separate `preroll-probe.log`
- [ ] **SOMA-PRE-04**: After 1-2 days of real listening, harvested log + probe data identify the root cause for at least one missing-preroll station (Boot Liquor target); conditional follow-up phase ships the fix if the root cause is clear and atomic
- [ ] **SOMA-PRE-05**: Instrumentation MUST NOT regress Phase 84 buffer adaptation — Phase 84 D-11 acceptance test (12-event harvest replay) re-runs clean before merge; source-grep drift-guard pins `_set_uri` order

### Phase 77 MPRIS2 Test Repair (FIX-MPRIS)

- [ ] **FIX-MPRIS-01**: Investigate the 7 D-03-deferred MPRIS2 cross-file test failures from Phase 77 — first plan runs `grep "class FakePlayer" tests/ | wc -l`; if > 1, the failure is structural (FakePlayer duplication) not environmental (dbus-daemon/PyGObject)
- [ ] **FIX-MPRIS-02**: All 7 failing tests pass cleanly via `uv run --with pytest pytest`; no test-runtime regressions in the 1462-test baseline; only `tests/_fake_player.py` declares `FakePlayer(QObject)` (Phase 77 D-04 convention preserved)
- [ ] **FIX-MPRIS-03**: Phase 77's `test_richtext_baseline_unchanged_by_phase_71` baseline drift-guard remains green; no source-introspection regressions

### Phase 58 PLS URL-Fallback (FIX-PLS)

- [ ] **FIX-PLS-01**: PLS auto-resolve gains URL-fallback for codec/bitrate detection — when the PLS title field lacks codec/bitrate info, the resolver inspects the resolved stream URL pattern (e.g., AudioAddict `_aac` / `_mp3` suffixes) to populate the missing fields; resolves the carry-over from pending todo `2026-05-10-pls-codec-bitrate-url-fallback`

### Conditional — Buffer Monitor Follow-Up (MON-BUFFER, CONDITIONAL)

- [ ] **MON-BUFFER-01** (CONDITIONAL): After 2 weeks of v2.2 development, if any of Phase 84-VERIFICATION.md's 3 Follow-Up Triggers fires (BUG-09 recurrence, statistical-gate signal change, user-reported drop-out), open a follow-up phase that takes one of: (a) adaptive-buffer regression diagnosis, (b) further state-machine tuning, (c) explicit "no action — closed" verification. Skips entirely if no Follow-Up Trigger fires.

---

## v2.3+ Requirements (Deferred)

Tracked but not in v2.2 roadmap.

### GBS.FM Polish

- **GBS-THEME-RETINT**: Auto-retint app accent color sampled from themed logo's dominant color via existing Phase 59 accent picker for the session. Deferred from v2.2 (P2 polish; logo-only is the v2.2 baseline)

### AppImage Update Infrastructure

- **PKG-LIN-APP-UPDATE**: zsync update server actually publishes release feeds matching the embedded URL — currently the URL is embedded but the host returns 404 between milestones. Deferred to a follow-on infra milestone.

### Flathub Submission

- **PKG-LIN-FP-FLATHUB**: Submit `io.github.kcreasey.MusicStreamer` manifest to Flathub for inclusion in the public store catalog. v2.2 ships a sideload-installable `.flatpak`; Flathub review process can take weeks and is gated on v2.2 closure.

---

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Snap packaging | User explicitly chose AppImage + Flatpak; Snap would be a third format with no additional reach |
| AppImage `.pls`/`.m3u` MIME associations | Conflicts with curated-library identity (PROJECT.md Out of Scope — Radio-Browser as primary browse mode is anti-feature) |
| Flatpak `--filesystem=home` permission | Flathub will reject or downgrade trust; first-launch import wizard (PKG-LIN-FP-06) is the alternative |
| Silent AppImage auto-update | AppImageUpdate convention is user-confirmed; never silent |
| Channel avatar in **logo** slot | Logo slot stays "station as curated by me" identity; avatar goes ONLY in cover slot (ART-AVATAR-06) |
| Channel avatar refresh on every play | YouTube avatars change ~never, Twitch ~monthly; one-time fetch + manual refresh is the model (ART-AVATAR-05) |
| Themed-day push notification / libnotify toast | The themed logo IS the notification (GBS-THEME-05) |
| Zero-token affordance always visible | Render is gated on `tokens==0 AND queue empty` (GBS-TOKEN-01) |
| GBS-FM marquee perpetual lines (positions 2+) | First pipe-segment only; perpetual lines are noise (GBS-MARQ-02) |
| pywin32 Python-side AUMID self-heal in v2.2 | Inno Setup directive is the canonical mechanism (WIN-02); pywin32 self-heal stays as a v2.3+ optional fallback |
| Building AppImage on Arch/Fedora-rawhide host | GLIBC baseline must be Ubuntu 22.04 LTS or older (PKG-LIN-APP-08); CI/build container is pinned |

---

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PKG-LIN-APP-01..09 | TBD | Pending |
| PKG-LIN-FP-01..10 | TBD | Pending |
| WIN-02, WIN-02-A, WIN-02-B, VER-02-J, WIN-05 | TBD | Pending |
| GBS-THEME-01..06 | TBD | Pending |
| GBS-MARQ-01..07 | TBD | Pending |
| GBS-TOKEN-01..05 | TBD | Pending |
| ART-AVATAR-01..10 | TBD | Pending |
| SOMA-PRE-01..05 | TBD | Pending |
| FIX-MPRIS-01..03 | TBD | Pending |
| FIX-PLS-01 | TBD | Pending |
| MON-BUFFER-01 (CONDITIONAL) | TBD | Pending |

**Coverage:**
- v2.2 requirements: 59 total (58 unconditional + 1 conditional)
- Mapped to phases: 0 (pending roadmap)
- Unmapped: 59 ⚠️

---

*Requirements defined: 2026-05-25*
*Last updated: 2026-05-25 — initial v2.2 definition after research synthesis*
