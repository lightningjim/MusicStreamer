# Feature Research — MusicStreamer v2.2

**Domain:** Personal GNOME desktop streaming app — packaging parity + targeted QOL polish
**Researched:** 2026-05-25
**Confidence:** HIGH (packaging best-practices verified against official Flathub/AppImage docs; UX recommendations drawn from established design-system patterns; provider-avatar APIs confirmed via current YouTube/Twitch developer documentation)

## Scope Note

This is a **subsequent milestone** for an existing, shipped product (v2.1, 1462 tests passing, 42 phases delivered). The "table stakes vs. differentiator" framing here is scoped to **what v2.2 is adding** — not what users expect from a streaming app in general (that was answered across v1.0–v2.1). Every feature below presumes the v2.1 baseline is intact.

The six v2.2 capability areas (per `milestone_context`):
1. Linux AppImage distribution
2. Linux Flatpak distribution
3. GBS.FM themed-day detection (logo hash drift + marquee keyword sniff)
4. GBS.FM announcement banner (first pipe-segment of marquee)
5. GBS.FM zero-token single-song add (UX never framed as "1 token")
6. Provider channel-avatar in cover slot for ICY-disabled YT/Twitch stations

Plus pre-committed carry-overs: Windows SMTC AUMID Start-Menu shortcut (WIN-02), Win11 packaging UAT (VER-02-J + WIN-05 retest), SomaFM preroll consistency, Phase 77 MPRIS2 test repair, PLS URL fallback (FIX-PLS), and the conditional 2-week buffer-events.log monitor.

## Feature Landscape

### Table Stakes (Users Expect These for the New Capabilities)

Features users will assume exist the moment a v2.2 capability lands. Missing these = the new capability feels half-built.

