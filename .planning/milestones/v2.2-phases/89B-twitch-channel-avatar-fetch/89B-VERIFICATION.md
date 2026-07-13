---
phase: 89B-twitch-channel-avatar-fetch
verified: 2026-06-17T00:00:00Z
status: passed
score: 16/16 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 15/15
  gaps_closed:
    - "Live Twitch avatar auto-fetch and cover-slot display (UAT #1) — now PASS after GQL fix (commit ff027cf8)"
    - "ICY-disabled now-playing cover slot shows avatar (UAT #2) — now PASS"
    - "No-token / failure fallback UX, Save always allowed (UAT #3) — now PASS"
    - "Add-path gap: NEW Twitch station fetches+persists avatar on FIRST save (89B-03, commit 29575e49)"
  gaps_remaining: []
  regressions: []
human_verification_confirmed:
  - test: "Live Twitch avatar auto-fetch and cover-slot display in EditStationDialog"
    result: pass
    note: "Re-tested 2026-06-17 after GQL fix (ff027cf8). Avatar fetches and renders circular-cropped in the cover-slot preview."
  - test: "ICY-disabled now-playing cover slot shows streamer avatar (not logo slot)"
    result: pass
    note: "Verified 2026-06-17 — cover slot shows circular avatar, left logo unchanged. Sibling-reuse sub-case N/A (Twitch is one live stream per channel by design)."
  - test: "No-token / failure fallback UX — non-blocking inline note, Save always succeeds"
    result: pass
    note: "Verified 2026-06-17 — non-blocking message, Save succeeds, cover falls back to station thumbnail. (UAT-discovered add-path defect closed via 89B-03.)"
---

# Phase 89B: Twitch Channel-Avatar Fetch — Verification Report (Re-Verification)

**Phase Goal:** ICY-disabled Twitch stations show the streamer's `profile_image_url` (circular crop) in the now-playing cover slot, sharing the Phase 89 cover-slot integration and the Phase 89a per-provider storage layout. The integration is a per-provider auto-fetch trigger only — zero new UI/render code.
**Verified:** 2026-06-17
**Status:** passed
**Re-verification:** Yes — after human-UAT confirmation (3/3 pass) and add-path gap closure (89B-03)

---

## Re-Verification Context

The initial verification (2026-06-16) was `human_needed` with 15/15 code must-haves verified and 3 live-token UAT items pending. Since then:

1. **UAT #1 surfaced a transport defect:** the Phase 32 `twitch-token.txt` (web `auth-token` cookie, client-id `kimne78…`) has NO Helix REST access — `api.twitch.tv/helix/users` returns HTTP 404 for it. CONTEXT D-06 / RESEARCH #1 wrongly assumed Bearer-framed Helix would work.
   - **Fixed (commit `ff027cf8`):** `twitch_helix.fetch_channel_avatar` rewritten to POST `gql.twitch.tv/gql` querying `user(login).profileImageURL` with `Authorization: OAuth <token>` + `Client-Id` (the streamlink credential). Login bound as a GraphQL **variable** (injection-safe). Verified live (twitchdev + lightningjim2 → valid PNGs).
2. **UAT #3 surfaced an add-path defect:** a NEW Twitch station did not fetch the avatar on FIRST save (only on re-edit), because `self._station.provider_id` was `None` on add and the debounced fetch's Pitfall-7 guard skipped it.
   - **Fixed (89B-03, commit `29575e49`):** in-memory provider refresh + synchronous `_maybe_fetch_avatar_sync` in `_on_save` before `accept()`.
3. **All 3 UAT items now PASS** (see `89B-HUMAN-UAT.md`, status: resolved).

