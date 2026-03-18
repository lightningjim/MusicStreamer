# Project Research Summary

**Project:** MusicStreamer — milestone additions
**Domain:** GNOME desktop internet radio / stream player (GTK4/Python/GStreamer)
**Researched:** 2026-03-18
**Confidence:** HIGH (stack and architecture); MEDIUM (external API specifics)

## Executive Summary

MusicStreamer is an existing GTK4/Libadwaita/Python/GStreamer internet radio app. The milestone adds three well-scoped features to a working but monolithic ~512-line codebase: live search and filter UI for the station list, ICY metadata display (track title from stream), and cover art lookup from that metadata. Each feature maps directly onto established GTK4 and GStreamer patterns — no new dependencies are needed, and all three can be implemented with the existing system bindings plus Python stdlib.

The recommended approach is to build in two sequential tracks. Track A (filtering) is entirely in-memory with no network I/O and should come first: implement `Gtk.ListBox.set_filter_func` with composed AND logic across a search entry, a provider dropdown (`Gtk.DropDown`), and a tag dropdown — all state held in a single struct, never re-querying SQLite on keystrokes. Track B (now-playing) follows: wire the GStreamer bus to receive `TAG` messages from ICY streams (the data is already flowing; it just has no listener), display the track title, then launch async iTunes Search API requests for cover art, delivering results to the UI via `GLib.idle_add`.

The primary risks are threading correctness (GTK widget updates from a cover-art worker thread will crash or corrupt state), API hammering (ICY TAG messages fire every few seconds, so cover art lookups must debounce on `(artist, title)` pair changes), and encoding edge cases (ICY streams often send Latin-1 bytes that need heuristic re-encoding). All three are well-understood and preventable with established patterns. The module structure refactor from a single `main.py` into discrete modules (`player.py`, `cover_art.py`, `ui/filter_bar.py`, etc.) is recommended to give each new component a clean home, but it can be done incrementally without a rewrite.

---

## Key Findings

### Recommended Stack

All three features are buildable entirely within the existing technology stack. No new pip dependencies are required or recommended. ICY metadata arrives via GStreamer's `icydemux` element (auto-inserted by `playbin` for ICY streams) as `Gst.MessageType.TAG` bus messages — the correct listener pattern is `bus.add_signal_watch()` + `bus.connect("message::tag", handler)`. Cover art lookup uses the iTunes Search API via `urllib.request` (stdlib), with MusicBrainz Cover Art Archive as a fallback. Filtering uses `Gtk.SearchBar`, `Gtk.SearchEntry`, `Gtk.DropDown` with `Gtk.StringList`, and `Gtk.ListBox.set_filter_func` — all stable GTK 4.0 APIs. Cross-thread dispatch for cover art uses the established `threading.Thread` + `GLib.idle_add` pattern.

**Core technologies:**
- `Gst.Bus` + `add_signal_watch()`: TAG message listener — enables ICY metadata without polling
- `urllib.request` (stdlib): cover art HTTP fetches — no added pip dependency
- `threading.Thread` + `GLib.idle_add`: async HTTP → safe UI delivery — GTK threading contract
- `Gtk.ListBox.set_filter_func` + `invalidate_filter()`: live filtering — avoids list rebuild on each keystroke
- `Gtk.DropDown` + `Gtk.StringList`: provider/tag dropdowns — correct GTK4 widget (ComboBoxText is deprecated)
- `Gtk.SearchBar` + `Gtk.SearchEntry`: search bar with toggle — standard GNOME pattern with built-in Escape handling

### Expected Features

**Must have (table stakes):**
- Live name search (filter as you type) — expected in any list-heavy GNOME app at 50+ stations
- Provider/source filter dropdown — stations are organized by provider; users think in those terms
- Genre/tag filter dropdown — tags column and edit UI already exist; users expect genre filtering
- Composed AND semantics across all three filters — partial filters that don't intersect feel broken
- Now-playing track title from ICY metadata — every radio app surfaces this; absence is a UX failure
- Visual loading/buffering state — users need feedback between clicking Play and audio starting
- Graceful error display for network/stream failures — silent failures erode trust

