# Roadmap: MusicStreamer

## Milestones

- ✅ **v1.0 MVP** — Phases 1–4 (shipped 2024-03-20)
- ✅ **v1.1 Polish & Station Management** — Phases 5–6 (shipped 2024-03-21)
- ✅ **v1.2 Station UX & Polish** — Phases 7–11 (shipped 2024-03-25)
- ✅ **v1.3 Discovery & Favorites** — Phases 12–15 (shipped 2024-04-03)
- ✅ **v1.4 Media & Art Polish** — Phases 16–20 (shipped 2024-04-05)
- ✅ **v1.5 Further Polish** — Phases 21–34 (shipped 2026-04-10)
- ✅ **v2.0 OS-Agnostic Revamp** — Phases 35–48 (shipped 2026-04-25)
- ✅ **v2.1 Fixes and Tweaks** — Phases 49–84 (shipped 2026-05-25)
- 🚧 **v2.2 Package Building and QOL features/tweaks** — Phases 85–95 (planning, started 2026-05-25)

Earlier milestone details collapsed for brevity; full ROADMAPs preserved under `.planning/milestones/v{X.Y}-ROADMAP.md`.

---

## Current Milestone: v2.2 Package Building and QOL features/tweaks

**Created:** 2026-05-25
**Core Value:** Finding and playing a stream should take seconds — the right station should always be one or two clicks away.
**Milestone Goal:** Close packaging parity across Linux (AppImage + Flatpak) and Windows (SMTC AUMID + Win11 packaging UAT), and deliver a focused QOL polish pass across GBS.FM integration, SomaFM preroll consistency, ICY-disabled cover visuals, and Phase 77 test debt.
**Granularity:** standard (config.json)
**Phase numbering:** continues from v2.1 Phase 84; first v2.2 phase is Phase 85.

### Phases

- [ ] **Phase 85a: Linux Packaging Spike** — De-risk linuxdeploy + conda + GStreamer plugin discovery before locking the AppImage recipe
- [x] **Phase 91: FIX-MPRIS (Phase 77 deferred MPRIS2 tests)** — Repair the 7 D-03-deferred MPRIS2 cross-file test failures so the test-clean baseline holds before Flatpak in-sandbox MPRIS verification
- [ ] **Phase 85: Linux Common + AppImage Build** — Ship a portable `MusicStreamer-<version>-x86_64.AppImage` with conda's GStreamer/Qt/Node bundle, `.desktop` integration, MPRIS2, and zsync update metadata
- [ ] **Phase 86: Linux Flatpak Build** — Ship `io.github.kcreasey.MusicStreamer.flatpak` via `flatpak-builder` on KDE 6.8 + PySide BaseApp + ffmpeg-full, with minimal finish-args and in-sandbox MPRIS2 verified
- [ ] **Phase 88: Windows Packaging Bundle (WIN-02 + VER-02-J + WIN-05)** — One Win11 VM session: Inno Setup AUMID polish + `.lnk` cleanup, full v2.2-installer UAT against a previously-v2.1 VM, and AAC stream retest
- [ ] **Phase 89a: Channel-Avatar DB Migration + Storage Layout** — Foundation column + filesystem layout for YT and Twitch avatars; idempotent additive migration in `repo.py:db_init()`
- [ ] **Phase 87: GBS.FM Marquee + Themed-Day Detection** — Banner widget + themed-logo session swap; establishes the QtWebEngine cookie-persistence-cross-process pattern reused by Phase 89
- [ ] **Phase 89: YouTube Channel-Avatar Fetch + Cover-Slot Swap** — ICY-disabled YT stations show the channel avatar (circular) in the cover slot; cover-resolver precedence keeps MB-CAA above avatar
- [ ] **Phase 89b: Twitch Channel-Avatar Fetch** — Helix `/users` integration reusing the Phase 32 user token; shares storage + cover-slot path with Phase 89
- [ ] **Phase 87b: GBS Zero-Token Single-Song Add** — Conditional "Add a song" affordance gated on tokens==0 AND queue empty; UX never frames as "1 token"
- [ ] **Phase 90: SomaFM Preroll Instrumentation** — Size-rotated `preroll-events.log` + hamburger-menu probe; ship+monitor pattern, no behavior change
- [ ] **Phase 90b (CONDITIONAL): SomaFM Preroll Fix** — Fires only if Phase 90's harvest identifies a clear, atomic root cause for the Boot Liquor / missing-preroll target
- [ ] **Phase 92: FIX-PLS — PLS URL-Fallback for Codec/Bitrate** — Carry-over from Phase 58 pending-todo: detect codec/bitrate from resolved URL pattern when PLS title metadata is missing
- [ ] **Phase 93 (CONDITIONAL): BUFFER-MONITOR Follow-Up** — Fires only if any of Phase 84-VERIFICATION.md's 3 Follow-Up Triggers fires during v2.2 dev window
- [ ] **Phase 94: Sidebar Logo Thumbnail Optimization** — Investigate sidebar scroll slowdown on large lists (e.g., DI.fm); generate pre-scaled small logo variants for sidebar use while preserving full-res for Now Playing
- [ ] **Phase 95: YT URL-Change Replay Bug** — After editing a YT stream with a changed URL, first play fails with "stream exhausted"; replay picks up the new URL. Diagnose stale cached resolution post-edit, fix to invalidate on station update

### Phase Details

#### Phase 85a: Linux Packaging Spike