This re-verification re-checked the ACTUAL current code (GQL path, add-path helper) — not the stale Helix-era claims in the prior report.

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | `twitch_helix.fetch_channel_avatar(url)` fetches the channel `profileImageURL` using the Phase 32 `twitch-token.txt` token, no new OAuth scopes (ART-AVATAR-04). **Transport pivoted Helix→GQL** (UAT fix) | VERIFIED | `twitch_helix.py:126-135` builds a scoped POST `Request` to `https://gql.twitch.tv/gql` with `Authorization: OAuth <token>` + `Client-Id: kimne78…`; `test_fetch_calls_gql_with_oauth_and_client_id` asserts full URL, POST method, OAuth header, client-id, and `profileImageURL` in query — passes |
| 2 | Login parsed from a twitch.tv URL: last path segment, strip `?`/`#`, clamp to `[a-z0-9_]+`, case-fold (D-02, WR-01) | VERIFIED | `twitch_helix.py:51-76` `_parse_login()`; `test_parse_login` covers trailing slash, query, fragment, mixed-case, bare-login, `&`-injection |
| 3 | Missing/empty `twitch-token.txt` raises `RuntimeError` before any HTTP call; GQL `data.user == null` and non-2xx both raise; all failures propagate (D-07) | VERIFIED | `twitch_helix.py:109-118, 139-142`; `test_fetch_raises_on_missing_token`, `test_fetch_raises_on_empty_data`, `test_fetch_raises_on_http_error` — pass |
| 4 | No non-square guard — Twitch profile images are always square (D-05) | VERIFIED | `twitch_helix.py` has no `width != height` guard; query requests `profileImageURL(width:300)`; source-grep guard confirms |
| 5 | Token never logged; `Authorization` scoped to the GQL `Request` object only, NOT the CDN image download (T-89b-01) | VERIFIED | `twitch_helix.py:146` CDN download uses plain `urlopen(image_url, ...)` with no headers; module docstring + test guards confirm |
| 6 | `register_avatar_fetcher('twitch', twitch_helix.fetch_channel_avatar)` wired; `get_avatar_fetcher('twitch')` returns it at module load (D-05) | VERIFIED | `yt_import.py:290-291` late import + registration; live check `get_avatar_fetcher('twitch') is twitch_helix.fetch_channel_avatar` → True |
| 7 | A twitch.tv URL enables the Refresh-avatar button and triggers debounced auto-fetch, like a YouTube URL (D-08) | VERIFIED | `edit_station_dialog.py` `is_twitch = "twitch.tv" in lower`; `test_twitch_url_enables_refresh_btn` passes |
| 8 | `_AvatarFetchWorker.run()` dispatches through `get_avatar_fetcher()` by URL sniff; `node_runtime` only for YouTube (D-08, Pitfall 1) | VERIFIED | `edit_station_dialog.py:169-192`; `test_avatar_worker_dispatches_twitch`, `test_youtube_dispatch_passes_node_runtime` pass |
| 9 | Twitch fetch branch carries the same `provider_id is None` guard + reuse-on-open skip as YouTube (Pitfall 7) | VERIFIED | `edit_station_dialog.py:1331` single Pitfall-7 guard (untouched, not duplicated); reuse gate at 1338-1342 |
| 10 | On save, blank Provider + twitch.tv URL → login derived, `repo.ensure_provider('Twitch: <login>')` sets `provider_id`; user-typed Provider NEVER overwritten (D-02/03/04) | VERIFIED | `edit_station_dialog.py:1699-1706` blank-only `if not provider_name:` guard; `test_save_derives_provider_for_blank_twitch`, `test_save_preserves_manual_provider_for_twitch` pass |
| 11 | All Twitch fetch failures fall back non-blocking; Save always allowed; no-token status points to Accounts (D-07) | VERIFIED | `_AvatarFetchWorker.run()` except-emit-"" backstop; `RuntimeError("No Twitch login — connect via Accounts to fetch avatar")`; add-path helper swallows + sets inline status |
| 12 | Stored avatar renders through unchanged `cover_art` / `now_playing_panel` provider-keyed path — no renderer edits (D-11) | VERIFIED | No commits to `cover_art.py` / `now_playing_panel.py` in phase; UAT #2 confirms cover-slot render |
| 13 | Avatar bytes stored per-provider as `assets/channel-avatars/{provider_id}.png` via `write_provider_avatar(provider_id, data)` + `update_provider_avatar_path(provider_id, path)` — never per-station (D-01) | VERIFIED | `_AvatarFetchWorker.run():188` + add-path helper `:1842-1843` both key on `provider_id` |
| 14 | No staleness TTL or per-bind/per-play refetch — avatar fetched once when provider has none; updated only via Refresh (D-09) | VERIFIED | reuse-on-open skip; no TTL or poll; `_force_avatar_refresh` only via Refresh button |
| 15 | Refresh re-fetches and overwrites single `{provider_id}.png`; 89.1 shared-effect hint reused, no Twitch divergence (D-10) | VERIFIED | `_on_refresh_avatar_clicked` (unchanged) sets `_force_avatar_refresh` then calls debounce; single `write_provider_avatar` overwrite |
| 16 | **(89B-03)** Adding a NEW Twitch station fetches + persists the avatar on the FIRST save (no re-edit); in-memory `provider_id`/`provider_name` refreshed after `ensure_provider`; existing-provider-with-avatar add does NOT refetch (D-07) | VERIFIED | `edit_station_dialog.py:1714-1715` in-memory refresh; `_maybe_fetch_avatar_sync` `:1806-1851` synchronous fetch-before-accept honoring D-07 reuse gate; `test_save_add_path_fetches_avatar`, `test_save_add_path_refreshes_in_memory_provider`, `test_save_existing_provider_with_avatar_no_refetch`, `test_save_fetch_failure_is_nonblocking`, `test_on_save_has_inmemory_provider_assignment` — all pass |

