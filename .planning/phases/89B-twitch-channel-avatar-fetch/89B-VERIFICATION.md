---
phase: 89B-twitch-channel-avatar-fetch
verified: 2026-06-16T00:00:00Z
status: human_needed
score: 15/15 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Open EditStationDialog for an ICY-disabled Twitch station with a live twitch-token.txt. Set/confirm the URL to a real streamer (e.g. https://www.twitch.tv/twitchdev). Observe the debounced auto-fetch trigger and confirm the Refresh-avatar button is enabled."
    expected: "The avatar fetch fires automatically; the cover-slot preview in the dialog updates to the streamer's circular-cropped profile image within ~1-2 seconds."
    why_human: "Requires a live Twitch token, a real network call to api.twitch.tv/helix/users, and visual inspection of the Qt widget — none of these are automatable without live credentials and UI interaction."
  - test: "With the Twitch station bound and ICY disabled, play the station and observe the now-playing cover slot."
    expected: "The cover slot shows the streamer's profile image (circular crop, via the existing Phase 89 cover-slot swap path) instead of the station thumbnail or a placeholder. The left logo slot is unchanged."
    why_human: "End-to-end visual rendering requires the station to be bound, ICY metadata to arrive as disabled, and the avatar file to be on disk — all requiring live session state."
  - test: "With no twitch-token.txt present (or after deleting it), open EditStationDialog for a Twitch station and observe the avatar status text."
    expected: "Save succeeds without blocking. The avatar area shows a non-blocking inline hint (e.g. 'No Twitch login — connect via Accounts to fetch avatar' or equivalent) — not a modal error, not a crash."
    why_human: "Requires deliberately removing the token file and verifying the UX fallback behavior in the running application."
---

# Phase 89B: Twitch Channel-Avatar Fetch — Verification Report

**Phase Goal:** ICY-disabled Twitch stations show the streamer's Helix `profile_image_url` (circular crop) in the now-playing cover slot, sharing the Phase 89 cover-slot integration and the Phase 89a per-provider storage layout. The integration is a per-provider auto-fetch trigger only — zero new UI/render code.
**Verified:** 2026-06-16
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | `twitch_helix.fetch_channel_avatar(url)` calls `GET https://api.twitch.tv/helix/users?login=<login>` with `Authorization: Bearer <token>` and `Client-Id: kimne78kx3ncx6brgo4mv6wki5h1ko` (D-05, D-06) | VERIFIED | `twitch_helix.py:109-115` builds scoped `urllib.request.Request` with both headers; test `test_fetch_calls_helix_with_bearer_and_client_id` asserts headers and URL shape — 8/8 tests pass |
| 2 | Login is parsed from a twitch.tv URL by taking the last path segment then stripping `?`/`#`, clamping to `[a-z0-9_]+`, and case-folding (D-02, WR-01) | VERIFIED | `twitch_helix.py:53-63` `_parse_login()` applies `rstrip("/")`, `split("/")[-1]`, `split("?")[0].split("#")[0]`, `re.match(r"[a-z0-9_]+")`, `.lower()`; `test_parse_login` covers trailing slash, query, fragment, mixed-case, bare-login, and `&`-injection cases |
| 3 | Missing `twitch-token.txt` raises before any HTTP call; HTTP 401 and empty `data:[]` both raise; all failures propagate (D-07) | VERIFIED | `twitch_helix.py:96-121`; three dedicated tests: `test_fetch_raises_on_missing_token` (asserts `urlopen` not called), `test_fetch_raises_on_empty_data`, `test_fetch_raises_on_401` — all pass |
| 4 | No non-square guard is present — Twitch profile images are always square (D-05) | VERIFIED | `twitch_helix.py` contains no `not square` / `width != height` guard; source-grep drift-guard `test_no_square_guard` confirms and asserts `profile_image_url` is present |
| 5 | Token value is never logged; `Authorization` is scoped to the Helix `Request` object only, not the CDN image download (T-89b-01, WR-01) | VERIFIED | `twitch_helix.py:127` CDN download uses plain `urlopen(image_url, ...)` with no headers; `test_token_never_logged` source-grep guards no log/print of token var; `test_fetch_calls_helix_with_bearer_and_client_id` asserts `isinstance(cdn_req, str)` — WR-02 fix confirmed in commit `9612c108` |
| 6 | `register_avatar_fetcher('twitch', twitch_helix.fetch_channel_avatar)` is wired so `get_avatar_fetcher('twitch')` returns the Twitch fetcher at module load (D-05) | VERIFIED | `yt_import.py:290-291` late import + registration; `test_registry_registers_twitch` and `test_avatar_registry_twitch_registered_in_phase_89b` both pass; live registry check `get_avatar_fetcher('twitch') is twitch_helix.fetch_channel_avatar` returns `True` |
| 7 | A twitch.tv URL enables the Refresh-avatar button and triggers the debounced auto-fetch, just like a YouTube URL (D-08) | VERIFIED | `edit_station_dialog.py:1283-1288` `is_twitch = "twitch.tv" in lower`; `setEnabled(is_yt or is_twitch)`; `_on_url_timer_timeout` uses `is_avatar_url` combining YouTube+Twitch; `test_twitch_url_enables_refresh_btn` passes |
| 8 | `_AvatarFetchWorker.run()` dispatches through `yt_import.get_avatar_fetcher()` — twitch.tv URL calls the Twitch fetcher (not YouTube fetcher); `node_runtime` passed only for YouTube (D-08, Pitfall 1) | VERIFIED | `edit_station_dialog.py:169-192`; URL-sniff dispatch: `"twitch.tv" in lower` → `provider_key = "twitch"`, else `"youtube"`; `node_runtime` forwarded only on `provider_key == "youtube"` path; `test_avatar_worker_dispatches_twitch` and `test_youtube_dispatch_passes_node_runtime` pass |
| 9 | Twitch fetch branch carries the same `provider_id is None` guard and reuse-on-open skip as the YouTube branch (Pitfall 7, 89.1 D-07) | VERIFIED | `edit_station_dialog.py:1323-1342`: single `is_avatar_url` gate covers both; `provider_id is None` guard at L1331; `provider_avatar` reuse-on-open skip at L1338-1342; no duplication |
| 10 | On save, when Provider field is blank AND URL is twitch.tv, login is derived and `repo.ensure_provider('Twitch: <login>')` sets `provider_id`; user-typed Provider is NEVER overwritten (D-02, D-03, D-04) | VERIFIED | `edit_station_dialog.py:1699-1705`; `if not provider_name:` guard; `f"Twitch: {_login}"` derivation; `test_save_derives_provider_for_blank_twitch`, `test_save_preserves_manual_provider_for_twitch`, `test_save_non_twitch_url_unchanged` — all pass |
| 11 | All Twitch fetch failures fall back non-blocking to station thumbnail; Save is always allowed; no-token status text points user to Accounts (D-07) | VERIFIED | `_AvatarFetchWorker.run()` `except Exception: self.finished.emit("", token)` WR-04 backstop at L190-192; `RuntimeError("No Twitch login — connect via Accounts to fetch avatar")` raised pre-HTTP; token error wording confirmed in `twitch_helix.py:103-105` |
| 12 | The stored Twitch avatar renders through the unchanged `cover_art` / `now_playing_panel` provider-keyed path — no renderer or cover-slot edits in this phase (D-11) | VERIFIED | `git diff 12d33bd3..HEAD -- musicstreamer/cover_art.py musicstreamer/ui_qt/now_playing_panel.py` produces no output; zero commits to those files in phase; `_channel_avatar_lookup` reads `station.provider_avatar_path` (89.1 D-05) — untouched |
| 13 | Fetched avatar bytes are stored per-provider as `assets/channel-avatars/{provider_id}.png` via `assets.write_provider_avatar(provider_id, data)` and persisted with `repo.update_provider_avatar_path(provider_id, path)` — never per-station `{station_id}.png` (D-01) | VERIFIED | `_AvatarFetchWorker.run():L188` calls `_assets.write_provider_avatar(self._provider_id, data)`; storage path is integer-keyed; roadmap SC#1's `<station-id>.png` wording superseded per CONTEXT D-01 — this is the correct 89.1 model |
| 14 | No staleness TTL or per-bind/per-play refetch added — avatar fetched once when provider has no avatar; updated only via manual Refresh button (D-09) | VERIFIED | `_on_url_timer_timeout:L1337-1342` reuse-on-open skip; no TTL or background poll; `_force_avatar_refresh` only set by `_on_refresh_avatar_clicked`; no per-play trigger added |
| 15 | Refresh re-fetches and overwrites single per-provider `{provider_id}.png`; existing 89.1 shared-effect Refresh hint reused with no Twitch-specific divergence (D-10) | VERIFIED | `_on_refresh_avatar_clicked` (unchanged from 89.1) sets `_force_avatar_refresh = True` then calls `_on_url_timer_timeout()`; single `write_provider_avatar(provider_id, data)` call overwrites; no Twitch-specific divergence |

**Score:** 15/15 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/twitch_helix.py` | `fetch_channel_avatar(url) -> bytes` via Helix /users; login parse helper; min 40 lines | VERIFIED | 129 lines; exports `fetch_channel_avatar` and `_parse_login`; all required literals present: `kimne78kx3ncx6brgo4mv6wki5h1ko`, `Authorization`, `Bearer`, `Client-Id`, `helix/users`, `profile_image_url` |
| `tests/test_twitch_helix.py` | Wave 0 unit tests: request shape, login parse, 401/empty-data/missing-token raises, registry registration; min 60 lines | VERIFIED | 324 lines; 8 named tests all pass; network mocked; WR-02 CDN-auth fix confirmed (`isinstance(cdn_req, str)`) |
| `tests/test_edit_station_dialog_avatar.py` | Wave 0 tests: twitch.tv URL enables Refresh; worker dispatch picks twitch fetcher; min 40 lines | VERIFIED | 249 lines; 3 named tests all pass |
| `tests/test_twitch_provider_assign.py` | Wave 0 tests: ensure_provider('Twitch: <login>') on blank-only; manual provider preserved; min 30 lines | VERIFIED | 240 lines; 4 named tests all pass (source-grep drift-guard + 3 behavioral) |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `musicstreamer/yt_import.py` | `musicstreamer/twitch_helix.fetch_channel_avatar` | `register_avatar_fetcher("twitch", ...)` | WIRED | `yt_import.py:290-291`; late import avoids cycle; `get_avatar_fetcher("twitch") is twitch_helix.fetch_channel_avatar` verified live |
| `musicstreamer/twitch_helix.py` | `musicstreamer/paths.twitch_token_path` | token read | WIRED | `twitch_helix.py:97` `open(paths.twitch_token_path())`; `paths` imported at top of module |
| `musicstreamer/ui_qt/edit_station_dialog.py:_AvatarFetchWorker.run` | `yt_import.get_avatar_fetcher` | registry dispatch by URL sniff | WIRED | `edit_station_dialog.py:181`; `get_avatar_fetcher(provider_key)` called with `"twitch"` or `"youtube"` |
| `musicstreamer/ui_qt/edit_station_dialog.py:_on_save` | `repo.ensure_provider` | `Twitch: <login>` on blank provider | WIRED | `edit_station_dialog.py:1706`; blank-only guard at L1699 confirmed |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `twitch_helix.fetch_channel_avatar` | `data[0]["profile_image_url"]` → CDN bytes | `urlopen(helix_req)` → `json.loads(resp.read())` | Yes — live Helix response (mocked in tests with fixture-locked shape) | FLOWING |
| `_AvatarFetchWorker.run()` | `data` (avatar bytes) | `fetcher(self._url)` → `_assets.write_provider_avatar(self._provider_id, data)` | Yes — dispatched through registry; path emitted via `finished` signal | FLOWING |
| `_on_save` provider derivation | `provider_name` | `twitch_helix._parse_login(url)` → `f"Twitch: {_login}"` → `repo.ensure_provider(provider_name)` | Yes — real DB call via `ensure_provider`; feeds `update_station(provider_id)` | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 8 twitch_helix tests pass | `.venv/bin/python -m pytest tests/test_twitch_helix.py -q` | 8 passed | PASS |
| 7 dialog/provider tests pass | `.venv/bin/python -m pytest tests/test_edit_station_dialog_avatar.py tests/test_twitch_provider_assign.py -q` | 7 passed | PASS |
| Full scoped suite (15 tests) | `.venv/bin/python -m pytest tests/test_twitch_helix.py tests/test_edit_station_dialog_avatar.py tests/test_twitch_provider_assign.py -q` | 15 passed | PASS |
| Full scoped suite + dialog regression | `.venv/bin/python -m pytest tests/test_twitch_helix.py tests/test_edit_station_dialog_avatar.py tests/test_twitch_provider_assign.py tests/test_edit_station_dialog.py -q` | 111 passed (pre-existing @KEXP live-network error note only) | PASS |
| Registry wiring live check | `.venv/bin/python -c "import musicstreamer.yt_import as y, musicstreamer.twitch_helix as t; assert y.get_avatar_fetcher('twitch') is t.fetch_channel_avatar"` | exits 0 | PASS |
| No import cycle | `.venv/bin/python -c "import musicstreamer.yt_import"` | exits 0 | PASS |
| cover_art.py unmodified (D-11) | `git diff 12d33bd3..HEAD -- musicstreamer/cover_art.py` | no output | PASS |
| now_playing_panel.py unmodified (D-11) | `git diff 12d33bd3..HEAD -- musicstreamer/ui_qt/now_playing_panel.py` | no output | PASS |

---

### Probe Execution

Step 7c: SKIPPED — no `scripts/*/tests/probe-*.sh` probes declared for this phase.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| ART-AVATAR-04 | 89B-01-PLAN.md, 89B-02-PLAN.md | For Twitch stations, `twitch_helix.py` fetches `profile_image_url` from `GET https://api.twitch.tv/helix/users?login=<x>` using existing Phase 32 `twitch-token.txt` token (no new OAuth scopes) | SATISFIED | `twitch_helix.py` fully implements the Helix fetch; REQUIREMENTS.md marks `[x]`; traceability table shows Phase 89b Complete |

No orphaned requirements: REQUIREMENTS.md traceability maps only ART-AVATAR-04 to Phase 89b. No additional IDs assigned to this phase.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No TBD/FIXME/XXX markers in any phase-modified file | — | None |
| — | — | No stubs (no `return null/[]/{}`, no placeholder returns) in production files | — | None |

Note: `test_avatar_worker_shutdown_no_crash` in `test_edit_station_dialog.py` produces a `RuntimeWarning: Failed to disconnect (None) from signal` — this is a pre-existing test harness artifact, not introduced by this phase.

---

### WR-01 and WR-02 Fix Confirmation

Both code-review warnings were closed in commit `9612c108`:

- **WR-01 (URL-encode + charset clamp):** `twitch_helix.py:110` uses `urllib.parse.quote(login, safe="")` in the Helix URL; `_parse_login` clamps to `re.match(r"[a-z0-9_]+", s)` before URL-encoding, preventing `&`/`=` injection into the query string or the `"Twitch: <login>"` provider name.
- **WR-02 (dead CDN-auth assertion):** `test_twitch_helix.py:155` now uses `assert isinstance(cdn_req, str)` — an unconditional live drift-guard that will catch any future regression wrapping the CDN download in a `Request` object with auth headers.

---

### Human Verification Required

#### 1. Live Twitch avatar auto-fetch and cover-slot display

**Test:** Open EditStationDialog for an ICY-disabled Twitch station with a valid live `twitch-token.txt`. Set the URL to a real streamer (e.g. `https://www.twitch.tv/twitchdev`). Observe debounced auto-fetch trigger and Refresh-avatar button state.

**Expected:** Refresh button is enabled; avatar fetch fires within ~500ms debounce; the cover-slot preview in the dialog updates to the streamer's circular-cropped profile image.

**Why human:** Requires a live Twitch token, real network call to `api.twitch.tv/helix/users`, and visual Qt widget inspection — not automatable without live credentials.

#### 2. ICY-disabled station now-playing cover slot shows avatar

**Test:** With the Twitch station bound and ICY disabled, play the station and observe the now-playing cover slot (not the logo slot).

**Expected:** Cover slot shows the streamer's profile image (circular crop) instead of a station thumbnail or placeholder. Left logo slot is unaffected.

**Why human:** Requires live session state (bound station, ICY metadata arriving as disabled, avatar file on disk), real GStreamer playback, and visual inspection of the rendered Qt panel.

#### 3. No-token fallback UX (save always allowed)

**Test:** Delete `twitch-token.txt`, open EditStationDialog for a Twitch station, observe the avatar status area, and confirm Save succeeds.

**Expected:** Avatar fetch fails silently (non-blocking inline status hint pointing to Accounts); dialog saves without a modal error or crash; station is saved successfully.

**Why human:** Requires deliberately manipulating the token file and testing actual application UX behavior.

---

### Gaps Summary

No gaps. All 15 automated must-haves are VERIFIED. The three outstanding items are live-visual confirmations that require a Twitch token and running application — they cannot be verified programmatically.

---

_Verified: 2026-06-16_
_Verifier: Claude (gsd-verifier)_