**Goal**: De-risk the linuxdeploy-plugin-conda + linuxdeploy-plugin-gstreamer toolchain before committing to the full Linux build recipe; produce a working hello-world AppImage that plays a remote MP3 stream on all three target distros.
**Depends on**: Nothing (Tier 1, parallel-eligible with Phase 91)
**Requirements**: (spike — no requirements consumed; outputs feed Phase 85)
**Success Criteria** (what must be TRUE):

  1. A hello-world Qt + GStreamer AppImage built in an Ubuntu 22.04 LTS Docker container launches and plays a remote MP3 stream on Ubuntu 22.04, Fedora 40, and openSUSE Tumbleweed (cross-distro empirical PASS).
  2. `strings AppRun_or_main_so | grep GLIBC_ | sort -V | tail -1` reports a GLIBC requirement of 2.35 or lower (Pitfall 1 mitigation verified).
  3. `linuxdeploy-plugin-gstreamer` against conda's `$CONDA_PREFIX/lib/gstreamer-1.0` produces an AppDir where `gst-inspect-1.0 avdec_aac` and `aacparse` both resolve from inside the AppRun shell (Pitfall 2 verified).
  4. Spike outcome document captures the AppRun env-var template (`GST_PLUGIN_SYSTEM_PATH_1_0`, `GST_PLUGIN_PATH_1_0`, `GST_PLUGIN_SCANNER`, `GST_REGISTRY_FORK=no`) ready for Phase 85 consumption.

**Plans**: 8 plans across 6 waves
- [x] 85A-01-PLAN.md — Host tooling install + environment manifest (Wave 0)
- [x] 85A-02-PLAN.md — Dockerfile + environment-spike.yml (Wave 1, parallel with 03)
- [x] 85A-03-PLAN.md — Toolchain SHA256 pins + verify-pins.sh drift-guard (Wave 1, parallel with 02)
- [x] 85A-04-PLAN.md — hello_world.py + AppRun template + smoke_test.py (Wave 2)
- [x] 85A-05-PLAN.md — build.sh end-to-end AppImage assembly (Wave 3)
- [x] 85A-06-PLAN.md — Distrobox scripts + per-distro programmatic smoke (Wave 4)
- [x] 85A-07-PLAN.md — Audible-PASS protocol per distro + screenshots (Wave 5, manual)
- [x] 85A-08-PLAN.md — SPIKE-FINDINGS.md + skill APPEND wrap-up + teardown (Wave 6)

**Research flag**: YES — `/gsd:plan-phase --research-phase 85a` recommended.

#### Phase 91: FIX-MPRIS (Phase 77 Deferred MPRIS2 Tests)

**Goal**: The 7 D-03-deferred MPRIS2 cross-file test failures from Phase 77 turn green, restoring the 100%-pass baseline before Flatpak in-sandbox MPRIS2 verification depends on it.
**Depends on**: Nothing (Tier 1, parallel-eligible with Phase 85a; tests-only, no production code dependency)
**Requirements**: FIX-MPRIS-01, FIX-MPRIS-02, FIX-MPRIS-03
**Success Criteria** (what must be TRUE):

  1. `grep -rnP '^\s*class\s+FakePlayer\s*\(\s*QObject\s*\)\s*:' tests/ | wc -l` returns exactly 1 and the only declaration site is `tests/_fake_player.py:37` (Pitfall 15 verified at source level; anchored to a real class declaration so the docstring literal in `tests/test_fake_player_no_inline.py:28` no longer false-positives — D-04).
  2. All 7 previously-deferred MPRIS2 cross-file tests pass via `uv run --with pytest pytest tests/test_media_keys_mpris2*.py`; no test-runtime regressions vs. the Phase 91 pre-phase baseline of 1838 passed (captured 2026-06-02); verification asserts passed >= 1838, never shrinkage.
  3. Phase 77's `test_richtext_baseline_unchanged_by_phase_71` drift-guard remains green; no source-introspection regressions introduced by the repair.

**Plans**: 1 plan, 1 wave
- [x] 91-01-PLAN.md — Bookkeeping close-out: verify Phase 77 MPRIS2 closure (378440c) holds, fix the miswritten SC1 grep to the anchored PCRE form, refresh the SC2 baseline, flip FIX-MPRIS-01/02/03 to Complete
**Research flag**: NO — pattern is well-established (Phase 77 D-04 + shared FakePlayer convention).

#### Phase 85: Linux Common + AppImage Build

**Goal**: Users can download a single `MusicStreamer-<version>-x86_64.AppImage`, mark executable, and run it portably on Ubuntu 22.04 LTS, Fedora 40, and openSUSE Tumbleweed with full audio, MPRIS2, and YouTube playback working out of the box.
**Depends on**: Phase 85a (spike outcome consumed: AppRun template + conda-plugin compatibility verified)
**Requirements**: PKG-LIN-APP-01, PKG-LIN-APP-02, PKG-LIN-APP-03, PKG-LIN-APP-04, PKG-LIN-APP-05, PKG-LIN-APP-06, PKG-LIN-APP-07, PKG-LIN-APP-08, PKG-LIN-APP-09, PKG-LIN-APP-10
**Success Criteria** (what must be TRUE):

  1. User downloads the AppImage, runs `chmod +x` and double-clicks; the app launches with no install step and plays a stream within seconds.
  2. The same AppImage launches and plays an AAC stream (DI.fm or SomaFM AAC tier) on Ubuntu 22.04 LTS, Fedora 40, and openSUSE Tumbleweed (cross-distro empirical PASS via the conda-bundled gst-libav).
  3. After running once via AppImageLauncher, a `.desktop` entry with icon and `MIME=audio` appears in the user's GNOME apps grid; standalone execution without AppImageLauncher still launches the app.
  4. OS media keys (play/pause/stop) control the AppImage's playback via MPRIS2 from the host session, and the Windows packaging drift-guards (`tools/check_bundle_plugins.py`, `tests/test_packaging_spec.py`) still pass after the Linux PR lands (Pitfall 16 mitigation).
  5. `tests/test_packaging_spec.py` source-grep checks confirm GLIBC baseline ≤ 2.35, no `.pls`/`.m3u` MIME associations registered, and zsync update info is embedded in the AppImage payload.

