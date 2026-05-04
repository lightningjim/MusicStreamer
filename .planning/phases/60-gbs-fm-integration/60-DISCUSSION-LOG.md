# Phase 60: GBS.FM Integration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-03
**Phase:** 60-gbs-fm-integration
**Areas discussed:** Station granularity, Surface mechanism, Authentication scope, Scope guardrail (with mid-discussion scope re-framing)

---

## Station granularity

| Option | Description | Selected |
|--------|-------------|----------|
| One station, one stream | GBS.FM is a single station with one playable stream URL (Lofi Girl shape). Saving = one row, no bulk import. | ✓ (initially) |
| One station, multi stream | One station with multiple stream variants (qualities/bitrates/codecs, Soma.FM-channel shape). One row + multiple `station_streams` rows. | ✓ (final, after re-frame) |
| Network of channels | Many sub-stations (DI.fm/JazzRadio shape). aa_import.py-style bulk import. | |
| Catalog/directory | Searchable directory of community stations (Radio-Browser shape). | |

**User's choice:** "One station, one stream" initially; flipped to "One station, multi stream" after the user clarified "importing all qualities at once would be nice" during the scope re-framing later in the discussion. The user explicitly: *"Sure, i had assumed you were meaning by multi stream as in 'GBS has mtuple channels' but that was my mistake."*
**Notes:** The flip cascaded through every other decision — once granularity was multi-stream, the surface became a multi-quality auto-import (not a single URL paste) and Phase 60's value became API integration (not just a manual add).

---

## Surface mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Hamburger menu entry | "Add GBS.FM" / "Set up GBS.FM" item in hamburger menu next to Discover/Import. One click → station appears. | ✓ |
| Discovery dialog featured | GBS.FM as featured/pinned result above Radio-Browser results in Discovery dialog. | |
| Pre-seeded on first launch | GBS.FM auto-added on first run / migration. No UI affordance. | |
| Edit station preset | "GBS.FM" preset button in EditStationDialog Add path. Pre-fills name/URL/provider/logo. | |

**User's choice:** Hamburger menu entry.
**Notes:** Idempotency, label, and click behavior were rolled into Auth and Scope discussions and locked as Claude-discretion items in CONTEXT.md (D-02 through D-02d). No first-launch nudge (D-02c).

---

## Authentication scope (model)

| Option | Description | Selected |
|--------|-------------|----------|
| No auth needed | GBS.FM is publicly accessible. No login, no API key. | |
| Account needed (cred at first add) | Login required for browse/play. Cred dialog at first add or in AccountsDialog. | |
| Optional account (degraded mode) | Public play works; logging in unlocks future features. AccountsDialog gets optional GBS.FM section. | ✓ |
| You decide | Defer to research; document dual-path. | |

**User's choice:** Optional account (degraded mode).
**Notes:** Sets up the door for SEED-008 follow-on phases (60.1 voting, 60.2 search+submit) without requiring auth in Phase 60 itself.

---

## Authentication scope (plumbing depth in Phase 60)

| Option | Description | Selected |
|--------|-------------|----------|
| Functional login now | Full GBS.FM auth flow ships in Phase 60. AccountsDialog group fully working. Token stored. | ✓ |
| Minimal stub now | AccountsDialog gets a "GBS.FM" row with placeholder button. UI slot reserved. | |
| Defer all auth | Phase 60 ships pure no-auth. AccountsDialog gets nothing. Future phase brings its own auth. | |

**User's choice:** Functional login now.
**Notes:** Meaningful scope expansion vs. literal "browse/save/play" reading — but deliberate scaffolding so 60.1/60.2 drop straight in.

---

## Authentication scope (auth flow shape)

| Option | Description | Selected |
|--------|-------------|----------|
| OAuth via subprocess WebView | Mirror Twitch flow. `oauth_helper.py --mode gbs`. Cookie/token harvested. | partial |
| API key paste field | Mirror AA listen_key. Paste field in AccountsDialog, stored in SQLite settings. | partial |
| Username/password form | AccountsDialog form. POST to login endpoint. New pattern. | partial (fallback) |
| Research decides | Defer to gsd-phase-researcher to map GBS.FM's actual auth surface; planner picks closest pattern. | ✓ (effective) |

**User's choice:** Free-text — *"There seems to be two ways but I don't have the documentation for the API. There's credentials and API. I did plan to provide a cookies file for access to review the full featured frontend."*

**Clarifying follow-up (Q1):** *"b, so we can figure out what works best"* — meaning the cookies file is a **dev fixture** for the researcher to map the API, NOT the user-facing v1 auth surface.

**Clarifying follow-up (Q2):** *"I think the credentials path is a good fall back if we determine the API doesn't give as much access as I think it would (equal level)"* — credentials-path is a fallback if the API path turns out to be more limited than expected.

**Notes:** Locked outcome is a research-gated preference ladder (D-04): API key paste → OAuth subprocess → cookies-import → username/password fallback. Researcher uses the dev cookies file at `~/.local/share/musicstreamer/dev-fixtures/gbs-cookies.txt` (D-04a, outside repo for safety) to inspect GBS.FM. Planner picks the closest existing pattern based on findings.

