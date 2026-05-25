---
diagnosis: T12-search-artist-album
phase: 60-gbs-fm-integration
severity: major
status: complete
date: 2026-05-04
---

# T12: GBSSearchDialog Missing Artist/Album Panels

## 1. Root Cause

The missing Artist: and Album: panels are a **planning scope gap**: `60-RESEARCH.md` explicitly
descoped those sections ("Phase 60 v1 should ignore those — only the song results matter for
'submit a song'"), and `_SongRowParser` was intentionally coded with a docstring comment that
reads "Ignores `<p class="artists">` / `<p class="albums">` blocks (D-08e — only song results
count)".  Neither parser nor renderer ever extracted the data; neither was supposed to.

---

## 2. Mechanism

### 2a. HTML structure (verified from `search_test_p1.html`)

The captured fixture confirms page 1 of a query does contain both blocks.  They appear immediately
before the `<table class="songs">` in the `<div class="playlist">` container:

```html
<p class="artists">Artists:<ul>
  <li><a href="/artist/53817">Ahmayktesta</a></li>
  ...
  <li><a href="/artist/4803">Testament</a></li>
</ul></p>

<p class="artists">Albums:<ul>
  <li><a href="/album/1488">#gbs-fm's greatest shits</a></li>
  ...
</ul></p>

<table class="songs"> ... </table>
```

Note: GBS.FM reuses the CSS class `"artists"` for both the Artist and Album paragraphs; the
distinction is the paragraph's leading text ("Artists:" vs "Albums:").

Page 2 (`search_test_p2.html`) has **no** Artist/Album blocks — they are page-1-only (or
first-match-only) content.  `search_empty.html` has neither block (the no-match state renders only
a "No exact dong/artist matches" text paragraph, no `<p class="artists">` elements).

### 2b. Parser (`gbs_api._SongRowParser`, `gbs_api.py` lines 286-362)

`_SongRowParser.handle_starttag` activates only when it sees `<table class="songs">`.  All HTML
before or outside that table is silently discarded — including the `<p class="artists">` blocks.
The docstring (line 293-295) is explicit:

```
Ignores <p class="artists"> / <p class="albums"> blocks (D-08e — only song results count).
```

The `search()` function (lines 368-396) returns:
```python
{"results": parser.results, "page": int(page), "total_pages": total_pages}
```
There is no `artist_links` or `album_links` key.  The data is not extracted at all.

### 2c. Worker signal (`gbs_search_dialog._GbsSearchWorker`, lines 53-78)

`_GbsSearchWorker.run()` calls `gbs_api.search()` and then emits:
```python
self.finished.emit(list(out.get("results", [])), int(out.get("page", ...)), int(out.get("total_pages", ...)))
```
The `finished` signal is typed `Signal(list, int, int)` — no channel for artist/album links.

### 2d. Dialog renderer (`GBSSearchDialog._on_search_finished`, lines 278-288)

Receives only `(results: list, page: int, total_pages: int)` and calls `_render_results()`.
`_render_results()` (lines 327-342) iterates over the song results list and populates the
`QTableView`.  There are no Artist:/Album: panels in `_build_ui()` (lines 154-226); the layout
contains only: search row → progress bar → results table → inline error label → pagination row →
close button.

### 2e. Test suite

`tests/test_gbs_api.py::test_search_parses_results` (line 202) asserts on `results`, `page`, and
`add_url` only.  No test asserts on `artist_links` or `album_links`.
`tests/test_gbs_search_dialog.py` never constructs or checks Artist:/Album: widgets.

---

## 3. Scope Determination

**Planning gap, not an implementation defect.**

`60-RESEARCH.md` line 422 explicitly says:
> "Search also includes `<p class="artists">` and `<p class="albums">` blocks with hits at the top
> of the page.  Phase 60 v1 should ignore those (only the song results matter for 'submit a song')."

`_SongRowParser`'s docstring (line 293-295 of `gbs_api.py`) cites this decision as "D-08e".
`60-07-search-submit-SUMMARY.md` records the plan as fully completed with zero known stubs.

The researcher and planner made a deliberate simplification.  T12 is evidence that the simplification
was wrong from the user's perspective, but the code faithfully implements what the plan said.

---

## 4. Data Availability

