# Phase 89c: Provider Brand-Avatar Cover-Slot Fallback — Research

**Researched:** 2026-06-17
**Domain:** Qt cover-slot render path extension — bundled package-data assets, registry lookup, circular-crop reuse, EditStationDialog brand-pick UI
**Confidence:** HIGH (all claims verified against live source; no web research needed per "Research flag: NO")

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-01: Brand-avatar registry keyed on exact `provider_name`. Registered: `"SomaFM"` (1) + all 6 AudioAddict networks — `"DI.fm"`, `"RadioTunes"`, `"JazzRadio"`, `"RockRadio"`, `"ClassicalRadio"`, `"ZenRadio"` (from aa_import.py:106-111). GBS.FM explicitly NOT registered.
- D-02: Per-network granularity — 7 distinct brand avatars, one per provider_name key.
- D-03: Assets are pre-composed circular PNGs (not runtime-cropped wordmarks).
- D-04: User supplies the final PNGs. Phase ships plumbing + filename slots. Missing asset = current behavior, no crash.
- D-05: Bundled as loose package data — `musicstreamer/ui_qt/brand-avatars/<key>.png`. Loaded via `importlib.resources.files`. Added to PyInstaller `datas`.
- D-06: Circular render reuses `_make_circular_pixmap` (now_playing_panel.py:219). No border, antialiased.
- D-07: Trigger is the `if not path:` branch in `_on_cover_art_ready` (L2183) — NOT `icy_disabled`. Source-grep drift-guard pins this.
- D-08: Resolution precedence at the exhausted branch: (1) `station.provider_avatar_path` if set and file exists, (2) bundled brand registry match on `provider_name`, (3) existing `_show_station_logo_in_cover_slot()`.
- D-09: EditStationDialog "Choose brand image…" picker writes via `assets.write_provider_avatar` + persists via `update_provider_avatar_path` (non-silent-reset).
- D-09a: OPEN — planner must resolve auto-fetch-vs-manual-pick collision (see §D-09a Resolution below).
- D-10: Brand avatar is transient per cover-resolution (not sticky). Real art always wins.
- D-11: New tracked state var `_last_brand_avatar` + sibling render method + 4th branch in `_apply_art_tier`. Do NOT reuse `_last_avatar_path` / `_set_avatar_pixmap_from_path`. Reset on `bind_station`.
- D-12: Source-grep drift-guard mirroring ART-AVATAR-09 / `test_mb_caa_runs_before_channel_avatar`.

### Claude's Discretion
- Registry module shape: dedicated `brand_avatars.py` with `lookup(provider_name) -> Optional[str]` recommended over inline dict.
- Exact tracked-var naming, sibling render-method name/placement.
- `brand-avatars/` filename-key scheme (slug per provider_name) and provider_name→key normalization.
- EditStationDialog "Choose brand image…" picker layout within existing avatar area.

### Deferred Ideas (OUT OF SCOPE)
- Additional ICY providers beyond SomaFM/AA.
- Central "manage all providers" screen.
- Claude auto-sourcing official brand marks.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ART-AVATAR-11 | Provider brand-avatar registry keyed on `provider_name`; bundled assets (not per-station fetch); GBS.FM excluded | D-01/D-02/D-04/D-05 confirmed; provider_name literals verified in source |
| ART-AVATAR-12 | Cover-resolution-exhausted trigger (`if not path:` branch, NOT `icy_disabled`); circular crop; no regression for unregistered providers | Exact trigger at L2183 confirmed; `_make_circular_pixmap` at L219 confirmed; fallthrough to `_show_station_logo_in_cover_slot` preserved |
</phase_requirements>

---

## Summary

Phase 89c extends the cover-slot render path at a single, precisely-located hook point: the `if not path:` branch at `now_playing_panel.py:L2183` inside `_on_cover_art_ready`. This is where cover-art resolution has been exhausted (iTunes and MB-CAA both missed) and the panel currently calls `_show_station_logo_in_cover_slot()`. Phase 89c inserts a three-tier resolution before that call: user override (`station.provider_avatar_path`) → bundled brand registry match → existing logo fallback.

All mechanisms reused from prior phases are confirmed live in the codebase. `_make_circular_pixmap` at L219, `_apply_art_tier` at L2087, `_set_avatar_pixmap_from_path` at L2205, `write_provider_avatar` in assets.py:63, and `update_provider_avatar_path` in repo.py:965 are all present and operational. The `_AvatarFetchWorker` + `_on_url_timer_timeout` auto-fetch path is gated exclusively on `is_avatar_url = "youtube.com" in lower or "youtu.be" in lower or "twitch.tv" in lower` — ICY-provider URLs (SomaFM, AA radio) do NOT match this gate, so the manual "Choose brand image…" picker for Phase 89c operates in a completely disjoint code path. No auto-fetch-vs-manual-pick collision exists at the URL-detection level.