**Clarifying follow-up (Q3) — GBS.FM URL:** *"you have it already, the name is the URL"* → `https://gbs.fm`. Captured in `<canonical_refs>`.

**Clarifying follow-up (Q4) — dev fixture location:** User open to either `.planning/phases/60-...` or `~/.local/share/musicstreamer/dev-fixtures/`. Locked: outside-repo (D-04a) because no `.gitignore` rule for fixtures exists today and committed session cookies are hard to scrub.

---

## Scope guardrail

| Option | Description | Selected (out of scope) |
|--------|-------------|----------|
| Voting/rating tracks | GBS.FM vote-on-current-track API (SEED-008 must-have). | (initially unchecked → re-discussed) |
| Search + submit songs | Search GBS.FM catalog + submit to station playlist (SEED-008 must-have). | (initially unchecked → re-discussed) |
| Per-song comments | Comment thread per song (SEED-008 nice-to-have). | ✓ |
| Discord↔IRC chat mirror + song upload | Two highest-complexity SEED-008 nice-to-haves. | ✓ |

**User's choice:** Multi-select picked Comments and Chat+Upload as out-of-scope; Voting and Search+Submit were left unchecked (initially).

**Disambiguation (3-option follow-up):**
- (a) Multi-select slip — voting and search/submit are out alongside chat/comments.
- (b) Deliberate scope expansion — Phase 60 includes voting + search/submit (3-4× larger phase).
- (c) Split into sub-phases — Phase 60 = browse/save/play, 60.1 = voting, 60.2 = search/submit.

**User's choice (initial):** (c) — split into sub-phases.

**User's interrupt (mid-discussion):** *"OK before we move forward, what do you mean by browse, save, play? I can definitely sdave and play the radio station already since I can and have already added it as a station (though importing all qualties at once would be nice)"*

This caught a real precision problem: literal browse/save/play is already possible via the existing "New Station" path. Phase 60 needs to be re-framed.

**Re-framed Phase 60 scope (proposed and confirmed):**
- Multi-quality auto-import (one click → all GBS.FM stream qualities populated as `station_streams` rows on a single library row).
- Station logo + metadata populated.
- AccountsDialog cookies/credentials/auth groundwork.
- GBS.FM API client foundation (`gbs_api.py` or similar).
- Phase 60.1 = voting (next, future). Phase 60.2 = search/submit (after 60.1, future).
- Per-song comments / chat mirror / song upload deferred to later milestone or backlog (lower ROI).
- ROADMAP entry text needs `/gsd-phase edit 60` before planning.

**User's choice (re-framed Q5):** *"yes, this wasn't just a basic pull all streams. It was actual integration with the API; I think that was a prior miscommunication. I am OK to pass off some of the less ROI features to later"*

**User's choice (re-framed Q6 — granularity flip):** *"Sure, i had assumed you were meaning by multi stream as in 'GBS has mtuple channels' but that was my mistake."* — granularity flips to "One station, multi stream."

---

## Claude's Discretion

- Module name (`gbs_api.py` recommended; `gbs_import.py` acceptable).
- Identifier strategy for "is GBS.FM already in the library?" (URL pattern match / `provider="GBS.FM"` query / dedicated `gbs_station_id` setting key — planner picks based on what GBS.FM API exposes).
- Toast wording.
- Auth flow inner UX (locked: AccountsDialog `QGroupBox` shape; open: file-vs-DB token storage, dialog vs paste-field for input — planner decides per researcher findings on D-04 ladder).
- Whether `import_station` lives in `gbs_api.py` or in a separate `gbs_import.py`.
- `ThreadPoolExecutor` use for parallel image fetches — matches `aa_import.py` precedent if needed; probably overkill for one station.

---

## Deferred Ideas

**Phase 60.1 (next, same milestone):**
- Voting/rating the currently-playing track via GBS.FM API. Builds on Phase 60's `gbs_api` + AccountsDialog auth.

**Phase 60.2 (after 60.1, same milestone):**
- Search + submit songs to the station's playlist. New dialog + API surface.

**Later milestone or backlog:**
- Per-song comments (SEED-008 nice-to-have).
- Discord↔IRC chat mirror (SEED-008 highest-complexity; "drop chat first if scope shrinks").
- Song upload (SEED-008 nice-to-have).

**Scope edges to revisit if feedback says otherwise:**
- First-launch nudge for "Add GBS.FM" (D-02c rejection — revisit if discoverability is poor).
- Per-station-quality manual override.
- GBS.FM-specific now-playing surface (show/DJ/playlist metadata).

**Cross-phase ROADMAP edits required (D-05c):**
- `/gsd-phase edit 60` — sharpen goal text + SC #1/#3 + add an AccountsDialog SC.
- `/gsd-phase add` (after 60 lands) — Phase 60.1 (voting) and Phase 60.2 (search+submit).
