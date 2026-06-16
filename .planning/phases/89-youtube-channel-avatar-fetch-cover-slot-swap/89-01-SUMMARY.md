---
phase: 89-youtube-channel-avatar-fetch-cover-slot-swap
plan: "01"
subsystem: data-model
tags: [channel-avatar, sqlite, models, repo, assets, atomic-write, tdd]
dependency_graph:
  requires: [89a]
  provides: [channel_avatar_path-on-Station, update_channel_avatar_path, write_channel_avatar]
  affects: [musicstreamer/models.py, musicstreamer/repo.py, musicstreamer/assets.py]
tech_stack:
  added: []
  patterns: [atomic-write-mkstemp-os.replace, dedicated-write-method, keyword-default-precedent]
key_files:
  created:
    - tests/test_assets_avatar.py
  modified:
    - musicstreamer/models.py
    - musicstreamer/repo.py
    - musicstreamer/assets.py
    - tests/test_repo.py
decisions:
  - "channel_avatar_path written ONLY via update_channel_avatar_path, never via update_station (Pitfall 5 / T-89-03)"
  - "tempfile.mkstemp(dir=dst_dir) used to guarantee same-filesystem atomic rename (A2 / T-89-01)"
  - "import tempfile added at module level in assets.py (not lazy import — simpler for this standalone function)"
metrics:
  duration: "~12 min"
  completed: "2026-06-16"
  tasks_completed: 2
  files_changed: 4
---

# Phase 89 Plan 01: Channel Avatar Storage Plumbing Summary

**One-liner:** `channel_avatar_path` field on `Station` dataclass wired through 4 repo read mappers + isolated write method, plus `write_channel_avatar` atomic PNG writer using `tempfile.mkstemp` + `os.replace` — foundation for Plans 02 and 04.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests: channel_avatar_path model/repo | cc4dd9fd | tests/test_repo.py (+72 lines) |
| 1 (GREEN) | Thread channel_avatar_path through models + repo | 9a4cfc6a | musicstreamer/models.py, musicstreamer/repo.py |
| 2 (RED) | Failing tests: assets.write_channel_avatar | 4bcc931e | tests/test_assets_avatar.py (new) |
| 2 (GREEN) | Add assets.write_channel_avatar atomic PNG writer | 53b6cc76 | musicstreamer/assets.py |

## What Was Built

### Task 1: channel_avatar_path plumbing (D-13)

- Added `channel_avatar_path: Optional[str] = None  # Phase 89 D-13` to `Station` dataclass in `musicstreamer/models.py`, immediately after `prerolls_fetched_at`.
- Wired `channel_avatar_path=r["channel_avatar_path"]` into all 4 `Station(...)` constructor call sites:
  - `list_stations` (~L572)
  - `get_station` (~L611)
  - `list_recently_played` (~L720)
  - `list_favorite_stations` (~L835)
- Added dedicated write method `update_channel_avatar_path(station_id: int, path: Optional[str]) -> None` to `Repo` class, mirroring `update_station_art`. Uses a single `UPDATE stations SET channel_avatar_path = ? WHERE id = ?` + commit. NOT routed through `update_station` (Pitfall 5 / T-89-03).
- 7 new tests in `tests/test_repo.py`: default-None, round-trip, clear-to-None, no-reset-via-update_station, and mapper coverage for all 4 list methods.

### Task 2: write_channel_avatar atomic PNG writer (D-12)

- Added `write_channel_avatar(station_id: int, data: bytes) -> str` to `musicstreamer/assets.py`.
- Implements D-12 atomic overwrite: `tempfile.mkstemp(dir=dst_dir, suffix=".png.tmp")` + `os.write` + `os.close` + `os.replace(tmp, dst)`.
- mkstemp in `dst_dir` guarantees same filesystem so `os.replace` is atomic (A2).
- Exception path: closes fd and unlinks tmp before re-raising (T-89-01 DoS mitigation).
- Returns `os.path.relpath(dst, paths.data_dir())` — e.g. `assets/channel-avatars/12.png`.
- Added `import tempfile` at module level in assets.py.
- 3 new tests in `tests/test_assets_avatar.py`: creates file + correct relative path, atomic overwrite leaves no .tmp, failure cleans up temp.

## Verification

```
tests/test_repo.py     98 passed (includes 7 new Phase 89 tests)
tests/test_assets_avatar.py   3 passed (all new)
tests/test_paths.py    12 passed (no regression)
Total: 113 passed, 1 warning
```

## Acceptance Criteria

- [x] `grep -n "channel_avatar_path" musicstreamer/models.py` shows field on Station (L43)
- [x] `grep -c "channel_avatar_path=r\[" musicstreamer/repo.py` returns 4 (all mappers wired)
- [x] `grep -n "def update_channel_avatar_path" musicstreamer/repo.py` matches (L850)
- [x] `def update_station` body does NOT reference `channel_avatar_path`
- [x] `grep -n "def write_channel_avatar" musicstreamer/assets.py` matches; body contains `os.replace` and `tempfile.mkstemp`
- [x] All tests pass

## Deviations from Plan

None — plan executed exactly as written. TDD RED/GREEN cycle followed for both tasks. The exception handling in `write_channel_avatar` uses a slightly more defensive `try/except OSError` around `os.close(fd)` as well as `os.unlink(tmp)` (the fd close may fail if the OS already closed it on exception; this is belt-and-suspenders).

## TDD Gate Compliance

Task 1:
- RED commit: cc4dd9fd (test(89-01): add failing tests for channel_avatar_path model/repo plumbing)
- GREEN commit: 9a4cfc6a (feat(89-01): thread channel_avatar_path through models + repo read/write)

Task 2:
- RED commit: 4bcc931e (test(89-01): add failing tests for assets.write_channel_avatar atomic PNG writer)
- GREEN commit: 53b6cc76 (feat(89-01): add assets.write_channel_avatar atomic PNG writer)

Both tasks satisfy RED→GREEN gate sequence.

## Threat Surface Scan

No new network endpoints, auth paths, or trust boundaries introduced. The `write_channel_avatar` function accepts `station_id: int` (from SQLite, not user-controlled string) — T-89-02 mitigation is intact. The atomic write via mkstemp+os.replace mitigates T-89-01. The `update_channel_avatar_path` dedicated method mitigates T-89-03.

## Known Stubs

None — all data flows are wired. The `channel_avatar_path` field starts as None for new stations (correct sentinel) and is only populated by `update_channel_avatar_path`, which Plans 02+ will call after avatar fetch.

## Self-Check

Files created/modified:
- musicstreamer/models.py — FOUND
- musicstreamer/repo.py — FOUND
- musicstreamer/assets.py — FOUND
- tests/test_repo.py — FOUND
- tests/test_assets_avatar.py — FOUND
