---
phase: 74
phase_name: "SomaFM Full Station Catalog + Art"
project: "MusicStreamer"
generated: "2026-05-14"
counts:
  decisions: 6
  lessons: 7
  patterns: 5
  surprises: 5
missing_artifacts: []
---

# Phase 74 Learnings: SomaFM Full Station Catalog + Art

Phase 74 added a bulk SomaFM importer (46 channels × 4 quality tiers × 5 ICE relays = ~920 stream rows + 46 logos) wired into a hamburger-menu action with toast-driven UX. The phase shipped in two cycles: Phase 74.0 (Plans 01–04, completed before this session) and Phase 74.1 gap closure (Plans 05–07, this session) that closed two BLOCKERs surfaced by live UAT.

## Decisions

### URL-slug bitrate parser as source of truth (D-G02 resolution)
On gap closure for G-02, the bitrate stored per stream is derived from the relay URL slug (`-NNN-mp3` / `-NNN-aac` / `-NNN-aacp`) via a `re.compile(r"-(\d+)-(?:mp3|aac|aacp)\b")` parser. The `_TIER_BY_FORMAT_QUALITY` table default (128 kbps for mp3/highest) is preserved as a fallback for unparseable URLs, but it is no longer authoritative.

**Rationale:** SomaFM publishes 128/192/256 kbps as the "highest" MP3 tier per channel; the bitrate is encoded in the URL slug and is the only correct source. The earlier hardcoded table value corrupted hi-res sort and tier quality labels for Synphaera, Groove Salad, and similar channels. Three alternative sources (channel `playlists[]` JSON, icy-headers via per-relay GET, hardcoded per-channel map) were considered in REVIEW.md CR-01; the URL-slug parser was selected as the cheapest correct option and reused verbatim.

**Source:** 74-REVIEW.md (CR-01), 74-05-PLAN.md, 74-05-SUMMARY.md

---

### 4-tier × 5-relay = 20 streams per channel
Every imported SomaFM channel produces exactly 20 `station_streams` rows: 4 quality tiers (highest, high, mid, low across mp3/aacp combinations) × 5 ICE relays (`ice2..ice6.somafm.com`). Stream `position` = `tier_base * 10 + relay_index`.

**Rationale:** Mirrors the existing AudioAddict + GBS.FM importer model where each station carries all available relays so playback can fail over without re-fetching the catalog. Confirmed via live UAT-10 in Phase 74.0 (20 streams per channel observed) and re-confirmed by UAT-F01-RETEST in 74-07.

**Source:** 74-02-PLAN.md, 74-CONTEXT.md (D-15), 74-VERIFICATION.md (SOMA-02, SOMA-03)

---

### Manual re-import only — no auto-import on app start (D-04)
The "Import SomaFM" action lives in the hamburger menu and only runs when the user clicks it. There is no startup hook, no background refresh, no schedule.

**Rationale:** SomaFM channel list changes rarely. Auto-import would burn bandwidth and risk silent data corruption if the upstream catalog ever shifts schema. Manual gives the user a clear "I asked for this" model and aligns with the AudioAddict + GBS.FM precedent.

**Source:** 74-CONTEXT.md (D-04), 74-04-PLAN.md, 74-04-UAT-LOG.md

---

### 4-class signal-rename: each worker gets a domain-named signal (G-01 resolution)
Resolving G-01 renamed `finished = Signal(...)` on four `QThread` subclasses to distinct domain-named signals: `_ExportWorker.export_finished`, `_ImportPreviewWorker.preview_finished`, `_GbsImportWorker.import_finished`, `_SomaImportWorker.import_finished`. All 4 emit sites and 4 connect sites updated to match.

**Rationale:** `QThread.finished` is a reserved no-arg C++ signal that Qt auto-emits at thread exit. Declaring a class-level `finished = Signal(int, int)` shadows it; the auto-emitted no-arg dispatch arrives at the slot expecting 2 ints, raises `TypeError` inside Qt's event dispatcher, and is silently swallowed. The latent bug existed on 3 other workers but only manifested for SomaFM because GBS / export / import-preview are rarely re-invoked. Fix-once-fix-all closed the family.

