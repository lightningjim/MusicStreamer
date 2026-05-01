---
phase: 58
slug: pls-auto-resolve-in-station-editor
status: draft
shadcn_initialized: false
preset: none
created: 2026-05-01
---

# Phase 58 — UI Design Contract

> Small UI delta on an existing modal QDialog. The contract is: **one new QPushButton added to an existing toolbar row + three standard Qt modals (QInputDialog, QMessageBox.question, QMessageBox.warning) + one background QThread worker**. No new layout, no new icons, no new top-level surface. Every visual dimension reduces to "no change — reuse existing `_theme.py` tokens and platform palette." The substantive design dimension is the **interaction / state contract** on the button press → fetch → confirm/warn → insert event boundary.
>
> All D-01..D-19 decisions are locked in 58-CONTEXT.md. This UI-SPEC fills in exact copy strings, the precise disabled/restored lifecycle, pluralization rules, and the visual placement within the existing button row — the details downstream agents need so they never re-design at implementation time.

---

## Phase Classification

**Type:** Feature add (one new button + three modal dialogs) on an existing dialog surface.
**New visual chrome:** ONE `QPushButton("Add from PLS…")` inserted after "Move Down" in `EditStationDialog`'s streams-section button row.
**New components:** `_PlaylistFetchWorker(QThread)` (non-visual, placed next to `_LogoFetchWorker`). Three standard Qt modal dialogs: `QInputDialog.getText`, `QMessageBox.question`, `QMessageBox.warning` — all system-rendered, no custom styling.
**New copy:** Button label, button tooltip, `QInputDialog` title + prompt label, `QMessageBox.question` title + body + button labels, `QMessageBox.warning` title + body template.
**Visual diff vs. Phase 55/64 ship:** The only pixel-level change at steady state is the addition of one button in the streams toolbar row. At rest the rest of the dialog is pixel-identical to the current Phase 64 ship.

CONTEXT.md (D-01..D-19) fully locks all implementation choices. This UI-SPEC pre-populates all contract fields from CONTEXT.md; no user questions were needed or asked.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none (Qt6 / PySide6 — desktop app, not web; shadcn N/A) |
| Preset | not applicable |
| Component library | PySide6 native widgets — `QPushButton`, `QInputDialog`, `QMessageBox` for this phase |
| Icon library | n/a — this phase adds no icon |
| Font | Qt platform default (same no-`setFont` policy used throughout `EditStationDialog`) |
| Theme tokens module | `musicstreamer/ui_qt/_theme.py` — `ERROR_COLOR_HEX` (`#c0392b`), `ERROR_COLOR_QCOLOR`, `STATION_ICON_SIZE`. **Phase 58 reads zero theme tokens directly.** The new button inherits the platform button palette; no QSS override is applied to it. |
| Style direction | Qt-native flat — no global QSS override. The new button inherits `palette(button)` / Fusion dark defaults, identical to all four existing stream-toolbar buttons. |

**No design-system migration in this phase.** All tokens, palette references, and fonts are inherited from prior phases unchanged.

---

## Spacing Scale

**No new spacing values.** The new button is inserted into the existing `btn_row` `QHBoxLayout` at `edit_station_dialog.py:362-372` which already declares `setSpacing(4)` and `setContentsMargins(0, 0, 0, 0)`. Inserting a fifth widget into that layout yields an automatic 4px horizontal gap to the left (from "Move Down") — **no `setContentsMargins` or per-widget spacing override is added**.

| Token | Value | Existing usage (unchanged) | Phase 58 use |
|-------|-------|----------------------------|--------------|
| xs | 4px | `btn_row.setSpacing(4)` (`edit_station_dialog.py:363`) | Implicit gap between "Move Down" and the new "Add from PLS…" button |
| sm | 8px | `streams_vbox.setSpacing(4)` (table-to-button-row gap) | Inherited; no change |
| md | 16px | Form label padding, outer dialog margins | Inherited; no change |

Larger tokens (`lg`/`xl`/`2xl`/`3xl`) are not introduced by this phase.

Exceptions: none. Phase 58 changes zero spacing values.

---

## Typography

