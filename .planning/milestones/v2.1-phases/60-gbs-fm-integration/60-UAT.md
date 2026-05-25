---
status: complete
phase: 60-gbs-fm-integration
round: 2
source:
  - 60-08-fix-302-messages-SUMMARY.md
  - 60-09-fix-vote-roundtrip-SUMMARY.md
  - 60-10-active-playlist-enumeration-SUMMARY.md
  - 60-11-search-artist-album-panels-SUMMARY.md
notes: |
  Round 2: focused retest of the 6 issues that failed in round 1 (preserved as
  60-UAT-round1.md). The 7 tests that passed in round 1 are NOT re-run because the
  underlying code paths were not modified by the gap-closure plans.
started: 2026-05-04T23:50:00Z
updated: 2026-05-04T23:50:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test (post-gap-closure)
expected: Kill any running MusicStreamer instance. Launch the app from scratch. The window loads without errors, the GBS.FM hamburger menu entries are present, and previously imported GBS.FM stations (if any) appear in the station list. No tracebacks in the console.
result: pass

### 2. T6 — Idempotent Re-Import (no changes)
expected: With a GBS.FM station already imported, click Hamburger → Add GBS.FM Station a second time without changing anything on the server. Toast should say "GBS.FM streams unchanged" (or similar — no-change wording), NOT "GBS.FM streams updated". This is the round-1 T6 failure that 60-08 addresses via field-level dirty-checking.
result: pass
observed: "no changes" toast wording — matches expected no-change semantic.

### 3. T8 — Active Playlist Enumerated Rows
expected: Bind to a GBS.FM station and let it play. The active-playlist widget below the now-playing row should enumerate the upcoming queue as numbered rows in the format "1. Artist - Title [duration]", "2. Artist - Title [duration]", up to 10 rows. It should NOT show a single summary line like "Playlist is X long with Y dongs". Round-1 T8 failure that 60-10 addresses.
result: pass

### 4. T10 — Vote Buttons Disabled Until Entryid Stamped
expected: Bind to a GBS.FM station. The five 1-5 vote buttons appear but are DISABLED (grayed out, not clickable) for the first ~15 seconds while the first /ajax poll arrives. Once the first poll lands and stamps the now-playing entryid, the buttons become enabled. Round-1 T10 failure that 60-09 addresses (replaces the silent click-drop with a visible disabled state).
result: pass
observed: Buttons enable after first /ajax poll, vote submits, and vote total + avg change is visible on the GBS.FM website (end-to-end server round-trip confirmed).

### 5. T11 — Vote Rollback Toast on Cookies Disappeared
expected: Bind to a GBS.FM station and wait for vote buttons to enable. While playing, manually delete the cookies file (~/.local/share/musicstreamer/gbs-cookies.txt) and click a vote button. A toast should appear saying "GBS.FM session expired — reconnect via Accounts" (or similar). The vote should NOT silently fail with no UI feedback. Round-1 T11 failure that 60-09 addresses.
result: pass
observed: "exactly as described" — toast appears on cookie-deletion vote-click rollback path.

### 6. T12 — Artist:/Album: Panels in Search Dialog
expected: Open Search GBS.FM (Hamburger → Search GBS.FM…). Search a query that matches both songs and artists/albums (e.g. "test", "metallica", or any popular artist). The dialog should now show two new horizontal panels above the song results: "Artist:" with clickable links and "Album:" with clickable links. Clicking an Artist link runs a new free-text search for that artist name; same for Album. (D-11a Shape 4: clicks reset the search input rather than navigating to /artist/<id>.) Round-1 T12 failure that 60-11 addresses.
result: issue
reported: |
  For one-word names, yes, but for multi-word it seems to just present the song search results. Also, e.g. clicking on Metallica to go into their album list just does another base search instead of going into the artist page.
severity: major
issues:
  - A: Multi-word artist/album click routes don't surface artist/album results — only song search results.
  - B: Clicks fall back to free-text search instead of opening the actual /artist/<id> or /album/<id> page (locked D-11a=Shape 4 behavior, but user expected drill-down navigation).

### 7. T13 — Submit Track Toast on Success
expected: In the Search GBS.FM dialog, find a song you're authorized to submit (i.e. you're logged in via cookies and within quota). Click Submit. The toast should say "Track submitted" (or similar success wording), NOT "Submit Failed: HTTP Error 302: Found". Round-1 T13 failure that 60-08 addresses via the _NoRedirect.http_error_302 override.
result: pass
observed: "Confirmed, see it on the site, too" — submission succeeded both in-app toast AND verified on gbs.fm.

## Summary

total: 7
passed: 6
issues: 1
pending: 0
skipped: 0
notes: |
  6 round-1 issues retested — 5 of 6 fully closed (T6, T8, T10, T11, T13).
  T12 is partially closed (panels render, parser works, but click navigation has
  2 sub-issues: multi-word search routing + drill-down vs free-text expectation).

## Gaps

- truth: "Clicking an Artist/Album panel link with a multi-word name should produce search results that include matching artists/albums (not only songs)."
  status: failed
  reason: "User reported: For one-word names, yes, but for multi-word it seems to just present the song search results."
  severity: major
  test: 6
  artifacts: []
  missing: []

- truth: "Clicking an Artist/Album link should open that artist's/album's catalog page (drill-down), not re-run a base search."
  status: failed
  reason: "User reported: clicking on Metallica to go into their album list, it just does another base search instead of going into the artist page."
  severity: major
  test: 6
  notes: |
    Locked D-11a=Shape 4 (free-text fallback) was driven by a deterministic grep gate
    (`<table class="songs">` count = 0 on /artist/4803 and /album/1488) — the actual
    pages use `<table class="artist">` and unclassed `<table width="620">`. The Shape 4
    fallback is technically what the plan committed, but the user's mental model is
    drill-down navigation; the gate missed the alternate table shapes.
  artifacts:
    - tests/fixtures/gbs/artist_4803.html  # has <table class="artist">
    - tests/fixtures/gbs/album_1488.html   # has unclassed <table width="620">
  missing:
    - "_ArtistPageParser handling <table class='artist'>"
    - "_AlbumPageParser handling unclassed <table width='620'>"
    - "Click handler that opens /artist/<id> or /album/<id> in a sub-dialog or panel"
