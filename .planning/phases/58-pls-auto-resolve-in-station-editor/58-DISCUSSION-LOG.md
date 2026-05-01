# Phase 58: PLS Auto-Resolve in Station Editor — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-01
**Phase:** 58-pls-auto-resolve-in-station-editor
**Areas discussed:** Trigger / entrypoint, Replace vs append, Bitrate/codec depth, Format scope

---

## Trigger / entrypoint

### Q1 — How does the user kick off PLS resolution?

| Option | Description | Selected |
|--------|-------------|----------|
| New 'Add from PLS…' button | A 5th button in the streams toolbar (next to Add/Remove/Move Up/Move Down). Click → small input dialog with paste field + OK. Predictable, discoverable, no surprise behavior on the existing 'Add' flow. | ✓ |
| Smart 'Add' button | Existing 'Add' button opens a tiny URL prompt; if the URL ends in .pls (or content-type is audio/x-scpls), expand into N rows; otherwise insert one blank-ish row with that URL. Single button does double duty. | |
| Detect on top 'URL:' field | Reuse the existing convenience URL field at the top of the dialog — if a PLS URL is typed there, run resolution alongside the existing logo fetch and append to the streams table. Lowest UI cost; deviates from brief's 'in the Streams section' wording. | |
| Inline paste field above table | A persistent QLineEdit + 'Resolve' button rendered between the Streams label and the table. Always visible, makes the feature very obvious. | |

**User's choice:** New 'Add from PLS…' button (Recommended)
**Notes:** Discoverable, no overload of existing Add semantics, lives where the brief specifies (Streams section).

### Q2 — When the user clicks 'Add from PLS…', what surface accepts the URL?

| Option | Description | Selected |
|--------|-------------|----------|
| QInputDialog one-liner | Built-in QInputDialog.getText with title 'Add from PLS' and label 'PLS URL:'. Zero new dialog code. Matches the lightweight 'paste once and go' use case. Cancel = no-op. | ✓ |
| Custom small QDialog with preview | Bespoke modal: paste field on top, 'Resolve' button, then preview list of parsed entries with checkboxes — user confirms which to import. More UI work; safer for messy PLS files. | |
| Read directly from clipboard | No dialog. Button click reads QApplication.clipboard().text(); if it looks like a PLS URL, resolve immediately; else show a brief error toast. Fastest UX but invisible failure modes. | |

**User's choice:** QInputDialog one-liner (Recommended)
**Notes:** Zero new dialog scaffolding; cancel is well-defined.

### Q3 — While the PLS HTTP fetch is in flight, what does the dialog show?

| Option | Description | Selected |
|--------|-------------|----------|
| Wait cursor + disable button | QApplication.setOverrideCursor(WaitCursor) and disable the 'Add from PLS…' button until done. Mirrors the existing _LogoFetchWorker pattern (D-10 from Phase 46-02). No new status label. Worker is a QThread with 10s urlopen timeout (matches _resolve_pls). | ✓ |
| Status label below the streams table | Tiny QLabel showing 'Resolving PLS…' / 'Found N streams' / 'PLS fetch failed'. More feedback; new widget to lay out and clear. | |
| Modal progress dialog | QProgressDialog 'Resolving PLS…' with a Cancel button. Heavier UI; lets the user abort a slow fetch. | |

**User's choice:** Wait cursor + disable button (Recommended)
**Notes:** Reuses the established `_LogoFetchWorker` D-10 cursor-restored-once-at-top-of-slot pattern.

### Q4 — If the PLS fetch fails (network error, malformed file, empty FileN= section), what happens?

| Option | Description | Selected |
|--------|-------------|----------|
| QMessageBox warning, no rows added | Show 'Could not resolve PLS: <reason>' with OK. Streams table is unchanged. User can retry or add rows manually. No destructive behavior on transient errors. | ✓ |
| Insert raw PLS URL as single row (legacy fallback) | Mirrors aa_import._resolve_pls's fallback: on failure, insert one row with the PLS URL itself as the stream URL. GStreamer can't play .pls so this is broken-by-default but matches the existing helper's contract. | |
| Silent log + no-op | Print to logger and do nothing visible. Quiet; user has to check logs to understand why nothing happened. | |

**User's choice:** QMessageBox warning, no rows added (Recommended)
**Notes:** Diverges from `_resolve_pls`'s `[pls_url]` fallback because the UI surface needs a clear failure indicator (and a single broken `.pls` row is worse than no row).

---

## Replace vs append

### Q1 — When the streams table already has rows and the user resolves a PLS, what happens to existing rows?

