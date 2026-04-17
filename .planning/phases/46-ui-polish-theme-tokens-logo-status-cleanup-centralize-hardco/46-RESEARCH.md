# Phase 46: UI polish — theme tokens + logo status cleanup - Research

**Researched:** 2026-04-17
**Domain:** PySide6/Qt desktop — token extraction + QTimer/cursor-override UX polish
**Confidence:** HIGH (code-only cleanup; all idioms already used elsewhere in the codebase)

## Summary

Phase 46 is a tight cleanup phase with all decisions pre-locked in `46-CONTEXT.md`. Scope: (a) extract `#c0392b` from 10 sites and `QSize(32, 32)` from 3 sites into `musicstreamer/ui_qt/_theme.py`; (b) distinguish two failure messages in `EditStationDialog._LogoFetchWorker`; (c) add a 3s-or-textChanged auto-clear on `_logo_status`; (d) wrap the fetch worker in `QApplication.setOverrideCursor(Qt.WaitCursor)` paired with `restoreOverrideCursor` in both finished and error paths; (e) keep the existing `audio-x-generic-symbolic` fallback.

All Qt idioms in this plan are already used elsewhere in the codebase (`QTimer.singleShot` — 5 call sites in player.py/__main__.py; `setOverrideCursor/restoreOverrideCursor` — `main_window.py:398/403`; `blockSignals` — already used in `accent_color_dialog.py:127,146,190` and `import_dialog.py:323`). The plan is mechanical with three behavioral gotchas (QTimer ownership, cursor stack semantics, textChanged reentrance during programmatic `setText("")`) flagged below.

**Primary recommendation:** Plan the phase in two waves — (1) create `_theme.py` and migrate all 13 call sites (10 hex + 3 QSize); (2) implement the `EditStationDialog` behavioral changes (AA-URL distinction, auto-clear timer, cursor override). Wave 1 is pure mechanical refactor with grep-based regression assertions; Wave 2 carries all the Qt lifecycle risk.

## User Constraints (from CONTEXT.md)

### Locked Decisions

