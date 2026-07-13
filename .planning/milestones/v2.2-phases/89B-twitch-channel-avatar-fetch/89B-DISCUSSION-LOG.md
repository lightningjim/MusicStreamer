# Phase 89b: Twitch Channel-Avatar Fetch - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-16
**Phase:** 89b-twitch-channel-avatar-fetch
**Areas discussed:** Avatar key / provider derivation, Helix authentication & failure handling, Refresh & rebrand cadence

---

## Avatar key (89.1 per-provider vs per-station vs per-login)

| Option | Description | Selected |
|--------|-------------|----------|
| Key by Twitch login | Ensure a provider named after the login parsed from the URL, set provider_id, store {provider_id}.png. 89.1-consistent, dedups siblings. | ✓ |
| Key by existing provider_id | Use the free-text Provider; blank → no avatar. Simplest but no avatar in the common blank case. | |
| Key by station_id | Revive per-station storage just for Twitch. Contradicts 89.1 deprecation. | |

**User's choice:** Key by Twitch login.
**Notes:** Reconciles 89b with 89.1's per-provider re-key; manually-added Twitch stations usually have provider_id = NULL, so the login provides a stable per-streamer dedup anchor.

---

## Provider name shape

| Option | Description | Selected |
|--------|-------------|----------|
| "Twitch: <login>" | Stable lowercase handle, namespaced. Survives display-name rebrands; safe dedup anchor. | ✓ |
| "Twitch: <display_name>" | Pretty branded label, but mutable — rebrand mints a new provider + orphans the avatar. | |
| Bare "<login>" | Stable/unique but collides visually with same-named YouTube providers. | |

**User's choice:** "Twitch: <login>" (after discussing the login-vs-display_name trade-off).
**Notes:** providers.name is the single string for BOTH tree label and dedup key (ensure_provider looks up by name); no separate display column without schema scope creep. Stability of the login wins over the prettier-but-mutable display_name.

---

## Existing Provider field handling

| Option | Description | Selected |
|--------|-------------|----------|
| Only auto-assign when blank | Respect a user-typed Provider; derive+assign login provider only when blank. | ✓ |
| Always derive from login | Force the login provider on any twitch.tv station, overwriting manual choices. | |

**User's choice:** Only auto-assign when blank.
**Notes:** Never silently overwrite a manual provider selection.

---

## Helix authentication & failure handling

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse cookie token + web client-id | Bearer <auth-token> + Client-Id kimne78…; non-blocking fallback to thumbnail on no-token/401/404/offline. | ✓ |
| Discuss failure UX specifics | Lock mechanics, talk through exact user-facing messaging. | |
| Defer auth detail to research/Claude | Trust the 89 failure pattern; let planner pin the header format. | |

**User's choice:** Reuse cookie token + web client-id.
**Notes:** twitch-token.txt is the harvested `auth-token` cookie (per oauth_helper header), used by streamlink as `Authorization: OAuth`. Helix `/users` needs `Authorization: Bearer` + a `Client-Id` header — same secret, different framing. No new OAuth scopes. All failure modes fall back non-blocking to the station thumbnail (Phase 89 D-03/D-08); Save always allowed; optional "connect Twitch in Accounts" hint when the cause is a missing/expired token.

---

## Refresh & rebrand cadence

| Option | Description | Selected |
|--------|-------------|----------|
| Manual Refresh only | One-time fetch + manual Refresh; no TTL, no per-bind/per-play refetch. | ✓ |
| Add a staleness TTL | Auto-refetch after an interval; contradicts "cached indefinitely" + rate-limit budget. | |

**User's choice:** Manual Refresh only.

| Option | Description | Selected |
|--------|-------------|----------|
| Same shared-effect hint as 89.1 D-08 | Reuse the existing per-provider Refresh tooltip/status; no Twitch divergence. | ✓ |
| Twitch-specific framing | Add Twitch/rebrand-specific wording. | |

**User's choice:** Same shared-effect hint as 89.1 D-08.
**Notes:** Per-provider avatar means Refresh updates every sibling Twitch station of that streamer; the existing 89.1 shared-effect hint already communicates this.

---

## Claude's Discretion

- Exact `twitch_helix.fetch_channel_avatar` signature (URL+parse vs login arg).
- Request timeout / error-class handling inside `twitch_helix.py` (mirror yt_import urlopen timeout + WR-01 backstop).
- Wording/placement of the no-token "connect Twitch" hint.
- Inline `split("/")[-1]` login derivation vs a small helper.

## Deferred Ideas

- Provider brand-avatar cover-slot fallback (SomaFM, AudioAddict) — Phase 89c (ART-AVATAR-11/12).
- Separate provider `display_name` column for a pretty label + stable key — schema scope creep, rejected.
- Staleness TTL / background refresh — rejected; manual Refresh only.
- Twitch avatar in the logo slot — rejected by REQUIREMENTS anti-goal (cover slot only).
