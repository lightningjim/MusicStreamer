# Phase 89: YouTube Channel-Avatar Fetch + Cover-Slot Swap - Context

**Gathered:** 2026-06-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver the YouTube channel-avatar feature end to end: `yt_import.fetch_channel_avatar()` to fetch a square avatar, thread the Phase 89a `channel_avatar_path` column through the read/write layer, auto-fetch on URL paste in `EditStationDialog` (with a manual "Refresh avatar" button), and swap the now-playing cover slot to a **circular-cropped** channel avatar for ICY-disabled YouTube stations — falling back cleanly to today's station-thumbnail behavior when no avatar exists. Cover-resolver precedence stays `ICY → iTunes → MB-CAA → channel-avatar → placeholder`; the avatar fallback fires ONLY when ICY is empty/disabled and never short-circuits Phase 73 MB-CAA coverage.

Delivers ART-AVATAR-03, ART-AVATAR-05, ART-AVATAR-06, ART-AVATAR-07, ART-AVATAR-08, ART-AVATAR-09, ART-AVATAR-10.

**Out of scope:** Twitch Helix avatar fetch (Phase 89b — registers into the per-provider hook this phase establishes).

</domain>

<decisions>
## Implementation Decisions

### Fetch timing & dialog feedback *(discussed)*
- **D-01:** Avatar auto-fetches on **debounced URL paste/edit** in `EditStationDialog` (**500ms** after the URL field settles — RESEARCH.md Q7 verified the live `_url_timer.setInterval(500)` at L361; the earlier "~600ms" estimate is superseded), matching the Phase 6/17 YT-thumbnail auto-fetch precedent. Not on Save/OK, not on every keystroke. Satisfies ART-AVATAR-05's "auto-fetch on paste".
- **D-02:** The dialog shows an **inline avatar thumbnail preview + a brief status line** ("Fetching avatar…" → "Avatar found"). Reuse the existing worker-thread + queued-`Signal` marshalling pattern from `now_playing_panel` (`cover_art_ready` precedent) — fetch on a worker thread, marshal the result to the Qt main thread; never block the UI.
- **D-03:** On fetch failure (network error, no avatar found, non-YouTube URL), show a **non-blocking inline message** ("No avatar found — cover will use the station thumbnail"). **Save is always allowed** — the column stays NULL and the cover slot falls back. Failure never blocks the core edit flow.
- **D-04:** **YT-gated now, structured for reuse.** The avatar fetch/preview/refresh UI activates only when the URL is detected as YouTube in this phase, but the fetch dispatch is written as a **per-provider hook/registry** so Phase 89b adds Twitch by registering its fetcher — zero rework of the dialog or cover-slot. Honors the phase boundary while keeping 89b cheap.

