# Codebase Concerns

**Analysis Date:** 2026-04-28

## Tech Debt

**GStreamer Bus-Loop Threading Model:**
- Issue: Complex cross-thread coordination between GLib MainLoop daemon thread (GstBusLoopThread) and Qt main thread. Bus signal handlers run on non-Qt thread and must emit Qt signals rather than touching QTimer/state directly. Latent race windows.
- Files: `musicstreamer/player.py` (44–150, 323–335), `musicstreamer/gst_bus_bridge.py`
- Impact: Subtle threading bugs hard to reproduce. Phase 43.1 revealed `bus.add_signal_watch()` must run on GLib thread, not Qt thread, or bus handlers silently drop. Regressed failover timing 10s during Phase 43 on Windows (bus never dispatched).
- Fix approach: Document threadings contracts in player.py module docstring (already done, lines 3–24). Consider extracting bus-handler pattern into a reusable thread-marshaling library for future projects. Audit all `Signal` emits from `_on_gst_*` handlers for Qt-affinity violations (Phase 35–50 already addressed via queued connections, but fragile to future maintainers).

**EQ Toggle Dropout (BUG-03):**
- Issue: Toggling EQ on/off via `set_eq_enabled()` briefly stops audio playback when equalizer element is bypassed/applied mid-stream. Phase 52 requirement not yet addressed.
- Files: `musicstreamer/player.py:211–227` (set_eq_enabled, _apply_eq_state)
- Impact: Audible glitch when user clicks EQ toggle button; playback resumes after dropout (not fatal, but jarring UX).
- Fix approach: Investigate whether GStreamer 1.28+ has a gap-free EQ bypass mechanism (e.g., drain event or flush-before-state-change). May require padding the buffer or deferring the element state change until after a sync point. Phase 52 should spike this before planning.

**Audio Buffer Underrun Resilience (BUG-09):**
- Issue: Intermittent playback dropouts/stutters when GStreamer buffer can't keep up (network stalls, CPU stalls). Currently unobservable to user; no visible indicator of buffering recovery. Phase 62 planned.
- Files: `musicstreamer/player.py:103–104` (BUFFER_DURATION_S=10s, BUFFER_SIZE_BYTES=10MB), `musicstreamer/_on_gst_buffering` (phase 47.1 adds buffer-percent signal, D-12)
- Impact: Random dropout reports from users without clear repro conditions. No diagnostic telemetry. Could indicate network/CPU bottleneck, decoder stall, or GStreamer internal issue.
- Fix approach: Phase 62 must add instrumentation: log all buffering events (< 100%) with timestamp and cause attribution (network stall vs CPU vs decoder). Emit toast when buffering recovery in progress. Once instrumentation reveals root cause, ship behavioral fix (e.g. adjusted buffer constants, smarter underrun recovery, reconnect logic). Current buffer-duration/buffer-size are Phase 16 baseline (10s/10MB) — preserve unless explicit override during Phase 62.

**Module Size & Cognitive Load:**
- Issue: Several core UI modules are large (798 lines: edit_station_dialog.py; 700: player.py; 659: main_window.py; 645: now_playing_panel.py; 556: station_list_panel.py). Each contains multiple responsibilities and state machines.
- Files: `musicstreamer/ui_qt/edit_station_dialog.py`, `musicstreamer/player.py`, `musicstreamer/ui_qt/main_window.py`
- Impact: High surface area for bugs, difficult to refactor or extract smaller units. New contributors need to understand entire module to make safe changes. Test coverage is by module, not by logical unit.
- Fix approach: Long-term refactoring (not v2.1 priority) — consider breaking edit_station_dialog into smaller pieces (stream-table delegate, tag-chip flow, logo-fetch worker moved to separate module). player.py is already split logically (error recovery, failover, EQ) but coupled tightly. Main_window is the orchestrator — intentionally large but could benefit from extracting signal-routing into a dedicated mediator.

**MPRIS2 Multi-Instance Limitation:**
- Issue: MPRIS2 service publishes as `org.musicstreamer.MusicStreamer` (line 255 in mpris2.py), with TODO comment for supporting unique suffix (e.g. `org.musicstreamer.MusicStreamer.instance2`). Only one instance of the app can expose MPRIS2 at a time.
- Files: `musicstreamer/media_keys/mpris2.py:255`
- Impact: If user runs two concurrent MusicStreamer instances on Linux, only the first one claims the MPRIS2 bus name and responds to media keys. Second instance is silent.
- Fix approach: Not urgent (single-user app); Phase 41 comment documents the limitation. Implementation would require tracking instance ID at startup and appending to service name. Low priority for v2.1.

**OAuth Token Subprocess Isolation:**
- Issue: oauth_helper.py subprocess (QWebEngineView) handles Twitch login and token capture (Phase 32). Token written to `TWITCH_TOKEN_PATH` with 0o600 perms. Attack surface: if subprocess is compromised, token could be exfiltrated.
- Files: `musicstreamer/oauth_helper.py` (1–127), `musicstreamer/ui_qt/accounts_dialog.py:197–223` (_launch_oauth_subprocess), `musicstreamer/constants.py` (TWITCH_TOKEN_PATH)
- Impact: Low risk in current form (subprocess runs locally, token stored in user homedir with 0o600). But subprocess does not validate redirect URLs, could be tricked by DNS hijacking to send token elsewhere.
- Fix approach: Phase 32 design is sound for single-user desktop app. If OAuth scope expands (multiple services, cloud sync), audit subprocess communication for token leakage. Current mitigation: subprocess never logs tokens, 0o600 file perms, token only used to build `Authorization` header, no token persistence across sessions.

