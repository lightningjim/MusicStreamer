# Phase 99: Migrate Avatar Add-Path Tests off Removed `url_edit` Widget — Research

**Researched:** 2026-06-28
**Domain:** Test migration / Qt widget API delta (Phase 97 EditStationDialog refactor)
**Confidence:** HIGH — all findings verified directly against production source and live test runs

---

## Summary

Phase 97 (D-01) removed `url_edit` from `EditStationDialog` and made `streams_table` the sole URL editor. The canonical stream URL is now accessed via `_get_canonical_url_live()`, which reads `streams_table.item(_canonical_row, _COL_URL).text()`. Nine tests written for Phase 89B still reference the removed widget and fail at runtime with `AttributeError: 'EditStationDialog' object has no attribute 'url_edit'`.

Production wiring is intact. `_on_save` reads the URL for Twitch login derivation via `_get_canonical_url_live().strip()` (line 2027). The avatar add-path, provider derivation, and the `_refresh_avatar_btn` enable logic all use this path. Only the test harness code is broken.

The fix is purely in the test files. No changes to production code are needed or expected.

**Primary recommendation:** For 8 of 9 failing tests (all in `test_twitch_provider_assign.py`), simply delete the `d.url_edit.setText(...)` lines — the fixture stream already provides the correct URL in the streams table after dialog creation, making those calls redundant. For the 1 remaining test (`test_twitch_url_enables_refresh_btn`), replace the 3 `url_edit.setText + _on_url_text_changed()` call pairs with `item.setText + _on_canonical_cell_changed(row, _COL_URL)`.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TEST-REGRESSION-97x89B | 9 tests fail with AttributeError: url_edit removed in Phase 97; migrate to streams-table URL path | Fully characterized: root cause, migration pattern, and verification command identified |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| URL input (station edit dialog) | UI (streams table) | — | Phase 97 D-01: streams table is the sole URL editor; url_edit removed |
| Canonical URL read (metadata/derivation) | `_get_canonical_url_live()` method | — | Single authoritative read path: reads `streams_table.item(_canonical_row, _COL_URL).text()` |
| Refresh-btn enable gate | `_on_canonical_cell_changed` / `_on_canonical_btn_clicked` | `_populate` (initial state) | All three set `_refresh_avatar_btn.setEnabled(is_yt or is_twitch)` |
| Test URL injection | Test file only — streams fixture or direct cell setText | — | No production change needed |

---

## Failing Tests: Enumeration

All 9 failing tests confirm with the run command `/.venv/bin/python -m pytest tests/test_twitch_provider_assign.py tests/test_edit_station_dialog_avatar.py::test_twitch_url_enables_refresh_btn --tb=no -q`. [VERIFIED: live test run]

### File 1: `tests/test_twitch_provider_assign.py` — 8 failing tests

| # | Test name | Line | `url_edit` usage | URL set |
|---|-----------|------|-------------------|---------|
| 1 | `test_save_derives_provider_for_blank_twitch` | 116 | `d.url_edit.setText(url)` | `"https://www.twitch.tv/twitchdev"` |
| 2 | `test_save_preserves_manual_provider_for_twitch` | 171 | `d.url_edit.setText(url)` | `"https://www.twitch.tv/twitchdev"` |
| 3 | `test_save_non_twitch_url_unchanged` | 224 | `d.url_edit.setText(url)` | `"http://ice3.somafm.com/groovesalad-128.mp3"` |
| 4 | `test_save_add_path_fetches_avatar` | 268 | `d.url_edit.setText(url)` | `"https://www.twitch.tv/twitchdev"` |
| 5 | `test_save_add_path_refreshes_in_memory_provider` | 313 | `d.url_edit.setText(url)` | `"https://www.twitch.tv/twitchdev"` |
| 6 | `test_save_existing_provider_with_avatar_no_refetch` | 351 | `d.url_edit.setText(url)` | `"https://www.twitch.tv/twitchdev"` |
| 7 | `test_save_manual_provider_not_overwritten_still_holds` | 391 | `d.url_edit.setText(url)` | `"https://www.twitch.tv/twitchdev"` |
| 8 | `test_save_fetch_failure_is_nonblocking` | 426 | `d.url_edit.setText(url)` | `"https://www.twitch.tv/twitchdev"` |

