# Project Research Summary

**Project:** MusicStreamer v2.2 — Package Building and QOL features/tweaks
**Domain:** Personal GNOME desktop streaming app — packaging parity (Linux AppImage + Flatpak, Windows SMTC polish) + targeted QOL (GBS.FM themed-day/marquee/zero-token, ICY-disabled channel-avatar fallback, SomaFM preroll consistency, test-debt repair)
**Researched:** 2026-05-25
**Confidence:** HIGH

---

## Executive Summary

MusicStreamer v2.2 is a **maturation milestone** on top of a shipped v2.1 product (1462 passing tests, 42 phases, single-developer GNOME desktop streaming app). The headline work splits into two orthogonal tracks: **(1) packaging parity** — Linux AppImage (SEED-009) and Linux Flatpak as a second distro format, plus a Windows SMTC AUMID Start-Menu shortcut polish (WIN-02 carry-over) — and **(2) targeted QOL** — GBS.FM themed-day detection, marquee announcement banner, zero-token single-song add, ICY-disabled cover-slot replacement (YT/Twitch channel avatar), SomaFM preroll consistency debug, and Phase 77 MPRIS2 test-debt repair. Phase 76's QtWebEngine GBS login subprocess is the keystone for three of the six GBS-adjacent features; Phase 73's MB-CAA cover-art precedence chain is the keystone the new channel-avatar work must NOT short-circuit.

The **recommended approach** mirrors the conda-forge recipe the v2.1 Windows installer proved out (PKG-04 / Phase 43 / Phase 69 lessons): use `linuxdeploy` + `linuxdeploy-plugin-conda` + `linuxdeploy-plugin-gstreamer` for the AppImage (one source-of-truth GStreamer recipe across Windows + Linux), and a parallel Flatpak track using `org.kde.Platform//6.8` + `io.qt.PySide.BaseApp//6.8` + `org.freedesktop.Platform.ffmpeg-full//24.08` (Flathub policy forbids conda — pip deps locked via `flatpak-pip-generator`). Windows AUMID work is **Inno-Setup-only** (extend the existing `MusicStreamer.iss` clause + parity test; pywin32 self-heal is optional fallback only). GBS marquee/themed-day work reuses the Phase 76 cookie subprocess via `http.cookiejar` export (no new deps). Channel-avatar work uses `yt-dlp`'s `thumbnails[].id == 'avatar_uncropped'` filter (NOT the top-level `thumbnail` field) and Twitch Helix `GET /helix/users?login=<x>` with the existing Phase 32 user token.

The **dominant risks** are all spike-first candidates rather than open architecture questions: (a) `linuxdeploy-plugin-gstreamer` + conda paths (GStreamer plugin discovery is empirically fragile across distros — Phase 43/69 found this is hostile on Windows already; Linux distro variance is worse); (b) Flatpak QtWebEngine sandbox-in-sandbox crash requiring `QTWEBENGINE_DISABLE_SANDBOX=1`; (c) AppImage GLIBC baseline pinning (build on Ubuntu 22.04 LTS in a Docker container, never on Arch/Fedora-rawhide); (d) yt-dlp channel-avatar field-name resolution; (e) SomaFM preroll root-cause space is wide (4 hypotheses) — instrument first, fix second, mirroring Phase 78/84 precedent. Pitfall research surfaced 16 concrete project-specific traps; pitfall 8 (channel-avatar precedence vs. MB-CAA) is the highest-stakes regression risk because it silently masks the Phase 73 coverage gap that motivated MB-CAA in the first place.

---

## Key Findings

### Recommended Stack

The v2.1 stack is intentionally **untouched**. v2.2 layers six new tools/libraries on top of the existing Python 3.11+ / PySide6 6.10 / GStreamer 1.28 / conda-forge / PyInstaller + Inno Setup / yt-dlp library API / `chardet>=5,<6` / `winrt-Windows.Media.*` baseline.

**Core technology additions (HIGH confidence — verified against linuxdeploy/Flathub/Microsoft/yt-dlp/Twitch official docs):**