**Windows Packaging Case-Sensitivity Collision:**
- Issue: Phase 44 installer placed app data at `%LOCALAPPDATA%\MusicStreamer` (capital) while platformdirs default on Windows is `%LOCALAPPDATA%\musicstreamer` (lowercase). On case-insensitive NTFS, these alias to the same directory, causing the uninstaller to block (user-data dir inside install dir).
- Files: `musicstreamer/paths.py` (uses platformdirs.user_data_dir), PyInstaller .spec and Inno Setup installer scripts (Phase 44)
- Impact: Windows uninstaller fails if user-data was ever written. Potential stranded data left behind on uninstall. User must manually delete `%LOCALAPPDATA%\musicstreamer` or rename it before uninstalling.
- Fix approach: Phase 56 or 44-follow-up should standardize on ONE case convention. Recommendation: use lowercase `musicstreamer` everywhere (matches Linux/macOS convention). Installer should force-create this at the time of install, set install dir to `Program Files\MusicStreamer` (capital for visibility), and user-data goes to `%LOCALAPPDATA%\musicstreamer` (lowercase, isolated from install tree).

**yt-dlp Library vs Subprocess Trade-offs:**
- Issue: Phase 35 migrated from mpv subprocess to yt-dlp library API to avoid spawning heavy process. Library API requires Node.js runtime for EJS n-challenge solver (`js_runtimes={"node": {"path": None}}`). Phase 999.9 pinned `player_client=web` after upstream dropped `extractor_args["youtubepot-jsruntime"]`. Fragile dependency on undocumented yt-dlp internals.
- Files: `musicstreamer/player.py:420–480` (_youtube_resolve_worker), `musicstreamer/yt_import.py` (scan_playlist, uses library API)
- Impact: YouTube playback breaks if yt-dlp internals change (new n-challenge solver, new player_client removal, etc.). Phase 49 regression (BUG-07) was suspected yt-dlp version issue (user reinstalled both yt-dlp + GStreamer plugins, one fixed it, not bisected).
- Fix approach: Maintain fallback subprocess path for yt-dlp CLI if library API breaks. Keep Node.js runtime validation in runtime_check.py (already present, Phase 44 confirms it). Monitor yt-dlp changelog for breaking changes to extractor_args or player_client. Consider pinning yt-dlp to a stable release family if breakage accumulates.

**GStreamer Windows Plugin Availability:**
- Issue: Phase 43 identified that `gst-libav` is REQUIRED on Windows for AAC/H.264 decoders, and GStreamer 1.28+ has a breaking change (decodebin3 hard-fails if ANY pad lacks a decoder, even pads not routed to sink). Phase 43.1 workaround: `flags & ~0x1` on playbin3 to skip video pad on audio-only HLS.
- Files: `musicstreamer/player.py:96–99` (flags & ~0x1), Phase 43 findings documented in `.planning/phases/43-gstreamer-windows-spike/43-SPIKE-FINDINGS.md` and `.claude/skills/spike-findings-musicstreamer/SKILL.md`
- Impact: If gst-libav is missing from the bundled runtime, any AAC/H.264 stream (most HLS) fails silently. PyInstaller bundle validation happens once at release time; users cannot self-heal missing codecs.
- Fix approach: Phase 44 bundling confirmed gst-libav is present in conda-forge build. Smoke test in PyInstaller build validates HLS playback. Before shipping any Windows release, always verify gst-libav presence in the bundle (conda list gst-libav or py -m pip list | grep gst-libav). Consider adding runtime check in runtime_check.py to warn user if expected GStreamer plugins are missing at startup.

**Cookie File Corruption Handling:**
- Issue: Phase 999.7 identified that yt-dlp can corrupt cookies.txt with its own marker headers when save_cookies() is called. Mitigation: use temp-copy pattern (`cookie_utils.temp_cookies_copy`) so yt-dlp writes to temp file and original is never touched. Auto-clear logic detects corrupted canonical file and emits toast.
- Files: `musicstreamer/cookie_utils.py` (temp-copy context manager), `musicstreamer/player.py:440–448` (yt-dlp resolve with cookie protection), `musicstreamer/yt_import.py` (scan_playlist with cookie protection), `musicstreamer/repo.py` (none — cookies not stored in DB)
- Impact: If canonical cookies.txt is corrupted despite temp-copy protection (e.g., race condition, out-of-disk, permission issue), YouTube playback fails and user must manually delete `~/.local/share/musicstreamer/cookies.txt`. No automatic recovery.
- Fix approach: Current mitigation is solid (temp-copy + corruption detection). Consider adding a "Reset Cookies" button in Accounts menu (UX improvement, not bug fix) so user can clear without manual file deletion. Phase 53 consolidates YouTube cookies into Accounts menu—good time to add reset button.

