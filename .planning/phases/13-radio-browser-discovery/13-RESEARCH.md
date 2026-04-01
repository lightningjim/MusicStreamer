# Phase 13: Radio-Browser Discovery - Research

**Researched:** 2026-03-31
**Domain:** Radio-Browser.info REST API + GTK4/libadwaita modal dialog + GLib debounce
**Confidence:** HIGH

## Summary

Phase 13 adds a discovery dialog backed by the Radio-Browser.info public API. The API is free, requires no auth, and was verified live during research. Endpoints for search, tags, and countries all respond correctly. The stack is identical to the rest of the project: GTK4 + libadwaita, GStreamer via `player.py`, SQLite via `repo.py`.

The main new concerns are: (1) threading — all API calls must run in daemon threads with `GLib.idle_add` callbacks, matching the pattern already used in `edit_dialog.py`; (2) debounce — `GLib.timeout_add` + `GLib.source_remove` gives 500ms debounce without any new dependencies; (3) provider name extraction — the `network` field is frequently empty, so falling back to the homepage domain (strip `www.`) is the reliable strategy; (4) the repo lacks a URL-exists check and a direct `insert_station` method — both need to be added.

**Primary recommendation:** Create `musicstreamer/radio_browser.py` as a thin API client, add `repo.station_exists_by_url()` and `repo.insert_station()`, then build `DiscoveryDialog` following the `EditStationDialog` pattern exactly.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Discovery UI is a modal dialog (separate `Adw.Window`), consistent with the existing `EditStationDialog` pattern
- **D-02:** Results displayed as simple `Adw.ActionRow` list rows — station name as title, subtitle with country/tags/bitrate
- **D-03:** Live search with debounce (~500ms) — results update as user types, no submit button needed
- **D-04:** Tag and country filters are `Adw.ComboRow` dropdowns, pre-populated from the Radio-Browser API
- **D-05:** Search text and dropdown filters compose together when querying the API
- **D-06:** Preview temporarily replaces current playback. Closing the dialog auto-resumes the previously playing station.
- **D-07:** Each result row has a small play button icon to trigger preview (not row-click activation)
- **D-08:** Provider name is auto-assigned from the station's homepage/network metadata in the Radio-Browser response (not hardcoded "Radio-Browser")
- **D-09:** If a station with the same URL already exists in the library, block the save with an error message (not a silent skip)
- **D-10:** Save button per row (or save action) adds the station directly to the library — no intermediate edit dialog

### Claude's Discretion
- Exact Radio-Browser API endpoints and query parameter mapping
- How to populate tag/country dropdowns (separate API calls vs extracted from results)
- ActionRow subtitle format
- Dialog size, spacing, and widget hierarchy
- How to handle Radio-Browser API errors or empty results
- Whether the play-preview button shows a stop icon when that row is actively previewing
- How to extract provider/network name from Radio-Browser metadata

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DISC-01 | User can search Radio-Browser.info stations by name or provider name from an in-app discovery dialog | `GET /json/stations/search?name=...` endpoint verified live; `Gtk.SearchEntry` + GLib debounce pattern identified |
| DISC-02 | User can filter Radio-Browser.info search results by tag (genre) or country | `GET /json/tags` and `GET /json/countries` endpoints verified; compose with search via `tag=` + `countrycode=` params |
| DISC-03 | User can play a Radio-Browser.info station as a preview without saving it to the library | `player.play()` accepts any `Station`-like URL; preview state tracked in dialog; main window saves `_current_station` for resume |
| DISC-04 | User can save a Radio-Browser.info station to their library from the discovery dialog | New `repo.insert_station()` needed; `repo.station_exists_by_url()` for duplicate check; `reload_list()` on save |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `urllib.request` + `json` | stdlib | HTTP GET + JSON parse for Radio-Browser API | Already used in `edit_dialog.py`; no extra deps |
| `threading` | stdlib | Daemon threads for API calls | Same pattern as `fetch_yt_thumbnail` in `edit_dialog.py` |
| `GLib.idle_add` | PyGObject (system) | Marshal thread results back to GTK main loop | Required for all widget updates from background threads |
| `GLib.timeout_add` / `GLib.source_remove` | PyGObject (system) | 500ms debounce on search entry | Native GTK debounce; no extra libraries needed |
| `Adw.Window` | libadwaita (system) | Modal dialog container | Matches `EditStationDialog` pattern exactly |
| `Adw.ActionRow` | libadwaita (system) | Result list rows | Decision D-02 |
| `Gtk.DropDown` + `Gtk.StringList` | GTK4 (system) | Tag/country filter dropdowns | Same widget used in `EditStationDialog` provider picker |
| `Gtk.SearchEntry` | GTK4 (system) | Search input with clear button | Built-in `search-changed` signal |
| `Gtk.Stack` | GTK4 (system) | loading / results / empty / error states | Already used in `main_window.py` |

