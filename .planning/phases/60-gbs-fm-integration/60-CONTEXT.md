# Phase 60: GBS.FM Integration — Context

**Gathered:** 2026-05-03
**Status:** Ready for planning

<domain>
## Phase Boundary

> **Scope update (2026-05-03):** ROADMAP entry for Phase 60 was edited via `/gsd-phase edit 60` after this CONTEXT.md was first written. The original split (Phase 60 = foundation, 60.1 = voting, 60.2 = search/submit) was rejected by the user — voting and search/submit ship in Phase 60 itself alongside the foundation, plus active-playlist viewing. Only comments / chat mirror / song upload remain deferred. CONTEXT.md updated in place: architectural decisions D-01..D-04c carry forward unchanged; D-05 series rewritten; D-06..D-08 added for the merged surfaces. See `60-DISCUSSION-LOG.md` for the original split rationale.

Phase 60 is the **GBS.FM API integration**: ship the foundation **and** the user-visible interactive features (active playlist view, vote, search-and-submit) in a single phase. Comments, chat mirror, and song upload remain deferred (lower ROI per user).

1. **Multi-quality auto-import** — a hamburger menu action ("Add GBS.FM") fetches all stream quality variants + station logo + station metadata via GBS.FM's API, and inserts them as **one library row with multiple `station_streams` entries** (mirroring the shape `aa_import.import_stations_multi()` produces).
2. **AccountsDialog auth/credentials** — a new "GBS.FM" `QGroupBox` lands in `accounts_dialog.py` alongside YouTube and Twitch. Login is **optional for play** but **required for vote and submit** (auth-gated features hide or disable their controls when the user is logged out).
3. **GBS.FM API client** — a new `musicstreamer/gbs_api.py` module exposing stream-fetch + station-metadata + active-playlist + vote + search + submit endpoints. Pure `urllib`, no SDK; modeled on `aa_import.py` / `radio_browser.py` / `yt_import.py` once researcher confirms which fits closest.
4. **Active playlist visibility** — when a GBS.FM station is playing, the Now Playing surface shows the active playlist (current and/or upcoming tracks, whatever the API exposes). New widget on the Now Playing panel (D-06).
5. **Vote on currently-playing track** — when a GBS.FM station is playing AND the user is logged in, the Now Playing surface offers a vote control that round-trips to the GBS.FM API with optimistic UI (D-07).
6. **Search + submit songs** — the user can search GBS.FM's catalog and submit a song to the station's playlist. New dialog accessed from the hamburger menu (D-08).
7. **Standard playback path** — saved GBS.FM stations play through the existing GStreamer pipeline; `stream_ordering.order_streams()` picks the best quality at play time. No changes to playback machinery.

**The literal "browse + save + play" reading of the original ROADMAP entry understated this scope.** A user can paste a single GBS.FM stream URL into "New Station" today and it plays. Phase 60 ships the *interactive integration with the GBS.FM API* — multi-quality awareness, automatic logo/metadata, AccountsDialog auth, active-playlist view, voting, and search-and-submit. The ROADMAP entry was rewritten on 2026-05-03 to reflect this.

**In scope:**
- Hamburger menu entry "Add GBS.FM" (slotted into Group 1 alongside `New Station / Discover Stations / Import Stations` at `main_window.py:131-138`).
- Hamburger menu entry for the search-and-submit dialog (label TBD — "Search GBS.FM…" recommended; D-08); placement decided by planner.
- New `gbs_api` module: stream-fetch, station-metadata-fetch, active-playlist-fetch, vote, search, submit. Pure `urllib`, no SDK.
- New library row insert: one `Station` + N `station_streams` rows populated with `url / quality / position / codec / bitrate_kbps` (mirrors `aa_import.import_stations_multi`).
- Idempotent re-fetch: clicking "Add GBS.FM" when it's already in the library refreshes streams + logo + metadata in-place (UPDATE vs INSERT). Toast on success.
- Logo download to `~/.local/share/musicstreamer/assets/` (existing `assets.copy_asset_for_station` pattern).
- AccountsDialog "GBS.FM" `QGroupBox` (status label + Connect/Disconnect button), mirroring the YouTube/Twitch precedent at `accounts_dialog.py:91-115`.
- Auth flow (one of: API key paste / OAuth subprocess WebView / cookies-import dialog / username-password — picked by planner once researcher reports back, see D-04).
- Token/credential storage at the convention the planner picks (file under `~/.local/share/musicstreamer/` like Twitch token / YouTube cookies, OR setting in SQLite `settings` table like `audioaddict_listen_key` at `accounts_dialog.py:157`).
- Active-playlist widget on Now Playing panel (D-06): shows current and/or upcoming tracks for the playing GBS.FM station; refresh strategy (poll / push / on-station-change) decided at planning time.
- Vote control on Now Playing panel (D-07): up/down or whatever GBS.FM exposes; auth-gated (hidden or disabled when logged out); optimistic UI with rollback on API error.
- Search-and-submit dialog (D-08): search GBS.FM catalog by query string, present results, submit selected song to the station's playlist; round-trips to the API and toasts success/failure.
- Standard ICY title path continues to work for the playing track display; vote control attaches to *that* track's identity (planner decides how to map ICY title → GBS.FM track ID; may need an extra API call).

