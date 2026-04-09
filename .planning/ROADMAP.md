# Roadmap: MusicStreamer

## Milestones

- ✅ **v1.0 MVP** — Phases 1–4 (shipped 2024-03-20)
- ✅ **v1.1 Polish & Station Management** — Phases 5–6 (shipped 2024-03-21)
- ✅ **v1.2 Station UX & Polish** — Phases 7–11 (shipped 2024-03-25)
- ✅ **v1.3 Discovery & Favorites** — Phases 12–15 (shipped 2024-04-03)
- ✅ **v1.4 Media & Art Polish** — Phases 16–20 (shipped 2024-04-05)
- 🚧 **v1.5 Further Polish** — Phase 21–22 (in progress, deadline 2024-04-19)

## Phases

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

### 🚧 v1.5 Further Polish (In Progress — deadline 2024-04-19)

**Milestone Goal:** Fix bugs discovered through daily use; close out v1.x before v2.0 revamp.

- [ ] **Phase 21: Panel Layout Fix** - Fix YouTube thumbnail inflating now-playing panel at max/fullscreen
- [x] **Phase 22: Import YT Cookies** - Let users import YouTube cookies via file/paste/Google login instead of yt-dlp browser extraction (completed 2024-04-07)

## Phase Details

### Phase 21: Panel Layout Fix
**Goal**: The now-playing panel maintains its intended dimensions at all window sizes
**Depends on**: Phase 20
**Requirements**: FIX-01
**Success Criteria** (what must be TRUE):
  1. Playing a YouTube station while the window is maximized does not widen or stretch the now-playing panel
  2. Playing a YouTube station while the window is fullscreen does not widen or stretch the now-playing panel
  3. YouTube 16:9 thumbnails remain contained within the logo slot at all window sizes (letterboxed, no overflow)
  4. Non-YouTube station art and layout are unaffected
**Plans**: TBD
**UI hint**: yes

### Phase 22: Import YT Cookies
**Goal**: Users can import YouTube cookies from file, paste, or Google login; cookies are stored and passed to yt-dlp/mpv on all YouTube operations; GNOME keyring extraction is suppressed
**Depends on**: Phase 21
**Requirements**: COOKIE-01, COOKIE-02, COOKIE-03, COOKIE-04, COOKIE-05, COOKIE-06
**Success Criteria** (what must be TRUE):
  1. Hamburger menu in header bar contains "YouTube Cookies..." item that opens cookie dialog
  2. File picker import copies a valid cookies.txt to app data directory
  3. Paste import writes valid cookie text to app data directory
  4. Google login via embedded browser captures YouTube cookies and saves as cookies.txt
  5. yt-dlp calls always include --no-cookies-from-browser and conditionally include --cookies
  6. mpv calls conditionally include --ytdl-raw-options=cookies=<path>
  7. Cookie file has 0o600 permissions
  8. Dialog shows last-imported date; Clear button removes cookies
**Plans:** 3/3 plans complete

Plans:
- [x] 22-01-PLAN.md — TDD: COOKIES_PATH constant + yt-dlp/mpv flag injection
- [x] 22-02-PLAN.md — CookiesDialog UI (file picker, paste, hamburger menu)
- [x] 22-03-PLAN.md — Google login flow via WebKit2

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Module Extraction | v1.0 | 3/3 | Complete | 2024-03-18 |
| 2. Search and Filter | v1.0 | 2/2 | Complete | 2024-03-19 |
| 3. ICY Metadata Display | v1.0 | 2/2 | Complete | 2024-03-20 |
| 4. Cover Art | v1.0 | 1/1 | Complete | 2024-03-20 |
| 5. Display Polish | v1.1 | 2/2 | Complete | 2024-03-21 |
| 6. Station Management | v1.1 | 2/2 | Complete | 2024-03-21 |
| 7. Station List Restructuring | v1.2 | 3/3 | Complete | 2024-03-22 |
| 8. Filter Bar Multi-Select | v1.2 | 2/2 | Complete | 2024-03-22 |
| 9. Station Editor Improvements | v1.2 | 2/2 | Complete | 2024-03-23 |
| 10. Now Playing & Audio | v1.2 | 2/2 | Complete | 2024-03-24 |
| 11. UI Polish | v1.2 | 2/2 | Complete | 2024-03-25 |
| 12. Favorites | v1.3 | 2/2 | Complete | 2024-03-31 |
| 13. Radio-Browser Discovery | v1.3 | 2/2 | Complete | 2024-04-01 |
| 14. YouTube Playlist Import | v1.3 | 2/2 | Complete | 2024-04-02 |
| 15. AudioAddict Import | v1.3 | 2/2 | Complete | 2024-04-03 |
| 16. GStreamer Buffer Tuning | v1.4 | 1/1 | Complete | 2024-04-03 |
| 17. AudioAddict Station Art | v1.4 | 2/2 | Complete | 2024-04-03 |
| 18. YouTube Thumbnail 16:9 | v1.4 | 1/1 | Complete | 2024-04-05 |
| 19. Custom Accent Color | v1.4 | 2/2 | Complete | 2024-04-05 |
| 20. Playback Controls & Media Keys | v1.4 | 2/2 | Complete | 2024-04-05 |
| 21. Panel Layout Fix | v1.5 | 0/? | Not started | - |
| 22. Import YT Cookies | v1.5 | 3/3 | Complete    | 2024-04-07 |

