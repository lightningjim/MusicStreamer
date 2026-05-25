---
phase: 60-gbs-fm-integration
plan: 11
type: execute
wave: 7
depends_on: [60-10]
files_modified:
  - scripts/gbs_capture_fixtures.sh
  - tests/fixtures/gbs/artist_4803.html
  - tests/fixtures/gbs/album_1488.html
  - musicstreamer/gbs_api.py
  - musicstreamer/ui_qt/gbs_search_dialog.py
  - tests/test_gbs_api.py
  - tests/test_gbs_search_dialog.py
autonomous: false
gap_closure: true
requirements: [GBS-01e]
tags: [phase60, gap-closure, search, artist-album-panels, fixture-capture, html-parser, qt-dialog]
revision: 2
revision_notes: "Iteration-2 plan-check fixes: (1) re-waved to 7 with depends_on [60-10] to serialize gbs_api.py + tests/test_gbs_api.py edits behind 60-10 (60-10 adds _QueueRowParser after _SongRowParser; this plan now anchors _ArtistAlbumParser AFTER _QueueRowParser to make the insertion explicit), (2) added cookie-expiry hard date guard to Task 0 verification (compare date against 2026-05-17), (3) Task 4 mixed-option ambiguity resolved — Task 0 must lock D-11a as one of four discrete shapes (artist-only Option B / album-only Option B / both Option B / both Option A / mixed) and Task 4 enumerates all five concrete shapes, (4) added defensive ordering comment in _GbsSearchWorker.run() requiring metadata_ready.emit AFTER finished.emit (Step 3a). autonomous: false unchanged (Task 0 checkpoint)."

user_decisions_required:
  - id: D-11a
    question: "What does /artist/<id> return — a parseable <table class='songs'> of that artist's tracks, or an unstructured biography page? (And the same question for /album/<id>.)"
    options: ["both have <table class='songs'> — Option B for both surfaces", "only artist has <table class='songs'> — Option B for artist, Option A for album", "only album has <table class='songs'> — Option A for artist, Option B for album", "neither has <table class='songs'> — Option A for both surfaces"]
    recommended: "captured fixture confirms it (Task 0); planner will lock the choice based on grep count of '<table class=\"songs\"' on each captured page"
    locked_default: "REQUIRES CAPTURE — Task 0 captures /artist/4803 + /album/1488; the grep result locks D-11a as one of the 4 enumerated shapes; Task 4 then collapses to a single concrete test shape"
    requires_checkpoint: true
  - id: D-11b
    question: "Max-height of the Artist + Album QListWidget panels"
    options: ["80px (~3 rows w/ scroll)", "120px (~5 rows w/ scroll)"]
    recommended: "80px — diagnosis §5c notes 40+ artist matches possible for popular queries; capping at 80px prevents the panels from dominating the dialog"
    locked_default: 80
  - id: D-11c
    question: "Hide-when-empty behavior for the panels"
    options: ["always rendered (empty list when no matches)", "hidden entirely when artist_links/album_links is empty"]
    recommended: "hidden — diagnosis §6.2 default; matches gbs.fm behavior on page 2+ and empty searches"
    locked_default: "hide when empty"

must_haves:
  truths:
    - "When the user searches and the response is page 1 with non-empty Artist/Album blocks, the dialog shows two new panels above the song results table: 'Artist:' and 'Album:' QListWidgets populated with the parsed link entries"
    - "Each panel entry displays the artist or album name as plain text; the URL (e.g. '/artist/4803') is stored as item data (Qt.UserRole), not rendered"
    - "Clicking an artist or album entry navigates per locked D-11a (Option A free-text search OR Option B fetch + reparse)"
    - "On page 2+ or no matches, the Artist:/Album: panels are hidden entirely (D-11c default)"
    - "Existing search/submit/pagination/auth-expired flows still work (no regression in 16 pre-existing tests)"
    - "Captured fixtures tests/fixtures/gbs/artist_<id>.html and album_<id>.html exist and drive the parser tests"
    - "_GbsSearchWorker.run() emits finished BEFORE metadata_ready, with a defensive comment in source pinning the ordering invariant"
  artifacts:
    - path: "scripts/gbs_capture_fixtures.sh"
      provides: "Updated to capture /artist/<id> and /album/<id> HTML"
    - path: "tests/fixtures/gbs/artist_4803.html"
      provides: "Live-captured artist page (Testament, /artist/4803)"
    - path: "tests/fixtures/gbs/album_1488.html"
      provides: "Live-captured album page (#gbs-fm's greatest shits, /album/1488)"
    - path: "musicstreamer/gbs_api.py"
      provides: "_ArtistAlbumParser HTMLParser + search() returns artist_links + album_links keys; conditionally fetch_artist_songs/fetch_album_songs"
      contains: "_ArtistAlbumParser"
      contains_2: "artist_links"
    - path: "musicstreamer/ui_qt/gbs_search_dialog.py"
      provides: "_artist_list + _album_list QListWidgets with hide-when-empty; metadata_ready Signal; click handlers per locked D-11a"
      contains: "_artist_list"
      contains_2: "_album_list"
  key_links:
    - from: "_GbsSearchWorker.run"
      to: "emits both finished and metadata_ready signals from same gbs_api.search return dict"
      via: "Option A signal split — keeps existing finished signature stable; emit ordering: finished BEFORE metadata_ready (defensive pin)"
      pattern: "metadata_ready"
    - from: "GBSSearchDialog._build_ui"
      to: "_artist_list + _album_list panels above _results_table"
      via: "QVBoxLayout insertion between _progress and _results_table"
      pattern: "_artist_list.setVisible"
    - from: "_artist_list.itemActivated / itemClicked"
      to: "navigation handler (per locked D-11a — Option A free-text search OR Option B fetch_artist_songs)"
      via: "bound-method signal connection (QA-05)"
      pattern: "_on_artist_link_clicked"
---