**No new typography roles.** The new button uses the Qt platform default font (no `setFont` call), identical to the four existing stream-toolbar buttons (`add_stream_btn`, `remove_stream_btn`, `move_up_btn`, `move_down_btn`). All Qt modal dialogs (`QInputDialog`, `QMessageBox`) use Qt's own system font rendering.

| Role | Size | Weight | Line Height | Source — unchanged |
|------|------|--------|-------------|--------------------|
| Button label text (all stream-toolbar buttons) | Qt platform default (~10pt on Linux X11 DPR=1.0) | Normal (400) | platform default | Qt `QPushButton` default — no `setFont` |
| Dialog body text (QInputDialog / QMessageBox) | Qt platform default | Normal (400) | platform default | Rendered by Qt's QDialog chrome — no project override |

**Font count:** No new font roles. 2 weights in use project-wide (Normal + DemiBold for ICY title) — unchanged by this phase.

---

## Color

**No new color usage.** The new button inherits `palette(button)` for background and `palette(buttonText)` for text — identical to all four existing stream-toolbar buttons. The three modal dialogs are system-rendered.

| Role | Value | Phase 58 use |
|------|-------|--------------|
| Dominant (60%) | `palette(window)` (Fusion `#353535` on dark) | Dialog background — inherited unchanged |
| Secondary (30%) | `palette(base)` / `palette(button)` | New button background via `palette(button)` — inherited unchanged |
| Accent (10%) | `palette(highlight)` (`#2A82DA` on Fusion dark) | **NOT used by the new button** — stream-toolbar buttons are never accent-colored |
| Destructive | `ERROR_COLOR_HEX = "#c0392b"` (`_theme.py:32`) | NOT used by the new button (it is an additive action, not destructive). The `QMessageBox.warning` icon is system-rendered. |

**Accent reserved for** (unchanged from prior phases): selected station row highlight, volume slider groove fill, play/pause button pressed state, keyboard focus ring. Phase 58 introduces zero new accent usage.

**Disabled state:** When the fetch worker is running, `self.add_pls_btn.setEnabled(False)` causes Qt to render the button text at reduced opacity using `palette(disabled)` — standard Qt behavior, no custom QSS needed.

---

## Component Inventory

| Component | Status | Source-of-truth file:line |
|-----------|--------|---------------------------|
| `add_pls_btn` (`QPushButton("Add from PLS…")`) | **NEW** | (new in `musicstreamer/ui_qt/edit_station_dialog.py`, inserted after `move_down_btn` in `btn_row`) |
| `_PlaylistFetchWorker(QThread)` | **NEW — non-visual** | (new in `edit_station_dialog.py`, placed immediately after `_LogoFetchWorker` class at `~line 125`) |
| `_pls_fetch_token: int` | **NEW — non-visual** | (new instance attribute in `EditStationDialog.__init__`, placed alongside `_logo_fetch_token`) |
| `_on_add_pls(self) -> None` | **NEW — non-visual** | (new method on `EditStationDialog`) |
| `_on_pls_fetched(self, entries, error_message, token) -> None` | **NEW — non-visual** | (new slot on `EditStationDialog`) |
| `_apply_pls_entries(self, entries, mode) -> None` | **NEW — non-visual** | (new method on `EditStationDialog`) |
| `playlist_parser.parse_playlist(body, content_type, url_hint)` | **NEW — non-visual, separate module** | `musicstreamer/playlist_parser.py` |
| `add_stream_btn` (`QPushButton("Add")`) | Existing — position 1 in btn_row | `edit_station_dialog.py:365` (unchanged) |
| `remove_stream_btn` (`QPushButton("Remove")`) | Existing — position 2 in btn_row | `edit_station_dialog.py:366` (unchanged) |
| `move_up_btn` (`QPushButton("Move Up")`) | Existing — position 3 in btn_row | `edit_station_dialog.py:367` (unchanged) |
| `move_down_btn` (`QPushButton("Move Down")`) | Existing — position 4 in btn_row | `edit_station_dialog.py:368` (unchanged) |
| `streams_table` (`QTableWidget`, 5 columns) | Existing — unchanged | `edit_station_dialog.py:335` |
| `_add_stream_row(url, quality, codec, bitrate_kbps, position, stream_id)` | Existing — called by `_apply_pls_entries` with `stream_id=None` | `edit_station_dialog.py:603` |
| `_LogoFetchWorker(QThread)` | Existing — shape model for new worker | `edit_station_dialog.py:54` |

