# Phase 89A: Channel-Avatar DB Migration + Storage Layout - Pattern Map

**Mapped:** 2026-06-13
**Files analyzed:** 7 (3 modified source files + 4 new test functions across 2 test files)
**Analogs found:** 7 / 7

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `musicstreamer/paths.py` (ADD `channel_avatars_dir()`) | utility/path | transform | `paths.eq_profiles_dir()` (L94–101) | exact |
| `musicstreamer/assets.py` (MODIFY `ensure_dirs()`) | utility/startup | transform | `assets.ensure_dirs()` existing body (L7–9) | exact |
| `musicstreamer/repo.py` (MODIFY `db_init()`) | model/migration | CRUD | `db_init()` Phase 83 `prerolls_fetched_at` block (L297–311) | exact |
| `tests/test_repo.py` — `test_channel_avatar_path_migration_idempotent` | test | request-response | `test_preferred_stream_id_migration_idempotent` (L875–897) | exact |
| `tests/test_repo.py` — `test_channel_avatar_path_schema_convergence` | test | request-response | `test_bitrate_kbps_migration_adds_column` (L642–678) | role-match |
| `tests/test_repo.py` — `test_ensure_dirs_creates_channel_avatars_dir` | test | file-I/O | `test_eq_profiles_dir_does_not_create_directory` (test_paths.py L98–102) | role-match |
| `tests/test_paths.py` — `test_channel_avatars_dir_honors_root_override` + `test_channel_avatars_dir_does_not_create_directory` | test | transform | `test_eq_profiles_dir_honors_root_override` + `test_eq_profiles_dir_does_not_create_directory` (test_paths.py L92–102) | exact |

---

## Pattern Assignments

### `musicstreamer/paths.py` — ADD `channel_avatars_dir()` (utility, transform)

**Analog:** `musicstreamer/paths.py` — `eq_profiles_dir()` at L94–101

**Core accessor pattern** (L94–101 — copy this shape verbatim):
```python
def eq_profiles_dir() -> str:
    """Return the directory holding imported AutoEQ profiles (Phase 47.2 D-12).

    Pure — does NOT create the directory. Callers use
    ``os.makedirs(paths.eq_profiles_dir(), exist_ok=True)`` before writing.
    """
    return os.path.join(_root(), "eq-profiles")
```

**New function to add immediately after L101:**
```python
def channel_avatars_dir() -> str:
    """Phase 89A D-02: flat directory for per-station channel avatar PNGs.

    Pure — does NOT create the directory. Callers use
    ``os.makedirs(paths.channel_avatars_dir(), exist_ok=True)`` before writing.
    Respects ``_root_override`` via ``_root()`` for test isolation.
    """
    return os.path.join(_root(), "assets", "channel-avatars")
```

**Key constraints:**
- Path is `assets/channel-avatars` (two path components after `_root()`), unlike `eq_profiles_dir` which is one level. Use `os.path.join(_root(), "assets", "channel-avatars")` exactly.
- No `os.makedirs` inside this function — module is pure (L1–15 docstring). Purity is tested by `test_paths_do_no_io_on_import` (test_paths.py L38–58).
- The `_root_override` hook is inherited automatically through `_root()` (L28–31) — no special handling needed.

---

### `musicstreamer/assets.py` — MODIFY `ensure_dirs()` (utility/startup, file-I/O)

**Analog:** `musicstreamer/assets.py` — current `ensure_dirs()` body at L7–9

**Current body** (L7–9 — confirmed):
```python
def ensure_dirs():
    os.makedirs(paths.data_dir(), exist_ok=True)
    os.makedirs(paths.assets_dir(), exist_ok=True)
```

**After modification (append one line matching the exact style):**
```python
def ensure_dirs():
    os.makedirs(paths.data_dir(), exist_ok=True)
    os.makedirs(paths.assets_dir(), exist_ok=True)
    os.makedirs(paths.channel_avatars_dir(), exist_ok=True)
```

