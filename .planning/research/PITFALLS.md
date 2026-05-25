# Pitfalls Research — MusicStreamer v2.2

**Domain:** Adding Linux packaging (AppImage + Flatpak), Windows SMTC AUMID, GBS.FM scraping, channel-avatar fallback, and SomaFM preroll debug to an existing Python/PySide6/GStreamer audio app.
**Researched:** 2026-05-25
**Confidence:** HIGH (most pitfalls verified against existing MusicStreamer codebase artifacts — Phase 35/43/43.1/56/69/76 lessons — plus current upstream issue trackers for linuxdeploy-plugin-gstreamer, Flathub QtWebEngine BaseApp, yt-dlp issue #10090, and Inno Setup `[Icons]` AppUserModelID semantics).

## Scope

These pitfalls are specific to ADDING the v2.2 capabilities. Generic Python/Qt/GStreamer warnings are EXCLUDED — see `.planning/codebase/CONCERNS.md` for those. Where a pitfall mirrors a behavior of an external project, the rule is cited per `feedback_mirror_decisions_cite_source.md` (never paraphrased). Where a pitfall is testable only via source-level grep (not behavioral mocks), it is flagged with the `feedback_gstreamer_mock_blind_spot.md` lens. Where a pitfall would have been caught by widget-extreme-sweep diagnostics, it is flagged with the `feedback_ui_bug_verify_with_extremes.md` lens.

---

## Critical Pitfalls

### Pitfall 1: AppImage built on too-new a host distro silently bumps the GLIBC baseline

**What goes wrong:**
The AppImage produced on a current dev box (Ubuntu 24.04 / Fedora 41 / Arch) refuses to launch on older but still-supported distros (Ubuntu 22.04, Debian 12). Error is a non-actionable `version 'GLIBC_2.38' not found (required by ./AppRun)` at exec time.

**Why it happens:**
glibc symbol versioning is forward-compatible only. Anything dynamically linked against a newer host's `libc.so.6` carries the host's GLIBC symbol requirement. libstdc++ has the same problem and is even worse because conda-forge's `libstdc++.so.6` is often newer than the system one — when the AppImage runtime picks the system loader, it can mix-and-match in ways that explode at runtime ([AppImage best practices](https://docs.appimage.org/reference/best-practices.html), [pkg2appimage #173](https://github.com/AppImage/pkg2appimage/issues/173)).

**How to avoid:**
- Build the AppImage in a pinned-old Docker container — Ubuntu 22.04 LTS (jammy) is the minimum reasonable baseline today; 20.04 if you want to support Mint/older RHEL derivatives.
- Bundle `libstdc++.so.6` from the build host into `usr/lib/` and have the AppRun script check at startup: `objdump -T /lib/x86_64-linux-gnu/libstdc++.so.6 | grep -q GLIBCXX_3.4.30 || export LD_LIBRARY_PATH=...$APPDIR/usr/lib`.
- Do NOT use conda-forge directly as the AppImage build env — its glibc/libstdc++ ABI is too modern and is not portable. Use a conda env *only* to produce `dist/` (PyInstaller-style staging), then assemble the AppImage in the old-host container.
- Verify with `strings AppRun_or_main_so | grep GLIBC_ | sort -V | tail -1` — must be ≤ target baseline.

**Warning signs:**
- `dpkg --compare-versions` shows the build host's glibc is newer than 2.35
- `ldd dist/MusicStreamer | grep 'not found'` returns anything on a target VM
- User reports "AppImage just exits with no output" — almost always a dynamic loader symbol-version mismatch dumped to stderr that the user didn't capture

**Phase to address:**
v2.2 Linux AppImage packaging phase (suggested: Phase 85). Set up the build container BEFORE writing the recipe — recipe is built around the container constraints, not the other way around. Spike-first candidate.

---

### Pitfall 2: linuxdeploy-plugin-gstreamer copies plugins but `gst-plugin-scanner` paths leak the build host

**What goes wrong:**
The AppImage runs on the build host but on other distros `gst-plugin-scanner` exits non-zero and `gst-launch-1.0 -v playbin uri=...` reports "no element 'souphttpsrc'". The plugins ARE inside the AppImage but the scanner cache is built with build-host absolute paths that don't exist on the target system.

**Why it happens:**
`linuxdeploy-plugin-gstreamer.sh` invokes the host's `gst-plugin-scanner`, which writes a binary registry cache (`~/.cache/gstreamer-1.0/registry.x86_64.bin`) containing absolute paths from the BUILD host. On a target distro with different library locations (especially openSUSE/Fedora, where `/usr/lib64` differs from `/usr/lib/x86_64-linux-gnu`), every plugin's runtime dependency resolution fails ([linuxdeploy-plugin-gstreamer #17](https://github.com/linuxdeploy/linuxdeploy-plugin-gstreamer/issues/17), [#9](https://github.com/linuxdeploy/linuxdeploy-plugin-gstreamer/issues/9)).

**How to avoid:**
- AppRun must FORCE a re-scan on first launch by `unset GST_REGISTRY` and setting `GST_REGISTRY_FORK=no`, then point `GST_PLUGIN_SCANNER=$APPDIR/usr/libexec/gstreamer-1.0/gst-plugin-scanner`.
- Bundle `gst-plugin-scanner` itself into `$APPDIR/usr/libexec/gstreamer-1.0/` — do not rely on the host's scanner.
- Set `GST_PLUGIN_SYSTEM_PATH_1_0=$APPDIR/usr/lib/gstreamer-1.0` AND `GST_PLUGIN_PATH_1_0=$APPDIR/usr/lib/gstreamer-1.0` (both, not just one — the underscored `_1_0` form is what 1.28+ honors).
- Mirror the Phase 69 Windows lesson (`tools/check_bundle_plugins.py`) on Linux: post-build, the AppRun must dlopen `gstlibav.so` + `gstaudioparsers.so` and verify `avdec_aac` + `aacparse` are present. Exit code 10 if not (parity with `packaging/windows/build.ps1` step 4b).
- Test on at least Ubuntu 22.04 + Fedora 40 + openSUSE Tumbleweed before publishing.

**Warning signs:**
- `gst-inspect-1.0 -b` from inside `$APPDIR/AppRun-shell` shows zero plugins
- `GST_DEBUG=2 ./MusicStreamer.AppImage` on a fresh target shows "no plugins" warnings before pipeline construction
- Different bitrate or codec works on build host but fails on target — almost always missing `gst-libav` plugin chain at runtime

**Phase to address:**
Same Linux AppImage phase (Phase 85). The plugin-presence drift-guard test should be added to `tests/test_packaging_spec.py` in the same phase, parallel to the existing Windows guard. Source-level grep gate per `feedback_gstreamer_mock_blind_spot.md`: `assert "GST_PLUGIN_SYSTEM_PATH_1_0" in apprun_text` and `assert "GST_PLUGIN_SCANNER" in apprun_text`.

---

### Pitfall 3: charset_normalizer mypyc shared module is silently dropped by PyInstaller AND linuxdeploy

**What goes wrong:**
On Linux AppImage builds (just as on Phase 35/36 GTK retirement), `requests` works in dev but throws `CharsetNormalizerError: No module named 'charset_normalizer.md__mypyc'` at runtime when fetching from iTunes / MusicBrainz / Twitch Helix / GBS.FM.

**Why it happens:**
`charset_normalizer >= 3` ships a precompiled mypyc shared object (`md__mypyc.cpython-312-x86_64-linux-gnu.so`) that is not auto-detected by either PyInstaller's collector or linuxdeploy's library walker. This is the same pitfall MusicStreamer hit when retiring GTK4 — the Windows installer uses `chardet>=5,<6` instead (see `PROJECT.md` line 51).

**How to avoid:**
Same fix as Windows: pin `chardet>=5,<6` in `pyproject.toml` and verify with `import charset_normalizer; charset_normalizer.from_bytes(b'x')` runs without the `md__mypyc` error in the staged build directory. Do NOT install `charset_normalizer` at all — `requests` falls back to `chardet` automatically.

**Warning signs:**
- `python -c "import requests; requests.get('https://itunes.apple.com/search?term=x')"` from inside the staged `usr/bin/` directory throws ImportError on `md__mypyc`
- iTunes/Twitch/MB calls work in dev but fail with the bundled AppImage on a fresh VM

**Phase to address:**
Linux AppImage phase (Phase 85). Add a `tests/test_packaging_spec.py::test_pyproject_pins_chardet_over_charset_normalizer` source-level guard.

---

### Pitfall 4: Flatpak QtWebEngine sandbox-in-sandbox blocks GBS.FM login subprocess

**What goes wrong:**
The Phase 76 GBS in-app login subprocess (QtWebEngine) crashes inside the Flatpak with `Failed to move to new namespace: PID namespaces supported, Network namespace supported, but failed: errno = Operation not permitted` (Chromium SUID sandbox cannot nest inside Flatpak's bubblewrap sandbox).

**Why it happens:**
Chromium's renderer-sandbox uses `unshare()` to enter new namespaces. Flatpak's bubblewrap already entered them, and the kernel does not allow nesting these specific capabilities. This is documented Chromium behavior, not a Flatpak bug ([Flathub QtWebEngine BaseApp](https://github.com/flathub/io.qt.qtwebengine.BaseApp), [Qt WebEngine Platform Notes](https://doc.qt.io/qt-6/qtwebengine-platform-notes.html)).

**How to avoid:**
- Use the `io.qt.qtwebengine.BaseApp` extension and set `QTWEBENGINE_DISABLE_SANDBOX=1` in the Flatpak manifest's `finish-args`. This disables Chromium's internal sandbox; Flatpak's bubblewrap still contains the renderer. Cite the BaseApp manifest for the exact env-var spelling per `feedback_mirror_decisions_cite_source.md` — do not paraphrase as `--no-sandbox` (which is a CLI flag, not an env var, and not the form QtWebEngine respects).
- Do NOT use `--device=all` to "fix" the crash — the actual issue is sandbox-nesting, not device access.
- Document the security trade-off in the manifest: Flatpak sandbox provides the outer containment; Chromium's inner sandbox is intentionally disabled because the kernel does not permit nesting.

**Warning signs:**
- `flatpak run --command=sh com.musicstreamer.MusicStreamer` followed by `QT_DEBUG_PLUGINS=1 python -c "from PySide6.QtWebEngineWidgets import QWebEngineView; ..."` reports the namespace error
- GBS.FM login button does nothing in Flatpak builds but works in AppImage builds — sandbox-nesting is the most likely cause

**Phase to address:**
Linux Flatpak phase (suggested: Phase 86, after Phase 85 AppImage). Spike-first candidate — verify the BaseApp + `QTWEBENGINE_DISABLE_SANDBOX=1` combination on a real Flathub-stage build before locking the manifest. Do not lock manifest decisions without quoting the BaseApp source.

---

### Pitfall 5: QtWebEngine cookie store is not shared between the login subprocess and main process by default

**What goes wrong:**
User logs into GBS.FM via the Phase 76 subprocess. The subprocess exits cleanly. Main process tries to fetch the authenticated marquee from `https://gbs.fm/api/marquee` — gets 401. Cookies appear to have been "lost" between the two QtWebEngine instances.

**Why it happens:**
`QWebEngineProfile`'s default constructor creates an OFF-THE-RECORD profile — cookies are in-memory only and die with the subprocess. To persist cookies on disk and have them survive across processes, you must (a) construct the profile with a non-empty storage name (`QWebEngineProfile("musicstreamer-gbs", parent)`), (b) explicitly call `setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)`, and (c) call `setPersistentStoragePath()` to a path under `~/.local/share/musicstreamer/` ([QWebEngineProfile docs](https://doc.qt.io/qt-6/qwebengineprofile.html)).

**How to avoid:**
- Both the login subprocess AND the main-process marquee fetcher MUST construct `QWebEngineProfile` with the SAME storage name and the same `setPersistentStoragePath()` value.
- The marquee fetcher should not use `QNetworkAccessManager` — it cannot read Chromium's cookie store. It must either (a) reuse a hidden `QWebEnginePage` instance with the persisted profile, or (b) export cookies to `requests`-readable form via `QWebEngineCookieStore.cookieAdded` signal at login time.
- Test: kill the subprocess, restart the app, verify the marquee fetch still works without re-login.
- Source-grep gate: `assert "PersistentCookiesPolicy" in source` AND `assert "setPersistentStoragePath" in source` — per `feedback_gstreamer_mock_blind_spot.md`, this is the kind of API contract that mocks will silently pass-through.

**Warning signs:**
- The cookies file at `~/.local/share/musicstreamer/QtWebEngine/Default/Cookies` (SQLite) doesn't exist after first login
- Marquee fetch works ONLY immediately after login and fails after app restart — classic in-memory cookie symptom
- Two `QWebEngineProfile` instances with different storage names = two cookie jars; do not let the planner paraphrase "they should share automatically" — they don't.

**Phase to address:**
GBS.FM themed-day / marquee phase (suggested: Phase 87). Must not establish a parallel QtWebEngine session — the Phase 76 profile must be reused. Spike-first to verify cookie persistence across process boundaries before locking the marquee architecture.

---

### Pitfall 6: SMTC AUMID mismatch silently breaks the Win+K media overlay

**What goes wrong:**
After installing the v2.2 Windows build, the SMTC overlay shows "Unknown app" even though `SetCurrentProcessExplicitAppUserModelID` is called at startup.

**Why it happens:**
Three independent failure modes:
1. The .lnk file's `System.AppUserModel.ID` shell property is missing or differs from the value passed to `SetCurrentProcessExplicitAppUserModelID`. Windows binds SMTC to the AUMID that the running process declared; the shortcut's AUMID must match exactly, character-for-character, casing included.
2. The `[Icons]` directive in older Inno Setup versions does not set the AUMID property unless `AppUserModelID:` is explicitly supplied ([Inno Setup [Icons] section](https://jrsoftware.org/ishelp/topic_iconssection.htm)).
3. Re-installing creates a new .lnk but does NOT remove a previously-pinned-to-taskbar .lnk that the user already pinned. The pinned shortcut retains the OLD AUMID. The user perceives this as "the new version broke media keys".

**How to avoid:**
- AUMID literal must be defined ONCE in a constants file and consumed by BOTH `musicstreamer/__main__.py` (the `SetCurrentProcessExplicitAppUserModelID` call) AND `packaging/windows/MusicStreamer.iss` (the `[Icons]` `AppUserModelID:` clause). The existing `tests/test_aumid_string_parity.py` enforces this on every Linux-CI run — do not delete it (per `packaging/windows/README.md`). Extend it to also assert the Inno `[Icons]` line literally contains `AppUserModelID: "org.lightningjim.MusicStreamer"`.
- Inno Setup uninstaller must remove the old .lnk explicitly via `[InstallDelete]` Type: `files` Name: `{userprograms}\MusicStreamer\MusicStreamer.lnk` BEFORE the new shortcut is created. Otherwise the SHELL caches the old AUMID against the file path.
- Document the "unpin from taskbar before upgrading" footnote in the WIN-02 release notes — there is no fully-automated fix for pre-existing pinned shortcuts. Microsoft's API for this is intentionally restricted to MSIX packages.
- Verify on a Win11 VM that has had v2.1 installed BEFORE installing v2.2 — fresh-VM test is insufficient.

**Warning signs:**
- `PowerShell: [Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime] | Out-Null; (Get-StartApps | Where Name -eq 'MusicStreamer').AppID` returns a different string than `__main__.py`'s `_WIN_AUMID`.
- SMTC works for the first user-session after install but breaks after `explorer.exe` is killed and restarted (Shell cache invalidation).

**Phase to address:**
WIN-02 SMTC AUMID phase (suggested: Phase 88, bundled with VER-02-J Win11 UAT + WIN-05 AAC retest per `PROJECT.md` line 17). Mirror-source rule: when CONTEXT.md says "follows Microsoft's AUMID guidance", cite [Microsoft Learn — Application User Model IDs](https://learn.microsoft.com/en-us/windows/win32/shell/appids) with the specific paragraph about per-process binding via `SetCurrentProcessExplicitAppUserModelID`. Do not paraphrase.

---

### Pitfall 7: yt-dlp `thumbnail` is the video preview, not the channel avatar

**What goes wrong:**
The new channel-avatar fetch worker calls `yt_dlp.YoutubeDL().extract_info(channel_url)` and saves `info['thumbnail']`. The image is a video frame (or "latest live stream" preview), not the channel avatar. When ICY is disabled and the cover slot falls back to the channel avatar, users see a video still instead of the channel icon.

**Why it happens:**
yt-dlp's YouTube extractor returns thumbnails from MULTIPLE sources — video frames, channel banners, uploader avatars. The top-level `thumbnail` field is the video thumbnail when extracting a video; for a channel/playlist URL it's the latest entry's thumbnail. The actual channel avatar is in `info['channel_thumbnails']` or `info['uploader_thumbnails']`, with separate `id` discriminators (`avatar_uncropped`, `banner_uncropped`) ([yt-dlp #10090](https://github.com/yt-dlp/yt-dlp/issues/10090), [#14041](https://github.com/yt-dlp/yt-dlp/issues/14041)).

**How to avoid:**
- Call `extract_info(channel_url, download=False, process=False)` with `extract_flat=True` to get the channel metadata only.
- Filter `info.get('thumbnails', [])` to entries with `id == 'avatar_uncropped'` (preferred — highest resolution unsquared avatar). Fall back to `id == 'avatar'`. Reject anything with `width != height` (banner aspect ratio, not avatar).
- Channel URL normalization: `@handle`, `/c/name`, `/channel/UC...`, and bare video URLs all need to resolve to a channel page. yt-dlp's `youtube:tab` extractor handles `@handle` and `/c/` automatically; bare video URLs need a two-step resolve (video → `info['channel_id']` → `https://youtube.com/channel/{channel_id}`).
- Source-grep gate: `assert "'avatar_uncropped'" in source or "'avatar'" in source` per `feedback_gstreamer_mock_blind_spot.md`. Do not let the planner paraphrase "we use yt-dlp's thumbnail field" — that field is the wrong one.

**Warning signs:**
- Lofi Girl shows a girl-with-headphones video still as the "channel avatar" instead of the chill-beats icon
- Different live streams from the same channel give different "avatars" — proves the field is the video thumbnail
- The image is 1280×720 (16:9, video aspect) instead of square — banner or video frame, not avatar

**Phase to address:**
YouTube channel-avatar fetch phase (suggested: Phase 89, part of ICY-disabled cover fallback). Spike-first: run `yt-dlp -J <channel_url>` for 3 channel-URL shapes (`@`, `/c/`, `/channel/`) plus 2 video URLs and document the actual JSON keys returned per [yt-dlp issue #10090](https://github.com/yt-dlp/yt-dlp/issues/10090). Mirror-source: when CONTEXT.md says "we mirror yt-dlp's thumbnail conventions", cite the actual `_extract_thumbnails` source in `youtube.py` with a permalink.

---

### Pitfall 8: Channel-avatar overrides legitimate cover art when ICY title is non-empty but iTunes returns no result

**What goes wrong:**
A station with ICY enabled plays a track that returns no iTunes match (e.g. Vaporwave / niche electronic — see `project_vaporwave_mb_caa_coverage.md`). Phase 73 MB-CAA fallback should kick in. Instead, because the developer added channel-avatar fallback at the wrong precedence level, the cover slot shows the channel avatar — masking the iTunes-empty/MB-CAA-should-have-found-it state.

**Why it happens:**
The natural design temptation is "if cover_art_result is None, show channel_avatar". But Phase 73's MB-CAA fallback is ALSO triggered when cover_art_result is None and ICY is non-empty. If channel-avatar is checked first, MB-CAA never runs.

**How to avoid:**
- Precedence order MUST be (and source-grep test MUST verify): `ICY → iTunes → MB-CAA → channel-avatar → placeholder`. Channel-avatar is the SECOND-TO-LAST fallback, not the first. Per `feedback_gstreamer_mock_blind_spot.md`, add a source-level grep gate that asserts the cover-resolution function calls `_mb_caa_lookup` BEFORE `_channel_avatar_lookup` in source order.
- Channel-avatar fallback fires ONLY when ICY is empty/disabled OR when iTunes returned a result AND MB-CAA returned a result AND BOTH were rejected by junk-detection. The "ICY is non-empty + iTunes-empty + MB-CAA-empty" state should remain the placeholder, not channel-avatar — channel-avatar makes the cover slot look "right" but masks the genuine coverage gap that motivated Phase 73.
- Stick to: channel-avatar replaces the PLACEHOLDER for stations where ICY is permanently disabled (YouTube live streams that never emit titles, etc.). That's the only valid use case.

**Warning signs:**
- Vaporwave / niche-electronic stations show the YouTube channel avatar instead of the placeholder — proves channel-avatar runs ahead of MB-CAA
- Phase 73 MB-CAA hit-rate telemetry drops after v2.2 ships — proves MB-CAA is being short-circuited

**Phase to address:**
ICY-disabled cover fallback phase (Phase 89, same as Pitfall 7). Drift-guard test: `tests/test_cover_resolution_precedence.py::test_mb_caa_runs_before_channel_avatar` doing source introspection on the resolver function.

---

### Pitfall 9: GBS.FM themed-logo detection drifts via CDN cache invalidation, not real theme change

**What goes wrong:**
The themed-day detector watches `Last-Modified` on `https://gbs.fm/logo_3.png`. CDN edge cache rotates → `Last-Modified` bumps → MusicStreamer applies a Halloween logo on a random Tuesday in March.

**Why it happens:**
HTTP `Last-Modified` is a property of the CACHE, not the resource. CDN purges, edge migrations, and infrastructure events all bump the timestamp without the underlying file changing. The correct signal is content-hash, not header-timestamp.

**How to avoid:**
- Download the file and compute SHA-256 of the bytes. Compare against a known-canonical hash of the year-round logo. Themed-day fires ONLY when the hash differs from the canonical AND a marquee keyword sniff (Phase 87 spec) corroborates the day.
- "Marquee keyword sniff" must be conservative — require an exact-substring match against a small whitelist (`"Memorial Day"`, `"4th of July"`, etc.), not a fuzzy match. Do NOT let the planner paraphrase "GBS announces themed days in the marquee" without citing the actual marquee text for at least 3 historical themed days per `feedback_mirror_decisions_cite_source.md`.
- Persist the themed-day decision in-memory for the session only (per `PROJECT.md` line 23 — "session-scoped at GBS launch"). Do not write themed state to SQLite — a player restart mid-weekend re-evaluates and may correctly de-theme if the canonical logo has returned by then.

**Warning signs:**
- Themed logo fires on non-holidays (or in months without GBS themed days)
- The logo hash changes but the marquee has no themed keyword — exit the themed state instead of trusting the hash alone
- User reports "themed logo stuck on for a week" — almost always the SQLite-persistence mistake

**Phase to address:**
GBS.FM themed-day phase (Phase 87). Spike-first: harvest 3 known themed-day responses + 5 non-themed-day responses from the real GBS site and lock the canonical-logo SHA-256 in a constant before writing the detector.

---

### Pitfall 10: GBS marquee pipe-segment parsing breaks on literal `|` in announcement text

**What goes wrong:**
GBS announces "Tonight | DJ Pulse | 8 pm" expecting users to read "Tonight | DJ Pulse | 8 pm". The marquee parser takes `text.split('|')[0]` → "Tonight" appears as the banner. Loss of context.

**Why it happens:**
The "first pipe-segment is the banner" rule (per `PROJECT.md` line 18) assumes the pipe is a structural delimiter. It isn't always — sometimes it's content.

**How to avoid:**
- Inspect at least 10 real marquee samples before writing the parser. Document the exact delimiter pattern (e.g., `" | "` with surrounding spaces is delimiter, `|` without spaces is content).
- If the delimiter is ambiguous, define the banner as "the first segment until either a delimiter OR newline OR end-of-string, whichever comes first, with a max length of N characters". Test against the 10 samples.
- Per `feedback_mirror_decisions_cite_source.md`: when CONTEXT.md says "the banner is the first pipe-segment", quote 3 actual marquee strings + the expected banner output, not just the rule. Spike-first.

**Warning signs:**
- Banner is one word ("Tonight", "Now") instead of a sentence
- Banner is empty when the marquee starts with `|` (defensive: strip leading delimiter before split)

**Phase to address:**
GBS.FM themed-day / marquee phase (Phase 87).

---

### Pitfall 11: SomaFM preroll diagnostic harvest corrupts the user's live session

**What goes wrong:**
The diagnostic added to investigate missing prerolls on Boot Liquor opens a SECOND GStreamer pipeline to the same URL "just to probe". User hears the audio double-up, or worse, the diagnostic interferes with the main session's ICY tag stream.

**Why it happens:**
The natural temptation is to use the real `playbin3` to probe. But playbin3 is stateful and noisy; two of them sharing the same URL can compete for the same upstream connection on SomaFM's side (some servers cap concurrent connections per IP).

**How to avoid:**
- Use a NON-DESTRUCTIVE probe: a single `requests.get(url, stream=True, headers={'Icy-MetaData': '1'})` that reads ICY metadata for 30 seconds and exits. No GStreamer involvement.
- Log the harvest to a separate file (`buffer-events.log` precedent from Phase 78 — use `preroll-probe.log`). Do not commingle with user-facing toast/logging.
- The probe is OPT-IN via hamburger menu, not automatic. The user explicitly triggers it; the harvest log is exported via the existing settings-export ZIP flow.
- Mirror the Phase 78/84 "ship+monitor" pattern (per `PROJECT.md` line 233): the probe gathers data, a follow-up phase analyzes if signal is sufficient.

**Warning signs:**
- Probe pipeline shows up in `pactl list sink-inputs` alongside the user's playback
- Audio doubles up briefly when probe starts
- Probe drops the user's main connection (SomaFM's per-IP cap)

**Phase to address:**
SomaFM preroll consistency phase (suggested: Phase 90). Mirror-source rule: when CONTEXT.md says "Boot Liquor has no preroll because…", cite the actual server response (curl output with headers + first 8KB) — do not paraphrase. Spike-first to capture the actual responses from 5 SomaFM stations (4 known-good per `PROJECT.md` line 19 + Boot Liquor) before designing the fix.

---

### Pitfall 12: Touching player.py for preroll debug regresses Phase 84 buffer adaptation

**What goes wrong:**
Adding preroll-probe instrumentation requires logging from `_on_gst_tag` or `_on_gst_stream_start`. The developer adds a `print()` or a log-emit on the GLib bus thread. The Phase 84 stage-and-apply fallback (per `PROJECT.md` line 233 — "stage at _on_underrun_cycle_closed, apply at next URI bind") relies on a specific ordering of signal emissions. The new log statement perturbs Qt's signal coalescing — the `set_property` write that was supposed to be staged fires too early.

**Why it happens:**
GStreamer bus → Qt signal marshaling is fragile (per `.planning/codebase/CONCERNS.md` "GStreamer Bus-Loop Threading Model" and "MPRIS2 Service Registration"). Any new signal/slot path or new code in the bus handler can change the queue order under load.

**How to avoid:**
- Preroll instrumentation MUST go in a new function called from existing `_on_gst_tag` AT THE END, never INSERT into the middle. Never add it to `_on_gst_buffering` or `_on_underrun_cycle_closed`.
- Add a regression test that pins the Phase 84 stage-and-apply ordering via source-grep, not behavior: assert that in `_try_next_stream`, the `_set_uri` call appears in source AFTER any stage-and-apply marker (per `feedback_gstreamer_mock_blind_spot.md` — source-grep over mocked behavior).
- Re-run the Phase 84 D-11 acceptance test (12-event harvest replay) before merging the preroll-probe phase. If the harvest replay diverges, revert.
- BUFFER-MONITOR (`PROJECT.md` line 21) is gated on three Follow-Up Triggers; the preroll-probe phase must not fire any of them spuriously.

**Warning signs:**
- After adding preroll instrumentation, the buffer-events.log shows underruns recovering at 30s when previously they grew to 60s
- Pause/resume on AAC streams introduces a new glitch (BUG-03 reopened)
- New flakiness in `test_player_*.py` — Qt signal ordering tests are the most sensitive

**Phase to address:**
SomaFM preroll phase (Phase 90). Add the Phase 84 stage-and-apply order drift-guard as part of Phase 90's deliverables, not as a separate phase.

---

### Pitfall 13: Phase 71 sibling rendering regression when touching NowPlayingPanel for cover-avatar fallback

**What goes wrong:**
The cover-slot fallback chain (Pitfall 8) requires conditional rendering in `NowPlayingPanel`. The developer touches `_set_cover_pixmap` to add the avatar branch. The Phase 71 "Also on:" sibling line stops rendering (or renders twice, or renders the wrong chips) because the panel's overall paint path was reshuffled.

**Why it happens:**
`now_playing_panel.py` is one of the large modules (645 lines per `.planning/codebase/CONCERNS.md` "Module Size & Cognitive Load") with multiple intersecting state machines. Per-row sibling chips (Phase 71 D-14, D-15 — manual chips show `×`, AA chips don't) depend on subtle widget composition order.

**How to avoid:**
- Read Phase 71's `71-CONTEXT.md` D-14 + D-15 locked decisions BEFORE editing the panel. The "the presence/absence of the × button is the sole visual distinction" rule has no other indicator — any rendering reorder that drops the × button silently breaks the manual-vs-AA distinction.
- Add `test_richtext_baseline_unchanged_by_phase_89` mirroring Phase 71's existing `test_richtext_baseline_unchanged_by_phase_71` drift-guard (per `PROJECT.md` Phase 71 row).
- Run a manual UAT on a station that HAS siblings (cross-network AA station) AND ICY-disabled cover-avatar fallback in the same session. Both must render correctly.
- Apply `feedback_ui_bug_verify_with_extremes.md`: before fixing any perceived layout issue, sweep widget through extreme states (empty / full siblings list; placeholder / avatar / iTunes cover) and confirm what the user actually sees — do not chase shadows.

**Warning signs:**
- Sibling chips render but show all as manual (with ×) or all as AA (without ×) — the discriminator was lost in a refactor
- Sibling line disappears entirely on YouTube/ICY-disabled stations after the avatar fallback ships
- `test_richtext_baseline_unchanged_by_phase_71` fails — Phase 71's existing guard caught the regression at the right time

**Phase to address:**
ICY-disabled cover fallback phase (Phase 89). Required test addition: Phase 71 baseline drift-guard parity.

---

### Pitfall 14: Phase 76 GBS subprocess reuse mistake — establishing a parallel session for marquee fetch

**What goes wrong:**
Marquee fetcher spawns its own QtWebEngine subprocess "for isolation". Each marquee poll prompts a fresh login. The user logs in once via the Phase 76 flow and is then surprised by repeated login prompts when the themed-day/marquee detector polls.

**Why it happens:**
The natural design temptation is "subprocess = clean state = no risk of UI freeze". But the Phase 76 cookies are bound to the FIRST subprocess's persistent storage path (Pitfall 5). A second subprocess without the same storage-path argument is a fresh anonymous session.

**How to avoid:**
- Single source of truth: define `GBS_WEB_PROFILE_NAME = "musicstreamer-gbs"` and `GBS_WEB_STORAGE_PATH = paths.gbs_web_storage_dir()` as module-level constants in `musicstreamer/gbs_auth.py` (the Phase 76 module).
- Marquee fetcher imports the same constants and constructs its `QWebEngineProfile` with them.
- Source-grep gate: `assert GBS_WEB_PROFILE_NAME in marquee_source` AND `assert "QWebEngineProfile(" in marquee_source and "gbs_auth" in marquee_source` per `feedback_gstreamer_mock_blind_spot.md`.
- Drift-guard test: introspect both source files and assert they reference the same constant identifier (parallel to Phase 77's FakePlayer-only-in-_fake_player.py rule per `PROJECT.md` line 231).

**Warning signs:**
- User reports "GBS login keeps popping up" — instant signal of a parallel session
- `~/.local/share/musicstreamer/QtWebEngine/` has two directories instead of one

**Phase to address:**
GBS.FM themed-day / marquee phase (Phase 87). Constants must move into `gbs_auth.py` in Phase 87's first plan (not its last).

---

### Pitfall 15: Phase 77 D-03-deferred MPRIS2 tests masquerade as environment-gap when the bug is in the test fixture

**What goes wrong:**
The 7 D-03-deferred MPRIS2 tests fail on Linux CI. The developer attributes the failures to "PyGObject not installed" (per `PROJECT.md` line 60). PyGObject IS installed. The real cause is a test-fixture bug — the FakePlayer pattern is duplicated in the failing test file, violating Phase 77 D-04 (per `PROJECT.md` line 231 — "only tests/_fake_player.py may declare FakePlayer").

**Why it happens:**
"Environment gap" is a comforting hypothesis that absolves the test author. The failure modes look identical (collection error or `AttributeError`), so without source-grep verification, the wrong cause is locked in.

**How to avoid:**
- Run `grep -rn "class FakePlayer(QObject)" tests/` BEFORE running the failing tests. If any file other than `tests/_fake_player.py` matches, the failure is structural, not environmental.
- Reuse the Phase 77 source-introspection drift-guards. If `tests/test_mpris2_*.py` declares its own FakePlayer, delete that declaration and import from `tests/_fake_player.py`.
- If after the import-fix the tests still fail, gather the actual error message (not the surface symptom) and verify against current PyGObject release notes. PyGObject does NOT silently disable D-Bus when it's missing — it raises ImportError loudly at the top of the failing test file.

**Warning signs:**
- "Environment gap" appears in two consecutive phase docs without resolution — usually means nobody verified the hypothesis
- `grep "class FakePlayer" tests/ | wc -l` returns > 1

**Phase to address:**
FIX-MPRIS phase (suggested: Phase 91, the existing v2.2 carry-over). The first plan of Phase 91 is the source-grep verification, not the test fix.

---

### Pitfall 16: Don't break Windows packaging while building Linux packaging

**What goes wrong:**
The developer adds an AppImage-specific `AppRun` path to `musicstreamer/paths.py` or `musicstreamer/__main__.py`. A latent Windows code path stops working because the new branch unconditionally reads `os.environ['APPDIR']` (which is None on Windows).

**Why it happens:**
AppImage's AppRun environment is invisible from Linux dev boxes that don't extract+run the AppImage. A "this only fires inside AppImage" branch is easy to write without realizing it imports or references something Windows-specific.

**How to avoid:**
- Every Linux-specific path must be gated by `sys.platform == 'linux'` AT THE TOP. Never read `os.environ['APPDIR']` without a `sys.platform` check first.
- After every Linux packaging change, run `tools/check_subprocess_guard.py`, `tools/check_spec_entry.py`, and the Windows packaging-spec drift-guards (per `packaging/windows/README.md`) on the Linux dev box BEFORE committing. These tests run cross-platform; they catch most Windows regressions.
- The Phase 69 packaging drift-guards (`tests/test_packaging_spec.py`) must be extended to ALSO cover the Linux recipe — single suite enforcing both targets.

**Warning signs:**
- `tools/check_bundle_plugins.py` exits non-zero on a Win11 VM after a Linux-only PR
- `tests/test_packaging_spec.py` adds a new test but the file's existing Windows tests start failing — usually a copy-paste import issue

**Phase to address:**
Linux AppImage phase (Phase 85) and Linux Flatpak phase (Phase 86) — both must have a "verify Windows build still works" success criterion. Bundled UAT (per `PROJECT.md` line 17 — "Win11 VM packaging UAT bundled with WIN-05 AAC retest") should happen AFTER both Linux phases, not before.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Use `os.environ['APPDIR']` directly without `sys.platform` check | One-line branch | Silently breaks Windows imports | **Never** — always gate with platform check |
| Skip the AppImage cross-distro test matrix | "It works on my Ubuntu, ship it" | Cascading user reports from Fedora/openSUSE | **Never** — test on at least 3 distros before publishing |
| Inline the AUMID literal in `__main__.py` and `MusicStreamer.iss` separately | Faster initial code | Silent SMTC breakage on drift | **Never** — single constant, parity test enforced |
| Use yt-dlp's `thumbnail` field for channel avatar | One-line fetch | Wrong image type (video frame, not avatar) | **Never** — filter by `id == 'avatar_uncropped'` |
| Spawn a second QtWebEngine subprocess for marquee | "Isolation" | Re-login storm | **Never** — reuse the Phase 76 profile |
| Inline channel-avatar branch BEFORE MB-CAA fallback in cover resolver | Simpler control flow | Phase 73 MB-CAA dies silently for Vaporwave/niche electronic | **Never** — channel-avatar is second-to-last, not first |
| Disable QtWebEngine sandbox in AppImage manifest "just in case" | Avoids one class of crash | Defeats security model with no benefit | Acceptable inside Flatpak (sandbox-in-sandbox is impossible — Pitfall 4), never in AppImage |
| Track GBS themed-day via `Last-Modified` header | Cheap probe | CDN cache invalidation = false positive | **Never** — use SHA-256 of content + marquee keyword corroboration |
| Probe SomaFM preroll with a real GStreamer pipeline | Reuses existing infra | Doubles up audio, fights for upstream connection | **Never** — use `requests.get(stream=True, headers={'Icy-MetaData': '1'})` |
| Persist GBS themed-day decision to SQLite | Survives restart | Sticks past the actual themed day | **Never** — session-scoped (per `PROJECT.md` line 23) |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| linuxdeploy-plugin-gstreamer | Trust host's `gst-plugin-scanner` cache | Bundle scanner, force re-scan at AppRun, set `GST_REGISTRY_FORK=no` |
| Flatpak QtWebEngine | `--filesystem=host` to "fix" cookie persistence | Use `io.qt.qtwebengine.BaseApp` + `QTWEBENGINE_DISABLE_SANDBOX=1` + `setPersistentStoragePath()` to `~/.var/app/com.musicstreamer.MusicStreamer/data/` (XDG-redirected automatically) |
| Flathub Node.js runtime | Assume Node is in the GNOME runtime | Add `org.freedesktop.Sdk.Extension.node20` (or current LTS) to `sdk-extensions:` and `append-path: /usr/lib/sdk/node20/bin` to `build-options:` |
| yt-dlp channel avatar | Use top-level `thumbnail` | Iterate `thumbnails[]` and filter by `id == 'avatar_uncropped'` |
| Twitch Helix `/users` for avatar | Reuse Phase 32 user token without checking scopes | Helix `/users` accepts both user and app token; cache `profile_image_url` per [Twitch API docs](https://dev.twitch.tv/docs/api/) (24 hr is community standard); rate limit is 800 req/min/client, well above need |
| Inno Setup `[Icons]` | Omit `AppUserModelID:` clause | Add clause + `tests/test_aumid_string_parity.py` extension that greps the `.iss` literal |
| QtWebEngine cookie store | New `QWebEngineProfile()` per process | Single `QWebEngineProfile("musicstreamer-gbs", parent)` + `setPersistentStoragePath()` + `ForcePersistentCookies` policy, shared across subprocess and main process by storage path identity |
| GBS.FM marquee parse | `text.split('|')[0]` | Inspect 10 real samples, define delimiter as `" | "` (spaces required), fall back to newline / max-length |
| SomaFM preroll probe | Spawn second `playbin3` | `requests.get` with `Icy-MetaData: 1`, 30 s read, separate log file |
| MPRIS2 deferred tests | Blame "environment gap" | `grep "class FakePlayer" tests/` first; expected count is 1 |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Channel-avatar fetch races playback start | UI flicker — placeholder → real cover → channel avatar → placeholder | Fetch avatar in background ONLY when ICY tag fires empty/disabled; never on playback start | Any station with > 100 ms avatar fetch latency |
| AppImage GStreamer plugin re-scan on every launch | 2–4 s cold-start delay | Persist `$XDG_CACHE_HOME/musicstreamer/gstreamer-1.0/registry.x86_64.bin`, invalidate on AppImage version change | Always — eliminate via cached registry |
| Twitch Helix `/users` polled per-render | Rate-limit at 800 req/min × users | Cache `profile_image_url` for 24 hours; refresh on stream-start, not on UI render | > 30 Twitch stations with offline polling |
| QtWebEngine subprocess startup on every marquee poll | 1–2 s lag per poll, login storms | Persistent QtWebEngine profile, hidden `QWebEnginePage` reused; poll cadence ≥ 5 min | Any cadence < 5 min |
| GBS themed-logo SHA-256 recomputed every poll | Bandwidth + CPU | Cache hash for session; recompute only on `Last-Modified` change (use header as INVALIDATION trigger, not authority) | Always — combine both signals |
| SomaFM preroll-probe consumes user's connection slot | Main playback drops during probe | Run probe ONLY when user is not actively playing that station, OR use a separate stream tier so SomaFM doesn't dedupe | When probe is automatic, not opt-in |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| `--filesystem=host` in Flatpak manifest | Defeats sandbox entirely | Use `--filesystem=xdg-music:ro` (read-only music dir) + XDG-redirected app data; nothing else |
| Flatpak `--socket=session-bus` for MPRIS2 with no portal | Exposes full session D-Bus | Use `--talk-name=org.mpris.MediaPlayer2.*` ONLY (most-specific bus name allow-list) |
| GBS.FM cookie file world-readable inside AppImage | Cookie theft via shared system | `chmod 0700` on `~/.local/share/musicstreamer/QtWebEngine/` at first-write; same pattern as `cookies.txt` 0o600 (per `PROJECT.md` line 72) |
| Twitch token re-used for Helix `/users` without scope check | Phase 32 TAUTH-01 token may lack required scope | Helix `/users` for OTHER users (not self) needs only client-id, no token; for self use app access token. Channel-avatar fetch is for arbitrary streamers → use app access token, not the user's OAuth token |
| Inno Setup uninstaller leaves cookies/tokens in `%APPDATA%\musicstreamer` | Stranded sensitive data on uninstall | Existing decision (per `packaging/windows/README.md` D-03) is intentional preservation; document it in the EULA + give users a hamburger-menu "Wipe local data" action if they want manual cleanup |
| Marquee fetcher follows redirects to off-domain URLs | XSS via redirect-to-attacker-domain | Pin allowed hosts: `gbs.fm`, `www.gbs.fm`, `cdn.gbs.fm`. Reject any redirect outside this set |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| "1 token" or "tokens remaining" terminology in GBS single-song add | Users don't know what tokens are; feels gamified | Frame as "Add this song" with no quantity (per `PROJECT.md` line 18 — "zero-token single-song add, UX never framed as '1 token'") |
| Channel-avatar suddenly replacing a working cover slot | Visual surprise — looks broken | Avatar fallback only when ICY is empty/disabled. Fade-in transition, not hard swap |
| Themed logo fires once and never updates | User restarts mid-weekend, doesn't see themed look | Re-evaluate themed-day on every GBS launch (session-scoped, not persistent) — accept the trade-off that closing and reopening can change the answer |
| AppImage requires `chmod +x` before running | First-run friction | Document in README + ship a wrapper `.desktop` file that GNOME associates automatically |
| Flatpak launches but media keys silent | Confusing — same app, different behavior | Document MPRIS2 D-Bus access in Flathub description; provide a "Test media keys" diagnostic in hamburger menu |
| SMTC "Unknown app" after upgrade | User pinned a pre-AUMID shortcut | One-time release-note prompt: "Unpin and re-pin MusicStreamer from your taskbar after this update" |
| Background art makes UI look broken at extreme widget states | Per `feedback_ui_bug_verify_with_extremes.md` — three rounds of hardening chasing a headphones-illustration stroke | Before fixing a perceived layout bug, sweep widget through 0/100% and ask user to confirm what they see |

---

## "Looks Done But Isn't" Checklist

- [ ] **AppImage:** Often missing GLIBC baseline pinning — verify with `strings AppRun_or_main_so | grep GLIBC_ | sort -V | tail -1 ≤ 2.35`
- [ ] **AppImage:** Often missing `gst-plugin-scanner` — verify with `test -x $APPDIR/usr/libexec/gstreamer-1.0/gst-plugin-scanner`
- [ ] **AppImage:** Often missing `gst-libav` — verify with `gst-inspect-1.0 avdec_aac` inside the AppImage shell
- [ ] **AppImage:** Often missing `chardet>=5,<6` pin — verify `requests` works in staged build dir without `charset_normalizer` errors
- [ ] **Flatpak:** Often missing `QTWEBENGINE_DISABLE_SANDBOX=1` in finish-args — verify GBS login subprocess opens without namespace error
- [ ] **Flatpak:** Often missing Node.js extension — verify with `flatpak run --command=node com.musicstreamer.MusicStreamer --version`
- [ ] **Flatpak:** Often missing MPRIS2 D-Bus access — verify with `flatpak run --command=dbus-send com.musicstreamer.MusicStreamer --session --print-reply --dest=org.mpris.MediaPlayer2.MusicStreamer /org/mpris/MediaPlayer2 org.freedesktop.DBus.Properties.GetAll string:org.mpris.MediaPlayer2.Player`
- [ ] **Flatpak:** Often `--filesystem=host` slipped in — verify manifest greps clean for `host` outside of comments
- [ ] **SMTC AUMID:** Often `MusicStreamer.iss` AUMID literal drifted from `__main__.py` — verify `tests/test_aumid_string_parity.py` passes
- [ ] **SMTC AUMID:** Often old .lnk not removed by uninstaller — verify with VM that has v2.1 installed FIRST, then upgrades to v2.2
- [ ] **SMTC AUMID:** Often AUMID set AFTER `QApplication()` — verify with `ProcessExplorer` or `Get-StartApps` after launch (per `packaging/windows/README.md` Phase 43.1 Pitfall #7)
- [ ] **GBS marquee:** Often single `|` content treated as delimiter — verify with 10 historical marquee samples
- [ ] **GBS themed-day:** Often persisted to SQLite — verify session-only, restart mid-weekend produces fresh evaluation
- [ ] **Channel avatar:** Often using top-level `thumbnail` — verify the saved image is square (avatar) not 16:9 (video frame)
- [ ] **Channel avatar:** Often runs BEFORE MB-CAA — verify cover-resolver source order via grep gate
- [ ] **SomaFM preroll:** Often probe is a real `playbin3` — verify probe is `requests.get` only, no GStreamer
- [ ] **Phase 77 deferred MPRIS2:** Often blamed on env-gap — verify `grep "class FakePlayer" tests/ | wc -l == 1` first

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| AppImage GLIBC mismatch shipped | HIGH | Rebuild on older container, version-bump, push out as patch release; users who hit the error get no playback at all |
| linuxdeploy GStreamer scanner cache poisoned | MEDIUM | Ship a new AppImage that force-rebuilds the registry on first launch; users delete `~/.cache/musicstreamer/gstreamer-1.0/` |
| Flatpak QtWebEngine sandbox crash | LOW | Add `QTWEBENGINE_DISABLE_SANDBOX=1` to manifest, push update via Flathub; users get update automatically |
| SMTC AUMID parity drift | LOW (fresh installs) / HIGH (pinned shortcuts) | Parity test catches drift before ship; for already-pinned shortcuts, instruct user to unpin+repin |
| Channel-avatar overrides MB-CAA (Pitfall 8) | MEDIUM | Re-order cover resolver, add drift-guard test, push patch release; affected stations remain on placeholder in the interim |
| GBS themed-day false positive | LOW | Hot-fix the SHA-256 canonical-logo constant, push release; user-visible bug is cosmetic |
| GBS subprocess login storm (Pitfall 14) | MEDIUM | Refactor marquee fetcher to import Phase 76 constants; users re-login once after the fix |
| SomaFM preroll probe disrupts main session | LOW | Make probe opt-in via hamburger menu (it already should be — Pitfall 11); users who haven't triggered the probe are unaffected |
| Phase 84 buffer adaptation regressed by preroll instrumentation | HIGH | Revert preroll commits, re-run Phase 84 D-11 acceptance test, redesign instrumentation with strict bus-handler discipline |
| Phase 71 sibling rendering regressed | MEDIUM | Restore baseline drift-guard, fix render order; sibling line briefly missing for affected stations |
| Phase 77 deferred MPRIS2 misdiagnosed | LOW | Run source-grep first, fix FakePlayer duplication, tests pass without env changes |

---

## Pitfall-to-Phase Mapping

Phase numbers are suggested (continuing from Phase 84 per `PROJECT.md` line 23). Final numbering is roadmap-author's call.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1: AppImage GLIBC baseline | Phase 85 (AppImage) | `strings $APPDIR/AppRun \| grep -oE 'GLIBC_[0-9.]+' \| sort -V \| tail -1` ≤ 2.35 on every CI build |
| 2: GStreamer plugin scanner paths | Phase 85 (AppImage) | `tests/test_packaging_spec.py::test_apprun_sets_gst_plugin_paths` source-grep |
| 3: charset_normalizer mypyc dropped | Phase 85 (AppImage) | `tests/test_packaging_spec.py::test_pyproject_pins_chardet_over_charset_normalizer` |
| 4: Flatpak QtWebEngine sandbox | Phase 86 (Flatpak) | Manifest contains `QTWEBENGINE_DISABLE_SANDBOX=1` AND `io.qt.qtwebengine.BaseApp` extension; live GBS login works in Flatpak build |
| 5: QtWebEngine cookie store sharing | Phase 87 (GBS marquee) | `tests/test_gbs_marquee.py::test_marquee_fetcher_reuses_gbs_auth_profile` source-grep + manual: kill+restart subprocess, marquee still authed |
| 6: SMTC AUMID mismatch | Phase 88 (WIN-02) | Extended `tests/test_aumid_string_parity.py` covers `.iss` + uninstaller `InstallDelete` clause |
| 7: yt-dlp channel-avatar field | Phase 89 (cover-avatar fallback) | `tests/test_channel_avatar.py::test_uses_avatar_uncropped_id_filter` source-grep + golden-master JSON from `yt-dlp -J` for 3 channel URL shapes |
| 8: Channel-avatar precedence vs MB-CAA | Phase 89 (cover-avatar fallback) | `tests/test_cover_resolution_precedence.py::test_mb_caa_runs_before_channel_avatar` source-introspection |
| 9: GBS themed-logo CDN drift | Phase 87 (GBS themed-day) | `tests/test_gbs_themed.py::test_themed_decision_uses_content_hash_not_last_modified` + marquee keyword corroboration |
| 10: Marquee pipe-segment parsing | Phase 87 (GBS marquee) | Golden-master test with 10 historical marquee strings + expected banner outputs |
| 11: SomaFM preroll probe destruction | Phase 90 (SomaFM preroll) | `tests/test_somafm_preroll.py::test_probe_uses_requests_not_gstreamer` source-grep |
| 12: Phase 84 buffer adaptation regression | Phase 90 (SomaFM preroll) | `tests/test_player.py::test_phase_84_stage_and_apply_order_unchanged_by_phase_90` source-introspection drift-guard |
| 13: Phase 71 sibling rendering regression | Phase 89 (cover-avatar fallback) | `tests/test_now_playing.py::test_richtext_baseline_unchanged_by_phase_89` (mirror Phase 71's existing guard) |
| 14: Phase 76 GBS subprocess parallel session | Phase 87 (GBS marquee) | Constants module test: `marquee_fetcher` source imports from `gbs_auth` module |
| 15: Phase 77 MPRIS2 env-gap misdiagnosis | Phase 91 (FIX-MPRIS) | `grep "class FakePlayer" tests/ \| wc -l == 1` as first plan deliverable |
| 16: Windows packaging regression from Linux work | Phase 85 + 86 + 88 (all packaging) | Existing `tools/check_subprocess_guard.py`, `tools/check_spec_entry.py`, `tests/test_packaging_spec.py` must pass after every Linux PR |

---

## Spike-First Candidates

The following items are recommended for explicit spike phases or spike-style first plans BEFORE locking architecture:

1. **AppImage build container baseline** — pick Ubuntu 22.04 or 20.04, build a hello-world GTK+GStreamer AppImage, test on 3 target distros. Decide baseline BEFORE Phase 85.
2. **Flatpak QtWebEngine BaseApp** — build a minimal QtWebEngine-based Flatpak that loads `https://gbs.fm` and reads cookies on restart. Decide manifest shape BEFORE Phase 86.
3. **QtWebEngine cookie persistence cross-process** — verify `setPersistentStoragePath()` + `ForcePersistentCookies` survives subprocess exit, restart, and is readable by a hidden `QWebEnginePage` in the main process. BEFORE Phase 87.
4. **yt-dlp channel-avatar field discovery** — run `yt-dlp -J` against 5 channel URL shapes, harvest the actual JSON, document which `thumbnails[].id` values are reliable. BEFORE Phase 89.
5. **SomaFM preroll harvest** — non-destructive `requests.get(stream=True, headers={'Icy-MetaData': '1'})` on Boot Liquor + 4 known-good stations, capture 30 s of metadata. BEFORE Phase 90 design.

---

## Sources

- [AppImage best practices — GLIBC compatibility](https://docs.appimage.org/reference/best-practices.html)
- [pkg2appimage #173 — Bundle libstdc++ and decide at runtime](https://github.com/AppImage/pkg2appimage/issues/173)
- [linuxdeploy-plugin-gstreamer — official repo](https://github.com/linuxdeploy/linuxdeploy-plugin-gstreamer)
- [linuxdeploy-plugin-gstreamer #17 — gst-plugin-scanner library path](https://github.com/linuxdeploy/linuxdeploy-plugin-gstreamer/issues/17)
- [linuxdeploy-plugin-gstreamer #9 — built on Ubuntu 18.04 doesn't run on 18.04](https://github.com/linuxdeploy/linuxdeploy-plugin-gstreamer/issues/9)
- [Flathub io.qt.qtwebengine.BaseApp](https://github.com/flathub/io.qt.qtwebengine.BaseApp)
- [Qt WebEngine Platform Notes — sandboxing](https://doc.qt.io/qt-6/qtwebengine-platform-notes.html)
- [QWebEngineProfile docs — persistent storage and cookies](https://doc.qt.io/qt-6/qwebengineprofile.html)
- [flatpak/flatpak #4032 — Chromium or Flatpak sandbox is active?](https://github.com/flatpak/flatpak/issues/4032)
- [Flathub Discourse — Distributing a Qt app in a flatpak with WebEngine](https://discourse.flathub.org/t/distributing-a-qt-app-in-a-flatpak-with-webengine/5224)
- [yt-dlp #10090 — Channel thumbnails often missing banner_uncropped](https://github.com/yt-dlp/yt-dlp/issues/10090)
- [yt-dlp #14041 — Better way to handle thumbnails](https://github.com/yt-dlp/yt-dlp/issues/14041)
- [Inno Setup [Icons] section](https://jrsoftware.org/ishelp/topic_iconssection.htm)
- [Twitch API Concepts — rate limits](https://dev.twitch.tv/docs/api/guide)
- [Twitch Developer Forums — 800 req/min app access token](https://discuss.dev.twitch.com/t/what-is-the-rate-limit/30504)
- [Microsoft Learn — Application User Model IDs](https://learn.microsoft.com/en-us/windows/win32/shell/appids)
- Internal: `packaging/windows/README.md` (Phase 43.1 + Phase 56 + Phase 69 lessons)
- Internal: `.planning/codebase/CONCERNS.md` (GStreamer Bus-Loop Threading Model, MPRIS2 Service Registration, Windows Packaging Case-Sensitivity Collision)
- Internal: `.planning/PROJECT.md` (Phase 71 sibling rendering decisions D-14/D-15; Phase 73 ART-MB precedence; Phase 76 GBS-AUTH-01; Phase 77 D-04 FakePlayer rule; Phase 84 D-11 stage-and-apply)
- Internal: `feedback_gstreamer_mock_blind_spot.md` (source-grep gates over behavioral mocks)
- Internal: `feedback_mirror_decisions_cite_source.md` (quote external rules, never paraphrase)
- Internal: `feedback_ui_bug_verify_with_extremes.md` (sweep widget states before fixing perceived layout bugs)
- Internal: `project_vaporwave_mb_caa_coverage.md` (MB-CAA coverage gap motivating Pitfall 8 precedence rule)

---

*Pitfalls research for: MusicStreamer v2.2 — packaging + GBS.FM + channel-avatar + SomaFM preroll*
*Researched: 2026-05-25*