**Theme Token Module**
- **D-01:** Create `musicstreamer/ui_qt/_theme.py` (mirror `_art_paths.py` convention — underscore-prefixed, module-level constants).
- **D-02:** Export `ERROR_COLOR` as BOTH a hex string and a `QColor` (e.g., `ERROR_COLOR_HEX` + `ERROR_COLOR_QCOLOR`, names at Claude's discretion) to avoid callers constructing QColor repeatedly.
- **D-03:** Migrate all 10 hardcoded `#c0392b` sites (5 in `import_dialog.py`, 1 each in `edit_station_dialog.py`, `cookie_import_dialog.py`, `accent_color_dialog.py`, 2 in `settings_import_dialog.py`). Fold the existing `_ERROR_COLOR` in `settings_import_dialog.py:46` into the shared token.
- **D-04:** No QPalette/QSS migration — direct imports only.

**Dark Mode**
- **D-05:** Not implemented. This phase only unblocks it by ending the hex-literal pattern.

**Station Icon Size**
- **D-06:** `STATION_ICON_SIZE = 32` lives in `_theme.py` (not `_art_paths.py`). Update `load_station_icon` default arg. Migrate 3 `setIconSize(QSize(32, 32))` sites.

**Logo Fetch Status**
- **D-07:** Two distinct messages: `"AudioAddict station — use Choose File to supply a logo"` vs `"Fetch not supported for this URL"`.
- **D-08:** Classification lives inside `_LogoFetchWorker.run` (or a helper called from there). No new network calls — URL parse only.
- **D-09:** Auto-clear `_logo_status` — whichever fires first wins. 3s `QTimer.singleShot` on success/failed/unsupported transitions, OR immediate clear on `QLineEdit.textChanged`. Timer stored on `self._logo_status_clear_timer` so it can be cancelled.

**Fetch-in-Flight Indicator**
- **D-10:** `QApplication.setOverrideCursor(Qt.WaitCursor)` at worker dispatch; `QApplication.restoreOverrideCursor()` in finished/error handlers. No new widgets, no spinner.
- **D-11:** Restore must pair 1:1 with override — try/finally in calling slot OR restore in BOTH finished and error slots (never both if only one override happened).

**Empty-State Glyph**
- **D-12:** Reuse existing `audio-x-generic-symbolic` fallback. No new asset.

### Claude's Discretion

- Constant names in `_theme.py` (e.g., `ERROR_COLOR` vs `ERROR_RED`, `STATION_ICON_SIZE` vs `ICON_SIZE_STATION`). Pick a consistent convention.
- Whether to expose a small helper (`error_stylesheet()`). Lean toward inline formatting at call sites.
- Whether to keep a backwards-compat `_ERROR_COLOR` alias in `settings_import_dialog.py` — preference is NO, delete the local.
- Test coverage scope — unit test `_theme.py` exports; behavioral test timer cancellation on `textChanged`; no test for cursor override (stateful Qt global).

### Deferred Ideas (OUT OF SCOPE)

- Dark-mode / palette switching / Qt.ColorScheme detection
- QSS stylesheet migration (per-widget → app-wide QSS file)
- `now_playing_panel._FALLBACK_ICON` dedup (different use — cover art slot)
- A11y mnemonics sweep
- `EditStationDialog.closeEvent/reject` 2s hang during fetch (D-10 only covers the in-flight path, not the discard-while-fetching path)
- Toast + inline label duplication on import complete

## Project Constraints (from CLAUDE.md)

No project-level `CLAUDE.md` constraints affect this phase directly. User-global `~/.claude/CLAUDE.md` Developer Profile directs:
- **Communication:** terse, concise, no preambles
- **Decisions:** single recommended option, fast
- **UX Philosophy:** pragmatic — include basic usability (status indicators, readable output) but no visual polish without request. This phase fits that profile — it's polishing what already exists, not adding decoration.

## Existing Patterns

The three Qt idioms this phase needs all have precedent in the codebase:

### 1. QTimer Lifecycle — parented QTimer with `timeout.connect` (preferred over `QTimer.singleShot` for cancellable timers)

`edit_station_dialog.py:209-213` shows the pattern already used for the URL debounce:

```python
self._url_timer = QTimer()                # no parent arg — will leak if dialog dies
self._url_timer.setSingleShot(True)
self._url_timer.setInterval(500)
self.url_edit.textChanged.connect(self._on_url_text_changed)
self._url_timer.timeout.connect(self._on_url_timer_timeout)
```

For the auto-clear timer, prefer the parented form (`QTimer(self)`) so the timer is a child of the dialog and gets cleaned up with it. Cancel via `timer.stop()` before restarting or on `textChanged`. Do NOT use `QTimer.singleShot(ms, callable)` for this case — the free function returns no handle, so there's no way to cancel a pending fire when `textChanged` arrives first.

**Reference for singleShot usage (non-cancellable):** `player.py:252,269,438,446` and `__main__.py:62` — all pass `0` ms as a deferred-dispatch mechanism, not a real wait.

### 2. Cursor Override — `setOverrideCursor` / `restoreOverrideCursor`

`main_window.py:397-405` is the canonical pattern:

```python
def _begin_busy(self) -> None:
    QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
    self._act_export.setEnabled(False)
    self._act_import_settings.setEnabled(False)

def _end_busy(self) -> None:
    QApplication.restoreOverrideCursor()
    self._act_export.setEnabled(True)
    self._act_import_settings.setEnabled(True)
```

Key details: `QApplication.setOverrideCursor` is a **class method**, not instance — no need to resolve `QApplication.instance()`. Accepts either `QCursor(Qt.WaitCursor)` or just `Qt.WaitCursor` (Qt auto-wraps). D-10's "no new widgets" constraint means the cursor is the only affordance — keep it paired 1:1 with the single override call.

### 3. QLabel stylesheet formats

Both forms are already in use and both will need to consume the new token:

- **Hex string form** (10 of 10 current sites): `setStyleSheet("color: #c0392b;")` — takes a raw hex string. Requires the **hex constant** from `_theme.py`.
- **QColor form** (1 current site at `settings_import_dialog.py:179-180`): `item.setForeground(0, _ERROR_COLOR)` where `_ERROR_COLOR = QColor("#c0392b")` — requires the **QColor constant**.

This confirms D-02 (two constants are required): a QColor cannot be inlined into a QSS string, and a hex string cannot be passed to `setForeground`.

### 4. blockSignals around programmatic setText

`accent_color_dialog.py:127-129, 146-148, 190-192` and `import_dialog.py:323,331` all use `widget.blockSignals(True) / setText(...) / blockSignals(False)` when a slot mutates the same widget whose signal triggered the slot. Directly relevant to the auto-clear behavior — see Pitfall 3 below.

## Technical Gotchas

### G-1: QTimer ownership — use `QTimer(self)`, never orphan

A bare `QTimer()` has no parent; if the dialog closes while the timer is pending, Qt may still fire the callback against a partially-destroyed dialog. Pattern:

```python
self._logo_status_clear_timer = QTimer(self)          # parent = dialog
self._logo_status_clear_timer.setSingleShot(True)
self._logo_status_clear_timer.setInterval(3000)
self._logo_status_clear_timer.timeout.connect(self._clear_logo_status)
```

Existing `self._url_timer = QTimer()` at `edit_station_dialog.py:209` is technically the leakier form — but since it IS assigned to `self`, Python keeps the object alive and Qt keeps the connection, so the pattern works. Still, **for the new timer, prefer `QTimer(self)`** — cheap insurance.

### G-2: `QApplication.setOverrideCursor` has stack semantics

Each `setOverrideCursor` call **pushes** onto an app-wide stack; each `restoreOverrideCursor` **pops** one level. Two overrides + one restore leaves the app with a wait cursor forever. Two restores after one override leaves the underlying cursor stack damaged (non-fatal but can leak into other dialogs).

D-10/D-11 decision: restore in BOTH `finished` AND `error` — but this requires that **exactly one** of them fires per override, OR you `try/finally` around the start slot. The `_LogoFetchWorker` has a single `finished = Signal(str, int)`, so the existing `_on_logo_fetched` is the sole callback (no separate `error` signal). Thus only one restore path: add `QApplication.restoreOverrideCursor()` at the top of `_on_logo_fetched` (both the stale-token early return AND the real completion paths must restore, or restore BEFORE the stale-token branch). The CONTEXT wording "both finished and error slots" is a template — for this specific worker it's "both branches of the one finished slot."

**Also critical:** stale-token early return at `edit_station_dialog.py:502-508` — if a new fetch was started before the prior finished fired, the token mismatch triggers an early return. The SECOND override (from the new fetch) still needs a matching restore, and the FIRST fetch's stale-finished must still restore (for its own override). In other words: every `setOverrideCursor` must be paired, regardless of token freshness. Recommended: restore at the very top of `_on_logo_fetched`, unconditionally. If you restore only after the stale-token branch, every stale emission leaks a cursor.

### G-3: `textChanged` fires on programmatic `setText("")`

`QLineEdit.textChanged` fires every time the text changes, including when the code itself calls `setText("")`. But the `_logo_status` is a `QLabel`, not a `QLineEdit` — `QLabel.setText` does NOT emit `textChanged` (QLabel has no such signal). So the clear helper (`self._logo_status.setText("")` or `.clear()`) cannot recurse into itself.

The real concern is different: D-09 wires `self.url_edit.textChanged` to immediately clear `_logo_status` AND cancel the pending timer. The existing `textChanged` connection at line 212 debounces a fetch via `self._url_timer.start()`. Your new handler must coexist with that one. Two options:

1. **Add a second slot** connected to the same signal — Qt supports multiple slots on one signal; both fire.
2. **Augment the existing `_on_url_text_changed` slot** to also clear status + cancel clear-timer.

Option 2 is simpler and keeps the signal wiring in one place. The programmatic `.setText()` calls in `_populate` (line 318, which runs during init) will also trigger `textChanged` → debounce → fetch. That's the EXISTING behavior; do not try to suppress it, since the current tests assume it. But confirm that adding a status-clear here does not break any existing test (it shouldn't, since label starts empty).