**Key constraints:**
- No inline comment needed — the existing two lines have none; match the style.
- `exist_ok=True` is mandatory (prevents `FileExistsError` on second startup; see Anti-Patterns).
- `paths.channel_avatars_dir()` is the only reference to the path string — no duplicate literals.
- `assets_dir()` (L43) must already be `makedirs`-ed before `channel_avatars_dir()` since the latter is a subdirectory of `assets/`. The ordering is preserved by appending after the `assets_dir` line.

---

### `musicstreamer/repo.py` — MODIFY `db_init()` (model/migration, CRUD)

**Analog:** `musicstreamer/repo.py` — Phase 83 `prerolls_fetched_at` block at L297–311 (confirmed)

**Closest analog** (L297–311 — direct copy template for a nullable column with no DEFAULT):
```python
    # Phase 83 D-04/D-15 — lazy-backfill timestamp; nullable INTEGER no DEFAULT;
    # idempotent via OperationalError catch; lands AFTER the stations_new rebuild
    # block for the same Pitfall 2 reason called out in the Phase 82 comment
    # above. Epoch seconds; NULL means "never fetched"; non-NULL means
    # "fetched, even if 0 prerolls returned" — distinguishes legitimately-empty
    # SomaFM channels from never-fetched ones (D-04, RESEARCH §Background fetch
    # gate). The on-demand backfill gate becomes: 0 prerolls AND fetched_at IS
    # NULL → schedule fetch; otherwise skip.
    try:
        con.execute(
            "ALTER TABLE stations ADD COLUMN prerolls_fetched_at INTEGER"
        )
        con.commit()
    except sqlite3.OperationalError:
        pass  # column already exists — idempotent
```

**New block to insert immediately after L311 (after the `pass` of the Phase 83 block):**
```python
    # Phase 89A D-04/D-05 — channel avatar path; nullable TEXT no DEFAULT.
    # NULL means no avatar stored; existing rows backfill automatically.
    # MUST land AFTER the legacy URL-column rebuild block (Pitfall 2): the
    # rebuild's CREATE TABLE stations_new / INSERT SELECT does not carry
    # dynamically-added columns, so placing the ALTER here ensures the column
    # lands on the rebuilt (or fresh) table. Idempotent via the same
    # try/except sqlite3.OperationalError idiom as the Phase 73/82/83 blocks above.
    try:
        con.execute("ALTER TABLE stations ADD COLUMN channel_avatar_path TEXT")
        con.commit()
    except sqlite3.OperationalError:
        pass  # column already exists — idempotent
```

**Key constraints:**
- Insertion point is L312 (the blank line after `pass  # column already exists — idempotent` that closes the Phase 83 block). Do NOT place before the `stations_new` rebuild block which ends at L265.
- Column spec is `TEXT` with no `DEFAULT` and no `NOT NULL` — nullable, NULL means no avatar. Mirrors `prerolls_fetched_at INTEGER` shape exactly except type is `TEXT`.
- The `con.commit()` inside the `try` is required (matches all three existing phase blocks at L278, L293, L309).
- `db_init` ends at L312 and `sweep_orphans` starts at L314 — the new block must stay within `db_init`.

---

## Test Pattern Assignments

### `tests/test_repo.py` — `test_channel_avatar_path_migration_idempotent` (test, request-response)

**Analog:** `test_preferred_stream_id_migration_idempotent` at test_repo.py L875–897

**Fixture:** `repo` (L6–13) — connects to `tmp_path`-based DB, calls `db_init()` once on construction.

**Core PRAGMA assertion pattern** (L875–897 — copy this shape verbatim, substituting column name and type):
```python
def test_preferred_stream_id_migration_idempotent(repo):
    # Second and third db_init calls must not raise.
    db_init(repo.con)
    db_init(repo.con)

    cols = repo.con.execute("PRAGMA table_info('stations')").fetchall()
    by_name = {row[1]: row for row in cols}
    assert "preferred_stream_id" in by_name, (
        f"preferred_stream_id column missing; got {sorted(by_name)}"
    )
    col = by_name["preferred_stream_id"]
    # type is index 2; notnull is index 3; dflt_value is index 4
    assert col[2] == "INTEGER", f"column type must be INTEGER; got {col[2]!r}"
    assert col[3] == 0, "preferred_stream_id must be nullable (notnull=0)"
    assert col[4] is None, (
        f"preferred_stream_id must have no DEFAULT; got {col[4]!r}"
    )
```

