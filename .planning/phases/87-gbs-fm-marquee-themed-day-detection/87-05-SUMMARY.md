---
phase: 87-gbs-fm-marquee-themed-day-detection
plan: "05"
subsystem: gbs-marquee
tags:
  - gbs.fm
  - announcement-banner
  - ui
  - plaintext-security
dependency_graph:
  requires:
    - 87-03 (GbsMarqueeWorker.marquee_ready Signal shape — first_segment, full_text)
    - 87-04 (attach_gbs_marquee_worker + NowPlayingPanel structure)
  provides:
    - AnnouncementBanner(QWidget) in musicstreamer/ui_qt/announcement_banner.py
    - NowPlayingPanel._on_marquee_ready slot (GBS-MARQ-03 predicate)
    - NowPlayingPanel._dismissed_announcement_hashes: set[str] (D-14 in-memory)
    - NowPlayingPanel._on_banner_dismissed slot
    - attach_gbs_marquee_worker extended with marquee_ready connection
  affects:
    - 87-06 (drift-guard greps announcement_banner.py for RichText — should return 0 hits)
tech_stack:
  added: []
  patterns:
    - TDD (RED 3e9520d4 → GREEN 5cafcff4 + e7b00104)
    - Qt.TextFormat.PlainText enforcement (CONVENTIONS T-40-04 / T-87-05-01)
    - Option (c) outer QVBoxLayout wrap — banner above 3-column inner layout
    - SHA-256 hash-keyed dismissal set (D-14 in-memory only)
    - Qt.QueuedConnection for cross-thread marquee_ready delivery
key_files:
  created:
    - musicstreamer/ui_qt/announcement_banner.py
    - tests/test_announcement_banner.py
  modified:
    - musicstreamer/ui_qt/now_playing_panel.py
decisions:
  - "Option (c) layout wrap: existing QHBoxLayout('outer') moved to _inner_widget; new QVBoxLayout(self) holds banner at row 0 and _inner_widget at row 1 with setContentsMargins(0,0,0,0) and setSpacing(0)"
  - "hash-keyed dismissal uses hashlib.sha256(first_segment.encode('utf-8')).hexdigest() — consistent with Plan 87-04 logo baseline pattern"
  - "Integration tests use monkeypatch(paths._root_override, tmp_path) to ensure no GBS cookies file exists, so _GbsPollWorker never fires real network calls during bind_station"
  - "block_real_network autouse fixture added to test_announcement_banner.py (mirrors test_now_playing_panel.py Phase 77 D-12 pattern)"
metrics:
  duration: "~16 minutes"
  completed: "2026-06-15"
  tasks: 2
  files: 3
---

# Phase 87 Plan 05: AnnouncementBanner Widget + NowPlayingPanel Wiring Summary

## What Was Built

**AnnouncementBanner(QWidget) with PlainText security lock + pipe→newline wrap + dismissed Signal; NowPlayingPanel outer QVBoxLayout wrap with banner at row 0; marquee_ready → _on_marquee_ready slot with GBS-MARQ-03 predicate; in-memory dismissal hash set.**

### Task 1 — AnnouncementBanner Widget (TDD)

`musicstreamer/ui_qt/announcement_banner.py` created:

- `class AnnouncementBanner(QWidget)`:
  - `__init__`: `QHBoxLayout` with `self._label: QLabel` (stretch=1, PlainText, wordWrap=True) + `self._dismiss_btn: QPushButton("×")` (flat, 24×24, `_on_dismiss_clicked` bound method).
  - `dismissed = Signal(str)` at class scope (Pitfall 4 — class scope, not instance).
  - `set_announcement(first_segment, announcement_hash)`: empty/whitespace → `clear()`; else `first_segment.replace("|", "\n")` → `setText`; show.
  - `clear()`: `setVisible(False)` + `setText("")`; `_current_hash` unchanged.
  - `_on_dismiss_clicked()`: `dismissed.emit(_current_hash)` → `clear()`.
  - Initially hidden (`setVisible(False)` in `__init__`).
- Security invariant: `Qt.TextFormat.PlainText` set explicitly (T-87-05-01 / CONVENTIONS T-40-04). ZERO `setTextFormat(Qt.RichText)` in the file.

`tests/test_announcement_banner.py` — 6 tests:

- `test_banner_uses_plaintext_format`: asserts `_label.textFormat() == Qt.TextFormat.PlainText`.
- `test_pipe_to_newline_wrap`: verifies `|` replaced by `\n`; all segments preserved.
- `test_dismiss_stores_hash`: dismissed Signal emits "deadbeef"; banner hidden after dismiss.
- `test_banner_hides_on_empty_announcement`: empty, non-empty, whitespace-only sequences.
- `test_banner_visibility_predicate`: full GBS-MARQ-03 predicate (show → dismiss → same hash hides → new hash re-shows).
- `test_banner_hides_on_non_gbs_bind`: non-GBS bind → banner stays hidden.

### Task 2 — NowPlayingPanel Banner Parenting + Signal Wiring (TDD)

`musicstreamer/ui_qt/now_playing_panel.py` extended:

**Imports:** `import hashlib` added; `from musicstreamer.ui_qt.announcement_banner import AnnouncementBanner` added.

**`__init__` layout restructure (Option c):**
- `self._announcement_banner = AnnouncementBanner(self)` constructed before layout build.
- `self._announcement_banner.dismissed.connect(self._on_banner_dismissed)` (AutoConnection, same-thread, QA-05).
- `_inner_widget = QWidget(self)` created.
- `_outer_v = QVBoxLayout(self)` with `setContentsMargins(0,0,0,0)` + `setSpacing(0)`.
- `_outer_v.addWidget(self._announcement_banner)` at row 0.
- `_outer_v.addWidget(_inner_widget)` at row 1.
- `outer = QHBoxLayout(_inner_widget)` — the existing three-column layout is now on `_inner_widget`, not on `self`.
- `self._dismissed_announcement_hashes: set[str] = set()` added.

**New methods:**
- `_on_banner_dismissed(announcement_hash: str)`: `_dismissed_announcement_hashes.add(announcement_hash)`.
- `_on_marquee_ready(first_segment: str, full_text: str)`: GBS-MARQ-03 predicate (non-GBS → clear; empty → clear; dismissed hash → clear; else `set_announcement`).

**Extended methods:**
- `attach_gbs_marquee_worker(worker)`: added `worker.marquee_ready.connect(self._on_marquee_ready, _Qt.QueuedConnection)` after existing `themed_logo_ready` connection.
- `bind_station(station)`: added `self._announcement_banner.clear()` when `station.provider_name != "GBS.FM"`.

## Outer QVBoxLayout Wrap Shape

```
NowPlayingPanel (QWidget)
└── _outer_v (QVBoxLayout, margins=0, spacing=0)
    ├── _announcement_banner (AnnouncementBanner, row 0, hidden by default)
    └── _inner_widget (QWidget, row 1)
        └── outer (QHBoxLayout, margins=16, spacing=24 — unchanged from pre-87-05)
            ├── logo_label (QLabel, 180×180)
            ├── center (QVBoxLayout, stretch=1)
            └── cover_label (QLabel, 180×180)
```

The banner takes full panel width and zero vertical space when hidden (Qt layout reclaims height for hidden widgets). The inner 3-column layout is byte-for-byte identical to the pre-87-05 shape — only its parent container changed from `self` to `_inner_widget`.

## Phase 71 RichText Baseline Confirmation

RichText count (via `grep -rn "setTextFormat(Qt.RichText)" musicstreamer/ | wc -l`) = **3**. Unchanged from Phase 71 baseline. The banner adds only a PlainText QLabel — ZERO new RichText labels.

The 3 surviving occurrences are:
1. `now_playing_panel.py:432` — `_sibling_label` (Phase 64 / D-01)
2. `now_playing_panel.py:752` — `_same_provider_links_label` (Phase 67 / D-04)
3. `now_playing_panel.py:768` — `_same_tag_links_label` (Phase 67 / D-04)

## Visual UAT Notes

Visual testing was done in offscreen mode via the pytest-qt suite. No live rendering was performed in this plan's scope. Narrow/medium/wide width UAT per `feedback_ui_bug_verify_with_extremes.md` is deferred to Phase 87 final UAT (after Plan 87-06). The outer QVBoxLayout wrap uses `setContentsMargins(0,0,0,0)` + `setSpacing(0)` so the banner sits flush above the existing 3-column layout with no visual gap.

The dismiss button (`×`) is 24×24 with `setFlat(True)` — small footprint, visually unobtrusive. The QLabel has `setWordWrap(True)` so long announcements wrap naturally; pipe-separated segments wrap at `\n` boundaries providing hint-aligned line breaks.

## AA Worker Lifecycle Tests