**Plans:** 4 plans across 3 waves
Plans:
**Wave 1**

- [x] 85-01-PLAN.md — environment.yml + build.sh refactor + production AppRun (D-01/D-02/D-03 single-source-of-truth bundle; Pitfalls 19/20)

**Wave 2** *(parallel; both depend on 85-01)*

- [x] 85-02-PLAN.md — GPG signing + zsync embedding + REQUIREMENTS PKG-LIN-APP-10 row (D-08/D-09/D-10/D-11/D-12)
- [x] 85-03-PLAN.md — .github/workflows/linux-appimage.yml workflow_dispatch CI scaffold (D-13/D-14/D-15/D-16)

**Wave 3** *(blocked on Waves 1+2)*

- [ ] 85-04-PLAN.md — Cross-distro smoke harness + Linux drift-guard pytest + README + REQUIREMENTS bookkeeping (D-04/D-05/D-06/D-07/D-17 + close)

**Research flag**: NO — spike consumed in Phase 85a; standard pattern in Phase 85.

#### Phase 86: Linux Flatpak Build

**Goal**: Users can install `io.github.kcreasey.MusicStreamer.flatpak` via `flatpak install --user` or sideload through GNOME Software, launch via Activities, and use the app with full audio + MPRIS2 + GBS.FM login working inside the sandbox.
**Depends on**: Phase 91 (FIX-MPRIS — Flatpak in-sandbox MPRIS2 verification of PKG-LIN-FP-08 requires the test baseline clean)
**Requirements**: PKG-LIN-FP-01, PKG-LIN-FP-02, PKG-LIN-FP-03, PKG-LIN-FP-04, PKG-LIN-FP-05, PKG-LIN-FP-06, PKG-LIN-FP-07, PKG-LIN-FP-08, PKG-LIN-FP-09, PKG-LIN-FP-10
**Success Criteria** (what must be TRUE):

  1. `flatpak install --user io.github.kcreasey.MusicStreamer.flatpak` succeeds against a clean sideload host; the app appears in GNOME Software and launches via `flatpak run`.
  2. Inside the sandbox, AAC streams (DI.fm, AudioAddict, SomaFM AAC tiers) play audibly via the `org.freedesktop.Platform.ffmpeg-full//24.08` extension (Phase 69 lesson re-applied to Linux).
  3. GBS.FM in-app login subprocess (Phase 76 QtWebEngine flow) completes without a namespace error and cookies persist across subprocess restart (Pitfall 4 mitigated via `QTWEBENGINE_DISABLE_SANDBOX=1` in finish-args, verbatim spelling per Flathub `io.qt.qtwebengine.BaseApp`).
  4. OS media keys via MPRIS2 control sandbox playback (`--own-name=org.mpris.MediaPlayer2.MusicStreamer`); no broad `--socket=session-bus` in the manifest.
  5. First launch on a host with existing `~/.local/share/musicstreamer/` offers the in-app import wizard (Phase 25 settings-export ZIP flow); manifest declares zero broad filesystem permissions; `appstreamcli validate` and `desktop-file-validate` both pass pre-flight.

**Plans**: 5 plans (3 waves)
- [x] 86-01-PLAN.md — Manifest + python3-modules.yaml + .desktop/metainfo artifacts (FP-01/03/04/05/09/10)
- [x] 86-02-PLAN.md — First-launch import wizard reusing Phase 25 ZIP flow (FP-06)
- [x] 86-03-PLAN.md — Manifest allow/deny-list + runtime-pin + validator + first-launch drift-guards (FP-01/03/04/05/06/08/09/10)
- [x] 86-04-PLAN.md — build.sh + workflow_dispatch CI + GPG signing + REQUIREMENTS signing row (FP-02/04/10/11)
- [ ] 86-05-PLAN.md — UAT evidence bundle: install/launch, AAC, GBS.FM login, MPRIS2 (FP-02/05/07/08)
**Research flag**: YES — `/gsd:plan-phase --research-phase 86` recommended (QtWebEngine sandbox-in-sandbox, BaseApp version pinning, Flathub policy nuances).

### Phase 86.1: SC5 failure followup from phase 86 (INSERTED)

**Goal:** Make the Flatpak first-launch import path correct and safe: the offered, consent-based, offer-once import wizard is the SOLE path by which unsandboxed host data enters the sandbox. Fix two coupled SC5 defects — (1) the wizard is never wired into startup, and (2) `migration.run_migration()` silently copies host secrets into the sandbox without consent because the :ro mount makes src != dest.
**Requirements**: PKG-LIN-FP-06
**Depends on:** Phase 86
**Plans:** 2 plans

Plans:
- [x] 86.1-01-PLAN.md — Add is_sandboxed() helper + make run_migration() sandbox-aware (skip auto-copy, keep marker/dest dir); secrets never copied without consent
- [x] 86.1-02-PLAN.md — Wire FlatpakImportWizard into _run_gui (gated on is_sandboxed AND should_offer, deferred via singleShot after window.show()); gate-logic tests

#### Phase 88: Windows Packaging Bundle (WIN-02 + VER-02-J + WIN-05)

