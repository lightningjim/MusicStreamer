# Phase 71: Sister Station Expansion - Research

**Researched:** 2026-05-12
**Domain:** SQLite schema migration, PySide6 Qt widget composition, URL-helper pure functions, settings ZIP export/import
**Confidence:** HIGH — all findings verified directly from codebase source (no external lookups required; domain is entirely internal)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** One unified 'Also on:' display. Manual sibling links are additive to the existing Phase 51/64 AA URL-derived 'Also on:' line — NOT a separate "Sisters:" or "Related:" row.
- **D-02:** Manual links can be cross-provider. The new mechanism handles AA name-mismatch (DI.fm "Classical Relaxation" ↔ RadioTunes "Relaxing Classical") AND same-provider variants (SomaFM Drone Zone ↔ Drone Zone 2).
- **D-03:** AA auto-detection unchanged. Phase 51's `find_aa_siblings` keeps its existing URL-channel-key behavior. No suppression of AA false positives in this phase.
- **D-04:** NowPlaying + Edit dialog only. No station-tree chain-link icon, no hamburger menu entry.
- **D-05:** Symmetric join table. `station_siblings(a_id INTEGER NOT NULL, b_id INTEGER NOT NULL, FOREIGN KEY(a_id) REFERENCES stations(id) ON DELETE CASCADE, FOREIGN KEY(b_id) REFERENCES stations(id) ON DELETE CASCADE, UNIQUE(a_id, b_id), CHECK(a_id < b_id))`.
- **D-06:** Migration follows Phase 47.2 idempotent pattern. `CREATE TABLE IF NOT EXISTS` in the main `db_init` body; no `user_version` bump.
- **D-07:** ZIP export carries siblings by station NAME, not ID. `siblings: ["Other Station Name", ...]`. On import, names resolved against destination library; unresolved names silently drop.
- **D-08:** ON DELETE CASCADE on both FKs.
- **D-09:** SomaFM 'Drone Zone' and 'Drone Zone 2' are INDEPENDENT stations — separate rows in `stations`, linked by the new sibling mechanism.
- **D-10:** Phase 71 ships fully manual linking only. No SomaFM URL-pattern detector.
- **D-11:** '+ Add sibling' button next to the chip row.
- **D-12:** Two-step picker: provider QComboBox → station list.
- **D-13:** One sibling per modal open; single-select.
- **D-14:** Per-chip × to unlink, in the merged 'Also on:' chip row.
- **D-15:** AA auto-detected chips show plain text, no ×.

### Claude's Discretion

- Helper module placement: `musicstreamer/url_helpers.py` (strong default; Phase 64 D-03 precedent).
- Chip row implementation: `FlowLayout` with compound `QWidget` (name `QPushButton` + `×` `QPushButton`).
- Provider QComboBox shape: native `QComboBox` (provider count 5–15).
- Station list widget in the picker: `QListWidget` (simpler for modal lifetime vs `QListView + QSortFilterProxyModel`).
- Sort order of manual-linked siblings: alphabetical by name.
- Merge helper: strict direct-link lookup (no transitive closure expansion).
- Tooltip on cross-provider chips: `f"Linked from {provider_name}"`.
- Toast delivery: new `Signal(str)` (e.g. `sibling_toast`) on `EditStationDialog`, connected to `MainWindow.show_toast`.

### Deferred Ideas (OUT OF SCOPE)

- SomaFM URL-pattern auto-detection (Phase 74).
- Auto-detection for other networks beyond AA and SomaFM.
- AA auto-detection override / suppression.
- Transitive closure auto-expansion.
- Multi-select picker.
- Station-tree chain-link icon.
- Vocabulary change to "sister" in the UI.
- Right-click context menu on a sibling chip.
- 'Manage siblings' bulk dialog.
- Cross-station bulk-link command.
</user_constraints>

---

## Summary

Phase 71 extends MusicStreamer's sibling-station concept from auto-detected AudioAddict URL pairs (Phase 51/64) to a first-class user-curated link mechanism. Three code layers are touched: (1) a new `station_siblings` SQLite table migrated via the established `CREATE TABLE IF NOT EXISTS` pattern in `db_init`; (2) new pure helpers `find_manual_siblings` and a merge wrapper in `url_helpers.py`; and (3) new Qt widgets in `EditStationDialog` — a chip row container replacing the current `_sibling_label` QLabel plus an `AddSiblingDialog` modal — with a minimal change to `NowPlayingPanel._refresh_siblings` to replace `find_aa_siblings` with the merge call.

All decisions are locked (D-01 through D-15). The research below answers the ten specific questions posed by the orchestrator, documents the exact shapes of existing interfaces that must remain compatible, and flags every load-bearing invariant the planner must not break.

**Primary recommendation:** Follow the Phase 47.2 / Phase 70 migration pattern exactly; reuse `_CHIP_QSS` and `FlowLayout` verbatim; keep `render_sibling_html` signature unchanged; add `sibling_toast = Signal(str)` on `EditStationDialog` connected via bound-method to `MainWindow.show_toast`.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| `station_siblings` schema + CRUD | Database/Storage (Repo) | — | Pure persistence layer; no Qt dependency |
| `find_manual_siblings` + merge helper | Pure helper (url_helpers.py) | — | No Qt, no DB access; mirrors `find_aa_siblings` placement |
| Chip row (sibling display/unlink) | Frontend (EditStationDialog) | — | Qt widget composition; reads from Repo directly |
| `AddSiblingDialog` picker | Frontend (new dialog) | — | Modal Qt dialog; calls Repo at accept time |
| NowPlaying merged display | Frontend (NowPlayingPanel) | — | Existing RichText label; only call site changes |
| ZIP export siblings field | Export/Import (settings_export.py) | — | Serialization layer; no Qt |

---

## Standard Stack

### Core (all already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `PySide6` | `>=6.10` (pyproject.toml) | Qt widgets — `QDialog`, `QListWidget`, `QComboBox`, `QHBoxLayout`, `FlowLayout` | Project-wide Qt binding |
| `sqlite3` | stdlib | `station_siblings` table + CRUD | All persistence in this project uses sqlite3 directly |
| `html` | stdlib | HTML escaping in `render_sibling_html` | T-39-01 deviation mitigation already in place |

[VERIFIED: pyproject.toml, repo.py, url_helpers.py — all direct codebase inspection]

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `FlowLayout` | project-local (`ui_qt/flow_layout.py`) | Wrapping chip row in EditStationDialog | Already imported in `edit_station_dialog.py:52`; reused for sibling chip row |