**Installation:** No new packages needed — all dependencies are system PyGObject packages already present.

---

## Architecture Patterns

### Recommended Project Structure
```
musicstreamer/
├── radio_browser.py        # NEW: API client (search, tags, countries)
├── repo.py                 # MODIFY: add station_exists_by_url(), insert_station()
└── ui/
    ├── discovery_dialog.py # NEW: DiscoveryDialog (Adw.Window subclass)
    └── main_window.py      # MODIFY: add "Discover" button, preview save/resume logic
```

### Pattern 1: Radio-Browser API Client (`radio_browser.py`)
**What:** Thin module wrapping three endpoints. No class needed — three module-level functions called from daemon threads.
**When to use:** Called exclusively from background threads; never called on the GTK main thread.

```python
# radio_browser.py
import urllib.request, json, urllib.parse

BASE = "https://all.api.radio-browser.info/json"

def search_stations(name: str, tag: str = "", countrycode: str = "",
                    limit: int = 100) -> list[dict]:
    params = {"name": name, "limit": str(limit),
              "hidebroken": "true", "order": "votes", "reverse": "true"}
    if tag:
        params["tag"] = tag
    if countrycode:
        params["countrycode"] = countrycode
    url = f"{BASE}/stations/search?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.load(r)

def fetch_tags(limit: int = 200) -> list[str]:
    url = f"{BASE}/tags?order=stationcount&reverse=true&limit={limit}&hidebroken=true"
    with urllib.request.urlopen(url, timeout=10) as r:
        return [t["name"] for t in json.load(r)]

def fetch_countries() -> list[tuple[str, str]]:
    """Returns list of (iso_3166_1, name) sorted by stationcount desc."""
    url = f"{BASE}/countries?order=stationcount&reverse=true"
    with urllib.request.urlopen(url, timeout=10) as r:
        return [(c["iso_3166_1"], c["name"]) for c in json.load(r)
                if c.get("iso_3166_1")]
```

**Verified:** All three endpoints tested live. `search_stations` params `name`, `tag`, `countrycode`, `hidebroken`, `order`, `reverse`, `limit` all confirmed working.

### Pattern 2: GLib Debounce
**What:** Cancel previous timeout source, schedule new one. Standard GTK pattern.

```python
# Inside DiscoveryDialog
self._debounce_id = None

def _on_search_changed(self, entry):
    if self._debounce_id is not None:
        GLib.source_remove(self._debounce_id)
    self._debounce_id = GLib.timeout_add(500, self._fire_search)

def _fire_search(self):
    self._debounce_id = None
    self._do_search()
    return False  # do not repeat
```

### Pattern 3: Background API Call with GLib.idle_add
**What:** Match `fetch_yt_thumbnail` pattern from `edit_dialog.py` exactly.

```python
def _do_search(self):
    self._stack.set_visible_child_name("loading")
    name = self._search_entry.get_text().strip()
    tag = self._get_selected_tag()
    cc = self._get_selected_country_code()
    def _worker():
        try:
            results = radio_browser.search_stations(name, tag, cc)
            GLib.idle_add(self._on_results, results)
        except Exception as e:
            GLib.idle_add(self._on_error, str(e))
    threading.Thread(target=_worker, daemon=True).start()
```

### Pattern 4: Provider Name Extraction
**What:** `network` field is frequently empty. Use homepage domain as fallback.