| Option | Description | Selected |
|--------|-------------|----------|
| Append after existing rows | New resolved rows are inserted at the end of the table, preserving existing rows. Position values continue from max(existing position) + 1. Non-destructive default; user can manually delete what they don't want. Matches how the existing 'Add' button works today. | |
| Always replace existing rows | Clear the streams table, then insert N resolved rows. Mirrors the 'paste once into new station' use case but destroys hand-curated rows on second invocation. High clobber risk. | |
| Prompt: Replace, Append, or Cancel | If existing rows are present, show a QMessageBox 3-button choice. Empty table → just append silently. Safest, but adds an extra click for the common case. | ✓ |
| Append, but offer 'Clear & Replace' from a confirm checkbox in QInputDialog | Default to append. The PLS-URL input dialog carries an unchecked '☐ Replace existing streams' checkbox the user can opt in to. | |

**User's choice:** Prompt: Replace, Append, or Cancel
**Notes:** Empty-table case skips the prompt; ambiguity only surfaces when there are real rows to clobber.

### Q2 — When the prompt fires (existing rows present), what's the default button?

| Option | Description | Selected |
|--------|-------------|----------|
| Append | Safest non-destructive default. Enter accepts Append; user has to deliberately click Replace to clobber. Cancel is the escape. | ✓ |
| Cancel | Forces a deliberate decision. Safest possible — Enter does nothing. Slightly annoying for the common 'I just want to append' case. | |
| Replace | Optimizes for the 'paste once, fresh start' use case. Aggressive default — Enter destroys existing rows. Not recommended given collision risk. | |

**User's choice:** Append (Recommended)
**Notes:** Matches Kyle's pattern across the codebase (Phase 39 delete confirm, Phase 51 Save-Discard-Cancel default Save).

### Q3 — On Append: when there are existing rows, what position numbers do new rows get?

| Option | Description | Selected |
|--------|-------------|----------|
| Continue from max(existing position) + 1 | If existing rows have positions [1, 2, 3], the resolved 4-entry PLS gets [4, 5, 6, 7]. Preserves existing failover order; new entries fall to the bottom of the priority queue. Matches Phase 47 ordering semantics (sorted by position asc). | ✓ |
| Continue from rowCount + 1 | Just N+1 where N is the visible row count. Simpler; usually equivalent unless the user has manually edited position values out-of-band (which the bitrate-based ordering tooltip discourages but the column allows). | |
| Renumber 1..N for whole table | After insert, rewrite ALL position values 1..rowCount, top-to-bottom. Cleaner table but rewrites the user's manual position edits. | |

**User's choice:** Continue from max(existing position) + 1 (Recommended)
**Notes:** Preserves user's manually-set position values.

### Q4 — On Replace: are stream rows deleted from the DB immediately, or only marked for deletion until Save?

