# Phase 9: Station Editor Improvements — Research

**Researched:** 2026-03-22
**Domain:** GTK4/Adwaita widget APIs, yt-dlp subprocess pattern
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Provider Picker (MGMT-01, MGMT-03)**
- D-01: Replace `self.provider_entry` (Gtk.Entry) with `Adw.ComboRow` — native Adwaita, fits existing form with SwitchRow. Populated from `repo.list_providers()`.
- D-02: Inline creation: user types a new provider name directly in the ComboRow. If the typed value is not in the list, `repo.ensure_provider()` creates it on save. No extra UI (no "New…" option, no "+" button).

**Tag Multi-Select (MGMT-02, MGMT-03)**
- D-03: Replace `self.tags_entry` (comma-separated Gtk.Entry) with a chip panel. Existing tags (from `repo.list_stations()` tag union) are shown as toggleable chips. Clicking a chip adds/removes it. A small text entry below allows typing a new tag not already in the list.
- D-04: Inline creation: user types a new tag name in the entry field. It is appended to the selected set on Enter or save. No extra dialog.

**YouTube Title Auto-Import (MGMT-04)**
- D-05: On URL focus-out, if the URL is a YouTube URL, fetch the stream title via `yt-dlp --print title` (daemon thread + GLib.idle_add, same pattern as thumbnail fetch).
- D-06: Populate the name field ONLY if name is currently empty or equals "New Station". Do not overwrite a name the user has already set.
- D-07: Title fetch and thumbnail fetch can run in parallel on focus-out (both are YouTube URLs). Guard with `_fetch_in_progress` or separate flags if needed.

### Claude's Discretion
- Layout of chip panel within the dialog (above or below a tags label, scrollable or wrapping)
- Whether Adw.ComboRow uses `set_use_subtitle` or a separate label row
- How to handle the case where ComboRow typed value matches an existing entry case-insensitively

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MGMT-01 | Station editor shows existing providers as selectable options (not just freeform text) | Adw.ComboRow with Gtk.StringList — replaces provider_entry at grid row 2 |
| MGMT-02 | Station editor shows existing genres/tags as selectable options with multi-select | Chip panel (Gtk.ToggleButton in Gtk.Box) — same pattern as filter bar in main_window.py |
| MGMT-03 | User can add a new provider or genre/tag inline from the station editor | ComboRow typed value + tags Gtk.Entry below chip panel |
| MGMT-04 | YouTube station URL auto-imports the stream title into the station name field | `yt-dlp --print title --no-playlist` in daemon thread via GLib.idle_add |
</phase_requirements>

## Summary

Phase 9 replaces three freeform `Gtk.Entry` widgets in `EditStationDialog` with proper selectors and adds YouTube title auto-import. The work is self-contained to `edit_dialog.py` with no schema changes and no new dependencies.

The chip panel for tags mirrors the established pattern in `main_window.py` (`_rebuild_filter_state`, `_make_chip`). The implementation can reuse that approach verbatim — `Gtk.ToggleButton` widgets in a `Gtk.Box`, tracked in a list, wrapped in a `Gtk.ScrolledWindow`. The title fetch follows the exact same daemon-thread + `GLib.idle_add` pattern as `fetch_yt_thumbnail`.

The one new widget is `Adw.ComboRow`. It accepts a `Gtk.StringList` as its model and has a built-in entry for user typing when `set_enable_search(True)` is set. On save, read the typed/selected value via `get_selected_item()` or `get_subtitle()` — the exact accessor depends on whether a selection was made vs. text typed.

**Primary recommendation:** Implement as three sequential tasks — (1) ComboRow provider picker, (2) chip-panel tag multi-select, (3) YouTube title fetch. Each is independently testable and does not affect the others.

## Standard Stack

### Core (already in project)
| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| PyGObject / GTK4 | system | UI framework | Already used throughout |
| Adwaita (libadwaita) | system | Adw.ComboRow | Already used (SwitchRow present) |
| yt-dlp | system | `--print title` subprocess | Already used for thumbnail fetch |

