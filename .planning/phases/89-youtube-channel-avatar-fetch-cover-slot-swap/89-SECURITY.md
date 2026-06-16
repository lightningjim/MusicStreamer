---
phase: 89
slug: youtube-channel-avatar-fetch-cover-slot-swap
status: verified
threats_open: 0
asvs_level: 2
created: 2026-06-16
---

# Phase 89 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Verified against current working tree (includes post-UAT commits 62acec21, cec28ed4, 8fcb0e02).

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| network(YouTube CDN) -> process | urllib.request.urlopen fetches avatar PNG bytes from CDN URL supplied by yt-dlp | Untrusted image bytes; validated at render boundary via QPixmap.isNull() and square-dimension reject |
| yt-dlp -> cookies file | yt-dlp's save_cookies() side-effect on __exit__ would overwrite canonical cookies.txt | cookies.txt (auth tokens); shielded via cookie_utils.temp_cookies_copy() |
| in-process -> filesystem | write_channel_avatar() writes PNG bytes to channel-avatars directory | PNG bytes; atomic write via tempfile.mkstemp + os.replace; temp cleaned on failure |
| cached PNG -> Qt render | QPixmap(abs_path) loads stored avatar PNG for display | Stored file bytes; isNull() gate rejects corrupt/missing files; no execution of bytes |
| worker thread -> Qt main thread | _AvatarFetchWorker.run() signals result back to main thread | rel_path string and int token; marshalled exclusively via queued Signal; no widget access off-thread |
| cover-resolver dispatch precedence | fetch_cover_art() dispatch order: iTunes -> MB-CAA -> (future) channel-avatar | Cover art path; precedence locked by source-grep drift-guard test |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status | Evidence |
|-----------|----------|-----------|-------------|------------|--------|----------|
| T-89-01 | DoS | assets.write_channel_avatar PNG write | mitigate | Atomic write: tempfile.mkstemp(dir=dst_dir)+os.replace; temp unlinked in except block on failure | closed | musicstreamer/assets.py:45-59 |
| T-89-02 | Tampering | path from station_id | mitigate | station_id typed int (models.py:28); f"{station_id}.png" under paths.channel_avatars_dir(); no user-controlled string in path | closed | musicstreamer/assets.py:44; musicstreamer/models.py:28 |
| T-89-03 | Tampering | update_station silent column reset | mitigate | update_station SQL SET clause names only 7 columns (name/provider_id/tags/station_art_path/album_fallback_path/icy_disabled/cover_art_source) — channel_avatar_path absent; update_channel_avatar_path is the sole writer | closed | musicstreamer/repo.py:654-665; repo.py:856-860 |
| T-89-04 | Tampering | malformed/oversized avatar bytes from CDN | mitigate(partial) | Square-dimension reject: w!=h raises ValueError (yt_import.py:254-255); QPixmap.isNull() validation at render (now_playing_panel.py:2211, edit_station_dialog.py:1530); bytes never exec'd | closed | musicstreamer/yt_import.py:254-255; musicstreamer/ui_qt/now_playing_panel.py:2211-2214; musicstreamer/ui_qt/edit_station_dialog.py:1530-1532 |
| T-89-05 | Info Disclosure | yt-dlp writing canonical cookies.txt | mitigate | cookie_utils.temp_cookies_copy() wraps both scan_playlist and fetch_channel_avatar; YoutubeDL context opened inside the temp_cookies_copy context manager | closed | musicstreamer/yt_import.py:216-221; musicstreamer/cookie_utils.py:52-83 |
| T-89-06 | DoS | network hang on avatar download | mitigate | urllib.urlopen(timeout=10) at download; socket_timeout=10 in yt-dlp opts (post-UAT cec28ed4); playlist_items="0" bounds extraction to channel level only (post-UAT 62acec21); runs on worker thread with bounded wait at teardown | closed | musicstreamer/yt_import.py:200,205,258 |
| T-89-07 | Tampering | precedence reorder regressing MB-CAA | mitigate | Source-grep drift-guard test_mb_caa_runs_before_channel_avatar asserts def _mb_caa_lookup appears before def _channel_avatar_lookup in cover_art.py source | closed | tests/test_cover_art_avatar.py:23-38; musicstreamer/cover_art.py:148,159 |
| T-89-08 | DoS | _channel_avatar_lookup raising into Qt callback | mitigate | Entire body wrapped in try/except Exception: callback(None); synchronous, no thread, no QPixmap | closed | musicstreamer/cover_art.py:175-187 |
| T-89-09 | Tampering | RichText sibling-render regression | mitigate | test_richtext_baseline_unchanged_by_phase_89 pins count=3 (EXPECTED_RICHTEXT_COUNT); scans full musicstreamer/ subtree | closed | tests/test_constants_drift.py:163-182; tests/test_constants_drift.py:21 |
| T-89-10 | DoS | corrupt PNG crashing cover slot, retried on resize | mitigate | QPixmap.isNull() check clears _last_avatar_path=None BEFORE falling back to _show_station_logo_in_cover_slot(); subsequent _apply_art_tier skips avatar branch because _last_avatar_path is None | closed | musicstreamer/ui_qt/now_playing_panel.py:2211-2214,2122-2123 |
| T-89-11 | DoS | QPixmap off main thread | mitigate | _AvatarFetchWorker.run() imports yt_import and assets only — no QPixmap, QPainter, or QImage; QPixmap constructed in _set_avatar_pixmap_from_path and _refresh_avatar_preview, both documented "Main thread only" with no worker entry points in now_playing_panel | closed | musicstreamer/ui_qt/edit_station_dialog.py:168-179; musicstreamer/ui_qt/now_playing_panel.py:2206 |
| T-89-12 | Info Disclosure | stale station avatar bleed | mitigate | self._last_avatar_path = None at line 936 in bind_station(), before the icy_disabled/channel_avatar_path check at line 937 | closed | musicstreamer/ui_qt/now_playing_panel.py:934-938 |
| T-89-13 | DoS | worker raising/touching widgets off-thread | mitigate | run() has bare except Exception: self.finished.emit("", token) — never re-raises, never touches widgets, no QTimer.singleShot; _shutdown_avatar_fetch_worker escalates to unconditional worker.wait() after 2s (post-UAT cec28ed4) so QThread is never destroyed while running; called from accept(), closeEvent(), AND reject() | closed | musicstreamer/ui_qt/edit_station_dialog.py:168-179,1549-1604 |
| T-89-14 | Tampering | stale avatar from superseded fast-typing fetch | mitigate | Monotonic _avatar_fetch_token incremented on each launch; _on_avatar_fetched first-line guard: if token != self._avatar_fetch_token: return | closed | musicstreamer/ui_qt/edit_station_dialog.py:1305-1306,1450-1451 |
| T-89-15 | DoS | fetch failure blocking edit flow | mitigate(accept residual) | Failure branch sets _avatar_status text only; no DB write; no setEnabled(False) on button_box or save_btn anywhere in avatar failure path; Save always reachable | closed | musicstreamer/ui_qt/edit_station_dialog.py:1454-1459,572-583 |
| T-89-SC | Tampering | supply chain (npm/pip installs) | accept | No new packages introduced — yt-dlp and PySide6 were already project dependencies; pyproject.toml unchanged from pre-phase baseline | closed | pyproject.toml:19,18 |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-89-01 | T-89-SC | No new packages added in this phase. yt-dlp and PySide6 supply-chain risk is a project-wide accepted risk predating Phase 89 and managed at the project level (yt-dlp pinned via pyproject.toml; no version floor added in this phase). | Kyle Creasey | 2026-06-16 |
| AR-89-02 | T-89-04 (partial) | Oversized avatar bytes are not size-capped before write. urllib downloads whatever the CDN serves; no Content-Length guard exists. Risk is accepted because: (1) avatar bytes are written to a dedicated channel-avatars directory, never executed; (2) corrupt/null files are caught at render time by QPixmap.isNull(); (3) disk exhaustion via CDN is considered out-of-scope for a desktop app. | Kyle Creasey | 2026-06-16 |