[VERIFIED: edit_station_dialog.py:52 — `from musicstreamer.ui_qt.flow_layout import FlowLayout`]

**Installation:** No new dependencies. All required libraries are already present.

---

## Architecture Patterns

### System Architecture Diagram

```
User clicks '+ Add sibling'
         │
         ▼
EditStationDialog._on_add_sibling_clicked()
         │
         ▼
AddSiblingDialog(station, repo)
  ├─ Repo.list_providers() → QComboBox
  ├─ provider_changed → Repo.list_stations() filtered by provider_id
  │                   → exclude self + already-linked (AA + manual)
  └─ OK clicked → Repo.add_sibling_link(a, b) → accept()
         │
         ▼
EditStationDialog._refresh_siblings()
  ├─ Repo.list_stations() → all_stations
  ├─ Repo.list_sibling_links(station_id) → manual_link_ids
  ├─ find_aa_siblings(all_stations, id, url) → aa_list
  ├─ find_manual_siblings(all_stations, id, manual_link_ids) → manual_list
  ├─ merge_siblings(aa_list, manual_list) → merged_list (dedup by station_id)
  └─ render chip row (AA chips = plain QPushButton; manual chips = compound widget)
         │                                              │
         ▼                                              ▼
sibling_toast.emit("Linked to X")             × click → Repo.remove_sibling_link()
         │                                              → _refresh_siblings()
         ▼                                              → sibling_toast.emit("Unlinked from X")
MainWindow.show_toast()

NowPlayingPanel.bind_station(station)
  └─ _refresh_siblings()
       ├─ Repo.list_stations() → all_stations
       ├─ Repo.list_sibling_links(station.id) → manual_link_ids
       ├─ find_aa_siblings(...)  → aa_list
       ├─ find_manual_siblings(...) → manual_list
       ├─ merge_siblings(aa_list, manual_list) → merged_list
       └─ render_sibling_html(merged_list, current_name) → RichText HTML (unchanged)
```

### Recommended Project Structure

```
musicstreamer/
├── url_helpers.py          # ADD: find_manual_siblings, merge_siblings
├── repo.py                 # ADD: station_siblings table in db_init executescript,
│                           #      add_sibling_link, remove_sibling_link, list_sibling_links
├── settings_export.py      # MODIFY: _station_to_dict + _insert_station + _replace_station
└── ui_qt/
    ├── edit_station_dialog.py   # MODIFY: chip row replaces _sibling_label, sibling_toast Signal
    ├── now_playing_panel.py     # MODIFY: _refresh_siblings call site only
    └── add_sibling_dialog.py   # NEW file

tests/
├── test_station_siblings.py    # NEW: pure helper tests + repo CRUD round-trips
└── test_settings_export.py     # MODIFY: add siblings round-trip + forward-compat
```

---

## Research Question Answers

### Q1: `find_manual_siblings` helper design and tuple shape compatibility

[VERIFIED: url_helpers.py:171-234, url_helpers.py:237-266]

**Finding:** `find_aa_siblings` returns `list[tuple[str, int, str]]` where the first element is a network slug drawn from the `NETWORKS` constant in `aa_import.py`. `render_sibling_html` maps that slug through `name_for_slug = {n["slug"]: n["name"] for n in NETWORKS}` — if the slug is not in NETWORKS, it falls back to displaying the slug string verbatim (`name_for_slug.get(slug, slug)`). This fallback is tested in `test_render_sibling_html_unknown_slug_falls_back_to_slug_literal`.

**Recommendation:** Use `provider_name` (the human-readable provider name string, e.g., "SomaFM") as the first element of the tuple for manual siblings. This is unambiguous: it IS what gets displayed as the network label by `render_sibling_html`'s fallback. No `render_sibling_html` signature change is needed. For AA entries the display name comes from NETWORKS; for manual entries the display name comes from the station's `provider_name` field (which `Repo.list_stations()` populates via `LEFT JOIN providers`).

**Exact signature:**
```python
def find_manual_siblings(
    stations: list,
    current_station_id: int,
    link_ids: list[int],
) -> list[tuple[str, int, str]]:
    """Return (provider_name_or_empty, station_id, station_name) tuples for
    manually-linked siblings. link_ids from Repo.list_sibling_links(current_station_id).
    Excludes current_station_id. Sort order: alphabetical by station_name.
    Pure function — no Qt, no DB access.
    """
```

The first element `provider_name_or_empty` is `station.provider_name or ""`. `render_sibling_html` renders this as the "network" label. For cross-provider siblings this is useful context; for same-provider siblings both station names share the same provider so the "network" label is redundant but harmless.

**Note:** The NowPlaying `render_sibling_html` path shows "provider_name — station_name" for manual siblings where the station name differs from the current station's name (same logic as AA). This is correct behavior: manual siblings to same-provider variants (Drone Zone ↔ Drone Zone 2) will show "SomaFM — Drone Zone 2", which is acceptably readable.

[VERIFIED: url_helpers.py:256-266 — `name_for_slug.get(slug, slug)` fallback, test_aa_siblings.py:225-231]

### Q2: Merge layer design and dedup rule

[VERIFIED: url_helpers.py:171-234, CONTEXT.md D-01, D-15]

**Dedup key:** `station_id` (the integer DB id). This is the only stable unique identifier across AA and manual paths.

**Precedence rule:** AA auto-detected entries take priority. The merge helper iterates `aa_list` first (building a `seen_ids` set), then appends manual entries only if their `station_id` is not already in `seen_ids`.

**Display consequence:** If a user manually links station X which `find_aa_siblings` also auto-detects, station X appears ONCE in the merged list with the AA tuple (network_slug, id, name). The manual DB row for that link remains in `station_siblings` and the `×` button does NOT appear for that chip (because it shows as an AA chip, which has no `×` per D-15). This is correct behavior per D-03 (no suppression of AA auto-siblings). The underlying `station_siblings` DB row is inert for display purposes but does no harm.

**Merge wrapper signature:**
```python
def merge_siblings(
    aa_siblings: list[tuple[str, int, str]],
    manual_siblings: list[tuple[str, int, str]],
) -> list[tuple[str, int, str]]:
    """Deduplicate by station_id; AA entries take precedence.
    Returns aa_siblings + non-duplicate manual_siblings.
    Pure function.
    """
```

**Source set passed to chip rendering:** The UI layer needs to know which entries are AA vs manual to decide whether to render a `×` button. The caller (`_refresh_siblings` in `EditStationDialog`) should keep the AA and manual lists separate before merging, so it can pass both to the chip-rendering loop independently. The `merge_siblings` function produces the combined list for `render_sibling_html` (NowPlaying) but the Edit dialog chip loop iterates the two lists separately, then skips manual entries whose `station_id` is already in the AA set.