The canonical fixture **already contains the data needed** for full implementation:

| Element | In `search_test_p1.html` | In `search_test_p2.html` | In `search_empty.html` |
|---------|--------------------------|--------------------------|------------------------|
| `<p class="artists">` (Artist block) | YES (lines 390-483) | NO | NO |
| `<p class="artists">` (Album block) | YES (lines 486-712) | NO | NO |
| `<table class="songs">` | YES | YES | NO |

URL patterns present in the fixture:
- Artist links: `/artist/<int>` (e.g. `href="/artist/53817"`)
- Album links: `/album/<int>` (e.g. `href="/album/1488"`)

Clicking an artist link on gbs.fm loads the song-results page for that artist. Based on the
URLconf exposed in the Django DEBUG 404 page (RESEARCH.md), there is no separate `/artist/` search
endpoint.  Artist/album pages on gbs.fm are content pages, not search filter endpoints.  However,
the gbs.fm search URL supports a `query=` parameter, and the artist-page links in the fixture
(`/artist/<id>`) suggest a different mechanism (browsing by artist ID, not a filtered `/search`).
The exact navigation target needs verification (see Open Questions §6.1).

---

## 5. Fix Outline

### 5a. Parser side — `gbs_api.py`

Add a second parser (or extend `_SongRowParser`) to extract the two `<p class="artists">` blocks.

**New helper class `_ArtistAlbumParser(HTMLParser)`:**
- Detects `<p class="artists">` by tag + class
- Reads the leading text node ("Artists:" vs "Albums:") to distinguish the two blocks
- Within each block, collects `(text, href)` pairs from `<li><a href="...">text</a></li>` entries
- Produces: `artist_links: list[dict]`, `album_links: list[dict]`
  where each dict is `{"text": str, "url": str}` e.g. `{"text": "Testament", "url": "/artist/4803"}`

**Updated `search()` return shape:**
```python
{
  "results": list[dict],       # unchanged
  "page": int,                 # unchanged
  "total_pages": int,          # unchanged
  "artist_links": list[dict],  # NEW: [] when page > 1 or no matches
  "album_links": list[dict],   # NEW: [] when page > 1 or no matches
}
```

### 5b. Worker signal — `gbs_search_dialog._GbsSearchWorker`

The `finished` signal is currently `Signal(list, int, int)`.  Two options:

**Option A (minimal change):** Keep the existing signal; add a second `metadata_ready` signal
`Signal(list, list)` emitting `(artist_links, album_links)` on the same `run()` call.

**Option B (breaking change to signal):** Change `finished` to `Signal(dict)` carrying the full
search result dict.  Cleaner, but breaks the existing `_on_search_finished` slot signature and all
16 tests in `test_gbs_search_dialog.py`.

Option A is recommended to minimize test churn.

### 5c. Dialog renderer — `GBSSearchDialog._build_ui()` and `_on_search_finished()`

Insert two new collapsible/hideable widget groups above the results table in `_build_ui()`:

```
[search row]
[progress bar]
[Artist: label + QListWidget _artist_list]   <-- NEW (hidden when empty)
[Album:  label + QListWidget _album_list]    <-- NEW (hidden when empty)
[results table]
[inline error label]
[pagination row]
[close button]
```

Each panel is a `QLabel` ("Artist:" / "Album:") + a `QListWidget` with fixed max-height
(e.g. 80px — prevents the panels from swamping the song table).  Hide both panels on initial
render and when the list is empty.  Show them only when data arrives.

`_on_search_finished()` / the new `_on_metadata_ready()` slot populates `_artist_list` and
`_album_list` and shows/hides each panel.  `_clear_table()` must also clear and hide both lists.

**PlainText constraint:** `QListWidget.addItem(text)` uses plain text by default; `href` values
are stored as item data (`Qt.ItemDataRole.UserRole`) — not rendered as HTML.  Complies with T-40-04.

### 5d. Click navigation

When the user clicks an artist or album entry in the list, the dialog must navigate to that artist
or album's content.  **The mechanism is a follow-up search, not a new `gbs_api` function**, because:
- The `<p class="artists">` links point to `/artist/<id>` and `/album/<id>` — content pages, not
  filtered search URLs.