No new dependencies required.

## Architecture Patterns

### Adw.ComboRow for Provider Picker

`Adw.ComboRow` is the standard Adwaita widget for a dropdown picker inside a form. It takes a `Gtk.StringList` as its model.

```python
# Populate ComboRow from existing providers
model = Gtk.StringList()
for p in repo.list_providers():
    model.append(p.name)
self.provider_row = Adw.ComboRow(title="Provider", model=model)
self.provider_row.set_enable_search(True)  # allows typing new values
```

**Reading value on save:**
- If user selected from list: `self.provider_row.get_selected_item().get_string()`
- If user typed a custom value: accessed via the internal search entry text

**Problem:** `Adw.ComboRow` with `set_enable_search(True)` exposes search but does NOT expose the typed text directly as a property — the search entry filters the list but does not return its value via a simple getter.

**Recommended workaround (confirmed pattern):** Connect to the `notify::selected` signal and also keep a reference to the typed text via a `Gtk.Entry` placed below the ComboRow for "new provider" input, OR use `Adw.ComboRow` purely as a selector and put a separate small `Gtk.Entry` (placeholder: "Or type new provider…") below it that is used only when the user wants to create a new one.

**Simpler alternative for discretion:** Use `Adw.EntryRow` with a completion popover, but that is more complex. Instead, use `Adw.ComboRow` for selection of existing providers and a secondary `Gtk.Entry` (hidden/shown conditionally, or always visible and empty by default) for "add new". On save, if the secondary entry has text, that takes precedence; otherwise use the ComboRow selection.

**Simplest viable approach:** Replace `provider_entry` with:
1. `Adw.ComboRow` (model = existing providers, or empty string for "None")
2. Small `Gtk.Entry` below labeled "New provider (leave blank to use selection)"

This is the cleanest approach given `Adw.ComboRow` does not expose typed-search-text as a property.

### Chip Panel for Tag Multi-Select

Reuse the established pattern from `main_window.py` (`_rebuild_filter_state`). The dialog needs:

```python
# Tag state
self._selected_tags: set[str] = set()
self._tag_chip_btns: list[Gtk.ToggleButton] = []
self._rebuilding = False

# Widget structure
tags_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
self._chip_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
chip_scroll = Gtk.ScrolledWindow()
chip_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
chip_scroll.set_min_content_height(36)
chip_scroll.set_child(self._chip_box)
self._new_tag_entry = Gtk.Entry()
self._new_tag_entry.set_placeholder_text("New tag…")
tags_box.append(chip_scroll)
tags_box.append(self._new_tag_entry)
```

Pre-populate `_selected_tags` from the station's current tags on dialog open.

On save, collect tags: `_selected_tags | {text from new_tag_entry if non-empty}`, join comma-separated.

### YouTube Title Fetch

Mirror of `fetch_yt_thumbnail` — change `--print thumbnail` to `--print title`:

```python
def fetch_yt_title(url: str, callback: callable) -> None:
    def _worker():
        try:
            result = subprocess.run(
                ["yt-dlp", "--print", "title", "--no-playlist", url],
                capture_output=True, text=True, timeout=15,
            )
            title = result.stdout.strip()
            GLib.idle_add(callback, title or None)
        except Exception:
            GLib.idle_add(callback, None)
    threading.Thread(target=_worker, daemon=True).start()
```

**Name guard (D-06):**
```python
def _on_title_fetched(self, title):
    if self._fetch_cancelled:
        return
    if title:
        current = self.name_entry.get_text().strip()
        if current in ("", "New Station"):
            self.name_entry.set_text(title)
```

**Parallel fetch flag (D-07):** Use two separate boolean flags — `_thumb_fetch_in_progress` and `_title_fetch_in_progress` — so thumbnail and title can run concurrently without blocking each other. The existing single `_fetch_in_progress` flag must be split.

