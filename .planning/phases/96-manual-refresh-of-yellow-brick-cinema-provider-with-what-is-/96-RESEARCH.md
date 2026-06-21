# Phase 96: Manual Refresh of Live-Stream URLs from Channel - Research

**Researched:** 2026-06-20
**Domain:** PySide6 UI (QDialog, QThread, QMenu), SQLite schema migration, yt_dlp channel scanning
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Per-station boolean flag, default OFF — "Re-sync live URL from channel" — new schema column on `stations` via idempotent additive migration in `repo.py:db_init()`.
- **D-02:** Flag gated to YouTube URLs only in `EditStationDialog`, mirroring the YouTube/Twitch gate at `edit_station_dialog.py:1289-1295`. Non-YouTube stations cannot enable it.
- **D-03:** At flag-time (and on each successful re-sync), store the stream's current YouTube title as a hidden "anchor" on the station. Anchor is used ONLY to pre-order/hint suggestions in the manual-map dialog — NOT to auto-apply anything. The station's user-facing display name is independent.
- **D-04:** Primary surface is a provider/channel-level "Refresh live streams" action via sidebar right-click context menu on the provider row. No provider context-menu exists today — this phase introduces one. Action re-scans the channel and opens the review/resolve dialog operating over ALL flagged stations of that provider at once.
- **D-05:** No automatic title matching. Review dialog always shows channel's currently-live streams side-by-side with user's flagged stations. The user maps/drops/adds every time. Stored title anchor only pre-orders or pre-suggests likely pairings; it never auto-applies a URL change.
- **D-06:** Update URL via manual map — user maps a flagged station to a currently-live stream; the station's stream URL (and title anchor) is re-pointed in place. Preserve name, tags, avatar, and any other streams on the station.
- **D-07:** Dialog also supports: map a replacement (flagged station whose old stream is gone → otherwise-unrelated new live stream); drop/delete a flagged station whose stream is gone with no replacement; add a brand-new currently-live stream as a new station.
- **D-08:** Each add/replace row in the review dialog exposes an editable name field, pre-filled with the live stream's current YouTube title (for new adds) or the existing station's current name (for replacements/remaps).
- **D-09:** Refresh is review-and-confirm, not silent. Reuses the async-worker + main-thread-persist pattern from `_AvatarFetchWorker` at `edit_station_dialog.py:134-193`.
- **D-10:** Conservative defaults. Unresolved flagged stations are left untouched (URL unchanged, NEVER auto-deleted). Drops and new-stream adds are opt-in (unchecked by default). Deletions always require an explicit tick. Nothing destructive or additive happens without deliberate user action. A summary of what will change is shown before Apply.

### Claude's Discretion
- Exact dialog layout (two-column map UI vs. row-per-station with a "currently-live" dropdown).
- How the title anchor pre-orders suggestions.
- Whether to also add a per-station "Refresh now" affordance in `EditStationDialog` alongside the flag (D-04).
- Migration column names/types for the flag and the title anchor.
- Whether the flag and anchor live on `stations` or are derived; dedup interaction with `station_exists_by_url`.
- Exact provider/channel grouping key used to scope "all flagged stations of this channel."

### Deferred Ideas (OUT OF SCOPE)
- Pluggable, custom-site-aware live-URL resolver (Twitch and arbitrary sites) — v3 milestone.
- Auto/scheduled refresh on app launch.
- Solving the top-level-URL ↔ first-StationStream-URL duplication — Phase 97.
</user_constraints>

---

## Summary

Phase 96 adds a manual, YouTube-only "re-sync live URL from channel" capability. The core problem is that 24/7 YouTube live streams (Yellow Brick Cinema, Cafe BGM, etc.) periodically get restarted by the channel owner, minting a new `watch?v=` URL; saved stations go stale because the old URL yields a dead stream. Today `import_stations` (yt_import.py:140) uses URL-based dedup via `station_exists_by_url`, which means a restarted stream re-imports as a duplicate instead of updating the saved station in place.

The implementation has five distinct work areas: (1) schema additions for the per-station flag and title anchor, plus a per-provider channel scan URL; (2) `EditStationDialog` checkbox and companion scan-URL field; (3) a new provider right-click context menu wired through the existing `StationTreeModel`/`_TreeNode` model; (4) a new `_LiveRefreshScanWorker` QThread mirroring `_YtScanWorker`, and a new `LiveRefreshDialog` mirroring the `import_dialog.py` YouTube tab; and (5) repo persistence methods for update-in-place (bypassing `station_exists_by_url`) and for station deletion and new-station insertion.

**Primary recommendation:** All five areas are independently plannable. The schema migration (Plan A) is the zero-risk prerequisite that unlocks everything else. The dialog (Plan B) and context-menu wiring (Plan C) can be co-developed. Apply persistence (Plan D) comes last.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Flag storage + title anchor | Database / Storage | — | New `stations` columns via additive migration |
| Channel scan URL storage | Database / Storage | — | New `providers` column (per-channel, not per-station) |
| YouTube channel re-scan | API / Backend (yt_dlp) | — | `scan_playlist` already provides this; new worker wraps it |
| Provider right-click menu | Frontend / UI | — | `_on_tree_context_menu` in `station_list_panel.py` |
| Review/resolve dialog | Frontend / UI | — | New `LiveRefreshDialog(QDialog)` modeled on `import_dialog.py` |
| Apply persistence | Database / Storage | — | `repo.update_stream`, `repo.delete_station`, `repo.insert_station` |
| Node-runtime threading | API / Backend | Frontend / UI | `check_node()` resolved at startup; passed through the worker |

---

## Standard Stack

### Core (all pre-existing — no new packages)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PySide6 | 6.11+ (project pinned) | QDialog, QThread, Signal, QMenu, QCheckBox, QComboBox | Project-standard UI toolkit [ASSUMED] |
| yt_dlp | 2026.x (project pinned) | `scan_playlist` re-use for channel live-stream enumeration | Already wired in `yt_import.py` [VERIFIED: codebase] |
| sqlite3 | stdlib | Additive column migrations via `db_init()` pattern | Established project DB layer [VERIFIED: codebase] |

### No new external packages
Phase 96 installs zero new PyPI packages. All building blocks exist in the project's `.venv`. [VERIFIED: codebase]