The key open question (D-09a) has a clean answer: the `_refresh_avatar_btn` is already gated in `_on_url_text_changed` (L1286-1288) to enable only for YouTube/Twitch URLs. SomaFM/AA stations have non-matching URLs, so the Refresh button stays disabled for them. The "Choose brand image…" picker is a new file-picker button (not the auto-fetch path), writes to the same `provider_avatar_path` column, and does not touch `_AvatarFetchWorker` at all. No clobber risk.

**Primary recommendation:** Wire the three-tier resolution inline at L2183–L2184 as a small extracted helper, add `_last_brand_avatar: Optional[str]` state var (initialized to `None`, reset in `bind_station`), add a `_set_brand_avatar_pixmap` render method, add a 4th `elif self._last_brand_avatar is not None` branch in `_apply_art_tier` between the existing `_last_avatar_path` branch and the `_show_station_logo_in_cover_slot()` else, and create `brand_avatars.py` with a `lookup(provider_name) -> Optional[str]` function that returns the absolute filesystem path to the bundled PNG if it exists.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Brand registry lookup | Application module (`brand_avatars.py`) | — | Pure data lookup; no Qt dependency; testable without display |
| Bundled PNG loading | Package data layer (`importlib.resources.files`) | — | PyInstaller-safe; no QRC recompile; matches existing `icons/` pattern |
| Cover-slot render (brand avatar) | Now-playing panel main thread | — | QPixmap/QPainter are not thread-safe (Phase 89 Pitfall 8) |
| Tier-replay on resize | `_apply_art_tier` (existing machinery) | — | 4th branch added; precendence: real cover > icy_disabled avatar > brand avatar > logo |
| User upload override | EditStationDialog + assets.py + repo.py | — | Reuses existing `write_provider_avatar` + `update_provider_avatar_path` (Phase 89.1) |
| Drift-guard | Test file `test_cover_art_avatar.py` (new test added) | — | Source-grep over behavioral mocks per project convention |

---

## Confirmed Integration Points (Line Numbers)

All line numbers verified against live source on 2026-06-17.

### now_playing_panel.py

| Symbol | Line | Role in Phase 89c |
|--------|------|-------------------|
| `_make_circular_pixmap(source, size)` | L219 (module-level) | Reused for brand PNG circular crop — no changes needed |
| `_last_cover_path` | L346 | Existing tier-replay state; unaffected |
| `_last_avatar_path` | L347 | Existing icy_disabled tier-replay state; do NOT reuse for brand |
| `bind_station()` | L909 | Reset `_last_brand_avatar = None` near L936 (where `_last_avatar_path = None` already lives) |
| `_apply_art_tier()` | L2087 | Add 4th branch at L2129 region: `elif self._last_brand_avatar is not None: self._set_brand_avatar_pixmap(self._last_brand_avatar)` |
| Current `_apply_art_tier` 3-branch structure | L2127-L2132 | `real cover → _last_avatar_path → else logo`. 4th branch inserts between `_last_avatar_path` and `else`. |
| `_on_cover_art_ready()` | L2173 | Slot for ICY cover-art worker result |
| **THE TRIGGER: `if not path:` branch** | **L2183-L2184** | Currently: `self._show_station_logo_in_cover_slot()`. Replace with: three-tier resolution (D-08) |
| `_set_cover_pixmap()` | L2188 | Real cover path; untouched |
| `_set_avatar_pixmap_from_path(rel_path)` | L2205 | icy_disabled avatar path; do NOT reuse — it joins `data_dir()` (brand path is package data) |
| `_show_station_logo_in_cover_slot()` | L2267 | Kept as the final fallback (tier 3 of D-08) |

### cover_art.py

| Symbol | Line | Role |
|--------|------|------|
| `_mb_caa_lookup` | L148 | Source-grep drift-guard anchor (must appear BEFORE any `_brand_avatar_lookup`) |
| `_channel_avatar_lookup` | L159 | Source-grep drift-guard anchor (must appear BETWEEN `_mb_caa_lookup` and any `_brand_avatar_lookup` if added here) |

**Important:** The CONTEXT.md D-07 drift-guard specifies that the brand lookup fires in `_on_cover_art_ready`, NOT in `fetch_cover_art`'s dispatch chain. The `_brand_avatar_lookup` need not be added to `cover_art.py` at all. The drift-guard test for this phase pins that the brand lookup is called inside `_on_cover_art_ready`'s `if not path:` branch, never from `fetch_cover_art`. This is a source-grep test on `now_playing_panel.py`, not on `cover_art.py`.

### assets.py

| Symbol | Line | Role |
|--------|------|------|
| `write_provider_avatar(provider_id, data)` | L63 | Reused for D-09 upload override (atomic mkstemp+os.replace, data_dir-relative return) |

### repo.py

