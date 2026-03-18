# Feature Landscape

**Domain:** Personal GNOME desktop internet radio / stream player
**Researched:** 2026-03-18
**Confidence note:** Web access was unavailable during this session. Findings draw on
training knowledge of GNOME HIG, Shortwave, Rhythmbox, Lollypop, RadioDroid, and
general desktop streaming app patterns (knowledge cutoff Aug 2025). Confidence levels
reflect this; architecture-stable patterns are marked HIGH, nuanced UX specifics MEDIUM.

---

## Table Stakes

Features users expect from any desktop streaming app. Missing = product feels unfinished
or frustrating.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Station list with inline art | Every modern media app (Rhythmbox, Shortwave, Lollypop) shows an icon per row. Text-only lists feel bare and make scanning harder at 50+ items. | Low | Already partially implemented (48 px prefix picture in `Adw.ActionRow`). Needs reliability pass. |
| Name search (live filter) | Standard in every list-heavy GNOME app. Users reaching 50+ stations expect it immediately. Absence causes real frustration at 100+ stations. | Low | `Gtk.SearchBar` + `Gtk.SearchEntry` + `ListBox.set_filter_func`. No DB round-trip needed — filter in-memory. |
| Provider/source filter dropdown | Stations are explicitly grouped by provider in the schema. Users mental model mirrors this (e.g. "I want a Soma.FM station"). | Low–Med | `Gtk.DropDown` or `Adw.ComboRow`. Requires syncing dropdown items with live provider list. |
| Genre/tag filter dropdown | Tags column already exists in schema and edit UI. Users expect to narrow by genre (e.g. "Jazz", "Ambient"). | Low–Med | Same pattern as provider filter. Tags are comma-separated today — split on display. |
| Composed filters (AND semantics) | Search + provider + genre must compose. Selecting a genre while having a search term active should intersect, not replace. | Med | `ListBox.set_filter_func` evaluates all active criteria on each row. State must be kept in sync across all three inputs. |
| Now-playing track title | Every internet radio app (RadioBrowser, Shortwave, Rhythmbox with radio plugin) prominently shows the current track title from ICY metadata. Users explicitly switch stations when they do not like the current track — they need to know what it is. | Low–Med | GStreamer `TAG` bus messages already arrive. Need to connect `bus.add_signal_watch()` handler → update a label in the now-playing bar. |
| Visual loading / buffering state | Users need feedback between clicking Play and audio starting. Without it, they click again or assume the app is broken. | Low | Toggle play button to a spinner or insensitive state during `GST_STATE_CHANGE_ASYNC`. |
| Play / stop toggle per station | Clicking an already-playing station should stop it. Rows with no visual "playing" indicator cause double-play confusion. | Low | Track `current_station_id`; update row appearance (e.g. playing icon) on state change. |
| Graceful error display | Network failures, dead streams, yt-dlp errors surface as user-visible inline messages, not silent failures or console-only errors. | Low | `Adw.Toast` or an in-row subtitle update covers most cases. |

---

## Differentiators

Features that set the app apart from a basic player. Not universally expected at this
scope, but highly valued once present.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Cover art from ICY metadata (external lookup) | Turns a radio player into something that feels alive. Shortwave does this; most minimal players do not. Visual context improves dwell time and reduces "what is playing?" mental load. | Med | Parse `artist` + `title` from ICY TAG messages → query iTunes Search API (`itunes.apple.com/search?term=...&entity=song`) or MusicBrainz Cover Art Archive. Cache results keyed on `artist+title` to avoid redundant lookups. Fallback to station album art. No API key required for either service. |
| Animated cover art transition | Crossfade between previous and new cover art on track change. Shortwave-style. Makes the app feel polished vs utilitarian. | Med | `Gtk.Stack` with `Gtk.StackTransitionType.CROSSFADE` between two `Gtk.Picture` widgets, alternating which is shown. |
| Now-playing bar (distinct from header) | A dedicated bottom (or top) strip with: cover art thumbnail, artist, track title, station name, play/stop. Feels like a real music app rather than a hacked label in the header bar. | Med | `Adw.ToolbarView` supports a bottom bar via `add_bottom_bar`. Persistent across station list scrolling. |
| Filter chip / active-filter summary | A small row of dismissible chips showing which filters are active ("Soma.FM ×", "Ambient ×"). Reduces "why am I only seeing three stations?" confusion. | Med | `Gtk.FlowBox` with pill-shaped labels. Each chip emits a signal to clear its filter. |
| Keyboard navigation parity | Full keyboard control: `Ctrl+F` focuses search, arrow keys navigate list, `Enter` plays, `Escape` stops. Power users and GNOME HIG both require it. | Low | `Gtk.ShortcutController` + action wiring. SearchBar has built-in `key-capture-widget` support. |

---

## Anti-Features