[ASSUMED: the exact caller-side pattern for keeping AA vs manual distinct during chip painting — no existing code implements this. Low risk: it is a local EditStationDialog implementation detail.]

### Q3: Symmetric join table query patterns

[VERIFIED: repo.py:15-66 — existing schema conventions, D-05 decision]

**Best SQL for `list_sibling_links`:**
```sql
SELECT b_id AS sibling_id FROM station_siblings WHERE a_id = ?
UNION
SELECT a_id AS sibling_id FROM station_siblings WHERE b_id = ?
```

This is the standard approach for undirected-graph adjacency with canonical ordering. The `UNION` (not `UNION ALL`) deduplicates — though with the `CHECK(a_id < b_id)` constraint, a given pair can appear in at most one row, so dedup is redundant in practice but harmless.

**Performance:** The library is 50–200 stations. Even without indexes, two linear scans over a 50-200 row table complete in microseconds. An index on `a_id` and a partial index on `b_id` would be premature optimization; omit for now.

**`add_sibling_link` normalization:**
```python
def add_sibling_link(self, a_id: int, b_id: int) -> None:
    lo, hi = min(a_id, b_id), max(a_id, b_id)
    self.con.execute(
        "INSERT OR IGNORE INTO station_siblings(a_id, b_id) VALUES (?, ?)",
        (lo, hi),
    )
    self.con.commit()
```

`INSERT OR IGNORE` makes re-add a no-op (idempotent). No return value needed; callers don't need the new row ID.

**`remove_sibling_link`:**
```python
def remove_sibling_link(self, a_id: int, b_id: int) -> None:
    lo, hi = min(a_id, b_id), max(a_id, b_id)
    self.con.execute(
        "DELETE FROM station_siblings WHERE a_id = ? AND b_id = ?",
        (lo, hi),
    )
    self.con.commit()
```

**`list_sibling_links`:**
```python
def list_sibling_links(self, station_id: int) -> list[int]:
    rows = self.con.execute(
        "SELECT b_id AS sid FROM station_siblings WHERE a_id = ? "
        "UNION "
        "SELECT a_id AS sid FROM station_siblings WHERE b_id = ?",
        (station_id, station_id),
    ).fetchall()
    return [r["sid"] for r in rows]
```

[VERIFIED: repo.py:173-504 — existing CRUD method shape; sqlite3 stdlib UNION behavior]

### Q4: AddSiblingDialog widget choice — `QListWidget` vs `QListView + QSortFilterProxyModel`

[VERIFIED: ui-spec:353 — "QListWidget (not QListView + model)"; discovery_dialog.py:229-252 — QStandardItemModel + QTableView]

**Confirmed:** `QListWidget` is the right choice for a modal with 50–200 in-memory items. `DiscoveryDialog` uses `QStandardItemModel + QTableView` because it has network-fetched results and a multi-column layout (name, tags, country, bitrate, play, save). `AddSiblingDialog` has a single column of station names that are already in memory — the additional model layer is dead weight. Python-level filtering via `str.lower()` substring on 50–200 items is instantaneous and simpler to test.

**Key pattern from DiscoveryDialog** that is NOT copied: `QThread` worker + `QProgressBar`. The `AddSiblingDialog` station list is populated synchronously from `Repo.list_stations()` which is already loaded in memory at dialog construction.

[VERIFIED: discovery_dialog.py:229-252; ui-spec station list widget decision]

### Q5: Provider QComboBox population and ordering

[VERIFIED: repo.py:177-179]

```python
def list_providers(self) -> List[Provider]:
    rows = self.con.execute("SELECT id, name FROM providers ORDER BY name").fetchall()
    return [Provider(id=r["id"], name=r["name"]) for r in rows]
```

**Finding:** `Repo.list_providers()` returns providers sorted **alphabetically by name**. The picker QComboBox will therefore be alphabetically sorted, which is the expected behavior for scanning a small list of 5–15 items. The default selection is the editing station's `provider_id`, resolved against the returned list by matching `provider.id == station.provider_id`.

**Important:** If a station's `provider_id` is `None` (no provider), the QComboBox should default to the first item or a "(no provider)" placeholder entry, rather than leaving the selection on a mismatched item. The planner should decide whether to include a blank/none provider option at the top of the combo.

[VERIFIED: repo.py:177-179]

### Q6: Toast delivery from EditStationDialog

[VERIFIED: main_window.py:788-803, main_window.py:434-436, discovery_dialog.py:149-168]

**Finding: Two patterns exist in the codebase:**

1. **`Signal(str)` pattern** — e.g., `NowPlayingPanel.gbs_vote_error_toast = Signal(str)` (line 141 in now_playing_panel.py) connected to `MainWindow.show_toast` at line 348.
2. **`toast_callback: Callable` constructor kwarg** — used by `DiscoveryDialog` (discovery_dialog.py:149-163: `toast_callback: Callable[[str], None]`).

Phase 51's `navigate_to_sibling = Signal(int)` is a Signal on `EditStationDialog`. The `gbs_vote_error_toast` pattern in `NowPlayingPanel` is the closest analog to what's needed here: a new signal on the dialog, connected in `MainWindow._on_edit_requested` (and `_on_add_station`).

**Recommendation:** Add `sibling_toast = Signal(str)` to `EditStationDialog`. Wire in `MainWindow._on_edit_requested` and `_on_add_station` (lines 791-803 and 775-789) identically to how `navigate_to_sibling` is wired. This is QA-05 compliant (bound method at connection site in MainWindow). The `toast_callback` kwarg alternative would require an `EditStationDialog.__init__` signature change that propagates to all three call sites — unnecessary.

**Connection site (in both `_on_edit_requested` and `_on_add_station`):**
```python
dlg.sibling_toast.connect(self.show_toast)
```

[VERIFIED: main_window.py:788-803; now_playing_panel.py:141 — `gbs_vote_error_toast = Signal(str)` pattern]

### Q7: Repo CRUD method signatures — complete picture

[VERIFIED: repo.py:173-504 — full Repo class]

All three methods normalize (smaller_id, larger_id) at the boundary. Complete signatures with return types:

```python
def add_sibling_link(self, a_id: int, b_id: int) -> None:
    """INSERT OR IGNORE (idempotent re-add). Normalizes to (lo, hi) ordering."""

def remove_sibling_link(self, a_id: int, b_id: int) -> None:
    """Normalizes to (lo, hi) then DELETE. No error if row absent (silent no-op)."""

def list_sibling_links(self, station_id: int) -> list[int]:
    """UNION query for both (a_id=? → b_id) and (b_id=? → a_id). Returns list[int] of sibling station_ids."""
```

All three follow the existing pattern: `self.con.execute(...)` + `self.con.commit()`. No return value for add/remove (matches `delete_stream`, `reorder_streams`).

**Schema migration placement:** In `db_init`, after the existing `executescript` block (line 66) and BEFORE the try/except ALTER TABLE blocks. The new table creation uses `CREATE TABLE IF NOT EXISTS` directly in a new `try/except sqlite3.OperationalError` block — actually, since `CREATE TABLE IF NOT EXISTS` never raises `OperationalError` in modern SQLite, it can go directly in the `executescript` block body (line 16) alongside the existing tables. This is the cleanest pattern and matches how `settings` was eventually added at lines 106-111 (which used a separate try/except — a slightly older idiom). The planner should put it in the main `executescript` block body for cleanness, paralleling `station_streams`.

[VERIFIED: repo.py:15-67 — executescript block; repo.py:106-111 — settings try/except alternative]

### Q8: Plan decomposition style — wave structure reference

[VERIFIED: .planning/phases/70-hi-res-indicator-for-streams-mirror-moode-audio-criteria/70-CONTEXT.md]

Phase 70 shipped 12 plans across 5 waves. For Phase 71 the natural wave structure is:

- **Wave 0 (RED):** Contract tests for `find_manual_siblings`, `merge_siblings`, `Repo.list_sibling_links/add/remove`, settings export round-trip — all failing (no implementation).
- **Wave 1 (GREEN):** `station_siblings` schema in `db_init`; `Repo.add_sibling_link`, `remove_sibling_link`, `list_sibling_links`; `find_manual_siblings` + `merge_siblings` in `url_helpers.py`. All Wave 0 pure-helper tests pass.
- **Wave 2:** `NowPlayingPanel._refresh_siblings` updated to call merge helper. `settings_export.py` `siblings` field added to `_station_to_dict`, `_insert_station`, `_replace_station`. Settings export/import tests pass.
- **Wave 3:** `EditStationDialog` chip row: replace `_sibling_label` with `_sibling_row_widget` (FlowLayout), chip rendering, `sibling_toast` signal, `×` click handler, `_refresh_siblings` rewrite. Wire `sibling_toast` in MainWindow.
- **Wave 4:** `AddSiblingDialog` in new file `add_sibling_dialog.py`. Integration: `+ Add sibling` button click opens modal; on Accept `_refresh_siblings` + toast.
- **Wave 5:** Docs/polish (project key decisions table, ROADMAP update if needed).

[VERIFIED: 70-CONTEXT.md wave structure; CONTEXT.md in-scope list]

### Q9: Testing strategy

[VERIFIED: tests/test_aa_siblings.py — reference shape]

**New test file: `tests/test_station_siblings.py`** (parallels `test_aa_siblings.py`)

Pure helper tests (no DB, no Qt):
- `test_find_manual_siblings_returns_linked_stations` — basic correctness
- `test_find_manual_siblings_excludes_self` — station_id itself never in result
- `test_find_manual_siblings_empty_when_no_links` — empty link_ids → []
- `test_find_manual_siblings_sorts_alphabetically` — stable sort order
- `test_find_manual_siblings_ignores_unknown_ids` — link_id not in stations list → silently dropped
- `test_merge_siblings_dedup_by_station_id` — station appearing in both AA and manual lists appears once (AA wins)
- `test_merge_siblings_aa_entries_preserved` — AA list entries survive verbatim
- `test_merge_siblings_manual_only` — when aa_list empty, manual list passes through
- `test_merge_siblings_empty_both` — [] + [] → []

Repo round-trip tests (in-memory DB via `tmp_path` fixture, mirrors `test_repo.py` shape):
- `test_add_sibling_link_round_trip` — add, list → id present
- `test_add_sibling_link_idempotent` — add twice → one row, no error
- `test_remove_sibling_link` — add, remove, list → empty
- `test_remove_sibling_link_noop_when_absent` — remove non-existent row → no error
- `test_list_sibling_links_symmetric` — add A↔B via (A,B), list from B → [A]
- `test_cascade_on_station_delete` — delete station A → `station_siblings` row auto-removed; B's link list is empty
- `test_add_sibling_link_normalizes_ordering` — add(B,A) then list(A) → [B]
- `test_db_init_idempotent_with_siblings_table` — call `db_init` twice → no error

Settings export tests (extend `tests/test_settings_export.py`):
- `test_siblings_round_trip` — export with siblings, import → siblings re-linked by name
- `test_siblings_missing_key_defaults_empty` — old ZIP without `siblings` key → no error, no links
- `test_siblings_unresolved_name_silently_dropped` — import ZIP where linked station name doesn't exist → no error, no orphan link
- `test_siblings_serialized_as_names` — exported JSON contains names, not IDs

AddSiblingDialog integration tests (in `tests/ui_qt/` or `tests/test_add_sibling_dialog.py`, pytest-qt):
- `test_provider_switch_reloads_station_list` — change QComboBox → list repopulates
- `test_search_filter_case_insensitive` — "drone" matches "Drone Zone 2"
- `test_ok_disabled_when_no_selection` — Link Station button disabled initially
- `test_ok_enabled_after_selection` — single-click → button enabled
- `test_double_click_accepts` — double-click = OK
- `test_self_excluded_from_list` — editing station never appears in picker
- `test_already_linked_excluded_from_list` — existing sibling not in picker
- `test_accept_calls_add_sibling_link` — Repo.add_sibling_link called with correct IDs
- `test_empty_state_all_linked` — "All stations in this provider are already linked."
- `test_empty_state_no_stations` — "No other stations found for this provider."

Chip row tests (in `tests/test_edit_station_dialog.py`):
- `test_manual_chip_has_x_button` — manual sibling compound widget has × QPushButton
- `test_aa_chip_has_no_x_button` — AA chip is single QPushButton
- `test_x_click_calls_remove_sibling_link` — × click → Repo.remove_sibling_link
- `test_x_click_fires_sibling_toast` — sibling_toast signal emitted with "Unlinked from {name}"
- `test_sibling_row_always_visible` — visible even with 0 siblings (unlike NowPlaying)

