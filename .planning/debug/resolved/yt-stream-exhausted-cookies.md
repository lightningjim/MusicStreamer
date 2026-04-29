---
status: resolved
trigger: "DATA_START\nI am getting \"Stream exhausted\" again on YT streams only. Twitch and HTTP audio is fine. CLI output says it can't find any streams. I disconnected Google and the stream played fine so something again with handling the cookies off to the yt-dlp for stream list is the problem\nDATA_END"
created: 2026-04-29T00:00:00Z
updated: 2026-04-29T00:00:00Z
---

## Current Focus

hypothesis: Phase 53 (commits a7c7e11, 1b03ada, 004de5c — "youtube-cookies-into-accounts-menu" + 53-02 trim-main-window) altered the cookies handoff path between the Accounts menu and yt-dlp such that the per-call temp-cookies-copy contract from Phase 999.7 (cookie_utils.temp_cookies_copy) is broken or bypassed when Google is connected. yt-dlp receives no usable cookies → format extraction returns zero streams → empty/invalid URL flows to GStreamer playbin → "Stream exhausted" / EOS. Google-disconnected path skips cookies entirely and works.
test: read the diff for Phase 53 commits (especially 53-02 trim-main-window which removed the YouTube Cookies menu entry/slot/import and wired toast_callback) plus current state of player.py::_youtube_resolve_worker, cookie_utils.temp_cookies_copy, and the new Accounts-menu cookie wiring; verify cookies.txt path resolution + temp-copy still occurs on the resolve worker side
expecting: cookies path is no longer being passed to yt-dlp on the player resolve path (likely the toast_callback rewire removed or bypassed the cookies arg), OR the cookies file is being passed but is empty/invalid (Accounts menu writes/imports differently than the old Cookie Import dialog)
next_action: RESOLVED — see Resolution section

## Symptoms

expected: YouTube stations play audio when Google is connected and cookies are imported (same as before Phase 53)
actual: yt-dlp returns no streams; GStreamer reports "Stream exhausted" / EOS immediately on every YT station
errors: "Stream exhausted" (GStreamer); CLI says it can't find any streams (yt-dlp format extraction returns empty)
reproduction: With Google connected (cookies present), play any YouTube station → fails immediately, every time, 100% repro on first play
workaround: Disconnect Google account → YouTube playback works (cookies path skipped entirely)
unaffected: Twitch streams play fine; HTTP audio (HLS/Icecast/Shoutcast) plays fine
started: After Phase 53 — "youtube-cookies-into-accounts-menu" (commits a7c7e11, 1b03ada, 004de5c, 090f9de, e10153e on main, landed 2026-04-29)

## Eliminated

- hypothesis: GStreamer / pipeline regression
  evidence: Twitch + HTTP audio paths play fine; only YouTube fails. Pipeline+playbin code unchanged.
  timestamp: 2026-04-29

- hypothesis: yt-dlp version regression
  evidence: yt-dlp version unchanged in the Phase 53 commit window; same yt-dlp works when Google is disconnected (cookies path bypassed)
  timestamp: 2026-04-29

- hypothesis: Cookies file missing entirely
  evidence: User has Google connected — cookies were imported via the new Accounts menu flow. If file were missing, the no-cookies path would be taken (which works). The bug only manifests WITH cookies present.
  timestamp: 2026-04-29

- hypothesis: Phase 53 broke the temp_cookies_copy invariant in player.py
  evidence: player.py::_youtube_resolve_worker is fully intact — temp_cookies_copy wraps YoutubeDL correctly. Phase 53 only touched main_window.py (removed YouTube Cookies menu entry, wired toast_callback to AccountsDialog). The cookie write path (CookieImportDialog._write_cookies) is unchanged.
  timestamp: 2026-04-29

- hypothesis: Cookies file is corrupted (yt-dlp marker header)
  evidence: cookies.txt inspected directly — starts with "# Netscape HTTP Cookie File / # https://curl.haxx.se/rfc/cookie_spec.html / # This is a generated file! Do not edit." (browser-exported format, not yt-dlp generated). Not corrupted.
  timestamp: 2026-04-29