| Option | Description | Selected |
|--------|-------------|----------|
| Marked for deletion until Save | Removing rows from the QTableWidget is a UI-only operation — the existing _on_remove_stream button already works this way (no DB write until Save). 'Replace' just clears all table rows in-memory; persistence happens in _on_save. If user clicks Discard, original rows are intact in DB. Consistent with the existing Save/Discard contract. | ✓ |
| Delete from DB immediately | On Replace, call repo.delete_stream(...) for each existing row. Faster save but breaks the Discard contract (user can't undo). Diverges from current dialog behavior. | |

**User's choice:** Marked for deletion until Save (Recommended)
**Notes:** Preserves Save/Discard contract; existing `_on_save` reconcile pass handles the diff naturally.

---

## Bitrate/codec depth

### Q1 — How aggressively do we try to populate Bitrate (kbps) and Codec for resolved entries?

| Option | Description | Selected |
|--------|-------------|----------|
| PLS Title parse only | Parse the TitleN= line per FileN= entry; extract bitrate via regex and codec via known tokens. Anything not matched → 0 / blank. Fast, no extra HTTP. Most AA/SomaFM/etc PLS files have usable Title metadata. | ✓ |
| PLS Title parse + ICY HEAD probe | After Title parse, fire a HEAD request per resolved URL with 'Icy-MetaData: 1' and a short timeout (~3s); read 'icy-br' (bitrate) and 'Content-Type' (codec). Probe ONLY fills fields that Title parse left as 0/blank. Slower (N round-trips) but fills in stations whose PLS has bare URLs and no Title. | |
| No probing — default 0/unknown | Fastest, dumbest. Bitrate=0, Codec='', Quality=Title-text-as-is (or blank). User edits manually if they want better data. Lowest implementation surface; least value. | |
| PLS Title parse + ICY probe ONLY when Title parse fails | Same as option 2 but skip the probe entirely if Title parse already produced bitrate AND codec. Hybrid — fast common path, fallback only when needed. | |

**User's choice:** PLS Title parse only (Recommended)
**Notes:** Avoids the latency + dead-server-hang risk of HEAD probes; ICY probing deferred as a future polish phase.

### Q2 — Quality column free-text label — what goes there?

| Option | Description | Selected |
|--------|-------------|----------|
| Full PLS TitleN= text | Whatever Title field the PLS provides. Lets the user identify the entry without copy-pasting from the URL. Phase 47 retained Quality as a free-text label for exactly this kind of stuff. | ✓ |
| Tier label extracted from Title | Try to extract just the tier portion (e.g. '128k', 'Premium'). More structured but needs heuristics; loses station-name context. | |
| Leave blank | Bitrate column carries the kbps; codec column carries the codec; Quality is redundant. Cleaner but loses the 'which row is which' signal when 4 rows have similar URLs and same bitrate. | |

**User's choice:** Full PLS TitleN= text (Recommended)
**Notes:** Same approach extends to M3U/M3U8 #EXTINF display name and XSPF <title> in D-12/D-13.

### Q3 — Codec column behavior when no recognized token matches the title

| Option | Description | Selected |
|--------|-------------|----------|
| Leave codec blank | Bitrate parsed; codec stays empty. User can edit manually. Phase 47 ordering tolerates blank codec via codec_rank None-safety; no failover regression. | ✓ |
| Fall back to last 'word' in title | Heuristic: grab the last whitespace-separated token as the codec. Sometimes useful, sometimes garbage. | |
| Use 'unknown' literal | Insert the string 'unknown' so the user sees something rendered. Distinct from blank but un-actionable. | |

**User's choice:** Leave codec blank (Recommended)
**Notes:** Avoids garbage data downstream of failover ranking.

### Q4 — Where does the PLS parser live?

| Option | Description | Selected |
|--------|-------------|----------|
| New helper in url_helpers.py, deprecate aa_import._resolve_pls | Promote PLS parsing to a single source of truth as parse_pls(body) -> list[dict] with keys {url, title, bitrate_kbps, codec}. aa_import._resolve_pls becomes a thin wrapper that drops everything but url. Mirrors Phase 64's render_sibling_html promotion pattern. | ✓ |
| Extend aa_import._resolve_pls in place | Change return type to list[dict]; update both AA callers. Cohabitation works but ties station-editor logic to the AA-import module. | |
| New private helper in edit_station_dialog.py | Add a _parse_pls(body) staticmethod or module-level function in the dialog file. Smallest blast radius; harder to test in isolation. | |

**User's choice:** New helper, deprecate aa_import._resolve_pls (Recommended)
**Notes:** Implementation diverges slightly from option label — the new helper lives in a dedicated `musicstreamer/playlist_parser.py` module (since it grew to handle PLS + M3U + M3U8 + XSPF). `url_helpers.py` would have been overloaded.

---

## Format scope

### Q1 — Strict PLS only, or accept other playlist formats too?

| Option | Description | Selected |
|--------|-------------|----------|
| PLS only | STR-15 names PLS specifically. All AA imports are PLS. Smallest parser surface, smallest test matrix. M3U/M3U8/XSPF can be added in a future polish phase. | |
| PLS + M3U/M3U8 | Same shape (URL-per-line for M3U; #EXTINF metadata). Adds parser work but covers more stations. Doubles test matrix. | |
| PLS + M3U/M3U8 + XSPF | Three formats. XSPF is XML, very different parser. Comprehensive but widens scope significantly. | ✓ |
| Detect format by Content-Type, parse whatever | Format-agnostic: HEAD request returns Content-Type, dispatch to per-format parser. Most flexible, biggest scope. | |

**User's choice:** PLS + M3U/M3U8 + XSPF
**Notes:** Scope expansion accepted explicitly. Phase title and STR-15 stay PLS-named (D-18); multi-format support is a quiet internal extension.

### Q2 — Title scope: rename phase, or keep "PLS Auto-Resolve"?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep title, support all internally | Phase title and STR-15 stay 'PLS' — the user-facing entrypoint stays 'Add from PLS…'. Internally the parser dispatches by extension/content-type. M3U and XSPF support is a quiet extension. | ✓ |
| Rename phase to 'Playlist Auto-Resolve' | Update ROADMAP.md Phase 58 title and STR-15 wording to 'playlist URL'. Button label becomes 'Add from playlist…'. More accurate but expands the docs change. | |
| Rename only the user-facing button, keep ROADMAP title | Button is 'Add from playlist…' but ROADMAP/STR-15 stay PLS-named. Hybrid; docs slightly out of sync. | |

**User's choice:** Keep title, support all internally (Recommended)
**Notes:** Familiar button label, low docs churn; tooltip surfaces the multi-format support.

### Q3 — How is the playlist format detected?

| Option | Description | Selected |
|--------|-------------|----------|
| URL extension first, Content-Type fallback | Inspect URL path: '.pls'/'.m3u'/'.m3u8'/'.xspf'. If extension missing/unrecognized, GET the body, inspect Content-Type header and dispatch. One round-trip per resolve. | ✓ |
| Sniff body content (no Content-Type trust) | Always GET body, then detect by content shape: '[playlist]' header → PLS, '#EXTM3U' first line → M3U, '<?xml' + 'xspf' element → XSPF. Robust against servers that lie about Content-Type. | |
| Both: extension hint + body sniff fallback | Use extension to pick a parser; if parsing fails, fall back to body sniffing. Most robust; slightly more error paths. | |

**User's choice:** URL extension first, Content-Type fallback (Recommended)
**Notes:** No body sniffing; cheaper detection. If a server lies about Content-Type and the URL has no extension, the parse fails cleanly with the QMessageBox warning (D-05).

### Q4 — M3U/M3U8 metadata: how do we treat #EXTINF lines?

| Option | Description | Selected |
|--------|-------------|----------|
| Display name → Quality column; ignore duration | #EXTINF:-1,Some Station Name — take 'Some Station Name' into Quality (mirrors PLS TitleN=). Bitrate/codec parsed from the same string with the regex used for PLS. Duration (-1 for streams) ignored. | ✓ |
| Parse M3U8 attributes (BANDWIDTH, CODECS) from #EXT-X-STREAM-INF | M3U8 master playlists carry BANDWIDTH=N + CODECS='...' on #EXT-X-STREAM-INF lines. Higher fidelity for HLS but adds parser logic. | |
| Just take URLs, ignore all metadata | M3U/M3U8: insert one row per non-comment URL line with everything else blank. Simplest; loses all info. | |

**User's choice:** Display name → Quality column; ignore duration (Recommended)
**Notes:** #EXT-X-STREAM-INF parsing deferred (D-12). Same regex/token logic as PLS Title parse — single helper.

### Q5 — XSPF parser — stdlib or skip?

| Option | Description | Selected |
|--------|-------------|----------|
| Stdlib xml.etree.ElementTree | Already in stdlib, no new dependency. XSPF is namespaced XML. defusedxml is optional optimization. | ✓ |
| Plain ElementTree (no defusedxml) | Same as above; explicitly accept that user-pasted XSPF could include XXE/billion-laughs payloads. Threat surface: user pastes a URL into their own station editor; nothing crosses trust boundary. | |
| Drop XSPF, just PLS+M3U/M3U8 | Reverse the earlier decision. XSPF is rare in the wild for radio streams. | |

**User's choice:** Stdlib xml.etree.ElementTree (Recommended)
**Notes:** No `defusedxml` dependency added. Threat-surface assessment in D-13 documents the acceptance.

---

## Claude's Discretion

- Exact button placement within the streams toolbar row (after "Move Down" recommended, but planner can group with "Add" if visual reasons surface).
- Exact `QMessageBox.warning` failure message wording (shape locked, wording planner's call).
- Whether `QMessageBox.question` 3-button form vs custom button-box for Replace/Append/Cancel (standard form preferred for stylistic consistency).
- Location of `_PlaylistFetchWorker` class — in-file with `_LogoFetchWorker`, or extract both to `_dialog_workers.py` as a real cleanup.
- Test fixture shapes for `tests/test_playlist_parser.py` and the `tests/test_edit_station_dialog.py` extension.
- URL deduplication on import (default no dedup; planner picks if trivial implementation + tests show value).
- Dirty-state baseline interaction (planner verifies snapshot mechanism picks up resolved rows; no code change expected).

## Deferred Ideas

- **HEAD/ICY probing** for missing bitrate/codec when Title parse is bare.
- **M3U8 master-playlist `BANDWIDTH`/`CODECS` attribute parsing** from `#EXT-X-STREAM-INF`.
- **Per-row preview/checkbox confirm dialog** before import (custom QDialog).
- **URL deduplication** on import.
- **PLS auto-detection in the top URL field** (kept logo-fetch-only).
- **Renaming STR-15 / Phase 58 to "Playlist Auto-Resolve"** if multi-format support becomes the primary capability narrative.
- **Discovery dialog / settings-import PLS expansion** — already covered for AA via `aa_import._resolve_pls` wrapper.