**Should have (differentiators):**
- Cover art from ICY metadata via external lookup — makes the app feel alive, not just utilitarian
- Animated cover art crossfade on track change — Shortwave-style polish
- Now-playing bar (distinct from header) — feels like a real music app
- Filter chips showing active filters — reduces "why am I only seeing 3 stations?" confusion
- Full keyboard navigation parity (Ctrl+F, arrow keys, Enter, Escape) — GNOME HIG expectation

**Defer (v2+):**
- Scrobbling (Last.fm/ListenBrainz) — ICY metadata plumbing is a prerequisite; build that first
- Animated cover art transition — nice but outside milestone scope
- Now-playing bar redesign — current header label is sufficient for this milestone
- Filter chips — useful but not blocking for the milestone
- In-app station discovery / RadioBrowser directory — changes the app's scope entirely
- Podcast support, equalizer, playlist/queue — out of scope per project goals

### Architecture Approach

The existing `main.py` monolith has four logical layers (domain models, repository, business logic, UI) that are not yet separated. The recommended approach is an incremental module extraction that gives each new feature a clean home: `models.py`, `repo.py`, `assets.py`, `player.py`, `cover_art.py`, and a `ui/` package containing `filter_bar.py`, `station_list.py`, `now_playing.py`, `main_window.py`, and `edit_dialog.py`. Each step is independently testable before the next begins, and the migration is additive — no rewrites, only extraction and wiring.

**Major components:**
1. `Player` — owns GStreamer pipeline and bus; emits `track_changed(artist, title)` callback; no GTK imports
2. `FilterBar` — owns filter state as a single struct; provides `matches(station) -> bool`; calls `invalidate_filter()` on the ListBox
3. `StationList` — owns `Gtk.ListBox` with `Station` objects attached to rows at build time; never rebuilds on filter changes
4. `CoverArtFetcher` — background service; queries iTunes Search API on a worker thread; delivers pixbuf via `GLib.idle_add`
5. `NowPlayingBar` — purely reactive widget; updated by `Player.track_changed` and `CoverArtFetcher` callbacks

### Critical Pitfalls

1. **GStreamer bus watch not wired** — `playbin` emits TAG messages but they are silently discarded if `bus.add_signal_watch()` and `bus.connect("message::tag", ...)` are never called. The current codebase has neither. Wire both in `__init__`, not in `_play_station`. Confirm by temporarily logging all bus message types.

2. **GTK widget updated from background thread** — cover art must be fetched off the main thread, but GTK is not thread-safe. Any widget mutation (label text, picture paintable) called from the worker thread will corrupt state or crash. All widget updates must go through `GLib.idle_add(callback, result)`, never called directly from the thread.

3. **Rebuilding the entire ListBox on every filter change** — calling `reload_list()` per keystroke destroys and recreates all rows, causes visible lag at 50+ stations, and reloads images from disk. Use `set_filter_func` + `invalidate_filter()`: build once, filter in-memory.

4. **Cover art requested on every TAG message** — ICY streams fire TAG messages every few seconds, not just on track change. Unthrottled HTTP requests will hit API rate limits. Debounce by comparing `(artist, title)` to the last seen pair; only fetch on change.

5. **ICY metadata encoding is Latin-1, not UTF-8** — GStreamer delivers the raw ICY string, which may be Latin-1 encoded. Without heuristic re-encoding, accented characters in artist/track names display as mojibake. Apply `.encode('latin-1', errors='replace').decode('utf-8', errors='replace')` defensively; test against Soma.FM stations.

---

## Implications for Roadmap

Based on the research, four phases emerge naturally from the feature dependency graph and the two-track recommendation in FEATURES.md.

### Phase 1: Module Extraction and Structure