- hypothesis: Cookies are expired or insufficient for YouTube
  evidence: Cookies contain HSID, SSID, APISID, SAPISID, __Secure-1PSID, __Secure-3PSID, SID, LOGIN_INFO — all proper YouTube session cookies, all expiring 2026-10-23 or later.
  timestamp: 2026-04-29

## Evidence

- timestamp: 2026-04-29
  checked: git log on main since Phase 53
  found: a7c7e11 test(53) UAT complete; 1b03ada docs(53-02) plan complete BUG-04 closed; 004de5c feat(53-02) trim main_window.py — removed YouTube Cookies menu entry, slot, import; wired toast_callback
  implication: 53-02 is the most likely regression site — it touched the cookie wiring in main_window.py

- timestamp: 2026-04-29
  checked: project memory project_decisions for Phase 999.7 cookie invariant
  found: "Phase 999.7: FIX-02 (yt-dlp temp-copy protection) restored on the library-API path via shared cookie_utils.py (mkstemp+copy2+unlink). Both read sites (player + yt_import) route cookies through a per-call temp file; yt-dlp's save_cookies() on __exit__ can no longer clobber canonical cookies.txt. Corruption auto-clear + toast wired on both sites."
  implication: The invariant the new debugger needs to check: does player.py::_youtube_resolve_worker still wrap yt_dlp.YoutubeDL inside cookie_utils.temp_cookies_copy, AND does the cookies path resolution still produce a valid file? Phase 53 may have severed one of those.

- timestamp: 2026-04-29
  checked: player.py::_youtube_resolve_worker source + Phase 53 diffs
  found: temp_cookies_copy invariant fully intact. Phase 53 did NOT touch player.py. CookieImportDialog write path unchanged. The bug is NOT in Phase 53 code.
  implication: Root cause must be environmental — how yt-dlp behaves differently with vs without cookies

- timestamp: 2026-04-29
  checked: yt-dlp verbose output WITH cookies present
  found: "[debug] [youtube] Found YouTube account cookies" → "[youtube] [jsc] Remote component challenge solver script (node) was skipped. It may be required..." → "n challenge solving failed: Some formats may be missing." → "No video formats found!"
  implication: ROOT CAUSE — yt-dlp 2026.03.17 authenticated code path (triggered when cookie account detected) requires the EJS remote component (ejs:github). The opts in _youtube_resolve_worker only set js_runtimes (local Node.js) but NOT remote_components. Unauthenticated path (no cookies) uses a different client config that still resolves with local Node.js only.

- timestamp: 2026-04-29
  checked: yt-dlp call WITH cookies + remote_components={"ejs:github"}
  found: Resolves successfully — 6 formats returned, HLS manifest URL obtained
  implication: Adding remote_components to opts fixes the regression

## Resolution

root_cause: yt-dlp 2026.03.17+ requires remote_components={"ejs:github"} in the opts dict when YouTube account cookies are present. When cookies are detected, yt-dlp enters an authenticated code path that requires the EJS remote solver script to solve the n-challenge. The js_runtimes={"node": {"path": None}} option alone is insufficient for the authenticated path. Without remote_components, the n-challenge solving is skipped, all formats are filtered out, and extract_info raises "No video formats found!" The unauthenticated path (no cookies) was unaffected because it uses a different client config that does not require the remote solver. Phase 53 did NOT introduce this bug — it is a yt-dlp behavior change that coincidentally became visible after Phase 53 landed because Phase 53 was the context in which the symptom appeared.
fix: Added "remote_components": {"ejs:github"} to the opts dict in player.py::_youtube_resolve_worker (line ~553) and musicstreamer/yt_import.py::scan_playlist. Both yt-dlp call sites now enable the EJS remote component. Verified: yt-dlp with cookies + remote_components resolves 6 formats; all 57 existing tests pass.
verification: python3 direct test — yt-dlp with cookies.txt + remote_components resolves jfKfPfyJRdk to HLS manifest URL with 6 formats. pytest tests/test_player.py tests/test_cookies.py tests/test_yt_import_library.py tests/test_cookie_import_dialog.py — 57 passed, 0 failures.
files_changed:
  - musicstreamer/player.py
  - musicstreamer/yt_import.py