**Two tests in this file already pass:** `test_save_source_has_twitch_derivation` (source-grep, no dialog) and `test_on_save_has_inmemory_provider_assignment` (source-grep, no dialog). Do not touch these.

### File 2: `tests/test_edit_station_dialog_avatar.py` — 1 failing test

| # | Test name | Lines | `url_edit` usage |
|---|-----------|-------|-----------------|
| 9 | `test_twitch_url_enables_refresh_btn` | 87–103 | 3× `d.url_edit.setText(url)` + 3× `d._on_url_text_changed()` |

**Two tests in this file already pass:** `test_avatar_worker_dispatches_twitch` and `test_youtube_dispatch_passes_node_runtime` — both test `_AvatarFetchWorker` directly, not the dialog widget.

---

## The Removed Widget vs. The New Path

### What was removed (Phase 97 D-01)

`url_edit` (a `QLineEdit`) was the sole URL input widget pre-Phase-97. The `textChanged` signal drove `_on_url_text_changed`, which enabled `_refresh_avatar_btn` and started the debounced metadata refresh timer.

```python
# GONE after Phase 97
self.url_edit = QLineEdit()
form.addRow("URL:", self.url_edit)
self.url_edit.textChanged.connect(self._on_url_text_changed)
```

### What exists now

`_on_url_text_changed` is preserved as a **no-op shim** (production line 1554–1558) so any external caller does not crash:

```python
def _on_url_text_changed(self) -> None:
    # Phase 97 D-01: url_edit removed — this method is no longer directly connected to any signal.
    # It is preserved as a no-op shim so external callers (if any) do not crash.
    pass
```

`_get_canonical_url_live()` (line 1314–1325) is the authoritative URL reader:

```python
def _get_canonical_url_live(self) -> str:
    row = self._canonical_row
    if row < 0 or row >= self.streams_table.rowCount():
        return ""
    item = self.streams_table.item(row, _COL_URL)
    return item.text() if item else ""
```

`_canonical_row` is set to 0 (first stream row) during `_populate()` (line 720), then updated if the station has a `canonical_stream_id` that matches a different row. All fixture stations have `canonical_stream_id=None`, so `_canonical_row` will always be 0 after dialog construction in these tests.

The `_refresh_avatar_btn.setEnabled(is_yt or is_twitch)` call is now in three places:
1. `_populate()` lines 791 — initial state on dialog open
2. `_on_canonical_btn_clicked()` lines 1357–1365 — when star button is clicked to change canonical row
3. `_on_canonical_cell_changed()` lines 1384–1398 — when the canonical row's URL cell text changes

### How `_on_save` reads the URL [VERIFIED: source grep]

```python
# edit_station_dialog.py line 2027
_url_for_derive = self._get_canonical_url_live().strip()  # Phase 97 D-02
if "twitch.tv" in _url_for_derive.lower():
    ...
    provider_name = f"Twitch: {_login}"
```

The `_on_save` path reads exclusively from the streams table via `_get_canonical_url_live()`. It does not read from any `url_edit` attribute.

---

## Standard Stack

No new packages. This is a pure test-file migration. [ASSUMED — no package changes needed based on scope]

## Package Legitimacy Audit

Not applicable. Phase installs no packages.

---

## Architecture Patterns

### The Key Insight: Fixture Streams Pre-Populate the Table

The shared `repo` fixture in `test_twitch_provider_assign.py` (lines 42–54) provides:

```python
r.list_streams.return_value = [
    StationStream(id=10, station_id=5, url="https://www.twitch.tv/twitchdev",
                  label="", quality="hi", position=1, stream_type="", codec="MP3"),
]
```

