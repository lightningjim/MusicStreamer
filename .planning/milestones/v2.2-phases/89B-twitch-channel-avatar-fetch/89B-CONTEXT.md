# Phase 89b: Twitch Channel-Avatar Fetch - Context

**Gathered:** 2026-06-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Register a **Twitch** avatar fetcher into the per-provider hook established by Phase 89
(`yt_import.register_avatar_fetcher`) so that a Twitch station's streamer profile image is
fetched from the Helix `/users` endpoint, stored under the **Phase 89.1 per-provider storage
layout** (`assets/channel-avatars/{provider_id}.png` + `providers.avatar_path`), and rendered
in the now-playing cover slot via the **existing Phase 89 circular-crop swap** for ICY-disabled
Twitch stations. The integration is a per-provider auto-fetch trigger only — **zero new dialog
or cover-slot code** (Phase 89 D-04). Delivers ART-AVATAR-04.

**Out of scope (their own phases):** provider brand-avatar fallback (Phase 89c, ART-AVATAR-11/12);
any change to the YouTube fetch path, the circular-crop renderer, or the 89.1 storage/dedup model
(this phase consumes them unchanged).

**Roadmap correction:** Phase 89b's success criteria predate Phase 89.1 and say store to
`<station-id>.png`. That is **superseded** — 89.1 re-keyed all channel avatars to
`{provider_id}.png` and deprecated the per-station column. 89b follows the per-provider model.

</domain>

<decisions>
## Implementation Decisions

### Avatar key & provider derivation *(discussed)*
- **D-01:** **Avatar is keyed per-provider (89.1 model), NOT per-station.** The Twitch avatar is
  stored as `assets/channel-avatars/{provider_id}.png` via the existing
  `assets.write_provider_avatar(provider_id, data)` and persisted with
  `repo.update_provider_avatar_path(provider_id, path)` (89.1 D-09/D-10). The roadmap's
  `<station-id>.png` wording is superseded.
- **D-02:** **Provider is derived from the Twitch login.** On a detected `twitch.tv` URL, parse the
  login (the last path segment, case-folded — same derivation `player.py:_twitch_resolve_worker`
  already uses: `url.rstrip("/").split("/")[-1]`) and `ensure_provider("Twitch: <login>")`, then
  set the station's `provider_id`. This gives Twitch stations a stable per-streamer dedup anchor so
  sibling stations of the same streamer share one fetch and one file (mirrors the YouTube
  provider-IS-the-channel identity).
- **D-03:** **Provider name = `"Twitch: <login>"`** (namespaced stable handle). `providers.name` is
  the SINGLE string used for both the public station-tree label and the avatar dedup key (via
  `ensure_provider` name lookup). The lowercase **login** is chosen over Helix `display_name`
  because it survives display-name rebrands — using `display_name` would mint a new provider row on
  rebrand, breaking dedup and orphaning the old avatar. The `"Twitch: "` prefix disambiguates from a
  same-named YouTube channel provider in the tree.
- **D-04:** **Only auto-assign the provider when the station's Provider field is blank.** If the user
  already typed a Provider in `EditStationDialog`, respect it and key the avatar on that existing
  `provider_id` — never silently overwrite a manual provider choice. Login-derivation + assignment
  fires only for the blank-provider case (the common one for manually-added Twitch stations).

