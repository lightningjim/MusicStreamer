# Phase 47 — UI Review

**Audited:** 2026-04-18
**Baseline:** Abstract 6-pillar standards (no UI-SPEC.md per CONTEXT rationale — mechanical QTableWidget column extension, no visual design decisions)
**Screenshots:** Not captured — desktop PySide6/Qt app, no HTTP dev server applicable. Audit is code-review only.
**Scope:** Single dialog, single column added. `musicstreamer/ui_qt/edit_station_dialog.py` (the only modified Qt surface; all other Phase 47 changes are backend).

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 4/4 | Header literal "Bitrate" is unambiguous; no generic placeholders introduced |
| 2. Visuals | 3/4 | Column fits the existing 4-col rhythm cleanly; no header unit hint ("kbps") |
| 3. Color | 4/4 | No new color tokens; inherits palette from existing QTableWidget |
| 4. Typography | 4/4 | No new fonts or sizes; inherits from existing table |
| 5. Spacing | 4/4 | Column width (70px) is proportional to the existing 80/80/60 scale |
| 6. Experience Design | 3/4 | Delegate validates input but provides no affordance hint; empty-cell save-path is robust |

**Overall: 22/24**

---

## Top 3 Priority Fixes

1. **Column header lacks unit suffix** — User sees "Bitrate" with no indication of unit. A value of "320" is ambiguous without context (kbps? kbit/s? Mbps?) — fix: change header label at `edit_station_dialog.py:294` from `"Bitrate"` to `"Bitrate (kbps)"`. One-line change, eliminates guesswork; the 70px column width has room for the parenthetical with `QHeaderView.Fixed` (measure: "Bitrate (kbps)" ≈ 90px at default font, so also bump `setColumnWidth(_COL_BITRATE, 70)` at line 306 to `95`).

2. **No placeholder hint for empty cells** — `_add_stream_row` renders `bitrate_kbps == 0` as an empty `QTableWidgetItem` (line 439-442), so users editing a legacy stream see a blank cell with no cue that they can type a number. The `QIntValidator(0, 9999)` only kicks in once they start editing — fix: set `Qt.ItemDataRole.PlaceholderText` on the empty cell (PySide6 supports this via `setData(Qt.ToolTipRole, "e.g. 128")` or a subtle grey dash `"—"`). Alternatively, enrich `_BitrateDelegate.createEditor` to call `editor.setPlaceholderText("e.g. 128")` — only visible during edit but still a discoverability win.

3. **Bitrate column not surfaced as a failover-ordering signal anywhere in the dialog** — The entire Phase 47 value proposition is "edit this number and higher-quality streams play first," but the Edit Station dialog gives the user no hint that this column drives failover order. The CONTEXT explicitly deferred a "computed order preview" column, which is the right call, but a one-line static help label above the table (or a tooltip on the column header) would close the gap — fix: add `self.streams_table.horizontalHeaderItem(_COL_BITRATE).setToolTip("Higher bitrate streams play first on failover")` after table construction. Zero visual cost, full discoverability.

---

## Detailed Findings

### Pillar 1: Copywriting (4/4)

**Evidence:**
- Header label at line 294: `["URL", "Quality", "Codec", "Bitrate", "Position"]` — all single-word, parallel with existing columns. "Bitrate" matches the vocabulary users already know from DI.fm tier terms in other surfaces.
- No generic "Submit/Save/OK/Cancel" introduced (Save/Discard/Delete buttons are pre-existing from Phase 39).
- No empty-state or error strings introduced by Phase 47. The save path's `try/except ValueError` coerces silently to 0 (line 709-710), which is the right UX — no error dialog for a cleared cell.

**Minor nit:** "Bitrate" alone (no unit) is the only copy concern — see Priority Fix #1.

### Pillar 2: Visuals (3/4)

**Evidence:**
- The column is inserted between Codec and Position — semantically correct grouping (URL | Quality | Codec | Bitrate | Position reads as "what → how → how-fast → where-in-order").
- Width progression (URL=Stretch, Quality=80, Codec=80, **Bitrate=70**, Position=60) steps down sensibly as columns become more compact.
- No icon, no color, no font differentiation — follows the cited Station Star Delegate pattern of "plain text cell, delegate only intervenes at edit time."

**Gap:** No visual discoverability of the validator. User has no cue the column is numeric-only until they start editing and the validator silently rejects keystrokes. The Star Delegate analog is stronger because it paints an icon; `_BitrateDelegate` paints nothing — inherits default rendering. This is acceptable (matches Quality/Codec/Position which are also plain text with implicit type expectations), but fails a perfect score because numeric constraints aren't self-documenting.

### Pillar 3: Color (4/4)

**Evidence:**
- No new color classes, hex literals, or QSS introduced by Phase 47. Grep for `#[0-9a-fA-F]` and `setStyleSheet` on the modified regions: zero hits.
- The existing `_DELETE_BTN_QSS = f"QPushButton {{ color: {ERROR_COLOR_HEX}; }}"` (line 145) and `_CHIP_QSS` (line 127) are Phase 46/39 tokens; untouched.
- Bitrate cells inherit `setAlternatingRowColors(True)` (line 296) — consistent with the other four columns.