**Subtle edge case:** the `_on_logo_fetched` success branch sets `self._logo_status.setText("Fetched")` AFTER `_refresh_logo_preview`. If the user types a new URL while the fetch is running, `textChanged` clears the label — then the in-flight fetch finishes and writes `"Fetched"` back in. This race exists in the current code too; D-09's timer-cancellation semantics don't fully fix it. Mitigation: the fetch-finish handler could check if its token is still current (which it already does) and skip the status write on stale. But CONTEXT doesn't require this; flag for plan discussion only.

### G-4: QColor instance is mutable shared state — safe at module level but be explicit

A module-level `QCOLOR_ERROR = QColor("#c0392b")` is fine because `setForeground` internally copies the color value (Qt value-type semantics). No risk of one caller mutating another's color. The existing `_ERROR_COLOR = QColor("#c0392b")` at `settings_import_dialog.py:46` relies on this already.

### G-5: No pre-existing token collisions

Grep confirms: there is no existing `_theme.py` in `musicstreamer/ui_qt/`, no existing `STATION_ICON_SIZE` constant, and no existing `ERROR_COLOR` export anywhere in `musicstreamer/`. `_ERROR_COLOR = QColor("#c0392b")` at `settings_import_dialog.py:46` is the ONE pre-existing local token that this phase folds into the shared module. Safe to create.