- **`linuxdeploy` (continuous)** — AppDir assembly + binary-dep discovery. Canonical AppImage tool (KDE, Subsurface, FreeCAD, Krita ship via it). Replaces `appimagetool` for our complexity level.
- **`linuxdeploy-plugin-conda` (continuous)** — Lets the AppImage build consume the **same conda-forge recipe** the Windows installer uses. Eliminates the Linux-vs-Windows divergence-risk that produced WIN-05 (AAC on Windows) in Phase 69.
- **`linuxdeploy-plugin-gstreamer` (continuous, officially experimental)** — Bundles GStreamer plugin `.so` files + `gst-plugin-scanner` + installs AppRun env-var hook. Direct Linux analog of `packaging/windows/runtime_hook.py`. Budget time for manual `GSTREAMER_PLUGINS_DIR` override per Pitfall 2.
- **Flatpak base stack:** `org.kde.Platform//6.8` + `org.kde.Sdk//6.8` + `io.qt.PySide.BaseApp//6.8` + `org.freedesktop.Platform.ffmpeg-full//24.08` — KDE 6.8 is the Flathub LTS-track; BaseApp 6.8 cuts CI time from ~45 min to ~8 min vs. building PySide6 from source; ffmpeg-full extension is the Phase 69 lesson applied to Linux (without it, DI.fm/AudioAddict/SomaFM AAC streams silently fail inside the sandbox).
- **`pywin32 >= 308`** — `IShellLink` + `IPropertyStore` + `PKEY_AppUserModel_ID` for optional pywin32-based AUMID self-heal. **NOT** required for v2.2's primary path (Inno `AppUserModelID:` directive at `MusicStreamer.iss` line 71 is the canonical mechanism). Runtime fallback only.
- **`flatpak-pip-generator`** — Resolves `pip` deps into offline-buildable manifest fragments (Flathub builds run with no network). Run once per `pyproject.toml` dep change; output checked in.

**Supporting libraries (zero new runtime deps):**

- `http.cookiejar` (stdlib) — Bridges QtWebEngine's `QWebEngineCookieStore.cookieAdded` to Mozilla-format cookie files consumable by urllib. Reuses the v1.5 Phase 23 / v2.0 Phase 999.7 YouTube cookie idiom for the new GBS marquee path.
- `appstreamcli` + `desktop-file-validate` (system pkgs) — Pre-flight validation for the AppStream metainfo XML (Flathub mandatory) and `.desktop` launcher entry.

**Conflict resolution — AppImage build technology:** STACK and ARCHITECTURE concur on `linuxdeploy + conda-plugin` (rejecting `appimage-builder`, `python-appimage`, and a Linux PyInstaller spec). Rationale cited verbatim from both: single conda source-of-truth eliminates Windows-vs-Linux GStreamer plugin-set divergence (Phase 69 lesson).

See `.planning/research/STACK.md` for full version-compatibility matrix and per-feature integration plan.

### Expected Features

**Must have / table stakes (P1 — non-negotiable per PROJECT.md milestone goal):**

