---
phase: 89B-twitch-channel-avatar-fetch
plan: 89B-03
reviewed: 2026-06-17T14:04:17Z
depth: deep
files_reviewed: 2
files_reviewed_list:
  - musicstreamer/ui_qt/edit_station_dialog.py
  - tests/test_twitch_provider_assign.py
findings:
  critical: 0
  warning: 2
  info: 2
  total: 4
status: issues_found
---

# Phase 89B-03: Code Review Report

**Reviewed:** 2026-06-17T14:04:17Z
**Depth:** deep (cross-file: yt_import, twitch_helix, assets, _AvatarFetchWorker)
**Files Reviewed:** 2
**Status:** issues_found (no blockers; 2 warnings, 2 info)
**Scope:** commits `29575e49` (feat) + `6055a07c` (test) only — pre-existing
_AvatarFetchWorker / _PlaylistFetchWorker pyright noise excluded per instructions.

## Summary

The 89B-03 gap-closure change is correct against all four stated invariants and the
six new tests pass GREEN (10/10 in the file). The synchronous helper
`_maybe_fetch_avatar_sync` faithfully mirrors `_AvatarFetchWorker.run()`, and the
in-memory provider refresh in `_on_save` is correctly placed after
`repo.ensure_provider`.

Invariant verification (all HOLD):
- **D-04 (user-typed provider never overwritten):** The Twitch-name derivation
  remains gated by `if not provider_name:` (line 1699), untouched by this diff. The
  new in-memory assignment (1714-1715) writes back whatever `ensure_provider`
  returned for the *manual* name in the manual case — it never re-derives. Confirmed
  by `test_save_manual_provider_not_overwritten_still_holds`.
- **Pitfall-7 (single provider_id guard not duplicated):** The line-1331 async guard
  is unchanged. The helper's `if provider_id is None: return` (1816) is a distinct
  save-path call site keyed on the freshly-resolved `provider_id` argument, not a
  second copy of the line-1331 `self._station.provider_id is None` widget-status
  guard. Different concern, different value — not a duplication.
- **D-07 reuse gate (existing-avatar provider must not refetch):** Lines 1827-1829
  replicate the async gate exactly (`provider_avatar and not _force_avatar_refresh`).
  Confirmed by `test_save_existing_provider_with_avatar_no_refetch` (no network, no
  write, no DB persist).
- **D-07 non-blocking failure:** The `except Exception` (1845) swallows all fetcher /
  write / DB errors; both registered fetchers (`twitch_helix.fetch_channel_avatar`,
  `yt_import.fetch_channel_avatar`) raise on failure rather than returning empty
  bytes, so no 0-byte PNG can be written. Confirmed by
  `test_save_fetch_failure_is_nonblocking` (`_save_succeeded is True`, no write).

Attribute-init audit (no AttributeError risk on the sync path): `_node_runtime`
(init line 342), `_repo` (336), `_avatar_status` (504) are always set in `__init__`;
`_force_avatar_refresh` is set only inside `_on_refresh_avatar_clicked`, and the
helper reads it via `getattr(self, "_force_avatar_refresh", False)` so the unset case
is safe.

The two warnings below are by-design tradeoffs of choosing a synchronous fetch; they
are worth recording for future maintainers but do not block ship.

## Warnings

### WR-01: Synchronous fetch can freeze the UI for up to ~20s before accept()

**File:** `musicstreamer/ui_qt/edit_station_dialog.py:1831-1851`
**Issue:** `_maybe_fetch_avatar_sync` runs two sequential blocking network calls on
the GUI thread. For Twitch (`twitch_helix.fetch_channel_avatar`, lines 136 + 146)
that is a GQL POST with `timeout=10` followed by a CDN image download with
`timeout=10` — worst case ~20s of a frozen, WaitCursor-locked dialog before
`accept()` fires. For YouTube the yt-dlp `extract_info` plus image download is also
not bounded by any single short timeout. This is the deliberate cost of the
sync-before-teardown design (the async slot would be disconnected by
`_shutdown_avatar_fetch_worker()` before it could persist), so it is a tradeoff
rather than a defect — but on a stalled connection the user sees a multi-second
hang on first save of every new Twitch/YouTube station.

The WaitCursor itself is safe: `setOverrideCursor` (1831) is paired with exactly one
`restoreOverrideCursor` in `finally` (1851), and every early `return` inside the
`try` (e.g. `if fetcher is None`, 1836-1837) unwinds through `finally`. The cursor
cannot get stuck on any in-body path. So this is purely the freeze duration, not a
cursor leak.

**Fix:** Acceptable as-is given the persistence constraint. If the freeze is judged
too long, bound it more tightly than the underlying 10s+10s — e.g. pass a shorter
timeout to the Twitch fetcher for the synchronous call site, or keep the async worker
but `worker.wait(<cap>)` for its completion in `_on_save` before teardown instead of
re-implementing the fetch inline. No code change required to ship.

### WR-02: setOverrideCursor sits OUTSIDE the try; a raise there would break Save (D-07)

**File:** `musicstreamer/ui_qt/edit_station_dialog.py:1831`
**Issue:** `QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))` is on line 1831,
one line *above* the `try:` at 1832. The helper is invoked at `_on_save:1798`, and
`self._save_succeeded = True` / `self.accept()` are at 1803-1804 — *after* the call.
If `setOverrideCursor` or `QCursor(...)` ever raised, the exception would propagate
out of the helper, skip `_save_succeeded = True` and `accept()`, and Save would
silently fail to close — a D-07 ("Save must always succeed") violation. In practice
these Qt constructors do not raise, so the invariant holds today; but the helper's
docstring promises "never raises," and the one statement that *could* (however
unlikely) is the one statement left outside the guard. Lines 1816-1829 (getattr with
defaults, string ops) are genuinely raise-free, so only line 1831 is exposed.

**Fix:** Move the cursor set inside the `try` so the contract is structurally
guaranteed (a `restoreOverrideCursor` with no matching set is a harmless no-op):
```python
try:
    QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
    from musicstreamer import yt_import, assets as _assets
    ...
except Exception:  # noqa: BLE001
    self._avatar_status.setText(...)
finally:
    QApplication.restoreOverrideCursor()
```

## Info

### IN-01: Sync helper omits the preview refresh / shared-effect status the async slot performs

**File:** `musicstreamer/ui_qt/edit_station_dialog.py:1842-1844`
**Issue:** `_on_avatar_fetched` (the async counterpart) calls
`self._refresh_avatar_preview()` and sets the "Avatar saved — all <provider> stations
updated" status on success (lines 1505-1511). The sync helper updates
`provider_avatar_path` and persists to DB but does neither. This is harmless because
`accept()` closes the dialog immediately after, so no preview is ever visible — but
it is a behavioral divergence from the mirrored method worth noting if the helper is
ever reused outside the close path.
**Fix:** None required while the only caller is `_on_save` immediately before
`accept()`. Add a one-line comment noting the deliberate omission if desired.

### IN-02: Failure-path status text is written to a widget on a dialog about to close

**File:** `musicstreamer/ui_qt/edit_station_dialog.py:1847-1849`
**Issue:** On fetch failure the helper sets `self._avatar_status` text, but `_on_save`
proceeds to `accept()` on the next lines, so the message is never seen by the user.
It is functionally dead UI feedback on this call site (it does match the async slot's
wording, so it is at least consistent). No correctness impact.
**Fix:** Harmless; leave for consistency with `_on_avatar_fetched`, or drop the
setText on the sync path since it is invisible.

---

_Reviewed: 2026-06-17T14:04:17Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