### G-6: `_LogoFetchWorker.run` has a broad `except Exception` that swallows ALL failures

Current code at `edit_station_dialog.py:107-108`:

```python
except Exception:
    self.finished.emit("", token)
```

Any exception (network error, yt_dlp failure, AA fetch failure, or classification logic bug) emits `("", token)` — which `_on_logo_fetched` reads as `tmp_path == ""` and falls into the "Fetch failed / Fetch not supported" branch based on URL classification at lines 512-518. The AA-URL distinction (D-07) needs to preserve this: when classification decides "AA URL but no channel key," emit a sentinel or set an instance flag BEFORE the exception handler could fire. Recommended approach: **perform classification BEFORE network calls**; if it resolves to "AA-no-key," emit `("", token)` cleanly and set a flag (e.g., `self._classification = "aa_no_key"`) the slot reads. Alternative: widen the signal to `finished = Signal(str, int, str)` where the third arg carries the classification status. CONTEXT says D-08 is at Claude's discretion on the exact mechanism — plan can pick.

### G-7: `_on_logo_fetched` is the only finished-slot — "error slot" does not exist

CONTEXT wording "restore in BOTH finished AND error slots" is a template. The worker has only `finished = Signal(str, int)`. There is no separate error signal. Plan should state explicitly: restore in `_on_logo_fetched` at top, unconditionally (before the stale-token early return). This covers success, fetch failure, unsupported URL, AA-no-key, and stale-token cases.

### G-8: `_on_logo_fetched` signature stability — test compat

Existing test `tests/test_edit_station_dialog.py:362` calls `dialog._on_logo_fetched(str(fetched))` with no token arg — relies on the `token: int = 0` default. When adding the auto-clear timer start here, preserve the defaulted `token` arg so the test keeps passing. Similarly, the test `test_auto_fetch_worker_starts_on_url_change` at line 325 patches `_LogoFetchWorker` with a MagicMock; `_on_url_timer_timeout` invokes `worker.start()` — the new `setOverrideCursor` call should happen at that same site (the dispatch slot, NOT inside the worker thread — see D-11 and G-2).

## Call-Site Migration Map

Grep-verified against the working tree (`musicstreamer/` only, excluding worktrees under `.claude/`).

### ERROR_COLOR — 10 sites (exactly matches CONTEXT inventory, no missed sites)