### Form Grid Integration

Current grid layout (edit_dialog.py):
- Row 0: Name
- Row 1: URL
- Row 2: Provider (`provider_entry` — REPLACE with ComboRow + optional new-provider Entry)
- Row 3: Tags (`tags_entry` — REPLACE with tags_box containing chip_scroll + new_tag_entry)

`Gtk.Grid.attach()` accepts any widget, so the chip panel box can replace `tags_entry` at row 3. The grid will expand vertically to accommodate it.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| Provider dropdown | Custom popup/popover | `Adw.ComboRow` |
| Tag chip toggle state | Manual active tracking | `Gtk.ToggleButton.get_active()` — built-in |
| YouTube title fetch | Custom HTTP scrape | `yt-dlp --print title` (already in project) |

## Common Pitfalls

### Pitfall 1: Adw.ComboRow typed-text access
**What goes wrong:** Calling `get_selected_item().get_string()` returns empty string (or the previously selected item) when the user typed a new value that doesn't match the list. The search text is internal to the widget and not exposed as a property.
**How to avoid:** Keep a separate `Gtk.Entry` for new-provider input. On save, check new-provider entry first; use ComboRow selection only if new-provider entry is empty.

### Pitfall 2: _fetch_in_progress flag blocks parallel fetches
**What goes wrong:** Current guard `if self._fetch_in_progress: return` in `_start_thumbnail_fetch` will prevent title fetch from starting if thumbnail fetch is running (or vice versa).
**How to avoid:** Split into `_thumb_fetch_in_progress` and `_title_fetch_in_progress`. Each fetch checks and sets its own flag.

### Pitfall 3: Chip panel initial selection from comma-separated tags string
**What goes wrong:** Station's `tags` field is a comma-separated string. Splitting on comma with no strip gives tags with leading spaces that won't match chip labels.
**How to avoid:** Use the existing `normalize_tags()` function from `main_window.py` (or replicate the strip+filter logic) when building `_selected_tags` from `self.station.tags`.

### Pitfall 4: New tag entry not cleared after adding to selection
**What goes wrong:** If user types a tag, saves, reopens dialog — the new_tag_entry persists. But since dialog is modal and closes on save, this is not actually an issue. The real risk is the entry text being ignored on save.
**How to avoid:** In `_save()`, read both `_selected_tags` AND `new_tag_entry.get_text().strip()` before building the tags string.

### Pitfall 5: ComboRow "None" / blank provider selection
**What goes wrong:** If user wants to clear the provider (set to None), there's no blank option in the list by default.
**How to avoid:** Prepend an empty string `""` as the first model item representing "No provider". On save, treat empty string selection as `provider_id = None`.

## Code Examples

### Building ComboRow from repo.list_providers()
```python
# In __init__, after self.station = repo.get_station(station_id)
providers = repo.list_providers()
provider_model = Gtk.StringList()
provider_model.append("")  # blank = no provider
for p in providers:
    provider_model.append(p.name)

self.provider_combo = Adw.ComboRow(title="Provider", model=provider_model)
# Pre-select current provider
current_name = self.station.provider_name or ""
for i, p in enumerate([""] + [p.name for p in providers]):
    if p == current_name:
        self.provider_combo.set_selected(i)
        break

self.new_provider_entry = Gtk.Entry()
self.new_provider_entry.set_placeholder_text("Or type new provider name…")
```

### Reading provider on save
```python
# In _save()
new_prov = self.new_provider_entry.get_text().strip()
if new_prov:
    provider_name = new_prov
else:
    idx = self.provider_combo.get_selected()
    item = self.provider_combo.get_model().get_item(idx)
    provider_name = item.get_string() if item else ""
provider_id = self.repo.ensure_provider(provider_name) if provider_name else None
```