During `EditStationDialog.__init__` → `_populate()`, this stream is loaded into `streams_table` row 0, and `_canonical_row` is set to 0. After dialog construction, `_get_canonical_url_live()` already returns `"https://www.twitch.tv/twitchdev"`. [VERIFIED: live Python session]

Similarly, `test_save_non_twitch_url_unchanged` overrides the fixture streams to `url="http://ice3.somafm.com/groovesalad-128.mp3"`, which is the same URL the test then sets via `url_edit.setText`. [VERIFIED: live Python session]

Conclusion: For all 8 tests in `test_twitch_provider_assign.py`, the `url_edit.setText(...)` lines set the same URL that the fixture already loaded. They are **purely redundant** — deleting them is sufficient. No replacement code needed.

### Migration Pattern A: Remove Redundant `url_edit.setText` (8 tests in test_twitch_provider_assign.py)

**Before:**
```python
d = EditStationDialog(station_blank_provider, player, repo, parent=None)
qtbot.addWidget(d)
d.url_edit.setText("https://www.twitch.tv/twitchdev")  # ← REMOVE THIS LINE
d.provider_combo.setCurrentText("")
```

**After:**
```python
d = EditStationDialog(station_blank_provider, player, repo, parent=None)
qtbot.addWidget(d)
# URL is pre-populated from repo.list_streams via _populate(); no url_edit needed.
d.provider_combo.setCurrentText("")
```

### Migration Pattern B: Replace `url_edit + _on_url_text_changed` with Canonical Cell (1 test)

For `test_twitch_url_enables_refresh_btn`, the test needs to change the URL to test different enable states. The reference pattern comes from existing passing tests in `test_edit_station_dialog.py` (lines 515–528, 581–596, 611–626). [VERIFIED: source grep on passing tests]

**Before (3 instances in the test body):**
```python
d.url_edit.setText("https://www.twitch.tv/twitchdev")
d._on_url_text_changed()
assert d._refresh_avatar_btn.isEnabled() is True
```

**After (reference pattern):**
```python
from musicstreamer.ui_qt.edit_station_dialog import _COL_URL
from PySide6.QtWidgets import QTableWidgetItem

row = d._canonical_row  # 0 after fixture _populate()
item = d.streams_table.item(row, _COL_URL)
if item is None:
    d.streams_table.setItem(row, _COL_URL, QTableWidgetItem("https://www.twitch.tv/twitchdev"))
else:
    item.setText("https://www.twitch.tv/twitchdev")
d._on_canonical_cell_changed(row, _COL_URL)
assert d._refresh_avatar_btn.isEnabled() is True
```

The import (`_COL_URL`, `QTableWidgetItem`) can be hoisted to the top of the test function to avoid repeating it 3 times.

**Verified working:** Live Python session confirmed this pattern produces:
- Twitch URL → `isEnabled() == True`
- YouTube URL → `isEnabled() == True`
- `http://stream.example.com/live.mp3` → `isEnabled() == False`

[VERIFIED: live Python session]

### Recommended Project Structure

No structural change. Edits are confined to:
- `tests/test_twitch_provider_assign.py` — 8 line deletions (one per test)
- `tests/test_edit_station_dialog_avatar.py` — 6 line replacements (3 `url_edit.setText` + 3 `_on_url_text_changed` → 3 `item.setText` + 3 `_on_canonical_cell_changed`), plus docstring update

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| URL injection in tests | A new `set_canonical_url(d, url)` helper | Direct `item.setText()` + `_on_canonical_cell_changed()` | Existing passing tests already use this two-liner pattern — adding a helper is over-engineering for 3 call sites |
| Triggering enable logic | Manually computing is_yt/is_twitch in tests | `_on_canonical_cell_changed(row, _COL_URL)` | This is the same method the production UI uses; testing through it validates the real gate |

---

## Common Pitfalls