<objective>
Close UAT issue T12 (search dialog missing Artist:/Album: hyperlink panels that gbs.fm's web search shows above the song results table). Diagnosis confirms this is a planning scope gap (RESEARCH.md line 422 explicitly descoped these blocks), not an implementation defect — the canonical fixture `tests/fixtures/gbs/search_test_p1.html` already contains both `<p class="artists">` blocks, but `_SongRowParser` was deliberately written to ignore them.

This plan also has ONE OPEN USER DECISION (D-11a) that requires a fixture capture before downstream tasks can be specified deterministically: does `/artist/<id>` (and `/album/<id>`) render a `<table class="songs">` we can parse with the existing `_SongRowParser`, or is it an unstructured biography page? Task 0 captures the fixture; the result determines whether navigation uses Option B (fetch + reparse) or Option A (free-text search fallback) for each surface independently.

Purpose: Search dialog mirrors gbs.fm's web UI — Artist:/Album: panels visible above the song table on page 1 with matches; clicking a link navigates to that artist's or album's tracks.

Output: New parser `_ArtistAlbumParser` in `gbs_api.py`; updated `search()` return dict; new `_artist_list` + `_album_list` panels in `GBSSearchDialog`; click navigation per locked D-11a; fixture-capture script update; new tests.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/phases/60-gbs-fm-integration/60-CONTEXT.md
@.planning/phases/60-gbs-fm-integration/60-DIAGNOSIS-search-artist-album.md
@.planning/phases/60-gbs-fm-integration/60-UAT.md
@.planning/phases/60-gbs-fm-integration/60-RESEARCH.md
@.planning/phases/60-gbs-fm-integration/60-02-api-client-SUMMARY.md
@.planning/phases/60-gbs-fm-integration/60-07-search-submit-SUMMARY.md
@./CLAUDE.md
@musicstreamer/gbs_api.py
@musicstreamer/ui_qt/gbs_search_dialog.py
@tests/test_gbs_api.py
@tests/test_gbs_search_dialog.py
@tests/fixtures/gbs/search_test_p1.html
@tests/fixtures/gbs/search_test_p2.html
@tests/fixtures/gbs/search_empty.html
@scripts/gbs_capture_fixtures.sh

<interfaces>
<!-- Existing search() / GBSSearchDialog surface — extend, don't break -->

```python
# musicstreamer/gbs_api.py — current search() return shape (PRESERVE)
def search(query: str, page: int, cookies: cookielib.MozillaCookieJar) -> dict:
    return {
        "results": list[dict],     # unchanged — KEEP existing keys
        "page": int,               # unchanged
        "total_pages": int,        # unchanged
        # NEW (this plan):
        "artist_links": list[dict],  # [{"text": str, "url": str}, ...]; [] when no matches/page>1
        "album_links": list[dict],   # same shape
    }
```

```python
# musicstreamer/ui_qt/gbs_search_dialog.py — current _GbsSearchWorker (PRESERVE finished signal shape)
class _GbsSearchWorker(QThread):
    finished = Signal(list, int, int)   # (results, page, total_pages) — KEEP
    error = Signal(str)
    # NEW (this plan):
    metadata_ready = Signal(list, list)  # (artist_links, album_links)

    def run(self):
        out = gbs_api.search(self._query, self._page, self._cookies)
        # ORDERING INVARIANT (60-11 / T12, defensive — see comment in source):
        # finished MUST emit BEFORE metadata_ready. _on_search_finished calls
        # _render_results -> _clear_table which HIDES the artist/album panels.
        # _on_metadata_ready then re-shows them by populating the lists. If
        # metadata_ready emits first, _clear_table will hide the panels we
        # just populated.
        self.finished.emit(...)            # MUST be first
        self.metadata_ready.emit(           # MUST be after finished
            list(out.get("artist_links", [])),
            list(out.get("album_links", [])),
        )
```

```python
# Existing _SongRowParser (gbs_api.py:286-362) anchors on <table class="songs"> — PRESERVE.
# Ignores <p class="artists"> blocks per its docstring — that's fine; the new parser handles them.
#
# Wave-6's 60-10 added _QueueRowParser AFTER _SongRowParser. So the file order
# at the time this plan executes is:
#   _SongRowParser (existing)
#   _QueueRowParser (added by 60-10 in wave 6)
#   <-- _ArtistAlbumParser inserts HERE (after _QueueRowParser, before search())
# This makes the insertion anchor explicit: "after _QueueRowParser", not "after _SongRowParser".
```

```python
# Existing GBSSearchDialog._build_ui layout order (gbs_search_dialog.py:154-226):
#   [search row]
#   [progress bar]
#   [results table]              <-- INSERT artist_list + album_list ABOVE this
#   [inline error label]
#   [pagination row]
#   [close button]
```
</interfaces>

<wave_strategy>
**Wave 7 (depends_on: [60-10])** — re-waved per iter-2 plan-check.

Reasoning: this plan modifies the same files as 60-10 — `musicstreamer/gbs_api.py` (60-10 adds `_QueueRowParser` after `_SongRowParser`; this plan adds `_ArtistAlbumParser` after `_QueueRowParser`) and `tests/test_gbs_api.py` (both append at the bottom). Running them in parallel would cause:
- A class-insertion conflict at the "after _SongRowParser" anchor (both 60-10 and 60-11 originally targeted the same anchor point in iter-1).
- Append-merge collisions in tests/test_gbs_api.py.

By chaining 60-11 → 60-10 → 60-08 (wave 7 → wave 6 → wave 5), the file ordering inside `gbs_api.py` becomes deterministic: `_SongRowParser` → `_QueueRowParser` (60-10) → `_ArtistAlbumParser` (60-11). The anchor change for this plan ("after _QueueRowParser") makes that ordering explicit.

This plan does NOT modify `now_playing_panel.py` (which is touched by 60-09 and 60-10), so the `now_playing_panel.py` chain is satisfied independently of this plan's wave.
</wave_strategy>

<diagnoses_to_apply>
**T12 root cause (60-DIAGNOSIS-search-artist-album.md §1):** Planning scope gap — RESEARCH.md line 422 descoped the Artist/Album panels for v1; `_SongRowParser` docstring at gbs_api.py:293-295 explicitly cites D-08e ("only song results count"). The HTML data for both panels is present in `tests/fixtures/gbs/search_test_p1.html` and unparseable from current code.

**Fix per §5a:** Add `_ArtistAlbumParser(HTMLParser)` that detects `<p class="artists">`, reads the leading text node ("Artists:" vs "Albums:") to discriminate the two blocks, and collects `(text, href)` pairs from each `<li><a href="...">text</a></li>`. Per §2a: "GBS.FM reuses the CSS class 'artists' for both the Artist and Album paragraphs; the distinction is the paragraph's leading text" — the parser MUST inspect leading text, not just the class attribute.

**Fix per §5b:** Add `metadata_ready` Signal to `_GbsSearchWorker` (Option A — minimal change, keeps existing 16 tests stable). Don't change `finished` signal shape. **Defensive ordering invariant (iter-2):** `metadata_ready.emit` MUST follow `finished.emit` — see Step 3a comment block.

**Fix per §5c:** Insert `_artist_list` + `_album_list` QListWidget panels above the results table; populate via `_on_metadata_ready` slot; hide entirely when both lists are empty (per locked D-11c default).

**Fix per §5d (gated by D-11a):** Click navigation strategy depends on what `/artist/<id>` and `/album/<id>` return. Task 0 captures the live fixtures and runs `grep -c '<table class="songs"'` against each captured HTML. The grep results lock D-11a as one of four discrete shapes:
- **D-11a Shape 1: both have table** → Option B for both surfaces (fetch_artist_songs + fetch_album_songs reuse `_SongRowParser`).
- **D-11a Shape 2: only artist has table** → Option B for artist, Option A for album.
- **D-11a Shape 3: only album has table** → Option A for artist, Option B for album.
- **D-11a Shape 4: neither has table** → Option A for both surfaces (free-text search fallback for both).

Task 4 then enumerates the test variants per the locked shape (see Task 4 below).
</diagnoses_to_apply>
</context>

<tasks>

<task type="checkpoint:human-action" gate="blocking">
  <name>Task 0: Capture /artist/&lt;id&gt; and /album/&lt;id&gt; fixtures + lock D-11a</name>
  <what-built>
    The dev cookies path (D-04a) is `~/.local/share/musicstreamer/dev-fixtures/gbs.fm.cookies.txt`. Plan 60-01 confirmed it was present at the time of original capture (2026-05-04); session expires 2026-05-17 per 60-RESEARCH.md. If the cookies have expired since then, this task surfaces the auth-refresh requirement before any downstream work is wasted.

    Steps performed by Claude (all automated — this checkpoint exists only to surface the locked D-11a decision before the rest of the plan proceeds):

    1. **Cookie expiry hard guard (run BEFORE the capture):**
       ```bash
       if [ "$(date +%Y%m%d)" -ge "20260517" ]; then
           echo "WARNING: dev cookies near/past expiry (today >= 2026-05-17)."
           echo "Refresh ~/.local/share/musicstreamer/dev-fixtures/gbs.fm.cookies.txt before capturing."
           exit 1
       fi
       echo "OK: dev cookies are within their freshness window (today < 2026-05-17)."
       ```
       Run this guard FIRST. If it exits non-zero, surface the cookie-refresh requirement to the user via the checkpoint before attempting any HTTP capture.

    2. Read `scripts/gbs_capture_fixtures.sh` to find the existing pattern.
    3. Append two new curl invocations to the script:
       ```bash
       # 14. /artist/<id> — Testament (4803, present in search_test_p1.html artist block)
       curl -sS -b "$COOKIES" "$BASE/artist/4803" > "$OUT/artist_4803.html"

       # 15. /album/<id> — #gbs-fm's greatest shits (1488, present in search_test_p1.html album block)
       curl -sS -b "$COOKIES" "$BASE/album/1488" > "$OUT/album_1488.html"
       ```
    4. Run `bash scripts/gbs_capture_fixtures.sh` against live gbs.fm.
    5. Inspect the captured HTML:
       ```bash
       grep -c '<table class="songs"' tests/fixtures/gbs/artist_4803.html
       grep -c '<table class="songs"' tests/fixtures/gbs/album_1488.html
       ```
    6. Lock D-11a based on the grep results:
       - artist >=1 AND album >=1 → D-11a Shape 1 (both Option B)
       - artist >=1 AND album == 0 → D-11a Shape 2 (artist Option B, album Option A)
       - artist == 0 AND album >=1 → D-11a Shape 3 (artist Option A, album Option B)
       - artist == 0 AND album == 0 → D-11a Shape 4 (both Option A)
    7. Commit the fixture + script updates:
       ```
       git add scripts/gbs_capture_fixtures.sh tests/fixtures/gbs/artist_4803.html tests/fixtures/gbs/album_1488.html
       git commit -m "test(60-11): capture /artist/4803 + /album/1488 fixtures for navigation tests (T12 Task 0)"
       ```
    8. Report findings to the user via this checkpoint.
  </what-built>
  <how-to-verify>
    The user is asked to confirm BOTH fixtures captured cleanly AND lock D-11a based on the inspection result.

    Claude's report SHOULD include:
    - **Cookie-expiry guard result** (`date +%Y%m%d` vs 20260517). If today >= 2026-05-17, halt and request cookie refresh BEFORE any further work.
    - Exit status of the capture script (0 = success; non-0 = cookies expired or other failure).
    - File sizes of the two new fixtures (any 0-byte file means a redirect-to-login was captured — auth needs refresh).
    - Output of the two `grep -c '<table class="songs"'` commands.
    - Locked D-11a shape (one of Shape 1 / Shape 2 / Shape 3 / Shape 4) based on grep output, with the explicit mapping:
      * Shape 1: artist=YES, album=YES → both Option B
      * Shape 2: artist=YES, album=NO → artist Option B, album Option A
      * Shape 3: artist=NO, album=YES → artist Option A, album Option B
      * Shape 4: artist=NO, album=NO → both Option A
    - Confirmation that no real cookie values leaked into the captured HTML (grep `csrftoken` / `sessionid` against artist_4803.html and album_1488.html — should both be 0).

    User confirms by typing one of: "approved D-11a=Shape 1" / "approved D-11a=Shape 2" / "approved D-11a=Shape 3" / "approved D-11a=Shape 4".

    If the dev cookies are expired (cookie-expiry guard returned non-zero OR a 0-byte fixture was captured), user must refresh the cookie file at `~/.local/share/musicstreamer/dev-fixtures/gbs.fm.cookies.txt` (manual browser export) and re-run the script before D-11a can be locked.
  </how-to-verify>
  <resume-signal>Type "approved D-11a=Shape &lt;N&gt;" once the cookie-expiry guard passes, fixtures are captured, the grep results are reported, and the navigation strategy is locked. The remaining tasks reference the locked D-11a shape when specifying click handlers and tests.</resume-signal>
</task>

<task type="auto" tdd="true">
  <name>Task 1 (TDD-RED): Write 5 failing tests for parser + dialog panels</name>
  <files>tests/test_gbs_api.py, tests/test_gbs_search_dialog.py</files>
  <behavior>
    - tests/test_gbs_api.py::test_search_returns_artist_links: Load `tests/fixtures/gbs/search_test_p1.html`, monkeypatch `_open_with_cookies` to return its contents, call `search(...)`. Assert `out["artist_links"]` is a non-empty list. Assert each entry has keys {"text": str, "url": str}. Assert at least one entry has `url == "/artist/4803"` (Testament — present in the fixture per diagnosis §2a).
    - tests/test_gbs_api.py::test_search_returns_album_links: Same fixture, same call. Assert `out["album_links"]` is non-empty and at least one entry has `url == "/album/1488"`.
    - tests/test_gbs_api.py::test_search_page2_has_no_artist_album_links: Same monkeypatch using `search_test_p2.html`. Assert `out["artist_links"] == []` AND `out["album_links"] == []` (page 2+ omits these blocks per diagnosis §2a).
    - tests/test_gbs_search_dialog.py::test_artist_panel_shown_when_links_present: Construct GBSSearchDialog. Emit `_search_worker.metadata_ready` with `[{"text": "Testament", "url": "/artist/4803"}], []`. Assert `dialog._artist_list.isVisible() is True` (or `not isHidden()` per the project's headless-test pattern). Assert `dialog._album_list.isVisible() is False`. Assert `dialog._artist_list.count() == 1` and the first item's `text() == "Testament"`.
    - tests/test_gbs_search_dialog.py::test_artist_panel_hidden_when_no_links: Emit metadata_ready with `[], []`. Assert `dialog._artist_list.isHidden() is True` AND `dialog._album_list.isHidden() is True` (D-11c default).

    Use the existing fixture infrastructure: `gbs_fixtures_dir`, `fake_cookies_jar`, `monkeypatch`, `qtbot`. Existing tests in test_gbs_search_dialog.py show the dialog construction pattern.

    For the dialog tests, you may need to manually invoke the slot if the metadata_ready signal isn't yet wired in production — that's fine, call `dialog._on_metadata_ready(artist_links, album_links)` directly. The test asserts the slot's behavior, which is what RED gates require.
  </behavior>
  <action>
    Append 3 new parser tests to tests/test_gbs_api.py (after the most recent landed test — wave-5 60-08 and wave-6 60-10 will have appended tests too; anchor on the file's tail). Append 2 new dialog tests to tests/test_gbs_search_dialog.py (after the last existing test).

    Run pytest -x tests/test_gbs_api.py tests/test_gbs_search_dialog.py — confirm 5 new tests fail. Commit RED:
    ```
    git add tests/test_gbs_api.py tests/test_gbs_search_dialog.py
    git commit -m "test(60-11): add failing tests for Artist:/Album: parser + panels (T12)"
    ```
  </action>
  <verify>
    <automated>cd /home/kcreasey/OneDrive/Projects/MusicStreamer && python -m pytest tests/test_gbs_api.py tests/test_gbs_search_dialog.py -x -k "artist_links or album_links or artist_album or artist_panel" 2>&1 | tail -20 | grep -v '^#' | grep -E 'FAILED|PASSED|ERROR'</automated>
  </verify>
  <done>5 new tests fail in expected ways (KeyError on artist_links / AttributeError on _artist_list). RED commit recorded.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2 (TDD-GREEN): _ArtistAlbumParser + search() returns artist_links/album_links</name>
  <files>musicstreamer/gbs_api.py</files>
  <behavior>
    - New `_ArtistAlbumParser(HTMLParser)` extracts both Artist: and Album: blocks from the search page HTML.
    - Discriminates the two blocks by the leading text node inside `<p class="artists">` ("Artists:" vs "Albums:") — both blocks share the same class attribute per diagnosis §2a.
    - `search()` return dict gains `artist_links: list[dict]` and `album_links: list[dict]` keys; both default to `[]` when the page has no matches or is page 2+.
    - All 3 parser tests pass; all pre-existing test_gbs_api.py tests still pass (24 from 60-08 + 2 from 60-10 + 3 from this plan = 29).
  </behavior>
  <action>
    Add `_ArtistAlbumParser` to `gbs_api.py`. **Anchor: place after `_QueueRowParser`** (added by 60-10 in wave 6), before `search()`. The file ordering at the time this plan executes is:
    ```
    _SongRowParser    (pre-existing)
    _QueueRowParser   (added by 60-10 in wave 6)
    _ArtistAlbumParser (THIS PLAN — insert here, before search())
    ```
    This anchor change (from "after _SongRowParser" in iter-1 to "after _QueueRowParser" in iter-2) makes the insertion explicit and removes the ambiguity that would have caused a same-anchor collision with 60-10 if both had run in parallel.

    Sketch of the parser (final code is yours):
    ```python
    class _ArtistAlbumParser(HTMLParser):
        """Extract `<p class="artists">` blocks above the songs table.

        gbs.fm reuses class="artists" for BOTH the Artist and Album blocks
        (diagnosis §2a). The block's category is determined by the leading
        text node — "Artists:" vs "Albums:".

        Each block contains <li><a href="/artist/N">name</a></li> entries
        (or /album/N for the album block).
        """
        def __init__(self):
            super().__init__()
            self.artist_links: list = []
            self.album_links: list = []
            self._in_artists_p: bool = False
            self._current_block: Optional[str] = None  # "artists" | "albums" | None
            self._pending_anchor_url: Optional[str] = None
            self._collect_anchor_text: bool = False

        def handle_starttag(self, tag, attrs):
            ad = dict(attrs)
            if tag == "p" and "artists" in (ad.get("class") or ""):
                self._in_artists_p = True
                self._current_block = None  # decided by next data node
            elif self._in_artists_p and tag == "a":
                self._pending_anchor_url = ad.get("href") or ""
                self._collect_anchor_text = True

        def handle_endtag(self, tag):
            if tag == "p" and self._in_artists_p:
                self._in_artists_p = False
                self._current_block = None
            elif tag == "a":
                self._collect_anchor_text = False
                self._pending_anchor_url = None

        def handle_data(self, data):
            if not self._in_artists_p:
                return
            txt = data.strip()
            if not txt:
                return
            # First non-empty data node decides the block.
            if self._current_block is None:
                lower = txt.lower()
                if lower.startswith("artists"):
                    self._current_block = "artists"
                elif lower.startswith("albums"):
                    self._current_block = "albums"
                return
            # If we're inside an anchor, collect the text + href.
            if self._collect_anchor_text and self._pending_anchor_url:
                target = self.artist_links if self._current_block == "artists" else self.album_links
                target.append({"text": txt, "url": self._pending_anchor_url})
                self._collect_anchor_text = False  # one text node per anchor


    def _parse_artist_album_html(html_str: str) -> tuple:
        parser = _ArtistAlbumParser()
        try:
            parser.feed(html_str or "")
            parser.close()
        except Exception:
            return ([], [])
        return (parser.artist_links, parser.album_links)
    ```

    Modify `search()` (around line 368-396) to call the new parser BEFORE the existing `_SongRowParser` invocation (or in parallel — doesn't matter; same input HTML). Add the two keys to the return dict:
    ```python
    artist_links, album_links = _parse_artist_album_html(html_str)
    return {
        "results": parser.results,
        "page": int(page),
        "total_pages": total_pages,
        "artist_links": artist_links,
        "album_links": album_links,
    }
    ```

    Run pytest -x tests/test_gbs_api.py — all pre-existing + 3 new parser tests pass. Commit GREEN:
    ```
    git add musicstreamer/gbs_api.py
    git commit -m "feat(60-11): _ArtistAlbumParser + search() returns artist_links/album_links (T12 parser)

    Adds HTMLParser-based extraction of <p class='artists'> blocks above the
    songs table. Discriminates Artist vs Album blocks by leading text node
    (both share class='artists'). Empty lists on page 2+ and no-match queries.

    Class is inserted AFTER _QueueRowParser (added by 60-10 in wave 6) to
    give the file a deterministic ordering: _SongRowParser, _QueueRowParser,
    _ArtistAlbumParser, search().

    Refs: .planning/phases/60-gbs-fm-integration/60-DIAGNOSIS-search-artist-album.md §5a"
    ```
  </action>
  <verify>
    <automated>cd /home/kcreasey/OneDrive/Projects/MusicStreamer && python -m pytest tests/test_gbs_api.py 2>&1 | tail -5 | grep -v '^#' | grep -E 'passed|failed'</automated>
  </verify>
  <done>29 tests pass in test_gbs_api.py (24 from 60-08 + 2 from 60-10 + 3 new). 2 dialog tests still failing — closed by Task 3. GREEN commit recorded.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3 (TDD-GREEN): _artist_list + _album_list panels in GBSSearchDialog + metadata_ready signal</name>
  <files>musicstreamer/ui_qt/gbs_search_dialog.py</files>
  <behavior>
    - `_GbsSearchWorker.run()` emits a new `metadata_ready(list, list)` signal alongside the existing `finished(list, int, int)`. **ORDERING INVARIANT (defensive): finished MUST emit BEFORE metadata_ready.** Defensive comment in source pins this invariant.
    - `_build_ui()` adds two new QListWidgets (with header QLabels) inserted above the results table. Both start hidden. Both have setMaximumHeight per locked D-11b (default 80).
    - `_on_search_finished` is unchanged; new `_on_metadata_ready(artist_links, album_links)` slot populates both panels and toggles their visibility per D-11c.
    - `_clear_table()` also clears + hides both panels.
    - Per locked D-11a: connect itemActivated (or itemClicked) on each panel to a navigation handler. Implementation depends on locked D-11a value — see action steps. The handler shape is determined by the SHAPE locked in Task 0:
      * Shape 1 (both B) → both handlers call fetch_artist_songs / fetch_album_songs
      * Shape 2 (artist B, album A) → artist handler calls fetch_artist_songs; album handler kicks free-text search
      * Shape 3 (artist A, album B) → artist handler kicks free-text search; album handler calls fetch_album_songs
      * Shape 4 (both A) → both handlers kick free-text search
    - All 16 pre-existing dialog tests + 2 new panel tests pass.
  </behavior>
  <action>
    **Step 3a: Add `metadata_ready` signal + emit from `_GbsSearchWorker.run()` — WITH ORDERING INVARIANT COMMENT.** At line 53-78 of `gbs_search_dialog.py`:
    ```python
    class _GbsSearchWorker(QThread):
        finished = Signal(list, int, int)
        # 60-11 / T12: pre-existing finished signal kept stable; metadata streams
        # via a separate signal so the existing 16 tests don't churn.
        metadata_ready = Signal(list, list)  # (artist_links, album_links)
        error = Signal(str)

        def run(self):
            try:
                out = gbs_api.search(self._query, self._page, self._cookies)
                # =====================================================================
                # ORDERING INVARIANT (60-11 / T12 — DEFENSIVE; DO NOT REORDER):
                #
                # finished MUST emit BEFORE metadata_ready.
                #
                # Why: _on_search_finished -> _render_results -> _clear_table HIDES
                # the artist/album panels. _on_metadata_ready then RE-SHOWS them by
                # populating the lists (D-11c). If metadata_ready emits first, the
                # subsequent _clear_table call from finished will hide the panels
                # we just populated. Qt signal queue order matches emit order, so
                # the emit ordering here is the load-bearing invariant.
                #
                # If a future refactor splits this method or adds buffering, the
                # invariant must be preserved (or _clear_table must be made aware
                # of the metadata state — currently the simpler invariant is the
                # right call per diagnosis §5d acceptable trade-off).
                # =====================================================================
                self.finished.emit(
                    list(out.get("results", [])),
                    int(out.get("page", self._page)),
                    int(out.get("total_pages", self._page)),
                )
                self.metadata_ready.emit(
                    list(out.get("artist_links", [])),
                    list(out.get("album_links", [])),
                )
            except Exception as exc:
                # ...unchanged
    ```

    **Step 3b: Add the two panels in `_build_ui`.** Insert between `self._progress` (after line 181) and the results table (before line 184):
    ```python
    # 60-11 / T12: Artist:/Album: panels — hidden by default, shown when
    # search response includes non-empty artist_links / album_links (page 1
    # with matches per diagnosis §2a).
    self._artist_label = QLabel("Artist:", self)
    self._artist_label.setTextFormat(Qt.TextFormat.PlainText)
    self._artist_label.setVisible(False)
    root.addWidget(self._artist_label)

    self._artist_list = QListWidget(self)
    self._artist_list.setMaximumHeight(80)  # D-11b LOCKED default
    self._artist_list.setVisible(False)
    self._artist_list.itemActivated.connect(self._on_artist_link_activated)  # QA-05
    root.addWidget(self._artist_list)

    self._album_label = QLabel("Album:", self)
    self._album_label.setTextFormat(Qt.TextFormat.PlainText)
    self._album_label.setVisible(False)
    root.addWidget(self._album_label)

    self._album_list = QListWidget(self)
    self._album_list.setMaximumHeight(80)
    self._album_list.setVisible(False)
    self._album_list.itemActivated.connect(self._on_album_link_activated)  # QA-05
    root.addWidget(self._album_list)
    ```

    Add imports: `from PySide6.QtWidgets import QListWidget, QListWidgetItem` (likely already imported — confirm).

    **Step 3c: Wire `metadata_ready` to a new slot.** In `_kick_search_worker` at line 266-276, add the connection:
    ```python
    self._search_worker.finished.connect(self._on_search_finished)
    self._search_worker.metadata_ready.connect(self._on_metadata_ready)  # 60-11 / T12
    self._search_worker.error.connect(self._on_search_error)
    self._search_worker.start()
    ```

    Add the slot method:
    ```python
    def _on_metadata_ready(self, artist_links: list, album_links: list) -> None:
        """60-11 / T12: populate Artist:/Album: panels above the song results.

        D-11c LOCKED: hide entirely when the corresponding list is empty.
        Each entry stores its href in Qt.ItemDataRole.UserRole for navigation.

        Per the ordering invariant in _GbsSearchWorker.run(), this slot runs
        AFTER _on_search_finished -> _clear_table, so we always start with
        cleared+hidden panels. Population here is the only path that re-shows.
        """
        # Artist panel
        self._artist_list.clear()
        for entry in artist_links:
            item = QListWidgetItem(str(entry.get("text", "")))  # PlainText (T-40-04)
            item.setData(Qt.ItemDataRole.UserRole, str(entry.get("url", "")))
            self._artist_list.addItem(item)
        has_artists = bool(artist_links)
        self._artist_label.setVisible(has_artists)
        self._artist_list.setVisible(has_artists)
        # Album panel
        self._album_list.clear()
        for entry in album_links:
            item = QListWidgetItem(str(entry.get("text", "")))
            item.setData(Qt.ItemDataRole.UserRole, str(entry.get("url", "")))
            self._album_list.addItem(item)
        has_albums = bool(album_links)
        self._album_label.setVisible(has_albums)
        self._album_list.setVisible(has_albums)
    ```

    **Step 3d: `_clear_table` clears + hides both panels.** Update line 323-325:
    ```python
    def _clear_table(self) -> None:
        self._model.removeRows(0, self._model.rowCount())
        self._submit_buttons = []
        # 60-11 / T12: also hide artist/album panels — they re-show only when
        # the next search response includes non-empty links via _on_metadata_ready.
        # See ordering invariant in _GbsSearchWorker.run(): metadata_ready emits
        # AFTER finished, so this hide is always followed by the correct re-show.
        if hasattr(self, "_artist_list"):
            self._artist_list.clear()
            self._artist_label.setVisible(False)
            self._artist_list.setVisible(False)
        if hasattr(self, "_album_list"):
            self._album_list.clear()
            self._album_label.setVisible(False)
            self._album_list.setVisible(False)
    ```

    **Step 3e: Click navigation handlers — per locked D-11a Shape.** Implementation collapses to ONE concrete shape determined by Task 0's lock:

    **For ANY shape that needs Option B (artist or album surface), add to `gbs_api.py`:**
    ```python
    def fetch_artist_songs(artist_id: int, cookies) -> dict:
        """GET /artist/<id>; reuse _SongRowParser to extract that artist's tracks.

        Returns the same shape as search() (without artist_links/album_links —
        artist pages don't show those panels).
        """
        url = f"{GBS_BASE}/artist/{int(artist_id)}"
        with _open_with_cookies(url, cookies, timeout=_TIMEOUT_READ) as resp:
            html_str = resp.read().decode("utf-8", errors="replace")
        parser = _SongRowParser()
        parser.feed(html_str)
        parser.close()
        return {"results": parser.results, "page": 1, "total_pages": 1,
                "artist_links": [], "album_links": []}

    def fetch_album_songs(album_id: int, cookies) -> dict:
        """GET /album/<id>; same shape as fetch_artist_songs."""
        url = f"{GBS_BASE}/album/{int(album_id)}"
        # ...same as fetch_artist_songs but with /album/ URL
    ```
    (Add only fetch_artist_songs if Shape 2 — artist B only. Add only fetch_album_songs if Shape 3. Add both for Shape 1. Skip both for Shape 4.)

    **Click handlers per shape — KEEP ONLY the matching shape, drop others:**

    *Shape 1 (both B):*
    ```python
    def _on_artist_link_activated(self, item):
        # 60-11 / T12 — D-11a Shape 1: fetch+reparse artist page
        url = item.data(Qt.ItemDataRole.UserRole) or ""
        m = re.match(r"^/artist/(\d+)$", url)
        if not m:
            return
        artist_id = int(m.group(1))
        self._kick_artist_fetch_worker(artist_id)  # new helper, mirrors _kick_search_worker

    def _on_album_link_activated(self, item):
        # 60-11 / T12 — D-11a Shape 1: fetch+reparse album page
        url = item.data(Qt.ItemDataRole.UserRole) or ""
        m = re.match(r"^/album/(\d+)$", url)
        if not m:
            return
        album_id = int(m.group(1))
        self._kick_album_fetch_worker(album_id)
    ```

    *Shape 2 (artist B, album A):*
    ```python
    def _on_artist_link_activated(self, item):
        # 60-11 / T12 — D-11a Shape 2: fetch+reparse for artist
        url = item.data(Qt.ItemDataRole.UserRole) or ""
        m = re.match(r"^/artist/(\d+)$", url)
        if not m:
            return
        self._kick_artist_fetch_worker(int(m.group(1)))

    def _on_album_link_activated(self, item):
        # 60-11 / T12 — D-11a Shape 2: free-text search fallback for album
        album_text = item.text()
        if not album_text:
            return
        self._search_edit.setText(album_text)
        self._start_search()
    ```

    *Shape 3 (artist A, album B):* — mirror of Shape 2, swap.

    *Shape 4 (both A):*
    ```python
    def _on_artist_link_activated(self, item):
        # 60-11 / T12 — D-11a Shape 4: free-text fallback for artist
        artist_text = item.text()
        if not artist_text:
            return
        self._search_edit.setText(artist_text)
        self._start_search()

    def _on_album_link_activated(self, item):
        # 60-11 / T12 — D-11a Shape 4: free-text fallback for album
        album_text = item.text()
        if not album_text:
            return
        self._search_edit.setText(album_text)
        self._start_search()
    ```

    Add a comment block at the top of the click handler region citing the locked D-11a shape (e.g. "Per Task 0 capture: Shape 2 locked — /artist/<id> has <table class='songs'>; /album/<id> does not.").

    Run pytest -x tests/test_gbs_search_dialog.py — 16 pre-existing + 2 new tests pass. Commit GREEN:
    ```
    git add musicstreamer/gbs_api.py musicstreamer/ui_qt/gbs_search_dialog.py
    git commit -m "feat(60-11): Artist:/Album: panels in GBSSearchDialog + click navigation per D-11a (T12)

    Adds _artist_list + _album_list QListWidget panels above the song results
    table. Both are hidden when their corresponding link list is empty
    (D-11c default). metadata_ready signal on _GbsSearchWorker streams the
    parsed lists from gbs_api.search.

    Click navigation per locked D-11a=Shape <N>. Handlers store URLs in
    Qt.UserRole (PlainText / T-40-04). Defensive ordering comment in
    _GbsSearchWorker.run() pins finished BEFORE metadata_ready.

    Refs: .planning/phases/60-gbs-fm-integration/60-DIAGNOSIS-search-artist-album.md §5b/c/d"
    ```

    NOTE: if the locked shape uses Option B (Shape 1, 2, or 3), ALSO add small additional tests (test_fetch_artist_songs_parses_table and/or test_fetch_album_songs_parses_table) that load the captured fixture, monkeypatch `_open_with_cookies`, and assert `fetch_*_songs(...)["results"]` is a non-empty list. Include in the same Task 3 GREEN commit.
  </action>
  <verify>
    <automated>cd /home/kcreasey/OneDrive/Projects/MusicStreamer && python -m pytest tests/test_gbs_search_dialog.py tests/test_gbs_api.py 2>&1 | tail -10 | grep -v '^#' | grep -E 'passed|failed'</automated>
  </verify>
  <done>All tests pass: 18 in test_gbs_search_dialog.py (16 pre-existing + 2 new panel), 29+ in test_gbs_api.py (29 baseline + optional fetch_*_songs tests if Option B locked for any surface). GREEN commit recorded.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 4: Click navigation integration test (per locked D-11a Shape — single concrete shape)</name>
  <files>tests/test_gbs_search_dialog.py</files>
  <behavior>
    - Integration test(s) exercise the click-navigation path. The number of tests and their shape is determined by the LOCKED D-11a shape from Task 0:
      * Shape 1 (both B) → 2 tests: artist click → fetch_artist_songs; album click → fetch_album_songs
      * Shape 2 (artist B, album A) → 2 tests: artist click → fetch_artist_songs; album click → free-text search
      * Shape 3 (artist A, album B) → 2 tests: artist click → free-text search; album click → fetch_album_songs
      * Shape 4 (both A) → 2 tests: artist click → free-text search; album click → free-text search
    - Each test patches the relevant gbs_api function (fetch_artist_songs / fetch_album_songs / search) to return canned data; does not require live HTTP.
  </behavior>
  <action>
    **Per locked D-11a Shape — collapse to the matching test shape; ALL OTHER shapes' tests are NOT written.**

    The plan-check iter-1 flagged Task 4's mixed-option ambiguity. Task 0 locks D-11a as one of four discrete shapes; Task 4 then writes EXACTLY the tests for that shape. Below is the enumerated mapping; pick the row matching Task 0's lock:

    **Shape 1 (both B):**
    ```python
    def test_artist_click_kicks_fetch_artist_songs(qtbot, monkeypatch):
        # Patch gbs_api.fetch_artist_songs to return canned results
        # Emit metadata_ready with [{"text": "Testament", "url": "/artist/4803"}], []
        # Simulate click on item 0 of _artist_list
        # Assert fetch_artist_songs called with artist_id=4803
        # Assert the results table re-renders with the canned results
        ...

    def test_album_click_kicks_fetch_album_songs(qtbot, monkeypatch):
        # Mirror, with /album/1488 and fetch_album_songs
        ...
    ```

    **Shape 2 (artist B, album A):**
    ```python
    def test_artist_click_kicks_fetch_artist_songs(qtbot, monkeypatch):
        # Same as Shape 1
        ...

    def test_album_click_kicks_free_text_search(qtbot, monkeypatch):
        # Emit metadata_ready with [], [{"text": "#gbs-fm's greatest shits", "url": "/album/1488"}]
        # Patch _start_search (or _kick_search_worker) to spy on calls
        # Click item 0 of _album_list
        # Assert dialog._search_edit.text() == "#gbs-fm's greatest shits"
        # Assert _start_search was called once
        ...
    ```

    **Shape 3 (artist A, album B):** — mirror of Shape 2 (test_artist_click_kicks_free_text_search + test_album_click_kicks_fetch_album_songs).

    **Shape 4 (both A):**
    ```python
    def test_artist_click_kicks_free_text_search(qtbot, monkeypatch):
        # Emit metadata_ready with [{"text": "Testament", "url": "/artist/4803"}], []
        # Patch _start_search to spy
        # Click item 0 of _artist_list
        # Assert dialog._search_edit.text() == "Testament"
        # Assert _start_search was called once
        ...

    def test_album_click_kicks_free_text_search(qtbot, monkeypatch):
        # Same shape, with album fixture
        ...
    ```

    Run pytest -x tests/test_gbs_search_dialog.py — confirm new test(s) pass. Commit:
    ```
    git add tests/test_gbs_search_dialog.py
    git commit -m "test(60-11): integration tests for artist/album click navigation per locked D-11a Shape <N> (T12)"
    ```
  </action>
  <verify>
    <automated>cd /home/kcreasey/OneDrive/Projects/MusicStreamer && python -m pytest tests/test_gbs_search_dialog.py 2>&1 | tail -5 | grep -v '^#' | grep -E 'passed|failed'</automated>
  </verify>
  <done>20 tests pass in test_gbs_search_dialog.py (16 pre-existing + 2 new panel + 2 new integration). Integration tests verify the locked D-11a Shape navigation path end-to-end.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| gbs.fm /search HTML → _ArtistAlbumParser | Untrusted HTML may contain markup or malicious href values |
| Parsed link entries → QListWidget | Stored in PlainText; URL in UserRole (not rendered) |
| Click handler → gbs_api.fetch_* (Option B) or search (Option A) | URL parsed from item data; integer id extracted before constructing fetch URL |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-60-11-01 | Information Disclosure | HTML injection in artist/album link text | mitigate | QListWidgetItem renders PlainText (T-40-04). Parser stores `str` from `handle_data`. URL stored in UserRole, not rendered. |
| T-60-11-02 | Tampering | Server returns href="javascript:..." or off-host URL | mitigate (Option B) / accept (Option A) | Option B: regex-extract `/artist/(\d+)` and `/album/(\d+)` and ignore non-matching hrefs (no JavaScript URLs reachable). Option A: free-text search uses item.text() (the artist name), not the href, so off-host URLs cannot escape the search query path. |
| T-60-11-03 | DoS | Search response with thousands of artist/album links | mitigate | QListWidget setMaximumHeight=80 (D-11b) limits visible rows; the underlying list count is unbounded but the panel is scrollable. If pathological responses become a problem, add a hard slice in _on_metadata_ready. |
| T-60-11-04 | Tampering | Captured fixture leaks real session cookies | mitigate | scripts/gbs_capture_fixtures.sh reads cookies from D-04a XDG path (outside repo); curl `-b "$COOKIES"` does not write cookie values into output (only request headers). Verify via grep on captured HTML — should be 0 matches for the live token values. Cookie-expiry hard guard at Task 0 prevents capturing stale-session redirect HTML. |
| T-60-11-05 | Spoofing | Auth-expired during fetch_artist_songs (Option B) | mitigate | fetch_artist_songs uses `_open_with_cookies` which raises GbsAuthExpiredError on 302→/accounts/login/. _GbsSearchWorker error path emits "auth_expired" sentinel; existing dialog handler shows the reconnect toast. |
| T-60-11-06 | Tampering | Future refactor reorders metadata_ready vs finished emission | mitigate | Defensive comment block in _GbsSearchWorker.run() explicitly pins the ordering invariant (Step 3a) — finished MUST emit BEFORE metadata_ready, otherwise _clear_table will hide the just-populated panels. |
</threat_model>

<verification>
- pytest tests/test_gbs_api.py shows ≥29 tests pass (24 from 60-08 wave-5 + 2 from 60-10 wave-6 + 3 new parser tests + optional fetch_*_songs tests).
- pytest tests/test_gbs_search_dialog.py shows 20 tests pass (16 pre-existing + 2 new panel + 2 new click integration).
- pytest tests/test_now_playing_panel.py + tests/test_main_window_integration.py + tests/test_stream_ordering.py all still pass.
- `grep -c '_ArtistAlbumParser' musicstreamer/gbs_api.py` ≥ 1.
- `grep -c '_artist_list' musicstreamer/ui_qt/gbs_search_dialog.py` ≥ 4 (declaration + setMaximumHeight + setVisible + clear).
- `grep -c '_album_list' musicstreamer/ui_qt/gbs_search_dialog.py` ≥ 4 (parallel).
- `grep -c 'metadata_ready' musicstreamer/ui_qt/gbs_search_dialog.py` ≥ 3 (signal + emit + connect).
- `grep -c 'ORDERING INVARIANT' musicstreamer/ui_qt/gbs_search_dialog.py` ≥ 1 (defensive comment block in _GbsSearchWorker.run()).
- `ls tests/fixtures/gbs/artist_4803.html tests/fixtures/gbs/album_1488.html` both exist.
- `grep -c 'csrftoken-PLACEHOLDER\\|sessionid-PLACEHOLDER' scripts/gbs_capture_fixtures.sh` ≥ 1 (sanitization markers retained).
- `grep -E 'csrftoken=[A-Za-z0-9]{8,}\\|sessionid=[A-Za-z0-9]{8,}' tests/fixtures/gbs/artist_4803.html` empty (no real cookie values).
- File ordering in `gbs_api.py`: `_SongRowParser` precedes `_QueueRowParser` precedes `_ArtistAlbumParser` precedes `search()`. Verify via `grep -n 'class _SongRowParser\\|class _QueueRowParser\\|class _ArtistAlbumParser\\|^def search' musicstreamer/gbs_api.py`.
- Manual reproduction: search "test" in dialog → see Artist: panel and Album: panel above song results table → click an artist → song table updates per locked D-11a Shape.
</verification>

<success_criteria>
- T12 closed: search dialog mirrors gbs.fm web UI's Artist:/Album: panels above the song results table on page 1 with matches.
- D-11a locked via Task 0 checkpoint inspection (one of Shape 1/2/3/4).
- All ≥49 tests across test_gbs_api.py + test_gbs_search_dialog.py pass.
- No regression in test_now_playing_panel.py, test_main_window_integration.py, test_stream_ordering.py.
- Five atomic commits: 1 fixture-capture (Task 0), 1 RED (Task 1), 2 GREEN (Tasks 2 + 3), 1 integration test (Task 4).
- Real session cookies never enter the repo tree.
- Cookie-expiry hard guard halts before HTTP capture if today >= 2026-05-17.
- File ordering inside gbs_api.py is deterministic: _SongRowParser → _QueueRowParser → _ArtistAlbumParser.
- Defensive ordering invariant comment block in _GbsSearchWorker.run() pins finished BEFORE metadata_ready.
</success_criteria>

<output>
After completion, create `.planning/phases/60-gbs-fm-integration/60-11-search-artist-album-panels-SUMMARY.md` per the standard summary template, including:
- Frontmatter: requires=[60-02, 60-07, 60-10], provides=["_ArtistAlbumParser", "search artist_links/album_links", "GBSSearchDialog Artist:/Album: panels", "click navigation per locked D-11a", optionally "fetch_artist_songs / fetch_album_songs"], requirements-completed=[GBS-01e]
- Sections: Performance / Accomplishments / Task Commits / Files Modified / Decisions Made (record locked D-11a Shape + the rationale from Task 0 inspection; D-11b=80px; D-11c=hide-when-empty) / TDD Gate Compliance / Deviations / Threat Flags / Self-Check
- Surface any user-visible follow-ups (e.g. if D-11a Option A locked for either surface, note that the artist/album-name match is semantic — false positives possible; future plan could harden by adding artist_id-aware /search filter if gbs.fm exposes one)
</output>
