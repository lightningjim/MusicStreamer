# Phase 90: SomaFM Preroll Instrumentation - Context

**Gathered:** 2026-06-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire a non-destructive structured preroll event log + a prerolls re-fetch lever
through `player.py`'s SomaFM preroll path, so the user can confirm — by running
through all SomaFM stations — that the previously-reported missing-preroll
symptom (Boot Liquor) is actually resolved, and so any future recurrence is both
legible (logged) and recoverable (re-fetch). Building the *fix* for a still-broken
station is the conditional Phase 90b, not this phase.

</domain>

<verification_findings>
## Empirical Verification (2026-06-18) — the reframe driver

This phase was discussed under an explicit "is this actually resolved?" lens. Data
gathered during discussion:

- **Live SomaFM API** (`https://api.somafm.com/channels.json`): Boot Liquor has 5
  prerolls upstream; 21 of 46 channels carry non-empty prerolls.
- **Local DB** (`musicstreamer.sqlite3`): Boot Liquor now has **all 5** preroll rows
  stored (`prerolls_fetched_at` = 2026-05-24, just after the 2026-05-14
  `…pre-somafm-wipe` catalog re-import). Real `bootliquor/*.m4a` URLs present.
- **Gate logic** (`_try_next_stream`, player.py:749): `provider_name == "SomaFM"`
  + per-launch throttle reset + non-empty `prerolls` ⇒ deterministically calls
  `_start_preroll` on bind. So Boot Liquor *will* play a preroll.
- **Stuck-station scan**: ZERO stations match "upstream-has-prerolls /
  local-fetched-with-0". 14 stations are simply unfetched (`fetched_at` NULL) and
  self-heal via the existing D-13 lazy backfill on next play.

**Conclusion:** Boot Liquor is resolved at the data + logic layer. BUT — per the
user — those prerolls existed upstream the *whole time*, so the original **failure
mechanism is unknown** AND the **resolution mechanism is unknown** (the catalog
re-import is a hypothesis, not proof). Hence: verify empirically + add a recovery
lever, rather than passively harvest to discover a now-already-fixed cause.

</verification_findings>

<decisions>
## Implementation Decisions

### Phase reframe — verify + recovery lever, not diagnostic harvest
- **D-01 [informational]:** Phase 90 is a verification + hardening pass, not a 1-2 day passive
  harvest. The instrumentation existed only to find an unknown cause; the cause is
  effectively resolved but unexplained. Keep light logging (legibility) + add a
  re-fetch lever (recoverability); drop the heavy harvest/probe. (Framing decision —
  realized across all plans collectively, not a single buildable artifact.)
- **D-02 [informational]:** Original miss mechanism and resolution mechanism are both UNKNOWN and
  accepted as such. Do not speculate a fix in this phase. If the run-through
  surfaces a station that is *truly still broken* (real miss with prerolls
  present), that triggers conditional Phase 90b. (Non-action constraint — no
  buildable artifact; enforced by the absence of any speculative fix in the plans.)

### Instrumentation (light) — SOMA-PRE-01, SOMA-PRE-02
- **D-03:** Build `musicstreamer/preroll_log.py` mirroring `musicstreamer/buffer_log.py`
  (Phase 78 size-rotated structured log) writing to
  `~/.local/share/musicstreamer/preroll-events.log`. Events: `preroll_start`
  (MUST include the chosen preroll URL + station name/id), `preroll_skipped_throttle`,
  `preroll_skipped_empty`, `preroll_handoff_complete`, `preroll_error`. Wire at the
  `_try_next_stream` gate and `_on_preroll_about_to_finish` with ZERO behavior change.
- **D-04:** Add `paths.preroll_events_log_path()` mirroring `paths.buffer_events_log_path()`.
- **D-05:** Add a hamburger-menu "Open preroll log" action. **Caveat for planner:**
  there is NO existing "Open buffer-events log" menu entry to mirror — `buffer_events_log_path()`
  is only called by the log writer, never by UI. So this is net-new UI; build it with the
  `QDesktopServices.openUrl(QUrl.fromLocalFile(...))` pattern (see main_window.py:919).
  Do NOT also add a buffer-log menu entry here (separate polish; deferred).

### Selection behavior
- **D-06:** Keep `random.choice(urls)` — one preroll picked at random per bind
  (authentic SomaFM station-ID rotation). No change to selection logic. The
  `preroll_start` event recording the chosen URL is what lets the user confirm
  rotation + reachability across repeated binds (answers the "random vs first?"
  question empirically).

### Re-fetch capability (new lever — user-authorized in Phase 90)
- **D-07:** Add a manual hamburger-menu "Re-fetch SomaFM prerolls" action that
  re-runs the **synchronous import-time capture** (`soma_import.py` path the May
  re-import used) for SomaFM stations with no local prerolls, ignoring
  `prerolls_fetched_at`. An observable lever the user can pull during the run-through.
- **D-08:** ALSO add automatic staleness re-fetch: when `prerolls_fetched_at` is set
  but local rows = 0 and older than a staleness threshold, re-attempt capture —
  permanently closing the latent "fetched-with-0 never re-fetches" trap (the gate at
  player.py:759 only backfills when `prerolls_fetched_at IS NULL`).
- **D-09:** Re-fetch must reuse existing single-flight (`_backfill_in_flight`,
  T-83-10) + thread-local Repo (Pattern 4) discipline, stay off the main thread, and
  stay silent on failure (Phase 83 D-04 lineage). Prefer the synchronous
  `soma_import` capture over the title-matched lazy backfill where feasible — the
  title-match (Phase 83 Pitfall 3) is the leading suspect for the original silent miss.