---

## Package Legitimacy Audit

> No new packages to audit. Phase 96 is purely additive within the existing stack.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
User right-clicks provider row
          |
          v
StationListPanel._on_tree_context_menu()
  (detect node.kind == "provider" branch -- NEW)
          |
          v
LiveRefreshDialog(repo, provider_id, provider_name, channel_scan_url, node_runtime)
  [opens modal]
          |
          +--> [Phase 1 of dialog] _LiveRefreshScanWorker(QThread)
          |         calls: yt_import.scan_playlist(channel_scan_url, node_runtime=...)
          |         emits: results: list[dict]  (title, url, provider)
          |         emits on error: error: str
          |
          +--> [Phase 2] Populate two-panel review UI:
          |      Left column:  "Your flagged stations" (from repo)
          |      Right column: "Currently live on channel" (from scan_playlist results)
          |      User maps each flagged station to a live stream (QComboBox per row)
          |      or checks "Drop" / checks "Add as new station" (unchecked by default)
          |
          +--> [Phase 3] User clicks Apply
                    |
                    v
               _apply_refresh(repo, mappings):
                 - For each REMAP:   repo.update_stream(stream_id, new_url, ...)
                                     + repo.set_live_url_title_anchor(station_id, new_title)
                 - For each DROP:    repo.delete_station(station_id)  [explicit tick required]
                 - For each ADD:     repo.insert_station(name, url, provider_name, tags="")
                                     + repo.set_live_url_syncs_from_channel(station_id, True)
                                     + repo.set_live_url_title_anchor(station_id, title)
               emits: refresh_complete signal → MainWindow refreshes station list
```

### Recommended Project Structure

No new top-level modules. All changes are additive within existing files:

```
musicstreamer/
├── repo.py                     # NEW: 3 additive migrations + 4 new Repo methods
├── models.py                   # NEW: Station.live_url_syncs_from_channel + .live_url_title_anchor
│                               #      Provider.channel_scan_url
├── ui_qt/
│   ├── station_list_panel.py   # NEW: provider branch in _on_tree_context_menu
│   ├── station_tree_model.py   # NEW: _TreeNode.provider_id field
│   ├── edit_station_dialog.py  # NEW: flag checkbox + scan-URL companion field
│   └── live_refresh_dialog.py  # NEW FILE: LiveRefreshDialog + _LiveRefreshScanWorker
tests/
├── test_repo.py                # NEW: 3 migration idempotency tests + new method tests
├── test_live_refresh_dialog.py # NEW FILE: diff logic unit tests
└── test_station_tree_model.py  # NEW: provider_id_at() / context-menu provider detection
```

### Pattern 1: Additive Column Migration (db_init idempotency)
**What:** Add new nullable columns to `stations` and `providers` via `ALTER TABLE ... ADD COLUMN` inside a `try/except sqlite3.OperationalError` block.
**When to use:** Any schema addition that must be backward-compatible with existing DBs.
**Example** (from `repo.py:313-324`, Phase 89A pattern):
```python
# Source: musicstreamer/repo.py:313-324 [VERIFIED: codebase]
try:
    con.execute("ALTER TABLE stations ADD COLUMN channel_avatar_path TEXT")
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists — idempotent
```
Phase 96 adds THREE such blocks in the same order:
1. `stations.live_url_syncs_from_channel INTEGER NOT NULL DEFAULT 0`
2. `stations.live_url_title_anchor TEXT` (nullable, no DEFAULT)
3. `providers.channel_scan_url TEXT` (nullable, no DEFAULT)

All three MUST land AFTER the legacy URL-column rebuild block (Phase 73/82/83/89A "Pitfall 2" ordering rule: the rebuild's `CREATE TABLE stations_new / INSERT SELECT` doesn't carry dynamically-added columns). [VERIFIED: codebase, repo.py:267-295]

### Pattern 2: QThread Worker with Signal Result (async-worker + main-thread-persist)
**What:** Blocking I/O runs on a QThread worker; results are emitted to the main thread via Signals; persistence always happens on the main thread.
**When to use:** All network calls (scan_playlist) and any blocking DB operation off the main thread.
**Example** (from `import_dialog.py:75-101`, `_YtScanWorker` — the template to copy):
```python
# Source: musicstreamer/ui_qt/import_dialog.py:75-101 [VERIFIED: codebase]
class _YtScanWorker(QThread):
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, url, toast_callback=None, *, node_runtime=None, parent=None):
        super().__init__(parent)
        self._url = url
        self._toast = toast_callback
        self._node_runtime = node_runtime

    def run(self):
        try:
            results = yt_import.scan_playlist(
                self._url,
                toast_callback=self._toast,
                node_runtime=self._node_runtime,
            )
            self.finished.emit(results)
        except Exception as exc:
            self.error.emit(str(exc))
```
The new `_LiveRefreshScanWorker` is a copy of this with the same `node_runtime` threading discipline.

### Pattern 3: Provider Right-Click Context Menu
**What:** In `_on_tree_context_menu`, the current code does `if station is None: return` for non-station rows. To add a provider menu, add a branch BEFORE the early return:
```python
# Source: musicstreamer/ui_qt/station_list_panel.py:682-694 [VERIFIED: codebase]
def _on_tree_context_menu(self, pos) -> None:
    index = self.tree.indexAt(pos)
    if not index.isValid():
        return
    source_idx = self._proxy.mapToSource(index)
    # NEW: detect provider row via internalPointer().kind
    node = source_idx.internalPointer()
    if node is not None and node.kind == "provider":
        # provider context menu -- NEW
        menu = QMenu(self)
        refresh_action = menu.addAction("Refresh live streams…")
        action = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if action is refresh_action:
            self.provider_refresh_requested.emit(
                node.provider_id,        # requires _TreeNode.provider_id (NEW)
                node.provider_name,
            )
        return
    station = self.model.station_for_index(source_idx)
    if station is None:
        return
    # ... existing station menu ...
