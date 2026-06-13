---
phase: 89A-channel-avatar-db-migration-storage-layout
reviewed: 2026-06-13T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - musicstreamer/paths.py
  - musicstreamer/assets.py
  - musicstreamer/repo.py
  - tests/test_paths.py
  - tests/test_repo.py
findings:
  critical: 1
  warning: 1
  info: 1
  total: 3
status: issues_found
---

# Phase 89A: Code Review Report

**Reviewed:** 2026-06-13T00:00:00Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Phase 89A is a minimal additive change: a new `channel_avatars_dir()` path accessor, one `os.makedirs` call in `ensure_dirs()`, and one `ALTER TABLE stations ADD COLUMN channel_avatar_path TEXT` migration block in `db_init()`.

The storage-layout and DB migration pieces are individually correct: the path accessor respects `_root_override`, the `makedirs` ordering is safe (parent `assets/` is created on line 9 before the child `assets/channel-avatars/` on line 10), and the ALTER TABLE block is idempotent via the established `try/except sqlite3.OperationalError` pattern.

However, **the new DB column is stranded**: `channel_avatar_path` exists in the schema but is never wired into the `Station` dataclass or the four `Station(...)` builder call sites in `repo.py`. Any consumer reading a station row cannot see the value. The tests in `test_repo.py` only verify schema shape (PRAGMA table_info) and data preservation for the legacy-migration path; they do not catch the missing hydration because they never call `repo.get_station()` and check `station.channel_avatar_path`. Additionally, `test_paths_do_no_io_on_import` does not call `channel_avatars_dir()`, leaving a gap in the purity coverage inherited by new accessors.

---

## Critical Issues

### CR-01: `channel_avatar_path` column is never hydrated into `Station` objects

**File:** `musicstreamer/repo.py:556,595,704,819`
**Issue:** `db_init()` adds `channel_avatar_path TEXT` to the `stations` table (line 321), but none of the four `Station(...)` builder call sites — `list_stations` (L556), `get_station` (L595), `list_recently_played` (L704), `list_favorite_stations` (L819) — read `r["channel_avatar_path"]` from the row. The `Station` dataclass in `models.py` also has no `channel_avatar_path` field. The column exists in SQLite but is invisible to every caller. Any Phase 89B/90 code that assumes `station.channel_avatar_path` is available will get `AttributeError` at runtime.

**Fix:** Add the field to the `Station` dataclass and hydrate it in all four builders.

`musicstreamer/models.py` — add after `album_fallback_path`:
```python
channel_avatar_path: Optional[str] = None   # Phase 89A D-04
```

`musicstreamer/repo.py` — in each of the four `Station(...)` calls, add:
```python
channel_avatar_path=r["channel_avatar_path"],
```

---

## Warnings

### WR-01: Tests do not exercise `channel_avatar_path` round-trip through any Station builder

**File:** `tests/test_repo.py:1171-1264`
**Issue:** `test_channel_avatar_path_migration_idempotent` and `test_channel_avatar_path_schema_convergence` verify only PRAGMA table_info shape and NULL data preservation. Neither test writes a non-NULL value to `channel_avatar_path` and then reads it back via `repo.get_station()` (or any other Station builder). Because of CR-01 (field missing from the dataclass and all builders), these tests pass today while the functional wiring is completely absent — the test suite gives a false green. This mirrors the Phase 82 preferred_stream_id and Phase 83 prerolls_fetched_at test pattern, which each include a "round-trips via all 4 Station builders" test that would catch exactly this failure.

**Fix:** Add a round-trip hydration test after CR-01 is fixed:
```python
def test_channel_avatar_path_round_trips_via_get_station(repo):
    sid = repo.create_station()
    repo.con.execute(
        "UPDATE stations SET channel_avatar_path = ? WHERE id = ?",
        ("assets/channel-avatars/42.png", sid),
    )
    repo.con.commit()
    st = repo.get_station(sid)
    assert st.channel_avatar_path == "assets/channel-avatars/42.png"
```
A companion test covering `list_stations`, `list_recently_played`, and `list_favorite_stations` should follow the Phase 82/83 "all 4 builders" precedent already established in this file.

---

## Info

### IN-01: `test_paths_do_no_io_on_import` does not call `channel_avatars_dir()`

**File:** `tests/test_paths.py:38-58`
**Issue:** The purity sweep at lines 48–56 calls every existing path accessor but omits the two newer ones (`eq_profiles_dir()` and `channel_avatars_dir()`). Adding a new pure accessor and not enrolling it in this test means the purity guarantee can silently break in future edits (e.g. if someone accidentally adds a `makedirs` call inside the accessor). The omission of `eq_profiles_dir()` is pre-existing; `channel_avatars_dir()` is new to this phase.

**Fix:** Add both omitted accessors to the purity sweep:
```python
paths.eq_profiles_dir()
paths.channel_avatars_dir()
```
(lines 56–57, before the `after = set(os.listdir(tmp_path))` assertion)

---

_Reviewed: 2026-06-13T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
