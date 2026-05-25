# Phase 73: MusicBrainz album-cover lookup - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-13
**Phase:** 73-musicbrainz-album-cover-lookup-complement-itunes-with-smart
**Areas discussed:** Routing trigger, Match acceptance, Result caching, Genre on MB-only path, User-Agent contact

---

## Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Routing trigger | When MB gets called relative to iTunes | ✓ |
| Match acceptance | Confidence rule for MB hits | ✓ |
| Result caching | Whether/where to cache results | ✓ |
| Genre on MB-only path | Genre handoff for favorites flow | ✓ |

**User's choice:** All four areas selected.
**Notes:** User picked the full set — no opt-out of any gray area.

---

## Routing — when MB gets called

| Option | Description | Selected |
|--------|-------------|----------|
| Implicit fallback only | iTunes first, MB on miss; no toggle. Simplest mental model. | |
| Global toggle in hamburger menu | App-wide "Cover art source" submenu (iTunes / MB / iTunes→MB fallback). | |
| Per-station preference | Selector inside EditStationDialog; per-station override. Default iTunes→MB fallback. | ✓ |
| Race both, first valid wins | Query iTunes + MB in parallel every ICY change. Best latency, doubles rate-limit pressure. | |

**User's choice:** Per-station preference.
**Notes:** Decision is to push routing all the way to the station record rather than a global app setting. Lets users tune per-source — e.g. an indie station that gets junk from iTunes can be flipped to MB-only without affecting a top-40 station that does well on iTunes.

### Modes & default (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| 3 modes (Auto / iTunes-only / MB-only) | Auto = iTunes→MB fallback. Default Auto. Simple, covers three intents. | ✓ |
| 4 modes (add MB-first) | Adds MB-first (MB→iTunes fallback). More surface, more edge cases. | |
| 2 modes (Auto / iTunes-only) | No way to force MB-primary. Smallest surface. | |
| Boolean (MB fallback on/off, per station) | Just a checkbox. Effectively a per-station opt-out of fallback. | |

**User's choice:** 3 modes (Auto / iTunes-only / MB-only), default Auto for new and existing stations.
**Notes:** Migration backfills existing stations to `Auto`. Schema/placement details are planner's discretion.

---

## Match acceptance — when an MB result is good enough

| Option | Description | Selected |
|--------|-------------|----------|
| Require artist match; reject bare titles (score ≥ 90) | Strictest. Skip MB on bare-title ICY entirely. | |
| Require artist match; score ≥ 80 | MB's own "good match" cutoff. Still rejects bare-title ICY. | ✓ |
| Allow bare-title with high bar | Bare titles allowed at score ≥ 95 AND release-with-art guard. | |
| First result only | No score gate. Trust MB's ordering. | |

**User's choice:** Require artist match; score ≥ 80.
**Notes:** Bare-title ICY (no " - " separator) skips MB entirely — no fallback to a looser query.

### Release selection (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Prefer official album, earliest first | Filter to Official+Album, pick earliest date. Multi-step fallback chain. Closest to "canonical cover." | ✓ |
| First release with CAA art | Walk in returned order, take first with art. Lowest code, sometimes compilation art. | |
| Release-group front art | Use release-group representative front art. One HTTP call. Loses special-edition disambiguation. | |
| Prefer album, then any with art | Try Official+Album earliest, fall back to any release with CAA art on miss. | |

**User's choice:** Prefer official album, earliest first.
**Notes:** Fallback chain — Official+Album earliest → any Official → any release with CAA art.

---

## Result caching

| Option | Description | Selected |
|--------|-------------|----------|
| Persistent SQLite cache, both sources | New `cover_art_cache` table. TTL'd hits + miss cache. Speeds iTunes too. Largest scope. | |
| Persistent SQLite cache, MB only | Same shape, MB only. Keeps iTunes path stateless. | |
| In-memory session cache only | Dict keyed by ICY title, cleared on restart. Avoids disk. | |
| No caching this phase | Stateless. Rate-limit handled by token bucket / queue. | ✓ |

**User's choice:** No caching this phase.
**Notes:** Caching deferred. Rate-limit-only enforcement is on its own merits.

### Rate-limit behavior under churn (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Latest-wins queue; drop superseded | Single-slot queue: replace queued query on new ICY. In-flight continues, result dropped by token guard. | ✓ |
| FIFO queue at 1/sec, no drop | All queries queued and paced. Backlog grows on rapid skips. | |
| Skip MB if a previous MB call is in-flight | Drop new MB query if one's running. Lossy on legitimate fast changes. | |
| Hard 1-req/sec mutex, callers block | Global semaphore with sleep. Cleanest semantically, worst under churn. | |

**User's choice:** Latest-wins queue; drop superseded.
**Notes:** Max 1 in-flight + 1 queued. Token-guard at the Qt slot already discards stale results.

---

## Genre handoff on MB-source path

| Option | Description | Selected |
|--------|-------------|----------|
| Use MB tags; empty if none | Highest-vote MB tag. No silent iTunes fallback in MB-only mode. | ✓ |
| Empty string in favorites | Honest about source. User can edit later. | |
| Iceberg: query iTunes anyway for genre | Side iTunes query for genre even in MB-only mode. Two network calls. | |
| Defer — leave favorites flow untouched | Phase 73 doesn't touch favorites/genre. Regression risk in MB-only mode. | |

**User's choice:** Use MB tags; empty if none.
**Notes:** In MB-only mode, no iTunes call at all — even for genre. Honors the user's choice strictly. In Auto mode, genre source matches art source (iTunes→iTunes-genre, MB fallback→MB-tag).

---

## MB User-Agent contact

| Option | Description | Selected |
|--------|-------------|----------|
| GitHub repo URL | `https://github.com/lightningjim/MusicStreamer`. No personal email in headers. | ✓ |
| Your email address | `lightning.jim@gmail.com`. Email exposed on every request. | |
| Generic project email | Decoupled inbox. Requires existing/new address. | |

**User's choice:** GitHub repo URL (`https://github.com/lightningjim/MusicStreamer`).
**Notes:** URL confirmed against QNAP origin path (`/lightningjim/MusicStreamer.git`). User-Agent string: `MusicStreamer/<version> (https://github.com/lightningjim/MusicStreamer)` where `<version>` is read via `importlib.metadata`.

---

## Claude's Discretion

- Schema migration shape (new column on `stations` vs lookup table).
- `cover_art.py` refactor strategy (one file vs split into `cover_art_itunes.py` + `cover_art_musicbrainz.py` + router).
- CAA image-size variant choice (250 / 500 / 1200) — bias toward smallest that scales cleanly to 160×160 on DPR=1.0.
- EditStationDialog widget choice (`QComboBox` vs three radio buttons) — match dialog's existing idiom.
- Rate-gate mechanism (`time.monotonic()` floor vs `threading.Semaphore` vs single-slot queue).
- Whether to add JSON fixture tests for MB responses (recommended).

## Deferred Ideas

- **Cover-art caching** (in-memory + persistent SQLite + on-disk image cache). Future phase if 1-req/sec gate is visibly hit.
- **Global cover-art-source toggle in hamburger menu.** Per-station is enough for now.
- **Editing favorites' genre after-the-fact** when a re-encountered track resolves to a different source.
- **AudioAddict / ICY-metadata / favicon station-art fetching** (ART-04 broader scope — separate phase).
- **MB tag → genre normalization** (mapping raw MB tags to iTunes-style genre names).
- **CAA image-size as a setting** (relevant if/when HiDPI displays land).