NowPlaying merged display:
- `test_now_playing_shows_merged_siblings` — bind_station with manual + AA siblings → both appear in `_sibling_label`
- `test_now_playing_hidden_when_no_siblings` — station with no AA and no manual → hidden

[VERIFIED: tests/test_aa_siblings.py — fixture shape (_mk factory, simple assert per test); tests/test_repo.py — repo fixture pattern]

### Q10: Pitfalls and load-bearing invariants

[VERIFIED: full codebase inspection]

**Pitfall 1: T-40-04 plain-text invariant — RichText grep baseline must stay flat**

The UI-SPEC explicitly states the RichText baseline (currently 9 instances across the codebase) must be unchanged by Phase 71. The new sibling chip row in `EditStationDialog` uses **Qt widget composition** (QPushButton chips), NOT a new `setTextFormat(Qt.RichText)` call. The existing `_sibling_label` in `EditStationDialog` will be REMOVED and replaced by `_sibling_row_widget`. The existing `_sibling_label` in `NowPlayingPanel` REMAINS (no structural change). After Phase 71 the `setTextFormat(Qt.RichText)` count should be one fewer (EditStationDialog loses its QLabel) or unchanged if the NowPlaying label count stays the same. Planner must run the grep gate.

**Pitfall 2: `render_sibling_html` signature must remain unchanged**

`render_sibling_html(siblings: list[tuple[str, int, str]], current_name: str) -> str` is called from both `EditStationDialog._refresh_siblings` (which is being replaced) and `NowPlayingPanel._refresh_siblings`. The NowPlaying call site must be updated to call `merge_siblings(aa_list, manual_list)` and pass the result to `render_sibling_html` — but the signature of `render_sibling_html` itself must NOT change. Any changes to the tuple structure would break the NowPlaying path silently.

**Pitfall 3: `sibling://{id}` link scheme used by NowPlayingPanel chip clicks**

`NowPlayingPanel._on_sibling_link_activated` parses `href` for the `sibling://` prefix and extracts an integer station ID. Manual siblings' chip links in NowPlaying HTML must use the same `sibling://{id}` format produced by `render_sibling_html`. Since the merge output feeds `render_sibling_html` unchanged, this is automatic — but any refactor that bypasses `render_sibling_html` in the NowPlaying path would break it.

**Pitfall 4: `EditStationDialog._refresh_siblings` currently reads `self.url_edit.text()` for the current URL**

At line 632: `current_url = self.url_edit.text().strip()`. The new version must preserve this (reading from the live URL field, not from `self._station.streams[0].url`) so that edits to the URL field are reflected in the sibling display before saving. This is load-bearing for the new-station case where `_station.streams` is empty.

**Pitfall 5: settings_export `commit_import` uses a single transaction via `with repo.con:`**

The `commit_import` function uses `with repo.con:` as a context manager (implicit transaction). When adding sibling-link rows during import, the `station_siblings` inserts must happen INSIDE this context (before `commit_import` returns), and only AFTER all station rows have been inserted (because the FKs reference `stations.id`). This requires a two-pass approach: first pass inserts all station rows (existing `_insert_station` / `_replace_station` calls), second pass resolves sibling names to IDs and inserts `station_siblings` rows. Both passes are inside the `with repo.con:` block.

[VERIFIED: settings_export.py:292-375 — the `with repo.con:` context; the station_data loop at lines 305-315]

**Pitfall 6: `PRAGMA foreign_keys = ON` must be set before any CASCADE behavior**

`db_connect()` sets `con.execute("PRAGMA foreign_keys = ON;")` (repo.py:11). Tests that construct their own `sqlite3.connect()` and call `db_init` must also set `PRAGMA foreign_keys = ON` before testing CASCADE behavior — as `test_repo.py` conftest already does (line 6: `con.execute("PRAGMA foreign_keys = ON;")`). New test fixtures must replicate this.

[VERIFIED: repo.py:8-12; tests/test_repo.py:6-7]

**Pitfall 7: `EditStationDialog._on_sibling_link_activated` dirty-check confirm flow**

The existing `_on_sibling_link_activated` at line 1241 handles the dirty-check confirm. The new chip click path (name button → `navigate_to_sibling.emit(sibling_id)`) needs the same dirty-check logic. The UI-SPEC confirms at line 196: "The existing dirty-check confirmation flow (Phase 51 D-11) applies." The new chip's name button click handler must check `_is_dirty()` and prompt the same Save/Discard/Cancel modal. The simplest implementation: the chip name button connects to `_on_sibling_link_activated` using the same `sibling://{id}` href pattern, so the existing method handles it without duplication.

[VERIFIED: edit_station_dialog.py:1241-1288; UI-SPEC chip construction table]

**Pitfall 8: `FlowLayout` does not manage Qt tab order**

UI-SPEC line 332: "FlowLayout does not manage tab order; planner ensures `setTabOrder` in `_refresh_siblings` if needed." The existing tag chip row (also FlowLayout) does not add explicit `setTabOrder` calls. For the sibling chip row, default tab order follows widget-creation order (Qt walks QApplication focus chain). Manual `setTabOrder` calls in `_refresh_siblings` after chip construction would establish explicit order. Whether this is needed depends on accessibility requirements — the UI-SPEC says "planner ensures" which means the planner must decide. Recommendation: add explicit `setTabOrder` calls to establish `[chip_name_btn, unlink_btn, ...]... + Add sibling` left-to-right order.

[VERIFIED: edit_station_dialog.py:372-374 — existing FlowLayout tag chip row has no setTabOrder]

**Pitfall 9: `AddSiblingDialog` excluded IDs must include BOTH AA auto-detected AND manual**

The picker exclusion logic must compute the union of AA auto-detected siblings and already-manually-linked siblings. Getting only manual links from `Repo.list_sibling_links` would leave AA auto-detected siblings visible in the picker, which would be confusing (user could "add" a sibling that already appears in the 'Also on:' row via AA detection). The UI-SPEC at line 269 explicitly states: "Exclude all station IDs already linked (both AA auto-detected and manual) — obtained by merging `find_aa_siblings(...) + Repo.list_sibling_links(...)` into a set of excluded IDs."

[VERIFIED: UI-SPEC line 269]

### Q11: Nyquist validation architecture

Config confirms `nyquist_validation: true`. Test framework: pytest + pytest-qt (existing, no new setup needed).

**Phase Requirements → Test Map:**