**Source:** 74-REVIEW.md (CR-02 / WR-04), 74-VERIFICATION.md (G-01 frontmatter), 74-06-PLAN.md, 74-06-SUMMARY.md

---

### Live UAT is mandatory — automated suite cannot prove G-01 / G-02
Phase 74's automated test bar is high (31/31 tests pass against mocked urlopen + offscreen Qt) but G-01 and G-02 both shipped past it. Closure requires source-grep gates + live UAT against `api.somafm.com` and the live PySide6 platform plugin.

**Rationale:** Mocked `urlopen` returns whatever the test stubs return — including the wrong (128) bitrate without contradiction. Qt offscreen platform does not dispatch the auto-emitted `QThread::finished()` no-arg signal the way the user's live X11/Wayland platform does. Both blind spots are documented in project memory and re-confirmed during this gap-closure cycle.

**Source:** 74-VERIFICATION.md (Behavioral Spot-Checks + Re-verification), 74-07-UAT-LOG.md (3/3 PASS), feedback-gstreamer-mock-blind-spot memory (sibling pattern)

---

### Parallel worktree execution with zero file overlap is safe in this codebase
Plans 74-05 and 74-06 ran in parallel `worktree-agent-*` isolation with no merge conflicts because `files_modified` had zero intersection (74-05 touched `soma_import.py` + `test_soma_import.py`; 74-06 touched `main_window.py` + `test_main_window_soma.py`). Post-merge tests (31/31) passed without integration fixups.

**Rationale:** GSD's intra-wave overlap detection caught the disjoint sets; the planner deliberately split the two gap closures by module boundary. Future gap-closure cycles can use the same heuristic: if `files_modified` is disjoint, parallelize.

**Source:** 74-05-PLAN.md (frontmatter), 74-06-PLAN.md (frontmatter), workflow execute-phase.md intra-wave overlap check

---

## Lessons

### `QThread.finished` is reserved — `Signal` subclass attrs must never shadow it
In PySide6, `QThread` exposes a no-arg C++ signal `finished` that is auto-emitted when the thread's `run()` returns. Declaring `finished = Signal(int, int)` (or any other arity) on a subclass shadows the inherited signal; the C++ auto-emit collides with the Python slot's expected signature and silently fails inside Qt's event dispatcher. No exception bubbles to Python. No log line. The toast just never appears.

**Context:** Caused UAT-07 failure in Phase 74.0; root cause hidden because `test_import_soma_done_zero_inserted_emits_no_changes_toast` passed by calling the slot directly (bypassing the live thread-exit signal flow). Confirmed via direct verification on PySide6 6.x; same trapdoor exists in PyQt5.

**Source:** 74-VERIFICATION.md (G-01 frontmatter root cause), 74-REVIEW.md (CR-02, WR-04), 74-06-SUMMARY.md

---

### `qtbot` + offscreen Qt platform doesn't reproduce `QThread.finished` shadowing
A qtbot regression test using `qtbot.waitSignal(worker.import_finished)` + a real `worker.start()` call PASSED against the unrenamed shadowing code under the headless offscreen Qt platform plugin. The plugin's event-loop dispatch differs from X11/Wayland in a way that lets the slot run despite the signature mismatch.

**Context:** Discovered during Plan 74-06 execution when the executor ran its own RED test against pre-fix code and it failed to go RED. Documented at length in 74-06-SUMMARY.md and added to feedback-gstreamer-mock-blind-spot memory as a sibling pattern. The strict regression net is the source-grep gates (`^\s+finished\s*=\s*Signal` returns 0) plus live UAT.

**Source:** 74-06-SUMMARY.md, feedback-gstreamer-mock-blind-spot memory

---