**D-Bus AUMID Binding on Windows (Phase 43.1 Pitfall #7):**
- Issue: `SetCurrentProcessExplicitAppUserModelID` must run BEFORE `QApplication()` and must use explicit `LPCWSTR` argtypes (ctypes default marshaling can fail). Without this, SMTC session is created but hidden from Win+V overlay. Discovered via UAT only.
- Files: `musicstreamer/__main__.py` (startup sequence), `musicstreamer/media_keys/smtc.py:129–133` (is_enabled flag documentation)
- Impact: If AUMID binding is skipped or fails silently, Windows media keys don't appear in Win+V overlay, so user thinks feature is broken. SMTC internally configured but invisible.
- Fix approach: Phase 56 should verify AUMID is set before QApplication() in __main__.py startup. Consider adding a diagnostic log at DEBUG level. Phase 43.1 UAT confirmed this works; keep it as-is but document in future Windows maintenance guides.

## Known Bugs

**YouTube Linux Playback Regression (BUG-07 — Phase 49):**
- Symptoms: YouTube live streams don't play audio on Linux (no error, stream just hangs)
- Files: `musicstreamer/player.py:420–480` (_youtube_resolve_worker)
- Trigger: Phase 49 reported user experienced this, but playback resumed after user reinstalled both yt-dlp and GStreamer plugins at OS level
- Status: RESOLVED 2026-04-27 (no code change; env-level fix). Root cause NOT formally identified — suspected one of {yt-dlp version, GStreamer plugin version}, both reinstalled together so bisect unknown. If regression returns, open Phase 49.1 to bisect (revert yt-dlp first, then GStreamer plugins, measure at each step).

**Recently Played List Not Updating Live (BUG-01 — Phase 50):**
- Symptoms: After playing a station, the "Recently Played" section at the top of the station list does not update until app restart
- Files: `musicstreamer/ui_qt/station_list_panel.py`, `musicstreamer/ui_qt/main_window.py` (_on_station_activated)
- Trigger: User selects and plays a station, waits for now-playing to appear, switches to another app or window, returns to MusicStreamer
- Status: FIXED 2026-04-28 (Phase 50-01). `StationListPanel.refresh_recent()` now called from `MainWindow._on_station_activated` after `update_last_played()`. Provider tree expand/collapse state preserved during refresh. UAT confirmed SC #1/#2/#3.

**Cross-Network AudioAddict Siblings (BUG-02 — Phase 51):**
- Symptoms: AudioAddict stations that exist on multiple networks (e.g. "Ambient" on DI.FM and ZenRadio) show no indication of sibling relationship; user must manually search other networks to find duplicates
- Files: `musicstreamer/aa_import.py`, `musicstreamer/ui_qt/edit_station_dialog.py` (would display sibling links here)
- Trigger: User imports "Ambient" from DI.FM, later discovers same channel on ZenRadio; no link between them
- Status: Not started (Phase 51 in backlog). No code change yet. Requires: detect sibling relationship via AudioAddict channel key at import time or on-demand lookup, surface in editor UI, allow user to navigate between siblings.

**EQ Toggle Audio Dropout (BUG-03 — Phase 52):**
- Symptoms: Clicking the EQ toggle button causes brief (< 1 second) audible gap or pop in playback
- Files: `musicstreamer/player.py:211–227` (set_eq_enabled, _apply_eq_state), `musicstreamer/ui_qt/equalizer_dialog.py` (toggle button wired to set_eq_enabled)
- Trigger: User toggles EQ on while stream is playing
- Status: Not started (Phase 52 in backlog). Root cause likely: GStreamer element state change (bypass → apply) causes stream pipeline to pause/resume. Solution may involve gap-free element state management or buffer padding.

**Station Logo Aspect Ratio Cropping (BUG-05 — Phase 54):**
- Symptoms: Rectangular logos (landscape or portrait) are cropped to fit square viewport; only square logos display fully
- Files: `musicstreamer/ui_qt/now_playing_panel.py` (logo image slot), `musicstreamer/ui_qt/_theme.py` (STATION_LOGO_SIZE)
- Trigger: User plays a station with rectangular logo (e.g. some YouTube channel banners, AA network logos)
- Status: Not started (Phase 54 in backlog). Current impl may use fixed aspect ratio or CENTER crop mode instead of letterbox/pillarbox. Fix: use `Qt.ContentFitPolicy.CONTAIN` or explicit aspect-ratio mode to preserve full logo within viewport bounds.

**Edit Station Dialog Section State Not Preserved (BUG-06 — Phase 55):**
- Symptoms: After expanding a section (e.g. "Tags") in the Edit Station dialog and clicking Save, all sections collapse to their initial state (closed)
- Files: `musicstreamer/ui_qt/edit_station_dialog.py` (section layout, save handler)
- Trigger: User edits a station, expands a collapsed section, changes a value, clicks Save. After save completes, that section is collapsed again.
- Status: Not started (Phase 55 in backlog). Likely cause: dialog is destroyed and reconstructed on save, or sections are reset during model update. Fix: capture section expansion state before save, restore after dialog refresh.

**Windows DI.fm HTTPS Rejection (WIN-01 — Phase 56):**
- Symptoms: DI.fm premium stream URLs work on Linux/yt-dlp but fail on Windows with GStreamer (TLS handshake succeeds, stream returns error -5)
- Files: `musicstreamer/player.py` (_set_uri, GStreamer playbin3), Phase 43 findings documented in STATE.md line 85
- Trigger: User tries to play a DI.fm premium stream on Windows (not Linux)
- Status: Not started (Phase 56 in backlog). Root cause confirmed in Phase 43 spike: DI.fm rejects HTTPS server-side, but behavior differs between yt-dlp (handles gracefully) and GStreamer (propagates error). Phase 56 must decide on policy: HTTP fallback for DI.fm only, or clear user error message explaining server-side rejection.

**Windows Audio Pause/Resume Glitch (WIN-03 — Phase 57):**
- Symptoms: Pausing and resuming playback on Windows produces audible pop, gap, or restart artifact; not present on Linux
- Files: `musicstreamer/player.py:272–289` (pause, stop methods), GStreamer pipeline state changes, audio-sink configuration
- Trigger: User clicks pause button while playing, then clicks play to resume
- Status: Not started (Phase 57 in backlog). Likely cause: Windows audio sink (pulsesink or wasapisink) drops audio context on NULL state change; Linux may handle state transitions more gracefully. Fix: investigate gap-free pause implementation or audio-context preservation during pause.

**Windows Volume Slider Not Working (WIN-04 — Phase 57):**
- Symptoms: Moving the volume slider on Windows has no effect on playback volume; works on Linux
- Files: `musicstreamer/ui_qt/now_playing_panel.py` (volume slider), `musicstreamer/player.py:203–205` (set_volume method, pipeline volume property)
- Trigger: User adjusts volume slider on Windows
- Status: Not started (Phase 57 in backlog). Likely cause: Windows audio sink does not respond to playbin3's volume property, or audio-sink is misconfigured. Fix: verify audio-sink is pulsesink (or wasapisink on newer Windows) and supports volume control; may need explicit volume-control logic per OS.

## Security Considerations

**URL Input Handling (AudioAddict/YouTube URL Classification):**
- Risk: User pastes arbitrary URLs into station editor; url_helpers._is_aa_url and _is_youtube_url use simple domain substring matching
- Files: `musicstreamer/url_helpers.py:15–35` (_is_youtube_url, _is_aa_url)
- Current mitigation: URLs classified for auto-fetch purposes only (thumbnail, channel key); no shell invocation or dynamic SQL building based on URL. Classification errors result in missing art, not crashes.
- Recommendations: Keep current simple matching (no regex complexity attack surface). Consider adding URL validation regex (e.g., `urllib.parse.urlparse` + scheme/netloc validation) if URL classification logic becomes more complex.

**OAuth Token Storage (Twitch auth-token):**
- Risk: Twitch token written to `~/.local/share/musicstreamer/twitch_token.txt` with 0o600 perms. If user's home directory is compromised, token is accessible.
- Files: `musicstreamer/oauth_helper.py:1–127`, `musicstreamer/ui_qt/accounts_dialog.py:197–223`, `musicstreamer/constants.py` (TWITCH_TOKEN_PATH)
- Current mitigation: Token stored locally only (not synced to cloud), 0o600 file perms, no backup of token, token only used for `--twitch-api-header Authorization=OAuth <token>` header construction.
- Recommendations: This is acceptable for single-user desktop app. If multi-user support is added, consider OS keyring storage (secretstorage.py on Linux, keychain on macOS, DPAPI on Windows). Current approach is pragmatic for personal use.

**SQL Injection (SQLite):**
- Risk: `musicstreamer/repo.py` uses parameterized queries throughout
- Files: `musicstreamer/repo.py` (all execute calls use `?` placeholders)
- Current mitigation: All user input (station name, URL, tags, etc.) passed via `?` placeholder parameters. No SQL string concatenation observed.
- Recommendations: Audit remains clean. Maintain this pattern for any future DB changes.

**Cookie File Path Injection:**
- Risk: yt-dlp receives `cookiefile` path from `cookie_utils.temp_cookies_copy()` context manager. If path is not properly sanitized, could be exploited.
- Files: `musicstreamer/cookie_utils.py` (temp-copy via tempfile.mkstemp), `musicstreamer/player.py:440–448` (yt_dlp.YoutubeDL(..., cookiefile=...))
- Current mitigation: `tempfile.mkstemp()` generates secure temp file with random suffix. No user input in path. yt-dlp never receives user-provided path.
- Recommendations: Current implementation is safe. Keep using mkstemp for any temp files.

**Subprocess Security (oauth_helper.py):**
- Risk: oauth_helper.py subprocess runs QWebEngineView and captures cookies from Twitch login. Subprocess isolation prevents compromise of main process, but subprocess itself could be exploited.
- Files: `musicstreamer/oauth_helper.py`, `musicstreamer/ui_qt/accounts_dialog.py:197–223` (QProcess launch)
- Current mitigation: Subprocess runs as user (same privilege as main app), no privileges elevation, subprocess never runs with sudo. Twitch login runs over HTTPS. Token written to 0o600 file.
- Recommendations: Add validation that oauth_helper.py only runs on .twitch.tv domain (line 93: `_TWITCH_LOGIN_URL`). Currently hardcoded, but consider adding domain whitelist if subprocess is extended to other services.

## Performance Bottlenecks

**GStreamer Bus Event Dispatching (Windows):**
- Problem: Phase 43.1 identified that `bus.add_signal_watch()` must run on GLib thread, not Qt thread. On Windows, inline-on-Qt-main attaches to a MainContext that no one iterates → bus handlers never fire → 10s failover timeout fires before error is detected.
- Files: `musicstreamer/gst_bus_bridge.py`, `musicstreamer/player.py:115–126` (bus wiring)
- Current behavior: Mitigated in Phase 43.1 by routing `bus.add_signal_watch()` through `GstBusLoopThread.run_sync()` to execute on GLib thread. On Linux, this was transparent (GLib loop always running); on Windows, mandatory.
- Impact: Without this fix, any GStreamer error on Windows has a 10s latency before failover attempts next stream. Currently fixed, but fragile to maintainers who might move bus setup inline.
- Improvement: Document this constraint in player.py module docstring (already present, lines 3–24). Add assertion in bus setup to verify we're on the bridge thread, fail fast if someone refactors this wrong.

**Cover Art Fetching (Session-Level Dedup):**
- Problem: iTunes Search API called for every ICY TAG event (potential 1000s per day on fast-changing station). Session-level dedup via `_last_cover_icy` module var prevents redundant calls for same ICY title.
- Files: `musicstreamer/cover_art.py` (module-level `_last_cover_icy` cache), `musicstreamer/player.py` (_on_gst_tag handler)
- Current behavior: Per-title dedup prevents re-fetch for repeated TAG events. Cache is per-process, cleared on app exit (acceptable for single instance).
- Impact: Without dedup, high-turnover stations (50+ titles/day) would hammer iTunes API and risk rate-limit. Current mitigation is minimal but effective.
- Improvement: Consider upgrading to time-window dedup (e.g., don't re-fetch same title within 1 hour) to reduce API spam if user plays same station multiple times. Current design is sufficient for daily use.

**Station List Rendering (300+ Stations):**
- Problem: StationListPanel uses QTreeView + StationFilterProxyModel. With 300+ stations grouped by 20+ providers, full tree rebuild is O(n) where n = station count + provider count. Currently refreshed on every filter change.
- Files: `musicstreamer/ui_qt/station_list_panel.py`, `musicstreamer/ui_qt/station_tree_model.py`, `musicstreamer/ui_qt/station_filter_proxy.py`
- Current behavior: Filter changes call model.refresh() which rebuilds the entire tree. Recently Played section uses `ListBox.insert(row, 0)` which preserves expand state.
- Impact: With 300 stations, filter changes might have 100–200ms delay (acceptable, but noticeable on slower hardware). Expand/collapse state preserved after filter, but full rebuild on every keystroke.
- Improvement: Consider virtualizing the tree (only render visible rows) or incremental filtering. Low priority for v2.1 (user library typically 50–150 stations). Phase 60 scope should assess if this becomes an issue with large imports.

**Audio Buffer Tuning (10s / 10MB):**
- Problem: Phase 16 tuned GStreamer buffer to 10s duration + 10MB size to eliminate ShoutCast drop-outs. This is a large buffer (memory overhead, ~1s latency on pause/resume). Phase 62 may identify that underruns occur despite buffer, suggesting network or CPU bottleneck upstream of the buffer.
- Files: `musicstreamer/player.py:103–104` (BUFFER_DURATION_S, BUFFER_SIZE_BYTES from constants), `musicstreamer/constants.py`
- Current behavior: All streams buffer to 10s before playback starts (transparent to user, added latency ~1s on initial play). Buffer prevents drop-outs on intermittent network hiccups.
- Impact: Large buffer uses ~10 MB RAM per stream. If Phase 62 identifies underruns despite full buffer, root cause is likely not buffering (e.g., network stall on resume, decoder stall on format change). Current tuning is Phase 16 baseline; should not be reduced without explicit Phase 62 data.
- Improvement: Phase 62 instrumentation must log buffer % when underrun occurs to distinguish between "buffer was full and still underran" (decoder/CPU issue) vs "buffer was draining" (network issue).

## Fragile Areas

**GStreamer Bus Message Dispatching (Cross-OS Risk):**
- Files: `musicstreamer/gst_bus_bridge.py`, `musicstreamer/player.py:115–126`, `musicstreamer/media_keys/mpris2.py`
- Why fragile: GLib MainLoop + Qt MainLoop coexistence requires careful thread affinity and GSource attachment. Windows doesn't run GLib loop by default, so bus handlers silently drop if wired on wrong thread. Linux users hit this only in edge cases. Very hard to test without hitting it live.
- Safe modification: Never move `bus.add_signal_watch()` out of `GstBusLoopThread.run_sync()` context. Always document thread affinity in comments. Test both Linux and Windows before shipping changes to player.py bus setup.
- Test coverage: Gaps: no unit test that validates bus handlers fire (would require live GStreamer pipeline or mock GLib loop). Phase 43.1 UAT on Windows VM is the only validation gate.

**Equalizer Element State Management (Phase 47.2):**
- Files: `musicstreamer/player.py:106–114` (EQ construction), `musicstreamer/player.py:211–227` (set_eq_enabled, _apply_eq_state), `musicstreamer/player.py:391–410` (private _apply_eq_state, _rebuild_eq_element)
- Why fragile: Rebuilding the equalizer element (changing num-bands) requires pipeline state changes and potential drain events. If state machine is wrong (e.g., applying changes during PLAYING state without proper flush), audio dropout occurs (BUG-03). Graceful degrade if gst-plugins-good is missing (self._eq = None and all methods become no-ops).
- Safe modification: Never change equalizer state without calling `_apply_eq_state()` from main thread. All band mutations via GstChildProxy (lines 391–410). Before shipping EQ changes, test on both Linux (ALSA) and Windows (WASAPI sink) to ensure no audio glitch.
- Test coverage: Gaps: no integration test for EQ toggle during playback. Only manual UAT. Phase 52 should add regression test for gap-free EQ toggle.

**MPRIS2 Service Registration (Linux Only):**
- Files: `musicstreamer/media_keys/mpris2.py` (dbus-python service), `musicstreamer/media_keys/__init__.py` (factory)
- Why fragile: dbus-python requires `DBusGMainLoop(set_as_default=True)` called BEFORE the service class is defined (not just instantiated). If ordering is wrong, D-Bus signal handlers never fire. No error raised; symptoms are "media keys don't work".
- Safe modification: Never refactor mpris2.py imports or module initialization order. Keep DBusGMainLoop setup at module level (line 1). If adding new D-Bus services, apply same pattern in a separate module.
- Test coverage: Gaps: no unit test for MPRIS2 signal dispatch (would require mocking dbus-python or running full D-Bus daemon). Phase 41 UAT on Linux desktop is the only validation gate. Media keys test coverage via test_mpris.py is minimal (legacy D-Bus integration test from v1.5, never migrated to Qt rewrite — likely stale).

**YouTube yt-dlp Library API (Library vs CLI Trade-off):**
- Files: `musicstreamer/player.py:420–480` (_youtube_resolve_worker), `musicstreamer/yt_import.py:20–70` (scan_playlist)
- Why fragile: yt-dlp library API is not a stable public API. Upstream changes (extractor_args keys, player_client options, JavaScript solver integration) break without deprecation warnings. Phase 999.9 pinned `player_client=web` after upstream removed the old extractor_args key. If upstream changes the JS solver again or removes player_client, library path breaks.
- Safe modification: Before updating yt-dlp dependency, test YouTube live stream playback end-to-end on Linux + Windows. Keep fallback subprocess path documented (Phase 35 spike noted fallback in comment) so it can be revived if library API breaks. Consider pinning yt-dlp to a major version family (2026.x) to catch breaking changes at dependency-update time.
- Test coverage: Gaps: no unit test for YouTube URL resolution. test_yt_thumbnail has a fixture YouTube URL but never calls extract_info. test_player_tag doesn't test YouTube path. Phase 50 has no YouTube regression test. Manual UAT is the only gate. If Phase 49 regression repeats, add CI test that plays a live YouTube stream to catch breakage early.

**Windows Audio Sink Selection (Platform-Specific):**
- Files: `musicstreamer/player.py:100–102` (audio-sink creation, pulsesink fallback if missing)
- Why fragile: Code assumes `Gst.ElementFactory.make("pulsesink", ...)` succeeds on both Linux and Windows. Windows conda-forge GStreamer bundle includes pulsesink, but pulsesink may not control Windows WASAPI audio (it connects to PulseAudio, which doesn't exist on Windows). Real Windows audio output may come from a second-choice sink (fallback to autoaudiosink or manual WASAPI sink).
- Safe modification: Phase 43 spike and Phase 44 bundle validation confirmed pulsesink + autoaudiosink works on Windows (even if pulsesink is a no-op, autoaudiosink picks native backend). Don't remove pulsesink attempt. If Windows audio fails on a new version, verify GStreamer bundle includes `gst-plugins-good` (provides pulsesink) and `gst-libav` (provides decoders).
- Test coverage: Gaps: no Windows unit test for audio sink creation (would require Windows VM + GStreamer plugins installed). Phase 44 UAT and Phase 57 bug reports are the only gates.

## Scaling Limits

**SQLite Database (300+ Stations × 5+ Streams + Favorites + Logs):**
- Current capacity: ~500 stations × ~2000 station_streams + ~10,000 favorite tracks tested (Phase 42 UAT)
- Limit: SQLite single-file ACID database runs on local machine. No built-in replication or sharding. At >10,000 favorite tracks or >1000 stations, query performance may degrade (depends on index coverage). WAL mode is active (Phase 35 migration).
- Scaling path: For v2.1, no scaling work needed (typical user has 50–200 stations). If future milestone adds cloud-sync or multi-device sync, evaluate migration to PostgreSQL or SQLite + delta-sync API. Current schema has no blocking barriers to migration.

**GStreamer Pipeline (Parallel Streams / Resource Limits):**
- Current capacity: Single playbin3 instance, one stream active at a time. Switching between streams requires pipeline state change (NULL → PLAYING). No resource pooling.
- Limit: Failover queue holds up to ~5–10 streams for a station before exhaustion. Each stream resolution (YouTube/Twitch) involves subprocess call or HTTP request (blocking until timeout). If user has 300 stations, failover recovery could take 30+ seconds in worst case.
- Scaling path: For v2.1, no scaling needed. If Phase 58+ adds features like multi-stream playback or background station preview, may need to pool multiple pipelines. Current design assumes one active play at a time.

**Worker Thread Pool (AA Import, Cover Art):**
- Current capacity: ThreadPoolExecutor with default workers (Python stdlib, ~10–20 threads on modern CPU). Phase 17 (AA import) uses ThreadPoolExecutor for logo fetching. Phase 42 (settings import) uses thread-local SQLite for bulk insert.
- Limit: If importing 1000+ AA channels with logo fetch, thread pool maxes at ~20 concurrent downloads. Disk/network I/O is the bottleneck, not CPU. No visible progress feedback if user cancels mid-import (threads keep working in background).
- Scaling path: For v2.1, import speeds are acceptable (Phase 15 import of 300+ channels takes ~30s with progress bar). If future milestone adds automatic refresh or background sync, consider adding import cancellation (CancelToken pattern) and thread pool tuning.

## Dependencies at Risk

**yt-dlp (Core Dependency for YouTube Playback):**
- Risk: yt-dlp upstream is actively maintained but frequently changes extractors + internal APIs. Phase 999.9 broke due to extractor_args key removal. Bundled in Windows PyInstaller exe, so updates require app re-release.
- Impact: YouTube streams stop working if yt-dlp has a breaking change and app is not updated quickly.
- Migration plan: Keep CLI fallback documented (Phase 35 spike notes it). If library API becomes too brittle, switch back to `yt-dlp --get-url` subprocess + JSON parse to get HLS URL (slightly slower, more stable).

**GStreamer (Core Dependency for Audio Playback):**
- Risk: GStreamer 1.28+ has breaking plugin changes (gst-libav required, video-pad strict-decode requires flags & ~0x1). Conda-forge GStreamer is ~3 months behind latest upstream.
- Impact: New GStreamer version could introduce new codec requirements, TLS backend issues (Phase 43 found OpenSSL TLS instead of GnuTLS), or plugin layout changes.
- Migration plan: Phase 43 spike pinned to GStreamer 1.28.2 conda-forge. Before updating GStreamer, run Phase 43-style smoke test on Windows VM to validate codec coverage + TLS. Linux typically has system GStreamer, so Windows bundle is the main risk point.

**PySide6 (UI Framework):**
- Risk: PySide6 is binary-compatible across minor versions, but major version changes are infrequent. Currently no known issues; Phase 35–44 tested against PySide6 6.x.
- Impact: If PySide6 major version changes (e.g., 7.x with breaking API), significant refactoring required. Unlikely in v2.1 timeframe.
- Migration plan: Keep PySide6 pinned to 6.x in pyproject.toml. Monitor upstream for 7.x roadmap, evaluate compatibility at that time.

**dbus-python (Linux Media Keys):**
- Risk: dbus-python is mature but rarely updated. Requires GObject introspection + libdbus dev libraries at build time. Not used on Windows.
- Impact: If GObject introspection changes, dbus-python build might fail on future Linux. Media keys would fall back to NoOpMediaKeysBackend gracefully.
- Migration plan: Alternative: switch to python-dbus-next (newer async API), but Phase 41 chose dbus-python for existing test coverage. No urgent need to migrate.

## Test Coverage Gaps

**MPRIS2 Signal Dispatch (Linux Media Keys):**
- What's not tested: D-Bus signal handlers (play, pause, stop button presses) are not unit-tested. test_mpris.py exists but is legacy GTK test (never migrated to Phase 41 Qt rewrite).
- Files: `musicstreamer/media_keys/mpris2.py`, `tests/test_mpris.py` (stale/untested)
- Risk: If MPRIS2 signal wiring is broken, user won't know until they test on Linux desktop with actual media keys. No CI coverage.
- Priority: Medium. Phase 41 should have created new Qt-based MPRIS2 integration test (currently missing). Easy to verify: write test that mocks D-Bus and validates signal routing.

**SMTC Signal Dispatch (Windows Media Keys):**
- What's not tested: Windows SMTC button callbacks are not unit-tested. Phase 43.1 UAT on Windows VM is the only gate.
- Files: `musicstreamer/media_keys/smtc.py` (thread-pool callback dispatch), tests missing
- Risk: If winrt signal wiring is broken, user won't know until they test on Windows with actual media keys. No CI coverage (would require Windows VM in CI).
- Priority: Medium. Phase 56 should add SMTC regression test (can mock winrt.windows.media.playback). Complexity: mocking async winrt callbacks requires careful setup.

**YouTube Playback End-to-End:**
- What's not tested: YouTube URL resolution (yt-dlp extract_info) and HLS playback are not unit-tested. test_yt_thumbnail fixtures a YouTube URL but never calls extract_info.
- Files: `musicstreamer/player.py:420–480` (_youtube_resolve_worker), `musicstreamer/yt_import.py:20–70` (scan_playlist)
- Risk: YouTube playback breaks (Phase 49 regression) without test catching it. Requires internet access to test live.
- Priority: High. Phase 50 or later should add mocked YouTube resolution test (mock yt_dlp.YoutubeDL or record HTTP responses for playback). Current gap: no CI test for YouTube extraction.

**GStreamer Buffer Underrun Handling:**
- What's not tested: BUS-handler buffering events (message::buffering < 100%) are not simulated. player.py emits buffer_percent signal (47.1) but no test validates recovery behavior.
- Files: `musicstreamer/player.py:480–510` (_on_gst_buffering handler), `musicstreamer/player.py:75` (buffer_percent signal)
- Risk: If buffer underrun recovery logic breaks (e.g., failover triggered incorrectly), no test catches it. Phase 62 is planned to add instrumentation; should include regression tests.
- Priority: Medium (part of Phase 62 scope). Test setup would require GStreamer pipeline simulation or mock GLib MainLoop.

**AudioAddict API Integration:**
- What's not tested: AA API calls (fetch_channels, fetch_image_map, channel key extraction) are not unit-tested. test_aa_import has mocks but doesn't validate API response parsing edge cases.
- Files: `musicstreamer/aa_import.py` (API client + PLS resolution), tests/test_aa_import.py (exists but may have gaps)
- Risk: AA API changes (new field names, removed fields) could break import flow. No CI validation against real AA API (would require valid API key in CI).
- Priority: Low. Current approach: monthly manual verification that AA import still works (user tests as part of maintenance). Could add fixture-based test with recorded API responses for CI.

**PyInstaller Bundle Validation (Windows):**
- What's not tested: Windows exe bundle is not validated in CI. Phase 44 UAT was manual on Windows VM (collect required GStreamer plugins, test HLS playback, verify start menu shortcut, run uninstaller).
- Files: PyInstaller .spec file (not checked into repo), Inno Setup installer script
- Risk: If PyInstaller hooks are misconfigured, Windows release has missing plugins/data files. Only caught at user installation time.
- Priority: High (for each Windows release). Recommendation: automate Windows bundle smoke test in CI (would require GitHub Actions Windows runner + GStreamer plugins installed). Currently no CI coverage — Phase 44 UAT is manual only.

## Missing Critical Features

**PLS Auto-Resolve in Station Editor (STR-15 — Phase 58):**
- Problem: User can paste a PLS URL into the Streams section, but it doesn't auto-expand into individual stream entries. Must manually add each stream.
- Blocks: Users with multi-stream playlists must import via AudioAddict PLS API or manually enter each URL.
- Impact: Low (workaround: paste URL into AA tab if available). Phase 58 planned but not started.

**Accent Color Visual Picker (ACCENT-02 — Phase 59):**
- Problem: Current accent color dialog offers 8 presets + hex input, but no HSV/wheel visual picker. Users must know hex codes or guess.
- Blocks: Users can't visually preview accent color before applying.
- Impact: Low (workaround: 8 presets sufficient for most users). Phase 59 planned but not started.

**GBS-FM Integration (GBS-01 — Phase 60):**
- Problem: No in-app access to GBS.FM streams (internet radio directory). Users must open browser and import manually.
- Blocks: Users can't discover/save GBS-FM streams from inside MusicStreamer.
- Impact: Low (nice-to-have discovery feature). Phase 60 planned but not started. Scope TBD at /gsd-discuss-phase time.

## Summary of v2.1 Priority Roadmap

**Active Phases (started):**
- Phase 50: Recently Played Live Update (COMPLETE 2026-04-28)

**Next High-Priority Phases (backlog bugs from v2.0):**
- Phase 51: AudioAddict Cross-Network Siblings (BUG-02)
- Phase 52: EQ Toggle Dropout Fix (BUG-03)
- Phase 53: YouTube Cookies into Accounts Menu (BUG-04)
- Phase 54: Station Logo Aspect Ratio Fix (BUG-05)
- Phase 55: Edit Station Preserves Section State (BUG-06)
- Phase 56: Windows DI.fm + SMTC Start Menu (WIN-01/WIN-02)
- Phase 57: Windows Audio Glitch + Test Fix (WIN-03/WIN-04)

**Medium-Priority Phases (features + instrumentation):**
- Phase 58: PLS Auto-Resolve in Station Editor (STR-15)
- Phase 59: Visual Accent Color Picker (ACCENT-02)
- Phase 60: GBS.FM Integration (GBS-01)
- Phase 61: Linux App Display Name in WM Dialogs (BUG-08)
- Phase 62: Audio Buffer Underrun Resilience (BUG-09, instrumentation phase)
- Phase 63: Auto-Bump pyproject Version on Phase Completion (VER-01)

---

*Concerns audit: 2026-04-28*