**Rationale:** The codebase is a 512-line monolith. All three incoming features need clean homes that are not `MainWindow`. Extracting `models.py`, `repo.py`, `assets.py`, and a stub `Player` class before adding features prevents tangled wiring and makes each subsequent phase independently testable. This phase delivers no user-visible change but is the lowest-risk first step.
**Delivers:** `models.py`, `repo.py`, `assets.py`, `player.py` (stub), app runs identically after import rewiring
**Addresses:** Architecture component boundaries from ARCHITECTURE.md
**Avoids:** Growing the monolith further (makes all future pitfalls harder to fix)
**Research flag:** Standard patterns — skip `research-phase`

### Phase 2: Search and Filter UI

**Rationale:** Track A from FEATURES.md — zero external I/O, lower risk, immediate user value. All APIs are stable and well-documented. Filter state must be established before any UI can demonstrate composed filtering. This phase is independent of GStreamer bus work.
**Delivers:** Live name search, provider dropdown filter, genre/tag dropdown filter, composed AND semantics across all three
**Uses:** `Gtk.SearchBar`, `Gtk.SearchEntry`, `Gtk.DropDown`, `Gtk.StringList`, `Gtk.ListBox.set_filter_func`, `invalidate_filter()`
**Implements:** `FilterBar` and `StationList` components
**Avoids:** Pitfall 3 (rebuild on keystroke), Pitfall 6 (non-composing filters), Pitfall 11 (tag whitespace), Pitfall 8 (playing indicator lost on reload)
**Research flag:** Standard patterns — skip `research-phase`

### Phase 3: ICY Metadata Display

**Rationale:** Track B starts here. Wiring the GStreamer bus is the prerequisite for both track title display and cover art lookup (which needs artist+title as its lookup key). This phase is the highest-risk step in isolation because the existing codebase has no bus listener at all, and getting it wrong wastes time diagnosing apparent feature absence. Must be done before Phase 4.
**Delivers:** Now-playing track title label updated live from ICY stream; `Player` class extracted and emitting `track_changed` callback
**Uses:** `Gst.Bus.add_signal_watch()`, `bus.connect("message::tag")`, `Gst.TagList.get_string()`, `GLib.idle_add`
**Implements:** `Player` component with `track_changed` callback
**Avoids:** Pitfall 1 (bus watch not wired), Pitfall 4 (Latin-1 encoding), Pitfall 9 (TAG arrives before PLAYING state)
**Research flag:** Standard patterns — skip `research-phase` (GStreamer TAG bus is well-documented)

### Phase 4: Cover Art Lookup

**Rationale:** Depends on Phase 3 (`artist` + `title` from ICY TAG messages are the lookup keys). Requires async HTTP, debouncing, caching, and a fallback chain. More moving parts than the previous phases, but all components are well-defined. iTunes Search API is the primary source; MusicBrainz is the fallback for obscure tracks.
**Delivers:** Cover art image in now-playing area, updating on track change, cached in `~/.local/share/musicstreamer/cover_cache/`
**Uses:** `urllib.request`, `threading.Thread`, `GLib.idle_add`, iTunes Search API, optional MusicBrainz CAA fallback
**Implements:** `CoverArtFetcher` and `NowPlayingBar` components
**Avoids:** Pitfall 2 (widget update from thread), Pitfall 5 (API hammering), Pitfall 10 (MusicBrainz User-Agent)
**Research flag:** Worth a focused check on iTunes Search API response structure before implementing — the `artworkUrl100` → `600x600` URL substitution pattern has HIGH confidence but no live verification in this session.

### Phase Ordering Rationale