**Out of scope (deferred to a later phase or backlog — lower ROI per user):**
- **Per-song comments** (SEED-008 nice-to-have). Comment thread per song; reply / submit / read. Sizable UI work + API surface.
- **Discord ↔ IRC chat mirror** (SEED-008 highest-complexity nice-to-have). Two transport layers + bidirectional message bridging + UI for chat history. SEED-008: "drop chat first if scope shrinks."
- **Song upload** (SEED-008 nice-to-have). File picker + multi-MB upload over HTTP + GBS.FM-side metadata mapping + post-upload status.

**Phase 60 is intentionally large** — it merges what was originally split into Phase 60 (foundation) + Phase 60.1 (voting) + Phase 60.2 (search/submit). User framing: ship the meaningful interactive value in one phase rather than three small ones, since the foundation alone has no user-visible payoff. Planner: feel free to split into multiple plans (e.g. `60-01-api-client`, `60-02-import`, `60-03-accounts`, `60-04-active-playlist`, `60-05-vote`, `60-06-search-submit`) — but keep them in the same phase.

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

- **D-03:** **New module `musicstreamer/gbs_api.py`** (final name at planner discretion; analogs are `aa_import.py`, `radio_browser.py`, `yt_import.py`). Public API surface includes the foundation endpoints **and** the interactive endpoints needed for D-06/D-07/D-08:
  - **Foundation:**
    - `fetch_streams(auth_context=None) -> list[dict]` — returns all quality variants. Each dict carries `{url, quality, position, codec, bitrate_kbps}` matching the AA shape at `aa_import.py:191-198`.
    - `fetch_station_metadata(auth_context=None) -> dict` — returns `{name, description, logo_url, ...}` for the GBS.FM station.
    - `import_station(repo, on_progress=None) -> tuple[int, int]` — orchestrator that calls the two `fetch_*` functions, downloads the logo, inserts/updates the `Station` and `station_streams` rows. Mirrors `aa_import.import_stations_multi` shape (single station, idempotent).
  - **Active playlist (D-06):**
    - `fetch_active_playlist(auth_context=None) -> dict` — returns the active playlist context. Exact shape (current track + upcoming queue / current + history / current only) is research-pending — researcher reports what GBS.FM actually exposes. Likely returns `{current: {...}, upcoming: [...], previous: [...]}` or some subset.
  - **Voting (D-07, auth-required):**
    - `vote(track_id: str | int, direction: str, auth_context) -> dict` — round-trips a vote to the GBS.FM API. `direction` shape (e.g. `"up" / "down"`, `"like" / "dislike"`, integer score, `"vote" / "unvote"`) is research-pending. Returns the new vote state or raises on error.
  - **Search + submit (D-08, auth-required for submit):**
    - `search(query: str, auth_context=None) -> list[dict]` — returns catalog search results. Each dict at minimum `{track_id, title, artist, ...}`. May or may not require auth depending on GBS.FM's policy — researcher confirms.
    - `submit(track_id: str | int, auth_context) -> dict` — submits a track to the station's playlist queue. Returns submission status; raises on error (e.g. duplicate, rate-limited, unauthorized).
  - **Auth context:** `auth_context` is the planner's choice of token/cookie/key passing convention — shape determined once researcher confirms auth scheme (see D-04 ladder). For Phase 60, a thin helper that reads the stored credential and returns whatever the API client needs (header dict / cookie jar / query string param) is the recommended shape.