### New Button Configuration (locked, mirrors existing btn_row convention)

The exact construction and connection — mirrors the four existing buttons exactly:

```python
self.add_pls_btn = QPushButton("Add from PLS…")
self.add_pls_btn.setToolTip(
    "Paste a playlist URL (PLS / M3U / M3U8 / XSPF) and import each stream entry as a row."
)
btn_row.addWidget(self.add_pls_btn)
# (addStretch() moved to after the new button)
```

Connection (bound-method per QA-05, placed after the four existing connections at `edit_station_dialog.py:376-379`):
```python
self.add_pls_btn.clicked.connect(self._on_add_pls)
```

**Button order in `btn_row`:** Add | Remove | Move Up | Move Down | Add from PLS… | [stretch]

---

## Interaction Contract

This is the only dimension with substantive Phase 58 content. One event boundary with four outcome branches.

### The Event Boundary — "Add from PLS…" button press → fetch → insert

**Precondition:** `EditStationDialog` is open. User has not started a PLS fetch (or a prior fetch has fully completed and re-enabled the button).

**Trigger:** User clicks `self.add_pls_btn`.

---

### Step 1 — URL Input (`QInputDialog.getText`)

**Exact call:**
```python
url, ok = QInputDialog.getText(
    self,
    "Add from PLS",
    "Playlist URL:",
    QLineEdit.Normal,
    "",
)
```

| Parameter | Value | Source |
|-----------|-------|--------|
| Parent | `self` (`EditStationDialog` instance) | D-02 |
| Window title | `"Add from PLS"` | D-02 |
| Prompt label | `"Playlist URL:"` | D-02 |
| Echo mode | `QLineEdit.Normal` | D-02 |
| Initial text | `""` (empty) | D-02 |

**Cancel / empty contract:** `if not ok or not url.strip(): return` — absolute no-op. No cursor change, no button disable, no error message. (Source: D-02)

**On a non-empty URL:** proceed to Step 2.

---

### Step 2 — Start Fetch (wait cursor + button disable)

**Exact sequence** (mirrors `_on_url_timer_timeout` at `edit_station_dialog.py:682-692`):

```python
self._pls_fetch_token += 1
token = self._pls_fetch_token
self.add_pls_btn.setEnabled(False)
self._pls_fetch_worker = _PlaylistFetchWorker(url.strip(), token, self)
self._pls_fetch_worker.finished.connect(self._on_pls_fetched)
QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
self._pls_fetch_worker.start()
```

**During fetch:**
- `self.add_pls_btn` is disabled (greyed out via `palette(disabled)` — no custom QSS).
- Wait cursor applied application-wide (`QApplication.setOverrideCursor`).
- No new status label is shown in the dialog. No progress indicator. No animation.
- All other dialog controls (the four existing stream buttons, Save, Discard, Delete, URL field, etc.) remain in their current enabled/disabled states — untouched by the fetch.

**Stale-token contract:** If the user somehow fires a second `_on_add_pls` before the first fetch completes (not possible since the button is disabled, but guard for defense-in-depth), `_on_pls_fetched` discards any emission whose `token != self._pls_fetch_token`. Matches `_logo_fetch_token` precedent at `edit_station_dialog.py:754`.

---

### Step 3 — Fetch Result: `_on_pls_fetched` slot

**FIRST action in the slot, unconditionally** (D-03 / D-10 invariant):
```python
QApplication.restoreOverrideCursor()
self.add_pls_btn.setEnabled(True)
```

This runs BEFORE the stale-token check, BEFORE the error check, and BEFORE any `QMessageBox`. Reason: every `setOverrideCursor` must have exactly one matching `restoreOverrideCursor`, regardless of outcome. (Same invariant as `_on_logo_fetched` at `edit_station_dialog.py:749`.)