| # | Feature | Why Expected | Complexity | Depends On |
|---|---------|--------------|------------|------------|
| TS-01 | **AppImage runs from any location, no install step** | Core AppImage promise — download-and-double-click portability. If user has to extract or run setup, it's not a real AppImage. | LOW | None (PyInstaller already produces a portable bundle) |
| TS-02 | **AppImage `.desktop` integration when launched via AppImageLauncher** | Without it, users see no menu entry / no icon and assume the app didn't install. AppImageLauncher prompts on first run; we just need to embed a valid `.desktop` + icon in the AppDir. | LOW | linuxdeploy `--desktop-file` + icon at `usr/share/icons/hicolor/256x256/apps/musicstreamer.png` |
| TS-03 | **AppImage bundles its own GStreamer + Qt + Node.js** | Users expect zero dependency surprises. Existing PKG-04 conda-forge approach on Windows proves the model; Linux must match. linuxdeploy-plugin-gstreamer + linuxdeploy-plugin-qt are the canonical tools. | MEDIUM | Phase 43 plugin-presence lessons + PKG-04 conda recipe (must reapply learning about `gst-libav` for AAC) |
| TS-04 | **AppImage embeds update info (zsync URL)** even if v2.2 doesn't ship an actual update server | AppImageUpdate is the de-facto standard. Even if we never publish a delta, embedding the field makes the binary forward-compatible. **Always with user consent** — never silent. | LOW | None — appimagetool flag |
| TS-05 | **AppImage does NOT register MIME associations for `.pls`/`.m3u`** | This is what users of a curated-library app actually expect. Surfaced here because Flathub reviewers will ask. Anti-pattern explained in AF-01. | n/a | n/a |
| TS-06 | **Flatpak audio works without Flatseal hand-tuning** | Users expect "install from Flathub → launch → audio works." Requires `--socket=pulseaudio` in finish-args. Anything that forces Flatseal is a Flathub review fail. | LOW | finish-args boilerplate |
| TS-07 | **Flatpak MPRIS2 controls work with GNOME media keys** | Existing v2.0 MPRIS2 backend must survive sandbox. Requires `--own-name=org.mpris.MediaPlayer2.musicstreamer` (or the AUMID we pick) in finish-args, NOT `--socket=session-bus`. | MEDIUM | ARCHITECTURE.md MPRIS2 D-Bus contract; Flathub forbids broad session-bus access for non-dev-tools |
| TS-08 | **Flatpak network access** | Streaming app — obviously needs it. `--share=network`. | LOW | None |
| TS-09 | **Flatpak settings persist between launches** | `~/.var/app/<id>/data/musicstreamer.sqlite3` should work transparently. Code must use XDG_DATA_HOME (already does via `paths.py`). | LOW | `paths.py` already XDG-correct |
| TS-10 | **Flatpak auto-updates via GNOME Software / `flatpak update`** | This is the entire pitch of Flatpak vs. AppImage. Falls out for free once we're on Flathub. | LOW | Flathub submission |
| TS-11 | **GBS.FM themed-logo detected within the session of joining the GBS view** | If user opens GBS and the logo doesn't reflect today's theme, the feature is invisible. Session-scoped fetch at GBS tab open (per milestone_context) is the right scope. | LOW–MED | Phase 76 QtWebEngine subprocess (cookied logo URL fetch) |
| TS-12 | **GBS.FM announcement banner is dismissible** | Persistent in-window banners without a dismiss control are universally hated. Established UX rule: persistent banners must be dismissible; one-shot info is auto-fade toast. Carbon and Fluent both codify this. | LOW | New banner widget — sits above StationListPanel/NowPlayingPanel split |
| TS-13 | **GBS.FM zero-token affordance works exactly once when tokens=0 AND queue is empty** | This is the literal user expectation per milestone_context: "out of tokens but no queued song, present the affordance as a single-use add button." Anything else is a bug. | LOW | Phase 60.4 token counter / Phase 76 GBS-AUTH-01 |
| TS-14 | **Channel avatar in cover slot loads within ~1s of station play for ICY-disabled stations** | Users won't wait. The slot currently shows the duplicate thumbnail "fast" — replacement must be at least as fast or the change reads as a regression. Pre-fetch + disk cache required. | MEDIUM | Phase 73 cover-art cache pattern (iTunes session dedup model); new YT/Twitch avatar cache layer |
| TS-15 | **Channel avatar fallback to existing thumbnail when avatar unavailable** | YouTube channel data fetch can fail (rate limit, network). Must degrade to the v2.1 behavior, not blank slot. | LOW | Existing cover-slot fallback chain |
| TS-16 | **SomaFM prerolls actually play on stations that currently miss them (Boot Liquor etc.)** | Regression-class bug — Phase 74 set the expectation that all SomaFM stations have prerolls. Inconsistency surprises users. | MEDIUM | Phase 74 (SOMA-01..17) preroll wiring |
| TS-17 | **Windows SMTC Start-Menu shortcut sets correct AUMID** | WIN-02 carry-over. Without it, SMTC media keys break on first-launch-from-Start-Menu (Inno installer currently produces a shortcut without the `System.AppUserModel.ID` property). Documented in v2.1 close. | LOW | v2.0 Phase 43.1 AUMID setting (Python side already does it; the shortcut file itself needs the matching AUMID property) |

### Differentiators (Set v2.2 Apart from "Just Another Streaming App")

Features that lean into MusicStreamer's curated-library identity and the niche GBS.FM/SomaFM integrations. Not table stakes for streaming apps in general, but **table stakes for *this* app's identity**.

