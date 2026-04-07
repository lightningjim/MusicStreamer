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

**Goal:** [To be planned]
**Requirements**: TBD
**Depends on:** Phase 23
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd-plan-phase 24 to break down)

### Phase 25: Fix filter chip overflow in station filter section

**Goal:** [To be planned]
**Requirements**: TBD
**Depends on:** Phase 24
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd-plan-phase 25 to break down)

### Phase 26: Fix broken Edit button next to Add Station

**Goal:** [To be planned]
**Requirements**: TBD
**Depends on:** Phase 25
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd-plan-phase 26 to break down)