**Then stale-token check:**
```python
if token != self._pls_fetch_token:
    return  # discard stale emission; cursor already restored
```

**Then dispatch on outcome** — four branches:

#### Branch A — Failure (`error_message != ""`)

Show `QMessageBox.warning`:

```python
QMessageBox.warning(
    self,
    "PLS resolution failed",
    f"Could not resolve playlist:\n{error_message}",
)
```

| Parameter | Value | Source |
|-----------|-------|--------|
| Parent | `self` | D-05 |
| Window title | `"PLS resolution failed"` | D-05 |
| Message body | `f"Could not resolve playlist:\n{error_message}"` | D-05 |

Where `error_message` is a short, user-readable reason string emitted by `_PlaylistFetchWorker.run()`. Examples of user-readable reasons (executor responsibility, not locked here beyond the template): `"HTTP 404: Not Found"`, `"Timed out after 10 seconds"`, `"No stream entries found in playlist"`, `"Unrecognized playlist format"`. The template is `"Could not resolve playlist:\n{reason}"` — the `\n` separates the fixed preamble from the dynamic reason on a second line.

**Streams table: unchanged.** No rows added, no rows removed.

#### Branch B — Empty entries (`error_message == ""` but `entries == []`)

This case should not normally occur (the worker treats an empty parse as `error_message = "No entries found."`) but is included for safety.

Show the same `QMessageBox.warning` with `error_message` set to `"No entries found."`:
```python
QMessageBox.warning(
    self,
    "PLS resolution failed",
    "Could not resolve playlist:\nNo entries found.",
)
```

**Streams table: unchanged.**

#### Branch C — Success, table is empty (`entries` non-empty, `self.streams_table.rowCount() == 0`)

Skip the Replace/Append/Cancel prompt. Call directly:
```python
self._apply_pls_entries(entries, mode="append")
```

No `QMessageBox.question`, no confirm. Silent append. (Source: D-06 "Empty table → skip the prompt and append silently.")

#### Branch D — Success, table has existing rows (`entries` non-empty, `self.streams_table.rowCount() > 0`)

Show `QMessageBox.question` with three custom buttons:

```python
n = self.streams_table.rowCount()
m = len(entries)
stream_word = "stream" if n == 1 else "streams"

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
msg_box.setDefaultButton(append_btn)  # Enter accepts non-destructive Append
msg_box.exec()

clicked = msg_box.clickedButton()
if clicked is replace_btn:
    self._apply_pls_entries(entries, mode="replace")
elif clicked is append_btn:
    self._apply_pls_entries(entries, mode="append")
# else: Cancel — no-op
```

**Exact copy contract:**

| Element | Exact string | Source |
|---------|-------------|--------|
| Window title | `"Import Playlist Streams"` | Inferred default (CONTEXT D-06 locks the shape; window title not locked in CONTEXT, defaulting to a descriptive title matching the operation) |
| Body paragraph 1 | `"This station has {N} existing stream."` (N=1) or `"This station has {N} existing streams."` (N>1) | D-06 |
| Body paragraph separator | blank line (`\n\n`) | D-06 |
| Body paragraph 2 | `"Replace them with the {M} resolved entry, or append the new entry after the existing ones?"` (M=1) or `"Replace them with the {M} resolved entries, or append the new entries after the existing ones?"` (M>1) | D-06 |
| Replace button label | `"Replace"` | D-06 |
| Append button label | `"Append"` | D-06 |
| Cancel button label | `"Cancel"` | D-06 |
| Default button | `"Append"` (Enter accepts) | D-06 |
| Replace button role | `QMessageBox.DestructiveRole` | Inferred default (Replace is destructive — removes existing rows) |
| Append button role | `QMessageBox.AcceptRole` | Inferred default (non-destructive, default action) |
| Cancel button role | `QMessageBox.RejectRole` | Inferred default |

**On Cancel:** no-op. Streams table unchanged. Cursor already restored (Step 3, first action). Button already re-enabled.

---

### Step 4 — `_apply_pls_entries(entries, mode)`

**Replace path** (`mode == "replace"`):
```python
self.streams_table.setRowCount(0)  # UI-only clear; no repo.delete_stream call
```
Then fall through to append-insert logic with `start_position = 1`.

