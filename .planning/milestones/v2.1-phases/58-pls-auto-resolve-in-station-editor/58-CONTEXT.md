# Phase 58: PLS Auto-Resolve in Station Editor — Context

**Gathered:** 2026-05-01
**Status:** Ready for planning

<domain>
## Phase Boundary

When the user is editing a station in `EditStationDialog` and wants to add the multiple streams that a single playlist URL points to, they click a new **"Add from PLS…"** button in the Streams-section toolbar, paste a playlist URL, and the dialog auto-fetches/parses the playlist and inserts one stream-table row per playlist entry — with bitrate, codec, and a human-readable Quality label populated from the playlist metadata where parseable.

The visible button label says **"Add from PLS…"** (consistent with STR-15 / ROADMAP wording), but internally the parser dispatches by URL extension and Content-Type and supports **PLS, M3U, M3U8, and XSPF**. M3U/M3U8/XSPF support is a quiet extension — pasting any of those URLs "just works" without a separate button or surface.

**In scope:**
- Add a 5th button "Add from PLS…" to the streams-section button row in `EditStationDialog` (currently `Add | Remove | Move Up | Move Down`).
- Click → `QInputDialog.getText` one-liner accepts a playlist URL.
- Background `QThread` worker fetches body, dispatches by `.pls`/`.m3u`/`.m3u8`/`.xspf` URL extension; falls back to `Content-Type` (`audio/x-scpls`, `audio/x-mpegurl`, `application/xspf+xml`) when extension is missing/unrecognized.
- Per-format parser returns `list[dict]` with keys `{url, title, bitrate_kbps, codec}` derived from playlist metadata only — **no per-URL HEAD/ICY probe**.
- Insert one row per parsed entry into the streams table (UI-only — persistence happens in existing `_on_save`).
- When existing rows are present, prompt with `QMessageBox` "Replace, Append, or Cancel" (default Append). Empty table → append silently.
- Failure (HTTP error, malformed playlist, empty entries) → `QMessageBox.warning`, no rows added, table unchanged.

**Out of scope:**
- ICY/HEAD probing of resolved stream URLs to populate bitrate/codec when the playlist itself doesn't carry them. PLS/M3U/XSPF Title-string parse only; if metadata missing, bitrate=0 and codec="" (per Phase 47 conventions).
- Renaming the phase, ROADMAP entry, or STR-15 wording. Title stays "PLS Auto-Resolve" — the multi-format support is a quiet capability extension, not a re-spec.
- Auto-detection of playlist URLs typed into the top "URL:" field. That field stays logo-fetch-only; the new feature lives in the Streams section as the brief specifies.
- Per-row checkbox preview of which entries to import. All-or-nothing import; user removes unwanted rows manually after the fact.
- New top-level dialog. The whole flow lives inside `EditStationDialog` and one `QInputDialog`.
- Playback-time PLS resolution (e.g. `Player.play` accepting a `.pls` URL). Phase 58 is import-time only; AA's existing `aa_import._resolve_pls` continues to handle the import-time path for the AudioAddict pipeline (and is refactored to use the new shared helper — see D-09).
- Scope creep into discovery dialog or settings-import paths. PLS auto-resolve is `EditStationDialog`-only for this phase.

</domain>

<decisions>
## Implementation Decisions

### Trigger / entrypoint

