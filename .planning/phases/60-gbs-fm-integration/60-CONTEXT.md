# Phase 60: GBS.FM Integration — Context

**Gathered:** 2026-05-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 60 is the **API integration foundation** for GBS.FM (https://gbs.fm) inside MusicStreamer:

1. **Multi-quality auto-import** — a single hamburger menu action ("Add GBS.FM") fetches all stream quality variants + station logo + station metadata via GBS.FM's API, and inserts them as **one library row with multiple `station_streams` entries** (mirroring the shape `aa_import.import_stations_multi()` produces).
2. **AccountsDialog auth/credentials groundwork** — a new "GBS.FM" `QGroupBox` lands in `accounts_dialog.py` alongside YouTube and Twitch, with optional login. The cookies/credentials/API-key plumbing ships in Phase 60 even though no Phase 60 user-visible feature actively consumes a token. This is deliberate scaffolding for Phase 60.1 / 60.2.
3. **GBS.FM API client foundation** — a new `musicstreamer/gbs_api.py` (or similar) module with the API client, modeled on the closest existing analog (`aa_import.py` / `radio_browser.py` / `yt_import.py`) once the researcher confirms which fits.
4. **Standard playback path** — saved GBS.FM stations play through the existing GStreamer pipeline; `stream_ordering.order_streams()` picks the best quality at play time. **Already works today for any URL pasted manually** — Phase 60 doesn't add to playback, only to ingestion.

**The literal "browse + save + play" reading of the ROADMAP entry understates this scope.** A user can paste a single GBS.FM stream URL into "New Station" today and it plays. Phase 60 ships the *integration with the GBS.FM API* — multi-quality awareness, automatic logo/metadata population, and the auth surface for follow-on phases.

**In scope:**
- Hamburger menu entry "Add GBS.FM" (slotted into Group 1 alongside `New Station / Discover Stations / Import Stations` at `main_window.py:131-138`).
- New `gbs_api` module (HTTP client, multi-quality stream fetch, station metadata fetch, logo URL fetch).
- New library row insert: one `Station` + N `station_streams` rows populated with `url / quality / position / codec / bitrate_kbps` (mirrors `aa_import.import_stations_multi`).
- Idempotent re-fetch: clicking the menu when GBS.FM already exists in the library refreshes the streams (re-fetches via API, updates rows). Toast on success.
- Logo download to `~/.local/share/musicstreamer/assets/` (existing `assets.copy_asset_for_station` pattern).
- AccountsDialog "GBS.FM" `QGroupBox` (status label + Connect/Disconnect button), mirroring the YouTube/Twitch precedent at `accounts_dialog.py:91-115`.
- Auth flow (one of: API key paste / OAuth subprocess WebView / cookies-import dialog / username-password — picked by planner once researcher reports back, see D-04).
- Token/credential storage at the convention the planner picks (file under `~/.local/share/musicstreamer/` like Twitch token / YouTube cookies, OR setting in SQLite `settings` table like `audioaddict_listen_key` at `accounts_dialog.py:157`).

**Out of scope (deferred to Phase 60.1 / 60.2 / future milestone):**
- **Phase 60.1 (next):** voting/rating the currently-playing track via GBS.FM API. Now-playing UI control + API method + optimistic UX. Builds directly on Phase 60's `gbs_api` module + AccountsDialog auth.
- **Phase 60.2 (next):** search GBS.FM catalog + submit songs to the station's playlist. New dialog + API surface. Builds on Phase 60.
- **Deferred to later milestone or backlog (lower ROI per user):**
  - Per-song comments (SEED-008 nice-to-have).
  - Discord ↔ IRC chat mirror (SEED-008 highest-complexity nice-to-have; "drop chat first if scope shrinks").
  - Song upload (SEED-008 nice-to-have).

**Cross-phase note:** the ROADMAP entry text for Phase 60 ("Browse, save, and play") is narrower than the actual scope captured here. A `/gsd-phase edit 60` pass before `/gsd-plan-phase 60` is recommended to sharpen the goal text + tighten SC #1/#3 so the planner and verifier work from an accurate description. **Phase 60.1 and 60.2 also need ROADMAP entries created via `/gsd-phase add` once Phase 60 lands** — they're not in the ROADMAP today.

</domain>

<decisions>
## Implementation Decisions

### Granularity & data shape

- **D-01:** GBS.FM is **one library row with multiple stream variants** (one `Station` + N `station_streams` entries — `quality / position / codec / bitrate_kbps` populated). Mirrors `aa_import.import_stations_multi` shape at `aa_import.py:207-309`. Rejects the "one row, one stream" reading because GBS.FM exposes multiple quality tiers (user explicitly: "importing all qualities at once would be nice"). Rejects the "network of channels" and "directory" readings because GBS.FM is a single station, not a network or catalog.
- **D-01a:** `stream_ordering.order_streams()` at `stream_ordering.py:43` already consumes the `(codec, bitrate_kbps, position)` shape and partitions unknown bitrates last (Phase 47.1 D-07/D-09). Phase 60 produces output that flows straight in — no changes to `stream_ordering` or the play path.
- **D-01b:** `Repo.insert_stream(station_id, url, label, quality, position, stream_type, codec, bitrate_kbps)` at `repo.py:185` is the multi-stream row helper. Phase 60 calls it once per quality variant after creating the parent `Station`. Pattern at `aa_import.py:245-263`.

### Surface mechanism

- **D-02:** **Hamburger menu entry — "Add GBS.FM"** — slotted into Group 1 of the hamburger menu at `main_window.py:131-138` (alongside `New Station`, `Discover Stations`, `Import Stations`, before the first `addSeparator()` at line 140). Click handler is a new `_on_gbs_add_clicked()` method on `MainWindow` following the `_open_discovery_dialog` / `_open_import_dialog` precedent at `main_window.py:669-680`. Bound-method connection (QA-05).
- **D-02a:** **Idempotent**. Clicking when GBS.FM is already in the library re-fetches the API and refreshes the existing row's `station_streams` entries (URLs may rotate; quality tiers may change). Behavior:
  - Look up the existing GBS.FM station by a stable identifier (URL pattern match, or a dedicated `provider="GBS.FM"` query, or a `gbs_station_id` setting key — planner picks the most robust based on what the API exposes).
  - If found: refresh streams + logo + metadata in-place (UPDATE rather than INSERT, preserve `station.id` so favorites and recently-played stay intact).
  - If not found: insert fresh.
  - Toast on success: "GBS.FM added" (insert) or "GBS.FM streams updated" (refresh).
- **D-02b:** **Menu item is always present** — never hidden, never disabled. The user can always click to refresh. Avoids the "I deleted it; how do I get it back?" trap and avoids state-tracking complexity in the menu.
- **D-02c:** **No first-launch nudge.** The menu item is the only entry point. Discoverable enough; user already knows the app has hamburger-menu actions.
- **D-02d:** **Provider name = "GBS.FM"** — used as the `provider` field on the `Station` row. Consistent capitalization with how the user types it; mirrors existing provider names like "DI.fm", "Soma.FM", "Lofi Girl".

### API client module

- **D-03:** **New module `musicstreamer/gbs_api.py`** (final name at planner discretion; analogs are `aa_import.py`, `radio_browser.py`, `yt_import.py`). Exposes:
  - `fetch_streams(auth_context=None) -> list[dict]` — returns all quality variants. Each dict carries `{url, quality, position, codec, bitrate_kbps}` matching the AA shape at `aa_import.py:191-198`.
  - `fetch_station_metadata(auth_context=None) -> dict` — returns `{name, description, logo_url, ...}` for the GBS.FM station.
  - `import_station(repo, on_progress=None) -> tuple[int, int]` — orchestrator that calls the two `fetch_*` functions, downloads the logo, inserts/updates the `Station` and `station_streams` rows. Mirrors `aa_import.import_stations_multi` shape (single station, idempotent).
  - `auth_context` is the planner's choice of token/cookie/key passing convention — leave shape to planner once researcher confirms auth scheme.
- **D-03a:** Pure `urllib`, no SDK — same convention as `radio_browser.py` and `aa_import.py`. 10s timeouts per call.
- **D-03b:** Image URL handling: download logo via `assets.copy_asset_for_station` (existing pattern, reused by `aa_import.import_stations_multi` at `aa_import.py:281`). Do not skip cover-art / iTunes-Search-API integration — `cover_art.py` keeps working at play time independently.

### Authentication scope

- **D-04:** **Optional account, functional login plumbing in Phase 60, research-gated inner UX.**
  - **Optional:** the GBS.FM stream is publicly playable without auth. Phase 60 ships browse/save/play in the no-auth path. The auth surface exists so users can opt in for richer features in 60.1/60.2.
  - **Functional plumbing now:** AccountsDialog gets a "GBS.FM" `QGroupBox` (status label + Connect/Disconnect button) mirroring the YouTube group at `accounts_dialog.py:91-103` and the Twitch group at `accounts_dialog.py:104-115`. The "Connect" path performs the real auth flow and stores the token/cookie/key. Phase 60 itself doesn't actively read the stored token (no feature in Phase 60 requires authenticated state), but the storage path is real.
  - **Inner UX is research-gated.** The user has not seen GBS.FM's API documentation; they expect both an API path (preferred — assumed equal-access to credentialed access) and a credentials path (fallback if API turns out to be limited). Researcher inspects GBS.FM via a dev cookies fixture (D-04a) and reports back; planner picks the closest existing pattern.
  - **Preference ladder for the auth UX:**
    1. **API key paste** (mirror AA `audioaddict_listen_key` setting at `accounts_dialog.py:157` — paste field, stored in SQLite `settings` table). Cleanest if GBS.FM exposes a stable user-page key.
    2. **OAuth subprocess WebView** (mirror Twitch flow — `oauth_helper.py --mode twitch` at `oauth_helper.py`, subprocess QWebEngineView, harvests cookie/token, stored at `~/.local/share/musicstreamer/gbs-token.txt` with 0o600 perms). Best if GBS.FM has a standard OAuth/login surface.
    3. **Cookies-import dialog** (mirror YouTube cookies — `cookie_import_dialog.py` with file-picker / paste / in-app login subprocess). Stored at `~/.local/share/musicstreamer/gbs-cookies.txt` with 0o600 perms. Best if no cleaner surface exists; the dev fixture (D-04a) becomes the production path.
    4. **Username/password form** (no existing precedent in MusicStreamer — would be a new pattern, ugliest UX, only chosen if 1–3 are unavailable). Stored as session token in SQLite.

  Researcher recommends one; planner locks it in `60-PLAN.md`.

- **D-04a:** **Dev fixture for research is OUTSIDE the repo.** Drop location: `~/.local/share/musicstreamer/dev-fixtures/gbs-cookies.txt`. Rationale: session cookies are sensitive — committing them to git history is hard to scrub; outside-repo eliminates the leak risk entirely. There is no `.gitignore` rule for fixtures today, so adding the file inside `.planning/` would be a real risk. Researcher reads from the absolute path; CONTEXT.md captures it (this section). Kyle drops the file after CONTEXT.md is written; researcher checks for its presence at the start of `gsd-phase-researcher`.
- **D-04b:** **Dev cookies file is NOT the user-facing v1 auth surface.** It's a development artifact for the researcher to inspect the GBS.FM auth-gated frontend and map the API surface. The user-facing auth UX is whichever option from D-04's preference ladder the planner picks based on research findings.
- **D-04c:** **AccountsDialog group placement.** Phase 60 inserts the new `_gbs_box: QGroupBox` between `_youtube_box` and the Twitch group at `accounts_dialog.py:91-115`. Add it to `layout` ordering at `accounts_dialog.py:137-138` accordingly. Status label uses the same `Qt.TextFormat.PlainText` (T-40-04) and `status_font` shared with Twitch/YouTube. Action button connection is bound-method (QA-05).

### Scope guardrails

- **D-05:** **Phase 60 scope is locked at: API integration foundation + multi-quality auto-import + AccountsDialog auth plumbing.** Voting and search-submit are explicitly Phase 60.1 / 60.2 (in the same milestone, future). Per-song comments, Discord↔IRC chat mirror, and song upload (all SEED-008 "nice-to-haves") are deferred to a later milestone or backlog. User explicitly: "I am OK to pass off some of the less ROI features to later."
- **D-05a:** **Phase 60.1 = voting/rating** (next phase after 60). Add via `/gsd-phase add` once Phase 60 lands. Builds on Phase 60's `gbs_api` module + AccountsDialog auth.
- **D-05b:** **Phase 60.2 = search + submit songs** (after 60.1). Add via `/gsd-phase add`.
- **D-05c:** **ROADMAP text for Phase 60 needs updating** before `/gsd-plan-phase`. Run `/gsd-phase edit 60` to:
  - Tighten the goal from "Browse, save, and play GBS.FM streams" to something like "Auto-import GBS.FM as a multi-quality station with metadata + AccountsDialog auth groundwork; foundation for voting (60.1) and search/submit (60.2)."
  - Sharpen SC #1 to require a single-click multi-quality import (not just "accessible from within MusicStreamer").
  - Add a new SC: AccountsDialog has a working "GBS.FM" group whose Connect/Disconnect cycle round-trips through the chosen auth surface.

### Claude's Discretion

- **Module name** — `gbs_api.py` is the recommended default. `gbs_import.py` (mirrors `aa_import.py` / `yt_import.py`) is acceptable if the planner prefers naming-by-role over naming-by-domain. Locked: snake_case + lowercase.
- **Identifier for "is GBS.FM already in the library?"** — D-02a leaves three options on the table (URL pattern match / `provider="GBS.FM"` query / dedicated `gbs_station_id` setting key). Planner picks based on what GBS.FM API actually exposes. Whatever is most stable across re-imports wins.
- **Toast wording** — "GBS.FM added" vs "GBS.FM streams updated" is the recommended split. Planner can adjust.
- **Auth flow specifics** — the entire D-04 inner UX is planner's choice once researcher reports back. The preference ladder + AccountsDialog `QGroupBox` shape is locked; everything inside the box is open.
- **Whether `import_station` lives in `gbs_api.py` or in a separate `gbs_import.py`** — lock the module count to "one or two" and let the planner decide. AA splits import vs API client into one file (`aa_import.py`). Radio-Browser does the same (`radio_browser.py` is both the API client and the discovery integration).
- **Concurrent-fetch parallelism** — `aa_import` uses `ThreadPoolExecutor` for image fetches at `aa_import.py:15`. Phase 60 fetches a single station's worth of data; parallelism may not be needed. Planner decides; if needed, mirror the AA pattern.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements

- `.planning/ROADMAP.md` §"Phase 60: GBS.FM Integration" — goal text and four success criteria. **Note:** scope as captured here exceeds the ROADMAP text; D-05c recommends `/gsd-phase edit 60` before planning.
- `.planning/REQUIREMENTS.md` §GBS-01 — "User can browse, save, and play GBS.FM streams from inside MusicStreamer (no browser bounce) *(harvest: SEED-008 — exact sub-capabilities to be refined at /gsd-discuss-phase time; may decompose into GBS-01..0N during planning)*". CONTEXT.md captures the refinement; planner decomposes into GBS-01a (multi-quality import), GBS-01b (auth plumbing), and ladder up to 60.1/60.2 if useful.
- `.planning/seeds/SEED-008-gbs-fm-integration.md` — full vision (voting, search+submit, comments, chat, upload). Phase 60 captures the foundation; 60.1/60.2 capture must-have voting/submit; SEED-008 nice-to-haves deferred.

### External target

- **Site:** https://gbs.fm — the platform being integrated. Researcher visits this directly (with the dev cookies fixture from D-04a) to map the API surface.

### Dev fixture (out of repo)

- `~/.local/share/musicstreamer/dev-fixtures/gbs-cookies.txt` — Kyle's session cookies, dropped after CONTEXT.md is committed. Researcher reads from this absolute path. Outside-repo by design (D-04a) — never commit cookies. **Researcher: check for this file's existence at the start; if missing, ask the user to drop it before proceeding.**

### Closest existing patterns (READ FIRST — Phase 60 mirrors these)

- `musicstreamer/aa_import.py` — multi-quality import precedent. Phase 60's `gbs_api.py` mirrors:
  - `aa_import.py:114-147` — `fetch_channels(listen_key, quality)` shape (single-quality fetch).
  - `aa_import.py:149-205` — `fetch_channels_multi(listen_key)` shape (multi-quality fetch); the `streams: [{url, quality, position, codec, bitrate_kbps}]` output is the canonical output shape Phase 60 should produce.
  - `aa_import.py:207-309` — `import_stations_multi(channels, repo, on_progress, on_logo_progress)` shape (orchestrator: one station per channel + multi-stream insert + logo download). Phase 60 simplifies to one station total.
  - `aa_import.py:23-47` — `_resolve_pls(pls_url)` PLS parsing (Phase 58 thin wrapper around `playlist_parser`). Phase 60 uses if GBS.FM serves PLS.
  - `aa_import.py:50-55` — `_normalize_aa_image_url(raw)` URL normalization. Phase 60 may need a similar helper for GBS.FM CDN image URLs.
  - `aa_import.py:103-112` — module-scope `QUALITY_TIERS / _CODEC_MAP / _BITRATE_MAP / _POSITION_MAP` constants; Phase 60 needs an equivalent for whatever quality tiers GBS.FM exposes.

- `musicstreamer/radio_browser.py` — pure-urllib HTTP client precedent. Phase 60 mirrors the no-SDK / no-auth-helper convention.

- `musicstreamer/yt_import.py` — third-party API → station list precedent (per SEED-008 breadcrumbs). Less direct match than `aa_import.py` but useful for the "scan + checklist + import" pattern if GBS.FM ever expands beyond one station.

### Auth precedents (preference ladder per D-04)

- **API key paste (preferred ladder #1):** `musicstreamer/ui_qt/accounts_dialog.py:157` — `audioaddict_listen_key` setting accessor. Setting written via `_repo.set_setting("audioaddict_listen_key", "")` at `accounts_dialog.py:294`.
- **OAuth subprocess WebView (ladder #2):** `musicstreamer/oauth_helper.py` (entry: `python -m musicstreamer.oauth_helper --mode twitch`). Phase 60 would add `--mode gbs`. Token at `~/.local/share/musicstreamer/gbs-token.txt` (mirror `paths.twitch_token_path()` convention).
- **Cookies-import dialog (ladder #3):** `musicstreamer/ui_qt/cookie_import_dialog.py:70` — `class CookieImportDialog(QDialog)`. File-picker, paste, and in-app login subprocess. Cookies at `~/.local/share/musicstreamer/gbs-cookies.txt` with 0o600 (mirror YouTube cookies path / Phase 999.7 file-permission convention).
- **Cookie utils (any cookies path):** `musicstreamer/cookie_utils.py` — `temp_cookies_copy()` (Phase 999.7) and `is_cookie_file_corrupted()`. Reused if D-04 picks ladder #3.
- **Paths convention:** `musicstreamer/paths.py` — XDG-discovery for `~/.local/share/musicstreamer/`. New helper `paths.gbs_token_path()` or `paths.gbs_cookies_path()` if D-04 picks ladder #2 or #3.

### Surface integration points

- `musicstreamer/ui_qt/main_window.py:131-138` — hamburger menu Group 1 (`New Station`, `Discover Stations`, `Import Stations`). New "Add GBS.FM" entry inserts here.
- `musicstreamer/ui_qt/main_window.py:669-680` — `_open_discovery_dialog` / `_open_import_dialog` handlers. Phase 60's `_on_gbs_add_clicked` follows the same shape but does NOT open a dialog — it kicks off `gbs_api.import_station(...)` and toasts on completion.
- `musicstreamer/ui_qt/accounts_dialog.py:91-103` — YouTube `_youtube_box: QGroupBox` (status label + action button). Phase 60's `_gbs_box` mirrors.
- `musicstreamer/ui_qt/accounts_dialog.py:104-115` — Twitch `_status_label` + `_action_btn` pair. Same shape, two existing precedents.
- `musicstreamer/ui_qt/accounts_dialog.py:137-138` — `layout.addWidget(...)` ordering. Insert `_gbs_box` between YouTube and Twitch.

### Data layer (no schema changes)

- `musicstreamer/repo.py:51-110` — `station_streams` schema (includes `bitrate_kbps` from Phase 47.2). No migration needed.
- `musicstreamer/repo.py:185-196` — `Repo.insert_stream(station_id, url, label, quality, position, stream_type, codec, bitrate_kbps)`. Phase 60 calls per-quality.
- `musicstreamer/repo.py:178-184` — `Repo.list_streams(station_id)`. Used by idempotent re-fetch (D-02a).
- `musicstreamer/repo.py:199-202` — `Repo.update_stream(...)`. Used during refresh (D-02a).

### Stream-ordering / playback (no changes — table-stakes)

- `musicstreamer/stream_ordering.py:43` — `order_streams(streams)`. Already partitions by `(codec_rank, bitrate_kbps, position)` per Phase 47.1 D-07/D-09. Phase 60's output flows in directly.
- `musicstreamer/player.py` — GStreamer playback. No changes; standard `Player.play(station)` path.

### Cover art (no changes)

- `musicstreamer/cover_art.py` — iTunes Search API for ICY-track album art. Continues to work independently of station logo.
- `musicstreamer/assets.py` — `copy_asset_for_station` for station logo download. Reused by `gbs_api.import_station`.

### Project conventions (apply during planning)

- **Bound-method signal connections, no self-capturing lambdas (QA-05)** — applies to the new menu `triggered` connection, AccountsDialog button connections, and any signal wiring inside the import flow.
- **`Qt.TextFormat.PlainText` (T-40-04)** — applies to all new status labels in AccountsDialog.
- **snake_case + type hints throughout, no formatter** — per `.planning/codebase/CONVENTIONS.md`.
- **Linux X11 deployment target, DPR=1.0** — per project memory `project_deployment_target.md`. HiDPI/Retina/Wayland-fractional findings get downgraded CRITICAL → WARNING in any UI audit.
- **Single-user scope** — per project memory `project_single_user_scope.md`. Assume one GBS.FM account, no multi-profile UX. Deferred SEED-008 nice-to-haves (chat moderation, multi-account submit) inherit this.
- **Pure `urllib`, no SDK for HTTP clients** — `radio_browser.py` and `aa_import.py` precedent.
- **10s timeout per HTTP call** — `aa_import.py` and `radio_browser.py` precedent.
- **File modes for sensitive data: 0o600** — Phase 999.7 cookie convention; applies to D-04 ladder #2 (token file) and #3 (cookies file).

### Cross-phase ROADMAP edits required (D-05c)

- `/gsd-phase edit 60` — sharpen goal text + SC #1/#3 + add an AccountsDialog SC. Run before `/gsd-plan-phase 60`.
- `/gsd-phase add` (after Phase 60 lands) — Phase 60.1 (voting/rating) and Phase 60.2 (search + submit). Both built on Phase 60's `gbs_api` + AccountsDialog auth.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`aa_import.import_stations_multi` shape** — orchestrator for "one station + multi-stream insert + logo download" (with `ThreadPoolExecutor` for image fetches and a `(channel_key, image_url)` map). Phase 60 simplifies to one station total but inherits the structure.
- **`aa_import.fetch_channels_multi` output shape** — `[{streams: [{url, quality, position, codec, bitrate_kbps}], ...}]`. Phase 60's `gbs_api.fetch_streams()` produces a flat version of this (no enclosing channel-list wrapper since GBS.FM is one station).
- **`Repo.insert_stream` / `Repo.update_stream`** — multi-stream row CRUD. No schema changes needed; `bitrate_kbps` column already in place (Phase 47.2 D-02 / 47.1 D-01).
- **`stream_ordering.order_streams`** — Phase 47.1 quality ranking. Consumes Phase 60's output unchanged.
- **`assets.copy_asset_for_station`** — station logo download; reused by `aa_import.import_stations_multi`.
- **`AccountsDialog._youtube_box` and Twitch group** — visual + status-label + action-button shape. Two existing precedents; Phase 60's `_gbs_box` is the third.
- **`paths.twitch_token_path()` / YouTube cookies path convention** — for D-04 ladder #2/#3 storage. Phase 60 adds `paths.gbs_token_path()` or `paths.gbs_cookies_path()` per planner.
- **`oauth_helper.py --mode twitch` pattern** — for D-04 ladder #2. Adding `--mode gbs` is the planner's call.
- **`cookie_import_dialog.CookieImportDialog`** — file-picker + paste + subprocess login. For D-04 ladder #3.
- **`cookie_utils.temp_cookies_copy()`** — Phase 999.7 read-side hardening for cookie files. Reused if D-04 picks ladder #3.

### Established Patterns

- **Hamburger menu Group 1 = ingestion actions.** New / Discover / Import all live there. "Add GBS.FM" fits the group's intent.
- **AccountsDialog `QGroupBox` per provider.** YouTube + Twitch + (DB-only AA section). GBS.FM follows.
- **Pure `urllib` HTTP clients with 10s timeouts.** `radio_browser.py` + `aa_import.py`. No new HTTP dep.
- **One station + multiple `station_streams` entries with quality/position/codec/bitrate_kbps.** Phase 47.x locked the data shape.
- **`stream_ordering` partitions unknowns last.** Phase 60 should set `bitrate_kbps=0` only when GBS.FM truly does not advertise bitrate; `_BITRATE_MAP` analogue should aim for non-zero values.
- **Bound-method signal connections (QA-05).** All new connections.
- **`Qt.TextFormat.PlainText` (T-40-04) for status labels.** Phase 60 status label too.
- **0o600 file mode for sensitive data.** Token/cookies file if D-04 picks ladder #2/#3.
- **Idempotent re-import.** `aa_import.import_stations_multi` dedups by `(network_slug, channel_key)`. Phase 60 dedups by GBS.FM-stable identifier (D-02a, planner picks).

### Integration Points

- **New menu action:** `main_window.py:131-138` — insert `act_gbs = self._menu.addAction("Add GBS.FM"); act_gbs.triggered.connect(self._on_gbs_add_clicked)` between `act_import` and the `addSeparator()` at line 140. Add `_on_gbs_add_clicked` method modeled on `_open_import_dialog` but kicking `gbs_api.import_station(self._repo, on_progress=...)` and toasting on completion.
- **New AccountsDialog group:** `accounts_dialog.py:91-115` → insert `_gbs_box` between `_youtube_box` and the Twitch group. Update `accounts_dialog.py:137-138` layout ordering. Status reflects whether the chosen auth credential (D-04) is set.
- **New module `musicstreamer/gbs_api.py`** (or `gbs_import.py`) — public API per D-03. Pure `urllib`, no SDK.
- **New paths helper** if D-04 picks ladder #2 or #3 — `paths.gbs_token_path()` or `paths.gbs_cookies_path()`.
- **No schema changes.** `station_streams.bitrate_kbps` already migrated (Phase 47.2 D-02). `settings` table reuses for any DB-stored auth value (mirror AA `audioaddict_listen_key`).
- **Logo download path:** `~/.local/share/musicstreamer/assets/gbs-fm-logo.png` (or whatever `assets.copy_asset_for_station` returns). Existing path; no new directory.
- **Toast surface:** `MainWindow._toast(...)` (existing) or whatever the import flows use today. Planner mirrors `aa_import` toast precedent.

</code_context>

<specifics>
## Specific Ideas

- **The user's framing reset mid-discussion.** Initial reading of "browse, save, play" was naive — that's already possible today via the manual "New Station" path. The actual value is **API integration** (multi-quality auto-import + metadata + auth groundwork), surfaced as one hamburger-menu click. CONTEXT.md captures the corrected scope; ROADMAP text needs the same correction (D-05c).
- **GBS.FM is a single station, not a network or directory.** This collapses the "import flow tab" / "discovery tab" decision tree entirely — no checklist, no search, no per-channel API loop. The hamburger entry is a single action.
- **The cookies file is a research artifact, not a v1 user-facing auth surface.** User drops it at `~/.local/share/musicstreamer/dev-fixtures/gbs-cookies.txt` (outside repo) so the researcher can map the GBS.FM API. The user-facing auth UX is whichever of D-04's ladder the planner picks based on findings.
- **AA-pattern-mirroring is the single biggest implementation lever.** Phase 47.x already locked the multi-stream data shape; `aa_import.import_stations_multi` already locked the orchestrator shape; `stream_ordering.order_streams` already locked the play-time consumer. Phase 60 produces output that flows in unchanged.
- **Phase 60 is the foundation, not the feature.** Voting (60.1) and search/submit (60.2) are where the user-visible interactivity from SEED-008 actually lands. Phase 60 ships the API client, the auth surface, and the multi-quality import — without those, 60.1 and 60.2 can't ship cleanly. Frame the phase value accordingly when writing PR descriptions / verification reports.
- **No breaking changes.** No schema migrations, no playback path changes, no AccountsDialog reorganization. All net-additive surface area.

</specifics>

<deferred>
## Deferred Ideas

### Phase 60.1 (next phase, same milestone)
- **Voting/rating the currently-playing track via GBS.FM API.** SEED-008 "must-have." Now-playing UI control + `gbs_api.vote(track_id, direction)` method + optimistic UX + error handling. Builds on Phase 60's `gbs_api` + AccountsDialog auth (auth required for voting).

### Phase 60.2 (after 60.1, same milestone)
- **Search + submit songs to the station's playlist.** SEED-008 "must-have." New dialog (similar shape to `DiscoveryDialog` but search-and-submit instead of search-and-save) + `gbs_api.search(query)` + `gbs_api.submit(track_id)` methods. Builds on 60 + 60.1.

### Later milestone or backlog (lower ROI per user)
- **Per-song comments.** SEED-008 "nice-to-have." Comment thread view per currently-playing-track; reply / submit / read. Sizable UI work + API surface.
- **Discord ↔ IRC chat mirror.** SEED-008 highest-complexity nice-to-have. Two transport layers (Discord WebSocket / IRC TCP) + bidirectional message bridging + UI for chat history. SEED-008: "drop chat first if scope shrinks."
- **Song upload.** SEED-008 nice-to-have. File picker + multi-MB upload over HTTP + GBS.FM-side metadata mapping + post-upload status.

### Scope boundary edges to revisit if user feedback says otherwise
- **First-launch nudge for "Add GBS.FM."** Currently rejected (D-02c). If discoverability turns out to be poor, a one-time toast or empty-state hint can be added without breaking anything.
- **Per-station-quality manual override.** Today `stream_ordering` picks; user can manually switch via the stream picker. If GBS.FM users want to "always prefer 256kbps mp3," that's a future polish phase touching the existing stream picker UX.
- **GBS.FM-specific now-playing surface.** If the API exposes show/DJ/playlist metadata that the standard ICY title doesn't capture, a future phase could add a richer surface. Today: standard ICY path.

### None — discussion stayed within (re-scoped) phase scope
- All other ideas raised during discussion are either captured as decisions above or deferred to the phases listed.

</deferred>

---

*Phase: 60-gbs-fm-integration*
*Context gathered: 2026-05-03*
