# Architecture Research — v2.2 Integration Plan

**Domain:** MusicStreamer v2.2 — Linux packaging parity + Windows polish + GBS.FM/SomaFM/avatar QOL
**Researched:** 2026-05-25
**Confidence:** HIGH (based on direct source audit of existing v2.1-shipped codebase)

**Scope of this document:** This is integration architecture, not greenfield. The MusicStreamer codebase is mature (~13k LOC Python, 1462 passing tests). Every recommendation below names the concrete file(s) the new work touches, the existing analog phase that establishes the pattern, and the signal/data wiring that connects new components to the running system.

---

## System Overview — Where v2.2 Work Lands

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    Qt GUI Layer (PySide6)                                     │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │ MainWindow (ui_qt/main_window.py)                                       │  │
│  │  ├─ StationListPanel       ──[unchanged in v2.2]                        │  │
│  │  ├─ NowPlayingPanel        ──[+ GBS banner, +channel-avatar cover swap, │  │
│  │  │   ui_qt/now_playing_panel.py    + zero-token "Add Song" affordance]  │  │
│  │  ├─ Toast Overlay          ──[reused for GBS marquee transitions,       │  │
│  │  │   ui_qt/toast.py             SomaFM preroll-debug breadcrumbs]       │  │
│  │  └─ Dialogs (Edit/Import/Accounts/Discovery/CookieImport/Manage…)       │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────┬──────────────────────────────────────────────┘
                                │ Qt signals (QueuedConnection across threads)
                                ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  Player (QObject) — musicstreamer/player.py (2100 lines, single file)        │
│   ├─ Failover queue + preroll injection  ──[+ Phase 77 MPRIS2 test repair,  │
│   │                                          + SomaFM preroll DEBUG plumbing]│
│   ├─ GStreamer playbin3 + EQ + adaptive buffer (Phase 84 stage-and-apply)    │
│   ├─ YouTube resolver (yt-dlp lib API + Node.js)                             │
│   └─ Twitch resolver (streamlink + auth-token)                               │
└─────────┬────────────────────────────────────────────────────┬───────────────┘
          │                                                    │
          ▼                                                    ▼
┌────────────────────────────┐                  ┌─────────────────────────────┐
│ GstBusLoopThread           │                  │ Media-keys backends         │
│ gst_bus_bridge.py          │                  │ media_keys/{mpris2,smtc}.py │
│ (daemon GLib.MainLoop)     │                  │  ──[Phase 77 FIX-MPRIS:     │
│                            │                  │     repair 7 cross-file     │
│                            │                  │     parity tests]           │
└────────────────────────────┘                  └─────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│  Live-data + provider clients (network-aware modules, no Qt)                  │
│   ├─ aa_live.py            — AudioAddict events poll (Phase 68, reused shape)│
│   ├─ gbs_api.py (1232 LOC) — GBS browse/playlist/vote                        │
│   │   ──[+ marquee scraper, +themed-logo hash detection]                     │
│   ├─ gbs_marquee.py        ──[NEW — see "GBS marquee data flow" below]       │
│   ├─ yt_import.py          — yt-dlp playlist scan + (NEW) channel avatar    │
│   └─ aa_import.py / soma_import.py / radio_browser.py / cover_art{,_mb}.py   │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│  oauth_helper.py — subprocess-isolated QtWebEngine login (130MB-walled-off)  │
│   ├─ Twitch cookie harvest                                                   │
│   ├─ GBS.FM cookie harvest (Phase 76: sessionid+csrftoken trigger set)       │
│   └─ Google/YouTube cookie harvest                                           │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│  Data layer — repo.py + paths.py (platformdirs-rooted)                       │
│   ~/.local/share/musicstreamer/                                              │
│     ├─ musicstreamer.sqlite3      (stations, station_streams, providers,     │
│     │                              station_siblings, favorites, settings…)   │
│     ├─ assets/                    (station logos, album fallbacks)           │
│     ├─ assets/channel-avatars/    ──[NEW — see channel-avatar section]       │
│     ├─ cookies.txt                (YT, 0o600)                                │
│     ├─ gbs-cookies.txt            (Phase 76, 0o600)                          │
│     ├─ twitch-token.txt           (Phase 32, 0o600)                          │
│     └─ buffer-events.log          (Phase 78, size-rotated)                   │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│  Packaging — split-by-platform tree                                          │
│   packaging/                                                                 │
│     ├─ windows/ ──[Inno Setup + PyInstaller + conda-forge GStreamer recipe;  │
│     │             v2.2 adds WIN-02 AUMID Start-Menu shortcut polish]         │
│     └─ linux/                                                                │
│         ├─ org.lightningjim.MusicStreamer.{desktop,png} (exists today)       │
│         ├─ common/      ──[NEW — shared Python-bundle stage]                 │
│         ├─ appimage/    ──[NEW — AppImage recipe (SEED-009)]                 │
│         └─ flatpak/     ──[NEW — Flatpak manifest + permissions]             │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## v2.2 Feature → Integration Point Matrix