- **D-01:** A new **5th button "Add from PLS…"** is added to the streams-section button row in `EditStationDialog._build_ui` at `edit_station_dialog.py:362-373`, after `Move Down`. Bound-method connection (QA-05): `self.add_pls_btn.clicked.connect(self._on_add_pls)`. Button is `QPushButton("Add from PLS…")` with the U+2026 ellipsis (matches "Connecting…" copywriting convention in the project). Tooltip: `"Paste a playlist URL (PLS / M3U / M3U8 / XSPF) and import each stream entry as a row."` so users discover the multi-format support without docs.
- **D-02:** Click handler `_on_add_pls(self)` opens `QInputDialog.getText(self, "Add from PLS", "Playlist URL:", QLineEdit.Normal, "")`. Cancel / empty → no-op. Otherwise the URL is handed to a new background worker (D-04). No clipboard auto-read, no preview dialog with per-row checkboxes — this is the lightweight "paste once and go" path.
- **D-03:** During the background fetch the dialog applies `QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))` and `self.add_pls_btn.setEnabled(False)`. Cursor is restored exactly once at the top of the worker's `finished` slot — covering success, failure, and stale-token branches — mirroring the `_LogoFetchWorker` D-10 pattern from Phase 46-02 (see `edit_station_dialog.py:691` for the precedent). No new status label is added; the wait cursor + disabled button is the only progress affordance.
- **D-04:** New `_PlaylistFetchWorker(QThread)` lives in `edit_station_dialog.py` next to `_LogoFetchWorker` (modeled on it). Constructor takes `(url: str, token: int, parent=None)`. `run()` performs `urllib.request.urlopen(url, timeout=10)`, decodes the body, and emits `finished = Signal(list, str, int)` carrying `(entries, error_message, token)` where `entries` is the parsed `list[dict]` (empty on failure) and `error_message` is `""` on success or a short user-readable reason on failure. Token follows the same monotonic stale-discard pattern as `_LogoFetchWorker` so any in-flight worker's emission is recognized as stale by `_on_pls_fetched` if the user fires another resolve before the previous one finishes.
- **D-05:** On failure (`error_message != ""` or `entries == []`): `QMessageBox.warning(self, "PLS resolution failed", f"Could not resolve playlist:\n{error_message or 'No entries found.'}")`. Streams table is unchanged. No raw-PLS-as-single-row legacy fallback (we are NOT mirroring `aa_import._resolve_pls`'s `[pls_url]` fallback in this UI path — GStreamer cannot play a `.pls` URL, so the "fallback" would just be a broken row). The user retries or adds manually. Defense-in-depth: also catch `urllib.error.URLError`, `socket.timeout`, `UnicodeDecodeError`, and any parser exception inside `run()` and convert to `error_message`.

### Replace vs append

- **D-06:** When `self.streams_table.rowCount() > 0` at resolve time, the post-fetch slot `_on_pls_fetched` shows a 3-button `QMessageBox.question`: `Replace | Append | Cancel`. Default button is **Append** (Enter accepts non-destructive Append). Cancel = no-op. Empty streams table → skip the prompt and append silently. Wording: `"This station has {N} existing stream{s}.\n\nReplace them with the {M} resolved entries, or append the new entries after the existing ones?"` (pluralization handled).
- **D-07:** **Replace** clears the table via `self.streams_table.setRowCount(0)` (UI-only — no `repo.delete_stream` call). The existing `_on_save` flow already handles row diff: rows in DB whose `stream_id` no longer appears in the post-save `ordered_ids` are pruned by the existing reconcile pass. **The Discard / Cancel button still rolls back to the original DB state** because the dialog has not committed yet. This preserves the Phase 39+ Save/Discard contract and the Phase 51-02 dirty-state baseline.
- **D-08:** **Append** position numbers continue from `max(existing position) + 1`. Implementation: scan column `_COL_POSITION` over current rows for the max int value (default 0 if all blank), then assign `max + 1`, `max + 2`, … to the resolved entries in playlist file-order. Preserves existing failover priority (Phase 47-01 ordering invariant: bitrate-desc within same position; lower position plays first). New rows fall to the bottom of the failover queue, matching the user's expectation of "append".

### Bitrate / codec depth

- **D-09:** A new shared helper module `musicstreamer/playlist_parser.py` is created with the public function `parse_playlist(body: str, content_type: str = "", url_hint: str = "") -> list[dict]` returning `[{url: str, title: str, bitrate_kbps: int, codec: str}, ...]`. Internal dispatch:
  - URL extension check first: `.pls` → `_parse_pls`, `.m3u`/`.m3u8` → `_parse_m3u`, `.xspf` → `_parse_xspf`.
  - Content-Type fallback when extension is missing/unknown: `audio/x-scpls`/`audio/scpls` → PLS, `audio/x-mpegurl`/`application/vnd.apple.mpegurl`/`audio/mpegurl` → M3U, `application/xspf+xml` → XSPF.
  - If neither resolves, return `[]` (caller treats as "malformed/unknown format" failure).
- **D-10:** `aa_import._resolve_pls` is refactored to delegate to the new `parse_playlist` helper, then map the returned dicts back to `list[str]` via `[e["url"] for e in entries]`. Existing callers at `aa_import.py:135, 177` continue to work unchanged. This makes the new helper the single source of truth for PLS parsing across the app and keeps the gap-06 file-order invariant intact.
- **D-11:** **PLS Title parse** — for each `FileN=URL` and matching `TitleN=…` line:
  - `bitrate_kbps`: regex `r"(\d+)\s*k(?:b(?:ps)?)?\b"` (case-insensitive) against the Title; first match → `int`. No match → `0`.
  - `codec`: scan Title (case-insensitive) for known tokens in priority order: `HE-AAC`, `AAC+`, `AAC`, `OGG`, `FLAC`, `OPUS`, `MP3`, `WMA`. First match → uppercase canonical form. No match → `""` (blank). **Do NOT** fall back to "last word in title" or insert literal `"unknown"`.
  - `title`: full Title text as-is (used as the Quality column value).
  - `url`: `FileN=` value, stripped.
- **D-12:** **M3U/M3U8 parse** — split body on newlines, walk pairwise.
  - For each non-comment URL line, the immediately preceding `#EXTINF:DURATION,DISPLAY_NAME` (if present) is the metadata.
  - `bitrate_kbps` and `codec`: same regex / token scan as D-11 against `DISPLAY_NAME`.
  - `title`: `DISPLAY_NAME` (or empty if no `#EXTINF` precedes the URL).
  - `url`: the URL line, stripped.
  - **`#EXT-X-STREAM-INF` (M3U8 master-playlist) `BANDWIDTH=` / `CODECS="…"` attributes are NOT parsed** for v1. Adds parser complexity beyond the "Title-string parse" depth chosen in D-11. Captured as a deferred idea.
- **D-13:** **XSPF parse** — `xml.etree.ElementTree.fromstring(body)` on the XSPF body. Walk `<track>` elements (handling the XSPF namespace `http://xspf.org/ns/0/`). For each track:
  - `url`: text of `<location>` child.
  - `title`: text of `<title>` child (or empty).
  - `bitrate_kbps` / `codec`: same regex / token scan against `title`.
  - **No `defusedxml` dependency added.** Plain `ElementTree.fromstring` is used. Threat surface assessment: the user pastes an XSPF URL into their own station editor — nothing crosses a trust boundary, no XML is read from peers/servers without explicit user opt-in, and the worker thread's exception handler catches any parser exceptions (XXE-style payloads will either be ignored by ElementTree's default resolver or raise, which becomes a "Could not resolve playlist" error path).