### Building tag chip panel and reading on save
```python
# Build chips in __init__
all_tags = sorted({t.strip() for s in repo.list_stations()
                   for t in s.tags.split(",") if t.strip()})
current_tags = {t.strip() for t in self.station.tags.split(",") if t.strip()}
self._selected_tags = set(current_tags)
self._tag_chip_btns = []
self._rebuilding = False

for tag in all_tags:
    btn = Gtk.ToggleButton(label=tag)
    btn.set_active(tag in self._selected_tags)
    btn.connect("toggled", self._on_tag_chip_toggled, tag)
    self._chip_box.append(btn)
    self._tag_chip_btns.append(btn)

# Toggled callback
def _on_tag_chip_toggled(self, btn, tag_name):
    if self._rebuilding:
        return
    if btn.get_active():
        self._selected_tags.add(tag_name)
    else:
        self._selected_tags.discard(tag_name)

# In _save()
new_tag = self.new_tag_entry.get_text().strip()
all_selected = self._selected_tags | ({new_tag} if new_tag else set())
tags = ", ".join(sorted(all_selected))
```

### Parallel fetch flags
```python
self._thumb_fetch_in_progress = False
self._title_fetch_in_progress = False
self._fetch_cancelled = False

def _on_url_focus_out(self, *_):
    url = self.url_entry.get_text().strip()
    if _is_youtube_url(url):
        self._start_thumbnail_fetch(url)
        self._start_title_fetch(url)

def _start_title_fetch(self, url: str):
    if self._title_fetch_in_progress:
        return
    self._title_fetch_in_progress = True
    fetch_yt_title(url, self._on_title_fetched)

def _on_title_fetched(self, title):
    self._title_fetch_in_progress = False
    if self._fetch_cancelled:
        return
    if title:
        current = self.name_entry.get_text().strip()
        if current in ("", "New Station"):
            self.name_entry.set_text(title)
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | None detected — manual smoke testing only |
| Config file | None |
| Quick run command | Launch app, open edit dialog manually |
| Full suite command | N/A |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MGMT-01 | Provider dropdown shows existing providers | manual-smoke | Launch app, edit station | N/A |
| MGMT-02 | Tags shown as toggleable chips, multi-select works | manual-smoke | Launch app, edit station | N/A |
| MGMT-03 | New provider/tag typed inline saves correctly | manual-smoke | Launch app, edit station, type new value, save, reopen | N/A |
| MGMT-04 | YouTube URL focus-out populates name field | manual-smoke | Add YouTube station, observe name auto-fill | N/A |

No automated test infrastructure detected in this project. All validation is manual smoke testing at the UI level.

### Wave 0 Gaps
None — no test framework to install. All verification is manual.

## Sources

### Primary (HIGH confidence)
- `musicstreamer/ui/edit_dialog.py` — exact widget structure, existing fetch pattern, grid layout
- `musicstreamer/ui/main_window.py` — chip panel pattern (`_rebuild_filter_state`, `_make_chip`) to replicate
- `musicstreamer/repo.py` — `list_providers()`, `ensure_provider()`, `list_stations()` signatures
- `musicstreamer/models.py` — `Station.tags` is a comma-separated string field

### Secondary (MEDIUM confidence)
- GTK4/Adwaita documentation: `Adw.ComboRow` API — `set_model(Gtk.StringList)`, `set_selected()`, `get_selected()`, `get_model().get_item()`, `set_enable_search(True)`
- Known limitation: `Adw.ComboRow` does not expose typed search text as a direct property — requires separate Entry for new-value creation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries, all patterns already in codebase
- Architecture: HIGH — chip panel is a direct copy of existing main_window.py pattern; title fetch is a direct variant of thumbnail fetch
- Adw.ComboRow typed-text limitation: MEDIUM — known GTK/Adwaita behavior, workaround (separate Entry) is standard

**Research date:** 2026-03-22
**Valid until:** Stable — GTK4/Adwaita API does not change rapidly