| Behavior | Test Type | Automated Command | File |
|----------|-----------|-------------------|------|
| `station_siblings` table created by `db_init` | unit | `pytest tests/test_station_siblings.py::test_db_init_idempotent_with_siblings_table -x` | Wave 0 gap |
| `add_sibling_link` idempotent | unit | `pytest tests/test_station_siblings.py::test_add_sibling_link_idempotent -x` | Wave 0 gap |
| `list_sibling_links` symmetric | unit | `pytest tests/test_station_siblings.py::test_list_sibling_links_symmetric -x` | Wave 0 gap |
| CASCADE on station delete | unit | `pytest tests/test_station_siblings.py::test_cascade_on_station_delete -x` | Wave 0 gap |
| `find_manual_siblings` excludes self | unit | `pytest tests/test_station_siblings.py::test_find_manual_siblings_excludes_self -x` | Wave 0 gap |
| merge dedup AA wins | unit | `pytest tests/test_station_siblings.py::test_merge_siblings_dedup_by_station_id -x` | Wave 0 gap |
| settings ZIP siblings round-trip | unit | `pytest tests/test_settings_export.py::test_siblings_round_trip -x` | Wave 0 gap |
| settings ZIP missing key tolerant | unit | `pytest tests/test_settings_export.py::test_siblings_missing_key_defaults_empty -x` | Wave 0 gap |
| AddSiblingDialog self-excluded | integration (pytest-qt) | `pytest tests/test_add_sibling_dialog.py::test_self_excluded_from_list -x` | Wave 0 gap |
| × chip fires remove + toast | integration (pytest-qt) | `pytest tests/test_edit_station_dialog.py::test_x_click_calls_remove_sibling_link -x` | Wave 0 gap |
| NowPlaying merged display | integration (pytest-qt) | `pytest tests/test_now_playing_panel.py::test_now_playing_shows_merged_siblings -x` | Wave 0 gap |

**Sampling rate:**
- Per task commit: `pytest tests/test_station_siblings.py -x --tb=short`
- Per wave merge: `pytest tests/ -x --tb=short -q`
- Phase gate: full suite green before `/gsd-verify-work`

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Symmetric undirected link storage | Two-row (A→B, B→A) writes | `CHECK(a_id < b_id)` canonical single-row | Dual-write requires atomic updates and dedup-on-read; single-row is simpler and correct |
| In-picker text filter | Custom debounce / QSortFilterProxyModel | Python `str.lower()` substring in `_repopulate_station_list` | 50-200 items; in-memory; no latency; existing idiom in DiscoveryDialog |
| Chip widget | Custom paint delegate | Two `QPushButton` widgets in `QHBoxLayout` (spacing=0) | `_CHIP_QSS` already handles the visual; compound QPushButton is the established tag-chip pattern |
| Sibling display HTML | Custom renderer for NowPlaying | `render_sibling_html` unchanged | Already HTML-escapes names, already tested, already handles bullet/em-dash formatting |

---

## Code Examples

### Schema addition (inside `db_init` executescript block body)

```python
# Source: repo.py:15-66 pattern — CREATE TABLE IF NOT EXISTS
        CREATE TABLE IF NOT EXISTS station_siblings (
          a_id INTEGER NOT NULL,
          b_id INTEGER NOT NULL,
          FOREIGN KEY(a_id) REFERENCES stations(id) ON DELETE CASCADE,
          FOREIGN KEY(b_id) REFERENCES stations(id) ON DELETE CASCADE,
          UNIQUE(a_id, b_id),
          CHECK(a_id < b_id)
        );
```

[VERIFIED: repo.py:51-64 — `station_streams` FK pattern with ON DELETE CASCADE as the model]

### `find_manual_siblings` (url_helpers.py, colocated with `find_aa_siblings`)

```python
# Source: url_helpers.py:171-234 shape
def find_manual_siblings(
    stations: list,
    current_station_id: int,
    link_ids: list[int],
) -> list[tuple[str, int, str]]:
    """Return (provider_name_or_empty, station_id, station_name) triples.

    link_ids: from Repo.list_sibling_links(current_station_id).
    Excludes current_station_id even if present in link_ids (defensive).
    Sort order: alphabetical by station_name.
    Pure function — no Qt, no DB access, no logging.
    """
    link_set = set(link_ids)
    result: list[tuple[str, int, str]] = []
    for st in stations:
        if st.id == current_station_id:
            continue
        if st.id not in link_set:
            continue
        result.append((st.provider_name or "", st.id, st.name))
    result.sort(key=lambda t: t[2].casefold())
    return result
```

### `merge_siblings` (url_helpers.py)

```python
def merge_siblings(
    aa_siblings: list[tuple[str, int, str]],
    manual_siblings: list[tuple[str, int, str]],
) -> list[tuple[str, int, str]]:
    """Deduplicate by station_id; AA entries take precedence.
    Pure function — no Qt, no DB access.
    """
    seen: set[int] = {sid for _, sid, _ in aa_siblings}
    merged = list(aa_siblings)
    for entry in manual_siblings:
        if entry[1] not in seen:
            merged.append(entry)
            seen.add(entry[1])
    return merged
```

### `_station_to_dict` addition (settings_export.py)

```python
# Source: settings_export.py:108-132 — _station_to_dict pattern
# Add after "streams" key:
"siblings": [],  # populated in build_zip via a second pass over station_links
```

Import forward-compat idiom (mirrors Phase 70 pattern):
```python
# Source: settings_export.py:420-424 — Phase 70 forward-compat idiom
sibling_names = list(data.get("siblings") or [])  # old ZIPs missing key → []
```

### `_mk` fixture for test_station_siblings.py

```python
# Source: tests/test_aa_siblings.py:12-23 — _mk factory pattern
def _mk(id_, name, provider_name=None, url="http://example.com/stream"):
    return Station(
        id=id_, name=name, provider_id=None, provider_name=provider_name,
        tags="", station_art_path=None, album_fallback_path=None,
        streams=[StationStream(id=id_*10, station_id=id_, url=url, position=1)],
    )
```

### `sibling_toast` signal declaration

```python
# Source: edit_station_dialog.py:250-255 — navigate_to_sibling pattern
# Add to EditStationDialog class body:
sibling_toast = Signal(str)
```

### `sibling_toast` wiring in MainWindow

```python
# Source: main_window.py:788-803 — navigate_to_sibling wiring pattern
dlg.sibling_toast.connect(self.show_toast)
```

---

## Common Pitfalls