**Append path** (`mode == "append"`):
Compute starting position:
```python
max_pos = 0
for row in range(self.streams_table.rowCount()):
    item = self.streams_table.item(row, _COL_POSITION)
    try:
        max_pos = max(max_pos, int(item.text()))
    except (TypeError, ValueError, AttributeError):
        pass
start_position = max_pos + 1
```

**Insert rows** (one per resolved entry, in playlist file-order):
```python
for i, entry in enumerate(entries):
    self._add_stream_row(
        url=entry["url"],
        quality=entry["title"],     # full Title text → Quality column (D-14)
        codec=entry["codec"],        # recognized token or "" (D-11/D-15)
        bitrate_kbps=entry["bitrate_kbps"],  # int or 0 (D-11/D-16)
        position=start_position + i,
        stream_id=None,              # new row, persisted on Save
    )
```

**Column mapping** (locked, matches D-11/D-12/D-13/D-14):

| Column | Source | Renders as |
|--------|--------|------------|
| URL (`_COL_URL = 0`) | `entry["url"]` — `FileN=` value stripped | URL string |
| Quality (`_COL_QUALITY = 1`) | `entry["title"]` — full `TitleN=` / `#EXTINF` display name / XSPF `<title>` | Human-readable string; may be blank |
| Codec (`_COL_CODEC = 2`) | `entry["codec"]` — recognized token (HE-AAC, AAC+, AAC, OGG, FLAC, OPUS, MP3, WMA) or `""` | Codec string or blank cell |
| Bitrate (`_COL_BITRATE = 3`) | `entry["bitrate_kbps"]` — int or 0 | `str(n)` or `""` when 0 (existing `_add_stream_row` convention) |
| Position (`_COL_POSITION = 4`) | `start_position + i` | Integer string |