### SQLite `PRAGMA foreign_keys` is per-connection and the app doesn't set it
The `station_streams.station_id` foreign key declares `ON DELETE CASCADE`, but `PRAGMA foreign_keys` returns `0` in `sqlite3` interactive sessions against the live DB. SQLite requires this PRAGMA to be set PER CONNECTION; without it, the schema's CASCADE is silently a no-op. Every `DELETE FROM stations` in the app leaks orphaned `station_streams` rows.

**Context:** Manifested during 74-07 UAT-F01-RETEST cleanup. The orchestrator-run `DELETE FROM stations WHERE name LIKE '%Synphaera%'` removed the station row but left 20 orphaned stream rows; dedup-by-URL in the next import matched those orphans and short-circuited the channel as "no changes". Required a manual `DELETE FROM station_streams WHERE url LIKE '%synphaera%'`. This is a latent bug in `db_connect()` (or wherever the SQLite connection is opened) — it should set `PRAGMA foreign_keys = ON` immediately after connecting.

**Source:** 74-07-UAT-LOG.md (F-07-03 finding), reference-musicstreamer-db-schema memory

---

### `provider_name` doesn't exist on `stations` — every "show by provider" query needs a JOIN
The `stations` table carries only `provider_id INTEGER` (FK to `providers.id`); the `provider_name` attribute on `Station` Python objects is computed via JOIN at SELECT time. Queries that emit `WHERE provider_name='SomaFM'` against the `stations` table will fail with "no such column".

**Context:** Caught in commit `e960008` during Phase 74.0 UAT-04 — the original planner-generated UAT SQL used `WHERE provider_name='SomaFM'` directly against `stations`. Fixed by switching to `SELECT count(*) FROM stations s JOIN providers p ON s.provider_id=p.id WHERE p.name='SomaFM'`. Now captured in project memory.

**Source:** 74-04-UAT-LOG.md (Pre-test schema note), reference-musicstreamer-db-schema memory

---

### Dedup-by-URL happens AFTER PLS resolution — re-import is not cheap
`import_stations` short-circuits a whole channel if `any(stream.url exists in DB)` — but only AFTER `fetch_channels` has already done the channel-list fetch (~50 KB) AND 4 sequential PLS GETs × 46 channels = 184 HTTP requests. Re-import wall-clock is ~20 seconds even when zero rows are inserted.

**Context:** Observed during 74-07 UAT-07-RETEST. User saw ~20 sec between the "Import SomaFM" click and the "no changes" toast; D-08 had targeted 5 sec but that was for the original import. Re-import pays the same network cost minus the DB writes. Possible perf fix: short-circuit at channel level via a stable channel identifier (e.g. `image_url` or channel slug) before running `_resolve_pls`.

**Source:** 74-07-UAT-LOG.md (F-07-01 finding), 74-07-SUMMARY.md

---

### Mirror-pattern with verbatim citation prevents re-derivation drift
Plan 74-05 reused REVIEW.md CR-01's `_bitrate_from_url` reference implementation verbatim, including the exact regex `r"-(\d+)-(?:mp3|aac|aacp)\b"`. This was a deliberate choice over re-deriving the regex from the SomaFM URL spec, aligned with project memory rule "Mirror X decisions must cite source".

**Context:** Phase 70 burned a full phase by paraphrasing a moOde rule instead of citing the source. Project memory `feedback-mirror-decisions-cite-source` records the lesson. 74-05 obeyed it: the regex and helper signature came from CR-01's code block, not a re-derived spec; the plan acceptance criteria explicitly referenced CR-01 as the source-of-truth file.

**Source:** 74-05-PLAN.md, 74-05-SUMMARY.md, feedback-mirror-decisions-cite-source memory

---

## Patterns

### Worker-signal naming: `{action}_finished = Signal(...)` per QThread subclass
Each `QThread` subclass that emits a completion signal MUST use a domain-named signal: `export_finished`, `preview_finished`, `import_finished`, etc. — never bare `finished`. Connect sites use the same domain name.

**When to use:** Every new `QThread` subclass in `ui_qt/main_window.py` (or anywhere PySide6 `QThread` is subclassed). Apply during code review even before the bug surfaces. The naming convention is now enforced by a source-grep gate (see next pattern).