All 147 `tests/test_now_playing_panel.py` tests pass without modification. The outer QVBoxLayout wrap does not touch any `_AaLiveWorker` or `_GbsPollWorker` lifecycle paths — the inner layout and its GBS/AA machinery are identical to pre-87-05. No regressions to the AA poll behavior, `bind_station` / `on_playing_state_changed` test paths, or Phase 68 live-status transitions.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Added block_real_network autouse fixture to test file**
- **Found during:** Task 2 RED phase — integration test `test_banner_visibility_predicate` crashed Qt on teardown when `bind_station` with a GBS.FM station started `_GbsPollWorker` threads that made real network calls.
- **Issue:** `_GbsPollWorker.run()` calls `gbs_api.fetch_active_playlist` → `gbs_api._open_with_cookies` → `urllib.request.build_opener` which creates SSL contexts in a thread. When the panel was destroyed at test teardown, the in-flight thread crashed Qt (`QObjectPrivate::deleteChildren`).
- **Fix:** Added `@pytest.fixture(autouse=True) def _block_real_network_for_this_file(block_real_network): yield` (mirrors `test_now_playing_panel.py` Phase 77 D-12 pattern). Also added `monkeypatch.setattr(paths, "_root_override", str(tmp_path))` to integration tests so no GBS cookies file exists, preventing GBS poll timer from starting on `bind_station`. The `block_real_network` fixture blocks `urlopen`; the `_root_override` ensures `_is_gbs_logged_in()` returns False so no poll worker is spawned.
- **Files modified:** `tests/test_announcement_banner.py`
- **Commit:** Incorporated into Task 2 GREEN commit `e7b00104`

## Known Stubs

None. All API surface fully implemented:
- `AnnouncementBanner` — complete widget with all required methods.
- `NowPlayingPanel._on_marquee_ready` — full GBS-MARQ-03 predicate implemented.
- `NowPlayingPanel._on_banner_dismissed` — stores hash in dismissed set.
- `attach_gbs_marquee_worker` — both `themed_logo_ready` and `marquee_ready` connections wired.
- `bind_station` — clears banner on non-GBS rebind.

## Threat Flags

No new network endpoints, auth paths, or schema changes beyond those in the plan's threat model. The banner QLabel uses `Qt.TextFormat.PlainText` — T-87-05-01 mitigated. No file IO, no SQLite writes, no cross-process communication. The dismissed hash set is in-memory only (D-14).

## Self-Check: PASSED

- `test -f musicstreamer/ui_qt/announcement_banner.py` — FOUND
- `test -f tests/test_announcement_banner.py` — FOUND
- `grep -c "^class AnnouncementBanner" musicstreamer/ui_qt/announcement_banner.py` → 1
- `grep -c "Qt.TextFormat.PlainText" musicstreamer/ui_qt/announcement_banner.py` → 2 (setTextFormat call + comment reference)
- `grep -c "setTextFormat(Qt.TextFormat.PlainText)" musicstreamer/ui_qt/announcement_banner.py` → 1 (the actual call)
- `grep -c "setWordWrap(True)" musicstreamer/ui_qt/announcement_banner.py` → 1
- `grep -c "dismissed = Signal(str)" musicstreamer/ui_qt/announcement_banner.py` → 1
- `grep -E "setTextFormat\(Qt\.RichText\)" musicstreamer/ui_qt/announcement_banner.py` → 0 hits (correct)
- `grep -rn "setTextFormat(Qt.RichText)" musicstreamer/ | wc -l` → 3 (Phase 71 baseline unchanged)
- `grep -c "AnnouncementBanner" musicstreamer/ui_qt/now_playing_panel.py` → 2 (import + constructor call)
- `grep -c "_dismissed_announcement_hashes" musicstreamer/ui_qt/now_playing_panel.py` → 4
- `grep -c "_on_marquee_ready" musicstreamer/ui_qt/now_playing_panel.py` → 3
- `grep -c "_on_banner_dismissed" musicstreamer/ui_qt/now_playing_panel.py` → 3
- `grep -c "worker.marquee_ready.connect" musicstreamer/ui_qt/now_playing_panel.py` → 1
- RED commit `3e9520d4` — exists
- Task 1 GREEN commit `5cafcff4` — exists
- Task 2 GREEN commit `e7b00104` — exists
- `uv run --with pytest --with pytest-qt pytest tests/test_announcement_banner.py` → 6/6 passed
- `uv run --with pytest --with pytest-qt pytest tests/test_announcement_banner.py tests/test_gbs_marquee.py` → 30/30 passed
- `uv run --with pytest --with pytest-qt pytest tests/test_now_playing_panel.py` → 147/147 passed
- `uv run --with pytest --with pytest-qt pytest tests/test_constants_drift.py::test_richtext_baseline_unchanged_by_phase_71` → PASSED