### Pitfall 1: Two-pass import needed for siblings
**What goes wrong:** `_insert_station` / `_replace_station` return `station_id`; you need the station's new DB ID to insert a `station_siblings` row. But the partner station row must also exist.
**Why it happens:** `commit_import` iterates `preview.stations_data` once, inserting/replacing each station. At iteration time for station A, station B (its sibling) may not have been inserted yet.
**How to avoid:** Add a second pass AFTER the main station loop. After all station rows are present, iterate `stations_data` again, resolve `siblings` names to IDs via a `name → id` dict built from the fresh DB, and insert `station_siblings` rows.
**Warning signs:** Import silently drops all sibling links even when both stations are in the ZIP.

### Pitfall 2: `_refresh_siblings` in EditStationDialog reads from `url_edit`, not `_station.streams`
**What goes wrong:** New implementation reads `self._station.streams[0].url` for the AA sibling check, missing URL edits not yet saved.
**Why it happens:** Developer assumes `_station` is the source of truth during editing.
**How to avoid:** Preserve line 632 pattern: `current_url = self.url_edit.text().strip()`. For the manual siblings list, `self._station.id` is always correct (the station exists in DB before the dialog opens).

### Pitfall 3: CASCADE test fails silently if PRAGMA foreign_keys not enabled
**What goes wrong:** `test_cascade_on_station_delete` deletes station A and then checks `list_sibling_links(B)` still returns `[A]`.
**Why it happens:** SQLite foreign key enforcement is OFF by default.
**How to avoid:** Every test fixture that opens a new `sqlite3.connect()` must call `con.execute("PRAGMA foreign_keys = ON;")`. The existing `test_repo.py` fixture already does this — mirror it exactly.
**Warning signs:** DELETE on station doesn't cascade; orphan rows remain in `station_siblings`.

### Pitfall 4: `AddSiblingDialog` excluded-IDs set built from stale data
**What goes wrong:** Picker shows stations that are already siblings (either AA auto-detected or manually linked).
**Why it happens:** `_repopulate_station_list` is called before the exclusion set is computed, or only `Repo.list_sibling_links` is used (missing AA auto-detected IDs).
**How to avoid:** Compute exclusion set once at `_repopulate_station_list` entry: `excluded = {current_station_id} | set(aa_sibling_ids) | set(repo.list_sibling_links(current_station_id))`.

### Pitfall 5: `FlowLayout` requires `chip.setParent(None)` before clear
**What goes wrong:** Clearing the chip row with `QLayoutItem.widget().deleteLater()` leaves ghost widgets or crashes.
**Why it happens:** `FlowLayout` stores `QLayoutItem` wrappers; `takeAt(0)` returns items but doesn't delete their widgets.
**How to avoid:** In `_refresh_siblings`, iterate `while self._sibling_row_layout.count(): item = self._sibling_row_layout.takeAt(0); if item.widget(): item.widget().deleteLater()`. This matches how the tag chip row is rebuilt in `_on_add_tag` / `_on_clear_tags`.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `EditStationDialog._render_sibling_html` private method | `render_sibling_html` free function in `url_helpers.py` | Phase 64 D-03 | Phase 71 extends `url_helpers.py` for the same reason |
| Single `find_aa_siblings` call site in NowPlaying | Will become `merge_siblings(find_aa_siblings(...), find_manual_siblings(...))` | Phase 71 | Both panels gain manual-link siblings in 'Also on:' display |
| `_sibling_label` QLabel in EditStationDialog | `_sibling_row_widget` FlowLayout container with chip widgets | Phase 71 | Enables per-chip `×` affordance |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Using `provider_name` as the first tuple element in `find_manual_siblings` output (no `render_sibling_html` change needed) | Q1 / Code Examples | If `render_sibling_html` is changed to special-case manual vs AA entries, display format changes. Low risk: the fallback behavior is verified by existing tests. |
| A2 | `(station.provider_name or "")` is adequate for the NowPlaying 'Also on:' label for manual cross-provider siblings — shows e.g. "SomaFM — Drone Zone 2" | Q1 | User may find "SomaFM — Drone Zone 2" odd when already viewing a SomaFM station. Acceptable per D-01 (merged, no distinction). |
| A3 | `AddSiblingDialog` should include a "(no provider)" entry at the top of the QComboBox for stations with `provider_id = None` | Q5 | Without it, stations with no provider are unreachable via the picker when filtering by provider. Medium risk — a small number of stations may have no provider. Planner should decide. |
| A4 | Two-pass import is the right approach for siblings in `commit_import` | Q10 Pitfall 1 | If a single-pass approach is used (build name→id map from DB after each insert), it could work but is more complex and error-prone. |

**Assumptions A1, A3, A4 are the highest-priority items for the planner to confirm before executing.**

---

## Open Questions

1. **Provider "(no provider)" entry in AddSiblingDialog QComboBox**
   - What we know: `Repo.list_providers()` returns only named providers; stations with `provider_id = NULL` have `provider_name = None`.
   - What's unclear: Should the picker include these unprovisioned stations at all? If yes, a synthetic "(no provider)" entry is needed at the top of the combo.
   - Recommendation: Include it — the user may have manually-imported stations without a provider assignment, and those should be link-able.

