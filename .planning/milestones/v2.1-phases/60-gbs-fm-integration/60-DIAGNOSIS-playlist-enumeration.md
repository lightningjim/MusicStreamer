---
phase: 60
diagnosis: playlist-enumeration
bug: T8
severity: major
diagnosed: 2026-05-04
---

# T8 Diagnosis: Active-Playlist Widget Shows Summary Only (No Queue Enumeration)

## 1. Root Cause

The parser (`_fold_ajax_events`) stores the raw HTML blobs from the `adds` event in `queue_html_snippets` but never parses them into structured rows; the renderer (`_on_gbs_playlist_ready`) never reads `queue_html_snippets` at all — it only renders `queue_summary` (the `pllength` string), leaving the per-track upcoming queue invisible.

---

## 2. Mechanism — Exact Code Path

### Parser side (`musicstreamer/gbs_api.py`, `_fold_ajax_events`)

Lines 254–261 of `gbs_api.py`:

```python
elif name == "adds":
    state["queue_html_snippets"].append(payload)   # raw HTML appended, never parsed
...
elif name == "pllength":
    state["queue_summary"] = (payload or "").strip()  # e.g. "Playlist is 11:34 long with 3 dongs"
```

`fetch_active_playlist` returns a state dict with:
- `queue_html_snippets`: list of raw HTML `<tr>` strings (one per `adds` event, each containing multiple `<tr>` rows for the upcoming tracks)
- `queue_summary`: the `pllength` display string

No HTML parsing of `queue_html_snippets` ever happens. The function has no `_QueueRowParser` or equivalent. The per-track data is present in the raw blobs but is never extracted into structured fields (e.g. `queue_rows: list[dict]`).

### Renderer side (`musicstreamer/ui_qt/now_playing_panel.py`, `_on_gbs_playlist_ready`)

Lines 965–976:

```python
self._gbs_playlist_widget.clear()
icy = state.get("icy_title")
if icy:
    now_item = QListWidgetItem(f"▶ {icy}")
    self._gbs_playlist_widget.addItem(now_item)
# Queue summary for v1 (Pitfall 6 — defensive HTML parsing happens in gbs_api).
summary = state.get("queue_summary")
if summary:
    self._gbs_playlist_widget.addItem(QListWidgetItem(summary))
score = state.get("score")
if score:
    self._gbs_playlist_widget.addItem(QListWidgetItem(f"Score: {score}"))
```

The renderer never touches `state["queue_html_snippets"]`. It only reads:
1. `icy_title` → "▶ {current track}"
2. `queue_summary` → raw `pllength` string (e.g. "Playlist is 11:34 long with 3 dongs")
3. `score` → "Score: 5.0 (4 votes)"

The comment on line 971 ("Queue summary for v1 (Pitfall 6 — defensive HTML parsing happens in gbs_api)") is the smoking gun: the planner intended HTML parsing to happen in `gbs_api`, but it was never implemented. The renderer was written to consume an already-parsed `queue_rows` list that does not exist.

---

## 3. Scope Determination — Implementation Gap, Not a Planning Gap

This is an **implementation gap**: the research and planning documents explicitly specified per-row enumeration, but the implementation shipped summary-only.

Evidence:

- **RESEARCH.md line 308:** The documented return shape for `fetch_active_playlist` explicitly includes `'queue': list[dict]` — "parsed `<tr>` rows from `adds` event with `class!='playing'` and `class!='history'`". This is the per-track upcoming queue.
- **RESEARCH.md lines 320–343:** Full HTML row parsing strategy documented, including extraction targets per row (artist, title, duration, entryid, class for playing/history/upcoming discrimination).
- **RESEARCH.md line 882 (Code Example 2):** The researcher's reference implementation stores `queue_html_snippets` as a stepping stone, with the comment "adds HTML is parsed similarly for queue rows" — signaling the intent to parse. The actual production `_fold_ajax_events` at `gbs_api.py:226–262` copied the `queue_html_snippets` accumulator but never added the parsing step.
- **CONTEXT.md D-06:** "shows current and/or upcoming tracks" — plural tracks, not a summary count.

The planner's comment at `now_playing_panel.py:971` — "Queue summary for v1 (Pitfall 6 — defensive HTML parsing happens in gbs_api)" — suggests this was treated as a v1 simplification, but the planner did not document it as an explicit scope reduction. No plan or summary document says "per-row enumeration deferred."

**Conclusion:** The v1 shipping decision to use `queue_summary` instead of parsed rows was a local implementation shortcut that was never flagged as a deferred scope item.

---

## 4. Data-Availability Check — What the Fixtures Actually Contain

Both `ajax_cold_start.json` and `ajax_steady_state.json` contain:

- One `adds` event whose payload is a multi-`<tr>` HTML string. The cold-start fixture's `adds` payload contains **four upcoming `<tr>` rows** (entryids 1810810, 1810811, 1810812 plus the now-playing 1810809 with class `playing`).

Per-row data extractable from each `<tr>`:
- `entryid` — from `<tr id="NNNNNN">`
- `artist` — from `<td class="artistry"><a href='/artist/X'>Artist Name</a></td>`
- `title` — from `<td><a href='/song/X'>Track Title</a></td>`
- `duration` — from `<td class="time">4:00</td>`
- `row class` — `"playing"` (now playing), `"even"`/`"odd"` (upcoming), `"history"` (played)
- `songid` — from `/song/<id>` href

The `pllength` event payload in both fixtures is `"\nPlaylist is 11:34 long with 3 dongs\n"` (whitespace-wrapped). "Dongs" is confirmed gbs.fm jargon for queued songs — the site's own UI text, not a typo (also appears in RESEARCH.md line 466: "You have 48 tokens, so you can add extra dongs to the playlist!").

The per-row data is present in the fixture and fully sufficient. Nothing needs to be fetched from the network beyond what the existing `/ajax` poll already returns.

---

## 5. Fix Outline

### 5a. Parser changes needed: YES — add `_QueueRowParser` to `gbs_api.py`

Add an HTML parser (analogous to `_SongRowParser` for search results, already at `gbs_api.py:286–360`) that extracts per-row data from the `adds` HTML blobs.

Extraction targets per `<tr>`:
- Skip rows where `class` contains `"playing"` (that's the now-playing row, already rendered via `icy_title`)
- Skip rows where `class` contains `"history"` (already played, not upcoming)
- Include rows with no special class (or just odd/even) as upcoming queue entries

Per-row fields to extract: `entryid` (from `<tr id>`), `artist`, `title`, `duration`, `songid`.

In `_fold_ajax_events`, replace the raw accumulator:
```python
# current (stores raw HTML):
elif name == "adds":
    state["queue_html_snippets"].append(payload)
```
with a call that parses the HTML and extends a structured `queue_rows` list:
```python
elif name == "adds":
    state["queue_rows"].extend(_parse_adds_html(payload))
```

Initialize `state["queue_rows"] = []` in the starting dict alongside `queue_html_snippets` (or replace it). `queue_html_snippets` can be retained for debugging/testing or removed — it is not consumed by anything in production.

### 5b. Renderer changes needed: YES — `_on_gbs_playlist_ready` in `now_playing_panel.py`

Replace the `queue_summary` single-item render with a loop over `queue_rows`:

Rendering pattern:
1. "▶ {icy_title}" — now-playing row (unchanged)
2. For each row in `state.get("queue_rows", [])`:
   - `"{n}. {artist} - {title}"` where `n` is 1-based position
   - One `QListWidgetItem` per row
3. "Score: {score}" — score row (unchanged)

### 5c. Should the summary line be retained alongside enumeration, or replaced?

**Recommendation: replace with enumeration.** The `pllength` string ("Playlist is 11:34 long with 3 dongs") duplicates information now implicit in the count of rendered rows, and its gbs.fm-internal jargon ("dongs") is user-facing noise. If the total queue duration is considered useful UI, the duration portion ("11:34 long") could be extracted from the string and displayed separately as a subtitle. This is a user-decision point (see Section 6).

---

## 6. Open Questions (User Decision Points)

1. **How many upcoming tracks to show?** The `adds` HTML in the cold-start fixture has 4 rows (1 playing + 3 upcoming). In steady state there could be more or fewer. Should the renderer show all of them, or cap at N (e.g. 5 or 10)? The widget already has `setMaximumHeight(180)` (~6 rows), so the physical display naturally caps, but a soft limit prevents excess QListWidgetItems.

2. **Should the summary line ("Playlist is X long with Y dongs") be replaced, retained as a secondary line, or rephrased?** The "dongs" jargon is from gbs.fm's own API and is rendered verbatim. If the user wants a cleaner string, the duration can be extracted from the `pllength` text and displayed as "Queue: 11:34 (3 tracks)" or similar, or the line can be dropped entirely once per-row enumeration is in place.

3. **Row format for upcoming tracks.** `"{n}. {artist} - {title}"` is the recommended default (matches gbs.fm web UI's artist/title columns). Duration could be appended: `"{n}. {artist} - {title} [{duration}]"`. User preference on verbosity.

4. **Disposition of `queue_html_snippets` in the parser return dict.** It is not consumed anywhere in production. It can be removed from `_fold_ajax_events`'s starting state or retained for test/debug purposes. Tests that assert `state["queue_html_snippets"] == []` will need updating if it is removed.

5. **`_QueueRowParser` placement.** It can live in `gbs_api.py` (alongside `_SongRowParser`) or be a module-private function. The `_SongRowParser` precedent argues for `gbs_api.py`.