| # | Feature | Value Proposition | Complexity | Depends On |
|---|---------|-------------------|------------|------------|
| D-01 | **AppImage + Flatpak ship simultaneously** (not one or the other) | Most niche Linux apps ship only AppImage *or* only Flatpak. Shipping both at v2.2 launch covers the two largest Linux desktop user populations (portable-binary purists + GNOME Software / Discover users) without forcing a choice. | HIGH (two pipelines, but mostly independent) | TS-01..10 |
| D-02 | **GBS.FM themed-day detection via logo hash drift** | Niche radio stations often swap their logo for holidays / station birthdays / themed days. Detecting it automatically (via SHA-256 of `logo_3.png` vs. last-known hash) lets the app surface "today is special" without GBS.FM exposing any structured API. Genuine craft signal. | MEDIUM | Phase 76 in-app login subprocess (cookied logo fetch); SQLite key for last-known hash |
| D-03 | **GBS.FM themed-day surfaces visually distinct from announcement banner** | Two signals (themed-day + marquee announcement) must not be conflated in UI. Themed-day = ambient (replaced logo, optional accent retint); announcement = explicit (top banner with text). The differentiator is *not collapsing them into one notification*. | MEDIUM | D-02; existing accent retint plumbing (Phase 75) |
| D-04 | **GBS.FM announcement banner surfaces only when marquee text is NEW** | Permanently-on banner = noise. Hash the first pipe-segment, store last-seen hash in SQLite, only show banner when hash changes. Restores to "seen" state on user dismiss. This is the UX that respects the user's attention. | MEDIUM | Banner widget; SQLite key `gbs_last_seen_announcement_hash` |
| D-05 | **GBS.FM zero-token affordance worded as action, not currency** | "Add a song" / "Queue 1 song" — never "Use your last token." Milestone_context is explicit: the feature must "never be framed as '1 token'." This follows through the GBS-AUTH-01 token-paste DROP (Phase 76 D-03): we deliberately keep the user out of the token-economy mental model. | LOW | Phase 76 GBS panel UI |
| D-06 | **Provider channel-avatar uses circular crop** (vs. square station logo) | YouTube and Twitch both use circular avatars throughout their own UIs. Matching that visual convention in the cover slot signals "this is a creator, not a radio brand." Visually distinguishes ICY-disabled creator streams from radio streams at a glance. | LOW | QPixmap clip-path; existing cover-slot QLabel |
| D-07 | **AppImage embeds a hand-designed `.desktop` icon at multiple resolutions** (256, 128, 64, 48, 32) | Most AppImages ship one icon size or rely on extraction-time scaling artifacts. Multi-size hicolor icon theme makes the app look native at any HiDPI factor (even though our deploy target is DPR=1.0 per MEMORY.md, Flathub review checks this). | LOW | Existing app icon asset |
| D-08 | **Flatpak uses `--filesystem=xdg-music:ro` or zero filesystem perms** | Most audio apps over-request filesystem access. We're streaming-only (no local files per PROJECT.md Out of Scope) — we genuinely need zero filesystem perms beyond the app's own `~/.var/app/<id>/`. This is a positive signal during Flathub review. | LOW | None — just don't add filesystem= to finish-args |

### Anti-Features (Will Be Requested, Must Decline)

Features that seem reasonable but conflict with the v2.2 scope, project identity, or the existing user contract.