### Helix fetch & authentication *(discussed)*
- **D-05:** **Fetch via Helix `/users`.** `musicstreamer/twitch_helix.py` exposes
  `fetch_channel_avatar(twitch_url_or_login) -> bytes`: derive the login, call
  `GET https://api.twitch.tv/helix/users?login=<login>`, read `data[0].profile_image_url`, and
  download those bytes. Registered at module load via
  `yt_import.register_avatar_fetcher("twitch", twitch_helix.fetch_channel_avatar)` (the stub comment
  already at `yt_import.py:266`). Twitch profile images are square (300×300) — no non-square guard
  needed (unlike YouTube's `width != height` reject in `fetch_channel_avatar`).
- **D-06:** **Reuse the existing Phase 32 token; no new OAuth scopes.** The `auth-token` value in
  `twitch-token.txt` (harvested cookie — see `oauth_helper.py` header) is sent to Helix as
  `Authorization: Bearer <auth-token>` paired with `Client-Id: kimne78kx3ncx6brgo4mv6wki5h1ko`
  (Twitch's public web SPA client-id). **Note the framing differs from streamlink:**
  `player.py:_twitch_resolve_worker` sends the same token as `Authorization: OAuth <token>` for the
  GQL plugin; Helix requires `Bearer` + a `Client-Id` header. Same secret, different transport.
- **D-07:** **All failure modes fall back non-blocking to the station thumbnail** (Phase 89
  D-03/D-08). No token (user never logged into Twitch) / Helix 401 (expired cookie) / empty `data`
  array (login not found) / network error → the fetch is a no-op, the column/provider avatar stays
  unset, and the cover slot uses today's behavior. **Save is always allowed.** A failed fetch in
  `EditStationDialog` shows a non-blocking inline note; consider a hint pointing to the Accounts
  dialog to (re)connect Twitch when the cause is a missing/expired token.

### Fetch trigger & refresh cadence *(discussed)*
- **D-08:** **Reuse the Phase 89 / 89.1 fetch trigger unchanged.** Debounced auto-fetch when a
  `twitch.tv` URL is detected in `EditStationDialog`; **reuse-on-open** (skip the network fetch when
  the provider already has an avatar — 89.1 D-07); manual **"Refresh avatar"** button. The Twitch
  fetcher plugs into the existing `_AvatarFetchWorker` / registry path — no new dialog widgets.
- **D-09:** **Manual Refresh only — no staleness TTL, no per-bind/per-play refetch.** One fetch when
  the provider has no avatar, then cached indefinitely; the user clicks Refresh to update after a
  streamer changes their picture. Honors the REQUIREMENTS anti-goal (no per-play refresh) and the
  Helix rate-limit budget (success criterion #3).
- **D-10:** **Refresh is shared-effect, surfaced via the existing 89.1 D-08 hint.** Because the
  avatar is per-provider (one streamer login), Refresh overwrites the single `{provider_id}.png` and
  every sibling Twitch station of that streamer updates. Reuse the existing shared-effect
  tooltip/status text — no Twitch-specific divergence.

### Rendering & precedence (locked by Phase 89 / 89.1 — not re-discussed)
- **D-11:** Cover-slot swap, circular-crop render, and the ICY-disabled trigger are **unchanged** —
  89b adds no UI/render code. `now_playing_panel.bind_station` already resolves the avatar via
  `station.provider_id` → `providers.avatar_path` (89.1 D-05); a stored Twitch avatar flows through
  that path automatically. `cover_art._channel_avatar_lookup`'s never-raises / no-thread contract
  (WR-04 / Pitfall 7) is preserved.

### Claude's Discretion
- Exact `twitch_helix.fetch_channel_avatar` signature (accept a URL and parse, vs. accept a login) —
  match the registry's `Callable[[str], bytes]` shape and the YouTube fetcher's style.
- Request timeout / error-class handling inside `twitch_helix.py` (mirror `yt_import` urlopen
  timeout and the WR-01 daemon-worker backstop discipline).
- Exact wording/placement of the no-token "connect Twitch" hint (D-07).
- Whether to add a tiny login-parse helper or inline the `split("/")[-1]` derivation (D-02).

</decisions>

<specifics>
## Specific Ideas

- The dedup target mirrors 89.1's Lofi Girl case: multiple Twitch streams of the **same streamer**
  (e.g. a main + a backup station for one login) produce exactly **one** Helix fetch and **one**
  cached file.
- Reuse, don't reinvent: the Twitch fetcher is a thin `twitch_helix.py` module behind the existing
  registry hook. The dialog, cover slot, storage writer, persist method, and circular renderer all
  already exist from Phases 89 / 89.1.
- The token is the **same** `twitch-token.txt` streamlink already uses for playback — 89b only
  changes the Authorization framing (`Bearer` + `Client-Id`) for the Helix REST endpoint.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` §ART-AVATAR (lines ~75–86) — **ART-AVATAR-04** (Twitch Helix
  `profile_image_url` fetch). Anti-goal table: avatar goes ONLY in the cover slot, never the logo
  slot; no per-play refresh.
- `.planning/ROADMAP.md` §"Phase 89b: Twitch Channel-Avatar Fetch" (lines ~366–386) — Goal,
  Depends-on (89a storage, 89 cover-slot swap), and the 3 success criteria. **Caveat:** criterion
  #1's `<station-id>.png` wording is superseded by Phase 89.1 (see D-01); read 89.1-CONTEXT for the
  current storage truth.

### Prior-phase context (the mechanism being reused — read these first)
- `.planning/phases/89-youtube-channel-avatar-fetch-cover-slot-swap/89-CONTEXT.md` — D-04 (the
  per-provider `register_avatar_fetcher` hook 89b registers into), D-02/D-03 (worker-thread fetch +
  non-blocking failure), D-05/D-06 (circular-crop render), D-08/D-09 (thumbnail fallback + transient
  swap).
- `.planning/phases/89.1-re-key-channel-avatar-from-per-station-to-per-provider-chann/89.1-CONTEXT.md`
  — **the authoritative storage/dedup model.** D-09 (`update_provider_avatar_path`), D-10
  (`{provider_id}.png` + `write_provider_avatar`), D-05 (provider-keyed resolution in
  `bind_station` / `_channel_avatar_lookup`), D-07 (reuse-on-open skip-fetch), D-08 (Refresh
  shared-effect hint).
- `.planning/phases/89A-channel-avatar-db-migration-storage-layout/89A-CONTEXT.md` — D-03 flat
  storage layout, D-12 atomic write discipline.

### Code precedent (read before implementing)
- `musicstreamer/yt_import.py` §registry (~L260–290) — `register_avatar_fetcher` / `get_avatar_fetcher`
  and the `# rework: register_avatar_fetcher("twitch", ...)` stub (L266); `fetch_channel_avatar`
  (~L240) as the fetcher-style template.
- `musicstreamer/oauth_helper.py` (header, L1–25) — explains the `twitch-token.txt` token is the
  harvested `auth-token` cookie (web client-id `kimne78kx3ncx6brgo4mv6wki5h1ko`), NOT a registered-app
  Helix Bearer token. Critical for D-06.
- `musicstreamer/player.py` §`_twitch_resolve_worker` (~L1937–1990) — existing twitch-token read
  (`paths.twitch_token_path()`), the `Authorization: OAuth` framing (Helix needs `Bearer`), the login
  derivation `url.rstrip("/").split("/")[-1]`, and the WR-01 daemon-worker error backstop pattern.
- `musicstreamer/constants.py` (~L29–47) — `TWITCH_TOKEN_PATH`, `clear_twitch_token()`.
- `musicstreamer/paths.py` §`twitch_token_path()` (~L50), `channel_avatars_dir()` (89a).
- `musicstreamer/assets.py` — `write_provider_avatar(provider_id, data)` (89.1 D-10, atomic write,
  relative-path return).
- `musicstreamer/repo.py` — `ensure_provider(name)` (~L388, the login→provider_id path for D-02),
  `update_provider_avatar_path(provider_id, path)` (89.1 D-09, non-silent-reset persist), `insert_station`
  / `save_station` provider handling (~L886).
- `musicstreamer/cover_art.py` §`_channel_avatar_lookup` (89.1 D-05, provider-keyed, WR-04 contract) —
  unchanged by 89b; verify a Twitch provider avatar resolves through it.
- `musicstreamer/ui_qt/now_playing_panel.py` §`bind_station` — provider-keyed avatar swap (89.1 D-05);
  unchanged.
- `musicstreamer/ui_qt/edit_station_dialog.py` — `_AvatarFetchWorker` (~L168), `provider_combo` (~L435),
  debounced auto-fetch + `_on_refresh_avatar_clicked` (~L502); the Twitch fetcher plugs in via the
  registry with no new widgets.

### Spike findings
- `Skill("spike-findings-musicstreamer")` — Twitch login/Kasada/Qt-threading patterns (e.g.
  helper Chromium UA notes); load before touching auth/threading details.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `yt_import.register_avatar_fetcher` / `get_avatar_fetcher` — the per-provider hook (89 D-04); 89b is
  one `register_avatar_fetcher("twitch", ...)` call plus the `twitch_helix.py` fetcher.
- `assets.write_provider_avatar(provider_id, data)` + `repo.update_provider_avatar_path(provider_id, path)`
  (89.1) — the entire storage + persist path, reused verbatim.
- `repo.ensure_provider(name)` — turns the parsed `"Twitch: <login>"` into a `provider_id` (D-02).
- `player._twitch_resolve_worker` — existing token-read + login-parse + daemon-worker error patterns to
  mirror in `twitch_helix.py`.
- `cover_art._channel_avatar_lookup` + `now_playing_panel.bind_station` — provider-keyed cover swap;
  consume unchanged.

### Established Patterns
- **Per-provider avatar key (89.1):** one fetch + one file per provider; Twitch joins by minting a
  `"Twitch: <login>"` provider for blank-provider stations.
- **Worker-thread + queued Signal fetch / non-blocking failure / Save-always-allowed (89):** the Twitch
  fetcher runs on the existing `_AvatarFetchWorker`; failures fall back to the station thumbnail.
- **Non-silent-reset persist (Pitfall 5):** avatar writes go through `update_provider_avatar_path`, not a
  broad save.
- **Token scoping (RESEARCH Pitfall 6):** scope the Twitch Authorization header to the Helix request
  only — do not set a global header.

### Integration Points
- **New** `musicstreamer/twitch_helix.py` — `fetch_channel_avatar()` (Helix `/users`, Bearer + Client-Id).
- `yt_import.py` — one `register_avatar_fetcher("twitch", ...)` line (replace the L266 stub comment).
- `repo` / dialog — login→provider derivation + blank-only assignment (D-02/D-04); reuses
  `ensure_provider` + existing save path.
- Storage / cover slot / renderer — **no change** (89.1 + 89 own these).

</code_context>

<deferred>
## Deferred Ideas

- Provider brand-avatar cover-slot fallback (SomaFM, AudioAddict) — **Phase 89c** (ART-AVATAR-11/12).
- A separate provider `display_name` column to get a pretty tree label while keying dedup on the stable
  login — rejected as schema scope creep for 89b (D-03 picks the stable login as the single name).
- Staleness TTL / background avatar refresh — rejected (D-09); manual Refresh only.
- Twitch avatar in the logo slot — rejected by the REQUIREMENTS anti-goal (cover slot only).

</deferred>

---

*Phase: 89B-twitch-channel-avatar-fetch*
*Context gathered: 2026-06-16*