### Circular-crop rendering *(discussed)*
- **D-05:** The circular crop applies to a **separate avatar render path ONLY**. Real covers (`_set_cover_pixmap`, iTunes/MB-CAA) and the station-thumbnail-in-cover fallback (`_show_station_logo_in_cover_slot`) keep their existing square `KeepAspectRatio` + `SmoothTransformation` render. Do NOT alter Phase 72.3 cover behavior — add a distinct avatar render method that clips to a circle.
- **D-06:** No border/ring — render a clean circular crop with a **smooth antialiased edge** (QPainter antialiasing). Matches the app's flat cover rendering.
- **D-07 (Claude's discretion):** Exact circle diameter vs. padding within the square slot — full-bleed (touch edges) vs. slight inset. Pick whatever looks balanced against the adjacent square covers; the user deferred this. Center-crop the source to square before clipping to the circle.

### Empty / failure fallback *(discussed)*
- **D-08:** For an ICY-disabled YouTube station with **no usable avatar** (fetch failed or none stored), the cover slot reverts to **exactly today's behavior** — `_show_station_logo_in_cover_slot()` (the station thumbnail). No generic-placeholder asset, no behavior regression. The avatar is purely additive when present. Satisfies ART-AVATAR-08's "reverts to current behavior".
- **D-09:** During the brief load window on station-bind, show the **station thumbnail immediately, then swap to the circular avatar** once the cached PNG loads. No flicker-to-blank; if the avatar load fails the thumbnail simply stays. (The cached avatar is a local PNG read via `QPixmap`, so load is effectively instant and stays inside the ART-AVATAR-08 <1s budget.)

### "Refresh avatar" affordance *(discussed)*
- **D-10:** The "Refresh avatar" button is **enabled only for avatar-capable (detected-YouTube) URLs** this phase; disabled/hidden otherwise. 89b's Twitch detection enables it for Twitch via the same per-provider hook (D-04).
- **D-11:** A refresh click runs the **same async worker fetch path** as auto-fetch (D-01/D-02): brief "Refreshing…" state, preview updates to the new avatar on success, and on failure the **old cached avatar is kept** with an inline "refresh failed" note. Non-blocking.
- **D-12:** Successful re-fetch (e.g., after a channel rebrand) **overwrites the cached PNG atomically** — write to a temp file then atomic-rename over `assets/channel-avatars/<station-id>.png`. Same flat path (89a D-03), column value unchanged, no orphaned files, no partial-file corruption. Follow any existing atomic-write convention in `assets.py` if present.

### Column plumbing (locked by 89a D-06 — now in scope, not re-discussed)
- **D-13:** Phase 89 threads `channel_avatar_path` through the `Station` dataclass (`models.py`), the row→`Station` mappers, and `save_station()` (`repo.py`) — the wiring 89a deliberately deferred. Store the column value as a path **relative to `data_dir()`** (e.g. `assets/channel-avatars/12.png`), mirroring `station_art_path`. Use `paths.channel_avatars_dir()` (89a D-02) for all path construction — no hardcoded path strings.

### Precedence & drift-guards (locked by requirements — not discussed)
- **D-14:** Cover-resolver source order stays `ICY → iTunes → MB-CAA → channel-avatar → placeholder` (ART-AVATAR-07). The channel-avatar fallback fires ONLY when ICY is empty/disabled and never short-circuits MB-CAA. Source-grep drift-guard `test_cover_resolution_precedence::test_mb_caa_runs_before_channel_avatar` must confirm `_mb_caa_lookup` appears before `_channel_avatar_lookup` in source (ART-AVATAR-09). The named `_mb_caa_lookup` / `_channel_avatar_lookup` functions must live in the same source file so the grep gate is meaningful — **researcher to confirm exact placement** relative to the current `cover_art.py` `fetch_cover_art` dispatch.
- **D-15:** Phase 71 sibling-render parity preserved — add drift-guard `test_richtext_baseline_unchanged_by_phase_89` mirroring the existing Phase 71 baseline test (ART-AVATAR-10).

### Claude's Discretion
- Exact circle diameter/inset (D-07).
- Debounce interval (≈600ms suggested — match the Phase 6/17 thumbnail precedent).
- Inline status/preview widget layout within `EditStationDialog`.
- Whether the avatar render path needs its own `_last_avatar_path`-style tracked state so `_apply_art_tier` re-renders the circular avatar correctly on panel resize (see Integration Points) — adopt the pattern that mirrors `_last_cover_path`.

</decisions>

<specifics>
## Specific Ideas

- Channel avatars are write-once-then-cached: YouTube avatars change ~never; the model is one-time fetch + manual refresh, NOT per-play (REQUIREMENTS.md anti-goal table line ~141).
- Circular crop is the visual identity for avatars specifically — square stays the language for real album covers and station thumbnails (D-05).
- Reuse, don't reinvent: the worker-thread + queued-`Signal` fetch/marshal pattern already proven in `now_playing_panel` is the template for both the dialog fetch and the refresh.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §ART-AVATAR (lines ~79-86) — ART-AVATAR-03 (`fetch_channel_avatar` field filter: `id == 'avatar_uncropped'`|`'avatar'`, reject `width != height`), 05 (auto-fetch on paste + Refresh button), 06 (circular crop in cover slot when ICY disabled), 07 (precedence `ICY → iTunes → MB-CAA → channel-avatar → placeholder`), 08 (<1s cached load + clean fallback), 09 (source-grep drift-guard), 10 (Phase 71 sibling parity drift-guard). Anti-goal table (lines ~140-141): avatar goes ONLY in cover slot, never logo slot; no per-play refresh.

### Roadmap
- `.planning/ROADMAP.md` §"Phase 89: YouTube Channel-Avatar Fetch + Cover-Slot Swap" — Goal, Depends-on (89a + Phase 87 cookie-persistence pattern), and the 5 Success Criteria (square-avatar field filter; circular swap + clean fallback; precedence drift-guard; Phase 71 parity; Refresh button + auto-fetch UX). Research flag: YES.

### Foundation (89a — consumed by this phase)
- `.planning/phases/89A-channel-avatar-db-migration-storage-layout/89A-CONTEXT.md` — D-02 (`paths.channel_avatars_dir()` accessor), D-03 (flat `assets/channel-avatars/<station-id>.png`, column stores path relative to `data_dir()`), D-06 (column plumbing through `Station`/mappers/`save_station()` DEFERRED to Phase 89 — now D-13 here).

### Code precedent (read before implementing)
- `musicstreamer/yt_import.py` — existing yt-dlp usage (`scan_playlist`, `import_stations`); add `fetch_channel_avatar(channel_url) -> bytes` here following the same yt-dlp info-extraction style.
- `musicstreamer/cover_art.py` §`fetch_cover_art` (~L147+) — current source-aware precedence dispatch (iTunes via `_itunes_attempt`, MB via `_cover_art_mb.fetch_mb_cover`). The new `_mb_caa_lookup` / `_channel_avatar_lookup` named functions + the avatar tier integrate relative to this (D-14 — researcher to confirm placement).
- `musicstreamer/cover_art_mb.py` — MB-CAA lookup (`fetch_mb_cover`) — the tier the avatar must sit AFTER.
- `musicstreamer/ui_qt/now_playing_panel.py` — cover slot: `_on_cover_art_ready` (~L2126, token-guarded queued slot), `_set_cover_pixmap` (~L2150, real-cover render + `_last_cover_path` tracking), `_show_station_logo_in_cover_slot` (thumbnail fallback), `_apply_art_tier` (~L2043, resize re-render — branches on `_last_cover_path`), `bind_station` `icy_disabled` handling (~L887). The `cover_art_ready` Signal + `_fetch_cover_art_async` worker pattern (~L2160) is the template for the dialog fetch.
- `musicstreamer/ui_qt/edit_station_dialog.py` — `cover_art_source_combo` (~L412) shows where avatar UI (preview, status, Refresh button) and the debounced URL-change handler attach; existing URL field is the auto-fetch trigger.
- `musicstreamer/paths.py` — `channel_avatars_dir()` accessor (89a) for all avatar path construction; `_root_override` test convention.
- `musicstreamer/repo.py` — `db_init()` already has the `channel_avatar_path` column (89a); thread it through the row→`Station` mappers (~L565, 604, 713, 828) and `save_station()` (~L626) following the `cover_art_source` precedent (Phase 73 keyword-default arg pattern).
- `musicstreamer/models.py` §`Station` dataclass — add `channel_avatar_path: Optional[str]` mirroring `station_art_path` / `cover_art_source`.
- `musicstreamer/assets.py` — `ensure_dirs()` (dir exists from 89a) and any atomic-write helper for D-12 PNG overwrite.

### Spike findings
- `Skill("spike-findings-musicstreamer")` — load for yt-dlp / Qt threading / GStreamer bus-handler patterns referenced by the ROADMAP pitfalls (avatar field stability, cover-slot threading).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `now_playing_panel._fetch_cover_art_async` + `cover_art_ready` Signal (queued, token-guarded) — the worker-thread/marshal template for both the dialog auto-fetch (D-02) and the manual refresh (D-11).
- `now_playing_panel._set_cover_pixmap` / `_last_cover_path` / `_apply_art_tier` — the cover-slot render + tier-replay machinery; the circular-avatar path mirrors this with its own tracked state (D-07/discretion).
- `repo.save_station()` keyword-default-arg pattern (Phase 73 `cover_art_source`) — the template for adding `channel_avatar_path` to the write boundary (D-13).
- `paths.channel_avatars_dir()` (89a) — single source of truth for avatar paths.

### Established Patterns
- **Worker-thread + queued Signal:** all network/blocking fetches run off the Qt main thread and marshal results back via a queued-connection Signal; slots never raise (WR-04 contract).
- **Stale-response token guard:** `_cover_fetch_token` discards out-of-order async responses — apply the same to debounced/refresh avatar fetches so a fast-typing user doesn't get a stale avatar.
- **Tier-change replay:** `_apply_art_tier` re-renders on resize by branching on tracked state; any new avatar render path must participate so the circle re-renders at the new tier.
- **Source-grep drift-guards over behavioral mocks** (`feedback_gstreamer_mock_blind_spot.md`): precedence/ordering enforced by grepping source, not mocking (D-14/D-15).
- **Path-relative-to-`data_dir()` column values + `_root_override` test isolation** (89a).

### Integration Points
- `yt_import.py` — new `fetch_channel_avatar()`.
- `cover_art.py` — new `_mb_caa_lookup` / `_channel_avatar_lookup` named functions; avatar tier wired after MB-CAA (D-14).
- `now_playing_panel.py` — new circular-avatar render path + bind-time avatar load for ICY-disabled stations; transient thumbnail→avatar swap (D-08/D-09); `_apply_art_tier` participation.
- `edit_station_dialog.py` — debounced URL-change handler, inline preview + status, "Refresh avatar" button gated to avatar-capable URLs (D-01/D-02/D-10/D-11).
- `models.py` / `repo.py` — thread `channel_avatar_path` (D-13).
- `assets.py` — atomic PNG overwrite for refresh (D-12).

</code_context>

<deferred>
## Deferred Ideas

- **Twitch Helix `profile_image_url` fetch** — Phase 89b (ART-AVATAR-04). Registers into the per-provider fetch hook established here (D-04); reuses the cover-slot circular-crop path and 89a storage. Zero new UI code expected.
- Channel-avatar in the **logo** slot — explicitly rejected by REQUIREMENTS.md anti-goal: avatar goes ONLY in the cover slot.
- Per-play avatar refresh — explicitly rejected: one-time fetch + manual refresh only.

</deferred>

---

*Phase: 89-youtube-channel-avatar-fetch-cover-slot-swap*
*Context gathered: 2026-06-15*