- Phase 1 before anything: extraction now costs ~1 hour and saves debugging time across all subsequent phases; doing it after adding features would require untangling more state.
- Phase 2 before Phase 3: filter UI has zero external dependencies and validates the new component structure before introducing GStreamer complexity. Delivers user-visible value early.
- Phase 3 before Phase 4: cover art lookup requires `(artist, title)` from ICY TAG messages; the Player's `track_changed` signal is Phase 4's input. The dependency is hard.
- Phases 2 and 3 are technically independent of each other and could run in parallel if two people are working, but sequencing them avoids merging complexity in a solo context.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 4 (Cover Art):** Validate iTunes Search API response structure (`artworkUrl100` field, URL substitution pattern) with a live test request before building the fetcher. Also confirm MusicBrainz two-step query syntax if the fallback is implemented.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Module Extraction):** Pure refactor, no new APIs.
- **Phase 2 (Filtering):** `set_filter_func`, `Gtk.DropDown`, `Gtk.SearchBar` are stable GTK 4.0 APIs with HIGH confidence.
- **Phase 3 (ICY Metadata):** GStreamer TAG bus pattern is canonical and well-documented; HIGH confidence across all sources.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All APIs verified: GStreamer TAG bus, GTK4 filter/search widgets, `GLib.idle_add`. iTunes Search API confirmed keyless with `artworkUrl100` field via official Apple docs. Only MusicBrainz query syntax is MEDIUM. |
| Features | MEDIUM | Table stakes and feature dependencies derived from codebase inspection (HIGH) and training knowledge of comparable GNOME apps (MEDIUM). No live user research. |
| Architecture | HIGH | Component boundaries, data flow, and module split are well-reasoned from direct codebase inspection. Threading model for GTK is a settled, documented contract. |
| Pitfalls | MEDIUM | Critical pitfalls 1–4 are HIGH confidence (GTK/GStreamer fundamentals). ICY encoding behavior (Pitfall 4) is LOW confidence — stream-source dependent, must validate against real streams. iTunes rate limits (Pitfall 5) are LOW confidence — undocumented, empirically validate. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **iTunes Search API rate limits:** Documented as ~20 req/min in STACK.md but flagged as LOW confidence in PITFALLS.md (undocumented). The app's use pattern (one lookup per track change) is unlikely to breach any reasonable limit, but validate empirically during Phase 4 development.
- **ICY encoding behavior:** Latin-1 vs UTF-8 ambiguity is stream-dependent and cannot be fully resolved without testing against real stations (Soma.FM, AudioAddict). Implement the heuristic re-encoding in Phase 3 and log raw bytes during development.
- **MusicBrainz Lucene query field names:** MEDIUM confidence — confirmed API exists and rate limits are documented, but exact query field names (`recording:`, `artist:`) are from training data, not live verification. Treat MusicBrainz as a true fallback and test it independently before relying on it.
- **`station.tags` data quality:** Comma-separated tags in existing DB may have inconsistent whitespace. Normalize on write and on comparison in Phase 2; consider a data migration script if existing station data is large.

---

## Sources

### Primary (HIGH confidence)
- Apple iTunes Search API official docs (fetched 2026-03-18) — `artworkUrl100` field, no API key required, ~20 req/min
- GTK4 API: `Gtk.ListBox.set_filter_func`, `Gtk.SearchBar`, `Gtk.SearchEntry`, `Gtk.DropDown` — stable since GTK 4.0
- GStreamer `playbin` + `icydemux` + TAG bus message pattern — GStreamer application development guide, canonical
- `GLib.idle_add` cross-thread dispatch — PyGObject documentation, GTK threading contract
- Existing codebase (`main.py`, 512 lines, inspected 2026-03-18) — direct inspection, HIGH confidence

### Secondary (MEDIUM confidence)
- GNOME HIG: search, filtering, list view patterns — stable spec, no live verification needed
- MusicBrainz Web Service: rate limits (1 req/sec), User-Agent requirement — documented policy; Lucene query syntax from training data
- Shortwave and Rhythmbox radio plugin UX patterns — training knowledge of comparable GNOME radio apps
- GStreamer TAG bus behavior with ICY streams — confirmed by GStreamer PyGObject tutorials

### Tertiary (LOW confidence)
- ICY stream encoding behavior (Latin-1 vs UTF-8) — stream-source dependent; requires empirical validation against real stations
- iTunes Search API undocumented rate limits — treat as best-effort; validate empirically in Phase 4

---

*Research completed: 2026-03-18*
*Ready for roadmap: yes*