| # | Feature | Why It Seems Good | Why It's Wrong Here | Alternative |
|---|---------|-------------------|---------------------|-------------|
| AF-01 | AppImage / Flatpak registers as default handler for `.pls` / `.m3u` files | "User clicks a playlist link, my app opens" | MusicStreamer is a curated-library app, not a generic stream player. PROJECT.md explicitly excludes "Local music library / file playback" from scope. MIME handler registration would invite users to dump arbitrary playlists at the app and complain when they don't show up in the library. | Keep the import flows (Import dialog → AudioAddict / YouTube / Radio-Browser tabs) as the only entry points. |
| AF-02 | Snap packaging | "More users can install it" | User explicitly chose AppImage + Flatpak per milestone_context. Snap's auto-update model is more invasive and its sandbox semantics differ from Flatpak in ways that would force a third packaging code path. | Decline. Document in PROJECT.md Out of Scope alongside iOS / Android / Web. |
| AF-03 | Flatpak with `--filesystem=home` | "Easier than thinking about portals" | Flathub reviewers will reject or downgrade trust score; users will (rightly) flag in Flatseal that the app over-reaches. We have no use case requiring home access. | Use only the app's own per-app data dir + portals for the file-picker import flows (which already work via the standard Qt FileDialog, which is portal-routed inside Flatpak automatically). |
| AF-04 | Flatpak with broad `--socket=session-bus` for MPRIS2 | "MPRIS2 needs D-Bus" | Flathub forbids broad session-bus for non-dev-tools. Correct pattern is `--own-name=org.mpris.MediaPlayer2.<id>` which scopes us to the one well-known name we need. | Use `--own-name` only. Verify MPRIS2 client (gnome-shell / playerctl) can still talk to us — they can, via the standard MPRIS2 discovery flow. |
| AF-05 | Themed-day push notification (libnotify toast on day-of) | "Tell the user something special is happening" | Pushing OS-level notifications for a desktop streaming app is the kind of behavior users disable globally and never re-enable. The themed logo IS the notification. | Surface only in-app: themed logo + (separately) the announcement banner when marquee is new. |
| AF-06 | Themed-day persists in UI until dismissed (carries across days) | "User shouldn't miss it" | If the theme is a logo swap initiated by GBS, the theme ends when GBS ends it (next logo fetch returns the default hash). Don't manufacture a persistence layer that fights the upstream signal. | Session-scoped fetch + cache (per milestone_context); next session re-checks. |
| AF-07 | Zero-token affordance always visible (even when tokens > 0) | "Discoverability" | Phase 76 already surfaces the token count. A persistent "add a song" button that does different things based on token state is confusing. The affordance must appear ONLY when (tokens == 0 AND queue is empty) — that's its meaning. | Conditional render gated on `tokens == 0 and queue_len == 0`. |
| AF-08 | Channel avatar replaces logo slot too (not just cover slot) | "Consistency" | The logo slot is the station identity. Replacing it with a YouTube channel avatar conflates "the station I curated" with "the creator behind it." Cover slot is the right place — it was the duplicate before, now it's the creator badge. | Cover slot only; logo slot keeps the station-as-curated-by-me identity. |
| AF-09 | Channel avatar refreshed on every play | "Always fresh" | YouTube avatars change ~never; Twitch avatars change ~monthly at most. Refreshing on every play burns API quota and adds latency for zero user benefit. | One-time fetch on station create/edit + a manual "refresh" affordance in EditStationDialog (matches the existing YT thumbnail refresh pattern from Phase 6/17). |
| AF-10 | AppImage silent auto-update on launch | "Always current" | AppImageUpdate docs are explicit: never download updates without user consent. Silent auto-update is a privacy/bandwidth/trust violation. | Embed zsync URL (so AppImageUpdate *can* update); show "Update available" non-blocking toast on launch when a newer build is detected; require explicit user click. |

## Feature Dependencies

```
v2.1 baseline (assumed intact)
├── Phase 76 (GBS-AUTH-01 QtWebEngine login subprocess)
│    ├── D-02 themed-day logo hash fetch
│    ├── D-04 marquee announcement fetch
│    └── D-05 zero-token affordance state
│
├── Phase 60.4 (GBS token counter)
│    └── TS-13/AF-07 zero-token affordance gating
│
├── Phase 74 (SomaFM SOMA-01..17)
│    └── TS-16 SomaFM preroll consistency fix
│
├── Phase 73 (cover-art cache pattern + 1 req/sec gate)
│    └── TS-14 channel avatar cache + rate limit (Twitch Helix)
│
├── Phase 47 (stream ordering / codec rank)
│    └── (no new v2.2 dependency, but FIX-PLS lives in this codepath)
│
├── v2.0 Phase 43.1 (Windows AUMID setting)
│    └── TS-17 WIN-02 Start-Menu shortcut AUMID
│
└── Phase 77 (deferred items reconciliation)
     └── FIX-MPRIS test repair (7 MPRIS2 cross-file failures)

v2.2 internal dependencies:
TS-01..05 (AppImage) ──independent of── TS-06..10 (Flatpak)
       │                                       │
       └────────── D-07 hicolor multi-size icon shared ─────────┘

TS-11 (themed-day fetch) ──before── D-02 (logo hash drift logic)
                              ──before── D-03 (visual distinction from announcement)

TS-12 (banner dismissible) ──before── D-04 (banner appears only on new hash)

TS-13 (zero-token works once) ──before── D-05 (wording: "Add a song", not "1 token")

TS-14 (avatar load <1s) ──before── D-06 (circular crop) — perf first, polish second

TS-16 (SomaFM preroll fix) ──independent── of all other v2.2 work (carry-over)
TS-17 (WIN-02 AUMID shortcut) ──independent── (Windows-only, no other deps)
```