| File | Line | Form | Notes |
|------|------|------|-------|
| `musicstreamer/ui_qt/settings_import_dialog.py` | 46 | `_ERROR_COLOR = QColor("#c0392b")` | Module-level. **Delete** and import `ERROR_COLOR_QCOLOR` from `_theme`. |
| `musicstreamer/ui_qt/settings_import_dialog.py` | 140 | `"color: #c0392b; font-size: 9pt;"` (multi-line QSS string) | Hex form. |
| `musicstreamer/ui_qt/edit_station_dialog.py` | 131 | `_DELETE_BTN_QSS = "QPushButton { color: #c0392b; }"` | Module-level constant. Either inline or keep the name and build from token. |
| `musicstreamer/ui_qt/cookie_import_dialog.py` | 106 | `setStyleSheet("color: #c0392b;")` | Hex form. |
| `musicstreamer/ui_qt/import_dialog.py` | 264 | `setStyleSheet("color: #c0392b;")` | Hex form. `_aa_status` initial style. |
| `musicstreamer/ui_qt/import_dialog.py` | 292 | `setStyleSheet("color: #c0392b;")` | Hex form. YT invalid URL. |
| `musicstreamer/ui_qt/import_dialog.py` | 339 | `setStyleSheet("color: #c0392b;")` | Hex form. YT scan error. |
| `musicstreamer/ui_qt/import_dialog.py` | 433 | `setStyleSheet("color: #c0392b;")` | Hex form. AA fetch error. |
| `musicstreamer/ui_qt/import_dialog.py` | 466 | `setStyleSheet("color: #c0392b;")` | Hex form. AA import error. |
| `musicstreamer/ui_qt/accent_color_dialog.py` | 166 | `setStyleSheet("border: 1px solid #c0392b;")` | Hex form — border color, not `color:`. |

**Count: 10. Matches CONTEXT §Canonical References exactly. No sites missed.**

### STATION_ICON_SIZE — 3 source sites + 2 test-assertion sites

| File | Line | Current | Migration |
|------|------|---------|-----------|
| `musicstreamer/ui_qt/station_list_panel.py` | 151 | `self.recent_view.setIconSize(QSize(32, 32))` | `setIconSize(QSize(STATION_ICON_SIZE, STATION_ICON_SIZE))` |
| `musicstreamer/ui_qt/station_list_panel.py` | 257 | `self.tree.setIconSize(QSize(32, 32))` | Same |
| `musicstreamer/ui_qt/favorites_view.py` | 97 | `self._stations_list.setIconSize(QSize(32, 32))` | Same |
| `musicstreamer/ui_qt/_art_paths.py` | 47 | `def load_station_icon(station, size: int = 32) -> QIcon:` | Default arg becomes `STATION_ICON_SIZE`. **Import-cycle caution:** `_art_paths.py` currently does not import from `_theme`. One-way dependency (`_art_paths` → `_theme`) is fine; no cycle. |

**Test assertion sites** (NOT code — these will need test updates):

| File | Line | Current | Expected post-migration |
|------|------|---------|------------------------|
| `tests/test_station_list_panel.py` | 98 | `assert panel.tree.iconSize() == QSize(32, 32)` | Still passes (constant value unchanged). But a grep assertion "no `QSize(32, 32)` in source" will trip if this test line is still literal. **Do not change the test** — it's asserting against the widget's actual iconSize property, not against the source text. The grep should be scoped to `musicstreamer/ui_qt/` only, not `tests/`. |
| `tests/test_station_list_panel.py` | 208 | `assert panel.recent_view.iconSize() == QSize(32, 32)` | Same. |

### Locations the CONTEXT did NOT mention but grep found

None. CONTEXT inventory is complete.

## Validation Architecture

Nyquist validation is enabled (`workflow.nyquist_validation: true` in `.planning/config.json`).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9+ with pytest-qt 4+ (already installed per `pyproject.toml:21-22`) |
| Config file | `pyproject.toml` §`[tool.pytest.ini_options]` (testpaths = `["tests"]`) |
| Quick run command | `.venv/bin/python -m pytest tests/test_theme.py tests/test_edit_station_dialog.py -x` |
| Full suite command | `.venv/bin/python -m pytest -x` |

### Phase Requirements → Test Map

