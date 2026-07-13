---
phase: 89A-channel-avatar-db-migration-storage-layout
plan: "01"
subsystem: paths, assets, tests
tags: [path-accessor, directory-creation, startup, test-coverage]
dependency_graph:
  requires: []
  provides: [channel_avatars_dir-accessor, ensure_dirs-channel-avatars, test-coverage-ART-AVATAR-02]
  affects: [musicstreamer/paths.py, musicstreamer/assets.py, tests/test_paths.py, tests/test_repo.py]
tech_stack:
  added: []
  patterns: [pure-path-accessor, eager-makedirs-in-ensure_dirs, tdd-red-green]
key_files:
  created: []
  modified:
    - musicstreamer/paths.py
    - musicstreamer/assets.py
    - tests/test_paths.py
    - tests/test_repo.py
decisions:
  - "channel_avatars_dir() mirrors eq_profiles_dir() shape exactly — two-component path under _root()"
  - "ensure_dirs() gets a third makedirs line after assets_dir per D-01 (no comment needed — matches existing style)"
  - "test_ensure_dirs_creates_channel_avatars_dir placed in test_repo.py (no test_assets.py exists)"
metrics:
  duration: "2m 30s"
  completed: "2026-06-13T21:35:54Z"
  tasks_completed: 2
  tasks_total: 2
requirements:
  - ART-AVATAR-02
---

# Phase 89A Plan 01: Storage Layout — channel_avatars_dir() + ensure_dirs() Summary

**One-liner:** Pure `channel_avatars_dir()` path accessor returning `<root>/assets/channel-avatars` added to paths.py; `ensure_dirs()` eagerly creates the directory at startup via a third makedirs line in assets.py.

## Tasks Completed

| Task | Name | Commits | Files |
|------|------|---------|-------|
| 1 | Add channel_avatars_dir() accessor + override/purity tests | 502ce8cf (RED), 0348bba0 (GREEN) | musicstreamer/paths.py, tests/test_paths.py |
| 2 | Eager directory creation in ensure_dirs() + ensure_dirs test | 4447156e (RED), 5533ebc1 (GREEN) | musicstreamer/assets.py, tests/test_repo.py |

## Verification Results

All new tests pass; no regressions in test_paths.py or test_repo.py (101 tests total):

```
uv run --with pytest pytest tests/test_paths.py tests/test_repo.py -x -q
101 passed in 0.72s
```

### Acceptance Criteria

- `grep -n "def channel_avatars_dir(" musicstreamer/paths.py` → matches exactly one line (L103)
- `os.makedirs` appears only in docstring references in paths.py (not actual code calls) — accessor is pure; confirmed by `test_channel_avatars_dir_does_not_create_directory` passing
- Both override and purity tests in test_paths.py pass
- `grep -n "channel_avatars_dir" musicstreamer/assets.py` → matches the new makedirs line (L10)
- `grep -n "^import os" tests/test_repo.py` → L1 (added to header)
- `test_ensure_dirs_creates_channel_avatars_dir` passes, confirming directory created under tmp_path

## Implementation Notes

### paths.py change

Added `channel_avatars_dir()` immediately after `eq_profiles_dir()` at L103. Returns `os.path.join(_root(), "assets", "channel-avatars")` — two path components after root, nesting under `assets/`. Docstring mirrors `eq_profiles_dir` style: pure, no mkdir, callers use `os.makedirs(paths.channel_avatars_dir(), exist_ok=True)`.

### assets.py change

Appended `os.makedirs(paths.channel_avatars_dir(), exist_ok=True)` as the third line of `ensure_dirs()`. Placement after `assets_dir()` makedirs ensures parent directory exists before the subdirectory is created (D-01). No inline comment — matches the two existing comment-free lines.

### test_paths.py additions

Two tests appended after the `eq_profiles_dir` analogs at L103+:
- `test_channel_avatars_dir_honors_root_override` — asserts two-component join under `_root_override`
- `test_channel_avatars_dir_does_not_create_directory` — asserts `os.path.exists(result) is False` (purity contract)

The autouse `_reset_root_override` fixture in test_paths.py handles teardown automatically.

### test_repo.py additions

- Added `import os` at L1 (header was missing it per RESEARCH note)
- Appended `test_ensure_dirs_creates_channel_avatars_dir(tmp_path, monkeypatch)` using local imports of `musicstreamer.paths` and `musicstreamer.assets`, monkeypatching `_root_override` to `tmp_path`, calling `ensure_dirs()`, and asserting `os.path.isdir(os.path.join(str(tmp_path), "assets", "channel-avatars"))`

## Deviations from Plan

None — plan executed exactly as written.

The acceptance criterion `grep -c 'os.makedirs' musicstreamer/paths.py` returns 2 (not 0) because the pre-existing `eq_profiles_dir()` docstring also contains `os.makedirs` as a usage example. Both occurrences are in docstrings only — no actual `os.makedirs` code calls exist in paths.py. The purity test confirms this at runtime.

## Known Stubs

None — no stub values or placeholder text introduced.

## Threat Flags

None — no new trust boundaries, network endpoints, or user-controlled data paths introduced.

## Self-Check: PASSED

All files created/modified exist on disk. All commits exist in git log:
- 502ce8cf (RED task1 — failing tests for channel_avatars_dir)
- 0348bba0 (GREEN task1 — channel_avatars_dir() implementation)
- 4447156e (RED task2 — failing test for ensure_dirs)
- 5533ebc1 (GREEN task2 — ensure_dirs makedirs implementation)