```python
from urllib.parse import urlparse

def _extract_provider(station_dict: dict) -> str:
    network = (station_dict.get("network") or "").strip()
    if network:
        return network
    homepage = (station_dict.get("homepage") or "").strip()
    if homepage:
        domain = urlparse(homepage).netloc
        return domain.replace("www.", "") or ""
    return ""
```

**Verified:** `network` field confirmed empty for BBC, many major stations. Homepage domain extraction tested via Python `urlparse` — produces clean values like `bbc.co.uk`, `101smoothjazz.com`.

### Pattern 5: Preview Playback State Management
**What:** Save prior station before preview; restore on dialog close.

In `DiscoveryDialog.__init__`:
```python
self._preview_station = None  # Station currently being previewed
self._prior_station = main_window._current_station  # save for resume
```

On close-request:
```python
def _on_close(self, *_):
    if self._preview_station is not None:
        main_window.player.stop()
        if self._prior_station:
            main_window._play_station(self._prior_station)
    return False
```

**Note:** `player.play()` requires a `Station` dataclass. For preview, construct a minimal `Station` from the Radio-Browser result dict. `station_id` can be `0` (dummy) since preview stations are never persisted.

### Pattern 6: Save to Library (Repo Changes Needed)
**What:** Two new repo methods needed:

```python
# Add to Repo class:

def station_exists_by_url(self, url: str) -> bool:
    row = self.con.execute(
        "SELECT 1 FROM stations WHERE url = ?", (url,)
    ).fetchone()
    return row is not None

def insert_station(self, name: str, url: str, provider_name: str,
                   tags: str) -> int:
    provider_id = self.ensure_provider(provider_name) if provider_name else None
    cur = self.con.execute(
        "INSERT INTO stations(name, url, provider_id, tags) VALUES (?, ?, ?, ?)",
        (name, url, provider_id, tags or ""),
    )
    self.con.commit()
    return int(cur.lastrowid)
```

**Why not use existing `create_station()` + `update_station()`:** `create_station()` inserts a blank row then `update_station()` fills it. For discovery save, we know all fields upfront — a single insert is cleaner and avoids an intermediate empty row if the save fails.

### ActionRow Subtitle Format
Per UI-SPEC: `"{countrycode} · {tags_truncated} · {bitrate}kbps"` — omit absent components. Tags from Radio-Browser are comma-separated in the `tags` field; take first 2-3 to avoid overflow.

```python
def _make_subtitle(s: dict) -> str:
    parts = []
    if s.get("countrycode"):
        parts.append(s["countrycode"])
    raw_tags = s.get("tags", "")
    if raw_tags:
        tag_list = [t.strip() for t in raw_tags.split(",") if t.strip()][:3]
        parts.append(", ".join(tag_list))
    if s.get("bitrate"):
        parts.append(f"{s['bitrate']}kbps")
    return " · ".join(parts)
```

### Anti-Patterns to Avoid
- **Calling `urllib.request.urlopen` on the GTK main thread:** Blocks UI. Always use a daemon thread.
- **Updating widgets from a non-main thread:** Always wrap in `GLib.idle_add`.
- **Building filter dropdowns from search results:** Populating from results means dropdowns are empty until a search runs. Use separate API calls on dialog open (fetch_tags, fetch_countries).
- **Using `Adw.ComboRow` for dropdowns:** The CONTEXT says `Adw.ComboRow` for the pattern — but `EditStationDialog` actually uses `Gtk.DropDown`. Use `Gtk.DropDown` + `Gtk.StringList` for consistency (the CONTEXT refers to the concept; `Gtk.DropDown` is the actual widget used in the codebase).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP requests | Custom socket code | `urllib.request` (stdlib) | Already in project; no new deps |
| Debounce timer | Manual time-based checks | `GLib.timeout_add` + `GLib.source_remove` | Native GTK; integrates with main loop |
| Thread-safe UI updates | Mutex/lock gymnastics | `GLib.idle_add` | The GTK way; already used in `edit_dialog.py` |
| Provider name parsing | Complex heuristics | `urlparse(homepage).netloc.replace("www.", "")` | One line; reliable enough |
| Radio-Browser server selection | Custom DNS lookup | `all.api.radio-browser.info` (DNS round-robin) | Verified working; simplest approach |

---

## Common Pitfalls