```
This requires (a) adding `provider_id: Optional[int] = None` to `_TreeNode` and (b) populating it in `_populate()` from `station.provider_id`.

### Pattern 4: Dedicated Single-Column UPDATE Methods
**What:** New columns are updated via dedicated repo methods (not routed through `update_station`) to avoid silent-reset of other columns. Established precedent from Phase 89.
**Example** (from `repo.py:951-963`, the template):
```python
# Source: musicstreamer/repo.py:951-963 [VERIFIED: codebase]
def update_channel_avatar_path(self, station_id: int, path: Optional[str]) -> None:
    """Not routed through update_station to avoid silent-reset of avatar on saves
    that don't touch the avatar column (RESEARCH.md Pitfall 5)."""
    self.con.execute(
        "UPDATE stations SET channel_avatar_path = ? WHERE id = ?",
        (path, station_id),
    )
    self.con.commit()
```
Phase 96 adds:
- `repo.set_live_url_syncs_from_channel(station_id: int, value: bool)` 
- `repo.set_live_url_title_anchor(station_id: int, title: Optional[str])`
- `repo.set_provider_channel_scan_url(provider_id: int, url: Optional[str])`
- `repo.list_stations_for_provider(provider_id: int) -> list[Station]` (new query method)
- `repo.list_flagged_stations_for_provider(provider_id: int) -> list[Station]` (new query method — stations WHERE provider_id=? AND live_url_syncs_from_channel=1)

### Pattern 5: YouTube URL Gating in EditStationDialog
**What:** The Refresh avatar button is enabled/disabled based on YouTube URL detection at `edit_station_dialog.py:1289-1295`. The flag checkbox must mirror this exactly.
```python
# Source: musicstreamer/ui_qt/edit_station_dialog.py:1289-1295 [VERIFIED: codebase]
url = self.url_edit.text().strip()
lower = url.lower()
is_yt = "youtube.com" in lower or "youtu.be" in lower
is_twitch = "twitch.tv" in lower
self._refresh_avatar_btn.setEnabled(is_yt or is_twitch)
```
For Phase 96: the flag checkbox is enabled ONLY when `is_yt` is True (NOT Twitch — YouTube-only per D-02). The companion scan-URL field (`QLineEdit`, placeholder: `https://youtube.com/@Channel/streams`) is shown/enabled only when the checkbox is enabled and checked.