### Dependency Notes

- **Phase 76 is the keystone**: three of the six v2.2 capability areas (themed-day, announcement banner, zero-token UX) reuse the QtWebEngine subprocess Phase 76 established. If Phase 76's session storage / cookie jar behavior changes, all three are affected.
- **AppImage and Flatpak are independent tracks**: they share the hicolor icon asset (D-07) and the application logic (no code changes for sandbox awareness, since `paths.py` already uses XDG dirs), but their build pipelines, finish-args / desktop files, and update mechanisms are fully separate. Can ship in either order.
- **Channel avatar work depends on cover-art cache pattern from Phase 73**, not iTunes specifically. The 1 req/sec gate is iTunes-specific; Twitch Helix has its own (much higher) rate limit. YouTube channel snippet via yt-dlp is essentially free (we already fetch video metadata; channel snippet is a separate API call but rare).
- **TS-13 + D-05 are the same feature decomposed by lens**: TS-13 is the functional requirement (works exactly once), D-05 is the UX framing (wording). Implementation is a single widget but reviewer should check both.
- **FIX-MPRIS (Phase 77 carry-over) blocks Flatpak validation**: if the MPRIS2 tests don't pass before Flatpak submission, we can't guarantee MPRIS2 works in-sandbox. Sequence: fix MPRIS tests → Flatpak build → manual MPRIS-in-Flatpak verification.

## MVP Definition

### Must Ship in v2.2 (P1)

The milestone goal per PROJECT.md is "packaging parity" — AppImage + Flatpak are non-negotiable. The GBS.FM and ICY-disabled polish are the headline QOL.

- [ ] **TS-01..05 AppImage** with `.desktop`, icon, GStreamer plugins bundled, zsync update info embedded
- [ ] **TS-06..10 Flatpak** with minimal finish-args, MPRIS2 via `--own-name`, on Flathub
- [ ] **TS-11 + D-02 + D-03 GBS.FM themed-day** detection + session-scoped + visually distinct from banner
- [ ] **TS-12 + D-04 GBS.FM announcement banner** dismissible + new-hash gated
- [ ] **TS-13 + D-05 GBS.FM zero-token affordance** worded as action, gated on `(tokens==0 AND queue empty)`
- [ ] **TS-14 + TS-15 + D-06 + AF-09 channel avatar** in cover slot for ICY-disabled YT/Twitch, circular, cached, fallback-safe, refresh-on-demand
- [ ] **TS-16 SomaFM preroll consistency** (carry-over investigation + fix)
- [ ] **TS-17 WIN-02 SMTC AUMID Start-Menu shortcut**
- [ ] **FIX-MPRIS** Phase 77's 7 D-03-deferred MPRIS2 cross-file test failures repaired
- [ ] **VER-02-J + WIN-05** Win11 VM packaging UAT (sign-off bundled)

### Should Add If Capacity Allows (P2)

- [ ] **D-07 hicolor multi-resolution icon set** — quality polish, low effort, only needs design pass once
- [ ] **D-08 Flatpak with zero filesystem permissions** explicitly documented (vs. just "we didn't add any") — defensible answer for Flathub reviewer
- [ ] **FIX-PLS Phase 58 PLS URL-fallback for codec/bitrate** (carry-over pending todo)

### Conditional (P3 — Trigger-Gated)

- [ ] **BUFFER-MONITOR 2-week follow-up** — only if any of the 3 Follow-Up Triggers in 84-VERIFICATION.md fires during v2.2 dev window
- [ ] **AppImage publishing infrastructure** (zsync server, release feed) — only if user actually wants to ship updates between milestones; for v2.2, embedding the update info is sufficient

### Out of Scope (Document in PROJECT.md if Asked)

- Snap packaging (AF-02)
- AppImage MIME associations for `.pls` / `.m3u` (AF-01)
- Themed-day system notifications (AF-05)
- Channel avatar replacing logo slot (AF-08)
- Silent auto-update (AF-10)

## Feature Prioritization Matrix