- **D-03a:** Pure `urllib`, no SDK — same convention as `radio_browser.py` and `aa_import.py`. 10s timeouts per call. Vote and submit calls may need a slightly longer timeout (e.g. 15s) to tolerate server-side write latency — planner decides per testing.
- **D-03b:** Image URL handling: download logo via `assets.copy_asset_for_station` (existing pattern, reused by `aa_import.import_stations_multi` at `aa_import.py:281`). Do not skip cover-art / iTunes-Search-API integration — `cover_art.py` keeps working at play time independently for the per-track album art.
- **D-03c:** **Error handling** — `vote`, `submit`, and `fetch_active_playlist` may surface user-meaningful failures (auth expired, rate-limited, network down). Module exposes typed exceptions or sentinel return values (planner picks); call sites translate into toast messages and rollback the optimistic UI for vote (D-07).

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

- **D-04a:** **Dev fixture for research lives at `<repo>/.local/gbs.fm.cookies.txt`** (gitignored — `.local/` was added to `.gitignore` 2026-05-04 specifically to keep this fixture out of git sync). Rationale: session cookies are sensitive; the `.local/` ignore rule eliminates the commit-leak risk while keeping the file co-located with the repo for ergonomic researcher access. The original draft proposed `~/.local/share/musicstreamer/dev-fixtures/gbs-cookies.txt` (fully outside-repo) — Kyle elected the project-relative `.local/` path with explicit gitignore protection instead. Researcher reads from `<repo>/.local/gbs.fm.cookies.txt`; checks for its presence at the start of `gsd-phase-researcher` and prompts the user to drop it if missing.
- **D-04b:** **Dev cookies file is NOT the user-facing v1 auth surface.** It's a development artifact for the researcher to inspect the GBS.FM auth-gated frontend and map the API surface. The user-facing auth UX is whichever option from D-04's preference ladder the planner picks based on research findings.
- **D-04c:** **AccountsDialog group placement.** Phase 60 inserts the new `_gbs_box: QGroupBox` between `_youtube_box` and the Twitch group at `accounts_dialog.py:91-115`. Add it to `layout` ordering at `accounts_dialog.py:137-138` accordingly. Status label uses the same `Qt.TextFormat.PlainText` (T-40-04) and `status_font` shared with Twitch/YouTube. Action button connection is bound-method (QA-05).

### Scope guardrails

- **D-05:** **Phase 60 scope is locked at the merged shape:** API integration foundation + multi-quality auto-import + AccountsDialog auth + active playlist visibility + voting + search-and-submit. Per-song comments, Discord↔IRC chat mirror, and song upload (all SEED-008 "nice-to-haves") remain deferred to a later milestone or backlog. User explicitly (`/gsd-phase edit 60` clarification, 2026-05-03): *"This also needs to integrate with the API though doesn't yet need to take into account all features. The ability to see the active playlist, vote, and even search for music to add is what I am wanting."*
- **D-05a:** **Original 60.1 / 60.2 split is retired.** No new phases get added to the ROADMAP for voting or search/submit — they ship in Phase 60. The 60.1/60.2 references in `60-DISCUSSION-LOG.md` are historical and reflect an interim split that the user reversed during the `/gsd-phase edit 60` step.
- **D-05b:** **Phase 60 is intentionally large.** Estimated 5–7 plans (e.g. `60-01-api-client`, `60-02-import`, `60-03-accounts`, `60-04-active-playlist`, `60-05-vote`, `60-06-search-submit`, plus testing/regression as warranted). The planner decomposes; the requirements (`GBS-01`) may decompose into `GBS-01a..0F` — planner's call.
- **D-05c:** **ROADMAP text for Phase 60 was updated on 2026-05-03** (`/gsd-phase edit 60`):
  - Goal rewritten to: *"GBS.FM is integrated as a first-class station inside MusicStreamer via the GBS.FM API: multi-quality auto-import, optional AccountsDialog login, view of the active playlist, vote on the currently-playing track, and search-and-submit songs to the station. Comments, Discord↔IRC chat mirror, and song upload are deferred to a later phase."*
  - SC count increased from 4 to 6 to cover the merged surfaces (see ROADMAP.md §"Phase 60: GBS.FM Integration" for the canonical text).
  - No further `/gsd-phase` action is required before `/gsd-plan-phase 60`.
