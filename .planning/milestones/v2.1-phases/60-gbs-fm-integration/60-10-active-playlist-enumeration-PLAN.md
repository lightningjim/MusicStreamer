---
phase: 60-gbs-fm-integration
plan: 10
type: execute
wave: 6
depends_on: [60-08]
files_modified:
  - musicstreamer/gbs_api.py
  - musicstreamer/ui_qt/now_playing_panel.py
  - tests/test_gbs_api.py
  - tests/test_now_playing_panel.py
autonomous: true
gap_closure: true
requirements: [GBS-01c]
tags: [phase60, gap-closure, html-parser, active-playlist, queue-enumeration]
revision: 2
revision_notes: "Iteration-2 plan-check fixes: (1) re-waved to 6 with depends_on [60-08] to serialize gbs_api.py + tests/test_gbs_api.py + tests/test_now_playing_panel.py edits behind 60-08, (2) added Step 3a to update existing test_gbs_playlist_populates_from_mock_state — replaces queue_summary assertion with queue_rows + enumerated rendering assertions, (3) explicit decision: state['queue_html_snippets'] is RETAINED for backward-compat (zero callers found, zero churn risk)."

user_decisions_required:
  - id: D-10a
    question: "Maximum upcoming-queue rows to enumerate?"
    options: ["all rows (no cap)", "cap at 5", "cap at 10"]
    recommended: "cap at 10 (widget setMaximumHeight=180px naturally shows ~6 rows; 10 leaves scrollback room without QListWidget bloat)"
    locked_default: 10
  - id: D-10b
    question: "Row format for upcoming queue items"
    options: ["{n}. {artist} - {title}", "{n}. {artist} - {title} [{duration}]"]
    recommended: "include duration"
    locked_default: "{n}. {artist} - {title} [{duration}]"
  - id: D-10c
    question: "Disposition of pllength 'Playlist is X long with Y dongs' summary line"
    options: ["replace with enumeration only", "keep summary as additional row", "replace with cleaner 'Queue: X (Y tracks)'"]
    recommended: "replace with enumeration only — diagnosis §5c calls out 'dongs' jargon as user-facing noise"
    locked_default: "replace (drop the pllength summary line entirely)"

must_haves:
  truths:
    - "Active-playlist widget shows ▶ {current track}, then 1..N rows for upcoming queue tracks (one QListWidgetItem per upcoming song), then 'Score: N (Y votes)' last"
    - "Each upcoming row uses the format chosen in D-10b (default: '{n}. {artist} - {title} [{duration}]') and is plain text (no HTML — Pitfall 11/T-40-04)"
    - "queue_summary 'Playlist is X long with Y dongs' is no longer rendered (replaced by enumeration per D-10c default)"
    - "Empty upcoming queue (no adds events with non-playing/non-history rows) shows current track + score row only — no enumeration rows, no crash"
    - "_QueueRowParser correctly skips rows with class containing 'playing' or 'history'; includes everything else (no class / 'odd' / 'even' / etc.)"
    - "Per-row entryid + songid + artist + title + duration are all extracted into the queue_rows dict list"
    - "state['queue_html_snippets'] is RETAINED in _fold_ajax_events output for backward-compat — no callers found, but no churn either"
  artifacts:
    - path: "musicstreamer/gbs_api.py"
      provides: "_QueueRowParser HTMLParser + _parse_adds_html helper + _fold_ajax_events emits queue_rows: list[dict]"
      contains: "_QueueRowParser"
      contains_2: "queue_rows"
    - path: "musicstreamer/ui_qt/now_playing_panel.py"
      provides: "_on_gbs_playlist_ready loops over queue_rows to populate _gbs_playlist_widget"
      contains: "queue_rows"
    - path: "tests/test_gbs_api.py"
      provides: "Parser tests against ajax_cold_start.json fixture"
      contains: "test_fetch_playlist_enumerates_queue"
    - path: "tests/test_now_playing_panel.py"
      provides: "Renderer test asserting QListWidget item count + format; updated test_gbs_playlist_populates_from_mock_state"
      contains: "test_gbs_playlist_renders_enumerated_queue"
  key_links:
    - from: "_fold_ajax_events"
      to: "_parse_adds_html(payload) extending state['queue_rows']"
      via: "for each adds event in /ajax response"
      pattern: "_parse_adds_html"
    - from: "_on_gbs_playlist_ready"
      to: "self._gbs_playlist_widget loop over state['queue_rows']"
      via: "after current-track row, before score row"
      pattern: 'state.get."queue_rows"'
---