| # | Feature | User Value | Implementation Cost | Priority |
|---|---------|------------|---------------------|----------|
| TS-01 | AppImage portable run | HIGH | LOW | P1 |
| TS-02 | AppImage .desktop integration | HIGH | LOW | P1 |
| TS-03 | AppImage bundles GStreamer/Qt/Node | HIGH | MEDIUM | P1 |
| TS-04 | AppImage embeds zsync update info | MEDIUM | LOW | P1 |
| TS-06 | Flatpak audio (pulseaudio socket) | HIGH | LOW | P1 |
| TS-07 | Flatpak MPRIS2 via --own-name | HIGH | MEDIUM | P1 |
| TS-08–10 | Flatpak network/data/updates | HIGH | LOW | P1 |
| TS-11 | Themed-day session-scoped fetch | MEDIUM | LOW–MED | P1 |
| TS-12 | Banner dismissible | HIGH (avoids annoyance) | LOW | P1 |
| TS-13 | Zero-token affordance works once | HIGH | LOW | P1 |
| TS-14 | Avatar loads <1s | HIGH | MEDIUM | P1 |
| TS-15 | Avatar fallback to thumbnail | HIGH | LOW | P1 |
| TS-16 | SomaFM preroll consistency | MEDIUM | MEDIUM | P1 |
| TS-17 | WIN-02 SMTC AUMID shortcut | HIGH (on Windows) | LOW | P1 |
| D-01 | Both AppImage + Flatpak at launch | HIGH | HIGH (two pipelines) | P1 |
| D-02 | Themed-day via logo hash drift | MEDIUM | MEDIUM | P1 |
| D-03 | Themed-day visually distinct from banner | HIGH (UX clarity) | MEDIUM | P1 |
| D-04 | Banner only on new hash | HIGH | MEDIUM | P1 |
| D-05 | Zero-token worded as action | HIGH | LOW | P1 |
| D-06 | Avatar circular crop | MEDIUM | LOW | P1 |
| D-07 | Hicolor multi-size icon | LOW | LOW | P2 |
| D-08 | Flatpak zero-filesystem-perms documented | MEDIUM (review signal) | LOW | P2 |
| FIX-MPRIS | Phase 77 MPRIS2 tests | HIGH (blocks Flatpak verify) | MEDIUM | P1 |
| FIX-PLS | Phase 58 PLS URL-fallback | LOW–MED | LOW | P2 |
| BUFFER-MONITOR | 2-week buffer-events.log watch | conditional | LOW (if triggered) | P3 |

## Competitor / Reference Feature Analysis

The closest reference points for v2.2's packaging + niche-radio-app patterns:

| Feature Area | Reference 1 | Reference 2 | MusicStreamer Approach |
|--------------|-------------|-------------|------------------------|
| Audio app on Flathub | Amberol (GNOME) — minimal finish-args, MPRIS2 via own-name, `--socket=pulseaudio` only | Lollypop — broader perms, uses `--filesystem=xdg-music` for local library | Mirror Amberol's posture: minimal perms, no filesystem access, MPRIS2 via own-name. We're streaming-only so we're *less* invasive than even Amberol. |
| AppImage Qt+GStreamer | Tenacity / Audacity AppImages — use linuxdeploy-plugin-qt + linuxdeploy-plugin-gstreamer | OBS Studio AppImage — bundles GStreamer via custom script | Use the official linuxdeploy plugins; PyInstaller produces the PySide6 bundle, linuxdeploy walks deps and packages GStreamer plugins per Phase 43 lessons (`gst-libav` for AAC etc.) |
| Themed-day in niche radio | Lainchan radio (themed logo on holidays) | SomaFM (logo doesn't change but station list does — different model) | GBS.FM-specific: hash-drift detection of `logo_3.png`, session-scoped, ambient visual treatment (logo + optional accent retint), never a system notification |
| Persistent announcement banner | GNOME Software "release notes available" banner — top-of-window, dismissible | Slack channel banner — top-of-channel, dismissible, shows again on changes | Match the GNOME Software pattern: above main split, dismissible, hash-gated so it doesn't re-appear until marquee changes |
| Token-economy framing avoidance | Apple Music "Add Station" (no count, just CTA) | Spotify "Save to library" (no count) | Frame as **action** ("Add a song", "Queue 1 song"), never **currency** ("Spend a token") |
| Provider avatar in audio UI | Pocket Casts (podcast avatars circular, cover slot) | Lollypop (album art square, artist photo circular) | Circular crop matches creator-content convention; rectangular logo for radio-station identity stays in the logo slot |

## Open Questions for Requirements Phase

1. **Zero-token wording final pick**: "Add a song" vs. "Queue 1 song" vs. "Queue this song" — needs UAT pass once the widget is wired. Recommendation: start with "Add a song" (shortest, most action-oriented, no implied state).
2. **Themed-day visual treatment**: just the logo swap, or also an accent retint? If both, retint how — sample from new logo's dominant color via existing Phase 59 accent picker code? Recommendation: logo swap only in P1; accent retint as P2 polish if time allows.
3. **Channel avatar fetch path on station create**: should EditStationDialog auto-fetch on URL paste (like the existing YT thumbnail behavior in Phase 6/17) or require a separate button? Recommendation: auto-fetch on paste — consistent with established UX.
4. **AppImage zsync update URL**: where will the release feed live? QNAP Gitea releases, GitHub releases (via mirror), or "embed a 404 URL and never ship updates between milestones"? This is a deploy/infra decision, not a code decision — flag for milestone planning, not blocking.
5. **Flatpak app ID**: `org.gbsfm.MusicStreamer`? `io.github.kcreasey.MusicStreamer`? Reverse-DNS rules from Flathub apply. Needs to be locked before first manifest commit; can't change after Flathub listing.

## Sources

- [AppImageLauncher project](https://appimagelauncher.com/) — first-run prompt UX, integration model
- [AppImage update documentation](https://docs.appimage.org/packaging-guide/optional/updates.html) — zsync embedding, consent requirement
- [AppImageUpdate (zsync2) home](https://appimage.github.io/AppImageUpdate/) — delta update mechanics
- [linuxdeploy user guide](https://docs.appimage.org/packaging-guide/from-source/linuxdeploy-user-guide.html) — AppDir build flow
- [linuxdeploy-plugin-gstreamer (awesome-linuxdeploy list)](https://github.com/linuxdeploy/awesome-linuxdeploy) — GStreamer plugin bundling
- [Flathub requirements](https://docs.flathub.org/docs/for-app-authors/requirements) — app submission rules
- [Flatpak sandbox permissions documentation](https://docs.flatpak.org/en/latest/sandbox-permissions.html) — finish-args reference, audio app guidance
- [Flathub App Submission wiki](https://github.com/flathub/flathub/wiki/App-Submission) — review process, permission minimization
- [Flathub PySide6 BaseApp](https://flathub.org/en/apps/io.qt.PySide.BaseApp) — confirms PySide6 deployment model on Flathub
- [Flatpak XDG Desktop Portal](https://flatpak.github.io/xdg-desktop-portal/) — portal-routed file pickers (free for Qt apps), permission store
- [YouTube Data API channels documentation](https://developers.google.com/youtube/v3/docs/channels) — channel thumbnail (88×88 avatar) via channels.list endpoint
- [Twitch API: avatars via /helix/users (forum thread)](https://discuss.dev.twitch.com/t/avatars-profile-pictures-on-helix-streams/25809) — `profile_image_url` field via `/helix/users?login=<name>` with App Access token
- [Carbon Design System notification pattern](https://carbondesignsystem.com/patterns/notification-pattern/) — toast vs banner distinction
- [LogRocket: Toast notifications UX best practices](https://blog.logrocket.com/ux-design/toast-notifications/) — dismissibility and persistence rules
- [yt-dlp issue #10090: channel thumbnails / avatar_uncropped](https://github.com/yt-dlp/yt-dlp/issues/10090) — confirms yt-dlp exposes channel avatar separately from video thumbnails

---
*Feature research for: MusicStreamer v2.2 packaging + targeted QOL*
*Researched: 2026-05-25*