### Anti-Patterns to Avoid
- **Auto-applying via title match:** Explicitly forbidden by D-05. Even if a scan result title exactly matches the stored anchor, do NOT automatically update the URL. The anchor only pre-orders the dropdown.
- **Routing flag/anchor updates through `update_station()`:** `update_station` does not include the new columns in its SET clause; calling it after setting the flag would NOT save the flag. Use dedicated setters (Pattern 4).
- **Starting `_LiveRefreshScanWorker` without `node_runtime`:** See Landmine below — always pass `node_runtime` even when `NodeRuntime.available` is False (the worker handles the missing-node path internally via `scan_playlist`'s opts).
- **Calling `repo.station_exists_by_url(new_url)` before updating:** The update-in-place path must bypass this check. The refresh workflow explicitly maps an old station to a new URL; dedup by URL would block the update.
- **Storing the channel handle (@handle) instead of the full /streams URL:** `is_yt_playlist_url()` recognizes `youtube.com/@Channel/streams` — use the full URL as the canonical scan key stored in `providers.channel_scan_url`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YouTube channel scan | Custom yt-dlp invocation | `yt_import.scan_playlist(url, node_runtime=...)` (yt_import.py:47-125) | Handles cookies corruption, node_runtime, extract_flat, live-status filtering — already battle-tested |
| Off-UI-thread network | Direct blocking call on main thread | `_LiveRefreshScanWorker(QThread)` mirroring `_YtScanWorker` (import_dialog.py:75-101) | PySide6 will freeze the UI; QThread+Signal is the project-standard pattern |
| Live-status filtering | Re-implementing `_entry_is_live` | Use `scan_playlist`'s built-in filtering | `_entry_is_live` handles `live_status == "is_live"` AND the sparse `is_live = True` fallback correctly |
| URL validation | Hand-rolled regex | `"youtube.com" in lower or "youtu.be" in lower` (edit_station_dialog.py:1293-1294) | Exact pattern already used project-wide; no new gate needed |
| Schema migration | Table rebuild | `ALTER TABLE ... ADD COLUMN` + `try/except OperationalError` | Established pattern in `db_init()` (repo.py:164-334); rebuild path is only needed for DROP COLUMN (legacy url removal) |

**Key insight:** `scan_playlist` is a drop-in refresh enumerator. The only new infrastructure is the dialog + context-menu wiring + persistence path. No custom yt-dlp integration needed.

---

## Data Model: New Schema Additions

### stations table additions

```sql
-- D-01 flag: per-station opt-in for live URL re-sync
ALTER TABLE stations ADD COLUMN live_url_syncs_from_channel INTEGER NOT NULL DEFAULT 0;
-- D-03 title anchor: stores the YouTube title at flag-set (or last successful re-sync)
ALTER TABLE stations ADD COLUMN live_url_title_anchor TEXT;
```

- `live_url_syncs_from_channel`: INTEGER (0/1 boolean), NOT NULL DEFAULT 0. Existing rows get 0 (OFF) automatically.
- `live_url_title_anchor`: TEXT, nullable, no DEFAULT. NULL means "anchor not set yet" (flag may be ON but anchor not captured).

### providers table addition

```sql
-- D-04: channel scan URL used by the "Refresh live streams" action
ALTER TABLE providers ADD COLUMN channel_scan_url TEXT;
```

- `channel_scan_url`: TEXT, nullable, no DEFAULT. Populated when the user sets the flag on a station belonging to this provider. Must be a YouTube `@Channel/streams` or `playlist?list=` URL (validated by `is_yt_playlist_url` before storing).

### Station and Provider model updates

`models.py`:
```python
# Station dataclass additions (append after existing fields)
live_url_syncs_from_channel: bool = False   # Phase 96 D-01
live_url_title_anchor: Optional[str] = None  # Phase 96 D-03
```

```python
# Provider dataclass addition
channel_scan_url: Optional[str] = None      # Phase 96 D-04
```

All `get_station`, `list_stations`, `list_recently_played` queries in `repo.py` must be updated to SELECT the two new `stations` columns and populate the dataclass. `list_providers` must SELECT `channel_scan_url` and return it in `Provider`. [VERIFIED: pattern from repo.py:641-673, 682-712, 800-825, 477-479]

### Canonical URL field for YouTube stations

The canonical live URL is `station_streams` row with `position=1`. `station_exists_by_url(url)` queries `station_streams.url` (repo.py:880-884). The refresh update-in-place path calls `repo.update_stream(stream_id=first_stream.id, url=new_url, ...)` where `first_stream = repo.list_streams(station_id)[0]` (sorted by position). This is exactly how `EditStationDialog._on_save` persists URL changes (edit_station_dialog.py:1814-1815). [VERIFIED: codebase]

---

## Critical Code Paths

### 1. Update-in-place: bypassing station_exists_by_url

`import_stations` (yt_import.py:128-152) skips any entry whose URL already exists in `station_streams`. The refresh path MUST NOT call `import_stations`. Instead:

```python
# Refresh path: update position-1 stream in-place
streams = repo.list_streams(station_id)  # sorted by position (repo.py:490-498)
primary = next((s for s in streams if s.position == 1), None)
if primary:
    repo.update_stream(
        stream_id=primary.id,
        url=new_url,
        label=primary.label,     # preserve existing label
        quality=primary.quality,  # preserve existing quality
        position=1,
        stream_type=primary.stream_type,  # preserve stream_type
        codec=primary.codec,
        bitrate_kbps=primary.bitrate_kbps,
        sample_rate_hz=primary.sample_rate_hz,
        bit_depth=primary.bit_depth,
    )
```

The `update_stream` signature at `repo.py:564-572` takes all fields positionally. Preserve all existing fields except `url` to avoid silent data loss. [VERIFIED: codebase]

After the URL update, also update the title anchor:
```python
repo.set_live_url_title_anchor(station_id, new_title_from_scan)
```

### 2. Node-runtime threading (LANDMINE)

`check_node()` (`runtime_check.py:109-116`) is called at app startup (`__main__.py:312`) and returns a `NodeRuntime(available: bool, path: Optional[str])`. The result is stored on `MainWindow._node_runtime` and passed to dialog constructors.

`_LiveRefreshScanWorker` receives `node_runtime` in `__init__` and passes it to `scan_playlist`:
```python
# Source: mirroring import_dialog.py:84-101 [VERIFIED: codebase]
def run(self):
    try:
        results = yt_import.scan_playlist(
            self._channel_scan_url,
            node_runtime=self._node_runtime,  # CRITICAL: must thread through
        )
        self.finished.emit(results)
    except ValueError as exc:
        self.error.emit(str(exc))
    except RuntimeError as exc:
        self.error.emit(str(exc))
```

`LiveRefreshDialog` receives `node_runtime` from `StationListPanel`, which receives it from `MainWindow`. The wiring chain:
```
__main__.py: node_runtime = check_node()
  -> MainWindow.__init__(node_runtime=...)
  -> StationListPanel.__init__(node_runtime=...)  [NEW: must add this param]
  -> LiveRefreshDialog.__init__(node_runtime=...)
  -> _LiveRefreshScanWorker.__init__(node_runtime=...)
  -> scan_playlist(node_runtime=...)
```

Currently `StationListPanel` does NOT receive `node_runtime`. This must be added. Check `main_window.py` where `StationListPanel` is constructed to confirm the constructor call site (`main_window.py:1321`). [VERIFIED: codebase — node_runtime is passed to ImportDialog at L1560 but NOT to StationListPanel today]

### 3. Provider context-menu detection

`_TreeNode` (station_tree_model.py:30-36) currently has: `kind`, `label`, `parent`, `children`, `station`, `provider_name`. It does NOT have `provider_id`.

Two changes needed:

**Change A** — Add `provider_id: Optional[int] = None` to `_TreeNode` dataclass (station_tree_model.py:30-36).

**Change B** — Populate it in `_populate()` (station_tree_model.py:209-233):
```python
# Source: station_tree_model.py:209-233 [VERIFIED: codebase]
for st in stations:
    pname = st.provider_name or "Ungrouped"
    grp = groups.get(pname)
    if grp is None:
        grp = _TreeNode(
            kind="provider",
            label=pname,
            parent=self._root,
            provider_name=pname,
            provider_id=st.provider_id,  # NEW — take from first station of this group
        )
        ...
```

Note: `st.provider_id` is `Optional[int]`. Ungrouped stations have `provider_id=None`. The context menu action must check `node.provider_id is not None` before opening the dialog (stations with no provider have no channel to re-scan).

**Change C** — Add a new signal to `StationListPanel`:
```python
provider_refresh_requested = Signal(int, str, str)  # provider_id, provider_name, channel_scan_url
```

**Change D** — Branch in `_on_tree_context_menu`:
```python
node = source_idx.internalPointer()
if node is not None and node.kind == "provider":
    # Only show menu if provider_id is not None AND provider has a channel_scan_url
    # (check via repo.get_provider_channel_scan_url or pass through model)
    ...
```

Alternative: show the menu always for provider rows, but the dialog handles the "no channel_scan_url" case with an error/prompt.

### 4. Channel scan URL: storage and derivation

When a user sets the flag on a station, the channel scan URL must be associated with the station's provider. This is the trickiest UX decision (Claude's Discretion area).

**Recommended approach:** Add a companion QLineEdit in `EditStationDialog` below the flag checkbox:
- Label: "Channel URL for refresh scan:"
- Placeholder: `https://youtube.com/@Channel/streams`
- Enabled only when the flag checkbox is checked
- Pre-populated from `self._station.provider?.channel_scan_url` if already set

At `_on_save()` time, if the flag is checked AND the companion URL is non-empty AND `is_yt_playlist_url(companion_url)` is True, call:
```python
repo.set_provider_channel_scan_url(station.provider_id, companion_url)
```

This approach avoids any async network call at flag-set time and lets the user supply the channel URL once per provider (subsequent stations of the same provider will pre-populate from the stored value).

**Title anchor at flag-set time:** The anchor is "the stream's current YouTube title." This is the station's existing `.name` (or the primary `StationStream`'s label if set). At flag-check time in `_on_save`, store:
```python
anchor = repo.list_streams(station.id)[0].label or station.name
repo.set_live_url_title_anchor(station.id, anchor)
```