**Dirty-state:** `_add_stream_row` calls feed into the existing `_capture_dirty_baseline` / `_is_dirty` snapshot mechanism. No code change needed; the resolved rows trip dirty correctly, and `Save | Discard | Cancel` continues to work. (Source: D-07 / CONTEXT §Claude's Discretion.)

---

### Keyboard shortcut on the new button

**None.** No `setShortcut` call. Tab cycles through the stream toolbar buttons in standard Qt order: Add → Remove → Move Up → Move Down → Add from PLS… → [stretch omitted from tab order]. (Source: CONTEXT §additional_context — "default: none — Tab cycles in standard order".)

---

### Interaction summary table

| User action | Outcome | Table state | Cursor |
|-------------|---------|-------------|--------|
| Click "Add from PLS…" → Cancel in QInputDialog | No-op | Unchanged | No change |
| Click "Add from PLS…" → empty URL → OK in QInputDialog | No-op | Unchanged | No change |
| Click "Add from PLS…" → valid URL → fetch fails | `QMessageBox.warning` shown | Unchanged | Restored before warning |
| Click "Add from PLS…" → valid URL → fetch succeeds → table empty | Silent append | N new rows added | Restored before append |
| Click "Add from PLS…" → valid URL → fetch succeeds → table non-empty → Replace | `QMessageBox.question` → Replace: clears table, inserts M rows at positions 1..M | Old rows removed, M new rows | Restored before question |
| Click "Add from PLS…" → valid URL → fetch succeeds → table non-empty → Append | `QMessageBox.question` → Append: inserts M rows after existing rows | Existing rows preserved, M new rows appended | Restored before question |
| Click "Add from PLS…" → valid URL → fetch succeeds → table non-empty → Cancel | `QMessageBox.question` → Cancel: no-op | Unchanged | Restored before question |

---

## Copywriting Contract

All strings are locked for the executor. No user questions were needed; CONTEXT.md D-01..D-06 provided all material.

| Element | Exact copy | Source |
|---------|-----------|--------|
| Button label | `"Add from PLS…"` (U+2026 HORIZONTAL ELLIPSIS — not three dots `...`) | D-01 / CONTEXT |
| Button tooltip | `"Paste a playlist URL (PLS / M3U / M3U8 / XSPF) and import each stream entry as a row."` | D-01 / CONTEXT |
| QInputDialog window title | `"Add from PLS"` | D-02 / CONTEXT |
| QInputDialog prompt label | `"Playlist URL:"` | D-02 / CONTEXT |
| QInputDialog initial value | `""` (empty string) | D-02 / CONTEXT |
| QMessageBox.question window title | `"Import Playlist Streams"` | Inferred default |
| QMessageBox.question body — N=1 streams, M=1 entry | `"This station has 1 existing stream.\n\nReplace them with the 1 resolved entry, or append the new entry after the existing ones?"` | D-06 / CONTEXT (pluralization applied) |
| QMessageBox.question body — N>1 streams, M>1 entries | `"This station has {N} existing streams.\n\nReplace them with the {M} resolved entries, or append the new entries after the existing ones?"` | D-06 / CONTEXT |
| QMessageBox.question body — N=1, M>1 | `"This station has 1 existing stream.\n\nReplace them with the {M} resolved entries, or append the new entries after the existing ones?"` | D-06 / CONTEXT (pluralization applied) |
| QMessageBox.question body — N>1, M=1 | `"This station has {N} existing streams.\n\nReplace them with the 1 resolved entry, or append the new entry after the existing ones?"` | D-06 / CONTEXT (pluralization applied) |
| Replace button label | `"Replace"` | D-06 / CONTEXT |
| Append button label | `"Append"` | D-06 / CONTEXT |
| Cancel button label | `"Cancel"` | D-06 / CONTEXT |
| Default button | `"Append"` | D-06 / CONTEXT |
| QMessageBox.warning window title | `"PLS resolution failed"` | D-05 / CONTEXT |
| QMessageBox.warning body template | `"Could not resolve playlist:\n{reason}"` | D-05 / CONTEXT |
| QMessageBox.warning reason — no entries parsed | `"No entries found."` | D-05 (inferred from "No entries found." wording) |
| Primary CTA (button itself, at rest) | `"Add from PLS…"` | D-01 |
| Empty state (streams table empty, no PLS imported yet) | n/a — table is already empty; no placeholder row or text shown. Existing behavior unchanged. | Existing |
| Error state | `QMessageBox.warning` as above — modal dismiss clears the state | D-05 |
| Destructive confirmation (Replace action) | Window: `"Import Playlist Streams"` / Body: per pluralization table above / Replace button (DestructiveRole) is the destructive option / Default is Append (non-destructive) | D-06 |

**Pluralization rules (locked):**

| Variable | Singular | Plural |
|----------|----------|--------|
| N (existing rows) | `"1 existing stream"` | `"{N} existing streams"` |
| M (resolved entries) | `"1 resolved entry"` | `"{M} resolved entries"` |
| M (in append clause) | `"the new entry"` | `"the new entries"` |

---

## States and Transitions

No new persistent states. The dialog has two transient states while a PLS fetch is in flight:

| State | Button | Cursor | Trigger in | Trigger out |
|-------|--------|--------|------------|-------------|
| **Idle** (default) | `add_pls_btn` enabled | System cursor | App start / fetch complete | User clicks "Add from PLS…" |
| **Fetching** | `add_pls_btn` disabled | `Qt.WaitCursor` | `_on_add_pls` after worker start | `_on_pls_fetched` first two lines |

**No new status label.** The wait cursor + disabled button is the sole progress affordance. (Source: D-03 / CONTEXT)

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| n/a | none — desktop Qt/PySide6 application; no shadcn, no third-party UI registry, no new dependency | not applicable |

Phase 58 introduces zero new packages. `urllib.request` and `xml.etree.ElementTree` are Python stdlib. STACK.md confirms `PySide6>=6.11` and `pytest-qt>=4` are already locked; no `pyproject.toml` edits required.

---

## Acceptance & Dimension Mapping

| Dimension | Verdict | Evidence |
|-----------|---------|----------|
| Visual fidelity | **PASS** | One new `QPushButton` with no custom styling; visual format inherits Fusion button palette identical to all four existing stream-toolbar buttons. |
| Layout | **PASS** | Button inserted into existing `btn_row` `QHBoxLayout` after "Move Down"; inherits `setSpacing(4)` and `setContentsMargins(0, 0, 0, 0)`. No new layout. |
| Typography | **PASS** | Default Qt platform font (no `setFont`) — parity with all four existing stream-toolbar buttons. |
| Color | **PASS** | Inherits `palette(button)` / `palette(buttonText)`. No theme-token read, no QSS override, no new accent usage. |
| Spacing | **PASS** | Zero new spacing values — pure inheritance from existing `btn_row.setSpacing(4)`. |
| Interaction / state | **The substance of this phase** — see §Interaction Contract. Four outcome branches fully specified with exact Qt call signatures, exact copy strings, cursor lifecycle, and pluralization rules. |
| Registry Safety | **n/a** | No third-party UI registry, no new package. |

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS — all 14 copy elements defined with exact strings; pluralization rules locked for N and M independently; window titles, prompt labels, button labels, and warning template all specified
- [ ] Dimension 2 Visuals: PASS — one new `QPushButton("Add from PLS…")`; no custom QSS; no icon; no custom widget; three system-rendered Qt modals
- [ ] Dimension 3 Color: PASS — inherits `palette(button)` for button; zero `_theme.py` read; no custom QSS applied to new button; disabled state via standard `palette(disabled)`
- [ ] Dimension 4 Typography: PASS — default Qt platform font (no `setFont`); button label inherits platform font identical to existing four toolbar buttons
- [ ] Dimension 5 Spacing: PASS — zero new spacing values; inherits `btn_row.setSpacing(4)` 4px horizontal rhythm
- [ ] Dimension 6 Registry Safety: PASS — n/a (desktop Qt/PySide6, no third-party UI registry)
- [ ] Dimension 7 Interaction (project-specific weight for this phase): cursor lifecycle locked (restore-first-always at top of `_on_pls_fetched`); four outcome branches specified; pluralization rules locked; button placement and order locked; stale-token discard contract specified

**Approval:** pending

---

## Brand / Style References

- **`musicstreamer/ui_qt/_theme.py`** — three exposed tokens (`ERROR_COLOR_HEX`, `ERROR_COLOR_QCOLOR`, `STATION_ICON_SIZE`); none are read by Phase 58.
- **`edit_station_dialog.py:362-373`** — existing `btn_row` `QHBoxLayout` construction; the new button is the 5th widget before `addStretch()`.
- **`edit_station_dialog.py:376-379`** — existing button signal connections; new `add_pls_btn.clicked.connect(self._on_add_pls)` is the 5th connection in this block.
- **`edit_station_dialog.py:54-122`** (`_LogoFetchWorker`) — shape model for `_PlaylistFetchWorker`. Constructor signature, `finished = Signal(...)`, stale-token pattern, `run()` exception handler.
- **`edit_station_dialog.py:682-692`** — wait-cursor application + worker start; mirror exactly for the PLS path.
- **`edit_station_dialog.py:739-758`** (`_on_logo_fetched`) — D-10 restore-first-always pattern; `_on_pls_fetched` follows the same slot structure.
- **`edit_station_dialog.py:603-626`** (`_add_stream_row`) — called by `_apply_pls_entries` per resolved entry with `stream_id=None`.
- **No external design references.** Phase fully captured by 58-CONTEXT.md D-01..D-19, ROADMAP §Phase 58 (4 success criteria), and STR-15.

---

## Pre-Population Sources

| Source | Decisions Used |
|--------|---------------|
| 58-CONTEXT.md (D-01..D-19) | 19 — all implementation decisions pre-populated; no user questions asked |
| edit_station_dialog.py (code scan) | Exact call signatures, line numbers, existing spacing/font/color conventions, `_add_stream_row` column mapping, `_LogoFetchWorker` shape |
| 64-UI-SPEC.md / 55-UI-SPEC.md (precedent specs) | Template structure, dimension mapping, checker sign-off format |
| _theme.py | Token names confirmed; confirmed Phase 58 reads zero tokens |
| STACK.md | Confirmed no new deps; confirmed Qt 6.11+ / Python 3.10+ |
| User input | 0 — fully pre-populated from upstream artifacts |