**Adaptation for `channel_avatar_path`:** replace `"preferred_stream_id"` with `"channel_avatar_path"`, replace `"INTEGER"` with `"TEXT"`.

---

### `tests/test_repo.py` — `test_channel_avatar_path_schema_convergence` (test, request-response)

**Analog:** `test_bitrate_kbps_migration_adds_column` pattern at test_repo.py L642–678 (pre-migration schema fixture shape).

**Helper used:** `_make_bare_con()` at test_repo.py L620–624 (confirmed):
```python
def _make_bare_con():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    return con
```

**Test structure to follow (D-07b):**
1. `fresh_con = _make_bare_con(); db_init(fresh_con)` — captures the target schema.
2. `legacy_con = _make_bare_con()` + `executescript(...)` — builds a pre-89a `stations` table (all columns through `prerolls_fetched_at`, but NOT `channel_avatar_path`). Insert one row to verify data survival.
3. Assert `channel_avatar_path` absent in `legacy_con` pre-migration.
4. `db_init(legacy_con)` — applies migration.
5. Assert `migrated_cols["channel_avatar_path"] == fresh_cols["channel_avatar_path"]` — schema convergence.
6. Assert existing row still has `channel_avatar_path IS NULL` — no data loss.

**Pre-89a stations DDL to use in `executescript`** (must include all columns present before this phase, in declaration order from `db_init`'s `CREATE TABLE IF NOT EXISTS stations`):
```sql
CREATE TABLE providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE stations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    provider_id INTEGER,
    tags TEXT DEFAULT '',
    station_art_path TEXT,
    album_fallback_path TEXT,
    icy_disabled INTEGER NOT NULL DEFAULT 0,
    last_played_at TEXT,
    is_favorite INTEGER NOT NULL DEFAULT 0,
    cover_art_source TEXT NOT NULL DEFAULT 'auto',
    preferred_stream_id INTEGER,
    prerolls_fetched_at INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(provider_id) REFERENCES providers(id) ON DELETE SET NULL
);
INSERT INTO stations(name) VALUES ('ExistingFM');
```

Note: `station_streams` table is referenced by `preferred_stream_id FK` but SQLite defers FK checks; `_make_bare_con()` enables foreign keys via PRAGMA, so include a minimal `station_streams` DDL if `db_init` will try to reference it during the ALTER. Inspect the full `db_init` body to determine whether the legacy schema needs `station_streams` too before running `db_init` on it.

---

### `tests/test_repo.py` — `test_ensure_dirs_creates_channel_avatars_dir` (test, file-I/O)

**Analog:** `test_eq_profiles_dir_does_not_create_directory` (test_paths.py L98–102) — inverted: this test asserts the directory IS created.

**Fixture:** `tmp_path` + `monkeypatch` (pytest builtins). No `repo` fixture needed.

**Pattern:**
```python
def test_ensure_dirs_creates_channel_avatars_dir(tmp_path, monkeypatch):
    import musicstreamer.paths as paths_mod
    import musicstreamer.assets as assets_mod
    monkeypatch.setattr(paths_mod, "_root_override", str(tmp_path))
    assets_mod.ensure_dirs()
    assert os.path.isdir(os.path.join(str(tmp_path), "assets", "channel-avatars"))
```

**File location:** Append to `tests/test_repo.py` (no `tests/test_assets.py` exists — confirmed by directory listing). Add `import os` at top if not already present (it is not currently imported in test_repo.py header; verify before appending).

---

### `tests/test_paths.py` — `test_channel_avatars_dir_honors_root_override` + `test_channel_avatars_dir_does_not_create_directory` (test, transform)

**Analog:** `test_eq_profiles_dir_honors_root_override` (L92–95) and `test_eq_profiles_dir_does_not_create_directory` (L98–102) — exact shape.

**Existing analog** (L92–102 — copy and substitute `eq_profiles_dir` → `channel_avatars_dir`, `"eq-profiles"` → `"assets", "channel-avatars"`):
```python
def test_eq_profiles_dir_honors_root_override(monkeypatch, tmp_path):
    """Phase 47.2 D-12: eq-profiles dir resolves under the override root."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    assert paths.eq_profiles_dir() == os.path.join(str(tmp_path), "eq-profiles")


def test_eq_profiles_dir_does_not_create_directory(monkeypatch, tmp_path):
    """Purity contract: helper returns a string; it does NOT mkdir."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    result = paths.eq_profiles_dir()
    assert os.path.exists(result) is False
```

**Adaptation:** The expected path is `os.path.join(str(tmp_path), "assets", "channel-avatars")`, not `os.path.join(str(tmp_path), "channel-avatars")`. Two path components because `channel_avatars_dir()` nests under `assets/`.

**File location:** Append to `tests/test_paths.py` after L102 (current last line). The `autouse` `_reset_root_override` fixture at L10–17 applies automatically — no extra teardown needed.

---

## Shared Patterns

### _root_override Test Isolation
**Source:** `musicstreamer/paths.py` L24–31, `tests/test_paths.py` L10–17
**Apply to:** All tests that call `paths.channel_avatars_dir()`, `assets.ensure_dirs()`, or any path accessor.

```python
# paths.py L24-31 — the hook:
_root_override: str | None = None

def _root() -> str:
    if _root_override is not None:
        return _root_override
    return platformdirs.user_data_dir("musicstreamer")

# test_paths.py L10-17 — autouse fixture that resets it:
@pytest.fixture(autouse=True)
def _reset_root_override():
    saved = paths._root_override
    paths._root_override = None
    yield
    paths._root_override = saved
```

Use `monkeypatch.setattr(paths, "_root_override", str(tmp_path))` in new tests (preferred — auto-restores). The autouse fixture in test_paths.py covers that file; test_repo.py tests must use `monkeypatch` explicitly.

### Idempotent ALTER TABLE Idiom
**Source:** `musicstreamer/repo.py` L274–311 (three existing instances)
**Apply to:** `db_init()` new block only.

```python
try:
    con.execute("ALTER TABLE stations ADD COLUMN <name> <type>")
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists — idempotent
```

### PRAGMA table_info Assertion Shape
**Source:** `tests/test_repo.py` L885–896
**Apply to:** `test_channel_avatar_path_migration_idempotent`

```python
cols = repo.con.execute("PRAGMA table_info('stations')").fetchall()
by_name = {row[1]: row for row in cols}
# row tuple: (cid=0, name=1, type=2, notnull=3, dflt_value=4, pk=5)
col = by_name["<column_name>"]
assert col[2] == "<TYPE>"
assert col[3] == 0      # nullable
assert col[4] is None   # no DEFAULT
```

---

## No Analog Found

None — all 7 file targets have exact or role-match analogs in the live codebase.

---

## Implementation Order (for planner)

The three source changes have a dependency chain: `paths.py` must be modified before `assets.py` (since `ensure_dirs` calls `channel_avatars_dir()`), and both can land independently of `repo.py`. Tests depend only on the source files they test.

1. `musicstreamer/paths.py` — add `channel_avatars_dir()` after L101
2. `musicstreamer/assets.py` — append makedirs line to `ensure_dirs()` after L9
3. `musicstreamer/repo.py` — append ALTER block after L311 (inside `db_init`, before `sweep_orphans` at L314)
4. `tests/test_paths.py` — append two purity/override tests after L102
5. `tests/test_repo.py` — append idempotency test, schema-convergence test, and ensure_dirs test

---

## Metadata

**Analog search scope:** `musicstreamer/` (paths.py, assets.py, repo.py), `tests/` (test_repo.py, test_paths.py)
**Files scanned:** 5 source files, 2 test files
**Line numbers verified:** All cited line numbers confirmed against live codebase on 2026-06-13
**Pattern extraction date:** 2026-06-13