| ID | Behavior | Test Type | Automated Command | File Exists? |
|----|----------|-----------|-------------------|-------------|
| P46-T1 | `_theme.py` exports `ERROR_COLOR_HEX` as `str` starting with `#` | unit | `pytest tests/test_theme.py::test_error_color_hex_is_string -x` | Wave 0 (new file) |
| P46-T2 | `_theme.py` exports `ERROR_COLOR_QCOLOR` as `QColor` | unit | `pytest tests/test_theme.py::test_error_color_qcolor_is_qcolor -x` | Wave 0 |
| P46-T3 | `_theme.py` exports `STATION_ICON_SIZE` as `int == 32` | unit | `pytest tests/test_theme.py::test_station_icon_size_is_32 -x` | Wave 0 |
| P46-T4 | Zero occurrences of raw `#c0392b` in `musicstreamer/ui_qt/` except `_theme.py` itself | grep-assertion | `pytest tests/test_theme.py::test_no_raw_error_hex_outside_theme -x` (or shell-based check) | Wave 0 |
| P46-T5 | Zero occurrences of `QSize(32, 32)` in `station_tree_model.py`, `favorites_view.py`, `station_list_panel.py` | grep-assertion | `pytest tests/test_theme.py::test_no_raw_icon_size_in_migrated_sites -x` | Wave 0 |
| P46-T6 | `_LogoFetchWorker` emits distinct classification for AA-no-key URL vs unsupported URL | unit | `pytest tests/test_edit_station_dialog.py::test_aa_url_no_key_shows_aa_message -x` | Wave 0 (extend existing) |
| P46-T7 | `_logo_status` label cleared 3s after fetch completes | behavioral (pytest-qt `qtbot.wait`) | `pytest tests/test_edit_station_dialog.py::test_logo_status_clears_after_3s -x` | Wave 0 |
| P46-T8 | Typing in `url_edit` immediately clears `_logo_status` AND cancels pending clear timer | behavioral | `pytest tests/test_edit_station_dialog.py::test_text_changed_cancels_pending_clear -x` | Wave 0 |
| P46-T9 | AA-URL classification message text is exactly the one in D-07 | unit | `pytest tests/test_edit_station_dialog.py::test_aa_no_key_message_string -x` | Wave 0 |
| P46-T10 | Existing `_on_logo_fetched` callback still accepts a single-arg call (token defaults) | regression | `pytest tests/test_edit_station_dialog.py::test_auto_fetch_completion_copies_via_assets -x` | ✅ exists at line 346 |