- **D-14:** **Quality column** is populated with the **full `title`** field from each parsed entry — same source as D-11/D-12/D-13 produce. Mirrors the "human-readable identifier" use of Quality across the app (Phase 47 left it as free-text). Empty title → blank column.
- **D-15:** **Codec column** — leave blank when no recognized token is found in the title (D-11 fallthrough). Phase 47-01's `codec_rank` `(codec or "").strip().upper()` None-safety guarantees blank codec rows still order correctly via the failover queue.
- **D-16:** **Bitrate column** — when bitrate parses to `0`, the column renders as the empty string per the existing `_add_stream_row` convention at `edit_station_dialog.py:621-624` (`str(bitrate_kbps) if bitrate_kbps else ""`). No change to that helper.
- **D-17:** **Encoding** — `urllib.request.urlopen(...).read()` returns bytes; decode with `body.decode("utf-8", errors="replace")` for PLS/M3U/M3U8. XSPF: pass bytes directly to `ElementTree.fromstring` (it handles encoding via the XML prologue). PLS files in the wild are sometimes latin-1; `errors="replace"` keeps parsing alive at the cost of replacement chars in titles — acceptable for Quality column, won't affect URLs (which are ASCII-only after URL-encoding).

### Format scope

- **D-18:** **Phase title remains "PLS Auto-Resolve in Station Editor"** in ROADMAP.md and the requirement remains STR-15 ("PLS URL"). Multi-format (M3U/M3U8/XSPF) support is internal: the user pastes any URL, the parser dispatches by extension/Content-Type, and the entries appear in the table. The button label "Add from PLS…" stays familiar and short. The tooltip (D-01) is the only user-facing surface that names all four formats.
- **D-19:** **Format detection order** — URL path extension first (cheapest, no I/O), Content-Type response header second, give up third. No body sniffing (no `[playlist]` header check, no `#EXTM3U` first-line check). Trade-off accepted: if a server sends a `.txt` URL with `Content-Type: text/plain` that contains a PLS body, we don't parse it. Real-world frequency is low; the failure mode is a clear "Could not resolve playlist" error, not silent data loss.