2. **Import second-pass: what to do when both A→B and B→A are in the ZIP?**
   - What we know: The ZIP serializes station A's `siblings: [B's name]` and station B's `siblings: [A's name]`.
   - What's unclear: The second pass would attempt to insert (A_id, B_id) once for each, but `INSERT OR IGNORE` makes the second insert a no-op. No issue — just confirming the planner uses `INSERT OR IGNORE`.
   - Recommendation: Use `INSERT OR IGNORE` (mirrors `add_sibling_link` normalization). No special handling needed.

3. **Tab order for `_sibling_row_widget` in `EditStationDialog`**
   - What we know: `FlowLayout` doesn't manage Qt tab order; chip order mirrors creation order in `_refresh_siblings`.
   - What's unclear: Whether explicit `setTabOrder` calls are needed in addition to the default creation order.
   - Recommendation: Add explicit `setTabOrder` calls in `_refresh_siblings` after all chips are added. The `+ Add sibling` button should be last in the chip-row tab order.

---

## Environment Availability

Step 2.6: SKIPPED — Phase 71 is code/config changes only. No new external tool dependencies. The existing Python + PySide6 + SQLite3 + pytest environment covers all implementation and testing requirements.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >= 9 + pytest-qt >= 4 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` `testpaths = ["tests"]` |
| Quick run command | `pytest tests/test_station_siblings.py -x --tb=short` |
| Full suite command | `pytest tests/ -x --tb=short -q` |

### Phase Requirements → Test Map

| Req | Behavior | Test Type | Automated Command | File Exists? |
|-----|----------|-----------|-------------------|-------------|
| D-05 | `station_siblings` table with CHECK + UNIQUE + CASCADE | unit | `pytest tests/test_station_siblings.py -x` | ❌ Wave 0 |
| D-06 | `db_init` idempotent (call twice, no error) | unit | `pytest tests/test_station_siblings.py::test_db_init_idempotent_with_siblings_table -x` | ❌ Wave 0 |
| D-07 | ZIP siblings round-trip by name | unit | `pytest tests/test_settings_export.py::test_siblings_round_trip -x` | ❌ Wave 0 |
| D-07 | Old ZIP (missing `siblings` key) → no error | unit | `pytest tests/test_settings_export.py::test_siblings_missing_key_defaults_empty -x` | ❌ Wave 0 |
| D-08 | ON DELETE CASCADE removes link row | unit | `pytest tests/test_station_siblings.py::test_cascade_on_station_delete -x` | ❌ Wave 0 |
| D-01 | NowPlaying shows merged AA+manual siblings | integration | `pytest tests/test_now_playing_panel.py::test_now_playing_shows_merged_siblings -x` | ❌ Wave 0 |
| D-14 | × click removes manual link | integration | `pytest tests/test_edit_station_dialog.py::test_x_click_calls_remove_sibling_link -x` | ❌ Wave 0 |
| D-15 | AA chip has no × button | integration | `pytest tests/test_edit_station_dialog.py::test_aa_chip_has_no_x_button -x` | ❌ Wave 0 |
| D-12 | Provider switch reloads station list | integration | `pytest tests/test_add_sibling_dialog.py::test_provider_switch_reloads_station_list -x` | ❌ Wave 0 |
| D-13 | Picker excludes self + already-linked | integration | `pytest tests/test_add_sibling_dialog.py::test_self_excluded_from_list -x` | ❌ Wave 0 |
| Merge | Dedup by station_id; AA wins | unit | `pytest tests/test_station_siblings.py::test_merge_siblings_dedup_by_station_id -x` | ❌ Wave 0 |
| Merge | Idempotent add (INSERT OR IGNORE) | unit | `pytest tests/test_station_siblings.py::test_add_sibling_link_idempotent -x` | ❌ Wave 0 |
| Symmetric | `list_sibling_links` sees rows from both directions | unit | `pytest tests/test_station_siblings.py::test_list_sibling_links_symmetric -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_station_siblings.py -x --tb=short`
- **Per wave merge:** `pytest tests/ -x --tb=short -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_station_siblings.py` — covers all pure helper + repo CRUD + CASCADE tests
- [ ] `tests/test_add_sibling_dialog.py` — covers picker interaction tests
- [ ] Add to `tests/test_settings_export.py`: `test_siblings_round_trip`, `test_siblings_missing_key_defaults_empty`, `test_siblings_unresolved_name_silently_dropped`
- [ ] Add to `tests/test_edit_station_dialog.py`: chip row tests (×, AA chip, sibling_toast)
- [ ] Add to `tests/test_now_playing_panel.py`: merged display test

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes (station names in chip labels, toasts) | `Qt.PlainText` on new QPushButton labels (chips use `setText()`, not `setTextFormat(Qt.RichText)`); `html.escape` already applied in `render_sibling_html` for NowPlaying HTML path |
| V6 Cryptography | no | — |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious station name in chip label | Tampering | `QPushButton.setText(name)` — Qt renders QPushButton text as plain text by default; no HTML injection possible (T-40-04 invariant) |
| Malicious station name in NowPlaying HTML | Tampering | `html.escape(station_name, quote=True)` already in `render_sibling_html` (line 263); merge output passes through this unchanged |
| ZIP import with crafted `siblings` list | Tampering | Names resolved by exact match against live `stations` table; unresolved names silently dropped; no eval/exec path |
| `sibling://{id}` href with non-integer payload | Tampering | `_on_sibling_link_activated` line 1260-1263 wraps `int(href[len(prefix):])` in try/except ValueError; already hardened |

---

## Sources

### Primary (HIGH confidence — direct codebase inspection)
- `musicstreamer/url_helpers.py` — `find_aa_siblings` signature (line 171), `render_sibling_html` signature (line 237), tuple shape, fallback slug behavior (line 259)
- `musicstreamer/repo.py` — `db_init` schema (lines 15-67), CRUD method shapes (lines 173-504), `list_providers` ordering (line 178), idempotent migration patterns (lines 69-111)
- `musicstreamer/models.py` — `Station`, `StationStream`, `Provider` dataclass fields
- `musicstreamer/settings_export.py` — `_station_to_dict` (lines 108-132), `_insert_station` (lines 390-425), `_replace_station` (lines 428-483), `commit_import` transaction pattern (lines 275-375)
- `musicstreamer/ui_qt/edit_station_dialog.py` — `_sibling_label` (line 486), `_refresh_siblings` (lines 617-651), `navigate_to_sibling = Signal(int)` (line 255), `_CHIP_QSS` (lines 189-203), `FlowLayout` import (line 52), `_on_sibling_link_activated` (lines 1241-1288)
- `musicstreamer/ui_qt/now_playing_panel.py` — `_sibling_label` (lines 354-360), `_refresh_siblings` (lines 1182-1224)
- `musicstreamer/ui_qt/main_window.py` — `show_toast` (line 434), `navigate_to_sibling` wiring (lines 788-803), `_on_navigate_to_sibling` (lines 813-840)
- `musicstreamer/ui_qt/discovery_dialog.py` — `QListWidget` vs model-based picker comparison (lines 229-252), `toast_callback` kwarg pattern (lines 149-168)
- `tests/test_aa_siblings.py` — `_mk` fixture factory (lines 12-23), test shape (all 232 lines)
- `tests/test_repo.py` — repo fixture (lines 7-14), test shape
- `.planning/phases/71-*/71-CONTEXT.md` — all D-01 through D-15 locked decisions
- `.planning/phases/71-*/71-UI-SPEC.md` — full component inventory, interaction contract, layout decisions
- `.planning/config.json` — `nyquist_validation: true`

### Secondary (MEDIUM confidence)
- `.planning/phases/70-*/70-CONTEXT.md` — Phase 70 wave structure and migration pattern reference

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are already in the project
- Architecture: HIGH — all patterns verified from existing code
- Pitfalls: HIGH — each pitfall sourced from concrete codebase evidence
- Test strategy: HIGH — exact test shapes modeled on existing `test_aa_siblings.py`

**Research date:** 2026-05-12
**Valid until:** 2026-06-12 (30 days; this is internal codebase research, stable until a phase 72+ modifies the same files)