- gbs.fm has no `/search?artist_id=` or `/search?album_id=` filter parameter in the URLconf.

Two options for click navigation:

**Option A (reuse search):** Clicking an artist entry fires a new `search()` call with
`query="artist:<name>"` or simply `query="<artist_name>"` — this finds songs matching the artist
name via the existing free-text search.  Simple; does not require a new `gbs_api` function;
may return false positives (other artists whose name contains the substring).

**Option B (new gbs_api endpoint):** Fetch `/artist/<id>` (the artist page HTML), parse the song
table it contains (if any), and display those results.  This would require a new `gbs_api`
function and a new fixture.  More accurate.  Needs verification of the artist-page HTML shape.

The right choice depends on the answer to Open Question §6.1.  If `/artist/<id>` renders a song
table in the same `<table class="songs">` format, Option B is better and reuses `_SongRowParser`
unchanged.  If not, Option A is the safer fallback.

### 5e. Tests

**New or extended fixtures:**
- `search_test_p1.html` already contains both Artist and Album blocks — usable as-is for parser
  tests.
- No new fixture needed for the parser tests.
- `search_test_p2.html` already lacks both blocks — validates the "page > 1 → empty lists" path.
- `search_empty.html` already lacks both blocks — validates the "no results" path.

**New test cases:**
- `test_gbs_api.py`: `test_search_returns_artist_links` — asserts `out["artist_links"]` is a
  non-empty list with `text` and `url` keys when parsing `search_test_p1.html`.
- `test_gbs_api.py`: `test_search_returns_album_links` — same for `album_links`.
- `test_gbs_api.py`: `test_search_page2_has_no_artist_album_links` — asserts both lists are `[]`
  when parsing `search_test_p2.html`.
- `test_gbs_search_dialog.py`: `test_artist_panel_shown_when_links_present` — emit
  `metadata_ready` with a non-empty artist list; assert `_artist_list` is visible and populated.
- `test_gbs_search_dialog.py`: `test_artist_panel_hidden_when_no_links` — emit with empty lists;
  assert panels are hidden.
- `test_gbs_search_dialog.py`: `test_album_panel_populated` — parallel to artist panel test.
- `test_gbs_search_dialog.py`: `test_clear_table_hides_artist_album_panels` — assert `_clear_table`
  hides the new panels.

---

## 6. Open Questions

**6.1 (DECISION REQUIRED) What is the navigation target when clicking an artist or album link?**

The fixture hrefs point to `/artist/<id>` and `/album/<id>` — page-level content URLs, not search
filter parameters.  The team needs to confirm whether:
a) `/artist/<id>` renders an HTML page with a `<table class="songs">` of that artist's tracks
   (which would let us reuse `_SongRowParser` and `_open_with_cookies` to load a filtered song list), or
b) `/artist/<id>` renders an unstructured artist biography/page with no parseable song table,
   requiring the query-based Option A fallback (search by artist name string).

Without this answer, the click-handler cannot be specified.  Recommendation: capture
`/artist/4803` (Testament) with the dev cookies fixture and inspect the HTML before implementing.

**6.2 (UX DECISION) Should the panels auto-collapse when there are no artist/album matches?**

On page 2+ searches and empty searches both blocks are absent from the HTML, so they should
definitely be hidden.  On page 1 with matches they are present.  The question is: if a query
returns songs but zero artist/album block entries (possible if the server omits the blocks even
on page 1 for certain queries), should the panels render as empty lists or be hidden entirely?
Recommendation: hide entirely when `artist_links == []` / `album_links == []` regardless of cause.
Needs user confirmation.

**6.3 (SCOPE) Does clicking an album link navigate into a filtered song view, or to an info page?**

Same question as 6.1 but for albums.  `/album/<id>` is in the URLconf; its HTML shape is unknown.
If it also renders a `<table class="songs">`, the same fix applies to both.

**6.4 (UX DECISION) What is the max height / scrollability of the Artist and Album panels?**

If a query returns 40 artist matches (as "test" does in the fixture — 46 artists listed), an
unconstrained `QListWidget` would dominate the dialog.  A fixed max height (e.g. 80px, showing ~3
rows with a scrollbar) or a collapsed-by-default accordion are both workable.  Needs user
preference.