**Score:** 16/16 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/twitch_helix.py` | `fetch_channel_avatar(url) -> bytes` via GQL; login parse helper | VERIFIED | 147 lines; GQL POST with OAuth framing; parameterized query (injection-safe); CDN download unauthenticated |
| `musicstreamer/ui_qt/edit_station_dialog.py` | Registry dispatch + provider derivation + **add-path sync fetch** | VERIFIED | `_maybe_fetch_avatar_sync` + in-memory provider refresh in `_on_save`; Pitfall-7 (1331) and D-04 (1699) guards untouched |
| `tests/test_twitch_helix.py` | Unit tests, GQL request shape, login parse, error raises, registry | VERIFIED | All pass; tests aligned to GQL (assert `OAuth` framing, `gql.twitch.tv/gql`, parameterized query) |
| `tests/test_edit_station_dialog_avatar.py` | twitch.tv enables Refresh; worker dispatch picks twitch fetcher | VERIFIED | Passes |
| `tests/test_twitch_provider_assign.py` | Provider derivation + **add-path coverage** | VERIFIED | 13 tests incl. 6 new add-path tests; all pass |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `yt_import.py` | `twitch_helix.fetch_channel_avatar` | `register_avatar_fetcher("twitch", ...)` | WIRED | live `is` check → True |
| `twitch_helix.py` | `paths.twitch_token_path` | token read | WIRED | `twitch_helix.py:110` |
| `_AvatarFetchWorker.run` | `get_avatar_fetcher` | registry dispatch by URL sniff | WIRED | `edit_station_dialog.py:181` |
| `_on_save` | `repo.ensure_provider` | `Twitch: <login>` on blank provider | WIRED | `edit_station_dialog.py:1706`, blank-only guard 1699 |
| `_on_save` → `_maybe_fetch_avatar_sync` | `assets.write_provider_avatar` / `repo.update_provider_avatar_path` | synchronous add-path persist before accept() | WIRED | `edit_station_dialog.py:1842-1843`; in-memory provider refresh 1714-1715 |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| twitch_helix + dialog-avatar + provider-assign | `.venv/bin/python -m pytest tests/test_twitch_helix.py tests/test_edit_station_dialog_avatar.py tests/test_twitch_provider_assign.py -q` | 21 passed | PASS |
| Edit-station regression | `.venv/bin/python -m pytest tests/test_edit_station_dialog.py -q` | 96 passed (2 benign warnings, no failures) | PASS |
| Registry wiring live check | `.venv/bin/python -c "...get_avatar_fetcher('twitch') is fetch_channel_avatar"` | OK | PASS |
| No debt markers in phase-modified files | grep TBD/FIXME/XXX/HACK on twitch_helix.py + edit_station_dialog.py | none | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| ART-AVATAR-04 | 89B-01/02/03 | Fetch the Twitch channel profile image using the Phase 32 `twitch-token.txt` token, no new OAuth scopes | SATISFIED | Implemented; REQUIREMENTS.md `[x]` / Phase 89b Complete. NOTE: REQUIREMENTS.md line 80 still names the Helix endpoint; the implementation pivoted to GQL (same token, same goal, same `profile_image_url`) because Helix 404s for this token class. Functional intent met; this is documentation-wording drift, not a functional gap. |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No TBD/FIXME/XXX/HACK markers in phase-modified files | — | None |
| — | — | No stubs in production files | — | None |

Note: `test_avatar_worker_shutdown_no_crash` emits a `RuntimeWarning: Failed to disconnect` — pre-existing test-harness artifact, not introduced by this phase.

---

### Human Verification — CONFIRMED (3/3 pass)

All three live-token items from the initial verification have been manually executed by the user on 2026-06-17 and recorded as PASS in `89B-HUMAN-UAT.md` (status: resolved):

1. **Live Twitch avatar auto-fetch + cover-slot display** — PASS (after GQL fix `ff027cf8`).
2. **ICY-disabled now-playing cover slot shows avatar** — PASS (cover slot circular avatar, logo slot unchanged).
3. **No-token / failure fallback UX, Save always succeeds** — PASS (non-blocking inline note, cover falls back to thumbnail).

---

### Addendum — 89B-03 Add-Path Gap Closure

UAT test #3 surfaced an out-of-band add-path defect: a NEW Twitch station resolved its avatar only on re-edit, not on first save. Root cause: `self._station.provider_id` was `None` on add (placeholder station), so the debounced fetch's Pitfall-7 guard (line 1331) skipped it; `_on_save` derived `provider_id` but never refreshed it in-memory nor fetched before `accept()`.

Closed by 89B-03 (commit `29575e49`):
- In-memory provider refresh (`self._station.provider_id`/`provider_name`) after `ensure_provider` (line 1714-1715), for both derived-Twitch and manual-provider cases.
- New synchronous `_maybe_fetch_avatar_sync(url, provider_id)` (line 1806-1851) called before `accept()`: mirrors `_AvatarFetchWorker.run()` inline (async would be torn down by `_shutdown_avatar_fetch_worker()` before persisting); honors the D-07 reuse gate; non-blocking on failure.
- D-04 blank-provider guard (1699) and the single Pitfall-7 guard (1331) confirmed untouched and not duplicated.
- 6 new add-path tests (RED→GREEN TDD); 21-test scoped sweep + 96-test edit-station regression all green.

---

### Gaps Summary

No gaps. All 16 must-haves VERIFIED in the actual codebase. The 3 live-token UAT items are confirmed PASS by the user. The UAT-discovered Helix-404 transport defect and the add-path first-save defect are both fixed and covered by tests.

---

_Verified: 2026-06-17 (re-verification)_
_Verifier: Claude (gsd-verifier)_