**Goal**: One Win11 VM session delivers v2.2 installer parity: SMTC media controls bind correctly via Start Menu launch, old `.lnk` shortcuts get cleaned up on upgrade, full golden-path UAT signs off, and AAC streams retest clean.
**Depends on**: Nothing inside v2.2 (parallel-eligible with Tiers 1–2; carry-over from v2.1)
**Requirements**: WIN-02, WIN-02-A, WIN-02-B, VER-02-J, WIN-05
**Success Criteria** (what must be TRUE):

  1. After installing v2.2 from the new installer, the Start Menu `MusicStreamer.lnk` carries `AppUserModelID = org.lightningjim.MusicStreamer` (verified via `(New-Object -ComObject Shell.Application).Namespace(0).ParseName('shortcut.lnk').ExtendedProperty('System.AppUserModel.ID')`) and the SMTC overlay shows "MusicStreamer" (not "Unknown app") on play.
  2. Upgrading a Win11 VM that had v2.1 installed first to v2.2 deletes the old `.lnk` via Inno `[InstallDelete]` BEFORE creating the new one; release-notes "unpin from taskbar before upgrading" footnote documented (Pitfall 6).
  3. `tests/test_aumid_string_parity.py` greps the installed `.lnk`'s AUMID property and asserts identity with the `SetCurrentProcessExplicitAppUserModelID` literal in `__main__.py` plus the Inno `[Icons]` directive.
  4. Win11 VM full-UAT script (launch, station play, ICY metadata, media keys, AAC stream playback, cover art, MB-CAA fallback, GBS.FM, SomaFM preroll) signs off all golden-path checks.
  5. DI.fm + AudioAddict + SomaFM AAC tier streams play audibly on the v2.2 installer (Phase 69 WIN-05 acceptance re-confirmed; `tools/check_bundle_plugins.py` exit code 10 guard fires correctly on missing gst-libav rebuild).

**Plans**: 3 plans across 2 waves
Plans:
**Wave 1** *(parallel; disjoint files)*

- [x] 88-01-PLAN.md — Inno [InstallDelete] old-.lnk cleanup + RELEASE-NOTES.md taskbar-unpin footnote (WIN-02-A)
- [x] 88-02-PLAN.md — Static 3-way AUMID parity test + AAC plugin-guard regression assertions, Linux-CI runnable (WIN-02-B, WIN-05)

**Wave 2** *(blocked on Waves 1; human at Win11 VM)*

- [ ] 88-03-PLAN.md — Win11 VM UAT script: installed-.lnk AUMID readback + SMTC overlay + golden-path + audible AAC + exit-10 guard confirmation (WIN-02, VER-02-J, WIN-05)
**Research flag**: NO — spike-style first-plan (WPR trace + `Get-StartApps` PowerShell verification) lives inside the phase but no `--research-phase` needed.

#### Phase 89a: Channel-Avatar DB Migration + Storage Layout

**Goal**: Foundation for both YT and Twitch avatar work — additive SQLite column + filesystem layout in place, idempotent and rollback-safe, with zero behavior change.
**Depends on**: Nothing inside v2.2 (parallel-eligible; Phase 89/89b consume it)
**Requirements**: ART-AVATAR-01, ART-AVATAR-02
**Success Criteria** (what must be TRUE):

  1. After upgrade, `PRAGMA table_info(stations)` shows the new `channel_avatar_path TEXT` column with NULL default for all existing rows; existing data unchanged.
  2. Migration is idempotent — running `db_init()` twice does not raise; rollback test confirms reverting + re-applying produces identical schema.
  3. `~/.local/share/musicstreamer/assets/channel-avatars/` directory exists with appropriate permissions and layout matching the existing `assets/` station-logo precedent.

**Plans**: TBD
**Research flag**: NO — direct mirror of existing `station_art_path` / `album_fallback_path` migration pattern in `repo.py`.

#### Phase 87: GBS.FM Marquee + Themed-Day Detection