### Pitfall 1: Calling the no-op `_on_url_text_changed()` and expecting it to do something
**What goes wrong:** `_on_url_text_changed()` is a no-op shim (Phase 97 D-01). Calling it after setting the canonical cell URL will NOT enable `_refresh_avatar_btn`. The test will see `isEnabled() == False` regardless of the URL.
**Why it happens:** Test was written before Phase 97; the shim was intentionally left for backward compatibility with any external callers but the internal enable logic moved to `_on_canonical_cell_changed`.
**How to avoid:** Use `_on_canonical_cell_changed(row, _COL_URL)` to trigger the enable gate. Confirm with: `grep -n "_on_url_text_changed" musicstreamer/ui_qt/edit_station_dialog.py` → shows only the shim and a comment.
**Warning signs:** `assert d._refresh_avatar_btn.isEnabled() is True` fails after calling `_on_url_text_changed`.

### Pitfall 2: Calling `_on_canonical_cell_changed` with wrong row or column
**What goes wrong:** `_on_canonical_cell_changed` has an early-exit guard: `if row != self._canonical_row or col != _COL_URL: return`. Passing the wrong row or col silently no-ops the enable logic.
**Why it happens:** The guard prevents spurious fires from non-canonical row edits.
**How to avoid:** Always call `d._on_canonical_cell_changed(d._canonical_row, _COL_URL)`. Since all test fixture stations have `canonical_stream_id=None`, `_canonical_row == 0` after construction. Both must be correct.

### Pitfall 3: `_on_canonical_cell_changed` also starts `_url_timer`
**What goes wrong:** Calling `_on_canonical_cell_changed` starts a 500ms `_url_timer` that will later fire `_on_url_timer_timeout`, spawning a `_LogoFetchWorker` and potentially a `_AvatarFetchWorker`. In most of the migrated tests, this is harmless because assertions are synchronous and the timer won't fire before them. But if a test does a `qtbot.wait(600)` or similar, the timer may fire and interfere.
**Why it happens:** `_on_canonical_cell_changed` mirrors `_on_canonical_btn_clicked` behavior, which includes the debounced refresh.
**How to avoid:** For purely synchronous enable-state tests, add `d._url_timer.stop()` after `_on_canonical_cell_changed()`. The existing `test_logo_status_clears_after_3s` and `test_text_changed_cancels_pending_clear` tests already demonstrate this defensive pattern.
**Warning signs:** Flaky test behavior if the test later calls `qtbot.wait()`.

### Pitfall 4: The `_populating` guard silently blocks `_on_canonical_cell_changed`
**What goes wrong:** If `_on_canonical_cell_changed` is called while `_populating=True`, it exits immediately. The guard is active during `_populate()` to prevent spurious fires, but it is always False by the time the test body runs (set back to False in the `finally` block of `_populate`).
**Why it happens:** Guard exists to suppress cellChanged during programmatic stream row insertion.
**How to avoid:** No action needed — `_populating` is always False by the time `qtbot.addWidget(d)` returns.

### Pitfall 5: Qt test runner — must use `.venv/bin/python`
**What goes wrong:** `python3 -m pytest` on the system Python lacks PySide6.QtWidgets and produces false `ImportError` failures.
**How to avoid:** Always use `.venv/bin/python -m pytest` per project memory. [ASSUMED — from project memory `run-tests-with-venv-python.md`]

### Pitfall 6: Don't accidentally break the two already-passing source-grep tests
**What goes wrong:** `test_save_source_has_twitch_derivation` and `test_on_save_has_inmemory_provider_assignment` are source-grep tests that inspect `edit_station_dialog.py` source code. Editing those tests would change coverage scope.
**How to avoid:** Leave lines 68–97 and 444–465 of `test_twitch_provider_assign.py` untouched. Only modify the 8 lines containing `d.url_edit.setText(...)`.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (via `.venv`) |
| Config file | `pyproject.toml` |
| Quick run command | `.venv/bin/python -m pytest tests/test_twitch_provider_assign.py tests/test_edit_station_dialog_avatar.py -q` |
| Full suite command | `.venv/bin/python -m pytest` (>600s — scope to affected files for iteration) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TEST-REGRESSION-97x89B | 9 failing tests migrate to streams-table URL path; 9 → 0 failures | unit (existing) | `.venv/bin/python -m pytest tests/test_twitch_provider_assign.py tests/test_edit_station_dialog_avatar.py::test_twitch_url_enables_refresh_btn -q` | Yes (tests exist; need edit) |