<objective>
Close UAT issue T8 (active-playlist widget shows summary line "Playlist is X long with Y dongs" instead of per-row enumeration of upcoming queue tracks). Diagnosis confirms the parser writes raw HTML blobs to `queue_html_snippets` and never parses them; the renderer reads `queue_summary` (the pllength string) and never reads `queue_html_snippets`. The HTML in `tests/fixtures/gbs/ajax_cold_start.json` already contains everything needed (entryid + artist + title + duration + class for playing/history/upcoming discrimination); no new fixtures required.

Purpose: Logged-in user playing GBS.FM sees one row per upcoming queued track, matching what the gbs.fm web UI shows.

Output: New `_QueueRowParser` HTMLParser in `gbs_api.py`, `queue_rows: list[dict]` added to the `_fold_ajax_events` return state, renderer loop in `_on_gbs_playlist_ready` replacing the single summary line, plus parser + renderer tests, plus an in-place update to the existing `test_gbs_playlist_populates_from_mock_state` so it asserts on the new enumerated rendering rather than the removed `queue_summary` line.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/phases/60-gbs-fm-integration/60-CONTEXT.md
@.planning/phases/60-gbs-fm-integration/60-DIAGNOSIS-playlist-enumeration.md
@.planning/phases/60-gbs-fm-integration/60-UAT.md
@.planning/phases/60-gbs-fm-integration/60-02-api-client-SUMMARY.md
@.planning/phases/60-gbs-fm-integration/60-05-active-playlist-SUMMARY.md
@./CLAUDE.md
@musicstreamer/gbs_api.py
@musicstreamer/ui_qt/now_playing_panel.py
@tests/test_gbs_api.py
@tests/test_now_playing_panel.py
@tests/fixtures/gbs/ajax_cold_start.json
@tests/fixtures/gbs/ajax_steady_state.json

<interfaces>
<!-- Existing parser surface — keep stable, ADD queue_rows -->

```python
# musicstreamer/gbs_api.py — current state dict shape from _fold_ajax_events
# DECISION (revision 2): queue_html_snippets is RETAINED for backward-compat.
# Zero production callers found via grep; zero test callers either. The cost
# of removal is non-zero (must scan all branches of _fold_ajax_events that
# initialize/extend it) while the benefit is just dictionary key cleanup.
# Defer removal until/unless a documented caller needs it gone.
state = {
    "user_vote": 0,                  # unchanged
    "score": "no votes",             # unchanged
    "queue_html_snippets": [],       # RETAINED (revision 2 decision)
    "queue_rows": [],                # NEW: list[dict] with parsed upcoming tracks
    "removed_ids": [],               # unchanged
    # ...other keys: now_playing_entryid, now_playing_songid, icy_title,
    # linked_metadata_html, song_length, song_position, queue_summary, last_removal_id
}

# NEW per-row dict shape:
queue_row = {
    "entryid": int,        # from <tr id="NNNNNN">
    "songid": int | None,  # from /song/<id> href if present
    "artist": str,         # from <td class="artistry"><a href='/artist/X'>name</a>
    "title": str,          # from <td><a href='/song/X'>title</a>
    "duration": str,       # from <td class="time">M:SS</td>
}
```

```python
# Existing _SongRowParser at gbs_api.py:286-362 is the precedent to follow.
# It uses html.parser.HTMLParser and anchors on /song/X, /artist/X, /add/X hrefs.
# _QueueRowParser is structurally similar but anchors on <tr id="..."> + <tr class="...">
# to discriminate playing/history/upcoming.
```

```python
# Existing renderer in now_playing_panel.py:965-976 (current — to be patched):
self._gbs_playlist_widget.clear()
icy = state.get("icy_title")
if icy:
    self._gbs_playlist_widget.addItem(QListWidgetItem(f"▶ {icy}"))
# Queue summary for v1 (Pitfall 6 — defensive HTML parsing happens in gbs_api).
summary = state.get("queue_summary")
if summary:
    self._gbs_playlist_widget.addItem(QListWidgetItem(summary))   # REMOVE (per D-10c default)
score = state.get("score")
if score:
    self._gbs_playlist_widget.addItem(QListWidgetItem(f"Score: {score}"))
```
</interfaces>

<wave_strategy>
**Wave 6 (depends_on: [60-08])** — re-waved per iter-2 plan-check.