### Pitfall 1: Stale Debounce Callback After Dialog Close
**What goes wrong:** Dialog is closed while debounce timer is pending. Timer fires, `_fire_search` runs, tries to update widgets on a destroyed window — crash or silent error.
**Why it happens:** `GLib.timeout_add` callbacks survive widget destruction unless explicitly cancelled.
**How to avoid:** In `_on_close_request`, cancel any pending debounce: `if self._debounce_id: GLib.source_remove(self._debounce_id)`.
**Warning signs:** Intermittent crash when closing dialog quickly after typing.

### Pitfall 2: Background Thread Updates After Dialog Close
**What goes wrong:** Search thread completes after dialog close, `_on_results` fires via `GLib.idle_add`, tries to update `_stack` or `_listbox` — widget may be gone.
**Why it happens:** Same race condition as `_fetch_cancelled` in `EditStationDialog`.
**How to avoid:** Add `self._cancelled = False` flag; set `True` in `_on_close_request`; check at start of all `idle_add` callbacks.

### Pitfall 3: `Gtk.DropDown` Index vs Value Mismatch
**What goes wrong:** User selects "Any genre" (index 0) but code reads index 0 as a real tag — sends `tag=""` when it should send nothing.
**Why it happens:** `Gtk.StringList` index 0 is the "Any" placeholder.
**How to avoid:** Check `selected_index == 0` → treat as no filter. Only pass `tag` to API if index > 0.

### Pitfall 4: Radio-Browser Tags Field is Comma-Separated (Not Array)
**What goes wrong:** Treating `tags` as a list when it's a plain string.
**Verified:** API response: `"tags": "jazz,smooth jazz,blues"` — plain comma-separated string.
**How to avoid:** Always split with `.split(",")` and strip whitespace.

### Pitfall 5: Empty Search Term Behavior
**What goes wrong:** Empty search string sent to Radio-Browser returns all stations (100+ results). This is probably not desired on dialog open.
**How to avoid:** Don't fire a search on dialog open — wait for user to type. Stack should start in "empty" state with a prompt like "Search for stations above."

### Pitfall 6: `player.play()` Requires `Station` Dataclass
**What goes wrong:** Passing a raw dict to `player.play()` — it accesses `.url`, `.name`, `.icy_disabled` attributes.
**How to avoid:** Construct a minimal `Station(id=0, name=..., url=..., provider_id=None, provider_name=..., tags=..., station_art_path=None, album_fallback_path=None, icy_disabled=False)` from the Radio-Browser result dict before calling `player.play()`.

### Pitfall 7: URL Not Unique in DB Schema
**What goes wrong:** The `stations` table has no UNIQUE constraint on `url` — duplicate saves succeed silently at the DB level.
**How to avoid:** `repo.station_exists_by_url()` must check before insert; block the save in the dialog if it returns True. Do not rely on a DB-level constraint.

---

## Code Examples

### Verified: Radio-Browser search response fields
```
Verified live 2026-03-31 against https://all.api.radio-browser.info/json/stations/search

Key fields used in this phase:
  name          — station display name
  url           — stream URL (use for playback + duplicate check)
  url_resolved  — may differ from url; use url for storage
  tags          — comma-separated string (e.g. "jazz,smooth jazz")
  countrycode   — ISO 3166-1 alpha-2 (e.g. "US", "DE")
  country       — full country name
  bitrate       — integer kbps
  homepage      — full URL (used for provider name extraction)
  network       — often empty string; prefer homepage domain
  lastcheckok   — 1 = working at last check (filtered by hidebroken=true)
  votes         — popularity signal (sort order)
```

### Verified: Tags endpoint response
```json
[{"name": "pop", "stationcount": 5079}, {"name": "music", "stationcount": 4004}, ...]
```
Returns `name` (tag string) and `stationcount`. Use `name` for the dropdown and API `tag=` param.

### Verified: Countries endpoint response
```json
[{"name": "The United States Of America", "iso_3166_1": "US", "stationcount": 6785}, ...]
```
Display `name` in dropdown; send `iso_3166_1` as `countrycode=` param.