### Sampling Rate
- **Per task commit:** `.venv/bin/python -m pytest tests/test_twitch_provider_assign.py tests/test_edit_station_dialog_avatar.py -q`
- **Per wave merge:** Same (single-wave phase)
- **Phase gate:** All 9 previously-failing tests green; 4 previously-passing tests still green (11 total PASS); no new failures

### Wave 0 Gaps

None — test infrastructure already exists. The tests only need line-level edits, not new files or framework setup.

---

## Code Examples

### Pattern A — Verified migration for `test_save_derives_provider_for_blank_twitch`

Before (line 116, fails):
```python
d.url_edit.setText("https://www.twitch.tv/twitchdev")
```

After (delete that line; URL already in streams table from fixture):
```python
# (line deleted — url pre-loaded from repo.list_streams via _populate)
```

The `repo.list_streams.return_value` in the `repo` fixture (lines 47–51) contains `url="https://www.twitch.tv/twitchdev"`. After `_populate()`, `_get_canonical_url_live()` returns that URL. `_on_save` at line 2027 reads it correctly.

### Pattern B — Verified migration for `test_twitch_url_enables_refresh_btn`

Before (lines 87–103, fails):
```python
d.url_edit.setText("https://www.twitch.tv/twitchdev")
d._on_url_text_changed()
assert d._refresh_avatar_btn.isEnabled() is True, (
    "Refresh button should be enabled for twitch.tv URL — "
    "dispatch gate not yet added to _on_url_text_changed"
)

d.url_edit.setText("https://www.youtube.com/@lofiirl")
d._on_url_text_changed()
assert d._refresh_avatar_btn.isEnabled() is True, (
    "Refresh button should remain enabled for youtube.com URL"
)

d.url_edit.setText("http://stream.example.com/live.mp3")
d._on_url_text_changed()
assert d._refresh_avatar_btn.isEnabled() is False, (
    "Refresh button should be disabled for non-avatar-capable URL"
)
```

After (use canonical cell + `_on_canonical_cell_changed`):
```python
from musicstreamer.ui_qt.edit_station_dialog import _COL_URL
from PySide6.QtWidgets import QTableWidgetItem

row = d._canonical_row  # 0 — fixture stream at row 0

# Twitch URL should enable refresh
d.streams_table.item(row, _COL_URL).setText("https://www.twitch.tv/twitchdev")
d._on_canonical_cell_changed(row, _COL_URL)
assert d._refresh_avatar_btn.isEnabled() is True, (
    "Refresh button should be enabled for twitch.tv URL"
)

# YouTube URL should still enable refresh (regression guard)
d.streams_table.item(row, _COL_URL).setText("https://www.youtube.com/@lofiirl")
d._on_canonical_cell_changed(row, _COL_URL)
assert d._refresh_avatar_btn.isEnabled() is True, (
    "Refresh button should remain enabled for youtube.com URL"
)

# Unrelated URL should disable refresh
d.streams_table.item(row, _COL_URL).setText("http://stream.example.com/live.mp3")
d._on_canonical_cell_changed(row, _COL_URL)
assert d._refresh_avatar_btn.isEnabled() is False, (
    "Refresh button should be disabled for non-avatar-capable URL"
)
```

Note: the `item()` call at each step is safe because the `twitch_dialog` fixture creates a dialog with one stream row (`url="http://s1.mp3"`) — row 0 always has a non-None item. The `if item is None: setItem(...)` guard from the passing-test pattern is defensive but not needed here. [VERIFIED: live Python session]