| # | Feature (from milestone) | Touches (existing) | Adds (new files) | Pattern analog |
|---|--------------------------|--------------------|------------------|----------------|
| 1 | AppImage build | `packaging/linux/`, `pyproject.toml` | `packaging/linux/common/`, `packaging/linux/appimage/build.sh`, `org.lightningjim.MusicStreamer.AppImage.recipe` | Phase 43/44/69 Windows PyInstaller spec |
| 2 | Flatpak build | `packaging/linux/`, `musicstreamer/paths.py` (XDG awareness already correct) | `packaging/linux/flatpak/org.lightningjim.MusicStreamer.yaml`, `flatpak/org.lightningjim.MusicStreamer.desktop` (sandbox-aware override) | Phase 44 Inno Setup is the conceptual analog (declarative bundler config) |
| 3 | Linux common groundwork | `pyproject.toml`, `tools/` | `packaging/linux/common/build_bundle.sh`, `packaging/linux/common/manifest.txt` | Phase 65/69 `tools/check_bundle_plugins.py` shared between Inno + spec |
| 4 | GBS marquee + themed-day | `gbs_api.py`, `ui_qt/now_playing_panel.py`, `ui_qt/main_window.py`, `theme.py` | `musicstreamer/gbs_marquee.py` (poll worker + parser), GBS banner widget inside NowPlayingPanel | Phase 68 `aa_live.py` + `_AaLiveWorker` (already in `now_playing_panel.py:114`) |
| 5 | GBS zero-token add | `gbs_api.py`, `ui_qt/now_playing_panel.py` | `_GbsAddSongWorker` QThread in `now_playing_panel.py` | Phase 60 `_GbsVoteWorker` (`now_playing_panel.py:142`) is the exact shape |
| 6 | YT channel avatar | `yt_import.py`, `ui_qt/now_playing_panel.py`, `ui_qt/edit_station_dialog.py` | `fetch_channel_avatar()` in `yt_import.py`, `channel_avatar_path` column in `stations` (migration) | Phase 17 AA logo `ThreadPoolExecutor`, Phase 6 YT-thumbnail auto-fetch on station save |
| 7 | Twitch channel avatar | `yt_import.py` (or new `twitch_helix.py`), `ui_qt/now_playing_panel.py` | `fetch_twitch_profile_image()` (uses existing twitch-token.txt + Helix `/users`) | Phase 32 `_play_twitch()` auth-token reuse |
| 8 | SMTC AUMID shortcut polish (WIN-02) | `packaging/windows/MusicStreamer.iss` only | none (Inno Setup directive tweak) | Phase 56 WIN-02 attempted; v2.1 closed via in-app launch path; v2.2 finishes Start-Menu shortcut alignment |
| 9 | SomaFM preroll debug | `player.py` (`_start_preroll`, `_on_preroll_about_to_finish`), `ui_qt/toast.py`, `paths.py` | `buffer-events.log` parallel: `preroll-events.log` (size-rotated) | Phase 78 `buffer_log.py` (already shipping size-rotated structured logs) |
| 10 | Phase 77 MPRIS2 7 cross-file failures | `tests/test_media_keys_*.py`, possibly `media_keys/mpris2.py`, `tests/_fake_player.py` | none (tests-only or surgical wiring fix) | Phase 77 shared FakePlayer + parity drift-guards (see 77-06-SUMMARY.md) |

---

## Integration Architecture — Detail by Feature

### 1+2+3. Linux Packaging (AppImage + Flatpak + Common Groundwork)

**Recommended structure:**
```
packaging/linux/
├── common/
│   ├── build_bundle.sh           # Produces packaging/linux/common/dist/MusicStreamer/
│   │                              # — flat directory with python + musicstreamer + qt + gst
│   ├── check_bundle.py            # Mirror of tools/check_bundle_plugins.py for Linux GST
│   └── README.md
├── appimage/
│   ├── build.sh                   # consumes ../common/dist, wraps in appimagetool
│   ├── AppRun                     # entry-point shim — sets GST_PLUGIN_PATH, GIO_EXTRA_MODULES,
│   │                              #                   GI_TYPELIB_PATH, XDG_DATA_DIRS
│   ├── org.lightningjim.MusicStreamer.appdata.xml   # AppStream metainfo
│   └── linuxdeploy-plugin-gstreamer.sh              # if linuxdeploy-plugin doesn't already exist
├── flatpak/
│   ├── org.lightningjim.MusicStreamer.yaml          # Flatpak manifest
│   ├── org.lightningjim.MusicStreamer.desktop       # sandbox-aware desktop file (no abs paths)
│   ├── org.lightningjim.MusicStreamer.metainfo.xml  # required for Flathub
│   └── README.md
├── org.lightningjim.MusicStreamer.desktop           # exists today (system-install variant)
└── org.lightningjim.MusicStreamer.png               # exists today
```

**Decision: Conda-forge for AppImage, GNOME SDK for Flatpak (not shared envs).**

Rationale:
- **AppImage** reuses the proven Windows conda-forge recipe (Phase 43/69 patterns). Build inside `mambaforge` env, then run `linuxdeploy --plugin gstreamer --plugin qt` against the conda env tree. Conda's GStreamer 1.28 + gst-libav + gst-plugins-{base,good,bad,ugly} + pyside6 has empirical AAC playback + GIO TLS working on Linux too. Pitfall (HIGH): linuxdeploy-plugin-gstreamer assumes distro-installed GStreamer paths — pointing it at conda's `$CONDA_PREFIX/lib/gstreamer-1.0` requires `GSTREAMER_INCLUDE_BAD=1` and explicit `LD_LIBRARY_PATH`. Spike this in Phase 1 of the Linux build work.
- **Flatpak** must use Freedesktop or GNOME SDK base (Flathub policy). Use `org.gnome.Sdk//47` with `python3` extension. GStreamer comes from the runtime — do NOT bundle conda. This means Flatpak is a parallel pipeline, not a wrapper over the common bundle. The "common" stage produces only the `musicstreamer/` Python package + assets, NOT the runtime; Flatpak's manifest then layers it onto GNOME SDK.