| Symbol | Line | Role |
|--------|------|------|
| `update_provider_avatar_path(provider_id, path)` | L965 | Reused for D-09 upload override persist (non-silent-reset single-column UPDATE) |
| `providers.avatar_path` in mappers | L644, L685, L795, L914 | Already surfaces as `station.provider_avatar_path` on all Station load paths (list, get, search, new-station). D-08 step-1 reads this. |

### aa_import.py

| Symbol | Line | Exact string |
|--------|------|--------------|
| `NETWORKS[0]["name"]` | L106 | `"DI.fm"` |
| `NETWORKS[1]["name"]` | L107 | `"RadioTunes"` |
| `NETWORKS[2]["name"]` | L108 | `"JazzRadio"` |
| `NETWORKS[3]["name"]` | L109 | `"RockRadio"` |
| `NETWORKS[4]["name"]` | L110 | `"ClassicalRadio"` |
| `NETWORKS[5]["name"]` | L111 | `"ZenRadio"` |

These are the EXACT strings that appear in `station.provider_name` for AudioAddict stations. The registry must key on these verbatim. [VERIFIED: live source read]

### soma_import.py

| Symbol | Line | Exact string |
|--------|------|--------------|
| `provider_name=` literal | L306 | `"SomaFM"` (CamelCase, no space, no period) |

[VERIFIED: live source read]

---

## D-09a Resolution (Open Question)

**Question:** Does the manual "Choose brand image…" picker for ICY providers collide with the auto-fetch debounce that handles YouTube/Twitch?

**Finding (VERIFIED: live source read):**

The auto-fetch path is gated in two places, both of which exclude SomaFM/AA URLs:

1. `_on_url_text_changed` (L1275-1288): enables `_refresh_avatar_btn` only for `is_yt or is_twitch` — both require URL pattern match on `youtube.com / youtu.be / twitch.tv`. A SomaFM URL like `https://ice2.somafm.com/groovesalad-256-mp3` matches none of these. The Refresh button stays disabled.

2. `_on_url_timer_timeout` (L1290-1356): launches `_AvatarFetchWorker` only when `is_avatar_url = "youtube.com" in lower or "youtu.be" in lower or "twitch.tv" in lower`. SomaFM/AA URLs are excluded. No worker fires.

**Conclusion:** A given provider is categorically either a YT/Twitch channel (auto-fetch applies) or an ICY brand provider (auto-fetch never fires). No collision exists at the URL-detection gate level.

**Recommended concrete approach for D-09:**
- Add a new button in the existing avatar row: `"Choose brand image…"` visible for ALL providers (not URL-gated), placed alongside the existing `_refresh_avatar_btn`.
- On click: `QFileDialog.getOpenFileName(…, "Images (*.png *.jpg *.jpeg *.webp)")`.
- On file selected: read bytes, call `assets.write_provider_avatar(self._station.provider_id, data)`, call `self._repo.update_provider_avatar_path(…)`, update in-memory `self._station.provider_avatar_path`, call `_refresh_avatar_preview()`.
- Guard: if `self._station.provider_id is None`, disable the button or show a "save station first" message (mirrors the existing Pitfall-7 guard at L1331).
- The existing `_refresh_avatar_btn` (`"Refresh avatar"`) stays YouTube/Twitch-only and is unaffected.
- No `_AvatarFetchWorker` involvement — this is a synchronous file-read-and-copy, not a network fetch.

This approach is structurally equivalent to the existing `_on_choose_logo` / `_choose_logo_btn` flow (L1384) which picks a file and calls `copy_asset_for_station`. Mirror that pattern.

---

## Asset Bundling Pattern

### importlib.resources.files (Python 3.9+, confirmed available)

```python
# In brand_avatars.py
import importlib.resources as _res
from typing import Optional

_REGISTRY: dict[str, str] = {
    "SomaFM":         "SomaFM.png",
    "DI.fm":          "DI.fm.png",
    "RadioTunes":     "RadioTunes.png",
    "JazzRadio":      "JazzRadio.png",
    "RockRadio":      "RockRadio.png",
    "ClassicalRadio": "ClassicalRadio.png",
    "ZenRadio":       "ZenRadio.png",
}

def lookup(provider_name: str) -> Optional[str]:
    """Return absolute path to bundled brand PNG if it exists, else None.

    Keyed on exact provider_name string (aa_import.py NETWORKS[*]["name"] /
    soma_import.py literal). Missing file (placeholder slot) returns None.
    """
    filename = _REGISTRY.get(provider_name)
    if filename is None:
        return None
    pkg_path = _res.files("musicstreamer.ui_qt") / "brand-avatars" / filename
    abs_str = str(pkg_path)
    if not __import__("os").path.isfile(abs_str):
        return None
    return abs_str
```

[ASSUMED: exact filename-slug scheme. The dict above uses provider_name as the stem — planner decides exact normalization (e.g. `DI.fm.png` vs `di-fm.png`). Either works; the dict is the single normalization point.]

### PyInstaller spec — datas registration

