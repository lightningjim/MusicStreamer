---
phase: 89c-provider-brand-avatar-cover-slot-fallback
reviewed: 2026-06-17T00:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - musicstreamer/brand_avatars.py
  - musicstreamer/ui_qt/now_playing_panel.py
  - musicstreamer/ui_qt/edit_station_dialog.py
  - tests/test_brand_avatars.py
  - tests/test_cover_art_avatar.py
  - packaging/windows/MusicStreamer.spec
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
status: issues_found
---

# Phase 89c: Code Review Report

**Reviewed:** 2026-06-17
**Depth:** standard (ultracode all-dimensions + adversarial)
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Reviewed the Phase 89c provider brand-avatar cover-slot fallback: the new
`brand_avatars` registry, the `_resolve_brand_avatar_fallback` /
`_set_brand_avatar_pixmap` wiring in `NowPlayingPanel`, the synchronous
`_on_choose_brand_image` picker in `EditStationDialog`, the PyInstaller datas
line, and the source-grep drift-guard tests.

The never-raise contract for `brand_avatars.lookup()` holds (dict `.get`,
guarded `_res.files`, `str()`-then-`os.path.isfile` — none can raise for any
string input). Persistence is correctly the dedicated single-column
`update_provider_avatar_path` UPDATE (no broad-save field wipe). The
Pitfall-7 `provider_id is None` guard genuinely precedes every write/DB call in
`_on_choose_brand_image`. The brand-avatars asset directory exists (only
`.gitkeep`; PNGs arrive later per D-04) and the spec datas tuple is correct.

Two real defects survived adversarial refutation: a stale-`_last_cover_path`
clobber in the tier-replay precedence, and an unguarded file-read raise in the
otherwise-defensive brand-image picker slot.

## Warnings

### WR-01: Brand/provider avatar fallback leaves `_last_cover_path` stale, so a later resize re-renders the previous track's cover art

**File:** `musicstreamer/ui_qt/now_playing_panel.py:2129-2136`, `2232-2282`
**Issue:**
`_apply_art_tier` chooses what to re-render on a tier change with the
precedence `_last_cover_path` > `_last_avatar_path` > `_last_brand_avatar`
(L2129-2134). The runtime fallback path does not clear `_last_cover_path`:

- `_on_cover_art_ready(empty)` → `_resolve_brand_avatar_fallback()` (L2188).
- `_resolve_brand_avatar_fallback` step 1 calls `_set_avatar_pixmap_from_path`
  (sets `_last_avatar_path`) and step 2 calls `_set_brand_avatar_pixmap`
  (sets `_last_brand_avatar`). Both setters explicitly "do NOT touch
  `_last_cover_path`" (docstrings L2213, L2268). Only step 3
  (`_show_station_logo_in_cover_slot`) clears it (L2330).
- `_last_cover_path` is *only* ever set to `None` in
  `_show_station_logo_in_cover_slot`; `bind_station` does not reset it
  (grep: L346, 2207, 2330 are the sole writers).

Repro: track A resolves an iTunes cover → `_last_cover_path = "/tmp/A.jpg"`.
Track B (same station, junk/no-match title) → cover fetch returns empty →
`_resolve_brand_avatar_fallback` paints the brand/provider avatar but leaves
`_last_cover_path = "/tmp/A.jpg"`. User crosses a tier band (window resize or
Ctrl+B compact toggle) → `_apply_art_tier` sees `_last_cover_path is not None`
and re-renders the **stale track-A cover**, clobbering the brand avatar.

`bind_station` is NOT affected (it calls `_show_station_logo_in_cover_slot()`
at L933, clearing `_last_cover_path`, before the avatar branch), so this is
specifically the in-session track-change → exhausted-cover → resize path. The
drift-guard tests are source-grep only and do not exercise this state
transition, so it is untested.

**Fix:** Clear the lower-precedence state vars when entering the avatar/brand
fallback. Simplest is to null `_last_cover_path` at the top of
`_resolve_brand_avatar_fallback` (mirroring how the avatar setters null the
slot they are leaving):
```python
def _resolve_brand_avatar_fallback(self) -> None:
    # Entering the cover-exhausted branch: the real-cover slot is no longer
    # authoritative. Clear it so a later _apply_art_tier resize does not
    # re-render a stale prior-track cover over the avatar (WR-01).
    self._last_cover_path = None
    if self._station is not None:
        rel = getattr(self._station, "provider_avatar_path", None)
        ...
```
Also confirm `_set_brand_avatar_pixmap` / `_set_avatar_pixmap_from_path`
clear the *other* avatar slot so a brand→provider→brand sequence cannot leave
both set and pick the wrong branch on replay.

### WR-02: `_on_choose_brand_image` reads an arbitrary picked file with no exception guard, breaking the never-raise pattern its siblings follow

**File:** `musicstreamer/ui_qt/edit_station_dialog.py:1421-1430`
**Issue:**
The slot does `with open(path, "rb") as f: data = f.read()` then
`write_provider_avatar(...)` and `update_provider_avatar_path(...)` with no
try/except. The directly-analogous handler `_maybe_fetch_avatar_sync`
(L1866-1889) wraps the identical read/write/persist sequence in
`try/except Exception` precisely because "all failure modes are non-blocking."
`_on_choose_brand_image` is reachable failure-prone: the chosen file can be
removed/permission-revoked between dialog dismissal and `open` (TOCTOU),
`f.read()` can `MemoryError` on a huge selection, `write_provider_avatar` can
raise on disk-full, and `update_provider_avatar_path` can raise on a locked DB.
Any of these propagates out of the button-click slot, and the wait-cursor-less
exception leaves the dialog in an inconsistent state (file possibly written but
DB not persisted when the UPDATE is the failing step).
**Fix:** Wrap the read-through-persist body in try/except, surfacing the
failure via `_avatar_status` like the sibling handler:
```python
if not path:
    return
try:
    with open(path, "rb") as f:
        data = f.read()
    from musicstreamer import assets as _assets
    rel_path = _assets.write_provider_avatar(self._station.provider_id, data)
    self._station.provider_avatar_path = rel_path
    self._refresh_avatar_preview()
    self._avatar_status.setText("Brand image saved")
    self._repo.update_provider_avatar_path(self._station.provider_id, rel_path)
except Exception:  # noqa: BLE001 — slot must not raise
    self._avatar_status.setText("Could not read or save the selected image")
```

## Info

### IN-01: `_on_choose_brand_image` writes the file before persisting the DB row, so a DB failure leaves an orphaned on-disk avatar

**File:** `musicstreamer/ui_qt/edit_station_dialog.py:1424-1430`
**Issue:** The sequence is write-file → set in-memory → refresh preview → set
status → DB UPDATE. If `update_provider_avatar_path` is the failing call, the
`{provider_id}.png` file and the in-memory `provider_avatar_path` are already
updated but the providers table is not, so the on-disk avatar is orphaned until
the next successful save overwrites it. This is benign (the file is keyed by
provider_id and self-heals on the next write/Refresh) and is shared with the
existing `_on_avatar_fetched` ordering, so it does not rise to a warning — but
folding it into the WR-02 try/except (which would leave status reflecting the
true persisted state) is the clean resolution.
**Fix:** Covered by the WR-02 try/except wrapping; optionally persist the DB
row before updating in-memory/preview state so a DB failure leaves no UI claim
of success.

---

_Reviewed: 2026-06-17_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard (ultracode + adversarial)_