- AppImage that runs portably (`.desktop` integration, GStreamer + Qt + Node.js bundled, zsync update info embedded, no MIME associations for `.pls`/`.m3u`)
- Flatpak via minimal finish-args (`--share=network`, `--socket=pulseaudio`, `--socket=wayland` + `--socket=fallback-x11`, `--own-name=org.mpris.MediaPlayer2.MusicStreamer`, NOT `--filesystem=home`, NOT `--socket=session-bus` broadly)
- GBS.FM themed-day detection (session-scoped at GBS launch; logo_3.png SHA-256 hash drift + conservative marquee keyword sniff)
- GBS.FM announcement banner (first pipe-segment of marquee, dismissible, hash-gated so it doesn't re-appear until marquee text changes)
- GBS.FM zero-token affordance — **NEVER framed as "1 token"** (per PROJECT.md line 18); appears ONLY when `tokens==0 AND queue empty`
- Channel avatar in cover slot for ICY-disabled YT/Twitch (circular crop, <1s load, fallback-safe to current behavior)
- SomaFM preroll consistency fix (Boot Liquor etc. currently miss prerolls that Groove Salad/Drone Zone/Beat Blender have)
- Windows SMTC AUMID Start-Menu shortcut (WIN-02 carry-over)
- FIX-MPRIS — Phase 77's 7 D-03-deferred MPRIS2 cross-file test failures repaired
- VER-02-J + WIN-05 — Win11 VM packaging UAT bundled with the WIN-02 work into one Win11 VM session

**Should have / differentiator (P2 — capacity-permitting):**

- D-07 hicolor multi-resolution icon set (256/128/64/48/32)
- D-08 Flatpak with documented zero-filesystem-permissions (defensible Flathub review signal)
- FIX-PLS — Phase 58 PLS URL-fallback for codec/bitrate (carry-over pending todo)

**Defer / conditional (P3):**

- BUFFER-MONITOR — only if any of Phase 84-VERIFICATION.md's 3 Follow-Up Triggers fires
- AppImage zsync update server (release feed infrastructure) — embed URL field, defer actual update shipping

**Anti-features (must decline if requested):**

- Snap packaging (AF-02 — user explicitly chose AppImage + Flatpak)
- AppImage MIME associations for `.pls` / `.m3u` (AF-01)
- Flatpak `--filesystem=home` (AF-03 — Flathub will reject/downgrade trust)
- Themed-day push notification / libnotify toast (AF-05 — themed logo IS the notification)
- Channel avatar in **logo** slot (AF-08 — avatar goes ONLY in cover slot)
- Silent AppImage auto-update (AF-10)
- Channel avatar refresh on every play (AF-09)
- Zero-token affordance always visible (AF-07 — render gated on `tokens==0 AND queue empty`)

**Conflict resolution — feature scope ordering:** FEATURES and ARCHITECTURE recommend carry-overs first (FIX-MPRIS frees the test-clean baseline before larger work lands; Inno-only WIN-02 is independent) while ARCHITECTURE's 7-tier ordering puts Linux packaging spike before everything. Reconciled in the roadmap suggestion below: Tier 1 runs packaging spike + FIX-MPRIS in parallel so neither blocks the other.

See `.planning/research/FEATURES.md` for the full prioritization matrix.

### Architecture Approach

v2.2 is **integration architecture, not greenfield**. Every new feature has a named existing-phase pattern analog. The Player (single 2100-LOC `player.py`), NowPlayingPanel (2978-LOC `ui_qt/now_playing_panel.py`), and `repo.py` SQLite layer are the gravity wells; new modules attach at well-established Qt-signal + ThreadPoolExecutor boundaries.

**Major components (new + modified):**

1. **`packaging/linux/` tree** — Three subdirs (`common/`, `appimage/`, `flatpak/`) under existing `packaging/linux/` root. `common/build_bundle.sh` produces a flat dist tree both downstream pipelines consume. AppImage layers conda's full GStreamer/Python on top; Flatpak layers GNOME KDE SDK on top. **Conda for AppImage, GNOME-KDE SDK for Flatpak — NOT shared envs.** Flathub policy forbids conda.
2. **`musicstreamer/gbs_marquee.py` (NEW)** — Pure-Python marquee + themed-logo scraper. Exactly mirrors `aa_live.py` shape (Phase 68 pattern). `_GbsMarqueeWorker(QThread)` lives in `NowPlayingPanel`. 60s cadence while GBS station bound + playing; 5min slow cadence otherwise.
3. **`_GbsAddSongWorker(QThread)` inside `now_playing_panel.py`** — Copy-paste from `_GbsVoteWorker:142`. UI gated on Phase 60.4 token-count state. Backend extends `gbs_api.py` with `add_song_zero_token()`.
4. **`musicstreamer/twitch_helix.py` (NEW, ~50 LOC)** — Single GET against `https://api.twitch.tv/helix/users?login=<x>`. Reuses existing Phase 32 user token. `urllib.request` per project convention.
5. **Channel-avatar storage** — `~/.local/share/musicstreamer/assets/channel-avatars/<station-id>.png`; new `channel_avatar_path TEXT` column on `stations` (additive migration). Single migration covers both YT + Twitch.
6. **`musicstreamer/preroll_log.py` (NEW)** — Mirrors `musicstreamer/buffer_log.py` (Phase 78 size-rotated structured logs). Wires at decision points in `player.py:_try_next_stream` + `_on_preroll_about_to_finish` — instrumentation only, no behavior change.
7. **Banner widget** — New `_GbsBanner(QWidget)` instantiated inside `NowPlayingPanel.__init__`, positioned at TOP of panel above existing three-column row1. Hidden by default; visible only when bound station is GBS.FM AND announcement is non-empty AND announcement-hash differs from last-seen.

**Internal boundaries — new (all queued-Signal across QThread + thread-local SQLite per established convention):**

- `gbs_marquee.py` ↔ `now_playing_panel.py` — mirror of `aa_live.py` ↔ `_AaLiveWorker`
- `yt_import.fetch_channel_avatar()` ↔ `edit_station_dialog.py` — mirror of Phase 17 AA-logo `ThreadPoolExecutor`
- `twitch_helix.py` ↔ `edit_station_dialog.py` — same shape as YT
- `preroll_log.py` ↔ `player.py` — synchronous append, lock-free single-writer
- `packaging/linux/common/` ↔ AppImage/Flatpak recipes — filesystem handoff via `packaging/linux/common/dist/`

See `.planning/research/ARCHITECTURE.md` for the full file-by-file integration matrix.

### Critical Pitfalls

Top critical pitfalls — see PITFALLS.md for the full 16-pitfall catalog with warning-signs and phase-mapping.

1. **AppImage GLIBC baseline silently bumped (Pitfall 1)** — Building on current Ubuntu/Fedora/Arch produces an AppImage with `GLIBC_2.38` requirement that won't run on Ubuntu 22.04 LTS / Debian 12. **Prevent:** Ubuntu 22.04 Docker container; verify `strings AppRun_or_main_so | grep GLIBC_ | sort -V | tail -1 ≤ 2.35` in CI.
2. **linuxdeploy-plugin-gstreamer leaks build-host paths into the registry cache (Pitfall 2)** — Plugins bundled but `gst-plugin-scanner` cache has build-host absolute paths. **Prevent:** AppRun must `unset GST_REGISTRY`, set `GST_REGISTRY_FORK=no`, point `GST_PLUGIN_SCANNER` to bundled scanner, set BOTH `GST_PLUGIN_SYSTEM_PATH_1_0` AND `GST_PLUGIN_PATH_1_0`. Test on Ubuntu 22.04 + Fedora 40 + openSUSE Tumbleweed.
3. **Flatpak QtWebEngine sandbox-in-sandbox crash (Pitfall 4)** — Chromium's renderer-sandbox uses `unshare()`; Flatpak's bubblewrap already entered the namespaces. **Prevent:** Set `QTWEBENGINE_DISABLE_SANDBOX=1` in `finish-args` (verbatim per `feedback_mirror_decisions_cite_source.md`). Do NOT paraphrase as `--no-sandbox`.
4. **QtWebEngine cookies don't share between subprocess and main process by default (Pitfalls 5 + 14)** — Default `QWebEngineProfile()` is off-the-record → in-memory only. **Prevent:** Both the Phase 76 login subprocess AND the new marquee fetcher MUST construct `QWebEngineProfile("musicstreamer-gbs", parent)` with identical storage-name + `setPersistentStoragePath()` + `setPersistentCookiesPolicy(ForcePersistentCookies)`. Define `GBS_WEB_PROFILE_NAME` + `GBS_WEB_STORAGE_PATH` as module-level constants; the marquee fetcher imports them.
5. **Channel-avatar overrides legitimate MB-CAA cover art (Pitfall 8)** — "if cover_art_result is None, show channel_avatar" short-circuits the Phase 73 MB-CAA fallback (per `project_vaporwave_mb_caa_coverage.md`). **Prevent:** Cover-resolver precedence MUST be `ICY → iTunes → MB-CAA → channel-avatar → placeholder`. Source-grep drift-guard. Channel-avatar fallback fires ONLY when ICY is empty/disabled.
6. **yt-dlp `thumbnail` is the video preview, not the channel avatar (Pitfall 7)** — Lofi Girl shows the headphones-girl video frame instead of the chill-beats icon. **Prevent:** Filter `info.get('thumbnails', [])` to entries with `id == 'avatar_uncropped'` (preferred) or `id == 'avatar'`. Reject `width != height`. Source-grep gate. Spike-first.
7. **SMTC AUMID mismatch on pre-existing pinned shortcuts (Pitfall 6)** — Existing Inno AUMID directive is correct + parity test enforces it. But re-install creates a new `.lnk` while user's previously-pinned taskbar `.lnk` retains OLD AUMID → "Unknown app". **Prevent:** Inno uninstaller `[InstallDelete]` clause; document "unpin from taskbar before upgrading". Verify on Win11 VM that had v2.1 installed BEFORE installing v2.2.
8. **SomaFM preroll probe corrupts the live session (Pitfall 11)** — Using a second `playbin3` to probe Boot Liquor doubles audio + fights for per-IP connection cap. **Prevent:** Non-destructive `requests.get(url, stream=True, headers={'Icy-MetaData': '1'})` for 30s, separate log, opt-in via hamburger menu. Mirror Phase 78/84 ship+monitor pattern.
9. **Phase 84 buffer adaptation regressed by preroll instrumentation (Pitfall 12)** — Adding logging mid-function perturbs Qt signal coalescing. **Prevent:** Add instrumentation at END of existing functions, NEVER mid-function. Pin Phase 84 stage-and-apply order via source-grep drift-guard. Re-run Phase 84 D-11 acceptance test.
10. **Phase 71 sibling rendering regressed by NowPlayingPanel cover-slot edits (Pitfall 13)** — Per `feedback_ui_bug_verify_with_extremes.md` and Phase 71 D-14/D-15. **Prevent:** Add `test_richtext_baseline_unchanged_by_phase_89` mirroring Phase 71's existing guard. Sweep widget through extreme states BEFORE attempting any layout fix.

**Verbatim citations required (per `feedback_mirror_decisions_cite_source.md`):**

- Inno Setup `[Icons]` AUMID semantics → cite https://jrsoftware.org/ishelp/topic_iconssection.htm — do NOT paraphrase.
- Microsoft AUMID guidance → cite https://learn.microsoft.com/en-us/windows/win32/shell/appids with the specific paragraph about per-process binding via `SetCurrentProcessExplicitAppUserModelID`.
- Flathub QtWebEngine sandbox env var → cite the `io.qt.qtwebengine.BaseApp` manifest at https://github.com/flathub/io.qt.qtwebengine.BaseApp for `QTWEBENGINE_DISABLE_SANDBOX=1` spelling — do NOT paraphrase as `--no-sandbox`.
- GBS marquee "first pipe-segment is the banner" → quote 3 actual marquee strings + expected banner outputs (10 historical samples minimum before locking the parser).
- Boot Liquor preroll absence → cite the actual server response (curl output with headers + first 8KB) when CONTEXT.md asserts root cause.

---

## Consolidated Spike-First Candidates

Six items merit explicit spike phases or spike-style first-plans BEFORE locking architecture:

1. **AppImage build container baseline** — Pick Ubuntu 22.04 LTS. Build a hello-world Qt + GStreamer AppImage. Test on Ubuntu 22.04 + Fedora 40 + openSUSE Tumbleweed. BEFORE Phase 85.
2. **linuxdeploy-plugin-gstreamer + conda paths feasibility** — Verify the plugin can find `$CONDA_PREFIX/lib/gstreamer-1.0`. Spike outcome feeds Phases 85 + 86 directly.
3. **Flatpak QtWebEngine BaseApp + sandbox flag** — Build a minimal QtWebEngine-based Flatpak that loads `https://gbs.fm` and reads cookies on restart. Verify `QTWEBENGINE_DISABLE_SANDBOX=1` works. BEFORE Phase 86.
4. **QtWebEngine cookie persistence cross-process** — Verify `setPersistentStoragePath()` + `ForcePersistentCookies` survives subprocess exit, restart, and is readable by a hidden `QWebEnginePage` in the main process. BEFORE Phase 87.
5. **yt-dlp channel-avatar field discovery** — `yt-dlp -J` against 5 channel URL shapes; harvest actual JSON; document which `thumbnails[].id` values are reliable. BEFORE Phase 89.
6. **SomaFM preroll harvest** — Non-destructive `requests.get(stream=True, headers={'Icy-MetaData': '1'})` against Boot Liquor + 4 known-good stations, 30s capture each. BEFORE Phase 90 design.

---

## Implications for Roadmap

Suggested phase structure: ARCHITECTURE's 7-tier ordering reconciled with FEATURES' "carry-overs first" recommendation. FIX-MPRIS runs in **parallel** with the Tier-1 Linux spike (FIX-MPRIS is tests-only). Phase numbers continue from 84 per PROJECT.md.

### Tier 1 — Spike & Foundation (Week 1, parallel)

**Phase 85a — Linux Packaging Spike (HIGH RISK)** — De-risk linuxdeploy-plugin-gstreamer + conda paths. Delivers a working hello-world AppImage with conda's GStreamer playing a remote MP3 stream on Ubuntu 22.04 + Fedora 40 + openSUSE Tumbleweed. Avoids Pitfalls 1, 2. **Research flag: YES.**

**Phase 91 — FIX-MPRIS (Phase 77 7 deferred MPRIS2 tests)** — Tests-only, no dependencies. Per Pitfall 15 (env-gap misdiagnosis), first plan is `grep "class FakePlayer" tests/ | wc -l` — if > 1, structural not environmental. Delivers clean test baseline. **Research flag: NO.**

### Tier 2 — Linux Packaging Build (Weeks 2-3)

**Phase 85 — Linux common groundwork + AppImage pipeline** — Consumes spike outcome. Delivers `packaging/linux/common/dist/` + `MusicStreamer-<version>-x86_64.AppImage` with `.desktop` integration, MPRIS continuity, Node.js bundling, zsync update info. Uses `linuxdeploy` + `linuxdeploy-plugin-conda` + `linuxdeploy-plugin-gstreamer`. Avoids Pitfalls 1, 2, 3.

**Phase 86 — Flatpak pipeline** — Parallel-but-late. GNOME-KDE SDK ≠ conda, so doesn't inherit from Phase 85 directly. **Per FEATURES dependency note: FIX-MPRIS (Phase 91) MUST precede Flatpak in-sandbox MPRIS verify.** Delivers `org.lightningjim.MusicStreamer.flatpak` build via `flatpak-builder`. Uses `io.qt.PySide.BaseApp//6.8` + `org.kde.Platform//6.8` + `org.kde.Sdk//6.8` + `org.freedesktop.Platform.ffmpeg-full//24.08` + `org.freedesktop.Sdk.Extension.node20`. Avoids Pitfalls 4, 5. **Research flag: YES.**

### Tier 3 — Windows Polish (Week 4, one Win11 VM session)

**Phase 88 — WIN-02 + VER-02-J + WIN-05 retest bundle** — Per PROJECT.md line 17, bundled into a single Win11 VM session. Inno-Setup-only changes; no Python code. Delivers Inno `[Icons]` AUMID parity test extension, `[InstallDelete]` clause for old `.lnk` removal, Win11 UAT sign-off + AAC retest. Avoids Pitfalls 6, 16. **Research flag: spike-style first-plan (WPR trace + `Get-StartApps` PowerShell verification BEFORE writing any new code).**

### Tier 4 — Channel-Avatar Infrastructure (Week 5, sequential within tier)

**Phase 89a — DB migration + storage layout** — Foundation for both YT + Twitch. Delivers `channel_avatar_path TEXT` column on `stations`; `~/.local/share/musicstreamer/assets/channel-avatars/` directory; idempotent migration; rollback test.

**Phase 89 — YT channel avatar fetch + cover-slot swap** — Per Pitfall 7 spike: yt-dlp field discovery first, implementation second. **Per Pitfall research, Phase 87 GBS marquee precedes Phase 89 channel-avatar fallback** as asserted in the user's brief. Delivers `yt_import.fetch_channel_avatar()` filtering on `id == 'avatar_uncropped'`; `edit_station_dialog.py` auto-fetch trigger on URL paste; `NowPlayingPanel` ICY-disabled branch with circular-crop QPixmap. Avoids Pitfalls 7, 8, 13. **Research flag: YES.**

**Phase 89b — Twitch channel avatar fetch** — Smaller than 89 (storage + UI path shared). Delivers `musicstreamer/twitch_helix.py` with `fetch_twitch_profile_image()` reusing existing `twitch-token.txt` user token (no new scopes); cache 24h.

### Tier 5 — GBS Polish (Week 6, sequential within tier)

**Phase 87 — GBS marquee + themed-day detection** — Establishes the QtWebEngine cookie-persistence-cross-process pattern. Delivers `musicstreamer/gbs_marquee.py`; `_GbsMarqueeWorker` QThread in NowPlayingPanel; banner widget; themed-logo session-scoped detection via SHA-256 content hash + marquee keyword corroboration. Avoids Pitfalls 5, 9, 10, 14. **Research flag: YES.**

**Phase 87b — GBS zero-token add affordance** — Depends on Phase 87's token-count state coupling. UX must NEVER use the word "token". Delivers `_GbsAddSongWorker(QThread)`; `gbs_api.add_song_zero_token()`; gated render on `tokens==0 AND queue empty AND station.provider_name=="GBS.FM"`.

### Tier 6 — SomaFM Preroll Debug (Week 7, spike-then-fix)

**Phase 90 — Preroll instrumentation** — Mirror Phase 78/84 ship+monitor pattern. Delivers `musicstreamer/preroll_log.py` size-rotated event log; wiring at decision points in `player.py` (NO behavior change); hamburger-menu "Open preroll log". Avoids Pitfalls 11, 12.

**Phase 90b (CONDITIONAL) — Preroll fix** — Contingent on what Phase 90's log reveals after 1-2 days of real listening. Hypothesis space: catalog gap, stream-URL pattern mismatch, `_preroll_in_flight` flag race, 10-minute throttle window cross-station leakage.

### Tier 7 — Carry-Overs (mid-milestone slot-in)

**Phase 92 — FIX-PLS (Phase 58 PLS URL-fallback for codec/bitrate)** — Small phase, no Linux dep. Slot-in any week mid-milestone.

**Phase 93 (CONDITIONAL) — BUFFER-MONITOR follow-up** — Only fires if any of Phase 84-VERIFICATION.md's 3 Follow-Up Triggers fires during the v2.2 dev window.

### Research Flags

Phases likely needing `/gsd:plan-phase --research-phase <N>`: 85a, 86, 87, 89.

Phases with standard patterns (skip research-phase): 85, 87b, 88, 89b, 90, 91, 92.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | linuxdeploy/Flathub/Microsoft/yt-dlp/Twitch official docs verified; existing v2.1 stack untouched |
| Features | HIGH | Packaging best-practices verified against Flathub + AppImage docs; UX from Carbon/Fluent/GNOME Software banner patterns; PROJECT.md milestone scope explicit |
| Architecture | HIGH | Direct source audit; every new component named against an existing-phase pattern analog (Phase 17, 32, 60.4, 68, 73, 76, 78) |
| Pitfalls | HIGH | 16 pitfalls verified against existing artifacts (Phase 35/43/43.1/56/69/76 lessons) + current upstream issue trackers; five auto-memory feedback-files cited as design constraints |

**Overall confidence:** HIGH

### Open Questions Needing User-Input Before Requirements Lock

These are scope/policy decisions, NOT architecture gaps:

1. **Zero-token affordance final wording** — "Add a song" vs. "Queue 1 song" vs. "Queue this song"? Per PROJECT.md line 18: MUST NOT contain the word "token". Recommendation: "Add a song".
2. **Themed-day visual treatment** — Logo swap only, OR also an accent retint sampled from new logo's dominant color via existing Phase 59 accent code? Recommendation: logo swap only in P1; accent retint as P2 polish.
3. **Channel-avatar fetch trigger** — Auto-fetch on URL paste in `EditStationDialog` (consistent with existing YT thumbnail behavior from Phase 6/17) OR explicit "Fetch avatar" button? Recommendation: auto-fetch on paste.
4. **Channel-avatar refresh cadence** — One-time fetch on station create/edit + manual "Refresh avatar" affordance vs. periodic refresh? Recommendation: one-time + manual.
5. **AppImage zsync update URL host** — QNAP Gitea releases, GitHub releases (via the mirror), or "embed a 404 URL and never ship updates between milestones"? Blocks Tier 2 close.
6. **Flatpak app ID (reverse-DNS)** — `org.lightningjim.MusicStreamer` vs. `io.github.kcreasey.MusicStreamer`? MUST be locked BEFORE first manifest commit; cannot change after Flathub listing.
7. **Flatpak data migration story** — (A) `--filesystem=xdg-data/musicstreamer:rw` (Flathub policy violation, simple) vs. (B) first-launch import wizard (Flathub-clean, matches Phase 25 settings export/import pattern)? Recommendation: option B.

---

## Sources

### Primary (HIGH confidence)

- linuxdeploy GitHub — https://github.com/linuxdeploy/linuxdeploy
- linuxdeploy-plugin-conda — https://github.com/linuxdeploy/linuxdeploy-plugin-conda
- linuxdeploy-plugin-gstreamer (issues #17, #9) — https://github.com/linuxdeploy/linuxdeploy-plugin-gstreamer
- Flatpak docs — https://docs.flatpak.org/
- flathub/io.qt.PySide.BaseApp (branches 6.8/6.9/6.10 verified) — https://github.com/flathub/io.qt.PySide.BaseApp
- flathub/io.qt.qtwebengine.BaseApp (`QTWEBENGINE_DISABLE_SANDBOX=1` spelling) — https://github.com/flathub/io.qt.qtwebengine.BaseApp
- develop.kde.org — Publishing your Python app as a Flatpak — https://develop.kde.org/docs/getting-started/python/python-flatpak/
- Flathub requirements / App Submission wiki — https://docs.flathub.org/docs/for-app-authors/requirements
- Twitch Helix Reference — Get Users — https://dev.twitch.tv/docs/api/reference/
- Qt 6.10 / Qt for Python 6 — QWebEngineCookieStore + QWebEngineProfile — https://doc.qt.io/qtforpython-6/PySide6/QtWebEngineCore/
- Microsoft Learn — Application User Model IDs — https://learn.microsoft.com/en-us/windows/win32/shell/appids
- Inno Setup `[Icons]` section — `AppUserModelID:` directive — https://jrsoftware.org/ishelp/topic_iconssection.htm
- AppImage best practices — GLIBC compatibility — https://docs.appimage.org/reference/best-practices.html
- Existing project: `.planning/PROJECT.md`, `.planning/codebase/STACK.md`, `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STRUCTURE.md`, `.planning/codebase/INTEGRATIONS.md`, `.planning/codebase/CONCERNS.md`, `.planning/seeds/SEED-009-linux-appimage-install.md`
- Existing project: `packaging/windows/MusicStreamer.iss` (line 71 AUMID), `packaging/windows/MusicStreamer.spec`, `packaging/windows/README.md`, `tests/test_aumid_string_parity.py`, `tools/check_bundle_plugins.py`
- Auto-memory: `feedback_gstreamer_mock_blind_spot.md`, `feedback_mirror_decisions_cite_source.md`, `feedback_ui_bug_verify_with_extremes.md`, `reference_musicstreamer_db_schema.md`, `project_vaporwave_mb_caa_coverage.md`, `project_deployment_target.md`

### Secondary (MEDIUM confidence)

- yt-dlp issues #10090, #14041, #7521 — https://github.com/yt-dlp/yt-dlp/issues/
- alexwlchan — Creating a personal wrapper around yt-dlp (2025) — https://alexwlchan.net/2025/yt-dlp-wrapper/
- Robertof/make-shortcut-with-appusermodelid — https://github.com/Robertof/make-shortcut-with-appusermodelid
- Carbon Design System — Toast vs banner notification patterns — https://carbondesignsystem.com/patterns/notification-pattern/
- pkg2appimage #173 — Bundle libstdc++ and decide at runtime — https://github.com/AppImage/pkg2appimage/issues/173
- Flathub Discourse — Distributing a Qt app in a flatpak with WebEngine — https://discourse.flathub.org/t/distributing-a-qt-app-in-a-flatpak-with-webengine/5224
- Tim Golden pywin32 docs — SetCurrentProcessExplicitAppUserModelID — https://timgolden.me.uk/pywin32-docs/

### Tertiary (LOW confidence — flagged for validation during planning)

- yt-dlp `thumbnails[].id == 'avatar_uncropped'` field permanence — InnerTube responses change without notice; wrap in try/except + spike harvest before Phase 89.
- `linuxdeploy-plugin-gstreamer` "experimental" maintainer marker — spike-first verification mandatory.
- GBS.FM marquee CSS selector stability — pin selector to `<span class="marquee">` + validate via known-good HTML fixture; 10-sample harvest spike.
- SomaFM preroll absence root cause — 4 hypotheses; mandatory instrument-first ship+monitor pattern before any fix.

---

*Research completed: 2026-05-25*
*Ready for roadmap: yes*
*Synthesizes: STACK.md, FEATURES.md, ARCHITECTURE.md, PITFALLS.md*