**Goal**: When the bound station is GBS.FM, the user sees the current themed logo (if any), a dismissible top-of-panel announcement banner, and a live updating marquee — all backed by the Phase 76 QtWebEngine cookie-persistence pattern that Phase 89 reuses for channel avatars.
**Depends on**: Nothing inside v2.2 (Phase 76 is the v2.1 keystone; this phase establishes the cookie-persistence pattern that Phase 89's cover-slot UI swap depends on)
**Requirements**: GBS-THEME-01, GBS-THEME-02, GBS-THEME-03, GBS-THEME-04, GBS-THEME-05, GBS-THEME-06, GBS-MARQ-01, GBS-MARQ-02, GBS-MARQ-03, GBS-MARQ-04, GBS-MARQ-05, GBS-MARQ-06, GBS-MARQ-07
**Success Criteria** (what must be TRUE):

  1. When the user binds a GBS.FM station on a known themed day (Halloween / Christmas / "da troops" / spooky / etc.), the now-playing logo slot displays the themed logo for the session — never the cover slot, never the station-list row, never a libnotify toast (GBS-THEME-05).
  2. Next app launch re-evaluates themed-day detection from scratch; the themed logo does NOT persist to SQLite or carry past a session boundary (GBS-THEME-04).
  3. When GBS.FM marquee text contains a new first pipe-segment announcement (hash-different from last-seen), a top-of-NowPlayingPanel banner appears with the announcement preserving `|` pipe wrap hints; user can dismiss with × and the same banner does not re-appear until the marquee changes.
  4. Marquee fetcher imports `paths.gbs_cookies_path()` + `musicstreamer.gbs_api.load_auth_context()`; source-grep drift-guard confirms no parallel cookie file is written and no QtWebEngine session is instantiated.
  5. 60-second poll cadence while GBS station bound + playing; 5-minute slow cadence otherwise; 10+ committed marquee fixtures plus 3+ themed-day / 5+ non-themed-day logo SHA-256 samples lock the parser and the canonical-hash table.

**Plans:** 6 plans
Plans:
**Wave 1**

- [x] 87-01-PLAN.md — Live themed-day fixture harvest (Memorial Day window) + REQUIREMENTS/ROADMAP D-07/D-08 edits

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 87-02-PLAN.md — Marquee endpoint lock + parse_marquee + synthetic fixture corpus (GBS-MARQ-02/07)

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 87-03-PLAN.md — GbsMarqueeWorker (QThread + cadence state machine + D-18 quiet-failure log sink, GBS-MARQ-01)

**Wave 4** *(blocked on Wave 3 completion)*

- [ ] 87-04-PLAN.md — Themed-day correlator + logo slot override + MainWindow worker construction (GBS-THEME-01..05)

**Wave 5** *(blocked on Wave 4 completion)*

- [ ] 87-05-PLAN.md — AnnouncementBanner widget + dismissal-hash set + outer-VBox panel wrap (GBS-MARQ-03/04/05)

**Wave 6** *(blocked on Wave 5 completion)*

- [ ] 87-06-PLAN.md — Source-grep drift-guards + GBS-THEME-06 follow-up todo (GBS-MARQ-06 enforce, GBS-THEME-06 accrete)

**Research flag**: YES — `/gsd:plan-phase --research-phase 87` recommended (QtWebEngine cookie persistence cross-process, marquee delimiter ambiguity, themed-day hash baseline harvest).
**UI hint**: yes

#### Phase 89: YouTube Channel-Avatar Fetch + Cover-Slot Swap

**Goal**: ICY-disabled YouTube stations (e.g., Lofi Girl) show the channel avatar (circular crop) in the cover slot instead of duplicating the station thumbnail; cover-resolver precedence keeps Phase 73 MB-CAA above the new avatar fallback.
**Depends on**: Phase 89a (DB migration + storage layout), Phase 87 (QtWebEngine cookie-persistence pattern established for cover-slot UI swap)
**Requirements**: ART-AVATAR-03, ART-AVATAR-05, ART-AVATAR-06, ART-AVATAR-07, ART-AVATAR-08, ART-AVATAR-09, ART-AVATAR-10
**Success Criteria** (what must be TRUE):

  1. When the user pastes a YouTube channel/video URL into `EditStationDialog`, `yt_import.fetch_channel_avatar()` populates a square channel avatar (filtered to `thumbnails[].id == 'avatar_uncropped'` or `'avatar'`, rejecting `width != height` entries) within 1 second of station-bind on a cached station (Pitfall 7 mitigated).
  2. When ICY metadata is disabled for a YT station with a stored channel avatar, the now-playing cover slot displays the avatar with circular crop instead of duplicating the station thumbnail; failure-to-fetch falls back cleanly to placeholder or station thumbnail (Pitfall 8 mitigated).
  3. Cover-resolver source order is `ICY → iTunes → MB-CAA → channel-avatar → placeholder`; source-grep drift-guard `test_cover_resolution_precedence::test_mb_caa_runs_before_channel_avatar` confirms `_mb_caa_lookup` appears in source before `_channel_avatar_lookup` (Pitfall 8 / Vaporwave-niche-electronic coverage preserved).
  4. Phase 71 sibling-line rendering parity preserved — drift-guard `test_richtext_baseline_unchanged_by_phase_89` mirrors the existing Phase 71 baseline test (Pitfall 13 mitigated).
  5. `EditStationDialog` surfaces a "Refresh avatar" button so the user can manually re-fetch after a channel rebrand; auto-fetch on URL paste matches the Phase 6/17 YT-thumbnail UX precedent.

**Plans**: TBD
**Research flag**: YES — `/gsd:plan-phase --research-phase 89` recommended (yt-dlp channel-avatar field stability spike, sibling-rendering regression risk).
**UI hint**: yes

#### Phase 89b: Twitch Channel-Avatar Fetch

**Goal**: ICY-disabled Twitch stations show the streamer's Helix `profile_image_url` (circular crop) in the cover slot, sharing the Phase 89 cover-slot integration and the Phase 89a storage layout.
**Depends on**: Phase 89a (DB migration + storage layout), Phase 89 (cover-slot UI swap path)
**Requirements**: ART-AVATAR-04
**Success Criteria** (what must be TRUE):

  1. `musicstreamer/twitch_helix.py` calls `GET https://api.twitch.tv/helix/users?login=<x>` with the existing Phase 32 `twitch-token.txt` user token (no new OAuth scopes) and stores `profile_image_url` bytes to `~/.local/share/musicstreamer/assets/channel-avatars/<station-id>.png`.
  2. When a Twitch station has ICY disabled and a stored Twitch avatar, the cover slot displays the avatar via the same circular-crop path as Phase 89 (zero new UI code; integration is a per-provider auto-fetch trigger only).
  3. Helix rate-limit budget is preserved — avatar fetched once per station-create/edit, then cached indefinitely with a manual "Refresh avatar" affordance (no per-play refresh).

**Plans**: TBD
**Research flag**: NO — Helix `/users` is a single GET, pattern is well-established in `aa_live.py` and elsewhere.

#### Phase 87b: GBS Zero-Token Single-Song Add

**Goal**: When the bound GBS.FM station has `tokens_available_count == 0` AND the queued-song count is 0, the now-playing panel renders an "Add a song" affordance that the user can activate to add exactly one song via the GBS zero-token endpoint. UX never frames the action as "1 token".
**Depends on**: Phase 87 (token-count state coupling + GBS marquee infrastructure)
**Requirements**: GBS-TOKEN-01, GBS-TOKEN-02, GBS-TOKEN-03, GBS-TOKEN-04, GBS-TOKEN-05
**Success Criteria** (what must be TRUE):

  1. Affordance renders only when `provider_name == "GBS.FM"` AND `tokens_available_count == 0` AND queued-song count is 0; in all other states it is hidden.
  2. UI text (label, tooltip, surrounding copy) never contains the word "token" — source-grep test on the new module enforces this; recommended wording is "Add a song".
  3. Activating the affordance opens the existing Phase 60.1/60.2 GBS search-drill-down dialog; confirming a song calls `gbs_api.add_song_zero_token()` which posts to the GBS one-shot endpoint observed via Phase 87 spike research.
  4. After a successful add, the affordance hides immediately and re-appears only when `tokens==0 AND queue empty` again (i.e., after the queued song plays out).
  5. Zero-token endpoint spec is fixture-locked in `tests/fixtures/gbs_zero_token/` (per `feedback_mirror_decisions_cite_source.md` — quote the GBS Settings page POST behavior, don't paraphrase).

**Plans**: TBD
**Research flag**: NO — research happens inside Phase 87 spike; Phase 87b consumes it.
**UI hint**: yes

#### Phase 90: SomaFM Preroll Instrumentation

**Goal**: Wire a non-destructive structured event log + opt-in probe through `player.py:_try_next_stream` and `_on_preroll_about_to_finish` so 1-2 days of real listening identifies why Boot Liquor and similar stations miss prerolls that Groove Salad / Drone Zone / Beat Blender consistently receive.
**Depends on**: Nothing inside v2.2 (parallel-eligible; carry-over investigation)
**Requirements**: SOMA-PRE-01, SOMA-PRE-02, SOMA-PRE-03, SOMA-PRE-04, SOMA-PRE-05
**Success Criteria** (what must be TRUE):

  1. New `musicstreamer/preroll_log.py` writes size-rotated structured events (`preroll_start`, `preroll_skipped_throttle`, `preroll_skipped_empty`, `preroll_handoff_complete`, `preroll_error`) to `~/.local/share/musicstreamer/preroll-events.log`; hamburger-menu "Open preroll log" mirrors the Phase 78 buffer-events log entry.
  2. Instrumentation adds at decision-point boundaries in `player.py` with zero behavior change; Phase 84 D-11 acceptance test (12-event harvest replay) re-runs clean before merge (Pitfall 12 mitigated).
  3. Opt-in "Probe SomaFM preroll" hamburger-menu action performs `requests.get(stream_url, stream=True, headers={'Icy-MetaData': '1'})` for 30 seconds against the current SomaFM station + 4 known-good baselines (Groove Salad, Drone Zone, Beat Blender, + one more); never spawns a second `playbin3` pipeline (Pitfall 11 mitigated).
  4. Source-grep drift-guard pins `_set_uri` ordering in `_try_next_stream` after any stage-and-apply marker (Phase 84 buffer adaptation regression-proof).
  5. After 1-2 days of real-listening harvest, log + probe data identify the root cause for at least one missing-preroll station (Boot Liquor target); conditional Phase 90b decision criteria documented (atomic catalog gap vs. throttle-window leakage vs. "no signal — closed").

**Plans**: TBD
**Research flag**: NO — Phase 78/84 ship+monitor pattern is the established template.

#### Phase 90b (CONDITIONAL): SomaFM Preroll Fix

**Goal**: Ship the fix Phase 90's harvest identified — only if the root cause is clear, atomic, and within the v2.2 dev window.
**Depends on**: Phase 90 (harvest data — fires only if root cause clear)
**Requirements**: (closes the SOMA-PRE-04 trigger half; no requirements unique to this phase)
**Success Criteria** (what must be TRUE):

  1. The fix targets exactly one root cause from Phase 90's hypothesis space (catalog gap, stream-URL pattern mismatch, `_preroll_in_flight` flag race, 10-minute throttle window cross-station leakage) — never speculative multi-cause refactor.
  2. After the fix, the target station (Boot Liquor) plays a preroll on bind via the same harvest probe that previously logged the miss; Groove Salad / Drone Zone / Beat Blender continue to play prerolls (no regression).
  3. Phase 90 instrumentation remains in place post-fix for at least one further monitor week so a re-occurrence would surface.

**Plans**: TBD
**Research flag**: NO — fix scope is constrained by the harvest data.
**Condition**: Fires only if Phase 90's harvest identifies a clear, atomic root cause for at least one missing-preroll station per SOMA-PRE-04 criterion.

#### Phase 92: FIX-PLS — PLS URL-Fallback for Codec/Bitrate

**Goal**: When a PLS file's title field lacks codec/bitrate info, the resolver inspects the resolved stream URL pattern (e.g., AudioAddict `_aac` / `_mp3` suffixes) to populate the missing fields — closing the Phase 58 pending-todo carry-over.
**Depends on**: Nothing inside v2.2 (small, slot-in any week)
**Requirements**: FIX-PLS-01
**Success Criteria** (what must be TRUE):

  1. When `pls.resolve()` returns a stream with empty codec/bitrate AND the resolved URL contains a recognized suffix (`_aac`, `_mp3`, `_aacp`, etc.), the resolver populates the missing fields from the URL pattern; existing PLS-title-derived metadata still wins when present.
  2. AudioAddict + Radio-Browser + other PLS-sourced stations that previously had blank codec/bitrate now show populated values in `station_streams` after a re-import or refresh.
  3. Stream-ordering correctness (`stream_ordering._CODEC_RANK`) is preserved — codec rank still wins over bitrate, lossless stays above lossy.

**Plans**: TBD
**Research flag**: NO — direct extension of Phase 58 logic.

#### Phase 93 (CONDITIONAL): BUFFER-MONITOR Follow-Up

**Goal**: Resolve any of Phase 84-VERIFICATION.md's 3 Follow-Up Triggers that fire during the v2.2 development window — diagnose, tune, or formally close as "no action".
**Depends on**: Phase 84 (v2.1) — fires only on trigger
**Requirements**: MON-BUFFER-01
**Success Criteria** (what must be TRUE):

  1. Which of the 3 Follow-Up Triggers (BUG-09 recurrence, statistical-gate signal change, user-reported drop-out) fired is documented with timestamps + observed evidence; non-fired triggers are explicitly noted as "no action required".
  2. Phase outcome is one of: (a) adaptive-buffer regression diagnosis + fix, (b) further state-machine tuning of the 30→60→120s growth ladder, (c) explicit "no action — closed" verification with evidence.
  3. If a fix ships, Phase 84 D-11 acceptance test (12-event harvest replay) re-runs clean post-fix; if "no action — closed", the buffer-events.log monitor concludes with the documented baseline preserved.

**Plans**: TBD
**Research flag**: NO — Phase 84 closure record + 84-VERIFICATION.md are the canonical reference.
**Condition**: Fires only if any of Phase 84-VERIFICATION.md's 3 Follow-Up Triggers fires during the v2.2 dev window. Skips entirely otherwise.

### Progress Table (v2.2)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 85a. Linux Packaging Spike | 8/8 | Complete    | 2026-05-26 |
| 91. FIX-MPRIS | 1/1 | Complete | 2026-06-02 |
| 85. Linux Common + AppImage Build | 3/4 | In Progress|  |
| 86. Linux Flatpak Build | 4/5 | In Progress|  |
| 88. Windows Packaging Bundle | 2/3 | In Progress|  |
| 89a. Channel-Avatar DB Migration | 0/? | Not started | - |
| 87. GBS Marquee + Themed-Day | 1/6 | In Progress|  |
| 89. YT Channel-Avatar | 0/? | Not started | - |
| 89b. Twitch Channel-Avatar | 0/? | Not started | - |
| 87b. GBS Zero-Token Add | 0/? | Not started | - |
| 90. SomaFM Preroll Instrumentation | 0/? | Not started | - |
| 90b. SomaFM Preroll Fix (CONDITIONAL) | 0/? | Not started | - |
| 92. FIX-PLS | 0/? | Not started | - |
| 93. BUFFER-MONITOR (CONDITIONAL) | 0/? | Not started | - |
| 94. Sidebar Logo Thumbnail Optimization | 0/? | Not started | - |
| 95. YT URL-Change Replay Bug | 0/? | Not started | - |

### Dependency Graph (Tier Summary)

```
Tier 1 (parallel-eligible, Week 1):
  Phase 85a (Linux Spike)  ────┐
  Phase 91 (FIX-MPRIS)     ────┤
                                │
Tier 2 (sequential, Weeks 2-3): │
  Phase 85a ──> Phase 85 (Linux Common + AppImage)
  Phase 91  ──> Phase 86 (Linux Flatpak — needs MPRIS baseline clean)

Tier 3 (Week 4, one Win11 VM session):
  Phase 88 (Windows Bundle — parallel-eligible w/ Tiers 1-2)

Tier 4 (Week 5+, channel-avatar infrastructure):
  Phase 89a (DB Migration) ──> Phase 89 (YT Avatar) ──> Phase 89b (Twitch Avatar)
                                  ▲
                                  └── Phase 87 also precedes Phase 89 (cookie-persistence pattern)

Tier 5 (Week 6, GBS polish):
  Phase 87 (GBS Marquee/Themed) ──> Phase 87b (Zero-Token Add)

Tier 6 (Week 7, SomaFM):
  Phase 90 (Preroll Instrumentation) ──> Phase 90b (CONDITIONAL Fix)

Tier 7 (carry-overs, slot-in):
  Phase 92 (FIX-PLS) — independent
  Phase 93 (CONDITIONAL BUFFER-MONITOR) — trigger-gated
```

### Coverage Summary (v2.2)

| Requirement Family | Count | Phase Assignment |
|--------------------|-------|------------------|
| PKG-LIN-APP (AppImage) | 9 | Phase 85 |
| PKG-LIN-FP (Flatpak) | 10 | Phase 86 |
| WIN bundle (WIN-02 + variants + VER-02-J + WIN-05) | 5 | Phase 88 |
| GBS-THEME | 6 | Phase 87 |
| GBS-MARQ | 7 | Phase 87 |
| GBS-TOKEN | 5 | Phase 87b |
| ART-AVATAR | 10 | Phase 89a (01–02), Phase 89 (03, 05–10), Phase 89b (04) |
| SOMA-PRE | 5 | Phase 90 |
| FIX-MPRIS | 3 | Phase 91 |
| FIX-PLS | 1 | Phase 92 |
| MON-BUFFER (CONDITIONAL) | 1 | Phase 93 |

**Total v2.2 requirements:** 62 (61 unconditional + 1 conditional)
**Mapped:** 62/62 ✓
**Orphans:** 0 ✓
**Double-mapped:** 0 ✓

### Phase 94: Optimize sidebar logo loading with pre-scaled thumbnails for large station lists

**Goal:** [To be planned]
**Requirements**: TBD
**Depends on:** Phase 92
**Plans:** 0 plans

Plans:

- [ ] TBD (run /gsd-plan-phase 94 to break down)

### Phase 95: YT URL-change replay bug: post-edit 'stream exhausted' on first play, second play picks up new URL

**Goal:** [To be planned]
**Requirements**: TBD
**Depends on:** Phase 94
**Plans:** 0 plans

Plans:

- [ ] TBD (run /gsd-plan-phase 95 to break down)

---

## Historical Phases (Collapsed)

<details>
<summary>✅ v1.0 MVP (Phases 1–4) — SHIPPED 2024-03-20</summary>

- [x] Phase 1: Module Extraction (3/3 plans) — completed 2024-03-18
- [x] Phase 2: Search and Filter (2/2 plans) — completed 2024-03-19
- [x] Phase 3: ICY Metadata Display (2/2 plans) — completed 2024-03-20
- [x] Phase 4: Cover Art (1/1 plan) — completed 2024-03-20

Full details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

<details>
<summary>✅ v1.1 Polish & Station Management (Phases 5–6) — SHIPPED 2024-03-21</summary>

- [x] Phase 5: Display Polish (2/2 plans) — completed 2024-03-21
- [x] Phase 6: Station Management (2/2 plans) — completed 2024-03-21

Full details: `.planning/milestones/v1.1-ROADMAP.md`

</details>

<details>
<summary>✅ v1.2 Station UX & Polish (Phases 7–11) — SHIPPED 2024-03-25</summary>

- [x] Phase 7: Station List Restructuring (3/3 plans) — completed 2024-03-22
- [x] Phase 8: Filter Bar Multi-Select (2/2 plans) — completed 2024-03-22
- [x] Phase 9: Station Editor Improvements (2/2 plans) — completed 2024-03-23
- [x] Phase 10: Now Playing & Audio (2/2 plans) — completed 2024-03-24
- [x] Phase 11: UI Polish (1/1 plan) — completed 2024-03-25

Full details: `.planning/milestones/v1.2-ROADMAP.md`

</details>

<details>
<summary>✅ v1.3 Discovery & Favorites (Phases 12–15) — SHIPPED 2024-04-03</summary>

- [x] Phase 12: Favorites (2/2 plans) — completed 2024-03-31
- [x] Phase 13: Radio-Browser Discovery (2/2 plans) — completed 2024-04-01
- [x] Phase 14: YouTube Playlist Import (2/2 plans) — completed 2024-04-02
- [x] Phase 15: AudioAddict Import (2/2 plans) — completed 2024-04-03

Full details: `.planning/milestones/v1.3-ROADMAP.md`

</details>

<details>
<summary>✅ v1.4 Media & Art Polish (Phases 16–20) — SHIPPED 2024-04-05</summary>

- [x] Phase 16: GStreamer Buffer Tuning (1/1 plan) — completed 2024-04-03
- [x] Phase 17: AudioAddict Station Art (2/2 plans) — completed 2024-04-03
- [x] Phase 18: YouTube Thumbnail 16:9 (1/1 plan) — completed 2024-04-05
- [x] Phase 19: Custom Accent Color (2/2 plans) — completed 2024-04-05
- [x] Phase 20: Playback Controls & Media Keys (2/2 plans) — completed 2024-04-05

Full details: `.planning/milestones/v1.4-ROADMAP.md`

</details>

<details>
<summary>✅ v1.5 Further Polish (Phases 21–34) — SHIPPED 2026-04-10</summary>

- [x] Phase 21: Panel Layout Fix (1/1 plan) — completed 2026-04-10
- [x] Phase 22: Import YT Cookies (3/3 plans) — completed 2026-04-07
- [x] Phase 23: Fix YT Playback (cookies) (1/1 plan) — completed 2026-04-07
- [x] Phase 24: Tag Chip FlowBox (1/1 plan) — completed 2026-04-08
- [x] Phase 25: Filter Chip Overflow (1/1 plan) — completed 2026-04-08
- [x] Phase 26: Edit Button Fix (1/1 plan) — completed 2026-04-08
- [x] Phase 27: Multi-Stream Model (3/3 plans) — completed 2026-04-08
- [x] Phase 28: Stream Failover (2/2 plans) — completed 2026-04-09
- [x] Phase 29: Hamburger Menu Consolidation (1/1 plan) — completed 2026-04-09
- [x] Phase 30: Elapsed Time Counter (1/1 plan) — completed 2026-04-09
- [x] Phase 31: Twitch via Streamlink (2/2 plans) — completed 2026-04-09
- [x] Phase 32: Twitch OAuth Token (2/2 plans) — completed 2026-04-10
- [x] Phase 33: YT 15s Wait + Toast (2/2 plans) — completed 2026-04-10
- [x] Phase 34: Deferred Items from Phase 33 (1/1 plan) — completed 2026-04-10

Full details: `.planning/milestones/v1.5-ROADMAP.md`

</details>

<details>
<summary>✅ v2.0 OS-Agnostic Revamp (Phases 35–48) — SHIPPED 2026-04-25</summary>

Full details: `.planning/milestones/v2.0-ROADMAP.md`
Audit: `.planning/milestones/v2.0-MILESTONE-AUDIT.md`

</details>

<details>
<summary>✅ v2.1 Fixes and Tweaks (Phases 49–84) — SHIPPED 2026-05-25</summary>

Full details: `.planning/milestones/v2.1-ROADMAP.md`
Audit: `.planning/milestones/v2.1-MILESTONE-AUDIT.md`
Phase directories: `.planning/milestones/v2.1-phases/`

</details>

## Backlog

(Items deferred during v2.1, awaiting promotion via `/gsd:review-backlog` if/when scope opens.)