- **D-05d:** **Cross-phase impact:** none. Phase 60 still depends on Nothing. Phase 61+ are unchanged. No renumbering needed.

### Active playlist surface (merged-scope addition)

- **D-06:** **The active GBS.FM playlist renders inside `NowPlayingPanel` (`musicstreamer/ui_qt/now_playing_panel.py`)** when the playing station is GBS.FM. Likely placement: a new widget (probably `QListWidget` or `QListView` with a small custom delegate) below the existing ICY title / star / pause / stop / stream-picker row, OR in a collapsible section below the panel — final placement is planner's call based on Phase 64's "Also on:" line precedent (it lands as a new label between `name_provider_label` and `icy_label`). Hidden when the playing station is not GBS.FM (mirrors Phase 51 D-06 / Phase 64 D-05 hide-when-empty contract).
- **D-06a:** **Refresh strategy is research-pending.** Three reasonable options:
  - **Poll on interval** (e.g. every 15-30s while a GBS.FM station is playing). Simplest; some wasted requests.
  - **Poll on track change** (subscribe to ICY title changes, fetch playlist when title changes). More efficient; relies on ICY title transitions firing.
  - **Push from API (WebSocket / SSE)** if GBS.FM exposes a live channel. Best UX; most plumbing.
  Researcher reports what GBS.FM exposes; planner picks. Default if uncertain: poll on track change with a fallback periodic poll.
- **D-06b:** **Auth-gating:** if GBS.FM exposes the active playlist publicly (no auth required), the widget shows for any user. If auth-required, the widget shows logged-in-only with a "Log in to see the playlist" placeholder otherwise. Researcher confirms.
- **D-06c:** **Click-through to track favoriting:** Phase 60 does NOT add click-to-favorite-track from the playlist widget — favoriting works via the existing star button on the now-playing track only. A future phase can extend if Kyle wants per-row favorite toggles.

### Vote control surface (merged-scope addition)