### Pillar 4: Typography (4/4)

**Evidence:**
- No `setFont`, no `QFont`, no size/weight manipulation introduced. Grep: zero hits in Phase 47 diff.
- Cell text uses default `QTableWidgetItem` font, identical to Quality/Codec/Position cells.
- Header label uses the standard QHeaderView font — consistent with the other four headers.

### Pillar 5: Spacing (4/4)

**Evidence:**
- Column widths: `URL=Stretch, Quality=80, Codec=80, Bitrate=70, Position=60` (lines 304-307). The 70px slot between two 80/60 neighbors reads as a natural interpolation.
- No new margins, no `setContentsMargins` changes, no `setSpacing` changes. Grep: zero Phase 47-scoped hits.
- The `_swap_rows` helper iterates `range(table.columnCount())` (line 472) — picks up the new column automatically, no hard-coded bounds.

### Pillar 6: Experience Design (3/4)

**Evidence:**

*Input validation (+):*
- `_BitrateDelegate` (line 155-167) attaches `QIntValidator(0, 9999, parent)` — blocks non-numeric keystrokes at the source. Follows the documented Station Star Delegate module-level class placement convention.
- Save-path coercion (lines 707-710) wraps `int(bitrate_text or "0")` in try/except `ValueError` → falls back to 0. Belt-and-braces: delegate validates at edit time, save-path neutralizes anything that slipped through (paste, programmatic set, etc.).

*Empty-state handling (+):*
- `_add_stream_row` renders `bitrate_kbps == 0` as empty string (line 441) — correct UX, avoids "0" as a misleading literal for "unknown."
- Legacy streams (pre-47 DB rows, ZIP imports without the key) hydrate as 0 via Plan 47-02's additive schema default, then display empty here. Full forward-compat path works.

*State coverage:*
- Loading state: N/A (synchronous table population).
- Error state: `_on_save` silently coerces malformed input to 0. No user-facing error — debatable but correct for a numeric field with a clear default ("unknown"). A toast or inline indicator would be over-engineering for this use case.
- Disabled state: Delete button still guarded by `_current_station_name` check (line 380-381, pre-existing Phase 39 behavior) — not regressed.
- Confirmation for destructive actions: Not applicable to bitrate edits (non-destructive; save writes through on button click per existing dialog contract).

*Gaps (−):*
- No affordance indicating the column drives failover order — the feature is invisible to users who don't read the changelog. See Priority Fix #3.
- No placeholder / ghost text on empty cells — validator discoverability deficit. See Priority Fix #2.
- Delegate class `_BitrateDelegate` has no `displayText` override, so Qt's default locale-aware integer formatting applies (may insert a thousands separator on some locales — e.g. "1,280" for a 1280kbps entry). Not a bug for the 0-9999 range (rare to hit 4-digit thousands separator territory), but worth noting for a future FLAC-at-1411kbps scenario.

---

## Consistency with Cited Analog (Station Star Delegate)

Per CONTEXT, `_BitrateDelegate` was styled "consistent with the Station Star Delegate pattern." Audit confirms:

- **Module-level class placement:** `_BitrateDelegate` at module scope (line 155), mirrors `StationStarDelegate` at module scope in `station_star_delegate.py:33`.
- **Underscore prefix for module-private delegate** (`_BitrateDelegate`): appropriate since it's local to this dialog, unlike the reusable `StationStarDelegate`. Divergence is intentional and correct.
- **`QStyledItemDelegate` subclass + `createEditor` override:** standard Qt idiom, both follow it.
- **Difference:** `StationStarDelegate` overrides `paint` + `editorEvent` to render and respond to clicks on a non-editable cell. `_BitrateDelegate` only overrides `createEditor` because it IS editing, not painting an affordance. The design divergence reflects purpose; neither is a regression.

Pattern alignment: **consistent**.

---

## Files Audited

- `musicstreamer/ui_qt/edit_station_dialog.py` (primary, 753 lines; Phase 47 diff localized to lines 24, 39, 147-167, 292-308, 421-444, 697-729)
- `musicstreamer/ui_qt/station_star_delegate.py` (82 lines, pattern-analog reference only, not modified by Phase 47)
- `.planning/phases/47-.../47-CONTEXT.md` (UI scope + rationale for no UI-SPEC)
- `.planning/phases/47-.../47-01-SUMMARY.md`, `47-02-SUMMARY.md`, `47-03-SUMMARY.md` (implementation record)
- `.planning/phases/47-.../47-01-PLAN.md`, `47-02-PLAN.md`, `47-03-PLAN.md` (intended contract)

---

*Phase: 47-stats-for-nerds-autoeq-import-harvest-seed-005-live-gstreame*
*Reviewed: 2026-04-18*