### Phase 23: Fix YouTube stream playback broken on CLI and app

**Goal:** yt-dlp and mpv use temporary copies of cookies.txt so the original imported file is never overwritten; corrupted cookies trigger automatic retry without auth
**Requirements**: FIX-02, FIX-03
**Depends on:** Phase 22
**Success Criteria** (what must be TRUE):
  1. Original cookies.txt is never modified by yt-dlp or mpv invocations
  2. Temp cookie files are cleaned up after subprocess exits or is stopped
  3. Copy failure falls back to no-cookies playback
  4. mpv retries without cookies if it exits within 2 seconds
**Plans:** 1/1 plans complete

Plans:
- [x] 23-01-PLAN.md — TDD: temp cookie copies for yt-dlp and mpv invocations

### Phase 24: Fix tag chip scroll overlapping buttons in edit dialog

**Goal:** Tag chips in the edit dialog wrap to multiple lines via FlowBox instead of overflowing horizontally, preventing overlap with adjacent form controls
**Requirements**: FIX-04
**Depends on:** Phase 23
**Success Criteria** (what must be TRUE):
  1. Tag chips wrap to multiple lines when they exceed the dialog column width
  2. Tag chips do not overlap Save/Delete buttons or other form controls
  3. Toggling a tag chip still updates selected tags correctly
  4. Adding a new tag via the entry still works
**Plans:** 1/1 plans complete

Plans:
- [x] 24-01-PLAN.md — Replace ScrolledWindow + horizontal Box with FlowBox for tag chips

### Phase 25: Fix filter chip overflow in station filter section

**Goal:** Provider and tag filter chips in the main window wrap via FlowBox instead of overflowing horizontally past adjacent buttons
**Requirements**: FIX-05
**Depends on:** Phase 24
**Plans:** 1/1 plans complete

Plans:
- [x] 25-01-PLAN.md — Replace ScrolledWindow chip containers with FlowBox in main window filter bar

### Phase 26: Fix broken Edit button next to Add Station

**Goal:** Remove broken standalone Edit button from filter bar; add pencil edit icon to now-playing controls_box that opens the editor for the currently playing station
**Requirements**: FIX-06
**Depends on:** Phase 25
**Plans:** 1/1 plans complete

Plans:
- [x] 26-01-PLAN.md — Remove filter bar Edit button, add now-playing edit button

### Phase 27: Add multiple streams per station for backup/round-robin and quality selection

**Goal:** Normalize station data model from single URL to multiple streams per station with quality tiers; provide Manage Streams UI in editor; update AudioAddict import for multi-quality and Radio-Browser for attach-to-existing
**Requirements**: STR-01, STR-02, STR-03, STR-04, STR-05, STR-06, STR-07, STR-08, STR-09, STR-10, STR-11, STR-12, STR-13, STR-14
**Depends on:** Phase 26
**Success Criteria** (what must be TRUE):
  1. station_streams table exists with all D-01 columns; existing station URLs migrated at position=1
  2. stations.url column removed; Station dataclass uses streams list
  3. Player resolves URL from station.streams[0]; preferred quality setting respected
  4. Station editor has "Manage Streams..." button opening sub-dialog for stream CRUD with reordering
  5. AudioAddict import creates hi/med/low streams per channel
  6. Radio-Browser discovery offers "new station" or "attach to existing station"