**Cursor override is explicitly NOT tested** (per CONTEXT §Claude's Discretion — stateful Qt global; `QApplication.overrideCursor()` can be read but would couple the test to Qt internals for dubious return). Plan may skip this.

### Sampling Rate

- **Per task commit:** `.venv/bin/python -m pytest tests/test_theme.py tests/test_edit_station_dialog.py -x` (~5 seconds)
- **Per wave merge:** `.venv/bin/python -m pytest tests/test_theme.py tests/test_edit_station_dialog.py tests/test_art_paths.py tests/test_station_list_panel.py -x` (covers migration-affected test files, ~30 seconds)
- **Phase gate:** `.venv/bin/python -m pytest -x` — full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_theme.py` — new file covering token exports (3 unit tests) + grep-based regression guards (2 assertions). Framework: pytest, no qtbot needed for hex/int assertions; `QApplication.instance()` needed for QColor construction (existing fixture via conftest.py autouse).
- [ ] Extend `tests/test_edit_station_dialog.py` — add 4 tests (T6, T7, T8, T9) for behavioral changes. Uses existing `qtbot` and `dialog` fixtures.
- [ ] No framework install needed — pytest-qt already installed (`pyproject.toml:22`).
- [ ] No shared fixtures needed — `qtbot` is pytest-qt's built-in; `dialog` fixture exists at `tests/test_edit_station_dialog.py:56`.

**Grep-based assertion recipe** (for P46-T4, P46-T5):

```python
# In tests/test_theme.py
from pathlib import Path
UI_QT = Path(__file__).parent.parent / "musicstreamer" / "ui_qt"

def test_no_raw_error_hex_outside_theme():
    """No file in musicstreamer/ui_qt/ (except _theme.py) may contain #c0392b."""
    offenders = []
    for py in UI_QT.glob("*.py"):
        if py.name == "_theme.py":
            continue
        text = py.read_text()
        if "#c0392b" in text:
            offenders.append(str(py))
    assert not offenders, f"Raw hex found in: {offenders}"

def test_no_raw_icon_size_in_migrated_sites():
    for name in ("station_tree_model.py", "favorites_view.py", "station_list_panel.py"):
        text = (UI_QT / name).read_text()
        # Allow the import line; reject literal QSize(32, 32) call-sites.
        # Tolerate multiline (different whitespace) via regex.
        import re
        assert not re.search(r"QSize\(\s*32\s*,\s*32\s*\)", text), f"Raw QSize in {name}"
```

## Pitfalls

### Pitfall P-1: Cursor stack leak on stale-token path

**What goes wrong:** New fetch starts → `setOverrideCursor` (push 1) → user types again → new fetch starts → `setOverrideCursor` (push 2) → prior fetch's `finished` fires → early-return on stale token → no restore → cursor stack leaks by 1. Eventually every stale fetch leaks a level, cursor is wait-forever.

**Why it happens:** D-11 says "restore in finished/error slots" but the stale-token early return at current line 502-508 bypasses the rest of the slot.

**How to avoid:** Call `QApplication.restoreOverrideCursor()` at the VERY TOP of `_on_logo_fetched`, before the stale-token check. Every override has a matching restore regardless of token freshness.

### Pitfall P-2: Forgetting that `_on_logo_fetched` runs for BOTH success and failure (and stale)

**What goes wrong:** Planner reads D-11 as "one restore in finished, one in error" and duplicates the `restoreOverrideCursor` call — producing a double-restore when `_on_logo_fetched` is the only slot. Result: cursor stack under-popped.

**How to avoid:** Plan must explicitly state: there is NO separate error signal on `_LogoFetchWorker`. The restore happens EXACTLY ONCE, at the top of `_on_logo_fetched`. See G-7.

### Pitfall P-3: `QTimer.singleShot(3000, lambda: self._logo_status.clear())` is not cancellable

**What goes wrong:** If the planner uses the free-function form `QTimer.singleShot(3000, slot)`, there is no timer handle. When `textChanged` fires at 500ms and the code wants to cancel the pending clear, there's no way to stop it. The clear still fires at 3000ms, wiping any status the user's new URL produced.

**How to avoid:** Use the attribute-stored pattern per D-09 — `self._logo_status_clear_timer = QTimer(self); setSingleShot; setInterval; timeout.connect`. Start via `.start()`, cancel via `.stop()`, restart via another `.start()` (auto-resets elapsed time).

### Pitfall P-4: AA classification triggers before D-07 branch in the `except Exception`

**What goes wrong:** `_LogoFetchWorker.run` has a broad `except Exception` at line 107. If the AA classification code raises (e.g., malformed URL), it falls through to `self.finished.emit("", token)` without the AA-no-key sentinel — and `_on_logo_fetched` shows "Fetch not supported for this URL" instead of the AA-distinctive message.

**How to avoid:** Do URL classification BEFORE any network call or potentially-raising logic. If classification says "AA URL," set a sentinel (instance attr on the worker, OR a 3rd signal arg) BEFORE the try/except wraps network I/O. The slot reads the sentinel even on emission from the exception branch.

### Pitfall P-5: `_on_logo_fetched` is called from tests without a token arg

**What goes wrong:** Adding a required parameter to `_on_logo_fetched` breaks `tests/test_edit_station_dialog.py:362` which calls `dialog._on_logo_fetched(str(fetched))` positionally. Any new behavior must preserve the `token: int = 0` default.

**How to avoid:** Add new state via instance attributes (`self._logo_status_clear_timer.start()` etc.) rather than new required args. If a new signal arg is added (for the AA-no-key sentinel), default it in the handler too.

### Pitfall P-6: `_populate` fires `textChanged` on dialog open → triggers clear-timer logic

**What goes wrong:** `_populate` at line 318 calls `self.url_edit.setText(streams[0].url)`, which fires `textChanged`, which triggers the NEW auto-clear handler — but `_logo_status` is empty at that point, so clearing is a no-op. However, the debounce timer ALSO starts (existing behavior), firing a fetch that sets `_logo_status` to "Fetching…". That's the CURRENT behavior and must not regress.

**How to avoid:** Do NOT wrap `_populate`'s `setText` in `blockSignals` — existing tests rely on the post-init fetch behavior (though it's implicit). Just ensure the new auto-clear handler is safe to call when `_logo_status.text()` is already empty (idempotent).

### Pitfall P-7: Import order and `_theme` discoverability

**What goes wrong:** `_art_paths.py` imports from `_theme` to get `STATION_ICON_SIZE`. If `_theme.py` at module top imports `QColor` from `PySide6.QtGui`, and `_art_paths.py` is imported early in test collection (before `QApplication` exists), `QColor("#c0392b")` at module import time is FINE (QColor does not require QApplication) — but some Qt types DO. Verify with `python -c "from PySide6.QtGui import QColor; c = QColor('#c0392b'); print(c.name())"`.

**How to avoid:** Keep `_theme.py` minimal — only `QColor`, `int`, and `str`. Do NOT put `QCursor(Qt.WaitCursor)` or `QPixmap` at module top-level in `_theme.py`; those require QGuiApplication.

## Sources

### Primary (HIGH confidence)
- Local codebase files (all read directly):
  - `musicstreamer/ui_qt/edit_station_dialog.py` (661 lines)
  - `musicstreamer/ui_qt/_art_paths.py` (79 lines)
  - `musicstreamer/ui_qt/settings_import_dialog.py` (247 lines)
  - `musicstreamer/ui_qt/import_dialog.py` (475 lines)
  - `musicstreamer/ui_qt/cookie_import_dialog.py`, `accent_color_dialog.py`, `station_tree_model.py`, `favorites_view.py`, `station_list_panel.py`, `main_window.py` (cursor pattern ref)
  - `musicstreamer/url_helpers.py` (`_is_aa_url`, `_aa_slug_from_url`, `_aa_channel_key_from_url` definitions)
  - `tests/test_edit_station_dialog.py`, `tests/test_art_paths.py`, `tests/test_settings_import_dialog.py` (existing patterns)
  - `.planning/config.json` (nyquist_validation=true confirmed)
- Grep-verified inventory:
  - `#c0392b` in `musicstreamer/`: 10 sites across 5 files — matches CONTEXT exactly
  - `QSize(32, 32)` in `musicstreamer/`: 3 sites across 2 files — matches CONTEXT exactly (station_list_panel.py has 2, favorites_view.py has 1)
  - `setOverrideCursor` in `musicstreamer/`: 1 precedent at `main_window.py:398`
  - `QTimer.singleShot` in `musicstreamer/`: 5 precedents (all player lifecycle, 0 ms deferred-dispatch)
  - No existing `_theme.py` anywhere in the codebase
  - No existing `STATION_ICON_SIZE` or `ERROR_COLOR` constant anywhere in `musicstreamer/`

### Secondary
- CONTEXT.md (`46-CONTEXT.md`) — locked decisions, inventory, discretion
- 40.1 UI-REVIEW.md — source of Top Fixes #1, #2, #3
- 45 UI-REVIEW.md — source of STATION_ICON_SIZE DRY recommendation
- 42 `.planning/debug/settings-import-silent-fail-on-readonly-db.md` — context for the `_ERROR_COLOR` local token's origin (not directly read but referenced in test docstrings)

### No external documentation needed
All Qt idioms have in-repo precedents (cursor override, QTimer lifecycle, blockSignals, setStyleSheet with both QSS-string and QColor forms). PySide6 API is stable; no Context7 or web search required for a code-cleanup phase of this scope.

## Metadata

**Confidence breakdown:**
- Token module structure: HIGH — mirrors existing `_art_paths.py` pattern
- Call-site inventory: HIGH — grep-verified against working tree
- Qt idioms (timer, cursor, stylesheet, blockSignals): HIGH — all have in-repo precedents
- `EditStationDialog` behavioral changes: HIGH for mechanical wiring, MEDIUM for the race-condition edge case between stale-token fetch-finish and new-URL textChanged (flagged in G-3 as known-existing race, not made worse by this phase)

**Research date:** 2026-04-17
**Valid until:** 30 days (PySide6 API is stable; codebase file inventory may shift if other phases land before 46 executes — re-grep `#c0392b` and `QSize(32, 32)` at plan time if more than a week passes).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| — | None | — | All claims are verified by direct code reads or grep against the working tree. |

No `[ASSUMED]` claims in this research — every factual statement was verified against the source tree at research time.