This avoids a network call at flag-set time while still capturing a useful anchor.

---

## Common Pitfalls

### Pitfall 1: Routing flag/anchor updates through update_station()

**What goes wrong:** `update_station()` has an explicit `SET ... WHERE id = ?` that does NOT include `live_url_syncs_from_channel` or `live_url_title_anchor`. Adding the flag to `_on_save()` without a dedicated setter silently loses the value every time the station is saved without explicit column handling.

**Why it happens:** `update_station()` is a 7-positional-arg legacy method; adding another positional arg risks breaking the ~5 existing call sites.

**How to avoid:** Use dedicated single-column setters (`set_live_url_syncs_from_channel`, `set_live_url_title_anchor`) following the Phase 89A pattern for `update_channel_avatar_path` (repo.py:951-963).

**Warning signs:** Flag checkbox in EditStationDialog saves but value is 0 on re-open.

### Pitfall 2: Forgetting list_stations / get_station SELECT updates

**What goes wrong:** The new `stations` columns are present in the DB but are not SELECTed in `list_stations`, `get_station`, `list_recently_played`, and `list_favorite_stations`. The `Station` dataclass fields exist but are always None/False.

**Why it happens:** Four separate `SELECT s.*, ...` queries in `repo.py` all need updating (L641-673, L682-712, L800-825, L911-942).

**How to avoid:** After adding the ALTER TABLE blocks in `db_init()`, immediately update all four Station-building queries to read `r["live_url_syncs_from_channel"]` and `r["live_url_title_anchor"]`.

**Warning signs:** Flag appears checked in UI but `get_station(id).live_url_syncs_from_channel` is False.

### Pitfall 3: scan_playlist called without node_runtime from LiveRefreshDialog

**What goes wrong:** Under GNOME `.desktop` launchers, `PATH` is stripped. `scan_playlist` with `node_runtime=None` tries `yt_dlp_opts.build_js_runtimes(None)`, which results in no JS runtime path. YouTube extraction fails for any URL that requires the EarlyJS challenge (most YT URLs post-2025).

**Why it happens:** `StationListPanel` currently does NOT accept or store `node_runtime` — it is only passed to `ImportDialog` and `EditStationDialog` from `MainWindow`. If `LiveRefreshDialog` is opened from `StationListPanel` without threading `node_runtime` through, the scan silently fails or falls back.

**How to avoid:** Add `node_runtime` parameter to `StationListPanel.__init__()` and store it. Pass it to `LiveRefreshDialog.__init__()`. Pass it to `_LiveRefreshScanWorker.__init__()`.

**Warning signs:** "Scan failed: ..." error in `LiveRefreshDialog` only when launched from a `.desktop` launcher, works fine from terminal.

### Pitfall 4: _TreeNode.provider_id is None for Ungrouped stations

**What goes wrong:** Stations with `provider_id=None` (ungrouped) are grouped under "Ungrouped" in the tree. If you add a context menu for all provider rows, right-clicking "Ungrouped" would try to open `LiveRefreshDialog(provider_id=None, ...)` which would be invalid.

**Why it happens:** `_TreeNode._populate()` takes `provider_id=st.provider_id` from the first station in the group; if all stations in "Ungrouped" have `provider_id=None`, the provider node also has `provider_id=None`.

**How to avoid:** Gate the context menu action on `node.provider_id is not None`. Either hide the "Refresh live streams" action for the Ungrouped provider, or show it disabled.

**Warning signs:** `LiveRefreshDialog` crashes or shows an empty station list when "Ungrouped" is right-clicked.

### Pitfall 5: update_stream preserves all non-URL fields

**What goes wrong:** `repo.update_stream` takes all stream fields. If the apply path only updates `url` and zeros out `label`, `quality`, `stream_type`, `codec`, etc., the user's existing stream metadata is silently lost.

**Why it happens:** `update_stream` (repo.py:564-572) is a full-row replace — it does not support partial updates.

**How to avoid:** Fetch the existing `StationStream` first, then pass all existing field values through to `update_stream` except `url` (which gets the new value). Follow the pattern in `EditStationDialog._on_save` (edit_station_dialog.py:1783-1815) which reads `existing_streams[stream_id]` before calling `update_stream`.

**Warning signs:** Station loses its quality/codec metadata after a refresh apply.

### Pitfall 6: station_exists_by_url blocks update-in-place

**What goes wrong:** If the refresh apply path calls `station_exists_by_url(new_url)` as a guard before updating, it will find a False result for a new (churned) URL and try to `insert_station` — creating a duplicate instead of updating the existing station.

**Why it happens:** `import_stations` (yt_import.py:140) uses `station_exists_by_url` for dedup. This is correct for import but wrong for refresh.

**How to avoid:** The refresh apply path NEVER calls `station_exists_by_url`. It directly calls `update_stream(stream_id=primary.id, url=new_url, ...)`.

### Pitfall 7: is_yt_playlist_url rejects watch?v= URLs for gating

**What goes wrong:** The flag checkbox in `EditStationDialog` is gated on "is the station's URL a YouTube URL" (D-02). The existing `is_yt_playlist_url()` only recognizes `@Channel/streams` and `playlist?list=` URLs — NOT `watch?v=` URLs (watch URLs are individual video URLs, not playlists). Most YBC-type stations have a `watch?v=` URL as their primary stream URL.

**Why it happens:** Confusion between "is this URL a YouTube channel to scan from?" (uses `is_yt_playlist_url`) and "is this station's stream URL a YouTube URL?" (uses `"youtube.com" in lower`).

**How to avoid:** Gate the checkbox using `"youtube.com" in lower or "youtu.be" in lower` (the same check used for the avatar Refresh button at edit_station_dialog.py:1293-1294), NOT `is_yt_playlist_url()`. The channel_scan_url companion field is validated with `is_yt_playlist_url()` separately.

### Pitfall 8: Migration ordering — new columns must land AFTER the URL-column rebuild block