Reasoning: this plan modifies the same files as 60-08 (`musicstreamer/gbs_api.py`, `tests/test_gbs_api.py`) and the same file as 60-09 (`musicstreamer/ui_qt/now_playing_panel.py`, `tests/test_now_playing_panel.py`). Specific potential conflicts:
- `gbs_api.py`: 60-08 modifies `_NoRedirect` (~lines 170-172) and `import_station` (~lines 528-548). 60-10 modifies `_fold_ajax_events` (~lines 226-262) and adds `_QueueRowParser` after `_SongRowParser` (line 362). Different functions, different anchors — but both touch the same file, so wave separation prevents merge churn.
- `now_playing_panel.py`: 60-09 modifies vote button construction + `_on_gbs_playlist_ready` lines 957-958 (entryid stamping). 60-10 modifies `_on_gbs_playlist_ready` lines 963-976 (renderer block). The two sections are 5 lines apart — high risk of textual collision in parallel.
- `tests/test_gbs_api.py`: 60-08 appends 6 tests at the bottom. 60-10 appends 2 tests at the bottom. Same insertion point → append-merge collision.
- `tests/test_now_playing_panel.py`: 60-09 appends 3 tests near line 1380. 60-10 appends 2 tests after the last GBS vote test. Same neighborhood → append-merge collision.

Depending on 60-08 (not 60-09) is sufficient: 60-08 ships first; 60-10 then sees 60-08's changes when it lands. 60-09 is parallel-safe with 60-08 (no file overlap). 60-11 will depend on 60-10 (declared in 60-11's frontmatter).