*Accepted risks do not resurface in future audit runs.*

---

## Post-UAT Hardening Verification

Three bugs found in UAT were fixed and committed after initial execution. All three post-UAT mitigations are confirmed present in current working tree:

| Commit | Threat | Change | Verified |
|--------|--------|--------|---------|
| 62acec21 | T-89-06 | playlist_items="0" added to fetch_channel_avatar opts | yt_import.py:200 |
| cec28ed4 | T-89-06, T-89-13 | socket_timeout=10 in opts; _shutdown_avatar_fetch_worker escalated to full worker.wait() after 2s timeout | yt_import.py:205; edit_station_dialog.py:1569-1570 |
| 8fcb0e02 | T-89-05, T-89-13 | node_runtime threaded through fetch_channel_avatar/_AvatarFetchWorker/EditStationDialog/MainWindow; cookie_utils.temp_cookies_copy() and thread-safety mitigations confirmed unaffected — node_runtime is a read-only constructor arg passed to yt_dlp opts, no interaction with cookie or thread paths | yt_import.py:159,173; edit_station_dialog.py:160,173,329,1313; main_window.py:1235,1258 |

---

## Unregistered Threat Flags

No unregistered flags. All SUMMARY.md `## Threat Flags` sections across Plans 01-05 report "None". No new network endpoints or auth paths beyond what the threat register covers were introduced during implementation.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-16 | 16 | 16 | 0 | Claude Sonnet 4.6 (automated) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-16