**Plans:** 3/3 plans complete

Plans:
- [x] 27-01-PLAN.md — TDD: schema, migration, StationStream model, stream CRUD, player URL resolution
- [x] 27-02-PLAN.md — ManageStreamsDialog UI + quality constants + edit_dialog update
- [x] 27-03-PLAN.md — AudioAddict multi-quality import + Radio-Browser attach-to-existing

### Phase 28: Stream failover logic with server round-robin and quality fallback

**Goal:** Player automatically tries next stream on error or timeout, using preferred quality first then position order; toast notifications for failover events; manual stream picker in now-playing controls
**Requirements**: D-01, D-02, D-03, D-04, D-05, D-06, D-07, D-08
**Depends on:** Phase 27
**Success Criteria** (what must be TRUE):
  1. GStreamer error or 10s timeout triggers failover to next stream
  2. Preferred quality stream is tried first; remaining in position order
  3. Each stream tried exactly once; all-exhausted stops playback with error toast
  4. Toast notifications on each failover attempt and on exhaustion
  5. Stream picker button in now-playing controls shows all streams for manual switching
  6. Manual stream selection plays immediately without affecting configured order
**Plans:** 2/2 plans complete

Plans:
- [x] 28-01-PLAN.md — TDD: failover logic in Player (stream queue, timeout, error handling)
- [x] 28-02-PLAN.md — ToastOverlay + stream picker MenuButton + failover callback wiring

### Phase 29: Move Discover, Import, and accent color into the hamburger menu

**Goal:** Move Discover, Import, and Accent Color buttons from header bar into the hamburger Gio.Menu with two sections (station actions + settings); header bar becomes search entry + hamburger only
**Requirements**: MENU-01, MENU-02, MENU-03, MENU-04, MENU-05
**Depends on:** Phase 28
**Plans:** 1/1 plans complete

Plans:
- [x] 29-01-PLAN.md — Restructure hamburger menu with sections and remove header bar buttons

### Phase 30: Add time counter showing how long current stream has been actively playing

**Goal:** Display an elapsed time counter in the now-playing panel (icon + label) that ticks every second, pauses/resumes with the stream, resets on station change, and hides when stopped
**Requirements**: TIMER-01, TIMER-02, TIMER-03, TIMER-04, TIMER-05, TIMER-06
**Depends on:** Phase 29
**Success Criteria** (what must be TRUE):
  1. Timer row visible between station name and controls when a stream is playing
  2. Timer ticks up in 1-second intervals while playing
  3. Timer pauses when stream paused, resumes with correct accumulated time
  4. Timer resets to 0:00 on station change; failover does not reset
  5. Timer hidden when nothing is playing
  6. Format: M:SS under 1 hour, H:MM:SS at 1 hour+
**Plans:** 1/1 plans complete

Plans:
- [x] 30-01-PLAN.md — Timer widget + GLib tick callback + play/pause/stop lifecycle wiring

### Phase 31: Integrate Twitch streaming via streamlink

**Goal:** Twitch URLs are auto-detected and played via streamlink URL resolution into GStreamer playbin3; offline channels show toast without triggering failover; GStreamer errors re-resolve once before falling through to normal failover
**Requirements**: TWITCH-01, TWITCH-02, TWITCH-03, TWITCH-04, TWITCH-05, TWITCH-06, TWITCH-07, TWITCH-08
**Depends on:** Phase 30
**Success Criteria** (what must be TRUE):
  1. Twitch URLs auto-detected by "twitch.tv" in URL string and routed to streamlink
  2. streamlink resolves to HLS URL played through GStreamer playbin3
  3. Offline channels show "[channel] is offline" toast without failover
  4. GStreamer error on Twitch stream re-resolves once before normal failover
  5. Elapsed timer pauses on offline (does not reset)
  6. Existing HTTP and YouTube playback unaffected
**Plans:** 2/2 plans complete

Plans:
- [x] 31-01-PLAN.md — TDD: Twitch URL detection, streamlink resolution, offline/error handling in player.py
- [x] 31-02-PLAN.md — Wire on_offline callback in main_window.py + toast + timer pause + human verify
