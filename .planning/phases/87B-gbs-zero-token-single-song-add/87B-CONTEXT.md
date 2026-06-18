# Phase 87b: GBS Zero-Token Single-Song Add - Context

**Gathered:** 2026-06-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver a persistent **"Add a song"** affordance in the now-playing panel for the bound GBS.FM station that lets the user add exactly one song via the GBS song-add endpoint, including the **zero-token "free song"** case when `tokens_available_count == 0`. The affordance opens the existing Phase 60.1/60.2 `GBSSearchDialog`; confirming a song submits it. UX never frames the action as "1 token."

**Reframe captured this session (changes the original roadmap scope):** the original phase scoped a *conditional* affordance that renders ONLY at `tokens==0 AND queue==0` and is hidden otherwise. The user decided adding a song is not a zero-token-only action — token-holders do it too — so the affordance becomes a **persistent button visible whenever a GBS.FM station is bound**, regardless of token count. The zero-token case is then "the same button; the server allows one free add." This **amends GBS-TOKEN-01 / ROADMAP SC#1** (drop the "hidden in all other states" gating) and makes **GBS-TOKEN-04** ("hide after add, reappear when tokens==0+queue empty") largely obsolete.

**In scope:**
- Persistent "Add a song" button in the now-playing panel, rendered whenever the bound station is GBS.FM (any token count), wired to open the existing `GBSSearchDialog`.
- A named song-add path (`gbs_api.add_song_zero_token()` per GBS-TOKEN-03) that, under the **provisional** contract, reuses the existing GET `/add/<songid>` endpoint (server-gated to one when tokens==0).
- A no-PII runtime **capture hook** that records the real `tokens==0` request/response the first time the free add is used in the wild, so the true behavior is fixture-locked after the fact.
- Server-is-truth error/limit handling: the server's `messages`-cookie text is surfaced verbatim; no local pre-gating of the one-at-a-time rule.
- Post-add UX: inline success → dialog closes → now-playing GBS playlist widget re-polls.
- Provisional fixture(s) under `tests/fixtures/gbs_zero_token/` capturing the observable `/add` shape (normal-token submit) + a placeholder for the captured zero-token response.

**Out of scope (deferred / rejected):**
- **Burning tokens to 0 to capture the real endpoint now** — user is at 48 tokens with no known path to 0; blocking the phase on this is rejected (see D-01/D-02).
- **Local pre-gating of the zero-token one-at-a-time limit** (disabled-button + tooltip) — rejected in favor of server-is-truth (D-07).
- **Token-cost framing anywhere in the affordance** — GBS-TOKEN-02 literal; the button says "Add a song" with no token wording.
- **Multi-add "stay open" dialog session UX** — considered, deferred (D-09 picked confirm→close→re-poll).
- **New search/drill-down UI** — the existing `GBSSearchDialog` is reused as-is; no new dialog.

</domain>

<decisions>
## Implementation Decisions

### Zero-token endpoint discovery (the central unknown)