**What goes wrong:** The legacy URL-column rebuild in `db_init()` (repo.py:208-265) uses `CREATE TABLE stations_new / INSERT SELECT ... FROM stations` which does NOT carry dynamically-added columns. If the Phase 96 `ALTER TABLE` blocks are placed BEFORE the rebuild block, they land on the OLD `stations` table and are lost during the rebuild.

**Why it happens:** The rebuild block's `CREATE TABLE stations_new` hardcodes the column list. Any column added to `stations` AFTER the initial schema but BEFORE the rebuild is silently dropped.

**How to avoid:** Place all three Phase 96 `ALTER TABLE` blocks AFTER line 265 (the rebuild block's `except sqlite3.OperationalError: pass`), following the Phase 73/82/83/89A/89.1 comment chain. The existing comments at repo.py:267-334 explicitly document this requirement. [VERIFIED: codebase]

---

## Runtime State Inventory

> Rename/refactor/migration phase? NO — this is a feature addition. No runtime state inventory needed.

None — verified by reading CONTEXT.md (no rename/refactor scope). Out of scope: skip entirely.

---

## Code Examples

### Adding live_url_syncs_from_channel and live_url_title_anchor migrations

```python
# Source: musicstreamer/repo.py (additive, after line 334) [VERIFIED: codebase pattern]
# Phase 96 D-01 — per-station opt-in flag; INTEGER NOT NULL DEFAULT 0;
# existing rows default to 0 (OFF). MUST land after the URL-column rebuild block.
try:
    con.execute(
        "ALTER TABLE stations ADD COLUMN live_url_syncs_from_channel INTEGER NOT NULL DEFAULT 0"
    )
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists — idempotent

# Phase 96 D-03 — title anchor; nullable TEXT no DEFAULT.
# NULL means flag is ON but anchor not yet captured.
try:
    con.execute("ALTER TABLE stations ADD COLUMN live_url_title_anchor TEXT")
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists — idempotent

# Phase 96 D-04 — per-provider channel scan URL; nullable TEXT no DEFAULT.
# providers table has NO legacy rebuild block (confirmed by grep: zero 'providers_new' hits).
try:
    con.execute("ALTER TABLE providers ADD COLUMN channel_scan_url TEXT")
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists — idempotent
```

### list_flagged_stations_for_provider — new Repo method

```python
# New method in musicstreamer/repo.py
def list_flagged_stations_for_provider(self, provider_id: int) -> list[Station]:
    """Return all stations belonging to provider_id that have live_url_syncs_from_channel=1.
    
    Phase 96 D-04: scopes the LiveRefreshDialog to only the flagged stations.
    Returns full Station objects (with streams) so the dialog can display current URLs.
    """
    rows = self.con.execute(
        """
        SELECT s.*, p.name AS provider_name, p.avatar_path AS provider_avatar_path
        FROM stations s
        LEFT JOIN providers p ON p.id = s.provider_id
        WHERE s.provider_id = ?
          AND s.live_url_syncs_from_channel = 1
        ORDER BY s.name COLLATE NOCASE
        """,
        (provider_id,),
    ).fetchall()
    return [
        Station(
            id=r["id"],
            name=r["name"],
            provider_id=r["provider_id"],
            provider_name=r["provider_name"],
            tags=r["tags"] or "",
            station_art_path=r["station_art_path"],
            album_fallback_path=r["album_fallback_path"],
            icy_disabled=bool(r["icy_disabled"]),
            cover_art_source=r["cover_art_source"] or "auto",
            last_played_at=r["last_played_at"],
            is_favorite=bool(r["is_favorite"]),
            preferred_stream_id=r["preferred_stream_id"],
            streams=self.list_streams(r["id"]),
            prerolls=self.list_prerolls(r["id"]),
            prerolls_fetched_at=r["prerolls_fetched_at"],
            channel_avatar_path=r["channel_avatar_path"],
            provider_avatar_path=r["provider_avatar_path"],
            live_url_syncs_from_channel=bool(r["live_url_syncs_from_channel"]),  # Phase 96
            live_url_title_anchor=r["live_url_title_anchor"],                     # Phase 96
        )
        for r in rows
    ]
```

### Flag checkbox gating in EditStationDialog._on_url_text_changed

```python
# Source: mirroring edit_station_dialog.py:1289-1295 [VERIFIED: codebase]
# Add to _on_url_text_changed() after the existing avatar gate:
url = self.url_edit.text().strip()
lower = url.lower()
is_yt = "youtube.com" in lower or "youtu.be" in lower
# Phase 96 D-02: flag checkbox enabled ONLY for YouTube URLs (not Twitch)
self._live_resync_checkbox.setEnabled(is_yt)
if not is_yt:
    self._live_resync_checkbox.setChecked(False)
# Companion scan-URL field shown only when checkbox is enabled and checked
self._live_resync_channel_url_edit.setVisible(
    is_yt and self._live_resync_checkbox.isChecked()
)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| station_exists_by_url dedup (import) | KEPT for import; bypassed for refresh (update_stream direct) | Phase 96 NEW | Refresh path updates in-place; import still dedupes |
| Provider rows non-actionable in sidebar | Provider right-click opens LiveRefreshDialog | Phase 96 NEW | First user-actionable provider-row feature |
| No channel URL stored on provider | providers.channel_scan_url (additive migration) | Phase 96 NEW | Enables channel re-scan without user re-entering URL |
| No per-station live-churn flag | stations.live_url_syncs_from_channel + .live_url_title_anchor | Phase 96 NEW | Opt-in per station; default OFF keeps most stations unaffected |

**Deprecated/outdated:**
- `import_stations()` is NOT deprecated — it remains the correct path for first-time import. The refresh path is additive, not a replacement.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `StationListPanel.__init__()` does not currently receive `node_runtime` | Architecture Patterns / Pitfall 3 | Low — confirmed by grep that node_runtime is passed to ImportDialog and EditStationDialog but NOT to StationListPanel (main_window.py:1321) |
| A2 | `providers` table has no legacy rebuild block (safe to add ALTER TABLE after the stations rebuild block without ordering concern) | Code Examples | Low — confirmed by grep for "providers_new" in repo.py returning 0 results |
| A3 | The `_TreeNode.internalPointer()` access is valid and safe to call from `_on_tree_context_menu` | Architecture Patterns / Pattern 3 | Low — the proxy model's `mapToSource` produces a valid source index; the model only creates indices via `createIndex(row, 0, node)` so `internalPointer()` always returns a `_TreeNode` for valid indices |
| A4 | Channel scan URL stored per-provider (not per-station) is the right grouping key | Architecture Patterns | Medium — if a provider has two separate YouTube channels (unusual), a per-provider URL is wrong. For YBC/CafeBGM pattern (one channel per provider), it's correct. The EditStationDialog companion field allows the user to override. |

---

## Open Questions (RESOLVED)

1. **Channel scan URL derivation: user-supplied vs. async-resolved?**
   - What we know: The channel scan URL (`@Channel/streams`) is not stored today. It can be entered by the user or auto-resolved from a `watch?v=` URL via yt-dlp (which extracts `channel_url`/`uploader_url`).
   - What's unclear: D-03 says to capture the title anchor at flag-set time but doesn't specify whether the scan URL is also resolved automatically then.
   - Recommendation: Use the user-supplied companion field approach (no async call at flag-set time). It's simpler, avoids a second yt-dlp call during `EditStationDialog`, and the user importing from a channel already knows their channel URL.
   - RESOLVED: Channel scan URL is a user-supplied companion field in EditStationDialog (no async yt-dlp resolution at flag-set time). Enacted by Plan 03 (companion field + `set_provider_channel_scan_url`) and consumed by Plan 05 (`channel_scan_url` resolved from `repo.list_providers()` at refresh time).

2. **Provider context menu on Ungrouped stations**
   - What we know: Stations with no provider have `provider_id=None` and group under "Ungrouped" in the tree.
   - What's unclear: Should right-clicking "Ungrouped" show a disabled "Refresh live streams" item, or no menu at all?
   - Recommendation: Show no menu for the Ungrouped provider row (gate on `node.provider_id is not None`). Ungrouped YouTube stations are an edge case; the user can set a provider first via EditStationDialog.
   - RESOLVED: Ungrouped / null-provider rows get NO context menu at all (the provider branch in `_on_tree_context_menu` gates on `node.provider_id is not None`). Enacted by Plan 05 Task 1 and guarded by the Plan 01 `test_tree_node_carries_provider_id` Ungrouped assertion.

3. **What happens when flagged_stations_for_provider returns empty?**
   - What we know: The user can right-click any provider, not just YouTube providers with flagged stations.
   - What's unclear: D-04 doesn't specify the UX for a provider with no flagged stations.
   - Recommendation: Show a toast or dialog message: "No stations in this provider are marked for live URL re-sync. Enable the flag on a station via Edit Station."
   - RESOLVED: An empty `list_flagged_stations_for_provider` result shows an informational toast ("No stations marked for live URL re-sync — enable the flag via Edit Station") and opens nothing. Enacted by Plan 04 Task 1 (empty-flagged message path) and Plan 05's empty-flagged guard.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python `.venv` | All code | ✓ | 3.14.4 | — |
| pytest | Tests | ✓ | 9.0.3 | — |
| PySide6 | UI | ✓ | 6.11+ (project pinned) | — |
| yt_dlp | scan_playlist | ✓ | 2026.x (project pinned) | — |
| sqlite3 | Repo migrations | ✓ | stdlib | — |
| node.js | YT JS extraction | ✓ (resolved via check_node at startup) | system-dependent | NodeRuntime.available=False degrades gracefully (yt-dlp errors propagated to user) |

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | `pyproject.toml` (project root) |
| Quick run command | `.venv/bin/python -m pytest tests/test_repo.py tests/test_live_refresh_dialog.py -x` |
| Full suite command | `.venv/bin/python -m pytest tests/ -x --ignore=tests/integration` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| D-01 | `live_url_syncs_from_channel` column present; DEFAULT 0; idempotent migration | unit | `.venv/bin/python -m pytest tests/test_repo.py::test_live_url_syncs_from_channel_migration_idempotent -x` | ❌ Wave 0 |
| D-01 | `set_live_url_syncs_from_channel` round-trips correctly | unit | `.venv/bin/python -m pytest tests/test_repo.py::test_live_url_syncs_from_channel_round_trip -x` | ❌ Wave 0 |
| D-01 | `Station.live_url_syncs_from_channel` loaded by `get_station`/`list_stations` | unit | `.venv/bin/python -m pytest tests/test_repo.py::test_station_live_flag_loaded_from_db -x` | ❌ Wave 0 |
| D-02 | Checkbox enabled for `youtube.com` URL, disabled for `twitch.tv`, disabled for other | unit | `.venv/bin/python -m pytest tests/test_edit_station_dialog.py::test_live_resync_checkbox_gating -x` | ❌ Wave 0 |
| D-03 | `live_url_title_anchor` column present; nullable; idempotent | unit | `.venv/bin/python -m pytest tests/test_repo.py::test_live_url_title_anchor_migration_idempotent -x` | ❌ Wave 0 |
| D-03 | `set_live_url_title_anchor` persists and is loaded by `get_station` | unit | `.venv/bin/python -m pytest tests/test_repo.py::test_live_url_title_anchor_round_trip -x` | ❌ Wave 0 |
| D-04 | `providers.channel_scan_url` column present; nullable; idempotent | unit | `.venv/bin/python -m pytest tests/test_repo.py::test_provider_channel_scan_url_migration_idempotent -x` | ❌ Wave 0 |
| D-04 | `_TreeNode` carries `provider_id`; provider context-menu branch fires | unit | `.venv/bin/python -m pytest tests/test_station_tree_model.py::test_tree_node_carries_provider_id -x` | ❌ Wave 0 |
| D-05 | `_build_row_suggestions` pre-orders by title-anchor similarity, does NOT auto-apply | unit | `.venv/bin/python -m pytest tests/test_live_refresh_dialog.py::test_suggestions_pre_order_no_auto_apply -x` | ❌ Wave 0 |
| D-06 | Update remap: `update_stream` called with new URL; other fields preserved | unit | `.venv/bin/python -m pytest tests/test_live_refresh_dialog.py::test_apply_remap_preserves_metadata -x` | ❌ Wave 0 |
| D-07 | Drop action calls `delete_station`; add action calls `insert_station` with flag=True | unit | `.venv/bin/python -m pytest tests/test_live_refresh_dialog.py::test_apply_drop_and_add_actions -x` | ❌ Wave 0 |
| D-08 | Editable name field pre-populated correctly for each action type | unit | `.venv/bin/python -m pytest tests/test_live_refresh_dialog.py::test_name_field_prepopulation -x` | ❌ Wave 0 |
| D-09 | Scan runs off UI thread (QThread); dialog populated on main thread via Signal | unit | `.venv/bin/python -m pytest tests/test_live_refresh_dialog.py::test_scan_worker_uses_qthread -x` | ❌ Wave 0 |
| D-10 | Unresolved flagged stations untouched; drops/adds unchecked by default | unit | `.venv/bin/python -m pytest tests/test_live_refresh_dialog.py::test_conservative_defaults -x` | ❌ Wave 0 |
| D-10 | Summary shown before Apply commits | manual UAT | n/a | n/a |
| D-01..D-10 | Real YBC channel re-sync: flag station, right-click provider, scan, apply remap | manual UAT | n/a | n/a |
| D-06 | `list_flagged_stations_for_provider` returns only flagged stations | unit | `.venv/bin/python -m pytest tests/test_repo.py::test_list_flagged_stations_for_provider -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/python -m pytest tests/test_repo.py -x -q`
- **Per wave merge:** `.venv/bin/python -m pytest tests/ -x --ignore=tests/integration -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_live_refresh_dialog.py` — new file; covers D-05/D-06/D-07/D-08/D-09/D-10
- [ ] `tests/test_repo.py` additions — D-01/D-03/D-04 migration idempotency + round-trip tests + `list_flagged_stations_for_provider` test
- [ ] `tests/test_station_tree_model.py` additions — `_TreeNode.provider_id` test + provider context-menu detection test
- [ ] `tests/test_edit_station_dialog.py` additions — D-02 flag gating test

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | n/a (local desktop app, no auth layer) |
| V3 Session Management | no | n/a |
| V4 Access Control | no | n/a |
| V5 Input Validation | yes | `is_yt_playlist_url()` on channel scan URL before storing/scanning; title length cap before storing anchor |
| V6 Cryptography | no | n/a |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious/oversized title from yt-dlp scan result | Tampering | Cap `live_url_title_anchor` at e.g. 500 chars before persisting; parameterized SQL already in use |
| Non-YouTube URL injected into `providers.channel_scan_url` | Tampering | Validate with `is_yt_playlist_url(url)` before `repo.set_provider_channel_scan_url()` — same gate as import flow |
| Arbitrary URL scan via user-supplied channel_scan_url field | SSRF (limited) | Desktop app; user controls their own data. The URL is passed to yt-dlp (which handles network), not to urllib directly. Acceptable risk for a user-trusted field. |
| Auto-deletion of flagged stations without user confirmation | Elevation of Privilege | D-10 conservative defaults: drops are explicitly opt-in (unchecked by default); no delete fires without explicit tick. |
| Station names clobbered silently by refresh | Tampering | D-08: name field is editable per row and pre-filled with EXISTING name (for remaps), not the channel title. User must explicitly change it. |
| `station_exists_by_url` bypassed for update-in-place | Spoofing | The refresh update is to an explicit `stream_id` (integer FK), not a URL-keyed INSERT. The risk is a user mapping a wrong stream to a wrong station — mitigated by D-05 (manual map, review-and-confirm). |

---

## Sources

### Primary (HIGH confidence)
- `musicstreamer/repo.py` — All migration patterns, `update_stream`, `insert_station`, `station_exists_by_url`, `update_station`, existing additive-column precedent [VERIFIED: codebase]
- `musicstreamer/yt_import.py` — `scan_playlist`, `import_stations`, `_entry_is_live`, `is_yt_playlist_url`, `fetch_channel_avatar` (two-step channel resolution) [VERIFIED: codebase]
- `musicstreamer/ui_qt/station_tree_model.py` — `_TreeNode`, `_populate()`, `station_for_index`, `provider_name_at` [VERIFIED: codebase]
- `musicstreamer/ui_qt/station_list_panel.py` — `_on_tree_context_menu`, existing station-only menu, `edit_requested` signal [VERIFIED: codebase]
- `musicstreamer/ui_qt/import_dialog.py` — `_YtScanWorker` (the exact template to copy), `_on_yt_scan_complete`, YouTube tab flow [VERIFIED: codebase]
- `musicstreamer/ui_qt/edit_station_dialog.py` — `_AvatarFetchWorker`, `_on_refresh_avatar_clicked`, YouTube/Twitch URL gate (L1289-1295), `_on_save` stream update path [VERIFIED: codebase]
- `musicstreamer/runtime_check.py` — `check_node()`, `NodeRuntime` dataclass [VERIFIED: codebase]
- `musicstreamer/models.py` — `Station`, `Provider`, `StationStream` dataclasses [VERIFIED: codebase]
- `96-CONTEXT.md` — D-01..D-10 behavioral contract [VERIFIED: file]

### Secondary (MEDIUM confidence)
- `tests/test_repo.py` — Migration idempotency test patterns for new tests to mirror [VERIFIED: codebase]
- `tests/test_station_tree_model.py` — Provider node test patterns [VERIFIED: codebase]

### Tertiary (LOW confidence)
- None.

---

## Metadata

**Confidence breakdown:**
- Schema additions: HIGH — exact migration pattern is established and verified in codebase
- Update-in-place path: HIGH — `update_stream` API is clear; bypass strategy for `station_exists_by_url` is straightforward
- Context-menu wiring: HIGH — `_TreeNode.internalPointer()` access pattern is direct; `provider_id` addition is minimal
- Worker/dialog structure: HIGH — `_YtScanWorker` is a direct template; `LiveRefreshDialog` parallels `import_dialog.py` YouTube tab
- Node-runtime threading: HIGH — established pattern, only gap is `StationListPanel` not receiving `node_runtime` yet
- Channel scan URL derivation: MEDIUM — Claude's Discretion area; recommended user-supplied companion field approach avoids async complexity

**Research date:** 2026-06-20
**Valid until:** 2026-07-20 (stable project; yt_dlp API changes are the primary expiry risk)