### Opening dialog from main_window.py
```python
# In MainWindow — add Discover button to HeaderBar or filter_box
discover_btn = Gtk.Button(label="Discover")
discover_btn.connect("clicked", self._open_discovery)
header.pack_end(discover_btn)

def _open_discovery(self, *_):
    from musicstreamer.ui.discovery_dialog import DiscoveryDialog
    dlg = DiscoveryDialog(self.get_application(), self.repo, self)
    dlg.set_transient_for(self)
    dlg.present()
```

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `urllib.request` | HTTP calls to Radio-Browser API | ✓ | stdlib | — |
| `threading` | Daemon threads | ✓ | stdlib | — |
| `GLib.timeout_add` | Debounce | ✓ | system PyGObject | — |
| `all.api.radio-browser.info` | All API calls | ✓ | live, verified | — |
| Internet connectivity | API calls | ✓ | confirmed | Error state in dialog |

**Missing dependencies with no fallback:** None.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | none (discovered via `pyproject.toml` presence) |
| Quick run command | `python3 -m pytest tests/ -q --tb=short` |
| Full suite command | `python3 -m pytest tests/ -q --tb=short` |

**Baseline:** 94 tests passing before this phase begins.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DISC-01 | `radio_browser.search_stations()` returns list of dicts with expected keys | unit | `pytest tests/test_radio_browser.py -x` | ❌ Wave 0 |
| DISC-01 | `radio_browser.search_stations()` handles network error (raises) | unit | `pytest tests/test_radio_browser.py -x` | ❌ Wave 0 |
| DISC-02 | `radio_browser.fetch_tags()` returns list of strings | unit | `pytest tests/test_radio_browser.py -x` | ❌ Wave 0 |
| DISC-02 | `radio_browser.fetch_countries()` returns list of (iso, name) tuples | unit | `pytest tests/test_radio_browser.py -x` | ❌ Wave 0 |
| DISC-04 | `repo.station_exists_by_url()` returns True for existing URL | unit | `pytest tests/test_repo.py -x` | ✅ (add to existing) |
| DISC-04 | `repo.station_exists_by_url()` returns False for unknown URL | unit | `pytest tests/test_repo.py -x` | ✅ (add to existing) |
| DISC-04 | `repo.insert_station()` persists name, url, provider, tags | unit | `pytest tests/test_repo.py -x` | ✅ (add to existing) |
| DISC-03 | Preview playback uses player.play() with dummy Station | manual-only | n/a — GStreamer/GTK integration | n/a |
| DISC-03 | Dialog close resumes prior station | manual-only | n/a — requires running app | n/a |

**Note on `test_radio_browser.py`:** Use `unittest.mock.patch("urllib.request.urlopen")` to avoid live network calls in unit tests. Provide fixture JSON matching the verified API shapes above.

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/ -q --tb=short`
- **Per wave merge:** `python3 -m pytest tests/ -q --tb=short`
- **Phase gate:** Full suite green (94 + new tests) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_radio_browser.py` — unit tests for API client functions (mock urllib)

*(No framework install needed — pytest already present)*

---

## Sources

### Primary (HIGH confidence)
- Radio-Browser API — live probed 2026-03-31: search, tags, countries endpoints all verified
- `musicstreamer/ui/edit_dialog.py` — threading + `GLib.idle_add` + `Gtk.DropDown` patterns
- `musicstreamer/player.py` — `player.play(Station, on_title)` signature confirmed
- `musicstreamer/repo.py` — `create_station()`, `update_station()` signatures; absence of URL uniqueness check confirmed
- `musicstreamer/ui/main_window.py` — `_current_station`, `_play_station()`, `reload_list()` confirmed

### Secondary (MEDIUM confidence)
- UI-SPEC.md (13-UI-SPEC.md) — widget hierarchy, subtitle format, copy strings — already approved

---

## Metadata

**Confidence breakdown:**
- Radio-Browser API: HIGH — live tested, all endpoints verified
- Standard stack: HIGH — same PyGObject stack as rest of project
- Architecture: HIGH — follows existing codebase patterns directly
- Pitfalls: HIGH — several verified from actual code inspection (URL not unique, network field empty, Station dataclass requirement)

**Research date:** 2026-03-31
**Valid until:** 2026-04-30 (Radio-Browser API is stable/free; GTK stack is system packages)