- **D-01: The zero-token POST spec does NOT exist and cannot be honestly captured now.** Contrary to the ROADMAP/REQUIREMENTS framing ("endpoint observed via Phase 87 spike research"), Phase 87 explicitly scoped zero-token *out* (`87-CONTEXT.md` §domain: "Zero-token single-song add — Phase 87b owns that surface; this phase establishes only the pattern"). There is no `tests/fixtures/gbs_zero_token/` directory and no documented `tokens==0` POST behavior anywhere in `.planning/`. The user is at **48 tokens** with no known/scheduled path to 0.
- **D-02: Strategy = Provisional contract + capture-on-first-use** (mirrors Phase 87 D-04's "ship the structure now, let the data accrete" pattern). Concretely:
  1. **Assume the zero-token add reuses the existing GET `/add/<songid>` path**, server-gated to allow one submission when `tokens==0`. This is the most likely mechanism given `gbs_api.submit()` already implements `/add/<songid>` and the server already enforces token rules server-side.
  2. **Build the gating-free UI + wiring + named add path now**, against that provisional contract.
  3. **Fixture-lock what IS observable today** (the normal-token `/add` request/response shape at 48 tokens) under `tests/fixtures/gbs_zero_token/`.
  4. **Add a no-PII runtime capture hook** that records the real `tokens==0` request + response the first time the free add fires in the wild (cookies/sensitive headers scrubbed per `87-CONTEXT.md` D-18 logging discipline). The captured payload becomes the true fixture.
  5. **Emit a follow-up todo** (`resolves_phase: 87b`, condition: "first observed tokens==0 add") to confirm/adjust the contract once the real behavior is captured.
- **D-03: GBS-TOKEN-05 is relaxed during planning** from "fixture-lock the live Settings-page POST, quote don't paraphrase" to: "fixture-lock the observable `/add` shape now; the real `tokens==0` fixture is captured-and-confirmed on first live use." Plan-phase rewrites GBS-TOKEN-05 accordingly and cites this decision. The cite-source rule (`feedback_mirror_decisions_cite_source.md`) still applies to whatever we DO capture — quote it, don't paraphrase.

### Affordance UI (placement, form, visibility)

- **D-04: Persistent "Add a song" QPushButton rendered with / just below the existing GBS active-playlist widget** (`now_playing_panel.py`, the Phase 60 D-06 `_gbs_*` hide-when-empty widget cluster, ~line 689). Chosen over a banner-style row (competes with the Phase 87 announcement banner) and a controls-area button (divorced from queue/token context).
- **D-05: The button is visible whenever the bound station is GBS.FM — NOT gated on token count or queue state.** This is the session reframe. Token-holders get a now-playing entry point they lack today (currently only the hamburger "Search GBS.FM…" menu reaches the dialog). **Amends GBS-TOKEN-01 / ROADMAP SC#1**: visibility predicate is `provider_name == "GBS.FM" AND station bound`, dropping the `tokens==0 AND queue==0 ... hidden in all other states` gating.
- **D-06: Label is "Add a song"; no token wording in the button label, tooltip, or any surrounding text** (GBS-TOKEN-02 literal, now applied universally to all token states). The source-grep "no 'token' word" test targets the new button/module. The pre-existing Phase 60.4 token-count display inside `GBSSearchDialog` ("under search") is NOT part of this affordance's surrounding text and is unaffected.

### Constraint handling (the "one free song at a time" rule)

- **D-07: Server is truth — no local pre-gating.** The add hits `/add/<songid>`; on rejection the server's `messages`-cookie text is surfaced verbatim (e.g. "you already have a song queued"), exactly the existing Pitfall 8 / `gbs_api.submit()` pattern. Chosen over local pre-check (which would duplicate zero-token server rules we are only guessing at under the provisional contract) and over local-only gating (which risks blocking legitimate adds if our guess is wrong). The capture hook records the real response either way, which is how we learn the true rules.
- **D-08: GBS-TOKEN-04 is obsolete under the reframe** — the button persists, so there is no "hide affordance after add / reappear when tokens==0+queue empty" behavior. Plan-phase rewrites or retires GBS-TOKEN-04 (and adjusts ROADMAP SC#4) to reflect "button persists; post-add behavior is dialog-close + playlist re-poll."

### Add + feedback flow

- **D-09: After a successful add — confirm inline, close, re-poll.** The dialog shows the server's success message inline briefly, then closes; the now-playing GBS playlist widget immediately re-polls (`fetch_active_playlist`) so the newly-queued song appears. Chosen over stay-open (multi-add friction at tokens==0) and close-immediately-toast-only (confirmation too far from attention).
- **D-10: Reuse `GBSSearchDialog` as-is** (GBS-TOKEN-03 "opens the existing search-drill-down dialog"). The new button calls the existing `_open_gbs_search_dialog()` launch path; the dialog already does search → `submit()` → `/add` → inline messages. No new dialog, no preview-play, login-gated as today.

### Claude's Discretion
- **`add_song_zero_token()` factoring** — whether it is a thin wrapper/alias over the existing `/add` path (preferred: avoids duplicating `submit()` logic) or a distinct function; either way it satisfies GBS-TOKEN-03's named-function contract and is the natural host for the capture hook. Planner's call.
- **Capture-hook mechanics** — where the scrubbed request/response is written (fixture dir vs `buffer_log` structured line vs both), the scrubbing implementation, and the "first live use" trigger/flag. Must follow `87-CONTEXT.md` D-18: structured key=value, no PII, no cookie/session values.
- **Auth-expiry surfacing** — reuse the Phase 87.1 `gbs_relogin_handler` (`ui_qt/gbs_relogin_handler.py`) for `GbsAuthExpiredError` from the add path; exact wiring is the planner's call.
- **Worker-thread vs inline submit** — the existing dialog already runs submit on a worker; keep that shape (`aa_live.py` precedent). Re-poll trigger plumbing is discretion.
- **Button enabled-state while a request is in flight** (debounce/disable) — discretion; mirror existing dialog submit-button behavior.

</decisions>

<specifics>
## Specific Ideas

- **"Adding a song isn't a zero-token-only action."** The user's pivotal insight — token-holders add songs too, so the same button should serve everyone and just behave differently at the server based on token state. This collapsed the original "conditional zero-token affordance" into "persistent Add-a-song button that also works at zero tokens," simplifying the tokens>0 path to a second launch point for the already-built dialog.
- **48 tokens, no path to 0.** The hard logistics constraint that forced the provisional/capture-on-use strategy. We physically cannot watch the `tokens==0` POST today, so we refuse to block the phase on it and instead instrument to capture it the first time it happens for real.
- **Mirror Phase 87's "structure now, data later."** The user has already accepted this pattern once (themed-day hash baseline, Phase 87 D-04). Reusing it here keeps the project's decision style consistent.
- **Server is truth.** Consistent with the whole GBS integration lineage (Phase 60 Pitfall 8 — the `messages` cookie text is the source of truth for quota/duplicate/limit feedback). We don't reimplement gbs.fm's rules client-side, especially rules we're guessing at.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements (PLAN-PHASE MUST EDIT THESE)
- `.planning/ROADMAP.md` §"Phase 87b: GBS Zero-Token Single-Song Add" (lines ~425–440). **Plan-phase MUST amend Success Criteria** per the reframe: SC#1 (affordance always-visible when GBS bound, not tokens==0+queue gated — D-05), SC#3 (endpoint is provisional `/add` reuse — D-02), SC#4 (no hide-after-add; button persists + re-poll — D-08), SC#5 (provisional fixture + capture-on-use — D-03).
- `.planning/REQUIREMENTS.md` §"GBS.FM — Zero-Token Single-Song Add (GBS-TOKEN)" (lines ~67–73). **Plan-phase MUST rewrite**: GBS-TOKEN-01 (always-visible — D-05), GBS-TOKEN-04 (obsolete/persist — D-08), GBS-TOKEN-05 (provisional + capture-on-use — D-03). GBS-TOKEN-02 (no "token" wording) and GBS-TOKEN-03 (opens existing dialog + named add function) stand as-is.
- `.planning/PROJECT.md` §Current Milestone v2.2 — "zero-token single-song add (UX never framed as '1 token')" is the milestone anchor for this phase.

### CRITICAL prior context (READ FIRST)
- `.planning/phases/87-gbs-fm-marquee-themed-day-detection/87-CONTEXT.md` — Phase 87 LOCKED the GBS auth/session reuse path (D-07: cookies-jar via `gbs_api.load_auth_context()` + `_open_with_cookies`; NO `QWebEngineProfile`). Also D-04 (ship-structure-now pattern this phase mirrors) and D-18 (quiet structured WARN, no-PII logging the capture hook must follow).
- `.planning/milestones/v2.1-phases/76-gbs-fm-authentication-support-both-pre-existing-api-token-an/76-CONTEXT.md` §D-04/D-06 — Django sessionid+csrftoken cookies at `paths.gbs_cookies_path()` (0o600). The auth model every GBS call uses.
- `.planning/milestones/v2.1-phases/60.4-two-informationals-1-under-search-show-the-amount-of-tokens-/60.4-01-PLAN.md` + `60.4-VALIDATION.md` — `fetch_user_tokens()` (token-count source + parser); the "0 tokens" variant test already exists.

### Closest existing patterns (this phase reuses)
- `musicstreamer/gbs_api.py:1129` — `submit(songid, cookies)` → GET `/add/<songid>`, intercepts 302, decodes `messages` cookie, raises `GbsAuthExpiredError` on 302→login. **The provisional zero-token path reuses this** (D-02); `add_song_zero_token()` likely wraps it.
- `musicstreamer/gbs_api.py:365` — `fetch_user_tokens(cookies)` → token count (Phase 60.4). Drives token-state awareness if needed.
- `musicstreamer/gbs_api.py:298` — `fetch_active_playlist(cookies, cursor)` → state dict incl. `queue_rows` (global upcoming queue). Source for the post-add re-poll (D-09).
- `musicstreamer/gbs_api.py:82-87` — `GbsApiError` / `GbsAuthExpiredError`. The add path raises/propagates these.
- `musicstreamer/ui_qt/gbs_search_dialog.py` — `GBSSearchDialog` (Phase 60.1/60.2 D-08). Reused as-is (D-10); already worker-threaded, login-gated, Pitfall-8 inline messages.
- `musicstreamer/ui_qt/main_window.py:237-238, 1542-1552` — hamburger "Search GBS.FM…" action + `_open_gbs_search_dialog()`. The new button reuses this launch path.
- `musicstreamer/ui_qt/now_playing_panel.py:~689` — GBS active-playlist widget cluster (Phase 60 D-06, hide-when-empty). Button placement anchor (D-04); `_GbsPlaylistWorker` / `playlist_ready` re-poll wiring lives here.
- `musicstreamer/ui_qt/gbs_relogin_handler.py` — Phase 87.1 shared auth-expiry surface; reused for the add path.
- `musicstreamer/buffer_log.py` — structured WARN/no-PII logging surface for the capture hook + quiet failures.
- `musicstreamer/aa_live.py` — worker-thread urllib + Qt-queued-signal precedent.

### Project conventions & feedback rules
- `.planning/codebase/CONVENTIONS.md` — snake_case, type hints, `Qt.TextFormat.PlainText` for QLabel, bound-method signal connections, urllib-only HTTP, 0o600 for sensitive files.
- `memory/feedback_mirror_decisions_cite_source.md` — quote source behavior verbatim; applies to whatever the capture hook records (D-03).

### Fixtures (to be created)
- `tests/fixtures/gbs_zero_token/` (NEW) — provisional `/add` request/response shape captured at 48 tokens now; real `tokens==0` payload appended on first live use (D-02/D-03).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`gbs_api.submit(songid, cookies)`** — the existing `/add/<songid>` path; provisional host for the zero-token add (server-gated).
- **`gbs_api.fetch_active_playlist()` → `queue_rows`** — post-add re-poll source (D-09).
- **`gbs_api.fetch_user_tokens()`** — token-count read (Phase 60.4), if token-state awareness is needed.
- **`GBSSearchDialog` + `_open_gbs_search_dialog()`** — the entire search→submit→inline-message flow, reused as-is.
- **`_GbsPlaylistWorker` / `playlist_ready` signal** (`now_playing_panel.py`) — worker-thread poll + Qt-queued result delivery to re-poll the playlist widget after an add.
- **`gbs_relogin_handler` (Phase 87.1)** — auth-expiry surfacing.
- **`buffer_log.py`** — structured, no-PII logging for the capture hook.
- **`load_auth_context()` / `_open_with_cookies()` / `paths.gbs_cookies_path()`** — the Phase 76 auth model all GBS requests share.

### Established Patterns
- **Server is truth for GBS quota/limit feedback** — `messages` cookie text surfaced verbatim (Phase 60 Pitfall 8). This phase extends it to the zero-token limit (D-07).
- **"Structure now, data accretes later"** — Phase 87 D-04 (themed-day hash baseline). This phase reuses it for the endpoint fixture (D-02/D-03).
- **Worker-thread urllib + Qt-queued signals** — codebase-wide (`aa_live.py`, the existing GBS workers).
- **Hide-when-empty GBS widgets** in `now_playing_panel.py` (Phase 60 D-06) — the button anchors here, though it is shown-when-GBS-bound rather than hide-when-empty.
- **Source-grep drift-guards for "forbidden word/construct"** — Phase 87 D-05/D-07 precedent; reused for the GBS-TOKEN-02 "no 'token' word" test on the new button module.

### Integration Points
- **`musicstreamer/ui_qt/now_playing_panel.py`** — add the "Add a song" button to the GBS widget cluster; wire visibility to GBS-bound state; wire post-add re-poll.
- **`musicstreamer/ui_qt/main_window.py`** — may host the button-click → dialog launch wiring (reusing `_open_gbs_search_dialog()`), and signal plumbing for re-poll.
- **`musicstreamer/gbs_api.py`** — add `add_song_zero_token()` (thin wrapper over `/add` + capture hook) per GBS-TOKEN-03.
- **`musicstreamer/ui_qt/gbs_search_dialog.py`** — minimal/no change (reused as-is); possibly emit a "submitted" signal the panel listens to for the re-poll, if not already present.
- **`tests/fixtures/gbs_zero_token/` (NEW)** + **`tests/test_gbs_*` ** — provisional fixture, the no-"token"-word source-grep test, and a unit test for `add_song_zero_token()` against the provisional fixture.
- **`.planning/REQUIREMENTS.md` / `.planning/ROADMAP.md`** — plan-phase amends GBS-TOKEN-01/04/05 + ROADMAP SC#1/#3/#4/#5 per D-03/D-05/D-08.

</code_context>

<deferred>
## Deferred Ideas

- **Capture-and-confirm the true `tokens==0` endpoint** — happens automatically on first live use via the capture hook (D-02); a follow-up todo (`resolves_phase: 87b`) tracks confirming/adjusting the provisional contract once real data lands. Not a blocker for shipping the UI.
- **Local pre-gating / disabled-button + tooltip at the one-at-a-time limit** — considered, rejected for server-is-truth (D-07). Revisit only if doomed requests prove annoying in practice.
- **Multi-add "stay open" dialog session** — considered, rejected (D-09 picked confirm→close→re-poll). Revisit if the user wants rapid multi-add with tokens.
- **Surfacing token cost for token-holders in the affordance** — out of scope by GBS-TOKEN-02 (no token framing). The Phase 60.4 in-dialog token count already informs token-holders; no new token messaging on the button.

### Reviewed Todos (not folded)
- `todos/2026-05-26-test-constants-drift-soma-nn-requirements.md`, `...test-hamburger-menu-actions-pre-existing-d03.md`, `...test-media-keys-smtc-win32-fallback.md`, `...test-bump-version-json-decoder-failures.md`, `...host-env-docker-info-probe.md`, `2026-05-10-pls-codec-bitrate-url-fallback.md` — all keyword-matched the phase (generic "test/phase/tbd" tokens) but none concern the GBS zero-token add. Pre-existing test failures / unrelated work; left in their own backlogs.

</deferred>

---

*Phase: 87B-gbs-zero-token-single-song-add*
*Context gathered: 2026-06-18*