After 60-08 lands, anchor _QueueRowParser insertion at "after `_SongRowParser` (~line 362)" — the line number may shift slightly if 60-08 added/removed lines above; use the textual anchor (after `_SongRowParser`'s class body ends), not the line number.
</wave_strategy>

<diagnoses_to_apply>
**T8 root cause (60-DIAGNOSIS-playlist-enumeration.md §2):** Parser stores raw `<tr>` HTML blobs in `queue_html_snippets` and never parses them. Renderer reads only `queue_summary` (the pllength string). RESEARCH.md §"fetch_active_playlist" line 308 explicitly specified `'queue': list[dict]` parsed from `<tr>` rows — never implemented.

**Fix per §5a/5b:** Add `_QueueRowParser` to `gbs_api.py` (analogous to `_SongRowParser` already at lines 286-362). In `_fold_ajax_events`, replace the raw-blob accumulator with a call that parses each `adds` payload and extends a structured `queue_rows` list. In `_on_gbs_playlist_ready`, replace the single `queue_summary` row with a loop over `state["queue_rows"]`.

**Discrimination rule (§5a):** Skip rows where class contains "playing" (already rendered as ▶ via icy_title) OR contains "history" (already played). Include rows with no class, "odd", "even", or any other class as upcoming queue entries.

**Locked user decisions (D-10a, D-10b, D-10c):** Cap at 10 upcoming rows; format `"{n}. {artist} - {title} [{duration}]"`; drop the pllength summary line entirely. Implement these defaults; if the user requests changes after seeing the result, revise in a follow-up plan.

**Revision-2 decision: `state["queue_html_snippets"]` retained.** Plan-check iter-1 flagged ambiguity. Decision: KEEP the key (initialize as `[]`, extend with payload alongside `queue_rows`). Rationale: zero production callers found via grep `queue_html_snippets` across `musicstreamer/`, `tests/`, and `.planning/`; zero test callers either. The cost of removal is non-zero (audit + edit + risk of breaking something undocumented) while the benefit is purely cosmetic. If a future plan wants to remove the key, that's a separate trivial cleanup.
</diagnoses_to_apply>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1 (TDD-RED): Write 4 failing tests for parser + renderer</name>
  <files>tests/test_gbs_api.py, tests/test_now_playing_panel.py</files>
  <behavior>
    - tests/test_gbs_api.py::test_fetch_playlist_enumerates_queue: Load tests/fixtures/gbs/ajax_cold_start.json, monkeypatch _open_with_cookies to return the file contents, call gbs_api.fetch_active_playlist(fake_cookies). Assert state["queue_rows"] is a non-empty list. Assert each row dict has keys {"entryid", "songid", "artist", "title", "duration"}. Assert state["queue_rows"] does NOT include the now-playing entryid (1810809 — the one with class="playing"). Assert state["queue_rows"][0]["entryid"] is one of the 3 upcoming entryids (1810810, 1810811, 1810812 per the diagnosis §4). (Currently fails: state["queue_rows"] does not exist.)
    - tests/test_gbs_api.py::test_queue_parser_skips_playing_and_history: Construct a small in-memory HTML snippet with 4 rows: one class="playing", one class="history", one class="odd", one with no class. Call _parse_adds_html(snippet) directly. Assert it returns exactly 2 rows (the "odd" and the no-class one). (Currently fails: _parse_adds_html does not exist.)
    - tests/test_now_playing_panel.py::test_gbs_playlist_renders_enumerated_queue: Use _construct_gbs_panel(qtbot). Construct a fake state dict: `{"icy_title": "Now Playing - Artist", "score": "5 (3 votes)", "user_vote": 0, "queue_rows": [{"entryid": 100, "songid": 1, "artist": "A1", "title": "T1", "duration": "3:00"}, {"entryid": 101, "songid": 2, "artist": "A2", "title": "T2", "duration": "4:00"}, {"entryid": 102, "songid": 3, "artist": "A3", "title": "T3", "duration": "2:30"}], "now_playing_entryid": 99}`. Stamp `panel._gbs_poll_token` and call `panel._on_gbs_playlist_ready(panel._gbs_poll_token, state)`. Assert `panel._gbs_playlist_widget.count() == 5` (1 ▶ row + 3 queue rows + 1 score row). Assert `panel._gbs_playlist_widget.item(1).text() == "1. A1 - T1 [3:00]"` (per D-10b default format). (Currently fails: renderer ignores queue_rows entirely.)
    - tests/test_now_playing_panel.py::test_gbs_playlist_caps_queue_at_10: Same setup but pass `queue_rows` containing 15 entries. Assert `panel._gbs_playlist_widget.count() == 12` (1 ▶ + 10 capped queue + 1 score). Assert `panel._gbs_playlist_widget.item(10).text().startswith("10.")`. (Currently fails: no cap exists.)

    Use the existing fixture infrastructure: `gbs_fixtures_dir`, `fake_cookies_jar` from tests/conftest.py; `_construct_gbs_panel(qtbot)` from tests/test_now_playing_panel.py. The pre-existing `test_fetch_playlist_cold_start` and `test_fetch_playlist_steady_state` show the monkeypatch pattern for `_open_with_cookies`.
  </behavior>
  <action>
    Append 2 tests to tests/test_gbs_api.py (after test_decode_django_messages_garbage_returns_empty AND after the 60-08 tests added in wave 5 — anchor on the file's last function, not a line number, since 60-08 lands first). Append 2 tests to tests/test_now_playing_panel.py (after the last existing GBS vote test, AND after the 60-09 vote tests added in wave 5).

    For the parser tests, the fixture at `tests/fixtures/gbs/ajax_cold_start.json` is the canonical source. Per the diagnosis §4 it has "four upcoming `<tr>` rows (entryids 1810810, 1810811, 1810812 plus the now-playing 1810809 with class 'playing')". The test should NOT hard-code these numeric entryids if they may drift on re-capture — instead assert (a) at least 1 row in queue_rows, (b) none of the rows have class="playing" or class="history", (c) each row has all 5 expected keys.

    For the renderer tests, build the fake state dict in-test (no fixture needed). The tests directly invoke `_on_gbs_playlist_ready` — no need to mock the worker thread.

    Run pytest -x tests/test_gbs_api.py tests/test_now_playing_panel.py — confirm 4 new tests fail. Commit RED:
    ```
    git add tests/test_gbs_api.py tests/test_now_playing_panel.py
    git commit -m "test(60-10): add failing tests for queue enumeration parser + renderer (T8)"
    ```
  </action>
  <verify>
    <automated>cd /home/kcreasey/OneDrive/Projects/MusicStreamer && python -m pytest tests/test_gbs_api.py tests/test_now_playing_panel.py -x -k "enumerates_queue or queue_parser_skips or renders_enumerated_queue or caps_queue_at_10" 2>&1 | tail -20 | grep -v '^#' | grep -E 'FAILED|PASSED|ERROR'</automated>
  </verify>
  <done>4 new tests fail in the expected ways (KeyError on queue_rows / NameError on _parse_adds_html / count mismatch). RED commit recorded.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2 (TDD-GREEN): Implement _QueueRowParser + _parse_adds_html in gbs_api.py</name>
  <files>musicstreamer/gbs_api.py</files>
  <behavior>
    - New `_QueueRowParser(HTMLParser)` class extracts per-row entryid, artist, title, duration, songid from the `adds` HTML.
    - New helper `_parse_adds_html(html_str: str) -> list[dict]` constructs and feeds the parser, returns the row list.
    - Skip discriminator: rows with class containing "playing" or "history" are not included.
    - `_fold_ajax_events` initializes `state["queue_rows"] = []` and on each `adds` event extends it with the parsed rows.
    - `state["queue_html_snippets"]` is RETAINED (revision-2 decision) — the parsed rows are added in PARALLEL to the raw blobs.
    - tests/test_gbs_api.py: 2 new parser tests pass; all pre-existing tests still pass (including the 60-08 tests that landed in wave 5).
  </behavior>
  <action>
    Add `_QueueRowParser` class to `gbs_api.py` immediately after `_SongRowParser` (around line 362, but anchor textually — wave 5's 60-08 may have shifted line numbers slightly). Mirror `_SongRowParser`'s structure: subclass `html.parser.HTMLParser`, use module-level regex for `/song/<id>` and `/artist/<id>` href patterns, anchor on `<tr id="...">` for the entryid + class.

    Per the diagnosis §5a and the HTML shape in §4, the per-row extraction targets are:
    - `entryid` from `<tr id="NNNNNN">` — capture the `id` attribute on `<tr>` start.
    - `class` from `<tr class="...">` — used to skip "playing" / "history" rows.
    - `artist` from text inside `<td class="artistry"><a href='/artist/X'>NAME</a></td>` — track when we're inside an artistry td.
    - `title` from text inside the next `<a href='/song/X'>TITLE</a>` after the artist anchor.
    - `songid` from the `/song/<id>` href.
    - `duration` from `<td class="time">M:SS</td>`.

    Concrete parser sketch (final code is yours):
    ```python
    class _QueueRowParser(HTMLParser):
        """Parse `adds` event HTML — one or more <tr> rows describing upcoming queue.

        Skips rows with class='playing' (now-playing, rendered separately via icy_title)
        and class='history' (already played). Returns one dict per upcoming row.

        Per-row dict keys: entryid (int), songid (int|None), artist (str), title (str), duration (str).
        Reference: 60-DIAGNOSIS-playlist-enumeration.md §5a.
        """
        _SONG_RE = re.compile(r"^/song/(\d+)$")
        _ARTIST_RE = re.compile(r"^/artist/(\d+)$")

        def __init__(self):
            super().__init__()
            self.rows: list = []
            self._current: Optional[dict] = None
            self._skip_current: bool = False
            self._in_artistry_td: bool = False
            self._in_time_td: bool = False
            self._in_song_anchor: bool = False
            self._in_artist_anchor: bool = False

        def handle_starttag(self, tag, attrs):
            ad = dict(attrs)
            if tag == "tr":
                row_class = (ad.get("class") or "")
                row_id = ad.get("id") or ""
                self._skip_current = ("playing" in row_class) or ("history" in row_class)
                if not self._skip_current and row_id:
                    try:
                        entryid = int(row_id)
                    except ValueError:
                        self._skip_current = True
                        return
                    self._current = {"entryid": entryid, "songid": None,
                                     "artist": "", "title": "", "duration": ""}
                else:
                    self._current = None
            elif self._current and tag == "td":
                td_class = ad.get("class") or ""
                self._in_artistry_td = ("artistry" in td_class)
                self._in_time_td = ("time" in td_class)
            elif self._current and tag == "a":
                href = ad.get("href") or ""
                if self._SONG_RE.match(href):
                    m = self._SONG_RE.match(href)
                    self._current["songid"] = int(m.group(1))
                    self._in_song_anchor = True
                elif self._ARTIST_RE.match(href):
                    self._in_artist_anchor = True

        def handle_endtag(self, tag):
            if tag == "tr":
                if self._current is not None and not self._skip_current:
                    self.rows.append(self._current)
                self._current = None
                self._skip_current = False
            elif tag == "td":
                self._in_artistry_td = False
                self._in_time_td = False
            elif tag == "a":
                self._in_song_anchor = False
                self._in_artist_anchor = False

        def handle_data(self, data):
            if not self._current or self._skip_current:
                return
            txt = data.strip()
            if not txt:
                return
            if self._in_artist_anchor and self._in_artistry_td:
                self._current["artist"] = txt
            elif self._in_song_anchor:
                self._current["title"] = txt
            elif self._in_time_td:
                self._current["duration"] = txt


    def _parse_adds_html(html_str: str) -> list:
        parser = _QueueRowParser()
        try:
            parser.feed(html_str or "")
            parser.close()
        except Exception:
            return []  # Pitfall 6: defensive — bad HTML returns empty, never raises
        return parser.rows
    ```

    Modify `_fold_ajax_events` (around line 226-262) — RETAIN `queue_html_snippets` per revision-2 decision:
    ```python
    state: dict = {
        "user_vote": 0,
        "score": "no votes",
        "queue_html_snippets": [],   # RETAINED for backward-compat (rev-2)
        "queue_rows": [],             # NEW
        "removed_ids": [],
    }
    ...
    elif name == "adds":
        state["queue_html_snippets"].append(payload)   # RETAINED
        state["queue_rows"].extend(_parse_adds_html(payload))
    ```

    Run pytest -x tests/test_gbs_api.py — pre-existing tests + 2 new parser tests pass. Commit GREEN:
    ```
    git add musicstreamer/gbs_api.py
    git commit -m "feat(60-10): _QueueRowParser + queue_rows in fold_ajax_events (T8 parser side)

    Adds HTMLParser-based extraction of per-row (entryid, songid, artist,
    title, duration) from <adds> event HTML, with skip-discriminator for
    class='playing' / class='history' rows. _fold_ajax_events now exposes
    state['queue_rows'] alongside the existing queue_html_snippets (which is
    RETAINED for backward-compat per revision-2 decision — zero callers
    found, but no churn either).

    Refs: .planning/phases/60-gbs-fm-integration/60-DIAGNOSIS-playlist-enumeration.md §5a"
    ```
  </action>
  <verify>
    <automated>cd /home/kcreasey/OneDrive/Projects/MusicStreamer && python -m pytest tests/test_gbs_api.py 2>&1 | tail -5 | grep -v '^#' | grep -E 'passed|failed'</automated>
  </verify>
  <done>All test_gbs_api.py tests pass (24 from 60-08 + 2 new parser tests = 26). 2 renderer tests still failing — to be closed by Task 3. GREEN commit recorded.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3 (TDD-GREEN): Replace queue_summary line with enumerated queue_rows loop in renderer + update existing test_gbs_playlist_populates_from_mock_state</name>
  <files>musicstreamer/ui_qt/now_playing_panel.py, tests/test_now_playing_panel.py</files>
  <behavior>
    - _on_gbs_playlist_ready iterates state["queue_rows"] (with the cap from D-10a)
    - Each upcoming row is added as one QListWidgetItem with format "{n}. {artist} - {title} [{duration}]" (D-10b default)
    - The pllength summary line is no longer rendered (D-10c default)
    - QListWidget item ordering is: [▶ now-playing] + [1..N upcoming] + ["Score: ..."]
    - Existing test_gbs_playlist_populates_from_mock_state is updated: removes the queue_summary assertion, adds queue_rows to the state dict, asserts on enumerated row rendering
    - 2 renderer tests pass; 1 updated test passes; all other now_playing_panel tests still pass (with 60-09's vote tests already landed in wave 5)
  </behavior>
  <action>
    **Step 3a: Update existing `test_gbs_playlist_populates_from_mock_state` (tests/test_now_playing_panel.py:1005-1039).**

    *Why:* the existing test passes `state["queue_summary"] = "Playlist is 11:21 long with 3 dongs"` and asserts `assert any("Playlist is 11:21" in t for t in items)` (line 1037). Per locked D-10c, this plan removes `queue_summary` rendering. After the renderer change in Step 3b, the assertion will fail because no rendered item contains "Playlist is 11:21". The plan-check iter-1 (BLOCKER) flagged this as a regression-blind plan.

    *Resolution chosen (per iter-2 plan-check directive):*
    1. Remove the `assert any("Playlist is 11:21" in t for t in items)` line entirely.
    2. Add `queue_rows` to the state dict so the test exercises the new rendering path.
    3. Assert on enumerated row text.

    *Concrete edit at tests/test_now_playing_panel.py:1019-1039:*

    Replace the state dict from:
    ```python
    state = {
        "now_playing_entryid": 1810736,
        "now_playing_songid": 782491,
        "icy_title": "Crippling Alcoholism - Templeton",
        "queue_summary": "Playlist is 11:21 long with 3 dongs",
        "score": "5.0 (1 vote)",
        "user_vote": 0,
        "queue_html_snippets": [],
        "removed_ids": [],
    }
    ```

    To:
    ```python
    state = {
        "now_playing_entryid": 1810736,
        "now_playing_songid": 782491,
        "icy_title": "Crippling Alcoholism - Templeton",
        # 60-10 / T8: queue_summary is no longer rendered (D-10c). Replace with
        # queue_rows so the test exercises the new enumerated-rendering path.
        "queue_summary": "Playlist is 11:21 long with 3 dongs",  # kept on state dict for parity, but no longer asserted on
        "queue_rows": [
            {"entryid": 1810810, "songid": 1, "artist": "Foo", "title": "Bar", "duration": "3:00"},
            {"entryid": 1810811, "songid": 2, "artist": "Baz", "title": "Quux", "duration": "4:30"},
        ],
        "score": "5.0 (1 vote)",
        "user_vote": 0,
        "queue_html_snippets": [],
        "removed_ids": [],
    }
    ```

    Replace the assertions at lines 1034-1039:
    ```python
    items = [
        panel._gbs_playlist_widget.item(i).text()
        for i in range(panel._gbs_playlist_widget.count())
    ]
    # Now-playing prefixed with arrow marker
    assert any("Crippling Alcoholism - Templeton" in t for t in items)
    # Queue summary
    assert any("Playlist is 11:21" in t for t in items)
    # Score
    assert any("5.0 (1 vote)" in t for t in items)
    ```

    With:
    ```python
    items = [
        panel._gbs_playlist_widget.item(i).text()
        for i in range(panel._gbs_playlist_widget.count())
    ]
    # Now-playing prefixed with arrow marker (unchanged)
    assert any("Crippling Alcoholism - Templeton" in t for t in items)
    # 60-10 / T8: queue_rows enumerated per D-10b — was queue_summary "Playlist is 11:21" (REMOVED).
    assert any("1. Foo - Bar [3:00]" in t for t in items)
    assert any("2. Baz - Quux [4:30]" in t for t in items)
    # 60-10 / T8: pllength summary line is NOT rendered (D-10c).
    assert not any("Playlist is 11:21" in t for t in items)
    # Score (unchanged)
    assert any("5.0 (1 vote)" in t for t in items)
    ```

    **Step 3b: Modify the renderer block in `now_playing_panel.py`** at lines 963-976 (within `_on_gbs_playlist_ready`).

    Replace the existing block:
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

    With:
    ```python
    self._gbs_playlist_widget.clear()
    icy = state.get("icy_title")
    if icy:
        # Pitfall 11: PlainText (QListWidgetItem default).
        self._gbs_playlist_widget.addItem(QListWidgetItem(f"▶ {icy}"))
    # 60-10 / T8: enumerate upcoming queue from parsed rows (per D-10a max 10 rows).
    queue_rows = state.get("queue_rows") or []
    for n, row in enumerate(queue_rows[:_GBS_QUEUE_MAX_ROWS], start=1):
        artist = (row.get("artist") or "").strip()
        title = (row.get("title") or "").strip()
        duration = (row.get("duration") or "").strip()
        # D-10b: "{n}. {artist} - {title} [{duration}]"
        if duration:
            label = f"{n}. {artist} - {title} [{duration}]"
        else:
            label = f"{n}. {artist} - {title}"
        self._gbs_playlist_widget.addItem(QListWidgetItem(label))
    # D-10c: pllength summary intentionally not rendered ('dongs' jargon).
    score = state.get("score")
    if score:
        self._gbs_playlist_widget.addItem(QListWidgetItem(f"Score: {score}"))
    ```

    Add a module-level constant near the top of `now_playing_panel.py` (next to other Phase 60 constants — search for `_GBS_` prefix to find the right neighborhood, or add near the other module-level constants if none exist):
    ```python
    # Phase 60 60-10 / D-10a: cap upcoming queue rendering. The widget already has
    # setMaximumHeight(180) (~6 rows visible without scroll), so 10 leaves scroll
    # room without bloating the QListWidget item count.
    _GBS_QUEUE_MAX_ROWS = 10
    ```

    Run pytest -x tests/test_now_playing_panel.py — all tests pass (60-09's 74-test baseline + 2 new renderer tests + the updated test_gbs_playlist_populates_from_mock_state). Commit GREEN:
    ```
    git add musicstreamer/ui_qt/now_playing_panel.py tests/test_now_playing_panel.py
    git commit -m "feat(60-10): renderer enumerates queue_rows (max 10) instead of pllength summary (T8)

    _on_gbs_playlist_ready loops over state['queue_rows'] (parsed in gbs_api by
    60-10 Task 2). Format per D-10b: '{n}. {artist} - {title} [{duration}]'.
    Cap per D-10a: 10 upcoming rows. The pllength 'Playlist is X long with Y
    dongs' line is no longer rendered (D-10c — gbs.fm-internal jargon).

    Test update: test_gbs_playlist_populates_from_mock_state now asserts on
    enumerated queue_rows rendering instead of the removed queue_summary
    line; the queue_rows assertion replaces the 'Playlist is 11:21' assertion
    that would otherwise fail after this renderer change.

    Refs: .planning/phases/60-gbs-fm-integration/60-DIAGNOSIS-playlist-enumeration.md §5b/c"
    ```
  </action>
  <verify>
    <automated>cd /home/kcreasey/OneDrive/Projects/MusicStreamer && python -m pytest tests/test_now_playing_panel.py tests/test_gbs_api.py 2>&1 | tail -10 | grep -v '^#' | grep -E 'passed|failed'</automated>
  </verify>
  <done>All tests pass: now_playing_panel.py (74 from 60-09 + 2 new renderer + 1 updated = 76 effective), test_gbs_api.py (26 from 60-08 + 60-10 Task 2). GREEN commit recorded.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| gbs.fm /ajax HTML → parser | Untrusted HTML inserted into QListWidget |
| Parser → renderer | Structured dict (entryid/artist/title/duration) — plain types |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-60-10-01 | Information Disclosure | HTML injection via artist/title containing markup | mitigate | QListWidgetItem renders PlainText by default (T-40-04 / Pitfall 11). Parser stores plain `str` from `handle_data`, never raw markup. |
| T-60-10-02 | Tampering | Parser misidentifies playing/history rows as upcoming | mitigate | Skip discriminator covers 'playing' OR 'history' substrings in class attribute; covered by test_queue_parser_skips_playing_and_history. |
| T-60-10-03 | DoS | Malicious gbs.fm response with thousands of `<tr>` rows | mitigate | _GBS_QUEUE_MAX_ROWS=10 caps the QListWidget population regardless of parser output size. |
| T-60-10-04 | Tampering | Malformed HTML raises in parser | mitigate | _parse_adds_html wraps feed/close in try/except → returns [] on any exception (Pitfall 6 defensive). |
</threat_model>

<verification>
- pytest tests/test_gbs_api.py shows all tests pass (24 from 60-08 wave-5 + 2 new parser tests = 26).
- pytest tests/test_now_playing_panel.py shows all tests pass (74 from 60-09 wave-5 + 2 new renderer + 1 updated = effective 76 — the "updated" test counts in the same name).
- pytest tests/test_gbs_search_dialog.py + tests/test_main_window_integration.py + tests/test_stream_ordering.py all still pass.
- grep -c '_QueueRowParser' musicstreamer/gbs_api.py >= 1 (definition).
- grep -c 'queue_rows' musicstreamer/gbs_api.py >= 3 (state init + extend + parser docstring/comment).
- grep -c 'queue_rows' musicstreamer/ui_qt/now_playing_panel.py >= 2 (state.get + loop).
- grep -c '_GBS_QUEUE_MAX_ROWS' musicstreamer/ui_qt/now_playing_panel.py >= 2 (constant + slice usage).
- grep -c 'queue_html_snippets' musicstreamer/gbs_api.py >= 2 (state init + extend) — RETAINED key is still emitted.
- Manual reproduction: log into GBS.FM, play it, observe ▶ current track row + 1..N upcoming rows in `{n}. Artist - Title [duration]` format + Score row at the bottom. Pllength "Y dongs" text no longer appears.
</verification>

<success_criteria>
- T8 closed: active-playlist widget shows enumerated upcoming queue (one row per upcoming song), no longer the pllength summary.
- All test_now_playing_panel.py tests pass — broken down as: 73 untouched + 1 UPDATED (test_gbs_playlist_populates_from_mock_state, queue_summary assertion removed; queue_rows enumeration assertions added) + 2 new (Task 1).
- All test_gbs_api.py tests pass: 24 from 60-08 wave-5 + 2 new parser tests = 26.
- No regression in test_gbs_search_dialog.py, test_main_window_integration.py, test_stream_ordering.py.
- `state["queue_html_snippets"]` retained (revision-2 decision); zero key removal churn.
- Three atomic commits: 1 RED (failing tests), 2 GREEN (parser, renderer + test update).
</success_criteria>

<output>
After completion, create `.planning/phases/60-gbs-fm-integration/60-10-active-playlist-enumeration-SUMMARY.md` per the standard summary template, including:
- Frontmatter: requires=[60-02, 60-05, 60-08], provides=["_QueueRowParser", "queue_rows in state", "enumerated renderer"], requirements-completed=[GBS-01c]
- Sections: Performance / Accomplishments / Task Commits / Files Modified / Decisions Made (record D-10a=10, D-10b=with-duration, D-10c=replace, queue_html_snippets=retained per rev-2) / TDD Gate Compliance / Deviations / Threat Flags / Self-Check
- Note in Deviations section: test_gbs_playlist_populates_from_mock_state was updated in-place (queue_summary assertion replaced with queue_rows enumeration assertions); documented in revision-2 of this plan.
- Surface any user feedback hooks (if user wants the pllength summary back, capture as a new gap or revise this plan with D-10c flipped)
</output>