The existing pattern (confirmed at MusicStreamer.spec:123):
```python
("../../musicstreamer/ui_qt/icons", "musicstreamer/ui_qt/icons"),  # SVG source
```

Add:
```python
("../../musicstreamer/ui_qt/brand-avatars", "musicstreamer/ui_qt/brand-avatars"),
```

The `importlib.resources.files()` call resolves to `musicstreamer/ui_qt/brand-avatars/` relative to the bundle root when the datas tuple maps to that destination path. [VERIFIED: existing icons datas pattern; ASSUMED: identical resolution behavior for brand-avatars subdir under PyInstaller — consistent with how icons/ works.]

### pyproject.toml package_data

`pyproject.toml` has no explicit `[tool.setuptools.package-data]` stanza. The `icons/` subdirectory is auto-included because setuptools with `packages.find` uses VCS discovery (git ls-files) to include tracked non-`.py` files. [VERIFIED: git tracks `musicstreamer/ui_qt/icons/*`; confirmed by `tools.setuptools.packages.find` in pyproject.toml L59-61.]

**Action required:** `git add musicstreamer/ui_qt/brand-avatars/` (even as an empty dir with a `.gitkeep`) so setuptools auto-discovers it in sdist/wheel builds. PNG files added later are picked up automatically once the directory is tracked.

---

## Architecture Patterns

### Trigger Hook — Exact Code Change

Current code at L2183-L2184:
```python
if not path:
    self._show_station_logo_in_cover_slot()
    return
```

Phase 89c replacement:
```python
if not path:
    self._resolve_brand_avatar_fallback()   # D-07/D-08: three-tier resolution
    return
```

Where `_resolve_brand_avatar_fallback()` implements D-08 precedence:
1. Check `station.provider_avatar_path` — if set and file exists on disk (join `data_dir()`), call `_set_avatar_pixmap_from_path(rel_path)` and set `_last_brand_avatar = ("user_override", rel_path)` — OR use the existing `_set_avatar_pixmap_from_path` which already uses `_last_avatar_path`. **Wait** — see Collision Analysis below.

### Collision Analysis: D-08 step-1 vs `_last_avatar_path`

