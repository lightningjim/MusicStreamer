# Phase 58: PLS Auto-Resolve in Station Editor — Research

**Researched:** 2026-05-01
**Domain:** Playlist parsing (PLS/M3U/M3U8/XSPF), QThread worker pattern, PySide6 modal dialogs
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** 5th button "Add from PLS…" (U+2026 ellipsis) after "Move Down" in `_build_ui`. Tooltip lists all 4 formats.
- **D-02:** Click handler opens `QInputDialog.getText`; Cancel/empty → no-op; no clipboard auto-read.
- **D-03:** `QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))` + `add_pls_btn.setEnabled(False)` during fetch. Cursor restored once at top of slot (D-10 pattern).
- **D-04:** New `_PlaylistFetchWorker(QThread)` with `(url, token, parent=None)`, `finished = Signal(list, str, int)`, exception-swallowing `run()`.
- **D-05:** Failure → `QMessageBox.warning`, table unchanged. No fallback-to-pls-url row (unlike `_resolve_pls`).
- **D-06:** Non-empty table → 3-button `QMessageBox.question` (Replace / Append / Cancel). Default = Append. Empty table → silent append.
- **D-07:** Replace = `setRowCount(0)` (UI-only). No `repo.delete_stream` at clear-time. `_on_save` reconcile prunes orphaned IDs.
- **D-08:** Append starts from `max(existing position) + 1`, maintains file-order.
- **D-09:** New `musicstreamer/playlist_parser.py` with `parse_playlist(body, content_type, url_hint) -> list[dict]`.
- **D-10:** `aa_import._resolve_pls` refactored to delegate to `parse_playlist`; both call sites at lines 135 and 177 preserved via thin wrapper preserving `list[str]` signature and `[pls_url]` fallback.
- **D-11:** PLS parse: `r"(\d+)\s*k(?:b(?:ps)?)?\b"` (case-insensitive) for bitrate; priority-ordered token scan for codec; full Title text as `title`.
- **D-12:** M3U/M3U8 parse: walk lines, pair `#EXTINF:DUR,DISPLAY_NAME` with next URL line. `#EXT-X-STREAM-INF` deferred.
- **D-13:** XSPF: `xml.etree.ElementTree.fromstring(body)`. No `defusedxml`. Worker exception handler covers parser errors.
- **D-14:** Quality column = full `title` field.
- **D-15:** Codec column blank when no recognized token found.
- **D-16:** Bitrate=0 renders as empty string (existing `_add_stream_row` convention at line 621-624).
- **D-17:** Decode PLS/M3U/M3U8 bytes as `body.decode("utf-8", errors="replace")`. XSPF bytes passed directly to `ET.fromstring`.
- **D-18:** Phase title stays "PLS Auto-Resolve". Button label stays "Add from PLS…". Multi-format is internal.
- **D-19:** Format detection: URL extension first, Content-Type second, give up third. No body sniffing.

### Claude's Discretion
- Button placement within the row (after "Move Down" recommended)
- `QMessageBox.warning` exact wording on failure
- Whether Replace/Append uses `QMessageBox.question` 3-button or custom button-box
- Location of `_PlaylistFetchWorker` (same file vs. `_dialog_workers.py` extraction)
- Test placement and fixture shapes
- Per-call URL deduplication (default: no dedup)
- Dirty-state: no code change needed (existing `_add_stream_row` feeds `_is_dirty` snapshot)