The docstring of `test_twitch_url_enables_refresh_btn` should also be updated to replace the reference to `url_edit` and `_on_url_text_changed` with the new mechanism.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `url_edit.setText` + `_on_url_text_changed()` in tests | `streams_table.item(row, _COL_URL).setText()` + `_on_canonical_cell_changed(row, _COL_URL)` | Phase 97 D-01 | Tests must use streams-table API; `url_edit` does not exist; `_on_url_text_changed` is a no-op |
| Single `url_edit` drives all URL-based state | `_canonical_row` tracks which stream row is the metadata anchor; its URL cell drives all consumers | Phase 97 D-04 | Multiple stream rows possible; canonical marker (star button) identifies which row |

**Deprecated/outdated:**
- `url_edit`: removed, attribute does not exist on `EditStationDialog`
- `_on_url_text_changed()`: preserved as no-op shim only; calling it in tests achieves nothing

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `d._canonical_row == 0` after fixture construction in all 9 failing tests (no `canonical_stream_id` set on fixture stations) | Migration Pattern, Code Examples | If a station has `canonical_stream_id` set, `_canonical_row` could be non-zero; would require reading `d._canonical_row` dynamically. Verified for all fixtures inspected; LOW risk. |
| A2 | No other test files outside `test_twitch_provider_assign.py` and `test_edit_station_dialog_avatar.py` reference `url_edit` | Scope | If other tests also reference `url_edit`, the failing count would be higher; the audit found exactly 9. |

All other claims were verified by direct source inspection or live execution.

---

## Open Questions (RESOLVED)

1. **RESOLVED: Should the docstring of `test_twitch_url_enables_refresh_btn` be updated?** → Yes. Plan 99-01 Task 2 updates the docstring to describe the streams-table / `_on_canonical_cell_changed` mechanism (same diff).
   - What we know: the docstring says "After setting url_edit to a twitch.tv URL and triggering `_on_url_text_changed`..." which describes the pre-Phase-97 mechanism
   - What's unclear: planner preference — minimal change (only fix the failing code) vs. keep documentation accurate
   - Recommendation: update the docstring to describe the new mechanism; it's in the same diff and prevents future confusion about how the test works

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `.venv/bin/python` with PySide6 | All test runs | Yes | PySide6 6.11.0, Qt 6.11.0 | None — required per project memory |
| `pytest` (via venv) | Test execution | Yes | pytest 9.0.3 | — |

Step 2.6: No external service dependencies. Test edits only.

---

## Sources

### Primary (HIGH confidence)
- `musicstreamer/ui_qt/edit_station_dialog.py` — lines 279, 285, 432–449, 663–795, 1314–1403, 1554–1558, 2020–2033 — source-grep verified
- `tests/test_twitch_provider_assign.py` — 10 tests; 8 failing enumerated with exact lines
- `tests/test_edit_station_dialog_avatar.py` — 3 tests; 1 failing with exact lines
- `tests/test_edit_station_dialog.py` — reference migration pattern from lines 515–528, 581–596, 611–626 (already-passing tests post-Phase-97)
- Live Python session: confirmed `_get_canonical_url_live()` returns fixture URL after dialog construction; confirmed Pattern B produces correct enable states

### Secondary (MEDIUM confidence)
- `.planning/v2.2-MILESTONE-AUDIT.md` — gap `TEST-REGRESSION-97x89B` description and fix recommendation
- `.planning/STATE.md` — Phase 97 D-01, D-02, D-04 decisions

---

## Metadata

**Confidence breakdown:**
- Failing tests enumeration: HIGH — live test run confirms all 9 names and lines
- Migration pattern A (delete redundant lines): HIGH — fixture URL verified via live Python session
- Migration pattern B (canonical cell + `_on_canonical_cell_changed`): HIGH — tested live; button enable verified for all 3 URL scenarios
- Pitfalls: HIGH — derived from direct source inspection of the no-op shim, `_populating` guard, and `_url_timer` behavior

**Research date:** 2026-06-28
**Valid until:** Indefinite (stable — no external dependencies; fails only if `EditStationDialog` internals change again)