Features to deliberately NOT build for this project.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| In-app station discovery / radio directory browser | RadioBrowser API integration sounds appealing but dramatically changes the app's scope from a curated personal library to a discovery tool. The project's stated value prop is "the right station is one or two clicks away" — a 30,000-station directory undermines that. | Maintain the curated library model. Add/edit via the dialog. |
| Scrobbling (Last.fm / ListenBrainz) | PROJECT.md explicitly defers this. The ICY metadata plumbing needed is a prerequisite anyway — do that first. Adding scrobbling before metadata display is solid inverts the dependency. | Leave for a future milestone after metadata display is stable. |
| Podcast support | Completely different feed model (RSS, episodic, seeking), different UX, different storage. A distraction from streaming. | Out of scope per PROJECT.md. |
| Equalizer / audio effects | GStreamer can do this but it adds significant UI complexity and is not in the app's value proposition. | Out of scope. |
| Playlist / queue management | Internet radio is stateless (you play one station at a time). A queue model is a music-library concept. | The "play a station" model is correct for this domain. |
| Tag autocomplete with a picker UI | Comma-separated free-text tags in the edit dialog are sufficient for a personal 50–200 station library. A full tag management UI (rename, merge, autocomplete) is over-engineering for this scale. | Keep tags as free text. Filter dropdown reads distinct tag values at query time. |
| Waveform / visualizer | Eye candy that adds no utility and has meaningful render cost. | Not worth building. |

---

## Feature Dependencies

```
Name search            →  (none — in-memory filter on loaded list)
Provider filter        →  Provider list loaded from DB on startup
Genre/tag filter       →  Tags parsed from station model at filter time
Composed filters       →  Name search + Provider filter + Genre/tag filter
                          (all three must exist before composition is meaningful)

ICY metadata display   →  GStreamer TAG bus message wiring
                          (prerequisite: bus.add_signal_watch() connected)

Cover art lookup       →  ICY metadata display
                          (artist+title from ICY TAG messages are the lookup key)

Animated art transition → Cover art lookup
                          (nothing to transition without art)

Now-playing bar        →  ICY metadata display  (track title)
                       →  Cover art lookup       (art thumbnail)
                          (bar is technically buildable before both, but looks empty)

Filter chips           →  Provider filter + Genre/tag filter
                          (chips reflect active filter state — needs filters first)
```

---

## MVP Recommendation

The milestone goal is search+filter UI + ICY metadata display + cover art from metadata.
That maps cleanly to two sequential tracks:

**Track A — Filtering (no external I/O, lower risk):**
1. Search box (live name filter)
2. Provider dropdown filter
3. Genre/tag dropdown filter
4. Composed AND semantics across all three

**Track B — Now Playing (external I/O, higher risk):**
1. GStreamer TAG bus message handler → ICY track title label
2. iTunes Search API (or MusicBrainz) cover art lookup + disk cache
3. Fallback chain: fetched art → station album art → station logo → generic placeholder

Build Track A first. It has zero external dependencies and delivers immediate value.
Track B has network I/O and async state management — do it after filtering is stable.

**Defer:**
- Animated cover art transition: nice but not in milestone scope
- Now-playing bar redesign: current header label is sufficient for this milestone
- Filter chips: useful but not blocking; add if time permits

---

## Cover Art Lookup — Technical Notes

Confidence: MEDIUM (based on documented public APIs, no live verification possible)

**iTunes Search API** (recommended first choice):
- Endpoint: `https://itunes.apple.com/search?term={artist}+{title}&entity=song&limit=1`
- Returns JSON with `artworkUrl100` (100 px). Replace `100x100` with `600x600` in the
  URL for higher resolution.
- No API key. Rate limit undocumented but generous for single-user desktop use.
- Response latency: typically 200–600 ms.

**MusicBrainz + Cover Art Archive** (fallback):
- Step 1: `https://musicbrainz.org/ws/2/recording/?query=artist:{artist}+recording:{title}&fmt=json`
  → extract release MBID
- Step 2: `https://coverartarchive.org/release/{mbid}/front-500`
- Two round trips; slower. Better for niche/non-commercial music.
- MusicBrainz requires a `User-Agent` header identifying the app.

**Caching strategy:**
- Key: `sha1(artist.lower() + "|" + title.lower())`
- Store in `~/.local/share/musicstreamer/cover_cache/{key}.jpg`
- Cache indefinitely (track titles do not retroactively change).
- On cache hit: load from disk, no network call.

**Async requirement:**
- Cover art lookup MUST be async (GLib.idle_add / threading.Thread) — blocking the
  GTK main loop on a network call will freeze the UI.

---

## Sources

- Training knowledge of Shortwave (GNOME radio app, GitLab.gnome.org/World/Shortwave) — MEDIUM confidence
- Training knowledge of Rhythmbox radio plugin UX — MEDIUM confidence
- GNOME HIG principles for search, filtering, list views — HIGH confidence (stable spec)
- iTunes Search API documentation (public, no auth) — MEDIUM confidence (no live verification)
- MusicBrainz web service documentation — MEDIUM confidence (no live verification)
- GStreamer TAG bus message behavior with ICY streams — HIGH confidence (GStreamer docs, stable API)
- Existing `main.py` codebase analysis — HIGH confidence (direct inspection)