### Regression safety — SOMA-PRE-05
- **D-10:** Zero behavior change to Phase 84 buffer adaptation. The Phase 84 D-11
  acceptance test (12-event harvest replay) MUST re-run clean before merge. A
  source-grep drift-guard pins `_set_uri` ordering in `_try_next_stream` after any
  stage-and-apply marker.

### Claude's Discretion
- Log rotation size/cap (mirror `buffer_log` defaults), the auto-refetch staleness
  threshold, exact event field schema, and menu action placement/labels.

</decisions>

<specifics>
## Specific Ideas

- **Proof method (user-owned):** the user will manually run through every SomaFM
  station on a fresh launch and observe what plays, cross-checking against
  `preroll-events.log`. The log's per-station decision path + chosen-URL record is
  the acceptance evidence that the issue is genuinely resolved. The instrumentation
  exists to make this run-through legible.
- The re-fetch is conceptually "expose the reliable import-time capture path on
  demand," since that path (not lazy title-matched backfill) is what reliably
  populated prerolls in May.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Preroll runtime path (instrument + drift-guard)
- `musicstreamer/player.py` — `_try_next_stream` SomaFM preroll gate (~line 749,
  `random.choice` selection + `_start_preroll` + lazy-backfill branch),
  `_on_preroll_about_to_finish` (handoff slot), `_start_preroll` (~line 1468),
  `_preroll_backfill_worker` (~line 1998). These are the decision points to log and
  the `_set_uri` ordering to pin.

### Logging template + paths
- `musicstreamer/buffer_log.py` — Phase 78 size-rotated structured log; the mirror
  template for `preroll_log.py`.
- `musicstreamer/paths.py` §`buffer_events_log_path()` (~line 68) — mirror target for
  `preroll_events_log_path()`.

### Preroll data + re-fetch path
- `musicstreamer/soma_import.py` — `fetch_channels()` (line 175), import-time preroll
  capture (lines 343-356). The synchronous capture the re-fetch lever should reuse.
- `musicstreamer/repo.py` — `station_prerolls` table (line 148), `list_prerolls`
  (516), `insert_preroll` (531), `set_prerolls_fetched_at` (781).

### UI wiring
- `musicstreamer/ui_qt/main_window.py` — hamburger menu construction + action wiring
  (~line 220+); `QDesktopServices.openUrl` pattern at line 919. Targets for the new
  "Open preroll log" + "Re-fetch SomaFM prerolls" actions.

### Phase scope + requirements
- `.planning/ROADMAP.md` — Phase 90 (lines 444-459) + conditional Phase 90b (460-470).
- `.planning/REQUIREMENTS.md` — SOMA-PRE-01..05 (lines 90-97).
- `.planning/milestones/v2.1-phases/83-at-start-of-playing-a-station-randomly-select-and-play-one-o/`
  — Phase 83 preroll feature decisions (D-01..D-04, D-11/D-12/D-13 throttle/backfill,
  Pitfall 3 title-match weak point).
- `.planning/milestones/v2.1-phases/84-bug-09-commit-b-buffer-tuning-behavior-fix-reframed-from-str/`
  — Phase 84 D-11 buffer-adaptation acceptance test (12-event harvest replay) that
  must re-run clean (SOMA-PRE-05).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `buffer_log.py` + `paths.buffer_events_log_path()`: direct template for the new
  preroll log module + path helper (size-rotation already solved).
- `soma_import.py` import-time preroll capture (lines 343-356): the reliable re-fetch
  engine — reuse rather than reinvent.
- `_backfill_in_flight` single-flight set + `_preroll_backfill_worker` thread-local
  Repo pattern: extend for the re-fetch lever's concurrency safety.

### Established Patterns
- Pattern 4 (thread-local `Repo` via `db_connect()`, never share main-thread Repo
  across threads) governs any background re-fetch.
- D-04 silent-failure lineage: preroll/backfill failures are logged-and-swallowed,
  never user-facing errors.

### Integration Points
- Hamburger menu in `main_window.py` (two net-new actions).
- Preroll gate in `_try_next_stream` (log calls + unchanged `_set_uri` order).
- `station_prerolls` table via `Repo.insert_preroll` / `set_prerolls_fetched_at`.

### Caveat / discrepancy for planner
- SOMA-PRE-02 assumes an existing "Open buffer-events log" menu entry to mirror.
  **It does not exist** — the buffer log is written but never surfaced in UI. The
  preroll "Open log" action is therefore net-new, not a mirror.

</code_context>

<deferred>
## Deferred Ideas

- **30s opt-in network probe + `preroll-probe.log`** (original SOMA-PRE-03): dropped
  from Phase 90; superseded by the manual run-through + event log. Re-surfaces in
  conditional Phase 90b only if a recurrence needs network-layer diagnosis.
- **1-2 day passive listening harvest** (original SOMA-PRE-04 harvest half): replaced
  by the deliberate all-stations run-through.
- **"Open buffer-events log" menu entry** (for consistency, since none exists): backlog
  polish, out of scope here.
- **Phase 90b (conditional fix):** fires only if the run-through + log reveal a station
  that is truly still broken (a real miss with prerolls present + populated).
- **REQUIREMENTS.md note:** the re-fetch lever (D-07/D-08) is new capability beyond
  SOMA-PRE-01..05; user explicitly authorized it in Phase 90. Consider adding
  SOMA-PRE-06 (planner/roadmap concern, not blocking).

</deferred>

---

*Phase: 90-somafm-preroll-instrumentation*
*Context gathered: 2026-06-18*