### Deferred Ideas (OUT OF SCOPE)
- HEAD/ICY probing per resolved URL
- M3U8 master-playlist `#EXT-X-STREAM-INF BANDWIDTH/CODECS` parsing
- Per-row preview/checkbox confirm dialog
- URL deduplication on import (unless trivial, planner's call)
- PLS auto-detection in the top URL field
- Renaming STR-15 / Phase 58 to "Playlist Auto-Resolve"
- Discovery dialog / settings-import PLS expansion
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STR-15 | User can paste a PLS URL into a station's Streams section and have it auto-resolve into N individual stream entries (one per playlist row) | All four format parsers + worker pattern + Replace/Append dialog + `_add_stream_row` integration fully researched |
</phase_requirements>

---

## Summary

Phase 58 introduces a "Add from PLS…" button to `EditStationDialog` that fetches a playlist URL, parses it (PLS, M3U, M3U8, or XSPF), and inserts one stream-table row per playlist entry. The UI change is a small button addition on an existing toolbar row; the main net-new work is `musicstreamer/playlist_parser.py` (pure module, no Qt), `_PlaylistFetchWorker(QThread)` (mirrors `_LogoFetchWorker`), and three new methods on `EditStationDialog` (`_on_add_pls`, `_on_pls_fetched`, `_apply_pls_entries`). Existing `aa_import._resolve_pls` is refactored to delegate to the new shared parser.

All architectural choices (D-01..D-19) are pre-locked in CONTEXT.md. Research confirms:
1. Every locked library API (`QMessageBox.addButton`, `setDefaultButton`, `clickedButton`, `urllib.request.urlopen`, `xml.etree.ElementTree.fromstring`, worker `wait()` pattern) works exactly as specified in PySide6 6.11.0 / Python 3.10+.
2. The bitrate regex and codec token list have two known edge-case findings the planner should address in the parser implementation.
3. The `_shutdown_logo_fetch_worker` pattern (`disconnect + wait(2000)`) is the exact template for `_shutdown_pls_fetch_worker` — both must be called from `accept()`, `closeEvent()`, and `reject()`.
4. `xml.etree.ElementTree` does NOT resolve external SYSTEM entities (XXE safe) but DOES expand internal entity references (billion-laughs risk is negligible for 2-3 levels, but a deeply nested entity could expand to ~310 KB in <5ms — acceptable for the user-pasted threat model per D-13).
5. No existing pluralization helper exists; inline ternary is the idiomatic pattern for this codebase.

**Primary recommendation:** Implement in 3 plans: (1) `playlist_parser.py` + tests + `_resolve_pls` refactor, (2) `_PlaylistFetchWorker` + dialog methods + button, (3) integration/edge-case tests.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Playlist fetch (HTTP) | Background QThread worker | — | Follows `_LogoFetchWorker` precedent; I/O must not block Qt main thread |
| Playlist parsing (PLS/M3U/M3U8/XSPF) | Pure Python module (`playlist_parser.py`) | — | No Qt dependency; independently unit-testable |
| Format dispatch (extension / Content-Type) | `playlist_parser.parse_playlist` | — | Belongs with parsing logic, not in the worker or dialog |
| Replace/Append UI prompt | Qt main thread (`_on_pls_fetched` slot) | — | Modal dialog must run on main thread |
| Row insertion into streams table | Qt main thread (`_apply_pls_entries`) | — | `QTableWidget` is not thread-safe |
| Dirty-state propagation | Existing `_capture_dirty_baseline` / `_is_dirty` | — | No new code; `_add_stream_row` already feeds snapshot |
| Persistence | Existing `_on_save` reconcile pass | — | No schema change; new rows persist via `stream_id=None` → `insert_stream` path |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `urllib.request` | stdlib | HTTP fetch of playlist body | Already used by `_resolve_pls`; no new deps [VERIFIED: existing codebase] |
| `xml.etree.ElementTree` | stdlib | XSPF XML parsing | Stdlib; D-13 explicitly accepts; no `defusedxml` per D-13 [VERIFIED: existing codebase] |
| `re` | stdlib | Bitrate regex, PLS line matching | Already used throughout musicstreamer [VERIFIED: existing codebase] |
| `PySide6.QtCore.QThread`, `Signal` | 6.11.0 | Background worker | Established pattern via `_LogoFetchWorker` [VERIFIED: codebase + runtime] |
| `PySide6.QtWidgets.QMessageBox` | 6.11.0 | Replace/Append/Cancel + warning dialogs | addButton/setDefaultButton/clickedButton API confirmed [VERIFIED: runtime] |
| `PySide6.QtWidgets.QInputDialog` | 6.11.0 | URL input prompt | Existing pattern in dialog [VERIFIED: codebase] |

### No New Dependencies
Phase 58 introduces zero new `pyproject.toml` entries. All required libraries are stdlib (`urllib.request`, `xml.etree.ElementTree`, `re`, `socket`) or already in the project (`PySide6`). [VERIFIED: CONTEXT.md D-09 + pyproject.toml]

---

## Architecture Patterns

### System Architecture Diagram

```
User clicks "Add from PLS…"
        |
        v
[_on_add_pls]
  QInputDialog.getText → URL
  if not ok or not url.strip(): return
        |
        v
  _pls_fetch_token += 1
  add_pls_btn.setEnabled(False)
  setOverrideCursor(WaitCursor)
  _PlaylistFetchWorker(url, token).start()
        |
        v (background thread)
[_PlaylistFetchWorker.run()]
  urlopen(url, timeout=10)
    -> bytes body + resp.headers
  content_type = resp.headers.get("Content-Type", "")
  body_str = body.decode("utf-8", errors="replace")   [PLS/M3U/M3U8]
  OR body bytes direct to ET.fromstring               [XSPF]
        |
        v
  playlist_parser.parse_playlist(body_str, content_type, url_hint=url)
    -> list[dict{url,title,bitrate_kbps,codec}]
  emit finished(entries, error_msg, token)
        |
        v (Qt main thread, queued)
[_on_pls_fetched(entries, error_msg, token)]
  restoreOverrideCursor()                  ← ALWAYS FIRST
  add_pls_btn.setEnabled(True)
  if token != _pls_fetch_token: return     ← stale discard
  if error_msg or not entries: QMessageBox.warning → return
  if streams_table.rowCount() > 0:
    QMessageBox.question (Replace/Append/Cancel)
  else:
    _apply_pls_entries(entries, mode="append")
        |
        v
[_apply_pls_entries(entries, mode)]
  if mode=="replace": streams_table.setRowCount(0)
  compute start_position from max(existing position)+1
  for each entry: _add_stream_row(url, title, codec, bitrate, position, stream_id=None)
        |
        v
[_on_save (existing — unchanged)]
  stream_id=None rows → repo.insert_stream(...)
  stream_id-set rows → repo.update_stream(...)
  repo.reorder_streams(station.id, ordered_ids)
  [streams with IDs absent from ordered_ids are pruned by reorder_streams semantics]
```

### Recommended Project Structure

```
musicstreamer/
├── playlist_parser.py          # NEW: parse_playlist + _parse_pls/_parse_m3u/_parse_xspf
├── ui_qt/
│   └── edit_station_dialog.py  # MODIFIED: _PlaylistFetchWorker, 3 new methods, new button
tests/
├── test_playlist_parser.py     # NEW: pure parser tests (no Qt)
└── test_edit_station_dialog.py # EXTENDED: PLS button, worker, Replace/Append/Cancel
```

### Pattern 1: _PlaylistFetchWorker — Mirror of _LogoFetchWorker

The exact shape to mirror (from `edit_station_dialog.py:54-122`):

```python
# Source: musicstreamer/ui_qt/edit_station_dialog.py:54-122 [VERIFIED]
class _PlaylistFetchWorker(QThread):
    """Background playlist fetcher. Emits finished(entries, error_message, token).

    entries: list[dict] on success, [] on failure.
    error_message: "" on success, user-readable reason on failure.
    token: monotonic stale-discard token from _pls_fetch_token.
    """
    finished = Signal(list, str, int)  # entries, error_message, token

    def __init__(self, url: str, token: int, parent=None):
        super().__init__(parent)
        self.setObjectName("playlist-fetch-worker")
        self._url = url
        self._token = token

    def run(self):
        token = self._token
        try:
            import urllib.request, urllib.error, socket
            from musicstreamer.playlist_parser import parse_playlist
            with urllib.request.urlopen(self._url, timeout=10) as resp:
                content_type = resp.headers.get("Content-Type", "")
                raw = resp.read()
            entries = parse_playlist(
                raw.decode("utf-8", errors="replace"),
                content_type=content_type,
                url_hint=self._url,
            )
            if not entries:
                self.finished.emit([], "No entries found.", token)
                return
            self.finished.emit(entries, "", token)
        except urllib.error.HTTPError as e:
            self.finished.emit([], f"HTTP {e.code}: {e.reason}", token)
        except urllib.error.URLError as e:
            self.finished.emit([], f"URL error: {e.reason}", token)
        except TimeoutError:
            self.finished.emit([], "Timed out after 10 seconds.", token)
        except UnicodeDecodeError as e:
            self.finished.emit([], f"Encoding error: {e}", token)
        except Exception:  # noqa: BLE001
            self.finished.emit([], "Unexpected error fetching playlist.", token)
```

**Key deviation from `_LogoFetchWorker`:** The XSPF path passes `raw` (bytes) to `ET.fromstring` inside `parse_playlist`; the worker decodes text for PLS/M3U/M3U8 via `errors="replace"` before passing to the parser. `parse_playlist` must handle the decode-vs-bytes dispatch internally (see D-17). [VERIFIED: codebase]

### Pattern 2: Worker Lifecycle — _shutdown_pls_fetch_worker

The `_shutdown_logo_fetch_worker` pattern (lines 814-829) must be replicated exactly for `_PlaylistFetchWorker`:

```python
# Source: edit_station_dialog.py:814-829 [VERIFIED]
def _shutdown_pls_fetch_worker(self) -> None:
    """Bound-wait so QThread: Destroyed while thread still running crash is prevented."""
    worker = self._pls_fetch_worker
    if worker is None or not worker.isRunning():
        return
    try:
        worker.finished.disconnect()
    except Exception:
        pass
    worker.wait(2000)
```

This must be called from `accept()`, `closeEvent()`, and `reject()` — the same three overrides that call `_shutdown_logo_fetch_worker`. [VERIFIED: codebase lines 831-858]

**Why:** PySide6/Qt raises `QThread: Destroyed while thread '' is still running` if the parent dialog is deleted while its child QThread is running. The existing logo fetch worker has the same crash documented (commit comment at line 833-836). Phase 58 introduces the same risk. [VERIFIED: codebase]

### Pattern 3: Stale-Token Check

```python
# Source: edit_station_dialog.py:754 [VERIFIED]
# Logo worker pattern (verbatim, for comparison):
if token and token != self._logo_fetch_token:
    ...return

# PLS worker equivalent:
if token != self._pls_fetch_token:
    return  # cursor already restored above
```

**Note:** The logo worker checks `if token and token != ...` (skips check when token=0) because `_on_logo_fetched` is also called directly from tests with `token=0`. The PLS worker's `_on_pls_fetched` may use the same defensive `token != self._pls_fetch_token` pattern since `_pls_fetch_token` starts at 0 and increments before first use. Tests should always pass a valid token. [VERIFIED: codebase]

### Pattern 4: QMessageBox with Custom Button Roles

PySide6 6.11.0 confirmed API (runtime-verified):

```python
# Source: PySide6 6.11.0 runtime verification [VERIFIED]
msg_box = QMessageBox(self)
msg_box.setWindowTitle("Import Playlist Streams")
msg_box.setText(
    f"This station has {n} existing {stream_word}.\n\n"
    f"Replace them with the {m} resolved "
    f"{'entry' if m == 1 else 'entries'}, or append the new "
    f"{'entry' if m == 1 else 'entries'} after the existing ones?"
)
replace_btn = msg_box.addButton("Replace", QMessageBox.DestructiveRole)
append_btn  = msg_box.addButton("Append",  QMessageBox.AcceptRole)
cancel_btn  = msg_box.addButton("Cancel",  QMessageBox.RejectRole)
msg_box.setDefaultButton(append_btn)  # setDefaultButton(QPushButton) confirmed working
msg_box.exec()

clicked = msg_box.clickedButton()
if clicked is replace_btn:
    self._apply_pls_entries(entries, mode="replace")
elif clicked is append_btn:
    self._apply_pls_entries(entries, mode="append")
# else: Cancel — no-op
```

`addButton(str, Role)` returns `QPushButton`. `setDefaultButton(QPushButton)` works. `clickedButton()` returns the button or None. `QMessageBox.DestructiveRole`, `AcceptRole`, `RejectRole` are `ButtonRole` enum members (not int) in PySide6 6.11. [VERIFIED: runtime]

### Pattern 5: playlist_parser.py Public Interface

```python
# Proposed implementation shape [VERIFIED: based on D-09..D-17]
def parse_playlist(
    body: str,
    content_type: str = "",
    url_hint: str = "",
) -> list[dict]:
    """Dispatch to PLS/M3U/M3U8/XSPF parser by URL extension then Content-Type.

    Returns list[{url: str, title: str, bitrate_kbps: int, codec: str}].
    Returns [] when format is unrecognized (not an error — caller decides).
    """
    import urllib.parse
    path = urllib.parse.urlparse(url_hint).path.lower()
    ext = os.path.splitext(path)[1]

    if ext == ".pls":
        return _parse_pls(body)
    if ext in (".m3u", ".m3u8"):
        return _parse_m3u(body)
    if ext == ".xspf":
        return _parse_xspf(body)

    # Fallback: Content-Type dispatch
    ct = content_type.lower().split(";")[0].strip()
    if ct in ("audio/x-scpls", "audio/scpls"):
        return _parse_pls(body)
    if ct in ("audio/x-mpegurl", "audio/mpegurl", "application/vnd.apple.mpegurl"):
        return _parse_m3u(body)
    if ct == "application/xspf+xml":
        return _parse_xspf(body)

    return []
```

**XSPF note:** `_parse_xspf` receives the raw `bytes` object (not decoded `str`) and calls `ET.fromstring(bytes_body)`. The caller (`_PlaylistFetchWorker.run`) must NOT decode XSPF bytes through `errors="replace"` before passing to the parser — `ET.fromstring` handles encoding via the XML prologue. The `parse_playlist(body: str, ...)` signature implies the text path; XSPF should accept bytes. The planner should make `parse_playlist` accept `bytes | str` or split the XSPF decode responsibility. [ASSUMED — the exact bytes-vs-str signature split needs planner decision; D-17 implies worker decodes before calling parse_playlist but ET needs bytes]

### Anti-Patterns to Avoid

- **Calling `repo.delete_stream` on Replace**: D-07 explicitly forbids it. Only `setRowCount(0)` at UI-level; `_on_save` reconcile handles DB pruning via reorder_streams.
- **Restoring cursor after stale-token check**: D-03/D-10 invariant — cursor restore MUST be the FIRST action in `_on_pls_fetched`, before the stale-token check, before any conditional logic. One `setOverrideCursor` → exactly one `restoreOverrideCursor`. [VERIFIED: codebase pattern]
- **Lambda in signal connection**: QA-05 requires bound-method connections. `self.add_pls_btn.clicked.connect(self._on_add_pls)` — no lambda.
- **Missing `_shutdown_pls_fetch_worker()` in `accept()`**: The existing `_shutdown_logo_fetch_worker` was missing from `accept()` and caused a crash (see commit note at line 833). Phase 58 must call `_shutdown_pls_fetch_worker()` from all three override methods. [VERIFIED: codebase]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| XML namespace parsing | Manual string-strip of `{ns}` prefix | `ET.findall(f'.//{{{ns}}}track')` with f-string ns | ElementTree requires namespace-qualified tags — confirmed working [VERIFIED: runtime] |
| Custom QDialog for Replace/Append | New QDialog with QVBoxLayout etc. | `QMessageBox.addButton(label, role)` | 3-button custom-role QMessageBox is exactly the right tool; Phase 51-04 sibling dialog uses same pattern [VERIFIED: codebase] |
| HTTP client | `requests` library | `urllib.request.urlopen` | Already used by `_resolve_pls`; no new dep needed |
| Bitrate regex | Custom parser | `re.compile(r"(\d+)\s*k(?:b(?:ps)?)?\b", re.IGNORECASE)` | Already specified in D-11; verified against real-world titles |
| Worker lifecycle management | Custom thread pool / asyncio | `QThread.wait(2000)` in shutdown method | Established pattern from `_LogoFetchWorker` [VERIFIED: codebase] |

---

## Research Findings by Question

### Q1: Format Spec Details and Parser Pseudocode

#### PLS Format

PLS is an INI-style format. Structure:
```
[playlist]
NumberOfEntries=N
File1=<url>
Title1=<display name>
Length1=-1    (optional)
File2=<url>
...
Version=2    (optional)
```

**Edge cases observed in the wild:**

1. **Missing TitleN for some FileN entries** — valid per spec. Parser must use `title_dict.get(n, "")` (default empty string). [VERIFIED: runtime test]
2. **BOM (U+FEFF) at file start** — appears in latin-1 / Windows-1252 encoded PLS files from some Eastern European stations. `decode("utf-8", errors="replace")` produces `�` replacement char at start of first line; strip BOM before parsing. Add `line.strip().lstrip('﻿')` to first-line processing OR call `body.lstrip('﻿')` on the decoded string. [ASSUMED — BOM stripping is a common real-world requirement; verified by test fixture]
3. **CRLF line endings** — `body.splitlines()` handles both `\r\n` and `\n`. [VERIFIED: runtime test]
4. **Case variation in keys** — `File1=` vs `file1=` vs `FILE1=`. Use case-insensitive regex: `re.match(r"^[Ff]ile(\d+)=(.+)$", line)` OR `re.match(r"^File(\d+)=(.+)$", line, re.IGNORECASE)`. [VERIFIED: runtime test]
5. **File-order preservation** — collect `(int_index, url)` pairs, sort by index before emitting. This is the gap-06 invariant from `_resolve_pls`. [VERIFIED: codebase]

**Parser pseudocode (D-09 / D-11):**

```python
def _parse_pls(body: str) -> list[dict]:
    url_dict: dict[int, str] = {}
    title_dict: dict[int, str] = {}
    for line in body.splitlines():
        line = line.strip().lstrip('﻿')  # BOM safety
        m = re.match(r"^File(\d+)=(.+)$", line, re.IGNORECASE)
        if m:
            url_dict[int(m.group(1))] = m.group(2).strip()
            continue
        m = re.match(r"^Title(\d+)=(.+)$", line, re.IGNORECASE)
        if m:
            title_dict[int(m.group(1))] = m.group(2).strip()

    result = []
    for idx in sorted(url_dict):
        title = title_dict.get(idx, "")
        result.append({
            "url": url_dict[idx],
            "title": title,
            "bitrate_kbps": _extract_bitrate(title),
            "codec": _extract_codec(title),
        })
    return result
```

#### M3U/M3U8 Format

M3U is a line-per-URL format; M3U8 (UTF-8 encoded M3U) adds the `#EXTM3U` header and `#EXTINF` directives.

**Structure:**
```
#EXTM3U          (optional but conventional)
#EXTINF:-1,Display Name Here
http://stream.url/path.mp3
#EXTINF:-1,Another Stream
http://another.url/stream.ogg
```

**Edge cases observed:**

1. **Missing `#EXTM3U` header** — plain `.m3u` files often omit it. Parser must not require it. [VERIFIED: runtime test — "Plain M3U without header" works]
2. **URL lines with no preceding `#EXTINF`** — treat title as empty string. [VERIFIED: runtime test]
3. **Comments between `#EXTINF` and URL line** — lines starting `#` that are NOT `#EXTINF` are skipped; the `prev_extinf` accumulator is only reset on a URL line, NOT on other comment lines. The current pseudocode correctly handles this. [VERIFIED: runtime test]
4. **`#EXTINF` with extended attributes** — form is `#EXTINF:-1 attr1="val" attr2="val",Display Name`. The display name starts after the FIRST comma. [VERIFIED: runtime test — extended attrs correctly stripped]
5. **Empty lines** — skip (`.strip()` → falsy).
6. **`#EXT-X-STREAM-INF`** — not parsed per D-12. Lines starting with `#EXT-X-` are treated as comments and skipped.

**Parser pseudocode (D-09 / D-12):**

```python
def _parse_m3u(body: str) -> list[dict]:
    result = []
    prev_extinf: str | None = None
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXTM3U"):
            continue
        if line.startswith("#EXTINF:"):
            comma = line.find(",")
            prev_extinf = line[comma + 1:].strip() if comma != -1 else ""
        elif line.startswith("#"):
            pass  # other directive or comment — do not clear prev_extinf
        else:
            title = prev_extinf or ""
            result.append({
                "url": line,
                "title": title,
                "bitrate_kbps": _extract_bitrate(title),
                "codec": _extract_codec(title),
            })
            prev_extinf = None
    return result
```

#### XSPF Format

XSPF is an XML-based playlist format. Namespace: `http://xspf.org/ns/0/`. Structure:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<playlist version="1" xmlns="http://xspf.org/ns/0/">
  <trackList>
    <track>
      <location>http://stream.url</location>
      <title>Display Name 128k MP3</title>
    </track>
  </trackList>
</playlist>
```

**Edge cases:**

1. **Namespace prefix variation** — some XSPF files use `<xspf:track>` with a `xmlns:xspf="http://xspf.org/ns/0/"` prefix. ElementTree's `{ns}tagname` syntax handles both default namespace and prefixed namespace when using `findall`. [VERIFIED: runtime — confirmed `{http://xspf.org/ns/0/}track` works for default-namespace XSPF]
2. **Extension elements** — `<extension application="..."><some:field/></extension>` within `<track>`. These are silently ignored by the parser (we only read `<location>` and `<title>`). [ASSUMED — common pattern; ET.findall with specific tag names ignores unrecognized children]
3. **Multiple `<location>` elements per track** — XSPF spec allows alternates. Take `track.find(f'{{{ns}}}location')` — finds the first, which is correct. [ASSUMED based on spec knowledge]
4. **Missing `<location>`** — skip the track (no URL = not a valid stream entry). `if loc is None: continue`
5. **Missing `<title>`** — title defaults to empty string. `title_el.text if title_el is not None else ""`

**Parser pseudocode (D-09 / D-13):**

```python
def _parse_xspf(body: bytes) -> list[dict]:
    """body is raw bytes — ET.fromstring handles encoding via XML prologue."""
    import xml.etree.ElementTree as ET
    ns = "http://xspf.org/ns/0/"
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return []
    result = []
    for track in root.findall(f".//{{{ns}}}track"):
        loc_el = track.find(f"{{{ns}}}location")
        if loc_el is None or not loc_el.text:
            continue
        title_el = track.find(f"{{{ns}}}title")
        title = (title_el.text or "") if title_el is not None else ""
        url = loc_el.text.strip()
        result.append({
            "url": url,
            "title": title,
            "bitrate_kbps": _extract_bitrate(title),
            "codec": _extract_codec(title),
        })
    return result
```

**Important:** `_parse_xspf(body: bytes)` takes bytes, not str. This requires the `parse_playlist` caller signature to handle bytes vs str for the XSPF branch. See the `[ASSUMED]` note in Pattern 5 above — the planner must decide whether `parse_playlist` accepts `bytes | str` or whether the worker passes bytes separately for XSPF. The simplest solution: `parse_playlist(body: str, ..., raw_bytes: bytes | None = None)` and use `raw_bytes` for XSPF, or detect XSPF format before decode and pass bytes conditionally. [ASSUMED — planner's call on the exact signature]

### Q2: Bitrate/Codec Regex Stress Testing

**Bitrate regex: `r"(\d+)\s*k(?:b(?:ps)?)?\b"` (case-insensitive)**

Runtime-verified against real-world titles [VERIFIED: runtime]:

| Title | Result |
|-------|--------|
| `"SomaFM - Indie Pop Rocks! 128k AAC"` | 128 ✓ |
| `"Radio Paradise 320 kbps MP3"` | 320 ✓ |
| `"DI.fm Ambient 64kb"` | 64 ✓ |
| `"AudioAddict HE-AAC 64kbps"` | 64 ✓ |
| `"Jazz 24 192 Kbps"` | 192 ✓ |
| `"BBC Radio 1 (No bitrate)"` | NO MATCH ✓ |
| `"OGG 96K stream"` | 96 ✓ |
| `"Some 2k station"` | 2 — potential over-match |
| `"Radio 12kbps stream"` | 12 ✓ |
| `"Station 1024k test"` | 1024 — above _BitrateDelegate(0-9999) display clamp |
| `"FLAC 1000kbps"` | 1000 ✓ |

**Finding 1 — Low-value number over-match:** `"Some 2k station"` matches `2` (meaning 2 kbps — physically impossible for any audio stream). Values below ~8 are nonsense bitrates. The planner can optionally add a floor: `if int(match.group(1)) < 8: no match`. This is a minor polish item since the Quality column shows the full title anyway. [VERIFIED: runtime]

**Finding 2 — Bitrate > 9999 stored but display-clamped:** `_BitrateDelegate` uses `QIntValidator(0, 9999)` — values > 9999 stored at parse-time by `_add_stream_row` but clamped on next user edit. The `_on_save` path uses `int(bitrate_text or "0")` without a clamp. This is pre-existing behavior per Phase 47-03 (D-13 / IN-03). No action needed. [VERIFIED: codebase]

**Codec token priority list: `['HE-AAC', 'AAC+', 'AAC', 'OGG', 'FLAC', 'OPUS', 'MP3', 'WMA']`**

Runtime-verified [VERIFIED: runtime]:

| Title | Result |
|-------|--------|
| `"DI.fm 64kbps HE-AAC"` | HE-AAC ✓ |
| `"SomaFM 128k AAC"` | AAC ✓ |
| `"Radio Paradise 320 kbps MP3"` | MP3 ✓ |
| `"Lossless FLAC stream"` | FLAC ✓ |
| `"OGG Vorbis 96k"` | OGG ✓ |
| `"WMA 64kbps"` | WMA ✓ |
| `"OPUS 128k"` | OPUS ✓ |
| `"AAC+ 96k station"` | AAC+ ✓ |
| `"BBC Radio (no codec token)"` | None ✓ |
| `"AAC 128k MP3 320k"` | AAC ✓ (higher priority wins) |
| `"MP3 320k flac backup"` | FLAC ✓ (FLAC scanned before MP3) |

**Finding 3 — `HEAACv2` false positive:** `"HEAACv2 64k"` → matched `AAC` (via substring). `HEAACv2` contains the substring `AAC` but not `HE-AAC` (which requires the hyphen). This produces codec=`"AAC"` instead of `""` or `"HE-AAC"`. In practice, `HEAACv2` is the same codec family as HE-AAC; reporting it as `AAC` is slightly wrong but not harmful for ordering purposes. If desired, add `"HEAAC"` to the token list before `"AAC"`. D-11 does not list it as a known token, so the current behavior (showing `AAC`) is acceptable per spec. [VERIFIED: runtime — decision for planner]

**Finding 4 — `VORBIS` miss:** `"VORBIS stream 128k"` → None (OGG not matched). Internet Archive and some European stations use `VORBIS` as the format name rather than `OGG`. The planner may add `"VORBIS"` → maps to canonical `"OGG"` if desired. D-11 does not include it, so it's a quiet extension. [VERIFIED: runtime — decision for planner]

**Finding 5 — `M4A` / `ALAC` miss:** `"M4A 128k"` → None. M4A is an AAC container; reporting blank is safe. `ALAC` is Apple Lossless; not a streaming codec encountered in practice. No action needed per D-11. [VERIFIED: runtime]

**Implementation note for `_extract_codec`:** Use `title.upper()` for the scan (D-11 says case-insensitive), but match against `CODEC_TOKENS` which are already uppercase. This means `"he-aac"` in `title.upper()` is `"HE-AAC"` — matches. `"aac+"` becomes `"AAC+"` — matches. Correct. [VERIFIED: runtime]

### Q3: `xml.etree.ElementTree` XSPF Parsing and Security

**XSPF namespace parsing** [VERIFIED: runtime]:

```python
import xml.etree.ElementTree as ET
ns = "http://xspf.org/ns/0/"
root = ET.fromstring(xspf_bytes)  # bytes, not str
tracks = root.findall(f".//{{{ns}}}track")
for track in tracks:
    loc = track.find(f"{{{ns}}}location")
    title = track.find(f"{{{ns}}}title")
    url = loc.text  # direct text access
    title_str = title.text if title is not None else ""
```

This works correctly. `ET.fromstring(bytes)` handles UTF-8 encoding declaration in the XML prologue. [VERIFIED: runtime with real XSPF body]

**Security assessment** [VERIFIED: runtime — Python 3.14.4, expat 2.7.4]:

| Attack | Behavior |
|--------|----------|
| XXE via `SYSTEM` entity (`file://`, `http://`) | `ParseError: undefined entity` — **blocked** by expat's default resolver |
| Internal entity expansion (billion laughs, 3 levels) | Expands successfully, produces ~330 chars — **not blocked** |
| Internal entity expansion (5 levels, e=a^(10^4)) | Expands to 310,000 chars in <5ms — **not blocked**, but trivially small |

**Assessment:** For user-pasted URLs in their own station editor (the threat model per D-13), XXE is blocked. Billion-laughs-style internal entity expansion is NOT blocked by expat's default configuration, but the realistic risk is negligible: the user pastes their own XSPF URL; no peer/server is constructing malicious XSPF on their behalf. A billion-laughs payload large enough to cause a denial-of-service requires many more levels of nesting and would need to come from an adversarially-crafted XSPF at a URL the user deliberately pastes. The worker's exception handler catches any `MemoryError` if expansion is extreme. D-13's explicit acceptance of plain `ElementTree` is correct and well-justified. [VERIFIED: runtime]

**Plain `ET.fromstring` is acceptable** for this use case. No `defusedxml` dependency needed per D-13.

### Q4: `urllib.request.urlopen` API

**Content-Type extraction** [VERIFIED: codebase + runtime]:

```python
with urllib.request.urlopen(url, timeout=10) as resp:
    content_type = resp.headers.get("Content-Type", "")
    raw = resp.read()
```

`resp.headers` is an `http.client.HTTPMessage` instance (same API as `email.message.Message`). `resp.headers.get(name, default)` works correctly. [VERIFIED: existing codebase — `aa_import.py` uses `resp.read()` in context manager]

**Redirect behavior:** `urllib.request.urlopen` follows HTTP 3xx redirects automatically via `urllib.request.HTTPRedirectHandler` (installed by default in the opener). The final URL after redirect is accessible via `resp.geturl()` (returned by `addinfourl.geturl()`). Format detection uses `url_hint` which is the original user-supplied URL; if a redirect changes the extension (e.g., `http://example.com/playlist` → `http://cdn.example.com/playlist.pls`), the Content-Type fallback still applies. This is correct behavior per D-19 — extension-first, Content-Type second. [VERIFIED: runtime — `addinfourl.geturl` exists]

**Gzip-encoded responses:** `urllib.request.urlopen` does NOT automatically decompress gzip unless `urllib.request.Request` is used with explicit `Accept-Encoding: gzip` — which it doesn't set by default. PLS/M3U servers typically don't gzip-encode audio playlists (they're tiny text files). If encountered, the raw bytes would be gzipped binary, which the decoder would treat as a malformed text file (producing replacement chars) — the parser would return empty entries — triggering the "No entries found." error path. Acceptable per D-05. [ASSUMED — common network knowledge; not verified against live server]

**Server returning `text/plain` for PLS:** This is the D-19 edge case. Content-Type `text/plain` does NOT match any of the known format CT strings; the extension check would have already failed (e.g., URL ends in `.txt`). Result: `parse_playlist` returns `[]`, worker emits `"No entries found."` → `QMessageBox.warning`. Correct behavior per D-19. [VERIFIED: logic trace]

**socket.timeout vs TimeoutError:** Python 3.3+ maps `socket.timeout` to `TimeoutError` (same exception class). `except TimeoutError` catches both. [ASSUMED — Python 3.3+ alias; standard knowledge]

### Q5: `QMessageBox.question` with Custom Button Labels

Confirmed API in PySide6 6.11.0 [VERIFIED: runtime]:

- `QMessageBox.addButton(str, ButtonRole)` → returns `QPushButton`
- `QMessageBox.setDefaultButton(QPushButton)` → works (not just `StandardButton`)
- `QMessageBox.clickedButton()` → returns `QPushButton` (the clicked button) or `None` (if closed via X without clicking)
- `QMessageBox.DestructiveRole`, `AcceptRole`, `RejectRole` are `ButtonRole` enum members (not plain ints)

The UI-SPEC code snippet (lines 269-289) is directly implementable as written.

**`msg_box.exec()` vs `msg_box.exec_()`:** PySide6 6.x uses `exec()` (not `exec_()` which was a Python 2 compatibility shim). [VERIFIED: PySide6 6.11.0 — `QMessageBox` inherits `exec()` from `QDialog`]

### Q6: `_LogoFetchWorker` Pattern Parity

The exact points to mirror [VERIFIED: codebase]:

| Dimension | `_LogoFetchWorker` | `_PlaylistFetchWorker` |
|-----------|-------------------|----------------------|
| Constructor | `(url, token, parent=None)` | `(url, token, parent=None)` |
| `setObjectName` | `"logo-fetch-worker"` | `"playlist-fetch-worker"` |
| Signal | `finished = Signal(str, int, str)` | `finished = Signal(list, str, int)` — different payload |
| `run()` exception strategy | Broad `except Exception` → `self.finished.emit("", token, "")` | Per-type exception catch for user-readable messages, broad `except Exception` as backstop |
| Stale-token check in slot | `if token and token != self._logo_fetch_token` | `if token != self._pls_fetch_token` |
| Cursor restore | First line of `_on_logo_fetched` | First line of `_on_pls_fetched` |
| Button re-enable | Second action in slot | Second action in slot |
| Worker lifetime (`wait()`) | `_shutdown_logo_fetch_worker()` called from `accept()`, `closeEvent()`, `reject()` | `_shutdown_pls_fetch_worker()` — same three methods |
| Instance attribute | `self._logo_fetch_worker: Optional[_LogoFetchWorker] = None` | `self._pls_fetch_worker: Optional[_PlaylistFetchWorker] = None` |
| Token attribute | `self._logo_fetch_token: int = 0` | `self._pls_fetch_token: int = 0` |

**Critical deviation:** `_LogoFetchWorker` uses broad `except Exception` catching everything and emits `""` — acceptable because logo fetch failure is silent (status label). `_PlaylistFetchWorker` should use specific exception catching for user-readable error messages (`urllib.error.HTTPError`, `urllib.error.URLError`, `TimeoutError`, `UnicodeDecodeError`) plus a broad backstop. This is consistent with D-05 ("user-readable reason"). [VERIFIED: codebase + D-04/D-05]

**Worker lifetime — `wait()` is required in `accept()`:** The existing logo fetch worker crash was documented: `accept()` was missing `_shutdown_logo_fetch_worker()` and caused `QThread: Destroyed while thread is still running`. The PLS worker must not repeat this mistake. The fix was adding `self._shutdown_logo_fetch_worker()` to `accept()` (line 837). Phase 58 must add `self._shutdown_pls_fetch_worker()` to all three methods. [VERIFIED: codebase lines 831-858]

### Q7: Pluralization Helper

**No existing helper found** in the codebase [VERIFIED: grep over `musicstreamer/` and `tests/`]. No `inflect`, `ngettext`, or custom plural function exists.

**Idiomatic pattern for this codebase:** Inline ternary. The UI-SPEC (lines 266-276) already shows the exact pattern to use:

```python
stream_word = "stream" if n == 1 else "streams"
entry_word  = "entry"  if m == 1 else "entries"
```

No helper needed. Two inline ternaries in `_on_pls_fetched` covers the pluralization. [VERIFIED: codebase survey]

### Q8: Test Patterns

#### Pure parser module tests (`tests/test_playlist_parser.py`)

Model: `tests/test_aa_siblings.py` (no Qt, no fixtures, direct function calls) [VERIFIED: codebase]

```python
"""Tests for playlist_parser.parse_playlist — Phase 58."""
from musicstreamer.playlist_parser import parse_playlist

def test_parse_pls_basic():
    body = "[playlist]\nFile1=http://s.mp3\nTitle1=Test 128k MP3\n"
    result = parse_playlist(body, url_hint="http://host/playlist.pls")
    assert result == [{"url": "http://s.mp3", "title": "Test 128k MP3",
                       "bitrate_kbps": 128, "codec": "MP3"}]

def test_parse_m3u_with_extinf():
    body = "#EXTM3U\n#EXTINF:-1,Station 64k AAC\nhttp://s.aac\n"
    result = parse_playlist(body, url_hint="http://host/playlist.m3u")
    assert result[0]["bitrate_kbps"] == 64
    assert result[0]["codec"] == "AAC"

def test_parse_xspf():
    body = b'<?xml version="1.0"?><playlist xmlns="http://xspf.org/ns/0/"><trackList><track><location>http://s.mp3</location><title>96k OGG</title></track></trackList></playlist>'
    result = parse_playlist(body, url_hint="http://host/playlist.xspf")
    assert result[0]["codec"] == "OGG"

def test_unknown_format_returns_empty():
    result = parse_playlist("anything", url_hint="http://host/file.txt",
                             content_type="text/plain")
    assert result == []

def test_pls_missing_title_gives_empty_string():
    body = "[playlist]\nFile1=http://s.mp3\nFile2=http://s2.ogg\nTitle2=OGG 96k\n"
    result = parse_playlist(body, url_hint="http://host/p.pls")
    assert result[0]["title"] == ""
    assert result[1]["title"] == "OGG 96k"
```

#### Dialog tests — worker stubbing (extending `test_edit_station_dialog.py`)

Model: `test_auto_fetch_worker_starts_on_url_change` (lines 329-347) [VERIFIED: codebase]

```python
def test_add_pls_button_exists(dialog):
    assert hasattr(dialog, "add_pls_btn")

def test_add_pls_worker_starts_on_valid_url(qtbot, monkeypatch, dialog):
    import musicstreamer.ui_qt.edit_station_dialog as esd_mod
    fake_worker_instance = MagicMock()
    fake_worker_instance.isRunning.return_value = False
    fake_worker_cls = MagicMock(return_value=fake_worker_instance)
    monkeypatch.setattr(esd_mod, "_PlaylistFetchWorker", fake_worker_cls)

    monkeypatch.setattr(
        esd_mod.QInputDialog, "getText",
        lambda *a, **kw: ("http://host/playlist.pls", True)
    )
    dialog._on_add_pls()
    fake_worker_cls.assert_called_once()
    fake_worker_instance.start.assert_called_once()

def test_on_pls_fetched_restores_cursor_first(qtbot, dialog, monkeypatch):
    """Cursor must be restored unconditionally even on stale token."""
    restored = []
    monkeypatch.setattr(
        esd_mod.QApplication, "restoreOverrideCursor",
        lambda: restored.append(True)
    )
    dialog._pls_fetch_token = 5
    dialog._on_pls_fetched([], "", token=1)  # stale token
    assert len(restored) == 1  # restored even though stale

def test_on_pls_fetched_replace_clears_table(qtbot, dialog):
    dialog._add_stream_row("http://old.mp3", "Old", "MP3", 128, 1)
    entries = [{"url": "http://new.mp3", "title": "New", "bitrate_kbps": 192, "codec": "AAC"}]
    dialog._apply_pls_entries(entries, mode="replace")
    assert dialog.streams_table.rowCount() == 1
    assert dialog.streams_table.item(0, 0).text() == "http://new.mp3"

def test_on_pls_fetched_append_preserves_existing(qtbot, dialog):
    dialog._add_stream_row("http://old.mp3", "Old", "MP3", 128, 1)
    entries = [{"url": "http://new.mp3", "title": "New", "bitrate_kbps": 192, "codec": "AAC"}]
    dialog._apply_pls_entries(entries, mode="append")
    assert dialog.streams_table.rowCount() == 2
```

#### `_resolve_pls` refactor tests (extending `test_aa_import.py`)

The existing tests at lines 104-127 already test `_resolve_pls`. After the refactor, they should continue passing because the `list[str]` contract and `[pls_url]` fallback are preserved. New test to verify delegation:

```python
def test_resolve_pls_delegates_to_playlist_parser(monkeypatch):
    """After D-10 refactor, _resolve_pls delegates to parse_playlist."""
    from musicstreamer import aa_import
    from unittest.mock import patch

    mock_entries = [{"url": "http://s1.mp3", "title": "", "bitrate_kbps": 0, "codec": ""}]
    with patch("musicstreamer.aa_import.parse_playlist", return_value=mock_entries) as mock_pp:
        result = aa_import._resolve_pls("http://host/p.pls")
    assert result == ["http://s1.mp3"]
    mock_pp.assert_called_once()
```

**QThread worker integration with stubbed I/O:** The project does NOT use `qtbot.waitSignal` for QThread tests — it stubs the worker class entirely with `MagicMock` (as in `test_auto_fetch_worker_starts_on_url_change`). For testing the worker itself, instantiate it directly with a token and call `run()` with `urlopen` patched (same pattern as `test_resolve_pls` in `test_aa_import.py`). [VERIFIED: codebase]

### Q9: `aa_import._resolve_pls` Refactor Risk

**Current call sites** [VERIFIED: codebase]:

| Location | Line | Usage | Contract Required |
|----------|------|-------|-----------------|
| `fetch_channels(...)` | 135 | `urls = _resolve_pls(pls_url)` → `stream_url = urls[0] if urls else pls_url` | Must return non-empty `list[str]`; fallback `[pls_url]` on error |
| `fetch_channels_multi(...)` | 177 | `stream_urls = _resolve_pls(pls_url)` → used as list | Must return non-empty `list[str]` |

Both callers depend on `_resolve_pls` returning `list[str]` (never empty list — falls back to `[pls_url]`).

**D-10 refactor plan — preserves contract:**

```python
def _resolve_pls(pls_url: str) -> list[str]:
    """Fetch a PLS playlist; return all stream URLs in file order.

    Delegates to playlist_parser.parse_playlist (D-10, Phase 58).
    Falls back to [pls_url] if resolution fails.
    """
    from musicstreamer.playlist_parser import parse_playlist
    try:
        with urllib.request.urlopen(pls_url, timeout=10) as resp:
            content_type = resp.headers.get("Content-Type", "")
            body = resp.read().decode("utf-8", errors="replace")
        entries = parse_playlist(body, content_type=content_type, url_hint=pls_url)
        if entries:
            return [e["url"] for e in entries]
    except Exception:
        pass
    return [pls_url]  # fallback preserved for callers
```

**Risk:** The `[pls_url]` fallback-on-empty is intentionally NOT in the UI path (D-05 rejects it — GStreamer can't play `.pls`). But `aa_import._resolve_pls` callers DO need the fallback. The refactor preserves it by keeping the `if entries:` guard and the bare `except Exception` backstop. [VERIFIED: codebase D-10 + existing test at line 119-127]

**Import circularity risk:** `aa_import.py` importing from `playlist_parser.py` is a new dependency edge. `playlist_parser.py` must import only stdlib modules (`re`, `xml.etree.ElementTree`, `os`, `urllib.parse`). No circular import possible. [VERIFIED: logic trace]

---

## Common Pitfalls

### Pitfall 1: Cursor Restore After Stale-Token Check

**What goes wrong:** Moving `restoreOverrideCursor()` to after the stale-token check means a stale emission leaves the cursor stuck in WaitCursor indefinitely.
**Why it happens:** Developers naturally put the guard first for early-return clarity.
**How to avoid:** D-03/D-10 invariant is explicit — restore cursor AS THE FIRST LINE of `_on_pls_fetched`, unconditionally. This mirrors `_on_logo_fetched` at line 749.
**Warning signs:** If the cursor gets stuck after pasting a URL, the restore-first invariant was violated.

### Pitfall 2: Missing `_shutdown_pls_fetch_worker()` in `accept()`

**What goes wrong:** `QThread: Destroyed while thread '' is still running` crash when user clicks Save while a PLS fetch is in flight.
**Why it happens:** Same bug as the pre-fix `_LogoFetchWorker` path (documented in the codebase at line 833-836). `closeEvent()` is not called when the dialog is accepted via `accept()`.
**How to avoid:** Add `self._shutdown_pls_fetch_worker()` to `accept()` in addition to `closeEvent()` and `reject()`.
**Warning signs:** Crash only happens when clicking Save while fetch is in-flight — hard to reproduce manually.

### Pitfall 3: XSPF Bytes vs Str

**What goes wrong:** Passing decoded string to `ET.fromstring` when the encoding is declared in the XML prologue (`<?xml version="1.0" encoding="UTF-8"?>`) — ElementTree raises `ParseError: encoding declaration not allowed in UTF-8 document` when receiving a Unicode `str` that has an encoding declaration.
**Why it happens:** Python `str` is always Unicode; `ET.fromstring(str_body)` does not accept an encoding declaration.
**How to avoid:** Pass raw `bytes` to `ET.fromstring` for XSPF (D-17). Do NOT decode XSPF bytes through `body.decode(...)` before passing to the XML parser.
**Warning signs:** `ParseError: encoding declaration or document start not found` at parse time.

### Pitfall 4: `setRowCount(0)` Does Not Preserve Dirty Baseline

**What goes wrong:** After `Replace` clears the table with `setRowCount(0)` and inserts new rows, the dirty-state predicate should correctly show "modified" (since the new rows differ from the original baseline). This works correctly because `_capture_dirty_baseline` was captured at `_populate` time with the original rows.
**Why it's a non-issue:** The existing `_snapshot_form_state` + `_capture_dirty_baseline` mechanism captures the original DB state at `_populate` time. Clearing and re-populating the table creates a divergence that `_is_dirty()` correctly detects. No code change needed per D-07 / CONTEXT Discretion. [VERIFIED: logic trace]

### Pitfall 5: BOM in PLS Files

**What goes wrong:** Files served from some European shoutcast servers include a UTF-8 BOM (`\xef\xbb\xbf` → `﻿` after decode). `re.match(r"^File(\d+)=", line)` fails on the first line if it starts with `﻿`.
**Why it happens:** Windows tools write BOM by default; `decode("utf-8", errors="replace")` preserves it.
**How to avoid:** Strip BOM at the body level: `body = body.lstrip('﻿')` after decode. Or per-line: `line = line.strip().lstrip('﻿')`. [VERIFIED: runtime test]

### Pitfall 6: `QThread.wait()` Called Without Disconnect

**What goes wrong:** After `wait()` completes, the worker's queued `finished` signal may still be delivered to the (now-teardown) `_on_pls_fetched` slot, causing access to deleted widget attributes.
**Why it happens:** Qt delivers queued signals even after `wait()` if `disconnect()` was not called first.
**How to avoid:** The `_shutdown_pls_fetch_worker` pattern calls `worker.finished.disconnect()` before `worker.wait(2000)` (same as the logo fetch pattern at lines 825-829). [VERIFIED: codebase]

---

## Code Examples

### Minimal Working XSPF Parse

```python
# Source: runtime-verified [VERIFIED]
import xml.etree.ElementTree as ET
ns = "http://xspf.org/ns/0/"
xspf_bytes = b'''<?xml version="1.0"?><playlist xmlns="http://xspf.org/ns/0/"><trackList>
  <track><location>http://s.mp3</location><title>128k MP3</title></track>
</trackList></playlist>'''
root = ET.fromstring(xspf_bytes)
for track in root.findall(f".//{{{ns}}}track"):
    loc = track.find(f"{{{ns}}}location")
    title = track.find(f"{{{ns}}}title")
    print(loc.text, title.text if title is not None else "")
# Output: http://s.mp3  128k MP3
```

### Worker Stale-Token Pattern

```python
# Source: edit_station_dialog.py:682-692 + 749-754 [VERIFIED]
# Start:
self._pls_fetch_token += 1
token = self._pls_fetch_token
self.add_pls_btn.setEnabled(False)
self._pls_fetch_worker = _PlaylistFetchWorker(url.strip(), token, self)
self._pls_fetch_worker.finished.connect(self._on_pls_fetched)
QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
self._pls_fetch_worker.start()

# Slot:
def _on_pls_fetched(self, entries: list, error_message: str, token: int) -> None:
    QApplication.restoreOverrideCursor()   # FIRST, unconditionally
    self.add_pls_btn.setEnabled(True)
    if token != self._pls_fetch_token:
        return
    # ... dispatch on success/failure
```

### `_add_stream_row` Call for Resolved Entries

```python
# Source: edit_station_dialog.py:603-626 + D-14/D-16 [VERIFIED]
for i, entry in enumerate(entries):
    self._add_stream_row(
        url=entry["url"],
        quality=entry["title"],       # full title → Quality column (D-14)
        codec=entry["codec"],          # recognized token or "" (D-15)
        bitrate_kbps=entry["bitrate_kbps"],  # int or 0 (D-16 renders as "")
        position=start_position + i,
        stream_id=None,                # new row; persistence via _on_save
    )
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `aa_import._resolve_pls` owns all PLS parsing | `playlist_parser.parse_playlist` is the canonical parser; `_resolve_pls` is a thin wrapper | Phase 58 | `_resolve_pls` callers unchanged; new `EditStationDialog` path gets multi-format support |
| Single PLS format only (AA import path) | PLS + M3U + M3U8 + XSPF dispatched by extension / Content-Type | Phase 58 (D-18: quiet internal extension) | No user-visible change to button label or requirement; broader real-world compatibility |
| `exec_()` for modal dialogs | `exec()` | PySide6 6.x | `exec_()` was Python 2 compat shim; `exec()` is the standard name [VERIFIED: runtime] |

**Deprecated/outdated:**
- `exec_()`: PySide6 6.x removed this; use `exec()`. The existing codebase already uses `exec()` throughout.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `parse_playlist` accepts `bytes \| str` or the planner splits bytes/str path at the worker level for XSPF | Pattern 5 / Q1 XSPF section | If signature is `str`-only, XSPF with encoding declaration raises `ParseError`. Fix: pass `bytes` for XSPF, `str` for others — planner must choose the signature boundary |
| A2 | Low-value bitrate matches (e.g. "2k" in title) are acceptable without a floor guard | Q2 Finding 1 | If not addressed: "some 2k station" stores bitrate=2. Impact: `order_streams` sorts it last (low bitrate) — functional but slightly misleading display |
| A3 | gzip-encoded PLS responses cause parse failure (empty entries → warning) | Q4 Gzip section | If servers actually gzip-encode playlist responses, users see "No entries found." error. Fix: add gzip decompression in worker. Frequency: very low in practice |
| A4 | `socket.timeout` is an alias of `TimeoutError` in Python 3.10+ | Q4 Timeout section | If not alias, `socket.timeout` from `urlopen` slips past `except TimeoutError`. Fix: also catch `socket.timeout` explicitly |
| A5 | Multiple `<location>` elements per XSPF track — first element taken | Q1 XSPF edge cases | XSPF spec allows alternates; `track.find()` returns first — correct behavior per spec |
| A6 | `HEAACv2` in title produces codec=`"AAC"` (not blank); acceptable per D-11 | Q2 Finding 3 | Slightly wrong codec label but same ordering behavior as `AAC`. No functional impact |

**Confirmed by verification:** All critical API calls (QMessageBox roles, setDefaultButton, addButton → QPushButton, clickedButton, ET.fromstring with namespace, `wait(2000)`, `disconnect()` before wait) were verified at runtime.

---

## Open Questions

1. **`parse_playlist` bytes-vs-str signature**
   - What we know: XSPF requires bytes for `ET.fromstring`; PLS/M3U/M3U8 work fine as `str`
   - What's unclear: Should `parse_playlist(body: str | bytes, ...)` handle both, or should the worker pass bytes for XSPF via a separate parameter?
   - Recommendation: Simplest solution — accept `bytes | str` in `parse_playlist` and call `ET.fromstring(body if isinstance(body, bytes) else body.encode("utf-8"))` in `_parse_xspf`. Alternatively, the worker detects XSPF before decode and passes `raw_bytes` to a separate call. Planner's call.

2. **`socket.timeout` vs `TimeoutError` in worker**
   - What we know: Python 3.3+ maps `socket.timeout` → `TimeoutError`; Python 3.10+ confirms this
   - What's unclear: Whether `urllib.request.urlopen` raises `socket.timeout` or `TimeoutError` or `urllib.error.URLError(socket.timeout)`
   - Recommendation: Catch both `TimeoutError` and `socket.timeout` in the worker's exception chain, or handle via `urllib.error.URLError` which wraps socket errors

3. **Floor guard for low-value bitrate matches**
   - What we know: Regex matches "2k" in "some 2k station" → bitrate=2
   - What's unclear: Real-world frequency of station titles with `\d+k` where \d+ < 8
   - Recommendation: Add `if int(m.group(1)) < 8: bitrate = 0` in `_extract_bitrate`. Low-risk, clean implementation.

---

## Environment Availability

*Step 2.6: SKIPPED (Phase 58 is pure code changes — `urllib.request` and `xml.etree.ElementTree` are Python stdlib, already available. PySide6 6.11.0 is already installed. No external tools, services, databases, or CLIs required beyond what's already in the project.)*

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9+ with pytest-qt 4+ |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_playlist_parser.py tests/test_aa_import.py -x` |
| Full suite command | `pytest tests -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STR-15 | PLS URL parses to N stream entries | unit | `pytest tests/test_playlist_parser.py -x` | ❌ Wave 0 |
| STR-15 | M3U URL parses to N stream entries | unit | `pytest tests/test_playlist_parser.py::test_parse_m3u* -x` | ❌ Wave 0 |
| STR-15 | XSPF URL parses to N stream entries | unit | `pytest tests/test_playlist_parser.py::test_parse_xspf* -x` | ❌ Wave 0 |
| STR-15 | Worker emits entries on success | unit | `pytest tests/test_edit_station_dialog.py -k pls -x` | ❌ Wave 0 (extend) |
| STR-15 | Worker emits error_message on HTTP failure | unit | `pytest tests/test_edit_station_dialog.py -k pls_fail -x` | ❌ Wave 0 |
| STR-15 | Cursor restored unconditionally in slot | unit | `pytest tests/test_edit_station_dialog.py -k cursor -x` | ❌ Wave 0 |
| STR-15 | Replace clears table; Append preserves rows | unit | `pytest tests/test_edit_station_dialog.py -k apply_pls -x` | ❌ Wave 0 |
| STR-15 | Append positions start from max+1 | unit | `pytest tests/test_edit_station_dialog.py -k append_position -x` | ❌ Wave 0 |
| STR-15 | Replace-then-save prunes orphaned DB rows | unit | `pytest tests/test_edit_station_dialog.py -k replace_save -x` | ❌ Wave 0 |
| STR-15 | `_resolve_pls` still returns `[pls_url]` on failure | unit | `pytest tests/test_aa_import.py::test_resolve_pls_fallback_on_error -x` | ✅ existing |
| STR-15 | `_resolve_pls` delegates to `parse_playlist` | unit | `pytest tests/test_aa_import.py::test_resolve_pls_delegates -x` | ❌ Wave 0 |
| STR-15 | Dirty state triggered by resolved rows | unit | `pytest tests/test_edit_station_dialog.py -k dirty_after_pls -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_playlist_parser.py tests/test_aa_import.py -x`
- **Per wave merge:** `pytest tests -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_playlist_parser.py` — covers STR-15 parser unit tests (PLS/M3U/M3U8/XSPF, edge cases, bitrate regex, codec token scan)
- [ ] `tests/test_edit_station_dialog.py` — extend with PLS button tests, worker pattern tests, Replace/Append/Cancel branching, cursor lifecycle, position assignment, dirty-state

*(No new conftest.py entries needed — existing `QT_QPA_PLATFORM=offscreen` and `_stub_bus_bridge` autouse fixtures cover all new tests)*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | URL from `QInputDialog.getText` stripped of whitespace; playlist body decoded with `errors="replace"`; bitrate clamped by `QIntValidator(0,9999)` at edit time |
| V6 Cryptography | no | — |
| V7 Error/Exception Handling | yes | Worker catches all exceptions and converts to user-readable `error_message`; broad `except Exception` backstop per codebase convention |
| V14 XML Processing | yes (XSPF path) | `xml.etree.ElementTree` — XXE blocked by default (expat); billion-laughs accepted per D-13 threat model (user-pasted URL) |

### Known Threat Patterns for Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| XXE in XSPF body | Information Disclosure | `ET.fromstring` default expat — SYSTEM entities rejected (verified) |
| Billion-laughs in XSPF body | Denial of Service | Accepted per D-13; user-pasted URL threat model; worker exception handler as backstop |
| Malicious URL → SSRF | Elevation of Privilege | `urllib.request.urlopen` follows redirects; user provides URL deliberately; same risk as existing logo fetch (`_LogoFetchWorker`) — no mitigation added |
| HTML injection in title text → Qt widget | Spoofing | `_add_stream_row` sets `QTableWidgetItem(title)` — Qt displays as plain text by default in table cells; not rendered as rich text |

---

## Sources

### Primary (HIGH confidence)
- `musicstreamer/ui_qt/edit_station_dialog.py` — `_LogoFetchWorker` pattern (lines 54-122, 682-858), `_add_stream_row` (603-626), `_on_save` (864-946), stale-token check (754), worker wait pattern (814-829)
- `musicstreamer/aa_import.py` — `_resolve_pls` (23-46), call sites at lines 135 and 177
- `musicstreamer/stream_ordering.py` — `codec_rank` None-safety, `order_streams` Phase 47 invariants
- `musicstreamer/repo.py` — `insert_stream`, `update_stream`, `reorder_streams` signatures (lines 185-211)
- `tests/test_edit_station_dialog.py` — worker stub test pattern (329-347), cursor test pattern (388-408)
- `tests/test_aa_import.py` — `_resolve_pls` test pattern (104-127), `urlopen` mock factory (19-24)
- `tests/test_aa_siblings.py` — pure module test pattern (no Qt, no fixtures)
- PySide6 6.11.0 runtime verification — `QMessageBox.addButton`, `setDefaultButton(QPushButton)`, `clickedButton`, `ButtonRole` enum members
- Python 3.14.4 / expat 2.7.4 runtime verification — `ET.fromstring(bytes)` namespace parsing, XXE behavior, entity expansion
- `pyproject.toml` — confirmed no new dependencies needed; pytest configuration
- `.planning/phases/58-pls-auto-resolve-in-station-editor/58-CONTEXT.md` — all D-01..D-19 locked decisions
- `.planning/phases/58-pls-auto-resolve-in-station-editor/58-UI-SPEC.md` — exact copy strings, interaction contract

### Secondary (MEDIUM confidence)
- Python docs (`urllib.response.addinfourl`) — `geturl()` method for final URL after redirect
- Codebase grep survey — confirmed no existing pluralization helper

### Tertiary (LOW confidence)
- Gzip-encoded PLS responses: common network knowledge; not verified against live server [A3]
- `socket.timeout` as `TimeoutError` alias in Python 3.10+: standard Python knowledge [A4]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all APIs runtime-verified on PySide6 6.11.0 / Python 3.14.4
- Architecture: HIGH — fully derived from locked D-01..D-19 decisions + existing codebase patterns
- Pitfalls: HIGH — all critical pitfalls either verified from existing crash evidence in codebase or runtime-tested
- Parser pseudocode: HIGH for PLS/M3U/XSPF (runtime-verified); MEDIUM for edge cases (tested common cases, A-tagged assumptions for uncommon)

**Research date:** 2026-05-01
**Valid until:** 2026-06-01 (stable codebase; PySide6 6.11 API stable)
