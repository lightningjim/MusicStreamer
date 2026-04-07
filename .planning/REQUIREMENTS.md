# Requirements: MusicStreamer

**Defined:** 2026-04-05
**Core Value:** Finding and playing a stream should take seconds — the right station should always be one or two clicks away.

## v1.5 Requirements

Requirements for this polish milestone. New items added as issues are discovered (deadline: 2026-04-19).

### Bug Fixes

- [ ] **FIX-01**: YouTube 16:9 thumbnail does not inflate now-playing panel when window is maximized/fullscreen
- [ ] **FIX-02**: yt-dlp/mpv cookie invocations use a temporary copy of cookies.txt so the original imported file is never overwritten
- [ ] **FIX-03**: If mpv exits immediately (~2s) with cookies, retry once without cookies to handle corrupted cookie files

### Cookie Management (Phase 22)

- [ ] **COOKIE-01**: Users can import YouTube cookies via file picker or paste textarea
- [ ] **COOKIE-02**: Cookies stored at ~/.local/share/musicstreamer/cookies.txt with 0o600 permissions; manual lifecycle with last-imported date display; clear button to remove
- [ ] **COOKIE-03**: yt-dlp subprocess calls include --cookies flag when cookies.txt exists and always include --no-cookies-from-browser
- [ ] **COOKIE-04**: mpv subprocess calls include --ytdl-raw-options=cookies=<path> when cookies.txt exists
- [ ] **COOKIE-05**: Hamburger menu in header bar with "YouTube Cookies..." item opens the cookie dialog
- [ ] **COOKIE-06**: Google login flow via embedded WebKit2 browser captures YouTube cookies and saves as cookies.txt

## Future Requirements

### v2.0 — OS-Agnostic Revamp

- **V2-01**: Cross-platform support (not GNOME-only)

## Out of Scope

| Feature | Reason |
|---------|--------|
| New features | v1.5 is bug-fix/polish only; new features deferred to v2.0 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FIX-01 | Phase 21 | Pending |
| FIX-02 | Phase 23 | Pending |
| FIX-03 | Phase 23 | Pending |
| COOKIE-01 | Phase 22 | Pending |
| COOKIE-02 | Phase 22 | Pending |
| COOKIE-03 | Phase 22 | Pending |
| COOKIE-04 | Phase 22 | Pending |
| COOKIE-05 | Phase 22 | Pending |
| COOKIE-06 | Phase 22 | Pending |

**Coverage:**
- v1.5 requirements: 9 total
- Mapped to phases: 9
- Unmapped: 0

---
*Requirements defined: 2026-04-05*
*Last updated: 2026-04-07 after Phase 23 planning*
