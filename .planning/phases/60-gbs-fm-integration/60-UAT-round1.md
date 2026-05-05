---
status: complete
phase: 60-gbs-fm-integration
source:
  - 60-01-fixtures-tests-SUMMARY.md
  - 60-02-api-client-SUMMARY.md
  - 60-03-import-SUMMARY.md
  - 60-04-accounts-SUMMARY.md
  - 60-05-active-playlist-SUMMARY.md
  - 60-06-vote-SUMMARY.md
  - 60-07-search-submit-SUMMARY.md
started: 2026-05-04T21:00:00Z
updated: 2026-05-04T21:13:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running MusicStreamer process. Launch the app fresh. Main window paints, station list loads, no traceback in stderr/log, hamburger menu opens. New gbs_api.py import does not block startup.
result: pass

### 2. Hamburger Menu — New GBS.FM Entries
expected: Open the hamburger menu. Two new entries appear: "Add GBS.FM" (in Group 1, near "Import Stations") and "Search GBS.FM…" (further down). Total of 11 actions in the menu (10 prior + 1; the second was already counted in 60-03's adjustment to 10 then 60-07 raised to 11). Existing menu entries unchanged in order/content.
result: pass

### 3. AccountsDialog — GBS.FM Group Renders
expected: Open Accounts dialog. A new "GBS.FM" QGroupBox appears between YouTube and Twitch. It contains a status label (showing "Disconnected" if no cookies are saved) and a single Connect button. Group ordering is YouTube → GBS.FM → Twitch → AudioAddict.
result: pass

### 4. GBS.FM Connect — Cookie Import (File + Paste)
expected: With no GBS.FM cookies saved yet, click Connect. The CookieImportDialog opens with target label "GBS.FM". Only the File and Paste tabs are visible (no OAuth tab). Provide a valid cookies.txt (Netscape format with .gbs.fm `csrftoken` + `sessionid`). Dialog closes; AccountsDialog GBS.FM status flips to "Connected"; file at `~/.local/share/musicstreamer/gbs-cookies.txt` exists with 0o600 perms.
result: pass

### 5. GBS.FM Disconnect — Cookies Removed
expected: With GBS.FM connected, click Disconnect on the GBS.FM group. The status flips to "Disconnected". The file at `~/.local/share/musicstreamer/gbs-cookies.txt` is gone. Click Disconnect again with no file present — no error, no crash, status remains "Disconnected".
result: pass

### 6. Add GBS.FM Station — Idempotent Import
expected: From the hamburger menu click "Add GBS.FM". A toast appears: "Importing GBS.FM…" then "GBS.FM added" on first import. The station appears in the station list with provider "GBS.FM" and at least one playable stream (FLAC at 1411 kbps if your account exposes it). Click "Add GBS.FM" again — toast says "GBS.FM streams updated" or "GBS.FM import: no changes" instead of duplicating the station.
result: issue
reported: "Even though all are imported, it is saying \"Streams updated\" every time only; no duplication"
severity: minor

### 7. Play Imported GBS.FM Station
expected: Double-click the GBS.FM station. Audio starts; ICY title shows current track; cover art / station logo loads if exposed by GBS.FM. No regression in non-GBS playback (any other station still plays normally afterwards).
result: pass

### 8. Active Playlist Widget — Polls and Updates
expected: While the GBS.FM station is playing AND you are logged in, an active-playlist QListWidget appears below the now-playing row showing the current track marked with ▶ plus the upcoming queue and a "Score: N" line. It refreshes roughly every 15 seconds (you can confirm by waiting for a track change). Widget is at most ~180px tall.
result: issue
reported: "I don't see the upcoming queue but I do see the \"playlist is X long with Y dongs\" and \"Score: 5.0 (4 votes)\""
severity: major

### 9. Active Playlist Widget — Hidden When Not Applicable
expected: Switch to a non-GBS station — the active-playlist widget disappears. Switch back to GBS.FM — it reappears. Disconnect the GBS.FM account while on the GBS station — the widget disappears within one poll cycle (no toast spam on auth_expired).
result: pass

### 10. Vote Control — Optimistic UI + Server Confirm
expected: While the GBS.FM station is playing AND you are logged in, 5 vote buttons (labeled 1–5) appear below the active playlist. Click "5" — the button highlights immediately (optimistic). Within ~1 second the highlight is confirmed by the server response (the button stays highlighted). Click "5" again — vote clears (no button highlighted). Click a different number — the highlight moves to the new button.
result: issue
reported: "Not seeing a server response. Also verified on the site that it wasn't seeing it. But I see the buttons and they do click"
severity: major

### 11. Vote Rollback on Error
expected: While voting, simulate an error (kill network briefly OR disconnect the GBS.FM account mid-click). The optimistic highlight reverts to the prior server-confirmed state, AND a toast appears with an error message (e.g. "GBS.FM session expired — reconnect via Accounts" for auth-expired).
result: issue
reported: "Tried both the down the bond [network down] as well as removing hte cookie file, bneither shows up the toast. Not sure if that is something I can well test"
severity: major
note: Likely correlated with Test 10 root cause — if the vote POST never reaches the network/server layer, neither error path fires, so rollback toast never surfaces.

### 12. Search Dialog — Login Gate + Search + Pagination
expected: From the hamburger menu click "Search GBS.FM…". Dialog opens, ~640×480 minimum. If logged out, search controls are disabled with a hint to connect via Accounts. Logged in: type a query (e.g. an artist name), press Enter / click Search. A table of results populates. If more than one page is returned, Prev / Next buttons advance pagination.
result: issue
reported: "It works but it's missing some info. [screenshot shows GBS.FM web search has Artist: + Album: hyperlinked panels above the song results table; ours only shows the song results table]. Results should also include the link to artists and album results, than then load a new list of songs."
severity: major

### 13. Submit a Track — Success / Duplicate / Quota / Auth-Expired
expected: In the Search dialog, click "Add!" on a row. On success, the row shows confirmation. On duplicate or token-quota errors, an inline error appears next to the row (no toast). On auth-expired (cookies expired or removed mid-session), a toast appears: "GBS.FM session expired — reconnect via Accounts".
result: issue
reported: "I get a 302 response but I see the result does hit the server end. [Screenshot 1: dialog shows red 'Submit Failed: HTTP Error 302: Found' below the results table. Screenshot 2: gbs.fm playlist queue shows 'The Art Of Noise — Moments In Love (10:19)' with submitter 'Lightning Jim' present in the queue]"
severity: major

## Summary

total: 13
passed: 7
issues: 6
pending: 0
skipped: 0

## Gaps

- truth: "On a redundant Add GBS.FM (no real DB change), toast should say 'GBS.FM import: no changes' rather than 'GBS.FM streams updated'."
  status: failed
  reason: "User reported: Even though all are imported, it is saying \"Streams updated\" every time only; no duplication"
  severity: minor
  test: 6
  artifacts: []
  missing: []

- truth: "Active-playlist widget should enumerate the upcoming queue (one row per upcoming track), not just a summary count line."
  status: failed
  reason: "User reported: I don't see the upcoming queue but I do see the \"playlist is X long with Y dongs\" and \"Score: 5.0 (4 votes)\" — the widget shows current track + summary line + score, but no per-row enumeration of upcoming songs."
  severity: major
  test: 8
  artifacts: []
  missing: ["per-row enumeration of upcoming queue tracks in _on_gbs_playlist_ready renderer"]

- truth: "Clicking a 1-5 vote button should round-trip a POST to gbs.fm and the vote should be visible on the GBS.FM site (server-confirmed)."
  status: failed
  reason: "User reported: Not seeing a server response. Also verified on the site that it wasn't seeing it. But I see the buttons and they do click — UI fires but request never lands at gbs.fm."
  severity: major
  test: 10
  artifacts: ["musicstreamer/gbs_api.py::vote_now_playing", "musicstreamer/ui_qt/now_playing_panel.py::_GbsVoteWorker", "musicstreamer/ui_qt/now_playing_panel.py::_on_gbs_vote_clicked"]
  missing: ["working end-to-end vote POST — likely root cause: wrong URL/method, missing CSRF, wrong entryid, cookie not attached, or silent server rejection"]

- truth: "When a vote fails (network down OR cookies removed mid-click), the optimistic highlight should revert AND an error toast should surface (e.g. 'GBS.FM session expired — reconnect via Accounts')."
  status: failed
  reason: "User reported: Tried both network down and removing the cookie file — neither shows the toast."
  severity: major
  test: 11
  artifacts: ["musicstreamer/ui_qt/now_playing_panel.py::_on_gbs_vote_error", "musicstreamer/ui_qt/now_playing_panel.py::gbs_vote_error_toast", "musicstreamer/ui_qt/main_window.py: now_playing.gbs_vote_error_toast.connect(show_toast)"]
  missing: ["error path actually firing for vote — likely correlated with Test 10 (if request never executes, error handler never runs); independently verify gbs_vote_error_toast.connect wiring + worker emits error signal on raised exception"]
  correlated_with_test: 10

- truth: "Search dialog should mirror gbs.fm's web search page: an Artist: hyperlink panel + an Album: hyperlink panel above the song-results table. Clicking an artist/album link should load a new list of songs filtered to that artist/album."
  status: failed
  reason: "User reported (with screenshot): It works but it's missing some info — gbs.fm site shows Artist: and Album: linked panels above the results table; our dialog renders only the song-results table. Results should also include the link to artists and album results, then load a new list of songs."
  severity: major
  test: 12
  artifacts: ["musicstreamer/gbs_api.py::search (HTML parser)", "musicstreamer/ui_qt/gbs_search_dialog.py (renderer)", "tests/fixtures/gbs/search_test_p1.html (re-inspect for Artist:/Album: link blocks not currently extracted)"]
  missing: ["gbs_api.search return shape needs to include artist_links + album_links lists (text + url) parsed from the HTML; gbs_search_dialog.py needs an Artist:/Album: panel above the results table; clicking a link kicks off a follow-up filtered search"]

- truth: "Submit a track via Search dialog 'Add!' should show success/duplicate/quota inline status; submission must be parsed from gbs.fm's 302 + Django-messages-cookie response (NOT raised as an HTTP error). On true auth-expired, surface reconnect toast."
  status: failed
  reason: "User reported (with two screenshots): submission DID land on the gbs.fm playlist queue (visible as 'The Art Of Noise — Moments In Love' submitted by 'Lightning Jim'), but the client showed 'Submit Failed: HTTP Error 302: Found' beneath the results table. The 302 + Django messages cookie is the canonical success-or-error signal from gbs.fm — gbs_api.submit (or _GbsSubmitWorker) is treating it as an error instead of decoding the messages cookie. Same fixture shape lives in tests/fixtures/gbs/add_redirect_response.txt + messages_cookie_track_added.txt."
  severity: major
  test: 13
  artifacts: ["musicstreamer/gbs_api.py::submit", "musicstreamer/ui_qt/gbs_search_dialog.py::_GbsSubmitWorker", "tests/fixtures/gbs/add_redirect_response.txt", "tests/fixtures/gbs/messages_cookie_track_added.txt"]
  missing: ["urllib redirect handler must NOT follow 302 (or must capture the messages cookie before urllib redirects); base64-url-decode the 'messages' cookie payload; map 'Track added' → success, dup/quota strings → inline error per D-08d; only auth-expired (302 to /accounts/login/) should fire the reconnect toast (per existing ajax_login_redirect.txt fixture)"]
  correlated_with_test: 6  # both Test 6's idempotent toast and Test 13's submit response involve interpreting 302/Django-messages responses