- **D-07:** **Vote control lands on `NowPlayingPanel` next to the existing star/pause/stop/stream-picker row** when the playing station is GBS.FM AND the user is logged in. Likely shape: one or two `QPushButton` widgets (up/down or thumb-up/thumb-down) with iconography matching `_theme.py` icon sizes. Hidden entirely when the station is non-GBS.FM or the user is logged out (mirrors D-05's auth-gating).
- **D-07a:** **Optimistic UI:** click → button visually toggles immediately, `gbs_api.vote(...)` runs on a worker thread, on success the visual state confirms; on error the button reverts and a toast surfaces the error. Mirrors the existing star-button precedent in `now_playing_panel.py` for off-thread API calls + Qt-signal completion.
- **D-07b:** **Track identity for voting** is research-pending. The Now Playing panel knows the ICY title (e.g. `"Artist - Title"`) but GBS.FM's vote API likely expects a `track_id`. Two approaches:
  - **Map ICY title → track_id via the active-playlist endpoint** (D-06): the playlist response presumably includes the `track_id` for the currently-playing track. Vote uses that.
  - **Direct ICY-title-based vote endpoint** if GBS.FM exposes one. Less likely.
  Researcher reports; planner picks. Default: derive from `fetch_active_playlist()` response.
- **D-07c:** **Rate-limiting / abuse prevention:** single-user scope (per project memory) means we don't need anti-abuse UI; we DO need to gracefully handle GBS.FM-server-side rate limits if the user mashes the vote button. The optimistic-UI rollback (D-07a) covers this — if the API returns 429 / similar, rollback + toast.
- **D-07d:** **Vote state persistence:** if the user reloads the now-playing panel mid-track (e.g. switches stations and switches back), do we re-fetch the user's current vote on this track? Recommendation: yes — `fetch_active_playlist` response should include the user's vote on the current track if logged in. Planner implements; if the API doesn't expose it, fallback to "vote button starts in neutral state every time."

### Search + submit surface (merged-scope addition)

- **D-08:** **New dialog `GBSSearchDialog` (working name) at `musicstreamer/ui_qt/gbs_search_dialog.py`** — search GBS.FM catalog by query string + submit selected song to the station's playlist. Modeled on `DiscoveryDialog` (`musicstreamer/ui_qt/discovery_dialog.py`) shape (search box → results list → action button), but the action is "Submit" instead of "Save to library."
- **D-08a:** **Hamburger menu entry** opens the dialog. Recommended label: "Search GBS.FM…" (with ellipsis to signal a dialog opens). Placement: planner's call — "Group 1 next to Discover Stations" is the most natural fit semantically. Bound-method `triggered` connection (QA-05).
- **D-08b:** **Dialog shape:**
  - Top: query `QLineEdit` + Search `QPushButton` (or live search via debounced `textChanged` — planner's call; live search has rate-limit risk).
  - Middle: results `QListWidget` showing each track as `Artist · Title` (or whatever shape the search returns).
  - Bottom: Submit `QPushButton` (enabled when a row is selected) + Close. Submit calls `gbs_api.submit(track_id, auth_context)` on a worker thread; toasts success/failure.
  - Empty state: "Enter a search term to find tracks on GBS.FM." Loading state: spinner + "Searching…". Error state: inline error label.
- **D-08c:** **Auth-gating:** dialog opens regardless of auth state, but Submit is disabled (or shows "Log in to submit songs") if the user isn't logged in. Search may or may not require auth depending on what GBS.FM exposes — research-pending; if auth-required for search, the entire dialog requires login (similar to MGMT-style required state). Planner decides based on research.
- **D-08d:** **Duplicate / rate-limit handling:** if `submit` returns "track already queued" or "rate limited," the dialog surfaces an inline error (not a toast) so the user can correct without losing the search context. Hard errors (auth expired, network down) surface as toasts and the dialog stays open.
- **D-08e:** **Result pagination:** if GBS.FM search returns many results, pagination/virtualization is research-pending. Default: show first N results (e.g. 50), with "Show more" affordance only if needed. Planner mirrors `DiscoveryDialog`'s approach if it has one.

### Claude's Discretion

- **Module name** — `gbs_api.py` is the recommended default. `gbs_import.py` (mirrors `aa_import.py` / `yt_import.py`) is acceptable if the planner prefers naming-by-role over naming-by-domain. Locked: snake_case + lowercase.
- **Identifier for "is GBS.FM already in the library?"** — D-02a leaves three options on the table (URL pattern match / `provider="GBS.FM"` query / dedicated `gbs_station_id` setting key). Planner picks based on what GBS.FM API actually exposes. Whatever is most stable across re-imports wins.
- **Toast wording** — "GBS.FM added" vs "GBS.FM streams updated" is the recommended split. Planner can adjust.
- **Auth flow specifics** — the entire D-04 inner UX is planner's choice once researcher reports back. The preference ladder + AccountsDialog `QGroupBox` shape is locked; everything inside the box is open.
- **Whether `import_station` lives in `gbs_api.py` or in a separate `gbs_import.py`** — lock the module count to "one or two" and let the planner decide. AA splits import vs API client into one file (`aa_import.py`). Radio-Browser does the same (`radio_browser.py` is both the API client and the discovery integration).
- **Concurrent-fetch parallelism** — `aa_import` uses `ThreadPoolExecutor` for image fetches at `aa_import.py:15`. Phase 60 fetches a single station's worth of data; parallelism may not be needed. Planner decides; if needed, mirror the AA pattern.
- **Active-playlist refresh strategy (D-06a)** — poll-on-interval vs poll-on-track-change vs WebSocket/SSE push. Default if uncertain: poll on track change with periodic fallback. Planner picks based on what the GBS.FM API exposes.
- **Active-playlist widget shape (D-06)** — `QListWidget` vs `QListView`+delegate vs custom widget; final placement (between `name_provider_label` and `icy_label` like Phase 64's "Also on:" line, or below the player controls, or in a collapsible section). Planner picks; precedent is Phase 64's hide-when-empty pattern.
- **Vote button iconography and direction (D-07)** — single thumb-up vs up/down pair vs heart/un-heart. Depends on what GBS.FM exposes. Use icons from `_theme.py` size scale.
- **Track identity for vote (D-07b)** — derive `track_id` from `fetch_active_playlist` response (recommended) vs ICY-title-based vote endpoint (only if exposed). Planner picks per research.
- **Search dialog filename and class name (D-08)** — `gbs_search_dialog.py` / `GBSSearchDialog` is the recommended default. Planner can rename if a clearer convention emerges.
- **Search debounce vs explicit-search-button (D-08b)** — live debounced search has rate-limit risk; explicit button is safer. Planner decides per research-confirmed rate limits.
- **Hamburger menu placement for "Search GBS.FM…" (D-08a)** — Group 1 next to "Discover Stations" (semantically closest) is the recommended default. Planner can move to Group 2 if the menu groups feel imbalanced.
- **Whether `import_station` lives in `gbs_api.py` or in a separate `gbs_import.py`** — lock the module count to "one or two" and let the planner decide. AA splits import vs API client into one file (`aa_import.py`). Radio-Browser does the same (`radio_browser.py` is both the API client and the discovery integration). For the merged scope, three reasonable groupings: (1) one file `gbs_api.py` for everything; (2) split client/import: `gbs_api.py` (HTTP + endpoints) + `gbs_import.py` (orchestrator); (3) split by feature: `gbs_api.py` + `gbs_import.py` + `gbs_search_dialog.py` (UI for search/submit). Planner picks based on plan decomposition.

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

### Dev fixture (gitignored, project-relative)

- `<repo>/.local/gbs.fm.cookies.txt` — Kyle's session cookies. `.local/` is gitignored (added 2026-05-04 alongside this CONTEXT.md update; see `.gitignore`). Researcher reads from this project-relative path. Never commit — gitignore + dotted-folder convention make accidental staging effectively impossible. **Researcher: check for this file's existence at the start; if missing, ask the user to drop it before proceeding.**

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

- `musicstreamer/ui_qt/main_window.py:131-138` — hamburger menu Group 1 (`New Station`, `Discover Stations`, `Import Stations`). New "Add GBS.FM" entry inserts here. New "Search GBS.FM…" entry (D-08a) most likely lands in this group too.
- `musicstreamer/ui_qt/main_window.py:669-680` — `_open_discovery_dialog` / `_open_import_dialog` handlers. Phase 60's `_on_gbs_add_clicked` follows the same shape but does NOT open a dialog — it kicks off `gbs_api.import_station(...)` and toasts on completion. Phase 60's `_open_gbs_search_dialog` (D-08) follows `_open_discovery_dialog` exactly (open-dialog handler).
- `musicstreamer/ui_qt/accounts_dialog.py:91-103` — YouTube `_youtube_box: QGroupBox` (status label + action button). Phase 60's `_gbs_box` mirrors.
- `musicstreamer/ui_qt/accounts_dialog.py:104-115` — Twitch `_status_label` + `_action_btn` pair. Same shape, two existing precedents.
- `musicstreamer/ui_qt/accounts_dialog.py:137-138` — `layout.addWidget(...)` ordering. Insert `_gbs_box` between YouTube and Twitch.

### Now Playing surfaces (D-06, D-07 — merged-scope additions)

- `musicstreamer/ui_qt/now_playing_panel.py` — `class NowPlayingPanel(QWidget)`. Read in full before planning the active-playlist widget (D-06) and the vote control (D-07). The panel already has multiple precedents for "show only when condition met" (Phase 51 sibling label pattern, Phase 64 "Also on:" line, hide-when-empty contract).
- `musicstreamer/ui_qt/now_playing_panel.py` (Phase 64 `_sibling_label` precedent) — same hide-when-empty contract Phase 60 D-06 / D-07 mirror. The panel has a stable layout with multiple optional widgets; D-06 / D-07 add two more.
- `musicstreamer/ui_qt/now_playing_panel.py` star button precedent — off-thread API call + Qt-signal completion + optimistic UI rollback. Phase 60 D-07a vote button mirrors this exactly.
- `musicstreamer/ui_qt/main_window.py` `_on_station_activated` flow — drives `NowPlayingPanel.bind_station(station)`. Phase 60 D-06 hooks into `bind_station` to start/stop the playlist refresh timer; D-07 hooks the same point to show/hide the vote control based on station provider.

### Search + submit surface (D-08 — merged-scope addition)

- `musicstreamer/ui_qt/discovery_dialog.py` — closest existing dialog precedent. Search-box + results-list + per-row action shape. Phase 60's `gbs_search_dialog.py` mirrors but the action is "Submit to playlist" instead of "Save to library." Read the full file for the dialog skeleton.
- `musicstreamer/ui_qt/discovery_dialog.py` (preview-play-via-main-Player precedent) — Phase 60's search dialog does NOT need preview play (the playing station is GBS.FM; the user is already listening). Skip that pattern.
- `musicstreamer/ui_qt/import_dialog.py` — secondary precedent if the planner wants a multi-tab shape (e.g. "Search" tab + "Recent submits" tab). Default is single-purpose; no tabs needed.

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

### Cross-phase ROADMAP changes (D-05c — completed 2026-05-03)

- ✓ `/gsd-phase edit 60` ran — Phase 60 ROADMAP entry rewritten to reflect the merged scope (goal + 6 SC). No further `/gsd-phase` action required before `/gsd-plan-phase 60`.
- The original plan to add Phase 60.1 (voting) and Phase 60.2 (search/submit) is **retired** — those scopes merged into Phase 60. No new ROADMAP entries needed for them.

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

- **New menu actions:** `main_window.py:131-138` — insert `act_gbs_add = self._menu.addAction("Add GBS.FM"); act_gbs_add.triggered.connect(self._on_gbs_add_clicked)` between `act_import` and the `addSeparator()` at line 140. Add a sibling `act_gbs_search = self._menu.addAction("Search GBS.FM…"); act_gbs_search.triggered.connect(self._open_gbs_search_dialog)` (D-08a) — placement planner's call. `_on_gbs_add_clicked` modeled on `_open_import_dialog` but kicking `gbs_api.import_station(self._repo, on_progress=...)` and toasting on completion. `_open_gbs_search_dialog` modeled on `_open_discovery_dialog` exactly.
- **New AccountsDialog group:** `accounts_dialog.py:91-115` → insert `_gbs_box` between `_youtube_box` and the Twitch group. Update `accounts_dialog.py:137-138` layout ordering. Status reflects whether the chosen auth credential (D-04) is set.
- **New module `musicstreamer/gbs_api.py`** (or `gbs_import.py`) — public API per D-03 (foundation + active-playlist + vote + search + submit). Pure `urllib`, no SDK.
- **New dialog `musicstreamer/ui_qt/gbs_search_dialog.py`** (D-08) — search GBS.FM catalog + submit selected song. Modeled on `discovery_dialog.py` shape.
- **New widgets on `NowPlayingPanel`:**
  - **Active-playlist widget (D-06):** new `QListWidget` (or equivalent) attribute `_gbs_playlist_list` (or similar) added to the panel layout. Populated by a new `_refresh_gbs_playlist()` method called from `bind_station(station)` when the station is GBS.FM, plus a `QTimer` for periodic refresh (D-06a). Hidden when the station is non-GBS.FM.
  - **Vote control (D-07):** new `_gbs_vote_btn` (or pair of buttons) added to the panel layout near the existing star/pause/stop/stream-picker row. Hidden when the station is non-GBS.FM or the user is logged out. Auth state observed via the same mechanism AccountsDialog uses (`_repo.get_setting("gbs_auth_token", "")` or whichever D-04 picks).
- **New paths helper** if D-04 picks ladder #2 or #3 — `paths.gbs_token_path()` or `paths.gbs_cookies_path()`.
- **No schema changes.** `station_streams.bitrate_kbps` already migrated (Phase 47.2 D-02). `settings` table reuses for any DB-stored auth value (mirror AA `audioaddict_listen_key`).
- **Logo download path:** `~/.local/share/musicstreamer/assets/gbs-fm-logo.png` (or whatever `assets.copy_asset_for_station` returns). Existing path; no new directory.
- **Toast surface:** `MainWindow._toast(...)` (existing) or whatever the import flows use today. Planner mirrors `aa_import` toast precedent. Used by: import success/refresh, vote success/error (D-07), submit success/error (D-08d).
- **Worker thread for API calls:** vote (D-07a) and submit (D-08) must NOT block the UI thread. Use `QThread` + `QObject.moveToThread` pattern OR `QtConcurrent.run` OR a `concurrent.futures.ThreadPoolExecutor` — match whatever pattern `cover_art.py` uses today (`CoverArtWorker` thread is the existing precedent).

</code_context>

<specifics>
## Specific Ideas

- **The user's framing reset twice.** First during discuss-phase: literal "browse + save + play" is already possible via manual "New Station"; real value is API integration. Second during `/gsd-phase edit 60`: voting and search/submit shouldn't be deferred to follow-on phases — they ship in Phase 60 alongside the foundation, plus active-playlist viewing. CONTEXT.md and ROADMAP both updated 2026-05-03 to reflect the merged scope.
- **GBS.FM is a single station, not a network or directory.** This collapses the "import flow tab" / "discovery tab" decision tree entirely for the *import* surface — no checklist, no per-channel API loop. The "Add GBS.FM" hamburger entry is a single action. The *search* surface (D-08) is a different shape: the user searches GBS.FM's track catalog (not station catalog) to submit a song to the playlist queue.
- **The cookies file is a research artifact, not a v1 user-facing auth surface.** User drops it at `~/.local/share/musicstreamer/dev-fixtures/gbs-cookies.txt` (outside repo) so the researcher can map the GBS.FM API. The user-facing auth UX is whichever of D-04's ladder the planner picks based on findings.
- **AA-pattern-mirroring is the single biggest implementation lever for the import path.** Phase 47.x already locked the multi-stream data shape; `aa_import.import_stations_multi` already locked the orchestrator shape; `stream_ordering.order_streams` already locked the play-time consumer. Phase 60's import path produces output that flows in unchanged.
- **Phase 64 is the closest precedent for the active-playlist + vote surfaces.** Phase 64's "Also on:" line is a hide-when-empty conditional widget on `NowPlayingPanel` that only renders for AA stations with siblings; D-06 active playlist + D-07 vote control follow the same hide-when-empty contract for non-GBS.FM stations and (for vote) logged-out users. Read `64-CONTEXT.md` D-01 / D-04 / D-05 / D-05a before planning the panel changes.
- **DiscoveryDialog is the closest precedent for the search-and-submit dialog.** Same search-box + results-list shape; just a different action button.
- **Phase 60 IS the feature, not just the foundation.** This is a re-framing from the original CONTEXT.md draft: voting, active playlist, and search/submit are the user-visible value; the API client, multi-quality import, and AccountsDialog auth are the plumbing that makes them work. Frame the phase value accordingly when writing PR descriptions / verification reports.
- **No breaking changes.** No schema migrations, no playback path changes, no AccountsDialog reorganization (insertion only). All net-additive surface area.

</specifics>

<deferred>
## Deferred Ideas

### Later milestone or backlog (lower ROI per user — confirmed deferred)

- **Per-song comments.** SEED-008 "nice-to-have." Comment thread view per currently-playing-track; reply / submit / read. Sizable UI work + API surface.
- **Discord ↔ IRC chat mirror.** SEED-008 highest-complexity nice-to-have. Two transport layers (Discord WebSocket / IRC TCP) + bidirectional message bridging + UI for chat history. SEED-008: "drop chat first if scope shrinks."
- **Song upload.** SEED-008 nice-to-have. File picker + multi-MB upload over HTTP + GBS.FM-side metadata mapping + post-upload status.

### Scope boundary edges to revisit if user feedback says otherwise

- **First-launch nudge for "Add GBS.FM."** Currently rejected (D-02c). If discoverability turns out to be poor, a one-time toast or empty-state hint can be added without breaking anything.
- **Per-station-quality manual override.** Today `stream_ordering` picks; user can manually switch via the stream picker. If GBS.FM users want to "always prefer 256kbps mp3," that's a future polish phase touching the existing stream picker UX.
- **Click-to-favorite from the active playlist widget (D-06c).** Phase 60 keeps favoriting on the existing star button only. If Kyle wants per-row favorite toggles in the active playlist, future phase.
- **Sticky vote state across track replays.** If GBS.FM rotates a song that the user already voted on (within the same session), should the vote button restore that state? Phase 60 keeps the vote button in whatever state `fetch_active_playlist` reports (D-07d). If GBS.FM doesn't expose user-vote state, the button always starts neutral on track change. A future phase could add a local cache.
- **Multi-station search-and-submit.** Phase 60's search dialog targets GBS.FM specifically. If MusicStreamer ever integrates with another station's submit API (Twitch chat song requests? a different community station?), generalizing the dialog is a future phase.

### Historical context (informational only)

- The original CONTEXT.md draft (committed `ea9e69b`) split this work into Phase 60 (foundation) + Phase 60.1 (voting) + Phase 60.2 (search/submit). The user reversed the split via `/gsd-phase edit 60` (2026-05-03), merging all three into Phase 60. `60-DISCUSSION-LOG.md` preserves the original split rationale for audit purposes; CONTEXT.md (this file) reflects the final merged scope.


</deferred>

---

*Phase: 60-gbs-fm-integration*
*Context gathered: 2026-05-03*