### Claude's Discretion

- Exact button placement within the row: after "Move Down" is recommended (chronological-action grouping reads as "manage rows | bulk import"), but inserting it between "Add" and "Remove" (grouping all add-style affordances together) is fine if the planner finds visual reasons during implementation.
- The `QMessageBox.warning` exact wording on failure (D-05). Locked is the **shape** (warning, no rows added) — wording is the planner's call so long as the displayed reason is user-readable, not a Python traceback.
- Whether the Replace/Append prompt uses the standard `QMessageBox.question` 3-button form (Yes/No/Cancel relabeled) or a custom button-box. Standard form preferred for stylistic consistency with Phase 51's Save/Discard/Cancel sibling-link prompt — but planner can deviate if `QMessageBox` styling doesn't allow custom button text on the target Qt 6.11 build.
- The location of the new `_PlaylistFetchWorker` class — in-file next to `_LogoFetchWorker` is recommended for parallelism, but extracting both into a `musicstreamer/ui_qt/_dialog_workers.py` module is acceptable as a refactor if the planner sees it as a real cleanup (and not just shuffle).
- Test placement: `tests/test_playlist_parser.py` for the new pure helper (PLS / M3U / M3U8 / XSPF fixtures + edge cases); `tests/test_edit_station_dialog.py` extension for the new button, the `_on_add_pls` flow, the `_PlaylistFetchWorker` round-trip with a stub URL handler, and the Replace/Append/Cancel branching. Planner picks the exact fixture shapes.
- Whether a per-call URL-deduplication pass runs before insert (drop a resolved URL if it's already in the streams table). Defaulting to **no dedup** — the user asked for "one row per playlist entry" — but if the planner finds the dedup is trivial and tests show value, it can ship as a quiet polish. Capture the alternative explicitly in PLAN.md for visibility.
- Dirty-state interaction: the resolved-row insert MUST trigger the Phase 51-02 dirty-state baseline (Save/Discard/Cancel handles the dialog properly). Planner verifies via the existing `_capture_dirty_baseline` / `_is_dirty` snapshot mechanism — likely no code change since `_add_stream_row` already feeds rows that the snapshot picks up.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` §"Phase 58: PLS Auto-Resolve in Station Editor" — goal, four success criteria.
- `.planning/REQUIREMENTS.md` §STR-15 — "User can paste a PLS URL into a station's Streams section and have it auto-resolve into N individual stream entries (one per playlist row)."
- `.planning/PROJECT.md` Key Decisions — `url_resolved preferred over url (Radio-Browser)`, `Resolve PLS to direct URL in aa_import.fetch_channels`, `ch['key'] not ch['name'] for AudioAddict PLS slug`. Establishes that PLS is a known-import-time concern in the project.

### Phase 47 precedent (failover ordering invariants — DO NOT BREAK)
- `.planning/phases/47-stats-for-nerds-and-autoeq-import/` (Phase 47-01..03 entries in `.planning/STATE.md`) — `codec_rank` None-safety + whitespace tolerance (PB-10), bitrate-desc-within-position ordering, `_BitrateDelegate` `QIntValidator(0, 9999)` policy, `bitrate_kbps=0 → empty-string` rendering convention. Resolved rows MUST honor these invariants.
- `musicstreamer/streams.py` (or wherever `order_streams` lives) — failover queue ordering. Resolved rows participate in the same queue; no special-casing.

### Phase 51 / 64 precedent (dialog patterns — Save/Discard/Cancel + dirty state)
- `.planning/phases/51-audioaddict-cross-network-siblings/51-CONTEXT.md` D-11/D-12 — snapshot-and-compare dirty-state baseline. Resolved rows must trip dirty correctly so `Save | Discard | Cancel` continues to work after a PLS import.
- `.planning/phases/64-audioaddict-siblings-on-now-playing/64-CONTEXT.md` — dialog signal/handler conventions, bound-method connection requirement (QA-05).

### Phase 46 precedent (background-thread fetch worker pattern — model for D-04)
- `musicstreamer/ui_qt/edit_station_dialog.py:54-167` — `_LogoFetchWorker(QThread)` with monotonic-token stale-discard. New `_PlaylistFetchWorker` mirrors its constructor shape, `finished` Signal, and the wait-cursor-restored-once-at-top-of-slot D-10 pattern at `edit_station_dialog.py:691`.

### Code touch points (load these to understand current state)

#### Streams section (where the new button + handler land)
- `musicstreamer/ui_qt/edit_station_dialog.py:329-374` — Streams table + button row construction. New button inserted after "Move Down" (D-01).
- `musicstreamer/ui_qt/edit_station_dialog.py:362-379` — existing button signal connections. New `self.add_pls_btn.clicked.connect(self._on_add_pls)` joins this group.
- `musicstreamer/ui_qt/edit_station_dialog.py:603-626` — `_add_stream_row(url, quality, codec, bitrate_kbps, position, stream_id)`. The resolved-row insert path calls this with `stream_id=None` (UI-only insert; persistence happens in `_on_save`).
- `musicstreamer/ui_qt/edit_station_dialog.py:899-938` — `_on_save` stream persistence block. Reconciles UI rows against `repo` state via `update_stream` (existing rows by `stream_id` UserRole), `insert_stream` (new rows where `stream_id is None`), and `reorder_streams(station.id, ordered_ids)`. Replace-clears the table → existing-stream-ids drop out of `ordered_ids` → repo prunes them naturally. **No `repo.delete_stream` calls needed at clear-time** (D-07).

#### Worker pattern (model — copy the shape, not the body)
- `musicstreamer/ui_qt/edit_station_dialog.py:54-167` — `_LogoFetchWorker(QThread)`. Constructor signature, `Signal(str, int, str)` shape, `_logo_fetch_token` monotonic stale-discard pattern (line 682-687).
- `musicstreamer/ui_qt/edit_station_dialog.py:687-692` — wait-cursor application + worker start. Mirror exactly for the PLS path.
- `musicstreamer/ui_qt/edit_station_dialog.py:~700-748` — `_on_logo_fetched` slot. Cursor restoration at the top, stale-token check second, success/failure branching after — same shape as the new `_on_pls_fetched`.

#### Existing PLS helper (refactor target — D-09 / D-10)
- `musicstreamer/aa_import.py:23-46` — `_resolve_pls(pls_url) -> list[str]`. Refactored to delegate to `playlist_parser.parse_playlist`. Both call sites at `aa_import.py:135, 177` continue to work unchanged because the wrapper preserves the `list[str]` signature. The gap-06 ordering invariant (file-order primary→fallback within a tier) is preserved by the new parser's file-order traversal.

#### Repo (no schema change required)
- `musicstreamer/repo.py:176` — `Repo.list_streams(station_id) -> List[StationStream]`.
- `musicstreamer/repo.py:185` — `Repo.insert_stream(station_id, url, label, quality, position, stream_type, codec, bitrate_kbps)`. Resolved rows insert through this in `_on_save`.
- `musicstreamer/repo.py:195` — `Repo.update_stream(...)`. Untouched by Phase 58 (only existing rows that survived a Replace flow continue to use it).
- `musicstreamer/repo.py:207` — `Repo.reorder_streams(station_id, ordered_ids)`. Already wired in `_on_save`.

#### Project conventions
- `.planning/codebase/CONVENTIONS.md` — snake_case, type hints throughout, no formatter, no linter on save.
- `.planning/codebase/STACK.md` — Python 3.10+, PySide6 6.11+, no new runtime deps for Phase 58 (urllib + xml.etree are stdlib).
- `.planning/codebase/CONCERNS.md` — security review checklist; the XSPF + plain ElementTree decision (D-13) is an explicit acceptance documented in this CONTEXT.
- Bound-method signal connections, no self-capturing lambdas (QA-05) — applies to `add_pls_btn.clicked` and `_PlaylistFetchWorker.finished` connections.
- Linux X11 deployment target, DPR=1.0 (per project memory) — HiDPI/Retina/Wayland-fractional findings in any UI audit downgrade from CRITICAL → WARNING.

### No external specs
No ADRs apply. The phase is captured by ROADMAP §Phase 58 (4 success criteria), STR-15, the four code touch-point clusters above, and the in-flight `_LogoFetchWorker` worker pattern.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`aa_import._resolve_pls`** — already does the canonical PLS-fetch + `FileN=` regex parse + file-order preservation. Phase 58 promotes it to a generalized `playlist_parser.parse_playlist` (D-09) and refactors `_resolve_pls` into a thin wrapper (D-10).
- **`_LogoFetchWorker(QThread)` pattern** — token-based stale-discard, wait-cursor convention, `finished` Signal with payload + token. New `_PlaylistFetchWorker` is a copy-shape-not-body twin.
- **`_add_stream_row(url, quality, codec, bitrate_kbps, position, stream_id=None)`** — already inserts a row with `stream_id=None` for new entries. Phase 58 calls this once per resolved entry; `_on_save` handles persistence.
- **`_BitrateDelegate(QStyledItemDelegate)`** — `QIntValidator(0, 9999)`; clamps user edits to the valid range. Resolved rows whose parsed bitrate exceeds 9999 (rare; e.g. `9999k` typo in Title) are clamped on next user edit but stored at parse-time as-is via `_add_stream_row` (display-only delegate, not domain validator).
- **`QInputDialog.getText`** — stdlib Qt one-liner. Cancel returns `("", False)`; covers the empty/cancel no-op path.
- **`_capture_dirty_baseline` / `_is_dirty`** — snapshot-and-compare baseline includes the streams table; resolved-row insert trips dirty correctly without modification.
- **`_on_save` reconcile pass** — `ordered_ids` accumulator + `reorder_streams` + insert_stream-on-stream_id-None + update_stream-on-stream_id-set already covers the Replace flow when rows are dropped from the UI (D-07). No new repo plumbing.

### Established Patterns
- **Background-fetch worker per HTTP-bound dialog action** — `_LogoFetchWorker` is the precedent. New `_PlaylistFetchWorker` follows it.
- **Monotonic stale-discard tokens** — guard against multiple in-flight workers (`_logo_fetch_token` precedent). New `_pls_fetch_token` does the same.
- **Wait-cursor + button-disable for sub-1s-to-10s I/O** — restored-once-at-top-of-slot. Phase 46-02 D-10 invariant.
- **UI-only row mutations + reconcile-at-save** — Phase 47-03 / Phase 51-02 / Phase 55. Replace-clear in Phase 58 follows the same.
- **`QMessageBox.question` 3-button confirm** — Phase 51-04 D-09 (sibling Save/Discard/Cancel) uses this shape. Phase 58 D-06 mirrors it for Replace/Append/Cancel.
- **Hidden `QLabel` failure messages — N/A here**: Phase 58 uses `QMessageBox.warning` for failure (D-05) instead of an in-dialog status label, because the in-dialog `_logo_status` field is logo-fetch-specific and the PLS path is action-triggered (not auto-debounced), so a modal alert reads more clearly than a tiny label flash.

### Integration Points
- **New file:** `musicstreamer/playlist_parser.py` — `parse_playlist(body, content_type, url_hint) -> list[dict]` + private `_parse_pls`, `_parse_m3u`, `_parse_xspf`. Pure module, fully unit-testable without Qt.
- **New button:** `self.add_pls_btn = QPushButton("Add from PLS…")` inserted at `edit_station_dialog.py:~370` (after Move Down). One-line addition to the `for btn in (...): btn_row.addWidget(btn)` loop.
- **New connection:** `self.add_pls_btn.clicked.connect(self._on_add_pls)` after the existing four connections at `edit_station_dialog.py:376-379`.
- **New methods on `EditStationDialog`:**
  - `_on_add_pls(self) -> None` — opens `QInputDialog`, kicks off worker.
  - `_on_pls_fetched(self, entries: list, error_message: str, token: int) -> None` — restores cursor, re-enables button, dispatches Replace/Append/Cancel prompt or warns on failure, then calls `_apply_pls_entries(entries, mode)`.
  - `_apply_pls_entries(self, entries: list[dict], mode: str) -> None` — `mode in {"replace", "append"}`. Replace clears via `setRowCount(0)`; both call `_add_stream_row` per entry with computed positions.
- **New class:** `_PlaylistFetchWorker(QThread)` next to `_LogoFetchWorker` in the same file (or in a new `_dialog_workers.py` if the planner chooses — see Discretion).
- **New token field:** `self._pls_fetch_token: int = 0` initialized alongside `self._logo_fetch_token` in `__init__`.
- **`aa_import._resolve_pls` body** is replaced with: `return [e["url"] for e in parse_playlist(body, content_type=resp.headers.get("Content-Type", ""), url_hint=pls_url)]`. Existing exception handler + `[pls_url]` fallback preserved for callers.

</code_context>

<specifics>
## Specific Ideas

- The user-visible promise: **"I paste an AA-style PLS URL into the editor's Streams section, click 'Add from PLS…', and the four tiered streams appear as four rows ready to save."** No edit, no manual bitrate entry, no copy-pasting from a viewer. M3U/M3U8/XSPF work the same way without the user thinking about it.
- The shared `playlist_parser` module is the one piece of net-new factoring. Everything else in the editor is plumbing: a button, a worker, two slots, an apply method.
- Phase 58 is the long-deferred Phase 49 work (backlog 999.12, deferred to v2.1 so v2.0 could ship). The AA-import path has had `_resolve_pls` for milestones; Phase 58 is the user-pointed surface that brings the same capability to manual station editing.
- Replace/Append/Cancel default of Append matches Kyle's implicit pattern across the codebase: non-destructive defaults, opt-in to destructive operations (Phase 39 delete confirm, Phase 51 Save-Discard-Cancel default Save, etc.).

</specifics>

<deferred>
## Deferred Ideas

- **HEAD/ICY probing** — fall back to a per-URL HEAD request with `Icy-MetaData: 1` when the playlist Title field doesn't carry bitrate/codec. Future polish phase if Kyle imports a station whose PLS Title is bare and the missing bitrate is annoying enough to fix interactively. Pattern would extend `_PlaylistFetchWorker` to a second pass after format parse — adds N round-trips per resolve.
- **M3U8 master-playlist `BANDWIDTH` / `CODECS` parsing** — D-12 explicitly defers `#EXT-X-STREAM-INF` attribute parsing for v1. Future phase if a real-world HLS station's metadata is materially better than the `#EXTINF` fallback.
- **Per-row preview / checkbox confirm dialog before import** — earlier rejected (D-02) in favor of the QInputDialog one-liner. If users find PLS files in the wild that contain garbage entries (e.g. ad pre-rolls, inactive servers), a future polish phase could add a custom QDialog with a per-row checklist on top of the parser output.
- **URL deduplication on import** — silently drop a resolved URL if it's already in the streams table. Captured as Claude's Discretion in D-decisions; if real-world usage shows duplicates piling up, promote to a locked decision in a follow-up.
- **PLS auto-detection in the top URL field** — the convenience field at `edit_station_dialog.py:281` could detect PLS-shape input and offer a "click to expand" toast, but this phase keeps that field logo-fetch-only per D-01 / out-of-scope.
- **Renaming STR-15 / Phase 58 to "Playlist Auto-Resolve"** — D-18 keeps the title PLS-named for v2.1. If the user feedback later treats the multi-format support as a primary capability rather than an internal extension, a docs-only follow-up renames the requirement and the button.
- **Discovery dialog / settings-import PLS expansion** — both currently bypass `EditStationDialog` and write streams directly via `repo.insert_stream`. If those paths grow PLS handling, a future phase plumbs `playlist_parser` into them. AA's `aa_import` already uses the underlying parser via the D-10 wrapper, so it's already covered.

</deferred>

---

*Phase: 58-pls-auto-resolve-in-station-editor*
*Context gathered: 2026-05-01*