**Source:** 74-06-PLAN.md, 74-06-SUMMARY.md

---

### Source-grep regression gate: ban `^\s+finished\s*=\s*Signal` across the codebase
A post-fix verification gate checks `grep -E '^\s+finished\s*=\s*Signal' musicstreamer/ui_qt/main_window.py` returns 0 matches. Any future PR that reintroduces a `finished = Signal(...)` class attribute fails this gate.

**When to use:** As a standing CI / pre-merge check for any module that subclasses `QThread`. The pattern generalizes: for any reserved-name bug (Qt, GStreamer, etc.), pin the ban with a source-level grep gate at the file/directory boundary. Extends the Phase 70 playbin3 grep-ban pattern to thread-affinity bugs.

**Source:** 74-VERIFICATION.md (Behavioral Spot-Checks), 74-06-SUMMARY.md, feedback-gstreamer-mock-blind-spot memory

---

### URL-slug-as-source-of-truth for stream metadata
When a remote API encodes structured metadata in a URL slug (e.g. `-256-mp3`, `-aacp`, `-flac`), parse the slug at ingest time rather than relying on table defaults or per-channel hardcoded maps. Keep the table default as a fallback only.

**When to use:** Any importer that maps remote URLs into local stream rows. Applies to AudioAddict, GBS.FM, future Radio-Browser.info, etc. The `_bitrate_from_url(url, default)` helper signature is the template.

**Source:** 74-REVIEW.md (CR-01), 74-05-PLAN.md, 74-05-SUMMARY.md

---

### Three-plan gap-closure shape: backend fix || UI fix → consolidated UAT
Gap-closure cycles split cleanly into "backend code fix" + "UI / thread fix" running in parallel (zero file overlap) followed by one consolidated UAT plan that re-verifies both gaps in a single user walkthrough. Skip per-gap UAT plans — fold both into one UAT log.

**When to use:** Any future `/gsd-plan-phase N --gaps` with 2+ BLOCKERs scoped to disjoint modules. Reduces UAT friction by 50% (one walkthrough not two) and matches GSD's wave-based parallel-isolation contract. Phase 74.1 (Plans 05/06/07) is the template.

**Source:** 74-05-PLAN.md + 74-06-PLAN.md (parallel-safe Wave 4), 74-07-PLAN.md (consolidated UAT)

---

### Frontmatter-driven re-verification: previous_score + status flip
When re-verifying a phase, the verifier writes a new VERIFICATION.md frontmatter with `status: verified`, `score: 17/17`, `gaps: []`, `previous_score: 15/17`, `reverified: <ISO>`. The previously-FAILED truth rows flip to VERIFIED with citations to the closure plans + UAT-LOG. This preserves audit history without bloating the file.

**When to use:** Every `/gsd-plan-phase N --gaps` cycle ends with a verifier re-run. Use this frontmatter pattern to make the closure trail machine-readable (any future audit script can diff `previous_score` against `score`).

**Source:** 74-VERIFICATION.md (Re-verification frontmatter at commit a94ca63)

---

## Surprises

### Headless Qt didn't expose the QThread.finished shadowing bug
The most carefully-written regression test for G-01 (a live-thread qtbot test with `waitSignal`) PASSED against the bug-causing code under the offscreen Qt platform plugin. Two days of automated CI green and the bug was still present. This forced the realization that automated test coverage is necessary but not sufficient for thread-affinity / signal-dispatch bugs in Qt.

**Impact:** Memory note added to `feedback-gstreamer-mock-blind-spot` documenting Qt offscreen platform as a sibling blind spot. Future PySide6 work must layer source-grep gates + live UAT on top of qtbot tests, not rely on qtbot alone.

**Source:** 74-06-SUMMARY.md (investigation note), 74-LEARNINGS.md (this section)

---