D-08 step-1 says: use `station.provider_avatar_path` if set and file exists. `_set_avatar_pixmap_from_path` already loads from `provider_avatar_path` (that's what Phase 89.1 wired in `bind_station`). BUT — `bind_station` only calls `_set_avatar_pixmap_from_path` when `icy_disabled` is True. For ICY-enabled SomaFM/AA stations, `bind_station` does NOT call `_set_avatar_pixmap_from_path` (the `if getattr(station, "icy_disabled", False):` guard at L937 excludes them). So `_last_avatar_path` is `None` for these stations throughout — no collision.

When D-08 step-1 fires (user override via D-09 pick), it can safely call `_set_avatar_pixmap_from_path` because:
- The method does the right thing (loads from `data_dir()`-relative path, circular crop).
- `_last_avatar_path` was None (not icy_disabled), so setting it does not stomp a real icy_disabled avatar.
- The tier-replay then hits the `elif self._last_avatar_path is not None` branch correctly.

**Conclusion:** D-08 step-1 CAN reuse `_set_avatar_pixmap_from_path` / `_last_avatar_path` when the source is the user-override `provider_avatar_path`. Only D-08 step-2 (bundled brand PNG from package data) needs the new `_last_brand_avatar` tracked var, because the bundled PNG is loaded from an absolute package-data path, not a `data_dir()`-relative path.

This simplifies the design:
- `_last_avatar_path` / `_set_avatar_pixmap_from_path` covers D-08 step-1 (user-override, `data_dir()`-relative).
- `_last_brand_avatar` / `_set_brand_avatar_pixmap` covers D-08 step-2 (bundled PNG, absolute package-data path).
- `_apply_art_tier` 4th branch sits between `_last_avatar_path` and the `else`:
  ```python
  elif self._last_brand_avatar is not None:
      self._set_brand_avatar_pixmap(self._last_brand_avatar)
  ```
- Precedence in `_apply_art_tier`: `_last_cover_path > _last_avatar_path > _last_brand_avatar > _show_station_logo_in_cover_slot`. [ASSUMED: this ordering is safe because `_last_avatar_path` is None for non-icy_disabled stations, so the two vars never compete in practice — but the ordering is still structurally correct per D-11.]

### `_resolve_brand_avatar_fallback()` full logic

```python
def _resolve_brand_avatar_fallback(self) -> None:
    """D-07/D-08: three-tier resolution at the cover-resolution-exhausted branch.

    Called only from _on_cover_art_ready when not path (L2183).
    Never called from fetch_cover_art dispatch chain (D-12 drift-guard).
    """
    # D-08 step 1: user-override via providers.avatar_path (Phase 89.1 column).
    # These ICY-enabled stations are NOT icy_disabled, so _last_avatar_path is
    # None — safe to set it here for tier-replay without collision.
    if self._station is not None:
        rel = getattr(self._station, "provider_avatar_path", None)
        if rel:
            from musicstreamer import paths as _p
            if _p_os.path.isfile(_p_os.path.join(_p.data_dir(), rel)):
                self._set_avatar_pixmap_from_path(rel)   # sets _last_avatar_path
                return

    # D-08 step 2: bundled brand registry.
    if self._station is not None:
        from musicstreamer import brand_avatars
        abs_path = brand_avatars.lookup(self._station.provider_name or "")
        if abs_path:
            self._set_brand_avatar_pixmap(abs_path)   # sets _last_brand_avatar
            return

    # D-08 step 3: existing fallback.
    self._show_station_logo_in_cover_slot()
```

### `_set_brand_avatar_pixmap(abs_path)` — new method

```python
def _set_brand_avatar_pixmap(self, abs_path: str) -> None:
    """D-11: load bundled brand PNG from absolute package-data path, circular-crop, display.

    Tracks _last_brand_avatar for tier-change replay in _apply_art_tier.
    Does NOT touch _last_cover_path or _last_avatar_path.
    On load failure, clears _last_brand_avatar = None and falls back to logo.
    Main thread only — QPixmap/QPainter are not thread-safe (Phase 89 Pitfall 8).
    """
    pix = QPixmap(abs_path)
    if pix.isNull():
        self._last_brand_avatar = None
        self._show_station_logo_in_cover_slot()
        return
    n = self._current_art_tier or 180
    circ = _make_circular_pixmap(pix, n)
    self.cover_label.setPixmap(circ)
    self._last_brand_avatar = abs_path   # absolute path (package data)
```

### bind_station reset

Add at L936 region (alongside `self._last_avatar_path = None`):
```python
self._last_brand_avatar = None   # D-11: stale-station bleed guard
```

And in `__init__` (alongside `self._last_avatar_path: Optional[str] = None` at L347):
```python
self._last_brand_avatar: Optional[str] = None   # Phase 89c D-11
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Circular crop | Custom QPainter clip code | `_make_circular_pixmap` (L219) | Already correct, antialiased, tested in production |
| Provider avatar write + persist | New write path | `assets.write_provider_avatar` + `repo.update_provider_avatar_path` | Atomic, non-silent-reset, already battle-tested in Phase 89/89.1 |
| PyInstaller-safe asset path | Hardcoded path string | `importlib.resources.files(…)` + datas in spec | Frozen-build-safe, mirrors icons/ pattern |
| Brand PNG registration | Inline dict in `_on_cover_art_ready` | Dedicated `brand_avatars.py` module | Testable, grep-friendly, consistent with `yt_import` registry pattern |

---

## Common Pitfalls

### Pitfall 1: `_set_avatar_pixmap_from_path` joins `data_dir()` — bundled assets are NOT in data_dir
**What goes wrong:** Calling `_set_avatar_pixmap_from_path` for the bundled brand PNG (D-08 step 2). That method calls `os.path.join(_paths.data_dir(), rel_path)`. A package-data absolute path fed as `rel_path` would produce a wrong path like `/home/user/.local/share/musicstreamer/musicstreamer/ui_qt/brand-avatars/SomaFM.png`.
**Prevention:** `_set_avatar_pixmap_from_path` is for D-08 step-1 (user override, `data_dir()`-relative). Bundled brand PNGs use the new `_set_brand_avatar_pixmap(abs_path)` which takes an already-absolute path.

### Pitfall 2: Trigger location drift — firing brand lookup from `icy_disabled` path instead of `_on_cover_art_ready`
**What goes wrong:** Adding brand-avatar logic to `bind_station`'s `icy_disabled` branch instead of the `_on_cover_art_ready` `if not path:` branch. SomaFM/AA are ICY-ENABLED (icy_disabled=False) — the `if getattr(station, "icy_disabled", False):` guard at L937 would never fire for them.
**Prevention:** D-07 is explicit. The drift-guard test (D-12) enforces the trigger is in `_on_cover_art_ready`.

### Pitfall 3: Stale brand avatar bleeds to new station
**What goes wrong:** Binding a SomaFM station, cover fallback shows SomaFM brand avatar, then binding GBS.FM station — if `_last_brand_avatar` is not reset, `_apply_art_tier` re-renders the SomaFM avatar for GBS.
**Prevention:** Reset `_last_brand_avatar = None` at the top of `bind_station` (alongside `_last_avatar_path`). This is D-11's stale-station bleed guard.

### Pitfall 4: Missing-asset → crash or broken-image
**What goes wrong:** The 7 filename slots exist in the registry dict but the PNG files are not yet present (D-04 — user provides them). If `brand_avatars.lookup()` returns a path but the file doesn't exist, `QPixmap.isNull()` will be True and cause confusing fallback behavior.
**Prevention:** `brand_avatars.lookup()` must check `os.path.isfile(abs_str)` before returning the path. Return `None` if the file does not exist. `_set_brand_avatar_pixmap` must also guard on `pix.isNull()`.

### Pitfall 5: D-09 upload override calls `_AvatarFetchWorker` (wrong path)
**What goes wrong:** Implementing "Choose brand image…" via the existing `_AvatarFetchWorker` / `_on_refresh_avatar_clicked` path, which fires a network fetch.
**Prevention:** The brand-image picker is a synchronous `QFileDialog` + file-read, analogous to `_on_choose_logo` (L1384), not a network fetch. No worker thread needed.

### Pitfall 6: D-09 upload writes to wrong location
**What goes wrong:** Writing the uploaded brand image to a station-keyed path (`channel_avatars_dir()/{station_id}.png`) instead of the provider-keyed path (`channel_avatars_dir()/{provider_id}.png`).
**Prevention:** Call `assets.write_provider_avatar(self._station.provider_id, data)` (Phase 89.1, L63). This keys by provider_id. The returned relative path is then persisted via `update_provider_avatar_path`.

### Pitfall 7: Provider_id is None for new/unsaved station
**What goes wrong:** User opens EditStationDialog for a new station (no provider yet), clicks "Choose brand image…", `self._station.provider_id is None` → `write_provider_avatar(None, data)` writes `None.png`, `update_provider_avatar_path(None, …)` silently updates 0 rows.
**Prevention:** Gate the brand-image picker on `self._station.provider_id is not None`. Show "Save station first" status text. Mirror the Pitfall-7 guard pattern at L1331.

### Pitfall 8: `_apply_art_tier` 4th branch sits in wrong position
**What goes wrong:** Adding `elif self._last_brand_avatar` BEFORE `elif self._last_avatar_path`, so an icy_disabled station's circular avatar is accidentally replaced by a brand avatar on resize.
**Prevention:** Precedence order MUST be `real cover → _last_avatar_path (icy_disabled) → _last_brand_avatar (brand) → logo`. In practice, `_last_avatar_path` and `_last_brand_avatar` are never both set simultaneously (icy_disabled vs. ICY-enabled are mutually exclusive), but the structural ordering keeps it safe for future edge cases.

### Pitfall 9: PyInstaller `datas` maps to wrong destination path
**What goes wrong:** The `datas` entry destination path is wrong (e.g. `"brand-avatars"` instead of `"musicstreamer/ui_qt/brand-avatars"`), so `importlib.resources.files("musicstreamer.ui_qt") / "brand-avatars"` resolves to a path that doesn't match the bundle layout.
**Prevention:** Mirror the existing icons entry exactly: `("../../musicstreamer/ui_qt/brand-avatars", "musicstreamer/ui_qt/brand-avatars")`. The destination must be `musicstreamer/ui_qt/brand-avatars` so the package namespace resolves correctly. Memory note: `frozen-build-env-missing-runtime-components` — silently missing dirs have caused blind spots before; add a logged warning if lookup finds a registered provider_name but the PNG is absent.

---

## Validation Architecture

No GStreamer behavioral mocks. All validation is source-grep or lightweight unit test per project convention (`feedback_gstreamer_mock_blind_spot`).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (confirmed in pyproject.toml `[tool.pytest.ini_options]`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `.venv/bin/python -m pytest tests/test_cover_art_avatar.py tests/test_brand_avatars.py -x` |
| Full suite command | `.venv/bin/python -m pytest tests/ -x` (note: full suite >600s; scope to relevant files per memory) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| ART-AVATAR-11 / D-01 | Registry recognizes all 7 provider_name strings exactly | unit | `pytest tests/test_brand_avatars.py::test_lookup_registered_providers -x` | No — Wave 0 |
| ART-AVATAR-11 / D-01 | GBS.FM returns None from registry | unit | `pytest tests/test_brand_avatars.py::test_lookup_gbs_returns_none -x` | No — Wave 0 |
| ART-AVATAR-11 / D-04 | Missing PNG file returns None (no crash) | unit | `pytest tests/test_brand_avatars.py::test_lookup_missing_file_returns_none -x` | No — Wave 0 |
| ART-AVATAR-12 / D-12 | Brand lookup fires ONLY from `_on_cover_art_ready` `if not path:` branch | source-grep | `pytest tests/test_cover_art_avatar.py::test_brand_lookup_only_in_cover_exhausted_branch -x` | No — Wave 0 |
| ART-AVATAR-12 / D-07 | `_resolve_brand_avatar_fallback` is NOT called from `fetch_cover_art` or `bind_station` icy_disabled path | source-grep | same test above | No — Wave 0 |
| D-11 / tier-replay | `_last_brand_avatar` present in `_apply_art_tier` branch | source-grep | `pytest tests/test_brand_avatars.py::test_apply_art_tier_has_brand_avatar_branch -x` | No — Wave 0 |
| D-11 / stale-station bleed | `_last_brand_avatar = None` reset in `bind_station` | source-grep | `pytest tests/test_brand_avatars.py::test_bind_station_resets_brand_avatar -x` | No — Wave 0 |
| D-08 / precedence ordering | Resolution: user override → bundled registry → logo | unit (no Qt) | `pytest tests/test_brand_avatars.py::test_resolution_precedence_*` | No — Wave 0 |
| ART-AVATAR-12 / no-regression | Unregistered providers (e.g. "GBS.FM", manual providers) reach `_show_station_logo_in_cover_slot` | source-grep / unit | `pytest tests/test_brand_avatars.py::test_unregistered_provider_fallsthrough -x` | No — Wave 0 |
| ART-AVATAR-09 (existing) | `_mb_caa_lookup` before `_channel_avatar_lookup` in cover_art.py | source-grep (existing) | `pytest tests/test_cover_art_avatar.py::test_mb_caa_runs_before_channel_avatar -x` | YES — exists |

### Validation Mechanism Details

**Source-grep tests** (preferred per `feedback_gstreamer_mock_blind_spot`):

1. **`test_brand_lookup_only_in_cover_exhausted_branch`** (new, in `test_cover_art_avatar.py` or new `test_brand_avatars.py`): Reads `now_playing_panel.py` as text. Asserts:
   - `"_resolve_brand_avatar_fallback"` or `"brand_avatars.lookup"` appears ONLY within `_on_cover_art_ready` function body (not in `bind_station`, not in `fetch_cover_art`).
   - Mirror of `test_mb_caa_runs_before_channel_avatar` style: `src.find("def _on_cover_art_ready")`, then verify the brand lookup token appears after that position and before the next `def ` boundary.

2. **`test_apply_art_tier_has_brand_avatar_branch`**: Reads `now_playing_panel.py` as text. Asserts `"_last_brand_avatar"` appears within `_apply_art_tier` function body.

3. **`test_bind_station_resets_brand_avatar`**: Reads `now_playing_panel.py` as text. Asserts `"_last_brand_avatar = None"` appears within `bind_station` function body.

**Unit tests** (pure Python, no Qt, no GStreamer):

4. **`test_brand_avatars.py`**: Tests `brand_avatars.lookup(provider_name)` with a temp directory as the package root:
   - Place a stub PNG at `tmp_path/musicstreamer/ui_qt/brand-avatars/SomaFM.png`.
   - Monkeypatch `importlib.resources.files("musicstreamer.ui_qt")` to return `tmp_path/musicstreamer/ui_qt`.
   - Assert `lookup("SomaFM")` returns the stub path.
   - Assert `lookup("GBS.FM")` returns None.
   - Assert `lookup("SomaFM")` returns None when the PNG is absent (file not present in tmp_path).
   - Assert `lookup("unknown provider")` returns None.

**Manual UAT** (cannot be automated without a running Qt display):
- Bind a SomaFM station, let a track complete cover-art resolution with no result → verify brand avatar appears in cover slot, logo slot unchanged.
- Resize the window → verify brand avatar re-renders at new tier (tier-replay).
- Play a track that resolves real cover art → verify real cover replaces brand avatar.
- Next track that misses cover art → verify brand avatar re-appears.
- Bind GBS.FM → verify station logo appears in cover slot (no regression, GBS excluded).
- Bind a station with no registered provider → verify station logo appears (no regression).
- EditStationDialog "Choose brand image…" for SomaFM station: pick a PNG → verify preview updates, `providers.avatar_path` updated in DB, cover slot shows the upload on next cover-miss.

### Sampling Rate
- **Per task commit:** `pytest tests/test_cover_art_avatar.py tests/test_brand_avatars.py -x`
- **Per wave merge:** `pytest tests/ -x -k "not integration"` (scoped; full suite >600s)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_brand_avatars.py` — new file covering registry unit tests + source-grep drift-guards for D-11/D-12
- [ ] `musicstreamer/brand_avatars.py` — registry module (created in Wave 0 as part of plumbing)
- [ ] `musicstreamer/ui_qt/brand-avatars/` — directory + `.gitkeep` (Wave 0; PNGs arrive from user later)

---

## Standard Stack

No new packages. All mechanisms are in-process Python stdlib + existing project code.

| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| `importlib.resources` | stdlib (Python 3.9+) | Load bundled brand PNG paths | Already used in codebase (importlib.metadata used; .files() API available) |
| `QPixmap` / `QPainter` | PySide6 ≥6.10 (pinned) | Circular-crop render | Existing `_make_circular_pixmap` reused |
| `QFileDialog` | PySide6 ≥6.10 | Brand-image picker in EditStationDialog | Already used for logo picker |

## Package Legitimacy Audit

No new packages installed. Section not applicable.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python `importlib.resources.files` | `brand_avatars.py` asset loading | Yes | stdlib (Python 3.12 confirmed) | None needed |
| `musicstreamer/ui_qt/brand-avatars/` directory | `brand_avatars.lookup()` | Not yet | — | Git-add empty dir; missing PNGs = current behavior |
| PySide6 `QFileDialog` | D-09 picker | Yes | 6.10+ (pinned) | — |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Filename slug scheme uses provider_name as stem (e.g. `DI.fm.png`, `RadioTunes.png`) | Standard Stack / brand_avatars.py example | Purely internal mapping; dict is the single normalization point; risk is cosmetic only |
| A2 | `importlib.resources.files("musicstreamer.ui_qt") / "brand-avatars"` resolves correctly in frozen PyInstaller bundle when spec's datas destination is `"musicstreamer/ui_qt/brand-avatars"` | Asset Bundling Pattern | If wrong: brand PNGs invisible in frozen build; fallback to `_show_station_logo_in_cover_slot` (no crash). Detected immediately in first Windows frozen build test. Memory note: `frozen-build-env-missing-runtime-components` — add logged warning |
| A3 | `_apply_art_tier` 4th branch can sit between `_last_avatar_path` and `else` without behavioral regression | Architecture Patterns | If wrong: resize shows wrong image for icy_disabled stations; easily caught by existing Phase 89 behavior (icy_disabled stations are YouTube/Twitch, not ICY-enabled) |
| A4 | pyproject.toml auto-includes brand-avatars/ in wheel via VCS discovery once the dir is git-tracked | Asset Bundling Pattern | If wrong: sdist/wheel doesn't include PNGs; add explicit `[tool.setuptools.package-data]` entry. Low risk: icons/ auto-inclusion is proven precedent |

---

## Open Questions

1. **D-09 picker placement in EditStationDialog**
   - What we know: avatar row already has `_avatar_preview`, `_avatar_status`, `_refresh_avatar_btn`. "Choose brand image…" adds a 4th element.
   - What's unclear: whether to put it inline in the `avatar_row` (crowded) or add a second row.
   - Recommendation: Add to `avatar_row` after `_refresh_avatar_btn`, with a stretch before it if needed. OR add a second form row labeled "Brand image:" — planner's call; functionally equivalent.

2. **`_resolve_brand_avatar_fallback` naming and placement**
   - What we know: must be called from L2184, not inline for readability.
   - What's unclear: whether this should be a standalone method or inline code.
   - Recommendation: Dedicated method `_resolve_brand_avatar_fallback()` for testability and doc-comment clarity.

3. **Filename slug normalization for provider_names with special chars (e.g. `"DI.fm"`)**
   - What we know: `"DI.fm"` contains a period; valid in a filename on all platforms.
   - What's unclear: whether to normalize to `di-fm.png` or keep `DI.fm.png`.
   - Recommendation: Keep exact name as stem (`DI.fm.png`, `RadioTunes.png`) — the dict is the normalization point and periods in filenames cause no issues. Avoids a runtime slug-transform step.

---

## Sources

### Primary (HIGH confidence — all live source reads on 2026-06-17)
- `musicstreamer/ui_qt/now_playing_panel.py` — exact line numbers for all integration points
- `musicstreamer/cover_art.py` — drift-guard named functions confirmed
- `musicstreamer/aa_import.py` L106-111 — NETWORKS list, exact provider_name strings
- `musicstreamer/soma_import.py` L306 — "SomaFM" literal
- `musicstreamer/assets.py` — `write_provider_avatar` (L63) signature
- `musicstreamer/repo.py` — `update_provider_avatar_path` (L965), mapper queries (L644+)
- `musicstreamer/ui_qt/edit_station_dialog.py` — `_on_url_timer_timeout`, `is_avatar_url` gate, `_on_url_text_changed`, `_on_refresh_avatar_clicked`
- `tests/test_cover_art_avatar.py` — existing drift-guard test to mirror
- `packaging/windows/MusicStreamer.spec` — existing datas entry pattern
- `pyproject.toml` — package structure, `[tool.setuptools.packages.find]`
- `musicstreamer/yt_import.py` — `register_avatar_fetcher` / `get_avatar_fetcher` registry pattern

### No web research performed
Research flag was explicitly NO. All findings are codebase-confirmed.

---

## Metadata

**Confidence breakdown:**
- Integration points (exact lines): HIGH — live source reads, all verified
- D-09a resolution: HIGH — live source confirms URL-gate excludes ICY providers categorically
- Asset bundling pattern: HIGH (dev) / MEDIUM (frozen PyInstaller) — icons/ pattern is proven precedent; brand-avatars mirrors it; frozen-build risk noted as A2
- Validation architecture: HIGH — mirrors existing test_cover_art_avatar.py style exactly

**Research date:** 2026-06-17
**Valid until:** Stable — no fast-moving dependencies; valid until now_playing_panel.py render path is refactored (no indication of this)