**What `common/build_bundle.sh` actually produces:** a clean wheel + flat asset directory. AppImage layers conda's full GStreamer/Python on top; Flatpak layers GNOME SDK on top. The "common" tier is roughly equivalent to `python -m build --wheel` plus copying `packaging/linux/org.lightningjim.MusicStreamer.{desktop,png}`.

**Permission model for Flatpak (concrete `--share`/`--socket`/`--filesystem`):**
| Permission | Why |
|------------|-----|
| `--share=network` | iTunes, MB+CAA, Radio-Browser, AA, SomaFM, GBS.FM, YouTube, Twitch |
| `--socket=pulseaudio` | Audio (Pipewire's PulseAudio compat layer covers Wayland users) |
| `--socket=wayland` + `--socket=fallback-x11` | UI |
| `--talk-name=org.mpris.MediaPlayer2.musicstreamer` | MPRIS2 advertisement (note: Flatpak auto-publishes per-app bus names with `org.mpris.MediaPlayer2.{app-id}` prefix; need to verify MPRIS2 backend's bus-name literal aligns) |
| `--filesystem=xdg-data/musicstreamer` | DB + cookies + assets persistence (default Flatpak sandbox redirects `~/.local/share` to `~/.var/app/<app-id>/data` — migration story below) |
| `--device=all` (or `--device=dri`) | None needed; audio-only — explicitly omit to score Flathub permission-cleanliness rating |

**Critical Flatpak data-migration concern:** `~/.local/share/musicstreamer/` outside the sandbox is NOT readable from inside. First-launch under Flatpak sees an empty `~/.var/app/org.lightningjim.MusicStreamer/data/`. Two options:
- (A) **Recommended:** add `--filesystem=xdg-data/musicstreamer:ro` (or `:rw`) override pointing at the unsandboxed path. Simple, breaks Flathub policy slightly.
- (B) First-launch import wizard: detect non-Flatpak data dir, prompt user to migrate. Cleaner; matches existing Phase 25 settings export/import pattern. This is the recommended one for Flathub publishing.

**QtWebEngine inside Flatpak:** `oauth_helper.py` subprocess runs QtWebEngine. Flathub's GNOME 47 runtime ships QtWebEngine; the existing subprocess launch (`python -m musicstreamer.oauth_helper --mode gbs`) Just Works inside Flatpak as long as the manifest declares `qt6-webengine` extension. Cookie persistence: Phase 76's `_GbsLoginWindow` uses `NoPersistentCookies` (line 281 of oauth_helper.py) — Netscape dump is sent over stdout pipe to parent. No on-disk persistent cookie store crosses subprocess boundary, so Flatpak sandboxing is irrelevant here.

**Node.js runtime (yt-dlp EJS solver):**
- AppImage: bundle a static Node binary alongside python (~30MB). Conda-forge ships `nodejs`; conda env already pulls it. Add to AppImage payload.
- Flatpak: declare `org.freedesktop.Sdk.Extension.node20` extension in manifest. Standard pattern.

**Suggested ordering inside the Linux packaging work:**
1. (spike-first) Conda-on-Linux + linuxdeploy-plugin-gstreamer compatibility — derisk before committing to either format
2. `packaging/linux/common/build_bundle.sh` — produces flat dist tree from conda env
3. AppImage recipe + `AppRun` shim + tooling smoke test
4. Flatpak manifest + GNOME SDK build smoke test
5. Cross-distro AppImage UAT (Ubuntu LTS + Fedora + Arch — matches SEED-009 phase 4)
6. Flathub submission prep (metainfo.xml, screenshot capture, Flathub policy review) — this can defer to a follow-on milestone

---

### 4. GBS.FM Marquee + Themed-Day Detection

**New module: `musicstreamer/gbs_marquee.py`** — pure Python, mirrors `aa_live.py` shape exactly.

```python
# Public API (target shape):
def fetch_marquee(cookies) -> Optional[MarqueeState]:
    """Scrape https://gbs.fm/ marquee element + logo URL.

    Returns MarqueeState(announcement: str, themed_logo_url: Optional[str])
    or None on auth/network failure (silent — caller re-polls)."""

def detect_themed_day(logo_url: str, marquee_text: str) -> Optional[str]:
    """Return the theme key ('halloween', 'xmas', 'pi-day', ...) or None.

    Phase 4 deliverable: combines logo_3.png hash drift detection +
    marquee keyword sniffing. Session-scoped — caller caches return
    value at GBS launch."""
```

**Data flow (mirror of Phase 68 AA Live exactly):**
```
NowPlayingPanel.__init__
   ├─ _gbs_marquee_worker: QThread = None
   ├─ _gbs_marquee_poll_timer: QTimer (Qt main thread)
   └─ slots: _on_gbs_marquee_ready(MarqueeState)
             _on_gbs_marquee_error(str)

MainWindow._on_station_bound(station):
   if station.provider_name == "GBS.FM":
       NowPlayingPanel.start_gbs_marquee_polling()    # 60s cadence
   else:
       NowPlayingPanel.stop_gbs_marquee_polling()     # or N-min slow cadence

_GbsMarqueeWorker(QThread).run():
   from musicstreamer.gbs_marquee import fetch_marquee
   state = fetch_marquee(self._cookies)
   self.finished.emit(state)        # Signal(object) — queued to main

_on_gbs_marquee_ready(state):
   theme = detect_themed_day(state.themed_logo_url, state.announcement)
   if theme != self._current_theme:
       self._apply_theme(theme)             # themes.py → CSS reload
       self.live_status_toast.emit(f"GBS theme: {theme}")
   if state.announcement != self._last_announcement:
       self._banner.set_text(state.announcement)
       self._last_announcement = state.announcement
```

**Banner widget placement:** New `_GbsBanner(QWidget)` instantiated inside `NowPlayingPanel.__init__`, positioned at the TOP of the panel (above the three-column row1). Hidden by default; visible only when bound station is GBS.FM AND announcement is non-empty. Mirror `_MutedLabel` pattern from `now_playing_panel.py:177`. Do NOT extend the toast overlay — toasts are ephemeral; banner is persistent for the session.

**Themed-logo flow:**
- `theme.py` already handles theme application (Phase 66 + 75 toast retinting). Add a `THEME_GBS_HALLOWEEN`, `THEME_GBS_XMAS`, etc. preset OR a `_GBS_THEMED_OVERLAY` color override.
- Logo widget swap is local to NowPlayingPanel: when GBS station bound + theme detected, the logo slot loads `~/.cache/musicstreamer/gbs-themed-logo-<hash>.png` (fetched once per session per theme).
- Logo widget is the existing `_load_scaled_pixmap` site at `now_playing_panel.py:202`.

**Cookie sharing with `gbs_api.py`:** `gbs_marquee.fetch_marquee()` accepts the same `MozillaCookieJar` that `gbs_api._load_cookies()` returns (`gbs_api.py:93`). No new persistence — cookies still live at `paths.gbs_cookies_path()`.

**Polling cadence (B-05 pattern from Phase 68):**
- 60s while GBS.FM station is bound + playing (matches AA live worker)
- 5 min slow-cadence otherwise (for announcement-only changes user might want even when listening to non-GBS)
- Worker is single-attempt (no retries inside run()) — caller schedules next via QTimer

---

### 5. GBS Zero-Token Single-Song Add

**Pattern: `_GbsAddSongWorker(QThread)` in `now_playing_panel.py`** — copy-paste from `_GbsVoteWorker` (line 142). Identical shape:
- Signal `add_song_finished = Signal(int, str)` (token, server msg)
- Signal `add_song_error = Signal(int, str)` (token, 'auth_expired' or msg)

**Backend in `gbs_api.py`:** add `add_song_zero_token(track_query: str, cookies) -> dict`. If the API doesn't actually have a zero-token endpoint (research gap — spike in Phase 1), it may need to wrap `submit_to_playlist()` with a pre-check on token state.

**UI placement:** inline in NowPlayingPanel, NOT a separate panel. Position: next to the title label OR as a small "+" button that opens a popover/QLineEdit-style inline input. The UX MUST NOT use the word "token" anywhere user-visible (PROJECT.md explicit constraint: "UX never framed as '1 token'").

**State coupling with Phase 60.4 token-count poll:** already in flight on `_GbsPollWorker` 30s cadence. Reuse `playlist_ready` signal payload (`state_dict` includes token info). The "Add Song" button enables when `state_dict.get('tokens_available_count')` reaches 0 AND the station is GBS.FM.

---

### 6. YouTube Channel Avatar Fetch

**Storage:** new asset subdir `~/.local/share/musicstreamer/assets/channel-avatars/<station-id>.png`. Use a dedicated subdir so `settings_export.py` ZIP packaging can be opted in/out independently of station logos.

**DB schema change (small migration):** add `channel_avatar_path TEXT` column to `stations`. Pattern matches existing `station_art_path` + `album_fallback_path` columns. Migration is additive (`ALTER TABLE stations ADD COLUMN ...`) — `repo.py:db_init()` already does this idiomatically.

**Fetch function:** `yt_import.fetch_channel_avatar(channel_url: str) -> bytes | None`
- Uses `yt_dlp.YoutubeDL({'extract_flat': True, ...}).extract_info(channel_url)`
- Reads `info['channels'][0]['thumbnails']` OR `info['uploader_avatar']` (verify field path; recent yt-dlp versions expose `channel_thumbnails`)
- Runs in worker thread (`ThreadPoolExecutor` — same pattern as Phase 17 AA logo download workers, `aa_import.py:266`)
- Cookies route through `cookie_utils.temp_cookies_copy()` (Phase 999.7 mandatory pattern)

**Trigger:**
- On station save in `edit_station_dialog.py` (one-time fetch — same UX as existing YT thumbnail auto-fetch from Phase 6)
- NOT on every play (would slam network + YouTube rate-limit)
- Re-fetch path: small "Refresh avatar" button in edit dialog for the case where a channel rebrands

**Cover-slot integration in `NowPlayingPanel`:** the current logic at the cover-art callback path falls back to the station logo when ICY is disabled (v2.1 behavior — Phase 5 FIX). NEW logic:
```
on_title_changed("", icy_disabled=True):
    if station.channel_avatar_path:
        cover_slot.set_pixmap(channel_avatar_path)   # NEW
    else:
        cover_slot.set_pixmap(station.station_art_path)   # current behavior
```
The switch lives in `_on_cover_art_ready` (or its equivalent ICY-disabled branch) — a 5-line conditional, not a new abstraction.

---

### 7. Twitch Channel Avatar Fetch

**Helix endpoint:** `GET https://api.twitch.tv/helix/users?login=<channel_login>` returns `data[0].profile_image_url`.

**Auth — critical decision:** Use the **existing user token** (`paths.twitch_token_path()`) NOT an app token. Rationale:
- App token requires a Client ID + Client Secret pair registered to a Twitch app — adds account-management UX surface
- User token (auth-token cookie, Phase 32) already has scope to read public user info via Helix
- Trade-off: user token expires; refresh path goes through existing `oauth_helper.py --mode twitch`

**File location:** new `musicstreamer/twitch_helix.py` (small, ~50 LOC). Avoid bloating `yt_import.py` (cross-provider name confusion). Pattern: pure `urllib.request` with timeout, returns bytes or None — mirrors `aa_live.fetch_live_map()` shape.

**Storage + cover-slot integration:** same `assets/channel-avatars/<station-id>.png` directory and `channel_avatar_path` column as YT (feature 6) — single migration covers both.

**Trigger:** on station save in `edit_station_dialog.py` AND in the existing Twitch URL auto-detect path (`edit_station_dialog.py` likely has a Twitch-URL branch already given Phase 31-32 work — verify and extend).

---

### 8. SMTC AUMID Start-Menu Shortcut (WIN-02)

**Existing state (from packaging/windows/MusicStreamer.iss + README):**
- AUMID `org.lightningjim.MusicStreamer` IS already set on the `.lnk` via `AppUserModelID:` directive (line 71 of `.iss`)
- `tests/test_aumid_string_parity.py` enforces literal parity across `MusicStreamer.iss` + `__main__.py:_set_windows_aumid`
- The known UAT failure is that SMTC overlay still shows "Unknown app" in some configurations

**Recommended approach: Inno-Setup-only fix.** Do NOT add Python-side `pywin32`/`comtypes`/`pylnk3` shortcut-creation code. Reasons:
- Existing infrastructure already creates the shortcut with AUMID
- The `tests/test_aumid_string_parity.py` drift-guard is a Linux-CI invariant — adding Python shortcut creation would need a parallel guard
- Bundling pywin32/pylnk3 adds 10-15 MB to the bundle for one shortcut at install time

**Concrete WIN-02 v2.2 deliverables:**
- Diagnostic Phase 1 (spike): Win11 VM session — manually verify the `.lnk`'s AUMID via `Get-AppxPackage` and `(New-Object -ComObject Shell.Application).Namespace(0).ParseName('shortcut.lnk').ExtendedProperty('System.AppUserModel.ID')`. Document actual vs. expected.
- If AUMID is correctly on the shortcut but SMTC still shows "Unknown app": the bug is upstream of Inno Setup — likely the AUMID-binding ordering in `__main__.py:_set_windows_aumid` (Phase 43.1 finding: must be set BEFORE QApplication construction).
- Pair with VER-02-J Win11 packaging UAT (bundled per `PROJECT.md`) + WIN-05 AAC retest in a single Win11 session.

---

### 9. SomaFM Preroll Debug Deliverable

**Where preroll injection lives today:** `player.py:_start_preroll` + `_on_preroll_about_to_finish` (lines ~620-705, see grep evidence above). Phase 83 + 84 closed the bulk of preroll work; v2.2's job is debugging WHY tier-specific stations like Boot Liquor don't get prerolls when Groove Salad / Drone Zone / Beat Blender do.

**Hypothesis space (to spike before committing to a fix phase):**
1. **Catalog gap:** `soma_import.py` populates `station.prerolls` via `update_station_prerolls`. Boot Liquor might have an empty or stale list. CHECK: query `SELECT name, prerolls_fetched_at, prerolls FROM stations WHERE provider_name='SomaFM' AND name='Boot Liquor'` first. If `prerolls` is `[]` and `prerolls_fetched_at IS NOT NULL`, the catalog believes there genuinely are no prerolls (D-04 / Pitfall 5 silent-skip path at line 703).
2. **Stream-URL pattern mismatch:** `_play_with_preroll` (or its equivalent) keys off station provider_name + URL pattern. Boot Liquor's URL might not match the assumed pattern.
3. **ICY-burst race condition:** `_preroll_in_flight` flag (`player.py:506`) suppresses ICY tag emission during preroll. If preroll handoff completes faster than the about-to-finish signal for some stations, the gate could close before the user even hears it.
4. **Throttle window:** the 10-minute attempt throttle (`_last_preroll_played_at`, line 507) is project-wide, not per-station. Switching from Groove Salad → Boot Liquor within 10 minutes ATTEMPTS a Boot Liquor preroll silently throttled.

**Debug surface deliverable:**
- New `musicstreamer/preroll_log.py` mirroring `musicstreamer/buffer_log.py` (Phase 78 size-rotated structured log at `paths.buffer_events_log_path()`)
- Log path: `~/.local/share/musicstreamer/preroll-events.log`
- Event types: `preroll_start`, `preroll_skipped_throttle`, `preroll_skipped_empty`, `preroll_skipped_genuinely_empty`, `preroll_handoff_complete`, `preroll_error`
- Each event includes: station_id, station_name, provider, timestamp, monotonic, urls_count, throttle_remaining_s
- Wired at the EXACT existing decision points in `player.py:_try_next_stream` and `_on_preroll_about_to_finish` — no behavior change, instrumentation only
- Hamburger-menu entry "Open preroll log" (mirror existing "Open buffer log" if it exists)

**Spike-first treatment:** Phase 1 of this feature MUST gather 1-2 days of preroll-events.log from real listening sessions BEFORE writing any fix. Phase 84 D-13 set the precedent (BUG-09 monitor closure) — observe first, fix second.

---

### 10. Phase 77 MPRIS2 Cross-File Test Repair (FIX-MPRIS)

**Scope (from PROJECT.md "Current State" line 60):** 7 MPRIS2 cross-file failures D-03-deferred to follow-up phase — see 77-06-SUMMARY.md.

**Without reading 77-06-SUMMARY.md directly (not in my required reading set)**, the likely failure shapes based on Phase 77's deliverables (shared FakePlayer + parity drift-guards):
- **Most likely:** parity drift-guard tests that pin `Player.__dict__` signal names + arity against `tests/_fake_player.py`. After Phase 78/80/82/83/84 added new signals to Player, FakePlayer drifted.
- **Possible:** environment gating — tests need `QT_QPA_PLATFORM=offscreen` AND a D-Bus session; CI workflow lacks one of those.
- **Possible (lower likelihood):** actual MPRIS2 wiring bug surfaced after the Phase 77 test infrastructure was hardened.

**Integration impact:** none on shipping code. Tests-only deliverable, surgical changes. Risk LOW.

**Sequence:** can land in parallel with any other v2.2 phase, no dependencies. Recommend slotting it as a small mid-milestone phase between two larger pieces of work to give review headspace.

---

## Suggested Build Order (Dependency-Respecting)

The order below groups related work and respects dependencies. Each "tier" can run roughly in parallel internally; tiers are sequential.

### Tier 1 — Spike & Foundation (Week 1)
Parallel:
- **Phase A — Linux packaging spike** (HIGH RISK): conda-on-Linux + linuxdeploy-plugin-gstreamer feasibility. Findings feed Phases B + C.
- **Phase B — FIX-MPRIS (Phase 77 7 deferred tests)**: tests-only, no dependencies, frees up the run-all-tests-clean baseline before larger work lands.

### Tier 2 — Linux Packaging Build (Weeks 2-3)
Sequential within tier (each depends on the previous):
- **Phase C — `packaging/linux/common/` groundwork** + the shared bundle script. Outputs the flat dist tree both downstream phases consume.
- **Phase D — AppImage build pipeline** (SEED-009): consumes Phase C output; produces `MusicStreamer-<version>-x86_64.AppImage`. Includes desktop integration (`.desktop`, MIME, MPRIS continuity test, Node bundling). Empirical smoke on Ubuntu LTS + Fedora.
- **Phase E — Flatpak build pipeline**: parallel-but-late — GNOME SDK ≠ conda, so it doesn't inherit from Phase C+D directly; but Flatpak's data-migration story benefits from Phase D shaking out the cookies/DB/asset path expectations first. Can also run partly in parallel with Phase D if engineering capacity allows.

### Tier 3 — Windows Polish (Week 4, one Win11 VM session)
- **Phase F — WIN-02 + VER-02-J + WIN-05 retest bundle**: one cohesive Win11 VM UAT session. Per PROJECT.md they're explicitly bundled. WIN-02 is the SMTC AUMID work; VER-02-J is the version-display UAT carry-over; WIN-05 is the AAC retest from Phase 69. Inno Setup tweaks only; no new Python code.

### Tier 4 — Channel-Avatar Infrastructure (Week 5)
Sequential (DB migration first):
- **Phase G — DB migration + storage layout**: adds `channel_avatar_path` column + `assets/channel-avatars/` directory; minimal repo.py changes. Feeds Phases H + I.
- **Phase H — YT channel avatar fetch + cover-slot swap**: `yt_import.fetch_channel_avatar()` + `edit_station_dialog.py` trigger + NowPlayingPanel ICY-disabled cover-slot branch.
- **Phase I — Twitch channel avatar fetch**: `twitch_helix.py` + reuse Phase H's cover-slot integration. Smaller than H because it shares the storage + UI path.

### Tier 5 — GBS Polish (Week 6)
Sequential (marquee groundwork first):
- **Phase J — GBS marquee + themed-day detection**: `gbs_marquee.py` module + `_GbsMarqueeWorker` QThread + banner widget + themed-logo session detection. Uses Phase 76's cookie infrastructure unchanged.
- **Phase K — GBS zero-token add affordance**: `_GbsAddSongWorker` + `gbs_api.add_song_zero_token()` + UI in NowPlayingPanel. Depends on Phase J's token-count state coupling.

### Tier 6 — SomaFM Preroll Debug (Week 7)
Spike-then-fix:
- **Phase L — Preroll instrumentation**: `preroll_log.py` size-rotated event log + wiring at decision points in `player.py`. NO behavior change. Ship + observe.
- **Phase M (conditional) — Preroll fix**: contingent on what Phase L's log reveals after 1-2 days of real listening. Mirror Phase 78/84 ship-and-monitor pattern.

### Tier 7 — Carry-Overs (mid-milestone slot-in)
- **Phase N — FIX-PLS (Phase 58 PLS URL-fallback for codec/bitrate)** — from the pending-todo carry-over list in PROJECT.md. Small phase, can slot in any week mid-milestone.
- **Phase O — BUFFER-MONITOR follow-up (Phase 84 2-week monitor)** — CONDITIONAL on Follow-Up Triggers per 84-VERIFICATION.md. May not fire at all.

**Total estimate:** 7-10 phases across ~6-8 weeks if all features land; 5-6 phases minimum if Flatpak defers to v2.3.

---

## Risky Integration Points (Spike-First Recommended)

| Risk | Why | Mitigation |
|------|-----|-----------|
| **linuxdeploy-plugin-gstreamer + conda paths** | Plugin assumes distro `/usr/lib/gstreamer-1.0`; conda env lives in `$CONDA_PREFIX/lib/gstreamer-1.0`. Empirical Phase 43/69 finding: GStreamer plugin discovery is fragile — `GST_PLUGIN_PATH` env var must be set in `AppRun`, scanner binary must be co-located, gst-registry rebuild fires on every launch if cache TTL is wrong. | Tier 1 Phase A spike — produce a working hello-world AppImage with conda's GStreamer playing a remote MP3 stream BEFORE committing to the full milestone scope. |
| **Flatpak QtWebEngine + oauth_helper** | Flatpak's GNOME SDK ships QtWebEngine but `--socket=wayland` + Chromium sandbox-in-sandbox is known to require `--device=dri` and/or `--share=ipc` permissions. Phase 76's subprocess pattern was designed for an un-sandboxed runtime. | Tier 2 Phase E spike — verify GBS.FM login works end-to-end inside Flatpak. If it doesn't, fall back to AppImage-only for v2.2 and defer Flatpak. |
| **GBS marquee scraping resilience** | gbs.fm is a Django site; the marquee element's CSS selector may not be stable. Phase 60 already documents auth-page brittleness. | Tier 5 Phase J: pin selector to `<span class="marquee">` AND validate via a known-good HTML fixture in tests; tolerate selector miss by returning `MarqueeState(announcement="", themed_logo_url=None)`. |
| **SMTC AUMID still showing "Unknown app"** | Existing test (`test_aumid_string_parity.py`) proves literal parity. Failure mode is upstream — AUMID-binding ordering, or Windows Notification Platform registry state. | Tier 3 Phase F spike: WPR (Windows Performance Recorder) trace + `Get-StartApps` Powershell verification BEFORE writing any new code. May reveal the fix is registry cleanup, not packaging. |
| **SomaFM preroll absence root cause** | Hypothesis space is wide (4 hypotheses listed above). Premature fix risks Phase 84-style ship-and-rollback. | Tier 6: instrumentation-only first; gather 1-2 days of real data before designing fix. Mirror Phase 84 D-13 waived-statistical-gate precedent. |
| **DB migration for `channel_avatar_path`** | `repo.py:db_init()` is a frequently-touched, mature schema. Migration must be additive + idempotent (existing pattern in `repo.py:234` for stations_new dance). | Tier 4 Phase G: write migration with rollback test (down-migration not needed but forward-idempotency required). Drift-guard `tests/test_repo.py`. |

---

## Anti-Patterns to Avoid (Project-Specific)

### Anti-Pattern: GStreamer-mock-based testing of preroll changes
**What people do:** Write pytest that mocks `pipeline.emit("about-to-finish")` to test preroll wiring.
**Why it's wrong:** Per `feedback_gstreamer_mock_blind_spot.md` (auto-memory), pipeline mocks pass through any `pipeline.emit(...)` call. Tests pass even when real GStreamer wouldn't fire the signal because of, e.g., a playbin3 vs. playbin 1.x signal-name mismatch.
**Do this instead:** Pair every mock-based preroll test with a source-level grep gate that bans legacy `playbin` 1.x signals on playbin3 code paths. Phase 83 + 84 already shipped instances; follow that template in Phase L preroll work.

### Anti-Pattern: "Mirror moOde/JAS/mpd" decisions without citing source
**What people do:** Justify a packaging or marquee decision with "this is how moOde does it" but paraphrase.
**Why it's wrong:** Per `feedback_mirror_decisions_cite_source.md` (auto-memory), Phase 70 D-04 burned a full phase chasing a paraphrased moOde decision that turned out not to be load-bearing.
**Do this instead:** Every "mirror X" in v2.2 must quote the specific rule + permalink. Especially relevant for Flatpak (mirror Flathub policy) + AppImage (mirror linuxdeploy docs) + GBS marquee (mirror gbs.fm response structure).

### Anti-Pattern: Sweeping UI fixes for marquee/banner before extreme-value testing
**What people do:** Tweak GBS banner layout to fix a perceived overflow; ship.
**Why it's wrong:** Per `feedback_ui_bug_verify_with_extremes.md` (auto-memory), Phase 72.4 burned three rounds chasing layout corruption that was really an extreme value (empty/maxed widget state).
**Do this instead:** Before any GBS banner UI fix, sweep the widget through {empty announcement, 1-char announcement, 280-char marquee text, hidden state}. Same discipline for channel-avatar cover-slot integration.

### Anti-Pattern: Forking sibling/recent-played logic for GBS announcements
**What people do:** Special-case GBS announcements inside StationListPanel.
**Why it's wrong:** Phase 71 sibling work + Phase 67 similar-stations work both proved that cross-concern UI surfaces fragment fast. Announcements are NOT siblings.
**Do this instead:** GBS announcement banner lives strictly inside NowPlayingPanel. It does not interact with StationListPanel's filter chips, recently-played, or favorites view.

### Anti-Pattern: AppImage that bundles distro GStreamer instead of conda's
**What people do:** Use `linuxdeploy-plugin-gstreamer` against `/usr/lib/gstreamer-1.0`.
**Why it's wrong:** Linux distros ship varying GStreamer versions (Ubuntu 22.04: 1.20, Fedora 40: 1.24, Arch: 1.26+). Phase 43/69 found that AAC playback requires gst-libav 1.28+; bundling distro gstreamer means AAC stations break on Ubuntu LTS.
**Do this instead:** Mirror Phase 43+69 conda-forge recipe exactly. AppImage built ON Ubuntu LTS but bundling CONDA's gst-libav 1.28 means it runs cleanly on every distro that satisfies AppImage's glibc floor.

---

## Integration Points — External Services (v2.2 additions only)

| Service | v2.2 use | Integration pattern | File |
|---------|----------|---------------------|------|
| gbs.fm marquee/homepage HTML | Marquee scrape + logo URL extraction | `urllib.request` + lightweight HTML parser (re or `html.parser`); cookies from `gbs_api._load_cookies()`. NO BeautifulSoup4 dependency (deliberate — keep dep count low). | `musicstreamer/gbs_marquee.py` (new) |
| api.twitch.tv/helix/users | Profile-image-url fetch | `urllib.request` + Client-Id header + auth-token cookie. Single GET; cache result indefinitely (refresh only on edit-dialog "Refresh avatar"). | `musicstreamer/twitch_helix.py` (new) |
| youtube.com channel page | Channel avatar via yt-dlp | Reuse existing `yt_dlp.YoutubeDL` extraction; new function in `yt_import.py`. | `musicstreamer/yt_import.py` (existing, extended) |
| AppImage update channel | None for v2.2 — no auto-update | If a future milestone needs auto-update, zsync-over-HTTPS is the AppImage-native pattern. Defer. | n/a |
| Flathub | Submission only — no runtime API | `.metainfo.xml` + screenshot URLs; submission PR against `flathub/flathub`. May defer to v2.3. | `packaging/linux/flatpak/` |

---

## Internal Boundaries — New + Modified

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `gbs_marquee.py` ↔ `now_playing_panel.py` | `_GbsMarqueeWorker` QThread + queued `Signal(object)` | Mirror of `aa_live.py` ↔ `_AaLiveWorker` (exactly the same shape). Worker is owned by NowPlayingPanel for lifecycle parity with `_aa_live_worker` at line 341. |
| `yt_import.fetch_channel_avatar()` ↔ `edit_station_dialog.py` | `ThreadPoolExecutor` daemon + Qt-queued callback | Mirror of Phase 17 AA logo download workers (`aa_import.py:266`). |
| `twitch_helix.py` ↔ `edit_station_dialog.py` | Same as YT — `ThreadPoolExecutor` + callback | Single shared `ChannelAvatarFetcher` orchestrator OR two parallel call sites. Recommend parallel (simpler; no cross-provider coupling). |
| `preroll_log.py` ↔ `player.py` | Direct call from `_start_preroll` + `_on_preroll_about_to_finish` decision points | Mirror of `buffer_log.py` integration (Phase 78). Synchronous append; lock-free single-writer. |
| `packaging/linux/common/` ↔ AppImage/Flatpak recipes | File-system handoff (dist tree) | Both downstream recipes consume `packaging/linux/common/dist/`. Treat as immutable artifact between tiers. |
| `MusicStreamer.iss` ↔ `__main__.py:_set_windows_aumid` | Test-enforced literal parity (`tests/test_aumid_string_parity.py`) | DO NOT add a third literal site — drift-guard burden grows quadratically. |

---

## Sources

- `.planning/PROJECT.md` (v2.2 milestone definition — lines 11-23)
- `.planning/codebase/ARCHITECTURE.md` (2026-04-28 codebase audit)
- `.planning/codebase/STRUCTURE.md` (directory layout, where-to-add-code conventions)
- `.planning/codebase/INTEGRATIONS.md` (external service catalogue + cookie/auth storage map)
- `.planning/seeds/SEED-009-linux-appimage-install.md` (AppImage scope + breadcrumbs)
- `.planning/seeds/SEED-008-gbs-fm-integration.md` (closed by v2.1; pattern reference)
- `musicstreamer/player.py` (2100 LOC; preroll + failover wiring lines 270-705)
- `musicstreamer/aa_live.py` (Phase 68 — canonical live-data poll pattern)
- `musicstreamer/oauth_helper.py` (Phase 76 GBS login subprocess; cookie harvest pattern)
- `musicstreamer/ui_qt/now_playing_panel.py` (2978 LOC — where every UI integration lands)
- `musicstreamer/yt_import.py` (yt-dlp pattern; cookie temp-copy invariant)
- `musicstreamer/gbs_api.py` (1232 LOC — extend, don't replace)
- `musicstreamer/paths.py` (XDG-rooted; Flatpak sandbox redirects automatically)
- `packaging/windows/build.ps1` + `MusicStreamer.iss` + `README.md` (Phase 43/44/69 patterns to mirror on Linux)
- Auto-memory: `feedback_gstreamer_mock_blind_spot.md`, `feedback_mirror_decisions_cite_source.md`, `feedback_ui_bug_verify_with_extremes.md`, `reference_musicstreamer_db_schema.md`

---

*Architecture research for: MusicStreamer v2.2 Package Building and QOL features/tweaks*
*Researched: 2026-05-25*