### Foreign-key cascades are silently dead at app runtime
The schema looked correct (`FOREIGN KEY(station_id) REFERENCES stations(id) ON DELETE CASCADE`) and the code that wrote the schema worked. Nothing in any test or UAT had ever tried to delete a station before. The first time it mattered (74-07 UAT cleanup) we discovered every `DELETE FROM stations` in the entire app history has been leaking orphan stream rows.

**Impact:** Latent bug captured as F-07-03; added to `reference-musicstreamer-db-schema` memory. Sets up a new phase to fix `db_connect()` to set `PRAGMA foreign_keys = ON` and to clean up any orphans in the live DB. Suggests every CASCADE / RESTRICT constraint in the schema should be tested with an actual DELETE — the constraint declaration itself proves nothing.

**Source:** 74-07-UAT-LOG.md (F-07-03 finding)

---

### Re-import takes 4× longer than initial import target (relative to its DB-write work)
D-08 set 5 seconds as the wall-clock target for the initial bulk import (46 channels worth of network fetches + dedup-zero DB writes). Re-import does the same 184 PLS GETs but performs ZERO DB writes — yet wall-clock was ~20 seconds, 4× the initial target. Dedup short-circuits in the wrong layer.

**Impact:** F-07-01 finding; candidate for a follow-up perf phase that short-circuits at the channel level (compare channel slug or `image_url` against existing rows BEFORE running `_resolve_pls`). Non-blocking for Phase 74.

**Source:** 74-07-UAT-LOG.md (F-07-01 finding), 74-07-SUMMARY.md

---

### Toast string lied about plurality
Single-station re-imports produce the toast `"SomaFM import: 1 stations imported"`. Missing conditional pluralization. Trivial one-line fix in `_on_soma_import_done`, but it shipped through 4 plans + a code review + a verifier without being caught — the test stubs always returned counts > 1.

**Impact:** F-07-02 candidate follow-up. Useful reminder that test inputs need to span both N=1 and N>1 cases for any pluralized output.

**Source:** 74-07-UAT-LOG.md (Row 2 verbatim toast text), 74-07-SUMMARY.md

---

### Four worker classes all had the same shadowing bug — but only one had visibly manifested
Once we tracked down G-01 in `_SomaImportWorker`, source-grep showed `_GbsImportWorker`, `_ExportWorker`, and `_ImportPreviewWorker` ALL declared `finished = Signal(...)` and ALL had the same latent trapdoor. Only `_SomaImportWorker` had been exercised in a high-frequency scenario (the user re-runs SomaFM imports; GBS / export / preview are one-shots). Three latent bugs were hiding behind one visible bug.

**Impact:** Gap-closure scope expanded from "fix the SomaFM worker" to "fix all four workers" per VERIFICATION.md's `missing:` list. Reinforces the broader pattern that fixing reserved-name bugs in one class should always trigger a codebase-wide source-grep for the same pattern.

**Source:** 74-VERIFICATION.md (Anti-Patterns Found rows for 4 worker classes), 74-06-SUMMARY.md

---

### WR-06: AAC codec literal precision loss (deferred follow-up)
`_TIER_BY_FORMAT_QUALITY` (musicstreamer/soma_import.py) maps both `(aac, highest)` AND `(aacp, high)` AND `(aacp, low)` to `codec="AAC"`. The DB has no `codec_subtype` column, so the LC-AAC vs HE-AAC distinction is lost permanently at insert time. Any future UI that displays "Codec: AAC" on SomaFM 64/32 kbps tiers is misleading — those streams are HE-AAC v1/v2 (SBR / Parametric Stereo).

**Impact:** Not a runtime bug today — Phase 69 WIN-05 verified that "aacp" decodes via the `aacparse + avdec_aac` chain, so the player still routes correctly. Flagged here while the codec literal is still grep-replaceable. To flip aacp tiers to `"HE-AAC"`, first tap Phase 69 WIN-05's player codec routing (musicstreamer/player.py codec map) to confirm the new label is tolerated before changing the literal.

**Source:** 74-REVIEW.md (WR-06 codec literal "AAC" conflates LC and HE-AAC)
